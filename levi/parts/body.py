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

import bmesh
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
# left alone.
BUST_PUSH = [(230, 0.0, 0, 20), (235, 14.0, 10, 26), (240, 10.5, 2, 20), (247, 6.0, 0, 20),
             (256, 4.3, 0, 20), (266, 4.0, 0, 20), (278, 2.0, 0, 20), (290, 1.8, 0, 20),
             (305, 0.0, 0, 20)]
# where the push has faded out toward the side (share of the half width):
# sooner along the rising neckline edge
BUST_FADE = [(235, 0.5), (240, 0.64), (247, 0.82)]
# soft collarbone ridge (+) and the shallow hollow under it (-): forward push
# px across the upper chest as smooth bumps (row, amplitude, vertical sigma),
# so the loops of the shoulder band (196, 203, 210...) sample the measured
# ridge at row 199 and hollow at row 209 without a kink
CLAVICLE = ((199, 1.2, 5.0), (209, -0.8, 4.0))
NECK_TILT = 0.6  # the neck-top rings rise toward the back to hide behind the jaw
NECK_SEAM_ROW = 161  # rings at/above this row (spec chin_z) get the tilt
TORSO_N = 32
# Loft rows: the TORSO table sampled (linearly) at these rows. Every table row
# outside the shoulder band is kept, so the surface between them is unchanged;
# the extra rings give the shoulder band, the waist (forward / side bends) and
# the hips (leg swings) evenly spaced loops. Inside the band (rows 189-230)
# the socket needs seven evenly spaced rows, so table rows 199/209/219 are
# resampled (the chest front moves < 1 px).
TORSO_ROWS = (148, 161, 170, 175, 178, 180, 182, 184, 186.5,
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


def _torso_thetas(table):
    """Per-ring vertex angles. Rings in the shoulder band put vertices
    +-1..+-SOCKET_K (each side) at even fractions of the socket's depth; above
    and below the band they ease back to uniform spacing."""
    n, K = TORSO_N, SOCKET_K
    h = n // 2
    out = []
    r_top, r_bot = SOCKET_ROWS[0], SOCKET_ROWS[-1]
    for row, hw, yf, yb, p, ysd in table:
        uni = [2 * math.pi * k / n for k in range(n)]
        if row < r_top:
            w = smoothstep(r_top - 9, r_top, row)
        else:
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
        out.append([u + (s - u) * w for u, s in zip(uni, sock)])
    return out


def _bust(row):
    """(amp, x0, x1) of BUST_PUSH at `row`; no push outside the table."""
    if row <= BUST_PUSH[0][0] or row >= BUST_PUSH[-1][0]:
        return 0.0, 0.0, 20.0
    return _interp([(r, (a, x0, x1)) for r, a, x0, x1 in BUST_PUSH], row)


def _clavicle(row):
    return sum(a * math.exp(-0.5 * ((row - c) / s) ** 2) for c, a, s in CLAVICLE)


def build_torso(bm):
    """Neck + torso loft (closed: no shoulder sockets cut). Returns the vertex
    rings, one per TORSO_ROWS entry (torso_table())."""
    table = torso_table()
    centers, hints, radii, ps = [], [], [], []
    for row, hw, yf, yb, p, ys in table:
        centers.append(P(0, ys, row))
        hints.append(Vector((1, 0, 0)))
        radii.append((px(hw), px(hw), px(ys - yf), px(yb - ys)))
        ps.append(p)
    # Rings are horizontal slices (the table rows); t=-Z, side=+X -> up=-Y.
    # per ring: (clavicle push, (bust amp, x0, x1), bust fade, armpit hollow)
    per_ring = [(_clavicle(r[0]) if r[0] < 230 else 0.0, _bust(r[0]),
                 _interp(BUST_FADE, r[0]), _interp(ARMPIT_HOLLOW, r[0])) for r in table]

    def tilt(i, co):
        row, hw, yf, _, _, ys = table[i]
        cl, (amp, x0, x1), s0, hol = per_ring[i]
        co = co.copy()
        if row <= NECK_SEAM_ROW:
            co.z += max(0.0, co.y - px(yf)) * NECK_TILT
        front = co.y < px(ys)
        ax = abs(co.x) / px(1)
        if abs(cl) > 1e-3 and front:
            # soft collarbone ridge and the shallow hollow under it
            co.y -= px(cl * smoothstep(6, 14, ax) * (1 - smoothstep(38, 52, ax)))
        if amp and front:
            # fade out toward the side; sooner along the rising neckline edge
            s1 = 0.9 * hw + 0.08 * hw * smoothstep(0.64, 0.82, s0)
            co.y -= px(amp * smoothstep(x0, x1, ax) * (1 - smoothstep(s0 * hw, s1, ax)))
        if hol:
            # armpit hollow: the side wall between the front and back folds
            g = math.exp(-((co.y / px(1) - ARM_Y) / ARMPIT_HOLLOW_W) ** 2)
            f = smoothstep(0.75 * hw, 0.97 * hw, ax)
            co.x -= math.copysign(px(hol * g * f), co.x)
        return co

    return sweep(bm, centers, hints, radii, n=TORSO_N, p=ps, cap0='ngon', cap1='pole',
                 cap1_len=px(4), ring_fn=tilt, tangent=(0, 0, -1), thetas=_torso_thetas(table))


def cut_socket(bm, rings, side):
    """Delete the socket patch on one side (+1 left, -1 right) and return
    (border verts in arm-ring order, their tangents into the hole).

    Arm ring order (ARM_N = 24): 0 outer (top edge middle), 6 front,
    12 inner (armpit), 18 back."""
    n, K = TORSO_N, SOCKET_K
    rows = list(TORSO_ROWS)
    ri = [rows.index(r) for r in SOCKET_ROWS]
    i0, i4 = ri[0], ri[-1]

    def K_(k):  # left ring index -> this side's
        return k % n if side > 0 else (n // 2 - k) % n
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
    centers, hints, radii, hand_t = [], [], [], []
    for key in ARM_STATIONS:
        s = arc(key)
        centers.append(S + u * s * k if s <= lu else E + f * (s - lu) * k)
        b = smoothstep(lu - 14, lu + 14, s)       # the frame turns over the elbow
        ha = front_side((u * (1 - b) + f * b).normalized())
        tw = _interp(twist_tab, s)
        hints.append((ha * (1 - tw) + w * tw).normalized())
        radii.append(tuple(px(x) for x in _interp(radii_tab, s)))
        hand_t.append(0 if key == ('W', 0) else None)
    for t in HAND_STATIONS:
        centers.append(W + d * t * k)
        hints.append(w.copy())
        radii.append(tuple(px(x) for x in _interp(HAND_R, t)))
        hand_t.append(t)

    shapes = [None if ht is None else _palm_shape(ht) for ht in hand_t]

    def shape(i, dx, dy):
        return shapes[i](dx, dy) if shapes[i] else (0.0, 0.0, 0.0)
    pexp = [2.0 if ht is None else _interp(HAND_P, ht) for ht in hand_t]
    rings, frames = ring_points(centers, hints, radii, ARM_N, p=pexp, shape=shape)
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


def finger(bm, base, direction, bend_axis, seg_len, r0, curl, mirror, n=FINGER_N, taper=FINGER_TAPER):
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
    sw, sb, sp = FINGER_SECTION
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
    for off, kd, splay, segs, r0, curl, lift in FINGERS:
        base = W + d * kd * k + w * off * k + n * (0.5 + lift) * k
        direction = _rot(d, n, splay)       # splay within the palm plane
        axis = direction.cross(n).normalized()  # rotating about it bends toward +n (palm)
        finger(bm, base, direction, axis, segs, r0, curl, mirror)
    # thumb: from inside the thumb ball at the heel of the palm, angled out toward
    # the thumb side and turned toward the palm, out of the fingers' plane
    (ta, tw, tn), (da, dw, dn), segs, r0, curl = THUMB
    base = W + d * ta * k + w * tw * k + n * tn * k
    tdir = (d * da + w * dw + n * dn).normalized()
    axis = tdir.cross(n).normalized()
    finger(bm, base, tdir, axis, segs, r0, curl, mirror, taper=THUMB_TAPER)


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
    tendon, heel) moves the point of the leg ring at `row` at unit direction (dx: + outer,
    dy: + front). shoes.py clears its shell against it."""
    return _leg_shape(row)


def build_leg(bm):
    centers, hints, radii, shapes = [], [], [], []
    for row in LEG_ROWS:
        cx, cy, hw, hd = leg_section(row)
        centers.append(P(cx, cy, row))
        hints.append(Vector((1, 0, 0)))
        # side+ = outer, side- = inner, up+ = front, up- = back
        radii.append((px(hw), px(hw), px(hd), px(hd)))
        shapes.append(_leg_shape(row))

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
    common.shade_smooth(obj, 75.0)
    common.add_outline(obj)
    return obj
