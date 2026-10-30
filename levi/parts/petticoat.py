"""Petticoat: three tiers of peach-pink scalloped bells below the skirt hem.

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
                   frill's bells into the core's gathers instead of a smooth
                   pink cone.

The sheet (ref/front|side|back.png) and the art (ref/setting.png,
ref/illustration.png) draw two or three stacked layers of bells under the
skirt's raised arches: each bell a puffed tube 4-7 cm wide, pinched where it
meets the next, whose level mouth ends in 2-4 round lobes (~2 cm), the bells
of the layers inside hanging below the outer ones. Round 11 builds that
(rounds 6-10 had two tiers of 6-7.5 cm folds that read as plain bands):

- Layout: every tier has the same NLOBES lobes (SPF samples across each) in
  bells of BELL_LOBES lobes, at the same azimuths on all three tiers
  (_layout), so the bells of the tiers stack and nest: an inner bell's crest
  lies under the outer bell's crest, its pinch under the outer pinch.
- Bell: across a bell the cloth bulges as a puffed tube, 2 sin(pi b) **
  BELL_Q - 1 (BELL_R, blurred so the pinch between two bells has a ~2.5 mm
  radius instead of a crease), BELL px deep at the hem and SEAM_FOLD of that
  just under the seam (the bells are gathered into the seam). The mouth
  flares (MOUTH, at the crest) and is level: the hem of each bell is levelled
  to the bell's mean height (_level_bells), and the pinch between two bells
  rises (BELL rise, ((1 + cos 2 pi b) / 2) ** BELL_P), so a sloping hem
  becomes a staircase of level bell mouths, as on the sheet, instead of rows
  of tilted scallops (round 11's first try: tongues and claws from the side).
- Lobes: each lobe is a small round puff across (LOBE_R, blurred) that opens
  only near the hem (FLUTE_SEAM, FLUTE_POW), and its hem a round scallop
  whose notch rises over the pleat (LOBE_Z, the cusp blurred, NOTCH_BLUR).
  The edge rolls under in a half circle (HEM_ROLL px, ROLL_DEG, its frame
  smoothed along the hem) and runs a little way back up inside (RET_UP), so
  every lobe has real thickness and the outline hull draws its edge.
- Profile: each tier is one surface, radius(azimuth, height), flaring out
  under the seam (inside the skirt) and hanging nearly straight lower down
  (1 - (1 - d) ** FLARE_POW of the full seam-to-hem drop d). Where the hem
  is tucked up under the skirt, the band ends higher on the same surface (it
  gets shorter, and its bells shallower: SHORT_POW). PROFILE rings (closer
  towards the hem) let the skirt chains bend it smoothly.
- Shading: the lobes' shading normals are blended towards the bells' (the
  same rings without the lobes, FOLD_SHADE), so lobe flanks peeking out under
  the skirt do not break into small shade wedges; the geometry, silhouette
  and outline keep the lobes. The outline hull is full width only at the
  scalloped edge (LINE_*): the bells' own silhouettes up the band, which
  stand for the art's thin pleat lines, and the core draw thinner lines.

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
tiers around it (their built meshes), the gathered surface's own offset
included. Below an outer layer's edge the limit relaxes gradually instead of
switching off, and the inward pull is spread along each ring (_clamp_ring),
so the clamp leaves no sharp radial steps. The clamp measures along a
horizontal ray from the body axis; a second pass (_push3d) then keeps the
nearest-point (3D) distance to every layer outside at least *_CLEAR3, where
a bell's steep flank or a skirt trough lies closer than the ray says.

The pink band's bottom outline is a bowl, lowest at the centre and rising
towards the sides (and higher at the back than the front in the side view).
It was measured on ref/{front,side,back}.png (panel rows, HEM_FRONT /
HEM_SIDE) instead of using the single spec.L['petticoat_hem_z'] landmark,
which only gives one height.

Shadows: see CAST_TIERS / CAST_CORE (render.py reads obj['levi_cast_shadow']).

Rigging: the rig weights every skirt-family layer by angle x height to the
skirt chains, which follow the thighs (levi/rig.py); the tiers' weights are
blended toward each other where they lie within ~1 cm (rig.LAYER_PARTS), so
the nested tiers move together.
Every tier wraps round both legs, well clear of them; none passes between
the thighs.

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

# ---------------------------------------------------------------- layout
DENSE = 1440      # samples of the dense hem outline (arc-length resampling)
NLOBES = 96       # lobes (scallops) round every tier: ~2.3 / 2.0 / 1.9 cm at the hems
# Samples across one lobe (phase: notch over the pleat at 0, crest at 0.5),
# evenly spaced: the rig smooths weights per vertex step, so samples bunched
# beside a notch take a wider step's whole weight gradient (round 11 trial:
# x2.5-2.7 in sit_chair / high_kick).
SPF = 8
BELL_LOBES = (3, 4)   # lobes per bell (the last bell takes the remainder, at least 2)
BELL4 = 0.3           # share of the bells with BELL_LOBES[1] lobes
WIDTH_VAR = 0.12      # lobe width irregularity (share of the mean width, +-)
DEPTH_VAR = 0.25      # lobe depth / rise irregularity
VAR_SMOOTH = 0.7      # per-lobe values blended over this many lobes (sigma)
BELL_VAR = 0.18       # bell depth / rise irregularity (one value per bell, shared by the tiers)
BELL_SMOOTH = 0.35    # ... blended over this many bells (sigma), so a pinch never steps

# ---------------------------------------------------------------- cross-sections
# Periodic tables over one lobe / one bell, Gaussian-blurred (sigma as a share
# of the period) so that every pinch, pleat and notch has a radius: a V crease
# drew a thorn of outline above every notch and folded over in a pose (round
# 11's first try: dihedrals of 130-144 deg, new flips at the back hem).
TAB_N = 2048
LOBE_P = 0.9          # lobe across: 2 sin(pi p) ** LOBE_P - 1, a round puff, a soft pleat
LOBE_BLUR = 0.1       # (about one sample: the pleat is a U, not a V)
ROUND = 0.65          # lobe rise 1 - (1 - x ** 2) ** ROUND, x = 1 at the notch .. 0 mid-lobe
NOTCH_BLUR = 0.05     # rounds the notch's cusp (~1.1 mm)
BELL_Q = 0.5          # bell across: 2 sin(pi b) ** BELL_Q - 1, a puffed tube with a pinch
BELL_BLUR = 0.07      # the pinch's radius (~5 mm on the outer tier, about two samples)
BELL_P = 3.0          # bell edge rise ((1 + cos 2 pi b) / 2) ** BELL_P: the mouth is round, its
                      # lowest lobes mid-bell, and turns up into the pinch
BELL_EDGE = 0.16      # share of a bell over which its levelled hem hands over to the next
PINCH_NOTCH = 0.8     # share of the lobe notch taken out at a pinch (the bell's rise is the notch there)
LEVEL = 1.0           # share of the hem levelled per bell (_level_bells)

# ---------------------------------------------------------------- band
SEAM_FOLD = 0.35  # share of the bell depth just below the seam (gathered: the bells run up the band)
SEAM_RAMP = 0.25  # ... reached over this share of the band from the seam (smoothstep), so the
                  # gathers open continuously out of the seam (no step at the first ring)
FOLD_POW = 0.6    # the bells open as d ** FOLD_POW down the band
# The lobes stay shallow up the band and open in the frill near the hem
# (FLUTE_SEAM of their depth at the seam, then d ** FLUTE_POW).
FLUTE_SEAM = 0.1
FLUTE_POW = 1.8
RISE_POW = 2.0    # the notches rise as s ** RISE_POW down the band (the pleat curves into them)
# Rings above this share of the band keep every second sample: the gathered
# rings under the seam are the smallest, and the rig's weights (smoothed and
# pruned per vertex step) switched bones over a few of them; the lobes are
# shallow there anyway.
COARSE_S = 0.35
# Where the hem is tucked up, the band is shorter and has less fabric to
# fold: the bell and lobe depths scale with (band length / full length) ** SHORT_POW.
SHORT_POW = 0.15
# The band flares out from its seam as 1 - (1 - d) ** FLARE_POW of the full
# drop d: most of the flare happens high up, inside the skirt, and the
# exposed lower band hangs nearly straight, turning gradually (no shelf).
FLARE_POW = 1.35
# ... and down the band itself the flare is spent as 1 - (1 - s) ** HANG_POW of
# what the band reaches at its hem: a band shortened by the tuck (the lifted
# front and back) flares under the skirt and still hangs straight where it
# shows, instead of standing out as a slanted blade seen from the side.
HANG_POW = 2.2
BELLY = 0.006     # how far the band bellies out between seam and hem (x hem outline)
MOUTH = 4.0       # px each bell's mouth flares out at its crest (none at the pinch) ...
MOUTH_S = 0.55    # ... growing (smoothstep) from this share of the band to the hem
HEM_ROLL = 0.6    # px radius of the rolled hem
RET_UP = 2.0      # px the turned-under hem runs back up inside ...
RET_MAX = 0.7     # ... at most this share of the last band segment
ROLL_SMOOTH = 2   # the roll's frame is averaged over +-this many samples (no twist at a notch)
ROLL_RADIAL = 1.0 # ... and its normal blended this much towards the radial direction
HEM_SMIN = 2.0    # softness (px) of the min of the front and side outlines
# The hem line hangs this far below the measured outline: the lobes' notches
# and the pinches rise above it, so on average the bottom edge meets the outline.
HEM_DROP = 6.0
# Profile rings from the seam (0) to the hem (1), denser where the band
# turns from sloping to hanging and where the lobes form.
PROFILE = (0.0, 0.16, 0.32, 0.46, 0.59, 0.70, 0.80, 0.88, 0.945, 1.0)
# Share of the gathered surface's normal in the shading normals (the rest is
# the bells' alone, without the lobes; see _finish), on the band and on the
# turned-under hem roll (whose inner faces and returns showed slivers).
FOLD_SHADE = 0.62
FOLD_SHADE_ROLL = 0.45
# Hem roll: angles (deg) of the rings round the half circle under the edge.
ROLL_DEG = (90.0, 180.0)
# Outline hull: full width at the scalloped edge, LINE_MIN of it up the band
# (the bells' silhouettes there are the art's pleat lines) and on the core;
# the weight eases in from LINE_S of the band down.
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
#   exponent), lift (x0, x1, front row, back row), top, lobe depth px (half
#   the crest-to-valley depth at the hem), lobe rise px, bell depth px (half
#   crest-to-pinch), bell rise px (the pinch above the mouth), seed, bowl
#   lift px (the tier's lowest hem stays this far above the bowl)
# top: ('free', height px, size of the top ring relative to the hem outline)
# for the outer tier, whose top is hidden under the skirt and over the core;
# ('core', px above the core's lower edge) for the inner tiers, sewn onto the
# core cone (the inner the tier, the lower): from below every tier reads as
# one continuous gathered panel nested inside the one around it. The inner
# tier hangs from the core's lower edge (the core mesh ends at its seam).
# Lift: under the middle of the skirt, front and back, the sheet shows the
# legs from the skirt hem down, so within x0 px of the midline (front view)
# a tier's hem rises to its lift row, behind the skirt's centre hem, easing
# back to the measured bowl by x1 (round 11: over a wide ramp, so the bells
# step up gently instead of standing as a steep wedge seen from the side).
TIERS = (
    ('petticoat_tier0', (HALF_W, FRONT_D, BACK_D, 2.0), (40, 160, 600, 586), ('free', 52, 0.95),
     1.8, 5.0, 9.0, 11.0, 1, 12.0),
    ('petticoat_tier1', (0.87 * HALF_W, 0.87 * FRONT_D, 0.87 * BACK_D, 2.1), (40, 160, 596, 582), ('core', 22),
     1.7, 4.7, 8.5, 10.0, 2, 6.0),
    ('petticoat_tier2', (0.83 * HALF_W, 0.83 * FRONT_D, 0.83 * BACK_D, 2.2), (40, 160, 593, 579), ('core', 0),
     1.6, 4.4, 8.0, 9.0, 3, 0.0),
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
CLUSTER_SLOPE = 0.4    # ... then rises at most this many px per px along the band
BAND_GUARD = 12.0      # hard floor on the seam-to-hem length (px), should BAND_MIN not be met
BAND_MIN = 34.0        # a tier's seam stays at least this many px above its hem: where the
                       # hem tucks up the seam rises with it (hidden inside the skirt), so
                       # the band never hangs as a long panel below a raised hem
CLEAR = 4.0            # px inside the skirt's inner surface (along the ray)
CLEAR3 = 2.7           # px nearest-point distance to the skirt (_push3d)
CLEAR_SOFT = 1.0       # softness of that limit (px)
CLEAR_HOLD = 4.0       # below the skirt's edge the limit holds for this many px,
CLEAR_RELAX = 0.15     # then relaxes this many px per px (the cloth below hangs
CLEAR_FADE = 90.0      # nearly straight, not flaring out), and ends this many px down
# An inner tier stays TIER_CLEAR px inside the tiers around it (their built
# meshes: the bell pinches and the rolled hem count); below an outer tier's
# edge the limit holds, then relaxes and ends as CLEAR_* do, over a shorter
# drop (the frill below may flare out under the edge above it).
TIER_CLEAR = (2.5, 2.0, 0.5, 30.0, 10.0)   # clear, hold, relax, fade, opening (px)
TIER_CLEAR3 = 2.6      # px nearest-point distance to the tiers around it (_push3d)
PUSH_MIN_COS = 0.35    # a push along the ray counts at least this share against a sloping wall
CORE_RX = L['waist_half_w'] * 1.40   # core top ring round the hips (m)
CORE_RY = 0.065
CORE_BOTTOM = 0.834    # the core cone's lower edge, relative to the outer tier's hem outline
CORE_CY = L['waist_center_y'] * 0.6
CORE_N = 96            # core columns
CORE_SIDE_P = 4        # the core's lower edge follows the inner tier's built seam by cos(angle) ** this
                       # (1 at the sides, ~0 front and back; see _core)
# core rings (share of the hip-to-seam drop). Round 11 tried 10 (closer towards
# the lower edge) and 192 columns: every extra ring or column sampled the
# 4-bone prune's switch between neighbouring skirt chains on a long edge
# (core x2.8-3.5 in high_kick, x3.2 in sit_chair); with 7 rings and 96 columns
# the core stays at or below round 10's stretch (high_kick 2.0, cross_legged
# 2.1, lie_back 1.9)
CORE_T = (0.0, 0.16, 0.33, 0.5, 0.67, 0.84, 1.0)
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
# Under the lift the bells are shallower (by this share at the midline, easing
# out with the lift): there the frill hides behind the skirt's centre lobe in
# the front and back views (the sheet shows legs there), and seen from the
# side its bells, edge-on and stepping up towards the midline, drew a fan of
# thin blades.
LIFT_BELL = 0.75


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


# ---------------------------------------------------------------- cross-section tables
def _table(f, blur):
    x = np.arange(TAB_N) / TAB_N
    return _smooth_loop(f(x), blur * TAB_N)


LOBE_R = _table(lambda p: 2.0 * np.sin(np.pi * p) ** LOBE_P - 1.0, LOBE_BLUR)
LOBE_Z = _table(lambda p: 1.0 - (1.0 - (1.0 - 2.0 * np.minimum(p, 1.0 - p)) ** 2) ** ROUND, NOTCH_BLUR)
BELL_R = _table(lambda b: 2.0 * np.sin(np.pi * b) ** BELL_Q - 1.0, BELL_BLUR)
_TAB_X = np.arange(TAB_N + 1) / TAB_N


def _tab(table, x):
    """Periodic table lookup at phases x (any real numbers)."""
    return np.interp(np.mod(x, 1.0), _TAB_X, np.append(table, table[0]))


def _bell_z(b):
    return ((1.0 + np.cos(2.0 * np.pi * np.asarray(b))) / 2.0) ** BELL_P


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
    beyond); above its top edge there is no limit. clear3: the nearest-point
    distance _push3d keeps from it where a point lies inside it."""

    def __init__(self, verts, polys, clear, hold, relax, fade, opening=20.0, clear3=0.0):
        self.bvh = BVHTree.FromPolygons(verts, polys)
        self.clear, self.hold, self.relax, self.fade, self.opening = clear, hold, relax, fade, opening
        self.clear3 = clear3

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

    def push(self, x, y, row):
        """Radial pull (px) that brings the point (x, y, row) to clear3 from
        the surface's nearest point, where the point lies inside the surface
        at its own height (0 elsewhere)."""
        if self.clear3 <= 0.0:
            return 0.0
        q = Vector((x, y, -row))
        hit = self.bvh.find_nearest(q, 2.0 * self.clear3)
        if hit[0] is None:
            return 0.0
        loc, nrm, _, dist = hit
        rad = Vector((x, y, 0.0))
        if rad.length < 1e-9 or not math.isfinite(self._cast(rad.normalized(), row)):
            return 0.0
        rad.normalize()
        if nrm.dot(Vector((loc.x, loc.y, 0.0))) < 0.0:
            nrm = -nrm
        deficit = self.clear3 + (q - loc).dot(nrm)
        if deficit <= 0.0:
            return 0.0
        return min(deficit / max(nrm.dot(rad), PUSH_MIN_COS), 3.0 * self.clear3)


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
    return _Inner(verts, polys, CLEAR, CLEAR_HOLD, CLEAR_RELAX, CLEAR_FADE, clear3=CLEAR3)


def _tier_inner(obj):
    """An outer tier's built mesh as a clearance limit for the tiers inside it."""
    me = obj.data
    verts = [Vector((v.co.x * spec.PX_PER_M, v.co.y * spec.PX_PER_M, -_row(v.co.z))) for v in me.vertices]
    polys = [list(p.vertices) for p in me.polygons]
    return _Inner(verts, polys, *TIER_CLEAR, clear3=TIER_CLEAR3)


def _spread(pull):
    """A per-sample pull spread to the neighbouring samples (dilated, then
    smoothed, never below what each sample needs), so it has no sharp steps."""
    if not pull.any():
        return pull
    wide = np.maximum(np.maximum(pull, np.roll(pull, 1)), np.roll(pull, -1))
    return np.maximum(pull, _smooth_loop(wide, 1.0))


def _clamp_ring(loop, inners, margin=None, apply_to=None):
    """Pull a ring of world points radially inside every surface in `inners`
    (the smallest limit, soft minimum). The pull is spread to the neighbouring
    samples (_spread), so it has no sharp steps.

    margin: px per sample kept free beyond the clearance; apply_to: rings (a
    tuple) the band's radial scale is applied to instead, returned as a tuple
    (so the clamp moves the whole gathered band in, rather than flattening its
    crests against the skirt). The first of them is the gathered surface: the
    limits are then measured at its own points (their own height: a lobe's
    notch or a pinch stands up to ~2 cm above the band's ring, where a skirt
    trough turning out at its hem lies further in), and a second pass
    (_Inner.push) keeps its nearest-point distance to each surface at least
    that surface's clear3."""
    n = len(loop)
    pull = np.zeros(n)
    rad = np.array([math.hypot(p.x, p.y) * spec.PX_PER_M for p in loop])
    test = loop if apply_to is None else apply_to[0]
    for i, p in enumerate(test):
        x, y = p.x * spec.PX_PER_M, p.y * spec.PX_PER_M
        r = math.hypot(x, y)
        row = _row(p.z)
        lim = min(s.limit(x, y, row) for s in inners) - (0.0 if margin is None or apply_to is not None else margin[i])
        if r < 1e-6 or not math.isfinite(lim):
            continue
        k = CLEAR_SOFT
        d = (r - lim) / k
        if d < -8.0:
            continue
        # soft min(r, lim): -k log(exp(-r/k) + exp(-lim/k))
        rn = lim - k * math.log1p(math.exp(-d)) if d > 0 else r - k * math.log1p(math.exp(d))
        # as a pull on the band (its radial scale moves this point by pull * r / rad)
        pull[i] = (r - rn) * rad[i] / r
    pull = _spread(pull)

    def scaled(ring, pl):
        sc = np.where(rad > 1e-6, (rad - pl) / np.maximum(rad, 1e-6), 1.0)
        return [Vector((p.x * k, p.y * k, p.z)) for p, k in zip(ring, sc)]
    if apply_to is None:
        return scaled(loop, pull)
    g = scaled(apply_to[0], pull)
    extra = np.array([max(s.push(p.x * spec.PX_PER_M, p.y * spec.PX_PER_M, _row(p.z)) for s in inners)
                      for p in g])
    pull = pull + _spread(extra)
    return tuple(scaled(r, pull) for r in apply_to)


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


def _arc_azimuth(shape):
    """Cumulative arc length (px) and azimuth (rad, 0 = front centre, + toward
    +X, increasing) of the dense outline's points, closed (the first point
    repeated at the end, one turn on)."""
    pts = np.array(_dense_outline(shape))
    closed = np.vstack([pts, pts[:1]])
    cum = np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(closed, axis=0).T))])
    az = np.unwrap(np.arctan2(closed[:, 0], -closed[:, 1]))
    return cum, az


def _fracs_at(shape, az):
    """Arc-length fractions (from the front centre) of the outline points at the azimuths az."""
    cum, a = _arc_azimuth(shape)
    t = np.mod(np.asarray(az) - a[0], 2 * math.pi) + a[0]
    return np.interp(t, a, cum) / cum[-1]


def _layout():
    """The lobes and bells round the tiers, the same for every tier: per sample
    its azimuth (rad, increasing from near the front centre), lobe phase (0 =
    notch, 0.5 = crest) and lobe index, bell phase (0 = the pinch, 0.5 =
    mid-bell) and bell index. The bells hold BELL_LOBES lobes each; the lobes
    are unevenly wide (WIDTH_VAR); bell 0 is centred on the front centre. The
    positions are laid out along the outer tier's hem outline and carried to
    the others by azimuth, so the tiers' bells stack."""
    bells, k, total = [], 0, 0
    while total < NLOBES:
        n = BELL_LOBES[1] if _hash(k, 51) < BELL4 else BELL_LOBES[0]
        bells.append(n)
        total, k = total + n, k + 1
    bells[-1] -= total - NLOBES
    if bells[-1] < 2:
        bells[-2] += bells.pop()
    w = np.array([1.0 + WIDTH_VAR * (2 * _hash(j, 3) - 1) for j in range(NLOBES)])
    pos = np.concatenate([[0.0], np.cumsum(w)])
    pos = pos / pos[-1]
    frac, ph, lob, bph, bel = [], [], [], [], []
    j0 = 0
    for kb, n in enumerate(bells):
        a, b = pos[j0], pos[j0 + n]
        for j in range(j0, j0 + n):
            for q in range(SPF):
                p = q / SPF
                f = pos[j] + p * (pos[j + 1] - pos[j])
                frac.append(f)
                ph.append(p)
                lob.append(j)
                bph.append((f - a) / (b - a))
                bel.append(kb)
        j0 += n
    frac = np.array(frac) - 0.5 * (pos[bells[0]] - pos[0])     # bell 0 centred on the front
    cum, az0 = _arc_azimuth(TIERS[0][1])
    az = np.interp(np.mod(frac, 1.0) * cum[-1], cum, az0)
    az = np.unwrap(az)
    return az, np.array(ph), np.array(lob), np.array(bph), np.array(bel), len(bells)


def hem_row(x, y, lift=None):
    """Panel row of a tier's hem line at the hem-outline point (x, y) (panel
    px), before the tuck.

    The hem point projects onto front-view column |x| and side-view column y.
    The measured bottom outline of each view is the lowest frill point over
    that column, so a hem point should hang no lower than either outline: take
    the higher of the two (a smooth minimum, so there is no crease where they
    cross), then HEM_DROP lower for the lobes. Inner tiers reach the lower
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


def _level_bells(rows, bell, bph, nbells):
    """The hem rows levelled (LEVEL) to each bell's mean, handing over to the
    neighbouring bell's level within BELL_EDGE of the pinch (smoothstep, half
    way at the pinch itself): a sloping hem becomes a staircase of level bell
    mouths whose steps hide in the rising pinches."""
    rows = np.asarray(rows, dtype=np.float64)
    m = np.array([rows[bell == k].mean() for k in range(nbells)])
    lev = m[bell].copy()
    t = np.clip(bph / BELL_EDGE, 0.0, 1.0)
    lev += (m[(bell - 1) % nbells] - m[bell]) * (0.5 - 0.5 * t * t * (3 - 2 * t))
    t = np.clip((1.0 - bph) / BELL_EDGE, 0.0, 1.0)
    lev += (m[(bell + 1) % nbells] - m[bell]) * (0.5 - 0.5 * t * t * (3 - 2 * t))
    return rows + LEVEL * (lev - rows)


def _lift_pinch(x, lift):
    """Radial scale of the hem outline point at x px (see LIFT_PINCH)."""
    return 1.0 - LIFT_PINCH * (1.0 - _smoothstep(lift[0], lift[1], abs(x)))


# ---------------------------------------------------------------- core
# The outer tier's seam height (world z) by ellipse angle, (angles, z) sorted,
# set by build() once the outer tier is built (its seam rises where its hem
# tucks up); the core cone ends CORE_TUCK px below it. _SEAM1: the middle
# tier's seam on the core (the core's gathers have faded out above it);
# _SEAM2: the inner tier's seam ring as built (angles, points), where the core
# mesh ends.
_SEAM0 = None
_SEAM1 = None
_SEAM2 = None


def _ellipse_angle(x, y):
    w, fd, bd = TIERS[0][1][:3]
    return math.atan2(y / (fd if y < 0 else bd), x / w)


def _core_bottom(phi):
    """(x, y, z) world point of the core cone's lower edge at ellipse angle phi."""
    _, dims0, lift0, (_, height0, _) = TIERS[0][:4]
    c, s = math.cos(phi), math.sin(phi)
    hx, hy = dims0[0] * c, (dims0[1] if s < 0 else dims0[2]) * s
    # a few px below the outer tier's top edge (untucked, until it is built)
    if _SEAM0 is None:
        z = hem_z(hx, hy, lift0) + height0 * PX
    else:
        z = float(np.interp(phi, _SEAM0[0], _SEAM0[1], period=2 * math.pi))
    z -= CORE_TUCK * PX
    k = CORE_BOTTOM * _lift_pinch(hx, lift0) * PX
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
def _per(units, seed, var, sigma):
    """Per-sample factor 1 +- var, one value per unit (lobe or bell index),
    blended over sigma samples so it never steps between units."""
    return _smooth_loop([1.0 + var * (2 * _hash(int(k), seed) - 1) for k in units], sigma)


def _tier(idx, inners, folds, layout, name, shape, lift, top, lobe_depth, lobe_rise,
          bell_depth, bell_rise, seed, bowl_up):
    """The tier's rings (with the lobes, and the same rings with the bells
    alone, for the shading normals), each ending in the hem roll, its seam
    heights by ellipse angle and its hem outline points."""
    az, ph, lob, bph, bel, nbells = layout
    # this tier's arc fractions at the layout's azimuths, increasing round the hem
    fracs = np.unwrap(2 * math.pi * _fracs_at(shape, az)) / (2 * math.pi)
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
    k12 = 1.5 * SPF     # the smoothing widths were set for 12 samples per ~1.7 cm (round 6-10 folds)
    rows = _limit_slope(_smooth_loop(raw, CLUSTER_SMOOTH * k12), arc, CLUSTER_SLOPE)
    rows = _smin(_smooth_loop(rows, 0.5 * k12), _limit_slope(raw, arc, CLUSTER_SLOPE), SMIN_FINE)

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
    # each bell's mouth level; a seam sewn onto the core cannot rise past the
    # core's top ring: never let the band get shorter than BAND_GUARD there
    # (nor turn inside out)
    hems = [min(spec.px_to_z(r), t.z - BAND_GUARD * PX)
            for r, t in zip(_level_bells(rows, bel, bph, nbells), tops)]
    amp = _per(lob, seed + 7, DEPTH_VAR, VAR_SMOOTH * SPF)
    rise = _per(lob, seed + 29, DEPTH_VAR, VAR_SMOOTH * SPF)
    # the bells' irregularity is shared by the tiers, so the stacked bells nest
    bamp = _per(bel, 41, BELL_VAR, BELL_SMOOTH * 3 * SPF)
    bamp = bamp * np.array([1.0 - LIFT_BELL * (1.0 - _smoothstep(lift[0], lift[1], abs(ox)))
                            for (ox, _), _ in outline])
    # fabric per bell: a band shortened by the tuck folds less deeply
    short = [min(1.0, max(0.0, (t.z - h) / max(t.z - f, 1e-6))) ** SHORT_POW
             for t, h, f in zip(tops, hems, full)]
    # the flare the band reaches at its hem (by how far down the full drop it ends)
    gh = [1.0 - (1.0 - min(1.0, max(0.0, (t.z - h) / max(t.z - f, 1e-6)))) ** FLARE_POW
          for t, h, f in zip(tops, hems, full)]
    lr, lz = _tab(LOBE_R, ph), _tab(LOBE_Z, ph)
    br, bz = _tab(BELL_R, bph), _bell_z(bph)
    # at a pinch the bell's own rise makes the notch: the lobe's sharper notch
    # there folded the cloth over at the hem (dihedrals up to 150 deg)
    lz = lz * (1.0 - PINCH_NOTCH * bz)
    out = {1.0: [], 0.0: []}
    for s in PROFILE:
        loops, band, margin = {1.0: [], 0.0: []}, [], []
        ramp = min(1.0, s / SEAM_RAMP)
        ramp = ramp * ramp * (3 - 2 * ramp)
        msm = _smoothstep(MOUTH_S, 1.0, s)
        rs = s ** RISE_POW * PX
        for i, ((bx, by), (nx, ny)) in enumerate(hem):
            t = tops[i]
            z = t.z + s * (hems[i] - t.z)
            # where on the full seam-to-hem drop this height lies
            d = min(1.0, max(0.0, (t.z - z) / max(t.z - full[i], 1e-6)))
            g = gh[i] * (1.0 - (1.0 - s) ** HANG_POW)
            belly = 1.0 + BELLY * math.sin(math.pi * d)
            # the seam ring itself lies on its support (the core cone)
            grow = (SEAM_FOLD + (1.0 - SEAM_FOLD) * d ** FOLD_POW) * ramp
            fgrow = (FLUTE_SEAM + (1.0 - FLUTE_SEAM) * d ** FLUTE_POW) * ramp
            reach = lobe_depth * amp[i] * short[i] * fgrow
            # the bells are carved inward from the band: their crests lie on it
            # (flaring out by MOUTH at the hem), their pinches 2 x the bell depth
            # inside it, so the bells hang along the band instead of standing
            # out from it the further down they open
            bell = (br[i] - 1.0) * bell_depth * bamp[i] * short[i] * grow + MOUTH * msm * (0.5 + 0.5 * br[i])
            bx0 = t.x + (belly * bx * PX - t.x) * g
            by0 = t.y + (belly * by * PX - t.y) * g
            band.append(Vector((bx0, by0, z)))
            margin.append(lr[i] * reach + bell)
            # the pinch rises evenly down the band (s), so the band stays evenly
            # ringed under it (rising only near the hem, s ** 2, it squeezed the
            # lower rings together and the rolled hem there poked through them)
            zb = z + bell_rise * bamp[i] * bz[i] * s * PX
            for k in (1.0, 0.0):
                # the soft rings (k = 0, for the shading normals) keep the bells
                gather = k * lr[i] * reach + bell
                zk = zb + k * lobe_rise * rise[i] * lz[i] * rs
                loops[k].append(Vector((bx0 + nx * gather * PX, by0 + ny * gather * PX, zk)))
        # the clamp keeps the gathered surface clear inside the skirt (and the
        # outer tiers) and moves the band and its gathers in together, so the
        # bells keep their full depth instead of being flattened against them
        gathered, smooth = _clamp_ring(band, inners, margin, apply_to=(loops[1.0], loops[0.0]))
        out[1.0].append(gathered)
        out[0.0].append(smooth)
    # the upper band (under the seam, where the gathered rings are smallest
    # and the lobes shallow) keeps every second sample (_mesh joins it)
    rings = tuple([ring[::2] if s < COARSE_S else ring for s, ring in zip(PROFILE, r)]
                  + _hem_roll(r[-2], r[-1]) for r in (out[1.0], out[0.0]))
    # the seam height by ellipse angle (sorted)
    seam = sorted((_ellipse_angle(bx, by), t.z) for ((bx, by), _), t in zip(hem, tops))
    return rings, (np.array([a for a, _ in seam]), np.array([z for _, z in seam])), hem


def _hem_roll(prev, edge):
    """Rings that turn the hem edge under: a half circle of HEM_ROLL px radius
    in the plane of the cloth's normal and its downward direction, then a
    short return back up inside (RET_UP). The frame (down the cloth, along
    the hem) is averaged over +-ROLL_SMOOTH samples, so the roll does not
    twist where the hem turns sharply at a notch."""
    P, Q = np.array([tuple(p) for p in edge]), np.array([tuple(p) for p in prev])

    def avg(v):
        acc = v.copy()
        for k in range(1, ROLL_SMOOTH + 1):
            acc += (np.roll(v, k, axis=0) + np.roll(v, -k, axis=0)) * (1.0 - k / (ROLL_SMOOTH + 1))
        return acc

    def unit(v, fallback):
        ln = np.linalg.norm(v, axis=1, keepdims=True)
        return np.where(ln > 1e-12, v / np.maximum(ln, 1e-12), fallback)
    down = unit(avg(unit(P - Q, np.array([0.0, 0.0, -1.0]))), np.array([0.0, 0.0, -1.0]))
    tan = avg(np.roll(P, -1, axis=0) - np.roll(P, 1, axis=0))
    radial = np.column_stack([P[:, 0], P[:, 1], np.zeros(len(P))])
    nrm = unit(np.cross(down, tan), unit(radial, np.array([1.0, 0.0, 0.0])))
    nrm *= np.where((nrm * radial).sum(1) < 0.0, -1.0, 1.0)[:, None]
    # turned towards the body axis: on the flank of a pinch the cloth's normal
    # points across the narrow fold, and the roll curled into its other wall
    rad_u = unit(radial, np.array([1.0, 0.0, 0.0]))
    nrm = unit(nrm + ROLL_RADIAL * rad_u, rad_u)
    nrm = unit(nrm - down * (nrm * down).sum(1, keepdims=True), rad_u)
    rr = HEM_ROLL * PX
    rings = []
    for deg in ROLL_DEG:
        a = math.radians(deg)
        pts = P - nrm * rr + nrm * (rr * math.cos(a)) + down * (rr * math.sin(a))
        rings.append([Vector(p) for p in pts])
    # the return runs up along the last band segment, never past its upper end
    # (on a short band, where the hem tucks up, it pierced the rings above)
    ret = np.minimum(RET_UP * PX, RET_MAX * np.linalg.norm(P - Q, axis=1))[:, None]
    rings.append([Vector(p) for p in P - nrm * (2 * rr) - down * ret])
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


def _finish(col, mat, name, loops, soft, line, shade):
    """Loft the rings into a cloth object with an outline.

    recalc_face_normals is ambiguous on an open tube, so orientation is set
    explicitly: faces point OUTWARD (away from the body axis) on the main
    sheet, so the outline hull sits on the outside of the hem and draws a
    line along every lobe; the hull's backface culling keeps it off the
    fill. The turned-under return then faces the axis, as the inside of a
    thin cloth should. Smooth shading throughout: the rolled hem turns in
    90 degree steps and must not split normals.

    soft: the same rings without the lobes. The shading normals are then
    blended from the gathered surface's (shade, per ring) and the bells', so
    the lobes shade softly: their flanks stay lit instead of breaking into
    small shade wedges where they peek out under the skirt, while the form,
    silhouette and outline keep the full lobes.

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
    share = [f for f, r in zip(shade, loops) for _ in r]
    normals = []
    for v, b, f in zip(me.vertices, base, share):
        own = Vector(v.normal)
        if b.dot(own) < 0.0:      # never blend against a flipped normal
            b = -b
        nv = own * f + b * (1.0 - f)
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
    straight lines to the inner tier's seam (_SEAM2), CORE_N columns, CORE_T
    rings, kept inside the skirt. Gathers (CORE_FOLD columns
    each) open from the hips and fade out above the middle tier's seam, so
    the tiers sewn on below lie on a smooth cone. It is its own object: merged
    with the inner tier's dense frill, the rig smoothed its long, sparse edges
    hardly at all (rig._diffuse scales by the object's median edge) and the
    hip ring stretched x3.4 in high_kick."""
    n = CORE_N
    nf = n // CORE_FOLD
    phis = [2 * math.pi * i / n for i in range(n)]
    tops = [_core_top(p) for p in phis]
    # the lower edge: down the cone's generator to the inner tier's seam
    # height (it rises where that tier's hem tucks up) and, towards the sides,
    # onto that seam as built: under the skirt's raised sides the clearance
    # draws the tiers in, and the cone ran on outside them (through the inner
    # tiers by up to 2-3 cm, as in round 10). Front and back keep the cone:
    # drawn in there too, the core's lower rings met the rising thighs (2.1 cm
    # into the body in squat; the core's weights, smoothed up to the hips,
    # follow the skirt chains' lift less than the tiers do).
    a2, ring2 = _SEAM2
    bots = []
    for p, t in zip(phis, tops):
        b = _core_bottom(p)
        built = Vector([float(np.interp(p, a2, ring2[:, c], period=2 * math.pi)) for c in range(3)])
        cone = t.lerp(b, min(1.0, (t.z - built.z) / max(t.z - b.z, 1e-9)))
        bots.append(cone.lerp(built, math.cos(p) ** CORE_SIDE_P))
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
        if t < 1.0:     # (the lower edge stays on the inner tier's seam)
            gathered, smooth = _clamp_ring(band, inners, reach, apply_to=(loops[1.0], loops[0.0]))
        else:
            gathered, smooth = loops[1.0], loops[0.0]
        out[1.0].append(gathered)
        out[0.0].append(smooth)
    obj = _finish(col, mat, 'petticoat_core', out[1.0], out[0.0], [0.0] * len(CORE_T),
                  [FOLD_SHADE] * len(CORE_T))
    obj['levi_cast_shadow'] = CAST_CORE
    return obj


def build(col):
    global _SEAM0, _SEAM1, _SEAM2
    skirt_in = _skirt_inner()
    folds = skirt.fold_table()
    layout = _layout()
    mat = common.toon_material('petticoat')
    _SEAM0 = _SEAM1 = _SEAM2 = None
    # the outer tier first: the core ends just inside its seam; the inner
    # tiers are sewn onto the core, each inside the tiers around it
    inners = [skirt_in]
    for idx, tier in enumerate(TIERS):
        (gathered, smooth), seam, hem = _tier(idx, inners, folds, layout, *tier)
        if idx == 0:
            _SEAM0 = seam
        if idx == 1:
            _SEAM1 = seam
        if idx == 2:
            # its first ring (every second sample, COARSE_S) by ellipse angle
            ring = sorted((_ellipse_angle(*h[0]), tuple(p)) for h, p in zip(hem[::2], gathered[0]))
            _SEAM2 = (np.array([a for a, _ in ring]), np.array([p for _, p in ring]))
        nroll = len(gathered) - len(PROFILE)
        obj = _finish(col, mat, tier[0], gathered, smooth, _line_weights(len(gathered)),
                      [FOLD_SHADE] * len(PROFILE) + [FOLD_SHADE_ROLL] * nroll)
        obj['levi_cast_shadow'] = CAST_TIERS[idx]
        inners = inners + [_tier_inner(obj)]
    _core(col, mat, inners[:1])
