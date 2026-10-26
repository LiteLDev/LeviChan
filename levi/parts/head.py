"""Head: skull, face (profile, nose, jaw), eyes, mouth, ears and the top of the neck.

head_face is one mesh from the crown to the top of the neck. The upper head
(down to just under the eyes, RING_ROWS) is a grid of horizontal rings; below
it the lower face, jaw, chin, under-jaw, throat and neck are one soft surface
of tilted loops (see 'lower face' below and lower_loops). Every ring is two
superellipse halves (face half in front, skull/jaw half behind) whose extents
come from a table of
measurements taken on ref/front.png (half-width) and ref/side.png (front
profile, jaw/skull back line), in reference panel pixels. The skin details
(lashes, brows, blush, nose tip) are painted into a procedurally generated
texture that is projected from the front view, so they land on the exact
panel pixels of the sheet.

The table's front column is the midline profile only. Across the face it is
split into a smooth base front (BASE_FRONT) plus a broad muzzle and the nose
around the midline, so the profile does not drag a band across the cheeks.
relief() then shapes the face in depth along -Y only (so the front-projected
texture stays on its panel pixels): an upper lid rim that carries the lashes,
a lower lid, soft cheeks and the lips / chin. The face's custom normals come
from the same head without nose and relief, blended with some of the real
normal (more of it at the features): clean two-tone shading that still turns
at the cheeks.

Eyes and mouth are real openings with face-like topology: around each one
the ring grid is replaced by a patch of concentric loops (edge loops around
the opening, as in a hand-built face), see `Patch`.
* Behind each eye opening sits an eyeball sphere (fit_eyeball), seen as a
  static white cap (head_eye_white_L / _R, rides 頭) and an iris disc on it
  (head_eye_L / _R: iris, pupil, highlights). The iris turns with the MMD
  eye bones (目.L / 目.R) about the sphere centre, obj['levi_eye_pivot'],
  so it slides over the white. The lids drape on the sphere (hug()) and
  their rim rolls back into it, with a short socket sleeve behind.
* The mouth is a narrow slit into a small pouch (palette 'mouth').
* MMD morphs are shape keys on head_face (value 0): まばたき, ウィンク,
  ウィンク右, 笑い (eyes) and あ, い, う, え, お (mouth). The lids slide over the
  eyeball and stay in front of it along the whole linear morph. The vowels
  open the jaw (the chin and the pouch's lower half turn about a hinge under
  the ear) and shape the lips on top.

Local landmark corrections (spec.L is a +-3 px first pass):
* the face, eyes and neck on ref/front.png are centred on panel column ~321.5,
  not 320, so the whole head is shifted by HEAD_DX (+1.5 px, character's left);
* chin_z: the sheet's front view puts the chin point on row ~162, the side view
  on row ~158; the model ends the (now rounded) chin at row 161.3, its
  profile 1-2.5 px behind the old wedge over rows 155-161; the lower face's
  blur rounds the front-view V into a softer chin (user-approved).
"""
import math
from functools import lru_cache

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

from .. import common, spec, toon

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


def a_of_x(X, row):
    """Ring angle (front half) of the point X px from the midline on `row`."""
    q = _ring_params(row, False)
    u = min(abs(X) / q['hw'], 1.0)
    return math.copysign(math.asin(min(1.0, u ** (1.0 / q['ef']))), X)


def x_of_a(a, row):
    q = _ring_params(row, False)
    s = math.sin(a)
    return q['hw'] * math.copysign(abs(s) ** q['ef'], s)


def face_point(X, row, detail=True):
    """Face surface point at (X px from the midline, row) as seen from the front.
    Below the upper head's rings (the mouth and chin) it is the front of the
    lower-face surface (lower_field)."""
    if row > LOWER_SPLIT:
        return lower_field(detail).front_point(X, row)
    return surf(a_of_x(X, row), row, detail)


# ---------------------------------------------------------------- features (front view px)
# Eye (front view, panel px: X = distance from the face midline, row)
EYE_IN, EYE_OUT = 14.0, 41.0     # inner / outer corner X of the painted eye
EYE_TOP_X, EYE_TOP_ROW = 24.0, 107.0   # flattest point of the upper lid
IRIS = (24.5, 116.8, 8.4, 8.8)   # centre X, centre row, radius X, radius rows


def hexrgb(h):
    h = h.lstrip('#')
    return np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)])


def _quad(p0, p1, p2):
    """Coefficients of the parabola through three (x, y) points."""
    return np.polyfit([p0[0], p1[0], p2[0]], [p0[1], p1[1], p2[1]], 2)


def _soft(d, w=0.35):
    """Coverage from a signed distance in panel px (negative = inside)."""
    return np.clip(0.5 - d / (2 * w), 0.0, 1.0)


def _smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


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
EYE_CX = 26.0                    # patch loops start at the top of the opening at this X


def eye_polygon(step=0.25):
    """The eye opening (white visible between the lash and the lower lid),
    closed, starting at the top at EYE_CX and running clockwise on screen.
    Returns (points [(X, row)], corner points)."""
    top = lambda X: (X, float(lash_bottom(X)))   # noqa: E731
    pts = [top(X) for X in np.arange(EYE_CX, EYE_OC, step)]
    pts += [(X, float(lower_lid(X))) for X in np.arange(EYE_OC, EYE_IN, -step)]
    r0, r1 = float(lower_lid(EYE_IN)), float(lash_bottom(EYE_IN))
    pts += [(EYE_IN, r) for r in np.arange(r0, r1, -step)]
    pts += [top(X) for X in np.arange(EYE_IN, EYE_CX, step)]
    corners = [(EYE_OC, float(lower_lid(EYE_OC))), (EYE_IN, r0), (EYE_IN, r1)]
    return pts, corners


def eye_outer_point(X, row, upper):
    """The opening vertex's partner on the loop around it, which bounds the
    lash band (and a thin rim below and at the corners): the lid moves this
    band rigidly in a blink. Straight out from the opening vertex, so the
    band's quads never cross at the corners."""
    if X <= EYE_IN + 1e-6:
        return X - 1.0, row
    if X >= EYE_OC - 1e-6:
        return X + 1.2, row
    if upper:
        return X, float(upper_lid(X)) - 0.7
    return X, row + 0.9


# Mouth: a narrow slit (front view px) on the painted mouth line
MOUTH_ROW = 146.2
MOUTH_HALF = 4.6                 # half-width of the slit
MOUTH_GAP = 0.6                  # slit height at the centre [px]


def mouth_row(X):
    return MOUTH_ROW - 0.008 * np.asarray(X, float) ** 2


def mouth_polygon(step=0.1, grow=0.0):
    """Slit outline (grow=0) or the lip loop around it (grow>0): a lens,
    closed, starting at the top centre, clockwise on screen."""
    xm = MOUTH_HALF + grow
    half = lambda X: MOUTH_GAP / 2 * math.sqrt(max(0.0, 1 - (X / MOUTH_HALF) ** 2)) \
        + grow * math.sqrt(max(0.0, 1 - (X / xm) ** 2))   # noqa: E731
    pts = [(X, float(mouth_row(X)) - half(X)) for X in np.arange(0.0, xm, step)]
    pts += [(X, float(mouth_row(X)) + half(X)) for X in np.arange(xm, -xm, -step)]
    pts += [(X, float(mouth_row(X)) - half(X)) for X in np.arange(-xm, 0.0, step)]
    return pts, [(xm, float(mouth_row(xm))), (-xm, float(mouth_row(-xm)))]


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
    lid = 0.5 * np.exp(-((R - (y_up + 1.0)) / 2.3) ** 2) * along
    lower = 0.12 * np.exp(-((R - (y_lo + 1.0)) / 2.0) ** 2) * along
    cheek = 0.6 * np.exp(-((X - 25.0) / 11.0) ** 2 - ((R - 131.0) / 9.0) ** 2)
    # lips and chin: restrained upper lip, lower lip and fold (kept faint and
    # narrow: wide bands read as shelves across the lower face)
    lips = (0.15 * np.exp(-((R - 143.6) / 1.8) ** 2) * np.exp(-(X / 5.0) ** 2)
            + 0.08 * np.exp(-((R - 148.3) / 1.4) ** 2) * np.exp(-(X / 4.5) ** 2)
            - 0.05 * np.exp(-((R - 151.0) / 2.0) ** 2) * np.exp(-(X / 6.0) ** 2))
    return socket + lid + lower + cheek + lips


# ---------------------------------------------------------------- textures
TEX_RES = 1024
TEX_PX = 8                       # texture pixels per panel pixel
TEX_COL0 = CENTER_COL - TEX_RES / TEX_PX / 2
TEX_ROW0 = 60.0
SKIN_UV = (2.0 / TEX_RES, 2.0 / TEX_RES)   # plain-skin corner for the back of the head
LASH = '#262A40'


# the lid-shadow layer (EyeShade): colour, strength at the lash line, fade [px]
SHADE_COLOUR, SHADE_ALPHA, SHADE_FADE = '#D3DCEB', 0.8, 2.2
# the 照れ overlay covers the cheeks: X range, bottom row [px]; its top
# follows the lower lid (flush_top)
FLUSH_X, FLUSH_BOTTOM = (11.0, 34.0), 131.0


def flush_top(X):
    return np.maximum(lower_lid(np.clip(X, EYE_IN + 2.0, EYE_OC - 3.0)) + 1.6, 118.5)


def _flush_d(X, R):
    """Distance-like value [px] inside the 照れ overlay (negative outside)."""
    X, R = np.asarray(X, float), np.asarray(R, float)
    return np.minimum.reduce([R - flush_top(X), FLUSH_BOTTOM - R, X - FLUSH_X[0], FLUSH_X[1] - X])


def _flush_fade(X, R):
    """The flush fades out toward the overlay's edge (plain face texture there)."""
    return _smooth(0.4, 2.6, _flush_d(X, R))


def _texture_grid():
    j = (np.arange(TEX_RES) + 0.5) / TEX_PX
    col = TEX_COL0 + j[None, :]
    row = TEX_ROW0 + j[:, None]
    col, row = np.broadcast_arrays(col, row)
    return np.abs(col - CENTER_COL), row


class _Canvas:
    def __init__(self, base):
        self.rgb = np.empty((TEX_RES, TEX_RES, 3))
        self.rgb[:] = base
        self.shade = np.ones((TEX_RES, TEX_RES))

    def paint(self, cov, colour, unshaded=False):
        cov = cov[..., None]
        self.rgb[:] = self.rgb * (1 - cov) + np.asarray(colour) * cov
        if unshaded:
            self.shade[:] = self.shade * (1 - cov[..., 0])

    def pixels(self):
        out = np.empty((TEX_RES, TEX_RES, 4), np.float32)
        out[..., :3] = self.rgb
        out[..., 3] = self.shade
        return out


def _eye_opening_d(X, R):
    """Signed distance-like value of the eye opening [px] (negative inside):
    round outside the corners, and the lid curves are not followed past them
    (they run off steeply)."""
    X = np.asarray(X, float)
    R = np.asarray(R, float)
    Xl = np.clip(X, EYE_IN, EYE_OC)
    dx = np.maximum(EYE_IN - X, X - EYE_OC)
    dr = np.maximum(lash_bottom(Xl) - R, R - lower_lid(Xl))
    return np.where((dx > 0) | (dr > 0), np.hypot(np.maximum(dx, 0), np.maximum(dr, 0)), np.maximum(dx, dr))


def face_texture_pixels(flushed=False):
    """RGBA float array (rows top->bottom). RGB = lit colour, A = 1 where the
    toon shade applies (skin), 0 for unshaded decals (lashes). flushed: the
    texture of the 照れ overlay (a deeper blush with hatching)."""
    X, R = _texture_grid()
    cv = _Canvas(hexrgb(spec.PALETTE['skin']['base']))
    paint = cv.paint

    # blush: a faint, soft wash under the eyes (the sheet has no visible hatching)
    blush = np.exp(-(((X - 24.5) / 9.0) ** 2 + ((R - 125.5) / 3.4) ** 2))
    paint(0.34 * blush, hexrgb('#F6B6AE'))
    for k in range(3):   # barely-there hatch strokes
        xs = 21.0 + 3.0 * k
        d = np.abs((X - xs) + 0.45 * (R - 125.5)) - 0.25
        inside = (np.abs(R - 125.5) < 1.3)
        paint(0.12 * _soft(d) * inside, hexrgb('#EE9C98'))
    if flushed:
        # a broader, deeper flush under the eyes and across the nose's sides,
        # with five clear hatch strokes (faded toward the overlay's edge,
        # _flush_fade, so it meets the plain face without a seam)
        wash = np.exp(-(((X - 24.0) / 10.5) ** 2 + ((R - 127.0) / 3.6) ** 2))
        fade = _flush_fade(X, R)
        paint(0.62 * wash * fade, hexrgb('#F49C98'))
        for k in range(5):
            xs = 17.5 + 3.0 * k
            d = np.abs((X - xs) + 0.5 * (R - 127.0)) - 0.32
            inside = _soft(np.abs(R - 127.0) - 1.9, 0.5)
            paint(0.55 * _soft(d) * inside * fade, hexrgb('#E07479'))

    y_up = upper_lid(X)
    y_lo = lower_lid(X)
    inner_d = EYE_IN - X
    # inside the opening only the lid's inner rim shows (the eyeball is its
    # own object): the lash colour under the upper lid, plain skin under
    # the lower one
    opening = _soft(_eye_opening_d(X, R) - 0.6, 0.6)
    upper_half = R < (lash_bottom(X) + y_lo) / 2
    paint(opening * upper_half, hexrgb(LASH), unshaded=True)
    paint(opening * ~upper_half, hexrgb(spec.PALETTE['skin']['base']))

    # upper lash mass: ~2.5 px, thicker toward the outer corner, with a flick
    thick = lash_thick(X)
    lash_d = np.maximum.reduce([y_up - 0.7 - R, R - (y_up + thick), inner_d - 0.3, X - (EYE_OUT + 1.2)])
    flick = np.maximum.reduce([np.abs(R - (112.0 - 0.8 * (X - EYE_OUT))) - 0.7, EYE_OUT - 0.8 - X,
                               X - (EYE_OUT + 2.2)])
    lash = np.maximum(_soft(lash_d), _soft(flick))
    paint(lash, hexrgb(LASH), unshaded=True)
    # lower lid: fine line on the outer half
    lo_d = np.maximum.reduce([np.abs(R - y_lo - 0.3) - 0.35, 27.0 - X, X - (EYE_OUT - 1.0)])
    paint(0.6 * _soft(lo_d), hexrgb('#B07A72'))
    # inner corner tick
    ic_d = np.maximum(np.abs(X - (EYE_IN - 0.3)) - 0.35, np.maximum(y_up + 1.0 - R, R - (y_up + 5.0)))
    paint(0.5 * _soft(ic_d), hexrgb('#A9706A'))

    # lid crease / brow: a soft mauve line above the lash (mostly under the bangs)
    brow_c = 103.9 - 0.04 * (X - 20.0) + 0.006 * (X - 26.0) ** 2
    taper = 0.42 * (1.15 - np.clip((X - 14) / 24, 0, 1))
    brow_d = np.maximum(np.abs(R - brow_c) - taper, np.maximum(15.0 - X, X - 37.0))
    paint(0.7 * _soft(brow_d, 0.5), hexrgb('#C08A84'))

    # nose tip: a faint, small mark
    nose_d = np.hypot(X / 1.0, (R - 132.0) / 0.5) - 1.0
    paint(0.25 * _soft(nose_d * 0.6), hexrgb("#E2A49C"))
    # mouth: the slit is geometry; a soft lip-line tint around it carries the
    # drawn mouth stroke's weight and fades toward the corners
    mouth_d = np.maximum(np.abs(R - mouth_row(X)) - 0.55, X - (MOUTH_HALF + 0.2))
    gap = 0.55 + 0.25 * np.clip(X / 1.5, 0, 1)
    paint(0.8 * gap * _soft(mouth_d, 0.45), hexrgb('#9C5A55'))
    lip_d = np.hypot(X / 2.2, (R - 147.3) / 0.6) - 1.0
    paint(0.12 * _soft(lip_d * 0.6), hexrgb(spec.PALETTE['mouth']['base']))
    return cv.pixels()


def eye_texture_pixels(iris_only=False, shade=False):
    """The eyes' texture in the same front-view mapping. All unshaded (A = 0).
    The white (sclera, static): plain white. shade: the lid-shadow layer
    (EyeShade) over the white: the upper lid's soft blue-grey shadow, fading
    to white below the lashes. The iris (turns with the eye bone, iris_only):
    muted dark green top -> light mint bottom, soft rim, slit pupil and the
    lashes' shadow band; the highlights are their own geometry (Highlights)."""
    X, R = _texture_grid()
    cv = _Canvas(hexrgb('#FFFFFF'))
    paint = lambda cov, colour: cv.paint(cov, colour, unshaded=True)   # noqa: E731
    paint(np.ones_like(X), hexrgb('#FFFFFF'))
    y_up = upper_lid(X)
    if shade:
        Xl = np.clip(X, EYE_IN, EYE_OC)
        t = np.clip((R - lash_bottom(Xl)) / SHADE_FADE, 0.0, 1.0)
        paint(SHADE_ALPHA * (1.0 - t * t * (3.0 - 2.0 * t)), hexrgb(SHADE_COLOUR))
        return cv.pixels()
    if not iris_only:
        return cv.pixels()
    ix, iy, irx, iry = IRIS
    q = np.sqrt(((X - ix) / irx) ** 2 + ((R - iy) / iry) ** 2)
    iris = _soft((q - 1.0) * irx)
    t = np.clip((R - (iy - iry * 0.6)) / (1.5 * iry), 0, 1)[..., None]
    grad = (1 - t) * hexrgb('#235E40') + t * hexrgb('#78CC94')
    rim = np.clip((q - 0.8) / 0.2, 0, 1)[..., None]
    paint(iris, grad * (1 - 0.4 * rim) + hexrgb('#1A4A30') * 0.4 * rim)
    q = np.sqrt(((X - (ix - 0.4)) / 1.3) ** 2 + ((R - 114.2) / 4.0) ** 2)
    paint(_soft((q - 1.0) * 1.3) * 0.8, hexrgb('#123F28'))
    # upper iris shadow band cast by the lashes
    paint(iris * 0.35 * _soft(R - (y_up + 3.2), 1.2), hexrgb('#143F2A'))
    return cv.pixels()


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


def front_uv(co):
    colp = spec.PANEL_W / 2 + co.x * PPM
    rowp = spec.SHEET_GROUND_Y - co.z * PPM
    return ((colp - TEX_COL0) * TEX_PX / TEX_RES, 1.0 - (rowp - TEX_ROW0) * TEX_PX / TEX_RES)


# ---------------------------------------------------------------- face topology
EYE_BOX = ((99.0, 131.5), 6.5, math.radians(88.0))   # rows, inner X [px], outer ring angle
EYE_LOOPS = (0.2, 0.42, 0.7)     # intermediate loops between the lash loop (0) and the grid (1)
MOUTH_BOX = ((139.0, 154.25), 9.0)                   # rows, half-width [px]
MOUTH_LOOPS = (0.25, 0.5, 0.75)
MOUTH_OUTLINE = (0.2, 0.6, 0.9, 1.0)   # outline hull width on the mouth loops from the slit out
EYE_GAP = 0.35                   # px between the opening's rim and the eyeball (closest point)
EYE_WALL_IN = 0.4                # px the rim rolls back into the eyeball
EYE_SLEEVE = 5.0                 # px deep socket sleeve behind the rim: what a turned eyeball uncovers
POUCH_BACK = (0.7, 6.2)          # px behind the slit: the slit's back rim, the cavity's back centre
POUCH_ROW = MOUTH_ROW + 0.9       # the cavity's centre row behind the slit
# the mouth cavity behind the lips' inner rim: rings (depth behind the face
# surface [px], centre row, half-width, half-height): a rounded bowl roomy
# enough for the upper teeth (under its roof) and the tongue (on its floor)
POUCH_RINGS = ((1.5, MOUTH_ROW + 0.45, 4.9, 2.45), (3.6, MOUTH_ROW + 0.8, 6.0, 3.4),
               (5.4, MOUTH_ROW + 1.0, 4.6, 2.8))


def _nearest(seq, v):
    return int(np.argmin([abs(s - v) for s in seq]))


def _resample(poly, fracs, corners=()):
    """Points at the arc-length fractions `fracs` of the closed polygon
    (starting at poly[0]); the samples nearest the corner points snap onto them."""
    pts = np.asarray(poly, float)
    seg = np.linalg.norm(np.roll(pts, -1, axis=0) - pts, axis=1)
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    out = []
    for f in fracs:
        s = f * cum[-1]
        k = int(np.clip(np.searchsorted(cum, s, side='right') - 1, 0, len(pts) - 1))
        t = (s - cum[k]) / max(seg[k], 1e-12)
        out.append(pts[k] + (pts[(k + 1) % len(pts)] - pts[k]) * t)
    out = np.array(out)
    for c in corners:
        k = 1 + int(np.argmin(np.linalg.norm(out[1:] - np.asarray(c), axis=1)))
        out[k] = c
    return [tuple(p) for p in out]


class Patch:
    """A rectangle of the ring grid (rows i0..i1, ring indices k0..k1 in
    `local` order) replaced by concentric loops: the grid boundary B, loops
    interpolated toward the feature, the outer feature loop C1 and the opening
    C0. Local X is measured outward for an eye (side = +1 left, -1 right), and
    signed for the mouth (side = 0).

    loops[j][m]: vertex index; px[j][m]: the rest (local X, row); fade[j]:
    share of the opening's morph motion loop j takes."""

    def __init__(self, kind, side, i0, i1, kl0, kl1):
        self.kind, self.side = kind, side
        self.i0, self.i1, self.kl0, self.kl1 = i0, i1, kl0, kl1
        self.loops, self.px, self.fade = [], [], []
        self.upper = []        # per opening vertex: on the upper lid / lip
        self.wall = []         # eye: rim vertices rolled into the eyeball; mouth: slit back rim
        self.pouch = []        # mouth: pouch back loop + centre; eye: socket sleeve behind the rim

    def k(self, kl):
        return kl if self.side >= 0 else N_RING - kl

    def sign(self):
        return -1.0 if self.side < 0 else 1.0

    def cells(self):
        return {(i, self.k(kl)) for i in range(self.i0, self.i1) for kl in range(self.kl0, self.kl1)} \
            if self.side >= 0 else \
            {(i, self.k(kl) - 1) for i in range(self.i0, self.i1) for kl in range(self.kl0, self.kl1)}

    def interior(self):
        return {(i, self.k(kl)) for i in range(self.i0 + 1, self.i1) for kl in range(self.kl0 + 1, self.kl1)}

    def boundary(self, start_kl):
        """Grid boundary (i, local kl), clockwise on screen from the top edge at start_kl."""
        i0, i1, a, b = self.i0, self.i1, self.kl0, self.kl1
        loop = [(i0, kl) for kl in range(start_kl, b)] + [(i, b) for i in range(i0, i1)]
        loop += [(i1, kl) for kl in range(b, a, -1)] + [(i, a) for i in range(i1, i0, -1)]
        loop += [(i0, kl) for kl in range(a, start_kl)]
        return loop


def make_patches(angles, rows):
    half = N_RING // 2
    (ra, rb), x_in, a_out = EYE_BOX
    i0, i1 = _nearest(rows, ra), _nearest(rows, rb)
    row_mid = rows[(i0 + i1) // 2]
    kl0 = next(k for k in range(half, N_RING) if x_of_a(angles[k], row_mid) >= x_in)
    kl1 = max(k for k in range(half, N_RING) if angles[k] <= a_out)
    return [Patch('eye', s, i0, i1, kl0, kl1) for s in (1, -1)]   # (the mouth: mouth_patch)


EYE_R_RANGE = (14.0, 36.0)      # eyeball radius search range [px]
EYE_RIM_SIN = 0.88               # the rim stays within ~62 deg of the eyeball's front (seen from the front)
EYE_PIVOT_BOX = (4.0, 40.0, 106.0, 126.0)   # eyeball centre search box: X, X, row, row [px]


def fit_eyeball(P):
    """Sphere behind the eye opening's rim points P (world), as deep as needed
    for the rim to stay EYE_GAP in front of it everywhere; centre and radius
    chosen so the rim stays as close to the sphere as possible all round (the
    face around the eye is a plate turned outward, so the centre sits behind
    it, outward of the iris). Returns (centre, radius) in world units."""
    pts = np.array([(p.x, p.y, p.z) for p in P]) * PPM
    g = EYE_GAP
    xs = HEAD_DX * PPM + np.arange(EYE_PIVOT_BOX[0], EYE_PIVOT_BOX[1] + 1e-6, 0.5)
    zs = zr(np.arange(EYE_PIVOT_BOX[2], EYE_PIVOT_BOX[3] + 1e-6, 0.5)) * PPM
    cx, cz = np.meshgrid(xs, zs, indexing='ij')
    best = None
    dxz2 = (pts[None, None, :, 0] - cx[..., None]) ** 2 + (pts[None, None, :, 2] - cz[..., None]) ** 2
    reach2 = dxz2.max(axis=2)
    for r in np.arange(EYE_R_RANGE[0], EYE_R_RANGE[1] + 1e-6, 0.5):
        ok = reach2 < (EYE_RIM_SIN * (r + g)) ** 2   # rim well inside the outline: no grazing walls
        cy = (pts[None, None, :, 1] + np.sqrt(np.clip((r + g) ** 2 - dxz2, 0, None))).max(axis=2)
        dist = np.sqrt(dxz2 + (pts[None, None, :, 1] - cy[..., None]) ** 2)
        cost = np.where(ok, dist.max(axis=2) - (r + g), np.inf)
        i, j = np.unravel_index(np.argmin(cost), cost.shape)
        if np.isfinite(cost[i, j]) and (best is None or cost[i, j] < best[0] - 1e-6):
            best = (cost[i, j], Vector((cx[i, j], cy[i, j], cz[i, j])) / PPM, r / PPM)
    if best is None:
        raise ValueError('head: no eyeball sphere fits the eye opening; widen EYE_PIVOT_BOX / EYE_R_RANGE')
    print(f"HEAD eyeball fit: rim spread {best[0]:.2f} px")
    return best[1], best[2]


def sphere_y(c, r, x, z):
    """Front surface y of the sphere at (x, z), or None outside its outline."""
    d2 = r * r - (x - c.x) ** 2 - (z - c.z) ** 2
    return c.y - math.sqrt(d2) if d2 > 0 else None


def sphere_point(c, r, x, z):
    """Point on the sphere's front at (x, z); outside its outline, the nearest
    outline point."""
    d = Vector((x - c.x, 0.0, z - c.z))
    if d.length >= r:
        d = d.normalized() * r
    return Vector((c.x + d.x, c.y - math.sqrt(max(0.0, r * r - d.length_squared)), c.z + d.z))


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
LOWER_SPLIT = LOWER_TOP           # face_point: below this row, the lower-face surface
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
LOWER_FRONT_EXP = ((131.5, 2.55), (140.0, 2.25), (148.0, 2.08), (156.0, 2.0), (161.3, 2.0))
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
LOWER_RELIEF = ((-0.45, 150.4, 1.9, 7.0), (0.35, 155.6, 2.6, 6.0))


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


def front_y_vec(row, X, detail):
    """_front_y vectorized over X >= 0 (array), with the lower face's rounder
    sections and smaller muzzle (identical to ring() down to LOWER_TOP). The
    muzzle's removed share moves the base front forward, so the midline stays
    on the measured profile."""
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
    if detail:
        yp = yp - q['nose'] * np.exp(-(X / q['sig']) ** 2) - relief(X, row) * _smooth(0.05, 0.3, c)
    return yp


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


def mouth_patch(pts, i_top):
    """The mouth's patch on the lower loops: between the loops nearest the
    MOUTH_BOX rows at the midline, MOUTH_BOX's half-width wide at the mouth."""
    half = N_RING // 2
    front = [row_of(lp[half].z) for lp in pts]
    (ra, rb), mx = MOUTH_BOX
    cand = range(i_top + 1, len(pts))
    near = lambda r: min(cand, key=lambda i: abs(front[i] - r))   # noqa: E731
    im = near(MOUTH_ROW)
    m = next(d for d in range(1, half) if abs(pts[im][half + d].x - HEAD_DX) * PPM >= mx)
    return near(ra), near(rb), half - m, half + m


def build_head(detail=True, eye_fit=None, layout=None):
    """BMesh of head_face, its patches, the eyeballs and the lower-face layout.
    eye_fit: the left eyeball (centre, radius) from the detailed head; fitted
    here when None. layout: the detailed head's (see lower_loops)."""
    angles, rows = ring_angles(N_RING), RING_ROWS
    pts = [ring(r, angles, detail) for r in rows]
    lower, layout = lower_loops(pts[-1], detail, layout)
    pts += lower
    patches = make_patches(angles, rows)
    if 'mouth' not in layout:
        layout['mouth'] = mouth_patch(pts, len(rows) - 1)
    patches.append(Patch('mouth', 0, *layout['mouth']))
    skip_v = set().union(*(p.interior() for p in patches))
    skip_f = set().union(*(p.cells() for p in patches))
    bm = bmesh.new()
    grid = {}
    for i, lp in enumerate(pts):
        for k, p in enumerate(lp):
            if (i, k) not in skip_v:
                grid[i, k] = bm.verts.new(p)
    for i in range(len(pts) - 1):
        for k in range(N_RING):
            if (i, k) in skip_f:
                continue
            k2 = (k + 1) % N_RING
            bm.faces.new((grid[i, k], grid[i, k2], grid[i + 1, k2], grid[i + 1, k]))
    bm.faces.new([grid[0, k] for k in reversed(range(N_RING))])   # the neck end stays open

    eyes = {}
    for p in patches:
        if p.kind == 'eye':
            build_patch(bm, p, grid, angles, rows, detail)
        else:
            build_mouth_patch(bm, p, grid, detail)
        if p.kind == 'eye' and p.side > 0:
            eyes[1] = eye_fit if eye_fit else fit_eyeball([bm.verts[v].co.copy() for v in p.loops[0]])
            eyes[-1] = mirror_eye(eyes[1])
    _sync(bm)
    layout.setdefault('vloop', {v.index: i for (i, k), v in grid.items()})
    for v in bm.verts:
        v.co = hug(v.co, eyes)
    for p in patches:
        if p.kind == 'eye':
            add_eye_rim(bm, p, *eyes[p.side])
        else:
            add_pouch(bm, p, detail)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    front = min(bm.faces, key=lambda f: f.calc_center_median().y)
    if front.normal.y > 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces)
    return bm, patches, eyes, layout


HUG_BAND = (0.5, 5.0)            # px outside the opening: lids drape on the eyeball .. own shape
IRIS_REACH = (11.0, 19.0)        # px from the iris centre: where a turned iris can roll (fading)
HUG_DISC = (0.72, 0.9)           # share of the eyeball radius (seen from the front) the cover fades over
HUG_SOFT = 1.0                   # px: softness of the cover push


def hug(co, eyes):
    """The lids drape over the eyeball: near the opening the face sits EYE_GAP
    (plus the lid rims' thickness) in front of the eyeball sphere, fading back
    to its own shape HUG_BAND px outside the opening. Further out, where the
    iris can roll to, the skin is only kept in front of the sphere (a soft
    push, fading out smoothly), so a turned iris stays under the skin."""
    if not eyes:
        return co
    X = (co.x - HEAD_DX) * PPM
    c, r = eyes[1 if X >= 0 else -1]
    ys = sphere_y(c, r, co.x, co.z)
    if ys is None or co.y > c.y:     # (the back of the head is not the face)
        return co
    X, R = abs(X), row_of(co.z)
    disc = 1.0 - float(_smooth(HUG_DISC[0], HUG_DISC[1], math.hypot(co.x - c.x, co.z - c.z) / r))
    w_near = (1.0 - float(_smooth(HUG_BAND[0], HUG_BAND[1], _eye_opening_d(X, R)))) * disc
    w_far = (1.0 - float(_smooth(IRIS_REACH[0], IRIS_REACH[1], math.hypot(X - IRIS[0], R - IRIS[1])))) * disc
    if w_near <= 0.0 and w_far <= 0.0:
        return co
    along = _smooth(EYE_IN - 4.0, EYE_IN + 1.0, X) * (1.0 - _smooth(EYE_OUT + 0.5, EYE_OUT + 5.0, X))
    Xl = min(max(X, EYE_IN), EYE_OUT)
    rim = 0.35 * np.exp(-((R - (upper_lid(Xl) + 1.0)) / 2.3) ** 2) * along \
        + 0.1 * np.exp(-((R - (lower_lid(Xl) + 1.0)) / 2.0) ** 2) * along
    out = co.copy()
    out.y += (ys - (EYE_GAP + float(rim)) / PPM - co.y) * w_near
    # a soft max(0, excess) (C1, zero below -HUG_SOFT): a hard one leaves a
    # crease where the skin meets the sphere
    h = HUG_SOFT / PPM
    e = out.y - (ys - EYE_GAP / PPM)
    push = 0.0 if e <= -h else (e if e >= h else (e + h) ** 2 / (4 * h))
    out.y -= push * w_far
    return out


def mirror_eye(fit):
    c, r = fit
    return Vector((2 * HEAD_DX - c.x, c.y, c.z)), r


def _new_vert(bm, co):
    return bm.verts.new(co)


def _sync(bm):
    bm.verts.index_update()
    bm.verts.ensure_lookup_table()
    bm.verts.ensure_lookup_table()


def _patch_boundary(p, grid, start):
    """The patch's grid boundary vertices (clockwise on screen from `start` on
    the top edge) and each one's arc-length fraction around it."""
    bverts = [grid[i, p.k(kl)] for i, kl in p.boundary(start)]
    seg = [(bverts[(m + 1) % len(bverts)].co - bverts[m].co).length for m in range(len(bverts))]
    return bverts, np.concatenate([[0.0], np.cumsum(seg)[:-1]]) / sum(seg)


def _bridge(bm, p, loops):
    """Quads between consecutive patch loops (BMVerts, the opening first)."""
    n = len(loops[0])
    for a, b in zip(loops, loops[1:]):
        for m in range(n):
            m2 = (m + 1) % n
            bm.faces.new((a[m], a[m2], b[m2], b[m]))
    _sync(bm)
    p.loops = [[v.index for v in lp] for lp in loops]


def build_patch(bm, p, grid, angles, rows, detail):
    """Concentric loops from the grid boundary to the eye opening, laid out
    in (ring angle, row) on the upper head's rings."""
    start = min(range(p.kl0 + 1, p.kl1), key=lambda kl: abs(x_of_a(angles[kl], rows[p.i0]) - EYE_CX))
    bverts, fr = _patch_boundary(p, grid, start)
    c0, c0_corners = eye_polygon()
    C0 = _resample(c0, fr, c0_corners)
    mid = lambda X: (lash_bottom(X) + lower_lid(X)) / 2   # noqa: E731
    p.upper = [r < mid(min(max(X, EYE_IN), EYE_OC)) - 1e-6 for X, r in C0]
    C1 = [eye_outer_point(X, r, up) for (X, r), up in zip(C0, p.upper)]
    sgn = p.sign()
    # loops in (local angle, row): C1 -> boundary
    b_par = [(angles[kl], rows[i]) for i, kl in p.boundary(start)]
    c1_par = [(a_of_x(X, r), r) for X, r in C1]
    loops_par = [[(a1 + (ab - a1) * t, r1 + (rb - r1) * t) for (a1, r1), (ab, rb) in zip(c1_par, b_par)]
                 for t in EYE_LOOPS]

    def px_of(par):
        return (x_of_a(par[0], par[1]), par[1])

    loops = [[_new_vert(bm, face_point(X * sgn, r, detail)) for X, r in C] for C in (C0, C1)]
    p.px = [list(C0), list(C1)]
    p.fade = [1.0, 1.0]
    for t, lp in zip(EYE_LOOPS, loops_par):
        loops.append([_new_vert(bm, surf(a * sgn, r, detail)) for a, r in lp])
        p.px.append([px_of(par) for par in lp])
        p.fade.append((1.0 - t) ** 1.5)
    loops.append(bverts)
    p.px.append([px_of(par) for par in b_par])
    p.fade.append(0.0)
    _bridge(bm, p, loops)


def build_mouth_patch(bm, p, grid, detail):
    """Concentric loops from the grid boundary to the mouth slit, laid out in
    front-view (X, row) and placed on the lower-face surface."""
    start = min(range(p.kl0 + 1, p.kl1), key=lambda kl: abs(grid[p.i0, p.k(kl)].co.x - HEAD_DX))
    bverts, fr = _patch_boundary(p, grid, start)
    c0, c0_corners = mouth_polygon()
    C0 = _resample(c0, fr, c0_corners)
    p.upper = [r < float(mouth_row(X)) - 1e-6 for X, r in C0]
    lips, lip_corners = mouth_polygon(grow=0.9)
    C1 = _resample(lips, fr, lip_corners)
    B = [((v.co.x - HEAD_DX) * PPM, row_of(v.co.z)) for v in bverts]
    p.px = [list(C0), list(C1)]
    p.fade = [1.0, 1.0]
    for t in MOUTH_LOOPS:
        p.px.append([(x1 + (xb - x1) * t, r1 + (rb - r1) * t) for (x1, r1), (xb, rb) in zip(C1, B)])
        p.fade.append((1.0 - t) ** 1.5)
    flat = [xr for lp in p.px for xr in lp]
    pts = lower_field(detail).front_points([x for x, _ in flat], [r for _, r in flat])
    loops, k = [], 0
    for lp in p.px:
        loops.append([_new_vert(bm, _world(P)) for P in pts[k:k + len(lp)]])
        k += len(lp)
    loops.append(bverts)
    p.px.append(B)
    p.fade.append(0.0)
    _bridge(bm, p, loops)


def add_eye_rim(bm, p, c, r):
    """The opening's rim rolls back radially into the eyeball sphere."""
    c0 = [bm.verts[v] for v in p.loops[0]]
    rim = [_new_vert(bm, eye_rim_point(v.co, c, r)) for v in c0]
    sleeve = [_new_vert(bm, eye_rim_point(v.co, c, r, EYE_SLEEVE)) for v in c0]
    n = len(c0)
    for m in range(n):
        m2 = (m + 1) % n
        bm.faces.new((rim[m], rim[m2], c0[m2], c0[m]))
        bm.faces.new((sleeve[m], sleeve[m2], rim[m2], rim[m]))
    _sync(bm)
    p.wall = [v.index for v in rim]
    p.pouch = [v.index for v in sleeve]


def eye_rim_point(co, c, r, depth=EYE_WALL_IN):
    return c + (co - c).normalized() * (r - depth / PPM)


def pouch_back(co):
    return co + Vector((0.0, POUCH_BACK[0] / PPM, 0.0))


def pouch_point(X, row, depth, detail=True):
    """A point `depth` px behind the face surface at front-view (X, row)."""
    return face_point(X, row, detail) + Vector((0.0, depth / PPM, 0.0))


def add_pouch(bm, p, detail):
    """The mouth slit's lips roll back into a closed cavity (POUCH_RINGS)."""
    c0 = [bm.verts[v] for v in p.loops[0]]
    rim = [_new_vert(bm, pouch_back(v.co)) for v in c0]
    rings = []
    for depth, crow, hx, hy in POUCH_RINGS:
        ring = []
        for (X, rr) in p.px[0]:
            ang = math.atan2((rr - float(mouth_row(X))) / MOUTH_GAP, X / MOUTH_HALF)
            ring.append(_new_vert(bm, pouch_point(math.cos(ang) * hx, crow + math.sin(ang) * hy, depth, detail)))
        rings.append(ring)
    mid = _new_vert(bm, pouch_point(0.0, POUCH_ROW, POUCH_BACK[1], detail))
    n = len(c0)
    for m in range(n):
        m2 = (m + 1) % n
        # the lips' inner edge and the cavity: 'mouth' (the painted lip line
        # stays on the lips' outer face, so an open mouth is not ringed by it)
        faces = [bm.faces.new((rim[m], rim[m2], c0[m2], c0[m]))]
        faces += [bm.faces.new((b[m], b[m2], a[m2], a[m])) for a, b in zip([rim] + rings, rings)]
        faces.append(bm.faces.new((mid, rings[-1][m2], rings[-1][m])))
        for f in faces:
            f.material_index = 1                                  # the cavity: 'mouth'
    _sync(bm)
    p.wall = [v.index for v in rim]
    p.pouch = [v.index for ring in rings for v in ring] + [mid.index]


# ---------------------------------------------------------------- morphs
# MMD expression morphs: shape keys at value 0 at rest. head_face carries the
# lid, brow and mouth motion. The other head pieces carry the same keys where
# they move: the lashes and the lid shadow follow the lids, the iris shrinks
# (瞳小), the highlights go out (ハイライト消), the teeth and tongue go with
# the mouth. The overlays (照れ, 涙, 汗 and the はぅ strokes) wait hidden
# inside the head and move into place. Panels: export_pmx.MORPH_INFO.
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
LID_OVERLAP = 0.25               # px the closed upper lid sits in front of the lower lid
LID_PATH = 0.2                   # px the lids keep in front of the eyeball along a morph
HAU_LINE = (120.0, 7.0)          # はぅ: the lids meet on a line from the inner corner (row) rising this much outward
JITO_ROW = 113.8                 # じと目: the flat upper lid's row
SMILE_ARCH = 2.5                 # 笑い: px the closed lids' middle rises over the corners' line


def eye_affects(name, side):
    """Whether the eye morph `name` moves the eye on `side` (+1 left, -1 right)."""
    return not ((name == 'ウィンク' and side < 0) or (name == 'ウィンク右' and side > 0))


def eye_open_shift(name, Xc):
    """(upper, lower) lid edge shift [rows, + down] at Xc of an open-eye morph."""
    top, bot = float(lash_bottom(Xc)), float(lower_lid(Xc))
    h = bot - top
    u = min(max((Xc - EYE_IN) / (EYE_OC - EYE_IN), 0.0), 1.0)
    mid = math.sin(math.pi * u) ** 0.7
    if name == 'なごみ':      # calm: heavy, relaxed lids
        return 0.42 * h, -0.1 * h
    if name == 'びっくり':    # surprised: wide open at the middle, the corners stay
        return -1.8 * mid, 1.1 * mid
    if name == 'じと目':      # half-lidded: a flat upper lid across the iris
        return min(max(JITO_ROW - top, 0.0), 0.8 * h), -0.6 * mid
    # キリッ (determined): the inner upper lid comes down, the lower lid rises
    return 2.6 * (1.0 - u) ** 1.5 + 0.5 * mid, -1.2 * mid


def eye_motion(name, X, row, upper):
    """(dX, drow, forward) of an opening vertex in the eye morph `name` [px]."""
    Xc = min(max(X, EYE_IN), EYE_OC)
    if name in EYE_OPEN:
        up, lo = eye_open_shift(name, Xc)
        if X <= EYE_IN + 1e-6:     # the inner edge, in order: from the upper to the lower lid's shift
            top, bot = float(lash_bottom(Xc)), float(lower_lid(Xc))
            t = min(max((row - top) / max(bot - top, 1e-6), 0.0), 1.0)
            return 0.0, up + (lo - up) * t, 0.0
        return 0.0, (up if upper else lo), 0.0
    close = float(lower_lid(Xc)) - 1.4            # where the lids meet
    if name == '笑い':
        # smiling eyes: closed along an upward arch (the middle above both
        # corners), the lower lid and the cheek under it pushed up to meet it
        u = min(max((X - EYE_IN) / (EYE_OC - EYE_IN), 0.0), 1.0)
        c_in, c_out = float(lower_lid(EYE_IN)) - 1.4, float(lower_lid(EYE_OC)) - 1.4
        close = c_in + (c_out - c_in) * u - SMILE_ARCH * math.sin(math.pi * u) ** 0.9
    elif name == 'はぅ':
        # squeezed shut: the lids meet on a line rising from the inner corner
        # to the outer one (the upper stroke of '>' / '<'); the lower stroke
        # is an overlay (Fx 'hau')
        close = HAU_LINE[0] - HAU_LINE[1] * (Xc - EYE_IN) / (EYE_OC - EYE_IN)
    # the vertical inner edge keeps a trace of its height (in order), so its
    # vertices close onto a short line instead of collapsing onto one point
    spread = 0.12 * (row - float(lash_bottom(Xc) + lower_lid(Xc)) / 2) if X <= EYE_IN + 1e-6 else 0.0
    if upper:
        return 0.0, close + 0.5 + spread - row, LID_OVERLAP
    return 0.0, close + spread - row, 0.0


# The vowels open the jaw: everything below the mouth line (lower lip, chin,
# under-jaw, the lower half of the mouth pouch) turns about the jaw hinge
# (below the ear) by JAW_OPEN degrees, times jaw_share(); the lips then shape
# the opening (mouth_motion). The throat and neck stay (the share fades out
# over the first neck loops), and the cheeks stretch between.
JAW_OPEN = {'あ': 9.0, 'い': 2.2, 'う': 2.2, 'え': 5.2, 'お': 6.5,       # degrees
            'ワ': 11.0, '▲': 3.0, 'にやり': 1.2, 'ぺろっ': 6.0}
JAW_HINGE = (287.0, 133.0)        # side-view col, row of the hinge axis (along X)
JAW_LINE = (0.45, 4.0, 0.35)      # the jaw's moving part ends along a line rising from the mouth
#                                   corners toward the hinge: rise per px of X, band half-width + growth per px


def mouth_motion(name, X, row, upper):
    """(dX, drow, forward) of a slit vertex in the mouth morph `name` [px]:
    the lips' own shape, on top of the jaw."""
    w = max(0.0, 1.0 - (X / MOUTH_HALF) ** 2) ** 0.7
    pull = 1.0 - 0.3 * abs(X) / MOUTH_HALF
    c = min((X / MOUTH_HALF) ** 2, 1.0)            # the corners
    shut = (0.27 if upper else -0.27) * w           # the lips meet (the slit closes)
    if name == 'ワ':      # wide open
        return 0.35 * X, (-1.4 if upper else 0.15) * w, 0.0
    if name == 'ん':      # lips pressed together
        return -0.06 * X, shut, 0.25 * pull
    if name == '∧':      # closed, the corners down
        return -0.04 * X, shut - 0.5 + 1.5 * (abs(X) / MOUTH_HALF) ** 1.2, 0.0
    if name == 'ω':      # cat mouth: corners and middle up, dips between
        return -0.08 * X, shut - 0.55 * math.cos(2.0 * math.pi * X / MOUTH_HALF), 0.35 * pull
    if name == '▲':      # open triangle: the upper lip peaks at the middle
        return 0.06 * X, (-2.3 * (1.0 - abs(X) / MOUTH_HALF) if upper else 0.9 * w ** 0.12), 0.0
    if name == 'にやり':  # grin: wide, corners up, the upper teeth just show
        return 0.18 * X, (-0.8 if upper else 0.1) * w - 1.0 * c, 0.0
    if name == '口角上げ':
        return 0.06 * X, -1.0 * c, 0.0
    if name == '口角下げ':
        return -0.03 * X, 0.9 * c, 0.0
    if name == '口横広げ':
        return 0.3 * X, 0.5 * shut, 0.0
    if name == 'ぺろっ':  # opens for the tongue (Teeth.tongue_out)
        return 0.1 * X, (-0.6 if upper else 0.3) * w, 0.0
    if name == '歯無し上':  # only the teeth move
        return 0.0, 0.0, 0.0
    if name == 'あ':
        return 0.14 * X, (-1.05 if upper else 0.1) * w, 0.0
    if name == 'い':     # wide, corners up a little
        return 0.3 * X, (-0.75 if upper else 0.15) * w - 0.5 * (1 - w), 0.0
    if name == 'え':
        return 0.22 * X, (-0.9 if upper else 0.1) * w - 0.25 * (1 - w), 0.0
    if name == 'お':
        return -0.34 * X, (-0.6 if upper else 0.15) * w, 0.9 * pull
    # う: a small, round, pursed mouth
    return -0.45 * X, (-0.35 if upper else 0.15) * w, 1.4 * pull


def jaw_share(X, row, col, upper=None):
    """Share of the jaw's turn a point (front-view X, row; side-view col) takes:
    1 below the mouth line, 0 above it, a soft band between that rises from
    the mouth corners toward the hinge. Across the slit the lips part: the
    lower lip takes all of it, the upper none, the corners half. upper: for
    vertices on the slit (and its rim), which side they are on."""
    X = abs(X)
    rise, band, grow = JAW_LINE
    ex = max(0.0, X - MOUTH_HALF)
    b = float(mouth_row(min(X, MOUTH_HALF))) - rise * ex
    s = float(_smooth(b - band - grow * ex, b + band + grow * ex, row))
    w = max(0.0, 1.0 - (X / MOUTH_HALF) ** 2) ** 0.25    # (a broad, D-shaped opening)
    below = (row > b) if upper is None else not upper
    s = s + w * (1.0 - s) if below else s - w * s
    # nothing behind the hinge, and nothing at the fixed upper head
    return (s * (1.0 - float(_smooth(JAW_HINGE[0] - 10.0, JAW_HINGE[0] + 2.0, col)))
            * float(_smooth(LOWER_TOP, LOWER_TOP + 5.0, row)))


POUCH_SHARE = (MOUTH_ROW + 0.35, MOUTH_ROW + 1.4)   # rows: the cavity hands over from the head
#                                                       (roof, teeth) to the jaw (floor, tongue)


def pouch_share(row):
    """Share of the jaw's turn inside the mouth cavity, by row."""
    return float(_smooth(*POUCH_SHARE, row))


def _jaw_turn(co, share, ang):
    """`co` turned about the jaw hinge by ang * share (radians, opening)."""
    h = Vector((HEAD_DX, yc(JAW_HINGE[0]), zr(JAW_HINGE[1])))
    a = ang * share
    d = co - h
    ca, sa = math.cos(a), math.sin(a)
    return h + Vector((d.x, d.y * ca - d.z * sa, d.y * sa + d.z * ca))


def morph_targets(name, patches, eyes, co, layout, skip=()):
    """{vertex index: world position} of the morph `name`; co: rest positions.
    skip: vertices the brow field leaves alone (the rims rolling into the
    openings, the mouth cavity)."""
    if name in BROW_MORPHS:
        return _brow_targets(name, eyes, co, skip)
    out = {}
    for p in patches:
        if p.kind == 'eye' and name in EYE_MORPHS:
            if not eye_affects(name, p.side):
                continue
            out.update(_eye_targets(name, p, eyes, co))
        elif p.kind == 'mouth' and name in MOUTH_MORPHS:
            out.update(_mouth_targets(name, p, eyes, co, layout))
    return out


# Brows: the painted brow (a soft line just above the lid crease, mostly under
# the bangs) moves with the skin. A brow morph shifts the skin in the front
# view by brow_shift() times brow_weight(): 1 on the brow line, fading over the
# forehead above and to nothing at the lash band below (the eye keeps its
# shape), and out between the brows and past the temples. The shifted points
# go back on the face (face_point + hug), so the skin slides over the form.
BROW_X = (15.0, 37.0)            # inner / outer end of the painted brow [px]
BROW_LAT = ((6.0, 13.0), (37.5, 41.5))   # the field fades in / out across X [px]
BROW_UP = 10.0                   # rows above the brow line the field fades over


def brow_row(X):
    return 103.9 - 0.04 * (X - 20.0) + 0.006 * (X - 26.0) ** 2


def brow_shift(name, X):
    """(dX outward, drow down) [px] of the brow at X for the brow morph `name`."""
    u = min(max((X - BROW_X[0]) / (BROW_X[1] - BROW_X[0]), 0.0), 1.0)
    inner = (1.0 - u) ** 1.3
    if name == '上':
        return 0.0, -2.4
    if name == '下':
        return 0.0, 1.2
    if name == '困る':    # troubled: the inner ends rise, the outer ends drop
        return 0.3 * inner, -3.0 * inner + 0.9 * u
    if name == '怒り':    # angry: the inner ends drop and draw together
        return -0.9 * inner, 2.2 * inner - 1.0 * u
    if name == '真面目':  # serious: a little lower and flatter
        return -0.3 * inner, 1.2 * inner + 0.3
    return 0.0, -1.1 - 0.9 * math.sin(math.pi * u) ** 0.8   # にこり: raised, arched


def brow_weight(X, R):
    lat = float(_smooth(*BROW_LAT[0], X)) * (1.0 - float(_smooth(*BROW_LAT[1], X)))
    if lat <= 0.0:
        return 0.0
    rb = brow_row(min(max(X, BROW_X[0]), BROW_X[1]))
    if R <= rb:
        return lat * float(_smooth(rb - BROW_UP, rb - 0.6, R))
    lid = float(upper_lid(min(max(X, EYE_IN), EYE_OUT))) - 1.0      # above the lash band (C1)
    if lid <= rb + 0.2:
        return 0.0
    return lat * (1.0 - float(_smooth(rb + 0.2, lid, R)))


def _brow_targets(name, eyes, co, skip):
    out = {}
    back_y = yc(285.0)
    for v, p in enumerate(co):
        if v in skip or p.y > back_y:
            continue
        X, R = (p.x - HEAD_DX) * PPM, row_of(p.z)
        if R > LOWER_TOP - 2.0:
            continue
        w = brow_weight(abs(X), R)
        if w < 1e-4:
            continue
        dX, dR = brow_shift(name, abs(X))
        sgn = 1.0 if X >= 0 else -1.0
        # the surface's own displacement, added to the vertex (exact at the field's edge)
        out[v] = p + (hug(face_point(sgn * (abs(X) + w * dX), R + w * dR), eyes) - hug(face_point(X, R), eyes))
    return out


def _moved(p, motion, co, eyes):
    """Target positions of the patch loops for a per-opening-vertex motion."""
    sgn = p.sign()
    out, fwd = {}, {}
    mot = [motion(X, r, up) for (X, r), up in zip(p.px[0], p.upper)]
    for j, (lp, px, f) in enumerate(zip(p.loops, p.px, p.fade)):
        if f <= 0.0:
            continue
        for m, (v, (X, r)) in enumerate(zip(lp, px)):
            dX, dr, dy = mot[m]
            if not (dX or dr or dy):
                continue
            X2, r2 = X + dX * f, r + dr * f
            pt = hug(face_point(X2 * sgn if p.side != 0 else X2, r2), eyes)
            out[v] = pt
            fwd[v] = dy * f / PPM
    return out, fwd


def _eye_targets(name, p, eyes, co):
    eye = eyes[p.side]
    c, r = eye
    out, fwd = _moved(p, lambda X, row, up: eye_motion(name, X, row, up), co, eyes)
    gap = EYE_GAP / PPM
    for v, pt in out.items():
        ys = sphere_y(c, r, pt.x, pt.z)
        if ys is not None:
            pt.y = min(pt.y, ys - gap)
        pt.y -= fwd[v]
    _clear_sphere(out, co, c, r, p)
    for w, s, v in zip(p.wall, p.pouch, p.loops[0]):
        if v in out:
            out[w] = eye_rim_point(out[v], c, r)
            out[s] = eye_rim_point(out[v], c, r, EYE_SLEEVE)
    return out


def _clear_sphere(out, co, c, r, p):
    """Push the moving lid vertices forward (radially) until their straight
    morph paths, and the chords to their neighbours along the loops, stay
    LID_PATH in front of the eyeball."""
    need = r + LID_PATH / PPM
    nbrs = []
    for lp in p.loops:
        n = len(lp)
        nbrs += [(lp[m], lp[(m + 1) % n]) for m in range(n)]
    for a, b in zip(p.loops, p.loops[1:]):
        nbrs += list(zip(a, b))
    nbrs = [(a, b) for a, b in nbrs if a in out or b in out]
    for _ in range(6):
        pushed = False
        for v in list(out):
            p0, p1 = co[v], out[v]
            nv = min(need, (p0 - c).length)
            for t in np.linspace(0.1, 1.0, 10):
                q = p0.lerp(p1, t)
                d = (q - c).length
                if d < nv - 1e-7:
                    out[v] = c + (p1 - c).normalized() * ((p1 - c).length + min((nv - d) / t, 3.0 / PPM))
                    p1 = out[v]
                    pushed = True
        for a, b in nbrs:
            pa0, pb0 = co[a], co[b]
            pa1, pb1 = out.get(a, pa0), out.get(b, pb0)
            nv = min(need, ((pa0 + pb0) / 2 - c).length)
            for t in np.linspace(0.1, 1.0, 10):
                q = (pa0.lerp(pa1, t) + pb0.lerp(pb1, t)) / 2
                d = (q - c).length
                if d < nv - 1e-7:
                    for v, p1 in ((a, pa1), (b, pb1)):
                        if v in out:
                            out[v] = c + (p1 - c).normalized() * ((p1 - c).length + min((nv - d) / t, 3.0 / PPM))
                    pushed = True
                    break
        if not pushed:
            break


def _mouth_targets(name, p, eyes, co, layout):
    out, fwd = _moved(p, lambda X, row, up: mouth_motion(name, X, row, up), co, eyes)
    for v, pt in out.items():
        pt.y -= fwd[v]
    for w, v in zip(p.wall, p.loops[0]):
        if v in out:
            out[w] = pouch_back(out[v])
    ang = math.radians(JAW_OPEN.get(name, 0.0))
    if ang <= 0.0:
        return out
    upper = dict(zip(p.loops[0], p.upper))
    upper.update(zip(p.wall, p.upper))
    i_top, i_neck = len(RING_ROWS) - 1, len(RING_ROWS) - 1 + layout['iT']
    share = {}
    for v, i in layout['vloop'].items():          # the grid: fades out down the neck
        if i > i_top:
            share[v] = 1.0 - float(_smooth(i_neck - 1.0, i_neck + 4.0, i))
    for lp in p.loops:                            # the patch, the slit and its rim
        for v in lp:
            share[v] = 1.0
    for v in p.wall:
        share[v] = 1.0
    for v in p.pouch:                             # the cavity: its floor goes with the jaw
        share[v] = None
    for v, f in share.items():
        X, col, row = _px(co[v])
        if f is None:
            s = pouch_share(row)
        else:
            s = jaw_share(X, row, col, upper.get(v)) * f
        if s > 1e-6:
            out[v] = _jaw_turn(out.get(v, co[v]), s, ang)
    return out


# ---------------------------------------------------------------- shading
def set_face_uv(me):
    uv = me.uv_layers.new(name='UVMap')
    back_y = yc(293.0)
    for poly in me.polygons:
        behind = poly.center.y > back_y
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            uv.data[li].uv = SKIN_UV if behind else front_uv(co)


def set_eye_region(me, pixels, skip=()):
    """toon_grad = 1 on vertices whose front-projected texel is an (unshaded)
    decal, 0 elsewhere (back of the head and `skip` included)."""
    attr = me.attributes.get(common.GRAD_ATTR) or me.attributes.new(common.GRAD_ATTR, 'FLOAT', 'POINT')
    back_y = yc(293.0)
    for v in me.vertices:
        val = 0.0
        if v.co.y <= back_y and v.index not in skip:
            u, w = front_uv(v.co)
            i = int(round((1.0 - w) * TEX_RES - 0.5))
            j = int(round(u * TEX_RES - 0.5))
            if 0 <= i < TEX_RES and 0 <= j < TEX_RES:
                val = 1.0 - float(pixels[i, j, 3])
        attr.data[v.index].value = val


SHADE_KEEP = (0.05, 0.18)        # share of the real normal: at the features .. on the broad face


def shade_keep(co):
    """Share of the real normal in the face's shading normal: low around the
    eyes and nose (their relief must not break the two-tone shading into
    specks), higher on the cheeks and jaw so the form still turns."""
    X = abs(co.x - HEAD_DX) * PPM
    R = row_of(co.z)
    eye = math.exp(-((X - 27.0) / 16.0) ** 2 - ((R - 116.0) / 10.0) ** 2)
    nose = math.exp(-(X / 7.0) ** 2 - ((R - 126.0) / 9.0) ** 2)
    f = max(eye, nose)
    return SHADE_KEEP[1] + (SHADE_KEEP[0] - SHADE_KEEP[1]) * f


def set_shading_normals(me, smooth, own=(), rim_of=None, tilt=None):
    """Custom normals: mostly the smooth face form (no nose / lid / lip detail,
    so the two-tone shading stays clean), blended with some of the real normal
    so the lids and cheeks still turn the light a little. `own`: vertices that
    keep their real normal (the mouth pouch). `rim_of`: {vertex: opening
    vertex} for the rims rolling into the openings, which take their opening
    vertex's normal, so the lid edge never turns dark in a sliver. `tilt`:
    {vertex: vector} added to the shading normal (see shade_tilts)."""
    normals = []
    for v, n in zip(me.vertices, smooth):
        k = 1.0 if v.index in own else shade_keep(v.co)
        normals.append((n * (1 - k) + v.normal * k).normalized())
    for v, src in (rim_of or {}).items():
        normals[v] = normals[src]
    for v, t in (tilt or {}).items():
        normals[v] = (normals[v] + t).normalized()
    me.normals_split_custom_set_from_vertices(normals)
    return normals


# ---------------------------------------------------------------- eyeballs
EYE_SEG, EYE_RINGS = 32, 8
EYE_MARGIN = math.radians(30.0)  # eyeball cap beyond the opening: room to turn
EYE_COVER = 0.3                  # px of face the eyeball cap must stay behind beyond the opening


def eye_axis(c, r, side):
    """Unit vector from the eyeball centre to the iris centre on the sphere
    (the rest gaze), and two unit vectors across it."""
    ax = (sphere_point(c, r, HEAD_DX + side * IRIS[0] / PPM, zr(IRIS[1])) - c).normalized()
    u = ax.cross(Vector((0.0, 0.0, 1.0))).normalized()
    return ax, u, u.cross(ax).normalized()


def _cap_point(c, r, basis, t, phi):
    ax, u, v = basis
    return c + (ax * math.cos(t) + (u * math.cos(phi) + v * math.sin(phi)) * math.sin(t)) * r


def _cap_limit(c, r, basis, phi, t0, t1, tree):
    """Largest polar angle in [t0, t1] (direction phi) up to which the sphere
    stays EYE_COVER behind the face (ray cast from the front into `tree`)."""
    t = t0
    for tt in np.arange(t0, t1 + 1e-9, math.radians(1.0)):
        q = _cap_point(c, r, basis, tt, phi)
        hit = tree.ray_cast(Vector((q.x, q.y - 0.2, q.z)), Vector((0.0, 1.0, 0.0)), 0.2)[0]
        if hit is None or hit.y > q.y - EYE_COVER / PPM:
            break
        t = tt
    return t


def eyeball_mesh(c, r, side, rim, tree):
    """A cap of the eyeball sphere around the rest gaze (pole on the iris),
    behind the opening (rim: world points of the opening), reaching up to
    EYE_MARGIN past it in every direction while it stays hidden behind the
    face (tree: BVH of head_face)."""
    basis = eye_axis(c, r, side)
    ax, u, v = basis
    th, ph = [], []
    for q in rim:
        d = (q - c).normalized()
        th.append(math.acos(max(-1.0, min(1.0, d.dot(ax)))))
        ph.append(math.atan2(d.dot(v), d.dot(u)))
    order = np.argsort(ph)
    ph_s, th_s = np.asarray(ph)[order], np.asarray(th)[order]
    ph_s = np.concatenate([ph_s - 2 * math.pi, ph_s, ph_s + 2 * math.pi])
    th_s = np.concatenate([th_s, th_s, th_s])
    bm = bmesh.new()
    tip = bm.verts.new(_cap_point(c, r, basis, 0.0, 0.0))
    phis = [2 * math.pi * s / EYE_SEG - math.pi for s in range(EYE_SEG)]
    tmaxs = []
    for phi in phis:
        tc = float(np.interp(phi, ph_s, th_s))
        tmaxs.append(_cap_limit(c, r, basis, phi, tc + math.radians(1.5),
                                min(tc + EYE_MARGIN, math.radians(88.0)), tree))
    rings = [[bm.verts.new(_cap_point(c, r, basis, tmax * j / EYE_RINGS, phi)) for phi, tmax in zip(phis, tmaxs)]
             for j in range(1, EYE_RINGS + 1)]
    for s in range(EYE_SEG):
        s2 = (s + 1) % EYE_SEG
        bm.faces.new((tip, rings[0][s], rings[0][s2]))
        for a, b in zip(rings, rings[1:]):
            bm.faces.new((a[s], b[s], b[s2], a[s2]))
    bm.normal_update()
    if tip.link_faces[0].normal.dot(ax) < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces)
    return bm


IRIS_LIFT = 0.08                 # px the iris disc floats in front of the white
IRIS_RINGS, IRIS_SEG = 8, 28
IRIS_EDGE = 0.985                # disc edge on the painted iris outline (inside its soft rim)
# 瞳小: the painted pupil shrinks to this share about its centre (X, row);
# the iris around it is drawn in over PUPIL_ZONE (half-widths X, rows, as
# share: full shrink inside the first, none beyond the second), the disc's
# rim stays
PUPIL_SMALL = 0.5
PUPIL_CENTRE = (IRIS[0] - 0.4, 114.2)
PUPIL_ZONE = ((2.6, 5.5), (0.5, 1.15))


def pupil_squeeze(X, row, k):
    """(X, row) of an iris point with the pupil shrunk to share k."""
    px, pr = PUPIL_CENTRE
    (ax, ar), (q0, q1) = PUPIL_ZONE
    q = math.hypot((X - px) / ax, (row - pr) / ar)
    s = k + (1.0 - k) * float(_smooth(q0, q1, q))
    return px + (X - px) * s, pr + (row - pr) * s


def iris_mesh(c, r, side, pupil=1.0):
    """The iris disc: a piece of the sphere IRIS_LIFT in front of the white,
    whose front projection is exactly the painted iris ellipse (pupil < 1:
    the same disc with the pupil drawn in, 瞳小)."""
    ix, iy, irx, iry = IRIS
    rr = r + IRIS_LIFT / PPM
    bm = bmesh.new()

    def at(X, row):
        if pupil != 1.0:
            X, row = pupil_squeeze(X, row, pupil)
        x, z = HEAD_DX + side * X / PPM, zr(row)
        return sphere_point(c, rr, x, z)
    centre = bm.verts.new(at(ix, iy))
    rings = []
    for j in range(1, IRIS_RINGS + 1):
        rho = IRIS_EDGE * j / IRIS_RINGS
        rings.append([bm.verts.new(at(ix + irx * rho * math.cos(a), iy + iry * rho * math.sin(a)))
                      for a in (2 * math.pi * s / IRIS_SEG for s in range(IRIS_SEG))])
    for s in range(IRIS_SEG):
        s2 = (s + 1) % IRIS_SEG
        bm.faces.new((centre, rings[0][s], rings[0][s2]))
        for a, b in zip(rings, rings[1:]):
            bm.faces.new((a[s], b[s], b[s2], a[s2]))
    bm.normal_update()
    if centre.link_faces[0].normal.dot(centre.co - c) < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces)
    return bm


def eye_object(col, name, mat, c, bm):
    """Mesh object of an eye part (front-projected UVs, sphere normals, all
    'eye' region, no outline)."""
    uv_layer = bm.loops.layers.uv.new('UVMap')
    for f in bm.faces:
        for loop in f.loops:
            loop[uv_layer].uv = front_uv(loop.vert.co)
    obj = common.new_object(col, name, bm, [mat])
    me = obj.data
    me.shade_smooth()
    me.normals_split_custom_set_from_vertices([(v.co - c).normalized() for v in me.vertices])
    attr = me.attributes.new(common.GRAD_ATTR, 'FLOAT', 'POINT')
    for a in attr.data:
        a.value = 1.0
    obj['no_outline'] = True
    return obj


# ---------------------------------------------------------------- eye layers
# Besides the white (static) and the iris (on the eye bone), each eye has:
# * EyeShade: the upper lid's shadow on the white, a band just in front of the
#   white and behind the iris (so the turning iris covers it). Static on the
#   head, but its shape keys ride the upper lid's edge, so the shadow stays
#   under the lid in every eye morph.
# * Highlights: two discs just in front of the iris, on the eye bone with it
#   (a static highlight would leave the iris at the gaze limits: the 36 px
#   eyeball moves the iris ~6 px there, its radius is 8.4 px). They do not
#   shrink with 瞳小 and go out in ハイライト消.
# * Lashes: real geometry over the painted upper lash (see Lashes).
SHADE_LIFT = 0.04                # px the lid-shadow layer floats in front of the white (behind the iris)
HILITE_LIFT = 0.095              # px the highlights float in front of the white (in front of the iris)
HILITES = ((IRIS[0] - 1.0, 110.8, 1.5), (IRIS[0] + 3.2, 121.2, 0.7))   # X, row, radius [px]
HILITE_SEG = 14


def _sphere_at(c, rr, side, X, row):
    return sphere_point(c, rr, HEAD_DX + side * X / PPM, zr(row))


def upper_shift(name, X):
    """Row shift of the upper lid's edge at X in the eye morph `name`."""
    Xc = min(max(X, EYE_IN + 1e-3), EYE_OC)
    return eye_motion(name, Xc, float(lash_bottom(Xc)), True)[1]


class EyeShade:
    NS, NT = 28, 6

    def __init__(self, c, r, side):
        self.c, self.rr, self.side = c, r + SHADE_LIFT / PPM, side
        self.px = []
        for i in range(self.NS + 1):
            X = EYE_IN - 1.0 + (EYE_OC - EYE_IN + 2.0) * i / self.NS
            top = float(lash_bottom(min(max(X, EYE_IN), EYE_OC)))
            for j in range(self.NT + 1):
                self.px.append((X, top - 1.2 + (SHADE_FADE + 2.0) * j / self.NT))

    def positions(self, name=None):
        moves = name is not None and eye_affects(name, self.side)
        return [_sphere_at(self.c, self.rr, self.side, X, row + (upper_shift(name, X) if moves else 0.0))
                for X, row in self.px]

    def mesh(self):
        bm = bmesh.new()
        vs = [bm.verts.new(p) for p in self.positions()]
        n = self.NT + 1
        for i in range(self.NS):
            for j in range(self.NT):
                a = i * n + j
                bm.faces.new((vs[a], vs[a + n], vs[a + n + 1], vs[a + 1]))
        return bm


class Highlights:
    def __init__(self, c, r, side):
        self.c, self.rr, self.side = c, r + HILITE_LIFT / PPM, side

    def positions(self, off=False):
        out = []
        for X, row, rad in HILITES:
            centre = _sphere_at(self.c, self.rr, self.side, X, row)
            out.append(centre)
            for s in range(HILITE_SEG):
                a = 2.0 * math.pi * s / HILITE_SEG
                out.append(centre.copy() if off else
                           _sphere_at(self.c, self.rr, self.side, X + rad * math.cos(a), row + rad * math.sin(a)))
        return out

    def mesh(self):
        bm = bmesh.new()
        vs = [bm.verts.new(p) for p in self.positions()]
        n = HILITE_SEG + 1
        for k in range(len(HILITES)):
            ctr = vs[k * n]
            ring = vs[k * n + 1:(k + 1) * n]
            for s in range(HILITE_SEG):
                bm.faces.new((ctr, ring[s], ring[(s + 1) % HILITE_SEG]))
        return bm


# ---------------------------------------------------------------- skin-attached pieces
class PatchSurface:
    """The eye patch's loops (opening -> grid boundary) as triangles in the
    front view (local X, row): a piecewise-linear map from front-view px to the
    patch's skin, at rest or in a morph."""

    def __init__(self, p):
        verts, px, index = [], [], {}
        for j, (lp, pxl) in enumerate(zip(p.loops, p.px)):
            for m, (v, q) in enumerate(zip(lp, pxl)):
                index[j, m] = len(verts)
                verts.append(v)
                px.append(q)
        n = len(p.loops[0])
        tris = []
        for j in range(len(p.loops) - 1):
            for m in range(n):
                m2 = (m + 1) % n
                a, b, c, d = index[j, m], index[j, m2], index[j + 1, m2], index[j + 1, m]
                tris += [(a, b, c), (a, c, d)]
        self.side = p.side
        self.verts = np.array(verts)
        self.px = np.array(px, float)
        self.tris = np.array(tris)

    def pos(self, co, targets=None):
        """(V, 3) positions of the patch vertices: rest `co`, or a morph's targets."""
        targets = targets or {}
        return np.array([tuple(targets.get(v, co[v])) for v in self.verts])

    def px_of(self, pos):
        """Front-view (local X, row) of patch vertex positions."""
        return np.stack([(pos[:, 0] - HEAD_DX) * PPM * self.side, row_of(pos[:, 2])], 1)

    def locate(self, Q, px=None, pos=None):
        """(triangle, barycentric) of the front-view points Q (N, 2). With `pos`
        (the patch positions behind `px`), where the patch overlaps itself in
        the front view (closed lids), the triangle nearest the viewer wins."""
        P = self.px if px is None else px
        Q = np.asarray(Q, float).reshape(-1, 2)
        A = P[self.tris[:, 0]]
        e1, e2 = P[self.tris[:, 1]] - A, P[self.tris[:, 2]] - A
        det = e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0]
        ok = np.abs(det) > 1e-9
        det = np.where(ok, det, 1.0)
        d = Q[:, None, :] - A[None]
        u = (d[..., 0] * e2[None, :, 1] - d[..., 1] * e2[None, :, 0]) / det
        v = (e1[None, :, 0] * d[..., 1] - e1[None, :, 1] * d[..., 0]) / det
        w = 1.0 - u - v
        score = np.where(ok[None], np.minimum(np.minimum(u, v), w), -np.inf)
        if pos is not None:
            ys = (pos[self.tris][None, :, :, 1] * np.stack([w, u, v], 2)).sum(2)
            score = np.where(score >= -1e-6, 1e3 - ys * PPM, score)
        t = np.argmax(score, axis=1)
        i = np.arange(len(Q))
        return t, np.stack([w[i, t], u[i, t], v[i, t]], 1)

    def points(self, t, bary, pos):
        return (pos[self.tris[t]] * bary[..., None]).sum(1)


def _frames(T):
    """Orthonormal frames (columns: edge, in-plane normal, normal toward -y) of
    triangles T (N, 3, 3)."""
    e1 = T[:, 1] - T[:, 0]
    n = np.cross(e1, T[:, 2] - T[:, 0])
    n *= np.where(n[:, 1:2] > 0, -1.0, 1.0)
    e1 /= np.linalg.norm(e1, axis=1, keepdims=True)
    n /= np.linalg.norm(n, axis=1, keepdims=True)
    return np.stack([e1, np.cross(n, e1), n], 2)


class SkinDecal:
    """Points riding an eye patch's skin: a root on the patch (front-view px)
    plus an offset that turns with the triangle under it. offsets: (N, 2) of
    (forward along -y, along the skin normal) [px] at rest."""

    def __init__(self, surf, co, Q, offsets):
        self.surf = surf
        rest = surf.pos(co)
        self.t, self.bary = surf.locate(Q)
        self.Fr = _frames(rest[surf.tris[self.t]])
        root = surf.points(self.t, self.bary, rest)
        off = np.asarray(offsets, float) / PPM
        self.off = off[:, 0:1] * np.array([0.0, -1.0, 0.0]) + off[:, 1:2] * self.Fr[:, :, 2]
        self.rest = root + self.off

    def positions(self, co, targets=None):
        pos = self.surf.pos(co, targets)
        root = self.surf.points(self.t, self.bary, pos)
        R = _frames(pos[self.surf.tris[self.t]]) @ np.transpose(self.Fr, (0, 2, 1))
        return root + np.einsum('nij,nj->ni', R, self.off)


# Lashes: the upper lash line as a thin solid over the painted lash mass (whose
# front view it covers exactly: it stands forward along -y only), so it reads
# in profile and 3/4. Its top edge lies on the lid; toward its lower edge (the
# opening's top) it stands LASH_E forward of the lid, more at the outer end.
# The outer flick is a ribbon lifted off the skin along its normal. Both ride
# the lid band (SkinDecal) through every morph.
LASH_E = (0.4, 1.2)              # px the lash's lower edge stands forward: inner .. outer end
LASH_LIFT = 0.05                 # px the lash floats off the skin
LASH_NS, LASH_NT = 48, 4
FLICK = (0.8, 2.2, 8)            # the flick runs from EYE_OUT - a to EYE_OUT + b (stations)
FLICK_LIFT = (0.1, 0.9)  
FLICK_CLOSED = 0.45               # the flick's length share while the lids are closed        # px off the skin along its normal: root .. tip


def lash_decal(p, co):
    """SkinDecal and faces of one eye's lash solid and flick."""
    Q, off, faces = [], [], []
    xa, xb = EYE_IN - 0.3, EYE_OUT + 1.2
    n = LASH_NT + 1
    for i in range(LASH_NS):
        s = i / (LASH_NS - 1)
        X = xa + (xb - xa) * s
        top, bot = float(upper_lid(X)) - 0.7, float(upper_lid(X) + lash_thick(X))
        e_max = ((LASH_E[0] + (LASH_E[1] - LASH_E[0]) * float(_smooth(0.1, 0.95, s)))
                 * (1.0 - 0.85 * float(_smooth(0.82, 1.0, s))) * (0.15 + 0.85 * float(_smooth(0.0, 0.12, s))))
        for j in range(n):
            t = j / LASH_NT
            Q.append((X, top + (bot - top) * t))
            off.append((LASH_LIFT + e_max * t ** 1.6, 0.0))
    base = len(Q)
    for i in range(LASH_NS):          # the underside's root along the opening's top edge
        Q.append(Q[i * n + LASH_NT])
        off.append((LASH_LIFT * 0.5, 0.0))
    for i in range(LASH_NS - 1):
        for j in range(LASH_NT):
            a = i * n + j
            faces.append((a, a + n, a + n + 1, a + 1))
        faces.append((i * n + LASH_NT, base + i, base + i + 1, (i + 1) * n + LASH_NT))
    faces.append(tuple(range(0, n)) + (base,))
    last = (LASH_NS - 1) * n
    faces.append((base + LASH_NS - 1,) + tuple(range(last + LASH_NT, last - 1, -1)))
    a0, a1, K = FLICK
    q = np.array([0.8, 1.0]) / math.hypot(1.0, 0.8)
    fl = len(Q)
    for k in range(K):
        s = k / (K - 1)
        X = EYE_OUT - a0 + (a0 + a1) * s
        c = np.array([X, 112.0 - 0.8 * (X - EYE_OUT)])
        hw = 0.7 * (1.0 - s) + 0.12 * s
        lift = FLICK_LIFT[0] + (FLICK_LIFT[1] - FLICK_LIFT[0]) * s ** 1.3
        for sg in (-1.0, 1.0):
            Q.append(tuple(c + sg * hw * q))
            off.append((0.0, lift))
        if k:
            b = fl + 2 * k
            faces.append((b - 2, b, b + 1, b - 1))
    return SkinDecal(PatchSurface(p), co, Q, off), faces


# はぅ: the lower stroke of '>' / '<' (the closed lids' lash band is the upper
# one): hidden inside the head at rest; in はぅ it lies on the closed lids.
HAU_STROKE = (2.4, 1.5, 24)      # px width at the apex, at the outer end; stations
HAU_BOW = 0.8                    # px the stroke bows down at its middle (tapered at its end)
FX_LIFT = 0.15                   # px the overlays float off the skin when in place
FX_HIDE = 10.0                   # px the overlays wait inside the head at rest ...
FX_CENTRE = (292.0, 118.0)       # ... toward this point on the midline (side-view col, row)


def fx_hidden(p):
    """Where an overlay point waits at rest: FX_HIDE px into the head."""
    c = Vector((HEAD_DX, yc(FX_CENTRE[0]), zr(FX_CENTRE[1])))
    return p + (c - p).normalized() * (FX_HIDE / PPM)


def hau_stroke(p, co, targets):
    """(rest, in place) world points and faces of one eye's はぅ stroke."""
    surf = PatchSurface(p)
    w0, w1, K = HAU_STROKE
    x0, r0 = EYE_IN - 1.2, HAU_LINE[0] + 0.1
    x1, r1 = EYE_OC - 3.0, HAU_LINE[0] + 0.85 * HAU_LINE[1]
    Q, faces = [], []
    for k in range(K):
        s = k / (K - 1)
        X, R = x0 + (x1 - x0) * s, r0 + (r1 - r0) * s + HAU_BOW * math.sin(math.pi * s)
        w = (w0 + (w1 - w0) * s ** 0.8) * (1.0 - 0.7 * float(_smooth(0.75, 1.0, s)))
        Q += [(X, R - 0.15 * w), (X - 0.25 * w, R + 0.85 * w)]
        if k:
            faces.append((2 * k - 2, 2 * k, 2 * k + 1, 2 * k - 1))
    pos = surf.pos(co, targets)
    t, b = surf.locate(Q, surf.px_of(pos), pos)
    placed = surf.points(t, b, pos) + np.array([0.0, -2.0 * FX_LIFT / PPM, 0.0])
    # (at rest those points lie over the open eye: it waits behind where it goes)
    rest = np.array([tuple(fx_hidden(Vector(tuple(q)))) for q in placed])
    return rest, placed, faces


# ---------------------------------------------------------------- mouth interior
# Upper teeth: a curved band under the cavity's roof, its lower edge just
# above the slit (hidden while the mouth is closed), static with the head
# (歯無し上 lifts it into the gum). Tongue: a flattened ellipsoid on the
# cavity's floor, riding the jaw with the floor (pouch_share); ぺろっ pushes
# its front out between the lips.
TEETH_HALF = 3.1                 # px half-width (about 2/3 of the slit)
TEETH_TOP = 144.6                # row of the band's top at the middle (rises 0.09 px / px^2 at the sides)
TEETH_GAP = 0.55                 # px the band's lower edge stays above the mouth line
TEETH_DEPTH = (1.9, 0.17, 0.55)  # px behind the face surface: middle, + per px^2 to the sides; thickness
TEETH_HIDE = (1.6, 0.6)          # 歯無し上: px up, px back
TONGUE = (148.5, 3.8, 3.3, 0.85, 1.8)   # centre row, depth [px]; half-width, half-height, half-depth
TONGUE_OUT = 8.5                 # ぺろっ: px the tip comes forward ...
TONGUE_OUT_JAW = 0.5             # ... taking this share of the jaw's turn (it rises over the lower lip)


def teeth_mesh(hidden=False):
    bm = bmesh.new()
    ns = 20
    rows = []
    for i in range(ns + 1):
        X = -TEETH_HALF + 2.0 * TEETH_HALF * i / ns
        top = TEETH_TOP + 0.09 * X * X
        bot = float(mouth_row(X)) - TEETH_GAP
        dep = TEETH_DEPTH[0] + TEETH_DEPTH[1] * X * X
        ring = []
        for R, d in ((top, dep), (0.5 * (top + bot), dep), (bot, dep), (bot, dep + TEETH_DEPTH[2]),
                     (top, dep + TEETH_DEPTH[2])):
            pt = pouch_point(X, R, d)
            if hidden:
                pt += Vector((0.0, TEETH_HIDE[1] / PPM, TEETH_HIDE[0] / PPM))
            ring.append(bm.verts.new(pt))
        rows.append(ring)
    m = len(rows[0])
    for a, b in zip(rows, rows[1:]):
        for k in range(m):
            k2 = (k + 1) % m
            bm.faces.new((a[k], b[k], b[k2], a[k2]))
    bm.faces.new(rows[0])
    bm.faces.new(list(reversed(rows[-1])))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def _face_front(bm):
    """Turn every face of an open sheet toward the viewer (-y): the toon shading
    reads a back-facing face's normal flipped."""
    bm.normal_update()
    flip = [f for f in bm.faces if f.normal.y > 0]
    if flip:
        bmesh.ops.reverse_faces(bm, faces=flip)
    return bm


def tongue_local(nu=16, nv=9):
    """Unit-sphere (lon, lat) samples of the tongue (x across, z down, d back)."""
    pts = [(0.0, 0.0, -1.0)]
    for j in range(1, nv):
        th = math.pi * j / nv
        for i in range(nu):
            ph = 2.0 * math.pi * i / nu
            pts.append((math.sin(th) * math.cos(ph), math.sin(th) * math.sin(ph), -math.cos(th)))
    pts.append((0.0, 0.0, 1.0))
    return pts


def tongue_points(out=0.0):
    """World points of the tongue; out: share of ぺろっ's push."""
    row, depth, hx, hz, hd = TONGUE
    origin = pouch_point(0.0, row, depth)
    res = []
    for x, z, d in tongue_local():
        X, Z, D = hx * x, hz * z * (0.75 if z < 0 else 1.0), hd * d    # flatter on top
        if out:
            f = min(max((hd - D) / (2.0 * hd), 0.0), 1.0)            # 1 at the tip, 0 at the root
            D -= out * TONGUE_OUT * f ** 1.5
            X *= 1.0 - 0.15 * out * f
            Z += out * (-2.4 * min(1.0, 1.6 * f) + 5.0 * max(0.0, (f - 0.7) / 0.3) ** 2)   # lifted; the tip hangs over the lower lip
        res.append(origin + Vector((X / PPM, D / PPM, -Z / PPM)))
    return res


def tongue_mesh():
    bm = bmesh.new()
    vs = [bm.verts.new(p) for p in tongue_points()]
    nu, nv = 16, 9
    top, bot = vs[0], vs[-1]
    ring = lambda j: vs[1 + (j - 1) * nu:1 + j * nu]   # noqa: E731
    for i in range(nu):
        i2 = (i + 1) % nu
        bm.faces.new((top, ring(1)[i2], ring(1)[i]))
        bm.faces.new((bot, ring(nv - 1)[i], ring(nv - 1)[i2]))
        for j in range(1, nv - 1):
            a, b = ring(j), ring(j + 1)
            bm.faces.new((a[i], a[i2], b[i2], b[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def tongue_targets(name):
    """World points of the tongue in the mouth morph `name` (None: it stays)."""
    ang = math.radians(JAW_OPEN.get(name, 0.0))
    if ang <= 0.0 and name != 'ぺろっ':
        return None
    pts = tongue_points(1.0 if name == 'ぺろっ' else 0.0)
    return [_jaw_turn(p, TONGUE_OUT_JAW if name == 'ぺろっ' else pouch_share(row_of(p.z)), ang) for p in pts]


# ---------------------------------------------------------------- overlays
# 照れ (a deeper blush with hatching, on both cheeks), 涙 (a tear down each
# cheek), 汗 (a sweat drop on the right cheek): hidden FX_HIDE behind the skin
# at rest, their key moves them FX_LIFT in front of it.
TEAR = ((27.0, 0.9), (27.8, 133.0), (0.7, 1.05, 1.35))   # top X, rows below the lower lid; bottom X, row;
#                                                          half-width top, bottom, bead
SWEAT = (-27.5, 126.0, 7.0, 2.3, 1.3, 14.0)   # X, top row, length, half-width, height [px], tilt [deg]


def skin_at(X, R, eyes, lift=FX_LIFT):
    return hug(face_point(X, R), eyes) + Vector((0.0, -lift / PPM, 0.0))


SKIN_MOTION = (8, 2.0)           # nearest face vertices, falloff [px] for skin_motion


def skin_motion(kd, co, targets, pts, surfs=()):
    """Displacement of the face skin under each point in `pts` in a morph
    (`targets`): piecewise linear over an eye patch (surfs: PatchSurface)
    where the point lies on one in the front view, else an inverse-distance
    blend of the nearest face vertices' motion. None when nothing moves."""
    out, moved = [], False
    for p in pts:
        X, R = (p.x - HEAD_DX) * PPM, row_of(p.z)
        s = next((s for s in surfs if s.side * X > 0), None)
        if s is not None:
            t, b = s.locate([(abs(X), R)])
            if b.min() >= -1e-6:
                tri = s.verts[s.tris[t[0]]]
                d = sum(((targets[i] - co[i]) * float(w) for i, w in zip(tri, b[0]) if i in targets),
                        Vector((0.0, 0.0, 0.0)))
                moved |= d.length > 1e-7
                out.append(d)
                continue
        acc, wsum = Vector((0.0, 0.0, 0.0)), 0.0
        for q, i, dist in kd.find_n(p, SKIN_MOTION[0]):
            w = 1.0 / (dist * PPM + SKIN_MOTION[1]) ** 2
            if i in targets:
                acc += (targets[i] - co[i]) * w
            wsum += w
        d = acc / wsum
        moved |= d.length > 1e-7
        out.append(d)
    return out if moved else None


def flush_mesh(eyes):
    """The 照れ overlay: a grid over each cheek (FLUSH_X x flush_top..FLUSH_BOTTOM)."""
    bm = bmesh.new()
    ns, nt = 16, 9
    for side in (1, -1):
        grid = []
        for i in range(ns + 1):
            X = FLUSH_X[0] + (FLUSH_X[1] - FLUSH_X[0]) * i / ns
            top = float(flush_top(X))
            grid.append([bm.verts.new(skin_at(side * X, top + (FLUSH_BOTTOM - top) * j / nt, eyes))
                         for j in range(nt + 1)])
        for a, b in zip(grid, grid[1:]):
            for j in range(nt):
                bm.faces.new((a[j], b[j], b[j + 1], a[j + 1]))
    return _face_front(bm)


def tear_mesh(eyes):
    """Two tears; per face UV keys in `bm.faces.layers.int['swatch']`."""
    bm = bmesh.new()
    sw = bm.faces.layers.int.new('swatch')
    (xt, dr), (xb, rb), (w0, w1, wb) = TEAR
    rt = float(lower_lid(xt)) + dr
    K = 14
    for side in (1, -1):
        rows = []
        for k in range(K + 1):
            s = k / K
            X, R = xt + (xb - xt) * s, rt + (rb - rt) * s
            w = (w0 + (w1 - w0) * s) * (1.0 - float(_smooth(0.9, 1.0, s)))
            if s < 0.12:    # the top tapers from the lid
                w *= 0.4 + 0.6 * s / 0.12
            w = max(w, wb * math.sqrt(max(0.0, 1.0 - ((s - 0.86) / 0.14) ** 2)), 0.02)   # the bead
            rows.append([bm.verts.new(skin_at(side * (X + o * w), R, eyes, FX_LIFT + 0.1))
                         for o in (-1.0, -0.7, 0.7, 1.0)])
        for a, b in zip(rows, rows[1:]):
            for m, key in ((0, 'tear_line'), (1, 'tear'), (2, 'tear_line')):
                f = (a[m], a[m + 1], b[m + 1], b[m])
                f = bm.faces.new(f if side > 0 else f[::-1])
                f[sw] = list(ATLAS).index(key)
        # a highlight streak on the tear
        hl = []
        for k in range(4, 11):
            s = k / K
            X, R = xt + (xb - xt) * s - 0.25, rt + (rb - rt) * s
            hl.append([bm.verts.new(skin_at(side * (X + o), R, eyes, FX_LIFT + 0.16)) for o in (-0.18, 0.18)])
        for a, b in zip(hl, hl[1:]):
            f = (a[0], a[1], b[1], b[0])
            f = bm.faces.new(f if side > 0 else f[::-1])
            f[sw] = list(ATLAS).index('white')
    return bm


def sweat_mesh(eyes):
    """A sweat drop lying on the right cheek: pointed top, round bottom, domed."""
    bm = bmesh.new()
    sw = bm.faces.layers.int.new('swatch')
    hh = SWEAT[4]
    nv, na = 12, 10

    def at(v, a, h):
        """v: 0 tip .. 1 bottom along the drop, a: -1..1 across, h: height share."""
        return skin_at(*_sweat_px(v, a), eyes, FX_LIFT + 0.15 + hh * h)
    tip = bm.verts.new(at(0.0, 0.0, 0.0))
    rings = []
    for k in range(1, nv + 1):
        v = k / (nv + 0.35)
        ring = []
        for i in range(na + 1):
            a = -1.0 + 2.0 * i / na
            ring.append(bm.verts.new(at(v, a, math.sqrt(max(0.0, 1.0 - a * a)) * math.sin(math.pi * v) ** 0.5)))
        rings.append(ring)
    for i in range(na):
        f = bm.faces.new((tip, rings[0][i + 1], rings[0][i]))
        f[sw] = list(ATLAS).index('sweat')
    for a, b in zip(rings, rings[1:]):
        for i in range(na):
            f = bm.faces.new((a[i], a[i + 1], b[i + 1], b[i]))
            f[sw] = list(ATLAS).index('sweat')
    end = rings[-1]
    f = bm.faces.new(end[::-1])
    f[sw] = list(ATLAS).index('sweat')
    # its highlight: a small streak on the upper inner side
    hl = []
    for k in range(4, 8):
        v = k / (nv + 0.35)
        hl.append([bm.verts.new(skin_at(*_sweat_px(v, a), eyes, FX_LIFT + 0.2 + hh * 0.95))
                   for a in (0.15, 0.4)])
    for a, b in zip(hl, hl[1:]):
        f = bm.faces.new((a[0], a[1], b[1], b[0]))
        f[sw] = list(ATLAS).index('white')
    return bm


def _sweat_px(v, a):
    X0, R0, L, hw, hh, tilt = SWEAT
    ca, sa = math.cos(math.radians(tilt)), math.sin(math.radians(tilt))
    width = hw * math.sin(math.pi * min(v, 0.999) ** 0.62)
    x, y = a * width, v * L
    return X0 + x * ca - y * sa, R0 + x * sa + y * ca


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


# ---------------------------------------------------------------- neck
NECK_SHADE_ROW = 166.0    # the neck's shading normals turn under the jaw above this row
NECK_SHADE_BAND = 8.0     # ... over this many rows either side (no hard edge)
NECK_TILT = Vector((0.0, 0.6, -0.8)) * 0.15   # added to the shading normal: down and back


def shade_tilts(me, vloop, i_neck):
    """{vertex: vector} added to the neck's shading normals. The sheet draws a
    band of shade under the chin: the neck's normals tilt down and back (away
    from the camera-relative key light), fading in over the loops around the
    throat (i_neck: the last under-jaw loop) and out over NECK_SHADE_BAND rows
    around NECK_SHADE_ROW, so the shade edge sits a few px below the jaw, still
    turns around the neck, and the neck meets the body's neck lit."""
    lo, hi = zr(NECK_SHADE_ROW + NECK_SHADE_BAND), zr(NECK_SHADE_ROW - NECK_SHADE_BAND)
    out = {}
    for v, i in vloop.items():
        w = float(_smooth(i_neck - 3.0, i_neck + 2.0, i)) * float(_smooth(lo, hi, me.vertices[v].co.z))
        if w > 0.0:
            out[v] = NECK_TILT * w
    return out


# ---------------------------------------------------------------- build
def build(col):
    skin = common.toon_material('skin')
    mouth = common.toon_material('mouth')
    teeth_mat = common.toon_material('cuff')
    pixels = face_texture_pixels()
    face = face_material(pixels)
    white_mat = face_material(eye_texture_pixels(), 'toon_face_eyewhite', 'levi_eyewhite_tex')
    iris_mat = face_material(eye_texture_pixels(iris_only=True), 'toon_face_iris', 'levi_iris_tex')
    shade_mat = face_material(eye_texture_pixels(shade=True), 'toon_face_eyeshade', 'levi_eyeshade_tex')
    atlas_mat = face_material(atlas_pixels(), 'toon_face_decal', 'levi_decal_tex')
    flush_mat = face_material(face_texture_pixels(flushed=True), 'toon_face_flush', 'levi_flush_tex')

    bm, patches, eyes, layout = build_head(detail=True)
    co = [v.co.copy() for v in bm.verts]
    smooth_bm, _, _, _ = build_head(detail=False, eye_fit=eyes[1], layout=layout)
    smooth_bm.normal_update()
    smooth = [v.normal.copy() for v in smooth_bm.verts]
    smooth_bm.free()
    rims = {p.side: [co[v] for v in p.loops[0]] for p in patches if p.kind == 'eye'}
    own = set()
    rim_of = {}           # rim / sleeve vertex -> its opening vertex (shares its shading normal)
    for p in patches:
        own |= set(p.wall) | set(p.pouch)
        rim_of.update(zip(p.wall, p.loops[0]))
        if p.kind == 'eye':
            rim_of.update(zip(p.pouch, p.loops[0]))

    head = common.new_object(col, 'head_face', bm, [face, mouth])
    me = head.data
    me.shade_smooth()
    set_face_uv(me)
    set_eye_region(me, pixels, skip=own)
    normals = set_shading_normals(me, smooth, own - set(rim_of), rim_of,
                                  shade_tilts(me, layout['vloop'], len(RING_ROWS) - 1 + layout['iT']))
    head.shape_key_add(name='Basis', from_mix=False)
    targets = {}
    for name in FACE_MORPHS:
        targets[name] = {v: q for v, q in morph_targets(name, patches, eyes, co, layout, own).items()
                         if (q - co[v]).length > 1e-7}
        if not targets[name]:
            continue
        kb = head.shape_key_add(name=name, from_mix=False)
        for v, pt in targets[name].items():
            kb.data[v].co = pt
        kb.value = 0.0   # a new key is not guaranteed to start at 0
    # no outline hull on the rims rolling into the openings and the pouch: seen
    # from above or below it would draw a line across the iris / the mouth
    vg = head.vertex_groups.new(name='outline_width')
    vg.add([v.index for v in me.vertices if v.index not in own], 1.0, 'REPLACE')
    vg.add(sorted(own), 0.0, 'REPLACE')
    # ... and it thins out toward the mouth slit, or an open mouth shows hull
    # wedges at its corners
    mp = next(p for p in patches if p.kind == 'mouth')
    for lp, wgt in zip(mp.loops, MOUTH_OUTLINE):
        vg.add(lp, wgt, 'REPLACE')
    common.add_outline(head, vertex_group='outline_width', min_factor=0.0)

    tree = BVHTree.FromPolygons([v.co for v in me.vertices], [tuple(q.vertices) for q in me.polygons])
    eye_patch = {p.side: p for p in patches if p.kind == 'eye'}
    hau = []
    for side, sfx in ((1, 'L'), (-1, 'R')):
        c, r = eyes[side]
        eye_object(col, f'head_eye_white_{sfx}', white_mat, c, eyeball_mesh(c, r, side, rims[side], tree))
        iris = eye_object(col, f'head_eye_{sfx}', iris_mat, c, iris_mesh(c, r, side))
        iris['levi_eye_pivot'] = tuple(c)      # 目.L / 目.R turn the iris about this point
        iris['levi_eye_radius'] = r
        small = iris_mesh(c, r, side, PUPIL_SMALL)
        add_keys(iris, {'瞳小': [v.co.copy() for v in small.verts]})
        small.free()
        # the lid shadow: static, but it rides the upper lid in the eye morphs
        es = EyeShade(c, r, side)
        shade = eye_object(col, f'head_eye_shade_{sfx}', shade_mat, c, es.mesh())
        shade['levi_cast_shadow'] = False
        add_keys(shade, {n: es.positions(n) for n in EYE_MORPHS})
        # the highlights ride the eye bone with the iris
        hl = Highlights(c, r, side)
        hobj = atlas_object(col, f'head_eye_hilite_{sfx}', hl.mesh(), atlas_mat, 'white')
        hobj['levi_eye_pivot'] = tuple(c)
        hobj['levi_eye_radius'] = r
        add_keys(hobj, {'ハイライト消': hl.positions(off=True)})
        # the lashes follow the lid band through every morph
        p = eye_patch[side]
        decal, faces = lash_decal(p, co)
        lbm = bmesh.new()
        vs = [lbm.verts.new(Vector(tuple(q))) for q in decal.rest]
        for f in faces:
            lbm.faces.new([vs[i] for i in f])
        lash = atlas_object(col, f'head_eye_lash_{sfx}', lbm, atlas_mat, 'lash')
        lash_keys = {n: decal.positions(co, targets[n]) for n in EYE_MORPHS + BROW_MORPHS if targets.get(n)}
        fl0 = LASH_NS * (LASH_NT + 2)          # the flick's first vertex
        for n in EYE_CLOSE:                     # closed lids: the flick folds in toward its root
            if n in lash_keys:
                pts = lash_keys[n]
                root = (pts[fl0] + pts[fl0 + 1]) / 2.0
                pts[fl0:] = root + (pts[fl0:] - root) * FLICK_CLOSED
        add_keys(lash, lash_keys)
        hau.append(hau_stroke(p, co, targets.get('はぅ', {})))

    # the mouth: upper teeth and tongue inside the cavity
    teeth = common.new_object(col, 'head_mouth_teeth', teeth_mesh(), [teeth_mat])
    hidden = teeth_mesh(hidden=True)
    add_keys(teeth, {'歯無し上': [v.co.copy() for v in hidden.verts]})
    hidden.free()
    tongue = atlas_object(col, 'head_mouth_tongue', tongue_mesh(), atlas_mat, 'tongue')
    add_keys(tongue, {n: tongue_targets(n) for n in MOUTH_MORPHS})
    teeth.data.shade_smooth()
    teeth['no_outline'] = True
    teeth['levi_cast_shadow'] = False

    # overlays, hidden inside the head until their key
    surfs = [PatchSurface(p) for p in patches if p.kind == 'eye']
    kd = KDTree(len(co))
    for i, q in enumerate(co):
        kd.insert(q, i)
    kd.balance()
    fbm = flush_mesh(eyes)
    uv = fbm.loops.layers.uv.new('UVMap')
    for f in fbm.faces:
        for loop in f.loops:
            loop[uv].uv = front_uv(loop.vert.co)
    flush = common.new_object(col, 'head_fx_flush', fbm, [flush_mat])
    flush.data.shade_smooth()
    flush.data.normals_split_custom_set_from_vertices([normals[kd.find(v.co)[1]] for v in flush.data.vertices])
    flush['no_outline'] = True
    flush['levi_cast_shadow'] = False
    for name, obj in (('照れ', flush),
                      ('涙', atlas_object(col, 'head_fx_tear', tear_mesh(eyes), atlas_mat)),
                      ('汗', atlas_object(col, 'head_fx_sweat', sweat_mesh(eyes), atlas_mat))):
        placed = [v.co.copy() for v in obj.data.vertices]
        for v in obj.data.vertices:       # (the flush moves rigidly: its custom normals stay)
            v.co = v.co + Vector((0.0, FX_HIDE / PPM, 0.0)) if obj is flush else fx_hidden(v.co)
        hidden = [v.co.copy() for v in obj.data.vertices]
        keys = {name: placed}
        # the skin under an overlay moves in the face's morphs (笑い lifts the
        # cheek, the jaw drags it): the overlay takes the same motion, so the
        # keys add up (照れ + 笑い) without the skin coming through
        for n in FACE_MORPHS:
            if targets.get(n):
                d = skin_motion(kd, co, targets[n], placed, surfs)
                if d is not None:
                    keys[n] = [h + dv for h, dv in zip(hidden, d)]
        add_keys(obj, keys)
    hbm = bmesh.new()
    placed_pts = []
    for rest, placed, faces in hau:
        vs = [hbm.verts.new(Vector(tuple(q))) for q in rest]
        placed_pts += list(placed)
        for f in faces:
            hbm.faces.new([vs[i] for i in f])
    hobj = atlas_object(col, 'head_fx_hau', hbm, atlas_mat, 'lash')
    add_keys(hobj, {'はぅ': placed_pts})

    for side, nm in ((1, 'head_ear_L'), (-1, 'head_ear_R')):
        ear = common.new_object(col, nm, ear_mesh(side), [skin])
        common.shade_smooth(ear, 80)
        common.add_outline(ear)

    c, r = eyes[1]
    print(f'HEAD eye pivot L ({c.x:.4f}, {c.y:.4f}, {c.z:.4f}) radius {r * PPM:.2f} px')
    _FIELDS.clear()        # (~60 MB of voxels: only needed while building)
    return col
