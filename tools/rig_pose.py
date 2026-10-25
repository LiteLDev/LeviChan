"""Build + rig + a deformation test pose, saved for render.py.

    blender -b -P tools/rig_pose.py -- [--out out/levi_pose.blend] [--parts body,skirt]
                                       [--proxy] [--fixtures] [--rest]

Pose: both elbows bent 60 deg, head turned 30 deg, left leg raised through
足ＩＫ.L, right knee bent 60 deg by FK (its IK muted), back-hair and sleeve
chains swung a little. --rest saves the rigged model unposed instead.
--fixtures adds throwaway test meshes (tools/rig_fixtures.py) for whichever of
body/hair/skirt/sleeves are missing; it is on automatically when no parts exist.
"""
import argparse
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import bpy  # noqa: E402
from mathutils import Quaternion, Vector  # noqa: E402

from levi import builder, rig  # noqa: E402


def build_scene(parts, proxy, fixtures):
    """Build parts (+ proxy / fixtures) and rig them. Returns the armature."""
    names = [p for p in parts.split(',') if p]
    if not names and not builder.available_parts():
        fixtures = True
    builder.build_all(names, with_proxy=proxy)
    if fixtures:
        import rig_fixtures
        rig_fixtures.build()
    return rig.build_rig()


def bend(arm, name, world_dir, deg):
    """Rotate pose bone `name` by `deg` so its direction turns toward world_dir."""
    pb = arm.pose.bones[name]
    rest = pb.bone.matrix_local.to_3x3()
    axis = rest.col[1].cross(Vector(world_dir))
    turn(arm, name, axis, deg)


def turn(arm, name, world_axis, deg):
    pb = arm.pose.bones[name]
    local = (pb.bone.matrix_local.to_3x3().inverted() @ Vector(world_axis)).normalized()
    pb.rotation_mode = 'QUATERNION'
    pb.rotation_quaternion = Quaternion(local, math.radians(deg)) @ pb.rotation_quaternion


def apply_test_pose(arm):
    pbs = arm.pose.bones
    for t in 'LR':
        bend(arm, f'ひじ.{t}', (0, -1, 0), 60)
    turn(arm, '頭', (0, 0, 1), 30)
    # left leg raised by moving its IK control
    ik = pbs['足ＩＫ.L']
    m = ik.matrix.copy()
    m.translation += Vector((0.0, -0.14, 0.24))
    ik.matrix = m
    # right knee by FK
    for n in ('ひざ.R', '足首.R'):
        pbs[n].constraints['IK'].mute = True
    bend(arm, '足.R', (0, -1, 0), 25)
    bend(arm, 'ひざ.R', (0, 1, 0), 60)
    # secondary chains
    for pb in pbs:
        if pb.name.startswith('後髪') and pb.name.endswith('_0'):
            turn(arm, pb.name, (0, 1, 0), 12)
        if pb.name.startswith('袖_0'):
            bend(arm, pb.name, (0, -1, 0), 20)
    bpy.context.view_layer.update()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='out/levi_pose.blend')
    ap.add_argument('--parts', default='')
    ap.add_argument('--proxy', action='store_true')
    ap.add_argument('--fixtures', action='store_true')
    ap.add_argument('--rest', action='store_true')
    args = ap.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
    arm = build_scene(args.parts, args.proxy, args.fixtures)
    if not args.rest:
        apply_test_pose(arm)
    out = os.path.join(ROOT, args.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    print('SAVED', out)


if __name__ == '__main__':
    main()
