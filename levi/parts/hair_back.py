"""Long back hair: white -> green wavy locks from under the crown to the skirt.

Built from scratch as swept locks: every lock is a Catmull-Rom spine carrying
a lens cross-section - a convex outer face, a flatter inner face and soft thin
edges - that tapers in width and thickness into a rounded point. A few broad
primary masses (ring 10) make up the back, smaller locks overlap and break
their edges, and every lock waves root to tip sideways and through depth.
Locks are authored in reference panel pixels so they can be fitted directly
against ref/back.png and ref/side.png:

    bx  : column in the BACK view   (image-left = character's left = +X)
    sx  : column in the SIDE view   (image-right = behind her = +Y)
    row : row shared by all panels  (z = (951 - row) / 643)

Control points can be written as
    ('s', azimuth_deg, polar_deg, lift)  on the skull ellipsoid (azimuth 0 =
                                         straight back, +90 = character's left)
    (bx, row)                            on the back surface of the hair mass:
                                         the depth comes from mass_sx(), which
                                         also keeps the hair clear of the skirt
    (bx, sx, row)                        explicit.
A lock may end in a curl (hook()): the bend eases in from well above the curl,
tightens towards the tip and climbs along its axis like a loose ringlet;
curls drawn in the back view's image plane are tilted out of it so they turn
through depth, and the section rolls over through the curl so the curl reads
as a scroll rather than a flat cut-out.

The scalp cap, bangs and face-framing side locks belong to hair_front; this
part starts just under the crown and hugs the back of the skull so the two
overlap without a gap. A backing curtain under the locks keeps the mass
solid from the crown to the hips. The locks hang roughly vertically from the
skull so the rig's back-hair sector chains follow their centrelines.

Colour: toon_material('hair', gradient='hair_tip'); the 'toon_grad'
attribute is a smooth function of the panel row per lock (its start varies
per lock), made monotonic along each spine so curls that turn back up stay
green.
"""
import math

import bmesh
from mathutils import Vector

from .. import common, spec

PX = spec.PX_PER_M
CX = spec.PANEL_W / 2

# Skull ellipsoid in panel px (re-measured on ref/back.png + ref/side.png:
# back view hair is +-74 px wide at row 100, side view back of head at sx 367,
# hair top at row ~22).  Centre depth follows spec.L['head_center_y'].
SKULL_C = (0.0, spec.L['head_center_y'] * spec.PX_PER_M, 108.0)   # (X px, Y px, row)
SKULL_R = (72.0, 82.0, 86.0)         # (rx, ry, rz) px

RING = 8            # vertices per cross-section (default; primaries use 10)
DENSE_PX = 3.0      # spine sampling before the adaptive resample (panel px)
SEG_PX = 20.0       # ring spacing on straight runs (panel px) ...
SEG_TURN = 14.0     # ... or sooner, once the spine has turned this many degrees
TH = 0.42           # outer half thickness / half width of a lock's lens section
LENS_INNER = 0.6    # inner (body-side) bulge relative to the outer one
TIP_PX = 40.0       # length over which a lock without a curl rounds into its point
WAVE_ROWS = (175.0, 260.0)   # rows over which the root-to-tip waves fade in
CURL_TURN = 9.0     # ... the same through a curl
# Curls (see hook()):
CURL_TILT = 30.0    # deg a back-view curl is tilted out of the image plane
CURL_EASE = 2.2     # start radius / radius: the bend eases in from well above
CURL_PITCH = 0.45   # rise along the curl axis over the curl, x radius
CURL_TWIST = 80.0   # default section twist through a curl (deg) ...
CURL_ROLL = 0.4     # ... reached this far into the curl
TOP_ROWS = (150.0, 320.0)    # rows over which the crown's flat, wide locks gain volume
TOP_WIDE = 1.4      # lock width factor at the crown
TOP_FLAT = 0.55     # lock thickness factor at the crown
CURL_TH = 0.6       # thickness ratio the section rounds to at a tip
CURL_KEEP = 0.85    # own-normal share at a curl tip (it shades as its own form)
LOW_KEEP = 0.5     # ... and where a lock is fully green

# Back surface of the hair mass (side-view column on the centre line) per
# row, from the back edge of the hair in ref/side.png minus the clump
# thickness; it falls off to the sides by MASS_FALL px at 110 px off-centre.
MASS_BACK = [(140, 358), (170, 364), (200, 372), (230, 382), (260, 398), (290, 420),
             (320, 432), (350, 428), (380, 414), (420, 402), (520, 400)]
MASS_FALL = 30.0
# Skirt back surface (measured on a hair-less render of the full model):
# row -> (centre column, half depth); the half width is SKIRT_AR x the depth.
SKIRT = [(370, 300, 60), (400, 298, 86), (440, 306, 105), (470, 313, 120),
         (500, 318, 142), (530, 320, 160)]
SKIRT_AR = 1.5
SKIRT_GAP = 8.0     # px kept between the skirt and the hair spine
HOOK_LAY = 2.0      # px a back-view curl sits at least above its lock's layer


def P(bx, sx, row):
    """Panel pixels (back-view column, side-view column, row) -> world Vector."""
    return Vector((spec.px_to_h(CX - bx), spec.px_to_h(sx - CX), spec.px_to_z(row)))


def to_px(v):
    """World Vector -> (bx, sx, row) panel pixels."""
    return CX - v.x * PX, CX + v.y * PX, spec.SHEET_GROUND_Y - v.z * PX


def skull(az, pol, lift=1.0):
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
    sx = table(MASS_BACK, row)[0] - MASS_FALL * ((bx - CX) / 110.0) ** 2 + lay
    sk = skirt_sx(bx, row)
    if sk is not None:
        sx = max(sx, sk + SKIRT_GAP + max(lay, 0.0))
    return sx


def clear_skirt(p):
    """Push a world point back (+Y) until it clears the skirt."""
    bx, sx, row = to_px(p)
    sk = skirt_sx(bx, row)
    if sk is not None and sx < sk + SKIRT_GAP:
        p = P(bx, sk + SKIRT_GAP, row)
    return p


def _pt(p, lay):
    if p[0] == 's':
        return skull(*p[1:])
    if len(p) == 2:
        return P(p[0], mass_sx(p[0], p[1], lay), p[1])
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


def smooth01(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def _radial(p):
    """Away from the body axis (slightly behind the spine)."""
    v = Vector((p.x, p.y + 0.02, 0.0))
    return v.normalized() if v.length > 1e-6 else Vector((0, 1, 0))


def _wave(spine, d, on_mass, lay):
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
            sx = mass_sx(bx, row, lay)
        sx += dep * env * math.cos(a)
        spine[i] = clear_skirt(P(bx, sx, row))


def hook(p0, d0, curl, opts, on_mass, lay):
    """Dense points of a rounded curl that continues the spine from p0, d0.

    curl = (radius_px, turn_deg, (img_x, depth)): the spine turns by
    turn_deg towards the horizontal direction img_x * (back-view image right)
    + depth * (+Y, behind her). Curls drawn in the back-view image plane
    (depth == 0) are tilted CURL_TILT deg out of it (tip swinging away from
    the body) so they turn through depth instead of lying flat on the mass.
    The bend eases in (radius CURL_EASE times larger at the start, so the
    curve begins well above the hook), tightens to 65 % towards the tip, and
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
    n = max(8, round(turn / 6.0))
    out = []
    p = p0.copy()
    for k in range(n):
        th = T * (k + 0.5) / n
        f = th / T
        r = R * (1.0 - 0.35 * f) * (1.0 + (ease - 1.0) * (1.0 - smooth01(f / 0.45))) / PX
        p = p + (d * math.cos(th) + e * math.sin(th)) * (r * T / n) + axis * (pitch / n)
        if on_mass and iy == 0:
            bx, sx, row = to_px(p)
            p = P(bx, max(sx, mass_sx(bx, row, lay + HOOK_LAY)), row)
        out.append((clear_skirt(p), (k + 1) / n))
    return out, axis


def _resample(n, pos, seg_px, turn_deg, curl_from):
    """Indices of the dense samples kept as rings: a new ring every seg_px panel px
    on straight runs, or sooner once the spine has turned by turn_deg (CURL_TURN
    from sample curl_from on, so curls stay smooth)."""
    keep = [0]
    acc_l = acc_a = 0.0
    for i in range(1, n - 1):
        acc_l += (pos[i] - pos[i - 1]).length * PX
        t0 = pos[i] - pos[i - 1]
        t1 = pos[i + 1] - pos[i]
        if t0.length > 1e-9 and t1.length > 1e-9:
            acc_a += math.degrees(t0.angle(t1, 0.0))
        if acc_l >= seg_px or acc_a >= (turn_deg if i < curl_from else CURL_TURN):
            keep.append(i)
            acc_l = acc_a = 0.0
    if n - 1 - keep[-1] < 2 and len(keep) > 1:
        keep.pop()          # avoid a sliver ring right before the tip
    keep.append(n - 1)
    return keep


def clump(bm, layer, d):
    """Add one hair lock to bm; returns its shading normals (see set_volume_normals).

    d: pts (control points), w (width px, one per point), th (outer half
    thickness as a ratio of the half width), lay (depth offset px for
    (bx, row) points), n ('radial' or a fixed normal-hint tuple: the lock's
    outer face), tw (cross-section twist deg about the spine, scalar or one
    per point), wave (see _wave), curl (optional, see hook()) with tip (tip
    width px) and ctw (twist through the curl, deg), gr (rows where the
    green starts / is full), ring (verts per section), keep (own-normal share).

    The cross-section is a lens with a convex outer face and a flatter inner
    one (LENS_INNER): rounded in the middle, thinning to soft edges. Width and
    thickness both taper into the tip, which turns rounder (CURL_TH) so the
    points read as soft, not cut from card.
    """
    lay = d.get('lay', 0.0)
    ctrl = [_pt(p, lay) for p in d['pts']]
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

    pos, par = catmull(ctrl, DENSE_PX)
    if 'wave' in d:
        _wave(pos, d, on_mass, lay)
    # per dense sample: width, thickness ratio, twist, normal hint, own-normal share
    r0, r1 = d.get('gr', (380, 450))
    # the green lengths shade more as their own forms (the sheet's tips carry
    # darker undersides than the flat-lit upper mass)
    # Near the crown the locks are wider and flatter so they merge into one
    # smooth mass; they gain their own volume as they fall (TOP_ROWS).
    attrs = []
    for p, u in zip(pos, par):
        row = to_px(p)[2]
        # (back locks only: the side locks with a fixed outer face keep their size)
        f = smooth01((row - TOP_ROWS[0]) / (TOP_ROWS[1] - TOP_ROWS[0])) if n == 'radial' else 1.0
        attrs.append((lerp_list(w, u) * (TOP_WIDE + (1.0 - TOP_WIDE) * f),
                      th * (TOP_FLAT + (1.0 - TOP_FLAT) * f), lerp_list(tw, u), lerp_list(hints, u),
                      keep0 + max(0.0, LOW_KEEP - keep0) * smooth01((row - r0) / (r1 - r0)), 0.0))
    tip_w = d.get('tip', 2.0)
    curl_from = len(pos)
    if 'curl' in d:
        d0 = pos[-1] - pos[-4]
        pts, axis = hook(pos[-1], d0, d['curl'], d, on_mass, lay)
        w0, tw0, h0, k0 = attrs[-1][0], attrs[-1][2], attrs[-1][3], attrs[-1][4]
        ctw = d.get('ctw', CURL_TWIST)
        for p, u in pts:
            s = smooth01(u)
            ww = tip_w + (w0 - tip_w) * math.cos(u * math.pi / 2) ** 0.9
            hb = h0.lerp(axis, smooth01(u / 0.3))
            # the section rolls over early in the curl (the last field is the
            # roll: see the shading normals below)
            roll = ctw * smooth01(u / CURL_ROLL)
            attrs.append((ww, th + (CURL_TH - th) * s, tw0 + roll, hb,
                          k0 + max(0.0, CURL_KEEP - k0) * s, roll))
            pos.append(p)
    else:
        # taper the last stretch into a rounder soft point
        tot = 0.0
        acc = [0.0]
        for a, b in zip(pos, pos[1:]):
            tot += (b - a).length * PX
            acc.append(tot)
        for i in range(len(pos)):
            u = smooth01((acc[i] - (tot - TIP_PX)) / TIP_PX)
            ww, tt, *rest = attrs[i]
            attrs[i] = (ww, tt + (CURL_TH - tt) * u, *rest)
    idx = _resample(len(pos), pos, d.get('seg', SEG_PX), SEG_TURN, curl_from)
    nr = d.get('ring', RING)
    rings = []
    prev_side = None
    gmax = 0.0
    ns = len(idx)
    for j, i in enumerate(idx):
        p = pos[i]
        t = (pos[idx[min(j + 1, ns - 1)]] - pos[idx[max(j - 1, 0)]]).normalized()
        ww, tr, twi, nh, kk, roll = attrs[i]
        nrm = nh - t * nh.dot(t)
        if nrm.length < 1e-4:
            nrm = prev_side.cross(t) if prev_side is not None else t.orthogonal()
        nrm.normalize()
        side = t.cross(nrm).normalized()
        if prev_side is not None and side.dot(prev_side) < 0:
            side.negate()       # keep the frame from flipping between rings
            nrm.negate()
        prev_side = side
        # shading frame: the section before the curl's roll. Shading the rolled
        # section as if it had not rolled puts the lock's inner face, where it
        # turns towards the viewer, into the shade tone - the darker undersides
        # of the sheet's curls - while the geometry still turns through depth.
        s_side, s_nrm = _twist(side, nrm, twi - roll)
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
            own.append((s_side * (ca / hw) + s_nrm * (sa / hy)).normalized())   # lens normal
        row = spec.SHEET_GROUND_Y - p.z * PX
        gmax = max(gmax, smooth01((row - r0) / (r1 - r0)))
        rings.append((ring, gmax, kk, own))
    shading = {}
    verts = []
    for ring, g, kk, own in rings:
        # mesh vertex indices follow creation order
        shading.update((len(bm.verts) + k, (kk, own[k])) for k in range(nr))
        vs = []
        for co in ring:
            v = bm.verts.new(co)
            v[layer] = g
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

# Primary masses (ring 10): four broad, thick locks that make up most of the
# back - two per lobe, each with its own root-to-tip wave. Secondary locks
# (ring 8) sit between and over them and break their edges; the waves of
# neighbours are out of phase so the outlines cross like the sheet's.
MAIN = [
    # A (primary): left edge -> big C curl at the bottom left
    dict(pts=[('s', 60, 34, .95), ('s', 62, 62, .96), ('s', 62, 92, .96), (260, 150),
              (252, 195), (246, 240), (236, 285), (224, 325), (216, 365), (215, 400),
              (220, 430), (232, 452)],
         w=[18, 22, 26, 30, 36, 42, 48, 52, 50, 44, 36, 28], ring=10, th=0.45,
         wave=(9, 160, 0, 6), curl=(36, 210, (1, 0)), tilt=20, tip=2.0, ctw=85, gr=(310, 440)),
    # B (primary): left inner; ends higher, tapering out behind the C curl
    dict(pts=[('s', 40, 28, .95), ('s', 42, 62, .96), ('s', 41, 94, .96), (280, 150),
              (274, 195), (268, 240), (258, 290), (248, 335), (254, 372), (268, 400),
              (280, 420)],
         w=[18, 22, 26, 30, 36, 44, 50, 54, 50, 34, 10], ring=10, th=0.45,
         wave=(9, 150, 140, 6), gr=(330, 430), lay=3),
    # C: along the central parting, the longest, tapering to a point
    dict(pts=[('s', 18, 25, .95), ('s', 21, 62, .96), ('s', 20, 95, .96), (302, 150),
              (299, 195), (296, 240), (292, 290), (288, 330), (292, 368), (300, 404),
              (304, 436), (302, 460)],
         w=[14, 18, 22, 24, 28, 32, 36, 38, 36, 30, 20, 7],
         wave=(6, 140, 260, 5), gr=(360, 465), lay=-2),
    # D (primary): right of the parting -> curl at the bottom (365, 510)
    dict(pts=[('s', -2, 24, .95), ('s', -2, 62, .96), ('s', -2, 95, .96), (322, 150),
              (326, 195), (330, 240), (336, 290), (334, 330), (328, 368), (334, 404),
              (344, 434), (352, 458)],
         w=[18, 22, 26, 30, 36, 44, 50, 54, 50, 42, 32, 26], ring=10, th=0.45,
         wave=(9, 160, 60, 6), curl=(23, 220, (-1, 0)), tip=2.0, ctw=-85,
         gr=(340, 455), lay=2),
    # E: S lock that sweeps right and hooks at the right edge
    dict(pts=[('s', -20, 25, .95), ('s', -21, 62, .96), ('s', -20, 95, .96), (342, 150),
              (348, 195), (354, 240), (362, 290), (368, 326), (382, 352), (398, 370)],
         w=[14, 18, 22, 24, 28, 34, 38, 36, 32, 26],
         wave=(6, 130, 200, 5), curl=(22, 190, (-1, 0)), tip=2.0, ctw=-80,
         gr=(300, 400), lay=5),
    # F (primary): right outer -> outer curl at the bottom right
    dict(pts=[('s', -40, 28, .95), ('s', -42, 62, .96), ('s', -41, 94, .96), (360, 150),
              (368, 195), (378, 240), (392, 290), (406, 330), (416, 370), (420, 404),
              (424, 430), (428, 456)],
         w=[18, 22, 26, 30, 36, 42, 48, 50, 46, 38, 30, 24], ring=10, th=0.45,
         wave=(9, 160, 300, 6), curl=(27, 205, (-1, 0)), tip=2.0, ctw=-85, gr=(310, 430)),
    # G: right edge, tucked in under F; turns inward at the tip
    dict(pts=[('s', -60, 34, .95), ('s', -62, 62, .96), ('s', -62, 92, .96), (380, 150),
              (386, 195), (392, 240), (402, 290), (412, 330), (418, 370), (414, 398),
              (406, 418)],
         w=[14, 18, 22, 24, 28, 34, 38, 36, 32, 26, 20],
         wave=(6, 140, 100, 5), curl=(14, 100, (1, 0)), tip=1.5, ctw=35,
         gr=(300, 420), lay=-3),
]

# Wave locks on top of the mass: narrower locks with stronger S-waves that
# draw the sheet's interior wave lines across the lobes and break the
# primaries' edges. They end at different heights.
WAVES = [
    dict(pts=[('s', 30, 50, .97), ('s', 30, 92, .97), (284, 160), (276, 215), (266, 270),
              (252, 318), (244, 352), (254, 384), (270, 406)],
         w=[12, 16, 20, 22, 24, 26, 24, 16, 5], gr=(340, 430), lay=8, ring=6, seg=24),
    dict(pts=[('s', -10, 50, .97), ('s', -10, 92, .97), (328, 160), (334, 215), (342, 270),
              (350, 315), (352, 350), (346, 384), (348, 410), (354, 428)],
         w=[12, 16, 20, 22, 24, 26, 26, 24, 20, 14], curl=(10, 80, (1, 0)), tip=1.5, ctw=30,
         gr=(360, 440), lay=8, ring=6, seg=24),
    dict(pts=[('s', -36, 50, .97), ('s', -38, 92, .97), (364, 160), (372, 215), (380, 268),
              (392, 312), (398, 350), (392, 384), (394, 404)],
         w=[12, 16, 20, 22, 24, 26, 22, 14, 5], gr=(320, 420), lay=8, ring=6, seg=24),
]

# Inner sheet: closer to the back, so the side view reads as a thick mass and
# no body shows through between the back locks.
INNER_LEFT = [
    dict(pts=[('s', 30, 62, .93), ('s', 32, 95, .94), (272, 338, 150), (250, 340, 200),
              (236, 350, 260), (236, 360, 320), (244, 372, 380), (258, 382, 430),
              (270, 390, 458)],
         w=[22, 24, 24, 34, 42, 44, 42, 32, 4], th=0.55, gr=(360, 450), ring=8, seg=26),
]

# Side-view curls: locks on the character's left (nearest the side camera),
# broad in the side view, that bulge backwards and end in the curls behind
# the skirt. Their curls turn backwards (+Y) and twist through the turn, so
# they read as round curls from the side and as part of the left lobe's curl
# group from the back. They face sideways, so they keep more of their own
# normals than the back-facing volume normal.
SWEEP = [
    # upper open curl: hole around sx 414-450, rows 375-402
    dict(pts=[('s', 30, 50, .93), ('s', 30, 92, .94), (282, 362, 150), (276, 378, 195),
              (268, 380, 250), (262, 416, 300), (262, 430, 335), (264, 410, 362),
              (268, 400, 386), (272, 408, 410)],
         w=[8, 10, 12, 20, 28, 32, 32, 30, 28, 26], th=0.5, n=(1, 0, 0), tw=30,
         curl=(20, 280, (0, 1)), tip=2.0, ctw=60, pitch=0.6, gr=(330, 420), keep=0.7, ring=6),
    # lower curl, rows 410-460
    dict(pts=[('s', 12, 50, .93), ('s', 12, 92, .94), (306, 362, 150), (304, 378, 195),
              (300, 380, 250), (296, 418, 300), (294, 430, 335), (292, 416, 370),
              (292, 414, 400), (294, 430, 436)],
         w=[8, 10, 12, 20, 28, 32, 30, 26, 24, 22], th=0.5, n=(1, 0, 0), tw=30,
         curl=(16, 240, (0, 1)), tip=1.5, ctw=60, pitch=0.6, gr=(340, 430), keep=0.7, ring=6),
]

# Outer side layer (mirrored pair): falls from the side of the head over the
# shoulders and hangs along the top of the sleeves.  Seen as the green-tipped
# flicks over the shoulders, the lock peeking out above the sleeve top and
# the big hooks that stick out past the sleeves in the front and back views.
OUTER_LEFT = [
    # shoulder flick: outer extremity ~(178, 230); flicks back to sx ~420
    dict(pts=[('s', 70, 80, .95), ('s', 72, 100, .95), (268, 340, 150), (246, 360, 192),
              (210, 384, 215), (190, 402, 232)],
         w=[16, 16, 14, 16, 18, 14], n=(0, 1, 0), th=0.75,
         curl=(8, 150, (1, 0)), tip=2.0, ctw=40, gr=(205, 245), ring=6),
    # lock behind the sleeve top, ends around (140, 334)
    dict(pts=[('s', 66, 95, .95), (270, 344, 150), (246, 354, 198), (214, 366, 240),
              (186, 378, 275), (162, 386, 300), (146, 390, 320), (140, 392, 334)],
         w=[16, 14, 14, 20, 26, 22, 14, 3], n=(0, 1, 0), th=0.75, gr=(285, 335), ring=8),
    # big hook: hangs behind the sleeve to the cuff, then curls up and out as a
    # broad crescent in the front and back views; a thick, rounded section gives
    # it body from the side (it stays at the sleeve's depth so the sleeve hides
    # its upper length in the front and back views, as on the sheet)
    dict(pts=[('s', 64, 100, .95), (268, 348, 155), (242, 358, 205), (212, 370, 250),
              (180, 382, 300), (150, 392, 350), (124, 398, 400), (110, 400, 424), (96, 400, 431),
              (82, 400, 420), (75, 400, 402), (72, 400, 380), (75, 400, 365), (80, 400, 355),
              (85, 400, 347)],
         w=[16, 14, 14, 24, 30, 28, 25, 22, 20, 18, 16, 14, 10, 6, 2], n=(0, 1, 0), th=0.85,
         gr=(320, 410), ring=8),
]

# Backing curtain: one continuous shell under the locks so the mass reads
# solid (no body showing between locks) from the crown to the hips.  Rows
# above the skull equator wrap the back half of the skull; below, an arc
# that follows the mass surface a few px inside the locks.
CURTAIN_STEP = 11   # verts per arc (outer and inner surface each)
CURTAIN_T = 7.0     # shell thickness px
CURTAIN_INSET = 5.0
CURTAIN_WRAP = 40.0  # px the arc curls forward at its side edges
# row -> half width of the curtain arc below the skull (px)
CURTAIN_HW = [(175, 62), (200, 62), (240, 66), (280, 78), (320, 92), (360, 94),
              (390, 86), (410, 66), (424, 38)]


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
            sx = mass_sx(CX - X, r) - CURTAIN_INSET - wrap
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
        g = smooth01((row - 368) / 65.0)
        vs = []
        for X, Y in loop:
            v = bm.verts.new(Vector((spec.px_to_h(X), spec.px_to_h(Y), spec.px_to_z(row))))
            v[layer] = g
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
VOL_KEEP = 0.3


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
