"""Head and neck accessories: leaf "ears" with flowers, beaded vine choker,
halter strings crossing over the upper chest.

Everything is positioned against the reference panels (re-measured green
masks / crops of ref/{front,side,back}.png). Exceptions, as local constants
(no other part's objects are read): the choker loop and the halter depths
are set so the strings rest on the body's skin, and the flower and leaf
mount sit on the hair surface (see FLOWER).
Coordinates below are given in reference pixels and converted with P():
    x  = front-view column offset from the panel centre (+ = character's left)
    y  = side-view column offset from the panel centre (- = forward)
    row = panel row (z = (951 - row) / 643)
The character-left (+X) side is described; the right side is its mirror.
"""
import math

import bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.interpolate import poly_3d_calc

from .. import spec
from ..common import GRAD_ATTR, add_outline, new_object, shade_smooth, toon_material
# Data / pure functions only (CLAUDE.md "Part rules"): body.build_torso rebuilds
# the torso surface from body's tables into a private bmesh, and bodice's
# profile / neckline functions give the rim the straps tuck under.
from . import bodice as _bodice
from . import body as _body

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
# Both leaves grow from one mount on the hair just behind the flower (sheet:
# side col ~290, row ~72). Leaf A: the taller inner leaf, close to the scalp,
# tip at front x ~60, row ~30. Leaf B: the broader outer leaf that fans out
# sideways (front x ~84-90, row ~38). Both tips sit less far back than the side
# sheet's (col ~309 / ~329) and higher: with the full backward run the blades
# were foreshortened into rounded tabs in the front and back views. The width
# directions are turned toward X so the blades fan apart.
# fold: cupping (edges raised along the facing normal), bend: backward curve of
# the tip, curl: sideways curve of the tip, twist: section roll root -> tip
# (deg), arch: mid-blade rise along the facing normal (share of the length).
LEAVES = (
    dict(base=(58, -36, 72), tip=(63, -15, 30), wdir=(0.9, 0.42, 0.05), width=27.0,
         face=(0.55, -0.75, 0.35), fold=0.25, bend=-0.08, curl=0.05, twist=8, arch=0.05),
    dict(base=(61, -32, 76), tip=(90, -4, 38), wdir=(0.66, 0.68, 0.3), width=30.0,
         face=(0.7, -0.55, 0.45), fold=0.22, bend=-0.08, curl=-0.06, twist=-14, arch=0.07),
)
LEAF_NU = 19          # rings along the leaf (incl. base/tip points), cosine-spaced
LEAF_NV = 5           # samples across the top surface (odd: midrib vertex)
LEAF_THICK = 0.0011   # half thickness at the midrib (m)
# Round 9 tried a taller ridge (1.5 mm) and a 25 % deeper cup (strengths guide
# 3.11): pairwise review (docs/pr/r9-5-trims) saw a hard light facet on the outer blade, so
# the head leaves stay as they were.
LEAF_RIDGE = 0.0009   # midrib ridge raised on the upper surface (m)

# Blade outline: u^a (1-u)^b, widest at u = a / (a + b) ~ 0.38, with a rounded
# root and a long, slightly concave taper to a sharp tip.
LEAF_SHAPE = (0.7, 1.15)


def _leaf_width(u):
    a, b = LEAF_SHAPE
    um = a / (a + b)
    return (u / um) ** a * ((1 - u) / (1 - um)) ** b

# The sheet puts the flower at the base of its leaf pair: front x ~47-49 px,
# side col ~280 (y -40), row ~68. Those two readings do not meet on the hair
# surface (at row 70 a point that far in from the silhouette lies well inside
# the head), so the flower sits on the hair surface between them, at the
# front/side diagonal, facing outward and a little forward so it reads
# face-on enough in both views.
FLOWER = dict(center=(61, -49, 69), normal=(0.78, -0.5, 0.3), radius=13.5)
FLOWER_LIFT = 0.0015  # petals held this far off the hair (no petal edge dips into it)
FLOWER_MOUNT = 0.0035  # the centre's underside runs this deep: a concealed stalk into the hair
FLOWER_PETALS = 5
PETAL_CUP = 0.10      # per-petal cup: the petal's edges rise by this share of the radius
PETAL_W = 0.5         # widest petal half width, share of the radius (neighbours overlap)
PETAL_WIDEST = 0.62   # radial position of the widest point
# m: each petal's leading edge up, trailing edge down (pinwheel overlap), times
# sqrt(s): where neighbours overlap (v ~ +/-0.66, s >= 0.25) the gap between
# their mid-surfaces exceeds their two half thicknesses, so they never cross
# (round 9 tried 1.0-1.3 mm petals with a 1.3-1.6 mm lean and a 2.5-3 mm dome: they
# added shade islands on the flower at the sheet views, so they stay at round 8)
PETAL_LEAN = 0.0011
PETAL_THICK = 0.0008  # petal thickness at the centre line
FLOWER_DOME = 0.002   # the centre stands this far proud of the petals
PETAL_S0 = 0.1        # petals start this far out (under the centre dome)
PETAL_NS = 9          # stations along a petal (incl. the base and tip points)
PETAL_NV = 5          # samples across the top surface

# Choker: tilted elliptical loop (front lower than back), beaded tube. The
# loop below is only the initial guess (centre y -31, rows 166-178): every
# point is refitted to the current neck surface (see _choker_point), with the
# bead tops resting on the skin.
# 24 small round beads (period 6 samples each) on a thin core cord; the bead
# profile (see _choker_radius) is a rounded bulge with a short waist between
# beads, so they read as separate beads rather than a serrated tube.
CHOKER = dict(center=(0, -31.0, 172.0), rx=16.6, ry=17.2, tilt=6.0,
              r=0.9, bead=1.3, seg=144, period=6, sides=7)
CHOKER_GAP = 0.0002   # skin -> bead top (m)
CHOKER_FIT_STEP = 2 * math.pi / 80   # angle between the 5 neck samples averaged per point
CHOKER_LINE = 0.0008  # outline width: a fine vine, not a serrated band

# Halter strap (character-left): it leaves the choker tube on its side-back
# (STRAP_THETA on the choker loop), runs over the shoulder slope (STRAP[1:4])
# and down the chest to the bodice top. x/row follow the front reference
# strings. The y values are only the starting guess: the build projects every
# path point onto the body's current torso surface (body.build_torso, see
# _Skin) and lifts it along the smooth surface normal, so the strings follow
# the chest whatever its depth.
STRAP_THETA = 0.45
STRAP = ((16.8, -26, 180), (20.5, -33, 183), (22.6, -42.5, 187), (24, -48, 191.5),
         (26.3, -48.3, 197), (31.3, -52.4, 210), (36.3, -57.1, 222), (41, -58.9, 233),
         (45, -59.2, 243))
# X strand: branches off the left strap at the upper chest (between STRAP[3]
# and STRAP[4]) and
# runs straight (in the front view) to the right strap near the bodice top.
CROSS = tuple((x, y, 193 + (24.9 - x) * 40.0 / 66.4) for x, y in (
    (24.9, -48.1), (12, -48.3), (0, -52.5), (-14, -56.5), (-28, -59.4), (-41.5, -58.8)))
# Cord radius. Every offset below is in terms of STRING_R, so a thicker cord still
# rests on the skin. Round 9 tried 3.4 and 4.4 mm cords (strengths guide 3.6: >= 4 mm
# to read at full-body size); pairwise review (docs/pr/r9-5-trims) preferred the finer 2.8 mm
# cords in every view (a heavy chest crossing, swollen branch junctions).
STRING_R = 0.0014
STRING_LINE = 0.0006
STRING_SIDES = 8          # round cords
STRING_PER_SEG = 3        # Catmull-Rom samples per control span
STRING_GAP = 0.0010     # skin -> string surface: centreline ~2.4 mm outside the skin
# Crossing (x = 0): the under strand drops to touch the skin and the over strand
# rides on top of it, both along the surface normal, fading out over CROSS_SIGMA.
CROSS_UNDER_GAP = 0.0002
CROSS_SIGMA = 12.0      # px
# Lower ends: the straps stop BODICE_TUCK px below the bodice neckline and settle
# onto the skin over the last TUCK_FADE px above it, so they slide in under the rim.
BODICE_TUCK = 3.0
TUCK_FADE = 4.0
STRING_TUCK_GAP = 0.0002
VEIN_R = 0.00055
PETIOLE_R = 0.0009      # leaf stalk radius where it leaves the hair
PETIOLE_IN = 2.5        # px the stalk starts inside the hair, behind the blade base
PETIOLE_SEG = 4         # stalk samples (tapering) before the blade base
VEIN_SIDES = 6


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


def _leaf(bm, grads, base, tip, wdir, width, face, fold, bend, curl, twist, arch):
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
        # midline: an S-curve (arched up through the middle, the tip bent
        # back down) and a sideways curl of the tip
        return (base + t * (length * u)
                + n * (length * (bend * u * u + arch * math.sin(math.pi * u)))
                + s * (curl * length * u * u))

    vs = [k / (LEAF_NV - 1) * 2 - 1 for k in range(LEAF_NV)]
    rings = []
    midrib = [frame(0.0)]
    for i in range(1, LEAF_NU - 1):
        u = 0.5 - 0.5 * math.cos(math.pi * i / (LEAF_NU - 1))   # denser at base and tip
        hw = hw_max * _leaf_width(u)
        th = LEAF_THICK * math.sin(math.pi * u) ** 0.5
        m = frame(u)
        # the section twists gently from root to tip (no flat planar sweep)
        tw = twist * u
        su = s * math.cos(tw) + n * math.sin(tw)
        nu = n * math.cos(tw) - s * math.sin(tw)
        top, bot = [], []
        ridge = LEAF_RIDGE * math.sin(math.pi * u) ** 0.5
        for v in vs:
            # cupped (U-shaped) section with a smooth raised midrib
            lift = nu * (fold * hw * v * v + ridge * (1 - v * v) ** 2)
            p = m + su * (hw * v) + lift
            cap = th * (1 - v * v)
            top.append(p + nu * cap)
            bot.append(p - nu * cap)
        ring = top + bot[-2:0:-1]
        rv = vs + vs[-2:0:-1]
        rings.append(([bm.verts.new(p) for p in ring], u, rv))
        midrib.append(m + nu * (th + ridge + 0.0002))
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
    return midrib, t


def _basis(normal):
    """Two unit vectors spanning the plane perpendicular to `normal` (a points up)."""
    up = Vector((0, 0, 1)) if abs(normal.z) < 0.95 else Vector((0, 1, 0))
    a = (up - normal * normal.dot(up)).normalized()
    return a, normal.cross(a)


def _petal_width(s):
    """Petal half width (share of PETAL_W * R) at radial position s (0 centre,
    1 tip): a narrow claw at the centre widening to a broad, rounded
    (elliptical) tip."""
    s = min(max(s, 0.0), 1.0)
    if s < PETAL_WIDEST:
        return 0.25 + 0.75 * math.sin(0.5 * math.pi * s / PETAL_WIDEST)
    return math.sqrt(max(0.0, 1.0 - ((s - PETAL_WIDEST) / (1.0 - PETAL_WIDEST)) ** 2))


def _flower(bm, center, normal, radius, cup=0.22, thick=PETAL_THICK):
    """Five separate, softly cupped petals (each a closed lens-section blade)
    radiating from the centre, overlapping their neighbours like a pinwheel:
    each petal's leading edge lies over the next petal's trailing edge."""
    a, b = _basis(normal)
    R = radius * PX
    vs = [k / (PETAL_NV - 1) * 2 - 1 for k in range(PETAL_NV)]
    for i in range(FLOWER_PETALS):
        phi = 2 * math.pi * i / FLOWER_PETALS + math.pi / 2
        ax = a * math.cos(phi) + b * math.sin(phi)
        perp = normal.cross(ax)

        def surf(s, v):
            hw = PETAL_W * R * _petal_width(s)
            # the flower as a whole is a shallow bowl; each petal cups (its
            # edges rise) and leans: its +v edge up, its -v edge down, so it
            # overlaps the neighbour without touching it
            lift = (cup * R * s * s + PETAL_CUP * R * v * v * s ** 1.2
                    + PETAL_LEAN * v * math.sqrt(s))
            return center + ax * (R * s) + perp * (hw * v) + normal * lift, hw

        rings = []
        for k in range(1, PETAL_NS - 1):
            s = PETAL_S0 + (1 - PETAL_S0) * (0.5 - 0.5 * math.cos(math.pi * k / (PETAL_NS - 1)))
            top, bot = [], []
            for v in vs:
                p, hw = surf(s, v)
                th = 0.5 * thick * (1 - v * v) ** 0.5 * (1 - 0.5 * s)
                top.append(p + normal * th)
                bot.append(p - normal * th)
            rings.append([bm.verts.new(p) for p in top + bot[-2:0:-1]])
        vb = bm.verts.new(surf(PETAL_S0, 0.0)[0])
        vt = bm.verts.new(surf(1.0, 0.0)[0])
        nr = len(rings[0])
        for r0, r1 in zip(rings, rings[1:]):
            for j in range(nr):
                k = (j + 1) % nr
                bm.faces.new((r0[j], r0[k], r1[k], r1[j]))
        for j in range(nr):
            k = (j + 1) % nr
            bm.faces.new((vb, rings[0][k], rings[0][j]))
            bm.faces.new((vt, rings[-1][j], rings[-1][k]))


def _dome(bm, center, normal, radius, height, seg=8, depth=None):
    """Small closed dome (flower centre)."""
    a, b = _basis(normal)
    rings = []
    for f, h in ((1.0, 0.0), (0.7, 0.75)):
        rings.append([bm.verts.new(center + (a * math.cos(2 * math.pi * k / seg)
                                             + b * math.sin(2 * math.pi * k / seg)) * radius * f
                                   + normal * height * h) for k in range(seg)])
    top = bm.verts.new(center + normal * height)
    bot = bm.verts.new(center - normal * (height * 0.3 if depth is None else depth))
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
                             lf['fold'], lf['bend'], lf['curl'], math.radians(lf['twist']), lf['arch']))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    leaves = new_object(col, f'acc_leaves_{tag}', bm, [toon_material('leaf', gradient='green')])
    _write_grad(leaves, grads)
    shade_smooth(leaves, 60)
    add_outline(leaves)

    # midrib veins: thin dark tubes on the upper surface
    bm = bmesh.new()
    for mr, t in midribs:
        # a short stalk from inside the hair into the blade base (so the leaf
        # is attached, not resting on the hair), then the midrib vein
        # The stalk tapers from PETIOLE_R at the hair to the vein's radius
        # where it meets the blade; the vein then thins toward the tip.
        stalk = [mr[0] - t * (PETIOLE_IN * PX * (1 - k / PETIOLE_SEG)) for k in range(PETIOLE_SEG)]
        vein = [mr[0]] + mr[2:-1:2]
        pts = stalk + vein
        radii = [PETIOLE_R + (VEIN_R * 1.3 - PETIOLE_R) * _body.smoothstep(0.0, 1.0, k / PETIOLE_SEG)
                 for k in range(PETIOLE_SEG)]
        radii += [VEIN_R * (1.3 - 0.75 * k / max(1, len(vein) - 1)) for k in range(len(vein))]
        _tube(bm, pts, radii, VEIN_SIDES)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    veins = new_object(col, f'acc_leaf_veins_{tag}', bm, [toon_material('green')])
    shade_smooth(veins, 80)
    add_outline(veins, width=0.0003)

    # flower
    c0 = _mirror(P(*FLOWER['center']), sx)
    nrm = _mirror(V(*FLOWER['normal']), sx)
    c = c0 + nrm * FLOWER_LIFT
    bm = bmesh.new()
    _flower(bm, c, nrm, FLOWER['radius'])
    npet = len(bm.faces)
    dc = c + nrm * (0.06 * FLOWER['radius'] * PX)
    _dome(bm, dc, nrm, FLOWER['radius'] * PX * 0.3, FLOWER_DOME, seg=12,
          depth=(dc - c0).dot(nrm) + FLOWER_MOUNT)
    for i, f in enumerate(bm.faces):
        f.material_index = 0 if i < npet else 1
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    flower = new_object(col, f'acc_flower_{tag}', bm,
                        [toon_material('flower'), toon_material('flower_center')])
    shade_smooth(flower, 50)
    add_outline(flower, width=0.0010)   # a lighter line: no dark rim when it turns away


def _choker_ring(theta):
    """Point on the choker's centre loop (reference px); theta=0 at +X, -pi/2 front."""
    ch = CHOKER
    _, cy, row = ch['center']
    # front (sin<0) sits lower than the back
    return (ch['rx'] * math.cos(theta), cy + ch['ry'] * math.sin(theta),
            row - ch['tilt'] * math.sin(theta))


class _Skin:
    """The body's current torso surface, rebuilt from body.py's tables
    (body.build_torso into a private bmesh; no body object is read), with
    nearest-point queries that return the smooth (vertex-interpolated) normal."""

    def __init__(self):
        bm = bmesh.new()
        _body.build_torso(bm)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.normal_update()
        bm.faces.ensure_lookup_table()
        self.bm = bm
        self.tree = BVHTree.FromBMesh(bm)

    def free(self):
        self.bm.free()

    def nearest(self, p):
        loc, _, idx, _ = self.tree.find_nearest(p)
        verts = self.bm.faces[idx].verts
        w = poly_3d_calc([v.co for v in verts], loc)
        n = sum((v.normal * wi for v, wi in zip(verts, w)), Vector())
        return loc, n.normalized()

    def lift(self, p, off):
        """`p` moved to `off` metres outside the skin along the surface normal."""
        for _ in range(3):
            loc, n = self.nearest(p)
            p = loc + n * off
        return p

    def radial(self, origin, d):
        """Distance from `origin` (inside the torso) to the skin along unit `d`."""
        hit = self.tree.ray_cast(origin, d)[0]
        return (hit - origin).length if hit is not None else None


def _choker_radius(i):
    """Tube radius (px) at loop sample i: smooth bead bulges, one per period."""
    ch = CHOKER
    c = math.cos(2 * math.pi * i / ch['period'])
    # a rounder bulge than a raised cosine: full over most of the bead, a
    # quick neck at the joint
    return ch['r'] + ch['bead'] * (0.5 + 0.5 * c) ** 0.7


def _choker_point(skin, theta):
    """Choker centre-loop point at `theta`, refitted to the neck: along the
    loop's horizontal radius from the neck axis, (bead radius + gap) outside the
    skin. Averaged over a few neighbouring angles so neck facets don't ripple it."""
    ch = CHOKER
    x, y, row = _choker_ring(theta)
    p = P(x, y, row)
    axis = P(0, ch['center'][1], row)
    off = (ch['r'] + ch['bead']) * PX + CHOKER_GAP
    step = CHOKER_FIT_STEP   # a fixed angular window (+/- 9 deg), whatever 'seg' is
    rs = []
    for k in (-2, -1, 0, 1, 2):
        xk, yk, _ = _choker_ring(theta + k * step)
        d = Vector((xk * PX, yk * PX - axis.y, 0.0)).normalized()
        r = skin.radial(axis, d)
        if r is not None:
            rs.append(r)
    d = Vector((p.x - axis.x, p.y - axis.y, 0.0)).normalized()
    if not rs:
        print(f'WARNING accessories: choker theta {theta:.3f} missed the neck; unfitted point kept')
        return p
    return axis + d * (sum(rs) / len(rs) + off)


def _choker(col, skin):
    ch = CHOKER
    pts, radii = [], []
    for i in range(ch['seg']):
        pts.append(_choker_point(skin, 2 * math.pi * i / ch['seg']))
        radii.append(_choker_radius(i) * PX)
    bm = bmesh.new()
    _tube(bm, pts, radii, ch['sides'], loop_center=P(*ch['center']))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    obj = new_object(col, 'acc_choker', bm, [toon_material('green')])
    shade_smooth(obj, 70)
    add_outline(obj, width=CHOKER_LINE)


def _rim_row(x_m):
    """Bodice neckline row at world x (front half)."""
    row = 238.0
    for _ in range(3):   # the half width depends (weakly) on the row
        hw = _bodice.profile(row)[0]
        row = _bodice.neck_row_t(min(abs(x_m) / hw, 1.0))
    return row


def _row(p):
    return spec.SHEET_GROUND_Y - p.z * spec.PX_PER_M


def _tucked(path):
    """Cut a (fitted) path of world points running down where it is
    BODICE_TUCK px below the neckline."""
    for i in range(1, len(path)):
        a, b = path[i - 1], path[i]
        da = _row(a) - _rim_row(a.x) - BODICE_TUCK
        db = _row(b) - _rim_row(b.x) - BODICE_TUCK
        if da < 0 <= db:
            lo, hi = 0.0, 1.0
            for _ in range(30):
                m = (lo + hi) / 2
                q = a.lerp(b, m)
                if _row(q) - _rim_row(q.x) - BODICE_TUCK < 0:
                    lo = m
                else:
                    hi = m
            end = a.lerp(b, hi)
            # a cut just past a sample would leave a near-zero last segment
            # (degenerate end ring): end the path on the cut point instead
            keep = i - 1 if hi < 0.25 and i >= 2 else i
            return path[:keep] + [end]
    return path


def _string_offset(p, cross=0):
    """Centreline height above the skin at `p`. cross: +1 over / -1 under strand."""
    base = STRING_R + STRING_GAP
    # settle onto the skin just above the neckline, to slide in under the rim
    depth = _row(p) - _rim_row(p.x)
    base += (STRING_R + STRING_TUCK_GAP - base) * _body.smoothstep(-TUCK_FADE, BODICE_TUCK, depth)
    if cross:
        g = math.exp(-(p.x / (CROSS_SIGMA * PX)) ** 2)
        under = STRING_R + CROSS_UNDER_GAP
        target = under if cross < 0 else under + 2 * STRING_R + 0.0002
        base += (target - base) * g
    return base


def _fit_string(skin, path, cross=0, keep_first=False, rounds=3):
    """Lift a dense path onto the skin, with light smoothing between rounds so
    the facets of the torso don't kink it. keep_first: the first point (inside
    the choker) stays put."""
    pts = [p.copy() for p in path]
    lo = 1 if keep_first else 0
    for r in range(rounds + 1):
        pts = pts[:lo] + [skin.lift(p, _string_offset(p, cross)) for p in pts[lo:]]
        if r == rounds:
            break
        sm = [p.copy() for p in pts]
        for i in range(max(lo, 1), len(pts) - 1):
            sm[i] = pts[i] * 0.5 + (pts[i - 1] + pts[i + 1]) * 0.25
        pts = sm
    return pts


def _add_string(bm, pts):
    _tube(bm, pts, [STRING_R] * len(pts), STRING_SIDES)


def _strings(col, skin):
    bm = bmesh.new()
    for sx in (1, -1):
        # the strap starts inside the choker tube, on its side-back
        start = _choker_point(skin, STRAP_THETA if sx > 0 else math.pi - STRAP_THETA)
        strap = _catmull([start] + [_mirror(P(*p), sx) for p in STRAP], STRING_PER_SEG)
        # fitted first, then cut, so the end lands BODICE_TUCK px under the rim
        _add_string(bm, _tucked(_fit_string(skin, strap, keep_first=True)))
        # the character-left strand passes over the other one where they cross
        cross = _catmull([_mirror(P(*p), sx) for p in CROSS], STRING_PER_SEG)
        _add_string(bm, _fit_string(skin, cross, cross=1 if sx > 0 else -1))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    obj = new_object(col, 'acc_halter', bm, [toon_material('green')])
    shade_smooth(obj, 80)
    add_outline(obj, width=STRING_LINE)


def build(col):
    for sx in (1, -1):
        _build_side(col, sx)
    skin = _Skin()
    try:
        _choker(col, skin)
        _strings(col, skin)
    finally:
        skin.free()
