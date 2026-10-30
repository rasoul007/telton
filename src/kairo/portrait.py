"""Hero-quality KAIRO art for review.

A dedicated renderer for stills (character sheet, key art) that draws the same
locked design as the film but with proper craft: tapered ink strokes, rounded
hands, real shoes, jacket lapels and buttons, shaded head, rim light and a
painted backdrop. Used to approve the character before a full re-render.
"""

from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

SS = 2                       # supersample for crisp edges
INK = (22, 18, 16)
INK_SOFT = (46, 40, 36)
SKIN = (233, 221, 202)
SKIN_SHADE = (206, 190, 168)
SUIT = (26, 26, 30)
SUIT_LIGHT = (44, 44, 50)
SHIRT = (240, 236, 226)
TIE = (14, 14, 16)
HIDE = (128, 92, 56)
HIDE_DARK = (92, 64, 38)
HIDE_LIGHT = (150, 110, 70)
RIM = (255, 206, 140)
FLOOR = (18, 16, 16)


def _taper(d, p0, p1, w0, w1, colour, caps=True):
    """A limb segment drawn as a tapered stroke with round joints."""
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    length = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / length, dx / length
    d.polygon([(p0[0] + nx * w0 / 2, p0[1] + ny * w0 / 2),
               (p1[0] + nx * w1 / 2, p1[1] + ny * w1 / 2),
               (p1[0] - nx * w1 / 2, p1[1] - ny * w1 / 2),
               (p0[0] - nx * w0 / 2, p0[1] - ny * w0 / 2)], fill=colour)
    if caps:
        d.ellipse([p0[0] - w0 / 2, p0[1] - w0 / 2, p0[0] + w0 / 2, p0[1] + w0 / 2],
                  fill=colour)
        d.ellipse([p1[0] - w1 / 2, p1[1] - w1 / 2, p1[0] + w1 / 2, p1[1] + w1 / 2],
                  fill=colour)


def _head_layer(img, centre, r, face, expression, mouth, hair_col=INK):
    """Head: shaded disc, ink outline, face, hair. Drawn in one piece."""
    shade, pos = _head_shading((0, 0), centre, r)
    img.alpha_composite(shade, pos)
    d = ImageDraw.Draw(img, "RGBA")
    cx, cy = centre
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=INK,
              width=max(3, int(r * 0.075)))

    # ---- hair: three short tapered strands on the crown
    for bx, tipx, tipy in ((-0.26, -0.40, -1.16), (-0.02, -0.02, -1.22),
                           (0.26, 0.42, -1.12)):
        _taper(d, (cx + bx * r, cy - 0.96 * r),
               (cx + tipx * r, cy + tipy * r),
               max(3, r * 0.085), max(2, r * 0.035), INK)

    # ---- eyes: small, black, with a highlight so they read alive
    ex_off = 0.33 * r * (1 - 0.28 * abs(face["turn"]))
    ey = cy - 0.06 * r
    erx, ery = 0.088 * r, 0.115 * r
    for side in (-1, 1):
        ex = cx + side * ex_off + face["turn"] * 0.16 * r
        if face["blink"]:
            d.line([(ex - erx, ey), (ex + erx, ey)], fill=INK, width=max(2, r * 0.05))
            continue
        d.ellipse([ex - erx, ey - ery, ex + erx, ey + ery], fill=INK)
        d.ellipse([ex - erx * 0.35 + erx * 0.25, ey - ery * 0.55,
                   ex + erx * 0.15, ey - ery * 0.05], fill=(255, 255, 255, 210))

    # ---- brows: tapered, angled by the expression
    brow = expression.get("brow", 0.0)
    for side in (-1, 1):
        bx = cx + side * ex_off + face["turn"] * 0.16 * r
        inner = (bx - side * 0.15 * r, ey - 0.28 * r + brow * 0.06 * r)
        outer = (bx + side * 0.16 * r, ey - 0.33 * r - brow * 0.10 * r)
        _taper(d, outer, inner, max(2, r * 0.055), max(2, r * 0.035), INK)

    # ---- nose: a small tick, only when the head is turned toward camera
    if abs(face["turn"]) < 0.5:
        nx = cx + face["turn"] * 0.20 * r
        _taper(d, (nx, cy + 0.09 * r), (nx + 0.045 * r, cy + 0.17 * r),
               max(2, r * 0.045), max(2, r * 0.03), INK_SOFT)

    # ---- mouth
    mx = cx + face["turn"] * 0.14 * r
    my = cy + 0.40 * r
    mw = 0.17 * r
    if mouth > 0.10:
        h = 0.06 * r + mouth * 0.20 * r
        d.ellipse([mx - mw, my - h * 0.35, mx + mw, my + h], fill=INK)
    elif expression.get("smile"):
        d.arc([mx - mw, my - 0.13 * r, mx + mw, my + 0.13 * r], 25, 155,
              fill=INK, width=max(2, r * 0.045))
    else:
        _taper(d, (mx - mw, my), (mx + mw, my), max(2, r * 0.045),
               max(2, r * 0.045), INK)

    # ---- rim light on the lit side
    rim = Image.new("RGBA", img.size, (0, 0, 0, 0))
    rd = ImageDraw.Draw(rim, "RGBA")
    rd.arc([cx - r - 1, cy - r - 1, cx + r + 1, cy + r + 1], 150, 265,
           fill=RIM + (200,), width=max(3, int(r * 0.10)))
    img.alpha_composite(rim.filter(ImageFilter.GaussianBlur(max(1, r * 0.03))))
    return img


def _head_shading(size, centre, r):
    """Radial shading for the head: lit upper-left, shaded lower-right."""
    w = h = int(2 * r) + 2
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    nx = (xx - w / 2) / (w / 2)
    ny = (yy - h / 2) / (h / 2)
    light = np.clip(0.62 - 0.5 * (nx * 0.55 + ny * 0.75), 0.0, 1.0)
    mask = np.clip(1.0 - (nx ** 2 + ny ** 2) * 0.98, 0, 1) ** 0.25
    shade = (np.array(SKIN)[None, None, :] * (1 - light[:, :, None] * 0.45)
             + np.array(SKIN_SHADE)[None, None, :] * (light[:, :, None] * 0.45))
    arr = np.dstack([np.clip(shade, 0, 255), (mask * 255)]).astype(np.uint8)
    img = Image.fromarray(arr, "RGBA")
    return img, (int(centre[0] - w / 2), int(centre[1] - h / 2))


HEAD_R, NECK_RISE, TORSO = 112, 92, 196
SHOULDER = 62
UPPER, FORE = 104, 96
THIGH, SHIN = 152, 152
FOOT_L, FOOT_H = 56, 22


def _joint(o, ang_deg, length, f=1):
    a = math.radians(ang_deg)
    return (o[0] + f * length * math.sin(a), o[1] + length * math.cos(a))


def draw_kairo(img, hip, s, wardrobe="suit", facing=1, turn=0.0, lean=0.0,
               arms=(14, 8, -12, -6), legs=(9, 4, -9, -4), expression=None,
               mouth=0.0, blink=False, prop=None, shadow=True):
    """Draw KAIRO standing with his hip at ``hip`` (device px).

    The whole skeleton is solved in body units and only converted to device
    pixels at draw time, so one scale factor controls everything.
    """
    expression = expression or {"brow": -2, "smile": True}
    d = ImageDraw.Draw(img, "RGBA")

    def D(p):
        return (hip[0] + p[0] * s, hip[1] + p[1] * s)

    def W(v):
        return max(2, int(round(v * s)))

    ground = hip[1] + (THIGH + SHIN + FOOT_H) * s
    if shadow:
        sw, sh = 240 * s, 26 * s
        d.ellipse([hip[0] - sw / 2, ground - sh / 2,
                   hip[0] + sw / 2, ground + sh / 2], fill=(0, 0, 0, 110))

    neck = (facing * TORSO * math.sin(math.radians(lean)) * 0.6, -TORSO)
    head_c = (neck[0] + facing * turn * 18, neck[1] - (NECK_RISE + HEAD_R * 0.86))
    sh_near = (neck[0] + facing * SHOULDER * 0.52, neck[1] + 12)
    sh_far = (neck[0] - facing * SHOULDER * 0.52, neck[1] + 16)
    hip_near = (facing * 18, 0)
    hip_far = (-facing * 18, 0)

    def arm(sh, a1, a2, colour, w0, w1):
        el = _joint(sh, a1, UPPER, facing)
        wr = _joint(el, a2, FORE, facing)
        _taper(d, D(sh), D(el), W(w0), W(w1), colour)
        _taper(d, D(el), D(wr), W(w1), W(w1 * 0.82), colour)
        return wr

    def leg(hp, a1, a2, colour, w0, w1):
        kn = _joint(hp, a1, THIGH, facing)
        an = _joint(kn, a2, SHIN, facing)
        _taper(d, D(hp), D(kn), W(w0), W(w1), colour)
        _taper(d, D(kn), D(an), W(w1), W(w1 * 0.8), colour)
        return an

    # far side sits behind the body mass
    limb_far = SUIT_LIGHT if wardrobe == "suit" else INK_SOFT
    limb_near = (52, 52, 60) if wardrobe == "suit" else INK
    arm(sh_far, arms[0], arms[1], limb_far, 30, 24)
    ankle_far = leg(hip_far, legs[0], legs[1], limb_far, 34, 26)

    # ---- wardrobe mass (unit space)
    if wardrobe == "suit":
        d.polygon([D((neck[0] - 66, neck[1] + 16)), D((neck[0] + 66, neck[1] + 16)),
                   D((66, 2)), D((-66, 2))], fill=SUIT)
        d.polygon([D((neck[0] - 60, neck[1] + 22)), D((neck[0] - 4, neck[1] + 24)),
                   D((neck[0] - 18, neck[1] + 100))], fill=SUIT_LIGHT)
        d.polygon([D((neck[0] + 60, neck[1] + 22)), D((neck[0] + 4, neck[1] + 24)),
                   D((neck[0] + 18, neck[1] + 100))], fill=SUIT_LIGHT)
        d.polygon([D((neck[0] - 19, neck[1] + 22)), D((neck[0] + 19, neck[1] + 22)),
                   D((neck[0] + 11, neck[1] + 108)), D((neck[0] - 11, neck[1] + 108))],
                  fill=SHIRT)
        d.polygon([D((neck[0] - 9, neck[1] + 34)), D((neck[0] + 9, neck[1] + 34)),
                   D((neck[0] + 7, neck[1] + 48)), D((neck[0] - 7, neck[1] + 48))],
                  fill=TIE)
        d.polygon([D((neck[0] - 6, neck[1] + 48)), D((neck[0] + 6, neck[1] + 48)),
                   D((neck[0] + 11, neck[1] + 104)), D((neck[0] - 11, neck[1] + 104))],
                  fill=TIE)
        rim_col = (255, 206, 140, 150)
        d.line([D((neck[0] - 66, neck[1] + 16)), D((-66, 2))], fill=rim_col, width=W(4))
        d.line([D((neck[0] - 66, neck[1] + 16)), D((neck[0] - 58, neck[1] + 70))],
               fill=rim_col, width=W(3))
        for uy in (-118, -86):
            d.ellipse([*D((-4, uy)), *D((4, uy + 8))], fill=(74, 74, 82, 255))
    else:
        d.polygon([D((neck[0] - 70, neck[1] + 14)), D((neck[0] + 70, neck[1] + 14)),
                   D((66, 96)), D((30, 80)), D((-8, 100)), D((-44, 78)),
                   D((-66, 96))], fill=HIDE)
        d.polygon([D((neck[0] - 70, neck[1] + 14)), D((neck[0] + 70, neck[1] + 14)),
                   D((neck[0] + 56, neck[1] + 46)), D((neck[0] - 56, neck[1] + 46))],
                  fill=HIDE_LIGHT)
        d.line([D((-60, 44)), D((60, 44))], fill=HIDE_DARK, width=W(9))
        d.line([D((neck[0] - 70, neck[1] + 14)), D((-66, 96))],
               fill=(255, 216, 150, 170), width=W(5))
        d.line([D((neck[0] - 70, neck[1] + 14)), D((neck[0] - 56, neck[1] + 46))],
               fill=(255, 216, 150, 150), width=W(4))
        d.line([D((neck[0] - 38, neck[1] + 20)), D((-12, 44))], fill=HIDE_DARK,
               width=W(6))

    # ---- near side
    ankle_near = leg(hip_near, legs[2], legs[3], limb_near, 36, 28)
    wrist_near = arm(sh_near, arms[2], arms[3], limb_near, 32, 26)

    # ---- feet
    for an, colour in ((ankle_near, INK), (ankle_far, (24, 24, 28))):
        ax, ay = D(an)
        if wardrobe == "suit":
            d.rounded_rectangle([ax - FOOT_L * s * 0.42, ay - FOOT_H * s * 0.15,
                                 ax + FOOT_L * s * 0.62, ay + FOOT_H * s],
                                radius=FOOT_H * s * 0.5, fill=colour)
            d.line([(ax - FOOT_L * s * 0.32, ay + FOOT_H * s * 0.85),
                    (ax + FOOT_L * s * 0.54, ay + FOOT_H * s * 0.85)],
                   fill=(80, 74, 68), width=W(3))
        else:
            d.ellipse([ax - FOOT_L * s * 0.40, ay - FOOT_H * s * 0.40,
                       ax + FOOT_L * s * 0.56, ay + FOOT_H * s * 0.95],
                      fill=SKIN, outline=INK, width=W(4))

    # ---- near hand
    wx, wy = D(wrist_near)
    d.ellipse([wx - 13 * s, wy - 13 * s, wx + 13 * s, wy + 13 * s],
              fill=(58, 58, 66) if wardrobe == "suit" else SKIN,
              outline=None if wardrobe == "suit" else INK,
              width=0 if wardrobe == "suit" else W(4))

    # ---- spear
    if prop == "spear":
        top = (wx + facing * 8 * s, wy - 420 * s)
        bot = (wx - facing * 10 * s, wy + 220 * s)
        _taper(d, bot, top, W(10), W(8), (120, 84, 48))
        _taper(d, top, (top[0] + facing * 3 * s, top[1] - 46 * s),
               W(15), W(2), (228, 222, 208))

    face = {"turn": turn, "blink": blink}
    _head_layer(img, D(head_c), HEAD_R * s, face, expression, mouth)
    return img


# ------------------------------------------------------------------ sheet
def _plate(w, h):
    """Dark room plate: warm lamp glow, floor, vignette, grain."""
    yy = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    top = np.array([16, 15, 19], np.float32)
    bottom = np.array([9, 8, 10], np.float32)
    arr = np.repeat((top * (1 - yy) + bottom * yy)[:, None, :], w, axis=1)
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB").convert("RGBA")
    d = ImageDraw.Draw(img, "RGBA")
    floor = int(h * 0.845)
    d.rectangle([0, floor, w, h], fill=(16, 14, 14, 255))
    d.line([(0, floor), (w, floor)], fill=(56, 46, 38, 255), width=int(h * 0.004))

    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow, "RGBA")
    gd.ellipse([-w * 0.10, h * 0.18, w * 0.42, h * 0.86], fill=(255, 186, 104, 46))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(h * 0.06)))

    # dust motes
    rng = np.random.default_rng(4)
    for _ in range(140):
        x, y = rng.uniform(0, w), rng.uniform(0, floor)
        r = rng.uniform(0.6, 2.6) * (h / 1350)
        a = int(rng.uniform(20, 90))
        d.ellipse([x, y, x + r, y + r], fill=(206, 200, 190, a))

    vig = Image.new("L", (w, h), 0)
    vd = ImageDraw.Draw(vig)
    vd.ellipse([-w * 0.25, -h * 0.35, w * 1.25, h * 1.35], fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(w * 0.10))
    dark = Image.new("RGBA", (w, h), (0, 0, 0, 190))
    img = Image.composite(img, Image.alpha_composite(img, dark), vig)
    return img


def _caption(d, xy, text, size):
    from bidi.algorithm import get_display
    import arabic_reshaper
    from PIL import ImageFont
    font = ImageFont.truetype(
        "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf", size)
    shown = get_display(arabic_reshaper.reshape(text))
    d.text(xy, shown, font=font, fill=(226, 214, 196, 235), anchor="ma")


def character_sheet(path="out/character_kairo_v2.png"):
    """Three approved views on one plate."""
    from pathlib import Path
    W0, H0 = 2400, 1350
    w, h = W0 * SS, H0 * SS
    img = _plate(w, h)
    floor = int(h * 0.845)

    warm = {"brow": -3, "smile": True}
    alert = {"brow": 4, "smile": False}

    # 1) present day, full body, front
    s1 = 2.45                      # device px per body unit
    hip1 = (w * 0.20, floor - (THIGH + SHIN + FOOT_H) * s1)
    draw_kairo(img, hip1, s1, "suit", facing=1, turn=-0.05, lean=2,
               arms=(16, 10, 34, 58), legs=(10, 4, -12, -5),
               expression=warm, mouth=0.35)

    # 2) prehistoric, three-quarter, spear
    s2 = 2.45
    hip2 = (w * 0.50, floor - (THIGH + SHIN + FOOT_H) * s2)
    draw_kairo(img, hip2, s2, "hide", facing=1, turn=0.35, lean=4,
               arms=(24, 30, 40, 62), legs=(14, 6, -16, -6),
               expression=alert, mouth=0.0, prop="spear")

    # 3) close-up head, inset
    s3 = 3.30
    inset_r = int(HEAD_R * s3 * 1.42)
    cx, cy = w * 0.80, h * 0.34
    d = ImageDraw.Draw(img, "RGBA")
    d.ellipse([cx - inset_r, cy - inset_r, cx + inset_r, cy + inset_r],
              fill=(24, 21, 22, 255), outline=(150, 122, 86, 255), width=int(4 * SS))
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    _head_layer(layer, (cx, cy), HEAD_R * s3,
                {"turn": 0.12, "blink": False}, warm, 0.25)
    box = (int(cx - inset_r), int(cy - inset_r),
           int(cx + inset_r), int(cy + inset_r))
    region = layer.crop(box)
    mask = Image.new("L", region.size, 0)
    ImageDraw.Draw(mask).ellipse([5, 5, region.size[0] - 5, region.size[1] - 5],
                                 fill=255)
    region.putalpha(ImageChops.multiply(region.split()[3], mask))
    img.alpha_composite(region, (box[0], box[1]))

    d = ImageDraw.Draw(img, "RGBA")
    _caption(d, (hip1[0], h * 0.925), "امروز — کت‌وشلوار", 34 * SS)
    _caption(d, (hip2[0], h * 0.925), "۲۰۰ هزار سال پیش — پوستین", 34 * SS)
    _caption(d, (cx, cy + inset_r + 44 * SS), "کلوزآپ چهره", 32 * SS)

    out = img.convert("RGB").resize((W0, H0), Image.LANCZOS)
    from .config import ROOT
    target = Path(path)
    if not target.is_absolute():
        target = ROOT / target
    target.parent.mkdir(parents=True, exist_ok=True)
    out.save(target)
    return target


