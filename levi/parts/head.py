"""Head: Levi's skull and ears with 风堇's face, eyes and mouth (round 11).

head_face is one closed mesh from the crown to a neck tube tucked inside the
body's neck (open only at the two eye openings and the neck's end):
* Her face (assets/hyacine/head.npz, made by tools/prep_hyacine_head.py from the
  风堇 PMX; NOTICE): the front mask without her flat ear cards, her mouth cavity
  with its rolled lips, the two crease strips that fill slits above her eyes.
  It is placed on Levi's head (eye and cheek aligned) and warped
  (levi/parts/_head_graft.py): in the hair-covered zone (forehead above the
  brows, temples, the sides behind the cheek) her surface is pulled onto
  Levi's round-10 skull, which every hair part is fitted to; over the eyes,
  nose, mouth and chin it keeps her shape, the nose toned toward Levi's sheet
  (smaller, lifted). Then her triangles are joined into her quads and
  subdivided once (every morph key alike).
* Levi's skull: the round-10 ring rows (crown down to LOWER_TOP, under the
  eyes; RING_ROWS / ring() stay the pure surface functions hair_front reads),
  less the faces her mask covers, zipped to her border by a strip of
  triangles (the cut drawn to her border first).
* The neck: a loft from the head's lower edge (her under-jaw border, the
  skull's lowest ring behind the ears) into a tube NECK_TUCK inside the body's
  neck, so the visible neck is the body's and a turned head shows no step.
Shading normals come from a smoothed copy without the nose (a membrane spans
it) blended with some of the real normal: Levi's two-tone face with a dot of a
nose. No outline hull at the eye openings and in the mouth, a thin one on the
nose. Levi's modelled ears stay (head_ear_L / _R).

Eyes (from hers, recoloured to Levi's design in the atlas, all opaque):
* head_eye_white_L / _R: her concave white cup, plain white with Levi's soft
  blue-grey lid shadow under the upper lid; rides 頭, takes the lid morphs.
* head_eye_L / _R: her concave iris dish, Levi's green iris (darker upper band,
  rounded darker pupil, navy rim); turns with 目.L / 目.R about
  obj['levi_eye_pivot'], her 目 bone (head-contract option A: the whole
  turn, not her 目先's 30 %).
* head_eye_hilite_L / _R: one vertical oval highlight toward the key light,
  in front of the iris, on 目 with it.
* head_eye_lash_L / _R: her upper lash (with the outer flick), lower lid line
  and brows as navy / mauve strips; her extra lash tuft is left out.
Mouth: her cavity and rolled lips are part of head_face (palette 'mouth');
head_mouth_teeth (her two strips, 'cuff') and head_mouth_tongue ride 頭 and
move by morph only.

Morphs: every name in ALL_MORPHS, from hers where she has it (renamed),
composed from hers otherwise (MORPH_SRC), plus her other expressions
(EXTRA_MORPHS; export_pmx.MORPH_INFO panels). Keys are W(p + d). Levi's
neutral mouth (small and straight) is a little of her own morphs built into
the rest shape (NEUTRAL). Overlays wait inside the head until their key:
照れ (a copy of the cheek skin with the flushed texture), 涙, 汗, はぅ.

Local landmark corrections (spec.L is a +-3 px first pass):
* the face, eyes and neck on ref/front.png are centred on panel column ~321.5,
  not 320, so the whole head is shifted by HEAD_DX (+1.5 px, character's left);
  her face's alignment carries the same shift.
"""
import math
import os
from functools import lru_cache

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

from .. import common, spec, toon
from . import _head_graft as G
from . import _head_levi as HL

PPM = spec.PX_PER_M
CENTER_COL = 321.5               # face midline on ref/front.png
HEAD_DX = (CENTER_COL - spec.PANEL_W / 2) / PPM
N_RING = 72                      # vertices per ring
OUTLINE_PX = spec.OUTLINE_WIDTH * PPM   # ~1.4 px: drawn lines are centred on the surface edge + half this


def zr(row):
    return (spec.SHEET_GROUND_Y - row) / PPM


def yc(col):
    """Side-view panel column -> world y."""
    return (col - spec.PANEL_W / 2) / PPM


def col_of(y):
    return y * PPM + spec.PANEL_W / 2


def row_of(z):
    return spec.SHEET_GROUND_Y - z * PPM


# ---------------------------------------------------------------- measurements
# row: (half-width [px], front profile line [col], widest-point depth [col],
#       back line [col]).  half-width is the surface (line centre - ~0.7 px);
#       front/back are drawn line centres (the outline shell is added on top).
# Rows < ~100 are under the hair and only need to stay inside it; the skull
# is kept at least as wide as the eye level so no ridge rings the face.
TABLE = [
    (43.0, 8.0, 290.0, 300.0, 312.0),
    (46.0, 18.0, 275.0, 300.0, 325.0),
    (52.0, 28.0, 261.0, 300.0, 336.0),
    (60.0, 36.0, 251.0, 300.0, 343.0),
    (70.0, 41.5, 245.0, 300.0, 347.0),
    (82.0, 44.8, 241.5, 299.0, 348.0),
    (95.0, 46.0, 240.5, 296.0, 346.0),
    # eye level -> jaw: the half-width tapers smoothly from the temples to the
    # jaw (no cheekbone shelf); rows < ~126 are under the hair on the front view
    (104.0, 46.3, 240.5, 293.5, 342.0),
    (109.0, 46.2, 240.5, 293.0, 339.5),
    (112.5, 45.5, 240.5, 293.0, 336.5),
    (116.0, 44.0, 240.5, 293.0, 334.0),
    (120.0, 41.8, 239.0, 292.5, 329.0),
    (124.0, 39.3, 237.0, 292.0, 323.0),
    # jaw: the widest point (mid) moves forward steadily from the ear to the
    # chin and stays well in front of the back line, so the side of the face
    # rolls under the jaw over a broad band (not a 3 px sliver that reads as a
    # bevel). The back line above row 153 is hidden behind the neck on the side
    # view and only eases the jaw corner under the ear. Below it the underside
    # runs back nearly level from the chin, like the sheet's under-jaw line
    # (which rises only ~5 rows over ~25 columns), not as a steep wedge.
    (128.0, 36.8, 234.6, 291.5, 317.0),
    (132.0, 34.95, 234.2, 290.0, 309.0),
    (136.0, 33.65, 235.4, 288.0, 300.0),
    (140.0, 32.3, 237.1, 284.8, 296.0),
    (142.0, 31.4, 238.0, 283.0, 294.5),
    (144.0, 30.3, 238.9, 281.8, 292.6),
    (146.0, 28.8, 239.8, 278.8, 289.4),
    (148.0, 26.5, 240.7, 276.0, 284.5),
    (150.0, 23.8, 242.2, 273.0, 279.5),
    (152.0, 20.3, 243.4, 269.9, 275.2),
    (153.5, 17.6, 244.2, 267.3, 273.4),
    (155.5, 14.9, 245.6, 263.2, 270.0),
    (157.0, 11.8, 246.7, 259.4, 266.0),
    (158.3, 9.4, 247.4, 255.6, 261.5),
    (159.5, 6.8, 248.1, 252.6, 257.0),
    # chin tip: a little fuller just above the end ring, so it rounds off
    # instead of running into a cone point (front V kept)
    (160.5, 4.4, 248.8, 250.8, 253.0),
    (161.3, 1.8, 249.6, 250.2, 250.9),
]
# Nose: forward protrusion of the profile at the midline [px] per row. The
# bridge rises out of the forehead from row ~106, so forehead, bridge and tip
# read as one continuous line in profile (no spike on a flat plane).
NOSE = [(106.0, 0.0), (108.5, 0.35), (111.0, 0.95), (113.5, 1.7), (116.0, 2.6),
        (118.0, 3.6), (120.0, 4.5), (122.0, 5.4), (123.5, 6.0), (125.0, 6.3),
        (126.5, 6.1), (128.0, 5.3), (129.5, 4.0), (131.0, 2.7), (132.5, 1.5),
        (134.0, 0.6), (135.5, 0.15), (137.0, 0.0)]
# base front surface of the face under the muzzle [col]: from the forehead it
# recedes smoothly to the chin; TABLE's front column is the midline profile
# Below the nose it recedes steadily (not a vertical plate that bends back
# only at the jaw), meeting the profile again at the chin.
BASE_FRONT = ((112.0, 240.5), (118.0, 240.1), (124.0, 239.2), (130.0, 238.5), (136.0, 239.0),
              (142.0, 240.6), (148.0, 242.6), (153.0, 244.6), (157.0, 246.3), (160.5, 248.2))
MUZZLE_SIGMA = 13.0              # lateral falloff of the muzzle [px]
# lateral falloff [px] by row: a broad bridge narrowing to a small tip
NOSE_SIGMA = ((106.0, 6.5), (116.0, 5.7), (122.0, 5.5), (126.0, 5.5), (137.0, 5.3))
# front half cross-section exponent by row: fuller than an ellipse at eye
# level (with the widest point brought forward, see TABLE) so the face plate
# is broad, relaxing to a plain ellipse at the chin
FRONT_EXP = ((80.0, 2.2), (98.0, 2.8), (118.0, 2.8), (132.0, 2.55), (146.0, 2.5), (155.0, 2.35), (161.3, 2.1))

# Round 9 chin (off by default, see below): a longer, narrower chin (the sheet's front view ends
# the chin on row ~162; the blurred lower face ended it on ~160). Below
# CHIN_FROM (the mouth line, so nothing above it moves) the measured rows
# stretch so the table's tip moves CHIN_DROP px lower, and over the last
# CHIN_NARROW[1] rows above the new tip the half-width narrows by up to
# CHIN_NARROW[0] px per side (in proportion where the chin is narrower than
# CHIN_NARROW[2] px), so the front view's V tapers more. 0 / (0, ...) = round 8.
# Neither won the shuffled pairwise Codex A/B against round 8 (docs/pr/r9-6-face):
# a 3.5 px (5 mm) lower tip with 0.5 px narrowing lost ("stretched", "a hanging
# point" in 3/4 and nods); 1.3 px of narrowing alone (with the rim below) tied
# over both orderings (sol 9-6 for it, astra 13-20 against). So both stay off.
CHIN_DROP = 0.0                   # px (tried 3.5)
CHIN_FROM = 146.0                 # row
CHIN_NARROW = (0.0, 13.0, 8.0)    # px per side (tried 0.5, 1.3), rows above the tip, half-width [px]
CHIN_TIP0 = TABLE[-1][0]          # the measured table's last row


def chin_row(row):
    """Measured (round 8) row -> row of the lengthened chin."""
    if row <= CHIN_FROM:
        return row
    return CHIN_FROM + (row - CHIN_FROM) * (CHIN_TIP0 + CHIN_DROP - CHIN_FROM) / (CHIN_TIP0 - CHIN_FROM)


def chin_narrow(row, hw):
    """Half-width [px] the chin loses on (new) `row` with measured half-width hw."""
    amt, span, ref = CHIN_NARROW
    tip = CHIN_TIP0 + CHIN_DROP
    return amt * float(_smooth(tip - span, tip - 0.35 * span, row)) * min(1.0, hw / ref)


def _chin_rows(table, k=0):
    """`table` with its row (entry k) moved by chin_row."""
    return tuple(tuple(chin_row(v) if i == k else v for i, v in enumerate(e)) for e in table)


def _smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


# (CHIN_DROP != 0 is an experiment: the neck table, LOWER_W_ROWS, LOWER_CHEEK_FILL and NECK_SHADE_ROW
# keep their rows)
TABLE = [(r, hw - chin_narrow(r, hw), f, m, b) for r, hw, f, m, b in _chin_rows(TABLE)]
BASE_FRONT = _chin_rows(BASE_FRONT)
FRONT_EXP = _chin_rows(FRONT_EXP)

# Horizontal rings of the upper head (skull, eyes, nose). Below the last one
# (LOWER_TOP) the lower face, jaw, under-jaw and neck are one surface of
# tilted loops (see lower_loops).
RING_ROWS = ([43.0, 44.5, 47, 50, 54, 59, 65, 72, 80, 88, 94, 98.5]
             + [100.0 + 1.5 * k for k in range(21)]        # eyes and nose: 100 .. 130
             + [131.5])


def pchip(xs, ys, x):
    """Monotone cubic interpolation (no overshoot) of the table columns."""
    xs = np.asarray(xs, float)
    ys = np.asarray(ys, float)
    h = np.diff(xs)
    d = np.diff(ys) / h
    m = np.zeros_like(ys)
    for k in range(1, len(xs) - 1):
        if d[k - 1] * d[k] > 0:
            w1, w2 = 2 * h[k] + h[k - 1], h[k] + 2 * h[k - 1]
            m[k] = (w1 + w2) / (w1 / d[k - 1] + w2 / d[k])
    m[0], m[-1] = d[0], d[-1]
    x = min(max(x, xs[0]), xs[-1])
    k = int(np.clip(np.searchsorted(xs, x) - 1, 0, len(xs) - 2))
    t = (x - xs[k]) / h[k]
    h00, h10 = 2 * t ** 3 - 3 * t ** 2 + 1, t ** 3 - 2 * t ** 2 + t
    h01, h11 = -2 * t ** 3 + 3 * t ** 2, t ** 3 - t ** 2
    return h00 * ys[k] + h10 * h[k] * m[k] + h01 * ys[k + 1] + h11 * h[k] * m[k + 1]


def table_at(row):
    cols = list(zip(*TABLE))
    hw, front, mid, back = (pchip(cols[0], cols[i], row) for i in (1, 2, 3, 4))
    half_line = OUTLINE_PX / 2
    return hw, front + half_line, mid, back - half_line


def muzzle_at(row):
    """How far the measured midline profile (TABLE front) stands in front of
    the face's base front surface (BASE_FRONT) [px]. The table profile is only
    true at the midline: applied across the whole face it would push a band
    from cheek to cheek forward; instead it is a broad muzzle around the
    midline."""
    rows, vals = zip(*BASE_FRONT)
    if row <= rows[0] or row >= rows[-1]:
        return 0.0
    base = pchip(rows, vals, row)
    cols = list(zip(*TABLE))
    return max(0.0, base - pchip(cols[0], cols[2], row))


def nose_at(row):
    rows, vals = zip(*NOSE)
    if row <= rows[0] or row >= rows[-1]:
        return 0.0
    return max(0.0, pchip(rows, vals, row))


def ring_angles(n):
    """Angles around the ring (0 = front centre), denser near the front."""
    out = []
    for k in range(n):
        u = -1.0 + 2.0 * k / n
        out.append(math.pi * math.copysign(abs(u) ** 1.25, u))
    return out


def front_exp(row):
    rows, vals = zip(*FRONT_EXP)
    return float(pchip(rows, vals, row))   # C1: no shading kinks at the table rows


def nose_sigma(row):
    rows, vals = zip(*NOSE_SIGMA)
    return float(np.interp(row, rows, vals))


LOWER_CHEEK = (3.0, 0.62, 145.0, 15.0)   # amplitude px, centre as share of hw, row, row sigma


def lower_cheek(X, row, hw):
    """Forward fullness [px] of the lower cheek between the mouth corners and
    the jaw line, so the cheek rolls round into the chin instead of running
    down to it as a flat plane. Zero at the midline (the profile) and at the
    side (hw: the front-view silhouette); part of the base form, so the
    shading normals see it too."""
    amp, share, r0, sig = LOWER_CHEEK
    u = X / max(hw, 1e-6)
    across = np.clip(np.sin(np.pi * np.clip(u, 0.0, 1.0)) ** 1.5, 0.0, 1.0) * np.exp(-((u - share) / 0.45) ** 2)
    return amp * across * np.exp(-((row - r0) / sig) ** 2)


@lru_cache(maxsize=4096)
def _ring_params(row, detail):
    """Ring shape parameters on `row` (cached: read-only, do not modify)."""
    hw, front, mid, back = table_at(row)
    muzzle = muzzle_at(row)
    front += muzzle
    return dict(hw=hw, mid=mid, muzzle=muzzle, bf=max(mid - front, 0.3), bb=max(back - mid, 0.3),
                nose=nose_at(row) if detail else 0.0, sig=nose_sigma(row), ef=2.0 / front_exp(row))


def _front_y(q, row, xp, c, detail):
    """Side-view column of the face (front half of a ring) at offset xp from
    the midline; c = cos of the ring angle."""
    yp = q['mid'] - q['bf'] * abs(c) ** q['ef'] - q['muzzle'] * math.exp(-(xp / MUZZLE_SIGMA) ** 2)
    yp -= float(lower_cheek(abs(xp), row, q['hw']))
    yp += float(master_offset(abs(xp), row, q['mid'] - yp, c))   # on the base form: detail or not alike
    if detail:
        yp -= q['nose'] * math.exp(-(xp / q['sig']) ** 2)
        # facial relief, faded out where the surface turns to the side
        yp -= float(relief(abs(xp), row)) * _smooth(0.05, 0.3, c)
    return yp


def ring(row, angles, detail=True):
    """One horizontal ring. detail=False leaves out the nose and the facial
    relief: that smooth surface gives the shading normals."""
    q = _ring_params(row, detail)
    hw, ef = q['hw'], q['ef']
    pts = []
    for a in angles:
        s, c = math.sin(a), math.cos(a)
        if c >= 0:   # front half
            xp = hw * math.copysign(abs(s) ** ef, s)
            yp = _front_y(q, row, xp, c, detail)
        else:        # back half: a plain ellipse
            xp = hw * s
            yp = q['mid'] + q['bb'] * abs(c)
        pts.append(Vector((HEAD_DX + xp / PPM, yc(yp), zr(row))))
    return pts


def surf(a, row, detail=True):
    """Head surface point at ring angle a on (any) row."""
    return ring(row, [a], detail)[0]


# ---------------------------------------------------------------- features (front view px)
# Eye (front view, panel px: X = distance from the face midline, row)
EYE_IN, EYE_OUT = 14.0, 41.0     # inner / outer corner X of the painted eye
EYE_TOP_X, EYE_TOP_ROW = 24.0, 107.0   # flattest point of the upper lid


def hexrgb(h):
    h = h.lstrip('#')
    return np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)])


def _quad(p0, p1, p2):
    """Coefficients of the parabola through three (x, y) points."""
    return np.polyfit([p0[0], p1[0], p2[0]], [p0[1], p1[1], p2[1]], 2)


def upper_lid(X):
    """Row of the upper lid line at distance X from the midline: a flat, heavy
    lid that drops to a low outer corner."""
    X = np.asarray(X, float)
    u = (X - EYE_TOP_X) / np.where(X < EYE_TOP_X, EYE_TOP_X - EYE_IN, EYE_OUT - EYE_TOP_X)
    return EYE_TOP_ROW + np.where(X < EYE_TOP_X, 3.4, 5.4) * np.abs(u) ** 3


_LOWER_Q = _quad((EYE_IN, 117.2), (25.0, 125.0), (EYE_OUT - 0.4, 112.8))


def lower_lid(X):
    return np.polyval(_LOWER_Q, np.asarray(X, float))


def lash_thick(X):
    """Height [px] of the upper lash mass below the lid line: ~2.5 px, thicker
    toward the outer corner, tapered at both ends."""
    X = np.asarray(X, float)
    thick = 2.5 + 1.1 * np.clip((X - EYE_IN) / (EYE_OUT - EYE_IN), 0, 1) ** 1.3
    thick = thick * np.clip(0.35 + (X - EYE_IN) / 4.0, 0.35, 1.0)
    return thick * np.clip(0.4 + (EYE_OUT + 1.2 - X) / 4.0, 0.4, 1.0)


def lash_bottom(X):
    """Upper edge of the eye opening: the bottom of the lash mass."""
    return upper_lid(X) + lash_thick(X)


def _outer_corner():
    lo, hi = 30.0, EYE_OUT
    for _ in range(60):
        m = (lo + hi) / 2
        lo, hi = (m, hi) if lash_bottom(m) < lower_lid(m) else (lo, m)
    return (lo + hi) / 2


EYE_OC = _outer_corner()         # outer corner of the opening (lash meets the lower lid), ~39.6


# Mouth: a narrow slit (front view px) on the painted mouth line
MOUTH_ROW = 146.2


def mouth_row(X):
    return MOUTH_ROW - 0.008 * np.asarray(X, float) ** 2


# Upper lid rim (round 9): near the opening the lid stands UPPER_RIM[0] px in
# front of the eyeball (hug) over the relief's lid roll of UPPER_RIM[1] px, so
# the upper lid reads as a ~1.5 mm thick rim in profile and 3/4 (round 8:
# 0.35 / 0.5 px). It tapers in from the inner corner and down to RIM_TAPER[2]
# of itself at the outer corner (X ranges [px]).
# The 1.0 / 1.2 px rim (tapered: ((EYE_IN - 2, EYE_IN + 6), (EYE_OC - 9,
# EYE_OUT + 2), 0.55)) did not win the pairwise A/B: gpt-6.1-sol preferred
# round 8's outer upper lid in 3/4 in both orderings ("terminates more
# cleanly", "less like a projecting strip"). The defaults are round 8's.
UPPER_RIM = (0.35, 0.5)
RIM_TAPER = ((EYE_IN - 9.0, EYE_IN - 8.0), (100.0, 101.0), 1.0)   # (no taper)


def rim_along(X):
    (a0, a1), (b0, b1), out = RIM_TAPER
    return _smooth(a0, a1, X) * (1.0 - (1.0 - out) * _smooth(b0, b1, X))


def relief(X, R):
    """Forward offset [px, + toward the viewer] of the face surface at (X, row):
    a shallow hollow around the eye with the upper and lower lid rims, soft
    cheeks, and the lips / chin articulation of the profile. Applied along -Y
    only, so the front-view projection of the painted features does not move."""
    X = np.asarray(X, float)
    R = np.asarray(R, float)
    Xl = np.clip(X, EYE_IN, EYE_OUT)          # the lid curves run off steeply past the corners
    y_up, y_lo = upper_lid(Xl), lower_lid(Xl)
    along = _smooth(EYE_IN - 4.0, EYE_IN + 1.0, X) * (1.0 - _smooth(EYE_OUT + 0.5, EYE_OUT + 5.0, X))
    # orbit: a soft hollow around the opening (the eyeball sits in it)
    e_d = np.maximum.reduce([y_up - R, R - y_lo, EYE_IN - X, X - EYE_OUT])
    socket = -0.55 * _smooth(4.0, -1.0, e_d)
    # upper lid: a soft rim that wraps over the top of the eye (carries the
    # lashes); the lower lid only a faint roll into the cheek
    lid = UPPER_RIM[1] * np.exp(-((R - (y_up + 1.0)) / 2.3) ** 2) * along * rim_along(X)
    lower = 0.12 * np.exp(-((R - (y_lo + 1.0)) / 2.0) ** 2) * along
    cheek = 0.6 * np.exp(-((X - 25.0) / 11.0) ** 2 - ((R - 131.0) / 9.0) ** 2)
    # lips and chin: restrained upper lip, lower lip and fold (kept faint and
    # narrow: wide bands read as shelves across the lower face)
    lips = (0.15 * np.exp(-((R - 143.6) / 1.8) ** 2) * np.exp(-(X / 5.0) ** 2)
            + 0.08 * np.exp(-((R - 148.3) / 1.4) ** 2) * np.exp(-(X / 4.5) ** 2)
            - 0.05 * np.exp(-((R - 151.0) / 2.0) ** 2) * np.exp(-(X / 6.0) ** 2))
    return socket + lid + lower + cheek + lips


def _eye_opening_d(X, R):
    """Signed distance-like value of the round-10 eye opening [px] (negative
    inside): round outside the corners, and the lid curves are not followed past
    them (they run off steeply). The shape-master sampling of the skull leaves the
    old opening out."""
    X = np.asarray(X, float)
    R = np.asarray(R, float)
    Xl = np.clip(X, EYE_IN, EYE_OC)
    dx = np.maximum(EYE_IN - X, X - EYE_OC)
    dr = np.maximum(lash_bottom(Xl) - R, R - lower_lid(Xl))
    return np.where((dx > 0) | (dr > 0), np.hypot(np.maximum(dx, 0), np.maximum(dr, 0)), np.maximum(dx, dr))


# ---------------------------------------------------------------- textures
# flat colour swatches (an ATLAS_N x ATLAS_N grid of ATLAS_CELL px cells) for
# the small geometric decals: real lashes, highlights, tears, sweat, the はぅ
# strokes. (colour, shaded): shaded swatches take the toon shade like skin.
ATLAS = {
    'lash': ('#262A40', False),
    'white': ('#FFFFFF', False),
    'tear': ('#A9D9F2', False),
    'sweat': ('#C4E9F8', False),
    'tear_line': ('#6FA9CF', False),
    'tongue': ('#EE9C9A', True),        # lighter than the cavity ('mouth'), so ぺろっ reads
}
ATLAS_N, ATLAS_CELL = 4, 4


def atlas_pixels():
    n = ATLAS_N * ATLAS_CELL
    out = np.ones((n, n, 4), np.float32)
    for k, (hexc, shaded) in enumerate(ATLAS.values()):
        r, c = divmod(k, ATLAS_N)
        out[r * ATLAS_CELL:(r + 1) * ATLAS_CELL, c * ATLAS_CELL:(c + 1) * ATLAS_CELL, :3] = hexrgb(hexc)
        out[r * ATLAS_CELL:(r + 1) * ATLAS_CELL, c * ATLAS_CELL:(c + 1) * ATLAS_CELL, 3] = 1.0 if shaded else 0.0
    return out


def atlas_uv(key):
    """UV of the centre of a swatch (rows top->bottom in atlas_pixels)."""
    r, c = divmod(list(ATLAS).index(key), ATLAS_N)
    n = ATLAS_N * ATLAS_CELL
    return ((c + 0.5) * ATLAS_CELL / n, 1.0 - (r + 0.5) * ATLAS_CELL / n)


def face_image(pixels, name):
    img = bpy.data.images.get(name)
    if img:
        bpy.data.images.remove(img)
    h, w = pixels.shape[:2]
    img = bpy.data.images.new(name, w, h, alpha=True, float_buffer=False)
    img.colorspace_settings.name = 'sRGB'
    img.alpha_mode = 'CHANNEL_PACKED'
    px = pixels[::-1]      # Blender images start at the bottom row
    img.pixels.foreach_set(px.ravel())
    img.pack()
    return img


def face_material(pixels, name='toon_face', image='levi_face_tex'):
    """Two-tone toon material like levi.toon, with the lit colour from the face
    texture and the shade colour = texture * (skin shade / skin base) where the
    texture alpha marks skin (decals stay unshaded).

    The decals are not skin: the material's toon_gradient is the 'eye' key,
    and the per-vertex toon_grad attribute (set_eye_region) marks the vertices
    on them, so render.py's region pass labels them as eyes."""
    old = bpy.data.materials.get(name)
    if old:
        bpy.data.materials.remove(old)
    mat = bpy.data.materials.new(name)
    mat['toon_key'] = 'skin'
    mat['toon_gradient'] = 'eye'
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.clear()
    out = nodes.new('ShaderNodeOutputMaterial')
    diff = nodes.new('ShaderNodeBsdfDiffuse')
    s2r = nodes.new('ShaderNodeShaderToRGB')
    links.new(diff.outputs['BSDF'], s2r.inputs['Shader'])
    bw = nodes.new('ShaderNodeRGBToBW')
    links.new(s2r.outputs['Color'], bw.inputs['Color'])
    ramp = toon._ramp(nodes, links, bw.outputs['Val'])

    tex = nodes.new('ShaderNodeTexImage')
    tex.image = face_image(pixels, image)
    tex.interpolation = 'Linear'
    tex.extension = 'EXTEND'
    pa = spec.PALETTE['skin']
    base, shade = toon.srgb(pa['base']), toon.srgb(pa['shade'])
    ratio = tuple(shade[i] / base[i] for i in range(3)) + (1.0,)
    shaded = nodes.new('ShaderNodeMix')
    shaded.data_type = 'RGBA'
    shaded.blend_type = 'MULTIPLY'
    shaded.inputs['Factor'].default_value = 1.0
    links.new(tex.outputs['Color'], shaded.inputs[6])
    shaded.inputs[7].default_value = ratio
    # where alpha (skin mask) is 0 the shade colour equals the lit colour
    shade_col = toon._mix(nodes, links, tex.outputs['Alpha'], tex.outputs['Color'], shaded.outputs[2])
    col = toon._mix(nodes, links, ramp.outputs['Color'], shade_col, tex.outputs['Color'])
    emit = nodes.new('ShaderNodeEmission')
    links.new(col, emit.inputs['Color'])
    links.new(emit.outputs['Emission'], out.inputs['Surface'])
    mat.diffuse_color = base
    return mat


# ---------------------------------------------------------------- lower face: one soft surface
# Below the upper head's last ring (LOWER_TOP, just under the eyes) the lower
# face, jaw, chin, under-jaw, throat and the top of the neck are one surface:
# head_face continues into the neck, so there is no seam or buried tube at
# the jaw. Its shape is the measured head (TABLE: front-view half-width, the
# side-view profile and under-jaw line; below the nose with rounder, U-shaped
# plan sections and a smaller muzzle) united with the neck (NECK), as an
# occupancy field on a voxel grid that is blurred (gaussian LOWER_BLUR). The
# blur rounds the jaw edge, the chin and the under-jaw/throat junction into
# one soft surface (a fillet where the jaw meets the neck), while broad
# surfaces stay where they are. It fades in below the nose (LOWER_W_ROWS), so
# the lower face meets the upper head's last ring exactly.
# The mesh: loops from that ring down to the neck's open end. Each column is a
# fan of rays from a point inside (LOWER_O) swept from the ring's vertex to
# the neck end's; a vertex is where its ray leaves the surface. Each column's
# loops are spaced evenly over three spans: the face down to the jaw edge, the
# under-jaw band (where the surface faces down more than JAW_DOWN) and the
# neck, so loops run along the jaw line and round the jaw edge and the throat.
LOWER_TOP = RING_ROWS[-1]
FIELD_BOX = ((0.0, 50.0), (214.0, 332.0), (114.0, 190.0))   # |X|, col, row [px]
FIELD_VOX = 0.5                   # px per voxel
LOWER_BLUR = 2.6                  # px: gaussian sigma of the occupancy blur
LOWER_W_ROWS = (LOWER_TOP, 139.0)   # the blur fades in over these rows ...
LOWER_W_NOSE = (7.0, 134.0, 141.0)  # ... and in below the nose: X sigma, rows
# front half cross-section exponent below the nose (blended in from front_exp
# over LOWER_RAMP rows, slowly: near the face's sides a lower exponent moves
# the surface back by several px): rounder toward the jaw, so the plan
# sections are U-shaped (narrowing to the chin) instead of boxes with a flat
# front and square corners
LOWER_FRONT_EXP = _chin_rows(((131.5, 2.55), (140.0, 2.25), (148.0, 2.08), (156.0, 2.0), (161.3, 2.0)))
LOWER_RAMP = (LOWER_TOP, 146.0)
LOWER_MUZZLE = 0.45               # share of the muzzle kept below the nose; the rest goes into the base front
# neck: row, front col, back col, half-width [px] (surface). The back is the
# round-5 neck's; below row 158 the throat follows the sheet's line (cols
# 272-275 over rows 158-170, 0.5-1.5 px in front of it); above, it leans
# forward into the under-jaw, so the blur's fillet spreads over a longer turn.
NECK = ((128.0, 272.0, 304.0, 15.8), (138.0, 270.0, 304.5, 16.0), (146.0, 268.5, 303.0, 15.5),
        (151.0, 268.3, 301.6, 15.3), (155.0, 269.4, 300.8, 15.1), (158.0, 271.0, 300.6, 14.95),
        (161.0, 272.8, 300.1, 14.85), (165.0, 273.8, 300.0, 14.8), (169.0, 275.2, 300.6, 14.8),
        (174.0, 276.9, 302.1, 14.8), (190.0, 277.5, 303.0, 14.8))
NECK_END = 174.0                  # the open end of the neck: inside the body's neck, under the choker
LOWER_O = ((0.0, 287.0, 142.0), (0.0, 290.0, 128.0))   # ray origins (X, col, row): front, back columns
LOWER_FAN = 240                   # rays per column when laying the loops out
LOOPS_FACE, LOOPS_UNDER, LOOPS_NECK = 36, 15, 16
JAW_DOWN = 0.62                   # the under-jaw band: the surface faces down more than this
# below the nose only: a little more fullness in the cheek beside the mouth
# (amplitude px, centre as share of the half-width, row, row sigma), so it
# rounds into the chin instead of reading as a plane
LOWER_CHEEK_FILL = (0.9, 0.5, 146.0, 6.0)
# finer than the blur, applied to the blurred surface (forward along -Y, on
# surfaces facing forward): the shallow fold under the lower lip and the chin
# pad below it, so the mouth-to-chin profile is not one straight line.
# (amplitude px (+ forward), row, row sigma, X sigma)
LOWER_RELIEF = _chin_rows(((-0.45, 150.4, 1.9, 7.0), (0.35, 155.6, 2.6, 6.0)), k=1)


def lower_relief(X, row):
    """Forward offset [px] of the lower face's fine relief at (X, row)."""
    X, row = np.asarray(X, float), np.asarray(row, float)
    return sum(a * np.exp(-((row - r0) / sr) ** 2 - (X / sx) ** 2) for a, r0, sr, sx in LOWER_RELIEF)


def _px(p):
    """World point -> (X px from the midline, side-view col, row)."""
    return ((p[0] - HEAD_DX) * PPM, col_of(p[1]), row_of(p[2]))


def _world(P):
    return Vector((HEAD_DX + P[0] / PPM, yc(P[1]), zr(P[2])))


def field_exp(row):
    """Front half cross-section exponent of the lower-face field."""
    e0 = front_exp(row)
    t = float(_smooth(*LOWER_RAMP, row))
    if t <= 0.0:
        return e0
    rows, vals = zip(*LOWER_FRONT_EXP)
    return e0 + (float(np.interp(row, rows, vals)) - e0) * t


def front_y_vec(row, X, detail, master=True):
    """_front_y vectorized over X >= 0 (array), with the lower face's rounder
    sections and smaller muzzle (identical to ring() down to LOWER_TOP). The
    muzzle's removed share moves the base front forward, so the midline stays
    on the measured profile. master=False: without the shape master's depth
    (what master_dy is measured against)."""
    q = _ring_params(row, detail)
    hw = q['hw']
    ef = 2.0 / field_exp(row)
    keep = 1.0 + (LOWER_MUZZLE - 1.0) * float(_smooth(*LOWER_RAMP, row))
    u = np.clip(X / hw, 0.0, 1.0)
    c = np.sqrt(np.clip(1.0 - u ** (2.0 / ef), 0.0, 1.0))
    yp = (q['mid'] - (q['bf'] + q['muzzle'] * (1.0 - keep)) * c ** ef
          - q['muzzle'] * keep * np.exp(-(X / MUZZLE_SIGMA) ** 2) - lower_cheek(X, row, hw))
    amp, share, r0, sig = LOWER_CHEEK_FILL
    yp = yp - (amp * float(_smooth(*LOWER_RAMP, row)) * np.exp(-((row - r0) / sig) ** 2)
               * np.sin(np.pi * u) ** 1.5 * np.exp(-((u - share) / 0.35) ** 2))
    if master:
        yp = yp + master_offset(X, row, q['mid'] - yp, c)
    if detail:
        yp = yp - q['nose'] * np.exp(-(X / q['sig']) ** 2) - relief(X, row) * _smooth(0.05, 0.3, c)
    return yp


# ---------------------------------------------------------------- shape master (round 10)
# The face front takes its depth from the shape master's 'head' surface
# (levi/shape.py): master_dy(row) [px, + = back] is added to the section
# functions' front (_front_y, front_y_vec), so the upper rings, the lower
# face's field, face_point and with them the patches, the eye fit and every
# morph target follow; along -Y only, so the front-projected texture stays on
# its panel pixels and the front-view outline (the half-width) stays ours.
#
# What the master says (measured once, master_fit): its upper face (brow,
# eyes) meets ours, but below the eyes its face recedes, ~1.5-2.5 cm behind
# ours over the cheeks, mouth and chin (a flatter face, less of a muzzle). Its
# finer forms do not carry over: blank eye sockets, no mouth, a small sharp
# nose with a nostril hollow, a V chin, and label noise (bang strands
# labelled head). Following them sample by sample left ridges, a pinched nose
# root and a notched profile, and lost the pairwise A/B to round 9 (16 of 16).
# So only the broad form is taken: the median set-back over the cheek band
# (MASTER_CHEEK, beside the nose, outside the sockets and the mouth) per row,
# fitted by one smooth ramp A * smoothstep(MASTER_RAMP0, r1, row), and
# MASTER_FOLLOW of it applied. Our own nose, lids, mouth and chin ride on it
# with their shapes; the sides fade out (master_depth), so the jaw and the
# front-view outline stay ours. The forehead and skull (under the hair_front
# cap) do not move: the ramp is 0 above MASTER_RAMP0 (mid-eye: the lower lid
# would go back more than the upper one: master_offset moves the opening
# and its rim back rigidly instead). The fit compares the master with our
# analytic section (front_y_vec); below LOWER_TOP the mesh is its blurred
# field, within ~1 px of it on the cheeks. The set-back is applied to the
# base form (before the nose and the relief), so the shading-normal head
# gets the same. The ramp ends no
# earlier than MASTER_RAMP1[0] (the data alone would end it at row ~129, a
# shelf under the eyes).
# How much to follow, by the order-balanced pairwise Codex A/B against round
# 9 (8 face close-ups, cel + clay; consistent picks new-old, astra / sol):
# 0.25: 8-0 / 8-0 ("shorter, rounder chin", "cleaner jaw curve"); 0.35:
# 6-2 / 8-0; 0.45: 0-8 / 6-2; 0.6: 0-8 / 0-8 and 1.0: 0-8 / 0-8 ("scooped
# mouth area", "hooked chin": the chin's thin wedge saturates in
# master_depth while the mouth goes back).
MASTER_GRID = ((0.0, 48.0), (96.0, 161.0))      # X, rows [px], 1 px steps
MASTER_BAND = (-4.0, 32.0)                      # accepted target - ours [px] (outside: stray labels)
MASTER_FACING = 0.3                             # the target faces forward: |n_y| at least (its winding varies)
MASTER_CHEEK = (6.0, 26.0)                      # X band [px] the set-back is read over
MASTER_EYE = 8.0                                # px: samples this close to the eye opening are dropped
MASTER_MOUTH = (8.0, 3.5)                       # dropped around the slit: half-width, half-height [px]
MASTER_RAMP0 = 112.0                            # row the set-back starts from (0 above)
MASTER_RAMP1 = (146.0, 160.0)                   # search range of the row it is complete by
MASTER_FOLLOW = 0.25                            # share of the master's set-back taken


@lru_cache(maxsize=1)
def master_fit():
    """(A [px], r1 [row]): the master's face set-back behind ours, fitted as
    A * smoothstep(MASTER_RAMP0, r1, row) to the per-row median over the
    cheek band."""
    from .. import shape
    (x0, x1), (r0, r1) = MASTER_GRID
    Xs = np.arange(x0, x1 + 0.5)
    Rs = np.arange(r0, r1 + 0.5)
    ours = np.array([front_y_vec(r, Xs, True, master=False) for r in Rs])          # (rows, X) cols
    hw = np.array([_ring_params(r, True)['hw'] for r in Rs])
    gx = np.gradient(ours, Xs, axis=1)
    gr = np.gradient(ours, Rs, axis=0)
    ok_ours = (Xs[None, :] < 0.92 * hw[:, None]) & (np.hypot(gx, gr) < 2.5)        # ours faces forward
    D = np.full((2,) + ours.shape, np.nan)
    for k, sg in enumerate((1.0, -1.0)):
        O = np.array([(HEAD_DX + sg * X / PPM, -1.0, zr(r)) for r in Rs for X in Xs])
        p, _, n, _ = shape.ray('head', O, [(0.0, 1.0, 0.0)], occluders=False)
        with np.errstate(invalid='ignore'):
            d = np.where(np.abs(n[:, 1]) >= MASTER_FACING, col_of(p[:, 1]), np.nan).reshape(ours.shape) - ours
            D[k] = np.where((d >= MASTER_BAND[0]) & (d <= MASTER_BAND[1]), d, np.nan)
    X2, R2 = np.meshgrid(Xs, Rs)
    mx, my = MASTER_MOUTH
    keep = (ok_ours & (X2 >= MASTER_CHEEK[0]) & (X2 <= MASTER_CHEEK[1])
            & (np.asarray(_eye_opening_d(X2, R2)) >= MASTER_EYE) & ~((X2 < mx) & (np.abs(R2 - mouth_row(X2)) < my)))
    rows, med = [], []
    for j, r in enumerate(Rs):
        v = D[:, j][:, keep[j]]
        v = v[np.isfinite(v)]
        if len(v) >= 5:
            rows.append(r)
            med.append(float(np.median(v)))
    rows, med = np.array(rows), np.array(med)
    if len(rows) < 10:
        raise ValueError(f'head: the shape master covers only {len(rows)} rows of the cheeks')
    best = None
    for r1 in np.arange(MASTER_RAMP1[0], MASTER_RAMP1[1] + 0.5, 1.0):
        s = _smooth(MASTER_RAMP0, r1, rows)
        a = float((s * med).sum() / max((s * s).sum(), 1e-9))
        err = float(((a * s - med) ** 2).sum())
        if best is None or err < best[0]:
            best = (err, a, float(r1))
    err, a, r1 = best
    a = max(a, 0.0)                                 # a set-back only: never in front of the measured profile
    print(f'HEAD shape master: face set-back {a:.1f} px from row {MASTER_RAMP0:.0f} to {r1:.0f} '
          f'({len(rows)} rows sampled, rms {math.sqrt(err / len(rows)):.1f} px); taking {MASTER_FOLLOW:.0%}')
    return a, r1


def master_dy(row):
    """Set-back [px, + = back] the shape master gives the face front on `row`
    (the same across the face; master_depth fades it out at the sides).
    master_fit is cached: change the MASTER_* fit parameters before the
    first head query, not between builds in one process."""
    a, r1 = master_fit()
    t = min(max((row - MASTER_RAMP0) / (r1 - MASTER_RAMP0), 0.0), 1.0)
    return MASTER_FOLLOW * a * t * t * (3.0 - 2.0 * t)


MASTER_EYE_KEEP = (2.0, 14.0)     # px from the eye opening: the eye's rigid set-back .. the ramp's
MASTER_EYE_ROW = 125.0            # the eye takes the ramp's set-back on this row (the lower lid's lowest)


def master_offset(X, row, depth, c):
    """Set-back [px, + back] of the face front at (|X|, row), `depth` px in
    front of its section's widest point (ring angle cos c): the ramp
    (master_dy, shaped by master_depth), except on and around the eye
    opening, which goes back rigidly by the ramp's value on its lower lid
    (MASTER_EYE_ROW), blended out over MASTER_EYE_KEEP. Rigidly: no fade or
    saturation there either, so the rim keeps its shape exactly, fit_eyeball
    refits the same sphere moved back, and the lids' morph paths, the socket
    sleeve and the eye checks stay ours. (The ramp across the opening tilted
    the rim: the half-way blink went 1.46 -> 1.54 mm and はぅ=0.5 1.48 ->
    1.60 mm through the turned eyeball; with the side fade on the rigid part
    the outer corner lagged 0.5 px and キリッ's socket sleeve crossed the
    gaze. Holding the eye at 0 left a groove under it, which lost the A/B.)"""
    k = _smooth(*MASTER_EYE_KEEP, _eye_opening_d(X, row))
    return k * master_depth(master_dy(row), depth, c) + (1.0 - k) * master_dy(MASTER_EYE_ROW)


MASTER_FACE_C = (0.0, 0.3)        # cos of the ring angle: the set-back faded out .. in toward the sides
MASTER_KEEP = 0.25               # share of the front's depth (in front of the widest point) a set-back keeps


def master_depth(d, depth, c):
    """The set-back d >= 0 [px] applied to a front point `depth` px in front of the
    section's widest point (ring angle cos c): a set-back saturates softly
    at (1 - MASTER_KEEP) of that depth, so toward the sides (depth -> 0) it
    fades out and the section never folds behind its widest point."""
    if np.ndim(d) == 0 and np.ndim(depth) == 0 and np.ndim(c) == 0:
        if d <= 0.0:
            return 0.0
        s = (1.0 - MASTER_KEEP) * max(float(depth), 1e-6)
        return s * math.tanh(float(d) / s) * float(_smooth(*MASTER_FACE_C, c))
    d = np.maximum(np.asarray(d, float), 0.0)
    s = (1.0 - MASTER_KEEP) * np.maximum(np.asarray(depth, float), 1e-6)
    return s * np.tanh(d / s) * _smooth(*MASTER_FACE_C, c)


def _occ(d):
    """Anti-aliased occupancy (the blur's input) from a signed distance [px]
    (positive inside)."""
    return np.clip(0.5 + d / FIELD_VOX, 0.0, 1.0)


FAR = 50.0                        # px: 'distance' outside every section


def _head_plane(row, X, C, detail):
    """Signed in-plane distance [px, positive inside] to the measured head's
    section on `row` at X (nx,) >= 0 and columns C (nc,): (nc, nx). The
    section is the front half (front_y_vec) and the back half ellipse of
    ring(); the distance is approximate, but zero exactly on the section."""
    if not TABLE[0][0] <= row <= TABLE[-1][0]:
        return np.full((len(C), len(X)), -FAR)
    q = _ring_params(row, detail)
    hw = q['hw']
    Xc = np.minimum(X, hw)
    yf = front_y_vec(row, Xc, detail)
    yb = q['mid'] + q['bb'] * np.sqrt(np.clip(1.0 - (Xc / hw) ** 2, 0.0, 1.0))
    gf, gb = np.gradient(yf, X), np.gradient(yb, X)
    df = (C[:, None] - yf[None, :]) / np.sqrt(1.0 + gf[None, :] ** 2)
    db = (yb[None, :] - C[:, None]) / np.sqrt(1.0 + gb[None, :] ** 2)
    d = np.minimum(np.minimum(df, db), (hw - X)[None, :])
    # near the outline the distance is exact (distance to the section's
    # polyline): the estimate above depends on where the section's tip falls
    # between the grid's X samples, which would leave ripples from row to row
    near = np.abs(d) < 2.5
    if near.any():
        a = np.linspace(0.0, math.pi / 2, 160)
        Xs = hw * np.sin(a) ** (2.0 / field_exp(row))
        Ys = front_y_vec(row, Xs, detail)
        Xb = hw * np.sin(a[::-1])
        Yb = q['mid'] + q['bb'] * np.cos(a[::-1])
        px = np.concatenate([-Xs[:0:-1], Xs, Xb[1:], -Xb[-2::-1]])
        py = np.concatenate([Ys[:0:-1], Ys, Yb[1:], Yb[-2::-1]])
        ci, xi = np.nonzero(near)
        Q = np.stack([X[xi], C[ci]], 1)
        A = np.stack([px[:-1], py[:-1]], 1)
        B = np.stack([px[1:], py[1:]], 1)
        AB = B - A
        t = np.clip(((Q[:, None, :] - A[None]) * AB[None]).sum(2) / np.maximum((AB * AB).sum(1), 1e-12)[None], 0, 1)
        dist = np.linalg.norm(Q[:, None, :] - A[None] - t[..., None] * AB[None], axis=2).min(1)
        d[ci, xi] = np.sign(d[ci, xi]) * dist
    return d


def neck_at(row):
    """(front col, back col, half-width) of the neck on `row`."""
    cols = [np.array(c) for c in zip(*NECK)]
    return tuple(float(np.interp(row, cols[0], c)) for c in cols[1:])


def _neck_plane(row, X, C):
    if row < NECK[0][0]:
        return np.full((len(C), len(X)), -FAR)
    f, b, w = neck_at(row)
    cy, hd = (f + b) / 2, (b - f) / 2
    # the blur pulls a round section in by ~sigma^2 / 2R: start that much fuller
    g = LOWER_BLUR ** 2 / 2
    hw, hd = w + g / w, hd + g / hd
    ex, ey = X[None, :] / hw, (C[:, None] - cy) / hd
    e = np.sqrt(ex ** 2 + ey ** 2)
    grad = np.sqrt((ex / hw) ** 2 + (ey / hd) ** 2) / np.maximum(e, 1e-6)
    return (1.0 - e) / np.maximum(grad, 1e-6)


def _blur(a, sigma, axis):
    k = int(math.ceil(3.0 * sigma))
    w = np.exp(-0.5 * (np.arange(-k, k + 1) / sigma) ** 2)
    w /= w.sum()
    pad = [(0, 0)] * a.ndim
    pad[axis] = (k, k)
    p = np.pad(a, pad, mode='edge')
    out = np.zeros_like(a)
    n = a.shape[axis]
    for i, wi in enumerate(w):
        sl = [slice(None)] * a.ndim
        sl[axis] = slice(i, i + n)
        out += wi * p[tuple(sl)]
    return out


class LowerField:
    """F < 0 inside the lower-face surface, F = 0 on it (panel px coordinates
    X, col, row; symmetric in X). Trilinear on a FIELD_VOX grid."""

    def __init__(self, detail):
        self.detail = detail
        (x0, x1), (c0, c1), (r0, r1) = FIELD_BOX
        v = FIELD_VOX
        self.X = np.arange(x0, x1 + v / 2, v)
        self.C = np.arange(c0, c1 + v / 2, v)
        self.R = np.arange(r0, r1 + v / 2, v)
        dist = np.empty((len(self.R), len(self.C), len(self.X)), np.float32)
        for i, row in enumerate(self.R):
            dist[i] = np.maximum(_head_plane(row, self.X, self.C, detail), _neck_plane(row, self.X, self.C))
        occ = _occ(dist)
        nx = len(self.X)
        full = np.concatenate([occ[:, :, :0:-1], occ], axis=2)    # mirror: -X .. X
        for ax in range(3):
            full = _blur(full, LOWER_BLUR / v, ax)
        blur = full[:, :, nx - 1:]
        sx, r_a, r_b = LOWER_W_NOSE
        w = (_smooth(LOWER_W_ROWS[0], LOWER_W_ROWS[1], self.R)[:, None, None]
             * (1.0 - np.exp(-(self.X / sx) ** 2)[None, None, :]
                * (1.0 - _smooth(r_a, r_b, self.R))[:, None, None]))
        # unblurred: the plain signed distance, which (unlike the occupancy) is
        # smooth across rows too, scaled to the blurred field's slope at the
        # surface (a step blurred by sigma rises 1 / (sqrt(2 pi) sigma) per px)
        g = 1.0 / (math.sqrt(2.0 * math.pi) * LOWER_BLUR)
        self.F = ((1.0 - w) * (-g * dist) + w * (0.5 - blur)).astype(np.float32)

    def sample(self, P):
        P = np.asarray(P, float).reshape(-1, 3)
        v = FIELD_VOX
        f = np.stack([(P[:, 2] - self.R[0]) / v, (P[:, 1] - self.C[0]) / v, (np.abs(P[:, 0]) - self.X[0]) / v], 1)
        f = np.clip(f, 0.0, np.array(self.F.shape) - 1.000001)
        i = np.floor(f).astype(int)
        t = f - i
        out = np.zeros(len(P))
        for a in (0, 1):
            wa = t[:, 0] if a else 1.0 - t[:, 0]
            for b in (0, 1):
                wb = wa * (t[:, 1] if b else 1.0 - t[:, 1])
                for c in (0, 1):
                    out += wb * (t[:, 2] if c else 1.0 - t[:, 2]) * self.F[i[:, 0] + a, i[:, 1] + b, i[:, 2] + c]
        return out

    def normal(self, P, h=0.5):
        """Outward unit normal (px coordinates) at points P (N, 3)."""
        P = np.asarray(P, float).reshape(-1, 3)
        g = np.stack([self.sample(P + e) - self.sample(P - e) for e in np.eye(3) * h], 1)
        return g / np.maximum(np.linalg.norm(g, axis=1, keepdims=True), 1e-12)

    def ray_hits(self, O, D, tmax=80.0, step=0.4):
        """Distance along each ray O + t D (O, D: (N, 3) or (3,), D unit, px) to
        where it first leaves the surface, and the number of surface crossings
        along it."""
        D = np.asarray(D, float).reshape(-1, 3)
        O = np.broadcast_to(np.asarray(O, float).reshape(-1, 3), D.shape)
        ts = np.arange(0.0, tmax, step)
        f = self.sample(O[:, None, :] + ts[None, :, None] * D[:, None, :]).reshape(len(D), len(ts))
        out = f > 0.0
        j = np.argmax(out, axis=1)
        if not out[np.arange(len(D)), j].all() or (j == 0).any():
            raise ValueError('head: a lower-face ray does not leave the surface; check LOWER_O / FIELD_BOX')
        lo, hi = ts[j - 1], ts[j]
        for _ in range(30):
            mid = (lo + hi) / 2
            inside = self.sample(O + mid[:, None] * D) < 0.0
            lo, hi = np.where(inside, mid, lo), np.where(inside, hi, mid)
        return (lo + hi) / 2, np.count_nonzero(np.diff(out.astype(int), axis=1), axis=1)

    def relieved(self, P):
        """Surface points P (N, 3) moved by the fine relief (detailed head only),
        faded out where the surface does not face forward."""
        P = np.array(P, float).reshape(-1, 3)
        if not self.detail:
            return P
        n = self.normal(P)
        P[:, 1] -= lower_relief(np.abs(P[:, 0]), P[:, 2]) * np.clip(-n[:, 1] * 1.4 - 0.4, 0.0, 1.0) ** 2
        return P

    def front_points(self, X, row):
        """Points (N, 3, px) where the front view's lines of sight at (X, row)
        (arrays) meet the surface, with the fine relief."""
        X, row = np.asarray(X, float).ravel(), np.asarray(row, float).ravel()
        cols = np.arange(FIELD_BOX[1][0], 300.0, 0.25)
        n = len(X)
        grid = np.stack([np.repeat(X, len(cols)), np.tile(cols, n), np.repeat(row, len(cols))], 1)
        inside = (self.sample(grid) < 0.0).reshape(n, len(cols))
        j = np.argmax(inside, axis=1)
        if not inside[np.arange(n), j].all() or (j == 0).any():
            raise ValueError('head: a front-view line of sight misses the lower-face surface')
        lo, hi = cols[j - 1], cols[j]
        for _ in range(30):
            mid = (lo + hi) / 2
            ins = self.sample(np.stack([X, mid, row], 1)) < 0.0
            lo, hi = np.where(ins, lo, mid), np.where(ins, mid, hi)
        return self.relieved(np.stack([X, (lo + hi) / 2, row], 1))

    def front_point(self, X, row):
        """World point where the front view's line of sight at (X, row) meets the surface."""
        return _world(self.front_points([X], [row])[0])


_FIELDS = {}


def lower_field(detail=True):
    if detail not in _FIELDS:
        _FIELDS[detail] = LowerField(detail)
    return _FIELDS[detail]


def _slerp(a, b, t):
    om = np.arccos(np.clip(np.sum(a * b, axis=-1, keepdims=True), -1.0, 1.0))
    so = np.maximum(np.sin(om), 1e-9)
    return np.sin((1.0 - t) * om) / so * a + np.sin(t * om) / so * b


def _circ_fill(v):
    """Fill NaNs of a circular sequence by interpolation from its valid entries."""
    v = np.asarray(v, float)
    ok = np.isfinite(v)
    if ok.all() or not ok.any():
        return v
    n = len(v)
    k = np.arange(n)
    kk, vv = k[ok], v[ok]
    return np.where(ok, v, np.interp(k, np.concatenate([kk - n, kk, kk + n]), np.concatenate([vv, vv, vv])))


def _lower_layout(top, fld):
    """Ray directions of the lower loops (L, K, 3), from the detailed head."""
    K = len(top)
    ca = np.cos(ring_angles(K))[:, None]
    O = (np.array(LOWER_O[0]) * (1.0 + ca) + np.array(LOWER_O[1]) * (1.0 - ca)) / 2   # K, 3
    Ptop = np.array([_px(p) for p in top])
    f, b, w = neck_at(NECK_END)
    cy, hd = (f + b) / 2, (b - f) / 2
    Pbot = np.array([(w * math.sin(a), cy - hd * math.cos(a), NECK_END) for a in ring_angles(K)])
    d0 = Ptop - O
    d1 = Pbot - O
    d0 /= np.linalg.norm(d0, axis=1, keepdims=True)
    d1 /= np.linalg.norm(d1, axis=1, keepdims=True)
    T = np.linspace(0.0, 1.0, LOWER_FAN)
    fan = _slerp(d0[:, None, :], d1[:, None, :], T[None, :, None])           # K, T, 3
    t, cross = fld.ray_hits(np.repeat(O, LOWER_FAN, axis=0), fan)
    H = (np.repeat(O, LOWER_FAN, axis=0) + t[:, None] * fan.reshape(-1, 3)).reshape(K, LOWER_FAN, 3)
    n = fld.normal(H.reshape(-1, 3)).reshape(K, LOWER_FAN, 3)
    s = np.concatenate([np.zeros((K, 1)), np.cumsum(np.linalg.norm(np.diff(H, axis=1), axis=2), axis=1)], 1)
    down = n[..., 2] > JAW_DOWN
    # (not the underside of the nose)
    allowed = (H[..., 2] > 138.0) & ~((np.abs(H[..., 0]) < 12.0) & (H[..., 2] < 143.0))
    fJ, fT = np.full(K, np.nan), np.full(K, np.nan)
    for k in range(K):
        idx = np.nonzero(down[k] & allowed[k])[0]
        if not len(idx):
            continue
        after = np.nonzero(~down[k, idx[0]:])[0]
        if len(after):
            fJ[k] = s[k, idx[0]] / s[k, -1]
            fT[k] = s[k, idx[0] + after[0]] / s[k, -1]
    if not np.isfinite(fJ).any():
        raise ValueError('head: no under-jaw band found')
    fJ, fT = _circ_fill(fJ), _circ_fill(fT)
    for _ in range(6):
        fJ = (np.roll(fJ, 1) + 2 * fJ + np.roll(fJ, -1)) / 4
        fT = (np.roll(fT, 1) + 2 * fT + np.roll(fT, -1)) / 4
    fJ = np.clip(fJ, 0.1, 0.84)
    fT = np.clip(np.maximum(fT, fJ + 0.08), 0.0, 0.94)
    fr = np.concatenate([fJ[None] * (np.arange(1, LOOPS_FACE + 1) / LOOPS_FACE)[:, None],
                         fJ[None] + (fT - fJ)[None] * (np.arange(1, LOOPS_UNDER + 1) / LOOPS_UNDER)[:, None],
                         fT[None] + (1.0 - fT)[None] * (np.arange(1, LOOPS_NECK + 1) / LOOPS_NECK)[:, None]])
    tt = np.array([[np.interp(fr[j, k] * s[k, -1], s[k], T) for k in range(K)] for j in range(len(fr))])
    dirs = _slerp(np.broadcast_to(d0, tt.shape + (3,)), np.broadcast_to(d1, tt.shape + (3,)), tt[..., None])
    half = K // 2
    step = np.diff(s, axis=1)
    kmax, jmax = np.unravel_index(np.argmax(step), step.shape)
    cross = cross.reshape(K, LOWER_FAN)
    kc, jc = np.unravel_index(np.argmax(cross), cross.shape)
    print(f'HEAD lower loops: {len(fr)} x {K}; fan step max {step[kmax, jmax]:.2f} px (column {kmax}, at '
          f'{np.round(H[kmax, jmax], 1).tolist()}); crossings max {int(cross[kc, jc])} (column {kc}, at '
          f'{np.round(H[kc, jc], 1).tolist()}); front jaw band {fJ[half] * s[half, -1]:.1f}..'
          f'{fT[half] * s[half, -1]:.1f} of {s[half, -1]:.1f} px')
    # every ray must leave the surface once: a ray that leaves and comes back
    # in skips the surface it hides (stretched quads), so the origins are wrong
    if cross.max() > 1 or step.max() > 5.0:
        raise ValueError('head: the lower-face rays do not see the whole surface from LOWER_O '
                         f'(crossings {int(cross.max())}, fan step {step.max():.2f} px)')
    return {'dirs': dirs, 'orig': np.broadcast_to(O, dirs.shape).copy(), 'iJ': LOOPS_FACE,
            'iT': LOOPS_FACE + LOOPS_UNDER}


def lower_loops(top, detail, layout=None):
    """World points of the lower loops (below the ring `top`, which is not
    repeated) down to the neck end. layout (from the detailed head) fixes the
    rays, so the smooth head (shading normals) gets the same vertices on its
    own surface."""
    fld = lower_field(detail)
    if layout is None:
        layout = _lower_layout(top, fld)
    D, O = layout['dirs'], layout['orig'].reshape(-1, 3)
    t, _ = fld.ray_hits(O, D)
    P = fld.relieved(O + t[:, None] * D.reshape(-1, 3)).reshape(D.shape)
    return [[_world(p) for p in lp] for lp in P], layout


# ---------------------------------------------------------------- morphs
# MMD expression morphs: shape keys at value 0 at rest (export_pmx.MORPH_INFO
# panels). head_face carries the lid, brow and mouth motion; the white cups,
# lashes, teeth and tongue carry the same keys where they move, the iris
# shrinks (瞳小), the highlights go out (ハイライト消). The overlays (照れ, 涙, 汗,
# the はぅ strokes) wait inside the head and move into place. Since round 11
# the motion is 风堇's own (MORPH_SRC, EXTRA_MORPHS below).
BLINK_KEY = 'まばたき'
EYE_CLOSE = (BLINK_KEY, 'ウィンク', 'ウィンク右', '笑い', 'はぅ')   # the lids meet
EYE_OPEN = ('なごみ', 'びっくり', 'じと目', 'キリッ')                  # the lids move, the eye stays open
EYE_MORPHS = EYE_CLOSE + EYE_OPEN
IRIS_MORPHS = ('瞳小',)
HILITE_MORPHS = ('ハイライト消',)
BROW_MORPHS = ('真面目', '困る', 'にこり', '怒り', '上', '下')
MOUTH_MORPHS = ('あ', 'い', 'う', 'え', 'お', 'ワ', 'ん', '∧', 'ω', '▲', 'にやり', '口角上げ', '口角下げ',
                '口横広げ', 'ぺろっ', '歯無し上')
FX_MORPHS = ('照れ', '涙', '汗')
FACE_MORPHS = EYE_MORPHS + BROW_MORPHS + MOUTH_MORPHS          # the keys on head_face
ALL_MORPHS = EYE_MORPHS + IRIS_MORPHS + HILITE_MORPHS + BROW_MORPHS + MOUTH_MORPHS + FX_MORPHS


# ---------------------------------------------------------------- decals
def atlas_object(col, name, bm, mat, swatch=None):
    """Mesh object of an unshaded decal coloured from the atlas (swatch: one key
    for all faces, else the bmesh's 'swatch' face layer). No outline, casts no
    shadow, 'eye' region (toon_grad 1)."""
    uv = bm.loops.layers.uv.new('UVMap')
    lay = bm.faces.layers.int.get('swatch')
    keys = list(ATLAS)
    for f in bm.faces:
        u = atlas_uv(swatch if swatch else keys[f[lay]])
        for loop in f.loops:
            loop[uv].uv = u
    obj = common.new_object(col, name, bm, [mat])
    obj.data.shade_smooth()
    attr = obj.data.attributes.new(common.GRAD_ATTR, 'FLOAT', 'POINT')
    for a in attr.data:
        a.value = 1.0
    obj['no_outline'] = True
    obj['levi_cast_shadow'] = False
    return obj


def add_keys(obj, keys):
    """Shape keys {name: [world points per vertex]} (the object has identity
    transform); keys that move nothing are left out."""
    rest = [v.co.copy() for v in obj.data.vertices]
    if obj.data.shape_keys is None:
        obj.shape_key_add(name='Basis', from_mix=False)
    for name, pts in keys.items():
        if pts is None or max((Vector(tuple(p)) - q).length for p, q in zip(pts, rest)) < 1e-7:
            continue
        kb = obj.shape_key_add(name=name, from_mix=False)
        for v, p in zip(kb.data, pts):
            v.co = Vector(tuple(p))
        kb.value = 0.0


# ---------------------------------------------------------------- ears
# Anime ear, mostly under the hair: ~2.95 cm tall, from the upper lid to the
# nose tip (spanning eye level, as both references do), set back of the head's
# widest point, the top leaning back. An oval plate on the side of the head,
# its back plane sunk into the skin at the front edge and bent to follow the
# head's curve top to bottom; the back edge stands out (EAR_FLARE). The outer
# face carries a rolled helix rim over the top and back, the scapha groove,
# the antihelix ridge, a concha bowl, the tragus and a soft lobe.
EAR_ROWS = (108.5, 127.5)        # top, bottom [px]
EAR_COL = 297.0                  # side-view column of the ear's middle
EAR_HALF_DEPTH = (6.8, 5.2)      # px: half the front-to-back size at the top / the lobe
EAR_TILT = 12.0                  # deg: the top leans back
EAR_FLARE = 20.0                 # deg: the back edge stands out
EAR_SINK = 1.8                   # px the back plane sits inside the skin at the ear's middle
EAR_BACK = 1.3                   # px from the back plane to the outer face's base
EAR_NT = 40
EAR_FRONT_RINGS = 10


def _arc(th, a, b, soft):
    return float(_smooth(a, a + soft, th)) * (1.0 - float(_smooth(b - soft, b, th)))


def ear_height(v, u, rho, th):
    """Outer face height [px] over the base at (v back, u up), radius share rho,
    outline angle th [deg] (0 back, 90 top, 180 front, -90 the lobe)."""
    helix = 1.5 * math.exp(-((rho - 0.9) / 0.1) ** 2) * _arc(th, -65.0, 170.0, 25.0)
    scapha = -0.55 * math.exp(-((rho - 0.72) / 0.08) ** 2) * _arc(th, -45.0, 140.0, 30.0)
    anti = 0.75 * math.exp(-((rho - 0.52) / 0.11) ** 2) * _arc(th, -40.0, 115.0, 30.0)
    concha = -1.9 * math.exp(-((v + 1.0) / 3.0) ** 2 - ((u + 1.2) / 3.4) ** 2)
    tragus = 0.9 * math.exp(-((v + 5.0) / 1.3) ** 2 - ((u + 2.2) / 1.7) ** 2)
    lobe = 0.5 * math.exp(-((u + 7.0) / 2.0) ** 2)
    return 0.9 + 0.4 * (1.0 - rho * rho) + helix + scapha + anti + concha + tragus + lobe


def _ear_frame(col):
    """(origin, e_v back, e_u up, e_w out) of the left ear (world): the origin
    on its front edge at side-view column `col`, EAR_SINK inside the skin."""
    row = 0.5 * (EAR_ROWS[0] + EAR_ROWS[1])
    a = min(np.linspace(math.radians(60.0), math.radians(150.0), 361),
            key=lambda a: abs(col_of(surf(a, row, False).y) - col))
    p = surf(a, row, False)
    da, dr = math.radians(1.0), 1.0
    t_ring = surf(a + da, row, False) - surf(a - da, row, False)
    t_down = surf(a, row + dr, False) - surf(a, row - dr, False)
    n = t_down.cross(t_ring).normalized()
    if n.x < 0:
        n = -n
    up0 = Vector((0.0, 0.0, 1.0))
    up0 = (up0 - n * up0.dot(n)).normalized()
    back0 = up0.cross(n).normalized()
    if back0.y < 0:
        back0 = -back0
    t = math.radians(EAR_TILT)
    e_u = up0 * math.cos(t) + back0 * math.sin(t)
    e_v = back0 * math.cos(t) - up0 * math.sin(t)
    f = math.radians(EAR_FLARE)
    e_v, e_w = e_v * math.cos(f) + n * math.sin(f), n * math.cos(f) - e_v * math.sin(f)
    return p - n * (EAR_SINK / PPM), e_v, e_u, e_w


def ear_mesh(side):
    bm = bmesh.new()
    hu = 0.5 * (EAR_ROWS[1] - EAR_ROWS[0])
    bend = 1.7 / (hu * hu)          # the plate bends with the head's curve, top to bottom
    v_front = -0.5 * (EAR_HALF_DEPTH[0] + EAR_HALF_DEPTH[1])
    o, e_v, e_u, e_w = _ear_frame(EAR_COL + v_front)

    def outline(th):
        r = math.radians(th)
        a = EAR_HALF_DEPTH[1] + (EAR_HALF_DEPTH[0] - EAR_HALF_DEPTH[1]) * 0.5 * (1.0 + math.sin(r))
        return a * math.cos(r), hu * math.sin(r)

    def world(v, u, w):
        # the frame turns about the ear's front edge (o), so the front stays sunk
        return o + e_v * ((v - v_front) / PPM) + e_u * (u / PPM) + e_w * ((w - bend * u * u) / PPM)

    ths = [360.0 * k / EAR_NT - 180.0 for k in range(EAR_NT)]
    rings = []
    for k in range(1, EAR_FRONT_RINGS + 1):
        rho = k / EAR_FRONT_RINGS
        ring = []
        for th in ths:
            ov, ou = outline(th)
            v, u = ov * rho, ou * rho
            ring.append(world(v, u, ear_height(v, u, rho, th)))
        rings.append(ring)
    for phi in (40.0, 80.0, 120.0, 160.0):
        ring = []
        for th in ths:
            ov, ou = outline(th)
            hf = ear_height(ov, ou, 1.0, th)
            wc, rr = 0.5 * (hf - EAR_BACK), 0.5 * (hf + EAR_BACK)
            L = math.hypot(ov, ou)
            grow = 1.0 + rr * 0.55 * math.sin(math.radians(phi)) / L
            ring.append(world(ov * grow, ou * grow, wc + rr * math.cos(math.radians(phi))))
        rings.append(ring)
    for rho in (1.0, 0.65, 0.3):
        ring = []
        for th in ths:
            ov, ou = outline(th)
            ring.append(world(ov * rho, ou * rho, -EAR_BACK))
        rings.append(ring)
    front_c = world(0.0, 0.0, ear_height(0.0, 0.0, 0.0, 0.0))
    back_c = world(0.0, 0.0, -EAR_BACK)
    vf = bm.verts.new(front_c)
    vrings = [[bm.verts.new(p) for p in ring] for ring in rings]
    vb = bm.verts.new(back_c)
    n = EAR_NT
    for i in range(n):
        i2 = (i + 1) % n
        bm.faces.new((vf, vrings[0][i], vrings[0][i2]))
        for a, b in zip(vrings, vrings[1:]):
            bm.faces.new((a[i], b[i], b[i2], a[i2]))
        bm.faces.new((vb, vrings[-1][i2], vrings[-1][i]))
    if side < 0:
        for v in bm.verts:
            v.co.x = 2.0 * HEAD_DX - v.co.x
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


# ---------------------------------------------------------------- round 11: 风堇's face
# Levi's names (ALL_MORPHS) from hers: a name she has is taken as it is; these
# are composed from hers (her morph, weight). ω is her 倒ω turned upside down.
PEROH_OPEN = 0.45                     # ぺろっ: her あ share, so the tongue comes out between the lips
MORPH_SRC = {
    'にこり': (('手前2', 1.0),),
    'なごみ': (('まばたき', 0.42), ('慈愛', 1.0)),
    'はぅ': (('笑い', 1.0),),
    'ω': (('口角上げ', 0.55), ('う', 0.2)),          # + OMEGA_LIFT: the lips' middle up, a cat's 'w'
    'にやり': (('にやり', 1.0), ('口角上げ', 0.3)),
    '▲': (('あ', 0.45), ('口角下げ', 1.0), ('口横缩げ', 0.8)),
    'ぺろっ': (('あ', PEROH_OPEN),),
}
# her other expressions, shipped under her (cleaned) names (export_pmx.MORPH_INFO panels)
EXTRA_MORPHS = ('怒り右', '手前', 'やっかい', '悲しい', 'キリッ2', '喜び', '喜び2', '慈愛', '慈愛2', '驚かす',
                'じと目2', 'ウィンク２', 'ウィンク２右', '笑い2', '笑い3', 'ムッ', '怒った', '怒った2', '口',
                'い2', 'え2', '口下', '大口', 'お2', '口横缩げ', '倒ω', '痛み', '痛み2', '痛み3', '口横缩げ2',
                'にやり2', 'にやり3', 'ワ2', 'ワ1', '口角下げ2', '口上', '心配する', '心配する2', 'え3', 'えー')
SHIP_MORPHS = ALL_MORPHS + EXTRA_MORPHS
# Levi's rest face is hers with a little of her own morphs built in (_head_levi: the lids
# lowered and flattened, the brows' inner ends up, the mouth small and level); every key
# is W(p + bake + d), so her morphs keep working from it
OMEGA_LIFT = (0.0010, 0.0024, 0.0030)  # ω: m up at the lips' middle; X, z reach [m]
PUPIL_SQUEEZE = (0.55, 0.60, 0.92)   # 瞳小: inner iris scale, from / to share of the dish radius
# the highlight (ref/setting.png): a vertical oval a little toward the nose on both eyes,
# its top tucked just under the lowered lid margin, with a thin dark ring; in D (the iris
# width): toward the nose, gap under the margin, half-width, half-height; lift off the dish [m]
HILITE = (0.06, 0.02, 0.085, 0.11, 0.0004)
HILITE_RING = (0.02, 0.0002)          # the ring: D wider than the card, m off the dish
HILITE_SEG = 28
IRIS_SQUASH = (0.87, 0.0002)          # the iris dish's height kept (round, not her tall oval), and how
#                                       far [m] its lowest point sits behind the baked lower lid's edge
BROW_SNAP = True                      # her brows, lowered, keep her own offset off the forehead
HILITE_OFF = 0.003                    # ハイライト消: m behind the iris
BROW_DROP = 0.006                     # m: her brow strips come down toward the eye (Levi's sheet)
TEETH_HIDE_M = (0.0016, 0.0012)       # 歯無し上: up, back [m]
TONGUE_OUT_M = (0.0075, 0.0032, 0.012)   # ぺろっ: the tip comes forward, up [m] (out over the lower
#                                          lip, through the parted lips); over this length from the tip
FLUSH_BOX = ((0.016, 0.064), (1.264, 1.292))   # |x| from the midline, z: the 照れ overlay patch
FLUSH_RIM = 0.004                      # m: ... and no nearer the eye openings
FX_DEPTH = 0.004                       # m: the tear and sweat wait this far inside the skin at rest
FLUSH_PARK = 0.5                       # 照れ's cheek copy waits this share of the way to the head's centre
HAU_HIDE = (0.0, 0.035, 0.0)           # m: the はぅ strokes wait behind the eye cups
SHADE_SMOOTH = 16                      # Laplacian passes of the copy head_face's shading normals come from
NOSE_ZONE = (0.013, 0.040, 0.004)      # m: |x|, below / above the eye centre: no nose in the shading form
MOUTH_ZONE = (0.012, 0.0045)           # m: half-width, half-height round the lip line: no lips in the shading form
MOUTH_OUTLINE = (0.0025, 0.0070, (0.003, 0.007))   # m: no outline this near the mouth (at the middle,
#                                        at the corners; |x| from the midline where it widens): round
#                                        the closed corners the hull stood out of the fold as hooks
NECK_TURN_Z = (1.240, 1.262)           # m: her border this high (behind the jaw) leaves downward ...
NECK_TURN = 1.0                        # ... this much (1: diagonally back and down)
JUNCTION_R, JUNCTION_FAIR = 0.011, 25  # m round the corners behind the jaw angle faired; passes
LOFT_FAIR_RINGS, LOFT_FAIR = 7, 30     # the neck loft's rings faired below the head's edge; passes
SEAM_BAND, SEAM_SMOOTH = (0.005, 0.015), 60   # m round the seam, passes: its shading form is smoother
FX_LIFT_M = 0.0002                     # m the overlays float off the skin when shown


def _neutral(getter, entries):
    """Offsets of a weighted sum of her morphs (a bake) on one piece."""
    out = 0.0
    for s, w in entries:
        out = out + getter(s) * w
    return out


def _bakes(getter):
    """(d0, lid0): Levi's whole rest bake on one piece, and its lid part."""
    lid0 = _neutral(getter, HL.NEUTRAL_LID)
    return _neutral(getter, HL.NEUTRAL) + lid0, lid0


def _lid_sides(getter, P):
    """{key: (closes L, closes R)} of the LID_MEET keys, from the face's offsets."""
    out = {}
    right = P[:, 0] < G.MID_X
    for n in HL.LID_MEET:
        d = _src_offsets(getter, n)
        if d is None:
            continue
        m = np.linalg.norm(d, axis=1)
        mL, mR = m[~right].max(), m[right].max()
        out[n] = (float(mL > 0.5 * max(mL, mR)), float(mR > 0.5 * max(mL, mR)))
    return out


def _key_bake(n, d0, lid0, P, sides):
    """The bake key n starts from: a lid-meeting key has no lid bake on the side(s) it closes."""
    if n not in sides:
        return d0
    sL = G.smooth(-0.01, 0.01, P[:, 0] - G.MID_X)
    cl, cr = sides[n]
    return d0 - lid0 * (cl * sL + cr * (1.0 - sL))[:, None]


def _src_offsets(getter, morph, pos=None):
    """Dense offsets of Levi's morph `morph` on one piece; getter(her name) gives
    her offsets there (pos: the piece's rest, for the authored fields). None if
    neither she nor MORPH_SRC has it."""
    her = set(G.morph_names())
    srcs = MORPH_SRC.get(morph, ((morph, 1.0),) if morph in her else ())
    out = None
    for s, w in srcs:
        d = getter(s) * w
        out = d if out is None else out + d
    if morph == 'ω' and out is not None and pos is not None:
        out = out + _omega_lift(pos)
    return out


def _omega_lift(P):
    """ω: the lips' middle lifted (both lips at the slit), so with the corners up the
    closed mouth reads as a cat's 'w'."""
    lift, rx, rz = OMEGA_LIFT
    X = np.abs(P[:, 0] - G.MID_X)
    zs = G.EYE_C[1] - G.LIP_SLIT
    front = P[:, 1] < -0.105
    out = np.zeros_like(P)
    out[:, 2] = lift * np.exp(-(X / rx) ** 2 - ((P[:, 2] - zs) / rz) ** 2) * front
    return out


def skull_points():
    """Levi's round-10 head surface without openings: (L, N_RING, 3) loops from
    the crown ring to the neck end, and the index of the first neck loop."""
    angles, rows = ring_angles(N_RING), RING_ROWS
    pts = [ring(r, angles, True) for r in rows]
    lower, layout = lower_loops(pts[-1], True, None)
    P = np.array([[tuple(p) for p in lp] for lp in pts + lower])
    return P, len(rows) - 1 + layout['iT']


def skull_mesh(P):
    """Vertices and faces of the loops P (L, K, 3): quads between loops and a
    fan round the crown (its centre last)."""
    L, K = P.shape[:2]
    V = np.concatenate([P.reshape(-1, 3), P[0].mean(0)[None]])
    c = L * K
    F = []
    for i in range(L - 1):
        for k in range(K):
            k2 = (k + 1) % K
            F.append([i * K + k, (i + 1) * K + k, (i + 1) * K + k2, i * K + k2])
    for k in range(K):
        F.append([c, k, (k + 1) % K])
    return V, F


def _vertex_normals(P, faces):
    N = np.zeros_like(P)
    for f in faces:
        p0 = P[f[0]]
        for a, b in zip(f[1:-1], f[2:]):
            n = np.cross(P[a] - p0, P[b] - p0)
            for v in (f[0], a, b):
                N[v] += n
    return N / np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-12)


def _shade_keep(P, mouth_z):
    """Share of the real normal in head_face's shading normal: low round the eyes
    and nose (their relief must not break the two-tone shading into specks), a
    little more on the cheeks and jaw, half on the skull."""
    X = np.abs(P[:, 0] - HEAD_DX)
    z = P[:, 2]
    front = G.smooth(-0.070, -0.092, P[:, 1])
    eye = np.exp(-((X - G.EYE_C[0]) / 0.020) ** 2 - ((z - G.EYE_C[1]) / 0.016) ** 2)
    nose = np.exp(-(X / 0.010) ** 2 - ((z - (G.EYE_C[1] - 0.024)) / 0.014) ** 2)
    mouth = np.exp(-(X / 0.012) ** 2 - ((z - mouth_z) / 0.006) ** 2)
    feat = np.maximum.reduce([eye, nose, mouth])
    return (0.20 - 0.15 * feat) * front + 0.5 * (1.0 - front)


def _mesh(name, pos, faces, uvs=None, mats=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(map(float, p)) for p in pos], [], [list(map(int, f)) for f in faces])
    if uvs is not None:
        lay = me.uv_layers.new(name='UVMap')
        flat = []
        for poly, u in zip(me.polygons, uvs):
            assert len(u) == poly.loop_total
            flat += [c for uu in u for c in uu]
        lay.data.foreach_set('uv', np.array(flat, np.float32))
    if mats is not None:
        me.polygons.foreach_set('material_index', np.array(mats, np.int32))
    return me


def _grad_attr(me, value):
    attr = me.attributes.get(common.GRAD_ATTR) or me.attributes.new(common.GRAD_ATTR, 'FLOAT', 'POINT')
    attr.data.foreach_set('value', np.full(len(me.vertices), value, np.float32))


def _decal(col, name, pos, tri, uv, mat, keys, cast=False):
    """An unshaded eye / lash piece from the atlas: no outline, 'eye' region."""
    obj = bpy.data.objects.new(name, _mesh(name, pos, tri, [list(map(tuple, u)) for u in uv]))
    col.objects.link(obj)
    obj.data.materials.append(mat)
    obj.data.shade_smooth()
    _grad_attr(obj.data, 1.0)
    obj['no_outline'] = True
    if not cast:
        obj['levi_cast_shadow'] = False
    add_keys(obj, keys)
    return obj


def atlas_material(name, path, image):
    """face_material() with the texture loaded from an asset PNG (RGBA: alpha is
    the shading mask)."""
    img = bpy.data.images.get(image)
    if img:
        bpy.data.images.remove(img)
    img = bpy.data.images.load(path, check_existing=False)
    img.name = image
    img.colorspace_settings.name = 'sRGB'
    img.alpha_mode = 'CHANNEL_PACKED'
    w, h = img.size
    px = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(px)
    pixels = px.reshape(h, w, 4)[::-1]
    bpy.data.images.remove(img)
    return face_material(pixels, name, image)


def build_face(col, face_mat, mouth_mat):
    """head_face: her face (warped, subdivided) zipped into Levi's skull. Returns
    (object, warp, rest points, keys, her eye-hole loops)."""
    lid_k = G.data().get('lid_k')
    if lid_k is None or abs(float(lid_k) - HL.LID_K) > 1e-6:
        raise ValueError(f'head: assets/hyacine/head.npz was painted for LID_K {lid_k}, the part bakes '
                         f'{HL.LID_K}: rerun tools/prep_hyacine_head.py (the crease and ticks sit on the baked lid)')
    fc = G.face_coarse()
    lips = G.LipRest(fc)              # Levi's lower face: flat lips, the mouth a little lower
    fc['pos'] = fc['pos'] + lips.D
    S0, i_neck = skull_points()
    Sv0, Sf = skull_mesh(S0)
    W = G.Warp(fc, BVHTree.FromPolygons([Vector(p) for p in Sv0], Sf))
    W.lips = lips
    W.fc = fc
    keys = {}
    get = lambda s: G.face_offsets(fc, s)        # noqa: E731
    d0, lid0 = _bakes(get)
    W.lid_sides = _lid_sides(get, fc['pos'])
    for n in SHIP_MORPHS:
        d = _src_offsets(get, n, fc['pos'])
        if d is not None and np.abs(d).max() > 1e-7:
            kb = _key_bake(n, d0, lid0, fc['pos'], W.lid_sides)
            keys[n] = W.face(kb + d)
    base = W.face(d0)
    faces, uvs, mats = G.quad_faces(base, fc['tri'], fc['uv'], fc['mat'])
    P2, F2, U2, M2, K2 = G.subdivide(base, faces, uvs, mats, keys)
    nM = len(P2)
    loops = G.boundary_loops(F2)
    top = int(np.argmax(P2[:, 2]))
    B = next(lp for lp in loops if top in lp)
    holes = [lp for lp in loops if lp is not B]
    # the skull: Levi's ring rows (crown down to LOWER_TOP, under the eyes) less what her mask covers
    nr = len(RING_ROWS)
    K = S0.shape[1]
    Su, Suf = skull_mesh(S0[:nr])
    keep, C, _, sl = G.cut_skull(Su, Suf, P2[B])
    used = sorted({v for f in keep for v in f})
    # the cut's run along the lowest ring (behind the ears) stays: the neck loft hangs from it
    last = [(v // K == nr - 1) and v < nr * K for v in C]
    n_c = len(C)
    run, best = [], []
    for s0 in range(n_c):                       # the longest cyclic run of lowest-ring vertices
        if last[s0] and not last[s0 - 1]:
            r = []
            j = s0
            while last[j % n_c] and len(r) < n_c:
                r.append(j % n_c)
                j += 1
            if len(r) > len(best):
                best = r
    back = [C[j] for j in best]                  # E_a .. E_b along C's order
    rest = [C[(best[-1] + k) % n_c] for k in range(n_c - len(best) + 2)]   # E_b .. (cut) .. E_a
    # her border: the arc along the cut (upper) and the arc under the jaw (lower)
    nB = len(B)
    ja = int(np.argmin(np.linalg.norm(P2[B] - Su[rest[-1]], axis=1)))    # near E_a
    jb = int(np.argmin(np.linalg.norm(P2[B] - Su[rest[0]], axis=1)))     # near E_b
    arc1 = [B[(jb + k) % nB] for k in range((ja - jb) % nB + 1)]          # jb .. ja one way
    arc2 = [B[(ja + k) % nB] for k in range((jb - ja) % nB + 1)]          # ja .. jb the other way
    upper, lower = (arc1, arc2) if B[int(np.argmax(P2[B][:, 2]))] in arc1 else (arc2, arc1)
    if upper[0] != B[jb]:
        upper = upper[::-1]                        # jb (E_b) .. over the top .. ja (E_a)
    # the cut is drawn to a curve GAP_KEEP outside her border's upper arc (along her
    # surface), its points in order along it: an even strip of triangles, no fold
    nbM = G.adjacency(nM, [list(f) for f in F2])
    bset = set(B)
    out_dir = []
    for k, v in enumerate(upper):
        inner = [u for u in nbM[v] if u not in bset]
        o = P2[v] - P2[inner].mean(0) if inner else np.zeros(3)
        t = P2[upper[min(k + 1, len(upper) - 1)]] - P2[upper[max(k - 1, 0)]]
        t /= max(np.linalg.norm(t), 1e-9)
        o -= t * (o @ t)
        out_dir.append(o / max(np.linalg.norm(o), 1e-9))
    targets = G.offset_targets(P2[upper], np.array(out_dir), Su[rest])
    Su, gap0 = G.close_gap(Su, used, rest, targets)
    remap = {v: nM + i for i, v in enumerate(used)}
    bridge = G.zip_chains(upper, P2[upper], [remap[v] for v in rest], Su[rest])
    # the lower edge: her under-jaw arc, then the lowest ring behind; the loft leaves it
    # along the surface it ends (her jaw's underside, the skull's slope)
    if lower[0] != B[ja]:
        lower = lower[::-1]                        # ja .. under the jaw .. jb
    edge = [('M', v) for v in lower] + [('S', v) for v in back[::-1]]      # .. jb, E_b .. back .. E_a
    Epos = np.array([P2[v] if k == 'M' else Su[v] for k, v in edge])
    th = np.arctan2(Epos[:, 0], -(Epos[:, 1] - (G.BODY_NECK[1] + G.BODY_NECK[2]) / 2))
    if ((np.diff(np.unwrap(th)) < 0).sum() > len(th) / 2):
        edge, Epos = edge[::-1], Epos[::-1]
    T0 = []
    for k, v in edge:
        if k == 'M':
            inner = [u for u in nbM[v] if u not in bset]
            t = P2[v] - (P2[inner].mean(0) if inner else P2[v] - np.array([0, 0, 1e-3]))
            # up the back of the jaw (behind the ramus) the surface turns down into the neck's
            # side, as the skull's columns do beside it; under the chin it carries on back
            down = NECK_TURN * G.smooth(*NECK_TURN_Z, P2[v][2])
            t = t / max(np.linalg.norm(t), 1e-9) + down * np.array([0, 0, -1.0])
        else:
            t = Su[v] - Su[v - K]                  # down the skull's column
        T0.append(t / max(np.linalg.norm(t), 1e-9))
    nM_n = _vertex_normals(P2, [list(f) for f in F2])
    Nsurf = np.array([nM_n[v] if k == 'M' else (Su[v] - G.WARP_C) / np.linalg.norm(Su[v] - G.WARP_C)
                      for k, v in edge])
    rings = G.loft_neck(Epos, np.array(T0), Nsurf)
    e_idx = [v if k == 'M' else remap[v] for k, v in edge]
    n_e = len(edge)
    base_n = nM + len(used)
    loft_v = np.concatenate(rings)
    loft_f = []
    prev = e_idx
    for r in range(len(rings)):
        cur = [base_n + r * n_e + j for j in range(n_e)]
        for j in range(n_e):
            j2 = (j + 1) % n_e
            loft_f.append([prev[j], prev[j2], cur[j2], cur[j]])
        prev = cur
    neck_end = prev
    verts = np.concatenate([P2, Su[used], loft_v])
    # fair the loft's upper rings (a membrane from the head's lower edge to the tube):
    # no crease runs down from where her jaw's border meets the skull's lowest ring
    nfair = LOFT_FAIR_RINGS * n_e
    free = np.zeros(len(verts), bool)
    free[base_n:base_n + nfair] = True
    nbl = G.adjacency(len(verts), [list(f) for f in loft_f])
    verts = G.laplace(verts, nbl, ~free, n=LOFT_FAIR)
    skin_uv = G.swatch_uv('skin')
    allf = ([list(f) for f in F2] + [list(t) for t in bridge] + [[remap[v] for v in f] for f in keep]
            + loft_f)
    # where her jaw's border climbs to the skull's lowest ring (behind the jaw angle, both
    # sides) the three meshes meet at a crease: fair everything there, her face included
    # (its morph keys take the same move)
    corners = [P2[B[ja]], P2[B[jb]]]
    near = np.min([np.linalg.norm(verts - c, axis=1) for c in corners], axis=0)
    free = near < JUNCTION_R
    nball = G.adjacency(len(verts), allf)
    before = verts.copy()
    verts = G.laplace(verts, nball, ~free, n=JUNCTION_FAIR)
    moved = verts - before
    for n_ in K2:
        K2[n_] = K2[n_] + moved[:nM]
    P2 = verts[:nM]
    alluv = [list(u) for u in U2] + [[skin_uv] * len(f) for f in allf[len(F2):]]
    allm = list(M2) + [0] * (len(allf) - len(F2))
    gap = np.array([np.linalg.norm(verts[b] - verts[c]) for t in bridge for b, c in ((t[0], t[2]), (t[1], t[2]))])
    if os.environ.get('LEVI_HEAD_DEBUG'):
        np.savez(os.environ['LEVI_HEAD_DEBUG'], P2=P2, B=np.array(B), verts=verts, nM=nM, Epos=Epos,
                 T0=np.array(T0), ekind=np.array([k for k, _ in edge]), rings=np.array(rings),
                 nquads=sum(len(f) == 4 for f in faces), nfaces=len(faces),
                 fidx=np.array([v for f in allf for v in f]), fsz=np.array([len(f) for f in allf]),
                 fkind=np.array([0] * len(F2) + [1] * len(bridge) + [2] * len(keep) + [3] * len(loft_f)))
    print(f'HEAD graft: face {nM} verts {len(F2)} faces (holes {[len(h) for h in holes]}, border {len(B)}: '
          f'upper {len(upper)}, under the jaw {len(lower)}); skull kept {len(keep)} of {len(Suf)} faces, '
          f'cut {len(C)} (back run {len(back)}), loops {[len(lp) for lp in sl]}; bridge {len(bridge)} tris, '
          f'gap median {np.median(gap) * 1000:.1f} max {gap.max() * 1000:.1f} mm (cut up to {gap0 * 1000:.1f} mm '
          f'off before the draw); neck loft {n_e} x {len(rings)}; warp max {np.abs(W.D).max() * 1000:.1f} mm, '
          f'misses {W.miss}')
    # one consistently oriented mesh (bmesh), faces outward
    import bmesh as _bm
    bm = _bm.new()
    bv = [bm.verts.new(Vector(p)) for p in verts]
    bfaces = []
    for f in allf:
        bfaces.append(bm.faces.new([bv[i] for i in f]))
    for f, m in zip(bfaces, allm):
        f.material_index = m
    _bm.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    front = min(bm.faces, key=lambda f: f.calc_center_median().y)
    if front.normal.y > 0:
        _bm.ops.reverse_faces(bm, faces=bm.faces)
    lay = bm.loops.layers.uv.new('UVMap')
    for f, f0, u in zip(bfaces, allf, alluv):
        at = {v: uu for v, uu in zip(f0, u)}
        for loop in f.loops:
            loop[lay].uv = at[loop.vert.index]
    me = bpy.data.meshes.new('head_face')
    bm.to_mesh(me)
    bm.free()
    head = bpy.data.objects.new('head_face', me)
    col.objects.link(head)
    me.materials.append(face_mat)
    me.materials.append(mouth_mat)
    me.shade_smooth()
    _grad_attr(me, 0.0)
    polys = [list(p.vertices) for p in me.polygons]
    # shading normals: the form of a smoothed copy, some of the real normal
    cavity = set(range(len(verts))) - {v for p, m in zip(polys, allm) if m == 0 for v in p}
    rims = {v for lp in holes for v in lp}
    end = set(neck_end)
    fixed = np.array([(i in cavity) or (i in rims) or (i in end) for i in range(len(verts))])
    nb = G.adjacency(len(verts), polys)
    # the shading form has no nose: a membrane spans the nose zone from the face round it
    X, z = np.abs(verts[:, 0] - HEAD_DX), verts[:, 2] - G.EYE_C[1]
    nose_zone = (X < NOSE_ZONE[0]) & (z > -NOSE_ZONE[1]) & (z < NOSE_ZONE[2]) & (verts[:, 1] < -0.09)
    nose_zone &= ~np.isin(np.arange(len(verts)), list(cavity))
    # nor lips: a membrane spans the closed mouth from the skin round it (the lip line's two
    # sides joined across the slit, the mouth's pocket left out)
    lipline = sorted({v for p, m in zip(polys, allm) if m == 1 for v in p} - cavity)
    mz = float(np.median(verts[lipline, 2]))
    mouth_zone = (np.hypot(X / MOUTH_ZONE[0], (verts[:, 2] - mz) / MOUTH_ZONE[1]) < 1.0) & (verts[:, 1] < -0.09)
    mouth_zone &= ~np.isin(np.arange(len(verts)), list(cavity))
    nb_skin = [list(s_) for s_ in G.adjacency(len(verts), [p for p, m in zip(polys, allm) if m == 0])]
    kd_l = KDTree(len(lipline))
    for i, v in enumerate(lipline):
        kd_l.insert(Vector(verts[v]), i)
    kd_l.balance()
    for v in lipline:
        for _, j, d in kd_l.find_n(Vector(verts[v]), 4):
            u = lipline[j]
            if u != v and d < 0.001 and u not in nb_skin[v]:
                nb_skin[v].append(u)
                nb_skin[u].append(v)
    form = G.laplace(verts, nb_skin, ~(nose_zone | mouth_zone), n=400)
    form = G.laplace(form, nb, fixed, n=SHADE_SMOOTH)
    smooth_n = _vertex_normals(form, polys)
    real_n = _vertex_normals(verts, polys)
    k = _shade_keep(verts, mz)
    # round the seam (her border, the strip, the skull's cut, the neck loft's top) the
    # form is smoothed further, so the zipped meshes' different densities do not show
    seam = sorted(set(B) | {v for t in bridge for v in t} | set(e_idx))
    kd_s = KDTree(len(seam))
    for i, v in enumerate(seam):
        kd_s.insert(Vector(verts[v]), i)
    kd_s.balance()
    band = np.array([1.0 - float(G.smooth(SEAM_BAND[0], SEAM_BAND[1], kd_s.find(Vector(p))[2])) for p in verts])
    seam_n = _vertex_normals(G.laplace(form, nb, fixed, n=SEAM_SMOOTH), polys)
    smooth_n = smooth_n * (1 - band[:, None]) + seam_n * band[:, None]
    smooth_n /= np.linalg.norm(smooth_n, axis=1, keepdims=True)
    k *= 1.0 - 0.8 * band
    k[list(cavity)] = 1.0
    nrm = smooth_n * (1 - k[:, None]) + real_n * k[:, None]
    nrm /= np.linalg.norm(nrm, axis=1, keepdims=True)
    me.normals_split_custom_set_from_vertices([tuple(n) for n in nrm])
    if os.environ.get('LEVI_HEAD_DEBUG'):
        cn = np.zeros(len(me.loops) * 3)
        me.corner_normals.foreach_get('vector', cn)
        cn = cn.reshape(-1, 3)
        vi = np.zeros(len(me.loops), np.int64)
        me.loops.foreach_get('vertex_index', vi)
        v = int(np.argmin(np.abs(verts[:, 0] - HEAD_DX - 0.005) + np.abs(verts[:, 2] - 1.281) + (verts[:, 1] > -0.12)))
        li = int(np.nonzero(vi == v)[0][0])
        print('HEAD normals debug', v, verts[v].round(4), 'smooth', smooth_n[v].round(3), 'real', real_n[v].round(3),
              'k', round(float(k[v]), 3), 'set', nrm[v].round(3), 'corner', cn[li].round(3))
    # keys: hers on the face, carried onto the skull near her border
    head.shape_key_add(name='Basis', from_mix=False)
    skull = range(nM, len(verts))
    all_keys = {}
    for n in SHIP_MORPHS:
        if n not in K2:
            continue
        arr = verts.copy()
        arr[:nM] = K2[n]
        dB = K2[n][B] - P2[B]
        if np.abs(dB).max() > 1e-7:
            for v, d in G.propagate(verts, B, dB, skull).items():
                arr[v] += d
        all_keys[n] = arr
    add_keys(head, all_keys)
    # outline: none at the eye openings and in the mouth, thin on the nose
    kd_e = KDTree(len(rims))
    for i, v in enumerate(sorted(rims)):
        kd_e.insert(Vector(verts[v]), i)
    kd_e.balance()
    kd_m = KDTree(len(cavity))
    for i, v in enumerate(sorted(cavity)):
        kd_m.insert(Vector(verts[v]), i)
    kd_m.balance()
    wts = np.ones(len(verts))
    for i, p in enumerate(verts):
        de = kd_e.find(Vector(p))[2]
        dm = kd_m.find(Vector(p))[2]
        r_m = MOUTH_OUTLINE[0] + (MOUTH_OUTLINE[1] - MOUTH_OUTLINE[0]) * float(
            G.smooth(*MOUTH_OUTLINE[2], abs(p[0] - HEAD_DX)))
        wts[i] = min(G.smooth(0.0004, 0.003, de), G.smooth(0.0, r_m, dm))
    wts *= 1.0 - 0.8 * G.nose_weight(verts)
    wts[list(cavity)] = 0.0
    vg = head.vertex_groups.new(name='outline_width')
    for w in sorted(set(np.round(wts, 3))):
        vg.add([int(i) for i in np.nonzero(np.round(wts, 3) == w)[0]], float(w), 'REPLACE')
    common.add_outline(head, vertex_group='outline_width', min_factor=0.0)
    return head, W, verts, all_keys, holes, nrm


def _closest_loop(loops, verts, c):
    return min(loops, key=lambda lp: np.linalg.norm(verts[lp].mean(0) - c))


def _side(pos, tri):
    """Triangle masks of the left (+x) / right eye pieces."""
    c = pos[tri].mean(1)[:, 0] - HEAD_DX
    return {'L': c > 0, 'R': c < 0}


def _sub(pos, tri, uv, sel):
    used = np.unique(tri[sel])
    lut = -np.ones(len(pos), np.int64)
    lut[used] = np.arange(len(used))
    return used, pos[used], lut[tri[sel]], uv[sel]


def _part_rest(W, name, pos_al, used, post=None):
    """Rest positions of an asset part's sub-piece: W(post(p + Levi's bake)); post maps
    the sub-piece's points before the warp (the lash reshape)."""
    P = pos_al[used]
    d0 = _bakes(lambda s: G.offsets(name, s))[0][used]
    Q = P + d0 if post is None else post(P + d0)
    return W.points(P, Q - P)


def _part_keys(W, name, pos_al, used, extra=None, post=None):
    """Keys of an asset part's sub-piece (vertices `used`), warped W(post(p + bake + d))."""
    keys = {}
    P = pos_al[used]
    get = lambda s: G.offsets(name, s)          # noqa: E731
    d0, lid0 = _bakes(get)
    d0, lid0 = d0[used], lid0[used]
    for n in SHIP_MORPHS:
        d = _src_offsets(get, n)
        if extra and n in extra:
            d = extra[n] if d is None else d + extra[n]
        if d is None:
            continue
        d = d[used]
        kb = _key_bake(n, d0, lid0, P, W.lid_sides)
        if np.abs(d).max() > 1e-7 or np.abs(kb - d0).max() > 1e-7:
            Q = P + kb + d
            if post is not None:
                Q = post(Q)
            keys[n] = W.points(P, Q - P)
    return keys


def _dish_frame(P):
    """Centre, normal (toward the viewer), x / z axes in the plane and radii of
    an iris dish (its fan centre: the vertex nearest the rim's centroid)."""
    c0 = P.mean(0)
    U, s, Vt = np.linalg.svd(P - c0)
    n = Vt[2] if Vt[2][1] < 0 else -Vt[2]
    ex = np.array([1.0, 0.0, 0.0]) - n * n[0]
    ex /= np.linalg.norm(ex)
    ez = np.cross(n, ex)
    if ez[2] < 0:
        ez = -ez
    q = P - c0
    rx, rz = np.abs(q @ ex).max(), np.abs(q @ ez).max()
    centre = P[np.argmin(np.linalg.norm(q - n * (q @ n)[:, None], axis=1))]
    return centre, n, ex, ez, rx, rz


def _hilite(c, n, ex, ez, hx, hz, lift, dish_bvh, seg):
    """An oval card centred at c (in the dish's plane), half-sizes hx, hz [m]: every
    point cast onto the dish along -n and lifted off it, so the card follows the
    dish's curve (a flat card sank behind it at the top)."""
    pts = [c] + [c + ex * (hx * math.cos(2 * math.pi * k / seg)) + ez * (hz * math.sin(2 * math.pi * k / seg))
                 for k in range(seg)]
    out = []
    for p in pts:
        hit = dish_bvh.ray_cast(Vector(p + n * 0.01), Vector(-n), 0.05)
        out.append(np.array(hit[0]) + n * lift if hit[0] is not None else p + n * lift)
    tri = [(0, 1 + k, 1 + (k + 1) % seg) for k in range(seg)]
    return np.array(out), np.array(tri)


def _hole_loop(fc, side):
    """Her face's eye-hole edge (coarse, her rest) on one side."""
    loops = G.boundary_loops([tuple(t) for t in fc['tri']])
    P = fc['pos']
    best = None
    for lp in loops:
        c = P[lp].mean(0)
        d = np.hypot(abs(c[0] - G.MID_X) - G.EYE_C[0], c[2] - G.EYE_C[1])
        if (c[0] - G.MID_X) * side > 0 and d < G.EYE_R[0] and (best is None or d < best[0]):
            best = (d, lp)
    return P[best[1]]


def _snap_brows(P, brow, face_bvh):
    """Her brow strips lowered by BROW_DROP, each point kept her own distance off the face
    (lowered straight down on a sloping forehead they stood 3-4 mm off it)."""
    out = P.copy()
    for v in brow:
        loc, nrm, _, d = face_bvh.find_nearest(Vector(P[v]))
        s0 = (Vector(P[v]) - loc).dot(nrm)
        q = P[v] - np.array([0.0, 0.0, BROW_DROP])
        if BROW_SNAP:
            loc2, nrm2, _, _ = face_bvh.find_nearest(Vector(q))
            q = np.array(loc2 + nrm2 * s0)
        out[v] = q
    return out


def build_eyes(col, W, mat, verts, holes):
    """The white cups, iris dishes (on 目), highlights (on 目) and lash / liner /
    brow strips, from her eye pieces, recoloured to Levi's design in the atlas and
    reshaped toward Levi's (the lash map, the round iris, the highlight)."""
    from . import _head_lash
    wp, wt, wu = G.part('white')
    ip, it, iu = G.part('iris')
    lp, lt, lu = G.part('lash')
    kinds = G.lash_kind()
    white_uv = G.swatch_uv('white')
    names = [str(x) for x in G.data()['swatch_names']]
    ring_uv = G.swatch_uv('ring' if 'ring' in names else 'navy')
    fc = W.fc
    face_bvh = BVHTree.FromPolygons([Vector(p) for p in fc['pos']], [tuple(t) for t in fc['tri']])
    lpb = _snap_brows(lp, np.unique(lt[kinds == 'brow']), face_bvh)
    out = {}
    for sfx, s in (('L', 1.0), ('R', -1.0)):
        sel = _side(wp, wt)[sfx]
        used, P, T, U = _sub(wp, wt, wu, sel)
        _decal(col, f'head_eye_white_{sfx}', _part_rest(W, 'white', wp, used), T, U, mat,
               _part_keys(W, 'white', wp, used))
        sel = _side(ip, it)[sfx]
        used, P, T, U = _sub(ip, it, iu, sel)
        # the lash first (the highlight sits under its margin)
        lsel = _side(lp, lt)[sfx] & ~np.isin(kinds, ('crease', 'other', 'flick'))
        lused, LP, LT, LU = _sub(lpb, lt, lu, lsel)
        upper = np.zeros(len(lused), bool)
        upper[np.unique(LT[kinds[lsel] == 'upper'])] = True
        d0l = _bakes(lambda m: G.offsets('lash', m))[0][lused]
        c_her = 0.5 * (P.min(0) + P.max(0))
        lmap = _head_lash.LashMap(LP, LP + d0l, upper, LT, _hole_loop(fc, s), c_her,
                                  0.5 * (P[:, 0].max() - P[:, 0].min()), s, log=print)
        lpb2 = lpb.copy()
        lpb2[lused] = lmap.pre(LP)
        rest = _part_rest(W, 'lash', lpb2, lused, post=lmap)
        lkeys = _part_keys(W, 'lash', lpb2, lused, post=lmap)
        keep = ~lmap.drop_tris
        live = np.unique(LT[keep])
        lut = -np.ones(len(lused), np.int64)
        lut[live] = np.arange(len(live))
        _decal(col, f'head_eye_lash_{sfx}', rest[live], lut[LT[keep]], LU[keep], mat,
               {k: v[live] for k, v in lkeys.items()})
        margin = rest[lmap.M]
        # the iris: round (her dish squashed in its own plane about a low point, so its
        # bottom stays on the baked lower lid)
        Pw = W.points(P)
        centre, n, ex, ez, rx, rz = _dish_frame(Pw)
        hole = verts[_closest_loop(holes, verts, centre)]
        lo = hole[(hole - centre) @ ez < 0]
        o = np.argsort(lo @ ex)
        z_lid = float(np.interp(0.0, (lo[o] - centre) @ ex, (lo[o] - centre) @ ez))
        sq, behind = IRIS_SQUASH
        zq = (Pw - centre) @ ez
        a_sq = (z_lid - behind - sq * zq.min()) / (1.0 - sq)
        Pw = Pw + ez * ((sq - 1.0) * (zq - a_sq))[:, None]
        centre, n, ex, ez, rx, rz = _dish_frame(Pw)
        q = Pw - centre
        inplane = q - n * (q @ n)[:, None]
        r = np.linalg.norm(inplane / np.array([1.0, 1.0, 1.0]), axis=1) / max(rx, rz)
        sc, a, b = PUPIL_SQUEEZE
        f = sc + (1.0 - sc) * G.smooth(a, b, r)
        small = centre + q - inplane + inplane * f[:, None]
        iris = _decal(col, f'head_eye_{sfx}', Pw, T, U, mat, {'瞳小': small})
        pivot = W.points(G.bone('左目' if s > 0 else '右目')[None])[0]
        iris['levi_eye_pivot'] = tuple(float(v) for v in pivot)
        iris['levi_eye_radius'] = float(np.linalg.norm(centre - pivot))
        dish = BVHTree.FromPolygons([Vector(p) for p in Pw], [tuple(t) for t in T])
        # the highlight: toward the nose, its top HILITE[1] under the margin over the centre
        D = 2.0 * rx * _head_lash.D_SHOW
        nas, gap, hx, hz, lift = HILITE
        mo = np.argsort((margin - centre) @ ex)
        m_up = (margin - centre) @ ez > 0
        mz_c = float(np.interp(0.0, ((margin - centre) @ ex)[mo][m_up[mo]], ((margin - centre) @ ez)[mo][m_up[mo]]))
        hc = centre + ex * (-s * nas * D) + ez * (mz_c - (gap + hz) * D)
        hp, ht = _hilite(hc, n, ex, ez, hx * D, hz * D, lift, dish, HILITE_SEG)
        rw, rlift = HILITE_RING
        rp, rt = _hilite(hc, n, ex, ez, (hx + rw) * D, (hz + rw) * D, rlift, dish, HILITE_SEG)
        cp = np.concatenate([hp, rp])
        ct = np.concatenate([ht, rt + len(hp)])
        cu = np.concatenate([np.full((len(ht), 3, 2), white_uv), np.full((len(rt), 3, 2), ring_uv)])
        hobj = _decal(col, f'head_eye_hilite_{sfx}', cp, ct, cu, mat, {'ハイライト消': cp - n * HILITE_OFF})
        hobj['levi_eye_pivot'] = iris['levi_eye_pivot']
        hobj['levi_eye_radius'] = iris['levi_eye_radius']
        out[sfx] = (pivot, centre, n, rx, rz)
        print(f'HEAD eye {sfx}: lid margin {mz_c / D:+.3f} D over the dish centre, lower lid {z_lid / D:+.3f} D; '
              f'iris {2 * rx * 1000:.1f} x {2 * rz * 1000:.1f} mm (squashed about {a_sq / D:+.3f} D); '
              f'highlight top {(mz_c - gap * D) / D:+.3f} D')
    p = out['L'][0]
    print(f'HEAD eye pivot L ({p[0]:.4f}, {p[1]:.4f}, {p[2]:.4f}) dish {out["L"][1].round(4).tolist()} '
          f'radii {out["L"][3] * 1000:.1f} x {out["L"][4] * 1000:.1f} mm')
    return out


def build_mouth(col, W, teeth_mat, tongue_mat):
    tp, tt, tu = G.part('teeth')
    tp = tp + W.lips.at(tp)          # with the lips (G.LipRest)
    up = np.zeros((len(tp), 3))
    zc = tp[:, 2].mean()
    upper = tp[:, 2] > zc
    up[upper] = (0.0, TEETH_HIDE_M[1], TEETH_HIDE_M[0])
    used = np.arange(len(tp))
    keys = _part_keys(W, 'teeth', tp, used, {'歯無し上': up})
    teeth = bpy.data.objects.new('head_mouth_teeth', _mesh('head_mouth_teeth', _part_rest(W, 'teeth', tp, used), tt))
    col.objects.link(teeth)
    teeth.data.materials.append(teeth_mat)
    teeth.data.shade_smooth()
    teeth['no_outline'] = True
    teeth['levi_cast_shadow'] = False
    add_keys(teeth, keys)
    gp, gt, gu = G.part('tongue')
    gp = gp + W.lips.at(gp)
    y0 = gp[:, 1].min()
    f = G.smooth(TONGUE_OUT_M[2], 0.0, gp[:, 1] - y0)[:, None]
    out = f * np.array([0.0, -TONGUE_OUT_M[0], TONGUE_OUT_M[1]])
    keys = _part_keys(W, 'tongue', gp, np.arange(len(gp)), {'ぺろっ': out})
    bm = bmesh.new()
    vs = [bm.verts.new(Vector(p)) for p in _part_rest(W, 'tongue', gp, np.arange(len(gp)))]
    for t in gt:
        bm.faces.new([vs[i] for i in t])
    tongue = atlas_object(col, 'head_mouth_tongue', bm, tongue_mat, 'tongue')
    tongue['levi_cast_shadow'] = False
    add_keys(tongue, keys)


def _surface_strip(bvh, path, width, lift):
    """A strip on the surface in `bvh` along `path` (world (x, z) stations; the
    points are cast onto the surface from the front), `width` per station."""
    L, R = [], []
    hits = []
    for x, z in path:
        h = bvh.ray_cast(Vector((x, -0.4, z)), Vector((0.0, 1.0, 0.0)), 1.0)
        hits.append((np.array(h[0]), np.array(h[1])))
    for i, (p, n) in enumerate(hits):
        a = hits[max(i - 1, 0)][0]
        b = hits[min(i + 1, len(hits) - 1)][0]
        t = (b - a) / max(np.linalg.norm(b - a), 1e-9)
        s = np.cross(n, t)
        s /= max(np.linalg.norm(s), 1e-9)
        c = p + n * lift
        L.append(c + s * width[i] / 2)
        R.append(c - s * width[i] / 2)
    pts = np.array(L + R)
    m = len(path)
    faces = [(i, i + 1, m + i + 1, m + i) for i in range(m - 1)]
    nrm = np.array([n for _, n in hits] * 2)
    return pts, faces, nrm


def build_fx(col, head, verts, keys, nrm, holes, flush_mat, decal_mat):
    """Overlays hidden behind the face until their key: 照れ (a copy of the cheek
    skin with a deeper flush), 涙, 汗, and the はぅ strokes."""
    me = head.data
    polys = [list(p.vertices) for p in me.polygons]
    rim = {v for lp in holes for v in lp}
    kd_r = KDTree(len(rim))
    for i, v in enumerate(sorted(rim)):
        kd_r.insert(Vector(verts[v]), i)
    kd_r.balance()
    (x0, x1), (z0, z1) = FLUSH_BOX
    sel = []
    for pi, f in enumerate(polys):
        c = verts[f].mean(0)
        if me.polygons[pi].material_index == 0 and x0 < abs(c[0] - HEAD_DX) < x1 and z0 < c[2] < z1 \
                and c[1] < -0.085 and min(kd_r.find(Vector(verts[v]))[2] for v in f) > FLUSH_RIM:
            sel.append(pi)
    used = sorted({v for pi in sel for v in polys[pi]})
    lut = {v: i for i, v in enumerate(used)}
    uvl = me.uv_layers.active.data
    uvs = [[tuple(uvl[li].uv) for li in me.polygons[pi].loop_indices] for pi in sel]
    fme = _mesh('head_fx_flush', verts[used], [[lut[v] for v in polys[pi]] for pi in sel], uvs)
    flush = bpy.data.objects.new('head_fx_flush', fme)
    col.objects.link(flush)
    fme.materials.append(flush_mat)
    fme.shade_smooth()
    fme.normals_split_custom_set_from_vertices([tuple(nrm[v]) for v in used])
    _grad_attr(fme, 0.0)
    flush['no_outline'] = True
    flush['levi_cast_shadow'] = False
    # at rest the overlay waits deep inside the head, FLUSH_PARK of the way to the warp's centre
    # (FX_DEPTH in along the normal put its corner by the eye into the socket, in front of the
    # white cup)
    hidden = verts[used] + FLUSH_PARK * (G.WARP_C - verts[used])
    placed = verts[used] + nrm[used] * FX_LIFT_M
    for v, p in zip(fme.vertices, hidden):
        v.co = Vector(p)
    fk = {'照れ': placed}
    for n, arr in keys.items():          # the cheek moves in the face's morphs: the hidden overlay too
        d = arr[used] - verts[used]
        if np.abs(d).max() > 1e-7:
            fk[n] = hidden + d
    add_keys(flush, fk)
    # tear, sweat (atlas swatches), placed on the face from the front
    bvh = BVHTree.FromPolygons([Vector(p) for p in verts], polys)
    ex = G.EYE_C[0]
    pieces = []
    for s in (1.0, -1.0):
        path = [(HEAD_DX + s * (ex + 0.004 - 0.001 * t), G.EYE_C[1] - 0.017 - 0.011 * t) for t in np.linspace(0, 1, 9)]
        width = [0.0011 + 0.0016 * t ** 3 for t in np.linspace(0, 1, 9)]
        pieces.append(('涙', _surface_strip(bvh, path, width, 0.0003), 'tear'))
    path = [(HEAD_DX - 0.047 + 0.0012 * t, G.EYE_C[1] - 0.015 - 0.009 * t) for t in np.linspace(0, 1, 8)]
    width = [0.0024 * math.sin(math.pi * min(t, 0.999) ** 0.62) + 0.0004 for t in np.linspace(0, 1, 8)]
    pieces.append(('汗', _surface_strip(bvh, path, width, 0.0003), 'sweat'))
    for key, nm in (('涙', 'head_fx_tear'), ('汗', 'head_fx_sweat')):
        bm = bmesh.new()
        placed = []
        for k, (pts, faces, nr), sw in pieces:
            if k != key:
                continue
            vs = [bm.verts.new(Vector(p - n * (FX_DEPTH + 0.0003))) for p, n in zip(pts, nr)]
            placed += list(pts)
            for f in faces:
                bm.faces.new([vs[i] for i in f])
        obj = atlas_object(col, nm, bm, decal_mat, 'tear' if key == '涙' else 'sweat')
        add_keys(obj, {key: placed})
    # はぅ: '>' '<' strokes over the closed lids (apex at the inner corner)
    if 'はぅ' in keys:
        kme = BVHTree.FromPolygons([Vector(p) for p in keys['はぅ']], polys)
        bm = bmesh.new()
        placed = []
        for s in (1.0, -1.0):
            xin, xout = G.EYE_C[0] - 0.012, G.EYE_C[0] + 0.013
            for dz in (0.0042, -0.0042):
                path = [(HEAD_DX + s * (xin + (xout - xin) * t), G.EYE_C[1] - 0.004 + dz * t)
                        for t in np.linspace(0, 1, 10)]
                width = [0.0013 * (1.0 - 0.55 * t) for t in np.linspace(0, 1, 10)]
                pts, faces, _ = _surface_strip(kme, path, width, 0.0005)
                vs = [bm.verts.new(Vector(p + np.array(HAU_HIDE))) for p in pts]
                placed += list(pts)
                for f in faces:
                    bm.faces.new([vs[i] for i in f])
        obj = atlas_object(col, 'head_fx_hau', bm, decal_mat, 'lash')
        add_keys(obj, {'はぅ': placed})


def build(col):
    skin = common.toon_material('skin')
    mouth = common.toon_material('mouth')
    teeth_mat = common.toon_material('cuff')
    face = atlas_material('toon_face', G.ATLAS_PNG, 'levi_face_tex')
    flush_mat = atlas_material('toon_face_flush', G.FLUSH_PNG, 'levi_flush_tex')
    decal_mat = face_material(atlas_pixels(), 'toon_face_decal', 'levi_decal_tex')
    head, W, verts, keys, holes, nrm = build_face(col, face, mouth)
    build_eyes(col, W, face, verts, holes)
    build_mouth(col, W, teeth_mat, decal_mat)
    build_fx(col, head, verts, keys, nrm, holes, flush_mat, decal_mat)
    for side, nm in ((1, 'head_ear_L'), (-1, 'head_ear_R')):
        ear = common.new_object(col, nm, ear_mesh(side), [skin])
        common.shade_smooth(ear, 80)
        common.add_outline(ear)
    _FIELDS.clear()
    return col
