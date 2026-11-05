"""`telton` command line — one stage per command, plus `run` for the whole chain."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .config import Project
from .util import ensure_dir, read_json, seconds_to_clock


def _project(args: argparse.Namespace) -> Project:
    return Project(args.project).ensure()


def cmd_collect(args: argparse.Namespace) -> int:
    from .collect import collect

    project = _project(args)
    payload = collect(project)
    print(f"collected {payload['count']} candidates → {project.candidates_path}")
    for feed in payload["feeds"]:
        print(f"  - {feed['id']}: {feed['status']}")
    for candidate in payload["candidates"][: args.show]:
        print(f"  [{candidate['bucket']}] {candidate['title'][:90]} ({candidate['source']})")
    if payload["count"]:
        print("\nnext: با این تیترها stories.json را در فارسی بنویس (verified=true) و `telton build` بزن.")
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    from .rundown import build

    project = _project(args)
    rundown = build(project, target=args.duration, title=args.title)
    print(f"rundown: {len(rundown.segments)} segments · {seconds_to_clock(rundown.end)}")
    print(f"  {project.build / 'script.md'}")
    print(f"  {project.build / 'subtitles.srt'}")
    print(f"  {project.build / 'caption.txt'}")
    return 0


def cmd_voice(args: argparse.Namespace) -> int:
    from .voice import voice_stage

    project = _project(args)
    rundown, audio = voice_stage(
        project,
        voice=args.voice,
        offline=args.offline,
        target=args.duration,
        rate=getattr(args, "rate", None),
        fit=not getattr(args, "no_fit", False),
    )
    print(f"voice-over ready: {seconds_to_clock(rundown.end)} · {audio}")
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    from .models import Rundown
    from .render import export_thumbnail, render_video

    project = _project(args)
    data = read_json(project.build / "rundown.json")
    if not data:
        print("rundown.json missing — run `telton build`", file=sys.stderr)
        return 2
    rundown = Rundown.from_dict(data)
    audio = project.build / "audio.wav"
    if args.vertical:
        args.width, args.height = 1080, 1920
    width = args.width or project.style.width
    height = args.height or project.style.height
    suffix = "" if (width, height) == (project.style.width, project.style.height) else f"-{width}x{height}"
    out_path = Path(args.output) if args.output else project.out / f"video{suffix}.mp4"
    video = render_video(
        project,
        rundown,
        audio if audio.exists() else None,
        out_path=out_path,
        width=width,
        height=height,
        fps=args.fps,
        max_seconds=args.max_seconds,
    )
    thumb = export_thumbnail(project, rundown, path=project.out / f"thumbnail{suffix}.jpg")
    try:                                    # a real hook thumbnail beats a plain frame
        from .thumbnail import build_thumbnails

        thumb = build_thumbnails(project, rundown)[0]
    except Exception as exc:
        print(f"  (thumbnail fallback: {exc})")
    print(f"video: {video} ({video.stat().st_size / 1e6:.1f} MB · {width}x{height})")
    print(f"thumbnail: {thumb}")
    return 0


def cmd_sync(args: argparse.Namespace) -> int:
    from .rundown import sync_stories

    project = _project(args)
    rundown = sync_stories(project)
    clips = [s.story.broll for s in rundown.segments if s.story and s.story.broll]
    print(f"synced {len(rundown.segments)} segments · {len(clips)} با فوتیج")
    for clip in clips:
        print(f"  🎬 {clip}")
    return 0


def cmd_thumb(args: argparse.Namespace) -> int:
    from .models import Rundown
    from .thumbnail import build_thumbnails

    project = _project(args)
    data = read_json(project.build / "rundown.json")
    if not data:
        print("rundown.json missing — run `telton build`", file=sys.stderr)
        return 2
    rundown = Rundown.from_dict(data)
    hooks = [args.hook] if args.hook else None
    for path in build_thumbnails(project, rundown, hooks=hooks):
        print(f"thumbnail: {path}")
    return 0


def cmd_stock(args: argparse.Namespace) -> int:
    from .stock import fill_missing, search_commons

    project = _project(args)
    if args.query:
        items = search_commons(args.query, kind=args.kind, limit=args.limit)
        print(f"{len(items)} نتیجه (فقط مجوز آزاد قابل استفاده است):")
        for item in items:
            mark = "✅" if item.free else "⛔"
            print(f"  {mark} [{item.license}] {item.title[:60]}")
            print(f"      {item.url}")
        return 0
    for entry in fill_missing(project, kind=args.kind, limit=args.limit, dry_run=args.dry_run):
        print(f"  {entry['status']:>15}  {entry['story']:<24} "
              f"{entry.get('query', '')} {entry.get('license', '')}")
    print("\nبعدی: telton sync -p %s && telton render -p %s" % (project.slug, project.slug))
    return 0


def cmd_short(args: argparse.Namespace) -> int:
    from .short import make_short

    project = _project(args)
    print(f"ساخت شورت {args.duration:.0f} ثانیه‌ای (۹:۱۶)…")
    result = make_short(
        project,
        target=args.duration,
        count=args.count,
        offline=args.offline,
        voice=args.voice,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_pack(args: argparse.Namespace) -> int:
    from .pack import make_pack

    project = _project(args)
    print("ساخت بستهٔ روزانه (بلند + دو شورت)…")
    plan = make_pack(project, target=args.duration, fast=args.fast)
    print("\nبرنامهٔ انتشار:")
    for item in plan:
        print(f"  ⏰ {item['slot']}  {item['type']:<12} {item['file']}")
    return 0


def cmd_voice_test(args: argparse.Namespace) -> int:
    """Render the same hard sentence with every available voice so you can pick."""
    from .text_fa import spoken
    from .voice import available_engines, synthesize

    project = _project(args)
    out_dir = ensure_dir(project.out / "voice-test")
    sentence = args.text or (
        "پرسپولیس در هفته یازدهم لیگ برتر، در خانه نساجی یک بر صفر برد و "
        "با بیست و سه امتیاز به صدر جدول برگشت. آرسنال هم در آنفیلد، "
        "لیورپول را شکست داد؛ آنتونلی در فرمول یک رکورد فتح را شکست."
    )
    tts_text = spoken(sentence)
    print("متن گوینده (با اعراب و تلفظ اصلاح‌شده):\n  " + tts_text + "\n")

    engines = available_engines()
    jobs: list[tuple[str, str, str]] = []
    for name, state in engines.items():
        if state != "ok":
            print(f"  - {name}: {state}")
            continue
        if name == "edge":
            jobs += [("edge-farid", "edge", "fa-IR-FaridNeural"),
                     ("edge-dilara", "edge", "fa-IR-DilaraNeural")]
        elif name == "google":
            jobs.append(("google", "google", ""))
        else:
            jobs.append((name, name, ""))

    made = []
    for label, engine, voice in jobs:
        target = out_dir / f"{label}.mp3"
        try:
            used = synthesize(tts_text, target, engine=engine, voice=voice or None,
                              rate=args.rate, pitch=args.pitch)
        except Exception as exc:
            print(f"  ✗ {label}: {exc}")
            continue
        size = target.stat().st_size / 1024
        print(f"  ✓ {label:<14} ({used}) {size:.0f} KB  → {target}")
        made.append((label, target))

    if not made:
        print("\nهیچ صدایی ساخته نشد.")
        return 2

    # one file that plays every voice back-to-back, so you can compare in one go
    compare = out_dir / "compare.mp3"
    try:
        from .util import ffmpeg_exe, run

        clips = [path for _, path in made]
        cmd = [ffmpeg_exe(), "-y", "-loglevel", "error"]
        for clip in clips:
            cmd += ["-i", str(clip)]
        gaps = len(clips) - 1
        for _ in range(gaps):
            cmd += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono:d=0.6"]

        parts = [f"[{i}:a]aresample=44100[a{i}]" for i in range(len(clips))]
        parts += [f"[{len(clips) + i}:a]aresample=44100[s{i}]" for i in range(gaps)]
        order: list[str] = []
        for i in range(len(clips)):
            order.append(f"[a{i}]")
            if i < gaps:
                order.append(f"[s{i}]")
        parts.append("".join(order) + f"concat=n={len(order)}:v=0:a=1[out]")
        cmd += ["-filter_complex", ";".join(parts), "-map", "[out]", str(compare)]
        run(cmd)
        print(f"\nفایل مقایسه (همه صداها پشت سر هم): {compare}")
    except Exception as exc:
        print(f"(فایل مقایسه ساخته نشد: {exc})")

    print("\nهمه را گوش کن و بگو کدام بهتر است؛ من همان را پیش‌فرض می‌کنم.")
    print("برای کیفیت حرفه‌ای: کلید OPENAI_API_KEY یا ELEVENLABS_API_KEY بده "
          "(متغیر محیطی) و دوباره این دستور را بزن.")
    open_folder(out_dir) if args.open else None
    return 0


def cmd_review(args: argparse.Namespace) -> int:
    from .models import Rundown
    from .review import approval_status, build_review, unverified_stories

    project = _project(args)
    data = read_json(project.build / "rundown.json")
    if not data:
        print("rundown.json missing — run `telton build`", file=sys.stderr)
        return 2
    rundown = Rundown.from_dict(data)
    page = build_review(project, rundown)
    status = approval_status(project)
    print(f"review page: {page}")
    print(f"approved: {status['approved']}")
    if status["reasons"]:
        print("  " + " · ".join(status["reasons"]))
    unverified = unverified_stories(rundown)
    if unverified:
        print(f"⚠️  unverified stories: {', '.join(unverified)}")
    return 0


def cmd_approve(args: argparse.Namespace) -> int:
    from .review import approve

    project = _project(args)
    record = approve(project, by=args.by, platforms=args.platforms, force=args.force)
    print("approved ✅")
    print(json.dumps({k: record[k] for k in ("by", "at", "sha256", "duration")}, ensure_ascii=False, indent=2))
    return 0


def cmd_broll(args: argparse.Namespace) -> int:
    from .telegram import auto_broll, fetch_posts

    project = _project(args)
    if args.list:
        posts = fetch_posts(args.channel, limit=args.limit)
        print(f"{len(posts)} پیام دارای مدیا از @{args.channel}:")
        for post in posts:
            kind = "🎬" if post.videos else "🖼"
            print(f"  {kind} {post.url}  {post.clean_text[:70]}")
        return 0
    report = auto_broll(
        project,
        channel=args.channel,
        limit=args.limit,
        min_score=args.min_score,
        dry_run=args.dry_run,
        max_clips=args.max_clips,
    )
    for item in report:
        line = f"  {item['status']:>18}  {item['story']:<24} {item.get('post', '')}"
        print(line)
        if item.get("caption"):
            print(f"  {'':>18}  ↳ {item['caption']}")
    done = sum(1 for item in report if item["status"].startswith("downloaded"))
    if done:
        print(f"\n{done} کلیپ به broll/ دانلود شد و در stories.json ثبت شد.")
    print("بعدی: telton render -p %s" % project.slug)
    return 0


def cmd_publish(args: argparse.Namespace) -> int:
    from .models import Rundown
    from .publish import NotApproved, make_kit, upload
    from .review import approve

    project = _project(args)
    data = read_json(project.build / "rundown.json")
    if not data:
        print("rundown.json missing — run `telton build`", file=sys.stderr)
        return 2
    rundown = Rundown.from_dict(data)
    if args.by:
        # explicit consent: recording the approval and publishing in one command
        try:
            approve(project, by=args.by, force=args.force)
        except PermissionError as exc:
            print(f"✋ {exc}", file=sys.stderr)
            return 3
    try:
        if args.platform:
            print(json.dumps(upload(project, args.platform, dry_run=not args.live), ensure_ascii=False, indent=2))
            return 0
        kit = make_kit(project, rundown)
    except NotApproved as exc:
        print(f"✋ {exc}", file=sys.stderr)
        return 3
    print(f"publish kit: {kit}")
    for item in sorted(kit.iterdir()):
        print(f"  - {item.name}")
    return 0


def cmd_daily(args: argparse.Namespace) -> int:
    """collect → (if curated) build → voice → render → review, for today's episode."""
    from datetime import date

    if not args.project or args.project == "episode":
        args.project = f"{date.today().isoformat()}-daily"
    project = _project(args)
    print(f"== project: {project.slug}")
    cmd_collect(args)
    if not project.stories_path.exists():
        print(
            "\n⚠️  stories.json ساخته نشد.\n"
            f"   تیترها در {project.candidates_path} و {project.build / 'candidates.md'} هستند.\n"
            "   خبرها را در فارسی بنویس (verified:true) و دوباره `telton daily` بزن."
        )
        return 0
    for step in (cmd_build, cmd_voice, cmd_render, cmd_review):
        code = step(args)
        if code:
            return code
    print(f"\nآماده‌ی تأیید: {project.out / 'review.html'}")
    print(f'سپس: telton publish -p {project.slug} --by "نام تو"')
    return 0


def cmd_youtube(args: argparse.Namespace) -> int:
    from . import youtube as yt
    from .publish import NotApproved

    if args.action == "auth":
        yt.load_credentials(
            args.client_secret, args.token, interactive=True, port=args.port, echo=print
        )
        print("✅ احراز هویت انجام شد.")
        print(json.dumps(yt.status(args.client_secret, args.token), ensure_ascii=False, indent=2))
        return 0

    if args.action == "status":
        print(json.dumps(yt.status(args.client_secret, args.token), ensure_ascii=False, indent=2))
        return 0

    from .models import Rundown

    project = _project(args)
    data = read_json(project.build / "rundown.json")
    if not data:
        print("rundown.json missing — run `telton build`", file=sys.stderr)
        return 2
    rundown = Rundown.from_dict(data)
    try:
        result = yt.upload_video(
            project,
            rundown,
            privacy=args.privacy,
            publish_at=args.publish_at,
            dry_run=args.dry_run,
            upload_thumbnail=not args.no_thumbnail,
            upload_captions=not args.no_captions,
            client_secret=args.client_secret,
            token=args.token,
        )
    except NotApproved as exc:
        print(f"✋ {exc}", file=sys.stderr)
        return 3
    except yt.YouTubeNotConfigured as exc:
        print(f"⚙️  {exc}", file=sys.stderr)
        return 4
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("url"):
        print(f"\n🎬 {result['url']}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    from .review import approval_status

    project = _project(args)
    stages = {
        "candidates": project.candidates_path.exists(),
        "stories": project.stories_path.exists(),
        "rundown": (project.build / "rundown.json").exists(),
        "audio": (project.build / "audio.wav").exists(),
        "video": project.video_path.exists(),
        "kit": (project.out / "publish-kit" / "video-9x16.mp4").exists(),
    }
    print(f"project {project.slug}  ({project.root})")
    for name, done in stages.items():
        print(f"  {'✅' if done else '· '} {name}")
    status = approval_status(project)
    print(f"  approval: {'✅ ' + str(status['record'].get('by')) if status['approved'] else '⏳ ' + '؛ '.join(status['reasons'])}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    """build → voice → render → review, in one go."""
    for step in (cmd_build, cmd_voice, cmd_render, cmd_review):
        code = step(args)
        if code:
            return code
    print('\nحالا out/review.html را ببین؛ بعد: telton approve --by "نام تو"')
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="telton",
        description="ایجنت خبر ورزشی: جمع‌آوری خبر → اسکریپت → نریشن → ویدیو → تأیید → انتشار",
    )
    parser.add_argument("--version", action="version", version=f"telton {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    def add(name: str, help_text: str, func) -> argparse.ArgumentParser:
        sp = sub.add_parser(name, help=help_text)
        sp.add_argument("--project", "-p", default="episode", help="project slug (projects/<slug>)")
        sp.set_defaults(func=func)
        return sp

    collect_p = add("collect", "collect headlines from RSS into build/candidates.json", cmd_collect)
    collect_p.add_argument("--show", type=int, default=12)

    build_p = add("build", "compose rundown + script + SRT + caption", cmd_build)
    build_p.add_argument("--duration", "-d", type=float, default=300.0, help="target seconds (پیش‌فرض ۳۰۰ = ۵ دقیقه)")
    build_p.add_argument("--title")

    voice_p = add("voice", "generate Persian voice-over and mix the audio track", cmd_voice)
    voice_p.add_argument("--voice", help="edge-tts voice id (default fa-IR-FaridNeural)")
    voice_p.add_argument("--rate", default=None, help="سرعت صدا مثل +12%% (پیش‌فرض از config/style.yaml)")
    voice_p.add_argument("--offline", action="store_true", help="skip TTS, use silence (fast smoke test)")
    voice_p.add_argument("--no-fit", action="store_true", help="keep every story even if it runs long")
    voice_p.add_argument("--duration", "-d", type=float, default=None)

    vt_p = add("voice-test", "render one sentence with every available voice", cmd_voice_test)
    vt_p.add_argument("--text", help="جمله‌ای که می‌خواهی مقایسه شود")
    vt_p.add_argument("--rate", default="+5%")
    vt_p.add_argument("--pitch", default="+2Hz")
    vt_p.add_argument("--open", action="store_true", help="پوشه را باز کن")

    render_p = add("render", "paint frames and encode the MP4", cmd_render)
    render_p.add_argument("--width", type=int, default=None)
    render_p.add_argument("--height", type=int, default=None)
    render_p.add_argument("--vertical", action="store_true", help="نسخه عمودی ۱۰۸۰×۱۹۲۰ (اینستاگرام/شورت)")
    render_p.add_argument("--fps", type=int, default=None)
    render_p.add_argument("--output", help="مسیر فایل خروجی")
    render_p.add_argument("--max-seconds", type=float, default=None, help="render a shorter draft")

    add("review", "write out/review.html (watch + check facts)", cmd_review)

    thumb_p = add("thumb", "make 3 click-worthy thumbnails", cmd_thumb)
    thumb_p.add_argument("--hook", help="متن قلاب تامبنیل (پیش‌فرض از project.yaml)")

    stock_p = add("stock", "download copyright-safe footage (Wikimedia Commons)", cmd_stock)
    stock_p.add_argument("--query", help="جست‌وجوی آزاد (برای دیدن نتایج)")
    stock_p.add_argument("--kind", default="video", choices=["video", "image"])
    stock_p.add_argument("--limit", type=int, default=4)
    stock_p.add_argument("--dry-run", action="store_true")

    short_p = add("short", "build a vertical short / reel (≤60s)", cmd_short)
    short_p.add_argument("--duration", "-d", type=float, default=50.0)
    short_p.add_argument("--count", type=int, default=3, help="چند خبر در شورت")
    short_p.add_argument("--voice")
    short_p.add_argument("--offline", action="store_true")

    pack_p = add("pack", "one-click daily pack: long video + 2 shorts", cmd_pack)
    pack_p.add_argument("--duration", "-d", type=float, default=300.0)
    pack_p.add_argument("--fast", action="store_true", help="فقط شورت‌ها را بساز")

    add("sync", "refresh headlines/b-roll in the existing rundown (no re-recording)", cmd_sync)

    approve_p = add("approve", "record your approval for the current video", cmd_approve)
    approve_p.add_argument("--by", required=True, help="your name (ثبت می‌شود)")
    approve_p.add_argument("--platforms", nargs="*", default=None)
    approve_p.add_argument("--force", action="store_true", help="approve even if some stories are unverified")

    publish_p = add("publish", "build the publish kit (requires approval)", cmd_publish)
    publish_p.add_argument("--platform", help="check an upload target (youtube/instagram/telegram/tiktok/x)")
    publish_p.add_argument("--live", action="store_true", help="actually attempt an upload (needs your API creds)")
    publish_p.add_argument("--by", help="تأیید + ساخت پکیج در یک دستور (نامت ثبت می‌شود)")
    publish_p.add_argument("--force", action="store_true", help="تأیید حتی اگر خبری verified نشده باشد")

    broll_p = add("broll", "download goal/highlight clips from a public Telegram channel", cmd_broll)
    broll_p.add_argument("--channel", default="varzesh3", help="نام کانال تلگرام (پیش‌فرض varzesh3)")
    broll_p.add_argument("--limit", type=int, default=20, help="چند پیام آخر بررسی شود")
    broll_p.add_argument("--min-score", type=int, default=3, help="حداقل تطابق کلیدواژه با خبر")
    broll_p.add_argument("--max-clips", type=int, default=8, help="حداکثر کلیپ دانلودی در هر اجرا")
    broll_p.add_argument("--dry-run", action="store_true", help="فقط نشان بده چه چیزی پیدا شد")
    broll_p.add_argument("--list", action="store_true", help="فهرست پیام‌های دارای ویدیو")

    yt_p = add("youtube", "آپلود به یوتیوب با OAuth خودت (auth / upload / status)", cmd_youtube)
    yt_p.add_argument("action", choices=["auth", "upload", "status"])
    yt_p.add_argument(
        "--privacy", default="unlisted", choices=["public", "unlisted", "private"],
        help="وضعیت انتشار (پیش‌فرض unlisted تا خودت بررسی کنی)",
    )
    yt_p.add_argument("--publish-at", help="زمان‌بندی انتشار، ISO مثل 2026-11-03T18:30:00Z (privacy private می‌شود)")
    yt_p.add_argument("--dry-run", action="store_true", help="فقط بدنه‌ی درخواست API را نشان بده")
    yt_p.add_argument("--no-thumbnail", action="store_true")
    yt_p.add_argument("--no-captions", action="store_true")
    yt_p.add_argument("--client-secret", help="مسیر client_secret.json (پیش‌فرض .secrets/client_secret.json)")
    yt_p.add_argument("--token", help="مسیر توکن (پیش‌فرض .secrets/youtube-token.json)")
    yt_p.add_argument("--port", type=int, default=0, help="پورت لوکال برای OAuth (۰ = تصادفی)")

    add("status", "show pipeline progress for a project", cmd_status)

    run_p = add("run", "build → voice → render → review", cmd_run)
    run_p.add_argument("--duration", "-d", type=float, default=300.0)
    run_p.add_argument("--title")
    run_p.add_argument("--voice")
    run_p.add_argument("--offline", action="store_true")
    run_p.add_argument("--rate", default=None)
    run_p.add_argument("--no-fit", action="store_true")
    run_p.add_argument("--width", type=int, default=None)
    run_p.add_argument("--height", type=int, default=None)
    run_p.add_argument("--fps", type=int, default=None)
    run_p.add_argument("--max-seconds", type=float, default=None)

    daily_p = add("daily", "one-shot daily episode: collect → build → voice → render → review", cmd_daily)
    daily_p.add_argument("--show", type=int, default=12)
    daily_p.add_argument("--duration", "-d", type=float, default=300.0)
    daily_p.add_argument("--title")
    daily_p.add_argument("--voice")
    daily_p.add_argument("--rate", default=None)
    daily_p.add_argument("--no-fit", action="store_true")
    daily_p.add_argument("--offline", action="store_true")
    daily_p.add_argument("--width", type=int, default=None)
    daily_p.add_argument("--height", type=int, default=None)
    daily_p.add_argument("--fps", type=int, default=None)
    daily_p.add_argument("--max-seconds", type=float, default=None)

    args = parser.parse_args(argv)
    if not hasattr(args, "show"):
        args.show = 12
    try:
        return args.func(args)
    except (FileNotFoundError, PermissionError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
