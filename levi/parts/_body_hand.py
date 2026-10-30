"""风堇's hands on Levi's arms (round 11): the body's palms and fingers.

The hand is the asset assets/hyacine/hands.npz (tools/prep_hyacine_hands.py: her left skin
hand with the nails welded on, recombined into quads, her weights, finger ids and bones). For
each arm (built for the left side; the right one is its mirror image):

1. Placed rigidly: her wrist frame (手首; the direction to the middle finger's root 中指１;
   the palm normal from the knuckle line 人指１ - 小指１) onto Levi's (body.WRIST,
   body.hand_frame(): palm toward the thigh, thumb forward and down), scaled uniformly to
   Levi's hand length (HAND_LEN). Her fingers keep their own relaxed pose and nails.
2. Her forearm stub (open ~2.4 cm before 手首) is bent onto Levi's forearm (Levi's wrist is
   extended ~12 deg against hers ~4) by linear-blend skinning with her own forearm weights
   (手捩, 手捩1-3, ひじ), and tapered round the forearm axis toward the arm's last ring
   (TAPER), so the bridge below runs straight instead of flaring into her thicker wrist.
3. One Catmull-Clark level: her cage has ~4 mm edges on the fingers but ~10 mm triangles
   with poles in the palm, which the cel terminator draws as facets. Data (her weights) are
   interpolated linearly.
4. The procedural arm stops CUT_MARGIN before rig.WRIST_BAND starts (the hand / forearm blend
   then runs over the bridge and her stub). A bridge of rings joins the arm's last ring to
   her loop. Angles round the limb correspond through a rotation-minimising frame carried
   along the centre line (no twist); each of her loop's vertices is reached by a cubic
   Hermite path from the arm ring's surface at its angle, leaving along the arm's own edges
   and arriving along her stub's, so the surface is tangent-continuous at both seams (no
   step, no pinch, no crease); one zipper row from the arm's 24 vertices to her 22
   (equal-angle walk, triangle pairs merged into quads).

The body stays one closed manifold. Its outline thins in the hand's palm-side creases
(Hands.outline: the vertex group OUTLINE_VG for add_outline). Rig data (rig.fit_fingers,
rig._hand_hint):
  * obj['levi_fingers']: {finger: [knuckle, joint, joint, tip]} (left side, world) from her
    bones after the placement;
  * an int point attribute named by obj['levi_finger_attr'] (FINGER_ATTR): 0 palm, wrist and
    arm, 1 thumb .. 5 little (the finger chain holding at least half of the vertex's weight);
  * her weights as hints: float point attributes HINT_PREFIX<k>, named by
    obj['levi_hand_weights'] = {attribute: her bone name without side}; on the hand and stub
    they sum to 1, across the bridge they fall to 0, elsewhere they are 0;
  * levi_joints 'wrist' (body.WRIST, where her 手首 lands) and 'fingertip' (the middle
    finger's farthest point along the hand), so the rig's wrist is her wrist pivot.
"""
import math
import os

import numpy as np
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ASSET = os.path.join(ROOT, 'assets', 'hyacine', 'hands.npz')
# LEVI_HYACINE_HANDS=0: the round-10 procedural hands (A/B renders)
ENABLED = os.environ.get('LEVI_HYACINE_HANDS', '1') != '0'

# m: Levi's hand length, wrist (body.WRIST) to the farthest point of the middle finger along
# hand_frame()'s d, measured on the round-10 procedural hand (hers is 136 mm: x0.93)
HAND_LEN = 0.1263
CUT_MARGIN = 0.012     # m: the arm's last ring lies this far before rig.WRIST_BAND's start
BRIDGE_STEP = 0.0075   # m between bridge rings (the arm's rings are 1-2 cm apart there)
# Stub taper: the share of the way from her section to the arm's last ring (per axis, across
# the palm w and through it n) at her open end, fading to none by TAPER_END along the
# forearm past the wrist pivot (m)
TAPER = (1.0, 1.0)
TAPER_END = 0.012
# Outline (round 11 review): her cage's sharpest concave creases (the thumb web, the palm's
# creases, the finger webs: 35-60 deg between faces) stay narrow grooves after one Catmull-Clark
# level, and the inverted hull drew the thumb's line running into the web as a jagged arrowhead
# with a shade sliver. On the palm side (past OUTLINE_SIDE along hand_frame's n) the hull thins
# there, down to OUTLINE_MIN of its width (the vertex group OUTLINE_VG, add_outline's per-vertex
# width), by the cage's concave dihedral (OUTLINE_CREASE, deg) interpolated over the subdivided
# hand: the line now tapers into the web. Not on the back: along the groove between the middle
# and ring metacarpals a thinner hull lengthened its 1 px inner contour (the hull tilts with the
# width), and neither a Taubin relax of the cage's creases nor filling that groove (2 umbrella
# steps of 0.5) changed it; the speck stays, visible only in close-ups of the back of the hand.
OUTLINE_SIDE = 0.005    # m
OUTLINE_VG = 'levi_outline'
OUTLINE_MIN = 0.3
OUTLINE_CREASE = (30.0, 55.0)
FINGER_ATTR = 'levi_finger'
HINT_PREFIX = 'levi_hw_'
# rig finger name -> her bones (knuckle, joint, joint, tip)
CHAINS = (('親指', ('親指０', '親指１', '親指２', '親指先')),
          ('人指', ('人指１', '人指２', '人指３', '人指先')),
          ('中指', ('中指１', '中指２', '中指３', '中指先')),
          ('薬指', ('薬指１', '薬指２', '薬指３', '薬指先')),
          ('小指', ('小指１', '小指２', '小指３', '小指先')))
FOREARM = ('ひじ', '手捩1', '手捩2', '手捩3', '手捩')

_ASSET = None


def asset():
    """The npz as plain arrays (loaded once; read-only)."""
    global _ASSET
    if _ASSET is None:
        z = np.load(ASSET)
        _ASSET = {
            'pos': z['pos'].astype(np.float64),
            'faces': [[int(i) for i in f if i >= 0] for f in z['faces']],
            'loop': [int(i) for i in z['loop']],
            'weights': z['weights'].astype(np.float64),
            'bones': [str(b) for b in z['bones']],
            'finger': z['finger'].astype(np.int64),
            'head': {str(n): np.array(h, np.float64) for n, h in zip(z['bone_names'], z['bone_head'])},
        }
    return _ASSET


def smoothstep(e0, e1, x):
    t = np.clip((np.asarray(x, np.float64) - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def _unit(v):
    return v / np.linalg.norm(v)


def _turn(a, b):
    """Rotation matrix turning unit vector a onto unit vector b about a x b."""
    v = np.cross(a, b)
    s, c = np.linalg.norm(v), float(a @ b)
    if s < 1e-12:
        return np.eye(3)
    k = v / s
    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    ang = math.atan2(s, c)
    return np.eye(3) + math.sin(ang) * K + (1 - math.cos(ang)) * K @ K


def finger_ids(W, bones):
    """0 palm, 1 thumb .. 5 little: the finger chain with at least half of each row's weight."""
    cs = np.stack([sum((W[:, bones.index(b)] for b in ch[:3] if b in bones), np.zeros(len(W)))
                   for _, ch in CHAINS], 1)
    return np.where(cs.max(1) >= 0.5, cs.argmax(1) + 1, 0)


def her_frame(head):
    """(her wrist, 3x3 columns d, w, n): along the hand, toward the thumb, palm side."""
    W = head['手首']
    d = _unit(head['中指１'] - W)
    w = head['人指１'] - head['小指１']
    w = _unit(w - d * (w @ d))
    return W, np.stack([d, w, np.cross(d, w)], 1)


def placed(W, frame, E):
    """Her hand on Levi's left arm (steps 1-2 without the taper): positions, placed bone heads,
    the forearm axis f and the scale."""
    A = asset()
    Wh, Mh = her_frame(A['head'])
    R = np.stack(frame, 1) @ Mh.T
    P = A['pos']
    her_len = float(((P[A['finger'] == 3] - Wh) @ Mh[:, 0]).max())
    s = HAND_LEN / her_len

    def tr(p):
        return W + s * (p - Wh) @ R.T
    P1 = tr(P)
    head = {k: tr(v) for k, v in A['head'].items()}
    f = _unit(W - E)
    Q = _turn(_unit(head['手首'] - head['ひじ']), f)
    bones = A['bones']
    phi = sum((A['weights'][:, bones.index(b)] for b in FOREARM if b in bones), np.zeros(len(P)))
    rel = P1 - W
    P2 = W + rel * (1 - phi)[:, None] + (rel @ Q.T) * phi[:, None]
    return P2, head, f, s


def taper(P, W, f, w, loop, ring):
    """Scale the stub's section round the forearm axis toward the arm's last ring `ring` (TAPER of
    the way at her open end, none past TAPER_END)."""
    a = _unit(w - f * (w @ f))
    b = np.cross(f, a)
    rel = P - W
    u = rel @ f
    out = rel - np.outer(u, f)
    x, y = out @ a, out @ b
    # her loop as the subdivision will leave it (its boundary rule draws the loop in a little)
    lq = P[loop]
    lq = (np.roll(lq, 1, 0) + 6 * lq + np.roll(lq, -1, 0)) / 8
    lp = np.concatenate([lq, (P[loop] + np.roll(P[loop], -1, 0)) / 2]) - W
    rr = ring - W
    k = []
    for ax, ta in ((a, TAPER[0]), (b, TAPER[1])):
        ext_loop = np.ptp(lp @ ax)
        ext_ring = np.ptp(rr @ ax)
        k.append(1 + ta * (ext_ring / ext_loop - 1))
    u0 = float((lp @ f).mean())
    g = 1 - smoothstep(u0, TAPER_END, u)
    kx, ky = 1 + (k[0] - 1) * g, 1 + (k[1] - 1) * g
    return W + np.outer(u, f) + np.outer(x * kx, a) + np.outer(y * ky, b), k


def cage_crease(P, faces, loop):
    """(n,) the sharpest concave dihedral (deg) among each cage vertex's edges (0 where convex)."""
    c = P[loop].mean(0)
    vol = sum(float(np.dot(P[f[0]], np.cross(P[f[i]], P[f[i + 1]]))) for f in faces for i in range(1, len(f) - 1))
    vol += sum(float(np.dot(c, np.cross(P[loop[(i + 1) % len(loop)]], P[loop[i]]))) for i in range(len(loop)))
    sgn = 1.0 if vol > 0 else -1.0      # outward normals
    FN, FC = np.zeros((len(faces), 3)), np.zeros((len(faces), 3))
    for fi, f in enumerate(faces):
        q = P[f]
        fn = sum(np.cross(q[i], q[(i + 1) % len(f)]) for i in range(len(f)))
        FN[fi], FC[fi] = sgn * fn / np.linalg.norm(fn), q.mean(0)
    ef = {}
    for fi, f in enumerate(faces):
        for i in range(len(f)):
            a, b = f[i], f[(i + 1) % len(f)]
            ef.setdefault((min(a, b), max(a, b)), []).append(fi)
    crease = np.zeros(len(P))
    for (a, b), fl in ef.items():
        if len(fl) == 2 and (FC[fl[1]] - FC[fl[0]]) @ FN[fl[0]] > 0:      # concave
            ang = math.degrees(math.acos(float(np.clip(FN[fl[0]] @ FN[fl[1]], -1.0, 1.0))))
            crease[a], crease[b] = max(crease[a], ang), max(crease[b], ang)
    return crease


def catmull_clark(V, faces, data, loop):
    """One Catmull-Clark level of a polygon mesh with one open boundary `loop` (B-spline rule
    along it). `data` (n, k) is interpolated linearly. Returns (V2, quads (m, 4), data2, loop2)."""
    n = len(V)
    ekey, edges, efaces = {}, [], []
    for fi, f in enumerate(faces):
        for i in range(len(f)):
            a, b = f[i], f[(i + 1) % len(f)]
            key = (a, b) if a < b else (b, a)
            if key not in ekey:
                ekey[key] = len(edges)
                edges.append(key)
                efaces.append([])
            efaces[ekey[key]].append(fi)
    E = np.array(edges)
    Fp = np.array([V[f].mean(0) for f in faces])
    Fd = np.array([data[f].mean(0) for f in faces])
    mid = (V[E[:, 0]] + V[E[:, 1]]) / 2
    Ep = mid.copy()
    for ei, fl in enumerate(efaces):
        if len(fl) == 2:
            Ep[ei] = (V[E[ei, 0]] + V[E[ei, 1]] + Fp[fl[0]] + Fp[fl[1]]) / 4
        elif len(fl) != 1:
            raise RuntimeError('_body_hand: non-manifold hand cage')
    Ed = (data[E[:, 0]] + data[E[:, 1]]) / 2
    Qs, nf = np.zeros((n, 3)), np.zeros(n)
    for fi, f in enumerate(faces):
        Qs[f] += Fp[fi]
        nf[f] += 1
    Rs, ne = np.zeros((n, 3)), np.zeros(n)
    for c in (0, 1):
        np.add.at(Rs, E[:, c], mid)
        np.add.at(ne, E[:, c], 1)
    Vp = (Qs / nf[:, None] + 2 * Rs / ne[:, None] + (ne - 3)[:, None] * V) / ne[:, None]
    L = len(loop)
    for i, v in enumerate(loop):
        Vp[v] = (V[loop[i - 1]] + 6 * V[v] + V[loop[(i + 1) % L]]) / 8
    quads = []
    for fi, f in enumerate(faces):
        k = len(f)
        for i in range(k):
            a, b, c = f[i - 1], f[i], f[(i + 1) % k]
            e1 = ekey[(b, c) if b < c else (c, b)]
            e0 = ekey[(a, b) if a < b else (b, a)]
            quads.append((b, n + e1, n + len(E) + fi, n + e0))
    loop2 = []
    for i, v in enumerate(loop):
        w = loop[(i + 1) % L]
        loop2 += [v, n + ekey[(v, w) if v < w else (w, v)]]
    return (np.vstack([Vp, Ep, Fp]), np.array(quads), np.vstack([data, Ed, Fd]), loop2)


def _herm(c0, m0, c1, m1, s):
    h00, h10 = 2 * s ** 3 - 3 * s ** 2 + 1, s ** 3 - 2 * s ** 2 + s
    h01, h11 = -2 * s ** 3 + 3 * s ** 2, s ** 3 - s ** 2
    return h00 * c0 + h10 * m0 + h01 * c1 + h11 * m1


def _dherm(c0, m0, c1, m1, s):
    return ((6 * s ** 2 - 6 * s) * c0 + (3 * s ** 2 - 4 * s + 1) * m0
            + (-6 * s ** 2 + 6 * s) * c1 + (3 * s ** 2 - 2 * s) * m1)


def _periodic(theta, ang, val):
    """Linear interpolation of val at angles `theta`, over samples at angles `ang` (any order)."""
    o = np.argsort(ang)
    a, v = ang[o], val[o]
    a = np.concatenate([a[-1:] - 2 * math.pi, a, a[:1] + 2 * math.pi])
    v = np.concatenate([v[-1:], v, v[:1]], axis=0)
    t = np.mod(theta - a[1], 2 * math.pi) + a[1]
    return np.array([np.interp(t, a, v[:, j]) for j in range(v.shape[1])]).T if v.ndim > 1 else np.interp(t, a, v)


def bridge(ring, prev, loop_P, inward):
    """Rings from the arm's last ring `ring` (n_a points; `prev` the ring before it, same order)
    to her loop `loop_P` (n_h points in loop order; `inward` (n_h, 3): the direction of her
    stub's surface from each loop vertex into the hand). Returns (inner rings (r, n_h, 3), their
    blend 0..1, zipper faces, loop order): zipper faces index the ring ('a', i) / the first inner
    ring ('b', j); the inner rings and the loop then join index to index (loop in that order)."""
    lead = ring - prev
    t_ring = _unit(lead.mean(0))
    cA, cH = ring.mean(0), loop_P.mean(0)
    _, _, vt = np.linalg.svd(loop_P - cH)
    tH = vt[2] if vt[2] @ inward.mean(0) > 0 else -vt[2]
    L = float(np.linalg.norm(cH - cA))
    nr = max(1, int(round(L / BRIDGE_STEP)))
    m0, m1 = t_ring * L, tH * L
    # rotation-minimising frame along the centre line, from the ring's first vertex
    e1 = ring[0] - cA
    e1 = _unit(e1 - t_ring * (e1 @ t_ring))
    T = t_ring.copy()
    sub = 16
    for i in range(1, nr * sub + 1):
        Tn = _unit(_dherm(cA, m0, cH, m1, i / (nr * sub)))
        e1 = _unit(_turn(T, Tn) @ e1)
        e1 = _unit(e1 - Tn * (e1 @ Tn))
        T = Tn
    e1A = _unit(ring[0] - cA - t_ring * ((ring[0] - cA) @ t_ring))

    def polar(P, c, T, e1):
        rel = P - c
        h = rel @ T
        q = rel - np.outer(h, T)
        e2 = np.cross(T, e1)
        return np.arctan2(q @ e2, q @ e1), np.linalg.norm(q, axis=1), h
    thA, rA, hA = polar(ring, cA, t_ring, e1A)
    thH = polar(loop_P, cH, T, e1)[0]
    order = np.arange(len(loop_P))
    if np.sum(np.angle(np.exp(1j * np.diff(np.append(thH, thH[0]))))) < 0:
        order = order[::-1]
        thH = thH[order]
    H, tin = loop_P[order], inward[order]
    # each loop vertex's path: from the arm ring's surface at its angle, along the arm's edges
    e2A = np.cross(t_ring, e1A)
    r0, h0 = _periodic(thH, thA, rA), _periodic(thH, thA, hA)
    P0 = cA + np.outer(r0 * np.cos(thH), e1A) + np.outer(r0 * np.sin(thH), e2A) + np.outer(h0, t_ring)
    t0 = _periodic(thH, thA, lead)
    t0 /= np.linalg.norm(t0, axis=1, keepdims=True)
    Lj = np.linalg.norm(H - P0, axis=1)[:, None]
    inner, blend = [], []
    for k in range(1, nr):
        s = k / nr
        inner.append(_herm(P0, Lj * t0, H, Lj * tin, s))
        blend.append(float(smoothstep(0.0, 1.0, s)))
    # zipper: the arm ring against the first inner ring (or the loop) by angle
    na, nb = len(ring), len(loop_P)
    au = np.unwrap(np.append(thA, thA[0]))
    if au[-1] < au[0]:
        raise RuntimeError('_body_hand: the arm ring runs clockwise')
    au[-1] = au[0] + 2 * math.pi
    j0 = int(np.argmin(np.abs(np.angle(np.exp(1j * (thH - au[0]))))))
    bh = np.roll(thH, -j0)
    bu = np.unwrap(np.append(bh, bh[0]))
    bu += 2 * math.pi * round((au[0] - bu[0]) / (2 * math.pi))
    bu[-1] = bu[0] + 2 * math.pi
    moves, i, j = [], 0, 0
    while i < na or j < nb:
        if j >= nb or (i < na and au[i + 1] <= bu[j + 1]):
            moves.append(('a', i))
            i += 1
        else:
            moves.append(('b', j))
            j += 1
    faces, k = [], 0
    A = lambda q: ('a', q % na)              # noqa: E731
    Bv = lambda q: ('b', (q + j0) % nb)      # noqa: E731
    while k < len(moves):
        (m, q), nxt = moves[k], moves[k + 1] if k + 1 < len(moves) else None
        if nxt and nxt[0] != m:
            ia = q if m == 'a' else nxt[1]
            jb = q if m == 'b' else nxt[1]
            faces.append((A(ia), A(ia + 1), Bv(jb + 1), Bv(jb)))
            k += 2
            continue
        if m == 'a':
            jb = sum(1 for mm in moves[:k] if mm[0] == 'b')
            faces.append((A(q), A(q + 1), Bv(jb)))
        else:
            ia = sum(1 for mm in moves[:k] if mm[0] == 'a')
            faces.append((A(ia), Bv(q + 1), Bv(q)))
        k += 1
    return np.array(inner).reshape(-1, nb, 3), blend, faces, order


class Hands:
    """Both hands of one body build: body.build_arm calls build() per arm, body.build then
    writes the point attributes (write_layers) and the rig data (store)."""

    def __init__(self):
        self.records = []     # (vertex index, finger id, hint row)
        self.line = []        # (vertex index, outline width factor < 1)
        self.left = None      # rig data of the left hand
        self.info = {}

    def build(self, bm, ring_verts, ring_co, prev_co, W, frame, E, mirror):
        """Bridge + hand onto the arm's last ring (BMVerts `ring_verts`, left-side positions
        `ring_co`, the ring before it `prev_co`); W, frame (d, w, n), E: body.WRIST,
        hand_frame(), ELBOW."""
        A = asset()
        W, E = np.array(W, np.float64), np.array(E, np.float64)
        frame = [np.array(v, np.float64) for v in frame]
        ring = np.array([tuple(c) for c in ring_co], np.float64)
        prev = np.array([tuple(c) for c in prev_co], np.float64)
        P, head, f, scale = placed(W, frame, E)
        P, k = taper(P, W, f, frame[1], A['loop'], ring)
        bones = A['bones']
        crease = cage_crease(P, A['faces'], A['loop'])
        palm = smoothstep(OUTLINE_SIDE - 0.003, OUTLINE_SIDE + 0.003, (P - W) @ frame[2])
        thin = smoothstep(OUTLINE_CREASE[0], OUTLINE_CREASE[1], crease) * palm
        V2, quads, D2, loop2 = catmull_clark(P, A['faces'], np.hstack([A['weights'], thin[:, None]]), A['loop'])
        line = 1.0 - (1.0 - OUTLINE_MIN) * D2[:, -1]
        D2 = D2[:, :-1]
        fid = finger_ids(D2, bones)
        # her stub's surface direction at each loop vertex: the edge to the interior neighbour
        # running most along the stub, into the hand
        on_loop = set(loop2)
        nbr = {v: set() for v in loop2}
        for q in quads:
            for i in range(4):
                a, b = int(q[i]), int(q[(i + 1) % 4])
                if a in nbr and b not in on_loop:
                    nbr[a].add(b)
                if b in nbr and a not in on_loop:
                    nbr[b].add(a)
        axis = _unit(V2.mean(0) - V2[loop2].mean(0))
        inward = np.array([_unit(max(((V2[u] - V2[v]) for u in sorted(nbr[v])), key=lambda e: _unit(e) @ axis))
                           for v in loop2])
        inner, blend, zfaces, order = bridge(ring, prev, V2[loop2], inward)
        sx = -1.0 if mirror else 1.0

        def new(p):
            return bm.verts.new((sx * p[0], p[1], p[2]))
        hv = [new(p) for p in V2]
        for q in quads:
            bm.faces.new([hv[i] for i in q])
        lv = [hv[loop2[i]] for i in order]
        lw = D2[[loop2[i] for i in order]]
        iv = [[new(p) for p in r] for r in inner]
        first = iv[0] if iv else lv
        for fc in zfaces:
            bm.faces.new([ring_verts[i] if t == 'a' else first[i] for t, i in fc])
        rows = iv + [lv]
        for a, b in zip(rows, rows[1:]):
            n = len(a)
            for j in range(n):
                bm.faces.new((a[j], a[(j + 1) % n], b[(j + 1) % n], b[j]))
        # vertex indices, not BMVerts: adding a layer later invalidates BMVert references (no
        # vertex is removed after the arms, so the indices hold)
        bm.verts.index_update()
        for v, d, fi, ln in zip(hv, D2, fid, line):
            self.records.append((v.index, int(fi), d))
            if ln < 1.0:
                self.line.append((v.index, float(ln)))
        for r, b in zip(iv, blend):
            for v, d in zip(r, lw):
                self.records.append((v.index, 0, d * b))
        if not mirror:
            mid = fid == 3
            tip = V2[mid][np.argmax((V2[mid] - W) @ frame[0])]
            self.left = {'fingers': {jp: [tuple(float(c) for c in head[b]) for b in ch] for jp, ch in CHAINS},
                         'wrist': tuple(float(c) for c in W), 'fingertip': tuple(float(c) for c in tip)}
            self.info = {'scale': round(scale, 4), 'taper': tuple(round(float(x), 3) for x in k),
                         'thin_line': int((line < 0.9).sum()),
                         'verts': len(V2) + sum(len(r) for r in inner), 'bridge_rings': len(inner),
                         'zipper': (sum(1 for fc in zfaces if len(fc) == 4), sum(1 for fc in zfaces if len(fc) == 3))}

    def write_layers(self, bm):
        """The finger id and hint attributes (call after every vertex exists)."""
        bones = asset()['bones']
        rec = self.records
        lf = bm.verts.layers.int.new(FINGER_ATTR)
        lh = [bm.verts.layers.float.new(f'{HINT_PREFIX}{k:02d}') for k in range(len(bones))]
        bm.verts.ensure_lookup_table()
        for i, fi, d in rec:
            v = bm.verts[i]
            v[lf] = fi
            for k, x in enumerate(d):
                if x > 0.0:
                    v[lh[k]] = float(x)

    def outline(self, obj):
        """add_outline's keyword arguments for the body: the vertex group OUTLINE_VG (1 everywhere,
        thinner in the hands' creases)."""
        vg = obj.vertex_groups.new(name=OUTLINE_VG)
        vg.add(list(range(len(obj.data.vertices))), 1.0, 'REPLACE')
        for i, ln in self.line:
            vg.add([i], ln, 'REPLACE')
        return {'vertex_group': OUTLINE_VG, 'min_factor': 0.0}

    def store(self, obj, joints):
        """Rig data on the body object; joints: the levi_joints dict, updated in place."""
        bones = asset()['bones']
        obj['levi_finger_attr'] = FINGER_ATTR
        obj['levi_hand_weights'] = {f'{HINT_PREFIX}{k:02d}': b for k, b in enumerate(bones)}
        obj['levi_fingers'] = {jp: [list(p) for p in pts] for jp, pts in self.left['fingers'].items()}
        joints['wrist'] = self.left['wrist']
        joints['fingertip'] = self.left['fingertip']


def keep_stations(stations, S, E, W, k):
    """How many of body.ARM_STATIONS the arm keeps: those at least -rig.WRIST_BAND[0] + CUT_MARGIN
    before the wrist along the arm (S, E, W: shoulder, elbow, wrist; k: metres per px)."""
    from ..rig import WRIST_BAND
    lu, lf = (Vector(E) - Vector(S)).length / k, (Vector(W) - Vector(E)).length / k
    lim = -(-WRIST_BAND[0] + CUT_MARGIN) / k
    n = 0
    for base, off in stations:
        before = off - {'S': lu + lf, 'E': lf, 'W': 0.0}[base]
        if before > lim:
            break
        n += 1
    return n
