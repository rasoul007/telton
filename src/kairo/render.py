"""Render the film: stills, 12 second clips, and the 300 second master.

Pipeline per scene
------------------
1. paint the backdrop once at 3840x2160,
2. draw KAIRO into a few mouth/blink layer variants,
3. for every one of the 288 frames: crop the camera move out of the 4K master,
   downscale to 1920x1080, composite the character layer and pipe the frame
   straight into ffmpeg.

The mouth is driven by the actual voice-over envelope, so the animation is in
sync with the Persian narration instead of being a static Ken Burns still.
"""

from __future__ import annotations

import json
import subprocess
import wave
from pathlib import Path

import numpy as np
from PIL import Image

from . import backdrops, figure, predator, screenplay
from .config import CLIPS, FPS, HEIGHT, OUT, SAMPLE_RATE, STILLS, WIDTH, FFMPEG, probe

SS = backdrops.SS
BIG_W, BIG_H = backdrops.W, backdrops.H

# hip height above the ground, in body units, per posture
STAND_HIP = 336.0
SIT_HIP = 208.0
KNEEL_HIP = 150.0

# where each backdrop puts the character (fraction of frame) and how big the
# character should read in frame
STAGE = {
    "modern_room": (0.34, 0.80),
    "modern_room_closeup": (0.50, 0.52),
    "savanna_aerial": (0.44, 0.84),
    "savanna_grass": (0.40, 0.84),
    "savanna_predator": (0.31, 0.88),
    "savanna_chase": (0.38, 0.86),
    "savanna_tracks": (0.52, 0.90),
    "savanna_rocks": (0.42, 0.84),
    "cave_entrance_ext": (0.60, 0.86),
    "cave_entrance_int": (0.58, 0.88),
    "cave_mouth_from_inside": (0.13, 0.90),
    "cave_passage_mouth": (0.38, 0.86),
    "cave_passage": (0.50, 0.90),
    "cave_chamber": (0.30, 0.88),
    "cave_chamber_exit": (0.44, 0.88),
    "map_platform": (0.24, 0.86),
    "map_macro": (0.30, 0.90),
    "map_touch": (0.28, 0.92),
    "map_point": (0.22, 0.92),
}

FRAMING = (("extreme", 2.9), ("macro", 2.9), ("close-up", 2.1),
           ("close", 2.1), ("wide", 0.95), ("aerial", 0.6), ("medium", 1.25))

SCALE_OVERRIDE = {   # scenes where the keyword framing reads wrong
    "S01": 1.90, "S02": 2.20, "S03": 2.10, "S04": 2.20, "S25": 2.30,
    "S06": 1.10, "S10": 1.30, "S19": 1.00, "S20": 1.30, "S21": 1.35,
    "S22": 1.35, "S23": 1.30, "S24": 1.25,
}

FOCUS = {            # camera centre for the push-in, per backdrop
    "modern_room": (0.34, 0.46),
    "modern_room_closeup": (0.50, 0.40),
    "savanna_aerial": (0.50, 0.55),
    "savanna_tracks": (0.50, 0.72),
    "cave_mouth_from_inside": (0.35, 0.55),
    "cave_chamber": (0.44, 0.55),
    "map_platform": (0.46, 0.62),
}

EXPRESSION_FOR = {
    "S01": "amused", "S02": "thoughtful", "S03": "sad", "S04": "serious",
    "S05": "neutral", "S06": "alert", "S07": "cautious", "S08": "cautious",
    "S09": "alert", "S10": "fear", "S11": "fear", "S12": "alert",
    "S13": "fear", "S14": "cautious", "S15": "cautious", "S16": "alert",
    "S17": "amazed", "S18": "cautious", "S19": "amazed", "S20": "amazed",
    "S21": "determined", "S22": "amazed", "S23": "amazed",
    "S24": "determined", "S25": "mysterious",
}


def hip_height(pose_name: str) -> float:
    if pose_name.startswith("sit") or pose_name == "closeup_calm":
        return SIT_HIP
    if pose_name in ("kneel_look", "lift_map"):
        return KNEEL_HIP
    return STAND_HIP


def scale_for(scene: dict) -> float:
    shot = scene["shot"].lower()
    mult = next((m for key, m in FRAMING if key in shot), 1.25)
    return SCALE_OVERRIDE.get(scene["id"], mult)


def stage_for(scene: dict):
    """Character origin in 4K space, plus the scale it is drawn at."""
    name = scene["render"]["backdrop"]
    pose_name = scene["render"]["pose"]
    ground_x, ground_y = STAGE.get(name, (0.45, 0.86))
    scale = scale_for(scene)
    if name.startswith("modern_room"):
        # hip must land exactly on the chair seat drawn by the backdrop
        origin_y = BIG_H * 0.82 - (184 + figure.POSES[pose_name].hip_drop) * scale
    else:
        origin_y = BIG_H * ground_y - hip_height(pose_name) * scale
    return (BIG_W * ground_x, origin_y), scale


def head_centre_y(scene: dict, origin, scale: float) -> float:
    pose = figure.POSES[scene["render"]["pose"]]
    return origin[1] + (pose.hip_drop - figure.TORSO - figure.NECK_RISE) * scale


def focus_for(scene: dict, origin, scale: float):
    """Camera centre: the head for close work, a neutral third for wide shots."""
    x = origin[0] / BIG_W
    if scale >= 1.8:
        y = head_centre_y(scene, origin, scale) / BIG_H
        y = min(max(y, 0.12), 0.78)
    else:
        y = 0.45
    return (min(max(x, 0.12), 0.88), y)



def facing_for(scene: dict) -> int:
    return -1 if scene["render"].get("facing") in ("left", "back") else 1


def voice_lead_in() -> float:
    report = screenplay.ROOT / "audio" / "vo" / "vo_report.json"
    if report.exists():
        return json.loads(report.read_text(encoding="utf-8"))["lead_in_s"]
    return 0.55


def scene_assets(scene: dict):
    """Paint the backdrop and pre-draw the character layer variants."""
    backdrop = scene["render"]["backdrop"]
    if backdrop == "eyes_to_savanna":
        eyes = Image.new("RGBA", (BIG_W, BIG_H), (0, 0, 0, 255))
        figure.draw_eyes(eyes, (BIG_W * 0.50, BIG_H * 0.44), BIG_H * 0.20)
        return ("s05", eyes, backdrops.savanna("grass", seed=7).convert("RGBA"))

    origin, scale = stage_for(scene)
    bg = backdrops.render(backdrop, k=scale,
                          seat_x=STAGE.get(backdrop, (0.34, 0.8))[0]).convert("RGBA")
    facing = facing_for(scene)

    extra = scene["render"].get("extra")
    if extra:
        if extra == "predator_silhouette":
            predator.draw_predator(bg, (BIG_W * 0.54, BIG_H * 0.88), 1.15 * SS,
                                 "silhouette", facing=-1)
        elif extra == "predator_full":
            predator.draw_predator(bg, (BIG_W * 0.64, BIG_H * 0.92), 1.15 * SS,
                                 "full", facing=-1)
        elif extra == "predator_threshold":
            predator.draw_predator(bg, (BIG_W * 0.40, BIG_H * 0.90), 0.70 * SS,
                                 "full", facing=-1)
        elif extra == "predator_chase":
            predator.draw_predator(bg, (BIG_W * 0.58, BIG_H * 0.94), 0.95 * SS,
                                 "silhouette", facing=-1)

    expr = EXPRESSION_FOR.get(scene["id"], "neutral")
    pose = scene["render"]["pose"]
    wardrobe = scene["wardrobe"]
    prop_state = "glow" if scene["id"] in ("S22", "S23", "S24") else "rest"

    def layer(mouth: float, blink: bool) -> Image.Image:
        override = None if backdrop.startswith("map_") else figure._UNSET
        return figure.kairo_layer((BIG_W, BIG_H), origin, scale, pose, wardrobe,
                                  expr, facing=facing, mouth=mouth, blink=blink,
                                  prop_state=prop_state, prop_override=override)

    # 0 closed, 1 half, 2 wide, 3 blink (eyes closed)
    variants = [layer(0.0, False), layer(0.45, False), layer(0.95, False),
                layer(0.0, True)]
    return ("figure", bg, variants)


def mouth_envelope(scene: dict, frames: int) -> np.ndarray:
    """Voice-over RMS, resampled to one value per frame."""
    path = screenplay.ROOT / "audio" / "vo" / f"{scene['id']}.wav"
    if not path.exists():
        return np.zeros(frames, dtype=np.float32)
    with wave.open(str(path), "rb") as w:
        sr = w.getframerate()
        data = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2")
    data = data.astype(np.float32) / 32768.0
    lead = voice_lead_in()
    hop = sr / FPS
    env = np.zeros(frames, dtype=np.float32)
    for f in range(frames):
        start = int((lead + f / FPS) * sr)
        if start >= data.size:
            break
        chunk = data[start:int(start + hop)]
        if chunk.size:
            env[f] = float(np.sqrt(np.mean(chunk ** 2)))
    peak = env.max() or 1.0
    return np.clip(env / (peak * 0.55), 0, 1)


def _blink_frames(scene: dict, frames: int) -> set[int]:
    """Deterministic natural blink pattern for this scene."""
    step = 67 + (scene["index"] * 13) % 37          # 2.4-3.3 s apart
    start = 24 + (scene["index"] * 7) % 40
    out = set()
    f = start
    while f < frames - 10:
        out.update({f, f + 1})
        f += step
    return out


def _crop_box(focus, zoom: float):
    cw, ch = BIG_W / zoom, BIG_H / zoom
    cx = min(max(focus[0] * BIG_W, cw / 2), BIG_W - cw / 2)
    cy = min(max(focus[1] * BIG_H, ch / 2), BIG_H - ch / 2)
    return (int(cx - cw / 2), int(cy - ch / 2),
            int(cx + cw / 2), int(cy + ch / 2))


def _ease(t: float) -> float:
    return t * t * (3 - 2 * t)          # smoothstep, no ease-in pop


def render_clip(scene: dict, force: bool = False) -> Path:
    out = CLIPS / f"{scene['id']}.mp4"
    if out.exists() and not force:
        # A partially written mp4 has no moov atom, so probe() returns None.
        # Never trust an existing file just because it exists.
        info = probe(out)
        if (info["duration_s"] and abs(info["duration_s"] - 12) <= 0.05
                and info["width"] == WIDTH and info["height"] == HEIGHT):
            return out
        out.unlink(missing_ok=True)
    CLIPS.mkdir(parents=True, exist_ok=True)

    frames = int(round(scene["duration_s"] * FPS))
    kind, a, b = scene_assets(scene)
    env = mouth_envelope(scene, frames)
    blinks = _blink_frames(scene, frames)
    z0, z1 = scene["render"]["zoom"]
    origin, scale = stage_for(scene)
    fx, fy = focus_for(scene, origin, scale)

    # Composite the character onto the backdrop once per mouth/blink state.
    # Per frame we then need a single crop+resize instead of two.
    if kind == "figure":
        composites = [Image.alpha_composite(a, layer).convert("RGB") for layer in b]
    else:
        composites = []

    cmd = [str(FFMPEG), "-hide_banner", "-loglevel", "error", "-y",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{WIDTH}x{HEIGHT}",
           "-r", str(FPS), "-i", "-", "-an",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
           "-threads", "2", "-pix_fmt", "yuv420p",
           "-movflags", "+faststart", str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    fade_frames = int(scene["render"].get("fade_out_s", 0) * FPS)
    for f in range(frames):
        t = f / max(1, frames - 1)
        zoom = z0 + (z1 - z0) * _ease(t)
        box = _crop_box((fx, fy), zoom)

        if kind == "s05":
            iris = min(1.0, max(0.0, (t - 0.25) / 0.6))
            # RGB is mandatory here: RGBA would feed 4 bytes per pixel into a
            # rawvideo rgb24 pipe and silently produce 4/3 the expected frames.
            src = Image.blend(a.convert("RGB"), b.convert("RGB"), iris ** 1.6)
            frame = src.resize((WIDTH, HEIGHT), Image.BILINEAR, box=box).convert("RGB")
        else:
            idx = 3 if f in blinks else (
                0 if env[f] < 0.12 else (1 if env[f] < 0.55 else 2))
            frame = composites[idx].resize((WIDTH, HEIGHT), Image.BILINEAR, box=box)

        if fade_frames and f >= frames - fade_frames:
            k = (frames - f) / fade_frames
            frame = Image.eval(frame, lambda v, k=k: int(v * k))

        if frame.mode != "RGB":       # the pipe is rgb24, no exceptions
            frame = frame.convert("RGB")

        proc.stdin.write(frame.tobytes())

    proc.stdin.close()
    proc.wait()
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed for {scene['id']}")

    # A shot that is not exactly 12.000 s is a defect, not a rounding error.
    info = probe(out)
    if info["duration_s"] is None or abs(info["duration_s"] - 12) > 0.05:
        out.unlink(missing_ok=True)
        raise RuntimeError(
            f"{scene['id']} rendered {info['duration_s']}s, expected 12s")
    return out


def _render_one(job):
    scene_id, scene = job
    path = render_clip(scene)
    return scene_id, str(path), probe(path)



def _preview(scene: dict) -> Image.Image:
    kind, a, b = scene_assets(scene)
    origin, scale = stage_for(scene)
    fx, fy = focus_for(scene, origin, scale)
    z0, z1 = scene["render"]["zoom"]
    box = _crop_box((fx, fy), (z0 + z1) / 2)
    if kind == "s05":
        return Image.blend(a, b, 0.75).convert("RGB")
    bg = a.crop(box).resize((WIDTH, HEIGHT), Image.BILINEAR)
    char = b[1].crop(box).resize((WIDTH, HEIGHT), Image.BILINEAR)
    return Image.alpha_composite(bg, char).convert("RGB")


def render_stills(force: bool = False) -> list[Path]:
    episode = screenplay.load()
    STILLS.mkdir(parents=True, exist_ok=True)
    paths = []
    for scene in episode["scenes"]:
        out = STILLS / f"{scene['id']}.png"
        if not out.exists() or force:
            _preview(scene).save(out)
        paths.append(out)
    return paths


def render_clips(force: bool = False, jobs: int = 3) -> list[Path]:
    """Render every clip. Scenes are independent, so they run in parallel."""
    episode = screenplay.load()
    todo = []
    for scene in episode["scenes"]:
        out = CLIPS / f"{scene['id']}.mp4"
        if force and out.exists():
            out.unlink()
        todo.append((scene["id"], scene))

    paths = []
    if jobs <= 1:
        for sid, scene in todo:
            path = render_clip(scene, force=force)
            info = probe(path)
            print(f"  {sid}  {info['duration_s']:.3f}s  "
                  f"{info['width']}x{info['height']} @ {info['fps']}fps",
                  flush=True)
            paths.append(path)
    else:
        from concurrent.futures import ProcessPoolExecutor, as_completed
        with ProcessPoolExecutor(max_workers=jobs) as pool:
            futures = {pool.submit(_render_one, job): job[0] for job in todo}
            for fut in as_completed(futures):
                sid, path, info = fut.result()
                print(f"  {sid}  {info['duration_s']:.3f}s  "
                      f"{info['width']}x{info['height']} @ {info['fps']}fps",
                      flush=True)
                paths.append(Path(path))
    return sorted(paths)


# ------------------------------------------------------------------- audio
def mix_audio() -> Path:
    """Place every voice-over at its scene start on top of the score bed."""
    from . import music
    score_path = music.build()
    mix_path = screenplay.ROOT / "audio" / "mix.wav"
    episode = screenplay.load()
    lead = voice_lead_in()

    with wave.open(str(score_path), "rb") as w:
        sr = w.getframerate()
        total = w.getnframes()
        score = np.frombuffer(w.readframes(total), dtype="<i2")
    score = score.reshape(-1, 2).astype(np.float32) / 32768.0

    for scene in episode["scenes"]:
        path = screenplay.ROOT / "audio" / "vo" / f"{scene['id']}.wav"
        if not path.exists():
            raise FileNotFoundError(f"missing voice-over for {scene['id']}")
        with wave.open(str(path), "rb") as w:
            assert w.getframerate() == sr, "voice-over must be 48 kHz"
            vo = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2")
        vo = vo.astype(np.float32) / 32768.0
        start = int((scene["start_s"] + lead) * sr)
        end = min(score.shape[0], start + vo.size)
        score[start:end, 0] += vo[: end - start]
        score[start:end, 1] += vo[: end - start]

    peak = float(np.max(np.abs(score))) or 1.0
    if peak > 0.95:
        score *= 0.95 / peak
    pcm = (np.clip(score, -1, 1) * 32767).astype("<i2")
    with wave.open(str(mix_path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    return mix_path


def _concat_clips() -> Path:
    episode = screenplay.load()
    list_path = CLIPS / "clips.txt"
    lines = []
    for scene in episode["scenes"]:
        clip = CLIPS / f"{scene['id']}.mp4"
        if not clip.exists():
            raise FileNotFoundError(f"missing clip {clip}")
        lines.append(f"file '{clip.name}'")
    list_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    joined = CLIPS / "episode_video.mp4"
    subprocess.run([str(FFMPEG), "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "concat", "-safe", "0", "-i", str(list_path),
                    "-c", "copy", str(joined)], check=True)
    info = probe(joined)
    if info["duration_s"] is None or abs(info["duration_s"] - 300) > 0.1:
        raise RuntimeError(
            f"concatenated video is {info['duration_s']}s, expected 300s")
    return joined


def assemble_film(force: bool = False) -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    final = OUT / "kairo_ep01_animatic.mp4"
    video = _concat_clips()
    audio = mix_audio()
    subprocess.run([str(FFMPEG), "-hide_banner", "-loglevel", "error", "-y",
                    "-i", str(video), "-i", str(audio),
                    "-map", "0:v:0", "-map", "1:a:0",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                    "-shortest", "-movflags", "+faststart", str(final)],
                   check=True)
    info = probe(final)
    report = {
        "file": str(final),
        "duration_s": info["duration_s"],
        "resolution": f"{info['width']}x{info['height']}",
        "fps": info["fps"],
        "scenes": len(screenplay.load()["scenes"]),
        "audio": str(audio),
    }
    if not (299.9 <= (info["duration_s"] or 0) <= 300.1):
        raise RuntimeError(f"master duration is {info['duration_s']}s, expected 300s")
    return report


def assemble_review() -> Path:
    """Subtitled review copy - for the team only, never the deliverable."""
    from . import subtitles
    srt = subtitles.write_srt()
    final = OUT / "kairo_ep01_animatic_review.mp4"
    master = OUT / "kairo_ep01_animatic.mp4"
    style = ("FontName=Noto Naskh Arabic,FontSize=20,PrimaryColour=&H00F0F0F0,"
             "OutlineColour=&H80000000,BorderStyle=1,Outline=2,Shadow=0,"
             "Alignment=2,MarginV=48")
    subprocess.run([str(FFMPEG), "-hide_banner", "-loglevel", "error", "-y",
                    "-i", str(master), "-vf",
                    f"subtitles={srt}:force_style='{style}'",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                    "-c:a", "copy", str(final)], check=True)
    return final

