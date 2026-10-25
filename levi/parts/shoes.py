"""Shoes: green pointed-toe stiletto pumps with criss-cross ankle laces, a bow
at the front of each ankle and a pair of leaves at the back/outer side of each
ankle.

Construction (left shoe, +X, mirrored for the right one):
  * shell: one smooth upper from the pointed toe to the rounded heel counter.
    A hand-measured station table is resampled with a monotone cubic along the
    shoe, so the toe box, the arch and the heel curve have no kinks. Each
    section is a superellipse that is boxy below (flat sole with a defined
    edge) and round above (toe box). The underside from the ball to the heel
    seat and the lining are the sheet's tan `sole` key.
  * topline: the open edge of the shell is rolled over into a short inner
    lining (green rim, tan lining), so the upper reads as a material with
    thickness, not a paper sheet.
  * stiletto: a tapered solid whose top is a broad heel-seat footprint sunk
    into the shell, narrowing smoothly to a small top lift.
  * laces: flat ribbons (width + thickness, broad face toward the skin) kept
    at a constant small offset from the leg. They start under the topline on
    both sides of the vamp, cross on the instep, wrap the ankle, cross again
    behind it above the heel counter, and are tied in a bow at the front with
    two short ends; one long end hangs at the outer back.
  * leaves: two lens-shaped blades with a soft midrib fold.

Every shell section keeps the body's foot (body.FOOT, imported so a foot
change cannot make skin poke through) inside it with FOOT_CLEAR px to spare.

Everything is laid out in reference-panel pixels (1 px = 1/643 m) as measured
from ref/front.png, ref/side.png and ref/back.png, then mapped to world space.

Local landmark corrections (spec.L is a +-3 px first pass):
  * toe tip: side col 227 -> y = -93 px (spec toe_tip_y = -95 px); front view
    toe points at x = +-15 px (spec toe_tip_x = 22 px).
  * shoe centre x = 28 px at the heel, 27 px across the ball (spec
    ankle_center_x = 35 px is the ankle, which sits further out).
  * heel back y = +22.5 px (counter, side col 342); stiletto between
    y = +7..+17 px (spec heel_back_y = 15 px).
  * heel seat at row 899 -> heel height ~49 px (spec heel_height = 55 px).
  * the side panel's soles sit at row ~945 while the front/back toe and heel
    tips reach row 951 (the sheet is drawn with a slight top-down
    perspective).  Rows below 850 are squeezed so the sole lands ~4 px above
    the ground: within 3 px of the side profile and of the front/back tips.
"""
import math

import bmesh
import numpy as np
from mathutils import Vector

from .. import common, spec
from .body import FOOT, LEG_FRONT, LEG_SIDE, MARGIN as BODY_MARGIN

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


def _pchip(xs, ys, x):
    """Monotone cubic (Fritsch-Carlson) through (xs, ys) at x: no overshoot,
    flat runs stay exactly flat."""
    n = len(xs)
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    h = [xs[i + 1] - xs[i] for i in range(n - 1)]
    d = [(ys[i + 1] - ys[i]) / h[i] for i in range(n - 1)]
    m = [d[0]] + [0.0] * (n - 2) + [d[-1]]
    for i in range(1, n - 1):
        if d[i - 1] * d[i] > 0:
            w1, w2 = 2 * h[i] + h[i - 1], h[i] + 2 * h[i - 1]
            m[i] = (w1 + w2) / (w1 / d[i - 1] + w2 / d[i])
    if d[0] * m[0] <= 0:
        m[0] = 0.0
    if d[-1] * m[-1] <= 0:
        m[-1] = 0.0
    i = max(k for k in range(n - 1) if xs[k] <= x)
    t = (x - xs[i]) / h[i]
    h00, h10 = 2 * t ** 3 - 3 * t ** 2 + 1, t ** 3 - 2 * t ** 2 + t
    h01, h11 = -2 * t ** 3 + 3 * t ** 2, t ** 3 - t ** 2
    return h00 * ys[i] + h10 * h[i] * m[i] + h01 * ys[i + 1] + h11 * h[i] * m[i + 1]


# ---------------------------------------------------------------- shell
# Key stations along the shoe, toe -> heel, panel px:
#   y, centre x, half width, sole row, top row, opening angle (fraction of pi),
#   inward skew of the sole (px; the front view narrows to a V on the inner side),
#   pinch (0..1: the upper half narrows toward the opening -> tapered heel cup
#   in the back view), keel (px the sole corners are lifted -> pointed V bottom
#   in the front view), inner-wall raise (px: the inner side of the opening
#   sits higher than the outer one, hidden in the side view)
# Closed toe box: frac = 1 (ring ends meet on the top centre line, top row =
# toe-box top).  Open stations: ring ends sit on the topline at `top row`.
# The heel half widths follow a circle of radius ~12 px around y = 10.5, so
# the counter is round in plan view.
STATIONS = [
    (-91.0, 15.5, 1.8, 942.6, 939.6, 1.0, 0.5, 0.0, 1.0, 0.0),
    (-85.0, 18.0, 5.4, 943.8, 935.0, 1.0, 2.0, 0.0, 2.0, 0.0),
    (-78.0, 20.5, 9.0, 944.3, 930.5, 1.0, 4.0, 0.0, 3.0, 0.0),
    (-71.0, 23.0, 12.2, 944.5, 927.5, 1.0, 4.0, 0.0, 3.8, 0.0),
    (-66.0, 24.2, 14.6, 944.5, 925.5, 1.0, 3.0, 0.0, 4.5, 0.0),
    (-62.0, 25.0, 15.8, 944.5, 923.5, 0.9, 2.5, 0.0, 5.0, 1.5),
    (-56.0, 25.6, 17.2, 944.5, 920.5, 0.8, 2.5, 0.0, 5.8, 4.0),
    (-50.0, 25.8, 18.0, 944.5, 918.0, 0.72, 3.0, 0.0, 6.0, 6.0),
    (-40.0, 26.5, 18.6, 944.5, 916.5, 0.67, 3.0, 0.0, 6.5, 8.0),
    (-30.0, 27.0, 18.0, 944.5, 916.0, 0.67, 3.0, 0.0, 6.5, 8.0),
    (-23.0, 28.5, 17.0, 942.0, 914.0, 0.67, 2.5, 0.0, 4.5, 6.0),
    (-18.0, 29.5, 15.5, 932.0, 903.0, 0.67, 1.5, 0.0, 0.5, 3.0),
    (-13.0, 30.0, 14.5, 920.0, 893.0, 0.67, 1.0, 0.0, 0.0, 0.0),
    (-8.0, 30.0, 14.0, 910.0, 884.0, 0.67, 0.0, 0.1, 0.0, 0.0),
    (-3.0, 30.0, 13.5, 903.0, 876.0, 0.67, 0.0, 0.15, 0.0, 0.0),
    (2.0, 30.0, 13.0, 899.5, 869.0, 0.67, 0.0, 0.2, 0.0, 0.0),
    (7.0, 30.0, 12.5, 899.0, 865.0, 0.67, 0.0, 0.3, 0.0, 0.0),
    (12.0, 30.0, 11.8, 899.0, 861.0, 0.67, 0.0, 0.45, 0.0, 0.0),
    (16.0, 30.0, 10.8, 898.5, 859.0, 0.67, 0.0, 0.5, 0.0, 0.0),
    (19.0, 30.0, 8.6, 896.0, 858.0, 0.67, 0.0, 0.5, 0.0, 0.0),
    (21.2, 30.0, 5.8, 890.0, 858.5, 0.67, 0.0, 0.45, 0.0, 0.0),
    (22.3, 30.0, 3.0, 884.0, 859.0, 0.67, 0.0, 0.4, 0.0, 0.0),
]
# Resampled stations (y): dense where the outline curves (toe, arch, heel).
SAMPLES = (-91.0, -87.0, -82.0, -76.0, -70.0, -66.0, -62.0, -57.0, -50.0, -42.0,
           -34.0, -27.0, -21.0, -15.5, -10.0, -4.0, 3.0, 10.0, 16.0, 19.5, 21.8)
TOE_TIP = (15.0, -93.0, 941.5)
BACK_Y = 22.8      # heel back spine (centre line)
RING = 13          # verts per cross-section (12 segments)
SQ_LO = 0.7        # superellipse exponent of the lower half: flat sole, defined edge
SQ_UP = 0.8        # upper half: rounded toe box / quarters
SOLE_Y = (-24.0, 6.0)  # the arch underside between these y is tan
SOLE_HALF = 0.15   # ... within this fraction of pi of the bottom centre
FOOT_P = 2.3       # body foot section exponent (body.build_foot)
FOOT_CLEAR = 1.0   # px the shell keeps outside the foot
RIM_T = 1.3        # px: upper thickness at the rolled topline
LINING_D = 2.5     # px the tan lining runs down inside the opening


def _spow(v, p):
    return math.copysign(abs(v) ** p, v)


_STATION_COLS = list(zip(*STATIONS))
_FOOT_ROWS = sorted(FOOT, key=lambda f: f[0])
FOOT_CAP = 3.0     # px: body.build_foot's pole caps beyond the first / last slice


def _station(y):
    ys = _STATION_COLS[0]
    return (y,) + tuple(_pchip(ys, _STATION_COLS[i], y) for i in range(1, 10))


def _foot_section(y):
    """Body foot section at y (true px): centre x, half width, centre z, half
    height. The pole caps taper linearly over FOOT_CAP px past the end slices."""
    rows = _FOOT_ROWS
    lo, hi = rows[0][0], rows[-1][0]
    if not lo - FOOT_CAP < y < hi + FOOT_CAP:
        return None
    k = 1.0
    if y < lo:
        f, k = list(rows[0]), 1.0 - (lo - y) / FOOT_CAP
    elif y > hi:
        f, k = list(rows[-1]), 1.0 - (y - hi) / FOOT_CAP
    else:
        for a, b in zip(rows, rows[1:]):
            if a[0] <= y <= b[0]:
                t = (y - a[0]) / max(b[0] - a[0], 1e-9)
                f = [u + (v - u) * t for u, v in zip(a, b)]
                break
    _, cx, hw, bot, top = f
    return cx, hw * k, spec.SHEET_GROUND_Y - (bot + top) / 2, (bot - top) / 2 * k


def _clear_foot(x, y, zpx):
    """Push a shell point (panel px, true z px) out of the foot by FOOT_CLEAR."""
    sec = _foot_section(y)
    if sec is None:
        return x, zpx
    cx, hw, cz, hh = sec
    dx, dz = x - cx, zpx - cz
    r = (abs(dx / hw) ** FOOT_P + abs(dz / hh) ** FOOT_P) ** (1.0 / FOOT_P)
    need = 1.0 + FOOT_CLEAR / min(hw, hh)
    if r < need and r > 1e-6:
        k = need / r
        return cx + dx * k, cz + dz * k
    return x, zpx


def _ring(st, sx):
    y, cx, hw, zb, zt, frac, skew, pinch, keel, rin = st
    closed = frac >= 0.999
    phim = math.pi * (1.0 if closed else frac)
    zb_m, zt_m = zrow(zb), zrow(zt)
    cend = max(1e-6, -math.cos(phim))
    # half height so the ring ends land on the top row
    hh = (zt_m - zb_m) / (1.0 + abs(math.cos(phim)) ** SQ_UP)
    zmid = zb_m + hh
    pts = []
    for k in range(RING):
        phi = phim * (2.0 * k / (RING - 1) - 1.0)
        s, c = math.sin(phi), math.cos(phi)
        sq = SQ_LO if c > 0.0 else SQ_UP
        xo = hw * _spow(s, sq)
        if c < 0.0:     # upper half: pinch toward the centre line
            xo *= 1.0 - pinch * (-c / cend) ** 0.8
        x = cx + xo - skew * ((1 + c) / 2) ** 1.5
        z = zmid - hh * _spow(c, sq)
        if c > 0.0:     # lower half: keel (sole corners lifted -> V bottom)
            z += keel * PX * (abs(xo) / hw) ** 1.5 * min(1.0, c / 0.45)
        elif s < 0.0:   # inner upper quarter: raised inner side wall
            z += rin * PX * min(1.0, -c / cend)
        if closed and k in (0, RING - 1):
            x = cx - skew * ((1 + c) / 2) ** 1.5      # exact top centre: ends merge
        x, zpx = _clear_foot(x, y, z / PX)
        pts.append(Vector((sx * x * PX, y * PX, zpx * PX)))
    if closed:
        pts[-1] = pts[0].copy()
    return pts


def _shell(bm, sx):
    """Open upper of one shoe, wound outward, plus its rolled topline rim and
    tan lining. Returns the topline points (inner side toe -> heel -> outer
    side toe) for the lace attachments."""
    faces = []

    def face(vs, mat=0):
        f = bm.faces.new(vs if sx < 0 else list(reversed(vs)))
        f.material_index = mat
        faces.append(f)
        return f

    stations = [_station(y) for y in SAMPLES]
    rings = []
    for st in stations:
        pts = _ring(st, sx)
        ring = [bm.verts.new(p) for p in pts[:-1]]
        ring.append(ring[0] if st[5] >= 0.999 else bm.verts.new(pts[-1]))
        rings.append(ring)
    for i, (a, b) in enumerate(zip(rings, rings[1:])):
        under = SOLE_Y[0] <= stations[i][0] and stations[i + 1][0] <= SOLE_Y[1]
        for j in range(RING - 1):
            mid = abs((j + 0.5) / (RING - 1) * 2.0 - 1.0) * stations[i][5]
            face((a[j], a[j + 1], b[j + 1], b[j]), 1 if under and mid < SOLE_HALF else 0)
    tip = bm.verts.new(P(*TOE_TIP, sx))
    r0 = rings[0]
    for j in range(RING - 1):
        face((tip, r0[j + 1], r0[j]))
    # heel back: the last ring closes onto a vertical spine on the centre
    # line (mirror pairs of the ring share one spine vertex), so the counter
    # stays round and its topline runs straight across the back
    rl = rings[-1]
    cx = sx * stations[-1][1] * PX
    spine = [bm.verts.new(Vector((cx, BACK_Y * PX, (rl[j].co.z + rl[RING - 1 - j].co.z) / 2)))
             for j in range(RING // 2 + 1)]

    def sp(j):
        return spine[min(j, RING - 1 - j)]
    for j in range(RING - 1):
        face((rl[j], rl[j + 1], sp(j + 1), sp(j)))

    # rolled topline: boundary edges -> rim (green) -> lining (tan)
    bm.normal_update()
    sub = set(faces)
    bnd = [e for e in bm.edges if e.is_boundary and e.link_faces[0] in sub]
    bverts = {v for e in bnd for v in e.verts}
    top = {}
    for v in bverts:
        n = v.normal.copy()
        inner = [e.other_vert(v) for e in v.link_edges if not e.is_boundary]
        d = Vector((0, 0, 0))
        for q in inner:
            d += (v.co - q.co).normalized()
        d = d.normalized() if d.length > 1e-9 else Vector((0, 0, 1))
        a = bm.verts.new(v.co - n * (RIM_T * 0.5 * PX) + d * (RIM_T * 0.45 * PX))
        b = bm.verts.new(v.co - n * (RIM_T * PX) - d * (LINING_D * PX))
        top[v] = (a, b)
    for e in bnd:
        f = e.link_faces[0]
        u, w = e.verts
        # the shell face runs u -> w or w -> u; the rim continues it reversed
        loop = next(lp for lp in f.loops if lp.edge is e)
        if loop.vert is u:
            u, w = w, u
        ru, rw = top[u], top[w]
        bm.faces.new((u, w, rw[0], ru[0])).material_index = 0
        bm.faces.new((ru[0], rw[0], rw[1], ru[1])).material_index = 1
    first_open = next(i for i, s in enumerate(stations) if s[5] < 0.999) - 1
    line = [r[0].co.copy() for r in rings[first_open:]]
    line += [r[-1].co.copy() for r in reversed(rings[first_open + 1:])]
    return line


# ---------------------------------------------------------------- heel
# Stiletto, rows top -> bottom: (row, centre y, half depth y, half width x).
# The top ring is the heel-seat footprint, sunk into the shell above its
# underside (row ~899), so the shaft grows out of the seat with no seam. Its
# cap ends inside the foot's heel pad, out of sight, as in round 2.
HEEL = [
    (895.0, 11.0, 8.4, 6.6),
    (901.0, 10.8, 7.0, 5.4),
    (908.0, 10.7, 4.8, 4.3),
    (920.0, 10.3, 3.3, 3.4),
    (935.0, 9.9, 2.5, 2.9),
    (944.0, 9.6, 2.1, 2.6),
]
HEEL_X = 29.5
HEEL_SIDES = 8
HEEL_SQ = 1.0      # elliptical shaft section


def _heel(bm, sx):
    """Closed stiletto; returns its faces (normals fixed by the caller)."""
    rings = []
    for row, cy, ry, rx in HEEL:
        ring = []
        for i in range(HEEL_SIDES):
            a = 2 * math.pi * (i + 0.5) / HEEL_SIDES
            ring.append(bm.verts.new(Vector((sx * (HEEL_X + rx * _spow(math.cos(a), HEEL_SQ)) * PX,
                                             (cy + ry * _spow(math.sin(a), HEEL_SQ)) * PX, zrow(row)))))
        rings.append(ring)
    faces = []
    for a, b in zip(rings, rings[1:]):
        for j in range(HEEL_SIDES):
            k = (j + 1) % HEEL_SIDES
            faces.append(bm.faces.new((a[j], a[k], b[k], b[j])))
    faces.append(bm.faces.new(rings[0]))
    faces.append(bm.faces.new(list(reversed(rings[-1]))))
    return faces


# ---------------------------------------------------------------- ribbons
def _ribbon(bm, pts, nrms, w, th, closed=False, taper=1.0):
    """Flat ribbon along pts (world): rectangle section `w` wide and `th`
    thick, broad face along nrms (e.g. away from the skin). `taper` scales the
    width at the far end of an open ribbon."""
    m = len(pts)
    rings = []
    prev = None
    for i, p in enumerate(pts):
        if closed:
            t = pts[(i + 1) % m] - pts[(i - 1) % m]
        else:
            t = pts[min(i + 1, m - 1)] - pts[max(i - 1, 0)]
        t.normalize()
        n = nrms[i] - t * nrms[i].dot(t)
        if n.length < 1e-6:
            n = prev if prev is not None else t.orthogonal()
        n.normalize()
        prev = n
        b = t.cross(n)
        hw = 0.5 * w * (1.0 + (taper - 1.0) * (i / (m - 1) if not closed else 0.0))
        ht = 0.5 * th
        rings.append([bm.verts.new(p + b * hw + n * ht), bm.verts.new(p - b * hw + n * ht),
                      bm.verts.new(p - b * hw - n * ht), bm.verts.new(p + b * hw - n * ht)])
    pairs = list(zip(rings, rings[1:]))
    if closed:
        pairs.append((rings[-1], rings[0]))
    for a, b in pairs:
        for j in range(4):
            k = (j + 1) % 4
            bm.faces.new((a[j], a[k], b[k], b[j]))
    if not closed:
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])


def _catmull(ctrl, n, closed=False):
    """Catmull-Rom through control tuples; n samples per span."""
    m = len(ctrl)
    out = []
    spans = m if closed else m - 1
    for i in range(spans):
        p0 = ctrl[(i - 1) % m] if closed else ctrl[max(i - 1, 0)]
        p1, p2 = ctrl[i % m], ctrl[(i + 1) % m]
        p3 = ctrl[(i + 2) % m] if closed else ctrl[min(i + 2, m - 1)]
        for k in range(n):
            t = k / n
            out.append(tuple(0.5 * (2 * b + (-a + c) * t + (2 * a - 5 * b + 4 * c - d) * t * t
                                    + (-a + 3 * b - 3 * c + d) * t ** 3)
                             for a, b, c, d in zip(p0, p1, p2, p3)))
    if not closed:
        out.append(tuple(ctrl[-1]))
    return out


# Skin around the ankle and instep: the body's leg (LEG_FRONT / LEG_SIDE,
# ellipses) and foot (FOOT, vertical slices) tables, imported so the laces
# follow the real skin. Each row is reduced to the bounding ellipse of the
# horizontal skin section (centre x, half width, front y, back y).
ROW_MIN, ROW_MAX = 800.0, 910.0
RIB_OFF = 1.7      # ribbon centre offset above the skin, px
RIB_W = 0.0023     # ribbon width, m
RIB_T = 0.0008     # ribbon thickness, m


def _leg_sec(row):
    """Body leg ellipse at sheet `row` (inner x, outer x, front y, back y), or
    None outside the leg table."""
    rows = sorted(LEG_FRONT)
    if not rows[0] <= row <= rows[-1]:
        return None
    for r0, r1 in zip(rows, rows[1:]):
        if r0 <= row <= r1:
            t = (row - r0) / (r1 - r0)
            xo, xi = [u + (v - u) * t for u, v in zip(LEG_FRONT[r0], LEG_FRONT[r1])]
            yf, yb = [u + (v - u) * t for u, v in zip(LEG_SIDE[r0], LEG_SIDE[r1])]
            return xi + BODY_MARGIN, xo - BODY_MARGIN, yf + BODY_MARGIN, yb - BODY_MARGIN


_SEC_CACHE = {}


def _skin_points(row):
    """Points (x, y) filling the horizontal skin section at `row`: the leg
    ellipse outline and every foot slice that reaches this height, sampled
    across its full width (so rays toward the front and back of the foot
    meet its edge too)."""
    zpx = zrow(row) / PX
    pts = []
    leg = _leg_sec(spec.SHEET_GROUND_Y - zpx)     # the body maps rows linearly
    if leg is not None:
        xi, xo, yf, yb = leg
        for k in range(144):
            a = 2 * math.pi * k / 144
            pts.append(((xi + xo) / 2 + (xo - xi) / 2 * math.sin(a), (yf + yb) / 2 - (yb - yf) / 2 * math.cos(a)))
    y = -88.0
    while y <= 17.0:
        sec = _foot_section(y)
        if sec is not None:
            cx, hw, cz, hh = sec
            d = abs(zpx - cz) / hh
            if d < 1.0:
                w = hw * (1.0 - d ** FOOT_P) ** (1.0 / FOOT_P)
                n = int(math.ceil(2 * w / 0.8)) + 1
                pts += [(cx - w + 2 * w * i / (n - 1), y) for i in range(n)]
        y += 0.5
    return np.array(pts)


def _ankle_sec(row):
    """Skin section at `row` (panel px): (centre x, centre y, half width x,
    half depth y, section points)."""
    row = round(min(max(row, ROW_MIN), ROW_MAX), 2)
    if row not in _SEC_CACHE:
        pts = _skin_points(row)
        (x0, y0), (x1, y1) = pts.min(0), pts.max(0)
        _SEC_CACHE[row] = ((x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2, pts)
    return _SEC_CACHE[row]


def _skin_radius(sec, ux, uy):
    """Distance from the section centre to the skin along unit direction
    (ux, uy): the farthest section point within 0.7 px of that ray."""
    cx, cy, rx, ry, pts = sec
    dx, dy = pts[:, 0] - cx, pts[:, 1] - cy
    along = dx * ux + dy * uy
    near = (along > 0.0) & (np.abs(dx * uy - dy * ux) < 0.7)
    if near.any():
        return float(along[near].max())
    return 1.0 / math.hypot(ux / rx, uy / ry)


def ank(theta, row, off=RIB_OFF, sx=1):
    """Point `off` px outside the skin at `row`: theta degrees from the front
    (-Y) toward the outer side (+X for the left leg), as the angle parameter of
    the section's bounding ellipse (so 90 is always the outer side)."""
    sec = _ankle_sec(row)
    cx, cy, rx, ry = sec[:4]
    t = math.radians(theta)
    d = Vector((rx * math.sin(t), -ry * math.cos(t)))
    d.normalize()
    r = _skin_radius(sec, d.x, d.y) + off
    return P(cx + d.x * r, cy + d.y * r, row, sx)


def _to_leg(p, sx):
    """(theta, row, off) such that ank(theta, row, off, sx) == world point p."""
    x, y, zpx = sx * p.x / PX, p.y / PX, p.z / PX
    top = spec.SHEET_GROUND_Y - SQUEEZE_ROW
    row = spec.SHEET_GROUND_Y - zpx if zpx >= top else SQUEEZE_ROW + (top - zpx) / _K
    sec = _ankle_sec(row)
    cx, cy, rx, ry = sec[:4]
    d = Vector((x - cx, y - cy))
    dist = d.length
    d.normalize()
    th = math.degrees(math.atan2(d.x / rx, -d.y / ry))
    return th, row, dist - _skin_radius(sec, d.x, d.y)


def _on_leg(bm, ctrl, sx, n=3, closed=False, w=RIB_W, taper=1.0, around=False):
    """Ribbon through (theta, row, off) controls around the skin. `around`: a
    closed loop whose theta runs once round the leg (wraps at 360 degrees)."""
    if around:
        m = len(ctrl)
        ext = ([(ctrl[-1][0] - 360.0,) + tuple(ctrl[-1][1:])] + list(ctrl)
               + [(c[0] + 360.0,) + tuple(c[1:]) for c in ctrl[:2]])
        samples = _catmull(ext, n)[n:n * (m + 1)]
    else:
        samples = _catmull(ctrl, n, closed)
    pts = [ank(th, r, off, sx) for th, r, off in samples]
    nrms = [(ank(th, r, off + 1.0, sx) - ank(th, r, off, sx)).normalized() for th, r, off in samples]
    _ribbon(bm, pts, nrms, w, RIB_T, closed=closed, taper=taper)


KNOT = (-12.0, 832.0)  # bow knot (theta, row)
CROSS = (-6.0, 885.0)  # instep lace crossing (theta, row)


def _band_row(theta):
    """Ankle wrap: high at the front knot, low at the back (leaf base)."""
    return 841.0 - 9.0 * math.cos(math.radians(theta - KNOT[0]))


def _ribbons(bm, sx, line):
    o = RIB_OFF
    # ankle wrap
    _on_leg(bm, [(th, _band_row(th), o) for th in range(-180, 180, 60)], sx, n=2,
            closed=True, around=True)
    # instep criss-cross: each lace starts tucked under the rolled topline on
    # one side of the vamp, climbs across the instep (crossing a little to
    # the inner side, as on the sheet), reaches the far side of the leg and
    # runs round behind the ankle into the wrap. The second lace rides one
    # ribbon thickness higher where they cross.
    for s, lift in ((1, 0.0), (-1, 0.6)):
        want = ank(-78.0 * s, 908.0, o, sx)
        anchor = min(line, key=lambda q: (q - want).length)
        th0, row0, off0 = _to_leg(anchor, sx)
        _on_leg(bm, [(th0, row0, off0 - RIM_T * 0.5), (CROSS[0], CROSS[1], o + lift),
                     (72 * s, 866.0, o + lift), (125 * s, 856.0, o),
                     (150 * s, _band_row(150 * s) + 1.0, o)], sx, n=3)
    # back X above the heel counter: wrap sides -> across the back -> tab top
    for s in (1, -1):
        _on_leg(bm, [(115 * s, _band_row(115 * s), o), (165 * s, 853.0, o + 0.3 * (s + 1)),
                     (192 * s, 859.0, o + 0.6)], sx, n=2)
    # bow: two loops spreading sideways from the knot at the front of the
    # ankle and lifting off the skin toward their ends, a gathering knot and
    # two short ends
    kth, krow = KNOT
    for s, span, hgt in ((1, 62.0, 7.0), (-1, 55.0, 6.5)):
        ctrl = []
        for i in range(6):
            t = 2 * math.pi * i / 6
            u = (1 - math.cos(t)) / 2                       # 0 at the knot, 1 at the far end
            th = kth + s * span * u
            row = krow - 3.5 * u - hgt * math.sin(t) * (0.45 + 0.55 * u) * s
            ctrl.append((th, row, o + 0.7 + 4.5 * u * u))
        _on_leg(bm, ctrl, sx, n=2, closed=True)
    for s in (1, -1):
        _on_leg(bm, [(kth + 2 * s, krow + 1.0, o + 1.1), (kth + 9 * s, krow + 7.0, o + 1.0),
                     (kth + 17 * s, krow + 15.0, o + 0.9)], sx, n=1, taper=0.6)
    _on_leg(bm, [(kth - 4, krow, o + 1.4), (kth + 4, krow, o + 1.4)], sx, n=1, w=RIB_W * 1.8)
    # long end hanging at the outer back below the leaves, swinging out a
    # little (kept close to the heel: further back it crosses the ankle's
    # knee/ankle weight blend and stretches when the foot points)
    tail = [(46.5, 8.0, 849.0), (50.0, 11.5, 857.0), (52.5, 15.0, 868.0),
            (53.5, 17.5, 879.0), (53.0, 18.5, 890.0), (51.5, 19.0, 899.0)]
    pts = [P(*p, sx) for p in tail]
    _ribbon(bm, pts, [Vector((sx, 0.35, 0.0)).normalized()] * len(pts), RIB_W, RIB_T, taper=0.6)


# ---------------------------------------------------------------- leaves
LEAF_BASE = (46.0, 9.0, 848.0)
LEAVES = [  # tip (x, y, row), half width px
    ((65.0, 30.5, 804.0), 12.0),
    ((73.0, 44.0, 824.0), 13.0),
]
LEAF_RINGS = 5
LEAF_T = 0.0008   # blade half thickness at the midrib, m
LEAF_FOLD = 0.4   # blade halves fold up along the midrib (reads broad from all views)


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
    th = LEAF_T
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
    heel_faces = []
    for sx in (1, -1):
        line = _shell(shell_bm, sx)
        heel_faces += _heel(shell_bm, sx)
        _ribbons(rib_bm, sx, line)
        for tip, hw in LEAVES:
            _leaf(leaf_bm, P(*LEAF_BASE), P(*tip), hw, sx)
    # heels are closed: let bmesh orient them; the open shells are wound
    # outward by construction (_shell)
    bmesh.ops.recalc_face_normals(shell_bm, faces=heel_faces)
    bmesh.ops.remove_doubles(shell_bm, verts=shell_bm.verts, dist=1e-7)
    _finish(rib_bm)
    _finish(leaf_bm)

    shell = common.new_object(col, 'shoes_shell', shell_bm,
                              [common.toon_material('shoe'), common.toon_material('sole')])
    common.shade_smooth(shell, 55.0)
    # the sheet's laces are the shoe's dark green (#2C6C40 lit), not the
    # brighter trim green
    rib = common.new_object(col, 'shoes_ribbons', rib_bm, [common.toon_material('shoe')])
    common.shade_smooth(rib, 50.0)
    leaf = common.new_object(col, 'shoes_leaves', leaf_bm, [common.toon_material('leaf')])
    common.shade_smooth(leaf, 60.0)
    objs = [shell, rib, leaf]
    common.add_outline(shell)
    common.add_outline(rib, width=0.0010)
    common.add_outline(leaf, width=0.0014)
    return objs
