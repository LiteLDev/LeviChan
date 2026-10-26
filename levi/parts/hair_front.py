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

Round 5 (8k face budget): a smooth, denser scalp cap with a rounded apex;
strands with 10-12-sided sections, 14-30 rings, smoothly transported section
frames and separate thickness/wrap tapers; roots that are pressed onto the
actual cap surface (settle()) so each clump grows out of the scalp in one
smooth ridge instead of cutting through it.
"""
import math

import bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree

from .. import common, spec

PX = 1.0 / spec.PX_PER_M
MID = spec.PANEL_W / 2


def P(fx, row, sc):
    """Reference-panel coordinates -> world point."""
    return Vector((fx * PX, (sc - MID) * PX, (spec.SHEET_GROUND_Y - row) * PX))


def smooth01(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


# ---------------------------------------------------------------- scalp cap
# Lofted from per-row profiles measured on the reference (net of the ~3 px the
# clumps and outline add): row -> (half width in the front view, front and
# back edge columns in the side view). Below the hairline the front of each
# section recedes behind the face so the face (unit `head`) shows between the
# bangs; the sides stay out as the hair beside the cheeks.
# spec.L['head_center_y'] (-38 px) / 'head_top_z' (row 30) are ~3 px and
# ~15 px off the hair mass measured here, so the cap uses its own numbers.
# hair_back reads CAP_PROFILE / CAP_EXP (measurement data, keep the names).
CAP_TOP = (14, 287)          # (row, side column) of the cap apex
CAP_PROFILE = [
    # row, half-width, side front col, side back col
    # Round 4: the crown clumps that used to sit ~4 px proud of the cap are
    # gone, so the front of rows 17-50 moves forward by that much to keep the
    # sheet's crown outline; rows 72-86 are set back 2-3 px so the fringe over
    # them reads less like a visor (the forehead skin stays >= 10 px behind).
    # Round 5: rows 17-29 are ~1 px fuller so the crown closes as a dome.
    (17, 9, 263, 310),
    (20, 15, 254, 320),
    (24, 22, 247, 329),
    (29, 28, 241, 337),
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
# Round 5: ring rows (denser toward the apex, where the dome turns fastest)
# and sections around. The profile between the measured rows is a monotone
# cubic (no creases where the slope changes); above the first measured row a
# sqrt dome closes it with a vertical tangent at the apex instead of a cone.
# hair_back sizes its envelope ENV_OFF = 3 px over a piecewise-linear lookup
# of CAP_PROFILE; the cubic stands at most ~0.8 px (width / back) and ~1.3 px
# (front, under the fringe) outside that lookup, and the dome stays inside its
# row-17 clamp, so the envelope still covers the cap.
CAP_RINGS = (14.4, 15.1, 16.0, 17.0, 18.3, 19.8, 21.5, 23.4, 25.6, 28.0, 30.8, 34.0,
             37.6, 41.6, 46.0, 51.0, 56.5, 62.5, 69.0, 76.0, 84.0, 92.0, 100.0, 108.0,
             116.0, 124.0, 132.0, 140.0, 148.0, 155.0, 162.0, 167.5, 172.0, 175.6)
CAP_AZ = 40


def _pchip_slopes(xs, ys):
    """Fritsch-Carlson slopes: a monotone cubic through (xs, ys)."""
    n = len(xs)
    d = [(ys[i + 1] - ys[i]) / (xs[i + 1] - xs[i]) for i in range(n - 1)]
    m = [d[0]] + [0.0] * (n - 2) + [d[-1]]
    for i in range(1, n - 1):
        if d[i - 1] * d[i] <= 0:
            m[i] = 0.0
        else:
            h0, h1 = xs[i] - xs[i - 1], xs[i + 1] - xs[i]
            w1, w2 = 2 * h1 + h0, h1 + 2 * h0
            m[i] = (w1 + w2) / (w1 / d[i - 1] + w2 / d[i])
    return m


_ROWS = [r[0] for r in CAP_PROFILE]
_COLS = [[r[c] for r in CAP_PROFILE] for c in (1, 2, 3)]
_SLOPES = [_pchip_slopes(_ROWS, c) for c in _COLS]
_APEX = (0.0, CAP_TOP[1], CAP_TOP[1])     # half width, front col, back col at the apex


def _profile(row):
    """(half width, side front col, side back col) of the cap at `row`."""
    t = _ROWS
    if row <= t[0]:
        # dome: v = apex + a sqrt(d) + b d, matching value and slope at row t[0]
        d0 = t[0] - CAP_TOP[0]
        d = max(0.0, row - CAP_TOP[0])
        out = []
        for c, (ys, ms) in enumerate(zip(_COLS, _SLOPES)):
            delta, s = ys[0] - _APEX[c], ms[0]
            a = (delta - d0 * s) / (math.sqrt(d0) / 2)
            b = s - a / (2 * math.sqrt(d0))
            out.append(_APEX[c] + a * math.sqrt(d) + b * d)
        return tuple(out)
    if row >= t[-1]:
        return tuple(c[-1] for c in _COLS)
    i = next(k for k in range(len(t) - 1) if row <= t[k + 1])
    h = t[i + 1] - t[i]
    u = (row - t[i]) / h
    h00, h10 = 2 * u ** 3 - 3 * u ** 2 + 1, u ** 3 - 2 * u ** 2 + u
    h01, h11 = -2 * u ** 3 + 3 * u ** 2, u ** 3 - u ** 2
    return tuple(h00 * ys[i] + h10 * h * ms[i] + h01 * ys[i + 1] + h11 * h * ms[i + 1]
                 for ys, ms in zip(_COLS, _SLOPES))


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
    u = min(1.0, abs(fx) / max(w, 1e-6))
    return (f + b) / 2 - (b - f) / 2 * (1 - u ** CAP_EXP) ** (1 / CAP_EXP)


def build_cap(col, mat):
    """The scalp cap. Returns (object, BVH of its surface) so the strands can
    settle their roots onto it."""
    bm = bmesh.new()
    top = bm.verts.new(P(0, *CAP_TOP))
    bot = bm.verts.new(P(0, *CAP_BOTTOM))
    rings = [[bm.verts.new(cap_point(-90 + 360.0 * i / CAP_AZ, r)) for i in range(CAP_AZ)]
             for r in CAP_RINGS]
    for i in range(CAP_AZ):
        k = (i + 1) % CAP_AZ
        bm.faces.new((top, rings[0][k], rings[0][i]))
        for a, b in zip(rings, rings[1:]):
            bm.faces.new((a[i], a[k], b[k], b[i]))
        bm.faces.new((rings[-1][i], rings[-1][k], bot))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bvh = BVHTree.FromBMesh(bm)
    return finish(col, 'hair_cap', bm, mat, angle=80), bvh


# ---------------------------------------------------------------- normals
# The sheet shades the hair as one soft mass: almost all of it lit, with thin
# shade accents along clump edges, not a shade block on every strand that
# turns away from the key light. The custom normals are therefore mostly the
# normal of a smooth volume around the head (an ellipsoid above its centre, a
# vertical elliptic cylinder below it, for the hanging locks), tilted forward
# on the sides, plus `keep` of each strand's own normal for the accents.
VOL_CENTER = P(0, 100, 296)
VOL_AXES = (66 * PX, 70 * PX, 86 * PX)
VOL_FORWARD = 0.55      # forward (-Y) tilt of the side-facing volume normals
VOL_KEEP = 0.3
KEEP_ATTR = 'hf_keep'   # per-vertex `keep` written by strand(keep=...)
LINE_ATTR = 'hf_line'   # per-vertex outline weight (1; settle() fades the roots)
LINE_GROUP = 'hair_line'
LINE_MIN = 0.05         # outline width share where a root is still buried
LINE_ON = 0.7           # emergence (0..1) at which a root's outline starts
LINE_RAMP = 0.1         # ... reaching full width this much later: a short
                        # ramp, since a part-width hull line renders as a
                        # faint grey sliver that reads as a shade speck


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
    """keep: share of the mesh's own vertex normal; overridden per vertex by
    the KEEP_ATTR attribute when the strands wrote one (it is then removed)."""
    attr = me.attributes.get(KEEP_ATTR)
    ks = [d.value for d in attr.data] if attr is not None else None
    if attr is not None:
        me.attributes.remove(attr)
    normals = []
    for i, v in enumerate(me.vertices):
        k = ks[i] if ks is not None and ks[i] >= 0 else keep
        n = volume_normal(v.co) * (1 - k) + v.normal * k
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


def _layer(bm, name, default):
    """A float vertex layer; vertices made before it existed get `default`."""
    lay = bm.verts.layers.float.get(name)
    if lay is None:
        lay = bm.verts.layers.float.new(name)
        for v in bm.verts:
            v[lay] = default
    return lay


class Strand:
    """What strand() built: rings of BMVerts root -> tip (the apex is the last
    one-vertex ring) and the arc length (m) from the root to each ring."""

    def __init__(self, rings, arc):
        self.rings = rings
        self.arc = arc


def strand(bm, ctrl, width, thick, segs=10, n=6, base_taper=0.25, tip_pow=0.8,
           normal=head_normal, tip_from=0.0, back=1.0, wrap=0.0, tip_thick=0.35,
           ogive=1.0, tip_dense=0.0, grad=None, frame_smooth=0.0, thin=None,
           wrap_tip=None, keep=None, swell=0.18):
    """Append a flattened, tapered tube along `ctrl` to bm; returns a Strand.

    width/thick: full width and thickness (m) at the widest point.
    swell: arc fraction over which the section grows from base_taper to full
    size at the root.
    tip_from: fraction of the length kept at full width before the tip taper.
    tip_pow / ogive: tip width profile (1 - u**ogive)**tip_pow over the taper
    (u 0..1). ogive 1 is a straight wedge; ~2 keeps the width longer and
    closes it in a rounded arc, so tips read soft instead of as sawteeth.
    tip_dense: packs rings toward the tip (see arc_params).
    tip_thick: share of the thickness kept toward the tip (lower = the tip
    thins out with the width instead of ending in a thick wall).
    thin: (t0, share): the thickness also eases down to `share` from arc
    fraction t0 to the tip, independently of the width (a fuller root, a
    lighter lower half).
    back: thickness of the inner (-normal) half relative to the outer half;
    < 1 gives a rounded wedge: a domed outer face over a flatter underside.
    wrap: how far the two edges curl back toward the head (x width), so a
    broad clump is a curved shell across its width instead of a flat plate;
    wrap_tip: the wrap at the tip (eased from `wrap`).
    frame_smooth: Gaussian width (arc fraction) over which the facing
    direction from `normal` is averaged before the section frame is built,
    so a lock turns its broad side gradually along a bend (no twist kinks).
    grad: (start, end) arc-length fractions of the white-to-mint 'toon_grad'
    ramp along this strand (smoothstep; None keeps it white), so the tint
    follows each lock's own flow instead of a shared world height.
    keep: (root, tip, t0, t1): the share of the strand's own normal in its
    custom normals (finish), eased from `root` at arc fraction t0 to `tip` at
    t1; None leaves the object's default.
    Tip is closed by a single apex vertex; the root is capped flat."""
    tip_from = min(max(tip_from, 0.0), 0.9)
    pts = catmull(ctrl, segs + 1, tip_dense)
    params = arc_params(segs + 1, tip_dense)
    layer = grad_layer(bm)
    klay = _layer(bm, KEEP_ATTR, -1.0)
    llay = _layer(bm, LINE_ATTR, 1.0)
    arc = [0.0]
    for a, c in zip(pts, pts[1:]):
        arc.append(arc[-1] + (c - a).length)

    def gval(t):
        if grad is None:
            return 0.0
        return smooth01((t - grad[0]) / (grad[1] - grad[0]))

    def kval(t):
        if keep is None:
            return -1.0
        k0, k1, t0, t1 = keep
        return k0 + (k1 - k0) * smooth01((t - t0) / (t1 - t0))

    tans = [(pts[min(i + 1, segs)] - pts[max(i - 1, 0)]).normalized() for i in range(segs)]
    want = [normal(p) for p in pts[:-1]]
    if frame_smooth > 0:
        sm = []
        for i in range(segs):
            acc = Vector((0.0, 0.0, 0.0))
            for j in range(segs):
                acc += want[j] * math.exp(-0.5 * ((params[i] - params[j]) / frame_smooth) ** 2)
            sm.append(acc if acc.length > 1e-9 else want[i])
        want = sm

    rings = []
    prev_b = None
    for i, p in enumerate(pts[:-1]):
        t = params[i]
        tan = tans[i]
        nrm = want[i] - tan * want[i].dot(tan)
        if nrm.length < 1e-6:
            nrm = tan.orthogonal()
        nrm.normalize()
        b = tan.cross(nrm).normalized()
        if prev_b is not None and b.dot(prev_b) < 0:
            b = -b
        prev_b = b
        # width profile: quick swell from the root, long taper to the tip
        sw = min(1.0, base_taper + (1 - base_taper) * min(1.0, t / swell))
        u = max(0.0, t - tip_from) / (1 - tip_from)
        tip = max(0.0, 1 - u ** ogive) ** tip_pow
        w = 0.5 * width * sw * tip
        h = 0.5 * thick * sw * max(tip, tip_thick)
        if thin is not None:
            h *= 1 - (1 - thin[1]) * smooth01((t - thin[0]) / (1 - thin[0]))
        wr = wrap if wrap_tip is None else wrap + (wrap_tip - wrap) * smooth01(t)
        gv, kv = gval(t), kval(t)
        ring = []
        for k in range(n):
            a = 2 * math.pi * k / n
            sa, ca = math.sin(a), math.cos(a)
            off = sa * h * (1.0 if sa > 0 else back) - wr * w * ca * ca
            v = bm.verts.new(p + b * (ca * w) + nrm * off)
            v[layer] = gv
            v[klay] = kv
            v[llay] = 1.0           # full outline unless settle() fades it
            ring.append(v)
        rings.append(ring)
    apex = bm.verts.new(pts[-1])
    apex[layer] = gval(1.0)
    apex[klay] = kval(1.0)
    apex[llay] = 1.0
    for a, c in zip(rings, rings[1:]):
        for k in range(n):
            kk = (k + 1) % n
            bm.faces.new((a[k], a[kk], c[kk], c[k]))
    for k in range(n):
        bm.faces.new((rings[-1][k], rings[-1][(k + 1) % n], apex))
    bm.faces.new(list(reversed(rings[0])))
    return Strand(rings + [[apex]], arc)


def settle(bm, st, cap_bvh, emerge, depth=1.5, squash=0.35):
    """Press a strand's root onto the cap so it grows out of the scalp.

    Over the first `emerge` metres of arc every vertex's height over the cap
    surface (nearest point, along the cap normal) is eased from
    squash * h - depth (the whole section flattened and buried) to its own h
    (smoothstep). The section follows the cap's curvature across its width,
    so the clump surfaces as one soft ridge, middle first, without a cut.
    The outline weight (LINE_ATTR) is 0 until the root is LINE_ON of the way
    out, then rises quickly to 1: a hull line on a barely raised ridge only
    shows as a faint grey sliver (it reads as a shade speck, not a line)."""
    llay = bm.verts.layers.float.get(LINE_ATTR)
    for ring, s_arc in zip(st.rings, st.arc):
        if s_arc >= emerge:
            break
        s = smooth01(s_arc / emerge)
        for v in ring:
            co, nrm, _i, _d = cap_bvh.find_nearest(v.co)
            if co is None:
                continue
            h = (v.co - co).dot(nrm)
            # never raise a vertex that already lies deeper than the target
            # (a deeply buried root keeps its section instead of folding)
            h2 = min(h, s * h + (1 - s) * (squash * h - depth * PX))
            v.co = v.co + nrm * (h2 - h)
            if llay is not None:
                v[llay] = smooth01((s - LINE_ON) / LINE_RAMP)


def finish(col, name, bm, mat, angle=70, keep=VOL_KEEP, line_min=None):
    """Mesh object from bm. toon_grad comes from the strands' own arc-length
    ramp (strand(grad=...)).

    keep: share of the strands' own normals in the custom normals (the rest is
    the smooth hair-volume normal, see volume_normal); strand(keep=...)
    overrides it per vertex.
    line_min: thin the outline where settle() buried a root (outline width
    x line_min there, full on the free strand); None = uniform outline."""
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    llay = bm.verts.layers.float.get(LINE_ATTR)
    lw = [v[llay] for v in bm.verts] if llay is not None else None
    obj = common.new_object(col, name, bm, [mat])
    me = obj.data
    if me.attributes.get(LINE_ATTR) is not None:
        me.attributes.remove(me.attributes[LINE_ATTR])
    common.shade_smooth(obj, angle)
    set_volume_normals(me, keep)
    if line_min is not None and lw is not None:
        vg = obj.vertex_groups.new(name=LINE_GROUP)
        by_w = {}
        for i, w in enumerate(lw):
            by_w.setdefault(round(max(0.0, min(1.0, w)), 4), []).append(i)
        for w, idx in by_w.items():
            vg.add(idx, w, 'REPLACE')
        common.add_outline(obj, vertex_group=LINE_GROUP, min_factor=line_min)
    else:
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
BANG_TIP_GAP = 5        # px in front of the skin at the tips
BANG_BULGE = 8          # px in front of the skin where the fringe arches out (row 84)


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
# Round 5: the clumps beside the dominant central lock are ~12% narrower and
# their tips swing 2 px further out, so the central sweep leads the fringe.
BANG_CLUMPS = (
    (-3, -7, 129, 24, 7.0, 1.4, 0.3, 'in'),      # dominant central lock, on top
    (5, 14, 108, 19, 4.0, 2.4, 0.4, 'in'),       # right of the centre parting
    (-15, -25, 101, 25, 5.0, 2.2, 0.38, 'in'),   # shorter over the eyes, so the
    (19, 29, 97, 25, 5.5, 2.0, 0.4, 'in'),       # tip rows vary by ~3 cm
    (-29, -38, 114, 25, 6.0, 1.9, 0.5, 'out'),
    (31, 40, 110, 23, 6.5, 2.3, 0.5, 'out'),
    (35, 44, 124, 17, 3.5, 1.7, 0.55, 'temple'),  # past the outer eye corners
    (-37, -45, 126, 17, 3.5, 1.7, 0.55, 'temple'),
)
OUTER_BULGE_LESS = 6    # px less forward arch on the outer clumps
BANG_STAGGER = 0.8      # px of forward offset per px of lift over the forehead
# Root path: four stations from the crown to the hairline, on the cap surface
# (grow base px + share x lift); settle() then buries and raises the root
# section against the real cap, so the stations only steer the path.
# ROOT_FX / ROOT_FX_TIP place them between the root and fx0 (and toward fx1).
ROOT_GROW = ((0.0, 0.0), (0.5, 0.1), (1.0, 0.25), (1.2, 0.45))
ROOT_FX = (0.0, 0.45, 0.75, 0.95)
ROOT_FX_TIP = (0.0, 0.0, 0.03, 0.1)
# per kind: (station rows, share of fx0 the root starts at)
ROOTS = {'in': ((20, 38, 54, 68), 0.25),
         'out': ((28, 42, 56, 70), 0.55),
         'temple': ((34, 46, 58, 70), 0.7)}
BANG_EMERGE = 0.92      # emergence length: x the arc to the third station
# Normals: pure scalp-volume normal while a root emerges (its flanks shade
# exactly like the cap around it, no shade slivers along the ridges), then
# VOL_KEEP of the clump's own normal on the free fringe.
BANG_KEEP = (0.0, VOL_KEEP, 0.25, 0.55)


def _polyline_len(pts):
    return sum((b - a).length for a, b in zip(pts, pts[1:]))


def bangs(bm, cap_bvh):
    """The fringe: rounded-wedge clumps that grow out of the cap above the
    hairline, arch out over the forehead and come back to rest just in front
    of it.

    Each root follows the cap surface and is pressed onto it (settle): it
    starts flattened just under the scalp and lifts out over ~3-4 cm, the
    middle ridge first, so the crown keeps one surface with soft clump lines."""
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
        # stagger the clumps in depth by their layer (higher lift = further
        # forward) so the exposed fringe reads as overlapping clumps, not one
        # shell; the stagger fades out toward the tips
        stag = BANG_STAGGER * (lift - 5.0)
        bulge -= stag
        tip -= 0.4 * stag
        rowm = (84 + row1) / 2
        fxq = fx0 + (fx1 - fx0) * 0.75
        rows, share = ROOTS[kind]
        fxr = fx0 * share
        ctrl = [cap_front_point(fxr + (fx0 - fxr) * a + (fx1 - fx0) * b, row, g0 + g1 * lift)
                for row, (g0, g1), a, b in zip(rows, ROOT_GROW, ROOT_FX, ROOT_FX_TIP)]
        emerge = _polyline_len(ctrl[:3]) * BANG_EMERGE
        ctrl += [P(fxm, 84, bulge),
                 P(fxq, rowm, (bulge + tip) / 2 - 1),
                 P(fx1, row1, tip)]
        # 16 sides on the broad inner clumps: a rounded centre ridge and flanks
        st = strand(bm, ctrl, wpx * PX, 0.010 if outer else 0.0115, segs=18, n=12 if outer else 16,
                    base_taper=0.7, tip_pow=0.75, ogive=rnd, tip_dense=0.35, normal=bang_normal,
                    tip_from=tf, back=0.4, wrap=0.25, wrap_tip=0.12, tip_thick=0.1,
                    thin=(0.45, 0.5), frame_smooth=0.08, keep=BANG_KEEP)
        settle(bm, st, cap_bvh, emerge, depth=1.2)


def ahoge(bm, cap_bvh):
    """Two crown tufts. They leave the scalp tangentially just behind the
    apex and curve forward and away from it, so the top reads as a tuft on a
    round crown rather than as the cap's own spike."""
    st = strand(bm, [P(-2, 34, 304), P(-2, 22, 292), P(-1, 15, 279), P(1, 11, 268), P(3, 11, 261)],
                0.016, 0.007, segs=14, n=8, base_taper=0.6, tip_pow=0.8, ogive=1.6, tip_dense=0.4,
                tip_from=0.35, normal=lambda p: Vector((1, 0, 0)))
    settle(bm, st, cap_bvh, 14 * PX, depth=1.0)
    st = strand(bm, [P(4, 36, 308), P(6, 25, 296), P(6, 19, 283), P(8, 17, 276)],
                0.012, 0.006, segs=10, n=8, base_taper=0.6, tip_pow=0.8, ogive=1.4,
                tip_dense=0.3, tip_from=0.3, normal=lambda p: Vector((1, 0, 0)))
    settle(bm, st, cap_bvh, 12 * PX, depth=1.0)


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
    # Round 5: thinner, rounder bundles; the outward turn starts ~10 rows
    # earlier, ~3 px higher and further out, and closes in a ~1.2 cm radius
    # with a short upward hook; the two tips end ~1 cm apart in height and
    # ~0.5 cm apart in depth.
    ([(38, 48, 252), (51, 72, 252), (50, 96, 257), (49, 112, 263), (52, 124, 270),
      (58, 134, 277), (65, 140, 283), (71, 140, 287), (75, 136, 290), (76, 131, 291)], 0.022),
    ([(46, 52, 262), (59, 78, 263), (57, 102, 269), (58, 117, 276), (62, 128, 283),
      (68, 134, 288), (73, 133, 292), (76, 128, 295), (76, 123, 296)], 0.023),
]
WISP_LOCKS = [
    # outer wisps flaring out at rows 115-140 (front), behind the eye (side);
    # they keep falling as they flare, and only the last ~1 cm turns softly
    # back up toward the head (no horizontal spike)
    # Round 5: narrower, and the second wisp ~3 px deeper so the two don't
    # read as one broad temple panel.
    ([(52, 48, 270), (63, 82, 272), (71, 104, 276), (77, 120, 280), (82, 131, 283),
      (86, 138, 285), (88, 139, 287), (89, 136, 289)], 0.019),
    ([(58, 58, 290), (70, 94, 291), (78, 116, 293), (83, 128, 295), (86, 134, 297),
      (87, 133, 299), (86, 129, 300)], 0.017),
]
# The lock in front of each shoulder: a two-strand bundle. The dominant
# S-shaped lock (A) turns forward gradually over rows ~140-225 and ends with
# a slight turn back toward the chest. The support (B) is under-layer volume
# behind A: it runs ~5-8 px deeper, never swings forward, and ends ~5 cm
# higher pointing down and back, so the two never read as parallel prongs.
# Round 5: the run through rows 85-150 is one shallow outward bow into the
# forward swing (no straight drop then bend); A keeps a near-round section
# (2.6 x 2.2 cm) and thins only over its last third.
FRONT_LONG_MAIN = [
    ([(52, 60, 276), (62, 86, 283), (67, 112, 288), (67, 132, 288), (67, 149, 281),
      (69, 164, 268), (72, 179, 255), (75, 193, 245), (78, 206, 240), (80, 217, 239),
      (80, 227, 241)], 0.026),
]
FRONT_LONG_SUPPORT = [
    ([(56, 66, 278), (65, 100, 290), (69, 130, 295), (71, 148, 294), (73, 162, 290),
      (75, 175, 285), (76, 186, 281), (76, 193, 280)], 0.022),
]
# The outward shoulder curl: round 4 gives it a rounder section (8 sides,
# thicker) and a wider, more gradual terminal turn instead of a tight hook.
# Round 5: it crosses the shoulder ~8 px further forward and a few rows
# higher, in front of the raised upper arm's path (arms_up: the curl sank
# 1.1-1.6 cm into the arm; now below the bodice's own 1.2 cm).
CURL_LOCK = ([(60, 70, 282), (66, 100, 284), (64, 130, 285), (64, 150, 282), (72, 170, 277),
              (81, 183, 276), (90, 195, 280), (98, 205, 285), (106, 214, 290), (118, 220, 291),
              (127, 226, 292), (132, 233, 292), (131, 241, 292), (126, 246, 292),
              (120, 246, 292)], 0.028)
# One strand behind the face frame filling the gap to the back hair (round 4
# dropped the second, deeper one: it only added a step at the temple).
# Round 5: a station at row 145 and a tapered end instead of a straight blade;
# ~3 px further back so it no longer shares a depth with the support lock.
SIDE_CURTAIN = [
    ([(56, 62, 303), (62, 108, 303), (64, 145, 303), (66, 176, 304), (67, 202, 306)], 0.032),
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
LOCK_EMERGE = 10.0      # px of arc past the first visible control point over
                        # which settle() lets the lock lift off the cap


def side_set(bm, defs, segs, thick, mirror, forward=1.2, lateral=False, cap_bvh=None, **kw):
    """forward: how much the ribbons turn to face the front (0 = face out
    sideways, broad in the side view). Other keywords go to strand().

    The root is buried: an extra control point continues the lock back up
    along the cap (tangentially, just under its surface), so the narrow first
    rings sit inside it and the lock surfaces at a shallow angle; with
    cap_bvh the root rings are then pressed onto the cap (settle) up to
    LOCK_EMERGE px past the first visible control point. The strand's
    arc-length fractions (tip_from, grad, keep) include this hidden ~12-17 px
    root, so the visible ramps start a little earlier than the numbers; they
    are tuned per family."""
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
        emerge = _polyline_len(pts[:2]) + LOCK_EMERGE * PX
        if mirror:
            pts = mirror_pts(pts)
        st = strand(bm, pts, w, thick, segs=segs, normal=nfn, **kw)
        if cap_bvh is not None:
            settle(bm, st, cap_bvh, emerge, depth=1.0)


# Normal blend per family (finish(keep=...)): the cap and fringe keep the
# smooth scalp volume; the hanging locks fade from it near the scalp to more
# of their own rounded section below the cheek, so they read as bundles, not
# flat plates, at oblique angles (strand(keep=LOCK_KEEP)).
LOCK_KEEP = (0.0, 0.7, 0.12, 0.55)


def build(col):
    mat = common.toon_material('hair', gradient='hair_tip')

    cap_bvh = build_cap(col, mat)[1]

    bm = bmesh.new()
    ahoge(bm, cap_bvh)
    crown = finish(col, 'hair_crown', bm, mat, line_min=LINE_MIN)
    crown['levi_cast_shadow'] = False   # a hard slit on the crown from above otherwise

    bm = bmesh.new()
    bangs(bm, cap_bvh)
    bangs_obj = finish(col, 'hair_bangs', bm, mat, line_min=LINE_MIN)
    # The fringe does not cast: with the low key light every clump ridge over
    # the crown printed a hard 1-2 px shadow sliver along its neighbour (round
    # 5: front hair islands 18 -> 13), and its shadow on the forehead is too
    # thin to read. Its own N.L shading still separates the clumps.
    bangs_obj['levi_cast_shadow'] = False

    for side, mirror in (('L', False), ('R', True)):
        bm = bmesh.new()
        # the temple locks swell out of the cap over ~35% of their length
        # (no broad shoulder where they surface)
        side_set(bm, CHEEK_LOCKS, 18, 0.0125, mirror, forward=0.7, lateral=True, n=12,
                 cap_bvh=cap_bvh, base_taper=0.2, swell=0.35, tip_pow=0.6, ogive=1.8, tip_dense=0.4,
                 tip_from=0.55, back=0.7, wrap=0.1, tip_thick=0.15, grad=(0.5, 1.0),
                 frame_smooth=0.08, thin=(0.6, 0.75), keep=LOCK_KEEP)
        side_set(bm, WISP_LOCKS, 16, 0.011, mirror, forward=0.6, n=10, cap_bvh=cap_bvh,
                 base_taper=0.2, swell=0.35, tip_pow=0.6, ogive=1.9, tip_dense=0.5, tip_from=0.45,
                 back=0.8, wrap=0.08, tip_thick=0.15, grad=(0.55, 1.0),
                 frame_smooth=0.08, keep=LOCK_KEEP)
        finish(col, f'hair_cheek_{side}', bm, mat, line_min=LINE_MIN)

        bm = bmesh.new()
        # near-round sections (width / thickness ~1.3) so the locks read as
        # bundles from every angle, not as blades with a broad flat face;
        # the width holds to mid-length and closes in an arc, while the
        # thickness eases off over the lower half
        side_set(bm, FRONT_LONG_MAIN, 30, 0.022, mirror, forward=0.9, lateral=True, n=12,
                 cap_bvh=cap_bvh, base_taper=0.3, tip_pow=0.7, ogive=2.0, tip_dense=0.35,
                 tip_from=0.4, back=0.85, wrap=0.05, tip_thick=0.15, grad=(0.42, 1.0),
                 frame_smooth=0.1, thin=(0.6, 0.65), keep=LOCK_KEEP)
        side_set(bm, FRONT_LONG_SUPPORT, 24, 0.015, mirror, forward=0.9, lateral=True, n=10,
                 cap_bvh=cap_bvh, base_taper=0.3, tip_pow=0.7, ogive=1.6, tip_dense=0.3,
                 tip_from=0.3, back=0.85, wrap=0.05, tip_thick=0.12, grad=(0.4, 1.0),
                 frame_smooth=0.1, thin=(0.4, 0.5), keep=LOCK_KEEP)
        finish(col, f'hair_lock_{side}', bm, mat, line_min=LINE_MIN)

        bm = bmesh.new()
        side_set(bm, [CURL_LOCK], 32, 0.018, mirror, n=10, cap_bvh=cap_bvh, base_taper=0.3,
                 tip_pow=0.6, ogive=1.3, tip_from=0.3, tip_dense=0.3, back=0.85, tip_thick=0.15,
                 grad=(0.55, 0.85), frame_smooth=0.06, keep=LOCK_KEEP)
        finish(col, f'hair_curl_{side}', bm, mat, line_min=LINE_MIN)

        bm = bmesh.new()
        # The curtain hangs behind the face frame and ends at the choker, well
        # above the other locks' green: its ramp ends past the tip (~45% mint
        # there), as the earlier height ramp did.
        side_set(bm, SIDE_CURTAIN, 14, 0.014, mirror, n=10, cap_bvh=cap_bvh, base_taper=0.3,
                 tip_pow=0.7, ogive=1.8, tip_from=0.55, tip_dense=0.3, tip_thick=0.2,
                 grad=(0.78, 1.25), frame_smooth=0.1)
        finish(col, f'hair_curtain_{side}', bm, mat, line_min=LINE_MIN)
