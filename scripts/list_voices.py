"""List HeyGen voices. Useful when you need to find a voice_id.

Usage:
    python scripts/list_voices.py
    python scripts/list_voices.py --language English --gender male
    python scripts/list_voices.py --type private
"""

from __future__ import annotations

import argparse
import os
import sys

import requests
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

console = Console()
URL = "https://api.heygen.com/v3/voices"


def main() -> None:
    load_dotenv()
    api_key = os.getenv("HEYGEN_API_KEY")
    if not api_key:
        console.print("[red]Missing HEYGEN_API_KEY in .env[/red]")
        sys.exit(1)

    parser = argparse.ArgumentParser()
    parser.add_argument("--type", choices=["public", "private"], default=None)
    parser.add_argument("--language", default=None)
    parser.add_argument("--gender", choices=["male", "female"], default=None)
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()

    params: dict[str, object] = {"limit": args.limit}
    for k in ("type", "language", "gender"):
        v = getattr(args, k)
        if v:
            params[k] = v

    r = requests.get(URL, headers={"X-Api-Key": api_key}, params=params, timeout=30)
    r.raise_for_status()
    body = r.json()
    voices = body.get("data", {}).get("voices") or body.get("voices") or []

    table = Table(title=f"HeyGen Voices ({len(voices)})")
    table.add_column("voice_id", style="cyan", no_wrap=True)
    table.add_column("Name")
    table.add_column("Lang")
    table.add_column("Gender")
    table.add_column("Type")
    for v in voices:
        table.add_row(
            str(v.get("voice_id", "")),
            str(v.get("name", "")),
            str(v.get("language", "")),
            str(v.get("gender", "")),
            str(v.get("type", "")),
        )
    console.print(table)


if __name__ == "__main__":
    main()
