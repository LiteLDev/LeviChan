"""Levi's upper lash on 风堇's lash strip (round 11 face pass; no bpy).

Her upper lash is a band of her 眉睫 strips about twice the design's weight, with a
fishtail wing, an up-swept prong (a separate island, dropped by head.py) and a solid
hook down the inner corner. Levi's (ref/setting.png front, levelled; the illustration;
the profile) is a thin even line on the lid margin, heavier in the outer third, one
flat blade at the outer end, a thin wall line down the outer corner, and an inner end
that tapers out above the corner (_head_levi.LASH_T, LASH_WALL_T).

One per-vertex map does it, the same for the rest and every key, so closed and
half-closed lashes stay seated on the lid edge:

    L(Q)[v] = A_v(Q) + k_v (Q[v] - A_v(Q))

* the margin M: her strip's lower edge, the vertices that lie on the face's eye-hole
  edge; a vertex's anchor A_v(Q) is a fixed blend of two neighbouring margin vertices
  (its foot on M at rest), taken in Q, so the anchor rides the lid in every key;
* k_v = target thickness / her thickness at that place along M (T / H), so the band
  keeps its curl and depth, only nearer the margin;
* the wing (past the outer wall's top) is scaled in its own frame (base on M -> tip,
  taken in Q): shorter and thinner, with its tip lifted a little;
* the inner end: the band tapers to LASH_END_T where the margin comes down below
  LASH_CUT_Z, and the columns nasal of it go (drop_tris).
All lengths in D (the iris width incl. its rim), x' from the iris centre (+ toward
the nose), z' up, measured on the baked rest.
"""
import numpy as np

from . import _head_levi as HL

D_SHOW = 0.957          # the iris shows to this share of its dish's half-width (the cup's rim hides the rest)
LASH_CUT_Z = 0.18       # D: nasal of x' 0.45 the band ends where the baked margin comes below this
LASH_END_T = 0.03       # D: ... tapering to this
WING_X = (-0.78, -0.70)  # x' [D]: the wing's own map is full from here (outer) .. none from here
WING_Z = -0.06          # z' [D]: the wing lies above this (the wall line below)
WING_SCALE = (0.80, 0.55)   # the wing's length, thickness (across its centreline) kept
WING_LIFT = 0.07        # D: the wing's tip lifted (at rest; along her rest frame's z)
WING_LIFT_R = 0.25      # D: ... falling off over this distance from the tip


def _smooth(e0, e1, x):
    t = np.clip((np.asarray(x, float) - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


class LashMap:
    """The map on one eye's upper strip.

    P: (n, 3) her rest positions of the sub-piece's vertices, Q0: their baked rest,
    upper: bool (n,) the upper strip's vertices, tri: (m, 3) the sub-piece's
    triangles, hole: (h, 3) the face's eye-hole edge vertices (her rest, this eye),
    centre: the iris centre, rx: its dish's half-width, side: +1 (L) / -1 (R)."""

    def __init__(self, P, Q0, upper, tri, hole, centre, rx, side, log=print):
        self.side = side
        self.D = D = 2.0 * rx * D_SHOW
        self.c = np.asarray(centre, float)
        n = len(P)
        up = np.nonzero(upper)[0]
        # the margin: upper vertices on the face's eye-hole edge, ordered along it
        dh = np.array([np.linalg.norm(hole - P[v], axis=1).min() for v in up])
        M = up[dh < 5e-5]
        if len(M) < 6:
            raise ValueError(f'head lash: only {len(M)} margin vertices')
        xs, zs = self.xz(Q0[M])
        # order: the margin runs from the inner end, over the top, down the outer wall;
        # walk it by nearest neighbours from the most nasal point
        order = [int(np.argmax(xs))]
        left = set(range(len(M))) - set(order)
        while left:
            last = order[-1]
            j = min(left, key=lambda k: (xs[k] - xs[last]) ** 2 + (zs[k] - zs[last]) ** 2)
            order.append(j)
            left.remove(j)
        M = M[order]
        self.M = M
        mx, mz = self.xz(Q0[M])
        seg = np.hypot(np.diff(mx), np.diff(mz))
        cum = np.concatenate([[0.0], np.cumsum(seg)])
        self.cum = cum
        # every upper vertex's foot on M (front plane, D units): segment j, share t, distance h
        X, Z = self.xz(Q0)
        js = np.zeros(n, int)
        ts = np.zeros(n)
        ss = np.zeros(n)
        hs = np.zeros(n)
        for v in up:
            best = None
            for j in range(len(M) - 1):
                a = np.array([mx[j], mz[j]])
                b = np.array([mx[j + 1], mz[j + 1]])
                ab = b - a
                t = float(np.dot([X[v], Z[v]] - a, ab) / max(np.dot(ab, ab), 1e-12))
                tc = min(max(t, 0.0), 1.0)
                d = float(np.linalg.norm([X[v], Z[v]] - (a + tc * ab)))
                # past the ends the margin runs on straight (the inner hook, the wall's foot)
                if (j == 0 and t < 0) or (j == len(M) - 2 and t > 1):
                    tc = t
                    d = float(np.linalg.norm([X[v], Z[v]] - (a + t * ab)))
                if best is None or d < best[0]:
                    best = (d, j, tc)
            hs[v], js[v], ts[v] = best
            ss[v] = cum[best[1]] + best[2] * seg[best[1]]
        # smooth the feet along the strip (margin vertices are their own feet)
        nb = [set() for _ in range(n)]
        for t in tri:
            for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
                if upper[a] and upper[b]:
                    nb[a].add(b)
                    nb[b].add(a)
        onM = np.zeros(n, bool)
        onM[M] = True
        for k, v in enumerate(M):
            ss[v] = cum[k]
        free = upper & ~onM
        for _ in range(5):
            s2 = ss.copy()
            for v in np.nonzero(free)[0]:
                if nb[v]:
                    s2[v] = 0.5 * ss[v] + 0.5 * np.mean([ss[u] for u in nb[v]])
            ss = s2
        js = np.clip(np.searchsorted(cum, ss, side='right') - 1, 0, len(M) - 2)
        ts = (ss - cum[js]) / np.maximum(seg[js], 1e-12)
        self.js, self.ts, self.ss = js, ts, ss
        A0 = self.anchor(Q0)
        ax0, az0 = self.xz(A0)
        dist = np.hypot(X - ax0, Z - az0)          # in the front plane (the strip curls back in depth)
        # the wing: past the wall's top (scaled in its own frame below)
        self.upper = upper
        self.wing_w = np.where(upper & (Z > WING_Z), _smooth(WING_X[1], WING_X[0], X), 0.0)
        # her thickness along M (the wing left out): the farthest vertex within +-0.04 D of arc
        band = up[self.wing_w[up] < 0.5]
        grid = np.linspace(min(ss[up].min(), 0.0), max(ss[up].max(), cum[-1]), 160)
        H = np.array([dist[band][np.abs(ss[band] - g) < 0.04].max(initial=0.0) for g in grid])
        H = np.maximum(H, 1e-3)
        for _ in range(3):
            H = np.convolve(np.pad(H, 2, mode='edge'), np.ones(5) / 5, mode='valid')
        # the target along M, from the anchor's place
        ax_, az_ = self.xz(A0)
        Tv = np.interp(ax_, [p[0] for p in HL.LASH_T], [p[1] for p in HL.LASH_T])
        # the outer wall: the margin below z' +0.10 on the outer side
        zmin = mz.min()
        wall = (ax_ < 0.0) & (az_ < 0.10)
        tw = np.clip((0.10 - az_) / max(0.10 - zmin, 1e-6), 0.0, 1.0)
        Tv = np.where(wall, HL.LASH_WALL_T[0] + (HL.LASH_WALL_T[1] - HL.LASH_WALL_T[0]) * tw, Tv)
        # the inner end: where the margin, nasal of x' 0.45, first comes below LASH_CUT_Z
        k45 = next((k for k in range(len(M)) if mx[k] <= 0.45), 0)
        if k45 > 0:
            f = (mx[k45 - 1] - 0.45) / max(mx[k45 - 1] - mx[k45], 1e-9)
            s45 = cum[k45 - 1] + f * seg[k45 - 1]
        else:
            s45 = cum[0]
        below = [k for k in range(k45) if mz[k] < LASH_CUT_Z]
        s_cut = cum[max(below)] if below else cum[0]
        s_cut = min(s_cut, s45 - 1e-6)
        taper = np.clip((ss - s_cut) / max(s45 - s_cut, 1e-6), 0.0, 1.0)
        T45 = float(np.interp(0.45, [p[0] for p in HL.LASH_T], [p[1] for p in HL.LASH_T]))
        Tv = np.where(ss < s45, LASH_END_T + (T45 - LASH_END_T) * taper, Tv)
        self.s_cut = s_cut
        Hv = np.interp(ss, grid, H)
        k = np.clip(Tv / Hv, 0.05, 1.0)
        self.k = np.where(upper, k, 1.0)
        self.k[M] = 1.0
        # the wing's frame: base, the margin vertex at the wall's top; tip, its outermost vertex
        tipv = up[np.argmin(X[up])]
        self.tip = tipv
        kb = int(np.argmin(np.abs(mz - 0.10) + 10.0 * (mx > 0)))     # the wall's top on M
        self.base = M[kb]
        self.lift = np.where(upper, WING_LIFT * D * np.exp(-(np.linalg.norm(P - P[tipv], axis=1) / (WING_LIFT_R * D)) ** 2), 0.0)
        drop = np.array([(upper[t].all() and (ss[t] < s_cut).all()) for t in tri])
        self.drop_tris = drop
        log(f'HEAD lash {"L" if side > 0 else "R"}: margin {len(M)} verts, D {D * 1000:.1f} mm, k {self.k[up].min():.2f}'
            f'..{self.k[up].max():.2f} (median {np.median(self.k[up]):.2f}), inner end cut at s {s_cut:.2f} D '
            f'({drop.sum()} tris go), wing {int((self.wing_w > 0).sum())} verts')

    def xz(self, Q):
        q = np.asarray(Q, float) - self.c
        return -self.side * q[..., 0] / self.D, q[..., 2] / self.D

    def anchor(self, Q):
        M = self.M
        return (1.0 - self.ts)[:, None] * Q[M[self.js]] + self.ts[:, None] * Q[M[np.minimum(self.js + 1, len(M) - 1)]]

    def pre(self, P):
        """Her rest moved before any bake (the wing tip's lift): so every key carries it."""
        out = np.array(P, float)
        out[:, 2] += self.lift
        return out

    def __call__(self, Q):
        Q = np.asarray(Q, float)
        A = self.anchor(Q)
        out = A + self.k[:, None] * (Q - A)
        # the wing in its own frame
        b, t = Q[self.base], Q[self.tip]
        ax = t - b
        L = np.linalg.norm(ax)
        if L > 1e-9:
            ax = ax / L
            o = Q - b
            along = (o @ ax)[:, None] * ax
            wq = b + WING_SCALE[0] * along + WING_SCALE[1] * (o - along)
            w = self.wing_w[:, None]
            out = out * (1.0 - w) + wq * w
        return np.where(self.upper[:, None], out, Q)
