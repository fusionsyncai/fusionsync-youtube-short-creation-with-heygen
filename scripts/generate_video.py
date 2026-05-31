"""
Generate a HeyGen short video from a memory/videos/*.md entry.

Usage:
    python scripts/generate_video.py memory/videos/2026-05-31-meta-ads-funnel-leak.md

What it does:
    1. Parses the "## 2. HeyGen Voice Script" section out of the markdown file.
    2. Estimates duration & credit cost. ABORTS if estimated credits > MAX_CREDITS_PER_VIDEO.
    3. POSTs to https://api.heygen.com/v3/videos.
    4. Polls until status=completed, then downloads the MP4 to output/<slug>.mp4.
    5. Updates the markdown frontmatter: status -> 'recorded', adds local_video_path.

Credit cap policy:
    HeyGen meters credits per second of generated video. We enforce a hard ceiling
    of MAX_CREDITS_PER_VIDEO (default 17). The estimate uses a conservative
    upper-bound rate so we err on the side of NOT spending more than the user
    intended. Override per-run with --max-credits if you really want to.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import requests
import yaml
from dotenv import load_dotenv
from rich.console import Console

console = Console()

HEYGEN_BASE_URL = "https://api.heygen.com"
CREATE_VIDEO_URL = f"{HEYGEN_BASE_URL}/v3/videos"
GET_VIDEO_URL = f"{HEYGEN_BASE_URL}/v3/videos/{{video_id}}"

WORDS_PER_MINUTE = 150
CREDITS_PER_MINUTE_UPPER_BOUND = 2.0

POLL_INTERVAL_SECONDS = 10
POLL_MAX_MINUTES = 15


@dataclass
class VideoEntry:
    md_path: Path
    slug: str
    title: str
    script: str
    frontmatter: dict


def parse_markdown(md_path: Path) -> VideoEntry:
    """Pull frontmatter + voice script out of a memory/videos/*.md file."""
    text = md_path.read_text(encoding="utf-8")

    fm_match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not fm_match:
        raise ValueError(f"No YAML frontmatter found in {md_path}")
    frontmatter = yaml.safe_load(fm_match.group(1)) or {}

    title_match = re.search(r"^## 1\. Title\s*\n+\*\*(.+?)\*\*", text, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else frontmatter.get("slug", md_path.stem)

    script_match = re.search(
        r"## 2\. HeyGen Voice Script\s*\n+(.+?)(?=\n+_\(|\n+---|\n+## )",
        text,
        re.DOTALL,
    )
    if not script_match:
        raise ValueError(
            f"Could not find '## 2. HeyGen Voice Script' section in {md_path}"
        )
    script = " ".join(script_match.group(1).split()).strip()
    if not script:
        raise ValueError(f"Voice script section is empty in {md_path}")

    slug = frontmatter.get("slug") or md_path.stem
    return VideoEntry(md_path=md_path, slug=slug, title=title, script=script, frontmatter=frontmatter)


def estimate_credits(script: str) -> tuple[float, float]:
    """Return (estimated_minutes, estimated_credits_upper_bound)."""
    word_count = len(script.split())
    minutes = word_count / WORDS_PER_MINUTE
    credits = minutes * CREDITS_PER_MINUTE_UPPER_BOUND
    return minutes, credits


def enforce_credit_cap(script: str, max_credits: int) -> None:
    minutes, credits = estimate_credits(script)
    seconds = minutes * 60
    console.print(
        f"[cyan]Script:[/cyan] {len(script.split())} words "
        f"(~{seconds:.0f}s natural pace) "
        f"-> est. [bold]{credits:.2f}[/bold] credits "
        f"(cap = {max_credits})"
    )
    if credits > max_credits:
        console.print(
            f"[bold red]ABORT:[/bold red] estimated cost {credits:.2f} credits "
            f"exceeds cap of {max_credits}. "
            f"Trim the voice script (target <= {int(max_credits / CREDITS_PER_MINUTE_UPPER_BOUND * WORDS_PER_MINUTE)} words)."
        )
        sys.exit(2)


def create_video(api_key: str, entry: VideoEntry, avatar_id: str, voice_id: str,
                 aspect_ratio: str, resolution: str) -> str:
    payload = {
        "type": "avatar",
        "avatar_id": avatar_id,
        "voice_id": voice_id,
        "script": entry.script,
        "title": entry.title,
        "aspect_ratio": aspect_ratio,
        "resolution": resolution,
    }
    headers = {"X-Api-Key": api_key, "Content-Type": "application/json"}

    console.print(f"[cyan]POST[/cyan] {CREATE_VIDEO_URL}  aspect={aspect_ratio} res={resolution}")
    r = requests.post(CREATE_VIDEO_URL, json=payload, headers=headers, timeout=60)
    if r.status_code >= 400:
        console.print(f"[red]HTTP {r.status_code}:[/red] {r.text}")
        r.raise_for_status()

    data = r.json()
    video_id = data.get("video_id") or data.get("data", {}).get("video_id") or data.get("id")
    if not video_id:
        raise RuntimeError(f"No video_id returned. Full response: {data}")
    console.print(f"[green]Submitted.[/green] video_id = {video_id}")
    return video_id


def poll_until_ready(api_key: str, video_id: str) -> str:
    headers = {"X-Api-Key": api_key}
    deadline = time.time() + POLL_MAX_MINUTES * 60
    last_status = ""

    while time.time() < deadline:
        r = requests.get(GET_VIDEO_URL.format(video_id=video_id), headers=headers, timeout=30)
        r.raise_for_status()
        body = r.json()
        data = body.get("data", body)
        status = data.get("status", "unknown")
        if status != last_status:
            console.print(f"  status -> [yellow]{status}[/yellow]")
            last_status = status

        if status == "completed":
            url = data.get("video_url") or data.get("video_url_caption") or data.get("url")
            if not url:
                raise RuntimeError(f"Completed but no video_url. Body: {body}")
            return url
        if status == "failed":
            code = data.get("failure_code") or data.get("error", {}).get("code")
            msg = data.get("failure_message") or data.get("error", {}).get("message")
            raise RuntimeError(f"HeyGen render failed ({code}): {msg}")

        time.sleep(POLL_INTERVAL_SECONDS)

    raise TimeoutError(f"Video {video_id} did not finish within {POLL_MAX_MINUTES} minutes")


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    console.print(f"[cyan]Downloading[/cyan] -> {dest}")
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with dest.open("wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 16):
                if chunk:
                    f.write(chunk)
    console.print(f"[green]Saved[/green] {dest} ({dest.stat().st_size / 1_000_000:.1f} MB)")


def update_frontmatter(md_path: Path, video_path: Path, video_id: str) -> None:
    text = md_path.read_text(encoding="utf-8")
    fm_match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not fm_match:
        return
    fm = yaml.safe_load(fm_match.group(1)) or {}
    fm["status"] = "recorded"
    fm["local_video_path"] = str(video_path)
    fm["heygen_video_id"] = video_id
    new_fm = yaml.safe_dump(fm, sort_keys=False).strip()
    new_text = f"---\n{new_fm}\n---\n" + text[fm_match.end():]
    md_path.write_text(new_text, encoding="utf-8")
    console.print(f"[green]Updated frontmatter[/green] -> status: recorded")


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Generate a HeyGen short video from a memory markdown file.")
    parser.add_argument("markdown_file", type=Path, help="Path to memory/videos/*.md")
    parser.add_argument("--max-credits", type=int,
                        default=int(os.getenv("MAX_CREDITS_PER_VIDEO", "17")),
                        help="Hard cap on estimated credits (default 17).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Validate script + estimate credits but do NOT submit to HeyGen.")
    args = parser.parse_args()

    api_key = os.getenv("HEYGEN_API_KEY")
    avatar_id = os.getenv("HEYGEN_AVATAR_ID")
    voice_id = os.getenv("HEYGEN_VOICE_ID")
    aspect_ratio = os.getenv("HEYGEN_ASPECT_RATIO", "9:16")
    resolution = os.getenv("HEYGEN_RESOLUTION", "1080p")

    missing = [k for k, v in [("HEYGEN_API_KEY", api_key),
                              ("HEYGEN_AVATAR_ID", avatar_id),
                              ("HEYGEN_VOICE_ID", voice_id)] if not v]
    if missing:
        console.print(f"[red]Missing env vars:[/red] {', '.join(missing)} (set them in .env)")
        sys.exit(1)

    if not args.markdown_file.exists():
        console.print(f"[red]File not found:[/red] {args.markdown_file}")
        sys.exit(1)

    entry = parse_markdown(args.markdown_file)
    console.print(f"[bold]{entry.title}[/bold]  ({entry.slug})")

    enforce_credit_cap(entry.script, args.max_credits)

    if args.dry_run:
        console.print("[yellow]Dry run \u2014 not submitting.[/yellow]")
        return

    video_id = create_video(api_key, entry, avatar_id, voice_id, aspect_ratio, resolution)
    video_url = poll_until_ready(api_key, video_id)

    out_path = Path("output") / f"{entry.slug}.mp4"
    download(video_url, out_path)
    update_frontmatter(args.markdown_file, out_path, video_id)

    console.print("[bold green]Done.[/bold green]")


if __name__ == "__main__":
    main()
