"""Structural tests for the MMD rig (levi/rig.py). Exit code 1 on failure.

    blender -b -P tools/rig_check.py -- [--parts body,skirt] [--proxy] [--fixtures]

With no parts in levi/parts the throwaway test meshes from tools/rig_fixtures.py
(and the proxy body) are rigged instead.

Checks: MMD core bones exist with the right parents under a single root; every
vertex of every part mesh is weighted to deform bones only, weights sum to 1,
at most 4 influences; Armature modifier targets the rig and sits before the
Outline hull; leg/toe IK constraints exist and actually reach their targets;
the standard PMX bone names (センター ... 足ＩＫ, 捩, 親指０) are all there; every pose in
tools/rig_pose.py produces finite geometry without torn or exploded edges, clothes
and hair stay out of the body, and the leg IK never bends a knee backward;
rigging twice gives identical bones and weights.

    --extended   also report (not gate) the motion metrics of tools/motion_check.py on the
                 extended poses (motion_poses.EXTENDED; --report-core adds the core poses)
                 and the eyes at the gaze limits with the eye morphs
    --motion     ... and on every frame of the motion clips (motion_poses.CLIPS; --clips a,b)
    --report DIR where report.md / motion_report.json go (default out/motion)
    --no-core    skip the gated core pose loop (structure, weights, IK and eyes still run)
The exit code only reflects the core checks.
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

from levi import builder, rig  # noqa: E402
import rig_pose  # noqa: E402
from rig_pose import build_scene  # noqa: E402

MAX_STRETCH = 2.0     # posed / rest edge length, any edge of any mesh, any pose
MIN_EDGE = 1e-3       # edges shorter than 1 mm (near-degenerate slivers) are not measured
MAX_PEN = 0.02        # deepest new penetration of clothes / hair into the body (m)
PEN_DEPTH = 0.005     # vertices deeper than this are counted in the report
PEN_SEARCH = 0.2      # find_nearest radius; farther points are treated as outside
PEN_BODY = ('body', '_proxy')                 # the closed skin the others must stay out of
PEN_SKIP = ('head',)    # the head's neck sits inside the body's neck on purpose
WINDING_CHUNK = 2e5     # points x triangles per winding-number batch

CORE_PARENTS = {
    '全ての親': None, 'センター': '全ての親', 'グルーブ': 'センター', '腰': 'グルーブ',
    '上半身': '腰', '上半身2': '上半身', '首': '上半身2', '頭': '首', '両目': '頭', '下半身': '腰',
}
for _t in 'LR':
    CORE_PARENTS.update({
        f'目.{_t}': '頭', f'肩.{_t}': '上半身2', f'ひじ.{_t}': f'腕捩.{_t}',
        # with the shoulder shrug (rig.SHOULDER_SHRUG) 腕 is the keyed input and the arm
        # chain hangs from the deforming 腕D
        f'腕.{_t}': f'肩.{_t}',
        f'腕捩.{_t}': f'腕D.{_t}' if rig.SHOULDER_SHRUG > 1e-4 else f'腕.{_t}', f'手捩.{_t}': f'ひじ.{_t}',
        f'手首.{_t}': f'手捩.{_t}', f'親指０.{_t}': f'手首.{_t}', f'親指１.{_t}': f'親指０.{_t}',
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


def _winding(tris, pts):
    """Generalized winding number of the triangle soup `tris` (T, 3, 3) at `pts` (P, 3):
    ~1 inside a closed surface, ~0 outside, and well defined next to open borders
    (the body's neck opening)."""
    out = np.zeros(len(pts))
    step = max(1, int(WINDING_CHUNK // max(len(tris), 1)))     # bounded memory per chunk
    for s in range(0, len(pts), step):
        a = tris[None, :, 0] - pts[s:s + step, None]
        b = tris[None, :, 1] - pts[s:s + step, None]
        c = tris[None, :, 2] - pts[s:s + step, None]
        la, lb, lc = (np.linalg.norm(v, axis=2) for v in (a, b, c))
        det = np.einsum('ptk,ptk->pt', a, np.cross(b, c))
        den = (la * lb * lc + np.einsum('ptk,ptk->pt', a, b) * lc
               + np.einsum('ptk,ptk->pt', b, c) * la + np.einsum('ptk,ptk->pt', c, a) * lb)
        out[s:s + step] = np.arctan2(det, den).sum(1) / (2 * np.pi)
    return out


def _inside_depth(body, co):
    """Depth (m) of each point inside the body surface, 0 outside. Points the nearest
    face calls inside are confirmed with the winding number."""
    bvh, tris = body
    out = np.zeros(len(co))
    cand, dist = [], []
    for i, p in enumerate(co):
        loc, nrm, _, d = bvh.find_nearest(Vector(p), PEN_SEARCH)
        if loc is not None and d > 1e-5 and (Vector(p) - loc).dot(nrm) < 0.0:
            cand.append(i)
            dist.append(d)
    if cand:
        wn = _winding(tris, co[cand])
        out[np.array(cand)[wn > 0.5]] = np.array(dist)[wn > 0.5]
    return out


def _body_bvh(body_objs):
    """(BVHTree, triangles) of the posed body meshes in world space, or None."""
    from mathutils.bvhtree import BVHTree
    dg = bpy.context.evaluated_depsgraph_get()
    verts, polys = [], []
    for o in body_objs:
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        mw = o.matrix_world
        base = len(verts)
        verts += [mw @ v.co for v in me.vertices]
        polys += [[base + i for i in p.vertices] for p in me.polygons]
        ev.to_mesh_clear()
    if not polys:
        return None
    v = np.array(verts)
    tris = np.array([v[[p[0], p[i], p[i + 1]]] for p in polys for i in range(1, len(p) - 1)])
    return BVHTree.FromPolygons(verts, polys), tris


MIN_KNEE_BEND = -0.5   # deg: a knee may be straight, never bent backward


def knee_bends(arm):
    """{side: forward bend of ひざ about its hinge (local X) in degrees}; negative is a
    hyperextended (reverse-bent) knee."""
    out = {}
    for t in 'LR':
        pb = arm.pose.bones.get(f'ひざ.{t}')
        if pb is None or pb.parent is None:
            continue
        rel = pb.parent.bone.matrix_local.inverted() @ pb.bone.matrix_local
        local = (pb.parent.matrix @ rel).inverted() @ pb.matrix
        out[t] = math.degrees(local.to_euler('XYZ').x)
    return out




GAZE = ((10, 0), (-10, 0), (0, 8), (0, -8), (10, 8), (-10, -8))   # 両目 yaw (her left +) / pitch (up +), deg
# (rig.EYE_LIMIT clamps 目 there in Blender; a VMD gaze beyond it is the animator's call)
MAX_EYE_POKE = 0.0015    # m: an eye may come at most this much further out of the face / lids


def _poke(bvh, co, piv):
    """How far each point lies outside the surface in `bvh`, seen from the eyeball centre
    `piv`: the length of the ray piv -> point beyond its first hit (0 when the ray goes
    through the eye opening)."""
    out = np.zeros(len(co))
    pv = Vector(piv)
    for i, p in enumerate(co):
        d = Vector(p) - pv
        ln = d.length
        if ln < 1e-6:
            continue
        hit = bvh.ray_cast(pv, d / ln, ln)
        if hit[0] is not None:
            out[i] = ln - hit[3]
    return out


def check_eyes(arm, errors):
    """Eyes turned by 両目 (目 appends it fully) in GAZE directions stay behind the face:
    seen from its eyeball centre, no eye vertex comes out through the face skin more than
    MAX_EYE_POKE further than at rest (through the eye opening is fine)."""
    from mathutils.bvhtree import BVHTree
    eyes = [o for o in skinned_meshes(arm) if any(g.name.split('.')[0] == '目' for g in o.vertex_groups)]
    if not eyes or '両目' not in arm.pose.bones:
        print('eyes: no eye geometry on 目')
        return
    cover = [o for o in skinned_meshes(arm) if o.users_collection[0].name == 'head' and o not in eyes
             and ('face' in o.name.lower() or 'lid' in o.name.lower())]
    rig_pose.reset_pose(arm)
    dg = bpy.context.evaluated_depsgraph_get()
    verts, polys = [], []
    for o in cover:
        me = o.evaluated_get(dg).to_mesh()
        base = len(verts)
        verts += [o.matrix_world @ v.co for v in me.vertices]
        polys += [[base + i for i in p.vertices] for p in me.polygons]
        o.evaluated_get(dg).to_mesh_clear()
    if not polys:
        return
    bvh = BVHTree.FromPolygons(verts, polys)    # the head does not move: rest surface is enough
    def pivot(o):
        g = max(o.vertex_groups, key=lambda g: g.name.split('.')[0] == '目')
        return arm.matrix_world @ arm.data.bones[g.name].head_local
    piv = {o.name: pivot(o) for o in eyes}
    rest = {o.name: _poke(bvh, _eval_verts(o), piv[o.name]) for o in eyes}
    worst = (0.0, '')
    for yaw, pitch in GAZE:
        rig_pose.reset_pose(arm)
        rig_pose.turn(arm, '両目', (0, 0, 1), yaw)
        rig_pose.turn(arm, '両目', (1, 0, 0), pitch)
        bpy.context.view_layer.update()
        for o in eyes:
            d = _poke(bvh, _eval_verts(o), piv[o.name]) - rest[o.name]
            if len(d) and d.max() > worst[0]:
                worst = (float(d.max()), f'{o.name} gaze {yaw:+d}/{pitch:+d}')
    rig_pose.reset_pose(arm)
    print(f'eyes: {len(eyes)} objects on 目, worst poke through the face {worst[0] * 1000:.2f} mm {worst[1]}')
    if worst[0] > MAX_EYE_POKE:
        errors.append(f'eyes poke through the face by {worst[0] * 1000:.1f} mm ({worst[1]})')


def check_mmd_names(arm, errors):
    """The PMX names motions bind to (VMD keys are matched by Japanese bone name)."""
    jp = {pb.get('mmd_name_j') for pb in arm.pose.bones}
    missing = [n for n in rig.STANDARD_PMX_BONES if n not in jp]
    print(f'standard PMX bone names: {len(rig.STANDARD_PMX_BONES) - len(missing)}/{len(rig.STANDARD_PMX_BONES)}')
    if missing:
        errors.append(f'standard PMX bone names missing: {missing}')


def pose_metrics(arm, objs, pose, rest, rest_depth):
    """{'stretch': (ratio, obj), 'pen': (depth, obj, count), 'knee': {side: deg}} for one pose."""
    rig_pose.apply_pose(arm, pose)
    knees = knee_bends(arm)
    posed = _eval_edges(objs)
    stretch, bad = (0.0, ''), []
    for name, (co, ln) in posed.items():
        if not np.isfinite(co).all():
            bad.append(name)
            continue
        r0 = rest[name][1]
        keep = r0 > MIN_EDGE
        r = ln[keep] / r0[keep]
        if len(r) and r.max() > stretch[0]:
            stretch = (float(r.max()), name)
    pen = (0.0, '', 0)
    body = [o for o in objs if o.users_collection[0].name in PEN_BODY]
    bvh = _body_bvh(body)
    if bvh is not None:
        for o in objs:
            if o in body or o.users_collection[0].name in PEN_SKIP:
                continue
            d = _inside_depth(bvh, _eval_verts(o))
            d = d - rest_depth[o.name]          # only new or deeper penetration counts
            n = int((d > PEN_DEPTH).sum())
            if len(d) and d.max() > pen[0]:
                pen = (float(d.max()), o.name, n)
    return {'stretch': stretch, 'pen': pen, 'nonfinite': bad, 'knee': knees}


def _eval_verts(o):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = o.evaluated_get(dg)
    me = ev.to_mesh()
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get('co', co)
    ev.to_mesh_clear()
    mw = np.array(o.matrix_world)
    return co.reshape(-1, 3) @ mw[:3, :3].T + mw[:3, 3]


def check_poses(arm, errors, poses):
    objs = skinned_meshes(arm)
    for o in objs:
        if 'Outline' in o.modifiers:
            o.modifiers['Outline'].show_viewport = False
    rig_pose.reset_pose(arm)
    rest = _eval_edges(objs)
    body = [o for o in objs if o.users_collection[0].name in PEN_BODY]
    bvh = _body_bvh(body)
    rest_depth = {o.name: _inside_depth(bvh, _eval_verts(o)) for o in objs
                  if bvh and o not in body and o.users_collection[0].name not in PEN_SKIP}
    print(f'{"pose":16s} {"stretch":>7s}  {"worst object":24s} {"pen cm":>6s} {"verts":>5s}  {"object":24s} {"knee":>6s}')
    for pose in poses:
        m = pose_metrics(arm, objs, pose, rest, rest_depth)
        s, so = m['stretch']
        p, po, pn = m['pen']
        knee = min(m['knee'].values()) if m['knee'] else 0.0
        flag = 'FAIL' if s > MAX_STRETCH or p > MAX_PEN or m['nonfinite'] or knee < MIN_KNEE_BEND else 'ok'
        print(f'{pose:16s} {s:7.2f}  {so:24s} {p * 100:6.2f} {pn:5d}  {po:24s} {knee:6.1f} {flag}')
        if knee < MIN_KNEE_BEND:
            errors.append(f'pose {pose}: knee bent backward ({knee:.1f} deg)')
        for name in m['nonfinite']:
            errors.append(f'{pose}: {name} has non-finite vertices')
        if s > MAX_STRETCH:
            errors.append(f'pose {pose} tears {so}: edge stretched x{s:.2f}')
        if p > MAX_PEN:
            errors.append(f'pose {pose}: {po} sinks {p * 100:.1f} cm into the body ({pn} vertices > {PEN_DEPTH * 1000:.0f} mm)')
    rig_pose.reset_pose(arm)
    for o in objs:
        if 'Outline' in o.modifiers:
            o.modifiers['Outline'].show_viewport = True
    bpy.context.view_layer.update()


def motion_report(arm, args):
    """--extended / --motion: the motion_check metrics, reported against their thresholds
    (no effect on the exit code)."""
    import time
    import motion_check
    import motion_poses
    t0 = time.time()
    objs = skinned_meshes(arm)
    for o in objs:
        if 'Outline' in o.modifiers:
            o.modifiers['Outline'].show_viewport = False
    model = motion_check.Model(arm, objs)
    results, eyes = {}, None
    nv = sum(len(model.info[o.name]['rest']) for o in objs)
    print(f'MOTION model: {len(objs)} meshes, {nv} vertices, {len(model.joints)} joint bands '
          f'({time.time() - t0:.1f} s)')
    if args.extended:
        names = [p for p in args.ext_poses.split(',') if p] or list(motion_poses.EXTENDED)
        if args.report_core:
            results['core'] = motion_check.run_poses(model, list(rig_pose.POSES))
        results['extended'] = motion_check.run_poses(model, names)
        eyes = motion_check.eye_check(model)
        for r in eyes:
            print(f"eyes {r['name']:22s} poke {r['value'] * 1000:.2f} mm {r['object']} {r['where']}")
    if args.motion:
        clips = [c for c in args.clips.split(',') if c] or list(motion_poses.CLIPS)
        results['motion'] = {c: motion_check.run_clip(model, c, stride=max(1, args.pen_stride)) for c in clips}
    out = os.path.join(ROOT, args.report)
    faces = sum(len(o.data.polygons) for o in objs)
    note = (f'Model: {len(objs)} meshes, {nv} vertices, {faces} faces (without outlines). '
            f'Run time {time.time() - t0:.0f} s. Not gated: the exit code of rig_check covers the core poses '
            'only. No cloth or hair physics: chains move only as keyed or driven (MMD simulates them).')
    txt = motion_check.report(results, out, eyes, extra=note)
    print(txt)
    print('MOTION REPORT', os.path.join(out, 'report.md'), f'({time.time() - t0:.0f} s)')
    rig_pose.reset_pose(arm)
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
    ap.add_argument('--poses', default='', help='comma-separated rig_pose.POSES (default: all)')
    ap.add_argument('--quick', action='store_true', help='build once: skip the repeatability checks')
    ap.add_argument('--extended', action='store_true', help='report (not gate) the extended poses')
    ap.add_argument('--motion', action='store_true', help='report (not gate) every frame of the motion clips')
    ap.add_argument('--ext-poses', default='', help='comma-separated extended poses (default: all)')
    ap.add_argument('--clips', default='', help='comma-separated motion clips (default: all)')
    ap.add_argument('--report-core', action='store_true', help='add the core poses to the motion report')
    ap.add_argument('--report', default='out/motion', help='report directory (--extended / --motion)')
    ap.add_argument('--pen-stride', type=int, default=1,
                    help='clips: penetration / layer crossings every Nth frame (other metrics every frame)')
    ap.add_argument('--no-core', action='store_true', help='skip the gated core pose loop')
    args = ap.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])

    if args.extended or args.motion:
        import motion_poses
        bad = [p for p in args.ext_poses.split(',') if p and p not in motion_poses.EXTENDED]
        bad += [c for c in args.clips.split(',') if c and c not in motion_poses.CLIPS]
        if bad:
            ap.error(f'unknown extended pose(s) / clip(s) {bad}')
    errors = []
    prints = []
    for attempt in ((1,) if args.quick else (1, 2)):
        arm = build_scene(args.parts, args.proxy, args.fixtures)
        prints.append(fingerprint(arm))
    if prints[0] != prints[-1]:
        errors.append('rig not repeatable (bones/weights differ between builds)')
    if not args.quick:
        # rigging the same scene twice must also be stable
        arm = rig.build_rig()
        if fingerprint(arm) != prints[1]:
            errors.append('re-running build_rig on a rigged scene changes the result')

    n_def = sum(1 for b in arm.data.bones if b.use_deform)
    print(f'bones={len(arm.data.bones)} deform={n_def} meshes={len(skinned_meshes(arm))}')
    check_bones(arm, errors)
    check_mmd_names(arm, errors)
    check_ik(arm, errors)
    check_weights(arm, errors)
    check_eyes(arm, errors)
    # the throwaway fixtures (tubes, no hands) only make sense for the round-1 test pose
    fixtures = args.fixtures or not (args.parts or builder.available_parts())
    default = ["test"] if fixtures else list(rig_pose.POSES)
    if not args.no_core:
        check_poses(arm, errors, [p for p in args.poses.split(",") if p] or default)
    if args.extended or args.motion:
        motion_report(arm, args)
    if any(not math.isfinite(c) for b in arm.data.bones for c in b.head_local):
        errors.append('non-finite bone position')

    for e in errors:
        print('FAIL', e)
    print('RIG CHECK', 'FAILED' if errors else 'OK')
    sys.exit(1 if errors else 0)


if __name__ == '__main__':
    main()
