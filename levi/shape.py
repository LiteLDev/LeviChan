"""The shape master (round 10): target surfaces sampled by the parts.

`assets/shape/levi_shape.npz` (written by tools/prep_shape.py) is the FBX shape
reference, decimated to 400k triangles, aligned to our frame and skeleton, each
triangle labelled with the part that owns it (`PARTS`). It is one fused,
watertight shell: it has outer surfaces only (no body under the clothes, no eyes).

Parts reshape by sampling it inside their own section functions, never by moving
vertices after the build (see CLAUDE.md, "Shape master"). Queries take a part
name or a tuple of names; all positions are world metres.

    from levi import shape
    r, n, lab = shape.radial('skirt', centre, dirs, r_max=0.6)   # outermost-surface radius
    p, d, n = shape.nearest('body', pts)
    hit = shape.ray('head', origins, dirs)
    shape.inside(pts)                                              # inside the whole shell

Misses are NaN; `fill_ring` / `fill_rows` close the gaps by interpolation.
Labels are good, not perfect (stray patches where our overlays lay on cloth, see
docs/pr/r10-phase0/): check them against the geometry in your area.
"""
import math
import os

import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, 'assets', 'shape', 'levi_shape.npz')

_data = None
_trees = {}


def data():
    """(V, F, label, parts) of the master, loaded once."""
    global _data
    if _data is None:
        z = np.load(PATH)
        _data = (z['V'].astype(np.float64), z['F'], z['label'], tuple(str(p) for p in z['parts']))
    return _data


def parts():
    return data()[3]


def _names(labels):
    if labels is None:
        return None
    names = (labels,) if isinstance(labels, str) else tuple(labels)
    unknown = set(names) - set(parts())
    if unknown:
        raise ValueError(f'unknown shape labels {sorted(unknown)}; known: {parts()}')
    return tuple(sorted(names))


def faces(labels=None):
    """Triangle indices owned by `labels` (all if None)."""
    V, F, lab, parts = data()
    names = _names(labels)
    if names is None:
        return np.arange(len(F))
    ids = [parts.index(n) for n in names]
    return np.nonzero(np.isin(lab, ids))[0]


def tree(labels=None):
    """BVH of the triangles owned by `labels` (the whole shell if None), cached."""
    key = _names(labels)
    if key not in _trees:
        V, F, _, _ = data()
        sel = faces(labels)
        _trees[key] = (BVHTree.FromPolygons(V.tolist(), F[sel].tolist()), sel)
    return _trees[key][0]


def face_label(index, labels=None):
    """Part name of triangle `index` of tree(labels)."""
    _, _, lab, parts = data()
    tree(labels)
    return parts[lab[_trees[_names(labels)][1][index]]]


def _as_pts(p):
    return np.atleast_2d(np.asarray(p, dtype=np.float64))


def nearest(labels, pts, max_d=math.inf):
    """Closest point on `labels`: (points, distances, normals); NaN beyond max_d."""
    t = tree(labels)
    P = _as_pts(pts)
    out = np.full((len(P), 3), np.nan)
    nrm = np.full((len(P), 3), np.nan)
    dist = np.full(len(P), np.nan)
    for i, p in enumerate(P):
        hit = t.find_nearest(Vector(p), max_d) if math.isfinite(max_d) else t.find_nearest(Vector(p))
        if hit[0] is not None:
            out[i], nrm[i], dist[i] = hit[0], hit[1], hit[3]
    return out, dist, nrm


def ray(labels, origins, dirs, max_d=10.0, occluders=True):
    """First hit along each ray: (points, distances, normals, part names).

    With occluders=True the ray stops at the first surface of the whole shell and
    counts only if that surface belongs to `labels` (a sleeve in front of the arm
    hides it: NaN). With occluders=False only `labels` is tested.
    """
    O = _as_pts(origins)
    D = _as_pts(dirs)
    D = D / np.linalg.norm(D, axis=1, keepdims=True)
    if len(D) == 1 and len(O) > 1:
        D = np.repeat(D, len(O), 0)
    names = _names(labels)
    t = tree(None if occluders else labels)
    pts = np.full((len(O), 3), np.nan)
    nrm = np.full((len(O), 3), np.nan)
    dist = np.full(len(O), np.nan)
    who = [None] * len(O)
    for i, (o, d) in enumerate(zip(O, D)):
        loc, n, idx, dd = t.ray_cast(Vector(o), Vector(d), max_d)
        if loc is None:
            continue
        name = face_label(idx, None if occluders else labels)
        who[i] = name
        if occluders and name not in names:
            continue
        pts[i], nrm[i], dist[i] = loc, n, dd
    return pts, dist, nrm, who


def radial(labels, centre, dirs, r_max=1.0, occluders=True):
    """Radius of the outermost surface of `labels` along each direction from `centre`.

    Cast inward from centre + dir * r_max, so folds that turn back on themselves
    give their outermost layer. `centre` is one point or one per direction.
    Returns (radii, normals, part names); NaN where the outermost surface is
    another part (occluders=True) or nothing is hit.
    """
    D = _as_pts(dirs)
    D = D / np.linalg.norm(D, axis=1, keepdims=True)
    C = _as_pts(centre)
    if len(C) == 1:
        C = np.repeat(C, len(D), 0)
    p, d, n, who = ray(labels, C + D * r_max, -D, r_max, occluders)
    return r_max - d, n, who


def inside(pts):
    """True where a point lies inside the whole (watertight) shell: parity of
    crossings along +Z, confirmed along -Y (a ray grazing an edge can miscount)."""
    t = tree(None)
    out = []
    for p in _as_pts(pts):
        votes = 0
        for d in ((0, 0, 1), (0, -1, 0.01)):
            o, dv, k = Vector(p), Vector(d).normalized(), 0
            while True:
                hit = t.ray_cast(o, dv)
                if hit[0] is None:
                    break
                k += 1
                o = hit[0] + dv * 1e-6
            votes += k % 2
        out.append(votes == 2)
    return np.array(out)


def fill_ring(r):
    """Close NaN gaps in a closed ring of samples by circular linear interpolation."""
    r = np.asarray(r, dtype=np.float64).copy()
    ok = np.isfinite(r)
    if ok.all() or not ok.any():
        return r
    n = len(r)
    idx = np.nonzero(ok)[0]
    xs = np.concatenate([idx - n, idx, idx + n])
    ys = np.tile(r[idx], 3)
    r[~ok] = np.interp(np.nonzero(~ok)[0], xs, ys)
    return r


def fill_rows(a, axis=0):
    """Close NaN gaps along `axis` of a 2-D table by linear interpolation (ends held)."""
    a = np.moveaxis(np.asarray(a, dtype=np.float64).copy(), axis, 0)
    for j in range(a.shape[1]):
        col = a[:, j]
        ok = np.isfinite(col)
        if ok.any() and not ok.all():
            col[~ok] = np.interp(np.nonzero(~ok)[0], np.nonzero(ok)[0], col[ok])
    return np.moveaxis(a, 0, axis)


def smoothstep(e0, e1, x):
    t = np.clip((np.asarray(x, dtype=np.float64) - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)
