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


def _w(v):
    """Integer stroke width (Pillow rejects float widths)."""
    return max(2, int(round(v)))


def _head_layer(img, centre, r, face, expression, mouth, hair_col=INK):
    """Head: shaded disc, ink outline, face, hair. Drawn in one piece."""
    cx, cy = centre
    ImageDraw.Draw(img, "RGBA").ellipse([cx - r, cy - r, cx + r, cy + r],
                                        fill=SKIN)
    shade, pos = _head_shading((0, 0), centre, r)
    img.alpha_composite(shade, pos)
    d = ImageDraw.Draw(img, "RGBA")
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
            d.line([(ex - erx, ey), (ex + erx, ey)], fill=INK, width=_w(r * 0.05))
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
        _taper(d, outer, inner, _w(r * 0.055), _w(r * 0.035), INK)

    # ---- nose: a small tick, only when the head is turned toward camera
    if abs(face["turn"]) < 0.5:
        nx = cx + face["turn"] * 0.20 * r
        _taper(d, (nx, cy + 0.09 * r), (nx + 0.045 * r, cy + 0.17 * r),
               _w(r * 0.045), _w(r * 0.03), INK_SOFT)

    # ---- mouth
    mx = cx + face["turn"] * 0.14 * r
    my = cy + 0.40 * r
    mw = 0.17 * r
    if mouth > 0.10:
        h = 0.06 * r + mouth * 0.20 * r
        d.ellipse([mx - mw, my - h * 0.35, mx + mw, my + h], fill=INK)
    elif expression.get("smile"):
        d.arc([mx - mw, my - 0.13 * r, mx + mw, my + 0.13 * r], 25, 155,
              fill=INK, width=_w(r * 0.045))
    else:
        _taper(d, (mx - mw, my), (mx + mw, my), _w(r * 0.045),
               _w(r * 0.045), INK)

    # ---- rim light on the lit side
    rim = Image.new("RGBA", img.size, (0, 0, 0, 0))
    rd = ImageDraw.Draw(rim, "RGBA")
    rr = r * 0.945
    rd.arc([cx - rr, cy - rr, cx + rr, cy + rr], 150, 262,
           fill=RIM + (150,), width=max(2, int(r * 0.045)))
    img.alpha_composite(rim.filter(ImageFilter.GaussianBlur(max(1, r * 0.012))))
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
NECK_VIS = 22          # chin-to-shoulder gap: the visible neck
TOTAL_H = TORSO + NECK_VIS + HEAD_R * 1.86 + THIGH + SHIN + FOOT_H


def _joint(o, ang_deg, length, f=1):
    a = math.radians(ang_deg)
    return (o[0] + f * length * math.sin(a), o[1] + length * math.cos(a))



def _suit(d, D, W, neck, facing):
    """Black business suit: tailored jacket, shirt V, tie, lapels, buttons."""
    nx = neck[0]
    sh_y = neck[1] + 16
    sh = 56                      # half shoulder width
    waist, hem = 46, 54          # half widths at waist and jacket hem

    body = [D((nx - sh, sh_y)), D((nx + sh, sh_y)), D((waist, -74)),
            D((hem, 6)), D((hem * 0.42, 12)), D((-hem * 0.42, 12)),
            D((-hem, 6)), D((-waist, -74))]
    d.polygon(body, fill=SUIT, outline=INK, width=W(4))

    # shirt front: a narrow V down to the tie knot, with a small collar
    d.polygon([D((nx - 16, sh_y + 2)), D((nx + 16, sh_y + 2)),
               D((nx + 5, neck[1] + 96)), D((nx - 5, neck[1] + 96))],
              fill=SHIRT)
    for side in (-1, 1):
        d.polygon([D((nx + side * 6, sh_y - 6)), D((nx + side * 17, sh_y + 2)),
                   D((nx + side * 6, sh_y + 14))], fill=(228, 224, 214))

    # tie: knot + tapered blade
    d.polygon([D((nx - 9, sh_y + 8)), D((nx + 9, sh_y + 8)),
               D((nx + 6, sh_y + 26)), D((nx - 6, sh_y + 26))], fill=TIE)
    d.polygon([D((nx - 7, sh_y + 26)), D((nx + 7, sh_y + 26)),
               D((nx + 5, neck[1] + 104)), D((nx - 5, neck[1] + 104))],
              fill=TIE)

    # lapels read as two seam lines, not as a filled wedge
    for side in (-1, 1):
        d.line([D((nx + side * 15, sh_y + 2)),
                D((nx + side * 31, sh_y + 74))],
               fill=(72, 70, 78, 235), width=max(1, W(2)))
        d.line([D((nx + side * 15, sh_y + 2)),
                D((nx + side * 7, sh_y + 30))],
               fill=(72, 70, 78, 235), width=max(1, W(2)))

    # buttons
    for uy in (neck[1] + 86, neck[1] + 120):
        d.ellipse([*D((-4, uy)), *D((4, uy + 8))], fill=(78, 78, 86, 255))

    # hem shadow + warm rim on the lamp side
    d.polygon([D((-hem, -2)), D((hem, -2)), D((hem, 6)), D((-hem, 6))],
              fill=(12, 12, 15, 255))


def _hide_tunic(d, D, W, neck, facing):
    """Prehistoric animal-hide tunic: ragged hem, belt, strap, stitching."""
    nx = neck[0]
    sh_y = neck[1] + 16
    sh = 54
    hem_y, hem_w = 108, 66

    # ragged lower edge so the hide never reads as a rectangle
    hem = [(nx + hem_w, sh_y + 54),
           (nx + hem_w * 0.90, hem_y),
           (nx + hem_w * 0.60, hem_y - 14),
           (nx + hem_w * 0.30, hem_y + 2),
           (nx - 2, hem_y - 12),
           (nx - hem_w * 0.32, hem_y + 2),
           (nx - hem_w * 0.64, hem_y - 15),
           (nx - hem_w * 0.92, hem_y),
           (nx - hem_w, sh_y + 54)]
    tunic = ([D((nx - sh, sh_y)), D((nx + sh, sh_y)),
              D((nx + hem_w * 0.94, sh_y + 44))] + [D(p) for p in hem]
             + [D((nx - hem_w * 0.94, sh_y + 44))])
    d.polygon(tunic, fill=HIDE, outline=(52, 34, 20), width=W(4))

    # soft lit side, so the hide has form without a hard panel edge
    d.polygon([D((nx - sh + 4, sh_y + 3)), D((nx - sh * 0.30, sh_y + 3)),
               D((nx - hem_w * 0.30, hem_y - 6)), D((nx - hem_w * 0.86, hem_y - 6)),
               D((nx - hem_w * 0.80, sh_y + 44))], fill=HIDE_LIGHT + (34,))

    # neck opening
    d.polygon([D((nx - 15, sh_y - 2)), D((nx + 15, sh_y - 2)),
               D((nx, sh_y + 26))], fill=(76, 52, 32, 240))

    # shoulder strap crossing the chest, under the belt
    d.polygon([D((nx - sh + 8, sh_y + 2)), D((nx - sh + 20, sh_y + 2)),
               D((nx + 22, sh_y + 54)), D((nx + 6, sh_y + 54))],
              fill=HIDE_DARK)

    # belt + knot
    by = sh_y + 54
    d.rectangle([*D((-hem_w + 4, by)), *D((hem_w - 4, by + 12))],
                fill=(70, 46, 26))
    d.rectangle([*D((-8, by - 3)), *D((8, by + 15))], fill=(96, 66, 40),
                outline=(52, 34, 20), width=max(1, W(2)))
def _tube(d, pts, widths, fill):
    """Draw a tapered polyline as ONE silhouette, so joints show no seams.

    Stroking each segment separately leaves an ink ring at every knee and elbow;
    building the outline once and filling it once keeps the limb continuous.
    """
    n = len(pts)
    seg_n = []
    for i in range(n - 1):
        dx, dy = pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]
        length = math.hypot(dx, dy) or 1.0
        seg_n.append((-dy / length, dx / length))
    vert_n = []
    for j in range(n):
        if j == 0:
            vx, vy = seg_n[0]
        elif j == n - 1:
            vx, vy = seg_n[-1]
        else:
            ax, ay = seg_n[j - 1]
            bx, by = seg_n[j]
            vx, vy = ax + bx, ay + by
            length = math.hypot(vx, vy) or 1.0
            vx, vy = vx / length, vy / length
        vert_n.append((vx, vy))
    left, right = [], []
    for j in range(n):
        hw = widths[j] / 2.0
        left.append((pts[j][0] + vert_n[j][0] * hw, pts[j][1] + vert_n[j][1] * hw))
        right.append((pts[j][0] - vert_n[j][0] * hw, pts[j][1] - vert_n[j][1] * hw))
    d.polygon(left + right[::-1], fill=fill)
    for j in (0, n - 1):
        rr = widths[j] / 2.0
        d.ellipse([pts[j][0] - rr, pts[j][1] - rr,
                   pts[j][0] + rr, pts[j][1] + rr], fill=fill)


def draw_kairo(img, hip, s, wardrobe="suit", facing=1, turn=0.0, lean=0.0,
               arms=(14, 8, -12, -6), legs=(9, 4, -9, -4), expression=None,
               mouth=0.0, blink=False, prop=None, shadow=True):
    """Draw KAIRO standing with his hip at ``hip`` (device px).

    The skeleton is solved in body units and converted to device pixels only at
    draw time, so one scale factor controls the whole figure. Every limb is laid
    down as a single inked silhouette, and limbs are drawn before the wardrobe
    so a hanging arm sits behind the jacket or tunic instead of on top of it.
    """
    expression = expression or {"brow": -2, "smile": True}
    d = ImageDraw.Draw(img, "RGBA")

    def D(p):
        return (hip[0] + p[0] * s, hip[1] + p[1] * s)

    def W(v):
        return max(2, int(round(v * s)))

    ground = hip[1] + (THIGH + SHIN + FOOT_H) * s
    if shadow:
        sw, sh = 250 * s, 24 * s
        d.ellipse([hip[0] - sw / 2, ground - sh / 2,
                   hip[0] + sw / 2, ground + sh / 2], fill=(0, 0, 0, 115))

    neck = (facing * TORSO * math.sin(math.radians(lean)) * 0.6, -TORSO)
    head_c = (neck[0] + facing * turn * 18,
              neck[1] - (NECK_VIS + HEAD_R * 0.86))
    sh_near = (neck[0] + facing * SHOULDER * 0.80, neck[1] + 42)
    sh_far = (neck[0] - facing * SHOULDER * 0.80, neck[1] + 44)
    hip_near = (facing * 16, 0)
    hip_far = (-facing * 16, 0)

    suit = wardrobe == "suit"
    limb_far = (28, 28, 33) if suit else (56, 48, 42)
    limb_near = (36, 36, 43) if suit else (44, 37, 31)
    INK_W = W(6)

    def chain(p0, mid, p1, w0, w1, w2, fill):
        pts = [D(p0), D(mid), D(p1)]
        ws = [W(w0), W(w1), W(w2)]
        _tube(d, pts, [w + INK_W for w in ws], INK)
        _tube(d, pts, ws, fill)

    def elbow_of(sh, a1):
        return _joint(sh, a1, UPPER, facing)

    def wrist_of(sh, a1, a2):
        return _joint(elbow_of(sh, a1), a2, FORE, facing)

    def arm(sh, a1, a2, colour, w0, w1):
        el = elbow_of(sh, a1)
        wr = wrist_of(sh, a1, a2)
        chain(sh, el, wr, w0, w1, w1 * 0.84, colour)
        return el, wr

    def leg(hp, a1, a2, colour, w0, w1):
        kn = _joint(hp, a1, THIGH, facing)
        an = _joint(kn, a2, SHIN, facing)
        chain(hp, kn, an, w0, w1, w1 * 0.78, colour)
        return an

    wrist_near = wrist_of(sh_near, arms[2], arms[3])

    # ---- both legs and both arms, behind the wardrobe
    ankle_far = leg(hip_far, legs[0], legs[1], limb_far, 34, 27)
    ankle_near = leg(hip_near, legs[2], legs[3], limb_near, 36, 29)
    _, wrist_far = arm(sh_far, arms[0], arms[1], limb_far, 30, 25)
    _, wrist = arm(sh_near, arms[2], arms[3], limb_near, 32, 27)

    # ---- neck, under the collar
    _tube(d, [D((neck[0], neck[1] - 6)),
              D((neck[0] + facing * turn * 4, neck[1] - NECK_VIS * 0.55)),
              D((head_c[0] - facing * turn * 10, head_c[1] + HEAD_R * 0.95))],
          [W(36), W(38), W(44)], SKIN)

    # ---- wardrobe mass over the neck and shoulders
    if suit:
        _suit(d, D, W, neck, facing)
    else:
        _hide_tunic(d, D, W, neck, facing)

    # ---- spear: held at the wrist, angled forward so the tip clears the head
    if prop == "spear":
        wx, wy = D(wrist_near)
        top = (wx + facing * 62 * s, wy - 430 * s)
        bot = (wx - facing * 30 * s, wy + 150 * s)
        _taper(d, bot, top, W(13), W(11), (52, 34, 20))
        _taper(d, bot, top, W(8), W(7), (128, 88, 50))
        _taper(d, (top[0] + facing * 4 * s, top[1] + 6 * s),
               (top[0] + facing * 26 * s, top[1] - 62 * s),
               W(16), W(2), (226, 220, 206))


    # ---- feet
    foot_len = 74 * s
    for ankle, colour in ((ankle_near, (30, 30, 36) if suit else SKIN),
                          (ankle_far, (24, 24, 30) if suit else SKIN)):
        ax, ay = D(ankle)
        top_y = ay - FOOT_H * s * 0.10
        bot_y = ay + FOOT_H * s * 1.06
        if suit:
            front = ax + facing * 0.66 * foot_len
            back = ax - facing * 0.34 * foot_len
            d.rounded_rectangle([min(front, back), top_y, max(front, back), bot_y],
                                radius=FOOT_H * s * 0.6, fill=colour,
                                outline=INK, width=W(4))
            d.line([(min(front, back) + foot_len * 0.08, bot_y - FOOT_H * s * 0.14),
                    (max(front, back) - foot_len * 0.08, bot_y - FOOT_H * s * 0.14)],
                   fill=(88, 82, 76), width=W(3))
        else:
            front = ax + facing * 0.58 * foot_len
            back = ax - facing * 0.32 * foot_len
            d.ellipse([min(front, back), ay - FOOT_H * s * 0.30,
                       max(front, back), bot_y],
                      fill=colour, outline=INK, width=W(4))

    # ---- hands
    fx, fy = D(wrist_far)
    d.ellipse([fx - 13 * s, fy - 12 * s, fx + 13 * s, fy + 13 * s],
              fill=SKIN_SHADE, outline=INK, width=W(4))
    hx, hy = D(wrist)
    d.ellipse([hx - 14 * s, hy - 13 * s, hx + 14 * s, hy + 14 * s],
              fill=SKIN, outline=INK, width=W(4))

    _head_layer(img, D(head_c), HEAD_R * s, {"turn": turn, "blink": blink},
                expression, mouth)
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


def character_sheet_v2(path="out/character_kairo_v2.png"):
    """First-pass three-view plate (kept for comparison with rev 03)."""
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
    _caption(d, (hip2[0], h * 0.925), "۲۰۰ هزار سال پیش، پوستین", 34 * SS)
    _caption(d, (cx, cy + inset_r + 44 * SS), "کلوزآپ چهره", 32 * SS)

    out = img.convert("RGB").resize((W0, H0), Image.LANCZOS)
    from .config import ROOT
    target = Path(path)
    if not target.is_absolute():
        target = ROOT / target
    target.parent.mkdir(parents=True, exist_ok=True)
    out.save(target)
    return target


# ------------------------------------------------------------------ typesetting
_AR_REG = "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf"
_AR_BOLD = "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Bold.ttf"
_SERIF = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"
_SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
_MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"

_ARABIC = set(range(0x0620, 0x064B)) | set(range(0x066E, 0x06D4))
_FONTS: dict = {}
_RAQM = None


def _font(path: str, size: float):
    from PIL import ImageFont
    key = (path, int(round(size)))
    if key not in _FONTS:
        _FONTS[key] = ImageFont.truetype(path, key[1])
    return _FONTS[key]


def _has_raqm() -> bool:
    global _RAQM
    if _RAQM is None:
        from PIL import features
        _RAQM = bool(features.check("raqm"))
    return _RAQM


def fa(text: str) -> str:
    """Return Persian text ready for Pillow, shaped exactly once.

    Two environments exist and they must not be confused:

    * Pillow built with **libraqm** shapes and bidi-reorders by itself when the
      text is drawn with ``direction="rtl"``. Passing it pre-shaped text makes
      HarfBuzz process the presentation forms a second time, which reverses the
      line and de-joins every letter — the exact bug in rev 02.
    * Pillow without Raqm has no complex-text engine at all, so the text must be
      shaped by ``arabic_reshaper`` and reordered by ``python-bidi`` first.

    This returns the raw string when Raqm is present, and the joined,
    right-to-left string when it is not.
    """
    if _has_raqm():
        return text
    import arabic_reshaper
    from bidi.algorithm import get_display

    shaped = arabic_reshaper.reshape(text)
    if any(ord(ch) in _ARABIC for ch in text):
        if not any(0xFE70 <= ord(ch) <= 0xFEFF for ch in shaped):
            raise RuntimeError(f"Persian shaping produced no joined forms: {text!r}")
    return get_display(shaped)


def _fa(d, xy, text, size, fill, bold=False, anchor="ma"):
    font = _font(_AR_BOLD if bold else _AR_REG, size)
    if _has_raqm():
        d.text(xy, text, font=font, fill=fill, anchor=anchor,
               direction="rtl", language="fa")
    else:
        d.text(xy, fa(text), font=font, fill=fill, anchor=anchor)



def _tracked(d, xy, text, size, fill, tracking=0.0, anchor="ls", path=_SANS):
    """Latin text with letter-spacing (Pillow has no tracking option)."""
    font = _font(path, size)
    gaps = [d.textlength(ch, font=font) for ch in text]
    total = sum(gaps) + tracking * max(0, len(text) - 1)
    x, y = xy
    if anchor[0] == "m":
        x -= total / 2
    elif anchor[0] == "r":
        x -= total
    for ch, gap in zip(text, gaps):
        d.text((x, y), ch, font=font, fill=fill, anchor="l" + anchor[1])
        x += gap + tracking


def _sheet_plate(w: int, h: int, floor: int):
    """Reference-sheet backdrop: warm lamp light left, cool separation right."""
    yy = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    top = np.array([19, 18, 22], np.float32)
    bottom = np.array([10, 9, 11], np.float32)
    arr = np.repeat((top * (1 - yy) + bottom * yy)[:, None, :], w, axis=1)
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB").convert("RGBA")

    warm = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(warm, "RGBA").ellipse(
        [-w * 0.10, h * 0.16, w * 0.44, h * 0.92], fill=(255, 178, 96, 40))
    img.alpha_composite(warm.filter(ImageFilter.GaussianBlur(h * 0.07)))

    cool = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(cool, "RGBA").ellipse(
        [w * 0.60, h * 0.10, w * 1.15, h * 0.85], fill=(74, 118, 168, 30))
    img.alpha_composite(cool.filter(ImageFilter.GaussianBlur(h * 0.08)))

    d = ImageDraw.Draw(img, "RGBA")
    d.rectangle([0, floor, w, h], fill=(15, 14, 15, 255))
    d.line([(0, floor), (w, floor)], fill=(62, 50, 40, 255), width=int(h * 0.0035))
    d.line([(0, floor + h * 0.005), (w, floor + h * 0.005)],
           fill=(30, 26, 24, 200), width=int(h * 0.002))

    rng = np.random.default_rng(7)
    for _ in range(220):
        x, y = rng.uniform(0, w), rng.uniform(0, floor)
        r = rng.uniform(0.5, 2.4) * (h / 1440)
        d.ellipse([x, y, x + r, y + r],
                  fill=(212, 204, 192, int(rng.uniform(14, 70))))

    vig = Image.new("L", (w, h), 0)
    ImageDraw.Draw(vig).ellipse([-w * 0.20, -h * 0.30, w * 1.20, h * 1.30], fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(w * 0.09))
    dark = Image.new("RGBA", (w, h), (0, 0, 0, 175))
    return Image.composite(img, Image.alpha_composite(img, dark), vig)


def _head_inset(img, centre, r, face, expression, mouth, ring=True):
    """Composite a cropped, circular head into ``img`` at ``centre``."""
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    _head_layer(layer, centre, r, face, expression, mouth)
    box = (int(centre[0] - r), int(centre[1] - r),
           int(centre[0] + r), int(centre[1] + r))
    region = layer.crop(box)
    mask = Image.new("L", region.size, 0)
    ImageDraw.Draw(mask).ellipse([2, 2, region.size[0] - 2, region.size[1] - 2],
                                 fill=255)
    region.putalpha(ImageChops.multiply(region.split()[3], mask))
    img.alpha_composite(region, (box[0], box[1]))
    if ring:
        d = ImageDraw.Draw(img, "RGBA")
        d.ellipse([box[0], box[1], box[2], box[3]], outline=(146, 116, 78, 200),
                  width=max(2, int(r * 0.012)))
    return img
# ------------------------------------------------------------------ rev 03 sheet
_PALETTE = (
    ("suit", SUIT), ("shirt", SHIRT), ("tie", TIE), ("hide", HIDE),
    ("hide dark", HIDE_DARK), ("skin", SKIN), ("rim", RIM),
)

# label, brow, smile, mouth opening, head turn  — the six approved expressions
_EXPRESSIONS = (
    ("گرم", -3, True, 0.0, 0.05),
    ("متفکر", -1, False, 0.0, 0.20),
    ("کنجکاو", 3, False, 0.0, -0.24),
    ("هوشیار", 5, False, 0.0, 0.30),
    ("ترس", -6, False, 0.55, -0.10),
    ("مصمم", 6, False, 0.0, 0.10),
)


def character_sheet(path="out/character_kairo_v3_sheet.png"):
    """Rev 03 character reference: continuity views, face detail, expressions.

    One plate an illustrator or an image model can work from: the locked
    wardrobe of each timeline at one identical scale on one floor line, a large
    face detail, the six approved expressions, the palette in hex, and a
    proportion ruler measured in body units.
    """
    from pathlib import Path

    W0, H0 = 2560, 1440
    w, h = W0 * SS, H0 * SS
    floor = int(h * 0.800)
    img = _sheet_plate(w, h, floor)
    d = ImageDraw.Draw(img, "RGBA")

    height_px = 780.0                            # same for every view, always
    s = height_px * SS / TOTAL_H
    base = floor - (THIGH + SHIN + FOOT_H) * s
    hipA = (w * 0.125, base)
    hipB = (w * 0.285, base)
    hipC = (w * 0.445, base)

    warm = {"brow": -3, "smile": True}
    alert = {"brow": 5, "smile": False}

    # 1) present day — black suit, key light from the floor lamp
    draw_kairo(img, hipA, s, "suit", facing=1, turn=-0.03, lean=1,
               arms=(-9, -5, 7, 2), legs=(-9, -3, 11, 4),
               expression=warm, mouth=0.30)
    # 2) 200,000 years ago — hide tunic, three-quarter, spear
    draw_kairo(img, hipB, s, "hide", facing=1, turn=0.34, lean=3,
               arms=(-13, -7, 13, 19), legs=(-11, -4, 13, 5),
               expression=alert, mouth=0.0, prop="spear")
    # 3) the cave — same hide, cool rim light, turned away from the lens
    draw_kairo(img, hipC, s, "hide", facing=-1, turn=-0.36, lean=-2,
               arms=(-12, -6, 10, 4), legs=(10, 4, -12, -4),
               expression={"brow": 2, "smile": False}, mouth=0.0)

    # ---- header
    _tracked(d, (w * 0.047, h * 0.126), "KAIRO", 120 * SS,
             (243, 234, 217, 255), tracking=22 * SS, anchor="ls", path=_SERIF)
    d.line([(w * 0.047, h * 0.145), (w * 0.395, h * 0.145)],
           fill=(126, 100, 70, 190), width=max(1, int(2.5 * SS)))
    _tracked(d, (w * 0.047, h * 0.170), "CHARACTER REFERENCE  ·  EPISODE 01",
             22 * SS, (176, 164, 146, 235), tracking=5 * SS, anchor="ls",
             path=_MONO)
    _fa(d, (w * 0.047, h * 0.188), "کایرو، مردی که زمان را شکست داد",
        40 * SS, (236, 225, 208, 255), bold=True, anchor="la")
    _tracked(d, (w * 0.953, h * 0.076), "REV 03  ·  2560x1440  ·  16:9",
             22 * SS, (128, 120, 110, 220), tracking=3 * SS, anchor="rs",
             path=_MONO)

    # ---- divider between the views and the detail column
    d.line([(w * 0.578, h * 0.190), (w * 0.578, floor - h * 0.010)],
           fill=(78, 68, 58, 150), width=max(1, int(1.6 * SS)))

    # ---- face detail
    inset_c = (w * 0.775, h * 0.315)
    _head_inset(img, inset_c, 232 * SS, {"turn": 0.14, "blink": False},
                warm, 0.26)
    _fa(d, (inset_c[0], h * 0.520), "جزئیات چهره", 38 * SS,
        (214, 202, 184, 245), bold=True)

    # ---- expression strip
    for i, (label, brow, smile, mouth, turn) in enumerate(_EXPRESSIONS):
        cx = w * (0.641 + i * 0.0645)
        cy = h * 0.610
        _head_inset(img, (cx, cy), 46 * SS, {"turn": turn, "blink": False},
                    {"brow": brow, "smile": smile}, mouth, ring=False)
        _fa(d, (cx, cy + 56 * SS), label, 30 * SS, (214, 202, 184, 250))

    # ---- palette
    _fa(d, (w * 0.641, h * 0.700), "پالت رنگ", 32 * SS, (176, 164, 146, 235),
        anchor="la")
    for i, (name, col) in enumerate(_PALETTE):
        x = w * (0.641 + i * 0.052)
        y = h * 0.728
        d.rectangle([x, y, x + 52 * SS, y + 52 * SS], fill=col,
                    outline=(120, 104, 84, 200), width=max(1, int(2 * SS)))
        _tracked(d, (x, y + 74 * SS), name.upper(), 15 * SS,
                 (150, 140, 126, 225), tracking=1.0 * SS, anchor="ls",
                 path=_MONO)
        _tracked(d, (x, y + 97 * SS), "#%02X%02X%02X" % col, 15 * SS,
                 (118, 110, 100, 210), tracking=0.4 * SS, anchor="ls",
                 path=_MONO)

    # ---- proportion ruler, measured in body units off the first view
    rx = w * 0.028
    head_top = hipA[1] - (TORSO + NECK_VIS + HEAD_R * 1.86) * s
    marks = (
        (head_top, "HEAD TOP"),
        (hipA[1] - (TORSO + NECK_RISE - HEAD_R * 0.14) * s, "CHIN"),
        (hipA[1] - (TORSO - 14) * s, "SHOULDER"),
        (hipA[1], "HIP"),
        (hipA[1] + THIGH * s, "KNEE"),
    )
    d.line([(rx, head_top), (rx, floor)], fill=(92, 84, 74, 160),
           width=max(1, int(1.6 * SS)))
    d.line([(rx - 8 * SS, head_top), (rx + 8 * SS, head_top)],
           fill=(152, 142, 128, 220), width=max(1, int(2 * SS)))
    for y, label in marks[1:]:
        d.line([(rx - 7 * SS, y), (rx + 7 * SS, y)],
               fill=(152, 142, 128, 220), width=max(1, int(2 * SS)))
        _tracked(d, (rx + 15 * SS, y), label, 15 * SS,
                 (146, 136, 122, 210), tracking=1.3 * SS, anchor="lm",
                 path=_MONO)
    _tracked(d, (rx + 15 * SS, head_top + 8 * SS), "838 U", 17 * SS,
             (176, 160, 134, 225), tracking=1.3 * SS, anchor="lm", path=_MONO)

    # ---- captions under the floor line
    _fa(d, (hipA[0], h * 0.848), "امروز، کت‌وشلوار مشکی", 36 * SS,
        (228, 216, 198, 250), bold=True)
    _fa(d, (hipB[0], h * 0.848), "۲۰۰ هزار سال پیش، پوستین", 36 * SS,
        (228, 216, 198, 250), bold=True)
    _fa(d, (hipC[0], h * 0.848), "داخل غار، نور سرد", 36 * SS,
        (228, 216, 198, 250), bold=True)
    _fa(d, (hipB[0], h * 0.902),
        "چهره، نسبت‌ها، مدل مو و فرم بدن در هر ۲۵ صحنه یکسان است؛", 29 * SS,
        (168, 156, 140, 235))
    _fa(d, (hipB[0], h * 0.944),
        "فقط پوشش با خط زمانی عوض می‌شود. در گذشته پاها بدون کفش است.", 29 * SS,
        (168, 156, 140, 235))

    out = img.convert("RGB").resize((W0, H0), Image.LANCZOS)
    from .config import ROOT
    target = Path(path)
    if not target.is_absolute():
        target = ROOT / target
    target.parent.mkdir(parents=True, exist_ok=True)
    out.save(target)
    return target


def hero_reference(path="out/character_kairo_reference.png"):
    """The single seed image: one clean KAIRO on a plate, no text, no props.

    Every scene prompt is fed this image so the character cannot drift.
    """
    from pathlib import Path

    W0, H0 = 1920, 1080
    w, h = W0 * SS, H0 * SS
    floor = int(h * 0.845)
    img = _sheet_plate(w, h, floor)

    s = (h * 0.82) / TOTAL_H
    hip = (w * 0.5, floor - (THIGH + SHIN + FOOT_H) * s)
    draw_kairo(img, hip, s, "suit", facing=1, turn=0.0, lean=0,
               arms=(-9, -5, 7, 2), legs=(-9, -3, 11, 4),
               expression={"brow": -2, "smile": True}, mouth=0.22)

    out = img.convert("RGB").resize((W0, H0), Image.LANCZOS)
    from .config import ROOT
    target = Path(path)
    if not target.is_absolute():
        target = ROOT / target
    target.parent.mkdir(parents=True, exist_ok=True)
    out.save(target)
    return target
