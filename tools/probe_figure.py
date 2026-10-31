"""Scratch probe: render KAIRO large on a neutral plate to judge craft.

Not part of the pipeline; used while dialling in the figure.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PIL import Image, ImageDraw

from kairo import portrait as P

W, H = 1400, 1600
img = Image.new("RGBA", (W, H), (58, 56, 60, 255))
d = ImageDraw.Draw(img, "RGBA")
for x in range(0, W, 100):
    d.line([(x, 0), (x, H)], fill=(70, 68, 72, 255))
for y in range(0, H, 100):
    d.line([(0, y), (W, y)], fill=(70, 68, 72, 255))

floor = int(H * 0.93)
wardrobe = sys.argv[1] if len(sys.argv) > 1 else "suit"
height_px = float(sys.argv[2]) if len(sys.argv) > 2 else 1250.0
s = height_px / 838.0
hip = (W * 0.5, floor - (P.THIGH + P.SHIN + P.FOOT_H) * s)
print("hip", hip, "s", s, "head top", hip[1] - (P.TORSO + P.NECK_RISE + P.HEAD_R * 1.86) * s)

arms = tuple(float(v) for v in sys.argv[3].split(",")) if len(sys.argv) > 3 else (-9, -5, 7, 2)
legs = tuple(float(v) for v in sys.argv[4].split(",")) if len(sys.argv) > 4 else (-9, -3, 11, 4)

P.draw_kairo(img, hip, s, wardrobe, facing=1, turn=0.0, lean=0,
             arms=arms, legs=legs,
             expression={"brow": -2, "smile": True}, mouth=0.25,
             prop="spear" if wardrobe == "hide" else None)
img.convert("RGB").save("/tmp/probe.png")
print("wrote /tmp/probe.png")
