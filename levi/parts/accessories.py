"""Head and neck accessories: leaf "ears" with flowers, beaded vine choker,
halter strings crossing over the upper chest.

Everything is positioned against the reference panels (re-measured green
masks / crops of ref/{front,side,back}.png). Exceptions, as local constants
(no other part's objects are read): the choker loop and the halter depths
are set so the strings rest on the body's skin, and the flower depth clears
the front hair locks (see FLOWER).
Coordinates below are given in reference pixels and converted with P():
    x  = front-view column offset from the panel centre (+ = character's left)
    y  = side-view column offset from the panel centre (- = forward)
    row = panel row (z = (951 - row) / 643)
The character-left (+X) side is described; the right side is its mirror.
"""
import math

import bmesh
from mathutils import Vector

from .. import spec
from ..common import GRAD_ATTR, add_outline, new_object, shade_smooth, toon_material

PX = 1.0 / spec.PX_PER_M


def P(x, y, row):
    """Reference pixels (front col offset, side col offset, row) -> world point."""
    return Vector((x * PX, y * PX, spec.px_to_z(row)))


def V(x, y, z):
    """Direction given in the same pixel axes (z up)."""
    return Vector((x, y, z)).normalized()


def _mirror(v, sx):
    return Vector((v.x * sx, v.y, v.z))


# ------------------------------------------------------------------ leaves
# (base, tip, width-direction hint, full width px, facing hint)
# Leaf A: the taller inner leaf; leaf B: the larger outer leaf that fans out
# sideways and backwards (its tip is behind the ear line in the side view).
LEAVES = (
    dict(base=(47, -29, 73), tip=(66, -12, 34), wdir=(0.7, 0.7, 0.0), width=26.0,
         face=(0.6, -0.7, 0.3), fold=0.6, bend=-0.10, curl=0.0),
    dict(base=(57, -20, 82), tip=(87, 5, 45), wdir=(0.7, 0.7, 0.0), width=26.0,
         face=(0.6, -0.7, 0.3), fold=0.6, bend=-0.10, curl=-0.06),
)
LEAF_NU = 10          # rings along the leaf (incl. base/tip points)
LEAF_NV = 7           # samples across the top surface (odd: midrib vertex)
LEAF_THICK = 0.0011   # half thickness at the midrib (m)

# The sheet draws the flower face-on in both front and side views, which no
# single 3D spot can satisfy: the bangs/cheek locks at x~50 px reach y~-95 px,
# so a flower at the leaf-base depth (y~-40) is hidden in the front view. It is
# placed just in front of those locks (front view priority), facing the
# front/side diagonal so it also reads in the side view (on the temple).
FLOWER = dict(center=(51, -98, 70), normal=(0.65, -0.7, 0.3), radius=12.5)
FLOWER_SEG = 30
FLOWER_PETALS = 5

# Choker: tilted elliptical loop (front lower than back), beaded tube. The loop
# follows the neck section (centre y -31, half-axes ~14.6 x 15.2 px at rows
# 166-178) offset by ~2 px so the tube sits on the skin all round.
CHOKER = dict(center=(0, -31.0, 172.0), rx=16.6, ry=17.2, tilt=6.0,
              r=1.4, bead=1.3, seg=60, period=3, sides=6)

# Halter strap (character-left): it leaves the choker tube on its side-back
# (STRAP_THETA on the choker loop), runs over the shoulder slope (STRAP[1:4])
# and down the chest to the bodice top. x/row follow the front reference strings; the depth (y) rests
# the string on the body's skin (measured on the round-2 body; ~1.2 px of
# clearance from skin to string axis, i.e. the string touches without sinking).
STRAP_THETA = 0.45
STRAP = ((16.8, -26, 180), (20.5, -33, 183), (22.6, -42.5, 187), (24, -48, 191.5),
         (26.3, -48.3, 197), (31.3, -52.4, 210), (36.3, -57.1, 222), (41, -58.9, 233),
         (45, -59.2, 243))
# X strand: branches off the left strap at the upper chest (between STRAP[3]
# and STRAP[4]) and
# runs straight (in the front view) to the right strap near the bodice top.
CROSS = tuple((x, y, 193 + (24.9 - x) * 40.0 / 66.4) for x, y in (
    (24.9, -48.1), (12, -48.3), (0, -52.5), (-14, -56.5), (-28, -59.4), (-41.5, -58.8)))
CROSS_LIFT = 0.003    # forward offset of one strand at the crossing (m)
STRING_R = 0.0014
STRING_LINE = 0.0006
VEIN_R = 0.00055


# ------------------------------------------------------------------ helpers
def _catmull(points, per_seg):
    """Catmull-Rom resample of a polyline (endpoints kept)."""
    pts = [Vector(p) for p in points]
    ext = [pts[0] * 2 - pts[1]] + pts + [pts[-1] * 2 - pts[-2]]
    out = []
    for i in range(1, len(ext) - 2):
        p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
        for k in range(per_seg):
            t = k / per_seg
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t * t * t))
    out.append(pts[-1])
    return out


def _write_grad(obj, values):
    me = obj.data
    attr = me.attributes.get(GRAD_ATTR) or me.attributes.new(GRAD_ATTR, 'FLOAT', 'POINT')
    for i, v in enumerate(values):
        attr.data[i].value = max(0.0, min(1.0, v))


def _leaf(bm, grads, base, tip, wdir, width, face, fold, bend, curl):
    """Thick, folded, slightly bent leaf blade added to `bm`.

    Lens-shaped cross-section (thickest on the midrib, sharing the rim);
    the two halves are raised along the facing normal so the blade folds
    along the midrib and the halves pick up different toon tones.
    Returns the midrib polyline (on the upper surface) for the vein.
    """
    axis = tip - base
    length = axis.length
    t = axis / length
    s = (wdir - t * t.dot(wdir)).normalized()
    n = t.cross(s)
    if n.dot(face) < 0:
        n = -n
    hw_max = width * PX / 2

    def frame(u):
        # midline with a gentle backward bend and a sideways curl of the tip
        return (base + t * (length * u) + n * (bend * length * u * u)
                + s * (curl * length * u * u))

    vs = [k / (LEAF_NV - 1) * 2 - 1 for k in range(LEAF_NV)]
    rings = []
    midrib = [frame(0.0)]
    for i in range(1, LEAF_NU - 1):
        u = i / (LEAF_NU - 1)
        hw = hw_max * math.sin(math.pi * u ** 0.8) ** 0.75
        th = LEAF_THICK * math.sin(math.pi * u) ** 0.5
        m = frame(u)
        top, bot = [], []
        for v in vs:
            lift = n * (fold * hw * abs(v) ** 1.3)
            p = m + s * (hw * v) + lift
            cap = th * (1 - v * v)
            top.append(p + n * cap)
            bot.append(p - n * cap)
        ring = top + bot[-2:0:-1]
        rv = vs + vs[-2:0:-1]
        rings.append(([bm.verts.new(p) for p in ring], u, rv))
        midrib.append(m + n * (th + 0.0004))
    midrib.append(frame(1.0))
    vb = bm.verts.new(frame(0.0))
    vt = bm.verts.new(frame(1.0))
    for vv, u, rv in rings:
        # darker green toward the stem
        grads.extend([0.6 * (1 - u) ** 2] * len(rv))
    grads.extend([0.6, 0.0])
    nr = len(rings[0][0])
    for (a, _, _), (b, _, _) in zip(rings, rings[1:]):
        for j in range(nr):
            k = (j + 1) % nr
            bm.faces.new((a[j], a[k], b[k], b[j]))
    first, last = rings[0][0], rings[-1][0]
    for j in range(nr):
        k = (j + 1) % nr
        bm.faces.new((vb, first[k], first[j]))
        bm.faces.new((vt, last[j], last[k]))
    return midrib


def _basis(normal):
    """Two unit vectors spanning the plane perpendicular to `normal` (a points up)."""
    up = Vector((0, 0, 1)) if abs(normal.z) < 0.95 else Vector((0, 1, 0))
    a = (up - normal * normal.dot(up)).normalized()
    return a, normal.cross(a)


def _flower(bm, center, normal, radius, cup=0.22, thick=0.0012):
    """Five-petal flat flower (front, rim and back), petals notched to the centre."""
    a, b = _basis(normal)
    R = radius * PX

    def rad(phi):
        return R * (0.42 + 0.58 * abs(math.cos(FLOWER_PETALS * phi / 2)) ** 0.55)

    def pt(phi, f, z):
        r = rad(phi) * f
        return center + (a * math.cos(phi) + b * math.sin(phi)) * r + normal * (cup * R * f * f + z)

    fracs = (0.35, 0.7, 1.0)
    phis = [2 * math.pi * k / FLOWER_SEG for k in range(FLOWER_SEG)]
    rings = [[bm.verts.new(pt(p, f, 0.0)) for p in phis] for f in fracs]
    back = [bm.verts.new(pt(p, 1.0, -thick)) for p in phis]
    c_front = bm.verts.new(center + normal * 0.0002)
    c_back = bm.verts.new(center - normal * (thick + 0.0004))
    n = FLOWER_SEG
    for j in range(n):
        k = (j + 1) % n
        bm.faces.new((c_front, rings[0][j], rings[0][k]))
        for r0, r1 in zip(rings, rings[1:]):
            bm.faces.new((r0[j], r1[j], r1[k], r0[k]))
        bm.faces.new((rings[-1][j], back[j], back[k], rings[-1][k]))
        bm.faces.new((c_back, back[k], back[j]))


def _dome(bm, center, normal, radius, height, seg=8):
    """Small closed dome (flower centre)."""
    a, b = _basis(normal)
    rings = []
    for f, h in ((1.0, 0.0), (0.7, 0.75)):
        rings.append([bm.verts.new(center + (a * math.cos(2 * math.pi * k / seg)
                                             + b * math.sin(2 * math.pi * k / seg)) * radius * f
                                   + normal * height * h) for k in range(seg)])
    top = bm.verts.new(center + normal * height)
    bot = bm.verts.new(center - normal * height * 0.3)
    for j in range(seg):
        k = (j + 1) % seg
        bm.faces.new((rings[0][j], rings[0][k], rings[1][k], rings[1][j]))
        bm.faces.new((rings[1][j], rings[1][k], top))
        bm.faces.new((rings[0][k], rings[0][j], bot))


def _tube(bm, points, radii, sides, loop_center=None):
    """Tube along `points` built straight into `bm`.

    loop_center=None: open path with flat caps. Otherwise the path is a closed
    loop around loop_center (used to orient the cross-section, so beads bulge
    evenly all round) and the tube wraps around with no caps.
    """
    n = len(points)
    closed = loop_center is not None
    rings = []
    prev = None
    for i, p in enumerate(points):
        if closed:
            tng = (points[(i + 1) % n] - points[i - 1]).normalized()
            side = p - loop_center
        else:
            tng = (points[min(i + 1, n - 1)] - points[max(i - 1, 0)]).normalized()
            side = prev if prev is not None else tng.orthogonal()
        side = (side - tng * side.dot(tng)).normalized()
        prev = side
        upv = tng.cross(side)
        rings.append([bm.verts.new(p + (side * math.cos(2 * math.pi * k / sides)
                                        + upv * math.sin(2 * math.pi * k / sides)) * radii[i])
                      for k in range(sides)])
    for i in range(n if closed else n - 1):
        a, b = rings[i], rings[(i + 1) % n]
        for j in range(sides):
            k = (j + 1) % sides
            bm.faces.new((a[j], a[k], b[k], b[j]))
    if not closed:
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])


# ------------------------------------------------------------------ build
def _build_side(col, sx):
    tag = 'L' if sx > 0 else 'R'
    # leaves
    bm = bmesh.new()
    grads = []
    midribs = []
    for lf in LEAVES:
        base = _mirror(P(*lf['base']), sx)
        tip = _mirror(P(*lf['tip']), sx)
        wdir = _mirror(V(*lf['wdir']), sx)
        face = _mirror(V(*lf['face']), sx)
        midribs.append(_leaf(bm, grads, base, tip, wdir, lf['width'], face,
                             lf['fold'], lf['bend'], lf['curl']))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    leaves = new_object(col, f'acc_leaves_{tag}', bm, [toon_material('leaf', gradient='green')])
    _write_grad(leaves, grads)
    shade_smooth(leaves, 60)
    add_outline(leaves)

    # midrib veins: thin dark tubes on the upper surface
    bm = bmesh.new()
    for mr in midribs:
        pts = mr[1:-1]
        _tube(bm, pts, [VEIN_R] * len(pts), 4)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    veins = new_object(col, f'acc_leaf_veins_{tag}', bm, [toon_material('green')])
    shade_smooth(veins, 80)
    add_outline(veins, width=0.0003)

    # flower
    c = _mirror(P(*FLOWER['center']), sx)
    nrm = _mirror(V(*FLOWER['normal']), sx)
    bm = bmesh.new()
    _flower(bm, c, nrm, FLOWER['radius'])
    npet = len(bm.faces)
    _dome(bm, c + nrm * (0.06 * FLOWER['radius'] * PX), nrm, FLOWER['radius'] * PX * 0.26, 0.0016)
    for i, f in enumerate(bm.faces):
        f.material_index = 0 if i < npet else 1
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    flower = new_object(col, f'acc_flower_{tag}', bm,
                        [toon_material('flower'), toon_material('flower', gradient='leaf')])
    # centre: pale yellow-green (white blended toward leaf green)
    centre_verts = set()
    for p in flower.data.polygons:
        if p.material_index == 1:
            centre_verts.update(p.vertices)
    _write_grad(flower, [0.5 if i in centre_verts else 0.0 for i in range(len(flower.data.vertices))])
    shade_smooth(flower, 50)
    add_outline(flower)


def _choker_ring(theta):
    """Point on the choker's centre loop (reference px); theta=0 at +X, -pi/2 front."""
    ch = CHOKER
    _, cy, row = ch['center']
    # front (sin<0) sits lower than the back
    return (ch['rx'] * math.cos(theta), cy + ch['ry'] * math.sin(theta),
            row - ch['tilt'] * math.sin(theta))


def _choker(col):
    ch = CHOKER
    pts, radii = [], []
    for i in range(ch['seg']):
        pts.append(P(*_choker_ring(2 * math.pi * i / ch['seg'])))
        bead = 1.0 if i % ch['period'] == 0 else 0.0
        radii.append((ch['r'] + ch['bead'] * bead) * PX)
    bm = bmesh.new()
    _tube(bm, pts, radii, ch['sides'], loop_center=P(*ch['center']))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    obj = new_object(col, 'acc_choker', bm, [toon_material('green')])
    shade_smooth(obj, 70)
    add_outline(obj, width=0.0012)


def _add_string(bm, path):
    pts = _catmull(path, 2)
    _tube(bm, pts, [STRING_R] * len(pts), 4)


def _strings(col):
    bm = bmesh.new()
    for sx in (1, -1):
        # the strap starts inside the choker tube, on its side-back
        strap = [_choker_ring(STRAP_THETA)] + list(STRAP)
        _add_string(bm, [_mirror(P(*p), sx) for p in strap])
        cross = [_mirror(P(*p), sx) for p in CROSS]
        if sx > 0:
            # this strand passes over the other one where they cross
            cross = [p + Vector((0, -CROSS_LIFT * math.exp(-(p.x / (12 * PX)) ** 2), 0))
                     for p in cross]
        _add_string(bm, cross)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    obj = new_object(col, 'acc_halter', bm, [toon_material('green')])
    shade_smooth(obj, 80)
    add_outline(obj, width=STRING_LINE)


def build(col):
    for sx in (1, -1):
        _build_side(col, sx)
    _choker(col)
    _strings(col)
