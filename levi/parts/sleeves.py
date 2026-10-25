"""Detached bishop sleeves: a drawstring-gathered top whose fabric flares up
into a muted-green petal ruffle, tied with a green ribbon bow; a drooping
balloon of fabric (light green under the drawstring fading to pale mint); and
a two-tier white frilled cuff at the wrist.

Everything is modelled for the character's left arm (+X) and mirrored to the
right with a Mirror modifier that is applied before the outline is added.

Geometry is fitted directly to the reference panels rather than to the rough
spec.L arm landmarks: the sheet's wrist (where the hand leaves the cuff) sits at
about front px (538, 436), i.e. ~20 px further out and ~20 px higher than
spec.L['wrist'] = (520, 455), and the gathered band sits on the upper arm at
about (415, 292). Coordinates below are written in reference pixels:
  front panel (col, row) -> world (x, z), side-panel column offset -> world y.
"""
import math

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

from .. import common, spec

CX = spec.PANEL_W / 2


def W(col, row, side_col=None):
    """Front-panel pixel (+ optional side-panel column) -> world point."""
    y = 0.0 if side_col is None else spec.px_to_h(side_col - CX)
    return Vector((spec.px_to_h(col - CX), y, spec.px_to_z(row)))


px = spec.px_to_h   # pixel length -> metres


Y = Vector((0.0, 1.0, 0.0))

# ---------------------------------------------------------------- balloon
# Stations down the sleeve. Each ring lies in the plane spanned by the front-view
# segment (outer edge -> inner edge) and world Y, so the front silhouette is the
# union of those segments and the side silhouette the union of ellipses.
#   (outer edge col,row), (inner edge col,row), side-view centre col, side half-depth px
STATIONS = [
    ((433, 280), (398, 304), 296, 21),   # s0 gathered under the band
    ((450, 288), (382, 320), 295, 30),
    ((465, 301), (373, 338), 297, 38),
    ((486, 325), (393, 366), 299, 44),
    ((509, 347), (414, 392), 301, 48),
    ((535, 370), (437, 421), 302, 51),
    ((556, 385), (461, 451), 302, 51),   # widest, just above the cuff
    ((553, 395), (480, 457), 301, 44),
    ((546, 401), (493, 455), 299, 32),
    ((537, 405), (506, 447), 297, 15),   # gathered into the cuff
]
RING_N = 24
SUPER = 0.82          # superellipse exponent (<1 = fuller, boxier balloon)
SUBDIV = 2            # interpolated rings per station gap

# Gradient sleeve_dark -> sleeve (0..1) by front-sheet row. Measured on the
# sheet: right under the drawstring the balloon is already a light green
# (~#A8CCAC, t~0.45), it pales fast to ~#D9EDD7 by row 334 and only reaches
# the plain sleeve mint around the elbow-level row ~400.
GRAD_KEYS = ((278, 0.42), (290, 0.50), (310, 0.70), (334, 0.80),
             (352, 0.85), (372, 0.92), (398, 1.0))


def _grad(co):
    row = spec.panel_px('front', co)[1]
    if row <= GRAD_KEYS[0][0]:
        return GRAD_KEYS[0][1]
    for (r0, t0), (r1, t1) in zip(GRAD_KEYS, GRAD_KEYS[1:]):
        if row <= r1:
            return t0 + (t1 - t0) * (row - r0) / (r1 - r0)
    return 1.0


def _catmull(p0, p1, p2, p3, t):
    t2, t3 = t * t, t * t * t
    return 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2
                  + (-p0 + 3 * p1 - 3 * p2 + p3) * t3)


def _interp(rows, sub):
    """Catmull-Rom resample of a list of float tuples (sub points per gap)."""
    out = []
    n = len(rows)
    for i in range(n - 1):
        p0, p1, p2, p3 = (rows[max(i - 1, 0)], rows[i], rows[i + 1], rows[min(i + 2, n - 1)])
        for k in range(sub):
            t = k / sub
            out.append(tuple(_catmull(a, b, c, d, t) for a, b, c, d in zip(p0, p1, p2, p3)))
    out.append(rows[-1])
    return out


def _spow(v, e):
    return math.copysign(abs(v) ** e, v)


def _ring(st, n=RING_N, scale=1.0, shift=None):
    oc, orow, ic, irow, sc, ry = st
    po, pi = W(oc, orow), W(ic, irow)
    mid = (po + pi) / 2 + Y * px(sc - CX) + (shift if shift is not None else Vector())
    a = (po - pi) / 2 * scale
    b = px(ry) * scale
    pts = []
    for k in range(n):
        th = 2 * math.pi * k / n
        pts.append(mid + a * _spow(math.cos(th), SUPER) + Y * (b * _spow(math.sin(th), SUPER)))
    return pts


def _orient_outward(bm, centres):
    """Flip a lofted open surface so its normals point away from the ring centres."""
    bm.normal_update()
    score = 0.0
    for f in bm.faces:
        c = f.calc_center_median()
        ctr = min(centres, key=lambda p: (p - c).length_squared)
        score += f.normal.dot(c - ctr) * f.calc_area()
    if score < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
    return bm


def _loft_out(rings):
    bm = common.loft(rings, closed=True)
    return _orient_outward(bm, [sum(r, Vector()) / len(r) for r in rings])


def _balloon_bm():
    flat = [(o[0], o[1], i[0], i[1], sc, ry) for o, i, sc, ry in STATIONS]
    sts = _interp(flat, SUBDIV)
    rings = [_ring(s) for s in sts]

    # Turned-in hems at both openings so the fabric reads as having thickness.
    def inward(st, toward):
        oc, orow, ic, irow, sc, _ = st
        c = (W(oc, orow) + W(ic, irow)) / 2
        return (toward - c).normalized() * px(3)

    top_c = (W(*STATIONS[1][0]) + W(*STATIONS[1][1])) / 2
    bot_c = (W(*STATIONS[-2][0]) + W(*STATIONS[-2][1])) / 2
    rings.insert(0, _ring(sts[0], scale=0.86, shift=inward(sts[0], top_c)))
    rings.append(_ring(sts[-1], scale=0.82, shift=inward(sts[-1], bot_c)))
    return _loft_out(rings)


# ---------------------------------------------------------------- band, frills
DOWN_ARM = Vector((0.6, 0.0, -0.8))   # rough forearm direction, for orienting frames


def _station_mid(st):
    (oc, orow), (ic, irow), sc, _ = st
    return (W(oc, orow) + W(ic, irow)) / 2 + Y * px(sc - CX)


BAND_MID = _station_mid(STATIONS[0])    # gathered band wraps the first ring
CUFF_MID = _station_mid(STATIONS[-1])   # cuff wraps the last ring


def _frame(o_px, i_px):
    """(e, axis) in world XZ from a front-view outer->inner segment.

    e points from the inner to the outer edge (outward/up), axis is
    perpendicular to it pointing down the arm (toward the hand).
    """
    e = (W(*o_px) - W(*i_px))
    e.y = 0.0
    e.normalize()
    axis = Vector((e.z, 0.0, -e.x))
    if axis.dot(DOWN_ARM) < 0:
        axis = -axis
    return e, axis


BAND_E, BAND_AX = _frame(STATIONS[0][0], STATIONS[0][1])
TIE = BAND_MID - BAND_AX * px(1)        # drawstring centre (ruffle waist, bow knot)


def _perp_xz(f):
    """Unit vector in world XZ perpendicular to f, pointing to +X (outward)."""
    e = Vector((-f.z, 0.0, f.x)).normalized()
    return -e if e.x < 0 else e


def _petal(th, k, phase, point):
    """Periodic petal profile in -1..1: cosine blended toward a triangle wave
    (point=1) so the crests come to soft points like the sheet's frills."""
    c = math.cos(k * th + phase)
    return (1.0 - point) * c + point * (2.0 / math.pi) * math.asin(max(-1.0, min(1.0, c)))


def _frill_ring(c, e, ra, rb, n, k=0, amp=0.0, lift_dir=None, lift=0.0, phase=0.0, point=0.5):
    """Ellipse (e, b) of radii ra, rb around c; k petals push the ring out
    radially by amp and along lift_dir by lift at their crests. b is world Y
    made perpendicular to e and lift_dir (= Y when lift_dir lies in XZ)."""
    b = Y.copy()
    if lift_dir is not None:
        b = b - lift_dir * b.dot(lift_dir)
    b = (b - e * b.dot(e)).normalized()
    pts = []
    for j in range(n):
        th = 2 * math.pi * j / n
        g = _petal(th, k, phase, point) if k else 0.0
        w = 1.0 + amp * g
        p = c + e * (ra * w * math.cos(th)) + b * (rb * w * math.sin(th))
        if lift_dir is not None and lift:
            p = p + lift_dir * (lift * g)
        pts.append(p)
    return pts


def _tube_bm(c, e, axis, ra, rb, a0, a1, n=24):
    rings = [_frill_ring(c + axis * a, e, ra, rb, n) for a in (a0, (a0 + a1) / 2, a1)]
    return _loft_out(rings)


# Top ruffle. The sheet's heading is a tulip of soft pointed petals rising
# out of the drawstring and curling outward at the rim: in both the front and
# the side view the middle petals stand tallest (front row ~244, ~37 px above
# the tie) while the side petals splay out lower (front tips ~(382, 281) and
# (456, 266); side cols 257..332). It is lit on its upper face and shaded
# where the petals turn down; pleats between the petals give the alternating
# lit/shade folds the sheet paints.
TIE_R = 22.0                  # px, drawstring radius (covers the balloon's ~22 px top ring)
# Axis at the rim: tilted toward the body, flatter than the band (the sheet's
# side petal tips slope down toward the body).
RIM_NORMAL = Vector((-0.2, 0.0, 0.98)).normalized()
RUFFLE_SHIFT = Vector((px(5.0), 0.0, 0.0))   # rim centre offset (front: ~col 419)
# (height along the axis px, radius front px, radius side px, pleat amp, petal lift px)
RUFFLE_PROFILE = (
    (0.0, TIE_R, TIE_R, 0.03, 0.0),       # cinched by the drawstring
    (16.0, 25.0, 25.0, 0.10, 1.5),
    (33.0, 30.0, 31.0, 0.16, 5.5),        # shoulder: the tallest petals
    (30.0, 35.0, 36.0, 0.22, 6.0),        # rim curling outward and down
    (27.5, 34.0, 35.0, 0.22, 6.0),        # rolled hem (gives the rim a fold line)
)
RUFFLE_N = 40
RUFFLE_PETALS = 10
RUFFLE_POINT = 0.0            # profile blend; at 4 samples per petal it has no effect


def _ruffle_bm():
    k, n = RUFFLE_PETALS, RUFFLE_N
    # tucked into the balloon's gathered top
    rings = [_frill_ring(BAND_MID + BAND_AX * px(6), BAND_E, px(TIE_R + 1), px(TIE_R + 1), n)]
    last = len(RUFFLE_PROFILE) - 1
    for i, (h, ra, rb, amp, lift) in enumerate(RUFFLE_PROFILE):
        s = min(1.0, i / (last - 1))      # the hem shares the rim's frame
        f = (-BAND_AX).lerp(RIM_NORMAL, s).normalized()
        c = TIE + f * px(h) + RUFFLE_SHIFT * s
        rings.append(_frill_ring(c, _perp_xz(f), px(ra), px(rb), n, k, amp, f, px(lift),
                                 point=RUFFLE_POINT))
    return _loft_out(rings)


def _flare(c0, d0, c1, d1, r0, r1, n, k, steps, phase=0.0, point=0.5, power=1.2):
    """Fluted frill lofted from a gathered ring (centre c0, normal d0, radii
    r0 px) to a flared rim (c1, d1, r1 px). steps: one (s 0..1, pleat amp,
    petal lift px) per ring."""
    rings = []
    for s, amp, lift in steps:
        f = d0.lerp(d1, s).normalized()
        sc = s ** power
        ra, rb = r0[0] + (r1[0] - r0[0]) * sc, r0[1] + (r1[1] - r0[1]) * sc
        rings.append(_frill_ring(c0.lerp(c1, s), _perp_xz(f), px(ra), px(rb), n, k, amp, f,
                                 px(lift), phase, point))
    return rings


# Cuff: two tiers of fluted white frill spilling out of the balloon hem
# toward the hand and drooping a little (so the side view sees a bell, as
# drawn, rather than looking straight into the opening).
#   (offset along the arm px, base radii, rim radii, length px, petal phase)
CUFF_TIERS = (
    (1.0, (21, 15), (33, 38), 16.0, 0.0),
    (8.0, (19, 14), (28, 33), 15.0, math.pi / 7),
)
CUFF_N = 35
CUFF_FLUTES = 7
CUFF_DROOP = 0.6              # downward tilt added to the arm axis at the rim
CUFF_FORWARD = 0.5            # forward (-Y) tilt: the front view sees into the shaded underside
CUFF_STEPS = ((0.0, 0.0, 0.0), (0.5, 0.07, 1.0), (1.0, 0.15, 2.5))
# The tiers are thin closed shells, not open sheets: an open rim facing the
# camera gets no inverted-hull line, and the sheet's frill lobes are all
# outlined.
CUFF_THICK = 1.0              # px


def _cuff_bms():
    e, axis = _frame(STATIONS[-1][0], STATIONS[-1][1])
    c = CUFF_MID
    # Elliptical like the balloon's turned-in hem (~21 x 12 px) so no gap shows.
    band = _tube_bm(c, e, axis, px(22), px(15), px(-3), px(6), n=16)
    droop = (axis + Vector((0.0, -CUFF_FORWARD, -CUFF_DROOP))).normalized()
    tiers = []
    for off, r0, r1, length, ph in CUFF_TIERS:
        c0 = c + axis * px(off)
        rings = _flare(c0, axis, c0 + droop * px(length), droop, r0, r1, CUFF_N, CUFF_FLUTES,
                       CUFF_STEPS, ph, 0.0, power=1.4)
        bm = _loft_out(rings)
        bmesh.ops.solidify(bm, geom=bm.faces[:], thickness=px(CUFF_THICK))
        bm.normal_update()
        tiers.append(bm)
    return band, tiers


# ---------------------------------------------------------------- bow + ribbons
# The sheet draws the bow face-on in every view (front knot ~(430, 277), side
# ~col 294), so it sits on the front-outer diagonal of the band where both
# the front and the side views see it, its two loops lying along the band and
# drooping down the sleeve, outlined dark green like the sheet's ribbon.
RIB_R = 0.0019
BOW_ANG = math.radians(55.0)  # around the band from front (-Y) toward the outer side
LOOP_LEN = 36.0               # px, knot -> loop tip
LOOP_W = 15.0                 # px, loop opening
LOOP_DROOP = math.radians(30.0)
LOOP_SPLAY = 6.0              # px the loop tips stand off the band (seen in front and side)
FRONT_TAILS = [
    [(437, 313), (453, 340), (457, 373), (442, 400), (432, 440)],
    [(429, 315), (427, 345), (428, 372), (417, 398), (413, 424)],
]
# The back view shows the same pair of tails (mirrored), hanging behind.
BACK_TAILS = [
    [(436, 312), (451, 335), (455, 372), (441, 401), (431, 441)],
    [(428, 316), (427, 347), (414, 373), (417, 400), (417, 426)],
]


def _polyline(pts, sub=2):
    rows = [tuple(p) for p in pts]
    return [Vector(p) for p in _interp(rows, sub)]


def _clear(p, bvhs, gap):
    """Push p out of each (outward-oriented) surface in bvhs to at least gap."""
    for bvh in bvhs:
        loc, nrm, _, _ = bvh.find_nearest(p)
        if loc is not None and (p - loc).dot(nrm) < gap:
            p = loc + nrm * gap
    return p


def _knot_bm(c, r, u=8, v=5):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=u, v_segments=v, radius=r)
    bmesh.ops.translate(bm, vec=c, verts=bm.verts)
    return bm


def _bow(bvhs):
    """Knot + two loops on the front-outer band; returns (knot point, [bm]).
    Loop points are kept clear of the surfaces in bvhs (balloon, ruffle)."""
    e0, ax0 = BAND_E, BAND_AX
    d = e0 * math.sin(BOW_ANG) - Y * math.cos(BOW_ANG)   # out of the band
    t = e0 * math.cos(BOW_ANG) + Y * math.sin(BOW_ANG)   # along the band
    knot = TIE + d * px(TIE_R + 3.5)
    out = [_knot_bm(knot, px(3.4))]
    m = 16
    L, Wd = px(LOOP_LEN), px(LOOP_W)
    for s in (-1, 1):
        u = t * (s * math.cos(LOOP_DROOP)) + ax0 * math.sin(LOOP_DROOP)
        v = ax0 * math.cos(LOOP_DROOP) - t * (s * math.sin(LOOP_DROOP))
        pts = []
        for j in range(m + 1):
            tau = 2 * math.pi * j / m
            a = (1 - math.cos(tau)) / 2               # 0 at the knot, 1 at the tip
            p = (knot + u * (L * a) + v * (Wd / 2 * math.sin(tau) * a ** 0.4)
                 + d * (px(3.0) * math.sin(math.pi * a) + px(LOOP_SPLAY) * a))
            pts.append(_clear(p, bvhs, px(2.2)))
        pts[-1] = pts[0] + u * px(0.6)  # avoid a coincident start/end ring
        out.append(common.tube_along(pts, [RIB_R] * len(pts), n=4))
    return knot, out


def _tails(knot, bvh, front=True):
    """Ribbon tails hanging from the knot, draped just outside the balloon."""
    out = []
    sign = -1.0 if front else 1.0
    kc, kr = spec.panel_px('front', knot)
    for path in (FRONT_TAILS if front else BACK_TAILS):
        pts2 = _polyline([(kc, kr)] + path)
        pts = [knot]
        y_prev = knot.y
        for p2 in pts2[1:]:
            o = W(p2.x, p2.y)
            o.y = sign * 1.0
            hit = bvh.ray_cast(o, Y * (-sign), 2.0)
            y = hit[0].y + sign * px(2.2) if hit[0] is not None else y_prev
            if sign * (y - knot.y) < 0:      # never tuck behind the knot
                y = knot.y
            y_prev = y
            pts.append(Vector((o.x, y, o.z)))
        radii = [RIB_R] * len(pts)
        radii[-1] = RIB_R * 0.7
        out.append(common.tube_along(pts, radii, n=4))
    return out


# ---------------------------------------------------------------- build
def _finish(col, name, bm, mat, grad=None, outline=None):
    obj = common.new_object(col, name, bm, [mat])
    common.shade_smooth(obj, 50.0)
    if grad:
        common.set_gradient(obj, grad)
    common.mirror_x(obj, merge=False)
    common.apply_modifiers(obj)
    common.add_outline(obj, outline)
    return obj


def _join(bms):
    """Merge several BMeshes into one (frees the inputs)."""
    me_bm = bmesh.new()
    for b in bms:
        tmp = bpy.data.meshes.new('_tmp_sleeve')
        b.to_mesh(tmp)
        b.free()
        me_bm.from_mesh(tmp)
        bpy.data.meshes.remove(tmp)
    return me_bm


def build(col):
    sleeve_mat = common.toon_material('sleeve_dark', gradient='sleeve')
    green = common.toon_material('green')
    # Plain palette materials: the ruffle renders exactly sleeve_dark, the
    # cuff exactly cuff (the sheet's cuff shade is greyer, ~#D8D0C9; that
    # would be a palette change).
    ruffle_mat = common.toon_material('sleeve_dark')
    cuff = common.toon_material('cuff')

    balloon = _balloon_bm()
    balloon.normal_update()
    ruffle = _ruffle_bm()
    ruffle.normal_update()
    bvh = BVHTree.FromBMesh(balloon)

    # Bow and tails are fitted to the balloon before the meshes are handed to
    # Blender. The loops are not pushed off the ruffle: its flare would fling
    # them up the arm. They stay clear of it on their own (knot TIE_R + 3.5 px
    # out, loops splaying further out, at most ~6 px up the arm where the
    # ruffle is still ~23 px in radius).
    knot, bow = _bow([bvh])
    back = BAND_E * math.sin(BOW_ANG) + Y * math.cos(BOW_ANG)
    knot_b = TIE + back * px(TIE_R + 2.5)
    ribbon = (bow + _tails(knot, bvh, front=True)
              + [_knot_bm(knot_b, px(2.6), 6, 4)] + _tails(knot_b, bvh, front=False))

    _finish(col, 'sleeve_balloon', balloon, sleeve_mat, grad=_grad)
    _finish(col, 'sleeve_ruffle', ruffle, ruffle_mat)

    cuff_band, tiers = _cuff_bms()
    _finish(col, 'sleeve_cuff', _join([cuff_band] + tiers), cuff)

    _finish(col, 'sleeve_ribbon', _join(ribbon), green, outline=spec.OUTLINE_WIDTH * 0.5)
