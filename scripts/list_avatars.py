"""List your HeyGen avatar looks. Useful when you need to find an avatar_id.

Usage:
    python scripts/list_avatars.py                # all (public + private)
    python scripts/list_avatars.py --private      # only your own
    python scripts/list_avatars.py --limit 50
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
URL = "https://api.heygen.com/v3/avatars/looks"


def main() -> None:
    load_dotenv()
    api_key = os.getenv("HEYGEN_API_KEY")
    if not api_key:
        console.print("[red]Missing HEYGEN_API_KEY in .env[/red]")
        sys.exit(1)

    parser = argparse.ArgumentParser()
    parser.add_argument("--type", choices=["public", "private"], default=None)
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()

    params: dict[str, object] = {"limit": args.limit}
    if args.type:
        params["type"] = args.type

    r = requests.get(URL, headers={"X-Api-Key": api_key}, params=params, timeout=30)
    r.raise_for_status()
    body = r.json()
    looks = body.get("data", {}).get("looks") or body.get("looks") or []

    table = Table(title=f"HeyGen Avatar Looks ({len(looks)})")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Name")
    table.add_column("Type")
    table.add_column("Status")
    for look in looks:
        table.add_row(
            str(look.get("id", "")),
            str(look.get("name", "")),
            str(look.get("avatar_type", "")),
            str(look.get("status", "")),
        )
    console.print(table)


if __name__ == "__main__":
    main()
