"""Petticoat: peach-pink gathered tiers below the skirt hem.

Objects:
  petticoat_core     inner cone from the hips down; hidden by the skirt.
  petticoat_tier0-1  gathered ruffle tiers, outermost first. The outer one
                     shows where the skirt is lifted; the inner one hangs
                     lowest, beside the legs, and shows below the outer one.

Each tier is one thin band of gathered fabric, not a row of padded panels:
- The band falls from its seam (gathered onto the core, or under the skirt
  for the outer tier) in a smooth curve, sloping out under the seam and
  hanging nearly straight at the hem, sampled by five profile rings so the
  skirt chains bend it smoothly. It barely bellies out (BELLY).
- Gathers: shallow bell folds (about one per two petals, unevenly spaced and
  deep) plus a small, irregular puff per petal, a little off the petal's
  centre. They are shallow at the seam (SEAM_FOLD) and open up towards the
  hem. Each tier has its own seed and phase, and neighbouring tiers' petals
  are offset by half a petal, so the tiers' scallops do not line up.
- The hem is a row of shallow scallop petals with a near-circular bottom that
  meets the next petal in a notch with a finite slope. Each petal has
  PETAL_FP samples, denser on the shoulders by the notch than across the flat
  bottom. The hem edge turns up and in by about a pixel (one return ring), a
  thin fold rather than a rolled bead, so the outline hull still draws a line
  along every scallop.

Exposure: the sheet shows the ruffles mainly under the skirt's raised fold
troughs, and keeps them tucked up under the hanging lobes; in the side view
the leg shows under the skirt's sides. A tier's hem is raised (tuck()):
- in the back half, under the skirt's lobes, to just above the skirt's hem
  there (TUCK_PX), fading out towards the troughs (TUCK_SECTOR back weight);
- round each side, over the band of side-view columns where the sheet shows
  the leg (SIDE_BAND), behind the lowest skirt hem nearby (SIDE_WINDOW).
The front keeps its measured hem. The tucked hem is then smoothed along the
band and its slope limited (MAX_SLOPE), so it rises in broad curves rather
than steep steps. The skirt's hem rows and folds come from
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
JITTER = 0.35     # bell fold spacing irregularity (fraction of a bell)
DEPTH_VAR = 0.4   # bell depth / petal rise irregularity
PETALS_PER_BELL = 1.4
# Sample positions across a petal (fraction of its width, notch at 0): dense
# on the curved shoulders by the notch, sparse across the flat bottom.
PETAL_FP = (0.0, 0.13, 0.27, 0.42, 0.58, 0.73, 0.87)
PUFF = 2.4        # px a petal's gather puffs out (varies per petal by PUFF_VAR)
PUFF_VAR = 0.6
PUFF_SHIFT = 0.2  # max shift of a petal's puff off its centre (fraction of a petal)
NOTCH_K = 0.85    # petal bottom: circular arc for 1, rounder notch below
NOTCH_N = 1.0 - math.sqrt(1.0 - NOTCH_K)
BELL_RISE = 0.5   # hem rise at a bell fold relative to the petal rise
BELLY = 0.008     # how far the band bellies out between seam and hem (x hem outline)
RET_UP = 1.1      # hem return: px up ...
RET_IN = 0.6      # ... and px in from the hem edge
HEM_SMIN = 2.0    # softness (px) of the min of the front and side outlines
# The hem line hangs this far below the measured outline: the scallops' notches
# rise above it and their shoulders curve up, so on average the bottom edge
# meets the outline.
HEM_DROP = 3.0

# Tiers, outermost first. The sheet's bottom outline is a bowl: the outer
# ruffles (lifted with the skirt's sides) end highest and the tiers further
# in hang lower.
#   name, hem outline (half width, front depth, back depth px, superellipse
#   exponent), lift (x0, x1), top, scallop petals, bell fold depth px, petal
#   rise px, seed
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
    ('petticoat_tier0', (HALF_W, FRONT_D, BACK_D, 2.0), (55, 90), ('free', 52, 0.80), 40, 8.0, 6.5, 1),
    ('petticoat_tier1', (0.70 * HALF_W, 0.70 * FRONT_D, 0.70 * BACK_D, 2.2), (55, 90), ('core', 22), 28, 6.0, 5.5, 2),
)
# Tuck up under the skirt, per tier: (front lobes, sides, back lobes) weights
# (see the module docstring); front and back blend across the sides.
# SIDE_BAND = (centre y, half width, ease px) of side-view columns; the leg
# shows a little in front of the middle.
TUCK_SECTOR = ((0.0, 1.0, 0.4), (0.0, 1.0, 0.4))
SIDE_BAND = (-18.0, 14.0, 22.0)
SIDE_WINDOW = 12.0     # deg either side: the side tuck clears the lowest skirt hem in this window
TUCK_PX = 4.0          # tucked hem sits this far above the skirt's hem
EXPOSE = (28.0, None)   # px of each tier that may hang below the skirt's hem (back half)
EXPOSE_FRONT = 30.0    # the limit relaxes this much more per unit of front weight
TUCK_U = (0.3, 0.75)   # lobe weight: 1 within |u| < u0 of the crest, 0 past u1
TUCK_SMOOTH = 0.6      # the tucked hem row is smoothed along the hem (sigma, petals)
MAX_SLOPE = 0.7        # the hem rises at most this many px per px along the band
MIN_LEN = 18.0         # a tier's hem stays at least this many px below its top
CLEAR = 4.0            # px inside the skirt's inner surface
CLEAR_SOFT = 1.0       # softness of that limit (px)
CLEAR_HOLD = 6.0       # below the skirt's edge the limit holds for this many px,
CLEAR_FADE = 20.0      # then relaxes (1 px per px), and ends this many px down
CORE_RX = L['waist_half_w'] * 1.40   # core top ring round the hips (m)
CORE_RY = 0.065
CORE_CY = L['waist_center_y'] * 0.6
CORE_N = 16
CORE_RINGS = 6
CORE_TUCK = 16.0       # px the core reaches down inside the outer tier's top edge
LIFT_ROW = 585   # high enough that no lifted sliver peeks out under the skirt
# The lifted parts are hidden behind the skirt's long centre lobes, front and
# back; they are also drawn in a little towards the legs (by this fraction at
# the midline, easing out with the lift), so those lobes can hang down and
# tuck in instead of flaring out over the ruffles.
LIFT_PINCH = 0.12
# Profile rings from the seam to the hem: (height between the hem (0) and
# the top ring (1), fold amount). The ring's distance out from the top ring
# towards the hem outline is 1 - h^2: sloping out under the seam, hanging
# straight at the hem. The return ring follows.
SEAM_FOLD = 0.35
RINGS = (
    (1.00, SEAM_FOLD),
    (0.72, 0.6),
    (0.46, 0.8),
    (0.22, 0.92),
    (0.00, 1.00),
)


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
        holds for CLEAR_HOLD px, then relaxes by 1 px per px, and is inf more
        than CLEAR_FADE px down."""
        d = Vector((x, y, 0.0))
        if d.length < 1e-9:
            return math.inf
        d.normalize()
        for up in np.arange(0.0, CLEAR_FADE + 0.1, 2.0):
            r = self._cast(d, row - up)
            if math.isfinite(r):
                return r - CLEAR + max(0.0, up - CLEAR_HOLD)
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


def tuck(folds, x, y, row, sector, expose=None):
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
    if expose is not None and wf < 1.0:
        lim = float(srows[len(srows) // 2 - 1:len(srows) // 2 + 2].max()) + expose + EXPOSE_FRONT * wf / (1.0 - wf)
    return min(r_lobe, r_side, lim)


def _limit_slope(rows, arc, slope):
    """Lower the closed sequence of hem rows (raise the hem) wherever it would
    climb faster than slope px per px of arc (arc: positions px along the
    band, perimeter last)."""
    rows = np.array(rows, dtype=np.float64)
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
    return rows


class Waves:
    """Rounded, unevenly spaced waves around a band, s in [0, 1) (arc length)."""

    def __init__(self, count, seed, jitter, phase=0.0):
        self.n = count
        self.crest = [(k + 0.5 + phase + jitter * (_hash(k, seed) - 0.5)) / count for k in range(count)]
        self.amp = [1.0 + DEPTH_VAR * (2 * _hash(k, seed + 17) - 1) for k in range(count)]

    def __call__(self, s):
        """(f, amp): f in [0, 1) runs from one crest to the next (0.5 = the fold
        between them); amp eases between the two crests' depths."""
        c, n = self.crest, self.n
        s = (s - c[0]) % 1.0 + c[0]
        k = bisect.bisect_right(c, s) - 1
        b = c[(k + 1) % n] + (1.0 if k == n - 1 else 0.0)
        f = (s - c[k]) / (b - c[k])
        e = 0.5 - 0.5 * math.cos(math.pi * f)
        return f, self.amp[k] + (self.amp[(k + 1) % n] - self.amp[k]) * e


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
def _tier(col, idx, inner, folds, name, shape, lift, top, petals, depth_px, rise_px, seed):
    spp = len(PETAL_FP)
    off = 0.5 * (idx % 2)                                # neighbouring tiers: petals offset by half
    fracs = [(k + fp + off) / petals for k in range(petals) for fp in PETAL_FP]
    outline, total = _outline(shape, fracs)
    n = len(outline)
    # top ring: free (above the untucked hem, scaled) or sewn onto the core
    hem = [((bx * k, by * k), nrm) for (bx, by), nrm in outline for k in (_lift_pinch(bx, lift),)]
    if top[0] == 'free':
        tops = [Vector((top[2] * bx * PX, top[2] * by * PX, hem_z(ox, oy, lift) + top[1] * PX))
                for ((bx, by), _), ((ox, oy), _) in zip(hem, outline)]
    else:
        tops = [_core_point(bx, by, top[1]) for (bx, by), _ in hem]
    # hem rows: measured bowl + lift, tucked under the skirt, smoothed, slope
    # limited, and at least MIN_LEN below the top
    rows = [tuck(folds, ox, oy, hem_row(ox, oy, lift), TUCK_SECTOR[idx], EXPOSE[idx]) for (ox, oy), _ in outline]
    rows = _smooth_loop(rows, TUCK_SMOOTH * spp)
    arc = [(f - fracs[0]) * total for f in fracs] + [total]
    rows = _limit_slope(rows, arc, MAX_SLOPE)
    hems = [spec.px_to_z(max(r, _row(t.z) + MIN_LEN)) for r, t in zip(rows, tops)]
    # rise and puff vary per petal, and the puff (the petal's gather) sits a
    # little off the petal's centre
    pamp = [1.0 + DEPTH_VAR * (2 * _hash(k, seed + 7) - 1) for k in range(petals)]
    puff = [PUFF * (1.0 + PUFF_VAR * (2 * _hash(k, seed + 29) - 1)) for k in range(petals)]
    shift = [PUFF_SHIFT * (2 * _hash(k, seed + 43) - 1) for k in range(petals)]
    bells = Waves(max(3, round(petals / PETALS_PER_BELL)), seed + 101, JITTER, phase=0.37 * idx)
    waves = []
    for i in range(n):
        k, fp = divmod(i, spp)
        fp = PETAL_FP[fp]
        fb, ab = bells(fracs[i] % 1.0)
        ub = 0.5 - 0.5 * math.cos(2 * math.pi * fb)      # 0 on a bell crest, 1 in the fold
        # puff: 0 at both notches, peak at 0.5 + shift
        c = 0.5 + shift[k]
        g = fp / (2 * c) if fp < c else 0.5 + (fp - c) / (2 * (1 - c))
        up = 0.5 - 0.5 * math.cos(2 * math.pi * g)
        d = 2.0 * min(fp, 1.0 - fp)                       # 0 at the petal centre, 1 at the notch
        notch = (1.0 - math.sqrt(1.0 - NOTCH_K * d * d)) / NOTCH_N   # near-circular, finite slope at the notch
        dip = depth_px * ab * ub + puff[k] * up
        rise = rise_px * pamp[k] * notch + BELL_RISE * rise_px * ab * ub * ub
        waves.append((dip, rise))
    loops = []
    for h, amount in RINGS:
        g = 1.0 - h * h
        belly = 1.0 + BELLY * math.sin(math.pi * h)
        loop = []
        for i, ((bx, by), (nx, ny)) in enumerate(hem):
            dip, rise = waves[i]
            d = dip * amount * PX
            t = tops[i]
            hx, hy = belly * bx * PX, belly * by * PX
            x = t.x + (hx - t.x) * g - nx * d
            y = t.y + (hy - t.y) * g - ny * d
            z = hems[i] + h * (t.z - hems[i]) + rise * PX * (1.0 - h)
            loop.append(Vector((x, y, z)))
        loops.append(_clamp_ring(loop, inner))
    # hem return: a thin fold up and in from the (clamped) hem edge
    loops.append(_clamp_ring([Vector((p.x - nx * RET_IN * PX, p.y - ny * RET_IN * PX, p.z + RET_UP * PX))
                              for p, (_, (nx, ny)) in zip(loops[-1], hem)], inner))
    return _finish(col, common.toon_material('petticoat'), name, loops)


def _finish(col, mat, name, loops):
    """Loft the rings into a sheet object with an outline.

    recalc_face_normals is ambiguous on an open tube, so orientation is set
    explicitly: faces point OUTWARD (away from the body axis), so the outline
    hull sits on the outside of the hem and draws a line along every
    scallop; the hull's backface culling keeps it off the fill.
    """
    bm = common.loft(loops, closed=True)
    out = sum(f.normal.dot(Vector((c.x, c.y, 0.0))) * f.calc_area()
              for f in bm.faces for c in (f.calc_center_median(),))
    if out < 0.0:
        bmesh.ops.reverse_faces(bm, faces=list(bm.faces))
    obj = common.new_object(col, name, bm, [mat])
    common.shade_smooth(obj, 70.0)
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
