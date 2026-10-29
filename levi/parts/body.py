"""Skin body: neck, torso, A-pose arms with five-fingered hands, legs, feet.

Everything is a swept ring loft (quads, with small triangle fans only at
rounded tips), so each limb carries clean, evenly spaced edge loops at the
shoulder, elbow, wrist, hip, knee and ankle: about 1 cm apart (5-7 panel px)
through every joint band the rig's helper bones bend, so linear-blend skinning
samples the bend smoothly instead of folding a few long quads. The head is a
separate part; the neck stops in a tilted ring tucked just under the jaw
(spec.L['chin_z']).

The arms grow out of the torso: a six-by-six patch of quads on each side of
the shoulder band is cut away and the arm loft starts from the hole's 24-vertex
border (the shoulder socket). Between the socket and the first round arm ring
the rings follow cubic Hermite paths that leave the torso along its own
surface and arrive along the arm, so the trapezius slope rolls over a rounded
deltoid into the upper arm, and the armpit is a soft hollow between the side
of the chest and the inner arm. The torso rings bunch their vertices around
the socket's front and back edges (the armpit folds), and the shoulder joint
sits inside the deltoid volume.

Joint anatomy carried by the loops: a rounded kneecap dome and a shallow crease
behind the knee (where the fold forms in a squat), a straight shin front with
the calf fullness at the back, a gluteal fold under the buttock, the armpit
hollow, and dense loops over the elbow and wrist.

Round 11 (upper body; 风堇 has no torso, shoulders or elbows to reuse): the neck,
shoulder and upper-chest rings carry twice the vertices across the middle of their front
(TORSO_DENSE), the exposed upper chest rises evenly into the bust instead of stepping
forward at the bodice's top edge (UPPER_CHEST), and soft anatomy relief sits on the
shape master's surface: collarbones, the hollow above them, the notch at the base of the
neck and its two tendons, the trapezius at the neck's base, the spine and the shoulder
blades (_torso_relief). The elbow is rounded with an elbow point and a soft crook
(ELBOW_FILLET, ELBOW_BUMPS).

All shape data below is in *panel pixels* measured on ref/{front,side}.png
(see `P()`): x = offset from the panel centre column (+ = character's left),
y = side-view offset (- = forward), row = image row (ground at
spec.SHEET_GROUND_Y). The exposed skin (neck, shoulders, upper chest, hands,
legs below the petticoat) was fitted to the reference silhouette; the parts
hidden under the bodice / sleeves / skirt / shoes are kept a few pixels inside
the clothing outline so the clothing parts can wrap them.

Local corrections vs. spec.L (re-measured on the reference):
  * knee at row ~700 (spec says 740): the leg is widest there in both views.
  * shoulder joint / elbow / wrist moved to fit the visible upper arm and the
    hands (wrist ~(220, 438) px instead of (200, 455)).
  * neck centre y = -31 px (spec -38).

Other parts import from here (data / pure functions only, keep the names):
accessories calls build_torso() (the chest surface the halter rests on) and
smoothstep(); shoes reads FOOT, LEG_FRONT, LEG_SIDE, LEG_ROWS and MARGIN and calls
leg_section() / leg_offset() (round 8: it clears its shell off the leg, which now runs
on below the malleoli into the heel round the ankle pivot).
"""
import math
import os

import bmesh
import numpy as np
from mathutils import Matrix, Vector
from mathutils.kdtree import KDTree

from .. import common, spec

MARGIN = 1.0  # px pulled in so the outline hull lands on the reference line


def P(x, y, row):
    """Panel pixels -> world metres."""
    return Vector((spec.px_to_h(x), spec.px_to_h(y), spec.px_to_z(row)))


px = spec.px_to_h  # panel pixels -> metres


def smoothstep(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def _interp(table, t):
    """Piecewise-linear lookup in [(t, value)] (values: numbers or tuples)."""
    if t <= table[0][0]:
        return table[0][1]
    for (t0, v0), (t1, v1) in zip(table, table[1:]):
        if t <= t1:
            a = (t - t0) / (t1 - t0)
            if isinstance(v0, tuple):
                return tuple(x + (y - x) * a for x, y in zip(v0, v1))
            return v0 + (v1 - v0) * a
    return table[-1][1]


# ---------------------------------------------------------------- shape master (round 10)
# The exposed skin takes its shape from the shape master (levi/shape.py, label
# 'body'): each section function (leg_offset, arm_rings, build_torso) casts rays
# from its ring centre out along its own vertex directions, and blends its
# procedural radius toward the master's by a weight that is 1 where the master is
# the outermost surface and plausible, fading to 0 into hidden zones (under the
# petticoat, the bodice, the sleeves and the shoes), which keep the procedural shape.
# False: the procedural shape alone (round 9); LEVI_BODY_MASTER=0 for A/B renders
MASTER = os.environ.get('LEVI_BODY_MASTER', '1') != '0'
MASTER_INSET = 0.5     # px: stay this far inside the master's surface (the outline hull)
# A sample counts only if the master's radius is within this share of ours and its
# surface faces outward along the ray (the master's labels have stray patches: cuffs
# and ribbons labelled body; a ray starting inside a neighbouring limb exits it).
MASTER_RATIO = (0.7, 1.45)
MASTER_REACH = 1.6     # rays start this many of our radii out from the ring centre
MASTER_FACING = 0.15   # min cos between the hit surface's normal and the ray (outward)


def _master_radii(centres, dirs, r_ours, labels=('body',), reach=None, occluders=True):
    """Radius (m) of the shape master's outermost `labels` surface along each unit
    direction from its centre (left-side points; the mirrored right side is sampled
    too and averaged, so the body stays symmetric), or NaN where another part is
    outermost or no plausible surface is hit (see MASTER_RATIO / MASTER_FACING).
    reach: optional per-ray cap (m) on how far out the ray starts. occluders=False
    looks through other parts (the legs inside the skirt)."""
    from .. import shape as master
    C = np.asarray(centres, dtype=np.float64).reshape(-1, 3)
    D = np.asarray(dirs, dtype=np.float64).reshape(-1, 3)
    D = D / np.linalg.norm(D, axis=1, keepdims=True)
    R = np.asarray(r_ours, dtype=np.float64).reshape(-1)
    rmax = R * MASTER_REACH
    if reach is not None:
        rmax = np.minimum(rmax, np.asarray(reach, dtype=np.float64))
    lo, hi = MASTER_RATIO
    out = []
    for sgn in (1.0, -1.0):
        Cs, Ds = C.copy(), D.copy()
        Cs[:, 0] *= sgn
        Ds[:, 0] *= sgn
        _, dist, nrm, _ = master.ray(labels, Cs + Ds * rmax[:, None], -Ds, float(rmax.max()), occluders)
        r = rmax - dist
        with np.errstate(invalid='ignore'):
            ok = (np.isfinite(r) & (r > R * lo) & (r < np.minimum(R * hi, rmax - 1e-4))
                  & ((nrm * Ds).sum(1) > MASTER_FACING))
        out.append(np.where(ok, r, np.nan))
    a, b = out
    with np.errstate(invalid='ignore'):
        return np.where(np.isfinite(a) & np.isfinite(b), (a + b) / 2, np.where(np.isfinite(a), a, b))


def _gauss(a, sig_r, sig_c, periodic=True):
    """Separable Gaussian smoothing of a 2-D table: rows clamped at the ends, columns
    periodic (rings) or clamped."""
    a = np.asarray(a, dtype=np.float64)
    for axis, sig, per in ((0, sig_r, False), (1, sig_c, periodic)):
        if sig <= 0:
            continue
        h = max(1, int(math.ceil(3 * sig)))
        k = np.exp(-0.5 * (np.arange(-h, h + 1) / sig) ** 2)
        k /= k.sum()
        b = np.moveaxis(a, axis, 0)
        n = b.shape[0]
        idx = np.arange(-h, n + h)
        idx = idx % n if per else np.clip(idx, 0, n - 1)
        pad = b[idx]
        b = sum(k[j] * pad[j:j + n] for j in range(2 * h + 1))
        a = np.moveaxis(b, 0, axis)
    return a


def _blend_table(delta, weight, sig_d, sig_w, periodic=True):
    """Offsets from a table of master deltas (NaN = no sample) and a 0..1 reliability
    weight per sample: the deltas are filled across the gaps and smoothed, the weight
    (0 where there is no sample) smoothed wider, so the shape fades into the hidden
    zones over a few loops instead of stepping."""
    from .. import shape as master
    d = np.array(delta, dtype=np.float64)
    ok = np.isfinite(d)
    w = np.where(ok, np.asarray(weight, dtype=np.float64), 0.0)
    if not ok.any():
        return np.zeros_like(d)
    for i in range(d.shape[0]):
        if ok[i].any():
            d[i] = master.fill_ring(d[i]) if periodic else master.fill_rows(d[i][:, None])[:, 0]
    d = master.fill_rows(d, 0)
    d = np.where(np.isfinite(d), d, 0.0)
    d = _gauss(d, sig_d[0], sig_d[1], periodic)
    w = _gauss(w, sig_w[0], sig_w[1], periodic)
    # a lone sample cannot pull a loop out: the weight saturates only where the
    # neighbourhood is mostly sampled
    w = np.clip(w * 1.25, 0.0, 1.0)
    return d * w


# ---------------------------------------------------------------- sweep
def _frames(centers, side_hints, tangent=None):
    n = len(centers)
    out = []
    for i in range(n):
        if tangent is not None:
            t = Vector(tangent).normalized()
        else:
            a = centers[max(i - 1, 0)]
            b = centers[min(i + 1, n - 1)]
            t = (b - a).normalized()
        h = side_hints[i]
        side = (h - t * h.dot(t)).normalized()
        up = t.cross(side)
        out.append((t, side, up))
    return out


def _ring_dir(theta, p):
    c, s = math.cos(theta), math.sin(theta)
    e = 2.0 / p
    return (math.copysign(abs(c) ** e, c), math.copysign(abs(s) ** e, s))


def ring_points(centers, side_hints, radii, n, p=2.0, tangent=None, thetas=None, shape=None):
    """Vertex positions of lofted rings (see `sweep`) without creating them.

    thetas[i]: optional per-ring list of n superellipse angles (default
    uniform). shape(i, dx, dy) -> (d_side, d_up, d_t) in metres: optional
    per-vertex offset in the ring's frame. Returns (rings, frames)."""
    frames = _frames(centers, side_hints, tangent)
    rings = []
    for i, (c, (t, side, up), r) in enumerate(zip(centers, frames, radii)):
        pi = p[i] if isinstance(p, (list, tuple)) else p
        ring = []
        for k in range(n):
            th = thetas[i][k] if thetas is not None else 2 * math.pi * k / n
            dx, dy = _ring_dir(th, pi)
            rs = r[0] if dx >= 0 else r[1]
            ru = r[2] if dy >= 0 else r[3]
            co = c + side * (dx * rs) + up * (dy * ru)
            if shape is not None:
                a, b, d = shape(i, dx, dy)
                co = co + side * a + up * b + t * d
            ring.append(co)
        rings.append(ring)
    return rings, frames


def skin_rings(bm, rings, frames=None, cap0=None, cap1=None, cap0_len=0.0, cap1_len=0.0, mirror=False):
    """Create verts (positions, or existing BMVerts kept as they are) and quads.

    cap: 'pole' (triangle fan to a tip cap_len along the end frame's tangent),
    'ngon' or None. mirror: x -> -x for created verts. Returns the vert rings."""
    out = []
    for ring in rings:
        vr = []
        for co in ring:
            if isinstance(co, bmesh.types.BMVert):
                vr.append(co)
            else:
                v = Vector(co)
                if mirror:
                    v.x = -v.x
                vr.append(bm.verts.new(v))
        out.append(vr)
    n = len(out[0])
    for a, b in zip(out, out[1:]):
        for k in range(n):
            j = (k + 1) % n
            bm.faces.new((a[k], a[j], b[j], b[k]))
    ends = ((out[0], cap0, -cap0_len, 0), (out[-1], cap1, cap1_len, -1))
    for ring, cap, ln, fi in ends:
        if cap == 'ngon':
            bm.faces.new(ring)
        elif cap == 'pole':
            t = frames[fi][0].copy()
            if mirror:
                t.x = -t.x
            tip = bm.verts.new(sum((v.co for v in ring), Vector()) / n + t * ln)
            for k in range(n):
                bm.faces.new((ring[k], ring[(k + 1) % n], tip))
    return out


def sweep(bm, centers, side_hints, radii, n, p=2.0, cap0='pole', cap1='pole',
          cap0_len=0.0, cap1_len=0.0, ring_fn=None, tangent=None, thetas=None, shape=None):
    """Loft rings along `centers` into `bm`.

    radii[i] = (side+, side-, up+, up-) in metres; side = hint orthogonalised
    against the tangent, up = tangent x side. p: superellipse exponent (scalar
    or per-ring list). cap: 'pole' (triangle fan to a tip point offset by
    cap_len along the tangent), 'ngon' or None. ring_fn(i, co) may move ring
    vertices after placement; shape: see `ring_points`. tangent: fixed ring
    normal for all rings (for tables measured as horizontal / vertical
    slices); default follows the centre line. Returns the list of vertex rings.
    """
    rings, frames = ring_points(centers, side_hints, radii, n, p, tangent, thetas, shape)
    if ring_fn:
        rings = [[ring_fn(i, co) for co in ring] for i, ring in enumerate(rings)]
    return skin_rings(bm, rings, frames, cap0, cap1, cap0_len, cap1_len)


# ---------------------------------------------------------------- torso + neck
# row, half width, front y, back y, superellipse exponent, side y (panel px).
# The side y is where the ring's side (x extreme) sits: the ring has separate
# front and back radii from it, so the bust grows forward without dragging the
# shoulder socket and the armpits forward. None = halfway between front and back.
TORSO = [
    (148, 12.5, -42, -17, 2.0, None),   # tucked inside the head (tilted, see below)
    (161, 13.5, -44, -17, 2.0, None),   # chin_z: seam under the jaw
    (170, 13.5, -44, -17, 2.0, None),
    (175, 14.0, -45, -16, 2.0, None),
    (178, 15.2, -45, -15, 2.0, None),
    (180, 19.0, -45, -14, 2.0, None),   # neck base (the sheet flares from row ~180)
    (182, 26.5, -45, -12.5, 2.1, None),
    (184, 33.5, -45.5, -11, 2.2, None),
    (186.5, 44.0, -46.5, -9.5, 2.3, -27.5),
    (189, 56.0, -48, -8, 2.4, -27.0),   # SOCKET_ROWS[0]: shoulder top
    (199, 68.0, -51.5, -4, 2.6, -27.0),
    (209, 68.0, -56, -1.5, 2.5, -27.5),
    (219, 65.0, -60.5, -0.5, 2.45, -28.0),
    (230, 60.5, -65.5, 0.2, 2.35, -29.0),  # SOCKET_ROWS[-1]: armpit apex
    (235, 58.3, -70.8, 0.6, 2.3, -29.5),
    (240, 56.0, -76, 1, 2.2, -30.0),    # bodice top at the side
    (247, 55.0, -85, 2, 2.2, -31.5),    # bust, ~2-3 px inside the bodice shell
    (256, 54.0, -89.5, 3.5, 2.2, -33.0),
    (266, 53.0, -90.5, 5, 2.2, -35.0),
    (278, 50.5, -88, 6, 2.2, -37.0),
    (290, 46.5, -83, 5, 2.2, None),
    (305, 42.0, -78, 2, 2.2, None),
    (320, 39.0, -76, -1, 2.2, None),
    (335, 39.0, -76, -2, 2.2, None),    # waist
    (350, 42.0, -74, 0, 2.2, None),
    (370, 48.0, -70, 6, 2.2, None),
    (395, 55.0, -66, 14, 2.3, None),
    (420, 60.0, -60, 19, 2.3, None),
    (432, 61.3, -56.5, 19.5, 2.3, None),  # extra hip loops for leg bends
    (445, 62.0, -52, 19, 2.3, None),    # hips
    (455, 60.5, -47.5, 16.5, 2.25, None),
    (465, 57.0, -42, 13, 2.2, None),
    (480, 42.0, -32, 4, 2.0, None),
    (489, 22.0, -24, -4, 2.0, None),
]
# Bust fill under the bodice: rows -> (forward push px, push starts / is full
# at these |x| px), interpolated between rows. The bodice shell
# (levi/parts/bodice.py) is fuller off the centre line than a plain section,
# and its neckline rises toward the sides, so off-centre the upper bust is
# pushed forward to sit ~2-3 px inside the shell (no visible gap into the
# neckline from above); the centre, where the neckline dips and skin shows, is
# left alone. Round 11: the exposed upper chest above it no longer stops in a shelf at
# row 230 (UPPER_CHEST fairs it into this fill), and the centre takes a share (last
# column) of the push at the neckline rows, so the cleavage is a shallow valley ~5 px
# deep between the two bust lobes instead of a narrow groove 7 px deep (which the faired
# chest carried up as a crease).
BUST_PUSH = [(230, 0.0, 0, 20, 0.0), (235, 13.0, 0, 24, 0.33), (240, 10.5, 2, 20, 0.2),
             (247, 6.0, 0, 20, 0.0), (256, 4.3, 0, 20, 0.0), (266, 4.0, 0, 20, 0.0),
             (278, 2.0, 0, 20, 0.0), (290, 1.8, 0, 20, 0.0), (305, 0.0, 0, 20, 0.0)]
# where the push has faded out toward the side (share of the half width):
# sooner along the rising neckline edge
BUST_FADE = [(235, 0.5), (240, 0.64), (247, 0.82)]
# Neck-top tilt: the rings rise toward the back (NECK_TILT px per px of depth behind the
# front) to follow the jaw line into the head; round 11 fades it out linearly from the top
# ring (full) to NECK_TILT_END (none), so the rings stay evenly spaced up the nape too
# (round 10 tilted rows <= 161 fully and none from 170: a 25 px gap at the nape).
NECK_TILT = 0.6
NECK_TILT_END = 178.0
TORSO_N = 32
# Round 11: the rings down to TORSO_DENSE_LAST (neck, shoulders, upper chest and back,
# under the bodice down to the bust) carry TORSO_DENSE x the vertices across their front
# arc's middle (between the shoulder sockets), so the notch at the base of the neck, its
# tendons and the inner collarbones are sampled ~1 cm apart: 36 vertices instead of 32
# (the front arc's middle 4 steps are split). The socket arcs, the steps beside them and
# the back keep their TORSO_N spacing, so the 24-vertex socket border and the skin round
# the shoulders and the armpits are unchanged; see _ring_arcs.
# The next ring has TORSO_N again; the band between them (hidden under the bodice) joins
# each pair of dense segments to one with a quad and a triangle.
TORSO_DENSE = 2
TORSO_DENSE_KEEP = (3, 5)    # plain TORSO_N steps kept at each end of the (front, back) arc
TORSO_DENSE_LAST = 256
# Loft rows: the TORSO table sampled (linearly) at these rows. Every table row
# outside the shoulder band is kept, so the surface between them is unchanged;
# the extra rings give the shoulder band, the waist (forward / side bends) and
# the hips (leg swings) evenly spaced loops. Inside the band (rows 189-230)
# the socket needs seven evenly spaced rows, so table rows 199/209/219 are
# resampled (the chest front moves < 1 px). Round 11: rows 154.5 and 165.5 on the
# neck (the visible neck from the jaw down is the body's: loops ~5 px apart).
TORSO_ROWS = (148, 154.5, 161, 165.5, 170, 175, 178, 180, 182, 184, 186.5,
              189, 196, 203, 210, 217, 224, 230,            # shoulder band = SOCKET_ROWS
              235, 240, 247, 256, 266, 278, 290, 298, 305, 313, 320, 328, 335, 343, 350,
              360, 370, 382, 395, 407, 420, 432, 445, 455, 465, 472, 480, 489)
# Shoulder socket: the torso quads between these rows and between ring
# vertices -SOCKET_K..+SOCKET_K around the side (x extreme, k = 0) are
# replaced by the arm. Its border has 2 * (2K + 1) + 2 * (len(SOCKET_ROWS) - 2)
# = ARM_N verts; with len(SOCKET_ROWS) == 2K + 1 the patch is square.
SOCKET_ROWS = (189, 196, 203, 210, 217, 224, 230)
SOCKET_K = 3
SOCKET_BORDER = 2 * (2 * SOCKET_K + 1) + 2 * (len(SOCKET_ROWS) - 2)
ARM_Y = -27.0     # side y of the arm / socket centre
# socket half depth (px from ARM_Y to its front / back edge) by row: narrow
# on top of the shoulder, as deep as the arm at the armpit folds
SOCKET_W = [(189, 9.0), (199, 14.0), (209, 16.0), (219, 15.0), (230, 13.0)]
# Armpit hollow: the chest wall under the socket is drawn in (px toward the
# midline) between the front (pectoral) and back (latissimus) folds, so a
# raised arm folds the skin into a hollow instead of a flat wall.
ARMPIT_HOLLOW = [(228, 0.0), (235, 1.5), (242, 1.2), (256, 0.0)]
ARMPIT_HOLLOW_W = 10.0    # px: half depth (around ARM_Y) of the hollow


def torso_table():
    """The loft rings: (row, half width, front y, back y, exponent, side y) for
    each of TORSO_ROWS, linearly interpolated from TORSO (side y resolved)."""
    full = [(r, hw, yf, yb, p, ys if ys is not None else (yf + yb) / 2)
            for r, hw, yf, yb, p, ys in TORSO]
    out = []
    for row in TORSO_ROWS:
        j = 0
        while j < len(full) - 2 and full[j + 1][0] < row:
            j += 1
        a, b = full[j], full[j + 1]
        t = min(1.0, max(0.0, (row - a[0]) / (b[0] - a[0])))
        out.append((row,) + tuple(u + (v - u) * t for u, v in zip(a[1:], b[1:])))
    return out


def _ring_arcs(dense):
    """Arcs of a torso ring from the left side (k = 0) round the front: (TORSO_N index
    steps, vertices per step): the left socket's front half, the front arc, the right
    socket, the back arc, the left socket's back half. A dense ring splits the front and
    back arcs' steps except TORSO_DENSE_KEEP steps at each end, so the skin next to the
    socket border, where the staged shoulder helpers hand over, keeps round 10's spacing
    and weights. The rig's weight smoothing reads the mesh graph, so a denser patch
    beside the shoulder shifts the shrug / stage weights round it: split up to the border,
    the back armpit stretched x2.25 in arms_up (round 10 x1.78); with two plain steps the
    肩 weight spread over the back (x2.05-2.13 in dance_sway / idol_dance) and the front
    socket edge (x1.80 in hands_behind_head, round 10 x1.70). With three plain steps in
    front and a plain back these are back at round 10's values."""
    n, K = TORSO_N, SOCKET_K
    a = n // 2 - 2 * K
    if not dense:
        return ((K, 1), (a, 1), (2 * K, 1), (a, 1), (K, 1))
    m = TORSO_DENSE

    def arc(e):
        e = min(e, a // 2)
        return tuple(s for s in ((e, 1), (a - 2 * e, m), (e, 1)) if s[0] > 0)
    front, back = TORSO_DENSE_KEEP
    return ((K, 1),) + arc(front) + ((2 * K, 1),) + arc(back) + ((K, 1),)


def ring_size(dense):
    """Vertices per torso ring (TORSO_N, or the dense rings' count)."""
    return sum(a * m for a, m in _ring_arcs(dense))


def ring_index(k, dense):
    """Ring vertex index of the plain ring's (integer) index k on a socket arc (the mirror
    of coarse_index there)."""
    j, c = 0, 0
    for a, m in _ring_arcs(dense):
        if k <= c + a:
            return j + (k - c) * m
        j += a * m
        c += a
    return j


def coarse_index(j, dense):
    """Ring vertex j as a (fractional) TORSO_N ring index: the same angle on a plain ring."""
    c = 0.0
    for a, m in _ring_arcs(dense):
        if j <= a * m:
            return c + j / m
        j -= a * m
        c += a
    return c


def _torso_thetas(table):
    """Per-ring vertex angles. Rings in the shoulder band put vertices
    +-1..+-SOCKET_K (each side) at even fractions of the socket's depth; above
    and below the band they ease back to uniform spacing (the dense neck rings: uniform
    over each half; below the band: a plain ring's angles, the dense arcs split
    evenly, so the last dense ring's even vertices sit on the plain ring's)."""
    n, K = TORSO_N, SOCKET_K
    h = n // 2
    out = []
    r_top, r_bot = SOCKET_ROWS[0], SOCKET_ROWS[-1]
    for row, hw, yf, yb, p, ysd in table:
        dense = row <= TORSO_DENSE_LAST
        m = ring_size(dense)
        kc = [coarse_index(j, dense) for j in range(m)]
        if row < r_top:
            # uniform over each half (the front and back arcs may differ in density)
            r = ring_index(h, dense)
            uni = [math.pi * j / r if j <= r else math.pi + math.pi * (j - r) / (m - r) for j in range(m)]
            w = smoothstep(r_top - 9, r_top, row)
        else:
            uni = [2 * math.pi * k / n for k in kc]
            w = 1.0 - smoothstep(r_bot, r_bot + 26, row)
        if w <= 0:
            out.append(uni)
            continue
        sw = _interp(SOCKET_W, row)
        rf, rb = ysd - yf, yb - ysd

        def ang(depth, r):
            v = max(0.05, min(0.92, (depth / r))) ** (p / 2)
            return math.asin(v)
        # depth from the ring's side point to the socket's lines, forward
        # (front radius) and backward (back radius)
        a = [0.0] + [ang(ysd - ARM_Y + sw * j / K, rf) for j in range(1, K + 1)]
        b = [0.0] + [ang(ARM_Y + sw * j / K - ysd, rb) for j in range(1, K + 1)]
        # left side: k=0 (+X), k=1..K front, k=n-1..n-K back; right side mirrored
        sock = [0.0] * n
        for j in range(1, K + 1):
            sock[j], sock[n - j] = a[j], 2 * math.pi - b[j]
            sock[h - j], sock[h + j] = math.pi - a[j], math.pi + b[j]
        sock[h] = math.pi
        # front arc k=K..h-K and back arc h+K..n-K: uniform between the edges
        for k in range(K + 1, h - K):
            sock[k] = a[K] + (math.pi - 2 * a[K]) * (k - K) / (h - 2 * K)
        for k in range(h + K + 1, n - K):
            sock[k] = math.pi + b[K] + (math.pi - 2 * b[K]) * (k - h - K) / (h - 2 * K)
        # a dense ring's extra vertices: linear in k along the (uniform) front / back arcs
        sock.append(2 * math.pi)
        sk = [sock[int(k)] + (sock[min(int(k) + 1, n)] - sock[int(k)]) * (k - int(k)) for k in kc]
        out.append([u + (s - u) * w for u, s in zip(uni, sk)])
    return out


def _bust(row):
    """(amp, x0, x1, centre share) of BUST_PUSH at `row`; no push outside the table."""
    if row <= BUST_PUSH[0][0] or row >= BUST_PUSH[-1][0]:
        return 0.0, 0.0, 20.0, 0.0
    return _interp([(r, tuple(v)) for r, *v in BUST_PUSH], row)


def _neck_tilt(row):
    """NECK_TILT share at `row`: full on the top ring, none from NECK_TILT_END."""
    top = TORSO_ROWS[0]
    return NECK_TILT * max(0.0, min(1.0, (NECK_TILT_END - row) / (NECK_TILT_END - top)))


def build_torso(bm):
    """Neck + torso loft (closed: no shoulder sockets cut). Returns the vertex
    rings, one per TORSO_ROWS entry (torso_table()); the rings down to
    TORSO_DENSE_LAST have ring_size(True) vertices, the rest TORSO_N."""
    table = torso_table()
    centers, hints, radii, ps = [], [], [], []
    for row, hw, yf, yb, p, ys in table:
        centers.append(P(0, ys, row))
        hints.append(Vector((1, 0, 0)))
        radii.append((px(hw), px(hw), px(ys - yf), px(yb - ys)))
        ps.append(p)
    # Rings are horizontal slices (the table rows); t=-Z, side=+X -> up=-Y.
    # per ring: ((bust amp, x0, x1), bust fade, armpit hollow)
    per_ring = [(_bust(r[0]), _interp(BUST_FADE, r[0]), _interp(ARMPIT_HOLLOW, r[0])) for r in table]

    def tilt(i, co):
        row, hw, yf, _, _, ys = table[i]
        (amp, x0, x1, c), s0, hol = per_ring[i]
        co = co.copy()
        co.z += max(0.0, co.y - px(yf)) * _neck_tilt(row)
        front = co.y < px(ys)
        ax = abs(co.x) / px(1)
        if amp and front:
            # fade out toward the side; sooner along the rising neckline edge
            s1 = 0.9 * hw + 0.08 * hw * smoothstep(0.64, 0.82, s0)
            co.y -= px(amp * (c + (1 - c) * smoothstep(x0, x1, ax)) * (1 - smoothstep(s0 * hw, s1, ax)))
        if hol:
            # armpit hollow: the side wall between the front and back folds
            g = math.exp(-((co.y / px(1) - ARM_Y) / ARMPIT_HOLLOW_W) ** 2)
            f = smoothstep(0.75 * hw, 0.97 * hw, ax)
            co.x -= math.copysign(px(hol * g * f), co.x)
        return co

    thetas = _torso_thetas(table)
    nd = sum(1 for r in table if r[0] <= TORSO_DENSE_LAST)
    rings, frames = [], []
    for a, b in ((0, nd), (nd, len(table))):
        r, f = ring_points(centers[a:b], hints[a:b], radii[a:b], len(thetas[a]), ps[a:b], (0, 0, -1),
                           thetas[a:b])
        rings += r
        frames += f
    rings = [[tilt(i, co) for co in ring] for i, ring in enumerate(rings)]
    # the shape master, then the upper chest and the anatomy on the dense rings (all the
    # master's rows are dense)
    dense = _torso_master(table[:nd], rings[:nd])
    dense = _upper_chest(table[:nd], dense)
    dense = _torso_relief(table[:nd], dense)
    top = skin_rings(bm, dense, frames[:nd], 'ngon', None)
    low = skin_rings(bm, rings[nd:], frames[nd:], None, 'pole', 0.0, px(4))
    _join_dense(bm, top[-1], low[0])
    return top + low


def _join_dense(bm, a, b):
    """Faces between the last dense ring `a` and the plain ring `b` below it: a quad per
    socket-arc segment, a quad + a triangle per pair of dense segments (the dense ring's
    even vertices sit on the plain ring's)."""
    i = j = 0
    na, nb = len(a), len(b)
    for steps, m in _ring_arcs(True):
        for _ in range(steps):
            if m == 1:
                bm.faces.new((a[i], a[(i + 1) % na], b[(j + 1) % nb], b[j]))
            else:
                bm.faces.new((a[i], a[i + 1], b[j]))
                bm.faces.new((a[i + 1], a[(i + 2) % na], b[(j + 1) % nb], b[j]))
            i += m
            j += 1


# Upper chest (round 11): above the bodice the exposed chest used to stay flat down to
# row 230 and then step forward into the bust fill under the neckline (BUST_PUSH: 18 px in
# 5 rows off the centre line): a ridge across the chest at the bodice's top edge. Each
# front column (front arc) is now one cubic Hermite in the row from UPPER_CHEST[0] to
# UPPER_CHEST[1] through the rings' own values there (the end ring is the bust fill at the
# neckline, which keeps its fit inside the bodice); the slopes are the column's one-sided
# slope above the start and its three-point slope at the end (through the start and the
# next ring), so the upper chest rises evenly into the bust (the upper pole of the
# breast). Columns near the sockets (UPPER_CHEST_EDGE TORSO_N steps from the socket
# border) blend out.
UPPER_CHEST = (203.0, 235.0)
UPPER_CHEST_EDGE = 2.5


def _upper_chest(table, rings):
    rows = [r[0] for r in table]
    r0, r1 = UPPER_CHEST
    i0, i1 = rows.index(r0), rows.index(r1)
    if i0 < 1 or i1 + 1 >= len(rows):
        return rings
    n, K = TORSO_N, SOCKET_K
    h = n // 2
    m = len(rings[0])
    out = [list(r) for r in rings]
    span = r1 - r0
    for j in range(m):
        kc = coarse_index(j, True)
        if not K < kc < h - K:
            continue                # front arc only
        w = smoothstep(0.0, UPPER_CHEST_EDGE, min(kc - K, h - K - kc))
        y0, y1 = rings[i0][j].y, rings[i1][j].y
        # slopes (m per row): one-sided above the span, three-point at its end
        m0 = (y0 - rings[i0 - 1][j].y) / (rows[i0] - rows[i0 - 1])
        h2 = rows[i1 + 1] - rows[i1]
        d1, d2 = (y1 - y0) / span, (rings[i1 + 1][j].y - y1) / h2
        m1 = (d1 * h2 + d2 * span) / (span + h2)
        for i in range(i0 + 1, i1):
            t = (rows[i] - r0) / span
            h00, h10 = 2 * t ** 3 - 3 * t ** 2 + 1, t ** 3 - 2 * t ** 2 + t
            h01, h11 = -2 * t ** 3 + 3 * t ** 2, t ** 3 - t ** 2
            y = h00 * y0 + h10 * m0 * span + h01 * y1 + h11 * m1 * span
            co = rings[i][j].copy()
            co.y += (y - co.y) * w
            out[i][j] = co
    return out


# Anatomy relief (round 11), on the dense rings after the shape master (which would
# otherwise flatten it): soft displacements along the surface normal (px, + outward) of
# the strapless neckline's skin, wide enough for the ~1 cm loops that the cel ramp turns
# each into one clean terminator curve. Front (y ahead of the ring's side point):
#   the collarbones: a ridge whose crest row runs CLAVICLE (|x| px, row) from the notch out
#     to the shoulder, rising a little; CLAVICLE_AMP (height, row sigma above, below,
#     |x| fade in (from, to), fade out (from, to));
#   the hollow above them (supraclavicular): SUPRACLAV (depth, |x| centre, |x| sigma,
#     row centre, row sigma), which also turns the flat shoulder ledge in front of the neck
#     into a slope from the trapezius down to the collarbone;
#   the notch at the base of the neck between the collarbones' heads: NOTCH (depth, bottom
#     row, top row, half width at the bottom, widening per row up), framed by
#   the two neck tendons (sternocleidomastoid) running up from it: SCM (height, (|x|, row)
#     at the notch, (|x|, row) under the choker, sigma).
# Back (under the hair): the groove of the spine SPINE (depth, sigma, rows in, out), the
#   shoulder blades SCAPULA (height; medial border |x| at the top row, per row; lateral
#   border likewise; rows: top in, full, bottom fade out (under the bodice's back edge);
#   top row), and the trapezius TRAPEZIUS (height, rows in (from, to), out (from, to)):
#   the neck's back-sides thicken toward its base (peak 45 deg either side of the back),
#   so the neck sweeps down into the shoulders instead of standing on them like a tube.
# Every term fades out over the socket border (as the shape master does), which stays put.
CLAVICLE = ((6.0, 196.0), (16.0, 195.2), (30.0, 193.6), (44.0, 192.0), (58.0, 191.0))
CLAVICLE_AMP = (1.6, 2.6, 4.5, (4.0, 12.0), (46.0, 58.0))
SUPRACLAV = (2.4, 28.0, 8.0, 187.5, 2.8)
NOTCH = (1.6, 194.0, 183.0, 4.0, 0.4)
SCM = (0.6, (7.0, 193.0), (14.0, 178.0), 2.8)
SPINE = (0.5, 6.0, (186.0, 196.0), (240.0, 250.0))
SCAPULA = (1.1, (16.0, 0.25), (54.0, -0.5), (200.0, 210.0, 238.0, 250.0), 205.0)
TRAPEZIUS = (1.6, (166.0, 176.0), (182.0, 189.0))
RELIEF_SOCKET = (0.5, 2.5, 176.0, 182.0, 238.0, 244.0)   # dk fade (from K+, to K+), rows in, out


def _relief_front(ax, row):
    c = _interp(CLAVICLE, ax)
    a, s_up, s_dn, (i0, i1), (o0, o1) = CLAVICLE_AMP
    s = s_up if row < c else s_dn
    f = a * smoothstep(i0, i1, ax) * (1 - smoothstep(o0, o1, ax)) * math.exp(-0.5 * ((row - c) / s) ** 2)
    d, xc, xs, rc, rs = SUPRACLAV
    f -= d * math.exp(-0.5 * ((ax - xc) / xs) ** 2 - 0.5 * ((row - rc) / rs) ** 2)
    d, rb, rt, w0, dw = NOTCH
    w = w0 + dw * max(0.0, rb - row)
    f -= d * math.exp(-0.5 * (ax / w) ** 2) * smoothstep(rt - 2, rt + 4, row) * (1 - smoothstep(rb - 1, rb + 3, row))
    a, (xb, rb2), (xt, rt2), s = SCM
    xs_ = xb + (xt - xb) * (row - rb2) / (rt2 - rb2)
    f += a * math.exp(-0.5 * ((ax - xs_) / s) ** 2) * smoothstep(rt2 - 2, rt2 + 3, row) * (1 - smoothstep(rb2 - 3, rb2 + 1, row))
    return f


def _relief_back(ax, row, phi):
    """phi: the vertex's angle round the ring from the back centre (rad)."""
    a, (t0, t1), (t2, t3) = TRAPEZIUS
    f = a * max(0.0, math.sin(2 * phi)) ** 1.5 * smoothstep(t0, t1, row) * (1 - smoothstep(t2, t3, row))
    d, s, (r0, r1), (r2, r3) = SPINE
    f -= d * math.exp(-0.5 * (ax / s) ** 2) * smoothstep(r0, r1, row) * (1 - smoothstep(r2, r3, row))
    a, (m0, mk), (l0, lk), (t0, t1, b0, b1), top = SCAPULA
    xm = m0 + mk * (row - top)
    xl = l0 + lk * (row - top)
    if xl > xm:
        f += (a * smoothstep(xm - 4, xm + 6, ax) * (1 - smoothstep(xl - 10, xl + 2, ax))
              * smoothstep(t0, t1, row) * (1 - smoothstep(b0, b1, row)))
    return f


def _torso_relief(table, rings):
    n, K = TORSO_N, SOCKET_K
    h = n // 2
    k0, k1, a0, a1, b0, b1 = RELIEF_SOCKET
    m = len(rings[0])
    out = []
    for i, ((row, hw, yf, yb, p, ys), ring) in enumerate(zip(table, rings)):
        band = smoothstep(a0, a1, row) * (1 - smoothstep(b0, b1, row))
        up, dn = rings[max(i - 1, 0)], rings[min(i + 1, len(rings) - 1)]
        new = []
        for j, co in enumerate(ring):
            ax, r = abs(co.x) / px(1), spec.SHEET_GROUND_Y - co.z * spec.PX_PER_M
            if co.y < px(ys):
                f = _relief_front(ax, r)
            else:   # angle from the back centre on the ring's (half width, back depth) ellipse
                f = _relief_back(ax, r, math.atan2(abs(co.x) / px(hw), (co.y - px(ys)) / px(yb - ys)))
            kc = coarse_index(j, True)
            dk = min(kc, n - kc, abs(kc - h))
            f *= 1 - band * (1 - smoothstep(K + k0, K + k1, dk))
            if abs(f) < 1e-4:
                new.append(co)
                continue
            # the surface normal from the ring grid, outward from the ring's centre line
            nrm = (ring[(j + 1) % m] - ring[j - 1]).cross(dn[j] - up[j])
            if nrm.dot(Vector((co.x, co.y - px(ys), 0.0))) < 0:
                nrm = -nrm
            new.append(co + nrm.normalized() * px(f))
        out.append(new)
    return out


# Shape master on the torso: rows where the master's skin counts (ramp in, full,
# full, out): the neck below the jaw, the shoulders and the upper chest, fading out
# above the bust (the master's bust rises ~1 cm proud of ours at the bodice's top
# edge; following it there pushed a ridge across the chest and the skin through the
# bodice's neckline). The bodice and the choker hide the rest (no samples); the back
# is under the hair (only stray samples next to the shoulder: a knob), so the master
# counts on the front and the sides only.
TORSO_MASTER_ROWS = (163, 172, 212, 232)
TORSO_MASTER_BACK = (-0.1, 0.4)   # weight 1 -> 0 as the ray turns toward the back (its +y share)
# The shoulder sockets keep their procedural border (the arm's transition rings start
# from it; a horizontal ray from the torso's centre there meets the arm): no master
# within SOCKET_K + this many ring vertices of each side, over these rows.
TORSO_MASTER_SOCKET = (2.0, 182.0, 238.0)
TORSO_MASTER_SMOOTH = ((1.0, 1.0), (1.5, 1.5))   # (rings, ring vertices)
_TORSO_MASTER = {}


def _torso_master(table, rings):
    """Torso rings moved horizontally (from the ring's centre line) toward the shape
    master where its skin is outermost."""
    if not MASTER:
        return rings
    # (round 11) the dense rings: ring vertex counts and the side distance in TORSO_N
    # steps; the column smoothing scales with the front / back arcs' density
    n, K = TORSO_N, SOCKET_K
    m = len(rings[0])
    dense = m != n
    key = tuple(round(c, 6) for ring in rings for co in ring for c in co)
    if key not in _TORSO_MASTER:
        C, D, R, W = [], [], [], []
        r0, r1, r2, r3 = TORSO_MASTER_ROWS
        ks, s0, s1 = TORSO_MASTER_SOCKET
        for (row, hw, yf, yb, p, ys), ring in zip(table, rings):
            win = smoothstep(r0, r1, row) * (1 - smoothstep(r2, r3, row))
            for k, co in enumerate(ring):
                v = Vector((co.x, co.y - px(ys), 0.0))
                C.append((0.0, px(ys), co.z))
                D.append(tuple(v.normalized()) if v.length > 1e-9 else (1.0, 0.0, 0.0))
                R.append(max(v.length, 1e-6))
                # ring distance (TORSO_N steps) from the nearer side (k = 0 left, n / 2 right)
                kc = coarse_index(k, dense)
                dk = min(kc, n - kc, abs(kc - n // 2))
                band = smoothstep(s0 - 6, s0, row) * (1 - smoothstep(s1, s1 + 6, row))
                back = 1 - smoothstep(*TORSO_MASTER_BACK, D[-1][1])
                W.append(win * back * (1 - band * (1 - smoothstep(K + 0.5, K + 0.5 + ks, dk))))
        W = np.array(W)
        r_t = np.full(len(R), np.nan)
        sel = W > 0
        if sel.any():
            r_t[sel] = _master_radii(np.array(C)[sel], np.array(D)[sel], np.array(R)[sel])
        delta = ((r_t - np.array(R)) / px(1) - MASTER_INSET).reshape(len(rings), m)
        W = W.reshape(len(rings), m)
        sm = TORSO_MASTER_SMOOTH
        if dense:
            sm = tuple((a, b * TORSO_DENSE) for a, b in sm)
        # the soft window is applied again after smoothing: zero on the socket border
        # and outside the rows
        _TORSO_MASTER[key] = (_blend_table(delta, W, *sm) * W, D)
    off, D = _TORSO_MASTER[key]
    return [[co + Vector(D[i * m + k]) * px(off[i, k]) for k, co in enumerate(ring)]
            for i, ring in enumerate(rings)]


def cut_socket(bm, rings, side):
    """Delete the socket patch on one side (+1 left, -1 right) and return
    (border verts in arm-ring order, their tangents into the hole).

    Arm ring order (ARM_N = 24): 0 outer (top edge middle), 6 front,
    12 inner (armpit), 18 back."""
    rows = list(TORSO_ROWS)
    ri = [rows.index(r) for r in SOCKET_ROWS]
    i0, i4 = ri[0], ri[-1]
    # the socket rings' vertex count (round 11: the dense rings; the socket arcs keep their
    # TORSO_N spacing, so k = -K..K still spans the socket) and the right side's index
    n, K = len(rings[i0]), SOCKET_K
    r = ring_index(TORSO_N // 2, n != TORSO_N)

    def K_(k):  # left ring index -> this side's (the ring is mirror symmetric about x = 0)
        return k % n if side > 0 else (r - k) % n
    faces = []
    for i in range(i0, i4):
        for k in range(-K, K):
            a, b = rings[i], rings[i + 1]
            vs = (a[K_(k)], a[K_(k + 1)], b[K_(k + 1)], b[K_(k)])
            f = bm.faces.get(vs)
            if f is None:
                raise RuntimeError(f'body: shoulder socket quad missing (ring {i}, k {k})')
            faces.append(f)
    # (row index, k) around the border in arm-ring order
    order = [(i0, k) for k in range(0, K + 1)]
    order += [(i, K) for i in ri[1:-1]]
    order += [(i4, k) for k in range(K, -K - 1, -1)]
    order += [(i, -K) for i in reversed(ri[1:-1])]
    order += [(i0, k) for k in range(-K, 0)]
    loop, tans = [], []
    for i, k in order:
        v = rings[i][K_(k)]
        t = Vector()
        if i == i0:
            t += (v.co - rings[i - 1][K_(k)].co).normalized()
        if i == i4:
            # the armpit: mostly straight out of the chest wall (a soft, open
            # fold rather than a hairpin turn) with a little of the upward run
            out = Vector((v.co.x, v.co.y - px(ARM_Y), 0.0)).normalized()
            t += (out + 0.5 * (v.co - rings[i + 1][K_(k)].co).normalized()).normalized()
        if k == K:
            t += (v.co - rings[i][K_(K + 1)].co).normalized()
        if k == -K:
            t += (v.co - rings[i][K_(-K - 1)].co).normalized()
        loop.append(v)
        tans.append(t.normalized())
    assert len(loop) == ARM_N, (len(loop), ARM_N)
    # 'FACES' also drops the patch's inner edges and verts (no loose wire left
    # inside the socket); the border verts stay, still used by the torso quads
    bmesh.ops.delete(bm, geom=faces, context='FACES')
    return loop, tans


# ---------------------------------------------------------------- arms + hands
# Left arm (+X); the right arm is the mirror image.
SHOULDER = (66, -27, 214)
ELBOW = (118, -18, 352)
WRIST = (220, -24, 438)
HAND_DIR = (70, 4, 40)       # wrist -> middle fingertip (x, y, rows down)
HAND_W_FRONT = 0.675         # share of the palm width seen in the front view
ARM_N = SOCKET_BORDER    # 24: arm ring vertices = the socket border
# Rig shoulder joint (left, panel px): the centre of the deltoid ball, between
# the shoulder top (row ~189) and the armpit apex (row 230), so the rounded cap
# turns with the arm. Without it the rig's cross-section fit lands ~8 rows lower.
SHOULDER_JOINT = None
# Hermite transition rings between the socket border and the first round arm
# ring: four, so the deltoid and the armpit fold bend over evenly spaced loops
SOCKET_STEPS = (0.25, 0.45, 0.64, 0.82)
# Tangent lengths (x chord) leaving the torso / entering the arm, for the
# armpit (inner) and the shoulder cap (outer) sides of the socket, blended
# around it: shorter in the armpit opens a broad fold instead of a pinched
# corner. (A longer cap tangent, for a fuller deltoid, stretched the cap
# past x1.9 in arms_up.)
SOCKET_TAN_INNER = (0.85, 0.7)
SOCKET_TAN_OUTER = (0.95, 0.75)
SOCKET_FULL = 1.0     # px of front / back fullness at the middle of the transition
# Arm radii (side+ = outer/up, side- = inner, front, back px) by arc length
# from SHOULDER (px; arm_rings computes |ELBOW - SHOULDER| ~148 px and
# |WRIST - ELBOW| ~134 px). Keys are offsets: ('S', d) from the shoulder, ('E', d) from the elbow,
# ('W', d) from the wrist.
ARM_R = [
    (('S', 38), (18.0, 15.0, 17.0, 16.0)),
    (('S', 56), (15.5, 14.0, 15.5, 15.0)),
    (('S', 75), (13.6, 13.2, 14.3, 13.8)),
    (('S', 95), (13.0, 12.5, 13.2, 13.0)),
    (('E', -14), (12.5, 12.0, 12.5, 12.5)),
    (('E', 0), (12.0, 12.0, 12.5, 12.5)),
    (('E', 14), (12.0, 11.5, 12, 12)),
    (('E', 45), (11.5, 11.0, 11, 10.5)),
    (('E', 80), (10.0, 9.5, 9, 8.5)),
    # round 8: a fuller wrist (was 9.5 / 9.0 / 7.5 / 7.0 and 10.5 / 10.5 / 7.0 / 7.0),
    # still 1.5 : 1, so the palm doesn't sit on a narrow waist when the wrist bends
    (('E', 108), (9.9, 9.5, 7.7, 7.3)),
    (('W', 0), (11.2, 11.2, 7.3, 7.3)),
]
# (Round 9 tried a fuller deltoid cap, +1.5-2.5 px on the first rings fading out by
# ('S', 75): it tied or lost the pairwise review and cost front IoU; any front fullness
# cut a shade island off the armpit's shadow above the bodice. docs/pr/r9-7-limbs/.)
# Elbow (round 11). The rest arm bends ~29 deg at ELBOW (in the front plane: the sheet's
# A-pose carrying angle); round 10 swept straight rings along the shoulder -> elbow ->
# wrist polyline, an angular mitre with no elbow point or crook. Now the loft's centre
# line rounds the corner over ELBOW_FILLET px each side (a quadratic Bezier; the joint
# centre moves ~3 mm into the bend), and the rings carry the joint's landmarks as ring-local
# bumps (px outward; along the arm: centre px from ELBOW, sigma px; round the ring: the
# lobe's centre direction (side: + outer, up: + front) and exponent): the olecranon (the
# elbow point, at the back), the two epicondyles (inner larger) and the soft crook in front.
ELBOW_FILLET = 16.0
ELBOW_BUMPS = (
    (1.6, -2.0, 5.0, (0.0, -1.0), 4.0),      # olecranon
    (0.8, 1.0, 4.5, (-0.85, -0.5), 6.0),     # medial epicondyle
    (0.4, 0.0, 4.5, (0.9, -0.4), 6.0),       # lateral epicondyle
    (-0.7, 2.0, 7.0, (0.0, 1.0), 3.0),       # crook (antecubital hollow)
)
# hand twist (0 = forearm frame, 1 = hand frame) by offset from the elbow
ARM_TWIST = [(45, 0.0), (80, 0.45), (108, 0.8)]   # ... and 1.0 at the wrist
# Arm loft stations: ~11 px apart along the shafts, 7 px over the elbow
# (the rig's ひじ補助 band) and 6 px into the wrist.
ARM_STATIONS = ([('S', d) for d in (38, 49, 60, 72, 84, 96, 108, 119)]
                + [('E', d) for d in (-21, -14, -7, 0, 7, 14, 21, 31, 44, 58, 72, 86, 99, 111)]
                + [('W', d) for d in (-12, -6, 0)])
# Hand rings: (distance from the wrist along the hand px, radii as above: toward
# the thumb, toward the little finger, palm side, back). Round 8: the palm ~5%
# wider and ~12% thicker than round 7's flat paddle, with squarer edges, on the
# 1.53 : 1 wrist. (+12% / +20% read as a swollen mitten in pairwise review.)
HAND_R = [(0, (11.2, 11.2, 7.3, 7.3)), (8, (13.2, 12.8, 7.8, 7.6)), (19, (17.2, 16.6, 8.2, 7.8)),
          (28, (18.3, 17.7, 7.6, 7.3)), (34, (17.8, 17.2, 6.8, 6.6)), (39, (15.3, 14.7, 6.2, 5.9)),
          (42, (10.2, 9.6, 4.6, 4.3))]
HAND_STATIONS = (4, 8, 13, 19, 24, 28, 31, 34, 36.5, 39, 41, 42)
# superellipse exponent of the hand rings (wrist -> palm): squarer palm edges
HAND_P = ((0, 2.0), (12, 2.3))
# thumb ball along the hand (px from the wrist): ramps in, full, full, out
THENAR = (3, 10, 20, 31)


# Shape master on the hands (volume only): the master's hands are mittens, turned
# about the forearm against ours, so they give no ring-by-ring radii. Instead the
# palm's width and thickness and the fingers' thickness are measured in the master's
# own principal frame of each hand (HAND_MASTER_SLICES, px along the hand from our
# wrist) and the palm rings, the knuckle row and the finger sections take this share
# of the ratio master / ours. The fingers keep their own separation and topology.
HAND_MASTER_W = (0.5, 0.5, 0.25)  # palm width, palm thickness, finger thickness
HAND_MASTER_CAP = 0.15            # no scale beyond 1 -+ this (the mitten's fingers are one slab)
HAND_MASTER_SLICES = ((14.0, 32.0), (40.0, 56.0))   # palm, fingers
HAND_MASTER_REACH = 30.0          # px round the hand's axis
HAND_MASTER_LABELS = ('body', 'sleeves')
_HAND_MASTER = None
HAND_MASTER_INFO = {}


def _hand_master():
    """(palm width, palm thickness, finger thickness) scale factors from the master."""
    global _HAND_MASTER
    if _HAND_MASTER is not None:
        return _HAND_MASTER
    if not MASTER:
        _HAND_MASTER = (1.0, 1.0, 1.0)
        return _HAND_MASTER
    from .. import shape as master
    # the master's hand surface: its skin and the cuff-side patches of the hand that
    # were labelled sleeves (the label sheet), nothing else (the skirt and the hair
    # hang within reach of the hand)
    V, F = master.data()[:2]
    V = V[np.unique(F[master.faces(HAND_MASTER_LABELS)])]
    k = px(1)
    W0 = np.array(P(*WRIST))
    d0, w0, n0 = (np.array(v) for v in hand_frame())
    (p0, p1), (f0, f1) = HAND_MASTER_SLICES
    meas = []
    for sgn in (1.0, -1.0):
        m3 = np.array([sgn, 1.0, 1.0])
        Wd, dd = W0 * m3, d0 * m3
        rel = V - Wd
        t = rel @ dd
        sel = (np.linalg.norm(rel - np.outer(t, dd), axis=1) < HAND_MASTER_REACH * k) & (t > -5 * k) & (t < 80 * k)
        Q = V[sel]
        if len(Q) < 50:
            continue
        _, _, vt = np.linalg.svd(Q - Q.mean(0), full_matrices=False)
        a1, a2 = vt[1], vt[2]          # across the hand, through it
        tq = (Q - Wd) @ dd

        def ext(lo, hi, ax):
            q = Q[(tq >= lo * k) & (tq < hi * k)] @ ax
            return (np.percentile(q, 99) - np.percentile(q, 1)) / k if len(q) >= 10 else np.nan
        meas.append((ext(p0, p1, a1), ext(p0, p1, a2), ext(f0, f1, a2)))
    if not meas:
        _HAND_MASTER = (1.0, 1.0, 1.0)
        return _HAND_MASTER
    pw, pt, ft = np.nanmean(np.array(meas, dtype=np.float64), 0)
    # ours over the same slices
    ts = [t for t in HAND_STATIONS if p0 <= t <= p1]
    ow = np.mean([sum(_interp(HAND_R, t)[:2]) for t in ts])
    ot = np.mean([sum(_interp(HAND_R, t)[2:]) for t in ts])
    of = np.mean([2 * f[4] for f in FINGERS]) * (FINGER_SECTION[1] + FINGER_SECTION[2]) / 2 * FINGER_TAPER[1]
    ww, wt, wf = HAND_MASTER_W
    c = HAND_MASTER_CAP
    _HAND_MASTER = tuple(float(np.clip(1 + wgt * (m / o - 1), 1 - c, 1 + c)) if np.isfinite(m) else 1.0
                         for wgt, m, o in ((ww, pw, ow), (wt, pt, ot), (wf, ft, of)))
    HAND_MASTER_INFO.update(master=(pw, pt, ft), ours=(ow, ot, of), scale=_HAND_MASTER)
    return _HAND_MASTER


def _hand_r(t):
    """HAND_R at `t` px from the wrist, scaled toward the master's palm (none at the wrist)."""
    sw, st, _ = _hand_master()
    f = smoothstep(0.0, 10.0, t)
    a, b, c, d = _interp(HAND_R, t)
    gw, gt = 1 + (sw - 1) * f, 1 + (st - 1) * f
    return (a * gw, b * gw, c * gt, d * gt)


def hand_frame():
    """Unit vectors (d: along the hand, w: toward the thumb, n: palm normal)."""
    d = Vector((HAND_DIR[0], HAND_DIR[1], -HAND_DIR[2])).normalized()
    perp_up = Vector((-d.z, 0, d.x)).normalized()      # in the front plane, upward
    # The sheet shows the back of the hand with the thumb on the lower, inner
    # edge (palm turned back toward the thigh): the thumb side points forward
    # and down.
    w = (-perp_up * HAND_W_FRONT + Vector((0, -1, 0)) * math.sqrt(1 - HAND_W_FRONT ** 2))
    w = (w - d * w.dot(d)).normalized()
    n = d.cross(w)   # palm side for the left hand
    return d, w, n


def _palm_shape(t_px):
    """Ring-local offsets (side=toward thumb, up=palm side) for the hand rings
    at `t_px` along the hand: a shallow palm arch, the thenar (thumb ball)
    and hypothenar pads, a domed back over the metacarpals, and knuckles
    staggered along the palm end (index/middle longest, the little finger side
    shortest)."""
    k = px(1)
    # round 8: the thumb ball starts at the heel of the palm, where the thumb now
    # roots (build_fingers), and stands ~5 mm proud
    t0, t1, t2, t3 = THENAR
    thenar = smoothstep(t0, t1, t_px) * (1 - smoothstep(t2, t3, t_px))
    hypo = smoothstep(4, 14, t_px) * (1 - smoothstep(24, 34, t_px))
    arch = smoothstep(8, 18, t_px) * (1 - smoothstep(32, 40, t_px))
    knuck = smoothstep(26, 33, t_px) * (1 - smoothstep(37, 41, t_px))
    stagger = smoothstep(24, 36, t_px)

    def f(dx, dy):
        a = b = d = 0.0
        if dy > 0:     # palm side
            b -= 1.3 * arch * dy * max(0.0, 1 - (dx / 0.7) ** 2)          # hollow of the palm
            pad = thenar * 6.5 * max(0.0, dx) ** 1.2 * dy ** 0.8          # thumb ball
            pad += hypo * 1.1 * max(0.0, -dx) ** 1.5 * dy ** 0.7          # little finger pad
            a += pad * 0.55 * (1 if dx > 0 else -1)
            b += pad
        else:          # back of the hand: a dome over the metacarpals rising into the
            # knuckle row, highest over the middle and ring fingers (transverse arch)
            b += (0.8 * arch + 1.4 * knuck) * dy * (1 - dx * dx)
        # the thumb-side edge swells out along the thumb's metacarpal, so the outline
        # runs from the wrist into the thumb instead of meeting it at a corner
        a += thenar * 2.2 * max(0.0, dx) ** 3 * max(0.0, 1 - ((dy - 0.35) / 0.9) ** 2)
        d += stagger * (2.6 * dx - 2.0 * dx * dx)                          # knuckle arc
        return a * k, b * k, d * k
    return f


# Shape master on the arm rings: the bare shoulder cap (the transition rings follow
# the first round ring), fading out under the sleeve's top band (px of arc from
# SHOULDER: full, none). Inside the sleeves the arm keeps its procedural shape (the
# master's skin there is stray: cuff ruffles and ribbons labelled body; following it
# pushed the upper arm through the sleeve's band); the hand rings keep their own
# (HAND_R, _hand_master). Smoothing (stations, ring vertices) of the deltas, the weight.
ARM_MASTER_ARC = (50.0, 75.0)
ARM_MASTER_SMOOTH = ((0.8, 1.0), (1.5, 2.0))
_ARM_MASTER = {}


def _arm_master(centers, frames, rings, use):
    """Arm rings moved radially (in each ring's plane) toward the shape master where
    its skin is outermost, by the station weights use[i] (0..1)."""
    if not MASTER or not any(u > 0 for u in use):
        return rings
    key = tuple(round(c, 6) for co in centers for c in co)
    C, D, R = [], [], []
    for i, ring in enumerate(rings):
        t = frames[i][0]
        for co in ring:
            v = co - centers[i]
            v = v - t * v.dot(t)
            C.append(tuple(centers[i]))
            D.append(tuple(v.normalized()) if v.length > 1e-9 else tuple(frames[i][1]))
            R.append(max(v.length, 1e-6))
    if key not in _ARM_MASTER:
        sel = np.repeat(np.array(use) > 0, ARM_N)
        r_t = np.full(len(R), np.nan)
        r_t[sel] = _master_radii(np.array(C)[sel], np.array(D)[sel], np.array(R)[sel])
        delta = ((r_t - np.array(R)) / px(1) - MASTER_INSET).reshape(len(rings), ARM_N)
        # the stations without samples (weight 0) take part in the smoothing, so the
        # master's share fades out instead of stopping at a ring
        w = np.repeat(np.array(use, dtype=np.float64)[:, None], ARM_N, 1)
        _ARM_MASTER[key] = _blend_table(delta, w, *ARM_MASTER_SMOOTH, periodic=True) * w
    off = _ARM_MASTER[key]
    return [[co + Vector(D[i * ARM_N + k]) * px(off[i, k]) for k, co in enumerate(ring)]
            for i, ring in enumerate(rings)]


def _elbow_shape(d):
    """Ring-local offsets (see _palm_shape) of ELBOW_BUMPS at `d` px from ELBOW along the
    arm, or None away from the elbow."""
    bumps = []
    for a, c, sg, (lx, ly), q in ELBOW_BUMPS:
        g = math.exp(-0.5 * ((d - c) / sg) ** 2)
        if g > 1e-3:
            ln = math.hypot(lx, ly)
            bumps.append((a * g, lx / ln, ly / ln, q))
    if not bumps:
        return None
    k = px(1)

    def f(dx, dy):
        r = sum(a * max(0.0, dx * lx + dy * ly) ** q for a, lx, ly, q in bumps)
        return dx * r * k, dy * r * k, 0.0
    return f


def arm_rings(loop, tans):
    """Positions (left side) of the arm rings from the socket border to the
    palm end, and the frames of the round part.

    loop: socket border positions (left side, arm-ring order); tans: their unit
    tangents leaving the torso into the hole."""
    S, E, W = P(*SHOULDER), P(*ELBOW), P(*WRIST)
    k = px(1)
    lu, lf = (E - S).length / k, (W - E).length / k
    u = (E - S).normalized()
    f = (W - E).normalized()
    d, w, n = hand_frame()

    def front_side(t):
        return Vector((-t.z, 0, t.x)).normalized()  # outward/up in front plane

    def arc(key):
        base, off = key
        return off + {'S': 0.0, 'E': lu, 'W': lu + lf}[base]
    radii_tab = [(arc(key), r) for key, r in ARM_R]
    s_all = [arc(key) for key in ARM_STATIONS]
    if any(b <= a for a, b in zip(s_all, s_all[1:])):
        raise RuntimeError('body: ARM_STATIONS out of order for the current SHOULDER / ELBOW / WRIST')
    twist_tab = [(lu + s, t) for s, t in ARM_TWIST] + [(lu + lf, 1.0)]
    L = ELBOW_FILLET
    fa, fb = E - u * L * k, E + f * L * k

    def centre(s):
        if abs(s - lu) < L:       # the rounded elbow (quadratic Bezier through the corner)
            t = (s - lu + L) / (2 * L)
            return fa * (1 - t) ** 2 + E * (2 * t * (1 - t)) + fb * t * t
        return S + u * s * k if s <= lu else E + f * (s - lu) * k
    centers, hints, radii, hand_t = [], [], [], []
    for key in ARM_STATIONS:
        s = arc(key)
        centers.append(centre(s))
        b = smoothstep(lu - 14, lu + 14, s)       # the frame turns over the elbow
        ha = front_side((u * (1 - b) + f * b).normalized())
        tw = _interp(twist_tab, s)
        hints.append((ha * (1 - tw) + w * tw).normalized())
        radii.append(tuple(px(x) for x in _interp(radii_tab, s)))
        hand_t.append(0 if key == ('W', 0) else None)
    for t in HAND_STATIONS:
        centers.append(W + d * t * k)
        hints.append(w.copy())
        radii.append(tuple(px(x) for x in _hand_r(t)))
        hand_t.append(t)

    shapes = [_palm_shape(ht) if ht is not None else _elbow_shape(arc(key) - lu)
              for key, ht in zip(list(ARM_STATIONS) + [None] * len(HAND_STATIONS), hand_t)]

    def shape(i, dx, dy):
        return shapes[i](dx, dy) if shapes[i] else (0.0, 0.0, 0.0)
    pexp = [2.0 if ht is None else _interp(HAND_P, ht) for ht in hand_t]
    rings, frames = ring_points(centers, hints, radii, ARM_N, p=pexp, shape=shape)
    a0, a1 = ARM_MASTER_ARC
    rings = _arm_master(centers, frames, rings,
                        [0.0 if ht is not None else 1 - smoothstep(a0, a1, arc(key))
                         for key, ht in zip(list(ARM_STATIONS) + [None] * len(HAND_STATIONS), hand_t)])
    # transition: cubic Hermite from each socket vertex (leaving along the
    # torso surface) to its vertex on the first round ring (arriving along the arm)
    t1 = frames[0][0]
    first = rings[0]
    trans = []
    for s in SOCKET_STEPS:
        h00, h10 = 2 * s ** 3 - 3 * s ** 2 + 1, s ** 3 - 2 * s ** 2 + s
        h01, h11 = -2 * s ** 3 + 3 * s ** 2, s ** 3 - s ** 2
        ring = []
        for j, (p0, t0, p1) in enumerate(zip(loop, tans, first)):
            L = (p1 - p0).length
            c = 0.5 + 0.5 * math.cos(2 * math.pi * j / len(loop))   # 1 on the cap, 0 in the armpit
            ta, tb = (i + (o - i) * c for i, o in zip(SOCKET_TAN_INNER, SOCKET_TAN_OUTER))
            ring.append(h00 * p0 + h10 * t0 * (L * ta) + h01 * p1 + h11 * t1 * (L * tb))
        # front / back quadrants of the middle rings: a little extra fullness
        # (none at the torso border or the first round ring), so the armpit
        # folds stay round instead of narrowing into a web
        c = sum(ring, Vector()) / len(ring)
        amp = px(SOCKET_FULL) * math.sin(math.pi * s)
        for j, p in enumerate(ring):
            q = math.sin(2 * math.pi * j / len(ring)) ** 2      # 1 front / back, 0 cap / armpit
            r = p - c
            r -= t1 * r.dot(t1)
            if r.length > 1e-9:
                ring[j] = p + r.normalized() * amp * q
        trans.append(ring)
    return trans + rings, frames


def build_arm(bm, loop, tans, side):
    """Arm + hand + fingers for one side (+1 left, -1 right) from its socket."""
    mirror = side < 0
    # socket data are in world space; design the left arm, mirror for the right
    if mirror:
        tans = [Vector((-t.x, t.y, t.z)) for t in tans]
        lp = [Vector((-v.co.x, v.co.y, v.co.z)) for v in loop]
    else:
        lp = [v.co.copy() for v in loop]
    rings, frames = arm_rings(lp, tans)
    skin_rings(bm, [loop] + rings, frames, cap1='pole', cap1_len=px(2), mirror=mirror)
    W = P(*WRIST)
    d, w, n = hand_frame()
    build_fingers(bm, W, d, w, n, mirror)


# finger: (offset along w px, knuckle distance px, splay deg, segment lengths px,
#          base radius px, curl deg per joint, palm-side offset px: - = toward the back)
# Round 8: the fingers are held together, 1-2 mm apart at the proximal segment, with
# little splay (3 / 0 / -3 / -7 deg; round 7 fanned them 5.5 / -0.5 / -5 / -12), the
# proximal segment ~46% of the finger, and the middle and ring knuckles ~4 mm higher
# on the back of the hand than the index and little ones (the transverse arch).
FINGERS = [
    (12.5, 38.0, 3.0, (18, 11.5, 9.5), 3.9, 5.0, 0.3),      # index
    (4.2, 40.0, 0.0, (19.5, 12.5, 10), 4.1, 7.0, -2.2),     # middle
    (-4.0, 38.0, -3.0, (18, 11.5, 9.5), 3.9, 9.0, -1.8),    # ring
    (-11.6, 34.0, -7.0, (13.5, 8.5, 7.5), 3.3, 11.0, 0.8),  # pinky
]
JOINT_RINGS = (0.22, 0.78, 1.0)  # ring positions along each finger segment
FINGER_TAPER = (1.0, 0.86, 0.74, 0.62)   # radius at knuckle, two middle joints, tip
KNUCKLE_SWELL = 1.04                     # joint rings a little fuller than the shafts
FINGER_N = 8                             # vertices per finger ring
# Finger section (round 8): radii as shares of the ring radius, across / back of the
# hand / palm side: ~10% deeper than wide (round 7: 15% flatter than wide).
FINGER_SECTION = (0.9, 0.95, 1.05)
# Joint relief as shares of the ring radius: the knuckle stands out on the back of
# each finger joint and the skin creases on the palm side; between the joints the
# palm side is a little fuller (the finger pads).
JOINT_BUMP, JOINT_CREASE, FINGER_PAD = 0.10, 0.10, 0.05
# Fingertip dome: rings (distance past the last ring, radius) as shares of the tip
# radius; the last entry is the pole.
TIP_DOME = ((0.45, 0.88), (0.8, 0.55), (1.0, 0.0))
# Thumb (round 8): rooted at the heel of the palm inside the thumb ball, ~20% of the
# way to the knuckles and ~6 mm toward the palm (round 7: 35%, 3.5 mm), leaving the
# side of the palm heel through the ball, so the outline runs from the wrist into the
# thumb (round 7's thumb hung from the middle of the palm like a separate stick).
# (along d, toward the thumb w, toward the palm n) px; direction (d, w, n);
# segments (metacarpal, mostly inside the ball; proximal; distal) px; radius px; curl deg
THUMB = ((9.0, 8.5, 3.2), (0.86, 0.47, 0.20), (19, 14, 11), 5.6, 10.0)
THUMB_TAPER = (1.0, 0.76, 0.70, 0.59)   # a thick metacarpal inside the ball, then the free thumb


def _rot(v, axis, deg):
    return Matrix.Rotation(math.radians(deg), 3, axis) @ v


def finger(bm, base, direction, bend_axis, seg_len, r0, curl, mirror, n=FINGER_N, taper=FINGER_TAPER,
           section=FINGER_SECTION):
    pts = [base - direction * px(r0 * 0.6)]
    dirs = [direction]
    rs = [r0 * 0.82]
    kind = [None]
    cur, dcur = base, direction
    pts.append(cur)
    dirs.append(dcur)
    rs.append(r0)
    kind.append(None)
    # rings just after / before each knuckle and on it, so every joint bends
    # over three loops instead of one
    rtip = r0 * taper[-1]
    for j, L in enumerate(seg_len):
        if j == len(seg_len) - 1:
            L -= rtip * TIP_DOME[-1][0]     # the dome below keeps the finger's length
        dcur = _rot(dcur, bend_axis, curl * (0.6 if j == 0 else 1.0))
        ra, rb = taper[j], taper[j + 1]
        for t in JOINT_RINGS:
            pts.append(cur + dcur * px(L * t))
            dirs.append(dcur)
            r = ra + (rb - ra) * t
            joint = t == 1.0 and j < len(seg_len) - 1
            if joint:
                r *= KNUCKLE_SWELL
            rs.append(r0 * r)
            kind.append('joint' if joint else ('pad' if t < 1.0 else None))
        cur = cur + dcur * px(L)
    # a rounded fingertip (round 7: a cone to a pole, a pencil point in clay)
    for f, k in TIP_DOME[:-1]:
        pts.append(cur + dcur * px(rtip * f))
        dirs.append(dcur)
        rs.append(rtip * k)
        kind.append(None)
    sw, sb, sp = section
    radii = [(px(r) * sw, px(r) * sw, px(r) * sb, px(r) * sp) for r in rs]
    # side hint = across the finger (in the palm plane); up = toward the back of the hand

    def shape(i, dx, dy):
        r = px(rs[i])
        if kind[i] == 'joint':
            b = r * (JOINT_BUMP if dy > 0 else JOINT_CREASE) * dy * dy
        elif kind[i] == 'pad' and dy < 0:
            b = -r * FINGER_PAD * dy * dy
        else:
            b = 0.0
        return 0.0, b, 0.0
    hints = [bend_axis.copy() for _ in dirs]
    rings, frames = ring_points(pts, hints, radii, n, shape=shape)
    skin_rings(bm, rings, frames, cap0='pole', cap1='pole', cap0_len=px(1.0),
               cap1_len=px(rtip * (TIP_DOME[-1][0] - TIP_DOME[-2][0])), mirror=mirror)


def build_fingers(bm, W, d, w, n, mirror=False):
    k = px(1)
    # the shape master's palm width spaces the fingers and sets their width (so the
    # gaps between them keep their share), its finger thickness their depth
    sw, _, sf = _hand_master()
    fs, fb, fp = FINGER_SECTION
    sec = (fs * sw, fb * sf, fp * sf)
    for off, kd, splay, segs, r0, curl, lift in FINGERS:
        base = W + d * kd * k + w * off * sw * k + n * (0.5 + lift) * k
        direction = _rot(d, n, splay)       # splay within the palm plane
        axis = direction.cross(n).normalized()  # rotating about it bends toward +n (palm)
        finger(bm, base, direction, axis, segs, r0, curl, mirror, section=sec)
    # thumb: from inside the thumb ball at the heel of the palm, angled out toward
    # the thumb side and turned toward the palm, out of the fingers' plane
    (ta, tw, tn), (da, dw, dn), segs, r0, curl = THUMB
    base = W + d * ta * k + w * tw * sw * k + n * tn * k
    tdir = (d * da + w * dw + n * dn).normalized()
    axis = tdir.cross(n).normalized()
    finger(bm, base, tdir, axis, segs, r0, curl, mirror, taper=THUMB_TAPER, section=sec)


# ---------------------------------------------------------------- legs + feet
# Front view: row -> (outer, inner) offsets of the left leg from the midline.
# Side view: row -> (front y, back y). Measured every 10 rows on the reference
# (rows <= 620 are under the petticoat and extrapolated toward the hip).
LEG_FRONT = {
    455: (60, 6), 472: (62.3, 6.5), 490: (64.5, 7), 510: (65, 8.5), 530: (65.5, 10),
    550: (65.3, 11.2), 570: (65, 12.5), 600: (64.5, 14.5),
    630: (63, 16.5), 640: (61.5, 15.8), 650: (61.5, 16.5), 660: (63.5, 17.5),
    670: (65.5, 19.5), 680: (67.5, 20), 690: (69.5, 20.5), 700: (70.5, 20),
    710: (70.5, 19.5), 720: (69.5, 20.5), 730: (67.5, 22), 740: (65.5, 22),
    750: (63.5, 22.5), 760: (61, 23.5), 770: (58.5, 24), 780: (56, 24),
    790: (54, 24), 800: (51.5, 24), 810: (49.5, 23.5),
    # round 8: the ankle no longer pinches to 2.5 cm above the shoe. The sheet's
    # skin stays ~25 px wide down into the shoe opening (rows 800-860); below the
    # malleoli the leg runs on into the heel, round the ankle pivot (ANKLE_ROW)
    820: (48.5, 23.5), 830: (47.5, 22.5), 842: (47, 21.5), 852: (46, 21.5),
    862: (42.5, 23), 874: (39, 25),
}
LEG_SIDE = {
    455: (-50, 22), 472: (-49, 21), 490: (-48, 20), 510: (-47, 18), 530: (-46, 16),
    550: (-45, 14.5), 570: (-44, 13), 600: (-42, 11),
    630: (-41, 9), 640: (-38.5, 10), 650: (-35.5, 12), 660: (-32, 15.5),
    670: (-30.5, 19), 680: (-30, 22), 690: (-29, 24), 700: (-28, 25),
    710: (-27, 25), 720: (-27, 23), 730: (-26, 23), 740: (-25, 21),
    750: (-24, 18), 760: (-24, 17), 770: (-23, 15), 780: (-23, 13),
    790: (-23, 11), 800: (-23, 9), 810: (-24, 8.5),
    # round 8: as deep as the sheet's ankle (rows 812-842 measure -25..+9), the
    # heel swelling out behind it below the Achilles tendon
    820: (-25, 9), 830: (-25, 9.5), 842: (-24, 10), 852: (-22, 11),
    862: (-17, 11.5), 874: (-12, 11),
}
# Loft rows: ~13 rows apart over the hip / groin (the leg swings), ~15 down the
# hidden thigh, then 6-7 rows (about 1 cm) over the whole knee band the rig
# bends (rig.JOINT_ALONG, rows ~650-730), ~11 down the shin, and 7 again
# (about 1 cm) over the ankle band the foot bends about (rows ~830-873).
LEG_ROWS = (455, 467, 480, 493, 506, 520, 535, 550, 566, 582, 598, 612, 624, 635, 645,
            654, 662, 670, 677, 684, 691, 697, 703, 709, 715, 721, 728, 735, 743,
            752, 762, 773, 785, 797, 809, 820, 830, 838, 845, 852, 859, 866, 873)
LEG_N = 28        # vertices per leg ring: a round terminator on the cel shade
# Knee pivot exported to the rig (obj['levi_joints']['knee']): the
# thigh-to-shin transition, above the widest leg section at row ~700 (the
# top of the calf behind the knee), so the bend turns about the kneecap and
# the calf stays below it. Its depth is KNEE_FWD px ahead of the leg axis, as
# the rig's own fit does, so IK bends the knee forward.
KNEE_ROW = 690.0
# Round 10 (the 风堇 MMD knee, user decision): 5 px puts the pivot ~43% of the leg's depth
# behind the front skin (round 9: 15 px, 23%), as in the reference, so the kneecap's skin
# wraps round a corner. That is ~2 mm ahead of the hip-ankle line; the leg IK starts from a
# prebent knee (rig.KNEE_IK_PREBEND) to find the bend. 2.5 px (47%) lost the pairwise review
# to 5 (0-6, 0-8) and failed the IK in sit_chair with an 8 deg prebend; 0 px (52%) widened
# the bend span. (Round 8, 9 px: squat stretch x1.54 -> x1.75 with the old wide band.)
KNEE_FWD = 5.0
LEG_SIGMA = 5.0   # px: Gaussian smoothing of the measured profiles (no kinks)
# Wider smoothing where the thigh narrows above the knee and the calf swells
# below it (rows ~620-700), so the knee-to-calf contour is one soft curve in
# every view instead of a corner at the top of the knee.
LEG_SIGMA_KNEE = (600, 640, 700, 730, 10.0)   # ramp in, full, full, ramp out rows; sigma px
LEG_SIGMA_SIDE = 9.0   # the side profile has the sharper turns (thigh front into the knee)
# Kneecap: a broad, rounded dome pushed forward (px) on the front of the knee,
# (row, amplitude, vertical sigma): full at the front centre, fading out to
# the sides. A narrow push or a dip below it reads as an angular shade edge.
KNEECAP = (KNEE_ROW + 2.0, 2.0, 15.0)
# Crease behind the knee (row, depth px, vertical sigma): the back of the knee
# is drawn in a little where the skin folds in a squat (between the two knee
# helpers' knots), so the fold lands on a loop instead of across quads.
KNEE_CREASE = (KNEE_ROW + 6.0, 0.7, 5.0)
# Gluteal fold under the buttock at the back of the thigh (hidden under the
# skirt; the hip-extension fold of a stride).
GLUTE_FOLD = (493.0, 0.8, 7.0)
# Calf / shin: below the knee the calf fullness sits at the back (more on the
# inner side) and the shin front stays straight: px radial offsets on the
# oblique sectors only, so the measured front / side extremes are unchanged.
CALF = ((705, 725, 775, 815), 1.3, 0.5, -0.8)   # rows (ramp in, full, full, out), back-inner, back-outer, front
# Round 9: the inner (medial) calf head sits lower than the outer: the back-inner
# fullness uses the CALF rows moved down by this many rows (~1.7 cm). 0 = round 8. Its
# tail (to row 826) eases the inner hollow beside the Achilles tendon (ACHILLES, from row
# 806) by up to ~0.3 px; fading it out by row 815 instead lost the pairwise review
# (2 / 2 and 8 / 12 against 16 / 4 and 7 / 5 over three runs each). (A swell on the inner
# side itself, for a low inner calf curve in the front view, left a dip between the
# wider knee and the calf: "small inward kink".)
CALF_INNER_DROP = 11.0
# Round 9: the knee a little wider at the condyles (row, vertical sigma px, inner px,
# outer px), sides only: ~4.5 mm across at z 0.40, a little more on the inner side.
# The rounded kneecap and the knee's depth are unchanged. A broad swell (sigma 18 px,
# ~2.8 cm) blends knee and calf into one curve; narrower ones (12-16 px, 1.8-2.2 px
# inner) read as a knob over a waisted shin and lost the pairwise review. Inner and
# outer 0 = round 8.
KNEE_WIDE = (KNEE_ROW + 2.0, 18.0, 1.6, 1.3)
# Ankle (round 8). The rig's ankle pivot (obj['levi_joints']['ankle']) is the
# real ankle joint inside the shoe, about 4.5 cm above the heel seat (row 899),
# not spec ankle_z (row 830, 6 cm higher, where the shin was thinnest and every
# foot turn bent it into an hourglass). ANKLE_BACK px behind the leg axis there.
ANKLE_ROW = 868.0
ANKLE_BACK = 1.0
# Malleoli: (row, amplitude px, vertical sigma px, angle round from straight
# out (+ toward the back), angular sigma rad); the inner one sits ~1 cm higher.
# (Over 4 px / 0.45 rad they read as a round knob when the foot turned; at 1.1-1.2 px
# the ankle lost the pairwise review at rest, "constricted where it enters the shoe".)
MALLEOLUS_OUT = (858.0, 1.5, 5.0, 0.25, 0.6)
MALLEOLUS_IN = (851.0, 1.7, 5.0, 0.15, 0.6)
# Achilles tendon: the back obliques either side of the tendon are drawn in
# (rows ramp in, full, full, out; depth px), so the tendon stands as a ridge
# between the calf and the heel.
ACHILLES = ((806, 822, 846, 860), 0.9)
# Heel: the back of the leg swells out under the tendon into the heel (row, px, sigma).
HEEL_BULGE = (870.0, 1.2, 5.0)


def _smoothed(table, row, sigma=LEG_SIGMA):
    """Gaussian-smoothed piecewise-linear profile (per column) at `row`; the
    window is renormalised at the table's ends so they stay put."""
    rows = sorted(table)
    lo, hi = rows[0], rows[-1]

    def lin(r):
        r = min(max(r, lo), hi)
        for a, b in zip(rows, rows[1:]):
            if r <= b:
                t = (r - a) / (b - a)
                return [x + (y - x) * t for x, y in zip(table[a], table[b])]
        return list(table[hi])
    if row <= lo or row >= hi:
        return lin(row)
    acc, wsum = [0.0, 0.0], 0.0
    span = min(3 * sigma, row - lo, hi - row)
    steps = max(1, int(span))
    for j in range(-steps, steps + 1):
        r = row + span * j / steps
        g = math.exp(-0.5 * ((r - row) / sigma) ** 2)
        v = lin(r)
        acc = [a + g * x for a, x in zip(acc, v)]
        wsum += g
    return [a / wsum for a in acc]


def _bump(spec_, row):
    c, amp, sig = spec_
    return amp * math.exp(-0.5 * ((row - c) / sig) ** 2)


def _leg_shape(row):
    """shape(dx, dy) -> (d_side, d_up) px for a leg ring at `row` (dx: + outer,
    dy: + front, unit superellipse directions)."""
    knee = _bump(KNEECAP, row)
    crease = _bump(KNEE_CREASE, row)
    glute = _bump(GLUTE_FOLD, row)
    (c0, c1, c2, c3), bi, bo, fr = CALF
    calf = smoothstep(c0, c1, row) * (1 - smoothstep(c2, c3, row))
    dr = CALF_INNER_DROP
    calf_in = smoothstep(c0 + dr, c1 + dr, row) * (1 - smoothstep(c2 + dr, c3 + dr, row))
    kw = _bump((KNEE_WIDE[0], 1.0, KNEE_WIDE[1]), row)
    knee_in, knee_out = kw * KNEE_WIDE[2], kw * KNEE_WIDE[3]
    mal = [(_bump(m[:3], row), m[3], m[4], sgn) for m, sgn in ((MALLEOLUS_OUT, 1.0), (MALLEOLUS_IN, -1.0))]
    (a0, a1, a2, a3), adep = ACHILLES
    ach = adep * smoothstep(a0, a1, row) * (1 - smoothstep(a2, a3, row))
    heel = _bump(HEEL_BULGE, row)

    def f(dx, dy):
        a = b = 0.0
        if dy > 0:
            b += knee * dy * dy
        else:
            b += (crease + glute) * dy * dy        # toward the front: drawn in
            b -= heel * dy * dy                    # the heel swells out behind
        if calf or calf_in:
            obl = (2 * dx * dy) ** 2               # 0 on the axes, 1 at 45 deg
            amt = obl * (calf * fr if dy > 0 else (calf * bo if dx > 0 else calf_in * bi))
            a += amt * dx
            b += amt * dy
        if dx < 0:
            a -= knee_in * dx * dx                 # inner side: outward is -x
        else:
            a += knee_out * dx * dx
        amt = 0.0
        for m, ang0, sig, sgn in mal:
            if m > 1e-4 and dx * sgn > 0:
                ang = math.atan2(-dy, dx * sgn)    # 0 straight out (in), + toward the back
                amt += m * math.exp(-0.5 * ((ang - ang0) / sig) ** 2)
        if ach > 1e-4 and dy < 0:
            amt -= ach * (2 * dx * dy) ** 2        # the hollows beside the tendon
        a += amt * dx
        b += amt * dy
        return a, b
    return f


def knee_joint():
    """Left knee pivot (world): on the leg axis at KNEE_ROW, KNEE_FWD px forward."""
    xo, xi = _smoothed(LEG_FRONT, KNEE_ROW, 10.0)
    yf, yb = _smoothed(LEG_SIDE, KNEE_ROW, LEG_SIGMA_SIDE)
    return P((xo + xi) / 2, (yf + yb) / 2 - KNEE_FWD, KNEE_ROW)


# Shape master on the legs. The master's skin counts from the petticoat's hem down
# (LEG_MASTER_ROWS: ramp in, full, full, out); its thighs inside the skirt are
# partial and lumpy (cloth-fused patches labelled body), so the hidden thigh keeps
# its procedural shape, but takes the hem row's correction (axis shift and section
# scale), fading out toward the hip (THIGH_HOLD rows: none, full), so the thigh runs
# into the fitted knee without a waist at the hem. The ribbons of the shoes wrap the
# ankle from row ~800 and shoes.py ties its laces to the plain LEG_FRONT / LEG_SIDE
# ellipses there, so the ankle keeps its procedural shape.
LEG_MASTER_ROWS = (604, 628, 755, 805)
THIGH_HOLD = (470, 628)
LEG_CLOTH_CLEAR = 6.0 / 1000 * spec.PX_PER_M   # px the thigh keeps inside the master's skirt / petticoat
LEG_MASTER_STEP = 2.0      # px between table rows
LEG_MASTER_N = 48          # angles round the ring
# The legs take only the master's proportions, not its relief: per row the delta is
# fitted by a low-order Fourier series round the ring (order 1: the axis shifts,
# order 2: the section's width / depth), smoothed along the leg (rows px). Our
# anatomy (kneecap, calf, tendon) stays. Following the master ring by ring (its knee
# hollows, the narrowing between knee and calf) lost the pairwise review 2-22 / 0-20:
# "wavy", "kinked knee", "pinched".
LEG_MASTER_ORDER = 2
LEG_MASTER_ROW_SIGMA = 14.0
LEG_MASTER_MIN_VALID = 0.4     # rows with fewer samples round the ring don't count
LEG_MASTER_RIDGE = (0.02, 0.5)  # ridge on (order 1, order 2) terms, in sample counts (keeps gaps tame)
# The master's share around the knee (rows KNEE_ROW +- KNEE_MASTER_BAND, smooth):
# the knee's style is an open question, so its outer shape can be held nearer round 9's.
KNEE_MASTER_W = 1.0
KNEE_MASTER_BAND = (14.0, 30.0)
_LEG_MASTER = None
LEG_MASTER_INFO = {}


def _leg_lowpass(delta, ang):
    """delta [row, angle] (NaN = no sample) -> its low-order Fourier fit round each
    ring (LEG_MASTER_ORDER), the coefficients smoothed along the rows (weighted by the
    rows' sample share, LEG_MASTER_ROW_SIGMA)."""
    terms = [np.ones_like(ang)]
    lam = [0.0]
    for k in range(1, LEG_MASTER_ORDER + 1):
        terms += [np.cos(k * ang), np.sin(k * ang)]
        lam += [LEG_MASTER_RIDGE[min(k, 2) - 1]] * 2
    A = np.stack(terms, 1)
    coef = np.zeros((len(delta), len(terms)))
    wrow = np.zeros(len(delta))
    for i, d in enumerate(delta):
        ok = np.isfinite(d)
        if ok.mean() < LEG_MASTER_MIN_VALID:
            continue
        Ao = A[ok]
        coef[i] = np.linalg.solve(Ao.T @ Ao + np.diag(lam) * ok.sum(), Ao.T @ d[ok])
        wrow[i] = ok.mean()
    # normalised Gaussian smoothing along the rows (rows without a fit don't count)
    h = int(math.ceil(3 * LEG_MASTER_ROW_SIGMA / LEG_MASTER_STEP))
    g = np.exp(-0.5 * (np.arange(-h, h + 1) * LEG_MASTER_STEP / LEG_MASTER_ROW_SIGMA) ** 2)
    n = len(delta)
    out = np.zeros_like(coef)
    for i in range(n):
        j = np.arange(i - h, i + h + 1)
        ok = (j >= 0) & (j < n)
        ww = g[ok] * wrow[j[ok]]
        if ww.sum() > 1e-9:
            out[i] = (ww[:, None] * coef[j[ok]]).sum(0) / ww.sum()
    return out @ A.T


def _leg_master():
    """(rows, offsets px [row, angle]) of the master's leg skin: the radial offset
    that moves each ring point (leg_section + anatomy, at parametric angle
    2 pi j / LEG_MASTER_N) onto the master, weighted. None without the master."""
    global _LEG_MASTER
    if _LEG_MASTER is not None or not MASTER:
        return _LEG_MASTER
    from .. import shape as master
    r0, r1, r2, r3 = LEG_MASTER_ROWS
    t0, t1 = THIGH_HOLD
    rows = np.arange(t0 - 12.0, r3 + 12.0 + 1e-6, LEG_MASTER_STEP)
    ang = 2 * math.pi * np.arange(LEG_MASTER_N) / LEG_MASTER_N
    C, D, R, Q = [], [], [], []
    for row in rows:
        cx, cy, hw, hd = leg_section(row)
        f = _leg_shape(row)
        for a in ang:
            dx, dy = math.cos(a), math.sin(a)
            oa, ob = f(dx, dy)
            qx, qy = hw * dx + oa, hd * dy + ob
            L = math.hypot(qx, qy)
            C.append(P(cx, cy, row))
            D.append((qx / L, -qy / L, 0.0))
            R.append(px(L))
            # the ray may not start past the midline (inside the other leg)
            Q.append(px(cx) / max(1e-6, -qx / L) if qx < 0 else 1.0)
    R = np.array(R)
    r_t = _master_radii(C, D, R, reach=np.array(Q) * 0.98)
    delta = ((r_t - R) / px(1) - MASTER_INSET).reshape(len(rows), len(ang))
    delta[rows < r0] = np.nan          # under the petticoat: no samples
    kb0, kb1 = KNEE_MASTER_BAND
    win = []
    for r in rows:
        w = 1 - smoothstep(r2, r3, r)
        w *= 1 - (1 - smoothstep(kb0, kb1, abs(r - KNEE_ROW))) * (1 - KNEE_MASTER_W)
        win.append(w)
    win = np.array(win)
    off = _leg_lowpass(delta, ang)
    # above the full rows the correction of the first full row is held, fading out
    # up the thigh
    i1 = int(np.argmin(np.abs(rows - r1)))
    for i, r in enumerate(rows):
        if r < r1:
            off[i] = off[i1] * smoothstep(t0, t1, r)
    off = off * win[:, None]
    # hidden zone: stay LEG_CLOTH_CLEAR inside the master's skirt / petticoat (the
    # nearest cloth surface out along the ray from the leg's centre)
    _, d_cloth, _, _ = master.ray(('skirt', 'petticoat'), C, D, 0.3, False)
    room = (d_cloth.reshape(len(rows), len(ang)) - R.reshape(len(rows), len(ang))) / px(1) - LEG_CLOTH_CLEAR
    # (only the master's outward push is limited: where our procedural thigh is
    # already tighter than that, it stays as it is)
    with np.errstate(invalid='ignore'):
        cap = np.where(np.isfinite(room), np.maximum(room, 0.0), np.inf)
    LEG_MASTER_INFO['clamped'] = int((off > cap).sum())
    LEG_MASTER_INFO['valid'] = float(np.isfinite(delta).mean())
    off = np.minimum(off, cap)
    _LEG_MASTER = (rows, off)
    return _LEG_MASTER


def ankle_joint():
    """Left ankle pivot (world): on the leg axis at ANKLE_ROW, ANKLE_BACK px behind it."""
    cx, cy, _, _ = leg_section(ANKLE_ROW)
    return P(cx, cy + ANKLE_BACK, ANKLE_ROW)


def leg_section(row):
    """Left leg ring at `row` (panel px): (centre x, centre y, half width, half depth),
    before the anatomy offsets (leg_offset). shoes.py clears its shell against it."""
    r0, r1, r2, r3, sk = LEG_SIGMA_KNEE
    knee = smoothstep(r0, r1, row) * (1 - smoothstep(r2, r3, row))
    xo, xi = _smoothed(LEG_FRONT, row, LEG_SIGMA + (sk - LEG_SIGMA) * knee)
    yf, yb = _smoothed(LEG_SIDE, row, LEG_SIGMA_SIDE)
    return (xo + xi) / 2, (yf + yb) / 2, (xo - xi) / 2 - MARGIN, (yb - yf) / 2 - MARGIN


def leg_offset(row):
    """f(dx, dy) -> (d_side, d_front) px: how the anatomy (kneecap, calf, malleoli,
    tendon, heel) and the shape master move the point of the leg ring at `row` at unit
    direction (dx: + outer, dy: + front). shoes.py clears its shell against it."""
    anat = _leg_shape(row)
    tab = _leg_master()
    if tab is None or not tab[0][0] <= row <= tab[0][-1]:
        return anat
    rows, off = tab
    j = min(len(rows) - 2, int((row - rows[0]) / LEG_MASTER_STEP))
    t = (row - rows[j]) / (rows[j + 1] - rows[j])
    o = off[j] * (1 - t) + off[j + 1] * t
    if not np.any(np.abs(o) > 1e-6):
        return anat
    n = len(o)
    _, _, hw, hd = leg_section(row)

    def f(dx, dy):
        a, b = anat(dx, dy)
        u = (math.atan2(dy, dx) / (2 * math.pi)) % 1.0 * n
        k = int(u) % n
        s = o[k] + (o[(k + 1) % n] - o[k]) * (u - int(u))
        qx, qy = hw * dx + a, hd * dy + b
        L = math.hypot(qx, qy)
        if L < 1e-9:
            return a, b
        return a + s * qx / L, b + s * qy / L
    return f


def build_leg(bm):
    centers, hints, radii, shapes = [], [], [], []
    for row in LEG_ROWS:
        cx, cy, hw, hd = leg_section(row)
        centers.append(P(cx, cy, row))
        hints.append(Vector((1, 0, 0)))
        # side+ = outer, side- = inner, up+ = front, up- = back
        radii.append((px(hw), px(hw), px(hd), px(hd)))
        shapes.append(leg_offset(row))

    def shape(i, dx, dy):
        a, b = shapes[i](dx, dy)
        return px(a), px(b), 0.0
    sweep(bm, centers, hints, radii, n=LEG_N, cap0='pole', cap1='pole',
          cap0_len=px(6), cap1_len=px(5), tangent=(0, 0, -1), shape=shape)


# Foot as vertical slices across the foot (heel -> toe), fitted inside the
# shoes part's shell (levi/parts/shoes.py STATIONS: centre x, half width,
# insole and toe-box rows, converted to plain panel rows) with ~2 px clearance,
# and to the instep skin visible in the shoe opening on ref/side.png. The heel
# (first slices) is ~1 px per side narrower than round 4, so the shoe's heel
# counter can slim down (shoes keeps its shell FOOT_CLEAR outside these).
# (y, centre x, half width, bottom row, top row)  panel px
FOOT = [
    (14, 30.5, 4.8, 896, 872),
    (8, 30.5, 8.3, 898, 862),
    (0, 30.5, 10.2, 899, 851),
    (-8, 30.0, 11.1, 909, 848),
    (-15, 29.5, 11.8, 926, 852),
    (-22, 28.5, 12.5, 941, 860),
    (-30, 27.0, 14.0, 944, 866),
    (-40, 26.5, 14.5, 944, 888),
    (-50, 25.5, 14.0, 944, 907),
    (-58, 24.5, 13.0, 944.5, 920),
    (-66, 23.0, 11.0, 945, 928.5),
    (-74, 21.0, 8.5, 945, 933),
    (-80, 19.5, 6.0, 945, 936),
    (-85, 18.0, 3.8, 945, 939.5),
]
FOOT_N = 16    # vertices per foot slice: a rounder instep in the shoe opening


def build_foot(bm):
    centers, radii = [], []
    for y, cx, hw, bot, top in FOOT:
        centers.append(P(cx, y, (bot + top) / 2))
        hh = px((bot - top) / 2)
        radii.append((px(hw), px(hw), hh, hh))
    hints = [Vector((1, 0, 0))] * len(FOOT)
    # slices normal to -Y: side = +X, up = +Z
    sweep(bm, centers, hints, radii, n=FOOT_N, p=2.3, cap0='pole', cap1='pole',
          cap0_len=px(3), cap1_len=px(3), tangent=(0, -1, 0))


# ---------------------------------------------------------------- build
# Point attribute for the rig (obj['levi_socket_param'] names it): the signed distance
# (m) from the shoulder socket border, + on the arm (transition rings, arm, hand,
# fingers), - on the torso of the same side, 0 on the border. The rig's staged shoulder
# helpers (rig.SHOULDER_STAGES) hand the arm's turn over across it, the same at the cap
# and in the armpit, so no border between helper and no helper crosses the socket.
SOCKET_PARAM_ATTR = 'levi_socket_s'
SOCKET_PARAM_FAR = 0.3   # m: the parameter is clamped to +-this (far beyond any knot)


def _socket_param(bm, arms):
    # plain data first: a new layer invalidates the BMVert references held in `arms`
    bm.verts.index_update()
    sides = []
    for loop, arm_verts, side in arms:
        tree = KDTree(len(loop))
        for i, v in enumerate(loop):
            tree.insert(v.co, i)
        tree.balance()
        sides.append((tree, {v.index for v in arm_verts}, side))
    layer = bm.verts.layers.float.new(SOCKET_PARAM_ATTR)
    for v in bm.verts:
        v[layer] = -SOCKET_PARAM_FAR      # the midline
        for tree, arm_idx, side in sides:
            if v.co.x * side > 0.0:
                d = min(tree.find(v.co)[2], SOCKET_PARAM_FAR)
                v[layer] = d if v.index in arm_idx else -d


def _mirror_x(bm_src):
    """Append a mirrored (x -> -x) copy of all geometry in bm_src."""
    geom = bm_src.verts[:] + bm_src.edges[:] + bm_src.faces[:]
    dup = bmesh.ops.duplicate(bm_src, geom=geom)
    verts = [e for e in dup['geom'] if isinstance(e, bmesh.types.BMVert)]
    bmesh.ops.scale(bm_src, vec=(-1, 1, 1), verts=verts)


def build(col):
    bm = bmesh.new()
    build_leg(bm)
    build_foot(bm)
    _mirror_x(bm)
    rings = build_torso(bm)
    sockets = [(cut_socket(bm, rings, s), s) for s in (1, -1)]
    arms = []
    for (loop, tans), s in sockets:
        before = set(bm.verts)
        build_arm(bm, loop, tans, s)
        arms.append((loop, set(bm.verts) - before, s))
    _socket_param(bm, arms)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    obj = common.new_object(col, 'body', bm, [common.toon_material('skin')])
    obj['levi_socket_param'] = SOCKET_PARAM_ATTR
    joints = {'knee': tuple(knee_joint()), 'ankle': tuple(ankle_joint())}
    if SHOULDER_JOINT is not None:
        joints['shoulder_joint'] = tuple(P(*SHOULDER_JOINT))
    obj['levi_joints'] = joints
    if MASTER:
        print(f"BODY shape master: hand scale (palm width, palm thickness, finger thickness) "
              f"{tuple(round(v, 3) for v in _hand_master())}; legs {LEG_MASTER_INFO}")
    common.shade_smooth(obj, 75.0)
    common.add_outline(obj)
    return obj
