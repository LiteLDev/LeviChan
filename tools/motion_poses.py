"""Extended poses and keyframed motion clips for the complex-motion tests.

rig_pose.POSES (17) stays the gating core set of tools/rig_check.py. This module adds

  EXTENDED   combined, extreme but humanly plausible static poses (sitting, kneeling, lunges,
             running, kicks, arm wraps, twists, MMD dance key poses); reported by
             `rig_check.py --extended`, not gated.
  CLIPS      animated sequences at 30 fps (walk, run, turn in place, sit down / stand up,
             spin with the arms out, an idol-dance phrase), keyed with Bezier interpolation
             on the standard MMD input bones (センター, 足ＩＫ / つま先ＩＫ, 上半身…, 腕, ひじ…) and
             evaluated on every frame by `rig_check.py --motion`.

Every pose function poses the armature from rest, like rig_pose's. Directions are world
directions with the parent at rest (helpers from rig_pose), given for the character's left
(.L, +X) and mirrored for .R. Joint angles stay inside a healthy adult's active range of
motion (knee <= 160 deg, elbow <= 145 deg, hip flexion <= 120 deg bent / 90 deg straight,
neck yaw <= 60 deg + torso twist <= 40 deg, forearm twist <= 80 deg).

Legs use the leg IK (feet placed with `foot`) except where marked FK (`leg_fk` mutes the
IK of that leg, as MMD's IK switch would): cross_legged, high_kick, lie_back_elbows. Clips
only use IK poses (keyframes cannot carry the IK mute).

A clip frame is addressed as '<clip>@<frame>' wherever a pose name is accepted
(rig_pose.apply_pose, render.py --pose).
"""
import math

import bpy
from mathutils import Matrix, Quaternion, Vector

import rig_pose
from rig_pose import _chains, aim, bend, move, turn, twist

FPS = 30


def _m(tag, v):
    """Mirror a left-side (+X) direction or offset for tag 'R'."""
    return Vector((-v[0], v[1], v[2])) if tag == 'R' else Vector(v)


def _perp(v, axis):
    v = Vector(v) - Vector(axis) * Vector(v).dot(axis)
    return v.normalized() if v.length > 1e-6 else v


def _signed(u, w, axis):
    return math.atan2(u.cross(w).dot(axis), u.dot(w))


def _q_turn(arm, name, q):
    """Apply world rotation q (parent at rest) to pose bone `name`, like rig_pose.turn."""
    axis, ang = q.to_axis_angle()
    if abs(ang) > 1e-6:
        turn(arm, name, axis, math.degrees(ang))


def limb(arm, upper, lower, tag, upper_dir, bend_deg, flex_toward=None, rest_flex=(0, -1, 0)):
    """Aim `upper` (.tag) along upper_dir, roll it about its length so the joint below flexes
    toward flex_toward (a world direction), then flex `lower` by bend_deg about its own
    hinge (rest_flex: where the lower bone swings at rest, -Y for the elbow, +Y for the knee).
    Directions are given for the left side and mirrored for .R."""
    up_n, lo_n = f'{upper}.{tag}', f'{lower}.{tag}'
    if up_n not in arm.pose.bones:
        return
    d0 = arm.pose.bones[up_n].bone.matrix_local.to_3x3().col[1].normalized()
    d1 = _m(tag, upper_dir).normalized()
    q = d0.rotation_difference(d1)
    if flex_toward is not None:
        u = _perp(q @ _perp(rest_flex, d0), d1)
        w = _perp(_m(tag, flex_toward), d1)
        if u.length > 1e-6 and w.length > 1e-6:
            q = Quaternion(d1, _signed(u, w, d1)) @ q
    _q_turn(arm, up_n, q)
    if bend_deg:
        bend(arm, lo_n, rest_flex, bend_deg)


def arm_pose(arm, tag, upper_dir, elbow=0.0, flex_toward=None, pronate=0.0, wrist=0.0, shrug=0.0):
    """Arm .tag: 腕 aimed at upper_dir, elbow flexed `elbow` deg toward flex_toward, forearm
    pronated `pronate` deg (手捩, + turns the palm down/back), wrist flexed `wrist` deg toward
    the palm, clavicle raised `shrug` deg."""
    if shrug:
        bend(arm, f'肩.{tag}', (0, 0, 1), shrug)
    limb(arm, '腕', 'ひじ', tag, upper_dir, elbow, flex_toward, rest_flex=(0, -1, 0))
    s = 1 if tag == 'L' else -1
    if pronate:
        n = f'手捩.{tag}' if f'手捩.{tag}' in arm.pose.bones else f'手首.{tag}'
        twist(arm, n, pronate * s)
    if wrist:
        bend(arm, f'手首.{tag}', (0, -1, 0), wrist)


def _ik_mute(arm, tag, mute):
    for n in (f'ひざ.{tag}', f'足首.{tag}'):
        for c in arm.pose.bones[n].constraints:
            if c.type == 'IK':
                c.mute = mute


def leg_fk(arm, tag, thigh_dir, knee, flex_toward=None, ankle=0.0):
    """FK leg .tag (its IK muted): thigh along thigh_dir, knee flexed `knee` deg toward
    flex_toward (where the shin swings), ankle plantar-flexed `ankle` deg."""
    _ik_mute(arm, tag, True)
    limb(arm, '足', 'ひざ', tag, thigh_dir, knee, flex_toward, rest_flex=(0, 1, 0))
    if ankle:
        bend(arm, f'足首.{tag}', (0, 0, -1), ankle)


def foot(arm, tag, off=(0, 0, 0), pitch=0.0, yaw=0.0, toe_dir=None):
    """Place 足ＩＫ.tag: the ankle moved by `off` from rest (x outward), the foot pitched
    `pitch` deg (+ = toes down, heel up), turned `yaw` deg (+ = toes out), or pointing along
    toe_dir (ankle -> toe, world). Left-side values, mirrored for .R."""
    ik, toe = arm.pose.bones[f'足ＩＫ.{tag}'], arm.pose.bones[f'つま先ＩＫ.{tag}']
    a0, t0 = ik.bone.head_local, toe.bone.head_local
    d0 = t0 - a0
    if toe_dir is not None:
        d1 = _m(tag, toe_dir).normalized() * d0.length
    else:
        s = 1 if tag == 'L' else -1
        d1 = Quaternion((0, 0, 1), math.radians(yaw * s)) @ (Quaternion((1, 0, 0), math.radians(pitch)) @ d0)
    r = d0.rotation_difference(d1).to_matrix().to_4x4()
    root = arm.pose.bones['全ての親']           # placed relative to the (possibly moved) root
    m = (root.matrix @ root.bone.matrix_local.inverted() @ Matrix.Translation(a0 + _m(tag, off))
         @ r @ ik.bone.matrix_local.to_3x3().to_4x4())
    ik.matrix = m
    bpy.context.view_layer.update()


def centre(arm, off=(0, 0, 0), yaw=0.0):
    if yaw:
        turn(arm, 'センター', (0, 0, 1), yaw)
    if any(off):
        move(arm, 'センター', off)


def spine(arm, pitch=0.0, yaw=0.0, roll=0.0, lower_pitch=0.0, lower_roll=0.0, split=0.6):
    """Torso: pitch (+ forward), yaw (+ to her left), roll (+ bends to her left), split
    `split` on 上半身 and the rest on 上半身2; lower_* turn the pelvis (下半身)."""
    for n, k in (('上半身', split), ('上半身2', 1 - split)):
        if pitch:
            turn(arm, n, (1, 0, 0), pitch * k)
        if yaw:
            turn(arm, n, (0, 0, 1), yaw * k)
        if roll:
            turn(arm, n, (0, 1, 0), roll * k)
    if lower_pitch:
        turn(arm, '下半身', (1, 0, 0), lower_pitch)
    if lower_roll:
        turn(arm, '下半身', (0, 1, 0), lower_roll)


def head(arm, yaw=0.0, pitch=0.0, roll=0.0, neck=0.5):
    """Head yaw (+ her left), pitch (+ down), roll (+ toward her left shoulder); `neck`
    of it on 首, the rest on 頭."""
    for n, k in (('首', neck), ('頭', 1 - neck)):
        if yaw:
            turn(arm, n, (0, 0, 1), yaw * k)
        if pitch:
            turn(arm, n, (1, 0, 0), pitch * k)
        if roll:
            turn(arm, n, (0, 1, 0), roll * k)


def fingers(arm, tag, curl):
    """Curl every finger of .tag by `curl` (0..1 of rig_pose.FIST)."""
    for pb in arm.pose.bones:
        if pb.name.endswith('.' + tag) and pb.bone.collections and pb.bone.collections[0].name == 'Fingers':
            stem = pb.name.split('.')[0]
            deg = rig_pose.FIST.get(stem) or rig_pose.FIST.get(stem[-1], 0)
            turn(arm, pb.name, pb.bone.matrix_local.to_3x3().col[0], deg * curl)


def skirt_flare(arm, deg, back=0.0):
    """Skirt chain roots flared out `deg` (as a spin or a jump would through physics) and
    blown back `back` deg."""
    for n in _chains(arm, 'スカート'):
        bone = arm.pose.bones[n].bone
        out = bone.tail_local - bone.head_local
        out.z = 0.0
        if out.length > 1e-6 and deg:
            bend(arm, n, out.normalized(), deg)
        if back:
            turn(arm, n, (1, 0, 0), back)


def hair_swing(arm, yaw=0.0, back=0.0):
    """Back hair chains swung sideways (about Y, + toward her left) / back, spread down
    each chain like hanging hair (rig_pose.SWING_SPREAD)."""
    for i, share in enumerate(rig_pose.SWING_SPREAD):
        for n in _chains(arm, '後髪', f'_{i}'):
            if yaw:
                turn(arm, n, (0, 1, 0), yaw * share)
            if back:
                turn(arm, n, (1, 0, 0), back * share)


# ---------------------------------------------------------------- extended poses

def pose_rest(arm):
    pass


def _sit(arm, amount=1.0, lean=0.0):
    """Sitting on a chair (seat ~43 cm) blended by `amount` from standing, torso leaned
    forward `lean` deg (rising from / lowering onto the seat)."""
    a = amount
    centre(arm, (0.0, 0.30 * a, -0.40 * a))
    for t in 'LR':
        foot(arm, t, (0.015 * a, -0.13 * a, 0.0))
        arm_pose(arm, t, (0.18 + 0.05 * a, -0.10 - 0.45 * a, -1.0), 15 + 45 * a, (0, -1, 0.2))
    spine(arm, pitch=lean, lower_pitch=-6 * a)


def pose_sit_chair(arm):
    """Sitting upright on a chair, knees ~95 deg, hands resting on the lap."""
    _sit(arm, 1.0, 4.0)
    head(arm, pitch=6)


def pose_seiza(arm):
    """Kneeling seiza: sitting on the heels, knees ~155 deg, insteps flat on the floor,
    hands on the thighs."""
    centre(arm, (0.0, 0.17, -0.63))
    for t in 'LR':
        foot(arm, t, (0.01, -0.02, -0.138), toe_dir=(0.0, 1.0, -0.12))
        arm_pose(arm, t, (0.15, -0.45, -1.0), 55, (0, -1, 0.1))
    spine(arm, pitch=3, lower_pitch=-4)


def pose_kneel_one(arm):
    """Kneeling on the right knee (toes tucked), left foot planted forward, knee 90 deg,
    left forearm on the left knee."""
    centre(arm, (0.0, 0.02, -0.36))
    foot(arm, 'L', (0.03, -0.38, 0.0))
    foot(arm, 'R', (0.0, 0.18, -0.02), toe_dir=(0.0, -0.55, -1.0))
    spine(arm, pitch=8)
    arm_pose(arm, 'L', (0.2, -0.75, -0.6), 70, (0, -0.2, 1))
    arm_pose(arm, 'R', (0.15, 0.0, -1.0), 15)


def pose_cross_legged(arm):
    """Sitting cross-legged on the floor (FK legs): thighs out and forward, knees bent
    ~125 deg, shins crossed in front, hands on the knees."""
    centre(arm, (0.0, 0.05, -0.70))
    leg_fk(arm, 'L', (0.62, -0.72, -0.04), 125, flex_toward=(-1.0, 0.05, 0.08), ankle=15)
    leg_fk(arm, 'R', (0.62, -0.72, -0.13), 125, flex_toward=(-1.0, 0.05, -0.12), ankle=15)
    spine(arm, pitch=8, lower_pitch=-10)
    for t in 'LR':
        arm_pose(arm, t, (0.45, -0.55, -0.7), 40, (0.3, -1, 0))


def pose_deep_lunge(arm):
    """Deep forward lunge: left knee ~90 deg over the ankle, right leg far back with the
    knee near the floor and the heel up; torso upright, hands on the front thigh."""
    centre(arm, (0.0, 0.06, -0.33))
    foot(arm, 'L', (0.03, -0.42, 0.0))
    foot(arm, 'R', (0.01, 0.40, -0.06), pitch=45)
    spine(arm, pitch=6)
    for t in 'LR':
        arm_pose(arm, t, (0.2, -0.6, -0.8), 40, (0, -1, 0.2))


def _run(arm, side, k=1.0):
    """Running stride, flight phase: leg `side` driven forward and up (thigh ~55 deg,
    knee ~95 deg), the other pushed back off its toes; opposite arm forward, elbows 90 deg,
    torso leaned 8 deg and counter-twisted. k scales the stride (clip in-betweens)."""
    o = 'R' if side == 'L' else 'L'
    centre(arm, (0.0, -0.03 * k, -0.05 * k + 0.03 * (1 - k)))
    foot(arm, side, (0.0, -0.22 * k, 0.30 * k), pitch=25 * k)
    foot(arm, o, (0.0, 0.32 * k, 0.07 * k), pitch=55 * k)
    sgn = 1 if side == 'L' else -1
    spine(arm, pitch=8 * k, yaw=-10 * sgn * k, lower_pitch=4 * k)
    head(arm, yaw=6 * sgn * k)
    arm_pose(arm, o, (0.15, -0.55 * k, -1.0 + 0.3 * k), 90, (0, -1, 0))
    arm_pose(arm, side, (0.15, 0.55 * k, -1.0 + 0.2 * k), 90, (0, -1, 0))
    for t in 'LR':
        fingers(arm, t, 0.5)


def pose_run_l(arm):
    _run(arm, 'L')


def pose_run_r(arm):
    _run(arm, 'R')


def pose_jump_tuck(arm):
    """Tuck jump at the top: body raised 30 cm, both knees pulled up (thighs ~85 deg,
    knees ~120 deg), arms reaching forward-up, skirt and hair lifted by the fall."""
    move(arm, '全ての親', (0.0, 0.0, -0.30))     # framing: the body stays where render.py looks
    centre(arm, (0.0, 0.0, 0.30))
    for t in 'LR':
        foot(arm, t, (0.02, -0.234, 0.758), pitch=30)
        arm_pose(arm, t, (0.35, -0.6, 0.55), 30, (0, 0, 1))
    spine(arm, pitch=12)
    skirt_flare(arm, 18, back=-6)
    hair_swing(arm, back=-15)


def pose_high_kick(arm):
    """Front kick: left leg straight, raised 85 deg (FK), foot pointed; standing leg
    straight, torso leaned back 12 deg, arms out for balance."""
    centre(arm, (0.0, 0.04, -0.01))
    leg_fk(arm, 'L', (0.05, -1.0, 0.09), 0, ankle=25)
    foot(arm, 'R', (0.0, 0.02, 0.0))
    spine(arm, pitch=-10, lower_pitch=-4)
    arm_pose(arm, 'L', (1.0, 0.25, 0.05), 15, (0, -1, 0))
    arm_pose(arm, 'R', (1.0, -0.25, 0.15), 15, (0, -1, 0))


def pose_arms_crossed(arm):
    """Arms crossed over the chest: upper arms at the sides, forearms folded across,
    left over right, hands at the opposite upper arms."""
    arm_pose(arm, 'L', (0.25, -0.55, -1.0), 110, (-1.0, -0.35, 0.25), pronate=10)
    arm_pose(arm, 'R', (0.25, -0.50, -1.0), 106, (-1.0, -0.20, 0.30), pronate=10)


def pose_hands_behind_head(arm):
    """Hands clasped behind the head: arms raised out sideways and up, elbows ~140 deg."""
    for t in 'LR':
        arm_pose(arm, t, (0.85, 0.30, 0.55), 140, (-0.7, 0.4, 0.4), shrug=5)
    head(arm, pitch=-5)


def pose_hands_behind_back(arm):
    """Hands clasped behind the back at the waist: upper arms back-down, forearms across."""
    for t in 'LR':
        arm_pose(arm, t, (0.22, 0.42, -1.0), 95, (-1.0, 0.25, 0.2), pronate=-20)


def pose_hand_to_shoulder(arm):
    """Left hand on the right shoulder (arm across the chest), right arm hanging."""
    arm_pose(arm, 'L', (-0.05, -0.90, -0.30), 122, (-1.0, 0.2, 0.6))
    arm_pose(arm, 'R', (0.15, 0.05, -1.0), 10)
    head(arm, yaw=-10, pitch=8)


def pose_hands_on_hips(arm):
    """Hands on the hips, elbows out (akimbo)."""
    for t in 'LR':
        arm_pose(arm, t, (0.85, 0.15, -0.60), 80, (-0.8, 0.0, -0.6), pronate=20, wrist=-10)


def pose_reach_up_back(arm):
    """Stretching: both arms reaching up and back overhead, back arched."""
    move(arm, '全ての親', (0.0, 0.0, -0.17))     # keep the hands inside render.py's frame
    for t in 'LR':
        arm_pose(arm, t, (0.30, 0.30, 1.0), 10, (0, -1, 0), shrug=10)
    spine(arm, pitch=-14)
    head(arm, pitch=-12)


def pose_hug_self(arm):
    """Hugging herself: arms wrapped around the ribs, hands on the opposite flanks."""
    arm_pose(arm, 'L', (-0.05, -0.90, -0.45), 112, (-1.0, 0.45, 0.05))
    arm_pose(arm, 'R', (-0.05, -0.95, -0.35), 108, (-1.0, 0.35, 0.15))
    spine(arm, pitch=8)
    head(arm, pitch=10, roll=8)


def pose_twist_bend(arm):
    """Torso twisted 35 deg to her left and bent 30 deg forward, arms hanging."""
    centre(arm, (0.0, 0.02, -0.02))
    spine(arm, pitch=30, yaw=35, lower_pitch=6)
    for t in 'LR':
        rig_pose.bend_posed(arm, f'腕.{t}', (0, -1, 0), 25)


def pose_lie_back_elbows(arm):
    """Lying back on the elbows on the floor, legs straight forward (FK), torso leaned
    back ~50 deg, upper arms vertical under the shoulders, forearms flat forward."""
    centre(arm, (0.0, 0.10, -0.72))
    for t in 'LR':
        leg_fk(arm, t, (0.10, -1.0, -0.03), 8, ankle=20)
    spine(arm, pitch=-45)
    head(arm, pitch=35)
    for t in 'LR':
        # in the leaned-back torso's frame: upper arm down-back, forearm forward
        arm_pose(arm, t, (0.2, 0.72, -0.70), 95, (0, -0.77, -0.64))


def pose_look_over_shoulder(arm):
    """Looking back over her left shoulder: torso twisted 35 deg, head turned 55 deg on it
    and tipped down 10 deg, left arm a little back."""
    spine(arm, yaw=35, lower_pitch=0)
    head(arm, yaw=55, pitch=10, roll=-5)
    arm_pose(arm, 'L', (0.2, 0.35, -1.0), 20)
    arm_pose(arm, 'R', (0.2, -0.25, -1.0), 20)


def pose_curtsy(arm):
    """Curtsy: right foot crossed behind the left on its toes, both knees bent, torso and
    head bowed a little, hands holding the skirt out at the hem."""
    centre(arm, (0.0, 0.03, -0.10))
    foot(arm, 'L', (0.0, -0.03, 0.0), yaw=8)
    foot(arm, 'R', (-0.13, 0.20, 0.03), pitch=35)
    spine(arm, pitch=12)
    head(arm, pitch=12, roll=-6)
    for t in 'LR':
        arm_pose(arm, t, (0.55, -0.15, -1.0), 22, (0, -1, 0), pronate=-30)
        fingers(arm, t, 0.6)


def pose_dance_sway(arm):
    """MMD dance key: left arm up overhead, hip swayed to her right, right knee bent with
    the heel up, torso counter-bent, head tilted."""
    move(arm, '全ての親', (0.0, 0.0, -0.08))     # framing: keeps the raised hand in render.py's frame
    centre(arm, (-0.05, 0.0, -0.05))
    spine(arm, roll=10, lower_roll=-8)
    foot(arm, 'R', (0.0, -0.06, 0.03), pitch=30)
    arm_pose(arm, 'L', (0.25, -0.05, 1.0), 25, (-1, 0, 0), shrug=6)
    arm_pose(arm, 'R', (0.85, -0.15, -0.60), 80, (-0.8, 0.0, -0.6), pronate=20)
    head(arm, roll=-10, yaw=10)


def pose_dance_point(arm):
    """MMD dance key: right arm pointing forward-up, left hand on the chest, left knee bent
    forward on its toes, torso turned a little to her right."""
    centre(arm, (0.0, 0.0, -0.04))
    foot(arm, 'L', (-0.02, -0.10, 0.04), pitch=35)
    spine(arm, yaw=-12, roll=-4)
    arm_pose(arm, 'R', (0.25, -1.0, 0.55), 10, (0, 0, 1), pronate=30)
    arm_pose(arm, 'L', (0.25, -0.60, -1.0), 118, (-1.0, -0.4, 0.4))
    fingers(arm, 'R', 0.7)
    head(arm, yaw=-15, roll=6)


def pose_dance_heart(arm):
    """MMD dance key: both arms up making a heart over the head, elbows out, a little
    side lean, one knee bent."""
    for t in 'LR':
        arm_pose(arm, t, (0.65, -0.15, 0.80), 105, (-1.0, 0.0, 0.3), shrug=6)
        fingers(arm, t, 0.4)
    centre(arm, (0.03, 0.0, -0.03))
    spine(arm, roll=-6)
    foot(arm, 'L', (0.0, -0.05, 0.02), pitch=20)
    head(arm, roll=8)


def pose_dance_clap(arm):
    """MMD dance key: knees bent, hands clapping in front of the chest, torso bent 15 deg."""
    centre(arm, (0.0, 0.03, -0.12))
    for t in 'LR':
        foot(arm, t, (0.03, 0.0, 0.0), yaw=10)
        arm_pose(arm, t, (0.15, -0.75, -0.5), 105, (-0.5, -0.5, 0.7), pronate=-60)
    spine(arm, pitch=15)
    head(arm, pitch=-10)


EXTENDED = {
    'sit_chair': pose_sit_chair, 'seiza': pose_seiza, 'kneel_one': pose_kneel_one,
    'cross_legged': pose_cross_legged, 'deep_lunge': pose_deep_lunge, 'run_l': pose_run_l,
    'run_r': pose_run_r, 'jump_tuck': pose_jump_tuck, 'high_kick': pose_high_kick,
    'arms_crossed': pose_arms_crossed, 'hands_behind_head': pose_hands_behind_head,
    'hands_behind_back': pose_hands_behind_back, 'hand_to_shoulder': pose_hand_to_shoulder,
    'hands_on_hips': pose_hands_on_hips, 'reach_up_back': pose_reach_up_back, 'hug_self': pose_hug_self,
    'twist_bend': pose_twist_bend, 'lie_back_elbows': pose_lie_back_elbows,
    'look_over_shoulder': pose_look_over_shoulder, 'curtsy': pose_curtsy, 'dance_sway': pose_dance_sway,
    'dance_point': pose_dance_point, 'dance_heart': pose_dance_heart, 'dance_clap': pose_dance_clap,
}
FK_POSES = ('cross_legged', 'high_kick', 'lie_back_elbows')


# ---------------------------------------------------------------- motion clips
# A clip: (frames, [(frame, key function(arm))...]). Keys are poses built from rest; the
# clip keys every changed bone channel at each key frame (Bezier, auto-clamped handles).

def _walk_key(ph, stride=1.0):
    """Walk cycle (in place, like an MMD walk motion) at phase ph (0..1): left foot
    forward at 0, right forward at 0.5; a foot lifts while it swings forward."""
    def key(arm):
        a = 2 * math.pi * ph
        for t, s in (('L', 1), ('R', -1)):
            y = -0.15 * s * math.cos(a) * stride
            swing = max(0.0, -s * math.sin(a))            # 1 mid-swing, 0 in stance
            foot(arm, t, (0.0, y, 0.06 * swing * stride), pitch=10 * swing)
            arm_pose(arm, t, (0.15, 0.30 * s * math.cos(a), -1.0), 18 + 10 * max(0.0, s * math.cos(a)),
                     (0, -1, 0))
        # lowest at double support (feet apart), highest passing
        centre(arm, (0.0, -0.01, -0.035 - 0.012 * math.cos(4 * math.pi * ph)))
        spine(arm, yaw=-7 * math.cos(a), pitch=3)
        turn(arm, '下半身', (0, 0, 1), 5 * math.cos(a))
        head(arm, yaw=3 * math.cos(a))
        skirt_flare(arm, 3)
    return key


def _run_key(ph):
    """Run cycle (in place) at phase ph: left foot forward at 0; the recovery leg tucks up
    while it swings forward, the push-off foot leaves on its toes; arms opposite, 90 deg."""
    def key(arm):
        a = 2 * math.pi * ph
        c = math.cos(a)
        for t, s in (('L', 1), ('R', -1)):
            fwd = s * c                                   # +1: this leg forward
            swing = max(0.0, -s * math.sin(a))
            foot(arm, t, (0.0, -0.24 * fwd, 0.04 + 0.26 * swing), pitch=15 + 35 * max(0.0, -fwd))
            arm_pose(arm, t, (0.15, 0.55 * fwd, -0.85 + 0.25 * abs(fwd)), 90, (0, -1, 0))
            fingers(arm, t, 0.5)
        centre(arm, (0.0, -0.03, -0.05 + 0.03 * abs(math.sin(a))))
        spine(arm, pitch=8, yaw=-10 * c, lower_pitch=4)
        turn(arm, '下半身', (0, 0, 1), 8 * c)
        head(arm, yaw=7 * c)
        skirt_flare(arm, 6, back=6)
        hair_swing(arm, back=8)
    return key


def _turn_key(u):
    """Turning 180 deg in place to her left over u = 0..1, stepping L, R, L, R."""
    steps = (('L', 0.00, 0.30, 0, 80), ('R', 0.20, 0.55, 0, 130), ('L', 0.50, 0.80, 80, 180),
             ('R', 0.70, 1.00, 130, 180))

    def smooth(x):
        x = min(1.0, max(0.0, x))
        return x * x * (3 - 2 * x)

    def key(arm):
        body = 180 * smooth(u * 1.1 - 0.05)
        centre(arm, (0.0, 0.0, -0.03 - 0.02 * math.sin(math.pi * u)), yaw=body)
        rest_c = arm.pose.bones['センター'].bone.head_local
        for t in 'LR':
            ang, lift = 0.0, 0.0
            for tt, a0, a1, g0, g1 in steps:
                if tt != t:
                    continue
                if u >= a1:
                    ang = g1
                elif u > a0:
                    k = smooth((u - a0) / (a1 - a0))
                    ang = g0 + (g1 - g0) * k
                    lift = 0.05 * math.sin(math.pi * k)
                    break
                else:
                    ang = g0
                    break
            # the foot turned `ang` about the vertical through the centre
            q = Quaternion((0, 0, 1), math.radians(ang))
            ik = arm.pose.bones[f'足ＩＫ.{t}']
            a0v = ik.bone.head_local
            pos = q @ (a0v - Vector((rest_c.x, rest_c.y, a0v.z))) + Vector((rest_c.x, rest_c.y, a0v.z))
            d = q @ (arm.pose.bones[f'つま先ＩＫ.{t}'].bone.head_local - a0v)
            s = 1 if t == 'L' else -1
            off = pos - a0v
            foot(arm, t, (off.x * s, off.y, off.z + lift), toe_dir=(d.x * s, d.y, d.z))
            arm_pose(arm, t, (0.35, -0.1, -1.0), 30, (0, -1, 0))
        spine(arm, yaw=12 * math.sin(math.pi * u))
        head(arm, yaw=20 * math.sin(math.pi * u))
    return key


def _sit_key(amount, lean):
    def key(arm):
        _sit(arm, amount, lean)
        head(arm, pitch=4)
    return key


def _spin_key(u):
    """Spin 360 deg to her left with the arms out, over u = 0..1 (feet turn with her)."""
    def smooth(x):
        return x * x * (3 - 2 * x)

    def key(arm):
        ang = 360 * smooth(u)
        speed = 6 * u * (1 - u)                  # 0..1.5, peak mid-spin
        centre(arm, (0.0, 0.0, -0.02), yaw=ang)
        rest_c = arm.pose.bones['センター'].bone.head_local
        q = Quaternion((0, 0, 1), math.radians(ang))
        for t in 'LR':
            ik = arm.pose.bones[f'足ＩＫ.{t}']
            a0v = ik.bone.head_local
            piv = Vector((rest_c.x, rest_c.y, a0v.z))
            pos = q @ (a0v - piv) + piv
            d = q @ (arm.pose.bones[f'つま先ＩＫ.{t}'].bone.head_local - a0v)
            s = 1 if t == 'L' else -1
            off = pos - a0v
            foot(arm, t, (off.x * s, off.y, off.z + 0.03 * min(1.0, speed)), toe_dir=(d.x * s, d.y, d.z - 0.04))
            arm_pose(arm, t, (1.0, 0.1 * speed, 0.05 + 0.1 * (1 - min(1.0, speed))), 15, (0, -1, 0))
        skirt_flare(arm, 22 * min(1.0, speed))
        hair_swing(arm, yaw=12 * min(1.0, speed), back=-6 * min(1.0, speed))
        head(arm, yaw=-10 * min(1.0, speed))
    return key


CLIPS = {
    # 2 walk cycles of 30 frames (1 s each), keyed every 1/8 cycle
    'walk': (60, [(int(round(60 * i / 16)), _walk_key((i / 8) % 1.0)) for i in range(17)]),
    # 2 run cycles of 20 frames, keyed every 1/8 cycle (2.5 frames -> rounded)
    'run': (40, [(int(round(40 * i / 16)), _run_key((i / 8) % 1.0)) for i in range(17)]),
    'turn': (45, [(int(round(45 * i / 9)), _turn_key(i / 9)) for i in range(10)]),
    'sit_stand': (90, [(0, _sit_key(0.0, 0.0)), (12, _sit_key(0.25, 18.0)), (24, _sit_key(0.65, 30.0)),
                       (36, _sit_key(1.0, 12.0)), (50, _sit_key(1.0, 4.0)), (58, _sit_key(1.0, 22.0)),
                       (68, _sit_key(0.70, 32.0)), (78, _sit_key(0.30, 16.0)), (90, _sit_key(0.0, 0.0))]),
    'spin': (45, [(int(round(45 * i / 9)), _spin_key(i / 9)) for i in range(10)]),
    'idol_dance': (90, [(0, pose_rest), (12, pose_dance_sway), (24, pose_dance_point), (36, pose_dance_clap),
                        (48, pose_dance_heart), (60, pose_hands_on_hips), (72, pose_run_l), (82, pose_dance_sway),
                        (90, pose_rest)]),
}


def clip_frames(name):
    return CLIPS[name][0]


def build_clip(arm, name):
    """Key clip `name` on the armature (a fresh action 'clip_<name>'). Returns its frame
    count. Each key pose is applied from rest and every pose-bone channel that differs
    from rest in any key is keyed (quaternions kept in one hemisphere)."""
    frames, keys = CLIPS[name]
    snaps = []
    for f, fn in keys:
        rig_pose.reset_pose(arm)
        fn(arm)
        bpy.context.view_layer.update()
        muted = [pb.name for pb in arm.pose.bones for c in pb.constraints if c.type == 'IK' and c.mute]
        if muted:
            raise ValueError(f'clip {name}: key at frame {f} mutes IK ({muted}); clips must use IK legs')
        snap = {}
        for pb in arm.pose.bones:
            q = pb.rotation_quaternion.copy() if pb.rotation_mode == 'QUATERNION' else \
                pb.matrix_basis.to_quaternion()
            snap[pb.name] = (pb.location.copy(), q, pb.scale.copy())
        snaps.append((f, snap))
    rig_pose.reset_pose(arm)
    # bones whose transform channels drivers write (follow / append helpers, skirt drape) are
    # not keyed (drivers on custom properties or constraints do not count)
    driven = set()
    if arm.animation_data:
        for fc in arm.animation_data.drivers:
            dp = fc.data_path
            if dp.startswith('pose.bones["') and dp.rsplit('.', 1)[-1] in (
                    'location', 'rotation_quaternion', 'rotation_euler', 'rotation_axis_angle', 'scale'):
                driven.add(dp.split('"')[1])
    moved = set()
    for _, snap in snaps:
        for n, (loc, q, sc) in snap.items():
            if n not in driven and (loc.length > 1e-7 or abs(abs(q.w) - 1.0) > 1e-7 or
                                    (sc - Vector((1, 1, 1))).length > 1e-7):
                moved.add(n)
    act = bpy.data.actions.get(f'clip_{name}')
    if act:
        bpy.data.actions.remove(act)
    if arm.animation_data is None:
        arm.animation_data_create()
    arm.animation_data.action = bpy.data.actions.new(f'clip_{name}')
    arm.animation_data.action['levi_bones'] = sorted(moved)     # keyed bones (motion_vmd.py)
    arm.animation_data.action['levi_arm'] = arm.name
    prev = {}
    sc = bpy.context.scene
    for f, snap in snaps:
        for n in sorted(moved):
            pb = arm.pose.bones[n]
            loc, q, s = snap[n]
            if n in prev and prev[n].dot(q) < 0:
                q = -q
            prev[n] = q
            pb.rotation_mode = 'QUATERNION'
            pb.location, pb.rotation_quaternion, pb.scale = loc, q, s
            pb.keyframe_insert('location', frame=f)
            pb.keyframe_insert('rotation_quaternion', frame=f)
            pb.keyframe_insert('scale', frame=f)
    sc.render.fps = FPS
    sc.frame_start, sc.frame_end = 0, frames
    return frames


_BUILT = set()


def apply_clip_frame(arm, name, frame):
    """Pose the armature at `frame` of clip `name` (building its action if needed)."""
    act = arm.animation_data.action if arm.animation_data else None
    if act is None or act.name != f'clip_{name}':
        rig_pose.reset_pose(arm)
        built = bpy.data.actions.get(f'clip_{name}')
        # rebuilt once per session: an action saved in a .blend may predate CLIPS or the rig
        if built is None or (arm.name, name) not in _BUILT:
            build_clip(arm, name)
            _BUILT.add((arm.name, name))
        else:
            arm.animation_data_create()
            arm.animation_data.action = built
            if built.slots and arm.animation_data.action_slot is None:
                arm.animation_data.action_slot = built.slots[0]
    bpy.context.scene.frame_set(int(frame))
    bpy.context.view_layer.update()


def clear_clip(arm):
    if arm.animation_data and arm.animation_data.action:
        arm.animation_data.action = None
