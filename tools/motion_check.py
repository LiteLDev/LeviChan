"""Deformation metrics for the complex-motion tests (rig_check.py --extended / --motion).

Not a gate: rig_check's core poses keep the pass/fail exit code. This module measures, for
every extended pose (motion_poses.EXTENDED, optionally the core POSES too) and every frame of
every motion clip (motion_poses.CLIPS), with vectorized numpy on the evaluated meshes:

  stretch / compress  largest / smallest edge length ratio (posed / rest) per object
  flip                faces turned more than 120 deg against their dominant bone's rotation
                      (folded or collapsed skin and cloth)
  pen / pen_frac      clothes and hair newly inside the body (parity rays, winding number where
                      they disagree): depth and share of the object's vertices deeper than PEN_DEPTH
  self / contact      body self-intersection between segments far apart on the rest body, grouped
                      by segment pair, depth winding-confirmed: 'self' for segments passing
                      through each other (thigh into thigh, forearm into chest), 'contact' for
                      neighbours pressing in at a deep bend (calf into thigh, arm into chest side)
  cross               new triangle crossings between cloth / hair layers (hair through sleeves
                      or bodice, skirt through petticoat)
  joint / vol         local collapse at a joint band: median of the skin's distance to the bone
                      axis (posed / rest; a crease squeezes one side, a collapse the whole band)
                      and the band's mean squared radius ratio (local volume); the forearm band
                      also catches a candy-wrapper twist
  twist               forearm / thigh / neck twist angle (information)
  knee / elbow        signed bend (deg); negative = hyperextended
  pop / bone_pop      (clips) one-frame spikes of vertex / bone acceleration beyond both
                      neighbours two frames away (popping, IK flips, driver jumps), mm
  jitter              (clips) the same spike test on edge strain (weight-discontinuity flicker)
  speed               (clips) fastest vertex, m/s (information)
  eye                 eyes through the face or lids for gaze at rig.EYE_LIMIT combined with the
                      eye morphs (まばたき, ウィンク, 笑い...), mm beyond rest

Each metric has (minor, major) thresholds in THRESH; report() writes <out>/motion_report.json
and <out>/report.md (tables + the worst problems ranked, grouped by part and location).
"""
import json
import math
import os
import time

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

import rig_check
import rig_pose
from rig_check import PEN_BODY, PEN_SKIP, _eval_verts as eval_world, _winding as winding  # shared with the gate
PEN_DEPTH = 0.005          # m: penetration counted in pen_frac beyond this depth
PEN_SEARCH = 0.2
MIN_EDGE = 1e-3
MIN_AREA = 1e-8
FLIP_COS = -0.5            # face normal more than 120 deg from its bone-rotated rest normal
SELF_REST = 0.04           # m: crossing body triangles closer than this at rest are neighbours
SELF_NEAR = 0.05           # m: depth search radius around the crossings
SELF_MAX_DEPTH = 0.09      # m: deeper "inside" readings are the far side of a limb, ignored
SELF_CONFIRM = 300         # deepest candidates per segment pair confirmed by winding number
SELF_WINDING = 1.0
POP_FLOOR = 0.0005         # m/frame^2 added to the neighbours in the spike ratio
POP_RATIO = 2.0
JITTER_FLOOR = 0.002
WINDING_MAX = 1500       # candidates per object and frame confirmed by winding number

# metric: (minor, major, 'hi' = larger is worse / 'lo' = smaller is worse, unit)
THRESH = {
    'stretch': (1.6, 2.0, 'hi', 'x'),
    'compress': (0.3, 0.12, 'lo', 'x'),
    'flip': (10, 100, 'hi', 'faces'),
    'pen': (0.01, 0.02, 'hi', 'm'),
    'pen_frac': (0.005, 0.03, 'hi', ''),
    'self': (0.005, 0.015, 'hi', 'm'),
    'contact': (0.03, 0.06, 'hi', 'm'),
    'cross': (40, 400, 'hi', 'pairs'),
    'joint': (0.85, 0.7, 'lo', 'x'),
    'vol': (0.8, 0.65, 'lo', 'x'),
    'knee': (-0.5, -5.0, 'lo', 'deg'),
    'elbow': (-5.0, -15.0, 'lo', 'deg'),
    'pop': (0.002, 0.006, 'hi', 'm'),
    'bone_pop': (0.002, 0.006, 'hi', 'm'),
    'jitter': (0.03, 0.08, 'hi', ''),
    'speed': (12.0, 20.0, 'hi', 'm/s'),
    'eye': (0.0008, 0.0015, 'hi', 'm'),
}
LEVELS = ('ok', 'minor', 'major')

# body segments by bone stem (dominant deform weight); .L/.R kept as suffix
SEGMENT = {
    '上半身': 'chest', '上半身2': 'chest', '下半身': 'pelvis', '首': 'neck', '頭': 'head',
    '肩': 'shoulder', '肩補助': 'shoulder', '腕D': 'upperarm', '腕捩': 'upperarm', '腕': 'upperarm',
    'ひじ補助': 'forearm', 'ひじ': 'forearm', '手捩': 'forearm', '手首': 'hand',
    '足': 'thigh', 'ひざ補助': 'shin', 'ひざ補助2': 'shin', 'ひざ': 'shin', '足首': 'foot', 'つま先': 'foot',
}
ADJACENT = {frozenset(p) for p in (
    ('chest', 'pelvis'), ('chest', 'neck'), ('neck', 'head'), ('chest', 'shoulder'), ('shoulder', 'upperarm'),
    ('chest', 'upperarm'), ('upperarm', 'forearm'), ('forearm', 'hand'), ('pelvis', 'thigh'),
    ('thigh', 'shin'), ('shin', 'foot'))}

# joint bands: (centre bone head, band radius m, allowed dominant bone stems, axis segments
# as (bone whose motion carries it, rest point a, rest point b) with points 'bone.head' /
# 'bone.tail' / 'bone.head+z<m>')
JOINTS = {
    'shoulder': ('腕D', 0.07, ('上半身2', '肩', '肩補助', '腕D', '腕捩'),
                 (('肩', '肩.head', '腕D.head'), ('腕D', '腕D.head', 'ひじ.head'))),
    'elbow': ('ひじ', 0.06, ('腕D', '腕捩', 'ひじ補助', 'ひじ', '手捩'),
              (('腕捩', '腕D.head', 'ひじ.head'), ('ひじ', 'ひじ.head', '手首.head'))),
    'forearm': ('手捩', 0.05, ('ひじ', 'ひじ補助', '手捩', '手首'),
                (('ひじ', 'ひじ.head', '手捩.head'), ('手捩', '手捩.head', '手首.head'))),
    'wrist': ('手首', 0.035, ('手捩', 'ひじ', '手首'),
              (('手捩', '手捩.head', '手首.head'), ('手首', '手首.head', '手首.tail'))),
    'hip': ('足', 0.09, ('下半身', '足'),
            (('下半身', '足.head+z0.12', '足.head'), ('足', '足.head', 'ひざ.head'))),
    'knee': ('ひざ', 0.07, ('足', 'ひざ補助', 'ひざ補助2', 'ひざ'),
             (('足', '足.head', 'ひざ.head'), ('ひざ', 'ひざ.head', '足首.head'))),
    'ankle': ('足首', 0.05, ('ひざ', '足首'),
              (('ひざ', 'ひざ.head', '足首.head'), ('足首', '足首.head', 'つま先.head'))),
    'neck': ('首', 0.07, ('上半身2', '首', '頭'),
             (('上半身2', '上半身2.head', '首.head'), ('首', '首.head', '頭.head'),
              ('頭', '頭.head', '頭.head+z0.08'))),
    'waist': ('上半身', 0.11, ('下半身', '上半身', '上半身2'),
              (('下半身', '下半身.tail', '下半身.head'), ('上半身', '上半身.head', '上半身2.head'))),
}
SIDED_JOINTS = ('shoulder', 'elbow', 'forearm', 'wrist', 'hip', 'knee', 'ankle')
TWISTS = {'forearm': ('ひじ', '手首'), 'thigh': ('下半身', '足'), 'neck': ('上半身2', '頭')}
GAZE = ((0, 0), (10, 0), (-10, 0), (0, 8), (0, -8), (10, 8), (-10, -8), (10, -8), (-10, 8))
EYE_MORPHS = (('まばたき', 1.0), ('まばたき', 0.5), ('ウィンク', 1.0), ('ウィンク右', 1.0), ('笑い', 1.0))
CROSS_GROUPS = {
    'hair': ('hair_back', 'hair_front'),
    'garment': ('bodice', 'sleeves', 'accessories'),
    'skirt': ('skirt',),
    'petticoat': ('petticoat',),
}
CROSS_PAIRS = (('hair', 'garment'), ('hair', 'skirt'), ('skirt', 'petticoat'))


def _stem(name):
    return name.split('.')[0]


def _side(name):
    return '.' + name.split('.')[1] if '.' in name else ''


def _seg(bone):
    s = SEGMENT.get(_stem(bone))
    if s is None and '指' in _stem(bone):
        s = 'hand'
    if s is None:
        return 'other'
    return s + (_side(bone) if s not in ('chest', 'pelvis', 'neck', 'head') else '')


class Model:
    """Rest-state data of the rigged scene, gathered once."""

    def __init__(self, arm, objs):
        self.arm = arm
        self.objs = objs
        self.deform = [b.name for b in arm.data.bones if b.use_deform]
        self.bidx = {n: i for i, n in enumerate(self.deform)}
        self.mw_arm = np.array(arm.matrix_world)
        rig_pose.reset_pose(arm)
        bpy.context.view_layer.update()
        self.info = {}
        for o in objs:
            co = eval_world(o)
            me = o.data
            ed = np.empty(len(me.edges) * 2, dtype=np.int64)
            me.edges.foreach_get('vertices', ed)
            me.calc_loop_triangles()
            tri = np.empty(len(me.loop_triangles) * 3, dtype=np.int64)
            me.loop_triangles.foreach_get('vertices', tri)
            ed, tri = ed.reshape(-1, 2), tri.reshape(-1, 3)
            ok = len(co) == len(me.vertices)
            if not ok:
                print(f'motion_check: {o.name} evaluates to {len(co)} vertices, not {len(me.vertices)}: '
                      'edge / weight metrics skipped')
            dom = self._dominant(o) if ok else np.full(len(co), -1)
            el = np.linalg.norm(co[ed[:, 0]] - co[ed[:, 1]], axis=1) if ok else np.zeros(0)
            n0, area = _tri_normals(co, tri) if ok else (np.zeros((0, 3)), np.zeros(0))
            if not ok:
                ed = np.zeros((0, 2), np.int64)
            keep = el > MIN_EDGE
            self.info[o.name] = dict(
                part=o.users_collection[0].name, rest=co, edges=ed,
                tris=tri if ok else np.zeros((0, 3), np.int64), dom=dom, len0=el, n0=n0, area0=area, ok=ok,
                medges=ed[keep], mlen0=el[keep])
        self.body = [o for o in objs if o.users_collection[0].name in PEN_BODY and self.info[o.name]['ok']]
        self.others = [o for o in objs if o not in self.body and o.users_collection[0].name not in PEN_SKIP]
        self._prep_body()
        self._prep_joints()
        self.pen0 = {}
        bvh = self.body_bvh(self.rest_coords())
        for o in self.others:
            self.pen0[o.name] = inside_depth(bvh, self.info[o.name]['rest']) if bvh else np.zeros(len(self.info[o.name]['rest']))
        self.cross0 = self.cross_sets(self.rest_coords())

    def _dominant(self, o):
        names = {vg.index: vg.name for vg in o.vertex_groups}
        dom = np.full(len(o.data.vertices), -1, dtype=np.int64)
        for v in o.data.vertices:
            best, bw = -1, 0.0
            for g in v.groups:
                i = self.bidx.get(names.get(g.group))
                if i is not None and g.weight > bw:
                    best, bw = i, g.weight
            dom[v.index] = best
        return dom

    def rest_coords(self):
        return {o.name: self.info[o.name]['rest'] for o in self.objs}

    def bone_name(self, i):
        return self.deform[i] if i >= 0 else '?'

    # ---- body: one triangle soup for penetration, self-intersection and joints
    def _prep_body(self):
        tris, offs, doms, rest = [], 0, [], []
        self.body_slices = {}
        for o in self.body:
            inf = self.info[o.name]
            tris.append(inf['tris'] + offs)
            doms.append(inf['dom'])
            rest.append(inf['rest'])
            self.body_slices[o.name] = (offs, offs + len(inf['rest']))
            offs += len(inf['rest'])
        if not tris:
            self.btris = None
            return
        self.btris = np.concatenate(tris)
        self.bdom = np.concatenate(doms)
        self.brest = np.concatenate(rest)
        segs = sorted({_seg(self.bone_name(i)) for i in np.unique(self.bdom)})
        self.seg_names = segs
        sidx = {s: k for k, s in enumerate(segs)}
        self.vseg = np.array([sidx[_seg(self.bone_name(i))] for i in self.bdom])
        self.tseg = self.vseg[self.btris[:, 0]]
        self.tcent0 = self.brest[self.btris].mean(1)
        bvh0 = BVHTree.FromPolygons(self.brest.tolist(), self.btris.tolist())
        self.self0 = {tuple(sorted(p)) for p in bvh0.overlap(bvh0)}

    def body_co(self, coords):
        return np.concatenate([coords[o.name] for o in self.body]) if self.body else None

    def body_bvh(self, coords):
        """(BVHTree, triangles (T, 3, 3), vertices as a list) of the body at `coords`."""
        if self.btris is None:
            return None
        co = self.body_co(coords)
        cl = co.tolist()
        return BVHTree.FromPolygons(cl, self.btris.tolist()), co[self.btris], cl

    def _prep_joints(self):
        arm = self.arm
        self.joints = {}
        if self.btris is None:
            return
        bones = arm.data.bones

        def point(spec):
            base, _, dz = spec.partition('+z')
            bn, attr = base.rsplit('.', 1)
            return bn, attr, float(dz) if dz else 0.0

        for jn, (centre, rad, stems, segs) in JOINTS.items():
            for side in (('.L', '.R') if jn in SIDED_JOINTS else ('',)):
                def full(stem):
                    for cand in (stem + side, stem):
                        if cand in bones:
                            return cand
                    return None
                cb = full(centre)
                if cb is None:
                    continue
                segl = []
                for bn, pa, pb in segs:
                    b = full(bn)
                    pts = []
                    for p in (pa, pb):
                        pbn, attr, dz = point(p)
                        pbone = full(pbn)
                        if b is None or pbone is None:
                            break
                        v = getattr(bones[pbone], attr + '_local') + Vector((0, 0, dz))
                        pts.append(self.mw_arm[:3, :3] @ np.array(v) + self.mw_arm[:3, 3])
                    if b is None or len(pts) < 2 or b not in self.bidx and b not in bones:
                        continue
                    segl.append((b, pts[0], pts[1]))
                if not segl:
                    continue
                c = self.mw_arm[:3, :3] @ np.array(bones[cb].head_local) + self.mw_arm[:3, 3]
                allowed = {self.bidx[n] for n in self.deform if _stem(n) in stems and
                           (not side or _side(n) in (side, ''))}
                near = np.linalg.norm(self.brest - c, axis=1) < rad
                keep = near & np.isin(self.bdom, list(allowed))
                idx = np.nonzero(keep)[0]
                if len(idx) < 8:
                    continue
                r0 = _seg_dist(self.brest[idx], [(a, b) for _, a, b in segl])
                good = r0 > 0.004
                self.joints[jn + side] = dict(idx=idx[good], r0=r0[good], segs=segl)

    def cross_sets(self, coords):
        out = {}
        bv = {}
        for g, cols in CROSS_GROUPS.items():
            vs, ts, off = [], [], 0
            for o in self.objs:
                inf = self.info[o.name]
                if inf['part'] in cols and inf['ok'] and len(inf['tris']):
                    vs.append(coords[o.name])
                    ts.append(inf['tris'] + off)
                    off += len(coords[o.name])
            if ts:
                bv[g] = BVHTree.FromPolygons(np.concatenate(vs).tolist(), np.concatenate(ts).tolist())
        for a, b in CROSS_PAIRS:
            if a in bv and b in bv:
                out[(a, b)] = set(bv[a].overlap(bv[b]))
        return out


def _tri_normals(co, tri):
    c = np.cross(co[tri[:, 1]] - co[tri[:, 0]], co[tri[:, 2]] - co[tri[:, 0]])
    ln = np.linalg.norm(c, axis=1)
    return c / np.maximum(ln, 1e-20)[:, None], 0.5 * ln


def _seg_dist(p, segs):
    """Distance of points p (N, 3) to the nearest of the segments [(a, b)...]."""
    best = np.full(len(p), np.inf)
    for a, b in segs:
        a, b = np.asarray(a), np.asarray(b)
        d = b - a
        t = np.clip(((p - a) @ d) / max(d @ d, 1e-12), 0.0, 1.0)
        best = np.minimum(best, np.linalg.norm(p - (a + t[:, None] * d), axis=1))
    return best


RAY_DIRS = ((1.0, 0.0, 0.0), (0.0, -0.7071, -0.7071))   # parity rays (not up the open neck)


def _parity(bvh, p, d):
    """Number of surface crossings of the ray p + t d (t > 0), mod 2."""
    n, o = 0, Vector(p)
    dv = Vector(d)
    for _ in range(64):
        hit = bvh.ray_cast(o, dv, 3.0)
        if hit[0] is None:
            break
        n += 1
        o = hit[0] + dv * 1e-5
    return n & 1


def inside_depth(body, co, base=None, min_new=0.0):
    """Depth of each point inside the posed body (0 outside). A point the nearest face calls
    inside is confirmed by the crossing parity of two rays, and by the winding number where
    the rays disagree (open borders, grazing hits). With `base` (depths at rest) only points
    more than `min_new` deeper than their base are confirmed; the others keep the
    nearest-face depth capped at base (no new penetration)."""
    bvh, tris = body[0], body[1]
    n = len(co)
    loc = np.zeros((n, 3))
    nrm = np.zeros((n, 3))
    dist = np.full(n, np.inf)
    fn = bvh.find_nearest
    for i, p in enumerate(co.tolist()):
        hit = fn(p, PEN_SEARCH)
        if hit[0] is not None:
            loc[i], nrm[i], dist[i] = hit[0], hit[1], hit[3]
    side_in = (dist < np.inf) & (dist > 1e-5) & (np.einsum('ij,ij->i', co - loc, nrm) < 0)
    out = np.zeros(n)
    if base is not None:
        keep = side_in & (dist > base + min_new)
        quiet = side_in & ~keep
        out[quiet] = np.minimum(dist[quiet], base[quiet])
        side_in = keep
    cand = np.nonzero(side_in)[0]
    if not len(cand):
        return out
    pts = co[cand].tolist()
    par = np.array([[_parity(bvh, p, d) for d in RAY_DIRS] for p in pts])
    inside = par.all(1)
    # rays that disagree, or both even: open border, grazing hit, or a point inside two
    # overlapping volumes (self-intersecting body: even crossings, winding 2) -> winding
    # number, for at most WINDING_MAX of them (the deepest)
    unsure = np.nonzero(~inside)[0]
    if len(unsure) > WINDING_MAX:
        unsure = unsure[np.argsort(-dist[cand[unsure]])[:WINDING_MAX]]
    if len(unsure):
        inside[unsure] = winding(tris, co[cand[unsure]]) > 0.5
    out[cand[inside]] = dist[cand[inside]]
    return out


def bone_mats(model):
    """(B, 4, 4) world skinning matrices (posed @ rest^-1) of the deform bones."""
    arm = model.arm
    mw = model.mw_arm
    inv = np.linalg.inv(mw)
    out = np.empty((len(model.deform), 4, 4))
    for i, n in enumerate(model.deform):
        pb = arm.pose.bones[n]
        out[i] = mw @ np.array(pb.matrix) @ np.array(pb.bone.matrix_local.inverted()) @ inv
    return out


def _signed_bend(u, f, front):
    ang = math.degrees(math.acos(max(-1.0, min(1.0, u.normalized().dot(f.normalized())))))
    return ang if f.dot(front) >= 0 or ang < 2.0 else -ang


def joint_angles(model):
    """{'knee.L': deg, 'elbow.L': deg, ...} signed bends (negative = hyperextended) and
    {'twist.forearm.L': deg...}."""
    arm = model.arm
    pbs = arm.pose.bones
    out = {}
    import rig_check
    for t, v in rig_check.knee_bends(arm).items():
        out[f'knee.{t}'] = v
    for t in 'LR':
        need = (f'腕D.{t}', f'ひじ.{t}', f'手首.{t}', f'腕捩.{t}')
        if not all(n in pbs for n in need):
            continue
        sh, el, wr = (pbs[n].head for n in need[:3])
        up_b = pbs[f'腕捩.{t}']
        rest_up = (up_b.bone.matrix_local.to_3x3().col[1]).normalized()
        front0 = Vector((0, -1, 0)) - rest_up * rest_up.dot(Vector((0, -1, 0)))
        rot = (up_b.matrix.to_3x3() @ up_b.bone.matrix_local.to_3x3().inverted())
        out[f'elbow.{t}'] = _signed_bend(el - sh, wr - el, rot @ front0)
    for name, (pa, pb_) in TWISTS.items():
        for side in (('.L', '.R') if name in ('forearm', 'thigh') else ('',)):
            a, b = pa + (side if pa + side in pbs else ''), pb_ + (side if pb_ + side in pbs else '')
            if a not in pbs or b not in pbs:
                continue
            A, B = pbs[a], pbs[b]
            rel = (A.matrix.to_3x3() @ A.bone.matrix_local.to_3x3().inverted()).inverted() @ \
                (B.matrix.to_3x3() @ B.bone.matrix_local.to_3x3().inverted())
            q = rel.to_quaternion()
            ax = B.bone.matrix_local.to_3x3().col[1].normalized()
            tw = 2 * math.degrees(math.atan2(Vector((q.x, q.y, q.z)).dot(ax), q.w))
            if tw > 180:
                tw -= 360
            if tw < -180:
                tw += 360
            out[f'twist.{name}{side}'] = tw
    return out


class Frame:
    """Metrics of the current pose."""

    def __init__(self, model, pen=True, cross=True):
        self.model = model
        t0 = time.time()
        self.coords = {o.name: eval_world(o) for o in model.objs}
        self.mats = bone_mats(model)
        self.res = {}
        self.body = model.body_bvh(self.coords)
        self._edges()
        if pen:
            self._pen()
        self._self()
        if cross:
            self._cross()
        self._joints()
        self.angles = joint_angles(model)
        for k, v in self.angles.items():
            kind = k.split('.')[0]
            if kind in ('knee', 'elbow'):
                self._worst(kind, v, 'rig', k, k)
        self.seconds = time.time() - t0

    def _worst(self, metric, value, part, obj, where, extra=None):
        """Keep the worst value of `metric` (per object for per-object metrics)."""
        lo = THRESH[metric][2] == 'lo'
        key = (metric, obj)
        cur = self.res.get(key)
        if cur is None or (value < cur['value'] if lo else value > cur['value']):
            self.res[key] = dict(metric=metric, value=float(value), part=part, object=obj, where=where,
                                 **(extra or {}))

    def _edges(self):
        m = self.model
        for o in m.objs:
            inf = m.info[o.name]
            co = self.coords[o.name]
            if not np.isfinite(co).all():
                self._worst('stretch', float('inf'), inf['part'], o.name, 'non-finite vertices')
                continue
            if not inf['ok'] or not len(inf['edges']):
                continue
            ed = inf['edges']
            keep = inf['len0'] > MIN_EDGE
            r = np.linalg.norm(co[ed[keep, 0]] - co[ed[keep, 1]], axis=1) / inf['len0'][keep]
            if not len(r):
                continue
            ek = ed[keep]
            i, j = int(r.argmax()), int(r.argmin())
            self._worst('stretch', r[i], inf['part'], o.name, m.bone_name(inf['dom'][ek[i, 0]]))
            self._worst('compress', r[j], inf['part'], o.name, m.bone_name(inf['dom'][ek[j, 0]]))
            # flipped faces against the dominant bone's rotation
            tri = inf['tris']
            ok = (inf['area0'] > MIN_AREA) & (inf['dom'][tri[:, 0]] >= 0)
            if ok.any():
                n1, _ = _tri_normals(co, tri[ok])
                rot = self.mats[inf['dom'][tri[ok, 0]], :3, :3]
                exp = np.einsum('tij,tj->ti', rot, inf['n0'][ok])
                cosv = np.einsum('ti,ti->t', n1, exp)
                bad = cosv < FLIP_COS
                n = int(bad.sum())
                where = ''
                if n:
                    b, c = np.unique(inf['dom'][tri[ok][bad, 0]], return_counts=True)
                    where = m.bone_name(int(b[c.argmax()]))
                self._worst('flip', n, inf['part'], o.name, where)

    def _pen(self):
        m = self.model
        body = self.body
        if body is None:
            return
        for o in m.others:
            inf = m.info[o.name]
            d = inside_depth(body, self.coords[o.name], m.pen0[o.name], 0.001) - m.pen0[o.name]
            if not len(d):
                continue
            i = int(d.argmax())
            frac = float((d > PEN_DEPTH).sum()) / len(d)
            where = m.bone_name(inf['dom'][i]) if inf['ok'] else ''
            self._worst('pen', max(0.0, d[i]), inf['part'], o.name, where,
                        {'count': int((d > PEN_DEPTH).sum())})
            self._worst('pen_frac', frac, inf['part'], o.name, where)

    def _self(self):
        m = self.model
        if m.btris is None:
            return
        co = m.body_co(self.coords)
        bvh, tris, cl = self.body
        # overlap() lists each crossing as (i, j) and (j, i): one sorted pair each
        pairs = np.array(sorted({tuple(sorted(q)) for q in bvh.overlap(bvh)} - m.self0),
                         dtype=np.int64).reshape(-1, 2)
        if len(pairs):
            far = np.linalg.norm(m.tcent0[pairs[:, 0]] - m.tcent0[pairs[:, 1]], axis=1) > SELF_REST
            pairs = pairs[far]
        groups = {}
        for a, b in pairs.tolist():
            sa, sb = m.tseg[a], m.tseg[b]
            key = (min(sa, sb), max(sa, sb))
            groups.setdefault(key, []).append((a, b))
        self.self_pairs = {}
        for (sa, sb), lst in groups.items():
            na, nb = m.seg_names[sa], m.seg_names[sb]
            if na == nb:
                continue
            depth = self._self_depth(co, cl, sa, sb, np.array(lst), tris)
            label = f'{na} x {nb}'
            self.self_pairs[label] = (len(lst), depth)
            # neighbouring segments (calf against thigh, upper arm against chest) press into
            # each other at a deep bend: 'contact'; others pass through: 'self'
            adj = frozenset((na.split('.')[0], nb.split('.')[0])) in ADJACENT
            self._worst('contact' if adj else 'self', depth, 'body', 'body:' + label, label,
                        {'pairs': len(lst)})

    def _self_depth(self, co, cl, sa, sb, lst, tris):
        """Depth of segment A's skin inside segment B (and B's in A) near the crossing
        triangles: the distance to the other segment's nearest face, for vertices behind
        that face that the winding number of the whole body puts inside a second volume
        (> SELF_WINDING: a skin vertex sits at 0.5 on its own surface)."""
        m = self.model
        if sa == sb:
            return 0.0
        cent = co[m.btris[lst.ravel()]].mean(1)
        best = 0.0
        for s_in, s_of in ((sa, sb), (sb, sa)):
            vi = np.nonzero(m.vseg == s_in)[0]
            if not len(vi):
                continue
            p = co[vi]
            dmin = np.full(len(vi), np.inf)
            for k in range(0, len(cent), 256):
                dmin = np.minimum(dmin, np.linalg.norm(p[:, None] - cent[None, k:k + 256], axis=2).min(1))
            vi = vi[dmin < SELF_NEAR]
            ti = np.nonzero(m.tseg == s_of)[0]
            if not len(vi) or not len(ti):
                continue
            bvh = BVHTree.FromPolygons(cl, m.btris[ti].tolist())
            cand, dist = [], []
            for i, q in zip(vi.tolist(), co[vi].tolist()):
                loc, nrm, _, d = bvh.find_nearest(q, SELF_MAX_DEPTH)
                if loc is not None and (Vector(q) - loc).dot(nrm) < 0 and d > 1e-4:
                    cand.append(i)
                    dist.append(d)
            if not cand:
                continue
            cand, dist = np.array(cand), np.array(dist)
            order = np.argsort(-dist)[:SELF_CONFIRM]
            wn = winding(tris, co[cand[order]])
            ok = dist[order][wn > SELF_WINDING]
            if len(ok):
                best = max(best, float(ok.max()))
        return best

    def _cross(self):
        m = self.model
        now = m.cross_sets(self.coords)
        for k, s in now.items():
            n = len(s - m.cross0.get(k, set()))
            self._worst('cross', n, f'{k[0]}/{k[1]}', f'{k[0]} x {k[1]}', f'{k[0]} x {k[1]}')

    def _joints(self):
        m = self.model
        if not m.joints:
            return
        co = m.body_co(self.coords)
        self.joint_vals = {}
        for jn, j in m.joints.items():
            segs = []
            for b, a, bb in j['segs']:
                M = self.mats[m.bidx[b]] if b in m.bidx else _pose_mat(m, b)
                segs.append((M[:3, :3] @ a + M[:3, 3], M[:3, :3] @ bb + M[:3, 3]))
            r = _seg_dist(co[j['idx']], segs)
            ratio = r / j['r0']
            med = float(np.median(ratio))    # a crease squeezes one side, a collapse all of it
            vol = float((r ** 2).mean() / (j['r0'] ** 2).mean())
            i = j['idx'][int(ratio.argmin())]
            self.joint_vals[jn] = (med, vol)
            self._worst('joint', med, 'body', 'joint:' + jn, jn)
            self._worst('vol', vol, 'body', 'joint:' + jn, jn)

    def rows(self):
        return list(self.res.values())


def _pose_mat(model, name):
    """World skinning matrix of a non-deform bone."""
    pb = model.arm.pose.bones[name]
    mw = model.mw_arm
    return mw @ np.array(pb.matrix) @ np.array(pb.bone.matrix_local.inverted()) @ np.linalg.inv(mw)


def level(metric, value):
    mi, ma, how, _ = THRESH[metric]
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return 0
    if how == 'hi':
        return 2 if value > ma else 1 if value > mi else 0
    return 2 if value < ma else 1 if value < mi else 0


def excess(metric, value):
    """How far past the minor threshold, in units of the minor..major span (ranking)."""
    mi, ma, how, _ = THRESH[metric]
    span = abs(ma - mi) or 1.0
    return ((value - mi) if how == 'hi' else (mi - value)) / span


# ------------------------------------------------------------------ eyes

def eye_check(model):
    """Worst eye poke through the face / lids (mm beyond rest) over GAZE x EYE_MORPHS."""
    import rig_check
    arm = model.arm
    objs = model.objs
    eyes = [o for o in objs if any(g.name.split('.')[0] == '目' for g in o.vertex_groups)]
    cover = [o for o in objs if o.users_collection[0].name == 'head' and o not in eyes
             and ('face' in o.name.lower() or 'lid' in o.name.lower())]
    if not eyes or not cover or '両目' not in arm.pose.bones:
        return []
    keys = {}
    for o in cover:
        if o.data.shape_keys:
            for kb in o.data.shape_keys.key_blocks[1:]:
                keys.setdefault(kb.name, []).append(kb)

    def cover_bvh():
        dg = bpy.context.evaluated_depsgraph_get()
        verts, polys = [], []
        for o in cover:
            me = o.evaluated_get(dg).to_mesh()
            base = len(verts)
            verts += [o.matrix_world @ v.co for v in me.vertices]
            polys += [[base + i for i in p.vertices] for p in me.polygons]
            o.evaluated_get(dg).to_mesh_clear()
        return BVHTree.FromPolygons(verts, polys)

    def piv(o):
        g = next(g for g in o.vertex_groups if g.name.split('.')[0] == '目')
        return arm.matrix_world @ arm.pose.bones[g.name].head

    rig_pose.reset_pose(arm)
    bvh = cover_bvh()
    rest = {o.name: rig_check._poke(bvh, eval_world(o), piv(o)) for o in eyes}
    rows = []
    for morph, val in ((None, 0.0),) + EYE_MORPHS:
        if morph is not None and morph not in keys:
            continue
        for kb in keys.get(morph, []):
            kb.value = val
        bpy.context.view_layer.update()
        bvh = cover_bvh()
        worst = (0.0, '', '')
        for yaw, pitch in GAZE:
            rig_pose.reset_pose(arm)
            rig_pose.turn(arm, '両目', (0, 0, 1), yaw)
            rig_pose.turn(arm, '両目', (1, 0, 0), pitch)
            bpy.context.view_layer.update()
            for o in eyes:
                d = rig_check._poke(bvh, eval_world(o), piv(o)) - rest[o.name]
                if len(d) and d.max() > worst[0]:
                    worst = (float(d.max()), o.name, f'gaze {yaw:+d}/{pitch:+d}')
        for kb in keys.get(morph, []):
            kb.value = 0.0
        # against the open-eyed rest: a closed lid behind the cornea at neutral gaze counts too
        name = 'gaze' if morph is None else f'gaze+{morph}{"" if val == 1.0 else f"={val:g}"}'
        rows.append(dict(name=name, metric='eye', value=worst[0], part='head', object=worst[1] or 'eyes',
                         where=worst[2]))
    rig_pose.reset_pose(arm)
    bpy.context.view_layer.update()
    return rows


# ------------------------------------------------------------------ runs

def run_poses(model, names, log=print):
    """{pose: {'rows': [...], 'joints': {...}, 'angles': {...}, 'self_pairs': {...}}}"""
    out = {}
    for n in names:
        rig_pose.apply_pose(model.arm, n)
        f = Frame(model)
        out[n] = dict(rows=f.rows(), joints=getattr(f, 'joint_vals', {}), angles=f.angles,
                      self_pairs=getattr(f, 'self_pairs', {}), seconds=round(f.seconds, 2))
        log(_line(n, f.rows()) + f'  ({f.seconds:.2f} s)')
    rig_pose.reset_pose(model.arm)
    return out


def run_clip(model, clip, log=print, stride=1):
    """Every frame of motion_poses.CLIPS[clip]: per-frame rows (worst kept with its frame)
    plus the temporal metrics (pop, bone_pop, jitter, speed)."""
    import motion_poses
    arm = model.arm
    frames = motion_poses.clip_frames(clip)
    rig_pose.reset_pose(arm)
    motion_poses.build_clip(arm, clip)
    worst = {}
    per_frame = []
    traj, strain, bones = [], [], []
    pbn = [pb.name for pb in arm.pose.bones if pb.bone.use_deform]
    names = [o.name for o in model.objs if model.info[o.name]['ok']]
    t0 = time.time()
    for fr in range(frames + 1):
        bpy.context.scene.frame_set(fr)
        bpy.context.view_layer.update()
        full = fr % stride == 0 or fr == frames
        f = Frame(model, pen=full, cross=full)
        rows = f.rows()
        per_frame.append(dict(frame=fr, worst=_frame_summary(rows)))
        for r in rows:
            key = (r['metric'], r['object'])
            lo = THRESH[r['metric']][2] == 'lo'
            cur = worst.get(key)
            if cur is None or (r['value'] < cur['value'] if lo else r['value'] > cur['value']):
                worst[key] = dict(r, frame=fr)
        traj.append(np.concatenate([f.coords[n] for n in names]).astype(np.float32))
        strain.append(np.concatenate([
            np.linalg.norm(f.coords[n][model.info[n]['medges'][:, 0]] - f.coords[n][model.info[n]['medges'][:, 1]],
                           axis=1) / model.info[n]['mlen0'] for n in names]).astype(np.float32))
        mw = arm.matrix_world
        bones.append(np.array([[*(mw @ arm.pose.bones[b].head), *(mw @ arm.pose.bones[b].tail)] for b in pbn],
                              dtype=np.float32).reshape(-1, 3))
    secs = time.time() - t0
    motion_poses.clear_clip(arm)
    rig_pose.reset_pose(arm)
    # temporal metrics
    X = np.stack(traj)                     # (F, V, 3)
    vmap, offs = [], 0
    for n in names:
        k = len(model.info[n]['rest'])
        vmap.append((n, offs, offs + k))
        offs += k

    def locate(vi):
        for n, a, b in vmap:
            if a <= vi < b:
                inf = model.info[n]
                return inf['part'], n, model.bone_name(inf['dom'][vi - a])
        return '?', '?', '?'

    temporal = []
    if len(X) >= 7:
        acc = np.linalg.norm(X[2:] - 2 * X[1:-1] + X[:-2], axis=2)       # (F-2, V), frame t+1
        val, t, vi = _spike(acc, POP_FLOOR)
        part, obj, where = locate(vi)
        temporal.append(dict(metric='pop', value=val, part=part, object=obj, where=where, frame=t + 1))
        B = np.stack(bones)
        bacc = np.linalg.norm(B[2:] - 2 * B[1:-1] + B[:-2], axis=2)
        val, t, bi = _spike(bacc, POP_FLOOR)
        temporal.append(dict(metric='bone_pop', value=val, part='rig', object='bones',
                             where=pbn[bi // 2] if bi >= 0 else '', frame=t + 1))
        S = np.stack(strain)
        sacc = np.abs(S[2:] - 2 * S[1:-1] + S[:-2])
        val, t, ei = _spike(sacc, JITTER_FLOOR)
        eobj, ewhere, epart = '?', '?', '?'
        off = 0
        for n in names:
            ne = len(model.info[n]['medges'])
            if off <= ei < off + ne:
                inf = model.info[n]
                eobj, epart = n, inf['part']
                ewhere = model.bone_name(inf['dom'][inf['medges'][ei - off, 0]])
                break
            off += ne
        temporal.append(dict(metric='jitter', value=val, part=epart, object=eobj, where=ewhere, frame=t + 1))
        vel = np.linalg.norm(X[1:] - X[:-1], axis=2) * motion_poses.FPS
        t, vi = np.unravel_index(int(vel.argmax()), vel.shape)
        part, obj, where = locate(vi)
        temporal.append(dict(metric='speed', value=float(vel[t, vi]), part=part, object=obj, where=where,
                             frame=int(t) + 1))
    rows = list(worst.values()) + temporal
    log(_line(clip, rows) + f'  ({frames + 1} frames, {secs:.1f} s)')
    return dict(rows=rows, frames=frames + 1, seconds=round(secs, 1), per_frame=per_frame)


def _spike(a, floor):
    """Largest one-frame spike of a (T, N): a[t] beyond both a[t-2] and a[t+2], where it
    is also POP_RATIO times their larger value (+floor). Returns (excess, t, n)."""
    if len(a) < 5:
        return 0.0, -1, -1
    mid = a[2:-2]
    nb = np.maximum(a[:-4], a[4:])
    ex = mid - nb
    ex[mid < POP_RATIO * (nb + floor)] = 0.0
    t, n = np.unravel_index(int(ex.argmax()), ex.shape)
    return float(max(0.0, ex[t, n])), int(t) + 2, int(n)


def _frame_summary(rows):
    out = {}
    for r in rows:
        m = r['metric']
        lo = THRESH[m][2] == 'lo'
        if m not in out or (r['value'] < out[m] if lo else r['value'] > out[m]):
            out[m] = round(r['value'], 5)
    return out


def _fmt(metric, v):
    if v is None:
        return '-'
    unit = THRESH[metric][3]
    if unit == 'm':
        return f'{v * (1000 if metric in ("pop", "bone_pop", "eye") else 100):.1f}'
    if metric == 'pen_frac':
        return f'{v * 100:.1f}%'
    if unit in ('faces', 'pairs'):
        return f'{int(v)}'
    if unit == 'deg':
        return f'{v:.1f}'
    return f'{v:.2f}'


def _line(name, rows):
    s = _frame_summary(rows)
    bits = []
    for m in ('stretch', 'compress', 'flip', 'pen', 'self', 'contact', 'joint', 'vol', 'knee', 'elbow', 'pop', 'jitter'):
        if m in s:
            mark = ('', '!', '!!')[level(m, s[m])]
            bits.append(f'{m} {_fmt(m, s[m])}{mark}')
    return f'{name:20s} ' + '  '.join(bits)


# ------------------------------------------------------------------ report

COLS = (('stretch', 'stretch'), ('compress', 'compress'), ('flip', 'flip'), ('pen', 'pen cm'),
        ('pen_frac', 'pen %'), ('self', 'self cm'), ('contact', 'contact cm'), ('cross', 'cross'), ('joint', 'joint'), ('vol', 'vol'),
        ('knee', 'knee'), ('elbow', 'elbow'), ('pop', 'pop mm'), ('bone_pop', 'bone pop mm'),
        ('jitter', 'jitter'), ('speed', 'speed m/s'))


def issues(results):
    """Every row at minor or worse, as flat dicts with set / name / level / excess."""
    out = []
    for set_name, items in results.items():
        for name, data in items.items():
            for r in data['rows']:
                lv = level(r['metric'], r['value'])
                if lv:
                    out.append(dict(r, set=set_name, name=name, level=LEVELS[lv],
                                    excess=round(excess(r['metric'], r['value']), 3)))
    out.sort(key=lambda r: (-LEVELS.index(r['level']), -r['excess']))
    return out


def _cell(rows, metric):
    lo = THRESH[metric][2] == 'lo'
    rs = [r for r in rows if r['metric'] == metric]
    if not rs:
        return '-'
    r = min(rs, key=lambda r: r['value']) if lo else max(rs, key=lambda r: r['value'])
    lv = level(metric, r['value'])
    v = _fmt(metric, r['value'])
    tag = '' if not lv else f" **{v}** ({r['where'] or r['object']}{', f' + str(r['frame']) if 'frame' in r else ''})" \
        if lv == 2 else f" *{v}* ({r['where'] or r['object']})"
    return tag.strip() if lv else v


def report(results, out_dir, eye_rows=None, extra=''):
    """Write <out>/motion_report.json and report.md. results: {set: {name: data}}."""
    os.makedirs(out_dir, exist_ok=True)
    if eye_rows:
        results = dict(results)
        results['eyes'] = {r['name']: dict(rows=[r]) for r in eye_rows}
    iss = issues(results)
    with open(os.path.join(out_dir, 'motion_report.json'), 'w', encoding='utf-8') as f:
        json.dump(_jsonable(dict(thresholds={k: list(v) for k, v in THRESH.items()}, results=results,
                                 issues=iss)), f, indent=1, ensure_ascii=False)
    lines = ['# Motion test report', '', extra, '',
             'Thresholds (minor / major): ' + ', '.join(
                 f'{k} {_fmt(k, v[0])}/{_fmt(k, v[1])}' for k, v in THRESH.items()) + '.',
             'Cells: plain = ok, *italic* = minor, **bold** = major (location, frame for clips). '
             'pen/self/contact in cm, pop in mm; joint = median skin radius ratio at the worst joint band, '
             'vol = its mean squared radius ratio; knee/elbow = least signed bend (negative = hyperextended).', '']
    for set_name, items in results.items():
        if set_name == 'eyes':
            continue
        cols = [c for c in COLS if any(r['metric'] == c[0] for d in items.values() for r in d['rows'])]
        lines += [f'## {set_name}', '', '| name | ' + ' | '.join(h for _, h in cols) + ' |',
                  '|---|' + '---|' * len(cols)]
        for name, d in items.items():
            lines.append(f'| {name} | ' + ' | '.join(_cell(d['rows'], m) for m, _ in cols) + ' |')
        lines.append('')
    if eye_rows:
        lines += ['## eyes (gaze at the limits x eye morphs)', '', '| case | poke mm | where |', '|---|---|---|']
        for r in eye_rows:
            lv = LEVELS[level('eye', r['value'])]
            lines.append(f"| {r['name']} | {r['value'] * 1000:.2f} ({lv}) | {r['object']} {r['where']} |")
        lines.append('')
    # grouped problems: (metric, part, location) -> worst + where it happens
    groups = {}
    for r in iss:
        key = (r['metric'], r['part'], r['object'] if r['metric'] in ('self', 'contact', 'joint', 'vol', 'cross') else
               r['where'] or r['object'])
        g = groups.setdefault(key, dict(level=r['level'], excess=r['excess'], worst=r, cases=[]))
        g['cases'].append(f"{r['name']}{'@' + str(r['frame']) if 'frame' in r else ''}")
    ranked = sorted(groups.items(), key=lambda kv: (-LEVELS.index(kv[1]['level']), -kv[1]['excess']))
    lines += ['## Top problems (grouped by metric, part and location)', '',
              '| # | level | metric | part | location | worst | in |', '|---|---|---|---|---|---|---|']
    for k, ((metric, part, loc), g) in enumerate(ranked[:40]):
        w = g['worst']
        cases = ', '.join(dict.fromkeys(g['cases']))
        if len(cases) > 160:
            cases = cases[:157] + '...'
        lines.append(f"| {k + 1} | {g['level']} | {metric} | {part} | {loc} ({w['object']}) | "
                     f"{_fmt(metric, w['value'])} in {w['name']}{'@' + str(w['frame']) if 'frame' in w else ''} | {cases} |")
    by_part = {}
    for r in iss:
        p = by_part.setdefault(r['part'], [0, 0])
        p[0 if r['level'] == 'major' else 1] += 1
    lines += ['', '## Issues by part (major / minor rows)', '', '| part | major | minor |', '|---|---|---|']
    for p, (ma, mi) in sorted(by_part.items(), key=lambda kv: -kv[1][0] * 1000 - kv[1][1]):
        lines.append(f'| {p} | {ma} | {mi} |')
    txt = '\n'.join(lines) + '\n'
    with open(os.path.join(out_dir, 'report.md'), 'w', encoding='utf-8') as f:
        f.write(txt)
    return txt


def _jsonable(x):
    if isinstance(x, dict):
        return {str(k): _jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_jsonable(v) for v in x]
    if isinstance(x, (np.floating, np.integer)):
        x = x.item()
    if isinstance(x, float) and not math.isfinite(x):
        return str(x)
    return x
