"""Head: skull, face (profile, nose, jaw), ears and the top of the neck.

The head is a loft of horizontal rings. Every ring is two superellipse halves
(face half in front, skull/jaw half behind) whose extents come from a table of
measurements taken on ref/front.png (half-width) and ref/side.png (front
profile, jaw/skull back line), in reference panel pixels. The eyes, brows,
mouth, nose tip and blush are painted into a procedurally generated texture
that is projected from the front view, so they land on the exact panel pixels
of the sheet.

The table's front column is the midline profile only. Across the face it is
split into a smooth base front (BASE_FRONT) plus a broad muzzle and the nose
around the midline, so the profile does not drag a band across the cheeks.
relief() then shapes the face in depth along -Y only (so the front-projected
texture stays on its panel pixels): shallow eye sockets, an upper lid rim that
carries the lashes, a lower lid, soft cheeks and the lips / chin. The face's
custom normals come from the same head without nose and relief, blended with
a little of the real normal: clean two-tone shading that still turns at the
cheeks.

A thin upper-lid sheet over each painted eye (head_lid) carries the MMD blink
morph as the shape key 'まばたき' (see the eyelids section).

Local landmark corrections (spec.L is a +-3 px first pass):
* the face, eyes and neck on ref/front.png are centred on panel column ~321.5,
  not 320, so the whole head is shifted by HEAD_DX (+1.5 px, character's left);
* chin_z: the sheet's front view puts the chin point on row ~162, the side view
  on row ~158; the model compromises at row 160.5.
"""
import math

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

from .. import common, spec, toon

PPM = spec.PX_PER_M
CENTER_COL = 321.5               # face midline on ref/front.png
HEAD_DX = (CENTER_COL - spec.PANEL_W / 2) / PPM
N_RING = 60                      # vertices per ring
SHADE_KEEP = 0.3                 # share of the real normal in the face's shading normals
OUTLINE_PX = spec.OUTLINE_WIDTH * PPM   # ~1.4 px: drawn lines are centred on the surface edge + half this


def zr(row):
    return (spec.SHEET_GROUND_Y - row) / PPM


def yc(col):
    """Side-view panel column -> world y."""
    return (col - spec.PANEL_W / 2) / PPM


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
    (128.0, 36.8, 235.5, 291.5, 317.0),
    (132.0, 35.1, 234.4, 290.5, 309.0),
    (136.0, 34.0, 234.0, 287.9, 300.0),
    (140.0, 32.3, 235.5, 284.8, 296.0),
    (142.0, 31.4, 237.5, 283.0, 294.5),
    (144.0, 30.3, 238.7, 281.0, 293.0),
    (146.0, 28.8, 240.0, 278.8, 291.0),
    (148.0, 26.5, 241.3, 276.4, 288.2),
    (150.0, 23.8, 242.0, 273.6, 284.2),
    (152.0, 20.3, 243.0, 270.5, 278.6),
    (153.5, 17.6, 243.5, 268.0, 274.6),
    (155.5, 13.9, 244.3, 263.6, 271.5),
    (157.0, 10.6, 245.2, 259.8, 267.6),
    (158.3, 7.9, 246.2, 256.0, 262.0),
    (159.5, 5.0, 247.3, 251.8, 255.5),
    # chin tip: a little fuller just above the end ring, so it rounds off
    # instead of running into a cone point (front V kept)
    (160.5, 2.8, 248.4, 250.0, 252.0),
    (161.3, 0.9, 249.2, 249.7, 250.2),
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
              (142.0, 242.5), (148.0, 244.2), (153.0, 245.5), (157.0, 246.4), (160.5, 248.3))
MUZZLE_SIGMA = 11.0              # lateral falloff of the muzzle [px]
# lateral falloff [px] by row: a broad bridge narrowing to a small tip
NOSE_SIGMA = ((106.0, 6.5), (116.0, 5.4), (122.0, 5.0), (126.0, 4.9), (135.5, 4.6))
# front half cross-section exponent by row: fuller than an ellipse at eye
# level (with the widest point brought forward, see TABLE) so the face plate
# is broad enough that the front-projected eyes stay compact on the side view,
# relaxing to a plain ellipse at the chin
FRONT_EXP = ((80.0, 2.2), (98.0, 2.8), (118.0, 2.8), (132.0, 2.4), (148.0, 2.1), (161.3, 2.0))

RING_ROWS = ([43.0, 44.5, 47, 50, 54, 59, 65, 72, 80, 88, 94, 98.5]
             + [101.0 + 1.5 * k for k in range(20)]        # eyes and nose: 101 .. 129.5
             + [131, 133, 135, 137, 139, 141, 142.5, 144, 145.3, 146.5, 147.7, 149, 150.5,
                152, 153.5, 155, 156.5, 157.8, 159, 160.2, 161.3])


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


LOWER_CHEEK = (2.0, 0.62, 145.0, 8.0)   # amplitude px, centre as share of hw, row, row sigma


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


def _ring_params(row, detail):
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


def face_y(X, row, detail=True):
    """Side-view column of the face surface at distance X [px] from the
    midline on ring row `row` (the analytic surface the head mesh samples)."""
    q = _ring_params(row, detail)
    u = min(abs(X) / q['hw'], 1.0)
    s = u ** (1.0 / q['ef'])
    return _front_y(q, row, X, math.sqrt(max(0.0, 1.0 - s * s)), detail)


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


# ---------------------------------------------------------------- face texture
TEX_RES = 1024
TEX_PX = 8                       # texture pixels per panel pixel
TEX_COL0 = CENTER_COL - TEX_RES / TEX_PX / 2
TEX_ROW0 = 60.0
SKIN_UV = (2.0 / TEX_RES, 2.0 / TEX_RES)   # plain-skin corner for the back of the head


# Eye (front view, panel px: X = distance from the face midline, row)
EYE_IN, EYE_OUT = 14.0, 41.0     # inner / outer corner X
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


def upper_lid(X):
    """Row of the upper lid line at distance X from the midline: a flat, heavy
    lid that drops to a low outer corner."""
    X = np.asarray(X, float)
    u = (X - EYE_TOP_X) / np.where(X < EYE_TOP_X, EYE_TOP_X - EYE_IN, EYE_OUT - EYE_TOP_X)
    return EYE_TOP_ROW + np.where(X < EYE_TOP_X, 3.4, 5.4) * np.abs(u) ** 3


def lower_lid(X):
    return np.polyval(_quad((EYE_IN, 117.2), (25.0, 125.0), (EYE_OUT - 0.4, 112.8)), np.asarray(X, float))


def _smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def relief(X, R):
    """Forward offset [px, + toward the viewer] of the face surface at (X, row):
    the eye sockets with the upper and lower lid rims around them, soft cheeks,
    and the lips / chin articulation of the profile. Applied along -Y only, so
    the front-view projection of the painted features does not move."""
    X = np.asarray(X, float)
    R = np.asarray(R, float)
    y_up, y_lo = upper_lid(X), lower_lid(X)
    along = _smooth(EYE_IN - 4.0, EYE_IN + 1.0, X) * (1.0 - _smooth(EYE_OUT + 0.5, EYE_OUT + 5.0, X))
    # socket: a shallow rounded bowl around each eye, deepest at the rim of
    # the opening and bulging back out toward the iris (no hard edge)
    e_d = np.maximum.reduce([y_up - R, R - y_lo, EYE_IN - X, X - EYE_OUT])
    inside = _smooth(3.5, -2.0, e_d)
    rr = ((X - 27.0) / 13.5) ** 2 + ((R - 116.5) / 8.5) ** 2
    socket = -inside * (1.25 - 0.6 * np.clip(1.0 - rr, 0.0, 1.0))
    # upper lid: a soft rim that wraps over the top of the eye (carries the
    # lashes); the lower lid only a faint roll into the cheek
    lid = 0.8 * np.exp(-((R - (y_up + 1.0)) / 2.3) ** 2) * along
    lower = 0.2 * np.exp(-((R - (y_lo + 1.0)) / 2.0) ** 2) * along
    cheek = 0.9 * np.exp(-((X - 25.0) / 10.0) ** 2 - ((R - 130.0) / 7.0) ** 2)
    # lips and chin: restrained upper lip, mouth line, lower lip and fold
    # (kept faint and narrow: wide bands read as shelves across the lower face)
    lips = (0.25 * np.exp(-((R - 143.6) / 1.8) ** 2) * np.exp(-(X / 5.0) ** 2)
            - 0.2 * np.exp(-((R - 146.3) / 1.0) ** 2) * np.exp(-(X / 4.5) ** 2)
            + 0.15 * np.exp(-((R - 148.3) / 1.4) ** 2) * np.exp(-(X / 4.5) ** 2)
            - 0.12 * np.exp(-((R - 151.0) / 2.0) ** 2) * np.exp(-(X / 6.0) ** 2))
    return socket + lid + lower + cheek + lips


def face_texture_pixels():
    """RGBA float array (rows top->bottom). RGB = lit colour, A = 1 where the
    toon shade applies (skin), 0 for unshaded eye decals."""
    j = (np.arange(TEX_RES) + 0.5) / TEX_PX
    col = TEX_COL0 + j[None, :]
    row = TEX_ROW0 + j[:, None]
    col, row = np.broadcast_arrays(col, row)
    X = np.abs(col - CENTER_COL)          # outward distance from the midline
    R = row
    rgb = np.empty(col.shape + (3,))
    rgb[:] = hexrgb(spec.PALETTE['skin']['base'])
    shade = np.ones(col.shape)

    def paint(cov, colour, unshaded=False):
        cov = cov[..., None]
        rgb[:] = rgb * (1 - cov) + np.asarray(colour) * cov
        if unshaded:
            shade[:] = shade * (1 - cov[..., 0])

    # blush: a faint, soft wash under the eyes (the sheet has no visible hatching)
    blush = np.exp(-(((X - 24.5) / 9.0) ** 2 + ((R - 125.5) / 3.4) ** 2))
    paint(0.34 * blush, hexrgb('#F6B6AE'))
    for k in range(3):   # barely-there hatch strokes
        xs = 21.0 + 3.0 * k
        d = np.abs((X - xs) + 0.45 * (R - 125.5)) - 0.25
        inside = (np.abs(R - 125.5) < 1.3)
        paint(0.12 * _soft(d) * inside, hexrgb('#EE9C98'))

    # eye opening: flat, heavy upper lid that drops to a low outer corner, and
    # a lower lid curve, in (X, row)
    y_up = upper_lid(X)
    y_lo = lower_lid(X)
    inner_d = EYE_IN - X
    eye_d = np.maximum.reduce([y_up - R, R - y_lo, inner_d, X - EYE_OUT])
    eye = _soft(eye_d)
    paint(eye, hexrgb('#FFFFFF'), unshaded=True)
    # soft lid shadow on the white under the upper lid
    paint(eye * 0.55 * _soft(R - (y_up + 2.4), 0.8), hexrgb('#DCE3EE'), unshaded=True)

    # iris: muted dark green top -> light mint bottom, soft rim, slit pupil
    ix, iy, irx, iry = IRIS
    q = np.sqrt(((X - ix) / irx) ** 2 + ((R - iy) / iry) ** 2)
    iris = _soft((q - 1.0) * irx) * eye
    t = np.clip((R - (iy - iry * 0.6)) / (1.5 * iry), 0, 1)[..., None]
    grad = (1 - t) * hexrgb('#235E40') + t * hexrgb('#78CC94')
    rim = np.clip((q - 0.8) / 0.2, 0, 1)[..., None]
    iris_col = grad * (1 - 0.4 * rim) + hexrgb('#1A4A30') * 0.4 * rim
    paint(iris, iris_col, unshaded=True)
    q = np.sqrt(((X - (ix - 0.4)) / 1.3) ** 2 + ((R - 114.2) / 4.0) ** 2)
    paint(_soft((q - 1.0) * 1.3) * eye * 0.8, hexrgb('#123F28'), unshaded=True)
    # upper iris shadow band cast by the lashes
    paint(iris * 0.55 * _soft(R - (y_up + 3.2), 1.2), hexrgb('#143F2A'), unshaded=True)
    hi = np.hypot(X - (ix - 1.0), R - 110.8) - 1.5
    paint(_soft(hi) * eye, hexrgb('#FFFFFF'), unshaded=True)
    hi2 = np.hypot(X - (ix + 3.2), R - 121.2) - 0.7
    paint(_soft(hi2) * eye * 0.8, hexrgb('#E8FFF0'), unshaded=True)

    # upper lash mass: ~2.5 px, thicker toward the outer corner, with a flick
    thick = 2.5 + 1.1 * np.clip((X - EYE_IN) / (EYE_OUT - EYE_IN), 0, 1) ** 1.3
    thick = thick * np.clip(0.35 + (X - EYE_IN) / 4.0, 0.35, 1.0)    # tapered inner end
    thick = thick * np.clip(0.4 + (EYE_OUT + 1.2 - X) / 4.0, 0.4, 1.0)   # and outer end
    lash_d = np.maximum.reduce([y_up - 0.7 - R, R - (y_up + thick), inner_d - 0.3, X - (EYE_OUT + 1.2)])
    flick = np.maximum.reduce([np.abs(R - (112.0 - 0.8 * (X - EYE_OUT))) - 0.7, EYE_OUT - 0.8 - X,
                               X - (EYE_OUT + 2.2)])
    lash = np.maximum(_soft(lash_d), _soft(flick))
    paint(lash, hexrgb('#262A40'), unshaded=True)
    # lower lid: fine line on the outer half
    lo_d = np.maximum.reduce([np.abs(R - y_lo - 0.3) - 0.35, 27.0 - X, X - (EYE_OUT - 1.0)])
    paint(0.6 * _soft(lo_d), hexrgb('#B07A72'))
    # inner corner tick
    ic_d = np.maximum(np.abs(X - (EYE_IN + 0.3)) - 0.35, np.maximum(y_up + 1.0 - R, R - (y_up + 5.0)))
    paint(0.5 * _soft(ic_d), hexrgb('#A9706A'))

    # lid crease / brow: a soft mauve line above the lash (mostly under the bangs)
    brow_c = 103.9 - 0.04 * (X - 20.0) + 0.006 * (X - 26.0) ** 2
    taper = 0.42 * (1.15 - np.clip((X - 14) / 24, 0, 1))
    brow_d = np.maximum(np.abs(R - brow_c) - taper, np.maximum(15.0 - X, X - 37.0))
    paint(0.7 * _soft(brow_d, 0.5), hexrgb('#C08A84'))

    # nose tip and mouth: faint, small marks
    nose_d = np.hypot(X / 1.0, (R - 133.0) / 0.5) - 1.0
    paint(0.35 * _soft(nose_d * 0.6), hexrgb('#E2A49C'))
    mouth_c = 146.2 - 0.008 * X ** 2         # flat, corners not turned down
    mouth_d = np.maximum(np.abs(R - mouth_c) - 0.32, X - 4.2)
    gap = 0.65 + 0.35 * np.clip(X / 1.5, 0, 1)    # a lighter centre, as drawn
    paint(0.6 * gap * _soft(mouth_d), hexrgb('#A65F5A'))
    lip_d = np.hypot(X / 2.2, (R - 147.3) / 0.6) - 1.0
    paint(0.12 * _soft(lip_d * 0.6), hexrgb(spec.PALETTE['mouth']['base']))

    out = np.empty(col.shape + (4,), np.float32)
    out[..., :3] = rgb
    out[..., 3] = shade
    return out


def face_image(pixels):
    name = 'levi_face_tex'
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


def face_material(pixels):
    """Two-tone toon material like levi.toon, with the lit colour from the face
    texture and the shade colour = texture * (skin shade / skin base) where the
    texture alpha marks skin (eyes stay unshaded).

    The eye decals are not skin: the material's toon_gradient is the 'eye' key,
    and the per-vertex toon_grad attribute (set_eye_region) marks the vertices
    inside the eye openings, so render.py's region pass labels them as eyes."""
    name = 'toon_face'
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
    tex.image = face_image(pixels)
    tex.interpolation = 'Linear'
    tex.extension = 'EXTEND'
    pa = spec.PALETTE['skin']
    base, shade = toon.srgb(pa['base']), toon.srgb(pa['shade'])
    ratio =tuple(shade[i] / base[i] for i in range(3)) + (1.0,)
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


# ---------------------------------------------------------------- geometry
def head_mesh(detail=True):
    angles = ring_angles(N_RING)
    rings = [ring(r, angles, detail) for r in RING_ROWS]
    bm = common.loft(rings, closed=True, cap_start=True, cap_end=True)
    return bm


def smooth_normals():
    """Vertex normals of the head without nose and facial relief (same vertex
    order as head_mesh()): the clean shading form of the face."""
    bm = head_mesh(detail=False)
    bm.normal_update()
    out = [v.normal.copy() for v in bm.verts]
    bm.free()
    return out


def front_uv(co):
    colp = spec.PANEL_W / 2 + co.x * PPM
    rowp = spec.SHEET_GROUND_Y - co.z * PPM
    return ((colp - TEX_COL0) * TEX_PX / TEX_RES, 1.0 - (rowp - TEX_ROW0) * TEX_PX / TEX_RES)


def set_face_uv(me):
    uv = me.uv_layers.new(name='UVMap')
    back_y = yc(293.0)
    for poly in me.polygons:
        behind = poly.center.y > back_y
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            uv.data[li].uv = SKIN_UV if behind else front_uv(co)


def set_eye_region(me, pixels):
    """toon_grad = 1 on vertices whose front-projected texel is an (unshaded)
    eye decal, 0 elsewhere (back of the head included)."""
    attr = me.attributes.get(common.GRAD_ATTR) or me.attributes.new(common.GRAD_ATTR, 'FLOAT', 'POINT')
    back_y = yc(293.0)
    for v in me.vertices:
        val = 0.0
        if v.co.y <= back_y:
            u, w = front_uv(v.co)
            i = int(round((1.0 - w) * TEX_RES - 0.5))
            j = int(round(u * TEX_RES - 0.5))
            if 0 <= i < TEX_RES and 0 <= j < TEX_RES:
                val = 1.0 - float(pixels[i, j, 3])
        attr.data[v.index].value = val


def set_shading_normals(me, smooth, keep=SHADE_KEEP):
    """Custom normals: mostly the smooth face form (no nose / lid / lip detail,
    so the two-tone shading stays clean), blended with some of the real normal
    so the sockets, lids and cheeks still turn the light a little."""
    normals = [(n * (1 - keep) + v.normal * keep).normalized() for v, n in zip(me.vertices, smooth)]
    me.normals_split_custom_set_from_vertices(normals)
    return normals


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
NECK_SHADE_BAND = 5.0     # ... over this many rows either side (no hard edge)
NECK_TILT = Vector((0.0, 0.6, -0.8)) * 0.7   # added to the real normal: down and back


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
    # the throat also leans forward into the jaw's underside as a soft fillet
    rows = [(138.0, 288.5, 16.0, 16.0), (148.0, 286.0, 15.4, 16.0), (154.0, 285.6, 15.1, 15.0),
            (158.0, 286.2, 14.9, 13.6), (162.0, 286.8, 14.8, 12.7), (168.0, 287.8, 14.8, 12.6),
            (174.0, 289.5, 14.8, 12.6)]
    rings = [common.ellipse_ring((HEAD_DX, yc(cy), zr(r)), w / PPM, d / PPM, 20) for r, cy, w, d in rows]
    return common.loft(rings, closed=True, cap_start=True, cap_end=False)


# ---------------------------------------------------------------- eyelids
# A thin upper-lid sheet per eye for the MMD blink morph, in the face
# material.
# * Rest (the basis shape): folded into the band just above and on the
#   painted upper lash, a hair in front of the face. Its UVs are the front
#   projection of these rest positions, so at rest it is an exact copy of the
#   painted face under it (skin under the brow, the lash) and the open eye is
#   the painted one.
# * BLINK_KEY: the same sheet comes forward and down over the painted eye to
#   ~2 px below the lower lid line (so the painted eye stays covered when the
#   head is seen from below). Stretched, its upper rows show plain skin
#   and its two edge rows the lash band, so the closed eye is skin with a lash
#   line along the closing edge. The sheet stays in front of the face along
#   the whole (linear) morph.
BLINK_KEY = 'まばたき'
LID_X = (EYE_IN - 0.8, EYE_IN + 2.5, EYE_IN + 6.5, 22.0, 26.5, 31.0, 35.5, EYE_OUT, EYE_OUT + 2.4)
LID_REST = (-2.3, -1.9, -1.5, -1.1, 0.3, 1.6)   # rest rows relative to the upper lid line
LID_CLEAR = 0.3          # px in front of the face when closed
LID_OVER = 0.1           # px in front of the face at rest
LID_PATH = 0.15          # px in front of the face along the blink


def _lid_rows(X):
    """(rest rows, closed rows) of the six lid vertex rows at X."""
    xc = min(max(X, EYE_IN), EYE_OUT)
    up = float(upper_lid(xc))
    top = up + LID_REST[0]
    edge = max(float(lower_lid(xc)) + 1.8, up + 4.0)   # covers the painted eye from below too
    r3, r4 = edge - 1.9, edge - 1.3
    r1 = min(up + 1.0, (top + r3) / 2)
    return tuple(up + d for d in LID_REST), (top, r1, (r1 + r3) / 2, r3, r4, edge)


def mesh_face_y(tree):
    """face_y measured on the head mesh itself (ray cast along +Y into the
    head_face BVH `tree`): the polygons sit up to ~2 px behind the analytic
    surface where the face turns to the side, which matters for a sheet
    floating 0.1-0.3 px off it."""
    def f(X, row):
        o = Vector((HEAD_DX + X / PPM, -1.0, zr(row)))
        hit = tree.ray_cast(o, Vector((0.0, 1.0, 0.0)), 2.0)[0]
        return hit.y * PPM + spec.PANEL_W / 2 if hit is not None else face_y(X, row)
    return f


def lid_shapes(tree):
    """Rest and closed vertex grids of the left lid: lists over LID_X of six
    [X, col, row] (col = side-view column).

    1. Each vertex sits LID_OVER (rest) / LID_CLEAR (closed) in front of the
       face mesh over the rows its neighbouring lid faces span: the lid rim and
       the socket bend the face down the rows.
    2. Across X the face turns away steeply toward the temple, so a pair of
       columns only moves forward where the chord between them would cut into
       the face.
    3. The morph is linear: a closed vertex comes further forward until the
       straight paths from rest (its own and the chords to its neighbours)
       stay in front of the face; the socket bulges toward the iris between
       the lid line and the closing line."""
    surf = mesh_face_y(tree)
    rows = [_lid_rows(X) for X in LID_X]
    n, m = len(LID_X), len(LID_REST)
    out = []
    for k, margin in ((0, LID_OVER), (1, LID_CLEAR)):
        grid = []
        for i, X in enumerate(LID_X):
            rs = rows[i][k]
            col = []
            for j, r in enumerate(rs):
                span = np.linspace(rs[max(j - 1, 0)], rs[min(j + 1, m - 1)], 7)
                col.append([X, min(surf(X, s) for s in span) - margin, r])
            grid.append(col)
        for _ in range(3):
            for i in range(n - 1):
                for j in range(m):
                    a, b = grid[i][j], grid[i + 1][j]
                    need = max(0.0, max(a[1] + (b[1] - a[1]) * t - (surf(a[0] + (b[0] - a[0]) * t, a[2] + (b[2] - a[2]) * t) - margin)
                                        for t in (0.25, 0.5, 0.75)))
                    a[1] -= need
                    b[1] -= need
        out.append(grid)
    rest, closed = out

    def lerp(p, q, t):
        return [p[c] + (q[c] - p[c]) * t for c in range(3)]
    for _ in range(2):
        for i in range(n):
            for j in range(m):
                push = 0.0
                for t in np.linspace(0.1, 0.9, 9):
                    for i2 in (i - 1, i, i + 1):
                        if not 0 <= i2 < n:
                            continue
                        # point on the chord to the neighbour column (or the vertex itself)
                        p = lerp(lerp(rest[i][j], closed[i][j], t), lerp(rest[i2][j], closed[i2][j], t), 0.5 if i2 != i else 0.0)
                        push = max(push, 2 * (p[1] - (surf(p[0], p[2]) - LID_PATH)) / t / (2 if i2 == i else 1))
                closed[i][j][1] -= push
    return rest, closed


def lid_object(col, mat, head, head_normals, pixels):
    """Both upper lids in one object, with the BLINK_KEY shape key.

    head: the head_face object; head_normals: its per-vertex shading normals.
    At rest the lid copies the face under it exactly: UV (front projection),
    shading normal (interpolated from the face polygon under each vertex) and
    the eye-decal mask (toon_grad, as set_eye_region)."""
    me = head.data
    tree = BVHTree.FromPolygons([v.co for v in me.vertices], [tuple(p.vertices) for p in me.polygons])
    rest, closed = lid_shapes(tree)
    bm = bmesh.new()
    uv_layer = bm.loops.layers.uv.new('UVMap')
    key_pos, uvs = [], {}
    for side in (1, -1):
        verts = []
        for i, X in enumerate(LID_X):
            vc = []
            for j in range(len(rest[i])):
                _, y0, r0 = rest[i][j]
                _, y1, r1 = closed[i][j]
                v = bm.verts.new((HEAD_DX + side * X / PPM, yc(y0), zr(r0)))
                key_pos.append(Vector((HEAD_DX + side * X / PPM, yc(y1), zr(r1))))
                uvs[v] = front_uv(v.co)   # the painted face under the rest position
                vc.append(v)
            verts.append(vc)
        for i in range(len(LID_X) - 1):
            for j in range(len(rest[0]) - 1):
                quad = (verts[i][j], verts[i + 1][j], verts[i + 1][j + 1], verts[i][j + 1])
                f = bm.faces.new(quad if side > 0 else quad[::-1])
                for loop in f.loops:
                    loop[uv_layer].uv = uvs[loop.vert]
    bm.normal_update()
    if sum(f.normal.y for f in bm.faces) > 0:   # face the viewer (-Y)
        bmesh.ops.reverse_faces(bm, faces=bm.faces)
    obj = common.new_object(col, 'head_lid', bm, [mat])
    lid = obj.data
    lid.shade_smooth()
    obj['no_outline'] = True
    normals = []
    for v in lid.vertices:
        hit, _, idx, _ = tree.ray_cast(v.co + Vector((0.0, -0.05, 0.0)), Vector((0.0, 1.0, 0.0)), 0.1)
        if hit is None:
            normals.append(v.normal.copy())
            continue
        vs = me.polygons[idx].vertices
        w = [1.0 / ((me.vertices[k].co - hit).length + 1e-6) for k in vs]
        normals.append(sum((head_normals[k] * wk for k, wk in zip(vs, w)), Vector()).normalized())
    lid.normals_split_custom_set_from_vertices(normals)
    set_eye_region(lid, pixels)
    obj.shape_key_add(name='Basis', from_mix=False)
    kb = obj.shape_key_add(name=BLINK_KEY, from_mix=False)
    for d, p in zip(kb.data, key_pos):
        d.co = p
    kb.value = 0.0   # open eyes: a new key is not guaranteed to start at 0
    return obj


def build(col):
    skin = common.toon_material('skin')
    pixels = face_texture_pixels()
    face = face_material(pixels)

    head = common.new_object(col, 'head_face', head_mesh(), [face])
    head.data.shade_smooth()
    set_face_uv(head.data)
    set_eye_region(head.data, pixels)
    head_normals = set_shading_normals(head.data, smooth_normals())
    lid_object(col, face, head, head_normals, pixels)
    common.add_outline(head)

    for side, nm in ((1, 'head_ear_L'), (-1, 'head_ear_R')):
        ear = common.new_object(col, nm, ear_mesh(side), [skin])
        common.shade_smooth(ear, 80)
        common.add_outline(ear)

    neck = common.new_object(col, 'head_neck', neck_mesh(), [skin])
    neck.data.shade_smooth()
    set_neck_normals(neck.data)
    common.add_outline(neck)
    return col
