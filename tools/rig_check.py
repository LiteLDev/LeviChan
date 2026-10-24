"""Structural tests for the MMD rig (levi/rig.py). Exit code 1 on failure.

    blender -b -P tools/rig_check.py -- [--parts body,skirt] [--proxy] [--fixtures]

With no parts in levi/parts the throwaway test meshes from tools/rig_fixtures.py
(and the proxy body) are rigged instead.

Checks: MMD core bones exist with the right parents under a single root; every
vertex of every part mesh is weighted to deform bones only, weights sum to 1,
at most 4 influences; Armature modifier targets the rig and sits before the
Outline hull; leg/toe IK constraints exist and actually reach their targets;
the test pose (tools/rig_pose.py) produces finite geometry without torn or
exploded edges; rigging twice gives identical bones and weights.
"""
import argparse
import hashlib
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

from levi import rig  # noqa: E402
from rig_pose import apply_test_pose, build_scene  # noqa: E402

MAX_STRETCH = 3.0     # posed / rest edge length

CORE_PARENTS = {
    '全ての親': None, 'センター': '全ての親', 'グルーブ': 'センター', '腰': 'グルーブ',
    '上半身': '腰', '上半身2': '上半身', '首': '上半身2', '頭': '首', '両目': '頭', '下半身': '腰',
}
for _t in 'LR':
    CORE_PARENTS.update({
        f'目.{_t}': '頭', f'肩.{_t}': '上半身2', f'腕.{_t}': f'肩.{_t}', f'ひじ.{_t}': f'腕.{_t}',
        f'手首.{_t}': f'ひじ.{_t}', f'親指０.{_t}': f'手首.{_t}', f'親指１.{_t}': f'親指０.{_t}',
        f'親指２.{_t}': f'親指１.{_t}',
        f'足.{_t}': '下半身', f'ひざ.{_t}': f'足.{_t}', f'足首.{_t}': f'ひざ.{_t}', f'つま先.{_t}': f'足首.{_t}',
        f'足ＩＫ.{_t}': '全ての親', f'つま先ＩＫ.{_t}': f'足ＩＫ.{_t}',
    })
    for _f in ('人指', '中指', '薬指', '小指'):
        CORE_PARENTS.update({f'{_f}１.{_t}': f'手首.{_t}', f'{_f}２.{_t}': f'{_f}１.{_t}',
                             f'{_f}３.{_t}': f'{_f}２.{_t}'})
IK_EXPECT = {f'ひざ.{t}': (f'足ＩＫ.{t}', 2) for t in 'LR'}
IK_EXPECT.update({f'足首.{t}': (f'つま先ＩＫ.{t}', 1) for t in 'LR'})


def skinned_meshes(arm):
    return sorted((o for o in bpy.data.objects if o.type == 'MESH' and o.users_collection
                   and o.users_collection[0].name != rig.RIG_COLLECTION), key=lambda o: o.name)


def check_bones(arm, errors):
    bones = arm.data.bones
    for name, parent in CORE_PARENTS.items():
        b = bones.get(name)
        if b is None:
            errors.append(f'missing bone {name}')
            continue
        got = b.parent.name if b.parent else None
        if got != parent:
            errors.append(f'{name}: parent {got} != {parent}')
    roots = [b.name for b in bones if b.parent is None]
    if roots != ['全ての親']:
        errors.append(f'armature roots {roots} (expected only 全ての親)')
    for b in bones:
        if b.length < 1e-4:
            errors.append(f'{b.name}: zero-length bone')
        pb = arm.pose.bones[b.name]
        if not pb.get('mmd_name_j') or not pb.get('mmd_name_e'):
            errors.append(f'{b.name}: missing PMX names')
    jp = [arm.pose.bones[b.name].get('mmd_name_j') for b in bones]
    if len(set(jp)) != len(jp):
        errors.append('duplicate PMX Japanese bone names')


def check_ik(arm, errors):
    for owner, (target, chain) in IK_EXPECT.items():
        pb = arm.pose.bones.get(owner)
        cons = [c for c in pb.constraints if c.type == 'IK'] if pb else []
        if not cons:
            errors.append(f'{owner}: no IK constraint')
            continue
        c = cons[0]
        if c.target != arm or c.subtarget != target or c.chain_count != chain:
            errors.append(f'{owner}: IK -> {c.subtarget} chain {c.chain_count}, expected {target} chain {chain}')
    # IK must actually solve: raise the left foot and see the chain follow
    ik, toe_ik = arm.pose.bones['足ＩＫ.L'], arm.pose.bones['つま先ＩＫ.L']
    m = ik.matrix.copy()
    m.translation += Vector((0.0, -0.10, 0.15))
    ik.matrix = m
    bpy.context.view_layer.update()
    gap_knee = (arm.pose.bones['ひざ.L'].tail - ik.head).length
    gap_toe = (arm.pose.bones['足首.L'].tail - toe_ik.head).length
    print(f'IK reach: knee {gap_knee * 1000:.2f} mm, toe {gap_toe * 1000:.2f} mm')
    if gap_knee > 0.002 or gap_toe > 0.002:
        errors.append(f'IK does not reach target (knee {gap_knee:.4f} m, toe {gap_toe:.4f} m)')
    ik.location = (0, 0, 0)
    bpy.context.view_layer.update()


def check_weights(arm, errors):
    deform = {b.name for b in arm.data.bones if b.use_deform}
    total = 0
    for o in skinned_meshes(arm):
        mods = [m for m in o.modifiers]
        am = [i for i, m in enumerate(mods) if m.type == 'ARMATURE' and m.object == arm]
        if not am:
            errors.append(f'{o.name}: no Armature modifier on the rig')
            continue
        if 'Outline' in o.modifiers and am[0] > list(o.modifiers).index(o.modifiers['Outline']):
            errors.append(f'{o.name}: Armature modifier after Outline')
        names = {vg.index: vg.name for vg in o.vertex_groups}
        bad_groups = [n for n in names.values() if n not in deform and n in arm.data.bones]
        if bad_groups:
            errors.append(f'{o.name}: weights on non-deform bones {bad_groups}')
        unweighted = unnorm = over = 0
        for v in o.data.vertices:
            ws = [g.weight for g in v.groups if g.weight > 0 and names.get(g.group) in deform]
            if not ws:
                unweighted += 1
            elif abs(sum(ws) - 1.0) > 1e-3:
                unnorm += 1
            if len(ws) > rig.MAX_INFLUENCE:
                over += 1
        total += len(o.data.vertices)
        for n, what in ((unweighted, 'unweighted'), (unnorm, 'non-normalized'), (over, f'>{rig.MAX_INFLUENCE} influences')):
            if n:
                errors.append(f'{o.name}: {n} {what} vertices')
    print(f'weights checked on {total} vertices')


def _eval_edges(objs):
    dg = bpy.context.evaluated_depsgraph_get()
    out = {}
    for o in objs:
        me = o.evaluated_get(dg).to_mesh()
        co = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get('co', co)
        ed = np.empty(len(me.edges) * 2, dtype=np.int64)
        me.edges.foreach_get('vertices', ed)
        co, ed = co.reshape(-1, 3), ed.reshape(-1, 2)
        out[o.name] = (co, np.linalg.norm(co[ed[:, 0]] - co[ed[:, 1]], axis=1))
        o.evaluated_get(dg).to_mesh_clear()
    return out


def check_pose(arm, errors):
    objs = skinned_meshes(arm)
    for o in objs:
        if 'Outline' in o.modifiers:
            o.modifiers['Outline'].show_viewport = False
    rest = _eval_edges(objs)
    apply_test_pose(arm)
    posed = _eval_edges(objs)
    worst = (0.0, '')
    for name, (co, ln) in posed.items():
        if not np.isfinite(co).all():
            errors.append(f'{name}: non-finite vertices in pose')
            continue
        r = ln / np.maximum(rest[name][1], 1e-6)
        if len(r) and r.max() > worst[0]:
            worst = (float(r.max()), name)
    print(f'pose: max edge stretch {worst[0]:.2f} ({worst[1]})')
    if worst[0] > MAX_STRETCH:
        errors.append(f'pose tears {worst[1]}: edge stretched x{worst[0]:.2f}')
    for pb in arm.pose.bones:
        pb.matrix_basis.identity()
        for c in pb.constraints:
            c.mute = False
    for o in objs:
        if 'Outline' in o.modifiers:
            o.modifiers['Outline'].show_viewport = True
    bpy.context.view_layer.update()


def fingerprint(arm):
    h = hashlib.sha1()
    for b in arm.data.bones:
        h.update(b.name.encode())
        h.update(np.round(np.array([*b.head_local, *b.tail_local]), 6).tobytes())
    for o in skinned_meshes(arm):
        names = {vg.index: vg.name for vg in o.vertex_groups}
        for v in o.data.vertices:
            for g in sorted(v.groups, key=lambda g: names[g.group]):
                h.update(names[g.group].encode())
                h.update(np.float32(round(g.weight, 5)).tobytes())
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--parts', default='')
    ap.add_argument('--proxy', action='store_true')
    ap.add_argument('--fixtures', action='store_true')
    args = ap.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])

    errors = []
    prints = []
    for attempt in (1, 2):
        arm = build_scene(args.parts, args.proxy, args.fixtures)
        prints.append(fingerprint(arm))
    if prints[0] != prints[1]:
        errors.append('rig not repeatable (bones/weights differ between builds)')
    # rigging the same scene twice must also be stable
    arm = rig.build_rig()
    if fingerprint(arm) != prints[1]:
        errors.append('re-running build_rig on a rigged scene changes the result')

    n_def = sum(1 for b in arm.data.bones if b.use_deform)
    print(f'bones={len(arm.data.bones)} deform={n_def} meshes={len(skinned_meshes(arm))}')
    check_bones(arm, errors)
    check_ik(arm, errors)
    check_weights(arm, errors)
    check_pose(arm, errors)
    if any(not math.isfinite(c) for b in arm.data.bones for c in b.head_local):
        errors.append('non-finite bone position')

    for e in errors:
        print('FAIL', e)
    print('RIG CHECK', 'FAILED' if errors else 'OK')
    sys.exit(1 if errors else 0)


main()
