# KAIRO — character bible

Reference for every department. These rules are enforced in code
(`src/kairo/figure.py`) and checked by `kairo check`.

## Silhouette (never changes)

| Feature | Rule | Body units |
|---|---|---|
| Head | round, slightly oversized | radius 118 |
| Eyes | small, black, elliptical | 0.105 r wide, 0.135 r tall |
| Eyebrows | simple, expressive, one stroke each | 0.40 r long |
| Mouth | single movable line / small oval | 0.34 r wide |
| Hair | three short strands on the crown | 0.17 r long |
| Torso | single thin body line | 208 units neck→hip |
| Arms | thin, two segments | 118 + 112 |
| Legs | thin, two segments | 168 + 168 |
| Feet | slightly oversized | 64 x 24 |
| Shoulders | narrower than the head | ±34 from the spine |

Total standing height is 876 body units; the head is ~27% of it, which is what
reads as "slightly oversized" without becoming chibi.

## Wardrobe

**Present day (S01–S05, S25)** — black business suit, white shirt, black tie,
dark shoes, no accessories. The jacket has a visible shoulder line, lapels and
a waist hem so the torso reads as clothing rather than a black block.

**Prehistoric (S06–S24)** — simple brown animal-hide tunic to mid-thigh with a
belt line and ragged hem, bare feet, wooden spear. No modern objects of any
kind. The tunic is deliberately the only brown mass in frame.

Wardrobe is bound to the act, not chosen per scene: `present/transition` must
be `suit`, `prehistoric/cave/map` must be `hide`. A mismatch fails QC.

## Performance rules

- KAIRO always looks into the lens when he narrates (S01–S04, S25).
- In the past he never looks into the lens — he is being remembered, not
  addressing us. This is the visual difference between the two timelines.
- Blinks are 2 frames, every 2.4–3.3 s, never on a cut.
- Mouth shape follows the voice-over envelope, not a fixed loop.
- Expressions used: warm, amused, thoughtful, sad, serious, alert, cautious,
  fear, amazed, determined, mysterious.

## The predator (locked design)

Large prehistoric big cat: low heavy shoulders, arched back, tucked belly,
wedge skull, short rounded ears, thick tail, tawny-grey coat with a dark dorsal
stripe. One design, four presentations: `silhouette` (S09), `full` (S10),
`threshold` (S14), `chase` (S11, S12). It never crosses the cave threshold.

## The map (locked design)

Circular amber stone tablet: three concentric rings, twelve radial grooves,
star-point markers, angular glyphs, one blank destination node at the
lower-right of the face. The glowing point appears at that node and is never
explained or located.
