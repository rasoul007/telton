"""The prehistoric predator: one locked design, four presentation variants.

Built as a single locked quadruped silhouette (arched back, high shoulder,
tucked belly, wedge skull, long tail) so it can never drift between shots.
"""

from __future__ import annotations

from PIL import ImageDraw

FUR = (150, 132, 104, 255)
FUR_DARK = (96, 80, 60, 255)
BELLY = (186, 170, 142, 255)
SILHOUETTE = (17, 14, 13, 255)
EYE = (244, 210, 110, 255)


def draw_predator(layer, ground, scale, variant="full", facing=-1):
    """Draw the predator with its paws at ``ground``.

    ``variant``: full | silhouette | threshold (mid-distance, outside the cave)
    ``facing``: 1 looks right, -1 looks left.
    """
    d = ImageDraw.Draw(layer)
    x, y = ground
    f = facing
    s = scale

    L = 420.0 * s                 # nose to rump
    Hh = 300.0 * s                # shoulder height

    def P(u, v):
        """u: 0 = nose, 1 = rump.  v: 0 = ground, 1 = shoulder line."""
        return (x - f * u * L, y - v * Hh)

    body = SILHOUETTE if variant == "silhouette" else FUR
    belly = SILHOUETTE if variant == "silhouette" else BELLY
    shade = SILHOUETTE if variant == "silhouette" else FUR_DARK

    # ---- far legs first (behind the body) --------------------------------
    def leg(u_top, u_paw, w_top, w_paw, colour):
        top = P(u_top, 0.52)
        knee = P((u_top + u_paw) / 2 + 0.02, 0.26)
        paw = P(u_paw, 0.0)
        d.line([top, knee, paw], fill=colour, width=int(w_top), joint="curve")
        d.line([knee, paw], fill=colour, width=int(w_paw), joint="curve")
        d.ellipse([paw[0] - w_paw * 0.62, paw[1] - w_paw * 0.30,
                   paw[0] + w_paw * 0.62, paw[1] + w_paw * 0.34], fill=colour)

    leg(0.30, 0.34, 0.085 * L, 0.058 * L, shade)     # far front
    leg(0.82, 0.88, 0.095 * L, 0.060 * L, shade)     # far hind
    leg(0.22, 0.20, 0.095 * L, 0.066 * L, body)    # near front
    leg(0.74, 0.70, 0.105 * L, 0.070 * L, body)    # near hind

    # ---- tail ------------------------------------------------------------
    d.line([P(0.97, 0.88), P(1.10, 0.96), P(1.20, 0.74)],
           fill=body, width=int(0.085 * L), joint="curve")

    # ---- body: arched back, deep chest, tucked belly ---------------------
    body_pts = [P(0.16, 1.00), P(0.34, 1.04), P(0.56, 0.98), P(0.78, 0.99),
                P(0.96, 0.88), P(1.00, 0.62), P(0.90, 0.52), P(0.62, 0.46),
                P(0.36, 0.47), P(0.22, 0.56), P(0.14, 0.78)]
    d.polygon(body_pts, fill=body)

    # ---- neck and wedge skull -------------------------------------------
    d.polygon([P(0.18, 1.00), P(0.10, 0.96), P(0.06, 0.86), P(0.16, 0.72)],
              fill=body)
    skull = [P(0.08, 1.06), P(0.02, 1.02), P(-0.05, 0.92), P(-0.045, 0.84),
             P(0.02, 0.79), P(0.09, 0.83), P(0.11, 0.97)]
    d.polygon(skull, fill=body)
    # ears: short and rounded, set wide on the skull
    for u in (0.015, 0.065):
        tip = P(u - 0.012, 1.13)
        base_l = P(u - 0.035, 1.02)
        base_r = P(u + 0.030, 1.02)
        d.polygon([base_l, tip, base_r], fill=body)

    if variant != "silhouette":
        # dorsal stripe
        d.line([P(0.20, 1.00), P(0.50, 1.03), P(0.80, 0.98)], fill=shade,
               width=int(0.05 * L), joint="curve")
        # eye catching the light
        e = P(0.045, 0.97)
        d.ellipse([e[0] - 0.011 * L, e[1] - 0.011 * L,
                   e[0] + 0.011 * L, e[1] + 0.011 * L], fill=EYE)
        # fangs
        for k in range(3):
            a = P(-0.030 - k * 0.012, 0.845)
            b = P(-0.030 - k * 0.012, 0.805)
            d.line([a, b], fill=(238, 232, 214, 255), width=max(2, int(0.012 * L)))
    return layer
