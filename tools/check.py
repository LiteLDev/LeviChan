"""Structural tests for the procedural model. Exit code 1 on failure.

    blender -b -P tools/check.py -- [--parts body,skirt]

Checks, per part: build() runs and produces mesh objects, face count within
spec.BUDGET, no NaN/inf coordinates, no zero-area faces, every material is a
toon/outline material, every visible mesh has an outline. Whole model: total
faces <= spec.TOTAL_BUDGET. Builds twice to prove builds are repeatable.
Warnings only (no failure): ornaments seated on another part cutting into it (SEATED).
"""
import argparse
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from levi import builder, common, spec  # noqa: E402

ZERO_AREA = 1e-10
# Ornaments seated on another part's surface: (object-name prefix, palette key of the faces
# that must stay clear of it, the part under them). The host's shape belongs to another part,
# so a cut is a warning: the head flower's petals over hair_front's cheek wisp (its concealed
# stalk, another key, enters the hair on purpose).
SEATED = (('acc_flower_', 'flower', 'hair_front'),)


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


def _evaluated_bmesh(o, keep=None):
    """World-space bmesh of `o` without its outline hull; `keep(material)`: faces kept."""
    import bmesh
    import bpy
    hull = [(m, m.show_viewport) for m in o.modifiers if m.name == 'Outline']
    for m, _ in hull:
        m.show_viewport = False
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    me = bpy.data.meshes.new_from_object(o.evaluated_get(dg), depsgraph=dg)
    for m, v in hull:
        m.show_viewport = v
    me.transform(o.matrix_world)
    bm = bmesh.new()
    bm.from_mesh(me)
    if keep is not None:
        drop = [f for f in bm.faces if not keep(me.materials[f.material_index] if me.materials else None)]
        bmesh.ops.delete(bm, geom=drop, context='FACES')
    bpy.data.meshes.remove(me)
    return bm


def seat_warnings(names):
    """SEATED ornaments whose keyed faces cross the part under them (face pairs)."""
    import bpy
    from mathutils.bvhtree import BVHTree
    out = []
    # object names first: evaluating meshes invalidates a live all_objects iteration
    objs = {n: sorted(o.name for o in bpy.data.collections[n].all_objects if o.type == 'MESH')
            for n in names if bpy.data.collections.get(n)}
    for prefix, key, host in SEATED:
        if host not in objs:
            continue
        for n in sorted(sum(objs.values(), [])):
            if not n.startswith(prefix):
                continue
            bm = _evaluated_bmesh(bpy.data.objects[n], lambda m: m is not None and m.get('toon_key') == key)
            tree = BVHTree.FromBMesh(bm)
            bm.free()
            for h in objs[host]:
                hb = _evaluated_bmesh(bpy.data.objects[h])
                k = len(tree.overlap(BVHTree.FromBMesh(hb)))
                hb.free()
                if k:
                    out.append(f'{n}: {k} {key} face pairs cross {host}/{h}')
    return out


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

    for w in seat_warnings(list(cols)):
        print('WARN', w)

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
