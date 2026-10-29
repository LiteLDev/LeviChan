"""Detached bishop sleeves, modelled as hanging cloth: a fabric tube gathered
under a soft drawstring band whose fabric flares into a tall, fluted
dark-green paper-bag frill, tied with a ribbon bow (two triangular loops of
narrow ribbon, a closed wrapped knot, long thin tails); below the band the
sleeve opens into a bell with a few broad longitudinal folds (light green
under the band fading to pale mint), and is gathered again at the wrist,
where its hem turns inward and a two-tier white ruffle with round flutes
spills out toward the hand.

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

# Folds. The radius is modulated by: fine pleats where the drawstring gathers
# the cloth; a soft five-fold swell falling from the band; a few stable,
# unevenly spaced valleys that run down the bell, drifting a little around
# the arm and deepening toward the wrist; and (round 9) the wrist gather's
# pleats, which fan up the lower bell as lengthwise folds, growing deeper and
# tighter as the fullness is compressed into the cuff. Every fold is a broad
# rounded trough, several ring vertices and several rings wide, so the cloth
# can compress along the arm (a raised arm lets the bag fall back) without
# the folds creasing.
GATHER_K_TOP = 8              # pleats under the drawstring (6 ring vertices each)
GATHER_TOP = 0.16
# Wrist pleats (round 9; round 8: 8 pleats of 0.05 over the last quarter only).
GATHER_K = 8                  # pleats at the wrist gather (6 ring vertices each: rounded, no slivers)
GATHER_CUFF = 0.15            # their depth at the cuff (fraction of the radius; round 8: 0.05)
GATHER_RISE = (0.6, 0.97)     # s over which they grow from nothing (below the elbow) to full depth
GATHER_RISE_POW = 1.6         # > 1: shallow far up, deepening fast into the gather
GATHER_PINCH = 1.35           # > 1: narrow valleys between broad, rounded crests (cloth, not a sine)
GATHER_IRR = 0.30             # uneven pleat widths and depths (hand-gathered, not stamped)
GATHER_TWIST = 0.10           # rad the pleats wander round the arm up the bell (they fan, not stripes)
# 0: the pleats swing about the fitted girth; 1: their valleys stay on it and only the
# crests stand out.
GATHER_BIAS = 0.5
# Share of the folds the turned-in lip and facing take: a lip crinkled as deep as the
# hem's pleats caught the light in bright flecks at the wrist opening.
HEM_FOLD = 0.4
SWELL_AMP = 0.07              # depth of the swell under the band (fraction of the radius)
# (ring angle rad: 0 = outer edge, pi/2 = back, -pi/2 = front; relative depth)
VALLEYS = ((-1.20, 0.9), (-0.55, 0.7), (0.70, 1.0), (2.35, 0.7), (-2.50, 0.8))
VALLEY_W = 0.40               # angular half-width (rad): ~6 ring vertices, a rounded trough
VALLEY_AMP = (0.08, 0.22)     # depth at the top of the bell / near the wrist (round 8: 0.07, 0.12)
VALLEY_DRIFT = 0.25           # rad of sideways wander along the sleeve
VALLEY_RAMP = (0.55, 0.95)    # s over which they deepen (round 8: 0.3, 0.85): the elbow keeps round 8's depth
VALLEY_INFLATE = 0.4          # share of their depth the ring is inflated by (round 8: 0.25)
VALLEY_HANDOVER = 0.55        # share of the valleys' depth handed to the wrist pleats in the gather
# Shading (round 9): the cel ramp sees FOLD_SHADE of each fold's own normal,
# blended with the normal of the same cloth with the folds FOLD_SOFT as deep,
# so the deeper folds still turn the terminator into long soft tongues
# instead of chipping it into specks (as petticoat.FOLD_SHADE).
FOLD_SHADE = 0.0
FOLD_SOFT = 0.45


def _fold(th, s, k=1.0, env=False):
    """Radial factor at ring angle th and sleeve parameter s (0 band .. 1 wrist);
    k scales the valleys' and the wrist pleats' depth (the soft shading surface;
    the drawstring pleats and the swell keep theirs, as in round 8). env: the envelope over
    the valleys' and the wrist pleats' crests instead (what a ribbon lying on the
    cloth bridges, see _tails).

    Valleys pull in and the ring is inflated by a share of their depth, so the
    ridges between them stand slightly proud of the fitted stations and the
    mean radius stays close to them; the wrist pleats likewise swing about the
    fitted girth."""
    fine = GATHER_TOP * (1.0 - _smooth(0.0, 0.3, s))
    v_fine = (1.0 - math.cos(GATHER_K_TOP * th + 0.4)) / 2.0
    swell = SWELL_AMP * _smooth(0.06, 0.25, s) * (1.0 - _smooth(0.3, 0.6, s))
    v_swell = (1.0 - math.cos(5 * th + 0.3)) / 2.0
    # valleys fade in below the band and hand over to the wrist pleats at the gather
    depth = ((VALLEY_AMP[0] + (VALLEY_AMP[1] - VALLEY_AMP[0]) * _smooth(*VALLEY_RAMP, s))
             * _smooth(0.08, 0.25, s) * (1.0 - VALLEY_HANDOVER * _smooth(0.88, 1.0, s)))
    v_val = 0.0
    for i, (phi, w) in enumerate(VALLEYS):
        c = phi + VALLEY_DRIFT * math.sin(math.pi * s + 1.3 * i)
        dth = (th - c + math.pi) % (2 * math.pi) - math.pi
        v_val += w * math.exp(-(dth / VALLEY_W) ** 2)
    cuff = GATHER_CUFF * _smooth(*GATHER_RISE, s) ** GATHER_RISE_POW
    pleat = (0.0 if env else _wrist_pleat(th, s)) - _PLEAT_MEAN - GATHER_BIAS * (_PLEAT_MAX - _PLEAT_MEAN)
    if env:
        v_val = 0.0
    return (1.0 - fine * v_fine - swell * v_swell + 0.4 * swell
            - k * depth * (v_val - VALLEY_INFLATE) - k * cuff * pleat)


def _wrist_pleat(th, s):
    """Wrist pleat profile (0 on a crest .. ~1 in a valley) at ring angle th: a
    periodic, monotonic warp of the angle gives uneven widths and lets the
    pleats wander round the arm up the bell."""
    tw = (th + GATHER_IRR * (0.09 * math.sin(2 * th + 1.1) + 0.05 * math.sin(3 * th + 2.3))
          + GATHER_TWIST * math.sin(math.pi * s + 0.6))
    v = ((1.0 - math.cos(GATHER_K * tw + 0.9)) / 2.0) ** GATHER_PINCH
    return v * (1.0 + GATHER_IRR * 0.6 * math.cos(3 * th + 0.8))


# mean of the pleat profile round the ring: the pleats swing about the fitted girth
_PLEAT = [_wrist_pleat(2 * math.pi * j / 720, 1.0) for j in range(720)]
_PLEAT_MEAN, _PLEAT_MAX = sum(_PLEAT) / len(_PLEAT), max(_PLEAT)


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


def _ring_dirs(st, s, n=RING_N, scale=1.0, shift=None):
    """(centre, [unfolded radial offset per ring vertex]) of station st at s."""
    oc, orow, ic, irow, sc, ry = st
    po, pi = W(oc, orow), W(ic, irow)
    mid = (po + pi) / 2 + Y * px(sc - CX) + (shift if shift is not None else Vector())
    a = (po - pi) / 2 * scale
    b = px(ry) * scale
    sag = SAG * _smooth(0.3, 0.75, s)
    offs = []
    for j in range(n):
        th = 2 * math.pi * j / n
        # the hanging (inner, lower) half carries more depth than the upper half
        bb = b * (1.0 - sag * math.cos(th))
        offs.append(a * _spow(math.cos(th), SUPER) + Y * (bb * _spow(math.sin(th), SUPER)))
    return mid, offs


def _ring(st, s, n=RING_N, scale=1.0, shift=None, k=1.0, env=False, q=None):
    """Folded superellipse ring of station st at sleeve parameter s (folds k as
    deep; env: their crests' envelope, see _fold); q: per-vertex radius factor
    of the shape master (round 10, see _target_q), applied under the folds."""
    mid, offs = _ring_dirs(st, s, n, scale, shift)
    return [mid + o * (_fold(2 * math.pi * j / n, s, k, env) * (1.0 if q is None else float(q[j])))
            for j, o in enumerate(offs)]


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


# ---------------------------------------------------------------- shape master (round 10)
# The bag takes its girth from the shape master: per ring and per ring vertex
# the outermost `sleeves` surface along the vertex's radial direction (in the
# ring's own plane, from the station centre) gives a factor q = target radius /
# procedural radius. Where the target is hidden (hair behind the arm, the body
# or skirt in front of the inner side) or flares into a thin flap (the pointed
# hem wings that curl up past the wrist), the factor falls back to 1 by a
# validity weight; it is clamped, smoothed round the ring and along the sleeve,
# and faded in below the band (TARGET_BAND), so the drawstring keeps its
# procedural pleats and the bow sits as before, and handed back to the
# procedural hem toward the wrist (TARGET_HEM), where the cuff is sewn in. The
# folds are still procedural on top of it (clean quad lanes, the rig's drape
# weights, the soft shading). The station spline, which levi_sleeve_s measures
# along, stays the bag's centre line: the factors change the girth round it.
TARGET_RMAX = 2.0             # rays start this many procedural radii out
TARGET_RNEAR = 1.4            # ... or this many, looking through other cloth
TARGET_OPAQUE = ('hair_back', 'hair_front')
TARGET_NEAR_MAX = 1.02        # ... where the cloth may only come in
TARGET_INNER_MIN = 0.97       # the inner side is taken in no further (see _target_q)
TARGET_CLAMP = (0.75, 1.30)   # factor limits: a flap or a stray patch is a bulge at most
TARGET_SMOOTH = (12, 3)       # [1 2 1] passes round the ring / along the sleeve
TARGET_BAND = (0.03, 0.16)    # s over which the target takes over from the band
TARGET_HEM = (0.75, 1.0)      # s over which it hands back to the procedural hem ...
TARGET_HEM_OUT = 0.85         # ... fully where the target is narrower, this share where wider
TARGET_FLAP = 0.05            # samples this far past the upper clamp are the hem wing: dropped, not clipped


def _circ_smooth(a, passes, axis=-1):
    for _ in range(passes):
        a = 0.25 * np.roll(a, 1, axis) + 0.5 * a + 0.25 * np.roll(a, -1, axis)
    return a


def _line_smooth(a, passes):
    for _ in range(passes):
        b = a.copy()
        b[1:-1] = 0.25 * a[:-2] + 0.5 * a[1:-1] + 0.25 * a[2:]
        a = b
    return a


def _weighted_smooth(q, ok, circ, line=0, axis=-1):
    """Radius factors q smoothed round the ring (circ passes along axis) and
    along the sleeve (line passes along axis 0), each sample weighted by its
    validity ok (bool, or a 0..1 share): missing samples count as procedural (1)
    and the result is renormalised by the smoothed validity, so a lone valid
    sample doesn't spread thin; where samples are few it fades back to 1."""
    w = np.asarray(ok, dtype=float)
    qw = 1.0 + (np.where(w > 0.0, q, 1.0) - 1.0) * w
    qw = _line_smooth(_circ_smooth(qw, circ, axis), line)
    w = _line_smooth(_circ_smooth(w, circ, axis), line)
    return 1.0 + (qw - 1.0) / np.maximum(w, 1e-3) * np.clip(w * 2.0, 0.0, 1.0)


def _cast_in(cen, dirs, r0, occluders=True):
    """Radius of the outermost `sleeves` surface along each direction, cast
    inward from cen + dir * r0 (per ray; NaN past the centre or where another
    part is outermost), and who is outermost."""
    from .. import shape
    _, d, _, who = shape.ray('sleeves', cen + dirs * r0[:, None], -dirs, max_d=float(r0.max()),
                             occluders=occluders)
    r = r0 - d
    return np.where(r > 0.0, r, np.nan), who


_TQ = {}                      # cached shape-master factors (one build reloads the module)


def _target_q():
    """(us, q): the ring parameters u and the shape master's radius factor per
    ring and ring vertex (RING_COUNT x RING_N), validity-weighted and smoothed."""
    if 'q' in _TQ:
        return _TQ['us'], _TQ['q']
    us = _ring_params()
    last = len(FLAT) - 1
    raw = np.full((len(us), RING_N), np.nan)
    for i, u in enumerate(us):
        s = u / last
        mid, offs = _ring_dirs(_interp_at(FLAT, u), s)
        rp = np.array([o.length for o in offs])
        dirs = np.array([tuple(o / o.length) for o in offs])
        cen = np.repeat(np.array([tuple(mid)]), RING_N, 0)
        # rays from TARGET_RMAX procedural radii out, each along its own vertex direction
        r, who = _cast_in(cen, dirs, rp * TARGET_RMAX)
        raw[i] = r / rp
        # Where other cloth or the body lies outside the bag (the inner side, next to
        # the skirt and the bodice) look through it, from closer in; not through the
        # hair, which hides a fused, missing sleeve surface.
        miss = ~np.isfinite(raw[i]) & np.array([w not in TARGET_OPAQUE for w in who])
        if miss.any():
            r, _ = _cast_in(cen[miss], dirs[miss], rp[miss] * TARGET_RNEAR, occluders=False)
            # trusted only to take cloth in: there the skirt's labels stray onto
            # the sleeve and the target's bag is fused with the skirt it touches
            f = r / rp[miss]
            raw[i, miss] = np.where(f <= TARGET_NEAR_MAX, f, np.nan)
    ok = np.isfinite(raw) & (raw > TARGET_CLAMP[0] - 0.15) & (raw < TARGET_CLAMP[1] + TARGET_FLAP)
    q = _weighted_smooth(np.clip(np.nan_to_num(raw, nan=1.0), *TARGET_CLAMP), ok, *TARGET_SMOOTH)
    fade = np.array([_smooth(*TARGET_BAND, u / last) for u in us])[:, None]
    # The inner side (toward the body, the inside of a bent elbow) is taken in at
    # most to TARGET_INNER_MIN: there the cloth folds against the arm when the elbow
    # bends, and a bag taken in closer compressed past the rig's limits
    # (hands_behind_head, idol_dance).
    inner = np.array([_smooth(0.0, 0.7, -math.cos(2 * math.pi * j / RING_N)) for j in range(RING_N)])
    floor = TARGET_CLAMP[0] + (TARGET_INNER_MIN - TARGET_CLAMP[0]) * inner
    q = 1.0 + (np.clip(q, floor[None, :], TARGET_CLAMP[1]) - 1.0) * fade
    # Into the wrist gather the bag keeps its procedural girth on the inside, where the
    # cuff ruffle is sewn in behind the turned-in facing (a narrower hem would let
    # the ruffle's root through), and most of it outside (the target's flare there
    # is the hem wing curling away, not the gathered hem).
    hem = np.array([_smooth(*TARGET_HEM, u / last) for u in us])[:, None]
    q = np.where(q < 1.0, 1.0 + (q - 1.0) * (1.0 - hem), 1.0 + (q - 1.0) * (1.0 - TARGET_HEM_OUT * hem))
    _TQ['us'], _TQ['q'] = us, q
    return us, q


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


def _balloon_rings(k=1.0, env=False):
    """(rings, sleeve parameter per ring) of the bag, its folds k as deep (env:
    their crests' envelope)."""
    flat = FLAT
    last = len(flat) - 1
    us, tq = _target_q()
    rings = [_ring(_interp_at(flat, u), u / last, k=k, env=env, q=q) for u, q in zip(us, tq)]
    # exact place of each ring along the centre line, for SLEEVE_PARAM_ATTR
    # (a nearest-point projection could jump between the upper and lower run
    # of the bent centre line for cloth far out on the inside of the bend)
    sp = [float(np.interp(u, [p[0] for p in _PROFILE], _SEG_S)) for u in us]
    st0, st1 = flat[0], flat[-1]

    # Top: the cloth tucks up under the drawstring band.
    up = (_station_mid(STATIONS[1]) - _flat_mid(st0)).normalized()
    rings.insert(0, _ring(st0, 0.0, scale=0.86, shift=up * px(3), k=k, env=env))
    # Wrist: the hem turns inward over a short interior return (a thin lip,
    # then a facing running back up inside), so the opening has depth. Both
    # step straight back up the cuff axis, so the return stays centred.
    _, cuff_ax = _frame(STATIONS[-1][0], STATIONS[-1][1])
    # (The lip ring keeps ~2 px edges to the hem: shorter edges tear under skinning.)
    qh = tq[-1]                     # the lip and facing follow the hem ring
    rings.append(_ring(st1, 1.0, scale=0.95, shift=-cuff_ax * px(3.0), k=k * HEM_FOLD, env=env, q=qh))
    rings.append(_ring(st1, 1.0, scale=0.89, shift=-cuff_ax * px(8.5), k=k * HEM_FOLD, env=env, q=qh))
    return rings, [0.0] + sp + [1.0, 1.0]


def _balloon_bm():
    rings, sp = _balloon_rings()
    bm = _loft_out(rings)
    layer = bm.verts.layers.float.new(SLEEVE_PARAM_ATTR)
    n = len(rings[0])
    bm.verts.index_update()
    for v in bm.verts:              # common.loft creates the vertices ring by ring
        v[layer] = sp[v.index // n]
    return bm


def _soft_normals(bm_soft, obj, keep, own_from=None):
    """Custom normals of a mirrored object built from one side's BMesh: each
    corner takes its vertex's own normal blended (keep) with the vertex normal
    of bm_soft, the same lattice with shallower folds (mirrored for the right
    side). Vertices from index own_from on (of one side: the bag's hem, lip
    and facing, where the cloth turns inward over a sharp edge) keep their own
    split corner normals: a blended normal there smeared the crease into
    bright flecks at the wrist opening."""
    bm_soft.normal_update()
    base = [v.normal.copy() for v in bm_soft.verts]
    bm_soft.free()
    me = obj.data
    n = len(base)
    assert len(me.vertices) == 2 * n, (obj.name, len(me.vertices), n)
    a, b = me.vertices[0].co, me.vertices[n].co
    assert (Vector((-a.x, a.y, a.z)) - b).length < 1e-6, (obj.name, 'mirror order')
    vn = []
    for i, v in enumerate(me.vertices):
        b = base[i % n]
        if i >= n:                  # the Mirror modifier appends the mirrored copy in order
            b = Vector((-b.x, b.y, b.z))
        own = Vector(v.normal)
        if b.dot(own) < 0.0:        # never blend against a flipped normal
            b = -b
        nv = own * keep + b * (1.0 - keep)
        vn.append(nv.normalized() if nv.length > 1e-9 else own)
    corner = [Vector(c.vector) if own_from is not None and lp.vertex_index % n >= own_from
              else vn[lp.vertex_index] for lp, c in zip(me.loops, me.corner_normals)]
    me.normals_split_custom_set(corner)


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


def _warp(th, irr):
    """The lobes' irregular angle (see _lobe): periodic and monotonic."""
    return th + irr * (0.09 * math.sin(2 * th + 1.1) + 0.05 * math.sin(3 * th + 2.3))


def _lobe(th, k, phase, irr=0.0, pinch=1.6, var=0.22):
    """Lobe profile (about -1.4..1.4) with broad rounded crests and narrower
    valleys (cloth scallops: the fullness rolls over, the gathers pinch; pinch
    1 gives an even sine wave), the lobes made up to var (22%) uneven so the
    ring does not read as a cut star.
    irr (0..1) also warps the angle so the lobes differ in width and adds a
    second, unrelated height variation: hand-gathered cloth, not a stamped
    crown. The warp is periodic and monotonic, so the ring stays closed and
    its vertices keep their order."""
    tw = _warp(th, irr)
    u = (1.0 - math.cos(k * tw + phase)) / 2.0          # 0 on a crest, 1 in a valley
    g = 1.0 - 2.0 * u ** pinch
    return g * (1.0 + var * math.cos(3 * th + 0.8 + phase) + irr * 0.16 * math.cos(5 * th + 0.4))


def _frill_ring(c, e, ra, rb, n, k=0, amp=0.0, lift_dir=None, lift=0.0, phase=0.0, irr=0.0,
                pinch=1.6, curl=0.0, girth=None, ripple=None, rnd=0.0, ths=None, var=0.22, amp_w=None):
    """Ellipse (e, b) of radii ra, rb around c; k rounded lobes push the ring
    out radially by amp and along lift_dir by lift at their crests (and pull
    it in / down in the valleys between them); curl pushes the crests alone
    further out (a lobe's edge turning outward). b is world Y made
    perpendicular to e and lift_dir (= Y when lift_dir lies in XZ). girth: a
    radius factor per ring vertex (the shape master's, see _frill_q); the lift
    along lift_dir keeps its height.

    ripple (k2, amp2, lift2 m, phase2): a secondary, finer wave on top of the
    lobes (small folds within each flute). rnd (0..0.9, round 11): the flutes
    are rounded flutes, not a sine star. Each vertex slides round the ring by
    rnd / (2k) sin(2 psi) of the lobe phase psi, so the crests and the valleys
    are stretched (broad, round turns) and the flanks between them crowded (steep),
    as gathered cloth folds into U-shaped flutes; a plain sine as deep as the
    flutes turned both into points, which read end-on as a cut star.
    ths: the vertices' ring parameters (default even, 2 pi j / n; see
    _even_params, which spaces them evenly along the deepest ring instead, so
    the round crests get as many vertices as the flanks). amp_w: a factor per
    vertex on the lobes' depth, rise and curl (and the ripple)."""
    b = Y.copy()
    if lift_dir is not None:
        b = b - lift_dir * b.dot(lift_dir)
    b = (b - e * b.dot(e)).normalized()
    pts = []
    for j in range(n):
        th = 2 * math.pi * j / n if ths is None else ths[j]
        g = _lobe(th, k, phase, irr, pinch, var) if k else 0.0
        if amp_w is not None:
            g *= float(amp_w[j])
        g2 = 0.0
        if ripple and k:
            k2, a2, l2, ph2 = ripple
            g2 = math.cos(k2 * _warp(th, irr) + ph2) * (1.0 if amp_w is None else float(amp_w[j]))
        w = ((1.0 + amp * g + curl * max(g, 0.0) ** 2 + (ripple[1] * g2 if g2 else 0.0))
             * (1.0 if girth is None else float(girth[j])))
        tp = th + (rnd / (2 * k)) * math.sin(2 * (k * _warp(th, irr) + phase)) if k and rnd else th
        p = c + e * (ra * w * math.cos(tp)) + b * (rb * w * math.sin(tp))
        if lift_dir is not None and (lift or g2):
            p = p + lift_dir * (lift * g + (ripple[2] * g2 if g2 else 0.0))
        pts.append(p)
    return pts


def _even_params(n, k, amp, phase, irr, pinch, curl=0.0, rnd=0.0, ripple=None, var=0.22):
    """Ring parameters (n angles) that space the vertices evenly along a ring
    with these lobes (unit circle; see _frill_ring), so a deep, rounded flute's
    crest and valley get as many vertices as its flanks (with even parameters
    the rounding stretched them over 2-3 vertices: polygonal points in the
    outline). A whole loft uses the deepest ring's parameters on every ring, so
    its vertices stay in step from ring to ring."""
    m = 24 * n
    ring = _frill_ring(Vector(), Vector((1.0, 0.0, 0.0)), 1.0, 1.0, m, k, amp, None, 0.0, phase, irr,
                       pinch, curl, ripple=None if ripple is None else (ripple[0], ripple[1], 0.0, ripple[3]),
                       rnd=rnd, var=var)
    ring.append(ring[0])
    arc = np.concatenate([[0.0], np.cumsum([(b - a).length for a, b in zip(ring, ring[1:])])])
    u = np.linspace(0.0, 2 * math.pi, m + 1)
    return [float(v) for v in np.interp(np.arange(n) * arc[-1] / n, arc, u)]


def _frill_q(name, plain, use, clamp, passes):
    """Shape-master girth factor per ring vertex angle of a frill (cached by name):
    the outermost `sleeves` radius about each ring centre of the plain frill
    (plain() -> rings, centres; no lobes, no girth) over its own, for the rings
    `use` (slice), averaged over them, validity-weighted, smoothed round the ring
    (passes) and clamped. One profile for every ring, so a rolled rim's two
    faces scale alike."""
    if name in _TQ:
        return _TQ[name]
    rings, centres = plain()[:2]
    f = []
    for ring, c in list(zip(rings, centres))[use]:
        P = np.array([tuple(p) for p in ring])
        C = np.array(tuple(c))
        r = np.linalg.norm(P - C, axis=1)
        dirs = (P - C) / r[:, None]
        rt, _ = _cast_in(np.repeat(C[None], len(P), 0), dirs, r * TARGET_RMAX)
        f.append(rt / r)
    f = np.array(f)
    ok = np.isfinite(f) & (f > clamp[0] - 0.15) & (f < clamp[1] + 0.25)
    mean = np.where(ok, np.clip(np.nan_to_num(f, nan=1.0), *clamp), 0.0).sum(0) / np.maximum(ok.sum(0), 1)
    _TQ[name] = np.clip(_weighted_smooth(mean, ok.mean(0), passes), *clamp)
    return _TQ[name]


def _girth(q, w, floor=0.0):
    """Per-vertex girth factor 1 + w (q - 1) of a frill ring, at least floor (<= 1)."""
    return np.maximum(1.0 + w * (q - 1.0), floor)


# Top frill: the paper-bag heading. The sheet draws a tall frill rising out of
# the drawstring like a tulip, narrow at the tie and flaring wide at the rim,
# where a few deep flutes stand up as broad points (front view: its top at row
# ~245, ~32 px above the knot; side view ~75 px across the flutes).
# Above the tie a few px of gathered cloth, then the frill flares open (no
# straight, collar-like wall), its fluting growing from the pinched gathers
# into deep, rounded flutes at the rim (RUFFLE_ROUND), each rising where the
# cloth bunches and dipping between, with a finer secondary ripple inside
# each flute (RUFFLE_RIPPLE). The rim rolls under in a short return so the edge
# has a thickness and an outline, but the sheet itself stays a single layer.
# Round 11 (clothes-detail review: "a low cup from the front"): rim 26.4 -> 31 px
# above the tie, flutes 0.07 -> 0.165 deep with 1.8 -> 3.4 px of rise, 72 -> 120 ring points.
TIE_R = 22.0                  # px, drawstring radius (covers the balloon's ~19 px top ring)
# Axis at the rim: tilted toward the body, flatter than the band (the sheet's
# side lobes slope down toward the body).
RIM_NORMAL = Vector((-0.2, 0.0, 0.98)).normalized()
RUFFLE_SHIFT = Vector((px(3.0), 0.0, 0.0))   # rim centre offset (front: ~col 418)
# The frame turns from the band axis (34 deg) to RIM_NORMAL (11.5 deg) up the frill, which
# lays the outer side's wall over (and stands the inner side's up): with the taller, deeper
# flutes the outer ones flared out flat as ears. The outer side's radius is taken in by up
# to RUFFLE_TAPER toward the rim (fading round to none on the inner side), so its wall
# rises at ~50-65 deg like the rest. On the inner side, against the chest and the armpit,
# the flutes lie flatter (RUFFLE_INNER_FLAT of their depth less), as cloth pressed against
# the body does: full-depth flutes there reached 7.8 mm into the skin at rest.
# (height along the axis px, radius front px, radius side px, lobe amp, lobe lift px)
RUFFLE_PROFILE = (
    (0.0, TIE_R, TIE_R, 0.03, 0.0),       # cinched by the drawstring
    (4.0, 22.4, 22.4, 0.05, 0.2),         # gathered just above it
    (8.5, 23.2, 23.6, 0.08, 0.6),         # the frill opens ...
    (13.0, 24.8, 25.4, 0.10, 1.05),
    (17.5, 27.0, 27.8, 0.12, 1.6),        # ... flares like a paper bag ...
    (21.5, 29.4, 30.4, 0.135, 2.15),
    (25.0, 31.6, 32.8, 0.15, 2.65),
    (28.0, 33.4, 34.8, 0.16, 3.05),       # ... and opens outward at the rim
    (30.2, 34.8, 36.3, 0.165, 3.3),       # the rim rolls over ...
    (31.0, 36.0, 37.5, 0.165, 3.4),       # ... in a rounded fold ~2.5 px across ...
    (30.5, 37.0, 38.5, 0.165, 3.4),
    (29.4, 37.4, 38.9, 0.165, 3.4),
    (28.2, 37.3, 38.8, 0.165, 3.4),       # ... and ends ~3 px under it
)
RUFFLE_N = 120
RUFFLE_TAPER = 0.18
RUFFLE_INNER_FLAT = 0.6
RUFFLE_LOBES = 9              # ~13 ring vertices per flute
RUFFLE_PINCH = 1.35           # broad, rounded flute tops and narrower dips (the sheet's side view)
RUFFLE_IRR = 0.35             # somewhat uneven flute widths and heights (see _lobe)
# ... and depths: round 10's 22% (_lobe's default) gave the deeper, taller flutes one
# horn-like flute on the outer side
RUFFLE_VAR = 0.1
RUFFLE_ROUND = 0.6            # rounded flutes (see _frill_ring), by the lobes' share of their rim depth
RUFFLE_CURL = 0.035           # the flutes' crests turn outward toward the rim (from RUFFLE_CURL_FROM px)
RUFFLE_CURL_FROM = 18.0
# secondary ripple: lobes, depth and rise (px) at the rim, by the lobes' share of their rim depth
RUFFLE_RIPPLE = (22, 0.022, 0.8)
# shading (round 11, as the bag's FOLD_SHADE / FOLD_SOFT): the cel ramp sees RUFFLE_SHADE of
# the flutes' own normal, the rest from the frill with its flutes RUFFLE_SOFT as deep, so the
# deeper flutes shade as broad tongues instead of chipping the terminator into specks
RUFFLE_SHADE = 0.0
RUFFLE_SOFT = 0.45
# Shape master (round 10): the frill's girth round the band follows the target
# (sampled over the opening and the rim, rings 4..), as a radius factor on the rings
# from RUFFLE_TARGET_H px above the drawstring, which stays cinched (never inside it).
RUFFLE_TARGET = (slice(4, None), (0.82, 1.08), 16)   # rings sampled, clamp, smoothing passes
RUFFLE_TARGET_H = (4.0, 14.0)


def _ruffle_rings(k=RUFFLE_LOBES, q=None, taper=True, depth=1.0):
    """(rings, centres) of the heading frill with k lobes; q: the shape master's
    girth factor per ring vertex (see _frill_q), taken in from RUFFLE_TARGET_H px
    above the drawstring and never inside it; taper: the outer side taken in
    (RUFFLE_TAPER; off for the shape master's sampling, so its girth doesn't undo it).
    depth scales the flutes (the soft shading surface, see RUFFLE_SHADE)."""
    n = RUFFLE_N
    top = max(range(len(RUFFLE_PROFILE)), key=lambda i: RUFFLE_PROFILE[i][0])
    amp_rim = max(p[3] for p in RUFFLE_PROFILE)
    k2, a2, l2 = RUFFLE_RIPPLE
    # the vertices spaced evenly along the rim's flutes (see _even_params), on every ring
    ths = _even_params(n, RUFFLE_LOBES, amp_rim, 0.3, RUFFLE_IRR, RUFFLE_PINCH, RUFFLE_CURL,
                       RUFFLE_ROUND, (k2, a2, 0.0, 1.9), RUFFLE_VAR)
    # tucked into the balloon's gathered top
    rings = [_frill_ring(BAND_MID + BAND_AX * px(6), BAND_E, px(TIE_R - 1), px(TIE_R - 1), n, ths=ths)]
    centres = [BAND_MID + BAND_AX * px(6)]
    for i, (h, ra, rb, amp, lift) in enumerate(RUFFLE_PROFILE):
        # the frame turns from the band axis to the rim normal smoothly with
        # height (no sharp kink between rings); the rolled hem shares the rim's frame
        s = 1.0 if i >= top else _smooth(0.0, 1.0, h / RUFFLE_PROFILE[top][0])
        f = (-BAND_AX).lerp(RIM_NORMAL, s).normalized()
        c = TIE + f * px(h) + RUFFLE_SHIFT * s
        g = None if q is None else _girth(q, 1.0 if i >= top else _smooth(*RUFFLE_TARGET_H, h),
                                          min(1.0, (TIE_R + 0.5) / min(ra, rb)))
        if taper:
            tp = 1.0 - RUFFLE_TAPER * s * (1.0 + np.cos(np.array(ths))) / 2.0
            g = tp if g is None else g * tp
        aw = 1.0 - RUFFLE_INNER_FLAT * _smooth(0.0, 0.5, s) * ((1.0 - np.cos(np.array(ths))) / 2.0) ** 2
        # the rolled hem keeps the rim's curl and ripple, so the fold stays even round each flute
        hh = RUFFLE_PROFILE[top][0] if i >= top else h
        share = amp / amp_rim
        rings.append(_frill_ring(c, _perp_xz(f), px(ra), px(rb), n, k, depth * amp, f, px(depth * lift), 0.3,
                                 RUFFLE_IRR, RUFFLE_PINCH,
                                 curl=depth * RUFFLE_CURL * _smooth(RUFFLE_CURL_FROM, RUFFLE_PROFILE[top][0], hh),
                                 girth=g, ripple=(k2, depth * a2 * share, px(depth * l2 * share), 1.9),
                                 rnd=RUFFLE_ROUND * share, ths=ths, var=RUFFLE_VAR, amp_w=aw))
        centres.append(c)
    return rings, centres


def _ruffle_bm(depth=1.0):
    q = _frill_q('ruffle', lambda: _ruffle_rings(0, taper=False), *RUFFLE_TARGET)
    return _loft_out(_ruffle_rings(q=q, depth=depth)[0])


# Cuff: a two-tier white ruffle attached inside the gathered hem, spilling
# out toward the hand and drooping a little (so the side view sees a bell, as
# drawn, rather than looking straight into the opening). Each tier is a
# closed fold of cloth -- outer face, rolled rim, inner face back up to the
# attachment -- so the edge has thickness and an outline without a
# solidified plate edge.
# Round 11 (clothes-detail review: "a thin grey collar from the front, an
# 11-point star end-on"; the sheet draws a voluminous two-tier ruffle with
# round flutes): an upper tier (sleeve_cuff) and a longer under tier
# (sleeve_cuff_under) that shows ~9 px below it, both with 13 round flutes
# (CUFF_ROUND: U-shaped, not a sine star) deepening toward the free edge,
# where each crest turns outward and the rim rolls into a bead ~3 mm across.
# Both tiers share one centre line, frame and flute pattern, measured by the
# distance d (px) along it, so the under tier nests inside the upper one at
# every d (_cuff_clearance) and the two move alike when skinned.
CUFF_N = 128                  # ~10 ring vertices per flute
CUFF_LOBES = 13
CUFF_IRR = 0.3                # a little unevenness between the flutes (see _lobe)
CUFF_PINCH = 1.0              # even waves: no creased valleys to break the shading
CUFF_ROUND = 0.6              # round flutes (see _frill_ring), by the flutes' share of CUFF_AMP
# A mild droop only: a strongly one-sided ruffle swings round with the
# forearm twist and folds into the hem.
CUFF_DROOP = 0.75             # downward tilt added to the arm axis at the end of the centre line
CUFF_FORWARD = 0.4            # forward (-Y) tilt: the front view sees into the shaded underside
CUFF_ROOT = -4.0              # px along the arm: attachment, inside the turned-in hem
CUFF_PATH = 31.0              # px, length of the shared centre line (the under tier's rim)
# Flutes by d along the centre line, the same on the outer and the inner face
# of both tiers, so the rolled rims keep their thickness round every flute and
# the tiers nest: radial amplitude CUFF_AMP (d / CUFF_AMP_D)^0.7, lift (px
# along the ruffle) CUFF_LIFT (d / CUFF_AMP_D)^0.7, and the crests' outward turn
# CUFF_CURL over each tier's last CUFF_CURL_FROM share.
CUFF_AMP = 0.13               # round 9: 0.12 (11 lobes)
CUFF_AMP_D = 24.0
CUFF_LIFT = 1.6               # round 9: 1.2
CUFF_CURL = 0.05
CUFF_CURL_FROM = 0.45
# shading: CUFF_SHADE of the flutes' own normal, the rest from the ruffle with
# its flutes CUFF_SOFT as deep (see FOLD_SHADE): shaded flute flanks, not specks
CUFF_SHADE = 0.2
CUFF_SOFT = 0.0
# Shape master (round 10): the cuff keeps its procedural girth. The target's
# cuff is a scrunchie in a jumble of the hem wing; its girth, sampled like the
# heading frill's, only widened the flare by up to 6%, and that pushed the cuff
# 2-3 mm further into the body where the hands meet it (dance_point, hug_self:
# already majors), for no visible gain. The bag's hem it is sewn into follows
# the target only as far as TARGET_HEM allows.
# Tiers: (d along the centre line px, radius front px, radius side px), out along
# the outer face, round the rolled rim and back up the inner face.
CUFF_TIERS = {
    'upper': (
        (0.0, 21.8, 19.8),        # sewn inside the hem facing (clear of its pleat valleys)
        (7.5, 23.9, 22.4),
        (15.0, 28.6, 28.6),       # the flare rounds over ...
        (19.5, 31.4, 31.8),
        (21.6, 32.7, 33.1),       # ... to the free edge
        (22.0, 32.6, 33.0),       # rolled rim: a rounded bead ~2 px across ...
        (21.6, 31.4, 31.8),
        (20.2, 30.2, 30.5),
        (15.6, 27.6, 27.5),       # ... and the inner face back up, inside the outer
        (9.5, 23.6, 22.4),
        (1.0, 21.1, 19.1),
    ),
    'under': (
        (2.0, 19.9, 17.9),        # sewn just inside the upper tier's root
        (9.0, 21.4, 19.9),
        (15.0, 24.4, 23.8),       # nested inside the upper tier ...
        (20.0, 27.6, 27.6),
        (24.0, 29.8, 30.0),       # ... and out below its rim
        (28.0, 31.4, 31.8),
        (30.6, 32.2, 32.6),
        (31.0, 32.1, 32.5),       # rolled rim
        (30.6, 31.0, 31.4),
        (29.0, 30.2, 30.5),
        (24.0, 28.4, 28.5),       # the inner face back up
        (16.0, 23.4, 22.8),
        (8.0, 20.6, 19.0),
        (2.6, 19.3, 17.3),
    ),
}
CUFF_OUTLINE_MIN = 0.35       # outline width factor where the under tier lies under the upper one


def _cuff_frame():
    """(root, axis of the hem, droop direction, mid direction) of the cuff's centre line."""
    e, axis = _frame(STATIONS[-1][0], STATIONS[-1][1])
    c0 = CUFF_MID + axis * px(CUFF_ROOT)
    droop = (axis + Vector((0.0, -CUFF_FORWARD, -CUFF_DROOP))).normalized()
    return c0, axis, droop, axis.lerp(droop, 0.5).normalized()


def _cuff_rings(tier, k=1.0):
    """Rings of one tier of the cuff; k scales its flutes (the soft shading surface)."""
    c0, axis, droop, mid = _cuff_frame()
    prof = CUFF_TIERS[tier]
    dmax = max(p[0] for p in prof)
    # both tiers space their vertices alike, evenly along a full-depth flute ring (_even_params)
    ths = _even_params(CUFF_N, CUFF_LOBES, CUFF_AMP, math.pi / CUFF_LOBES, CUFF_IRR, CUFF_PINCH,
                       CUFF_CURL, CUFF_ROUND)
    rings = []
    for d, ra, rb in prof:
        t = d / CUFF_PATH
        f = axis.lerp(droop, t).normalized()
        c = c0 + mid * px(d)
        a = (min(d, 1.15 * CUFF_AMP_D) / CUFF_AMP_D) ** 0.7
        curl = CUFF_CURL * _smooth((1.0 - CUFF_CURL_FROM) * dmax, dmax, d)
        rings.append(_frill_ring(c, _perp_xz(f), px(ra), px(rb), CUFF_N, CUFF_LOBES,
                                 k * CUFF_AMP * a, f, px(k * CUFF_LIFT * a),
                                 math.pi / CUFF_LOBES, CUFF_IRR, CUFF_PINCH,
                                 k * curl, rnd=k * CUFF_ROUND * min(a, 1.0), ths=ths))
    return rings


def _cuff_bm(tier, k=1.0):
    return _loft_out(_cuff_rings(tier, k))


def _cuff_clearance():
    """Smallest gap (m) from the under tier's outer face out to the upper tier,
    along each under-tier ring's radial directions (the tiers share centres and
    flutes at every d, see CUFF_TIERS); negative where it pokes into the upper
    tier (the first surface hit faces away from the ray)."""
    rings = _cuff_rings('upper')
    verts, quads = _rings_poly(rings)
    bm = bmesh.new()
    vs = [bm.verts.new(v) for v in verts]
    for q in quads:
        bm.faces.new([vs[i] for i in q])
    _orient_outward(bm, [sum(r, Vector()) / len(r) for r in rings])
    bvh = BVHTree.FromBMesh(bm)
    bm.free()
    under = _cuff_rings('under')
    c0, _, _, mid = _cuff_frame()
    prof = CUFF_TIERS['under']
    top = max(range(len(prof)), key=lambda i: prof[i][0])
    rim = max(p[0] for p in CUFF_TIERS['upper'])
    gap = 1.0
    for i in range(top):                            # the outer face, up to the rim
        c = c0 + mid * px(prof[i][0])
        for p in under[i]:
            d = (p - c).normalized()
            loc, nrm, _, dist = bvh.ray_cast(p + d * 1e-6, d, px(30))
            if loc is not None:
                gap = min(gap, dist if nrm.dot(d) < 0 else -dist)
            elif prof[i][0] < rim - 2.0:            # outside the upper tier where it should be under it
                gap = min(gap, -px(1.0))
    return gap


def _rings_poly(rings):
    """(verts, quads) of a closed loft of rings, for a BVHTree."""
    n = len(rings[0])
    verts = [tuple(p) for r in rings for p in r]
    quads = [(a * n + j, a * n + (j + 1) % n, (a + 1) * n + (j + 1) % n, (a + 1) * n + j)
             for a in range(len(rings) - 1) for j in range(n)]
    return verts, quads


# ---------------------------------------------------------------- bow + ribbons
# The sheet draws the bow face-on in every view (front knot ~(430, 277), side
# ~col 294), so it sits on the front-outer diagonal of the band where both
# the front and the side views see it.
# Round 11 (clothes-detail review: "short flat slab loops seen edge-on, box
# corners and a hard-shaded block knot: from the front a green brick"): the
# sheet's bow is two triangular loops of narrow ribbon whose openings face the
# viewer, a small round knot and long thin tails. Each loop is a closed ribbon
# path traced in the bow's plane (x round the band from the knot, y down the
# arm), laid on the band (wrapping BOW_WRAP of its curvature, so it lies on
# the cloth instead of standing off it like a plate) and kept BOW_CLEAR off the
# cloth and the frill. Its face is turned BOW_TILT from the cloth's normal
# toward the loop's outside: a ring of ribbon, a thin outlined triangle from
# the front and the ribbon's face from 3/4. Sections are stadiums (rounded
# edges: no box corners). The knot is a closed, rounded wrap round the loops'
# roots (a capsule pinched where they enter: never an open end). The loops
# stay about round 10's size (29/27 x 10 px; round 9 rejected larger bow loops).
RIB_W = 2.7                   # px, tail width (the sheet's tails are thin cords; round 10: 3.8)
RIB_T = 0.75                  # px, ribbon thickness
BOW_ANG = math.radians(55.0)  # around the band from front (-Y) toward the outer side
BOW_DROP = 3.0                # px down the arm from the drawstring: the bow sits below the frill rim
BOW_W = 3.8                   # px, loop ribbon width
BOW_TILT = math.radians(55.0)
BOW_WRAP = 0.5
BOW_CLEAR = 0.9               # px between the ribbon's lowest edge and the cloth
LOOP_LIFT = (1.6, 0.4)        # px the loop stands further off: at the knot / at its far end
# Loops: the path's control points (x, y px from the knot; the knot itself
# closes the path): knot -> upper corner -> outer edge -> lower corner -> knot,
# and the droop (deg the loop is turned down the arm about the knot). The band
# rises toward the outer side (the arm hangs out and down), so round the band is
# not level: the outer loop droops 30 deg in the bow's plane to lie about level
# and the front one 8 deg to hang ~30 deg, as the sheet's front view draws them.
LOOPS = (
    ([(-6.6, -2.8), (-13.8, -5.0), (-19.1, -5.7), (-21.3, -4.7), (-22.0, -2.0), (-21.8, 2.7),
      (-20.7, 5.8), (-18.3, 6.4), (-13.9, 5.3), (-6.8, 3.0)], 8.0),
    ([(6.6, -2.6), (13.6, -4.7), (18.9, -5.3), (21.1, -4.3), (21.8, -1.6), (21.6, 2.9),
      (20.5, 6.0), (18.0, 6.6), (13.6, 5.5), (6.6, 3.2)], 30.0),
)
LOOP_M = 44                   # samples round a loop (~1.5 px apart)
LOOP_SIDES = 8                # ribbon section points (a stadium: flat faces, rounded edges)
KNOT_LEN = 5.4                # px, the wrap's length along the loops
KNOT_R = (1.8, 2.6)           # px, its half-thickness off the cloth / half-height along the arm
KNOT_N = 12                   # section points of the wrap
# The tails (front view px from the knot), as round 10; thin cords hanging over the bag.
FRONT_TAILS = [
    [(437, 313), (453, 340), (457, 373), (442, 400), (432, 440)],
    [(429, 315), (427, 345), (428, 372), (417, 398), (413, 424)],
]
# The back view shows the same pair of tails (mirrored), hanging behind.
BACK_TAILS = [
    [(436, 312), (451, 335), (455, 372), (441, 401), (431, 441)],
    [(428, 316), (427, 347), (414, 373), (417, 400), (417, 426)],
]
# Catmull-Rom points per tail polyline gap (as round 10): 7 (~4 px apart) let the thin tails
# follow the bag's local folds closely enough to fold over themselves (flipped faces 20-96 in
# arms_forward, hands_behind_head, idol_dance; round 10: 0-28)
TAIL_SUB = 4
TAIL_SIDES = 6
TAIL_TIP = (0.35, 0.07)       # the tail narrows to this share of its width over this share of its length


def _polyline(pts, sub=2):
    rows = [tuple(p) for p in pts]
    return [Vector(p) for p in _interp(rows, sub)]


def _section(hw, ht, sides):
    """Stadium cross-section, (offset along the width, along the thickness) in
    loop order: two flat faces joined by rounded edges with (sides - 4) / 2
    points on each edge's arc (sides 4: a flat rectangle)."""
    if sides == 4:
        return [(hw, ht), (hw, -ht), (-hw, -ht), (-hw, ht)]
    h = min(ht, 0.8 * hw)
    c = hw - h
    m = (sides - 4) // 2
    arc = [math.pi / 2 - math.pi * (k + 1) / (m + 1) for k in range(m)]
    out = [(c, h)] + [(c + h * math.cos(a), h * math.sin(a)) for a in arc] + [(c, -h), (-c, -h)]
    out += [(-c - h * math.cos(a), -h * math.sin(a)) for a in arc] + [(-c, h)]
    return out


SHADE_ATTR = 'levi_shade_n'    # build-time vertex attribute: the ribbon's shading normal (see _ribbon)


def _ribbon(pts, wdirs, widths, thick, closed=False, sides=8):
    """Ribbon along pts with a stadium section (see _section): the width (px,
    per point) runs along wdirs made perpendicular to the path, the thickness
    across it. An open ribbon is capped; a closed one joins its ends.
    Each vertex stores in SHADE_ATTR the normal of the broad face it belongs to
    (the rounded edges split between them), which _finish makes its shading
    normal: a narrow ribbon then shades lit or shaded across its whole width,
    as a flat ribbon does, instead of its rounded edges turning past the cel
    terminator as hairline slivers."""
    n = len(pts)
    bm = bmesh.new()
    lay = bm.verts.layers.float_vector.new(SHADE_ATTR)
    rings = []
    for i in range(n):
        if closed:
            t = pts[(i + 1) % n] - pts[(i - 1) % n]
        else:
            t = pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]
        t.normalize()
        w = wdirs[i] - t * wdirs[i].dot(t)
        w = w.normalized() if w.length > 1e-9 else t.orthogonal().normalized()
        nrm = t.cross(w)
        ring = []
        for a, c in _section(px(widths[i]) / 2, px(thick) / 2, sides):
            v = bm.verts.new(pts[i] + w * a + nrm * c)
            v[lay] = nrm if c > 1e-12 else -nrm if c < -1e-12 else (w if a > 0 else -w)
            ring.append(v)
        rings.append(ring)
    m = len(rings[0])
    pairs = list(zip(rings, rings[1:])) + ([(rings[-1], rings[0])] if closed else [])
    for ra, rb in pairs:
        for j in range(m):
            k = (j + 1) % m
            bm.faces.new((ra[j], ra[k], rb[k], rb[j]))
    if not closed:
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def _shade_from_attr(obj):
    """Corner normals of a mirrored object from SHADE_ATTR (see _ribbon), mirrored for
    the right half; vertices without one (zero: the knots) keep their own. The
    attribute is removed afterwards."""
    me = obj.data
    attr = me.attributes.get(SHADE_ATTR)
    if attr is None:
        return
    vec = [Vector(d.vector) for d in attr.data]
    n = len(vec) // 2
    a, b = me.vertices[0].co, me.vertices[n].co
    assert (Vector((-a.x, a.y, a.z)) - b).length < 1e-6, (obj.name, 'mirror order')
    corner = []
    for lp, c in zip(me.loops, me.corner_normals):
        v = vec[lp.vertex_index]
        if lp.vertex_index >= n:
            v = Vector((-v.x, v.y, v.z))
        corner.append(v.normalized() if v.length > 0.5 else Vector(c.vector))
    me.normals_split_custom_set(corner)
    me.attributes.remove(me.attributes[SHADE_ATTR])


def _band_dirs(phi):
    """(radial, tangent) unit vectors around the band at angle phi from the front."""
    r = BAND_E * math.sin(phi) - Y * math.cos(phi)
    t = BAND_E * math.cos(phi) + Y * math.sin(phi)
    return r, t


def _surface_r(bvh, r, z, floor):
    """Radius of the sleeve surface around the band axis along radial r, z down
    the arm: the outermost of the first surfaces each tree (bvh: one or a list)
    meets going out from the axis."""
    o = TIE + BAND_AX * z
    rad = floor
    for tree in (bvh if isinstance(bvh, (list, tuple)) else [bvh]):
        hit = tree.ray_cast(o + r * px(2), r, px(60))
        if hit[0] is not None:
            rad = max(rad, (hit[0] - o).dot(r))
    return rad


def _band_coords(p):
    """(z down the arm, unit radial vector, radius) of p around the band axis."""
    d = p - TIE
    z = d.dot(BAND_AX)
    q = d - BAND_AX * z
    rad = q.length
    return z, q / rad, rad


def _closed_spline(ctrl, m):
    """m points evenly spaced along the closed Catmull-Rom curve through ctrl (2-tuples)."""
    n = len(ctrl)
    dense = []
    for i in range(n):
        p0, p1, p2, p3 = (Vector(ctrl[(i + k) % n]) for k in (-1, 0, 1, 2))
        for s in range(24):
            dense.append(_catmull(p0, p1, p2, p3, s / 24))
    arc = [0.0]
    for a, b in zip(dense, dense[1:] + dense[:1]):
        arc.append(arc[-1] + (b - a).length)
    out, j = [], 0
    for k in range(m):
        target = arc[-1] * k / m
        while arc[j + 1] < target:
            j += 1
        f = (target - arc[j]) / max(arc[j + 1] - arc[j], 1e-12)
        out.append(dense[j].lerp(dense[(j + 1) % len(dense)], f))
    return out


def _capsule(c, axis, u, ru, rv, length, n=KNOT_N):
    """The wrapped knot: a closed, rounded wrap along axis (the loops' direction)
    with section radii ru along u and rv across it: a short barrel with a soft
    crease across its middle (the wrapping fold), rounded and pinched toward
    both ends where the loops' roots enter, and capped there (no open end)."""
    v = axis.cross(u).normalized()
    rings = []
    for a, s in ((-0.5, 0.5), (-0.45, 0.8), (-0.36, 0.95), (-0.2, 1.0), (0.0, 0.95),
                 (0.2, 1.0), (0.36, 0.95), (0.45, 0.8), (0.5, 0.5)):
        cc = c + axis * (length * a)
        rings.append([cc + u * (ru * s * math.cos(2 * math.pi * j / n))
                      + v * (rv * s * math.sin(2 * math.pi * j / n)) for j in range(n)])
    return common.loft(rings, closed=True, cap_start=True, cap_end=True)


def _bow(bvh):
    """Knot + two loops on the front-outer band; returns (knot point, [bm]).
    bvh: the surfaces the bow lies on (the bag's crest envelope, the frill)."""
    floor = px(TIE_R + 0.5)
    r0, t0 = _band_dirs(BOW_ANG)
    z0 = px(BOW_DROP)
    s0 = _surface_r(bvh, r0, z0, floor)
    rk = s0 + px(BOW_CLEAR + KNOT_R[0])
    knot = TIE + BAND_AX * z0 + r0 * rk
    out = [_capsule(knot, t0, r0, px(KNOT_R[0]), px(KNOT_R[1]), px(KNOT_LEN))]
    # the ribbon's lowest edge: its half width turned toward the cloth, and half its thickness
    need = px(BOW_CLEAR + 0.5 * BOW_W * math.sin(BOW_TILT) + 0.5 * RIB_T)
    for ctrl, droop in LOOPS:
        sg = -1.0 if ctrl[0][0] < 0 else 1.0
        th = sg * math.radians(droop)
        ct, st = math.cos(th), math.sin(th)
        pts2 = [Vector((x * ct - y * st, x * st + y * ct)) for x, y in [(0.0, 0.0)] + list(ctrl)]
        path = _closed_spline([tuple(p) for p in pts2], LOOP_M)
        reach = max(p.length for p in path)
        pts, dist = [], []
        for p2 in path:
            a = p2.length / reach                     # 0 at the knot .. 1 at the far end
            flat = knot + t0 * px(p2.x) + BAND_AX * px(p2.y)
            rr, _ = _band_dirs(BOW_ANG + px(p2.x) / rk)
            wrap = TIE + BAND_AX * (z0 + px(p2.y)) + rr * rk
            p = flat.lerp(wrap, BOW_WRAP)
            z, rd, rad = _band_coords(p)
            lift = px(LOOP_LIFT[0] + (LOOP_LIFT[1] - LOOP_LIFT[0]) * _smooth(0.0, 0.6, a))
            base = _surface_r(bvh, rd, z, floor) + need + lift
            # into the knot the loop runs through the wrap's centre
            rad_new = rad + (max(rad, base) - rad) * _smooth(0.08, 0.3, a)
            pts.append(TIE + BAND_AX * z + rd * rad_new)
            dist.append(p2.length)
        cen = sum(pts, Vector()) / len(pts)
        m = len(pts)
        wd, ws = [], []
        for j, p in enumerate(pts):
            t = (pts[(j + 1) % m] - pts[j - 1]).normalized()
            _, nrm, _ = _band_coords(p)
            o = p - cen
            o = (o - nrm * o.dot(nrm)).normalized()
            face = nrm * math.cos(BOW_TILT) + o * math.sin(BOW_TILT)
            wd.append(t.cross(face))
            # pinched into the knot, full width round the loop
            ws.append(BOW_W * (0.42 + 0.58 * _smooth(1.0, 7.0, dist[j])))
        out.append(_ribbon(pts, wd, ws, RIB_T, closed=True, sides=LOOP_SIDES))
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
    """Thin ribbon tails hanging from the knot over the balloon, tapering to a
    narrow tip and turning a little as they fall, standing a little off the cloth mid-way."""
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
        for _ in range(3):
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
        # the cloth's normal along the tail, smoothed so the twist doesn't jump between samples
        for _ in range(2):
            nrms = [nrms[0]] + [(nrms[j - 1] + nrms[j] * 2 + nrms[j + 1]).normalized()
                                for j in range(1, m - 1)] + [nrms[-1]]
        wd, ws = [], []
        for j, p in enumerate(pts):
            t = pts[min(j + 1, m - 1)] - pts[max(j - 1, 0)]
            w = nrms[j].cross(t).normalized()
            # gentle twist so the face turns toward and away from the light
            s = j / (m - 1)
            ang = 0.45 * math.sin(2 * math.pi * 1.1 * s + 1.7 * ti) * _smooth(0.0, 0.25, s)
            nf = t.normalized().cross(w)
            wd.append(w * math.cos(ang) + nf * math.sin(ang))
            tip = TAIL_TIP[0] + (1.0 - TAIL_TIP[0]) * _smooth(0.0, TAIL_TIP[1], 1.0 - s)
            ws.append(RIB_W * (1.0 - 0.2 * s) * tip)
        out.append(_ribbon(pts, wd, ws, RIB_T, sides=TAIL_SIDES))
    return out


# ---------------------------------------------------------------- build
OUTLINE_VG = 'outline_w'      # per-vertex outline width (see add_outline's min_factor)


def _finish(col, name, bm, mat, grad=None, outline=None, soft=None, line=None, smooth=50.0):
    """soft: (BMesh of the same lattice with shallower folds, own-normal share
    [, first vertex keeping its own normals]) for _soft_normals. line: (weight
    per vertex of one side, min_factor) for the outline width (OUTLINE_VG)."""
    obj = common.new_object(col, name, bm, [mat])
    common.shade_smooth(obj, smooth)
    if grad:
        common.set_gradient(obj, grad)
    common.mirror_x(obj, merge=False)
    common.apply_modifiers(obj)
    if soft is not None:
        _soft_normals(soft[0], obj, *soft[1:])
    _shade_from_attr(obj)
    if line is None:
        common.add_outline(obj, outline)
        return obj
    w, fmin = line
    n = len(w)
    assert len(obj.data.vertices) == 2 * n, (name, len(obj.data.vertices), n)
    vg = obj.vertex_groups.new(name=OUTLINE_VG)
    for i in range(2 * n):              # the Mirror modifier appends the mirrored copy in order
        vg.add([i], float(w[i % n]), 'REPLACE')
    common.add_outline(obj, outline, vertex_group=OUTLINE_VG, min_factor=fmin)
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


def _under_line():
    """Outline weight per vertex of the cuff's under tier: full where it shows
    below the upper tier, CUFF_OUTLINE_MIN of the width where it lies under it."""
    rim = max(p[0] for p in CUFF_TIERS['upper'])
    return [_smooth(rim - 6.0, rim, d) for d, _, _ in CUFF_TIERS['under'] for _ in range(CUFF_N)]


def build(col):
    sleeve_mat = common.toon_material('sleeve_dark', gradient='sleeve')
    green = common.toon_material('green')
    # Plain palette materials: the frill renders exactly sleeve_dark, the
    # cuff exactly cuff.
    ruffle_mat = common.toon_material('sleeve_dark')
    cuff = common.toon_material('cuff')

    balloon = _balloon_bm()
    # The bow and its tails lie on the envelope over the folds' crests: a ribbon
    # bridges the valleys instead of dipping into each one (round 9: laid into the
    # deeper valleys, the tails kinked and folded up in idol_dance).
    env = _loft_out(_balloon_rings(env=True)[0])
    env.normal_update()
    bvh = BVHTree.FromBMesh(env)
    env.free()
    ruffle = _ruffle_bm()
    ruffle.normal_update()
    bvh_ruffle = BVHTree.FromBMesh(ruffle)

    knot, bow = _bow([bvh, bvh_ruffle])
    back = BAND_E * math.sin(BOW_ANG) + Y * math.cos(BOW_ANG)
    zb = px(BOW_DROP)           # level with the front knot, below the frill
    kr = 0.85                   # the back knot is a little smaller
    knot_b = TIE + BAND_AX * zb + back * (_surface_r([bvh, bvh_ruffle], back, zb, px(TIE_R + 0.5))
                                          + px(BOW_CLEAR + kr * KNOT_R[0]))
    _, tb = _band_dirs(math.pi - BOW_ANG)
    ribbon = (bow + _tails(knot, bvh, front=True)
              + [_capsule(knot_b, tb, back, px(kr * KNOT_R[0]), px(kr * KNOT_R[1]), px(kr * KNOT_LEN))]
              + _tails(knot_b, bvh, front=False))

    gap = _cuff_clearance()
    print(f'SLEEVES cuff tiers: smallest gap under -> upper {gap / px(1.0):.2f} px')
    assert gap > px(0.5), ('sleeves: the cuff\'s under tier pokes into the upper one', gap)

    # the lip and the facing (the last 2 rings, after the top ring and the RING_COUNT
    # rings ending at the hem) keep their own normals; the hem ring itself shades with
    # the bag (own normals there too lit its pleat crests as bright flecks)
    hem = (RING_COUNT + 1) * RING_N
    soft = (_loft_out(_balloon_rings(FOLD_SOFT)[0]), FOLD_SHADE, hem) if FOLD_SHADE < 1.0 else None
    cuff_soft = (lambda t: (_cuff_bm(t, CUFF_SOFT), CUFF_SHADE)) if CUFF_SHADE < 1.0 else (lambda t: None)
    objs = [_finish(col, 'sleeve_balloon', balloon, sleeve_mat, grad=_grad, soft=soft),
            _finish(col, 'sleeve_ruffle', ruffle, ruffle_mat,
                    soft=(_ruffle_bm(RUFFLE_SOFT), RUFFLE_SHADE) if RUFFLE_SHADE < 1.0 else None),
            _finish(col, 'sleeve_cuff', _cuff_bm('upper'), cuff, soft=cuff_soft('upper')),
            _finish(col, 'sleeve_cuff_under', _cuff_bm('under'), cuff, soft=cuff_soft('under'),
                    line=(_under_line(), CUFF_OUTLINE_MIN)),
            _finish(col, 'sleeve_ribbon', _join(ribbon), green, outline=spec.OUTLINE_WIDTH * 0.5, smooth=75.0)]
    # The white cuff ruffle doesn't cast: its scalloped rim printed small
    # hard shadow specks onto the bag and the hand that the sheet never paints.
    # The ribbon is thin strips (render.NO_CAST_OBJECTS lists it too).
    for o in objs[2:]:
        o['levi_cast_shadow'] = False
    # for the rig (round 8): the ribbon's long loose strips are the bow's tails, lying on
    # the bag; they take its skin weights (rig._sleeve_ride_weights)
    objs[4]['levi_sleeve_tails'] = True
    host = max(objs, key=lambda o: len(o.data.vertices))
    assert host is objs[0], ('sleeves: sleeve_balloon must have the most vertices (rig._sleeve_host)',
                             [(o.name, len(o.data.vertices)) for o in objs])
    for o in objs:
        # for the rig (round 5: drape weights by position along the sleeve):
        # each vertex's place along the sleeve, 0 band .. 1 wrist, independent
        # of how the rings are spaced
        _write_sleeve_param(o)
        o['levi_sleeve_param'] = SLEEVE_PARAM_ATTR
