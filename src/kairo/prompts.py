"""Compile per-scene text-to-image and image-to-video prompts.

Every prompt is assembled from four blocks so that style and character
identity can never drift between scenes:

    STYLE_BLOCK  +  CHARACTER_BLOCK  +  scene image_prompt  +  CONTINUITY_BLOCK

Output: prompts/S01.md ... prompts/S25.md and prompts/INDEX.md
"""

from __future__ import annotations

from pathlib import Path

from . import screenplay

ROOT = screenplay.ROOT
PROMPTS_DIR = ROOT / "prompts"

STYLE_BLOCK = (
    "STYLE — Cinematic 2D hand-drawn stickman animation, consistent series look. "
    "Beautifully illustrated painted backgrounds with layered atmospheric depth, "
    "professional cinematic composition, atmospheric lighting and soft shadows, "
    "subtle film grain, 16:9 frame, 1920x1080, 24 fps motion, high detail. "
    "Not 3D, not photorealistic, not live action, no mixed styles."
)

CHARACTER_BLOCK = (
    "CHARACTER — KAIRO: cartoon stickman, slightly oversized round head, small black "
    "elliptical eyes, simple expressive eyebrows, movable mouth line, four short hair "
    "strands, thin simple arms and legs, slightly oversized feet. Head-to-body "
    "proportions must not change. {wardrobe_line} The same reference character image "
    "is used in every scene."
)

WARDROBE_LINES = {
    "suit": ("Modern appearance: black business suit, white shirt, black tie, dark shoes. "
             "No prehistoric clothing, no accessories."),
    "hide": ("Prehistoric appearance: simple primitive brown animal-hide tunic, bare feet, "
             "wooden spear when hunting. No modern accessories, no suit, no tie."),
}

NEGATIVE_BASE = (
    "3D render, CGI, photorealistic humans, live action footage, mixed visual styles, "
    "changing character design, inconsistent proportions, extra limbs, extra fingers, "
    "morphing face, different hairstyle, oversized muscles, realistic skin texture, "
    "text, letters, subtitles, captions, watermark, logo, signature, frame border, "
    "modern objects in prehistoric scenes, deer or wolf predator redesign, "
    "different cave layout, redesigned map, lens flare spam, heavy motion blur, "
    "jitter, camera shake in locked shots, duplicated characters, crowd"
)


def character_block(wardrobe: str) -> str:
    return CHARACTER_BLOCK.format(wardrobe_line=WARDROBE_LINES[wardrobe])


def continuity_block(scene: dict, episode: dict) -> str:
    anchors = episode["continuity_anchors"]
    lines = [f"- {c}" for c in scene["continuity"]]
    if scene["wardrobe"] == "hide":
        lines.append(f"- predator (if present): {anchors['predator']}")
    if scene["act"] == "map" or scene["setting"] == "map_platform":
        lines.append(f"- map: {anchors['map']}")
    if scene["setting"].startswith("cave"):
        lines.append(f"- cave: {anchors['cave']}")
    if scene["setting"].startswith("modern"):
        lines.append(f"- room: {anchors['room']}")
    return "CONTINUITY (must match previous and next scene)\n" + "\n".join(lines)


def build_scene_prompt(scene: dict, episode: dict) -> str:
    cur = scene["render"]["zoom"]
    return f"""# {scene['id']} — {scene['title']}
**{scene['timecode']}** · {scene['duration_s']}s · act: `{scene['act']}` · setting: `{scene['setting']}` · wardrobe: `{scene['wardrobe']}`

## 1. Text-to-image prompt (first frame / key art)
```
{STYLE_BLOCK}

{character_block(scene['wardrobe'])}

SHOT — {scene['shot']}. {scene['image_prompt']}

LIGHTING — {scene['lighting']}. Camera framing {cur[0]:.2f}x of frame.
```

## 2. Image-to-video prompt (12 second shot)
```
{STYLE_BLOCK}

{character_block(scene['wardrobe'])}

MOTION — {scene['video_prompt']}

CAMERA — {scene['camera']}. Duration exactly 12 seconds, 24 fps, no cuts inside the shot.

AUDIO INTENT — {scene['audio']}
```

## 3. Negative prompt
```
{NEGATIVE_BASE}
```

## 4.{continuity_block(scene, episode)}

## 5. Cast / performance
- Action: {scene['action']}
- Expression: {scene['expression']}
- Transition out: {scene['transition']}

## 6. Persian voice-over (verbatim, never translated)
> {scene['dialogue_fa']}

_English gloss (crew only, never burned in): {scene['gloss_en']}_
"""


def build_index(episode: dict) -> str:
    rows = ["| # | Timecode | Title | Setting | Wardrobe | Pose |",
            "|---|----------|-------|---------|----------|------|"]
    for s in episode["scenes"]:
        rows.append(
            f"| {s['index']:02d} | {s['timecode']} | {s['title']} | "
            f"`{s['setting']}` | {s['wardrobe']} | `{s['render']['pose']}` |")
    return f"""# KAIRO — Episode 01 shot index

25 scenes x 12 s = 300 s. Style and character blocks are identical in every
file: paste them into the image model, then paste the same character block plus
the motion block into the image-to-video model. Keep one seed per character
reference and reuse the same reference image in all 25 scenes.

{chr(10).join(rows)}

## Global negative prompt
```
{NEGATIVE_BASE}
```
"""


def build_all() -> list[Path]:
    episode = screenplay.merge()
    PROMPTS_DIR.mkdir(exist_ok=True)
    written = []
    for scene in episode["scenes"]:
        path = PROMPTS_DIR / f"{scene['id']}.md"
        path.write_text(build_scene_prompt(scene, episode), encoding="utf-8")
        written.append(path)
    index = PROMPTS_DIR / "INDEX.md"
    index.write_text(build_index(episode), encoding="utf-8")
    written.append(index)
    return written
