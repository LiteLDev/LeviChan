"""How far the skirt drape tables move when the thigh moves by a fraction of a millimetre.

    blender -b out/levi.blend -P tools/drape_perturb.py -- [--out out/drape_perturb] [--procs 8]
            [--variants base,kx+0.1,...] [--set 'NAME=PYEXPR;...']

Builds the rig on the (unrigged) model until rig._skirt_drape is called, keeps its inputs
(the chains, the cloth, the drape's thigh line and the body) and stops there. Then it
rebuilds only the drape with the inputs changed and reports, per change, how far each step
of the solve moved, aligned by call order (the loops are deterministic):
  clear  - _drape_clear's turns (rad) for every (thigh, pitch, chain, tabulated yaw), and how
           many grid steps (DRAPE_RES) the largest change is
  gather - _drape_gather's turns and yaws for every (thigh, pitch)
  driver - the tables the drivers hold (drape_tp0 / tp1 / tn per follow bone, yaw_t0 / t1 /
           lift_t per root, the seat swing) and the PMX shares (_drape_share)
It calls _skirt_drape with the changed hip / knee directly, so it measures the solve, not
DRAPE_THIGH_JOINTS (which keeps the leg bones out of it).

Variants: 'k<axis><+-mm>' the knee joint moved, 'h<axis><+-mm>' the hip, 'p<+-mm>' every thigh
profile radius, 'c<axis><+-mm>' all cloth points. The default set is the knee +-0.05 / 0.1 mm and
the hip +-0.1 mm along x, y, z and the radii +-0.2 mm. --set overrides rig constants first (e.g.
'DRAPE_SOFT=30.0;DRAPE_READOUT=(0.02,4)'). Writes <out>/drape_perturb.json and prints a table.
Light on memory; with --procs N the variants run N at a time (forked).
"""
import json
import math
import multiprocessing as mp
import os
import sys
import time

import bpy  # noqa: F401  (run inside Blender)
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from levi import rig  # noqa: E402

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
OPT = {'--out': os.path.join(ROOT, 'out', 'drape_perturb'), '--procs': '8', '--variants': '', '--set': ''}
while argv:
    k = argv.pop(0)
    OPT[k] = argv.pop(0)
for kv in [s for s in OPT['--set'].split(';') if s.strip()]:
    k, v = kv.split('=', 1)
    setattr(rig, k.strip(), eval(v, vars(rig)))
    print('OVERRIDE', k.strip(), '=', getattr(rig, k.strip()), flush=True)
VARIANTS = [v for v in OPT['--variants'].split(',') if v and v != 'base'] or (
    [f'k{a}{s}{d}' for a in 'xyz' for d in ('0.05', '0.1') for s in '+-']
    + [f'h{a}{s}0.1' for a in 'xyz' for s in '+-'] + ['p+0.2', 'p-0.2'])
AX = {'x': 0, 'y': 1, 'z': 2}


class _Stop(Exception):
    pass


CAP = {}
_orig = rig._skirt_drape


def _grab(chains, pts, cy, hip, knee, body, inner=None):
    CAP.update(chains=[(float(a), [tuple(float(c) for c in j) for j in js]) for a, js in chains], pts=np.asarray(pts),
               cy=float(cy), hip=np.asarray(hip, dtype=float), knee=np.asarray(knee, dtype=float),
               body=np.asarray(body), inner=None if inner is None else np.asarray(inner))
    raise _Stop()


def run(var):
    """(var, {'clear', 'gather', 'psi', 'out'}) for one variant ('base' unchanged)."""
    hip, knee, pts, inner, dp = CAP['hip'].copy(), CAP['knee'].copy(), CAP['pts'], CAP['inner'], 0.0
    if var != 'base':
        if var[0] == 'p':
            dp = float(var[1:]) * 1e-3
        else:
            dv = np.zeros(3)
            dv[AX[var[1]]] = float(var[2:]) * 1e-3
            if var[0] == 'k':
                knee = knee + dv
            elif var[0] == 'h':
                hip = hip + dv
            else:
                pts = pts + dv
                inner = None if inner is None else inner + dv
    rec = {'clear': [], 'gather': [], 'psi': []}
    oc, og, prof0 = rig._drape_clear, rig._drape_gather, rig.DRAPE_THIGH_PROFILE

    def clear(*a, **k):
        r = oc(*a, **k)
        rec['clear'].append(np.asarray(r, dtype=float).copy())
        return r

    def gather(*a, **k):
        r = og(*a, **k)
        rec['gather'].append(np.asarray(r[0], dtype=float).copy())
        rec['psi'].append(np.asarray(r[1], dtype=float).copy())
        return r
    rig._drape_clear, rig._drape_gather = clear, gather
    if dp:
        rig.DRAPE_THIGH_PROFILE = tuple(np.array(prof0) + dp)
    try:
        rec['out'] = _orig([(a, list(js)) for a, js in CAP['chains']], pts, CAP['cy'], hip, knee, CAP['body'],
                           inner=inner)
    finally:
        rig._drape_clear, rig._drape_gather, rig.DRAPE_THIGH_PROFILE = oc, og, prof0
    for k in ('clear', 'gather', 'psi'):
        rec[k] = np.array(rec[k])
    return var, rec


def driver_tables(out):
    """{name: row}: what the drivers hold, plus the PMX shares and the seat swing."""
    T = {}
    for k, d in out.items():
        for i in range(len(d['L'])):
            for t in 'LR':
                tab = np.asarray(d[t][i])
                T[f'{k}/{i}/drape_{t}p0'] = np.maximum(tab, 0.0)
                T[f'{k}/{i}/drape_{t}p1'] = np.maximum(np.asarray(d[t + 'a'][i]), 0.0)
                T[f'{k}/{i}/drape_{t}n'] = np.maximum(-tab, 0.0)
                T[f'{k}/{i}/pmx_{t}'] = np.array([rig._drape_share(d, t, i)])
            if i and 'seat' in d:
                T[f'{k}/{i}/seat'] = np.array([d['seat'][i] - d['seat'][i - 1], d['seat_chair'][i] - d['seat_chair'][i - 1]])
        for t in 'LR':
            T[f'{k}/0/yaw_{t}0'] = np.asarray(d['y' + t])
            T[f'{k}/0/yaw_{t}1'] = np.asarray(d['y' + t + 'a'])
            T[f'{k}/0/lift_{t}'] = np.abs(np.asarray(d[t][0]))
    return T


def compare(base, rec):
    dc = np.abs(base['clear'] - rec['clear'])
    dg = np.abs(base['gather'] - rec['gather'])
    dp = np.abs(base['psi'] - rec['psi'])
    Tb, Tr = driver_tables(base['out']), driver_tables(rec['out'])
    dd = {n: float(np.abs(Tb[n] - Tr[n]).max()) for n in Tb}
    worst = sorted(dd.items(), key=lambda x: -x[1])[:5]
    return {'clear_max': float(dc.max()), 'clear_steps': float(dc.max() / math.radians(rig.DRAPE_RES)),
            'clear_n>0.01': int((dc > 0.01).sum()), 'gather_max': float(max(dg.max(), dp.max())),
            'gather_n>0.01': int(((dg > 0.01).any(-1) | (dp > 0.01)).sum()),
            'tables': len(dd), 'tables_changed': sum(v > 1e-4 for v in dd.values()),
            'tables_n>0.01': sum(v > 0.01 for v in dd.values()), 'table_max': worst[0][1], 'worst': worst}


def main():
    t0 = time.time()
    rig._skirt_drape = _grab
    try:
        rig.build_rig()
    except _Stop:
        pass
    rig._skirt_drape = _orig
    if not CAP:
        sys.exit('drape_perturb: the rig build never reached the skirt drape')
    print('captured the drape inputs (%.0f s); hip %s knee %s' % (time.time() - t0, CAP['hip'], CAP['knee']), flush=True)
    np.seterr(all='ignore')
    vs = ['base'] + VARIANTS
    procs = int(OPT['--procs'])
    if procs > 1:
        with mp.get_context('fork').Pool(procs) as pool:
            res = dict(pool.map(run, vs))
    else:
        res = dict(map(run, vs))
    rep = {'set': OPT['--set'], 'variants': {}}
    print('%-8s %8s %6s %8s %7s %8s %s' % ('variant', 'clear', 'steps', 'gather', 'tables', 'max', 'worst table'))
    for v in VARIANTS:
        r = compare(res['base'], res[v])
        rep['variants'][v] = r
        print('%-8s %8.4f %6.1f %8.4f %3d/%3d %8.4f %s' % (v, r['clear_max'], r['clear_steps'], r['gather_max'],
                                                          r['tables_n>0.01'], r['tables'], r['table_max'], r['worst'][0][0]))
    rep['worst'] = max(r['table_max'] for r in rep['variants'].values())
    os.makedirs(OPT['--out'], exist_ok=True)
    path = os.path.join(OPT['--out'], 'drape_perturb.json')
    json.dump(rep, open(path, 'w'), indent=1)
    print('DRAPE PERTURB worst table change %.4f rad (%.0f s) -> %s' % (rep['worst'], time.time() - t0, path), flush=True)


main()
