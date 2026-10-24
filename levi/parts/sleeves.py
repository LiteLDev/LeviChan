"""Detached bishop sleeves: gathered top band with a muted-green ruffle and a
green ribbon bow, a drooping balloon of fabric (green at the top fading to pale mint) and a
white frilled cuff at the wrist.

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

# Gradient: green right under the band, easing quickly to pale mint (sheet rows).
GRAD_ROWS = (282, 362)
GRAD_EASE = 2.2


def _grad(co):
    row = spec.panel_px('front', co)[1]
    t = max(0.0, min(1.0, (row - GRAD_ROWS[0]) / (GRAD_ROWS[1] - GRAD_ROWS[0])))
    return 1.0 - (1.0 - t) ** GRAD_EASE


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
BAND_R = 23.0
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


def _ellipse(c, e, ra, rb, n, wave=0.0, freq=0, axis=None, lift=0.0, phase=0.0):
    pts = []
    for k in range(n):
        th = 2 * math.pi * k / n
        w = 1.0 + wave * math.sin(freq * th + phase)
        p = c + e * (ra * w * math.cos(th)) + Y * (rb * w * math.sin(th))
        if axis is not None and lift:
            p = p + axis * (lift * math.cos(freq * th + phase))
        pts.append(p)
    return pts


def _tube_bm(c, e, axis, ra, rb, a0, a1, n=24):
    rings = [_ellipse(c + axis * a, e, ra, rb, n) for a in (a0, (a0 + a1) / 2, a1)]
    return _loft_out(rings)


def _top_frill_bm():
    """Ruffled heading flaring up and out above the gathered band."""
    base = BAND_MID + Vector((0, 0, px(2)))
    edge = W(421, 254, 293.5)
    f = (edge - base).normalized()
    e = Vector((-f.z, 0.0, f.x))
    if e.x < 0:
        e = -e
    n = 48
    mid = base.lerp(edge, 0.5) + e * px(1)
    rings = [
        _ellipse(base, e, px(21), px(21), n),
        _ellipse(mid, e, px(30), px(29), n, wave=0.05, freq=8),
        _ellipse(edge, e, px(37), px(36), n, wave=0.10, freq=8, axis=f, lift=px(4)),
    ]
    return _loft_out(rings)


def _cuff_bms():
    e, axis = _frame(STATIONS[-1][0], STATIONS[-1][1])
    c = CUFF_MID
    # Elliptical like the balloon's turned-in hem (~21 x 12 px) so no gap shows.
    band = _tube_bm(c, e, axis, px(22), px(15), px(-3), px(6))
    n = 54
    tiers = []
    for off, ra0, rb0, ra, rb, lift, ph in ((px(2), px(21), px(15), px(31), px(37), px(3), 0.0),
                                             (px(9), px(19), px(14), px(27), px(32), px(3), 0.4)):
        b0 = c + axis * off
        b1 = b0 + axis * px(7)
        b2 = b0 + axis * px(15)
        rings = [
            _ellipse(b0, e, ra0, rb0, n),
            _ellipse(b1, e, (ra0 + ra) / 2, (rb0 + rb) / 2, n, wave=0.06, freq=9, phase=ph),
            _ellipse(b2, e, ra, rb, n, wave=0.12, freq=9, axis=axis, lift=lift, phase=ph),
        ]
        tiers.append(_loft_out(rings))
    return band, tiers


# ---------------------------------------------------------------- bow + ribbons
RIB_R = 0.0019
FRONT_TAILS = [
    [(437, 313), (453, 340), (457, 373), (442, 400), (432, 440)],
    [(429, 315), (427, 345), (428, 372), (417, 398), (413, 424)],
]
# The back view shows the same pair of tails (mirrored), hanging behind.
BACK_TAILS = [
    [(436, 312), (451, 335), (455, 372), (441, 401), (431, 441)],
    [(428, 316), (427, 347), (414, 373), (417, 400), (417, 426)],
]


def _polyline(pts, sub=3):
    rows = [tuple(p) for p in pts]
    return [Vector(p) for p in _interp(rows, sub)]


def _knot_and_loops(e, axis):
    knot = BAND_MID + e * px(BAND_R + 6.0) + axis * px(4.0)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=8, v_segments=5, radius=px(4.0))
    bmesh.ops.scale(bm, vec=(1.0, 1.3, 1.0), verts=bm.verts)
    bmesh.ops.translate(bm, vec=knot, verts=bm.verts)
    loops = []
    m = 12
    for s in (-1, 1):
        pts = []
        for k in range(m + 1):
            tau = 2 * math.pi * k / m
            w = px(30) * (1 - math.cos(tau)) / 2           # spread along Y
            h = px(10) * math.sin(tau) - px(4) * (1 - math.cos(tau)) / 2
            # Loops splay off the sleeve (outward along e) so they read in
            # front, side and back views like the sheet's bow.
            p = knot + Y * (s * w) + e * (0.45 * w) - axis * h
            pts.append(p)
        pts[-1] = pts[0] + Y * (s * px(0.6))  # avoid a coincident start/end ring
        loops.append(common.tube_along(pts, [px(2.0)] * len(pts), n=4))
    return knot, bm, loops


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
    # The inverted-hull outline shell would otherwise cast a shadow over the
    # whole sleeve (EEVEE ignores the outline material's backface culling for
    # shadows), turning every face into the shade tone. Cel look: no casting.
    obj.visible_shadow = False
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
    cuff = common.toon_material('cuff')

    balloon = _balloon_bm()
    bvh = BVHTree.FromBMesh(balloon)
    _finish(col, 'sleeve_balloon', balloon, sleeve_mat, grad=_grad)

    e0, ax0 = _frame(STATIONS[0][0], STATIONS[0][1])
    band = _tube_bm(BAND_MID, e0, ax0, px(BAND_R), px(BAND_R), px(-5), px(6))
    # The sheet paints the heading ruffle in a muted green (~#5A9A6A, the
    # sleeve_dark shade), lighter than the dark ribbon green.
    _finish(col, 'sleeve_band', _join([band, _top_frill_bm()]), common.toon_material('sleeve_dark'))

    cuff_band, tiers = _cuff_bms()
    _finish(col, 'sleeve_cuff', _join([cuff_band] + tiers), cuff)

    knot, knot_bm, loops = _knot_and_loops(e0, ax0)
    tails = _tails(knot, bvh, front=True) + _tails(knot, bvh, front=False)
    _finish(col, 'sleeve_ribbon', _join([knot_bm] + loops + tails), green,
            outline=spec.OUTLINE_WIDTH * 0.5)
