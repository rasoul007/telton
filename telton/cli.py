"""`telton` command line — one stage per command, plus `run` for the whole chain."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .config import Project
from .util import read_json, seconds_to_clock


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
        rate=getattr(args, "rate", "+0%"),
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
    video = render_video(
        project,
        rundown,
        audio if audio.exists() else None,
        width=args.width,
        height=args.height,
        fps=args.fps,
        max_seconds=args.max_seconds,
    )
    thumb = export_thumbnail(project, rundown)
    print(f"video: {video} ({video.stat().st_size / 1e6:.1f} MB)")
    print(f"thumbnail: {thumb}")
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


def cmd_publish(args: argparse.Namespace) -> int:
    from .models import Rundown
    from .publish import NotApproved, make_kit, upload

    project = _project(args)
    data = read_json(project.build / "rundown.json")
    if not data:
        print("rundown.json missing — run `telton build`", file=sys.stderr)
        return 2
    rundown = Rundown.from_dict(data)
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
    voice_p.add_argument("--rate", default="+0%", help="TTS speed, e.g. +8%% (پیش‌فرض +0%%)")
    voice_p.add_argument("--offline", action="store_true", help="skip TTS, use silence (fast smoke test)")
    voice_p.add_argument("--no-fit", action="store_true", help="keep every story even if it runs long")
    voice_p.add_argument("--duration", "-d", type=float, default=None)

    render_p = add("render", "paint frames and encode the MP4", cmd_render)
    render_p.add_argument("--width", type=int, default=None)
    render_p.add_argument("--height", type=int, default=None)
    render_p.add_argument("--fps", type=int, default=None)
    render_p.add_argument("--max-seconds", type=float, default=None, help="render a shorter draft")

    add("review", "write out/review.html (watch + check facts)", cmd_review)

    approve_p = add("approve", "record your approval for the current video", cmd_approve)
    approve_p.add_argument("--by", required=True, help="your name (ثبت می‌شود)")
    approve_p.add_argument("--platforms", nargs="*", default=None)
    approve_p.add_argument("--force", action="store_true", help="approve even if some stories are unverified")

    publish_p = add("publish", "build the publish kit (requires approval)", cmd_publish)
    publish_p.add_argument("--platform", help="check an upload target (youtube/instagram/telegram/tiktok/x)")
    publish_p.add_argument("--live", action="store_true", help="actually attempt an upload (needs your API creds)")

    add("status", "show pipeline progress for a project", cmd_status)

    run_p = add("run", "build → voice → render → review", cmd_run)
    run_p.add_argument("--duration", "-d", type=float, default=300.0)
    run_p.add_argument("--title")
    run_p.add_argument("--voice")
    run_p.add_argument("--offline", action="store_true")
    run_p.add_argument("--width", type=int, default=None)
    run_p.add_argument("--height", type=int, default=None)
    run_p.add_argument("--fps", type=int, default=None)
    run_p.add_argument("--max-seconds", type=float, default=None)

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
