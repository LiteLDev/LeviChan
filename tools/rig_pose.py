"""Build + rig + deformation test poses, saved for render.py.

    blender -b -P tools/rig_pose.py -- [--out out/levi_pose.blend] [--parts body,skirt]
                                       [--proxy] [--fixtures] [--rest] [--pose NAME]

POSES (rig_check deforms the model with every one of them):
  test             round-1 pose: elbows 60 deg, head 30 deg, left leg raised through
                   足ＩＫ.L, right knee 60 deg by FK, hair / sleeve / skirt chains swung a little
  arms_up          both arms overhead, shoulders shrugged 8 deg by hand + the rig's own shrug (model lowered 17 cm)
  arms_forward     upper arms forward, hands shoulder-width apart, elbows bent 120 deg upward
  wrist_twist_pos  forearms twisted +60 deg (手捩 when the rig has it, else 手首)
  wrist_twist_neg  ... -60 deg
  squat            hips dropped 27 cm with the feet held by IK (knees ~120 deg)
  walk             stride: left foot forward and lifted, right foot back, arm swing
  head_left/right  head turned 45 deg and tilted 15 deg
  torso_left/right upper body twisted 30 deg
  swing            back hair (spread down each chain), side locks, sleeve drapes and skirt chains swung hard
  fist             both hands closed into fists (fingers curled 75/90/60 deg), elbows 30 deg
  raise_bend       arms raised 45 deg sideways, elbows 60 deg
  reach_forward    arms swung 45 deg forward, elbows 90 deg
  forward_bend     torso bent 40 deg forward over the spine, pelvis tipped 10 deg, arms hanging
  side_bend        upper body bent 30 deg to her left, right arm raised
Extended poses (tools/motion_poses.py EXTENDED) and motion clip frames ('<clip>@<frame>',
motion_poses.CLIPS) are accepted wherever a pose name is (--pose, apply_pose, render.py --pose).
--rest saves the rigged model unposed instead.
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
    """Rotate pose bone `name` by `deg` so its direction turns toward world_dir
    (axes are taken in the bone's rest frame, i.e. relative to its parent)."""
    pb = arm.pose.bones[name]
    rest = pb.bone.matrix_local.to_3x3()
    axis = rest.col[1].cross(Vector(world_dir))
    turn(arm, name, axis, deg)


def turn(arm, name, world_axis, deg):
    pb = arm.pose.bones[name]
    local = (pb.bone.matrix_local.to_3x3().inverted() @ Vector(world_axis)).normalized()
    pb.rotation_mode = 'QUATERNION'
    pb.rotation_quaternion = Quaternion(local, math.radians(deg)) @ pb.rotation_quaternion


def aim(arm, name, world_dir, frac=1.0):
    """Rotate pose bone `name` (from rest) so it would point along world_dir, or `frac` of
    the way, if its parent stayed at rest (like bend/turn, relative to the parent)."""
    pb = arm.pose.bones[name]
    d0 = pb.bone.matrix_local.to_3x3().col[1].normalized()
    d1 = Vector(world_dir).normalized()
    ang = math.degrees(d0.angle(d1))
    if ang > 1e-3:
        turn(arm, name, d0.cross(d1), ang * frac)


def turn_posed(arm, name, world_axis, deg):
    """Rotate pose bone `name` by `deg` about `world_axis` taken in the current pose
    (after its parents have moved), unlike turn(), which uses the rest frame."""
    bpy.context.view_layer.update()
    pb = arm.pose.bones[name]
    local = (pb.matrix.to_3x3().normalized().inverted() @ Vector(world_axis)).normalized()
    pb.rotation_mode = 'QUATERNION'
    pb.rotation_quaternion = pb.rotation_quaternion @ Quaternion(local, math.radians(deg))
    bpy.context.view_layer.update()


def bend_posed(arm, name, world_dir, deg):
    """Bend pose bone `name` by `deg` toward world_dir, in the current pose."""
    bpy.context.view_layer.update()
    pb = arm.pose.bones[name]
    d = (pb.tail - pb.head).normalized()
    turn_posed(arm, name, d.cross(Vector(world_dir)), deg)


def twist(arm, name, deg):
    """Rotate pose bone `name` about its own axis."""
    turn(arm, name, arm.pose.bones[name].bone.matrix_local.to_3x3().col[1], deg)


def move(arm, name, delta):
    pb = arm.pose.bones[name]
    m = pb.matrix.copy()
    m.translation += Vector(delta)
    pb.matrix = m
    bpy.context.view_layer.update()


def reset_pose(arm):
    if arm.animation_data and arm.animation_data.action:   # a motion clip (motion_poses)
        arm.animation_data.action = None
    for pb in arm.pose.bones:
        pb.matrix_basis.identity()
        for c in pb.constraints:
            c.mute = False
    bpy.context.view_layer.update()


def _chains(arm, prefix, seg='_0'):
    """Pose bones of the chains named prefix*, segment `seg` (e.g. the chain roots)."""
    return [pb.name for pb in arm.pose.bones
            if pb.name.startswith(prefix) and pb.name.split('.')[0].endswith(seg)]


def _skirt_flare(arm, flare, sway):
    for n in _chains(arm, 'スカート'):
        bone = arm.pose.bones[n].bone
        out = bone.tail_local - bone.head_local
        out.z = 0.0
        if out.length > 1e-6:
            bend(arm, n, out.normalized(), flare)
        turn(arm, n, (0, 1, 0), sway)


def pose_test(arm):
    pbs = arm.pose.bones
    for t in 'LR':
        bend(arm, f'ひじ.{t}', (0, -1, 0), 60)
    turn(arm, '頭', (0, 0, 1), 30)
    move(arm, '足ＩＫ.L', (0.0, -0.14, 0.24))          # left leg raised by its IK control
    for n in ('ひざ.R', '足首.R'):                       # right knee by FK
        pbs[n].constraints['IK'].mute = True
    bend(arm, '足.R', (0, -1, 0), 25)
    bend(arm, 'ひざ.R', (0, 1, 0), 60)
    for n in _chains(arm, '後髪'):
        turn(arm, n, (0, 1, 0), 12)
    for n in _chains(arm, '袖'):
        bend(arm, n, (0, -1, 0), 20)
    _skirt_flare(arm, 5, 5)


def pose_arms_up(arm):
    # the rig lifts the shoulders by itself as the arms rise (rig.SHOULDER_SHRUG): 8 deg by
    # hand on top of that (round 3: 15 deg with no automatic shrug)
    move(arm, '全ての親', (0.0, 0.0, -0.17))      # whole model lowered: keeps the hands inside render.py's frame
    for tag, s in (('L', 1), ('R', -1)):
        bend(arm, f'肩.{tag}', (0, 0, 1), 8)
        aim(arm, f'腕.{tag}', (0.6 * s, -0.1, 1.0))
        bend(arm, f'ひじ.{tag}', (0, -1, 0), 25)


def pose_arms_forward(arm):
    """Upper arms forward, hands about shoulder-width apart, elbows bent 120 deg upward
    (forearms rising back toward the face)."""
    for tag, s in (('L', 1), ('R', -1)):
        aim(arm, f'腕.{tag}', (0.35 * s, -1.0, -0.8))
        bend_posed(arm, f'ひじ.{tag}', (0, 0, 1), 120)


def _wrist_twist(arm, deg):
    for tag, s in (('L', 1), ('R', -1)):
        bend(arm, f'ひじ.{tag}', (0, -1, 0), 45)
        name = f'手捩.{tag}' if f'手捩.{tag}' in arm.pose.bones else f'手首.{tag}'
        twist(arm, name, deg * s)
        bend(arm, f'手首.{tag}', (0, -1, 0), 20)


def pose_wrist_twist_pos(arm):
    _wrist_twist(arm, 60)


def pose_wrist_twist_neg(arm):
    _wrist_twist(arm, -60)


def pose_squat(arm):
    move(arm, 'センター', (0.0, 0.05, -0.27))
    bend(arm, '上半身', (0, -1, 0), 25)
    for tag, s in (('L', 1), ('R', -1)):
        move(arm, f'足ＩＫ.{tag}', (0.04 * s, 0.0, 0.0))
        aim(arm, f'腕.{tag}', (0.4 * s, -0.6, -0.5))


def pose_walk(arm):
    move(arm, 'センター', (0.0, -0.02, -0.04))
    move(arm, '足ＩＫ.L', (0.0, -0.24, 0.05))
    move(arm, '足ＩＫ.R', (0.0, 0.2, 0.03))
    bend(arm, '腕.L', (0, 1, 0), 25)
    bend(arm, '腕.R', (0, -1, 0), 25)
    for tag in 'LR':
        bend(arm, f'ひじ.{tag}', (0, -1, 0), 20)
    turn(arm, '上半身', (0, 0, 1), -8)
    _skirt_flare(arm, 4, 0)


def _head(arm, yaw, roll):
    turn(arm, '頭', (0, 0, 1), yaw)
    turn(arm, '頭', (0, -1, 0), roll)


def pose_head_left(arm):
    _head(arm, 45, 15)


def pose_head_right(arm):
    _head(arm, -45, -15)


def pose_torso_left(arm):
    turn(arm, '上半身', (0, 0, 1), 20)
    turn(arm, '上半身2', (0, 0, 1), 10)


def pose_torso_right(arm):
    turn(arm, '上半身', (0, 0, 1), -20)
    turn(arm, '上半身2', (0, 0, 1), -10)


SWING_SPREAD = (0.4, 0.25, 0.2, 0.15)   # share of a hair chain's swing per segment, root first


def pose_swing(arm):
    # back hair swings like hanging hair under physics: the turn is spread down each chain
    # (SWING_SPREAD), so a lock bends along its length instead of pivoting at the scalp
    for i, share in enumerate(SWING_SPREAD):
        for n in _chains(arm, '後髪', f'_{i}'):
            turn(arm, n, (0, 1, 0), 20 * share)
            turn(arm, n, (1, 0, 0), 15 * share)
    for n in _chains(arm, '横髪'):
        turn(arm, n, (1, 0, 0), 20)
    for n in _chains(arm, '袖'):
        bend(arm, n, (0, -1, 0), 35)
    # the skirt is blown back (about X): swung sideways it would swallow the hands at
    # her sides, which only MMD physics (hand rigid bodies) can push it off
    _skirt_flare(arm, 10, 0)
    for n in _chains(arm, 'スカート'):
        turn(arm, n, (1, 0, 0), 8)
    for n in _chains(arm, 'スカート', '_1'):
        turn(arm, n, (1, 0, 0), 8)


def pose_raise_bend(arm):
    """Arms raised 45 deg sideways with the elbows bent 60 deg."""
    for t in 'LR':
        bend(arm, f'腕.{t}', (0, 0, 1), 45)
        bend(arm, f'ひじ.{t}', (0, -1, 0), 60)


def pose_reach_forward(arm):
    """Arms swung 45 deg forward with the elbows bent 90 deg (the round-2 'forward_bend')."""
    for t in 'LR':
        bend(arm, f'腕.{t}', (0, -1, 0), 45)
        bend(arm, f'ひじ.{t}', (0, -1, 0), 90)


def pose_forward_bend(arm):
    """Torso bent 40 deg forward over the spine (上半身 25 + 上半身2 15), the pelvis
    tipped 10 deg with it, head lifted back 10 deg, arms hanging forward."""
    move(arm, 'センター', (0.0, 0.03, -0.02))
    turn(arm, '下半身', (1, 0, 0), 10)
    turn(arm, '上半身', (1, 0, 0), 25)
    turn(arm, '上半身2', (1, 0, 0), 15)
    turn(arm, '首', (1, 0, 0), -10)
    for t in 'LR':
        bend_posed(arm, f'腕.{t}', (0, -1, 0), 30)
        bend_posed(arm, f'ひじ.{t}', (0, -1, 0), 30)


def pose_side_bend(arm):
    """Upper body bent 30 deg to the character's left (上半身 20 + 上半身2 10), head
    following, right arm raised 40 deg."""
    turn(arm, '上半身', (0, 1, 0), 20)      # about +Y: the top swings toward +X (her left)
    turn(arm, '上半身2', (0, 1, 0), 10)
    bend_posed(arm, '腕.R', (0, 0, 1), 40)
    bend_posed(arm, 'ひじ.R', (0, 0, 1), 30)


FIST = {'親指０': 15, '親指１': 35, '親指２': 45, '１': 75, '２': 90, '３': 60}


def pose_fist(arm):
    """Both hands closed into fists (finger bones curled about their own X, which the
    rig rolls toward the palm), elbows bent 30 deg to show the hands."""
    for t in 'LR':
        bend(arm, f'ひじ.{t}', (0, -1, 0), 30)
    for pb in arm.pose.bones:
        if pb.bone.collections and pb.bone.collections[0].name == 'Fingers':
            stem = pb.name.split('.')[0]
            deg = FIST.get(stem) or FIST.get(stem[-1], 0)
            turn(arm, pb.name, pb.bone.matrix_local.to_3x3().col[0], deg)


POSES = {
    'test': pose_test, 'arms_up': pose_arms_up, 'arms_forward': pose_arms_forward,
    'wrist_twist_pos': pose_wrist_twist_pos, 'wrist_twist_neg': pose_wrist_twist_neg,
    'squat': pose_squat, 'walk': pose_walk, 'head_left': pose_head_left, 'head_right': pose_head_right,
    'torso_left': pose_torso_left, 'torso_right': pose_torso_right, 'swing': pose_swing, 'fist': pose_fist,
    'raise_bend': pose_raise_bend, 'reach_forward': pose_reach_forward, 'forward_bend': pose_forward_bend,
    'side_bend': pose_side_bend,
}


def extended():
    """{name: function} of tools/motion_poses.py EXTENDED (not gated by rig_check)."""
    import motion_poses
    return motion_poses.EXTENDED


def known(name):
    """True for a core pose, an extended pose, or a clip frame '<clip>@<frame>'."""
    if name in POSES:
        return True
    import motion_poses
    if '@' in name:
        clip, _, f = name.partition('@')
        return clip in motion_poses.CLIPS and f.isdigit() and int(f) <= motion_poses.clip_frames(clip)
    return name in motion_poses.EXTENDED


def apply_pose(arm, name):
    """Reset the armature and apply POSES[name], an extended pose (motion_poses.EXTENDED)
    or a motion clip frame '<clip>@<frame>' (motion_poses.CLIPS)."""
    reset_pose(arm)
    if name in POSES:
        POSES[name](arm)
    else:
        import motion_poses
        if '@' in name:
            clip, _, f = name.partition('@')
            motion_poses.apply_clip_frame(arm, clip, int(f))
        else:
            motion_poses.EXTENDED[name](arm)
    bpy.context.view_layer.update()


def apply_test_pose(arm):
    apply_pose(arm, 'test')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='out/levi_pose.blend')
    ap.add_argument('--parts', default='')
    ap.add_argument('--proxy', action='store_true')
    ap.add_argument('--fixtures', action='store_true')
    ap.add_argument('--rest', action='store_true')
    ap.add_argument('--pose', default='test',
                    help='a POSES name, an extended pose (motion_poses.EXTENDED) or <clip>@<frame>')
    args = ap.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
    if not known(args.pose):
        ap.error(f'--pose: unknown pose {args.pose!r}')
    arm = build_scene(args.parts, args.proxy, args.fixtures)
    if not args.rest:
        apply_pose(arm, args.pose)
    out = os.path.join(ROOT, args.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    print('SAVED', out)


if __name__ == '__main__':
    main()
