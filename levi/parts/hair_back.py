"""Long back hair: white -> green wavy clumps from under the crown to the skirt.

Built from scratch as clumped strand ribbons: every clump is a Catmull-Rom
spine with a flattened lens cross-section (wide across the hair sheet, thin
through it) that tapers to a closed tip. Clumps are authored in reference
panel pixels so they can be fitted directly against ref/back.png and
ref/side.png:

    bx  : column in the BACK view   (image-left = character's left = +X)
    sx  : column in the SIDE view   (image-right = behind her = +Y)
    row : row shared by all panels  (z = (951 - row) / 643)

Points written as ('s', azimuth_deg, polar_deg, lift) sit on the skull
ellipsoid (azimuth 0 = straight back, +90 = character's left; polar 0 = top).
The scalp cap, bangs and face-framing side locks belong to hair_front; this
part starts just under the crown and hugs the back of the skull so the two
overlap without a gap.

Colour: toon_material('hair', gradient='hair_tip'); the 'toon_grad'
attribute is written per vertex from the arc-length position along each
clump (white roots, green tips), which matches the sheet better than a pure
height gradient: the short outer clumps behind the sleeves turn green much
higher up than the long centre clumps.
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

RING = 8            # vertices per cross-section
SEG_PX = 18.0       # target spine segment length (panel px)

def P(bx, sx, row):
    """Panel pixels (back-view column, side-view column, row) -> world Vector."""
    return Vector((spec.px_to_h(CX - bx), spec.px_to_h(sx - CX), spec.px_to_z(row)))

def skull(az, pol, lift=1.0):
    """Point on the (lifted) skull ellipsoid, returned in world space."""
    a, p = math.radians(az), math.radians(pol)
    cx, cy, cr = SKULL_C
    rx, ry, rz = (r * lift for r in SKULL_R)
    X = cx + rx * math.sin(p) * math.sin(a)
    Y = cy + ry * math.sin(p) * math.cos(a)
    row = cr - rz * math.cos(p)
    return Vector((spec.px_to_h(X), spec.px_to_h(Y), spec.px_to_z(row)))

def _pt(p):
    if p[0] == 's':
        return skull(*p[1:])
    return P(*p)

def catmull(pts, seg_px):
    """Uniform Catmull-Rom through pts, ~seg_px panel pixels per segment.

    Returns the dense spine (including both ends) and each sample's control
    parameter (span index + fraction) for interpolating per-control widths.
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

def _normal_hint(kind, p):
    if isinstance(kind, tuple):
        return Vector(kind).normalized()
    # 'radial': away from the body axis (slightly behind the spine)
    v = Vector((p.x, p.y + 0.02, 0.0))
    return v.normalized() if v.length > 1e-6 else Vector((0, 1, 0))

def clump(bm, layer, d):
    """Add one hair clump to bm.

    d: pts (control points), w (width px, one per point), th (thickness as a
    ratio of the width), n ('radial' or a fixed normal-hint tuple), g (arc
    length fractions where the green tip starts / is full).
    """
    ctrl = [_pt(p) for p in d['pts']]
    w = list(d['w'])
    assert len(w) == len(ctrl), 'one width per control point'
    th = [d.get('th', 0.4) * wi for wi in w]
    spine, par = catmull(ctrl, SEG_PX)
    n = len(spine)
    # arc length for gradient
    acc = [0.0]
    for a, b in zip(spine, spine[1:]):
        acc.append(acc[-1] + (b - a).length)
    total = acc[-1]
    g0, g1 = d.get('g', (0.6, 0.95))
    rings = []
    prev_side = None
    for i, p in enumerate(spine):
        t = (spine[min(i + 1, n - 1)] - spine[max(i - 1, 0)]).normalized()
        nh = _normal_hint(d.get('n', 'radial'), p)
        side = t.cross(nh)
        if side.length < 1e-4:
            side = prev_side if prev_side is not None else t.orthogonal()
        side.normalize()
        if prev_side is not None and side.dot(prev_side) < 0:
            side.negate()
        prev_side = side
        nrm = side.cross(t).normalized()
        u = par[i]
        ww = lerp_list(w, u) / PX / 2
        tt = lerp_list(th, u) / PX / 2
        if i == n - 1:  # pointed but non-degenerate tip
            ww, tt = max(ww, 0.4 / PX), max(tt, 0.25 / PX)
        ring = []
        for k in range(RING):
            a = 2 * math.pi * k / RING
            ca, sa = math.cos(a), math.sin(a)
            # lens profile: sharp edges at the sides, rounded faces
            ring.append(p + side * (ww * ca) + nrm * (tt * sa * (0.35 + 0.65 * abs(sa))))
        g = smooth01((acc[i] / total - g0) / max(1e-3, g1 - g0)) if total > 0 else 0.0
        rings.append((ring, g))
    verts = []
    for ring, g in rings:
        row = []
        for co in ring:
            v = bm.verts.new(co)
            v[layer] = g
            row.append(v)
        verts.append(row)
    for a, b in zip(verts, verts[1:]):
        for k in range(RING):
            k2 = (k + 1) % RING
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
    return e

# ------------------------------------------------------------------ clumps
# Targets measured on the reference (panel px):
#   back view, hair mass edges: r150 254/388, r170 247/393, r190 234/406,
#     r240 ~210/425, r300 ~210/420, r400 ~220/410; tip curls rows 420-510.
#   side view, back edge (sx): r100 366, r150 367, r180 376, r200 392,
#     r230 424 (flick), r250 397, r300 439, r330 450, r360 424, r380 412 with
#     the open curl 450-468 at rows 368-405, lower curl to 466 at rows 410-460.
#   front/back view hooks past the sleeves: outer edge bx 61-66 at rows
#     370-410, tip at (84, 347), bottom under the cuff around row 440.

# Back sheet: the main mass seen in the back view, from just under the crown
# to the green tips around the hips.  Listed from the character's left (+X,
# back-view image-left) to her right.  The S-waves alternate between
# neighbours so clumps cross like the sheet's wave outlines.
MAIN = [
    # left edge clump: ends in the big C curl at the bottom left
    dict(pts=[('s', 58, 34, .95), ('s', 62, 62, .96), ('s', 62, 92, .96), (266, 346, 150),
              (248, 356, 190), (226, 370, 240), (214, 390, 290), (220, 400, 340), (230, 398, 390),
              (234, 400, 430), (244, 402, 465), (262, 404, 484), (286, 404, 480), (298, 404, 462),
              (290, 404, 450)],
         w=[14, 18, 22, 24, 30, 40, 42, 40, 36, 30, 24, 18, 12, 6, 2.5], g=(0.66, 0.84)),
    dict(pts=[('s', 38, 28, .95), ('s', 42, 62, .96), ('s', 41, 94, .96), (285, 352, 150),
              (270, 364, 190), (255, 380, 240), (262, 406, 290), (250, 418, 340), (262, 404, 390),
              (274, 402, 430), (284, 402, 462), (282, 402, 478)],
         w=[14, 20, 24, 24, 32, 42, 42, 42, 38, 32, 24, 6], g=(0.68, 0.93)),
    dict(pts=[('s', 18, 25, .95), ('s', 21, 62, .96), ('s', 20, 95, .96), (303, 356, 150),
              (295, 370, 190), (287, 380, 240), (280, 414, 290), (293, 422, 340), (284, 400, 390),
              (298, 404, 430), (310, 402, 462), (304, 402, 484), (292, 402, 488)],
         w=[14, 20, 24, 24, 32, 42, 42, 42, 38, 32, 28, 20, 5], g=(0.7, 0.93)),
    dict(pts=[('s', 0, 24, .95), ('s', 0, 62, .96), ('s', 0, 95, .96), (322, 358, 150),
              (321, 372, 190), (318, 382, 240), (325, 418, 290), (312, 426, 340), (326, 400, 390),
              (332, 404, 430), (342, 402, 470), (352, 402, 500), (366, 402, 500)],
         w=[14, 20, 24, 24, 32, 42, 42, 42, 38, 32, 26, 16, 4], g=(0.7, 0.93)),
    # right-centre clump: sweeps right into the big curl at the bottom right
    dict(pts=[('s', -18, 25, .95), ('s', -21, 62, .96), ('s', -20, 95, .96), (341, 356, 150),
              (347, 370, 190), (349, 380, 240), (342, 414, 290), (357, 422, 340), (344, 400, 390),
              (366, 404, 430), (400, 404, 458), (430, 404, 462), (442, 402, 446), (436, 402, 436)],
         w=[14, 20, 24, 24, 32, 42, 42, 42, 38, 32, 24, 14, 6, 2], g=(0.68, 0.9)),
    dict(pts=[('s', -38, 28, .95), ('s', -42, 62, .96), ('s', -41, 94, .96), (359, 352, 150),
              (372, 364, 190), (381, 380, 240), (388, 406, 290), (374, 418, 340), (386, 404, 390),
              (404, 400, 420), (418, 398, 430)],
         w=[14, 20, 24, 24, 32, 42, 42, 42, 40, 30, 5], g=(0.62, 0.95)),
    # right edge clump
    dict(pts=[('s', -58, 34, .95), ('s', -62, 62, .96), ('s', -62, 92, .96), (378, 346, 150),
              (394, 356, 190), (410, 370, 240), (418, 390, 290), (410, 400, 340), (404, 398, 390),
              (406, 396, 415)],
         w=[14, 18, 22, 24, 30, 40, 42, 40, 34, 6], g=(0.6, 0.95)),
]

# Inner sheet: closer to the back, so the side view reads as a thick mass and
# no body shows through between the back clumps.
INNER_LEFT = [
    dict(pts=[('s', 30, 62, .93), ('s', 32, 95, .94), (272, 338, 150), (250, 340, 200),
              (236, 350, 260), (240, 358, 320), (252, 364, 380), (266, 364, 430), (276, 362, 455)],
         w=[22, 24, 24, 34, 42, 42, 40, 30, 4], th=0.35, g=(0.62, 0.95)),
]

# Side-view sweep: ribbons turned edge-on to the back view (broad in the side
# view) that bulge backwards and end in the two outward curls behind the
# skirt.
SWEEP = [
    # upper open curl: hole around sx 414-450, rows 375-402
    dict(pts=[('s', 10, 50, .93), ('s', 10, 92, .94), (310, 362, 150), (306, 378, 195),
              (302, 376, 250), (298, 420, 300), (300, 434, 335), (302, 410, 362), (304, 398, 385),
              (306, 408, 410), (308, 432, 416), (310, 456, 404), (310, 462, 385), (308, 454, 372),
              (306, 447, 368)],
         w=[8, 10, 12, 20, 32, 34, 32, 28, 22, 18, 14, 10, 7, 4, 2], th=0.4, n=(1, 0, 0),
         g=(0.6, 0.86)),
    # lower curl, rows 410-460
    dict(pts=[('s', -10, 50, .93), ('s', -10, 92, .94), (332, 362, 150), (336, 378, 195),
              (338, 376, 250), (342, 420, 300), (344, 434, 335), (340, 412, 365), (336, 400, 400),
              (336, 410, 435), (340, 432, 455), (342, 452, 452), (344, 460, 432), (342, 454, 418),
              (340, 446, 414)],
         w=[8, 10, 12, 20, 32, 34, 32, 28, 22, 16, 12, 8, 5, 3, 1.5], th=0.4, n=(1, 0, 0),
         g=(0.62, 0.86)),
]

# Outer side layer (mirrored pair): falls from the side of the head over the
# shoulders and fans out behind the sleeves.  Seen as the green flicks over
# the shoulders, the wavy clumps peeking out behind the sleeve tops and the
# big hooks that stick out past the sleeves in the front and back views.
OUTER_LEFT = [
    # shoulder flick: outer extremity ~(178, 230); flicks back to sx ~420
    dict(pts=[('s', 70, 80, .95), ('s', 72, 100, .95), (268, 340, 150), (246, 360, 192),
              (210, 384, 215), (190, 402, 232), (182, 410, 238), (178, 414, 229)],
         w=[16, 16, 12, 13, 14, 10, 5, 2], n=(0, 1, 0), g=(0.6, 0.95)),
    # clump behind the sleeve top, ends around (140, 334)
    dict(pts=[('s', 66, 95, .95), (270, 344, 150), (246, 354, 198), (214, 366, 240),
              (186, 378, 275), (162, 386, 300), (146, 390, 320), (140, 392, 334)],
         w=[16, 14, 14, 20, 26, 22, 14, 3], n=(0, 1, 0), g=(0.5, 0.92)),
    # big hook: hangs behind the sleeve to the cuff, then curls up and out
    dict(pts=[('s', 64, 100, .95), (268, 348, 155), (242, 358, 205), (212, 370, 250),
              (180, 382, 300), (150, 392, 350), (124, 398, 400), (108, 400, 428), (88, 400, 424),
              (75, 400, 402), (72, 400, 380), (75, 400, 365), (80, 400, 355), (85, 400, 347)],
         w=[16, 14, 14, 24, 30, 28, 24, 20, 18, 16, 15, 10, 6, 2], n=(0, 1, 0),
         g=(0.45, 0.8)),
]

# Backing curtain: one continuous shell under the clumps so the mass reads
# solid (no body showing between clumps) from the crown to the hips.  Rows
# above the skull equator wrap the back half of the skull; below, an arc
# that curves around the back.  (row, rx, ry, cy, half-angle deg), px; the
# back-most point is at sx = 320 + cy + ry, kept a few px inside the clumps.
CURTAIN_STEP = 11   # verts per arc (outer and inner surface each)
CURTAIN_T = 7.0     # shell thickness px

def _curtain_rows():
    rows = []
    lift = 0.94
    cx, cy, cr = SKULL_C
    for r in (40, 56, 74, 92, 110):
        dz = (r - cr) / (SKULL_R[2] * lift)
        s = math.sqrt(max(0.0, 1 - dz * dz))
        rows.append((r, SKULL_R[0] * lift * s, SKULL_R[1] * lift * s, cy, 92.0))
    rows += [
        (130, 68, 70, -30, 95), (150, 60, 60, -15, 90), (175, 70, 50, 0, 85),
        (200, 86, 45, 12, 85), (240, 100, 45, 11, 85), (290, 100, 50, 34, 82),
        (340, 98, 50, 48, 82), (390, 92, 45, 33, 82), (420, 80, 40, 34, 80),
        (432, 50, 26, 38, 75),
    ]
    return rows

def curtain(bm, layer):
    rows = _curtain_rows()
    m = CURTAIN_STEP
    verts = []
    for row, rx, ry, cy, ang in rows:
        A = math.radians(ang)
        ring = []
        for k in range(m):                       # outer (back) surface
            a = -A + 2 * A * k / (m - 1)
            ring.append((rx * math.sin(a), cy + ry * math.cos(a)))
        for k in range(m):                       # inner surface, reversed
            a = A - 2 * A * k / (m - 1)
            ring.append(((rx - CURTAIN_T) * math.sin(a), cy + (ry - CURTAIN_T) * math.cos(a)))
        g = smooth01((row - 370) / 70.0)
        vs = []
        for X, Y in ring:
            v = bm.verts.new(Vector((spec.px_to_h(X), spec.px_to_h(Y), spec.px_to_z(row))))
            v[layer] = g
            vs.append(v)
        verts.append(vs)
    n = 2 * m
    for a, b in zip(verts, verts[1:]):
        for k in range(n):
            k2 = (k + 1) % n
            bm.faces.new((a[k], a[k2], b[k2], b[k]))
    bm.faces.new(list(reversed(verts[0])))
    bm.faces.new(verts[-1])

def build(col):
    mat = common.toon_material('hair', gradient='hair_tip')
    defs = (MAIN + SWEEP + INNER_LEFT + [mirror(d) for d in INNER_LEFT]
            + OUTER_LEFT + [mirror(d) for d in OUTER_LEFT])
    bm = bmesh.new()
    layer = bm.verts.layers.float.new(common.GRAD_ATTR)
    curtain(bm, layer)
    for d in defs:
        clump(bm, layer, d)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    obj = common.new_object(col, 'hair_back', bm, [mat])
    common.shade_smooth(obj, angle_deg=70.0)
    common.add_outline(obj)
    # The inverted-hull outline encloses the mesh, so if the object casts
    # shadows the hull shadows the whole hair and only the shade tone ever
    # renders.  Cel style needs no cast shadows from the hair anyway.
    obj.visible_shadow = False
    return obj
