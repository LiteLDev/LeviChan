"""Fit the skirt hem (skirt.HEM_ROW / skirt.HEM_OFF) to the three reference views.

    blender -b --factory-startup -P levi/parts/_skirt_fit.py [-- --write]

The hem is a closed curve sampled at N_PHI azimuths; each sample has a row
(height) and a radial fold offset. Projected into a view, the lower envelope
of the visible part of that curve is the skirt's lower outline, which must
match the measured outline tables in skirt.py. Visibility follows the
petticoat: it fills the inside of the skirt down to below the hem, so in each
view only the near half of the hem shows (front: y < 3 px, back: y > -3 px,
side from +X: x > -3 px; the 3 px tolerance keeps the silhouette-plane samples
in both halves). Hidden far-half samples are only kept from hanging more than
FAR_SLACK rows below the near outline.

Coordinate descent on rows and offsets minimises the L1 outline error summed
over the three views, plus a small smoothness term on offsets. Deterministic.
With --write the tables in skirt.py are replaced in place.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from levi.parts import skirt  # noqa: E402

N = skirt.N_PHI
MISS = 25.0        # per-column penalty where the reference has skirt and the model none
STICK = 12.0       # per-column penalty where the model sticks out past the reference
SMOOTH = 0.04      # offset smoothness weight
OFF_RANGE = (-40.0, 28.0)
ROW_RANGE = (525.0, 625.0)
EXT_ROWS = (530, 626)
FAR_W = 2.0
FAR_SLACK = 12.0
ROW_SMOOTH = 0.03
ROW_CURV = 0.06
OFF_CURV = 0.25


def COL_W(view, c):
    """Per-column weight. The side view's low lobe at the hip line (|y| < ~32 px)
    hangs to row ~604 while the front and back views put the hem at that
    azimuth near row 550-565; it cannot match all three, so the front/back
    views win there."""
    if view == 'side' and -36 <= c <= 30:
        return 0.25
    return 1.0
EXT_W = 0.5
VIEW_W = {'front': 1.0, 'back': 1.0, 'side': 0.7}   # side view disagrees most with the others

VIEWS = {
    # name: (horizontal from (x, y), visible(x, y), table)
    'front': (lambda x, y: x, lambda x, y: y < 3.0, skirt.FRONT_HEM),
    'back': (lambda x, y: -x, lambda x, y: y > -3.0, skirt.BACK_HEM),
    'side': (lambda x, y: y, lambda x, y: x > -3.0, skirt.SIDE_HEM),
}


def dense(table_s):
    t = skirt.parse_table(table_s)
    lo, hi = int(t[0][0]), int(t[-1][0])
    return lo, [skirt.interp(t, c) for c in range(lo, hi + 1)]


REFS = {k: dense(v[2]) for k, v in VIEWS.items()}
# reference columns whose outline reaches at least row r, per view (for the extent term)
REF_EXT = {k: {r: [lo + j for j, rv in enumerate(ref) if rv >= r] for r in range(*EXT_ROWS, 3)}
           for k, (lo, ref) in REFS.items()}


def hem_points(rows, offs):
    return [skirt.point_px(i, 1.0, rows[i], offs[i]) for i in range(N)]


def view_error(name, pts):
    hf, vis, _ = VIEWS[name]
    lo, ref = REFS[name]
    m = {}
    proj = [(hf(x, y), r, vis(x, y)) for x, y, r in pts]
    for h, r, v in proj:
        # endpoints too, so near-vertical segments (narrow hanging slivers) count
        if v and r > m.get(round(h), -1e9):
            m[round(h)] = r
    for i in range(N):
        h0, r0, v0 = proj[i]
        h1, r1, v1 = proj[(i + 1) % N]
        if not (v0 and v1):
            continue
        if h1 < h0:
            h0, r0, h1, r1 = h1, r1, h0, r0
        c0, c1 = int(h0) + (h0 > int(h0)), int(h1 // 1)
        span = h1 - h0
        for c in range(c0, c1 + 1):
            r = r0 if span < 1e-9 else r0 + (r1 - r0) * (c - h0) / span
            if r > m.get(c, -1e9):
                m[c] = r
    err = 0.0
    # hidden (far-side) hem must not hang visibly below the near hem: the
    # petticoat only hides it for FAR_SLACK rows below the near outline
    for h, r, v in proj:
        if v:
            continue
        env = m.get(round(h))
        if env is None:
            err += FAR_W * max(0.0, r - 540.0)
        else:
            err += FAR_W * max(0.0, r - env - FAR_SLACK)
    # horizontal extents of the hanging lobes, row by row (penalises thin
    # slivers that a column-only metric barely sees)
    if m:
        cols = sorted(m)
        for r in range(EXT_ROWS[0], EXT_ROWS[1], 3):
            mc = [c for c in cols if m[c] >= r]
            rc = REF_EXT[name][r]
            if not mc and not rc:
                continue
            if not mc or not rc:
                err += EXT_W * 60
                continue
            err += EXT_W * (abs(mc[0] - rc[0]) + abs(mc[-1] - rc[-1]))
    for k, rv in enumerate(ref):
        c = lo + k
        mv = m.get(c)
        w = COL_W(name, c)
        err += w * (MISS if mv is None else abs(mv - rv))
    hi = lo + len(ref) - 1
    err += STICK * sum(1 for c in m if c < lo or c > hi)
    return err * VIEW_W[name], m


# Outer side outline of the flare above the hem (panel px, measured on the
# reference): front view half-width, side view front (-Y) and back (+Y) edge.
EDGE_FRONT_X = {485: 197, 500: 217, 520: 238, 535: 246, 550: 240, 560: 231}
EDGE_SIDE_F = {400: -116, 450: -122, 480: -133, 500: -142, 520: -153, 540: -163,
               550: -168, 560: -172, 570: -176, 580: -170, 590: -158}
EDGE_SIDE_B = {480: 121, 500: 141, 520: 158, 540: 169, 560: 159}
EDGE_W = 2.0


def edge_error(rows, offs):
    """Outline of the cloth at fixed rows vs the reference edges."""
    need = sorted(set(EDGE_FRONT_X) | set(EDGE_SIDE_F) | set(EDGE_SIDE_B))
    ext = {r: [1e9, -1e9, 1e9, -1e9] for r in need}   # min x, max x, min y, max y
    for i in range(N):
        span = rows[i] - skirt.TOP_ROW
        for r in need:
            t = (r - skirt.TOP_ROW) / span
            if t > 1.0:
                continue
            x, y, _ = skirt.point_px(i, t, rows[i], offs[i])
            e = ext[r]
            e[0], e[1], e[2], e[3] = min(e[0], x), max(e[1], x), min(e[2], y), max(e[3], y)
    err = 0.0
    for r, v in EDGE_FRONT_X.items():
        e = ext[r]
        err += abs(-e[0] - v) + abs(e[1] - v) if e[1] > -1e8 else 2 * v
    for r, v in EDGE_SIDE_F.items():
        e = ext[r]
        err += abs(e[2] - v) if e[2] < 1e8 else abs(v)
    for r, v in EDGE_SIDE_B.items():
        e = ext[r]
        err += abs(e[3] - v) if e[3] > -1e8 else abs(v)
    return EDGE_W * err


def total_error(rows, offs):
    pts = hem_points(rows, offs)
    e = sum(view_error(v, pts)[0] for v in VIEWS)
    e += edge_error(rows, offs)
    e += SMOOTH * sum((offs[i] - offs[(i + 1) % N]) ** 2 for i in range(N))
    e += ROW_SMOOTH * sum((rows[i] - rows[(i + 1) % N]) ** 2 for i in range(N))
    # curvature terms: allow steady slopes, suppress zigzags and spikes
    e += ROW_CURV * sum((rows[i - 1] - 2 * rows[i] + rows[(i + 1) % N]) ** 2 for i in range(N))
    e += OFF_CURV * sum((offs[i - 1] - 2 * offs[i] + offs[(i + 1) % N]) ** 2 for i in range(N))
    return e


def fit(passes=40):
    rows, offs = skirt.initial_hem()
    rows = [round(r) for r in rows]
    best = total_error(rows, offs)
    print('initial error', round(best, 1))
    steps = (12, 6, 2, -2, -6, -12)
    # moves shift a window of consecutive samples, so a lobe edge held up by
    # several neighbours (the envelope is a max) can still move
    windows = (1, 3, 7)
    for p in range(passes):
        improved = 0
        for w in windows:
            for i in range(N):
                idx = [(i + k) % N for k in range(-(w // 2), w // 2 + 1)]
                for arr, rng in ((rows, ROW_RANGE), (offs, OFF_RANGE)):
                    for s in steps:
                        old = [arr[j] for j in idx]
                        for j in idx:
                            arr[j] = min(rng[1], max(rng[0], arr[j] + s))
                        if [arr[j] for j in idx] == old:
                            continue
                        e = total_error(rows, offs)
                        if e < best - 1e-6:
                            best = e
                            improved += 1
                        else:
                            for j, v in zip(idx, old):
                                arr[j] = v
        print(f'pass {p} error {best:.1f} moves {improved}')
        if not improved:
            break
    return rows, offs, best


def report(rows, offs):
    pts = hem_points(rows, offs)
    for v in VIEWS:
        e, m = view_error(v, pts)
        lo, ref = REFS[v]
        worst = sorted(((abs(m[lo + k] - r) if (lo + k) in m else 99, lo + k) for k, r in enumerate(ref)),
                       reverse=True)[:6]
        print(f'{v}: weighted score {e:.0f} ({e / len(ref):.2f}/column)  worst |dz| px by column {worst}')
    print(f'edges: error {edge_error(rows, offs):.0f}')


def write(rows, offs):
    path = os.path.join(ROOT, 'levi', 'parts', 'skirt.py')
    with open(path, encoding='utf-8') as f:
        src = f.read()

    def fmt(name, vals):
        body = ', '.join(str(int(round(v))) for v in vals)
        lines, line = [], ''
        for tok in body.split(' '):
            if len(line) + len(tok) > 92:
                lines.append(line.rstrip())
                line = ''
            line += tok + ' '
        lines.append(line.rstrip())
        return f'{name} = [\n    ' + '\n    '.join(lines) + '\n]'

    for name, vals in (('HEM_ROW', rows), ('HEM_OFF', offs)):
        src, n = re.subn(rf'^{name} = (None|\[[^\]]*\])', fmt(name, vals), src, flags=re.M)
        assert n == 1, name
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(src)
    print('wrote', path)


def main():
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    rows, offs, _ = fit()
    report(rows, offs)
    print('HEM_ROW =', [int(round(v)) for v in rows])
    print('HEM_OFF =', [int(round(v)) for v in offs])
    if '--write' in args:
        write(rows, offs)


if __name__ == '__main__':
    main()
