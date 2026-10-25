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
                 'r', 'r_end', 'group')

    def __init__(self, name, jp, en, head, tail, parent=None, connect=False,
                 deform=True, r=0.05, r_end=None, group='Body'):
        self.name, self.jp, self.en = name, jp, en
        self.head, self.tail = Vector(head), Vector(tail)
        self.parent, self.connect, self.deform = parent, connect, deform
        self.r = r
        self.r_end = r * 0.6 if r_end is None else r_end
        self.group = group


def _mx(p, s):
    return Vector((p[0] * s, p[1], p[2]))


JOINT_KEYS = ('shoulder_joint', 'elbow', 'wrist', 'fingertip', 'hip', 'knee', 'ankle', 'toe')


def landmark_joints():
    """Limb joints (character's left side, +X) from spec.L only."""
    return {
        'shoulder_joint': Vector(L['shoulder_joint']), 'elbow': Vector(L['elbow']),
        'wrist': Vector(L['wrist']), 'fingertip': Vector(L['fingertip']),
        'hip': Vector((L['leg_center_x'], 0.0, L['crotch_z'] + 0.065)),
        # the knee sits slightly forward so IK bends it the right way
        'knee': Vector((L['leg_center_x'], -0.012, L['knee_z'])),
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


def _core_bones(J=None):
    """Core MMD skeleton. Spine/head from landmarks, limbs from joints J (left side,
    built at +X and mirrored)."""
    J = J or landmark_joints()
    b = []
    add = b.append
    hc_y = L['head_center_y']
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
    eye_y = L['nose_tip_y'] + 0.035
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
        add(Bone('目' + sfx, jp_side + '目', 'Eye' + en_sfx, _mx((L['eye_x'], eye_y, L['eye_z']), s),
                 _mx((L['eye_x'], eye_y - 0.03, L['eye_z']), s), '頭', r=0.02, r_end=0.015, group='Body'))
        add(Bone('肩' + sfx, jp_side + '肩', 'Shoulder' + en_sfx, _mx((L['neck_half_w'] * 1.1, sj.y, L['shoulder_z']), s),
                 _mx(sj, s), '上半身2', r=0.045, r_end=0.03, group='Arms'))
        add(Bone('腕' + sfx, jp_side + '腕', 'Arm' + en_sfx, _mx(sj, s), _mx(el, s), '肩' + sfx, connect=True,
                 r=0.04, r_end=0.03, group='Arms'))
        add(Bone('ひじ' + sfx, jp_side + 'ひじ', 'Elbow' + en_sfx, _mx(el, s), _mx(wr, s), '腕' + sfx, connect=True,
                 r=0.035, r_end=0.03, group='Arms'))
        add(Bone('手首' + sfx, jp_side + '手首', 'Wrist' + en_sfx, _mx(wr, s), _mx(palm_end, s), 'ひじ' + sfx,
                 connect=True, r=0.03, r_end=0.02, group='Arms'))
        # thumb: 親指０ (metacarpal) + 親指１, 親指２
        t_pts = [wr + d * 0.08 * hand_len + f * 0.012, wr + d * 0.25 * hand_len + f * 0.028,
                 wr + d * 0.42 * hand_len + f * 0.038, wr + d * 0.58 * hand_len + f * 0.045]
        parent = '手首' + sfx
        for i in range(3):
            nm = f'親指{"０１２"[i]}'
            add(Bone(nm + sfx, jp_side + nm, f'Thumb{i}' + en_sfx, _mx(t_pts[i], s), _mx(t_pts[i + 1], s),
                     parent, connect=i > 0, r=0.014, r_end=0.01, group='Fingers'))
            parent = nm + sfx
        for jp, en, off, ln in fingers:
            base = palm_end + f * off
            seg = [0.0, 0.4, 0.73, 1.0]
            pts = [base + d * (t * ln * hand_len) for t in seg]
            parent = '手首' + sfx
            for i in range(3):
                nm = f'{jp}{"１２３"[i]}'
                add(Bone(nm + sfx, jp_side + nm, f'{en}{i + 1}' + en_sfx, _mx(pts[i], s), _mx(pts[i + 1], s),
                         parent, connect=i > 0, r=0.012, r_end=0.008, group='Fingers'))
                parent = nm + sfx

        hip, knee, ankle, toe = J['hip'], J['knee'], J['ankle'], J['toe']
        add(Bone('足' + sfx, jp_side + '足', 'Leg' + en_sfx, _mx(hip, s), _mx(knee, s), '下半身',
                 r=0.065, r_end=0.04, group='Legs'))
        add(Bone('ひざ' + sfx, jp_side + 'ひざ', 'Knee' + en_sfx, _mx(knee, s), _mx(ankle, s), '足' + sfx,
                 connect=True, r=0.05, r_end=0.035, group='Legs'))
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


def _chain_bones(prefix, jp, en, joints, parent, r, group, sfx='', jp_side='', en_sfx=''):
    out = []
    for i, (a, bpt) in enumerate(zip(joints, joints[1:])):
        name = f'{prefix}_{i}{sfx}'
        out.append(Bone(name, f'{jp_side}{jp}_{i}', f'{en}_{i}{en_sfx}', a, bpt, parent, connect=i > 0,
                        r=r, r_end=max(0.02, (bpt - a).length * 0.5), group=group))
        parent = name
    return out


def _secondary_bones(parts, core):
    """Hair / skirt / sleeve chains for the parts present. parts: {name: [mesh objs]}."""
    bones = []
    byname = {b.name: b for b in core}

    def verts(*names):
        objs = [o for n in names for o in parts.get(n, [])]
        return _world_verts(objs)

    # back hair: sectors around the skull axis, hanging from eye level
    pts = verts('hair_back')
    if len(pts):
        chains = _sector_chains(pts, (0.0, L['head_center_y']), L['eye_z'], 10, 4, 0.10)
        for k, (_, joints) in enumerate(chains):
            bones += _chain_bones(f'後髪{k}', f'後髪{k}', f'HairBack{k}', joints, '頭', 0.035, 'Hair')

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
                bones += _chain_bones('横髪', '横髪', 'SideHair', joints, '頭', 0.025, 'Hair',
                                      sfx='.' + tag, jp_side=jp_side, en_sfx='_' + tag)

    # skirt (+ petticoat): sectors around the body axis, hanging from the hip
    pts = verts('skirt', 'petticoat')
    if len(pts):
        cy = float(pts[:, 1].mean())
        chains = _sector_chains(pts, (0.0, cy), L['hip_z'], 12, 3, 0.08)
        for k, (_, joints) in enumerate(chains):
            hem_r = max(0.03, math.hypot(joints[-1].x, joints[-1].y - cy) * math.pi / 12)
            bones += _chain_bones(f'スカート{k}', f'スカート{k}', f'Skirt{k}', joints, '下半身', hem_r, 'Skirt')

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
        return ['頭'] + grp('Hair')
    if part == 'head':
        low = obj.name.lower()
        if 'eye' in low and not any(k in low for k in ('brow', 'lash', 'lid', 'white')):
            return ['目.L', '目.R']
        return ['頭', '首', '上半身2']
    if part in ('skirt', 'petticoat'):
        return ['上半身', '下半身'] + _names(bones, lambda b: base(b) == '足') + grp('Skirt')
    if part == 'sleeves':
        return ['上半身2'] + _names(bones, lambda b: base(b) in ('肩', '腕', 'ひじ', '手首')) + grp('Sleeve')
    if part == 'bodice':
        return ['上半身', '上半身2', '首', '下半身'] + _names(bones, lambda b: base(b) in ('肩', '腕'))
    if part == 'shoes':
        return _names(bones, lambda b: base(b) in ('ひざ', '足首'))
    if part == 'accessories':
        zc = sum((obj.matrix_world @ Vector(c)).z for c in obj.bound_box) / 8
        return ['頭'] if zc > L['chin_z'] else core_names
    return core_names   # body, proxy, anything unknown


def _weights(co, bones):
    """(V, k) bone indices and weights for world positions `co` against `bones`."""
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
    logw = -SHARPNESS * d2
    k = min(MAX_INFLUENCE, len(bones))
    idx = np.argsort(-logw, axis=1, kind='stable')[:, :k]
    lw = np.take_along_axis(logw, idx, axis=1)
    w = np.exp(lw - lw[:, :1])
    w /= w.sum(1, keepdims=True)
    w[w < MIN_WEIGHT] = 0.0
    w /= w.sum(1, keepdims=True)
    return idx, w


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
        idx, w = _weights(co, cand)
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
    core = _core_bones(J)
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
