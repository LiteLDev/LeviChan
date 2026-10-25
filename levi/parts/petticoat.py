"""Petticoat: peach-pink tiers of puffy scalloped ruffles below the skirt hem.

Objects:
  petticoat_core    low-res inner cone from the hips down; hidden by the skirt.
  petticoat_tier0-2 ruffle tiers, outermost first. The two outer ones show
                    where the skirt's sides are lifted; the innermost hangs
                    lowest, beside the legs.

Each tier is a short frill of rounded puffs, one puff per hem scallop,
gathered in threes into bell flounces. Around the tier the hem outline
bulges out in a rounded arc per puff (notches between, deeper folds between
bells), and the hem rises at the notches, so every scallop is a clean
rounded petal. The puff swells to a belly just above the hem, the lip tucks
back in under it and folds up inside, so the hem is a fold and the outline
hull draws a line along every scallop. Shading normals are set per ring:
the top of a tier (seen just below the hem of the tier outside it) and the
tucked-in lip face down and take the shade tone, the belly is lit. In the
cel ramp that gives each scallop a light petal with a darker band above and
a shade crescent along its rounded edge, and the side of each puff away
from the key light falls into shade too, like the frilly flower edge on the
sheet. The scallops are about 28 panel px wide with 7 vertices each, so
the hem outline is smooth instead of aliasing into a fuzzy fringe.

The pink band's bottom outline is a bowl, lowest at the centre and rising
towards the sides (and higher at the back than the front in the side view).
It was measured on ref/{front,side,back}.png (panel rows, HEM_FRONT /
HEM_SIDE) instead of using the single spec.L['petticoat_hem_z'] landmark,
which only gives one height.
"""
import bisect
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
SCALLOP_DEPTH = 6 * PX   # how far the hem rises at a notch between puffs
# Scallop tips only touch the hem line at their centres; drop the line a
# little so the averaged scalloped outline sits on the measured one.
HEM_DROP = 2
SEG = 7                  # vertices per puff (one puff = one scallop)
# Puffs are gathered in threes into hanging bells: between two bells the
# fabric folds in (FLUTE_DIP x the puff depth) up the whole tier and the hem
# rises FLUTE_RISE, so the frill reads as separate bell flounces with a
# scalloped edge, and the fold's side away from the light takes a vertical
# shade strip.
FLUTE = 3
FLUTE_DIP = 0.7
FLUTE_RISE = 5 * PX
TOP_SCALE = 0.80         # outer tiers' size at their top, relative to the hem outline
PUFF_NORMAL = 0.35       # how far shading normals follow the puffs (0 = smooth outline)
DENSE = 1440            # samples of the dense hem outline (arc-length resampling)

# Ruffle tiers, outermost first. The sheet's bottom outline is a bowl: the
# outer ruffles (lifted with the skirt's sides) end highest and the tiers
# further in hang lower. (name, hem outline (half width, front depth, back
# depth px, superellipse exponent), centre lift (x0, x1) px, height px,
# puffs, puff depth px, belly elevation deg)
# Belly elevation is the tilt of the lit band's shading normal (+ up).
#
# Under the middle of the skirt, front and back, the sheet shows the legs
# from the skirt hem down. Every tier would hang in front of them there, so
# within x0 px of the midline (front view) a tier's hem rises to LIFT_ROW,
# behind the skirt's centre hem (spec skirt_hem_z, row 598), easing back to
# the measured bowl by x1. The innermost tier is boxy (exponent 3) and
# hangs straight (top as wide as the hem): its flat sides reach towards the
# low middle of the side view's bottom outline and show beside the legs in
# the front view.
# Rigging: every tier stays well clear of the leg bones (leg_center_x 43 +
# thigh_half_w 22; the inner tier's sides are >75 px from the leg axis), so
# the skinning weights it to the skirt chains like the skirt itself. A layer
# hugging or passing between the thighs gets split leg weights and tears
# when one leg is raised (rig_check stretch x4-x9 in experiments), so the
# sheet's shadowed layer between the legs is left out.
TIERS = (
    ('petticoat_tier0', (HALF_W, FRONT_D, BACK_D, 2.0), (60, 78), 50, TOP_SCALE, 45, 9.0, -20.0),
    ('petticoat_tier1', (0.76 * HALF_W, 0.76 * FRONT_D, 0.76 * BACK_D, 2.0), (60, 78), 46, TOP_SCALE, 36, 8.0, -20.0),
    ('petticoat_tier2', (148, 105, 105, 3.0), (60, 78), 44, 1.0, 27, 7.0, -20.0),
)
LIFT_ROW = 585   # high enough that no lifted sliver peeks out under the skirt
# Rings from top to hem: (height above the hem as a fraction of the tier
# height, size scale (relative to the hem outline), puff amount, shading
# elevation deg or None for the tier's belly elevation). Below -56 deg the
# key light falls under toon.RAMP_THRESHOLD and the ring takes the shade.
# The last ring folds the lip back up inside, so the hem is a fold rather
# than an open border and the outline hull draws a line along each scallop.
RINGS = (
    (1.00, None, 0.25, -90.0),
    (0.14, 1.00, 1.00, None),
    (0.00, 0.95, 1.00, -70.0),
    (0.10, 0.90, 1.00, -70.0),
)


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


def _ellipse(phi, scale=1.0, dims=(HALF_W, FRONT_D, BACK_D)):
    """Point (x, y) in metres on a hem ellipse at angle phi (0 = +X, -pi/2 = front).

    dims: (half width, front depth, back depth) in panel px.
    """
    s = math.sin(phi)
    d = dims[1] if s < 0 else dims[2]
    return (scale * dims[0] * PX * math.cos(phi), scale * d * PX * s)


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


def _outline(shape, n, phase):
    """n points (px) evenly spaced by arc length on the hem outline, offset by
    `phase` spacings from the front centre, with their outward unit normals."""
    pts = _dense_outline(shape)
    m = len(pts)
    cum = [0.0]
    for i in range(m):
        a, b = pts[i], pts[(i + 1) % m]
        cum.append(cum[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    total = cum[-1]
    res = []
    for i in range(n):
        s = ((i + phase) / n * total) % total
        j = min(bisect.bisect_right(cum, s) - 1, m - 1)
        a, b = pts[j], pts[(j + 1) % m]
        t = (s - cum[j]) / max(cum[j + 1] - cum[j], 1e-9)
        tx, ty = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(tx, ty) or 1.0
        res.append(((a[0] + tx * t, a[1] + ty * t), (ty / ln, -tx / ln)))
    return res


def hem_z(x, y, lift=None):
    """World z of a tier's hem at the hem-outline point (x, y) (panel px).

    The hem point projects onto front-view column |x| and side-view column y.
    The measured bottom outline of each view is the lowest ruffle point over
    that column, so a hem point may hang no lower than either outline: take
    the higher of the two. Inner tiers reach the lower centre of the
    bowl-shaped outline, outer tiers its lifted sides. lift = (x0, x1) raises
    the hem near the midline to LIFT_ROW (see TIERS).
    """
    ax = abs(x)
    row = min(_interp(HEM_FRONT, ax), _interp(HEM_SIDE, y))
    if lift and row > LIFT_ROW:
        row += (LIFT_ROW - row) * (1.0 - _smoothstep(lift[0], lift[1], ax))
    return spec.px_to_z(row + HEM_DROP)


def _puff(u):
    """Rounded puff profile across one scallop, u in [0, 1): 0 at the notch, 1 at the crown."""
    return math.sin(math.pi * u) ** 0.5


def _tier(col, idx, name, shape, lift, height_px, top_scale, puffs, depth_px, belly_deg):
    if puffs % FLUTE:
        raise ValueError(f'{name}: puffs must be a multiple of FLUTE ({FLUTE})')
    n = puffs * SEG
    fn = FLUTE * SEG
    height = height_px * PX
    # Alternate tiers by half a flute so the bells interleave as on the sheet.
    hem = _outline(shape, n, 0.5 * fn * (idx % 2))
    hems = [hem_z(p[0], p[1], lift) for p, _ in hem]
    loops, elev = [], []
    for h, scale, amount, e in RINGS:
        scale = top_scale if scale is None else scale
        loop = []
        for i, ((bx, by), (nx, ny)) in enumerate(hem):
            p = _puff((i % SEG) / SEG)
            f = 1.0 - _puff((i % fn) / fn)      # 1 in the fold between two bells
            # The puff crown reaches the hem outline; notches dip in, and
            # the folds between bells run up the whole tier.
            dip = depth_px * amount * ((1.0 - p) + FLUTE_DIP * f)
            x = (scale * bx - nx * dip) * PX
            y = (scale * by - ny * dip) * PX
            z = hems[i] + height * h + SCALLOP_DEPTH * (1.0 - p) + FLUTE_RISE * f
            loop.append(Vector((x, y, z)))
        loops.append(loop)
        elev.append(math.radians(belly_deg if e is None else e))
    # Shading normals: the horizontal normal of each ring's puffed outline
    # (so the steep side of a puff away from the light shades), partly
    # relaxed towards the smooth hem outline's normal (PUFF_NORMAL) so the
    # puffs seen edge-on at the sides don't streak, then tilted to the
    # ring's elevation. The rings run counter-clockwise, so (t.y, -t.x)
    # points outward.
    normals = []
    up = Vector((0.0, 0.0, 1.0))
    for loop, e in zip(loops, elev):
        for i in range(n):
            t = loop[(i + 1) % n] - loop[i - 1]
            pn = Vector((t.y, -t.x, 0.0)).normalized()
            on = Vector((hem[i][1][0], hem[i][1][1], 0.0))
            hn = (on.lerp(pn, PUFF_NORMAL)).normalized()
            normals.append(hn * math.cos(e) + up * math.sin(e))
    return _finish(col, common.toon_material('petticoat'), name, loops, normals)


def _finish(col, mat, name, loops, normals=None):
    """Loft the rings into a sheet object with toon shading normals + outline.

    recalc_face_normals is ambiguous on an open tube, so orientation is set
    explicitly: faces point OUTWARD (away from the body axis). The loft's
    winding is consistent, through the folded hem too, so the whole sheet is
    flipped or kept by the faces' overall direction. Outward faces put the
    outline hull on the outside of the hem fold, so it draws a line along
    every scallop (with inward faces the hull sits inside the fold and the
    hem gets no line); the hull's backface culling keeps it off the fill.

    normals: optional outward shading normal per vertex (ring-major, the
    order of `loops`).
    """
    bm = common.loft(loops, closed=True)
    out = sum(f.normal.dot(Vector((c.x, c.y, 0.0))) * f.calc_area()
              for f in bm.faces for c in (f.calc_center_median(),))
    if out < 0.0:
        bmesh.ops.reverse_faces(bm, faces=list(bm.faces))
    obj = common.new_object(col, name, bm, [mat])
    common.shade_smooth(obj, 60.0)
    if normals:
        obj.data.normals_split_custom_set_from_vertices([v.normalized() for v in normals])
    common.add_outline(obj)
    return obj


def _core(col, mat):
    """Hidden inner cone from the hips down into the top of the outer tier."""
    n = 32
    dims0, lift0, height0, top0 = TIERS[0][1:5]
    top = common.ellipse_ring((0, L['waist_center_y'] * 0.6, L['hip_z']), L['waist_half_w'] * 1.40, 0.065, n)
    mid_z = (L['hip_z'] + spec.px_to_z(530)) / 2
    mid = common.ellipse_ring((0, 0, mid_z), HALF_W * PX * 0.50, FRONT_D * PX * 0.55, n)
    bot = []
    for i in range(n):
        phi = 2 * math.pi * i / n
        x, y = _ellipse(phi, top0 * 0.985, dims0[:3])
        hx, hy = _ellipse(phi, 1.0, dims0[:3])
        # Tuck a few px below the outer tier's top edge so no gap shows.
        bot.append(Vector((x, y, hem_z(hx / PX, hy / PX, lift0) + (height0 - 6) * PX)))
    return _finish(col, mat, 'petticoat_core', [top, mid, bot])


def build(col):
    _core(col, common.toon_material('petticoat'))
    for idx, tier in enumerate(TIERS):
        _tier(col, idx, *tier)
