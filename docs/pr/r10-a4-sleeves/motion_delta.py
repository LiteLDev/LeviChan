"""Sleeve rows of two motion reports (tools/rig_check.py --motion), side by side.

python motion_delta.py <base motion_report.json> <new motion_report.json> [--all]
Per set / pose (or clip) / metric / object: the worst value in each report and its
level (minor / major by motion_check.THRESH). Prints a markdown table of the rows
at minor or worse in either report, the counts, and the new majors."""
import json
import sys

LEVEL = {0: 'ok', 1: 'minor', 2: 'major'}


def level(th, metric, v):
    if metric not in th:
        return 0
    minor, major, way = th[metric][:3]
    if way == 'hi':
        return 2 if v >= major else 1 if v >= minor else 0
    return 2 if v <= major else 1 if v <= minor else 0


def rows(path, everything):
    d = json.load(open(path, encoding='utf-8'))
    th, out = d['thresholds'], {}
    for st, poses in d['results'].items():
        for pose, r in poses.items():
            for row in r.get('rows', []):
                obj = row.get('object') or ''
                if not everything and 'sleeve' not in obj and row.get('part') != 'sleeves':
                    continue
                key = (st, pose, row['metric'], obj)
                lv = level(th, row['metric'], row['value'])
                worse = th.get(row['metric'], [0, 0, 'hi'])[2] == 'hi'
                old = out.get(key)
                if old is None or (row['value'] > old[0] if worse else row['value'] < old[0]):
                    out[key] = (row['value'], lv)
    return out


def main():
    a = [x for x in sys.argv[1:] if not x.startswith('--')]
    everything = '--all' in sys.argv
    base, new = rows(a[0], everything), rows(a[1], everything)
    keys = sorted(set(base) | set(new))
    print('| set | pose | metric | object | main | new |\n|---|---|---|---|---|---|')
    cnt = {'base': [0, 0], 'new': [0, 0]}
    new_major, gone_major = [], []
    for k in keys:
        b, n = base.get(k, (float('nan'), 0)), new.get(k, (float('nan'), 0))
        for tag, x in (('base', b), ('new', n)):
            if x[1]:
                cnt[tag][x[1] - 1] += 1
        if b[1] or n[1]:
            print(f'| {k[0]} | {k[1]} | {k[2]} | {k[3]} | {b[0]:.3f} {LEVEL[b[1]]} | {n[0]:.3f} {LEVEL[n[1]]} |')
        if n[1] == 2 and b[1] < 2:
            new_major.append((k, b, n))
        if b[1] == 2 and n[1] < 2:
            gone_major.append((k, b, n))
    print(f"\nmain: {cnt['base'][1]} major / {cnt['base'][0]} minor; new: {cnt['new'][1]} major / {cnt['new'][0]} minor")
    print('new majors:', [(k, round(b[0], 4), round(n[0], 4)) for k, b, n in new_major] or 'none')
    print('majors gone:', [(k, round(b[0], 4), round(n[0], 4)) for k, b, n in gone_major] or 'none')


main()
