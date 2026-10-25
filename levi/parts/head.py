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
    (128.0, 36.8, 235.5, 291.5, 317.0),
    (132.0, 35.1, 234.4, 291.0, 309.0),
    (136.0, 34.0, 234.0, 290.0, 299.0),
    (140.0, 32.3, 235.5, 288.0, 295.5),
    (142.0, 31.4, 237.5, 287.0, 294.5),
    (144.0, 30.3, 238.7, 285.5, 293.0),
    (146.0, 28.8, 240.0, 284.0, 290.5),
    (148.0, 26.5, 241.3, 282.0, 286.0),
    (150.0, 23.8, 242.0, 277.0, 280.0),
    (152.0, 20.3, 243.0, 271.0, 275.0),
    (153.5, 17.6, 243.5, 267.0, 272.0),
    (155.5, 13.9, 244.3, 262.0, 269.0),
    (157.0, 10.6, 245.2, 257.5, 265.0),
    (158.3, 7.9, 246.2, 253.0, 259.0),
    (159.5, 5.0, 247.3, 250.0, 253.0),
    (160.5, 2.6, 248.3, 249.3, 250.5),
    (161.3, 0.8, 249.0, 249.3, 249.8),
]
# Nose: forward protrusion of the profile at the midline [px] per row. The
# bridge rises out of the forehead from row ~106, so forehead, bridge and tip
# read as one continuous line in profile (no spike on a flat plane).
NOSE = [(106.0, 0.0), (108.5, 0.4), (111.0, 1.1), (113.5, 2.0), (116.0, 3.1),
        (118.0, 4.4), (120.0, 5.6), (122.0, 7.0), (123.5, 8.2), (125.0, 8.6),
        (126.5, 8.2), (128.0, 6.5), (129.5, 4.3), (131.0, 2.5), (132.5, 1.1),
        (134.0, 0.3), (135.5, 0.0)]
# base front surface of the face under the muzzle [col]: from the forehead it
# recedes smoothly to the chin; TABLE's front column is the midline profile
BASE_FRONT = ((112.0, 240.5), (118.0, 240.3), (124.0, 240.0), (132.0, 239.7), (138.0, 239.9),
              (144.0, 240.7), (150.0, 242.0))
MUZZLE_SIGMA = 11.0              # lateral falloff of the muzzle [px]
# lateral falloff [px] by row: a broad bridge narrowing to a small tip
NOSE_SIGMA = ((106.0, 6.5), (116.0, 5.2), (122.0, 4.5), (126.0, 4.3), (135.5, 4.0))
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
    return float(np.interp(row, rows, vals))


def nose_sigma(row):
    rows, vals = zip(*NOSE_SIGMA)
    return float(np.interp(row, rows, vals))


def ring(row, angles, detail=True):
    """One horizontal ring. detail=False leaves out the nose and the facial
    relief: that smooth surface gives the shading normals."""
    hw, front, mid, back = table_at(row)
    muzzle = muzzle_at(row)
    front += muzzle
    bf, bb = max(mid - front, 0.3), max(back - mid, 0.3)
    nose = nose_at(row) if detail else 0.0
    sig = nose_sigma(row)
    ef, eb = 2.0 / front_exp(row), 1.0
    pts = []
    for a in angles:
        s, c = math.sin(a), math.cos(a)
        if c >= 0:   # front half
            xp = hw * math.copysign(abs(s) ** ef, s)
            yp = mid - bf * abs(c) ** ef - muzzle * math.exp(-(xp / MUZZLE_SIGMA) ** 2)
            if detail:
                yp -= nose * math.exp(-(xp / sig) ** 2)
                # facial relief, faded out where the surface turns to the side
                yp -= float(relief(abs(xp), row)) * _smooth(0.05, 0.3, c)
        else:
            xp = hw * math.copysign(abs(s) ** eb, s)
            yp = mid + bb * abs(c) ** eb
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
    lips = (0.3 * np.exp(-((R - 143.6) / 1.8) ** 2) * np.exp(-(X / 6.0) ** 2)
            - 0.25 * np.exp(-((R - 146.3) / 1.0) ** 2) * np.exp(-(X / 5.0) ** 2)
            + 0.2 * np.exp(-((R - 148.3) / 1.4) ** 2) * np.exp(-(X / 5.0) ** 2)
            - 0.3 * np.exp(-((R - 151.0) / 1.6) ** 2) * np.exp(-(X / 7.0) ** 2))
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


def ear_mesh(side):
    """Small ear, mostly hidden by the hair; peeks out on the front view. A
    thin oval plate whose front edge tucks into the side of the head and whose
    back edge flares out a little, with a shallow bowl (concha) on its outer
    face, so it reads as an ear and not a button."""
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=1.0)
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


NECK_SHADE_ROW = 166.0    # neck rings above this row are drawn in the shade tone


def neck_mesh():
    """Top of the neck, from inside the head down to just above the choker."""
    # row, depth centre [col], half-width, half-depth [px]: the top flares
    # back into the base of the skull instead of meeting it as a plain tube
    # the throat also leans forward into the jaw's underside as a soft fillet
    rows = [(138.0, 288.5, 16.0, 16.0), (148.0, 286.0, 15.4, 16.0), (154.0, 285.6, 15.1, 15.0),
            (158.0, 286.2, 14.9, 13.6), (162.0, 286.8, 14.8, 12.7), (168.0, 287.8, 14.8, 12.6),
            (174.0, 289.5, 14.8, 12.6)]
    rings = [common.ellipse_ring((HEAD_DX, yc(cy), zr(r)), w / PPM, d / PPM, 24) for r, cy, w, d in rows]
    return common.loft(rings, closed=True, cap_start=True, cap_end=False)


def build(col):
    skin = common.toon_material('skin')
    pixels = face_texture_pixels()
    face = face_material(pixels)

    head = common.new_object(col, 'head_face', head_mesh(), [face])
    head.data.shade_smooth()
    set_face_uv(head.data)
    set_eye_region(head.data, pixels)
    set_shading_normals(head.data, smooth_normals())
    common.add_outline(head)

    for side, nm in ((1, 'head_ear_L'), (-1, 'head_ear_R')):
        ear = common.new_object(col, nm, ear_mesh(side), [skin])
        common.shade_smooth(ear, 80)
        common.add_outline(ear)

    neck = common.new_object(col, 'head_neck', neck_mesh(), [skin])
    neck.data.shade_smooth()
    # the sheet draws only a band under the chin in the shade colour (cast
    # shadows are off): point the upper neck's normals away from the key light
    # and keep the real normals near the choker, so the lit/shade edge sits
    # a few px below the jaw and the neck meets the body's neck lit.
    away = Vector((0.35, 0.8, -0.5)).normalized()
    z_edge = zr(NECK_SHADE_ROW)
    neck.data.normals_split_custom_set_from_vertices(
        [away if v.co.z > z_edge else v.normal.copy() for v in neck.data.vertices])
    common.add_outline(neck)
    return col
