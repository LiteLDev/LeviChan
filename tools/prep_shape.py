"""Turn the FBX shape reference into the per-part shape master (round 10).

    blender -b out/levi_plain.blend -P tools/prep_shape.py -- --fbx <path.fbx>
                                     [--faces 400000] [--out assets/shape/levi_shape.npz]

Run on an unrigged full build (`build.py -- --out out/levi_plain.blend`): our
parts label the FBX. Writes assets/shape/levi_shape.npz (see levi/shape.py):

  V      (n, 3) float32  vertices, metres, our frame (faces -Y, Z up, origin
                         between the feet on the ground)
  F      (m, 3) int32    triangles
  label  (m,)   uint8    index into `parts` (the part that owns the face)
  dist   (m,)   float16  distance from the face centre to that part's surface
                         in our build at labelling time (m): a confidence
  parts  (k,)   str      part names, in label order

The FBX is one fused, watertight shell (cloth, hair and skin welded, nothing
under the clothes), so it gives target *surfaces* only. Steps:
  1. Normalise: scale to spec.HEIGHT, centre between the feet.
  2. Align to our skeleton: a global y offset (lower legs) and a turn of each
     arm about spec shoulder_joint so its hand lands on our hand (ARM_BLEND
     fades the turn in past the shoulder).
  3. Decimate (collapse) to --faces triangles.
  4. Label each face by the nearest object of our build; where the sheet's
     colour region (ref/<view>_regions.png, faces seen in an ortho view) rules
     that object out, take the nearest object whose palette allows it. Then
     smooth (crease-aware ICM) and merge patches with smooth borders into the
     label around them (merge_smooth_patches).
`--sheet DIR` renders the labels in six views for checking.
"""
import argparse
import math
import os
import sys

import bpy
import bmesh
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from levi import regions, spec  # noqa: E402

PARTS = ('body', 'head', 'hair_front', 'hair_back', 'accessories', 'bodice',
         'skirt', 'petticoat', 'sleeves', 'shoes')
# Our hand centroid (body mesh beyond x = 0.30, left side) on the round-9 build:
# the arm turn aims the FBX hand here.
OUR_HAND = (0.3458, -0.0108, 0.7242)
HAND_X = 0.30
ARM_BLEND = (0.13, 0.22)     # |x| over which the arm turn fades in (m)
LEG_Z = (0.30, 0.46)         # lower-leg band used for the y offset (below the petticoat)
LABEL_SMOOTH = 8           # ICM passes
LABEL_SIGMA = 0.005        # m of extra distance worth one unit of score
LABEL_LAMBDA = 0.6         # score per smoothly joined neighbour of a label
LABEL_CREASE = 0.35        # rad: dihedral angle at which a neighbour counts e^-1
LABEL_SHEET_BONUS = 3.0    # score for the label the sheet colour check chose
PATCH_SMOOTH = 0.75        # mean crease weight along a patch border above which it is merged
PATCH_MAX_SHARE = 0.2      # ... if smaller than this share of its label
PATCH_PASSES = 4
PATCH_SPLIT = 0.5          # crease weight below which an edge splits a patch
PATCH_LABEL_BORDER = 0.5   # share of a patch border that must be other labels
PATCH_DIST = 0.015         # m: mean extra distance to the new part allowed
PATCH_CONFIRMED = 0.3      # ... unless this share of it is confirmed by the sheet colour
# Sheet colour check: a face seen in an ortho view, inside a region of the sheet
# (the same region REGION_PAD px all round), may only belong to an object whose
# palette keys map to that region; otherwise it goes to the nearest object that
# does, if one lies within REGION_REACH.
VIEW_DIR = {'front': (0, -1, 0), 'side': (1, 0, 0), 'back': (0, 1, 0)}   # toward the camera
REGION_PAD = 3
REGION_REACH = 0.05


def mesh_arrays(obj):
    dg = bpy.context.evaluated_depsgraph_get()
    e = obj.evaluated_get(dg)
    me = e.to_mesh()
    me.calc_loop_triangles()
    v = np.empty(len(me.vertices) * 3, np.float64)
    me.vertices.foreach_get('co', v)
    t = np.empty(len(me.loop_triangles) * 3, np.int64)
    me.loop_triangles.foreach_get('vertices', t)
    M = np.array(obj.matrix_world)
    v = v.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]
    e.to_mesh_clear()
    return v, t.reshape(-1, 3)


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def rot_between(a, b):
    a = Vector(a).normalized()
    b = Vector(b).normalized()
    return a.rotation_difference(b)


def import_fbx(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=path, use_image_search=False)
    new = [o for o in bpy.data.objects if o not in before and o.type == 'MESH']
    if len(new) != 1:
        raise SystemExit(f'expected one mesh in {path}, got {len(new)}')
    return new[0]


def normalise(V):
    V = V - [0, 0, V[:, 2].min()]
    V *= spec.HEIGHT / V[:, 2].max()
    f = V[V[:, 2] < 0.03]
    V[:, :2] -= [(f[:, 0].max() + f[:, 0].min()) / 2, (f[:, 1].max() + f[:, 1].min()) / 2]
    return V


def leg_y(V):
    s = V[(V[:, 2] > LEG_Z[0]) & (V[:, 2] < LEG_Z[1]) & (np.abs(V[:, 0]) < 0.15)]
    return float(np.median(s[:, 1]))


def align(V, body):
    """Global y offset from the lower legs, then each arm turned about the shoulder.
    The head needs no shift: the upper face (z 1.30-1.34) meets ours; below it the
    two faces differ in shape (our nose stands ~3 cm further out), which the head
    part decides."""
    dy = leg_y(body) - leg_y(V)
    V = V + [0, dy, 0]
    print(f'ALIGN y offset {dy * 100:+.2f} cm (lower legs)')
    for side in (1, -1):
        sj = np.array(spec.L['shoulder_joint'], float) * [side, 1, 1]
        h = V[V[:, 0] * side > HAND_X]
        src = h.mean(0) - sj
        dst = np.array(OUR_HAND) * [side, 1, 1] - sj
        q = rot_between(src, dst)
        R = np.array(q.to_matrix())
        w = smoothstep(ARM_BLEND[0], ARM_BLEND[1], V[:, 0] * side)[:, None]
        turned = (V - sj) @ R.T + sj
        # blend by slerping the rotation angle, not the positions
        axis, ang = q.to_axis_angle()
        out = V.copy()
        m = w[:, 0] > 0
        for wv in np.unique(np.round(w[m, 0], 3)):
            sel = m & (np.round(w[:, 0], 3) == wv)
            Rw = np.array(Matrix.Rotation(ang * wv, 3, axis))
            out[sel] = (V[sel] - sj) @ Rw.T + sj
        V = out
        print(f'ALIGN arm {"L" if side > 0 else "R"} turn {math.degrees(ang):.2f} deg '
              f'(hand moved {np.linalg.norm(turned[V[:, 0] * side > HAND_X].mean(0) - h.mean(0)) * 100:.1f} cm)')
    return V


def decimate(V, F, faces):
    me = bpy.data.meshes.new('shape')
    me.from_pydata(V.tolist(), [], F.tolist())
    ob = bpy.data.objects.new('shape', me)
    bpy.context.collection.objects.link(ob)
    if len(F) > faces:
        m = ob.modifiers.new('d', 'DECIMATE')
        m.ratio = faces / len(F)
        m.use_collapse_triangulate = True
    V2, F2 = mesh_arrays(ob)
    bpy.data.objects.remove(ob)
    return V2, F2


def object_regions(o):
    """Sheet regions an object may show: its materials' palette keys (and gradient ends)."""
    out = set()
    for m in o.data.materials:
        if m is None or m.get('is_outline'):
            continue
        for k in (m.get('toon_key'), m.get('toon_gradient')):
            r = regions.REGION_OF_KEY.get(k)
            if r:
                out.add(regions.LABEL[r])
    return out


def object_trees():
    """[(object name, part index, allowed region labels, BVH)] for every visible part mesh."""
    objs = []
    for j, name in enumerate(PARTS):
        col = bpy.data.collections.get(name)
        if col is None:
            raise SystemExit(f'part collection {name} missing: run on a full unrigged build')
        for o in col.all_objects:
            if o.type != 'MESH' or o.hide_render:
                continue
            v, t = mesh_arrays(o)
            if not len(t):
                continue
            objs.append((o.name, j, object_regions(o), BVHTree.FromPolygons(v.tolist(), t.tolist())))
    return objs


def face_neighbours(F):
    e = np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]])
    fid = np.tile(np.arange(len(F)), 3)
    e.sort(1)
    key = e[:, 0] * (F.max() + 1) + e[:, 1]
    order = np.argsort(key, kind='stable')
    k, f = key[order], fid[order]
    same = k[1:] == k[:-1]
    a, b = f[:-1][same], f[1:][same]
    return np.concatenate([a, b]), np.concatenate([b, a])


def load_labels(path):
    im = bpy.data.images.load(path)
    im.colorspace_settings.name = 'sRGB'
    w, h = im.size
    a = np.empty(w * h * 4, np.float32)
    im.pixels.foreach_get(a)
    bpy.data.images.remove(im)
    return regions.decode(a.reshape(h, w, 4)[::-1, :, :3])


def sheet_regions(V, F):
    """(m, n_regions + 2) votes: per face, the sheet region under it in each ortho view
    where the face is visible and the region is the same REGION_PAD px all round."""
    C = V[F].mean(1)
    fbx = BVHTree.FromPolygons(V.tolist(), F.tolist())
    votes = np.zeros((len(F), regions.UNKNOWN + 1), np.int32)
    for view in spec.VIEWS:
        lab = load_labels(os.path.join(ROOT, 'ref', f'{view}_regions.png'))
        d = Vector(VIEW_DIR[view])
        h, w = lab.shape
        for i, c in enumerate(C):
            col, row = spec.panel_px(view, c)
            col, row = int(round(col)), int(round(row))
            if not (REGION_PAD <= col < w - REGION_PAD and REGION_PAD <= row < h - REGION_PAD):
                continue
            r = lab[row, col]
            if r in (regions.BG, regions.UNKNOWN):
                continue
            ring = lab[row - REGION_PAD:row + REGION_PAD + 1:REGION_PAD, col - REGION_PAD:col + REGION_PAD + 1:REGION_PAD]
            if (ring != r).any():
                continue
            if fbx.ray_cast(Vector(c) + d * 1e-4, d)[0] is not None:
                continue      # hidden in this view
            votes[i, r] += 1
    return votes


def components(lab, src, dst, w):
    """Connected patches of equal label over the face adjacency (min-id propagation),
    split along folds (crease weight below PATCH_SPLIT): a smooth patch of cloth that
    touches a raised ribbon of the same label is judged on its own border."""
    same = (lab[src] == lab[dst]) & (w > PATCH_SPLIT)
    s, d = src[same], dst[same]
    comp = np.arange(len(lab))
    while True:
        new = comp.copy()
        np.minimum.at(new, s, comp[d])
        new = new[new]                    # pointer jumping
        if (new == comp).all():
            return comp
        comp = new


def merge_smooth_patches(lab, src, dst, w, D, confirmed):
    """A patch (split along folds) that is an artefact of where our overlay lay
    takes the label bordering it most. It must be:
      - bordered by other labels for at least PATCH_LABEL_BORDER of its border,
        over smooth surface (mean crease weight above PATCH_SMOOTH);
      - smaller than PATCH_MAX_SHARE of its label;
      - about as close to the new part as to its own in our build (mean extra
        distance under PATCH_DIST), so a real part is never swallowed.
      - not mostly confirmed by the sheet colour (PATCH_CONFIRMED; `confirmed`
        holds the part the colour check confirmed per face, or -1).
    Real part borders (hems, the neckline, ribbon and lock edges) are folds."""
    for it in range(PATCH_PASSES):
        comp = components(lab, src, dst, w)
        border = lab[src] != lab[dst]
        cs = comp[src][border]
        n = np.bincount(cs, minlength=len(lab)).astype(np.float64)
        ws = np.bincount(cs, weights=w[border], minlength=len(lab))
        n_all = np.bincount(comp[src][comp[src] != comp[dst]], minlength=len(lab))
        size = np.bincount(comp, minlength=len(lab))
        total = np.bincount(lab, minlength=len(PARTS))
        smooth = (n > 0) & (ws / np.maximum(n, 1) > PATCH_SMOOTH) & (n >= PATCH_LABEL_BORDER * n_all)
        small = size < PATCH_MAX_SHARE * total[lab[np.arange(len(lab))]]
        # the neighbouring label with the most (crease-weighted) border
        nb = np.zeros((len(lab), len(PARTS)))
        np.add.at(nb, (cs, lab[dst][border]), w[border])
        target = nb.argmax(1)
        extra = D[np.arange(len(lab)), target[comp]] - D[np.arange(len(lab)), lab]
        mean_extra = np.bincount(comp, weights=extra, minlength=len(lab)) / np.maximum(size, 1)
        conf = np.bincount(comp, weights=(confirmed == lab), minlength=len(lab)) / np.maximum(size, 1)
        cand = np.nonzero(smooth & small & (size > 0) & (mean_extra < PATCH_DIST) & (conf < PATCH_CONFIRMED))[0]
        if not len(cand):
            break
        move = np.zeros(len(lab), bool)
        move[cand] = True
        m = move[comp]
        print(f'PATCHES pass {it}: merging {len(cand)} smooth-bordered patches ({int(m.sum())} faces)')
        lab = np.where(m, target[comp], lab)
    return lab


def label(V, F, objs):
    """Nearest object of our build, overruled where the sheet's colour region says the
    face cannot belong to it (a skin face under our bodice is bodice on the sheet)."""
    C = V[F].mean(1)
    D = np.empty((len(F), len(objs)), np.float32)
    for k, (_, _, _, t) in enumerate(objs):
        D[:, k] = [t.find_nearest(c)[3] for c in C]
    part_of = np.array([j for _, j, _, _ in objs])
    allowed = np.zeros((regions.UNKNOWN + 1, len(objs)), bool)
    for k, (_, _, regs, _) in enumerate(objs):
        for r in regs:
            allowed[r, k] = True
    votes = sheet_regions(V, F)
    best = D.argmin(1)
    r = votes.argmax(1)
    voted = votes.max(1) > 0
    bad = voted & ~allowed[r, best]
    Dm = np.where(allowed[r], D, np.inf)
    alt = Dm.argmin(1)
    fix = bad & (Dm[np.arange(len(F)), alt] < REGION_REACH)
    best = np.where(fix, alt, best)
    print(f'REGIONS faces seen {int(voted.sum())}, relabelled by the sheet {int(fix.sum())}, '
          f'contradicting with nothing in reach {int((bad & ~fix).sum())}')
    # part-level distances for the smoothing below
    D = np.stack([D[:, part_of == j].min(1) if (part_of == j).any() else np.full(len(F), np.inf, np.float32)
                  for j in range(len(PARTS))], 1)
    lab = part_of[best]
    # Crease-aware smoothing (iterated conditional modes): each face scores every
    # part by how much farther that part is than the nearest (in LABEL_SIGMA) and
    # by its neighbours' labels, each neighbour weighted by how smoothly the FBX
    # surface continues across their shared edge. Labels then change across folds
    # and seams, and a patch of smooth cloth our overlay happens to lie on (a
    # ribbon tail, a lock end on the skirt) joins the cloth around it.
    data = -(D - D.min(1, keepdims=True)) / LABEL_SIGMA
    data[np.arange(len(F)), lab] += np.where(fix, LABEL_SHEET_BONUS, 0.0)
    src, dst = face_neighbours(F)
    N = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    N /= np.linalg.norm(N, axis=1, keepdims=True) + 1e-12
    ang = np.arccos(np.clip((N[src] * N[dst]).sum(1), -1, 1))
    w = np.exp(-(ang / LABEL_CREASE) ** 2)
    for _ in range(LABEL_SMOOTH):
        score = data.copy()
        np.add.at(score, (src, lab[dst]), LABEL_LAMBDA * w)
        new = score.argmax(1)
        if (new == lab).all():
            break
        lab = new
    # the label the sheet colour confirmed per face (-1: none)
    confirmed = np.where(voted & allowed[r, best], part_of[best], -1)
    lab = merge_smooth_patches(lab, src, dst, w, D, confirmed)
    dist = D[np.arange(len(F)), lab]
    return lab.astype(np.uint8), dist.astype(np.float16)


LABEL_RGB = {
    'body': (0.95, 0.75, 0.65), 'head': (1.0, 0.55, 0.45), 'hair_front': (0.55, 0.85, 1.0),
    'hair_back': (0.15, 0.45, 0.95), 'accessories': (0.95, 0.85, 0.1), 'bodice': (0.75, 0.3, 0.9),
    'skirt': (0.3, 0.8, 0.35), 'petticoat': (1.0, 0.4, 0.75), 'sleeves': (0.1, 0.6, 0.55),
    'shoes': (0.35, 0.25, 0.2),
}


def sheet(V, F, lab, out):
    for o in list(bpy.data.objects):
        o.hide_render = True
    me = bpy.data.meshes.new('lab')
    me.from_pydata(V.tolist(), [], F.tolist())
    ob = bpy.data.objects.new('lab', me)
    bpy.context.scene.collection.objects.link(ob)
    for name in PARTS:
        m = bpy.data.materials.new('lab_' + name)
        m.diffuse_color = (*LABEL_RGB[name], 1)
        me.materials.append(m)
    me.polygons.foreach_set('material_index', lab.astype(np.int32))
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_WORKBENCH'
    sc.display.shading.light = 'STUDIO'
    sc.display.shading.color_type = 'MATERIAL'
    sc.render.resolution_x, sc.render.resolution_y = 700, 1000
    sc.render.film_transparent = False
    cam = bpy.data.objects.new('labcam', bpy.data.cameras.new('labcam'))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.type = 'ORTHO'
    cam.data.ortho_scale = 1.6
    os.makedirs(out, exist_ok=True)
    for name, az, el in (('front', 0, 0), ('side', 90, 0), ('back', 180, 0),
                         ('q34_front_left', 35, 10), ('q34_back_right', 215, 10), ('high', 20, 45)):
        a, e = math.radians(az), math.radians(el)
        d = Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e)))
        cam.location = Vector((0, 0, 0.75)) + d * 5
        cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
        sc.render.filepath = os.path.join(out, f'labels_{name}.png')
        bpy.ops.render.render(write_still=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--fbx', required=True)
    ap.add_argument('--faces', type=int, default=400000)
    ap.add_argument('--out', default='assets/shape/levi_shape.npz')
    ap.add_argument('--sheet', default='')
    args = ap.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])

    objs = object_trees()
    body, _ = mesh_arrays(bpy.data.objects['body'])
    src = import_fbx(args.fbx)
    V, F = mesh_arrays(src)
    bpy.data.objects.remove(src)
    print(f'FBX {len(V)} vertices, {len(F)} triangles')
    V = align(normalise(V), body)
    V, F = decimate(V, F, args.faces)
    print(f'DECIMATED {len(F)} triangles')
    lab, dist = label(V, F, objs)
    for j, name in enumerate(PARTS):
        sel = lab == j
        d = dist[sel].astype(np.float32)
        print(f'LABEL {name:12s} faces {int(sel.sum()):7d}  dist p50 {np.median(d) * 1000 if sel.any() else 0:6.1f} mm'
              f'  p90 {np.percentile(d, 90) * 1000 if sel.any() else 0:6.1f} mm')
    out = os.path.join(ROOT, args.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    np.savez_compressed(out, V=V.astype(np.float32), F=F.astype(np.int32), label=lab, dist=dist,
                        parts=np.array(PARTS))
    print('SAVED', out, os.path.getsize(out) // 1024, 'KB')
    if args.sheet:
        sheet(V, F, lab, os.path.join(ROOT, args.sheet))


main()
