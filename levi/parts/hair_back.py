"""Long back hair: white -> green wavy clumps from under the crown to the skirt.

Built from scratch as clumped strand ribbons: every clump is a Catmull-Rom
spine with a flattened lens cross-section (wide across the hair sheet, thin
through it) that tapers to a closed tip. Clumps are authored in reference
panel pixels so they can be fitted directly against ref/back.png and
ref/side.png:

    bx  : column in the BACK view   (image-left = character's left = +X)
    sx  : column in the SIDE view   (image-right = behind her = +Y)
    row : row shared by all panels  (z = (951 - row) / 643)

Control points can be written as
    ('s', azimuth_deg, polar_deg, lift)  on the skull ellipsoid (azimuth 0 =
                                         straight back, +90 = character's left)
    (bx, row)                            on the back surface of the hair mass:
                                         the depth comes from mass_sx(), which
                                         also keeps the hair clear of the skirt
    (bx, sx, row)                        explicit.
A clump may end in a rounded hook: the spine keeps turning at a constant rate
in a plane given by its start direction and a horizontal curl direction, so
the tips curl like the sheet's (back view: in the image plane; side view:
curling backwards behind the skirt).

The scalp cap, bangs and face-framing side locks belong to hair_front; this
part starts just under the crown and hugs the back of the skull so the two
overlap without a gap. A backing curtain under the clumps keeps the mass
solid from the crown to the hips.

Colour: toon_material('hair', gradient='hair_tip'); the 'toon_grad'
attribute is a smooth function of the panel row per clump (the sheet's green
starts at about the same height across the mass), made monotonic along each
spine so hooks that curl back up stay green.
"""
import math

import bmesh
from mathutils import Vector

from .. import common, spec

PX = spec.PX_PER_M
CX = spec.PANEL_W / 2

# Skull ellipsoid in panel px (re-measured on ref/back.png + ref/side.png:
# back view hair is +-74 px wide at row 100, side view back of head at sx 367,
# hair top at row ~22).  Centre depth follows spec.L['head_center_y'].
SKULL_C = (0.0, spec.L['head_center_y'] * spec.PX_PER_M, 108.0)   # (X px, Y px, row)
SKULL_R = (72.0, 82.0, 86.0)         # (rx, ry, rz) px

RING = 8            # vertices per cross-section (default)
SEG_PX = 16.0       # target spine segment length (panel px)

# Back surface of the hair mass (side-view column on the centre line) per
# row, from the back edge of the hair in ref/side.png minus the clump
# thickness; it falls off to the sides by MASS_FALL px at 110 px off-centre.
MASS_BACK = [(140, 358), (170, 364), (200, 372), (230, 382), (260, 398), (290, 420),
             (320, 432), (350, 428), (380, 414), (420, 402), (520, 400)]
MASS_FALL = 30.0
# Skirt back surface (measured on a hair-less render of the full model):
# row -> (centre column, half depth); the half width is SKIRT_AR x the depth.
SKIRT = [(370, 300, 60), (400, 298, 86), (440, 306, 105), (470, 313, 120),
         (500, 318, 142), (530, 320, 160)]
SKIRT_AR = 1.5
SKIRT_GAP = 8.0     # px kept between the skirt and the hair spine
HOOK_LAY = 2.0      # px a back-view hook sits above its clump's layer
HOOK_TH = 0.45      # hook thickness / width


def P(bx, sx, row):
    """Panel pixels (back-view column, side-view column, row) -> world Vector."""
    return Vector((spec.px_to_h(CX - bx), spec.px_to_h(sx - CX), spec.px_to_z(row)))


def to_px(v):
    """World Vector -> (bx, sx, row) panel pixels."""
    return CX - v.x * PX, CX + v.y * PX, spec.SHEET_GROUND_Y - v.z * PX


def skull(az, pol, lift=1.0):
    """Point on the (lifted) skull ellipsoid, returned in world space."""
    a, p = math.radians(az), math.radians(pol)
    cx, cy, cr = SKULL_C
    rx, ry, rz = (r * lift for r in SKULL_R)
    X = cx + rx * math.sin(p) * math.sin(a)
    Y = cy + ry * math.sin(p) * math.cos(a)
    row = cr - rz * math.cos(p)
    return Vector((spec.px_to_h(X), spec.px_to_h(Y), spec.px_to_z(row)))


def table(tab, row):
    """Piecewise-linear lookup in [(row, v...), ...] (clamped)."""
    if row <= tab[0][0]:
        return tab[0][1:]
    for (r0, *a), (r1, *b) in zip(tab, tab[1:]):
        if row <= r1:
            u = (row - r0) / (r1 - r0)
            return tuple(x + (y - x) * u for x, y in zip(a, b))
    return tab[-1][1:]


def skirt_sx(bx, row):
    """Side-view column of the skirt's back surface at back-view column bx
    (None above or beside the skirt)."""
    if row < SKIRT[0][0]:
        return None
    c, b = table(SKIRT, row)
    u = abs(bx - CX) / (SKIRT_AR * b)
    if u >= 1.0:
        return None
    return c + b * math.sqrt(1.0 - u * u)


def mass_sx(bx, row, lay=0.0):
    """Depth of the hair mass's back surface at back-view (bx, row)."""
    sx = table(MASS_BACK, row)[0] - MASS_FALL * ((bx - CX) / 110.0) ** 2 + lay
    sk = skirt_sx(bx, row)
    if sk is not None:
        sx = max(sx, sk + SKIRT_GAP + max(lay, 0.0))
    return sx


def clear_skirt(p):
    """Push a world point back (+Y) until it clears the skirt."""
    bx, sx, row = to_px(p)
    sk = skirt_sx(bx, row)
    if sk is not None and sx < sk + SKIRT_GAP:
        p = P(bx, sk + SKIRT_GAP, row)
    return p


def _pt(p, lay):
    if p[0] == 's':
        return skull(*p[1:])
    if len(p) == 2:
        return P(p[0], mass_sx(p[0], p[1], lay), p[1])
    return P(*p)


def catmull(pts, seg_px):
    """Uniform Catmull-Rom through pts, ~seg_px panel pixels per segment.

    Returns the dense spine (including both ends) and each sample's control
    parameter (span index + fraction) for interpolating per-control values.
    """
    ext = [pts[0] * 2 - pts[1]] + pts + [pts[-1] * 2 - pts[-2]]
    out, par = [], []
    for i in range(len(pts) - 1):
        p0, p1, p2, p3 = ext[i:i + 4]
        samples = max(1, min(8, math.ceil((p2 - p1).length * PX / seg_px)))
        for k in range(samples):
            t = k / samples
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
            par.append(i + t)
    out.append(pts[-1].copy())
    par.append(len(pts) - 1)
    return out, par


def lerp_list(vals, u):
    """Piecewise-linear lookup of vals at control parameter u."""
    i = min(int(u), len(vals) - 2)
    f = u - i
    return vals[i] * (1 - f) + vals[i + 1] * f


def smooth01(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def _radial(p):
    """Away from the body axis (slightly behind the spine)."""
    v = Vector((p.x, p.y + 0.02, 0.0))
    return v.normalized() if v.length > 1e-6 else Vector((0, 1, 0))


def hook(ctrl, curl, lay, on_mass):
    """Append a rounded hook to the control points `ctrl` (world, in place).

    curl = (radius_px, turn_deg, (img_x, depth)[, steps]): the spine turns by
    turn_deg towards the horizontal direction img_x * (back-view image right)
    + depth * (+Y, behind her), on a spiral whose radius shrinks to 70 %.
    Hooks that curl in the image plane (depth == 0) of clumps laid on the
    mass (on_mass) follow the mass surface HOOK_LAY px above the clump's
    layer so they read over their neighbours; the others keep their 3D curl
    and only clear the skirt.
    Returns the normal hints (curl-plane normal) for the new points.
    """
    R, turn, (ix, iy), *rest = curl
    steps = rest[0] if rest else max(3, round(turn / 22.0))
    d = ctrl[-1] - ctrl[-2]
    if iy == 0 and abs(d.x) + abs(d.z) > 1e-9:   # curl in the back-view image plane
        d.y = 0.0
    d.normalize()
    e = Vector((-ix, iy, 0.0))
    e = (e - d * e.dot(d)).normalized()
    nrm = d.cross(e).normalized()
    if nrm.dot(_radial(ctrl[-1])) < 0:
        nrm.negate()
    dth = math.radians(turn) / steps
    p = ctrl[-1].copy()
    hints = []
    for k in range(steps):
        r = R * (1.0 - 0.3 * (k + 0.5) / steps) / PX
        th = dth * (k + 0.5)
        p = p + (d * math.cos(th) + e * math.sin(th)) * (r * dth)
        if iy == 0 and on_mass:
            bx, _, row = to_px(p)
            ctrl.append(P(bx, mass_sx(bx, row, lay + HOOK_LAY), row))
        else:
            ctrl.append(clear_skirt(p))
        hints.append(nrm)
    return hints


def clump(bm, layer, d):
    """Add one hair clump to bm.

    d: pts (control points), w (width px, one per point), th (thickness as a
    ratio of the width), lay (depth offset px for (bx, row) points), n
    ('radial' or a fixed normal-hint tuple), curl (optional hook, see hook()),
    tip (width of the hook tip px), gr (rows where the green starts / is full).
    """
    lay = d.get('lay', 0.0)
    ctrl = [_pt(p, lay) for p in d['pts']]
    w = list(d['w'])
    assert len(w) == len(ctrl), 'one width per control point'
    n = d.get('n', 'radial')
    hints = [Vector(n).normalized() if isinstance(n, tuple) else _radial(c) for c in ctrl]
    if 'curl' in d:
        hints += hook(ctrl, d['curl'], lay, len(d['pts'][-1]) == 2)
        n_new = len(ctrl) - len(w)
        w0, w1 = w[-1], d.get('tip', 2.0)
        # hold the width round the bend, then taper into the tip
        w += [w0 + (w1 - w0) * smooth01((k + 1) / n_new) ** 1.6 for k in range(n_new)]
    th = [d.get('th', 0.32) * wi for wi in w]
    if 'curl' in d:
        # slightly rounder section through the hook so its edge turned away
        # from the light takes the shade tone
        n_old = len(d['w'])
        th[n_old:] = [HOOK_TH * wi for wi in w[n_old:]]
    nr = d.get('ring', RING)
    spine, par = catmull(ctrl, SEG_PX)
    ns = len(spine)
    r0, r1 = d.get('gr', (380, 450))
    rings = []
    prev_side = None
    gmax = 0.0
    for i, p in enumerate(spine):
        t = (spine[min(i + 1, ns - 1)] - spine[max(i - 1, 0)]).normalized()
        u = par[i]
        nh = lerp_list(hints, u)
        side = t.cross(nh)
        if side.length < 1e-4:
            side = prev_side if prev_side is not None else t.orthogonal()
        side.normalize()
        if prev_side is not None and side.dot(prev_side) < 0:
            side.negate()
        prev_side = side
        nrm = side.cross(t).normalized()
        ww = lerp_list(w, u) / PX / 2
        tt = lerp_list(th, u) / PX / 2
        if i == ns - 1:  # pointed but non-degenerate tip
            ww, tt = max(ww, 0.4 / PX), max(tt, 0.25 / PX)
        ring = []
        for k in range(nr):
            a = 2 * math.pi * k / nr
            ca, sa = math.cos(a), math.sin(a)
            # lens profile: sharp edges at the sides, rounded faces
            ring.append(p + side * (ww * ca) + nrm * (tt * sa * (0.35 + 0.65 * abs(sa))))
        row = spec.SHEET_GROUND_Y - p.z * PX
        gmax = max(gmax, smooth01((row - r0) / (r1 - r0)))
        rings.append((ring, gmax))
    verts = []
    for ring, g in rings:
        vs = []
        for co in ring:
            v = bm.verts.new(co)
            v[layer] = g
            vs.append(v)
        verts.append(vs)
    for a, b in zip(verts, verts[1:]):
        for k in range(nr):
            k2 = (k + 1) % nr
            bm.faces.new((a[k], a[k2], b[k2], b[k]))
    bm.faces.new(list(reversed(verts[0])))
    bm.faces.new(verts[-1])


def mirror(d):
    """Mirror a clump definition across the character's midline."""
    e = dict(d)
    pts = []
    for p in d['pts']:
        if p[0] == 's':
            pts.append(('s', -p[1]) + tuple(p[2:]))
        else:
            pts.append((2 * CX - p[0],) + tuple(p[1:]))
    e['pts'] = pts
    if isinstance(d.get('n'), tuple):
        x, y, z = d['n']
        e['n'] = (-x, y, z)
    if 'curl' in d:
        R, turn, (ix, iy), *rest = d['curl']
        e['curl'] = (R, turn, (-ix, iy), *rest)
    return e


# ------------------------------------------------------------------ clumps
# Targets measured on the reference (panel px):
#   back view, main mass edges: r150 252/387, r200 256/385 (bare shoulder
#     skin at bx 233-250 between the mass and the shoulder lock), r250 251/391,
#     r300 231/410, r320 219/418, r350-400 ~212/422.  Lower third: two lobes
#     split at bx ~305; left lobe ends in a big C hook (outer edge 220 at
#     row 450, bottom (262, 495), tip (302, 460)); right lobe: an S lock that
#     hooks at the right edge (417, 402), a curl bottoming at (365, 510) with
#     its tip back at (335, 492), and an outer curl out to (437, 460) with
#     its tip at (400, 492).  Green starts ~row 375 (right) / 395 (left).
#   side view, back edge (sx): r150 367, r200 392, r230 424 (shoulder flick),
#     r250 397, r300 439, r330 450, r360 424 with the open curl 450-468 at
#     rows 368-405 and the lower curl to 466 at rows 410-460.
#   front/back view hooks past the sleeves: outer edge bx 61-66 at rows
#     370-410, tip at (84, 347).

# Main back mass, from the character's left (+X, back-view image-left) to
# her right.  Widths overlap their neighbours so the mass reads as one; the
# S-waves alternate between neighbours so the clump outlines cross.
MAIN = [
    # A: left edge -> big C hook at the bottom left
    dict(pts=[('s', 60, 34, .95), ('s', 62, 62, .96), ('s', 62, 92, .96), (260, 150),
              (252, 195), (246, 240), (236, 285), (224, 325), (216, 365), (215, 400),
              (220, 435), (230, 462)],
         w=[16, 20, 24, 28, 32, 38, 44, 46, 46, 42, 36, 30],
         curl=(32, 200, (1, 0), 10), tip=2.0, gr=(380, 445)),
    # B: left inner, tucks in behind the C hook
    dict(pts=[('s', 40, 28, .95), ('s', 42, 62, .96), ('s', 41, 94, .96), (280, 150),
              (274, 195), (268, 240), (258, 290), (248, 335), (254, 372), (270, 404),
              (282, 432), (286, 452)],
         w=[16, 20, 24, 28, 34, 40, 46, 50, 50, 44, 30, 4], gr=(385, 452), lay=3),
    # C: along the central parting, tucks under the hooks
    dict(pts=[('s', 18, 25, .95), ('s', 21, 62, .96), ('s', 20, 95, .96), (302, 150),
              (299, 195), (296, 240), (292, 290), (288, 330), (292, 368), (300, 404),
              (304, 438), (300, 470)],
         w=[16, 20, 24, 28, 34, 40, 44, 46, 46, 40, 30, 3], gr=(380, 450), lay=-2),
    # D: right of the parting -> curl at the bottom (365, 510)
    dict(pts=[('s', -2, 24, .95), ('s', -2, 62, .96), ('s', -2, 95, .96), (322, 150),
              (326, 195), (330, 240), (336, 290), (334, 330), (328, 368), (334, 406),
              (346, 438), (356, 464), (362, 482)],
         w=[16, 20, 24, 28, 34, 40, 46, 50, 50, 44, 36, 28, 24],
         curl=(22, 215, (-1, 0), 10), tip=2.0, gr=(365, 432), lay=2),
    # E: S lock that sweeps right and hooks at the right edge
    dict(pts=[('s', -20, 25, .95), ('s', -21, 62, .96), ('s', -20, 95, .96), (342, 150),
              (348, 195), (354, 240), (362, 290), (368, 328), (382, 356), (400, 376),
              (414, 394)],
         w=[16, 20, 24, 28, 34, 40, 46, 44, 38, 30, 24],
         curl=(22, 190, (-1, 0), 8), tip=2.0, gr=(352, 400), lay=4),
    # F: right outer -> outer curl at the bottom right
    dict(pts=[('s', -40, 28, .95), ('s', -42, 62, .96), ('s', -41, 94, .96), (360, 150),
              (368, 195), (378, 240), (392, 290), (406, 330), (416, 370), (420, 406),
              (426, 436), (432, 466)],
         w=[16, 20, 24, 28, 34, 40, 44, 46, 44, 40, 32, 26],
         curl=(24, 200, (-1, 0), 9), tip=2.0, gr=(362, 430)),
    # G: right edge, tucked in under F
    dict(pts=[('s', -60, 34, .95), ('s', -62, 62, .96), ('s', -62, 92, .96), (380, 150),
              (386, 195), (392, 240), (402, 290), (412, 330), (418, 370), (414, 404),
              (406, 430)],
         w=[16, 20, 24, 28, 34, 40, 44, 42, 38, 30, 4], gr=(362, 430), lay=-3),
]

# Wave locks on top of the mass: narrower clumps with stronger S-waves that
# draw the sheet's interior wave lines across the lobes.
WAVES = [
    dict(pts=[('s', 30, 50, .97), ('s', 30, 92, .97), (284, 160), (276, 215), (266, 270),
              (252, 318), (244, 352), (254, 384), (272, 410), (282, 432)],
         w=[12, 16, 20, 22, 24, 26, 26, 24, 18, 3], gr=(382, 445), lay=7, ring=6),
    dict(pts=[('s', -10, 50, .97), ('s', -10, 92, .97), (328, 160), (334, 215), (342, 270),
              (350, 315), (352, 350), (346, 384), (352, 414), (366, 438)],
         w=[12, 16, 20, 22, 24, 26, 26, 24, 20, 14],
         curl=(12, 130, (1, 0), 4), tip=1.5, gr=(365, 432), lay=7, ring=6),
    dict(pts=[('s', -36, 50, .97), ('s', -38, 92, .97), (364, 160), (372, 215), (380, 268),
              (392, 312), (398, 350), (392, 384), (396, 414), (406, 436)],
         w=[12, 16, 20, 22, 24, 26, 24, 22, 16, 3], gr=(360, 428), lay=7, ring=6),
]

# Inner sheet: closer to the back, so the side view reads as a thick mass and
# no body shows through between the back clumps.
INNER_LEFT = [
    dict(pts=[('s', 30, 62, .93), ('s', 32, 95, .94), (272, 338, 150), (250, 340, 200),
              (236, 350, 260), (236, 360, 320), (244, 372, 380), (258, 382, 430),
              (270, 390, 458)],
         w=[22, 24, 24, 34, 42, 44, 42, 32, 4], th=0.35, gr=(380, 450), ring=6),
]

# Side-view curls: ribbons broad in the side view that bulge backwards and
# end in the curls behind the skirt; their hooks curl backwards (+Y) so they
# read as curls from the side and as compact green tips from the back.  They
# face sideways, so they keep most of their own normals (keep) rather than
# the back-facing volume normal.
SWEEP = [
    # upper open curl: hole around sx 414-450, rows 375-402
    dict(pts=[('s', 10, 50, .93), ('s', 10, 92, .94), (312, 362, 150), (310, 378, 195),
              (308, 380, 250), (306, 416, 300), (306, 430, 335), (306, 410, 362),
              (306, 400, 386), (306, 408, 410)],
         w=[8, 10, 12, 20, 30, 34, 34, 32, 30, 28], th=0.25, n=(1, 0, 0),
         curl=(21, 280, (0, 1), 12), tip=2.0, gr=(330, 400), ring=6, keep=0.8),
    # lower curl, rows 410-460
    dict(pts=[('s', -10, 50, .93), ('s', -10, 92, .94), (334, 362, 150), (336, 378, 195),
              (338, 380, 250), (340, 418, 300), (342, 430, 335), (342, 416, 370),
              (346, 414, 400), (350, 430, 436)],
         w=[8, 10, 12, 20, 30, 34, 32, 28, 26, 24], th=0.25, n=(1, 0, 0),
         curl=(16, 240, (0, 1), 10), tip=1.5, gr=(330, 405), ring=6, keep=0.8),
]

# Outer side layer (mirrored pair): falls from the side of the head over the
# shoulders and hangs along the top of the sleeves.  Seen as the green-tipped
# flicks over the shoulders, the lock peeking out above the sleeve top and
# the big hooks that stick out past the sleeves in the front and back views.
OUTER_LEFT = [
    # shoulder flick: outer extremity ~(178, 230); flicks back to sx ~420
    dict(pts=[('s', 70, 80, .95), ('s', 72, 100, .95), (268, 340, 150), (246, 360, 192),
              (210, 384, 215), (190, 402, 232)],
         w=[16, 16, 14, 16, 18, 14], n=(0, 1, 0),
         curl=(8, 150, (1, 0), 5), tip=2.0, gr=(205, 245), ring=6),
    # lock behind the sleeve top, ends around (140, 334)
    dict(pts=[('s', 66, 95, .95), (270, 344, 150), (246, 354, 198), (214, 366, 240),
              (186, 378, 275), (162, 386, 300), (146, 390, 320), (140, 392, 334)],
         w=[16, 14, 14, 20, 26, 22, 14, 3], n=(0, 1, 0), gr=(285, 335), ring=6),
    # big hook: hangs behind the sleeve to the cuff, then curls up and out
    dict(pts=[('s', 64, 100, .95), (268, 348, 155), (242, 358, 205), (212, 370, 250),
              (180, 382, 300), (150, 392, 350), (124, 398, 400), (110, 400, 424), (96, 400, 431), (82, 400, 420),
              (75, 400, 402), (72, 400, 380), (75, 400, 365), (80, 400, 355), (85, 400, 347)],
         w=[16, 14, 14, 24, 30, 28, 24, 21, 19, 17, 16, 15, 10, 6, 2], n=(0, 1, 0),
         gr=(320, 410), ring=6),
]

# Backing curtain: one continuous shell under the clumps so the mass reads
# solid (no body showing between clumps) from the crown to the hips.  Rows
# above the skull equator wrap the back half of the skull; below, an arc
# that follows the mass surface a few px inside the clumps.
CURTAIN_STEP = 11   # verts per arc (outer and inner surface each)
CURTAIN_T = 7.0     # shell thickness px
CURTAIN_INSET = 7.0
CURTAIN_WRAP = 40.0  # px the arc curls forward at its side edges
# row -> half width of the curtain arc below the skull (px)
CURTAIN_HW = [(175, 62), (200, 62), (240, 66), (280, 78), (320, 92), (360, 96),
              (400, 96), (425, 88), (442, 56)]


def _curtain_rows():
    """[(row, [(X px, Y px), ...] outer->inner loop)]."""
    rows = []
    lift = 0.94
    cx, cy, cr = SKULL_C
    m = CURTAIN_STEP

    def arc(rx, ry, cyy, ang):
        A = math.radians(ang)
        out = [(rx * math.sin(-A + 2 * A * k / (m - 1)), cyy + ry * math.cos(-A + 2 * A * k / (m - 1)))
               for k in range(m)]
        inn = [((rx - CURTAIN_T) * math.sin(A - 2 * A * k / (m - 1)),
                cyy + (ry - CURTAIN_T) * math.cos(A - 2 * A * k / (m - 1))) for k in range(m)]
        return out + inn

    for r in (40, 56, 74, 92, 110):
        dz = (r - cr) / (SKULL_R[2] * lift)
        s = math.sqrt(max(0.0, 1 - dz * dz))
        rows.append((r, arc(SKULL_R[0] * lift * s, SKULL_R[1] * lift * s, cy, 92.0)))
    rows.append((130, arc(68, 70, -30, 95)))
    rows.append((150, arc(60, 60, -15, 90)))
    for r, hw in CURTAIN_HW:
        out, inn = [], []
        for k in range(m):
            a = -1.0 + 2.0 * k / (m - 1)            # -1..1 across the arc
            X = hw * math.sin(a * math.pi / 2)
            wrap = CURTAIN_WRAP * (1 - math.cos(a * math.pi / 2))
            sx = mass_sx(CX - X, r) - CURTAIN_INSET - wrap
            sk = skirt_sx(CX - X, r)
            if sk is not None:          # keep the inner surface outside the skirt
                sx = max(sx, sk + CURTAIN_T + 2.0)
            Y = sx - CX
            out.append((X, Y))
            inn.append((X * (hw - CURTAIN_T) / hw, Y - CURTAIN_T))
        rows.append((r, out + inn[::-1]))
    return rows


def curtain(bm, layer):
    verts = []
    for row, loop in _curtain_rows():
        g = smooth01((row - 368) / 65.0)
        vs = []
        for X, Y in loop:
            v = bm.verts.new(Vector((spec.px_to_h(X), spec.px_to_h(Y), spec.px_to_z(row))))
            v[layer] = g
            vs.append(v)
        verts.append(vs)
    n = 2 * CURTAIN_STEP
    for a, b in zip(verts, verts[1:]):
        for k in range(n):
            k2 = (k + 1) % n
            bm.faces.new((a[k], a[k2], b[k2], b[k]))
    bm.faces.new(list(reversed(verts[0])))
    bm.faces.new(verts[-1])


# ---------------------------------------------------------------- normals
# Same approach as hair_front: the custom normals are mostly the normal of one smooth
# volume (the skull ellipsoid above its centre, a vertical elliptic cylinder
# below it for the hanging mass) plus VOL_KEEP of each strand's own normal,
# so the hair reads as one lit mass with thin shade accents along the clump
# edges and no shading seam where it meets hair_front.
VOL_AXES_LOW = (110.0, 80.0)   # cylinder half axes (X, Y) px below the skull
VOL_KEEP = 0.3


def volume_normal(co):
    cx, cy, cr = SKULL_C
    dx = co.x * PX - cx
    dy = co.y * PX - cy
    dz = (cr - (spec.SHEET_GROUND_Y - co.z * PX))      # + above the skull centre
    if dz > 0:
        rx, ry, rz = SKULL_R
        n = Vector((dx / rx ** 2, dy / ry ** 2, dz / rz ** 2))
    else:
        ax, ay = VOL_AXES_LOW
        n = Vector((dx / ax ** 2, dy / ay ** 2, 0.0))
    return n.normalized() if n.length > 1e-12 else Vector((0.0, 1.0, 0.0))


def set_volume_normals(me, keep_of=None):
    """keep_of: optional {vertex index: share of the own normal} overrides."""
    keep_of = keep_of or {}
    normals = []
    for v in me.vertices:
        keep = keep_of.get(v.index, VOL_KEEP)
        n = volume_normal(v.co) * (1 - keep) + v.normal * keep
        normals.append(n.normalized() if n.length > 1e-9 else Vector(v.normal))
    me.normals_split_custom_set_from_vertices(normals)


def build(col):
    mat = common.toon_material('hair', gradient='hair_tip')
    defs = (INNER_LEFT + [mirror(d) for d in INNER_LEFT] + MAIN + SWEEP + WAVES
            + OUTER_LEFT + [mirror(d) for d in OUTER_LEFT])
    bm = bmesh.new()
    layer = bm.verts.layers.float.new(common.GRAD_ATTR)
    curtain(bm, layer)
    keep_of = {}
    for d in defs:
        v0 = len(bm.verts)
        clump(bm, layer, d)
        if 'keep' in d:
            keep_of.update((i, d['keep']) for i in range(v0, len(bm.verts)))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    obj = common.new_object(col, 'hair_back', bm, [mat])
    common.shade_smooth(obj, angle_deg=70.0)
    set_volume_normals(obj.data, keep_of)
    common.add_outline(obj)
    return obj
