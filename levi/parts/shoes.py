"""Shoes: green pointed-toe stiletto pumps with criss-cross ankle laces, a bow
at the front of each ankle and a pair of leaves at the back/outer side of each
ankle.

Construction (left shoe, +X, mirrored for the right one; round 11 after 风堇's
shoe build: a separate sole slab with a step, a heel cap, closed bows):
  * shell: one smooth upper from the pointed toe to the rounded heel counter.
    A hand-measured station table is resampled with a monotone cubic along the
    shoe, so the toe box, the arch and the heel curve have no kinks. Each
    section is a superellipse that is a rounded box below (the upper comes down
    the side and turns under onto the outsole) and round above (toe box),
    turning into a plain ellipse round the heel cup. The toe tapers almost
    linearly in plan into a soft point a few px ahead of the foot (pumps have
    empty toe room). The topline dips over the rear quarters and rises into a
    narrow tab at the back (the sheet's back view).
  * topline: the open edge of the shell is rolled over into a short inner
    lining (green rim, tan lining), so the upper reads as a material with
    thickness, not a paper sheet.
  * outsole: a 2.3 mm slab under the forepart and the shank, its top inside the
    shell's turned-under edge, its square edge standing a step proud of the
    upper along the feather line; green walls, the sheet's tan `sole` tread
    (seen from behind between green rims either side of the heel). Toward the
    toe it thins to a 0.8 mm edge and runs into the upper's point; ahead of the
    heel breast it melts into the upper (no end face, no tab at the heel).
  * stiletto: a tapered solid whose top is a broad heel-seat footprint sunk
    into the shell, narrowing smoothly to its tip, which stands in a 3 mm tan
    top lift level with the outsole's tread.
  * laces: rounded straps (a flattened hexagonal section, shaded with flat
    strap normals so each broad face reads as one tone, as the sheet paints
    them) kept at a constant small offset from the leg, laid out by controls,
    then smoothed along their length and resampled closer where they bend.
    They start under the topline on both sides of the vamp, cross on the
    instep, wrap the ankle, cross again behind it above the heel counter (each
    crossing one lace over the other: the upper one is bumped over the lower
    after the smoothing), and are tied in a bow at the front (two full teardrop
    loops, a closed knot bead burying the loop roots and the ends' starts, two
    ends falling away); one long end hangs at the outer back.
  * leaves: two ovate, cupped blades with a midrib groove and a short narrow
    stalk, springing from one point on top of the ankle wrap at the outer
    back (where the long lace end also leaves the wrap), each rolled its own
    way and twisting gradually toward the tip so the pair fans.

The shoes follow the body only through its exports: body.FOOT (the shell keeps
the foot inside it), LEG_FRONT / LEG_SIDE / LEG_ROWS / MARGIN and leg_section /
leg_offset (the shell's topline and the laces keep off the leg's skin).

Every shell section keeps the body's foot (body.FOOT, imported so a foot
change cannot make skin poke through) inside it with FOOT_CLEAR px to spare.

Everything is laid out in reference-panel pixels (1 px = 1/643 m) as measured
from ref/front.png, ref/side.png and ref/back.png, then mapped to world space.

Local landmark corrections (spec.L is a +-3 px first pass):
  * toe tip: side col 227 -> y = -93 px (spec toe_tip_y = -95 px); front view
    toe points at x = +-15 px (spec toe_tip_x = 22 px). The shell's tip is
    at y = -97: the pointed toe runs ~4 px past the drawn tip so the point
    can taper ahead of the foot instead of pinching it.
  * shoe centre x = 28 px at the heel, 27 px across the ball (spec
    ankle_center_x = 35 px is the ankle, which sits further out).
  * heel back y = +22.5 px (counter, side col 342); stiletto between
    y = +7..+17 px (spec heel_back_y = 15 px).
  * heel seat at row 899 -> heel height ~49 px (spec heel_height = 55 px).
  * the side panel's soles sit at row ~945 while the front/back toe and heel
    tips reach row 951 (the sheet is drawn with a slight top-down
    perspective).  Rows below 850 are squeezed so the shell's sole lands ~4 px
    above the ground: within 3 px of the side profile and of the front/back
    tips. Round 11's outsole and top lift reach 0.75 mm / 1.5 mm lower: the
    tread is 4.7 mm above the ground (round 10: 5.4 mm toe, 6.2 mm heel tip).
    (Grounding the sole, SOLE_LIFT 0.5, was tried in round 4: it costs
    0.035 side / 0.009 front shoe IoU, so the lift stays a sheet
    calibration; a ground offset belongs in the rig/export.)
"""
import math

import bmesh
import numpy as np
from mathutils import Quaternion, Vector

from .. import common, spec
from .body import FOOT, LEG_FRONT, LEG_ROWS, LEG_SIDE, MARGIN as BODY_MARGIN, leg_offset, leg_section

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


def Pz(x, y, zpx, sx=1):
    """Panel px with the height in true px above the ground (not a row) -> world."""
    return Vector((sx * x * PX, y * PX, zpx * PX))


def row_of(zpx):
    """Inverse of zrow: true height (px) -> reference row."""
    top = spec.SHEET_GROUND_Y - SQUEEZE_ROW
    return spec.SHEET_GROUND_Y - zpx if zpx >= top else SQUEEZE_ROW + (top - zpx) / _K


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
#   inward skew of the sole (px; kept <= 1: a larger skew read as a keel),
#   pinch (0..1: the upper half narrows toward the opening -> tapered heel cup
#   in the back view), keel (px the sole corners were lifted, rounds 4-10; unused
#   since round 11: the flat outsole is the bottom), inner-wall raise (px:
#   the inner side of the opening sits higher than the outer one, hidden in
#   the side view)
# Closed toe box: frac = 1 (ring ends meet on the top centre line, top row =
# toe-box top).  Open stations: ring ends sit on the topline at `top row`.
# The heel half widths follow a circle of radius ~12 px around y = 10.5, so
# the counter is round in plan view.
STATIONS = [
    (-95.0, 15.4, 1.4, 942.6, 940.4, 1.0, 0.3, 0.0, 0.3, 0.0),
    (-89.0, 17.0, 4.3, 943.5, 936.4, 1.0, 0.6, 0.0, 0.6, 0.0),
    (-83.0, 18.8, 6.7, 944.1, 932.8, 1.0, 0.8, 0.0, 0.8, 0.0),
    (-77.0, 20.6, 9.3, 944.4, 929.3, 1.0, 1.0, 0.0, 1.0, 0.0),
    (-71.0, 22.6, 11.7, 944.5, 926.3, 1.0, 1.0, 0.0, 1.0, 0.0),
    (-66.0, 24.0, 13.7, 944.5, 924.1, 1.0, 1.0, 0.0, 1.0, 0.0),
    (-62.0, 25.0, 15.2, 944.5, 922.4, 0.9, 1.0, 0.0, 1.0, 1.5),
    (-56.0, 25.6, 16.7, 944.5, 919.8, 0.8, 1.0, 0.0, 1.0, 4.0),
    (-50.0, 25.8, 16.8, 944.5, 918.0, 0.72, 1.0, 0.0, 1.0, 6.0),
    (-40.0, 26.5, 17.2, 944.5, 916.5, 0.67, 1.0, 0.0, 1.0, 8.0),
    (-30.0, 27.0, 16.7, 944.5, 916.0, 0.67, 1.0, 0.0, 1.0, 8.0),
    (-23.0, 28.5, 15.9, 941.8, 914.0, 0.67, 0.8, 0.0, 0.8, 6.0),
    (-18.0, 29.5, 14.9, 934.0, 903.0, 0.67, 0.5, 0.0, 0.4, 3.0),
    (-13.0, 30.0, 14.5, 924.5, 893.5, 0.67, 0.3, 0.05, 0.0, 0.0),
    (-8.0, 30.0, 14.0, 913.5, 885.0, 0.67, 0.0, 0.1, 0.0, 0.0),
    (-3.0, 30.0, 13.5, 906.0, 878.0, 0.67, 0.0, 0.15, 0.0, 0.0),
    (2.0, 30.0, 12.4, 901.8, 872.0, 0.67, 0.0, 0.2, 0.0, 0.0),
    (7.0, 30.0, 11.3, 900.0, 868.0, 0.67, 0.0, 0.25, 0.0, 0.0),
    (12.0, 30.0, 10.3, 899.5, 864.5, 0.67, 0.0, 0.3, 0.0, 0.0),
    (16.0, 30.0, 9.2, 898.5, 861.5, 0.67, 0.0, 0.35, 0.0, 0.0),
    (19.0, 30.0, 7.6, 896.0, 859.5, 0.67, 0.0, 0.35, 0.0, 0.0),
    (21.2, 30.0, 5.2, 890.0, 859.0, 0.67, 0.0, 0.35, 0.0, 0.0),
    (22.3, 30.0, 2.7, 884.0, 858.3, 0.67, 0.0, 0.35, 0.0, 0.0),
]
# Resampled stations (y): dense where the outline curves (toe, arch, heel).
# Round 5: ~2.5 px apart through the ball-to-arch bend (-30..+3), where the
# sole climbs into the heel seat, so the waist reads as one continuous curve.
SAMPLES = (-94.5, -91.0, -87.0, -83.0, -78.5, -74.0, -69.5, -65.0, -60.5, -56.0,
           -51.0, -45.5, -40.0, -34.5, -30.0, -27.0, -24.5, -22.0, -19.5, -17.0,
           -14.5, -12.0, -9.0, -5.5, -1.5, 3.0, 7.0, 11.0, 14.5, 17.3, 19.5, 21.0, 21.9)
TOE_TIP = (14.8, -97.0, 941.6)
BACK_Y = 22.8      # heel back spine (centre line)
RING = 21          # verts per cross-section (20 segments: round toe box, smooth sole edge)
# Round 11: the lower half is a rounded box (0.7 -> 0.36): the upper comes down the
# side nearly upright and turns under onto the outsole along a feather line, as a
# lasted upper does, instead of rounding into the bottom like a boat (no sole edge).
SQ_LO = 0.36       # superellipse exponent of the lower half: upright side, turned-under edge
SQ_UP = 0.9        # upper half: rounded toe box / quarters
SQ_HEEL = 1.0      # ... both blend to a plain ellipse round the heel cup
HEEL_ROUND = (-4.0, 12.0)  # y range (px) of that blend
# (Round 5-10 painted the middle of the arch underside tan. Round 11: the outsole slab
# below carries the tan underside; the shell's underside is inside it.)
# Waist: the lower half of each section narrows toward the sole through the
# shank (fraction of the half width at the bottom centre), so the arch reads
# as a slim sole bridging to the heel seat instead of a filled wedge, and the
# heel cup tapers toward the stiletto from behind. _clear_foot still keeps
# the foot inside.
WAIST = ((-32.0, 0.0), (-22.0, 0.15), (-12.0, 0.38), (0.0, 0.38), (8.0, 0.28), (15.0, 0.14), (20.0, 0.0))
FOOT_P = 2.3       # body foot section exponent (body.build_foot)
FOOT_CLEAR = 1.8   # px the shell keeps outside the foot
RIM_T = 1.3        # px: upper thickness at the rolled topline
LINING_D = 2.5     # px the tan lining runs down inside the opening


def _spow(v, p):
    return math.copysign(abs(v) ** p, v)


_STATION_COLS = list(zip(*STATIONS))
_WAIST_Y, _WAIST_K = (list(c) for c in zip(*WAIST))
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
    """Push a shell point (panel px, true z px) out of the foot by FOOT_CLEAR.

    Above the foot's centre the clearance scales with the section (FOOT_CLEAR over its
    smaller half axis, as in rounds 4-10). Below it, round 11 keeps the same clearance
    sideways but only FOOT_CLEAR px under the foot's sole: the scaled clearance put the
    shell 5 px under the tall slices at the ball (half height 39 px against a half width
    of 14) and pushed a 2 mm bulge into the sole there."""
    sec = _foot_section(y)
    if sec is None:
        return x, zpx
    cx, hw, cz, hh = sec
    dx, dz = x - cx, zpx - cz
    need = 1.0 + FOOT_CLEAR / min(hw, hh)
    if dz < 0.0:
        hw, hh, need = hw * need, hh + FOOT_CLEAR, 1.0
    r = (abs(dx / hw) ** FOOT_P + abs(dz / hh) ** FOOT_P) ** (1.0 / FOOT_P)
    if r < need and r > 1e-6:
        k = need / r
        return cx + dx * k, cz + dz * k
    return x, zpx


LEG_CAP = 5.0      # px: body.build_leg's pole cap below its last ring
_LEG_CACHE = {}


def _leg_outline(row):
    """Body leg skin at body `row` as (x, y) px points round the ring (body.leg_section
    + body.leg_offset, so the malleoli and the heel count), or None below the leg."""
    lo, hi = LEG_ROWS[0], LEG_ROWS[-1]
    if not lo <= row <= hi + LEG_CAP:
        return None
    row = round(row, 2)       # the cache key is the row the outline is computed for
    if row not in _LEG_CACHE:
        r = min(row, hi)
        cx, cy, hw, hd = leg_section(r)
        k = 1.0 if row <= hi else max(0.0, 1.0 - (row - hi) / LEG_CAP) ** 0.5
        a = 2 * math.pi * np.arange(72) / 72
        f = leg_offset(r)
        off = np.array([f(dx, dy) for dx, dy in zip(np.cos(a), np.sin(a))])
        _LEG_CACHE[row] = np.stack([cx + (np.cos(a) * hw + off[:, 0]) * k,
                                    cy - (np.sin(a) * hd + off[:, 1]) * k], 1)
    return _LEG_CACHE[row]


def _clear_leg(x, y, zpx):
    """Round 8: the leg runs on into the heel below the malleoli (body.ANKLE_ROW), so
    a shell point at the topline may sit over the leg rather than the foot: push it
    out sideways (x) to FOOT_CLEAR outside the leg's skin at its own y."""
    pts = _leg_outline(spec.SHEET_GROUND_Y - zpx)
    if pts is None:
        return x
    xs = []
    for (x0, y0), (x1, y1) in zip(pts, np.roll(pts, -1, axis=0)):
        if (y0 - y) * (y1 - y) <= 0 and abs(y1 - y0) > 1e-9:
            xs.append(x0 + (x1 - x0) * (y - y0) / (y1 - y0))
    if len(xs) < 2:
        return x
    lo, hi = min(xs) - FOOT_CLEAR, max(xs) + FOOT_CLEAR
    if lo < x < hi:
        mid = (min(xs) + max(xs)) / 2
        return hi if x >= mid else lo
    return x


def _ring(st, sx):
    y, cx, hw, zb, zt, frac, skew, pinch, keel, rin = st
    closed = frac >= 0.999
    phim = math.pi * (1.0 if closed else frac)
    zb_m, zt_m = zrow(zb), zrow(zt)
    cend = max(1e-6, -math.cos(phim))
    # the heel cup turns elliptical (no boxy sole corners bulging round the
    # heel seat in the back view)
    u = min(1.0, max(0.0, (y - HEEL_ROUND[0]) / (HEEL_ROUND[1] - HEEL_ROUND[0])))
    u = u * u * (3.0 - 2.0 * u)
    sq_lo, sq_up = SQ_LO + (SQ_HEEL - SQ_LO) * u, SQ_UP + (SQ_HEEL - SQ_UP) * u
    waist = _pchip(_WAIST_Y, _WAIST_K, y)
    # half height so the ring ends land on the top row
    hh = (zt_m - zb_m) / (1.0 + abs(math.cos(phim)) ** sq_up)
    zmid = zb_m + hh
    pts = []
    for k in range(RING):
        phi = phim * (2.0 * k / (RING - 1) - 1.0)
        s, c = math.sin(phi), math.cos(phi)
        sq = sq_lo if c > 0.0 else sq_up
        xo = hw * _spow(s, sq)
        if c < 0.0:     # upper half: pinch toward the centre line
            xo *= 1.0 - pinch * (-c / cend) ** 0.8
        else:           # lower half: slim waist through the shank
            xo *= 1.0 - waist * c ** 1.5
        x = cx + xo - skew * ((1 + c) / 2) ** 1.5
        z = zmid - hh * _spow(c, sq)
        # (round 11: no keel; the flat outsole is the bottom, the shell turns under onto it)
        if c <= 0.0 and s < 0.0:   # inner upper quarter: raised inner side wall
            z += rin * PX * min(1.0, -c / cend)
        if closed and k in (0, RING - 1):
            x = cx - skew * ((1 + c) / 2) ** 1.5      # exact top centre: ends merge
        x, zpx = _clear_foot(x, y, z / PX)
        x = _clear_leg(x, y, zpx)
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
    for a, b in zip(rings, rings[1:]):
        for j in range(RING - 1):
            face((a[j], a[j + 1], b[j + 1], b[j]))
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
    # in edge order, not a set: BMVerts hash by address, so a set's order (and the
    # new rim vertices' indices) changed from one process to the next
    bverts = list(dict.fromkeys(v for e in bnd for v in e.verts))
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


# ---------------------------------------------------------------- outsole
# Round 11, after 风堇's shoes (a separate sole slab under the upper, with a step): a thin
# slab under the forepart and the shank. At each shell station its top lies SOLE_EMBED px
# above the shell's lowest point, so the shell's turned-under edge is inside it and the
# upper meets it along a feather line; there its edge stands SOLE_STEP px proud of the
# upper, a crisp ledge. Square edges, green walls, the sheet's tan `sole` underneath (the
# sheet's back view shows that tan between green rims either side of the heel). It is part
# of shoes_shell: rigid on the foot (rig.RIGID_FOOT).
#   * Toe: over the last SOLE_TOE px the slab thins (embed and margin to SOLE_TIP_T, a
#     0.8 mm edge) and its ledge narrows to nothing; ahead of the shell's last ring it
#     follows the upper's own fan into the toe point, so the pointed toe stays as sharp
#     as round 10's (a rounded plate past the point read as a spatula / square stub).
#   * Heel breast: over SOLE_END the ledge narrows to nothing and the slab melts into the
#     shell (its tread bends up onto the shell's rounded bottom, its walls shrink away), so
#     it ends inside the upper just ahead of the stiletto (running on into the heel, its
#     corners stood out of the heel's round breast as small box tabs).
SOLE_T = 0.0023     # m: slab thickness (embed + margin), normal to the sole line
SOLE_EMBED = 1.0    # px: slab top above the shell's lowest point (vertical)
SOLE_STEP = 0.5     # px: slab edge beyond the upper at the feather line
SOLE_TOE = 15.0     # px from the toe point over which the slab thins and its ledge narrows
SOLE_TIP_T = (0.3, 0.2)   # px at the toe point: embed (top above the upper's bottom), margin
                          # (tread under it): a 0.5 px = 0.8 mm edge
SOLE_TIP_BACK = (0.06, 0.35)  # px the slab's point (top, tread) stays behind the upper's tip
SOLE_END = (-1.5, 3.0)    # y range (px) over which the slab sinks into the shell; it ends at
                          # SOLE_END[1], a shell ring just ahead of the heel's breast (y 3.8)
SOLE_END_Y = (0.0, 1.5)   # extra sections through that fade
SOLE_END_IN = 0.2   # px the slab's end stays inside the shell
SOLE_TREAD_N = 4    # tread segments across (flat but where it bends onto the shell at the end)
# The slab's outline hull thins to nothing toward its point (vertex group OUTLINE_VG), so
# the upper's own hull draws the toe point: two hulls offset along different normals at the
# point drew a small notch / spur on it.
OUTLINE_VG = 'shoe_line'
SOLE_LINE_FADE = 4.0   # px from the toe point
_CUT = 'shoe_line_cut'  # vertex layer: 1 - the outline weight (0 everywhere but the slab's point)


def _feather(ring, z):
    """Outermost x where a shell ring ((x, z) px pairs, left shoe) crosses height z."""
    xs = []
    for (x0, z0), (x1, z1) in zip(ring, ring[1:]):
        if (z0 - z) * (z1 - z) <= 0.0 and abs(z1 - z0) > 1e-9:
            xs.append(x0 + (x1 - x0) * (z - z0) / (z1 - z0))
    return min(xs), max(xs)


def _smoothstep(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3.0 - 2.0 * t)


def _toe_k(y):
    """0 at the toe point, 1 from SOLE_TOE px behind it."""
    return _smoothstep((y - TOE_TIP[1]) / SOLE_TOE)


def _end_f(y):
    """1 ahead of the heel-breast fade, 0 at the slab's end."""
    return 1.0 - _smoothstep((y - SOLE_END[0]) / (SOLE_END[1] - SOLE_END[0]))


def _shell_lower(y):
    """The shell ring at y as (x, z) px pairs (left shoe) and its lowest z."""
    ring = [(p.x / PX, p.z / PX) for p in _ring(_station(y), 1)]
    return ring, min(z for _, z in ring)


def _arc_z(ring, x):
    """Lowest z where a shell ring ((x, z) px pairs) crosses the vertical at x: its bottom."""
    zs = []
    for (x0, z0), (x1, z1) in zip(ring, ring[1:]):
        if (x0 - x) * (x1 - x) <= 0.0 and abs(x1 - x0) > 1e-9:
            zs.append(z0 + (z1 - z0) * (x - x0) / (x1 - x0))
    return min(zs)


def _outsole_sections():
    """Slab sections toe -> heel end (left shoe, px): each a ring of (x, y, z) points round
    the section, top inner, top outer, then the tread from its outer corner to its inner one
    (SOLE_TREAD_N + 1 points)."""
    ys = sorted({y for y in SAMPLES if y <= SOLE_END[1]} | set(SOLE_END_Y))
    tops = []
    for y in ys:
        ring, zb = _shell_lower(y)
        k, f = _toe_k(y), _end_f(y)
        embed = SOLE_TIP_T[0] + (SOLE_EMBED - SOLE_TIP_T[0]) * k
        margin = SOLE_TIP_T[1] + (SOLE_T / PX - SOLE_EMBED - SOLE_TIP_T[1]) * k
        zt = zb + embed
        xl, xr = _feather(ring, zt)
        # the ledge: full from SOLE_TOE px behind the point, none at the point or the end;
        # at the end the top corners sit a little inside the shell
        st = SOLE_STEP * min(1.0, (y - TOE_TIP[1]) / SOLE_TOE) ** 0.8 * f - SOLE_END_IN * (1.0 - f)
        tops.append((y, zt, xl - st, xr + st, embed, margin, f))
    out = []
    for i, (y, zt, xl, xr, embed, margin, f) in enumerate(tops):
        a, b = tops[max(i - 1, 0)], tops[min(i + 1, len(tops) - 1)]
        d = Vector((b[0] - a[0], b[1] - a[1])).normalized()
        # the thickness is laid off along the sole line's normal (in the side view), so the
        # slab stays SOLE_T thick up the steep shank; at the end it turns vertical
        n = Vector((d.y, -d.x)).lerp(Vector((0.0, -1.0)), 1.0 - f).normalized()
        t = embed + margin
        yb, zbot = y + n.x * t, zt + n.y * t
        tread = []
        if f < 1.0:
            # the tread bends up onto the shell's rounded bottom (SOLE_END_IN inside it) and
            # the walls shrink to nothing, so the slab's end lies wholly inside the upper
            ring_b, _ = _shell_lower(yb)
            for j in range(SOLE_TREAD_N + 1):
                x = xr + (xl - xr) * j / SOLE_TREAD_N
                za = min(_arc_z(ring_b, x) + SOLE_END_IN, zt - 0.02)
                tread.append((x, yb, zbot + (za - zbot) * (1.0 - f)))
        else:
            tread = [(xr + (xl - xr) * j / SOLE_TREAD_N, yb, zbot) for j in range(SOLE_TREAD_N + 1)]
        out.append([(xl, y, zt), (xr, y, zt)] + tread)
    return out


def _outsole(bm, sx):
    """Closed outsole slab of one shoe; returns (faces, the tread's lowest z in px)."""
    secs = _outsole_sections()
    # (a new vertex layer would invalidate the vertices made so far: make it first)
    cut = bm.verts.layers.float.get(_CUT) or bm.verts.layers.float.new(_CUT)
    rings = [[bm.verts.new(Pz(x, y, z, sx)) for x, y, z in c] for c in secs]
    m = len(rings[0])
    faces = []

    def face(vs, mat):
        f = bm.faces.new(vs)
        f.material_index = mat
        faces.append(f)
    # ring: 0 top inner, 1 top outer, 2 .. m-1 the tread outer -> inner; top (hidden but
    # for the ledge) and the walls green, the tread tan
    for a, b in zip(rings, rings[1:]):
        for j in range(m):
            k = (j + 1) % m
            face((a[j], a[k], b[k], b[j]), 1 if 2 <= j < m - 1 else 0)
    # toe point: ahead of the shell's first ring the upper is a fan of triangles into its
    # tip, so the slab runs straight into a vertical edge SOLE_TIP_T thick just behind and
    # under the tip (its top on the fan's bottom line, its tread a little further back):
    # the slab's outline and the ledge (none there) converge with the upper's point
    tx, ty, tz = TOE_TIP[0], TOE_TIP[1], zrow(TOE_TIP[2]) / PX
    top = bm.verts.new(Pz(tx, ty + SOLE_TIP_BACK[0], tz - 0.02, sx))
    bot = bm.verts.new(Pz(tx, ty + SOLE_TIP_BACK[1], tz - 0.02 - sum(SOLE_TIP_T), sx))
    tip = Pz(tx, ty, tz, sx)
    for v in [top, bot] + [v for r in rings[:3] for v in r]:
        v[cut] = 1.0 - _smoothstep((v.co - tip).length / PX / SOLE_LINE_FADE)
    r0 = rings[0]
    face((r0[0], r0[1], top), 0)
    face((r0[1], r0[2], bot, top), 0)
    for j in range(2, m - 1):
        face((r0[j], r0[j + 1], bot), 1)
    face((r0[m - 1], r0[0], top, bot), 0)
    face(list(reversed(rings[-1])), 0)   # the end, inside the shell
    floor = min(v.co.z for r in rings for v in r) / PX
    return faces, floor


# ---------------------------------------------------------------- heel
# Stiletto, rows top -> bottom: (row, centre y, half depth y, half width x).
# The top ring is the heel-seat footprint, sunk into the shell above its
# underside (row ~899), so the shaft grows out of the seat with no seam. Its
# cap ends inside the foot's heel pad, out of sight, as in round 2.
# Round 5: two more rings through the seat-to-shaft flare (a short concave
# neck instead of one crease) and 14 sides, so the shaft reads round.
HEEL = [
    (895.0, 11.0, 8.4, 6.6),
    (898.0, 10.9, 7.5, 5.8),
    (901.0, 10.8, 6.9, 5.35),
    (904.5, 10.75, 5.7, 4.75),
    (908.0, 10.7, 4.75, 4.3),
    (914.0, 10.5, 3.85, 3.8),
    (920.0, 10.3, 3.3, 3.4),
    (935.0, 9.9, 2.5, 2.9),
    (944.0, 9.6, 2.1, 2.6),
]
HEEL_X = 29.5
HEEL_SIDES = 14
HEEL_SQ = 0.8      # shaft section: a rounded box (broad back face, tight sides: no wide
                   # shade strip down the shaft from behind)
# Round 11 (风堇's heels end in a cap): a top lift, a separate tan block under the shaft's
# tip, standing LIFT_STEP proud of it with a crisp top edge and a small chamfer round
# the tread. Its tread is level with the outsole's (both rest on the floor); the shaft
# ends LIFT_SINK px inside it.
LIFT_H = 0.003     # m: top-lift height
LIFT_STEP = 0.15   # px the lift stands out round the shaft's tip
LIFT_BEVEL = 0.2   # px: chamfer round the tread
LIFT_SINK = 0.2    # px the shaft's tip reaches into the lift


def _heel_at(row):
    """(centre y, half depth, half width) of the stiletto at `row` (linear in the table,
    extended past its ends)."""
    rows = HEEL
    i = 0 if row <= rows[0][0] else min(len(rows) - 2, max(k for k in range(len(rows) - 1) if rows[k][0] <= row))
    (r0, *a), (r1, *b) = rows[i], rows[i + 1]
    t = (row - r0) / (r1 - r0)
    return tuple(u + (v - u) * t for u, v in zip(a, b))


def _heel_ring(bm, sx, zpx, cy, ry, rx):
    ring = []
    for i in range(HEEL_SIDES):
        a = 2 * math.pi * (i + 0.5) / HEEL_SIDES
        ring.append(bm.verts.new(Pz(HEEL_X + rx * _spow(math.cos(a), HEEL_SQ),
                                    cy + ry * _spow(math.sin(a), HEEL_SQ), zpx, sx)))
    return ring


def _close_tube(bm, rings):
    faces = []
    for a, b in zip(rings, rings[1:]):
        for j in range(HEEL_SIDES):
            k = (j + 1) % HEEL_SIDES
            faces.append(bm.faces.new((a[j], a[k], b[k], b[j])))
    faces.append(bm.faces.new(rings[0]))
    faces.append(bm.faces.new(list(reversed(rings[-1]))))
    return faces


def _heel(bm, sx, floor):
    """Closed stiletto and its top lift, whose tread is at `floor` (true z px); returns
    (shaft faces, lift faces) (normals fixed by the caller)."""
    top = floor + LIFT_H / PX                       # the lift's top
    tip_row = row_of(top - LIFT_SINK)               # the shaft's tip, inside the lift
    table = [h[1:] + (zrow(h[0]) / PX,) for h in HEEL if h[0] < tip_row - 0.5]
    table.append(_heel_at(tip_row) + (top - LIFT_SINK,))
    shaft = _close_tube(bm, [_heel_ring(bm, sx, z, cy, ry, rx) for cy, ry, rx, z in table])
    cy, ry, rx = _heel_at(row_of(top))
    s, b = LIFT_STEP, LIFT_BEVEL
    lift = _close_tube(bm, [_heel_ring(bm, sx, top, cy, ry + s, rx + s),
                            _heel_ring(bm, sx, floor + b, cy, ry + s, rx + s),
                            _heel_ring(bm, sx, floor, cy, ry + s - b, rx + s - b)])
    return shaft, lift


# ---------------------------------------------------------------- ribbons
RIB_SIDES = 6      # lace section: a flattened hexagon (rounded strap)
RIB_SQ = 0.75      # superellipse exponent of the section: fuller than an ellipse
RIB_EDGE_N = 0.45  # shading normals: broad-face normal + this much of the radial
                   # direction, so each face shades as one flat strap (as the sheet
                   # paints the laces) instead of a round cord with a terminator
RIB_N_ATTR = 'shoe_rib_n'
# the outermost section vertices sit at +-30 degrees: scale them out to the full width
RIB_REACH = math.cos(math.pi / RIB_SIDES) ** RIB_SQ


def _ribbon(bm, pts, nrms, w, th, closed=False, taper=1.0, swell=None, frac=None):
    """Lace along pts (world): a rounded strap section `w` wide and `th`
    thick, its broad faces toward +-nrms (pass nrms pointing away from the
    skin). `taper` scales the width at the far end of an open ribbon (by `frac`,
    each point's share of the length, default its index share); `swell`
    (optional, one factor per point) scales width and thickness locally."""
    m = len(pts)
    if frac is None:
        frac = [i / (m - 1) for i in range(m)]
    nl = bm.verts.layers.float_vector.get(RIB_N_ATTR) or bm.verts.layers.float_vector.new(RIB_N_ATTR)
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
        k = swell[i] if swell is not None else 1.0
        hw = 0.5 * w * k * (1.0 + (taper - 1.0) * (frac[i] if not closed else 0.0))
        ht = 0.5 * th * k
        ring = []
        for j in range(RIB_SIDES):
            # half-step offset: no vertex sits exactly on an edge, so every
            # vertex belongs to one broad face (top or bottom)
            a = 2.0 * math.pi * (j + 0.5) / RIB_SIDES
            ca, sa = math.cos(a), math.sin(a)
            v = bm.verts.new(p + b * (hw * _spow(ca, RIB_SQ) / RIB_REACH) + n * (ht * _spow(sa, RIB_SQ)))
            v[nl] = (n * math.copysign(1.0, sa) + b * (RIB_EDGE_N * ca)).normalized()
            ring.append(v)
        rings.append(ring)
    pairs = list(zip(rings, rings[1:]))
    if closed:
        pairs.append((rings[-1], rings[0]))
    for a, b in pairs:
        for j in range(RIB_SIDES):
            k = (j + 1) % RIB_SIDES
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
# Round 9 tried 2.6-4.2 mm ribbons, 1.1-1.4 mm thick (strengths guide 3.10); pairwise
# review (docs/pr/r9-5-trims) called them heavy and their shaded backs added shade islands,
# so the laces keep round 8's size. The crossing lift follows the thickness.
RIB_W = 0.0023     # ribbon width, m
RIB_T = 0.0009     # ribbon thickness, m
RIB_CROSS = RIB_T / PX + 0.15   # px the upper lace rides above the lower where they cross
# Round 11: smoothing along the lace softens that lift (0.8 mm left at the instep), so the
# upper lace also gets a bump after smoothing: at least CROSS_CLEAR over the lower lace's
# centre line, along the skin normal, across the lower lace's width and fading out over
# CROSS_RAMP on either side.
CROSS_CLEAR = RIB_T + 0.0003     # m
CROSS_RAMP = 1.0 * RIB_W         # m


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
    # round 11: and the leg's real outline (leg_section + leg_offset: malleoli, tendon,
    # heel), so a lace never runs closer than RIB_OFF to a bump the ellipse misses (the
    # outer malleolus came within 0.3 mm of the instep laces)
    out = _leg_outline(spec.SHEET_GROUND_Y - zpx)
    if out is not None:      # 72 points round: four between each for _skin_radius's 0.7 px rays
        nxt = np.roll(out, -1, axis=0)
        pts += [tuple(p) for k in range(4) for p in out + (nxt - out) * (k / 4)]
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
    row = row_of(zpx)
    sec = _ankle_sec(row)
    cx, cy, rx, ry = sec[:4]
    d = Vector((x - cx, y - cy))
    dist = d.length
    d.normalize()
    th = math.degrees(math.atan2(d.x / rx, -d.y / ry))
    return th, row, dist - _skin_radius(sec, d.x, d.y)


# Round 11: a lace is no longer a polyline through 2-4 projected samples per control span
# (a visible kink about every 1 cm, the skin tables' facets on top). Its controls are
# sampled densely, projected onto the skin, smoothed along the lace (Gaussian, LACE_SIGMA;
# open ends stay put) and resampled by arc length, closer where it bends: at most
# LACE_TURN per sample and LACE_STEP apart on straight runs.
LACE_DENSE = 48      # Catmull-Rom samples per control span before smoothing
LACE_SIGMA = 2.0     # px: smoothing along the lace
LACE_STEP = 3.2      # px: longest step between samples (straight runs)
LACE_MIN = 0.5       # px: shortest step (the bow loops' tight ends)
LACE_TURN = 7.0      # degrees: most a lace turns between two samples


def _arclen(P, closed):
    seg = np.linalg.norm((np.roll(P, -1, 0) if closed else P[1:]) - P[:-1 if not closed else None], axis=1)
    return seg, np.concatenate([[0.0], np.cumsum(seg)])


def _smooth_line(P, sigma, closed):
    """Gaussian smoothing of a polyline along its arc length (sigma in m). Open ends are
    padded by point reflection, which keeps each end point and its direction."""
    seg, s = _arclen(P, closed)
    if closed:
        L = s[-1]
        s = s[:-1]
        d = s[None, :] - s[:, None]
        d = (d + L / 2) % L - L / 2
        ds = (seg + np.roll(seg, 1)) / 2
        w = np.exp(-0.5 * (d / sigma) ** 2) * ds[None, :]
        return (w @ P) / w.sum(1, keepdims=True)
    L = s[-1]
    k0 = max(1, int(np.searchsorted(s, 3 * sigma)))
    k1 = max(1, int(len(s) - np.searchsorted(s, L - 3 * sigma)))
    k0, k1 = min(k0, len(P) - 1), min(k1, len(P) - 1)
    EP = np.concatenate([2 * P[0] - P[k0:0:-1], P, 2 * P[-1] - P[-2:-k1 - 2:-1]])
    ES = np.concatenate([-s[k0:0:-1], s, 2 * L - s[-2:-k1 - 2:-1]])
    ds = np.gradient(ES)
    w = np.exp(-0.5 * ((ES[None, :] - s[:, None]) / sigma) ** 2) * ds[None, :]
    out = (w @ EP) / w.sum(1, keepdims=True)
    out[0], out[-1] = P[0], P[-1]
    return out


def _resample(P, closed, step=LACE_STEP, turn=LACE_TURN, least=LACE_MIN):
    """Arc-length parameters (m) for samples along polyline P: at most `turn` degrees of
    bend and `step` px apart, never closer than `least` px."""
    seg, s = _arclen(P, closed)
    Q = np.vstack([P, P[:1]]) if closed else P
    tng = np.diff(Q, axis=0)
    tng /= np.maximum(np.linalg.norm(tng, axis=1, keepdims=True), 1e-12)
    prev = np.roll(tng, 1, 0) if closed else np.vstack([tng[:1], tng[:-1]])
    ang = np.arccos(np.clip((tng * prev).sum(1), -1.0, 1.0))      # bend at each segment's start
    kappa = ang / np.maximum((seg + (np.roll(seg, 1) if closed else np.r_[seg[:1], seg[:-1]])) / 2, 1e-9)
    # density (samples per m), smoothed so the spacing changes gradually
    rho = np.maximum(kappa / math.radians(turn), 1.0 / (step * PX))
    sig = 2.0 * PX
    mid = s[:-1] + seg / 2
    if closed:
        L = s[-1]
        d = (mid[None, :] - mid[:, None] + L / 2) % L - L / 2
    else:
        d = mid[None, :] - mid[:, None]
    w = np.exp(-0.5 * (d / sig) ** 2) * seg[None, :]
    rho = np.minimum((w @ rho) / w.sum(1), 1.0 / (least * PX))
    cost = np.concatenate([[0.0], np.cumsum(rho * seg)])
    n = max(int(math.ceil(cost[-1])), 8 if closed else 2)
    tgt = np.linspace(0.0, cost[-1], n, endpoint=False) if closed else np.linspace(0.0, cost[-1], n + 1)
    return np.interp(tgt, cost, s), s


def _at(P, s, closed, si):
    """Points of polyline P (arc lengths s) at arc lengths si."""
    Q = np.vstack([P, P[:1]]) if closed else P
    return np.stack([np.interp(si, s, Q[:, k]) for k in range(3)], 1)


def _seg_closest(A, B):
    """Closest points between every segment of polyline A (n x 3) and every segment of
    polyline B (m x 3), vectorised (Ericson, Real-Time Collision Detection 5.1.9): distances
    (n-1, m-1), the parameter along A's segments, and the closest points on A and on B."""
    A0, d1 = A[:-1, None], (A[1:] - A[:-1])[:, None]
    B0, d2 = B[None, :-1], (B[1:] - B[:-1])[None]
    r = A0 - B0
    a = np.maximum((d1 * d1).sum(-1), 1e-30)
    e = np.maximum((d2 * d2).sum(-1), 1e-30)
    b, c, f = (d1 * d2).sum(-1), (d1 * r).sum(-1), (d2 * r).sum(-1)
    den = a * e - b * b
    s = np.where(den > 1e-24, np.clip((b * f - c * e) / np.maximum(den, 1e-30), 0.0, 1.0), 0.0)
    t = (b * s + f) / e
    s = np.where(t < 0.0, np.clip(-c / a, 0.0, 1.0), np.where(t > 1.0, np.clip((b - c) / a, 0.0, 1.0), s))
    t = np.clip(t, 0.0, 1.0)
    p, q = A0 + d1 * s[..., None], B0 + d2 * t[..., None]
    return np.linalg.norm(p - q, axis=-1), s, p, q


def _cross_bump(P, N, over):
    """Lift the open polyline P (dense, smoothed; N its outward normals) where it passes over
    the lace `over` (its built centre line), so that there its centre line stands at least
    CROSS_CLEAR over the lower one's along the skin normal: a plateau across the lower lace's
    width, fading out over CROSS_RAMP on either side. Applied after the smoothing, which
    would flatten it."""
    O = np.array([tuple(v) for v in over], float)
    d, sp, p, q = _seg_closest(P, O)
    i, j = np.unravel_index(np.argmin(d), d.shape)
    Nu = N / np.linalg.norm(N, axis=1, keepdims=True)
    n = Nu[i] + (Nu[i + 1] - Nu[i]) * sp[i, j]
    n /= np.linalg.norm(n)
    h = CROSS_CLEAR - float(np.dot(p[i, j] - q[i, j], n))
    if h <= 0.0:
        return P
    tp = (P[i + 1] - P[i]) / np.linalg.norm(P[i + 1] - P[i])
    to = (O[j + 1] - O[j]) / np.linalg.norm(O[j + 1] - O[j])
    sin = max(0.3, float(np.linalg.norm(np.cross(tp, to))))
    half = 0.5 * RIB_W / sin + 0.25 * RIB_W
    seg, s = _arclen(P, False)
    dist = np.abs(s - (s[i] + seg[i] * sp[i, j]))
    t = np.clip((dist - half) / CROSS_RAMP, 0.0, 1.0)
    return P + (h * (1.0 - t * t * (3.0 - 2.0 * t)))[:, None] * Nu


def _lace(bm, pts, nrms, closed=False, w=RIB_W, taper=1.0, swell=None, sigma=LACE_SIGMA, least=LACE_MIN,
          over=None):
    """Smooth, resample and build a lace from a dense centre line `pts` (N x 3, m) with
    outward normals `nrms` (N x 3). `swell(f)` scales the section by the arc-length
    share f (0..1, closed: 1 is the start again). `over`: the centre line of a lace this
    one crosses over (see _cross_bump)."""
    P = _smooth_line(np.asarray(pts, float), sigma * PX, closed)
    N = _smooth_line(np.asarray(nrms, float), sigma * PX, closed) if len(nrms) > 1 else None
    if over is not None and N is not None and not closed:
        P = _cross_bump(P, N, over)
    si, s = _resample(P, closed, least=least)
    pts = [Vector(p) for p in _at(P, s, closed, si)]
    if N is None:
        nn = [Vector(nrms[0])] * len(pts)
    else:
        nn = [Vector(n).normalized() for n in _at(N, s, closed, si)]
    frac = list(si / s[-1])
    sw = [swell(f) for f in frac] if swell else None
    _ribbon(bm, pts, nn, w, RIB_T, closed=closed, taper=taper, swell=sw, frac=frac)
    return pts


def _leg_line(ctrl, sx, closed=False, around=False):
    """Dense centre line and outward normals (N x 3 arrays) of a lace through
    (theta, row, off) controls round the skin. `around`: a closed loop whose theta runs
    once round the leg (wraps at 360 degrees)."""
    n = LACE_DENSE
    if around:
        m = len(ctrl)
        ext = ([(ctrl[-1][0] - 360.0,) + tuple(ctrl[-1][1:])] + list(ctrl)
               + [(c[0] + 360.0,) + tuple(c[1:]) for c in ctrl[:2]])
        samples = _catmull(ext, n)[n:n * (m + 1)]
    else:
        samples = _catmull(ctrl, n, closed)
    pts = [ank(th, r, off, sx) for th, r, off in samples]
    nrms = [(ank(th, r, off + 1.0, sx) - p).normalized() for (th, r, off), p in zip(samples, pts)]
    return np.array([tuple(p) for p in pts]), np.array([tuple(v) for v in nrms])


def _on_leg(bm, ctrl, sx, closed=False, w=RIB_W, taper=1.0, around=False, swell=None, over=None):
    """Lace through (theta, row, off) controls around the skin (see _leg_line)."""
    pts, nrms = _leg_line(ctrl, sx, closed, around)
    return _lace(bm, pts, nrms, closed=closed or around, w=w, taper=taper, swell=swell, over=over)


KNOT = (-12.0, 832.0)  # bow knot (theta, row)
CROSS = (-6.0, 885.0)  # instep lace crossing (theta, row)


def _band_row(theta):
    """Ankle wrap: high at the front knot, low at the back (leaf base)."""
    return 841.0 - 9.0 * math.cos(math.radians(theta - KNOT[0]))


# The bow's knot (round 11, after 风堇's closed, pinched bow knots): a closed bead over the
# wrap, the gathered loop roots and the ends' starts, all of which it buries: a
# superellipsoid KNOT_R px (semi-axes: round the leg along the wrap, up the leg, out from
# the skin) about a point KNOT_C px off the skin, a rounded box seen from the front and a
# dome from the side, its height pinched in the middle (KNOT_PINCH) where it is cinched,
# so it bulges a little where the loops enter on either side. Its inner face lies under
# the wrap, its outer one over the loops. (Round 10's patch read as a cube; round 11's
# first band, a closed ribbon with an open middle, as a metal ring.)
KNOT_ROOT = RIB_OFF + 0.75   # px off the skin: the loops and ends are gathered here,
                             # just outside the wrap they are tied from
KNOT_C = RIB_OFF + 0.6
KNOT_R = (1.15, 1.0, 0.8)    # px: ~3.6 mm round the leg, 3.1 mm tall, 2.5 mm thick
KNOT_E = (0.6, 0.8)          # exponents: front outline (rounded box), side profile
KNOT_PINCH = 0.12
KNOT_SEG = (16, 6)           # segments round the front outline, from the inner pole to the outer


def _knot(bm, sx):
    """Closed knot bead of one bow (shaded with its own smooth normals)."""
    kth, krow = KNOT
    c = ank(kth, krow, KNOT_C, sx)
    out = (ank(kth, krow, KNOT_C + 1.0, sx) - c).normalized()
    along = ank(kth + 1.0, krow, KNOT_C, sx) - ank(kth - 1.0, krow, KNOT_C, sx)
    along = (along - out * along.dot(out)).normalized()
    up = out.cross(along).normalized()
    ra, ru, ro = (r * PX for r in KNOT_R)
    e1, e2 = KNOT_E

    def at(phi, th):
        ca, cu = _spow(math.cos(phi), e1), _spow(math.sin(phi), e1)
        rad, h = _spow(math.cos(th), e2), _spow(math.sin(th), e2)
        pinch = 1.0 - KNOT_PINCH * (1.0 - ca * ca)
        return c + along * (ra * ca * rad) + up * (ru * pinch * cu * rad) + out * (ro * h)

    nphi, nth = KNOT_SEG
    nl = bm.verts.layers.float_vector.get(RIB_N_ATTR) or bm.verts.layers.float_vector.new(RIB_N_ATTR)
    eps = 1e-3

    def vert(phi, th):
        v = bm.verts.new(at(phi, th))
        if abs(th) > math.pi / 2 - 1e-6:
            n = out * math.copysign(1.0, th)
        else:
            dp = at(phi + eps, th) - at(phi - eps, th)
            dt = at(phi, th + eps) - at(phi, th - eps)
            n = dp.cross(dt).normalized()
            if n.dot(v.co - c) < 0.0:
                n = -n
        v[nl] = n
        return v
    rings = [[vert(2 * math.pi * i / nphi, -math.pi / 2 + math.pi * j / nth) for i in range(nphi)]
             for j in range(1, nth)]
    poles = (vert(0.0, -math.pi / 2), vert(0.0, math.pi / 2))
    for a, b in zip(rings, rings[1:]):
        for i in range(nphi):
            k = (i + 1) % nphi
            bm.faces.new((a[i], a[k], b[k], b[i]))
    for i in range(nphi):
        k = (i + 1) % nphi
        bm.faces.new((poles[0], rings[0][k], rings[0][i]))
        bm.faces.new((poles[1], rings[-1][i], rings[-1][k]))
    return c


def _ribbons(bm, sx, line):
    """All laces of one shoe; returns their centre lines by name and the knot's centre (for
    the clearance report)."""
    o = RIB_OFF
    laces = {}
    # ankle wrap
    laces['wrap'] = _on_leg(bm, [(th, _band_row(th), o) for th in range(-180, 180, 60)], sx,
                            around=True)
    # instep criss-cross: each lace starts tucked under the rolled topline on
    # one side of the vamp, climbs across the instep (crossing a little to
    # the inner side, as on the sheet), reaches the far side of the leg and
    # runs round behind the ankle into the wrap. The second lace rides one
    # ribbon thickness higher where they cross.
    # Round 11: the lace reaching the outer side ends in the knot the leaves and the long
    # end spring from (as on the sheet's side view, where it runs up to the leaves' base),
    # not just behind it: the rig takes the leaves' root weights from the nearest larger
    # skinned piece, and this lace is it (passing 7 mm under the root, it handed the root
    # 20% foot and stretched the blades x1.58 in kneel_one).
    for s, lift in ((1, 0.0), (-1, RIB_CROSS)):
        want = ank(-78.0 * s, 908.0, o, sx)
        anchor = min(line, key=lambda q: (q - want).length)
        th0, row0, off0 = _to_leg(anchor, sx)
        back = ([(112.0, 857.5, o), (LEAF_THETA, _band_row(LEAF_THETA) + 0.5, o)] if s > 0 else
                [(-125.0, 856.0, o), (-150.0, _band_row(-150.0) + 1.0, o)])
        laces[f'instep{s:+d}'] = _on_leg(
            bm, [(th0, row0, off0 - RIM_T * 0.5), (CROSS[0], CROSS[1], o + lift),
                 (72 * s, 866.0, o + lift)] + back, sx, over=laces.get('instep+1'))
    # back X above the heel counter: wrap sides -> across the back -> tab top. The outer
    # lace rides over the inner one where they cross behind the tendon (round 8's lift
    # left their centre lines 0.5 mm apart: the 0.9 mm laces cut through each other).
    for s in (-1, 1):
        hi = RIB_CROSS if s > 0 else 0.0
        laces[f'back{s:+d}'] = _on_leg(
            bm, [(115 * s, _band_row(115 * s), o), (165 * s, 853.0, o + hi),
                 (192 * s, 859.0, o + hi + 0.3)], sx, over=laces.get('back-1'))
    # bow: two full loops spreading sideways from the knot at the front of
    # the ankle and lifting off the skin toward their ends (a soft teardrop:
    # narrow at the knot, round at the far end), a gathering knot and two
    # short ends falling away from it
    kth, krow = KNOT
    for s, span, hgt in ((1, 68.0, 8.0), (-1, 61.0, 7.5)):
        ctrl = []
        for i in range(8):
            t = 2 * math.pi * i / 8
            u = (1 - math.cos(t)) / 2                       # 0 at the knot, 1 at the far end
            th = kth + s * span * u
            row = krow - 3.5 * u - hgt * math.sin(t) * (0.35 + 0.65 * u ** 0.7) * s
            # the roots are gathered in the knot band, just outside the wrap
            ctrl.append((th, row, o + 0.8 + (KNOT_ROOT - o - 0.8) * (1 - u) + 5.0 * u * u))
        # the ribbon is a little narrower where it is gathered into the knot
        laces[f'loop{s:+d}'] = _on_leg(bm, ctrl, sx, closed=True,
                                       swell=lambda f: 0.8 + 0.2 * (1 - math.cos(2 * math.pi * f)) / 2)
    for s in (1, -1):
        laces[f'end{s:+d}'] = _on_leg(   # starting inside the knot
            bm, [(kth + 0.3 * s, krow + 0.3, KNOT_ROOT), (kth + 8 * s, krow + 6.5, o + 1.6),
                 (kth + 15 * s, krow + 13.0, o + 1.7), (kth + 21 * s, krow + 19.0, o + 1.5)],
            sx, taper=0.55)
    knot = _knot(bm, sx)
    # long end hanging at the outer back below the leaves, swinging out a
    # little (kept close to the heel: further back it crosses the ankle's
    # knee/ankle weight blend and stretches when the foot points)
    # It leaves the wrap under the leaf root, so the leaves and the tail
    # spring from one knot, and runs back along the wrap's direction before
    # it falls (Catmull-Rom through the controls: no kinks).
    tail = [(47.0, 9.0, 853.5), (52.2, 14.5, 866.0), (53.6, 18.0, 881.0),
            (51.5, 19.2, 899.0)]
    ctrl = [tuple(wrap_point(RIB_OFF, sx))] + [tuple(P(*p, sx)) for p in tail]
    laces['tail'] = _lace(bm, _catmull(ctrl, LACE_DENSE), [tuple(Vector((sx, 0.35, 0.0)).normalized())],
                          taper=0.6)
    return laces, knot


LOOPS = ('wrap', 'loop+1', 'loop-1')   # the closed laces


def lace_report(laces, skip=(), reach=0.002, reach_wrap=0.012):
    """Closest approach (mm) of every pair of laces, segment to segment along their built
    centre lines (so a crossing between two samples counts: comparing the samples alone,
    up to 5 mm apart, missed the instep crossing), away from the open ends (`reach`; with
    the wrap `reach_wrap`: a lace leaving the wrap runs along it for ~1 cm before it parts
    from it) and from the `skip` spheres ((centre, radius): the knot):
    [(distance, name a, name b, world point)], closest first."""
    lines = {}
    for k, v in laces.items():
        L = np.array([tuple(p) for p in v], float)
        lines[k] = np.vstack([L, L[:1]]) if k in LOOPS else L
    out = []
    names = sorted(lines)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            A, B = lines[a], lines[b]
            d, _, p, q = _seg_closest(A, B)
            ok = np.ones(d.shape, bool)
            r = reach_wrap if 'wrap' in (a, b) else reach
            for name, L, x in ((a, A, p), (b, B, q)):
                if name not in LOOPS:
                    ok &= np.minimum(np.linalg.norm(x - L[0], axis=-1), np.linalg.norm(x - L[-1], axis=-1)) > r
            for c, r in skip:
                c = np.asarray(tuple(c), float)
                ok &= (np.linalg.norm(p - c, axis=-1) > r) & (np.linalg.norm(q - c, axis=-1) > r)
            d = np.where(ok, d, np.inf)
            k = np.unravel_index(np.argmin(d), d.shape)
            if np.isfinite(d[k]):
                out.append((d[k] * 1000, a, b, tuple(np.round(p[k], 4))))
    return sorted(out)


# ---------------------------------------------------------------- leaves
LEAF_THETA = 132.0   # leaf root on the ankle wrap: outer back (degrees from the front)
LEAF_ROOT_OFF = 0.9  # px the root sits outside the wrap's centre line (on top of the ribbon)
LEAVES = [  # tip (x, y, row), half width px, roll about the blade axis (deg), twist to the tip (deg)
    ((65.0, 30.5, 804.0), 11.5, -38.0, -12.0),
    ((73.0, 44.0, 824.0), 12.5, 30.0, 14.0),
]
LEAF_FACE = (1.0, -0.5, 0.3)   # blade face normal before the roll: outer, a little front and up
LEAF_RINGS = 9
LEAF_STALK = 0.2   # fraction of the length over which the blade widens from a narrow
                   # stalk (35% of the ovate width) to the full ovate width
# Round 9 tried thicker (1.1 mm half), deeper-cupped (0.30) blades with a raised midrib
# (strengths guide 3.10): pairwise review (docs/pr/r9-5-trims) found no difference and
# each change added a shade island on the rear blade in the high view, so they stay.
LEAF_T = 0.0008   # blade half thickness at the midrib, m
LEAF_CUP = 0.22   # the halves curve up toward the face (fraction of the half width at the edge)
LEAF_RIB = 0.6    # midrib groove on the face, as a fraction of LEAF_T
LEAF_PEAK = 0.8   # width profile exponent: widest at ~0.42 of the length (ovate)


def wrap_point(off, sx=1):
    """World point `off` px outside the skin on the ankle wrap's line at
    LEAF_THETA: the knot the leaves (off = RIB_OFF + LEAF_ROOT_OFF) and the
    long lace end (off = RIB_OFF) spring from."""
    return ank(LEAF_THETA, _band_row(LEAF_THETA), off, sx)


def _leaf(bm, base, tip, half_w, roll, sx, twist=0.0):
    """Ovate, cupped blade from base to tip (left-shoe world coordinates) with
    a soft midrib groove on its face; the finished points are mirrored for
    sx=-1 so both feet curl the same way. The section is a closed lens: five
    points across the face, three across the back, sharing the two edges."""
    def V(v):
        return bm.verts.new(Vector((sx * v.x, v.y, v.z)))

    axis = tip - base
    length = axis.length
    a = axis.normalized()
    # blade faces outward and a little forward and up (LEAF_FACE): broad in
    # the front, side and back views alike; each blade is rolled its own way
    # about its axis so the pair fans and never turns edge-on together
    n0 = Quaternion(a, math.radians(roll)) @ Vector(LEAF_FACE).normalized()
    wdir = a.cross(n0).normalized()
    nrm = wdir.cross(a).normalized()
    if nrm.dot(n0) < 0:
        nrm = -nrm
    th = LEAF_T
    nrm0, wdir0 = nrm, wdir
    rings = []
    for i in range(1, LEAF_RINGS + 1):
        t = i / (LEAF_RINGS + 1)
        # the blade turns gradually about its axis toward the tip (each leaf
        # its own way), so its face changes along the length instead of
        # reading as one flat paddle
        q = Quaternion(a, math.radians(twist) * t * t)
        nrm, wdir = q @ nrm0, q @ wdir0
        w = half_w * PX * math.sin(math.pi * t ** LEAF_PEAK)
        w *= 0.35 + 0.65 * min(1.0, t / LEAF_STALK) ** 0.7   # narrow stalk at the root
        c = base + axis * t + nrm0 * (math.sin(math.pi * t) * 0.05 * length)  # blade arches back
        c -= wdir0 * (0.05 * length * t * t)                # slight sideways curl
        h = th * min(1.0, 4.0 * t * (1.0 - t) + 0.25)      # thinner toward root and tip

        def pt(u, side):
            lift = LEAF_CUP * w * (0.55 * abs(u) + 0.45 * u * u)
            off = side * h * (1.0 - u * u)
            if side > 0 and u == 0.0:
                off -= LEAF_RIB * h                         # midrib groove
            return V(c + wdir * (u * w) + nrm * (lift + off))
        rings.append([pt(-1.0, 1), pt(-0.5, 1), pt(0.0, 1), pt(0.5, 1), pt(1.0, 1),
                      pt(0.5, -1), pt(0.0, -1), pt(-0.5, -1)])
    n = len(rings[0])
    for r0, r1 in zip(rings, rings[1:]):
        for j in range(n):
            k = (j + 1) % n
            bm.faces.new((r0[j], r0[k], r1[k], r1[j]))
    # bases pulled apart slightly so the two blades do not share a vertex
    vb, vt = V(base + a * (0.4 * PX)), V(tip)
    for j in range(n):
        k = (j + 1) % n
        bm.faces.new((vb, rings[0][k], rings[0][j]))
        bm.faces.new((vt, rings[-1][j], rings[-1][k]))


# ---------------------------------------------------------------- build
def _finish(bm):
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-7)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def _strap_normals(me):
    """Custom normals from the per-vertex strap normals _ribbon stored."""
    attr = me.attributes.get(RIB_N_ATTR)
    if attr is None:
        return
    nrm = [Vector(d.vector) for d in attr.data]
    me.attributes.remove(attr)
    # the hexagonal end caps keep their own face normal
    loops = [None] * len(me.loops)
    for poly in me.polygons:
        for li in poly.loop_indices:
            loops[li] = poly.normal.copy() if poly.loop_total > 4 else nrm[me.loops[li].vertex_index]
    me.normals_split_custom_set(loops)


def build(col):
    shell_bm, rib_bm, leaf_bm = bmesh.new(), bmesh.new(), bmesh.new()
    shell_bm.verts.layers.float.new(_CUT)     # before any vertex (see _outsole)
    solids = []
    # leaf root in left-shoe coordinates: _leaf mirrors its points itself
    root = wrap_point(RIB_OFF + LEAF_ROOT_OFF)
    for sx in (1, -1):
        line = _shell(shell_bm, sx)
        sole, floor = _outsole(shell_bm, sx)
        shaft, lift = _heel(shell_bm, sx, floor)
        for f in lift:
            f.material_index = 1
        solids += sole + shaft + lift
        laces, knot = _ribbons(rib_bm, sx, line)
        for tip, hw, roll, twist in LEAVES:
            _leaf(leaf_bm, root, P(*tip), hw, roll, sx, twist)
        if sx > 0:
            rep = lace_report(laces, skip=[(knot, 1.2 * max(KNOT_R) * PX)])
            near = [r for r in rep if r[0] < RIB_T * 1000]
            cross = {f'{a}x{b}': d for d, a, b, _ in rep if (a, b) in (('instep+1', 'instep-1'), ('back+1', 'back-1'))}
            print(f'SHOES tread at {floor * PX * 1000:.2f} mm; laces closer than the lace '
                  f'thickness: {len(near)}', ' '.join(f'{a}x{b} {d:.2f}mm' for d, a, b, _ in near[:6]),
                  '| crossings', ' '.join(f'{k} {d:.2f}mm' for k, d in sorted(cross.items())))
    # the outsoles, heels and lifts are closed: let bmesh orient them; the open shells
    # are wound outward by construction (_shell)
    bmesh.ops.recalc_face_normals(shell_bm, faces=solids)
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
    _strap_normals(rib.data)
    leaf = common.new_object(col, 'shoes_leaves', leaf_bm, [common.toon_material('leaf')])
    common.shade_smooth(leaf, 60.0)
    # for the rig: where the leaves spring from (the knot on the ankle wrap, both feet,
    # world m): each blade rides the wrap there and the leg skin further up (rig.SKIN_ORNAMENTS)
    leaf['levi_attach_points'] = [tuple(root), (-root.x, root.y, root.z)]
    objs = [shell, rib, leaf]
    attr = shell.data.attributes[_CUT]
    w = [1.0 - d.value for d in attr.data]
    shell.data.attributes.remove(attr)
    vg = shell.vertex_groups.new(name=OUTLINE_VG)
    for k in sorted(set(w)):
        vg.add([i for i, x in enumerate(w) if x == k], k, 'REPLACE')
    common.add_outline(shell, vertex_group=OUTLINE_VG, min_factor=0.0)
    common.add_outline(rib, width=0.0010)
    common.add_outline(leaf, width=0.0014)
    return objs
