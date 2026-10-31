"""python3 object_pops.py A.npz [B.npz ...]: per clip, per hair object, the vertex pop (motion_check's spike test, mm) of each dump. A dump holds poses (clip@frame names), objs, counts and coords (frames x vertices x 3, world)."""
import sys, numpy as np
def spike(a, floor=0.0005, ratio=2.0):
    if len(a) < 5: return 0.0, -1
    mid = a[2:-2]; nb = np.maximum(a[:-4], a[4:]); ex = mid - nb; ex[mid < ratio * (nb + floor)] = 0.0
    t, n = np.unravel_index(int(ex.argmax()), ex.shape); return float(max(0, ex[t, n])) * 1000, int(t) + 3
D = [np.load(p) for p in sys.argv[1:]]
objs = list(D[0]['objs']); counts = D[0]['counts']; off = np.concatenate([[0], np.cumsum(counts)])
poses = list(D[0]['poses'])
clips = sorted({p.split('@')[0] for p in poses if '@' in p})
for c in clips:
    idx = [i for _f, i in sorted((int(p.split('@')[1]), i) for i, p in enumerate(poses) if p.startswith(c + '@'))]
    rows = []
    for k, o in enumerate(objs):
        vals = []
        for d in D:
            X = d['coords'][idx][:, off[k]:off[k + 1]].astype(np.float64)
            acc = np.linalg.norm(X[2:] - 2 * X[1:-1] + X[:-2], axis=2)
            vals.append(spike(acc))
        if max(v for v, _f in vals) >= 2.0:
            rows.append((max(v for v, _f in vals), o, vals))
    rows.sort(reverse=True)
    print(f'{c}: ' + '; '.join(f"{o} " + ' -> '.join(f'{v:.1f}@{f}' for v, f in vals) for _m, o, vals in rows[:8]))
