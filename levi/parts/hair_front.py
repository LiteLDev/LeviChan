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
    (17, 8, 266, 310),
    (20, 14, 258, 320),
    (24, 21, 251, 329),
    (29, 27, 245, 337),
    (35, 34, 241, 343),
    (42, 40, 237, 348),
    (50, 47, 233, 353),
    (60, 55, 229, 357),
    (72, 60, 226, 360),
    (86, 63, 228, 361),
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
    n_az = 24
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
def catmull(pts, samples):
    """Centripetal Catmull-Rom through pts, resampled evenly by arc length."""
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
    for s in range(samples):
        target = total * s / (samples - 1)
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


def strand(bm, ctrl, width, thick, segs=10, n=6, base_taper=0.25, tip_pow=0.8,
           normal=head_normal, tip_from=0.0, back=1.0, wrap=0.0, tip_thick=0.35):
    """Append a flattened, tapered tube along `ctrl` to bm.

    width/thick: full width and thickness (m) at the widest point.
    tip_from: fraction of the length kept at full width before the tip taper.
    tip_thick: share of the thickness kept toward the tip (lower = the tip
    thins out with the width instead of ending in a thick wall).
    back: thickness of the inner (-normal) half relative to the outer half;
    < 1 gives a rounded wedge: a domed outer face over a flatter underside.
    wrap: how far the two edges curl back toward the head (x width), so a
    broad clump is a curved shell across its width instead of a flat plate.
    Tip is closed by a single apex vertex; the root is capped flat."""
    tip_from = min(max(tip_from, 0.0), 0.9)
    pts = catmull(ctrl, segs + 1)
    rings = []
    prev_b = None
    for i, p in enumerate(pts[:-1]):
        t = i / segs
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
        tip = (1 - max(0.0, t - tip_from) / (1 - tip_from)) ** tip_pow
        w = 0.5 * width * sw * tip
        h = 0.5 * thick * sw * max(tip, tip_thick)
        ring = []
        for k in range(n):
            a = 2 * math.pi * k / n
            sa, ca = math.sin(a), math.cos(a)
            off = sa * h * (1.0 if sa > 0 else back) - wrap * w * ca * ca
            ring.append(bm.verts.new(p + b * (ca * w) + nrm * off))
        rings.append(ring)
    apex = bm.verts.new(pts[-1])
    for a, c in zip(rings, rings[1:]):
        for k in range(n):
            kk = (k + 1) % n
            bm.faces.new((a[k], a[kk], c[kk], c[k]))
    for k in range(n):
        bm.faces.new((rings[-1][k], rings[-1][(k + 1) % n], apex))
    bm.faces.new(list(reversed(rings[0])))


def finish(col, name, bm, mat, grad_fn=None, angle=70, keep=VOL_KEEP):
    """Mesh object from bm; grad_fn=None leaves it all white (toon_grad 0).

    keep: share of the strands' own normals in the custom normals (the rest is
    the smooth hair-volume normal, see volume_normal)."""
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    obj = common.new_object(col, name, bm, [mat])
    if grad_fn is not None:
        common.set_gradient(obj, grad_fn)
    common.shade_smooth(obj, angle)
    set_volume_normals(obj.data, keep)
    common.add_outline(obj)
    return obj


def zgrad(row_start, row_full):
    """Gradient fn: white above row_start, fully green by row_full."""
    return common.z_gradient(P(0, row_start, 0).z, P(0, row_full, 0).z)


def mirror_pts(pts):
    return [Vector((-p.x, p.y, p.z)) for p in pts]


# ---------------------------------------------------------------- layout
def crown_clumps(bm):
    """A few broad, flat clumps radiating from the crown over the cap (white):
    the sheet's crown is a soft mass with only a few clump lines."""
    for az, end_row, w in (
            (-50, 96, 0.056), (-10, 120, 0.060), (30, 140, 0.062), (70, 156, 0.064),
            (-130, 96, 0.056), (-170, 120, 0.060), (150, 140, 0.062), (110, 156, 0.064)):
        ctrl = []
        for k in range(6):
            t = k / 5
            row = 19 + (end_row - 19) * t
            ctrl.append(cap_point(az, row, grow=0.0025 * (1 - t) + 0.0015 * math.sin(math.pi * t)))
        strand(bm, ctrl, w * 1.2, 0.007, segs=7, back=0.3, wrap=0.15)


BANG_NORMAL = Vector((0, -1, 0.25)).normalized()


def bang_normal(p):
    """Bangs face the front; the outer ones turn toward their side so they
    read as a mass, not edge-on slivers, in the side view."""
    return (BANG_NORMAL + Vector((0.6 * p.x / (40 * PX), 0, 0))).normalized()


def on_cap(fx, row, lift=4):
    """Point `lift` px in front of the cap's front surface."""
    return P(fx, row, cap_front_sc(fx, row) - lift)


# Front-most side-view column of the face skin vs |front offset|, rows ~80-120
# (measured on the round-2 head mesh; unit `head` owns it, so it is a local
# constant here). The bang tips keep a small air gap in front of it.
FACE_FRONT = ((0, 240), (10, 241), (20, 245), (30, 254), (40, 268), (46, 290))
BANG_TIP_GAP = 7        # px in front of the skin at the tips
BANG_BULGE = 18         # px in front of the skin where the fringe arches out (row 84)


def face_front_sc(fx):
    t = FACE_FRONT
    a = abs(fx)
    for (x0, s0), (x1, s1) in zip(t, t[1:]):
        if a <= x1:
            return s0 + (s1 - s0) * (a - x0) / (x1 - x0)
    return t[-1][1]


# A few broad clumps of varied width and length (sheet: the longest falls
# between the eyes, slightly to the image-left), roots overlapping on the
# crown. (fx root, fx tip, tip row, width px, lift px). The lift layers the
# clumps so overlapping ones never share a surface: higher lift = on top.
BANG_CLUMPS = (
    (-3, -9, 125, 31, 6.0),     # dominant central clump
    (3, 4, 112, 16, 3.5),       # filler under the centre parting
    (10, 18, 105, 27, 5.0),
    (-17, -27, 100, 27, 5.0),
    (24, 36, 95, 23, 6.5),
    (-30, -41, 104, 21, 6.5),
    (35, 45, 114, 13, 4.0),     # thin temple locks between eye and temple
    (-36, -46, 110, 13, 4.0),
)


def bangs(bm):
    """The fringe: rounded-wedge clumps that leave the cap at the hairline,
    arch out over the forehead and come back to rest just in front of it."""
    for fx0, fx1, row1, wpx, lift in BANG_CLUMPS:
        tip = face_front_sc(fx1) - BANG_TIP_GAP
        fxm = fx0 + (fx1 - fx0) * 0.45
        bulge = min(face_front_sc(fxm) - BANG_BULGE, cap_front_sc(fxm, 84) - lift - 2)
        rowm = (84 + row1) / 2
        fxq = fx0 + (fx1 - fx0) * 0.75
        # roots lie flush on the cap (tangent to it) and only lift off it
        # toward the hairline, so the crown reads as one continuous surface
        ctrl = [on_cap(fx0 * 0.25, 21, 2.5), on_cap(fx0 * 0.6, 38, 2 + 0.3 * lift),
                on_cap(fx0 * 0.9 + (fx1 - fx0) * 0.1, 60, 0.75 * lift),
                P(fxm, 84, bulge),
                P(fxq, rowm, (bulge + tip) / 2 - 1),
                P(fx1, row1, tip)]
        strand(bm, ctrl, wpx * PX, 0.013, segs=10, n=8, base_taper=0.7, tip_pow=0.9,
               normal=bang_normal, tip_from=0.45, back=0.4, wrap=0.3, tip_thick=0.12)


def ahoge(bm):
    strand(bm, [P(-2, 32, 300), P(-1, 20, 284), P(0, 15, 266), P(1, 13, 256)],
           0.016, 0.007, segs=7, base_taper=1.0, tip_pow=0.7,
           normal=lambda p: Vector((1, 0, 0)))
    strand(bm, [P(4, 34, 304), P(6, 23, 290), P(5, 17, 274)],
           0.012, 0.006, segs=5, base_taper=1.0, tip_pow=0.7,
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
    ([(38, 48, 252), (52, 72, 252), (50, 96, 258), (48, 118, 266), (50, 136, 276),
      (54, 148, 284), (59, 154, 289)], 0.030),
    ([(46, 52, 262), (60, 78, 262), (57, 104, 268), (55, 126, 278), (57, 140, 286),
      (62, 148, 292)], 0.032),
]
WISP_LOCKS = [
    # outer wisps flaring out at rows 115-140 (front), behind the eye (side),
    # tips curling outward and up
    ([(52, 48, 270), (63, 82, 272), (73, 106, 276), (81, 124, 280), (86, 134, 283),
      (90, 139, 285), (93, 136, 286)], 0.032),
    ([(58, 58, 288), (70, 94, 288), (80, 118, 290), (85, 130, 292), (89, 135, 293),
      (92, 132, 294)], 0.030),
]
FRONT_LONG = [
    # A: hangs behind the face frame (outside the ear) down past the chin,
    # then swings forward into the lock in front of the shoulder
    ([(52, 60, 276), (66, 96, 284), (63, 130, 290), (64, 148, 288), (67, 162, 278),
      (70, 176, 263), (73, 192, 247), (74, 208, 238), (74, 224, 240)], 0.042),
    # B, C: stay behind the neck down to the choker, then swing forward to
    # fill out the lock in front of the shoulder
    ([(56, 66, 272), (66, 104, 280), (63, 138, 292), (66, 160, 302), (71, 184, 302),
      (77, 200, 266), (78, 214, 250), (78, 230, 250)], 0.046),
    ([(58, 70, 278), (66, 112, 280), (66, 150, 296), (70, 182, 304), (78, 204, 264),
      (80, 220, 260)], 0.042),
]
CURL_LOCK = ([(60, 70, 282), (66, 100, 284), (64, 130, 286), (62, 150, 288), (70, 174, 288),
              (76, 188, 288), (86, 201, 290), (93, 207, 290), (103, 213, 290), (118, 219, 292),
              (128, 224, 292), (133, 230, 292), (131, 241, 292), (123, 248, 292),
              (116, 244, 292)], 0.030)
SIDE_CURTAIN = [
    ([(56, 62, 300), (62, 110, 298), (64, 160, 298), (66, 200, 300)], 0.032),
    ([(58, 70, 322), (62, 120, 320), (64, 165, 320), (64, 200, 320)], 0.032),
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


def side_set(bm, defs, segs, thick, mirror, forward=1.2, tip_pow=0.8, lateral=False,
             tip_from=0.0, back=1.0, wrap=0.0):
    """forward: how much the ribbons turn to face the front (0 = face out
    sideways, broad in the side view). back / wrap: see strand()."""
    def nfn(p):
        return lock_normal(p, forward, lateral)
    for ctrl, w in defs:
        pts = [P(*c) for c in ctrl]
        # sink the root into the cap so no flat root cap shows
        pts[0] = pts[0].lerp(Vector((0.0, HEAD_AXIS.y, pts[0].z)), 0.3)
        if mirror:
            pts = mirror_pts(pts)
        strand(bm, pts, w, thick, segs=segs, base_taper=0.3, tip_pow=tip_pow, normal=nfn,
               tip_from=tip_from, back=back, wrap=wrap)


def build(col):
    mat = common.toon_material('hair', gradient='hair_tip')

    build_cap(col, mat)

    bm = bmesh.new()
    crown_clumps(bm)
    ahoge(bm)
    finish(col, 'hair_crown', bm, mat)

    bm = bmesh.new()
    bangs(bm)
    finish(col, 'hair_bangs', bm, mat)

    for side, mirror in (('L', False), ('R', True)):
        bm = bmesh.new()
        side_set(bm, CHEEK_LOCKS, 9, 0.014, mirror, forward=0.7, tip_pow=0.6, lateral=True,
                 back=0.6, wrap=0.2)
        side_set(bm, WISP_LOCKS, 8, 0.012, mirror, forward=0.6, tip_pow=0.45, wrap=0.15)
        finish(col, f'hair_cheek_{side}', bm, mat, zgrad(108, 146))

        bm = bmesh.new()
        side_set(bm, FRONT_LONG, 16, 0.022, mirror, forward=0.9, tip_pow=0.7, lateral=True,
                 tip_from=0.55, back=0.7, wrap=0.15)
        finish(col, f'hair_lock_{side}', bm, mat, zgrad(180, 222))

        bm = bmesh.new()
        side_set(bm, [CURL_LOCK], 26, 0.012, mirror, tip_pow=0.35)
        finish(col, f'hair_curl_{side}', bm, mat, zgrad(196, 228))

        bm = bmesh.new()
        side_set(bm, SIDE_CURTAIN, 7, 0.014, mirror)
        finish(col, f'hair_curtain_{side}', bm, mat, zgrad(175, 225))
