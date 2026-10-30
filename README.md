# KAIRO — Episode 01: The Man Who Defeated Time

A complete production kit for a 5-minute cinematic 2D stickman short film:
25 connected scenes x 12 s = **300 s**, 16:9, 1920x1080, 24 fps, Persian.

This repository does two things:

1. **Locks the film as data** — screenplay, per-scene image/video generation
   prompts, continuity anchors and Persian dialogue in one validated source.
2. **Renders a fully narrated animatic** of the whole episode (real Persian
   voice-over, original score, mouth animation synced to the voice, 25 exact
   12-second shots) so timing, tone and continuity can be judged before any
   final-painted animation exists.

```
out/kairo_ep01_animatic.mp4          <- 300 s master, 1920x1080, 24 fps
out/kairo_ep01_review.srt           <- Persian subtitles (review only, not burned in)
```

## What is generated, and what is not

| Piece | Status in this repo |
|---|---|
| Screenplay, 25 scenes, Persian dialogue | **Done** — `film/`, validated |
| Per-scene image + video prompts | **Done** — `prompts/S01.md … S25.md` |
| Persian narration (male, `fa-IR-FaridNeural`) | **Done** — `audio/vo/` |
| Original score + sound design, 300 s | **Done** — `audio/music/score.wav` |
| 25 shots x 12 s, 1920x1080, 24 fps | **Done** — animated animatic, procedural 2D |
| Final painted animation with rich hand-drawn backgrounds | **Not generated here** — needs an image/video model. Use `prompts/` |

The animatic is a real, timed, narrated film cut in the specified style
(flat 2D stickman over painted layered backdrops), not a storyboard slideshow:
KAIRO blinks, his mouth moves with the voice-over, the camera pushes and tilts,
and every shot is exactly 12.000 s. It is the reference cut that a produced
version should match shot for shot.

## How to run

```bash
npm install                      # provides the pinned ffmpeg binary
pip install -r requirements.txt  # pillow, numpy, edge-tts

PYTHONPATH=src python3 -m kairo screenplay  # validate + merge the 25 scene files
PYTHONPATH=src python3 -m kairo prompts     # write prompts/S01..S25 + INDEX
PYTHONPATH=src python3 -m kairo voice       # Persian VO, fitted to 12 s slots
PYTHONPATH=src python3 -m kairo score       # 300 s score + sound design
PYTHONPATH=src python3 -m kairo stills      # one 1080p frame per scene
PYTHONPATH=src python3 -m kairo clips       # 25 x 12 s clips (slow, ~10 min)
PYTHONPATH=src python3 -m kairo film        # concat + mix -> out/*.mp4
PYTHONPATH=src python3 -m kairo srt         # review subtitles
PYTHONPATH=src python3 -m kairo check       # QC: every rule measured, exit 1 on fail
```

`npm run <command>` works for each of the above.

## Layout

```
film/episode_header.json   series + format + continuity anchors (single source)
film/scenes/S01..S25.json  one file per scene: shot, camera, lighting, audio,
                           action, Persian dialogue, image/video prompts
film/episode01.json        merged, validated screenplay (generated)
prompts/                   per-scene generation prompts + shot index
src/kairo/                 pipeline: screenplay, prompts, voice, music,
                           figure, predator, backdrops, render, subtitles, qc
build/stills, build/clips  rendered intermediates (git-ignored)
audio/vo, audio/music      voice-over and score
out/                       deliverable master + review subtitles
```

## The film at a glance

| Act | Scenes | Time | Look |
|---|---|---|---|
| Present day | S01–S05 | 00:00–01:00 | dark room, warm lamp, clock |
| The memory | S05 | 00:48–01:00 | match cut: pupil to sunrise |
| Prehistoric Africa | S06–S13 | 01:00–02:36 | golden savanna, hunt, chase |
| The cave | S13–S19 | 02:24–03:48 | threshold, passage, chamber |
| The map | S19–S24 | 03:36–04:48 | amber tablet, golden-blue light |
| The revelation | S25 | 04:48–05:00 | back to the room, fade out |

Continuity is enforced, not hoped for: wardrobe is bound to the timeline
(`present/transition → suit`, `prehistoric/cave/map → hide`), every scene
references a named backdrop with fixed geometry, and `kairo check` fails the
build if any of it drifts.
