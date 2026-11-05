#!/usr/bin/env python3
"""Download the free offline Persian voice used by the `piper` engine.

    python scripts/fetch_piper_model.py

~64 MB, once. The model is not stored in git (too big for a repo).
"""

from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main/fa/fa_IR/amir/medium/"
FILES = ("fa_IR-amir-medium.onnx", "fa_IR-amir-medium.onnx.json")
TARGET = Path(__file__).resolve().parent.parent / "assets" / "tts"


def main() -> int:
    TARGET.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        dest = TARGET / name
        if dest.exists() and dest.stat().st_size > 1000:
            print(f"already there: {dest}")
            continue
        print(f"downloading {name} ...")
        try:
            request = urllib.request.Request(BASE + name, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(request, timeout=180) as response:
                dest.write_bytes(response.read())
        except Exception as exc:
            print(f"[!] failed: {exc}")
            return 1
        print(f"  saved: {dest} ({dest.stat().st_size / 1e6:.1f} MB)")
    print("\nready. now run:  telton voice-test -p <slug>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
