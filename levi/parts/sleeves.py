"""Detached bishop sleeves, modelled as hanging cloth: a fabric tube gathered
under a soft drawstring band whose fabric flares into a low scalloped
dark-green frill, tied with a flat ribbon bow (folded loops, wrapped knot,
tapered tails); below the band the sleeve opens into a bell with a few broad
longitudinal folds (light green under the band fading to pale mint), and is
gathered again at the wrist, where its hem turns inward and a single white
ruffle spills out toward the hand.

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
import numpy as np
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


def _smooth(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3.0 - 2.0 * t)


# ---------------------------------------------------------------- balloon
# Stations down the sleeve. Each ring lies in the plane spanned by the front-view
# segment (outer edge -> inner edge) and world Y, so the front silhouette is the
# union of those segments and the side silhouette the union of ellipses.
#   (outer edge col,row), (inner edge col,row), side-view centre col, side half-depth px
# The side view is a bell: narrow under the band (the sheet's sleeve is ~45 px
# deep at row 280 and ~60 px at row 300), widening to ~100 px above the cuff
# and rounding off into the wrist gather.
STATIONS = [
    ((433, 280), (398, 304), 296, 19),   # s0 gathered under the band
    ((450, 288), (384, 320), 296, 27),
    ((465, 301), (376, 338), 297, 35),
    ((486, 325), (394, 366), 299, 42),
    ((509, 347), (414, 392), 301, 46),
    ((531, 367), (437, 421), 302, 49),
    # The bell eases into the wrist: its girth falls off over the last ~30 px
    # along the cuff axis instead of contracting across a flat annulus right
    # above the cuff (a boxy shelf). The outer (upper, wrist-side) shoulder
    # sits ~6 px inside the sheet's corner, and the hem stays loose (~60% of
    # the widest depth, as the sheet's side view draws it, with the cuff
    # ruffle spilling out of it) instead of cinching into a narrow neck, so
    # the end reads as cloth falling into a gathered hem, not a padded pod.
    # The hanging underside (inner edge) keeps its fullness.
    ((535, 377), (456, 441), 302, 44),   # widest
    ((537, 386), (469, 447), 301, 41),
    ((538, 394), (481, 450), 300, 37),
    ((538, 400), (492, 452), 299, 32),
    ((539, 404), (502, 451), 297, 28),   # gathered into the cuff: a loose hem, not a tight neck
]
SUPER = 1.0           # round (elliptical) sections; < 1 squares them off into panels
# Down the bell the cross-section turns egg-shaped: the Y depth is scaled by
# (1 - SAG cos th), so the upper (outer, th = 0) side flattens and the
# hanging inner side (th = pi) grows fuller, carrying more of the cloth at
# the lower edge instead of an even pod around the arm. The front silhouette
# is unchanged (only the Y depth is redistributed).
SAG = 0.08

# Rings: the same vertex count all the way down, so the fold lanes run as
# continuous quad strips. They are spaced evenly along the sleeve's profile
# (centre travel plus change of girth, see _ring_params), so the dome that
# rolls into the cuff is sampled as finely as the long run of the bell, and
# the rig's positional drape weights see a dense, regular lattice: no single
# ring decides where a weight knot falls. (Round 4 had 16 hand-placed rings,
# and moving two of them by 0.1 station pushed arms_forward from x1.76 to x1.88.)
RING_N = 48                   # vertices round each ring (~1 cm apart on the widest ring)
RING_COUNT = 40               # rings from the band to the wrist gather

# Folds. The radius is modulated by: fine pleats where the drawstring and the
# wrist gather the cloth; a soft five-fold swell falling from the band; and a
# few stable, unevenly spaced valleys that run down the bell, drifting a
# little around the arm and deepening toward the wrist, where the fullness is
# compressed into the cuff. Every fold is a broad rounded trough, several
# ring vertices and several rings wide, so the cloth can compress along the
# arm (a raised arm lets the bag fall back) without the folds creasing.
GATHER_K = 8                  # pleats at the gathers (6 ring vertices each: rounded, no slivers)
GATHER_TOP, GATHER_CUFF = 0.16, 0.05
SWELL_AMP = 0.07              # depth of the swell under the band (fraction of the radius)
# (ring angle rad: 0 = outer edge, pi/2 = back, -pi/2 = front; relative depth)
VALLEYS = ((-1.20, 0.9), (-0.55, 0.7), (0.70, 1.0), (2.35, 0.7), (-2.50, 0.8))
VALLEY_W = 0.40               # angular half-width (rad): ~6 ring vertices, a rounded trough
VALLEY_AMP = (0.07, 0.12)     # depth at the top of the bell / near the wrist
VALLEY_DRIFT = 0.25           # rad of sideways wander along the sleeve


def _fold(th, s):
    """Radial factor at ring angle th and sleeve parameter s (0 band .. 1 wrist).

    Valleys pull in and the ring is inflated by a share of their depth, so the
    ridges between them stand slightly proud of the fitted stations and the
    mean radius stays close to them."""
    fine = GATHER_TOP * (1.0 - _smooth(0.0, 0.3, s)) + GATHER_CUFF * _smooth(0.75, 1.0, s)
    v_fine = (1.0 - math.cos(GATHER_K * th + 0.4)) / 2.0
    swell = SWELL_AMP * _smooth(0.06, 0.25, s) * (1.0 - _smooth(0.3, 0.6, s))
    v_swell = (1.0 - math.cos(5 * th + 0.3)) / 2.0
    # valleys fade in below the band and hand over to the wrist pleats at the gather
    depth = ((VALLEY_AMP[0] + (VALLEY_AMP[1] - VALLEY_AMP[0]) * _smooth(0.3, 0.85, s))
             * _smooth(0.08, 0.25, s) * (1.0 - 0.55 * _smooth(0.88, 1.0, s)))
    v_val = 0.0
    for i, (phi, w) in enumerate(VALLEYS):
        c = phi + VALLEY_DRIFT * math.sin(math.pi * s + 1.3 * i)
        dth = (th - c + math.pi) % (2 * math.pi) - math.pi
        v_val += w * math.exp(-(dth / VALLEY_W) ** 2)
    return (1.0 - fine * v_fine - swell * v_swell + 0.4 * swell
            - depth * v_val + 0.25 * depth)


# Gradient sleeve_dark -> sleeve (0..1) by front-sheet row. Measured on the
# sheet: right under the drawstring the balloon is already a light green
# (~#A8CCAC, t~0.45), it pales fast to ~#D9EDD7 by row 330 and only reaches
# the plain sleeve mint around the elbow-level row ~400.
GRAD_KEYS = ((278, 0.42), (291, 0.50), (306, 0.62), (330, 0.76),
             (352, 0.84), (372, 0.91), (398, 1.0))


GRAD_SIDE = 0.14             # the gathered top is darker on the body side, lighter outward


def _grad(co):
    row = spec.panel_px('front', co)[1]
    t = 1.0
    if row <= GRAD_KEYS[0][0]:
        t = GRAD_KEYS[0][1]
    else:
        for (r0, t0), (r1, t1) in zip(GRAD_KEYS, GRAD_KEYS[1:]):
            if row <= r1:
                t = t0 + (t1 - t0) * (row - r0) / (r1 - r0)
                break
    # The sheet keeps the dark green under the band on the inner side (front
    # view) while the outer side (side view) is already light.
    u = max(-1.0, min(1.0, (co - BAND_MID).dot(BAND_E) / px(TIE_R)))
    return t + GRAD_SIDE * u * (1.0 - _smooth(292.0, 330.0, row))


def _catmull(p0, p1, p2, p3, t):
    t2, t3 = t * t, t * t * t
    return 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2
                  + (-p0 + 3 * p1 - 3 * p2 + p3) * t3)


def _interp_at(rows, u):
    """Catmull-Rom point of a list of float tuples at parameter u in 0..len-1."""
    n = len(rows)
    i = min(int(u), n - 2)
    t = u - i
    p0, p1, p2, p3 = (rows[max(i - 1, 0)], rows[i], rows[i + 1], rows[min(i + 2, n - 1)])
    return tuple(_catmull(a, b, c, d, t) for a, b, c, d in zip(p0, p1, p2, p3))


def _interp(rows, sub):
    """Catmull-Rom resample of a list of float tuples (sub points per gap)."""
    out = [_interp_at(rows, i + k / sub) for i in range(len(rows) - 1) for k in range(sub)]
    out.append(rows[-1])
    return out


def _spow(v, e):
    return math.copysign(abs(v) ** e, v)


def _ring(st, s, n=RING_N, scale=1.0, shift=None):
    """Folded superellipse ring of station st at sleeve parameter s."""
    oc, orow, ic, irow, sc, ry = st
    po, pi = W(oc, orow), W(ic, irow)
    mid = (po + pi) / 2 + Y * px(sc - CX) + (shift if shift is not None else Vector())
    a = (po - pi) / 2 * scale
    b = px(ry) * scale
    sag = SAG * _smooth(0.3, 0.75, s)
    pts = []
    for k in range(n):
        th = 2 * math.pi * k / n
        m = _fold(th, s)
        # the hanging (inner, lower) half carries more depth than the upper half
        bb = b * (1.0 - sag * math.cos(th))
        pts.append(mid + (a * _spow(math.cos(th), SUPER) + Y * (bb * _spow(math.sin(th), SUPER))) * m)
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


def _flat_mid(st):
    """Centre of a flat station (oc, orow, ic, irow, side col, half-depth)."""
    oc, orow, ic, irow, sc, _ = st
    return (W(oc, orow) + W(ic, irow)) / 2 + Y * px(sc - CX)


def _station_mid(st):
    (oc, orow), (ic, irow), sc, ry = st
    return _flat_mid((oc, orow, ic, irow, sc, ry))


FLAT = [(o[0], o[1], i[0], i[1], sc, ry) for o, i, sc, ry in STATIONS]
_FINE = 400                   # samples of the station spline for the arc-length tables


def _profile_table():
    """[(u, centre, cumulative profile length, cumulative centre-line length)]
    along the station spline. The profile length adds the change of mean
    radius to the centre's travel, so a ring sequence even in it is even along
    the cloth's meridian too."""
    last = len(FLAT) - 1
    out, acc, clen, prev = [], 0.0, 0.0, None
    for i in range(_FINE + 1):
        u = last * i / _FINE
        st = _interp_at(FLAT, u)
        c = _flat_mid(st)
        oc, orow, ic, irow, _, ry = st
        r = ((W(oc, orow) - W(ic, irow)).length / 2 + px(ry)) / 2
        if prev is not None:
            step = (c - prev[0]).length
            acc += math.hypot(step, r - prev[1])
            clen += step
        out.append((u, c, acc, clen))
        prev = (c, r)
    return out


_PROFILE = _profile_table()
# centre-line segments for sleeve_params: start points, directions, squared
# lengths, and the arc length (normalised 0..1) at each sample
_SEG_A = np.array([tuple(p[1]) for p in _PROFILE[:-1]])
_SEG_D = np.array([tuple(p[1]) for p in _PROFILE[1:]]) - _SEG_A
_SEG_LL = np.maximum((_SEG_D * _SEG_D).sum(1), 1e-14)
_SEG_S = np.array([p[3] for p in _PROFILE]) / _PROFILE[-1][3]


def _ring_params(n=RING_COUNT):
    """Station parameters u of n rings evenly spaced along the sleeve profile."""
    total = _PROFILE[-1][2]
    us, j = [], 0
    for k in range(n):
        target = total * k / (n - 1)
        while j < len(_PROFILE) - 2 and _PROFILE[j + 1][2] < target:
            j += 1
        (u0, _, a0, _), (u1, _, a1, _) = _PROFILE[j], _PROFILE[j + 1]
        us.append(u0 + (u1 - u0) * (0.0 if a1 <= a0 else max(0.0, min(1.0, (target - a0) / (a1 - a0)))))
    return us


def sleeve_param(p):
    """Pure function for the rig: position of world point p along the sleeve,
    0 at the band (drawstring) .. 1 at the wrist gather, by the nearest point
    of the sleeve's centre line (arc length along it). Works for either arm
    (|x| is used). Points above the band give 0 and points past the cuff 1.
    The rig can split the drape weights by this instead of by ring positions
    or bone envelopes. The balloon's own vertices carry the exact value of
    their ring in the point attribute SLEEVE_PARAM_ATTR."""
    return float(sleeve_params(np.array([tuple(p)], dtype=float))[0])


def sleeve_params(co):
    """sleeve_param for an (n, 3) array of world points (vectorised)."""
    co = np.asarray(co, dtype=float).reshape(-1, 3)
    q = np.concatenate([np.abs(co[:, :1]), co[:, 1:]], axis=1)
    out = np.empty(len(q))
    for s in range(0, len(q), 256):            # chunks keep the (n, segments, 3) temporaries ~2 MB
        qq = q[s:s + 256, None, :]
        t = np.clip(((qq - _SEG_A) * _SEG_D).sum(2) / _SEG_LL, 0.0, 1.0)
        dist = ((_SEG_A + _SEG_D * t[:, :, None] - qq) ** 2).sum(2)
        i = dist.argmin(1)
        ti = t[np.arange(len(i)), i]
        out[s:s + 256] = _SEG_S[i] + ti * (_SEG_S[i + 1] - _SEG_S[i])
    return out


SLEEVE_PARAM_ATTR = 'levi_sleeve_s'   # point attribute: place along the sleeve, 0 band .. 1 wrist


def _write_sleeve_param(obj):
    """Fill SLEEVE_PARAM_ATTR by projection, unless the mesh already carries it
    exactly (the balloon writes its rings' values while it is built)."""
    me = obj.data
    if me.attributes.get(SLEEVE_PARAM_ATTR) is not None:
        return
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    mw = np.array(obj.matrix_world)
    co = co @ mw[:3, :3].T + mw[:3, 3]
    attr = me.attributes.get(SLEEVE_PARAM_ATTR) or me.attributes.new(SLEEVE_PARAM_ATTR, 'FLOAT', 'POINT')
    attr.data.foreach_set('value', sleeve_params(co).astype(np.float32))


def _balloon_bm():
    flat = FLAT
    last = len(flat) - 1
    us = _ring_params()
    rings = [_ring(_interp_at(flat, u), u / last) for u in us]
    # exact place of each ring along the centre line, for SLEEVE_PARAM_ATTR
    # (a nearest-point projection could jump between the upper and lower run
    # of the bent centre line for cloth far out on the inside of the bend)
    sp = [float(np.interp(u, [p[0] for p in _PROFILE], _SEG_S)) for u in us]
    st0, st1 = flat[0], flat[-1]

    # Top: the cloth tucks up under the drawstring band.
    up = (_station_mid(STATIONS[1]) - _flat_mid(st0)).normalized()
    rings.insert(0, _ring(st0, 0.0, scale=0.86, shift=up * px(3)))
    # Wrist: the hem turns inward over a short interior return (a thin lip,
    # then a facing running back up inside), so the opening has depth. Both
    # step straight back up the cuff axis, so the return stays centred.
    _, cuff_ax = _frame(STATIONS[-1][0], STATIONS[-1][1])
    # (The lip ring keeps ~2 px edges to the hem: shorter edges tear under skinning.)
    rings.append(_ring(st1, 1.0, scale=0.95, shift=-cuff_ax * px(3.0)))
    rings.append(_ring(st1, 1.0, scale=0.89, shift=-cuff_ax * px(8.5)))
    sp = [0.0] + sp + [1.0, 1.0]
    bm = _loft_out(rings)
    layer = bm.verts.layers.float.new(SLEEVE_PARAM_ATTR)
    n = len(rings[0])
    bm.verts.index_update()
    for v in bm.verts:              # common.loft creates the vertices ring by ring
        v[layer] = sp[v.index // n]
    return bm


# ---------------------------------------------------------------- band, frills
DOWN_ARM = Vector((0.6, 0.0, -0.8))   # rough forearm direction, for orienting frames

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
TIE = BAND_MID - BAND_AX * px(1)        # drawstring centre (frill waist, bow knot)


def _perp_xz(f):
    """Unit vector in world XZ perpendicular to f, pointing to +X (outward)."""
    e = Vector((-f.z, 0.0, f.x)).normalized()
    return -e if e.x < 0 else e


def _lobe(th, k, phase, irr=0.0, pinch=1.6):
    """Lobe profile (about -1.4..1.4) with broad rounded crests and narrower
    valleys (cloth scallops: the fullness rolls over, the gathers pinch; pinch
    1 gives an even sine wave), the lobes made up to 22% uneven so the ring
    does not read as a cut star.
    irr (0..1) also warps the angle so the lobes differ in width and adds a
    second, unrelated height variation: hand-gathered cloth, not a stamped
    crown. The warp is periodic and monotonic, so the ring stays closed and
    its vertices keep their order."""
    tw = th + irr * (0.09 * math.sin(2 * th + 1.1) + 0.05 * math.sin(3 * th + 2.3))
    u = (1.0 - math.cos(k * tw + phase)) / 2.0          # 0 on a crest, 1 in a valley
    g = 1.0 - 2.0 * u ** pinch
    return g * (1.0 + 0.22 * math.cos(3 * th + 0.8 + phase) + irr * 0.16 * math.cos(5 * th + 0.4))


def _frill_ring(c, e, ra, rb, n, k=0, amp=0.0, lift_dir=None, lift=0.0, phase=0.0, irr=0.0,
                pinch=1.6):
    """Ellipse (e, b) of radii ra, rb around c; k rounded lobes push the ring
    out radially by amp and along lift_dir by lift at their crests (and pull
    it in / down in the valleys between them). b is world Y made
    perpendicular to e and lift_dir (= Y when lift_dir lies in XZ)."""
    b = Y.copy()
    if lift_dir is not None:
        b = b - lift_dir * b.dot(lift_dir)
    b = (b - e * b.dot(e)).normalized()
    pts = []
    for j in range(n):
        th = 2 * math.pi * j / n
        g = _lobe(th, k, phase, irr, pinch) if k else 0.0
        w = 1.0 + amp * g
        p = c + e * (ra * w * math.cos(th)) + b * (rb * w * math.sin(th))
        if lift_dir is not None and lift:
            p = p + lift_dir * (lift * g)
        pts.append(p)
    return pts


# Top frill. The sheet's heading is a low, softly scalloped frill rising out
# of the drawstring and turning outward at the rim; its middle lobes reach
# front row ~245 and the side lobes splay out lower (side cols 257..332).
# Above the tie only a few px of gathered cloth, then the frill flares open
# like a soft cup (no straight, collar-like wall), its fluting growing from
# the pinched gathers into broad, uneven waves at the rim -- each wave rises
# where the cloth bunches and dips between, lit on top and shaded where it
# turns down. The rim rolls under in a short return so the edge has a
# thickness and an outline, but the sheet itself stays a single thin layer.
TIE_R = 22.0                  # px, drawstring radius (covers the balloon's ~19 px top ring)
# Axis at the rim: tilted toward the body, flatter than the band (the sheet's
# side lobes slope down toward the body).
RIM_NORMAL = Vector((-0.2, 0.0, 0.98)).normalized()
RUFFLE_SHIFT = Vector((px(3.0), 0.0, 0.0))   # rim centre offset (front: ~col 418)
# (height along the axis px, radius front px, radius side px, lobe amp, lobe lift px)
RUFFLE_PROFILE = (
    (0.0, TIE_R, TIE_R, 0.04, 0.0),       # cinched by the drawstring
    (4.0, 22.4, 22.4, 0.05, 0.2),         # gathered just above it
    (9.0, 23.8, 24.2, 0.07, 0.6),         # the frill opens ...
    (14.0, 25.8, 26.4, 0.07, 0.9),
    (18.0, 28.0, 28.8, 0.07, 1.1),        # ... flares ...
    (21.6, 30.4, 31.4, 0.07, 1.5),
    (24.2, 32.8, 33.8, 0.07, 1.7),        # ... and opens outward at the rim
    (25.9, 34.6, 35.6, 0.07, 1.8),        # the rim rolls over ...
    (26.4, 35.9, 36.9, 0.07, 1.8),        # ... in a rounded fold ~2.5 px across ...
    (25.9, 36.9, 37.9, 0.07, 1.8),
    (24.8, 37.3, 38.3, 0.07, 1.8),
    (23.6, 37.3, 38.3, 0.07, 1.8),        # ... and ends ~3 px under it
)
RUFFLE_N = 72
RUFFLE_LOBES = 9              # 8 ring vertices per wave: soft rounded fluting
RUFFLE_PINCH = 1.0            # even sine waves: no pinched valleys between pointed petals
RUFFLE_IRR = 0.5              # somewhat uneven wave widths and heights (see _lobe)


def _ruffle_bm():
    k, n = RUFFLE_LOBES, RUFFLE_N
    # tucked into the balloon's gathered top
    rings = [_frill_ring(BAND_MID + BAND_AX * px(6), BAND_E, px(TIE_R - 1), px(TIE_R - 1), n)]
    top = max(range(len(RUFFLE_PROFILE)), key=lambda i: RUFFLE_PROFILE[i][0])
    for i, (h, ra, rb, amp, lift) in enumerate(RUFFLE_PROFILE):
        # the frame turns from the band axis to the rim normal smoothly with
        # height (no sharp kink between rings); the rolled hem shares the rim's frame
        s = 1.0 if i >= top else _smooth(0.0, 1.0, h / RUFFLE_PROFILE[top][0])
        f = (-BAND_AX).lerp(RIM_NORMAL, s).normalized()
        c = TIE + f * px(h) + RUFFLE_SHIFT * s
        rings.append(_frill_ring(c, _perp_xz(f), px(ra), px(rb), n, k, amp, f, px(lift), 0.3,
                                 RUFFLE_IRR, RUFFLE_PINCH))
    return _loft_out(rings)


# Cuff: one white ruffle attached inside the gathered hem, spilling out
# toward the hand and drooping a little (so the side view sees a bell, as
# drawn, rather than looking straight into the opening). It is a closed
# fold of cloth -- outer face, rolled rim, inner face back up to the
# attachment -- so the edge has thickness and an outline without a
# solidified plate edge.
CUFF_N = 64
CUFF_LOBES = 8                # 8 ring vertices per lobe: soft, rounded scallops
CUFF_IRR = 0.3                # a little unevenness between the scallops (see _lobe)
CUFF_PINCH = 1.2              # nearly even waves: no creased valleys to break the shading
# A mild droop only: a strongly one-sided ruffle swings round with the
# forearm twist and folds into the hem.
CUFF_DROOP = 0.6              # downward tilt added to the arm axis at the rim
CUFF_FORWARD = 0.35           # forward (-Y) tilt: the front view sees into the shaded underside
CUFF_ROOT = -4.0              # px along the arm: attachment, inside the turned-in hem
#   (s along the ruffle 0..1, radius front px, radius side px, lobe amp, lobe lift px)
CUFF_PROFILE = (
    (0.00, 23.0, 21.0, 0.02, 0.0),        # sewn inside the hem facing
    (0.35, 25.6, 24.0, 0.04, 0.15),
    (0.70, 28.6, 28.6, 0.06, 0.25),       # the flare rounds over ...
    (0.92, 31.2, 31.6, 0.07, 0.3),
    (1.00, 32.4, 33.0, 0.07, 0.3),        # ... to the free edge
    (0.97, 31.5, 32.0, 0.07, 0.3),        # rolled rim: a rounded lip ~0.5 px thick ...
    (0.88, 30.0, 30.4, 0.07, 0.3),
    (0.70, 27.9, 27.9, 0.06, 0.25),       # ... and the inner face back up, inside the outer
    (0.45, 24.9, 23.6, 0.04, 0.15),       # one at every s (same centre and frame there)
    (0.05, 22.3, 20.3, 0.02, 0.0),
)
CUFF_LEN = 27.0               # px, attachment -> rim


def _cuff_bm():
    e, axis = _frame(STATIONS[-1][0], STATIONS[-1][1])
    c0 = CUFF_MID + axis * px(CUFF_ROOT)
    droop = (axis + Vector((0.0, -CUFF_FORWARD, -CUFF_DROOP))).normalized()
    rings = []
    for s, ra, rb, amp, lift in CUFF_PROFILE:
        f = axis.lerp(droop, s).normalized()
        c = c0 + (axis.lerp(droop, 0.5).normalized()) * px(CUFF_LEN * s)
        rings.append(_frill_ring(c, _perp_xz(f), px(ra), px(rb), CUFF_N, CUFF_LOBES,
                                 amp * s ** 0.7, f, px(lift), math.pi / CUFF_LOBES, CUFF_IRR,
                                 CUFF_PINCH))
    return _loft_out(rings)


# ---------------------------------------------------------------- bow + ribbons
# The sheet draws the bow face-on in every view (front knot ~(430, 277), side
# ~col 294), so it sits on the front-outer diagonal of the band where both
# the front and the side views see it. It is flat ribbon: two folded loops
# (pinched at the knot, opening into broad wings, each a front and a back
# layer joined by a rounded fold at the tip) lying along the band and
# drooping down the sleeve, a wrapped knot over their roots, and two tails.
RIB_W = 3.8                   # px, ribbon width (tails)
RIB_T = 0.8                   # px, ribbon thickness
BOW_ANG = math.radians(55.0)  # around the band from front (-Y) toward the outer side
BOW_DROP = 3.0                # px down the arm from the drawstring: the bow sits below the frill rim
# (horizontal direction (x, y) for the +side loop, length px, wing width px at
# the fold, droop deg, loop height px). The sheet draws the loops spread wide
# in both the front and the side view, so they point between X and Y.
LOOPS = (((0.75, 0.66), 29.0, 10.0, 22.0, 8.5), ((0.75, 0.66), 27.0, 9.5, 32.0, 8.0))
LOOP_TILT = math.radians(30.0)   # wing width turned out of the cloth: the openings show
LOOP_ROOT_W = 3.6             # px, ribbon width where the loop is pinched by the knot
LOOP_M = 16                   # samples around a loop
FRONT_TAILS = [
    [(437, 313), (453, 340), (457, 373), (442, 400), (432, 440)],
    [(429, 315), (427, 345), (428, 372), (417, 398), (413, 424)],
]
# The back view shows the same pair of tails (mirrored), hanging behind.
BACK_TAILS = [
    [(436, 312), (451, 335), (455, 372), (441, 401), (431, 441)],
    [(428, 316), (427, 347), (414, 373), (417, 400), (417, 426)],
]
TAIL_SUB = 4                  # Catmull-Rom points per tail polyline gap (smooth bends when skinned)


def _polyline(pts, sub=2):
    rows = [tuple(p) for p in pts]
    return [Vector(p) for p in _interp(rows, sub)]


def _strip(pts, wdirs, widths, thick, closed=False):
    """Flat ribbon (4-vertex rectangular section) along pts. The width runs
    along wdirs (made perpendicular to the path), the thickness across it.
    Open strips are capped."""
    n = len(pts)
    bm = bmesh.new()
    rings = []
    for i in range(n):
        if closed:
            t = pts[(i + 1) % n] - pts[(i - 1) % n]
        else:
            t = pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]
        t.normalize()
        w = wdirs[i] - t * wdirs[i].dot(t)
        w.normalize()
        nrm = t.cross(w)
        hw, ht = px(widths[i]) / 2, px(thick) / 2
        p = pts[i]
        rings.append([bm.verts.new(p + w * hw + nrm * ht), bm.verts.new(p - w * hw + nrm * ht),
                      bm.verts.new(p - w * hw - nrm * ht), bm.verts.new(p + w * hw - nrm * ht)])
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
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def _band_dirs(phi):
    """(radial, tangent) unit vectors around the band at angle phi from the front."""
    r = BAND_E * math.sin(phi) - Y * math.cos(phi)
    t = BAND_E * math.cos(phi) + Y * math.sin(phi)
    return r, t


def _surface_r(bvh, r, z, floor):
    """Radius of the sleeve surface around the band axis along radial r, z down the arm."""
    o = TIE + BAND_AX * z
    hit = bvh.ray_cast(o + r * px(2), r, px(60))
    rad = (hit[0] - o).dot(r) if hit[0] is not None else floor
    return max(rad, floor)


def _band_coords(p):
    """(z down the arm, unit radial vector, radius) of p around the band axis."""
    d = p - TIE
    z = d.dot(BAND_AX)
    q = d - BAND_AX * z
    rad = q.length
    return z, q / rad, rad


def _barrel(c, axis, u, ru, rv, length, n=8):
    """Small capped barrel (the wrapped knot): axis direction, section radii
    ru along u and rv across it."""
    v = axis.cross(u).normalized()
    rings = []
    for a, s in ((-0.5, 0.8), (0.0, 1.0), (0.5, 0.8)):
        cc = c + axis * (length * a)
        rings.append([cc + u * (ru * s * math.cos(2 * math.pi * j / n))
                      + v * (rv * s * math.sin(2 * math.pi * j / n)) for j in range(n)])
    bm = common.loft(rings, closed=True, cap_start=True, cap_end=True)
    return bm


def _bow(bvh):
    """Knot + two folded loops on the front-outer band; returns (knot point, [bm])."""
    gap = px(1.2)
    floor = px(TIE_R + 0.5)
    r0, t0 = _band_dirs(BOW_ANG)
    z0 = px(BOW_DROP)
    knot_r = _surface_r(bvh, r0, z0, floor) + gap + px(2.6)
    knot = TIE + BAND_AX * z0 + r0 * knot_r
    out = [_barrel(knot, t0, BAND_AX, px(LOOP_ROOT_W / 2 + 1.6), px(3.1), px(5.5))]
    down = Vector((0.0, 0.0, -1.0))
    for side, (hdir, length, wing, droop_deg, height) in zip((-1, 1), LOOPS):
        dr = math.radians(droop_deg)
        u = (Vector((side * hdir[0], side * hdir[1], 0.0)).normalized() * math.cos(dr)
             + down * math.sin(dr)).normalized()
        pts, wd, ws = [], [], []
        for j in range(LOOP_M):
            tau = 2 * math.pi * j / LOOP_M
            a = (1 - math.cos(tau)) / 2               # 0 at the knot, 1 at the fold
            z, rr, rad = _band_coords(knot + u * (px(length) * a))
            # the loop is a straight stiff wing, laid onto the cloth where it would cut in
            base = max(rad - px(2.6), _surface_r(bvh, rr, z, floor) + gap)
            # front layer (sin > 0) and back layer meet at the knot and the fold;
            # the loop stands off most at its middle
            lift = px(height) * (0.5 + 0.5 * math.sin(tau)) * math.sin(math.pi * min(a * 1.25, 1.0)) ** 0.6
            pts.append(TIE + BAND_AX * z + rr * (base + lift))
            # width across the path, lying on the cloth (tilted out a little)
            wd.append(u.cross(rr) * math.cos(LOOP_TILT) + rr * math.sin(LOOP_TILT))
            # teardrop wing: pinched at the knot, fullest before the fold, rounded at it
            spread = math.sin(math.pi / 2 * min(a / 0.7, 1.0)) * (1.0 - 0.15 * _smooth(0.7, 1.0, a))
            ws.append(LOOP_ROOT_W + (wing - LOOP_ROOT_W) * spread)
        out.append(_strip(pts, wd, ws, RIB_T, closed=True))
    return knot, out


def _stand(s):
    """Tail clearance off the cloth at s (0 knot .. 1 end): closest at the ends."""
    return px(1.6 + 1.6 * math.sin(math.pi * s) ** 2)


SLEEVE_AXIS = (BAND_MID, CUFF_MID)


def _outward(loc, nh):
    """nh flipped, if needed, to point away from the sleeve axis at loc (the
    turned-in hem facings have inward-facing normals)."""
    a, b = SLEEVE_AXIS
    d = b - a
    t = max(0.0, min(1.0, (loc - a).dot(d) / d.length_squared))
    return -nh if nh.dot(loc - (a + d * t)) < 0 else nh


def _tails(knot, bvh, front=True):
    """Flat ribbon tails hanging from the knot over the balloon, tapering and
    turning a little as they fall, standing a little off the cloth mid-way."""
    out = []
    sign = -1.0 if front else 1.0
    kc, kr = spec.panel_px('front', knot)
    for ti, path in enumerate(FRONT_TAILS if front else BACK_TAILS):
        pts2 = _polyline([(kc, kr)] + path, TAIL_SUB)
        m = len(pts2)
        pts, nrms = [knot], [None]
        y_prev, n_prev = knot.y, Vector((0.0, sign, 0.0))
        for j, p2 in enumerate(pts2[1:], 1):
            s = j / (m - 1)
            o = W(p2.x, p2.y)
            o.y = sign * 1.0
            hit, nh, _, _ = bvh.ray_cast(o, Y * (-sign), 2.0)
            stand = _stand(s)
            if hit is not None:
                if nh.y * sign < 0:
                    nh = -nh
                p = hit + nh * stand
                y_prev, n_prev = p.y, nh
            else:
                # past the sleeve's edge: wrap onto the nearest cloth instead of
                # hanging free (a free end would swing off the sleeve when the arm moves)
                loc, nh, _, _ = bvh.find_nearest(Vector((o.x, y_prev, o.z)))
                if loc is None:
                    loc, nh = Vector((o.x, y_prev, o.z)), n_prev
                else:
                    nh = _outward(loc, nh)
                p = loc + nh * stand
                y_prev, n_prev = p.y, nh
            if sign * (p.y - knot.y) < 0:      # never tuck behind the knot
                p.y = knot.y
            pts.append(p)
            nrms.append(nh)
        nrms[0] = nrms[1]
        # relax kinks left by the projection, then keep the strip off the cloth
        for _ in range(2):
            pts = [pts[0]] + [(pts[j - 1] + pts[j] * 2 + pts[j + 1]) / 4 for j in range(1, m - 1)] + [pts[-1]]
        for j in range(1, m):
            s = j / (m - 1)
            loc, nh, _, _ = bvh.find_nearest(pts[j])
            if loc is not None:
                nh = _outward(loc, nh)
                if nh.dot(pts[j] - loc) < 0 or (pts[j] - loc).length < px(1.4):
                    pts[j] = loc + nh * _stand(s)
                nrms[j] = nh
            if sign * (pts[j].y - knot.y) < 0:      # still never behind the knot
                pts[j].y = knot.y
        wd, ws = [], []
        for j, p in enumerate(pts):
            t = pts[min(j + 1, m - 1)] - pts[max(j - 1, 0)]
            w = nrms[j].cross(t).normalized()
            # gentle twist so the face turns toward and away from the light
            s = j / (m - 1)
            ang = 0.45 * math.sin(2 * math.pi * 1.1 * s + 1.7 * ti) * _smooth(0.0, 0.25, s)
            nf = t.normalized().cross(w)
            wd.append(w * math.cos(ang) + nf * math.sin(ang))
            ws.append(RIB_W * (1.0 - 0.3 * s))
        out.append(_strip(pts, wd, ws, RIB_T))
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
    # Plain palette materials: the frill renders exactly sleeve_dark, the
    # cuff exactly cuff.
    ruffle_mat = common.toon_material('sleeve_dark')
    cuff = common.toon_material('cuff')

    balloon = _balloon_bm()
    balloon.normal_update()
    bvh = BVHTree.FromBMesh(balloon)

    knot, bow = _bow(bvh)
    back = BAND_E * math.sin(BOW_ANG) + Y * math.cos(BOW_ANG)
    zb = px(BOW_DROP)           # level with the front knot, below the frill
    knot_b = TIE + BAND_AX * zb + back * max(px(TIE_R + 2.5), _surface_r(bvh, back, zb, 0.0) + px(2.2))
    _, tb = _band_dirs(math.pi - BOW_ANG)
    ribbon = (bow + _tails(knot, bvh, front=True)
              + [_barrel(knot_b, tb, BAND_AX, px(2.6), px(2.2), px(4.0))]
              + _tails(knot_b, bvh, front=False))

    objs = [_finish(col, 'sleeve_balloon', balloon, sleeve_mat, grad=_grad),
            _finish(col, 'sleeve_ruffle', _ruffle_bm(), ruffle_mat),
            _finish(col, 'sleeve_cuff', _cuff_bm(), cuff),
            _finish(col, 'sleeve_ribbon', _join(ribbon), green, outline=spec.OUTLINE_WIDTH * 0.5)]
    # The white cuff ruffle doesn't cast: its scalloped rim printed small
    # hard shadow specks onto the bag and the hand that the sheet never paints.
    objs[2]['levi_cast_shadow'] = False
    for o in objs:
        # for the rig (round 5: drape weights by position along the sleeve):
        # each vertex's place along the sleeve, 0 band .. 1 wrist, independent
        # of how the rings are spaced
        _write_sleeve_param(o)
        o['levi_sleeve_param'] = SLEEVE_PARAM_ATTR
