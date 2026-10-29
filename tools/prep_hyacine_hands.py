"""Make assets/hyacine/hands.npz: 风堇's left hand, the body's hands (levi/parts/_body_hand.py).

    blender -b --factory-startup -P tools/prep_hyacine_hands.py -- --pmx <风堇 .pmx> [--out assets/hyacine/hands.npz]

The PMX stays outside the repo (see NOTICE) and is read as data with tools/pmxread.py only.
Deterministic (no randomness, fixed orders); the build reads only the npz. Steps:

1. Materials 肌 (skin) and 指甲 (nails), in our frame: Blender (x, y, z) = MMD (x, z, y) x 0.08,
   triangle winding reversed.
2. Vertices welded by position (rounded to 0.01 mm): the UV-seam duplicates, and the nails, whose
   rims coincide with the skin's fingertip holes, so every fingertip closes.
3. The left hand's loose part (centre x > 0.25 m). The right hand is its exact mirror (checked: the
   tool fails if any right-hand vertex lies more than 0.01 mm from the mirrored left one), so the
   build mirrors the left. Degenerate faces are dropped. One open loop remains, at the forearm end
   (11 vertices, ~2.4 cm before 手首).
4. Triangles recombined into quads (bmesh join_triangles, 40 deg face and shape thresholds).
5. Her weights by bone, with the standard names without the 左 prefix (手首, 親指０/１/２,
   人指１/２/３, 中指.., 薬指.., 小指.., 手捩, 手捩1-3, ひじ); bones outside the arm (the 袖口 cuff
   chain carries a trace) are dropped and the rows renormalised.
6. A finger id per vertex: the finger chain holding the most weight, if it holds at least half
   (1 thumb, 2 index, 3 middle, 4 ring, 5 little), else 0 (palm, wrist).
7. The bone heads of the arm from ひじ to the fingertips (her 人差指先 is stored as 人指先).

npz arrays: pos (N, 3) m; faces (F, 4) int32, -1 pads a triangle; loop (L,) the open loop in
order; weights (N, B) float32 with bones (B,); finger (N,) int8; bone_names (K,) and
bone_head (K, 3) m; meta (json: source, transform, counts).
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
MIRROR_TOL = 1e-5      # m: the right hand must be the left one mirrored within this
JOIN_ANGLE = 40.0      # deg: join_triangles face / shape thresholds
CHAINS = (('親指０', '親指１', '親指２'), ('人指１', '人指２', '人指３'), ('中指１', '中指２', '中指３'),
          ('薬指１', '薬指２', '薬指３'), ('小指１', '小指２', '小指３'))
ARM_BONES = ('ひじ', '手捩1', '手捩2', '手捩3', '手捩', '手首') + sum(CHAINS, ())
TIPS = {'親指先': '親指先', '人差指先': '人指先', '中指先': '中指先', '薬指先': '薬指先', '小指先': '小指先'}


def our_frame(a):
    return np.asarray(a, np.float64)[..., [0, 2, 1]] * SCALE


def islands(n, edges):
    lab = np.arange(n)
    while True:
        a, b = lab[edges[:, 0]], lab[edges[:, 1]]
        if (a == b).all():
            return lab
        m = np.minimum(a, b)
        np.minimum.at(lab, edges[:, 0], m)
        np.minimum.at(lab, edges[:, 1], m)
        while True:
            nl = lab[lab]
            if (nl == lab).all():
                break
            lab = nl


def boundary_loop(faces):
    """The open loop of a triangle list (one loop expected), ordered along the faces' winding."""
    e = np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]])
    key = np.sort(e, axis=1)
    u, inv, cnt = np.unique(key, axis=0, return_inverse=True, return_counts=True)
    b = e[cnt[inv.reshape(-1)] == 1]
    if not len(b):
        return np.zeros(0, np.int64)
    nxt = {int(a): int(c) for a, c in b}
    if len(nxt) != len(b):
        raise RuntimeError('prep_hyacine_hands: the boundary is not a simple loop')
    start = int(b[:, 0].min())
    loop = [start]
    while nxt[loop[-1]] != start:
        loop.append(nxt[loop[-1]])
    if len(loop) != len(b):
        raise RuntimeError(f'prep_hyacine_hands: {len(b)} boundary edges, the loop has {len(loop)}')
    return np.array(loop, np.int64)


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument('--pmx', required=True)
    ap.add_argument('--out', default=os.path.join(os.path.dirname(HERE), 'assets', 'hyacine', 'hands.npz'))
    ap.add_argument('--join-deg', type=float, default=JOIN_ANGLE)
    a = ap.parse_args(argv)
    m = pmxread.read(a.pmx)

    # 1. skin + nails
    o, sel = 0, []
    for mt in m['mats']:
        n = mt['nidx'] // 3
        if mt['name'] in ('肌', '指甲'):
            sel.append(m['faces'][o // 3:o // 3 + n])
        o += mt['nidx']
    if len(sel) != 2:
        raise RuntimeError('prep_hyacine_hands: materials 肌 / 指甲 not found')
    F = np.concatenate(sel)
    vs, inv = np.unique(F, return_inverse=True)
    tri = inv.reshape(-1, 3)[:, ::-1]                      # winding reversed (the axis swap mirrors)
    pos = our_frame(m['pos'][vs])

    # 2. weld by position
    _, first, weld = np.unique(np.round(pos / WELD).astype(np.int64), axis=0, return_index=True,
                               return_inverse=True)
    weld = weld.reshape(-1)
    P = pos[first]
    tri = weld[tri]

    # 3. the left hand
    e = np.concatenate([tri[:, [0, 1]], tri[:, [1, 2]], tri[:, [2, 0]]])
    lab = islands(len(P), e)
    parts = {int(k): P[lab == k].mean(0) for k in np.unique(lab)}
    left = [k for k, c in parts.items() if c[0] > 0.25]
    right = [k for k, c in parts.items() if c[0] < -0.25]
    if len(left) != 1 or len(right) != 1:
        raise RuntimeError(f'prep_hyacine_hands: expected one hand per side, got {len(left)} / {len(right)}')
    hand = lab == left[0]
    R = P[lab == right[0]] * np.array([-1.0, 1.0, 1.0])
    Lh = P[hand]
    gap = max(float(np.min(np.linalg.norm(R - p, axis=1))) for p in Lh)
    if len(R) != len(Lh) or gap > MIRROR_TOL:
        raise RuntimeError(f'prep_hyacine_hands: the right hand is not the left one mirrored ({gap * 1000:.3f} mm)')
    keep = np.nonzero(hand)[0]
    remap = np.full(len(P), -1, np.int64)
    remap[keep] = np.arange(len(keep))
    th = remap[tri[hand[tri[:, 0]]]]
    deg = (th[:, 0] == th[:, 1]) | (th[:, 1] == th[:, 2]) | (th[:, 2] == th[:, 0])
    th = th[~deg]
    V = P[keep]
    area = np.linalg.norm(np.cross(V[th[:, 1]] - V[th[:, 0]], V[th[:, 2]] - V[th[:, 0]]), axis=1) / 2
    th = th[area > 1e-10]
    loop = boundary_loop(th)

    # 4. quads
    bm = bmesh.new()
    bv = [bm.verts.new(tuple(p)) for p in V]
    for f in th:
        bm.faces.new([bv[i] for i in f])
    bm.verts.index_update()
    bm.normal_update()
    r = math.radians(a.join_deg)
    bmesh.ops.join_triangles(bm, faces=bm.faces[:], angle_face_threshold=r, angle_shape_threshold=r)
    faces = np.full((len(bm.faces), 4), -1, np.int32)
    for i, f in enumerate(bm.faces):
        ix = [v.index for v in f.verts]
        faces[i, :len(ix)] = ix
    bm.free()

    # 5. weights by bone
    BL = m['bone_list']
    bn = [b['name'] for b in BL]
    src = vs[first[keep]]                       # an original PMX vertex of each welded one
    wsum = {}
    for j in range(4):
        bi, bw = m['bones'][src, j], m['wts'][src, j]
        for i in np.nonzero((bi >= 0) & (bw > 0))[0]:
            name = bn[bi[i]]
            if name.startswith('左'):
                name = name[1:]
            wsum.setdefault(name, np.zeros(len(keep)))[i] += bw[i]
    dropped = {k: round(float(v.sum()), 3) for k, v in wsum.items() if k not in ARM_BONES}
    bones = [b for b in ARM_BONES if b in wsum]
    Wt = np.stack([wsum[b] for b in bones], 1)
    s = Wt.sum(1, keepdims=True)
    if (s <= 1e-9).any():
        raise RuntimeError('prep_hyacine_hands: a hand vertex has no arm weight')
    Wt = Wt / s

    # 6. finger id
    cs = np.stack([sum((Wt[:, bones.index(b)] for b in ch if b in bones), np.zeros(len(keep)))
                   for ch in CHAINS], 1)
    finger = np.where(cs.max(1) >= 0.5, cs.argmax(1) + 1, 0).astype(np.int8)

    # 7. bone heads
    names, heads = [], []
    for b in BL:
        nm = b['name'][1:] if b['name'].startswith('左') else None
        if nm in ARM_BONES or nm in TIPS:
            names.append(TIPS.get(nm, nm))
            heads.append(our_frame(b['pos']))

    nq = int((faces[:, 3] >= 0).sum())
    meta = {'source': os.path.basename(a.pmx), 'tool': 'tools/prep_hyacine_hands.py',
            'transform': 'Blender (x, y, z) = MMD (x, z, y) * 0.08, triangle winding reversed',
            'material': ['肌', '指甲'], 'side': 'left (the right hand is its mirror)',
            'verts': int(len(V)), 'faces': int(len(faces)), 'quads': nq, 'tris': int(len(faces) - nq),
            'loop': int(len(loop)), 'weld_m': WELD, 'join_deg': a.join_deg, 'dropped_weight': dropped,
            'finger_counts': [int((finger == k).sum()) for k in range(6)]}
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    np.savez_compressed(a.out, pos=V.astype(np.float64), faces=faces, loop=loop.astype(np.int32),
                        weights=Wt.astype(np.float32), bones=np.array(bones), finger=finger,
                        bone_names=np.array(names), bone_head=np.array(heads, np.float64),
                        meta=np.array(json.dumps(meta, ensure_ascii=False)))
    print('PREP hands', json.dumps(meta, ensure_ascii=False))
    print('PREP wrote', a.out, os.path.getsize(a.out), 'bytes')


main()
