"""Grey stand-in body built from spec landmarks, for parts that need context
(sleeves around arms, shoes around feet) before the real body lands.

Built only with `build.py --proxy`; never part of the final model.
"""
import bmesh
from mathutils import Vector

from . import common, spec

NAME = '_proxy'


def build():
    L = spec.L
    col = common.part_collection(NAME)
    mat = common.toon_material('skin')

    def sphere(name, center, r, scale=(1, 1, 1)):
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=10, radius=r)
        bmesh.ops.scale(bm, vec=scale, verts=bm.verts)
        bmesh.ops.translate(bm, vec=Vector(center), verts=bm.verts)
        common.new_object(col, name, bm, [mat])

    head_r = (L['head_top_z'] - L['chin_z']) / 2
    sphere('proxy_head', (0, L['head_center_y'], (L['head_top_z'] + L['chin_z']) / 2 - 0.01),
           head_r, (L['head_half_w'] / head_r * 1.1, 1.0, 1.0))

    # Torso: neck -> waist -> hip, elliptical sections.
    secs = [
        (L['choker_z'] + 0.02, L['neck_half_w'], L['neck_half_w'], L['neck_center_y']),
        (L['shoulder_z'], L['shoulder_half_w'] * 0.85, 0.055, L['chest_center_y']),
        (L['bodice_top_z'], L['bust_half_w'], 0.075, L['chest_center_y']),
        (L['waist_z'], L['waist_half_w'], 0.05, L['waist_center_y']),
        (L['hip_z'], L['waist_half_w'] * 1.45, 0.07, L['waist_center_y'] * 0.6),
        (L['crotch_z'], L['leg_center_x'] + L['thigh_half_w'], 0.065, 0.0),
    ]
    rings = [common.ellipse_ring((0, cy, z), rx, ry, 16) for z, rx, ry, cy in secs]
    common.new_object(col, 'proxy_torso', common.loft(rings, cap_start=True, cap_end=True), [mat])

    for sx in (1, -1):
        leg = [Vector((sx * L['leg_center_x'], 0, L['crotch_z'] + 0.02)),
               Vector((sx * L['leg_center_x'], 0, L['knee_z'])),
               Vector((sx * L['ankle_center_x'], 0, L['ankle_z']))]
        common.new_object(col, f'proxy_leg_{sx}',
                          common.tube_along(leg, [L['thigh_half_w'], L['knee_half_w'], L['ankle_half_w']]), [mat])
        arm = [Vector((sx * p[0], p[1], p[2])) for p in
               (L['shoulder_joint'], L['elbow'], L['wrist'], L['fingertip'])]
        common.new_object(col, f'proxy_arm_{sx}', common.tube_along(arm, [0.03, 0.024, 0.018, 0.008]), [mat])
        foot = [Vector((sx * L['ankle_center_x'], L['heel_back_y'], L['heel_height'])),
                Vector((sx * L['toe_tip_x'], L['toe_tip_y'], 0.004))]
        common.new_object(col, f'proxy_foot_{sx}', common.tube_along(foot, [0.022, 0.012], n=6), [mat])
    return col
