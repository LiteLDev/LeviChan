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
# PMX names of the standard bones MMD motions bind to (VMD keys match by name)
STANDARD_PMX_BONES = ('全ての親', 'センター', 'グルーブ', '腰', '上半身', '上半身2', '首', '頭', '両目', '下半身') + tuple(
    side + n for side in '左右' for n in
    ('目', '肩', '腕', '腕捩', 'ひじ', '手捩', '手首', '親指０', '親指１', '親指２') +
    tuple(f + i for f in ('人指', '中指', '薬指', '小指') for i in '１２３') +
    ('足', 'ひざ', '足首', 'つま先', '足ＩＫ', 'つま先ＩＫ'))


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


JOINT_KEYS = ('shoulder_joint', 'elbow', 'wrist', 'fingertip', 'hip', 'knee', 'ankle', 'toe')


def deform_arm(names, tag):
    """Name of the bone the arm's skin follows on side `tag`: 腕D under the shoulder
    shrug (腕 is then only the keyed input), else 腕. `names`: the bone names present."""
    return f'腕D.{tag}' if f'腕D.{tag}' in names else f'腕.{tag}'


def landmark_joints():
    """Limb joints (character's left side, +X) from spec.L only."""
    return {
        'shoulder_joint': Vector(L['shoulder_joint']), 'elbow': Vector(L['elbow']),
        'wrist': Vector(L['wrist']), 'fingertip': Vector(L['fingertip']),
        'hip': Vector((L['leg_center_x'], 0.0, L['crotch_z'] + 0.065)),
        # the knee sits slightly forward so IK bends it the right way (sheet row 700,
        # where the leg kinks and the body's leg loops are widest)
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


EYE_DEPTH = 0.02
TWIST_AT = 0.6        # twist bones start this far down their limb segment (semi-standard)
TWIST_RAMP = (0.1, 0.95)   # ... and take over that segment's weight between these fractions


EYE_PIVOT_PROP = 'levi_eye_pivot'   # head objects that are eyes carry their eyeball centre (world, m)
EYE_LIMIT = (10.0, 8.0)   # deg: most the eyes turn (yaw, pitch) in Blender; the head's clean gaze range


def eye_objects(head_objs):
    """Head objects that are the eyes themselves (rotate with 目.L / 目.R): those carrying
    obj['levi_eye_pivot'], else ones named *eye* that are not brows, lashes, lids or whites."""
    out = [o for o in head_objs if o.get(EYE_PIVOT_PROP) is not None]
    if out:
        return out
    return [o for o in head_objs if 'eye' in o.name.lower()
            and not any(k in o.name.lower() for k in ('brow', 'lash', 'lid', 'white'))]


def eye_pivots(head_objs):
    """{'L': Vector, 'R': Vector} eyeball centres: obj['levi_eye_pivot'] (world; one per
    object, its side by x), else the least-squares sphere centre of each side's eye
    vertices. A side with nothing mirrors the other."""
    piv = {}
    for o in eye_objects(head_objs):
        p = o.get(EYE_PIVOT_PROP)
        if p is not None and len(p) == 3:
            v = Vector(tuple(p))
            piv.setdefault('L' if v.x >= 0 else 'R', v)
    if len(piv) < 2:
        pts = _world_verts(eye_objects(head_objs))
        for t, s in (('L', 1.0), ('R', -1.0)):
            side = pts[pts[:, 0] * s > 0.005] if len(pts) else pts
            if t in piv or len(side) < 12:
                continue
            A = np.c_[2 * side, np.ones(len(side))]
            c = np.linalg.lstsq(A, (side ** 2).sum(1), rcond=None)[0][:3]
            if np.linalg.norm(c - side.mean(0)) < 0.03:   # a real sphere-ish cap, not a flat decal
                piv[t] = Vector(c)
    for a, b in (('L', 'R'), ('R', 'L')):
        if a not in piv and b in piv:
            piv[a] = Vector((-piv[b].x, piv[b].y, piv[b].z))
    return piv


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
    piv = eye_pivots(head_objs)
    if piv:
        out['eye'] = piv['L']
        out['eye_R'] = piv['R']
        out['eye_src'] = 'pivot'
        return out
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
JOINT_AUX_BLEND = 0.06  # half-width (m) along the limb of the band the helpers carry
# per part: (blend start before the joint, blend end after it)
JOINT_BAND = {'sleeves': (0.06, 0.06)}
JOINT_AUX_FOLLOW = 0.5  # share of the lower bone's rotation a single helper takes
# 腕補助 shoulder helper (off): on the round-3 body with its closed shoulder socket it
# raised arms_up's worst stretch from x1.76 to x2.0-3.0 for every band / share / reach
# tried, and cut a notch into the rear armpit; the plain envelope blend is smoother there.
# Round 4 tried it again under the shrug, on the cap side only: x2.0-2.6 (any border
# between helper and no helper around the arm is a 60 deg seam). The shrug does its job.
SHOULDER_AUX = False
# share of 腕's rotation the clavicle (肩補助) takes: a raised arm lifts the shoulder
SHOULDER_SHRUG = 0.15
# share of 腕's rotation the sleeve drapes turn back (袖追従): gravity-ish when the arm rises
SLEEVE_COUNTER = 0.75   # round 4: 0.4 left the raised bags standing above the shoulders
DRAPE_SEGMENTS = 2    # bones per sleeve drape chain
# Blender only, round 7 (MMD simulates the drapes; the PMX keeps the -SLEEVE_COUNTER append
# of 腕): the round-4..6 driver set 袖追従 to 腕's quaternion to the power -0.75, which
# switches branch when 腕 passes 180 deg (the drape jumped 300 mm in one frame at
# idol_dance@81). Now 袖追従 turns SLEEVE_COUNTER of the way toward 袖重力, which turns back
# all of 腕 (the conjugate quaternion: no branch), and all the way once 腕 has turned
# SLEEVE_COUNTER_FULL[1] deg, ramping from SLEEVE_COUNTER_FULL[0]: at 180 deg, where
# shortest-arc blending switches sides, the result is the same either way, so the drape
# moves continuously. (Turning back the forearm's whole world rotation instead, gravity
# style, let bags bent overhead fall through the upper arm and folded them: 130-330
# flipped faces in hug_self, dance_heart, hands_behind_head.)
SLEEVE_COUNTER_FULL = (150.0, 180.0)   # (120 bunched the bow tails at a raised elbow: compress 0.05; 165 popped)
# Blender only: crowded sleeves compress. When the two drape roots come closer than
# SLEEVE_CROWD[1] m (arms folded or crossed in front of the body), each sleeve's body (the
# SLEEVE_BODY copies of the forearm bones, which carry the sleeve's forearm share) flattens
# toward the forearm, and each drape shrinks toward its root, by up to SLEEVE_CROWD[2] at
# SLEEVE_CROWD[0] m, so the two inflated bags press together instead of passing through
# each other. In MMD the copies just follow the forearm and the two sleeves' drape bodies
# collide (export_pmx.SLEEVE_R_GROUP).
SLEEVE_CROWD = (0.12, 0.32, 0.5)
# forearm bone -> (its sleeve copy, English name, share of SLEEVE_CROWD[2] it flattens by).
# Only ひじ: copies of 手捩 / 手首 also flattened the gathered hem and the cuff ruffle, which
# then went into the wrist and the other forearm (arms_crossed: 0.2% -> 4% inside).
SLEEVE_BODY = {'ひじ': ('袖胴', 'SleeveBody', 1.0)}
# Blender only: the copies also flatten as this side's wrist comes to the torso (hands on the
# flanks, an arm across the chest): (full at m, none from m, torso bones whose heads count)
SLEEVE_NEAR = (0.10, 0.18, ('上半身', '上半身2', '首'))
# 肩補助 carries this share of 肩's skin, by position along 肩 (inner end .. joint)
SHRUG_SPAN = (0.1, 0.8)
# Staged shoulder: helpers 肩補助2, 肩補助3 (children of 肩補助, at the shoulder joint) append
# shares of 腕's rotation so their total turns sit between the shrug's SHOULDER_SHRUG and
# 腕D's full turn, in thirds. A raised arm's skin then turns in steps across the socket
# instead of blending the shrug and the arm directly (~110 deg apart overhead, which
# linear skinning flattens into a narrow strip). The body's socket parameter
# (body.SOCKET_PARAM_ATTR: signed distance from the socket border, + on the arm) places
# them: the shrug's and arm's combined weight is handed shrug -> 肩補助2 -> 肩補助3 -> 腕D
# at these knots (m), the same all round the socket, so no border between helper and no
# helper crosses it (round 4's seams). (total turns, knots); None = off.
# Round 7: the last two knots 1.5 / 3.5 -> 2 / 4.5 cm (stage 3 -> 腕D further onto the arm):
# with the swing + twist stages, shoulder volume 0.60 -> 0.65 in hands_behind_head and
# 0.63 -> 0.66 in dance_sway.
SHOULDER_STAGES = ((SHOULDER_SHRUG + (1.0 - SHOULDER_SHRUG) / 3.0, SHOULDER_SHRUG + 2.0 * (1.0 - SHOULDER_SHRUG) / 3.0),
                   (-0.03, -0.005, 0.02, 0.045))
_SOCKET_S = None   # per-vertex socket parameter of the body object being skinned (_weights)
# Round 7, Blender: how the shrug, the stages and 腕D share 腕's rotation (_shoulder_drivers).
# A plain share q^k of 腕's turn (PMX 回転付与, slerp from identity) flips sides when the turn
# passes 180 deg, which an arm hanging 18 deg off vertical does on its way overhead with a
# little humeral roll (round 6: a 431 mm pop of 肩補助2 in idol_dance@80). Instead the turn
# splits into a swing that carries the arm from this reference direction (world, left side:
# out, a little up and back) to where it points, and a twist about the arm. The swing is
# singular only with the arm pointing straight across the front of the body to her other
# side; every pose and clip frame stays at least 64 deg from that (idol_dance@76; hug_self
# 75 deg). The stages take the share of that swing (B^k A^-k: B the swing from the reference to the
# arm, A the one to the rest direction, so rest is identity) and of the twist. The twist
# share fades out between SHOULDER_TWIST_FADE and 180 deg of twist, where a share of an
# angle would jump from +180 to -180 (only idol_dance's run -> overhead transition gets
# there: its keys carry 腕 once round a full turn). 腕D takes whatever is left of 腕's turn,
# so the arm points exactly where 腕 aims. The PMX keeps the plain shares.
SHOULDER_SWING_REF = (1.0, 0.1, 0.3)
SHOULDER_TWIST_FADE = 120.0     # deg
# The clavicle (肩補助) keeps round 6's plain share q^0.15 while 腕's turn stays below
# SHOULDER_SHRUG_BLEND[0] deg and blends to the swing + twist share by [1], before q^k would
# flip: the swing + twist shrug alone moved the shoulder joint up to 2.9 cm in poses whose
# hands were placed against the old one (hands in the hair and flowers in dance_heart,
# dance_point, jump_tuck). A long blend keeps the clavicle's handover slow even when the
# arm sweeps through it (idol_dance@78-81: arm bone pop 4.7 mm; 150-178 deg: 43 mm).
SHOULDER_SHRUG_BLEND = (100.0, 175.0)
# per helper name: (blend start before the joint, blend end after it) overriding the part's band
JOINT_BAND_BY_AUX = {'腕補助': (0.04, 0.06)}   # the knee uses JOINT_HINGE (round 5's band: 7.5 cm)
# per joint (first helper's name): the helpers as (share of the lower bone's rotation,
# position along the lower bone where the skin turns with that helper alone). The band
# turns smoothly from the upper bone (at -before) through each helper to the lower bone
# (at +after). The knee gets two helpers: a deep squat bends it ~120 deg, and one helper
# leaves 50-70 deg between neighbours, which linear skinning collapses into a notch.
JOINT_AUX_CHAIN = {'腕補助': ((0.35, 0.0),), 'ひざ補助': ((0.33, -0.025), (0.67, 0.025))}
# per helper: (full, none) lateral distance (m) from the lower bone's axis within which the
# split applies. The shoulder's upper bone 肩 also weights torso skin, which stays put.
# per helper: (band scale at the front, at the back, the front direction); unused while
# JOINT_HINGE covers the knee (round 5: (1.4, 0.85, (0, -1, 0)))
JOINT_FRONT_BACK = {}
JOINT_REACH_BY_AUX = {'腕補助': (0.05, 0.08)}
# per helper: hinge partition (_split_joint_aux), replacing JOINT_BAND_BY_AUX /
# JOINT_FRONT_BACK / aux_at for that joint. A vertex at distance t along the lower bone
# from the joint gets the angle atan2(t, d) and the knots are angles: (d at the front,
# at the side, at the back in m, interpolated quadratically in the cosine of the
# vertex's direction from the limb axis toward `forward`; knots in degrees from the
# upper limb (-) to the lower (+): upper end, one per helper, lower end; forward).
# Round 6, knee: the band reaches ~19 cm in front and at the sides, ~11 behind (d x
# tan 75 deg), so the kneecap wraps round a long arc while the hollow folds short. The
# round-5 band (7.5 cm x 1.4 in front, x 0.85 behind) swung thigh skin above the joint
# out into a lobe; shorter bands here (d 3-4 cm) pinched the knee or passed x1.85.
# Round 7: the hollow folds without crossing itself only if the share changes no faster
# along the angle than the bend allows (share' x bend < 1): behind the knee the band is
# longer (d 4.5 cm) and the knots wider (+-80 / +-27 deg), so a seiza (156 deg) folds the
# hollow instead of passing calf and thigh skin through each other (round 6: 160 faces
# flipped in seiza, 116 in jump_tuck, knee volume 0.61; now 54 / 44, 0.65). Longer still
# (7 cm, +-84 deg: 32 flips) swelled the calf behind a squatting knee into a hook, so the
# visible shape decided here. JOINT_HINGE_CAP keeps the angular band off the ankle and hip.
JOINT_HINGE = {'ひざ補助': ((0.05, 0.05, 0.045), (-80.0, -27.0, 27.0, 80.0), (0.0, -1.0, 0.0))}
JOINT_HINGE_CAP = (0.10, 0.16)   # m along the limb: beyond, the hinge band is all upper / lower limb


def _joint_aux(add, jp, en, joint, nxt, parent, lower, upper, s, sfx, jp_side, en_sfx, group):
    """Elbow / knee helpers: deform bones at the joint, children of the upper limb, that take
    a share of the lower bone's rotation (回転付与, JOINT_AUX_CHAIN; one helper with
    JOINT_AUX_FOLLOW by default). The band of skin and cloth around the joint turns through
    them, so a deep bend is shared between several partial turns instead of being
    stretched (or collapsed) across one blend. Helpers after the first are named jp2, jp3."""
    tail = joint + (nxt - joint).normalized() * JOINT_AUX_LEN
    chain = JOINT_AUX_CHAIN.get(jp, ((JOINT_AUX_FOLLOW, 0.0),))
    for i, (follow, at) in enumerate(chain):
        k = str(i + 1) if i else ''
        add(Bone(jp + k + sfx, jp_side + jp + k, en + k + en_sfx, _mx(joint, s), _mx(tail, s), parent, group=group,
                 meta={'follow': (lower, follow), 'joint_aux': (list(upper), lower), 'aux_at': at,
                       'aux_share': follow}))


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
        # 目 turns about the eyeball centre and appends 両目 fully (MMD standard: a gaze
        # keyed on 両目 turns both eyes)
        e = H['eye_R'] if tag == 'R' and 'eye_R' in H else _mx(eye, s)
        add(Bone('目' + sfx, jp_side + '目', 'Eye' + en_sfx, e, e - Vector((0, 0.03, 0)), '頭',
                 r=0.02, r_end=0.015, group='Body', meta={'follow': ('両目', 1.0)}))
        add(Bone('肩' + sfx, jp_side + '肩', 'Shoulder' + en_sfx, _mx((L['neck_half_w'] * 1.1, sj.y, L['shoulder_z']), s),
                 _mx(sj, s), '上半身2', r=0.045, r_end=0.03, group='Arms'))
        arm = '腕' + sfx              # the bone the arm's skin and children hang from
        if SHOULDER_SHRUG > 1e-4:
            # shoulder shrug. 腕 stays the standard bone motions key (child of 肩), but only
            # as input: 肩補助 turns SHOULDER_SHRUG of 腕's rotation about the inner end of
            # the clavicle (回転付与), lifting the shoulder as the arm rises, and the
            # deforming arm 腕D hangs from it at the joint and turns the remaining
            # 1 - SHOULDER_SHRUG of 腕. Powers of one rotation add up, so 腕D points exactly
            # where the animator aimed 腕, from a raised joint. Nothing appends a bone below
            # itself (MMD would cope, mmd_tools' 付与 emulation would make a dependency
            # cycle). All three share 腕's rest frame, so a share of its local rotation
            # means the same turn in each.
            arm_dir = (el - sj).normalized()
            sh0 = Vector((L['neck_half_w'] * 1.1, sj.y, L['shoulder_z']))
            add(Bone('肩補助' + sfx, jp_side + '肩補助', 'ShoulderAux' + en_sfx, _mx(sh0, s),
                     _mx(sh0 + arm_dir * JOINT_AUX_LEN, s), '肩' + sfx, group='Arms',
                     meta={'follow_q': ('腕' + sfx, SHOULDER_SHRUG), 'shrug_of': '肩' + sfx,
                           'shoulder': ('shrug', '肩補助' + sfx)}))
            add(Bone('腕' + sfx, jp_side + '腕', 'Arm' + en_sfx, _mx(sj, s), _mx(el, s), '肩' + sfx, connect=True,
                     deform=False, group='Arms'))
            arm = '腕D' + sfx
            add(Bone(arm, jp_side + '腕D', 'ArmD' + en_sfx, _mx(sj, s), _mx(el, s), '肩補助' + sfx,
                     r=0.04, r_end=0.03, group='Arms',
                     meta={'follow_q': ('腕' + sfx, 1.0 - SHOULDER_SHRUG), 'helper': True,
                           'shoulder': ('arm', '肩補助' + sfx)}))
            if SHOULDER_STAGES:
                # staged shoulder helpers (SHOULDER_STAGES): total turn = the shrug's
                # SHOULDER_SHRUG (their parent) + their own append, like 腕D's
                for i, total in enumerate(SHOULDER_STAGES[0]):
                    k = str(i + 2)
                    add(Bone('肩補助' + k + sfx, jp_side + '肩補助' + k, 'ShoulderAux' + k + en_sfx, _mx(sj, s),
                             _mx(el, s), '肩補助' + sfx, group='Arms',
                             meta={'follow_q': ('腕' + sfx, total - SHOULDER_SHRUG), 'helper': True,
                                   'shoulder': ('stage', '肩補助' + sfx),
                                   'stage': ('肩補助' + sfx, arm, (total - SHOULDER_SHRUG) / (1.0 - SHOULDER_SHRUG))}))
        else:
            add(Bone(arm, jp_side + '腕', 'Arm' + en_sfx, _mx(sj, s), _mx(el, s), '肩' + sfx, connect=True,
                     r=0.04, r_end=0.03, group='Arms'))
        if SHOULDER_AUX:
            # shoulder helper: the skin band around the shoulder joint (armpit, deltoid)
            # takes part of the arm's swing (JOINT_AUX_CHAIN), so a raised arm
            # doesn't pinch the armpit
            parent = '肩補助' + sfx if SHOULDER_SHRUG > 1e-4 else '肩' + sfx
            upper = ('肩' + sfx, '肩補助' + sfx) if SHOULDER_SHRUG > 1e-4 else ('肩' + sfx,)
            _joint_aux(add, '腕補助', 'ArmAux', sj, el, parent, arm, upper, s, sfx, jp_side, en_sfx, 'Arms')
        # semi-standard twist bones: 腕 -> 腕捩 -> ひじ -> 手捩 -> 手首. They turn only about
        # their own axis and take a share of their limb segment's weight that grows from
        # 0 at its top to 1 at its bottom (_split_along), so a twist spreads along the limb.
        add(Bone('腕捩' + sfx, jp_side + '腕捩', 'ArmTwist' + en_sfx, _mx(sj.lerp(el, TWIST_AT), s), _mx(el, s),
                 arm, group='Arms', meta={'twist_of': arm}))
        add(Bone('ひじ' + sfx, jp_side + 'ひじ', 'Elbow' + en_sfx, _mx(el, s), _mx(wr, s), '腕捩' + sfx, connect=True,
                 r=0.035, r_end=0.03, group='Arms'))
        _joint_aux(add, 'ひじ補助', 'ElbowAux', el, wr, '腕捩' + sfx, 'ひじ' + sfx, (arm, '腕捩' + sfx),
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
        if HIP_AUX:
            # hip helper (round 7): turns HIP_AUX of the thigh about the hip joint (回転付与);
            # the skin blending pelvis and thigh blends through it (_hat_remap)
            tail = hip + (knee - hip).normalized() * JOINT_AUX_LEN
            add(Bone('足補助' + sfx, jp_side + '足補助', 'LegAux' + en_sfx, _mx(hip, s), _mx(tail, s), '下半身',
                     group='Legs', meta={'follow': ('足' + sfx, HIP_AUX), 'joint_aux': (('下半身',), '足' + sfx),
                                         'aux_share': HIP_AUX, 'hat': True}))
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
KNEE_IK_MIN = math.radians(0.5)   # least knee bend the leg IK may solve to (positive X = forward bend)
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
HAIR_SECTORS = 10     # back-hair chains around the skull
HAIR_RING = True      # weight the back hair by angle between neighbouring chains (like the skirt)
HAIR_LOCK_CHAINS = True   # long back-hair locks get their own chains (_hair_locks)
HAIR_GRAVITY = 0.5    # Blender only: share of the torso's sideways bend the hanging hair turns back
HAIR_FOLLOW = 0.15    # share of the head's rotation the back-hair chains take (the scalp takes all of it)
# Pitch gravity: share of the torso's forward / backward pitch (上半身 + 上半身2) that
# each back-hair chain segment turns back, by segment index from the top. The top
# segment rests on the back and goes with it; the lower ones peel off and hang, so a
# forward bend no longer carries the lower hair rearward as one stiff cape. The shares
# add up down the chain: segment i of n has turned back HAIR_PITCH_GRAVITY x
# (i / (n - 1)) ** HAIR_PITCH_EXP of the pitch in all (0, .1, .36, .75 for 4 segments),
# so the bend spreads over the joints below the top one and grows toward the ends
# (with more of it higher up, the curtain's lower edge went 1.7 cm into her back in
# forward_bend). Blender: pitch only, about the bone's rest axis nearest world X; PMX:
# a negative 回転付与 of 上半身 (the whole turn, the only form a 付与 has), which MMD
# physics overrides when it is on.
HAIR_PITCH_GRAVITY = 0.75
HAIR_PITCH_EXP = 1.8        # sector chains (the curtain lies on her back)
HAIR_PITCH_LOCK_EXP = 1.3   # lock chains on the back: they start hanging a little higher up
# Outer locks (lock chains whose hanging part lies at least HAIR_OUTER_ANGLE deg round
# from straight back: beside the arms, off her back) settle fully and earlier (0, .42,
# .72, 1 for 4 segments). On the back such a profile put the locks 3 cm into her.
HAIR_OUTER_ANGLE = 55.0
HAIR_PITCH_OUTER = (1.0, 0.8)   # (total, exponent)
HAIR_LOCK_SEG = ((0.4, 5), (0.25, 4), (0.0, 3))   # lock length (m) -> chain segments
HAIR_PITCH_SOURCES = ('上半身', '上半身2')
# back hair is weighted to 頭 fully above the eyes, fading to the chains by just under
# the choker: below that it hangs at the shoulders, which a head turn must not sweep it
# into (at 0.6 follow a 45 deg turn pushed the curtain 2.5 cm into a closed shoulder)
HAIR_HEAD_FADE = (L['choker_z'] - 0.05, L['eye_z'] + 0.03)
SIDE_LOCKS_ON_HEAD = True   # face-framing side locks hang from 頭 itself instead of 髪追従
# hair_front object name prefix (+ _L / _R) -> side-lock chain (Japanese, English name)
SIDE_HAIR_FAMILIES = (('hair_cheek', '横髪', 'SideHair'), ('hair_lock', '横髪長', 'SideHairLong'),
                      ('hair_curl', '横髪巻', 'SideHairCurl'), ('hair_curtain', '横髪奥', 'SideHairBack'))
FOLLOW_FRONT = 1.0    # total share of the thighs' rotation a skirt chain takes at centre front
FOLLOW_BACK = 0.5     # ... and at centre back (a leg swung back still pushes the back skirt)
# how a chain's thigh share is spread over its joints (root, joint 1, joint 2...); the
# chain's total turn at the hem is the sum
SKIRT_SEG_FOLLOW = (0.65, 0.1)
SKIRT_LEG_SHARPNESS = 1.0   # 1 = the even split (1 + sin a) / 2; 1.5-2 sheared the petticoat (x2.0-2.4 in walk)
SKIRT_SECTORS = 16          # skirt chains around the body
SKIRT_SEGMENTS = 3          # bones per skirt chain
# Skirt drape (Blender): each chain joint turns forward / back only as far as the cloth must
# to clear the thighs, and hangs back toward its rest direction otherwise (_skirt_drape).
SKIRT_DRAPE = True
DRAPE_PHI = tuple(range(-60, 121, 10))   # deg of thigh pitch (forward +) the drape table samples
DRAPE_CLEAR = 0.012         # m kept between the innermost cloth layer and the thigh surface
DRAPE_BEND = 30.0           # deg: most a joint bends against the segment above it
DRAPE_UP = 10.0             # deg a segment may lift above the one over it
DRAPE_SPREAD = 100.0        # deg around the body over which a lifted chain lifts its neighbours
DRAPE_SPREAD_POW = 2.0      # ... falling off as 1 - (angle / spread) ** this (flat next to the lifted chain)
DRAPE_SHARE_AT = 60.0       # deg of thigh pitch at which the PMX's linear 回転付与 share is read


def skirt_follow(angle, s):
    """Share of thigh `s` (+1 left, -1 right) a skirt chain at `angle` takes (0 = behind,
    +90 = character's left). Both thighs together give FOLLOW_FRONT in front and
    FOLLOW_BACK behind; each thigh's part fades smoothly to 0 on the far side."""
    a = math.radians(angle)
    total = FOLLOW_BACK + (FOLLOW_FRONT - FOLLOW_BACK) * 0.5 * (1.0 - math.cos(a))
    # each thigh's part falls off around the body with SKIRT_LEG_SHARPNESS: the chains over
    # one leg follow that leg alone, so a stride lifts the skirt in front of the moving leg
    # instead of a broad panel; at the centre front and back both legs still share equally
    own, other = ((0.5 * (1.0 + k * math.sin(a))) ** SKIRT_LEG_SHARPNESS for k in (s, -s))
    return total * own / max(own + other, 1e-9)


def _thigh_profile(body, hip, knee, s):
    """(t, radius) samples of one thigh (side s) along hip -> knee from the body mesh:
    the 90th percentile distance of the body's vertices from the axis, per slab."""
    ax = knee - hip
    ln = float(np.linalg.norm(ax))
    ax = ax / ln
    ts = np.linspace(0.0, 1.0, 11)
    rs = np.full(len(ts), 0.065)
    if len(body):
        side = body[body[:, 0] * s > 0.005]
        rel = side - hip
        t = rel @ ax / ln
        lat = np.linalg.norm(rel - np.outer(rel @ ax, ax), axis=1)
        for i, tk in enumerate(ts):
            sel = lat[(np.abs(t - tk) < 0.05) & (lat < 0.12)]
            if len(sel) >= 8:
                rs[i] = float(np.percentile(sel, 90))
    return ts, rs


def _rot_x(p, c, a):
    """Points p turned about the world X axis through c by `a` rad, forward-positive
    (a vector hanging down swings toward -Y, the way she faces)."""
    ca, sa = math.cos(a), math.sin(a)
    q = p - c
    return np.stack([q[..., 0], q[..., 1] * ca + q[..., 2] * sa, -q[..., 1] * sa + q[..., 2] * ca], -1) + c


def _thigh_depth(q, hip, knee, prof):
    """How far points q lie inside the thigh capsule hip -> knee widened by DRAPE_CLEAR
    (<= 0 outside); the hip end (t < 0.12, the pelvis) does not count."""
    ax = knee - hip
    ln2 = float(ax @ ax)
    t = ((q - hip) @ ax) / ln2
    tc = np.clip(t, 0.0, 1.0)
    d = np.linalg.norm(q - (hip + tc[..., None] * ax), axis=-1)
    r = np.interp(tc, prof[0], prof[1]) + DRAPE_CLEAR
    return np.where((t > 0.12) & (t < 1.08), r - d, -1.0)


def _skirt_drape(chains, pts, cy, hip, knee, body):
    """Drape table of the skirt chains: {chain k: {'L'|'R': (nseg, len(DRAPE_PHI)) absolute
    forward turn (rad) of each segment}} for that thigh pitched alone by each DRAPE_PHI.

    Each segment, root first, takes the smallest turn (from its rest direction, so it
    hangs, within DRAPE_BEND of the segment above) that keeps the cloth of its sector
    (skirt and petticoat, the innermost layer counts) DRAPE_CLEAR off the swung thigh.
    Chains then lift their neighbours by a share falling off over DRAPE_SPREAD, as the
    cloth between them is pulled along. Cloth already inside the thigh at rest is ignored."""
    ang = np.degrees(np.arctan2(pts[:, 0], pts[:, 1] - cy))
    step = 360.0 / SKIRT_SECTORS
    grid = np.radians(np.arange(-150.0, 150.1, 2.5))
    phis = np.radians(np.array(DRAPE_PHI, dtype=float))
    out = {}
    sides = {}
    for tag, s in (('L', 1.0), ('R', -1.0)):
        h, kn = hip * np.array([s, 1, 1]), knee * np.array([s, 1, 1])
        sides[tag] = (h, kn, _thigh_profile(body, h, kn, s))
    raw = {tag: {} for tag in sides}
    for k, (a, joints) in enumerate(chains):
        J = np.array([tuple(j) for j in joints])
        n = len(J) - 1
        d = (ang - a + 180.0) % 360.0 - 180.0
        sel = pts[np.abs(d) < 0.6 * step]
        if len(sel) > 900:
            sel = sel[np.linspace(0, len(sel) - 1, 900).astype(int)]
        zj = J[:, 2]
        u = np.interp(-sel[:, 2], np.maximum.accumulate(-zj), np.arange(n + 1.0))
        keep = u > 0.35
        sel, u = sel[keep], u[keep]
        seg = np.clip(np.floor(u), 0, n - 1).astype(int)
        for tag, (h, kn, prof) in sides.items():
            rest_in = _thigh_depth(sel, h, kn, prof) > 0.0
            tab = np.zeros((n, len(phis)))
            for pi, phi in enumerate(phis):
                knee_p = _rot_x(kn, h, phi)
                A = []
                q = sel.copy()
                Jc = J.copy()
                for j in range(n):
                    prev = A[-1] if A else 0.0
                    m = (seg == j) & ~rest_in
                    cand = grid[np.abs(grid - prev) <= math.radians(DRAPE_BEND)]
                    if not m.any():
                        best = min(cand, key=lambda g: (abs(g), g))
                    else:
                        P = q[m]
                        dep = np.stack([_thigh_depth(_rot_x(P, Jc[j], g - prev), h, knee_p, prof).max()
                                        for g in cand])
                        clear = dep <= 0.0
                        if clear.any():
                            c = cand[clear]
                            best = c[np.argmin(np.abs(c) + 1e-6 * c)]
                        else:
                            best = cand[np.argmin(dep)]
                    A.append(float(best))
                    turn = best - prev
                    below = seg >= j
                    q[below] = _rot_x(q[below], Jc[j], turn)
                    Jc[j + 1:] = _rot_x(Jc[j + 1:], Jc[j], turn)
                # no zigzag: a segment that must lift more than the one above it lifts that
                # one too (within DRAPE_UP), so the cloth curves over the thigh in one
                # direction (blended skinning cuts a zigzag's corners into the leg)
                up = math.radians(DRAPE_UP)
                for j in range(n - 2, -1, -1):
                    if A[j + 1] > 0:
                        A[j] = max(A[j], A[j + 1] - up)
                    elif A[j + 1] < 0:
                        A[j] = min(A[j], A[j + 1] + up)
                tab[:, pi] = A
            raw[tag][k] = tab
    angles = np.array([a for a, _ in chains])
    for tag in sides:
        for k in range(len(chains)):
            dk = np.abs((angles - angles[k] + 180.0) % 360.0 - 180.0)
            f = np.clip(1.0 - (dk / DRAPE_SPREAD) ** DRAPE_SPREAD_POW, 0.0, 1.0)
            f[dk < 1e-6] = 1.0
            stack = np.stack([raw[tag][m] * f[m] for m in range(len(chains))])
            mx, mn = stack.max(0), stack.min(0)
            out.setdefault(k, {})[tag] = np.maximum(mx, 0.0) + np.minimum(mn, 0.0)
    return out


HAIR_LOCK_LEN = 0.2    # a back-hair loose part at least this long (m) ...
HAIR_LOCK_SPAN = 70.0  # ... spanning less than this (deg) around the skull is a lock with its own chain


def _lock_key(pts):
    """Identity of a loose part: its rounded centroid and vertex count (rest positions,
    the same in every pass)."""
    return tuple(np.round(pts.mean(0), 4).tolist()) + (len(pts),)


def _hair_locks(objs):
    """([(key, points)] for the long narrow loose parts of the back hair, points of the rest)."""
    locks, rest = [], []
    for o in objs:
        co = _world_verts([o])
        if not len(co):
            continue
        lab = _islands(len(co), _topology(o, co))
        for k in np.unique(lab):
            p = co[lab == k]
            ang = np.degrees(np.arctan2(p[:, 0], p[:, 1] - L['head_center_y']))
            c = math.degrees(math.atan2(float(np.sin(np.radians(ang)).mean()), float(np.cos(np.radians(ang)).mean())))
            dev = (ang - c + 180.0) % 360.0 - 180.0
            span = float(np.percentile(dev, 95) - np.percentile(dev, 5))
            long_ = min(L['eye_z'], float(p[:, 2].max())) - float(p[:, 2].min()) >= HAIR_LOCK_LEN
            if HAIR_LOCK_CHAINS and long_ and span < HAIR_LOCK_SPAN and len(p) >= 24:
                locks.append((_lock_key(p), p))
            else:
                rest.append(p)
    locks.sort(key=lambda kp: kp[0])
    return locks, (np.concatenate(rest) if rest else np.zeros((0, 3)))


def _hair_pitch_gravity(chain, byname, total=HAIR_PITCH_GRAVITY, exp=HAIR_PITCH_EXP):
    """Give the segments of one back-hair chain their HAIR_PITCH_GRAVITY shares (meta
    'pitch_gravity': [(torso bone, share)], read by _create_armature) and the PMX 付与
    (meta 'append': a negative share of 上半身). Returns the chain."""
    srcs = [n for n in HAIR_PITCH_SOURCES if n in byname]

    def cum(j, n):
        return total * (j / (n - 1)) ** exp
    for b in chain:
        i, n = b.meta.get('seg', 0), b.meta.get('nseg', 1)
        if i < 1 or n < 2:
            continue
        k = cum(i, n) - cum(i - 1, n)
        if k > 1e-4 and srcs:
            b.meta['pitch_gravity'] = [(src, k) for src in srcs]
            b.meta['append'] = (srcs[0], -k)
    return chain


def _secondary_bones(parts, core):
    """Hair / skirt / sleeve chains for the parts present. parts: {name: [mesh objs]}."""
    bones = []
    byname = {b.name: b for b in core}

    def verts(*names):
        objs = [o for n in names for o in parts.get(n, [])]
        return _world_verts(objs)

    def hair_parent():
        # long hair hangs from a bone on the neck that takes HAIR_FOLLOW of the head's
        # rotation (_hair_head_fade turns the hair near the scalp with the head fully),
        # so a turned head doesn't swing the whole curtain through the body
        if not any(b.name == HAIR_ROOT for b in bones):
            h = byname['頭'].head
            meta = {'follow': ('頭', HAIR_FOLLOW)} if HAIR_FOLLOW > 1e-4 else {}
            if HAIR_GRAVITY > 1e-4:
                meta['gravity'] = [(n, HAIR_GRAVITY) for n in ('上半身', '上半身2') if n in byname]
            bones.append(Bone(HAIR_ROOT, HAIR_ROOT, 'HairRoot', h, h + Vector((0, 0, 0.03)), '首',
                              deform=False, group='HairFollow', meta=meta))
        return HAIR_ROOT

    # back hair: each long lock (a loose part, _hair_locks) gets its own chain along its
    # centreline, so it bends along its length; the rest (the curtain behind them) hangs
    # from sectors around the skull axis. All hang from eye level.
    locks, rest = _hair_locks(parts.get('hair_back', []))
    for k, (key, lp) in enumerate(locks):
        top = min(L['eye_z'], float(lp[:, 2].max()))
        nseg = next(s for h, s in HAIR_LOCK_SEG if top - lp[:, 2].min() >= h)
        joints = _band_chain(lp[lp[:, 2] <= top + 0.02], top, float(lp[:, 2].min()), nseg)
        if joints:
            low = lp[lp[:, 2] < L['choker_z']]
            low = low if len(low) else lp
            ang = math.degrees(math.atan2(abs(float(low[:, 0].mean())), float(low[:, 1].mean()) - L['head_center_y']))
            pitch = HAIR_PITCH_OUTER if ang >= HAIR_OUTER_ANGLE else (HAIR_PITCH_GRAVITY, HAIR_PITCH_LOCK_EXP)
            print(f'rig hair lock 後髪束{k}: {nseg} segments, {ang:.0f} deg round, '
                  f'{"outer" if ang >= HAIR_OUTER_ANGLE else "back"} pitch gravity')
            bones += _hair_pitch_gravity(
                _chain_bones(f'後髪束{k}', f'後髪束{k}', f'HairLock{k}', joints, hair_parent(), 0.03, 'Hair',
                             meta={'lock': key}), byname, *pitch)
    if len(rest):
        chains = _sector_chains(rest, (0.0, L['head_center_y']), L['eye_z'], HAIR_SECTORS, 4, 0.10)
        for k, (ang, joints) in enumerate(chains):
            bones += _hair_pitch_gravity(
                _chain_bones(f'後髪{k}', f'後髪{k}', f'HairBack{k}', joints, hair_parent(), 0.035, 'Hair',
                             meta={'chain': k, 'angle': ang, 'cy': L['head_center_y']}), byname)

    # side locks: hair_front strands hanging beside the face, below the eyes. Each lock
    # family (SIDE_HAIR_FAMILIES: cheek locks, the long shoulder lock, the curl, the side
    # curtain) gets its own short chain when its objects exist, so the families sway apart
    # instead of as one slab; otherwise one chain per side through all of them.
    top = L['eye_z'] - 0.02
    parent = '頭' if SIDE_LOCKS_ON_HEAD else None
    fronts = parts.get('hair_front', [])
    families = any(o.name.startswith(p + '_') for o in fronts for p, _, _ in SIDE_HAIR_FAMILIES)
    for tag, s, jp_side in SIDES:
        groups = []
        for prefix, jp, en in SIDE_HAIR_FAMILIES:
            objs = [o for o in fronts if o.name.startswith(f'{prefix}_{tag}')]
            if objs:
                groups.append((jp, en, _world_verts(objs), prefix))
        if not families:          # (with families on one side only, the other rides 頭)
            groups = [('横髪', 'SideHair', verts('hair_front'), None)]
        for jp, en, pts, prefix in groups:
            sel = pts[(pts[:, 0] * s > L['head_half_w'] * 0.6) & (pts[:, 2] < top)] if len(pts) else pts
            if len(sel) < 12 or top - sel[:, 2].min() < 0.04:
                continue
            nseg = 3 if top - sel[:, 2].min() >= 0.12 else 2
            joints = _band_chain(sel, float(sel[:, 2].max()), float(sel[:, 2].min()), nseg)
            if joints:
                bones += _chain_bones(jp, jp, en, joints, parent or hair_parent(), 0.025, 'Hair',
                                      sfx='.' + tag, jp_side=jp_side, en_sfx='_' + tag,
                                      meta={'family': prefix} if prefix else None)

    # skirt (+ petticoat): sectors around the body axis, hanging from the hip
    pts = verts('skirt', 'petticoat')
    if len(pts):
        cy = float(pts[:, 1].mean())
        chains = _sector_chains(pts, (0.0, cy), L['hip_z'], SKIRT_SECTORS, SKIRT_SEGMENTS, 0.08)
        drape = {}
        if SKIRT_DRAPE and chains:
            th = byname['足.L']
            drape = _skirt_drape(chains, pts, cy, np.array(th.head), np.array(th.tail), verts('body'))
        for k, (ang, joints) in enumerate(chains):
            hem_r = max(0.03, math.hypot(joints[-1].x, joints[-1].y - cy) * math.pi / SKIRT_SECTORS)
            # the chain hangs from two follow bones that add a share of each thigh's
            # rotation (PMX 回転付与), so the skirt moves with the legs as a whole
            # instead of being torn by per-vertex leg weights
            # The share is spread down the chain (SKIRT_SEG_FOLLOW): the root takes part of
            # it at the hip and the joints below add the rest, so a raised thigh lifts the
            # skirt in a soft curve instead of swinging the whole panel about the hip line.
            chain = _chain_bones(f'スカート{k}', f'スカート{k}', f'Skirt{k}', joints, '下半身', hem_r, 'Skirt',
                                 meta={'chain': k, 'angle': ang, 'cy': cy})
            parent = '下半身'
            for i, seg in enumerate(chain):
                frac = SKIRT_SEG_FOLLOW[i] if i < len(SKIRT_SEG_FOLLOW) else 0.0
                if frac > 1e-4 or k in drape:
                    head = seg.head
                    for tag, s, jp_side in SIDES[::-1]:
                        name = f'スカート{k}追従{jp_side}' + (f'{i}' if i else '')
                        share = skirt_follow(ang, s) * frac
                        meta = {'follow': (f'足.{tag}', share)}
                        if k in drape:
                            # the PMX gets the drape's linear part at DRAPE_SHARE_AT (physics does the
                            # rest there); Blender turns the bone by the drape table itself
                            tab = drape[k][tag]
                            xs = np.array(DRAPE_PHI, dtype=float)
                            a = math.radians(DRAPE_SHARE_AT)
                            turn = lambda r: float(np.interp(DRAPE_SHARE_AT, xs, r))  # noqa: E731
                            lin = (turn(tab[i]) - (turn(tab[i - 1]) if i else 0.0)) / a
                            meta = {'follow': (f'足.{tag}', round(lin, 4)),
                                    'drape': {'i': i, 'L': drape[k]['L'], 'R': drape[k]['R'], 'own': tag,
                                              'above': f'スカート{k}追従左' + (f'{i - 1}' if i > 1 else '')}}
                        # a drape bone points along -X: its local Y is the forward-pitch axis, which
                        # the axis-angle rotation keeps even when a pose reset zeroes it
                        tail = head + (Vector((-0.03, 0, 0)) if k in drape else Vector((0, 0, 0.03)))
                        bones.append(Bone(name, name, f'Skirt{k}Follow{tag}' + (f'{i}' if i else ''), head,
                                          tail, parent, deform=False, group='SkirtFollow', meta=meta))
                        parent = name
                seg.parent = parent
                bones.append(seg)
                parent = seg.name

    # sleeve drapes: sleeve vertices well away from the arm bones hang from the forearm
    pts = verts('sleeves')
    if len(pts):
        for tag, s, jp_side in SIDES:
            side = pts[pts[:, 0] * s > 0.05]
            if not len(side):
                continue
            arm = [byname[f'{n}.{tag}'] for n in ('腕', 'ひじ', '手首')]   # rest positions only
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
            joints = _band_chain(below, root.z, float(below[:, 2].min()), DRAPE_SEGMENTS)
            if joints:
                joints[0] = root
                parent = el.name
                if SLEEVE_COUNTER > 1e-4:
                    # the drape hangs from a bone that turns back SLEEVE_COUNTER of the upper
                    # arm's rotation (negative 回転付与): a raised arm lets the bag fall back
                    # toward the shoulder instead of standing up with its rest fullness.
                    # Built parallel to 腕 (same rest frame) for the shared quaternion. It
                    # hangs from the forearm, so with a bent elbow it is only gravity-ish.
                    # In MMD the drape segments are physics bodies and gravity does this;
                    # the append matters there only with physics off.
                    up = byname[f'腕.{tag}']
                    adir = (up.tail - up.head).normalized()
                    parent = f'袖追従.{tag}'
                    meta = {'follow_q': (f'腕.{tag}', -SLEEVE_COUNTER)}
                    if SLEEVE_COUNTER_FULL:
                        # Blender only (SLEEVE_COUNTER_FULL): 袖重力 shares 袖追従's rest frame
                        # and turns back all of 腕; 袖追従 turns toward it
                        grav = f'袖重力.{tag}'
                        bones.append(Bone(grav, f'{jp_side}袖重力', f'SleeveCounter_{tag}', root, root + adir * 0.03,
                                          el.name, deform=False, group='SleeveFollow',
                                          meta={'helper': True, 'conj_of': f'腕.{tag}'}))
                        meta['sleeve_counter'] = grav
                        if SLEEVE_CROWD:
                            # the sleeve's forearm share rides copies of the forearm bones that
                            # flatten toward the forearm when crowded (SLEEVE_BODY)
                            for stem, (jp, en, share) in SLEEVE_BODY.items():
                                src_b = byname.get(f'{stem}.{tag}')
                                if src_b is not None:
                                    bones.append(Bone(f'{jp}.{tag}', f'{jp_side}{jp}', f'{en}_{tag}', src_b.head,
                                                      src_b.tail, src_b.name, group='SleeveBody',
                                                      meta={'helper': True, 'crowd': grav, 'crowd_share': share}))
                            meta['crowd'] = grav
                    bones.append(Bone(parent, f'{jp_side}袖追従', f'SleeveFollow_{tag}', root, root + adir * 0.03,
                                      el.name, deform=False, group='SleeveFollow', meta=meta))
                bones += _chain_bones('袖', '袖', 'Sleeve', joints, parent, 0.04, 'Sleeve',
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
        side = [b for b in bones if b.group == 'Hair' and b.name.startswith(own)]
        fam = next((p for p, _, _ in SIDE_HAIR_FAMILIES if part == 'hair_front' and obj.name.startswith(p + '_')), None)
        mine = [b for b in side if fam and b.meta.get('family') == fam]
        if mine:        # a side-lock family rides its own chains only
            side = mine
        elif part == 'hair_front' and any(b.meta.get('family') for b in side):
            side = []   # bangs, crown: the head, when every family has its own chain
        return ['頭'] + [b.name for b in side if b.deform]
    if part == 'head':
        low = obj.name.lower()
        if obj in eye_objects(_HEAD_OBJS or [obj]):
            p = obj.get(EYE_PIVOT_PROP)
            if p is not None and len(p) == 3:
                return ['目.L' if p[0] >= 0 else '目.R']   # one eye: rigid on its own bone
            return ['目.L', '目.R']
        if 'eye' in low:
            return ['頭']           # eye whites and other eye pieces that do not turn: rigid on the head
        return ['頭', '首', '上半身2']
    if part in ('skirt', 'petticoat'):
        return ['上半身', '下半身'] + grp('Skirt')
    if part == 'sleeves':      # detached sleeves: arm only, never the torso
        return _names(bones, lambda b: base(b) in ('肩', '肩補助', '腕補助', '腕', '腕D', '腕捩', 'ひじ補助', 'ひじ', '手捩', '手首')) + grp('Sleeve', 'SleeveBody')
    if part == 'bodice':       # a corset: the torso skin's weights (_skin_sample), the shoulder bones only where
        # the skin under the top rim has them (the armpit); anything hanging below the hip rides the skirt
        return ['上半身', '上半身2', '首', '下半身'] + _names(bones, lambda b: base(b) in SKIN_FOLLOW_ARM) + grp('Skirt')
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
RING_MAX_GAP = 1.6    # chains farther apart than this (in sector steps) are not blended


def _skirt_weights(co, bones, group='Skirt', body_names=('上半身', '下半身'), max_gap=None):
    """(V, B) weights for skirt / petticoat vertices, at most 4 bones each by construction.

    Around the body axis a vertex blends linearly between the two nearest skirt chains
    by angle; down each chain it blends between consecutive bones by height (hat
    functions centred on the bones), and over the first half bone below the hip it
    hands over from 上半身/下半身 (the same envelopes as the bodice above it). The thighs
    are not weighted here at all: the chains follow them through their follow bones.
    The long back hair uses the same ring of chains (group 'Hair', handing over from 頭),
    so neighbouring locks blend instead of each riding one chain. Across a gap wider than
    max_gap sectors (the hair has no chain over the face) a vertex follows its nearest chain.
    """
    V = len(co)
    col = {b.name: i for i, b in enumerate(bones)}
    W = np.zeros((V, len(bones)))
    chains = {}
    for i, b in enumerate(bones):
        if b.group == group and 'chain' in b.meta:
            chains.setdefault(b.meta['chain'], []).append((b.meta['seg'], i, b))
    body = [n for n in body_names if n in col]
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
    if max_gap and len(A) > 1:
        step = float(np.median(np.diff(np.sort(A))))
        # across a wide gap each side keeps its own chain, handing over within one sector
        # step of the gap's middle (continuous, no snap)
        snap = 1.0 - _smoothstep(gap / 2 - step / 2, gap / 2 + step / 2, dp)
        front = ((180.0 - A[prv]) % 360.0) < gap          # the gap spans the front (the face)
        w_prv = np.where((gap > max_gap * step) & front, snap, w_prv)
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
    sub = [bones[i] for i in bi]
    env = _envelope(co, sub)
    if group == 'Skirt':
        env = _skin_sample(co, [b.name for b in sub], env)
    W[:, bi] += env * rest[:, None]
    return W


# Garments over the torso take the weights of the body skin under them, so skin and cloth
# move together (the skirt's waist in a side bend, the bodice rim at the armpit)
SKIN_FOLLOW = True
# round 7: garments sample the shrug and the staged shoulder bones themselves (they used to
# be folded into the shrug and 腕D): the Blender stages turn by swing + twist
# (_shoulder_drivers), which a blend of the shrug and the arm no longer reproduces (the
# bodice sank 1.5 cm into the chest in jump_tuck, dance_point and dance_heart)
SKIN_FOLLOW_ARM = ('肩', '肩補助', '肩補助2', '肩補助3', '腕D')   # shoulder bones the bodice may take from the skin
BODICE_ARM_CAP = 0.12      # most of a bodice vertex the arm (腕D) may carry
SKIN_K = 8                 # nearest skin vertices averaged (inverse distance) ...
SKIN_SOFT = 0.005          # ... softened by this many m, so the sample varies smoothly
_SKIN = None               # (points (N, 3), {bone: column}, weights (N, B)) of the skinned body (build_rig)


SKIN_REACH = (0.025, 0.07)  # m from the skin: garment weights hand over from the skin's to their own


def _skin_sample(co, names, base, reach=None):
    """`base` (V, len(names)) blended toward the weights of the body skin nearest each
    point (SKIN_K nearest vertices, inverse-distance, among the skin vertices that are
    mostly `names`), fully within reach[0] of the skin, not at all beyond reach[1]
    (default SKIN_REACH), so cloth on the body moves with it and loose cloth keeps `base`.
    Returns `base` unchanged without a skinned body."""
    reach = SKIN_REACH if reach is None else reach
    if not SKIN_FOLLOW or _SKIN is None:
        return base
    pts, col, W = _SKIN
    cols = [col.get(n) for n in names]
    if all(c is None for c in cols):
        return base
    sub = np.stack([W[:, c] if c is not None else np.zeros(len(W)) for c in cols], 1)
    keep = sub.sum(1) > 0.5
    if keep.sum() < SKIN_K:
        return base
    from mathutils.kdtree import KDTree
    pts, sub = pts[keep], sub[keep] / sub[keep].sum(1, keepdims=True)
    tree = KDTree(len(pts))
    for i, p in enumerate(pts):
        tree.insert(p, i)
    tree.balance()
    nn = np.zeros((len(co), SKIN_K), dtype=np.int64)
    dd = np.full((len(co), SKIN_K), 1e3)
    for v, q in enumerate(co):
        for k, (_, i, dist) in enumerate(tree.find_n(q, SKIN_K)):
            nn[v, k], dd[v, k] = i, dist
    wt = 1.0 / (dd + SKIN_SOFT)
    sk = np.einsum('vk,vkb->vb', wt, sub[nn]) / wt.sum(1, keepdims=True)
    f = (1.0 - _smoothstep(reach[0], reach[1], dd.min(1)))[:, None]
    return base * (1.0 - f) + sk * f


def _store_skin(objs):
    """Remember the skinned body's vertices and weights for _skin_sample."""
    global _SKIN
    pts, rows, names = [], [], {}
    for o in objs:
        co = _world_verts([o])
        if not len(co):
            continue
        gn = {g.index: g.name for g in o.vertex_groups}
        for v in o.data.vertices:
            rows.append([(names.setdefault(gn[g.group], len(names)), g.weight) for g in v.groups if g.group in gn])
        pts.append(co)
    if not pts:
        _SKIN = None
        return
    W = np.zeros((sum(len(p) for p in pts), len(names)))
    for i, r in enumerate(rows):
        for c, wv in r:
            W[i, c] = wv
    _SKIN = (np.concatenate(pts), names, W)


# ---- per-object helpers: topology, sides, smoothing, pruning
SMOOTH_RADIUS = {     # metres of weight smoothing along the surface, per part
    'body': 0.008, 'head': 0.01, 'shoes': 0.012, 'accessories': 0.012, 'bodice': 0.035,
    'hair_front': 0.025, 'hair_back': 0.03, 'sleeves': 0.065, 'skirt': 0.03, 'petticoat': 0.04,
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
    """Loose-part label of every vertex: the smallest vertex index in its part.
    Vectorized union-find (hook roots onto the smaller root, then pointer jumping)."""
    lab = np.arange(n)
    if not len(edges):
        return lab
    a, b = edges[:, 0], edges[:, 1]
    while True:
        la, lb = lab[a], lab[b]
        diff = la != lb
        if not diff.any():
            return lab
        np.minimum.at(lab, np.maximum(la, lb)[diff], np.minimum(la, lb)[diff])
        while True:
            nl = lab[lab]
            if (nl == lab).all():
                break
            lab = nl


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
    # only the bones this mesh uses: the rest stay zero under any averaging
    act = np.nonzero(np.abs(w).max(0) > 0.0)[0]
    if not len(act):
        return w
    out = w.copy()
    out[:, act] = _smooth_ml(w[:, act], co, edges, radius, 0)
    return out


def _edge_ref(co, edges):
    ln = np.linalg.norm(co[edges[:, 0]] - co[edges[:, 1]], axis=1)
    pos = ln[ln > 1e-6]
    return ln, (float(np.median(pos)) if len(pos) else 0.0)


def _match(co, edges, ln):
    """Cluster labels pairing each vertex with a neighbour (handshake matching on the
    shortest edges, a few rounds), so the coarse graph keeps the mesh's connectivity:
    clusters never join surfaces that only lie close in space. Deterministic."""
    n = len(co)
    lab = -np.ones(n, dtype=np.int64)
    src = np.concatenate([edges[:, 0], edges[:, 1]])
    dst = np.concatenate([edges[:, 1], edges[:, 0]])
    d = np.concatenate([ln, ln])
    keep = src != dst
    src, dst, d = src[keep], dst[keep], d[keep]
    nxt = 0
    for _ in range(3):
        free = (lab[src] < 0) & (lab[dst] < 0)
        s, t, dd = src[free], dst[free], d[free]
        if not len(s):
            break
        order = np.lexsort((t, dd, s))          # per source: shortest edge first, then index
        s, t = s[order], t[order]
        first = np.ones(len(s), dtype=bool)
        first[1:] = s[1:] != s[:-1]
        choice = -np.ones(n, dtype=np.int64)
        choice[s[first]] = t[first]
        v = np.nonzero(choice >= 0)[0]
        mutual = v[(choice[choice[v]] == v) & (v < choice[v])]
        if not len(mutual):
            break
        ids = nxt + np.arange(len(mutual))
        lab[mutual] = ids
        lab[choice[mutual]] = ids
        nxt += len(mutual)
    single = np.nonzero(lab < 0)[0]
    lab[single] = nxt + np.arange(len(single))
    return lab, nxt + len(single)


SMOOTH_DIRECT = 64   # iterations above which smoothing runs on a coarsened mesh first


def _smooth_ml(w, co, edges, radius, depth):
    """Smoothing about `radius` metres whatever the mesh density. Within SMOOTH_DIRECT
    iterations of the plain diffusion (_diffuse) it runs directly; otherwise neighbouring
    vertices are paired (_match), the cluster averages are smoothed on the coarse graph
    (recursively), the coarse change is added back to every vertex of its cluster, and a
    short diffusion on the fine mesh (about one coarse edge) evens out the cluster steps.
    Diffusion radii add in squares, so the two passes together give `radius`. Cost stays
    about linear in the vertex count."""
    ln, ref = _edge_ref(co, edges)
    if ref <= 0.0:
        return w
    iters = int(round(2.0 * (radius / ref) ** 2))
    if iters <= SMOOTH_DIRECT or len(co) < 64 or depth >= 12:
        return _diffuse(w, co, edges, ln, ref, min(iters, MAX_SMOOTH_ITERS))
    lab, nc = _match(co, edges, ln)
    if nc > 0.85 * len(co):       # nothing to pair (a soup of separate edges): plain diffusion
        return _diffuse(w, co, edges, ln, ref, min(iters, MAX_SMOOTH_ITERS))
    cnt = np.bincount(lab, minlength=nc).astype(float)[:, None]
    cco = np.zeros((nc, 3))
    np.add.at(cco, lab, co)
    cco /= cnt
    cw = np.zeros((nc, w.shape[1]))
    np.add.at(cw, lab, w)
    cw /= cnt
    ce = np.stack([lab[edges[:, 0]], lab[edges[:, 1]]], 1)
    ce = ce[ce[:, 0] != ce[:, 1]]
    ce = np.unique(np.sort(ce, 1), axis=0) if len(ce) else ce
    _, cref = _edge_ref(cco, ce) if len(ce) else (None, 0.0)
    post = min(radius * 0.7, 1.5 * max(cref, ref))      # fine-level pass: about one coarse edge
    rc = math.sqrt(max(radius ** 2 - post ** 2, 0.0))
    if len(ce):
        cw = _smooth_ml(cw, cco, ce, rc, depth + 1) - cw
    else:
        cw = np.zeros_like(cw)
    w = w + cw[lab]
    return _diffuse(w, co, edges, ln, ref, int(round(2.0 * (post / ref) ** 2)))


def _diffuse(w, co, edges, ln, ref, iters):
    """`iters` Laplacian steps of the weight rows along the mesh edges."""
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


PRUNE_FOLD = 2.0      # a bone keeps all its weight from this many times the 5th-largest weight up
PRUNE_SMOOTH = 0.03    # m: smoothing of the copy that picks the kept bones (_prune's guide)
PRUNE_MOTION = True   # refit pruned vertices to their unpruned motion (_motion_refit)
FOLD_TARGET_MIN = 0.05   # a helper folds into a bone it blends between in full once that keeps this much


_PARENTS = {}         # bone name -> parent name, the whole rig (set by build_rig)
FOLD_CHAIN_GROUPS = ('Skirt', 'Hair', 'Sleeve')   # chain bones fold into the kept bones in proportion


def _fold_targets(bones):
    """Per column: [(column, fraction)], the bones a pruned weight folds into, first
    choice first, so the skin keeps moving almost as before. A joint helper splits into
    the upper and lower bone by its share of the bend (ひじ補助 50/50 between 腕捩 and ひじ);
    a twist bone goes to the bone it twists with, the shrug to 肩. Then, for limb and torso
    bones, the nearest relatives: the parent chain upward, then the children. Secondary
    chains (skirt, hair, sleeve drapes) have none: neighbouring chains move alike, so
    their weight is spread over the kept bones in proportion."""
    col = {b.name: j for j, b in enumerate(bones)}
    kids = {}
    for b in bones:
        p = _PARENTS.get(b.name, b.parent)
        while p and p not in col:
            p = _PARENTS.get(p)
        if p:
            kids.setdefault(p, []).append(b.name)
    out = []
    for b in bones:
        m, t = b.meta, []
        if 'joint_aux' in m:
            upper, lower = m['joint_aux']
            share = m.get('aux_share', 0.5)
            up = next((u for u in reversed(list(upper)) if u in col), None)
            if up is not None:
                t.append((col[up], 1.0 - share))
            if lower in col:
                t.append((col[lower], share))
        for key in ('twist_of', 'shrug_of'):
            if m.get(key) in col:
                t.append((col[m[key]], 1.0))
        if 'stage' in m:        # a shoulder stage splits into the shrug and the arm by its share
            lo, hi, frac = m['stage']
            t += [(col[n], f) for n, f in ((lo, 1.0 - frac), (hi, frac)) if n in col]
        if b.group not in FOLD_CHAIN_GROUPS:
            p = _PARENTS.get(b.name, b.parent)
            while p:
                if p in col and bones[col[p]].group not in FOLD_CHAIN_GROUPS:
                    t.append((col[p], 1.0))
                p = _PARENTS.get(p)
            t += [(col[c], 1.0) for c in sorted(kids.get(b.name, []))
                  if bones[col[c]].group not in FOLD_CHAIN_GROUPS]
        out.append(t)
    return out


def _prune(w, bones=None, guide=None, co=None):
    """Keep at most MAX_INFLUENCE bones per vertex, continuously and without crushing the
    kept ones. With t the 5th-largest weight (at least MIN_WEIGHT), every bone folds away
    the share 1 - smoothstep(t, PRUNE_FOLD * t, w) of its weight w: all of it at or below t
    (so at most four remain), none from PRUNE_FOLD * t up. The result is a continuous
    function of the weights, whichever bones swap rank; the round-4 prune subtracted t from
    every bone, which turned a smooth field into a cliff where five or six bones overlap
    on a dense mesh. The folded weight goes to the bones a helper blends between
    (_fold_targets: ひじ補助 to 腕捩 / ひじ by its share, a twist bone to its limb, the
    shrug to 肩) as far as those keep weight, the rest to the kept bones in proportion.
    `bones`: the columns' Bone objects (None: proportional only)."""
    k = MAX_INFLUENCE
    n, B = w.shape
    w = w / np.maximum(w.sum(1, keepdims=True), 1e-12)
    g = w if guide is None else guide / np.maximum(guide.sum(1, keepdims=True), 1e-12)
    if B > k:
        t = -np.partition(-g, k, axis=1)[:, k]
    else:
        t = np.zeros(n)
    t = np.maximum(t, MIN_WEIGHT)[:, None]
    fold = w * (1.0 - _smoothstep(0.0, 1.0, (g - t) / ((PRUNE_FOLD - 1.0) * t)))
    out = w - fold
    left = fold.sum(1)
    if bones is not None:
        for j, tg in enumerate(_fold_targets(bones)):
            if not tg:
                continue
            amt = fold[:, j].copy()
            split = sum(f for _, f in tg if f < 1.0) > 0.0      # a helper's fixed split
            for c, frac in tg:
                if c == j:
                    continue
                g = _smoothstep(0.0, FOLD_TARGET_MIN, out[:, c])
                give = (fold[:, j] * frac if split and frac < 1.0 else amt) * g
                give = np.minimum(give, amt)
                out[:, c] += give
                left -= give
                amt -= give
    out += out / np.maximum(out.sum(1, keepdims=True), 1e-12) * np.maximum(left, 0.0)[:, None]
    empty = np.nonzero(out.sum(1) <= 1e-12)[0]      # only with 5+ exactly tied bones
    out[empty, np.argmax(w[empty], axis=1)] = 1.0
    kk = min(k, B)
    idx = np.argsort(-out, axis=1, kind='stable')[:, :kk]
    ww = np.take_along_axis(out, idx, axis=1)
    ww = ww / np.maximum(ww.sum(1, keepdims=True), 1e-12)
    if co is not None and bones is not None and _MOTION:
        ww = _motion_refit(w, idx, ww, co, bones, fold.sum(1) > 1e-9)
    return idx, ww


_MOTION = {}          # deform bone name -> (K, 3, 4) skinning matrices in the sample poses (build_rig)
MOTION_D = 0.01       # m: motion error that weighs as much as moving a kept weight by its own size
MOTION_TOP = 8        # strongest unpruned bones whose motion the refit matches


def _motion_refit(w, idx, ww, co, bones, folded):
    """Re-weight the kept bones of each pruned vertex so it moves as the unpruned blend
    did in the sample poses (_motion_samples): least squares over the poses, sum 1,
    regularized toward the folded weights, the more strongly the smaller a kept weight
    is (a bone entering the set enters at zero: no jump). Folding a few % of torso weight
    on a raised upper arm into the arm moves the skin centimetres; this puts it back.
    Only vertices that lost weight in the prune are touched."""
    rows = np.nonzero(folded)[0]
    if not len(rows):
        return ww
    shape = next(iter(_MOTION.values())).shape
    S = np.zeros((len(bones),) + shape)
    have = np.zeros(len(bones), dtype=bool)
    for j, b in enumerate(bones):
        if b.name in _MOTION:
            S[j] = _MOTION[b.name]
            have[j] = True
    K = shape[0]
    m = min(MOTION_TOP, w.shape[1])
    out = ww.copy()
    for s0 in range(0, len(rows), 8192):
        r = rows[s0:s0 + 8192]
        p = np.c_[co[r], np.ones(len(r))]
        src = np.argsort(-w[r], axis=1, kind='stable')[:, :m]
        sw = np.take_along_axis(w[r], src, 1)
        sw = sw / np.maximum(sw.sum(1, keepdims=True), 1e-12)
        ok = have[src].all(1) & have[idx[r]].all(1)
        y = np.einsum('nj,njkab,nb->nka', sw, S[src], p).reshape(len(r), -1)
        A = np.einsum('njkab,nb->njka', S[idx[r]], p)
        A = A.reshape(len(r), A.shape[1], -1)
        o = ww[r]
        lam = K * MOTION_D ** 2 * (0.05 / (o + 0.002))
        H = np.einsum('nia,nja->nij', A, A) + lam[:, :, None] * np.eye(A.shape[1])[None]
        g = np.einsum('nia,na->ni', A, y) + lam * o
        Hi = np.linalg.inv(H)
        hg, h1 = np.einsum('nij,nj->ni', Hi, g), Hi.sum(2)
        mu = (hg.sum(1) - 1.0) / np.maximum(h1.sum(1), 1e-12)
        u = np.maximum(hg - mu[:, None] * h1, 0.0)
        u = u / np.maximum(u.sum(1, keepdims=True), 1e-12)
        out[r[ok]] = u[ok]
    return out


def _prune_subtract(w):
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


# bodice pieces hand over to the skirt weights between these heights relative to hip_z.
# Above the hip the skirt field is itself the 上半身/下半身 blend, so a long hand-over
# costs nothing and lets hanging ribbons leave the waist without a kink.
SKIRT_BAND = (0.06, -0.02)
ANKLE_BLEND = 0.03    # foot / shin blend half-width around the ankle joint height
DRAPE_NEAR, DRAPE_FAR = 0.04, 0.13   # sleeve drape weight fades in between these from the arm axis


def _split_joint_aux(w, co, bones, band):
    """Spread each elbow / knee bend over the upper limb (no turn), its helper bones (a share
    of the bend each) and the lower limb with everything hanging from it (the full bend).
    Along the lower bone the limb's total weight is re-split by a smooth partition of unity
    with knots at -before (upper), each helper's 'aux_at' and +after (lower); inside the
    upper and lower groups the bones keep their envelope proportions."""
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
    joints = {}
    for j, b in enumerate(bones):
        if 'joint_aux' in b.meta and not b.meta.get('hat'):
            joints.setdefault(b.meta['joint_aux'][1], []).append(j)
    for lower, aux in joints.items():
        if lower not in col:
            continue
        aux.sort(key=lambda j: bones[j].meta.get('aux_share', 0.0))
        b = bones[aux[0]]
        upper = b.meta['joint_aux'][0]
        stem = b.name.split('.')[0]
        before, after = JOINT_BAND_BY_AUX.get(stem, band)
        up = [col[n] for n in upper if n in col]
        # the limb and what it carries rigidly; secondary chains (sleeve drapes) keep their own weights
        lo = [col[n] for n in below(lower) if n in col and bones[col[n]].group not in ('Sleeve', 'Hair', 'Skirt')]
        if not up:
            continue
        lb = bones[col[lower]]
        d = np.array((lb.tail - lb.head).normalized())
        t = (co - np.array(lb.head)) @ d
        lat_d = np.linalg.norm((co - np.array(lb.head)) - t[:, None] * d, axis=1)
        scale = JOINT_FRONT_BACK.get(stem)
        hinge = JOINT_HINGE.get(stem)
        if hinge is not None:
            # hinge partition (JOINT_HINGE): the share follows an angle around the joint,
            # atan2(t, d), with d long in front (the kneecap's arc spreads its stretch),
            # shorter behind (the hollow folds instead of collapsing a long band), varying
            # smoothly round the limb so neighbouring columns don't shear
            (d_f, d_s, d_b), deg, hfwd = hinge
            if len(deg) != len(aux) + 2:
                raise ValueError(f'JOINT_HINGE[{stem!r}]: {len(deg)} knots for {len(aux)} helpers')
            lat = (co - np.array(lb.head)) - t[:, None] * d
            c = (lat @ np.array(hfwd, dtype=float)) / np.maximum(np.linalg.norm(lat, axis=1), 1e-6)
            dist = d_s + 0.5 * (d_f - d_b) * c + (0.5 * (d_f + d_b) - d_s) * c * c
            t = np.degrees(np.arctan2(t, dist))
            knots = list(deg)
        elif scale is not None:
            # the band is wider over the front of the joint (the kneecap wraps round) and
            # narrower behind it (the hollow creases instead of pinching): t is divided by
            # the local band scale, lerped by how far round to the front the vertex is
            lat = (co - np.array(lb.head)) - t[:, None] * d
            fwd = np.array(scale[2], dtype=float)
            front = (lat @ fwd) / np.maximum(np.linalg.norm(lat, axis=1), 1e-6)
            k = scale[1] + (scale[0] - scale[1]) * _smoothstep(-1.0, 1.0, front)
            t = t / k
        if hinge is None:
            knots = [-before] + [bones[j].meta.get('aux_at', 0.0) for j in aux] + [after]
        steps = [_smoothstep(k0, k1, t) for k0, k1 in zip(knots, knots[1:])]
        f = [1.0 - steps[0]] + [s0 - s1 for s0, s1 in zip(steps, steps[1:])] + [steps[-1]]
        if hinge is not None and JOINT_HINGE_CAP:
            # a long band behind the joint never reaches the ankle or the hip: beyond these
            # distances along the limb the skin is all upper / all lower limb
            along = (co - np.array(lb.head)) @ d
            g = _smoothstep(JOINT_HINGE_CAP[0], JOINT_HINGE_CAP[1], np.abs(along))
            hard = [np.where(along < 0, 1.0, 0.0)] + [np.zeros(len(co))] * (len(f) - 2) + [np.where(along < 0, 0.0, 1.0)]
            f = [fi * (1.0 - g) + hi * g for fi, hi in zip(f, hard)]
        cols = up + lo + aux
        old = w[:, cols].copy()
        su, sl = w[:, up].sum(1), w[:, lo].sum(1)
        tot = su + sl + w[:, aux].sum(1)
        live = tot > 1e-9
        pu = np.where(live[:, None], w[:, up] / np.maximum(su, 1e-12)[:, None], 0.0)
        pu[su <= 1e-12] = np.eye(len(up))[-1]          # empty group: its main bone
        pl = np.where(live[:, None], w[:, lo] / np.maximum(sl, 1e-12)[:, None], 0.0)
        pl[sl <= 1e-12] = np.eye(len(lo))[0]
        w[:, up] = pu * (tot * f[0])[:, None]
        w[:, lo] = pl * (tot * f[-1])[:, None]
        for j, fj in zip(aux, f[1:-1]):
            w[:, j] = tot * fj
        reach = JOINT_REACH_BY_AUX.get(stem)
        if reach is not None:
            # only skin around the limb: torso skin with a little of the upper bone's
            # weight (the ribs under the armpit) must not be handed to the arm
            g = (1.0 - _smoothstep(reach[0], reach[1], lat_d))[:, None]
            w[:, cols] = old * (1.0 - g) + w[:, cols] * g


# Round 7: hip helpers 足補助 turn HIP_AUX of their thigh about the hip joint. Wherever the
# skin blends the pelvis (下半身) and a thigh, the blend is re-made through the helper
# (_hat_remap): with s the thigh's share of the pair and a = HIP_AUX, weights
# (1 - s/a, s/a, 0) below s = a and (0, (1-s)/(1-a), (s-a)/(1-a)) above, so the skin moves
# the same to first order but the skin at s = a turns rigidly with the helper instead of
# averaging a straight and a bent thigh, which collapsed the hip (volume 0.48-0.75 in
# cross_legged, lie_back_elbows, high_kick; now 0.9+). The crotch midline, shared by both
# thighs, splits its pelvis weight between the sides by their thigh weights first.
# (0.4 eased cross_legged's stretch between the buttocks, x2.38 -> x2.25, but pushed the
# inner thighs 6.5 cm into each other there.) None = off.
HIP_AUX = 0.5


def _hat_remap(w, bones):
    col = {b.name: i for i, b in enumerate(bones)}
    hats = [(j, b) for j, b in enumerate(bones) if b.meta.get('hat') and b.meta['joint_aux'][1] in col]
    groups = {}
    for j, b in hats:
        up = next((u for u in reversed(list(b.meta['joint_aux'][0])) if u in col), None)
        if up is not None:
            groups.setdefault(col[up], []).append((j, col[b.meta['joint_aux'][1]], b.meta.get('aux_share', 0.5)))
    for up, items in groups.items():
        lows = np.stack([w[:, lo] for _, lo, _ in items], 1)
        tot_lo = lows.sum(1)
        wu = w[:, up].copy()
        new_up = np.where(tot_lo > 1e-12, 0.0, wu)
        for k, (h, lo, a) in enumerate(items):
            pu = np.where(tot_lo > 1e-12, wu * lows[:, k] / np.maximum(tot_lo, 1e-12), 0.0)
            T = pu + lows[:, k]
            s = np.where(T > 1e-12, lows[:, k] / np.maximum(T, 1e-12), 0.0)
            # hat functions with the helper's knot at its share a
            w_up = T * np.clip(1.0 - s / a, 0.0, 1.0)
            w_lo = T * np.clip((s - a) / (1.0 - a), 0.0, 1.0)
            new_up += w_up
            w[:, h] += T - w_up - w_lo
            w[:, lo] = w_lo
        w[:, up] = new_up


def _split_along(w, co, bones, key, span):
    """Give each bone with meta `key` (naming its source bone) the share of the source's
    weight that grows smoothly from 0 to 1 along the source, between the fractions `span`.
    Twist bones (twist_of, TWIST_RAMP): the twist spreads down the limb segment. The
    shrug (shrug_of, SHRUG_SPAN): the inner end of 肩 (neck, collarbone) stays, the outer
    end (shoulder top, the cap round the joint) rises with the shrug."""
    col = {b.name: i for i, b in enumerate(bones)}
    for j, b in enumerate(bones):
        p = col.get(b.meta.get(key))
        if p is None:
            continue
        a, c = np.array(bones[p].head), np.array(bones[p].tail)
        t = ((co - a) @ (c - a)) / max(float((c - a) @ (c - a)), 1e-12)
        f = _smoothstep(span[0], span[1], t)
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


def _drape_along_chain(w, co, bones, drape):
    """Re-split the drape chain's share between its segments by the normalized position
    along the chain (hat functions centred on the segments, like the skirt), instead of
    their envelopes: moving a ring of the sleeve shifts its weights smoothly."""
    segs = sorted(drape, key=lambda j: bones[j].meta.get('seg', 0))
    n = len(segs)
    if n < 2:
        return
    u = _polyline_u(co, np.array([bones[j].head for j in segs]), np.array([bones[j].tail for j in segs]))
    uc = np.clip(u, 0.5, n - 0.5)
    tot = w[:, segs].sum(1)
    for i, j in enumerate(segs):
        w[:, j] = tot * np.maximum(0.0, 1.0 - np.abs(uc - (i + 0.5)))


def _drape_only_away_from_arm(w, co, bones):
    """Sleeve drape chains (袖) only move cloth hanging away from the arm: their weight
    fades in between DRAPE_NEAR and DRAPE_FAR from the arm bones, so the cuff and the
    band around the arm follow the arm and a swinging drape doesn't tear them."""
    for tag in 'LR':
        names = {b.name for b in bones}
        arm = [b for b in bones if b.name in (deform_arm(names, tag), f'ひじ.{tag}')]
        drape = [j for j, b in enumerate(bones) if b.group == 'Sleeve' and b.name.endswith('.' + tag)]
        if not arm or not drape:
            continue
        d = np.min([_seg_dist(co, np.array(b.head), np.array(b.tail)) for b in arm], axis=0)
        g = _smoothstep(DRAPE_NEAR, DRAPE_FAR, d)
        moved = w[:, drape].sum(1) * (1.0 - g)
        w[:, drape] *= g[:, None]
        _drape_along_chain(w, co, bones, drape)
        others = [j for j, b in enumerate(bones) if j not in drape and b.name in
                  {f'{n}.{tag}' for n in ('腕', '腕D', '腕捩', 'ひじ', '手捩', '手首')}]
        tot = w[:, others].sum(1)
        if others:
            env = _envelope(co, [bones[j] for j in others])
            w[:, others] += np.where(tot[:, None] > 1e-9, w[:, others] / np.maximum(tot, 1e-9)[:, None],
                                     env) * moved[:, None]


def _hair_head_fade(w, co, bones):
    """Long back hair turns with the head only near the scalp: 頭 takes exactly
    smoothstep(HAIR_HEAD_FADE) of the height, the rest is shared by the hair chains in
    their own proportions; the chains take only HAIR_FOLLOW of a head turn. So the
    crown follows the head fully, hair at and below the shoulders (where a turned head
    would sweep it into them) follows the neck, and the turn is spread over the nape.
    Applied after smoothing, as a pure function of height: vertices a hair's thickness
    apart get the same share, so the twist through the band doesn't tear thin locks."""
    col = {b.name: i for i, b in enumerate(bones)}
    h = col.get('頭')
    if h is None:
        return w
    z0, z1 = HAIR_HEAD_FADE
    f = _smoothstep(z0, z1, co[:, 2])
    others = [j for j in range(len(bones)) if j != h]
    rest = w[:, others].sum(1)
    w = w.copy()
    w[:, others] *= np.where(rest > 1e-12, (1.0 - f) / np.maximum(rest, 1e-12), 0.0)[:, None]
    w[:, h] = np.where(rest > 1e-12, f, 1.0)
    return w


# round 7: wider and smoother (round 6: 4.5 cm over a 7 cm half width, 22 cm deep): the
# pelvis / thigh change spreads over the buttocks and the groin, x2.0-2.1 -> 1.7-1.8 in
# high_kick, the lunges and kneeling (with the hip helpers)
CROTCH_SMOOTH = 0.06           # weight smoothing radius (m) at the crotch
CROTCH_PARTS = ('body', '_proxy')   # skin only: garments there follow the skirt chains
CROTCH_ZONE = (0.12, 0.25, 0.06)   # half width, depth below the hip joints, vertical fade


def _crotch_mask(co, bones):
    """0..1: vertices at the crotch, between the thighs below the hip joints."""
    col = {b.name: i for i, b in enumerate(bones)}
    if '足.L' not in col or '足.R' not in col:
        return None
    hip_z = bones[col['足.L']].head.z
    hw, depth, fade = CROTCH_ZONE
    return (1.0 - _smoothstep(hw * 0.6, hw, np.abs(co[:, 0]))) * \
        _smoothstep(hip_z - depth, hip_z - depth + fade, co[:, 2]) * \
        (1.0 - _smoothstep(hip_z - fade, hip_z, co[:, 2]))


ARMPIT_SMOOTH = 0.05          # weight smoothing radius (m) in the armpit
# armpit centre relative to the shoulder joint (inward, back, down) and the radii between
# which the wide smoothing fades out
ARMPIT_ZONE = ((0.04, 0.0, 0.04), 0.06, 0.11)


ARMPIT_TOP = (0.0, 0.02)   # m above the shoulder joint over which the armpit zone fades out (round 7)


def _armpit_mask(co, bones):
    """0..1: vertices in either armpit, below and inside the shoulder joint."""
    col = {b.name: i for i, b in enumerate(bones)}
    off, r0, r1 = ARMPIT_ZONE
    m = None
    for t, s in (('L', 1.0), ('R', -1.0)):
        arm = col.get(deform_arm(col, t))
        if arm is None:
            continue
        h = bones[arm].head
        c = np.array((h.x - s * off[0], h.y + off[1], h.z - off[2]))
        f = 1.0 - _smoothstep(r0, r1, np.linalg.norm(co - c, axis=1))
        if ARMPIT_TOP:
            # round 7: only below the shoulder: the sphere also reached the top of the
            # shoulder beside the neck, where it smeared the arm over the trapezius
            f = f * (1.0 - _smoothstep(h.z + ARMPIT_TOP[0], h.z + ARMPIT_TOP[1], co[:, 2]))
        m = f if m is None else np.maximum(m, f)
    return m


# the arm's bones may hold at most smoothstep(J.x - ARM_CAP[0], J.x - ARM_CAP[1], |x|) of a
# skin vertex (J = the shoulder joint): chest and back skin medial of the shoulder stays on
# the torso instead of following a raised arm by a third (the chest-side stretch in arms_up,
# which garments sampling the skin copied)
ARM_CAP = None   # off: tried (0.05, 0.005) / (0.07, 0): arms_up x2.26 / x2.04 on the chest
ARM_CAP_BONES = ('腕D', '腕', '腕捩', 'ひじ補助', 'ひじ', '手捩', '手首')


def _arm_cap(w, co, bones):
    col = {b.name: i for i, b in enumerate(bones)}
    w = w.copy()
    for t, s in (('L', 1.0), ('R', -1.0)):
        arm = col.get(deform_arm(col, t))
        if arm is None:
            continue
        jx = abs(bones[arm].head.x)
        cap = _smoothstep(jx - ARM_CAP[0], jx - ARM_CAP[1], co[:, 0] * s)
        cols = [col[f'{n}.{t}'] for n in ARM_CAP_BONES if f'{n}.{t}' in col]
        a = w[:, cols].sum(1)
        excess = np.maximum(a - cap, 0.0)
        if not excess.any():
            continue
        w[:, cols] *= np.where(a > 1e-12, 1.0 - excess / np.maximum(a, 1e-12), 1.0)[:, None]
        tgt = col.get(f'肩補助.{t}', col.get('上半身2'))
        if tgt is None:
            continue
        w[:, tgt] += excess
    return w


# Sleeves are weighted by construction with at most 4 bones (_sleeve_weights): two
# neighbouring arm bones along the arm (SLEEVE_ARM_KNOTS) and two neighbouring drape
# segments, so no prune ever cuts a 5-6 bone field into a stretch ridge.
SLEEVE_BUILD = True
# (bone stem, position along shoulder -> elbow -> wrist: ('s', m) from the shoulder,
# ('e', m) from the elbow, ('f', frac) of the forearm, ('w', m) past the wrist)
SLEEVE_ARM_KNOTS = (('腕D', ('s', 0.0)), ('腕捩', ('e', -0.06)), ('ひじ補助', ('e', 0.0)),
                    ('ひじ', ('e', 0.06)), ('手捩', ('f', 0.85)), ('手首', ('w', 0.03)))
SLEEVE_SMOOTH = 0.0          # m: surface smoothing of the constructed sleeve weights (already smooth)
SLEEVE_ATTACH = (0.35, 0.7)   # sleeve parameter s: the drape fades in after the band, out before the cuff
_SLEEVE_S = None               # per-vertex sleeve parameter of the object being skinned (_weights)
_SLEEVE_EDGES, _SLEEVE_N = None, 0   # ... its edges and vertex count
SLEEVE_PARAM_SMOOTH = 0.065    # m: surface smoothing of the sleeve's arm / drape parameters
SLEEVE_ELBOW_SPREAD = (0.06, 0.65, 0.03, 0.25)   # (band b, gain c, arm radius r0, window): see _sleeve_weights


def _sleeve_param(obj, co):
    """The sleeve's own 0 (band) .. 1 (wrist) parameter: the part's point attribute named by
    obj['levi_sleeve_param'] (sleeves.sleeve_params), else None."""
    return _point_param(obj, co, 'levi_sleeve_param')


def _point_param(obj, co, prop):
    """The float point attribute named by obj[prop], one value per vertex, else None."""
    name = obj.get(prop)
    attr = obj.data.attributes.get(name) if name else None
    if attr is None or attr.domain != 'POINT' or len(attr.data) != len(co):
        return None
    v = np.empty(len(co))
    attr.data.foreach_get('value', v)
    return v


def _sleeve_weights(co, bones, sparam=None, edges=None):
    """(V, B) sleeve weights with at most 4 bones per vertex by construction. Along the
    arm (arc length a of the nearest point on shoulder -> elbow -> wrist) a hat blend of
    two neighbouring SLEEVE_ARM_KNOTS bones; the drape share g (fading in between
    DRAPE_NEAR and DRAPE_FAR from the arm axis, and only between the attachments
    SLEEVE_ATTACH along the sleeve parameter s) goes to a hat blend of two neighbouring
    drape segments by the position u along the drape chain. With `edges`, the parameters
    a, g and u (not the weights) are smoothed along the surface (SLEEVE_PARAM_SMOOTH), so
    the result stays smooth and still has at most 4 bones. Without a sleeve parameter s is
    the arm position normalized over the drape's span."""
    col = {b.name: i for i, b in enumerate(bones)}
    W = np.zeros((len(co), len(bones)))
    done = np.zeros(len(co), dtype=bool)
    for t, sd in (('L', 1.0), ('R', -1.0)):
        side = co[:, 0] * sd > 0.0
        arm = col.get(deform_arm(col, t))
        el, wr = col.get(f'ひじ.{t}'), col.get(f'手首.{t}')
        if arm is None or el is None or wr is None or not side.any():
            continue
        S, E, Wp = (np.array(bones[arm].head), np.array(bones[el].head), np.array(bones[wr].head))
        l1, l2 = float(np.linalg.norm(E - S)), float(np.linalg.norm(Wp - E))
        u = _polyline_u(co, np.array([S, E]), np.array([E, Wp]))
        a = np.where(u < 1.0, u * l1, l1 + (u - 1.0) * l2)
        fd = (Wp - E) / l2
        past = (co - Wp) @ fd
        a = np.where((u >= 1.999) & (past > 0), l1 + l2 + past, a)      # past the wrist: along the forearm
        drape = sorted((j for j, b in enumerate(bones) if b.group == 'Sleeve' and b.name.endswith('.' + t)),
                       key=lambda j: bones[j].meta.get('seg', 0))
        g = np.zeros(len(co))
        uc = np.zeros(len(co))
        if drape:
            d = np.min([_seg_dist(co, np.array(bones[c].head), np.array(bones[c].tail)) for c in (arm, el)], axis=0)
            sel = side & (d > DRAPE_NEAR)
            if sparam is not None:
                sp = sparam
            elif sel.sum() >= 16:
                lo, hi = float(a[sel].min()), float(a[sel].max())
                sp = np.clip((a - lo) / max(hi - lo, 1e-6), 0.0, 1.0)
            else:   # a few points (an ornament's host): no span to normalize over; mid-sleeve
                sp = np.full(len(co), 0.5)
            g = _smoothstep(DRAPE_NEAR, DRAPE_FAR, d) * _smoothstep(0.0, SLEEVE_ATTACH[0], sp) * \
                (1.0 - _smoothstep(SLEEVE_ATTACH[1], 1.0, sp))
            uc = _polyline_u(co, np.array([bones[j].head for j in drape]), np.array([bones[j].tail for j in drape]))
        if SLEEVE_ELBOW_SPREAD:
            # cloth standing off the arm bends over a wider band at the elbow: its distance
            # from the elbow along the arm is scaled down by b / (b + c (d - r0)) near the
            # elbow, so a bag ~7 cm out turns across ~2x the band and its inner side folds
            # instead of collapsing (round 7: compress 0.04 and flipped faces at ひじ補助)
            b_, c_, r0, wwin = SLEEVE_ELBOW_SPREAD
            dax = np.minimum(_seg_dist(co, S, E), _seg_dist(co, E, Wp))
            f = b_ / (b_ + c_ * np.maximum(dax - r0, 0.0))
            da = a - l1
            m = f + (1.0 - f) * _smoothstep(0.5 * wwin, wwin, np.abs(da))
            a = l1 + da * m
        if edges is not None and len(edges) and SLEEVE_PARAM_SMOOTH > 0:
            sm = _smooth(np.stack([a, g, uc], 1), co, edges, SLEEVE_PARAM_SMOOTH)
            a, g, uc = (np.where(side, sm[:, i], x) for i, x in enumerate((a, g, uc)))
        knots, cols = [], []
        for stem, (kind, v) in SLEEVE_ARM_KNOTS:
            n = deform_arm(col, t) if stem == '腕D' else f'{stem}.{t}'
            if n in col:
                knots.append({'s': v, 'e': l1 + v, 'f': l1 + v * l2, 'w': l1 + l2 + v}[kind])
                cols.append(col[n])
        if len(knots) < 2:
            continue
        knots = np.maximum.accumulate(np.array(knots))
        ac = np.clip(a, knots[0], knots[-1])
        armw = np.zeros((len(co), len(bones)))
        for i in range(len(knots) - 1):
            k0, k1 = knots[i], knots[i + 1]
            inside = (ac >= k0) & ((ac <= k1) if i == len(knots) - 2 else (ac < k1))
            f = np.clip((ac - k0) / max(k1 - k0, 1e-9), 0.0, 1.0)
            armw[inside, cols[i]] += 1.0 - f[inside]
            armw[inside, cols[i + 1]] += f[inside]
        dw = np.zeros((len(co), len(bones)))
        if drape:
            uq = np.clip(uc, 0.5, len(drape) - 0.5)
            for i, j in enumerate(drape):
                dw[:, j] = np.maximum(0.0, 1.0 - np.abs(uq - (i + 0.5)))
        W[side] = (armw * (1.0 - g)[:, None] + dw * g[:, None])[side]
        # the forearm's share rides its copies that flatten when crowded (SLEEVE_CROWD); all of
        # it (a partial hand-over would put 5-6 bones on a vertex)
        for stem, (jp, _, _) in SLEEVE_BODY.items():
            src_c, body = col.get(f'{stem}.{t}'), col.get(f'{jp}.{t}')
            if src_c is not None and body is not None:
                W[side, body] += W[side, src_c]
                W[side, src_c] = 0.0
        done |= side
    if not done.all():
        plain = [j for j, b in enumerate(bones) if not {'twist_of', 'joint_aux', 'shrug_of', 'stage'} & set(b.meta)]
        W[np.ix_(~done, plain)] = _envelope(co[~done], [bones[j] for j in plain])
    return W


# Thick cloth shells (the skirt's outer face, inner face and rounded hem): vertices at the
# same place on the cloth (angle around the body, height) get the same weights, so the two
# faces cannot separate in a pose: weights are averaged over SHELL_CELL cells.
SHELL_PARTS = ('skirt',)
SHELL_CELL = (1.5, 0.004)    # deg around the body, m of height


def _shell_share(w, co, bones):
    """Weights as a smooth function of (angle around the body, height): splatted onto a
    SHELL_CELL grid with bilinear weights and read back the same way, so vertices of both
    faces at one spot get equal weights and the field stays continuous."""
    cy = next((b.meta['cy'] for b in bones if b.group == 'Skirt' and 'cy' in b.meta), None)
    if cy is None:
        return w
    ncell = int(round(360.0 / SHELL_CELL[0]))
    th = (np.degrees(np.arctan2(co[:, 0], co[:, 1] - cy)) % 360.0) / (360.0 / ncell)
    zz = co[:, 2] / SHELL_CELL[1]
    i0, j0 = np.floor(th).astype(np.int64), np.floor(zz).astype(np.int64)
    fx, fz = th - i0, zz - j0
    corners = [(0, 0, (1 - fx) * (1 - fz)), (1, 0, fx * (1 - fz)), (0, 1, (1 - fx) * fz), (1, 1, fx * fz)]
    # the angle wraps (cells at 359.x and 0.x deg are neighbours)
    keys = np.concatenate([np.stack([(i0 + di) % ncell, j0 + dj], 1) for di, dj, _ in corners])
    uniq, inv = np.unique(keys, axis=0, return_inverse=True)
    inv = inv.reshape(4, -1)
    acc = np.zeros((len(uniq), w.shape[1]))
    den = np.zeros(len(uniq))
    for (di, dj, f), ix in zip(corners, inv):
        np.add.at(acc, ix, w * f[:, None])
        np.add.at(den, ix, f)
    node = acc / np.maximum(den, 1e-12)[:, None]
    out = sum(node[ix] * f[:, None] for (di, dj, f), ix in zip(corners, inv))
    return out


def _base_weights(part, co, bones):
    """(V, B) weights before side masking / smoothing / pruning."""
    plain = [j for j, b in enumerate(bones) if not {'twist_of', 'joint_aux', 'shrug_of', 'stage'} & set(b.meta)]
    sub = [bones[j] for j in plain]
    # the bodice samples the shrug and the stages from the skin too (they are not 'plain')
    stg = [j for j, b in enumerate(bones) if {'stage', 'shrug_of'} & set(b.meta)] if part == 'bodice' else []
    ws = np.zeros((len(co), len(stg)))
    if part in ('skirt', 'petticoat'):
        w0 = _skirt_weights(co, sub)
    elif part == 'hair_back' and HAIR_RING:
        w0 = _skirt_weights(co, sub, group='Hair', body_names=('頭',), max_gap=RING_MAX_GAP)
    else:
        main = [i for i, b in enumerate(sub) if b.group != 'Skirt']
        w0 = np.zeros((len(co), len(sub)))
        env = _envelope(co, [sub[i] for i in main])
        if part == 'bodice':
            # the skin's own shrug and staged shoulder bones too, so the bodice rides the
            # chest skin under it exactly
            names_s = [sub[i].name for i in main] + [bones[j].name for j in stg]
            smp = _skin_sample(co, names_s, np.concatenate([env, np.zeros((len(co), len(stg)))], 1))
            w0[:, main], ws = smp[:, :len(main)], smp[:, len(main):]
            # a fitted strapless bodice takes at most BODICE_ARM_CAP of the arm from the skin
            # (its rim at the armpit rides along; the neckline and chest stay on the torso).
            # The stages are not capped: capping them too left the chest skin, which turns
            # with them, pushing through the bodice (and the cap split the rim's weights)
            arm = [i for i in main if sub[i].name.split('.')[0] in ('腕D', '腕')]
            chest = next((i for i in main if sub[i].name == '上半身2'), None)
            if arm and chest is not None:
                a = w0[:, arm].sum(1)
                k = np.minimum(1.0, BODICE_ARM_CAP / np.maximum(a, 1e-9))
                w0[:, chest] += a * (1.0 - k)
                w0[:, arm] *= k[:, None]
        else:
            w0[:, main] = env
        if len(main) < len(sub):        # bodice ribbons hanging over the skirt ride the skirt
            t = _smoothstep(L['hip_z'] + SKIRT_BAND[0], L['hip_z'] + SKIRT_BAND[1], co[:, 2])[:, None]
            w0 = (1.0 - t) * w0 + t * _skirt_weights(co, sub)
            ws = ws * (1.0 - t)
    w = np.zeros((len(co), len(bones)))
    w[:, plain] = w0
    if len(stg):
        w[:, stg] = ws
    if part in NECK_PARTS:
        _neck_partition(w, co, bones)
    if part == 'sleeves' and SLEEVE_BUILD:
        ok = lambda x: x if x is not None and len(co) > 1 and _SLEEVE_N == len(co) else None  # noqa: E731
        return _sleeve_weights(co, bones, ok(_SLEEVE_S), ok(_SLEEVE_EDGES))
    if part == 'sleeves':
        _drape_only_away_from_arm(w, co, bones)
    _split_ankle(w, co, bones)
    _split_along(w, co, bones, 'twist_of', TWIST_RAMP)
    if part != 'bodice':        # the bodice took the skin's shrug weight as it is
        _split_along(w, co, bones, 'shrug_of', SHRUG_SPAN)
    _split_joint_aux(w, co, bones, JOINT_BAND.get(part, (JOINT_AUX_BLEND, JOINT_AUX_BLEND)))
    if part == 'body' and SHOULDER_STAGES and any('stage' in b.meta for b in bones):
        if _SOCKET_S is not None and len(_SOCKET_S) == len(co):
            _shoulder_stages(w, bones, _SOCKET_S)
        else:
            print('rig: WARNING body has no socket parameter (body.SOCKET_PARAM_ATTR): '
                  'the staged shoulder helpers get no weight')
    return w


# Round 7: the neck's skin is split between 上半身2, 首 and 頭 by height along 首 (0 at its
# head, 1 at its tail; knots: 上半身2 -> 首, then 首 -> 頭), so a turned or tipped head is
# shared over the whole neck in two steps. The envelopes left the neck mostly 上半身2 up to
# the choker with 頭 reaching down to the nape (首 never above 35%): looking over the
# shoulder stretched the nape x2.0 and the choker, riding 首 alone over that skin, x2.5.
NECK_PARTS = ('body', 'head', '_proxy')
NECK_KNOTS = ((-0.35, 0.45), (0.5, 1.15))   # 頭 by the chin (t 1.16)
NECK_REACH = (0.045, 0.075)    # m from 首's axis: the split applies fully within, not beyond
NECK_SPAN = ((-1.2, -0.8), (1.6, 2.0))   # ... and fades out below / above 首 (its fractions)


def _neck_frac(co, bones):
    """(t, rho): the fraction along 首 and the distance from its axis of each point."""
    col = {b.name: i for i, b in enumerate(bones)}
    nb = bones[col['首']]
    a, c = np.array(nb.head), np.array(nb.tail)
    d = c - a
    t = ((co - a) @ d) / max(float(d @ d), 1e-12)
    rho = np.linalg.norm(co - (a + t[:, None] * d), axis=1)
    return t, rho


def _neck_split(t):
    """(上半身2, 首, 頭) shares at fraction t along 首 (NECK_KNOTS)."""
    u1 = _smoothstep(NECK_KNOTS[0][0], NECK_KNOTS[0][1], t)
    u2 = _smoothstep(NECK_KNOTS[1][0], NECK_KNOTS[1][1], t)
    return 1.0 - u1, u1 - u2, u2


def _neck_partition(w, co, bones):
    """Re-split the spine weight (上半身2 + 首 + 頭) of the skin around the neck by height
    (_neck_split); other bones (肩, the shoulders) keep theirs."""
    col = {b.name: i for i, b in enumerate(bones)}
    if not all(n in col for n in ('上半身2', '首', '頭')) or not len(co):
        return
    idx = [col['上半身2'], col['首'], col['頭']]
    t, rho = _neck_frac(co, bones)
    m = (1.0 - _smoothstep(NECK_REACH[0], NECK_REACH[1], rho)) * \
        _smoothstep(NECK_SPAN[0][0], NECK_SPAN[0][1], t) * (1.0 - _smoothstep(NECK_SPAN[1][0], NECK_SPAN[1][1], t))
    s = w[:, idx].sum(1)
    for i, f in zip(idx, _neck_split(t)):
        w[:, i] = (1.0 - m) * w[:, i] + m * s * f


def _shoulder_stages(w, bones, sparam):
    """Re-split each side's shrug + arm weight (肩補助, 肩補助2, 肩補助3, 腕D) by the body's
    socket parameter: a partition of unity with knots SHOULDER_STAGES[1], shrug first."""
    if not SHOULDER_STAGES:
        return
    col = {b.name: i for i, b in enumerate(bones)}
    knots = SHOULDER_STAGES[1]
    if len(knots) != len(SHOULDER_STAGES[0]) + 2:
        raise ValueError(f'SHOULDER_STAGES: {len(knots)} knots for {len(SHOULDER_STAGES[0])} stages')
    steps = [_smoothstep(k0, k1, sparam) for k0, k1 in zip(knots, knots[1:])]
    f = [1.0 - steps[0]] + [s0 - s1 for s0, s1 in zip(steps, steps[1:])] + [steps[-1]]
    for t in 'LR':
        names = [f'肩補助.{t}'] + [f'肩補助{i + 2}.{t}' for i in range(len(SHOULDER_STAGES[0]))] + [f'腕D.{t}']
        if not all(n in col for n in names):
            continue
        cols = [col[n] for n in names]
        g = w[:, cols].sum(1)
        for c, fc in zip(cols, f):
            w[:, c] = g * fc


RIGID_ISLAND = 0.05   # loose pieces (not skin) within this radius move rigidly ...
ATTACH_REACH = 0.03   # ... with the weights of the surface they sit on, found within this distance
_HEAD_OBJS = []       # the head part's objects (build_rig)
_ATTACH_HOST = np.zeros((0, 3))   # every skinned vertex outside the small loose pieces (build_rig)
WAIST_STRADDLE = 0.15  # ... unless both 上半身 and 下半身 hold at least this share of it


def _attach_weights(p, part, bones, fallback, exclude=None):
    """Weights for a small rigid ornament (points `p`): the part's weights at the point of
    the surface it sits on (the closest vertex of any larger skinned piece: the ankle wrap
    under a shoe leaf, the hair under a flower), so it rides that surface instead of
    floating at its own centroid's blend. `fallback` (the island average) when nothing
    is within ATTACH_REACH. Host vertices at the points `exclude` (the piece itself, when
    it is large enough to be a host) are skipped."""
    host = _ATTACH_HOST
    if not len(host):
        return fallback
    c = p.mean(0)
    r = float(np.linalg.norm(p - c, axis=1).max())
    near = host[np.linalg.norm(host - c, axis=1) <= r + ATTACH_REACH]
    if exclude is not None and len(near):
        own = np.linalg.norm(near[:, None, :] - exclude[None], axis=2).min(1) < 1e-7
        near = near[~own]
    if not len(near):
        return fallback
    d = np.linalg.norm(p[:, None, :] - near[None], axis=2)
    i = np.unravel_index(int(np.argmin(d)), d.shape)
    if d[i] > ATTACH_REACH:
        return fallback
    at = near[i[1]][None]
    w = _base_weights(part, at, bones) * _side_mask(c[None], np.zeros(1, dtype=int), bones, False)
    tot = w.sum()
    return w[0] / tot if tot > 1e-9 else fallback


# ornaments that lie along the skin over a joint ride the skin under each of their points
# instead of one attachment point (round 7: the shoe leaves rise from the ankle wrap up the
# shin; rigid on the wrap's ankle blend they swung into the leg when the foot turned)
SKIN_ORNAMENTS = {'shoes': ('shoes_leaves',)}
ORNAMENT_SPAN = 0.02      # m from the root within which a piece keeps (mostly) its root's weights
ORNAMENT_SMOOTH = 0.01    # m: smoothing of the blend profile along the piece
ORNAMENT_KNOTS = 24       # samples of that profile


def _skin_ornament(obj, part):
    return SKIN_FOLLOW and _SKIN is not None and any(obj.name.startswith(p) for p in SKIN_ORNAMENTS.get(part, ()))


def _skin_ornament_weights(w, co, labels, part, bones, roots):
    """Per loose piece: at its root (the nearest of `roots`, the points the part says its
    pieces spring from; else the vertex nearest any larger piece) the weights of the
    surface there (as for a rigid ornament), so it stays attached; further out a blend of
    those and the skin's weights under the far end, by how far the skin under each point
    has gone from one to the other (smoothed along the piece, ORNAMENT_SMOOTH): the blade
    keeps its clearance as the skin under it moves, and its weights change by one smooth
    ramp along it, never across it."""
    sk = _skin_sample(co, [b.name for b in bones], w, reach=(1.0, 2.0))
    A, Fw = sk.copy(), sk.copy()
    t = np.zeros(len(co))
    done = np.zeros(len(co), dtype=bool)
    host = _ATTACH_HOST
    for k in np.unique(labels):
        m = np.nonzero(labels == k)[0]
        p = co[m]
        if len(roots):
            r = roots[int(np.argmin(np.linalg.norm(roots - p.mean(0), axis=1)))]
        else:
            if not len(host):
                continue
            c = p.mean(0)
            near = host[np.linalg.norm(host - c, axis=1) <= float(np.linalg.norm(p - c, axis=1).max()) + ATTACH_REACH]
            if len(near):
                near = near[np.linalg.norm(near[:, None, :] - p[None], axis=2).min(1) >= 1e-7]   # not itself
            if not len(near):
                continue
            d = np.linalg.norm(p[:, None, :] - near[None], axis=2)
            r = p[np.unravel_index(int(np.argmin(d)), d.shape)[0]]
        root_w = _attach_weights(r[None], part, bones, sk[m].mean(0), exclude=p)
        dist = np.linalg.norm(p - r, axis=1)
        # one far set of weights (the skin's under the far end); the weights only move
        # along root -> far (one scalar per point), never across the blade
        far = sk[m][dist >= np.quantile(dist, 0.9)].mean(0)
        span = far - root_w
        A[m], Fw[m] = root_w, far
        done[m] = True
        if float(span @ span) < 1e-6:      # the skin under it moves as its root: rigid
            continue
        # how far along root -> far the skin under each point is, as one smooth, rising
        # function of the distance from the root (so the two faces of a thin blade, at the
        # same distance, share their weights), attached at the root
        f = np.clip((sk[m] - root_w) @ span / float(span @ span), 0.0, 1.0)
        dmax = max(float(dist.max()), 1e-6)
        knots = np.linspace(0.0, dmax, ORNAMENT_KNOTS)
        h = dmax / (ORNAMENT_KNOTS - 1)
        kern = np.exp(-0.5 * ((dist[None] - knots[:, None]) / max(ORNAMENT_SMOOTH, h)) ** 2)
        g = np.maximum.accumulate((kern @ f) / np.maximum(kern.sum(1), 1e-12))
        g = np.minimum(g, _smoothstep(0.0, ORNAMENT_SPAN, knots))
        t[m] = np.interp(dist, knots, g)
    out = np.where(done[:, None], A * (1.0 - t[:, None]) + Fw * t[:, None], sk)
    s = out.sum(1, keepdims=True)
    return np.where(s > 1e-12, out / np.maximum(s, 1e-12), w)


def _island_rules(w, co, labels, bones, part):
    """Per loose part: a finger part belongs to its own finger chain only (neighbouring
    finger envelopes overlap at ~1 cm), and small ornaments (bows, leaves, beads) take
    their island's average weights so they move as one piece."""
    chains = {}
    col = {b.name: j for j, b in enumerate(bones)}
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
            mean = w[m].mean(0)
            # an ornament across the 上半身/下半身 split (the waist bow) rides the waist
            # like the cloth under it instead of turning rigidly with one half
            waist = [col[n] for n in ('上半身', '下半身') if n in col]
            straddles = len(waist) == 2 and min(mean[waist]) > WAIST_STRADDLE
            if np.linalg.norm(p - p.mean(0), axis=1).max() < RIGID_ISLAND and not straddles:
                # back hair has per-lock passes after the base weights: keep its average there
                w[m] = mean if part == 'hair_back' else _attach_weights(p, part, bones, mean)
    s = w.sum(1, keepdims=True)
    return np.where(s > 1e-12, w / np.maximum(s, 1e-12), w)


# neck accessories with explicit weights (accessories part, by object name prefix)
NECK_CORDS = {'acc_choker': 'choker', 'acc_halter': 'halter'}
HALTER_NECK_FADE = (0.03, 0.005)   # below choker_z: the halter hands over from 首 to the skin's weights


def _neck_cord(obj, part):
    if part != 'accessories':
        return None
    return next((v for k, v in NECK_CORDS.items() if obj.name.startswith(k)), None)


NECK_CORD_SKIN = True    # round 7: the choker and halter ride the skin under them (_choker_skin)
CHOKER_BINS = 72         # stations round the choker loop at which the skin is sampled
CHOKER_SMOOTH = 12.0     # deg: smoothing of the sampled weights round the loop
HALTER_REACH = (0.02, 0.06)   # m off the skin: the halter takes the skin's weights within this
HALTER_SMOOTH = 0.008    # m: surface smoothing of the halter's sampled weights


def _choker_skin(co, bones):
    """(V, B) choker weights from the neck skin, or None without a skinned body. Each
    vertex takes the skin's weights at the tube's centre line at its angle round the loop
    (the best-fit plane of the ring), sampled at CHOKER_BINS stations and smoothed round
    the loop: a whole cross-section of the tube shares one set of weights, so a turned or
    bent neck cannot shear the tube (round 6 split 首 / 上半身2 across the tube's height:
    ×2.47 in look_over_shoulder), and the ring moves with the skin it lies on."""
    if not SKIN_FOLLOW or _SKIN is None or len(co) < 8:
        return None
    A = np.c_[co[:, 0], co[:, 1], np.ones(len(co))]
    coef = np.linalg.lstsq(A, co[:, 2], rcond=None)[0]
    n = np.array([-coef[0], -coef[1], 1.0])
    n /= np.linalg.norm(n)
    c = co.mean(0)
    e1 = np.array([1.0, 0.0, 0.0]) - n * n[0]
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(n, e1)
    d = co - c
    phi = np.arctan2(d @ e2, d @ e1)
    rho = np.hypot(d @ e1, d @ e2)
    h = d @ n
    nb = CHOKER_BINS
    k = np.floor((phi + np.pi) / (2 * np.pi) * nb).astype(int) % nb
    cnt = np.bincount(k, minlength=nb)
    if (cnt == 0).any():
        return None
    rb, hb = np.bincount(k, rho, nb) / cnt, np.bincount(k, h, nb) / cnt
    ang = (np.arange(nb) + 0.5) / nb * 2 * np.pi - np.pi
    pts = c + np.cos(ang)[:, None] * rb[:, None] * e1 + np.sin(ang)[:, None] * rb[:, None] * e2 + hb[:, None] * n
    ws = _skin_sample(pts, [b.name for b in bones], np.zeros((nb, len(bones))), reach=(1.0, 2.0))
    if ws.sum(1).min() < 0.5:
        return None
    # circular Gaussian smoothing over the stations
    da = (np.arange(nb)[:, None] - np.arange(nb)[None]) % nb
    da = np.minimum(da, nb - da) * 360.0 / nb
    g = np.exp(-0.5 * (da / CHOKER_SMOOTH) ** 2)
    ws = (g @ ws) / g.sum(1, keepdims=True)
    # linear interpolation between the two stations either side of each vertex
    t = (phi + np.pi) / (2 * np.pi) * nb - 0.5
    i0 = np.floor(t).astype(int)
    f = (t - i0)[:, None]
    out = ws[i0 % nb] * (1.0 - f) + ws[(i0 + 1) % nb] * f
    return out / out.sum(1, keepdims=True)


def _neck_cord_weights(kind, w, co, bones, edges=None):
    """The choker rides the neck skin (_choker_skin; without a skinned body: 首, with a
    little 上半身2 at its lower edge). The halter cords run from the choker over the shoulder
    slope to the bodice and take the weights of the skin under them (HALTER_REACH), so
    they stay on the neck and the shoulder slope as they move (without a skinned body: 首
    at the choker end, the smoothed envelope weights below)."""
    col = {b.name: i for i, b in enumerate(bones)}
    neck, chest, head = col.get('首'), col.get('上半身2'), col.get('頭')
    if neck is None or chest is None or head is None:
        return w
    if NECK_CORD_SKIN and SKIN_FOLLOW and _SKIN is not None:
        if kind == 'choker':
            sk = _choker_skin(co, bones)
            if sk is not None:
                return sk
        else:
            sk = _skin_sample(co, [b.name for b in bones], w, reach=HALTER_REACH)
            # like the bodice it lies on: at most BODICE_ARM_CAP of the arm (the chest skin
            # by the armpit takes more of a raised arm than a cord laid over it would)
            arm = [i for i, b in enumerate(bones) if b.name.split('.')[0] in ('腕D', '腕')]
            if arm:
                a = sk[:, arm].sum(1)
                k = np.minimum(1.0, BODICE_ARM_CAP / np.maximum(a, 1e-9))
                sk[:, chest] += a * (1.0 - k)
                sk[:, arm] *= k[:, None]
            # one set of weights across the cord's section (a 1.4 mm tube): smoothed wider
            # than its girth, so the section cannot shear
            if edges is not None:
                sk = _smooth(sk, co, edges, HALTER_SMOOTH)
            return sk / np.maximum(sk.sum(1, keepdims=True), 1e-12)
    out = np.zeros_like(w)
    if kind == 'choker':
        out = np.zeros_like(w)
        t, _ = _neck_frac(_choker_centre(co), bones)
        for i, g in zip((chest, neck, head), _neck_split(t)):
            out[:, i] = g
        return out
    f = _smoothstep(L['choker_z'] - HALTER_NECK_FADE[0], L['choker_z'] - HALTER_NECK_FADE[1], co[:, 2])
    out = w * (1.0 - f)[:, None]
    t, _ = _neck_frac(co, bones)
    for i, g in zip((chest, neck, head), _neck_split(t)):
        out[:, i] += f * g
    return out


def _choker_centre(co):
    """Each choker vertex moved onto the loop's best-fit plane (its centreline height)."""
    A = np.c_[co[:, 0], co[:, 1], np.ones(len(co))]
    coef = np.linalg.lstsq(A, co[:, 2], rcond=None)[0]
    out = co.copy()
    out[:, 2] = A @ coef
    return out


def _polyline_u(co, A, B):
    """Position of each point along the polyline of segments A[i]-B[i]: i + t on its
    nearest segment."""
    best, u = np.full(len(co), np.inf), np.zeros(len(co))
    for i in range(len(A)):
        ab = B[i] - A[i]
        t = np.clip(((co - A[i]) @ ab) / max(float(ab @ ab), 1e-12), 0.0, 1.0)
        dist = np.linalg.norm(co - (A[i] + t[:, None] * ab), axis=1)
        closer = dist < best
        best = np.where(closer, dist, best)
        u = np.where(closer, i + t, u)
    return u


def _lock_weights(w, co, labels, bones):
    """A back-hair lock with its own chain (meta 'lock' = its key) rides that chain alone,
    by position along the chain (so a curl at the tip stays on the last bones even where
    it turns back up), handing over from 頭 over the first half bone."""
    by_key = {}
    for j, b in enumerate(bones):
        if 'lock' in b.meta:
            by_key.setdefault(tuple(b.meta['lock']), []).append(j)
    if not by_key:
        return
    head = [j for j, b in enumerate(bones) if b.name == '頭']
    for k in np.unique(labels):
        m = labels == k
        cols = sorted(by_key.get(_lock_key(co[m]), []), key=lambda j: bones[j].meta.get('seg', 0))
        if not cols:
            continue
        A = np.array([bones[j].head for j in cols])
        B = np.array([bones[j].tail for j in cols])
        u = _polyline_u(co[m], A, B)
        n = len(cols)
        share = _smoothstep(0.0, ROOT_BLEND, u) if head else np.ones(len(u))
        uc = np.clip(u, 0.5, n - 0.5)
        w[m] = 0.0
        rows = np.nonzero(m)[0]
        for i, j in enumerate(cols):
            w[rows, j] = share * np.maximum(0.0, 1.0 - np.abs(uc - (i + 0.5)))
        if head:
            w[rows, head[0]] = 1.0 - share


def _weights(obj, part, co, bones):
    """(V, k) bone indices and weights for the vertices of `obj` (world positions `co`)."""
    global _SLEEVE_S, _SLEEVE_EDGES, _SLEEVE_N, _SOCKET_S
    edges = _topology(obj, co)
    _SLEEVE_S = _sleeve_param(obj, co) if part == 'sleeves' else None
    _SLEEVE_EDGES, _SLEEVE_N = (edges, len(co)) if part == 'sleeves' else (None, 0)
    _SOCKET_S = _point_param(obj, co, 'levi_socket_param') if part == 'body' else None
    w = _base_weights(part, co, bones)
    _SLEEVE_S, _SLEEVE_EDGES, _SLEEVE_N = None, None, 0
    _SOCKET_S = None
    cord = _neck_cord(obj, part)
    labels = _islands(len(co), edges)
    if part == 'hair_back':
        _lock_weights(w, co, labels, bones)
    masked = w * _side_mask(co, labels, bones, part not in SIDED_PARTS_EXEMPT)
    ok = masked.sum(1) > 1e-9
    w = np.where(ok[:, None], masked, w)
    w = w / w.sum(1, keepdims=True)
    radius = SLEEVE_SMOOTH if part == 'sleeves' and SLEEVE_BUILD else SMOOTH_RADIUS.get(part, DEFAULT_SMOOTH)
    w = _smooth(w, co, edges, radius)
    m = _crotch_mask(co, bones) if part in CROTCH_PARTS and CROTCH_SMOOTH > 0 else None
    if m is not None and m.max() > 0:
        # the crotch is pulled between both thighs in a stride: spread its L/R weight
        # change over a wider band than the rest of the skin
        w = w * (1.0 - m[:, None]) + _smooth(w, co, edges, CROTCH_SMOOTH) * m[:, None]
    m = _armpit_mask(co, bones) if part in CROTCH_PARTS and ARMPIT_SMOOTH > 0 else None
    if m is not None and m.max() > 0:
        # a raised arm pulls the armpit skin between the ribs and the arm: spread the
        # torso / arm weight change over a wider band there too
        w = w * (1.0 - m[:, None]) + _smooth(w, co, edges, ARMPIT_SMOOTH) * m[:, None]
    if part in CROTCH_PARTS and HIP_AUX:
        _hat_remap(w, bones)
    if part == 'hair_back':
        w = _hair_head_fade(w, co, bones)
    if part in SHELL_PARTS:
        w = _shell_share(w, co, bones)
    if part in CROTCH_PARTS and ARM_CAP:
        w = _arm_cap(w, co, bones)
    if cord:
        w = _neck_cord_weights(cord, w, co, bones, edges)
    elif _skin_ornament(obj, part):
        roots = np.array([tuple(obj.matrix_world @ Vector(p)) for p in obj.get('levi_attach_points', [])]).reshape(-1, 3)
        w = _skin_ornament_weights(w, co, labels, part, bones, roots)
    else:
        w = _island_rules(w, co, labels, bones, part)
    # which bones a vertex keeps is decided on a wider-smoothed copy of its weights, so
    # the set changes gradually along the surface instead of wherever two weak bones swap
    guide = _smooth(w, co, edges, PRUNE_SMOOTH) if PRUNE_SMOOTH > 0 and radius > 0 else None
    if guide is not None and part in SHELL_PARTS:
        guide = _shell_share(guide, co, bones)
    return _prune(w, bones, guide, co)


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
    if not any(m.name not in keep for m in obj.modifiers):
        return
    if obj.data.shape_keys:
        _apply_modifiers_with_keys(obj, keep)
    else:
        common.apply_modifiers(obj, keep=keep)


def _apply_modifiers_with_keys(obj, keep):
    """Apply the generator modifiers (mirror, subsurf...) of a mesh with shape keys
    (the head's morphs), keeping every key: the mesh is evaluated once per key at full
    value, and the keys are rebuilt on the evaluated topology. Refuses (and leaves the
    object as it is) if a key changes the vertex count."""
    keys = obj.data.shape_keys.key_blocks
    saved = [(kb.name, kb.value, kb.mute, kb.slider_min, kb.slider_max) for kb in keys]
    show = {m.name: m.show_viewport for m in obj.modifiers}
    for m in obj.modifiers:
        if m.name in keep:
            m.show_viewport = False
    show_only = obj.show_only_shape_key
    obj.show_only_shape_key = False
    dg = bpy.context.evaluated_depsgraph_get()

    def sample(active):
        for i, kb in enumerate(keys):
            if i:
                kb.value = 1.0 if i == active else 0.0
                kb.mute = False
        obj.data.update()
        dg.update()
        ev = obj.evaluated_get(dg)
        me = ev.to_mesh()
        co = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get('co', co)
        ev.to_mesh_clear()
        return co
    shapes = [sample(i) for i in range(len(keys))]
    for (name, val, mute, lo, hi), kb in zip(saved, keys):
        kb.value, kb.mute = val, mute
    obj.show_only_shape_key = show_only
    if any(len(c) != len(shapes[0]) for c in shapes):
        print(f'rig: {obj.name}: a shape key changes the topology under its modifiers; not applied')
        for m in obj.modifiers:
            m.show_viewport = show[m.name]
        return
    for i, kb in enumerate(keys):
        if i:
            kb.value = 0.0
    dg.update()
    new = bpy.data.meshes.new_from_object(obj.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    old_me = obj.data
    obj.shape_key_clear()
    obj.data = new
    new.name = old_me.name
    for m in list(obj.modifiers):
        if m.name in keep:
            m.show_viewport = show[m.name]
        else:
            obj.modifiers.remove(m)
    base = obj.shape_key_add(name=saved[0][0], from_mix=False)
    base.data.foreach_set('co', shapes[0])
    for (name, val, mute, lo, hi), co in zip(saved[1:], shapes[1:]):
        kb = obj.shape_key_add(name=name, from_mix=False)
        kb.data.foreach_set('co', co)
        kb.slider_min, kb.slider_max = lo, hi
        kb.value, kb.mute = val, mute
    if old_me.users == 0:
        bpy.data.meshes.remove(old_me)


def _drape_prop(arm, pb, prop, tab, thigh, sgn):
    """pb[prop] = the drape row `tab` (rad over DRAPE_PHI) at the forward pitch of
    `thigh`: a driver reading the thigh's twist about its own X (evaluated local rotation,
    so IK counts) through an F-curve with the table as linear keys, flat outside."""
    pb[prop] = 0.0
    fc = pb.driver_add(f'["{prop}"]')
    drv = fc.driver
    drv.type = 'SCRIPTED'
    v = drv.variables.new()
    v.name, v.type = 'p', 'TRANSFORMS'
    tg = v.targets[0]
    tg.id, tg.bone_target = arm, thigh
    tg.transform_type, tg.rotation_mode, tg.transform_space = 'ROT_X', 'SWING_TWIST_X', 'LOCAL_SPACE'
    drv.expression = 'p'
    for m in list(fc.modifiers):
        fc.modifiers.remove(m)
    pts = sorted((sgn * math.radians(x), float(y)) for x, y in zip(DRAPE_PHI, tab))
    fc.keyframe_points.add(len(pts))
    for kp, (x, y) in zip(fc.keyframe_points, pts):
        kp.co = (x, y)
        kp.interpolation = 'LINEAR'
    fc.extrapolation = 'CONSTANT'
    fc.update()


def _skirt_drape_driver(arm, pb, d):
    """Blender only: turn a skirt chain joint about the world X axis by the drape table
    (_skirt_drape). The chain's L follow bone at joint i carries two properties, the
    absolute turn of segment i for each thigh pitched alone (_drape_prop); the larger
    forward and backward lifts of the two thighs combine, and the joint turns by the
    combined turn of its segment minus the one above (read from the joint above's
    follow bone). The R follow bones stay at rest. In the PMX the segments below the
    chain roots are physics bodies colliding with the legs, so only the linear share
    ('follow') is exported."""
    if d['own'] != 'L':
        return
    i = d['i']
    for t in 'LR':
        x = arm.data.bones[f'足.{t}'].matrix_local.to_3x3().col[0]
        sgn = 1.0 if x.dot(Vector((-1.0, 0.0, 0.0))) > 0 else -1.0   # forward pitch = + twist about X
        _drape_prop(arm, pb, f'drape_{t}', d[t][i], f'足.{t}', sgn)
    pb.rotation_mode = 'AXIS_ANGLE'      # about local Y (the bone points along -X): forward pitch
    pb.rotation_axis_angle = (0.0, 0.0, 1.0, 0.0)
    fc = pb.driver_add('rotation_axis_angle', 0)
    drv = fc.driver
    drv.type = 'SCRIPTED'
    srcs = [('a', pb.name, 'drape_L'), ('b', pb.name, 'drape_R')]
    if i:
        srcs += [('c', d['above'], 'drape_L'), ('d', d['above'], 'drape_R')]
    for name, bone, prop in srcs:
        v = drv.variables.new()
        v.name, v.type = name, 'SINGLE_PROP'
        tg = v.targets[0]
        tg.id_type, tg.id = 'OBJECT', arm
        tg.data_path = f'pose.bones["{bone}"]["{prop}"]'
    expr = 'max(0,a,b)+min(0,a,b)'
    if i:
        expr += '-max(0,c,d)-min(0,c,d)'
    drv.expression = expr
    for m in list(fc.modifiers):
        fc.modifiers.remove(m)


def _quat_power_drivers(arm, pb, src, k):
    """PMX 回転付与 of `src` with share k (negative allowed) for a bone whose source is
    below it in the hierarchy (the shrug follows the arm it carries). A Copy Rotation
    constraint would read the source's evaluated matrix, a dependency cycle; drivers read
    the source's own rotation channels instead, which MMD's 付与 uses too, and set this
    bone's rotation to slerp(identity, q, k) = q^k. The owner must share the source's
    rest orientation, so the local quaternion means the same turn in both."""
    pb.rotation_mode = 'QUATERNION'
    # the drivers read the source's quaternion channels (MMD motions and mmd_tools' VMD
    # import key quaternions): keep the source in quaternion mode
    arm.pose.bones[src].rotation_mode = 'QUATERNION'
    # half angle from atan2, so a non-unit quaternion (per-component F-curve interpolation)
    # gives the angle Blender shows, not acos(w) of the raw value
    h = 'atan2(sqrt(x * x + y * y + z * z), abs(w))'
    sgn = '(1.0 if w >= 0.0 else -1.0)'
    n = 'max(sqrt(x * x + y * y + z * z), 1e-9)'
    exprs = [f'cos({k!r} * {h})'] + [f'{sgn} * {c} * sin({k!r} * {h}) / {n}' for c in 'xyz']
    for i, expr in enumerate(exprs):
        fc = pb.driver_add('rotation_quaternion', i)
        drv = fc.driver
        drv.type = 'SCRIPTED'
        for ci, c in enumerate('wxyz'):
            v = drv.variables.new()
            v.name, v.type = c, 'SINGLE_PROP'
            t = v.targets[0]
            t.id_type, t.id = 'OBJECT', arm
            t.data_path = f'pose.bones["{src}"].rotation_quaternion[{ci}]'
        drv.expression = expr
        for m in list(fc.modifiers):
            fc.modifiers.remove(m)


# symbolic quaternions for driver expressions: a component is a polynomial
# {sorted tuple of factor strings: coefficient}, so products of constant quaternions
# collapse into a few terms per channel
def _p_const(c):
    return {(): float(c)} if abs(c) > 1e-12 else {}


def _p_atom(*factors):
    return {tuple(sorted(factors)): 1.0}


def _p_add(a, b, k=1.0):
    r = dict(a)
    for f, v in b.items():
        r[f] = r.get(f, 0.0) + k * v
    return {f: v for f, v in r.items() if abs(v) > 1e-12}


def _p_mul(a, b):
    r = {}
    for fa, va in a.items():
        for fb, vb in b.items():
            f = tuple(sorted(fa + fb))
            r[f] = r.get(f, 0.0) + va * vb
    return {f: v for f, v in r.items() if abs(v) > 1e-12}


def _q_mul(a, b):
    def comb(*terms):
        r = {}
        for k, p, q in terms:
            r = _p_add(r, _p_mul(p, q), k)
        return r
    (w1, x1, y1, z1), (w2, x2, y2, z2) = a, b
    return [comb((1, w1, w2), (-1, x1, x2), (-1, y1, y2), (-1, z1, z2)),
            comb((1, w1, x2), (1, x1, w2), (1, y1, z2), (-1, z1, y2)),
            comb((1, w1, y2), (-1, x1, z2), (1, y1, w2), (1, z1, x2)),
            comb((1, w1, z2), (1, x1, y2), (-1, y1, x2), (1, z1, w2))]


def _num(v):
    s = f'{v:.7f}'.rstrip('0').rstrip('.')
    return s if s not in ('', '-', '-0') else '0'


def _p_str(p):
    """A polynomial as a driver expression (short: Blender keeps 255 characters)."""
    if not p:
        return '0.0'
    terms = []
    for f, v in sorted(p.items()):
        if not f:
            terms.append(_num(v))
        elif abs(v - 1.0) < 1e-9:
            terms.append('*'.join(f))
        elif abs(v + 1.0) < 1e-9:
            terms.append('-' + '*'.join(f))
        else:
            terms.append('*'.join([_num(v)] + list(f)))
    return '+'.join(terms).replace('+-', '-')


def _q_const(q):
    return [_p_const(c) for c in (q.w, q.x, q.y, q.z)]


def _q_conj(q):
    return [q[0]] + [{f: -v for f, v in p.items()} for p in q[1:]]


def _q_pow_const(q, k):
    from mathutils import Quaternion
    ax, ang = q.to_axis_angle()
    return Quaternion(ax, ang * k)


def _driver(fc, expr, variables):
    """Scripted driver on F-curve fc: variables are (name, id, data path)."""
    if len(expr) > 255:
        raise ValueError(f'driver expression longer than Blender keeps ({len(expr)}): {expr}')
    drv = fc.driver
    drv.type = 'SCRIPTED'
    for name, idv, path in variables:
        v = drv.variables.new()
        v.name, v.type = name, 'SINGLE_PROP'
        t = v.targets[0]
        t.id_type, t.id = 'OBJECT', idv
        t.data_path = path
    drv.expression = expr
    for m in list(fc.modifiers):
        fc.modifiers.remove(m)


def _shoulder_drivers(arm, pb, src, kind, total, shrug):
    """Blender evaluation of the shrug, the staged helpers and 腕D (SHOULDER_SWING_REF):
    swing from a reference direction + twist about the arm, both shared continuously
    instead of q^k. The shrug bone carries the decomposition as custom properties (sh_*,
    from 腕's quaternion); each bone's quaternion is a product of constants, a power of the
    swing and twists (kind 'shrug' / 'stage' / 'arm', total = its total share), evaluated
    in steps of short expressions (custom properties), one quaternion product per step."""
    a = SHOULDER_SHRUG
    src_pb = arm.pose.bones[src]
    src_pb.rotation_mode = 'QUATERNION'
    sp = arm.pose.bones[shrug]
    m = arm.data.bones[src].matrix_local.to_3x3()
    side = -1.0 if src.endswith('.R') else 1.0
    uw = Vector((SHOULDER_SWING_REF[0] * side, SHOULDER_SWING_REF[1], SHOULDER_SWING_REF[2])).normalized()
    u = (m.transposed() @ uw).normalized()
    A = u.rotation_difference(Vector((0.0, 1.0, 0.0)))
    q_src = [(c, arm, f'pose.bones["{src}"].rotation_quaternion[{i}]') for i, c in enumerate('wxyz')]

    def path(bone, name):
        return f'pose.bones["{bone}"]["{name}"]'

    def prop(owner, name, expr, variables):
        owner[name] = 0.0
        _driver(owner.driver_add(f'["{name}"]'), expr, variables)

    def qprop(owner, name, qsym, variables):
        for c, comp in zip('wxyz', qsym):
            prop(owner, f'{name}_{c}', _p_str(comp), variables)

    def qread(bone, name, var):     # a quaternion stored as properties: symbols + variables
        names = [f'{var}{i}' for i in range(4)]
        return [_p_atom(n) for n in names], [(n, arm, path(bone, f'{name}_{c}')) for n, c in zip(names, 'wxyz')]

    def swing(e):        # B^e: the share e of the swing from the reference to the arm
        s = f'sin({_num(0.5 * e)}*b)'
        return [_p_atom(f'cos({_num(0.5 * e)}*b)'), _p_atom(s, 'ax'), _p_atom(s, 'ay'), _p_atom(s, 'az')]

    def twist(k):        # the share k of the (faded) twist about the arm's own axis
        return [_p_atom(f'cos({_num(0.5 * k)}*t)'), {}, _p_atom(f'sin({_num(0.5 * k)}*t)'), {}]
    bv = [('b', arm, path(shrug, 'sh_b'))] + [(f'a{c}', arm, path(shrug, f'sh_a{c}')) for c in 'xyz']
    tv = [('t', arm, path(shrug, 'sh_tw'))]
    qv = [_p_atom(c) for c in 'wxyz']
    if kind == 'shrug':
        # the decomposition, as properties of the shrug bone
        n = '(w*w+x*x+y*y+z*z)'
        for k, e in (('sh_dx', f'2*(x*y-w*z)/{n}'), ('sh_dy', f'(w*w-x*x+y*y-z*z)/{n}'),
                     ('sh_dz', f'2*(y*z+w*x)/{n}')):
            prop(sp, k, e, q_src)
        dv = [(c, arm, path(shrug, 'sh_d' + c)) for c in 'xyz']
        U = [_num(c) for c in u]
        prop(sp, 'sh_cx', f'{U[1]}*z-{U[2]}*y'.replace('--', '+'), dv)
        prop(sp, 'sh_cy', f'{U[2]}*x-{U[0]}*z'.replace('--', '+'), dv)
        prop(sp, 'sh_cz', f'{U[0]}*y-{U[1]}*x'.replace('--', '+'), dv)
        cv = [('c' + c, arm, path(shrug, 'sh_c' + c)) for c in 'xyz']
        cn = 'sqrt(cx*cx+cy*cy+cz*cz)'
        prop(sp, 'sh_b', f'atan2({cn},{U[0]}*x+{U[1]}*y+{U[2]}*z)'.replace('+-', '-'), cv + dv)
        for c in 'xyz':
            prop(sp, f'sh_a{c}', f'c{c}/max({cn},1e-9)', cv)
        # T = S^-1 q, S = B A^-1: the twist about the arm; then its faded share
        qprop(sp, 'sh_i', _q_mul(_q_const(A), swing(-1.0)), bv)
        iq, iv = qread(shrug, 'sh_i', 'i')
        tq = _q_mul(iq, qv)
        prop(sp, 'sh_tww', _p_str(tq[0]), iv + q_src)
        prop(sp, 'sh_twy', _p_str(tq[2]), iv + q_src)
        prop(sp, 'sh_tau', '2*atan2(r*(1 if p>=0 else -1),abs(p))',
             [('p', arm, path(shrug, 'sh_tww')), ('r', arm, path(shrug, 'sh_twy'))])
        f0 = math.radians(SHOULDER_TWIST_FADE)
        prop(sp, 'sh_fs', f'min(max((abs(g)-{_num(f0)})/{_num(math.pi - f0)},0),1)', [('g', arm, path(shrug, 'sh_tau'))])
        prop(sp, 'sh_tw', 'g*(1-s*s*(3-2*s))', [('g', arm, path(shrug, 'sh_tau')), ('s', arm, path(shrug, 'sh_fs'))])
        # the shrug by swing + twist ...
        qprop(sp, 'sh_s', _q_mul(swing(a), _q_const(_q_pow_const(A, -a))), bv)
        pq, pv = qread(shrug, 'sh_s', 'p')
        qprop(sp, 'sh_r', _q_mul(pq, twist(a)), pv + tv)
        # ... and as round 6's plain share q^a (shortest path), which is what the poses
        # and garments were set up against; the clavicle takes q^a up to SHOULDER_SHRUG_BLEND[0]
        # of 腕's turn and hands over to the swing + twist share by [1], before q^a flips
        prop(sp, 'sh_h', 'atan2(sqrt(x*x+y*y+z*z),abs(w))', q_src)
        hv = [('h', arm, path(shrug, 'sh_h')), ('g', arm, path(shrug, 'sh_sg'))]
        prop(sp, 'sh_sg', '1 if w>=0 else -1', q_src)
        prop(sp, 'sh_c_w', f'cos({_num(a)}*h)', hv)
        for c in 'xyz':
            prop(sp, f'sh_c_{c}', f'g*{c}*sin({_num(a)}*h)/max(sqrt(x*x+y*y+z*z),1e-9)', hv + q_src)
        b0, b1 = (math.radians(0.5 * v) for v in SHOULDER_SHRUG_BLEND)
        prop(sp, 'sh_al', f'min(max((h-{_num(b0)})/{_num(b1 - b0)},0),1)', hv)
        prop(sp, 'sh_k', 'k*k*(3-2*k)', [('k', arm, path(shrug, 'sh_al'))])
        cq, cv2 = qread(shrug, 'sh_c', 'c')
        rq, rv = qread(shrug, 'sh_r', 'r')
        prop(sp, 'sh_dot', '+'.join(f'c{i}*r{i}' for i in range(4)), cv2 + rv)
        kv = [('k', arm, path(shrug, 'sh_k')), ('e', arm, path(shrug, 'sh_dot'))]
        for i, c in enumerate('wxyz'):
            prop(sp, f'sh_u_{c}', f'(1-k)*c{i}+k*(1 if e>=0 else -1)*r{i}', kv + cv2 + rv)
        uq, uv = qread(shrug, 'sh_u', 'u')
        for i, c in enumerate('wxyz'):
            prop(sp, f'sh_f_{c}', f'u{i}/max(sqrt(u0*u0+u1*u1+u2*u2+u3*u3),1e-9)', uv)
        out, ov = qread(shrug, 'sh_f', 'f')
    elif kind == 'stage':
        # total turn B^t A^-t T^t, then relative to the (blended) shrug: f^-1 total
        qprop(pb, 'st_p', _q_mul(swing(total), _q_const(_q_pow_const(A, -total))), bv)
        pq, pv = qread(pb.name, 'st_p', 'p')
        qprop(pb, 'st_t', _q_mul(pq, twist(total)), pv + tv)
        tq, tv2 = qread(pb.name, 'st_t', 'r')
        fq, fv = qread(shrug, 'sh_f', 'f')
        out, ov = _q_mul(_q_conj(fq), tq), fv + tv2
    else:
        # 腕D: whatever is left of 腕's turn after the shrug, f^-1 q
        fq, fv = qread(shrug, 'sh_f', 'f')
        out, ov = _q_mul(_q_conj(fq), qv), fv + q_src
    pb.rotation_mode = 'QUATERNION'
    for i in range(4):
        _driver(pb.driver_add('rotation_quaternion', i), _p_str(out[i]), ov)
def _conj_drivers(arm, pb, src):
    """Blender only: pb turns exactly back by src's rotation (the normalized conjugate of its
    quaternion; pb shares src's rest frame). Unlike a fractional power it has no branch."""
    pb.rotation_mode = 'QUATERNION'
    arm.pose.bones[src].rotation_mode = 'QUATERNION'
    n = 'max(sqrt(w * w + x * x + y * y + z * z), 1e-9)'
    for i, c in enumerate('wxyz'):
        drv = pb.driver_add('rotation_quaternion', i).driver
        drv.type = 'SCRIPTED'
        _quat_vars(drv, arm, src)
        drv.expression = f'{"" if c == "w" else "-"}{c} / {n}'


def _prop_var(drv, name, arm, path):
    """Driver variable `name`: the armature object's property at data path `path`."""
    v = drv.variables.new()
    v.name, v.type = name, 'SINGLE_PROP'
    t = v.targets[0]
    t.id_type, t.id = 'OBJECT', arm
    t.data_path = path


def _quat_vars(drv, arm, src):
    """Driver variables w, x, y, z: src's rotation quaternion channels."""
    for ci, c in enumerate('wxyz'):
        _prop_var(drv, c, arm, f'pose.bones["{src}"].rotation_quaternion[{ci}]')


def _sleeve_counter(arm, pb, grav, src):
    """Blender only (SLEEVE_COUNTER_FULL): 袖追従 (pb) turns toward 袖重力 (which turns back all
    of src = 腕) by a world-space Copy Rotation whose influence is SLEEVE_COUNTER, rising
    smoothly to 1 between SLEEVE_COUNTER_FULL degrees of 腕's turn. The ramp is a driven
    property of 袖重力 (driver expressions are short)."""
    pb.rotation_mode = 'QUATERNION'
    arm.pose.bones[src].rotation_mode = 'QUATERNION'
    gp = arm.pose.bones[grav]
    gp['levi_counter_ramp'] = 0.0
    a0, a1 = (math.radians(v) for v in SLEEVE_COUNTER_FULL)
    drv = gp.driver_add('["levi_counter_ramp"]').driver
    drv.type = 'SCRIPTED'
    _quat_vars(drv, arm, src)
    drv.expression = f'min(max((2.0 * atan2(sqrt(x * x + y * y + z * z), abs(w)) - {a0:.6f}) / {a1 - a0:.6f}, 0.0), 1.0)'
    c = pb.constraints.new('COPY_ROTATION')
    c.name = 'Sleeve counter'
    c.target, c.subtarget = arm, grav
    c.target_space = c.owner_space = 'WORLD'
    c.mix_mode = 'REPLACE'
    drv = c.driver_add('influence').driver
    drv.type = 'SCRIPTED'
    _prop_var(drv, 'u', arm, f'pose.bones["{grav}"]["levi_counter_ramp"]')
    k = SLEEVE_COUNTER
    drv.expression = f'{k!r} + {1.0 - k!r} * u * u * (3.0 - 2.0 * u)'


def _ramp_prop(arm, pb, prop, pairs, lo, hi):
    """Blender only: pb[prop] = 1 - smoothstep(lo, hi, d), d the smallest world distance
    between the bone heads of `pairs`: 1 when they are close, 0 from hi apart."""
    pb[prop] = 0.0
    drv = pb.driver_add(f'["{prop}"]').driver
    drv.type = 'SCRIPTED'
    names = []
    for i, (a, b) in enumerate(pairs):
        v = drv.variables.new()
        v.name, v.type = f'd{i}', 'LOC_DIFF'
        names.append(v.name)
        for t, n in zip(v.targets, (a, b)):
            t.id, t.bone_target = arm, n
            t.transform_space = 'WORLD_SPACE'
    d = names[0]
    for n in names[1:]:
        d = f'min({d}, {n})'
    drv.expression = f'1.0 - smoothstep({lo!r}, {hi!r}, {d})'


def _crowd_props(arm, ref):
    """Blender only: on 袖重力 (ref) of each side, 'levi_crowd' (SLEEVE_CROWD: the two drape
    roots, ref and its mirror, close together) and 'levi_near' (SLEEVE_NEAR: this side's
    wrist at the torso), each 0..1. False when the mirror is missing."""
    tag = ref.rsplit('.', 1)[-1]
    other = ref.rsplit('.', 1)[0] + '.' + ('R' if tag == 'L' else 'L')
    if other not in arm.pose.bones:
        return False
    pb = arm.pose.bones[ref]
    _ramp_prop(arm, pb, 'levi_crowd', [(ref, other)], SLEEVE_CROWD[0], SLEEVE_CROWD[1])
    wrist = f'手首.{tag}'
    pairs = [(wrist, n) for n in SLEEVE_NEAR[2] if n in arm.pose.bones] if SLEEVE_NEAR and wrist in arm.pose.bones else []
    pb['levi_near'] = 0.0
    if pairs:
        _ramp_prop(arm, pb, 'levi_near', pairs, SLEEVE_NEAR[0], SLEEVE_NEAR[1])
    return True


def _crowd_drivers(arm, pb, ref, axes, share=1.0, near=True):
    """Blender only (SLEEVE_CROWD, SLEEVE_NEAR): pb's scale on `axes` (local) is
    1 - SLEEVE_CROWD[2] * share * (ref's levi_crowd, or levi_near if larger and `near`)."""
    if 'levi_crowd' not in arm.pose.bones[ref] and not _crowd_props(arm, ref):
        return
    terms = ['c', 'n'] if near else ['c']
    for i, ax in enumerate('xyz'):
        if ax not in axes:
            continue
        drv = pb.driver_add('scale', i).driver
        drv.type = 'SCRIPTED'
        for name, prop in zip(terms, ('levi_crowd', 'levi_near')):
            _prop_var(drv, name, arm, f'pose.bones["{ref}"]["{prop}"]')
        amount = 'max(c, n)' if near else 'c'
        drv.expression = f'1.0 - {SLEEVE_CROWD[2] * share!r} * {amount}'


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
            if 'drape' in b.meta:
                _skirt_drape_driver(arm, pb, b.meta['drape'])
            elif src in data.bones and infl > 1e-4:
                c = pb.constraints.new('COPY_ROTATION')
                c.name = 'Follow'
                c.target, c.subtarget = arm, src
                c.target_space, c.owner_space = 'LOCAL_OWNER_ORIENT', 'LOCAL'
                c.mix_mode = 'BEFORE'
                c.influence = infl
        for src, k in b.meta.get('gravity', ()):
            # Blender only (MMD physics hangs the hair itself): turn back k of the torso
            # bone's sideways bend (about the forward axis), so the long hair keeps hanging
            # when she leans to a side. A forward bend and her twist still carry it along:
            # bent forward, the hair rests on her back (hanging free it went into it)
            c = pb.constraints.new('COPY_ROTATION')
            c.name = f'Gravity {src}'
            c.target, c.subtarget = arm, src
            c.target_space, c.owner_space = 'LOCAL_OWNER_ORIENT', 'LOCAL'
            c.mix_mode = 'BEFORE'
            c.use_x = c.use_y = False
            c.invert_z = True
            c.influence = k
        pg = b.meta.get('pitch_gravity', ())
        if pg:
            # Blender: turn back k of each torso bone's pitch only. The source's local turn
            # is re-expressed in this bone's rest frame, so its pitch is a turn about this
            # bone's rest axis nearest world X. For a segment running sideways (an outer
            # lock over the arm) that is its own length: it rolls a little and swings the
            # segments below it down, which is the point. (One Euler component: exact
            # for a pure bend, approximate when the torso also twists.)
            m = data.bones[b.name].matrix_local.to_3x3()
            ax = max(range(3), key=lambda i: abs(m.col[i].x))
            for src, k in pg:
                c = pb.constraints.new('COPY_ROTATION')
                c.name = f'Pitch gravity {src}'
                c.target, c.subtarget = arm, src
                c.target_space, c.owner_space = 'LOCAL_OWNER_ORIENT', 'LOCAL'
                c.mix_mode = 'BEFORE'
                c.use_x, c.use_y, c.use_z = (ax == 0), (ax == 1), (ax == 2)
                c.invert_x = c.invert_y = c.invert_z = True
                c.influence = k
        if 'append' in b.meta:
            # PMX only: 回転付与 with a (possibly negative) share, no Blender constraint
            src, k = b.meta['append']
            pb['mmd_append'] = src
            pb['mmd_append_influence'] = float(k)
        if b.name.split('.')[0] == '目' and EYE_LIMIT:
            # Blender only (PMX bones have no rotation limits): the eyes turn at most
            # EYE_LIMIT (yaw, pitch) degrees, the range in which the irises stay behind the lids
            c = pb.constraints.new('LIMIT_ROTATION')
            c.name = 'Gaze limit'
            c.owner_space = 'LOCAL'
            c.use_limit_x = c.use_limit_z = True
            c.min_x, c.max_x = -math.radians(EYE_LIMIT[1]), math.radians(EYE_LIMIT[1])
            c.min_z, c.max_z = -math.radians(EYE_LIMIT[0]), math.radians(EYE_LIMIT[0])
        if b.meta.get('helper'):
            pb['mmd_helper'] = True     # driven by 付与 only: hidden, not for the animator
        if 'follow_q' in b.meta:
            src, infl = b.meta['follow_q']
            pb['mmd_append'] = src
            pb['mmd_append_influence'] = float(infl)
            if 'shoulder' in b.meta and SHOULDER_SWING_REF:
                # the same total shares as the PMX append: the shrug's, the shrug's plus
                # the stage's own, the whole turn for 腕D
                kind, shrug = b.meta['shoulder']
                total = {'shrug': SHOULDER_SHRUG, 'stage': SHOULDER_SHRUG + infl, 'arm': 1.0}[kind]
                _shoulder_drivers(arm, pb, src, kind, total, shrug)
            elif 'sleeve_counter' in b.meta:
                _sleeve_counter(arm, pb, b.meta['sleeve_counter'], src)
            else:
                _quat_power_drivers(arm, pb, src, infl)
        if 'conj_of' in b.meta:
            _conj_drivers(arm, pb, b.meta['conj_of'])
        if 'crowd' in b.meta:
            # the sleeve's body copies flatten (local X, Z) when crowded or pressed to the torso;
            # the drape (袖追従, not deforming) shrinks about its root when crowded
            _crowd_drivers(arm, pb, b.meta['crowd'], 'xz' if b.deform else 'xyz', b.meta.get('crowd_share', 1.0), b.deform)
        if 'twist_of' in b.meta:
            # PMX fixed axis: a twist bone turns only about its own length
            pb.rotation_mode = 'QUATERNION'
            pb.lock_rotation = (True, False, True)
            pb.lock_rotation_w = False
            pb['mmd_fixed_axis'] = 1
    for t in 'LR':
        knee = arm.pose.bones[f'ひざ.{t}']
        knee.lock_ik_y = knee.lock_ik_z = True      # hinge about its local X
        # ... bending forward only (never hyperextended): exported as the PMX IK link
        # limit, like the standard model's (-180..-0.5 deg about X in MMD's axes)
        knee.use_ik_limit_x = True
        knee.ik_min_x, knee.ik_max_x = KNEE_IK_MIN, math.pi
        knee.ik_stretch = 0.0
        thigh = arm.pose.bones[f'足.{t}']
        thigh.ik_stretch = 0.0
        # Blender's solver, given the knee limit, may twist the thigh about its length to
        # reach a target and cross the legs; MMD's CCD solver does not. Blender only:
        # export_pmx keeps the PMX 足 link unlimited (mmd_ik_limit_custom1).
        thigh.lock_ik_y = True
    return arm


# generic poses for the prune's motion refit: (input bone stems, how, degrees). `how` is a
# world direction to bend toward (x mirrored on .R), or twist / curl / pitch / yaw / roll / side
MOTION_POSES = (
    (('腕',), (0, 0, 1), 80), (('腕',), (0, -1, 0), 80), (('ひじ',), (0, -1, 0), 90),
    (('手捩',), 'twist', 60), (('腕捩',), 'twist', 45), (('手首',), (0, -1, 0), 45),
    (('肩',), (0, 0, 1), 20), (('足',), (0, -1, 0), 60), (('足',), (0, 1, 0), 30),
    (('足',), 'side', 30), (('ひざ',), (0, 1, 0), 90), (('足首',), (0, -1, 0), 30),
    (('上半身',), 'pitch', 30), (('上半身',), 'yaw', 30), (('上半身2',), 'roll', 20),
    (('下半身',), 'pitch', 20), (('首',), 'yaw', 40), (('頭',), 'pitch', 30),
    (('Fingers',), 'curl', 60), (('Chains',), 'pitch', 25),
)


def _motion_samples(arm):
    """{deform bone: (K, 3, 4)} skinning matrices (posed @ rest^-1) of every deform bone
    in MOTION_POSES (each joint bent or twisted on its own, chain roots swung), evaluated
    on the real armature with its constraints and drivers, IK muted. The prune's refit
    (_motion_refit) compares vertex motion in them. The pose is reset afterwards."""
    from mathutils import Quaternion
    pbs = arm.pose.bones
    muted = [c for pb in pbs for c in pb.constraints if c.type == 'IK' and not c.mute]
    for c in muted:
        c.mute = True
    deform = [pb for pb in pbs if pb.bone.use_deform]
    out = {pb.name: [] for pb in deform}

    def rot(pb, axis_w, deg):
        local = (pb.bone.matrix_local.to_3x3().inverted() @ Vector(axis_w)).normalized()
        pb.rotation_mode = 'QUATERNION'
        pb.rotation_quaternion = Quaternion(local, math.radians(deg)) @ pb.rotation_quaternion

    for stems, how, deg in MOTION_POSES:
        for pb in pbs:
            pb.matrix_basis.identity()
        for pb in pbs:
            stem = pb.name.split('.')[0]
            grp = pb.bone.collections[0].name if pb.bone.collections else ''
            side = -1.0 if pb.name.endswith('.R') else 1.0
            hit = stem in stems or ('Fingers' in stems and grp == 'Fingers') or \
                ('Chains' in stems and grp in FOLD_CHAIN_GROUPS and stem.endswith('_0'))
            if not hit:
                continue
            ax = pb.bone.matrix_local.to_3x3()
            if how == 'twist':
                rot(pb, ax.col[1], deg * side)
            elif how == 'curl':
                rot(pb, ax.col[0], deg)
            elif isinstance(how, str):
                w_ax = {'pitch': (1, 0, 0), 'yaw': (0, 0, 1), 'roll': (0, 1, 0), 'side': (0, side, 0)}[how]
                rot(pb, w_ax, deg)
            else:
                tgt = Vector(how)
                tgt.x *= side
                rot(pb, ax.col[1].cross(tgt), deg)
        bpy.context.view_layer.update()
        for pb in deform:
            out[pb.name].append(np.array(pb.matrix @ pb.bone.matrix_local.inverted())[:3])
    for pb in pbs:
        pb.matrix_basis.identity()
    for c in muted:
        c.mute = False
    bpy.context.view_layer.update()
    return {k: np.array(v) for k, v in out.items()}


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
    # eyelid sheets (head_lid, carrying the blink morph) sit in front of the eyes: leave
    # them out, or the eye depth follows the lids
    global _HEAD_OBJS
    _HEAD_OBJS = list(parts.get('head', []))
    H = fit_head(parts.get('head', []))
    F = fit_fingers(parts.get('body', []), J)
    print(f"rig fingers    {'mesh' if F else 'spec'}  ({len(F)} chains fitted to the body's fingers)")
    core = _core_bones(J, H, F)
    by = {b.name: b for b in core}
    hd, ey = by['頭'].head, by['目.L'].head
    print(f"rig head  頭             {'mesh' if 'head_y' in H else 'spec'}  ({hd.x:+.3f}, {hd.y:+.3f}, {hd.z:+.3f})")
    print(f"rig head  目.L           {H.get('eye_src', 'mesh') if 'eye' in H else 'spec'}  ({ey.x:+.3f}, {ey.y:+.3f}, {ey.z:+.3f})")
    bones = core + _secondary_bones(parts, core)
    arm = _create_armature(bones)
    global _ATTACH_HOST, _PARENTS, _MOTION
    _MOTION = _motion_samples(arm) if PRUNE_MOTION else {}
    _PARENTS = {b.name: b.parent for b in bones}
    host = []
    for objs in parts.values():
        for o in objs:
            co = _world_verts([o])
            if not len(co):
                continue
            lab = _islands(len(co), _topology(o, co))
            for k in np.unique(lab):
                pk = co[lab == k]
                if np.linalg.norm(pk - pk.mean(0), axis=1).max() >= RIGID_ISLAND:
                    host.append(pk)
    _ATTACH_HOST = np.concatenate(host) if host else np.zeros((0, 3))
    global _SKIN
    _SKIN = None
    order = sorted(parts, key=lambda n: n not in ('body', '_proxy'))   # the skin first: garments sample it
    for part in order:
        for o in parts[part]:
            if o.parent is None:
                o.parent = arm
                o.matrix_parent_inverse = arm.matrix_world.inverted()
            _skin(o, part, bones, arm)
        if part in ('body', '_proxy') and _SKIN is None:
            _store_skin(parts[part])
    bpy.context.view_layer.update()
    return arm
