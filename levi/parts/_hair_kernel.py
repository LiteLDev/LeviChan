"""Shared hair-strand kernel for hair_front and hair_back (round 11).

A private helper (files starting with '_' are not parts): it builds no objects
itself. Parts author control points and call it inside their own build():

    from . import _hair_kernel as hk
    st = hk.strand(pts, name='lock_A', width=0.02, aspect=3.0,
                   facing=lambda p: outward(p), curl=hk.curl(turn=220, toward='in'),
                   split=hk.split(at=0.8), grad=(0.55, 0.95))
    hk.emit(bm, st)            # quads + toon_grad + UVs into the part's BMesh

Units are metres in the world frame (Z up, the character faces -Y). The geometry
is numpy only (deterministic, no randomness); only emit() touches bmesh.

Technique (the 风堇 study, analysis report 'hair-technique'): smooth hair is
not density but four habits, all enforced here.
  1. Crescent sections: a convex outer face, a flatter or concave underside and
     thin rims (two vertices per rim), not round or lens-shaped tubes.
  2. Curvature limits everywhere: a C2 centreline with R >= max(12 mm, 0.6 w)
     and rho = (section extent toward the bend centre) x curvature <= 0.45, so
     the inner side never folds; at most ~6-8 deg of turn per ring.
  3. Strands narrow before a curl tightens, and the curl tightens as it thins
     (kappa ~ w^-0.8), entering from the spine's own curvature (G2).
  4. Tips are flat blades (thickness ~ w^1.4, >= 1 mm to the apex), optionally
     split into sub-tips welded into the same island.

Pipeline of strand(): centreline() (C2 spline, ~1 mm samples, curvature-limited
by relax()) -> frames() (rotation-minimising frame + rate-limited twist toward
the authored facing) -> extent check (rho with the real sections, re-relax) ->
optional lift (shingling, see rest_on()) -> optional curl (grown, G2) ->
adaptive rings -> crescent sections -> optional split tips -> validate().

Conventions
-----------
- `facing`: the direction the strand's OUTER (convex) face looks: a callable
  f(p: np.ndarray(3)) -> 3-vector, a constant 3-vector, or keyframes
  [(u, vec), ...] (u = arc fraction of the spine). Parts with mathutils
  functions wrap them: facing=lambda p: head_normal(Vector(p)).
- Section frame per sample: T (tangent, root -> tip), N (outer-face normal),
  B = T x N (across the width). A ring lists the outer face first, rim to rim
  along +B, then the underside back (n vertices, cos-spaced, half-offset, so
  each rim gets exactly two vertices: one on each face). Vertex k on the top
  face and vertex n-1-k on the underside share the same position across.
- u (UV) runs across the width (0 at the -B rim, 1 at the +B rim, the same on
  both faces, so the ring has no seam), v along the strand (arc / length).
- Each tube is closed: a ladder cap across the root (n/2-1 quads that follow
  the crescent) and a fan to an apex at the tip. Sub-tips share the split ring.
"""
import math

import numpy as np

# ---------------------------------------------------------------- limits
STEP = 0.001            # m, centreline sampling
R_MIN = 0.012           # m, minimum bend radius ...
R_PER_W = 0.6           # ... and at least this x the local width
RHO_MAX = 0.45          # (extent toward the bend centre) x curvature on the spine
RHO_CURL = 0.40         # ... inside a grown curl
TIP_ZONE = 0.10         # last share of a strand's length where ...
TIP_W = 0.006           # ... a tip narrower than this (m) ...
TIP_R_MIN = 0.008       # ... may bend down to this radius (m)
TWIST_RATE = 3.0        # deg / mm, the section's roll rate limit
MAX_SHIFT = 0.008       # m: relax() may move the authored centreline at most this far ...
MAX_SHRINK = 0.12       # ... or shorten it by this share; beyond, the shape is wrong, not rough
FACING_STEP = 0.004     # m between samples of a callable facing
FACING_SMOOTH = 0.003   # m, Gaussian sigma on the facing angle before the rate limit

RING_ARC = 0.008        # m: a new ring at arc >= min(RING_ARC, RING_ARC_W * w) ...
RING_ARC_W = 0.35
RING_TURN = 6.0         # ... or at this turn (deg) ...
RING_TWIST = 6.0        # ... or this twist (deg) ...
RING_WRATIO = 1.15      # ... or this width ratio since the last ring,
RING_GAP = 0.0015       # never closer than max(RING_GAP, RING_GAP_W * w) ...
RING_GAP_W = 0.12
RING_GAP_TIP = 0.001    # ... (RING_GAP_TIP in the relaxed tip zone) ...
RING_HARD = 7.0         # ... unless the turn / twist since the last ring would pass this (deg)
RING_HARD_WRATIO = 1.22
TIP_POINT = 1.2         # the apex lies at least this x the last ring's width past it (a pointed blade)
GROOVE_KEEP = 0.5       # share of the half-thickness left at a split's cut column at the split ring ...
GROOVE_SIGMA = 0.12     # ... (Gaussian in the across parameter s), deepening over the warp stretch
RING_N = ((0.020, 12), (0.040, 14), (None, 16))   # vertices around by the strand's max width

WRAP = 0.2              # mid-surface wrap: m(s) = -WRAP * (w/2) * s^2 (rims curl to the underside)
K_IN = 0.6              # underside = m - K_IN * h (flatter / concave underside)
T_RIM = 0.001           # m, rim thickness term: h(s) = (a/2)(1 - s^2)^H_EXP + T_RIM/2
H_EXP = 0.6
T_EXP = 1.4             # t(u) = t_mid * (w / w_max)^T_EXP ...
T_MIN = 0.001           # ... >= T_MIN to the apex (flat blades, not cones)
W_MIN = 0.0008          # m, narrowest ring
TIP_DECAY = 0.001 / math.log(1.0 / 0.84)   # m: the width never falls faster than x0.84 per mm,
                                            # so ~1 mm rings can follow a closing tip (a blade end)
SWELL = (0.6, 0.12)     # width S(u): s0 -> 1 over the first u_sw of the length (smoothstep)
TIP = (0.6, 2.2, 0.7)   # width T(u) = (1 - x^a)^b, x = (u - u_t) / (1 - u_t) past u_t

# validate(): hard limits checked on the built rings
LIMITS = {
    'turn': 8.0,            # deg of centreline turn per ring
    'rho': 0.5,             # inner extent x curvature at a ring
    'fold': 0,              # quads whose along-strand edge runs backwards
    'twist': 10.0,          # deg of section roll per ring
    'wratio': (0.8, 1.25),  # width ratio between consecutive rings (but the last two)
    'gap': 0.010,           # m, ring spacing
    'apex': 12.0,           # deg between the last ring's tangent and the chord to the apex
}

GRAD_ATTR = 'toon_grad'


class HairKernelError(ValueError):
    """A strand breaks a kernel limit; the message names the strand and where."""


# ---------------------------------------------------------------- small helpers
def smooth01(x):
    """Smoothstep of x clipped to 0..1 (scalars or arrays)."""
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def _norm(a, axis=-1):
    return np.sqrt(np.sum(a * a, axis=axis))


def _unit(a, axis=-1):
    n = _norm(a, axis)
    return a / np.maximum(n, 1e-15)[..., None] if np.ndim(a) > 1 else a / max(float(n), 1e-15)


def _blur(x, sigma):
    """1-D Gaussian blur (sigma in samples), edge-normalised."""
    x = np.asarray(x, float)
    if sigma <= 0.3 or len(x) < 3:
        return x.copy()
    r = int(math.ceil(3.0 * sigma))
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    num = np.convolve(np.pad(x, r, mode='edge'), k, mode='valid')
    return num / k.sum()


def _tridiag(a, b, c, d):
    """Thomas solve: a (sub), b (diag), c (super) of length n; d (n, 3)."""
    n = len(b)
    cp = np.empty(n)
    dp = np.empty_like(d)
    cp[0] = c[0] / b[0]
    dp[0] = d[0] / b[0]
    for i in range(1, n):
        den = b[i] - a[i] * cp[i - 1]
        cp[i] = c[i] / den
        dp[i] = (d[i] - a[i] * dp[i - 1]) / den
    x = np.empty_like(d)
    x[-1] = dp[-1]
    for i in range(n - 2, -1, -1):
        x[i] = dp[i] - cp[i] * x[i + 1]
    return x


def _as_fn(v, name):
    """float | (root, tip) | callable(u) -> callable(u array) -> array."""
    if callable(v):
        return lambda u: np.asarray(v(np.asarray(u, float)), float) * np.ones_like(np.asarray(u, float))
    if isinstance(v, (tuple, list)) and len(v) == 2:
        a, b = float(v[0]), float(v[1])
        return lambda u: a + (b - a) * smooth01(np.asarray(u, float))
    try:
        c = float(v)
    except (TypeError, ValueError):
        raise HairKernelError(f'{name}: expected a number, (root, tip) or a callable of u, got {v!r}')
    return lambda u: np.full(np.shape(u), c)


def ring_count(w_max):
    """Vertices around a strand of this maximum width (12 / 14 / 16, RING_N)."""
    for lim, n in RING_N:
        if lim is None or w_max <= lim:
            return n
    return RING_N[-1][1]


# ---------------------------------------------------------------- sections & profiles
def ring_params(n):
    """(s, top) of a half-offset cos-spaced ring of n vertices: s in (-1, 1) across
    the width (B), top = on the outer face. Vertex k at phi = 2 pi (k + 0.5) / n,
    s = -cos(phi): the outer face runs k = 0 .. n/2-1 (s rising), the underside
    back. Each rim gets two vertices (one per face)."""
    if n < 6 or n % 2:
        raise HairKernelError(f'ring of {n} vertices: use an even count >= 6')
    phi = 2.0 * math.pi * (np.arange(n) + 0.5) / n
    return -np.cos(phi), np.sin(phi) > 0


def section(n, w, t, wrap=WRAP, k_in=K_IN, t_rim=T_RIM, p=H_EXP, s=None, top=None):
    """Crescent / C cross-section(s).

    w, t: full width and total thickness at the middle (m); scalars or arrays (S,)
    for S sections. Returns x (across, along B) and y (along N), each (S, n)
    (or (n,) for scalars). Mid-surface m(s) = -wrap (w/2) s^2, half-thickness
    h(s) = (a/2)(1 - s^2)^p + t_rim/2 with a chosen so the middle is exactly t
    thick, outer face m + h, underside m - k_in h. s / top override the ring
    layout (ring_params(n))."""
    if s is None:
        s, top = ring_params(n)
    s = np.asarray(s, float)
    top = np.asarray(top, bool)
    scalar = np.ndim(w) == 0 and np.ndim(t) == 0 and np.ndim(wrap) == 0
    w = np.atleast_1d(np.asarray(w, float))[:, None]
    t = np.atleast_1d(np.asarray(t, float))[:, None]
    wrap = np.atleast_1d(np.asarray(wrap, float))[:, None]
    a = np.maximum(0.0, 2.0 * t / (1.0 + k_in) - t_rim)
    h = 0.5 * a * np.clip(1.0 - s * s, 0.0, 1.0) ** p + 0.5 * t_rim
    m = -wrap * 0.5 * w * s * s
    y = np.where(top, m + h, m - k_in * h)
    x = 0.5 * w * s * np.ones_like(y)
    if scalar:
        return x[0], y[0]
    return x, y


def taper(u, swell=SWELL, tip=TIP):
    """Width share S(u) T(u): S swells s0 -> 1 over the first u_sw (smoothstep);
    T = (1 - x^a)^b past u_t (x = (u - u_t) / (1 - u_t)), an ogive closing at u = 1.
    swell / tip None turn either off."""
    u = np.asarray(u, float)
    S = np.ones_like(u)
    if swell:
        s0, usw = swell
        S = s0 + (1.0 - s0) * smooth01(u / usw)
    T = np.ones_like(u)
    if tip:
        ut, a, b = tip
        x = np.clip((u - ut) / (1.0 - ut), 0.0, 1.0)
        T = np.clip(1.0 - x ** a, 0.0, 1.0) ** b
    return S * T


def limit_decay(w, s, decay=TIP_DECAY):
    """Raise a width profile w over arc s so it never falls faster than
    exp(-ds / decay) toward the tip (forward pass in log space): an ogive that
    would close to zero ends as a narrow blade instead."""
    lw = np.log(np.maximum(np.asarray(w, float), 1e-9)) + np.asarray(s, float) / decay
    return np.exp(np.maximum.accumulate(lw) - np.asarray(s, float) / decay)


def thickness(w, t_mid, w_max, t_min=T_MIN):
    """t = t_mid (w / w_max)^T_EXP, at least t_min: thickness closes faster than
    the width, so tips are flat blades."""
    return np.maximum(t_min, t_mid * (np.asarray(w, float) / w_max) ** T_EXP)


def _extent(x, y, dirB, dirN):
    """Section extent toward a direction given by its B / N components (S,): max_k
    (x_k dirB + y_k dirN)."""
    return np.max(x * dirB[:, None] + y * dirN[:, None], axis=1)


# ---------------------------------------------------------------- curves
class Curve:
    """A dense polyline (about STEP apart): P (M, 3) points root -> tip, s (M,) arc
    from the root, T (M, 3) unit tangents, K (M, 3) curvature vectors (|K| = 1/R,
    pointing at the bend centre), fixed (M,) anchors held by relax()."""

    def __init__(self, P, fixed=None):
        P = np.asarray(P, float)
        if len(P) < 3:
            raise HairKernelError('a curve needs at least 3 samples')
        self.P = P
        self.fixed = np.zeros(len(P), bool) if fixed is None else np.asarray(fixed, bool).copy()
        d = np.diff(P, axis=0)
        L = np.maximum(_norm(d), 1e-12)
        du = d / L[:, None]
        self.s = np.concatenate([[0.0], np.cumsum(L)])
        T = np.empty_like(P)
        T[0], T[-1] = du[0], du[-1]
        T[1:-1] = du[:-1] * L[1:, None] + du[1:] * L[:-1, None]
        self.T = _unit(T)
        K = np.zeros_like(P)
        K[1:-1] = (du[1:] - du[:-1]) / (0.5 * (L[:-1] + L[1:]))[:, None]
        K[0], K[-1] = K[1], K[-2]
        self.K = K

    @property
    def length(self):
        return float(self.s[-1])

    @property
    def u(self):
        return self.s / max(self.length, 1e-12)

    @property
    def kappa(self):
        return _norm(self.K)


def _c2_spline(Q, alpha, d0=None, d1=None):
    """C2 cubic spline through Q at knots spaced |dQ|^alpha (natural ends, or
    clamped to the unit directions d0 / d1). Returns (knots, evaluate(t))."""
    k = len(Q)
    chord = np.maximum(_norm(np.diff(Q, axis=0)), 1e-9)
    dt = chord ** alpha
    t = np.concatenate([[0.0], np.cumsum(dt)])
    A = np.zeros((k, k))
    r = np.zeros((k, 3))
    for i in range(1, k - 1):
        A[i, i - 1], A[i, i], A[i, i + 1] = dt[i - 1], 2.0 * (dt[i - 1] + dt[i]), dt[i]
        r[i] = 6.0 * ((Q[i + 1] - Q[i]) / dt[i] - (Q[i] - Q[i - 1]) / dt[i - 1])
    if d0 is None:
        A[0, 0] = 1.0
    else:   # derivative w.r.t. t: a unit direction x |dQ| / dt
        g0 = _unit(np.asarray(d0, float)) * chord[0] / dt[0]
        A[0, 0], A[0, 1] = 2.0 * dt[0], dt[0]
        r[0] = 6.0 * ((Q[1] - Q[0]) / dt[0] - g0)
    if d1 is None:
        A[-1, -1] = 1.0
    else:
        g1 = _unit(np.asarray(d1, float)) * chord[-1] / dt[-1]
        A[-1, -2], A[-1, -1] = dt[-1], 2.0 * dt[-1]
        r[-1] = 6.0 * (g1 - (Q[-1] - Q[-2]) / dt[-1])
    M = np.linalg.solve(A, r)

    def ev(tt):
        tt = np.asarray(tt, float)
        i = np.clip(np.searchsorted(t, tt, 'right') - 1, 0, k - 2)
        h = dt[i][:, None]
        a = (t[i + 1][:, None] - tt[:, None]) / h
        b = 1.0 - a
        return (a * Q[i] + b * Q[i + 1]
                + ((a ** 3 - a) * M[i] + (b ** 3 - b) * M[i + 1]) * h * h / 6.0)
    return t, ev


def _bspline(Q, deg=3):
    """Clamped B-spline with Q as control points, knots by chord-length averaging.
    Returns (greville abscissae, evaluate(t in 0..1))."""
    k = len(Q)
    p = min(deg, k - 1)
    c = np.concatenate([[0.0], np.cumsum(_norm(np.diff(Q, axis=0)))])
    c = c / max(c[-1], 1e-12)
    inner = [float(np.mean(c[j:j + p])) for j in range(1, k - p)]
    knots = np.array([0.0] * (p + 1) + inner + [1.0] * (p + 1))
    grev = np.array([np.mean(knots[j + 1:j + p + 1]) for j in range(k)])

    def ev(tt):
        tt = np.clip(np.asarray(tt, float), 0.0, 1.0 - 1e-12)
        # Cox-de Boor, vectorised over the parameters
        Nb = np.zeros((len(tt), len(knots) - 1))
        for j in range(len(knots) - 1):
            Nb[:, j] = (knots[j] <= tt) & (tt < knots[j + 1])
        for q in range(1, p + 1):
            Nn = np.zeros((len(tt), len(knots) - 1 - q))
            for j in range(len(knots) - 1 - q):
                d1 = knots[j + q] - knots[j]
                d2 = knots[j + q + 1] - knots[j + 1]
                if d1 > 0:
                    Nn[:, j] += (tt - knots[j]) / d1 * Nb[:, j]
                if d2 > 0:
                    Nn[:, j] += (knots[j + q + 1] - tt) / d2 * Nb[:, j + 1]
            Nb = Nn
        out = Nb @ Q
        out[np.asarray(tt) >= 1.0 - 1e-12] = Q[-1]
        return out
    return grev, ev


def _hermite_resample(P, fixed, step):
    """Resample a dense polyline at ~step by cubic Hermite (Bessel tangents), piece
    by piece between fixed samples, which stay exact samples."""
    d = np.maximum(_norm(np.diff(P, axis=0)), 1e-12)
    t = np.concatenate([[0.0], np.cumsum(d)])
    M = len(P)
    m = np.empty_like(P)
    a, b = d[:-1][:, None], d[1:][:, None]
    m[1:-1] = (b * (P[1:-1] - P[:-2]) / a + a * (P[2:] - P[1:-1]) / b) / (a + b)
    m[0] = 2.0 * (P[1] - P[0]) / d[0] - m[1]
    m[-1] = 2.0 * (P[-1] - P[-2]) / d[-1] - m[-2]
    brk = sorted(set([0, M - 1] + list(np.flatnonzero(fixed))))
    tt, ff = [], []
    for i0, i1 in zip(brk, brk[1:]):
        L = t[i1] - t[i0]
        cnt = max(1, int(round(L / step)))
        tt.append(t[i0] + L * np.arange(cnt) / cnt)
        f = np.zeros(cnt, bool)
        f[0] = bool(fixed[i0])
        ff.append(f)
    tt.append([t[-1]])
    ff.append([bool(fixed[-1])])
    tt = np.concatenate(tt)
    i = np.clip(np.searchsorted(t, tt, 'right') - 1, 0, M - 2)
    h = np.maximum(t[i + 1] - t[i], 1e-12)[:, None]
    x = (tt[:, None] - t[i][:, None]) / h
    x2, x3 = x * x, x * x * x
    out = ((2 * x3 - 3 * x2 + 1) * P[i] + (x3 - 2 * x2 + x) * h * m[i]
           + (-2 * x3 + 3 * x2) * P[i + 1] + (x3 - x2) * h * m[i + 1])
    fx = np.concatenate(ff)
    # fixed samples land exactly on their old position
    for j in np.flatnonzero(fx):
        k = int(np.argmin(np.abs(t - tt[j])))
        out[j] = P[k]
    return out, fx


def _spline_curve(points, anchors, tangents, mode, alpha, step):
    Q = np.asarray(points, float)
    if Q.ndim != 2 or Q.shape[1] != 3 or len(Q) < 2:
        raise HairKernelError('points: a list of at least two 3-D points')
    k = len(Q)
    anchors = sorted(set(int(a) % k for a in anchors) | {0})
    if mode == 'bspline' and k >= 4:
        grev, ev = _bspline(Q)
        tk = grev
        t0, t1 = 0.0, 1.0
    elif mode in ('interp', 'bspline'):
        d0, d1 = (tuple(tangents) + (None, None))[:2]
        tk, ev = _c2_spline(Q, alpha, d0, d1)
        t0, t1 = 0.0, float(tk[-1])
    else:
        raise HairKernelError(f"mode {mode!r}: 'interp' or 'bspline'")
    # dense evaluation, then exact points at uniform arc between anchors
    if mode == 'bspline' and k >= 4:
        tf = np.linspace(t0, t1, 64 * k + 1)
    else:
        tf = np.concatenate([np.linspace(tk[i], tk[i + 1], 64, endpoint=False) for i in range(k - 1)]
                            + [[tk[-1]]])
    tf = np.unique(np.concatenate([tf, tk[anchors]]))
    Pf = ev(tf)
    arc = np.concatenate([[0.0], np.cumsum(_norm(np.diff(Pf, axis=0)))])
    sa = np.interp(tk[anchors], tf, arc)
    brk = sorted(set([0.0, float(arc[-1])] + [float(x) for x in sa]))
    ss, fx = [], []
    for a0, a1 in zip(brk, brk[1:]):
        if a1 - a0 < 1e-9:
            continue
        cnt = max(1, int(round((a1 - a0) / step)))
        ss.append(a0 + (a1 - a0) * np.arange(cnt) / cnt)
        f = np.zeros(cnt, bool)
        f[0] = any(abs(a0 - x) < 1e-9 for x in sa) or a0 == 0.0
        fx.append(f)
    ss.append([arc[-1]])
    fx.append([(k - 1) in anchors])
    ss = np.concatenate(ss)
    fixed = np.concatenate(fx)
    P = ev(np.interp(ss, arc, tf))
    if len(P) < 3:
        raise HairKernelError('strand too short for the sampling step')
    return Curve(P, fixed)


def _kmax_fn(width, e_bend, r_min, rho_max, tip_zone):
    def km(u):
        u = np.asarray(u, float)
        R = np.full(u.shape, r_min)
        if width is not None:
            w = width(u)
            R = np.maximum(R, R_PER_W * w)
            tz = (u > 1.0 - tip_zone) & (w < TIP_W)
            R = np.where(tz, np.maximum(TIP_R_MIN, R_PER_W * w), R)
        k = 1.0 / R
        if e_bend is not None:
            k = np.minimum(k, rho_max / np.maximum(e_bend(u), 1e-6))
        return k
    return km


def relax(curve, kmax, *, name='strand', iters=16, strict=True, max_shift=MAX_SHIFT, max_shrink=MAX_SHRINK):
    """Curvature-limited fairing: implicit, masked Laplacian smoothing where
    |K| > kmax (callable of the arc fraction u, or an array over the samples),
    with the curve's fixed samples (anchors, both ends) held. Returns a new
    Curve resampled at the same spacing. A bend that cannot be opened with the
    anchors where they are (a U-turn tighter than allowed, a corner on an
    anchor), or only by moving the curve more than max_shift (m) or shortening
    it by more than max_shrink, raises HairKernelError (strict) naming where:
    such a shape has to be re-authored, not smoothed away."""
    P = curve.P.copy()
    fixed = curve.fixed.copy()
    fixed[0] = fixed[-1] = True
    step = curve.length / (len(P) - 1)
    km_arr = None if callable(kmax) else np.asarray(kmax, float)
    u0 = curve.u
    c = curve
    for it in range(iters + 1):
        c = Curve(P, fixed)
        km = kmax(c.u) if km_arr is None else np.interp(c.u, u0, km_arr)
        ratio = c.kappa / km
        if not np.all(np.isfinite(ratio)):
            raise HairKernelError(f'{name}: non-finite curvature while relaxing (duplicate points?)')
        if ratio.max() <= 1.0:
            if it and strict:
                _check_shift(curve, c, max_shift, max_shrink, name)
            return c
        if it == iters:
            break
        bad = ratio > 0.995
        r = float(np.clip(np.median(1.0 / km[bad]) / step, 3.0, 400.0))
        mask = _blur(bad.astype(float), 0.75 * r)
        mask = np.clip(2.0 * mask / max(mask.max(), 1e-12), 0.0, 1.0)
        mask[fixed] = 0.0
        lam = min((0.35 * r) ** 2 * 2.0 ** it, 1e9)
        lm = lam * mask
        a = -0.5 * lm
        cc = -0.5 * lm
        b = 1.0 + lm
        a[0] = cc[-1] = 0.0
        P = _tridiag(a, b, cc, P)
        P, fixed = _hermite_resample(P, fixed, step)
    if strict:
        i = int(np.argmax(ratio))
        on_anchor = bool(c.fixed[max(0, i - 2):i + 3].any())
        raise HairKernelError(
            f'{name}: cannot open the bend at {1000 * c.s[i]:.0f} mm of {1000 * c.length:.0f} mm '
            f'(point {np.round(c.P[i], 4).tolist()}): R {1000 / max(c.kappa[i], 1e-9):.1f} mm, '
            f'needs >= {1000 / km[i]:.1f} mm'
            + (' -- the bend sits on an anchor: move or untag it' if on_anchor else
               ' -- the control points turn too tightly (a U-turn narrower than 2R?): widen the '
               'turn, narrow the strand there, or turn its broad face toward the bend'))
    return c


def _check_shift(old, new, max_shift, max_shrink, name):
    """Raise when relax() moved the curve too far from the authored one."""
    A, Bp = new.P, old.P
    best = np.full(len(A), np.inf)
    for i in range(0, len(Bp), 256):
        d = _norm(A[:, None, :] - Bp[None, i:i + 256, :])
        best = np.minimum(best, d.min(1))
    j = int(np.argmax(best))
    shrink = 1.0 - new.length / max(old.length, 1e-12)
    if best[j] > max_shift or shrink > max_shrink:
        raise HairKernelError(
            f'{name}: opening its bends to the curvature limits moves the centreline {1000 * best[j]:.1f} mm '
            f'(at {1000 * new.s[j]:.0f} mm, point {np.round(new.P[j], 4).tolist()}) and shortens it '
            f'{100 * shrink:.0f}% (limits {1000 * max_shift:.0f} mm, {100 * max_shrink:.0f}%): the control '
            'points turn too tightly for the strand\'s width -- widen the turn, narrow the strand there, '
            'or turn its broad face toward the bend')


def centreline(points, *, anchors=(), tangents=(None, None), mode='interp', alpha=1.0, step=STEP,
               width=None, e_bend=None, r_min=R_MIN, rho_max=RHO_MAX, tip_zone=TIP_ZONE,
               name='strand', strict=True):
    """C2 centreline sampled about every `step` m, curvature-limited.

    points: control points (m). mode 'interp': a C2 cubic spline THROUGH them,
    knots spaced |dP|^alpha (1 = chord length, 0.5 = centripetal); natural ends
    unless tangents=(root_dir, tip_dir) clamp them. mode 'bspline': a clamped
    cubic B-spline with the points as control vertices (it passes through the two
    ends only; use it for one smooth arch through a bulge point).
    anchors: indices of points held fixed by the limiter (the root always is; in
    'bspline' mode an interior anchor pins the curve point at that control
    vertex's Greville abscissa).
    width / e_bend: callables of the arc fraction u giving the full width and
    the section's extent toward the bend centre (m). The curve is relaxed until
    R >= max(r_min, R_PER_W * w) (down to TIP_R_MIN where w < TIP_W in the last
    tip_zone) and kappa * e_bend <= rho_max.
    Returns a Curve."""
    c = _spline_curve(points, anchors, tangents, mode, alpha, step)
    w = None if width is None else _as_fn(width, 'width')
    e = None if e_bend is None else _as_fn(e_bend, 'e_bend')
    km = _kmax_fn(w, e, r_min, rho_max, tip_zone)
    return relax(c, lambda u: 0.98 * km(u), name=name, strict=strict)


# ---------------------------------------------------------------- frames
def rmf(P, T, U0):
    """Rotation-minimising frame by double reflection (Wang et al. 2008):
    returns U (M, 3) with U[0] = U0 projected normal to T[0], and V = T x U."""
    M = len(P)
    U = np.empty_like(P)
    u = np.asarray(U0, float) - np.dot(U0, T[0]) * T[0]
    if _norm(u) < 1e-9:
        u = np.cross(T[0], [0.0, 0.0, 1.0] if abs(T[0][2]) < 0.9 else [1.0, 0.0, 0.0])
    U[0] = u / _norm(u)
    Pl, Tl = P.tolist(), T.tolist()
    ux, uy, uz = U[0]
    for i in range(M - 1):
        p0, p1, t0, t1 = Pl[i], Pl[i + 1], Tl[i], Tl[i + 1]
        v1 = (p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2])
        c1 = v1[0] * v1[0] + v1[1] * v1[1] + v1[2] * v1[2]
        if c1 < 1e-24:
            U[i + 1] = (ux, uy, uz)
            continue
        f = 2.0 / c1 * (v1[0] * ux + v1[1] * uy + v1[2] * uz)
        rl = (ux - f * v1[0], uy - f * v1[1], uz - f * v1[2])
        f = 2.0 / c1 * (v1[0] * t0[0] + v1[1] * t0[1] + v1[2] * t0[2])
        tl = (t0[0] - f * v1[0], t0[1] - f * v1[1], t0[2] - f * v1[2])
        v2 = (t1[0] - tl[0], t1[1] - tl[1], t1[2] - tl[2])
        c2 = v2[0] * v2[0] + v2[1] * v2[1] + v2[2] * v2[2]
        if c2 > 1e-24:
            f = 2.0 / c2 * (v2[0] * rl[0] + v2[1] * rl[1] + v2[2] * rl[2])
            rl = (rl[0] - f * v2[0], rl[1] - f * v2[1], rl[2] - f * v2[2])
        d = rl[0] * t1[0] + rl[1] * t1[1] + rl[2] * t1[2]
        ux, uy, uz = rl[0] - d * t1[0], rl[1] - d * t1[1], rl[2] - d * t1[2]
        n = math.sqrt(ux * ux + uy * uy + uz * uz)
        ux, uy, uz = ux / n, uy / n, uz / n
        U[i + 1] = (ux, uy, uz)
    return U, np.cross(T, U)


def _lipschitz(theta, s, rate):
    """Closest-in-the-middle rate-limited copy of theta: the mean of the upper and
    lower McShane envelopes, so |d theta / ds| <= rate and an already slow theta
    is unchanged."""
    th = list(map(float, theta))
    up, lo = th[:], th[:]
    sl = list(map(float, s))
    M = len(th)
    for i in range(1, M):
        d = rate * (sl[i] - sl[i - 1])
        up[i] = min(up[i], up[i - 1] + d)
        lo[i] = max(lo[i], lo[i - 1] - d)
    for i in range(M - 2, -1, -1):
        d = rate * (sl[i + 1] - sl[i])
        up[i] = min(up[i], up[i + 1] + d)
        lo[i] = max(lo[i], lo[i + 1] - d)
    return 0.5 * (np.array(up) + np.array(lo))


def _facing_targets(curve, facing, fstep):
    """(sample indices, target vectors) of the facing spec along the curve."""
    M = len(curve.P)
    if callable(facing):
        n = max(2, int(round(curve.length / fstep)) + 1)
        idx = np.unique(np.round(np.linspace(0, M - 1, n)).astype(int))
        vec = np.array([np.asarray(facing(curve.P[i].copy()), float) for i in idx])
        return idx, vec
    if len(facing) == 3 and all(np.isscalar(x) for x in facing):
        n = max(2, int(round(curve.length / fstep)) + 1)
        idx = np.unique(np.round(np.linspace(0, M - 1, n)).astype(int))
        return idx, np.tile(np.asarray(facing, float), (len(idx), 1))
    keys = sorted(((float(u), np.asarray(v, float)) for u, v in facing), key=lambda kv: kv[0])
    idx = np.array([int(np.argmin(np.abs(curve.u - u))) for u, _ in keys])
    return idx, np.array([v for _, v in keys])


def frames(curve, facing, *, twist_rate=TWIST_RATE, smooth=FACING_SMOOTH, fstep=FACING_STEP):
    """Section frames along a Curve.

    A rotation-minimising frame (U, V) carries the section with no roll of its
    own; the roll theta (angle of N from U toward V) goes through the facing
    targets (see the module docstring), Gaussian-smoothed by `smooth` (m) and
    rate-limited to twist_rate deg / mm -- no per-ring sign flips.
    Returns dict(U, V, theta, N, B), arrays over the curve's samples."""
    T = curve.T
    idx, vec = _facing_targets(curve, facing, fstep)
    proj = vec - np.sum(vec * T[idx], axis=1)[:, None] * T[idx]
    good = _norm(proj) > 0.2 * np.maximum(_norm(vec), 1e-12)
    if not good.any():
        raise HairKernelError('facing: every target is (nearly) along the strand')
    idx, proj = idx[good], proj[good]
    U, V = rmf(curve.P, T, proj[0])
    ang = np.arctan2(np.sum(proj * V[idx], axis=1), np.sum(proj * U[idx], axis=1))
    ang = np.unwrap(ang)
    theta = np.interp(curve.s, curve.s[idx], ang)
    step = curve.length / (len(curve.P) - 1)
    theta = _blur(theta, smooth / step)
    theta = _lipschitz(theta, curve.s, math.radians(twist_rate) * 1000.0)
    theta = _blur(theta, 1.0)
    N = np.cos(theta)[:, None] * U + np.sin(theta)[:, None] * V
    B = np.cross(T, N)
    return {'U': U, 'V': V, 'theta': theta, 'N': N, 'B': B}


# ---------------------------------------------------------------- curl
def curl(turn=240.0, toward='in', face='centre', radius=None, core=0.6, lead=1.5, exp=0.8,
         taper=(1.5, 0.8), pitch=None, rho=RHO_CURL):
    """Parameters of a grown end curl (strand(curl=...)); checked here.

    turn: total turn (deg, 180-300 for Levi's open curls) from the spine's end.
    toward: the bend direction at the start: 'in' (toward the underside, -N:
      the lock curls under), 'out' (+N, flips out), '+B' / '-B' (sideways, in
      the width plane) or a world 3-vector.
    face: how the section sits in the curl: 'centre' (the broad face toward the
      curl centre -- a ribbon wound round the curl, the drill / ringlet look),
      'plane' (the width lies in the bend plane: a flat C-blade cut from a
      sheet, 风堇's end curls), 'keep' (no extra roll). The roll toward it runs
      at <= TWIST_RATE over the lead-in (longer if it must).
    radius: bend radius (m) at the curl core (default max(1.6 w_c, 1.25 R_MIN)).
    core: width at the core as a share of the spine's end width (the strand
      narrows over the lead-in before it tightens), lead: lead-in length in
      spine widths (>= 1.5): the curvature ramps linearly from the spine's.
    exp: past the lead-in kappa = kappa_c (w_c / w)^exp, capped by rho (extent
      x curvature) and R >= max(R_MIN, R_PER_W w) (TIP_R_MIN at a narrow end).
    taper: (a, b) of the closing width w_c (1 - psi^a)^b over the turn after the
      lead-in (psi 0 -> 1): the curl thins as it turns and ends in a blade.
    pitch: None, or (h, rise): a ringlet rising h m per turn (>= 1.2 w_c) toward
      the world vector rise."""
    if not 30.0 <= turn <= 720.0:
        raise HairKernelError(f'curl turn {turn} deg: expected 30-720 (Levi: 180-300)')
    if lead < 1.5:
        raise HairKernelError(f'curl lead {lead}: the curvature needs >= 1.5 widths to ramp in')
    if not 0.2 <= core <= 1.0:
        raise HairKernelError(f'curl core {core}: expected 0.2-1.0 of the spine width')
    if face not in ('centre', 'plane', 'keep'):
        raise HairKernelError(f"curl face {face!r}: 'centre', 'plane' or 'keep'")
    return {'turn': float(turn), 'toward': toward, 'face': face, 'radius': radius, 'core': float(core),
            'lead': float(lead), 'exp': float(exp), 'taper': tuple(taper), 'pitch': pitch, 'rho': float(rho)}


def _rot(v, axis, ang):
    """Rodrigues rotation of v (3,) about a unit axis."""
    c, s = math.cos(ang), math.sin(ang)
    return v * c + np.cross(axis, v) * s + axis * np.dot(axis, v) * (1.0 - c)


def _grow_curl(st, prm, sec, t_of_w, step, name):
    """Integrate a curl from the spine's end state st (P, T, U, V, K, theta, w).

    Returns dict of arrays over the curl's samples (the junction excluded): P, T,
    U, V, theta, w, t, wrap, psi (0 in the lead-in, then 0 -> 1 over the turn)."""
    P, T, U, V = (np.array(st[k], float) for k in ('P', 'T', 'U', 'V'))
    K0 = np.asarray(st['K'], float)
    th0, w0, wrap = float(st['theta']), float(st['w']), float(st['wrap'])
    n, k_in, t_rim = sec['n'], sec['k_in'], sec['t_rim']
    k0u, k0v = float(np.dot(K0, U)), float(np.dot(K0, V))
    tw = prm['toward']
    if isinstance(tw, str):
        off = {'in': math.pi, 'out': 0.0, '+B': 0.5 * math.pi, '-B': -0.5 * math.pi}
        if tw not in off:
            raise HairKernelError(f"{name}: curl toward {tw!r}: 'in', 'out', '+B', '-B' or a vector")
        phi0 = th0 + off[tw]
    else:
        D = np.asarray(tw, float)
        D = D - np.dot(D, T) * T
        if _norm(D) < 1e-6:
            raise HairKernelError(f'{name}: curl toward {tw}: along the strand at its end')
        phi0 = math.atan2(float(np.dot(D, V)), float(np.dot(D, U)))
    # roll target relative to the bend direction phi
    face = prm['face']
    if face == 'keep':
        cands = [th0 - phi0]
    elif face == 'centre':
        cands = [0.0, math.pi]          # N toward / away from the centre
    else:
        cands = [0.5 * math.pi, -0.5 * math.pi]   # B along the bend
    rel0 = th0 - phi0
    best = min(cands, key=lambda c: abs((c - rel0 + math.pi) % (2 * math.pi) - math.pi))
    delta = (best - rel0 + math.pi) % (2 * math.pi) - math.pi
    rate = math.radians(TWIST_RATE) * 1000.0 * 0.9
    w_c = prm['core'] * w0
    L_in = prm['lead'] * w0
    L_tw = max(L_in, 1.5 * abs(delta) / rate)    # smoothstep's steepest slope is 1.5 / L
    R_c = prm['radius'] or max(1.6 * w_c, 1.25 * R_MIN)
    k_c = 1.0 / R_c
    Theta = math.radians(prm['turn'])
    ta, tb = prm['taper']
    sgn_pitch, h_pitch = 0.0, 0.0
    if prm['pitch'] is not None:
        h_pitch, rise = prm['pitch']
        h_pitch = max(float(h_pitch), 1.2 * w_c)
        d0 = math.cos(phi0) * U + math.sin(phi0) * V
        sgn_pitch = 1.0 if np.dot(np.cross(T, d0), np.asarray(rise, float)) >= 0 else -1.0
    s_ar = 0.0
    turned, turn_in, phi = 0.0, None, phi0
    w_prev = None
    out = {k: [] for k in ('P', 'T', 'U', 'V', 'theta', 'w', 't', 'wrap', 'psi')}
    guard = 50.0 * (Theta * R_c + L_in) / step
    for _ in range(int(guard)):
        s_ar += step
        r = min(1.0, s_ar / L_in)
        if s_ar <= L_in:
            w = w0 + (w_c - w0) * float(smooth01(r))
            psi = 0.0
        else:
            if turn_in is None:
                turn_in = turned
                if Theta - turn_in < math.radians(20.0):
                    raise HairKernelError(
                        f'{name}: the curl lead-in already turns {math.degrees(turn_in):.0f} deg of '
                        f'{prm["turn"]:.0f}: raise turn or shorten lead')
            psi = min(1.0, (turned - turn_in) / (Theta - turn_in))
            w = w_c * max(0.0, 1.0 - psi ** ta) ** tb
        if w_prev is not None:
            w = max(w, w_prev * math.exp(-step / TIP_DECAY))
        w = max(w, W_MIN)
        w_prev = w
        t = float(t_of_w(w))
        g = float(smooth01(s_ar / L_tw))
        theta = th0 + g * (delta + (phi - phi0))
        # extent toward the bend centre with the section as it sits now
        x, y = section(n, w, t, wrap, k_in, t_rim)
        al = phi - theta
        ext = float(np.max(x * math.sin(al) + y * math.cos(al)))
        relax_tip = prm.get('tip_relax', True) and w < TIP_W and psi > 0.6
        R_fl = max(TIP_R_MIN if relax_tip else R_MIN, R_PER_W * w)
        k_cap = min(prm['rho'] / max(ext, 1e-6), 1.0 / R_fl)
        k_t = min(k_c * (w_c / w) ** prm['exp'] if s_ar > L_in else k_c, k_cap)
        ku = (1.0 - r) * k0u + r * k_t * math.cos(phi)
        kv = (1.0 - r) * k0v + r * k_t * math.sin(phi)
        km = math.hypot(ku, kv)
        if km > k_cap:
            ku, kv, km = ku * k_cap / km, kv * k_cap / km, k_cap
        if sgn_pitch:
            beta = 0.5 * math.asin(min(1.0, h_pitch * km / math.pi)) * r
            phi += sgn_pitch * km * math.tan(beta) * step
        Kv = ku * U + kv * V
        ang = km * step
        if ang > 1e-12:
            ax = _unit(np.cross(T, Kv))
            T1, U1, V1 = _rot(T, ax, ang), _rot(U, ax, ang), _rot(V, ax, ang)
        else:
            T1, U1, V1 = T, U, V
        P = P + 0.5 * (T + T1) * step
        T, U, V = _unit(T1), U1, V1
        U = _unit(U - np.dot(U, T) * T)
        V = np.cross(T, U)
        turned += ang
        for k, v in (('P', P), ('T', T), ('U', U), ('V', V), ('theta', theta), ('w', w), ('t', t),
                     ('wrap', wrap), ('psi', psi)):
            out[k].append(v)
        if turn_in is not None and psi >= 1.0:
            break
    else:
        raise HairKernelError(f'{name}: the curl did not close (check radius / taper)')
    return {k: np.array(v) for k, v in out.items()}


# ---------------------------------------------------------------- split tips
def split(at=0.75, shares=(0.6, 0.4), diverge=7.0, lengths=(1.0, 0.8)):
    """Parameters of split tips (strand(split=...)): at arc fraction `at` of the
    whole strand the section is cut into len(shares) sub-blades across its width
    (shares from the -B rim to the +B rim), which fan out by `diverge` deg between
    neighbours (ramped in, C2) and run lengths x the remaining length along the
    strand's path, each closing to its own blade tip. They share the split ring,
    so the lock stays one island."""
    shares = tuple(float(x) for x in shares)
    lengths = tuple(float(x) for x in lengths)
    if len(shares) < 2 or len(shares) != len(lengths) or abs(sum(shares) - 1.0) > 1e-6:
        raise HairKernelError('split: shares (summing to 1) and lengths, one per sub-tip, at least two')
    if not 0.3 <= at <= 0.95 or not 0.0 <= diverge <= 20.0:
        raise HairKernelError(f'split: at {at} (0.3-0.95), diverge {diverge} deg (0-20)')
    return {'at': float(at), 'shares': shares, 'diverge': float(diverge), 'lengths': lengths}


_curl_spec, _split_spec = curl, split     # (strand()'s parameters shadow the names)


# ---------------------------------------------------------------- rings
def _place_rings(s, T, theta, w, i0, i1, tipzone):
    """Ring stations among samples i0 .. i1 (both included as stations). Turn and
    twist are accumulated sample by sample (an S-bend inside one gap counts)."""
    out = [i0]
    j = i0
    dots = np.clip(np.sum(T[1:] * T[:-1], 1), -1.0, 1.0)
    cturn = np.concatenate([[0.0], np.cumsum(np.arccos(dots))]).tolist()
    ctw = np.concatenate([[0.0], np.cumsum(np.abs(np.diff(theta)))]).tolist()
    hard = math.radians(RING_HARD)
    while j < i1:
        choose, last_ok, wanted, hard_stop = None, None, False, False
        for i in range(j + 1, i1 + 1):
            ds = s[i] - s[j]
            turn = cturn[i] - cturn[j]
            tw = ctw[i] - ctw[j]
            wr = max(w[i] / w[j], w[j] / w[i])
            if i > j + 1 and (turn > hard or tw > hard or wr > RING_HARD_WRATIO):
                hard_stop = True
                break
            last_ok = i
            gap = RING_GAP_TIP if tipzone[i] else max(RING_GAP, RING_GAP_W * w[i])
            want = (ds >= min(RING_ARC, RING_ARC_W * w[i]) or turn >= math.radians(RING_TURN)
                    or tw >= math.radians(RING_TWIST) or wr >= RING_WRATIO)
            wanted = wanted or want
            if wanted and ds >= gap:
                choose = i
                break
        if choose is None:
            # the floor was not reached before a hard limit (or the end): the last
            # sample within the hard limits; reaching the end with no ring wanted
            # ends the placement
            choose = last_ok if (wanted or hard_stop) else i1
        if choose >= i1:
            break
        out.append(choose)
        j = choose
    if out[-1] != i1:
        # the final station: drop a ring sitting too close in front of it
        if len(out) > 1 and s[i1] - s[out[-1]] < 0.5 * RING_GAP_TIP:
            out.pop()
        out.append(i1)
    return out


# ---------------------------------------------------------------- strands
class Strand:
    """One built tube (numpy only; emit() writes it into a BMesh).

    name, n (vertices per ring), rings (R, n, 3), centres / T / N / B (R, 3) at
    the ring stations, arc (R,) m from the root, width / thick (R,), u (n,) UV
    across, v (R,) UV along, grad (R, n) toon_grad, attrs {name: (R, n)},
    apex (3,) or None (a split strand ends at its split ring; its sub-tips
    continue it), length (m), tips [Strand] (sub-tips: their ring 0 is
    the parent's last ring at parent_idx), curve (dict of the dense samples:
    P, s, T, N, B, w, t), meta (dict: curl / split arcs, overlap ...), flip
    (faces reversed: a mirrored strand)."""

    def __init__(self, **kw):
        self.tips = []
        self.parent_idx = None
        self.apex = None
        self.flip = False
        self.meta = {}
        self.attrs = {}
        self.__dict__.update(kw)

    def face_count(self):
        """Faces emit() makes for this strand and its sub-tips."""
        R, n = self.rings.shape[:2]
        f = (R - 1) * n
        if self.parent_idx is None:
            f += n // 2 - 1
        if self.apex is not None:
            f += n
        return f + sum(t.face_count() for t in self.tips)

    def at(self, u):
        """Centreline frame at arc fraction u of the whole strand (the parent's
        path past a split): dict P, T, N, B (3,) and w, t (m)."""
        c = self.curve
        sa = float(np.clip(u, 0.0, 1.0)) * (c['s'][-1] - c['s'][0]) + c['s'][0]
        f = {k: np.array([np.interp(sa, c['s'], c[k][:, i]) for i in range(3)]) for k in ('P', 'T', 'N')}
        T = _unit(f['T'])
        N = _unit(f['N'] - np.dot(f['N'], T) * T)
        return {'P': f['P'], 'T': T, 'N': N, 'B': np.cross(T, N),
                'w': float(np.interp(sa, c['s'], c['w'])), 't': float(np.interp(sa, c['s'], c['t']))}

    def surface(self, u, s=0.0, face='top'):
        """A point on the strand's outer ('top') or under ('under') face at arc
        fraction u and across parameter s (-1 .. 1, rim to rim along +B)."""
        f = self.at(u)
        wrap = float(np.interp(float(np.clip(u, 0, 1)) * self.curve['s'][-1], self.curve['s'], self.curve['wrap']))
        x, y = section(2, f['w'], f['t'], wrap, self.meta['k_in'], self.meta['t_rim'],
                       s=np.array([s, s]), top=np.array([True, False]))
        k = 0 if face == 'top' else 1
        return f['P'] + x[k] * f['B'] + y[k] * f['N']

    def all_tubes(self):
        """This strand and its sub-tips, depth first."""
        out = [self]
        for t in self.tips:
            out += t.all_tubes()
        return out

    def triangles(self):
        """(F, 3, 3) triangles of the closed surface (quads split), for ray tests."""
        tris = []
        for tb in self.all_tubes():
            R = tb.rings
            n = R.shape[1]
            for j in range(len(R) - 1):
                a, b = R[j], R[j + 1]
                a1, b1 = np.roll(a, -1, axis=0), np.roll(b, -1, axis=0)
                tris.append(np.stack([a, a1, b1], 1))
                tris.append(np.stack([a, b1, b], 1))
            if tb.parent_idx is None:
                r0 = R[0]
                for k in range(n // 2 - 1):
                    tris.append(np.stack([r0[[k]], r0[[k + 1]], r0[[n - 2 - k]]], 1))
                    tris.append(np.stack([r0[[k]], r0[[n - 2 - k]], r0[[n - 1 - k]]], 1))
            if tb.apex is not None:
                a = R[-1]
                tris.append(np.stack([a, np.roll(a, -1, axis=0), np.tile(tb.apex, (n, 1))], 1))
        return np.concatenate(tris, 0)


def _settings(width, thick, aspect, swell, tip, wrap, k_in, t_rim, n, has_curl):
    if tip == 'auto':
        tip = None if has_curl else TIP
    if callable(width):
        wfun = _as_fn(width, 'width')
        w_max = float(np.max(wfun(np.linspace(0.0, 1.0, 201))))
    else:
        w_max = float(width)
        wfun = lambda u: w_max * taper(u, swell, tip)   # noqa: E731
    if w_max <= 0:
        raise HairKernelError('width must be > 0')
    t_mid = float(thick) if thick is not None else w_max / float(aspect)
    return {
        'wfun': wfun, 'w_max': w_max, 't_mid': t_mid,
        'tfun': lambda w: thickness(w, t_mid, w_max),
        'wrapfun': _as_fn(wrap, 'wrap'), 'k_in': float(k_in), 't_rim': float(t_rim),
        'n': int(n) if n else ring_count(w_max),
    }


def strand(points, *, width, facing, name='strand', thick=None, aspect=3.0, mode='interp', alpha=1.0,
           anchors=(), tangents=(None, None), swell=SWELL, tip='auto', wrap=WRAP, k_in=K_IN, t_rim=T_RIM,
           n=None, curl=None, split=None, lift=None, grad=None, attrs=None, r_min=R_MIN, rho_max=RHO_MAX,
           twist_rate=TWIST_RATE, facing_smooth=FACING_SMOOTH, step=STEP, check=True):
    """Build one hair strand (a closed crescent tube) and return a Strand.

    points / mode / alpha / anchors / tangents: the centreline (centreline()).
    width: maximum full width (m), shaped by taper(u, swell, tip) along the spine
      (tip='auto': TIP, or none when the strand ends in a curl, which closes it),
      or a callable w(u) (u = arc fraction of the spine).
    thick: total thickness at the widest point (m), else width / aspect
      (bangs 3-5, side locks 2-3, back primaries 2.5-3.5, curl blades 4-6);
      along the strand t = thick (w / w_max)^1.4, >= 1 mm.
    facing: the outer face's direction (module docstring).
    wrap / k_in / t_rim: the crescent (section()); wrap may be (root, tip) or
      a callable of u. n: vertices around (default 12 / 14 / 16 by width).
    curl: curl(...) parameters, grown from the spine's end (G2).
    split: split(...) parameters (sub-tips at an arc fraction of the whole).
    lift: callable(u) or array over u in 0..1: the spine's centreline is moved
      out along its section normal by this much (m) -- rest_on() makes it.
    grad: toon_grad, None (0), (u0, u1) (smoothstep over the whole strand's arc
      fraction) or a callable(p, u) -> 0..1 per vertex.
    attrs: {layer name: float or callable(p, u)} extra per-vertex float layers.
    r_min / rho_max / twist_rate / facing_smooth: the limits (module constants).
    check: run validate() (raises HairKernelError naming the strand)."""
    cfg = _settings(width, thick, aspect, swell, tip, wrap, k_in, t_rim, n, curl is not None)
    wfun, tfun, wrapfun, nn = cfg['wfun'], cfg['tfun'], cfg['wrapfun'], cfg['n']
    has_curl = curl is not None
    # narrow tips may bend tighter (TIP_R_MIN) -- but not on a parent path that
    # splits: its sub-tips run beside that path, the inner one on a tighter turn
    tz = 0.0 if (has_curl or split is not None) else TIP_ZONE
    km_base = _kmax_fn(wfun, None, r_min, rho_max, tz)
    spine = relax(_spline_curve(points, anchors, tangents, mode, alpha, step),
                  lambda u: 0.98 * km_base(u), name=name)
    lifted = lift is None
    for it in range(6):
        u = spine.u
        w = wfun(u)
        t = tfun(w)
        fr = frames(spine, facing, twist_rate=twist_rate, smooth=facing_smooth)
        if not lifted:
            lv = lift(u) if callable(lift) else np.interp(u, np.linspace(0, 1, len(lift)), np.asarray(lift, float))
            spine = Curve(spine.P + fr['N'] * np.asarray(lv, float)[:, None], spine.fixed)
            lifted = True
            continue
        x, y = section(nn, w, t, wrapfun(u), cfg['k_in'], cfg['t_rim'])
        kap = spine.kappa
        d = spine.K / np.maximum(kap, 1e-12)[:, None]
        ext = _extent(x, y, np.sum(d * fr['B'], 1), np.sum(d * fr['N'], 1))
        km = np.minimum(km_base(u), rho_max / np.maximum(ext, 1e-6))
        if np.all(kap <= km):
            break
        spine = relax(spine, 0.98 * km, name=name)
    else:
        raise HairKernelError(f'{name}: the spine did not settle within its curvature limits')
    # ---- assemble the dense samples (spine + curl)
    D = {'P': spine.P, 'T': spine.T, 'N': fr['N'], 'B': fr['B'], 'U': fr['U'], 'V': fr['V'],
         'theta': fr['theta'], 'w': w, 't': t, 'wrap': wrapfun(u)}
    s_spine = spine.length
    meta = {'spine_len': s_spine}
    if has_curl:
        prm = curl if isinstance(curl, dict) else _curl_spec(**curl)
        end = {'P': spine.P[-1], 'T': spine.T[-1], 'U': fr['U'][-1], 'V': fr['V'][-1],
               'K': spine.K[-2], 'theta': fr['theta'][-1], 'w': w[-1], 'wrap': D['wrap'][-1]}
        sec = {'n': nn, 'k_in': cfg['k_in'], 't_rim': cfg['t_rim']}
        C = _grow_curl(end, dict(prm, tip_relax=split is None), sec, tfun, step, name)
        C['N'] = np.cos(C['theta'])[:, None] * C['U'] + np.sin(C['theta'])[:, None] * C['V']
        C['B'] = np.cross(C['T'], C['N'])
        for k in D:
            D[k] = np.concatenate([D[k], C[k]], 0)
        meta['curl'] = prm
    P = D['P']
    s = np.concatenate([[0.0], np.cumsum(_norm(np.diff(P, axis=0)))])
    L = float(s[-1])
    ut = s / L
    meta['length'] = L
    if has_curl:
        meta['curl_from'] = s_spine
    W = np.maximum(limit_decay(D['w'], s), W_MIN)
    D['w'] = W
    D['t'] = np.asarray(tfun(W), float)
    tipzone = (ut > 1.0 - TIP_ZONE) & (W < TIP_W)
    M = len(P)
    # ---- split station
    sp = None
    if split is not None:
        sp = split if isinstance(split, dict) else _split_spec(**split)
        i_sp = int(np.argmin(np.abs(s - sp['at'] * L)))
        if i_sp >= M - 3:
            raise HairKernelError(f'{name}: split at {sp["at"]} leaves no tip')
        last = i_sp
    else:
        last = _tip_station(s, W, P)
    idx = _place_rings(s, D['T'], D['theta'], W, 0, last, tipzone)
    ridx = np.array(idx)
    s_par, top = ring_params(nn)
    s_ring = np.tile(s_par, (len(ridx), 1))
    if sp is not None:
        # slide the columns sideways over the last stretch before the split, so
        # a cut column lands exactly at each share (cos spacing is sparse mid-width)
        cols, warp = _split_columns(nn, sp['shares'], name)
        cut_s = [float(warp(s_par[c])) for c in cols[1:-1]]
        L_w = max(0.008, 0.5 * float(W[i_sp]))
        b = smooth01((s[ridx] - (s[i_sp] - L_w)) / L_w)[:, None]
        s_ring = s_par + b * (warp(s_par) - s_par)
    x, y = section(nn, W[ridx], D['t'][ridx], D['wrap'][ridx], cfg['k_in'], cfg['t_rim'], s=s_ring, top=top)
    if sp is not None:
        # pinch the cut columns as the split nears, so each sub-blade leaves with a thin rim
        mid = -D['wrap'][ridx][:, None] * 0.5 * W[ridx][:, None] * s_ring * s_ring
        y = mid + (y - mid) * _groove(s_ring, cut_s, b)
    rings = (P[ridx][:, None, :] + x[..., None] * D['B'][ridx][:, None, :]
             + y[..., None] * D['N'][ridx][:, None, :])
    uu = 0.5 * (s_par + 1.0)
    st = Strand(name=name, n=nn, rings=rings, centres=P[ridx].copy(), T=D['T'][ridx].copy(),
                N=D['N'][ridx].copy(), B=D['B'][ridx].copy(), arc=s[ridx].copy(), width=W[ridx].copy(),
                thick=D['t'][ridx].copy(), u=uu, v=ut[ridx].copy(), length=L, meta=meta,
                curve={'P': P, 's': s, 'T': D['T'], 'N': D['N'], 'B': D['B'], 'w': W, 't': D['t'],
                       'theta': D['theta'], 'wrap': D['wrap']})
    meta['k_in'], meta['t_rim'] = cfg['k_in'], cfg['t_rim']
    if sp is None:
        st.apex = P[-1].copy()
    else:
        meta['split'] = dict(sp, arc=float(s[i_sp]))
        st.tips = _split_tips(st, D, s, i_sp, sp, cfg, s_ring[-1], top, cols, name)
    for tb in st.all_tubes():
        _paint(tb, grad, attrs, L)
    if check:
        validate(st)
    return st


def _tip_station(s, W, P):
    """The last ring before the apex: TIP_POINT x its width (at least
    RING_GAP_TIP) from the end, so the fan closes in a point, not a stub; but
    within 0.32 R of it in a tight curl, so the apex stays on the curve's turn."""
    rem = s[-1] - s
    kap = np.maximum.accumulate(Curve(P).kappa[::-1])[::-1]     # the tightest bend still ahead
    want = np.minimum(TIP_POINT * W, 0.32 / np.maximum(kap, 1e-9))
    ok = np.flatnonzero(rem >= np.maximum(RING_GAP_TIP, want))
    return int(ok[-1]) if len(ok) and ok[-1] > 0 else len(s) - 2


def _groove(sv, cuts, depth):
    """Half-thickness factor pinching a split's cut columns (sv: across parameters,
    cuts: their s, depth 0..1 of the full pinch to GROOVE_KEEP)."""
    g = np.ones_like(np.asarray(sv, float))
    for c in cuts:
        g = g - np.asarray(depth) * (1.0 - GROOVE_KEEP) * np.exp(-0.5 * ((sv - c) / GROOVE_SIGMA) ** 2)
    return np.clip(g, GROOVE_KEEP, 1.0)


def _split_columns(n, shares, name):
    """Top-face columns bounding each sub-tip ([0, c1, .., n/2-1]) and the warp
    of the across parameter s that moves each cut column exactly to its share."""
    s_par, _ = ring_params(n)
    h = n // 2
    s_top = s_par[:h]
    span = s_top[-1] - s_top[0]
    targets = [s_top[0] + c * span for c in np.cumsum(shares)[:-1]]
    cuts = [int(np.argmin(np.abs(s_top - x))) for x in targets]
    cols = [0] + cuts + [h - 1]
    if any(b - a < 2 for a, b in zip(cols, cols[1:])):
        raise HairKernelError(f'{name}: split shares {tuple(shares)} leave a sub-tip under 3 columns '
                              f'of the {n}-vertex ring: use fewer sub-tips or a wider strand (n)')
    xp = np.array([s_top[0]] + [s_top[c] for c in cuts] + [s_top[-1]])
    fp = np.array([s_top[0]] + targets + [s_top[-1]])
    if np.any(np.diff(fp) <= 0):
        raise HairKernelError(f'{name}: split shares {tuple(shares)} out of order')
    return cols, lambda sv: np.interp(sv, xp, fp)


def _split_tips(st, D, s, i_sp, sp, cfg, s_last, top, cols, name):
    """Sub-tips continuing the strand from its last ring (at sample i_sp, whose
    vertices sit at the across parameters s_last)."""
    n = st.n
    h = n // 2
    s_par = s_last
    s_top = s_par[:h]
    W, P, Bv, Nv = D['w'], D['P'], D['B'], D['N']
    Kp = Curve(P).K
    w_p0, wrap0 = W[i_sp], D['wrap'][i_sp]
    L_rem = s[-1] - s[i_sp]
    k = len(sp['shares'])
    tips = []
    for j, (lo, hi) in enumerate(zip(cols, cols[1:])):
        pidx = list(range(lo, hi + 1)) + list(range(n - 1 - hi, n - lo))
        sp_lo, sp_hi = s_top[lo], s_top[hi]
        share = (sp_hi - sp_lo) / (s_top[-1] - s_top[0])
        smid = 0.5 * (sp_lo + sp_hi)
        x0 = 0.5 * w_p0 * smid
        y0 = -wrap0 * 0.5 * w_p0 * smid * smid
        ang = math.radians(sp['diverge'] * (j - 0.5 * (k - 1)))
        L_j = sp['lengths'][j] * L_rem
        sl = s[i_sp:] - s[i_sp]
        m = int(np.searchsorted(sl, L_j)) + 1
        m = max(4, min(m, len(sl)))
        ii = np.arange(i_sp, i_sp + m)
        d = sl[:m]
        L_j = float(d[-1])
        w_j0 = share * w_p0
        # the sub-tips fan out by `diverge` and then run on side by side (a smoothstep
        # offset whose steepest slope is the divergence angle), never toward the
        # centre of a bend in the width plane (an inner tip would fold there)
        L_s = min(L_j, 3.0 * w_j0 + 0.010)
        D_off = math.tan(ang) * L_s / 1.5
        kB = float(np.mean(np.sum(Kp[ii] * Bv[ii], 1)))
        if D_off * kB > 0 and abs(kB) * L_j > 0.2:
            D_off = 0.0
        xo = x0 + D_off * smooth01(d / L_s)
        Q = P[ii] + Bv[ii] * xo[:, None] + Nv[ii] * y0
        # per-sample parent values along the tip, and the tip's own width / thickness
        Wp, tp, wrp, Np, thq = W[ii], D['t'][ii], D['wrap'][ii], Nv[ii], D['theta'][ii]
        wq = share * np.interp(s[i_sp] + d * (L_rem / max(L_j, 1e-9)), s, D['w'])
        wq = np.maximum(limit_decay(wq, d), W_MIN)
        sv = np.concatenate([s_par[lo:hi + 1], s_par[n - 1 - hi:n - lo]])
        tv = np.concatenate([top[lo:hi + 1], top[n - 1 - hi:n - lo]])
        sl_loc = 2.0 * (sv - sp_lo) / (sp_hi - sp_lo) - 1.0
        # the offset path is longer outside a bend and shorter inside: resample it
        # evenly (half steps: a tip is short and may bend tighter than its parent)
        c0 = Curve(Q)
        Q, _ = _hermite_resample(Q, np.zeros(len(Q), bool), 0.5 * STEP)
        u_new = Curve(Q).u
        Wp, tp, wrp, thq, wq = (np.interp(u_new, c0.u, a) for a in (Wp, tp, wrp, thq, wq))
        Np = np.stack([np.interp(u_new, c0.u, Np[:, c]) for c in range(3)], 1)
        d = Curve(Q).s
        L_j = float(d[-1])
        # an inner tip runs on a tighter path than its parent: hold it to the limits
        # the rings need (R >= TIP_R_MIN, rho), start held for G1 with the split
        for _ in range(3):
            cq = Curve(Q)
            Tq = cq.T
            Nq = _unit(Np - np.sum(Np * Tq, 1)[:, None] * Tq)
            Bq = np.cross(Tq, Nq)
            xb, yb = _tip_sections(sv, tv, sl_loc, sp_lo, sp_hi, s_top, x0, y0, Wp, tp, wrp, wq, d, w_j0, cfg, L_j)
            kap = cq.kappa
            dh = cq.K / np.maximum(kap, 1e-12)[:, None]
            ext = _extent(xb, yb, np.sum(dh * Bq, 1), np.sum(dh * Nq, 1))
            Rf = np.maximum(TIP_R_MIN, R_PER_W * wq)
            km = np.minimum(1.0 / Rf, RHO_MAX / np.maximum(ext, 1e-6))
            if np.all(kap <= km):
                break
            fx = np.zeros(len(Q), bool)
            fx[:2] = True
            try:
                c2 = relax(Curve(Q, fx), 0.98 * km, name=f'{name}.tip{j}')
            except HairKernelError as e:
                raise HairKernelError(
                    f'{name}: sub-tip {j} (share {share:.2f}) cannot follow the strand past the split at '
                    f'{1000 * s[i_sp]:.0f} mm: beside the centreline its path bends tighter than its own '
                    f'limits ({e}). Split earlier or later, narrow the split strand there, or open that '
                    'bend') from None
            u_old, u_new = cq.u, c2.u
            Q = c2.P
            Wp, tp, wrp, thq, wq = (np.interp(u_new, u_old, a) for a in (Wp, tp, wrp, thq, wq))
            Np = np.stack([np.interp(u_new, u_old, Np[:, c]) for c in range(3)], 1)
            d = c2.s
            L_j = float(d[-1])
        cq = Curve(Q)
        Tq = cq.T
        Nq = _unit(Np - np.sum(Np * Tq, 1)[:, None] * Tq)
        Bq = np.cross(Tq, Nq)
        tq = cfg['tfun'](wq)
        tipz = (d / max(L_j, 1e-9) > 0.6) & (wq < TIP_W)
        loc = _place_rings(cq.s, Tq, thq, wq, 0, _tip_station(cq.s, wq, Q), tipz)
        g = np.array(loc)
        xs, ys = _tip_sections(sv, tv, sl_loc, sp_lo, sp_hi, s_top, x0, y0, Wp[g], tp[g], wrp[g], wq[g], d[g],
                               w_j0, cfg, L_j)
        rings = Q[g][:, None, :] + xs[..., None] * Bq[g][:, None, :] + ys[..., None] * Nq[g][:, None, :]
        rings[0] = st.rings[-1][pidx]
        tip = Strand(name=f'{name}.tip{j}', n=len(pidx), rings=rings, centres=Q[g].copy(), T=Tq[g].copy(),
                     N=Nq[g].copy(), B=Bq[g].copy(), arc=s[i_sp] + d[g], width=wq[g].copy(),
                     thick=tq[g].copy(), u=0.5 * (sv + 1.0), v=(s[i_sp] + d[g]) / s[-1], length=L_j,
                     curve={'P': Q, 's': s[i_sp] + d, 'T': Tq, 'N': Nq, 'B': Bq, 'w': wq, 't': tq, 'wrap': wrp,
                            'theta': thq},
                     meta={'share': float(share), 'k_in': cfg['k_in'], 't_rim': cfg['t_rim']})
        tip.parent_idx = pidx
        tip.apex = Q[-1].copy()
        tip.v_apex = float((s[i_sp] + L_j) / s[-1])
        tips.append(tip)
    return tips


def _tip_sections(sv, tv, sl_loc, sp_lo, sp_hi, s_top, x0, y0, Wp, tp, wrp, wq, d, w_j0, cfg, L_j):
    """A sub-tip's sections (x, y about its own centreline): the parent's portion
    (grooved at the cut) blending into the sub-blade's own crescent over
    max(6 mm, 1.2 w) after the split (at most half the tip)."""
    xa, ya = section(len(sv), Wp, tp, wrp, cfg['k_in'], cfg['t_rim'], s=sv, top=tv)
    ga = _groove(sv, [c for c in (sp_lo, sp_hi) if s_top[0] < c < s_top[-1]], 1.0)
    mida = -np.asarray(wrp)[:, None] * 0.5 * np.asarray(Wp)[:, None] * sv * sv
    ya = mida + (ya - mida) * ga - y0
    xa = xa - x0
    xb, yb = section(len(sv), wq, cfg['tfun'](wq), wrp, cfg['k_in'], cfg['t_rim'], s=0.98 * sl_loc, top=tv)
    bl = smooth01(np.asarray(d) / min(max(0.006, 1.2 * w_j0), 0.5 * L_j))[:, None]
    return (1.0 - bl) * xa + bl * xb, (1.0 - bl) * ya + bl * yb


def _paint(tb, grad, attrs, L):
    """toon_grad and extra attributes per vertex of a tube."""
    R, n = tb.rings.shape[:2]
    ua = np.repeat((tb.arc / L)[:, None], n, 1)
    ue = float(getattr(tb, 'v_apex', 1.0))
    if grad is None:
        tb.grad = np.zeros((R, n))
        tb.grad_apex = 0.0
    elif callable(grad):
        tb.grad = np.array([[float(grad(tb.rings[j, k].copy(), ua[j, k])) for k in range(n)] for j in range(R)])
        tb.grad_apex = float(grad(tb.apex.copy(), ue)) if tb.apex is not None else 0.0
    else:
        g0, g1 = grad
        tb.grad = smooth01((ua - g0) / max(g1 - g0, 1e-9))
        tb.grad_apex = float(smooth01((ue - g0) / max(g1 - g0, 1e-9)))
    tb.grad = np.clip(tb.grad, 0.0, 1.0)
    tb.attrs, tb.attrs_apex = {}, {}
    for key, val in (attrs or {}).items():
        if callable(val):
            tb.attrs[key] = np.array([[float(val(tb.rings[j, k].copy(), ua[j, k])) for k in range(n)]
                                      for j in range(R)])
            tb.attrs_apex[key] = float(val(tb.apex.copy(), ue)) if tb.apex is not None else 0.0
        else:
            tb.attrs[key] = np.full((R, n), float(val))
            tb.attrs_apex[key] = float(val)


# ---------------------------------------------------------------- validation
def _min_rot(a, b):
    """Matrix of the minimal rotation taking unit a to unit b."""
    v = np.cross(a, b)
    c = float(np.dot(a, b))
    if c < -0.9999:
        o = np.array([1.0, 0.0, 0.0]) if abs(a[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
        v = _unit(np.cross(a, o))
        return 2.0 * np.outer(v, v) - np.eye(3)
    vx = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + vx + vx @ vx / (1.0 + c)


def _tube_metrics(tb):
    R = tb.rings
    C = tb.centres
    nr = len(R)
    d = np.diff(C, axis=0)
    seg = _norm(d)
    du = d / np.maximum(seg, 1e-15)[:, None]
    turn = np.degrees(np.arccos(np.clip(np.sum(du[1:] * du[:-1], 1), -1.0, 1.0)))   # at stations 1..
    kap = np.radians(turn) / np.maximum(0.5 * (seg[1:] + seg[:-1]), 1e-12)
    pn = _unit(du[1:] - du[:-1])
    rho = np.zeros(len(turn))
    for i in range(len(turn)):
        j = i + 1
        if j < nr and turn[i] > 1e-6:
            rho[i] = kap[i] * float(np.max((R[j] - C[j]) @ pn[i]))
    fold = 0
    where_fold = []
    for j in range(nr - 1):
        tm = _unit(C[j + 1] - C[j])
        adv = (R[j + 1] - R[j]) @ tm
        nf = int((adv <= 0).sum())
        if nf:
            where_fold.append(j)
        fold += nf
    tw = []
    for j in range(1, nr):
        n0 = _min_rot(_unit(tb.T[j - 1]), _unit(tb.T[j])) @ tb.N[j - 1]
        n0 = _unit(n0 - np.dot(n0, tb.T[j]) * tb.T[j])
        n1 = tb.N[j]
        tw.append(math.degrees(math.atan2(float(np.dot(np.cross(n0, n1), tb.T[j])), float(np.dot(n0, n1)))))
    tw = np.abs(np.array(tw)) if tw else np.zeros(0)
    wr = tb.width[1:] / np.maximum(tb.width[:-1], 1e-12)
    gaps = _norm(np.diff(C, axis=0))
    apex = 0.0
    if tb.apex is not None:
        apex = math.degrees(math.acos(float(np.clip(np.dot(_unit(tb.apex - C[-1]), _unit(tb.T[-1])), -1, 1))))
    return {'turn': turn, 'rho': rho, 'fold': fold, 'fold_at': where_fold, 'twist': tw,
            'wratio': wr, 'gap': gaps, 'apex': apex}


def validate(st, limits=None, raise_=True):
    """Check every tube of a Strand against LIMITS (turn per ring, rho, folded
    quads, twist per ring, width ratio per ring except the last two, ring
    spacing). Returns a summary dict; with raise_ a violation raises
    HairKernelError listing each one with the tube name, ring, arc and point."""
    lim = dict(LIMITS, **(limits or {}))
    errs = []
    summ = {'rings': 0, 'faces': st.face_count(), 'max_turn': 0.0, 'max_rho': 0.0, 'folds': 0,
            'max_twist': 0.0, 'wratio': [1.0, 1.0], 'max_gap': 0.0, 'min_gap': 1.0}
    for tb in st.all_tubes():
        m = _tube_metrics(tb)
        summ['rings'] += len(tb.rings)

        def where(j):
            j = min(max(j, 0), len(tb.centres) - 1)
            return (f'{tb.name} ring {j}/{len(tb.rings)} at {1000 * tb.arc[j]:.0f} mm '
                    f'{np.round(tb.centres[j], 4).tolist()}')
        if len(m['turn']):
            i = int(np.argmax(m['turn']))
            summ['max_turn'] = max(summ['max_turn'], float(m['turn'][i]))
            if m['turn'][i] > lim['turn']:
                errs.append(f'turn {m["turn"][i]:.1f} deg > {lim["turn"]} at {where(i + 1)}')
            i = int(np.argmax(m['rho']))
            summ['max_rho'] = max(summ['max_rho'], float(m['rho'][i]))
            if m['rho'][i] > lim['rho']:
                errs.append(f'rho {m["rho"][i]:.2f} > {lim["rho"]} at {where(i + 1)}')
        summ['max_apex'] = max(summ.get('max_apex', 0.0), m['apex'])
        if m['apex'] > lim['apex']:
            errs.append(f'apex {m["apex"]:.1f} deg off the last ring\'s tangent > {lim["apex"]} at '
                        f'{where(len(tb.centres) - 1)}')
        summ['folds'] += m['fold']
        if m['fold'] > lim['fold']:
            errs.append(f'{m["fold"]} folded quads, first at {where(m["fold_at"][0])}')
        if len(m['twist']):
            i = int(np.argmax(m['twist']))
            summ['max_twist'] = max(summ['max_twist'], float(m['twist'][i]))
            if m['twist'][i] > lim['twist']:
                errs.append(f'twist {m["twist"][i]:.1f} deg > {lim["twist"]} at {where(i + 1)}')
        wr = m['wratio'][:max(0, len(m['wratio']) - 2)]
        if len(wr):
            summ['wratio'] = [min(summ['wratio'][0], float(wr.min())), max(summ['wratio'][1], float(wr.max()))]
            lo, hi = lim['wratio']
            bad = np.flatnonzero((wr < lo) | (wr > hi))
            if len(bad):
                errs.append(f'width ratio {wr[bad[0]]:.2f} outside {lo}-{hi} at {where(int(bad[0]) + 1)}')
        if len(m['gap']):
            summ['max_gap'] = max(summ['max_gap'], float(m['gap'].max()))
            summ['min_gap'] = min(summ['min_gap'], float(m['gap'].min()))
            i = int(np.argmax(m['gap']))
            if m['gap'][i] > lim['gap']:
                errs.append(f'ring gap {1000 * m["gap"][i]:.1f} mm > {1000 * lim["gap"]:.0f} at {where(i)}')
        if not np.all(np.isfinite(tb.rings)):
            errs.append(f'{tb.name}: non-finite vertices')
    summ['errors'] = errs
    if errs and raise_:
        raise HairKernelError(f'strand {st.name!r} fails the hair kernel limits:\n  ' + '\n  '.join(errs))
    return summ


# ---------------------------------------------------------------- mirroring
def mirrored(st, name=None):
    """A copy of a Strand mirrored across x = 0 (faces reversed so they still
    face out). Names: `name` or the original's with _L/_R swapped."""
    def mx(a):
        a = np.array(a, float, copy=True)
        a[..., 0] *= -1.0
        return a
    nm = name or (st.name[:-2] + {'_L': '_R', '_R': '_L'}[st.name[-2:]] if st.name[-2:] in ('_L', '_R')
                  else st.name + '_M')
    out = Strand(**{k: v for k, v in st.__dict__.items() if k not in ('tips',)})
    out.name = nm
    out.rings, out.centres, out.T, out.N = mx(st.rings), mx(st.centres), mx(st.T), mx(st.N)
    out.B = np.cross(out.T, out.N)
    out.apex = None if st.apex is None else mx(st.apex)
    out.curve = {k: (mx(v) if k in ('P', 'T', 'N') else v) for k, v in st.curve.items()}
    out.curve['B'] = np.cross(out.curve['T'], out.curve['N'])
    out.flip = not st.flip
    out.tips = [mirrored(t, name=f'{nm}.tip{i}') for i, t in enumerate(st.tips)]
    return out


# ---------------------------------------------------------------- shingling
def _line_hits(O, Dn, tris):
    """Signed parameters mu of the lines O + mu Dn (one direction for all
    points) through triangles (F, 3, 3): returns (len(O), F) with NaN for misses."""
    v0, e1, e2 = tris[:, 0], tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0]
    pv = np.cross(Dn, e2)
    det = np.sum(e1 * pv, 1)
    ok = np.abs(det) > 1e-14
    inv = np.where(ok, 1.0 / np.where(ok, det, 1.0), 0.0)
    tv = O[:, None, :] - v0[None]
    uu = np.sum(tv * pv[None], 2) * inv
    qv = np.cross(tv, e1[None])
    vv = np.sum(qv * Dn, 2) * inv
    mu = np.sum(qv * e2[None], 2) * inv
    hit = ok[None] & (uu >= 0) & (vv >= 0) & (uu + vv <= 1)
    return np.where(hit, mu, np.nan)


class Lift:
    """A smooth outward lift of a strand's spine (callable of the arc fraction u,
    pass as strand(lift=...)); overlap = largest share of the strand's width
    resting on the lower layers at any ring, need = the raw per-ring lift."""

    def __init__(self, u, lift, overlap, need):
        self.u_knots, self.values, self.overlap, self.need = u, lift, overlap, need

    def __call__(self, u):
        return np.interp(u, self.u_knots, self.values)


def rest_on(upper, lowers, *, gap=0.00075, smooth=0.02, root_fade=0.0, reach=0.01):
    """How far to lift strand `upper` so its underside rests on the convex top of
    the strands `lowers` plus `gap` (m, 0.5-1 mm).

    For every ring the underside points cast a line along the ring's section
    normal N; the highest lower surface within reach (above the point: at most
    the upper's thickness + reach) sets the lift needed there. The per-ring need
    is dilated and Gaussian-smoothed along the arc (sigma `smooth` m) so the
    lock changes layer in one long, gentle step, faded in from the root over
    root_fade m. Returns a Lift; rebuild with strand(..., lift=lift) (strand_on()
    does both). Spine samples are moved, never mesh vertices."""
    tris = np.concatenate([lo.triangles() for lo in lowers], 0)
    tmin, tmax = tris.min(1), tris.max(1)
    n = upper.n
    under = ~ring_params(n)[1]
    need = np.zeros(len(upper.rings))
    cov = np.zeros(len(upper.rings))
    for j, ring in enumerate(upper.rings):
        q = ring[under]
        Nj = upper.N[j]
        span = float(upper.thick[j]) + reach
        lo_box, hi_box = q.min(0) - span - 0.005, q.max(0) + span + 0.005
        sel = np.all(tmax >= lo_box, 1) & np.all(tmin <= hi_box, 1)
        if not sel.any():
            continue
        mu = _line_hits(q, Nj, tris[sel])
        mu = np.where((mu >= -(gap + 0.003)) & (mu <= span), mu, np.nan)
        has = ~np.all(np.isnan(mu), 1)
        cov[j] = has.mean()
        if has.any():
            need[j] = max(0.0, float(np.nanmax(mu[has])) + gap)
    u = upper.arc / upper.length
    if not upper.tips and upper.apex is not None:
        u = np.append(u, 1.0)
        need = np.append(need, need[-1])
        cov = np.append(cov, cov[-1])
    # smooth along the arc: dilate, then blur; never below the raw need
    su = np.linspace(0.0, 1.0, 401)
    raw = np.interp(su, u, need)
    sig = smooth / upper.length * 400.0
    r = int(math.ceil(1.5 * sig))
    dil = np.array([raw[max(0, i - r):i + r + 1].max() for i in range(len(raw))])
    sm = _blur(dil, sig)
    for _ in range(3):
        sm = _blur(np.maximum(sm, raw), sig)
    sm = np.maximum(sm, raw)
    sm = _blur(sm, 0.25 * sig)
    if root_fade > 0:
        sm *= smooth01(su * upper.length / root_fade)
    return Lift(su, sm, float(cov.max()) if len(cov) else 0.0, need)


def strand_on(lowers, *, gap=0.00075, max_overlap=0.30, smooth=0.02, root_fade=0.0, iters=3, strict=False,
              **kw):
    """strand(**kw) resting on `lowers` (shingled layers): build, measure with
    rest_on(), rebuild lifted, repeat until the underside clears (iters). The
    result's meta holds 'lift_max' (m) and 'overlap' (share of the width over
    the lower layers at the worst ring); strict raises when overlap > max_overlap
    (a lock should cover at most ~30% of its neighbour below)."""
    name = kw.get('name', 'strand')
    st = strand(**kw)
    total = None
    for _ in range(iters):
        lf = rest_on(st, lowers, gap=gap, smooth=smooth, root_fade=root_fade)
        if lf.values.max() < 0.25 * gap:
            break
        total = lf.values if total is None else total + lf.values
        acc = Lift(lf.u_knots, total.copy(), lf.overlap, lf.need)
        st = strand(**dict(kw, lift=acc))
    lf = rest_on(st, lowers, gap=gap, smooth=smooth, root_fade=root_fade)
    st.meta['lift_max'] = 0.0 if total is None else float(total.max())
    st.meta['overlap'] = lf.overlap
    st.meta['residual'] = float(lf.need.max())
    if strict and lf.overlap > max_overlap:
        raise HairKernelError(f'{name}: rests {100 * lf.overlap:.0f}% of its width on the layer below '
                              f'(max {100 * max_overlap:.0f}%): space the locks wider')
    return st


# ---------------------------------------------------------------- emission
def emit(bm, st, *, uv='UVMap', grad_attr=GRAD_ATTR, root_cap=True, _parent=None):
    """Write a Strand (and its sub-tips) into a BMesh: quads along the tube, a
    ladder cap across the root (root_cap), a fan to the apex, toon_grad
    (grad_attr, a float vertex layer), UVs (uv: loop layer name, or None) and
    the strand's attrs (float vertex layers, -1 on vertices made before).
    Faces face outward (reversed for a mirrored strand).
    Returns {'rings': [[BMVert]], 'apex': BMVert or None, 'tips': [...], 'faces': [BMFace]}."""
    glay = bm.verts.layers.float.get(grad_attr) or bm.verts.layers.float.new(grad_attr)
    uvl = None
    if uv:
        uvl = bm.loops.layers.uv.get(uv) or bm.loops.layers.uv.new(uv)
    xl = {}
    for key in st.attrs:
        lay = bm.verts.layers.float.get(key)
        if lay is None:
            lay = bm.verts.layers.float.new(key)
            for v in bm.verts:
                v[lay] = -1.0
        xl[key] = lay
    uvmap = {}
    rings_v = []
    n = st.n
    for j, ring in enumerate(st.rings):
        if j == 0 and _parent is not None:
            vs = [_parent[i] for i in st.parent_idx]
            rings_v.append(vs)
            continue
        vs = []
        for k in range(n):
            v = bm.verts.new(ring[k].tolist())
            v[glay] = float(st.grad[j, k])
            for key, lay in xl.items():
                v[lay] = float(st.attrs[key][j, k])
            vs.append(v)
        rings_v.append(vs)
    for j, vs in enumerate(rings_v):
        for k, v in enumerate(vs):
            uvmap.setdefault(v, (float(st.u[k]), float(st.v[j])))
    faces = []

    def face(vs):
        vs = list(reversed(vs)) if st.flip else vs
        f = bm.faces.new(vs)
        if uvl is not None:
            for lp in f.loops:
                lp[uvl].uv = uvmap.get(lp.vert, (0.5, 1.0))
        faces.append(f)
        return f
    for a, b in zip(rings_v, rings_v[1:]):
        for k in range(n):
            k2 = (k + 1) % n
            face((a[k], a[k2], b[k2], b[k]))
    if root_cap and _parent is None:
        r0 = rings_v[0]
        for k in range(n // 2 - 1):
            face((r0[n - 1 - k], r0[n - 2 - k], r0[k + 1], r0[k]))
    apex_v = None
    if st.apex is not None:
        apex_v = bm.verts.new(st.apex.tolist())
        apex_v[glay] = float(st.grad_apex)
        for key, lay in xl.items():
            apex_v[lay] = float(st.attrs_apex.get(key, 0.0))
        uvmap[apex_v] = (0.5, float(getattr(st, 'v_apex', 1.0)))
        last = rings_v[-1]
        for k in range(n):
            face((last[k], last[(k + 1) % n], apex_v))
    tips = [emit(bm, t, uv=uv, grad_attr=grad_attr, root_cap=False, _parent=rings_v[-1]) for t in st.tips]
    return {'rings': rings_v, 'apex': apex_v, 'tips': tips, 'faces': faces}


__all__ = [
    'HairKernelError', 'Curve', 'Strand', 'Lift', 'LIMITS',
    'centreline', 'relax', 'rmf', 'frames', 'ring_params', 'section', 'taper', 'thickness', 'ring_count',
    'curl', 'split', 'strand', 'strand_on', 'rest_on', 'validate', 'mirrored', 'emit', 'smooth01',
]
