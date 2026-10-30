"""Command line entry point: ``python -m kairo <command>``."""

from __future__ import annotations

import argparse
import json
import sys

from . import prompts, screenplay


def cmd_screenplay() -> None:
    episode = screenplay.merge()
    errors = screenplay.validate(episode)
    if errors:
        print("SCREENPLAY INVALID")
        for err in errors:
            print("  -", err)
        sys.exit(1)
    print(json.dumps(screenplay.stats(episode), ensure_ascii=False, indent=2))
    print("screenplay valid: 25 scenes / 300 s")


def cmd_prompts() -> None:
    written = prompts.build_all()
    print(f"wrote {len(written)} prompt files into prompts/")


def cmd_voice(force: bool) -> None:
    from . import voice
    report = voice.generate_all(force=force)
    print(json.dumps({k: v for k, v in report.items() if k != "scenes"},
                     ensure_ascii=False, indent=2))
    for row in report["scenes"]:
        flag = "ok " if row["fits"] else "OVER"
        print(f"  {flag} {row['id']}  speech={row['final_s']:>6.2f}s "
              f"budget={row['budget_s']:.2f}s rate=+{row['rate_pct'] or 0}%"
              + (f" tempo={row['atempo']}" if row["atempo"] else ""))


def cmd_score(force: bool) -> None:
    from . import music
    path = music.build(force=force)
    print(f"score written: {path}")


def cmd_stills(force: bool) -> None:
    from . import render
    paths = render.render_stills(force=force)
    print(f"{len(paths)} stills rendered into build/stills/")


def cmd_clips(force: bool, jobs: int = 3) -> None:
    from . import render
    paths = render.render_clips(force=force, jobs=jobs)
    print(f"{len(paths)} clips rendered into build/clips/")


def cmd_film(force: bool) -> None:
    from . import render
    print(render.assemble_film(force=force))


def cmd_srt() -> None:
    from . import subtitles
    path = subtitles.write_srt()
    print(f"review subtitles: {path}")


def cmd_sheet() -> None:
    from . import portrait
    print(portrait.character_sheet())


def cmd_review() -> None:
    from . import render
    print(render.assemble_review())


def cmd_preview() -> None:
    from . import render
    print(render.encode_preview())


def cmd_check() -> None:
    from . import qc
    report = qc.run_all()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["passed"]:
        sys.exit(1)


def cmd_all() -> None:
    cmd_screenplay()
    cmd_prompts()
    cmd_voice(force=False)
    cmd_score(force=False)
    cmd_stills(force=False)
    cmd_clips(force=False)
    cmd_film(force=False)
    cmd_srt()
    cmd_check()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="kairo", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    for name, fn, needs_force in (
        ("screenplay", cmd_screenplay, False),
        ("prompts", cmd_prompts, False),
        ("voice", cmd_voice, True),
        ("score", cmd_score, True),
        ("stills", cmd_stills, True),
        ("clips", cmd_clips, True),
    ):
        p = sub.add_parser(name)
        if needs_force:
            p.add_argument("--force", action="store_true")

    clips_p = sub.choices["clips"]
    clips_p.add_argument("--jobs", type=int, default=3)

    p = sub.add_parser("film")
    p.add_argument("--force", action="store_true")
    sub.add_parser("srt")
    sub.add_parser("sheet")
    sub.add_parser("review")
    sub.add_parser("preview")
    sub.add_parser("check")
    sub.add_parser("all")

    args = parser.parse_args(argv)
    handlers = {
        "screenplay": lambda: cmd_screenplay(),
        "prompts": lambda: cmd_prompts(),
        "voice": lambda: cmd_voice(getattr(args, "force", False)),
        "score": lambda: cmd_score(getattr(args, "force", False)),
        "stills": lambda: cmd_stills(getattr(args, "force", False)),
        "clips": lambda: cmd_clips(getattr(args, "force", False),
                                    getattr(args, "jobs", 3)),
        "film": lambda: cmd_film(getattr(args, "force", False)),
        "srt": lambda: cmd_srt(),
        "sheet": lambda: cmd_sheet(),
        "review": lambda: cmd_review(),
        "preview": lambda: cmd_preview(),
        "check": lambda: cmd_check(),
        "all": lambda: cmd_all(),
    }
    handlers[args.command]()


if __name__ == "__main__":
    main()
