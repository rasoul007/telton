"""One-click daily pack: long video + two vertical shorts (morning / evening / night).

    telton pack -p <slug>            # long (16:9) + short3 + short2
    telton pack -p <slug> --fast     # skip the long render (shorts only)

Morning short = the newest/strongest story, night short = a different angle
(different story set) so the two do not look identical to the algorithm.
"""

from __future__ import annotations

from pathlib import Path

from .config import Project


def _exists(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 1000


def make_pack(project: Project, target: float = 300.0, fast: bool = False) -> list[dict]:
    """Build everything a day needs; returns a schedule with file paths."""
    from .render import render_video
    from .rundown import build
    from .short import make_short
    from .thumbnail import build_thumbnails
    from .voice import assemble_audio, voice_stage

    project.ensure()
    made: list[dict] = []

    if not fast:
        rundown = build(project, target=target)
        rundown, audio = voice_stage(project, target=target)
        render_video(project, rundown, audio)
        build_thumbnails(project, rundown)
        made.append({"slot": "19:30", "type": "long 16:9", "file": str(project.video_path)})

    morning = make_short(project, target=45, count=3)
    made.append({"slot": "10:00", "type": "short 9:16", "file": morning["short"],
                 "stories": morning["stories"]})

    night = make_short(project, target=40, count=2)
    made.append({"slot": "22:00", "type": "short 9:16", "file": night["short"],
                 "stories": night["stories"]})
    return made
