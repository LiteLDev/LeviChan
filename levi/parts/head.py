"""Head: skull, face (profile, nose, jaw), eyes, mouth, ears and the top of the neck.

The head is a grid of horizontal rings. Every ring is two superellipse halves
(face half in front, skull/jaw half behind) whose extents come from a table of
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
  eyeball and stay in front of it along the whole linear morph.

Local landmark corrections (spec.L is a +-3 px first pass):
* the face, eyes and neck on ref/front.png are centred on panel column ~321.5,
  not 320, so the whole head is shifted by HEAD_DX (+1.5 px, character's left);
* chin_z: the sheet's front view puts the chin point on row ~162, the side view
  on row ~158; the model ends the (now rounded) chin at row 161.3, its
  profile 1-2.5 px behind the old wedge over rows 155-161.
"""
import math
from functools import lru_cache

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

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
    (132.0, 35.1, 234.2, 290.5, 309.0),
    (136.0, 34.0, 235.4, 287.9, 300.0),
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
NOSE = [(106.0, 0.0), (108.5, 0.4), (111.0, 1.1), (113.5, 2.0), (116.0, 3.1),
        (118.0, 4.4), (120.0, 5.5), (122.0, 6.7), (123.5, 7.6), (125.0, 7.9),
        (126.5, 7.6), (128.0, 6.3), (129.5, 4.3), (131.0, 2.5), (132.5, 1.1),
        (134.0, 0.3), (135.5, 0.0)]
# base front surface of the face under the muzzle [col]: from the forehead it
# recedes smoothly to the chin; TABLE's front column is the midline profile
# Below the nose it recedes steadily (not a vertical plate that bends back
# only at the jaw), meeting the profile again at the chin.
BASE_FRONT = ((112.0, 240.5), (118.0, 240.3), (124.0, 240.1), (130.0, 240.3), (136.0, 241.1),
              (142.0, 242.5), (148.0, 244.2), (153.0, 245.9), (157.0, 246.8), (160.5, 248.2))
MUZZLE_SIGMA = 11.0              # lateral falloff of the muzzle [px]
# lateral falloff [px] by row: a broad bridge narrowing to a small tip
NOSE_SIGMA = ((106.0, 6.5), (116.0, 5.4), (122.0, 5.0), (126.0, 4.9), (135.5, 4.6))
# front half cross-section exponent by row: fuller than an ellipse at eye
# level (with the widest point brought forward, see TABLE) so the face plate
# is broad, relaxing to a plain ellipse at the chin
FRONT_EXP = ((80.0, 2.2), (98.0, 2.8), (118.0, 2.8), (132.0, 2.4), (148.0, 2.1), (161.3, 2.0))

RING_ROWS = ([43.0, 44.5, 47, 50, 54, 59, 65, 72, 80, 88, 94, 98.5]
             + [100.0 + 1.5 * k for k in range(21)]        # eyes and nose: 100 .. 130
             + [131.5, 133, 134.5, 136, 137.5, 139, 140.5, 141.75, 143, 144.25, 145.5, 146.75, 148,
                149.25, 150.5, 151.75, 153, 154.25, 155.4, 156.5, 157.5, 158.4, 159.2, 159.9,
                160.5, 161.0, 161.3])


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
    """Face surface point at (X px from the midline, row) as seen from the front."""
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
    lower = 0.25 * np.exp(-((R - (y_lo + 1.0)) / 2.0) ** 2) * along
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


def face_texture_pixels():
    """RGBA float array (rows top->bottom). RGB = lit colour, A = 1 where the
    toon shade applies (skin), 0 for unshaded decals (lashes)."""
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
    nose_d = np.hypot(X / 1.0, (R - 133.0) / 0.5) - 1.0
    paint(0.35 * _soft(nose_d * 0.6), hexrgb('#E2A49C'))
    # mouth: the slit is geometry; a soft lip-line tint around it carries the
    # drawn mouth stroke's weight and fades toward the corners
    mouth_d = np.maximum(np.abs(R - mouth_row(X)) - 0.55, X - (MOUTH_HALF + 0.2))
    gap = 0.55 + 0.25 * np.clip(X / 1.5, 0, 1)
    paint(0.55 * gap * _soft(mouth_d, 0.45), hexrgb('#A65F5A'))
    lip_d = np.hypot(X / 2.2, (R - 147.3) / 0.6) - 1.0
    paint(0.12 * _soft(lip_d * 0.6), hexrgb(spec.PALETTE['mouth']['base']))
    return cv.pixels()


def eye_texture_pixels(iris_only=False):
    """The eyes' texture in the same front-view mapping. The white (sclera,
    static): white with the lid's soft shadow under the upper lid. The iris
    (turns with the eye bone, iris_only): muted dark green top -> light mint
    bottom, soft rim, slit pupil, the lashes' shadow band and the highlights.
    All unshaded (A = 0)."""
    X, R = _texture_grid()
    cv = _Canvas(hexrgb('#FFFFFF'))
    paint = lambda cov, colour: cv.paint(cov, colour, unshaded=True)   # noqa: E731
    paint(np.ones_like(X), hexrgb('#FFFFFF'))
    y_up = upper_lid(X)
    # soft lid shadow on the white under the upper lid
    paint(0.55 * _soft(R - (y_up + 2.4), 0.8), hexrgb('#DCE3EE'))
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
    hi = np.hypot(X - (ix - 1.0), R - 110.8) - 1.5
    paint(_soft(hi), hexrgb('#FFFFFF'))
    hi2 = np.hypot(X - (ix + 3.2), R - 121.2) - 0.7
    paint(_soft(hi2) * 0.8, hexrgb('#E8FFF0'))
    return cv.pixels()


def face_image(pixels, name):
    img = bpy.data.images.get(name)
    if img:
        bpy.data.images.remove(img)
    img = bpy.data.images.new(name, TEX_RES, TEX_RES, alpha=True, float_buffer=False)
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
MOUTH_LOOPS = (0.3, 0.62)
EYE_GAP = 0.35                   # px between the opening's rim and the eyeball (closest point)
EYE_WALL_IN = 0.4                # px the rim rolls back into the eyeball
EYE_SLEEVE = 5.0                 # px deep socket sleeve behind the rim: what a turned eyeball uncovers
POUCH_BACK = (0.7, 3.6)          # px behind the slit: the slit's back rim, the pouch back
POUCH_SIZE = (6.2, 3.4)          # half-width, half-height [px] of the pouch back


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
    out = [Patch('eye', s, i0, i1, kl0, kl1) for s in (1, -1)]
    (ma, mb), mx = MOUTH_BOX
    j0, j1 = _nearest(rows, ma), _nearest(rows, mb)
    m = next(d for d in range(1, half) if x_of_a(angles[half + d], MOUTH_ROW) >= mx)
    out.append(Patch('mouth', 0, j0, j1, half - m, half + m))
    return out


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


def build_head(detail=True, eye_fit=None):
    """BMesh of head_face and its layout (patches). eye_fit: the left eyeball
    (centre, radius) from the detailed head; fitted here when None."""
    angles, rows = ring_angles(N_RING), RING_ROWS
    patches = make_patches(angles, rows)
    skip_v = set().union(*(p.interior() for p in patches))
    skip_f = set().union(*(p.cells() for p in patches))
    bm = bmesh.new()
    grid = {}
    for i, r in enumerate(rows):
        pts = ring(r, angles, detail)
        for k, p in enumerate(pts):
            if (i, k) not in skip_v:
                grid[i, k] = bm.verts.new(p)
    for i in range(len(rows) - 1):
        for k in range(N_RING):
            if (i, k) in skip_f:
                continue
            k2 = (k + 1) % N_RING
            bm.faces.new((grid[i, k], grid[i, k2], grid[i + 1, k2], grid[i + 1, k]))
    bm.faces.new([grid[0, k] for k in reversed(range(N_RING))])
    bm.faces.new([grid[len(rows) - 1, k] for k in range(N_RING)])

    eyes = {}
    for p in patches:
        build_patch(bm, p, grid, angles, rows, detail)
        if p.kind == 'eye' and p.side > 0:
            eyes[1] = eye_fit if eye_fit else fit_eyeball([bm.verts[v].co.copy() for v in p.loops[0]])
            eyes[-1] = mirror_eye(eyes[1])
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
    return bm, patches, eyes


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
        + 0.2 * np.exp(-((R - (lower_lid(Xl) + 1.0)) / 2.0) ** 2) * along
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


def build_patch(bm, p, grid, angles, rows, detail):
    """Concentric loops from the grid boundary to the feature's opening."""
    eye = p.kind == 'eye'
    start_x = EYE_CX if eye else 0.0
    c0, c0_corners = eye_polygon() if eye else mouth_polygon()
    start = min(range(p.kl0 + 1, p.kl1), key=lambda kl: abs(x_of_a(angles[kl], rows[p.i0]) - start_x))
    bnd = p.boundary(start)
    bverts = [grid[i, p.k(kl)] for i, kl in bnd]
    seg = [(bverts[(m + 1) % len(bverts)].co - bverts[m].co).length for m in range(len(bverts))]
    fr = np.concatenate([[0.0], np.cumsum(seg)[:-1]]) / sum(seg)
    C0 = _resample(c0, fr, c0_corners)
    if eye:
        mid = lambda X: (lash_bottom(X) + lower_lid(X)) / 2   # noqa: E731
        p.upper = [r < mid(min(max(X, EYE_IN), EYE_OC)) - 1e-6 for X, r in C0]
        C1 = [eye_outer_point(X, r, up) for (X, r), up in zip(C0, p.upper)]
        ts = EYE_LOOPS
    else:
        p.upper = [r < float(mouth_row(X)) - 1e-6 for X, r in C0]
        lips, lip_corners = mouth_polygon(grow=0.9)
        C1 = _resample(lips, fr, lip_corners)
        ts = MOUTH_LOOPS
    sgn = p.sign()
    # loops in (local angle, row): C1 -> boundary
    b_par = [(angles[kl], rows[i]) for i, kl in bnd]
    c1_par = [(a_of_x(X, r), r) for X, r in C1]
    loops_par = []
    for t in ts:
        loops_par.append([(a1 + (ab - a1) * t, r1 + (rb - r1) * t) for (a1, r1), (ab, rb) in zip(c1_par, b_par)])

    def world(par):
        return surf(par[0] * sgn, par[1], detail)

    def px_of(par):
        return (x_of_a(par[0], par[1]), par[1])

    loops = [[_new_vert(bm, face_point(X * sgn, r, detail)) for X, r in C0],
             [_new_vert(bm, face_point(X * sgn, r, detail)) for X, r in C1]]
    p.px = [list(C0), list(C1)]
    p.fade = [1.0, 1.0]
    for t, lp in zip(ts, loops_par):
        loops.append([_new_vert(bm, world(par)) for par in lp])
        p.px.append([px_of(par) for par in lp])
        p.fade.append((1.0 - t) ** 1.5)
    loops.append(bverts)
    p.px.append([px_of(par) for par in b_par])
    p.fade.append(0.0)
    n = len(bverts)
    for a, b in zip(loops, loops[1:]):
        for m in range(n):
            m2 = (m + 1) % n
            bm.faces.new((a[m], a[m2], b[m2], b[m]))
    _sync(bm)
    p.loops = [[v.index for v in lp] for lp in loops]


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


def add_pouch(bm, p, detail):
    """The mouth slit's lips roll back into a small closed pouch."""
    c0 = [bm.verts[v] for v in p.loops[0]]
    rim = [_new_vert(bm, pouch_back(v.co)) for v in c0]
    centre = face_point(0.0, MOUTH_ROW + 0.8, detail) + Vector((0.0, POUCH_BACK[1] / PPM, 0.0))
    back = []
    for (X, rr) in p.px[0]:
        ang = math.atan2((rr - (MOUTH_ROW + 0.8)) / POUCH_SIZE[1], X / POUCH_SIZE[0])
        back.append(_new_vert(bm, centre + Vector((math.cos(ang) * POUCH_SIZE[0] / PPM, -0.6 / PPM,
                                                   -math.sin(ang) * POUCH_SIZE[1] / PPM))))
    mid = _new_vert(bm, centre)
    n = len(c0)
    for m in range(n):
        m2 = (m + 1) % n
        bm.faces.new((rim[m], rim[m2], c0[m2], c0[m]))          # the lips' inner edge: skin
        for f in (bm.faces.new((back[m], back[m2], rim[m2], rim[m])), bm.faces.new((mid, back[m2], back[m]))):
            f.material_index = 1                                  # the pouch: 'mouth'
    _sync(bm)
    p.wall = [v.index for v in rim]
    p.pouch = [v.index for v in back] + [mid.index]


# ---------------------------------------------------------------- morphs
BLINK_KEY = 'まばたき'
EYE_MORPHS = (BLINK_KEY, 'ウィンク', 'ウィンク右', '笑い')
MOUTH_MORPHS = ('あ', 'い', 'う', 'え', 'お')
LID_OVERLAP = 0.25               # px the closed upper lid sits in front of the lower lid
LID_PATH = 0.2                   # px the lids keep in front of the eyeball along a morph


def eye_motion(name, X, row, upper):
    """(dX, drow, forward) of an opening vertex in the eye morph `name` [px]."""
    Xc = min(max(X, EYE_IN), EYE_OC)
    close = float(lower_lid(Xc)) - 1.4            # where the lids meet
    if name == '笑い':
        # smiling eyes: closed along an upward arch, the lower lid (and the
        # cheek under it) pushed up further at the middle
        bump = math.sin(math.pi * min(max((X - EYE_IN) / (EYE_OC - EYE_IN), 0.0), 1.0)) ** 0.9
        close -= 4.0 * bump
    # the vertical inner edge keeps a trace of its height (in order), so its
    # vertices close onto a short line instead of collapsing onto one point
    spread = 0.12 * (row - float(lash_bottom(Xc) + lower_lid(Xc)) / 2) if X <= EYE_IN + 1e-6 else 0.0
    if upper:
        return 0.0, close + 0.5 + spread - row, LID_OVERLAP
    return 0.0, close + spread - row, 0.0


def mouth_motion(name, X, row, upper):
    """(dX, drow, forward) of a slit vertex in the mouth morph `name` [px]."""
    w = max(0.0, 1.0 - (X / MOUTH_HALF) ** 2) ** 0.7
    if name == 'あ':
        return -0.1 * X, (-0.5 if upper else 3.4) * w, 0.0
    if name == 'い':
        return 0.2 * X, (-0.35 if upper else 0.9) * w - 0.5 * (1 - w), 0.0
    if name == 'え':
        return 0.06 * X, (-0.45 if upper else 2.0) * w, 0.0
    if name == 'お':
        return -0.28 * X, (-0.6 if upper else 2.8) * w, 0.5 * (1.0 - 0.3 * abs(X) / MOUTH_HALF)
    # う: a small, round, pursed mouth
    return -0.4 * X, (-0.5 if upper else 0.9) * w, 0.9 * (1.0 - 0.3 * abs(X) / MOUTH_HALF)


def morph_targets(name, patches, eyes, co):
    """{vertex index: world position} of the morph `name`; co: rest positions."""
    out = {}
    for p in patches:
        if p.kind == 'eye' and name in EYE_MORPHS:
            if (name == 'ウィンク' and p.side < 0) or (name == 'ウィンク右' and p.side > 0):
                continue
            out.update(_eye_targets(name, p, eyes, co))
        elif p.kind == 'mouth' and name in MOUTH_MORPHS:
            out.update(_mouth_targets(name, p, eyes, co))
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


def _mouth_targets(name, p, eyes, co):
    out, fwd = _moved(p, lambda X, row, up: mouth_motion(name, X, row, up), co, eyes)
    for v, pt in out.items():
        pt.y -= fwd[v]
    for w, v in zip(p.wall, p.loops[0]):
        if v in out:
            out[w] = pouch_back(out[v])
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


def set_shading_normals(me, smooth, own=(), rim_of=None):
    """Custom normals: mostly the smooth face form (no nose / lid / lip detail,
    so the two-tone shading stays clean), blended with some of the real normal
    so the lids and cheeks still turn the light a little. `own`: vertices that
    keep their real normal (the mouth pouch). `rim_of`: {vertex: opening
    vertex} for the rims rolling into the openings, which take their opening
    vertex's normal, so the lid edge never turns dark in a sliver."""
    normals = []
    for v, n in zip(me.vertices, smooth):
        k = 1.0 if v.index in own else shade_keep(v.co)
        normals.append((n * (1 - k) + v.normal * k).normalized())
    for v, src in (rim_of or {}).items():
        normals[v] = normals[src]
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
IRIS_RINGS, IRIS_SEG = 5, 28
IRIS_EDGE = 0.985                # disc edge on the painted iris outline (inside its soft rim)


def iris_mesh(c, r, side):
    """The iris disc: a piece of the sphere IRIS_LIFT in front of the white,
    whose front projection is exactly the painted iris ellipse."""
    ix, iy, irx, iry = IRIS
    rr = r + IRIS_LIFT / PPM
    bm = bmesh.new()

    def at(X, row):
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


# ---------------------------------------------------------------- ears, neck
def ear_mesh(side):
    """Small ear, mostly hidden by the hair; peeks out on the front view. A
    thin oval plate whose front edge tucks into the side of the head and whose
    back edge flares out a little, with a shallow bowl (concha) on its outer
    face, so it reads as an ear and not a button."""
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=10, v_segments=7, radius=1.0)
    for v in bm.verts:
        x, y, z = v.co
        if x > 0.2:   # outer face: dish the middle in
            v.co.x -= 0.75 * x * max(0.0, 1.0 - (y * y + z * z) / 0.55)
    bmesh.ops.scale(bm, vec=(3.0 / PPM, 5.0 / PPM, 6.6 / PPM), verts=bm.verts)
    bmesh.ops.rotate(bm, cent=(0, 0, 0), verts=bm.verts,
                     matrix=Matrix.Rotation(math.radians(-14), 3, 'Y'))   # top leans out
    bmesh.ops.rotate(bm, cent=(0, 0, 0), verts=bm.verts,
                     matrix=Matrix.Rotation(math.radians(-16), 3, 'Z'))   # back edge flares out
    bmesh.ops.rotate(bm, cent=(0, 0, 0), verts=bm.verts,
                     matrix=Matrix.Rotation(math.radians(-10), 3, 'X'))   # top tilts back
    if side < 0:
        for v in bm.verts:
            v.co.x = -v.co.x
        bmesh.ops.reverse_faces(bm, faces=bm.faces)
    bmesh.ops.translate(bm, vec=(HEAD_DX + side * 37.0 / PPM, yc(290.5), zr(134.0)), verts=bm.verts)
    return bm


NECK_SHADE_ROW = 166.0    # the neck's shading normals turn under the jaw above this row
NECK_SHADE_BAND = 8.0     # ... over this many rows either side (no hard edge)
NECK_TILT = Vector((0.0, 0.6, -0.8)) * 0.15   # added to the real normal: down and back


def set_neck_normals(me):
    """The sheet draws a band of shade under the chin. Tilt the upper neck's
    real normals down and back (away from the camera-relative key light) and
    fade the tilt out over NECK_SHADE_BAND rows around NECK_SHADE_ROW, so the
    shade edge sits a few px below the jaw, still turns around the neck, and
    the neck meets the body's neck lit. The jaw's cast shadow lands on top."""
    lo, hi = zr(NECK_SHADE_ROW + NECK_SHADE_BAND), zr(NECK_SHADE_ROW - NECK_SHADE_BAND)
    out = []
    for v in me.vertices:
        w = float(_smooth(lo, hi, v.co.z))
        out.append((v.normal + NECK_TILT * w).normalized())
    me.normals_split_custom_set_from_vertices(out)


def neck_mesh():
    """Top of the neck, from inside the head down to just above the choker."""
    # row, depth centre [col], half-width, half-depth [px]: the top flares
    # back into the base of the skull instead of meeting it as a plain tube
    # the throat also leans forward into the jaw's underside as a broad fillet
    # (it meets the underside at ~150 deg, not square), so the jaw rolls into
    # the neck instead of sitting on a cylinder
    rows = [(138.0, 288.5, 16.0, 16.0), (146.0, 285.0, 15.5, 18.0), (151.0, 283.6, 15.3, 18.0),
            (155.0, 284.0, 15.1, 16.8), (158.0, 284.6, 14.95, 16.0), (161.0, 285.8, 14.85, 14.3),
            (165.0, 286.9, 14.8, 13.1), (169.0, 287.9, 14.8, 12.7), (174.0, 289.5, 14.8, 12.6)]
    rings = [common.ellipse_ring((HEAD_DX, yc(cy), zr(r)), w / PPM, d / PPM, 28) for r, cy, w, d in rows]
    return common.loft(rings, closed=True, cap_start=True, cap_end=False)


# ---------------------------------------------------------------- build
def build(col):
    skin = common.toon_material('skin')
    mouth = common.toon_material('mouth')
    pixels = face_texture_pixels()
    face = face_material(pixels)
    white_mat = face_material(eye_texture_pixels(), 'toon_face_eyewhite', 'levi_eyewhite_tex')
    iris_mat = face_material(eye_texture_pixels(iris_only=True), 'toon_face_iris', 'levi_iris_tex')

    bm, patches, eyes = build_head(detail=True)
    co = [v.co.copy() for v in bm.verts]
    smooth_bm, _, _ = build_head(detail=False, eye_fit=eyes[1])
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
    set_shading_normals(me, smooth, own - set(rim_of), rim_of)
    head.shape_key_add(name='Basis', from_mix=False)
    for name in EYE_MORPHS + MOUTH_MORPHS:
        kb = head.shape_key_add(name=name, from_mix=False)
        for v, pt in morph_targets(name, patches, eyes, co).items():
            kb.data[v].co = pt
        kb.value = 0.0   # a new key is not guaranteed to start at 0
    # no outline hull on the rims rolling into the openings and the pouch: seen
    # from above or below it would draw a line across the iris / the mouth
    vg = head.vertex_groups.new(name='outline_width')
    vg.add([v.index for v in me.vertices if v.index not in own], 1.0, 'REPLACE')
    vg.add(sorted(own), 0.0, 'REPLACE')
    common.add_outline(head, vertex_group='outline_width', min_factor=0.0)

    tree = BVHTree.FromPolygons([v.co for v in me.vertices], [tuple(q.vertices) for q in me.polygons])
    for side, sfx in ((1, 'L'), (-1, 'R')):
        c, r = eyes[side]
        eye_object(col, f'head_eye_white_{sfx}', white_mat, c, eyeball_mesh(c, r, side, rims[side], tree))
        iris = eye_object(col, f'head_eye_{sfx}', iris_mat, c, iris_mesh(c, r, side))
        iris['levi_eye_pivot'] = tuple(c)      # 目.L / 目.R turn the iris about this point
        iris['levi_eye_radius'] = r

    for side, nm in ((1, 'head_ear_L'), (-1, 'head_ear_R')):
        ear = common.new_object(col, nm, ear_mesh(side), [skin])
        common.shade_smooth(ear, 80)
        common.add_outline(ear)

    neck = common.new_object(col, 'head_neck', neck_mesh(), [skin])
    neck.data.shade_smooth()
    set_neck_normals(neck.data)
    common.add_outline(neck)
    c, r = eyes[1]
    print(f'HEAD eye pivot L ({c.x:.4f}, {c.y:.4f}, {c.z:.4f}) radius {r * PPM:.2f} px')
    return col
