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
# Round 10: this sheet table is the procedural base (CAP_PROFILE_SHEET); the cap
# takes its crown from the shape master on top of it (see "shape master" below),
# and CAP_PROFILE, which hair_back reads with CAP_EXP, is measured on that
# reshaped cap (same layout: row, half width, front col, back col).
CAP_TOP = (14, 287)          # (row, side column) of the cap apex
CAP_PROFILE_SHEET = [
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
CAP_AZ = 128      # round 9: 40 -> 128 sections and CROWN_RING_SPLIT, so the crown
                  # grooves (below) resolve without a stitched, braid-like aliasing
CROWN_RING_SPLIT = (70.0, 2.5)  # above this row, ring gaps wider than this (px) are halved

# Round 9: crown lock ridges. The scalp is no longer one smooth cap: CROWN_GROOVES
# grooves radiate from a whorl a little behind the apex and part the crown into
# broad locks (crests on the measured cap profile, so no silhouette moves; the
# grooves are carved in, the skull lies 2.5-5 cm under the cap). Angles are around
# the whorl (0 = toward the face, + toward +X, the character's left), uneven so
# the locks differ in width; the front sector between -35 and +35 deg is left to
# the bang roots, which surface there as locks of their own. Each groove is a
# cosine dip CROWN_HALF (m) wide on either side of its line and CROWN_DEPTH x its own share deep; it fades in over
# CROWN_FADE_IN (radians from the whorl, seen from the skull centre: the lines
# converge there) and out toward the hairline over CROWN_FADE_ROWS (the bangs'
# and side locks' roots take over). CROWN_DEPTH = 0 restores the smooth cap.
CROWN_WHORL = (90.0, 19.0)      # (cap az, row): on the cap behind the apex
CROWN_GROOVES = ((38, 1.0), (78, 0.9), (117, 1.0), (162, 0.8), (-122, 0.9), (-80, 1.0), (-43, 0.9))
CROWN_DEPTH = 0.005
CROWN_HALF = 0.010
CROWN_FADE_IN = (0.05, 0.42)
CROWN_FADE_ROWS = (58.0, 92.0)
CROWN_KEEP = 0.5                # own-normal share in a groove (cap: VOL_KEEP), so it shades


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


_ROWS = [r[0] for r in CAP_PROFILE_SHEET]
_COLS = [[r[c] for r in CAP_PROFILE_SHEET] for c in (1, 2, 3)]
_SLOPES = [_pchip_slopes(_ROWS, c) for c in _COLS]
_APEX = (0.0, CAP_TOP[1], CAP_TOP[1])     # half width, front col, back col at the apex


def _profile(row):
    """(half width, side front col, side back col) of the sheet (procedural) cap
    at `row`."""
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


def sheet_point(az, row):
    """Point on the procedural (sheet) cap. az: 0 = +X, -90 = front (-Y)."""
    w, f, b = _profile(row)
    a = math.radians(az)
    return P(w * _se(math.cos(a)), row, (f + b) / 2 + (b - f) / 2 * _se(math.sin(a)))


def _axis_foot(p):
    """The head-axis point the cap's radial directions start from (head_normal)."""
    return Vector((0.0, HEAD_AXIS.y, min(p.z, HEAD_AXIS.z)))


# ---------------------------------------------------------------- shape master (round 10)
# The crown takes part of its shape from the shape master (levi/shape.py): on a
# grid of sheet-cap points (az, row), a ray cast in along the cap's radial
# direction (head_normal) finds the target's outermost hair surface, and the cap
# moves along that direction by
#     offset = FIT_STRENGTH(row) x weight x (target - FIT_INSET - sheet cap),
# smoothed to the mass (FIT_D_SMOOTH, then FIT_MASS_SMOOTH: the target's lock
# relief is left out, the procedural crown grooves stay).
#  - weight 1 where the target's outermost surface is front hair (or the head
#    label, which also covers bang surfaces over the face: the labels there come
#    from the nearest of our objects); 0 where the target's back hair is
#    outermost (hair_back owns that mass) and under the target's leaves and
#    flowers (ours sit there); smoothed (FIT_W_SMOOTH) and faded out below the
#    crown over FIT_ROWS (the face, the fringe, the hanging locks and the back
#    hair take over there; the sheet cap stays under them).
#  - FIT_STRENGTH: the target's crown is lower and flatter than ours (2-3 cm at
#    the front top); in pairwise review the full fit (and every stronger variant)
#    lost to the rounder sheet dome; this setting (a quarter of the way at the
#    apex, half from row 40) still lost 0-26 with both models.
#  - FIT is therefore off (round 10 decision: naturalness ranks above fidelity):
#    the cap, CAP_PROFILE (= CAP_PROFILE_SHEET) and everything on it are main's,
#    and no fit table is computed. FIT = True turns the reshape back on.
# Everything that sits on the cap (the fringe roots, ahoge, the side locks'
# roots) moves with the same offset field (cap_shift), and the cap is kept
# FACE_CLEAR off the forehead (_clear_face).
FIT = False                     # round 10 decision: off (see the note above)
FIT_AZ = 256                    # grid sections (the cap itself: CAP_AZ)
FIT_ROW_STEP = 1.0              # px
FIT_LABELS = ('hair_front', 'head')
FIT_REACH = 0.06                # m: rays start this far outside the sheet cap
FIT_ROWS = (72.0, 94.0)         # weight 1 above, 0 below
FIT_INSET = 0.0015              # m under the target (the settled roots, the outline)
FIT_STRENGTH = ((14.0, 0.25), (40.0, 0.5))   # (row, share of the way to the target)
FIT_W_SMOOTH = (6.0, 3.0)       # deg, rows (Gaussian sigma on the weight)
FIT_D_SMOOTH = (1.6, 1.0)       # deg, rows (on the raw offset)
FIT_MASS_SMOOTH = (8.0, 5.0)    # deg, rows (on the offset applied: the mass only)
FACE_ROWS = (44.0, 102.0)       # rows where the cap is kept off the forehead ...
FACE_FADE = 6.0                 # (fading in / out over the first / last rows)
FACE_CLEAR = 0.002              # ... by this much (m)
APEX_ROWS = 9.0                 # rows below the apex over which the offset leaves the ring mean

_FIT = {}


def _gauss_ring_rows(a, s_az, s_row, step_az, step_row):
    """Gaussian blur of a (rows, az) table: circular along az, clamped along rows."""
    import numpy as np
    out = np.asarray(a, dtype=np.float64)
    for axis, s, step, circ in ((1, s_az, step_az, True), (0, s_row, step_row, False)):
        sig = s / step
        if sig <= 0:
            continue
        k = int(math.ceil(3 * sig))
        w = np.exp(-0.5 * (np.arange(-k, k + 1) / sig) ** 2)
        w /= w.sum()
        if circ:
            pad = np.concatenate([out[:, -k:], out, out[:, :k]], axis=1) if k else out
            out = sum(w[i] * pad[:, i:i + out.shape[1]] for i in range(2 * k + 1))
        else:
            pad = np.concatenate([np.repeat(out[:1], k, 0), out, np.repeat(out[-1:], k, 0)], axis=0)
            out = sum(w[i] * pad[i:i + out.shape[0]] for i in range(2 * k + 1))
    return out


def _fit_table():
    """(rows, az, offset (m), sheet points, sheet normals) on the fit grid,
    computed once from the shape master."""
    if 'tab' in _FIT:
        return _FIT['tab']
    import numpy as np
    from .. import shape
    rows = np.arange(CAP_TOP[0], CAP_BOTTOM[0] + 1e-6, FIT_ROW_STEP)
    azs = -90.0 + 360.0 * np.arange(FIT_AZ) / FIT_AZ
    nr, na = len(rows), len(azs)
    pts = np.zeros((nr, na, 3))
    nrm = np.zeros((nr, na, 3))
    rad = np.zeros((nr, na))
    for i, r in enumerate(rows):
        for j, a in enumerate(azs):
            p = sheet_point(a, r)
            d = p - _axis_foot(p)
            pts[i, j] = p
            rad[i, j] = d.length
            nrm[i, j] = d.normalized() if d.length > 1e-9 else (0.0, 0.0, 1.0)
    if not FIT:
        _FIT['tab'] = (rows, azs, np.zeros((nr, na)), pts, nrm)
        return _FIT['tab']
    foot = pts - nrm * rad[..., None]
    reach = rad + FIT_REACH
    hit, dist, _n, who = shape.ray(None, (foot + nrm * reach[..., None]).reshape(-1, 3),
                                   (-nrm).reshape(-1, 3), max_d=float(reach.max()) + 0.01, occluders=False)
    r_t = (reach.reshape(-1) - dist).reshape(nr, na)
    who = np.array([w or '' for w in who]).reshape(nr, na)
    r_t[~(r_t > 0.02)] = np.nan              # (a miss, or through to the far side)
    hair = np.isin(who, FIT_LABELS) & np.isfinite(r_t)
    step_az = 360.0 / FIT_AZ
    wt = _gauss_ring_rows(hair.astype(np.float64), FIT_W_SMOOTH[0], FIT_W_SMOOTH[1], step_az, FIT_ROW_STEP)
    wt = np.clip((wt - 0.15) / 0.7, 0.0, 1.0)
    wt = wt * wt * (3 - 2 * wt)
    wt *= (1.0 - shape.smoothstep(FIT_ROWS[0], FIT_ROWS[1], rows))[:, None]
    raw = np.where(hair, r_t, np.nan) - FIT_INSET - rad
    # offsets where the target is not hair: interpolated (they only matter where
    # the smoothed weight reaches over them)
    for i in range(nr):
        if np.isfinite(raw[i]).any():
            raw[i] = shape.fill_ring(raw[i])
        else:
            raw[i] = np.nan
    raw = np.nan_to_num(shape.fill_rows(raw, axis=0))
    raw = _gauss_ring_rows(raw, FIT_D_SMOOTH[0], FIT_D_SMOOTH[1], step_az, FIT_ROW_STEP)
    strength = np.interp(rows, [r for r, _ in FIT_STRENGTH], [k for _, k in FIT_STRENGTH])
    off = _gauss_ring_rows(strength[:, None] * wt * raw, FIT_MASS_SMOOTH[0], FIT_MASS_SMOOTH[1],
                           step_az, FIT_ROW_STEP)
    # the apex is one point: the ring mean there, blended out over APEX_ROWS
    a = shape.smoothstep(rows[0], rows[0] + APEX_ROWS, rows)[:, None]
    ring_mean = off.mean(axis=1, keepdims=True)
    off = ring_mean + a * (off - ring_mean)
    off = _clear_face(rows, pts, nrm, off)
    _FIT['tab'] = (rows, azs, off, pts, nrm)
    return _FIT['tab']


def _head_bvh():
    """BVH of unit `head`'s smooth surface (head.ring, a pure surface function)
    over its upper rings, closed at the crown."""
    from . import head as _head
    rows = list(_head.RING_ROWS)
    ang = _head.ring_angles(72)
    verts, faces = [], []
    for r in rows:
        verts += [tuple(p) for p in _head.ring(r, ang, detail=False)]
    n = len(ang)
    for i in range(len(rows) - 1):
        for j in range(n):
            k = (j + 1) % n
            faces.append((i * n + j, i * n + k, (i + 1) * n + k, (i + 1) * n + j))
    top = Vector(verts[0]) * 0.0
    for v in verts[:n]:
        top += Vector(v) / n
    verts.append(tuple(top))
    faces += [(len(verts) - 1, k, (k + 1) % n) for k in range(n)]
    return BVHTree.FromPolygons(verts, faces)


def _clear_face(rows, pts, nrm, off):
    """Keep the cap FACE_CLEAR outside unit `head`'s surface over FACE_ROWS (the
    fitted cap would otherwise sink into the forehead between the fringe tips):
    a smooth maximum, so it binds without a crease, faded out above the brows."""
    out = off.copy()
    bvh = _head_bvh()
    k = FACE_CLEAR / 2
    for i, r in enumerate(rows):
        if not FACE_ROWS[0] <= r <= FACE_ROWS[1]:
            continue
        fade = (smooth01((r - FACE_ROWS[0]) / FACE_FADE)
                * (1.0 - smooth01((r - FACE_ROWS[1] + FACE_FADE) / FACE_FADE)))
        for j in range(pts.shape[1]):
            p, n = Vector(pts[i, j]), Vector(nrm[i, j])
            foot = _axis_foot(p)
            far = foot + n * ((p - foot).length + 0.1)
            hit = bvh.ray_cast(far, -n, 0.2)
            if hit[0] is None:
                continue
            # offset that puts the cap there, never past the sheet cap (where the
            # sheet cap already tucked under the skin it stays there)
            t = min((hit[0] - p).dot(n) + FACE_CLEAR, 0.0)
            a = out[i, j]
            out[i, j] = a + fade * ((a + t + math.sqrt((a - t) ** 2 + k * k)) / 2 - a)
    return out


def _fit_lookup(az, row):
    """Bilinear lookup of the fit offset (m) at (az, row)."""
    if not FIT:
        return 0.0
    rows, azs, a = _fit_table()[:3]
    x = (row - rows[0]) / FIT_ROW_STEP
    i0 = int(max(0, min(len(rows) - 2, math.floor(x))))
    u = max(0.0, min(1.0, x - i0))
    y = ((az - azs[0]) / (360.0 / FIT_AZ)) % FIT_AZ
    j0 = int(math.floor(y)) % FIT_AZ
    j1 = (j0 + 1) % FIT_AZ
    v = y - math.floor(y)
    return float((a[i0, j0] * (1 - v) + a[i0, j1] * v) * (1 - u)
                 + (a[i0 + 1, j0] * (1 - v) + a[i0 + 1, j1] * v) * u)


def cap_point(az, row, grow=0.0):
    """Point on the cap surface. az: 0 = +X, -90 = front (-Y); row: panel row.

    The sheet cap moved along its radial direction by the shape-master offset.
    grow: outward offset in metres (radial from the head axis)."""
    p = sheet_point(az, row)
    n = p - _axis_foot(p)
    n = n.normalized() if n.length > 1e-9 else Vector((0.0, 0.0, 1.0))
    p = p + n * _fit_lookup(az, row)
    if grow:
        p = p + (p - _axis_foot(p)).normalized() * grow
    return p


def cap_shift(p):
    """Move a point placed against the sheet cap (a strand control point) with the
    cap: along head_normal by the fit offset at the nearest sheet-cap grid point
    (inverse-distance blend of the 4 nearest), so roots stay on the reshaped scalp
    and hanging points below the crown (offset 0) stay put."""
    if not FIT:
        return Vector(p)
    if 'kd' not in _FIT:
        from mathutils.kdtree import KDTree
        tab = _fit_table()
        pts = tab[3].reshape(-1, 3)
        kd = KDTree(len(pts))
        for k, q in enumerate(pts):
            kd.insert(q, k)
        kd.balance()
        _FIT['kd'] = (kd, tab[2].reshape(-1))
    kd, off = _FIT['kd']
    acc = wsum = 0.0
    for _co, k, d in kd.find_n(p, 4):
        w = 1.0 / max(d, 1e-4)
        acc += w * off[k]
        wsum += w
    p = Vector(p)
    return p + head_normal(p) * (acc / wsum if wsum else 0.0)


def _front_at(fx, row):
    """Front-half cap point on sheet row `row` whose x is fx (px): bisection in az."""
    w = _profile(row)[0]
    if w <= 1e-6:
        return cap_point(-90.0, row)
    lo, hi = -180.0, 0.0                 # front half: x rises from -w to +w
    x = max(-w, min(w, fx)) * PX
    for _ in range(40):
        mid = (lo + hi) / 2
        if cap_point(mid, row).x < x:
            lo = mid
        else:
            hi = mid
    return cap_point((lo + hi) / 2, row)


def cap_front_sc(fx, row):
    """Side-view column of the cap's front surface at front offset fx (px) and the
    height of panel row `row`. The fit offset moves cap points along head_normal,
    off their sheet row (on the dome mostly down), so the sheet row whose moved
    point lies at that height is solved for first."""
    z = (spec.SHEET_GROUND_Y - row) * PX
    r = row
    p = _front_at(fx, r)
    for _ in range(12):
        dz = p.z - z
        if abs(dz) < 1e-5:
            break
        r = max(CAP_TOP[0], min(CAP_BOTTOM[0], r + dz / PX))
        p = _front_at(fx, r)
    return p.y / PX + MID


PROFILE_DENSE_TO = 116.0       # CAP_PROFILE rows every 4 px above this row
PROFILE_LOG = None     # a list collects (row, containment growth) for diagnostics


def _measure_profile():
    """CAP_PROFILE of the reshaped cap: per sheet-table row, the half width and
    the front / back columns of its horizontal section, with the half width and
    the back column grown until the superellipse (CAP_EXP) on them contains the
    section's back half (hair_back's envelope sits ENV_OFF over that superellipse)."""
    import numpy as np
    tab = _fit_table()
    rows, azs, off, pts, nrm = tab
    new = pts + nrm * off[..., None]
    out = []
    # the reshaped apex can lie below the sheet table's first rows: start just
    # under it (denser over the dome), then the sheet rows
    top = spec.SHEET_GROUND_Y - float(new[0, 0, 2]) / PX
    # (every 4 rows down to the sheet rows past the fit, so hair_back's linear
    # lookup between them stays within its ENV_OFF over the reshaped cap)
    rows_out = ([top + d for d in (1.5, 4.0, 8.0, 13.0)]
                + [float(r) for r in np.arange(top + 17.0, PROFILE_DENSE_TO, 4.0)]
                + [r for r in _ROWS if r >= PROFILE_DENSE_TO])
    for R in rows_out:
        z = (spec.SHEET_GROUND_Y - R) * PX
        sec = []
        for j in range(len(azs)):
            zz = new[:, j, 2]               # falls with the row
            k = np.nonzero((zz[:-1] >= z) & (zz[1:] < z))[0]
            if not len(k):
                continue
            k = k[0]
            u = (zz[k] - z) / (zz[k] - zz[k + 1])
            sec.append(new[k, j] * (1 - u) + new[k + 1, j] * u)
        sec = np.array(sec)
        xs = np.abs(sec[:, 0]) / PX
        cols = sec[:, 1] / PX + MID
        w, f, b = float(xs.max()), float(cols.min()), float(cols.max())
        mid, hd = (f + b) / 2, (b - f) / 2
        back = cols > mid
        s = (xs[back] / w) ** CAP_EXP + ((cols[back] - mid) / hd) ** CAP_EXP
        k = float(s.max()) ** (1.0 / CAP_EXP) if len(s) else 1.0
        if k > 1.0:
            # grow about the section's middle: hair_back reads only the middle,
            # the half depth and the half width
            w, hd = w * k, hd * k
            f, b = mid - hd, mid + hd
        if PROFILE_LOG is not None:
            PROFILE_LOG.append((R, k))
        out.append((round(R, 2), round(w, 2), round(f, 2), round(b, 2)))
    return out


def __getattr__(name):
    # CAP_PROFILE is measured on the reshaped cap, on first use (hair_back
    # imports it); the shape master is only read inside Blender.
    if name == 'CAP_PROFILE':
        if 'profile' not in _FIT:
            _FIT['profile'] = _measure_profile() if FIT else [tuple(r) for r in CAP_PROFILE_SHEET]
        return _FIT['profile']
    raise AttributeError(name)


def _crown_frame(at=None):
    """(skull centre, whorl axis, forward and sideways unit vectors around it).
    at: the cap point function (default cap_point; sheet_point for the sheet cap)."""
    c = Vector((0.0, HEAD_AXIS.y, HEAD_AXIS.z))
    a = ((at or cap_point)(*CROWN_WHORL) - c).normalized()
    e1 = Vector((0.0, -1.0, 0.0))
    e1 = (e1 - a * e1.dot(a)).normalized()
    return c, a, e1, a.cross(e1).normalized()


def crown_groove(p, frame):
    """(inward depth in m, crown envelope 0..1) of the crown grooves at cap point p."""
    if CROWN_DEPTH <= 0:
        return 0.0, 0.0
    c, a, e1, e2 = frame
    d = p - c
    r = d.length
    u = d / r
    phi = math.acos(max(-1.0, min(1.0, u.dot(a))))
    row = spec.SHEET_GROUND_Y - p.z * spec.PX_PER_M
    env = smooth01((phi - CROWN_FADE_IN[0]) / (CROWN_FADE_IN[1] - CROWN_FADE_IN[0]))
    env *= 1.0 - smooth01((row - CROWN_FADE_ROWS[0]) / (CROWN_FADE_ROWS[1] - CROWN_FADE_ROWS[0]))
    if env <= 0:
        return 0.0, 0.0
    th = math.degrees(math.atan2(u.dot(e2), u.dot(e1)))
    ring = r * math.sin(phi)            # radius of the circle round the whorl axis
    g = 0.0
    for ang, share in CROWN_GROOVES:
        dth = abs((th - ang + 180.0) % 360.0 - 180.0)
        dist = ring * math.radians(dth)
        if dist < CROWN_HALF:
            g = max(g, share * 0.5 * (1 + math.cos(math.pi * dist / CROWN_HALF)))
    return CROWN_DEPTH * env * g, env


def _sheet_cap_bvh():
    """BVH of the sheet (procedural, unfitted) cap with its crown grooves: the
    cheek wisps settle on it (see build)."""
    frame = _crown_frame(sheet_point)
    verts, faces = [P(0, *CAP_TOP)], []
    rows = []
    for r0, r1 in zip(CAP_RINGS, CAP_RINGS[1:] + (None,)):
        rows.append(r0)
        if r1 is not None and r1 <= CROWN_RING_SPLIT[0] and r1 - r0 > CROWN_RING_SPLIT[1]:
            rows.append((r0 + r1) / 2)
    for r in rows:
        for i in range(CAP_AZ):
            p = sheet_point(-90 + 360.0 * i / CAP_AZ, r)
            verts.append(p - head_normal(p) * crown_groove(p, frame)[0])
    verts.append(P(0, *CAP_BOTTOM))
    n = CAP_AZ
    for i in range(n):
        k = (i + 1) % n
        faces.append((0, 1 + k, 1 + i))
        for j in range(len(rows) - 1):
            faces.append((1 + j * n + i, 1 + j * n + k, 1 + (j + 1) * n + k, 1 + (j + 1) * n + i))
        last = 1 + (len(rows) - 1) * n
        faces.append((last + i, last + k, len(verts) - 1))
    bm = bmesh.new()
    bv = [bm.verts.new(v) for v in verts]
    for fc in faces:
        bm.faces.new([bv[i] for i in fc])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return BVHTree.FromBMesh(bm)


def build_cap(col, mat):
    """The scalp cap. Returns (object, BVH of its surface) so the strands can
    settle their roots onto it. Round 9: the crown grooves (crown_groove) are
    carved in along head_normal, with more of the cap's own normal kept in them."""
    bm = bmesh.new()
    klay = _layer(bm, KEEP_ATTR, -1.0)
    frame = _crown_frame()

    def vert(p):
        dep, env = crown_groove(p, frame)
        v = bm.verts.new(p - head_normal(p) * dep)
        v[klay] = VOL_KEEP + (CROWN_KEEP - VOL_KEEP) * env
        return v
    top = vert(cap_point(-90.0, CAP_TOP[0]))
    bot = vert(P(0, *CAP_BOTTOM))
    rows = []
    for r0, r1 in zip(CAP_RINGS, CAP_RINGS[1:] + (None,)):
        rows.append(r0)
        if r1 is not None and r1 <= CROWN_RING_SPLIT[0] and r1 - r0 > CROWN_RING_SPLIT[1]:
            rows.append((r0 + r1) / 2)
    rings = [[vert(cap_point(-90 + 360.0 * i / CAP_AZ, r)) for i in range(CAP_AZ)]
             for r in rows]
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


def orient_outward(bm):
    """Round 10: recalc_face_normals orients each closed strand consistently but
    can pick the inside of a thin, curved crescent (a fringe clump lying close
    over the cap came out inside out: dark, with its outline hull inside). Flip
    every island whose enclosed (signed) volume is negative."""
    seen = set()
    for f0 in bm.faces:
        if f0 in seen:
            continue
        island, stack = [], [f0]
        seen.add(f0)
        while stack:
            f = stack.pop()
            island.append(f)
            for e in f.edges:
                for g in e.link_faces:
                    if g not in seen:
                        seen.add(g)
                        stack.append(g)
        vol = 0.0
        for f in island:
            vs = [v.co for v in f.verts]
            for a, b in zip(vs[1:], vs[2:]):
                vol += vs[0].dot(a.cross(b))
        if vol < 0:
            bmesh.ops.reverse_faces(bm, faces=island)


def finish(col, name, bm, mat, angle=70, keep=VOL_KEEP, line_min=None):
    """Mesh object from bm. toon_grad comes from the strands' own arc-length
    ramp (strand(grad=...)).

    keep: share of the strands' own normals in the custom normals (the rest is
    the smooth hair-volume normal, see volume_normal); strand(keep=...)
    overrides it per vertex.
    line_min: thin the outline where settle() buried a root (outline width
    x line_min there, full on the free strand); None = uniform outline."""
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    orient_outward(bm)
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
    w, f, b = _profile(row)
    u = min(1.0, abs(fx) / max(w, 1e-6))
    p = cap_shift(P(fx, row, (f + b) / 2 - (b - f) / 2 * (1 - u ** CAP_EXP) ** (1 / CAP_EXP)))
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
# Round 9 (the reference's strength: thick masses, not paper strips): the same
# layout, but the three primary locks (the central sweep and one over each eye)
# are ~4.2 cm wide at the root and the secondaries narrower; every clump is a
# crescent: last field = the strand's `thick` (m), and with BANG_BACK < 0 the
# underside is concave (convex top, hollow underside), so a primary is ~1 cm
# through its middle and thinner toward its edges, which curl back (wrap).
# (A rebuild as three wide primaries plus four small locks lost the pairwise
# front-view review: the eyes-level fringe read as fewer, blunter tips.)
BANG_CLUMPS = (
    (-3, -7, 129, 27, 7.0, 1.4, 0.32, 'in', 0.024),     # primary: central sweep, on top
    (5, 14, 108, 19, 4.0, 2.4, 0.4, 'in', 0.016),       # secondary right of the parting
    (-15, -25, 101, 27, 5.0, 2.2, 0.38, 'in', 0.022),   # primaries over the eyes, shorter,
    (19, 29, 97, 27, 5.5, 2.0, 0.4, 'in', 0.022),       # so the tip rows vary by ~3 cm
    (-29, -38, 114, 24, 6.0, 1.9, 0.5, 'out', 0.017),
    (31, 40, 110, 22, 6.5, 2.3, 0.5, 'out', 0.017),
    (35, 44, 124, 17, 3.5, 1.7, 0.55, 'temple', 0.014),  # past the outer eye corners
    (-37, -45, 126, 17, 3.5, 1.7, 0.55, 'temple', 0.014),
)
BANG_BACK = -0.15       # underside offset share (strand back=): < 0 = concave
BANG_WRAP = (0.22, 0.12)  # edge curl-back at the root and the tip (x width)
# The thicker crescent stands further out than round 8's 11.5 mm lens: the
# centreline moves back by this share of the extra outer half-thickness (px
# scale: root/forehead, mid-fringe, tip), so the fringe keeps its outline and
# the tips their gap to the face.
BANG_REF_HALF = 0.00575
BANG_SINK = (1.0, 0.7, 0.3)
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
    for fx0, fx1, row1, wpx, lift, rnd, tf, kind, thick in BANG_CLUMPS:
        outer = kind != 'in'
        sink = max(0.0, thick / 2 - BANG_REF_HALF) / PX     # px
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
        s0, s1, s2 = (k * sink for k in BANG_SINK)
        ctrl = [cap_front_point(fxr + (fx0 - fxr) * a + (fx1 - fx0) * b, row, g0 + g1 * lift - s0)
                for row, (g0, g1), a, b in zip(rows, ROOT_GROW, ROOT_FX, ROOT_FX_TIP)]
        emerge = _polyline_len(ctrl[:3]) * BANG_EMERGE
        ctrl += [P(fxm, 84, bulge + s0),
                 P(fxq, rowm, (bulge + tip) / 2 - 1 + s1),
                 P(fx1, row1, tip + s2)]
        # 16 sides on the broad clumps: a rounded centre ridge and flanks
        st = strand(bm, ctrl, wpx * PX, thick, segs=18, n=12 if outer or wpx < 20 else 16,
                    base_taper=0.7, tip_pow=0.75, ogive=rnd, tip_dense=0.35, normal=bang_normal,
                    tip_from=tf, back=BANG_BACK, wrap=BANG_WRAP[0], wrap_tip=BANG_WRAP[1], tip_thick=0.1,
                    thin=(0.45, 0.5), frame_smooth=0.08, keep=BANG_KEEP)
        settle(bm, st, cap_bvh, emerge, depth=1.2)


def ahoge(bm, cap_bvh):
    """Two crown tufts. They leave the scalp tangentially just behind the
    apex and curve forward and away from it, so the top reads as a tuft on a
    round crown rather than as the cap's own spike."""
    sh = cap_shift      # round 10: the tufts ride the reshaped crown
    st = strand(bm, [sh(P(-2, 34, 304)), sh(P(-2, 22, 292)), sh(P(-1, 15, 279)), sh(P(1, 11, 268)),
                     sh(P(3, 11, 261))],
                0.016, 0.007, segs=14, n=8, base_taper=0.6, tip_pow=0.8, ogive=1.6, tip_dense=0.4,
                tip_from=0.35, normal=lambda p: Vector((1, 0, 0)))
    settle(bm, st, cap_bvh, 14 * PX, depth=1.0)
    st = strand(bm, [sh(P(4, 36, 308)), sh(P(6, 25, 296)), sh(P(6, 19, 283)), sh(P(8, 17, 276))],
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
# Round 9: rerouted in front of the shoulder. Round 5-8's curl crossed the top of
# the shoulder at the arm's own depth (side col 276-292, the deltoid spans ~277-313)
# and hooked over the outer upper arm, so any raised arm (spin, high_kick, arms_up)
# swept up into it (15-20 % inside). Below row 150 it now comes forward over the
# front of the shoulder and hooks out in front of the arm's plane (CURL_FRONT px
# in front of round 8's path at the hook, eased in from CURL_FRONT_ROWS); the
# front view keeps the same outward flip at the shoulder line. CURL_FRONT = 0
# restores round 8's path.
CURL_PATH = ((60, 70, 282), (66, 100, 284), (64, 130, 285), (64, 150, 282), (72, 170, 277),
             (81, 183, 276), (90, 195, 280), (98, 205, 285), (106, 214, 290), (118, 220, 291),
             (127, 226, 292), (132, 233, 292), (131, 241, 292), (126, 246, 292), (120, 246, 292))
CURL_FRONT = 22.0
CURL_FRONT_ROWS = (170.0, 215.0)   # (it stays behind the long front lock above)
# ... and the hook hangs closer to the arm: its reach past CURL_IN[0] (front-view
# px) is scaled by CURL_IN[1], so the open loop does not float out over a raised
# or bent arm (pairwise review: "outward loops above the sleeves").
CURL_IN = (92.0, 0.9)
# The curl's broad side turns this far toward the front (lock_normal forward; round 8
# 1.2): in front of the shoulder a front-facing ribbon read as a thin strip in profile.
CURL_FORWARD = 0.7


def _curl_lock():
    pts = []
    for fx, row, sc in CURL_PATH:
        f = smooth01((row - CURL_FRONT_ROWS[0]) / (CURL_FRONT_ROWS[1] - CURL_FRONT_ROWS[0]))
        if fx > CURL_IN[0]:
            fx = CURL_IN[0] + (fx - CURL_IN[0]) * CURL_IN[1]
        pts.append((fx, row, sc - CURL_FRONT * f))
    return pts, 0.028


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


LOCK_SHIFT = (1.0, 1.0, 0.5)    # share of cap_shift on the root, the first and second points
ROOT_SINK = 5.0         # px the first control point is pushed into the cap
ROOT_BURY = (12, 4)     # extra root point: px back up along the cap, px into it
LOCK_EMERGE = 10.0      # px of arc past the first visible control point over
                        # which settle() lets the lock lift off the cap


def side_set(bm, defs, segs, thick, mirror, forward=1.2, lateral=False, cap_bvh=None, shift=True, **kw):
    """forward: how much the ribbons turn to face the front (0 = face out
    sideways, broad in the side view). Other keywords go to strand().

    The root is buried: an extra control point continues the lock back up
    along the cap (tangentially, just under its surface), so the narrow first
    rings sit inside it and the lock surfaces at a shallow angle; with
    cap_bvh the root rings are then pressed onto the cap (settle) up to
    LOCK_EMERGE px past the first visible control point. The strand's
    arc-length fractions (tip_from, grad, keep) include this hidden ~12-17 px
    root, so the visible ramps start a little earlier than the numbers; they
    are tuned per family.
    shift: move the root with the reshaped cap (cap_shift, LOCK_SHIFT)."""
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
        # round 10: the buried root and the first visible point ride the reshaped
        # cap of their own side (after mirroring); the rest of the lock keeps its path
        if shift:
            pts = [p.lerp(cap_shift(p), k) for p, k in zip(pts, LOCK_SHIFT)] + pts[len(LOCK_SHIFT):]
        emerge = _polyline_len(pts[:2]) + LOCK_EMERGE * PX
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
    # Round 10: the cheek wisps keep round 9's roots exactly (settled on the sheet
    # cap, no cap_shift): their roots at the temple moved ~4 mm with the reshaped cap
    # and that alone took their pen_frac in dance_heart / idol_dance@48 from 2.0-2.5%
    # (minor) to 3.2-3.8% (major). The fitted cap differs from the sheet cap there by
    # a few mm at most.
    sheet_bvh = _sheet_cap_bvh()

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
                 cap_bvh=sheet_bvh, shift=False, base_taper=0.2, swell=0.35, tip_pow=0.6, ogive=1.8, tip_dense=0.4,
                 tip_from=0.55, back=0.7, wrap=0.1, tip_thick=0.15, grad=(0.5, 1.0),
                 frame_smooth=0.08, thin=(0.6, 0.75), keep=LOCK_KEEP)
        side_set(bm, WISP_LOCKS, 16, 0.011, mirror, forward=0.6, n=10, cap_bvh=sheet_bvh, shift=False,
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
        side_set(bm, [_curl_lock()], 32, 0.018, mirror, forward=CURL_FORWARD, n=10, cap_bvh=cap_bvh,
                 base_taper=0.3, tip_pow=0.6, ogive=1.3, tip_from=0.3, tip_dense=0.3, back=0.85, tip_thick=0.15,
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
