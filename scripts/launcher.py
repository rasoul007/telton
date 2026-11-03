#!/usr/bin/env python3
"""منوی ساده‌ی tooop news — برای کسانی که برنامه‌نویسی نمی‌دانند.

اجرا: روی START-WINDOWS.bat (ویندوز) یا START-MAC.command (مک) دابل‌کلیک کن.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

NEEDED = ("PIL", "arabic_reshaper", "bidi", "imageio_ffmpeg", "yaml", "feedparser")


def clear() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def line() -> None:
    print("─" * 52)


def header() -> None:
    clear()
    line()
    print("        📺  tooop news  —  کارخانه‌ی ویدیو")
    line()
    print()


def ask(prompt: str, default: str = "") -> str:
    value = input(prompt).strip()
    return value or default


def open_folder(path: Path) -> None:
    """پوشه را در فایل‌اکسپلورر باز می‌کند تا کاربر فایل را ببیند."""
    try:
        if os.name == "nt":
            os.startfile(str(path))            # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.run(["open", str(path)], check=False)
        else:
            subprocess.run(["xdg-open", str(path)], check=False)
    except Exception:
        pass


def missing_packages() -> list[str]:
    missing = []
    for module in NEEDED:
        try:
            __import__(module)
        except ImportError:
            missing.append(module)
    return missing


def install_requirements() -> bool:
    print("📦 اولین بار است که اجرا می‌شود؛ کتابخانه‌ها نصب می‌شوند (۱ تا ۳ دقیقه).")
    print("   اینترنت لازم است و فقط همین یک‌بار انجام می‌شود.\n")
    attempts = [
        [sys.executable, "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")],
        [sys.executable, "-m", "pip", "install", "--user", "-r", str(ROOT / "requirements.txt")],
    ]
    for cmd in attempts:
        result = subprocess.run(cmd)
        if result.returncode == 0:
            return True
    print("\n❌ نصب کتابخانه‌ها موفق نشد.")
    print("   این متن را برای پشتیبانی بفرست: pip install -r requirements.txt")
    return False


def ensure_ready() -> bool:
    if sys.version_info < (3, 10):
        print("❌ نسخه‌ی پایتون قدیمی است. از python.org نسخه‌ی 3.11 یا بالاتر را نصب کن.")
        return False
    if not missing_packages():
        return True
    if not install_requirements():
        return False
    if missing_packages():
        print("❌ بعضی کتابخانه‌ها نصب نشدند. یک‌بار دیگر تلاش کن.")
        return False
    print("\n✅ نصب کامل شد.\n")
    return True


def projects() -> list[str]:
    folder = ROOT / "projects"
    if not folder.exists():
        return []
    return sorted(
        [p.name for p in folder.iterdir() if (p / "project.yaml").exists()],
        reverse=True,
    )


def choose_project() -> str | None:
    items = projects()
    if not items:
        print("❌ هیچ قسمتی ساخته نشده است.")
        return None
    print("کدام قسمت؟")
    for i, name in enumerate(items, start=1):
        print(f"  {i}) {name}")
    choice = ask(f"شماره (پیش‌فرض ۱): ", "1")
    if not choice.isdigit() or not (1 <= int(choice) <= len(items)):
        print("شماره نامعتبر بود؛ آخرین قسمت انتخاب شد.")
        return items[0]
    return items[int(choice) - 1]


def run_telton(argv: list[str]) -> bool:
    """اجرای مرحله‌های برنامه با پیام‌های ساده."""
    from telton.cli import main as telton_main

    try:
        code = telton_main(argv)
    except Exception as exc:                     # خطای پیش‌بینی‌نشده
        print(f"\n❌ خطا: {exc}")
        print("   اگر تکرار شد، همین متن را برای پشتیبانی بفرست.")
        return False
    if code not in (0, None):
        print("\n❌ این مرحله کامل نشد.")
        return False
    return True


def build_video(slug: str, vertical: bool) -> None:
    project_dir = ROOT / "projects" / slug
    out_dir = project_dir / "out"
    label = "عمودی (اینستاگرام)" if vertical else "افقی (یوتیوب)"
    print(f"\n🎬 ساخت ویدیوی {label} از قسمت «{slug}»")
    print("   ⏱ حدود ۴ تا ۶ دقیقه طول می‌کشد. پنجره را نبند.\n")

    tts = os.environ.get("TELTON_OFFLINE", "") != "1"
    if not run_telton(["build", "-p", slug, "-d", "300"]):
        return
    print("\n🎙 ساخت صدا…")
    voice_args = ["voice", "-p", slug, "-d", "300", "--rate", "+10%"]
    if not tts:
        voice_args.append("--offline")
    if not run_telton(voice_args):
        return
    print("\n🎥 ساخت تصویر… (این مرحله طولانی‌تر است)")
    render_args = ["render", "-p", slug]
    if vertical:
        render_args.append("--vertical")
    if not run_telton(render_args):
        return
    run_telton(["review", "-p", slug])

    print("\n✅ ویدیو آماده شد!")
    print(f"   پوشه: {out_dir}")
    open_folder(out_dir)


def upload_process(privacy_choice: str, slug: str) -> str:
    print("\n📤 آپلود به یوتیوب")
    print("   1) فقط خودم ببینم (پیشنهاد برای بار اول)")
    print("   2) عمومی برای همه")
    print("   3) زمان‌بندی‌شده")
    choice = ask("انتخاب (پیش‌فرض ۱): ", "1")
    privacy = {"1": "unlisted", "2": "public", "3": "private"}.get(choice, "unlisted")
    name = ask("نامت برای ثبت تأیید (پیش‌فرض tooop news): ", "tooop news")

    if not run_telton(["publish", "-p", slug, "--by", name]):
        return privacy
    args = ["youtube", "upload", "-p", slug, "--privacy", privacy]
    if privacy == "private":
        when = ask("زمان انتشار به شکل 2026-11-03T18:30:00Z (خالی = بعداً دستی): ")
        if when:
            args += ["--publish-at", when]
    run_telton(args)
    return privacy


def youtube_connect() -> None:
    header()
    print("🔑 اتصال به یوتیوب (فقط بار اول)")
    print()
    secret = ROOT / ".secrets" / "client_secret.json"
    if not secret.exists():
        print("برای این کار یک «کلید» از گوگل لازم است. خیلی ساده:")
        print()
        print("  1. برو به  console.cloud.google.com")
        print("  2. یک پروژه‌ی جدید بساز (اسمش هرچه باشد)")
        print("  3. بخش  YouTube Data API v3  را پیدا کن و Enable بزن")
        print("  4. بخش  OAuth consent screen  →  External  →  ایمیل خودت را Test user کن")
        print("  5. بخش  Credentials  →  Create credentials  →  OAuth client ID")
        print("     نوع: Desktop app  →  Download JSON")
        print("  6. فایل دانلودشده را با همین اسم اینجا بگذار:")
        print(f"     {secret}")
        print()
        print("  راهنمای تصویری کامل:  docs/youtube.md")
        print()
        open_folder(ROOT / ".secrets")
        return
    print("مرورگر باز می‌شود؛ با اکانت کانال tooop news وارد شو و «اجازه دادن» را بزن.")
    run_telton(["youtube", "auth"])
    print()
    print("بررسی وضعیت…")
    run_telton(["youtube", "status"])


def show_status() -> None:
    items = projects()
    if not items:
        print("هنوز هیچ قسمتی ساخته نشده.")
        return
    slug = items[0]
    project_dir = ROOT / "projects" / slug
    print(f"آخرین قسمت: {slug}")
    for name, label in (
        ("video.mp4", "ویدیوی افقی (یوتیوب)"),
        ("video-1080x1920.mp4", "ویدیوی عمودی (اینستاگرام)"),
        ("thumbnail.jpg", "کاور"),
        ("review.html", "صفحه‌ی بازبینی"),
    ):
        path = project_dir / "out" / name
        size = f"{path.stat().st_size / 1e6:.1f} مگابایت" if path.exists() else "—"
        print(f"  {'✅' if path.exists() else '⬜'} {label}: {size}")
    print()
    run_telton(["youtube", "status"])
    open_folder(project_dir / "out")


def main() -> int:
    if not ensure_ready():
        input("\nبرای بستن Enter بزن…")
        return 1
    slug = projects()[0] if projects() else ""
    while True:
        header()
        print("چه کاری انجام بدهم؟\n")
        print("  1) 🎬 ساخت ویدیوی افقی برای یوتیوب")
        print("  2) 📱 ساخت ویدیوی عمودی برای اینستاگرام")
        print("  3) 📤 آپلود به یوتیوب")
        print("  4) 🔑 اتصال به یوتیوب (اولین بار)")
        print("  5) 📂 دیدن فایل‌ها و وضعیت")
        print("  0) خروج")
        print()
        choice = ask("شماره را بنویس: ")

        if choice == "0":
            print("\nخدانگهدار 👋")
            return 0
        if choice == "4":
            youtube_connect()
        elif choice == "5":
            show_status()
        elif choice in {"1", "2", "3"}:
            slug = choose_project() or slug
            if not slug:
                input("\nEnter…")
                continue
            if choice == "1":
                build_video(slug, vertical=False)
            elif choice == "2":
                build_video(slug, vertical=True)
            else:
                upload_process("", slug)
        else:
            print("شماره‌ی درست را وارد کن.")
        print()
        input("برای ادامه Enter بزن…")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nلغو شد.")
        raise SystemExit(1)
