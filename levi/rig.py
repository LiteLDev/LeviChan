"""MMD-standard armature for Levi, placed from spec.L landmarks, plus rule-based skinning.

    from levi import rig
    arm = rig.build_rig()      # after builder.build_all(...)

Spine/head bones come from spec.L. Limb joints (shoulder, elbow, wrist,
fingertip, hip, knee, ankle, toe) are fitted to the `body` part when it exists:
a `levi_joints` dict on a body object wins, otherwise cross-section centroids of
the body mesh around each landmark joint; spec.L is only the fallback. Secondary chains (back hair, side locks, skirt,
sleeve drapes) are created only when the matching part is in the scene, and
follow that part's actual vertices so they sit inside the geometry.

Skinning is positional, so it does not care whether a garment is manifold or
split into many objects: every bone is an elongated Gaussian envelope (lateral
radius `r`, end radius `r_end` beyond its head/tail), each collection only sees
the bones its rule allows, and weights keep the 4 strongest influences,
normalized. Objects that touch at a seam get the same weights from the same
formula, so seams don't tear.

Blender bone names are the MMD Japanese names with Blender's .L/.R suffix
(腕.L). PMX names (左腕 / Arm_L) are kept in BONE_NAMES for export.
"""
import math

import bpy
import numpy as np
from mathutils import Vector

from . import common, spec

ARM_NAME = 'Levi_arm'
RIG_COLLECTION = '_rig'
MAX_INFLUENCE = 4
MIN_WEIGHT = 0.01
SHARPNESS = 2.0          # Gaussian exponent on the normalized envelope distance

L = spec.L
SIDES = (('L', 1.0, '左'), ('R', -1.0, '右'))


# ---------------------------------------------------------------- bone table
class Bone:
    __slots__ = ('name', 'jp', 'en', 'head', 'tail', 'parent', 'connect', 'deform',
                 'r', 'r_end', 'group', 'meta')

    def __init__(self, name, jp, en, head, tail, parent=None, connect=False,
                 deform=True, r=0.05, r_end=None, group='Body', meta=None):
        self.name, self.jp, self.en = name, jp, en
        self.head, self.tail = Vector(head), Vector(tail)
        self.parent, self.connect, self.deform = parent, connect, deform
        self.r = r
        self.r_end = r * 0.6 if r_end is None else r_end
        self.group = group
        self.meta = meta or {}


def _mx(p, s):
    return Vector((p[0] * s, p[1], p[2]))


KNEE_ROW = 700
JOINT_KEYS = ('shoulder_joint', 'elbow', 'wrist', 'fingertip', 'hip', 'knee', 'ankle', 'toe')


def landmark_joints():
    """Limb joints (character's left side, +X) from spec.L only."""
    return {
        'shoulder_joint': Vector(L['shoulder_joint']), 'elbow': Vector(L['elbow']),
        'wrist': Vector(L['wrist']), 'fingertip': Vector(L['fingertip']),
        'hip': Vector((L['leg_center_x'], 0.0, L['crotch_z'] + 0.065)),
        # the knee sits slightly forward so IK bends it the right way. Local correction:
        # spec says row 740, but the knee kink on the sheet (and the body part's leg
        # loops) is at row ~700; 740 left a 14 cm shin under a 50 cm thigh.
        'knee': Vector((L['leg_center_x'], -0.012, spec.px_to_z(KNEE_ROW))),
        'ankle': Vector((L['ankle_center_x'], 0.0, L['ankle_z'])),
        'toe': Vector((L['toe_tip_x'], L['toe_tip_y'], 0.012)),
    }


def _slab_centroid(pts, center, axis, half=0.012, radius=0.07, min_pts=6):
    """Centroid of the cross-section of `pts` through `center` perpendicular to `axis`."""
    rel = pts - np.array(center)
    a = np.array(axis.normalized())
    along = rel @ a
    lat = np.linalg.norm(rel - along[:, None] * a, axis=1)
    sel = pts[(np.abs(along) <= half) & (lat <= radius)]
    if len(sel) < min_pts:
        return None
    c = Vector(sel.mean(0))
    return c - Vector(a) * Vector(a).dot(c - Vector(center))   # keep the along-axis position


MAX_FIT_SHIFT = 0.08


def fit_joints(body_objs):
    """Limb joints fitted to the body mesh; spec.L landmarks where the mesh gives no answer.

    Priority: a 'levi_joints' custom property (dict key -> (x, y, z), left side) on any
    body object, then cross-section centroids of the body mesh around each landmark
    joint (both sides fitted and averaged, mirrored to +X), then the landmark.
    """
    J = landmark_joints()
    if not body_objs:
        return J, {}
    stored = {}
    for o in body_objs:
        d = o.get('levi_joints')
        if d:
            for k in JOINT_KEYS:
                if k in d:
                    stored[k] = Vector(tuple(d[k]))
    pts = _world_verts(body_objs)
    fitted = {}
    if len(pts):
        mirrored = pts * np.array([-1.0, 1.0, 1.0])
        per_side = [pts[pts[:, 0] > 0.01], mirrored[mirrored[:, 0] > 0.01]]
        arm_chain = ('shoulder_joint', 'elbow', 'wrist', 'fingertip')
        for _ in range(3):          # later passes re-slice along the corrected directions
            for k in ('shoulder_joint', 'elbow', 'wrist', 'hip', 'knee', 'ankle'):
                if k in arm_chain:
                    i = arm_chain.index(k)
                    prev = J[arm_chain[max(i - 1, 0)]] if i else J['shoulder_joint'] - (J['elbow'] - J['shoulder_joint'])
                    axis = (J[arm_chain[i + 1]] - prev)
                    side = [p[p[:, 0] > J['shoulder_joint'].x * 0.85] for p in per_side]
                else:
                    axis = Vector((0, 0, 1))
                    side = per_side
                cs = [_slab_centroid(p, J[k], axis) for p in side]
                cs = [c for c in cs if c is not None]
                if not cs:
                    continue
                c = sum(cs, Vector()) / len(cs)
                if (c - landmark_joints()[k]).length <= MAX_FIT_SHIFT:
                    J[k] = c
                    fitted[k] = c
            # fingertip / toe: extreme vertices along the hand / foot direction
            # a slab only fixes the arm's direction, not where along it the joint is: keep the
            # landmark upper-arm / forearm lengths along the fitted directions
            lmj = landmark_joints()
            for a, b in (('shoulder_joint', 'elbow'), ('elbow', 'wrist')):
                if b in fitted:
                    J[b] = J[a] + (J[b] - J[a]).normalized() * (lmj[b] - lmj[a]).length
                    fitted[b] = J[b]
            for k, base, prev in (('fingertip', 'wrist', 'elbow'), ('toe', 'ankle', 'knee')):
                # farthest vertex past the (fitted) base joint, along the landmark hand/foot
                # direction bent toward the fitted limb direction
                reach = (lmj[k] - lmj[base]).length * 1.3
                d = ((lmj[k] - lmj[base]).normalized() + (J[base] - J[prev]).normalized() * 0.5).normalized()
                cand = []
                for p in per_side:
                    rel = p - np.array(J[base])
                    near = p[(np.linalg.norm(rel, axis=1) < reach) & (rel @ np.array(d) > 0)]
                    if len(near):
                        cand.append(Vector(near[np.argmax(near @ np.array(d))]))
                if cand:
                    c = sum(cand, Vector()) / len(cand)
                    if k == 'toe':
                        c.z = max(c.z, 0.012)
                    J[k] = c
                    fitted[k] = c
    if fitted.get('knee') is not None:
        J['knee'].y = min(J['knee'].y, (J['hip'].y + J['ankle'].y) / 2 - 0.008)   # keep a forward bend
    J.update(stored)
    fitted.update(stored)
    return J, fitted


EYE_DEPTH = 0.02
TWIST_AT = 0.6        # twist bones start this far down their limb segment (semi-standard)
TWIST_RAMP = (0.1, 0.95)   # ... and take over that segment's weight between these fractions


def fit_head(head_objs):
    """Head centre depth and the left eye position from the head part's mesh.

    Returns {'head_y', 'eye'} for the keys the mesh answers. The eyes are painted
    into the face texture, so the eye bone goes on the face surface at the landmark
    eye (x, z), EYE_DEPTH behind it (about the eyeball centre).
    """
    out = {}
    pts = _world_verts(head_objs)
    skull = pts[pts[:, 2] > L['chin_z']] if len(pts) else pts
    if len(skull) < 8:
        return out
    out['head_y'] = float(skull[:, 1].min() + skull[:, 1].max()) / 2
    ex, ez = L['eye_x'], L['eye_z']
    near = skull[(np.abs(np.abs(skull[:, 0]) - ex) < 0.01) & (np.abs(skull[:, 2] - ez) < 0.01)]
    if len(near):
        out['eye'] = Vector((ex, float(near[:, 1].min()) + EYE_DEPTH, ez))
    return out


FINGER_KNOTS = (0.0, 0.44, 0.75, 1.0)   # knuckle, middle joints, tip along a finger's base..tip
FINGER_NAMES = (('親指', 'Thumb'), ('人指', 'IndexFinger'), ('中指', 'MiddleFinger'),
                ('薬指', 'RingFinger'), ('小指', 'LittleFinger'))


def _mesh_islands(objs):
    """[(world points (n, 3))] per loose part of the meshes `objs`."""
    out = []
    for o in objs:
        co = _world_verts([o])
        if not len(co):
            continue
        lab = _islands(len(co), _topology(o, co))
        out += [co[lab == k] for k in np.unique(lab)]
    return out


def _finger_line(pts, d):
    """Knuckle .. tip joint points (FINGER_KNOTS) along the principal axis of one finger."""
    c = pts.mean(0)
    _, _, vt = np.linalg.svd(pts - c, full_matrices=False)
    a = vt[0] if vt[0] @ np.array(d) > 0 else -vt[0]
    t = (pts - c) @ a
    t0, t1 = float(t.min()), float(t.max())
    ln = t1 - t0
    base, tip = t0 + 0.06 * ln, t1 - 0.04 * ln
    out = []
    for k in FINGER_KNOTS:
        tk = base + (tip - base) * k
        sel = pts[np.abs(t - tk) < 0.08 * ln]
        p = sel.mean(0) if len(sel) >= 3 else c + a * tk
        out.append(Vector(p - a * ((p - c) @ a - tk)))     # keep it exactly at tk along the axis
    return out, a


def fit_fingers(body_objs, J):
    """{jp: [knuckle, joint, joint, tip]} (left side) from the body's loose finger parts.

    The hand's five fingers are the loose parts lying past the wrist within reach of
    the fingertip; the thumb is the one most angled away from the hand direction, the
    others are ordered from the thumb side. Both hands are fitted (the right one
    mirrored) and averaged. Returns {} unless every finger is found."""
    wr, tip = J['wrist'], J['fingertip']
    d = (tip - wr).normalized()
    hand_len = (tip - wr).length
    fwd = Vector((0, -1, 0))
    f = (fwd - d * d.dot(fwd)).normalized()
    sides = []
    islands = _mesh_islands(body_objs)
    for s in (1.0, -1.0):
        found = []
        for pts in islands:
            p = pts * np.array([s, 1.0, 1.0])
            c = Vector(p.mean(0))
            ext = float(np.linalg.norm(p - p.mean(0), axis=1).max())
            if len(p) >= 8 and (c - wr).dot(d) > 0 and (c - wr).length < 1.3 * hand_len and ext < 0.6 * hand_len:
                found.append(_finger_line(p, d))
        if len(found) != 5:
            continue
        thumb = max(range(5), key=lambda i: -abs(float(found[i][1] @ np.array(d))))
        rest = sorted((i for i in range(5) if i != thumb), key=lambda i: -found[i][0][0].dot(f))
        sides.append([found[i][0] for i in [thumb] + rest])
    if not sides:
        return {}
    return {jp: [sum((sd[i][k] for sd in sides), Vector()) / len(sides) for k in range(4)]
            for i, (jp, _) in enumerate(FINGER_NAMES)}


def finger_chains(F, wr, d, f, hand_len, palm_end, fingers):
    """(jp, en, 4 joint points) for the thumb and the four fingers: fitted ones from F,
    otherwise a generic hand laid along the hand direction."""
    t_pts = [wr + d * 0.08 * hand_len + f * 0.012, wr + d * 0.25 * hand_len + f * 0.028,
             wr + d * 0.42 * hand_len + f * 0.038, wr + d * 0.58 * hand_len + f * 0.045]
    yield '親指', 'Thumb', F.get('親指', t_pts)
    for jp, en, off, ln in fingers:
        base = palm_end + f * off
        yield jp, en, F.get(jp, [base + d * (t * ln * hand_len) for t in (0.0, 0.4, 0.73, 1.0)])


JOINT_AUX_LEN = 0.04  # length of the elbow / knee helper bones
JOINT_AUX_BLEND = 0.06  # half-width (m) along the limb of the band the helper carries
# per part: (blend start before the joint, blend end after it, use the half-turn helper).
# Puffed sleeves spread the elbow bend over the whole balloon instead (no helper): from
# 8 cm above to 15 cm below the joint.
JOINT_BAND = {'sleeves': (0.06, 0.06, True)}
JOINT_AUX_FOLLOW = 0.5  # share of the lower bone's rotation the helper takes


def _joint_aux(add, jp, en, joint, nxt, parent, lower, upper, s, sfx, jp_side, en_sfx, group):
    """Elbow / knee helper: a deform bone at the joint, child of the upper limb, that takes
    JOINT_AUX_FOLLOW of the lower bone's rotation (回転付与). The band of skin and cloth
    around the joint follows it, so a deep bend is shared between two half-turns instead
    of being stretched (or collapsed) across one blend."""
    tail = joint + (nxt - joint).normalized() * JOINT_AUX_LEN
    add(Bone(jp + sfx, jp_side + jp, en + en_sfx, _mx(joint, s), _mx(tail, s), parent, group=group,
             meta={'follow': (lower, JOINT_AUX_FOLLOW), 'joint_aux': (list(upper), lower)}))


def _core_bones(J=None, H=None, F=None):
    """Core MMD skeleton. Spine/head from landmarks (head depth and eyes from the
    head mesh fit H when given), limbs from joints J (left side, built at +X and
    mirrored)."""
    J = J or landmark_joints()
    H = H or {}
    F = F or {}
    b = []
    add = b.append
    hc_y = H.get('head_y', L['head_center_y'])
    spine_y = L['waist_center_y'] * 0.8
    chest_y = L['chest_center_y'] * 0.85
    neck_y = L['neck_center_y']
    z_pivot = (L['waist_z'] + L['hip_z']) / 2         # 上半身 / 下半身 split
    z_chest = (L['waist_z'] + L['bodice_top_z']) / 2
    z_neck0 = L['shoulder_z'] + 0.005
    z_head0 = L['choker_z'] + 0.015
    z_center = 0.4 * spec.HEIGHT

    add(Bone('全ての親', '全ての親', 'ParentNode', (0, 0, 0), (0, 0, 0.1), deform=False, group='Root'))
    add(Bone('センター', 'センター', 'Center', (0, spine_y, z_center), (0, spine_y, z_center - 0.06),
             '全ての親', deform=False, group='Root'))
    add(Bone('グルーブ', 'グルーブ', 'Groove', (0, spine_y, z_center + 0.04), (0, spine_y, z_center + 0.1),
             'センター', deform=False, group='Root'))
    add(Bone('腰', '腰', 'Waist', (0, spine_y, z_pivot - 0.05), (0, spine_y, z_pivot),
             'グルーブ', deform=False, group='Root'))
    add(Bone('上半身', '上半身', 'UpperBody', (0, spine_y, z_pivot), (0, chest_y, z_chest),
             '腰', r=0.09, r_end=0.05))
    add(Bone('上半身2', '上半身2', 'UpperBody2', (0, chest_y, z_chest), (0, neck_y, z_neck0),
             '上半身', connect=True, r=0.09, r_end=0.05))
    add(Bone('首', '首', 'Neck', (0, neck_y, z_neck0), (0, hc_y, z_head0),
             '上半身2', connect=True, r=0.03, r_end=0.02))
    add(Bone('頭', '頭', 'Head', (0, hc_y, z_head0), (0, hc_y, L['head_top_z']),
             '首', connect=True, r=0.09, r_end=0.02))
    eyes = (0, hc_y - 0.06, L['head_top_z'] + 0.05)
    add(Bone('両目', '両目', 'Eyes', eyes, (eyes[0], eyes[1] - 0.03, eyes[2]), '頭', deform=False))
    eye = H.get('eye', Vector((L['eye_x'], L['nose_tip_y'] + 0.035, L['eye_z'])))
    add(Bone('下半身', '下半身', 'LowerBody', (0, spine_y, z_pivot), (0, -0.02, L['crotch_z'] + 0.02),
             '腰', r=0.10, r_end=0.05))

    hand = J['fingertip'] - J['wrist']
    hand_len = hand.length
    d = hand.normalized()
    fwd = Vector((0, -1, 0))
    f = (fwd - d * d.dot(fwd)).normalized()          # across the palm, toward the thumb
    wrist = J['wrist']
    palm_end = wrist + d * 0.45 * hand_len
    fingers = (  # (jp, en, lateral offset, length factor)
        ('人指', 'IndexFinger', 0.012, 0.50),
        ('中指', 'MiddleFinger', 0.004, 0.55),
        ('薬指', 'RingFinger', -0.004, 0.50),
        ('小指', 'LittleFinger', -0.011, 0.40),
    )
    for tag, s, jp_side in SIDES:
        sfx = '.' + tag
        en_sfx = '_' + tag
        sj, el, wr = J['shoulder_joint'], J['elbow'], wrist
        add(Bone('目' + sfx, jp_side + '目', 'Eye' + en_sfx, _mx(eye, s),
                 _mx(eye - Vector((0, 0.03, 0)), s), '頭', r=0.02, r_end=0.015, group='Body'))
        add(Bone('肩' + sfx, jp_side + '肩', 'Shoulder' + en_sfx, _mx((L['neck_half_w'] * 1.1, sj.y, L['shoulder_z']), s),
                 _mx(sj, s), '上半身2', r=0.045, r_end=0.03, group='Arms'))
        add(Bone('腕' + sfx, jp_side + '腕', 'Arm' + en_sfx, _mx(sj, s), _mx(el, s), '肩' + sfx, connect=True,
                 r=0.04, r_end=0.03, group='Arms'))
        # semi-standard twist bones: 腕 -> 腕捩 -> ひじ -> 手捩 -> 手首. They turn only about
        # their own axis and take a share of their limb segment's weight that grows from
        # 0 at its top to 1 at its bottom (_split_twist), so a twist spreads along the limb.
        add(Bone('腕捩' + sfx, jp_side + '腕捩', 'ArmTwist' + en_sfx, _mx(sj.lerp(el, TWIST_AT), s), _mx(el, s),
                 '腕' + sfx, group='Arms', meta={'twist_of': '腕' + sfx}))
        add(Bone('ひじ' + sfx, jp_side + 'ひじ', 'Elbow' + en_sfx, _mx(el, s), _mx(wr, s), '腕捩' + sfx, connect=True,
                 r=0.035, r_end=0.03, group='Arms'))
        _joint_aux(add, 'ひじ補助', 'ElbowAux', el, wr, '腕捩' + sfx, 'ひじ' + sfx, ('腕' + sfx, '腕捩' + sfx),
                   s, sfx, jp_side, en_sfx, 'Arms')
        add(Bone('手捩' + sfx, jp_side + '手捩', 'WristTwist' + en_sfx, _mx(el.lerp(wr, TWIST_AT), s), _mx(wr, s),
                 'ひじ' + sfx, group='Arms', meta={'twist_of': 'ひじ' + sfx}))
        add(Bone('手首' + sfx, jp_side + '手首', 'Wrist' + en_sfx, _mx(wr, s), _mx(palm_end, s), '手捩' + sfx,
                 connect=True, r=0.03, r_end=0.02, group='Arms'))
        # fingers: one chain per finger, fitted to the finger's own centreline when the
        # body mesh gives one (fit_fingers), each bone's Z rolled to the palm side so a
        # positive turn about its local X curls it toward the palm
        palm = d.cross(f).normalized()
        for jp, en, pts in finger_chains(F, wr, d, f, hand_len, palm_end, fingers):
            parent = '手首' + sfx
            thumb = jp == '親指'
            for i in range(3):
                nm = f'{jp}{("０１２" if thumb else "１２３")[i]}'
                add(Bone(nm + sfx, jp_side + nm, f'{en}{i if thumb else i + 1}' + en_sfx, _mx(pts[i], s),
                         _mx(pts[i + 1], s), parent, connect=i > 0, r=0.014 if thumb else 0.012,
                         r_end=0.01 if thumb else 0.008, group='Fingers',
                         meta={'align_z': tuple(_mx(palm, s)), 'finger': jp}))
                parent = nm + sfx

        hip, knee, ankle, toe = J['hip'], J['knee'], J['ankle'], J['toe']
        add(Bone('足' + sfx, jp_side + '足', 'Leg' + en_sfx, _mx(hip, s), _mx(knee, s), '下半身',
                 r=0.065, r_end=0.04, group='Legs'))
        add(Bone('ひざ' + sfx, jp_side + 'ひざ', 'Knee' + en_sfx, _mx(knee, s), _mx(ankle, s), '足' + sfx,
                 connect=True, r=0.05, r_end=0.035, group='Legs'))
        _joint_aux(add, 'ひざ補助', 'KneeAux', knee, ankle, '足' + sfx, 'ひざ' + sfx, ('足' + sfx,),
                   s, sfx, jp_side, en_sfx, 'Legs')
        add(Bone('足首' + sfx, jp_side + '足首', 'Ankle' + en_sfx, _mx(ankle, s), _mx(toe, s), 'ひざ' + sfx,
                 connect=True, r=0.04, r_end=0.03, group='Legs'))
        add(Bone('つま先' + sfx, jp_side + 'つま先', 'Toe' + en_sfx, _mx(toe, s),
                 _mx((toe[0], toe[1] - 0.025, toe[2]), s), '足首' + sfx, deform=False, group='Legs'))
        add(Bone('足ＩＫ' + sfx, jp_side + '足ＩＫ', 'LegIK' + en_sfx, _mx(ankle, s),
                 _mx((ankle[0], ankle[1] - 0.08, ankle[2]), s), '全ての親', deform=False, group='IK'))
        add(Bone('つま先ＩＫ' + sfx, jp_side + 'つま先ＩＫ', 'ToeIK' + en_sfx, _mx(toe, s),
                 _mx((toe[0], toe[1], toe[2] - 0.04), s), '足ＩＫ' + sfx, deform=False, group='IK'))
    return b


# IK: (constraint owner, IK control bone, chain length, iterations). The toe IK
# gets 40 iterations too: Blender's damped solver needs them for large rotations.
IK_SETUP = [(f'ひざ.{t}', f'足ＩＫ.{t}', 2, 40) for t in 'LR'] + \
           [(f'足首.{t}', f'つま先ＩＫ.{t}', 1, 40) for t in 'LR']


# ---------------------------------------------------------------- chains from geometry
def _world_verts(objs):
    out = []
    for o in objs:
        me = o.data
        if not len(me.vertices):
            continue
        co = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get('co', co)
        co = co.reshape(-1, 3)
        mw = np.array(o.matrix_world)
        out.append(co @ mw[:3, :3].T + mw[:3, 3])
    return np.concatenate(out) if out else np.zeros((0, 3))


def _band_chain(pts, z_top, z_bot, nseg):
    """Joint points of a chain through `pts` from z_top down to z_bot: per-band centroids."""
    band = (z_top - z_bot) / nseg
    joints = []
    for i in range(nseg + 1):
        z = z_top - i * band
        sel = pts[np.abs(pts[:, 2] - z) <= band * 0.5 + 1e-6]
        if len(sel) == 0:
            return None
        joints.append(Vector(sel.mean(0)))
    if any((a - b).length < 0.01 for a, b in zip(joints, joints[1:])):
        return None
    return joints


def _sector_chains(pts, center, root_z, n_sectors, nseg, min_len, min_pts=24):
    """Chains hanging from root_z, one per angular sector around a vertical axis
    through `center` (x, y). Angle 0 is +Y (behind), +90 deg is +X (character's left)."""
    if len(pts) == 0:
        return []
    ang = np.degrees(np.arctan2(pts[:, 0] - center[0], pts[:, 1] - center[1]))
    ang[ang >= 180.0] -= 360.0          # arctan2 can return +180 (x = +0.0); bins are [-180, 180)
    step = 360.0 / n_sectors
    out = []
    for k in range(n_sectors):
        a0 = -180.0 + k * step
        sel = pts[(ang >= a0) & (ang < a0 + step) & (pts[:, 2] <= root_z + 0.02)]
        if len(sel) < min_pts:
            continue
        z_bot = float(sel[:, 2].min())
        if root_z - z_bot < min_len:
            continue
        joints = _band_chain(sel, root_z, z_bot, nseg)
        if joints:
            out.append((a0 + step / 2, joints))
    return out


def _seg_dist(p, a, b):
    ab = b - a
    t = np.clip(((p - a) @ ab) / max(ab @ ab, 1e-12), 0.0, 1.0)
    return np.linalg.norm(p - (a + t[:, None] * ab), axis=1)


def _chain_bones(prefix, jp, en, joints, parent, r, group, sfx='', jp_side='', en_sfx='', meta=None):
    out = []
    for i, (a, bpt) in enumerate(zip(joints, joints[1:])):
        name = f'{prefix}_{i}{sfx}'
        out.append(Bone(name, f'{jp_side}{jp}_{i}', f'{en}_{i}{en_sfx}', a, bpt, parent, connect=i > 0,
                        r=r, r_end=max(0.02, (bpt - a).length * 0.5), group=group,
                        meta=dict(meta or {}, seg=i, nseg=len(joints) - 1)))
        parent = name
    return out


HAIR_ROOT = '髪追従'
HAIR_FOLLOW = 0.6     # share of the head's rotation the hair chains take (the scalp takes all of it)
FOLLOW_FRONT = 1.0    # total share of the thighs' rotation a skirt chain takes at centre front
FOLLOW_BACK = 0.5     # ... and at centre back (a leg swung back still pushes the back skirt)


def skirt_follow(angle, s):
    """Share of thigh `s` (+1 left, -1 right) a skirt chain at `angle` takes (0 = behind,
    +90 = character's left). Both thighs together give FOLLOW_FRONT in front and
    FOLLOW_BACK behind; each thigh's part fades smoothly to 0 on the far side."""
    a = math.radians(angle)
    total = FOLLOW_BACK + (FOLLOW_FRONT - FOLLOW_BACK) * 0.5 * (1.0 - math.cos(a))
    return total * 0.5 * (1.0 + s * math.sin(a))


def _secondary_bones(parts, core):
    """Hair / skirt / sleeve chains for the parts present. parts: {name: [mesh objs]}."""
    bones = []
    byname = {b.name: b for b in core}

    def verts(*names):
        objs = [o for n in names for o in parts.get(n, [])]
        return _world_verts(objs)

    def hair_parent():
        # long hair hangs from a bone on the neck that takes HAIR_FOLLOW of the head's
        # rotation, so a turned head doesn't swing the whole curtain through the body
        if not any(b.name == HAIR_ROOT for b in bones):
            h = byname['頭'].head
            bones.append(Bone(HAIR_ROOT, HAIR_ROOT, 'HairRoot', h, h + Vector((0, 0, 0.03)), '首',
                              deform=False, group='HairFollow', meta={'follow': ('頭', HAIR_FOLLOW)}))
        return HAIR_ROOT

    # back hair: sectors around the skull axis, hanging from eye level
    pts = verts('hair_back')
    if len(pts):
        chains = _sector_chains(pts, (0.0, L['head_center_y']), L['eye_z'], 10, 4, 0.10)
        for k, (_, joints) in enumerate(chains):
            bones += _chain_bones(f'後髪{k}', f'後髪{k}', f'HairBack{k}', joints, hair_parent(), 0.035, 'Hair')

    # side locks: hair_front strands hanging beside the face, below the eyes
    pts = verts('hair_front')
    if len(pts):
        top = L['eye_z'] - 0.02
        for tag, s, jp_side in SIDES:
            sel = pts[(pts[:, 0] * s > L['head_half_w'] * 0.6) & (pts[:, 2] < top)]
            if len(sel) < 12 or top - sel[:, 2].min() < 0.06:
                continue
            joints = _band_chain(sel, float(sel[:, 2].max()), float(sel[:, 2].min()), 3)
            if joints:
                bones += _chain_bones('横髪', '横髪', 'SideHair', joints, hair_parent(), 0.025, 'Hair',
                                      sfx='.' + tag, jp_side=jp_side, en_sfx='_' + tag)

    # skirt (+ petticoat): sectors around the body axis, hanging from the hip
    pts = verts('skirt', 'petticoat')
    if len(pts):
        cy = float(pts[:, 1].mean())
        chains = _sector_chains(pts, (0.0, cy), L['hip_z'], 12, 3, 0.08)
        for k, (ang, joints) in enumerate(chains):
            hem_r = max(0.03, math.hypot(joints[-1].x, joints[-1].y - cy) * math.pi / 12)
            # the chain hangs from two follow bones that add a share of each thigh's
            # rotation (PMX 回転付与), so the skirt moves with the legs as a whole
            # instead of being torn by per-vertex leg weights
            parent = '下半身'
            head = joints[0]
            for tag, s, jp_side in SIDES[::-1]:
                name = f'スカート{k}追従{jp_side}'
                bones.append(Bone(name, name, f'Skirt{k}Follow{tag}', head, head + Vector((0, 0, 0.03)), parent,
                                  deform=False, group='SkirtFollow',
                                  meta={'follow': (f'足.{tag}', skirt_follow(ang, s))}))
                parent = name
            bones += _chain_bones(f'スカート{k}', f'スカート{k}', f'Skirt{k}', joints, parent, hem_r, 'Skirt',
                                  meta={'chain': k, 'angle': ang, 'cy': cy})

    # sleeve drapes: sleeve vertices well away from the arm bones hang from the forearm
    pts = verts('sleeves')
    if len(pts):
        for tag, s, jp_side in SIDES:
            side = pts[pts[:, 0] * s > 0.05]
            if not len(side):
                continue
            arm = [byname[f'{n}.{tag}'] for n in ('腕', 'ひじ', '手首')]
            d = np.min([_seg_dist(side, np.array(b.head), np.array(b.tail)) for b in arm], axis=0)
            drape = side[d > 0.05]
            if len(drape) < 24:
                continue
            el = arm[1]
            a, bpt = np.array(el.head), np.array(el.tail)
            c = drape.mean(0)
            t = float(np.clip((c - a) @ (bpt - a) / ((bpt - a) @ (bpt - a)), 0.2, 0.9))
            root = Vector(a + t * (bpt - a))
            below = drape[drape[:, 2] < root.z]
            if len(below) < 24 or root.z - below[:, 2].min() < 0.05:
                continue
            joints = _band_chain(below, root.z, float(below[:, 2].min()), 2)
            if joints:
                joints[0] = root
                bones += _chain_bones('袖', '袖', 'Sleeve', joints, el.name, 0.04, 'Sleeve',
                                      sfx='.' + tag, jp_side=jp_side, en_sfx='_' + tag)
    return bones


# ---------------------------------------------------------------- skinning rules
def _names(bones, pred):
    return [b.name for b in bones if b.deform and pred(b)]


def _candidates(part, obj, bones):
    """Deform bones a mesh of `part` may be weighted to."""
    core = [b for b in bones if b.group in ('Body', 'Arms', 'Fingers', 'Legs')]
    core_names = _names(core, lambda b: not b.name.startswith('目'))
    grp = lambda *gs: _names(bones, lambda b: b.group in gs)  # noqa: E731
    base = lambda b: b.name.split('.')[0]  # noqa: E731
    if part in ('hair_front', 'hair_back'):
        # front hair (bangs, crown, side locks) follows the head and its side-lock chains;
        # only the long back hair uses the back-hair chains, which lag the head (髪追従)
        own = '後髪' if part == 'hair_back' else '横髪'
        return ['頭'] + _names(bones, lambda b: b.group == 'Hair' and b.name.startswith(own))
    if part == 'head':
        low = obj.name.lower()
        if 'eye' in low and not any(k in low for k in ('brow', 'lash', 'lid', 'white')):
            return ['目.L', '目.R']
        return ['頭', '首', '上半身2']
    if part in ('skirt', 'petticoat'):
        return ['上半身', '下半身'] + grp('Skirt')
    if part == 'sleeves':      # detached sleeves: arm only, never the torso
        return _names(bones, lambda b: base(b) in ('肩', '腕', '腕捩', 'ひじ補助', 'ひじ', '手捩', '手首')) + grp('Sleeve')
    if part == 'bodice':       # a strapless corset: torso only; anything hanging below the hip rides the skirt
        return ['上半身', '上半身2', '首', '下半身'] + grp('Skirt')
    if part == 'shoes':
        return _names(bones, lambda b: base(b) in ('ひざ', '足首'))
    if part == 'accessories':
        zc = sum((obj.matrix_world @ Vector(c)).z for c in obj.bound_box) / 8
        return ['頭'] if zc > L['chin_z'] else core_names
    return core_names   # body, proxy, anything unknown


def _smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _envelope(co, bones):
    """(V, B) bone weights for world positions `co`: softmax of the envelope log-weights.

    The log-weight is -SHARPNESS * d^2 inside the envelope (d = normalized distance) and
    continues linearly outside it, so far from every bone the weights still change
    slowly instead of snapping to whichever envelope is a hair closer."""
    A = np.array([b.head for b in bones])
    B = np.array([b.tail for b in bones])
    r = np.array([b.r for b in bones])
    re = np.array([b.r_end for b in bones])
    AB = B - A
    ln = np.linalg.norm(AB, axis=1)
    axis = AB / ln[:, None]
    rel = co[:, None, :] - A[None]                         # V,B,3
    t = np.einsum('vbk,bk->vb', rel, axis)                 # along-axis coordinate
    lat = np.linalg.norm(rel - t[..., None] * axis[None], axis=2)
    over = np.maximum(0.0, -t) + np.maximum(0.0, t - ln[None])
    d2 = (lat / r) ** 2 + (over / re) ** 2
    d = np.sqrt(d2)
    logw = np.where(d <= 1.0, -SHARPNESS * d2, -SHARPNESS * (2.0 * d - 1.0))
    w = np.exp(logw - logw.max(1, keepdims=True))
    return w / w.sum(1, keepdims=True)


# ---- skirt / petticoat: angle x height around the body axis
ROOT_BLEND = 0.5      # chain units (from the hip) over which 上半身/下半身 hand over to the chains


def _skirt_weights(co, bones):
    """(V, B) weights for skirt / petticoat vertices, at most 4 bones each by construction.

    Around the body axis a vertex blends linearly between the two nearest skirt chains
    by angle; down each chain it blends between consecutive bones by height (hat
    functions centred on the bones), and over the first half bone below the hip it
    hands over from 上半身/下半身 (the same envelopes as the bodice above it). The thighs
    are not weighted here at all: the chains follow them through their follow bones.
    """
    V = len(co)
    col = {b.name: i for i, b in enumerate(bones)}
    W = np.zeros((V, len(bones)))
    chains = {}
    for i, b in enumerate(bones):
        if b.group == 'Skirt' and 'chain' in b.meta:
            chains.setdefault(b.meta['chain'], []).append((b.meta['seg'], i, b))
    body = [n for n in ('上半身', '下半身') if n in col]
    if not chains or not body:
        return _envelope(co, bones)
    keys = sorted(chains, key=lambda k: chains[k][0][2].meta['angle'])
    A = np.array([chains[k][0][2].meta['angle'] for k in keys])
    cy = chains[keys[0]][0][2].meta['cy']
    theta = np.degrees(np.arctan2(co[:, 0], co[:, 1] - cy))
    rows = np.arange(V)
    d_fwd = (theta[:, None] - A[None]) % 360.0         # how far past chain c (increasing angle)
    d_bwd = (A[None] - theta[:, None]) % 360.0
    prv, nxt = d_fwd.argmin(1), d_bwd.argmin(1)
    dp, dn = d_fwd[rows, prv], d_bwd[rows, nxt]
    gap = dp + dn
    w_prv = np.where(gap > 1e-9, dn / np.maximum(gap, 1e-9), 1.0)
    rest = np.zeros(V)                                  # share left to the body bones
    for c, k in enumerate(keys):
        ac = w_prv * (prv == c) + (1.0 - w_prv) * (nxt == c)
        segs = sorted(chains[k], key=lambda s: s[0])
        n = len(segs)
        zj = np.array([s[2].head.z for s in segs] + [segs[-1][2].tail.z])
        u = np.interp(-co[:, 2], np.maximum.accumulate(-zj), np.arange(n + 1.0))
        share = _smoothstep(0.0, ROOT_BLEND, u)
        uc = np.clip(u, 0.5, n - 0.5)
        for i, j, _ in segs:
            W[:, j] += ac * share * np.maximum(0.0, 1.0 - np.abs(uc - (i + 0.5)))
        rest += ac * (1.0 - share)
    bi = [col[n] for n in body]
    W[:, bi] += _envelope(co, [bones[i] for i in bi]) * rest[:, None]
    return W


# ---- per-object helpers: topology, sides, smoothing, pruning
SMOOTH_RADIUS = {     # metres of weight smoothing along the surface, per part
    'body': 0.008, 'head': 0.01, 'shoes': 0.012, 'accessories': 0.012, 'bodice': 0.02,
    'hair_front': 0.025, 'hair_back': 0.03, 'sleeves': 0.065, 'skirt': 0.02, 'petticoat': 0.02,
}
DEFAULT_SMOOTH = 0.012
MAX_SMOOTH_ITERS = 300
SIDE_BAND = 0.02      # a .L/.R bone fades out over this far past the midline
ISLAND_SIDE_X = 0.03  # a loose piece whose centre is this far off the midline belongs to one side
SIDED_PARTS_EXEMPT = ('skirt', 'petticoat')   # angular leg weights there are already symmetric


def _topology(obj, co):
    """Edges (E, 2) of the mesh plus links between coincident vertices (split seams)."""
    me = obj.data
    ed = np.empty(len(me.edges) * 2, dtype=np.int64)
    me.edges.foreach_get('vertices', ed)
    ed = ed.reshape(-1, 2)
    _, first, inv = np.unique(np.round(co, 5), axis=0, return_index=True, return_inverse=True)
    rep = first[inv.reshape(-1)]
    dup = np.nonzero(rep != np.arange(len(co)))[0]
    if len(dup):
        ed = np.concatenate([ed, np.stack([dup, rep[dup]], 1)])
    return ed


def _islands(n, edges):
    parent = np.arange(n)

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    for a, b in edges.tolist():
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)
    return np.array([find(i) for i in range(n)])


def _side_mask(co, labels, bones, per_vertex):
    """(V, B) factors that keep .L bones off the right side and .R bones off the left."""
    m = np.ones((len(co), len(bones)))
    sums = np.bincount(labels, weights=co[:, 0], minlength=labels.max() + 1)
    cnt = np.bincount(labels, minlength=labels.max() + 1)
    cx = (sums / np.maximum(cnt, 1))[labels]
    isl_side = np.where(np.abs(cx) > ISLAND_SIDE_X, np.sign(cx), 0.0)
    for j, b in enumerate(bones):
        s = {'L': 1.0, 'R': -1.0}.get(b.name.rsplit('.', 1)[-1]) if '.' in b.name else None
        if s is None:
            continue
        if per_vertex:
            m[:, j] = _smoothstep(-SIDE_BAND, 0.0, co[:, 0] * s)
        m[isl_side == -s, j] = 0.0
    return m


def _smooth(w, co, edges, radius):
    """Laplacian smoothing of the weight rows along the mesh edges, about `radius` metres.

    Each edge pulls with (median edge / its length)^2 (at most 1), so every iteration
    spreads about one median edge length in metres whatever the edge: long edges down
    a thin ribbon don't carry weights much farther than `radius`."""
    if radius <= 0 or not len(edges):
        return w
    ln = np.linalg.norm(co[edges[:, 0]] - co[edges[:, 1]], axis=1)
    pos = ln[ln > 1e-6]
    if not len(pos):
        return w
    ref = float(np.median(pos))
    iters = int(min(MAX_SMOOTH_ITERS, round(2.0 * (radius / ref) ** 2)))
    if iters <= 0:
        return w
    c = np.minimum(1.0, (ref / np.maximum(ln, 1e-9)) ** 2)
    src = np.concatenate([edges[:, 0], edges[:, 1]])
    dst = np.concatenate([edges[:, 1], edges[:, 0]])
    cc = np.concatenate([c, c])
    order = np.argsort(src, kind='stable')
    src, dst, cc = src[order], dst[order], cc[order][:, None]
    verts, starts = np.unique(src, return_index=True)
    deg = np.diff(np.append(starts, len(src)))[:, None]
    w = w.copy()
    for _ in range(iters):
        pull = np.add.reduceat(cc * (w[dst] - w[src]), starts, axis=0) / deg
        w[verts] += 0.5 * pull
    return w


def _prune(w):
    """Keep the MAX_INFLUENCE strongest bones per vertex, continuously: the next-strongest
    weight (at least MIN_WEIGHT) is subtracted from every bone before renormalizing, so a
    bone entering or leaving the top four does so at zero weight instead of jumping."""
    k = min(MAX_INFLUENCE, w.shape[1])
    w = w / np.maximum(w.sum(1, keepdims=True), 1e-12)
    thr = -np.sort(-w, axis=1)[:, k] if w.shape[1] > k else np.zeros(len(w))
    top = np.argmax(w, axis=1)
    w = np.maximum(w - np.maximum(thr, MIN_WEIGHT)[:, None], 0.0)
    empty = np.nonzero(w.sum(1) <= 0)[0]      # only with 5+ exactly tied bones
    w[empty, top[empty]] = 1.0
    idx = np.argsort(-w, axis=1, kind='stable')[:, :k]
    ww = np.take_along_axis(w, idx, axis=1)
    return idx, ww / np.maximum(ww.sum(1, keepdims=True), 1e-12)


SKIRT_BAND = 0.03     # bodice pieces hand over to the skirt weights within this of hip_z
ANKLE_BLEND = 0.03    # foot / shin blend half-width around the ankle joint height
DRAPE_NEAR, DRAPE_FAR = 0.04, 0.13   # sleeve drape weight fades in between these from the arm axis


def _split_joint_aux(w, co, bones, band):
    """Spread each elbow / knee bend over three rotations: the upper limb (0), its helper
    bone (half the bend) and the lower limb with everything hanging from it (full bend).
    Along the lower bone, within `width` of the joint, the limb's total weight is
    re-split by a smooth partition of unity (upper -> helper -> lower); inside each group
    the bones keep their envelope proportions."""
    before, after, helper = band
    col = {b.name: i for i, b in enumerate(bones)}
    kids = {}
    for b in bones:
        kids.setdefault(b.parent, []).append(b.name)

    def below(name):
        out, todo = [], [name]
        while todo:
            n = todo.pop()
            out.append(n)
            todo += kids.get(n, [])
        return out
    for j, b in enumerate(bones):
        if 'joint_aux' not in b.meta:
            continue
        upper, lower = b.meta['joint_aux']
        if lower not in col:
            continue
        up = [col[n] for n in upper if n in col]
        # the limb and what it carries rigidly; secondary chains (sleeve drapes) keep their own weights
        lo = [col[n] for n in below(lower) if n in col and bones[col[n]].group not in ('Sleeve', 'Hair', 'Skirt')]
        if not up:
            continue
        L = bones[col[lower]]
        d = np.array((L.tail - L.head).normalized())
        t = (co - np.array(b.head)) @ d
        if helper:
            f_lo = _smoothstep(0.0, after, t)
            f_up = 1.0 - _smoothstep(-before, 0.0, t)
        else:
            f_lo = _smoothstep(-before, after, t)
            f_up = 1.0 - f_lo
        f_aux = 1.0 - f_lo - f_up
        su, sl = w[:, up].sum(1), w[:, lo].sum(1)
        tot = su + sl
        live = tot > 1e-9
        pu = np.where(live[:, None], w[:, up] / np.maximum(su, 1e-12)[:, None], 0.0)
        pu[su <= 1e-12] = np.eye(len(up))[-1]          # empty group: its main bone
        pl = np.where(live[:, None], w[:, lo] / np.maximum(sl, 1e-12)[:, None], 0.0)
        pl[sl <= 1e-12] = np.eye(len(lo))[0]
        w[:, up] = pu * (tot * f_up)[:, None]
        w[:, lo] = pl * (tot * f_lo)[:, None]
        w[:, j] += tot * f_aux


def _split_twist(w, co, bones):
    """Give each twist bone (meta 'twist_of') the share of its limb segment's weight that
    grows smoothly from 0 at the segment's top to 1 at its bottom (TWIST_RAMP)."""
    col = {b.name: i for i, b in enumerate(bones)}
    for j, b in enumerate(bones):
        p = col.get(b.meta.get('twist_of'))
        if p is None:
            continue
        a, c = np.array(bones[p].head), np.array(bones[p].tail)
        t = ((co - a) @ (c - a)) / max(float((c - a) @ (c - a)), 1e-12)
        f = _smoothstep(TWIST_RAMP[0], TWIST_RAMP[1], t)
        w[:, j] += w[:, p] * f
        w[:, p] *= 1.0 - f


def _split_ankle(w, co, bones):
    """Below the ankle everything is foot (足首), above it shin (ひざ), with a short blend
    around the joint: the shoe is rigid and the skin inside it moves the same way."""
    col = {b.name: i for i, b in enumerate(bones)}
    for tag in 'LR':
        a, k = col.get(f'足首.{tag}'), col.get(f'ひざ.{tag}')
        if a is None or k is None:
            continue
        s = w[:, a] + w[:, k]
        f = _smoothstep(bones[a].head.z - ANKLE_BLEND, bones[a].head.z + ANKLE_BLEND, co[:, 2])
        w[:, a], w[:, k] = s * (1.0 - f), s * f


def _drape_only_away_from_arm(w, co, bones):
    """Sleeve drape chains (袖) only move cloth hanging away from the arm: their weight
    fades in between DRAPE_NEAR and DRAPE_FAR from the arm bones, so the cuff and the
    band around the arm follow the arm and a swinging drape doesn't tear them."""
    for tag in 'LR':
        arm = [b for b in bones if b.name in (f'腕.{tag}', f'ひじ.{tag}')]
        drape = [j for j, b in enumerate(bones) if b.group == 'Sleeve' and b.name.endswith('.' + tag)]
        if not arm or not drape:
            continue
        d = np.min([_seg_dist(co, np.array(b.head), np.array(b.tail)) for b in arm], axis=0)
        g = _smoothstep(DRAPE_NEAR, DRAPE_FAR, d)
        moved = w[:, drape].sum(1) * (1.0 - g)
        w[:, drape] *= g[:, None]
        others = [j for j, b in enumerate(bones) if j not in drape and b.name in
                  {f'{n}.{tag}' for n in ('腕', '腕捩', 'ひじ', '手捩', '手首')}]
        tot = w[:, others].sum(1)
        if others:
            env = _envelope(co, [bones[j] for j in others])
            w[:, others] += np.where(tot[:, None] > 1e-9, w[:, others] / np.maximum(tot, 1e-9)[:, None],
                                     env) * moved[:, None]


def _base_weights(part, co, bones):
    """(V, B) weights before side masking / smoothing / pruning."""
    plain = [j for j, b in enumerate(bones) if 'twist_of' not in b.meta and 'joint_aux' not in b.meta]
    sub = [bones[j] for j in plain]
    if part in ('skirt', 'petticoat'):
        w0 = _skirt_weights(co, sub)
    else:
        main = [i for i, b in enumerate(sub) if b.group != 'Skirt']
        w0 = np.zeros((len(co), len(sub)))
        w0[:, main] = _envelope(co, [sub[i] for i in main])
        if len(main) < len(sub):        # bodice ribbons hanging over the skirt ride the skirt
            t = _smoothstep(L['hip_z'] + SKIRT_BAND, L['hip_z'] - SKIRT_BAND, co[:, 2])[:, None]
            w0 = (1.0 - t) * w0 + t * _skirt_weights(co, sub)
    w = np.zeros((len(co), len(bones)))
    w[:, plain] = w0
    if part == 'sleeves':
        _drape_only_away_from_arm(w, co, bones)
    _split_ankle(w, co, bones)
    _split_twist(w, co, bones)
    _split_joint_aux(w, co, bones, JOINT_BAND.get(part, (JOINT_AUX_BLEND, JOINT_AUX_BLEND, True)))
    return w


RIGID_ISLAND = 0.05   # loose pieces (not skin) within this radius move rigidly: island-average weights


def _island_rules(w, co, labels, bones, part):
    """Per loose part: a finger part belongs to its own finger chain only (neighbouring
    finger envelopes overlap at ~1 cm), and small ornaments (bows, leaves, beads) take
    their island's average weights so they move as one piece."""
    chains = {}
    for j, b in enumerate(bones):
        if 'finger' in b.meta:
            chains.setdefault(b.meta['finger'], []).append(j)
    for k in np.unique(labels):
        m = labels == k
        if chains:
            sums = {jp: w[np.ix_(m, cols)].sum() for jp, cols in chains.items()}
            tot = sum(sums.values())
            best = max(sums, key=sums.get)
            if tot > 0.3 * m.sum() and sums[best] > 0.6 * tot:
                for jp, cols in chains.items():
                    if jp != best:
                        w[np.ix_(m, cols)] = 0.0
        if part != 'body':
            p = co[m]
            if np.linalg.norm(p - p.mean(0), axis=1).max() < RIGID_ISLAND:
                w[m] = w[m].mean(0)
    s = w.sum(1, keepdims=True)
    return np.where(s > 1e-12, w / np.maximum(s, 1e-12), w)


def _weights(obj, part, co, bones):
    """(V, k) bone indices and weights for the vertices of `obj` (world positions `co`)."""
    w = _base_weights(part, co, bones)
    edges = _topology(obj, co)
    labels = _islands(len(co), edges)
    masked = w * _side_mask(co, labels, bones, part not in SIDED_PARTS_EXEMPT)
    ok = masked.sum(1) > 1e-9
    w = np.where(ok[:, None], masked, w)
    w = w / w.sum(1, keepdims=True)
    w = _smooth(w, co, edges, SMOOTH_RADIUS.get(part, DEFAULT_SMOOTH))
    w = _island_rules(w, co, labels, bones, part)
    return _prune(w)


def _skin(obj, part, bones, arm):
    names = _candidates(part, obj, bones)
    byname = {b.name: b for b in bones}
    cand = [byname[n] for n in names if n in byname]
    me = obj.data
    stale = set(obj.get('levi_rig_groups', [])) | set(byname)
    for vg in list(obj.vertex_groups):
        if vg.name in stale:
            obj.vertex_groups.remove(vg)
    obj['levi_rig_groups'] = []
    if len(me.vertices):
        co = _world_verts([obj])
        idx, w = _weights(obj, part, co, cand)
        groups = {}
        for j in np.unique(idx[w > 0]):
            groups[j] = obj.vertex_groups.new(name=cand[j].name)
        for j, vg in groups.items():
            rows, cols = np.nonzero((idx == j) & (w > 0))
            for v, c in zip(rows.tolist(), cols.tolist()):
                vg.add([v], float(w[v, c]), 'REPLACE')
        obj['levi_rig_groups'] = [vg.name for vg in groups.values()]
    for m in list(obj.modifiers):     # armature modifiers left over from a previous rig
        if m.type == 'ARMATURE' and m.name != 'Armature' and m.object in (None, arm):
            obj.modifiers.remove(m)
    mod = obj.modifiers.get('Armature')
    if mod is not None and mod.type != 'ARMATURE':
        mod.name = 'Armature_prev'
        mod = None
    mod = mod or obj.modifiers.new('Armature', 'ARMATURE')
    mod.object = arm
    mod.use_vertex_groups = True
    mod.use_bone_envelopes = False
    _move_before_outline(obj, mod)


def _move_before_outline(obj, mod):
    names = [m.name for m in obj.modifiers]
    if 'Outline' not in names:
        return
    i, target = names.index(mod.name), names.index('Outline')
    if i > target:
        obj.modifiers.move(i, target)


# ---------------------------------------------------------------- armature
def _clear_previous():
    old = bpy.data.objects.get(ARM_NAME)
    if old:
        data = old.data
        bpy.data.objects.remove(old, do_unlink=True)
        if data.users == 0:
            bpy.data.armatures.remove(data)
    col = bpy.data.collections.get(RIG_COLLECTION)
    if col:
        bpy.data.collections.remove(col)


def _part_meshes():
    parts = {}
    for col in bpy.context.scene.collection.children:
        if col.name == RIG_COLLECTION:
            continue
        objs = [o for o in col.all_objects if o.type == 'MESH']
        for o in col.all_objects:
            if o.type in ('CURVE', 'SURFACE', 'FONT', 'META'):
                print(f'rig: {o.name} is a {o.type}, not a mesh; it will not deform')
        if objs:
            parts[col.name] = sorted(objs, key=lambda o: o.name)
    return parts


def _bake_modifiers(obj):
    """Apply generators (mirror, subsurf...) so weights cover the real vertices.
    The Outline hull and any armature stay live."""
    keep = ('Outline',) + tuple(m.name for m in obj.modifiers if m.type == 'ARMATURE')
    if obj.data.shape_keys:
        print(f'rig: {obj.name} has shape keys; skinning its base mesh without applying modifiers')
        return
    if any(m.name not in keep for m in obj.modifiers):
        common.apply_modifiers(obj, keep=keep)


def _create_armature(bones):
    col = bpy.data.collections.new(RIG_COLLECTION)
    bpy.context.scene.collection.children.link(col)
    data = bpy.data.armatures.new('Levi')
    arm = bpy.data.objects.new(ARM_NAME, data)
    col.objects.link(arm)
    data.display_type = 'STICK'
    arm.show_in_front = True
    vl = bpy.context.view_layer
    vl.objects.active = arm
    arm.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    eb = {}
    for b in bones:
        e = data.edit_bones.new(b.name)
        e.head, e.tail = b.head, b.tail
        e.roll = 0.0
        if 'align_z' in b.meta:
            e.align_roll(Vector(b.meta['align_z']))
        e.use_deform = b.deform
        eb[b.name] = e
    for b in bones:
        if b.parent:
            eb[b.name].parent = eb[b.parent]
            eb[b.name].use_connect = b.connect and (eb[b.parent].tail - b.head).length < 1e-5
    bpy.ops.object.mode_set(mode='OBJECT')
    colls = {}
    for b in bones:
        bc = colls.get(b.group) or data.collections.new(b.group)
        colls[b.group] = bc
        bc.assign(data.bones[b.name])
        arm.pose.bones[b.name]['mmd_name_j'] = b.jp
        arm.pose.bones[b.name]['mmd_name_e'] = b.en
    for owner, target, chain, iters in IK_SETUP:
        pb = arm.pose.bones[owner]
        c = pb.constraints.new('IK')
        c.name = 'IK'
        c.target = arm
        c.subtarget = target
        c.chain_count = chain
        c.iterations = iters
        c.use_tail = True
        c.use_stretch = False
    for b in bones:
        pb = arm.pose.bones[b.name]
        if 'follow' in b.meta:
            # PMX 回転付与: add `influence` of the source bone's rotation (relative to its
            # rest, expressed in this bone's rest orientation) to this bone
            src, infl = b.meta['follow']
            pb['mmd_append'] = src
            pb['mmd_append_influence'] = float(infl)
            if src in data.bones and infl > 1e-4:
                c = pb.constraints.new('COPY_ROTATION')
                c.name = 'Follow'
                c.target, c.subtarget = arm, src
                c.target_space, c.owner_space = 'LOCAL_OWNER_ORIENT', 'LOCAL'
                c.mix_mode = 'BEFORE'
                c.influence = infl
        if 'twist_of' in b.meta:
            # PMX fixed axis: a twist bone turns only about its own length
            pb.rotation_mode = 'QUATERNION'
            pb.lock_rotation = (True, False, True)
            pb.lock_rotation_w = False
            pb['mmd_fixed_axis'] = 1
    for t in 'LR':
        knee = arm.pose.bones[f'ひざ.{t}']
        knee.lock_ik_y = knee.lock_ik_z = True      # hinge about its local X
        knee.ik_stretch = 0.0
        arm.pose.bones[f'足.{t}'].ik_stretch = 0.0
    return arm


def bone_table(arm=None):
    """[(blender_name, jp, en)] for the rig in the scene (for export)."""
    arm = arm or bpy.data.objects[ARM_NAME]
    return [(pb.name, pb.get('mmd_name_j', pb.name), pb.get('mmd_name_e', pb.name)) for pb in arm.pose.bones]


def build_rig():
    """Build the armature for the parts in the scene and skin them. Returns the armature object."""
    if bpy.context.object and bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    _clear_previous()
    parts = _part_meshes()
    for objs in parts.values():
        for o in objs:
            if o.data.users > 1:      # weights live in the mesh: linked duplicates need their own
                o.data = o.data.copy()
            _bake_modifiers(o)
    bpy.context.view_layer.update()
    J, fitted = fit_joints(parts.get('body', []))
    for k in JOINT_KEYS:
        src = 'mesh' if k in fitted else 'spec'
        print(f'rig joint {k:14s} {src}  ({J[k].x:+.3f}, {J[k].y:+.3f}, {J[k].z:+.3f})')
    H = fit_head(parts.get('head', []))
    F = fit_fingers(parts.get('body', []), J)
    print(f"rig fingers    {'mesh' if F else 'spec'}  ({len(F)} chains fitted to the body's fingers)")
    core = _core_bones(J, H, F)
    by = {b.name: b for b in core}
    hd, ey = by['頭'].head, by['目.L'].head
    print(f"rig head  頭             {'mesh' if 'head_y' in H else 'spec'}  ({hd.x:+.3f}, {hd.y:+.3f}, {hd.z:+.3f})")
    print(f"rig head  目.L           {'mesh' if 'eye' in H else 'spec'}  ({ey.x:+.3f}, {ey.y:+.3f}, {ey.z:+.3f})")
    bones = core + _secondary_bones(parts, core)
    arm = _create_armature(bones)
    for part, objs in parts.items():
        for o in objs:
            if o.parent is None:
                o.parent = arm
                o.matrix_parent_inverse = arm.matrix_world.inverted()
            _skin(o, part, bones, arm)
    bpy.context.view_layer.update()
    return arm
