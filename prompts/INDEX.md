# KAIRO — Episode 01 shot index

25 scenes x 12 s = 300 s. Style and character blocks are identical in every
file: paste them into the image model, then paste the same character block plus
the motion block into the image-to-video model. Keep one seed per character
reference and reuse the same reference image in all 25 scenes.

| # | Timecode | Title | Setting | Wardrobe | Pose |
|---|----------|-------|---------|----------|------|
| 01 | 00:00–00:12 | A Mysterious Beginning | `modern_room` | suit | `sit_talk` |
| 02 | 00:12–00:24 | People and Their Hurry | `modern_room` | suit | `sit_gesture` |
| 03 | 00:24–00:36 | Forgetting Today | `modern_room` | suit | `sit_glance_clock` |
| 04 | 00:36–00:48 | Something Changed | `modern_room_closeup` | suit | `closeup_calm` |
| 05 | 00:48–01:00 | Entering a Memory | `eye_matchcut` | suit | `eyes_extreme` |
| 06 | 01:00–01:12 | The Ancient World | `savanna_aerial` | hide | `stand_grass_spear` |
| 07 | 01:12–01:24 | The Hunt | `savanna_grass` | hide | `walk_spear` |
| 08 | 01:24–01:36 | Footprints | `savanna_grass` | hide | `kneel_look` |
| 09 | 01:36–01:48 | Danger | `savanna_grass` | hide | `stand_freeze` |
| 10 | 01:48–02:00 | The Predator | `savanna_predator` | hide | `stand_back_spear` |
| 11 | 02:00–02:12 | Escape | `savanna_chase` | hide | `run` |
| 12 | 02:12–02:24 | The Cave Entrance | `savanna_rocks` | hide | `run_turn` |
| 13 | 02:24–02:36 | Entering the Cave | `cave_entrance_int` | hide | `stumble` |
| 14 | 02:36–02:48 | The Predator Stops | `cave_entrance_int` | hide | `press_rock` |
| 15 | 02:48–03:00 | Strange Silence | `cave_entrance_int` | hide | `peek_rock` |
| 16 | 03:00–03:12 | A Strange Sound | `cave_entrance_int` | hide | `turn_passage` |
| 17 | 03:12–03:24 | Curiosity | `cave_passage_mouth` | hide | `step_forward` |
| 18 | 03:24–03:36 | The Dark Passage | `cave_passage` | hide | `walk_passage` |
| 19 | 03:36–03:48 | The Unknown Chamber | `cave_chamber` | hide | `stand_amazed` |
| 20 | 03:48–04:00 | Discovering the Map | `cave_chamber` | hide | `approach_map` |
| 21 | 04:00–04:12 | Approaching the Map | `cave_chamber` | hide | `reach_hand` |
| 22 | 04:12–04:24 | Touching the Map | `cave_chamber` | hide | `touch_map` |
| 23 | 04:24–04:36 | The Illuminated Point | `cave_chamber` | hide | `stand_amazed` |
| 24 | 04:36–04:48 | The Decision | `cave_chamber` | hide | `lift_map` |
| 25 | 04:48–05:00 | The Revelation | `modern_room_closeup` | suit | `sit_final` |

## Global negative prompt
```
3D render, CGI, photorealistic humans, live action footage, mixed visual styles, changing character design, inconsistent proportions, extra limbs, extra fingers, morphing face, different hairstyle, oversized muscles, realistic skin texture, text, letters, subtitles, captions, watermark, logo, signature, frame border, modern objects in prehistoric scenes, deer or wolf predator redesign, different cave layout, redesigned map, lens flare spam, heavy motion blur, jitter, camera shake in locked shots, duplicated characters, crowd
```
