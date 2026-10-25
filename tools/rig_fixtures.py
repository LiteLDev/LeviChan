"""Throwaway test meshes for exercising the rig without the real parts.

NOT model parts: they only give rig tests non-manifold, multi-object clothing and
hair in the right places. build(names) adds them under part-named collections
(body, skirt, hair_back, hair_front, sleeves) so the per-part skinning rules
apply. Only collections that don't already exist are added.
"""
import math

import bmesh
import bpy
from mathutils import Vector

from levi import common, spec

L = spec.L
FIXTURES = ('body', 'skirt', 'hair_back', 'hair_front', 'sleeves')


def _grid(rows):
    """Open surface (non-manifold) from rows of points."""
    bm = bmesh.new()
    vs = [[bm.verts.new(p) for p in r] for r in rows]
    for a, b in zip(vs, vs[1:]):
        for j in range(len(a) - 1):
            bm.faces.new((a[j], a[j + 1], b[j + 1], b[j]))
    return bm


def _finish(obj, gradient=None):
    common.shade_smooth(obj)
    if gradient:
        common.set_gradient(obj, gradient)
    common.add_outline(obj)


def skirt(col):
    """Open flared cone from the waist to the hem, split into front and back halves."""
    mat = common.toon_material('dress')
    cy = L['waist_center_y'] * 0.6
    n, m = 24, 10
    for half, a0 in (('front', math.pi), ('back', 0.0)):
        rows = []
        for i in range(m + 1):
            t = i / m
            z = L['waist_z'] + (L['skirt_hem_z'] - L['waist_z']) * t
            rx = L['waist_half_w'] * 1.1 + (L['skirt_hem_half_w'] - L['waist_half_w']) * t ** 1.3
            ry = 0.06 + (L['skirt_hem_back_y'] - 0.06) * t ** 1.3
            row = []
            for j in range(n + 1):
                a = a0 + math.pi * j / n
                row.append(Vector((rx * math.cos(a), cy + ry * math.sin(a), z)))
            rows.append(row)
        _finish(common.new_object(col, f'fx_skirt_{half}', _grid(rows), [mat]))


def _ribbon(col, name, pts, width, mat, grad=None, twist=0.0):
    rows = []
    for i, p in enumerate(pts):
        t = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        side = t.cross(Vector((0, 0, 1)))
        if side.length < 1e-4:
            side = Vector((1, 0, 0))
        side.normalize()
        rows.append([p - side * width / 2, p + side * width / 2])
    bm = _grid([[r[0], r[1]] for r in rows])
    obj = common.new_object(col, name, bm, [mat])
    _finish(obj, grad)
    return obj


def hair_back(col):
    """Long hair strands hanging from the back of the skull, one object each."""
    mat = common.toon_material('hair', gradient='hair_tip')
    hc = Vector((0, L['head_center_y'], (L['head_top_z'] + L['chin_z']) / 2))
    grad = common.z_gradient(0.95, 0.75)
    for k in range(9):
        a = math.radians(-100 + 200 * k / 8)        # 0 = straight back (+Y)
        out = Vector((math.sin(a), math.cos(a), 0))
        root = hc + out * 0.085 + Vector((0, 0, 0.05))
        pts = []
        for i in range(12):
            t = i / 11
            p = root + out * (0.03 + 0.12 * t) + Vector((0, 0, -0.55 * t))
            p.x += 0.02 * math.sin(6 * t + k)
            pts.append(p)
        _ribbon(col, f'fx_hair_back_{k}', pts, 0.06, mat, grad)


def hair_front(col):
    """Side locks beside the face plus a bang strip."""
    mat = common.toon_material('hair', gradient='hair_tip')
    grad = common.z_gradient(1.05, 0.95)
    for s in (1, -1):
        x = s * L['head_half_w'] * 1.05
        pts = [Vector((x, L['head_center_y'] - 0.04, L['eye_z'] + 0.05 - 0.3 * i / 9)) for i in range(10)]
        _ribbon(col, f'fx_sidelock_{s}', pts, 0.03, mat, grad)
    pts = [Vector((-0.06 + 0.12 * i / 6, L['head_center_y'] - 0.08, L['eye_z'] + 0.05)) for i in range(7)]
    rows = [[p + Vector((0, 0, 0.04)), p] for p in pts]
    obj = common.new_object(col, 'fx_bangs', _grid(list(map(list, zip(*rows)))), [mat])
    _finish(obj)


def sleeves(col):
    """Bell sleeves from the upper arm to the wrist, open at both ends, with a hanging drape."""
    mat = common.toon_material('sleeve')
    for s in (1, -1):
        sj, el, wr = (Vector((s * p[0], p[1], p[2])) for p in (L['shoulder_joint'], L['elbow'], L['wrist']))
        axis_pts = [sj.lerp(el, 0.4), el, el.lerp(wr, 0.5), wr]
        radii = [0.045, 0.06, 0.08, 0.09]
        rows = []
        n = 16
        for p, r, nxt in zip(axis_pts, radii, axis_pts[1:] + [axis_pts[-1] + (wr - el) * 0.1]):
            t = (nxt - p).normalized()
            side = t.cross(Vector((0, -1, 0))).normalized()
            up = t.cross(side)
            row = []
            for j in range(n + 1):
                a = 2 * math.pi * j / n
                sag = max(0.0, -math.sin(a)) * (r - 0.04) * 1.2   # bell hangs down
                row.append(p + side * math.cos(a) * r + up * math.sin(a) * (r + sag))
            rows.append(row)
        _finish(common.new_object(col, f'fx_sleeve_{s}', _grid(rows), [mat]))


def _dense(points, radii, step=0.01):
    pts, rs = [], []
    for (a, ra), (b, rb) in zip(zip(points, radii), zip(points[1:], radii[1:])):
        n = max(2, int((b - a).length / step))
        for i in range(n):
            t = i / n
            pts.append(a.lerp(b, t))
            rs.append(ra + (rb - ra) * t)
    return pts + [points[-1]], rs + [radii[-1]]


def body(col):
    """Densely ringed limbs/torso (unlike the 3-ring proxy) so joint deformation is visible."""
    mat = common.toon_material('skin')

    def tube(name, points, radii, n=16):
        pts, rs = _dense([Vector(p) for p in points], radii)
        obj = common.new_object(col, name, common.tube_along(pts, rs, n=n), [mat])
        _finish(obj)

    secs = [
        (L['choker_z'] + 0.02, L['neck_half_w'], L['neck_half_w'], L['neck_center_y']),
        (L['shoulder_z'], L['shoulder_half_w'] * 0.85, 0.055, L['chest_center_y']),
        (L['bodice_top_z'], L['bust_half_w'], 0.075, L['chest_center_y']),
        (L['waist_z'], L['waist_half_w'], 0.05, L['waist_center_y']),
        (L['hip_z'], L['waist_half_w'] * 1.45, 0.07, L['waist_center_y'] * 0.6),
        (L['crotch_z'], L['leg_center_x'] + L['thigh_half_w'], 0.065, 0.0),
    ]
    rings = []
    for (z0, rx0, ry0, cy0), (z1, rx1, ry1, cy1) in zip(secs, secs[1:]):
        for i in range(8):
            t = i / 8
            rings.append(common.ellipse_ring((0, cy0 + (cy1 - cy0) * t, z0 + (z1 - z0) * t),
                                             rx0 + (rx1 - rx0) * t, ry0 + (ry1 - ry0) * t, 24))
    z, rx, ry, cy = secs[-1]
    rings.append(common.ellipse_ring((0, cy, z), rx, ry, 24))
    obj = common.new_object(col, 'fx_torso', common.loft(rings, cap_start=True, cap_end=True), [mat])
    _finish(obj)
    head_r = (L['head_top_z'] - L['chin_z']) / 2
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=16, radius=head_r)
    bmesh.ops.scale(bm, vec=(L['head_half_w'] / head_r * 1.1, 1.0, 1.0), verts=bm.verts)
    bmesh.ops.translate(bm, vec=Vector((0, L['head_center_y'], (L['head_top_z'] + L['chin_z']) / 2 - 0.01)),
                        verts=bm.verts)
    _finish(common.new_object(col, 'fx_head', bm, [mat]))
    for s in (1, -1):
        m = lambda p: (s * p[0], p[1], p[2])  # noqa: E731
        tube(f'fx_leg_{s}', [m((L['leg_center_x'], 0, L['crotch_z'] + 0.04)), m((L['leg_center_x'], -0.012, L['knee_z'])),
                             m((L['ankle_center_x'], 0, L['ankle_z'])), m((L['toe_tip_x'], L['toe_tip_y'], 0.015))],
             [L['thigh_half_w'], L['knee_half_w'], L['ankle_half_w'], 0.012])
        tube(f'fx_arm_{s}', [m(L['shoulder_joint']), m(L['elbow']), m(L['wrist']), m(L['fingertip'])],
             [0.03, 0.024, 0.018, 0.008])


def build(names=FIXTURES):
    fns = {'skirt': skirt, 'hair_back': hair_back, 'hair_front': hair_front, 'sleeves': sleeves, 'body': body}
    out = {}
    for n in names:
        if bpy.data.collections.get(n) is not None:
            continue
        col = common.part_collection(n)
        fns[n](col)
        out[n] = col
    return out
