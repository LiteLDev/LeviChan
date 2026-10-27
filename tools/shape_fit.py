"""How closely each part follows the shape master (round 10).

    blender -b out/levi.blend -P tools/shape_fit.py -- [--parts skirt,sleeves] [--out out/shape_fit.txt]

Per part, two distances in mm (p50 / p90 / p99):
  target->ours  points sampled over the master's faces labelled with the part
                (area-weighted, SAMPLES, fixed seed) to the part's surface: does
                the part reach the target shape? This is the number to lower.
  ours->target  the part's vertices to the master's labelled faces, for the
                vertices within NEAR of them (hidden layers, e.g. the body under
                the clothes, are farther and not counted): does the part stay on it?
plus `covered`, the share of target samples within COVER of the part.
Outline hulls are excluded. One `FIT <part> ...` line per part; --out also
writes them to a file (review.py copies it into the review).
"""
import argparse
import os
import sys

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from levi import shape  # noqa: E402

SAMPLES = 20000
NEAR = 0.03      # m
COVER = 0.005    # m
SEED = 7


def part_mesh(name):
    col = bpy.data.collections.get(name)
    if col is None:
        return None, None
    dg = bpy.context.evaluated_depsgraph_get()
    vs, ts, off = [], [], 0
    for o in col.all_objects:
        if o.type != 'MESH' or o.hide_render:
            continue
        outline = o.modifiers.get('Outline')
        if outline:
            outline.show_viewport = False
        dg.update()
        e = o.evaluated_get(dg)
        me = e.to_mesh()
        me.calc_loop_triangles()
        v = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get('co', v)
        t = np.empty(len(me.loop_triangles) * 3, np.int64)
        me.loop_triangles.foreach_get('vertices', t)
        M = np.array(o.matrix_world)
        vs.append(v.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3])
        ts.append(t.reshape(-1, 3) + off)
        off += len(vs[-1])
        e.to_mesh_clear()
        if outline:
            outline.show_viewport = True
    if not vs:
        return None, None
    return np.concatenate(vs), np.concatenate(ts)


def sample_faces(V, F, n, rng):
    a = np.linalg.norm(np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]]), axis=1)
    i = rng.choice(len(F), n, p=a / a.sum())
    u, v = rng.random(n), rng.random(n)
    flip = u + v > 1
    u[flip], v[flip] = 1 - u[flip], 1 - v[flip]
    T = V[F[i]]
    return T[:, 0] + u[:, None] * (T[:, 1] - T[:, 0]) + v[:, None] * (T[:, 2] - T[:, 0])


def pct(d):
    if not len(d):
        return '   -  /   -  /   - '
    p = np.percentile(d * 1000, [50, 90, 99])
    return f'{p[0]:5.1f} / {p[1]:5.1f} / {p[2]:5.1f}'


def fit(name, rng):
    Vo, Fo = part_mesh(name)
    if Vo is None:
        return None
    ours = BVHTree.FromPolygons(Vo.tolist(), Fo.tolist())
    V, F, _, _ = shape.data()
    sel = shape.faces(name)
    P = sample_faces(V, F[sel], SAMPLES, rng)
    d_to = np.array([ours.find_nearest(Vector(p))[3] for p in P])
    tgt = shape.tree(name)
    d_from = np.array([h[3] if h[0] is not None else np.inf
                       for h in (tgt.find_nearest(Vector(p), NEAR) for p in Vo)])
    d_from = d_from[np.isfinite(d_from)]
    return (f'FIT {name:12s} target->ours {pct(d_to)} mm  ours->target {pct(d_from)} mm  '
            f'covered {np.mean(d_to < COVER):.3f}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--parts', default='')
    ap.add_argument('--out', default='')
    args = ap.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
    names = [p for p in args.parts.split(',') if p] or list(shape.parts())
    rng = np.random.default_rng(SEED)
    lines = [ln for ln in (fit(n, rng) for n in names) if ln]
    print('\n'.join(lines))
    if args.out:
        out = os.path.join(ROOT, args.out)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines) + '\n')


main()
