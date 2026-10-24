"""Petticoat: peach-pink multi-tier ruffles peeking out below the skirt hem.

Objects:
  petticoat_core    low-res inner cone from the hips down; hidden by the skirt.
  petticoat_tier0-3 concentric ruffle tiers, outermost first. The outer ones
                    show where the skirt's sides are lifted; each tier further
                    in hangs lower, down to the layer seen between the legs.

Each tier is a fluted (gathered) sheet: the radius dips between folds and
the dip deepens towards the hem, so the frill has volume and its outline
waves. The hem is cut into rounded petal-like scallops.

The pink band's bottom outline is a bowl, lowest at the centre and rising
towards the sides (and higher at the back than the front in the side view).
It was measured on ref/{front,side,back}.png (panel rows, HEM_FRONT /
HEM_SIDE) instead of using the single spec.L['petticoat_hem_z'] landmark,
which only gives one height.
"""
import math

import bmesh
from mathutils import Vector

from levi import common, spec

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
SCALLOP_DEPTH = 5 * PX
# Scallop tips only touch the hem line at their centres; drop the line a
# little so the averaged scalloped outline sits on the measured one.
HEM_DROP = 3
FLUTE_DEPTH = 0.14     # radial dip between flutes at the hem (fraction of radius)
PETALS_PER_FLUTE = 3   # hem scallops per gathered fold

# Concentric ruffle tiers, outermost first. The sheet's bottom outline is a
# bowl: the outer ruffles (lifted with the skirt's sides) end highest and
# every tier further in hangs lower, down to the layer seen between the legs.
# (name, radius fraction rho of the hem outline, height px, flutes,
#  vertices per scallop, rings, normal up-bias)
# up-bias tilts a tier's shading normals (+ up, - down). The flared tiers
# already read as lit pink with shade in the fold valleys, so they keep plain
# normals; the innermost layer, which is in the skirt's shadow on the sheet,
# is tilted down so it mostly takes the shade tone.
TIERS = (
    ('petticoat_tier0', 1.00, 50, 24, 4, 4, 0.00),
    ('petticoat_tier1', 0.82, 46, 20, 3, 4, 0.00),
    ('petticoat_tier2', 0.62, 44, 16, 3, 4, 0.00),
    ('petticoat_tier3', 0.42, 42, 12, 3, 4, -0.50),
)
TOP_SCALE = 0.80       # tier radius at its top, relative to its hem radius


def _interp(table, x):
    if x <= table[0][0]:
        return table[0][1]
    for (x0, y0), (x1, y1) in zip(table, table[1:]):
        if x <= x1:
            t = (x - x0) / (x1 - x0)
            return y0 + (y1 - y0) * t
    return table[-1][1]


def _ellipse(phi, scale=1.0):
    """Hem outline point (x, y) at angle phi (0 = +X, -pi/2 = front)."""
    s = math.sin(phi)
    d = FRONT_D if s < 0 else BACK_D
    return (scale * HALF_W * PX * math.cos(phi), scale * d * PX * s)


def hem_z(rho, phi):
    """World z of the hem of the tier at radius fraction rho, angle phi.

    The hem point projects onto front-view column |x| and side-view column y.
    The measured bottom outline of each view is the lowest ruffle point over
    that column, so a hem point may hang no lower than either outline: take
    the higher of the two. Inner tiers (smaller rho) reach the lower centre
    of the bowl-shaped outline, outer tiers its lifted sides.
    """
    x, y = _ellipse(phi, rho)
    row = min(_interp(HEM_FRONT, abs(x) / PX), _interp(HEM_SIDE, y / PX))
    return spec.px_to_z(row + HEM_DROP)


def _scallop(t):
    """Petal profile along one scallop, t in [0, 1): 0 at the notch, 1 at the tip."""
    return math.sin(math.pi * t) ** 0.7


def _tier(col, mat, idx, name, rho, height_px, flutes, seg, rings, up_bias):
    petal_n = PETALS_PER_FLUTE * seg
    n = flutes * petal_n
    height = height_px * PX
    # Alternate tiers by half a fold so their flutes interleave as on the sheet.
    phase = (math.pi / flutes) * (idx % 2)
    loops = []
    for k in range(rings):
        t = k / (rings - 1)            # 0 = top, 1 = hem
        ease = t * t * (3 - 2 * t)
        loop = []
        for i in range(n):
            phi = 2 * math.pi * i / n + phase - math.pi / 2
            flute = 0.5 - 0.5 * math.cos(2 * math.pi * i / petal_n)   # 0 at fold ridge, 1 between
            scale = rho * (TOP_SCALE + (1.0 - TOP_SCALE) * ease) * (1.0 - FLUTE_DEPTH * t * flute)
            x, y = _ellipse(phi, scale)
            z = hem_z(rho, phi) + height * (1.0 - t)
            if k == rings - 1:
                # Scallop tips sit on the hem line, notches rise.
                z += SCALLOP_DEPTH * (1.0 - _scallop((i % seg) / seg))
                # Folds pull the hem up a little between flutes.
                z += 3 * PX * flute
            elif k == rings - 2:
                # Slight outward curl just above the hem for ruffle volume.
                x *= 1.015
                y *= 1.015
            loop.append(Vector((x, y, z)))
        loops.append(loop)
    return _finish(col, mat, name, loops, up_bias)


def _finish(col, mat, name, loops, up_bias=0.0):
    """Loft the rings into a sheet object with toon shading normals + outline.

    recalc_face_normals is ambiguous on an open tube, so orientation is set
    explicitly: faces point INWARD (towards the body axis). add_outline's
    Solidify flips all normals of its result, so an open sheet must start
    out facing away from the viewer for the hull to land outside and the
    sheet itself to stay visible; with outward faces the hull covers the
    whole frill in a flat tone (verified in render). EEVEE shades the sheet
    from its camera-facing side, so the lighting still reads as outward.
    """
    bm = common.loft(loops, closed=True)
    flip = [f for f in bm.faces
            if f.normal.dot(Vector((f.calc_center_median().x, f.calc_center_median().y, 0.0))) > 0.0]
    if flip:
        bmesh.ops.reverse_faces(bm, faces=flip)
    obj = common.new_object(col, name, bm, [mat])
    common.shade_smooth(obj, 60.0)
    if up_bias:
        # Vertex normals point inward (-n_out); the shading normal is the
        # outward one tilted up: n = -(n_out + up) = vn - up.
        me = obj.data
        up = Vector((0.0, 0.0, up_bias))
        me.normals_split_custom_set_from_vertices([(v.normal - up).normalized() for v in me.vertices])
    common.add_outline(obj)
    return obj


def _core(col, mat):
    """Hidden inner cone from the hips down into the top of the outer tier."""
    n = 32
    _, rho0, height0 = TIERS[0][:3]
    top = common.ellipse_ring((0, L['waist_center_y'] * 0.6, L['hip_z']), L['waist_half_w'] * 1.40, 0.065, n)
    mid_z = (L['hip_z'] + spec.px_to_z(530)) / 2
    mid = common.ellipse_ring((0, 0, mid_z), HALF_W * PX * 0.50, FRONT_D * PX * 0.55, n)
    bot = []
    for i in range(n):
        phi = 2 * math.pi * i / n
        x, y = _ellipse(phi, rho0 * TOP_SCALE * 0.985)
        # Tuck a few px below the outer tier's top edge so no gap shows.
        bot.append(Vector((x, y, hem_z(rho0, phi) + (height0 - 6) * PX)))
    return _finish(col, mat, 'petticoat_core', [top, mid, bot])


def build(col):
    mat = common.toon_material('petticoat')
    _core(col, mat)
    for idx, tier in enumerate(TIERS):
        _tier(col, mat, idx, *tier)
