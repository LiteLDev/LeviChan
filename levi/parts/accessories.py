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
import bisect
import math

import bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.interpolate import poly_3d_calc

from .. import spec
from ..common import GRAD_ATTR, add_outline, new_object, shade_smooth, toon_material
# Data / pure functions only (CLAUDE.md "Part rules"): body.build_torso rebuilds
# the torso surface from body's tables into a private bmesh (the neck the choker
# rests on, the chest the cords lie on), and bodice's profile / neckline functions
# give the rim the straps tuck under. No head data: round 11's head tucks its neck
# inside the body's, so the body's neck is the outer skin under the choker.
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
LEAF_NU = 27          # rings along the leaf (incl. base/tip points), cosine-spaced (round 10: 19)
LEAF_NV = 7           # samples across the top surface (odd: midrib vertex; round 10: 5)
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
PETAL_S0 = 0.1        # petals start this far out (under the centre cushion)
PETAL_NS = 13         # stations along a petal (incl. the base and tip points; round 10: 9)
PETAL_NV = 7          # samples across the top surface (round 10: 5, a polygonal rim)
# Flower centre: a cushion CENTRE_R (share of the flower radius) across, its widest
# ring CENTRE_EQ above the petal plane and CENTRE_HALF high either side
# (CENTRE_LATS), with no outline of its own (CENTRE_LINE of the flower's): the
# sheet paints a small soft yellow dot (~0.23 of the radius) with no ring. An
# inverted hull round a dome sitting among the petals cannot draw a clean ring: its
# visible part lies below the dome's widest ring, among the petals' raised inner
# edges, so a petal sliver showed between the fill and the line (round 11's first
# build: a 1 mm ring with a sliver from 1 to 6 o'clock; a 0.5 mm line on a drum
# below the equator stood off the fill as a hairline).
CENTRE_R = 0.25
CENTRE_EQ = 0.0016
CENTRE_HALF = 0.0013
CENTRE_SEG = 20
CENTRE_LATS = (67.5, 45.0, 22.5, 0.0, -30.0, -60.0)   # ring latitudes, top to underside
CENTRE_LINE = 0.0
FLOWER_LINE = 0.0010   # the petals' outline: lighter than the default (no dark rim when it turns away)

# Choker: tilted elliptical loop (front lower than back). The loop below is
# only the initial guess (centre y -31, rows 166-178): every point is refitted
# to the current neck surface (see _choker_point), the bead insides resting on
# the skin.
# Round 11: CHOKER_BEADS separate round beads (closed BEAD_SEG x BEAD_RINGS
# spheres, a little long along the cord, poles on the cord) threaded on a thin
# closed cord, like the sheet's row of round bumps and the art's vine of links.
# Round 10 was one 7-sided tube bulging into faceted double cones ('nuts').
CHOKER = dict(center=(0, -31.0, 172.0), rx=16.6, ry=17.2, tilt=6.0)
CHOKER_BEADS = 24     # even: a bead at the front and one at the back centre (mirror symmetric)
BEAD_R = 0.0028       # bead radius across the cord (m)
BEAD_LONG = 1.08      # semi-axis along the cord, share of BEAD_R (the beads just miss each other)
BEAD_SEG = 12         # segments round the cord
BEAD_RINGS = 7        # latitude bands, pole to pole
CORD_R = 0.0007       # the cord the beads are threaded on (shows between them)
CORD_SIDES = 6
CORD_PER_BEAD = 4     # cord rings per bead pitch
CHOKER_LOOP_SAMPLES = 16   # fitted loop points per bead pitch (the beads are spaced by arc length)
CHOKER_GAP = 0.0002   # skin -> bead inside (m)
CHOKER_FIT_STEP = 2 * math.pi / 80   # angle between the 5 neck samples averaged per point
CHOKER_LINE = 0.0008  # outline width: a fine vine, not a serrated band

# Halter strap (character-left): it leaves the choker from inside one of its
# beads on the side-back (STRAP_BEAD, counted from the back centre toward +X),
# runs forward over the shoulder slope (STRAP[:4], the side sheet's strap
# leaves the choker heading forward-down at ~30 deg) and down the chest to the
# bodice top. x/row follow the front reference strings. The y values are only
# the starting guess: the build projects every path point onto the body's
# current torso surface (body.build_torso, see _Skin), lifted along the smooth
# surface normal, and lets it settle like a taut cord (_fit_string), so the
# strings follow the chest whatever its depth.
STRAP_BEAD = 4
STRAP = ((17.6, -27.5, 178.5), (20.5, -33, 183), (22.6, -42.5, 187), (24, -48, 191.5),
         (26.3, -48.3, 197), (31.3, -52.4, 210), (36.3, -57.1, 222), (41, -58.9, 233),
         (45, -59.2, 243), (49, -59.5, 253))
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
STRING_PER_SEG = 8        # Catmull-Rom samples per control span (round 10: 3, a kink every ~1 cm)
STRING_STEP = 0.0028      # m between the cord's rings (resampled evenly by arc length)
STRING_GAP = 0.0010     # skin -> string surface: centreline ~2.4 mm outside the skin
# The fitted path settles like a taut cord: STRING_ROUNDS rounds of smoothing along
# the cord (Gaussian, STRING_RELAX m) and pushing it back out of the skin. It may
# bridge a hollow (the neck / shoulder corner) by at most STRING_SLACK; at the
# crossing and the bodice tuck it lies at its exact height.
STRING_RELAX = 0.004
STRING_ROUNDS = 8
STRING_SLACK = 0.0025
SLACK_FADE = 18.0         # px above the tuck over which the cord comes down to the skin
# Followed exactly, a height above the torso's ~1.5 cm facets creases the cord at
# every facet edge (10-20 deg): the cords are fitted to the torso after
# STRING_SKIN_SUBDIV smooth subdivisions, the settling moves are smoothed along
# the cord (STRING_SETTLE_SMOOTH), and the cord surface is held at least
# STRING_FLOOR off the real torso.
STRING_SKIN_SUBDIV = 1
STRING_SETTLE_SMOOTH = 0.004
STRING_FLOOR = 0.0
# The X strands leave one strap and end on the other: they start and end on the
# strap's centre line, thinned to STRING_TIP of the radius (their end caps stay
# inside the strap) and back to full width over STRING_TAPER, about where they
# leave the strap's surface (round 10: a full-width flat end cap off the centre
# line poked out of the strap's side).
STRING_TIP = 0.8
STRING_TAPER = 0.0025
# Crossing (x = 0): the under strand drops to touch the skin and the over strand
# rides on top of it, both along the surface normal, fading out over CROSS_SIGMA.
CROSS_UNDER_GAP = 0.0002
CROSS_SIGMA = 12.0      # px
# Lower ends: the straps settle onto the skin over the TUCK_FADE px above the bodice
# neckline (down to BODICE_TUCK px below it), so they slide in under the rim, and end
# STRAP_UNDER px below it. The bodice's real rim runs ~2 px below bodice.neck_row_t
# there, so round 11's first build (ending 3 px below) had only its last two rings
# under the bodice (~2 mm of it); 8 px puts ~1 cm under it, where the bodice stands
# 6-8 mm off the skin (the cord needs 3.6 mm).
BODICE_TUCK = 3.0
STRAP_UNDER = 8.0
TUCK_FADE = 10.0
STRING_TUCK_GAP = 0.0008
# Skinning marks for the rig (rig._halter_ride / _halter_joins, point attributes named by
# obj['levi_cord_ride'] / obj['levi_cord_join']). With the skin's weights the tucked strap
# ends took some of the clavicle bone, which the bodice over them does not, and a raised arm drew
# them out from under the rim; the X strands, smoothed along their own cord, came up to
# 4.4 mm off the strap they end on. So:
# * ride: share of the bodice's own weights, 1 from the rim down (the tucked end moves with
#   the rim), fading out over RIDE_FADE px above it;
# * join: share of the strap's weights at the strand's pin (obj['levi_cord_pins'], the end
#   points on the strap's centre line), 1 at the pin, 0 JOIN_SPAN along the strand.
RIDE_FADE = 10.0
JOIN_SPAN = 0.015
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


def _write_point(obj, name, values):
    """Float point attribute `name` (values clamped to 0..1, one per vertex)."""
    me = obj.data
    if len(values) != len(me.vertices):
        raise ValueError(f'{obj.name}: {len(values)} values for {len(me.vertices)} vertices ({name})')
    attr = me.attributes.get(name) or me.attributes.new(name, 'FLOAT', 'POINT')
    attr.data.foreach_set('value', [max(0.0, min(1.0, v)) for v in values])


def _write_grad(obj, values):
    _write_point(obj, GRAD_ATTR, values)


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


def _cushion(bm, center, normal, radius, half, depth, seg=CENTRE_SEG):
    """Closed flower centre: an oblate cushion (an ellipsoid, `radius` across,
    `half` high either side of its widest ring at `center`), whose underside runs
    on into a concealed stalk ending `depth` below `center`. Round 10's dome was
    12-sided and widest at its foot, among the petals' raised edges."""
    a, b = _basis(normal)
    rings = []
    for lat in CENTRE_LATS:
        ca, sa = math.cos(math.radians(lat)), math.sin(math.radians(lat))
        rings.append([bm.verts.new(center + (a * math.cos(2 * math.pi * k / seg)
                                             + b * math.sin(2 * math.pi * k / seg)) * (radius * ca)
                                   + normal * (half * sa)) for k in range(seg)])
    top = bm.verts.new(center + normal * half)
    bot = bm.verts.new(center - normal * depth)
    for r0, r1 in zip(rings, rings[1:]):
        for j in range(seg):
            k = (j + 1) % seg
            bm.faces.new((r0[j], r0[k], r1[k], r1[j]))
    for j in range(seg):
        k = (j + 1) % seg
        bm.faces.new((rings[0][j], rings[0][k], top))
        bm.faces.new((rings[-1][k], rings[-1][j], bot))


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
    veins['levi_cast_shadow'] = False
    add_outline(veins, width=0.0003)

    # flower
    c0 = _mirror(P(*FLOWER['center']), sx)
    nrm = _mirror(V(*FLOWER['normal']), sx)
    c = c0 + nrm * FLOWER_LIFT
    bm = bmesh.new()
    _flower(bm, c, nrm, FLOWER['radius'])
    npet, nvp = len(bm.faces), len(bm.verts)
    dc = c + nrm * CENTRE_EQ
    _cushion(bm, dc, nrm, FLOWER['radius'] * PX * CENTRE_R, CENTRE_HALF,
             depth=(dc - c0).dot(nrm) + FLOWER_MOUNT)
    for i, f in enumerate(bm.faces):
        f.material_index = 0 if i < npet else 1
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    nv = len(bm.verts)
    flower = new_object(col, f'acc_flower_{tag}', bm,
                        [toon_material('flower'), toon_material('flower_center')])
    shade_smooth(flower, 50)
    # the petals take the full line, the centre CENTRE_LINE of it (none: a soft dot)
    vg = flower.vertex_groups.new(name='flower_line')
    vg.add(list(range(nvp)), 1.0, 'REPLACE')
    vg.add(list(range(nvp, nv)), 0.0, 'REPLACE')
    add_outline(flower, width=FLOWER_LINE, vertex_group='flower_line', min_factor=CENTRE_LINE)


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

    def __init__(self, subdiv=0):
        bm = bmesh.new()
        _body.build_torso(bm)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        for _ in range(subdiv):
            # smooth subdivision: the new points sit on a curved surface through the
            # torso's own vertices (bulging out over convex facets, never inside them)
            bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=1, smooth=1.0,
                                      use_grid_fill=True, use_smooth_even=True)
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

    def project(self, p, iters=8):
        """(loc, n, h): p = loc + h n, n the smooth normal at the skin point loc (a
        Phong projection: loc slides until the smooth normal there points at p). The
        nearest point alone stays on a facet edge while p moves past it, and an
        offset along the smooth normal from there kinked a cord at every facet."""
        loc, n = self.nearest(p)
        for _ in range(iters):
            h = (p - loc).dot(n)
            loc2, n2 = self.nearest(p - n * h)
            done = (loc2 - loc).length < 1e-7
            loc, n = loc2, n2
            if done:
                break
        return loc, n, (p - loc).dot(n)

    def lift(self, p, off):
        """`p` moved to `off` metres outside the skin along the smooth surface normal."""
        loc, n, _ = self.project(p)
        return loc + n * off

    def radial(self, origin, d):
        """Distance from `origin` (inside the torso) to the skin along unit `d`."""
        hit = self.tree.ray_cast(origin, d)[0]
        return (hit - origin).length if hit is not None else None


def _bead_theta(k):
    """Loop angle of bead k (0 at the back centre, counting toward +X)."""
    return math.pi / 2 - 2 * math.pi * k / CHOKER_BEADS


def _choker_point(skin, theta):
    """Choker centre-loop point at `theta`, refitted to the neck: along the
    loop's horizontal radius from the neck axis, (bead radius + gap) outside the
    body's neck. Averaged over a few neighbouring angles so neck facets don't
    ripple it. (The first round-11 build also rested it on round 10's head neck
    table, head.neck_at shifted HEAD_DX, which stood ~3 px proud of the body's
    neck on the left; round 11's head tucks its neck inside the body's, and with
    it the table left the left beads 2-5 mm off the skin.)"""
    ch = CHOKER
    x, y, row = _choker_ring(theta)
    p = P(x, y, row)
    axis = P(0, ch['center'][1], row)
    off = BEAD_R + CHOKER_GAP
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


def _bead(bm, c, t, d):
    """Closed bead (UV sphere, BEAD_SEG x BEAD_RINGS) centred on `c`, its poles on
    the cord (unit tangent `t`), `d` a unit direction across the cord."""
    d = (d - t * d.dot(t)).normalized()
    u = t.cross(d)
    a, b = BEAD_R * BEAD_LONG, BEAD_R
    rings = []
    for i in range(1, BEAD_RINGS):
        ph = math.pi * i / BEAD_RINGS
        ring = []
        for j in range(BEAD_SEG):
            ps = 2 * math.pi * j / BEAD_SEG
            ring.append(bm.verts.new(c + t * (a * math.cos(ph))
                                     + (d * math.cos(ps) + u * math.sin(ps)) * (b * math.sin(ph))))
        rings.append(ring)
    p0, p1 = bm.verts.new(c + t * a), bm.verts.new(c - t * a)
    for r0, r1 in zip(rings, rings[1:]):
        for j in range(BEAD_SEG):
            k = (j + 1) % BEAD_SEG
            bm.faces.new((r0[j], r0[k], r1[k], r1[j]))
    for j in range(BEAD_SEG):
        k = (j + 1) % BEAD_SEG
        bm.faces.new((p0, rings[0][k], rings[0][j]))
        bm.faces.new((p1, rings[-1][j], rings[-1][k]))


def _choker_loop(skin):
    """The fitted centre loop, densely sampled from the back centre toward +X:
    (points, cumulative arc length round the closed loop)."""
    n = CHOKER_BEADS * CHOKER_LOOP_SAMPLES
    pts = [_choker_point(skin, _bead_theta(i * CHOKER_BEADS / n)) for i in range(n)]
    s = [0.0]
    for a, b in zip(pts, pts[1:] + pts[:1]):
        s.append(s[-1] + (b - a).length)
    return pts, s


def _loop_at(loop, f):
    """(point, unit tangent) at share `f` of the loop's length from the back
    centre (toward +X)."""
    pts, s = loop
    n = len(pts)

    def at(t):
        t %= s[-1]
        i = min(bisect.bisect_right(s, t) - 1, n - 1)
        return pts[i].lerp(pts[(i + 1) % n], (t - s[i]) / max(s[i + 1] - s[i], 1e-12))

    t, dt = f * s[-1], 0.25 * s[-1] / n
    return at(t), (at(t + dt) - at(t - dt)).normalized()


def _choker(col, loop):
    """Beads at equal steps of arc length round the fitted loop (its radius about
    the neck axis changes round the neck: equal angles would space them
    unevenly)."""
    ch = CHOKER
    centre = P(*ch['center'])
    bm = bmesh.new()
    # the cord: a thin closed tube through the bead centres
    n = CHOKER_BEADS * CORD_PER_BEAD
    cord = [_loop_at(loop, i / n)[0] for i in range(n)]
    _tube(bm, cord, [CORD_R] * n, CORD_SIDES, loop_center=centre)
    # the beads, threaded on it (their poles on the cord's line)
    for k in range(CHOKER_BEADS):
        c, t = _loop_at(loop, k / CHOKER_BEADS)
        _bead(bm, c, t, Vector((c.x - centre.x, c.y - centre.y, 0.0)))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    obj = new_object(col, 'acc_choker', bm, [toon_material('green')])
    shade_smooth(obj, 70)
    obj['levi_cast_shadow'] = False   # small beads print specks on the neck
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
    STRAP_UNDER px below the neckline."""
    for i in range(1, len(path)):
        a, b = path[i - 1], path[i]
        da = _row(a) - _rim_row(a.x) - STRAP_UNDER
        db = _row(b) - _rim_row(b.x) - STRAP_UNDER
        if da < 0 <= db:
            lo, hi = 0.0, 1.0
            for _ in range(30):
                m = (lo + hi) / 2
                q = a.lerp(b, m)
                if _row(q) - _rim_row(q.x) - STRAP_UNDER < 0:
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


def _string_exact(p, cross=0):
    """1 where the cord lies at exactly its height above the skin (the crossing,
    the tuck under the bodice rim), 0 where it may bridge a hollow."""
    e = _body.smoothstep(-SLACK_FADE, BODICE_TUCK, _row(p) - _rim_row(p.x))
    if cross:
        e = max(e, math.exp(-(p.x / (CROSS_SIGMA * PX)) ** 2))
    return e


def _arclen(pts):
    s = [0.0]
    for a, b in zip(pts, pts[1:]):
        s.append(s[-1] + (b - a).length)
    return s


def _resample(pts, step):
    """Polyline resampled evenly by arc length, about `step` apart (ends kept)."""
    s = _arclen(pts)
    n = max(2, int(round(s[-1] / step)) + 1)
    out, j = [], 0
    for i in range(n):
        si = s[-1] * i / (n - 1)
        while j < len(s) - 2 and s[j + 1] < si:
            j += 1
        f = (si - s[j]) / max(s[j + 1] - s[j], 1e-12)
        out.append(pts[j].lerp(pts[j + 1], min(max(f, 0.0), 1.0)))
    return out


def _smooth_path(pts, sigma):
    """Gaussian smoothing along the arc length (ends kept; mirrored past them,
    so the ends keep their direction instead of curling in)."""
    s = _arclen(pts)
    n = len(pts)
    # the path with its point reflections through both ends
    ext = ([(pts[0] * 2 - pts[j], -s[j]) for j in range(n - 1, 0, -1)] + list(zip(pts, s))
           + [(pts[-1] * 2 - pts[j], 2 * s[-1] - s[j]) for j in range(n - 2, -1, -1)])
    out = [pts[0]]
    for i in range(1, n - 1):
        acc, wsum = Vector(), 0.0
        for q, sj in ext:
            ds = sj - s[i]
            if abs(ds) <= 3 * sigma:
                w = math.exp(-0.5 * (ds / sigma) ** 2)
                acc += q * w
                wsum += w
        out.append(acc / wsum)
    out.append(pts[-1])
    return out


def _smooth_values(v, s, sigma):
    """Gaussian smoothing of the values `v` at arc lengths `s` (mirrored past the ends)."""
    if sigma <= 0:
        return list(v)
    ext = [(v[j], -s[j]) for j in range(len(v) - 1, 0, -1)] + list(zip(v, s)) \
        + [(v[j], 2 * s[-1] - s[j]) for j in range(len(v) - 2, -1, -1)]
    out = []
    for si in s:
        acc = wsum = 0.0
        for x, sj in ext:
            if abs(sj - si) <= 3 * sigma:
                w = math.exp(-0.5 * ((sj - si) / sigma) ** 2)
                acc += x * w
                wsum += w
        out.append(acc / wsum)
    return out


def _settle(skin, pts, cross):
    """The path moved along the smooth skin normal into its height band: at least
    its offset above the skin, at most STRING_SLACK more (a taut cord over a
    hollow; none where it lies exactly). The moves are smoothed along the cord
    (STRING_SETTLE_SMOOTH), so the facets' creases don't come back as kinks."""
    proj = [skin.project(p) for p in pts]
    d = []
    for p, (_, _, h) in zip(pts, proj):
        off = _string_offset(p, cross)
        d.append(min(max(h, off), off + STRING_SLACK * (1.0 - _string_exact(p, cross))) - h)
    d = _smooth_values(d, _arclen(pts), STRING_SETTLE_SMOOTH)
    return [p + n * di for p, (_, n, _), di in zip(pts, proj, d)]


def _fit_string(skin, path, cross=0, first=None, last=None, floor=None):
    """Evenly resampled path lifted onto the skin, then settled like a taut cord
    (STRING_ROUNDS of smoothing along it and pushing it back out of the skin), so
    neither the torso's facets nor a hollow kink it. first / last: fixed end
    points (inside a choker bead, on a strap's centre line)."""
    pts = _resample(path, STRING_STEP)
    pts = [skin.lift(p, _string_offset(p, cross)) for p in pts]

    def pin(pts):
        if first is not None:
            pts[0] = first.copy()
        if last is not None:
            pts[-1] = last.copy()
        return pts

    pts = pin(pts)
    for _ in range(STRING_ROUNDS):
        pts = _smooth_path(pts, STRING_RELAX)
        pts = _resample(pin(_settle(skin, pts, cross)), STRING_STEP)
    floor = floor or skin
    out = []
    for p in pts:
        # the true distance to the nearest facet (the smooth-normal height overstates
        # it in a hollow)
        loc, n, _, d = floor.tree.find_nearest(p)
        d = d if (p - loc).dot(n) >= 0 else -d
        out.append(p if d >= STRING_R + STRING_FLOOR else p + n * (STRING_R + STRING_FLOOR - d))
    return pin(out)


def _nearest_on(path, p):
    """Point of polyline `path` nearest to `p`."""
    best, bd = path[0], float('inf')
    for a, b in zip(path, path[1:]):
        ab = b - a
        t = min(max((p - a).dot(ab) / max(ab.length_squared, 1e-12), 0.0), 1.0)
        q = a + ab * t
        if (q - p).length < bd:
            best, bd = q, (q - p).length
    return best


def _string_radii(pts, taper):
    """Constant STRING_R, or (taper) thinned to STRING_TIP at both ends."""
    if not taper:
        return [STRING_R] * len(pts)
    s = _arclen(pts)
    return [STRING_R * (STRING_TIP + (1 - STRING_TIP)
                        * _body.smoothstep(0.0, STRING_TAPER, min(si, s[-1] - si))) for si in s]


def _strings(col, skin, loop, cage):
    """skin: the torso smoothly subdivided (STRING_SKIN_SUBDIV) the cords are fitted
    to; cage: the torso itself (the cords' floor); loop: the choker's centre loop
    (_choker_loop), whose beads the straps leave."""
    bm = bmesh.new()
    straps = {}
    ride, join, pins = [], [], []      # per vertex in build order (STRING_SIDES per ring)
    for sx in (1, -1):
        # the strap starts inside a choker bead (STRAP_BEAD) on the side-back
        f = STRAP_BEAD / CHOKER_BEADS
        start = _loop_at(loop, f if sx > 0 else 1.0 - f)[0]
        strap = _catmull([start] + [_mirror(P(*p), sx) for p in STRAP], STRING_PER_SEG)
        # fitted first, then cut, so the end lands STRAP_UNDER px under the rim
        straps[sx] = _tucked(_fit_string(skin, strap, first=start, floor=cage))
        _tube(bm, straps[sx], _string_radii(straps[sx], False), STRING_SIDES)
        for p in straps[sx]:
            ride += [_body.smoothstep(-RIDE_FADE, 0.0, _row(p) - _rim_row(p.x))] * STRING_SIDES
            join += [0.0] * STRING_SIDES
    for sx in (1, -1):
        # an X strand runs from this side's strap to the other's; the character-left
        # strand passes over the other one where they cross
        c = [_mirror(P(*p), sx) for p in CROSS]
        cs = 1 if sx > 0 else -1
        a = _nearest_on(straps[sx], skin.lift(c[0], _string_offset(c[0], cs)))
        b = _nearest_on(straps[-sx], skin.lift(c[-1], _string_offset(c[-1], cs)))
        path = _fit_string(skin, _catmull([a] + c[1:-1] + [b], STRING_PER_SEG), cs, first=a, last=b,
                           floor=cage)
        _tube(bm, path, _string_radii(path, True), STRING_SIDES)
        pins += [a, b]
        s = _arclen(path)
        for si in s:
            ride += [0.0] * STRING_SIDES
            join += [max(_body.smoothstep(JOIN_SPAN, 0.0, si),
                         _body.smoothstep(JOIN_SPAN, 0.0, s[-1] - si))] * STRING_SIDES
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    obj = new_object(col, 'acc_halter', bm, [toon_material('green')])
    shade_smooth(obj, 80)
    obj['levi_cast_shadow'] = False
    _write_point(obj, 'cord_ride', ride)
    _write_point(obj, 'cord_join', join)
    obj['levi_cord_ride'] = 'cord_ride'
    obj['levi_cord_join'] = 'cord_join'
    obj['levi_cord_pins'] = [c for p in pins for c in p]
    add_outline(obj, width=STRING_LINE)


def build(col):
    for sx in (1, -1):
        _build_side(col, sx)
    skin, smooth = _Skin(), _Skin(STRING_SKIN_SUBDIV)
    try:
        loop = _choker_loop(skin)
        _choker(col, loop)
        _strings(col, smooth, loop, skin)
    finally:
        skin.free()
        smooth.free()
