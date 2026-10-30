"""Front and side hair: scalp cap, ahoge, bangs and the face-framing side locks.

Round 11: every strand is built by the shared hair kernel (_hair_kernel.py),
which applies the technique learnt from the 风堇 (Hyacine) model: crescent
sections (a convex top, a concave underside and thin rims), C2 centrelines held
to R >= max(12 mm, 0.6 w) and rho <= 0.45 (no sharp turns), adaptive rings,
strands that narrow before an end curl tightens, blade tips, and a validator
that fails the build on any strand past the limits. Overlapping clumps nest (an
upper clump rests on the ones below it) instead of cutting through each other.
The scalp cap is a grid around the crown whorl, so the crown's grooves run along
its columns as smooth pleats; its crown is a round dome (CROWN_DOME: the round-10
table made it a pointed tent), and the ahoge is two small pinches of the scalp
shell (AHOGE_PINCH), the way 风堇's model raises its forehead crescent out of the
hood, not tubes stood on the scalp. Roots are pressed into the cap along the smooth
radial direction (settle), and after that every strand's root ring must start
inside the cap and its surface turn at most SURFACE_TURN per ring outside it
(check_surface), so no root stands proud of the scalp or creases where it meets it.

Shapes are authored in reference-panel pixels so they can be fitted against
ref/{front,side}.png:  P(fx, row, sc)
    fx  = front-view column offset from the panel centre (+ = image right,
          i.e. the character's left, +X)
    row = panel row (shared by all views)
    sc  = side-view panel column (smaller = further forward, -Y)
The long hair below the shoulders is unit `hair_back`; leaves/flowers are
`accessories`. hair_back reads CAP_PROFILE / CAP_EXP (measurement data only).
"""
import math

import bmesh
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

from .. import common, spec
from . import _hair_kernel as hk

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
CAP_TOP_R10 = (14, 287)      # (row, side column) of the round-4..10 cap apex
CAP_TABLE_R10 = [
    # row, half-width, side front col, side back col
    # Round 4: the crown clumps that used to sit ~4 px proud of the cap are
    # gone, so the front of rows 17-50 moves forward by that much to keep the
    # sheet's crown outline; rows 72-86 are set back 2-3 px so the fringe over
    # them reads less like a visor (the forehead skin stays >= 10 px behind).
    # Round 5: rows 17-29 are ~1 px fuller so the crown closes as a dome.
    # (Round 11: the rows above 72 are replaced by the round crown, see CROWN_DOME.)
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
# Round 11 (crown): the old table's half widths over the crown grew linearly (row 17:
# 9 px, 20: 15, 24: 22, 29: 28 ... 60: 55), a tent with straight ~48 deg flanks and an
# apex radius of 13-19 px in the front and back views (the circle through the apex and
# the outline at +-45 px: 47 px), a ridge running front to back (3D apex radii 22 x 150
# mm): the head read pointed. The sheet's crown is a round dome (front / back outline:
# a circle of R 52-55 px) and so is 风堇's hood (apex radius ~0.9 x its half width).
# Rows above CROWN_DOME['blend'][1] now follow a superellipse quadrant
#     w(row) = W (1 - ((R - row) / (R - apex))^p)^(1/p)
# through the apex and (W, R) (p = 2: an ellipse of apex radius W^2 / (R - apex); a
# little over 2 flattens the very top, as the sheet draws it), blended into the
# measured rows over CROWN_DOME['blend']. Built: front / back outline apex radius
# 50 px against 54 px for the circle through the apex and the outline at +-45 px
# (round 10: 13-19 against 47), 3D apex radii 78 x 183 mm (check_cap_round). The
# outline stands 1.5-3 px outside the sheet's at +-20..40 px (round 10: 1-4 px inside
# it; p 2.1, W 64, R 100: 3-4 px outside). The apex drops from row 14 to 17 (the sheet:
# front ~17-18, side ~15-16); the side view keeps its dome (already round: apex radius
# ~100 px), its columns read on the old profile `shift` rows higher, shift = (apex - 14)
# fading out by row side_fade (so the front of the crown above the fringe stays where
# it was from row ~24 down). The skull (unit head) lies 4.4 cm under the old apex.
CROWN_DOME = dict(apex=17.0, p=2.05, w=58.0, row=84.0, blend=(60.0, 72.0), side_fade=26.0)
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


def _make_profile(top, table):
    """The profile function of a cap table: row -> (half width, side front col, side
    back col), a monotone cubic through the rows, closed above the first row by a sqrt
    dome with a vertical tangent at the apex `top` (row, side col)."""
    t = [r[0] for r in table]
    cols = [[r[c] for r in table] for c in (1, 2, 3)]
    slopes = [_pchip_slopes(t, c) for c in cols]
    apex = (0.0, top[1], top[1])     # half width, front col, back col at the apex

    def profile(row):
        if row <= t[0]:
            # dome: v = apex + a sqrt(d) + b d, matching value and slope at row t[0]
            d0 = t[0] - top[0]
            d = max(0.0, row - top[0])
            out = []
            for c, (ys, ms) in enumerate(zip(cols, slopes)):
                delta, s = ys[0] - apex[c], ms[0]
                a = (delta - d0 * s) / (math.sqrt(d0) / 2)
                b = s - a / (2 * math.sqrt(d0))
                out.append(apex[c] + a * math.sqrt(d) + b * d)
            return tuple(out)
        if row >= t[-1]:
            return tuple(c[-1] for c in cols)
        i = next(k for k in range(len(t) - 1) if row <= t[k + 1])
        h = t[i + 1] - t[i]
        u = (row - t[i]) / h
        h00, h10 = 2 * u ** 3 - 3 * u ** 2 + 1, u ** 3 - 2 * u ** 2 + u
        h01, h11 = -2 * u ** 3 + 3 * u ** 2, u ** 3 - u ** 2
        return tuple(h00 * ys[i] + h10 * h * ms[i] + h01 * ys[i + 1] + h11 * h * ms[i + 1]
                     for ys, ms in zip(cols, slopes))
    return profile


# rows of the round crown in CAP_PROFILE (denser than the old table near the apex, so
# the cubic, and hair_back's piecewise-linear lookup of it, follow the dome)
CROWN_ROWS = (17.5, 18.5, 20.0, 22.0, 24.0, 26.5, 29.0, 32.0, 35.0, 38.5, 42.0, 46.0, 50.0,
              55.0, 60.0, 66.0, 72.0)


def _crown_table():
    """CAP_PROFILE_SHEET: CAP_TABLE_R10 with the rows above CROWN_DOME['blend'][1]
    replaced by the round crown (see CROWN_DOME)."""
    D = CROWN_DOME
    apex, p, W, R = D['apex'], D['p'], D['w'], D['row']
    b0, b1 = D['blend']
    old = _make_profile(CAP_TOP_R10, CAP_TABLE_R10)
    out = []
    for r in (r for r in CROWN_ROWS if r > apex + 0.25):
        u = (R - r) / (R - apex)
        w = W * (1.0 - u ** p) ** (1.0 / p)
        k = smooth01((r - b0) / (b1 - b0))
        w = w * (1.0 - k) + old(r)[0] * k
        shift = (apex - CAP_TOP_R10[0]) * (1.0 - smooth01((r - apex) / (D['side_fade'] - apex)))
        _w, f, bk = old(r - shift)
        out.append((r, round(w, 2), round(f, 2), round(bk, 2)))
    return out + [tuple(t) for t in CAP_TABLE_R10 if t[0] > b1]


CAP_TOP = (CROWN_DOME['apex'], CAP_TOP_R10[1])     # (row, side column) of the cap apex
CAP_PROFILE_SHEET = _crown_table()
_ROWS = [r[0] for r in CAP_PROFILE_SHEET]
_profile = _make_profile(CAP_TOP, CAP_PROFILE_SHEET)
_profile.__doc__ = """(half width, side front col, side back col) of the sheet (procedural) cap at `row`."""
_profile_r10 = _make_profile(CAP_TOP_R10, CAP_TABLE_R10)


def crown_widen(row):
    """Half width of the round crown over the round-10 cap's at `row` (1 below the crown):
    the fringe's root stations scale their front offset by it, so they keep their place
    on the dome (round 11 crown: unscaled, the temple clumps' roots moved from the side of
    the head to its front and the clumps shortened 213 -> 180 mm)."""
    if row >= CROWN_DOME['blend'][1]:
        return 1.0
    return _profile(row)[0] / max(_profile_r10(row)[0], 1e-6)


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



# ---------------------------------------------------------------- scalp cap (round 11)
# Round 9-10 carved the crown grooves into a latitude-longitude grid around the
# vertical axis; the grooves radiate from the whorl, so they crossed the grid
# diagonally and were sampled as staircases (zig-zag shade streaks, the jagged
# crown of the round-11 analysis, D10). Round 11 builds the cap on a grid around
# the whorl axis instead: rings of constant polar angle from the whorl (CAP_PHI),
# spokes of constant angle round it (CAP_SPOKE...), denser across each groove and
# with a spoke on every groove line. A groove therefore runs along a column of
# the grid as a smooth pleat. The surface itself is the sheet cap (CAP_PROFILE,
# unchanged): every grid vertex is cast from the skull centre onto a dense mesh
# of sheet_point() (outermost hit), then the grooves are carved in along
# head_normal as before. The whorl and the point opposite it (under the cap,
# inside the head) are the two poles.
CAP_RAY_ROW = 1.0               # px between rows of the dense sheet mesh the grid is cast onto
CAP_RAY_AZ = 288                # ... and its sections
CAP_PHI_CROWN = (0.035, 1.45, 24)   # rad from the whorl: first ring, end of the visible crown, rings
CAP_PHI_LOW = 10                # rings from there to the lower pole (hidden under the hair and head)
CAP_SPOKE = 7.5                 # deg between spokes away from the grooves ...
CAP_SPOKE_GROOVE = 2.5          # ... and across a groove, CAP_SPOKE_BAND deg either side of its line
CAP_SPOKE_BAND = 5.0
# Under the fringe the cap is a hidden layer: it is carved in by CAP_RECESS (m) over
# the front sector (CAP_RECESS_AZ deg either side of the face, fading out over the
# next CAP_RECESS_AZ_FADE) between CAP_RECESS_ROWS (fading in / out over
# CAP_RECESS_FADE rows), so the clumps' concave undersides and rims rest on it
# instead of sinking into it (round 11 first build: 10-23 % of the eye primaries'
# and outer clumps' vertices past their roots lay inside the cap). The cap only
# shrinks, so CAP_PROFILE stays an envelope of it (hair_back reads the table).
CAP_RECESS = 0.008
CAP_RECESS_AZ = (60.0, 25.0)
CAP_RECESS_ROWS = (58.0, 112.0)
CAP_RECESS_FADE = 10.0


def cap_recess(p):
    """Inward depth (m) of the fringe recess at cap point p."""
    if CAP_RECESS <= 0:
        return 0.0
    row = spec.SHEET_GROUND_Y - p.z * spec.PX_PER_M
    w = smooth01((row - CAP_RECESS_ROWS[0]) / CAP_RECESS_FADE)
    w *= 1.0 - smooth01((row - CAP_RECESS_ROWS[1]) / CAP_RECESS_FADE)
    if w <= 0:
        return 0.0
    ang = math.degrees(math.atan2(abs(p.x), -(p.y - HEAD_AXIS.y)))
    w *= 1.0 - smooth01((ang - CAP_RECESS_AZ[0]) / CAP_RECESS_AZ[1])
    return CAP_RECESS * w

_CAP = {}


def _sheet_rows():
    rows = list(np.arange(CAP_TOP[0] + 0.25, CAP_RINGS[-1], CAP_RAY_ROW)) + [CAP_RINGS[-1]]
    return [float(r) for r in rows]


def _sheet_mesh():
    """(verts, faces) of the dense, ungrooved sheet cap (closed)."""
    if 'sheet' in _CAP:
        return _CAP['sheet']
    rows = _sheet_rows()
    n = CAP_RAY_AZ
    verts = [tuple(P(0, *CAP_TOP))]
    for r in rows:
        verts += [tuple(sheet_point(-90 + 360.0 * i / n, r)) for i in range(n)]
    verts.append(tuple(P(0, *CAP_BOTTOM)))
    faces = []
    for i in range(n):
        k = (i + 1) % n
        faces.append((0, 1 + k, 1 + i))
        for j in range(len(rows) - 1):
            faces.append((1 + j * n + i, 1 + j * n + k, 1 + (j + 1) * n + k, 1 + (j + 1) * n + i))
        last = 1 + (len(rows) - 1) * n
        faces.append((last + i, last + k, len(verts) - 1))
    _CAP['sheet'] = (verts, faces)
    return _CAP['sheet']


def _sheet_bvh():
    """BVH of the dense, ungrooved sheet cap (a side lock with bvh='sheet' settles on it;
    rounds 9-10 and the first round-11 build settled the cheek locks and wisps there)."""
    if 'sheet_bvh' not in _CAP:
        verts, faces = _sheet_mesh()
        bm = bmesh.new()
        bv = [bm.verts.new(v) for v in verts]
        for fc in faces:
            bm.faces.new([bv[i] for i in fc])
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        _CAP['sheet_bvh'] = BVHTree.FromBMesh(bm)
        bm.free()
    return _CAP['sheet_bvh']


def cap_spokes():
    """Spoke angles (deg, round the whorl axis, 0 = toward the face, + toward +X)."""
    G, B, S = CAP_SPOKE_GROOVE, CAP_SPOKE_BAND, CAP_SPOKE
    dense = set()
    for ang, _share in CROWN_GROOVES:
        for k in range(-int(round(B / G)), int(round(B / G)) + 1):
            dense.add(round(((ang + k * G + 180.0) % 360.0) - 180.0, 6))
    dense = sorted(dense)
    out = []
    for a, b in zip(dense, dense[1:] + [dense[0] + 360.0]):
        gap = b - a
        m = max(1, int(math.ceil(gap / S - 1e-6)))
        out += [a + gap * i / m for i in range(m)]
    return [((a + 180.0) % 360.0) - 180.0 for a in out]


def cap_rings():
    """Ring polar angles (rad from the whorl axis)."""
    p0, p1, k = CAP_PHI_CROWN
    top = list(np.linspace(p0, p1, k))
    step = (math.pi - p1) / (CAP_PHI_LOW + 1)
    return top + [p1 + step * (i + 1) for i in range(CAP_PHI_LOW)]


def _cast(bvh, c, d):
    """Outermost hit of the line c + t d (t > 0) on bvh, cast inward from 0.4 m out."""
    hit = bvh.ray_cast(c + d * 0.4, -d, 0.45)
    if hit[0] is None:
        raise RuntimeError(f'hair_front cap: no sheet-cap hit along {tuple(d)}')
    return hit[0]


def cap_grid():
    """(whorl point, rings (R, S) of Vectors on the grooved cap, lower pole) and the
    groove envelope per vertex (for the normal blend)."""
    if 'grid' in _CAP:
        return _CAP['grid']
    verts, faces = _sheet_mesh()
    bvh = BVHTree.FromPolygons(verts, faces)
    frame = _crown_frame()
    c, a, e1, e2 = frame
    spokes = [math.radians(t) for t in cap_spokes()]
    rings, envs = [], []
    for ph in cap_rings():
        ring, env = [], []
        for th in spokes:
            d = a * math.cos(ph) + (e1 * math.cos(th) + e2 * math.sin(th)) * math.sin(ph)
            p = _cast(bvh, c, d.normalized())
            dep, ev = crown_groove(p, frame)
            ring.append(p - head_normal(p) * (dep + cap_recess(p)))
            env.append(ev)
        rings.append(ring)
        envs.append(env)
    top = _cast(bvh, c, a)
    bot = _cast(bvh, c, -a)
    _CAP['grid'] = (top, rings, bot, envs)
    return _CAP['grid']


def build_cap(col, mat):
    """The scalp cap on the whorl grid. Returns (object, BVH of its surface): the
    strands settle their roots onto it."""
    top, rings, bot, envs = cap_grid()
    bm = bmesh.new()
    klay = _layer(bm, KEEP_ATTR, -1.0)

    def vert(p, env):
        v = bm.verts.new(p)
        v[klay] = VOL_KEEP + (CROWN_KEEP - VOL_KEEP) * env
        return v
    vt = vert(top, 0.0)
    vb = vert(bot, 0.0)
    vr = [[vert(p, e) for p, e in zip(r, er)] for r, er in zip(rings, envs)]
    S = len(vr[0])
    for i in range(S):
        k = (i + 1) % S
        bm.faces.new((vt, vr[0][i], vr[0][k]))
        for ra, rb in zip(vr, vr[1:]):
            bm.faces.new((ra[i], rb[i], rb[k], ra[k]))
        bm.faces.new((vr[-1][i], vb, vr[-1][k]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if bm.calc_volume(signed=True) < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces)
    bvh = BVHTree.FromBMesh(bm)
    return finish(col, 'hair_cap', bm, mat, angle=80, recalc=False), bvh


def cap_profile_error():
    """How far (m) the built cap stands outside CAP_PROFILE's superellipses (hair_back's
    envelope sits ENV_OFF over them): max over the cap vertices above the lowest row."""
    top, rings, bot, _ = cap_grid()
    prof = __getattr__('CAP_PROFILE')
    rows = [r[0] for r in prof]
    worst = 0.0
    for ring in rings:
        for p in ring:
            row = spec.SHEET_GROUND_Y - p.z * spec.PX_PER_M
            if not rows[0] <= row <= rows[-1]:
                continue
            i = max(0, min(len(rows) - 2, next((k for k in range(len(rows) - 1) if row <= rows[k + 1]), 0)))
            u = (row - rows[i]) / (rows[i + 1] - rows[i])
            w, f, b = (prof[i][c] * (1 - u) + prof[i + 1][c] * u for c in (1, 2, 3))
            mid, hd = (f + b) / 2, (b - f) / 2
            x = abs(p.x) * spec.PX_PER_M
            y = p.y * spec.PX_PER_M + MID - mid
            k = ((x / w) ** CAP_EXP + (abs(y) / hd) ** CAP_EXP) ** (1.0 / CAP_EXP)
            worst = max(worst, (k - 1.0) * min(w, hd) * PX)
    return worst


# Round 11 (crown): build-time roundness checks on the built cap (the round-10 cap was a
# tent: outline apex radius 13-19 px against a 47 px circle, 3D apex radii 22 x 150 mm).
#  - front / back outline: its apex radius (a parabola fitted over |x| <= CAP_ROUND_HALF
#    px) at least CAP_ROUND_MIN x the radius of the circle through the apex and the
#    outline at +-CAP_ROUND_AT px;
#  - 3D: the apex's principal radii (a quadric fitted to the cap within CAP_APEX_FIT m
#    of its highest point) no more than 1 : 1 / CAP_APEX_ASPECT_MIN apart (no ridge).
CAP_ROUND_HALF = 15.0
CAP_ROUND_AT = 45.0
CAP_ROUND_MIN = 0.85
CAP_APEX_FIT = 0.015
CAP_APEX_ASPECT_MIN = 0.4


def _cap_top_z(bvh, x, y):
    """Height (m) of the cap's top surface over (x, y), or None."""
    hit = bvh.ray_cast(Vector((x, y, 2.5)), Vector((0.0, 0.0, -1.0)), 2.0)
    return None if hit[0] is None else hit[0].z


def check_cap_round(bvh):
    """The cap's crown roundness (see above); raises past the limits."""
    xs = np.arange(-CAP_ROUND_AT - 3.0, CAP_ROUND_AT + 3.01, 0.5)              # px
    ys = (np.arange(200.0, 380.0, 0.5) - MID) * PX                              # m
    out = []
    for x in xs:
        zs = [_cap_top_z(bvh, x * PX, y) for y in ys]
        zs = [z for z in zs if z is not None]
        out.append(max(zs) * spec.PX_PER_M if zs else np.nan)
    z = np.array(out)                                     # px, up
    ia = int(np.nanargmax(z))
    xa, za = xs[ia], z[ia]
    sel = np.isfinite(z) & (np.abs(xs - xa) <= CAP_ROUND_HALF)
    c2 = np.polyfit(xs[sel] - xa, z[sel], 2)[0]
    r_apex = -1.0 / (2.0 * c2) if c2 < 0 else float('inf')
    rc = []
    for side in (-1.0, 1.0):
        k = int(np.argmin(np.abs(xs - side * CAP_ROUND_AT)))
        dx, dz = abs(xs[k] - xa), za - z[k]
        rc.append((dx * dx + dz * dz) / (2.0 * dz))
    r_circle = float(np.mean(rc))
    # 3D apex: highest point, then a quadric z = c + g.(x, y) + (x, y) Q (x, y)^T around it
    yb = None
    zb = -1.0
    for y in ys:
        zz = _cap_top_z(bvh, xa * PX, y)
        if zz is not None and zz > zb:
            zb, yb = zz, y
    g = np.linspace(-CAP_APEX_FIT, CAP_APEX_FIT, 21)
    rows = []
    for dx in g:
        for dy in g:
            if dx * dx + dy * dy > CAP_APEX_FIT ** 2:
                continue
            zz = _cap_top_z(bvh, xa * PX + dx, yb + dy)
            if zz is not None:
                rows.append((dx * dx, dx * dy, dy * dy, dx, dy, 1.0, zz))
    M = np.array(rows)
    (qa, qb, qc, _gx, _gy, _c), *_ = np.linalg.lstsq(M[:, :6], M[:, 6], rcond=None)
    lam, vec = np.linalg.eigh(np.array([[qa, qb / 2], [qb / 2, qc]]))
    radii = [-1.0 / (2.0 * l) if l < 0 else float('inf') for l in lam]
    across = radii[int(np.argmax(np.abs(vec[0])))]        # principal direction nearer x
    along = radii[1 - int(np.argmax(np.abs(vec[0])))]
    res = dict(apex_row=spec.SHEET_GROUND_Y - za, r_apex=r_apex, r_circle=r_circle, ratio=r_apex / r_circle,
               r_across=across, r_along=along, aspect=min(radii) / max(radii))
    if res['ratio'] < CAP_ROUND_MIN:
        raise hk.HairKernelError(f"hair_front cap: the crown's outline apex radius is {res['ratio']:.2f} x "
                                 f"its circle's (< {CAP_ROUND_MIN}): a pointed head")
    if res['aspect'] < CAP_APEX_ASPECT_MIN:
        raise hk.HairKernelError(f"hair_front cap: apex radii {1000 * across:.0f} x {1000 * along:.0f} mm "
                                 f"(ratio {res['aspect']:.2f} < {CAP_APEX_ASPECT_MIN}): a ridge")
    return res


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
KEEP_ATTR = 'hf_keep'   # per-vertex `keep` (strand attrs)
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
    the KEEP_ATTR attribute where a strand wrote one >= 0 (it is then removed)."""
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


def head_normal(p):
    """Outward direction used to orient ribbons: radial from the cap centre
    above it, horizontal-radial from the head axis below it."""
    q = Vector((0.0, HEAD_AXIS.y, min(p.z, HEAD_AXIS.z)))
    n = p - q
    if n.length < 1e-6:
        return Vector((0, -1, 0))
    return n.normalized()


def _layer(bm, name, default):
    """A float vertex layer; vertices made before it existed get `default`."""
    lay = bm.verts.layers.float.get(name)
    if lay is None:
        lay = bm.verts.layers.float.new(name)
        for v in bm.verts:
            v[lay] = default
    return lay


def finish(col, name, bm, mat, angle=70, keep=VOL_KEEP, line_min=None, recalc=False):
    """Mesh object from bm (the kernel emits outward-facing closed strands;
    recalc re-derives the orientation for other meshes). toon_grad comes from
    the strands' own arc-length ramp (kernel grad).

    keep: share of the strands' own normals in the custom normals (the rest is
    the smooth hair-volume normal, see volume_normal); a strand's KEEP_ATTR
    overrides it per vertex.
    line_min: thin the outline where settle() buried a root (outline width
    x line_min there, full on the free strand); None = uniform outline."""
    if recalc:
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


# ---------------------------------------------------------------- kernel glue (round 11)
# Every strand is built by the shared kernel (_hair_kernel): a C2 centreline held
# to R >= max(12 mm, 0.6 w) and rho <= 0.45, rotation-minimising frames with a
# rate-limited roll, crescent sections (convex top, concave underside, thin rims),
# adaptive rings, grown end curls and split tips. hk.strand() validates every
# strand (turn <= 8 deg / ring, rho <= 0.5, no folded quads, twist <= 10 deg / ring,
# ring gap <= 10 mm) and raises HairKernelError naming the strand; settle() below
# re-validates after pressing a root into the scalp. Overlapping clumps are nested
# with hk.strand_on() (the upper clump's underside rests on the lower's top + a gap)
# instead of cutting through each other.
def A(v):
    return np.array((float(v[0]), float(v[1]), float(v[2])))


def Vv(a):
    return Vector((float(a[0]), float(a[1]), float(a[2])))


def facing_fn(fn):
    """A mathutils facing function as a kernel facing callable."""
    return lambda p: A(fn(Vv(p)))


def keep_attr(keep):
    """KEEP_ATTR value per vertex: (root, tip, u0, u1) eased over the arc fraction,
    or None (the object's default)."""
    if keep is None:
        return -1.0
    k0, k1, t0, t1 = keep
    return lambda p, u: k0 + (k1 - k0) * float(hk.smooth01((u - t0) / (t1 - t0)))


SETTLE_SQUASH = 0.35
LOG = []                # per-strand summary lines (printed by build)
STATS = {}              # object -> [vertices, vertices buried in the cap past the root]


def _cap_height(bvh, q):
    """(height of q over the cap along head_normal(q), that direction): the cap is hit by
    a ray cast in along the smooth radial direction, not at its nearest point (round 11
    first build: the nearest point jumped between the faces of a crown groove, and the
    roots pressed onto it creased 23-100 deg across the groove, D-review p3)."""
    n = head_normal(q)
    hit = bvh.ray_cast(q + n * 0.05, -n, 0.12)
    if hit[0] is None:
        return None, n
    return (q - hit[0]).dot(n), n


def settle(st, bvh, emerge, depth=1.5, squash=SETTLE_SQUASH, line=True):
    """Press a strand's root onto the cap so it grows out of the scalp.

    Over the first `emerge` metres of arc every ring vertex's height over the cap
    surface (along the smooth radial direction head_normal) is eased from
    squash * h - depth (the section flattened and just buried) to its own h
    (smoothstep): the clump surfaces as one soft ridge, middle first, without a cut.
    The outline weight (LINE_ATTR) is 0 until the root is LINE_ON of the way out,
    then rises to 1. Ring vertices only (the spine, frames and the sections' layout
    stay), then the strand is validated again."""
    R = st.rings
    lw = np.ones(R.shape[:2])
    for j in range(len(R)):
        a = float(st.arc[j])
        if a >= emerge:
            break
        s = float(hk.smooth01(a / emerge))
        for k in range(R.shape[1]):
            q = Vv(R[j, k])
            h, nrm = _cap_height(bvh, q)
            if h is None:
                continue
            h2 = min(h, s * h + (1 - s) * (squash * h - depth * PX))
            R[j, k] = A(q + nrm * (h2 - h))
        lw[j] = float(hk.smooth01((s - LINE_ON) / LINE_RAMP))
    if line:
        st.attrs[LINE_ATTR] = lw
        st.attrs_apex[LINE_ATTR] = 1.0
    st.meta['emerge'] = emerge
    hk.validate(st)
    return st


_RAYS = (Vector((0.0, 0.0, 1.0)), Vector((0.6, 0.0, -0.8)), Vector((-0.5, 0.7, 0.5)).normalized())


def _inside(bvh, p):
    """Point inside the closed mesh of bvh (ray parity, majority of 3 directions)."""
    votes = 0
    for d in _RAYS:
        n, q = 0, Vector(p)
        for _ in range(16):
            hit = bvh.ray_cast(q, d, 1.0)
            if hit[0] is None:
                break
            n += 1
            q = hit[0] + d * 1e-6
        votes += n % 2
    return votes >= 2


def _inside_flags(st, cap_bvh):
    """[(tube, (rings, n) bool: vertex inside the cap)] of a strand."""
    out = []
    for tb in st.all_tubes():
        f = np.array([[_inside(cap_bvh, Vv(p)) for p in ring] for ring in tb.rings], dtype=bool)
        out.append((tb, f))
    return out


def buried(st, cap_bvh, flags=None):
    """(vertices, vertices inside the cap past the root's emergence) of a strand: the
    burial beyond the designed root (round 10: 14-73 % of each hair_front object's
    vertices lay inside the cap or another lock)."""
    em = st.meta.get('emerge', 0.0)
    tot = bad = 0
    for tb, f in (flags or _inside_flags(st, cap_bvh)):
        tot += f.size
        bad += int(f[np.asarray(tb.arc) > em].sum())
    return tot, bad


# Post-settle surface checks (round 11 review): the kernel validates the spine; pressing
# a root into the cap moves ring vertices one by one, so the surface itself is checked
# too: every strand's root ring starts inside the cap (no flat-cut stump standing proud
# of it, ROOT_INSIDE), and along every column of the rings outside the cap the surface
# line turns at most SURFACE_TURN deg per ring (no crease where a root meets the scalp).
ROOT_INSIDE = 1.0       # share of the root ring's vertices inside the cap
SURFACE_TURN = 20.0     # deg


def surface_turn(tb, flags):
    """(largest turn (deg) of a ring column's surface line at a vertex outside the cap,
    the arc (m) of that ring)."""
    R = np.asarray(tb.rings)
    if len(R) < 3:
        return 0.0, 0.0
    e = np.diff(R, axis=0)                                   # (rings - 1, n, 3)
    ln = np.linalg.norm(e, axis=2)
    ok = (ln[:-1] > 1e-6) & (ln[1:] > 1e-6)
    c = np.sum(e[:-1] * e[1:], axis=2) / np.maximum(ln[:-1] * ln[1:], 1e-12)
    ang = np.degrees(np.arccos(np.clip(c, -1.0, 1.0)))
    ang[~ok | flags[1:-1]] = 0.0
    if not ang.size:
        return 0.0, 0.0
    j = int(np.unravel_index(int(ang.argmax()), ang.shape)[0])
    return float(ang.max()), float(np.asarray(tb.arc)[j + 1])


def check_surface(st, cap_bvh, flags):
    """(root ring share inside the cap, worst surface turn outside it); raises past the limits."""
    tb0, f0 = flags[0]
    root = float(f0[0].mean())
    turn, at = max(surface_turn(tb, f) for tb, f in flags)
    st.meta.update(root_inside=root, surface_turn=turn, surface_turn_at=at)
    if CHECK_SURFACE and root < ROOT_INSIDE:
        raise hk.HairKernelError(f'{st.name}: {100 * (1 - root):.0f} % of its root ring stands outside the cap')
    if CHECK_SURFACE and turn > SURFACE_TURN:
        raise hk.HairKernelError(f'{st.name}: its surface turns {turn:.1f} deg between two rings outside the cap')
    return root, turn


CHECK_SURFACE = True


# Nesting (round 11). hk.strand_on() lifts a strand wherever a line along its section
# normal from its underside meets a lower strand within reach, which also lifts it
# over a neighbour lying BESIDE it when its facing tilts toward that neighbour (the
# side locks round the head: 2-4 cm). nested() lifts only where the underside really
# lies inside a lower strand (odd crossings ahead along N, per lower strand), by the
# distance to that strand's top plus NEST_GAP, smoothed along the arc and faded in
# from the root; the spine moves, never single vertices.
NEST_GAP = 0.0008       # m left between a strand's underside and the strand below it
NEST_SMOOTH = 0.018     # m, Gaussian sigma of the lift along the arc
NEST_ITERS = 5


def _nest_need(st, lowers):
    """(per-ring lift needed (m), share of the width over a lower strand, top-face
    points inside a lower strand) of strand st."""
    s_par, top = hk.ring_params(st.n)
    under = ~top
    caps = [lo for lo in lowers if isinstance(lo, CapLower)]
    lowers = [lo for lo in lowers if not isinstance(lo, CapLower)]
    tri = [lo.triangles() for lo in lowers]
    box = [(t.min((0, 1)), t.max((0, 1))) for t in tri]
    need = np.zeros(len(st.rings))
    cov = np.zeros(len(st.rings))
    inv = 0
    for j, ring in enumerate(st.rings):
        Nj = st.N[j]
        for cp in caps:
            nd, k = cp.need(ring[under], Nj)
            if k:
                need[j] = max(need[j], nd)
                cov[j] = max(cov[j], k / float(under.sum()))
        lo_r, hi_r = ring.min(0) - 0.002, ring.max(0) + 0.002
        for t, (lo, hi) in zip(tri, box):
            if np.any(hi < lo_r) or np.any(lo > hi_r):
                continue
            tmin, tmax = t.min(1), t.max(1)
            ext = float(st.thick[j]) + 0.03
            sel = np.all(tmax >= lo_r - ext, 1) & np.all(tmin <= hi_r + ext, 1)
            if not sel.any():
                continue
            for face, sign in ((under, 1.0), (top, -1.0)):
                q = ring[face]
                mu = hk._line_hits(q, Nj * sign, t[sel])
                pos = np.where(np.isnan(mu), -1.0, mu)
                cnt = (pos > 1e-7).sum(1)
                ins = cnt % 2 == 1
                if not ins.any():
                    continue
                if sign > 0:
                    need[j] = max(need[j], float(pos[ins].max(1).max()) + NEST_GAP)
                    cov[j] = max(cov[j], float(ins.mean()))
                else:
                    inv += int(ins.sum())
    return need, cov, inv


def _smooth_lift(st, need, root_fade):
    """The lift over the spine's arc fraction (strand(lift=...) reads it on the spine;
    a grown curl moves with the spine's end, so its rings' need lands there)."""
    L = float(st.meta.get('spine_len', st.length)) if st.meta.get('curl') else st.length
    on = st.arc < L - 1e-6
    u = np.append(st.arc[on] / L, 1.0)
    need = np.append(need[on], need[~on].max() if (~on).any() else need[on][-1])
    su = np.linspace(0.0, 1.0, 401)
    raw = np.interp(su, u, need)
    sig = NEST_SMOOTH / L * 400.0
    r = int(math.ceil(1.0 * sig))
    dil = np.array([raw[max(0, i - r):i + r + 1].max() for i in range(len(raw))])
    sm = dil
    for _ in range(3):
        sm = np.maximum(hk._blur(sm, sig), raw)
    sm = hk._blur(sm, 0.25 * sig)
    if root_fade > 0:
        sm = sm * hk.smooth01(su * L / root_fade)
    return su, sm


class CapLower:
    """The scalp cap as a 'lower' for nested(): past its root's emergence a lock
    rests on the cap instead of sinking its concave underside and rims into it
    (round 11 first build: 15-18 % of the fringe and curtain vertices lay inside
    the cap beyond their designed root burial). Its need is the depth under the
    cap surface (nearest point), over the cosine between the lock's facing and
    the cap normal there (a line along a lock's tilted facing would run along the
    cap surface)."""

    def __init__(self, bvh):
        self.bvh = bvh

    def need(self, pts, N):
        out = 0.0
        hits = 0
        for p in pts:
            q = Vv(p)
            if not _inside(self.bvh, q):
                continue
            co, nrm, _i, d = self.bvh.find_nearest(q)
            if co is None:
                continue
            hits += 1
            c = max(0.35, float(np.dot(N, A(nrm))))
            out = max(out, d / c + NEST_GAP)
        return out, hits


_CAP_LOWER = []


def cap_lower(bvh=None):
    if bvh is not None:
        _CAP_LOWER[:] = [CapLower(bvh)]
    return _CAP_LOWER[0]


def nested(lowers, root_fade=0.0, **kw):
    """hk.strand(**kw) lifted out of the strands `lowers` it would cut into (see above).
    meta: lift_max, overlap (share of the width inside a lower at the worst ring),
    residual (m of lift still needed past root_fade), inverted (top-face points inside
    a lower strand: the layer order is wrong there)."""
    st = hk.strand(**kw)
    total = None
    lowers = list(lowers)
    hist = []
    for _ in range(NEST_ITERS if lowers else 0):
        need, cov, inv = _nest_need(st, lowers)
        hist.append((st.arc.copy(), need.copy()))
        if need.max() < 0.25 * NEST_GAP:
            break
        # the absolute lift each ring needs (the lift it already has + what it still
        # lacks), smoothed; never below the lift so far (a sum of smoothed bumps from
        # successive passes would pile up where they overlap)
        # (within the root's emergence the clumps are pressed into the scalp, where
        # neighbouring roots merge like pleats: no lift is asked for there, or the
        # faded lift creeps up toward the root pass after pass)
        if root_fade > 0:
            need = need * hk.smooth01((st.arc - 0.5 * root_fade) / (0.5 * root_fade))
        if total is not None:
            L = float(st.meta.get('spine_len', st.length)) if st.meta.get('curl') else st.length
            have = np.interp(np.minimum(st.arc / L, 1.0), np.linspace(0.0, 1.0, len(total)), total)
            need = np.where(need > 0, need + have, 0.0)
        su, sm = _smooth_lift(st, need, root_fade)
        total = sm if total is None else np.maximum(total, sm)
        for k in range(4):
            # a lift that bends the spine past the ring limits is spread wider
            try:
                st = hk.strand(**dict(kw, lift=hk.Lift(su, total.copy(), float(cov.max()), need)))
                break
            except hk.HairKernelError:
                if k == 3:
                    raise
                tb = hk._blur(total, 0.75 * NEST_SMOOTH / st.length * 400.0)
                total = tb * (total.max() / max(tb.max(), 1e-9))
    if lowers:
        need, cov, inv = _nest_need(st, lowers)
        free = st.arc > root_fade
        st.meta.update(lift_max=0.0 if total is None else float(total.max()), overlap=float(cov.max()), need=need,
                       lift=None if total is None else total,
                       residual=float(need[free].max()) if free.any() else 0.0, inverted=inv, need_hist=hist)
    return st


def log_strand(st, obj, cap_bvh=None):
    v = hk.validate(st)
    m = st.meta
    bur = ''
    if cap_bvh is not None:
        flags = _inside_flags(st, cap_bvh)
        tot, bad = buried(st, cap_bvh, flags)
        STATS.setdefault(obj, [0, 0])
        STATS[obj][0] += tot
        STATS[obj][1] += bad
        root, turn = check_surface(st, cap_bvh, flags)
        bur = (f'  buried past root {100 * bad / max(tot, 1):.1f}%  root in cap {100 * root:.0f}%  '
               f'surface turn {turn:.1f} at {1000 * m["surface_turn_at"]:.0f} mm')
    LOG.append(f'{obj:15s} {st.name:16s} len {1000 * st.length:5.0f} mm  n {st.n:2d}  rings {v["rings"]:3d}  '
               f'faces {v["faces"]:4d}  turn {v["max_turn"]:4.1f}  rho {v["max_rho"]:.2f}  twist '
               f'{v["max_twist"]:4.1f}  gap {1000 * v["max_gap"]:4.1f} mm{bur}'
               + (f'  overlap {100 * m["overlap"]:.0f}% lift {1000 * m["lift_max"]:.1f} mm '
                  f'residual {1000 * m["residual"]:.2f} mm inverted {m.get("inverted", 0)}'
                  if 'overlap' in m else ''))


def emit_all(bm, strands, obj, cap_bvh=None):
    for st in strands:
        log_strand(st, obj, cap_bvh)
        hk.emit(bm, st)


def cap_front_point(fx, row, grow):
    """Point on the cap's front surface at front offset fx, moved `grow` px
    outward along head_normal (negative = buried inside the cap)."""
    w, f, b = _profile(row)
    u = min(1.0, abs(fx) / max(w, 1e-6))
    p = cap_shift(P(fx, row, (f + b) / 2 - (b - f) / 2 * (1 - u ** CAP_EXP) ** (1 / CAP_EXP)))
    return p + head_normal(p) * (grow * PX)


def _polyline_len(pts):
    return sum((b - a).length for a, b in zip(pts, pts[1:]))


# ---------------------------------------------------------------- bangs
BANG_NORMAL = Vector((0, -1, 0.25)).normalized()


def bang_normal(p):
    """Bangs face the front; the outer ones turn toward their side so they
    read as a mass, not edge-on slivers, in the side view. Over the crown the
    facing leans to the scalp's own normal (the root lies on it)."""
    n = (BANG_NORMAL + Vector((0.6 * p.x / (40 * PX), 0, 0))).normalized()
    row = spec.SHEET_GROUND_Y - p.z * spec.PX_PER_M
    t = smooth01((row - 30.0) / 40.0)
    return (head_normal(p) * (1 - t) + n * t).normalized()


# Front-most side-view column of the face skin vs |front offset|, rows ~80-120
# (measured on the round-2 head mesh; unit `head` owns it, so it is a local
# constant here). The bang tips keep a small air gap in front of it.
FACE_FRONT = ((0, 240), (10, 241), (20, 245), (30, 254), (40, 268), (46, 290))
BANG_TIP_GAP = 5        # px in front of the skin at the tips
# ... and this much more where a tip ends over an eye (its upper lid and lashes stand
# in front of the skin table; round 11 review: with the r11 head a primary's tip lay
# 0.2 mm in front of the right upper lash): full within BANG_EYE_REACH px of the eye
# centre column (spec eye_x, out to the outer corners) and over BANG_EYE_ROWS, fading
# out over BANG_EYE_FADE px.
BANG_EYE_GAP = 1.5
BANG_EYE_REACH = 18.0
BANG_EYE_ROWS = (90.0, 112.0)
BANG_EYE_FADE = 8.0
BANG_BULGE = 8          # px in front of the skin where the fringe arches out (row 84)


def bang_eye_gap(fx, row):
    """Extra tip gap (px) of a fringe tip ending at (fx, row) over an eye."""
    ex = spec.L['eye_x'] * spec.PX_PER_M
    w = 1.0 - smooth01((abs(abs(fx) - ex) - BANG_EYE_REACH) / BANG_EYE_FADE)
    w *= smooth01((row - BANG_EYE_ROWS[0] + BANG_EYE_FADE) / BANG_EYE_FADE)
    w *= 1.0 - smooth01((row - BANG_EYE_ROWS[1]) / BANG_EYE_FADE)
    return BANG_EYE_GAP * w


def face_front_sc(fx):
    t = FACE_FRONT
    a = abs(fx)
    for (x0, s0), (x1, s1) in zip(t, t[1:]):
        if a <= x1:
            return s0 + (s1 - s0) * (a - x0) / (x1 - x0)
    return t[-1][1]


# A few broad, nested clumps of varied width and length (sheet: the longest
# falls between the eyes, slightly to the image-left; the outer pair frame the
# face past the outer eye corners). Roots converge on the crown.
# (fx root, fx tip, tip row, width px, layer, tip roundness, taper start, kind).
# layer: higher = on top (built later, resting on the clumps below it, see
# BANG_GAP). Roundness is the tip ogive's exponent: higher keeps the width longer
# and closes the tip in an arc. kind: 'in' = inner clump rooted at the crown;
# 'out' = outer clump (arches out less, rooted part way down the crown); 'temple'
# = outer lock rooted near the temple.
# Round 9: the three primary locks (the central sweep and one over each eye) are
# ~4.2 cm wide at the root and the secondaries narrower.
# Round 11 (kernel): crescent sections of aspect BANG_ASPECT (convex top, concave
# underside, rims curling back by BANG_WRAP), one smooth arch from the crown to
# the tip (the control points are B-spline control vertices: round 10 interpolated
# a corner at row 84, a 24-35 deg / ring crease across the primaries), nested in
# layer order instead of interpenetrating, the primaries split into two sub-tips
# and every tip turning in toward the face like a comma (BANG_COMMA).
BANG_CLUMPS = (
    (-3, -7, 129, 27, 7.0, 1.4, 0.40, 'in'),     # primary: central sweep, on top
    (6, 15, 108, 19, 4.0, 2.4, 0.45, 'in'),      # secondary right of the parting
    (-16, -26, 101, 27, 5.0, 2.2, 0.42, 'in'),   # primaries over the eyes, shorter,
    (19, 29, 97, 27, 5.5, 2.0, 0.44, 'in'),      # so the tip rows vary by ~3 cm
    (-31, -40, 114, 24, 6.0, 1.9, 0.50, 'out'),
    (33, 42, 110, 22, 6.5, 2.3, 0.50, 'out'),
    (42, 53, 128, 14, 3.5, 1.7, 0.55, 'temple'),  # past the outer eye corners, under the outs
    (-43, -53, 129, 14, 3.5, 1.7, 0.55, 'temple'),
)
BANG_PRIMARY = ()       # clumps whose tips split (BANG_SPLIT). Round 11 review: the split
                        # primaries (0, 2, 3) drew outline spurs at each fork and a notch at
                        # the longer sub-tip over the eyes, so the fringe tips stay whole
BANG_SPLIT = dict(at=0.80, shares=(0.56, 0.44), diverge=6.0, lengths=(1.0, 0.72))
BANG_ASPECT = 5.0       # width / thickness at the widest ring
BANG_SWELL = (0.35, 0.30)
BANG_TIP_B = 0.75
BANG_WRAP = (0.22, 0.14)  # rim curl-back at the root and the tip (x width)
BANG_COMMA = 0.0        # px the tip control vertex moves in toward the face (0: the tips keep
                        # BANG_TIP_GAP; at 3 px some tips met the brow)
# The crescent's outer face stands 0.625 x its thickness over the spine; the spine
# moves back by this share of the outer half over BANG_REF_HALF (px scale: root /
# forehead, mid-fringe, tip), so the fringe keeps round 10's outline and its tips
# their gap to the face.
BANG_REF_HALF = 0.00575
BANG_SINK = (1.0, 0.7, 0.3)
OUTER_BULGE_LESS = 6    # px less forward arch on the outer clumps
BANG_STAGGER = 0.5      # px of forward offset per layer over the forehead
BANG_GAP = 0.0008       # m: an upper clump's underside rests this far over the clumps below
# Root path: four stations from the crown to the hairline, on the cap surface
# (grow base px + share x layer); settle() then buries and raises the root
# section against the real cap, so the stations only steer the path.
ROOT_GROW = ((0.0, 0.0), (0.5, 0.1), (1.0, 0.25), (1.2, 0.45))
ROOT_FX = (0.0, 0.45, 0.75, 0.95)
ROOT_FX_TIP = (0.0, 0.0, 0.03, 0.1)
# per kind: (station rows, share of fx0 the root starts at)
ROOTS = {'in': ((20, 38, 54, 68), 0.35),
         'out': ((26, 40, 55, 69), 0.6),
         'temple': ((32, 45, 57, 69), 0.75)}
BANG_EMERGE = 1.0       # emergence length: x the arc to station BANG_EMERGE_AT
BANG_EMERGE_AT = 4      # (stations from the crown: 3 = the third)
BANG_WSCALE = 0.85      # x the widths in BANG_CLUMPS
BANG_SPREAD = 1.25      # x the tips' front-view offset from the root line (fan)
BANG_DEPTH = 1.5        # px each layer below the top one sits further back (pre-nesting)
BANG_BULGE_OUT = 3.0    # px the row-84 control vertex stands past the arch it shapes
# Normals: pure scalp-volume normal while a root emerges (its flanks shade
# exactly like the cap around it, no shade slivers along the ridges), then
# VOL_KEEP of the clump's own normal on the free fringe.
BANG_KEEP = (0.0, VOL_KEEP, 0.25, 0.55)


def bang_points(fx0, fx1, row1, wpx, lift, kind, thick):
    """B-spline control vertices (m) of one fringe clump, and its emergence arc (m)."""
    outer = kind != 'in'
    sink = max(0.0, 0.625 * thick - BANG_REF_HALF) / PX     # px
    tip = face_front_sc(fx1) - BANG_TIP_GAP - bang_eye_gap(fx1, row1)
    fxm = fx0 + (fx1 - fx0) * 0.45
    # On the forehead the cap (which recedes behind the face only below the
    # hairline) usually binds; the face term only limits where the cap is set
    # back. Outer clumps then sit OUTER_BULGE_LESS px further back.
    bulge = min(face_front_sc(fxm) - BANG_BULGE, cap_front_sc(fxm, 84) - lift - 2)
    if outer:
        bulge += OUTER_BULGE_LESS
    stag = BANG_STAGGER * (lift - 5.0)
    bulge -= stag + BANG_BULGE_OUT
    bulge += BANG_DEPTH * (max(c[4] for c in BANG_CLUMPS) - lift)
    rowm = (84 + row1) / 2
    fxq = fx0 + (fx1 - fx0) * 0.75
    rows, share = ROOTS[kind]
    fxr = fx0 * share
    s0, s1, s2 = (k * sink for k in BANG_SINK)
    ctrl = [cap_front_point((fxr + (fx0 - fxr) * a + (fx1 - fx0) * b) * crown_widen(row), row, g0 + g1 * lift - s0)
            for row, (g0, g1), a, b in zip(rows, ROOT_GROW, ROOT_FX, ROOT_FX_TIP)]
    emerge = _polyline_len(ctrl[:BANG_EMERGE_AT]) * BANG_EMERGE
    ctrl += [P(fxm, 84, bulge + s0),
             P(fxq, rowm, (bulge + tip) / 2 - 1 + s1),
             P(fx1, row1, tip + s2 + BANG_COMMA)]
    return [A(p) for p in ctrl], emerge


def bangs(cap_bvh):
    """The fringe: crescent clumps that grow out of the cap above the hairline,
    arch out over the forehead and come back to rest just in front of it, each
    resting on the clumps below it. Returns the kernel strands."""
    order = sorted(range(len(BANG_CLUMPS)), key=lambda i: (BANG_CLUMPS[i][4], i))
    built = []
    top = max(c[4] for c in BANG_CLUMPS)
    for i in order:
        fx0, fx1, row1, wpx, lift, rnd, tf, kind = BANG_CLUMPS[i]
        fx1 = fx0 + (fx1 - fx0) * BANG_SPREAD
        wpx *= BANG_WSCALE
        w = wpx * PX
        thick = w / BANG_ASPECT
        pts, emerge = bang_points(fx0, fx1, row1, wpx, lift, kind, thick)
        kw = dict(name=f'bang{i}', points=pts, mode='bspline', width=w, thick=thick,
                  facing=facing_fn(bang_normal), swell=BANG_SWELL, tip=(tf, rnd, BANG_TIP_B),
                  wrap=BANG_WRAP, n=16 if wpx >= 24 else (14 if wpx >= 19 else 12),
                  grad=None, attrs={KEEP_ATTR: keep_attr(BANG_KEEP), LINE_ATTR: 1.0},
                  split=hk.split(**BANG_SPLIT) if i in BANG_PRIMARY else None)
        st = nested(built, root_fade=emerge, **kw)
        settle(st, cap_bvh, emerge, depth=1.2)
        built.append(st)
    return built


# ---------------------------------------------------------------- ahoge
# Round 11 (crown): the sheet's ahoge is two small tufts at the top front of the crown,
# curving forward and up: two small points in the side view (cols ~257 / 269), one
# small point on the round dome in the front and back views. 风堇 has no tuft, but her
# forehead crescent shows how her model raises a lock: not a tube stood on the scalp
# but the single-sided hood shell itself folded up, its root rising out of the hood
# with no burial and no slit. Each tuft here is such a pinch of the scalp: a
# single-sided patch over an egg-shaped footprint on the cap (`across` either side,
# `front` / `back` along the hair's flow toward the face), conforming to the cap and
# rising to its tip as h = H (1 - r)^AHOGE_K (concave flanks; the tip rounded over the
# first AHOGE_ROUND of r, so it is sharp but not a needle), its top leaning forward by
# AHOGE_LEAN H (h / H)^1.5 (a lock lifting off the crown and curling forward: a long
# gentle back, a short steep front), the rim sunk AHOGE_SINK r^6 under the cap (no
# edge where it leaves the scalp) and its outline faded out toward the rim. The front
# tuft stands higher, so the front and back views see one point.
# Rounds 10-11 built the ahoge as kernel tufts (closed tubes): buried in the cap they
# read as a slit (D9); at the sheet's size (<= 25 mm, 6-7 px tall) a tube gets 3-12
# rings and read as a faceted stub end-on from the front, a thorn or a crest; the
# round-11 swept-back tuft (38 mm) lay on the ridge of the old pointed cap.
AHOGE_PINCH = (
    # centre (front-view px, side-view col) on the cap, heading (deg from forward toward +X,
    # seen from above), footprint (m), height (m)
    dict(name='ahoge_front', at=(-0.6, 261.0), heading=-5.0, across=0.0085, front=0.0085, back=0.0240,
         height=0.0097),
    dict(name='ahoge_back', at=(0.6, 271.5), heading=6.0, across=0.0065, front=0.0070, back=0.0180,
         height=0.0050),
)
AHOGE_K = 2.0
AHOGE_LEAN = 0.25       # x H (<= front / 3 H: the front flank does not overhang)
AHOGE_ROUND = 0.12
AHOGE_SINK = 0.0006     # m
AHOGE_LINE = (0.55, 0.9)    # outline weight 1 -> 0 over this share of r
AHOGE_KEEP = (0.6, VOL_KEEP)    # own-normal share at the tip, at the rim (the cap's)
AHOGE_RINGS = 16        # rings at r = (i / AHOGE_RINGS)^AHOGE_REXP (denser toward the tip)
AHOGE_REXP = 1.2
AHOGE_SPOKES = 32
# Build-time checks (HairKernelError past them)
AHOGE_MAX_HEIGHT = 7.0      # px: a tip stands at most this far over the cap below it
AHOGE_TIP_COLS = (257.0, 269.0)     # side-view columns of the sheet's two points ...
AHOGE_TIP_TOL = 4.0                 # ... the tips lie within this many px of them
AHOGE_MAX_WIDTH = 14.0      # px: front-view width of the raised part (h > AHOGE_SINK)
AHOGE_RIM_OUT = 0.001       # m: no rim vertex stands further outside the cap
AHOGE_MAX_BURIED = 0.2      # share of a tuft's vertices under the cap
AHOGE_LOG = {}


def _cap_below(cap_bvh, p):
    """(point, normal) of the cap straight below p (cast down from 5 cm above)."""
    hit = cap_bvh.ray_cast(p + Vector((0.0, 0.0, 0.05)), Vector((0.0, 0.0, -1.0)), 0.2)
    if hit[0] is None:
        raise RuntimeError(f'hair_front ahoge: no cap below {tuple(p)}')
    return hit[0], hit[1]


def _pinch_r(rr):
    """Footprint parameter -> profile parameter: rr, rounded off over the first AHOGE_ROUND."""
    e = AHOGE_ROUND
    return (math.sqrt(rr * rr + e * e) - e) / (math.sqrt(1.0 + e * e) - e)


def pinch(bm, cap_bvh, t):
    """One ahoge tuft as a pinch of the scalp (see above), emitted into bm. Returns its
    log entry (tip landmarks, raised width, buried share, worst turn along a spoke)."""
    fx, sc = t['at']
    c0, _n = _cap_below(cap_bvh, P(fx, CAP_TOP[0], sc))
    n0 = head_normal(c0)
    hd = math.radians(t.get('heading', 0.0))
    fwd = Vector((math.sin(hd), -math.cos(hd), 0.0))
    e1 = (fwd - n0 * fwd.dot(n0)).normalized()         # forward, in the scalp's tangent plane
    e2 = n0.cross(e1).normalized()
    H, af, ab, b = t['height'], t['front'], t['back'], t['across']

    def place(rr, th):
        a = 0.5 * (af + ab) + 0.5 * (af - ab) * math.cos(th)     # egg: front reach at 0, back at pi
        q = c0 + (e1 * (math.cos(th) * a) + e2 * (math.sin(th) * b)) * rr
        nq = head_normal(q)
        hit = cap_bvh.ray_cast(q + nq * 0.03, -nq, 0.08)
        s = hit[0] if hit[0] is not None else q
        h = H * (1.0 - _pinch_r(rr)) ** AHOGE_K
        return s + head_normal(s) * (h - AHOGE_SINK * rr ** 6) + e1 * (AHOGE_LEAN * H * (h / H) ** 1.5)

    klay = _layer(bm, KEEP_ATTR, -1.0)
    llay = _layer(bm, LINE_ATTR, 1.0)
    glay = bm.verts.layers.float.get(common.GRAD_ATTR) or bm.verts.layers.float.new(common.GRAD_ATTR)
    uvl = bm.loops.layers.uv.get('UVMap') or bm.loops.layers.uv.new('UVMap')
    uv = {}

    def vert(rr, th):
        v = bm.verts.new(place(rr, th))
        v[klay] = AHOGE_KEEP[1] + (AHOGE_KEEP[0] - AHOGE_KEEP[1]) * (1.0 - smooth01(rr / 0.8))
        v[llay] = 1.0 - smooth01((rr - AHOGE_LINE[0]) / (AHOGE_LINE[1] - AHOGE_LINE[0]))
        v[glay] = 0.0                   # the hair's base colour (no mint on the crown)
        uv[v] = (0.5 + 0.5 * rr * math.cos(th), 0.5 + 0.5 * rr * math.sin(th))
        return v
    S = AHOGE_SPOKES
    ths = [2.0 * math.pi * j / S for j in range(S)]
    tip = vert(0.0, 0.0)
    rings = [[vert((i / AHOGE_RINGS) ** AHOGE_REXP, th) for th in ths] for i in range(1, AHOGE_RINGS + 1)]
    faces = []
    for j in range(S):
        k = (j + 1) % S
        faces.append(bm.faces.new((tip, rings[0][j], rings[0][k])))
        for ra, rb in zip(rings, rings[1:]):
            faces.append(bm.faces.new((ra[j], rb[j], rb[k], ra[k])))
    for f in faces:
        f.normal_update()
    if sum(f.normal.dot(head_normal(f.calc_center_median())) for f in faces) < 0:
        bmesh.ops.reverse_faces(bm, faces=faces)
        for f in faces:
            f.normal_update()
    for f in faces:
        for lp in f.loops:
            lp[uvl].uv = uv[lp.vert]

    # checks
    def over(p):
        hgt, _nrm = _cap_height(cap_bvh, p)
        return hgt if hgt is not None else 0.0
    tipc = Vector(tip.co)
    under, _ = _cap_below(cap_bvh, tipc)
    height = (tipc.z - under.z) * spec.PX_PER_M
    col = tipc.y * spec.PX_PER_M + MID
    row = spec.SHEET_GROUND_Y - tipc.z * spec.PX_PER_M
    allv = [tip] + [v for r in rings for v in r]
    hs = [over(v.co) for v in allv]
    raised = [v.co.x for v, h in zip(allv, hs) if h > AHOGE_SINK]
    width = (max(raised) - min(raised)) * spec.PX_PER_M if raised else 0.0
    rim = max(over(v.co) for v in rings[-1])
    buried = sum(1 for h in hs if h < 0.0) / len(hs)
    # turn per ring along each spoke, past the rounded tip (there the spokes turn over
    # its ~0.5 mm radius by construction; tip_turn logs it)
    turn = tip_turn = 0.0
    turn_at = 0
    rr_of = [0.0] + [(i / AHOGE_RINGS) ** AHOGE_REXP for i in range(1, AHOGE_RINGS + 1)]
    for j in range(S):
        line = [tipc] + [Vector(r[j].co) for r in rings]
        for i, (p0, p1, p2) in enumerate(zip(line, line[1:], line[2:])):
            d0, d1 = p1 - p0, p2 - p1
            if d0.length > 1e-9 and d1.length > 1e-9:
                a = math.degrees(d0.angle(d1))
                if rr_of[i + 1] <= 2.0 * AHOGE_ROUND:
                    tip_turn = max(tip_turn, a)
                elif a > turn:
                    turn, turn_at = a, i + 1
    facing = min(f.normal.dot(head_normal(f.calc_center_median())) for f in faces)
    log = dict(name=t['name'], height=height, col=col, row=row, width=width, rim=rim, buried=buried,
               turn=turn, turn_at=turn_at, tip_turn=tip_turn, facing=facing, faces=len(faces))
    target = min(AHOGE_TIP_COLS, key=lambda c: abs(c - col))
    errs = []
    if height > AHOGE_MAX_HEIGHT:
        errs.append(f'tip {height:.1f} px over the cap (> {AHOGE_MAX_HEIGHT})')
    if abs(col - target) > AHOGE_TIP_TOL:
        errs.append(f'tip at side col {col:.1f} (sheet {target:.0f} +- {AHOGE_TIP_TOL:.0f})')
    if width > AHOGE_MAX_WIDTH:
        errs.append(f'raised part {width:.1f} px wide in the front view (> {AHOGE_MAX_WIDTH})')
    if rim > AHOGE_RIM_OUT:
        errs.append(f'rim {1000 * rim:.2f} mm outside the cap (> {1000 * AHOGE_RIM_OUT:.1f})')
    if buried > AHOGE_MAX_BURIED:
        errs.append(f'{100 * buried:.0f} % of it under the cap (> {100 * AHOGE_MAX_BURIED:.0f})')
    if turn > SURFACE_TURN:
        errs.append(f'a spoke turns {turn:.1f} deg at ring {turn_at} (> {SURFACE_TURN})')
    if facing <= 0.0:
        errs.append(f'a face turns into the head (facing {facing:.2f})')
    if errs:
        raise hk.HairKernelError(f"hair_front {t['name']}: " + '; '.join(errs))
    return log


def ahoge(bm, cap_bvh):
    """The two ahoge tufts (AHOGE_PINCH) into bm; AHOGE_LOG gets their checks."""
    AHOGE_LOG.clear()
    AHOGE_LOG['tufts'] = [pinch(bm, cap_bvh, t) for t in AHOGE_PINCH]
    return AHOGE_LOG['tufts']


# ---------------------------------------------------------------- side locks
# Side locks for the character's left (+X, image right); the right side is the
# kernel's exact mirror (hk.mirrored). ctrl points (fx, row, sc) and full width (m).
# The side view of the sheet shows the face clear from the nose back to col ~260
# (rows 90-155), with only a short cheek lock behind the eye: every lock stays
# behind that line.
# Round 11 (kernel): crescent sections (aspect LOCK_ASPECT), adaptive rings, and
# the ends re-authored within the curvature limits: the cheek locks and wisps
# end in a grown outward turn (<= 120 deg, R >= 12 mm, narrowing to a blade;
# round 10: barbs turning 94 deg in one ring, D6), the shoulder curl in a spiral
# that tightens as it narrows (round 10: a 180 deg hook in 2.3 cm, D5).
# Each entry: (ctrl, width, end turn or None).
CHEEK_LOCKS = [
    # Beside the cheek, behind the eye in the side view. They leave the cap at
    # the temple, come in toward the cheek, and turn their green tips outward
    # at jaw level; below the cheekbone they drift back toward the ear so the
    # jaw stays clear in the side view. The tips turn out and a little forward,
    # in front of the long lock behind them.
    # (round 11 review: the roots start 6 px lower than the first build, under the temple
    # clumps, so a forearm laid over the head, dance_heart, crosses less of them)
    ([(40, 54, 252), (51, 72, 252), (50, 96, 257), (49, 112, 263), (51, 124, 269), (54, 132, 274)], 0.021,
     dict(turn=75, toward=(0.7, -0.7, 0.15), radius=0.024, core=0.6, lead=1.5)),
    ([(46, 58, 262), (57, 78, 263), (58, 102, 272), (60, 115, 279), (62, 126, 284)], 0.019,
     dict(turn=70, toward=(1.0, -0.35, 0.2), radius=0.024, core=0.6, lead=1.5)),
]
WISP_LOCKS = [
    # outer wisps flaring out at rows 115-140 (front), behind the eye (side);
    # they keep falling as they flare and close in a blade (round 10: a soft
    # upward turn on wisp 0, a 94 deg barb on wisp 1). The accessories' flower
    # sits on wisp 0 at the temple (its path there is round 10's).
    ([(52, 48, 273), (64, 82, 275), (72, 104, 278), (77, 120, 281), (82, 131, 284), (86, 138, 287)], 0.019,
     None),
    # (wisp 1: round 11 review, 3-7 px in and forward of the first build, ending 3 rows
    # higher: a raised upper arm beside the head, reach_up_back, met its lower half)
    ([(58, 58, 291), (69, 94, 292), (75, 114, 294), (79, 125, 296), (81, 130, 298)], 0.017, None),
]
# The lock in front of each shoulder: an S-shaped lock that turns forward
# gradually over rows ~140-225 and ends with a slight turn back toward the chest.
# Round 11: round 10's support lock (an under-layer lying in the same place as the
# shoulder curl's upper half) is gone; the curl now runs behind this lock there.
FRONT_LONG_MAIN = [
    ([(52, 60, 276), (62, 86, 283), (67, 112, 288), (67, 132, 288), (67, 149, 281),
      (69, 164, 268), (72, 179, 255), (75, 193, 245), (78, 206, 240), (80, 217, 239),
      (80, 227, 241)], 0.026, None),
]
# The outward shoulder curl (round 9 reroute kept): below row 150 it comes forward
# over the front of the shoulder and turns out in front of the arm's plane
# (CURL_FRONT px in front of round 8's path, eased in over CURL_FRONT_ROWS; the
# raised arm used to sweep up into it), its reach past CURL_IN[0] (front-view px)
# scaled by CURL_IN[1] so the loop does not float out over a raised or bent arm.
# Round 11: the path ends where round 10's hook began; the kernel grows the end as
# a spiral (CURL_SPIRAL) that narrows to CURL_SPIRAL['core'] of the lock before it
# tightens from R ~ 20 mm to ~10 mm, the width in the bend plane (风堇's end curls).
# (round 11: rows 70-150 run ~8-10 px deeper than round 10's, under the long lock; rows
# 150-195 2-4 px less deep than the first round-11 build, where arms_up raised the
# shoulder into it: 0.9 cm / 1 % of the curl inside, now 0.5 cm / 0.2 %, round 10 0.2 cm)
CURL_PATH = ((58, 72, 292), (64, 100, 295), (63, 130, 294), (64, 150, 287), (72, 170, 279),
             (81, 183, 274), (90, 195, 279), (98, 205, 285), (106, 213, 290))
CURL_FRONT = 22.0
CURL_FRONT_ROWS = (170.0, 215.0)   # (it stays behind the long front lock above)
CURL_IN = (92.0, 0.9)
# The curl's broad side turns this far toward the front (lock_normal forward; round 8
# 1.2): in front of the shoulder a front-facing ribbon read as a thin strip in profile.
CURL_FORWARD = 0.7
# Round 11 review: the spiral turns outward and down first (round 10's hook did too) and
# curls back in and up, in front of the shoulder's outer side: the first build's spiral
# turned in toward the chest, in front of the shoulder joint, where the upper arm swept
# through it as it came down (idol_dance@56: 40 % of the curl inside the arm; outward,
# 0 %, and the clip's worst frame 0.067 against round 10's 0.128). The width holds at
# `core` of the lock over most of the turn and closes in a short blade (taper (3, 0.8):
# the first build's (1.4, 1.2) closed it to a needle).
CURL_SPIRAL = dict(turn=235, toward=(0.6, 0.0, -0.8), face='plane', radius=0.021, core=0.4, lead=1.5,
                   exp=0.8, taper=(3.0, 0.8))


def _curl_lock():
    pts = []
    for fx, row, sc in CURL_PATH:
        f = smooth01((row - CURL_FRONT_ROWS[0]) / (CURL_FRONT_ROWS[1] - CURL_FRONT_ROWS[0]))
        if fx > CURL_IN[0]:
            fx = CURL_IN[0] + (fx - CURL_IN[0]) * CURL_IN[1]
        pts.append((fx, row, sc - CURL_FRONT * f))
    return pts, 0.028, CURL_SPIRAL


# One strand behind the face frame filling the gap to the back hair.
# Round 11 review: 2-5 px further in over rows 62-202 than the first build (round 10's
# path + 1-3 px back): a raised upper arm beside the head met it there (reach_up_back:
# 11 % of it inside the arm, round 10 5 %, now 2 %; with the first build's path above
# row 145 the arm met its middle and the curl resting on it, 10 %). Its inner rim then
# lies inside the cap behind the ear (16 % of it past its root, hidden; 8 % before).
SIDE_CURTAIN = [
    ([(57, 62, 304), (63, 108, 305), (65, 145, 306), (66, 176, 307), (67, 202, 309)], 0.032, None),
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
CHEEK_EMERGE = 24.0     # ... the cheek locks and wisps (they converge at the temple, under the flower)
LOCK_EMERGE = 16.0      # px of arc past the first visible control point over
                        # which settle() lets the lock lift off the cap
LOCK_GAP = 0.0008       # m: a lock resting on another (hk.strand_on)
# The cheek locks and wisps settle on the built (grooved) cap like every other strand
# (rounds 9-10 and the first round-11 build: on the ungrooved sheet cap, where wisp 1's
# root crosses a crown groove and stood 2-2.5 mm proud of the cap as a flat-cut stump).
CHEEK_BVH = 'cap'
CHEEK_SWELL = (0.7, 0.5)    # kernel swell of the cheek locks and wisps (root width share, over u;
                            # round 11 first build 0.2: a 4 mm root packed rings 2 mm apart into
                            # the hidden root, where a forearm laid over the head met them)
CHEEK_DEPTH = 1.0           # px settle() buries the cheek locks' and wisps' roots (others: 1.0)
# Normal blend per family: the hanging locks fade from the scalp volume near the
# scalp to more of their own rounded section below the cheek, so they read as
# bundles, not flat plates, at oblique angles.
LOCK_KEEP = (0.0, 0.7, 0.12, 0.55)


def side_strand(name, entry, *, forward, lateral, aspect, swell, tip, wrap, grad, keep, bvh,
                lowers=(), n=12, curl_face='keep', curl_exp=0.3, emerge_px=LOCK_EMERGE, depth=1.0):
    """One side lock (left side), its root buried: an extra control point continues
    the lock back up along the cap (just under its surface), so the narrow first
    rings sit inside it and the lock surfaces at a shallow angle; settle() then
    presses the root rings onto the cap up to LOCK_EMERGE px past the first
    visible control point. The arc fractions (tip, grad, keep) include this
    hidden root."""
    ctrl, w, end = entry
    pts = [P(*c) for c in ctrl]
    n0 = head_normal(pts[0])
    p0 = pts[0] - n0 * (ROOT_SINK * PX)
    up = p0 - pts[1]
    up = up - n0 * up.dot(n0)
    if up.length < 1e-6:
        up = Vector((0.0, 0.0, 1.0)) - n0 * n0.z
    up.normalize()
    root = p0 + up * (ROOT_BURY[0] * PX)
    root = root - head_normal(root) * (ROOT_BURY[1] * PX)
    pts = [root, p0] + pts[1:]
    emerge = _polyline_len(pts[:2]) + emerge_px * PX
    curl = None
    if end is not None:
        prm = dict(dict(face=curl_face, exp=curl_exp), **end)
        curl = hk.curl(**prm)
    kw = dict(name=name, points=[A(p) for p in pts], width=w, aspect=aspect,
              facing=facing_fn(lambda p: lock_normal(p, forward, lateral)), swell=swell,
              tip=tip, wrap=wrap, n=n, curl=curl, grad=grad,
              attrs={KEEP_ATTR: keep_attr(keep), LINE_ATTR: 1.0})
    st = nested(lowers, root_fade=emerge, **kw)
    settle(st, bvh, emerge, depth=depth)
    return st


# The side bundle is nested as one stack, from the head outward (SIDE_ORDER): each
# lock rests on the ones before it that it would otherwise cut through (round 10:
# 14-19 % of every side family's vertices inside another lock). The families still
# ride their own chains (rig.SIDE_HAIR_FAMILIES).
SIDE_ORDER = ('curtain', 'curl', 'main', 'cheek0', 'cheek1', 'wisp1', 'wisp0')


def side_specs():
    """{key: (family, name, entry, settings)} of the side locks (left side)."""
    out = {}
    for k, e in enumerate(CHEEK_LOCKS):
        out[f'cheek{k}'] = ('hair_cheek', e, dict(
            forward=0.7, lateral=True, aspect=2.8, swell=CHEEK_SWELL, tip=None, wrap=0.15,
            grad=(0.5, 1.0), keep=LOCK_KEEP, bvh=CHEEK_BVH, emerge_px=CHEEK_EMERGE, depth=CHEEK_DEPTH))
    for k, e in enumerate(WISP_LOCKS):
        out[f'wisp{k}'] = ('hair_cheek', e, dict(
            forward=0.6, lateral=False, aspect=2.8, swell=CHEEK_SWELL, tip=(0.5, 1.9, 0.6), wrap=0.15,
            grad=(0.55, 1.0), keep=LOCK_KEEP, bvh=CHEEK_BVH, emerge_px=CHEEK_EMERGE, depth=CHEEK_DEPTH))
    out['main'] = ('hair_lock', FRONT_LONG_MAIN[0], dict(
        forward=0.9, lateral=True, aspect=2.8, swell=(0.3, 0.25), tip=(0.40, 2.0, 0.7), wrap=0.12,
        grad=(0.42, 1.0), keep=LOCK_KEEP, bvh='cap'))
    out['curl'] = ('hair_curl', _curl_lock(), dict(
        forward=CURL_FORWARD, lateral=False, aspect=3.2, swell=(0.3, 0.25), tip=None, wrap=0.15,
        grad=(0.55, 0.85), keep=LOCK_KEEP, bvh='cap', curl_face='plane', curl_exp=0.8))
    # The curtain hangs behind the face frame and ends at the choker, well above
    # the other locks' green: its ramp ends past the tip (~45% mint there).
    out['curtain'] = ('hair_curtain', SIDE_CURTAIN[0], dict(
        forward=1.2, lateral=False, aspect=2.8, swell=(0.3, 0.25), tip=(0.55, 1.8, 0.7), wrap=0.15,
        grad=(0.78, 1.25), keep=None, bvh='cap'))
    return out


def side_locks(cap_bvh, sheet_bvh):
    """{family: [left strands]} of the side locks."""
    specs = side_specs()
    fam = {'hair_cheek': [], 'hair_lock': [], 'hair_curl': [], 'hair_curtain': []}
    built = []
    for key in SIDE_ORDER:
        family, entry, cfg = specs[key]
        cfg = dict(cfg, bvh=sheet_bvh if cfg['bvh'] == 'sheet' else cap_bvh)
        st = side_strand(f'{key}_L', entry, lowers=built, **cfg)
        built.append(st)
        fam[family].append(st)
    return fam


def build(col):
    mat = common.toon_material('hair', gradient='hair_tip')
    LOG.clear()
    STATS.clear()
    _cap_obj, cap_bvh = build_cap(col, mat)
    sheet_bvh = _sheet_bvh()

    bm = bmesh.new()
    ahoge(bm, cap_bvh)
    crown = finish(col, 'hair_crown', bm, mat, line_min=LINE_MIN)
    crown['levi_cast_shadow'] = False   # a tuft prints a hard sliver on the crown otherwise

    bm = bmesh.new()
    emit_all(bm, bangs(cap_bvh), 'hair_bangs', cap_bvh)
    bangs_obj = finish(col, 'hair_bangs', bm, mat, line_min=LINE_MIN)
    # The fringe does not cast: with the low key light every clump ridge over
    # the crown printed a hard 1-2 px shadow sliver along its neighbour, and its
    # shadow on the forehead is too thin to read. Its own N.L shading still
    # separates the clumps.
    bangs_obj['levi_cast_shadow'] = False

    fams = side_locks(cap_bvh, sheet_bvh)
    for side in ('L', 'R'):
        for name, strands in fams.items():
            bm = bmesh.new()
            sts = strands if side == 'L' else [hk.mirrored(s) for s in strands]
            emit_all(bm, sts, f'{name}_{side}', cap_bvh)
            finish(col, f'{name}_{side}', bm, mat, line_min=LINE_MIN)
    err = cap_profile_error()
    print(f'HAIR_FRONT cap: {len(cap_spokes())} spokes x {len(cap_rings())} rings; '
          f'outside CAP_PROFILE by at most {1000 * err:.2f} mm')
    rnd = check_cap_round(cap_bvh)
    print(f"HAIR_FRONT cap crown: apex row {rnd['apex_row']:.2f}; front / back outline apex radius "
          f"{rnd['r_apex']:.1f} px (|x| <= {CAP_ROUND_HALF:.0f} px) vs the circle through the apex and the "
          f"outline at +-{CAP_ROUND_AT:.0f} px {rnd['r_circle']:.1f} px (ratio {rnd['ratio']:.2f}, min {CAP_ROUND_MIN}); "
          f"3D apex radii {1000 * rnd['r_across']:.0f} mm across x {1000 * rnd['r_along']:.0f} mm along "
          f"(ratio {rnd['aspect']:.2f}, min {CAP_APEX_ASPECT_MIN})")
    for d in AHOGE_LOG['tufts']:
        print(f"HAIR_FRONT {d['name']}: tip at side col {d['col']:.1f}, row {d['row']:.1f}, {d['height']:.1f} px over "
              f"the cap; raised part {d['width']:.1f} px wide; rim {1000 * d['rim']:.2f} mm off the cap; "
              f"{100 * d['buried']:.0f} % under the cap; spoke turn <= {d['turn']:.1f} deg (ring {d['turn_at']}; "
              f"{d['tip_turn']:.0f} over the rounded tip); facing >= "
              f"{d['facing']:.2f}; {d['faces']} faces")
    for line in LOG:
        print('HAIR_FRONT', line)
    for obj, (tot, bad) in STATS.items():
        print(f'HAIR_FRONT {obj:15s} vertices {tot:5d}, inside the cap past the root {100 * bad / max(tot, 1):4.1f}%')
