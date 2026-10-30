"""风堇's pelvis and legs on Levi's proportions (round 11): the body's hips, legs and feet.

The source is the asset assets/hyacine/legs.npz (tools/prep_hyacine_legs.py): her tights, one
welded quad mesh from the waist opening down to her ankles (pelvis, buttocks, crotch, both
legs), mirror-exact. It replaces round 10's leg tubes (two lofts pushed 7 cm into a torso
that ended in a brief-shaped block) and the feet nested 4.6 cm into them: the hip collars,
the crotch block and the ankle step are gone; torso, pelvis, legs and feet are one surface.

1. Two Catmull-Clark levels of her cage: the smooth surface everything is sampled from. Her
   thigh rings are ~3 cm apart in 16 columns, and her loops converge on the crotch in slivers.
2. Warp to Levi (`Warp`), evaluated on her points as the part builds them:
   * heights: a monotone cubic through her waist loop, crotch, knee and ankle onto the torso
     ring the pelvis hangs from (WELD_ROW, less TOP_GAP), CROTCH_Z, the round-10 knee pivot
     (body.KNEE_ROW: her kneecap lands on Levi's knee) and the stiletto ankle pivot
     (body.ANKLE_ROW);
   * sections: each horizontal section is scaled about its centre, per direction, by the
     ratio of the low-passed radii (LP_ORDER round the ring, LP_SIGMA along the body) of
     Levi's round-10 surface (target) and hers (source). So Levi's proportions are met at
     those scales (round 10's leg tables, fitted to the sheet, and their shape-master
     correction; round 10's pelvis), while her shorter-scale form survives, scaled with the
     section: kneecap, knee hollow, ankle bones, Achilles tendon, glutes, groin crease. Round
     10's own anatomy offsets (kneecap dome, calf, malleoli) are left out of the leg target:
     hers replace them. The pelvis is scaled about the midline, the legs about their own
     axes; the two blend between LEG_BLEND's heights;
   * her waist loop is levelled and turned onto the torso ring's vertices (TOP_FADE), and the
     pelvis eases onto round 10's torso surface between TOP_BLEND_ROWS, where the petticoat's
     and the skirt's waistbands leave a few mm (her detail stands out of it by at most
     CLOTH_OUT there);
   * her crotch, a ~6 mm gusset between thighs that touch, is widened (CROTCH_GAP): the
     thigh weights change hands across it.
3. A structured "pants" grid is sampled from the warped surface (see H0_UP): pelvis rings
   of the waist loop's 64 columns (horizontal rays from the pelvis centre) down to the ring
   just above the crotch; a chain of CHAIN_M vertices along the midline under the crotch;
   per leg, the ring's half and the chain, one corner quad at the front and one at the back
   of the gusset, and GUSSET_ROWS rows relaxed on the surface down to the first horizontal
   leg ring. Every vertex has valence 4 except the two valence-5 corners per leg in the
   groin. Below, each leg is a loft of rings (LEG_RING_ROWS, ~1 cm through the knee and
   ankle bands) in N_LEG columns evenly spaced round the leg's axis, each vertex the warped
   surface along a horizontal ray from the axis. Below the ankle the loft bends along
   FOOT_PATH into the stiletto foot (rings normal to the path), sampled from round 10's foot
   and ankle (body.FOOT and the leg, which the shoes fit), her ankle fading out over
   HER_ANKLE_ROWS, the old leg / foot crease filled on the instep side only (FOOT_FILL). A
   rounded cap (TOE_CAP) and a pole close the toe.
4. The pelvis' 64-vertex waist loop is bridged to the torso's 32-vertex ring at WELD_ROW by
   one row of quad + triangle pairs (hidden under the bodice and the skirt), mirrored at the
   midline so the body stays mirror-exact; the torso below that ring is dropped
   (body.build_torso itself is unchanged: accessories reads the closed torso).

Exports for the shoes (body.LEG_FRONT / LEG_SIDE / leg_section / leg_offset) are slices of
the final left leg, every panel row of LEG_TABLE_ROWS (`tables`). Rig data (levi_joints):
the knee at KNEE_ROW, the new slice's centre across and round 10's pivot depth (its share of
the leg's depth behind the front skin, measured on round 10's surface); the ankle by round
10's definition; hip and toe stored at round 10's fit (HIP_JOINT, TOE_JOINT).
"""
import math
import os

import bmesh
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

from .. import spec

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ASSET = os.path.join(ROOT, 'assets', 'hyacine', 'legs.npz')
# LEVI_HYACINE_LEGS=0: the round-10 procedural legs and feet (A/B renders)
ENABLED = os.environ.get('LEVI_HYACINE_LEGS', '1') != '0'

PX = 1.0 / spec.PX_PER_M

# ---- seams and landmarks
WELD_ROW = 382.0      # the torso ring (body.TORSO_ROWS) the pelvis hangs from; rings below go
TOP_GAP = 0.011       # m: her waist loop sits this far under that ring (the bridging row)
TOP_FADE = 0.07       # m (hers): her loop's levelling / turning fades out this far below it
# the pelvis eases onto round 10's torso between these rows (all of it above them, where her
# tights' waistband hem lies)
TOP_BLEND_ROWS = (452.0, 410.0)
CROTCH_Z = 0.716      # m: Levi's crotch (round 10's torso bottom ring, row 489)
# m: the pelvis map hands over to the leg map between these heights (none on the midline:
# her crotch apex maps to CROTCH_Z)
LEG_BLEND = (CROTCH_Z - 0.002, CROTCH_Z - 0.07)
# The crotch widened (Warp.__call__): x moves by CROTCH_GAP tanh(x / CROTCH_GAP_W) (m), fading
# out CROTCH_GAP_FALL (m) from the midline, from just under her crotch apex (CROTCH_GAP_Z, m
# about CROTCH_Z: in from above, full, full, out below): her ~6 mm gusset becomes ~2 cm and
# the inner thighs part by ~1 cm, about round 10's thigh gap. Without it the strides tore the
# gusset x2.9; stretched through the pubis too (in from 3 cm above) it folded in a sawtooth.
CROTCH_GAP = 0.011
CROTCH_GAP_W = 0.005
CROTCH_GAP_FALL = (0.03, 0.07)
CROTCH_GAP_Z = (0.008, -0.005, -0.02, -0.075)
# The pelvis and the crotch are a structured "pants" grid sampled from the warped surface
# (round 11 review: her own topology, kept as the first subdivision level, converged on the
# crotch in 1.5 mm slivers round valence-6/7 poles, which crumpled the gusset at rest and
# folded it into a ridge in strides). Rings of the waist loop's 64 columns run down the pelvis
# to the ring at CROTCH_Z + H0_UP, whose midline points F (front) and B (back) end a chain of
# CHAIN_M vertices along the midline under the crotch. Each leg's first loop is the ring's
# half and the chain; one corner quad at F and one at B (valence-5 poles at the groin, off the
# midline) take it to N_LEG columns, and GUSSET_ROWS rows, put on the surface and relaxed
# (GUSSET_RELAX), reach the first horizontal leg ring at GUSSET_END_ROW.
H0_UP = 0.02          # m above CROTCH_Z
PELVIS_STEP = 7.0     # px between the pelvis rings
CLEFT_SOFT = (3, 2.5)     # [1 2 1] passes over the pelvis rings' radii, columns (sigma) round the back
CHAIN_M = 7           # ~1.1 cm along the gusset
N_LEG = 29 + CHAIN_M  # the 31 ring vertices between F and B, the chain, less the two corners
GUSSET_ROWS = 10
GUSSET_END_ROW = 561.0
GUSSET_RELAX = (60, 0.5)   # steps, rate
# then the crotch is rounded (Legs._round_crotch): umbrella steps, rate, the zone's radii (m,
# x / y / z about the crotch apex) and its fade (normalized distance)
CROTCH_ROUND = (12, 0.5, (0.05, 0.065, 0.045), (0.6, 1.0))
# round 10's fitted rig hip and toe (足.L / つま先.L heads, build_rig.log): stored, so the rig
# keeps them (the fit would read the new pelvis' uneven vertex density, and the new foot's
# pole tip, 5 mm past round 10's farthest toe vertex)
HIP_JOINT = (0.071, -0.022824, 0.828608)
TOE_JOINT = (0.027994, -0.132193, 0.012)

# ---- section matching
N_ANG = 72
LP_ORDER = 2                # Fourier terms round the ring kept as "proportions"
LP_SIGMA = {'pelvis': 0.02, 'leg': 0.025}   # m: Gaussian along the body axis
TABLE_STEP = 0.002          # m between table rows
# Under the petticoat's waistband and the skirt's (rows above ~430) the garments leave ~3-5 mm
# (body-contract E3; 17 skin points already poke through the petticoat top in round 10), so
# the pelvis eases onto round 10's surface toward the loop (TOP_BLEND_ROWS) and her detail
# stands out of it by at most CLOTH_OUT (tanh; m, above CLOTH_ROWS[0] .. below [1]). Below,
# the petticoat and the skirt stand 3-10 cm off the hips and thighs: her glutes and thighs
# keep their form (a clamp to round 10's surface there flattened the glutes and printed
# round 10's torso / tube crease onto the groin).
CLOTH_OUT = (0.004, 0.025)
CLOTH_ROWS = (428.0, 456.0)

# ---- leg loft
# rows of the leg rings below GUSSET_END_ROW: ~1.4 cm on the hidden thigh, ~1 cm through
# the knee band the rig bends (rig.JOINT_ALONG, rows ~650-735), ~1.4 cm down the shin,
# ~1.1 cm over the ankle band
LEG_RING_ROWS = (570, 579, 588, 597, 606, 615, 624, 632, 640, 647, 654, 660, 666, 672, 678,
                 684, 690, 696, 702, 708, 714, 720, 727, 734, 742, 751, 760, 769, 778, 787,
                 796, 805, 814, 822, 830, 837, 844, 851)
# The foot: centre line (panel px: x out, y back, row) from the last leg ring's axis through
# the heel bend and down the instep to the toe, inside body.FOOT's sections
FOOT_PATH = ((32.6, -3.0, 857.0), (32.3, -5.0, 866.0), (31.4, -9.5, 876.0),
             (30.4, -15.0, 885.0), (29.2, -21.5, 893.5), (28.0, -28.5, 900.5),
             (27.0, -37.0, 908.5), (26.0, -46.0, 917.0), (24.8, -55.0, 925.5),
             (23.4, -63.5, 932.0), (21.6, -71.5, 936.5), (19.8, -78.5, 939.5),
             (18.4, -84.0, 941.4))
FOOT_STEP = 6.5       # px between foot rings along the path
TOE_TIP = (17.8, -88.4, 942.0)   # px: the path's end (body.FOOT's cap)
# The toe cap: rings at these fractions of the way from the last foot ring to the tip of round
# 10's toe along the path's end tangent (where the pole sits), an ellipsoid through the last
# ring kept inside round 10's toe (review: the pole in the last ring's plane cut it off flat)
TOE_CAP = (0.4, 0.72)
HER_ANKLE_ROWS = (856.0, 872.0)  # her ankle fades into round 10's foot over these rows
FOOT_INSET = 0.3      # px inside round 10's foot / ankle surface (the shoe keeps FOOT_CLEAR)
FOOT_SMOOTH = (1.0, 1.0)   # Gaussian sigma (rings, columns) over the foot's radii
FOOT_FILL = 0.0015    # m the smoothing may move the instep side outward (the creases fill)
FOOT_FILL_ROWS = (885.0, 900.0)   # ... fading out by these rows (the vamp's top line, ~row 915)
LEG_TABLE_ROWS = (455, 878)

_CACHE = {}


def zrow(row):
    return (spec.SHEET_GROUND_Y - np.asarray(row, dtype=np.float64)) * PX


def rowz(z):
    return spec.SHEET_GROUND_Y - np.asarray(z, dtype=np.float64) * spec.PX_PER_M


def _ss(e0, e1, x):
    t = np.clip((np.asarray(x, dtype=np.float64) - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


# ---------------------------------------------------------------- mesh helpers
def asset():
    if 'asset' not in _CACHE:
        z = np.load(ASSET)
        _CACHE['asset'] = {
            'pos': z['pos'].astype(np.float64),
            'faces': [[int(i) for i in f if i >= 0] for f in z['faces']],
            'mirror': z['mirror'].astype(np.int64),
            'waist': [int(i) for i in z['waist']],
            'rings': [[int(i) for i in r if i >= 0] for r in z['rings']],
            'ring_z': z['ring_z'].astype(np.float64),
            'bones': dict(zip([str(b) for b in z['bone_names']], z['bone_head'].astype(np.float64))),
        }
    return _CACHE['asset']


def catmull_clark(P, polys):
    """One Catmull-Clark level (boundaries as creases). Returns (points, quads, edge index
    {(a, b): e} of the input, parent face per quad). New indices: input vertex v -> v, edge
    e -> V + e, face f -> V + E + f."""
    V = len(P)
    eid, E, fe = {}, [], []
    for f in polys:
        ids = []
        for k in range(len(f)):
            a, b = f[k], f[(k + 1) % len(f)]
            key = (a, b) if a < b else (b, a)
            e = eid.get(key)
            if e is None:
                e = eid[key] = len(E)
                E.append(key)
            ids.append(e)
        fe.append(ids)
    E = np.array(E, dtype=np.int64)
    nE, nF = len(E), len(polys)
    FP = np.array([P[f].mean(0) for f in polys])
    fi = np.concatenate([[i] * len(f) for i, f in enumerate(polys)])
    ei = np.concatenate(fe)
    vi = np.concatenate(polys)
    ecnt = np.bincount(ei, minlength=nE)
    fsum = np.zeros((nE, 3))
    np.add.at(fsum, ei, FP[fi])
    mid = (P[E[:, 0]] + P[E[:, 1]]) / 2
    bnd = ecnt == 1
    EP = np.where(bnd[:, None], mid, (P[E[:, 0]] + P[E[:, 1]] + fsum) / 4)
    # vertex points
    val = np.bincount(E.ravel(), minlength=V).astype(np.float64)
    Fs = np.zeros((V, 3))
    np.add.at(Fs, vi, FP[fi])
    Fc = np.bincount(vi, minlength=V).astype(np.float64)
    Rs = np.zeros((V, 3))
    np.add.at(Rs, E[:, 0], mid)
    np.add.at(Rs, E[:, 1], mid)
    n = np.maximum(val, 1.0)[:, None]
    VP = (Fs / np.maximum(Fc, 1)[:, None] + 2 * Rs / n + (n - 3) * P) / n
    Bs = np.zeros((V, 3))
    Bc = np.zeros(V)
    be = E[bnd]
    np.add.at(Bs, be[:, 0], P[be[:, 1]])
    np.add.at(Bs, be[:, 1], P[be[:, 0]])
    np.add.at(Bc, be.ravel(), 1)
    onb = Bc > 0
    VP[onb] = 0.75 * P[onb] + 0.125 * Bs[onb]
    pts = np.concatenate([VP, EP, FP])
    quads, parent = [], []
    for f, (poly, ids) in enumerate(zip(polys, fe)):
        k = len(poly)
        for i in range(k):
            quads.append((poly[i], V + ids[i], V + nE + f, V + ids[i - 1]))
            parent.append(f)
    return pts, np.array(quads, dtype=np.int64), eid, np.array(parent)


def _sub_loop(loop, eid, V):
    """A closed vertex loop of the input mesh after one catmull_clark level."""
    out = []
    for k in range(len(loop)):
        a, b = loop[k], loop[(k + 1) % len(loop)]
        out += [a, V + eid[(a, b) if a < b else (b, a)]]
    return out


def _tree(P, polys):
    return BVHTree.FromPolygons([tuple(p) for p in P], [list(map(int, f)) for f in polys])


def _cast_in(tree, origins, dirs, reach):
    """Distance from each origin to the outermost surface along unit dirs (cast inward from
    origin + dir * reach), NaN on a miss."""
    out = np.full(len(origins), np.nan)
    for i in range(len(origins)):
        rc = float(reach[i])
        if rc <= 1e-6:
            continue
        d = dirs[i]
        hit = tree.ray_cast(Vector(origins[i] + d * rc), Vector(-d), rc)
        if hit[0] is not None:
            out[i] = rc - hit[3]
    return out


def _pchip_slopes(xs, ys):
    h = np.diff(xs)
    d = np.diff(ys) / h
    m = np.empty(len(xs))
    m[0], m[-1] = d[0], d[-1]
    for i in range(1, len(xs) - 1):
        if d[i - 1] * d[i] > 0:
            w1, w2 = 2 * h[i] + h[i - 1], h[i] + 2 * h[i - 1]
            m[i] = (w1 + w2) / (w1 / d[i - 1] + w2 / d[i])
        else:
            m[i] = 0.0
    return m


def _pchip(xs, ys, m, x):
    x = np.asarray(x, dtype=np.float64)
    i = np.clip(np.searchsorted(xs, x) - 1, 0, len(xs) - 2)
    h = xs[i + 1] - xs[i]
    t = (x - xs[i]) / h
    h00, h10 = 2 * t ** 3 - 3 * t ** 2 + 1, t ** 3 - 2 * t ** 2 + t
    h01, h11 = -2 * t ** 3 + 3 * t ** 2, t ** 3 - t ** 2
    y = h00 * ys[i] + h10 * h * m[i] + h01 * ys[i + 1] + h11 * h * m[i + 1]
    lo, hi = x < xs[0], x > xs[-1]
    y = np.where(lo, ys[0] + (x - xs[0]) * m[0], y)
    return np.where(hi, ys[-1] + (x - xs[-1]) * m[-1], y)


class ZMap:
    """Her height -> Levi's: a monotone cubic through the landmark pairs."""

    def __init__(self, her, lev):
        o = np.argsort(her)
        self.x, self.y = np.asarray(her, float)[o], np.asarray(lev, float)[o]
        self.m = _pchip_slopes(self.x, self.y)
        zs = np.linspace(self.x[0] - 0.2, self.x[-1] + 0.2, 4001)
        self._fx, self._fy = zs, self(zs)

    def __call__(self, z):
        return _pchip(self.x, self.y, self.m, z)

    def inv(self, zp):
        return np.interp(zp, self._fy, self._fx)


def _gauss_rows(a, sig):
    """Gaussian smoothing along axis 0 (sig in rows), ends clamped."""
    if sig <= 0:
        return a
    h = max(1, int(math.ceil(3 * sig)))
    k = np.exp(-0.5 * (np.arange(-h, h + 1) / sig) ** 2)
    k /= k.sum()
    idx = np.clip(np.arange(-h, len(a) + h), 0, len(a) - 1)
    pad = a[idx]
    return sum(k[j] * pad[j:j + len(a)] for j in range(2 * h + 1))


def _fill_rows(a):
    """NaN rows of a 2-D table filled by linear interpolation along the rows (ends held)."""
    ok = np.isfinite(a).all(1)
    if ok.all() or not ok.any():
        return a
    i = np.arange(len(a))
    return np.stack([np.interp(i, i[ok], a[ok, j]) for j in range(a.shape[1])], 1)


def _lowpass(R, ang, sig_rows):
    """Per row the Fourier fit (order LP_ORDER) of R round the ring (NaN = no sample), then
    smoothed along the rows."""
    terms = [np.ones_like(ang)]
    for k in range(1, LP_ORDER + 1):
        terms += [np.cos(k * ang), np.sin(k * ang)]
    A = np.stack(terms, 1)
    coef = np.full((len(R), A.shape[1]), np.nan)
    for i, r in enumerate(R):
        ok = np.isfinite(r)
        if ok.mean() < 0.5:
            continue
        Ao = A[ok]
        coef[i] = np.linalg.solve(Ao.T @ Ao + 1e-6 * np.eye(A.shape[1]), Ao.T @ r[ok])
    coef = _gauss_rows(_fill_rows(coef), sig_rows)
    return coef @ A.T


def _fill_ring(r):
    """NaN gaps of a periodic row filled by linear interpolation."""
    ok = np.isfinite(r)
    if ok.all() or not ok.any():
        return r
    n = len(r)
    i = np.arange(n)
    xi = np.concatenate([i[ok] - n, i[ok], i[ok] + n])
    return np.interp(i, xi, np.tile(r[ok], 3))


def _table_at(T, z0, step, zq, angq):
    """Bilinear lookup in a table [rows from z0 down by step, N_ANG periodic angles]."""
    u = np.clip((z0 - zq) / step, 0, len(T) - 1.000001)
    i = u.astype(int)
    fu = u - i
    a = (np.mod(angq, 2 * math.pi) / (2 * math.pi)) * N_ANG
    j = a.astype(int) % N_ANG
    fa = a - np.floor(a)
    j1 = (j + 1) % N_ANG
    top = T[i, j] * (1 - fa) + T[i, j1] * fa
    bot = T[i + 1, j] * (1 - fa) + T[i + 1, j1] * fa
    return top * (1 - fu) + bot * fu


def _rows_at(C, z0, step, zq):
    """Linear lookup of per-row values C [rows, ...] at heights zq."""
    u = np.clip((z0 - np.asarray(zq, float)) / step, 0, len(C) - 1.000001)
    i = u.astype(int)
    f = (u - i).reshape(u.shape + (1,) * (C.ndim - 1))
    return C[i] * (1 - f) + C[i + 1] * f


# ---------------------------------------------------------------- round 10's surface (target)
def _r10():
    """BVH of round 10's lower body (torso loft, both legs and feet, procedural), the torso
    ring at WELD_ROW (positions), and the leg section functions."""
    if 'r10' in _CACHE:
        return _CACHE['r10']
    from . import body
    bm = bmesh.new()
    body.build_leg(bm)
    body.build_foot(bm)
    body._mirror_x(bm)
    rings = body.build_torso(bm)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    iw = list(body.TORSO_ROWS).index(WELD_ROW)
    ring = np.array([v.co[:] for v in rings[iw]])
    tree = BVHTree.FromBMesh(bm)
    bm.free()
    _CACHE['r10'] = (tree, ring)
    return _CACHE['r10']


def _r10_leg_radius(rows, ang, anatomy=False):
    """Round 10's left leg section (body._leg_section_r10 + its shape-master correction, and
    with `anatomy` its kneecap / calf / malleoli offsets) as (centres (R, 2) m, radii (R, A)
    m about them at world angles `ang`)."""
    from . import body
    a = np.linspace(0, 2 * math.pi, 361)[:-1]
    C, Rr = [], []
    for row in rows:
        cx, cy, hw, hd = body._leg_section_r10(row)
        f = body._leg_offset_r10(row, anatomy)
        off = np.array([f(math.cos(t), math.sin(t)) for t in a])
        qx = hw * np.cos(a) + off[:, 0]
        qy = hd * np.sin(a) + off[:, 1]        # + front (-y world)
        th = np.arctan2(-qy, qx)
        r = np.hypot(qx, qy)
        o = np.argsort(th)
        th, r = th[o], r[o]
        Rr.append(np.interp(np.mod(ang + math.pi, 2 * math.pi) - math.pi, th, r, period=2 * math.pi) * PX)
        C.append((cx * PX, cy * PX))
    return np.array(C), np.array(Rr)


# ---------------------------------------------------------------- the warp
class Warp:
    """Her points -> Levi's (see the module docstring, step 2)."""

    def __init__(self, src_tree, bones, crotch_her, loop_pts, torso_ring):
        from . import body
        self.ang = 2 * math.pi * np.arange(N_ANG) / N_ANG
        self.dirs = np.stack([np.cos(self.ang), np.sin(self.ang), np.zeros(N_ANG)], 1)
        self.loop_z = float(loop_pts[:, 2].mean())
        z_top = float(zrow(WELD_ROW)) - TOP_GAP
        self.z_top = z_top
        knee, ankle = body._knee_joint_r10(), body._ankle_joint_r10()
        self.zmap = ZMap([self.loop_z, crotch_her, bones['ひざD'][2], bones['足首D'][2]],
                         [z_top, CROTCH_Z, knee.z, ankle.z])
        self.bones = bones
        tree10, _ = _r10()
        # --- pelvis tables (about the midline), rows from z_top down to just under the crotch
        self.p0, step = z_top + 0.004, TABLE_STEP
        zp = np.arange(self.p0, CROTCH_Z - 0.012, -step)
        zh = self.zmap.inv(zp)
        cyh = np.full(len(zp), float(bones['下半身'][1]))
        cyl = np.full(len(zp), -0.03)
        for _ in range(2):
            Rh = self._ring(src_tree, np.stack([np.zeros_like(zh), cyh, zh], 1), 0.3)
            Rl = self._ring(tree10, np.stack([np.zeros_like(zp), cyl, zp], 1), 0.3)
            for R, cy in ((Rh, cyh), (Rl, cyl)):
                q = N_ANG // 4
                ok = np.isfinite(R[:, q]) & np.isfinite(R[:, 3 * q])
                cy[ok] += (R[ok, q] - R[ok, 3 * q]) / 2
            cyh, cyl = _gauss_rows(cyh, 3.0), _gauss_rows(cyl, 3.0)
        Rh = self._ring(src_tree, np.stack([np.zeros_like(zh), cyh, zh], 1), 0.3)
        Rl = self._ring(tree10, np.stack([np.zeros_like(zp), cyl, zp], 1), 0.3)
        sig = LP_SIGMA['pelvis'] / step
        self.pel_S = _lowpass(Rl, self.ang, sig) / _lowpass(Rh, self.ang, sig)
        self.pel_R10 = np.array([_fill_ring(r) for r in _fill_rows(Rl)])
        self.pel_cyh_z, self.pel_cyh = zh, cyh            # her centre by her height
        self.pel_cyl = cyl
        # --- leg tables (about each leg's axis), from just above the crotch down past the ankle
        self.l0 = CROTCH_Z + 0.01
        zp = np.arange(self.l0, float(zrow(882.0)), -step)
        zh = self.zmap.inv(zp)
        hip, kn, an = bones['足D'], bones['ひざD'], bones['足首D']
        ch = np.stack([np.interp(zh, [an[2], kn[2], hip[2]], [an[k], kn[k], hip[k]]) for k in (0, 1)], 1)
        for it in range(3):
            Rh = self._ring(src_tree, np.c_[ch, zh], 0.15, midline=True)
            if it == 2:
                break
            q = N_ANG // 4
            for k, (a, b) in enumerate(((0, 2 * q), (q, 3 * q))):
                ok = np.isfinite(Rh[:, a]) & np.isfinite(Rh[:, b])
                ch[ok, k] += (Rh[ok, a] - Rh[ok, b]) / 2
            ch = _gauss_rows(ch, 0.012 / step)
        Cl, Rl = _r10_leg_radius(rowz(zp), self.ang)
        sig = LP_SIGMA['leg'] / step
        self.leg_S = _lowpass(Rl, self.ang, sig) / _lowpass(Rh, self.ang, sig)
        self.leg_chz, self.leg_ch = zh, ch
        self.leg_cl = Cl
        # --- the waist loop: her loop's angles about her centre -> the torso ring's
        self._loop(loop_pts, torso_ring)

    def _ring(self, tree, centres, reach, midline=False):
        """Radii [rows, N_ANG] of the outermost surface about horizontal centres."""
        n = len(centres)
        O = np.repeat(centres, N_ANG, 0)
        D = np.tile(self.dirs, (n, 1))
        rc = np.full(len(O), reach)
        if midline:
            inward = D[:, 0] < -1e-9
            rc[inward] = np.minimum(rc[inward], (O[inward, 0] - 0.003) / -D[inward, 0])
            return _cast_in(tree, O, D, rc).reshape(n, N_ANG)
        # about the midline: made mirror-exact (a quad's two triangles mirror onto the other
        # diagonal, so the halves' hits differ by up to ~0.1 mm)
        R = _cast_in(tree, O, D, rc).reshape(n, N_ANG)
        Rm = R[:, (N_ANG // 2 - np.arange(N_ANG)) % N_ANG]
        with np.errstate(invalid='ignore'):
            return np.where(np.isfinite(R) & np.isfinite(Rm), (R + Rm) / 2, np.where(np.isfinite(R), R, Rm))

    def _loop(self, loop_pts, torso_ring):
        """Her waist loop's original vertices (every other of the cc1 loop) are levelled and
        turned onto the torso ring's vertices: dz, dtheta by angle (periodic tables)."""
        cyh = float(np.interp(loop_pts[:, 2].mean(), self.pel_cyh_z[::-1], self.pel_cyh[::-1]))
        th = np.arctan2(loop_pts[:, 1] - cyh, loop_pts[:, 0])
        cyl = self.pel_cyl[0]
        n = len(torso_ring)
        # torso ring k runs clockwise from +x seen from above; her loop counter-clockwise
        T = torso_ring[[(-i) % n for i in range(n)]]
        tt = np.arctan2(T[:, 1] - cyl, T[:, 0])
        orig = th[0::2]
        d = np.angle(np.exp(1j * (tt - orig)))
        o = np.argsort(np.mod(th, 2 * math.pi))
        self.loop_th = np.mod(th, 2 * math.pi)[o]
        self.loop_dz = (self.loop_z - loop_pts[:, 2])[o]
        dth = np.empty(len(th))
        dth[0::2] = d
        dth[1::2] = (d + np.roll(d, -1)) / 2
        self.loop_dth = dth[o]
        self.torso_T = T

    def _periodic(self, vals, th):
        return np.interp(np.mod(th, 2 * math.pi), self.loop_th, vals, period=2 * math.pi)

    def __call__(self, Q):
        Q = np.asarray(Q, dtype=np.float64)
        x, y, z = Q[:, 0], Q[:, 1], Q[:, 2]
        step = TABLE_STEP
        # her pelvis centre at her height (held below her crotch)
        cyh = np.interp(z, self.pel_cyh_z[::-1], self.pel_cyh[::-1])
        th = np.arctan2(y - cyh, x)
        g = 1.0 - _ss(0.0, TOP_FADE, self.loop_z - self._periodic(self.loop_dz, th) - z)
        g = np.where(z > self.loop_z + 0.03, 1.0, g)
        zadj = z + self._periodic(self.loop_dz, th) * g
        zp = self.zmap(zadj)
        # pelvis map (about the midline; held at the crotch's tables below it)
        zc = np.maximum(zp, CROTCH_Z - 0.01)
        r = np.hypot(x, y - cyh)
        S = _table_at(self.pel_S, self.p0, step, zc, th)
        tho = th + self._periodic(self.loop_dth, th) * g
        cyl = _rows_at(self.pel_cyl, self.p0, step, zc)
        # the top eases onto round 10's torso (the waistbands' room), her detail standing
        # out of it limited softly to CLOTH_OUT
        r10 = _table_at(self.pel_R10, self.p0, step, zc, tho)
        d = r * S - r10
        out_ = CLOTH_OUT[0] + (CLOTH_OUT[1] - CLOTH_OUT[0]) * _ss(float(zrow(CLOTH_ROWS[0])),
                                                                 float(zrow(CLOTH_ROWS[1])), zp)
        d = np.where(d > 0, out_ * np.tanh(d / out_), d)
        gb = _ss(float(zrow(TOP_BLEND_ROWS[0])), float(zrow(TOP_BLEND_ROWS[1])), zp)
        rp = r10 + (1.0 - gb) * d
        Pp = np.stack([rp * np.cos(tho), cyl + rp * np.sin(tho), zp], 1)
        w = _ss(LEG_BLEND[0], LEG_BLEND[1], zp)
        out = Pp
        legs = w > 0
        if legs.any():
            Pl = self.leg(Q[legs], zp[legs])
            out = Pp.copy()
            out[legs] = Pp[legs] * (1 - w[legs, None]) + Pl * w[legs, None]
        # the crotch widened: her inner thighs meet in a ~6 mm gusset, across which the left /
        # right thigh weights change hands (a stride stretched it x2.9); stretched across
        # the midline (odd, smooth in x) and the inner thighs moved apart below it
        a, b, c, d_ = CROTCH_GAP_Z
        gz = _ss(CROTCH_Z + a, CROTCH_Z + b, zp) * (1.0 - _ss(CROTCH_Z + c, CROTCH_Z + d_, zp))
        x = out[:, 0]
        out[:, 0] = x + CROTCH_GAP * gz * np.tanh(x / CROTCH_GAP_W) * (1.0 - _ss(*CROTCH_GAP_FALL, np.abs(x)))
        return out

    def leg(self, Q, zp):
        """The leg map for her points Q at Levi heights zp (each about its own leg's axis)."""
        step = TABLE_STEP
        s = np.where(Q[:, 0] < 0, -1.0, 1.0)
        x, y, z = np.abs(Q[:, 0]), Q[:, 1], Q[:, 2]
        ch = np.stack([np.interp(z, self.leg_chz[::-1], self.leg_ch[::-1, k]) for k in (0, 1)], 1)
        th = np.arctan2(y - ch[:, 1], x - ch[:, 0])
        r = np.hypot(x - ch[:, 0], y - ch[:, 1])
        S = _table_at(self.leg_S, self.l0, step, zp, th)
        cl = _rows_at(self.leg_cl, self.l0, step, zp)
        rp = r * S
        return np.stack([s * (cl[:, 0] + rp * np.cos(th)), cl[:, 1] + rp * np.sin(th), zp], 1)

    def leg_axis(self, zp):
        """Levi's left leg axis (x, y) at heights zp (round 10's leg_section centres)."""
        return _rows_at(self.leg_cl, self.l0, TABLE_STEP, zp)


# ---------------------------------------------------------------- the geometry
class Legs:
    """Pelvis + both legs + feet as arrays (positions, polygons) with the waist loop and the
    data the body exports. Built once per session (deterministic).

    Layout (vertex blocks in P): the pelvis rings (PELVIS rows x 64, row 0 the waist loop), the
    crotch chain (CHAIN_M, on the midline), the left leg (GUSSET_ROWS rings of N_LEG, the loft
    rings, the foot rings, the toe cap rings, the toe pole), the right leg (its mirror)."""

    def __init__(self):
        A = asset()
        P0, F0 = A['pos'], A['faces']
        V0 = len(P0)
        # two subdivision levels: the smooth surface everything is sampled from
        P1, Q1, eid1, _ = catmull_clark(P0, F0)
        P2, Q2, _, _ = catmull_clark(P1, [list(q) for q in Q1])
        loop1 = _sub_loop(A['waist'], eid1, V0)
        # the crotch: her lowest midline vertex
        mid = np.abs(P0[:, 0]) < 1e-9
        crotch_her = float(P0[mid, 2].min())
        tree10, torso_ring = _r10()
        src = _tree(P2, Q2)
        self.warp = W = Warp(src, A['bones'], crotch_her, P1[loop1], torso_ring)
        D2 = W(P2)
        dst = _tree(D2, Q2)
        # the left half alone (the midline's faces included), for the gusset rows' projection
        dst_l = _tree(D2, Q2[D2[Q2][:, :, 0].mean(1) > -1e-4])
        # 1. the pelvis rings, the waist loop (row 0) down to the ring at CROTCH_Z + H0_UP
        band = self._pelvis_band(dst, W(P1[loop1]), W)
        nb = len(band[0])
        q = nb // 4
        Bp, Fp = band[-1][q], band[-1][3 * q]
        # 2. the chain under the crotch, on the midline from B to F (CHAIN_M inner points)
        chain = self._chain(dst, Bp, Fp)
        # 3. the left leg: the gusset rows (L1 .. Ln) and the loft below
        h = band[-1]
        L0 = [h[k] for k in range(0, q + 1)] + list(chain) + [h[k] for k in range(3 * q, nb)]
        L0 = np.array(L0)
        # the columns' top points: the ring / chain vertex each L1 vertex hangs from; the corner
        # vertices X_B, X_F from the corner triples (h[q-1], B, c_1), (c_m, F, h[3q+1])
        m = CHAIN_M
        tops = ([h[k] for k in range(0, q - 1)] + [(h[q - 1] + Bp + chain[0]) / 3.0]
                + list(chain[1:m - 1]) + [(chain[m - 1] + Fp + h[3 * q + 1]) / 3.0]
                + [h[k] for k in range(3 * q + 2, nb)])
        tops = np.array(tops)
        if len(tops) != N_LEG:
            raise RuntimeError(f'body legs: {len(tops)} gusset columns, N_LEG {N_LEG}')
        zn = float(zrow(GUSSET_END_ROW))
        ax_t = W.leg_axis(tops[:, 2])
        phi_top = np.unwrap(np.arctan2(tops[:, 1] - ax_t[:, 1], tops[:, 0] - ax_t[:, 0]))
        # the loft's columns: evenly spaced angles about the leg axis (the circular mean offset)
        k = np.arange(N_LEG)
        off = np.angle(np.mean(np.exp(1j * (phi_top - 2 * math.pi * k / N_LEG))))
        off = phi_top[0] + np.angle(np.exp(1j * (off - phi_top[0])))       # on the tops' branch
        cols = off + 2 * math.pi * k / N_LEG
        Ln = self._leg_ring(dst, W, zn, cols)
        gus = self._gusset(dst_l, L0, tops, Ln)
        rings, centres = self._loft(dst, tree10, cols, W)
        # assemble
        P = list(band) + [np.array(chain)]
        F = []
        base = [0]
        for r in band[1:]:
            base.append(base[-1] + nb)
        for a, b in zip(base, base[1:]):
            for k_ in range(nb):
                j = (k_ + 1) % nb
                F.append([a + k_, b + k_, b + j, a + j])
        ring_h = base[-1]
        ch0 = ring_h + nb
        nxt = ch0 + m
        left_leg = gus + rings[:-1]          # rings of N_LEG (gusset L1..Ln, loft, foot, toe cap)
        tip = rings[-1][0]
        self.n_rings = len(left_leg)
        for side in (1.0, -1.0):
            mir = side < 0
            # L0 as indices: the ring's half (the right one mirrored: k -> nb/2 - k) and the chain
            hk = (lambda k_: ring_h + ((nb // 2 - k_) % nb if mir else k_))
            seq0 = [hk(k_) for k_ in range(0, q + 1)] + [ch0 + i for i in range(m)] + \
                [hk(k_) for k_ in range(3 * q, nb)]
            first = nxt
            rows = [list(range(first + i * N_LEG, first + (i + 1) * N_LEG)) for i in range(len(left_leg))]
            tip_i = first + len(left_leg) * N_LEG
            faces = []
            # L0 -> L1 (corner quads at B and F)
            L1 = rows[0]
            g = {}
            for k_ in range(0, q - 1):
                g[k_] = L1[k_]
            g[q - 1] = L1[q - 1]                 # h[q-1] -> X_B
            g[q + 1] = L1[q - 1]                 # c_1 -> X_B
            for i in range(1, m - 1):
                g[q + 1 + i] = L1[q - 1 + i]     # c_(i+1) -> lc_(i+1)
            g[q + m] = L1[q + m - 2]             # c_m -> X_F
            g[q + m + 2] = L1[q + m - 2]         # h[3q+1] -> X_F
            for i in range(q + m + 3, len(seq0)):
                g[i] = L1[i - 4]
            n0 = len(seq0)
            for p in range(n0):
                p1 = (p + 1) % n0
                if p in (q - 1, q, q + m, q + m + 1):
                    continue
                faces.append([seq0[p], g[p], g[p1], seq0[p1]])
            faces.append([seq0[q - 1], g[q - 1], seq0[q + 1], seq0[q]])               # at B
            faces.append([seq0[q + m], g[q + m], seq0[q + m + 2], seq0[q + m + 1]])   # at F
            for a, b in zip(rows, rows[1:]):
                for k_ in range(N_LEG):
                    j = (k_ + 1) % N_LEG
                    faces.append([a[k_], b[k_], b[j], a[j]])
            for k_ in range(N_LEG):
                faces.append([rows[-1][k_], tip_i, rows[-1][(k_ + 1) % N_LEG]])
            if mir:
                faces = [f[::-1] for f in faces]
            F += faces
            pts = np.concatenate(left_leg + [tip[None]]) * np.array([side, 1.0, 1.0])
            P.append(pts)
            nxt += len(pts)
        P = np.concatenate(P)
        # mirror images: band column k <-> nb/2 - k, the chain itself, left leg <-> right leg
        mirror = np.arange(len(P))
        for r in range(len(band)):
            mirror[r * nb:(r + 1) * nb] = r * nb + (nb // 2 - np.arange(nb)) % nb
        nl = (len(P) - ch0 - m) // 2
        mirror[ch0 + m:ch0 + m + nl] = np.arange(ch0 + m + nl, ch0 + m + 2 * nl)
        mirror[ch0 + m + nl:] = np.arange(ch0 + m, ch0 + m + nl)
        apex = chain[int(np.argmin(chain[:, 2]))]
        self.P = self._round_crotch(P, F, mirror, apex, nb)
        self.F = F
        self.loop = np.arange(nb)
        self.centres = centres
        self.n_cols = N_LEG
        e = self._edges()
        ln = np.linalg.norm(self.P[e[:, 0]] - self.P[e[:, 1]], axis=1)
        val = np.bincount(e.ravel(), minlength=len(self.P))
        self.info = {'her_crotch_z': round(crotch_her, 4), 'pelvis_rings': len(band),
                     'gusset_rows': GUSSET_ROWS, 'leg_rings': self.n_rings, 'columns': N_LEG,
                     'verts': int(len(self.P)), 'faces': int(len(F)),
                     'edge_mm': (round(float(ln.min()) * 1e3, 2), round(float(np.median(ln)) * 1e3, 2)),
                     'poles': {int(v): int((val == v).sum()) for v in np.unique(val) if v != 4}}

    @staticmethod
    def _round_crotch(P, F, mirror, apex, n_loop):
        """Umbrella smoothing round the crotch (CROTCH_ROUND), mirror-exact: the widened gusset
        (CROTCH_GAP) is a flat arch between the thighs whose sides turn into the inner thighs
        over about a row; this rounds them."""
        it, lam, rad, (d0, d1) = CROTCH_ROUND
        E = set()
        for f in F:
            for k in range(len(f)):
                a, b = int(f[k]), int(f[(k + 1) % len(f)])
                E.add((min(a, b), max(a, b)))
        E = np.array(sorted(E))
        deg = np.bincount(E.ravel(), minlength=len(P)).astype(np.float64)
        d = np.linalg.norm((P - apex) / np.array(rad), axis=1)
        w = lam * (1.0 - _ss(d0, d1, d))
        w[:n_loop] = 0.0
        left = np.nonzero(P[:, 0] >= 0.0)[0]
        P = P.copy()
        for _ in range(it):
            s = np.zeros_like(P)
            np.add.at(s, E[:, 0], P[E[:, 1]])
            np.add.at(s, E[:, 1], P[E[:, 0]])
            P = P + w[:, None] * (s / np.maximum(deg, 1.0)[:, None] - P)
            P[mirror[left]] = P[left] * np.array([-1.0, 1.0, 1.0])
            P[mirror == np.arange(len(P)), 0] = 0.0
        return P

    def _edges(self):
        E = set()
        for f in self.F:
            for k in range(len(f)):
                a, b = int(f[k]), int(f[(k + 1) % len(f)])
                E.add((min(a, b), max(a, b)))
        return np.array(sorted(E))

    # ---- the pelvis
    def _pelvis_band(self, dst, loop, W):
        """Rings of the pelvis (each the waist loop's 64 columns) from the waist loop down to
        the ring at CROTCH_Z + H0_UP, sampled along horizontal rays from the pelvis centre at
        the loop vertices' angles. The right half mirrors the left (column k -> nb/2 - k)."""
        nb = len(loop)
        q = nb // 4
        mx = loop[(nb // 2 - np.arange(nb)) % nb] * np.array([-1.0, 1.0, 1.0])
        if np.abs(mx - loop).max() > 1e-6 or abs(loop[q, 0]) > 1e-6 or abs(loop[3 * q, 0]) > 1e-6 \
                or loop[q, 1] < loop[3 * q, 1]:
            raise RuntimeError('body legs: the waist loop is not mirror-ordered from +x via the back')
        z0 = float(loop[:, 2].mean())
        h0 = CROTCH_Z + H0_UP
        n = max(2, int(round((z0 - h0) / (PELVIS_STEP * PX))))
        cy0 = float(_rows_at(W.pel_cyl, W.p0, TABLE_STEP, z0))
        psi = np.arctan2(loop[:, 1] - cy0, loop[:, 0])
        psi[q], psi[3 * q] = math.pi / 2, -math.pi / 2
        left = list(range(3 * q, nb)) + list(range(0, q + 1))
        out = [loop.copy()]
        for i in range(1, n + 1):
            z = z0 + (h0 - z0) * i / n
            cy = float(_rows_at(W.pel_cyl, W.p0, TABLE_STEP, z))
            O = np.tile([0.0, cy, z], (len(left), 1))
            D = np.stack([np.cos(psi[left]), np.sin(psi[left]), np.zeros(len(left))], 1)
            r = _cast_in(dst, O, D, np.full(len(left), 0.3))
            if not np.isfinite(r).all():
                raise RuntimeError(f'body legs: pelvis ring at z {z:.3f} missed the surface')
            # the gluteal cleft: one column sits in it, a V of ~90 deg; rounded over a few
            # columns either side (CLEFT_SOFT passes of [1 2 1] round the ring, mirror-exact)
            full = np.zeros(nb)
            full[left] = r
            for k in range(q + 1, 3 * q):
                full[k] = full[(nb // 2 - k) % nb]
            sm = full.copy()
            for _ in range(CLEFT_SOFT[0]):
                sm = (np.roll(sm, 1) + 2 * sm + np.roll(sm, -1)) / 4.0
            dk = np.minimum(np.abs(np.arange(nb) - q), nb - np.abs(np.arange(nb) - q))
            wk = np.exp(-0.5 * (dk / CLEFT_SOFT[1]) ** 2)
            r = (full + (sm - full) * wk)[left]
            ring = np.zeros((nb, 3))
            ring[left] = O + D * r[:, None]
            ring[q, 0] = ring[3 * q, 0] = 0.0
            for k in range(q + 1, 3 * q):
                ring[k] = ring[(nb // 2 - k) % nb] * np.array([-1.0, 1.0, 1.0])
            out.append(ring)
        return out

    @staticmethod
    def _chain(dst, B, F):
        """CHAIN_M points on the midline under the crotch, evenly spaced along it from B to F
        (outermost hits of rays in the x = 0 plane from a point above the crotch)."""
        C = np.array([0.0, (B[1] + F[1]) / 2, max(B[2], F[2]) + 0.02])
        aB = math.atan2(B[1] - C[1], C[2] - B[2])
        aF = math.atan2(F[1] - C[1], C[2] - F[2])
        a = np.linspace(aB, aF, 241)
        D = np.stack([np.zeros_like(a), np.sin(a), -np.cos(a)], 1)
        r = _cast_in(dst, np.tile(C, (len(a), 1)), D, np.full(len(a), 0.2))
        ok = np.isfinite(r[1:-1])
        pts = np.concatenate([[B], (C + D * r[:, None])[1:-1][ok], [F]])
        pts[:, 0] = 0.0
        s = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))])
        sq = s[-1] * np.arange(1, CHAIN_M + 1) / (CHAIN_M + 1)
        out = np.stack([np.interp(sq, s, pts[:, k]) for k in range(3)], 1)
        out[:, 0] = 0.0
        return out

    @staticmethod
    def _leg_ring(dst, W, z, cols):
        """A horizontal left leg ring at height z: the surface along rays from the leg axis at
        world angles `cols` (inward rays start at the midline)."""
        c = W.leg_axis(np.array([z]))[0]
        n = len(cols)
        O = np.tile([c[0], c[1], z], (n, 1))
        D = np.stack([np.cos(cols), np.sin(cols), np.zeros(n)], 1)
        rc = np.minimum(0.15, np.where(D[:, 0] < 0, (O[:, 0] - 0.003) / np.maximum(-D[:, 0], 1e-9), 0.15))
        r = _cast_in(dst, O, D, rc)
        if not np.isfinite(r).all():
            r = _fill_ring(r)
        return O + D * r[:, None]

    @staticmethod
    def _gusset(tree, L0, tops, Ln):
        """The rows L1 .. Ln between the pelvis ring + chain (L0) and the first horizontal leg
        ring Ln: each column straight from its top to Ln, put on the left half of the surface,
        then relaxed on it (GUSSET_RELAX; L0 and Ln fixed)."""
        n = GUSSET_ROWS
        rows = [tops + (Ln - tops) * (i / n) for i in range(1, n)]
        G = np.array(rows)                     # (n - 1, N_LEG, 3)

        def project(X):
            out = X.copy()
            for i, p in enumerate(X):
                loc = tree.find_nearest(Vector(p))[0]
                if loc is not None:
                    out[i] = loc
            return out
        G = project(G.reshape(-1, 3)).reshape(G.shape)
        # neighbours: along the row, and up / down the column (row 1's up: the tops, which carry
        # the corner triples' centroids; L0 itself stays fixed)
        it, lam = GUSSET_RELAX
        for _ in range(it):
            up = np.concatenate([[tops], G[:-1]])
            dn = np.concatenate([G[1:], [Ln]])
            avg = (np.roll(G, 1, 1) + np.roll(G, -1, 1) + up + dn) / 4.0
            G = project((G + lam * (avg - G)).reshape(-1, 3)).reshape(G.shape)
        return [g for g in G] + [Ln]

    def _loft(self, dst, tree10, cols, W):
        """Left leg rings below the first horizontal ring (LEG_RING_ROWS), the foot's rings, the
        toe cap's rings and the toe pole (last 'ring', one point), at the columns' world angles
        `cols` about the leg axis."""
        nc = len(cols)
        out, centres = [], []
        for row in LEG_RING_ROWS:
            ring = self._leg_ring(dst, W, float(zrow(row)), cols)
            out.append(ring)
            centres.append(ring.mean(0))
        # the foot: rings normal to FOOT_PATH, starting below the last leg ring
        z_last = float(out[-1][:, 2].mean())
        ax = W.leg_axis(np.array([z_last]))[0]
        path = self._foot_path(out[-1], [ax[0], ax[1], z_last])
        her_fade = HER_ANKLE_ROWS
        hint = np.array([1.0, 0.0, 0.0])
        foot = []

        def frame(t):
            side = hint - t * (hint @ t)
            side /= np.linalg.norm(side)
            return side, np.cross(t, side)
        for k in range(1, len(path) - 1):
            c = path[k]
            t = path[k + 1] - path[k - 1]
            t /= np.linalg.norm(t)
            side, up = frame(t)
            # ring angle -> world direction: the leg rings' columns are world angles about the
            # axis (x, y); on a horizontal ring side = +x, up = -y, so a world angle a is the
            # ring angle -a
            D = np.cos(-cols)[:, None] * side + np.sin(-cols)[:, None] * up
            O = np.repeat(c[None], nc, 0)
            rc = np.full(nc, 40.0 * PX)
            inward = D[:, 0] < 0
            rc[inward] = np.minimum(rc[inward], (O[inward, 0] - 0.003) / -D[inward, 0])
            r_old = _cast_in(tree10, O, D, rc) - FOOT_INSET * PX
            wh = 1.0 - _ss(her_fade[0], her_fade[1], float(rowz(c[2])))
            r = r_old
            if wh > 0:
                r_her = _cast_in(dst, O, D, rc)
                r = np.where(np.isfinite(r_her), wh * r_her + (1 - wh) * r_old, r_old)
            foot.append((O, D, _fill_ring(r)))
            centres.append(c)
        # round 10's foot meets its leg in creases (the old step): smoothed over about a ring
        # and a column; only the instep side above the vamp may fill out (FOOT_FILL; FOOT_FILL_ROWS
        # by the ring's centre), the heel counter, the toe box and the sole sit 1-2 mm from the shoe
        Rf = np.array([r for _, _, r in foot])
        Rs = _gauss_rows(Rf, FOOT_SMOOTH[0])
        Rs = _gauss_rows(np.concatenate([Rs.T[-3:], Rs.T, Rs.T[:3]]), FOOT_SMOOTH[1])[3:-3].T
        rows_c = rowz(np.array([c[2] for c in centres[-len(foot):]]))
        cap = FOOT_FILL * np.maximum(0.0, -np.sin(cols))[None, :] * (1.0 - _ss(*FOOT_FILL_ROWS, rows_c))[:, None]
        Rf = Rf + np.minimum(Rs - Rf, cap)
        for (O, D, _), r in zip(foot, Rf):
            out.append(O + D * r[:, None])
        # the toe cap: rings shrinking along the path's end tangent onto the pole, an
        # ellipsoid through the last ring and the tip of round 10's toe (TOE_CAP: axial
        # fractions), kept inside round 10's toe surface
        c_last = path[-2]
        t = path[-1] - path[-3]
        t /= np.linalg.norm(t)
        reach = 40.0 * PX
        hit = _cast_in(tree10, c_last[None], t[None], np.array([reach]))[0]
        tip_d = (hit if np.isfinite(hit) else float(np.linalg.norm(path[-1] - c_last))) - FOOT_INSET * PX
        last = out[-1]
        r_last = np.linalg.norm(last - c_last, axis=1)
        dirs = (last - c_last) / np.maximum(r_last, 1e-9)[:, None]
        dirs = dirs - t * (dirs @ t)[:, None]
        dirs /= np.linalg.norm(dirs, axis=1)[:, None]
        for f in TOE_CAP:
            c = c_last + t * tip_d * f
            r = r_last * math.sqrt(1.0 - f * f)
            r10 = _cast_in(tree10, np.repeat(c[None], nc, 0), dirs, np.full(nc, reach)) - FOOT_INSET * PX
            r = np.where(np.isfinite(r10), np.minimum(r, r10), r)
            out.append(c + dirs * np.maximum(r, 0.3 * r_last)[:, None])
            centres.append(c)
        out.append((c_last + t * tip_d)[None])
        return out, centres

    @staticmethod
    def _foot_path(last_ring, last_c):
        """Points along FOOT_PATH (m) every FOOT_STEP px, from the last leg ring's axis; the
        first and last points only set the end tangents."""
        pts = [np.array(last_c)] + [np.array([x * PX, y * PX, float(zrow(r))]) for x, y, r in FOOT_PATH]
        pts.append(np.array([TOE_TIP[0] * PX, TOE_TIP[1] * PX, float(zrow(TOE_TIP[2]))]))
        pts = np.array(pts)
        # Catmull-Rom, densely, then resampled by arc length
        dense = []
        ext = np.concatenate([[2 * pts[0] - pts[1]], pts, [2 * pts[-1] - pts[-2]]])
        for i in range(1, len(ext) - 2):
            p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
            for t in np.linspace(0, 1, 40, endpoint=False):
                dense.append(0.5 * (2 * p1 + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                                    + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
        dense.append(pts[-1])
        dense = np.array(dense)
        s = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(dense, axis=0), axis=1))])
        n = max(3, int(round(s[-1] / (FOOT_STEP * PX))))
        sq = np.linspace(0, s[-1], n + 1)
        return np.stack([np.interp(sq, s, dense[:, k]) for k in range(3)], 1)


    # ---- into the body's bmesh
    def attach(self, bm, rings):
        """Add the pelvis, legs and feet to `bm` and weld them to the torso: the torso's rings
        below WELD_ROW (and its crotch pole) are deleted, and one row of quad + triangle
        pairs joins the torso ring (32) to the pelvis' waist loop (64), mirrored at the
        midline. `rings`: body.build_torso's vertex rings."""
        from . import body
        iw = list(body.TORSO_ROWS).index(WELD_ROW)
        T = rings[iw]
        drop = {v for r in rings[iw + 1:] for v in r}
        last = rings[-1][0]
        pole = [e.other_vert(last) for e in last.link_edges]
        pole = [v for v in pole if v not in drop and v not in T]
        if len(pole) != 1:
            raise RuntimeError('body legs: the torso has no single crotch pole')
        bmesh.ops.delete(bm, geom=list(drop) + pole, context='VERTS')
        vs = [bm.verts.new(tuple(p)) for p in self.P]
        for f in self.F:
            bm.faces.new([vs[i] for i in f])
        n = len(T)
        Tc = [T[(-i) % n] for i in range(n)]        # counter-clockwise from +x seen from above
        L = [vs[int(j)] for j in self.loop]
        if len(L) != 2 * n:
            raise RuntimeError(f'body legs: waist loop {len(L)} vs torso ring {n}')
        h = n // 4
        for i in range(n):
            t0, t1 = Tc[i], Tc[(i + 1) % n]
            l0, l1, l2 = L[2 * i], L[2 * i + 1], L[(2 * i + 2) % (2 * n)]
            if i < h or i >= 3 * h:      # left half (+x): triangle on the segment's first vertex
                bm.faces.new((t0, l0, l1))
                bm.faces.new((t0, l1, l2, t1))
            else:                        # right half: the mirror image
                bm.faces.new((t0, l0, l1, t1))
                bm.faces.new((t1, l1, l2))
        return vs

    # ---- exports
    def _left_tris(self):
        tri = []
        for f in self.F:
            if self.P[f, 0].mean() <= 0:
                continue
            tri += [(f[0], f[1], f[2])] if len(f) == 3 else [(f[0], f[1], f[2]), (f[0], f[2], f[3])]
        return np.array(tri)

    def tables(self):
        """Slices of the final left leg (pelvis' left half, loft, foot) every panel row in
        LEG_TABLE_ROWS: rows, centres (cx, cy) px, half extents (hw, hd) px and the radial
        residual s [row, 72] px of the skin past the ellipse (hw cos a, hd sin a) along
        its direction (dx + out, dy + front), as body.leg_offset reads it."""
        if hasattr(self, '_tables'):
            return self._tables
        tri = self._left_tris()
        Pp = self.P / PX                    # px
        a = 2 * math.pi * np.arange(N_ANG) / N_ANG
        rows = np.arange(LEG_TABLE_ROWS[0], LEG_TABLE_ROWS[1] + 1)
        C, H, S = [], [], []
        for row in rows:
            zc = (spec.SHEET_GROUND_Y - row) + 1e-4     # off the loft rings' own heights
            seg = _slice(Pp, tri, zc)
            xs, ys = seg[..., 0], seg[..., 1]
            x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
            cx, cy, hw, hd = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2
            qx, qy = hw * np.cos(a), hd * np.sin(a)
            L = np.hypot(qx, qy)
            d = np.stack([qx / L, -qy / L], 1)          # world (x, y) directions
            rho = _ray_segments(np.array([cx, cy]), d, seg)
            C.append((cx, cy))
            H.append((hw, hd))
            S.append(np.where(np.isfinite(rho), rho - L, 0.0))
        self._tables = {'rows': rows, 'c': np.array(C), 'h': np.array(H), 's': np.array(S)}
        return self._tables

    def section(self, row):
        """(cx, cy, hw, hd) px of the left leg's slice at `row` (interpolated)."""
        t = self.tables()
        u = float(np.clip(row - t['rows'][0], 0, len(t['rows']) - 1.000001))
        i, f = int(u), u - int(u)
        c = t['c'][i] * (1 - f) + t['c'][i + 1] * f
        h = t['h'][i] * (1 - f) + t['h'][i + 1] * f
        return float(c[0]), float(c[1]), float(h[0]), float(h[1])

    def offset(self, row):
        """f(dx, dy) -> (d_side, d_front) px from the section ellipse to the skin (body.leg_offset)."""
        t = self.tables()
        u = float(np.clip(row - t['rows'][0], 0, len(t['rows']) - 1.000001))
        i, fr = int(u), u - int(u)
        s = t['s'][i] * (1 - fr) + t['s'][i + 1] * fr
        _, _, hw, hd = self.section(row)
        n = len(s)

        def f(dx, dy):
            v = (math.atan2(dy, dx) / (2 * math.pi)) % 1.0 * n
            k = int(v) % n
            sk = s[k] + (s[(k + 1) % n] - s[k]) * (v - int(v))
            qx, qy = hw * dx, hd * dy
            ln = math.hypot(qx, qy)
            if ln < 1e-9:
                return 0.0, 0.0
            return sk * qx / ln, sk * qy / ln
        return f

    def joints(self):
        """levi_joints for the rig: the knee at body.KNEE_ROW, across at the new slices' centre
        (smoothed over +-10 rows like round 10's tables) and as deep behind the front skin, as a
        share of the leg's depth there, as round 10's pivot (_r10_knee_depth; review: KNEE_FWD
        from the new slice's box centre put it 5 mm further forward, 40% instead of 45%);
        the ankle by round 10's definition (body.ANKLE_ROW / ANKLE_BACK on the leg axis); the
        hip and toe (HIP_JOINT, TOE_JOINT)."""
        if hasattr(self, '_joints'):
            return self._joints
        from . import body
        t = self.tables()
        sel = np.abs(t['rows'] - body.KNEE_ROW) <= 10
        cx = float(t['c'][sel, 0].mean())
        i = int(np.argmin(np.abs(t['rows'] - body.KNEE_ROW)))
        seg = _slice(self.P / PX, self._left_tris(), (spec.SHEET_GROUND_Y - body.KNEE_ROW) + 1e-4)
        cy = float(t['c'][i, 1])
        rho = _ray_segments(np.array([cx, cy]), np.array([[0.0, -1.0], [0.0, 1.0]]), seg)
        yf, yb = cy - rho[0], cy + rho[1]
        knee = body.P(cx, yf + _r10_knee_depth() * (yb - yf), body.KNEE_ROW)
        ax = self.warp.leg_axis(np.array([float(zrow(body.ANKLE_ROW))]))[0] / PX
        ankle = body.P(ax[0], ax[1] + body.ANKLE_BACK, body.ANKLE_ROW)
        self._joints = {'knee': tuple(knee), 'ankle': tuple(ankle), 'hip': HIP_JOINT, 'toe': TOE_JOINT}
        return self._joints


def _r10_knee_depth():
    """Round 10's knee pivot (body._knee_joint_r10) as a share of its leg's depth behind the
    front skin (rays along -y / +y from the pivot onto round 10's surface)."""
    from . import body
    tree, _ = _r10()
    k = np.array(body._knee_joint_r10()[:])
    r = _cast_in(tree, np.array([k, k]), np.array([[0.0, -1.0, 0.0], [0.0, 1.0, 0.0]]), np.array([0.2, 0.2]))
    return float(r[0] / (r[0] + r[1]))


def _slice(P, tri, z):
    """Segments (M, 2, 2) where the plane at height z cuts triangles `tri` of points P."""
    V = P[tri]
    d = V[:, :, 2] - z
    sel = (d.min(1) < 0) & (d.max(1) > 0)
    V, d = V[sel], d[sel]
    pts, crs = [], []
    for k in range(3):
        p, q = V[:, k], V[:, (k + 1) % 3]
        dp, dq = d[:, k], d[:, (k + 1) % 3]
        cr = dp * dq < 0
        t = dp / np.where(cr, dp - dq, 1.0)
        pts.append((p + (q - p) * t[:, None])[:, :2])
        crs.append(cr)
    cr, X = np.stack(crs, 1), np.stack(pts, 1)
    keep = cr.sum(1) == 2
    idx = np.argsort(~cr[keep], axis=1, kind='stable')[:, :2]
    return np.take_along_axis(X[keep], idx[:, :, None], 1)


def _ray_segments(o, d, seg):
    """Farthest intersection distance of rays from o along unit directions d (K, 2) with
    segments (M, 2, 2); NaN where a ray meets none."""
    A, B = seg[:, 0], seg[:, 1]
    e = B - A
    den = d[:, None, 0] * e[None, :, 1] - d[:, None, 1] * e[None, :, 0]
    w = A - o
    with np.errstate(divide='ignore', invalid='ignore'):
        t = (w[None, :, 0] * e[None, :, 1] - w[None, :, 1] * e[None, :, 0]) / den
        s = (w[None, :, 0] * d[:, None, 1] - w[None, :, 1] * d[:, None, 0]) / den
    ok = (np.abs(den) > 1e-12) & (s >= 0) & (s <= 1) & (t > 0)
    t = np.where(ok, t, -np.inf)
    r = t.max(1)
    return np.where(np.isfinite(r), r, np.nan)


def legs():
    if 'legs' not in _CACHE:
        _CACHE['legs'] = Legs()
    return _CACHE['legs']
