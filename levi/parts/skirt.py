"""Outer skirt: knee-length white overskirt flaring from the waist in deep,
rolling godet folds. White at the waist fading to pale mint at the hem.

Shape: one cloth sheet parameterised by azimuth phi (0 = front centre, +phi
toward the character's left / +X) and a profile running from the waist down
to the hem and, at the fold troughs, a short turned-out edge.
- Each height has an egg-shaped section (half-width X, front depth Yf, back
  depth Yb, panel px) measured from the reference outlines (_SECTION) and
  interpolated with a shape-preserving cubic, so the bell has no creases at
  the table rows.
- The cloth hangs in godet folds, one per row of FOLDS: a crest at the
  centre of each hem lobe of the sheet's outlines and a trough midway to the
  next crest. Per fold the table gives the hem height at the crest and at
  the following trough, the fold's half-depth, a smooth radial offset, the
  crest's tuck at the hem and the lobe width exponent.
  At the hem a crest bulges out and hangs low in a rounded lobe; a trough
  is drawn in and lifted in a rounded arch. The hem height is one cosine
  wave between them (level at both ends: no flat runs, no corners). The
  radial fold offset eases in below the hips and deepens down to the hem.
  The waves are mildly asymmetric: a broad rise, then a steeper (but at
  least STEEP_MIN of the half-fold wide) face into the next trough that
  looks toward +phi, away from the key light in every view. Both halves
  level out at crest and trough, so the cloth turns round everywhere.
- Through mid-skirt the crests stand further out from their troughs
  (MID_CREST), so the folds run down from the hips as channels instead of
  appearing only at the hem; the troughs and the hem outline do not move.
- The fold model above has curvature steps (a level crest run meets a steep
  face that turns hard into its trough; the narrow arches rise ~50 px in
  ~30 px of arc). The cloth is therefore evaluated on a fine azimuth grid and
  smoothed along the circumference with a Gaussian (SMOOTH_PX for the radial
  offsets, SMOOTH_ROW_PX for the hem height), which rounds every trough,
  arch top and lobe junction while moving the cloth by about 1 px.
- Rings: T_STEPS gives 30 stations down the length, 0.04 apart through the
  upper and middle skirt and closer toward the hem, so the skirt chains bend
  the cloth in a curve (squat, walk, forward bend), not in straight panels.
  N_PHI azimuth samples are spaced by arc length and packed where the
  smoothed hem curve bends.
- Shading: the near-frontal key light only shades faces turned ~72-90 deg
  away, a few px wide on these folds, so the sheet's tapered fold shadows are
  added as faint mint streaks on each steep face (the dress -> dress_mint
  gradient attribute), feathered on both sides and faded in with height.
  White -> mint with height on top, and the turned-out edge mint inside.
- Hem edge: the cloth is one closed shell (shell()): THICK thick, thickening
  to HEM_THICK toward the hem, where it turns round in a half tube, so the
  edge reads as soft turned fabric rather than a cut blade. Around a trough
  the last part of the sheet flares out a little (HEM_FLARE), tangent-
  continuous, so the inside of the fabric just shows in the mint tone (the
  sheet's hem turns at every trough). At a crest the hem tucks under a
  little instead, easing in from mid-skirt (CREST_CURL_T) and ending at half
  its steepest slope, so the edge does not hook back.
- Hem relief (round 9, hem_relief()): narrow valleys sink every trough and
  split every fold's broad rise, deepening from mid-skirt toward the hem and
  opening out again at the edge, so the lower skirt shows about twice the
  folds, deeper, while crests, outlines and hem rows stay. The outer face's
  shading normals are blended toward the cloth without them (RELIEF_SHADE).
- Outline (round 9): lighter round the hem roll and on the inside of the
  cloth (OUTLINE_VG, HEM_LINE_MIN).
- Normals are smooth over the whole cloth, round the hem roll too; only the
  waist rim (under the bodice) is split.
- FOLDS was fitted by levi/parts/_skirt_fit.py so that the visible lower
  outline and the flare outlines match the front, side and back views at once
  (the petticoat hides what lies behind it) while the cloth stays outside the
  petticoat, with the hem's slope and curvature along the cloth bounded
  (round 6), so the lobes end round instead of in thin edge-on fins.

All reference measurements are in panel pixels (rows / columns of
ref/<view>.png; panel centre column = 320).
"""
import math

import bmesh
import numpy as np
from mathutils import Vector

from .. import common, spec

# ---------------------------------------------------------------- reference
# Visible lower edge of the overskirt (the petticoat starts below it), measured
# column by column. Key = panel px from the panel centre (+ = image right).
# Front: image right = +X. Back: image right = -X. Side: image right = +Y.
FRONT_HEM = """
-245:540 -242:548 -234:556 -230:560 -226:554 -222:550 -218:550 -214:555 -210:559 -206:563
-202:565 -198:566 -194:565 -190:562 -186:550 -182:546 -178:550 -174:555 -170:559 -166:563
-162:568 -158:569 -154:575 -150:580 -146:583 -142:585 -138:587 -134:589 -130:590 -126:591
-122:592 -118:592 -114:592 -110:556 -106:553 -102:555 -98:542 -94:540 -90:540 -86:541
-82:542 -78:543 -74:544 -70:547 -66:549 -62:551 -58:566 -54:594 -50:598 -46:600 -42:602
-38:603 -34:605 -30:607 -26:609 -22:610 -18:611 -14:612 -10:612 -6:612 -2:612 2:606
6:594 10:596 14:598 18:599 22:601 26:603 30:603 34:604 38:604 42:604 46:603 50:602
54:600 58:598 62:595 66:551 70:548 74:546 78:544 82:543 86:542 90:541 94:540 98:541
102:553 106:556 110:555 114:591 118:592 122:592 126:591 130:590 134:590 138:588 142:586
146:579 150:572 154:565 158:561 162:563 166:560 170:556 174:553 178:549 182:545 186:549
190:562 194:566 198:566 202:565 206:563 210:561 214:557 218:553 222:549 226:552 230:561
234:557 240:550 246:540
"""
BACK_HEM = """
-245:545 -238:560 -234:573 -230:559 -226:563 -222:552 -218:550 -214:555 -210:560 -206:564
-202:567 -198:570 -194:572 -190:569 -186:559 -182:553 -178:553 -174:556 -170:557 -166:559
-162:561 -158:564 -154:565 -150:568 -146:570 -142:572 -138:575 -134:587 -130:586 -126:585
-122:587 -118:589 -114:590 -110:590 -106:590 -102:563 -98:557 -94:544 -90:546 -86:548
-82:550 -78:553 -74:555 -70:558 -66:574 -62:568 -58:568 -54:606 -50:607 -46:608 -42:610
-38:612 -34:614 -30:615 -26:617 -22:618 -18:618 -14:619 -10:619 -6:619 -2:619 2:619
6:618 10:618 14:595 18:593 22:584 26:581 30:578 34:574 38:571 42:567 46:564 50:562
54:558 58:556 62:553 66:551 70:549 74:546 78:548 82:565 86:583 90:588 94:589 98:590
102:590 106:590 110:590 114:589 118:588 122:586 126:589 130:590 134:574 138:571 142:568
146:566 150:566 154:563 158:561 162:559 166:556 170:554 174:551 178:556 182:568 186:572
190:572 194:571 198:569 202:565 206:561 210:556 214:551 218:546 222:550 226:555 230:559
234:571 240:555 246:543
"""
SIDE_HEM = """
-176:560 -172:575 -166:590 -162:601 -158:594 -154:586 -150:589 -146:593 -142:595 -138:596
-134:589 -130:592 -126:595 -122:597 -118:598 -114:587 -110:580 -106:581 -102:583 -98:584
-94:586 -90:587 -86:587 -82:588 -78:587 -74:586 -70:583 -66:580 -62:549 -58:549 -54:549
-50:550 -42:551 -34:570 -26:595 -18:601 -10:603 -2:604 2:604 6:604 10:603 14:603
18:602 22:600 26:598 30:573 34:552 38:548 42:545 46:542 50:539 54:537 58:535 62:533
66:531 70:530 74:529 78:529 82:533 86:545 90:550 94:555 98:589 102:589 106:588 110:586
114:584 118:580 122:576 126:571 130:565 134:559 138:554 142:549 146:546 150:549 154:560
158:561 162:556 168:546
"""

# Section per panel row: (row, half-width X, front depth Yf (toward -Y), back
# depth Yb (toward +Y)), outer cloth surface before folds. Front-view sides
# above row ~480 and the side-view back edge above ~480 are hidden by sleeves
# and hair, so those rows follow a smooth bell from the waist (tucked under the
# bodice) to the measured flare.
_SECTION = [
    (326, 33, 64, 2),
    (338, 50, 84, 16),
    (360, 78, 97, 34),
    (400, 118, 110, 62),
    (450, 160, 117, 94),
    (480, 188, 127, 117),
    (500, 214, 136, 136),
    (520, 235, 147, 152),
    (540, 249, 158, 165),
    (560, 252, 166, 165),
    (575, 253, 170, 160),
    (600, 254, 163, 150),
    (620, 254, 157, 142),
]
TOP_ROW = 326            # tucked under the bodice bottom edge

N_PHI = 360
CURV_DENSITY = 1.5       # extra azimuth samples where the hem curve bends (see azimuths())
# rings down the length (waist -> hem): close enough everywhere that the
# skirt chains bend the cloth in a curve (squat, walk, forward bend), and
# denser toward the hem where the folds, the hem wave, the crest tuck and the
# edge flare are all strongest
T_STEPS = (0.0, 0.04, 0.08, 0.12, 0.16, 0.20, 0.24, 0.28, 0.32, 0.36, 0.40, 0.44, 0.48,
           0.52, 0.56, 0.60, 0.635, 0.67, 0.705, 0.74, 0.77, 0.80, 0.83, 0.86, 0.885,
           0.91, 0.935, 0.955, 0.975, 1.0)
N_RINGS = len(T_STEPS)
THICK = 0.0018           # cloth thickness (m); the shell is built inward from profiles()
HEM_THICK = 0.0030       # thickness at the hem edge, where the cloth rolls round
HEM_THICK_T = 0.87       # ... eased in (level start) from this t
HEM_ROLL = 4             # segments of the rounded hem edge (a half tube)
NF = 2880                # fine azimuth grid the cloth is evaluated and smoothed on
SMOOTH_PX = 5.0          # Gaussian smoothing of the cloth round the skirt (px of arc at
                         # the hem), so curvature is continuous at every crest, trough
                         # and lobe junction (the fold model alone has curvature steps)
SMOOTH_ROW_PX = 7.0      # the same for the hem height: rounds the tops of the narrow arches
                         # (they rose ~50 px in ~30 px of arc to a near point)

FOLD_T0 = 0.05           # folds open from this t (below the hips), full depth at the hem
FOLD_EASE = 0.15         # ... eased in over about this share of the length
MID_RELIEF = 0.15        # extra fold depth through mid-skirt (share, peaks halfway, 0 at the hem)
MID_CREST = 0.35        # extra crest height above the trough through mid-skirt (share; troughs stay)
LOBE_P_RANGE = (1.5, 2.0)  # per-fold hem lobe exponent (FOLDS column 6, x10): > 1 widens the lobe bottom
BASE_POW = 1.4           # smooth offset grows as t**BASE_POW
STEEP_MIN = 0.7          # the falling fold face spans at least this share of the half-fold
# Hem edge: no separate rolled lip. Around each trough the last part of the
# sheet itself flares out a little (HEM_FLARE px at the edge, growing as a
# square from HEM_FLARE_T), so the edge turns out in a tangent-continuous
# curve sampled by the main rings and the inside of the fabric just shows.
# The flare weight w rises from 0 to 1 over each fold's half-width toward
# its trough (|u| from LIP_U0 to 1).
LIP_U0 = 0.15
HEM_FLARE = 0.9          # (3.5 before the rounded hem, 2.5 in round 5: the turned-out troughs read as blades edge-on)
HEM_FLARE_T = 0.7
STEEP_FACE_DEG = 70.0    # orientation of the steep fold face at the hem, from the view axis
Z_MINT = 0.6             # white -> mint height gradient reaches this at the hem
STREAK = 0.08            # extra mint on the fold streaks (soft shading, not a painted wedge)
STREAK_W = 0.7           # streak width at the hem, as a share of the steep face width
STREAK_T0 = 0.3          # streaks start at this t
STREAK_SOFT = 0.6        # streak edge feather (in u)
DRIFT_DEG = 4.0          # sideways wander of the folds up the skirt (deg at the waist)
CREST_CURL_T = 0.45      # main-sheet t where the per-fold crest curl (tuck under) starts
CURL_K = 0.3             # share of the fitted crest tuck (FOLDS column 5) that is built: the
                         # full tuck folds the crest edge back into an edge-on blade
# Hem relief (round 9): godet folds deepen sharply toward the hem (the
# reference model's folds are ~3x deeper near the hem than at the hips) and
# twice as many show across the front. Both only move cloth INWARD, in narrow
# valleys, so the crests - which carry the three views' outlines - and the
# hem rows stay where FOLDS put them:
# - every main trough sinks by RELIEF_TROUGH px, in a valley RELIEF_TROUGH_W
#   of the half-fold wide (narrow valley, the broad crest is untouched);
# - every fold's broad rise (u < 0, see _hem_terms_raw) gets a secondary
#   valley RELIEF_SUB px deep at u = RELIEF_SUB_U, RELIEF_SUB_W wide, so a
#   second, smaller crest stands between it and the trough before;
# both grow as s ** RELIEF_POW from main-sheet t = RELIEF_T0 to the hem
# (nothing above it: the hips keep their smooth bell). The Gaussian along
# the circumference (SMOOTH_PX) rounds the valley bottoms. FOLDS was fitted
# without the relief (it only takes cloth inward, so the fitted outlines
# hold); _skirt_fit scores the built cloth, relief included.
# Shading: the relief's own normals would break the near-frontal key light's
# terminator into specks along every valley wall; the outer face's shading
# normals are blended toward the cloth without the relief (RELIEF_SHADE of
# the real normal), so the cel split stays clean while the outline and the
# silhouette keep the full folds (the petticoat's FOLD_SHADE does the same).
RELIEF_T0 = 0.42
RELIEF_POW = 1.6
RELIEF_TROUGH = 20.0
RELIEF_TROUGH_W = 0.35
RELIEF_SUB = 14.0
RELIEF_SUB_U = -0.45
RELIEF_SUB_W = 0.22
RELIEF_SHADE = 0.6
RELIEF_MOUTH = 1.0
RELIEF_MOUTH_T = 0.7
# Outline (round 9): the hem roll and the inside of the cloth draw a lighter
# line (HEM_LINE_MIN of the outline width) than the outer face's silhouette.
HEM_LINE_MIN = 0.45
OUTLINE_VG = 'skirt_line'

# One row per fold, sorted by azimuth; fitted by _skirt_fit.py, regenerate with
#   blender -b --factory-startup -P levi/parts/_skirt_fit.py -- --write
# (refines this table; --fresh restarts from initial_folds(); without --write
# it only prints the table and the fit report; --report scores it as is).
# (crest azimuth deg, crest hem row, hem row of the trough after it,
#  half-depth px, smooth radial offset px, inward tuck of the crest at the
#  hem px - negative flares it out over the petticoat, hem lobe exponent x10)
FOLDS = [
    (4, 603, 557, 10, -4, 18, 15),
    (44, 585, 550, 16, 0, 11, 18),
    (92, 562, 527, 10, -12, 12, 18),
    (136, 561, 551, 12, -2, 13, 15),
    (184, 561, 551, 14, -6, 21, 15),
    (212, 568, 543, 14, -2, 18, 20),
    (243, 553, 541, 16, -8, 12, 20),
    (315, 564, 548, 20, -6, 14, 20),
]


def parse_table(s):
    out = []
    for tok in s.split():
        a, b = tok.split(':')
        out.append((float(a), float(b)))
    return sorted(out)


def interp(table, v):
    if v <= table[0][0]:
        return table[0][1]
    if v >= table[-1][0]:
        return table[-1][1]
    lo, hi = 0, len(table) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if table[mid][0] <= v:
            lo = mid
        else:
            hi = mid
    (a0, b0), (a1, b1) = table[lo], table[hi]
    return b0 + (b1 - b0) * (v - a0) / (a1 - a0)


_SEC = np.array(_SECTION, dtype=np.float64)


def _pchip_slopes(x, y):
    """Shape-preserving (Fritsch-Carlson) node slopes: no overshoot, so the
    flare never bulges past the measured sections."""
    h = np.diff(x)
    d = np.diff(y) / h
    m = np.zeros_like(y)
    for i in range(1, len(y) - 1):
        if d[i - 1] * d[i] > 0:
            w1, w2 = 2 * h[i] + h[i - 1], h[i] + 2 * h[i - 1]
            m[i] = (w1 + w2) / (w1 / d[i - 1] + w2 / d[i])
    m[0], m[-1] = d[0], d[-1]
    return m


_SEC_M = [_pchip_slopes(_SEC[:, 0], _SEC[:, k]) for k in (1, 2, 3)]


def _pchip(x, xs, ys, ms):
    x = np.clip(np.asarray(x, dtype=np.float64), xs[0], xs[-1])
    i = np.clip(np.searchsorted(xs, x, side='right') - 1, 0, len(xs) - 2)
    h = xs[i + 1] - xs[i]
    s = (x - xs[i]) / h
    h00, h10 = (1 + 2 * s) * (1 - s) ** 2, s * (1 - s) ** 2
    h01, h11 = s * s * (3 - 2 * s), s * s * (s - 1)
    return h00 * ys[i] + h10 * h * ms[i] + h01 * ys[i + 1] + h11 * h * ms[i + 1]


def section(row):
    """(X, Yf, Yb) at panel row(s), smoothly interpolated between the
    measured sections (a piecewise-linear profile would crease the bell at
    every table row)."""
    return tuple(_pchip(row, _SEC[:, 0], _SEC[:, k], m) for k, m in zip((1, 2, 3), _SEC_M))


def _smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def fold_index(folds, phi):
    """Fold index k and position u in it: -1 at the previous trough, 0 at the
    crest, 1 at the next trough (troughs midway between neighbouring crests)."""
    cr = np.radians(np.array([f[0] for f in folds], dtype=np.float64))
    prev = np.roll(cr, 1)
    prev[0] -= 2 * np.pi
    nxt = np.roll(cr, -1)
    nxt[-1] += 2 * np.pi
    tr_lo, tr_hi = 0.5 * (prev + cr), 0.5 * (cr + nxt)
    phi = np.mod(np.asarray(phi, dtype=np.float64) - tr_lo[0], 2 * np.pi) + tr_lo[0]
    k = np.clip(np.searchsorted(tr_hi, phi), 0, len(cr) - 1)
    c = cr[k]
    u = np.where(phi < c, (phi - c) / (c - tr_lo[k]), (phi - c) / (tr_hi[k] - c))
    return k, np.clip(u, -1.0, 1.0)


def azimuths(folds):
    """N_PHI sample azimuths, spaced by arc length round the hem and denser
    where the hem curve bends (lobe bottoms, arch tops, the turns of narrow
    folds), so every crest-to-trough transition gets intermediate samples.
    First sample at phi = 0."""
    d = _dense(folds)                        # the built cloth (full relief)
    if 'azimuths' in d:
        return d['azimuths'].copy()
    fine = np.append(d['phi'], 2 * np.pi)
    row = d['row']
    radius = _hem_radius(d['phi'])
    rad = radius + d['off'][:, -1]           # the smoothed cloth at the hem
    ds = radius * (fine[1] - fine[0])
    # curvature of the hem curve in the (arc, row) and (arc, radius) planes
    d2 = np.hypot(np.roll(row, -1) - 2 * row + np.roll(row, 1),
                  np.roll(rad, -1) - 2 * rad + np.roll(rad, 1)) / ds ** 2
    k = int(round(np.radians(3.0) / (fine[1] - fine[0])))       # +-3 deg moving average
    d2 = np.convolve(np.concatenate([d2[-k:], d2, d2[:k]]), np.ones(2 * k + 1) / (2 * k + 1), 'valid')
    dens = ds * (1.0 + CURV_DENSITY * np.sqrt(d2 / d2.mean()))
    dens = np.append(dens, dens[0])
    cdf = np.concatenate([[0.0], np.cumsum(0.5 * (dens[1:] + dens[:-1]))])
    cdf /= cdf[-1]
    d['azimuths'] = np.interp(np.arange(N_PHI) / N_PHI, cdf, fine)
    return d['azimuths'].copy()


def _hem_radius(phi):
    """Radius (px) of the bell's section at the hem (row 575) toward azimuth phi."""
    X, Yf, Yb = (float(v) for v in section(575.0))
    c = np.cos(phi)
    return np.hypot(X * np.sin(phi), c * np.where(c > 0, Yf, Yb))


def _smooth_loop(v, sigma):
    """Circular Gaussian smoothing along axis 0 (sigma in samples)."""
    w = 2 * np.pi * np.fft.fftfreq(v.shape[0])
    h = np.exp(-0.5 * (w * sigma) ** 2).reshape((-1,) + (1,) * (v.ndim - 1))
    return np.real(np.fft.ifft(np.fft.fft(v, axis=0) * h, axis=0))


def _trough_floor(folds, phi):
    """The fold term's trough level (px, -trough half-depth) under phi: the
    levels of the fold's two troughs, blended smoothly across the fold (equal
    to each at its trough, no step at the crest)."""
    f = np.array(folds, dtype=np.float64)
    k, u = fold_index(folds, phi)
    n = len(f)
    lo = -0.5 * (f[np.mod(k - 1, n), 3] + f[k, 3])     # trough before fold k
    hi = -0.5 * (f[k, 3] + f[np.mod(k + 1, n), 3])     # trough after it
    return lo + (hi - lo) * _smoothstep(0.5 * (u + 1.0))


_DENSE_CACHE = {}
DENSE_CACHE_MAX = 4      # entries kept (the built cloth and the relief-free one, per table)


def _dense(folds, relief=1.0):
    """The cloth on a fine uniform azimuth grid (NF samples from phi = 0):
    dict with 'phi', the hem 'row' (NF,) and the radial 'off'set (NF, N_RINGS)
    of every ring, px. The fold model (hem_terms) is built from pieces that
    meet with matching slopes but not matching curvature (a level crest run,
    then a steep face that turns hard into the trough), which reads as a
    pointed trough in clay and cel; a Gaussian along the circumference
    (SMOOTH_PX of arc at the hem) makes the cloth turn round everywhere while
    moving it by only ~1 px. relief scales the hem relief (hem_relief(); 0
    gives the cloth the shading normals are blended toward). Cached per fold
    table and relief."""
    key = (tuple(tuple(f) for f in folds), float(relief))
    if key in _DENSE_CACHE:
        return _DENSE_CACHE[key]
    phi = np.arange(NF) * (2 * np.pi / NF)
    t = np.array(T_STEPS)[None, :]
    # fold, smooth offset and crest curl follow the drifting folds (exact at
    # the hem, where the drift is 0: the last column is the hem row)
    row, fold_t, offs_t, w_t, curl_t, u_t, _ = _hem_terms_raw(folds, phi[:, None] + drift(phi[:, None], t))
    row = row[:, -1]
    # folds open gently below the hips and deepen down to the hem; the crest
    # curl eases in (level start) from mid-skirt toward the hem
    off = t ** BASE_POW * offs_t + fold_growth(t) * fold_t
    # through mid-skirt the crests stand out further from their troughs
    # (MID_CREST of the fold's height above its trough, peaking halfway, 0 at
    # the waist and the hem): the folds carry volume down from the hips, while
    # the troughs (the inner surface the petticoat sits under) and the hem
    # outline stay where they were
    s = np.clip((t - FOLD_T0) / (1.0 - FOLD_T0), 0.0, 1.0)
    floor = _trough_floor(folds, phi[:, None] + drift(phi[:, None], t))
    off = off + MID_CREST * np.sin(np.pi * s) ** 2 * (fold_t - floor)
    # crests tuck under, troughs flare out a little at the edge; the tuck
    # eases in from CREST_CURL_T and ends at half its steepest slope, so the
    # crest's edge turns in without hooking back edge-on
    kc = np.clip((t - CREST_CURL_T) / (1 - CREST_CURL_T), 0, 1)
    kc = kc * kc * (2.0 - kc)
    off = off - CURL_K * curl_t * (1 - w_t) * kc + HEM_FLARE * w_t * flare_k(t)
    # round 9: narrow valleys deepening toward the hem (inward only)
    off = off - relief * hem_relief(u_t, t)
    px =float(_hem_radius(phi).mean()) * (2 * np.pi / NF)       # px of arc per sample
    val = {'phi': phi, 'row': _smooth_loop(row, SMOOTH_ROW_PX / px),
           'off': _smooth_loop(off, SMOOTH_PX / px)}
    if len(_DENSE_CACHE) >= DENSE_CACHE_MAX:     # bounded: the fit tries many tables
        _DENSE_CACHE.pop(next(iter(_DENSE_CACHE)))
    _DENSE_CACHE[key] = val
    return val


def relief_growth(t):
    """0..1 share of the hem relief at main-sheet height t: none above
    RELIEF_T0, then s ** RELIEF_POW (level start) down to the hem; the
    last stretch (from RELIEF_MOUTH_T) gives back RELIEF_MOUTH of it, so
    each valley opens out into its mouth at the hem edge instead of
    pinching it in (the petticoat below keeps its clearance)."""
    t = np.asarray(t, dtype=np.float64)
    s = np.clip((t - RELIEF_T0) / (1.0 - RELIEF_T0), 0.0, 1.0)
    return s ** RELIEF_POW * (1.0 - RELIEF_MOUTH * _smoothstep((t - RELIEF_MOUTH_T) / (1.0 - RELIEF_MOUTH_T)))


def hem_relief(u, t):
    """Inward depth (px) of the round-9 hem relief at fold position u (-1
    trough before, 0 crest, 1 trough after) and main-sheet height t: a narrow
    valley at every main trough and a secondary valley on each fold's broad
    rise. 0 at every crest, so the outlines stay."""
    a = np.abs(np.asarray(u, dtype=np.float64))
    trough = 1.0 - _smoothstep((1.0 - a) / RELIEF_TROUGH_W)
    sub = 1.0 - _smoothstep(np.abs(np.asarray(u) - RELIEF_SUB_U) / RELIEF_SUB_W)
    return relief_growth(t) * (RELIEF_TROUGH * trough + RELIEF_SUB * sub)


def hem_terms(folds, phi):
    """Per azimuth: (hem row, fold offset at the hem (px, + = outward), smooth
    offset (px), lip weight (0..1), crest curl (px), fold position u, streak
    start u). The hem row is the built one (smoothed, as in profiles()); the
    other terms are the fold model's, before the smoothing along the hem."""
    terms = _hem_terms_raw(folds, phi)
    d = _dense(folds)
    p = np.mod(np.asarray(phi, dtype=np.float64), 2 * np.pi)
    row = np.interp(p.ravel(), d['phi'], d['row'], period=2 * np.pi).reshape(p.shape)
    return (row,) + tuple(terms[1:])


def _hem_terms_raw(folds, phi):
    """hem_terms() of the fold model itself (hem row not smoothed)."""
    f = np.array(folds, dtype=np.float64)
    k, u = fold_index(folds, phi)
    side = np.where(u < 0, -1, 0)              # the trough on this side: k-1 or k
    kt = np.mod(k + side, len(f))              # trough index (trough after fold kt)
    kn = np.mod(kt + 1, len(f))
    a = np.abs(u)
    crest_row, trough_row = f[k, 1], f[kt, 2]
    # the hem is one smooth wave: a cosine from the lobe bottom (crest) to
    # the arch top (trough), level at both ends, so lobes and arches are both
    # round with no flat run and no corner where they meet
    # (the fold's exponent p > 1 broadens its lobe bottom; the slope still
    # vanishes at both ends, so the arch top stays round)
    p = np.clip(f[k, 6] / 10.0, *LOBE_P_RANGE)
    row = crest_row + (trough_row - crest_row) * 0.5 * (1.0 - np.cos(np.pi * a ** p))
    amp, amp_t = f[k, 3], 0.5 * (f[kt, 3] + f[kn, 3])
    # asymmetric wave: a broad rise from the trough before the crest (u < 0),
    # a short steep drop into the trough after it (u near 1). The steep face
    # looks toward +phi, which is away from the key light in every view
    # (the light rotates with the camera), so it reads as the sheet's shade
    # wedge running up from each turn of the hem.
    # The drop eases in and out (smoothstep, so the trough is rounded, not a
    # V) and is as wide as puts its mean slope at STEEP_FACE_DEG to the
    # front / back view axis at the hem (the cone's flare tilts its normal
    # up, so only ~72-90 deg reads as shade; past 90 it would hide).
    # The width is one number per fold, taken three quarters of the way from
    # crest to trough (u = 0.75): evaluated per azimuth, its clips put slope breaks
    # inside the face (a kink where the tilt clip engages).
    half = np.radians(0.5 * np.mod(np.roll(f[:, 0], -1) - f[:, 0], 360.0))   # fold k: crest -> trough
    amp_n = 0.5 * (f[:, 3] + np.roll(f[:, 3], -1))                         # depth at the trough after k
    phi_m = np.radians(f[:, 0]) + 0.75 * half
    phi_f = np.minimum(np.abs(np.mod(phi_m + np.pi, 2 * np.pi) - np.pi),
                       np.abs(np.mod(phi_m, 2 * np.pi) - np.pi))
    tilt = np.radians(np.clip(STEEP_FACE_DEG - np.degrees(phi_f), 15.0, 80.0))
    steep_k = np.clip((f[:, 3] + amp_n) / np.tan(tilt) / (half * _hem_radius(phi_m)), STEEP_MIN, 1.0)
    steep = steep_k[k]
    # both halves level out at the crest and in the trough (zero slope), so
    # the cloth turns round at every crest and crease instead of creasing
    g = np.where(u < 0, 0.5 * (1.0 + np.cos(np.pi * a)),
                 1.0 - _smoothstep((u - (1.0 - steep)) / steep))
    fold = -amp_t + (amp + amp_t) * g
    base_t = 0.5 * (f[kt, 4] + f[kn, 4])
    base = f[k, 4] + (base_t - f[k, 4]) * _smoothstep(a)
    curl_t = 0.5 * (f[kt, 5] + f[kn, 5])
    curl = f[k, 5] + (curl_t - f[k, 5]) * _smoothstep(a)
    lip = _smoothstep((a - LIP_U0) / (1 - LIP_U0))
    # painted fold shade: the outer STREAK_W share of the steep face (u in
    # [1 - steep, 1]), widest at the hem; returned as the u where the streak
    # starts at the hem
    streak_u0 = np.where(u > 0, 1.0 - steep * STREAK_W, 2.0)
    return row, fold, base, lip, curl, u, streak_u0


def drift(phi, t):
    """Azimuth (radians) the fold pattern is shifted by at main-sheet height t:
    the folds wander a little sideways on their way up from the hem, so they
    are not straight radial channels. 0 at the hem."""
    return np.radians(DRIFT_DEG) * np.sin(3.0 * phi + 0.7) * (1.0 - t) ** 1.5


def streaks(folds):
    """Mint streak weight (0..1) per (azimuth sample, main-sheet ring): a wedge
    on every fold's turned-away face, from STREAK_T0 down to the hem."""
    *_, u, u0 = ring_terms(folds)                             # follow the drifting folds
    h = np.clip((np.array(T_STEPS)[None, :] - STREAK_T0) / (1 - STREAK_T0), 0, 1)  # 0 top, 1 hem
    start = 1.0 - (1.0 - u0) * _smoothstep(h)                 # narrows upward, eased
    # feathered on the leading side, faded out again into the trough (where
    # the next fold's u = -1 carries no streak) and faded in with height, so
    # the streak reads as soft shading rather than a cut-out triangle
    across = _smoothstep((u - start) / STREAK_SOFT + 0.5) * (1.0 - _smoothstep((u - 0.8) / 0.2))
    return np.where(h > 0, _smoothstep(h) * across, 0.0)


def fold_growth(t):
    """Share (0..1) of the hem fold depth at main-sheet height t."""
    s = np.clip((np.asarray(t, dtype=np.float64) - FOLD_T0) / (1.0 - FOLD_T0), 0.0, 1.0)
    # level start (no crease line where the folds open), then linear (a godet
    # cone) down to the hem, so the folds already show through mid-skirt
    # MID_RELIEF carries extra depth through mid-skirt, back to 1 at the hem
    e = 1.0 - np.exp(-s / FOLD_EASE)
    return s * e / (1.0 - math.exp(-1.0 / FOLD_EASE)) * (1.0 + MID_RELIEF * np.sin(np.pi * s) ** 2)


def ring_terms(folds, phi=None):
    """hem_terms per (azimuth sample, main-sheet ring), with the fold pattern
    shifted by drift() at each ring's height (each term shaped (N_PHI, rings)).
    phi: the sample azimuths if already computed (azimuths(folds))."""
    phi = (azimuths(folds) if phi is None else np.asarray(phi))[:, None]
    return hem_terms(folds, phi + drift(phi, np.array(T_STEPS)[None, :]))


def profiles(folds, relief=1.0):
    """Cloth points, array (N_PHI, N_RINGS, 3) of (x, y, row) in panel px.

    Rings: T_STEPS (waist -> hem edge). The fold offsets and hem rows are
    the smoothed ones of _dense(), sampled at azimuths(). relief: share of
    the hem relief (1 = the built cloth; the samples stay the same).
    """
    phi = azimuths(folds)
    d = _dense(folds, relief)
    rows = np.interp(phi, d['phi'], d['row'], period=2 * np.pi)
    off = np.stack([np.interp(phi, d['phi'], d['off'][:, j], period=2 * np.pi)
                    for j in range(N_RINGS)], axis=1)
    s, c = np.sin(phi), np.cos(phi)
    out = np.empty((N_PHI, N_RINGS, 3))
    t = np.array(T_STEPS)[None, :]
    row = TOP_ROW + t * (rows[:, None] - TOP_ROW)
    X, Yf, Yb = section(row)
    x = X * s[:, None]
    y = -c[:, None] * np.where(c[:, None] > 0, Yf, Yb)
    r = np.hypot(x, y)
    ux, uy = x / r, y / r
    out[:, :, 0] = x + ux * off
    out[:, :, 1] = y + uy * off
    out[:, :, 2] = row
    return out


def flare_k(t):
    """0..1 share of the hem-edge flare at main-sheet height t (level start)."""
    return np.clip((np.asarray(t, dtype=np.float64) - HEM_FLARE_T) / (1 - HEM_FLARE_T), 0, 1) ** 2


def initial_folds(crests=(4, 44, 92, 136, 184, 212, 243, 315)):
    """Starting guess for the fit: crest / trough rows read off the view tables
    (front/back weighted by cos^2 of the azimuth, side by sin^2). Eight folds
    (round 6): the narrow pairs at the four quarters (~22 deg apart) were
    merged, since a narrow lobe between two arches read as an edge-on fin."""
    front, back, side = (parse_table(s) for s in (FRONT_HEM, BACK_HEM, SIDE_HEM))
    X, Yf, Yb = (float(v) for v in section(560))

    def row_at(deg):
        phi = math.radians(deg)
        c = math.cos(phi)
        x, y = X * math.sin(phi), -c * (Yf if c > 0 else Yb)
        r_fb = interp(front, x) if c > 0 else interp(back, -x)
        w = c * c
        return w * r_fb + (1 - w) * interp(side, y)

    out = []
    for i, cdeg in enumerate(crests):
        ndeg = crests[(i + 1) % len(crests)] + (360 if i == len(crests) - 1 else 0)
        # front / back centre lobes hang lowest and roll under onto the
        # petticoat, so they do not hang out of the side view's outline
        curl = round(6 + 10 * math.cos(math.radians(cdeg)) ** 8)
        out.append((cdeg, round(row_at(cdeg)), round(row_at(0.5 * (cdeg + ndeg))), 18, -6, curl, 16))
    return out


def fold_table():
    return FOLDS if FOLDS else initial_folds()


_MAIN_CACHE = {}


def front_surface_y(dx, row):
    """Front-most y (px, -Y = toward the viewer) of the outer cloth surface on the
    main sheet at front-view column offset dx and panel row; used by the bodice
    ribbon tails, which lie on the skirt front (|dx| < ~60 px). Only the front
    half (y < 0) counts; None where the cloth there does not reach row."""
    folds = fold_table()
    key = tuple(tuple(f) for f in folds)
    if _MAIN_CACHE.get('key') != key:
        _MAIN_CACHE.update(key=key, pts=profiles(folds)[:, :len(T_STEPS)])
    pts = _MAIN_CACHE['pts']
    # (x, y) of every azimuth's profile at this row (rows increase down a profile)
    a, b = pts[:, :-1, :], pts[:, 1:, :]
    hit = (a[:, :, 2] <= row) & (row <= b[:, :, 2]) & (b[:, :, 2] > a[:, :, 2])
    f = np.where(hit, (row - a[:, :, 2]) / np.where(hit, b[:, :, 2] - a[:, :, 2], 1.0), 0.0)
    k = np.argmax(hit, axis=1)
    ok = hit.any(axis=1)
    i = np.arange(N_PHI)
    x = a[i, k, 0] + (b[i, k, 0] - a[i, k, 0]) * f[i, k]
    y = a[i, k, 1] + (b[i, k, 1] - a[i, k, 1]) * f[i, k]
    # crossings of x = dx between neighbouring azimuths on the front half
    x1, y1, ok1 = np.roll(x, -1), np.roll(y, -1), np.roll(ok, -1)
    cross = ok & ok1 & ((x - dx) * (x1 - dx) <= 0) & (x != x1) & (y < 0) & (y1 < 0)
    if not cross.any():
        return None
    s = (dx - x[cross]) / (x1[cross] - x[cross])
    return float((y[cross] + (y1[cross] - y[cross]) * s).min())


# ---------------------------------------------------------------- build
def _sheet(pts):
    """Outer cloth sheet points and outward unit normals, both (N_RINGS,
    N_PHI, 3) metres, from profiles() points (px)."""
    rings = [[Vector((spec.px_to_h(pts[i, k, 0]), spec.px_to_h(pts[i, k, 1]),
                      spec.px_to_z(pts[i, k, 2]))) for i in range(N_PHI)]
             for k in range(N_RINGS)]
    bm = common.loft(rings, closed=True)
    # the sheet's normals point away from the body (outer cloth side)
    radial = sum(f.normal.dot(Vector((f.calc_center_median().x, f.calc_center_median().y, 0.0)))
                 for f in bm.faces)
    if radial < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces)
    bm.normal_update()
    P = np.array([v.co[:] for v in bm.verts]).reshape(N_RINGS, N_PHI, 3)
    Nv = np.array([v.normal[:] for v in bm.verts]).reshape(N_RINGS, N_PHI, 3)
    bm.free()
    return P, Nv


def build(col):
    folds = fold_table()
    P, Nv = _sheet(profiles(folds))
    _, Nsoft = _sheet(profiles(folds, relief=0.0))   # the cloth without the hem relief
    outer, inner, roll = shell(P, Nv)

    # one closed cloth shell: outer sheet, the rounded hem roll, inner sheet
    # and the waist rim, with vertex rows [outer rings 0..n-1, inner rings
    # 0..n-1, roll rows 1..HEM_ROLL-1]
    rows = list(outer) + list(inner) + list(roll)
    bm = bmesh.new()
    vs = [[bm.verts.new(p) for p in r] for r in rows]

    def strip(a, b):
        for j in range(N_PHI):
            k = (j + 1) % N_PHI
            bm.faces.new((a[j], a[k], b[k], b[j]))

    n = N_RINGS
    for k in range(n - 1):
        strip(vs[k], vs[k + 1])                     # outer sheet
        strip(vs[n + k + 1], vs[n + k])             # inner sheet
    hem = [vs[n - 1]] + vs[2 * n:] + [vs[2 * n - 1]]
    for a, b in zip(hem, hem[1:]):
        strip(a, b)                                 # rounded hem: outer -> inner
    strip(vs[n], vs[0])                             # waist rim (under the bodice)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

    mat = common.toon_material('dress', gradient='dress_mint')
    obj = common.new_object(col, 'skirt', bm, [mat])
    me = obj.data
    nverts = n * N_PHI
    assert len(me.vertices) == 2 * nverts + (HEM_ROLL - 1) * N_PHI, 'skirt: unexpected vertex layout'
    # smooth everywhere on the cloth, round the hem roll too (no angle-based
    # splits inside a fold); only the waist rim, hidden under the bodice, is sharp
    me.shade_smooth()
    sharp = me.attributes.get('sharp_edge') or me.attributes.new('sharp_edge', 'BOOLEAN', 'EDGE')
    for e in me.edges:
        a, b = e.vertices
        sharp.data[e.index].value = (a < 2 * nverts and b < 2 * nverts and
                                     (a % nverts) // N_PHI == 0 and (b % nverts) // N_PHI == 0)
    _shade_normals(me, Nsoft)
    # white -> mint with height (up to Z_MINT), mint streaks on the folds'
    # turned-away faces, and the flared edge at the troughs (its inside shows)
    # mint by flare weight
    zg = common.z_gradient(spec.px_to_z(420), spec.px_to_z(600))
    common.set_gradient(obj, lambda co: Z_MINT * zg(co))
    st = streaks(folds)
    edge = ring_terms(folds)[3] * flare_k(T_STEPS)[None, :]     # the drifted flare weight
    attr = me.attributes[common.GRAD_ATTR]
    for v in me.vertices:
        if v.index < 2 * nverts:
            ring, i = divmod(v.index % nverts, N_PHI)
            # the inner face takes the full edge mint, the outer face only a
            # light tint right at the edge
            s = 1.0 if v.index >= nverts else 0.0
        else:   # the hem roll: from the outer tint round to the inner mint
            j, i = divmod(v.index - 2 * nverts, N_PHI)
            ring, s = n - 1, (j + 1) / HEM_ROLL
        e = edge[i, ring]
        e = s * e + (1 - s) * 0.5 * e * e
        g = min(1.0, attr.data[v.index].value + STREAK * st[i, ring])
        # soft union of the height / streak tint and the edge tint (no
        # crease in the colour where one takes over from the other)
        attr.data[v.index].value = g + e - g * e
    # outline: full width on the outer face, lighter round the hem roll
    # and on the inside of the cloth
    vg = obj.vertex_groups.new(name=OUTLINE_VG)
    vg.add(list(range(nverts)), 1.0, 'REPLACE')
    for j in range(HEM_ROLL - 1):
        w = 1.0 - (1.0 - HEM_LINE_MIN) * (j + 1) / HEM_ROLL
        vg.add(list(range(2 * nverts + j * N_PHI, 2 * nverts + (j + 1) * N_PHI)), w, 'REPLACE')
    common.add_outline(obj, vertex_group=OUTLINE_VG, min_factor=HEM_LINE_MIN)
    return obj


def _shade_normals(me, Nsoft):
    """Blend the outer face's shading normals toward the cloth without the hem
    relief (Nsoft, (N_RINGS, N_PHI, 3)): RELIEF_SHADE of each vertex's own
    normal. The first roll rows take the same correction, fading out round
    the hem roll; the inner face, the rest of the roll and the waist rim (ring 0)
    keep their own normals."""
    if RELIEF_SHADE >= 1.0:
        return
    n = N_RINGS
    nverts = n * N_PHI
    soft = Nsoft.reshape(-1, 3)
    own = np.empty(len(me.loops) * 3)
    me.corner_normals.foreach_get('vector', own)
    own = own.reshape(-1, 3)
    lv = np.empty(len(me.loops), dtype=np.int64)
    me.loops.foreach_get('vertex_index', lv)
    k = np.zeros(len(lv))               # share of the correction
    src = np.zeros(len(lv), dtype=np.int64)
    outer = (lv < nverts) & (lv >= N_PHI)
    k[outer] = 1.0
    src[outer] = lv[outer]
    roll = lv >= 2 * nverts
    j = (lv[roll] - 2 * nverts) // N_PHI            # roll row 0 .. HEM_ROLL-2
    k[roll] = np.clip(1.0 - 2.0 * (j + 1) / HEM_ROLL, 0.0, 1.0)
    src[roll] = (n - 1) * N_PHI + (lv[roll] - 2 * nverts) % N_PHI
    # the correction at the source vertex (the hem ring for the roll):
    # blended minus own, taken from the vertex's (smooth) normal
    vn = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get('normal', vn)
    vn = vn.reshape(-1, 3)
    s = soft[src]
    s = np.where((s * vn[src]).sum(1)[:, None] < 0, -s, s)
    want = RELIEF_SHADE * vn[src] + (1.0 - RELIEF_SHADE) * s
    want /= np.maximum(np.linalg.norm(want, axis=1), 1e-9)[:, None]
    out = own + k[:, None] * (want - vn[src])
    out /= np.maximum(np.linalg.norm(out, axis=1), 1e-9)[:, None]
    me.normals_split_custom_set([tuple(v) for v in out])


def shell(P, Nv):
    """The cloth's two faces and its rounded hem from the sheet points P and
    their outward unit normals Nv (both (N_RINGS, N_PHI, 3), metres).

    The inner face is the sheet moved THICK inward along its normals, as the
    old solidify (offset -1) built it and as the petticoat's clearance model
    rebuilds it. Toward the hem (from HEM_THICK_T, level start) the outer face
    moves out until the cloth is HEM_THICK thick (under 1 px), and the edge
    turns round in a half tube of HEM_ROLL segments, so the hem reads as a
    soft turned edge, not a cut blade. (No even-thickness correction: the
    folds' radii of curvature are many times the thickness.)
    Returns (outer, inner, roll): roll is (HEM_ROLL - 1, N_PHI, 3), the
    intermediate rows from the outer hem round to the inner one."""
    t = np.array(T_STEPS)
    grow = (HEM_THICK - THICK) * _smoothstep((t - HEM_THICK_T) / (1 - HEM_THICK_T))
    outer = P + Nv * grow[:, None, None]
    inner = P - Nv * THICK
    o, i = outer[-1], inner[-1]
    mid, half = 0.5 * (o + i), 0.5 * (o - i)
    # the direction the cloth runs on past the hem (down the last segment),
    # square to the normal
    d = P[-1] - P[-2]
    d -= Nv[-1] * (d * Nv[-1]).sum(axis=1)[:, None]
    d /= np.linalg.norm(d, axis=1)[:, None]
    r = np.linalg.norm(half, axis=1)[:, None]
    roll = np.array([mid + half * math.cos(a) + d * r * math.sin(a)
                     for a in np.pi * np.arange(1, HEM_ROLL) / HEM_ROLL])
    return outer, inner, roll
