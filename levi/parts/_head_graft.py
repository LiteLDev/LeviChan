"""风堇's face on Levi's head (round 11): the graft machinery for levi/parts/head.py.

Her data comes only from assets/hyacine/ (tools/prep_hyacine_head.py): her face
mask, mouth, eyes, lash / liner / brow strips with UVs and her vertex morphs,
in our frame but not aligned to Levi.

* ALIGN puts her face on Levi's head: eye and cheek aligned (the shift that
  lines up her iris centres and the cheek under the eye with Levi's).
* Warp: a smooth space warp W on top of ALIGN. In the hair-covered zone
  (forehead above the brows, temples, the sides behind the cheek) her surface
  is pulled radially onto Levi's skull surface (the round-10 head, which every
  hair part is fitted to); over the eyes, nose, mouth and chin it is her shape
  (weight 0, smoothstep transitions over ~1-1.5 cm). Her nose is toned toward
  Levi's sheet (a smaller nose, lifted: NOSE_TONE). W is defined on her face
  vertices and interpolated (Gaussian, nearest face vertices) everywhere else,
  so the eyes, lashes and mouth parts ride it; morph keys are W(p + d).
* The face (her mask + her mouth cavity + the crease strips that fill two
  slits above her eyes) is quadded (her mesh was modelled in quads) and
  subdivided once (Catmull-Clark, every key alike: the subdivision is linear).
* One closed head_face: Levi's skull (the round-10 ring rows, crown to under
  the eyes) loses the faces her mask covers (seen from the head centre, the
  chart in `chart`); the cut is drawn up to her border (close_gap) and a strip
  of triangles zips the two (zip_chains). Below, a loft (loft_neck) runs from
  the head's lower edge (her under-jaw border, the skull's lowest ring behind
  the ears) into a neck tube NECK_TUCK inside the body's neck, so the visible
  neck is the body's and a turned head shows no step. Her jaw morphs move her
  border; the skull and the loft take that motion with a falloff (PROP_R).
* Her ear cards leave a sliver spike in her border behind the jaw angle; it
  goes (fill_notches).
"""
import math
import os
from functools import lru_cache

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ASSET = os.path.join(ROOT, 'assets', 'hyacine')
ATLAS_PNG = os.path.join(ASSET, 'head_atlas.png')
FLUSH_PNG = os.path.join(ASSET, 'head_flush.png')

# her face onto Levi's head: eye and cheek aligned (work/analysis head-contract face_delta)
ALIGN = np.array([0.0023, -0.0509, 0.0511])
MID_X = 0.0023                       # Levi's face midline (head.HEAD_DX)
EYE_C = (0.0400, 1.2965)             # her eye opening's centre after ALIGN: |x| from the midline, z
EYE_R = (0.022, 0.0155)              # ... and its half size plus a margin [m]: the warp leaves it alone
WARP_C = np.array([MID_X, -0.035, 1.300])   # radial pull centre (inside the skull)
FOREHEAD = (0.016, 0.030)            # m above the eye centre: the forehead pull ramps in
SIDE = (0.052, 0.064)                # m from the midline: the side pull ramps in
BACK = (-0.090, -0.072)              # y: her mask's sides behind this are pulled
CHIN_FREE = (1.262, 1.250)           # z: the side pull fades out under the cheek (her jaw stays hers)
NOSE_TONE = (0.20, 0.0, 0.0105)     # share of the nose's relief taken out, lift [m], X sigma [m]
NOSE_ROWS = (0.034, 0.028, 0.006, 0.0)    # m below the eye centre: the nose zone fades in (under the
#                                           subnasal, hers at -30 mm) .. out (at the bridge's root)
JAW_LIFT = (0.0028, (-0.114, -0.088), (1.248, 1.240), (0.046, 0.026))   # the jaw's underside lifted this
#                                     much [m] toward the neck: from her chin's lowest point back to full by the
#                                     second y, under the first z (full under the second), within |x| from the
#                                     midline (full within the second): her underside, chin to neck, rose 11 deg
#                                     in profile and read as a heavy wedge; the design's rises ~15 deg (now 15)
INTERP_K, INTERP_SIGMA = 12, 0.003   # warp interpolation: nearest face vertices, Gaussian sigma [m]
PROP_R = 0.022                       # m: the skull takes her border's morph motion over this distance
# the body's neck (body.TORSO rows 148-178: half-width 13.5 px, front -44 px, back -17 px,
# centred on x = 0) and how far inside it the head's neck end is tucked
BODY_NECK = (13.5 / 643, -44.0 / 643, -17.0 / 643)
NECK_TUCK = 2.6 / 643
CHART_C = np.array([MID_X, -0.040, 1.285])


def smooth(e0, e1, x):
    t = np.clip((np.asarray(x, float) - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


@lru_cache(maxsize=1)
def data():
    d = np.load(os.path.join(ASSET, 'head.npz'))
    return {k: d[k] for k in d.files}


def morph_names():
    return [str(n) for n in data()['morph_names']]


def part(name):
    """(pos aligned (n, 3), tri (m, 3), uv (m, 3, 2)) of an asset part."""
    d = data()
    return d[name + '_pos'].astype(float) + ALIGN, d[name + '_tri'].astype(np.int64), d[name + '_uv'].astype(float)


def offsets(name, morph):
    """Dense (n, 3) offsets of `morph` on part `name` (zeros if it does not move it)."""
    d = data()
    n = len(d[name + '_pos'])
    out = np.zeros((n, 3))
    k = morph_names().index(morph)
    a, b = d[name + '_mptr'][k], d[name + '_mptr'][k + 1]
    out[d[name + '_mvi'][a:b]] = d[name + '_moff'][a:b]
    return out


def swatch_uv(name):
    d = data()
    return tuple(float(v) for v in d['swatch_uv'][[str(n) for n in d['swatch_names']].index(name)])


def lash_kind():
    d = data()
    kinds = [str(k) for k in d['lash_kind']]
    return np.array([kinds[i] for i in d['lash_isl']])


def bone(name):
    d = data()
    return d['bone_head'][[str(n) for n in d['bone_names']].index(name)].astype(float) + ALIGN


# ---------------------------------------------------------------- the face, coarse
def face_coarse():
    """Her face mask + mouth cavity + the crease strips (they fill two slits of
    the mask above the eyes), welded. Returns dict(pos, tri, uv, mat (0 skin,
    1 mouth), pieces {part: (tri mask in the part, local -> global vertex)})."""
    pieces = []
    F = part('face')
    pieces.append(('face', F, np.ones(len(F[1]), bool), 0))
    M = part('mouth')
    pieces.append(('mouth', M, np.ones(len(M[1]), bool), 1))
    L = part('lash')
    pieces.append(('lash', L, lash_kind() == 'crease', 0))
    keys, pos = {}, []
    tri, uv, mat, maps = [], [], [], {}
    for name, (p, t, u), sel, m in pieces:
        used = np.unique(t[sel])
        lut = -np.ones(len(p), np.int64)
        for v in used:
            k = tuple(np.round(p[v] / 1e-7).astype(np.int64))
            if k not in keys:
                keys[k] = len(pos)
                pos.append(p[v])
            lut[v] = keys[k]
        tri.append(lut[t[sel]])
        uv.append(u[sel])
        mat.append(np.full(sel.sum(), m))
        maps[name] = lut
    pos, tri, uv, mat = np.array(pos), np.concatenate(tri), np.concatenate(uv), np.concatenate(mat)
    nt, nu, drop = fill_notches(pos, tri, uv)
    if drop.any():               # a spike: one sliver triangle sticking out; it goes, with its tip
        tri, uv, mat = tri[~drop], uv[~drop], mat[~drop]
        live = np.zeros(len(pos), bool)
        live[tri.reshape(-1)] = True
        lut = -np.ones(len(pos), np.int64)
        lut[live] = np.arange(live.sum())
        pos, tri = pos[live], lut[tri]
        maps = {k: np.where(m >= 0, lut[np.maximum(m, 0)], -1) for k, m in maps.items()}
    if len(nt):
        tri, uv = np.concatenate([tri, nt]), np.concatenate([uv, nu])
        mat = np.concatenate([mat, np.zeros(len(nt), mat.dtype)])
    return {'pos': pos, 'tri': tri, 'uv': uv, 'mat': mat, 'maps': maps, 'notch': len(nt) + int(drop.sum())}


NOTCH_GAP, NOTCH_STEPS, NOTCH_DEPTH = 0.0085, 2, 0.9   # a slot's mouth: border points this close, this
#                                                         many steps apart, the slot this many mouths deep


def fill_notches(pos, tri, uv):
    """Fill the narrow slots her ear cards leave in her outer border (behind the
    jaw angle): triangles zipping each slot's two sides from its mouth to its
    end. Returns (triangles, corner UVs) consistently wound with the mask."""
    loops = boundary_loops([tuple(t) for t in tri])
    top = int(np.argmax(pos[:, 2]))
    B = next(lp for lp in loops if top in lp)
    n = len(B)
    P = pos[B]
    D = np.linalg.norm(P[:, None] - P[None], axis=2)
    I = np.arange(n)
    st = np.abs(I[:, None] - I[None])
    st = np.minimum(st, n - st)
    corner = {}
    edge_dir = {}
    for t, u in zip(tri, uv):
        for k in range(3):
            corner.setdefault(int(t[k]), tuple(u[k]))
            edge_dir[(int(t[k]), int(t[(k + 1) % 3]))] = True
    out_t, out_u, used = [], [], set()
    tri_of = {frozenset(map(int, t)): i for i, t in enumerate(tri)}
    drop = np.zeros(len(tri), bool)
    cand = sorted(((st[a, b], a, b) for a, b in zip(*np.nonzero((D < NOTCH_GAP) & (st >= NOTCH_STEPS)))
                   if a < b), reverse=True)
    for s, a, b in cand:
        # the slot is the shorter way round from a to b
        path = list(range(a, b + 1)) if b - a <= n // 2 else list(range(b, a + n + 1))
        path = [p % n for p in path]
        if any(p in used for p in path):
            continue
        # a slot: deeper than NOTCH_DEPTH times its mouth
        m0, m1 = P[path[0]], P[path[-1]]
        ax = (m1 - m0) / max(np.linalg.norm(m1 - m0), 1e-9)
        q = P[path] - m0
        depth = np.linalg.norm(q - np.outer(q @ ax, ax), axis=1).max()
        if depth < NOTCH_DEPTH * np.linalg.norm(m1 - m0):
            continue
        used |= set(path)
        Q = [B[p] for p in path]
        print(f'HEAD notch filled: {len(Q)} border vertices, mouth {np.linalg.norm(m1 - m0) * 1000:.1f} mm, '
              f'depth {depth * 1000:.1f} mm at {np.round(P[path].mean(0), 3).tolist()}')
        tris = []
        lo, hi = 0, len(Q) - 1
        while hi - lo > 1:
            dl = np.linalg.norm(pos[Q[lo + 1]] - pos[Q[hi]])
            dr = np.linalg.norm(pos[Q[lo]] - pos[Q[hi - 1]])
            if dl <= dr:
                tris.append((Q[lo], Q[lo + 1], Q[hi]))
                lo += 1
            else:
                tris.append((Q[lo], Q[hi - 1], Q[hi]))
                hi -= 1
        exist = [tri_of.get(frozenset(t)) for t in tris]
        if all(e is not None for e in exist):
            for e in exist:
                drop[e] = True
            continue
        # wind against the mask's own edge along the slot
        flip = edge_dir.get((Q[0], Q[1]), False)
        for t in tris:
            t = t[::-1] if flip else t
            out_t.append(t)
            out_u.append([corner[v] for v in t])
    return np.array(out_t, np.int64).reshape(-1, 3), np.array(out_u, float).reshape(-1, 3, 2), drop


def face_offsets(fc, morph):
    """Dense offsets of `morph` on the welded coarse face (mean over the pieces
    that carry a vertex)."""
    n = len(fc['pos'])
    acc, cnt = np.zeros((n, 3)), np.zeros(n)
    for name, lut in fc['maps'].items():
        off = offsets(name, morph)
        ok = lut >= 0
        if not ok.any():
            continue
        np.add.at(acc, lut[ok], off[ok])
        np.add.at(cnt, lut[ok], 1.0)
    return acc / np.maximum(cnt, 1.0)[:, None]


def adjacency(n, faces):
    nb = [set() for _ in range(n)]
    for f in faces:
        for a, b in zip(f, list(f[1:]) + [f[0]]):
            nb[a].add(b)
            nb[b].add(a)
    return [sorted(s) for s in nb]


def boundary_loops(faces):
    """Ordered boundary loops (vertex lists) of a polygon list, longest first."""
    from collections import Counter
    E = Counter()
    nxt = {}
    for f in faces:
        f = list(f)
        for a, b in zip(f, f[1:] + f[:1]):
            E[(min(a, b), max(a, b))] += 1
            nxt.setdefault(a, []).append(b)
    bnd = {}
    for f in faces:
        f = list(f)
        for a, b in zip(f, f[1:] + f[:1]):
            if E[(min(a, b), max(a, b))] == 1:
                bnd.setdefault(a, []).append(b)
    loops, seen = [], set()
    for s in sorted(bnd):
        if s in seen:
            continue
        lp, v = [], s
        while v not in seen:
            seen.add(v)
            lp.append(v)
            v = bnd[v][0]
        loops.append(lp)
    return sorted(loops, key=len, reverse=True)


def laplace(pos, nb, fixed, n=20, lam=0.5):
    """n passes of uniform Laplacian smoothing; `fixed` vertices stay."""
    P = pos.copy()
    cnt = np.array([len(s) for s in nb])
    has = cnt > 0
    flat = np.concatenate([np.asarray(s, np.int64) for s in nb if len(s)])
    starts = np.concatenate([[0], np.cumsum(cnt[has])[:-1]])
    free = ~np.asarray(fixed, bool) & has
    for _ in range(n):
        Q = P.copy()
        Q[has] = np.add.reduceat(P[flat], starts, axis=0) / cnt[has, None]
        P[free] += lam * (Q[free] - P[free])
    return P


# ---------------------------------------------------------------- the warp
def hair_weight(P):
    """1 where her surface is pulled onto Levi's skull (the hair zone), 0 over
    the features."""
    X = np.abs(P[:, 0] - MID_X)
    y, z = P[:, 1], P[:, 2]
    w_fore = smooth(EYE_C[1] + FOREHEAD[0], EYE_C[1] + FOREHEAD[1], z)
    w_side = smooth(SIDE[0], SIDE[1], X) * smooth(CHIN_FREE[1], CHIN_FREE[0], z)
    w_back = smooth(BACK[0], BACK[1], y) * smooth(CHIN_FREE[1], CHIN_FREE[0], z)
    w = np.maximum.reduce([w_fore, w_side, w_back])
    q = np.hypot((X - EYE_C[0]) / EYE_R[0], (z - EYE_C[1]) / EYE_R[1])
    eye = smooth(1.35, 1.0, q)
    return w * (1.0 - eye)


def nose_weight(P):
    X = np.abs(P[:, 0] - MID_X)
    z = P[:, 2] - EYE_C[1]
    a, b, c, d = NOSE_ROWS
    # in from a .. b below the eye centre, out from c .. d below it
    return np.exp(-(X / NOSE_TONE[2]) ** 2) * smooth(-a, -b, z) * smooth(-d, -c, z)


# Levi's lower face (round 11 face pass): one smooth receding line from the nose to the
# chin in profile, no pout, no dimples beside the mouth's corners (ref/setting.png profile;
# the mouth is a clean small mark from every angle). On her rest, before the warp, so her
# morphs open the lips from it: the skin round the mouth (the lips, the corners' pockets and
# dimples) moves along -Y onto a smooth fill of the face round it (a thin-plate spline through
# her skin outside the zone: it meets the face there in height and slope); her rolled inner lip
# (a strip of the face round the slit) and the mouth's pocket, teeth and tongue ride the lip's
# edge; then the mouth slides MOUTH_DROP down along the face (Levi's mouth sits lower).
LIP_SLIT = 0.0437                      # m below the eye centre: her slit
LIP_ZONE = (0.019, 0.0080)             # half-width, half-height round the slit: the relief here goes
#                                        (wide: her grooves 12-14 mm beside the corners drew a line
#                                        from each corner seen at 45-75 deg)
LIP_FADE = 1.45                        # ... fading out by this many times the zone
LIP_WINDOW = (0.035, 0.022, 0.0100)    # the fill's data: |x| <, below / above the slit [m] (not the nose;
#                                        the move fades out under the window's top)
LIP_TPS_SMOOTH = 0.02                  # thin-plate smoothing [mm^2]
LIP_STRIP = (0.015, 0.008, 0.236)      # her rolled inner lip: |x|, |z - slit| [m], UV v below
LIP_TEETH = 0.3                        # share of the lips' move the teeth and tongue take
MOUTH_DROP = 0.002                     # m the mouth slides down along the face
MOUTH_DROP_R = (0.025, 0.010)          # its Gaussian reach: X (wide: the corners drop as the middle), z [m]


class _TPS:
    """A thin-plate spline y(x, z) (mm inside) through points, lightly smoothed."""

    def __init__(self, xz, y, lam):
        self.q = np.asarray(xz, float) * 1000.0
        n = len(self.q)
        K = self._k(self.q, self.q) + lam * np.eye(n)
        Pm = np.concatenate([np.ones((n, 1)), self.q], 1)
        A = np.zeros((n + 3, n + 3))
        A[:n, :n], A[:n, n:], A[n:, :n] = K, Pm, Pm.T
        sol = np.linalg.solve(A, np.concatenate([np.asarray(y, float) * 1000.0, np.zeros(3)]))
        self.w, self.a = sol[:n], sol[n:]

    @staticmethod
    def _k(p, q):
        r2 = ((p[:, None, :] - q[None, :, :]) ** 2).sum(-1)
        return 0.5 * r2 * np.log(np.maximum(r2, 1e-12))

    def __call__(self, xz):
        q = np.atleast_2d(np.asarray(xz, float)) * 1000.0
        out = np.empty(len(q))
        for i in range(0, len(q), 2048):
            qq = q[i:i + 2048]
            out[i:i + 2048] = self._k(qq, self.q) @ self.w + self.a[0] + qq @ self.a[1:]
        return out / 1000.0


class LipRest:
    """The rest change of the mouth: D on the coarse face (fc), at() for other points."""

    def __init__(self, fc):
        P, T, M, UV = fc['pos'], fc['tri'], fc['mat'], fc['uv']
        n = len(P)
        skin = np.zeros(n, bool)
        skin[np.unique(T[M == 0])] = True
        cav = np.zeros(n, bool)
        cav[np.unique(T[M == 1])] = True
        self.border = np.nonzero(skin & cav)[0]
        x, z, y = P[:, 0] - MID_X, P[:, 2] - EYE_C[1] + LIP_SLIT, P[:, 1]
        # her rolled inner lip: face triangles round the slit with the strip's own UVs
        c = P[T].mean(1)
        st = ((M == 0) & (np.abs(c[:, 0] - MID_X) < LIP_STRIP[0])
              & (np.abs(c[:, 2] - EYE_C[1] + LIP_SLIT) < LIP_STRIP[1]) & (UV[..., 1].max(1) < LIP_STRIP[2]))
        strip = np.zeros(n, bool)
        strip[np.unique(T[st])] = True
        outer = np.zeros(n, bool)
        outer[np.unique(T[(M == 0) & ~st])] = True
        edge = strip & outer                      # the lip's edge: where it rolls in
        inner = strip & ~outer                    # the rolled strip itself
        front = skin & (y < -0.095)
        q = np.hypot(x / LIP_ZONE[0], z / LIP_ZONE[1])
        data = front & outer & ~strip & (q > 1.0) & (np.abs(x) < LIP_WINDOW[0]) & (z > -LIP_WINDOW[1]) \
            & (z < LIP_WINDOW[2])
        self.fill = _TPS(np.stack([x[data], z[data]], 1), y[data], LIP_TPS_SMOOTH)
        w = smooth(LIP_FADE, 1.0, q) * smooth(LIP_WINDOW[2], LIP_WINDOW[2] - 0.0025, z) * front * (outer | edge)
        D = np.zeros_like(P)
        D[:, 1] = w * (self.fill(np.stack([x, z], 1)) - y)
        # the rolled strip rides the lip's edge
        ev = np.nonzero(edge)[0]
        kd = KDTree(len(ev))
        for i, v in enumerate(ev):
            kd.insert(Vector(P[v]), i)
        kd.balance()
        for v in np.nonzero(inner)[0]:
            hits = kd.find_n(Vector(P[v]), 3)
            wt = np.array([1.0 / (h[2] + 1e-4) ** 2 for h in hits])
            D[v] = (wt[:, None] * D[[ev[h[1]] for h in hits]]).sum(0) / wt.sum()
        # the pocket (her mouth piece behind the lips) moves with the lips
        self.kd_b = KDTree(len(self.border))
        for i, v in enumerate(self.border):
            self.kd_b.insert(Vector(P[v]), i)
        self.kd_b.balance()
        self.Db = D[self.border].copy()
        for v in np.nonzero(cav & ~skin)[0]:
            D[v] = self._from_border(P[v])
        # down along the fill at the slit's middle (it recedes: down and back)
        h = 1e-4
        fz = float(np.diff(self.fill(np.array([[0.0, -h], [0.0, h]])))[0] / (2 * h))
        t = np.array([0.0, -fz, -1.0])
        self.t_drop = t / np.linalg.norm(t)
        D += self._drop(P)
        self.D = D
        self.w = w
        res = y[data] - self.fill(np.stack([x[data], z[data]], 1))
        print(f'HEAD lips: the fill through {int(data.sum())} points (rms {np.sqrt((res ** 2).mean()) * 1000:.2f} mm); '
              f'strip {int(inner.sum())} + edge {len(ev)} verts; the lip line moves '
              f'{D[self.border, 1].min() * 1000:.1f} .. {D[self.border, 1].max() * 1000:.1f} mm along y, '
              f'max {np.linalg.norm(D, axis=1).max() * 1000:.1f} mm')

    def _from_border(self, q):
        hits = self.kd_b.find_n(Vector(q), 4)
        dist = np.array([h[2] for h in hits])
        wt = 1.0 / (dist + 1e-4) ** 2
        return (wt[:, None] * self.Db[[h[1] for h in hits]]).sum(0) / wt.sum()

    def _drop(self, Q):
        X, z = np.abs(Q[:, 0] - MID_X), Q[:, 2] - EYE_C[1]
        g = np.exp(-(X / MOUTH_DROP_R[0]) ** 2 - ((z + LIP_SLIT) / MOUTH_DROP_R[1]) ** 2)
        return MOUTH_DROP * g[:, None] * self.t_drop

    def at(self, Q):
        """The change at points inside the mouth (teeth, tongue): LIP_TEETH of the lips' move
        (the lower teeth, dropped with the jaw, came through the chin's skin with all of it), and
        the drop."""
        return LIP_TEETH * np.array([self._from_border(q) for q in Q]) + self._drop(Q)


def jaw_lift(P):
    """JAW_LIFT at points P (her aligned rest) [m, up]."""
    a, (y0, y1), (z0, z1), (x0, x1) = JAW_LIFT
    return a * smooth(y0, y1, P[:, 1]) * smooth(z0, z1, P[:, 2]) * smooth(x0, x1, np.abs(P[:, 0] - MID_X))


def skin_vertices(fc):
    """1.0 on the coarse face's skin vertices, 0 on the mouth cavity's only."""
    out = np.zeros(len(fc['pos']))
    out[np.unique(fc['tri'][fc['mat'] == 0])] = 1.0
    return out


class Warp:
    """W on the coarse face (exact per vertex) and interpolated elsewhere."""

    def __init__(self, fc, skull_bvh):
        P = fc['pos']
        faces = [tuple(t) for t in fc['tri']]
        nb = adjacency(len(P), faces)
        bnd = set(v for lp in boundary_loops(faces) for v in lp)
        fixed = np.array([i in bnd for i in range(len(P))])
        Ps = laplace(P, nb, fixed, n=40)
        D = np.zeros_like(P)
        w = hair_weight(P)
        miss = 0
        for i in np.nonzero(w > 1e-4)[0]:
            d = P[i] - WARP_C
            r = np.linalg.norm(d)
            u = d / r
            hit = skull_bvh.ray_cast(Vector(WARP_C), Vector(u), 0.5)
            if hit[0] is None:
                miss += 1
                continue
            D[i] = w[i] * (hit[3] - r) * u
        nw = nose_weight(P)
        D += nw[:, None] * (NOSE_TONE[0] * (Ps - P) + np.array([0.0, 0.0, NOSE_TONE[1]]))
        D[:, 2] += jaw_lift(P) * skin_vertices(fc)
        self.P, self.D, self.w = P, D, w
        self.kd = KDTree(len(P))
        for i, p in enumerate(P):
            self.kd.insert(Vector(p), i)
        self.kd.balance()
        self.miss = miss

    def interp(self, Q):
        out = np.zeros((len(Q), 3))
        for i, q in enumerate(Q):
            hits = self.kd.find_n(Vector(q), INTERP_K)
            idx = np.array([h[1] for h in hits])
            dist = np.array([h[2] for h in hits])
            wt = np.exp(-(dist / INTERP_SIGMA) ** 2 + (dist.min() / INTERP_SIGMA) ** 2)
            out[i] = (wt[:, None] * self.D[idx]).sum(0) / wt.sum()
        return out

    def face(self, d=None):
        """Warped face, rest (d None) or a key: W(p + d) with the interpolated
        warp's change from p to p + d added to the exact rest warp."""
        out = self.P + self.D
        if d is None:
            return out
        out = out + d
        mv = np.nonzero(np.abs(d).max(1) > 1e-9)[0]
        if len(mv):
            out[mv] += self.interp(self.P[mv] + d[mv]) - self.interp(self.P[mv])
        return out

    def points(self, Q, d=None):
        if d is None:
            return Q + self.interp(Q)
        R = Q + self.interp(Q)
        mv = np.nonzero(np.abs(d).max(1) > 1e-9)[0]
        out = R + d
        if len(mv):
            out[mv] += self.interp(Q[mv] + d[mv]) - self.interp(Q[mv])
        return out


# ---------------------------------------------------------------- subdivision
def quad_faces(pos, tri, uv, mat):
    """Join her triangles into quads (her mesh was modelled in quads): pairs
    across an edge with matching UVs and material, by bmesh.ops.join_triangles.
    Returns (faces (list of vertex lists), corner UVs (list of lists), mats)."""
    import bmesh
    bm = bmesh.new()
    vs = [bm.verts.new(Vector(p)) for p in pos]
    bm.verts.index_update()
    lay = bm.loops.layers.uv.new('UVMap')
    for t, u, m in zip(tri, uv, mat):
        f = bm.faces.new([vs[i] for i in t])
        f.material_index = int(m)
        for loop, uu in zip(f.loops, u):
            loop[lay].uv = (float(uu[0]), float(uu[1]))
    bm.normal_update()           # (the angle tests read the face normals)
    bmesh.ops.join_triangles(bm, faces=list(bm.faces), cmp_uvs=True, cmp_materials=True,
                             angle_face_threshold=math.radians(40.0), angle_shape_threshold=math.radians(40.0))
    faces, uvs, mats = [], [], []
    for f in bm.faces:
        faces.append([lp.vert.index for lp in f.loops])
        uvs.append([tuple(lp[lay].uv) for lp in f.loops])
        mats.append(f.material_index)
    bm.free()
    return faces, uvs, mats


def subdivide(pos, faces, uvs, mats, keys):
    """One Catmull-Clark level of a mesh and of every key (a temporary object
    with a Subsurf modifier, evaluated per key: the subdivision is linear, so
    W(p + d) keys stay consistent). Returns (pos, faces, uvs, mats, keys)."""
    me = bpy.data.meshes.new('_graft_tmp')
    me.from_pydata([tuple(p) for p in pos], [], faces)
    tmp_mats = [bpy.data.materials.new('_graft_tmp_%d' % i) for i in range(2)]
    for m in tmp_mats:
        me.materials.append(m)
    me.polygons.foreach_set('material_index', np.array(mats, np.int32))
    lay = me.uv_layers.new(name='UVMap')
    flat = [c for u in uvs for uu in u for c in uu]
    lay.data.foreach_set('uv', np.array(flat, np.float32))
    obj = bpy.data.objects.new('_graft_tmp', me)
    bpy.context.scene.collection.objects.link(obj)
    names = list(keys)
    obj.shape_key_add(name='Basis', from_mix=False)
    for n in names:
        kb = obj.shape_key_add(name='k%d' % names.index(n), from_mix=False)
        kb.data.foreach_set('co', np.asarray(keys[n], np.float32).ravel())
        kb.value = 0.0
    mod = obj.modifiers.new('sub', 'SUBSURF')
    mod.levels = mod.render_levels = 1
    mod.boundary_smooth = 'PRESERVE_CORNERS'
    mod.uv_smooth = 'PRESERVE_BOUNDARIES'
    mod.use_limit_surface = True
    mod.quality = 3
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()

    def read(full=False):
        ev = obj.evaluated_get(dg)
        m = ev.to_mesh()
        co = np.empty(len(m.vertices) * 3)
        m.vertices.foreach_get('co', co)
        out = co.reshape(-1, 3)
        if full:
            fs = [list(p.vertices) for p in m.polygons]
            ul = m.uv_layers.active
            u = np.empty(len(m.loops) * 2)
            ul.data.foreach_get('uv', u)
            u = u.reshape(-1, 2)
            us = [[tuple(u[li]) for li in p.loop_indices] for p in m.polygons]
            mi = [p.material_index for p in m.polygons]
            ev.to_mesh_clear()
            return out, fs, us, mi
        ev.to_mesh_clear()
        return out
    P2, F2, U2, M2 = read(True)
    K2 = {}
    kbs = obj.data.shape_keys.key_blocks
    for i, n in enumerate(names):
        kbs[i + 1].value = 1.0
        dg.update()
        K2[n] = read()
        kbs[i + 1].value = 0.0
    bpy.data.objects.remove(obj, do_unlink=True)
    bpy.data.meshes.remove(me)
    for m in tmp_mats:
        bpy.data.materials.remove(m)
    return P2, F2, U2, M2, K2


# ---------------------------------------------------------------- the skull and the cut


def chart(P):
    """Head-centred chart: the angle from straight ahead, as a 2D point in the
    direction round the forward axis (the face is a disc round the origin)."""
    d = P - CHART_C
    d = d / np.linalg.norm(d, axis=1, keepdims=True)
    u = np.arccos(np.clip(-d[:, 1], -1, 1))
    phi = np.arctan2(d[:, 2], d[:, 0])
    return np.stack([u * np.cos(phi), u * np.sin(phi)], 1)


def inside_poly(pts, poly):
    x, y = pts[:, 0], pts[:, 1]
    inside = np.zeros(len(pts), bool)
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        c = ((y1 > y) != (y2 > y)) & (x < (x2 - x1) * (y - y1) / (y2 - y1 + 1e-30) + x1)
        inside ^= c
    return inside


def cut_skull(S, Sfaces, B_pos):
    """Skull faces her mask does not cover (chart test against her border B):
    returns (kept face list, the cut loop C ordered, the neck end loop)."""
    poly = chart(B_pos)
    inn = inside_poly(chart(S), poly)
    keep = [f for f in Sfaces if not any(inn[v] for v in f)]
    for _ in range(20):          # no pinched boundary: drop faces that touch the cut at a single corner
        loops = boundary_loops(keep)
        deg = {}
        from collections import Counter
        E = Counter()
        for f in keep:
            for a, b in zip(f, list(f[1:]) + [f[0]]):
                E[(min(a, b), max(a, b))] += 1
        for (a, b), c in E.items():
            if c == 1:
                deg[a] = deg.get(a, 0) + 1
                deg[b] = deg.get(b, 0) + 1
        bad = {v for v, c in deg.items() if c > 2}
        if not bad:
            break
        keep = [f for f in keep if not any(v in bad for v in f)]
    loops = boundary_loops(keep)
    if len(loops) == 1:
        return keep, loops[0], [], loops
    # the neck end is the loop lowest down; the cut the longest other one
    low = min(loops, key=lambda lp: S[lp, 2].mean())
    cut = max([lp for lp in loops if lp is not low], key=len)
    return keep, cut, low, loops


GAP_KEEP, GAP_R = 0.0025, 0.016    # m: the cut is drawn to this far off her border; over this distance
GAP_EVEN = 0.3                      # share of even spacing in the cut's points along her border


def offset_targets(Apos, Aout, Cpos):
    """Where the cut's points go: each point's arc-length parameter on the open
    chain Apos (her border's upper arc; closest point, made strictly increasing
    and evened out a little), then GAP_KEEP along the outward direction Aout
    there."""
    seg = np.linalg.norm(np.diff(Apos, axis=0), axis=1)
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    a, ab = Apos[:-1], np.diff(Apos, axis=0)
    s = np.zeros(len(Cpos))
    for j, p in enumerate(Cpos):
        t = np.clip(((p - a) * ab).sum(1) / np.maximum((ab * ab).sum(1), 1e-18), 0.0, 1.0)
        k = int(np.argmin(np.linalg.norm(a + t[:, None] * ab - p, axis=1)))
        s[j] = cum[k] + t[k] * seg[k]
    s[0], s[-1] = 0.0, cum[-1]
    s = np.minimum(np.maximum.accumulate(s), cum[-1])
    s = (1.0 - GAP_EVEN) * s + GAP_EVEN * np.linspace(0.0, cum[-1], len(s))
    pts = np.stack([np.interp(s, cum, Apos[:, i]) for i in range(3)], 1)
    out = np.stack([np.interp(s, cum, Aout[:, i]) for i in range(3)], 1)
    out /= np.maximum(np.linalg.norm(out, axis=1, keepdims=True), 1e-9)
    return pts + out * GAP_KEEP


def close_gap(S, kept, C, targets):
    """Draw the skull round the cut onto `targets` (where her jaw is fuller or
    lower than Levi's the cut lies centimetres off her border): the skull
    within GAP_R of the cut follows with a falloff (inverse-distance blend of
    the cut's moves)."""
    Cpos = S[C]
    off = targets - Cpos
    ln = np.linalg.norm(off, axis=1)
    kd = KDTree(len(C))
    for n, p in enumerate(Cpos):
        kd.insert(Vector(p), n)
    kd.balance()
    out = S.copy()
    for v in kept:
        hits = kd.find_n(Vector(S[v]), 6)
        dist = np.array([h[2] for h in hits])
        f = 1.0 - smooth(0.0, GAP_R, dist.min())
        if f <= 0:
            continue
        wt = 1.0 / (dist + 1e-4) ** 2
        out[v] += f * (wt[:, None] * off[[h[1] for h in hits]]).sum(0) / wt.sum()
    return out, float(ln.max())


def zip_chains(A, Apos, C, Cpos):
    """Triangles zipping two open chains that start and end at matching points
    (her border's upper arc, the skull's cut): C's points get the arc-length
    parameter of their closest point on A (monotonic), merged by parameter."""
    nA, nC = len(A), len(C)
    seg = np.linalg.norm(np.diff(Apos, axis=0), axis=1)
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    a, ab = Apos[:-1], np.diff(Apos, axis=0)
    s = np.zeros(nC)
    for j, p in enumerate(Cpos):
        t = np.clip(((p - a) * ab).sum(1) / np.maximum((ab * ab).sum(1), 1e-18), 0.0, 1.0)
        d = np.linalg.norm(a + t[:, None] * ab - p, axis=1)
        k = int(np.argmin(d))
        s[j] = cum[k] + t[k] * seg[k]
    s[0], s[-1] = 0.0, cum[-1]
    s = np.minimum(np.maximum.accumulate(s), cum[-1])
    tris = []
    i = j = 0
    while i < nA - 1 or j < nC - 1:
        if i < nA - 1 and (j >= nC - 1 or cum[i + 1] <= s[j + 1]):
            tris.append((A[i], A[i + 1], C[j]))
            i += 1
        else:
            tris.append((A[i], C[j + 1], C[j]))
            j += 1
    return tris


# the neck: a loft from the head's lower edge (her under-jaw border, the skull's
# lowest ring behind) into a tube NECK_TUCK inside the body's neck
NECK_TOP_Z = (1.217, 1.247)     # m: the tube's top (front, back): the loft arrives here, vertically
NECK_END_Z = 1.200              # m: the open end, inside the body's neck under the choker
LOFT_RINGS, TUBE_RINGS = 9, 2
LOFT_PULL = (0.9, 1.0)          # Hermite tangent lengths (leaving the head, arriving down the tube) / chord
LOFT_TSMOOTH, LOFT_RSMOOTH = 10, 6  # smoothing passes: edge tangents and column angles; along the rings
LOFT_ACROSS = 0.45                  # least share of a column's start across the edge (see loft_neck)


def neck_ring(theta, z):
    hw, yf, yb = BODY_NECK
    cy, hd = (yf + yb) / 2, (yb - yf) / 2
    lim = 1.0 - NECK_TUCK / hw
    return np.stack([hw * lim * np.sin(theta), cy - hd * lim * np.cos(theta), z], -1)


def loft_neck(Upos, T0, Nsurf=None):
    """Rings (list of (n, 3) arrays) from the loop Upos (the head's lower edge,
    leaving along T0) down into the tucked neck tube; each column keeps its
    angle round the neck axis."""
    hw, yf, yb = BODY_NECK
    cy = (yf + yb) / 2
    th = np.unwrap(np.arctan2(Upos[:, 0], -(Upos[:, 1] - cy)))
    if th[-1] < th[0]:
        raise ValueError('loft_neck: the loop must run counter-clockwise seen from above')
    th = np.maximum.accumulate(th)
    T0 = T0.copy()
    for _ in range(LOFT_TSMOOTH):        # the tangent field turns smoothly round the edge
        T0 = (np.roll(T0, 1, 0) + 2 * T0 + np.roll(T0, -1, 0)) / 4
    T0 /= np.linalg.norm(T0, axis=1, keepdims=True)
    # the tube's columns: evenly spaced in angle from the edge's own angles (smoothed),
    # so a column's angle does not jump where the edge's spacing changes
    for _ in range(LOFT_TSMOOTH):
        ext = np.concatenate([th[-1:] - 2 * np.pi, th, th[:1] + 2 * np.pi])
        th = (ext[:-2] + 2 * ext[1:-1] + ext[2:]) / 4
    zt = NECK_TOP_Z[0] + (NECK_TOP_Z[1] - NECK_TOP_Z[0]) * (1.0 - np.cos(th)) / 2
    P1 = neck_ring(th, zt)
    if Nsurf is not None:
        # each column leaves across the edge, not along it: at least LOFT_ACROSS of its
        # tangent along the edge's outward normal in the surface (where the edge climbs
        # the back of the jaw, a column hanging straight down would run along it)
        tang = np.roll(Upos, -1, 0) - np.roll(Upos, 1, 0)
        tang /= np.maximum(np.linalg.norm(tang, axis=1, keepdims=True), 1e-12)
        nu = np.cross(Nsurf, tang)
        nu /= np.maximum(np.linalg.norm(nu, axis=1, keepdims=True), 1e-12)
        nu[(nu * (P1 - Upos)).sum(1) < 0] *= -1.0
        d = (T0 * nu).sum(1)
        low = d < LOFT_ACROSS
        T0[low] += (LOFT_ACROSS - d[low])[:, None] * nu[low]
        T0 /= np.linalg.norm(T0, axis=1, keepdims=True)
    chord = np.linalg.norm(P1 - Upos, axis=1)[:, None]
    m0 = T0 * chord * LOFT_PULL[0]
    m1 = np.array([0.0, 0.0, -1.0]) * chord * LOFT_PULL[1]
    rings = []
    for k in range(1, LOFT_RINGS + 1):
        t = k / LOFT_RINGS
        h00, h10 = 2 * t ** 3 - 3 * t ** 2 + 1, t ** 3 - 2 * t ** 2 + t
        h01, h11 = -2 * t ** 3 + 3 * t ** 2, t ** 3 - t ** 2
        r = h00 * Upos + h10 * m0 + h01 * P1 + h11 * m1
        # every ring point on its column's angle round the neck axis (the angles are in
        # order): where the edge turns a corner (her jaw's border meeting the skull's
        # ring) the first rings cannot fold back over each other
        rho = np.hypot(r[:, 0], r[:, 1] - cy)
        own = np.arctan2(r[:, 0], -(r[:, 1] - cy))
        own = th + (own - th + np.pi) % (2 * np.pi) - np.pi
        a = float(smooth(1.0, 4.0, k))     # (none on the first ring: the edge itself climbs
        ang = own + a * (th - own)         # the back of the jaw, where its columns stack)
        r[:, 0], r[:, 1] = rho * np.sin(ang), cy - rho * np.cos(ang)
        # even out the ring along itself (more toward the tube, none at the head's edge)
        for _ in range(int(round(LOFT_RSMOOTH * t))):
            r = (np.roll(r, 1, 0) + 2 * r + np.roll(r, -1, 0)) / 4
        rings.append(r)
    for k in range(1, TUBE_RINGS + 1):
        rings.append(neck_ring(th, zt + (NECK_END_Z - zt) * k / TUBE_RINGS))
    return rings


def propagate(P, src_idx, src_d, targets, radius=PROP_R, k=6):
    """Motion of her border (src) carried onto nearby skull vertices (targets),
    fading out over `radius`."""
    kd = KDTree(len(src_idx))
    for n, i in enumerate(src_idx):
        kd.insert(Vector(P[i]), n)
    kd.balance()
    out = {}
    for v in targets:
        hits = kd.find_n(Vector(P[v]), k)
        dist = np.array([h[2] for h in hits])
        f = 1.0 - smooth(0.0, radius, dist.min())
        if f <= 0:
            continue
        wt = 1.0 / (dist + 1e-4) ** 2
        d = (wt[:, None] * src_d[[h[1] for h in hits]]).sum(0) / wt.sum()
        if np.abs(d).max() > 1e-9:
            out[v] = f * d
    return out
