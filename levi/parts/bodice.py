"""Corset bodice: strapless white bodice with a sweetheart neckline, princess
seams, front lacing with eyelets and a dark-green diamond, a leaf cluster at
the neckline (character's left), and the green waist bow whose two pairs of
ribbon tails ripple down the front of the skirt.

Form (round 3):
- The shell is a rounded rib cage (superellipse sections, rounder at the
  waist and back) with a modest bust: two broad, overlapping forward lobes
  with a shallow centre dip, drawn in again under the bust. Its front-most
  depth per row is still the measured side-view silhouette.
- Shallow gathers run down from the neckline, which is a thin turned edge
  (a rolled lip with a short inner return) instead of a separate piping band.
- The lacing sits on a central panel: two narrow facings carry flat ring
  eyelets, and round cords bow out between them, lying over / under at each
  crossing and dipping into the eyelets at their ends.
- The bow is a flat ribbon: each loop is a strip pinched into a wrapped knot,
  its face tilted so the loop has depth (a cone, not a wire), the returning
  half of the loop set behind the outgoing one.
- Round 11 (clothes-detail review; same sizes, closure / sampling / silhouette
  only): the knot is a closed wrapped solid whose edges roll under into a
  crease round the bunched loop fabric (loop, tail and lacing ends start inside
  it); the tails end in angled cuts meeting at one point per side; the back has
  a centre-back and two princess seams; a 2.5 mm piping cord runs round the
  waist on the line where the skirt comes out of the bodice (waist_seam(),
  solved against skirt.profiles()).
- The tails are flat ribbons with width that twist at their bends and narrow
  a little toward their cut tips. They lie on the skirt's own cloth surface
  (levi.parts.skirt.front_surface_y), lifted a little more around the hip so
  that the skirt bending at the hip (the rig hands the tails over to the skirt
  weights there) does not swallow them.

All shapes are fitted to ref/front.png and ref/side.png (panel pixels, measured
around this part's own region; see the tables below). Front-view columns are
measured relative to FRONT_CX: the drawn bodice is centred ~1.3 px right of the
panel centre, so features are kept symmetric about x = 0 using offsets from the
drawn centre instead of absolute columns.
"""
import bisect
import functools
import math

import bmesh
import bpy
import numpy as np
from mathutils import Vector

from levi import common, spec
from levi.parts import skirt

PX = spec.px_to_h(1.0)    # one panel pixel in metres
FRONT_CX = 321.0          # drawn centre line of the bodice in ref/front.png


def Z(row):
    return spec.px_to_z(row)


def interp(table, t):
    """Piecewise-linear lookup in a sorted [(t, value), ...] table (clamped)."""
    if t <= table[0][0]:
        return table[0][1]
    for (t0, v0), (t1, v1) in zip(table, table[1:]):
        if t <= t1:
            return v0 + (v1 - v0) * (t - t0) / (t1 - t0)
    return table[-1][1]


def smooth_interp(table, t):
    """C1 cubic Hermite through a sorted [(t, value), ...] table (clamped).

    Tangents are finite differences over the real knot spacing, so unevenly
    spaced knots give no slope jumps.
    """
    ts = [a for a, _ in table]
    vs = [b for _, b in table]
    if t <= ts[0]:
        return vs[0]
    if t >= ts[-1]:
        return vs[-1]
    i = min(bisect.bisect_right(ts, t) - 1, len(ts) - 2)

    def slope(k):
        a, b = max(k - 1, 0), min(k + 1, len(ts) - 1)
        return (vs[b] - vs[a]) / (ts[b] - ts[a])

    h = ts[i + 1] - ts[i]
    u = (t - ts[i]) / h
    h00, h10 = 2 * u ** 3 - 3 * u ** 2 + 1, u ** 3 - 2 * u ** 2 + u
    h01, h11 = -2 * u ** 3 + 3 * u ** 2, u ** 3 - u ** 2
    return h00 * vs[i] + h10 * h * slope(i) + h01 * vs[i + 1] + h11 * h * slope(i + 1)


def smoothstep(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def catmull_path(pts, k):
    """Catmull-Rom spline through Vector control points, k samples per span."""
    out = []
    n = len(pts)
    for i in range(n - 1):
        p0, p1, p2, p3 = pts[max(i - 1, 0)], pts[i], pts[i + 1], pts[min(i + 2, n - 1)]
        for s in range(k):
            u = s / k
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * u + (2 * p0 - 5 * p1 + 4 * p2 - p3) * (u * u)
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * (u ** 3)))
    out.append(pts[-1].copy())
    return out


# ---------------------------------------------------------------- measurements
# Bodice profile per sheet row: (half-width from front view, front-most y from
# the side view, back-most y), all in panel px. The back is hidden by hair in
# both side and back views; it is set ~3 px behind the body's back surface.
PROFILE = [
    # row, half_w, y_front, y_back
    # half_w is the drawn line centre minus half the outline; y_front allows for
    # the full ~1.4 px outline hull (side silhouette).
    (230, 55.5, -84.0, 9.0),
    (240, 57.0, -87.5, 8.0),
    (250, 57.0, -92.5, 8.0),
    (260, 56.5, -95.0, 8.0),
    # rows 270-300: the under-bust draw-in spread over ~30 px (was a short
    # shelf at 270-280, which shaded as a crease under the bust)
    (270, 54.8, -93.2, 9.0),
    # half widths 270-310 eased to a steady taper (was -3.8 / -1.7 px per 10
    # rows, a kink that bent the side terminator into steps)
    (280, 51.6, -90.6, 9.0),
    (290, 49.0, -88.3, 8.5),
    (300, 47.0, -86.9, 6.5),
    (310, 45.0, -86.2, 4.5),
    (320, 45.0, -86.4, 3.0),
    (330, 46.5, -86.6, 2.5),
    (340, 48.0, -86.6, 2.5),
    (352, 51.0, -87.0, 3.5),
]
ROW_BOT = 352             # hidden under the skirt waistband
# Section exponents: the front is a little fuller across the bust and rounds
# off toward the waist; the back is close to an ellipse (a rounded rib cage).
# (one gentle monotone change: a faster change moves the side terminator in steps)
P_FRONT = [(236, 2.18), (290, 2.09), (340, 2.0), (352, 2.0)]
P_BACK = 2.2
# Bust: two broad overlapping lobes centred at |x| = BUST_T * half_w; the
# table gives their strength per row. Below the bust it eases out over ~40 px
# (a long, monotone draw-in to the waist: no short shelf above the lacing).
BUST = [(232, 0.035), (246, 0.07), (262, 0.08), (278, 0.05), (292, 0.022), (306, 0.005),
        (318, 0.0)]
BUST_T, BUST_S = 0.36, 0.30

# Sweetheart neckline: top row vs |x| / half_w across the front half.
NECK_FRONT = [(0.0, 243.0), (0.10, 241.5), (0.28, 237.0), (0.50, 234.0),
              (0.62, 233.5), (0.80, 235.5), (1.0, 240.0)]
NECK_BACK_DROP = 8.0      # px lower at the centre back than at the side seam
# Turned edge: (px below the neckline, px outward from the shell) per extra
# row above the shell's last row: a rolled lip and a short inner return.
LIP = [(0.8, 0.5), (0.0, 0.1), (0.25, -0.55), (2.0, -0.75)]
LIP_START = 1.8           # the shell proper ends this far below the neckline
# Gathers below the neckline: individually placed, rounded folds (character's
# left half; the right half mirrors them with a slight shift so the two sides
# are not identical). (centre t = x / half_w, half width in t, crest px, length
# px below the turned edge.) Each fold is sampled by >= 6 shell columns; the
# folds grow in under the turned edge (which stays smooth) and fade down into
# the bust. A broad shallow trough between them keeps the surface zero-mean.
# A few broad, soft folds (not ribs): each spans ~10 shell columns.
GATHERS = [(0.13, 0.085, 0.9, 26.0), (0.36, 0.095, 1.15, 34.0), (0.58, 0.075, 0.7, 22.0)]
GATHER_SKEW = 0.015       # the right half's folds sit this much (t) further out
GATHER_TROUGH = 0.4       # share of the local fold strength taken back between folds
GATHER_MAX_LEN = max(g[3] for g in GATHERS)
GATHER_CENTRE_ROUND = 0.04   # t: |t| is rounded over this much at the centre front
# The centre front leans back toward the chest just under the sweetheart dip.
NECK_LEAN = 3.0

# Princess seams: |x| offset (px from centre) per row.
SEAM = [(236, 36.5), (250, 36.5), (266, 36.0), (278, 30.5), (290, 24.5), (300, 21.5),
        (320, 20.0), (348, 19.0)]
# Round 11: the back (plain until now; the hair hides it at rest, turns and spins show it)
# gets a centre-back seam and two princess seams, curving in from the shoulder blades to
# the waist (|x| px from the centre per row), welts like the front's. They end under the
# waist piping.
BACK_SEAM = [(244, 31.0), (262, 29.5), (280, 26.0), (300, 22.0), (320, 19.5), (345, 19.0)]
SEAM_END = 1.6            # px the welts run on below the waist seam line (into the piping and skirt)

# Waist piping (round 11): a round cord along the line where the skirt comes out of the
# bodice (waist_seam(): the crossing of the two cloth surfaces, low at the front and high
# at the centre back, where the skirt's waist rim used to peak through the bodice and broke
# the outline over 4-5 cm). It stands proud of both, so the outline runs unbroken round the
# waist and the layer step reads; self fabric (white) like the sheet's plain waist.
PIPE_R = 0.00125          # m: cord radius (2.5 mm across)
PIPE_SIDES = 8
PIPE_N = 192              # stations round the waist (~2.4 mm apart)
PIPE_FIT = 0.85           # share of the distance at which the cord would just touch both cloths
PIPE_SOFT = 1.0           # px: softness of the max of the bodice and skirt radii it rides
PIPE_LINE = 0.0016        # outline width (the cord's top edge is the waist line)
PIPE_SHADE = 0.3          # share of the cord's own roundness in its shading normals (the rest: the cloth's)
SEAM_PSI = 720            # section angles the seam line is solved at
SEAM_ROW_STEP = 0.5       # px between the rows its crossing is bracketed on
SEAM_SMOOTH = 4.0         # deg: Gaussian on the seam row round the waist (the skirt is a polygon)

# Lacing (front view, measured at 7x on ref/front.png).
DIAMOND = (291.8, 11.2, 6.4)                 # centre row, half-width, half-height
EYELET_ROWS = [294.5, 302.8, 310.8, 318.8]
EYELET_DX = 25.5
LACE_END = (337.0, 1.8)                      # row, |dx| where the lacing ends inside the knot
# Lacing cord: width x thickness of the oval section (m) and the centreline lift
# (px) of the under strand at a crossing; the over strand clears it by LACE_CLEAR
# whatever the thickness. Round 9 tried 2.0-2.4 mm cords and larger eyelets
# (strengths guide 3.6); pairwise review (docs/pr/r9-5-trims) found them crowded and heavy.
LACE_W = 0.0019
LACE_T = 0.0012
LACE_UNDER = 0.85
LACE_CLEAR = 0.0003
LACE_OVER = LACE_UNDER + (LACE_T + LACE_CLEAR) / PX
EYELET_R = (1.5, 0.5)                        # px: ring radius, tube radius
FACING = (289.0, 324.0)                      # rows spanned by the eyelet facings

# Bow (front view, px; centre knot + two loops).
KNOT = (321.0, 338.0)
BOW_LOOP_L = [(318, 340), (306, 332), (293, 327.5), (289, 333), (289.5, 344), (292, 354.5),
              (305, 349), (317, 343), (321, 339)]
BOW_Y_KNOT = -97.0        # side view: bow front edge at col ~220 incl. outline
BOW_Y_SLOPE = 0.62        # loops sweep back around the waist
# Round 9 tried 9-11 mm loops 1.3-2 mm thick, a 30 deg twist of the loop roots and a
# knot bead (strengths guide 3.6 / item 10); pairwise review (docs/pr/r9-5-trims) read the twist
# as a pinch at the knot and the wider loops as heavy, so the bow is unchanged.
BOW_W = 5.3               # ribbon width (px)
BOW_TILT = math.radians(60)   # ribbon face tilted from the viewer toward the loop's outside
BOW_TILT_OUT = math.radians(44)   # ... less on the outgoing span, which shows its broad face
BOW_RETURN = 2.6          # px the returning half of each loop sits behind the outgoing half
BOW_THICK = 0.0011        # ribbon thickness (m)
BOW_HALF_DEPTH = 0.5 * BOW_W * math.sin(BOW_TILT)
# Round 11: the loops start inside the knot (their first control point lay just outside its
# end, so the cut root showed beside it); this point is put before BOW_LOOP_L's first.
BOW_ROOT = (319.6, 338.8)
# Knot (round 11): a closed, wrapped knot of the old size. A short band wraps round the
# gathered loop roots; at each end its edge rolls under into a crease, and the bunched loop
# fabric fills the wrap and swells out of it as a low dome the loops leave from (round 10:
# an open 8-sided barrel, through whose ends the loop roots and the cut lacing cords
# showed from 3/4 and side views). Profile from the middle out to the end's pole: (px
# along the knot's axis from its centre, share of the wrap's middle half depth / height).
KNOT_R = (2.6, 3.5)       # px: half depth (y) and half height of the wrap's middle
KNOT_PROFILE = [(0.0, 1.0), (0.8, 0.988), (1.45, 0.955), (1.9, 0.905), (2.2, 0.84),
                (2.42, 0.75), (2.52, 0.655), (2.47, 0.565), (2.32, 0.5),      # the edge rolls under
                (2.36, 0.43), (2.5, 0.35), (2.62, 0.25), (2.69, 0.13)]       # the bunched fabric's dome
KNOT_POLE = 2.71          # px: the dome's pole
KNOT_NT = 24              # samples round the knot's axis

# Ribbon tails (front view, px). Two strands per side meet at the tip.
# name: (control points, ribbon width px, twist gain)
TAILS = {
    'L_wave': ([(320, 342), (310, 387), (286, 420), (273, 440), (298, 468), (303, 480),
                (300, 490), (289, 498), (276, 518), (281, 533), (292, 550), (293, 558)], 3.9, 1.0),
    'L_thin': ([(320, 344), (316, 362), (307, 420), (300, 466), (291, 497), (291, 532),
                (292, 557)], 2.0, 0.5),
    'R_wave': ([(323, 342), (341, 381), (358, 420), (371, 441), (346, 466), (340, 486),
                (356, 500), (369, 520), (360, 537), (350, 558)], 3.9, 1.0),
    'R_thin': ([(323, 344), (328, 362), (335, 420), (348, 470), (358, 500), (354, 532),
                (349, 557)], 2.0, 0.5),
}
TAIL_THICK = 0.0011
# Round 9 tried the traced widths x 1.1-1.4 (strengths guide: 8-10 mm ribbons) and
# 1.3-1.8 mm thickness; pairwise review (docs/pr/r9-5-trims) was split and the wider twists
# added shade islands, so the tails keep the traced widths.
# Stations along a tail: Catmull-Rom samples per control span, then thinned to at most
# this many px apart (wide, thin tails) except in the bends. Round 7: 10 samples and 5 /
# 6.5 px left 12-22 mm between stations across the skirt chains' hand-over below the
# waist, and a lifted skirt stretched those long edges x2.0.
TAIL_SAMPLES = 40
# round 11: 3 px on the thin strands too (round 10: 4 px). With the stations moved by the
# twist sampling, 4 px left 9 mm edges on L_thin across the skirt chains' first segment,
# which stretched x2.32 in sit_stand@60 (round 10: x2.26); at 3 px x2.27.
TAIL_STEP = (3.0, 3.0)
TWIST_MAX = math.radians(50)
# px: twist ~ the turn over this much ribbon (times 1.6 * gain); fitted to the
# round-4 twist of these paths
TWIST_SPAN = 9.2
# Round 11 (clothes-detail review: a hard kink where the twist starts, square stubs at the
# tips and at the roots below the knot):
# - the twist is worked out on the dense path and a station is also kept wherever it has
#   turned TWIST_STEP since the last one, so the stations crowd where the twist changes;
#   it saturates smoothly (C1) toward TWIST_MAX from TWIST_KNEE of it (round 10 clamped
#   hard at TWIST_MAX), and the edge-on lift off the skirt uses a rounded |sin| (round 10:
#   |sin|, a kink in the ribbon's depth wherever the twist changes sign);
# - each strand starts inside the knot (TAIL_ROOT_ROW, TAIL_ROOT_IN of the way to its
#   centre) instead of 1-6 px below it;
# - the tip narrows only to TAIL_TIP_W and is cut at an angle, over TAIL_CUT widths, the
#   point on the edge toward the other strand of its side (the two meet at the tip), so
#   the pair ends in one point as on the sheet (round 10: both strands tapered to 25 %
#   and stopped in square stubs side by side). The cut is sampled TAIL_CUT_STEP px apart.
TWIST_STEP = math.radians(4.0)
TWIST_KNEE = 0.7
TWIST_SIGN_SOFT = 0.12
TAIL_ROOT_ROW = KNOT[1] + 1.0
TAIL_ROOT_IN = 0.6
TAIL_TIP_W = 0.7
TAIL_CUT = 2.2
TAIL_CUT_STEP = 1.0
# px: over the last TAIL_OVER_LEN px the thin strand rises onto the wide one (one ribbon
# thickness and a little), so the two meet at the tip without passing through each other
TAIL_OVER = TAIL_THICK / PX + 0.25
TAIL_OVER_LEN = 26.0
TAIL_PAIRS = {'L_wave': 'L_thin', 'L_thin': 'L_wave', 'R_wave': 'R_thin', 'R_thin': 'R_wave'}
# Tails sit TAIL_PROUD px in front of the skirt's cloth surface, taken from
# levi.parts.skirt.front_surface_y() (its godet folds included; tail x is
# world x, the same frame the skirt uses), plus HIP_LIFT px around the hip,
# where the rig hands the tails from the torso over to the skirt chains and the
# skirt front swings forward with the thighs. Fallback only where the skirt does
# not reach a tail point: the measured envelope below - side-view front edge
# (px from centre, side_mask) and front-view half width.
SKIRT_FRONT = [(340, -92), (360, -98), (380, -106), (400, -110), (420, -111), (440, -115),
               (460, -122), (480, -131), (500, -140.5), (520, -151.5), (540, -161.5),
               (560, -170.5), (580, -176)]
SKIRT_HW = [(340, 50), (400, 100), (450, 140), (500, 180), (560, 230)]
TAIL_PROUD = 2.5
HIP_LIFT = (6.5, 405.0, 30.0)    # extra px, centre row, half width (gaussian)

# Leaf cluster at the neckline, character's left (image right in front view).
# (base col,row) -> (tip col,row), half-width px, forward tilt px.
# Last field: roll px - one edge forward, the other back, so the leaves sit in
# distinct planes and overlap in depth instead of reading as one flat badge.
LEAVES = [
    ((356.0, 248.5), (342.5, 230.0), 5.0, -1.0, -0.9),
    ((359.5, 249.0), (362.0, 225.5), 6.0, 0.0, 0.5),   # the upright, pointed centre leaf
    ((362.0, 249.5), (378.5, 243.0), 5.0, -1.0, 1.0),
]

OUTLINE_FINE = 0.0007     # line weight for thin trims (seams, lacing, ribbons)


# ---------------------------------------------------------------- bodice shape
_HW_T = [(r, w) for r, w, _, _ in PROFILE]
_YF_T = [(r, f) for r, _, f, _ in PROFILE]
_YB_T = [(r, b) for r, _, _, b in PROFILE]


def profile(row):
    """(half_w, y_front, y_back) in metres at a sheet row."""
    return (smooth_interp(_HW_T, row) * PX, smooth_interp(_YF_T, row) * PX,
            smooth_interp(_YB_T, row) * PX)


def _sp(v, e):
    return math.copysign(abs(v) ** e, v)


def _front_raw(t, row):
    """Unnormalised front depth factor at t = x / half_w: superellipse + bust lobes."""
    p = smooth_interp(P_FRONT, row)
    a = min(abs(t), 1.0)
    base = (1.0 - a ** p) ** (1.0 / p)
    b = max(0.0, smooth_interp(BUST, row))
    if b <= 0.0:
        return base
    lobe = math.exp(-((a - BUST_T) / BUST_S) ** 2)
    # the lobe dies out toward the side so the section still closes at |t| = 1
    return base + b * lobe * (1.0 - a ** 6)


@functools.lru_cache(maxsize=None)
def _front_norm_at(row_key):
    """Maximum of _front_raw over t at row row_key / 8: the best of 61 samples
    refined by a parabola through its neighbours, so it varies smoothly with the
    row (no stepping as the maximum moves between samples)."""
    row = row_key / 8.0
    vals = [_front_raw(i / 60.0, row) for i in range(61)]
    k = max(range(61), key=vals.__getitem__)
    if 0 < k < 60:
        a, b, c = vals[k - 1], vals[k], vals[k + 1]
        den = a - 2 * b + c
        if den < 0:
            s = 0.5 * (a - c) / den
            return b - 0.25 * (a - c) * s
    return vals[k]


def _front_norm(row):
    """_front_norm_at on a 1/8 px row grid (cached), linearly interpolated: C0
    in the row, with no steps."""
    k = math.floor(row * 8)
    f = row * 8 - k
    return _front_norm_at(k) * (1 - f) + _front_norm_at(k + 1) * f


def front_factor(t, row):
    """Front depth factor in 0..1, whose maximum over t is 1 (the measured side
    silhouette)."""
    return _front_raw(t, row) / _front_norm(row)


def neck_row_t(t):
    """Neckline row on the front half at t = x / half_w."""
    return smooth_interp(NECK_FRONT, min(abs(t), 1.0))


def lean(t, row):
    """Centre front drawn back toward the chest under the sweetheart dip (px,
    negative = away from the viewer); the turned edge follows it."""
    a = abs(t)
    if a >= 0.3:
        return 0.0
    depth = row - neck_row_t(t) - LIP_START
    return -NECK_LEAN * (1.0 - smoothstep(0.0, 0.3, a)) * (1.0 - smoothstep(-LIP_START, 10.0, depth))


def gather(t, row):
    """Shallow gathers below the neckline (px toward the viewer)."""
    if abs(t) >= 0.78:
        return 0.0
    depth = row - neck_row_t(t) - LIP_START
    if depth >= GATHER_MAX_LEN:
        return 0.0
    # a smoothed |t|: the folds mirror about the centre front without a
    # crease down the t = 0 column
    a = math.sqrt(t * t + GATHER_CENTRE_ROUND ** 2) - GATHER_CENTRE_ROUND
    skew = GATHER_SKEW * smoothstep(0.0, 0.1, -t)
    grow = smoothstep(-1.0, 2.5, depth)
    ridge = trough = 0.0
    for c, s, amp, length in GATHERS:
        # a fold's crest fades out smoothly over its length (C1 at both ends)
        f = amp * grow * (1.0 - smoothstep(0.0, length, depth))
        d = (a - c - skew) / s
        ridge += f * math.exp(-d * d)
        trough += f * math.exp(-(d / 2.2) ** 2)
    return (ridge - GATHER_TROUGH * trough) * (1.0 - smoothstep(0.62, 0.78, a))


def section_point(psi, row, folds=True):
    """Shell point at section angle psi (-pi/2 = centre front, 0 = character's
    left side) and sheet row."""
    hw, yf, yb = profile(row)
    c, s = math.cos(psi), math.sin(psi)
    if s < 0:     # front half
        p = smooth_interp(P_FRONT, row)
        x = hw * _sp(c, 2.0 / p)
        t = x / hw
        yc = (yf + yb) / 2
        y = yc - (yc - yf) * front_factor(t, row) - lean(t, row) * PX
        if folds:
            y -= gather(t, row) * PX
    else:
        x = hw * _sp(c, 2.0 / P_BACK)
        yc = (yf + yb) / 2
        y = yc + (yb - yc) * _sp(s, 2.0 / P_BACK)
    return Vector((x, y, Z(row)))


def front_y(x, row, folds=True):
    """Front surface y of the bodice at world x and sheet row."""
    hw, yf, yb = profile(row)
    t = max(-0.999, min(0.999, x / hw))
    yc = (yf + yb) / 2
    y = yc - (yc - yf) * front_factor(t, row) - lean(t, row) * PX
    if folds:
        y -= gather(t, row) * PX
    return y


def psi_of_t(t, row):
    """Front-half section angle whose x / half_w is t."""
    p = smooth_interp(P_FRONT, row)
    return -math.acos(max(-1.0, min(1.0, _sp(t, p / 2.0))))


def neck_row(psi):
    s, c = math.sin(psi), math.cos(psi)
    if s <= 0:   # front half
        return neck_row_t(abs(c) ** (2.0 / smooth_interp(P_FRONT, 240)))
    return NECK_FRONT[-1][1] + NECK_BACK_DROP * s


# Columns: uniform in x / half_w across the front (gathers, bust, trims); round
# the sides and back they are spread by angle, densest across the underarm /
# side seam (where raised arms and side bends fold the cloth) and sparsest at
# the centre back, which the hair covers.
FRONT_T = 0.7             # front columns are uniform in x / half_w over |t| <= FRONT_T
FRONT_SEG = 42
FRONT_DT = 2 * FRONT_T / FRONT_SEG
BACK_SEG = 42
# Relative column density round the back band: 1 + SIDE_DENSE[0] on a flat-topped
# bump of half width SIDE_DENSE[2] (rad) centred at psi = SIDE_DENSE[1] and its
# mirror pi - SIDE_DENSE[1] (psi = 0 / pi are the sides, -pi/2 the centre front;
# negative values move the bumps toward the front), so the band from the front
# panel's edge round the side seam into the back is dense and the step from the
# front spacing stays small.
SIDE_DENSE = (2.6, -0.15, 0.85)
NV = 24                   # shell rows below the turned edge


def column_t(i):
    """x / half_w of front column i (None for back columns)."""
    return -FRONT_T + FRONT_DT * i if i <= FRONT_SEG else None


def _back_density(psi):
    a, c, s = SIDE_DENSE
    d = 1.0
    for side in (c, math.pi - c):
        d += a * math.exp(-((psi - side) / s) ** 4)
    return d


@functools.lru_cache(maxsize=None)
def _back_angles(row_key):
    """BACK_SEG + 1 section angles from the front band's left end round the back
    to its right end, spaced by the inverse of _back_density."""
    row = row_key / 8.0
    a0 = psi_of_t(FRONT_T, row)
    a1 = psi_of_t(-FRONT_T, row) + 2 * math.pi
    n = 400
    cum = [0.0]
    for k in range(n):
        m = a0 + (a1 - a0) * (k + 0.5) / n
        cum.append(cum[-1] + _back_density(m))
    out = []
    for i in range(BACK_SEG + 1):
        target = cum[-1] * i / BACK_SEG
        k = min(bisect.bisect_left(cum, target), n)
        k = max(k, 1)
        f = (target - cum[k - 1]) / (cum[k] - cum[k - 1])
        out.append(a0 + (a1 - a0) * (k - 1 + f) / n)
    return tuple(out)


def column_angle(i, row):
    """Section angle of column i at a row. Columns run counter-clockwise from
    the front-right (t = -FRONT_T) end of the front band; the back columns run
    from its left end (t = +FRONT_T) round the back (see _back_angles)."""
    t = column_t(i)
    if t is not None:
        return psi_of_t(t, row)
    return _back_angles(round(row * 8))[i - FRONT_SEG]


# Relative row density down the shell, on nominal rows (neckline ~240 to the
# waist): extra rings through the gathers under the turned edge and through the
# under-bust draw-in (rows ~262-300), where the curvature changes fastest.
ROW_DENSE = [(248.0, 9.0, 0.9), (281.0, 17.0, 0.8)]   # (row, sigma px, extra density)


def _row_density(row):
    return 1.0 + sum(a * math.exp(-((row - c) / s) ** 2) for c, s, a in ROW_DENSE)


@functools.lru_cache(maxsize=None)
def row_fractions():
    """NV + 1 fractions (0 = waist edge, 1 = under the turned edge) spaced by the
    inverse of _row_density on a nominal neckline row."""
    top = NECK_FRONT[0][1] + LIP_START
    n = 400
    cum = [0.0]
    for k in range(n):
        cum.append(cum[-1] + _row_density(ROW_BOT + (top - ROW_BOT) * (k + 0.5) / n))
    out = []
    for j in range(NV + 1):
        target = cum[-1] * j / NV
        k = max(min(bisect.bisect_left(cum, target), n), 1)
        f = (target - cum[k - 1]) / (cum[k] - cum[k - 1])
        out.append((k - 1 + f) / n)
    return tuple(out)


def outward_at(psi, row):
    """Horizontal outward normal of the (fold-free) section at psi."""
    e = 1e-3
    a = section_point(psi - e, row, folds=False)
    b = section_point(psi + e, row, folds=False)
    d = b - a
    return Vector((d.y, -d.x, 0.0)).normalized()


def build_shell(col, mat):
    bm = bmesh.new()
    nu = FRONT_SEG + BACK_SEG
    grid = []
    # Front columns keep a constant x / half_w (straight columns in the front
    # view, ~10 of them across each gather fold); their angle is solved per row.
    # The side / back columns follow _back_angles (densest round the side seam).
    # The outer ends of the gathers (|t| 0.7-0.78) fall on side columns; they
    # are evaluated from the same x-based t there, so the surface is continuous.
    top_row = NECK_FRONT[-1][1]
    tops = [neck_row_t(column_t(i)) if column_t(i) is not None else neck_row(column_angle(i, top_row))
            for i in range(nu)]

    for vv in row_fractions():
        ring = []
        for i in range(nu):
            row = ROW_BOT + (tops[i] + LIP_START - ROW_BOT) * vv
            ring.append(bm.verts.new(section_point(column_angle(i, row), row)))
        grid.append(ring)
    # turned edge: rolled lip and inner return, offset along the section normal
    for below, out in LIP:
        ring = []
        for i in range(nu):
            row = tops[i] + below
            a = column_angle(i, row)
            p = section_point(a, row, folds=False) + outward_at(a, row) * (out * PX)
            ring.append(bm.verts.new(p))
        grid.append(ring)
    for a, b in zip(grid, grid[1:]):
        for i in range(nu):
            k = (i + 1) % nu
            # columns run counter-clockwise seen from +Z and rows go up, so
            # (a_i, a_k, b_k, b_i) faces outward on the shell proper; the
            # inner return continues the same winding (facing the body)
            bm.faces.new((a[i], a[k], b[k], b[i]))
    obj = common.new_object(col, 'bodice_shell', bm, [mat])
    common.shade_smooth(obj, 70)
    common.add_outline(obj)
    return obj


# ---------------------------------------------------------------- trims
def section(w, h, sides, kind='ribbon', camber=0.0):
    """Cross-section offsets (along width, along face normal) for half width w
    and half thickness h, in loop order.

    kind 'ribbon': a stadium - two flat faces joined by rounded edges, with
    (sides - 4) / 2 points on each rounded edge, so smooth shading keeps the
    flat faces flat and the edges soft (no hard sliver along the edge).
    camber > 0: both faces also get a centre point raised by camber * w (a
    shallow arched ribbon; it takes two of the sides).
    kind 'round': an ellipse (cords). sides == 4: the old flat rectangle."""
    if sides == 4:
        return [(w, h), (-w, h), (-w, -h), (w, -h)]
    if kind == 'round':
        return [(w * math.cos(2 * math.pi * k / sides), h * math.sin(2 * math.pi * k / sides))
                for k in range(sides)]
    h = min(h, 0.8 * w)               # a tapered tip thins as well as narrows
    c = w - h
    m = (sides - (6 if camber else 4)) // 2
    arc = [math.pi / 2 - math.pi * (k + 1) / (m + 1) for k in range(m)]
    out = [(c, h)]
    out += [(c + h * math.cos(a), h * math.sin(a)) for a in arc]
    out.append((c, -h))
    if camber:
        out.append((0.0, -h + camber * w))
    out.append((-c, -h))
    out += [(-c - h * math.cos(a), -h * math.sin(a)) for a in arc]
    out.append((-c, h))
    if camber:
        out.append((0.0, h + camber * w))
    return out


def band(points, width, thick, face=Vector((0, -1, 0)), widths=None, loop=False, faces=None,
         sides=4, kind='ribbon', camber=0.0):
    """Closed (capped) strip along `points`.

    `face` is the direction the strip's flat side looks toward; `width` lies in
    the plane perpendicular to it. widths: optional per-point width scale.
    loop: the path is a closed loop (no caps). faces: optional per-point face
    direction overriding `face`. sides / kind: the cross-section (see section).
    """
    pts = [Vector(p) for p in points]
    n_pts = len(pts)
    rings = []
    for i, p in enumerate(pts):
        if loop:
            t = (pts[(i + 1) % n_pts] - pts[i - 1]).normalized()
        else:
            t = (pts[min(i + 1, n_pts - 1)] - pts[max(i - 1, 0)]).normalized()
        f = faces[i] if faces else face
        b = f - t * f.dot(t)
        if b.length < 1e-6:
            b = t.orthogonal()
        b.normalize()
        n = t.cross(b).normalized()
        w = width * (widths[i] if widths else 1.0) / 2
        h = thick / 2
        rings.append([p + n * a + b * c for a, c in section(w, h, sides, kind, camber)])
    if not loop:
        return common.loft(rings, closed=True, cap_start=True, cap_end=True)
    bm = common.loft(rings + [rings[0]], closed=True)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-7)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def merge_bms(bms):
    out = bmesh.new()
    for bm in bms:
        me_tmp = bpy.data.meshes.new('_tmp_bodice')
        bm.to_mesh(me_tmp)
        bm.free()
        out.from_mesh(me_tmp)
        bpy.data.meshes.remove(me_tmp)
    return out


def finish(col, name, bms, mat, smooth=True, outline=OUTLINE_FINE, angle=50):
    obj = common.new_object(col, name, merge_bms(bms), [mat])
    if smooth:
        common.shade_smooth(obj, angle)
    common.add_outline(obj, width=outline)
    return obj


def on_shell(dx_px, row, lift_px):
    """Point on the bodice front surface (front-view dx px from centre)."""
    x = dx_px * PX
    return Vector((x, front_y(x, row) - lift_px * PX, Z(row)))


def surface_normal_px(dx, row, y_fn, e=1.0):
    """Viewer-side normal, in world axes, of a front surface y = y_fn(dx, row)
    (all in panel px). z decreases as the row grows, so dy/dz = -dy/drow."""
    gx = (y_fn(dx + e, row) - y_fn(dx - e, row)) / (2 * e)
    gr = (y_fn(dx, row + e) - y_fn(dx, row - e)) / (2 * e)
    return Vector((gx, -1.0, -gr)).normalized()


def shell_normal(dx_px, row):
    """Outward (viewer-side) normal of the bodice front surface."""
    return surface_normal_px(dx_px, row, lambda a, r: front_y(a * PX, r) / PX, e=0.5)


def shell_path(a, b, n, lift_px):
    """Sample a straight front-view line (dx,row)->(dx,row) projected onto the shell."""
    return [on_shell(a[0] + (b[0] - a[0]) * s / n, a[1] + (b[1] - a[1]) * s / n, lift_px)
            for s in range(n + 1)]


def back_psi(dx_px, row):
    """Back-half section angle (0..pi) whose x is dx_px (front-view px)."""
    hw = profile(row)[0] / PX
    t = max(-0.999, min(0.999, dx_px / hw))
    return math.acos(_sp(t, P_BACK / 2.0))


def shell_normal_psi(psi, row):
    """Outward unit normal of the shell at section angle psi and row."""
    du = section_point(psi + 1e-3, row) - section_point(psi - 1e-3, row)
    dv = section_point(psi, row + 0.5) - section_point(psi, row - 0.5)
    n = dv.cross(du).normalized()
    return n if n.dot(outward_at(psi, row)) > 0 else -n


def seam_row(psi):
    """Row of the waist seam line (waist_seam()) at section angle psi."""
    ps, rows = waist_seam()
    return float(np.interp((psi + 0.5 * math.pi) % (2 * math.pi) - 0.5 * math.pi, ps, rows,
                           period=2 * math.pi))


def welt(pts, normals):
    """A seam welt along `pts`: a low rounded strip whose broad face follows the
    shell, fading in under the turned edge."""
    n = len(pts) - 1
    widths = [0.5 + 0.5 * smoothstep(0.0, 2.5, s) for s in range(n + 1)]
    return band(pts, 0.0011, 0.0006, widths=widths, sides=6, faces=normals)


def build_seams(col, mat):
    bms = []
    n = 16
    for sx in (-1, 1):
        start = neck_row_at_dx(SEAM[0][1]) + 0.9     # tucked under the rolled lip
        rows = [start + (348 - start) * s / n for s in range(n + 1)]
        bms.append(welt([on_shell(sx * smooth_interp(SEAM, r), r, 0.4) for r in rows],
                        [shell_normal(sx * smooth_interp(SEAM, r), r) for r in rows]))
    # the back: centre-back and princess seams, from under the turned edge down into
    # the waist piping
    for sx in (-1, 0, 1):
        dx = (lambda r: sx * smooth_interp(BACK_SEAM, r))   # noqa: E731
        start = neck_row(back_psi(dx(BACK_SEAM[0][0]), BACK_SEAM[0][0])) + 0.9
        end = seam_row(back_psi(dx(335.0), 335.0)) + SEAM_END
        rows = [start + (end - start) * s / n for s in range(n + 1)]
        psis = [back_psi(dx(r), r) for r in rows]
        nrm = [shell_normal_psi(p, r) for p, r in zip(psis, rows)]
        pts = [section_point(p, r) + q * (0.4 * PX) for p, r, q in zip(psis, rows, nrm)]
        bms.append(welt(pts, nrm))
    return finish(col, 'bodice_seams', bms, mat, outline=0.0010, angle=80)


# ---------------------------------------------------------------- waist seam line, piping
def _skirt_polar(pts, row, cy):
    """(polar angles, radii) about (0, cy) px of the skirt's outer cloth at a panel
    row, sorted by angle; pts: skirt.profiles() points (px) of its first rings."""
    rows = pts[:, :, 2]
    k = np.clip((rows <= row).sum(1) - 1, 0, rows.shape[1] - 2)
    i = np.arange(len(pts))
    r0, r1 = rows[i, k], rows[i, k + 1]
    f = np.clip((row - r0) / np.maximum(r1 - r0, 1e-9), 0.0, 1.0)[:, None]
    xy = pts[i, k, :2] + (pts[i, k + 1, :2] - pts[i, k, :2]) * f
    a = np.arctan2(xy[:, 0], -(xy[:, 1] - cy))
    o = np.argsort(a)
    return a[o], np.hypot(xy[:, 0], xy[:, 1] - cy)[o]


@functools.lru_cache(maxsize=None)
def waist_seam():
    """(psi, row) arrays round the bodice: per section angle, the row where the
    skirt's outer cloth (skirt.profiles(), as built) comes out of the bodice, i.e.
    the first row from the top at which the shell lies inside it, smoothed round
    the waist (SEAM_SMOOTH). Inside / outside is read along rays from the waist's
    mid depth, where both sections are star-shaped."""
    pts = skirt.profiles(skirt.fold_table())[:, :6, :]
    psi = -0.5 * math.pi + 2 * math.pi * np.arange(SEAM_PSI) / SEAM_PSI
    cy = _waist_cy()
    rows = np.arange(float(pts[:, 0, 2].max()), ROW_BOT + 1e-9, SEAM_ROW_STEP)
    f = np.zeros((len(rows), SEAM_PSI))
    for r, row in enumerate(rows):
        A, R = _skirt_polar(pts, row, cy)
        P = np.array([section_point(float(p), float(row))[:2] for p in psi]) / PX
        a = np.arctan2(P[:, 0], -(P[:, 1] - cy))
        f[r] = np.hypot(P[:, 0], P[:, 1] - cy) - np.interp(a, A, R, period=2 * np.pi)
    out = np.full(SEAM_PSI, float(ROW_BOT))
    for j in range(SEAM_PSI):
        neg = np.nonzero(f[:, j] <= 0.0)[0]
        if not len(neg):
            continue
        k = neg[0]
        if k == 0:
            out[j] = rows[0]
            continue
        f0, f1 = f[k - 1, j], f[k, j]
        out[j] = rows[k - 1] + (rows[k] - rows[k - 1]) * f0 / (f0 - f1)
    sig = SEAM_SMOOTH / 360.0 * SEAM_PSI
    m = int(3 * sig) + 1
    ker = np.exp(-0.5 * (np.arange(-m, m + 1) / sig) ** 2)
    out = np.convolve(np.concatenate([out[-m:], out, out[:m]]), ker / ker.sum(), mode='valid')
    return psi, out


def _waist_cy():
    _, yf, yb = profile(340.0)
    return 0.5 * (yf + yb) / PX


def _skirt_r(pts, a, row, cy):
    A, R = _skirt_polar(pts, max(row, float(pts[:, 0, 2].max())), cy)
    return float(np.interp(a, A, R, period=2 * np.pi))


def piping_path():
    """(centre points, offset directions) of the waist piping, PIPE_N stations
    evenly spaced round the waist seam line. Each station sits on the outer of
    the two cloths there (where the skirt's waist rim stands out of the bodice
    the cord rides its top edge) and is pushed out along the bisector of the
    bodice's and the skirt's normals, so the cord lies in the corner between
    them, touching both (PIPE_FIT of the tangent distance)."""
    pts = skirt.profiles(skirt.fold_table())[:, :6, :]
    top = float(pts[:, 0, 2].max())
    cy = _waist_cy()
    psi, rows = waist_seam()
    P = [section_point(float(p), float(r)) for p, r in zip(psi, rows)]
    arc = [0.0]
    for a, b in zip(P, P[1:] + P[:1]):
        arc.append(arc[-1] + (b - a).length)
    ps = list(psi) + [psi[0] + 2 * math.pi]
    rs = list(rows) + [rows[0]]
    cen, dirs = [], []
    for k in range(PIPE_N):
        s = arc[-1] * k / PIPE_N
        i = max(0, min(bisect.bisect_right(arc, s) - 1, len(ps) - 2))
        f = (s - arc[i]) / max(arc[i + 1] - arc[i], 1e-12)
        p, r = ps[i] + (ps[i + 1] - ps[i]) * f, rs[i] + (rs[i + 1] - rs[i]) * f
        q = section_point(p, r)
        x, y = q.x / PX, q.y / PX
        a = math.atan2(x, -(y - cy))
        rb = math.hypot(x, y - cy)
        rsk = _skirt_r(pts, a, r, cy)
        # the outer cloth (a soft max, so the cord does not kink where the rim takes over)
        re = 0.5 * (rb + rsk + math.hypot(rb - rsk, PIPE_SOFT) - PIPE_SOFT)
        sa, ca = math.sin(a), math.cos(a)
        on = Vector((re * sa * PX, (cy - re * ca) * PX, q.z))
        # skirt normal: horizontal normal of its section, tilted up by its flare
        e = 0.01
        r0, r1 = _skirt_r(pts, a - e, r, cy), _skirt_r(pts, a + e, r, cy)
        dr = (r1 - r0) / (2 * e)
        t = Vector((dr * sa + rsk * ca, -dr * ca + rsk * sa, 0.0))
        nh = Vector((t.y, -t.x, 0.0)).normalized()
        if nh.dot(Vector((sa, -ca, 0.0))) < 0:
            nh = -nh
        slope = _skirt_r(pts, a, max(r, top) + 1.0, cy) - _skirt_r(pts, a, max(r, top), cy)
        ns = (nh + Vector((0.0, 0.0, max(slope, 0.0)))).normalized()
        nb = shell_normal_psi(p, r)
        o = (nb + ns).normalized()
        half = 0.5 * nb.angle(ns)
        d = min(PIPE_FIT * PIPE_R / max(math.cos(half), 0.5), 2.0 * PIPE_R)
        cen.append(on + o * d)
        dirs.append(o)
    # a light smoothing round the loop: the seam line comes from polygons
    n = len(cen)
    sm = [(cen[k - 1] + 2 * cen[k] + cen[(k + 1) % n]) / 4 for k in range(n)]
    return sm, dirs


def build_piping(col, mat):
    pts, dirs = piping_path()
    bm = band(pts, 2 * PIPE_R, 2 * PIPE_R, faces=dirs, loop=True, sides=PIPE_SIDES, kind='round')
    obj = finish(col, 'bodice_piping', [bm], mat, outline=PIPE_LINE, angle=180)
    obj['levi_cast_shadow'] = False      # a thin cord: no hard print on the skirt
    # shading normals mostly those of the cloth corner it lies in (the bisector), so
    # the cord's underside does not break into shade specks along the waist; the
    # outline draws the cord
    cen = np.array([tuple(p) for p in pts])
    out = []
    for v in obj.data.vertices:
        co = np.array(v.co[:])
        k = int(np.argmin(((cen - co) ** 2).sum(1)))
        t = Vector(cen[(k + 1) % len(cen)] - cen[k - 1]).normalized()
        r = Vector(co - cen[k])
        r = (r - t * r.dot(t)).normalized()
        out.append(tuple((PIPE_SHADE * r + (1.0 - PIPE_SHADE) * dirs[k]).normalized()))
    obj.data.normals_split_custom_set_from_vertices(out)
    return obj


def neck_row_at_dx(dx_px):
    """Neckline row at a front-view offset, consistent with the shell: the
    neckline is keyed to x / half_w at the neckline row itself."""
    row = NECK_FRONT[0][1]
    for _ in range(4):
        hw = profile(row)[0] / PX
        row = neck_row_t(min(dx_px / hw, 1.0))
    return row


def ring_bm(center, normal, r_major, r_minor, nu=8, nv=4, squash=0.6):
    """Flat ring (eyelet / grommet) lying on a surface with the given normal."""
    bm = bmesh.new()
    rot = normal.to_track_quat('Z', 'Y').to_matrix()
    rings = []
    for i in range(nu):
        a = 2 * math.pi * i / nu
        ring = []
        for j in range(nv):
            b = 2 * math.pi * j / nv + math.pi / nv
            r = r_major + r_minor * math.cos(b)
            p = Vector((r * math.cos(a), r * math.sin(a), r_minor * squash * math.sin(b)))
            ring.append(bm.verts.new(center + rot @ p))
        rings.append(ring)
    for i in range(nu):
        a, b = rings[i], rings[(i + 1) % nu]
        for j in range(nv):
            k = (j + 1) % nv
            bm.faces.new((a[j], b[j], b[k], a[k]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def cord(a, b, lift_end, lift_mid, n=10, width=LACE_W, thick=LACE_T, lift_to=None):
    """Round cord (a slightly flattened oval section) between two front-view
    points: it leaves the cloth at the ends (inside the eyelets) and bows out
    to lift_mid at its middle. lift_to: the cord instead rises off the cloth
    toward its end, to this lift."""
    pts, faces = [], []
    for s in range(n + 1):
        u = s / n
        dx = a[0] + (b[0] - a[0]) * u
        row = a[1] + (b[1] - a[1]) * u
        if lift_to is None:
            lift = lift_end + (lift_mid - lift_end) * math.sin(math.pi * u) ** 0.6
        else:
            lift = lift_end + (lift_to - lift_end) * smoothstep(0.2, 1.0, u)
        pts.append(on_shell(dx, row, lift))
        faces.append(shell_normal(dx, row))
    # taper the last few % into the eyelets, so the ends do not stop as flat cuts
    widths = [0.75 + 0.25 * smoothstep(0.0, 0.12, min(s / n, 1 - s / n)) for s in range(n + 1)]
    return band(pts, width, thick, faces=faces, widths=widths, sides=6, kind='round')


def build_lacing(col, mat_green):
    bms = []
    rows = EYELET_ROWS
    # criss-cross between the eyelet columns, alternating which strand lies on
    # top so every crossing has a clear over / under
    for i in range(len(rows) - 1):
        for sx in (-1, 1):
            over = (sx > 0) == (i % 2 == 0)
            bms.append(cord((sx * EYELET_DX, rows[i]), (-sx * EYELET_DX, rows[i + 1]),
                            0.0, LACE_OVER if over else LACE_UNDER))
    dr, dw, dh = DIAMOND
    for sx in (-1, 1):
        # top: from under the diamond's side tips out to the first eyelets
        bms.append(cord((sx * dw * 0.4, dr + dh * 0.25), (sx * EYELET_DX, rows[0]), 0.1, 0.8, n=8))
        # last eyelets down into the bow knot, ending inside its wrap
        end_lift = front_y(sx * LACE_END[1] * PX, LACE_END[0]) / PX - (BOW_Y_KNOT + 1.2)
        bms.append(cord((sx * EYELET_DX, rows[-1]), (sx * LACE_END[1], LACE_END[0]), 0.0, 0.95, n=10,
                        lift_to=end_lift))
    # eyelets: flat rings seated on the facings
    for r in rows:
        for sx in (-1, 1):
            dx = sx * (EYELET_DX + 0.4)
            bms.append(ring_bm(on_shell(dx, r, 0.8), shell_normal(dx, r), EYELET_R[0] * PX,
                               EYELET_R[1] * PX))
    return finish(col, 'bodice_lacing', bms, mat_green, angle=80)


def build_facings(col, mat):
    """The lacing panel's two edges: narrow facings under the eyelet columns."""
    bms = []
    r0, r1 = FACING
    for sx in (-1, 1):
        dx = sx * (EYELET_DX + 0.4)
        n = 10
        rows = [r0 + (r1 - r0) * s / n for s in range(n + 1)]
        pts = [on_shell(dx, r, 0.15) for r in rows]
        # rounded ends: a quarter-ellipse width profile over the last ~2 px
        widths = [max(0.4, math.sqrt(max(0.0, 1 - (1 - min(1.0, min(s, n - s) / 2.0)) ** 2)))
                  for s in range(n + 1)]
        bms.append(band(pts, 3.4 * PX, 0.0006, widths=widths, sides=6,
                        faces=[shell_normal(dx, r) for r in rows]))
    return finish(col, 'bodice_facings', bms, mat, outline=0.0008, angle=80)


def build_diamond(col, mat):
    dr, dw, dh = DIAMOND
    bm = bmesh.new()
    # 5x5 grid in diamond (u,v) space, conforming to the shell; the plate is a
    # low cushion (a smooth dome, flat-ish near the rim) so it reads as a
    # shallow rounded stone with one soft terminator instead of four facets
    vs = {}
    g = 4
    for a in range(g + 1):
        for b in range(g + 1):
            u, v = 2 * a / g - 1, 2 * b / g - 1    # -1..1
            dx = (u - v) * 0.5 * dw
            row = dr + (u + v) * 0.5 * dh
            lift = 0.4 + 0.4 * (1 - u * u) * (1 - v * v)
            vs[a, b] = bm.verts.new(on_shell(dx, row, lift))
    for a in range(g):
        for b in range(g):
            bm.faces.new((vs[a, b], vs[a + 1, b], vs[a + 1, b + 1], vs[a, b + 1]))
    sol = bmesh.ops.extrude_face_region(bm, geom=list(bm.faces))
    moved = [e for e in sol['geom'] if isinstance(e, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=(0, 0.0015, 0), verts=moved)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    # smooth over the cushion, sharp at the rim (the side walls are ~90 deg)
    return finish(col, 'bodice_diamond', [bm], mat, outline=0.0009, angle=50)


# ---------------------------------------------------------------- bow
def skirt_surface_y(dx_px, row):
    # the skirt's own cloth surface (with its godet folds) where it exists;
    # the measured envelope above its waist ring
    y = skirt.front_surface_y(dx_px, row)
    if y is not None:
        return y
    front = interp(SKIRT_FRONT, row)
    hw = interp(SKIRT_HW, row)
    t = min(abs(dx_px) / hw, 0.95)
    return front * math.sqrt(1 - t * t)


def bow_y(dx_px, row, back=0.0):
    """Bow depth (px): knot forward, loops wrapping back around the waist but
    kept off the bodice and in front of the skirt's top edge."""
    y = BOW_Y_KNOT + BOW_Y_SLOPE * abs(dx_px)
    # the tilted ribbon reaches BOW_HALF_DEPTH px behind its centre line; the
    # limits leave room for the returning half (up to BOW_RETURN further back)
    lim = front_y(dx_px * PX, min(row, ROW_BOT), folds=False) / PX - 1.5 - BOW_HALF_DEPTH
    if row > 340:
        sk = skirt.front_surface_y(dx_px, row)
        if sk is not None:
            lim = min(lim, sk - 5.0 - BOW_HALF_DEPTH)
    return min(y, lim - BOW_RETURN) + back


def knot_bm():
    """The closed wrapped knot: a solid of revolution about the horizontal axis
    through KNOT (elliptic sections, KNOT_R), along KNOT_PROFILE out to a pole
    at each end. Closed, so no view shows into it."""
    kx = (KNOT[0] - FRONT_CX) * PX
    ky, kr = BOW_Y_KNOT + 1.2, KNOT[1]
    half = KNOT_PROFILE
    prof = [(-x, r) for x, r in reversed(half[1:])] + half
    bm = bmesh.new()
    rings = []
    for x, r in prof:
        ring = []
        for j in range(KNOT_NT):
            a = 2 * math.pi * j / KNOT_NT        # 0 = top, -pi/2 = toward the viewer
            ring.append(bm.verts.new(Vector((kx + x * PX, (ky + KNOT_R[0] * r * math.sin(a)) * PX,
                                             Z(kr - KNOT_R[1] * r * math.cos(a))))))
        rings.append(ring)
    for a, b in zip(rings, rings[1:]):
        for j in range(KNOT_NT):
            k = (j + 1) % KNOT_NT
            bm.faces.new((a[j], a[k], b[k], b[j]))
    for ring, x in ((rings[0], -KNOT_POLE), (rings[-1], KNOT_POLE)):
        pole = bm.verts.new(Vector((kx + x * PX, ky * PX, Z(kr))))
        for j in range(KNOT_NT):
            bm.faces.new((ring[j], ring[(j + 1) % KNOT_NT], pole))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def build_bow(col, mat):
    bms = []
    kx = (KNOT[0] - FRONT_CX)
    for sx in (-1, 1):
        ctrl = [Vector((sx * (c - FRONT_CX), 0, r)) for c, r in BOW_LOOP_L]
        root = Vector((sx * (BOW_ROOT[0] - FRONT_CX), 0, BOW_ROOT[1]))
        path = adaptive(catmull_path([root] + ctrl, 12), 2.8, math.radians(11))
        n = len(path)
        cen = sum(ctrl[1:-1], Vector()) / (len(ctrl) - 2)
        # arc position of the loop's outer turn: the returning half sits behind
        far = max(range(n), key=lambda i: abs(path[i].x))
        arc = [0.0]
        for a, b in zip(path, path[1:]):
            arc.append(arc[-1] + (b - a).length)
        pts, faces, widths = [], [], []
        for i, p in enumerate(path):
            # the return drops behind over ~8 px of ribbon round the outer turn
            back = BOW_RETURN * smoothstep(arc[far] - 5.0, arc[far] + 3.5, arc[i])
            pts.append(Vector((p.x * PX, bow_y(p.x, p.z, back) * PX, Z(p.z))))
            radial = Vector((p.x - cen.x, 0.0, -(p.z - cen.z)))
            radial = radial.normalized() if radial.length > 1e-6 else Vector((sx, 0, 0))
            # the outgoing span shows its broad face; the ribbon rolls over
            # round the outer turn and the return faces out toward the waist side
            roll = smoothstep(arc[far] - 7.0, arc[far] + 7.0, arc[i])
            tilt = BOW_TILT_OUT + (BOW_TILT - BOW_TILT_OUT) * roll
            faces.append((Vector((0, -1, 0)) * math.cos(tilt) + radial * math.sin(tilt)).normalized())
            # gathered into the knot: narrow at both ends of the loop
            d = math.hypot(p.x - kx, p.z - KNOT[1])
            widths.append(0.4 + 0.6 * smoothstep(2.0, 11.0, d))
        bms.append(band(pts, BOW_W * PX, BOW_THICK, widths=widths, faces=faces, sides=10, camber=0.06))
    bms.append(knot_bm())
    return finish(col, 'bodice_bow', bms, mat, outline=0.0011, angle=75)


# ---------------------------------------------------------------- tails
def adaptive(path, max_step, max_turn):
    """Thin a dense polyline: keep a point once the path has run max_step or
    turned max_turn since the last kept one, so the stations crowd into the
    bends and stay sparse along straight runs. The ends are always kept."""
    out = [path[0]]
    run = turn = 0.0
    prev_d = None
    for a, b in zip(path, path[1:-1]):
        d = b - a
        run += d.length
        if prev_d is not None and d.length > 1e-9 and prev_d.length > 1e-9:
            turn += prev_d.angle(d)
        prev_d = d
        if run >= max_step or turn >= max_turn:
            out.append(b)
            run = turn = 0.0
    if (path[-1] - out[-1]).length < 0.35 * max_step and len(out) > 1:
        out.pop()
    out.append(path[-1])
    return out


def tail_surface(dx, row, width_px):
    """Skirt front under a tail point: the most forward skirt point under the
    ribbon's width, so a ribbon crossing a godet fold bridges it."""
    half = 0.5 * width_px + 1.0
    return min(skirt_surface_y(dx + o, row) for o in (-half, 0.0, half))


def soft_twist(v):
    """v clamped to +-TWIST_MAX smoothly (C1): unchanged below TWIST_KNEE of it,
    then easing into the limit."""
    u, k = abs(v) / TWIST_MAX, TWIST_KNEE
    if u > k:
        u = 1.0 if u >= 2 - k else u - (u - k) ** 2 / (4 * (1 - k))
    return math.copysign(u * TWIST_MAX, v)


def tail_twist(path, gain):
    """Twist (rad) at every point of a dense front-view path (Vector(dx, 0, row)):
    the ribbon turns toward edge-on where the path bends, with the bend's sign, so
    a zigzag twists one way and back. The curvature (turn per px of ribbon) is
    smoothed over ~7 px: independent of the sampling."""
    P = np.array([(p.x, p.z) for p in path])
    d = np.diff(P, axis=0)
    turn = np.zeros(len(P))
    a, b = d[:-1], d[1:]
    turn[1:-1] = np.arctan2(a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0], (a * b).sum(1))
    arc = np.concatenate([[0.0], np.cumsum(np.linalg.norm(d, axis=1))])
    ds = 0.5 * (arc[np.minimum(np.arange(len(P)) + 1, len(P) - 1)] - arc[np.maximum(np.arange(len(P)) - 1, 0)])
    w = np.exp(-((arc[None, :] - arc[:, None]) / 7.0) ** 2)
    sm = (w @ turn) / np.maximum(w @ ds, 1e-9) * TWIST_SPAN
    return [soft_twist(1.6 * gain * float(v)) for v in sm], arc.tolist()


def tail_stations(path, phi, arc, max_step, max_turn, fine_from):
    """Indices of the dense path kept as ribbon stations: both ends, and a point
    once the path has run max_step px, turned max_turn or twisted TWIST_STEP
    since the last kept one (every TAIL_CUT_STEP px past arc fine_from)."""
    keep = [0]
    run = turn = 0.0
    prev_d = None
    n = len(path)
    step = max_step
    for i in range(1, n - 1):
        d = path[i] - path[i - 1]
        run += d.length
        if prev_d is not None and d.length > 1e-9 and prev_d.length > 1e-9:
            turn += prev_d.angle(d)
        prev_d = d
        step = TAIL_CUT_STEP if arc[i] >= fine_from else max_step
        if run >= step or turn >= max_turn or abs(phi[i] - phi[keep[-1]]) >= TWIST_STEP:
            keep.append(i)
            run = turn = 0.0
    if len(keep) > 1 and arc[-1] - arc[keep[-1]] < 0.35 * step:
        keep.pop()
    keep.append(n - 1)
    return keep


def _x_at_row(path, row):
    """Front-view dx of a dense path where it crosses `row` last (nearest row if none)."""
    best = None
    for a, b in zip(path, path[1:]):
        if (a.z - row) * (b.z - row) <= 0 and a.z != b.z:
            best = a.x + (b.x - a.x) * (row - a.z) / (b.z - a.z)
    return best if best is not None else min(path, key=lambda p: abs(p.z - row)).x


def build_tails(col, mat):
    bms = []
    dense = {}
    for name, (ctrl, width_px, gain) in TAILS.items():
        cpts = [Vector((c - FRONT_CX, 0, r)) for c, r in ctrl]
        # the strand starts inside the knot, so no cut end shows below it
        kx = KNOT[0] - FRONT_CX
        root = Vector((cpts[0].x + (kx - cpts[0].x) * TAIL_ROOT_IN, 0, TAIL_ROOT_ROW))
        dense[name] = (catmull_path([root] + cpts, TAIL_SAMPLES), width_px, gain)
    for name, (dpath, width_px, gain) in dense.items():
        phi_d, arc_d = tail_twist(dpath, gain)
        total = arc_d[-1]
        arc0 = arc_d[TAIL_SAMPLES]          # the traced start (end of the span from the root)
        cut = TAIL_CUT * width_px * TAIL_TIP_W
        s0 = total - 2.0 * cut               # the cut is spread over the last 2 * cut px
        keep = tail_stations(dpath, phi_d, arc_d, TAIL_STEP[0] if width_px > 3 else TAIL_STEP[1],
                             math.radians(9), s0 - TAIL_CUT_STEP)
        path = [dpath[i] for i in keep]
        phi = [phi_d[i] for i in keep]
        arc = [arc_d[i] for i in keep]
        n = len(path)
        # the edge that runs on to the point: the one toward the other strand of the side
        partner = dense[TAIL_PAIRS[name]][0]
        row_q = path[-1].z - 12.0
        toward = _x_at_row(partner, row_q) - _x_at_row(path, row_q)
        pts, faces, widths = [], [], []
        for i, p in enumerate(path):
            dx, row = p.x, p.z
            nrm = surface_normal_px(dx, row, lambda a, r: tail_surface(a, r, width_px))
            h, c, w = HIP_LIFT
            proud = TAIL_PROUD + h * math.exp(-((row - c) / w) ** 2)
            if width_px < 3:
                # the thin strand lies over the wide one where they meet at the tip
                proud += TAIL_OVER * smoothstep(TAIL_OVER_LEN, 0.0, total - arc[i])
            # an edge-on ribbon stands its half width off the skirt (a rounded |sin|:
            # no kink where the twist changes sign); the offset is along the skirt's normal
            s = math.sin(phi[i])
            off = proud + 0.5 * width_px * (math.hypot(s, TWIST_SIGN_SOFT) - TWIST_SIGN_SOFT)
            # start from the skirt point that the offset carries back onto the
            # traced front-view position (dx, row)
            y = tail_surface(dx - nrm.x * off, row + nrm.z * off, width_px) + nrm.y * off
            # near the knot the tails leave the bow, in front of the skirt top
            k = max(0.0, min(1.0, (372 - row) / 30))
            y = y * (1 - k) + min(y, BOW_Y_KNOT + 1.0) * k
            pts.append(Vector((dx * PX, y * PX, Z(row))))
            tng = (path[min(i + 1, n - 1)] - path[max(i - 1, 0)])
            tng = Vector((tng.x, 0.0, -tng.z)).normalized()
            side = tng.cross(nrm).normalized()
            faces.append((nrm * math.cos(phi[i]) + side * math.sin(phi[i])).normalized())
            # taper: gathered under the knot, narrowing a little toward the cut tip
            ws = 0.7 + 0.3 * smoothstep(0.0, 14.0, arc[i] - arc0)
            ws *= TAIL_TIP_W + (1.0 - TAIL_TIP_W) * smoothstep(0.0, 22.0, total - arc[i])
            widths.append(ws)
        bms.append(cut_band(pts, arc, width_px * PX, TAIL_THICK, widths, faces,
                            8 if width_px > 3 else 6, s0, cut, toward))
    return finish(col, 'bodice_ribbon_tails', bms, mat, outline=OUTLINE_FINE, angle=75)


def cut_band(pts, arc, width, thick, widths, faces, sides, s0, cut, toward):
    """band() along `pts` whose end is cut at an angle: past arc s0 every section
    point slides back along the ribbon by its share of the cut, so the end runs
    on along the edge whose width direction points toward front-view x sign
    `toward` and the other edge stops `cut` (px of arc) short of it."""
    n = len(pts)
    T, B, N, W = [], [], [], []
    for i, p in enumerate(pts):
        t = (pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized()
        b = faces[i] - t * faces[i].dot(t)
        b = (b if b.length > 1e-6 else t.orthogonal()).normalized()
        T.append(t)
        B.append(b)
        N.append(t.cross(b).normalized())
        W.append(width * widths[i] / 2)
    h = thick / 2
    total = arc[-1]
    sgn = 1.0 if N[-1].x * toward >= 0 else -1.0

    def at(s):
        k = max(0, min(bisect.bisect_right(arc, s) - 1, n - 2))
        f = max(0.0, min(1.0, (s - arc[k]) / max(arc[k + 1] - arc[k], 1e-9)))
        lerp = lambda u, v: u + (v - u) * f   # noqa: E731
        return lerp(pts[k], pts[k + 1]), lerp(N[k], N[k + 1]).normalized(), \
            lerp(B[k], B[k + 1]).normalized(), lerp(W[k], W[k + 1])

    rings = []
    for i in range(n):
        ring = []
        for a, c in section(W[i], h, sides):
            if arc[i] <= s0:
                ring.append(pts[i] + N[i] * a + B[i] * c)
                continue
            an = max(-1.0, min(1.0, a / W[i]))
            s_end = total - cut * (1.0 - sgn * an) / 2.0
            p, nn, bb, ww = at(s0 + (arc[i] - s0) * (s_end - s0) / (total - s0))
            ring.append(p + nn * (an * ww) + bb * c)
        rings.append(ring)
    return common.loft(rings, closed=True, cap_start=True, cap_end=True)


# ---------------------------------------------------------------- leaves
# Round 9 (strengths guide 3.11: 3-6 mm cup, a midrib ridge, 1-1.5 mm thick).
# Round 8: 1.8 / 0.6 px, 0.7 mm thick, 0.6 px off the shell.
LEAF_CUP = 2.4            # px the leaf's edges curl toward the viewer
LEAF_RIB = 0.9            # px the midrib ridge stands proud
LEAF_THICK = 0.0012       # m: the blade's thickness (extruded toward the body)
LEAF_OFF = LEAF_THICK / PX + 0.15   # px the blade's face stands off the shell at its base
LEAF_ROOT = (359.5, 250.0)   # shared attachment of the cluster (front col,row)


def leaf_bm(base, tip, half_w, tilt_px, roll_px=0.0):
    """Pointed leaf, cupped (edges curling forward) with a raised midrib;
    base/tip are front-view (col,row)."""
    # bases drawn together into one shared attachment
    base = (base[0] + (LEAF_ROOT[0] - base[0]) * 0.5, base[1] + (LEAF_ROOT[1] - base[1]) * 0.5)
    b = Vector((base[0] - FRONT_CX, 0, base[1]))
    t = Vector((tip[0] - FRONT_CX, 0, tip[1]))
    axis = t - b
    side = Vector((-axis.z, 0, axis.x)).normalized()
    bm = bmesh.new()
    stations = 10
    rows = []
    across = [k / 3.0 - 1.0 for k in range(7)]      # -1..1, midrib at 0
    for s in range(stations + 1):
        # cosine spacing: stations crowd into the rounded base and the tip
        u = 0.5 - 0.5 * math.cos(math.pi * s / stations)
        c = b + axis * u
        # narrow stalk at the base (never zero width: no degenerate faces)
        w = half_w * max(math.sin(math.pi * min(1.0, u * 1.05)) ** 0.8, 0.15)
        cup = LEAF_CUP * math.sin(math.pi * u) ** 0.7
        rib = LEAF_RIB * math.sin(math.pi * u) ** 0.5     # tapers toward both ends
        row_pts = []
        for f in across:
            # U-shaped cup with a soft ridge on the midrib; roll_px turns the
            # leaf's plane (one edge forward, the other back) so the three
            # leaves of the cluster sit in distinct planes
            fwd = cup * f * f + rib * (1 - f * f) ** 2 + roll_px * f * math.sin(math.pi * 0.5 * u)
            q = c + side * (w * f)
            # lie on the curved bodice surface, tips lifting by tilt_px. Depth
            # is sampled no further out than 90 % of the half width: past the
            # shell's side the surface turns backward and would curl the tip.
            x = math.copysign(min(abs(q.x) * PX, 0.9 * profile(q.z)[0]), q.x)
            yy = (front_y(x, q.z) / PX - LEAF_OFF - 1.0 * smoothstep(0.0, 0.35, u)
                  - tilt_px * u - 0.6 * u * u - fwd)
            row_pts.append(Vector((q.x * PX, yy * PX, Z(q.z))))
        rows.append(row_pts)
    na = len(across)
    vs = [[bm.verts.new(p) for p in r] for r in rows[:-1]]
    tip_v = bm.verts.new(rows[-1][na // 2])
    for s in range(stations - 1):
        for j in range(na - 1):
            bm.faces.new((vs[s][j], vs[s][j + 1], vs[s + 1][j + 1], vs[s + 1][j]))
    for j in range(na - 1):
        bm.faces.new((vs[-1][j], vs[-1][j + 1], tip_v))
    # a little thickness so the outline hull reads cleanly
    ext = bmesh.ops.extrude_face_region(bm, geom=list(bm.faces))
    moved = [e for e in ext['geom'] if isinstance(e, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=(0, LEAF_THICK, 0), verts=moved)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def build_leaves(col, mat):
    bms = [leaf_bm(*lf) for lf in LEAVES]
    return finish(col, 'bodice_leaves', bms, mat, outline=0.0012, angle=60)


# ---------------------------------------------------------------- entry
def build(col):
    dress = common.toon_material('dress')
    green = common.toon_material('green')
    leaf = common.toon_material('leaf')
    build_shell(col, dress)
    build_seams(col, dress)
    build_piping(col, dress)
    build_facings(col, dress)
    build_diamond(col, green)
    build_lacing(col, green)
    build_bow(col, green)
    build_tails(col, green)
    build_leaves(col, leaf)
    return col
