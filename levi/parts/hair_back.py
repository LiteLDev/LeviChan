"""Long back hair: white -> green wavy locks from under the crown to the skirt.

Built from scratch as swept locks: every lock is a Catmull-Rom spine carrying
a lens cross-section - a convex outer face, a flatter inner face and soft
edges - that tapers in width and thickness into a rounded point. A few broad
primary masses (ring 12) make up the back, smaller locks overlap and break
their edges, and every lock waves root to tip sideways and through depth.
Locks are authored in reference panel pixels so they can be fitted directly
against ref/back.png and ref/side.png:

    bx  : column in the BACK view   (image-left = character's left = +X)
    sx  : column in the SIDE view   (image-right = behind her = +Y)
    row : row shared by all panels  (z = (951 - row) / 643)

Control points can be written as
    ('s', azimuth_deg, polar_deg)        a scalp point: its back-view column
                                         and row come from the skull ellipsoid
                                         (azimuth 0 = straight back, +90 =
                                         character's left), its depth from the
                                         hair envelope
    (bx, row)                            on the hair envelope (env_sx)
    (bx, sx, row)                        explicit.

One envelope. Every scalp and mass point of every lock lies on ONE smooth
surface (env_sx): a few px over hair_front's scalp cap above the nape (its
CAP_PROFILE data), blending into a family of hanging superelliptic sections
below it, whose back follows the sheet's side silhouette (MASS_BACK). A lock's
own layer offset ('lay') fades in from zero over its first LAY_FADE px, and
its root starts ROOT_SINK px inside the envelope (buried under the cap), so
the locks grow out of one scalp volume instead of starting as stacked shells.

A lock may end in a curl (hook()): the bend eases in from above the curl,
tightens towards the tip and climbs along its axis like a loose ringlet;
curls drawn in the back view's image plane are tilted out of it so they turn
through depth, and the section rolls over gradually through the curl.

Colour: toon_material('hair', gradient='hair_tip'); 'toon_grad' is ONE
smooth function of the position (grad_global) shared by every lock and the
backing curtain, so the white-to-mint fade runs coherently across the mass;
it is made monotonic along each spine so curls that turn back up stay green.
Only the outer side locks, which the sheet tips green higher up, keep their
own ranges ('gr').

The scalp cap, bangs and face-framing side locks belong to hair_front (this
part reads its CAP_PROFILE/CAP_EXP measurement data only). A backing curtain
under the locks keeps the mass solid from the crown to the hips. The locks
hang roughly vertically so the rig's back-hair sector chains follow them.
"""
import math

import bmesh
from mathutils import Vector

from .. import common, spec
from .hair_front import CAP_EXP, CAP_PROFILE   # measurement data only (see docstring)

PX = spec.PX_PER_M
CX = spec.PANEL_W / 2

# Skull ellipsoid in panel px (back view hair is +-74 px wide at row 100, side
# view back of head at sx 367). Centre depth follows spec.L['head_center_y'].
# Used for scalp point positions (bx, row) and the hair's volume normals.
SKULL_C = (0.0, spec.L['head_center_y'] * spec.PX_PER_M, 108.0)   # (X px, Y px, row)
SKULL_R = (72.0, 82.0, 86.0)         # (rx, ry, rz) px
SCALP_LIFT = 0.95

RING = 8            # vertices per cross-section (default; primaries use 12)
DENSE_PX = 3.0      # spine sampling before the adaptive resample (panel px)
SEG_PX = 20.0       # ring spacing on straight runs (panel px) ...
SEG_TURN = 12.0     # ... or sooner, once the spine has turned this many degrees
CURL_SEG = 14.0     # ring spacing inside a curl (panel px) ...
CURL_TURN = 12.0    # ... or this many degrees
TH = 0.45           # outer half thickness / half width of a lock's lens section
LENS_INNER = 0.65   # inner (body-side) bulge relative to the outer one
TIP_PX = 44.0       # length over which a lock without a curl rounds into its point
WAVE_ROWS = (175.0, 260.0)   # rows over which the root-to-tip waves fade in
# Roots: every lock starts ROOT_SINK px under the envelope and rises onto it
# over ROOT_LEN px of spine; its own layer offset fades in over LAY_FADE px
# (~8 cm) and its width grows from ROOT_W over the first ROOT_LEN px.
ROOT_SINK = 6.0
ROOT_LEN = 40.0
LAY_FADE = 55.0
ROOT_W = 0.55
TUCK_PX = 6.0       # px an un-curled lock end sinks under the mass ...
TUCK_LEN = 60.0     # ... over this many px of spine
# Curls (see hook()):
CURL_TILT = 30.0    # deg a back-view curl is tilted out of the image plane
CURL_EASE = 1.5     # start radius / radius: the bend eases in from above
CURL_SHRINK = 0.2   # the radius tightens by this share towards the tip
CURL_PITCH = 0.25   # rise along the curl axis over the curl, x radius
CURL_TWIST = 45.0   # default section twist through a curl (deg) ...
CURL_ROLL = 0.85    # ... spread over this share of the curl
CURL_TAPER = 1.6    # width taper exponent through a curl (1 = linear to the tip)
TOP_ROWS = (150.0, 300.0)    # rows over which the crown's flatter, wider locks gain volume
TOP_WIDE = 1.3      # lock width factor at the crown
TOP_FLAT = 0.7      # lock thickness factor at the crown
CURL_TH = 0.5       # thickness ratio the section rounds to through a curl
TIP_TH = 0.55       # ... and at the point of a lock without a curl
CURL_KEEP = 0.8     # own-normal share at a curl tip (it shades as its own form)
LOW_KEEP = 0.62     # ... and where a lock is fully green

# Back of the hair envelope on the centre line per row (side-view column),
# from the back edge of the hair in ref/side.png minus the clump thickness.
MASS_BACK = [(110, 364), (140, 362), (170, 365), (200, 372), (230, 382), (260, 398),
             (290, 420), (320, 432), (350, 428), (380, 414), (420, 402), (520, 400)]
# Hanging sections below the cap: row -> (half width rx, depth ry, superellipse
# exponent). At the top they continue the cap's rounded back; lower down they
# widen and flatten over the shoulders and back.
SECT = [(116, 68, 60, 2.3), (140, 74, 66, 2.3), (175, 84, 62, 2.2), (210, 96, 56, 2.1),
        (260, 112, 52, 2.0), (320, 122, 50, 2.0)]
ENV_OFF = 3.0             # px the envelope sits over hair_front's cap
ENV_BLEND = (100.0, 132.0)  # rows over which the cap hands over to the hanging sections
# Skirt back surface (measured on a hair-less render of the full model):
# row -> (centre column, half depth); the half width is SKIRT_AR x the depth.
SKIRT = [(370, 300, 60), (400, 298, 86), (440, 306, 105), (470, 313, 120),
         (500, 318, 142), (530, 320, 160)]
SKIRT_AR = 1.5
SKIRT_GAP = 3.5     # px kept between the skirt and a lock's inner face
SKIRT_BLEND = 24.0  # px of spine over which a skirt push is blended
HOOK_LAY = 2.0      # px a back-view curl sits at least above its lock's layer

# White-to-mint fade shared by the whole mass: it starts at row G0 (the left
# lobe a little lower than the right, as on the sheet) and is full G_SPAN rows on.
G0 = ((250.0, 370.0), (360.0, 352.0))     # (bx, start row) at the two sides
G_SPAN = 110.0
G_RIPPLE = 9.0      # rows


def P(bx, sx, row):
    """Panel pixels (back-view column, side-view column, row) -> world Vector."""
    return Vector((spec.px_to_h(CX - bx), spec.px_to_h(sx - CX), spec.px_to_z(row)))


def to_px(v):
    """World Vector -> (bx, sx, row) panel pixels."""
    return CX - v.x * PX, CX + v.y * PX, spec.SHEET_GROUND_Y - v.z * PX


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
    if b >= 1.0:
        return sect
    # piecewise-linear like hair_front's own cap loft, so ENV_OFF holds exactly
    w, f, bk = table(CAP_PROFILE, row)
    cap = (f + bk) / 2 + _se_back(dx, w + ENV_OFF, (bk - f) / 2 + ENV_OFF, CAP_EXP)
    return cap + (sect - cap) * b


def skirt_sx(bx, row):
    """Side-view column of the skirt's back surface at back-view column bx
    (None above or beside the skirt)."""
    if row < SKIRT[0][0]:
        return None
    c, b = table(SKIRT, row)
    u = abs(bx - CX) / (SKIRT_AR * b)
    if u >= 1.0:
        return None
    return c + b * math.sqrt(1.0 - u * u)


def mass_sx(bx, row, lay=0.0):
    """Depth of the hair mass's back surface at back-view (bx, row)."""
    sx = env_sx(bx, row) + lay
    sk = skirt_sx(bx, row)
    if sk is not None:
        sx = max(sx, sk + SKIRT_GAP + max(lay, 0.0))
    return sx


def clear_skirt(p, gap=SKIRT_GAP):
    """Push a world point back (+Y) until it clears the skirt."""
    bx, sx, row = to_px(p)
    sk = skirt_sx(bx, row)
    if sk is not None and sx < sk + gap:
        p = P(bx, sk + gap, row)
    return p


def grad_global(bx, row):
    """Shared white (0) -> mint (1) fade of the back mass."""
    (b0, r0), (b1, r1) = G0
    g0 = r0 + (r1 - r0) * smooth01((bx - b0) / (b1 - b0))
    # a slow ripple across the back: neighbouring locks start their fade at
    # slightly different heights, but as one smooth field, not per lock
    g0 += G_RIPPLE * math.sin((bx - CX) / 34.0)
    return smooth01((row - g0) / G_SPAN)


def _pt(p):
    if p[0] == 's':
        bx, _, row = to_px(skull(p[1], p[2]))
        return P(bx, env_sx(bx, row), row)
    if len(p) == 2:
        return P(p[0], mass_sx(p[0], p[1]), p[1])
    return P(*p)


def catmull(pts, step_px):
    """Uniform Catmull-Rom through pts, sampled densely (~step_px panel px).

    Returns the samples (including both ends) and each sample's control
    parameter (span index + fraction) for interpolating per-control values.
    """
    ext = [pts[0] * 2 - pts[1]] + pts + [pts[-1] * 2 - pts[-2]]
    out, par = [], []
    for i in range(len(pts) - 1):
        p0, p1, p2, p3 = ext[i:i + 4]
        samples = max(1, math.ceil((p2 - p1).length * PX / step_px))
        for k in range(samples):
            t = k / samples
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
            par.append(i + t)
    out.append(pts[-1].copy())
    par.append(len(pts) - 1)
    return out, par


def lerp_list(vals, u):
    """Piecewise-linear lookup of vals at control parameter u."""
    i = min(int(u), len(vals) - 2)
    f = u - i
    return vals[i] * (1 - f) + vals[i + 1] * f


def smooth_list(vals, u):
    """Monotone cubic (Fritsch-Carlson) lookup of scalar vals at control
    parameter u: continuous slope, so widths swell and taper without kinks,
    and never overshooting, so a steep taper cannot dip below its end value."""
    n = len(vals)
    i = min(int(u), n - 2)
    f = u - i

    def tangent(k):
        if k <= 0:
            return vals[1] - vals[0]
        if k >= n - 1:
            return vals[-1] - vals[-2]
        a, b = vals[k] - vals[k - 1], vals[k + 1] - vals[k]
        if a * b <= 0.0:
            return 0.0
        return 2.0 * a * b / (a + b)      # harmonic mean: keeps the cubic monotone

    p1, p2 = vals[i], vals[i + 1]
    m1, m2 = tangent(i), tangent(i + 1)
    f2, f3 = f * f, f * f * f
    return ((2 * f3 - 3 * f2 + 1) * p1 + (f3 - 2 * f2 + f) * m1
            + (-2 * f3 + 3 * f2) * p2 + (f3 - f2) * m2)


def _radial(p):
    """Away from the body axis (slightly behind the spine)."""
    v = Vector((p.x, p.y + 0.02, 0.0))
    return v.normalized() if v.length > 1e-6 else Vector((0, 1, 0))


def _arclen(pos):
    acc = [0.0]
    for a, b in zip(pos, pos[1:]):
        acc.append(acc[-1] + (b - a).length * PX)
    return acc


def _wave(spine, d, on_mass):
    """Root-to-tip S-wave on the dense spine (in place).

    d['wave'] = (amp_px, wavelength_rows, phase_deg, depth_px): a sideways
    (back-view) sine of amp_px plus a depth sine a quarter period out of
    phase, so the lock undulates through depth as well as across the back.
    It fades in below the shoulders (WAVE_ROWS) and eases to 40 % over the last
    60 rows, so the fitted ends and curls move by a few px at most.
    Points on the mass re-follow its surface after the sideways shift.
    """
    amp, lam, ph, dep = d['wave']
    r_end = to_px(spine[-1])[2]
    snap_row = min((p[1] for p in d['pts'] if p[0] != 's' and len(p) == 2), default=1e9)
    for i, p in enumerate(spine):
        bx, sx, row = to_px(p)
        env = smooth01((row - WAVE_ROWS[0]) / (WAVE_ROWS[1] - WAVE_ROWS[0]))
        env *= 1.0 - 0.6 * smooth01((row - (r_end - 60.0)) / 60.0)
        if env <= 0.0:
            continue
        a = 2 * math.pi * row / lam + math.radians(ph)
        bx += amp * env * math.sin(a)
        if on_mass and row >= snap_row:
            sx = mass_sx(bx, row)
        sx += dep * env * math.cos(a)
        spine[i] = P(bx, sx, row)


def _layer(spine, lay, sink, tuck):
    """Offset the dense spine along the volume normal (in place): -sink px at
    the root rising to 0 over ROOT_LEN, plus the lock's own layer offset
    faded in over LAY_FADE - so every lock leaves the scalp on the shared
    envelope and separates into its own layer only further down. With tuck,
    the offset eases to -TUCK_PX over the last TUCK_LEN px, so a lock that
    ends without a curl slips under its neighbours instead of ending as a
    tongue on top of them."""
    acc = _arclen(spine)
    tot = acc[-1]
    for i, p in enumerate(spine):
        s = acc[i]
        off = lay * smooth01(s / LAY_FADE) - sink * (1.0 - smooth01(s / ROOT_LEN))
        if tuck:
            t = smooth01((s - (tot - TUCK_LEN)) / TUCK_LEN)
            off += (-TUCK_PX - off) * t
        if off:
            spine[i] = p + volume_normal(p) * (off / PX)


def _clear_rings(rings, centres):
    """Section-aware skirt clearance (in place): push each ring back (+Y) until
    every one of its vertices clears the skirt by SKIRT_GAP, blending each
    push over SKIRT_BLEND px of spine so the lock bends round the skirt
    instead of kinking."""
    push = []
    for ring in rings:
        m = 0.0
        for co in ring:
            bx, sx, row = to_px(co)
            sk = skirt_sx(bx, row)
            if sk is not None:
                m = max(m, sk + SKIRT_GAP - sx)
        push.append(m)
    if not any(push):
        return
    acc = _arclen(centres)
    n = len(rings)
    for i in range(n):
        m = push[i]
        for j in range(n):
            dist = abs(acc[i] - acc[j])
            if j != i and dist < SKIRT_BLEND:
                m = max(m, push[j] * (1.0 - dist / SKIRT_BLEND))
        if m > 0.0:
            off = Vector((0.0, m / PX, 0.0))
            rings[i] = [co + off for co in rings[i]]


def hook(p0, d0, curl, opts, on_mass):
    """Dense points of a rounded curl that continues the spine from p0, d0.

    curl = (radius_px, turn_deg, (img_x, depth)): the spine turns by
    turn_deg towards the horizontal direction img_x * (back-view image right)
    + depth * (+Y, behind her). Curls drawn in the back-view image plane
    (depth == 0) are tilted CURL_TILT deg out of it (tip swinging away from
    the body) so they turn through depth instead of lying flat on the mass.
    The bend eases in (radius CURL_EASE times larger at the start, so the
    curve begins above the hook), tightens by CURL_SHRINK towards the tip, and
    climbs CURL_PITCH x radius along the curl axis like a loose ringlet so
    the tip clears its own lock.
    Returns [(point, u)] with u = 0..1 along the curl, and the curl axis.
    """
    R, turn, (ix, iy) = curl
    tilt = math.radians(opts.get('tilt', CURL_TILT))
    d = d0.normalized()
    if iy == 0:
        e = Vector((-ix, 0.0, 0.0)) * math.cos(tilt) + Vector((0.0, 1.0, 0.0)) * math.sin(tilt)
        # enlarge a little so the curl's foreshortened back-view width stays close
        # to the fitted one (its height grows by the same factor)
        R = R / max(0.6, math.cos(tilt) ** 0.5)
    else:
        e = Vector((-ix, iy, 0.0))
    e = (e - d * e.dot(d)).normalized()
    axis = d.cross(e).normalized()
    if axis.dot(_radial(p0)) < 0:
        axis.negate()
    T = math.radians(turn)
    ease = opts.get('ease', CURL_EASE)
    pitch = opts.get('pitch', CURL_PITCH) * R / PX
    n = max(12, round(turn / 3.0))
    out = []
    p = p0.copy()
    # depth the spine end already sits over the mass: the curl keeps at least
    # that, growing by HOOK_LAY over its first third (no step in depth)
    bx0, sx0, row0 = to_px(p0)
    base = sx0 - env_sx(bx0, row0)
    for k in range(n):
        th = T * (k + 0.5) / n
        f = th / T
        r = R * (1.0 - CURL_SHRINK * f) * (1.0 + (ease - 1.0) * (1.0 - smooth01(f / 0.45))) / PX
        p = p + (d * math.cos(th) + e * math.sin(th)) * (r * T / n) + axis * (pitch / n)
        if on_mass and iy == 0:
            bx, sx, row = to_px(p)
            lift = base + HOOK_LAY * smooth01(3.0 * (k + 1) / n)
            p = P(bx, max(sx, mass_sx(bx, row, lift)), row)
        out.append((clear_skirt(p), (k + 1) / n))
    return out, axis


def _resample(n, pos, seg_px, turn_deg, curl_from):
    """Indices of the dense samples kept as rings: a new ring every seg_px panel px
    on straight runs, or sooner once the spine has turned by turn_deg (CURL_SEG /
    CURL_TURN from sample curl_from on, so curls stay round)."""
    keep = [0]
    acc_l = acc_a = 0.0
    for i in range(1, n - 1):
        acc_l += (pos[i] - pos[i - 1]).length * PX
        t0 = pos[i] - pos[i - 1]
        t1 = pos[i + 1] - pos[i]
        if t0.length > 1e-9 and t1.length > 1e-9:
            acc_a += math.degrees(t0.angle(t1, 0.0))
        curl = i >= curl_from
        if acc_l >= (min(seg_px, CURL_SEG) if curl else seg_px) or acc_a >= (CURL_TURN if curl else turn_deg):
            keep.append(i)
            acc_l = acc_a = 0.0
    if n - 1 - keep[-1] < 2 and len(keep) > 1:
        keep.pop()          # avoid a sliver ring right before the tip
    keep.append(n - 1)
    return keep


def clump(bm, layer, d):
    """Add one hair lock to bm; returns its shading normals (see set_volume_normals).

    d: pts (control points), w (width px, one per point), th (outer half
    thickness as a ratio of the half width), lay (layer offset px, faded in
    from the root), n ('radial' or a fixed normal-hint tuple: the lock's
    outer face), tw (cross-section twist deg about the spine, scalar or one
    per point), wave (see _wave), curl (optional, see hook()) with tip (tip
    width px) and ctw (twist through the curl, deg), gr (optional own fade
    rows; default: grad_global), ring (verts per section), keep (own-normal
    share), seg (ring spacing px).

    The cross-section is a lens with a convex outer face and a flatter inner
    one (LENS_INNER): rounded in the middle, thinning to soft edges. Width and
    thickness both taper into the tip, which turns rounder (CURL_TH) so the
    points read as soft, not cut from card.
    """
    lay = d.get('lay', 0.0)
    ctrl = [_pt(p) for p in d['pts']]
    w = list(d['w'])
    assert len(w) == len(ctrl), 'one width per control point'
    nctl = len(ctrl)
    n = d.get('n', 'radial')
    hints = [Vector(n).normalized() if isinstance(n, tuple) else _radial(c) for c in ctrl]
    tw = d.get('tw', 0.0)
    tw = list(tw) if isinstance(tw, (list, tuple)) else [tw] * nctl
    th = d.get('th', TH)
    keep0 = d.get('keep', VOL_KEEP)
    on_mass = len(d['pts'][-1]) == 2
    rooted = d['pts'][0][0] == 's'
    gr = d.get('gr')

    def gfun(bx, row):
        if gr is None:
            return grad_global(bx, row)
        return smooth01((row - gr[0]) / (gr[1] - gr[0]))

    pos, par = catmull(ctrl, DENSE_PX)
    if 'wave' in d:
        _wave(pos, d, on_mass)
    _layer(pos, lay, ROOT_SINK if rooted else 0.0, d.get('tuck', on_mass and 'curl' not in d))
    for i, p in enumerate(pos):
        pos[i] = clear_skirt(p)
    acc = _arclen(pos)
    # per dense sample: width, thickness ratio, twist, normal hint, own-normal share
    # Near the crown the locks are wider and flatter so they merge into one
    # smooth mass; they gain their own volume as they fall (TOP_ROWS).
    attrs = []
    for p, u, s in zip(pos, par, acc):
        bx, _, row = to_px(p)
        # (back locks only: the side locks with a fixed outer face keep their size)
        f = smooth01((row - TOP_ROWS[0]) / (TOP_ROWS[1] - TOP_ROWS[0])) if n == 'radial' else 1.0
        ww = smooth_list(w, u) * (TOP_WIDE + (1.0 - TOP_WIDE) * f)
        if rooted:
            ww *= ROOT_W + (1.0 - ROOT_W) * smooth01(s / ROOT_LEN)
        attrs.append((ww, th * (TOP_FLAT + (1.0 - TOP_FLAT) * f), lerp_list(tw, u), lerp_list(hints, u),
                      keep0 + max(0.0, LOW_KEEP - keep0) * gfun(bx, row)))
    tip_w = d.get('tip', 2.0)
    curl_from = len(pos)
    if 'curl' in d:
        d0 = pos[-1] - pos[-4]
        pts, axis = hook(pos[-1], d0, d['curl'], d, on_mass)
        w0, th0, tw0, h0, k0 = attrs[-1]
        ctw = d.get('ctw', CURL_TWIST)
        for p, u in pts:
            s = smooth01(u)
            # a gradual taper: about two thirds of the width half way round
            ww = tip_w + (w0 - tip_w) * (1.0 - u ** CURL_TAPER)
            hb = h0.lerp(axis, smooth01(u / 0.35))
            roll = ctw * smooth01(u / CURL_ROLL)
            attrs.append((ww, th0 + (CURL_TH - th0) * smooth01(u / 0.5), tw0 + roll, hb,
                          k0 + max(0.0, CURL_KEEP - k0) * s))
            pos.append(p)
    else:
        # taper the last stretch into a rounder soft point
        tot = acc[-1]
        for i in range(len(pos)):
            u = smooth01((acc[i] - (tot - TIP_PX)) / TIP_PX)
            ww, tt, *rest = attrs[i]
            attrs[i] = (ww, tt + (TIP_TH - tt) * u, *rest)
    idx = _resample(len(pos), pos, d.get('seg', SEG_PX), SEG_TURN, curl_from)
    nr = d.get('ring', RING)
    rings = []
    prev_side = None
    gmax = 0.0
    ns = len(idx)
    for j, i in enumerate(idx):
        p = pos[i]
        t = (pos[idx[min(j + 1, ns - 1)]] - pos[idx[max(j - 1, 0)]]).normalized()
        ww, tr, twi, nh, kk = attrs[i]
        nrm = nh - t * nh.dot(t)
        if nrm.length < 1e-4:
            nrm = prev_side.cross(t) if prev_side is not None else t.orthogonal()
        nrm.normalize()
        side = t.cross(nrm).normalized()
        if prev_side is not None and side.dot(prev_side) < 0:
            side.negate()       # keep the frame from flipping between rings
            nrm.negate()
        prev_side = side
        side, nrm = _twist(side, nrm, twi)
        hw = ww / PX / 2
        ht = tr * ww / PX / 2
        if j == ns - 1:  # soft but non-degenerate tip
            hw, ht = max(hw * 0.5, 0.5 / PX), max(ht * 0.5, 0.35 / PX)
        ring, own = [], []
        for k in range(nr):
            a = 2 * math.pi * k / nr
            ca, sa = math.cos(a), math.sin(a)
            hy = ht * (1.0 if sa > 0 else LENS_INNER)
            ring.append(p + side * (hw * ca) + nrm * (hy * sa))
            own.append((side * (ca / hw) + nrm * (sa / hy)).normalized())   # lens normal
        bx, _, row = to_px(p)
        gmax = max(gmax, gfun(bx, row))
        rings.append((ring, gmax, kk, own))
    # the whole section, not just the spine, clears the skirt
    geo = [r[0] for r in rings]
    _clear_rings(geo, [pos[i] for i in idx])
    rings = [(g, *r[1:]) for g, r in zip(geo, rings)]
    shading = {}
    verts = []
    for ring, g, kk, own in rings:
        # mesh vertex indices follow creation order
        shading.update((len(bm.verts) + k, (kk, own[k])) for k in range(nr))
        vs = []
        for co in ring:
            v = bm.verts.new(co)
            bx, _, row = to_px(co)
            v[layer] = max(g, gfun(bx, row))
            vs.append(v)
        verts.append(vs)
    for a, b in zip(verts, verts[1:]):
        for k in range(nr):
            k2 = (k + 1) % nr
            bm.faces.new((a[k], a[k2], b[k2], b[k]))
    bm.faces.new(list(reversed(verts[0])))
    bm.faces.new(verts[-1])
    return shading


def _twist(side, nrm, deg):
    """Rotate a section frame (side, nrm) by deg about the spine."""
    if not deg:
        return side, nrm
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return side * c + nrm * s, nrm * c - side * s


def mirror(d):
    """Mirror a lock definition across the character's midline."""
    e = dict(d)
    pts = []
    for p in d['pts']:
        if p[0] == 's':
            pts.append(('s', -p[1]) + tuple(p[2:]))
        else:
            pts.append((2 * CX - p[0],) + tuple(p[1:]))
    e['pts'] = pts
    if isinstance(d.get('n'), tuple):
        x, y, z = d['n']
        e['n'] = (-x, y, z)
    if 'curl' in d:
        R, turn, (ix, iy) = d['curl']
        e['curl'] = (R, turn, (-ix, iy))
    for k in ('tw', 'ctw'):
        if k in d:
            v = d[k]
            e[k] = [-x for x in v] if isinstance(v, (list, tuple)) else -v
    if 'wave' in d:
        amp, lam, ph, dep = d['wave']
        e['wave'] = (-amp, lam, ph, dep)
    return e


# ------------------------------------------------------------------ locks
# Targets measured on the reference (panel px):
#   back view, main mass edges: r150 252/387, r200 256/385 (bare shoulder
#     skin at bx 233-250 between the mass and the shoulder lock), r250 251/391,
#     r300 231/410, r320 219/418, r350-400 ~212/422.  Lower third: two lobes
#     split at bx ~305; left lobe ends in a big C hook (outer edge 220 at
#     row 450, bottom (262, 495), tip (302, 460)); right lobe: an S lock that
#     hooks at the right edge (417, 402), a curl bottoming at (365, 510) with
#     its tip back at (335, 492), and an outer curl out to (437, 460) with
#     its tip at (400, 492).  Green starts ~row 375 (right) / 395 (left).
#   side view, back edge (sx): r150 367, r200 392, r230 424 (shoulder flick),
#     r250 397, r300 439, r330 450, r360 424 with the open curl 450-468 at
#     rows 368-405 and the lower curl to 466 at rows 410-460.
#   front/back view hooks past the sleeves: outer edge bx 61-66 at rows
#     370-410, tip at (84, 347).

# Primary masses (ring 12): broad, full locks that make up most of the back -
# A/B the left lobe, D/F the right one - each with its own root-to-tip wave.
# Secondary locks sit between and over them and break their edges; the
# waves of neighbours are out of phase so the outlines cross like the sheet's.
MAIN = [
    # A (primary): left edge -> big C curl at the bottom left
    dict(pts=[('s', 60, 30), ('s', 62, 62), ('s', 62, 92), (258, 150),
              (252, 195), (246, 240), (236, 285), (224, 325), (216, 365), (215, 400),
              (220, 430), (232, 452)],
         w=[18, 24, 28, 32, 38, 44, 50, 54, 52, 48, 42, 36], ring=12, th=0.5,
         wave=(8, 160, 0, 6), curl=(38, 195, (1, 0)), tilt=14, tip=4.0, ctw=35, seg=20),
    # B (primary): left inner; ends higher, tapering out behind the C curl
    dict(pts=[('s', 40, 26), ('s', 42, 62), ('s', 41, 94), (280, 150),
              (274, 195), (268, 240), (258, 290), (250, 335), (256, 372), (268, 400),
              (280, 422)],
         w=[18, 24, 28, 32, 38, 46, 52, 56, 54, 44, 24], ring=10, th=0.5,
         wave=(8, 150, 140, 6), lay=2, seg=20),
    # C: along the central parting, under its neighbours; ends above the
    # lobes' split so the two lobes separate at the bottom
    dict(pts=[('s', 18, 22), ('s', 21, 62), ('s', 20, 95), (302, 150),
              (299, 195), (296, 240), (293, 290), (291, 330), (294, 368), (300, 400),
              (303, 430)],
         w=[16, 20, 24, 28, 32, 36, 40, 42, 38, 28, 8],
         wave=(5, 140, 260, 4), lay=-2, ring=10),
    # D (primary): right of the parting -> curl at the bottom (365, 510)
    dict(pts=[('s', -2, 22), ('s', -2, 62), ('s', -2, 95), (322, 150),
              (326, 195), (330, 240), (336, 290), (334, 330), (330, 368), (336, 404),
              (345, 428), (352, 448)],
         w=[18, 24, 28, 32, 38, 46, 52, 56, 54, 48, 40, 32], ring=12, th=0.5,
         wave=(8, 160, 60, 6), curl=(25, 195, (-1, 0)), tilt=10, tip=4.0, ctw=-15, lay=2, seg=20),
    # E: S lock that sweeps right and hooks at the right edge (accent)
    dict(pts=[('s', -20, 24), ('s', -21, 62), ('s', -20, 95), (342, 150),
              (348, 195), (354, 240), (362, 290), (368, 326), (382, 352), (398, 370)],
         w=[16, 20, 24, 28, 32, 36, 38, 36, 30, 22],
         wave=(5, 130, 200, 4), curl=(20, 160, (-1, 0)), tip=2.0, ctw=-30, lay=4, ring=10),
    # F (primary): right outer -> outer curl at the bottom right
    dict(pts=[('s', -40, 26), ('s', -42, 62), ('s', -41, 94), (360, 150),
              (368, 195), (378, 240), (392, 290), (406, 330), (416, 370), (420, 404),
              (424, 430), (428, 456)],
         w=[18, 24, 28, 32, 38, 44, 50, 52, 48, 42, 36, 30], ring=12, th=0.5,
         wave=(8, 160, 300, 6), curl=(28, 185, (-1, 0)), tilt=12, tip=4.0, ctw=-35, seg=20),
    # G: right edge, tucked in under F; turns inward at the tip (accent)
    dict(pts=[('s', -60, 30), ('s', -62, 62), ('s', -62, 92), (380, 150),
              (386, 195), (392, 240), (402, 290), (412, 330), (418, 370), (414, 398),
              (406, 418)],
         w=[16, 20, 24, 28, 32, 36, 38, 36, 30, 18, 5],
         wave=(5, 140, 100, 4), lay=-3, ring=10),
]

# Wave locks on top of the mass: narrower locks with stronger S-waves that
# draw the sheet's interior wave lines across the lobes and break the
# primaries' edges. They end at different heights and taper into the mass.
WAVES = [
    dict(pts=[('s', 30, 50), ('s', 30, 92), (284, 160), (276, 215), (266, 270),
              (252, 318), (244, 352), (254, 384), (270, 406)],
         w=[12, 18, 22, 24, 26, 28, 24, 14, 4], lay=4, ring=8, seg=20),
    dict(pts=[('s', -10, 50), ('s', -10, 92), (328, 160), (334, 215), (342, 270),
              (350, 315), (352, 350), (346, 384), (348, 410), (354, 428)],
         w=[12, 18, 22, 24, 26, 28, 26, 22, 14, 4],
         lay=4, ring=8, seg=20),
    dict(pts=[('s', -36, 50), ('s', -38, 92), (364, 160), (372, 215), (380, 268),
              (392, 312), (398, 350), (392, 384), (394, 404)],
         w=[12, 18, 22, 24, 26, 28, 22, 12, 4], lay=4, ring=8, seg=20),
]

# Inner sheet: closer to the back, so the side view reads as a thick mass and
# no body shows through between the back locks.
INNER_LEFT = [
    dict(pts=[('s', 30, 62), ('s', 32, 95), (272, 338, 150), (250, 340, 200),
              (236, 350, 260), (236, 360, 320), (244, 372, 380), (258, 382, 430),
              (270, 390, 458)],
         w=[22, 24, 24, 34, 42, 44, 42, 32, 4], th=0.55, ring=8, seg=34),
]

# Side-view curls: locks on the character's left (nearest the side camera),
# broad in the side view, that bulge backwards and end in the curls behind
# the skirt. Their curls turn backwards (+Y) and roll through the turn, so
# they read as round curls from the side and as part of the left lobe's curl
# group from the back. They face sideways, so they keep more of their own
# normals than the back-facing volume normal.
SWEEP = [
    # upper open curl: hole around sx 414-450, rows 375-402 (the dominant one)
    dict(pts=[('s', 30, 50), ('s', 30, 92), (282, 362, 150), (276, 378, 195),
              (268, 382, 250), (262, 416, 300), (262, 430, 335), (264, 412, 362),
              (268, 402, 386), (272, 408, 410)],
         w=[8, 12, 14, 20, 28, 34, 36, 34, 32, 30], th=0.55, n=(1, 0, 0), tw=30,
         curl=(20, 280, (-0.4, 1)), tip=3.5, ctw=35, pitch=0.7, keep=0.6, ring=8),
    # lower lock: bulges back under the upper curl and tapers out behind the
    # left lobe (a curl here knotted into the C curl of MAIN A)
    dict(pts=[('s', 12, 50), ('s', 12, 92), (306, 362, 150), (304, 378, 195),
              (300, 382, 250), (296, 418, 300), (294, 430, 335), (292, 418, 370),
              (292, 418, 400), (296, 432, 432), (302, 436, 452)],
         w=[8, 12, 14, 20, 28, 32, 30, 28, 26, 18, 4], th=0.55, n=(1, 0, 0), tw=30,
         keep=0.6, ring=8),
]

# Outer side locks (mirrored pair): broad locks that grow out of the side of
# the mass behind the ear, fall over the back of the shoulder and hang along
# the back of the sleeve, a little behind it. Seen as the green-tipped lock
# over the shoulder and the crescent curls past the sleeves in the front and
# back views. Each is a rounded, tapering lock with an S through depth (it
# leaves the mass, settles onto the sleeve and swings back out at the curl);
# the curl rolls forward round the sleeve's outer edge.
OUTER_LEFT = [
    # shoulder lock: over the back of the shoulder, its tip turning back and up
    # (the sheet's green flick at sx ~420, row ~230 in the side view)
    dict(pts=[('s', 70, 70), ('s', 72, 100), (260, 150), (244, 340, 192),
              (228, 350, 215), (214, 366, 232)],
         w=[12, 16, 22, 24, 20, 16], n=(0.3, 1, 0), th=0.75,
         curl=(10, 150, (0.3, 1)), tip=2.0, ctw=25, gr=(200, 250), ring=8),
    # wave lock: a broad lock that spreads out over the back of the upper arm
    # in two soft S lobes (the green-tipped waves beside the sleeve top in the
    # front view, out to bx ~125 at rows 270-330) and tapers to a point
    dict(pts=[('s', 66, 95), (264, 150), (246, 344, 196), (214, 350, 238),
              (184, 354, 270), (158, 358, 298), (142, 362, 320), (132, 368, 340),
              (126, 374, 358)],
         w=[14, 22, 28, 34, 38, 36, 30, 18, 4], n=(0.3, 1, 0), th=0.78,
         tw=[0, 0, 10, 20, 10, -10, -20, -10, 0],
         wave=(7, 70, 90, 3), gr=(255, 330), ring=10),
    # crescent lock: hangs behind the sleeve to the cuff, then turns out and
    # up past the sleeve as the sheet's broad crescent (outer edge bx ~62 at
    # rows 370-410, tip (84, 347)), swinging back out a little in depth
    dict(pts=[('s', 64, 100), (262, 155), (240, 346, 205), (210, 352, 252),
              (182, 358, 298), (150, 364, 340), (118, 370, 384), (100, 374, 414),
              (87, 378, 427), (75, 380, 417), (70, 378, 398), (72, 374, 378),
              (77, 370, 362), (84, 366, 352), (90, 364, 346)],
         w=[16, 26, 32, 35, 35, 33, 30, 27, 24, 20, 16, 13, 10, 7, 4], n=(0.35, 1, 0), th=0.62,
         tw=[0, 0, 10, 20, 15, 0, -15, -10, 5, 15, 22, 24, 22, 20, 20],
         gr=(300, 395), ring=10, seg=16),
]

# Backing curtain: one continuous shell under the locks so the mass reads
# solid (no body showing between locks) from the crown to the hips.  Rows
# above the skull equator wrap the back half of the skull; below, an arc
# that follows the envelope a few px inside the locks.
CURTAIN_STEP = 11   # verts per arc (outer and inner surface each)
CURTAIN_T = 7.0     # shell thickness px
CURTAIN_INSET = 5.0
CURTAIN_WRAP = 24.0  # px the arc curls forward at its side edges
# row -> half width of the curtain arc below the skull (px)
CURTAIN_HW = [(175, 62), (200, 62), (240, 64), (280, 74), (320, 84), (360, 86),
              (390, 82), (410, 60), (420, 34)]


def _curtain_rows():
    """[(row, [(X px, Y px), ...] outer->inner loop)]."""
    rows = []
    lift = 0.94
    cx, cy, cr = SKULL_C
    m = CURTAIN_STEP

    def arc(rx, ry, cyy, ang):
        A = math.radians(ang)
        out = [(rx * math.sin(-A + 2 * A * k / (m - 1)), cyy + ry * math.cos(-A + 2 * A * k / (m - 1)))
               for k in range(m)]
        inn = [((rx - CURTAIN_T) * math.sin(A - 2 * A * k / (m - 1)),
                cyy + (ry - CURTAIN_T) * math.cos(A - 2 * A * k / (m - 1))) for k in range(m)]
        return out + inn

    for r in (40, 56, 74, 92, 110):
        dz = (r - cr) / (SKULL_R[2] * lift)
        s = math.sqrt(max(0.0, 1 - dz * dz))
        rows.append((r, arc(SKULL_R[0] * lift * s, SKULL_R[1] * lift * s, cy, 92.0)))
    rows.append((130, arc(68, 70, -30, 95)))
    rows.append((150, arc(60, 60, -15, 90)))
    for r, hw in CURTAIN_HW:
        out, inn = [], []
        for k in range(m):
            a = -1.0 + 2.0 * k / (m - 1)            # -1..1 across the arc
            X = hw * math.sin(a * math.pi / 2)
            wrap = CURTAIN_WRAP * (1 - math.cos(a * math.pi / 2))
            sx = env_sx(CX - X, r) - CURTAIN_INSET - wrap
            sk = skirt_sx(CX - X, r)
            if sk is not None:          # keep the inner surface outside the skirt
                sx = max(sx, sk + CURTAIN_T + 2.0)
            Y = sx - CX
            out.append((X, Y))
            inn.append((X * (hw - CURTAIN_T) / hw, Y - CURTAIN_T))
        rows.append((r, out + inn[::-1]))
    return rows


def curtain(bm, layer):
    verts = []
    for row, loop in _curtain_rows():
        vs = []
        for X, Y in loop:
            v = bm.verts.new(Vector((spec.px_to_h(X), spec.px_to_h(Y), spec.px_to_z(row))))
            v[layer] = grad_global(CX - X, row)
            vs.append(v)
        verts.append(vs)
    n = 2 * CURTAIN_STEP
    for a, b in zip(verts, verts[1:]):
        for k in range(n):
            k2 = (k + 1) % n
            bm.faces.new((a[k], a[k2], b[k2], b[k]))
    bm.faces.new(list(reversed(verts[0])))
    bm.faces.new(verts[-1])


# ---------------------------------------------------------------- normals
# Same approach as hair_front: the custom normals are mostly the normal of one smooth
# volume (the skull ellipsoid above its centre, a vertical elliptic cylinder
# below it for the hanging mass) plus VOL_KEEP of each strand's own normal,
# so the hair reads as one lit mass with thin shade accents along the clump
# edges and no shading seam where it meets hair_front.
VOL_AXES_LOW = (110.0, 80.0)   # cylinder half axes (X, Y) px below the skull
VOL_KEEP = 0.55


def volume_normal(co):
    cx, cy, cr = SKULL_C
    dx = co.x * PX - cx
    dy = co.y * PX - cy
    dz = (cr - (spec.SHEET_GROUND_Y - co.z * PX))      # + above the skull centre
    if dz > 0:
        rx, ry, rz = SKULL_R
        n = Vector((dx / rx ** 2, dy / ry ** 2, dz / rz ** 2))
    else:
        ax, ay = VOL_AXES_LOW
        n = Vector((dx / ax ** 2, dy / ay ** 2, 0.0))
    return n.normalized() if n.length > 1e-12 else Vector((0.0, 1.0, 0.0))


def set_volume_normals(me, shading):
    """shading: {vertex index: (share of the own normal, own normal)} for the
    locks; other vertices (the curtain) keep VOL_KEEP of their mesh normal."""
    normals = []
    for v in me.vertices:
        keep, own = shading.get(v.index, (VOL_KEEP, v.normal))
        n = volume_normal(v.co) * (1 - keep) + own * keep
        normals.append(n.normalized() if n.length > 1e-9 else Vector(v.normal))
    me.normals_split_custom_set_from_vertices(normals)


def build(col):
    mat = common.toon_material('hair', gradient='hair_tip')
    defs = (INNER_LEFT + [mirror(d) for d in INNER_LEFT] + MAIN + SWEEP + WAVES
            + OUTER_LEFT + [mirror(d) for d in OUTER_LEFT])
    bm = bmesh.new()
    layer = bm.verts.layers.float.new(common.GRAD_ATTR)
    curtain(bm, layer)
    shading = {}
    for d in defs:
        shading.update(clump(bm, layer, d))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    obj = common.new_object(col, 'hair_back', bm, [mat])
    common.shade_smooth(obj, angle_deg=70.0)
    set_volume_normals(obj.data, shading)
    common.add_outline(obj)
    return obj
