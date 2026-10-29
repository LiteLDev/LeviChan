"""Petticoat: three tiers of peach-pink scalloped frills below the skirt hem.

Objects:
  petticoat_tier0  the outer tier. Its top hangs free under the skirt; its
                   frill ends highest.
  petticoat_tier1  the middle tier, sewn onto the core; its frill shows below
                   the outer one.
  petticoat_tier2  the inner tier, hanging from the core's lower edge (round
                   11: the core became a short gathered tier); it hangs
                   lowest, beside the legs.
  petticoat_core   a gathered cone from the hips down to the inner tier,
                   hidden by the skirt. From below the view runs up the inner
                   frill's flutes into the core's gathers instead of a smooth
                   pink cone.

The sheet (ref/front|side|back.png) and the art (ref/setting.png,
ref/illustration.png) draw two or three stacked layers of small, round,
puffed scallops (~1.3-1.6 cm) hanging in bell-shaped clusters under the
skirt's raised arches. Round 11 builds that (rounds 6-10 had two tiers of
6-7.5 cm folds that read as plain bands):

- Frill: each tier is gathered into ~1.6 cm flutes (one per scallop, SPF
  samples across, unevenly wide and deep, VAR_SMOOTH), shallow up the band
  and opening in the frill near the hem (FLUTE_SEAM, FLUTE_POW). The flutes are puffed,
  not a sine wave: across a flute the cloth bulges as 2 sin(pi phase) **
  PUFF_P - 1, so the crest is a round puff and the valley between two
  scallops a pinched pleat, as in the art's radial pleat lines.
- Hem: one round scallop per flute, the notch over the pleat (the lobe a
  circular arc, ROUND). The edge rolls under in a half circle
  (HEM_ROLL px, ROLL_DEG) and runs a little way back up inside (RET_UP), so
  every scallop has real thickness and the outline hull draws its edge.
- Bell: the lower band flares out a little (MOUTH from MOUTH_S of the band
  down), and the clusters (cluster_rows(), below) make each tier hang lower
  under the skirt's arches: under each arch the three stacked frills form a
  bell, as on the sheet.
- Profile: each tier is one surface, radius(azimuth, height), flaring out
  under the seam (inside the skirt) and hanging nearly straight lower down
  (1 - (1 - d) ** FLARE_POW of the full seam-to-hem drop d). Where the hem
  is tucked up under the skirt, the band ends higher on the same surface (it
  gets shorter, and its flutes shallower: SHORT_POW). PROFILE rings (closer
  towards the hem) let the skirt chains bend it smoothly.
- Shading: the flutes' shading normals are blended towards the smooth
  band's (FOLD_SHADE), so flute flanks peeking out under the skirt do not
  break into small shade wedges; the geometry, silhouette and outline keep
  the flutes. The outline hull is full width only at the scalloped edge
  (LINE_*): the flutes' own silhouettes up the band, which stand for the
  art's thin pleat lines, and the core draw thinner lines.

Exposure (round 6): the exposed frills follow the skirt's hem instead of
hanging from a fixed bowl and being tucked up in steps. Each tier's hem is
the skirt's built hem (skirt.hem_terms) plus an exposure that swells, with a
cosine ease across each skirt fold, from a narrow band under the lobe to a
rounded cluster under the arch (cluster_rows(): EXPOSE_LOBE / EXPOSE, more
in front and back, least at the sides where the side view shows the leg),
and never below the measured bowl (less BOWL_UP per tier, so the three hems
stay stacked). The hem is smoothed along the band and its rise limited
(CLUSTER_SLOPE). Where the hem rises, the tier's seam rises with it
(BAND_MIN, hidden inside the skirt), so the exposed band keeps its gathered
flare instead of hanging as a long flat panel. The skirt's hem rows and
folds come from levi/parts/skirt.py (fold_table / hem_terms / fold_index /
profiles, pure functions), so the clusters and the clearance follow the
skirt.

Clearance: every ring is kept at least CLEAR px inside the skirt's inner
surface (the skirt's sheet rebuilt from skirt.profiles(), less its solidify
thickness) with a soft minimum, and each inner tier TIER_CLEAR px inside the
tiers around it (their built meshes), the flutes' outward reach included.
Below an outer layer's edge the limit relaxes gradually instead of switching
off, and the inward pull is spread along each ring (_clamp_ring), so the
clamp leaves no sharp radial steps.

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
# Samples across one scallop / flute (phase: notch over the pleat at 0, crest
# at 0.5), evenly spaced: the rig smooths the weights along the rings per
# vertex step (rig._diffuse treats every edge shorter than the median alike),
# so samples bunched beside the notch (1.4 mm apart, round 11 trial) took the
# whole weight gradient of a wider step and stretched x2.5-2.7 in sit_chair
# / high_kick where the flute scale stretched x1.5.
PHASES = (0.0, 1 / 6, 2 / 6, 0.5, 4 / 6, 5 / 6)
SPF = len(PHASES)
WIDTH_VAR = 0.18  # scallop width irregularity (share of the mean width, +-)
DEPTH_VAR = 0.3   # flute depth / scallop rise irregularity
VAR_SMOOTH = 0.7  # per-flute depth / rise blended over this many flutes (sigma)
ROUND = 0.65      # scallop rise 1 - (1 - x ** 2) ** ROUND, x = 1 at the notch .. 0 mid-lobe
                  # (0.5: a circular lobe; a little fuller beside the notch, so the
                  # notch is not a lone raised vertex the rig's smoothing skips)
PUFF_P = 0.55     # flute cross-section 2 sin(pi phase) ** PUFF_P - 1: puffed crest, pinched pleat
SEAM_FOLD = 0.35  # share of the bell depth just below the seam (gathered: the bells run up the band)
SEAM_RAMP = 0.25  # ... reached over this share of the band from the seam (smoothstep), so the
                  # gathers open continuously out of the seam (no step at the first ring)
FOLD_POW = 0.6    # the bells open as d ** FOLD_POW down the band
# The flutes stay shallow up the band and open in the frill near the hem
# (FLUTE_SEAM of their depth at the seam, then d ** FLUTE_POW): deep flutes
# all the way up drew a long pleat line per flute (a feathered fan) wherever
# the band is seen along its slope.
FLUTE_SEAM = 0.12
FLUTE_POW = 1.6
# Bells: the flutes gather in runs of BELL_SIZE (3-4, ~5-6 cm) into a wider
# fold (a cosine, crest mid-bell, BELL[tier] depth px) whose edges rise (BELL
# rise px, ((1 + cos) / 2) ** BELL_P), so each run hangs as a small bell with
# a scalloped mouth, as the sheet draws them; the bells keep their full
# shading (only the flutes are softened, FOLD_SHADE).
BELL_SIZE = (3, 4)
BELL = ((4.5, 5.0), (4.0, 4.6), (3.6, 4.2))
BELL_P = 1.5
RISE_POW = 2.0    # the scallop notch rises as s ** RISE_POW down the band (the pleat curves into it)
# Rings above this share of the band keep every second sample: the gathered
# rings under the seam are the smallest (1.8 mm between samples on the middle
# tier), and the rig's weights (smoothed and pruned per vertex step) switched
# bones over a few of them, stretching single edges x2.1-2.5 (walk, high_kick)
# where the band stretched x1.2; the flutes there are shallow anyway.
COARSE_S = 0.35
LEVEL = 0.5       # share of each scallop levelled about its middle on a sloping hem (_level)
# Where the hem is tucked up, the band is shorter and has less fabric to
# fold: the flute depth scales with (band length / full length) ** SHORT_POW.
SHORT_POW = 0.15
# The band flares out from its seam as 1 - (1 - d) ** FLARE_POW of the full
# drop d: most of the flare happens high up, inside the skirt, and the
# exposed lower band hangs nearly straight, turning gradually (no shelf).
FLARE_POW = 1.35
BELLY = 0.006     # how far the band bellies out between seam and hem (x hem outline)
MOUTH = 3.0       # px the frill's mouth flares out (bell) ...
MOUTH_S = 0.5     # ... growing (smoothstep) from this share of the band to the hem
HEM_ROLL = 0.6    # px radius of the rolled hem
RET_UP = 2.0      # px the turned-under hem runs back up inside
HEM_SMIN = 2.0    # softness (px) of the min of the front and side outlines
# The hem line hangs this far below the measured outline: the scallops'
# notches rise above it, so on average the bottom edge meets the outline.
HEM_DROP = 5.0
# Profile rings from the seam (0) to the hem (1), denser where the band
# turns from sloping to hanging and where the scallops form.
PROFILE = (0.0, 0.16, 0.32, 0.46, 0.59, 0.70, 0.80, 0.88, 0.945, 1.0)
# Share of the gathered surface's normal in the shading normals (the rest is
# the smooth band's; see _finish).
FOLD_SHADE = 0.68
# Hem roll: angles (deg) of the rings round the half circle under the edge.
ROLL_DEG = (90.0, 180.0)
# Outline hull: full width at the scalloped edge, LINE_MIN of it up the band
# (the flutes' silhouettes there are the art's thin pleat lines) and on the
# core; the weight eases in from LINE_S of the band down.
LINE_VG = 'petticoat_line'
LINE_MIN = 0.3
LINE_S = (0.6, 0.94)
# Whether each tier casts sun shadows (obj['levi_cast_shadow'], read by
# render.py). The frill tiers do not: the scalloped hems printed scalloped
# bands on the thighs that the sheet does not paint, and an outer tier's
# shadow on the inner one made the petticoat far darker than the sheet (side
# / back shade 0.61 / 0.60 with it, 0.49 / 0.48 without; sheet 0.44 / 0.38).
# The core still casts, so the contact shadow inside the petticoat stays,
# with a smooth edge.
CAST_TIERS = (False, False, False)
CAST_CORE = True

# Tiers, outermost first. The sheet's bottom outline is a bowl: the outer
# frills (lifted with the skirt's sides) end highest and the tiers further
# in hang lower.
#   name, hem outline (half width, front depth, back depth px, superellipse
#   exponent), lift (x0, x1), top, scallops (= flutes), flute depth px
#   (half the crest-to-valley depth at the hem), scallop rise px, seed,
#   bowl lift px (the tier's lowest hem stays this far above the bowl)
# top: ('free', height px, size of the top ring relative to the hem outline)
# for the outer tier, whose top is hidden under the skirt and over the core;
# ('core', px above the core's lower edge) for the inner tiers, sewn onto the
# core cone (the inner the tier, the lower): from below every tier reads as
# one continuous gathered panel nested inside the one around it. The inner
# tier hangs from the core's lower edge (the core mesh ends at its seam).
# Scallops: about 1.5-1.7 cm each at the built hem (the outer tier's hem
# runs ~1.8 m round, the inner ~1.35 m).
# Lift: under the middle of the skirt, front and back, the sheet shows the
# legs from the skirt hem down, so within x0 px of the midline (front view)
# a tier's hem rises to its lift row (front, back), behind the skirt's centre
# hem, easing back to the measured bowl by x1: lift = (x0, x1, front row, back
# row). Round 11: the lift is gentler and wider (the stacked frills stay in
# order, the inner the lower, and show under the skirt's raised centre front
# as the sheet's bells do): the inner tiers' bowl lies ~4 cm lower in front,
# and lifting them 4-6 cm over 3.5 cm of hem drew a steep staircase of
# scallops (a feathered wedge from the side).
TIERS = (
    ('petticoat_tier0', (HALF_W, FRONT_D, BACK_D, 2.0), (40, 110, 600, 586), ('free', 52, 0.86),
     116, 2.5, 4.2, 1, 12.0),
    ('petticoat_tier1', (0.87 * HALF_W, 0.87 * FRONT_D, 0.87 * BACK_D, 2.1), (40, 110, 603, 588), ('core', 22),
     100, 2.3, 4.0, 2, 6.0),
    ('petticoat_tier2', (0.83 * HALF_W, 0.83 * FRONT_D, 0.83 * BACK_D, 2.2), (40, 110, 606, 590), ('core', 0),
     84, 2.1, 3.8, 3, 0.0),
)
# Exposure (round 6): the tiers show as rounded frill clusters under the
# skirt's raised arches, and as a narrower band under its lobes (see
# cluster_rows()). Per tier, px of frill hanging below the skirt's built hem
# at an arch and under a lobe's crest (negative: tucked up behind it), each
# as (sides, front, back). The sheet shows a deep frill band front and back
# and mostly leg under the sides; each tier further in shows as another,
# lower layer of the stack.
EXPOSE = ((18.0, 70.0, 52.0), (28.0, 80.0, 62.0), (38.0, 90.0, 72.0))
EXPOSE_LOBE = ((2.0, 42.0, 30.0), (10.0, 50.0, 38.0), (18.0, 58.0, 46.0))
# Fold position |u| (0 crest, 1 arch) over which a cluster grows from its
# lobe exposure to its full arch exposure, per tier; a cosine ease, so the
# cluster's sides run round into the skirt's hem instead of ending in a
# vertical edge.
CLUSTER_U = ((0.25, 0.95), (0.18, 0.92), (0.12, 0.90))
# front / back weight: 1 within FRONT_DEG[1] deg of the front (back) centre,
# easing (smoothstep) to 0 at FRONT_DEG[0], a broad ramp so the exposure does
# not change abruptly round the quarters
FRONT_DEG = (68.0, 8.0)
CLUSTER_SMIN = 3.0     # softness (px) of the min of the bowl and the clusters
SMIN_FINE = 1.0        # softness of the later mins (smoothed vs raw hem, seam vs hem): each smooth
                       # min sits up to k*ln2 above both arguments, so chained ones stay tight
CLUSTER_SMOOTH = 1.2   # the hem row is smoothed along the hem (sigma, in units of 12 samples)
CLUSTER_SLOPE = 0.55   # ... then rises at most this many px per px along the band
BAND_GUARD = 12.0      # hard floor on the seam-to-hem length (px), should BAND_MIN not be met
BAND_MIN = 34.0        # a tier's seam stays at least this many px above its hem: where the
                       # hem tucks up the seam rises with it (hidden inside the skirt), so
                       # the band never hangs as a long panel below a raised hem
CLEAR = 4.0            # px inside the skirt's inner surface
CLEAR_SOFT = 1.0       # softness of that limit (px)
CLEAR_HOLD = 4.0       # below the skirt's edge the limit holds for this many px,
CLEAR_RELAX = 0.15     # then relaxes this many px per px (the cloth below hangs
CLEAR_FADE = 90.0      # nearly straight, not flaring out), and ends this many px down
# An inner tier stays TIER_CLEAR px inside the tiers around it (their built
# meshes: the flute valleys and the rolled hem count); below an outer tier's
# edge the limit holds, then relaxes and ends as CLEAR_* do, over a shorter
# drop (the frill below may flare out under the edge above it).
TIER_CLEAR = (2.5, 2.0, 0.5, 30.0, 10.0)   # clear, hold, relax, fade, opening (px)
CORE_RX = L['waist_half_w'] * 1.40   # core top ring round the hips (m)
CORE_RY = 0.065
CORE_CY = L['waist_center_y'] * 0.6
CORE_N = 96            # core columns
CORE_T = (0.0, 0.16, 0.33, 0.5, 0.67, 0.84, 1.0)   # core rings (share of the hip-to-seam drop)
CORE_FOLD = 4          # core columns per gather (the core's own gathers from the hips)
CORE_DEPTH = 4.5       # px, half the crest-to-valley depth of the core's gathers ...
CORE_GROW = 0.35       # ... reached this share down from the hips (smoothstep) ...
CORE_SEAM_FADE = 12.0  # ... and gone this many px above the middle tier's seam (smooth below it)
CORE_TUCK = 16.0       # px the core reaches down inside the outer tier's top edge
# The lifted parts are hidden behind the skirt's long centre lobes, front and
# back; they are also drawn in a little towards the legs (by this fraction at
# the midline, easing out with the lift), so those lobes can hang down and
# tuck in instead of flaring out over the frills.
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


# ---------------------------------------------------------------- clearance
_SEC575 = tuple(float(v) for v in skirt.section(575.0))


def skirt_azimuth(x, y):
    """Skirt azimuth phi (0 = front centre, + toward +X) of the point (x, y) px."""
    X, Yf, Yb = _SEC575
    return math.atan2(x / X, -y / (Yf if y < 0 else Yb))


class _Inner:
    """Radius (px) of a surface's innermost layer along a horizontal ray from
    the body axis, in panel px with z = -row: limit() is the largest radius a
    point at that row may have to stay `clear` px inside it. Below the
    surface's lower edge the limit holds for `hold` px, then relaxes by
    `relax` px per px, and over the last `opening` px before `fade` opens up
    quadratically (by ~200 px over 20 px, so there is no step to the inf
    beyond); above its top edge there is no limit."""

    def __init__(self, verts, polys, clear, hold, relax, fade, opening=20.0):
        self.bvh = BVHTree.FromPolygons(verts, polys)
        self.clear, self.hold, self.relax, self.fade, self.opening = clear, hold, relax, fade, opening

    def _cast(self, d, row):
        hit, _, _, dist = self.bvh.ray_cast(Vector((0.0, 0.0, -row)), d, 1000.0)
        return math.inf if hit is None else dist

    def limit(self, x, y, row):
        d = Vector((x, y, 0.0))
        if d.length < 1e-9:
            return math.inf
        d.normalize()
        for up in np.arange(0.0, self.fade + 0.1, 2.0):
            r = self._cast(d, row - up)
            if math.isfinite(r):
                return (r - self.clear + self.relax * max(0.0, up - self.hold)
                        + 0.5 * max(0.0, up - (self.fade - self.opening)) ** 2)
        return math.inf


def _skirt_inner():
    """The skirt's inner surface: its cloth sheet rebuilt from skirt.profiles()
    with common.loft (as skirt.build() does, in px with z = -row), together
    with its solidify shell (the vertices moved inward along their normals by
    the skirt's thickness); the first hit of either counts."""
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
    return _Inner(verts, polys, CLEAR, CLEAR_HOLD, CLEAR_RELAX, CLEAR_FADE)


def _tier_inner(obj):
    """An outer tier's built mesh as a clearance limit for the tiers inside it."""
    me = obj.data
    verts = [Vector((v.co.x * spec.PX_PER_M, v.co.y * spec.PX_PER_M, -_row(v.co.z))) for v in me.vertices]
    polys = [list(p.vertices) for p in me.polygons]
    return _Inner(verts, polys, *TIER_CLEAR)


def _clamp_ring(loop, inners, margin=None, apply_to=None):
    """Pull a ring of world points radially inside every surface in `inners`
    (the smallest limit, soft minimum). The pull is spread to the neighbouring
    samples (dilated, then smoothed, never below what each sample needs), so
    it has no sharp steps.

    margin: px per sample kept free beyond the clearance (the outward reach
    of the flutes laid on this smooth band); apply_to: rings (a tuple) the
    band's radial scale is applied to instead, returned as a tuple (so the
    clamp moves the whole gathered band in, rather than flattening the
    flutes' crests against the skirt)."""
    n = len(loop)
    pull = np.zeros(n)
    rad = np.zeros(n)
    for i, p in enumerate(loop):
        x, y = p.x * spec.PX_PER_M, p.y * spec.PX_PER_M
        r = math.hypot(x, y)
        rad[i] = r
        row = _row(p.z)
        lim = min(s.limit(x, y, row) for s in inners) - (0.0 if margin is None else margin[i])
        if r < 1e-6 or not math.isfinite(lim):
            continue
        k = CLEAR_SOFT
        d = (r - lim) / k
        if d < -8.0:
            continue
        # soft min(r, lim): -k log(exp(-r/k) + exp(-lim/k))
        rn = lim - k * math.log1p(math.exp(-d)) if d > 0 else r - k * math.log1p(math.exp(d))
        pull[i] = r - rn
    if pull.any():
        wide = np.maximum(np.maximum(pull, np.roll(pull, 1)), np.roll(pull, -1))
        pull = np.maximum(pull, _smooth_loop(wide, 1.0))
    scale = np.where(rad > 1e-6, (rad - pull) / np.maximum(rad, 1e-6), 1.0)

    def scaled(ring):
        return [Vector((p.x * k, p.y * k, p.z)) for p, k in zip(ring, scale)]
    return scaled(loop) if apply_to is None else tuple(scaled(r) for r in apply_to)


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
    The measured bottom outline of each view is the lowest frill point over
    that column, so a hem point should hang no lower than either outline: take
    the higher of the two (a smooth minimum, so there is no crease where they
    cross), then HEM_DROP lower for the scallops. Inner tiers reach the lower
    centre of the bowl-shaped outline, outer tiers its lifted sides. lift =
    (x0, x1, front row, back row) raises the hem near the midline (see TIERS).
    """
    ax = abs(x)
    a, b = _interp(HEM_FRONT, ax), _interp(HEM_SIDE, y)
    row = float(_smin(a, b, HEM_SMIN)) + HEM_DROP
    lift_row = (lift[2] if y < 0 else lift[3]) if lift else math.inf
    if row > lift_row:
        row += (lift_row - row) * (1.0 - _smoothstep(lift[0], lift[1], ax))
    return row


def hem_z(x, y, lift=None):
    """World z of hem_row()."""
    return spec.px_to_z(hem_row(x, y, lift))


def _smin(a, b, k):
    """Smooth minimum of a and b (scalars or arrays, softness k)."""
    return np.minimum(a, b) - k * np.log1p(np.exp(-np.abs(np.subtract(a, b)) / k))


def cluster_rows(folds, idx, xy, rows):
    """Hem rows of tier idx at the hem-outline points xy ((n, 2) px), from
    their untucked (measured bowl + lift) hem rows: the skirt's built hem
    (skirt.hem_terms) plus an exposure that eases (cosine over CLUSTER_U[idx]
    of the skirt fold position) from EXPOSE_LOBE under a lobe's crest to
    EXPOSE under an arch, so each arch frames a rounded frill cluster;
    both blend from the sides to the front and back (FRONT_DEG). Never lower
    than the bowl (smooth min)."""
    phi = np.array([skirt_azimuth(x, y) for x, y in xy])
    _, u = skirt.fold_index(folds, phi)
    here = skirt.hem_terms(folds, phi)[0]
    u0, u1 = CLUSTER_U[idx]
    e = np.clip((np.abs(u) - u0) / (u1 - u0), 0.0, 1.0)
    e = 0.5 - 0.5 * np.cos(np.pi * e)
    off = np.abs(np.degrees(np.arctan2(np.sin(phi), np.cos(phi))))   # 0 front .. 180 back

    def ramp(v):
        t = np.clip((v - FRONT_DEG[0]) / (FRONT_DEG[1] - FRONT_DEG[0]), 0.0, 1.0)
        return t * t * (3 - 2 * t)
    wf, wb = ramp(off), ramp(180.0 - off)

    def blend(v):
        return v[0] + (v[1] - v[0]) * wf + (v[2] - v[0]) * wb
    lobe, trough = blend(EXPOSE_LOBE[idx]), blend(EXPOSE[idx])
    return _smin(np.asarray(rows, dtype=np.float64), here + lobe + (trough - lobe) * e, CLUSTER_SMIN)


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


def _lift_pinch(x, lift):
    """Radial scale of the hem outline point at x px (see LIFT_PINCH)."""
    return 1.0 - LIFT_PINCH * (1.0 - _smoothstep(lift[0], lift[1], abs(x)))


# ---------------------------------------------------------------- core
# The outer tier's seam height (world z) by ellipse angle, (angles, z) sorted,
# set by build() once the outer tier is built (its seam rises where its hem
# tucks up); the core cone ends CORE_TUCK px below it. _SEAM1 / _SEAM2: the
# middle tier's seam on the core (the core's gathers have faded out above
# it) and the inner tier's, where the core mesh ends.
_SEAM0 = None
_SEAM1 = None
_SEAM2 = None


def _ellipse_angle(x, y):
    w, fd, bd = TIERS[0][1][:3]
    return math.atan2(y / (fd if y < 0 else bd), x / w)


def _core_bottom(phi):
    """(x, y, z) world point of the core cone's lower edge at ellipse angle phi."""
    _, dims0, lift0, (_, height0, top0) = TIERS[0][:4]
    c, s = math.cos(phi), math.sin(phi)
    hx, hy = dims0[0] * c, (dims0[1] if s < 0 else dims0[2]) * s
    # a few px below the outer tier's top edge (untucked, until it is built)
    if _SEAM0 is None:
        z = hem_z(hx, hy, lift0) + height0 * PX
    else:
        z = float(np.interp(phi, _SEAM0[0], _SEAM0[1], period=2 * math.pi))
    z -= CORE_TUCK * PX
    k = top0 * 0.97 * _lift_pinch(hx, lift0) * PX
    return Vector((k * hx, k * hy, z))


def _core_top(phi):
    """(x, y, z) world point of the core's top ring (round the hips) at angle phi."""
    return Vector((CORE_RX * math.cos(phi), CORE_CY + CORE_RY * math.sin(phi), L['hip_z']))


def _core_point(x, y, up_px):
    """Point on the core cone up_px above its lower edge, in the direction of
    the hem outline point (x, y) px."""
    phi = _ellipse_angle(x, y)
    b, t = _core_bottom(phi), _core_top(phi)
    return b.lerp(t, min(1.0, up_px * PX / (t.z - b.z)))


# ---------------------------------------------------------------- tiers
def _bells(count, seed):
    """Flute index ranges [a, b) of the bells: runs of BELL_SIZE flutes (the
    size picked per bell), the last one taking the remainder."""
    out, a, k = [], 0, 0
    while count - a >= 2 * BELL_SIZE[0]:
        n = BELL_SIZE[0] + int(_hash(k, seed + 11) * (BELL_SIZE[1] - BELL_SIZE[0] + 1))
        n = min(n, count - a - BELL_SIZE[0])
        out.append((a, a + n))
        a, k = a + n, k + 1
    out.append((a, count))
    return out


def _gathers(count, seed, off):
    """Arc-length fractions of the samples round a tier (SPF per flute, the
    flutes unevenly wide), each sample's phase in its flute (0 = notch over
    the pleat, 0.5 = crest), flute index, and phase in its bell (0 at the
    bell's edge, a notch, 0.5 mid-bell)."""
    w = [1.0 + WIDTH_VAR * (2 * _hash(k, seed + 3) - 1) for k in range(count)]
    total = sum(w)
    pos = np.concatenate([[0.0], np.cumsum(w)])
    fracs, phase, fold, bell = [], [], [], []
    start = off * total / count
    for a, b in _bells(count, seed):
        for k in range(a, b):
            for fp in PHASES:
                fracs.append((start + pos[k] + fp * w[k]) / total)
                phase.append(fp)
                fold.append(k)
                bell.append((pos[k] + fp * w[k] - pos[a]) / (pos[b] - pos[a]))
    return fracs, phase, fold, bell


def _level(hems, phase):
    """The hem heights with each scallop levelled (LEVEL of the way) about its
    own middle, the notches between at the mean of their two neighbours: on a
    sloping hem (a cluster's side, the lifted midline) the scallops then step
    down as round lobes instead of tilting into a sawtooth of points."""
    h = np.asarray(hems, dtype=np.float64)
    mid = SPF // 2
    c = h[mid::SPF]
    lev = np.repeat(c, SPF)
    lev[::SPF] = 0.5 * (c + np.roll(c, 1))
    return list(h + LEVEL * (lev - h))


def _per_fold(count, seed, fold):
    """Per-sample factor 1 +- DEPTH_VAR, one value per flute, blended smoothly
    over neighbouring flutes so the depth never steps at a notch."""
    raw = [1.0 + DEPTH_VAR * (2 * _hash(k, seed) - 1) for k in fold]
    return _smooth_loop(raw, VAR_SMOOTH * SPF)


def _puff(phase):
    """Flute cross-section, -1 at the pleat (phase 0) to +1 at the crest (0.5):
    a round puff with a pinched pleat."""
    return 2.0 * math.sin(math.pi * phase) ** PUFF_P - 1.0


def _tier(idx, inners, folds, name, shape, lift, top, count, depth_px, rise_px, seed, bowl_up):
    """The tier's rings (with the flutes and scallops, and the same rings
    without them, for the shading normals), each ending in the hem roll, and
    its seam ring (the top of the band)."""
    fracs, phase, fold, bell = _gathers(count, seed, 0.5 * (idx % 2))
    bell_depth, bell_rise = BELL[idx]
    outline, total = _outline(shape, fracs)
    # hem outline, drawn in near the lifted midline
    hem = [((bx * k, by * k), nrm) for (bx, by), nrm in outline for k in (_lift_pinch(bx, lift),)]
    # the hem: measured bowl + lift (less the tier's bowl lift), raised into
    # the frill clusters under the skirt (cluster_rows), smoothed along the
    # band and its rise limited to CLUSTER_SLOPE (raise-only, so the hem
    # never sags below a lobe), then smoothed once more; never below the raw
    # clusters ramped in at the same slope (a soft min, so no crease where it
    # takes over), so no sliver shows under the skirt's lobes or past the lift
    # row
    full = [hem_z(ox, oy, lift) for (ox, oy), _ in outline]
    arc = [(f - fracs[0]) * total for f in fracs] + [total]
    raw = cluster_rows(folds, idx, [p for p, _ in outline],
                       [hem_row(ox, oy, lift) - bowl_up for (ox, oy), _ in outline])
    k12 = 12.0     # the smoothing widths were set for 12 samples per (old) fold
    rows = _limit_slope(_smooth_loop(raw, CLUSTER_SMOOTH * k12), arc, CLUSTER_SLOPE)
    rows = _smin(_smooth_loop(rows, 0.5 * k12), _limit_slope(raw, arc, CLUSTER_SLOPE), SMIN_FINE)
    hems = [spec.px_to_z(r) for r in rows]

    # top ring: free (above the untucked hem, scaled) or sewn onto the core;
    # either way at least BAND_MIN above the hem (smooth min): where the hem
    # tucks up the seam rises with it, inside the skirt, so the band keeps its
    # length and flare instead of hanging as a long panel or folding flat
    def seam_up(top_row, hem_r):
        return top_row - float(_smin(top_row, hem_r - BAND_MIN, SMIN_FINE))
    if top[0] == 'free':
        tops = []
        for ((bx, by), _), ((ox, oy), _), r in zip(hem, outline, rows):
            z = hem_z(ox, oy, lift) + top[1] * PX
            tops.append(Vector((top[2] * bx * PX, top[2] * by * PX, z + seam_up(_row(z), r) * PX)))
    else:
        tops = []
        for ((bx, by), _), r in zip(hem, rows):
            t = _core_point(bx, by, top[1])
            tops.append(_core_point(bx, by, top[1] + seam_up(_row(t.z), r)))
    # a seam sewn onto the core cannot rise past the core's top ring; never let
    # the band get shorter than BAND_GUARD there (nor turn inside out)
    hems = [min(h, t.z - BAND_GUARD * PX) for h, t in zip(hems, tops)]
    hems = _level(hems, phase)
    amp = _per_fold(count, seed + 7, fold)
    rise = _per_fold(count, seed + 29, fold)
    # fabric per flute: a band shortened by the tuck folds less deeply
    short = [min(1.0, max(0.0, (t.z - h) / max(t.z - f, 1e-6))) ** SHORT_POW
             for t, h, f in zip(tops, hems, full)]
    puff = [_puff(p) for p in phase]
    # the bells: a wider cosine fold (crest mid-bell) whose edges rise
    bwave = [-math.cos(2 * math.pi * b) for b in bell]
    bnotch = [(0.5 + 0.5 * math.cos(2 * math.pi * b)) ** BELL_P for b in bell]
    bamp = _per_fold(count, seed + 41, fold)
    notch = [1.0 - (1.0 - (1.0 - 2.0 * min(p, 1.0 - p)) ** 2) ** ROUND for p in phase]
    out = {1.0: [], 0.0: []}
    for s in PROFILE:
        loops, band, reach, breach = {1.0: [], 0.0: []}, [], [], []
        ramp = min(1.0, s / SEAM_RAMP)
        ramp = ramp * ramp * (3 - 2 * ramp)
        mouth = MOUTH * _smoothstep(MOUTH_S, 1.0, s)
        for i, ((bx, by), (nx, ny)) in enumerate(hem):
            t = tops[i]
            z = t.z + s * (hems[i] - t.z)
            # where on the full seam-to-hem drop this height lies
            d = min(1.0, max(0.0, (t.z - z) / max(t.z - full[i], 1e-6)))
            g = 1.0 - (1.0 - d) ** FLARE_POW
            belly = 1.0 + BELLY * math.sin(math.pi * d)
            # the seam ring itself lies on its support (the core cone)
            grow = (SEAM_FOLD + (1.0 - SEAM_FOLD) * d ** FOLD_POW) * ramp
            fgrow = (FLUTE_SEAM + (1.0 - FLUTE_SEAM) * d ** FLUTE_POW) * ramp
            reach.append(depth_px * amp[i] * short[i] * fgrow)
            breach.append(bell_depth * bamp[i] * short[i] * grow)
            bx0 = t.x + (belly * bx * PX - t.x) * g + nx * mouth * PX
            by0 = t.y + (belly * by * PX - t.y) * g + ny * mouth * PX
            band.append(Vector((bx0, by0, z)))
            rs = s ** RISE_POW * PX
            for k in (1.0, 0.0):
                # the soft rings (k = 0, for the shading normals) keep the bells
                gather = k * puff[i] * reach[-1] + bwave[i] * breach[-1]
                zk = z + k * rise_px * rise[i] * notch[i] * rs + bell_rise * bamp[i] * bnotch[i] * rs
                loops[k].append(Vector((bx0 + nx * gather * PX, by0 + ny * gather * PX, zk)))
        # the clamp keeps the smooth band clear + the flutes' reach inside the
        # skirt (and the outer tiers) and moves the fluted ring with it, so the
        # flutes keep their full depth instead of being flattened against them
        gathered, smooth = _clamp_ring(band, inners, [a + b for a, b in zip(reach, breach)],
                                       apply_to=(loops[1.0], loops[0.0]))
        out[1.0].append(gathered)
        out[0.0].append(smooth)
    # the upper band (under the seam, where the gathered rings are smallest
    # and the flutes shallow) keeps every second sample (_mesh joins it)
    rings = tuple([ring[::2] if s < COARSE_S else ring for s, ring in zip(PROFILE, r)]
                  + _hem_roll(r[-2], r[-1]) for r in (out[1.0], out[0.0]))
    # the seam height by ellipse angle (sorted)
    seam = sorted((_ellipse_angle(bx, by), t.z) for ((bx, by), _), t in zip(hem, tops))
    return rings, (np.array([a for a, _ in seam]), np.array([z for _, z in seam])), hem


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


def _line_weights(nbands):
    """Outline weight per ring of a tier (PROFILE rings, then the hem roll)."""
    w = [_smoothstep(LINE_S[0], LINE_S[1], s) for s in PROFILE]
    return w + [1.0] * (nbands - len(PROFILE))


# ---------------------------------------------------------------- meshes
def _mesh(rings):
    """BMesh of the closed rings, a loft; where a ring has twice the samples
    of the one above it, each upper edge fans into two (a triangle and a
    quad), sample 2j below sample j."""
    bm = bmesh.new()
    vs = [[bm.verts.new(p) for p in r] for r in rings]
    for up, lo in zip(vs, vs[1:]):
        n, m = len(up), len(lo)
        for j in range(n):
            k = (j + 1) % n
            if m == n:
                bm.faces.new((up[j], up[k], lo[k], lo[j]))
            else:
                assert m == 2 * n, (n, m)
                bm.faces.new((up[j], lo[2 * j + 1], lo[2 * j]))
                bm.faces.new((up[j], up[k], lo[(2 * j + 2) % m], lo[2 * j + 1]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def _outward(bm):
    """bm with its faces turned to point away from the body axis (area
    weighted), since recalc_face_normals is ambiguous on an open tube."""
    out = sum(f.normal.dot(Vector((c.x, c.y, 0.0))) * f.calc_area()
              for f in bm.faces for c in (f.calc_center_median(),))
    if out < 0.0:
        bmesh.ops.reverse_faces(bm, faces=list(bm.faces))
    return bm


def _finish(col, mat, name, loops, soft, line):
    """Loft the rings into a cloth object with an outline.

    recalc_face_normals is ambiguous on an open tube, so orientation is set
    explicitly: faces point OUTWARD (away from the body axis) on the main
    sheet, so the outline hull sits on the outside of the hem and draws a
    line along every scallop; the hull's backface culling keeps it off the
    fill. The turned-under return then faces the axis, as the inside of a
    thin cloth should. Smooth shading throughout: the rolled hem turns in
    90 degree steps and must not split normals.

    soft: the same rings without the flutes. The shading normals are then
    blended from the fluted surface's (FOLD_SHADE) and the smooth band's,
    so the flutes shade softly: their flanks stay lit instead of breaking
    into small shade wedges where they peek out under the skirt, while
    the form, silhouette and outline keep the full flutes.

    line: outline weight per ring, see LINE_*.
    """
    bm = _outward(_mesh(loops))
    obj = common.new_object(col, name, bm, [mat])
    common.shade_smooth(obj, 180.0)
    sb = _outward(_mesh(soft))
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
    vg = obj.vertex_groups.new(name=LINE_VG)
    i0 = 0
    for w, n in zip(line, [len(r) for r in loops]):
        vg.add(list(range(i0, i0 + n)), w, 'REPLACE')
        i0 += n
    common.add_outline(obj, vertex_group=LINE_VG, min_factor=LINE_MIN)
    return obj


def _core(col, mat, inners):
    """The core: a cone from the hips (CORE_RX / CORE_RY ring) down its
    straight generators to the lower edge the outer tier's seam sets
    (_core_bottom) or, above it, the inner tier's seam (_SEAM2), CORE_N
    columns, CORE_T rings. Gathers (CORE_FOLD columns
    each) open from the hips and fade out above the middle tier's seam, so
    the tiers sewn on below lie on a smooth cone. It is its own object: merged
    with the inner tier's dense frill, the rig smoothed its long, sparse edges
    hardly at all (rig._diffuse scales by the object's median edge) and the
    hip ring stretched x3.4 in high_kick."""
    n = CORE_N
    nf = n // CORE_FOLD
    phis = [2 * math.pi * i / n for i in range(n)]
    tops, bots = [_core_top(p) for p in phis], []
    for p, t in zip(phis, tops):
        # down the cone's generator to the inner tier's seam (which rises
        # where that tier's hem tucks up), so the core never runs on below it
        b = _core_bottom(p)
        z2 = float(np.interp(p, _SEAM2[0], _SEAM2[1], period=2 * math.pi))
        bots.append(t.lerp(b, min(1.0, (t.z - z2) / max(t.z - b.z, 1e-9))))
    z1 = [float(np.interp(p, _SEAM1[0], _SEAM1[1], period=2 * math.pi)) * spec.PX_PER_M for p in phis]
    out = {1.0: [], 0.0: []}
    for t in CORE_T:
        band, reach, loops = [], [], {1.0: [], 0.0: []}
        for j in range(n):
            p = tops[j].lerp(bots[j], t)
            g = _smoothstep(0.0, CORE_GROW, t) * _smoothstep(z1[j] + CORE_SEAM_FADE, z1[j] + 2 * CORE_SEAM_FADE,
                                                             p.z * spec.PX_PER_M)
            reach.append(CORE_DEPTH * g)
            band.append(p)
            r = Vector((p.x, p.y - CORE_CY, 0.0))
            r = r.normalized() if r.length > 1e-9 else Vector((1.0, 0.0, 0.0))
            wave = math.cos(2 * math.pi * j * nf / n)
            for k in (1.0, 0.0):
                loops[k].append(p + r * (k * wave * reach[-1] * PX))
        gathered, smooth = _clamp_ring(band, inners, reach, apply_to=(loops[1.0], loops[0.0]))
        out[1.0].append(gathered)
        out[0.0].append(smooth)
    obj = _finish(col, mat, 'petticoat_core', out[1.0], out[0.0], [0.0] * len(CORE_T))
    obj['levi_cast_shadow'] = CAST_CORE
    return obj


def build(col):
    global _SEAM0, _SEAM1, _SEAM2
    skirt_in = _skirt_inner()
    folds = skirt.fold_table()
    mat = common.toon_material('petticoat')
    _SEAM0 = _SEAM1 = _SEAM2 = None
    # the outer tier first: the core ends just inside its seam; the inner
    # tiers are sewn onto the core, each inside the tiers around it
    inners = [skirt_in]
    for idx, tier in enumerate(TIERS):
        (gathered, smooth), seam, _ = _tier(idx, inners, folds, *tier)
        if idx == 0:
            _SEAM0 = seam
        if idx == 1:
            _SEAM1 = seam
        if idx == 2:
            _SEAM2 = seam
        obj = _finish(col, mat, tier[0], gathered, smooth, _line_weights(len(gathered)))
        obj['levi_cast_shadow'] = CAST_TIERS[idx]
        inners = inners + [_tier_inner(obj)]
    _core(col, mat, [skirt_in])
