"""Fit the skirt's godet folds (skirt.FOLDS) to the three reference views.

    blender -b --factory-startup -P levi/parts/_skirt_fit.py [-- [--fresh] [--write] | --report] [--baseline OLD_SKIRT.py]

The cloth is skirt.profiles(FOLDS). Each fold has a crest azimuth, the hem
row at its crest and at the following trough, a half-depth and a smooth
radial offset. The fit compares, per view, against the measured outline tables in skirt.py:
- the lower outline: per column the lowest *visible* cloth point near the hem
  vs FRONT_HEM / BACK_HEM / SIDE_HEM. Visibility uses a depth buffer of the
  current petticoat (built here from levi/parts/petticoat.py): cloth behind
  the petticoat does not show, cloth in front of it or below it does;
- the flare outline above the hem: per row the outermost cloth point vs the
  EDGE_* tables;
- clearance: no cloth point may sit inside the petticoat (radially, per
  azimuth and row) - the skirt is the outer garment;
- priors: folds stay near AMP_TARGET deep, smooth offsets vary slowly, and
  every trough sits above its two crests;
- hem smoothness (round 6): the built hem's slope and curvature along the
  cloth (SLOPE_MAX / CURV_MAX), so no lobe hangs as a narrow tongue between
  two deep arches (edge-on it read as a thin fin).
Coordinate descent over the fold parameters, deterministic. With --write the
FOLDS table in skirt.py is replaced in place; --report only scores it.
--freeze 1,5 keeps those FOLDS columns as they are. --baseline OLD.py adds a
penalty for cloth more than INSIDE_TOL px inside an earlier skirt (the layer
the petticoat was fitted inside), e.g. after
    git show main:levi/parts/skirt.py > out/skirt_base.py
The petticoat follows the skirt's folds, so re-run the fit once per skirt
change rather than iterating the two to convergence. Since round 6 the
petticoat's ruffles hang from the stored FOLDS' hem (petticoat.cluster_rows),
so the occluders and the clearance term describe the stored table: the fit is
biased toward it and should move the table in small steps (CREST_SLACK). A
change of the fold count is a manual edit of FOLDS / initial_folds() first.
"""
import os
import re
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from levi.parts import skirt  # noqa: E402

N = skirt.N_PHI
MISS = 25.0        # per-column penalty where the reference has skirt and the model none
STICK = 12.0       # per-column penalty where the model sticks out past the reference
OFF_RANGE = (-50.0, 30.0)
CURL_RANGE = (-10.0, 24.0)   # a deeper tuck collapses the lobe under the bell
CURL_SIDE = 11.0   # crest tuck beyond this is penalised, except toward the centre front / back lobes
CURL_W = 20.0
CURL_SMOOTH = 0.3
DEPTH_MAX = 50.0   # trough arches higher than this above a neighbouring crest are penalised
DEPTH_W = 2.0
INSIDE_W = 200.0   # per px of cloth more than INSIDE_TOL inside the baseline skirt (--baseline)
INSIDE_TOL = 2.5
ROW_RANGE = (525.0, 625.0)
AMP_RANGE = (10.0, 28.0)
AMP_TARGET = 20.0  # fold half-depth the prior pulls toward (px)
AMP_W = 2.0
BASE_SMOOTH = 1.0
ORDER_W = 100.0
LOBE_MIN = 10.0    # a trough is at least this many rows above its crests
VIEW_W = {'front': 1.0, 'back': 1.5, 'side': 1.5}
LOW_W = {'front': 0.5, 'back': 0.5, 'side': 4.0}   # extra per px hanging below the outline
LOW_TOL = 6.0
OUT_W = 6.0        # per px a strip past the outline's ends hangs below its end row
EDGE_W = 5.0
PET_W = 60.0       # per px of a cloth point inside the petticoat (+ CLEAR)
CLEAR = 3.0
VIS_TOL = 3.0      # px a cloth point may sit behind the petticoat depth and still count as visible
UPS = 12           # azimuth upsampling of the hem curve (sub-pixel spacing for the envelope)
# Hem smoothness (the built, smoothed hem row along the arc of the hem): a lobe
# hanging far below two narrow arches is a near-flat strip of cloth that reads
# as a thin fin edge-on, and its flanks as near-vertical cut edges. Penalised
# per px of arc: the hem's slope (rows per px of arc) beyond SLOPE_MAX and its
# curvature (rows per px^2) beyond CURV_MAX, both squared. Arc length counts
# the fold's radial in / out (hem_shape()).
SLOPE_MAX = 1.3
SLOPE_W = 40.0
CURV_MAX = 0.08
CURV_W = 4.0e4


def COL_W(view, c):
    """Per-column weight. The side view's low lobe at the hip line (|y| < ~32 px)
    hangs to row ~604 while the front and back views put the hem at that
    azimuth near row 550-565 and the petticoat's ruffles stand out past it; it
    cannot match all three, so the front/back views win there."""
    if view == 'side' and -36 <= c <= 30:
        return 0.6
    # The back view's centre lobes hang to rows ~590-619 over |x| < 110 px,
    # which cloth outside the petticoat's inner tiers can only do at
    # y ~ +95..+150, where the side view ends the skirt at rows ~550-589: the
    # back view wins there too.
    if view == 'side' and 85 <= c <= 150:
        return 0.2
    return 1.0


# view: (horizontal, depth toward the camera is smaller, table)
VIEWS = {
    'front': (lambda x, y: x, lambda x, y: y, skirt.FRONT_HEM),
    'back': (lambda x, y: -x, lambda x, y: -y, skirt.BACK_HEM),
    'side': (lambda x, y: y, lambda x, y: -x, skirt.SIDE_HEM),
}


def dense(table_s):
    t = skirt.parse_table(table_s)
    lo, hi = int(t[0][0]), int(t[-1][0])
    return lo, np.array([skirt.interp(t, c) for c in range(lo, hi + 1)])


REFS = {k: dense(v[2]) for k, v in VIEWS.items()}
COLW = {k: np.array([COL_W(k, lo + j) for j in range(len(ref))]) for k, (lo, ref) in REFS.items()}

# Outer outline of the flare above the hem (panel px, measured on the
# reference): front view half-width, side view front (-Y) and back (+Y) edge.
EDGE_FRONT_X = {485: 197, 500: 217, 520: 238, 535: 246, 550: 240, 560: 231}
EDGE_SIDE_F = {400: -116, 450: -122, 480: -133, 500: -142, 520: -153, 540: -163,
               550: -168, 560: -172, 570: -176, 580: -170, 590: -158}
EDGE_SIDE_B = {480: 121, 500: 141, 520: 158, 540: 169, 552: 165, 558: 160}
# Below the hem line only upper bounds: the whole reference silhouette
# (skirt + petticoat, ref/<view>_mask.png) per row - cloth must stay inside.
# (front-view half width, side-view front edge, side-view back edge)
SIL_MAX = {564: (229, -174, 157), 570: (234, -176, 162), 576: (236, -174, 163),
           582: (230, -168, 158), 588: (222, -160, 152), 594: (213, -158, 144),
           600: (201, -162, 142), 606: (191, -161, 136), 612: (164, -148, 120)}
SIL_W = 6.0
EDGE_ROWS = np.array(sorted(set(EDGE_FRONT_X) | set(EDGE_SIDE_F) | set(EDGE_SIDE_B) | set(SIL_MAX)),
                     dtype=float)

# ---------------------------------------------------------------- petticoat
H0, HN = -340, 681          # depth-buffer columns
R0, RN = 300, 400           # depth-buffer rows
NB = 180                    # azimuth bins of the radial table
RB0, RBN = 330, 170         # radial-table rows (2 px bins)


def petticoat_samples():
    """Dense surface samples (x, y, row) in panel px of the current petticoat."""
    import bpy
    from levi import builder
    builder.reset_scene()
    col = builder.build_part('petticoat')
    bpy.context.view_layer.update()
    pts = []
    for o in col.all_objects:
        if o.type != 'MESH' or o.hide_render:
            continue
        mw = np.array(o.matrix_world)
        me = o.data
        co = np.array([v.co[:] for v in me.vertices])
        co = co @ mw[:3, :3].T + mw[:3, 3]
        pts.append(co)
        for p in me.polygons:
            vs = co[list(p.vertices)]
            c = vs.mean(axis=0)
            for a in (0.33, 0.66):
                pts.append(c + (vs - c) * a)
    co = np.concatenate([p.reshape(-1, 3) for p in pts])
    px = np.empty_like(co)
    px[:, 0] = co[:, 0] * spec_ppm()
    px[:, 1] = co[:, 1] * spec_ppm()
    px[:, 2] = skirt.spec.SHEET_GROUND_Y - co[:, 2] * spec_ppm()
    return px


def spec_ppm():
    return skirt.spec.PX_PER_M


def build_occluders(px):
    zb = {}
    for v, (hf, df, _) in VIEWS.items():
        z = np.full((RN, HN), np.inf)
        h = np.round(hf(px[:, 0], px[:, 1])).astype(int) - H0
        r = np.round(px[:, 2]).astype(int) - R0
        ok = (h >= 0) & (h < HN) & (r >= 0) & (r < RN)
        np.minimum.at(z, (r[ok], h[ok]), df(px[ok, 0], px[ok, 1]))
        for _ in range(2):    # close sampling holes (min filter)
            zz = z.copy()
            for dr in (-1, 0, 1):
                for dh in (-1, 0, 1):
                    zz = np.minimum(zz, np.roll(np.roll(z, dr, 0), dh, 1))
            z = zz
        zb[v] = z
    rad = np.full((RBN, NB), -np.inf)
    phi = np.mod(np.arctan2(px[:, 0], -px[:, 1]), 2 * np.pi)
    b = (phi / (2 * np.pi) * NB).astype(int) % NB
    rb = np.round((px[:, 2] - RB0) / 2).astype(int)
    ok = (rb >= 0) & (rb < RBN)
    np.maximum.at(rad, (rb[ok], b[ok]), np.hypot(px[ok, 0], px[ok, 1]))
    # fill sampling holes (a few bins into empty cells only), then pad by one bin
    for _ in range(4):
        nb = rad.copy()
        for dr in (-1, 0, 1):
            for db in (-1, 0, 1):
                nb = np.maximum(nb, np.roll(np.roll(rad, dr, 0), db, 1))
        rad = np.where(np.isfinite(rad), rad, nb)
    rr = rad.copy()
    for dr in (-1, 0, 1):
        for db in (-1, 0, 1):
            rr = np.maximum(rr, np.roll(np.roll(rad, dr, 0), db, 1))
    return zb, rr


ZB, RAD, BASE_RAD = None, None, None
HEM_T0 = 0.75      # rings from here down count for the visible lower outline
LOW_T0 = 0.2       # rings from here down count for the clearance / baseline terms


# ---------------------------------------------------------------- error terms
def hem_curves(P):
    """Hem-zone points (the rings from t = HEM_T0 down), upsampled along azimuth."""
    k0 = int(np.searchsorted(skirt.T_STEPS, HEM_T0 - 1e-9))
    H = P[:, k0:, :]
    nxt = np.roll(H, -1, axis=0)
    parts = [H + (nxt - H) * (j / UPS) for j in range(UPS)]
    return np.stack(parts, axis=1).reshape(-1, 3)


def envelope(view, pts):
    hf, df, _ = VIEWS[view]
    h = hf(pts[:, 0], pts[:, 1])
    d = df(pts[:, 0], pts[:, 1])
    hi = np.round(h).astype(int)
    ri = np.round(pts[:, 2]).astype(int)
    zi = ZB[view][np.clip(ri - R0, 0, RN - 1), np.clip(hi - H0, 0, HN - 1)]
    vis = d <= zi + VIS_TOL
    m = np.full(HN, -np.inf)
    vis &= (hi - H0 >= 0) & (hi - H0 < HN)
    np.maximum.at(m, hi[vis] - H0, pts[vis, 2])
    # the upsampled hem points can still step over a column where the
    # azimuth samples are sparse (the broad crests): fill empty columns
    # between two filled ones (no wrap-around at the ends)
    gap = np.full(HN, -np.inf)
    gap[1:-1] = np.minimum(m[:-2], m[2:])
    return np.where(np.isinf(m), gap, m)


def view_error(view, pts):
    lo, ref = REFS[view]
    m = envelope(view, pts)
    mv = m[lo - H0: lo - H0 + len(ref)]
    miss = ~np.isfinite(mv)
    dz = np.where(miss, 0, mv) - ref
    e = np.where(miss, MISS, np.abs(dz)) * COLW[view]
    err = e.sum()
    # cloth hanging below the outline reads as a tongue over the petticoat
    err += LOW_W[view] * np.maximum(0.0, dz - LOW_TOL).sum()
    # cloth showing past the ends of the measured outline: a flat cost per
    # column, plus the drop below the outline's end row (a strip hanging
    # down beside the silhouette must not be cheap)
    out = np.isfinite(m)
    out[lo - H0: lo - H0 + len(ref)] = False
    err += STICK * out.sum()
    cols = np.nonzero(out)[0]
    if len(cols):
        end = np.where(cols < lo - H0, ref[0], ref[-1])
        err += OUT_W * np.maximum(0.0, m[cols] - end - LOW_TOL).sum()
    return err * VIEW_W[view], m


def row_crossings(P):
    """Outer extents at EDGE_ROWS: (min x, max x, min y, max y) per row."""
    a, b = P[:, :-1, :], P[:, 1:, :]
    r = EDGE_ROWS[:, None, None]
    ra, rb = a[None, :, :, 2], b[None, :, :, 2]
    hit = ((ra - r) * (rb - r) <= 0) & (ra != rb)
    f = np.where(hit, (r - ra) / np.where(ra != rb, rb - ra, 1.0), 0.0)
    x = a[None, :, :, 0] + (b[None, :, :, 0] - a[None, :, :, 0]) * f
    y = a[None, :, :, 1] + (b[None, :, :, 1] - a[None, :, :, 1]) * f
    big = 1e9
    return (np.where(hit, x, big).min(axis=(1, 2)), np.where(hit, x, -big).max(axis=(1, 2)),
            np.where(hit, y, big).min(axis=(1, 2)), np.where(hit, y, -big).max(axis=(1, 2)))


def edge_error(P):
    x0, x1, y0, y1 = row_crossings(P)
    idx = {r: i for i, r in enumerate(EDGE_ROWS)}
    err = 0.0
    for r, v in EDGE_FRONT_X.items():
        i = idx[r]
        err += abs(-x0[i] - v) + abs(x1[i] - v) if x1[i] > -1e8 else 2 * v
    for r, v in EDGE_SIDE_F.items():
        i = idx[r]
        err += abs(y0[i] - v) if y0[i] < 1e8 else abs(v)
    for r, v in EDGE_SIDE_B.items():
        i = idx[r]
        err += abs(y1[i] - v) if y1[i] > -1e8 else abs(v)
    over = 0.0
    for r, (hw, yf, yb) in SIL_MAX.items():
        i = idx[r]
        if x1[i] < -1e8:          # no cloth this low
            continue
        over += max(0.0, -x0[i] - hw) + max(0.0, x1[i] - hw)
        over += max(0.0, yf - y0[i]) + max(0.0, y1[i] - yb)
    return EDGE_W * err + SIL_W * over


def clearance_error(P):
    """Cloth points inside the petticoat (px summed), sampled along the faces
    between rings too."""
    pts = cloth_samples(P)
    b, rb, ok = radial_bins(pts)
    rp = np.full(len(pts), -np.inf)
    rp[ok] = RAD[rb[ok], b[ok]]
    r = np.hypot(pts[:, 0], pts[:, 1])
    return np.maximum(0.0, rp + CLEAR - r).sum()


def cloth_samples(P):
    """Cloth points from t = LOW_T0 down (below the waist band) plus points
    along the faces between rings."""
    k0 = int(np.searchsorted(skirt.T_STEPS, LOW_T0 - 1e-9))
    Q = P[:, k0:, :]
    a, b = Q[:, :-1, :], Q[:, 1:, :]
    return np.concatenate([Q] + [a + (b - a) * f for f in (0.25, 0.5, 0.75)], axis=1).reshape(-1, 3)


def radial_bins(pts):
    phi = np.mod(np.arctan2(pts[:, 0], -pts[:, 1]), 2 * np.pi)
    b = (phi / (2 * np.pi) * NB).astype(int) % NB
    rb = np.round((pts[:, 2] - RB0) / 2).astype(int)
    return b, rb, (rb >= 0) & (rb < RBN)


def baseline_radius(path):
    """Innermost cloth radius per (row bin, azimuth bin) of an earlier skirt
    module (e.g. the round-3 skirt.py, which the petticoat is fitted inside)."""
    import importlib.util
    spec_ = importlib.util.spec_from_file_location('levi.parts._skirt_baseline', path)
    mod = importlib.util.module_from_spec(spec_)
    spec_.loader.exec_module(mod)
    P = mod.profiles(mod.fold_table())
    a, b = P[:, :-1, :], P[:, 1:, :]
    pts = np.concatenate([P] + [a + (b - a) * f for f in np.linspace(0.1, 0.9, 9)], axis=1)
    nxt = np.roll(pts, -1, axis=0)
    pts = np.concatenate([pts + (nxt - pts) * f for f in (0.0, 0.25, 0.5, 0.75)], axis=1).reshape(-1, 3)
    bb, rb, ok = radial_bins(pts)
    rad = np.full((RBN, NB), np.inf)
    np.minimum.at(rad, (rb[ok], bb[ok]), np.hypot(pts[ok, 0], pts[ok, 1]))
    return rad


def inside_baseline(P):
    """Per sample: px the cloth sits inside the baseline skirt (0 where no baseline)."""
    pts = cloth_samples(P)
    b, rb, ok = radial_bins(pts)
    rr = np.full(len(pts), np.inf)
    rr[ok] = BASE_RAD[rb[ok], b[ok]]
    r = np.hypot(pts[:, 0], pts[:, 1])
    return np.where(np.isfinite(rr), np.maximum(0.0, rr - r), 0.0)


def prior_error(folds):
    """Keep the folds deep and the smooth offset / hem rows coherent between folds."""
    f = np.array(folds, dtype=np.float64)
    nxt = np.roll(f, -1, axis=0)
    e = AMP_W * ((f[:, 3] - AMP_TARGET) ** 2).sum()
    e += BASE_SMOOTH * ((f[:, 4] - nxt[:, 4]) ** 2).sum()
    # a trough sits above both neighbouring crests
    e += ORDER_W * (np.maximum(0, f[:, 2] + LOBE_MIN - f[:, 1]) +
                    np.maximum(0, f[:, 2] + LOBE_MIN - nxt[:, 1])).sum()
    # ... but not far above: deep arches read as a cut, scalloped shell
    e += DEPTH_W * (np.maximum(0, f[:, 1] - f[:, 2] - DEPTH_MAX) ** 2 +
                    np.maximum(0, nxt[:, 1] - f[:, 2] - DEPTH_MAX) ** 2).sum()
    # neighbouring crest curls change gradually (no lobe tucked under alone)
    e += CURL_SMOOTH * ((f[:, 5] - nxt[:, 5]) ** 2).sum()
    # only the long centre-front / centre-back lobes may tuck under deeply
    cap = CURL_SIDE + (CURL_RANGE[1] - CURL_SIDE) * np.cos(np.radians(f[:, 0])) ** 4
    e += CURL_W * (np.maximum(0.0, f[:, 5] - cap) ** 2).sum()
    return e


def hem_shape(folds):
    """(slope, curvature, arc px per sample) of the built hem row along the
    hem, on skirt._dense()'s fine azimuth grid."""
    d = skirt._dense(folds)
    row = d['row']
    rad = skirt._hem_radius(d['phi']) + d['off'][:, -1]
    # arc length along the hem in plan, the fold's radial in / out included:
    # a deep fold's flank runs toward the view, so the hem may drop steeply in
    # projection while it falls gently along the cloth
    ds = np.hypot(rad * (d['phi'][1] - d['phi'][0]), 0.5 * (np.roll(rad, -1) - np.roll(rad, 1)))
    slope = (np.roll(row, -1) - np.roll(row, 1)) / (2 * ds)
    curv = (np.roll(row, -1) - 2 * row + np.roll(row, 1)) / ds ** 2
    return slope, curv, ds


def smooth_error(folds):
    slope, curv, ds = hem_shape(folds)
    return (SLOPE_W * (np.maximum(0.0, np.abs(slope) - SLOPE_MAX) ** 2 * ds).sum() +
            CURV_W * (np.maximum(0.0, np.abs(curv) - CURV_MAX) ** 2 * ds).sum())


def total_error(folds, detail=False):
    P = skirt.profiles(folds)
    pts = hem_curves(P)
    ev = {v: view_error(v, pts)[0] for v in VIEWS}
    ee = edge_error(P)
    ce = PET_W * clearance_error(P)
    if BASE_RAD is not None:
        ce += INSIDE_W * np.maximum(0.0, inside_baseline(P) - INSIDE_TOL).sum()
    pe = prior_error(folds) + smooth_error(folds)
    tot = sum(ev.values()) + ee + ce + pe
    if detail:
        return tot, ev, ee, ce, pe
    return tot


# ---------------------------------------------------------------- fit
# per fold column: (step sizes, (min, max))
PARAMS = {
    0: ((2, 1, -1, -2), None),                  # crest azimuth (deg), kept in order
    1: ((8, 4, 2, -2, -4, -8), ROW_RANGE),      # crest hem row
    2: ((8, 4, 2, -2, -4, -8), ROW_RANGE),      # trough hem row
    3: ((4, 2, -2, -4), AMP_RANGE),             # half-depth
    4: ((4, 2, -2, -4), OFF_RANGE),             # smooth offset
    5: ((6, 3, -3, -6), CURL_RANGE),            # crest tuck (px; < 0 flares out)
    6: ((2, 1, -1, -2), (15, 20)),              # hem lobe exponent x10 (wider lobe bottom)
}
DEFAULTS = (0, 0, 0, 18, 0, 6, 16)    # for columns a stored table lacks
CREST_GAP = 20        # min degrees between neighbouring crests (no narrow pinched folds)
CREST_SLACK = 8       # max degrees a crest may move from its initial azimuth


def valid_azimuth(folds, k, init):
    n = len(folds)
    a = folds[k][0]
    if abs(a - init[k][0]) > CREST_SLACK:
        return False
    prev = folds[(k - 1) % n][0] - (360 if k == 0 else 0)
    nxt = folds[(k + 1) % n][0] + (360 if k == n - 1 else 0)
    return a - prev >= CREST_GAP and nxt - a >= CREST_GAP and 0 <= a < 360


def fit(passes=30, fresh=False, freeze=()):
    """Coordinate descent from the stored table (or skirt.initial_folds()),
    keeping the FOLDS columns in `freeze` as they are."""
    start = skirt.initial_folds() if fresh or not skirt.FOLDS else skirt.FOLDS
    folds = [list(f) + list(DEFAULTS[len(f):]) for f in start]
    for f in folds:
        for col, (_, rng) in PARAMS.items():
            if rng is not None:
                f[col] = min(rng[1], max(rng[0], f[col]))
    init = [list(f) for f in folds]
    best = total_error(folds)
    print('initial error', round(best, 1))
    n = len(folds)
    for p in range(passes):
        improved = 0
        for k in range(n):
            for col, (steps, rng) in PARAMS.items():
                if col in freeze:
                    continue
                # single fold, this fold and the next together, and (once
                # per pass) all folds at once
                groups = [(k,), (k, (k + 1) % n)]
                if k == 0:
                    groups.append(tuple(range(n)))
                for group in groups:
                    if col == 0 and len(group) > 1:
                        continue
                    for s in steps:
                        old = [folds[j][col] for j in group]
                        for j in group:
                            v = folds[j][col] + s
                            folds[j][col] = v if rng is None else min(rng[1], max(rng[0], v))
                        ok = [folds[j][col] for j in group] != old
                        if ok and col == 0:
                            ok = valid_azimuth(folds, k, init)
                        e = total_error(folds) if ok else None
                        if e is not None and e < best - 1e-6:
                            best = e
                            improved += 1
                        else:
                            for j, v in zip(group, old):
                                folds[j][col] = v
        print(f'pass {p} error {best:.1f} moves {improved}', flush=True)
        if not improved:
            break
    return [tuple(int(round(v)) for v in f) for f in folds], best



def report(folds):
    tot, ev, ee, ce, pe = total_error(folds, detail=True)
    P = skirt.profiles(folds)
    pts = hem_curves(P)
    for v in VIEWS:
        e, m = view_error(v, pts)
        lo, ref = REFS[v]
        mv = m[lo - H0: lo - H0 + len(ref)]
        fin = np.isfinite(mv)
        d = np.where(fin, mv - ref, 0)
        worst = sorted(zip(np.abs(d), np.arange(lo, lo + len(ref)), d), reverse=True)[:6]
        print(f'{v}: score {e:.0f}  mean |dz| {np.abs(d[fin]).mean():.1f}px over {fin.sum()} cols, '
              f'{(~fin).sum()} cols hidden/missing; worst (col, dz) '
              f'{[(int(c), int(z)) for _, c, z in worst]}')
    pet = PET_W * clearance_error(P)
    print(f'edges {ee:.0f}  petticoat clearance {pet:.1f}  baseline {ce - pet:.1f}  '
          f'prior {pe:.0f}  total {tot:.0f}')
    f = np.array(folds, dtype=np.float64)
    depth = np.maximum(f[:, 1], np.roll(f[:, 1], -1)) - f[:, 2]
    print(f'arch depth (px) max {depth.max():.0f} mean {depth.mean():.0f}; crest curl max {f[:, 5].max():.0f}')
    slope, curv, _ = hem_shape(folds)
    print(f'hem smoothness: max slope {np.abs(slope).max():.2f} (cap {SLOPE_MAX}), curvature '
          f'{curv.min():.3f}..{curv.max():.3f} (cap {CURV_MAX}), penalty {smooth_error(folds):.0f}')
    # inward moves vs the baseline skirt (the petticoat is fitted inside it)
    if BASE_RAD is not None:
        d = inside_baseline(P)
        print(f'cloth samples > {INSIDE_TOL} px inside the baseline skirt: '
              f'{int((d > INSIDE_TOL).sum())}/{len(d)}; deepest {d.max():.1f} px')
    else:
        print('no --baseline given: inward moves vs an earlier skirt are not checked')


def write(folds):
    path = os.path.join(ROOT, 'levi', 'parts', 'skirt.py')
    with open(path, encoding='utf-8') as f:
        src = f.read()
    body = 'FOLDS = [\n' + ''.join(f'    {tuple(int(v) for v in r)},\n' for r in folds) + ']'
    src, n = re.subn(r'^FOLDS = (None|\[[^\]]*\])', body, src, flags=re.M)
    assert n == 1
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(src)
    print('wrote', path)


def main():
    global ZB, RAD, BASE_RAD
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    ZB, RAD = build_occluders(petticoat_samples())
    if '--baseline' in args:
        BASE_RAD = baseline_radius(args[args.index('--baseline') + 1])
    if '--report' in args:
        folds = skirt.fold_table()
    else:
        freeze = ()
        if '--freeze' in args:      # e.g. --freeze 1,6: keep the crest rows and lobe widths
            freeze = tuple(int(c) for c in args[args.index('--freeze') + 1].split(','))
        folds, _ = fit(fresh='--fresh' in args, freeze=freeze)
    report(folds)
    print('FOLDS =', folds)
    if '--write' in args:
        write(folds)


if __name__ == '__main__':
    main()