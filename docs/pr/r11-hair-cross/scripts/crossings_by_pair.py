"""blender -b levi_rig.blend -P crossings_by_pair.py -- --repo REPO --poses a,b --out X.json [--mc PATH_TO_motion_check.py]
Per pose, per (hair object, garment/skirt object) pair: new crossing triangle pairs vs rest, the
intersection curve's length (mm, motion_check.tri_cut_length), where (centroid / bbox of the
crossing hair triangles) and how deep: the vertices of either object within 4 cm of the crossing
that changed side of the other object's surface since rest (signed distance by the nearest
face's normal), p90 and max of their distance from it (mm)."""
import sys, os, json, time
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
argv = sys.argv[sys.argv.index('--') + 1:]
def arg(n, d=None):
    return argv[argv.index(n) + 1] if n in argv else d
REPO = arg('--repo'); OUT = arg('--out')
sys.path.insert(0, REPO); sys.path.insert(1, os.path.join(REPO, 'tools')); os.chdir(REPO)
import rig_pose, motion_poses as M
import importlib.util
spec = importlib.util.spec_from_file_location('mc_x', arg('--mc', os.path.join(REPO, 'tools', 'motion_check.py')))
mc = importlib.util.module_from_spec(spec); spec.loader.exec_module(mc)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
G = {'hair': ('hair_back', 'hair_front'), 'garment': ('bodice', 'sleeves', 'accessories'), 'skirt': ('skirt',)}
def grp(o):
    c = o.users_collection[0].name
    for g, cols in G.items():
        if c in cols:
            return g
objs = [o for o in bpy.data.objects if o.type == 'MESH' and not o.get('levi_hair_collider') and not o.name.startswith('+')
        and '_proxy' not in o.name and not o.hide_render and grp(o)]
for o in objs:
    if 'Outline' in o.modifiers:
        o.modifiers['Outline'].show_viewport = False
sc = bpy.context.scene
def coords(o, dg):
    eo = o.evaluated_get(dg); me = eo.to_mesh(); n = len(me.vertices)
    co = np.empty(n * 3); me.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
    mw = np.array(eo.matrix_world); co = co @ mw[:3, :3].T + mw[:3, 3]
    me.calc_loop_triangles()
    t = np.empty(len(me.loop_triangles) * 3, np.int64); me.loop_triangles.foreach_get('vertices', t)
    eo.to_mesh_clear()
    return co, t.reshape(-1, 3)
def state(p):
    if '@' not in p:
        M.clear_clip(arm); sc.frame_set(0)
    if p == 'rest':
        rig_pose.reset_pose(arm); bpy.context.view_layer.update()
    else:
        rig_pose.apply_pose(arm, p)
    dg = bpy.context.evaluated_depsgraph_get()
    return {o.name: coords(o, dg) for o in objs}
def bvhs(S):
    return {n: BVHTree.FromPolygons(c.tolist(), t.tolist()) for n, (c, t) in S.items()}
def overlaps(bv):
    out = {}
    hair = [o.name for o in objs if grp(o) == 'hair']
    oth = [o.name for o in objs if grp(o) in ('garment', 'skirt')]
    for a in hair:
        for b in oth:
            s = bv[a].overlap(bv[b])
            if s:
                out[(a, b)] = set(s)
    return out
def sdist(bv, pts):
    out = np.full(len(pts), np.nan)
    for i, p in enumerate(pts):
        loc, nrm, _f, d = bv.find_nearest(Vector(p))
        if loc is not None:
            out[i] = d if (Vector(p) - loc).dot(nrm) >= 0 else -d
    return out
rest = state('rest'); B0 = bvhs(rest); R0 = overlaps(B0)
res = {}
PL = arg('--poses').split(',')
if 'ALL' in PL:
    PL = [p for p in rig_pose.POSES if p != 'rest'] + list(M.EXTENDED) + [p for p in PL if p != 'ALL']
NODEPTH = '--nodepth' in argv
for p in PL:
    t0 = time.time()
    S = state(p); BV = bvhs(S); O = overlaps(BV)
    rows = []
    for (a, b), s in O.items():
        new = np.array(sorted(s - R0.get((a, b), set())), np.int64).reshape(-1, 2)
        if not len(new):
            continue
        ca, ta = S[a]; cb, tb = S[b]
        A = ca[ta[new[:, 0]]]; Bt = cb[tb[new[:, 1]]]
        ln = mc.tri_cut_length(A, Bt) * 1000.0
        cen = A.mean(1)
        depth = []
        for (x, y) in (() if NODEPTH else ((a, b), (b, a))):      # x's vertices against y's surface
            cx = S[x][0]
            near = np.zeros(len(cx), bool)
            for c in cen[:: max(1, len(cen) // 200)]:
                near |= np.linalg.norm(cx - c, axis=1) < 0.04
            idx = np.nonzero(near)[0]
            if len(idx) > 3000:
                idx = idx[:: len(idx) // 3000 + 1]
            if not len(idx):
                depth.append((0.0, 0.0)); continue
            d1 = sdist(BV[y], cx[idx]); d0 = sdist(B0[y], rest[x][0][idx])
            flip = (np.sign(d1) != np.sign(d0)) & (np.abs(d0) > 0.001) & np.isfinite(d1) & np.isfinite(d0)
            v = np.abs(d1[flip]) * 1000.0
            depth.append((float(np.percentile(v, 90)) if len(v) else 0.0, float(v.max()) if len(v) else 0.0))
        rows.append(dict(hair=a, other=b, n=int(len(new)), mm=float(ln.sum()), c=cen.mean(0).round(4).tolist(),
                         lo=cen.min(0).round(4).tolist(), hi=cen.max(0).round(4).tolist(),
                         depth_other_in_hair=depth[1] if depth else (0, 0), depth_hair_in_other=depth[0] if depth else (0, 0)))
    rows.sort(key=lambda r: -r['mm'])
    res[p] = rows
    print('POSE', p, 'pairs', sum(r['n'] for r in rows), 'mm', round(sum(r['mm'] for r in rows)),
          f'{time.time() - t0:.0f}s', flush=True)
    for r in rows[:10]:
        print(f"    {r['hair']} x {r['other']} n {r['n']} mm {r['mm']:.0f} depth(o in h p90/max) "
              f"{r['depth_other_in_hair'][0]:.0f}/{r['depth_other_in_hair'][1]:.0f} (h in o) "
              f"{r['depth_hair_in_other'][0]:.0f}/{r['depth_hair_in_other'][1]:.0f} c {r['c']} lo {r['lo']} hi {r['hi']}")
json.dump(res, open(OUT, 'w'), indent=1)
print('SAVED', OUT)
