"""Make assets/hyacine/legs.npz: 风堇's pelvis and legs (her tights 裤袜), the body's legs
(levi/parts/_body_legs.py).

    blender -b --factory-startup -P tools/prep_hyacine_legs.py -- --pmx <风堇 .pmx> [--out assets/hyacine/legs.npz]

The PMX stays outside the repo (see NOTICE) and is read as data with tools/pmxread.py only.
Deterministic (no randomness, fixed orders); the build reads only the npz. Steps:

1. Material 裤袜 (the tights: pelvis, buttocks, crotch and both legs in one piece, open at the
   waist and at each ankle inside her loafers), in our frame: Blender (x, y, z) = MMD (x, z, y)
   x 0.08, triangle winding reversed.
2. Vertices welded by position (rounded to 0.01 mm: the UV-seam duplicates); degenerate faces
   dropped.
3. Mirror symmetry checked (the tool fails if any vertex lies more than 0.01 mm from a mirrored
   one) and made exact: the right half is rebuilt as the mirror of the left, the midline at x = 0.
4. Triangles recombined into quads (bmesh join_triangles, 40 deg face and shape thresholds) on
   the left half; the right half is its mirror, so both legs have the same topology.
5. Loops (vertex indices in order, the left side for the leg rings, winding along +angle about
   the leg / body axis seen from above): the waist opening (32) and every clean horizontal edge
   loop round the left leg (all quads on both sides, z spread < 6 mm), each with its mean z.
6. Her leg bones (heads, our frame): 下半身, 足D, ひざD, 足首D, つま先 (left), and her
   weights over 下半身 / 足D / ひざD / 足首D (left and right) as a hint.

npz arrays: pos (N, 3) m; faces (F, 4) int32, -1 pads a triangle; mirror (N,) the index of each
vertex's mirror image; waist (32,) the waist loop; rings (R, K) int32 the left-leg loops padded
with -1, ring_z (R,); weights (N, B) float32 with bones (B,); bone_names (K,) / bone_head (K, 3);
meta (json: source, transform, counts).
"""
import argparse
import json
import math
import os
import sys

import bmesh
import bpy  # noqa: F401  (bmesh needs Blender)
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pmxread  # noqa: E402

SCALE = 0.08
WELD = 1e-5            # m: positions rounded to this before welding
MIRROR_TOL = 1e-5      # m: the right half must be the left one mirrored within this
MID_TOL = 1e-6         # m: |x| below this is the midline
JOIN_ANGLE = 40.0      # deg: join_triangles face / shape thresholds
RING_SPREAD = 0.006    # m: a leg loop counts as horizontal if its z spread is below this
LEG_BONES = ('下半身', '足D', 'ひざD', '足首D')
HEADS = ('下半身', '足D', 'ひざD', '足首D', 'つま先', '腰', 'センター')


def our_frame(a):
    return np.asarray(a, np.float64)[..., [0, 2, 1]] * SCALE


def boundary_loops(faces):
    """Open loops of a polygon list (rows padded with -1), each ordered along the faces' winding."""
    e = []
    for f in faces:
        k = [int(v) for v in f if v >= 0]
        e += [(k[i], k[(i + 1) % len(k)]) for i in range(len(k))]
    e = np.array(e)
    key = np.sort(e, axis=1)
    _, inv, cnt = np.unique(key, axis=0, return_inverse=True, return_counts=True)
    b = e[cnt[inv.reshape(-1)] == 1]
    nxt = {int(a): int(c) for a, c in b}
    if len(nxt) != len(b):
        raise RuntimeError('prep_hyacine_legs: the boundary is not made of simple loops')
    loops, seen = [], set()
    for s in sorted(nxt):
        if s in seen:
            continue
        loop = [s]
        while nxt[loop[-1]] != s:
            loop.append(nxt[loop[-1]])
        seen.update(loop)
        loops.append(np.array(loop, np.int64))
    return loops


def leg_rings(bm, P):
    """Clean horizontal edge loops round the left leg: walked across all-quad vertices of
    valence 4 from every edge of the left leg that runs round it."""
    out = {}
    for e in bm.edges:
        a, b = e.verts
        if min(a.co.x, b.co.x) < 0.01 or e.is_boundary:
            continue
        d = (b.co - a.co).normalized()
        if abs(d.z) > 0.35:
            continue
        loop_e, loop_v = [e], [a]
        cur, v, ok = e, b, True
        while v is not a:
            if len(v.link_edges) != 4 or any(len(f.verts) != 4 for f in v.link_faces):
                ok = False
                break
            # the edge across from `cur` at v: shares no face with it
            nf = set(cur.link_faces)
            cand = [x for x in v.link_edges if x is not cur and not (set(x.link_faces) & nf)]
            if len(cand) != 1:
                ok = False
                break
            loop_v.append(v)
            cur = cand[0]
            loop_e.append(cur)
            v = cur.other_vert(v)
            if len(loop_v) > 64:
                ok = False
                break
        if not ok:
            continue
        idx = [x.index for x in loop_v]
        z = P[idx, 2]
        if z.max() - z.min() > RING_SPREAD or P[idx, 0].min() < 0.0:
            continue
        key = tuple(sorted(idx))
        if key in out:
            continue
        # order counter-clockwise seen from above about the loop's centre
        c = P[idx].mean(0)
        ang = np.arctan2(P[idx, 1] - c[1], P[idx, 0] - c[0])
        if np.sum(np.sin(np.diff(np.unwrap(ang)))) < 0:
            idx = idx[::-1]
        start = int(np.argmin(np.abs(np.angle(np.exp(1j * (np.arctan2(P[idx, 1] - c[1], P[idx, 0] - c[0])))))))
        idx = idx[start:] + idx[:start]                     # start at the outer side (+x)
        out[key] = (float(z.mean()), idx)
    rings = sorted(out.values(), key=lambda r: -r[0])
    return rings


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument('--pmx', required=True)
    ap.add_argument('--out', default=os.path.join(os.path.dirname(HERE), 'assets', 'hyacine', 'legs.npz'))
    ap.add_argument('--join-deg', type=float, default=JOIN_ANGLE)
    a = ap.parse_args(argv)
    m = pmxread.read(a.pmx)

    # 1. the tights
    o, sel = 0, []
    for mt in m['mats']:
        n = mt['nidx'] // 3
        if mt['name'] == '裤袜':
            sel.append(m['faces'][o // 3:o // 3 + n])
        o += mt['nidx']
    if len(sel) != 1:
        raise RuntimeError('prep_hyacine_legs: material 裤袜 not found')
    F = sel[0]
    vs, inv = np.unique(F, return_inverse=True)
    tri = inv.reshape(-1, 3)[:, ::-1]                      # winding reversed (the axis swap mirrors)
    pos = our_frame(m['pos'][vs])

    # 2. weld by position, drop degenerate faces
    _, first, weld = np.unique(np.round(pos / WELD).astype(np.int64), axis=0, return_index=True,
                               return_inverse=True)
    weld = weld.reshape(-1)
    P = pos[first].copy()
    tri = weld[tri]
    tri = tri[(tri[:, 0] != tri[:, 1]) & (tri[:, 1] != tri[:, 2]) & (tri[:, 2] != tri[:, 0])]
    area = np.linalg.norm(np.cross(P[tri[:, 1]] - P[tri[:, 0]], P[tri[:, 2]] - P[tri[:, 0]]), axis=1) / 2
    tri = tri[area > 1e-10]

    # 3. exact mirror symmetry
    n = len(P)
    mirror = np.full(n, -1, np.int64)
    Q = P * np.array([-1.0, 1.0, 1.0])
    for i in range(n):
        d = np.linalg.norm(P - Q[i], axis=1)
        j = int(np.argmin(d))
        if d[j] > MIRROR_TOL:
            raise RuntimeError(f'prep_hyacine_legs: vertex {i} has no mirror image ({d[j] * 1000:.3f} mm)')
        mirror[i] = j
    if not (mirror[mirror] == np.arange(n)).all():
        raise RuntimeError('prep_hyacine_legs: the mirror map is not an involution')
    mid = np.abs(P[:, 0]) < MID_TOL
    if not (mid == (mirror == np.arange(n))).all():
        raise RuntimeError('prep_hyacine_legs: midline vertices disagree with the mirror map')
    P[mid, 0] = 0.0
    right = P[:, 0] < 0
    P[right] = P[mirror[right]] * np.array([-1.0, 1.0, 1.0])

    # 4. quads on the left half, mirrored
    cx = P[tri].mean(1)[:, 0]
    if np.any(np.abs(cx) < MID_TOL):
        raise RuntimeError('prep_hyacine_legs: a triangle lies on the midline')
    lt = tri[cx > 0]
    # (her right half splits a few quads along the other diagonal: it is replaced by the left)
    if 2 * len(lt) != len(tri):
        raise RuntimeError('prep_hyacine_legs: the halves have different triangle counts')
    bm = bmesh.new()
    bv = [bm.verts.new(tuple(p)) for p in P]
    for f in lt:
        bm.faces.new([bv[i] for i in f])
    bm.verts.index_update()
    bm.normal_update()
    r = math.radians(a.join_deg)
    bmesh.ops.join_triangles(bm, faces=bm.faces[:], angle_face_threshold=r, angle_shape_threshold=r)
    left = [[v.index for v in f.verts] for f in bm.faces]
    bm.free()
    polys = left + [[int(mirror[i]) for i in reversed(f)] for f in left]
    faces = np.full((len(polys), 4), -1, np.int32)
    for i, f in enumerate(polys):
        faces[i, :len(f)] = f

    # 5. loops
    loops = boundary_loops(faces)
    if sorted(len(lp) for lp in loops) != [22, 22, 32]:
        raise RuntimeError(f'prep_hyacine_legs: expected open loops 32 + 22 + 22, got {[len(lp) for lp in loops]}')
    top = max(loops, key=lambda lp: P[lp, 2].mean())
    c = P[top].mean(0)
    ang = np.arctan2(P[top, 1] - c[1], P[top, 0] - c[0])
    if np.sum(np.sin(np.diff(np.unwrap(ang)))) < 0:
        top = top[::-1]
    ang = np.arctan2(P[top, 1] - c[1], P[top, 0] - c[0])
    top = np.roll(top, -int(np.argmin(np.abs(ang))))
    bm = bmesh.new()
    bv = [bm.verts.new(tuple(p)) for p in P]
    for f in polys:
        bm.faces.new([bv[i] for i in f])
    bm.verts.index_update()
    rings = leg_rings(bm, P)
    bm.free()
    K = max(len(rr[1]) for rr in rings)
    ring_arr = np.full((len(rings), K), -1, np.int32)
    for i, (_, idx) in enumerate(rings):
        ring_arr[i, :len(idx)] = idx
    ring_z = np.array([z for z, _ in rings])

    # 6. weights and bones
    BL = m['bone_list']
    bn = [b['name'] for b in BL]
    src = vs[first]
    cols = [s + b for b in LEG_BONES for s in (('',) if b == '下半身' else ('左', '右'))]
    W = np.zeros((n, len(cols)))
    for j in range(4):
        bi, bw = m['bones'][src, j], m['wts'][src, j]
        for i in np.nonzero((bi >= 0) & (bw > 0))[0]:
            name = bn[bi[i]]
            if name in cols:
                W[i, cols.index(name)] += bw[i]
    names, heads = [], []
    for nm in HEADS:
        full = nm if nm in ('下半身', '腰', 'センター') else '左' + nm
        if full not in bn:
            raise RuntimeError(f'prep_hyacine_legs: bone {full} not found')
        names.append(nm)
        heads.append(our_frame(BL[bn.index(full)]['pos']))

    nq = int((faces[:, 3] >= 0).sum())
    meta = {'source': os.path.basename(a.pmx), 'tool': 'tools/prep_hyacine_legs.py',
            'transform': 'Blender (x, y, z) = MMD (x, z, y) * 0.08, triangle winding reversed',
            'material': '裤袜', 'verts': int(n), 'faces': int(len(faces)), 'quads': nq,
            'tris': int(len(faces) - nq), 'waist': int(len(top)), 'open_loops': [int(len(lp)) for lp in loops],
            'leg_rings': [[round(z, 4), int((ring_arr[i] >= 0).sum())] for i, z in enumerate(ring_z)],
            'weld_m': WELD, 'join_deg': a.join_deg, 'weight_bones': cols}
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    np.savez_compressed(a.out, pos=P.astype(np.float64), faces=faces, mirror=mirror.astype(np.int32),
                        waist=top.astype(np.int32), rings=ring_arr, ring_z=ring_z,
                        weights=W.astype(np.float32), bones=np.array(cols),
                        bone_names=np.array(names), bone_head=np.array(heads, np.float64),
                        meta=np.array(json.dumps(meta, ensure_ascii=False)))
    print('PREP legs', json.dumps(meta, ensure_ascii=False))
    print('PREP wrote', a.out, os.path.getsize(a.out), 'bytes')


main()
