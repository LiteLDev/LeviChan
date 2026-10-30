"""Long back hair: white -> green wavy locks from the crown to the skirt (round 11).

Every lock is a strand of the shared hair kernel (_hair_kernel, the 风堇 study):
a C2 centreline held to the curvature limits (R >= max(12 mm, 0.6 w), rho <= 0.45,
<= 8 deg of turn per ring), rotation-minimising frames with a rate-limited roll, a
crescent section (convex top, flatter or concave underside, thin rims) that
narrows into a flat blade or into an end curl grown G2 from the spine (it narrows
before it tightens and tightens as it thins), split sub-tips welded into their
lock. strand() validates every lock at build time and raises (HairKernelError)
naming the lock, ring and point, so a build never carries a kink.

Layout (back view, the character's left = image left):
  - an UNDER-LAYER ('hair_back_shell'): one thin closed sheet lying on the
    scalp cap (hair_front's CAP_PROFILE) from the skull's equator and hanging
    a few px under the envelope down the back, so no body shows between the
    locks. It spans the back of the skull (more than rig.HAIR_LOCK_SPAN round
    it), so the rig hangs it from the back-hair sector chains, not a lock chain;
  - PRIMARY locks (PRIMS): ten crescent locks across the back mass in two
    lobes, each its own loose part (the rig gives it its own 後髪束 chain),
    built in layers: the under row rests its underside on the under-layer and
    the cap, the over row on the under row (kernel shingling: the spine is lifted
    in one smooth step, never the vertices), so neighbours stack instead of
    passing through each other. Three of them end in the sheet's curls (A the
    big C on the left, D the open curl right of the parting, F the outer right
    curl), A and D with two sub-tips; SW ends in the side view's open curl
    turning back; the others end in blades at staggered heights;
  - OUTER side locks (OUTER, both sides): the shoulder flick, the wave lock over
    the back of the upper arm and the crescent past the sleeve (a flat C-blade).
Locks are authored in reference panel pixels so they can be fitted directly
against ref/back.png and ref/side.png:

    bx  : column in the BACK view   (image-left = character's left = +X)
    sx  : column in the SIDE view   (image-right = behind her = +Y)
    row : row shared by all panels  (z = (951 - row) / 643)

One envelope (env_sx): a few px over hair_front's scalp cap above the nape (its
CAP_PROFILE data), blending into hanging superelliptic sections whose back
follows the sheet's side silhouette (MASS_BACK). A mass lock's key points are
(bx, row) on it; ('s', azimuth, polar) is a scalp point; (bx, sx, row) explicit.

Skirt clearance: the lock ends keep SKIRT_GAP off the skirt's real back surface,
godet fold crests included (skirt_sx(): the skirt's pure surface functions
skirt.profiles / skirt.fold_table, never its objects). Round 11 no longer
projects spine or curl points onto it (the per-point push made the round-10
pipes, telescoping steps and twist flips at the curl junctions): a smooth
clearance envelope (clear_sx: a blurred max filter of the skirt surface + SKIRT_GAP)
meets the hair envelope in a soft maximum, so the locks ride over the godet
crests; whatever still clashes after the build lifts the whole lock end in one
smooth displacement (_settle), and the lock is validated again.

Colour: toon_material('hair', gradient='hair_tip'); toon_grad is one smooth
field over the mass (grad_global), kept monotonic down each lock so curls that
turn back up stay green; the outer locks keep their own ranges.
Shading: custom normals blend one continuous volume normal (volume_normal) with
each lock's own normal: mostly the volume high up, so the crown and back shade
as a few large shapes, more of the own normal on the free lower lengths and
curls (they read as forms). Outlines are on/off per vertex by how far a lock
stands over its neighbours (outline_weights).

The scalp cap, bangs and face-framing side locks belong to hair_front (this part
reads its CAP_PROFILE / CAP_EXP measurement data only).
"""
import math

import bmesh
import numpy as np
from mathutils import Vector

from .. import common, spec
from . import _hair_kernel as hk
from . import skirt as _skirt                  # pure surface functions only (see docstring)
from .hair_front import CAP_EXP, CAP_PROFILE   # measurement data only (see docstring)

PX = spec.PX_PER_M
CX = spec.PANEL_W / 2

# Skull ellipsoid in panel px (back view hair is +-74 px wide at row 100, side
# view back of head at sx 367). Centre depth follows spec.L['head_center_y'].
# Used for scalp point positions and the hair's volume normals.
SKULL_C = (0.0, spec.L['head_center_y'] * spec.PX_PER_M, 108.0)   # (X px, Y px, row)
SKULL_R = (72.0, 82.0, 86.0)         # (rx, ry, rz) px
SCALP_LIFT = 0.95

# Back of the hair envelope on the centre line per row (side-view column),
# from the back edge of the hair in ref/side.png minus the clump thickness.
MASS_BACK = [(110, 364), (140, 362), (170, 365), (200, 372), (230, 382), (260, 397),
             (290, 417), (320, 427), (350, 424), (380, 412), (420, 402), (520, 400)]
# Valley between the two lower lobes: (parting column, depth px, half width px,
# rows over which it deepens). The volume normals (VOL_LOBES) follow it.
VALLEY = (306.0, 8.0, 20.0, (190.0, 300.0))
# Hanging sections below the cap: row -> (half width rx, depth ry, superellipse exponent).
SECT = [(116, 68, 60, 2.3), (140, 74, 66, 2.3), (175, 84, 62, 2.2), (210, 96, 56, 2.1),
        (260, 112, 52, 2.0), (320, 122, 50, 2.0)]
ENV_OFF = 3.0             # px the envelope sits over hair_front's cap
ENV_BLEND = (100.0, 132.0)  # rows over which the cap hands over to the hanging sections

# Skirt back surface (skirt.profiles), sampled once on a grid of back-view columns x rows.
SKIRT_GRID = (200, 1.0)   # +-px of back-view column and px step of the lookup grid
SKIRT_GAP = 7.0           # px kept between the skirt and a lock's underside
# Clearance envelope (clear_sx): the skirt's back surface max-filtered over
# CLEAR_MAXF (+-px across, +-rows), Gaussian-blurred (CLEAR_SIGMA px across, rows)
# with the filtered surface held under it, + SKIRT_GAP. A lock rides over the godet
# crests instead of following them. It meets the hair envelope in a soft maximum
# (CLEAR_SOFT px), so a lock end bends onto the skirt without a corner.
CLEAR_MAXF = (20, 6)
CLEAR_SIGMA = (25.0, 15.0)
CLEAR_SOFT = 8.0
# Any skirt clash left after a lock is built lifts its end in one smooth step along
# the lock's normal, ramped in over at least SKIRT_LIFT_LEN px of spine.
SKIRT_LIFT_LEN = 60.0

# Shingling: a lock's underside rests on the convex top of the layers under it plus
# GAP (m); the lift fades in over ROOT_FADE (m) from the root, which is buried in the
# scalp cap by design (ROOT_SINK px under its rest, rising onto it within 0.8 ROOT_FADE).
GAP = 0.00075
ROOT_FADE = 0.05
ROOT_SINK = 5.0
ROOT_SINK_SIDE = 8.0
SIDE_FACE_ROWS = (150.0, 215.0)   # rows over which an outer lock's face turns from the scalp's to its own
SHINGLE_SMOOTH = 0.03       # m, sigma of the lift along a lock
SETTLE_ITERS = 4

# White-to-mint fade shared by the whole mass: it starts at row G0 (the left
# lobe a little lower than the right, as on the sheet) and is full G_SPAN rows on.
G0 = ((250.0, 334.0), (360.0, 316.0))     # (bx, start row) at the two sides
G_SPAN = 130.0
G_RIPPLE = 9.0      # rows

DEBUG = False       # print the shingle / skirt lift needs per settle pass
RECORD = None       # a list: build() appends (object name, strand, info) per lock (diagnostics)


# ---------------------------------------------------------------- panel frame
def P(bx, sx, row):
    """Panel pixels (back-view column, side-view column, row) -> world Vector."""
    return Vector((spec.px_to_h(CX - bx), spec.px_to_h(sx - CX), spec.px_to_z(row)))


def W(bx, sx, row):
    """Panel pixels -> world numpy point(s) (broadcasts)."""
    bx, sx, row = np.broadcast_arrays(np.asarray(bx, float), np.asarray(sx, float), np.asarray(row, float))
    return np.stack([(CX - bx) / PX, (sx - CX) / PX, (spec.SHEET_GROUND_Y - row) / PX], -1)


def to_px(v):
    """World point(s) (Vector or (..., 3) array) -> (bx, sx, row) panel pixels."""
    if isinstance(v, Vector):
        return CX - v.x * PX, CX + v.y * PX, spec.SHEET_GROUND_Y - v.z * PX
    v = np.asarray(v, float)
    return CX - v[..., 0] * PX, CX + v[..., 1] * PX, spec.SHEET_GROUND_Y - v[..., 2] * PX


def skull(az, pol, lift=SCALP_LIFT):
    """Point on the (lifted) skull ellipsoid, returned in world space."""
    a, p = math.radians(az), math.radians(pol)
    cx, cy, cr = SKULL_C
    rx, ry, rz = (r * lift for r in SKULL_R)
    X = cx + rx * math.sin(p) * math.sin(a)
    Y = cy + ry * math.sin(p) * math.cos(a)
    row = cr - rz * math.cos(p)
    return Vector((spec.px_to_h(X), spec.px_to_h(Y), spec.px_to_z(row)))


def table(tab, row):
    """Piecewise-linear lookup in [(row, v...), ...] (clamped)."""
    if row <= tab[0][0]:
        return tab[0][1:]
    for (r0, *a), (r1, *b) in zip(tab, tab[1:]):
        if row <= r1:
            u = (row - r0) / (r1 - r0)
            return tuple(x + (y - x) * u for x, y in zip(a, b))
    return tab[-1][1:]


def stable(tab, row):
    """Slope-continuous (cubic Hermite, Catmull-Rom tangents) lookup in
    [(row, v...), ...], clamped: the envelope has no creases at the rows
    where the measured profile changes slope."""
    if row <= tab[0][0]:
        return tab[0][1:]
    if row >= tab[-1][0]:
        return tab[-1][1:]
    n = len(tab)
    i = next(k for k in range(n - 1) if row <= tab[k + 1][0])
    r0, r1 = tab[i][0], tab[i + 1][0]
    h = r1 - r0
    u = (row - r0) / h
    h00, h10 = 2 * u ** 3 - 3 * u ** 2 + 1, u ** 3 - 2 * u ** 2 + u
    h01, h11 = -2 * u ** 3 + 3 * u ** 2, u ** 3 - u ** 2
    out = []
    for c in range(1, len(tab[0])):
        def slope(k):
            a, b = tab[max(k - 1, 0)], tab[min(k + 1, n - 1)]
            return (b[c] - a[c]) / (b[0] - a[0])
        out.append(h00 * tab[i][c] + h10 * h * slope(i) + h01 * tab[i + 1][c] + h11 * h * slope(i + 1))
    return tuple(out)


def smooth01(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def _se_back(dx, w, d, e):
    """Depth behind a superellipse's centre at offset dx (half axes w, d)."""
    u = min(1.0, abs(dx) / w)
    return d * (1.0 - u ** e) ** (1.0 / e)


def env_sx(bx, row):
    """Side-view column of the hair envelope at back-view (bx, row)."""
    dx = bx - CX
    b = smooth01((row - ENV_BLEND[0]) / (ENV_BLEND[1] - ENV_BLEND[0]))
    sect = 0.0
    if b > 0.0:
        rx, ry, e = stable(SECT, row)
        sect = stable(MASS_BACK, row)[0] - ry + _se_back(dx, rx, ry, e)
        # the two lobes part in a shallow valley from the shoulder blades down
        bx0, depth, half, (r0, r1) = VALLEY
        sect -= depth * smooth01((row - r0) / (r1 - r0)) * math.exp(-((bx - bx0) / half) ** 2)
    if b >= 1.0:
        return sect
    # piecewise-linear like hair_front's own cap loft, so ENV_OFF holds exactly
    w, f, bk = table(CAP_PROFILE, row)
    cap = (f + bk) / 2 + _se_back(dx, w + ENV_OFF, (bk - f) / 2 + ENV_OFF, CAP_EXP)
    return cap + (sect - cap) * b


def env_point(bx, row):
    return P(bx, env_sx(bx, row), row)


# ---------------------------------------------------------------- skirt clearance
_SKIRT_TAB = {}


def _skirt_table():
    """(rows, columns x, back y (rows, cols), NaN where the cloth's back half does not
    reach): the rear-most y (px, +Y = behind) of the skirt's outer cloth at world x px
    and panel row, from skirt.profiles(skirt.fold_table())."""
    if 'tab' in _SKIRT_TAB:         # (the skirt's tables are fixed data: computed once)
        return _SKIRT_TAB['tab']
    folds = _skirt.fold_table()
    pts = _skirt.profiles(folds)
    half, step = SKIRT_GRID
    xs = np.arange(-half, half + step / 2, step)
    rows = np.arange(math.floor(pts[:, :, 2].min()), math.ceil(pts[:, :, 2].max()) + step / 2, step)
    out = np.full((len(rows), len(xs)), np.nan)
    a, b = pts[:, :-1, :], pts[:, 1:, :]
    idx = np.arange(len(pts))
    for ri, row in enumerate(rows):
        hit = (a[:, :, 2] <= row) & (row <= b[:, :, 2]) & (b[:, :, 2] > a[:, :, 2])
        f = np.where(hit, (row - a[:, :, 2]) / np.where(hit, b[:, :, 2] - a[:, :, 2], 1.0), 0.0)
        k = np.argmax(hit, axis=1)
        ok = hit.any(axis=1)
        x = a[idx, k, 0] + (b[idx, k, 0] - a[idx, k, 0]) * f[idx, k]
        y = a[idx, k, 1] + (b[idx, k, 1] - a[idx, k, 1]) * f[idx, k]
        x1, y1, ok1 = np.roll(x, -1), np.roll(y, -1), np.roll(ok, -1)
        seg = ok & ok1 & (x != x1) & ((y > 0) | (y1 > 0))
        x0, y0, x1, y1 = x[seg], y[seg], x1[seg], y1[seg]
        if not len(x0):
            continue
        lo, hi = np.minimum(x0, x1), np.maximum(x0, x1)
        inside = (xs[None, :] >= lo[:, None]) & (xs[None, :] <= hi[:, None])
        s = (xs[None, :] - x0[:, None]) / (x1 - x0)[:, None]
        yy = np.where(inside, y0[:, None] + (y1 - y0)[:, None] * s, -np.inf)
        best = yy.max(axis=0)
        out[ri] = np.where(best > 0, best, np.nan)
    tab = (rows, xs, out)
    _SKIRT_TAB['tab'] = tab
    return tab


def _grid_lookup(tab, bx, row):
    """Bilinear lookup (side-view column) in a (rows, xs, y) grid; NaN outside / at holes."""
    rows, xs, ys = tab
    bx, row = np.broadcast_arrays(np.asarray(bx, float), np.asarray(row, float))
    x = CX - bx                     # world x px (bx: image-left = +X)
    step = rows[1] - rows[0]
    fr, fx = (row - rows[0]) / step, (x - xs[0]) / (xs[1] - xs[0])
    out = np.full(bx.shape, np.nan)
    ok = (fr >= 0) & (fr <= len(rows) - 1) & (fx >= 0) & (fx <= len(xs) - 1)
    if not ok.any():
        return out
    r0 = np.minimum(fr[ok].astype(int), len(rows) - 2)
    c0 = np.minimum(fx[ok].astype(int), len(xs) - 2)
    u, v = fr[ok] - r0, fx[ok] - c0
    q00, q10, q01, q11 = ys[r0, c0], ys[r0 + 1, c0], ys[r0, c0 + 1], ys[r0 + 1, c0 + 1]
    val = (q00 * (1 - u) + q10 * u) * (1 - v) + (q01 * (1 - u) + q11 * u) * v
    # at the cloth's edge: the largest known corner, if any
    corners = np.stack([q00, q10, q01, q11], -1)
    edge = np.isnan(val) & ~np.all(np.isnan(corners), -1)
    if edge.any():
        val[edge] = np.nanmax(corners[edge], -1)
    out[ok] = CX + val
    return out


def skirt_sx(bx, row):
    """Side-view column of the skirt's back surface at back-view column bx
    (None above, below or beside the skirt's back half)."""
    v = float(_grid_lookup(_skirt_table(), bx, row))
    return None if math.isnan(v) else v


def _maxf(a, r, axis):
    """Sliding maximum (+-r samples) along an axis, NaN as -inf."""
    a = np.where(np.isnan(a), -np.inf, a)
    pad = [(0, 0)] * a.ndim
    pad[axis] = (r, r)
    p = np.pad(a, pad, constant_values=-np.inf)
    win = np.lib.stride_tricks.sliding_window_view(p, 2 * r + 1, axis=axis)
    return win.max(-1)


def _nblur(a, sigma, axis):
    """Gaussian blur along an axis over the finite samples only (normalised)."""
    ok = np.isfinite(a)
    r = int(math.ceil(3 * sigma))
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    num = np.apply_along_axis(lambda v: np.convolve(v, k, 'same'), axis, np.where(ok, a, 0.0))
    den = np.apply_along_axis(lambda v: np.convolve(v, k, 'same'), axis, ok.astype(float))
    return np.where(den > 0.05 * k.sum(), num / np.maximum(den, 1e-12), np.nan)


def _clear_table():
    """(rows, xs, y): the smooth clearance envelope (see CLEAR_*), side-view y px - CX."""
    if 'clear' in _SKIRT_TAB:
        return _SKIRT_TAB['clear']
    rows, xs, S = _skirt_table()
    M = _maxf(_maxf(S, CLEAR_MAXF[0], 1), CLEAR_MAXF[1], 0)
    M = np.where(np.isfinite(M), M, np.nan)

    def blur(a):
        return _nblur(_nblur(a, CLEAR_SIGMA[0], 1), CLEAR_SIGMA[1], 0)
    E = blur(M)
    for _ in range(3):
        E = blur(np.fmax(E, M))
    E = np.fmax(E, M)
    E = _nblur(_nblur(E, CLEAR_SIGMA[0] / 4, 1), CLEAR_SIGMA[1] / 4, 0)
    tab = (rows, xs, E + SKIRT_GAP)
    _SKIRT_TAB['clear'] = tab
    return tab


def clear_sx(bx, row):
    """Smooth clearance envelope (side-view column) at back-view (bx, row): NaN where
    the skirt is not behind."""
    return _grid_lookup(_clear_table(), bx, row)


def _softmax(a, b, k=CLEAR_SOFT):
    a, b = np.asarray(a, float), np.asarray(b, float)
    b = np.where(np.isnan(b), -1e9, b)
    m = np.maximum(a, b)
    return m + k * np.log(np.exp((a - m) / k) + np.exp((b - m) / k))


# ---------------------------------------------------------------- colour
def grad_global(bx, row):
    """Shared white (0) -> mint (1) fade of the back mass (scalars or arrays)."""
    (b0, r0), (b1, r1) = G0
    bx, row = np.asarray(bx, float), np.asarray(row, float)
    t = np.clip((bx - b0) / (b1 - b0), 0, 1)
    g0 = r0 + (r1 - r0) * t * t * (3 - 2 * t)
    # a slow ripple across the back: neighbouring locks start their fade at
    # slightly different heights, but as one smooth field, not per lock
    g0 = g0 + G_RIPPLE * np.sin((bx - CX) / 34.0)
    return hk.smooth01((row - g0) / G_SPAN)


# ---------------------------------------------------------------- normals
# The custom normals are mostly the normal of one smooth volume plus a share of each
# strand's own (final mesh) normal, so the hair reads as one continuously lit mass
# high up instead of a stack of strips, with no shading seam where it meets
# hair_front:
# - above the skull centre, the skull ellipsoid (as hair_front);
# - below it, a vertical elliptic cylinder, blended in over VOL_BLEND_ROWS
#   rows so there is no crease at the skull's equator;
# - from the shoulder blades down, the cylinder splits into the sheet's two
#   lobes (VOL_LOBES): two cylinders that meet in a soft valley at the lobes'
#   parting (the sheet's long shade wedge beside the parting).
VOL_AXES_LOW = (92.0, 80.0)    # single cylinder half axes (X, Y) px below the skull
VOL_BLEND_ROWS = 40.0
VOL_LOBES = dict(offset=50.0, axes=(42.0, 110.0), valley=18.0, rows=(165.0, 285.0))
VOL_KEEP = 0.25     # own-normal share of the under-layer (and the floor of the blend)
KEEP_TOP = 0.3      # ... of a lock high up,
KEEP_LOW = 0.55     # ... on its free lower length (KEEP_ROWS) ...
KEEP_ROWS = (210.0, 340.0)
CURL_KEEP = 0.7     # ... and through a curl or sub-tip (it shades as its own form)
SIDE_KEEP = 0.6     # the outer side locks


def _lobe_normal(dx, dy, single):
    """Normal of the two-lobe volume: each lobe's inner flank (towards the
    parting) turns into the valley; its outer flank keeps the single
    cylinder's normal (`single`), so the mass's outer sides shade as before."""
    lb = VOL_LOBES
    xs = CX - VALLEY[0] - SKULL_C[0]               # parting, X px from the axis
    ax, ay = lb['axes']
    s = smooth01((dx - xs) / lb['valley'] + 0.5)   # 1 on the character's left lobe
    out = Vector((0.0, 0.0, 0.0))
    for side, wgt in ((1.0, s), (-1.0, 1.0 - s)):
        xc = xs + side * lb['offset']
        n = Vector(((dx - xc) / ax ** 2, dy / ay ** 2, 0.0))
        inner = smooth01(0.5 - side * (dx - xc) / lb['valley'])
        n = (n.normalized() if n.length > 1e-12 else single) * inner + single * (1.0 - inner)
        out += n * wgt
    return out


def volume_normal(co, lobes=True):
    """Shading normal of the hair volume at world point co. lobes=False
    leaves out the two-lobe valley turn: the direction straight out of the
    mass (a lock's outer face)."""
    cx, cy, cr = SKULL_C
    dx = co.x * PX - cx
    dy = co.y * PX - cy
    row = spec.SHEET_GROUND_Y - co.z * PX
    dz = cr - row                                   # + above the skull centre
    rx, ry, rz = SKULL_R
    top = Vector((dx / rx ** 2, dy / ry ** 2, max(dz, 0.0) / rz ** 2))
    # Below the skull the field depends on the position across the back only
    # (the envelope's depth there, not the point's own): locks lying at
    # slightly different depths then shade alike.
    dy = env_sx(CX - cx - dx, row) - CX - cy
    ax, ay = VOL_AXES_LOW
    low = Vector((dx / ax ** 2, dy / ay ** 2, 0.0))
    b = smooth01((row - VOL_LOBES['rows'][0]) / (VOL_LOBES['rows'][1] - VOL_LOBES['rows'][0]))
    if lobes and b > 0.0 and low.length > 1e-12:
        low = low.normalized()
        low = low * (1.0 - b) + _lobe_normal(dx, dy, low) * b
    t = smooth01(-dz / VOL_BLEND_ROWS)
    n = Vector((0.0, 0.0, 0.0))
    if top.length > 1e-12:
        n += top.normalized() * (1.0 - t)
    if low.length > 1e-12:
        n += low.normalized() * t
    return n.normalized() if n.length > 1e-9 else Vector((0.0, 1.0, 0.0))


def _out_normal(p):
    """Direction straight out of the mass at numpy point p (a lock's facing)."""
    return np.array(volume_normal(Vector(p), lobes=False))


def set_volume_normals(me, shading, vol):
    """shading: own-normal share per vertex; vol: volume normal per vertex."""
    normals = []
    for v, nv, keep in zip(me.vertices, vol, shading):
        own = Vector(v.normal)
        # On the hanging mass a lock's side edges (own normal across the volume) take
        # the volume's normal: they shade with their neighbours instead of as thin
        # strips. Curls and free ends (keep above VOL_KEEP) keep their own form shading.
        edge = max(0.0, own.dot(nv)) ** 2
        keep *= edge + (1.0 - edge) * smooth01((keep - VOL_KEEP) / (CURL_KEEP - VOL_KEEP))
        n = nv * (1 - keep) + own * keep
        normals.append(n.normalized() if n.length > 1e-9 else Vector(v.normal))
    me.normals_split_custom_set_from_vertices(normals)


# ---------------------------------------------------------------- layers under the locks
class _Surface:
    """A lower layer for the kernel's shingling (hk.rest_on): just its triangles."""

    def __init__(self, tris, name):
        self.tris = np.asarray(tris, float)
        self.name = name
        self.lo, self.hi = self.tris.reshape(-1, 3).min(0), self.tris.reshape(-1, 3).max(0)

    def triangles(self):
        return self.tris


def _grid_tris(G):
    """(F, 3, 3) triangles of a (R, C, 3) point grid (open both ways)."""
    a, b, c, d = G[:-1, :-1], G[:-1, 1:], G[1:, 1:], G[1:, :-1]
    return np.concatenate([np.stack([a, b, c], -2).reshape(-1, 3, 3), np.stack([a, c, d], -2).reshape(-1, 3, 3)])


def _cap_proxy():
    """hair_front's scalp cap (the CAP_PROFILE superellipses: they contain the cap's
    back half) as triangles over the back of the head: the locks rest on it."""
    r0, r1 = CAP_PROFILE[0][0], CAP_PROFILE[-1][0]
    rows = np.linspace(r0, r1, int((r1 - r0) / 3.0) + 1)
    th = np.radians(np.linspace(-25.0, 205.0, 70))
    G = []
    for r in rows:
        w, f, bk = table(CAP_PROFILE, r)
        c, hd = (f + bk) / 2, (bk - f) / 2
        cs, sn = np.cos(th), np.sin(th)
        X = w * np.sign(cs) * np.abs(cs) ** (2 / CAP_EXP)
        Y = hd * np.sign(sn) * np.abs(sn) ** (2 / CAP_EXP)
        G.append(W(CX - X, c + Y, np.full_like(X, r)))
    return _Surface(_grid_tris(np.array(G)), 'cap')


# The surface the under row of locks rests on, as an offset (px, along the volume normal)
# from the envelope per row: just over the scalp cap high up (the envelope sits ENV_OFF
# over it there), the under-layer's outer face lower down.
BASE = [(0, -2.6), (110, -2.6), (122, -2.2), (134, -1.8), (165, -2.0), (210, -0.5), (340, 0.0), (386, -1.5)]
# Under-layer: rows UNDER_ROWS every UNDER_STEP px, UNDER_COLS columns across. Its outer
# face is BASE, its middle UNDER_T px thick (thinner at its top edge on the cap, UNDER_T_TOP
# rows), thinning to UNDER_RIM px at its side edges, and it keeps UNDER_CAP_GAP px off the
# cap. Half width per row in the back view: UNDER_HW (it spans well over rig.HAIR_LOCK_SPAN
# round the head, so the rig hangs it from the sector chains, never a lock chain).
UNDER_ROWS = (110.0, 370.0)
UNDER_STEP = 8.0
UNDER_TOP_ROWS = (110.0, 128.0, 146.0, 164.0, 184.0, 205.0)
UNDER_COLS = 21
UNDER_T = 1.6
UNDER_T_TOP = (110.0, 142.0, 0.3)
UNDER_RIM = 0.4
UNDER_WRAP = 30.0           # px the side edges curl forward on the hanging length ...
UNDER_WRAP_ROWS = (175.0, 335.0)   # ... faded in from / out after these rows
UNDER_CAP_GAP = 0.4
UNDER_HW = [(110, 76), (130, 78), (170, 76), (210, 76), (250, 82), (290, 90), (320, 92),
            (345, 84), (360, 66), (370, 42)]


def cap_sx(bx, row):
    """Side-view column of hair_front's cap (its CAP_PROFILE superellipse) at back-view
    (bx, row): None below the cap or beside it."""
    if not CAP_PROFILE[0][0] <= row <= CAP_PROFILE[-1][0]:
        return None
    w, f, bk = table(CAP_PROFILE, row)
    if abs(bx - CX) >= w:
        return None
    return (f + bk) / 2 + _se_back(bx - CX, w, (bk - f) / 2, CAP_EXP)


def _under_layer():
    """(outer (R, C, 3), inner (R, C, 3)) world grids of the under-layer."""
    # sparse rows over the nape, where the rig fades the hair from the head bone to the
    # chains (a turned head shears that band: longer edges stretch less), UNDER_STEP below
    r_top = UNDER_TOP_ROWS[-1]
    n_r = int(round((UNDER_ROWS[1] - r_top) / UNDER_STEP))
    rows = np.concatenate([UNDER_TOP_ROWS[:-1], np.linspace(r_top, UNDER_ROWS[1], n_r + 1)])
    a = np.linspace(-1.0, 1.0, UNDER_COLS)
    outer, inner = [], []
    r0, r1, t0 = UNDER_T_TOP
    for r in rows:
        hw = stable(UNDER_HW, r)[0]
        base = stable(BASE, r)[0]
        # (evenly spaced across: crowded edge columns made short edges that a head turn
        # stretched, the fade to the head bone differing a little across them)
        bxs = CX - hw * a
        t_mid = t0 + (UNDER_T - t0) * smooth01((r - r0) / (r1 - r0))
        thick = UNDER_RIM + (t_mid - UNDER_RIM) * (1.0 - a * a) ** 0.5
        # the side edges curl forward round her back (seen from the side the mass reads
        # solid down to the back, as on the sheet), on the hanging length only
        wrap = UNDER_WRAP * smooth01((r - UNDER_WRAP_ROWS[0]) / 40.0) * (1.0 - smooth01((r - UNDER_WRAP_ROWS[1]) / 30.0))
        o_row, i_row = [], []
        for bx, t, aa in zip(bxs, thick, a):
            e = env_point(bx, r)
            n = volume_normal(e, lobes=False)
            po = e + n * (base / PX) - Vector((0.0, wrap * (1.0 - math.cos(aa * math.pi / 2)) / PX, 0.0))
            pb, psx, prow = to_px(po)
            # the inner face keeps off the cap and clears the skirt (the smooth envelope, as the locks)
            cs = cap_sx(pb, prow)
            need = float(clear_sx(pb, prow)) + t
            if cs is not None:
                need = np.fmax(need, cs + UNDER_CAP_GAP + t / max(n.y, 0.3))
            if not math.isnan(need):
                psx = float(_softmax(psx, need, 1.0))
                po = P(pb, psx, prow)
            o_row.append(np.array(po))
            i_row.append(np.array(po - n * (t / PX)))
        outer.append(o_row)
        inner.append(i_row)
    return np.array(outer), np.array(inner)


def _emit_grid_shell(bm, outer, inner, gfun, keep):
    """A closed thin shell from outer / inner grids (R, C, 3) into bm: both faces,
    the side rims and ladder caps at the first and last rows. Returns the new verts."""
    R, C = outer.shape[:2]
    glay = bm.verts.layers.float.get(common.GRAD_ATTR) or bm.verts.layers.float.new(common.GRAD_ATTR)
    klay = bm.verts.layers.float.get(_KEEP_ATTR) or bm.verts.layers.float.new(_KEEP_ATTR)
    vo = [[bm.verts.new(p.tolist()) for p in row] for row in outer]
    vi = [[bm.verts.new(p.tolist()) for p in row] for row in inner]
    verts = [v for row in vo + vi for v in row]
    for v in verts:
        bx, _, r = to_px(np.array(v.co))
        v[glay] = float(gfun(bx, r))
        v[klay] = keep
    for j in range(R - 1):
        for k in range(C - 1):
            bm.faces.new((vo[j][k], vo[j][k + 1], vo[j + 1][k + 1], vo[j + 1][k]))      # outer (+N)
            bm.faces.new((vi[j][k], vi[j + 1][k], vi[j + 1][k + 1], vi[j][k + 1]))      # inner
        for k, s in ((0, 1), (C - 1, -1)):                                               # side rims
            f = (vo[j][k], vo[j + 1][k], vi[j + 1][k], vi[j][k])
            bm.faces.new(f if s > 0 else f[::-1])
    for j, s in ((0, 1), (R - 1, -1)):                                                   # top / bottom
        for k in range(C - 1):
            f = (vo[j][k], vi[j][k], vi[j][k + 1], vo[j][k + 1])
            bm.faces.new(f if s > 0 else f[::-1])
    return verts


def _shell_tris(outer, inner):
    return np.concatenate([_grid_tris(outer), _grid_tris(inner),
                           _grid_tris(np.stack([outer[:, 0], inner[:, 0]], 1)),
                           _grid_tris(np.stack([outer[:, -1], inner[:, -1]], 1)),
                           _grid_tris(np.stack([outer[0], inner[0]], 0)),
                           _grid_tris(np.stack([outer[-1], inner[-1]], 0))])


# ---------------------------------------------------------------- lock authoring
# Mass edges in the back view: (row, left bx, right bx) (left = the character's left).
PRIM_EDGES = [(150, 254, 386), (200, 254, 386), (250, 248, 392), (300, 230, 410),
              (350, 214, 421), (400, 213, 423), (440, 218, 424)]
PRIM_ROWS = (150.0, 200.0, 250.0, 300.0, 345.0, 390.0)   # rows of the hanging key points
PRIM_SPREAD = (0.06, 0.94)   # share of the mass width the outer locks' centres sit at
PRIM_COVER = 1.22            # lock width / (mass width / number of locks): neighbours overlap
PRIM_LAYER_W = (1.06, 0.95)  # width factor of the under / over row (the over row covers the gaps)
PRIM_SCALP = ((26.0, 15.0), (60.0, 27.0), (92.0, 33.0))   # (polar deg, width px) of the scalp keys
LAYER_STEP = 0.55            # the over row is authored this x its thickness over the under row
PRIM_ASPECT = 5.0            # width / thickness at the widest point (broad, flat locks)
PRIM_WRAP = (0.15, 0.12)     # crescent wrap at the root (hugging the skull) and down the lock
PRIM_WAVE = (6.0, 170.0)     # sideways amplitude px, wavelength rows
PRIM_WAVE_ROWS = (205.0, 285.0)   # rows over which the wave fades in
TIP_LEN = 0.09               # m over which a lock without a curl closes into its blade
CURL_TILT = 34.0             # deg a back-view curl turns out of the image plane (away from her)
N_RING = 16                  # vertices round a primary (12 / 14 / 16 by width otherwise)
FLAT_TOP = (0.5, (140.0, 280.0))  # a primary's thickness share above the first row, full by the second

# One entry per primary, the character's left to right. f: place across the mass;
# layer: 0 rests on the under-layer, 1 on the locks under it; end: last spine row;
# wf: width factor; ph: wave phase (deg; the locks of one lobe wave nearly together);
# keys: (bx, row) overrides of the lower key points (sheet-fitted ends); curl: (radius
# px, turn deg, image-x direction or 'out', core); split: sub-tips.
PRIMS = [
    dict(name='A', f=0.0, layer=1, wf=1.08, ph=0.0, end=452,
         keys=[(244, 240), (234, 285), (223, 325), (217, 365), (216, 400), (221, 430), (233, 452)],
         curl=(40.0, 205.0, 1, 0.72), split=(0.86, (0.56, 0.44), 8.0, (1.0, 0.72))),
    dict(name='L1', f=0.21, layer=0, wf=1.0, ph=20.0, end=380,
         keys=[(266, 300), (262, 335), (262, 360), (265, 380)],
         curl=(19.0, 200.0, (0.8, 1.0, 0.6), 0.7)),
    dict(name='C', f=0.42, layer=1, wf=0.95, ph=40.0, end=402),
    dict(name='D', f=0.6, layer=0, wf=1.0, ph=165.0, end=448,
         keys=[(332, 240), (335, 290), (334, 330), (334, 368), (339, 404), (346, 428), (352, 448)],
         curl=(30.0, 190.0, -1, 0.72), split=(0.87, (0.55, 0.45), 8.0, (1.0, 0.75))),
    dict(name='E', f=0.8, layer=1, wf=1.0, ph=185.0, end=380,
         keys=[(374, 290), (382, 326), (393, 354), (404, 380)]),
    dict(name='F', f=1.0, layer=0, wf=1.0, ph=205.0, end=442,
         keys=[(396, 290), (408, 330), (416, 370), (420, 404), (424, 424), (427, 442)],
         curl=(22.0, 165.0, -1, 0.72)),
]


def _pchip(xk, yk, x):
    """Monotone cubic (Fritsch-Carlson) interpolation (no overshoot)."""
    xk, yk = np.asarray(xk, float), np.asarray(yk, float)
    x = np.clip(np.asarray(x, float), xk[0], xk[-1])
    h = np.diff(xk)
    d = np.diff(yk) / h
    m = np.zeros_like(yk)
    m[0], m[-1] = d[0], d[-1]
    for i in range(1, len(yk) - 1):
        if d[i - 1] * d[i] > 0:
            m[i] = 2 * d[i - 1] * d[i] / (d[i - 1] + d[i])
    i = np.clip(np.searchsorted(xk, x, 'right') - 1, 0, len(xk) - 2)
    t = (x - xk[i]) / h[i]
    t2, t3 = t * t, t * t * t
    return ((2 * t3 - 3 * t2 + 1) * yk[i] + (t3 - 2 * t2 + t) * h[i] * m[i]
            + (-2 * t3 + 3 * t2) * yk[i + 1] + (t3 - t2) * h[i] * m[i + 1])


def _key_xy(k):
    """A key point -> (bx, row) (scalp points via the skull ellipsoid)."""
    if k[0] == 's':
        bx, _, row = to_px(skull(k[1], k[2]))
        return bx, row
    return float(k[0]), float(k[-1])


def _section_under(w_px, t_px, s, wrap=hk.WRAP):
    """How far below the spine (px) the crescent's underside reaches at across params s."""
    _x, y = hk.section(2, w_px / PX, t_px / PX, wrap, s=np.asarray(s, float), top=np.zeros(len(s), bool))
    return -np.asarray(y) * PX


def prim_defs():
    """Kernel inputs of the primaries: dicts with the key path, widths, layer, ends."""
    n = len(PRIMS)
    out = []
    for i, p in enumerate(PRIMS):
        f = p['f']
        lw = PRIM_LAYER_W[p['layer']] * p['wf']
        az = 64.0 - 128.0 * f                        # scalp azimuth: + = her left
        drop = 6.0 * abs(f - 0.5) * 2                # outer roots a little lower on the skull
        keys = [('s', az * (1.0 + 0.03 * k), pol + drop * (1.0 - 0.5 * k)) for k, (pol, _w) in enumerate(PRIM_SCALP)]
        ws = [w * lw for _pol, w in PRIM_SCALP]
        lower = {int(r): bx for bx, r in p.get('keys', [])}
        rows = [r for r in PRIM_ROWS if r < p['end'] - 20] + [p['end']]
        if 'keys' in p:
            top = min(r for _bx, r in p['keys'])
            rows = [r for r in rows if r < top] + [r for _bx, r in p['keys']]
        for r in rows:
            lo, hi = stable(PRIM_EDGES, r)
            bx = lower.get(int(r), lo + (hi - lo) * (PRIM_SPREAD[0] + (PRIM_SPREAD[1] - PRIM_SPREAD[0]) * f))
            keys.append((bx, r))
            ws.append((hi - lo) / n * PRIM_COVER * lw)
        out.append(dict(p, keys=keys, w=ws, curled=p.get('curl') is not None))
    return out


def _dense_path(keys, step=1.5):
    """Dense (bx, row) samples (about step px apart) of a C2 spline through the keys."""
    Q = np.array([(*_key_xy(k), 0.0) for k in keys])
    tk, ev = hk._c2_spline(Q, 0.5)
    t = np.concatenate([np.linspace(tk[i], tk[i + 1], 40, endpoint=False) for i in range(len(Q) - 1)] + [[tk[-1]]])
    D = ev(t)[:, :2]
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(D, axis=0), axis=1))])
    ss = np.linspace(0.0, s[-1], max(8, int(s[-1] / step)))
    D = np.stack([np.interp(ss, s, D[:, 0]), np.interp(ss, s, D[:, 1])], 1)
    # the key points' arc positions (for per-key widths)
    sk = np.interp(tk, t, np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(ev(t)[:, :2], axis=0), axis=1))]))
    return D, ss, sk


def _mass_spine(d):
    """World control points and the width profile (u -> m) of a mass lock."""
    D, s2, sk = _dense_path(d['keys'])
    bx, row = D[:, 0].copy(), D[:, 1].copy()
    w = _pchip(sk, d['w'], s2)
    # sideways S-wave, faded in below the shoulders and down to 40 % over the last 60 rows
    amp, lam = PRIM_WAVE
    amp *= d.get('amp', 1.0)
    r_end = row[-1]
    env = np.array([smooth01((r - PRIM_WAVE_ROWS[0]) / (PRIM_WAVE_ROWS[1] - PRIM_WAVE_ROWS[0]))
                    * (1.0 - 0.8 * smooth01((r - (r_end - 70.0)) / 70.0)) for r in row])
    bx = bx + amp * env * np.sin(2 * np.pi * row / lam + math.radians(d['ph']))
    w_max = float(w.max())
    t_mid = w_max / d.get('aspect', PRIM_ASPECT)
    t = np.maximum(1.0, t_mid * (w / w_max) ** hk.T_EXP)
    # the underside on the layer under it: the base surface (BASE) + GAP for the under
    # row, about half an under lock higher for the over row (the shingling then lifts it
    # exactly onto the locks under it)
    wrap = PRIM_WRAP[1] + (PRIM_WRAP[0] - PRIM_WRAP[1]) * (1.0 - hk.smooth01(s2 / s2[-1] / 0.3))
    s_across = np.linspace(-1.0, 1.0, 9)
    und_mid = np.array([_section_under(w[i], t[i], s_across, wrap[i]).max() for i in range(len(row))])
    step = LAYER_STEP * t if d['layer'] else 0.0
    off = np.array([stable(BASE, r)[0] for r in row]) + GAP * PX + und_mid + step
    pts = []
    for i in range(len(row)):
        e = env_point(bx[i], row[i])
        n = volume_normal(e, lobes=False)
        sink = ROOT_SINK * (1.0 - smooth01(s2[i] / (0.8 * ROOT_FADE * PX)))
        p = e + n * ((off[i] - sink) / PX)
        # the section's underside clears the smooth skirt envelope (a soft maximum)
        pb, psx, pr = to_px(p)
        und = _section_under(w[i], t[i], s_across, wrap[i])
        cl = clear_sx(pb + 0.5 * w[i] * s_across, np.full(9, pr))
        if np.isfinite(cl).any():
            need = float(np.nanmax(cl + und))
            psx = float(_softmax(psx, need))
            p = P(pb, psx, pr)
        pts.append(np.array(p))
    pts = np.array(pts)
    return pts, w


def _resample(pts, spacing):
    """Resample a dense 3-D polyline about `spacing` m apart."""
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))])
    n = max(4, int(round(s[-1] / spacing)) + 1)
    ss = np.linspace(0.0, s[-1], n)
    return np.stack([np.interp(ss, s, pts[:, c]) for c in range(3)], 1)


def _width_fn(U, w_px, taper_len=None, length=None):
    """Kernel width callable (u -> m) from a width profile over the arc fraction U,
    closed into a blade over the last taper_len m of a lock of `length` m."""
    w_m = np.asarray(w_px, float) / PX
    if taper_len is None:
        return lambda u: np.interp(u, U, w_m)
    ut = max(0.4, 1.0 - taper_len / length)
    return lambda u: np.interp(u, U, w_m) * hk.taper(u, swell=None, tip=(ut, 2.2, 0.7))


def _curl_params(c, w_end_px):
    """Kernel curl() from (radius px, turn deg, image-x direction | 'out', core)."""
    R, turn, ix, core = c
    face = 'plane'
    if ix == 'out':
        # (a lock rolling back over itself, the broad face toward the curl centre: no roll)
        toward, face = 'out', 'keep'
    elif isinstance(ix, tuple):
        toward = ix                                              # a world direction
    else:
        tilt = math.radians(CURL_TILT)
        toward = (-ix * math.cos(tilt), math.sin(tilt), 0.0)     # image right = -X; +Y away from her
    w_c = core * w_end_px / PX
    # (a flat blade bending in its own plane: rho = (w / 2) / R, so R >= 1.25 w at rho 0.4)
    return hk.curl(turn=turn, toward=toward, face=face, radius=max(R / PX, 1.3 * w_c) if face == 'plane' else R / PX,
                   core=core, lead=1.8, taper=(1.5, 0.8))


def mass_lock_kwargs(d):
    """hk.strand keyword arguments for a primary (see prim_defs)."""
    pts, w = _mass_spine(d)
    P_ = _resample(pts, 0.012)
    Uw = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))])
    Uw /= Uw[-1]
    L = float(np.sum(np.linalg.norm(np.diff(pts, axis=0), axis=1)))
    kw = dict(points=P_, name=f'hair_back_{d["name"]}', facing=_out_normal, aspect=d.get('aspect', PRIM_ASPECT), flat=True,
              n=d.get('n', N_RING),
              wrap=lambda u: PRIM_WRAP[1] + (PRIM_WRAP[0] - PRIM_WRAP[1]) * (1.0 - hk.smooth01(u / 0.3)))
    if d['curled']:
        kw['width'] = _width_fn(Uw, w * _end_narrow(Uw, L))
        kw['curl'] = _curl_params(d['curl'], float(w[-1] * 0.62))
        if d.get('split'):
            at, shares, div, lengths = d['split']
            kw['split'] = hk.split(at=at, shares=shares, diverge=div, lengths=lengths)
    else:
        kw['width'] = _width_fn(Uw, w, TIP_LEN, L)
    return kw


def _end_narrow(U, L, share=0.62, length=0.14):
    """Width factor easing to `share` over the last `length` m of a spine that curls."""
    u0 = max(0.3, 1.0 - length / L)
    return 1.0 - (1.0 - share) * np.array([smooth01((u - u0) / (1.0 - u0)) for u in U])


# Outer side locks (character's left; the right side mirrors them): broad locks that
# grow out of the side of the mass behind the ear, fall over the back of the shoulder
# and hang along the back of the sleeve. Points as in the module docstring; w: width
# px per point; face: the outer face's direction (world, character's left side).
OUTER = [
    # shoulder flick: over the back of the shoulder, its end turning back and up in one
    # open flick (the sheet's green flick at sx ~420, row ~230 in the side view); long
    # enough to be a lock with its own chain (see _check_islands)
    dict(name='flick', pts=[('s', 86, 84), (252, 318, 128), (247, 323, 156), (243, 333, 190), (230, 345, 216),
                            (219, 357, 236), (211, 366, 250)],
         w=[8, 11, 14, 16, 17, 17, 17], face=(0.3, 1.0, 0.0), aspect=3.8, gr=(190, 255),
         curl=dict(turn=90.0, toward=(0.2, 1.0, 0.6), face='plane', radius=0.028, core=0.8, lead=1.6,
                   taper=(1.1, 1.0))),
    # wave lock: spreads over the back of the upper arm in two soft S lobes (the
    # green-tipped waves beside the sleeve top in the front view) and closes in a blade
    dict(name='wave', pts=[('s', 80, 98), (250, 326, 158), (236, 347, 200), (206, 353, 240),
                           (178, 360, 270), (154, 366, 298), (140, 366, 322), (131, 371, 342),
                           (126, 377, 360)],
         w=[11, 16, 21, 24, 25, 24, 20, 15, 8], face=(0.3, 1.0, 0.0), aspect=4.2, gr=(255, 330), tip=0.07),
    # crescent: hangs behind the sleeve to the cuff, then turns out and up past it as one
    # flat C-blade (the sheet's crescent: outer edge bx ~62 at rows 370-410, tip ~(84, 347))
    dict(name='crescent', pts=[('s', 72, 110), (254, 338, 170), (240, 357, 210), (215, 362, 252),
                               (188, 368, 298), (156, 375, 340), (124, 378, 380), (104, 381, 410)],
         w=[12, 17, 20, 22, 21, 20, 18, 16], face=(0.3, 1.0, 0.0), aspect=4.2, gr=(300, 395),
         curl=dict(turn=200.0, toward=(1.0, 0.15, 0.0), face='plane', radius=0.026, core=0.62, lead=1.8,
                   taper=(1.6, 0.8))),
]


def _base_point(bx, row, w_px, t_px, wrap=hk.WRAP):
    """World point of a spine resting on the base surface (BASE + GAP) at (bx, row)."""
    e = env_point(bx, row)
    n = volume_normal(e, lobes=False)
    und = float(_section_under(w_px, t_px, np.linspace(-1.0, 1.0, 9), wrap).max())
    return np.array(e + n * ((stable(BASE, row)[0] + GAP * PX + und) / PX))


def _side_spine(d):
    """World spine (key points) and widths (px) of an outer lock: the root on the scalp
    (sunk into the cap by design), the rest explicit (bx, sx, row) points; a lock lying
    along the side of the head is lifted off the cap by the shingling (_settle)."""
    w_k = np.array(d['w'], float)
    t_k = (w_k.max() / d.get('aspect', 3.0)) * (w_k / w_k.max()) ** hk.T_EXP
    pts = []
    for k, wi, ti in zip(d['pts'], w_k, t_k):
        if k[0] == 's':
            bx, _, row = to_px(skull(k[1], k[2]))
            p = _base_point(min(bx, CX - 1.0) if bx < CX else max(bx, CX + 1.0), row, wi, ti)
            p = p - np.array(volume_normal(Vector(p), lobes=False)) * (ROOT_SINK_SIDE / PX)
        elif len(k) == 2:
            p = _base_point(k[0], k[1], wi, ti)
        else:
            p = np.array(P(*k))
        pts.append(p)
    return np.array(pts), w_k


def side_lock_kwargs(d, side=1):
    """hk.strand keyword arguments for an outer lock; side -1 mirrors it to her right."""
    pts, w = _side_spine(d)
    L = float(np.sum(np.linalg.norm(np.diff(pts, axis=0), axis=1)))
    U = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))]) / L
    mir = np.array([side, 1.0, 1.0])
    pts = pts * mir
    face = np.array(d['face'], float) * mir
    def facing(p, face=face / np.linalg.norm(face)):
        # on the scalp the outer face follows the surface; hanging, it turns to `face`
        b = hk.smooth01((to_px(p)[2] - SIDE_FACE_ROWS[0]) / (SIDE_FACE_ROWS[1] - SIDE_FACE_ROWS[0]))
        return (1.0 - b) * _out_normal(p) + b * face
    kw = dict(points=pts, name=f'hair_back_{d["name"]}_{"L" if side > 0 else "R"}', facing=facing,
              aspect=d.get('aspect', 3.0))
    if 'curl' in d:
        c = dict(d['curl'])
        if not isinstance(c['toward'], str):
            c['toward'] = tuple(np.array(c['toward'], float) * mir)
        kw['curl'] = hk.curl(**c)
        kw['width'] = _width_fn(U, w)
    else:
        kw['width'] = _width_fn(U, w, d.get('tip', TIP_LEN), L)
    return kw


# ---------------------------------------------------------------- building a lock
def _strand_px(st):
    """Every vertex of a strand (all tubes and apexes) with its tube's ring index and
    the spine arc fraction it maps to (curl / sub-tip rings map to the spine's end)."""
    sl = st.meta['spine_len']
    out = []
    for tb in st.all_tubes():
        R = tb.rings
        u = np.minimum(tb.arc / sl, 1.0)
        out.append((R.reshape(-1, 3), np.repeat(u, R.shape[1]), np.repeat(tb.N, R.shape[1], 0)))
        if tb.apex is not None:
            out.append((tb.apex[None], np.array([min(1.0, tb.arc[-1] / sl)]), tb.N[-1:]))
    return (np.concatenate([o[0] for o in out]), np.concatenate([o[1] for o in out]),
            np.concatenate([o[2] for o in out]))


def _skirt_short(st):
    """(u, shortfall px along +Y) of every strand vertex against the real skirt + SKIRT_GAP."""
    V, u, N = _strand_px(st)
    bx, sx, row = to_px(V)
    sk = _grid_lookup(_skirt_table(), bx, row)
    short = np.where(np.isfinite(sk), sk + SKIRT_GAP - sx, 0.0)
    return u, np.maximum(short, 0.0), N


def _smooth_need(u, need, length, sigma_m):
    """A smooth lift profile over u (401 knots) at least `need` at each u: dilated,
    blurred and held over the raw need (as hk.rest_on)."""
    su = np.linspace(0.0, 1.0, 401)
    raw = np.zeros_like(su)
    idx = np.clip(np.round(np.asarray(u) * 400).astype(int), 0, 400)
    np.maximum.at(raw, idx, need)
    sig = max(1.0, sigma_m / max(length, 1e-6) * 400.0)
    r = int(math.ceil(1.5 * sig))
    dil = np.array([raw[max(0, i - r):i + r + 1].max() for i in range(len(raw))])
    sm = hk._blur(dil, sig)
    for _ in range(3):
        sm = hk._blur(np.maximum(sm, raw), sig)
    sm = np.maximum(sm, raw)
    return su, hk._blur(sm, 0.25 * sig)


class _Lift:
    def __init__(self, u, v):
        self.u, self.v = u, v

    def __call__(self, u):
        return np.interp(u, self.u, self.v)


def _settle(kw, lowers, root_fade=ROOT_FADE, iters=SETTLE_ITERS):
    """Build a lock (hk.strand), then lift its spine until its underside rests on the
    layers under it (hk.rest_on, + GAP) and every vertex clears the real skirt by
    SKIRT_GAP: each lift is one smooth displacement along the lock's normal (the skirt's
    ramped in over SKIRT_LIFT_LEN px or more toward the end). Validated on every build.
    Returns (strand, info)."""
    st = _strand(kw)
    su = np.linspace(0.0, 1.0, 401)
    total = np.zeros_like(su)
    near = [lo for lo in lowers if _overlaps(st, lo)]
    info = {}
    for _ in range(iters):
        L = st.meta['spine_len']
        need = np.zeros_like(su)
        if near:
            # the raw per-ring need, with the buried root (root_fade) asking for nothing
            # BEFORE the smoothing spreads it (spread first, the root's burial would
            # ask again on every pass and pile the lift up behind it)
            # (the spine's rings only: a curl's rings turn their normals away from the
            # spine's, and lifting the spine would not answer them)
            lf = hk.rest_on(st, near, gap=GAP, smooth=SHINGLE_SMOOTH, root_fade=0.0)
            spine = st.arc <= L + 1e-6
            raw = lf.need[:len(st.arc)] * hk.smooth01(st.arc / root_fade) * spine
            _su, sh = _smooth_need(np.minimum(st.arc / L, 1.0), raw, L, SHINGLE_SMOOTH)
            need = np.maximum(need, sh)
        u, short, _N = _skirt_short(st)
        if short.max() > 0.05:
            # the lift moves a vertex along the spine's normal where it maps (a curl with
            # the spine's end): its +Y share answers the skirt
            c = st.curve
            ny = np.interp(u * L, c['s'], c['N'][:, 1])
            _su, sk = _smooth_need(u, short / PX / np.maximum(ny, 0.35), L, SKIRT_LIFT_LEN / PX / 1.5)
            need = np.maximum(need, sk)
        if DEBUG:
            print('  settle %-22s it %d shingle %5.1f mm at u %.2f  skirt %5.1f px at u %.2f' % (
                kw['name'], _, 1000 * (sh.max() if near else 0), su[int(np.argmax(sh))] if near else 0,
                short.max(), u[int(np.argmax(short))]))
        if need.max() < 0.25 * GAP:
            break
        total = total + need
        st = _lifted(kw, su, total, L)
    info['lift_max'] = float(total.max())
    if near:
        lf = hk.rest_on(st, near, gap=GAP, smooth=SHINGLE_SMOOTH, root_fade=root_fade)
        free = (st.arc > root_fade) & (st.arc <= st.meta['spine_len'] + 1e-6)
        nd = lf.need[:len(free)]
        info['overlap'] = lf.overlap
        info['residual_mm'] = 1000 * float(nd[free].max()) if free.any() else 0.0
    _u, short, _N = _skirt_short(st)
    info['skirt_short_px'] = float(short.max())
    return st, info


def _strand(kw):
    """hk.strand(**kw), flattened high up (FLAT_TOP) and validated."""
    st = hk.strand(**dict({k: v for k, v in kw.items() if k != 'flat'}, check=False))
    if kw.get('flat'):
        _flatten(st)
    hk.validate(st)
    return st


def _flatten(st):
    """Thin a lock's section toward the crown (FLAT_TOP): each ring's offsets along its
    normal shrink about its underside, so the locks over the skull and shoulders lie
    as flat shingles (the kernel's thickness only follows the width)."""
    k0, (r0, r1) = FLAT_TOP
    R, C, N = st.rings, st.centres, st.N
    _bx, _sx, row = to_px(C)
    k = k0 + (1.0 - k0) * hk.smooth01((row - r0) / (r1 - r0))
    for j in np.flatnonzero(k < 0.999):
        y = (R[j] - C[j]) @ N[j]
        R[j] -= ((1.0 - k[j]) * (y - y.min()))[:, None] * N[j]


def _lifted(kw, su, total, length, tries=3):
    """hk.strand lifted by `total` (over the knots su); a lift whose bends break the
    kernel's limits is spread wider along the lock (never lower) and tried again."""
    sig = SHINGLE_SMOOTH
    for k in range(tries + 1):
        try:
            return _strand(dict(kw, lift=_Lift(su, total.copy())))
        except hk.HairKernelError:
            if k == tries:
                raise
        sig *= 1.6
        _u, sm = _smooth_need(su, total, length, sig)
        total[:] = np.maximum(total, sm)


def _overlaps(st, lo, pad=0.02):
    a = np.concatenate([tb.rings.reshape(-1, 3) for tb in st.all_tubes()])
    alo, ahi = a.min(0) - pad, a.max(0) + pad
    if isinstance(lo, _Surface):
        blo, bhi = lo.lo, lo.hi
    else:
        b = np.concatenate([tb.rings.reshape(-1, 3) for tb in lo.all_tubes()])
        blo, bhi = b.min(0), b.max(0)
    return bool(np.all(ahi >= blo) and np.all(bhi >= alo))


# ---------------------------------------------------------------- painting
_KEEP_ATTR = 'hb_keep'


def _paint(st, gfun, keepfun):
    """toon_grad (monotone down the lock: a curl turning back up stays green) and the
    own-normal share (attribute _KEEP_ATTR) on every tube of a strand."""
    sl = st.meta['spine_len']

    def tube(tb, g_start):
        bx, _sx, row = to_px(tb.rings)
        g = np.asarray(gfun(bx, row), float)
        cb, _s, cr = to_px(tb.centres)
        gc = np.maximum.accumulate(np.maximum(np.asarray(gfun(cb, cr), float), g_start))
        tb.grad = np.clip(np.maximum(g, gc[:, None]), 0.0, 1.0)
        ab, _s, ar = to_px(tb.apex) if tb.apex is not None else (cb[-1], 0, cr[-1])
        tb.grad_apex = float(np.clip(max(gc[-1], float(gfun(ab, ar))), 0.0, 1.0))
        k = np.array([keepfun(r, a / sl) for r, a in zip(cr, tb.arc)])
        tb.attrs = {_KEEP_ATTR: np.repeat(k[:, None], tb.rings.shape[1], 1)}
        tb.attrs_apex = {_KEEP_ATTR: float(k[-1])}
        for t in tb.tips:
            tube(t, gc[-1])
    tube(st, 0.0)


def _mass_keep(row, u):
    k = KEEP_TOP + (KEEP_LOW - KEEP_TOP) * smooth01((row - KEEP_ROWS[0]) / (KEEP_ROWS[1] - KEEP_ROWS[0]))
    if u > 1.0:                     # the curl and the sub-tips
        k += (CURL_KEEP - k) * smooth01((u - 1.0) / 0.08)
    return k


# ---------------------------------------------------------------- outline
# The inverted hull draws a line wherever a lock's silhouette passes over
# whatever lies behind it. Where two locks run nearly flush (within about a
# line width), the hull pokes in and out of the neighbour's surface and
# prints short broken scratches over the pale mass. So each vertex's hull
# width (OUTLINE_VG) follows its STEP: how far it stands out, along the volume
# normal, over the highest surface of any OTHER loose part right beside it.
# Nothing beside it keeps the full line; a clear step draws a bolder strand
# line; a flush seam gets none. Weights are on/off (isolated vertices follow
# their neighbours): a hull thinner than a pixel prints a faint grey hairline.
OUTLINE_VG = 'outline_width'
STRAND_LINE = 1.6           # strand lines x the silhouette width (a solid stroke)
STEP_PX = 8.0               # step (px) over the neighbour that draws a strand line
STEP_REACH = 14.0           # px searched around a vertex for neighbouring surfaces
STEP_TANGENT = 10.0         # ... of which at most this far off along the surface


def outline_weights(meshes, vols):
    """Hull width per vertex (0, 1 / STRAND_LINE or 1) from its step over the
    other loose parts, for meshes = [(mesh, part id per vertex)] seen together;
    returns one weight list per mesh."""
    from mathutils.bvhtree import BVHTree
    co, part, vol, polys, nbr = [], [], [], [], []
    for (me, pid), vl in zip(meshes, vols):
        base = len(co)
        co += [v.co.copy() for v in me.vertices]
        part += pid
        vol += vl
        polys += [tuple(base + i for i in p.vertices) for p in me.polygons]
        nbr += [[] for _ in me.vertices]
        for e in me.edges:
            a, b = (base + i for i in e.vertices)
            nbr[a].append(b)
            nbr[b].append(a)
    tree = BVHTree.FromPolygons(co, polys)
    fpart = [part[p[0]] for p in polys]
    reach, tan = STEP_REACH / PX, STEP_TANGENT / PX
    raw = []
    for i in range(len(co)):
        nv = vol[i]
        top = None
        for loc, fn, f, _d in tree.find_nearest_range(co[i], reach):
            if fpart[f] == part[i] or fn.dot(nv) < 0.2:
                continue            # own lock, or a body-side face
            dv = loc - co[i]
            h = dv.dot(nv)
            if (dv - nv * h).length > tan:
                continue
            top = h if top is None else max(top, h)
        if top is None:
            raw.append(1.0 / STRAND_LINE)       # the mass's own edge
        elif -top * PX >= STEP_PX:
            raw.append(1.0)                     # a strand line over a neighbour
        else:
            raw.append(0.0)                     # a flush seam
    # majority filter along the edges: a lone vertex follows its neighbours
    out = []
    for i, w in enumerate(raw):
        ws = [raw[j] for j in nbr[i]]
        if ws and sum(1 for x in ws if x == w) * 2 < len(ws):
            w = max(set(ws), key=ws.count)
        out.append(w)
    res, k = [], 0
    for me, _pid in meshes:
        res.append(out[k:k + len(me.vertices)])
        k += len(me.vertices)
    return res


# ---------------------------------------------------------------- build
# Three objects. The locks of the mass ('hair_back') do not cast sun shadows: at the
# low key light every lock edge printed a hard 1 px shadow copy of itself onto the
# lock beside it. The under-layer ('hair_back_shell') casts for the whole mass
# instead, so the hair still shadows the dress and back behind it. The curled
# primaries and the outer side locks ('hair_back_side') do cast: their curls shadow
# the skirt below them and the side locks the sleeves, as on the sheet.
def build_strands():
    """All back-hair strands, in build (layer) order: [(object, strand, kind, info)] and
    the under-layer grids."""
    cap = _cap_proxy()
    outer, inner = _under_layer()
    under = _Surface(_shell_tris(outer, inner), 'under')
    built = []
    lowers = [cap, under]
    # the wave and crescent side locks grow from the side of the head below the crown,
    # under the mass's outer locks (the crescent behind the wave); the shoulder flick
    # lies over them all on top of the shoulder
    def side(d):
        for sd in (1, -1):
            st, info = _settle(side_lock_kwargs(d, sd), lowers)
            built.append(('hair_back_side', st, ('side', d), info))
            lowers.append(st)
    side(OUTER[1])
    side(OUTER[2])
    defs = prim_defs()
    for layer in (0, 1):
        for d in (d for d in defs if d['layer'] == layer):
            st, info = _settle(mass_lock_kwargs(d), lowers)
            built.append(('hair_back_side' if d['curled'] else 'hair_back', st, 'mass', info))
            lowers.append(st)
    side(OUTER[0])
    return built, (outer, inner)


# The rig's lock test (rig._hair_locks, HAIR_LOCK_LEN / HAIR_LOCK_SPAN / 24 vertices),
# repeated here so a build that would change the rig's lock / sector split fails loudly.
LOCK_LEN = 0.2
LOCK_SPAN = 70.0
UNDER_SPAN_MIN = 76.0       # the under-layer keeps this margin over LOCK_SPAN (a sector island)


def _island_test(p):
    """(length below eye level m, span deg round the skull) of a loose part's points."""
    ang = np.degrees(np.arctan2(p[:, 0], p[:, 1] - spec.L['head_center_y']))
    c = math.degrees(math.atan2(float(np.sin(np.radians(ang)).mean()), float(np.cos(np.radians(ang)).mean())))
    dev = (ang - c + 180.0) % 360.0 - 180.0
    span = float(np.percentile(dev, 95) - np.percentile(dev, 5))
    return min(spec.L['eye_z'], float(p[:, 2].max())) - float(p[:, 2].min()), span


def _check_islands(outer, inner, built):
    """Every primary and outer lock passes the rig's lock test (its own chain, weighted
    along it: a lock never blends sector chains with the head bone, whose 4-bone pruning
    tore the round-10-style short flick in a head turn); the under-layer fails it with a
    margin (the sector chains)."""
    errs = []
    _ln, span = _island_test(np.concatenate([outer.reshape(-1, 3), inner.reshape(-1, 3)]))
    print(f'HAIR_BACK {len(built)} strands, under-layer {span:.0f} deg round the head, largest lift '
          f'{1000 * max(i.get("lift_max", 0.0) for _o, _s, _k, i in built):.0f} mm, skirt shortfall '
          f'{max(i.get("skirt_short_px", 0.0) for _o, _s, _k, i in built):.1f} px')
    if span < UNDER_SPAN_MIN:
        errs.append(f'the under-layer spans {span:.0f} deg round the head (< {UNDER_SPAN_MIN:.0f}): it would '
                    'be rigged as a lock')
    for _obj, st, kind, _info in built:
        p = np.concatenate([tb.rings.reshape(-1, 3) for tb in st.all_tubes()])
        ln, span = _island_test(p)
        if ln < LOCK_LEN or span >= LOCK_SPAN or len(p) < 24:
            errs.append(f'{st.name}: {ln:.2f} m below eye level, {span:.0f} deg round the head: not a lock')
    if errs:
        raise ValueError('hair_back islands break the rig contract:\n  ' + '\n  '.join(errs))


def build(col):
    mat = common.toon_material('hair', gradient='hair_tip')
    built, (outer, inner) = build_strands()
    names = ('hair_back_shell', 'hair_back', 'hair_back_side')
    bms = {}
    for nm in names:
        bm = bmesh.new()
        bm.verts.layers.float.new(common.GRAD_ATTR)
        bm.verts.layers.float.new(_KEEP_ATTR)
        bms[nm] = [bm, []]          # bmesh, loose part id per vertex
    pid = 0
    _emit_grid_shell(bms['hair_back_shell'][0], outer, inner, grad_global, VOL_KEEP)
    bms['hair_back_shell'][1] += [pid] * len(bms['hair_back_shell'][0].verts)
    _check_islands(outer, inner, built)
    for obj_name, st, kind, info in built:
        pid += 1
        if kind == 'mass':
            _paint(st, grad_global, _mass_keep)
        else:
            gr = kind[1]['gr']
            _paint(st, lambda bx, row, gr=gr: hk.smooth01((np.asarray(row) - gr[0]) / (gr[1] - gr[0])),
                   lambda row, u: SIDE_KEEP if u <= 1.0 else CURL_KEEP)
        bm, part = bms[obj_name]
        n0 = len(bm.verts)
        hk.emit(bm, st)
        part += [pid] * (len(bm.verts) - n0)
        if RECORD is not None:
            v = hk.validate(st, raise_=False)
            RECORD.append((obj_name, st, dict(info, **{k: v[k] for k in ('max_turn', 'max_rho', 'folds', 'max_twist',
                                                                          'max_gap', 'faces', 'rings')})))
    objs = []
    for nm, cast in zip(names, (True, False, True)):
        bm, part = bms[nm]
        obj = common.new_object(col, nm, bm, [mat])
        common.shade_smooth(obj, angle_deg=70.0)
        obj['levi_cast_shadow'] = cast
        objs.append((obj, part))
    vols = [[volume_normal(v.co) for v in o.data.vertices] for o, _p in objs]
    weights = outline_weights([(o.data, p) for o, p in objs], vols)
    for (obj, _p), vol, ws in zip(objs, vols, weights):
        me = obj.data
        keep = [a.value for a in me.attributes[_KEEP_ATTR].data]
        me.attributes.remove(me.attributes[_KEEP_ATTR])
        set_volume_normals(me, keep, vol)
        vg = obj.vertex_groups.new(name=OUTLINE_VG)
        for i, w in enumerate(ws):
            vg.add([i], w, 'REPLACE')
        common.add_outline(obj, width=spec.OUTLINE_WIDTH * STRAND_LINE, vertex_group=OUTLINE_VG,
                           min_factor=0.0)
    return objs[1][0]
