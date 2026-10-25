"""Shoes: green pointed-toe stiletto pumps with criss-cross ankle ribbons,
a small bow at the front of each ankle and a pair of leaves at the back/outer
side of each ankle. The outsole between the ball and the heel seat is the
sheet's pale tan (seen in the back view either side of the stiletto); the heel
cup tapers toward the topline so the back view reads as a slim pump.

Every shell station keeps the body's foot (body.FOOT) inside it with >= ~0 px
clearance below the opening, so no skin pokes through in the three views.

Everything is laid out in reference-panel pixels (1 px = 1/643 m) as measured
from ref/front.png, ref/side.png and ref/back.png, then mapped to world space.
The left shoe (+X) is built and mirrored for the right one.

Local landmark corrections (spec.L is a +-3 px first pass):
  * toe tip: side col 227 -> y = -93 px (spec toe_tip_y = -95 px); front view
    toe points at x = +-15 px (spec toe_tip_x = 22 px).
  * shoe centre x = 28 px at the heel, 27 px across the ball (spec
    ankle_center_x = 35 px is the ankle, which sits further out).
  * heel back y = +22 px (counter, side col 342); stiletto between
    y = +7..+17 px (spec heel_back_y = 15 px).
  * heel seat at row 899 -> heel height ~49 px (spec heel_height = 55 px).
  * the side panel's soles sit at row ~945 while the front/back toe and heel
    tips reach row 951 (the sheet is drawn with a slight top-down
    perspective).  Rows below 850 are squeezed so the sole lands ~4 px above
    the ground: within 3 px of the side profile and of the front/back tips.
"""
import math

import bmesh
from mathutils import Vector

from .. import common, spec

PX = 1.0 / spec.PX_PER_M

# Rows below SQUEEZE_ROW are mapped so that side-view row SOLE_ROW lands at
# SOLE_LIFT px above the ground (see module docstring).
SQUEEZE_ROW = 850.0
SOLE_ROW = 944.5
SOLE_LIFT = 3.5
_K = ((spec.SHEET_GROUND_Y - SQUEEZE_ROW) - SOLE_LIFT) / (SOLE_ROW - SQUEEZE_ROW)


def zrow(row):
    """Reference row -> world z (m)."""
    if row <= SQUEEZE_ROW:
        return (spec.SHEET_GROUND_Y - row) * PX
    return ((spec.SHEET_GROUND_Y - SQUEEZE_ROW) - (row - SQUEEZE_ROW) * _K) * PX


def P(x, y, row, sx=1):
    """Panel px (x: +outer for the left shoe, y: side-view offset, row) -> world."""
    return Vector((sx * x * PX, y * PX, zrow(row)))


# ---------------------------------------------------------------- shell
# Stations along the shoe, toe -> heel, panel px:
#   y, centre x, half width, sole row, top row, opening angle (fraction of pi),
#   inward skew of the sole (px; the front view narrows to a V on the inner side),
#   pinch (0..1: the upper half narrows toward the opening -> tapered heel cup
#   in the back view), keel (px the sole corners are lifted -> pointed V bottom
#   in the front view), inner-wall raise (px: the inner side of the opening
#   sits higher than the outer one, hidden in the side view)
# Closed toe box: frac = 1 (ring ends meet on the top centre line, top row =
# toe-box top).  Open stations: ring ends sit on the topline at `top row`.
STATIONS = [
    (-90.0, 16.0, 2.6, 943.8, 938.8, 1.0, 0.0, 0.0, 0.0, 0.0),
    (-85.0, 18.0, 6.0, 944.5, 935.0, 1.0, 2.0, 0.0, 1.5, 0.0),
    (-78.0, 20.5, 10.0, 944.5, 930.5, 1.0, 4.0, 0.0, 2.0, 0.0),
    (-70.0, 22.5, 13.6, 944.5, 926.5, 1.0, 5.0, 0.0, 2.5, 0.0),
    (-62.0, 24.0, 16.0, 944.5, 922.0, 1.0, 3.0, 0.0, 3.0, 0.0),
    (-57.0, 24.6, 18.0, 944.5, 920.0, 0.88, 3.0, 0.0, 3.0, 3.0),
    (-50.0, 25.5, 18.0, 944.5, 918.0, 0.75, 3.0, 0.0, 4.0, 6.0),
    (-40.0, 26.5, 18.6, 944.5, 916.5, 0.67, 3.0, 0.0, 4.5, 8.0),
    (-30.0, 27.0, 18.0, 944.5, 916.5, 0.67, 3.0, 0.0, 4.5, 8.0),
    (-23.0, 28.5, 17.0, 942.0, 915.0, 0.67, 2.5, 0.0, 3.0, 6.0),
    (-18.0, 29.5, 15.5, 932.0, 903.0, 0.67, 1.5, 0.0, 0.0, 3.0),
    (-13.0, 30.0, 14.5, 920.0, 893.0, 0.67, 1.0, 0.0, 0.0, 0.0),
    (-8.0, 30.0, 14.0, 910.0, 884.0, 0.67, 0.0, 0.1, 0.0, 0.0),
    (-3.0, 30.0, 13.5, 903.0, 876.0, 0.67, 0.0, 0.15, 0.0, 0.0),
    (2.0, 30.0, 13.0, 899.5, 869.0, 0.67, 0.0, 0.12, 0.0, 0.0),
    (7.0, 30.0, 12.5, 899.0, 865.0, 0.67, 0.0, 0.3, 0.0, 0.0),
    (12.0, 30.0, 11.5, 899.0, 860.0, 0.67, 0.0, 0.65, 0.0, 0.0),
    (16.0, 30.0, 10.0, 899.5, 858.0, 0.67, 0.0, 0.6, 0.0, 0.0),
    (19.0, 30.0, 7.5, 896.0, 857.5, 0.67, 0.0, 0.6, 0.0, 0.0),
    (21.5, 30.0, 4.5, 888.0, 859.0, 0.67, 0.0, 0.5, 0.0, 0.0),
]
# Sole underside (back view: the pale tan outsole between the forefoot walls
# and the stiletto): ring segments SOLE_SEGS of the stations from the ball to
# the heel seat get the sole material.
SOLE_Y = (-23.0, -8.0)
SOLE_SEGS = range(3, 7)
# There is no tan palette key; the sole uses the shoe key blended toward
# 'skin' (toon_material gradient) by SOLE_MIX, which lands on the sheet's
# sole tan (#938B70 shade) within a few dE.
SOLE_MIX = 0.31
TOE_TIP = (15.0, -93.0, 941.5)
BACK_Y = 22.5
RING = 11          # verts per cross-section (10 segments)
SQUARE = 0.7       # superellipse exponent (<1: boxier section)


def _spow(v, p):
    return math.copysign(abs(v) ** p, v)


def _ring(st, sx):
    y, cx, hw, zb, zt, frac, skew, pinch, keel, rin = st
    assert 0.5 <= frac <= 1.0, 'ring ends must be on the upper half of the section'
    phim = math.pi * frac
    zb_m, zt_m = zrow(zb), zrow(zt)
    hh = (zt_m - zb_m) / (1.0 + abs(math.cos(phim)) ** SQUARE)
    zmid = zb_m + hh
    pts = []
    cend = max(1e-6, -math.cos(phim))
    for k in range(RING):
        phi = phim * (2.0 * k / (RING - 1) - 1.0)
        s, c = math.sin(phi), math.cos(phi)
        xo = hw * _spow(s, SQUARE)
        if c < 0.0:     # upper half: pinch toward the centre line
            xo *= 1.0 - pinch * (-c / cend) ** 0.8
        x = cx + xo - skew * ((1 + c) / 2) ** 1.5
        z = zmid - hh * _spow(c, SQUARE)
        if c > 0.0:     # lower half: keel (sole corners lifted -> V bottom)
            z += keel * PX * (abs(xo) / hw) ** 1.5 * min(1.0, c / 0.45)
        elif s < 0.0:   # inner upper quarter: raised inner side wall
            z += rin * PX * min(1.0, -c / cend)
        pts.append(Vector((sx * x * PX, y * PX, z)))
    return pts


def _shell(bm, sx):
    """Open shell of one shoe. All faces share one winding; with k running
    toward +x (sx=1) that winding faces inward, so it is reversed there.
    Returns the closed topline loop (for the piping)."""
    def face(vs, mat=0):
        f = bm.faces.new(vs if sx < 0 else list(reversed(vs)))
        f.material_index = mat

    rings = [[bm.verts.new(p) for p in _ring(st, sx)] for st in STATIONS]
    for i, (a, b) in enumerate(zip(rings, rings[1:])):
        sole = SOLE_Y[0] <= STATIONS[i][0] and STATIONS[i + 1][0] <= SOLE_Y[1]
        for j in range(RING - 1):
            face((a[j], a[j + 1], b[j + 1], b[j]), 1 if sole and j in SOLE_SEGS else 0)
    tip = bm.verts.new(P(*TOE_TIP, sx))
    r0 = rings[0]
    for j in range(RING - 1):
        face((tip, r0[j + 1], r0[j]))
    y, cx, hw, zb, zt = STATIONS[-1][:5]
    back = bm.verts.new(P(cx, BACK_Y, zt - 2.0, sx))
    rl = rings[-1]
    for j in range(RING - 1):
        face((back, rl[j], rl[j + 1]))
    # topline loop: from the toe-box top centre along the inner ring ends to
    # the heel, across the back, then forward along the outer ring ends
    first_open = next(i for i, st in enumerate(STATIONS) if st[5] < 1.0) - 1
    top = [r[0].co.copy() for r in rings[first_open:]]
    top += [back.co.copy()]
    top += [r[-1].co.copy() for r in reversed(rings[first_open + 1:])]
    return top


# ---------------------------------------------------------------- heel
# Stiletto, rows top -> bottom: (row, centre y, half depth y, half width x)
HEEL = [
    (896.0, 10.5, 8.0, 6.0),
    (900.0, 10.2, 7.2, 5.5),
    (905.0, 10.6, 5.4, 4.8),
    (914.0, 10.8, 3.8, 4.0),
    (926.0, 10.2, 3.0, 3.4),
    (938.0, 9.6, 2.3, 3.0),
    (944.0, 9.4, 2.1, 3.0),
]
HEEL_X = 29.0
HEEL_SIDES = 6


def _heel(bm, sx):
    """Closed stiletto; returns its faces (normals fixed by the caller)."""
    rings = []
    for row, cy, ry, rx in HEEL:
        rings.append([bm.verts.new(Vector((sx * (HEEL_X + rx * math.cos(a)) * PX,
                                           (cy + ry * math.sin(a)) * PX, zrow(row))))
                      for a in (2 * math.pi * i / HEEL_SIDES for i in range(HEEL_SIDES))])
    faces = []
    for a, b in zip(rings, rings[1:]):
        for j in range(HEEL_SIDES):
            k = (j + 1) % HEEL_SIDES
            faces.append(bm.faces.new((a[j], a[k], b[k], b[j])))
    faces.append(bm.faces.new(rings[0]))
    faces.append(bm.faces.new(list(reversed(rings[-1]))))
    return faces


# ---------------------------------------------------------------- tubes
def _tube(bm, pts, r, n=3, closed=False, ref=Vector((0, 0, 1))):
    """Thin tube along pts (world). Frames come from a reference axis `ref`
    (pick one roughly perpendicular to the path) so closed loops line up
    without twist; where the tangent nears `ref` the previous frame is
    carried over instead."""
    m = len(pts)
    rings = []
    prev = None
    for i, p in enumerate(pts):
        if closed:
            t = pts[(i + 1) % m] - pts[(i - 1) % m]
        else:
            t = pts[min(i + 1, m - 1)] - pts[max(i - 1, 0)]
        t.normalize()
        side = t.cross(ref)
        if side.length < 0.3 and prev is not None:
            side = prev - t * prev.dot(t)
        if side.length < 1e-6:
            side = t.orthogonal()
        side.normalize()
        prev = side
        up = side.cross(t)
        rings.append([bm.verts.new(p + (side * math.cos(2 * math.pi * k / n + 0.5)
                                        + up * math.sin(2 * math.pi * k / n + 0.5)) * r)
                      for k in range(n)])
    pairs = list(zip(rings, rings[1:]))
    if closed:
        pairs.append((rings[-1], rings[0]))
    for a, b in pairs:
        for j in range(n):
            k = (j + 1) % n
            bm.faces.new((a[j], a[k], b[k], b[j]))
    if not closed:
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])


# ---------------------------------------------------------------- ankle frame
# Leg surface around the ankle/instep (left leg, panel px), re-measured from
# the front (x) and side (y) panels: row, centre x, half width x, front y, back y
ANKLE = [
    (800.0, 39.0, 14.0, -23.0, 9.0),
    (830.0, 35.0, 14.5, -27.0, 10.0),
    (850.0, 34.0, 14.5, -29.0, 13.0),
    (866.0, 33.5, 14.5, -33.0, 20.0),
    (880.0, 32.0, 14.5, -38.0, 22.0),
    (906.0, 28.5, 12.5, -49.0, 22.0),
]
RIB_OFF = 1.8      # ribbon offset above the skin, px
RIB_R = 0.0011     # ribbon tube radius, m


def _ankle_sec(row):
    rows = [a[0] for a in ANKLE]
    row = min(max(row, rows[0]), rows[-1])
    for a, b in zip(ANKLE, ANKLE[1:]):
        if a[0] <= row <= b[0]:
            t = (row - a[0]) / (b[0] - a[0])
            return [u + (v - u) * t for u, v in zip(a[1:], b[1:])]
    return list(ANKLE[-1][1:])


def ank(theta, row, off=RIB_OFF, sx=1):
    """Point on the leg surface: theta degrees from the front (-Y) toward the
    outer side (+X for the left leg), offset `off` px outward."""
    cx, rx, yf, yb = _ankle_sec(row)
    cy, ry = (yf + yb) / 2, (yb - yf) / 2
    t = math.radians(theta)
    return P(cx + (rx + off) * math.sin(t), cy - (ry + off) * math.cos(t), row, sx)


def _lerp_path(a, b, n):
    """n+1 (theta, row) samples from a to b."""
    return [(a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n) for i in range(n + 1)]


KNOT = (-16.0, 831.0)  # bow knot (theta, row)
CROSS_TH = -10.0       # instep lace crossing (theta)


def _band_row(theta):
    """Ankle wrap: high at the front knot, low at the back (leaf base)."""
    return 841.0 - 9.0 * math.cos(math.radians(theta - KNOT[0]))


def _ribbons(bm, sx):
    # ankle wrap
    band = [ank(th, _band_row(th), sx=sx) for th in range(-180, 180, 20)]
    _tube(bm, band, RIB_R, closed=True)
    # instep criss-cross: vamp corner -> front crossing (a little to the inner
    # side, as on the sheet) -> diagonally up to the back of the ankle -> wrap
    for s in (1, -1):
        path = _lerp_path((-80 * s, 906.0), (CROSS_TH, 882.0), 3)[:-1]
        path += _lerp_path((CROSS_TH, 882.0), (145 * s, 856.0), 4)
        path += [(160 * s, _band_row(160 * s))]
        _tube(bm, [ank(th, r, sx=sx) for th, r in path], RIB_R)
    # back V: wrap sides -> top of the heel counter
    for s in (1, -1):
        path = _lerp_path((115 * s, _band_row(115 * s)), (180 * s, 866.0), 4)
        _tube(bm, [ank(th, r, off=RIB_OFF + 1.2 * i / 4, sx=sx) for i, (th, r) in enumerate(path)],
              RIB_R)
    # bow: two loops lying round the ankle + two short tails
    kth, krow = KNOT
    out = (ank(kth, krow, sx=sx) - ank(kth, krow, off=0.0, sx=sx)).normalized()
    for s in (1, -1):
        loop = []
        for i in range(10):
            t = 2 * math.pi * i / 10
            u = (1 - math.cos(t)) / 2
            th = kth + s * 34.0 * u
            row = krow - 3.0 * u - 7.5 * math.sin(t) * s
            loop.append(ank(th, row, off=RIB_OFF + 0.5 + 5.0 * u, sx=sx))
        _tube(bm, loop, RIB_R, closed=True, ref=out)
        tail = [ank(kth + s * (2 + 5 * i), krow + 4.5 * i, off=RIB_OFF + 0.8, sx=sx) for i in range(4)]
        _tube(bm, tail, RIB_R, ref=out)
    knot = [ank(kth - 3, krow, off=RIB_OFF + 0.8, sx=sx), ank(kth + 3, krow, off=RIB_OFF + 0.8, sx=sx)]
    _tube(bm, knot, RIB_R * 2.0, n=4)
    # long tail hanging at the back/outer side below the leaves
    # (kept close to the heel: further back it crosses the ankle's
    # knee/ankle weight blend and stretches when the foot points)
    tail = [(46.5, 8.0, 849.0), (50.5, 12.0, 858.0), (52.5, 15.5, 869.0),
            (53.0, 17.5, 880.0), (52.5, 18.5, 891.0), (51.5, 19.0, 899.0)]
    _tube(bm, [P(*p, sx) for p in tail], RIB_R, ref=Vector((sx, 0, 0)))


# ---------------------------------------------------------------- leaves
LEAF_BASE = (46.0, 9.0, 848.0)
LEAVES = [  # tip (x, y, row), half width px
    ((65.0, 30.5, 804.0), 11.5),
    ((73.0, 44.0, 824.0), 12.5),
]
LEAF_RINGS = 5
LEAF_FOLD = 0.6   # blade halves fold up along the midrib (reads broad from all views)


def _leaf(bm, base, tip, half_w, sx):
    """Lens-shaped blade from base to tip (left-shoe world coordinates); the
    finished points are mirrored for sx=-1 so both feet curl the same way."""
    def V(v):
        return bm.verts.new(Vector((sx * v.x, v.y, v.z)))

    axis = tip - base
    length = axis.length
    a = axis.normalized()
    n0 = Vector((1.0, 1.0, 0.0)).normalized()   # blade faces outer-back
    wdir = a.cross(n0).normalized()
    nrm = wdir.cross(a).normalized()
    if nrm.dot(n0) < 0:
        nrm = -nrm
    th = 0.0007
    rings = []
    for i in range(1, LEAF_RINGS + 1):
        t = i / (LEAF_RINGS + 1)
        w = half_w * PX * math.sin(math.pi * t ** 0.8)
        c = base + axis * t + nrm * (math.sin(math.pi * t) * 0.06 * length)
        c -= wdir * (0.05 * length * t * t)                 # slight sideways curl
        f = nrm * (LEAF_FOLD * w)   # edges fold toward the face: V-section
        rings.append([V(c - wdir * w + f), V(c + nrm * th), V(c + wdir * w + f), V(c - nrm * th)])
    for r0, r1 in zip(rings, rings[1:]):
        for j in range(4):
            k = (j + 1) % 4
            bm.faces.new((r0[j], r0[k], r1[k], r1[j]))
    # bases pulled apart slightly so the two blades do not share a vertex
    vb, vt = V(base + a * (0.4 * PX)), V(tip)
    for j in range(4):
        k = (j + 1) % 4
        bm.faces.new((vb, rings[0][k], rings[0][j]))
        bm.faces.new((vt, rings[-1][j], rings[-1][k]))


# ---------------------------------------------------------------- build
def _finish(bm):
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-7)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def build(col):
    shell_bm, rib_bm, leaf_bm = bmesh.new(), bmesh.new(), bmesh.new()
    piping, heel_faces = [], []
    for sx in (1, -1):
        piping.append(_shell(shell_bm, sx))
        heel_faces += _heel(shell_bm, sx)
        _ribbons(rib_bm, sx)
        for tip, hw in LEAVES:
            _leaf(leaf_bm, P(*LEAF_BASE), P(*tip), hw, sx)
    # heels are closed: let bmesh orient them; the open shells are wound
    # outward by construction (_shell), so only merge their seams
    bmesh.ops.recalc_face_normals(shell_bm, faces=heel_faces)
    bmesh.ops.remove_doubles(shell_bm, verts=shell_bm.verts, dist=1e-7)
    pipe_bm = bmesh.new()
    for top in piping:
        _tube(pipe_bm, top, 0.0010, n=3, closed=True)
    _finish(pipe_bm)
    _finish(rib_bm)
    _finish(leaf_bm)

    shell = common.new_object(col, 'shoes_shell', shell_bm,
                              [common.toon_material('shoe'),
                               common.toon_material('shoe', gradient='skin')])
    common.shade_smooth(shell, 50.0)
    common.set_gradient(shell, lambda co: SOLE_MIX)   # read by the sole slot only
    pipe = common.new_object(col, 'shoes_topline', pipe_bm, [common.toon_material('shoe')])
    common.shade_smooth(pipe, 80.0)
    # the sheet's laces are the shoe's dark green (#2C6C40 lit), not the
    # brighter trim green
    rib = common.new_object(col, 'shoes_ribbons', rib_bm, [common.toon_material('shoe')])
    common.shade_smooth(rib, 80.0)
    leaf = common.new_object(col, 'shoes_leaves', leaf_bm, [common.toon_material('leaf')])
    common.shade_smooth(leaf, 60.0)
    objs = [shell, pipe, rib, leaf]
    common.add_outline(shell)
    common.add_outline(pipe, width=0.0012)
    common.add_outline(rib, width=0.0010)
    common.add_outline(leaf, width=0.0014)
    return objs
