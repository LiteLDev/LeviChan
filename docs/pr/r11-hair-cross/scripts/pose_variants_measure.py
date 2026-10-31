"""Pose variants: hair x garment crossings (pairs, curve mm, top object pairs), hand skin inside
the hair cap and inside the head (cap floor + face), wrist positions.
blender -b levi_rig.blend -P pose_variants_measure.py -- --repo REPO --variants pose_variants.py [--only a,b] [--out x.json]"""
import sys, os, json, runpy
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
argv = sys.argv[sys.argv.index('--') + 1:]
def arg(n, d=None):
    return argv[argv.index(n) + 1] if n in argv else d
REPO = arg('--repo')
sys.path.insert(0, REPO); sys.path.insert(1, os.path.join(REPO, 'tools')); os.chdir(REPO)
import rig_pose, motion_poses as M
from motion_check import tri_cut_length
from rig_check import _winding as winding
V = runpy.run_path(arg('--variants'))['VARIANTS']
only = set(arg('--only', '').split(',')) - {''}
arm = [o for o in bpy.data.objects if o.type == 'ARMATURE'][0]
HAIR = ('hair_back', 'hair_front'); GARM = ('bodice', 'sleeves', 'accessories')
objs = [o for o in bpy.data.objects if o.type == 'MESH' and o.users_collection and o.users_collection[0].name in HAIR + GARM + ('body', 'head')
        and not o.get('levi_hair_collider') and not o.name.startswith('+')]
for o in objs:
    if 'Outline' in o.modifiers: o.modifiers['Outline'].show_viewport = False
def ev(o):
    dg = bpy.context.evaluated_depsgraph_get(); e = o.evaluated_get(dg); me = e.to_mesh()
    co = np.empty(len(me.vertices) * 3); me.vertices.foreach_get('co', co); e.to_mesh_clear()
    mw = np.array(o.matrix_world); return co.reshape(-1, 3) @ mw[:3, :3].T + mw[:3, 3]
tris = {}
for o in objs:
    me = o.data; me.calc_loop_triangles(); t = np.empty(len(me.loop_triangles) * 3, np.int64); me.loop_triangles.foreach_get('vertices', t); tris[o.name] = t.reshape(-1, 3)
H = [o.name for o in objs if o.users_collection[0].name in HAIR]
G = [o.name for o in objs if o.users_collection[0].name in GARM]
names = {vg.index: vg.name for vg in bpy.data.objects['body'].vertex_groups if vg.name in arm.data.bones}
hand = []
for v in bpy.data.objects['body'].data.vertices:
    best, bw = '', 0
    for g in v.groups:
        if g.group in names and g.weight > bw: best, bw = names[g.group], g.weight
    hand.append(best.split('.')[0] in ('手首', '手捩') or best[:2] in ('親指', '人指', '中指', '薬指', '小指'))
hand = np.array(hand)
rig_pose.reset_pose(arm); M.clear_clip(arm); bpy.context.view_layer.update()
co0 = {o.name: ev(o) for o in objs}
bv0 = {n: BVHTree.FromPolygons(co0[n].tolist(), tris[n].tolist()) for n in H + G}
rest = {(h, g): set(bv0[h].overlap(bv0[g])) for h in H for g in G}
cap0 = co0['hair_cap']
print('CAP rest extents x', cap0[:, 0].min().round(3), cap0[:, 0].max().round(3), 'y', cap0[:, 1].min().round(3), cap0[:, 1].max().round(3),
      'z', cap0[:, 2].min().round(3), cap0[:, 2].max().round(3))
out = {}
def measure(tag):
    bpy.context.view_layer.update()
    co = {o.name: ev(o) for o in objs}
    bv = {n: BVHTree.FromPolygons(co[n].tolist(), tris[n].tolist()) for n in H + G}
    tot_p, tot_mm, pairs = 0, 0.0, []
    for h in H:
        for g in G:
            new = np.array(sorted(set(bv[h].overlap(bv[g])) - rest[(h, g)])).reshape(-1, 2)
            if not len(new):
                continue
            mm = float((tri_cut_length(co[h][tris[h][new[:, 0]]], co[g][tris[g][new[:, 1]]]) * 1000).sum())
            tot_p += len(new); tot_mm += mm; pairs.append((mm, len(new), h, g))
    pairs.sort(reverse=True)
    cap, ct = co['hair_cap'], tris['hair_cap']
    P = co['body'][hand]
    wn = winding(cap[ct], P)
    b = BVHTree.FromPolygons(cap.tolist(), ct.tolist())
    d = np.array([b.find_nearest(Vector(q))[3] for q in P[wn > 0.5]]) * 1000
    cuffs = {}
    for g in G:
        if g.startswith('sleeve_cuff'):
            Q = co[g]; w = winding(cap[ct], Q)
            dd = np.array([b.find_nearest(Vector(q))[3] for q in Q[w > 0.5]]) * 1000
            cuffs[g] = (int((w > 0.5).sum()), float(np.percentile(dd, 90)) if len(dd) else 0.0)
    wr = [tuple(round(float(x), 3) for x in arm.matrix_world @ arm.pose.bones[f'手首.{t}'].head) for t in 'LR']
    el = [tuple(round(float(x), 3) for x in arm.matrix_world @ arm.pose.bones[f'ひじ.{t}'].head) for t in 'LR']
    print(f'VARIANT {tag:34s} pairs {tot_p:5d} mm {tot_mm:6.0f} | hand in cap {len(d):5d} p90 {np.percentile(d, 90) if len(d) else 0:5.1f} '
          f'| cuffs in cap {cuffs} | wrists {wr} elbows {el}', flush=True)
    for mm, n, h, g in pairs[:6]:
        print(f'   {h:18s} x {g:20s} {n:5d} pairs {mm:6.0f} mm', flush=True)
    out[tag] = dict(pairs=tot_p, mm=tot_mm, top=[p[:4] for p in pairs[:10]], hand_in_cap=len(d), wrists=wr, elbows=el)
for tag, fn in V:
    if only and tag not in only:
        continue
    rig_pose.reset_pose(arm); M.clear_clip(arm); bpy.context.scene.frame_set(0)
    fn(arm, M, rig_pose)
    measure(tag)
if arg('--out'):
    json.dump(out, open(arg('--out'), 'w'), indent=1)
print('DONE')
