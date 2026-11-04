#!/usr/bin/env python3
"""tooop news - simple menu for people who are not programmers.

The console text is English/ASCII on purpose: Windows consoles mangle Persian
(bidi) text. Persian instructions live in READ-ME-FIRST.txt (opens fine in Notepad).
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

if os.name == "nt":  # pragma: no cover - only on Windows
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

NEEDED = ("PIL", "arabic_reshaper", "bidi", "imageio_ffmpeg", "feedparser")
YAML_MODULES = ("yaml", "ruamel.yaml")


def clear() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def line() -> None:
    print("-" * 54)


def header() -> None:
    clear()
    line()
    print("        tooop news   -   video factory")
    line()
    print()


def ask(prompt: str, default: str = "") -> str:
    value = input(prompt).strip()
    return value or default


def open_folder(path: Path) -> None:
    try:
        if os.name == "nt":
            os.startfile(str(path))            # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.run(["open", str(path)], check=False)
        else:
            subprocess.run(["xdg-open", str(path)], check=False, capture_output=True)
    except Exception:
        pass


def _has(module: str) -> bool:
    """True if the module can be imported.

    `find_spec("pkg.sub")` raises ModuleNotFoundError when `pkg` is missing, so a
    plain `find_spec(...) is not None` would crash instead of returning False.
    """
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ModuleNotFoundError, AttributeError, ValueError):
        return False


def missing_packages() -> list[str]:
    missing = [m for m in NEEDED if not _has(m)]
    if not any(_has(m) for m in YAML_MODULES):
        missing.append("ruamel.yaml")
    return missing


def install_requirements() -> bool:
    print("First run: installing the libraries. This takes 1-3 minutes.")
    print("Internet is needed. Please wait...\n")
    attempts = [
        [sys.executable, "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")],
        [sys.executable, "-m", "pip", "install", "--user", "-r", str(ROOT / "requirements.txt")],
    ]
    for cmd in attempts:
        if subprocess.run(cmd).returncode == 0:
            return True
    print("\n[!] Installing the libraries failed.")
    print("    Most common reason: your Python version is too new for ready-made")
    print("    packages. Fix: install Python 3.12 from https://www.python.org/downloads/")
    print("    (during setup tick: Add python.exe to PATH), then run this again.")
    print("    If it still fails, send a screenshot of this window.")
    return False


def ensure_ready() -> bool:
    if sys.version_info < (3, 10):
        print("[!] Python is too old. Install Python 3.12 from python.org")
        return False
    if not missing_packages():
        return True
    if not install_requirements():
        return False
    if missing_packages():
        print("[!] Some libraries are still missing. Please run it once more.")
        return False
    print("\n[ok] Libraries installed.\n")
    return True


def projects() -> list[str]:
    folder = ROOT / "projects"
    if not folder.exists():
        return []
    return sorted(
        [p.name for p in folder.iterdir() if (p / "project.yaml").exists()], reverse=True
    )


def choose_project() -> str | None:
    items = projects()
    if not items:
        print("No episode found.")
        return None
    print("Which episode?")
    for i, name in enumerate(items, start=1):
        print(f"  {i}) {name}")
    choice = ask("Number (default 1): ", "1")
    if not choice.isdigit() or not (1 <= int(choice) <= len(items)):
        print("Invalid number - using the latest episode.")
        return items[0]
    return items[int(choice) - 1]


def run_telton(argv: list[str]) -> bool:
    from telton.cli import main as telton_main

    try:
        code = telton_main(argv)
    except Exception as exc:
        print(f"\n[!] Error: {exc}")
        print("    If it happens again, send a screenshot of this window.")
        return False
    if code not in (0, None):
        print("\n[!] This step did not finish.")
        return False
    return True


def build_video(slug: str, vertical: bool) -> None:
    project_dir = ROOT / "projects" / slug
    out_dir = project_dir / "out"
    label = "VERTICAL (Instagram)" if vertical else "HORIZONTAL (YouTube)"
    print(f"\n== Building {label} video from episode: {slug}")
    print("   This takes 4-6 minutes. Please keep this window open.\n")

    if not run_telton(["build", "-p", slug, "-d", "300"]):
        return
    print("\n== Fetching match clips (Telegram) ...")
    run_telton(["broll", "-p", slug, "--channel", "varzesh3", "--limit", "150",
                "--max-clips", "6", "--min-score", "4"])
    print("\n== Fetching copyright-free footage for the rest ...")
    run_telton(["stock", "-p", slug, "--limit", "3"])
    run_telton(["sync", "-p", slug])
    print("\n== Making the voice-over...")
    if not run_telton(["voice", "-p", slug, "-d", "300"]):
        return
    print("\n== Rendering the video (longest step)...")
    args = ["render", "-p", slug] + (["--vertical"] if vertical else [])
    if not run_telton(args):
        return
    run_telton(["review", "-p", slug])

    print("\n[ok] Video is ready!")
    print(f"     Folder: {out_dir}")
    open_folder(out_dir)


def build_short(slug: str) -> None:
    print("\n== Making a 50-second vertical short (YouTube Shorts / Reels)")
    print("   It uses the 3 strongest stories of the episode.\n")
    if run_telton(["short", "-p", slug, "-d", "50", "--count", "3"]):
        print("\n[ok] Short is ready: out/short-1080x1920.mp4")
        open_folder(ROOT / "projects" / slug / "out")


def refresh_episode(slug: str) -> None:
    """Re-check the news, re-download clips and rebuild - without touching the script."""
    print("\n== Refresh: new headlines + new clips + rebuild")
    run_telton(["collect", "-p", slug])
    print("\n   Raw headlines saved. Re-downloading footage...")
    run_telton(["broll", "-p", slug, "--channel", "varzesh3", "--limit", "150",
                "--max-clips", "6", "--min-score", "4"])
    run_telton(["stock", "-p", slug, "--limit", "3"])
    run_telton(["sync", "-p", slug])
    print("\n== Re-rendering with the new footage...")
    build_video(slug, vertical=False)


def update_news(slug: str) -> None:
    """Show what is new right now (so you can add it to stories.json)."""
    print("\n== Update: what is new in the last hours")
    run_telton(["collect", "-p", slug])
    project_dir = ROOT / "projects" / slug
    digest = project_dir / "build" / "candidates.md"
    print(f"\n   Open this file and copy the headlines you want:\n   {digest}")
    open_folder(digest.parent)


def upload_process(slug: str) -> None:
    print("\n== Upload to YouTube")
    print("   1) Only me can see it (best for the first time)")
    print("   2) Public for everyone")
    print("   3) Scheduled")
    choice = ask("Choose (default 1): ", "1")
    privacy = {"1": "unlisted", "2": "public", "3": "private"}.get(choice, "unlisted")
    name = ask("Your name for the approval record (default: tooop news): ", "tooop news")

    if not run_telton(["publish", "-p", slug, "--by", name]):
        return
    args = ["youtube", "upload", "-p", slug, "--privacy", privacy]
    if privacy == "private":
        when = ask("Publish time, e.g. 2026-11-03T18:30:00Z (empty = later by hand): ")
        if when:
            args += ["--publish-at", when]
    run_telton(args)


def youtube_connect() -> None:
    header()
    print("== Connect to YouTube (only once)")
    print()
    secret = ROOT / ".secrets" / "client_secret.json"
    if not secret.exists():
        print("You need one free 'key' from Google. Step by step:")
        print()
        print("  1. open  https://console.cloud.google.com")
        print("  2. create a new project (any name)")
        print("  3. search  YouTube Data API v3  and click Enable")
        print("  4. open  OAuth consent screen  ->  External")
        print("     add your own email as a Test user, and click Publish app")
        print("  5. Credentials -> Create credentials -> OAuth client ID")
        print("     type: Desktop app  ->  Download JSON")
        print("  6. move that JSON file here, with this exact name:")
        print(f"     {secret}")
        print()
        print("  Full guide (Persian):  docs/youtube.md")
        print()
        print("  (This folder will now open for you.)")
        open_folder(ROOT / ".secrets")
        return
    print("A browser will open. Sign in with the tooop news account and click Allow.")
    run_telton(["youtube", "auth"])
    print("\nChecking the connection...")
    run_telton(["youtube", "status"])


def show_status() -> None:
    items = projects()
    if not items:
        print("No episode yet.")
        return
    slug = items[0]
    project_dir = ROOT / "projects" / slug
    print(f"Latest episode: {slug}\n")
    for name, label in (
        ("video.mp4", "Horizontal video (YouTube)"),
        ("video-1080x1920.mp4", "Vertical video (Instagram)"),
        ("thumbnail.jpg", "Cover image"),
        ("review.html", "Review page"),
    ):
        path = project_dir / "out" / name
        size = f"{path.stat().st_size / 1e6:.1f} MB" if path.exists() else "--"
        print(f"  {'[x]' if path.exists() else '[ ]'} {label}: {size}")
    print()
    run_telton(["youtube", "status"])
    open_folder(project_dir / "out")


def main() -> int:
    if not ensure_ready():
        input("\nPress Enter to close...")
        return 1
    slug = projects()[0] if projects() else ""
    while True:
        header()
        print("What do you want to do?\n")
        print("  1) Make video for YouTube   (horizontal)")
        print("  2) Make video for Instagram (vertical)")
        print("  3) Upload to YouTube")
        print("  4) Connect to YouTube (first time)")
        print("  5) Show files and status")
        print("  6) Make a 50s Short / Reel")
        print("  7) Refresh (new clips + rebuild now)")
        print("  8) Update (what is new right now)")
        print("  9) Make today's pack (long + 2 shorts)")
        print("  0) Exit")
        print()
        choice = ask("Type a number: ")

        if choice == "0":
            print("\nBye!")
            return 0
        if choice == "4":
            youtube_connect()
        elif choice == "5":
            show_status()
        elif choice in {"1", "2", "3", "6", "7", "8", "9"}:
            slug = choose_project() or slug
            if not slug:
                input("\nPress Enter...")
                continue
            if choice == "1":
                build_video(slug, vertical=False)
            elif choice == "2":
                build_video(slug, vertical=True)
            elif choice == "3":
                upload_process(slug)
            elif choice == "6":
                build_short(slug)
            elif choice == "7":
                refresh_episode(slug)
            elif choice == "8":
                update_news(slug)
            else:
                print("\n== Building today's pack: long video + 2 shorts (10-14 min)")
                run_telton(["pack", "-p", slug, "-d", "300"])
        else:
            print("Please type one of the numbers above.")
        print()
        input("Press Enter to continue...")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nCancelled.")
        raise SystemExit(1)
    except SystemExit:
        raise
    except Exception as exc:                     # never show a raw traceback
        import traceback

        print("\n[!] Unexpected error.")
        print(f"    {type(exc).__name__}: {exc}")
        print()
        print("    Send a screenshot of this window. Technical details:")
        traceback.print_exc()
        try:
            input("\nPress Enter to close...")
        except Exception:
            pass
        raise SystemExit(1)
