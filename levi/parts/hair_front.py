"""Front and side hair: scalp cap, ahoge, bangs and the face-framing side locks.

Everything is built from clumped strand ribbons (flattened tubes with real
thickness, so they still read edge-on in the side view) laid over a closed
superellipsoid scalp cap. Inner hair lines come from the strands' own
inverted-hull outlines where they overlap the cap and each other.

Shapes are authored directly in reference-panel pixels so they can be fitted
against ref/{front,side}.png:  P(fx, row, sc)
    fx  = front-view column offset from the panel centre (+ = image right,
          i.e. the character's left, +X)
    row = panel row (shared by all views)
    sc  = side-view panel column (smaller = further forward, -Y)
The long hair below the shoulders is unit `hair_back`; leaves/flowers are
`accessories`.
"""
import math

import bmesh
from mathutils import Vector

from .. import common, spec

PX = 1.0 / spec.PX_PER_M
MID = spec.PANEL_W / 2


def P(fx, row, sc):
    """Reference-panel coordinates -> world point."""
    return Vector((fx * PX, (sc - MID) * PX, (spec.SHEET_GROUND_Y - row) * PX))


# ---------------------------------------------------------------- scalp cap
# Lofted from per-row profiles measured on the reference (net of the ~3 px the
# clumps and outline add): row -> (half width in the front view, front and
# back edge columns in the side view). Below the hairline the front of each
# section recedes behind the face so the face (unit `head`) shows between the
# bangs; the sides stay out as the hair beside the cheeks.
# spec.L['head_center_y'] (-38 px) / 'head_top_z' (row 30) are ~3 px and
# ~15 px off the hair mass measured here, so the cap uses its own numbers.
CAP_TOP = (14, 287)          # (row, side column) of the cap apex
CAP_PROFILE = [
    # row, half-width, side front col, side back col
    # Round 4: the crown clumps that used to sit ~4 px proud of the cap are
    # gone, so the front of rows 17-50 moves forward by that much to keep the
    # sheet's crown outline; rows 72-86 are set back 2-3 px so the fringe over
    # them reads less like a visor (the forehead skin stays >= 10 px behind).
    (17, 8, 263, 310),
    (20, 14, 254, 320),
    (24, 21, 247, 329),
    (29, 27, 241, 337),
    (35, 34, 237, 343),
    (42, 40, 233, 348),
    (50, 47, 230, 353),
    (60, 55, 229, 357),
    (72, 60, 229, 360),
    (86, 63, 231, 361),
    (100, 64, 242, 362),
    (116, 64, 262, 362),
    (132, 62, 278, 360),     # round 3: rows 132-172 pulled back ~6-8 px so the
    (148, 58, 284, 353),     # jaw and cheek show in the side view (the ear
    (162, 50, 288, 343),     # stays covered)
    (172, 36, 292, 330),
]
CAP_BOTTOM = (178, 305)
CAP_EXP = 2.3


def _profile(row):
    t = CAP_PROFILE
    if row <= t[0][0]:
        return t[0][1:]
    for (r0, *a), (r1, *b) in zip(t, t[1:]):
        if row <= r1:
            u = (row - r0) / (r1 - r0)
            return tuple(x + (y - x) * u for x, y in zip(a, b))
    return t[-1][1:]


def _se(v):
    return math.copysign(abs(v) ** (2.0 / CAP_EXP), v)


# Axis the ribbons are oriented around (radial above row 95, horizontal below).
HEAD_AXIS = P(0, 95, 292)


def cap_point(az, row, grow=0.0):
    """Point on the cap surface. az: 0 = +X, -90 = front (-Y); row: panel row.

    grow: outward offset in metres (radial from the head axis)."""
    w, f, b = _profile(row)
    a = math.radians(az)
    p = P(w * _se(math.cos(a)), row, (f + b) / 2 + (b - f) / 2 * _se(math.sin(a)))
    if grow:
        q = Vector((0.0, HEAD_AXIS.y, min(p.z, HEAD_AXIS.z)))
        p = p + (p - q).normalized() * grow
    return p


def cap_front_sc(fx, row):
    """Side-view column of the cap's front surface at front offset fx."""
    w, f, b = _profile(row)
    u = min(1.0, abs(fx) / w)
    return (f + b) / 2 - (b - f) / 2 * (1 - u ** CAP_EXP) ** (1 / CAP_EXP)


def build_cap(col, mat):
    n_az = 26
    bm = bmesh.new()
    top = bm.verts.new(P(0, *CAP_TOP))
    bot = bm.verts.new(P(0, *CAP_BOTTOM))
    rings = [[bm.verts.new(cap_point(-90 + 360.0 * i / n_az, r[0])) for i in range(n_az)]
             for r in CAP_PROFILE]
    for i in range(n_az):
        k = (i + 1) % n_az
        bm.faces.new((top, rings[0][k], rings[0][i]))
        for a, b in zip(rings, rings[1:]):
            bm.faces.new((a[i], a[k], b[k], b[i]))
        bm.faces.new((rings[-1][i], rings[-1][k], bot))
    return finish(col, 'hair_cap', bm, mat, angle=80)


# ---------------------------------------------------------------- normals
# The sheet shades the hair as one soft mass: almost all of it lit, with thin
# shade accents along clump edges, not a shade block on every strand that
# turns away from the key light. The custom normals are therefore mostly the
# normal of a smooth volume around the head (an ellipsoid above its centre, a
# vertical elliptic cylinder below it, for the hanging locks), tilted forward
# on the sides, plus VOL_KEEP of each strand's own normal for the accents.
VOL_CENTER = P(0, 100, 296)
VOL_AXES = (66 * PX, 70 * PX, 86 * PX)
VOL_FORWARD = 0.55      # forward (-Y) tilt of the side-facing volume normals
VOL_KEEP = 0.3


def volume_normal(p):
    d = p - VOL_CENTER
    ax, ay, az = VOL_AXES
    n = Vector((d.x / ax ** 2, d.y / ay ** 2, max(d.z, 0.0) / az ** 2))
    if n.length < 1e-9:
        return Vector((0, -1, 0))
    n.normalize()
    # tilt the sides toward the front (scaled by how sideways they face, so
    # the back of the head keeps facing back)
    side = abs(n.x) * (1 - max(0.0, n.y))
    n = n + Vector((0, -VOL_FORWARD * side, 0))
    return n.normalized()


def set_volume_normals(me, keep):
    normals = []
    for v in me.vertices:
        n = volume_normal(v.co) * (1 - keep) + v.normal * keep
        normals.append(n.normalized() if n.length > 1e-9 else Vector(v.normal))
    me.normals_split_custom_set_from_vertices(normals)


# ---------------------------------------------------------------- strands
def arc_params(samples, tip_dense=0.0):
    """Arc-length fractions 0..1 for `samples` points; tip_dense > 0 packs them
    toward the end (spacing x(1 + tip_dense) at the root, x(1 - tip_dense) at
    the tip) so a rounded tip gets rings without adding segments."""
    out = []
    for s in range(samples):
        x = s / (samples - 1)
        out.append(x + tip_dense * math.sin(math.pi * x) / math.pi)
    return out


def catmull(pts, samples, tip_dense=0.0):
    """Centripetal Catmull-Rom through pts, resampled by arc length (evenly, or
    denser toward the end, see arc_params)."""
    pts = [Vector(p) for p in pts]
    ext = [pts[0] * 2 - pts[1]] + pts + [pts[-1] * 2 - pts[-2]]
    dense = []
    for i in range(1, len(ext) - 2):
        p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
        t0 = 0.0
        t1 = t0 + max((p1 - p0).length, 1e-6) ** 0.5
        t2 = t1 + max((p2 - p1).length, 1e-6) ** 0.5
        t3 = t2 + max((p3 - p2).length, 1e-6) ** 0.5
        for k in range(16):
            t = t1 + (t2 - t1) * k / 16
            a1 = p0 * ((t1 - t) / (t1 - t0)) + p1 * ((t - t0) / (t1 - t0))
            a2 = p1 * ((t2 - t) / (t2 - t1)) + p2 * ((t - t1) / (t2 - t1))
            a3 = p2 * ((t3 - t) / (t3 - t2)) + p3 * ((t - t2) / (t3 - t2))
            b1 = a1 * ((t2 - t) / (t2 - t0)) + a2 * ((t - t0) / (t2 - t0))
            b2 = a2 * ((t3 - t) / (t3 - t1)) + a3 * ((t - t1) / (t3 - t1))
            dense.append(b1 * ((t2 - t) / (t2 - t1)) + b2 * ((t - t1) / (t2 - t1)))
    dense.append(pts[-1])
    acc = [0.0]
    for a, b in zip(dense, dense[1:]):
        acc.append(acc[-1] + (b - a).length)
    total = acc[-1]
    out, j = [], 0
    for f in arc_params(samples, tip_dense):
        target = total * f
        while j < len(acc) - 2 and acc[j + 1] < target:
            j += 1
        seg = acc[j + 1] - acc[j]
        u = 0.0 if seg <= 0 else (target - acc[j]) / seg
        out.append(dense[j].lerp(dense[j + 1], min(1.0, max(0.0, u))))
    return out


def head_normal(p):
    """Outward direction used to orient ribbons: radial from the cap centre
    above it, horizontal-radial from the head axis below it."""
    q = Vector((0.0, HEAD_AXIS.y, min(p.z, HEAD_AXIS.z)))
    n = p - q
    if n.length < 1e-6:
        return Vector((0, -1, 0))
    return n.normalized()


def grad_layer(bm):
    """The bmesh float layer that becomes the 'toon_grad' point attribute."""
    return bm.verts.layers.float.get(common.GRAD_ATTR) or bm.verts.layers.float.new(common.GRAD_ATTR)


def strand(bm, ctrl, width, thick, segs=10, n=6, base_taper=0.25, tip_pow=0.8,
           normal=head_normal, tip_from=0.0, back=1.0, wrap=0.0, tip_thick=0.35,
           ogive=1.0, tip_dense=0.0, grad=None):
    """Append a flattened, tapered tube along `ctrl` to bm.

    width/thick: full width and thickness (m) at the widest point.
    tip_from: fraction of the length kept at full width before the tip taper.
    tip_pow / ogive: tip width profile (1 - u**ogive)**tip_pow over the taper
    (u 0..1). ogive 1 is a straight wedge; ~2 keeps the width longer and
    closes it in a rounded arc, so tips read soft instead of as sawteeth.
    tip_dense: packs rings toward the tip (see arc_params).
    tip_thick: share of the thickness kept toward the tip (lower = the tip
    thins out with the width instead of ending in a thick wall).
    back: thickness of the inner (-normal) half relative to the outer half;
    < 1 gives a rounded wedge: a domed outer face over a flatter underside.
    wrap: how far the two edges curl back toward the head (x width), so a
    broad clump is a curved shell across its width instead of a flat plate.
    grad: (start, end) arc-length fractions of the white-to-mint 'toon_grad'
    ramp along this strand (smoothstep; None keeps it white), so the tint
    follows each lock's own flow instead of a shared world height.
    Tip is closed by a single apex vertex; the root is capped flat."""
    tip_from = min(max(tip_from, 0.0), 0.9)
    pts = catmull(ctrl, segs + 1, tip_dense)
    params = arc_params(segs + 1, tip_dense)
    layer = grad_layer(bm)

    def gval(t):
        if grad is None:
            return 0.0
        g = max(0.0, min(1.0, (t - grad[0]) / (grad[1] - grad[0])))
        return g * g * (3 - 2 * g)

    rings = []
    prev_b = None
    for i, p in enumerate(pts[:-1]):
        t = params[i]
        tan = (pts[min(i + 1, segs)] - pts[max(i - 1, 0)]).normalized()
        nrm = normal(p)
        nrm = (nrm - tan * nrm.dot(tan))
        if nrm.length < 1e-6:
            nrm = tan.orthogonal()
        nrm.normalize()
        b = tan.cross(nrm).normalized()
        if prev_b is not None and b.dot(prev_b) < 0:
            b = -b
        prev_b = b
        # width profile: quick swell from the root, long taper to the tip
        sw = min(1.0, base_taper + (1 - base_taper) * min(1.0, t / 0.18))
        u = max(0.0, t - tip_from) / (1 - tip_from)
        tip = max(0.0, 1 - u ** ogive) ** tip_pow
        w = 0.5 * width * sw * tip
        h = 0.5 * thick * sw * max(tip, tip_thick)
        gv = gval(t)
        ring = []
        for k in range(n):
            a = 2 * math.pi * k / n
            sa, ca = math.sin(a), math.cos(a)
            off = sa * h * (1.0 if sa > 0 else back) - wrap * w * ca * ca
            v = bm.verts.new(p + b * (ca * w) + nrm * off)
            v[layer] = gv
            ring.append(v)
        rings.append(ring)
    apex = bm.verts.new(pts[-1])
    apex[layer] = gval(1.0)
    for a, c in zip(rings, rings[1:]):
        for k in range(n):
            kk = (k + 1) % n
            bm.faces.new((a[k], a[kk], c[kk], c[k]))
    for k in range(n):
        bm.faces.new((rings[-1][k], rings[-1][(k + 1) % n], apex))
    bm.faces.new(list(reversed(rings[0])))


def finish(col, name, bm, mat, angle=70, keep=VOL_KEEP):
    """Mesh object from bm. toon_grad comes from the strands' own arc-length
    ramp (strand(grad=...)).

    keep: share of the strands' own normals in the custom normals (the rest is
    the smooth hair-volume normal, see volume_normal)."""
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    obj = common.new_object(col, name, bm, [mat])
    common.shade_smooth(obj, angle)
    set_volume_normals(obj.data, keep)
    common.add_outline(obj)
    return obj


def mirror_pts(pts):
    return [Vector((-p.x, p.y, p.z)) for p in pts]


# ---------------------------------------------------------------- layout
# The crown is the cap itself: one smooth scalp volume. Round 4 dropped the
# separate crown clumps (their overlapping edges read as stepped plates from
# above); the soft clump lines over the crown are the bang roots, which start
# buried in the cap and surface gradually (see bangs()).
def cap_front_point(fx, row, grow):
    """Point on the cap's front surface at front offset fx, moved `grow` px
    outward along head_normal (negative = buried inside the cap)."""
    p = P(fx, row, cap_front_sc(fx, row))
    return p + head_normal(p) * (grow * PX)


BANG_NORMAL = Vector((0, -1, 0.25)).normalized()


def bang_normal(p):
    """Bangs face the front; the outer ones turn toward their side so they
    read as a mass, not edge-on slivers, in the side view."""
    return (BANG_NORMAL + Vector((0.6 * p.x / (40 * PX), 0, 0))).normalized()


# Front-most side-view column of the face skin vs |front offset|, rows ~80-120
# (measured on the round-2 head mesh; unit `head` owns it, so it is a local
# constant here). The bang tips keep a small air gap in front of it.
FACE_FRONT = ((0, 240), (10, 241), (20, 245), (30, 254), (40, 268), (46, 290))
BANG_TIP_GAP = 6        # px in front of the skin at the tips
BANG_BULGE = 15         # px in front of the skin where the fringe arches out (row 84)


def face_front_sc(fx):
    t = FACE_FRONT
    a = abs(fx)
    for (x0, s0), (x1, s1) in zip(t, t[1:]):
        if a <= x1:
            return s0 + (s1 - s0) * (a - x0) / (x1 - x0)
    return t[-1][1]


# A few broad, overlapping clumps of varied width and length (sheet: the
# longest falls between the eyes, slightly to the image-left; the outer pair
# frame the face past the outer eye corners). Roots converge on the crown.
# (fx root, fx tip, tip row, width px, lift px, tip roundness, taper start,
# kind). The lift layers the clumps so overlapping ones never share a
# surface: higher lift = on top. Roundness is strand()'s `ogive`: higher keeps
# the width longer and closes the tip in an arc, so neighbouring tips differ
# instead of forming a row of identical teeth. kind: 'in' = inner clump rooted
# at the crown; 'out' = outer clump (thinner, arches out less, so the brow
# doesn't read as a visor, rooted part way down the crown); 'temple' = outer
# lock rooted near the temple. Only the inner clumps start at the crown, so no
# long root seams run down the sides of the crown.
BANG_CLUMPS = (
    (-3, -7, 127, 24, 7.0, 1.4, 0.3, 'in'),      # dominant central lock, on top
    (5, 12, 108, 22, 4.0, 2.4, 0.4, 'in'),       # right of the centre parting
    (-15, -23, 101, 28, 5.0, 2.2, 0.38, 'in'),   # shorter over the eyes, so the
    (19, 28, 98, 28, 5.5, 2.0, 0.4, 'in'),       # tip rows vary by ~3 cm
    (-29, -38, 114, 26, 6.0, 1.9, 0.5, 'out'),
    (31, 40, 110, 24, 6.5, 2.3, 0.5, 'out'),
    (35, 44, 124, 17, 3.5, 1.7, 0.55, 'temple'),  # past the outer eye corners
    (-37, -45, 126, 17, 3.5, 1.7, 0.55, 'temple'),
)
OUTER_BULGE_LESS = 4    # px less forward arch on the outer clumps
# Root emergence: four stations from the buried root to the hairline. Each
# grows (base px + share x lift) off the cap, so overlapping roots are already
# layered by their lift where their domes surface; ROOT_FX / ROOT_FX_TIP place
# them between the root and fx0 (and toward fx1).
ROOT_GROW = ((-5.0, 0.0), (-3.5, 0.1), (-1.6, 0.25), (-0.6, 0.45))
ROOT_FX = (0.0, 0.45, 0.75, 0.95)
ROOT_FX_TIP = (0.0, 0.0, 0.03, 0.1)
# per kind: (station rows, share of fx0 the root starts at)
ROOTS = {'in': ((20, 38, 54, 68), 0.25),
         'out': ((28, 42, 56, 70), 0.55),
         'temple': ((34, 46, 58, 70), 0.7)}


def bangs(bm):
    """The fringe: rounded-wedge clumps that leave the cap at the hairline,
    arch out over the forehead and come back to rest just in front of it.

    Each root starts with its whole section buried in the cap and surfaces
    tangentially over ~30 rows; the curled-back edges (wrap) stay under the
    cap longest, so only a soft middle ridge emerges and the crown keeps one
    surface."""
    for fx0, fx1, row1, wpx, lift, rnd, tf, kind in BANG_CLUMPS:
        outer = kind != 'in'
        tip = face_front_sc(fx1) - BANG_TIP_GAP
        fxm = fx0 + (fx1 - fx0) * 0.45
        # On the forehead the cap (which recedes behind the face only below
        # the hairline) usually binds; the face term only limits where the cap
        # is set back. Outer clumps then sit OUTER_BULGE_LESS px further back.
        bulge = min(face_front_sc(fxm) - BANG_BULGE, cap_front_sc(fxm, 84) - lift - 2)
        if outer:
            bulge += OUTER_BULGE_LESS
        rowm = (84 + row1) / 2
        fxq = fx0 + (fx1 - fx0) * 0.75
        rows, share = ROOTS[kind]
        fxr = fx0 * share
        ctrl = [cap_front_point(fxr + (fx0 - fxr) * a + (fx1 - fx0) * b, row, g0 + g1 * lift)
                for row, (g0, g1), a, b in zip(rows, ROOT_GROW, ROOT_FX, ROOT_FX_TIP)]
        ctrl += [P(fxm, 84, bulge),
                 P(fxq, rowm, (bulge + tip) / 2 - 1),
                 P(fx1, row1, tip)]
        strand(bm, ctrl, wpx * PX, 0.009 if outer else 0.011, segs=10, n=8, base_taper=0.7,
               tip_pow=0.75, ogive=rnd, tip_dense=0.5, normal=bang_normal, tip_from=tf,
               back=0.4, wrap=0.25, tip_thick=0.1)


def ahoge(bm):
    """Two crown tufts; the roots start inside the cap."""
    strand(bm, [P(-2, 32, 300), P(-1, 20, 284), P(0, 14, 268), P(1, 11, 261)],
           0.016, 0.007, segs=9, base_taper=0.6, tip_pow=0.8, ogive=1.6, tip_dense=0.4,
           tip_from=0.3, normal=lambda p: Vector((1, 0, 0)))
    strand(bm, [P(4, 34, 304), P(6, 23, 290), P(5, 17, 274)],
           0.012, 0.006, segs=5, base_taper=0.6, tip_pow=0.8, ogive=1.4,
           normal=lambda p: Vector((1, 0, 0)))


# Side locks for the character's left (+X, image right); mirrored for the right.
# ctrl points (fx, row, sc), full width (m). The side view of the sheet shows
# the face clear from the nose back to col ~260 (rows 90-155), with only a
# short cheek lock behind the eye: every lock stays behind that line.
CHEEK_LOCKS = [
    # Beside the cheek, behind the eye in the side view (the face shows from
    # the nose back to col ~255). They leave the cap at the temple, come in
    # toward the cheek, and turn their green tips outward at jaw level.
    # Below the cheekbone they drift back toward the ear so the jaw stays
    # clear in the side view while the front view still sees them beside it.
    # Round 4: the last ~2 cm open into a shallow outward C-curve with a
    # small upward turn at the tip (sheet: soft cheek-level curls).
    ([(38, 48, 252), (52, 72, 252), (50, 96, 258), (48, 116, 265), (50, 132, 273),
      (55, 143, 280), (62, 149, 286), (68, 147, 289), (71, 142, 291)], 0.030),
    ([(46, 52, 262), (60, 78, 262), (57, 104, 268), (55, 124, 277), (58, 137, 285),
      (64, 144, 290), (69, 141, 293), (71, 136, 295)], 0.032),
]
WISP_LOCKS = [
    # outer wisps flaring out at rows 115-140 (front), behind the eye (side);
    # they keep falling as they flare, and only the last ~1 cm turns softly
    # back up toward the head (no horizontal spike)
    ([(52, 48, 270), (63, 82, 272), (71, 104, 276), (77, 120, 280), (82, 131, 283),
      (86, 138, 285), (88, 139, 287), (89, 136, 289)], 0.028),
    ([(58, 58, 288), (70, 94, 288), (78, 116, 290), (83, 128, 292), (86, 134, 294),
      (87, 133, 296), (86, 129, 297)], 0.026),
]
# The lock in front of each shoulder: a two-strand bundle. The dominant
# S-shaped lock (A) turns forward gradually over rows ~148-218; the support
# (B) runs ~5 px deeper and a little further out, turns later and ends ~1.5 cm
# higher, so the two read as layered hair rather than one crowded bend.
FRONT_LONG_MAIN = [
    # A: hangs behind the face frame (outside the ear) down past the chin,
    # then swings forward into the lock in front of the shoulder
    ([(52, 60, 276), (66, 96, 284), (64, 130, 290), (65, 148, 288), (67, 162, 278),
      (70, 176, 264), (73, 190, 250), (75, 203, 243), (77, 215, 240), (80, 226, 240)], 0.032),
]
FRONT_LONG_SUPPORT = [
    ([(56, 66, 272), (66, 104, 282), (64, 138, 292), (67, 156, 298), (71, 174, 294),
      (75, 190, 282), (78, 203, 268), (81, 212, 260), (83, 219, 256)], 0.026),
]
# The outward shoulder curl: round 4 gives it a rounder section (8 sides,
# thicker) and a wider, more gradual terminal turn instead of a tight hook.
CURL_LOCK = ([(60, 70, 282), (66, 100, 284), (64, 130, 286), (62, 150, 288), (70, 174, 288),
              (76, 188, 288), (86, 201, 290), (95, 208, 290), (106, 214, 290), (118, 220, 291),
              (127, 226, 292), (132, 233, 292), (131, 241, 292), (126, 246, 292),
              (120, 246, 292)], 0.028)
# One strand behind the face frame filling the gap to the back hair (round 4
# dropped the second, deeper one: it only added a step at the temple).
SIDE_CURTAIN = [
    ([(56, 62, 300), (62, 110, 298), (64, 160, 298), (66, 200, 300)], 0.032),
]


def lock_normal(p, forward=1.2, lateral=False):
    """Side locks face half forward, so they read broad in front and side.

    lateral: start from the pure sideways direction (+-X) instead of the
    head-radial one. Locks hanging in front of the head axis (beside the face,
    in front of the shoulder) would otherwise turn edge-on to the side view."""
    if lateral:
        n = Vector((math.copysign(1.0, p.x), 0.0, 0.0))
    else:
        n = head_normal(p)
        n = Vector((n.x, n.y, 0.0)) if abs(n.x) + abs(n.y) > 1e-6 else Vector((1, 0, 0))
    return (n.normalized() + Vector((0, -forward, 0))).normalized()


ROOT_SINK = 5.0         # px the first control point is pushed into the cap
ROOT_BURY = (12, 4)     # extra root point: px back up along the cap, px into it


def side_set(bm, defs, segs, thick, mirror, forward=1.2, lateral=False, **kw):
    """forward: how much the ribbons turn to face the front (0 = face out
    sideways, broad in the side view). Other keywords go to strand().

    The root is buried: an extra control point continues the lock back up
    along the cap (tangentially, just under its surface), so the narrow first
    rings sit inside it and the lock surfaces at a shallow angle instead of
    being cut off by the cap in a step. The strand's arc-length fractions
    (tip_from, grad) include this hidden ~12-17 px root, so the visible ramps
    start a little earlier than the numbers; they are tuned per family."""
    def nfn(p):
        return lock_normal(p, forward, lateral)
    for ctrl, w in defs:
        pts = [P(*c) for c in ctrl]
        n0 = head_normal(pts[0])
        p0 = pts[0] - n0 * (ROOT_SINK * PX)
        up = p0 - pts[1]
        up = up - n0 * up.dot(n0)
        if up.length < 1e-6:        # lock leaves the cap radially: go straight up
            up = Vector((0.0, 0.0, 1.0)) - n0 * n0.z
        up.normalize()
        root = p0 + up * (ROOT_BURY[0] * PX)
        root = root - head_normal(root) * (ROOT_BURY[1] * PX)
        pts = [root, p0] + pts[1:]
        if mirror:
            pts = mirror_pts(pts)
        strand(bm, pts, w, thick, segs=segs, normal=nfn, **kw)


# Normal blend per family (finish(keep=...)): the cap and fringe keep the
# smooth scalp volume; the hanging locks keep more of their own rounded
# section so they read as bundles, not flat plates, at oblique angles.
LOCK_KEEP = 0.6


def build(col):
    mat = common.toon_material('hair', gradient='hair_tip')

    build_cap(col, mat)

    bm = bmesh.new()
    ahoge(bm)
    finish(col, 'hair_crown', bm, mat)

    bm = bmesh.new()
    bangs(bm)
    finish(col, 'hair_bangs', bm, mat)

    for side, mirror in (('L', False), ('R', True)):
        bm = bmesh.new()
        side_set(bm, CHEEK_LOCKS, 10, 0.015, mirror, forward=0.7, lateral=True, n=8,
                 base_taper=0.3, tip_pow=0.7, ogive=1.8, tip_dense=0.5, tip_from=0.5,
                 back=0.7, wrap=0.1, tip_thick=0.12, grad=(0.62, 1.0))
        side_set(bm, WISP_LOCKS, 9, 0.014, mirror, forward=0.6, n=8,
                 base_taper=0.3, tip_pow=0.6, ogive=1.6, tip_dense=0.6, tip_from=0.35,
                 back=0.8, wrap=0.08, tip_thick=0.12, grad=(0.62, 1.0))
        finish(col, f'hair_cheek_{side}', bm, mat, keep=LOCK_KEEP)

        bm = bmesh.new()
        # near-round sections (width / thickness ~1.3) so the locks read as
        # bundles from every angle, not as blades with a broad flat face;
        # the taper starts at mid-length so the ends thin out gradually
        side_set(bm, FRONT_LONG_MAIN, 22, 0.024, mirror, forward=0.9, lateral=True, n=10,
                 base_taper=0.3, tip_pow=0.8, ogive=1.8, tip_dense=0.3, tip_from=0.5,
                 back=0.85, wrap=0.05, tip_thick=0.1, grad=(0.45, 1.0))
        side_set(bm, FRONT_LONG_SUPPORT, 15, 0.019, mirror, forward=0.9, lateral=True, n=8,
                 base_taper=0.3, tip_pow=0.8, ogive=1.7, tip_dense=0.3, tip_from=0.5,
                 back=0.85, wrap=0.05, tip_thick=0.1, grad=(0.42, 1.0))
        finish(col, f'hair_lock_{side}', bm, mat, keep=LOCK_KEEP)

        bm = bmesh.new()
        side_set(bm, [CURL_LOCK], 25, 0.018, mirror, n=8, base_taper=0.3, tip_pow=0.6,
                 ogive=1.3, tip_from=0.3, tip_dense=0.3, back=0.85, tip_thick=0.15,
                 grad=(0.55, 0.85))
        finish(col, f'hair_curl_{side}', bm, mat, keep=LOCK_KEEP)

        bm = bmesh.new()
        # The curtain hangs behind the face frame and ends at the choker, well
        # above the other locks' green: its ramp ends past the tip (~45% mint
        # there), as the earlier height ramp did.
        side_set(bm, SIDE_CURTAIN, 8, 0.014, mirror, base_taper=0.3, grad=(0.78, 1.25))
        finish(col, f'hair_curtain_{side}', bm, mat)
