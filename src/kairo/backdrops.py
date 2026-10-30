"""Procedural environments for KAIRO Episode 01.

Every backdrop is painted at 2x the delivery resolution (3840x2160) so the
final 1920x1080 frames stay crisp, and so the camera can push and crop without
losing detail.  Backdrops are pure functions of a name + seed: the cave
geometry, the savanna horizon and the room layout are identical everywhere
they are referenced, which is what keeps the film continuous.
"""

from __future__ import annotations

import math
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

SS = 2                      # supersample factor over 1920x1080
W, H = 1920 * SS, 1080 * SS


def vgrad(size, top, bottom):
    w, h = size
    t = np.linspace(0.0, 1.0, h, dtype=np.float32)[:, None]
    top = np.array(top, dtype=np.float32)
    bottom = np.array(bottom, dtype=np.float32)
    rows = top[None, :] * (1 - t) + bottom[None, :] * t
    arr = np.repeat(rows[:, None, :], w, axis=1)
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")


def grain(img, amount=6.0, seed=1):
    rng = np.random.default_rng(seed)
    arr = np.asarray(img, dtype=np.float32)
    noise = rng.normal(0, amount, arr.shape[:2])[:, :, None]
    return Image.fromarray(np.clip(arr + noise, 0, 255).astype(np.uint8), "RGB")


def vignette(img, strength=0.55):
    w, h = img.size
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    cx, cy = w / 2, h / 2
    r = np.sqrt(((xx - cx) / cx) ** 2 + ((yy - cy) / cy) ** 2)
    mask = np.clip(1.0 - strength * np.clip(r - 0.35, 0, 2.0) ** 1.6, 0.05, 1.0)
    arr = np.asarray(img, dtype=np.float32) * mask[:, :, None]
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")


def _haze(img: Image.Image, y0: float, y1: float,
          colour=(228, 200, 160), strength=64) -> Image.Image:
    """Atmospheric haze band, so grass planes don't meet on a hard line."""
    arr = np.asarray(img.convert("RGB"), dtype=np.float32)
    h = arr.shape[0]
    grad = np.zeros(h, dtype=np.float32)
    i0, i1 = int(y0 * h), min(h, int(y1 * h))
    if i1 > i0:
        grad[i0:i1] = np.linspace(1.0, 0.0, i1 - i0, dtype=np.float32)
    mask = (grad * strength / 255.0)[:, None, None]
    out = arr * (1 - mask) + np.array(colour, dtype=np.float32) * mask
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGB")


def add_glow(img: Image.Image, centre, radius, colour, strength=210):
    """Smooth circular light falloff.

    Built by hand with numpy: PIL's ``radial_gradient`` is Chebyshev (square),
    which leaves a visible rectangular box in the sky.
    """
    import numpy as np

    size = max(8, int(radius * 2))
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    r = np.sqrt((xx - size / 2) ** 2 + (yy - size / 2) ** 2) / (size / 2)
    mask = np.clip(1.0 - r, 0.0, 1.0) ** 2 * strength
    mask_img = Image.fromarray(mask.astype(np.uint8), "L")
    halo = Image.new("RGBA", (size, size), colour + (255,))
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    layer.paste(halo, (int(centre[0] - radius), int(centre[1] - radius)), mask_img)
    img.alpha_composite(layer)



def glow(draw, centre, radius, colour, steps=18):
    """Legacy stub kept for signature compatibility; use add_glow instead."""
    return None



# --------------------------------------------------------------------- room
def modern_room(close: bool = False, k: float = 1.0,
                seat_x: float = 0.34) -> Image.Image:
    """Dark modern room. ``k`` is the character scale, so the chair, lamp and
    clock always fit whoever is sitting in the chair."""
    img = vgrad((W, H), (16, 16, 22), (8, 8, 11)).convert("RGBA")
    d = ImageDraw.Draw(img, "RGBA")
    floor = H * 0.82
    seat_x = W * seat_x
    seat_y = floor - 184 * k
    # back wall / floor split with soft skirting
    d.rectangle([0, floor, W, H], fill=(14, 12, 13, 255))
    d.line([(0, floor), (W, floor)], fill=(40, 33, 28, 255), width=int(4 * SS))
    # curtain, camera-right
    d.rectangle([W * 0.76, 0, W, floor], fill=(20, 18, 24, 255))
    for i in range(7):
        x = W * 0.76 + i * W * 0.036
        d.line([(x, 0), (x + 30 * SS, floor)], fill=(27, 24, 30, 160),
               width=int(26 * SS))
    # wall clock above the chair
    ccx, ccy, cr = seat_x + 330 * k, seat_y - 560 * k, 60 * SS * (0.7 + 0.3 * k)
    d.ellipse([ccx - cr, ccy - cr, ccx + cr, ccy + cr], fill=(30, 28, 28, 255),
              outline=(120, 104, 78, 255), width=int(4 * SS))
    d.ellipse([ccx - cr * 0.86, ccy - cr * 0.86, ccx + cr * 0.86,
               ccy + cr * 0.86], fill=(222, 210, 188, 255))
    for i in range(12):
        a = math.radians(i * 30)
        d.line([(ccx + math.cos(a) * cr * 0.66, ccy + math.sin(a) * cr * 0.66),
                (ccx + math.cos(a) * cr * 0.80, ccy + math.sin(a) * cr * 0.80)],
               fill=(60, 52, 44, 255), width=int(3 * SS))
    d.line([(ccx, ccy), (ccx + cr * 0.34, ccy - cr * 0.30)],
           fill=(40, 34, 30, 255), width=int(4 * SS))
    d.line([(ccx, ccy), (ccx - cr * 0.10, ccy - cr * 0.58)],
           fill=(40, 34, 30, 255), width=int(3 * SS))
    # armchair, sized to the character
    hw = 150 * k
    d.rounded_rectangle([seat_x - hw, seat_y - 300 * k, seat_x + hw, seat_y + 24 * k],
                        radius=44 * k, fill=(58, 40, 30, 255))
    d.rounded_rectangle([seat_x - hw * 1.18, seat_y - 46 * k,
                         seat_x + hw * 1.18, seat_y + 30 * k],
                        radius=22 * k, fill=(46, 31, 24, 255))
    d.rounded_rectangle([seat_x - hw * 0.94, seat_y - 30 * k,
                         seat_x + hw * 0.94, seat_y + 16 * k],
                        radius=16 * k, fill=(70, 48, 35, 255))
    for side in (-1, 1):
        d.rounded_rectangle([seat_x + side * hw * 1.02 - 18 * k, seat_y - 84 * k,
                             seat_x + side * hw * 1.12 + 18 * k, seat_y + 10 * k],
                            radius=16 * k, fill=(52, 36, 27, 255))
        d.rectangle([seat_x + side * hw * 0.92 - 11 * k, seat_y + 24 * k,
                     seat_x + side * hw * 0.92 + 11 * k, floor],
                    fill=(34, 24, 18, 255))

    # floor lamp, camera-left of the chair, scaled with the character
    lx = max(W * 0.06, seat_x - 540 * k)
    ly = floor
    d.line([(lx, ly), (lx, ly - 470 * k)], fill=(38, 32, 26, 255),
           width=int(9 * k))
    d.ellipse([lx - 58 * k, ly - 24 * k, lx + 58 * k, ly + 14 * k],
              fill=(34, 28, 22, 255))
    d.polygon([(lx - 96 * k, ly - 430 * k), (lx + 96 * k, ly - 430 * k),
               (lx + 70 * k, ly - 560 * k), (lx - 70 * k, ly - 560 * k)],
              fill=(206, 158, 92, 255))
    add_glow(img, (lx, ly - 430 * k), 330 * k, (255, 196, 116), strength=150)
    add_glow(img, (lx + 40 * k, ly), 420 * k, (255, 172, 96), strength=90)
    if close:
        img = img.filter(ImageFilter.GaussianBlur(6 * SS))
    img = img.convert("RGB")
    return vignette(grain(img, 5, 3), 0.62 if not close else 0.5)



# ------------------------------------------------------------------ savanna
def _savanna_sky(img, d, horizon=0.62, sun=(0.20, 0.50)):
    sky = vgrad((W, int(H * horizon)), (86, 104, 142), (255, 186, 118))
    img.paste(sky, (0, 0))
    sx, sy = W * sun[0], H * sun[1]
    add_glow(img, (sx, sy), 300 * SS, (255, 206, 140))
    d.ellipse([sx - 54 * SS, sy - 54 * SS, sx + 54 * SS, sy + 54 * SS],
              fill=(255, 240, 208, 255))
    return sx, sy


def _hills(d, horizon_px, rng):
    for colour, height in (((132, 116, 104), 0.10), ((104, 96, 92), 0.055),
                           ((78, 74, 72), 0.03)):
        pts = [(0, horizon_px)]
        x = 0
        while x < W:
            pts.append((x, horizon_px - rng.uniform(0.02, height) * H))
            x += rng.randint(int(120 * SS), int(300 * SS))
        pts += [(W, horizon_px), (W, horizon_px + 40 * SS), (0, horizon_px + 40 * SS)]
        d.polygon(pts, fill=colour + (255,))


def _acacia(d, x, ground, h, rng):
    trunk = (56, 44, 32, 255)
    d.line([(x, ground), (x + h * 0.06, ground - h * 0.62)], fill=trunk,
           width=max(3, int(h * 0.035)))
    d.line([(x + h * 0.06, ground - h * 0.55), (x - h * 0.16, ground - h * 0.74)],
           fill=trunk, width=max(2, int(h * 0.02)))
    d.line([(x + h * 0.06, ground - h * 0.58), (x + h * 0.26, ground - h * 0.76)],
           fill=trunk, width=max(2, int(h * 0.02)))
    for _ in range(7):
        cx = x + rng.uniform(-0.30, 0.34) * h
        cy = ground - h * rng.uniform(0.72, 0.92)
        rw = h * rng.uniform(0.12, 0.22)
        d.ellipse([cx - rw, cy - rw * 0.34, cx + rw, cy + rw * 0.34],
                  fill=(48, 58, 34, 255))


def _grass_band(d, top, bottom, rng, colour, blade_h, density=1.0):
    h = float(bottom - top)
    if h <= 0:
        return
    # soft entry: the plane fades in instead of starting on a hard line
    steps = 26
    for i in range(steps):
        y0 = top + h * i / steps
        y1 = top + h * (i + 1) / steps
        alpha = int(255 * min(1.0, (i + 1) / 7.0))
        d.rectangle([0, y0, W, y1], fill=colour + (alpha,))
    for _ in range(int(W / (10 * SS) * density)):
        x = rng.uniform(0, W)
        y = rng.uniform(top, bottom)
        bh = rng.uniform(blade_h * 0.4, blade_h)
        lean = rng.uniform(-0.35, 0.35) * bh
        shade = rng.randint(-18, 18)
        col = tuple(max(0, min(255, c + shade)) for c in colour)
        d.line([(x, y), (x + lean, y - bh)], fill=col + (210,),
               width=max(1, int(3 * SS)))



def savanna(kind: str, seed: int = 7) -> Image.Image:
    rng = random.Random(seed)
    img = Image.new("RGBA", (W, H), (60, 60, 60, 255))
    d = ImageDraw.Draw(img, "RGBA")
    horizon = int(H * 0.60)

    if kind == "aerial":
        _savanna_sky(img, d, horizon=0.52, sun=(0.22, 0.34))
        _hills(d, int(H * 0.52), rng)
        _grass_band(d, int(H * 0.50), H, rng, (196, 158, 92), 26 * SS, 0.5)
        for _ in range(26):
            _acacia(d, rng.uniform(0, W), rng.uniform(H * 0.62, H * 0.86),
                    rng.uniform(H * 0.10, H * 0.26), rng)
        _grass_band(d, int(H * 0.80), H, rng, (150, 118, 66), 34 * SS, 0.8)
    else:
        _savanna_sky(img, d, horizon=0.62, sun=(0.18, 0.46))
        _hills(d, horizon, rng)
        _grass_band(d, horizon, H, rng, (188, 150, 84), 30 * SS, 0.7)
        for _ in range(9):
            _acacia(d, rng.uniform(0, W), rng.uniform(horizon, H * 0.86),
                    rng.uniform(H * 0.16, H * 0.34), rng)

    if kind == "grass":
        _grass_band(d, int(H * 0.70), H, rng, (170, 133, 70), 90 * SS, 1.0)
    elif kind == "predator":
        for _ in range(30):            # dense bushes, camera-right
            bx = rng.uniform(W * 0.55, W * 1.05)
            by = rng.uniform(H * 0.52, H * 0.80)
            rw = rng.uniform(H * 0.07, H * 0.16)
            d.ellipse([bx - rw, by - rw * 0.7, bx + rw, by + rw * 0.7],
                      fill=(44, 50, 32, 255))
        _grass_band(d, int(H * 0.78), H, rng, (160, 124, 64), 70 * SS, 1.0)
    elif kind == "chase":
        for _ in range(70):            # streaked grass sells the speed
            y = rng.uniform(H * 0.66, H)
            h = rng.uniform(80 * SS, 200 * SS)
            x = rng.uniform(-0.1 * W, W)
            d.line([(x, y), (x + h * 1.4, y - h * 0.35)],
                   fill=(196, 158, 92, rng.randint(90, 170)),
                   width=rng.randint(int(4 * SS), int(12 * SS)))
        _grass_band(d, int(H * 0.80), H, rng, (146, 112, 58), 60 * SS, 0.9)
    elif kind == "tracks":
        _grass_band(d, 0, H, rng, (108, 84, 54), 18 * SS, 0.6)
        for _ in range(40):
            x, y = rng.uniform(0, W), rng.uniform(H * 0.1, H)
            d.line([(x, y), (x + rng.uniform(-90, 90) * SS,
                             y + rng.uniform(10, 70) * SS)],
                   fill=(78, 58, 38, 255), width=int(3 * SS))
        for px, py in ((0.30, 0.42), (0.46, 0.58), (0.62, 0.74)):
            cx, cy = W * px, H * py
            rw = 74 * SS
            d.ellipse([cx - rw, cy - rw * 0.78, cx + rw, cy + rw * 0.78],
                      fill=(74, 56, 36, 255))
            d.ellipse([cx - rw * 0.55, cy - rw * 0.5, cx + rw * 0.55, cy + rw * 0.5],
                      fill=(92, 70, 46, 255))
            for k in range(4):
                a = -1.1 + k * 0.55
                d.ellipse([cx + math.cos(a) * rw * 1.12 - 20 * SS,
                           cy + math.sin(a) * rw * 0.9 - 20 * SS,
                           cx + math.cos(a) * rw * 1.12 + 20 * SS,
                           cy + math.sin(a) * rw * 0.9 + 20 * SS],
                          fill=(70, 52, 34, 255))
    elif kind == "rocks":
        _grass_band(d, int(H * 0.74), H, rng, (168, 132, 70), 70 * SS, 1.0)
        pts = [(W * 0.44, H), (W * 0.46, H * 0.46), (W * 0.60, H * 0.30),
               (W * 0.80, H * 0.34), (W * 0.92, H * 0.52), (W * 0.95, H)]
        d.polygon(pts, fill=(118, 104, 92, 255))
        d.polygon([(p[0], p[1] - 12 * SS) for p in pts], fill=(146, 128, 108, 255))
        mouth = [(W * 0.66, H), (W * 0.665, H * 0.66), (W * 0.70, H * 0.56),
                 (W * 0.76, H * 0.54), (W * 0.805, H * 0.62), (W * 0.81, H)]
        d.polygon(mouth, fill=(6, 6, 8, 255))

    return vignette(grain(_haze(img, 0.54, 0.80), 4, seed), 0.45)



# --------------------------------------------------------------------- cave
def _fractal(w: int, h: int, seed: int, octaves: int = 5, base: int = 6) -> np.ndarray:
    """Value-noise fBm in 0..1, built by upscaling small random grids."""
    acc = np.zeros((h, w), dtype=np.float32)
    amp, total = 1.0, 0.0
    for o in range(octaves):
        s = max(2, base * (2 ** o))
        rnd = np.random.default_rng(seed + o).integers(0, 255, (s, s)).astype(np.uint8)
        layer = Image.fromarray(rnd, "L").resize((w, h), Image.BICUBIC)
        acc += np.asarray(layer, dtype=np.float32) / 255.0 * amp
        total += amp
        amp *= 0.52
    return acc / total


def _rock_surface(w: int, h: int, seed: int, dark, light, contrast: float = 1.45):
    """Stone: fBm texture through a colour ramp, plus a soft top-down light."""
    f = _fractal(w, h, seed, octaves=5, base=5)
    f = np.clip((f - 0.5) * contrast + 0.5, 0, 1) ** 1.15
    ramp = (np.array(dark, np.float32)[None, None, :] * (1 - f)[:, :, None]
            + np.array(light, np.float32)[None, None, :] * f[:, :, None])
    light_grad = np.linspace(1.10, 0.62, h, dtype=np.float32)[:, None, None]
    arr = np.clip(ramp * light_grad, 0, 255).astype(np.uint8)
    return Image.fromarray(arr, "RGB")


def _rock_wall(d, rng, colour, count=90, spread=(0.0, 1.0)):
    """Boulders and rubble sitting at the base of the rock surface."""
    for _ in range(max(3, count // 22)):
        x = rng.uniform(spread[0] * W, spread[1] * W)
        y = rng.uniform(H * 0.66, H * 0.98)
        rw = rng.uniform(W * 0.05, W * 0.14)
        rh = rw * rng.uniform(0.28, 0.5)
        shade = rng.randint(-12, 8)
        col = tuple(max(0, min(255, c + shade)) for c in colour)
        d.ellipse([x - rw, y - rh, x + rw, y + rh], fill=col + (120,))


def _light_shaft(d, x0, x1, top, bottom, colour=(180, 210, 230), alpha=40):
    d.polygon([(x0, top), (x1, top), (x1 + (x1 - x0) * 0.55, bottom),
               (x0 - (x1 - x0) * 0.35, bottom)], fill=colour + (alpha,))


def _shafts_layer(beams, colour=(186, 214, 232), alpha=30, blur=34):
    """Soft volumetric beams: drawn once, blurred, then composited."""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer, "RGBA")
    for x0, x1 in beams:
        d.polygon([(W * x0, 0), (W * x1, 0),
                   (W * x1 + (W * (x1 - x0)) * 0.55, H),
                   (W * x0 - (W * (x1 - x0)) * 0.35, H)],
                  fill=colour + (alpha,))
    return layer.filter(ImageFilter.GaussianBlur(blur * SS))


def cave(kind: str, seed: int = 11) -> Image.Image:
    rng = random.Random(seed)

    if kind == "entrance_ext":
        img = savanna("rocks", seed).convert("RGBA")
        d = ImageDraw.Draw(img, "RGBA")
        add_glow(img, (W * 0.735, H * 0.72), 360 * SS, (255, 214, 150))
        return vignette(grain(img.convert("RGB"), 4, seed + 5), 0.5)

    img = Image.new("RGBA", (W, H), (10, 10, 12, 255))
    d = ImageDraw.Draw(img, "RGBA")

    if kind in ("entrance_int", "mouth_inside", "passage_mouth"):
        img.paste(_rock_surface(W, H, 23, (12, 11, 11), (78, 70, 62)), (0, 0))
        d = ImageDraw.Draw(img, "RGBA")
        _rock_wall(d, rng, (58, 52, 46), 50)
        mx0, mx1 = (W * 0.02, W * 0.36) if kind != "mouth_inside" else (W * 0.34, W * 0.62)
        d.polygon([(mx0, H * 0.04), (mx1, 0), (mx1, H * 0.92), (mx0, H * 0.98)],
                  fill=(255, 236, 196, 255))
        add_glow(img, ((mx0 + mx1) / 2, H * 0.45), 620 * SS, (255, 226, 170))
        d.polygon([(mx0, H * 0.80), (mx1, H * 0.72), (mx1 + W * 0.30, H),
                   (mx0 + W * 0.06, H)], fill=(250, 214, 156, 90))
        d.polygon([(0, 0), (W * 0.30, 0), (W * 0.16, H * 0.55), (0, H * 0.75)],
                  fill=(24, 21, 20, 255))
        d.polygon([(W, 0), (W * 0.72, 0), (W * 0.60, H * 0.30), (W, H * 0.16)],
                  fill=(20, 18, 17, 255))
        d.polygon([(0, H), (W * 0.22, H * 0.86), (W * 0.55, H)], fill=(18, 16, 15, 255))
        if kind == "passage_mouth":
            d.polygon([(W * 0.62, H * 0.18), (W * 0.86, H * 0.12),
                       (W * 0.92, H * 0.86), (W * 0.68, H * 0.94)],
                      fill=(6, 6, 8, 255))

    elif kind == "passage":
        d.rectangle([0, 0, W, H], fill=(9, 9, 11, 255))
        d.polygon([(0, 0), (W * 0.42, H * 0.22), (W * 0.42, H * 0.80), (0, H)],
                  fill=(58, 52, 48, 255))
        d.polygon([(W, 0), (W * 0.58, H * 0.20), (W * 0.58, H * 0.82), (W, H)],
                  fill=(48, 44, 41, 255))
        d.polygon([(W * 0.42, H * 0.22), (W * 0.58, H * 0.20),
                   (W * 0.58, H * 0.82), (W * 0.42, H * 0.80)],
                  fill=(20, 22, 26, 255))
        add_glow(img, (W * 0.50, H * 0.52), 320 * SS, (120, 196, 200))
        _rock_wall(d, rng, (62, 56, 50), 60, (0.0, 0.45))

    else:   # chamber / chamber_exit
        img.paste(_rock_surface(W, int(H * 0.78), 11, (18, 16, 15), (104, 94, 82)), (0, 0))
        d = ImageDraw.Draw(img, "RGBA")
        _rock_wall(d, rng, (86, 78, 68), 60)
        d.arc([-W * 0.20, -H * 0.30, W * 1.20, H * 1.30], 180, 360,
              fill=(46, 43, 40, 255), width=int(60 * SS))
        img = Image.alpha_composite(
            img, _shafts_layer(((0.22, 0.30), (0.52, 0.58), (0.74, 0.79))))
        d = ImageDraw.Draw(img, "RGBA")
        d.polygon([(0, H * 0.72), (W, H * 0.68), (W, H), (0, H)],
                  fill=(38, 34, 31, 255))
        img.paste(_rock_surface(W, int(H * 0.32), 31, (16, 15, 14), (58, 52, 46)),
                  (0, int(H * 0.68)))
        d = ImageDraw.Draw(img, "RGBA")
        cx, cy = W * 0.50, H * 0.74
        pw, ph = W * 0.15, H * 0.085
        # contact shadow, then the block: shadowed base, lit top face
        d.ellipse([cx - pw * 1.15, cy - ph * 0.10, cx + pw * 1.15, cy + ph * 0.55],
                  fill=(8, 7, 7, 150))
        d.polygon([(cx - pw, cy), (cx - pw * 0.8, cy - ph),
                   (cx + pw * 0.8, cy - ph * 0.92), (cx + pw, cy + ph * 0.1)],
                  fill=(64, 58, 52, 255))
        d.polygon([(cx - pw * 0.8, cy - ph), (cx + pw * 0.8, cy - ph * 0.92),
                   (cx + pw * 0.68, cy - ph * 1.12), (cx - pw * 0.68, cy - ph * 1.2)],
                  fill=(112, 103, 92, 255))
        add_glow(img, (cx, cy - ph * 1.1), 260 * SS, (120, 200, 210))
        if kind == "chamber_exit":
            d.polygon([(W * 0.86, H * 0.26), (W, H * 0.18), (W, H * 0.92),
                       (W * 0.84, H * 0.86)], fill=(8, 8, 10, 255))
            add_glow(img, (W * 0.95, H * 0.55), 220 * SS, (150, 200, 190))

    return vignette(grain(img.convert("RGB"), 5, seed + 3), 0.55)



# ---------------------------------------------------------------------- map
def map_view(kind: str, seed: int = 21) -> Image.Image:
    """The circular stone map: one design, four framings."""
    rng = random.Random(seed)
    img = Image.new("RGBA", (W, H), (16, 15, 16, 255))
    d = ImageDraw.Draw(img, "RGBA")
    _rock_wall(d, rng, (70, 64, 58), 80)

    if kind == "platform":
        d.polygon([(W * 0.10, H * 0.30), (W * 0.90, H * 0.26),
                   (W * 0.97, H * 1.05), (W * 0.03, H * 1.05)],
                  fill=(104, 96, 88, 255))
        d.polygon([(W * 0.10, H * 0.30), (W * 0.90, H * 0.26),
                   (W * 0.88, H * 0.36), (W * 0.12, H * 0.40)],
                  fill=(134, 124, 112, 255))
        cx, cy, r = W * 0.50, H * 0.66, W * 0.20
    elif kind == "macro":
        cx, cy, r = W * 0.50, H * 0.52, W * 0.42
    elif kind == "touch":
        cx, cy, r = W * 0.46, H * 0.54, W * 0.36
    else:   # point
        cx, cy, r = W * 0.50, H * 0.50, W * 0.34

    ry = r * 0.80
    d.ellipse([cx - r * 1.06, cy - ry * 1.06, cx + r * 1.06, cy + ry * 1.06],
              fill=(58, 46, 34, 255))
    d.ellipse([cx - r, cy - ry, cx + r, cy + ry], fill=(198, 152, 94, 255),
              outline=(84, 58, 34, 255), width=int(5 * SS))
    for k in (0.80, 0.55, 0.28):
        d.ellipse([cx - r * k, cy - ry * k, cx + r * k, cy + ry * k],
                  outline=(130, 90, 50, 255), width=int(3 * SS))
    for i in range(12):
        a = math.radians(i * 30)
        d.line([(cx + math.cos(a) * r * 0.30, cy + math.sin(a) * ry * 0.30),
                (cx + math.cos(a) * r * 0.96, cy + math.sin(a) * ry * 0.96)],
               fill=(126, 86, 48, 255), width=max(2, int(3 * SS)))
    for _ in range(46):                       # unknown glyphs
        a = rng.uniform(0, 2 * math.pi)
        rr = rng.uniform(0.32, 0.94)
        gx, gy = cx + math.cos(a) * r * rr, cy + math.sin(a) * ry * rr
        s = r * rng.uniform(0.02, 0.045)
        d.line([(gx - s, gy), (gx + s, gy)], fill=(96, 62, 34, 255),
               width=max(2, int(4 * SS)))
        d.line([(gx, gy - s), (gx, gy + s)], fill=(96, 62, 34, 255),
               width=max(2, int(4 * SS)))

    if kind == "touch":
        add_glow(img, (cx + r * 0.46, cy - ry * 0.10), r * 0.30, (255, 214, 132))
        d.ellipse([cx + r * 0.40, cy - ry * 0.22, cx + r * 0.52, cy + ry * 0.02],
                  fill=(255, 244, 210, 255))
    elif kind == "point":
        add_glow(img, (cx + r * 0.44, cy - ry * 0.12), r * 0.42, (255, 210, 120))
        d.ellipse([cx + r * 0.39, cy - ry * 0.24, cx + r * 0.49, cy + ry * 0.00],
                  fill=(255, 250, 226, 255))
        img = Image.alpha_composite(img, Image.new("RGBA", (W, H), (0, 0, 0, 118)))

    return vignette(grain(img.convert("RGB"), 4, seed + 1), 0.5)


# ---------------------------------------------------------------- dispatcher
_CAVE_KINDS = {
    "cave_entrance_ext": "entrance_ext",
    "cave_entrance_int": "entrance_int",
    "cave_mouth_from_inside": "mouth_inside",
    "cave_passage_mouth": "passage_mouth",
    "cave_passage": "passage",
    "cave_chamber": "chamber",
    "cave_chamber_exit": "chamber_exit",
}


def render(name: str, seed: int = 0, k: float = 1.0,
           seat_x: float = 0.34) -> Image.Image:
    """Paint any backdrop by name. Geometry is fixed per name, so reuses match."""
    if name in ("modern_room", "modern_room_closeup"):
        return modern_room(close=name.endswith("closeup"), k=k, seat_x=seat_x)
    if name in ("savanna_aerial", "savanna_grass", "savanna_predator",
                "savanna_chase", "savanna_tracks", "savanna_rocks"):
        return savanna(name.replace("savanna_", ""), seed=7)
    if name in _CAVE_KINDS:
        return cave(_CAVE_KINDS[name], seed=11)
    if name in ("map_platform", "map_macro", "map_touch", "map_point"):
        return map_view(name.replace("map_", ""), seed=21)
    raise KeyError(f"unknown backdrop: {name}")

