"""motion_cmp.py BASE.json NEW.json [poses] : skirt-family metrics per pose / clip, base vs new.
Worst value per (set, name, part, metric) over objects (and frames), parts skirt / petticoat / bodice
ribbon tails / hair_back, plus cross pairs with skirt."""
import json
import sys

base, new = (json.load(open(p)) for p in sys.argv[1:3])
PARTS = ('skirt', 'petticoat')
WORSE_HIGH = {'stretch', 'flip', 'pen', 'pen_frac', 'cross', 'pop', 'jitter', 'self', 'contact'}
TH = base['thresholds']


def table(d):
    out = {}
    for st, res in d['results'].items():
        if st == 'eyes':
            continue
        for name, v in res.items():
            rows = v.get('rows', []) if isinstance(v, dict) else []
            for r in rows:
                part, obj = r.get('part', ''), r.get('object', '')
                key_part = None
                if part in PARTS:
                    key_part = part
                elif obj.startswith('bodice_ribbon_tails'):
                    key_part = 'tails'
                elif 'skirt' in obj and r['metric'] == 'cross':
                    key_part = obj
                if key_part is None:
                    continue
                m = r['metric']
                if m not in ('stretch', 'compress', 'flip', 'pen', 'pen_frac', 'cross', 'pop', 'jitter'):
                    continue
                k = (st, name, key_part, m)
                val = r['value']
                if k not in out:
                    out[k] = (val, r.get('where', ''), r.get('frame'))
                else:
                    cur = out[k][0]
                    better = val > cur if m in WORSE_HIGH else val < cur
                    if better:
                        out[k] = (val, r.get('where', ''), r.get('frame'))
    return out


def level(m, v):
    if m not in TH:
        return ''
    lo, hi, d = TH[m][0], TH[m][1], TH[m][2]
    if d == 'hi':
        return 'MAJOR' if v >= hi else ('minor' if v >= lo else '')
    return 'MAJOR' if v <= hi else ('minor' if v <= lo else '')


B, N = table(base), table(new)
want = set(sys.argv[3].split(',')) if len(sys.argv) > 3 else None
keys = sorted(set(B) | set(N))
cnt = {'B': {'minor': 0, 'MAJOR': 0}, 'N': {'minor': 0, 'MAJOR': 0}}
lines = []
for k in keys:
    st, name, part, m = k
    b = B.get(k, (float('nan'), '', None))
    n = N.get(k, (float('nan'), '', None))
    lb, ln = level(m, b[0]), level(m, n[0])
    if lb:
        cnt['B'][lb] += 1
    if ln:
        cnt['N'][ln] += 1
    if want and name.split('@')[0] not in want:
        continue
    if not (lb or ln) and abs(b[0] - n[0]) < 0.05 * max(abs(b[0]), 1e-9):
        continue
    lines.append(f'{st:8s} {name:18s} {part:14s} {m:9s} base {b[0]:8.3f} {lb:5s} new {n[0]:8.3f} {ln:5s} ({n[1]} f{n[2]})')
print('\n'.join(lines))
print('skirt-family rows at minor/major: base %d/%d, new %d/%d' % (cnt['B']['minor'], cnt['B']['MAJOR'], cnt['N']['minor'], cnt['N']['MAJOR']))
