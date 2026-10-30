"""Procedural KAIRO renderer.

The character is built from a fixed skeleton so the design can never drift
between shots: same head radius, same torso length, same limb lengths, same
foot size.  Only pose, wardrobe, expression and lighting change.

All coordinates are in "body space": origin at the hip, y pointing down the
screen, x pointing in the direction the character faces.
"""

from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass

from PIL import Image, ImageDraw

# ---------------------------------------------------------------- proportions
HEAD_R = 118            # slightly oversized round head
NECK_RISE = 96          # head centre above the neck point
TORSO = 208             # neck to hip
UPPER_ARM = 118
FOREARM = 112
THIGH = 168
SHIN = 168
FOOT_L = 64             # slightly oversized feet
FOOT_H = 24
SHOULDER_W = 34

INK = (24, 20, 18)
SKIN = (232, 221, 203)
HIDE = (122, 86, 52)
HIDE_DARK = (86, 58, 34)
SUIT = (24, 24, 27)
SHIRT = (238, 233, 222)
RIM_WARM = (255, 208, 138)
_UNSET = object()
RIM_COOL = (140, 186, 214)


def _pt(origin, angle_deg, length, f):
    """Point at ``length`` from ``origin``; angle 0 = straight down,
    positive angle swings toward the character's facing direction."""
    a = math.radians(angle_deg)
    return (origin[0] + f * length * math.sin(a),
            origin[1] + length * math.cos(a))


def _mid(p, q, t=0.5):
    return (p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t)


@dataclass
class Pose:
    """Skeleton description for one keyframe pose."""
    torso_lean: float = 0.0      # + leans forward (toward facing)
    head_tilt: float = 0.0       # + tips forward
    head_turn: float = 0.0       # -1..1, sideways glance
    arm_back: tuple = (10.0, 5.0)
    arm_front: tuple = (-8.0, -4.0)
    leg_back: tuple = (6.0, 2.0)
    leg_front: tuple = (-6.0, -2.0)
    hip_drop: float = 0.0        # sit / kneel
    prop: str | None = None


POSES: dict[str, Pose] = {
    # ------------------------------------------------------------ present day
    "sit_talk": Pose(torso_lean=4, head_tilt=-2, arm_back=(16, 26), arm_front=(20, 34),
                     leg_back=(84, 6), leg_front=(76, 2), hip_drop=150),
    "sit_gesture": Pose(torso_lean=8, head_tilt=2, arm_back=(28, 46), arm_front=(58, 74),
                        leg_back=(84, 6), leg_front=(76, 2), hip_drop=150),
    "sit_glance_clock": Pose(torso_lean=-2, head_tilt=-14, head_turn=-0.8,
                             arm_back=(14, 20), arm_front=(24, 40),
                             leg_back=(84, 6), leg_front=(76, 2), hip_drop=150),
    "sit_final": Pose(torso_lean=6, head_tilt=-4, arm_back=(18, 30), arm_front=(30, 52),
                      leg_back=(84, 6), leg_front=(76, 2), hip_drop=150),
    # S04 is a seated close-up: keep the chair relationship, change only the head
    "closeup_calm": Pose(torso_lean=2, head_tilt=-3, arm_back=(14, 22),
                         arm_front=(22, 38), leg_back=(84, 6), leg_front=(76, 2),
                         hip_drop=150),
    # S05 is drawn as isolated eyes; the pose only supplies staging numbers
    "eyes_extreme": Pose(),
    # ------------------------------------------------------------- prehistoric
    "stand_grass_spear": Pose(torso_lean=6, head_tilt=-8, arm_back=(22, 30),
                              arm_front=(34, 58), leg_back=(10, 2), leg_front=(-12, -4),
                              prop="spear"),
    "walk_spear": Pose(torso_lean=12, head_tilt=4, arm_back=(30, 24),
                       arm_front=(46, 70), leg_back=(34, 10), leg_front=(-32, -16),
                       prop="spear"),
    "kneel_look": Pose(torso_lean=26, head_tilt=16, arm_back=(56, 76),
                       arm_front=(50, 70), leg_back=(96, -96), leg_front=(24, -40),
                       hip_drop=110, prop="spear"),
    "stand_freeze": Pose(torso_lean=-4, head_tilt=-6, head_turn=0.7,
                         arm_back=(24, 34), arm_front=(38, 62),
                         leg_back=(18, 6), leg_front=(-20, -8), prop="spear"),
    "stand_back_spear": Pose(torso_lean=-14, head_tilt=-10,
                             arm_back=(52, 88), arm_front=(60, 96),
                             leg_back=(28, 12), leg_front=(-30, -14), prop="spear"),
    "run": Pose(torso_lean=26, head_tilt=10, arm_back=(64, 38), arm_front=(74, 118),
                leg_back=(56, 92), leg_front=(-52, -30), prop="spear"),
    "run_turn": Pose(torso_lean=22, head_tilt=6, head_turn=0.6,
                     arm_back=(58, 40), arm_front=(70, 112),
                     leg_back=(52, 86), leg_front=(-46, -26), prop="spear"),
    "stumble": Pose(torso_lean=34, head_tilt=18, arm_back=(78, 64), arm_front=(84, 70),
                    leg_back=(40, 76), leg_front=(-34, -12), prop="spear"),
    "press_rock": Pose(torso_lean=8, head_tilt=-4, arm_back=(60, 92), arm_front=(56, 88),
                       leg_back=(16, 6), leg_front=(-16, -8), prop="spear"),
    "peek_rock": Pose(torso_lean=18, head_tilt=-6, head_turn=0.5,
                      arm_back=(40, 62), arm_front=(44, 66),
                      leg_back=(20, 8), leg_front=(-18, -6), prop="spear"),
    "turn_passage": Pose(torso_lean=2, head_tilt=-8, head_turn=0.9,
                         arm_back=(18, 26), arm_front=(26, 44),
                         leg_back=(12, 4), leg_front=(-12, -4), prop="spear"),
    "step_forward": Pose(torso_lean=14, head_tilt=-6, head_turn=0.7,
                         arm_back=(22, 30), arm_front=(30, 50),
                         leg_back=(26, 8), leg_front=(-24, -8), prop="spear"),
    "walk_passage": Pose(torso_lean=10, head_tilt=2, arm_back=(28, 20),
                         arm_front=(40, 62), leg_back=(30, 8), leg_front=(-28, -12),
                         prop="spear"),
    "stand_amazed": Pose(torso_lean=-8, head_tilt=-16,
                         arm_back=(20, 14), arm_front=(24, 18),
                         leg_back=(12, 4), leg_front=(-12, -4), prop="spear"),
    "approach_map": Pose(torso_lean=20, head_tilt=18,
                         arm_back=(34, 52), arm_front=(46, 72),
                         leg_back=(24, 8), leg_front=(-22, -8), prop="spear"),
    "reach_hand": Pose(torso_lean=22, head_tilt=14,
                       arm_back=(30, 44), arm_front=(86, 92),
                       leg_back=(18, 6), leg_front=(-18, -6), prop="spear"),
    "touch_map": Pose(torso_lean=26, head_tilt=16,
                      arm_back=(28, 40), arm_front=(92, 86),
                      leg_back=(16, 6), leg_front=(-16, -6), prop="spear"),
    "lift_map": Pose(torso_lean=8, head_tilt=10,
                     arm_back=(70, 96), arm_front=(76, 100),
                     leg_back=(16, 6), leg_front=(-16, -6), prop="map"),
}

def skeleton(pose: Pose, facing: int = 1) -> dict:
    """Resolve a Pose into absolute body-space joint positions."""
    f = facing
    hip = (0.0, float(pose.hip_drop))
    lean = math.radians(pose.torso_lean)
    neck = (hip[0] + f * TORSO * math.sin(lean), hip[1] - TORSO * math.cos(lean))
    sh_back = (neck[0] - f * SHOULDER_W * math.cos(lean),
               neck[1] + SHOULDER_W * math.sin(lean) + 8)
    sh_front = (neck[0] + f * SHOULDER_W * math.cos(lean),
                neck[1] - SHOULDER_W * math.sin(lean) + 8)
    hip_back = (hip[0] - f * 16, hip[1])
    hip_front = (hip[0] + f * 16, hip[1])

    elbow_b = _pt(sh_back, pose.arm_back[0], UPPER_ARM, f)
    wrist_b = _pt(elbow_b, pose.arm_back[1], FOREARM, f)
    elbow_f = _pt(sh_front, pose.arm_front[0], UPPER_ARM, f)
    wrist_f = _pt(elbow_f, pose.arm_front[1], FOREARM, f)
    knee_b = _pt(hip_back, pose.leg_back[0], THIGH, f)
    ankle_b = _pt(knee_b, pose.leg_back[1], SHIN, f)
    knee_f = _pt(hip_front, pose.leg_front[0], THIGH, f)
    ankle_f = _pt(knee_f, pose.leg_front[1], SHIN, f)
    head_c = (neck[0] + f * pose.head_turn * 26 + f * pose.head_tilt * 0.35,
              neck[1] - NECK_RISE)
    return {
        "hip": hip, "hip_back": hip_back, "hip_front": hip_front,
        "neck": neck, "sh_back": sh_back, "sh_front": sh_front,
        "elbow_b": elbow_b, "wrist_b": wrist_b,
        "elbow_f": elbow_f, "wrist_f": wrist_f,
        "knee_b": knee_b, "ankle_b": ankle_b,
        "knee_f": knee_f, "ankle_f": ankle_f,
        "head_c": head_c,
    }


# expression -> (brow angle deg, brow lift, mouth shape)
EXPRESSIONS = {
    "warm":       (-6, 0, "smile"),
    "amused":     (-10, -2, "smile"),
    "neutral":    (0, 0, "line"),
    "thoughtful": (4, 2, "line"),
    "sad":        (-14, -4, "frown"),
    "serious":    (12, -2, "flat"),
    "alert":      (-4, -6, "line"),
    "fear":       (-18, -8, "open"),
    "amazed":     (-16, -10, "open"),
    "determined": (14, 2, "flat"),
    "mysterious": (2, -2, "smile"),
    "cautious":   (6, -2, "line"),
}


def _both(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def kairo_layer(size, origin, scale, pose_name, wardrobe, expression,
                facing=1, mouth=0.0, blink=False, rim=RIM_WARM,
                prop_state="rest", prop_override=_UNSET):
    """Render KAIRO onto a transparent RGBA layer.

    ``mouth`` (0..1) opens the mouth and is driven by the voice-over envelope;
    ``blink`` closes the eyes for one or two frames.
    """
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    pose = POSES[pose_name]
    if prop_override is not _UNSET:
        pose = dataclasses.replace(pose, prop=prop_override)
    sk = skeleton(pose, facing)
    lw = max(2, int(15 * scale))
    torso_w = max(3, int(26 * scale))

    def P(p):
        return (origin[0] + p[0] * scale, origin[1] + p[1] * scale)

    def seg(a, b, width, color, off=(0, 0)):
        pa, pb = P(a), P(b)
        d.line([(pa[0] + off[0], pa[1] + off[1]),
                (pb[0] + off[0], pb[1] + off[1])],
               fill=color, width=width, joint="curve")

    def foot(ankle, color, off=(0, 0)):
        x, y = P(ankle)
        x += off[0]
        y += off[1]
        fl = FOOT_L * scale
        fh = FOOT_H * scale
        if wardrobe == "suit":
            x0, x1 = sorted((x - fl * 0.45, x + fl * 0.55 * facing))
            d.rounded_rectangle([x0, y - fh * 0.25, x1, y + fh],
                                radius=fh * 0.5, fill=color)
        else:
            d.ellipse([x - fl * 0.40, y - fh * 0.35,
                       x + fl * 0.60, y + fh * 0.85], fill=color)

    def leg(hip_p, knee, ankle, width, color, off=(0, 0)):
        seg(hip_p, knee, width, color, off)
        seg(knee, ankle, width, color, off)
        foot(ankle, color, off)

    def wardrobe_shape(color, off=(0, 0)):
        neck, hip = P(sk["neck"]), P(sk["hip"])
        nx, ny = neck[0] + off[0], neck[1] + off[1]
        hx, hy = hip[0] + off[0], hip[1] + off[1]
        if wardrobe == "suit":
            sh_w = 74 * scale       # jacket shoulders, wider than the waist
            waist_w = 54 * scale
            d.polygon([(nx - sh_w, ny + 10 * scale), (nx + sh_w, ny + 10 * scale),
                       (hx + waist_w, hy + 12 * scale),
                       (hx - waist_w, hy + 12 * scale)], fill=color)
        else:
            sh_w = 88 * scale
            d.polygon([(nx - sh_w, ny + 4 * scale),
                       (nx + sh_w, ny + 4 * scale),
                       (hx + 64 * scale, hy + 104 * scale),
                       (hx - 64 * scale, hy + 104 * scale)], fill=color)

    def draw_character(is_rim):
        back_ink = (54, 48, 44)     # far limbs sit a touch lighter: depth
        if is_rim:
            color = rim
            off = (-int(7 * scale) * (1 if facing > 0 else -1), -int(8 * scale))
            extra = max(4, int(16 * scale))
        else:
            color = INK
            off = (0, 0)
            extra = 0

        if not is_rim:
            # far limb and far arm first, so the body occludes them
            leg(sk["hip_back"], sk["knee_b"], sk["ankle_b"], lw, back_ink, off)
            seg(sk["sh_back"], sk["elbow_b"], lw - 2, back_ink, off)
            seg(sk["elbow_b"], sk["wrist_b"], lw - 2, back_ink, off)

        if is_rim:
            wardrobe_shape(color, off)
            seg(sk["neck"], sk["hip"], torso_w + extra, color, off)
            leg(sk["hip_front"], sk["knee_f"], sk["ankle_f"], lw + extra, color, off)
            seg(sk["sh_front"], sk["elbow_f"], lw + extra, color, off)
            seg(sk["elbow_f"], sk["wrist_f"], lw + extra, color, off)
        else:
            # the hide tunic is brown; the suit is black. Never one for the other.
            shape_col = INK if wardrobe == "suit" else HIDE
            torso_col = INK if wardrobe == "suit" else HIDE_DARK
            wardrobe_shape(shape_col, off)
            seg(sk["neck"], sk["hip"], torso_w, torso_col, off)
            leg(sk["hip_front"], sk["knee_f"], sk["ankle_f"], lw, color, off)
            seg(sk["sh_front"], sk["elbow_f"], lw, color, off)
            seg(sk["elbow_f"], sk["wrist_f"], lw, color, off)

    draw_character(True)
    draw_character(False)      # ink pass: the character is only "drawn" here

    # ---- wardrobe detailing on the ink pass ------------------------------
    neck, hip = P(sk["neck"]), P(sk["hip"])
    if wardrobe == "suit":
        sw = 74 * scale
        d.polygon([(neck[0] - sw * 0.32, neck[1] + 22 * scale),
                   (neck[0] + sw * 0.32, neck[1] + 22 * scale),
                   (neck[0] + sw * 0.05, neck[1] + 120 * scale),
                   (neck[0] - sw * 0.05, neck[1] + 120 * scale)], fill=SHIRT)
        d.polygon([(neck[0] - 7 * scale, neck[1] + 40 * scale),
                   (neck[0] + 7 * scale, neck[1] + 40 * scale),
                   (neck[0] + 4 * scale, neck[1] + 112 * scale),
                   (neck[0] - 4 * scale, neck[1] + 112 * scale)], fill=(12, 12, 14))
        for side in (-1, 1):        # lapels
            d.line([(neck[0] + side * 10 * scale, neck[1] + 24 * scale),
                    (neck[0] + side * sw * 0.52, neck[1] + 104 * scale)],
                   fill=(6, 6, 7), width=max(2, int(5 * scale)))
        # jacket hem marking the waist
        d.line([(hip[0] - 60 * scale, hip[1] + 6 * scale),
                (hip[0] + 48 * scale, hip[1] + 6 * scale)],
               fill=(8, 8, 9), width=max(2, int(6 * scale)))
    else:
        d.line([(neck[0] - 44 * scale, neck[1] + 74 * scale),
                (neck[0] + 44 * scale, neck[1] + 74 * scale)],
               fill=HIDE_DARK, width=max(2, int(7 * scale)))
        d.line([(neck[0] - 14 * scale, neck[1] + 22 * scale),
                (neck[0] + 10 * scale, neck[1] + 70 * scale)],
               fill=HIDE_DARK, width=max(2, int(4 * scale)))

    # ---- head ------------------------------------------------------------
    hc = P(sk["head_c"])
    r = HEAD_R * scale
    # neck first, and only up to the jaw line, so it can never cut the face
    seg(sk["neck"], _both(sk["neck"], sk["head_c"], 0.34),
        max(3, int(18 * scale)), INK)
    # rim light: an offset crescent on the lit side, not a halo
    rim_dx, rim_dy = -0.13 * r, -0.13 * r
    d.ellipse([hc[0] - r + rim_dx, hc[1] - r + rim_dy,
               hc[0] + r + rim_dx, hc[1] + r + rim_dy], fill=rim)
    d.ellipse([hc[0] - r, hc[1] - r, hc[0] + r, hc[1] + r],
              fill=SKIN, outline=INK, width=max(2, int(7 * scale)))

    # ---- hair: three short strands that sit on the crown -----------------
    hair_w = max(2, int(7 * scale))
    crown = -0.99 * r
    for dx, tip_dx, tip_dy in ((-0.24, -0.34, -1.13), (0.02, -0.02, -1.16),
                               (0.28, 0.40, -1.08)):
        d.line([(hc[0] + dx * r, hc[1] + crown),
                (hc[0] + tip_dx * r, hc[1] + tip_dy * r)],
               fill=INK, width=hair_w, joint="curve")

    # ---- face ------------------------------------------------------------
    brow_ang, brow_lift, mouth_shape = EXPRESSIONS.get(expression,
                                                      EXPRESSIONS["neutral"])
    eye_dx = 0.36 * r
    eye_y = hc[1] - 0.04 * r
    eye_w = 0.105 * r
    eye_h = 0.135 * r
    shift = pose.head_turn * 0.18 * r
    for s in (-1, 1):
        ex = hc[0] + s * eye_dx + shift
        if blink:
            d.line([(ex - eye_w, eye_y), (ex + eye_w, eye_y)],
                   fill=INK, width=max(2, int(5 * scale)))
        else:
            d.ellipse([ex - eye_w, eye_y - eye_h, ex + eye_w, eye_y + eye_h],
                      fill=INK)
        by = eye_y - 0.38 * r + brow_lift * 0.02 * r
        inner = (ex - s * 0.20 * r, by + math.sin(math.radians(brow_ang)) * 0.10 * r)
        outer = (ex + s * 0.20 * r, by - math.sin(math.radians(brow_ang)) * 0.10 * r)
        d.line([inner, outer], fill=INK, width=max(2, int(6 * scale)))

    mx = hc[0] + shift * 0.8
    my = hc[1] + 0.42 * r
    mw = 0.17 * r
    open_h = mouth * 0.26 * r
    if mouth > 0.12 or mouth_shape == "open":
        d.ellipse([mx - mw, my - max(open_h * 0.35, 0.035 * r),
                   mx + mw, my + max(open_h, 0.115 * r)], fill=INK)
    elif mouth_shape == "smile":
        d.arc([mx - mw, my - 0.14 * r, mx + mw, my + 0.14 * r],
              20, 160, fill=INK, width=max(2, int(5 * scale)))
    elif mouth_shape == "frown":
        d.arc([mx - mw, my - 0.03 * r, mx + mw, my + 0.23 * r],
              200, 340, fill=INK, width=max(2, int(5 * scale)))
    else:
        d.line([(mx - mw, my), (mx + mw, my)], fill=INK,
               width=max(2, int(5 * scale)))

    # ---- props -----------------------------------------------------------
    if pose.prop == "spear":
        draw_spear(d, P(sk["wrist_f"]), scale, facing)
    elif pose.prop == "map":
        draw_tablet(d, P(sk["wrist_f"]), 54 * scale, glow=prop_state == "glow")

    return layer



def draw_spear(d, hand, scale, facing):
    """Spear held upright through the hand: shaft leans back with the grip."""
    L = 470 * scale
    top = (hand[0] - facing * L * 0.10, hand[1] - L * 0.62)
    bottom = (hand[0] + facing * L * 0.10, hand[1] + L * 0.38)
    d.line([bottom, top], fill=(92, 64, 38), width=max(2, int(10 * scale)))
    tip = (top[0] - facing * 12 * scale, top[1] - 46 * scale)
    d.line([top, tip], fill=(206, 198, 182), width=max(2, int(13 * scale)))



def draw_tablet(d, hand, radius, glow=False, glyph_seed=5):
    """The ancient map: circular amber stone, concentric rings, glyphs."""
    import random
    rnd = random.Random(glyph_seed)
    x, y = hand[0], hand[1] - radius * 0.55
    ry = radius * 0.44
    d.ellipse([x - radius, y - ry, x + radius, y + ry],
              fill=(198, 152, 94), outline=(72, 50, 30),
              width=max(2, int(radius * 0.08)))
    for k in (0.74, 0.48, 0.24):
        d.ellipse([x - radius * k, y - ry * k, x + radius * k, y + ry * k],
                  outline=(122, 84, 48), width=max(1, int(radius * 0.03)))
    for i in range(12):
        a = math.radians(i * 30)
        d.line([(x + math.cos(a) * radius * 0.26, y + math.sin(a) * ry * 0.26),
                (x + math.cos(a) * radius * 0.94, y + math.sin(a) * ry * 0.94)],
               fill=(128, 88, 50), width=max(1, int(radius * 0.018)))
    for _ in range(16):
        a = rnd.uniform(0, 2 * math.pi)
        rr = rnd.uniform(0.3, 0.9)
        px, py = x + math.cos(a) * radius * rr, y + math.sin(a) * ry * rr
        s = radius * 0.05
        d.line([(px - s, py), (px + s, py)], fill=(96, 64, 36),
               width=max(1, int(radius * 0.016)))
    if glow:
        gx, gy = x + radius * 0.42, y + ry * 0.10
        for k, col in ((2.4, (255, 214, 130, 60)), (1.5, (255, 226, 160, 110)),
                       (0.7, (255, 245, 214, 255))):
            d.ellipse([gx - radius * 0.06 * k, gy - radius * 0.06 * k,
                       gx + radius * 0.06 * k, gy + radius * 0.06 * k], fill=col)


def draw_eyes(layer, centre, radius, open_ratio=1.0):
    """Extreme close-up eyes used for the match cut in S05."""
    d = ImageDraw.Draw(layer)
    cx, cy = centre
    r = radius
    d.rectangle([0, 0, layer.width, layer.height], fill=(16, 12, 10))
    for s in (-1, 1):
        ex = cx + s * r * 1.15
        d.ellipse([ex - r, cy - r, ex + r, cy + r], fill=(238, 228, 210))
        d.ellipse([ex - r * 0.44, cy - r * 0.52, ex + r * 0.44, cy + r * 0.52],
                  fill=(30, 22, 16))
        d.ellipse([ex - r * 0.16, cy - r * 0.20, ex + r * 0.16, cy + r * 0.20],
                  fill=(8, 6, 6))
        d.ellipse([ex - r * 0.05, cy - r * 0.30, ex + r * 0.10, cy - r * 0.16],
                  fill=(255, 250, 240))
    return layer

