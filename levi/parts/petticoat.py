"""Petticoat: peach-pink gathered tiers below the skirt hem.

Objects:
  petticoat_core     inner cone from the hips down; hidden by the skirt.
  petticoat_tier0-1  gathered ruffle tiers, outermost first. The outer one
                     shows where the skirt is lifted; the inner one hangs
                     lowest, beside the legs, and shows below the outer one.

Each tier is one thin band of softly gathered fabric:
- Gathers: many small rounded folds (one per scallop, unevenly wide and
  deep), a cosine wave across each fold, so crests and valleys are both
  round, with no creases or tips. The folds are tight at the seam
  (SEAM_FOLD) and open up towards the hem. Depth and rise vary from fold to
  fold, blended over neighbouring folds (VAR_SMOOTH), so nothing steps.
  Neighbouring tiers' folds are offset by half a fold.
- Hem: one rounded scallop per fold. The notch sits over the fold's inner
  valley and is itself a round arch (rise ((1 + cos) / 2) ** NOTCH_P), so the
  scallops are broad round petals with soft notches, not points or fins.
- Real thickness at the hem: the cloth rolls under in a half circle
  (HEM_ROLL px radius, ROLL_DEG rings) and runs a little way back up inside
  (RET_UP), so undersides read as a thin turned hem, and the outline hull
  draws a line along every scallop.
- Profile: each tier is one surface, radius(azimuth, height), flaring out
  under the seam (inside the skirt) and hanging nearly straight lower down
  (1 - (1 - d) ** FLARE_POW of the full seam-to-hem drop d). Where the hem
  is tucked up under the skirt, the band ends higher on the same surface (it
  gets shorter, and its folds shallower: SHORT_POW) instead of being squashed
  into a flat shelf. Eight PROFILE rings (slightly closer towards the hem)
  let the skirt chains bend it smoothly.
- Shading: the folds' shading normals are blended towards the smooth band's
  (FOLD_SHADE), so fold flanks peeking out under the skirt do not break into
  small shade wedges; the geometry, silhouette and outline keep the folds.

Exposure: the sheet shows the ruffles mainly under the skirt's raised fold
troughs, and keeps them tucked up under the hanging lobes; in the side view
the leg shows under the skirt's sides. A tier's hem is raised (tuck()):
- in the back half, under the skirt's lobes, to just above the skirt's hem
  there (TUCK_PX), fading out towards the troughs (TUCK_SECTOR back weight);
- round each side, over the band of side-view columns where the sheet shows
  the leg (SIDE_BAND), behind the lowest skirt hem nearby (SIDE_WINDOW).
The front keeps its measured hem. The tucked hem is then smoothed along the
band, its slope limited (MAX_SLOPE) and smoothed again, so it rises in broad
curves rather than steps, flaps or fins. The skirt's hem rows and folds come from
levi/parts/skirt.py (fold_table / hem_terms / fold_index / profiles, pure
functions), so the tuck and the clearance follow the skirt.

Clearance: every ring is kept at least CLEAR px inside the skirt's inner
surface (the skirt's sheet rebuilt from skirt.profiles(), less its solidify
thickness) with a soft minimum. Below the skirt's edge the limit relaxes
gradually instead of switching off, and the inward pull is spread along each
ring (_clamp_ring), so the clamp leaves no sharp radial steps.

The pink band's bottom outline is a bowl, lowest at the centre and rising
towards the sides (and higher at the back than the front in the side view).
It was measured on ref/{front,side,back}.png (panel rows, HEM_FRONT /
HEM_SIDE) instead of using the single spec.L['petticoat_hem_z'] landmark,
which only gives one height.

Shadows: see CAST_TIERS (render.py reads obj['levi_cast_shadow']).

Rigging: the rig weights every skirt-family layer by angle x height to the
skirt chains, which follow the thighs (levi/rig.py). Every tier wraps round
both legs, well clear of them; none passes between the thighs.

Not modelled: the sheet's small shaded patch between the legs (front view,
~30 x 25 px under the skirt's centre front) and the pink sliver below the
back skirt's centre lobe. A layer hanging there would also hang in front of
the legs in the back view, where the sheet shows bare legs below the skirt,
and a layer between the thighs would need split leg weights.
"""
import bisect
import math

import bmesh
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

from levi import common, spec
from levi.parts import skirt

L = spec.L
PX = 1.0 / spec.PX_PER_M

# ---------------------------------------------------------------- measured
# Bottom outline of the pink band (panel row) vs horizontal offset from the
# panel centre (px). Front and back views agree to ~2 px, and are symmetric.
HEM_FRONT = [(0, 629), (80, 626), (140, 620), (165, 613), (190, 607), (205, 600),
             (215, 594), (225, 587), (232, 580), (240, 568)]
# Side view: negative = character's front (-Y), positive = back (+Y).
HEM_SIDE = [(-170, 590), (-163, 600), (-155, 610), (-140, 617), (-120, 620),
            (-100, 625), (-60, 629), (0, 630), (40, 628), (70, 627), (90, 622),
            (105, 620), (120, 613), (135, 607), (145, 604), (155, 595),
            (162, 585), (170, 572)]
# Outer extent of the ruffles (px from centre) at the hem.
HALF_W = 235      # front view, +-X
FRONT_D = 163     # side view, -Y
BACK_D = 165      # side view, +Y

# ---------------------------------------------------------------- shape
DENSE = 1440      # samples of the dense hem outline (arc-length resampling)
SPF = 8           # samples across one gather fold (notch at 0, crest at 0.5)
WIDTH_VAR = 0.3   # fold width irregularity (share of the mean width, +-)
DEPTH_VAR = 0.35  # fold depth / scallop rise irregularity
VAR_SMOOTH = 0.7  # per-fold depth / rise blended over this many folds (sigma)
NOTCH_P = 2.2     # scallop rise ((1 + cos) / 2) ** NOTCH_P: broad petal, round arch notch
SEAM_FOLD = 0.7   # share of the fold depth at the seam (gathered: the folds run up the band)
FOLD_POW = 0.5    # the folds open as d ** FOLD_POW down the band (visible all the way up)
# Where the hem is tucked up, the band is shorter and has less fabric to
# fold: the fold depth scales with (band length / full length) ** SHORT_POW.
SHORT_POW = 0.7
# The band flares out from its seam as 1 - (1 - d) ** FLARE_POW of the full
# drop d: most of the flare happens high up, inside the skirt, and the
# exposed lower band hangs nearly straight, turning gradually (no shelf).
FLARE_POW = 2.6
BELLY = 0.006     # how far the band bellies out between seam and hem (x hem outline)
HEM_ROLL = 0.6    # px radius of the rolled hem
RET_UP = 2.5      # px the turned-under hem runs back up inside
HEM_SMIN = 2.0    # softness (px) of the min of the front and side outlines
# The hem line hangs this far below the measured outline: the scallops'
# notches rise above it, so on average the bottom edge meets the outline.
HEM_DROP = 6.0
# Profile rings from the seam (0) to the hem (1), denser where the band
# turns from sloping to hanging and where the scallops form.
PROFILE = (0.0, 0.15, 0.30, 0.45, 0.60, 0.74, 0.87, 1.0)
# Share of the gathered surface's normal in the shading normals (the rest is
# the smooth band's; see _finish).
FOLD_SHADE = 0.3
# Hem roll: angles (deg) of the rings round the half circle under the edge.
ROLL_DEG = (60.0, 120.0, 180.0)
# Whether each tier casts sun shadows (obj['levi_cast_shadow'], read by
# render.py). Neither does: the scalloped hems printed scalloped bands on the
# thighs that the sheet does not paint, and the outer tier's shadow on the
# inner one made the petticoat far darker than the sheet (side / back shade
# 0.61 / 0.60 with it, 0.49 / 0.48 without; sheet 0.44 / 0.38). The smooth
# core cone (and the skirt) still cast, so the contact shadow under the
# skirt stays, with a smooth edge.
CAST_TIERS = (False, False)

# Tiers, outermost first. The sheet's bottom outline is a bowl: the outer
# ruffles (lifted with the skirt's sides) end highest and the tiers further
# in hang lower.
#   name, hem outline (half width, front depth, back depth px, superellipse
#   exponent), lift (x0, x1), top, gather folds (= scallops), fold depth px
#   (half the crest-to-valley depth at the hem), scallop rise px, seed
# top: ('free', height px, size of the top ring relative to the hem outline)
# for the outer tier, whose top is hidden under the skirt and over the core;
# ('core', px above the core's lower edge) for the inner tiers. These are not
# free-hanging rings: their tops are sewn onto the core cone (the inner the
# tier, the higher), so from below every tier reads as one continuous
# gathered panel nested inside the one around it.
# Lift: under the middle of the skirt, front and back, the sheet shows the
# legs from the skirt hem down, so within x0 px of the midline (front view)
# a tier's hem rises to LIFT_ROW, behind the skirt's centre hem, easing back
# to the measured bowl by x1.
TIERS = (
    ('petticoat_tier0', (HALF_W, FRONT_D, BACK_D, 2.0), (55, 90), ('free', 52, 0.86), 41, 2.6, 4.5, 1),
    ('petticoat_tier1', (0.70 * HALF_W, 0.70 * FRONT_D, 0.70 * BACK_D, 2.2), (55, 90), ('core', 22), 30, 2.4, 4.0, 2),
)
# Tuck up under the skirt, per tier: (front lobes, sides, back lobes) weights
# (see the module docstring); front and back blend across the sides.
# SIDE_BAND = (centre y, half width, ease px) of side-view columns; the leg
# shows a little in front of the middle.
TUCK_SECTOR = ((0.0, 0.7, 0.4), (0.0, 0.7, 0.4))
SIDE_BAND = (-18.0, 14.0, 40.0)
SIDE_WINDOW = 12.0     # deg either side: the side tuck clears the lowest skirt hem in this window
TUCK_PX = 4.0          # tucked hem sits this far above the skirt's hem
EXPOSE = (28.0, None)   # px of each tier that may hang below the skirt's hem (back half)
EXPOSE_FRONT = 30.0    # the limit relaxes this much more per unit of front weight
EXPOSE_MAX = (42.0, None)   # px of each tier that may hang below the skirt's hem anywhere
                            # (the outer tier's front quarters hung ~55 px below lifted
                            # troughs, reading as long flaps from 3/4 behind)
TUCK_U = (0.3, 0.75)   # lobe weight: 1 within |u| < u0 of the crest, 0 past u1
TUCK_SMOOTH = 1.0      # the tucked hem row is smoothed along the hem (sigma, folds)
MAX_SLOPE = 0.45       # the hem rises at most this many px per px along the band
MIN_LEN = 18.0         # a tier's hem stays at least this many px below its top
CLEAR = 4.0            # px inside the skirt's inner surface
CLEAR_SOFT = 1.0       # softness of that limit (px)
CLEAR_HOLD = 6.0       # below the skirt's edge the limit holds for this many px,
CLEAR_RELAX = 0.4      # then relaxes this many px per px (the cloth below hangs
CLEAR_FADE = 40.0      # nearly straight, not flaring out), and ends this many px down
CORE_RX = L['waist_half_w'] * 1.40   # core top ring round the hips (m)
CORE_RY = 0.065
CORE_CY = L['waist_center_y'] * 0.6
CORE_N = 24
CORE_RINGS = 6
CORE_TUCK = 16.0       # px the core reaches down inside the outer tier's top edge
LIFT_ROW = 585   # high enough that no lifted sliver peeks out under the skirt
# The lifted parts are hidden behind the skirt's long centre lobes, front and
# back; they are also drawn in a little towards the legs (by this fraction at
# the midline, easing out with the lift), so those lobes can hang down and
# tuck in instead of flaring out over the ruffles.
LIFT_PINCH = 0.12


def _interp(table, x):
    if x <= table[0][0]:
        return table[0][1]
    for (x0, y0), (x1, y1) in zip(table, table[1:]):
        if x <= x1:
            t = (x - x0) / (x1 - x0)
            return y0 + (y1 - y0) * t
    return table[-1][1]


def _smoothstep(e0, e1, x):
    t = min(1.0, max(0.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def _hash(k, seed):
    """Deterministic pseudo-random number in [0, 1) for integer k."""
    v = math.sin(k * 12.9898 + seed * 78.233) * 43758.5453
    return v - math.floor(v)


def _row(z):
    return spec.SHEET_GROUND_Y - z * spec.PX_PER_M


def _smooth_loop(v, sigma):
    """Circular Gaussian smoothing of the closed sequence v (sigma in samples)."""
    v = np.asarray(v, dtype=np.float64)
    n = len(v)
    k = np.arange(n) - n // 2
    w = np.exp(-0.5 * (k / max(sigma, 1e-6)) ** 2)
    w /= w.sum()
    return np.real(np.fft.ifft(np.fft.fft(v) * np.fft.fft(np.roll(w, -(n // 2)))))


# ---------------------------------------------------------------- skirt
_SEC575 = tuple(float(v) for v in skirt.section(575.0))


def skirt_azimuth(x, y):
    """Skirt azimuth phi (0 = front centre, + toward +X) of the point (x, y) px."""
    X, Yf, Yb = _SEC575
    return math.atan2(x / X, -y / (Yf if y < 0 else Yb))


class _SkirtInner:
    """Radius (px) of the skirt's inner surface along a horizontal ray from the
    body axis. The skirt's cloth sheet is rebuilt from skirt.profiles() with
    common.loft (as skirt.build() does, in px with z = -row), together with
    its solidify shell (the vertices moved inward along their normals by the
    skirt's thickness); the first hit of either counts."""

    def __init__(self):
        P = skirt.profiles(skirt.fold_table())
        rings = [[Vector((P[i, k, 0], P[i, k, 1], -P[i, k, 2])) for i in range(P.shape[0])]
                 for k in range(P.shape[1])]
        bm = common.loft(rings, closed=True)
        bm.normal_update()
        bm.verts.index_update()
        # the solidify shell: each vertex moved by the thickness against its
        # normal, pointing away from the body on the main sheet as in
        # skirt.build() (offset -1)
        thick = skirt.THICK * spec.PX_PER_M
        nmain = (len(skirt.T_STEPS) - 1) * P.shape[0]
        out = sum(f.normal.dot(Vector((f.calc_center_median().x, f.calc_center_median().y, 0.0)))
                  for f in list(bm.faces)[:nmain])
        sign = 1.0 if out > 0 else -1.0
        verts = [v.co.copy() for v in bm.verts]
        verts += [v.co - v.normal * (sign * thick) for v in bm.verts]
        nv = len(bm.verts)
        polys = [[v.index for v in f.verts] for f in bm.faces]
        polys += [[i + nv for i in p] for p in polys]
        bm.free()
        self.bvh = BVHTree.FromPolygons(verts, polys)

    def _cast(self, d, row):
        hit, _, _, dist = self.bvh.ray_cast(Vector((0.0, 0.0, -row)), d, 1000.0)
        return math.inf if hit is None else dist

    def limit(self, x, y, row):
        """Largest radius (px) a point in the direction of (x, y) px at the
        panel row may have: CLEAR inside the skirt; below the skirt's edge it
        holds for CLEAR_HOLD px, then relaxes by CLEAR_RELAX px per px; over
        the last 20 px before CLEAR_FADE it opens up quadratically (by ~200
        px at CLEAR_FADE, so there is no step to the inf beyond)."""
        d = Vector((x, y, 0.0))
        if d.length < 1e-9:
            return math.inf
        d.normalize()
        for up in np.arange(0.0, CLEAR_FADE + 0.1, 2.0):
            r = self._cast(d, row - up)
            if math.isfinite(r):
                return (r - CLEAR + CLEAR_RELAX * max(0.0, up - CLEAR_HOLD)
                        + 0.5 * max(0.0, up - (CLEAR_FADE - 20.0)) ** 2)
        return math.inf


def _clamp_ring(loop, inner):
    """Pull a ring of world points radially inside the skirt (soft minimum).
    The pull is spread to the neighbouring samples (dilated, then smoothed,
    never below what each sample needs), so it has no sharp steps."""
    n = len(loop)
    pull = np.zeros(n)
    rad = np.zeros(n)
    for i, p in enumerate(loop):
        x, y = p.x * spec.PX_PER_M, p.y * spec.PX_PER_M
        r = math.hypot(x, y)
        rad[i] = r
        lim = inner.limit(x, y, _row(p.z))
        if r < 1e-6 or not math.isfinite(lim):
            continue
        k = CLEAR_SOFT
        d = (r - lim) / k
        if d < -8.0:
            continue
        # soft min(r, lim): -k log(exp(-r/k) + exp(-lim/k))
        rn = lim - k * math.log1p(math.exp(-d)) if d > 0 else r - k * math.log1p(math.exp(d))
        pull[i] = r - rn
    if not pull.any():
        return loop
    wide = np.maximum(np.maximum(pull, np.roll(pull, 1)), np.roll(pull, -1))
    pull = np.maximum(pull, _smooth_loop(wide, 1.0))
    out = []
    for p, r, d in zip(loop, rad, pull):
        s = (r - d) / r if r > 1e-6 else 1.0
        out.append(Vector((p.x * s, p.y * s, p.z)))
    return out


# ---------------------------------------------------------------- outline
def _dense_outline(shape):
    """Dense closed counter-clockwise hem outline (px) from the front centre.

    shape: (half width, front depth, back depth, exponent), a superellipse
    (exponent 2 = ellipse, larger = boxier).
    """
    w, fd, bd, ex = shape
    e = 2.0 / ex
    out = []
    for i in range(DENSE):
        phi = 2 * math.pi * i / DENSE - math.pi / 2
        c, s = math.cos(phi), math.sin(phi)
        out.append((w * math.copysign(abs(c) ** e, c), (fd if s < 0 else bd) * math.copysign(abs(s) ** e, s)))
    return out


def _outline(shape, fracs):
    """Points (px) on the hem outline at the given arc-length fractions from
    the front centre, with their outward unit normals; and the perimeter."""
    pts = _dense_outline(shape)
    m = len(pts)
    cum = [0.0]
    for i in range(m):
        a, b = pts[i], pts[(i + 1) % m]
        cum.append(cum[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    total = cum[-1]
    res = []
    for f in fracs:
        s = (f * total) % total
        j = min(bisect.bisect_right(cum, s) - 1, m - 1)
        a, b = pts[j], pts[(j + 1) % m]
        t = (s - cum[j]) / max(cum[j + 1] - cum[j], 1e-9)
        tx, ty = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(tx, ty) or 1.0
        res.append(((a[0] + tx * t, a[1] + ty * t), (ty / ln, -tx / ln)))
    return res, total


def hem_row(x, y, lift=None):
    """Panel row of a tier's hem line at the hem-outline point (x, y) (panel
    px), before the tuck.

    The hem point projects onto front-view column |x| and side-view column y.
    The measured bottom outline of each view is the lowest ruffle point over
    that column, so a hem point should hang no lower than either outline: take
    the higher of the two (a smooth minimum, so there is no crease where they
    cross), then HEM_DROP lower for the scallops. Inner tiers reach the lower
    centre of the bowl-shaped outline, outer tiers its lifted sides. lift =
    (x0, x1) raises the hem near the midline to LIFT_ROW (see TIERS).
    """
    ax = abs(x)
    a, b = _interp(HEM_FRONT, ax), _interp(HEM_SIDE, y)
    row = min(a, b) - HEM_SMIN * math.log1p(math.exp(-abs(a - b) / HEM_SMIN)) + HEM_DROP
    if lift and row > LIFT_ROW:
        row += (LIFT_ROW - row) * (1.0 - _smoothstep(lift[0], lift[1], ax))
    return row


def hem_z(x, y, lift=None):
    """World z of hem_row()."""
    return spec.px_to_z(hem_row(x, y, lift))


def tuck(folds, x, y, row, sector, expose=None, expose_max=None):
    """Hem row after tucking (x, y) px up under the skirt (see TUCK_SECTOR);
    row is the untucked hem row, folds the skirt's fold table."""
    phi = skirt_azimuth(x, y)
    _, u = skirt.fold_index(folds, phi)
    srows = skirt.hem_terms(folds, phi + np.radians(SIDE_WINDOW) * np.linspace(-1.0, 1.0, 9))[0]
    lobe = 1.0 - _smoothstep(TUCK_U[0], TUCK_U[1], abs(float(u)))
    wf = _smoothstep(-0.25, 0.25, math.cos(phi))       # 1 in the front half, 0 in the back
    # under a lobe: up to just above the skirt's hem there
    w_lobe = lobe * (sector[2] + (sector[0] - sector[2]) * wf)
    r_lobe = row + w_lobe * (min(row, float(srows[len(srows) // 2]) - TUCK_PX) - row)
    # at the sides: up behind the lowest skirt hem nearby
    w_side = sector[1] * (1.0 - _smoothstep(SIDE_BAND[1], SIDE_BAND[1] + SIDE_BAND[2], abs(y - SIDE_BAND[0])))
    r_side = row + w_side * (min(row, float(srows.max()) - TUCK_PX) - row)
    # under a raised trough in the back half: no more than EXPOSE px of this
    # tier below the skirt, so the tiers inside show below it as layered
    # ruffles instead of one tall panel (the front keeps its measured hem)
    lim = math.inf
    trough = float(srows[len(srows) // 2 - 1:len(srows) // 2 + 2].max())
    if expose is not None and wf < 1.0:
        lim = trough + expose + EXPOSE_FRONT * wf / (1.0 - wf)
    # anywhere: no more than expose_max px below the skirt (the front
    # quarters under lifted troughs would otherwise hang as long flaps)
    if expose_max is not None:
        lim = min(lim, trough + expose_max)
    return min(r_lobe, r_side, lim)


def _limit_slope(rows, arc, slope, sign=1.0):
    """Lower the closed sequence of hem rows (raise the hem) wherever it would
    climb faster than slope px per px of arc (arc: positions px along the
    band, perimeter last). sign=-1 raises the rows (lowers the hem) instead."""
    rows = sign * np.array(rows, dtype=np.float64)
    n = len(rows)
    total, arc = arc[-1], arc[:n]
    for _ in range(2):
        for i in range(n):              # forward and backward sweeps round the loop
            j = (i - 1) % n
            ds = (arc[i] - arc[j]) % total
            rows[i] = min(rows[i], rows[j] + slope * ds)
        for i in range(n - 1, -1, -1):
            j = (i + 1) % n
            ds = (arc[j] - arc[i]) % total
            rows[i] = min(rows[i], rows[j] + slope * ds)
    return sign * rows


def _gentle(rows, arc, slope):
    """The hem rows with their slope limited to `slope` both ways: the mean of
    the raised and the lowered envelope (each limited to `slope`), so a tuck
    keeps its mean height but ramps in and out gently."""
    return 0.5 * (_limit_slope(rows, arc, slope) + _limit_slope(rows, arc, slope, -1.0))


def _lift_pinch(x, lift):
    """Radial scale of the hem outline point at x px (see LIFT_PINCH)."""
    return 1.0 - LIFT_PINCH * (1.0 - _smoothstep(lift[0], lift[1], abs(x)))


# ---------------------------------------------------------------- core
def _core_bottom(phi):
    """(x, y, z) world point of the core's lower edge at ellipse angle phi."""
    _, dims0, lift0, (_, height0, top0) = TIERS[0][:4]
    c, s = math.cos(phi), math.sin(phi)
    hx, hy = dims0[0] * c, (dims0[1] if s < 0 else dims0[2]) * s
    # a few px below the outer tier's (untucked) top edge
    z = hem_z(hx, hy, lift0) + (height0 - CORE_TUCK) * PX
    k = top0 * 0.97 * _lift_pinch(hx, lift0) * PX
    return Vector((k * hx, k * hy, z))


def _core_top(phi):
    """(x, y, z) world point of the core's top ring (round the hips) at angle phi."""
    return Vector((CORE_RX * math.cos(phi), CORE_CY + CORE_RY * math.sin(phi), L['hip_z']))


def _core_point(x, y, up_px):
    """Point on the core cone up_px above its lower edge, in the direction of
    the hem outline point (x, y) px."""
    w, fd, bd = TIERS[0][1][:3]
    phi = math.atan2(y / (fd if y < 0 else bd), x / w)
    b, t = _core_bottom(phi), _core_top(phi)
    return b.lerp(t, min(1.0, up_px * PX / (t.z - b.z)))


# ---------------------------------------------------------------- tiers
def _gathers(count, seed, off):
    """Arc-length fractions of the samples round a tier (SPF per fold, the
    folds unevenly wide), each sample's phase in its fold (0 = notch over the
    inner valley, 0.5 = crest) and fold index."""
    w = [1.0 + WIDTH_VAR * (2 * _hash(k, seed + 3) - 1) for k in range(count)]
    total = sum(w)
    fracs, phase, fold = [], [], []
    start = off * total / count
    for k in range(count):
        for i in range(SPF):
            fp = i / SPF
            fracs.append((start + fp * w[k]) / total)
            phase.append(fp)
            fold.append(k)
        start += w[k]
    return fracs, phase, fold


def _per_fold(count, seed, fold):
    """Per-sample factor 1 +- DEPTH_VAR, one value per fold, blended smoothly
    over neighbouring folds so the depth never steps at a notch."""
    raw = [1.0 + DEPTH_VAR * (2 * _hash(k, seed) - 1) for k in fold]
    return _smooth_loop(raw, VAR_SMOOTH * SPF)


def _tier(col, idx, inner, folds, name, shape, lift, top, count, depth_px, rise_px, seed):
    fracs, phase, fold = _gathers(count, seed, 0.5 * (idx % 2))
    outline, total = _outline(shape, fracs)
    n = len(outline)
    # hem outline, drawn in near the lifted midline
    hem = [((bx * k, by * k), nrm) for (bx, by), nrm in outline for k in (_lift_pinch(bx, lift),)]
    # top ring: free (above the untucked hem, scaled) or sewn onto the core
    if top[0] == 'free':
        tops = [Vector((top[2] * bx * PX, top[2] * by * PX, hem_z(ox, oy, lift) + top[1] * PX))
                for ((bx, by), _), ((ox, oy), _) in zip(hem, outline)]
    else:
        tops = [_core_point(bx, by, top[1]) for (bx, by), _ in hem]
    # full drop (untucked hem) and the tucked hem: measured bowl + lift,
    # tucked under the skirt, smoothed, slope limited, smoothed again, and at
    # least MIN_LEN below the top. The slope is limited both ways (_gentle),
    # so tucks ramp in and out without lifting the hem around them. That can
    # let a tucked or lifted hem sag a little, so the result never hangs
    # below the raw tuck ramped in at 1 px per px (raise-only, so it is at or
    # above tuck() everywhere): no sliver shows under the skirt's lobes or
    # past LIFT_ROW.
    full = [hem_z(ox, oy, lift) for (ox, oy), _ in outline]
    arc = [(f - fracs[0]) * total for f in fracs] + [total]
    raw = [tuck(folds, ox, oy, hem_row(ox, oy, lift), TUCK_SECTOR[idx], EXPOSE[idx], EXPOSE_MAX[idx])
           for (ox, oy), _ in outline]
    rows = _gentle(_smooth_loop(raw, TUCK_SMOOTH * SPF), arc, MAX_SLOPE)
    rows = np.minimum(_smooth_loop(rows, 0.5 * SPF), _limit_slope(raw, arc, 1.0))
    hems = [spec.px_to_z(max(r, _row(t.z) + MIN_LEN)) for r, t in zip(rows, tops)]
    amp = _per_fold(count, seed + 7, fold)
    rise = _per_fold(count, seed + 29, fold)
    # fabric per fold: a band shortened by the tuck folds less deeply
    short = [min(1.0, max(0.0, (t.z - h) / max(t.z - f, 1e-6))) ** SHORT_POW
             for t, h, f in zip(tops, hems, full)]
    def rings(k):
        """The tier's rings with k x the gathers and scallops (k = 0: the
        smooth band they are laid on)."""
        loops = []
        for s in PROFILE:
            loop = []
            for i, ((bx, by), (nx, ny)) in enumerate(hem):
                t = tops[i]
                z = t.z + s * (hems[i] - t.z)
                # where on the full seam-to-hem drop this height lies
                d = min(1.0, max(0.0, (t.z - z) / max(t.z - full[i], 1e-6)))
                g = 1.0 - (1.0 - d) ** FLARE_POW
                belly = 1.0 + BELLY * math.sin(math.pi * d)
                cpos = math.cos(2 * math.pi * phase[i])
                # the seam ring itself lies on its support (the core cone)
                grow = SEAM_FOLD + (1.0 - SEAM_FOLD) * d ** FOLD_POW if s > 0.0 else 0.0
                gather = -k * cpos * depth_px * amp[i] * short[i] * grow
                notch = (0.5 + 0.5 * cpos) ** NOTCH_P
                x = t.x + (belly * bx * PX - t.x) * g + nx * gather * PX
                y = t.y + (belly * by * PX - t.y) * g + ny * gather * PX
                z += k * rise_px * rise[i] * notch * s ** 1.5 * PX
                loop.append(Vector((x, y, z)))
            loops.append(_clamp_ring(loop, inner))
        return loops + _hem_roll(loops[-2], loops[-1])

    obj = _finish(col, common.toon_material('petticoat'), name, rings(1.0), soft=rings(0.0))
    obj['levi_cast_shadow'] = CAST_TIERS[idx]
    return obj


def _hem_roll(prev, edge):
    """Rings that turn the hem edge under: a half circle of HEM_ROLL px radius
    in the plane of the cloth's normal and its downward direction, then a
    short return back up inside (RET_UP)."""
    n = len(edge)
    rr = HEM_ROLL * PX
    frames = []
    for i, p in enumerate(edge):
        down = p - prev[i]
        down = down.normalized() if down.length > 1e-9 else Vector((0.0, 0.0, -1.0))
        tan = edge[(i + 1) % n] - edge[i - 1]
        nrm = down.cross(tan)
        if nrm.length < 1e-9:
            nrm = Vector((p.x, p.y, 0.0))
        nrm.normalize()
        if nrm.dot(Vector((p.x, p.y, 0.0))) < 0.0:
            nrm = -nrm
        frames.append((p, nrm, down))
    rings = []
    for deg in ROLL_DEG:
        a = math.radians(deg)
        rings.append([p - nrm * rr + nrm * (rr * math.cos(a)) + down * (rr * math.sin(a))
                      for p, nrm, down in frames])
    rings.append([p - nrm * (2 * rr) - down * (RET_UP * PX) for p, nrm, down in frames])
    return rings


def _outward(bm):
    """bm with its faces turned to point away from the body axis (area
    weighted), since recalc_face_normals is ambiguous on an open tube."""
    out = sum(f.normal.dot(Vector((c.x, c.y, 0.0))) * f.calc_area()
              for f in bm.faces for c in (f.calc_center_median(),))
    if out < 0.0:
        bmesh.ops.reverse_faces(bm, faces=list(bm.faces))
    return bm


def _finish(col, mat, name, loops, soft=None):
    """Loft the rings into a cloth object with an outline.

    recalc_face_normals is ambiguous on an open tube, so orientation is set
    explicitly: faces point OUTWARD (away from the body axis) on the main
    sheet, so the outline hull sits on the outside of the hem and draws a
    line along every scallop; the hull's backface culling keeps it off the
    fill. The turned-under return then faces the axis, as the inside of a
    thin cloth should. Smooth shading throughout: the rolled hem turns in
    60 degree steps and must not split normals.

    soft: the same rings without the gathers. The shading normals are then
    blended from the gathered surface's (FOLD_SHADE) and the smooth band's,
    so the folds shade softly: their flanks stay lit instead of breaking
    into small shade wedges where the folds peek out under the skirt, while
    the form, silhouette and outline keep the full gathers.
    """
    bm = _outward(common.loft(loops, closed=True))
    obj = common.new_object(col, name, bm, [mat])
    common.shade_smooth(obj, 180.0)
    if soft is not None:
        sb = _outward(common.loft(soft, closed=True))
        sb.normal_update()
        base = [v.normal.copy() for v in sb.verts]
        sb.free()
        me = obj.data
        assert len(base) == len(me.vertices), (name, len(base), len(me.vertices))
        normals = []
        for v, b in zip(me.vertices, base):
            own = Vector(v.normal)
            if b.dot(own) < 0.0:      # never blend against a flipped normal
                b = -b
            nv = own * FOLD_SHADE + b * (1.0 - FOLD_SHADE)
            normals.append(nv.normalized() if nv.length > 1e-9 else Vector(v.normal))
        me.normals_split_custom_set_from_vertices(normals)
    common.add_outline(obj)
    return obj


def _core(col, mat, inner):
    """Hidden inner cone from the hips down into the top of the outer tier,
    with CORE_RINGS rings so the skirt chains bend it smoothly. The tiers'
    seams lie on the same straight generators, so they stay on it."""
    phis = [2 * math.pi * i / CORE_N for i in range(CORE_N)]
    top = [_core_top(p) for p in phis]
    bot = [_core_bottom(p) for p in phis]
    loops = [[t.lerp(b, j / (CORE_RINGS - 1)) for t, b in zip(top, bot)] for j in range(CORE_RINGS)]
    return _finish(col, mat, 'petticoat_core', [_clamp_ring(loop, inner) for loop in loops])


def build(col):
    inner = _SkirtInner()
    folds = skirt.fold_table()
    _core(col, common.toon_material('petticoat'), inner)
    for idx, tier in enumerate(TIERS):
        _tier(col, idx, inner, folds, *tier)
