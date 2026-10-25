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
  the following trough, the fold's half-depth and a smooth radial offset.
  At the hem a crest bulges out and hangs low in a rounded lobe; a trough
  is drawn in and lifted in a rounded arch. The hem height is one cosine
  wave between them (level at both ends: no flat runs, no corners). The
  radial fold offset eases in below the hips and deepens down to the hem.
  The waves are mildly asymmetric: a broad rise, then a steeper (but at
  least STEEP_MIN of the half-fold wide) face into the next trough that
  looks toward +phi, away from the key light in every view. Both halves
  level out at crest and trough, so the cloth turns round everywhere.
- Rings: T_STEPS gives 13 evenly spread stations down the length, so the
  skirt chains bend the cloth in a curve, not in long straight panels.
- Shading: the near-frontal key light only shades faces turned ~72-90 deg
  away, a few px wide on these folds, so the sheet's tapered fold shadows are
  added as soft mint streaks on each steep face (the dress -> dress_mint
  gradient attribute), feathered across the fold and faded in with height.
  White -> mint with height on top, and the turned-out edge mint.
- Hem edge: around a trough the hem turns outward and up in a small, thin
  roll (radius ROLL_R, a little past horizontal), easing in over most of
  the fold's half-width, so the inside of the fabric just shows in the mint
  tone (the sheet's hem curls at every turn). At a crest the hem tucks
  under a little instead, easing in from mid-skirt (CREST_CURL_T).
- Normals are smooth over the whole cloth; only the thin rim at the hem and
  waist is split.
- FOLDS was fitted by levi/parts/_skirt_fit.py so that the visible lower
  outline and the flare outlines match the front, side and back views at once
  (the petticoat hides what lies behind it) while the cloth stays outside the
  petticoat.

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

N_PHI = 153
CURV_DENSITY = 1.5       # extra azimuth samples where the hem curve bends (see azimuths())
# rings down the length (waist -> hem): evenly spaced so the skirt chains bend
# the cloth in a curve, a little denser toward the hem where the folds, the
# hem wave, the crest tuck and the edge flare are all strongest
T_STEPS = (0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.68, 0.76, 0.83, 0.89, 0.945, 1.0)
N_RINGS = len(T_STEPS)
THICK = 0.0018

FOLD_T0 = 0.05           # folds open from this t (below the hips), full depth at the hem
FOLD_EASE = 0.15         # ... eased in over about this share of the length
MID_RELIEF = 0.25        # extra fold depth through mid-skirt (share, peaks halfway, 0 at the hem)
LOBE_P_RANGE = (1.0, 1.6)  # per-fold hem lobe exponent (FOLDS column 6, x10): > 1 widens the lobe bottom
BASE_POW = 1.4           # smooth offset grows as t**BASE_POW
STEEP_MIN = 0.7          # the falling fold face spans at least this share of the half-fold
# Hem edge: no separate rolled lip. Around each trough the last part of the
# sheet itself flares out a little (HEM_FLARE px at the edge, growing as a
# square from HEM_FLARE_T), so the edge turns out in a tangent-continuous
# curve sampled by the main rings and the inside of the fabric just shows.
# The flare weight w rises from 0 to 1 over each fold's half-width toward
# its trough (|u| from LIP_U0 to 1).
LIP_U0 = 0.15
HEM_FLARE = 3.5
HEM_FLARE_T = 0.7
STEEP_FACE_DEG = 70.0    # orientation of the steep fold face at the hem, from the view axis
Z_MINT = 0.6             # white -> mint height gradient reaches this at the hem
STREAK = 0.08            # extra mint on the fold streaks (soft shading, not a painted wedge)
STREAK_W = 1.3           # streak width at the hem, in units of the steep face width
STREAK_T0 = 0.3          # streaks start at this t
STREAK_SOFT = 0.6        # streak edge feather (in u)
DRIFT_DEG = 4.0          # sideways wander of the folds up the skirt (deg at the waist)
CREST_CURL_T = 0.55      # main-sheet t where the per-fold crest curl (tuck under) starts

# One row per fold, sorted by azimuth; fitted by _skirt_fit.py, regenerate with
#   blender -b --factory-startup -P levi/parts/_skirt_fit.py -- --write
# (refines this table; --fresh restarts from initial_folds(); without --write
# it only prints the table and the fit report; --report scores it as is).
# (crest azimuth deg, crest hem row, hem row of the trough after it,
#  half-depth px, smooth radial offset px, inward tuck of the crest at the
#  hem px - negative flares it out over the petticoat, hem lobe exponent x10)
FOLDS = [
    (4, 592, 545, 10, 26, 21, 16),
    (32, 583, 543, 14, 18, 17, 12),
    (51, 575, 543, 10, 20, 11, 12),
    (92, 552, 530, 10, 13, 11, 10),
    (134, 567, 545, 14, 18, 6, 10),
    (150, 569, 555, 10, 22, 4, 14),
    (180, 603, 549, 10, 10, 18, 15),
    (204, 593, 554, 18, 14, 14, 12),
    (231, 565, 527, 14, 16, 14, 12),
    (256, 539, 529, 10, 12, 11, 10),
    (295, 554, 544, 10, 18, 14, 12),
    (326, 582, 543, 10, 28, 11, 12),
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
    fine = np.linspace(0.0, 2 * np.pi, 7201)
    row, fold, base, lip, curl, _, _ = hem_terms(folds, fine[:-1])
    X, Yf, Yb = (float(v) for v in section(575.0))
    c = np.cos(fine[:-1])
    radius = np.hypot(X * np.sin(fine[:-1]), c * np.where(c > 0, Yf, Yb))
    rad = radius + fold + base - curl * (1 - lip) + HEM_FLARE * lip
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
    return np.interp(np.arange(N_PHI) / N_PHI, cdf, fine)


def hem_terms(folds, phi):
    """Per azimuth: hem row, fold offset at the hem (px, + = outward), smooth
    offset (px) and lip weight (0..1)."""
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
    phi_f = np.minimum(np.abs(np.mod(phi + np.pi, 2 * np.pi) - np.pi),
                       np.abs(np.mod(phi, 2 * np.pi) - np.pi))
    tilt = np.radians(np.clip(STEEP_FACE_DEG - np.degrees(phi_f), 15.0, 80.0))
    half = np.radians(0.5 * np.mod(np.roll(f[:, 0], -1) - f[:, 0], 360.0))   # fold k: crest -> trough
    X, Yf, Yb = (float(v) for v in section(575.0))
    radius = np.hypot(X * np.sin(phi), np.cos(phi) * np.where(np.cos(phi) > 0, Yf, Yb))
    steep = np.clip((amp + amp_t) / np.tan(tilt) / (half[k] * radius), STEEP_MIN, 1.0)
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
    # painted fold shade: the steep face (u in [1 - steep, 1]), widest at the
    # hem; returned as the u where the streak starts at the hem
    streak_u0 = np.where(u > 0, np.maximum(1.0 - steep * STREAK_W, 0.35), 2.0)
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
    # feathered across the fold and faded in with height, so the streak
    # reads as soft shading rather than a cut-out triangle
    across = _smoothstep((u - start) / STREAK_SOFT + 0.5)
    return np.where(h > 0, _smoothstep(h) * across, 0.0)


def fold_growth(t):
    """Share (0..1) of the hem fold depth at main-sheet height t."""
    s = np.clip((np.asarray(t, dtype=np.float64) - FOLD_T0) / (1.0 - FOLD_T0), 0.0, 1.0)
    # level start (no crease line where the folds open), then linear (a godet
    # cone) down to the hem, so the folds already show through mid-skirt
    # MID_RELIEF carries extra depth through mid-skirt, back to 1 at the hem
    e = 1.0 - np.exp(-s / FOLD_EASE)
    return s * e / (1.0 - math.exp(-1.0 / FOLD_EASE)) * (1.0 + MID_RELIEF * np.sin(np.pi * s) ** 2)


def ring_terms(folds):
    """hem_terms per (azimuth sample, main-sheet ring), with the fold pattern
    shifted by drift() at each ring's height (each term shaped (N_PHI, rings))."""
    phi = azimuths(folds)[:, None]
    return hem_terms(folds, phi + drift(phi, np.array(T_STEPS)[None, :]))


def profiles(folds):
    """Cloth points, array (N_PHI, N_RINGS, 3) of (x, y, row) in panel px.

    Rings: T_STEPS (waist -> hem edge).
    """
    phi = azimuths(folds)
    rows = hem_terms(folds, phi)[0]
    s, c = np.sin(phi), np.cos(phi)
    out = np.empty((N_PHI, N_RINGS, 3))
    t = np.array(T_STEPS)[None, :]
    row = TOP_ROW + t * (rows[:, None] - TOP_ROW)
    X, Yf, Yb = section(row)
    x = X * s[:, None]
    y = -c[:, None] * np.where(c[:, None] > 0, Yf, Yb)
    r = np.hypot(x, y)
    ux, uy = x / r, y / r
    # fold, smooth offset and crest curl follow the drifting folds (exact at the hem)
    _, fold_t, offs_t, w_t, curl_t, _, _ = ring_terms(folds)
    # folds open gently below the hips and deepen down to the hem; the crest
    # curl eases in (level start) from mid-skirt toward the hem
    off = t ** BASE_POW * offs_t + fold_growth(t) * fold_t
    kc = np.clip((t - CREST_CURL_T) / (1 - CREST_CURL_T), 0, 1) ** 2
    # crests tuck under, troughs flare out a little at the edge
    off = off - curl_t * (1 - w_t) * kc + HEM_FLARE * w_t * flare_k(t)
    out[:, :, 0] = x + ux * off
    out[:, :, 1] = y + uy * off
    out[:, :, 2] = row
    return out


def flare_k(t):
    """0..1 share of the hem-edge flare at main-sheet height t (level start)."""
    return np.clip((np.asarray(t, dtype=np.float64) - HEM_FLARE_T) / (1 - HEM_FLARE_T), 0, 1) ** 2


def initial_folds(crests=(0, 31, 53, 92, 132, 152, 180, 206, 231, 256, 295, 325)):
    """Starting guess for the fit: crest / trough rows read off the view tables
    (front/back weighted by cos^2 of the azimuth, side by sin^2)."""
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
        out.append((cdeg, round(row_at(cdeg)), round(row_at(0.5 * (cdeg + ndeg))), 18, -6, curl, 12))
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
def build(col):
    folds = fold_table()
    pts = profiles(folds)
    rings = [[Vector((spec.px_to_h(pts[i, k, 0]), spec.px_to_h(pts[i, k, 1]),
                      spec.px_to_z(pts[i, k, 2]))) for i in range(N_PHI)]
             for k in range(N_RINGS)]
    bm = common.loft(rings, closed=True)
    # open sheet: make the normals point away from the body (outer cloth side)
    radial = sum(f.normal.dot(Vector((f.calc_center_median().x, f.calc_center_median().y, 0.0)))
                 for f in bm.faces)
    if radial < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces)
    nverts = len(bm.verts)

    mat = common.toon_material('dress', gradient='dress_mint')
    obj = common.new_object(col, 'skirt', bm, [mat])
    sol = obj.modifiers.new('Thickness', 'SOLIDIFY')
    sol.thickness = THICK
    sol.offset = -1.0
    sol.use_even_offset = True
    sol.use_quality_normals = True
    common.apply_modifiers(obj)
    # smooth everywhere on the cloth (no angle-based splits inside a fold);
    # only the edges around the thin rim at the hem and the waist are sharp
    obj.data.shade_smooth()
    me = obj.data
    sharp = me.attributes.get('sharp_edge') or me.attributes.new('sharp_edge', 'BOOLEAN', 'EDGE')
    end_rings = (0, N_RINGS - 1)
    for e in me.edges:
        r0 = (e.vertices[0] % nverts) // N_PHI
        r1 = (e.vertices[1] % nverts) // N_PHI
        sharp.data[e.index].value = r0 == r1 and r0 in end_rings
    # white -> mint with height (up to Z_MINT), mint streaks on the folds'
    # turned-away faces, and the flared edge at the troughs (its inside shows)
    # mint by flare weight
    zg = common.z_gradient(spec.px_to_z(420), spec.px_to_z(600))
    common.set_gradient(obj, lambda co: Z_MINT * zg(co))
    # solidify keeps the loft's vertices first, then their offset copies
    assert len(me.vertices) == 2 * nverts, 'skirt: unexpected solidify vertex layout'
    st = streaks(folds)
    edge = hem_terms(folds, azimuths(folds))[3][:, None] * flare_k(T_STEPS)[None, :]
    attr = me.attributes[common.GRAD_ATTR]
    for v in me.vertices:
        ring, i = divmod(v.index % nverts, N_PHI)
        g = min(1.0, attr.data[v.index].value + STREAK * st[i, ring])
        # the inner face (solidify copies) takes the full edge mint, the outer
        # face only a light tint right at the edge, so no flat mint band
        e = edge[i, ring] if v.index >= nverts else 0.5 * edge[i, ring] ** 2
        attr.data[v.index].value = max(g, e)
    common.add_outline(obj)
    return obj
