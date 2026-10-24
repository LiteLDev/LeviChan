"""Structural tests for the procedural model. Exit code 1 on failure.

    blender -b -P tools/check.py -- [--parts body,skirt]

Checks, per part: build() runs and produces mesh objects, face count within
spec.BUDGET, no NaN/inf coordinates, no zero-area faces, every material is a
toon/outline material, every visible mesh has an outline. Whole model: total
faces <= spec.TOTAL_BUDGET. Builds twice to prove builds are repeatable.
"""
import argparse
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from levi import builder, common, spec  # noqa: E402

ZERO_AREA = 1e-10


def check_part(name, col, errors):
    meshes = [o for o in col.all_objects if o.type == 'MESH']
    if not meshes:
        errors.append(f'{name}: no mesh objects')
        return 0
    n = common.face_count(meshes)
    budget = spec.BUDGET.get(name)
    if budget is not None and n > budget:
        errors.append(f'{name}: {n} faces > budget {budget}')
    for o in meshes:
        me = o.data
        if any(not all(math.isfinite(c) for c in v.co) for v in me.vertices):
            errors.append(f'{name}/{o.name}: non-finite vertex')
        zero = sum(1 for p in me.polygons if p.area < ZERO_AREA)
        if zero:
            errors.append(f'{name}/{o.name}: {zero} zero-area faces')
        for m in me.materials:
            if m is None or not (m.name.startswith('toon_') or m.name.startswith('outline_')):
                errors.append(f'{name}/{o.name}: material {m and m.name} is not from levi.toon')
        if not o.hide_render and 'Outline' not in o.modifiers and not o.get('no_outline'):
            errors.append(f'{name}/{o.name}: missing Outline modifier (set obj["no_outline"]=True to opt out)')
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--parts', default='')
    args = ap.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
    names = [p for p in args.parts.split(',') if p] or builder.available_parts()

    errors = []
    unknown = [n for n in names if n not in spec.BUDGET]
    for n in unknown:
        print(f'note: part {n} has no budget entry in spec.BUDGET')

    counts = {}
    for attempt in (1, 2):
        cols = builder.build_all(names)
        counts[attempt] = {n: check_part(n, c, errors if attempt == 1 else []) for n, c in cols.items()}
    if counts[1] != counts[2]:
        errors.append(f'build not repeatable: {counts[1]} vs {counts[2]}')

    total = sum(counts[1].values())
    for n, c in counts[1].items():
        print(f'PART {n:12s} faces={c:6d} budget={spec.BUDGET.get(n, "-")}')
    print(f'TOTAL faces={total} budget={spec.TOTAL_BUDGET}')
    if total > spec.TOTAL_BUDGET:
        errors.append(f'total {total} faces > {spec.TOTAL_BUDGET}')

    for e in errors:
        print('FAIL', e)
    print('CHECK', 'FAILED' if errors else 'OK')
    sys.exit(1 if errors else 0)


main()
