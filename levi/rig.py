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


# Round 11: the body's hands are 风堇's (levi/parts/_body_hand.py), one piece with the palm,
# so the fingers are no longer loose parts. The body stores the chains it placed from her
# bones (FINGER_CHAINS_PROP, left side, world) and a finger id per vertex (the int point
# attribute named by FINGER_ATTR_PROP: 0 palm, 1 thumb .. 5 little). fit_fingers takes the
# stored chains; without them it fits loose parts split by the finger id (then plain loose
# parts, the round-10 contract). _island_rules applies its finger rule per finger region.
FINGER_CHAINS_PROP = 'levi_fingers'
FINGER_ATTR_PROP = 'levi_finger_attr'
FINGER_SRC = {}     # how the last fit_fingers found its chains (for the build log)


def _finger_ids(obj, n):
    """(n,) finger id per vertex from the attribute named by obj[FINGER_ATTR_PROP], else None."""
    name = obj.get(FINGER_ATTR_PROP)
    attr = obj.data.attributes.get(name) if name else None
    if attr is None or attr.domain != 'POINT' or len(attr.data) != n or attr.data_type != 'INT':
        return None
    v = np.empty(n, dtype=np.int32)
    attr.data.foreach_get('value', v)
    return v.astype(np.int64)


def _part_labels(obj, co, labels):
    """Loose-part labels, each finger region (finger id > 0) of a loose part its own label."""
    fid = _finger_ids(obj, len(co))
    if fid is None or not fid.any():
        return labels
    _, out = np.unique(labels.astype(np.int64) * 8 + fid, return_inverse=True)
    return out.reshape(-1)


# Round 11 (review): the thumb's bones (親指０ metacarpal, 親指１, 親指２) are rolled about the
# thumb's chain (knuckle -> tip) by these angles (deg) from the knuckle-line palm normal, positive
# toward the index, so a turn about their X curls them like a thumb: the metacarpal swings out in
# front of the palm (palmar abduction, as the real CMC joint does), the phalanges close across
# the fingers. One roll for all three (the pad toward the index knuckle, ~75 deg) put the
# metacarpal on the palm, so the fist's curled index went 6.7 mm into the thumb's base and the
# fingertip 6.9 mm into the palm; (-30, 75, 75): the thumb rests on the index and middle
# fingers' middle phalanges, nothing passes through it, the index tip ~3 mm into the palm.
THUMB_ROLL = (-30.0, 75.0, 75.0)


def _mesh_islands(objs):
    """[(world points (n, 3))] per loose part of the meshes `objs` (finger regions split off)."""
    out = []
    for o in objs:
        co = _world_verts([o])
        if not len(co):
            continue
        lab = _part_labels(o, co, _islands(len(co), _topology(o, co)))
        out += [co[lab == k] for k in np.unique(lab)]
    return out


def _stored_fingers(body_objs):
    """{jp: [knuckle, joint, joint, tip]} a body object stores (FINGER_CHAINS_PROP), else {}."""
    for o in body_objs:
        d = o.get(FINGER_CHAINS_PROP)
        if not d:
            continue
        try:
            out = {jp: [Vector(tuple(p)) for p in d[jp]] for jp, _ in FINGER_NAMES}
        except (KeyError, TypeError, ValueError):
            continue
        if all(len(v) == 4 and all(len(p) == 3 for p in v) for v in out.values()):
            return out
    return {}


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
    mirrored) and averaged. Returns {} unless every finger is found.

    Round 11: the chains the body stores (FINGER_CHAINS_PROP: 风堇's finger bones, placed on
    the hand) come first; the loose parts are split by the finger id (_part_labels)."""
    FINGER_SRC.clear()
    stored = _stored_fingers(body_objs)
    if stored:
        FINGER_SRC['src'] = 'stored by the body'
        return stored
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
    FINGER_SRC['src'] = 'loose parts'
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
JOINT_BAND_BY_AUX = {'腕補助': (0.04, 0.06)}   # the knee uses JOINT_ALONG
# per joint (first helper's name): the helpers as (share of the lower bone's rotation,
# position along the lower bone where the skin turns with that helper alone). The band
# turns smoothly from the upper bone (at -before) through each helper to the lower bone
# (at +after). The knee has no helpers since round 10 (JOINT_ALONG).
JOINT_AUX_CHAIN = {'腕補助': ((0.35, 0.0),)}
# per helper: (full, none) lateral distance (m) from the lower bone's axis within which the
# split applies. The shoulder's upper bone 肩 also weights torso skin, which stays put.
# per helper: (band scale at the front, at the back, the front direction); unused since
# round 6 (round 5's knee: (1.4, 0.85, (0, -1, 0)))
JOINT_FRONT_BACK = {}
JOINT_REACH_BY_AUX = {'腕補助': (0.05, 0.08)}
# Round 10: the knee follows the 风堇 (Hyacine) MMD model's knee (user decision, round 10):
# a compact thigh -> shin blend with no helper bones (2 bones per vertex), about the pivot
# moved back to ~43% of the leg's depth (body.KNEE_FWD), so the bend turns over a short
# band and the knee reads as a defined corner instead of round 6-9's 17 cm "rubber hose".
# Per lower bone stem: along-limb partition (_split_joint_aux): (knots at the front, at the
# sides, at the back, forward). Knots are m along the limb from the pivot (- thigh, + shin):
# the upper end, one per helper, the lower end; between consecutive knots the share is a
# smoothstep. They are interpolated round the limb as a quadratic in the cosine of the
# direction toward `forward`, so neighbouring columns don't shear.
# Hyacine (measured on hyacine.blend: share of ひざ's turn against t / knee radius, round the
# limb): one smoothstep over about +-6 cm (+-1.7 R), the same all round, t50 ~0, 10-90%
# band 7.5-8.5 cm (2.1-2.3 R), no helpers. On our ~3x denser loft that profile (+-6.6 cm,
# variant H0) still bent over a long arc (motion_check span 0.83 squat / 0.95 seiza): her
# rings are 2.3 cm apart, so her turn lands on one ring. Narrowing the front to +-3.25 cm
# (10-90%: 4.3 cm front, 5.6 sides, 7.5 back) brings the span to Hyacine's 0.5-0.7
# (squat 0.63, seiza 0.71); the back stays wider so the hollow folds instead of creasing
# (seiza flips 52 -> 8). Pairwise Codex (both models, both orders; docs/pr/r10-knee/):
# every helperless compact variant beat round 9's knee 16-18 / 0-2 with both models (this
# one 18-0 and 18-0); within that family (+-6.6 / 5 / 4 cm, front-narrow) both models
# tied, so the spans and the hollow's metrics picked this one. A 50% helper at the pivot
# (H1) or Nahida's narrow back with the front 2 cm lower (N1) lost to the plain blend (2-16
# / 4-8, 0-18 / 0-18; astra even preferred round 9 to them; N1: 92-126 flips in seiza /
# cross_legged).
# Front +-3.0 cm: span 0.61 / 0.69 but the kneecap's skin stretched x1.91 in squat.
JOINT_ALONG = {'ひざ': ((-0.0325, 0.0325), (-0.045, 0.045), (-0.06, 0.06), (0.0, -1.0, 0.0))}
# Rounds 6-9 (replaced): a hinge partition, the share following atan2(t, d) with d 5 cm in
# front and at the sides and 4.5 cm behind, knots +-27 / +-80 deg, two helpers ひざ補助 /
# ひざ補助2 at 33 / 67%, capped 10-16 cm along the limb. Round 8's pairwise review preferred
# it over narrower bands ("pinched", "angular notch") with the pivot forward at 23% depth;
# round 10's pivot and the user's choice of the reference knee overrule that.


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


# Round 8, PMX: the shrug, the stages and 腕D as shares of the arm's SWING, without q^k. A
# plain 回転付与 share of 腕 (slerp from identity, shortest path) flips sides when 腕's turn
# passes 180 deg, so in MMD the shoulder helpers popped (idol_dance@80) although Blender's
# swing + twist drivers (_shoulder_drivers) did not. MMD can extract a swing with an IK: a
# hidden one-link IK bone `肩スイング` (child of 肩, at the shoulder joint, pointing along
# SHOULDER_SWING_REF) aims at a goal `肩スイングIK` riding 腕 at the elbow, so its turn is B,
# the swing from the reference direction to the arm (continuous everywhere except with the
# arm pointing opposite the reference, across the front of the body to her other side).
# `肩基準`, the same IK aimed at a goal fixed on 肩 at the rest elbow, holds the constant A
# (the swing to the rest arm). Products of shares of B and A, chained through hidden
# parents, give each bone's total turn B^t A^-t (identity at rest, = Blender's stages
# without their twist share):
#   肩補助親 (+s of 肩スイング) -> 肩補助 (-s of 肩基準)                           = B^s A^-s
#   肩補助 -> 肩補助Na (+s 肩基準) -> 肩補助Nb (+(t-s) 肩スイング) -> 肩補助N (-t 肩基準) = B^t A^-t
#   肩補助 -> 腕Da (+s 肩基準) -> 腕Db (-s 肩スイング) -> 腕D (+1 腕)                  = 腕 exactly
# The twist of 腕 goes to 腕D alone (the stages take none of it; 腕捩 carries the arm's
# twist down the limb). Blender keeps its drivers: the hidden parents there have no
# constraints and stay at rest, the PMX-only appends are custom properties (meta 'append',
# 'pmx_append'), and the IK bones deform nothing.
SHOULDER_PMX_SWING = True


def _shoulder_pmx_swing(b, tag, s, jp_side, en_sfx, sj, el):
    """Insert the PMX swing helpers (SHOULDER_PMX_SWING) for side `tag` into bone list b and
    re-parent the shrug, the stages and 腕D through them."""
    sfx = '.' + tag
    byname = {x.name: x for x in b}
    shrug, armd = byname['肩補助' + sfx], byname['腕D' + sfx]
    a = SHOULDER_SHRUG
    uw = Vector(SHOULDER_SWING_REF).normalized()
    ln = (el - sj).length
    J, E = _mx(sj, s), _mx(el, s)
    U = _mx(sj + uw * ln, s)
    d = (E - J).normalized() * 0.03
    # PMX local X axis of every follower: the axis of the constant swing A (reference ->
    # rest arm), perpendicular to the arm. MMD ignores local axes when it deforms; mmd_tools
    # turns them into the bone roll and emulates a 付与 share by scaling the source's Euler
    # angles in the follower's frame, which is exact for a turn about one local axis: A's
    # shares then cancel exactly at rest, and the shares of B stay close to MMD's slerp.
    n = tuple((U - J).normalized().cross((E - J).normalized()).normalized())
    before = {}      # existing bone name -> new bones to insert just before it (parents first)

    def nb(stem, en, head, tail, parent, meta, at, connect=False):
        before.setdefault(at, []).append(Bone(stem + sfx, jp_side + stem, en + en_sfx, head, tail, parent,
                                              connect=connect, deform=False, group='Arms', meta=dict(meta, helper=True)))
    # the goals ride 腕 / 肩: inserted after 腕 (before the first bone that follows it)
    after_arm = b[b.index(byname['腕' + sfx]) + 1].name
    for stem, en, goal_parent in (('肩スイング', 'ShoulderSwing', '腕' + sfx), ('肩基準', 'ShoulderRef', '肩' + sfx)):
        nb(stem, en, J, U, '肩' + sfx, {'ik_free': stem + 'IK' + sfx}, shrug.name)
        nb(stem + '先', en + 'Tip', U, U + (U - J).normalized() * 0.03, stem + sfx, {}, shrug.name, connect=True)
        nb(stem + 'IK', en + 'IK', E, E + d, goal_parent, {}, after_arm)
    sw, rf = '肩スイング' + sfx, '肩基準' + sfx
    # the hidden followers point along the reference direction (local Y), the deforming ones
    # along the arm (Blender's drivers work in 腕's frame), all with local X = n. The swing B
    # turns about an axis square to the reference, so in a frame whose Y is the reference
    # its Euler Y angle stays below 90 deg (no gimbal flip in mmd_tools' emulation) short of
    # B's own singularity; the deforming followers take only shares of A (about X) and the
    # whole of 腕, both exact.
    ref = (U - J).normalized() * JOINT_AUX_LEN
    nb('肩補助親', 'ShoulderAuxP', shrug.head, shrug.head + ref, '肩' + sfx, {'append': (sw, a), 'pmx_local_x': n},
       shrug.name)
    shrug.parent = '肩補助親' + sfx
    shrug.meta['pmx_append'] = (rf, -a)
    shrug.meta['pmx_local_x'] = n
    for st in [x for x in b if x.meta.get('shoulder', ('',))[0] == 'stage' and x.name.endswith(sfx)]:
        stem = st.name.split('.')[0]
        t = a + st.meta['follow_q'][1]
        nb(stem + 'a', st.en.replace(en_sfx, 'a' + en_sfx), st.head, st.head + ref, shrug.name,
           {'append': (rf, a), 'pmx_local_x': n}, st.name)
        nb(stem + 'b', st.en.replace(en_sfx, 'b' + en_sfx), st.head, st.head + ref, stem + 'a' + sfx,
           {'append': (sw, t - a), 'pmx_local_x': n}, st.name)
        st.parent = stem + 'b' + sfx
        st.meta['pmx_append'] = (rf, -t)
        st.meta['pmx_local_x'] = n
    nb('腕Da', 'ArmDa', armd.head, armd.head + ref, shrug.name, {'append': (rf, a), 'pmx_local_x': n}, armd.name)
    nb('腕Db', 'ArmDb', armd.head, armd.head + ref, '腕Da' + sfx, {'append': (sw, -a), 'pmx_local_x': n}, armd.name)
    armd.parent = '腕Db' + sfx
    armd.meta['pmx_append'] = ('腕' + sfx, 1.0)
    armd.meta['pmx_local_x'] = n
    out = []
    for x in b:
        out += before.get(x.name, [])
        out.append(x)
    b[:] = out


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
                if SHOULDER_PMX_SWING and SHOULDER_SWING_REF:
                    _shoulder_pmx_swing(b, tag, s, jp_side, en_sfx, sj, el)
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
        thumb_z = [palm] * 3
        if F:
            # round 11: the palm normal from the chains' knuckle line (index - little), not the
            # generic forward x hand direction (~42 deg off on Levi's hand, turned toward the
            # thigh, so fingers curled sideways); the thumb's bones rolled about the thumb by
            # THUMB_ROLL from it
            kn = F['人指'][0] - F['小指'][0]
            kn = kn - d * kn.dot(d)
            if kn.length > 1e-6:
                palm = d.cross(kn).normalized()
                td = F['親指'][3] - F['親指'][0]
                p0 = palm - td.normalized() * palm.dot(td.normalized()) if td.length > 1e-6 else Vector()
                if p0.length > 1e-6:
                    td, p0 = td.normalized(), p0.normalized()
                    thumb_z = [p0 * math.cos(math.radians(a)) + td.cross(p0) * math.sin(math.radians(a))
                               for a in THUMB_ROLL]
        for jp, en, pts in finger_chains(F, wr, d, f, hand_len, palm_end, fingers):
            parent = '手首' + sfx
            thumb = jp == '親指'
            for i in range(3):
                nm = f'{jp}{("０１２" if thumb else "１２３")[i]}'
                add(Bone(nm + sfx, jp_side + nm, f'{en}{i if thumb else i + 1}' + en_sfx, _mx(pts[i], s),
                         _mx(pts[i + 1], s), parent, connect=i > 0, r=0.014 if thumb else 0.012,
                         r_end=0.01 if thumb else 0.008, group='Fingers',
                         meta={'align_z': tuple(_mx(thumb_z[i] if thumb else palm, s)), 'finger': jp}))
                parent = nm + sfx

        hip, knee, ankle, toe = J['hip'], J['knee'], J['ankle'], J['toe']
        add(Bone('足' + sfx, jp_side + '足', 'Leg' + en_sfx, _mx(hip, s), _mx(knee, s), '下半身',
                 r=0.065, r_end=0.04, group='Legs'))
        add(Bone('ひざ' + sfx, jp_side + 'ひざ', 'Knee' + en_sfx, _mx(knee, s), _mx(ankle, s), '足' + sfx,
                 connect=True, r=0.05, r_end=0.035, group='Legs'))
        # (no knee helpers since round 10: JOINT_ALONG splits thigh / shin directly)
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
# Round 10 (Blender only): the leg IK starts its solve from the knee bent forward at least
# this much (deg; a Limit Rotation on ひざ ahead of the IK, on only while the IK is). With the
# knee pivot near the hip-ankle line (body.KNEE_FWD) the rest leg is all but straight, and
# Blender's damped solver, starting straight, cannot find the bend (seiza 18 deg instead of
# 150, jump_tuck 28 instead of 135). The IK still solves the whole chain: the rest pose and
# every reachable pose come out as before (a straight leg straightens again). 3 deg still
# failed jump_tuck; 8 deg reached all 170 core / extended poses and clip frames (every 3rd)
# but not sit_chair with the pivot 2.5 px further back; 20 deg leaves that margin. The PMX
# keeps MMD's own solver (a knee link limited to forward bends).
KNEE_IK_PREBEND = 20.0
# Round 10: the skirt drape's thigh (_thigh_spheres, _thigh_profile) runs from the hip to a
# point this far (m) in front of the knee pivot, round 9's pivot (body.KNEE_FWD 15 px, now
# 5): the skin didn't move, and the drape tables were tuned on that line. Through the new
# pivot the petticoat stretched x2.0-2.4 in cross_legged, high_kick, run, spin (round 9:
# up to x2.0-2.2 in other chains); through this point it is back to round 9's set.
DRAPE_KNEE_FWD = 10.0 / 643.0


KNEE_PREBEND_NAME = 'IK prebend'


def _knee_prebend(arm, knee, foot):
    """KNEE_IK_PREBEND: a local Limit Rotation (X >= the prebend) first in ひざ's stack, on
    while the leg's IK is: its influence is driven by the foot's (足首) IK, which an FK leg
    mutes with the knee's (MMD's IK switch, motion_poses.leg_fk), so an FK knee may
    straighten. (Reading the knee's own IK made a dependency cycle through ひざ.) Blender
    only: mmd_tools would export any Limit Rotation on the knee as its PMX IK link limit, so
    strip_blender_only removes it."""
    ik = next(c for c in foot.constraints if c.type == 'IK')
    c = knee.constraints.new('LIMIT_ROTATION')
    c.name = KNEE_PREBEND_NAME
    c.owner_space = 'LOCAL'
    c.use_limit_x = True
    c.min_x, c.max_x = math.radians(KNEE_IK_PREBEND), math.pi
    knee.constraints.move(knee.constraints.find(c.name), 0)
    fc = c.driver_add('influence')
    dr = fc.driver
    dr.type = 'SCRIPTED'
    for nm, path in (('m', 'mute'), ('w', 'influence')):
        v = dr.variables.new()
        v.name, v.type = nm, 'SINGLE_PROP'
        v.targets[0].id = arm
        v.targets[0].data_path = f'pose.bones["{foot.name}"].constraints["{ik.name}"].{path}'
    dr.expression = '(1 - m) * w'


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


def _grid_points(pts, cell):
    """The first point (in order) in each cell of a cell-sized grid: an even sample of the
    cloth whatever each mesh's vertex density (see DRAPE_GRID)."""
    if cell <= 0 or not len(pts):
        return pts
    _, first = np.unique(np.floor(pts / cell).astype(np.int64), axis=0, return_index=True)
    return pts[np.sort(first)]


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
# Blender only: share of the neck's (首) forward / backward tilt that 髪追従 turns back, so
# the curtain keeps hanging when she nods or looks up. Hanging from the top of the neck,
# a 2.5 deg tilt swung the lock ends 50 cm below by 2 cm, into her back and the skirt.
HAIR_NECK_HANG = 0.85
# Blender only: share of the torso's BACKWARD pitch (上半身 + 上半身2) that 髪追従 turns
# back. Arched back, her back turns away from the hair, which hangs straight from the
# head; carried with the torso, the curtain swung its ends 11 cm forward into the skirt
# (reach_up_back). Forward bends are HAIR_PITCH_GRAVITY's (one-sided since round 7).
HAIR_ARCH_HANG = 1.0
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
# .72, 1 for 4 segments). On the back such a profile put the locks 3 cm into her. (Round
# 8: an exponent of 0.5 hung them straighter in forward_bend's side view, but swung their
# curled ends out sideways in its front view and in twist_bend: Codex preferred 0.8.)
HAIR_OUTER_ANGLE = 55.0
HAIR_PITCH_OUTER = (1.0, 0.8)   # (total, exponent)
# Round 8: (share, z from, z to): a segment whose rest middle lies below the waist turns
# back at least `share` x smoothstep(z from -> z to) of the forward pitch in all (see
# _hair_pitch_gravity). None: the index profiles above alone (round 7).
HAIR_PITCH_HANG = (1.0, L['waist_z'] + 0.06, L['hip_z'] + 0.02)
# Round 8, Blender only: (bone, share, z from, z to): the hair lying on the hips and the
# skirt takes `share` x smoothstep(z from -> z to) of that bone's pitch (both ways), so it
# stays on the skirt as the hips tip (forward_bend tips them 10 deg: the skirt's back rose
# 2 cm into the lock ends, which the capped collision pushes left half inside). The PMX
# has no second 付与 source per bone: there MMD physics lays the hair on the skirt.
HAIR_PELVIS_FOLLOW = ('下半身', 1.0, L['waist_z'] + 0.02, L['hip_z'] - 0.02)
HAIR_LOCK_SEG = ((0.4, 5), (0.25, 4), (0.0, 3))   # lock length (m) -> chain segments
HAIR_PITCH_SOURCES = ('上半身', '上半身2')
# PMX pitch-only helpers. A 回転付与 copies the source's whole turn, so the round-6 export
# (a negative 付与 of 上半身) also countered her twist and side bend when MMD physics is off.
# HAIR_PITCH_HELPER is a hidden bone from 上半身's head to the neck base, beside the torso
# (parent: 上半身's parent), turned by a one-link IK that may only turn it about X toward a
# goal on 上半身2's end: it takes the torso's forward pitch alone (the IK limit allows 0 to
# 170 deg; a twist does not move the goal, a side bend moves it off the IK's plane). The
# hair segments append minus their pitch-gravity share of it. HAIR_ARCH_HELPER does the
# same for a backward pitch (limit -170 to 0 deg), and HAIR_ARCH_BONE (between 首 and
# 髪追従) appends -HAIR_ARCH_HANG of it, so an arched-back torso leaves the hair hanging.
# Blender reads the torso bones directly (_pitch_counter); the helpers move there too but
# nothing deforms with them. With MMD physics on, the hair bodies override all of this.
HAIR_PITCH_HELPER = '髪ピッチ'
HAIR_ARCH_HELPER = '髪反り'
HAIR_ARCH_BONE = '髪反り追従'
HAIR_PITCH_REACH = 2.0      # m: how far out along 上半身2 the helpers' IK goals lie
# back hair is weighted to 頭 fully above the eyes, fading to the chains by just under
# the choker: below that it hangs at the shoulders, which a head turn must not sweep it
# into (at 0.6 follow a 45 deg turn pushed the curtain 2.5 cm into a closed shoulder)
HAIR_HEAD_FADE = (L['choker_z'] - 0.05, L['eye_z'] + 0.03)
SIDE_LOCKS_ON_HEAD = True   # face-framing side locks hang from 頭 itself instead of 髪追従
# hair_front object name prefix (+ _L / _R) -> side-lock chain (Japanese, English name)
SIDE_HAIR_FAMILIES = (('hair_cheek', '横髪', 'SideHair'), ('hair_lock', '横髪長', 'SideHairLong'),
                      ('hair_curl', '横髪巻', 'SideHairCurl'), ('hair_curtain', '横髪奥', 'SideHairBack'))
# Round 8: families whose chain starts higher than eye_z - 2 cm (m), and families weighted
# along their chain (_side_chain_weights: 頭 at the root, handing over to the chain over its
# first bone) instead of by the bones' envelopes. The cheek wisps hang from the temple to
# just below the eyes: a two-bone chain from the cheekbone down, the roots on the head.
SIDE_HAIR_TOP = {'hair_cheek': L['eye_z'] + 0.03}
SIDE_HAIR_CHAIN_WEIGHTS = ('hair_cheek',)
SIDE_HAIR_ROOT_BLEND = 1.0   # chain units over which 頭 hands over to such a chain
FOLLOW_FRONT = 1.0    # total share of the thighs' rotation a skirt chain takes at centre front
FOLLOW_BACK = 0.5     # ... and at centre back (a leg swung back still pushes the back skirt)
# how a chain's thigh share is spread over its joints (root, joint 1, joint 2...); the
# chain's total turn at the hem is the sum
SKIRT_SEG_FOLLOW = (0.65, 0.1)
SKIRT_LEG_SHARPNESS = 1.0   # 1 = the even split (1 + sin a) / 2; 1.5-2 sheared the petticoat (x2.0-2.4 in walk)
SKIRT_SECTORS = 16          # skirt chains around the body
SKIRT_SEGMENTS = 3          # bones per skirt chain
# The chains hang from just below the waistband (this share of the way from hip_z up to
# waist_z), the pivot cloth really turns about: a thigh raised to the horizontal stands
# ~7 cm above the skirt's hip-level bell in front, which no turn about a hip-level root
# (round 6) can lift the cloth over, so the drape lifted the whole panel past 110 deg
# instead and the cloth in front of the hip stayed inside the thigh.
# 0.6 puts the roots 9 mm above the 上半身 / 下半身 split (_core_bones' z_pivot), where the
# skin is still almost all 下半身, so a torso bend barely moves the skin there; at 0.5 (on
# the split) the drape needs ~10 deg more lift for the same clearance, which stretched the
# cloth just below the roots to x2.15 (high_kick).
SKIRT_ROOT_RISE = 0.6
SKIRT_ROOT_Z = L['hip_z'] + SKIRT_ROOT_RISE * (L['waist_z'] - L['hip_z'])
# Skirt drape (Blender): each chain joint turns forward / back only as far as the cloth must
# to clear the thighs, and hangs back toward its rest direction otherwise (_skirt_drape).
SKIRT_DRAPE = True
DRAPE_PHI = tuple(range(-70, 141, 5))   # deg of thigh pitch (forward +) the drape table samples
DRAPE_CLEAR = 0.016         # m kept between the innermost cloth layer and the thigh surface
DRAPE_ROOT_MAX = 110.0      # deg the root segment may turn (seated, the front panel lies on the lap)
DRAPE_SPHERE_STEP = 0.015   # m between the spheres that stand in for the thigh (_thigh_spheres)
# ... which run on past the knee along a straight shin to this many thigh lengths (radius
# DRAPE_SHIN_R there): a kicked leg is straight, and the petticoat tiers below the skirt
# hem reach past the knee when the skirt lies along the thigh (the shoe came through them)
DRAPE_LEG_EXT = 1.45
DRAPE_SHIN_R = 0.05
# (m from the hip joint along the thigh, the thigh's skin weight there): measured on the
# round-6 body (足 vs 下半身, mean round the thigh); the obstacle near the groin moves as
# much as the blended skin does. Round 11 (风堇's continuous pelvis): re-measured as
# 足 + HIP_AUX x 足補助 round the thigh, 0.49 / 0.52 / 0.70 / 0.84 / 0.97 at 0 / 5 / 10 / 14 /
# 20 cm (the round-10 body 0.54 / 0.63 / 0.69 / 0.91 / 1.0): within 0.07 of round 10, so the
# table stays (moved by the difference, it raised the run clip's skirt pop 69 -> 83 mm)
DRAPE_SKIN_W = ((0.0, 0.5), (0.05, 0.6), (0.10, 0.75), (0.14, 0.97), (0.17, 1.0))
DRAPE_RES = 2.0             # deg: resolution of the clearance search (round 7: 1)
DRAPE_SLACK = 0.004         # m: where nothing clears, the least turn within this of the best depth
DRAPE_SMOOTH = 8            # [1 2 1] passes over the pitch samples (~11 deg; round 7: 5, which left a 6 mm pop rising from the seat)
# deg: most each joint below the root (the last value repeats) bends against the segment
# above it (30 stretched x2.1 at the middle joint; round 8 tried 36 at the hem joint, which
# stretched the petticoat between the front chains to x2.9 in run_r)
DRAPE_BEND = (24.0,)
# deg a segment may lift above the one over it. Round 11 (integration review 3): 7 (rounds
# 7-10: 10). The ring cap lifts a neighbour's hem segment toward a raised chain's and left its
# middle segment up to 10 deg lower: a fold at the lower joint, which the petticoat tiers
# straddle (seated, the inner tier's hem x1.94 between chains 9 and 10 in sit_chair); within
# 7 deg the middle segment comes along (x1.76 with DRAPE_STRAIN 0.26 and TIER_FIELD)
DRAPE_UP = 7.0
# Round 8 (_drape_gather): the cloth beside a lifted panel is pulled along. Round 7 lifted
# every neighbour by the panel's turn less 13 / 11 / 9 deg per chain step (a cone round the
# ring), which swung the whole skirt and petticoat into a bowl over a raised thigh. Now
# each chain may turn round the body toward the lifted cloth (yaw, which gathers the hem
# forward at its own height) and lift only as much as the ring's stretch needs, at the
# least height: a coordinate descent over yaws x root lifts per thigh pitch. (Off: each
# chain takes its own clearance only, then DRAPE_RING_CAP.)
DRAPE_GATHER = True
# deg per chain step (root, middle, hem) neighbouring chains may differ once every table
# is shaped (a cone that only lifts, applied last; round 7's was 13 / 11 / 9)
DRAPE_RING_CAP = (18.0, 16.0, 14.0)
DRAPE_RING_CAP_MIN = 0.35               # least share of the cap a narrow step keeps
# Round 11 (integration review 3): ((deg from, deg to), share): below `from` deg of thigh
# pitch the cap is this share of DRAPE_RING_CAP, the full cap again by `to` (smoothstep).
# At walking pitches the cone was what set the front's shape: the chain over the forward
# thigh lifted its hem 35-38 deg and each neighbour toward the other side hung the full 11-12
# deg step lower, so the petticoat's front hem stretched x1.81 in walk (x1.58 curtsy, x1.64
# walk clip) and the skirt's x1.55. With the narrower steps the lift spreads one chain
# further round the front (walk x1.61, curtsy x1.40, skirt x1.49 / 1.30, with the other
# round-11 settings); above 75 deg (seated, kicks, the tuck
# jump) the cap is as before, where a narrower cone lifted the whole ring into a bowl
# (round 8's pairwise review)
DRAPE_RING_CAP_PITCH = ((45.0, 75.0), 0.55)
DRAPE_YAW_GRID = (-30.0, -15.0, 0.0, 15.0, 30.0)   # deg: yaws at which the clearance is tabulated
DRAPE_YAW_MAX = 30.0        # deg a chain may turn round the body ...
DRAPE_YAW_BACK = (60.0, 120.0)   # ... fading in from straight back over these skirt angles (deg)
DRAPE_YAW_STEP = 2.0        # deg: the gather's yaw candidates ...
DRAPE_LIFT_STEP = 3.0       # ... and root lift candidates
DRAPE_LIFT_SHAPE = (1.0, 0.85, 0.7)   # share of a pulled chain's root lift its joints take
# ring strain free of cost (see DRAPE_TAUT). Round 11 (integration review 3): 0.26 (rounds
# 8-10: 0.3): measured against the innermost cloth, which is now the petticoat's inner
# tier hem, 0.3 let the gather leave the side chains of a seated pose far apart
DRAPE_STRAIN = 0.26
# The ring is measured against the innermost cloth. DRAPE_TAUT: the joints' distance to
# the next chain's over the innermost layer's spacing there, less 1 (a sector whose
# inner layer lies much closer than its joints starts taut, so the gather keeps its
# chains together and lifts them sooner); else only the growth of that distance over the
# spacing (which pulled the back forward into her when seated and was rated less natural
# in a pairwise review)
DRAPE_TAUT = True
# weights: ring strain past DRAPE_STRAIN (squared); how far the joints move (a share of
# the chain's length: rising in full, sideways and down by DRAPE_MOVE_FREE, toward the
# skirt's axis, into her, DRAPE_INWARD more); the yaw and its difference to the
# neighbours' and to the previous pitch sample's (and the turns'), as squared shares of
# DRAPE_YAW_MAX
DRAPE_GATHER_W = (2.0, 0.5, 0.05, 0.1, 0.2)
DRAPE_MOVE_FREE = 0.25
DRAPE_INWARD = 2.0
DRAPE_SWEEPS = 16           # coordinate descent sweeps (alternating direction)
DRAPE_PTS = 300             # cloth points per chain sector the clearance tests (without DRAPE_BIN)
# Round 11: the clearance tests the innermost cloth point of each DRAPE_BIN cell (deg round
# the chain x m of height) of the sector, over the skirt and the petticoat's full meshes,
# and the rest ring's innermost cloth (DRAPE_INNER) is read on the full meshes too (the
# inner tiers' hems set the ring strain: x2.29 -> x2.26 at the inner tier in cross_legged).
# The DRAPE_PTS points taken evenly by index were a different few hundred whenever a point
# entered or left the sector (the mean centre cy moves with any cloth edit), and the
# petticoat grid (DRAPE_GRID, first object first) dropped the inner tiers where they lie
# within a cell of the outer one: one skirt edit under the right hand changed the front
# chains' clearance by 20-40 deg and the inner tiers went 2.8 cm into the raised thigh in
# the run clip.
DRAPE_BIN = (2.0, 0.01)
DRAPE_INNER = 10.0          # percentile of the sector's radius taken as its innermost cloth (rest ring)
# The chains and the drape see the petticoat's cloth thinned to one point per DRAPE_GRID
# cell (_grid_points), so its share of the sector samples (DRAPE_PTS, taken evenly by
# index), of the innermost-cloth percentiles (DRAPE_INNER) and of the chains' fit (band
# centroids) does not grow with its vertex density (round 11: the round-10 petticoat with
# 2.5x the columns, same shape, lowered the seated front drape by ~10 cm and pushed the
# petticoat 2.4-3.2 cm into the thighs in sit_chair / run). 5 mm leaves round 11's
# petticoat (27k vertices) about as many points as round 10's had (12.9k, all of them);
# the skirt's own points are not thinned, so its share stays as it was.
DRAPE_GRID = 0.005
# Early lift: below DRAPE_EARLY_MAX deg of pitch a segment turns at least DRAPE_EARLY x the
# pitch x its steepest later turn per deg (its table made star-shaped from rest), so a
# stride starts the cloth moving with the thigh instead of only past the clearance
# angle; when the legs scissor (walk, run) the lift handed from one thigh to the other
# no longer dips to nothing for a frame (the pops of round 6).
DRAPE_EARLY = 0.5
DRAPE_EARLY_MAX = 70.0
DRAPE_COMBINE_EPS = 0.3     # rad: softness of the smooth max of both thighs' lifts (_drape_combine_expr)
DRAPE_SHARE_AT = 60.0       # deg of thigh pitch at which the PMX's linear 回転付与 share is read
DRAPE_SHARE_NORM = 0.5      # PMX: both thighs' shares scaled by (max / sum) ** this (_drape_share)
# Abduction: a second table with the thigh swung out this far (deg, seen from above); the
# drivers blend to it as the raised thigh turns outward (cross-legged, a side step), where
# the side-front cloth, not the front, lies over the thigh. Blender only.
DRAPE_PSI = 45.0
# Seat (round 8, Blender only): seated (both thighs raised past SEAT_PHI), the cloth behind
# and beside her does not hang through the seat or the floor: the joints below the roots
# swing out from the body (about the horizontal axis across each chain) just far enough to
# keep the joints SEAT_CLEAR above the seat, SEAT_DROP below the hip joints (the bottom of
# the buttocks), each joint at most SEAT_BEND against the segment above; the swing fades
# out toward the front (SEAT_ANG, deg from straight back), where the cloth lies on the lap.
SEAT = True
SEAT_PHI = (45.0, 80.0)
SEAT_DROP = 0.16
SEAT_CLEAR = 0.0
SEAT_BEND = 18.0
SEAT_ANG = (70.0, 140.0)
# ... on a chair (the shins hang: FLOOR_SHIN, the share of the shin's length its knee stands
# above its ankle, 1 when vertical) only the back lies on the seat (SEAT_ANG_CHAIR) and the
# sides hang beside the hips; on the floor (shins level: seiza, cross-legged, legs out) the
# sides spread round her too.
SEAT_ANG_CHAIR = (30.0, 130.0)
FLOOR_SHIN = (0.3, 0.65)
# ... and only with a foot on the ground: an ankle at most GROUNDED (m, eased) above 全ての親
# (a tuck jump raises both thighs too, but nothing is under her)
GROUNDED = (0.28, 0.42)


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


# Round 11: the drape's thigh is round 10's (r11/base). 风堇's pelvis is fuller round the hip
# joints (the profile's 90th percentile +8 / +11 / +7 mm at t = 0 / 0.1 / 0.2, then 1-4 mm
# thinner down the thigh) and her knee joint sits 5 mm further in; measured on the new body they
# re-tuned the drape tables and the run clip's skirt pop (frame 16) rose from 68.5 to 89 mm (80
# with round 10's profile alone, 86 with its knee alone). With both it is 65.6 mm, the
# petticoat's stretch as round 10's (x2.30) and the cloth's clearance unchanged. The profile is
# round 10's measurement (radius at t = 0, 0.1 .. 1 along hip -> knee); None measures the body.
DRAPE_THIGH_PROFILE = (0.0722, 0.0628, 0.0603, 0.0582, 0.0554, 0.0546, 0.0537, 0.0525, 0.0489, 0.0484, 0.0576)
DRAPE_KNEE_OUT = 0.0049     # m: the drape's knee this far out of the knee joint (round 10's knee)


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
    if DRAPE_THIGH_PROFILE is not None:
        rs = np.array(DRAPE_THIGH_PROFILE, dtype=float)
    return ts, rs


def _rot_x(p, c, a):
    """Points p turned about the world X axis through c by `a` rad, forward-positive
    (a vector hanging down swings toward -Y, the way she faces)."""
    ca, sa = math.cos(a), math.sin(a)
    q = p - c
    return np.stack([q[..., 0], q[..., 1] * ca + q[..., 2] * sa, -q[..., 1] * sa + q[..., 2] * ca], -1) + c


def _drape_share(tabs, tag, i):
    """PMX: the share of thigh `tag`'s rotation (回転付与) that skirt follow bone i takes,
    the drape's linear part at DRAPE_SHARE_AT. MMD adds the two thighs' appended turns,
    where Blender takes about the larger (_drape_combine_expr): each thigh's absolute
    turn is scaled by (max / sum) ** DRAPE_SHARE_NORM of the two at that pitch, so both
    thighs raised together (seated) lift the cloth by sqrt(max x sum) at 0.5, not by the
    sum of their tables (up to ~1.7x the drape), while one thigh alone keeps most of its
    own (MMD physics, colliding with the legs, does the rest)."""
    xs = np.array(DRAPE_PHI, dtype=float)

    def absolute(j):
        if j < 0:
            return 0.0
        T = {t: float(np.interp(DRAPE_SHARE_AT, xs, tabs[t][j])) for t in 'LR'}
        tot = abs(T['L']) + abs(T['R'])
        f = (max(abs(T['L']), abs(T['R'])) / tot) ** DRAPE_SHARE_NORM if tot > 1e-9 else 1.0
        return T[tag] * f
    return (absolute(i) - absolute(i - 1)) / math.radians(DRAPE_SHARE_AT)


def _thigh_spheres(hip, knee, prof, phi, psi=0.0, s=1.0):
    """The thigh pitched forward by phi (rad; its hip -> knee line seen from the side) and
    swung out so that, seen from above, it points psi (rad) outward from straight ahead
    (side s: +1 left), as a chain of spheres (centres (S, 3), radii (S,) widened by
    DRAPE_CLEAR), every DRAPE_SPHERE_STEP from the hip joint on past the knee along a
    straight shin (DRAPE_LEG_EXT, DRAPE_SHIN_R). Each
    centre moves as the skinned surface around it does: linear blend skinning between
    the pelvis (at rest) and the turned thigh, by the thigh's skin weight at that
    distance from the hip (DRAPE_SKIN_W). So near the groin, where the skin is half
    pelvis, the obstacle rises only part of the way, as the skin does, and the cloth
    there is not lifted over a rigid thigh that isn't there."""
    ax = knee - hip
    ln = float(np.linalg.norm(ax))
    ts = np.arange(0.0, DRAPE_LEG_EXT * ln + 1e-9, DRAPE_SPHERE_STEP)
    c0 = hip + np.outer(ts / ln, ax)
    d = _rot_x(ax / ln, np.zeros(3), phi)
    if psi:
        d = d + np.array([s * max(-d[1], 0.0) * math.tan(psi), 0.0, 0.0])
        d = d / np.linalg.norm(d)
    w = np.interp(ts, *zip(*DRAPE_SKIN_W))
    c = (1.0 - w)[:, None] * c0 + w[:, None] * (hip + np.outer(ts, d))
    r = np.interp(np.clip(ts / ln, 0.0, 1.0), prof[0], prof[1])
    r = np.where(ts > ln, np.minimum(r, DRAPE_SHIN_R), r) + DRAPE_CLEAR
    return c, r


def _thigh_depth(q, spheres):
    """How far points q (..., 3) lie inside the thigh's spheres (_thigh_spheres; <= 0 outside)."""
    c, r = spheres
    d = np.linalg.norm(q[..., None, :] - c, axis=-1)
    return (r - d).max(-1)


def _smooth_above(tab, phis, i0):
    """tab (n, P) smoothed over the pitch samples (_smooth_pitch) plus the smoothed (dilated)
    shortfall wherever smoothing took it below itself, so the curve stays on or above the
    table, then monotone away from rest on both sides (as _skirt_drape shapes its tables)."""
    sgn = np.sign(phis)[None]
    sm = _smooth_pitch(tab, i0)
    short = np.maximum(sgn * (tab - sm), 0.0)
    wide = np.zeros_like(short)
    for half in (sgn > 0, sgn < 0):
        sh = short * half
        w = sh.copy()
        for o in range(1, DRAPE_SMOOTH + 1):
            w[:, o:] = np.maximum(w[:, o:], sh[:, :-o])
            w[:, :-o] = np.maximum(w[:, :-o], sh[:, o:])
        wide += w * half
    return _monotone(sm + sgn * _smooth_pitch(wide, i0), i0)


def _monotone(tab, i0):
    """tab (n, P) made monotone away from rest (sample i0) on both sides."""
    out = tab.copy()
    for pi in range(i0 + 1, out.shape[1]):
        out[:, pi] = np.maximum(out[:, pi], out[:, pi - 1])
    for pi in range(i0 - 1, -1, -1):
        out[:, pi] = np.minimum(out[:, pi], out[:, pi + 1])
    return out


def _smooth_pitch(tab, i0):
    """DRAPE_SMOOTH [1 2 1] passes along the pitch samples (axis 1), held at nought at
    rest (sample i0); the end samples keep their values."""
    for _ in range(DRAPE_SMOOTH):
        sm = tab.copy()
        sm[:, 1:-1] = 0.25 * tab[:, :-2] + 0.5 * tab[:, 1:-1] + 0.25 * tab[:, 2:]
        sm[:, i0] = 0.0
        tab = sm
    return tab


def _yaw(p, c, psi):
    """Points p turned about the vertical through c by psi (rad) in the skirt's angle
    sense: + carries a chain toward larger skirt angles (from behind toward her left,
    i.e. clockwise seen from above)."""
    ca, sa = math.cos(psi), math.sin(psi)
    q = p - c
    return np.stack([q[..., 0] * ca + q[..., 1] * sa, -q[..., 0] * sa + q[..., 1] * ca, q[..., 2]], -1) + c


def _drape_bend(j):
    """Most joint j (>= 1) of a skirt chain may bend against the segment above (rad)."""
    b = DRAPE_BEND if isinstance(DRAPE_BEND, (tuple, list)) else (DRAPE_BEND,)
    return math.radians(b[min(j - 1, len(b) - 1)])


def _drape_clear(sel, seg, free, J, sph, sg, root_max):
    """The least forward (sg +1) / backward (sg -1) turn of each segment of a chain with
    rest joints J (n + 1, 3), root first, that keeps the cloth points `sel` of its
    sector (segment index `seg`; only those `free`, i.e. not inside the thigh at rest)
    off the thigh's spheres `sph` (_thigh_spheres). The root may turn up to root_max,
    each joint below within DRAPE_BEND of the segment above; where nothing clears, the
    least turn within DRAPE_SLACK of the best depth. Then no zigzag (DRAPE_UP).
    Returns the absolute signed turns (n,)."""
    n = len(J) - 1
    up = math.radians(DRAPE_UP)
    res = math.radians(DRAPE_RES)
    A = []
    q = sel.copy()
    Jc = J.copy()
    for j in range(n):
        prev = A[-1] if A else 0.0
        bend = _drape_bend(j) if j else 0.0
        lo, hi = (0.0, root_max) if j == 0 else (max(0.0, sg * prev - bend), sg * prev + bend)
        cand = sg * np.arange(lo, hi + 1e-9, res)
        m = (seg == j) & free
        if not m.any():
            best = float(cand[0])
        else:
            P = q[m]
            # every candidate at once: (G, M, 3)
            g = (cand - prev)[:, None]
            Q = P - Jc[j]
            ca, sa = np.cos(g), np.sin(g)
            R = np.stack([np.broadcast_to(Q[None, :, 0], (len(cand), len(Q))),
                          Q[None, :, 1] * ca + Q[None, :, 2] * sa,
                          -Q[None, :, 1] * sa + Q[None, :, 2] * ca], -1) + Jc[j]
            dep = _thigh_depth(R, sph).max(1)
            # the smallest turn that clears, or else that comes within DRAPE_SLACK of the
            # least depth any turn reaches (cloth turning barely helps must not swing the
            # panel to the limit)
            ok = np.nonzero(dep <= max(0.0, dep.min() + DRAPE_SLACK))[0]
            best = float(cand[ok[0]])
        A.append(best)
        turn = best - prev
        below = seg >= j
        q[below] = _rot_x(q[below], Jc[j], turn)
        Jc[j + 1:] = _rot_x(Jc[j + 1:], Jc[j], turn)
    # no zigzag: a segment that must lift more than the one above it lifts that one too
    # (within DRAPE_UP), so the cloth curves over the thigh in one direction (blended
    # skinning cuts a zigzag's corners into the leg)
    for j in range(n - 2, -1, -1):
        A[j] = sg * max(sg * A[j], sg * A[j + 1] - up)
    return np.array(A)


def _chain_fk(J, A, psi):
    """Joints 1..n (..., n, 3) of a chain with rest joints J (n + 1, 3) whose segments
    turn forward by the absolute angles A (..., n) about the world X axis through their
    joints, the whole chain then turned by psi (...,) about the vertical through its
    root (_yaw): the drape bones' order (the yaw bone is the pitch bones' parent)."""
    n = len(J) - 1
    shape = A.shape[:-1]
    P = np.broadcast_to(J, shape + J.shape).copy()
    prev = np.zeros(shape)
    for j in range(n):
        g = A[..., j] - prev
        ca, sa = np.cos(g)[..., None], np.sin(g)[..., None]
        Q = P[..., j + 1:, :] - P[..., j:j + 1, :]
        P[..., j + 1:, 1], P[..., j + 1:, 2] = (Q[..., 1] * ca + Q[..., 2] * sa + P[..., j:j + 1, 1],
                                                -Q[..., 1] * sa + Q[..., 2] * ca + P[..., j:j + 1, 2])
        prev = A[..., j]
    ca, sa = np.cos(psi)[..., None], np.sin(psi)[..., None]
    Q = P[..., 1:, :] - J[0]
    out = np.stack([Q[..., 0] * ca + Q[..., 1] * sa, -Q[..., 0] * sa + Q[..., 1] * ca, Q[..., 2]], -1) + J[0]
    return out


def _chain_shape(Pm, e, sg):
    """Absolute signed turns (..., n) of a chain whose segments need at least Pm (..., n,
    magnitudes, _drape_clear) and are lifted by e (...,) more at the root, less down the
    chain (DRAPE_LIFT_SHAPE: pulled up by the cloth beside it, the hem still hangs), kept
    within DRAPE_BEND of the segment above."""
    n = Pm.shape[-1]
    shape = np.array([DRAPE_LIFT_SHAPE[min(j, len(DRAPE_LIFT_SHAPE) - 1)] for j in range(n)])
    A = np.maximum(Pm, e[..., None] * shape)
    for j in range(1, n):
        A[..., j] = np.maximum(A[..., j], A[..., j - 1] - _drape_bend(j))
    return sg * A


def _drape_gather(Pm, J, rest, sg, init, cy=0.0):
    """One thigh at one pitch: each chain's yaw (gathered round toward the lifted cloth,
    _yaw) and extra root lift, chosen so that the ring of cloth between neighbouring
    chains is not stretched past DRAPE_STRAIN, moving the cloth as little as it can
    (raising it most of all: cloth that need not lift hangs as at rest), with little yaw,
    and close to the previous pitch sample's drape. Pm: {chain: (len(DRAPE_YAW_GRID), n)}
    the clearance turns (magnitudes) at each yaw; J: rest joints (K, n + 1, 3); rest:
    (the rest distances (K, n) of each chain's joints to the next chain's, the scale the
    strain is measured against (the innermost cloth's spacing there; inf across a gap));
    init: the previous sample's (A, psi) (None at rest). The strain is the joints' change
    of distance over that scale. Coordinate descent over a grid of yaws x root lifts.
    Returns (A (K, n) signed turns, psi (K,) rad, (A, psi))."""
    K, n = J.shape[0], J.shape[1] - 1
    yg = np.radians(np.array(DRAPE_YAW_GRID, dtype=float))
    ys = np.radians(np.arange(-DRAPE_YAW_MAX, DRAPE_YAW_MAX + 1e-9, DRAPE_YAW_STEP))
    es = np.radians(np.arange(0.0, DRAPE_ROOT_MAX + 1e-9, DRAPE_LIFT_STEP))
    Y, E = np.meshgrid(ys, es, indexing='ij')             # (NY, NE)
    w_strain, w_move, w_yaw, w_ring, w_step = DRAPE_GATHER_W
    seglen = np.linalg.norm(np.diff(J, axis=1), axis=2)  # (K, n)
    cand = []
    # between the tabulated yaws the larger of the two bracketing clearances (the depth is
    # not linear in the yaw: interpolating could put the cloth into the thigh)
    hi = np.clip(np.searchsorted(yg, ys - 1e-9), 1, len(yg) - 1)
    for k in range(K):
        pm = np.maximum(Pm[k][hi - 1], Pm[k][hi])                                # (NY, n)
        A = _chain_shape(np.broadcast_to(pm[:, None, :], Y.shape + (n,)), E, sg)
        X = _chain_fk(J[k], A, Y)                            # (NY, NE, n, 3)
        dz = X[..., 2] - J[k][None, None, 1:, 2]
        dh = np.linalg.norm(X[..., :2] - J[k][None, None, 1:, :2], axis=-1)
        # how far the joints move (seglen-weighted, over the chain's own length): rising
        # counts in full, sideways and down by DRAPE_MOVE_FREE
        # ... and toward the skirt's axis, into her, by DRAPE_INWARD (the back pulled forward
        # by the front went into the buttocks when seated)
        r0 = np.hypot(J[k][1:, 0], J[k][1:, 1] - cy)
        inward = np.maximum(r0 - np.hypot(X[..., 0], X[..., 1] - cy), 0.0)
        move = ((np.maximum(dz, 0.0) + DRAPE_MOVE_FREE * (dh + np.maximum(-dz, 0.0)) + DRAPE_INWARD * inward)
                * seglen[k]).sum(-1)
        move = move / (seglen[k] ** 2).sum()
        # the back keeps its place round the body (DRAPE_YAW_BACK): with both thighs raised
        # each one's gather turned the back chains apart, a fan that tore the back open
        a_k = abs(math.degrees(math.atan2(J[k][0, 0], J[k][0, 1] - cy)))
        ymax = math.radians(DRAPE_YAW_MAX) * _smoothstep(DRAPE_YAW_BACK[0], DRAPE_YAW_BACK[1], a_k)
        move = move + 1e3 * (np.abs(Y) > ymax + 1e-9)
        cand.append((A.reshape(-1, n), X.reshape(-1, n, 3), move.reshape(-1), Y.reshape(-1)))
    rest0, scale = rest
    if init is None:
        init = (np.zeros((K, n)), np.zeros(K))
    A_prev, psi_prev = init
    # start each chain from the candidate nearest the previous sample's drape
    st = np.array([int(np.argmin(((cand[k][0] - A_prev[k][None]) ** 2).sum(-1) + (cand[k][3] - psi_prev[k]) ** 2))
                   for k in range(K)])

    def ring(Xa, Xb, k):
        d = np.linalg.norm(Xa - Xb, axis=-1)
        s = d / scale[k] - 1.0 if DRAPE_TAUT else (d - rest0[k]) / scale[k]
        return (np.maximum(s - DRAPE_STRAIN, 0.0) ** 2).sum(-1)

    ref = math.radians(DRAPE_YAW_MAX)
    for sweep in range(DRAPE_SWEEPS):
        order = range(K) if sweep % 2 == 0 else range(K - 1, -1, -1)
        changed = False
        for k in order:
            A, X, move, psi = cand[k]
            kp, kn = (k - 1) % K, (k + 1) % K
            Xp, Xn = cand[kp][1][st[kp]], cand[kn][1][st[kn]]
            Ap, pp = A_prev[k], psi_prev[k]
            en = (w_strain * (ring(X, Xp[None], kp) + ring(X, Xn[None], k))
                  + w_move * move + w_yaw * (psi / ref) ** 2
                  + w_ring * (((psi - cand[kp][3][st[kp]]) / ref) ** 2 + ((psi - cand[kn][3][st[kn]]) / ref) ** 2)
                  + w_step * (((psi - pp) / ref) ** 2 + (((A - Ap[None]) / ref) ** 2).mean(-1)))
            b = int(np.argmin(en))
            if en[b] < en[st[k]] - 1e-12:
                st[k] = b
                changed = True
        if not changed:
            break
    A = np.stack([cand[k][0][st[k]] for k in range(K)])
    psi = np.array([cand[k][3][st[k]] for k in range(K)])
    return A, psi, (A, psi)


def _skirt_drape(chains, pts, cy, hip, knee, body, inner=None):
    """Drape table of the skirt chains: {chain k: {'L'|'R': (nseg, len(DRAPE_PHI)) absolute
    forward turn (rad) of each segment, 'yL'|'yR': (len(DRAPE_PHI),) the chain's yaw
    (rad, _yaw)}} for that thigh pitched alone by each DRAPE_PHI, and under 'La' / 'Ra'
    (and 'yLa' / 'yRa') the same for the thigh also swung out DRAPE_PSI (seen from above,
    see _thigh_spheres; backward pitches as 'L' / 'R').

    Each segment, root first, needs the smallest turn toward the thigh's swing (forward
    for a raised thigh, back for one swung back, never the other way) that keeps the
    cloth of its sector (skirt and petticoat, the innermost layer counts) DRAPE_CLEAR off
    the swung thigh (_drape_clear), tabulated for the chain also turned round the body by
    each DRAPE_YAW_GRID. Cloth already inside the thigh at rest is ignored. `pts` are the
    points the chains were fitted to; `inner` (the full skirt and petticoat meshes), when
    given, is the cloth the clearance and the rest ring read (DRAPE_BIN).

    The cloth beside a lifted panel is pulled along (round 8, _drape_gather): rather than
    lift it too (round 7's cone round the ring swung the whole skirt into a bowl), each
    chain may turn round toward the lifted cloth (yaw: the side cloth gathers forward at
    the same height) and lift only as far as its neighbours' pull needs, preferring low
    and little yaw. The chains over the thigh lie on it, the sides and back keep hanging,
    and the cloth between the thighs hangs into the gap where nothing lifts it.

    Each table is then made monotone in the thigh's pitch (a segment never drops back
    while the thigh keeps rising, so a clip never reverses it), lifted early (DRAPE_EARLY)
    and smoothed over the pitch samples; the drivers' Bezier keys then turn the cloth
    continuously (C1)."""
    step = 360.0 / SKIRT_SECTORS
    phis = np.radians(np.array(DRAPE_PHI, dtype=float))
    i0 = int(np.argmin(np.abs(phis)))
    up = math.radians(DRAPE_UP)
    root_max = math.radians(DRAPE_ROOT_MAX)
    yg = np.radians(np.array(DRAPE_YAW_GRID, dtype=float))
    out = {}
    sides = {}
    for tag, s in (('L', 1.0), ('R', -1.0)):
        h, kn = hip * np.array([s, 1, 1]), knee * np.array([s, 1, 1])
        prof = _thigh_profile(body, h, kn, s)
        sides[tag] = (h, kn, prof, s, 0.0)
        sides[tag + 'a'] = (h, kn, prof, s, math.radians(DRAPE_PSI))
    # the thigh at every sample, shared by all chains
    spheres = {tag: [_thigh_spheres(h, kn, prof, phi, psi, s) for phi in phis]
               for tag, (h, kn, prof, s, psi) in sides.items()}
    if len({len(j) for _, j in chains}) > 1:
        raise ValueError('skirt drape: chains with different segment counts')
    K = len(chains)
    Js = np.array([[tuple(j) for j in joints] for _, joints in chains])     # (K, n + 1, 3)
    n = Js.shape[1] - 1
    # each chain's sector of cloth (subsampled), its segment and rest clearance
    cpts = pts if inner is None or not DRAPE_BIN else inner
    cang = np.degrees(np.arctan2(cpts[:, 0], cpts[:, 1] - cy))
    secs = []
    for k, (a, joints) in enumerate(chains):
        J = Js[k]
        d = (cang - a + 180.0) % 360.0 - 180.0
        m = np.abs(d) < 0.6 * step
        sel = cpts[m]
        if DRAPE_BIN and len(sel):
            # the innermost point of each (angle, height) cell (see DRAPE_BIN)
            rad = np.hypot(sel[:, 0], sel[:, 1] - cy)
            ka = np.floor(d[m] / DRAPE_BIN[0]).astype(np.int64)
            kz = np.floor(sel[:, 2] / DRAPE_BIN[1]).astype(np.int64)
            o = np.lexsort((rad, kz, ka))
            first = np.ones(len(o), dtype=bool)
            first[1:] = (ka[o][1:] != ka[o][:-1]) | (kz[o][1:] != kz[o][:-1])
            sel = sel[np.sort(o[first])]
        elif len(sel) > DRAPE_PTS:
            sel = sel[np.linspace(0, len(sel) - 1, DRAPE_PTS).astype(int)]
        zj = J[:, 2]
        u = np.interp(-sel[:, 2], np.maximum.accumulate(-zj), np.arange(n + 1.0))
        keep = u > 0.35
        sel, u = sel[keep], u[keep]
        seg = np.clip(np.floor(u), 0, n - 1).astype(int)
        secs.append((sel, seg))
    angles = np.array([a for a, _ in chains])
    gap = ((np.roll(angles, -1) - angles) % 360.0) / step       # chain steps to the next chain
    # rest ring: each chain's joints to the next chain's, scaled down to the innermost cloth
    # (DRAPE_INNER percentile of the sector's distance from the axis round each joint): the
    # inner layers (the petticoat core round the hips) lie closer together than the joints
    # but move as far, so they stretch first
    rest = np.linalg.norm(Js[:, 1:] - np.roll(Js, -1, axis=0)[:, 1:], axis=2)    # (K, n)
    share = np.ones((K, n))
    for k, (a, _) in enumerate(chains):
        d = (cang - a + 180.0) % 360.0 - 180.0
        sec = cpts[np.abs(d) < 0.6 * step]
        rad = np.hypot(sec[:, 0], sec[:, 1] - cy)
        for j in range(1, n + 1):
            h = 0.5 * abs(Js[k][j - 1, 2] - Js[k][j, 2])
            near = np.abs(sec[:, 2] - Js[k][j, 2]) < h
            rj = math.hypot(Js[k][j, 0], Js[k][j, 1] - cy)
            if near.sum() >= 8 and rj > 1e-3:
                share[k, j - 1] = min(1.0, float(np.percentile(rad[near], DRAPE_INNER)) / rj)
    scale = rest * 0.5 * (share + np.roll(share, -1, axis=0))
    scale[gap > 1.5] = np.inf          # (a missing sector: no ring across the gap)
    raw = {tag: {} for tag in sides}
    yaw = {tag: {} for tag in sides}
    for tag, (h, kn, prof, s, psi_a) in sides.items():
        free = [_thigh_depth(sel, spheres[tag[0]][i0]) <= 0.0 for sel, _ in secs]
        tabs = np.zeros((K, n, len(phis)))
        ytab = np.zeros((K, len(phis)))
        for half in (range(i0 + 1, len(phis)), range(i0 - 1, -1, -1)):
            state = None
            for pi in half:
                phi = phis[pi]
                if psi_a and phi < 0:
                    continue            # (an abducted table's backward half is the plain one's)
                sg = 1.0 if phi > 0 else -1.0
                c, r = spheres[tag][pi]
                Pm = []
                for k in range(K):
                    sel, seg = secs[k]
                    rows = []
                    for y in yg:
                        # the chain turned round by y meets the thigh turned back by -y
                        sph = (_yaw(c, Js[k][0], -y), r)
                        rows.append(sg * _drape_clear(sel, seg, free[k], Js[k], sph, sg, root_max))
                    Pm.append(np.array(rows))
                if DRAPE_GATHER:
                    A, psi, state = _drape_gather(Pm, Js, (rest, scale), sg, state, cy)
                else:
                    A, psi = np.stack([sg * p[len(yg) // 2] for p in Pm]), np.zeros(K)
                tabs[:, :, pi] = A
                ytab[:, pi] = psi
        for k in range(K):
            raw[tag][k] = tabs[k]
            yaw[tag][k] = ytab[k]
    for tag in sides:
        if tag.endswith('a'):
            for k in raw[tag]:
                raw[tag][k][:, :i0] = raw[tag[:-1]][k][:, :i0]
                yaw[tag][k][:i0] = yaw[tag[:-1]][k][:i0]

    early_max = math.radians(DRAPE_EARLY_MAX)
    for tag in sides:
        for k in range(K):
            tab = raw[tag][k].copy()
            # monotone away from rest on both sides: a thigh rising further only ever lifts
            # the cloth further (the round-6 greedy table flipped segments between samples,
            # which a clip showed as one-frame reversals)
            for pi in range(i0 + 1, len(phis)):
                tab[:, pi] = np.maximum(tab[:, pi], tab[:, pi - 1])
            for pi in range(i0 - 1, -1, -1):
                tab[:, pi] = np.minimum(tab[:, pi], tab[:, pi + 1])
            # early lift (DRAPE_EARLY): star-shaped from rest up to DRAPE_EARLY_MAX
            for side_idx in (range(i0 + 1, len(phis)), range(i0 - 1, -1, -1)):
                idx = [pi for pi in side_idx if abs(phis[pi]) <= early_max + 1e-9]
                if not idx:
                    continue
                ratio = np.abs(tab[:, idx]) / np.abs(phis[idx])[None]
                hull = np.maximum.accumulate(ratio[:, ::-1], axis=1)[:, ::-1]
                sg = np.sign(phis[idx[0]])
                early = sg * DRAPE_EARLY * np.abs(phis[idx])[None] * hull
                tab[:, idx] = sg * np.maximum(sg * tab[:, idx], sg * early)
            # smoothed, plus the smoothed (dilated) shortfall wherever smoothing took a lift
            # below what the clearance needs, so the curve stays on or above the table
            sgn = np.sign(phis)[None]
            base, tab = tab, _smooth_pitch(tab, i0)
            short = np.maximum(sgn * (base - tab), 0.0)
            wide = np.zeros_like(short)
            for half in (sgn > 0, sgn < 0):          # each side of rest on its own
                sh = short * half
                w = sh.copy()
                for o in range(1, DRAPE_SMOOTH + 1):
                    w[:, o:] = np.maximum(w[:, o:], sh[:, :-o])
                    w[:, :-o] = np.maximum(w[:, :-o], sh[:, o:])
                wide += w * half
            tab = tab + sgn * _smooth_pitch(wide, i0)
            for pi in range(i0 + 1, len(phis)):
                tab[:, pi] = np.maximum(tab[:, pi], tab[:, pi - 1])
            for pi in range(i0 - 1, -1, -1):
                tab[:, pi] = np.minimum(tab[:, pi], tab[:, pi + 1])
            # the chain again: no zigzag (DRAPE_UP), then no joint bent past DRAPE_BEND
            sg = np.sign(phis)[None]
            for j in range(n - 2, -1, -1):
                tab[j] = sg[0] * np.maximum(sg[0] * tab[j], sg[0] * tab[j + 1] - up)
            for j in range(1, n):
                tab[j] = np.clip(tab[j], tab[j - 1] - _drape_bend(j), tab[j - 1] + _drape_bend(j))
            out.setdefault(k, {})[tag] = tab
            # the yaw: smoothed over the pitch samples like the turns (no monotone: the
            # pull may hand over between neighbours as the thigh rises)
            out[k]['y' + tag] = _smooth_pitch(yaw[tag][k][None], i0)[0]
    if DRAPE_RING_CAP:
        # the tables were shaped chain by chain (monotone, early lift, smoothing): neighbours
        # are kept within DRAPE_RING_CAP of each other per chain step again (a cone that only
        # ever lifts, as round 7's, but about twice as wide), so no single chain stands out
        # of the ring and the cloth blended between them keeps its length
        # The cap of each step shrinks with the innermost cloth's spacing there (rest, below
        # the median: down to DRAPE_RING_CAP_MIN of it), so the narrow front between the
        # thighs, where the petticoat hems lie close, keeps its chains closer together than
        # the wide sides do; a chain's cone reaches the others along the cheaper way round.
        cap = np.radians(np.array([DRAPE_RING_CAP[min(j, len(DRAPE_RING_CAP) - 1)] for j in range(n)]))
        fin = np.where(np.isfinite(scale), scale, np.nan)
        edge = cap[None] * gap[:, None] * np.clip(scale / np.nanmedian(fin, axis=0, keepdims=True),
                                                  DRAPE_RING_CAP_MIN, 1.0)
        cone = np.zeros((K, K, n, 1))
        for j in range(n):
            cum = np.concatenate([[0.0], np.cumsum(edge[:, j])])
            fwd = np.abs(cum[None, :K] - cum[:K, None])
            cone[:, :, j, 0] = np.minimum(fwd, cum[K] - fwd)
        if DRAPE_RING_CAP_PITCH:
            (p0, p1), f = DRAPE_RING_CAP_PITCH
            cone = cone * (f + (1.0 - f) * _smoothstep(p0, p1, np.degrees(np.abs(phis))))[None, None, None, :]
        sg = np.sign(phis)
        for tag in sides:
            F = np.stack([out[k][tag] for k in range(K)])                        # (K, n, P)
            pos = (np.maximum(F, 0.0)[None] - cone).max(1)
            neg = (np.minimum(F, 0.0)[None] + cone).min(1)
            F = np.maximum(pos, 0.0) + np.minimum(neg, 0.0)
            if DRAPE_RING_CAP_PITCH:
                # a cone that widens with the pitch let a hem it lifted at 48 deg drop back by
                # 63 deg while the thigh kept rising, and the narrow cone handed a neighbour's
                # whole rise round the side within one run frame (strain spikes of 0.27 in the
                # run clip): where the cap is narrowed, smoothed over the pitch again (on or above
                # the cone, as the tables were before it), and monotone away from rest. (Smoothed
                # at every pitch, the seated tables changed too: skirt x petticoat crossings in
                # cross_legged 226 -> 384.)
                (p0, p1), _ = DRAPE_RING_CAP_PITCH
                w = 1.0 - _smoothstep(p0, p1, np.degrees(np.abs(phis)))
                F = np.stack([_monotone(F[k] + w * (_smooth_above(F[k], phis, i0) - F[k]), i0) for k in range(K)])
            for k in range(K):
                tab = F[k]
                for j in range(n - 2, -1, -1):
                    tab[j] = sg * np.maximum(sg * tab[j], sg * tab[j + 1] - up)
                for j in range(1, n):
                    tab[j] = np.clip(tab[j], tab[j - 1] - _drape_bend(j), tab[j - 1] + _drape_bend(j))
                out[k][tag] = tab
    if SEAT:
        for k, (a, _) in enumerate(chains):
            out[k]['seat'] = _skirt_seat(Js[k], a, hip[2] - SEAT_DROP, SEAT_ANG)
            out[k]['seat_chair'] = _skirt_seat(Js[k], a, hip[2] - SEAT_DROP, SEAT_ANG_CHAIR)
    return out


def _skirt_seat(J, a, z_seat, fade_ang=SEAT_ANG):
    """The seat swing of a skirt chain at skirt angle a (deg) with rest joints J (n + 1,
    3): the absolute outward swing (rad, (n,), the root's 0) of each segment that keeps
    every joint below joint 1 SEAT_CLEAR above z_seat (the root segment does not swing:
    with SEAT_DROP below the hip joints, joint 1 is above the seat), each joint bending at
    most SEAT_BEND against the segment above (best effort beyond), faded out toward the
    front (fade_ang: deg from straight back)."""
    n = len(J) - 1
    o = np.array([math.sin(math.radians(a)), math.cos(math.radians(a)), 0.0])
    out = np.zeros(n)
    P = J.copy()
    lim = math.radians(SEAT_BEND)
    for j in range(1, n):
        prev = out[j - 1]
        need = 0.0
        for jj in range(j + 1, n + 1):
            if P[jj, 2] < z_seat + SEAT_CLEAR:
                need = 1.0
        if need:
            # the least extra swing (0.5 deg steps) that lifts the next joint clear
            best = lim
            for th in np.radians(np.arange(0.0, SEAT_BEND + 1e-9, 0.5)):
                q = _swing(P[j + 1], P[j], o, th)
                if q[2] >= z_seat + SEAT_CLEAR:
                    best = th
                    break
            out[j] = prev + best
            P[j + 1:] = _swing(P[j + 1:], P[j], o, best)
        else:
            out[j] = prev
    fade = 1.0 - _smoothstep(fade_ang[0], fade_ang[1], abs((a + 180.0) % 360.0 - 180.0))
    return out * fade


def _swing(p, c, o, th):
    """Points p turned about the horizontal axis through c across outward direction o
    (unit, horizontal) by th rad: a hanging segment swings out along o."""
    ax = np.array([o[1], -o[0], 0.0])          # down x o: + turns down toward o
    q = p - c
    ca, sa = math.cos(th), math.sin(th)
    return q * ca + np.cross(ax, q) * sa + np.outer(q @ ax, ax).reshape(q.shape) * (1 - ca) + c


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
    'pitch_gravity': [(torso bone, share)], read by _create_armature; round 8 also
    'pelvis_follow') and the PMX 付与
    (meta 'append': a negative share of HAIR_PITCH_HELPER, the torso's forward pitch alone;
    of 上半身 without the helper). Returns the chain."""
    srcs = [n for n in HAIR_PITCH_SOURCES if n in byname]
    helper = HAIR_PITCH_HELPER if HAIR_PITCH_HELPER and len(srcs) == len(HAIR_PITCH_SOURCES) else None

    # Round 8: below the waist the hair lies over her hips and skirt, which a bend of the
    # torso does not turn: there a segment turns back all of the torso's forward pitch
    # (HAIR_PITCH_HANG, by its rest height) and takes the pelvis' pitch instead
    # (HAIR_PELVIS_FOLLOW), so the ends hang down the skirt instead of sweeping out
    # behind her with the back or sinking into the skirt as the hips tip. Both are
    # cumulative shares down the chain, kept rising; each joint takes the increment.
    segs = sorted((b for b in chain if b.meta.get('nseg', 1) >= 2 and b.meta.get('seg', 0) >= 1),
                  key=lambda b: b.meta['seg'])
    run_g = run_p = run_i = 0.0
    prev = {}
    for b in segs:
        i, n = b.meta['seg'], b.meta['nseg']
        zm = float((b.head.z + b.tail.z) / 2)
        g = gi = total * (i / (n - 1)) ** exp
        if HAIR_PITCH_HANG:
            full, z_hi, z_lo = HAIR_PITCH_HANG
            g = max(g, full * float(_smoothstep(z_hi, z_lo, zm)))
        p = 0.0
        if HAIR_PELVIS_FOLLOW and HAIR_PELVIS_FOLLOW[0] in byname:
            _src, full, z_hi, z_lo = HAIR_PELVIS_FOLLOW
            p = full * float(_smoothstep(z_hi, z_lo, zm))
        g, p, gi = max(run_g, g), max(run_p, p), max(run_i, gi)
        prev[b.name] = (g - run_g, p - run_p, gi - run_i)
        run_g, run_p, run_i = g, p, gi
    for b in segs:
        k, kp, ki = prev[b.name]
        if k > 1e-4 and srcs:
            b.meta['pitch_gravity'] = [(src, k) for src in srcs]
        if ki > 1e-4 and srcs:
            # the PMX keeps the index profile alone: it has no pelvis follow (one 付与 source
            # per bone) to go with the full hang below the waist, so a tipped pelvis would
            # lift the skirt into fully hung lock ends there (with physics on, MMD hangs them)
            b.meta['append'] = (helper or srcs[0], -ki)
        if kp > 1e-4:
            b.meta['pelvis_follow'] = [(HAIR_PELVIS_FOLLOW[0], kp)]
    return chain


def _hair_pitch_helpers(byname, h):
    """The PMX pitch-only helpers (see HAIR_PITCH_HELPER) and HAIR_ARCH_BONE at `h`."""
    up, up2 = byname['上半身'], byname['上半身2']
    out = []
    # the goal lies far out along 上半身2 (HAIR_PITCH_REACH), so the helper's aim reads
    # 上半身2's own orientation (the sum of both bends) rather than the chord from 上半身's
    # head to the neck base, which turns only by about the length-weighted mean
    far = up2.head + (up2.tail - up2.head).normalized() * HAIR_PITCH_REACH
    d = (far - up.head).normalized()
    for name, en, lim in ((HAIR_PITCH_HELPER, 'HairPitch', (0.0, 170.0)), (HAIR_ARCH_HELPER, 'HairArch', (-170.0, 0.0))):
        out.append(Bone(name, name, en, up.head, far, up.parent, deform=False, group='HairFollow',
                        meta={'helper': True, 'ik': (name + 'IK', lim)}))
        out.append(Bone(name + '先', name + '先', en + 'Tip', far, far + d * 0.03, name, connect=True,
                        deform=False, group='HairFollow', meta={'helper': True}))
        out.append(Bone(name + 'IK', name + 'IK', en + 'IK', far, far + d * 0.03, '上半身2',
                        deform=False, group='HairFollow', meta={'helper': True}))
    meta = {'helper': True}
    if HAIR_ARCH_HANG > 1e-4:
        meta['append'] = (HAIR_ARCH_HELPER, -HAIR_ARCH_HANG)
    out.append(Bone(HAIR_ARCH_BONE, HAIR_ARCH_BONE, 'HairArchFollow', h, h + Vector((0, 0, 0.03)), '首',
                    deform=False, group='HairFollow', meta=meta))
    return out


def _pitch_counter(arm, pb, src, k, forward, name):
    """Blender: a Transform constraint that turns pose bone `pb` back by k of bone `src`'s
    forward (forward=True) or backward pitch only, about world X as it lies in pb's rest
    frame; zero on the other side (clamped: no extrapolation). The pitch is read in the
    source's own frame, on its axis nearest world X (the torso and pelvis bones are
    rolled square to X, so a bend is one component there).
    Round 8: the turn is spread over pb's three local Euler components along world X in its
    rest frame (round 7 put it all on pb's single axis nearest world X: on a segment running
    sideways, an outer lock over the arm, that is its own length, so the 'hang' only rolled
    it and the lock still swept out behind her in forward_bend). Exact about one axis,
    second-order close otherwise; approximate when the torso also twists."""
    sm = arm.data.bones[src].matrix_local.to_3x3()
    sax = max(range(3), key=lambda i: abs(sm.col[i].x))
    ssgn = 1.0 if sm.col[sax].x > 0 else -1.0
    S = 'XYZ'[sax]
    a = arm.data.bones[pb.name].matrix_local.to_3x3().transposed() @ Vector((1.0, 0.0, 0.0))
    big = math.radians(170.0)
    lo, hi = (0.0, big) if (ssgn > 0) == forward else (-big, 0.0)
    c = pb.constraints.new('TRANSFORM')
    c.name = name
    c.target, c.subtarget = arm, src
    c.target_space, c.owner_space = 'LOCAL', 'LOCAL'
    c.map_from = c.map_to = 'ROTATION'
    c.mix_mode_rot = 'BEFORE'
    c.use_motion_extrapolate = False
    for i, ch in enumerate('xyz'):
        setattr(c, f'map_to_{ch}_from', S)
        setattr(c, f'from_min_{ch}_rot', lo if ch == S.lower() else 0.0)
        setattr(c, f'from_max_{ch}_rot', hi if ch == S.lower() else 0.0)
        # source component s -> world pitch ssgn * s -> pb turns -k x that about a
        setattr(c, f'to_min_{ch}_rot', -k * ssgn * lo * a[i])
        setattr(c, f'to_max_{ch}_rot', -k * ssgn * hi * a[i])
    return c


# ---------------------------------------------------------------- hair collision (Blender only)
# MMD simulates the hair chains as rigid bodies that collide with the body (export_pmx);
# Blender has no physics, so a hanging chain went wherever its bones put it: the side curls
# into a raised shoulder, the back-hair ends into the skirt when the hips flexed or the skirt
# flared. Each hair chain segment s gets collision probes instead:
#   ghost   a non-deforming copy of s (same parent, rest and constraints; drivers copy s's
#           own pose rotation), so its tail is where s's tail would be without collision;
#   probe   a point bone on the ghost's tail with Shrinkwraps (nearest surface, outside),
#           one per collider and pass, which push it out of any collider it has entered,
#           and a Limit Distance (HAIR_COLLIDE_MAX_PUSH);
#   ghost 2 the ghost aimed at the tail probe, with a mid probe half way along it, so a
#           collider rising under the middle of a segment (not just its end) turns it too;
#   s       Damped Track to the mid probe as its last constraint: unchanged when nothing is
#           hit (the probe is then exactly on its axis), turned out of the collider otherwise.
# Colliders are closed, rounded convex hulls of the rest skin / cloth around each moving body
# part (HAIR_COLLIDERS) and radial envelopes of the skirt (its waist, and the band below the
# hip once per skirt chain), parented rigidly to the bone that carries that part, so a
# collider never depends on the deformed meshes (no dependency cycle). A probe keeps the hair
# surface beside it at least HAIR_COLLIDE_CLEAR off each collider, or its rest gap if that is
# smaller, so nothing moves at rest. strip_blender_only() removes probes, ghosts and
# colliders before a PMX export.
HAIR_COLLIDE = True
HAIR_COLLIDE_CLEAR = (0.006, 0.012)   # m kept between the hair surface and a collider: side locks (squeezed
# between shoulder, chest and head, more pushed them into the next one), back hair (on the skirt)
HAIR_COLLIDE_GROUP = 'HairCollide'
HAIR_COLLIDER_TAG = 'levi_hair_collider'
HAIR_CAPSULES_PROP = 'levi_hair_capsules'   # armature: JSON capsules for export_pmx's hair-only bodies
HAIR_COLLIDE_SKIRT_DROP = 0.32   # m below the hip that the skirt colliders reach
HAIR_COLLIDE_GRID = 0.006        # m: collider points are thinned to this grid before the hull
# (collider, stems of the dominant bones of its points, parent bone stem, parts sampled,
# only points this near the parent bone's head (m) or None, Blender collider, PMX capsule).
# The sleeves count only where an arm bone dominates them (not the hanging drape).
_ARM_STEMS = ('肩補助2', '肩補助3', '腕D', '腕', '腕捩')
# RIG_FIT_PROP (object, 0..1, default 1): the share of an object's vertices that the rig's
# point-count fits sample (the hair colliders here, the sleeve drape chains in
# _secondary_bones; _fit_verts), 0 to leave it out. Those fits take percentiles and centroids
# of vertices, so a part that remeshes a piece denser (round 11's sleeve frill and cuff,
# 2-4x) can keep its weight in them as it was, and leave out an inner layer that only skews
# them (the cuff's under tier).
RIG_FIT_PROP = 'levi_rig_fit'
HAIR_COLLIDERS = (
    ('shoulder', _ARM_STEMS, '腕D', ('body', 'sleeves'), 0.10, True, False),
    ('upperarm', _ARM_STEMS, '腕D', ('body', 'sleeves'), None, True, True),
    ('forearm', ('ひじ補助', 'ひじ', '手捩'), 'ひじ', ('body', 'sleeves'), None, True, True),
    ('hand', ('手首', 'Fingers'), '手首', ('body', 'sleeves'), None, True, True),
    ('chest', ('上半身2',), '上半身2', ('body', 'bodice'), None, True, True),
    ('waist', ('上半身',), '上半身', ('body', 'bodice'), None, True, True),
    ('neck', ('首',), '首', ('body', 'accessories'), None, True, False),
    ('head', ('頭',), '頭', ('head',), None, True, False),
)
HAIR_COLLIDE_PASSES = 2   # every probe runs its colliders twice: out of one may push into another
# Kinematic pushes have no memory: a limb that sweeps right through the hair pushes a
# probe out of its near side, then (past its middle) out of the far side, and the chain
# below swings across in one frame (idol_dance, an arm swung from behind her back to
# overhead: 0.3-0.8 m jumps; the left arm rising past the face: 0.3 m). So the arms meet
# only the side locks: the shoulder cap (the arm's skin and sleeve within 10 cm of the
# joint, which rises under the curls) everywhere, the forearms and hands below
# HAIR_COLLIDE_ARM_Z (a hand on the shoulder), the whole upper arm only the cheek wisps
# above it (round 8, HAIR_COLLIDE_UPPERARM). The back
# hair meets the trunk and the skirt but not the arms, which reach it only by sweeping
# through it. The skirt is tested only near it, and no probe is pushed more than
# HAIR_COLLIDE_MAX_PUSH from where it would be.
HAIR_COLLIDE_LIMBS = ('shoulder', 'forearm', 'hand')
HAIR_COLLIDE_ARM_Z = L['shoulder_z'] + 0.02
HAIR_COLLIDE_CAP_ABOVE = 0.03   # m the shoulder cap reaches above that (the lock roots by the jaw: a cap
# raised beside the head with the arm overhead swept them across her mouth)
HAIR_COLLIDE_SKIRT_ABOVE = 0.25   # m above the hip a probe still tests the skirt
HAIR_COLLIDE_MAX_PUSH = (0.05, 0.08)   # m: side locks (the arms reach them), back hair (the trunk and skirt only)
# ... and no more than turns a segment HAIR_COLLIDE_MAX_TURN deg: a probe pushed most of a segment's
# length out bent a lock end square to the rest (49 deg in look_over_shoulder, 85 in jump_tuck)
# where hair would bend gradually; a little hair left in the cloth reads better than a hook
HAIR_COLLIDE_MAX_TURN = 20.0   # deg per stage (tail probe, then mid probe): 40 at most
# ... per side-lock family (round 8): the cheek wisps' chain is 6 cm long beside the face,
# where a larger turn folded it (x0.11 at 32 deg in dance_sway) and Codex preferred the
# wisps hanging over them being pushed out round a raised arm: they only give a little
HAIR_COLLIDE_MAX_TURN_BY = {'hair_cheek': 6.0}
HAIR_COLLIDE_SMOOTH = (0.6, 0.35)   # curtain: own push, each neighbour's push
# Round 8: the limbs push as capsules round their bone (_Capsule), not hulls: inside a
# hull the nearest-surface push jumps between faces (the curl in spin: 17 -> 9 mm in a
# frame, an 82 mm pop at the lock end). A capsule pushes straight out from its axis, which
# is continuous but on the axis itself: per probe, a projector bone on the limb takes the
# probe's unpushed point and is clamped onto the bone's axis segment (Copy Location, Limit
# Location), and a Limit Distance keeps the probe its radius (+ clearance) from it. (A row
# of spheres pushed one after another walked a probe along the arm: 100 mm, cut to the push
# cap, whose direction then swung.) Radius: the HAIR_CAPSULE_Q-th percentile of the skin
# and sleeve's distance from the bone over the span they cover.
HAIR_COLLIDE_CAPSULES = ('shoulder', 'upperarm', 'forearm', 'hand')
HAIR_CAPSULE_Q = 60.0   # (90, a capsule as fat as the sleeve, laid the curls out along a raised
# arm; pairwise Codex preferred them hanging in front of it, a little into the sleeve)
# Round 8: the whole upper arm (a capsule) pushes these side-lock families above
# HAIR_COLLIDE_ARM_Z: the cheek wisps beside the face, which arms raised overhead or behind
# the head pressed into (10 % of them inside the arm in reach_up_back). Not the lock and
# curl roots by the jaw: an arm swung up past them squeezes them against the head, and the
# pushes swung the curls round in a frame (330 mm in idol_dance).
HAIR_COLLIDE_UPPERARM = ('hair_cheek',)
# Round 8: the curl's last segment (its hook, lying out along the arm) is not pushed by the
# shoulder cap itself but rides the segment above, which is: pushed on its own, it switched
# in and out of the cap as the segment above turned (a 108 mm pop at the tip in spin)
HAIR_CAP_TIP_FREE = ('hair_curl',)
# (fraction of a capsule's radius): its push fades in as the probe's unpushed point lies
# between these distances from the axis (none nearer: the limb has swept through the hair,
# which then passes through it rather than being flung across)
HAIR_CAPSULE_FADE = (0.1, 0.45)
# ... per side-lock family. The cheek wisps only yield to a soft contact near the arm's
# surface (gone by half its radius in): squeezed between a raised arm and the head, a full
# push hit its cap and swung about it (a 57 mm pop in idol_dance as the arm went up past
# the face); this way the push stays under ~0.15 of the radius and below the cap.
HAIR_CAPSULE_FADE_BY = {'hair_cheek': (0.5, 1.0)}
HAIR_COLLIDE_REACH = 0.12   # m: trunk / skirt / head hulls farther than this from a probe at rest are not tested
# (not normalised, on purpose: pushed alike with both neighbours a segment moves 1.3x its push,
# which is spare clearance; normalised, an isolated push was resolved only by half)


def _fit_verts(o, *arrays):
    """World vertices of o that the rig's fits sample (RIG_FIT_PROP), and the same rows of
    each further per-vertex array: an even, deterministic thinning to that share."""
    co = _world_verts([o])
    share = float(o.get(RIG_FIT_PROP, 1.0))
    if share < 1.0:
        i = np.arange(len(co))
        m = np.floor((i + 1) * share) > np.floor(i * share)
        co, arrays = co[m], tuple(a[m] for a in arrays)
    return (co,) + tuple(arrays) if arrays else co


def _dominant_stems(obj, arm):
    """(V,) stem of each vertex's heaviest bone ('Fingers' for finger bones, '' if none)."""
    groups = {}
    for vg in obj.vertex_groups:
        b = arm.data.bones.get(vg.name)
        if b is not None:
            fing = b.collections and b.collections[0].name == 'Fingers'
            groups[vg.index] = 'Fingers' if fing else vg.name
    out = []
    for v in obj.data.vertices:
        best, bw = '', 0.0
        for g in v.groups:
            n = groups.get(g.group)
            if n is not None and g.weight > bw:
                best, bw = n, g.weight
        out.append(best)
    return np.array(out, dtype=object)


def _hull_bm(pts):
    """bmesh of the closed convex hull of `pts`, or None."""
    import bmesh
    g = np.unique(np.round(pts / HAIR_COLLIDE_GRID).astype(np.int64), axis=0)
    if len(g) < 8:
        return None
    pts = g * HAIR_COLLIDE_GRID
    bm = bmesh.new()
    for p in pts:
        bm.verts.new(p.tolist())
    res = bmesh.ops.convex_hull(bm, input=list(bm.verts), use_existing_faces=False)
    junk = {v for v in res['geom_interior'] + res['geom_unused'] if isinstance(v, bmesh.types.BMVert)}
    junk |= {v for v in bm.verts if not v.link_faces}
    bmesh.ops.delete(bm, geom=list(junk), context='VERTS')
    if len(bm.faces) < 4:
        bm.free()
        return None
    return bm


def _radial_bm(pts, cy, z0, z1, n_ang=72, dz=0.015):
    """bmesh of a closed surface round the vertical axis through (0, cy) that follows the
    outermost of `pts` per angle and height between z0 and z1 (star-shaped, not convex:
    it keeps the skirt's fold troughs, where the lock ends hang), capped at both ends."""
    import bmesh
    nz = max(2, int(round((z1 - z0) / dz)) + 1)
    zs = np.linspace(z0, z1, nz)
    ang = np.arctan2(pts[:, 0], pts[:, 1] - cy)
    rad = np.hypot(pts[:, 0], pts[:, 1] - cy)
    bins = ((ang + np.pi) / (2 * np.pi) * n_ang).astype(int) % n_ang
    rings = []
    for z in zs:
        sel = np.abs(pts[:, 2] - z) <= dz
        r = np.full(n_ang, np.nan)
        for k in np.unique(bins[sel]):
            r[k] = float(np.percentile(rad[sel & (bins == k)], 95))
        if np.isnan(r).all():
            return None
        ok = ~np.isnan(r)
        idx = np.arange(n_ang)
        r = np.interp(idx, idx[ok], r[ok], period=n_ang)
        r = (np.roll(r, 1) + 2 * r + np.roll(r, -1)) / 4      # a light circular smoothing
        rings.append(r)
    th = (np.arange(n_ang) + 0.5) / n_ang * 2 * np.pi - np.pi
    bm = bmesh.new()
    vs = [[bm.verts.new((float(r[k] * math.sin(th[k])), float(cy + r[k] * math.cos(th[k])), float(z)))
           for k in range(n_ang)] for r, z in zip(rings, zs)]
    for a, b in zip(vs, vs[1:]):
        for k in range(n_ang):
            bm.faces.new((a[k], a[(k + 1) % n_ang], b[(k + 1) % n_ang], b[k]))
    for ring, z in ((vs[0], zs[0]), (vs[-1], zs[-1])):
        c = bm.verts.new((0.0, cy, float(z)))
        for k in range(n_ang):
            bm.faces.new((ring[k], ring[(k + 1) % n_ang], c))
    return bm


def _hull_collider(name, pts, arm, parent_bone, col, bm=None):
    """A closed collider object, parented rigidly to `parent_bone`: the convex hull of
    `pts` (world, rest), or the bmesh `bm` given."""
    bm = bm if bm is not None else _hull_bm(pts)
    if bm is None:
        return None
    bmesh_ops = __import__('bmesh').ops
    bmesh_ops.recalc_face_normals(bm, faces=list(bm.faces))
    for f in bm.faces:
        f.smooth = True
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    col.objects.link(obj)
    obj[HAIR_COLLIDER_TAG] = True
    # rounded: at a hull's sharp corner the nearest face's normal can face away from a point
    # that is outside, and the Shrinkwrap would then pull it onto the hull
    sub = obj.modifiers.new('Round', 'SUBSURF')
    sub.levels = sub.render_levels = 2
    obj.parent = arm
    obj.parent_type = 'BONE'
    obj.parent_bone = parent_bone
    obj.matrix_world = arm.matrix_world.copy()    # rest pose: the hull stays where it was built
    obj.hide_render = True
    obj.visible_shadow = False
    obj.display_type = 'WIRE'
    return obj


def _hair_colliders(arm, parts, bones, want=(), blender=True):
    """{name: (collider object, its rest BVH, info)} for every body part the hair may hit
    (none with blender=False), and the PMX hair-only capsules (arm[HAIR_CAPSULES_PROP]).
    info: (chain angle, axis y) for the per-chain skirt rings (made for the chains in
    `want` only), else None."""
    from mathutils.bvhtree import BVHTree
    col = bpy.data.collections[RIG_COLLECTION]
    names = set(arm.data.bones.keys())
    samples = {}
    capsules = []     # the same parts as MMD rigid bodies (export_pmx: hair-only colliders)
    for part in ('body', 'sleeves', 'bodice', 'accessories', 'head'):
        for o in parts.get(part, []):
            samples.setdefault(part, []).append(_fit_verts(o, _dominant_stems(o, arm)))
    out = {}

    def add(name, pts, parent, info=None, bm=None):
        if not blender:
            return
        if parent not in names or len(pts) < 8:
            print(f'rig hair collider {name}: skipped ({len(pts)} points, parent {parent})')
            return
        obj = _hull_collider(f'_hair_collider_{name}', pts, arm, parent, col, bm)
        if obj is None:
            return
        bpy.context.view_layer.update()
        ev = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
        me = ev.to_mesh()
        mw = np.array(obj.matrix_world)
        co = np.array([tuple(v.co) for v in me.vertices]) @ mw[:3, :3].T + mw[:3, 3]
        tris = [tuple(p.vertices) for p in me.polygons]
        ev.to_mesh_clear()
        out[name] = (obj, BVHTree.FromPolygons(co.tolist(), tris), info)

    for cname, stems, parent, use, within, in_blender, pmx in HAIR_COLLIDERS:
        for tag, s, _jp in (SIDES if parent not in ('上半身', '上半身2', '首', '頭') else (('', 0.0, ''),)):
            sfx = '.' + tag if tag else ''
            full = {st + sfx for st in stems} | ({'Fingers'} if 'Fingers' in stems else set())
            pts = []
            for part in use:
                for co, dom in samples.get(part, []):
                    m = np.isin(dom, list(full))
                    if 'Fingers' in full and tag:     # finger groups carry no side: keep this hand's
                        m &= ~((dom == 'Fingers') & (co[:, 0] * s <= 0))
                    pts.append(co[m])
            pts = np.concatenate(pts) if pts else np.zeros((0, 3))
            pname = deform_arm(names, tag) if parent == '腕D' else parent + sfx
            if within is not None and pname in names:
                pts = pts[np.linalg.norm(pts - np.array(arm.data.bones[pname].head_local), axis=1) <= within]
            cap = None
            if in_blender and blender and cname in HAIR_COLLIDE_CAPSULES and pname in names:
                bn = arm.data.bones[pname]
                fit = pts
                if cname == 'hand' and len(pts):
                    # round 11: 风堇's subdivided hand has ~5x the forearm's vertices per area, so
                    # the raw percentiles followed the fingers' spread (r 2.4 -> 2.9 cm, pushing the
                    # side locks into the head in dance_heart); fit the surface, like the hulls
                    fit = np.unique(np.round(pts / HAIR_COLLIDE_GRID).astype(np.int64), axis=0) * HAIR_COLLIDE_GRID
                cap = _Capsule.fit(pname, fit, np.array(bn.head_local), np.array(bn.tail_local))
                if cap:
                    out[cname + sfx] = (None, cap, None)
                    print(f'rig hair capsule {cname + sfx}: r {cap.r * 100:.1f} cm, '
                          f'{cap.t0 * 100:.1f}-{cap.t1 * 100:.1f} cm along {pname}')
                else:
                    print(f'rig hair collider {cname + sfx}: no capsule ({len(pts)} points), hull instead')
            if in_blender and cap is None:
                add(cname + sfx, pts, pname)
            if pmx and pname in names and len(pts) >= 8:
                bn = arm.data.bones[pname]
                a, b = np.array(bn.head_local), np.array(bn.tail_local)
                if tag:          # a limb: along its bone
                    cap = _fit_capsule(pts, a, b)
                else:            # the torso: across her at mid-bone height, front to back, from
                    # all its skin and cloth there (the back is not all this bone's), arms excluded
                    allp = np.concatenate([co for part in use for co, _d in samples.get(part, [])])
                    cap = _fit_slab_capsule(allp[np.abs(allp[:, 0]) < 0.11], float(a[2] + b[2]) / 2)
                if cap:
                    capsules.append(dict(name=cname + sfx, bone=pname, **cap))
    # the skirt: its waist (above the chain roots, where the cloth rides the skin) on
    # 下半身, and below the hip one whole ring per skirt chain riding that chain's root,
    # so a flare or a drape lift carries it like the cloth there. A probe tests the ring
    # of the chain nearest it at rest; whole rings (not wedges) have no side faces to be
    # pushed out through when the torso twists the hair round the skirt.
    sk = _world_verts(parts.get('skirt', []))
    roots = [b for b in bones if b.group == 'Skirt' and b.meta.get('seg') == 0 and 'chain' in b.meta]
    if len(sk):
        cy = roots[0].meta['cy'] if roots else float(sk[:, 1].mean())
        # (radial envelopes, not hulls: a hull bridges the fold troughs the lock ends hang in,
        # so those probes started inside it and were never tested)
        top = sk[sk[:, 2] >= L['hip_z'] - 0.01]
        if blender:
            add('skirt_waist', top, '下半身', bm=_radial_bm(top, cy, L['hip_z'] - 0.01, float(top[:, 2].max())))
        # PMX: the skirt top behind her as two hair-only capsules across the hips on 下半身
        for i, zc in enumerate((L['hip_z'] + 0.02, L['hip_z'] - 0.1)):
            band = sk[(np.abs(sk[:, 2] - zc) < 0.02) & (sk[:, 1] > cy)]
            if len(band) < 8:
                continue
            r = float(np.percentile(band[:, 1] - cy, 40)) - 0.005
            w = max(0.02, float(np.percentile(np.abs(band[:, 0]), 90)) - r)
            if r > 0.02:
                capsules.append(dict(name=f'skirt{i}', bone='下半身', a=(-w, cy, zc), b=(w, cy, zc), r=r))
    if len(sk) and roots:
        cy = roots[0].meta['cy']
        z0 = L['hip_z'] - HAIR_COLLIDE_SKIRT_DROP
        z1 = L['hip_z'] + 0.03
        ring = sk[(sk[:, 2] >= z0 - 0.02) & (sk[:, 2] <= z1 + 0.02)]
        ring_bm = _radial_bm(ring, cy, z0, z1) if blender and want else None
        for b in roots:
            if ring_bm is not None and b.meta['chain'] in want:
                add(f'skirt{b.meta["chain"]}', ring, b.name, (b.meta['angle'], cy), bm=ring_bm.copy())
        if ring_bm is not None:
            ring_bm.free()
    import json
    arm[HAIR_CAPSULES_PROP] = json.dumps(capsules, ensure_ascii=False)
    return out


def _capsule_fade(b):
    """(start, full) of a capsule push's fade for hair segment b (fractions of the radius)."""
    return HAIR_CAPSULE_FADE_BY.get(b.meta.get('family'), HAIR_CAPSULE_FADE)


class _Capsule:
    """A limb collider (round 8): the points within r of the bone's axis between t0 and t1
    (m from its head), rest pose."""

    def __init__(self, bone, a, ax, t0, t1, r):
        self.bone, self.a, self.ax, self.t0, self.t1, self.r = bone, a, ax, t0, t1, r

    @classmethod
    def fit(cls, bone, pts, a, b, q=HAIR_CAPSULE_Q):
        """Fitted to the points' 5-95 % span along the bone a -> b (within it) and the q-th
        percentile of their distance from it; None for too few points."""
        ln = float(np.linalg.norm(b - a))
        if ln < 1e-6 or len(pts) < 8:
            return None
        ax = (b - a) / ln
        t = (pts - a) @ ax
        t0, t1 = (float(v) for v in np.percentile(t, (5, 95)))
        t0, t1 = max(0.0, t0), min(ln, t1)
        sel = (t >= t0) & (t <= t1)
        if t1 < t0 or sel.sum() < 6:
            return None
        lat = np.linalg.norm(pts[sel] - a - np.outer(t[sel], ax), axis=1)
        r = float(np.percentile(lat, q))
        return cls(bone, a, ax, t0, t1, r) if r > 0.01 else None

    def signed(self, p):
        p = np.asarray(p)
        t = min(self.t1, max(self.t0, float((p - self.a) @ self.ax)))
        return float(np.linalg.norm(p - self.a - self.ax * t)) - self.r


def _fit_slab_capsule(pts, z, dz=0.03, margin=0.008):
    """A capsule across X at height z through the points' slab |z - pz| < dz: its round
    section spans their depth (3-97 %, less `margin`), its ends their width."""
    sl = pts[np.abs(pts[:, 2] - z) < dz]
    if len(sl) < 8:
        return None
    yf, yb = (float(v) for v in np.percentile(sl[:, 1], (3, 97)))
    r = (yb - yf) / 2 - margin
    w = float(np.percentile(np.abs(sl[:, 0]), 90)) - r
    if r < 0.01:
        return None
    w = max(w, 0.0)
    yc = (yb + yf) / 2
    return dict(a=(-w, yc, z), b=(w, yc, z), r=r)


def _fit_capsule(pts, a, b, q=40.0, margin=0.005):
    """A capsule along the bone a -> b inside the points' surface: the q-th percentile of
    their distance from the axis, less `margin`, over the 5-95 % of their span along it.
    {'a', 'b', 'r'} (world, rest) or None."""
    ax = b - a
    ln = float(np.linalg.norm(ax))
    if ln < 1e-6:
        return None
    ax = ax / ln
    t = (pts - a) @ ax
    lat = np.linalg.norm(pts - a - np.outer(t, ax), axis=1)
    r = float(np.percentile(lat, q)) - margin
    t0, t1 = (float(v) for v in np.percentile(t, (5, 95)))
    if r < 0.01 or t1 - t0 < 1e-3:
        return None
    t0, t1 = t0 + r, t1 - r          # the round ends stay within the span
    if t1 < t0:
        t0 = t1 = (t0 + t1) / 2
    return dict(a=tuple((a + ax * t0).tolist()), b=tuple((a + ax * t1).tolist()), r=r)


def _signed(bvh, p):
    """Signed distance of p from a closed hull (+ outside), or None."""
    loc, nrm, _i, dist = bvh.find_nearest(Vector(p))
    if loc is None:
        return None
    return dist if (Vector(p) - loc).dot(nrm) >= 0.0 else -dist


def _hair_collision(arm, bones, parts):
    """Probes, ghosts and colliders for every deforming hair chain segment (see above)."""
    _remove_colliders()                       # an earlier rig's
    segs = [b for b in bones if b.group == 'Hair' and b.deform and 'seg' in b.meta]
    if not segs:
        return
    if not HAIR_COLLIDE:     # (the PMX's hair-only capsules all the same)
        _hair_colliders(arm, parts, bones, blender=False)
        return
    # each probe's skirt chain: the one nearest round the skirt axis at rest
    roots = [b for b in bones if b.group == 'Skirt' and b.meta.get('seg') == 0 and 'chain' in b.meta]
    near_chain = {}
    for b in segs:
        if roots:
            a = math.degrees(math.atan2(b.tail.x, b.tail.y - roots[0].meta['cy']))
            near_chain[b.name] = min(roots, key=lambda r: abs((a - r.meta['angle'] + 180.0) % 360.0 - 180.0)).meta['chain']
    colliders = _hair_colliders(arm, parts, bones, set(near_chain.values()))
    if not colliders:
        return
    # hair vertices by the segment that dominates them (rest, world)
    hv = {}
    for part in ('hair_back', 'hair_front'):
        for o in parts.get(part, []):
            co, dom = _world_verts([o]), _dominant_stems(o, arm)
            for n in set(dom.tolist()):
                if n:
                    hv.setdefault(n, []).append(co[dom == n])
    hv = {k: np.concatenate(v) for k, v in hv.items()}
    by = {b.name: b for b in bones}
    child = {}
    for b in segs:
        if b.parent in by:
            child[b.parent] = b.name
    def tests(b, at):
        """Tests for a probe at point `at` of segment b: (hull collider, Shrinkwrap distance)
        or ('capsule', collider name, radius, distance kept from the axis, _Capsule)."""
        # the hair this point carries: the segment's own vertices and the next one's
        near = [hv[n] for n in (b.name, child.get(b.name)) if n in hv]
        near = np.concatenate(near) if near else at[None]
        rad = max(0.02, 0.6 * float((b.tail - b.head).length))
        near = near[np.linalg.norm(near - at, axis=1) <= rad]
        if not len(near):
            near = at[None]
        out = []
        mine = f'skirt{near_chain[b.name]}' if b.name in near_chain else None
        low = at[2] < L['shoulder_z'] - 0.10     # far below the neck: the head and neck are out of reach
        # the limbs first, the trunk last: squeezed between a raised arm and the chest, the
        # hair ends outside the trunk (the larger, slower surface) rather than inside it
        order = ('hand', 'forearm', 'upperarm', 'shoulder', 'skirt', 'waist', 'chest', 'neck', 'head')
        for cname, (obj, bvh, info) in sorted(colliders.items(), key=lambda kv: (
                next((i for i, p in enumerate(order) if kv[0].startswith(p)), len(order)), kv[0])):
            if info is not None and cname != mine:
                continue
            if cname.startswith(HAIR_COLLIDE_LIMBS) and (b.name.startswith('後髪') or (
                    at[2] > HAIR_COLLIDE_ARM_Z + (HAIR_COLLIDE_CAP_ABOVE if cname.startswith('shoulder') else 0.0))):
                continue           # (see HAIR_COLLIDE_LIMBS)
            if (cname.startswith('shoulder') and b.meta.get('family') in HAIR_CAP_TIP_FREE
                    and b.meta.get('seg', 0) == b.meta.get('nseg', 0) - 1):
                continue           # (see HAIR_CAP_TIP_FREE)
            if cname.startswith('upperarm') and (b.meta.get('family') not in HAIR_COLLIDE_UPPERARM
                                                 or at[2] <= HAIR_COLLIDE_ARM_Z):
                continue           # (see HAIR_COLLIDE_UPPERARM)
            if cname.startswith('skirt') and at[2] > L['hip_z'] + HAIR_COLLIDE_SKIRT_ABOVE:
                continue
            if low and cname in ('head', 'neck'):
                continue
            if obj is None:          # a limb's capsule (_Capsule): one Limit Distance
                d = keep(bvh.signed, at, near, b)
                g0 = bvh.signed(at)
                if d is not None:
                    out.append(('capsule', cname, bvh.r, bvh.r + d, bvh))
                elif g0 + bvh.r > _capsule_fade(b)[1] * bvh.r:
                    # inside the (round) capsule at rest, as the curls lying on the shoulder
                    # are: kept at least their rest distance from its axis, so the rest pose
                    # is untouched and a rising shoulder still lifts them
                    out.append(('capsule', cname, bvh.r, g0 + bvh.r - 1e-4, bvh))
                continue
            # (round 8) a trunk, head or skirt hull farther than HAIR_COLLIDE_REACH from the
            # probe at rest is not tested: a Shrinkwrap may misjudge a far point as inside and
            # throw it onto the hull (the chest pulled a lock end at the hips 29 cm, cut to the
            # push cap: 43 mm pops in turn and idol_dance)
            g0 = _signed(bvh, at)
            if g0 is not None and g0 > HAIR_COLLIDE_REACH:
                continue
            d = keep(lambda p: _signed(bvh, p), at, near, b)
            if d is not None:
                out.append((obj, d))
        return out

    def keep(sd, at, near, b):
        """Distance a probe at `at` is kept off a collider with signed distance sd(), or None
        when the probe starts in (or on) it."""
        g0 = sd(at)
        if g0 is None or g0 <= 1e-4:
            return None            # the probe is in (or on) this collider at rest: no test
        surf = min((s for s in (sd(p) for p in near[:: max(1, len(near) // 64)]) if s is not None), default=g0)
        # keep the hair surface HAIR_COLLIDE_CLEAR off, or at its rest gap if closer
        dist = g0 - max(0.0, surf - HAIR_COLLIDE_CLEAR[b.name.startswith('後髪')])
        return max(0.0, min(dist, g0 - 1e-4))

    plan = []
    for b in segs:
        tail = np.array(b.tail)
        mid = (np.array(b.head) + tail) / 2
        ct, cm = tests(b, tail), tests(b, mid)
        if ct or cm:
            plan.append((b, ct, cm))
    if not plan:
        return
    # bones: ghost (copy of s), tail probe; ghost 2 (the ghost aimed at the tail probe),
    # mid probe (half way along ghost 2). s aims at the mid probe, which is ghost 2's
    # middle unless that is in a collider: a shoulder rising right under the segment
    # (not just under its end) turns it out too.
    names = lambda b: (f'{b.name}_hc', f'{b.name}_hcp', f'{b.name}_hc2', f'{b.name}_hcm')  # noqa: E731
    # The curtain is one sheet weighted between neighbouring sector chains: pushed one by one,
    # a chain whose end met the skirt pulled the sheet away from its neighbours (x1.7 at
    # the curtain's edge when she twisted). So a curtain segment aims at its probes' push
    # averaged with the same segment's pushes on the neighbouring chains (weights
    # HAIR_COLLIDE_SMOOTH): smoothing bones (_hcs / _hcn) add the probes' local offsets.
    planned = {b.name for b, _t, _m in plan}
    curtain = sorted((b for b, _t, _m in plan if 'chain' in b.meta), key=lambda b: (b.meta['seg'], b.meta['angle']))
    ring = {}
    for b in curtain:
        ring.setdefault(b.meta['seg'], []).append(b)
    nbrs = {}
    gap = RING_MAX_GAP * 360.0 / HAIR_SECTORS
    for seg, lst in ring.items():
        for i, b in enumerate(lst):
            nbrs[b.name] = [o.name for o in (lst[i - 1] if i else None, lst[i + 1] if i + 1 < len(lst) else None)
                            if o is not None and abs(o.meta['angle'] - b.meta['angle']) <= gap]
    bpy.context.view_layer.objects.active = arm
    for o in bpy.context.view_layer.objects:
        o.select_set(o == arm)
    bpy.ops.object.mode_set(mode='EDIT')
    eb = arm.data.edit_bones
    for b, _t, _m in plan:     # (parents first: bones are in hierarchy order)
        e = eb[b.name]
        gname, pname, g2name, mname = names(b)
        d = (e.tail - e.head).normalized()
        # a ghost hangs from the real (corrected) parent, so the chain stays one smooth curve:
        # hanging it from the parent's ghost instead (not inheriting the parent's push) bent
        # every pushed joint into a kink the blended skin creased at (x2.1 in jump_tuck)
        made = [(gname, e.head, e.tail, e.parent), (pname, e.tail, e.tail + d * 0.005, gname),
                (g2name, e.head, e.tail, gname), (mname, (e.head + e.tail) / 2, (e.head + e.tail) / 2 + d * 0.005, g2name)]
        if b.name in nbrs:
            made += [(f'{b.name}_hcs', e.tail, e.tail + d * 0.005, gname),
                     (f'{b.name}_hcn', (e.head + e.tail) / 2, (e.head + e.tail) / 2 + d * 0.005, g2name)]
        # capsule tests read the probe's unpushed point from an anchor (_hca / _hcma: the
        # probe itself is what they push); a projector per capsule clamps it onto the axis
        for probe_tests, anchor, at, gparent in ((_t, f'{b.name}_hca', e.tail, gname),
                                                 (_m, f'{b.name}_hcma', (e.head + e.tail) / 2, g2name)):
            caps = [t for t in probe_tests if t[0] == 'capsule']
            if caps:
                made.append((anchor, at, at + d * 0.005, gparent))
            for t in caps:
                pe = eb[t[4].bone]
                ax = (pe.tail - pe.head).normalized()
                made.append((f'{anchor}_{t[1]}', pe.head, pe.head + ax * 0.01, pe))
        for n, head, tail, parent in made:
            k = eb.new(n)
            k.head, k.tail = head.copy(), tail.copy()
            k.roll = e.roll    # (a projector's roll does not matter: its X and Z are held at 0)
            k.parent = parent if not isinstance(parent, str) else eb[parent]
            k.use_deform = False
    bpy.ops.object.mode_set(mode='OBJECT')
    coll = arm.data.collections.get(HAIR_COLLIDE_GROUP) or arm.data.collections.new(HAIR_COLLIDE_GROUP)
    coll.is_visible = False
    for b, cons, mcons in plan:
        gname, pname, g2name, mname = names(b)
        made = [(gname, b.jp + '衝', b.en + '_hc'), (pname, b.jp + '衝先', b.en + '_hcp'),
                (g2name, b.jp + '衝2', b.en + '_hc2'), (mname, b.jp + '衝中', b.en + '_hcm'),
                (f'{b.name}_hcs', b.jp + '衝先均', b.en + '_hcs'), (f'{b.name}_hcn', b.jp + '衝中均', b.en + '_hcn'),
                (f'{b.name}_hca', b.jp + '衝先錨', b.en + '_hca'), (f'{b.name}_hcma', b.jp + '衝中錨', b.en + '_hcma')]
        made += [(f'{anc}_{t[1]}', b.jp + sj + t[1], b.en + se + '_' + t[1])
                 for anc, tl, sj, se in ((f'{b.name}_hca', cons, '衝先軸', '_hcq'), (f'{b.name}_hcma', mcons, '衝中軸', '_hcmq'))
                 for t in tl if t[0] == 'capsule']
        for n, jp, en in made:
            if n not in arm.data.bones:
                continue
            coll.assign(arm.data.bones[n])
            pbn = arm.pose.bones[n]
            pbn['mmd_name_j'], pbn['mmd_name_e'] = jp, en
            pbn['levi_blender_only'] = True
        src, gpb = arm.pose.bones[b.name], arm.pose.bones[gname]
        src.rotation_mode = gpb.rotation_mode = 'QUATERNION'
        for i in range(4):        # the ghost turns as s's own pose does (its input, not its result)
            fc = gpb.driver_add('rotation_quaternion', i)
            drv = fc.driver
            drv.type = 'AVERAGE'
            v = drv.variables.new()
            v.name, v.type = 'q', 'SINGLE_PROP'
            v.targets[0].id_type, v.targets[0].id = 'OBJECT', arm
            v.targets[0].data_path = f'pose.bones["{b.name}"].rotation_quaternion[{i}]'
            for m in list(fc.modifiers):
                fc.modifiers.remove(m)
        for c in src.constraints:     # ... and takes s's own constraints (pitch gravity)
            k = gpb.constraints.new(c.type)
            k.target, k.subtarget = c.target, c.subtarget     # first: the spaces it allows depend on it
            for prop in c.bl_rna.properties:
                if not prop.is_readonly and prop.identifier not in ('rna_type', 'type', 'target', 'subtarget'):
                    setattr(k, prop.identifier, getattr(c, prop.identifier))
        for probe, tl, ghost, at, anchor in ((pname, cons, gname, 1.0, f'{b.name}_hca'),
                                             (mname, mcons, g2name, 0.5, f'{b.name}_hcma')):
            ppb = arm.pose.bones[probe]
            for test, npass in ((t, i) for i in range(HAIR_COLLIDE_PASSES) for t in tl):
                if test[0] == 'capsule':
                    _c, cname, r, dist, cap = test
                    centre = f'{anchor}_{cname}'
                    if npass == 0:
                        # the projector: the unpushed point, clamped onto the capsule's axis
                        qpb = arm.pose.bones[centre]
                        k = qpb.constraints.new('COPY_LOCATION')
                        k.name = 'Probe point'
                        k.target, k.subtarget = arm, anchor
                        k = qpb.constraints.new('LIMIT_LOCATION')
                        k.name = 'On axis'
                        k.owner_space = 'LOCAL'
                        k.use_min_x = k.use_max_x = k.use_min_z = k.use_max_z = True
                        k.use_min_y = k.use_max_y = True
                        k.min_y, k.max_y = cap.t0, cap.t1
                        k.use_transform_limit = False
                    k = ppb.constraints.new('LIMIT_DISTANCE')
                    k.name = f'{cname} {npass + 1}'
                    k.target, k.subtarget = arm, centre
                    k.limit_mode = 'LIMITDIST_OUTSIDE'
                    k.distance = dist
                    fade = _capsule_fade(b)
                    if fade is not None:
                        # the push fades out as the unpushed point nears the centre: a limb
                        # sweeping right through the hair passes through it instead of
                        # flinging it across (continuous, at most ~(1 - fade[0]) r)
                        fc = k.driver_add('influence')
                        drv = fc.driver
                        drv.type = 'SCRIPTED'
                        v = drv.variables.new()
                        v.name, v.type = 'd', 'LOC_DIFF'
                        for tg, bn in zip(v.targets, (anchor, centre)):
                            tg.id, tg.bone_target, tg.transform_space = arm, bn, 'WORLD_SPACE'
                        drv.expression = f'smoothstep({fade[0] * r:.4f}, {fade[1] * r:.4f}, d)'
                        for m in list(fc.modifiers):
                            fc.modifiers.remove(m)
                    continue
                obj, dist = test
                k = ppb.constraints.new('SHRINKWRAP')
                k.name = f'{obj.name} {npass + 1}'
                k.target = obj
                k.shrinkwrap_type = 'NEAREST_SURFACE'
                k.wrap_mode = 'OUTSIDE'
                k.distance = dist
            if tl:
                k = ppb.constraints.new('LIMIT_DISTANCE')
                k.name = 'Max push'
                k.target, k.subtarget, k.head_tail = arm, ghost, at
                k.limit_mode = 'LIMITDIST_INSIDE'
                seg_len = float((b.tail - b.head).length) * at
                turn = HAIR_COLLIDE_MAX_TURN_BY.get(b.meta.get('family'), HAIR_COLLIDE_MAX_TURN)
                k.distance = min(HAIR_COLLIDE_MAX_PUSH[b.name.startswith('後髪')],
                                 seg_len * math.tan(math.radians(turn)))
        tail_aim, mid_aim = pname, mname
        if b.name in nbrs:
            # the smoothed targets: own push x HAIR_COLLIDE_SMOOTH[0] + each neighbour's x [1]
            tail_aim, mid_aim = f'{b.name}_hcs', f'{b.name}_hcn'
            for aim, sfx in ((tail_aim, '_hcp'), (mid_aim, '_hcm')):
                apb = arm.pose.bones[aim]
                for n, w in [(b.name, HAIR_COLLIDE_SMOOTH[0])] + [(o, HAIR_COLLIDE_SMOOTH[1]) for o in nbrs[b.name]]:
                    if n + sfx not in arm.pose.bones:
                        continue        # a neighbour without probes there: no push to share
                    k = apb.constraints.new('COPY_LOCATION')
                    k.name = f'Push {n}'
                    k.target, k.subtarget = arm, n + sfx
                    k.target_space = k.owner_space = 'LOCAL'
                    k.use_offset = True
                    k.influence = w
        k = arm.pose.bones[g2name].constraints.new('DAMPED_TRACK')
        k.name = 'Tail probe'
        k.target, k.subtarget = arm, tail_aim
        k = src.constraints.new('DAMPED_TRACK')
        k.name = 'Hair collision'
        k.target, k.subtarget = arm, mid_aim
    bpy.context.view_layer.update()
    print(f'rig hair collision: {len(plan)} segments, {sum(len(t) + len(m) for _b, t, m in plan)} tests, '
          f'{len(colliders)} colliders')


def strip_blender_only(arm):
    """Remove the Blender-only hair collision (probes, ghosts, their Damped Tracks and the
    colliders) before a PMX export: MMD's physics does that job there. Also removes the
    knee's IK prebend (KNEE_IK_PREBEND), which mmd_tools would export as the knee's IK
    link limit. Returns the number of hair collision bones removed."""
    for pb in arm.pose.bones:
        for c in [c for c in pb.constraints if c.name == 'Hair collision']:
            pb.constraints.remove(c)
        for c in [c for c in pb.constraints if c.name == KNEE_PREBEND_NAME]:
            # the knee's IK prebend (Blender's solver only): mmd_tools would read it as the
            # PMX knee link's limit
            pb.driver_remove(f'constraints["{c.name}"].influence')
            pb.constraints.remove(c)
    gone =[pb.name for pb in arm.pose.bones if pb.get('levi_blender_only')]
    for n in gone:
        arm.pose.bones[n].driver_remove('rotation_quaternion')
    if arm.animation_data:          # (the capsule pushes' influence drivers on the probes)
        dead = tuple(f'pose.bones["{n}"]' for n in gone)
        for fc in [fc for fc in arm.animation_data.drivers if fc.data_path.startswith(dead)]:
            arm.animation_data.drivers.remove(fc)
    if gone:
        bpy.context.view_layer.objects.active = arm
        for o in bpy.context.view_layer.objects:
            o.select_set(o == arm)
        bpy.ops.object.mode_set(mode='EDIT')
        for n in gone:
            arm.data.edit_bones.remove(arm.data.edit_bones[n])
        bpy.ops.object.mode_set(mode='OBJECT')
    _remove_colliders()
    return len(gone)


def _remove_colliders():
    for o in [o for o in bpy.data.objects if o.get(HAIR_COLLIDER_TAG)]:
        me = o.data
        bpy.data.objects.remove(o, do_unlink=True)
        if me is not None and me.users == 0:
            bpy.data.meshes.remove(me)


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
            parent = '首'
            if HAIR_PITCH_HELPER and all(n in byname for n in HAIR_PITCH_SOURCES):
                bones.extend(_hair_pitch_helpers(byname, h))
                parent = HAIR_ARCH_BONE
            meta = {'follow': ('頭', HAIR_FOLLOW)} if HAIR_FOLLOW > 1e-4 else {}
            if HAIR_GRAVITY > 1e-4:
                meta['gravity'] = [(n, HAIR_GRAVITY) for n in ('上半身', '上半身2') if n in byname]
            if HAIR_NECK_HANG > 1e-4 and '首' in byname:
                meta['pitch_hang'] = [('首', HAIR_NECK_HANG)]
            if HAIR_ARCH_HANG > 1e-4:
                meta['arch_hang'] = [(n, HAIR_ARCH_HANG) for n in HAIR_PITCH_SOURCES if n in byname]
            bones.append(Bone(HAIR_ROOT, HAIR_ROOT, 'HairRoot', h, h + Vector((0, 0, 0.03)), parent,
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
        # (rooted at the curtain's own top when it starts below eye level: round 11's
        # under-layer starts below the head bone's fade band, and chains rooted at eye
        # level found no points there, leaving it on the nearest lock bones' envelopes)
        root_z = min(L['eye_z'], float(rest[:, 2].max()))
        chains = _sector_chains(rest, (0.0, L['head_center_y']), root_z, HAIR_SECTORS, 4, 0.10)
        if root_z < L['eye_z']:
            # the root joint (a band centroid) just over the curtain's top edge: a vertex
            # above its chain's root would hang from 頭 alone, a seam in a head turn
            chains = [(a, [Vector((j[0].x, j[0].y, max(j[0].z, root_z + 0.005)))] + list(j[1:]))
                      for a, j in chains]
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
            # (round 8: a family may hang from higher up, SIDE_HAIR_TOP: the cheek wisps end
            # only 2-4 cm below the eyes and had no chain, so a raised arm went through them)
            ftop = SIDE_HAIR_TOP.get(prefix, top)
            sel = pts[(pts[:, 0] * s > L['head_half_w'] * 0.6) & (pts[:, 2] < ftop)] if len(pts) else pts
            if len(sel) < 12 or ftop - sel[:, 2].min() < 0.04:
                continue
            nseg = 3 if ftop - sel[:, 2].min() >= 0.12 else 2
            joints = _band_chain(sel, float(sel[:, 2].max()), float(sel[:, 2].min()), nseg)
            if joints:
                bones += _chain_bones(jp, jp, en, joints, parent or hair_parent(), 0.025, 'Hair',
                                      sfx='.' + tag, jp_side=jp_side, en_sfx='_' + tag,
                                      meta=dict({'family': prefix} if prefix else {},
                                                **({'chain_weights': True} if prefix in SIDE_HAIR_CHAIN_WEIGHTS else {})))

    # skirt (+ petticoat): sectors around the body axis, hanging from the hip (the
    # petticoat thinned to DRAPE_GRID, the skirt as it is)
    pts = np.concatenate([verts('skirt'), _grid_points(verts('petticoat'), DRAPE_GRID)])
    if len(pts):
        cy = float(pts[:, 1].mean())
        chains = _sector_chains(pts, (0.0, cy), SKIRT_ROOT_Z, SKIRT_SECTORS, SKIRT_SEGMENTS, 0.08)
        drape = {}
        if SKIRT_DRAPE and chains:
            th = byname['足.L']
            drape = _skirt_drape(chains, pts, cy, np.array(th.head),
                                 np.array(th.tail) + np.array((DRAPE_KNEE_OUT, -DRAPE_KNEE_FWD, 0.0)), verts('body'),
                                 inner=verts('skirt', 'petticoat'))
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
                            lin = _drape_share(drape[k], tag, i)
                            meta = {'follow': (f'足.{tag}', round(lin, 4)),
                                    'drape': dict(drape[k], i=i, own=tag, angle=ang, hub=f'スカート{min(drape)}追従右',
                                                  above=f'スカート{k}追従左' + (f'{i - 1}' if i > 1 else ''))}
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
    pts = np.concatenate([_fit_verts(o) for o in parts.get('sleeves', [])] or [np.zeros((0, 3))])
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
# round 9: bodice ornaments lying on the shell keep their own skin sample per point (as the
# shell under them does) instead of riding one attachment point rigidly: rigid on the
# neckline's weights, the leaf cluster sank up to 7 mm into the chest in arms_up
BODICE_RIDE = ('bodice_leaves',)
# round 11: the bodice's closed bow knot straddles 上半身/下半身, and the bow loops, the last
# lacing cords and the ribbon tails all start inside it. With per-vertex weights (the knot
# was exempt from rigid islands by WAIST_STRADDLE) their cut ends came 2-9 mm out of it in
# squat, torso turns, twist_bend and lie_back_elbows. Now the knot rides one set of weights,
# the mean of the part's base weights at sample points the part gives (the knot and the loop
# stations: the bow rides as one rigid ornament), and every strand vertex inside it, or
# within KNOT_HOLD of its surface, takes the same weights; further out a strand blends back
# to its own weights over KNOT_BLEND (as a SKIN_ORNAMENTS root does). The part writes each vertex's distance outside the knot (m, negative inside; 0 everywhere on an
# object that rides the knot whole, the bow) in the point attribute named by obj[KNOT_PARAM],
# and the knot's centre and half extents, and optionally that object's blend length (m,
# default KNOT_BLEND), in obj[KNOT_PROP].
KNOT_PARAM = 'levi_knot_param'
KNOT_PROP = 'levi_knot'
KNOT_SAMPLES = 'levi_knot_samples'   # points (flat, m) whose mean weights the knot rides; else its box
KNOT_HOLD = 0.0015
KNOT_BLEND = 0.012
# Round 11 (integration review 2): the ribbon tails lying on the skirt take one field of
# (angle round the body, height) with at most four bones by construction (_tail_weights):
# no smoothing of the weights, no prune or motion refit. Smoothed 3.5 cm along the strands,
# which wander across the front chains, the tails carried 5-9 bones (three chains x three
# segments and the body); the refit picked four per vertex from the few generic samples
# that move the chains, so stations 5 mm apart landed on different chain shares (chain 14:
# 0.23 vs 0.12 on R_wave at the hip), wherever the drape tables put it: the petticoat lane's
# round-3 drape moved it to x2.09 in cross_legged, x1.68 in kneel_one / deep_lunge (round
# 10: x1.74 / 1.54 / 1.52) and a strain jitter of 0.22 in the run clip (the petticoat
# core's mechanism, PLAIN_OBJECTS). The field:
# - round the body, the two nearest skirt chains, linear in the angle (as _skirt_weights);
#   the angle is smoothed along the strands (TAIL_SMOOTH[0]): a strand zigzagging across a
#   chain's line takes its straightened course's blend (cross_legged at the tips x1.59 ->
#   x1.34 from 4 to 6 cm);
# - down each chain its segments by height (hat functions), but the first segment carries
#   alone down to u1 = TAIL_ROOT[0] chain units below the root, and the hat to the second is
#   centred on their joint (u1 .. 2 - u1): a hat that starts at a pivot stretches twice as
#   much as one centred on it;
# - the body hands over to the chains below their root, the pivot the drape turns them
#   about, by an asinh profile of the distance s below it: asinh(s / d) / asinh(s1 / d), d =
#   TAIL_ROOT[1], s1 at u1, s softened over TAIL_ROOT[2] at the root (C1 there). A point s
#   below the pivot and d in front of it moves (R - 1)(s, d) relative to the body, so the
#   hand-over stretches with share' * sqrt(s^2 + d^2), which this profile keeps level; a
#   smoothstep peaks at the same x2.1 in high_kick over 5 or 10 cm (the plain blend,
#   ROOT_BLEND). A sharper start at the root (no onset) compressed the strand just below
#   it to x0.23 in jump_tuck, a larger d raised the peak (d 3 cm: x1.93);
# - the body bones' split (上半身 / 下半身 / 上半身2: the bodice's skin sample handing over to
#   the skirt's waist by SKIRT_BAND) is smoothed along the strands (TAIL_SMOOTH[1]) and
#   blended into the bow knot (_knot_weights, over the part's 3 cm) before it hands over.
# Measured on the full model (tails alone, the old weights -> these): high_kick x1.64 ->
# 1.66, jump_tuck 1.82 -> 1.71, sit_chair 1.67 -> 1.55, kneel_one 1.68 -> 1.48, deep_lunge
# 1.68 -> 1.40, cross_legged 2.09 -> 1.45, lie_back_elbows 1.70 -> 1.58, run 1.60 -> 1.34
# (strain jitter 0.22 -> 0.12); the least compression 0.44 -> 0.38 (jump_tuck).
TAIL_FIELD = 'bodice_ribbon_tails'      # name prefix of the objects weighted by _tail_weights
TAIL_ROOT = (0.85, 0.01, 0.015)    # chain units the body hands over to the chains over; asinh scale, onset (m)
TAIL_SMOOTH = (0.06, 0.035)  # m along the strands: the angle round the body; the body bones' split


def _knot_weights(w, co, obj, part, bones):
    """(weights, pinned vertices, knot weights): `w` with the knot's rigid weights inside
    the bow knot, blended out along the strands that leave it (see KNOT_PARAM), or None for
    an object without the knot data. The pinned vertices (inside the knot or within
    KNOT_HOLD of it) get the knot's own pruned weights again after the prune (_knot_pin):
    its guide, smoothed along a strand, would otherwise fold their weights a little
    differently from the knot's (0.3-0.4 mm out of it in forward_bend / lie_back)."""
    out = _point_param(obj, co, KNOT_PARAM)
    box = obj.get(KNOT_PROP)
    if out is None or box is None or len(box) not in (6, 7):
        return None
    c, a = np.array(box[:3], dtype=float), np.array(box[3:6], dtype=float)
    blend = float(box[6]) if len(box) == 7 else KNOT_BLEND
    smp = obj.get(KNOT_SAMPLES)
    if smp is not None and len(smp) >= 3 and len(smp) % 3 == 0:
        pts = np.array(smp, dtype=float).reshape(-1, 3)
    else:
        pts = np.vstack([c, c + np.diag(a), c - np.diag(a)])
    wk = _base_weights(part, pts, bones) * _side_mask(pts, np.zeros(len(pts), dtype=int), bones, True)
    wk = wk.sum(0)
    wk = wk / max(float(wk.sum()), 1e-12)
    t = (1.0 - _smoothstep(KNOT_HOLD, KNOT_HOLD + blend, out))[:, None]
    return w * (1.0 - t) + wk[None, :] * t, out <= KNOT_HOLD, wk


def _knot_pin(idx, ww, knot, bones):
    """The pruned (idx, ww) with the knot's own pruned weights on its pinned vertices."""
    if knot is None or not knot[1].any():
        return idx, ww
    ik, wk = _prune(knot[2][None, :], bones)
    idx, ww = idx.copy(), ww.copy()
    kk = min(idx.shape[1], ik.shape[1])
    idx[knot[1]] = 0
    ww[knot[1]] = 0.0
    idx[knot[1], :kk] = ik[0, :kk]
    ww[knot[1], :kk] = wk[0, :kk]
    return idx, ww


def _tail_weights(w, co, obj, part, bones, edges):
    """(idx, ww) of a TAIL_FIELD object (see there) from its base weights `w` (side-masked,
    normalized), or None without skirt chains."""
    chains = {}
    for i, b in enumerate(bones):
        if b.group == 'Skirt' and 'chain' in b.meta:
            chains.setdefault(b.meta['chain'], []).append((b.meta['seg'], i, b))
    col = {b.name: i for i, b in enumerate(bones)}
    hip = [col[n] for n in ('上半身', '下半身') if n in col]
    if not chains or not hip:
        return None
    is_chain = np.zeros(len(bones), dtype=bool)
    for k in chains:
        for _, j, _ in chains[k]:
            is_chain[j] = True
    # the body bones' split: the base weights' body share, which below the chains' root is
    # the skirt's waist sample (_skirt_weights' rest share) until it runs out; that sample
    # from there on
    sub = [bones[j] for j in hip]
    env = np.zeros_like(w)
    env[:, hip] = _skin_sample(co, [b.name for b in sub], _envelope(co, sub))
    env /= np.maximum(env.sum(1, keepdims=True), 1e-12)
    bw = np.where(is_chain[None], 0.0, w)
    bw = (bw + 1e-3 * env) / (bw.sum(1, keepdims=True) + 1e-3)
    bw = _smooth(bw, co, edges, TAIL_SMOOTH[1])
    bw /= np.maximum(bw.sum(1, keepdims=True), 1e-12)
    knot = _knot_weights(bw, co, obj, part, bones)
    if knot is not None:
        bw = knot[0]
    # round the body: the two nearest chains, by the angle smoothed along the strands
    keys = sorted(chains, key=lambda k: chains[k][0][2].meta['angle'])
    A = np.array([chains[k][0][2].meta['angle'] for k in keys])
    cy = chains[keys[0]][0][2].meta['cy']
    th = np.arctan2(co[:, 0], co[:, 1] - cy)
    cs = _smooth(np.c_[np.cos(th), np.sin(th)], co, edges, TAIL_SMOOTH[0])
    theta = np.degrees(np.arctan2(cs[:, 1], cs[:, 0]))
    rows = np.arange(len(co))
    d_fwd = (theta[:, None] - A[None]) % 360.0
    d_bwd = (A[None] - theta[:, None]) % 360.0
    prv, nxt = d_fwd.argmin(1), d_bwd.argmin(1)
    dp, dn = d_fwd[rows, prv], d_bwd[rows, nxt]
    gap = dp + dn
    w_prv = np.where(gap > 1e-9, dn / np.maximum(gap, 1e-9), 1.0)
    u1, d, e = TAIL_ROOT
    W = np.zeros_like(w)
    rest = np.zeros(len(co))
    for c, k in enumerate(keys):
        ac = w_prv * (prv == c) + (1.0 - w_prv) * (nxt == c)
        segs = sorted(chains[k], key=lambda s: s[0])
        n = len(segs)
        zj = np.array([s[2].head.z for s in segs] + [segs[-1][2].tail.z])
        u = np.interp(-co[:, 2], np.maximum.accumulate(-zj), np.arange(n + 1.0))
        seg0 = zj[0] - zj[1]
        s = np.maximum(u, 0.0) * seg0
        s = np.sqrt(s * s + e * e) - e          # C1 onset at the root
        s1 = math.sqrt((u1 * seg0) ** 2 + e * e) - e
        share = np.clip(np.arcsinh(s / d) / np.arcsinh(s1 / d), 0.0, 1.0)
        # the first segment alone down to u1, the hat to the second centred on their joint
        um = np.interp(u, [u1, 2.0 - u1, 1.5, n + 1.0], [0.5, 1.5, 1.5, n + 1.0])
        uc = np.clip(um, 0.5, n - 0.5)
        for i, j, _ in segs:
            W[:, j] += ac * share * np.maximum(0.0, 1.0 - np.abs(uc - (i + 0.5)))
        rest += ac * (1.0 - share)
    W += bw * rest[:, None]
    # at most four bones by construction, but for the few where the knot's 上半身2 meets the
    # chains: folded continuously, no refit
    idx, ww = _prune(W, bones)
    return _knot_pin(idx, ww, knot, bones)


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
    'body': 0.009, 'head': 0.01, 'shoes': 0.012, 'accessories': 0.012, 'bodice': 0.035,
    'hair_front': 0.025, 'hair_back': 0.03, 'sleeves': 0.065, 'skirt': 0.03, 'petticoat': 0.06,
}
# Round 11: the reference edges (m) a part's smoothing radii were tuned on, one per level of the
# multilevel smoothing (_smooth_ml: the fine mesh, then each coarsening), used in place of each
# level's median edge. The body's radii (SMOOTH_RADIUS, CROTCH_SMOOTH, ARMPIT_SMOOTH,
# PRUNE_SMOOTH) were tuned on the round-10 body (r11/base), whose levels these are (measured
# with smooth_levels). 风堇's subdivided hands (~2 mm edges, over half the body's vertices)
# brought the medians to 4.3 / 6.2 / 8.6 mm, which re-tuned the whole skin (arms_up's armpit
# x1.78 -> x2.39) and, through the coarse level the crotch pass runs on, broke the hips' left /
# right symmetry (up to 0.14). The hands are also left out of the body's smoothing graph
# (_smooth_zones: they take her weights, _hand_hint, and are smoothed on their own), so away
# from the forearms the body's weights are r11/base's.
SMOOTH_REF = {'body': (0.009354644735714363, 0.011139147256875703, 0.015647158775001092,
                       0.02070159577335434, 0.028074554799480053, 0.036939761281950985,
                       0.047217178786414626, 0.0606149933215295)}
# (petticoat, round 7: 0.04 -> 0.06. Its gathered inner tiers sit ~16 cm from the axis,
# where neighbouring skirt chains are only ~6.5 cm apart, and a draped chain turning more
# than its neighbour stretched them x2.2-3.2; 0.08 made the layers part in cross_legged.)
# (body, round 9: 0.008 -> 0.009 with the fractional steps of _diffuse: 0.008 on the body's
# ~9.1 mm median edge rounded to 2 whole steps, which 0.009 now gives; 0.008's 1.5 steps
# raised the body's stretch by up to 0.05 in arms_up / spin and flipped faces in the hollows.)
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


def _smooth(w, co, edges, radius, ref=None):
    """Laplacian smoothing of the weight rows along the mesh edges, about `radius` metres.

    Each edge pulls with (median edge / its length)^2 (at most 1), so every iteration
    spreads about one median edge length in metres whatever the edge: long edges down
    a thin ribbon don't carry weights much farther than `radius`. `ref`: the reference
    edge in place of the mesh's median, or one per level (SMOOTH_REF)."""
    if radius <= 0 or not len(edges):
        return w
    # only the bones this mesh uses: the rest stay zero under any averaging
    act = np.nonzero(np.abs(w).max(0) > 0.0)[0]
    if not len(act):
        return w
    out = w.copy()
    out[:, act] = _smooth_ml(w[:, act], co, edges, radius, 0, ref)
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


def _level_ref(ref_edge, depth, median):
    """The reference edge of smoothing level `depth` (0 the mesh itself): ref_edge's (a number
    for the fine level only, or a sequence with one per level), else the level's median edge."""
    if ref_edge is None:
        return median
    seq = ref_edge if isinstance(ref_edge, (tuple, list)) else (ref_edge,)
    return float(seq[depth]) if depth < len(seq) and seq[depth] else median


def smooth_levels(co, edges, depth=8):
    """The median edge of each level of _smooth_ml's coarsening of a mesh (co, edges), as long as
    it can pair vertices: what SMOOTH_REF records for a part (e.g. the body's, from r11/base)."""
    out = []
    for _ in range(depth):
        ln, ref = _edge_ref(co, edges)
        out.append(ref)
        lab, nc = _match(co, edges, ln)
        if nc > 0.85 * len(co) or len(co) < 64:
            break
        cnt = np.bincount(lab, minlength=nc).astype(float)[:, None]
        cco = np.zeros((nc, 3))
        np.add.at(cco, lab, co)
        ce = np.stack([lab[edges[:, 0]], lab[edges[:, 1]]], 1)
        ce = ce[ce[:, 0] != ce[:, 1]]
        if not len(ce):
            break
        co, edges = cco / cnt, np.unique(np.sort(ce, 1), axis=0)
    return out


def _smooth_ml(w, co, edges, radius, depth, ref_edge=None):
    """Smoothing about `radius` metres whatever the mesh density. Within SMOOTH_DIRECT
    iterations of the plain diffusion (_diffuse) it runs directly; otherwise neighbouring
    vertices are paired (_match), the cluster averages are smoothed on the coarse graph
    (recursively), the coarse change is added back to every vertex of its cluster, and a
    short diffusion on the fine mesh (about one coarse edge) evens out the cluster steps.
    Diffusion radii add in squares, so the two passes together give `radius`. Cost stays
    about linear in the vertex count. ref_edge: the reference edge in place of the median, of
    the fine level only (a number) or one per level (SMOOTH_REF; _level_ref)."""
    ln, ref = _edge_ref(co, edges)
    ref = _level_ref(ref_edge, depth, ref)
    if ref <= 0.0:
        return w
    # fractional (round 9): a whole number of steps made a small radius jump with the mesh's
    # median edge (the body's 8 mm on its ~9.2 mm edges sat at 1.5 steps, and R8-5's denser
    # hands tipped it from 1 to 2: the small weight change behind round 8's bend-span jumps,
    # which motion_check's round-9 span measure no longer amplifies)
    iters = 2.0 * (radius / ref) ** 2
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
    if len(ce):
        cref = _level_ref(ref_edge, depth + 1, cref)
    post = min(radius * 0.7, 1.5 * max(cref, ref))      # fine-level pass: about one coarse edge
    rc = math.sqrt(max(radius ** 2 - post ** 2, 0.0))
    if len(ce):
        cw = _smooth_ml(cw, cco, ce, rc, depth + 1, ref_edge) - cw
    else:
        cw = np.zeros_like(cw)
    w = w + cw[lab]
    return _diffuse(w, co, edges, ln, ref, 2.0 * (post / ref) ** 2)


def _diffuse(w, co, edges, ln, ref, iters):
    """`iters` Laplacian steps of the weight rows along the mesh edges. A fractional count
    runs ceil(iters) equal, proportionally shorter steps (diffusion adds linearly in the
    step size), so the smoothing varies continuously with the radius and the edge length."""
    if iters <= 1e-6:
        return w
    n = int(math.ceil(iters - 1e-9))
    rate = 0.5 * iters / n
    c = np.minimum(1.0, (ref / np.maximum(ln, 1e-9)) ** 2)
    src = np.concatenate([edges[:, 0], edges[:, 1]])
    dst = np.concatenate([edges[:, 1], edges[:, 0]])
    cc = np.concatenate([c, c])
    order = np.argsort(src, kind='stable')
    src, dst, cc = src[order], dst[order], cc[order][:, None]
    verts, starts = np.unique(src, return_index=True)
    deg = np.diff(np.append(starts, len(src)))[:, None]
    w = w.copy()
    for _ in range(n):
        pull = np.add.reduceat(cc * (w[dst] - w[src]), starts, axis=0) / deg
        w[verts] += rate * pull
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


def _prune(w, bones=None, guide=None, co=None, motion=None):
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
    if CHAIN_BODY_KEEP != 1.0 and bones is not None and _chain_cloth(bones):
        # skirt family: the body bones rank as CHAIN_BODY_KEEP x their weight (see there)
        g = g * np.array([CHAIN_BODY_KEEP if b.name in MOTION_CHAIN_BODY else 1.0 for b in bones])[None]
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
    if motion is None and _MOTION_CHAIN and bones is not None and _chain_cloth(bones):
        motion = _MOTION_CHAIN
    motion = motion or _MOTION
    if co is not None and bones is not None and motion:
        ww = _motion_refit(w, idx, ww, co, bones, fold.sum(1) > 1e-9, motion)
    return idx, ww


def _chain_cloth(bones):
    """Whether `bones` are a skirt-family part's candidates (_candidates: 上半身 / 下半身 and
    the skirt chains), which _prune refits with MOTION_CHAIN_POSES as well."""
    return any(b.group == MOTION_CHAIN_GROUP for b in bones) and \
        all(b.group == MOTION_CHAIN_GROUP or b.name in MOTION_CHAIN_BODY for b in bones)


_MOTION = {}          # deform bone name -> (K, 3, 4) skinning matrices in the sample poses (build_rig)
# Skirt-family refit (round 11): of the generic samples only the few that turn the thighs,
# the torso and all chain roots together move the skirt chains, so a vertex blending three
# chains had about as many informative samples as kept weights, and its refit followed
# whatever the drape tables did in those few (neighbouring petticoat-core vertices ended
# on chain 4 vs chain 6: x3.2 in cross_legged, and any change of the drape moved the cliff).
# The skirt and petticoat are refitted with MOTION_CHAIN_POSES as well: each thigh on its
# own and both together, forward, back and out ((bone, how, deg), as MOTION_POSES), the
# skirt chains following through their drape drivers, so the kept bones match the
# unpruned blend over the drape's range instead of a few samples.
MOTION_CHAIN_GROUP = 'Skirt'          # the chains' bone group ...
MOTION_CHAIN_BODY = ('上半身', '下半身')  # ... and the body bones a skirt-family part may take
_FWD, _BACK = (0, -1, 0), (0, 1, 0)
MOTION_CHAIN_POSES = (
    (('足.L', _FWD, 45),), (('足.R', _FWD, 45),), (('足.L', _FWD, 90),), (('足.R', _FWD, 90),),
    (('足.L', _FWD, 120),), (('足.R', _FWD, 120),), (('足.L', _BACK, 30),), (('足.R', _BACK, 30),),
    (('足.L', 'side', 35),), (('足.R', 'side', 35),), (('足.L', 'side', -35),), (('足.R', 'side', -35),),
    (('足.L', _FWD, 80), ('足.R', _FWD, 80)),
    (('足.L', _FWD, 60), ('足.R', _BACK, 25)), (('足.R', _FWD, 60), ('足.L', _BACK, 25)),
)
_MOTION_CHAIN = {}    # as _MOTION, plus the chain samples (build_rig)
# Which bones a skirt-family vertex keeps (_prune): the body bones (上半身 / 下半身) rank as
# CHAIN_BODY_KEEP x their weight. Round 11: at the skirt's waist above the chain roots a
# vertex carries six bones (its chain's root, 下半身, 上半身 ~0.045, the next segment and two
# neighbouring chain roots at 0.03-0.08); 上半身 tied with the weak chain bones, so the prune
# folded it on one vertex and kept it on the next (0.005 / 0.035 on vertices 2.3 mm apart),
# and every torso turn sheared those edges (x1.53 torso_left, x1.64 twist_bend, x1.56
# look_over_shoulder; round 10 x1.33-1.38). A neighbouring chain root moves like the vertex's
# own except in a drape; 上半身 alone turns the waist in a twist. Kept, it stays at its
# smooth 0.045 (x1.17 / 1.23 / 1.18). 3 also changed the cross_legged hem (x2.07 -> x2.21).
CHAIN_BODY_KEEP = 2.0
MOTION_D = 0.01       # m: motion error that weighs as much as moving a kept weight by its own size
MOTION_TOP = 8        # strongest unpruned bones whose motion the refit matches


def _motion_refit(w, idx, ww, co, bones, folded, motion=None):
    """Re-weight the kept bones of each pruned vertex so it moves as the unpruned blend
    did in the sample poses (_motion_samples): least squares over the poses, sum 1,
    regularized toward the folded weights, the more strongly the smaller a kept weight
    is (a bone entering the set enters at zero: no jump). Folding a few % of torso weight
    on a raised upper arm into the arm moves the skin centimetres; this puts it back.
    Only vertices that lost weight in the prune are touched."""
    motion = motion or _MOTION
    rows = np.nonzero(folded)[0]
    if not len(rows):
        return ww
    shape = next(iter(motion.values())).shape
    S = np.zeros((len(bones),) + shape)
    have = np.zeros(len(bones), dtype=bool)
    for j, b in enumerate(bones):
        if b.name in motion:
            S[j] = motion[b.name]
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


# bodice pieces hand over to the skirt weights between these heights relative to the
# skirt chains' root (SKIRT_ROOT_Z). Above the root the skirt field is itself the
# 上半身/下半身 blend, so a long hand-over costs nothing and lets hanging ribbons leave the
# waist without a kink; it ends at the root, so the ribbon tails lying on the skirt take
# exactly the skirt's weights where the chains take over and fold with it over a raised
# thigh (round 6 handed over across the chains' own hand-over: two ramps in one band,
# x2.1-2.2 stretch and up to 55% of the tails inside the thigh when the skirt lifted).
# It starts just below waist_z, so nothing at the waist bow or above changes hands.
SKIRT_BAND = (0.035, 0.0)
ANKLE_BLEND = 0.03    # foot / shin blend half-width around the ankle joint height (no ANKLE_BAND)
# Round 8: the ankle pivot is the real joint inside the shoe (body.ANKLE_ROW). Shin share
# smoothstep edges (m along the shin from the pivot, + up), instep side and heel side,
# blended round the leg: the instep's skin rises in front of the joint and stays foot
# higher up; behind, the skin from the pivot up is shin, bending over the tendon to the
# heel counter's top (the counter is rigid, RIGID_FOOT). Starting the heel side at
# +0.8 / +1.6 cm, inside the counter, stretched the tendon x2.3 / x2.8 with the toes
# tucked (kneel_one) and x1.9 / x2.15 in a squat.
ANKLE_BAND = ((-0.01, 0.045), (0.0, 0.035))
# Round 8: hand share smoothstep edges (m along the hand from the wrist pivot): 10-90%
# over ~4 cm, reaching back into the forearm; the palm heel is ~97% hand (round 7:
# envelopes, 5-6 cm, 55% 1.2 cm into the palm). In pairwise review +-1.5 cm and +-2.2 cm
# read as a pinched notch at a flexed wrist; this band won 8/2 and 10/0 against round 7.
WRIST_BAND = (-0.04, 0.025)
WRIST_PARTS = ('body', '_proxy')   # parts whose skin takes WRIST_BAND
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
    for b in bones:
        # an along-limb joint without helpers (JOINT_ALONG) splits upper / lower limb alone
        if b.name.split('.')[0] in JOINT_ALONG and b.name not in joints and b.parent in col:
            joints[b.name] = []
    for lower, aux in joints.items():
        if lower not in col:
            continue
        aux.sort(key=lambda j: bones[j].meta.get('aux_share', 0.0))
        along = JOINT_ALONG.get(lower.split('.')[0])
        if aux:
            b = bones[aux[0]]
            upper = b.meta['joint_aux'][0]
            stem = b.name.split('.')[0]
        else:
            upper, stem = (bones[col[lower]].parent,), lower.split('.')[0]
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
        if along is not None:
            # along-limb partition (JOINT_ALONG): knots in metres along the limb from the
            # pivot, their own at the front, the sides and the back, interpolated round the
            # limb as a quadratic in the cosine of the direction from the axis to `forward`,
            # so neighbouring columns don't shear (each knot must stay below the next one
            # all round the limb).
            kf, ks, kb, fwd = along
            if not len(kf) == len(ks) == len(kb) == len(aux) + 2:
                raise ValueError(f'JOINT_ALONG[{lower!r}]: knots for {len(aux)} helpers need {len(aux) + 2}')
            lat = (co - np.array(lb.head)) - t[:, None] * d
            c = (lat @ np.array(fwd, dtype=float)) / np.maximum(np.linalg.norm(lat, axis=1), 1e-6)
            # per-vertex knots: the smoothsteps below run between them
            knots = [s_ + 0.5 * (f_ - b_) * c + (0.5 * (f_ + b_) - s_) * c * c for f_, s_, b_ in zip(kf, ks, kb)]
        elif scale is not None:
            # the band is wider over the front of the joint (the kneecap wraps round) and
            # narrower behind it (the hollow creases instead of pinching): t is divided by
            # the local band scale, lerped by how far round to the front the vertex is
            lat = (co - np.array(lb.head)) - t[:, None] * d
            fwd = np.array(scale[2], dtype=float)
            front = (lat @ fwd) / np.maximum(np.linalg.norm(lat, axis=1), 1e-6)
            k = scale[1] + (scale[0] - scale[1]) * _smoothstep(-1.0, 1.0, front)
            t = t / k
        if along is None:
            knots = [-before] + [bones[j].meta.get('aux_at', 0.0) for j in aux] + [after]
        steps = [_smoothstep(k0, k1, t) for k0, k1 in zip(knots, knots[1:])]
        f = [1.0 - steps[0]] + [s0 - s1 for s0, s1 in zip(steps, steps[1:])] + [steps[-1]]
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
    """Foot (足首) below the ankle, shin (ひざ) above it, blended along the shin axis about
    the ankle pivot (ANKLE_BAND: higher on the instep, where the foot's skin rises in
    front of the joint, short behind it, the heel), so a foot turn bends the leg at the
    joint inside the shoe. The laces take the same positional weights as the skin under
    them; the shoe's shell is then made rigid on the foot (RIGID_FOOT), and the skin
    inside it is foot too (the band starts above the vamp and the heel counter's top).
    Without ANKLE_BAND: a horizontal band ANKLE_BLEND about the pivot's height (round 7)."""
    col = {b.name: i for i, b in enumerate(bones)}
    for tag in 'LR':
        a, k = col.get(f'足首.{tag}'), col.get(f'ひざ.{tag}')
        if a is None or k is None:
            continue
        s = w[:, a] + w[:, k]
        if ANKLE_BAND:
            piv = np.array(bones[a].head)
            up = np.array(bones[k].head) - piv
            up /= np.linalg.norm(up)
            fwd = np.array(bones[a].tail) - piv
            fwd -= up * (fwd @ up)
            fwd /= np.linalg.norm(fwd)
            rel = co - piv
            along = rel @ up
            lat = rel - along[:, None] * up
            c = (lat @ fwd) / np.maximum(np.linalg.norm(lat, axis=1), 1e-9)
            g = _smoothstep(-1.0, 1.0, c)               # 0 behind (heel) .. 1 in front (instep)
            (fl, fh), (bl, bh) = ANKLE_BAND
            f = _smoothstep(bl + (fl - bl) * g, bh + (fh - bh) * g, along)
        else:
            f = _smoothstep(bones[a].head.z - ANKLE_BLEND, bones[a].head.z + ANKLE_BLEND, co[:, 2])
        w[:, a], w[:, k] = s * (1.0 - f), s * f


# Round 8: objects that move rigidly with the foot whatever ANKLE_BAND says (part ->
# object name prefix): the shoe's shell. Its topline rises above the ankle pivot at the
# heel counter, and blended with the shin it stretched x2.2 in a squat.
RIGID_FOOT = {'shoes': 'shoes_shell'}


def _rigid_foot(w, bones):
    """Fold each side's shin (ひざ) weight into its foot (足首)."""
    col = {b.name: i for i, b in enumerate(bones)}
    for tag in 'LR':
        a, k = col.get(f'足首.{tag}'), col.get(f'ひざ.{tag}')
        if a is not None and k is not None:
            w[:, a] += w[:, k]
            w[:, k] = 0.0


def _split_wrist(w, co, bones):
    """Hand (手首) vs forearm (ひじ, 手捩, ひじ補助) by a band WRIST_BAND along the hand
    about the wrist pivot (round 8): the palm heel moves with the hand instead of half
    following the forearm. Run before the twist split (_split_along), which then hands
    the forearm's share near the wrist to 手捩 as before. Fingers keep their weights.
    Skin only (WRIST_PARTS): the sleeves build their own arm weights."""
    if not WRIST_BAND:
        return
    col = {b.name: i for i, b in enumerate(bones)}
    for tag in 'LR':
        h = col.get(f'手首.{tag}')
        names = [n for n in (f'ひじ.{tag}', f'手捩.{tag}', f'ひじ補助.{tag}') if n in col]
        if h is None or not names:
            continue
        arm = [col[n] for n in names]
        piv = np.array(bones[h].head)
        d = np.array(bones[h].tail) - piv
        d /= np.linalg.norm(d)
        f = _smoothstep(WRIST_BAND[0], WRIST_BAND[1], (co - piv) @ d)
        fa = w[:, arm].sum(1)
        s = w[:, h] + fa
        rest = s * (1.0 - f)
        prop = np.where(fa[:, None] > 1e-9, w[:, arm] / np.maximum(fa, 1e-9)[:, None], 0.0)
        # where the arm had no weight: all to ひじ (else the first forearm bone present)
        prop[fa <= 1e-9, names.index(f'ひじ.{tag}') if f'ひじ.{tag}' in names else 0] = 1.0
        w[:, arm] = prop * rest[:, None]
        w[:, h] = s * f


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
# Round 11: 风堇's pelvis and legs are one surface through the crotch (round 10's leg tubes
# overlapped a torso block, whose bottom took both thighs half and half while each tube was
# all its own thigh: the change of hands happened between pieces, out of sight). Now the
# gusset between the inner thighs carries the thighs' change of hands, and a stride shears it:
# 0.12 m spreads it over the gusset and the inner thighs (0.09: run x2.22 -> 2.30, 0.16: x2.31,
# cross_legged x3.79), and CROTCH_TAIL cuts what reaches past the top of the other inner thigh.
# The zone (4th value: its top, m above the hip joints) covers the buttocks up to the hip
# joints' height: below its old top (the hip joints, fading over 8 cm) the pelvis / thigh
# change at the back of the buttocks stayed steep, x2.09 / 2.24 in sit_chair /
# lie_back_elbows (now x1.79 / 1.79).
CROTCH_SMOOTH = 0.12           # weight smoothing radius (m) at the crotch
CROTCH_PARTS = ('body', '_proxy')   # skin only: garments there follow the skirt chains
CROTCH_ZONE = (0.12, 0.30, 0.12, 0.06)   # half width, depth below the hip joints, vertical fade, top


def _crotch_mask(co, bones):
    """0..1: vertices at the crotch, between the thighs below the hip joints."""
    col = {b.name: i for i, b in enumerate(bones)}
    if '足.L' not in col or '足.R' not in col:
        return None
    hip_z = bones[col['足.L']].head.z
    hw, depth, fade = CROTCH_ZONE[:3]
    top = hip_z + (CROTCH_ZONE[3] if len(CROTCH_ZONE) > 3 else 0.0)
    return (1.0 - _smoothstep(hw * 0.6, hw, np.abs(co[:, 0]))) * \
        _smoothstep(hip_z - depth, hip_z - depth + fade, co[:, 2]) * \
        (1.0 - _smoothstep(top - fade, top, co[:, 2]))


# Round 11 (review): the smoothing spread each thigh's weight 12-17 cm down the other's inner
# side (the standing thigh dragged 2.6-3 cm toward a kick). _crotch_tail moves each sided
# bone's share on the wrong side of the midline to the pelvis (下半身; the hat remap then hands
# it to the hip helper) between these geodesic distances from the body's midline (m; on the
# inner thigh: from the chain under the crotch), after the smoothing. Review 3: it went to the
# own side's bone, which steepened that thigh's own share down the inner thigh: x2.12-2.26 in
# the strides; to the pelvis x2.03-2.17 at the same drag, and the crotch fit (CROTCH_FIT) takes
# them under x1.84. With 13 gusset rows the drag below z 0.66 (~5 cm under the crotch) is
# under 5 mm (4.7 mm) at 0.09 (0.08: 1.5 mm, deep_lunge x1.80; 0.095-0.10: 7-7.5 mm, x1.70.
# Holding a pelvis share at the gusset, as 风堇's own weights do, or splitting left / right
# explicitly by the geodesic distance, sheared it more: x2.2-3.3.)
CROTCH_TAIL = (0.035, 0.09)


def _geodesic_from(co, edges, src, keep, reach):
    """Distance along the edges from the `src` vertices, over the `keep` vertices only (inf
    beyond `reach` m or out of reach)."""
    import heapq
    n = len(co)
    ok = keep[edges[:, 0]] & keep[edges[:, 1]]
    e = edges[ok]
    ln = np.linalg.norm(co[e[:, 0]] - co[e[:, 1]], axis=1)
    nbr = [[] for _ in range(n)]
    for (a, b), l in zip(e.tolist(), ln.tolist()):
        nbr[a].append((b, l))
        nbr[b].append((a, l))
    d = np.full(n, np.inf)
    heap = []
    for i in np.nonzero(src & keep)[0].tolist():
        d[i] = 0.0
        heap.append((0.0, i))
    heapq.heapify(heap)
    while heap:
        di, i = heapq.heappop(heap)
        if di > d[i] or di > reach:
            continue
        for j, l in nbr[i]:
            dj = di + l
            if dj < d[j]:
                d[j] = dj
                heapq.heappush(heap, (dj, j))
    return d


def _crotch_tail(w, co, edges, bones):
    """Each .L / .R pair's share on the other side of the midline, in the crotch zone, moved
    back to its own side between CROTCH_TAIL's geodesic distances from the midline."""
    col = {b.name: i for i, b in enumerate(bones)}
    m = _crotch_mask(co, bones)
    if m is None or not m.max() > 0 or not len(edges):
        return w
    t0, t1 = CROTCH_TAIL
    zone = m > 0
    mid = np.abs(co[:, 0]) < 1e-5
    d = _geodesic_from(co, edges, mid, zone | mid, t1 + 0.02)
    v = np.nonzero(zone)[0]
    cut = _smoothstep(t0, t1, np.where(np.isfinite(d[v]), d[v], 1.0)) * m[v]
    left = co[v, 0] >= 0.0
    r = np.arange(len(v))
    W = w[v].copy()
    pel = col.get('下半身')
    for j, b in enumerate(bones):
        jr = col.get(b.name[:-2] + '.R') if b.name.endswith('.L') else None
        if jr is None:
            continue
        own, oth = np.where(left, j, jr), np.where(left, jr, j)
        moved = W[r, oth] * cut
        if pel is not None:
            W[r, pel] += moved
        else:
            W[r, own] += moved
        W[r, oth] -= moved
    out = w.copy()
    out[v] = W
    return out


# Round 11 (review 3): the crotch's weights, after the prune, are refined against generic hip
# poses (_crotch_fit). The smoothed, tail-cut, hat-remapped weights leave the change of hands
# across the gusset and down the inner thighs uneven (the gusset grid's corners, the tail band),
# and a stride stretched those edges x2.1-2.3 (high_kick, deep_lunge, run; cross_legged x3.1)
# where round 10's separate leg tubes hid the change of hands inside the pelvis block (x1.7-1.9;
# x2.44). With the fit: x1.71-1.83, cross_legged x2.33; ~45 s of the rig build. The fit
# moves weight only among each vertex's kept bones of CROTCH_FIT_BONES (the pelvis, the thighs
# and their hip helpers), never raises a thigh's share on the other side of the midline (the
# opposite-thigh drag stays as _crotch_tail left it) and keeps the rest of the skin's weights,
# minimising over CROTCH_FIT_POSES (each thigh alone and in pairs, mirrored; none of them is a
# test pose) the edges' stretch past CROTCH_FIT_STRETCH and compression under
# CROTCH_FIT_COMPRESS, faces folding over (signed area under CROTCH_FIT_FOLD of its rest), the
# weights' roughness along the edges (CROTCH_FIT_SMOOTH) and their change (CROTCH_FIT_KEEP).
CROTCH_FIT = True
CROTCH_FIT_BONES = ('下半身', '足.L', '足.R', '足補助.L', '足補助.R')
# (mirror, ((side, thigh direction, twist), ...)): each thigh turned from hanging (-Z) to the
# direction (in the pelvis' rest frame, the left thigh's; +X out, -Y forward) by the shortest
# swing, after a twist (deg) about its own axis (+ turns the left knee outward); mirror adds the
# same pose with the sides swapped (x and the twist mirrored on .R)
CROTCH_FIT_POSES = (
    (True, (('L', (0.0, -0.866, -0.5), 0.0),)),                 # flexed 60
    (True, (('L', (0.0, -0.985, 0.174), 0.0),)),                # flexed 100
    (True, (('L', (0.0, -0.766, 0.643), 0.0),)),                # flexed 130 (a high kick)
    (True, (('L', (0.0, 0.5, -0.866), 0.0),)),                  # extended 30
    (True, (('L', (0.707, 0.0, -0.707), 0.0),)),                # abducted 45
    (True, (('L', (0.0, 0.0, -1.0), 45.0),)),                   # turned out 45
    (True, (('L', (0.0, 0.0, -1.0), -45.0),)),                  # turned in 45
    (True, (('L', (0.643, -0.766, 0.0), 0.0),)),                # flexed 90, out 40
    (True, (('L', (-0.342, -0.94, 0.0), 0.0),)),                # flexed 90, across 20
    (True, (('L', (0.0, -0.985, 0.174), 0.0), ('R', (0.0, 0.643, -0.766), 0.0))),   # lunge
    (True, (('L', (0.0, -0.866, -0.5), 0.0), ('R', (0.0, 0.5, -0.866), 0.0))),      # stride
    (False, (('L', (0.0, -1.0, 0.0), 0.0), ('R', (0.0, -1.0, 0.0), 0.0))),          # seated
    (False, (('L', (0.0, -0.866, -0.5), 0.0), ('R', (0.0, -0.866, -0.5), 0.0))),
    (False, (('L', (0.64, -0.77, 0.0), 110.0), ('R', (-0.64, -0.77, 0.0), -110.0))),  # cross-legged
    (False, (('L', (0.64, -0.77, 0.0), 55.0), ('R', (-0.64, -0.77, 0.0), -55.0))),
)
CROTCH_FIT_ITERS = 900
CROTCH_FIT_STRETCH = 1.4
CROTCH_FIT_COMPRESS = 0.6
CROTCH_FIT_FOLD = 0.15
CROTCH_FIT_W = (1.0, 1.0, 20.0)     # weights of the stretch, compression and fold terms
CROTCH_FIT_SMOOTH = 0.02
CROTCH_FIT_KEEP = 0.05
_CROTCH = {}          # deform bone name -> (K, 3, 4) skinning matrices in CROTCH_FIT_POSES (build_rig)


def _crotch_samples(arm):
    """{deform bone: (K, 3, 4)} skinning matrices in CROTCH_FIT_POSES, evaluated on the real
    armature (the hip helpers follow their thighs), IK muted, the pose reset afterwards."""
    from mathutils import Matrix
    pbs = arm.pose.bones
    if '足.L' not in pbs or '足.R' not in pbs:
        return {}
    muted = [c for pb in pbs for c in pb.constraints if c.type == 'IK' and not c.mute]
    for c in muted:
        c.mute = True
    deform = [pb for pb in pbs if pb.bone.use_deform]
    out = {pb.name: [] for pb in deform}
    poses = []
    for mirror, spec in CROTCH_FIT_POSES:
        poses.append(spec)
        if mirror:
            poses.append(tuple(('R' if sd == 'L' else 'L', (-d[0], d[1], d[2]), -tw) for sd, d, tw in spec))
    for spec in poses:
        for pb in pbs:
            pb.matrix_basis.identity()
        for sd, d, tw in spec:
            pb = pbs[f'足.{sd}']
            d = np.array(d, dtype=float) / np.linalg.norm(d)
            v0 = np.array((0.0, 0.0, -1.0))
            ax = np.cross(v0, d)
            sn, cs = float(np.linalg.norm(ax)), float(v0 @ d)
            K = np.zeros((3, 3))
            if sn > 1e-9:
                ax = ax / sn
                K = np.array([[0.0, -ax[2], ax[1]], [ax[2], 0.0, -ax[0]], [-ax[1], ax[0], 0.0]])
            th = math.atan2(sn, cs)
            swing = np.eye(3) + math.sin(th) * K + (1.0 - math.cos(th)) * K @ K
            t = math.radians(tw)
            twist = np.array([[math.cos(t), -math.sin(t), 0.0], [math.sin(t), math.cos(t), 0.0], [0.0, 0.0, 1.0]])
            rest = np.array(pb.bone.matrix_local.to_3x3())
            local = rest.T @ (swing @ twist) @ rest
            pb.rotation_mode = 'QUATERNION'
            pb.rotation_quaternion = Matrix(local.tolist()).to_quaternion()
        bpy.context.view_layer.update()
        for pb in deform:
            out[pb.name].append(np.array(pb.matrix @ pb.bone.matrix_local.inverted())[:3])
    for pb in pbs:
        pb.matrix_basis.identity()
    for c in muted:
        c.mute = False
    bpy.context.view_layer.update()
    return {k: np.array(v) for k, v in out.items()}


def _mesh_tris(obj):
    """(T, 3) fan triangles of the object's polygons."""
    me = obj.data
    n = len(me.polygons)
    if not n:
        return np.zeros((0, 3), dtype=np.int64)
    tot = np.empty(n, dtype=np.int64)
    me.polygons.foreach_get('loop_total', tot)
    st = np.empty(n, dtype=np.int64)
    me.polygons.foreach_get('loop_start', st)
    lv = np.empty(len(me.loops), dtype=np.int64)
    me.loops.foreach_get('vertex_index', lv)
    out = []
    for k in range(1, int(tot.max()) - 1):
        sel = tot > k + 1
        out.append(np.stack([lv[st[sel]], lv[st[sel] + k], lv[st[sel] + k + 1]], 1))
    return np.concatenate(out) if out else np.zeros((0, 3), dtype=np.int64)


def _mirror_index(co):
    """Each vertex's mirror image across x = 0 (positions to 0.01 mm), -1 where there is none;
    a midline vertex is its own."""
    key = np.round(co * 1e5).astype(np.int64)
    at = {tuple(k): i for i, k in enumerate(key.tolist())}
    return np.array([at.get((-k[0], k[1], k[2]), -1) for k in key.tolist()], dtype=np.int64)


def _bone_mirror(bones):
    """Column permutation swapping each .L bone with its .R twin."""
    col = {b.name: i for i, b in enumerate(bones)}
    return np.array([col.get(b.name[:-2] + ('.R' if b.name.endswith('.L') else '.L'), j)
                     if b.name.endswith(('.L', '.R')) else j for j, b in enumerate(bones)], dtype=np.int64)


def _mirror_average(w, co, bones):
    """Rows of w (V, B) averaged with their mirror image's (.L / .R swapped): the skin is built
    mirror-symmetric, and its weights are made so (round 11 review 3: the multilevel smoothing's
    coarse graph pairs vertices unevenly, 0.046 at the gluteal cleft; rig_check.check_symmetry
    on r11/body-hands allows 0.02)."""
    mi = _mirror_index(co)
    ok = mi >= 0
    out = w.copy()
    out[ok] = 0.5 * (w[ok] + w[mi[ok]][:, _bone_mirror(bones)])
    return out


def _capped_simplex(y, cap, total):
    """Rows of y projected onto {0 <= x <= cap, sum x = total} (bisection on the shift)."""
    lo = (y - cap).min(1) - 1.0
    hi = y.max(1)
    for _ in range(48):
        th = 0.5 * (lo + hi)
        big = np.clip(y - th[:, None], 0.0, cap).sum(1) > total
        lo = np.where(big, th, lo)
        hi = np.where(big, hi, th)
    return np.clip(y - (0.5 * (lo + hi))[:, None], 0.0, cap)


def _crotch_fit(idx, ww, co, edges, tris, bones):
    """The kept weights (idx, ww) of the crotch zone re-weighted among CROTCH_FIT_BONES so the
    skin stretches, compresses and folds less in CROTCH_FIT_POSES (_CROTCH); see CROTCH_FIT."""
    col = {b.name: i for i, b in enumerate(bones)}
    m = _crotch_mask(co, bones)
    adj_cols = [col[n] for n in CROTCH_FIT_BONES if n in col]
    if m is None or not _CROTCH or len(adj_cols) < 3 or any(bones[j].name not in _CROTCH for j in adj_cols):
        return ww
    free = m > 0.0
    em = (free[edges[:, 0]] | free[edges[:, 1]])
    E = edges[em]
    l0 = np.linalg.norm(co[E[:, 0]] - co[E[:, 1]], axis=1)
    E, l0 = E[l0 > 1e-6], l0[l0 > 1e-6]
    T = tris[free[tris].any(1)] if len(tris) else np.zeros((0, 3), dtype=np.int64)
    vs = np.unique(np.concatenate([E.ravel(), T.ravel()]))
    if not len(vs):
        return ww
    loc = np.full(len(co), -1)
    loc[vs] = np.arange(len(vs))
    ea, eb = loc[E[:, 0]], loc[E[:, 1]]
    I, W0 = idx[vs], ww[vs].astype(float)
    n, k = I.shape
    fr = free[vs]
    # every bone's skinning matrices in the fit poses; positions of each kept slot
    S = np.zeros((len(bones),) + next(iter(_CROTCH.values())).shape)
    for j, b in enumerate(bones):
        if b.name in _CROTCH:
            S[j] = _CROTCH[b.name]
    K = S.shape[1]
    ph = np.c_[co[vs], np.ones(n)]
    P = np.einsum('nskab,nb->knsa', S[I], ph)                # (K, n, k, 3)
    adj = fr[:, None] & np.isin(I, adj_cols) & (W0 > 0.0)
    side = np.array([1 if b.name.endswith('.L') else (-1 if b.name.endswith('.R') else 0) for b in bones])
    xs = co[vs, 0]
    other = ((xs[:, None] > 0.008) & (side[I] < 0)) | ((xs[:, None] < -0.008) & (side[I] > 0))
    cap = np.where(adj, np.where(other, W0, 1.0), 0.0)
    total = np.where(adj, W0, 0.0).sum(1)
    # dense columns of the adjustable bones (smoothness term)
    cidx = np.full(len(bones), -1)
    cidx[adj_cols] = np.arange(len(adj_cols))
    ci = cidx[I]                                             # (n, k), -1: not adjustable
    # faces: rest normal and area, the bone the face turns with
    if len(T):
        ta, tb, tc = loc[T[:, 0]], loc[T[:, 1]], loc[T[:, 2]]
        nr0 = np.cross(co[T[:, 1]] - co[T[:, 0]], co[T[:, 2]] - co[T[:, 0]])
        a0 = np.linalg.norm(nr0, axis=1)
        okf = a0 > 1e-10
        ta, tb, tc, nr0, a0 = ta[okf], tb[okf], tc[okf], nr0[okf], a0[okf]
        nr0 = nr0 / a0[:, None]
        dom = np.zeros((len(ta), len(bones)))
        for t in (ta, tb, tc):
            np.add.at(dom, (np.repeat(np.arange(len(ta)), k), I[t].ravel()), W0[t].ravel())
        R = S[dom.argmax(1)][:, :, :, :3]                    # (F, K, 3, 3)
        nref = np.einsum('fkab,fb->kfa', R, nr0)
    ks, kc, kf = CROTCH_FIT_W

    def evaluate(Wv):
        X = np.einsum('ns,knsa->kna', Wv, P)
        g = np.zeros_like(X)
        e = X[:, ea] - X[:, eb]
        ln = np.linalg.norm(e, axis=2)
        r = ln / l0
        ex = np.maximum(r - CROTCH_FIT_STRETCH, 0.0)
        cx = np.maximum(CROTCH_FIT_COMPRESS - r, 0.0)
        f = ks * (ex ** 4).sum() + kc * (cx ** 4).sum()
        ge = ((4.0 * ks * ex ** 3 - 4.0 * kc * cx ** 3) / np.maximum(ln, 1e-12) / l0)[..., None] * e
        np.add.at(g, (slice(None), ea), ge)
        np.add.at(g, (slice(None), eb), -ge)
        if len(T):
            u, v = X[:, tb] - X[:, ta], X[:, tc] - X[:, ta]
            sa = np.einsum('kfa,kfa->kf', np.cross(u, v), nref) / a0
            fx = np.maximum(CROTCH_FIT_FOLD - sa, 0.0)
            f += kf * (fx ** 2).sum()
            c = (-2.0 * kf * fx / a0)[..., None]
            gu, gv = c * np.cross(v, nref), c * np.cross(nref, u)
            np.add.at(g, (slice(None), tb), gu)
            np.add.at(g, (slice(None), tc), gv)
            np.add.at(g, (slice(None), ta), -gu - gv)
        gW = np.einsum('kna,knsa->ns', g, P)
        D = np.zeros((n, len(adj_cols)))
        rows = np.repeat(np.arange(n), k)
        okc = ci.ravel() >= 0
        np.add.at(D, (rows[okc], ci.ravel()[okc]), Wv.ravel()[okc])
        dd = D[ea] - D[eb]
        f += CROTCH_FIT_SMOOTH * (dd ** 2).sum()
        gD = np.zeros_like(D)
        np.add.at(gD, ea, 2.0 * CROTCH_FIT_SMOOTH * dd)
        np.add.at(gD, eb, -2.0 * CROTCH_FIT_SMOOTH * dd)
        gW += np.where(ci >= 0, gD[np.arange(n)[:, None], np.maximum(ci, 0)], 0.0)
        f += CROTCH_FIT_KEEP * ((Wv - W0) ** 2).sum()
        gW += 2.0 * CROTCH_FIT_KEEP * (Wv - W0)
        return f, np.where(adj, gW, 0.0)

    rows = np.nonzero(adj.any(1))[0]
    # mirror pairs: each region vertex's mirror and the slot of each kept bone's twin there
    mv = _mirror_index(co)[vs]
    mj = np.where(mv >= 0, loc[np.maximum(mv, 0)], -1)
    bm = _bone_mirror(bones)
    slot = np.full((n, k), -1)
    for s_ in range(k):
        for t_ in range(k):
            hit = (mj >= 0) & (I[np.maximum(mj, 0), t_] == bm[I[:, s_]])
            slot[:, s_] = np.where(hit & (slot[:, s_] < 0), t_, slot[:, s_])
    pair = (mj >= 0) & ((slot >= 0) | (W0 <= 0.0)).all(1)
    pr = np.nonzero(pair)[0]

    def project(Y):
        Y = Y.copy()
        Y[rows] = np.where(adj[rows], _capped_simplex(Y[rows], cap[rows], total[rows]), Y[rows])
        # the poses and limits are mirror-symmetric, so is the fit (to the last bit)
        Z = Y[mj[pr][:, None], np.maximum(slot[pr], 0)]
        Y[pr] = np.where(slot[pr] >= 0, 0.5 * (Y[pr] + Z), Y[pr])
        return Y

    # spectral projected gradient (Barzilai-Borwein steps, non-monotone Armijo search)
    Wv = project(W0)
    f, g = evaluate(Wv)
    f0 = f
    best = (f, Wv)
    alpha, hist = 1e-4, [f]
    for _ in range(CROTCH_FIT_ITERS):
        d = project(Wv - alpha * g) - Wv
        gd = float((g * d).sum())
        if gd > -1e-14:
            break
        lam, fmax = 1.0, max(hist)
        while True:
            Y = Wv + lam * d
            f2, g2 = evaluate(Y)
            if f2 <= fmax + 1e-4 * lam * gd or lam < 1e-6:
                break
            lam *= 0.5
        s_, y_ = Y - Wv, g2 - g
        sy = float((s_ * y_).sum())
        alpha = min(max(float((s_ * s_).sum()) / sy, 1e-8), 1e2) if sy > 1e-18 else 1e2
        Wv, f, g = Y, f2, g2
        hist = (hist + [f])[-8:]
        if f < best[0]:
            best = (f, Wv)
    f, Wv = best
    out = ww.copy()
    out[vs] = Wv
    print(f'rig crotch fit: {len(rows)} vertices, {K} poses, objective {f0:.4g} -> {f:.4g}')
    return out


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


# Round 8: a raised arm lets the sleeve's bag fall toward the band. The bag is tied at the
# band and at the wrist, so gravity along the sleeve slides its cloth toward the band, where
# it bunches, and pulls the wrist half against the forearm; skinning alone keeps the rest
# inflation (an inflated column, round 7: "a waist and a secondary bulb above the band").
# Two corrective shape keys per side on every sleeve object, built from the rest mesh around
# the rest arm axis (shoulder -> elbow -> wrist) and the part's sleeve parameter s (0 band ..
# 1 wrist):
#   SLEEVE_GATHER_KEYS: the radius beyond r0 (the arm with a sleeve on it, ~2 cm clear of
#   the skin) is scaled by one falling profile, 1 + swell near the band down to 1 - deflate
#   toward the wrist (back to 1 in the cuff gather), with soft folds round the arm where it
#   bunches: the fullness gathers above the band and the wrist half lies along the forearm;
#   SLEEVE_SLIDE_KEYS (delta on top of the first): the arc position along the arm moves
#   toward the band by slide * sin(pi s) (tied ends), loose cloth only ('loose' m beyond r0).
# Blender drives the keys by the arm's rise: smoothstep(SLEEVE_GATHER_RISE) of the sine of
# the shoulder (腕D) -> wrist chord's elevation (world Z: gravity), 0 with the arm hanging or
# horizontal; the slide fades out as the elbow bends (SLEEVE_GATHER_STRAIGHT: the chord over
# the arm's length), since cloth can't slide through a bent elbow (arms_forward: 67 sleeve
# vertices up to 1.5 cm inside the arm), and the gather partly (SLEEVE_GATHER_BENT). The
# drivers read world positions only, so nothing jumps when 腕 passes 180 deg. The PMX keeps the keys as vertex morphs ('other'
# panel), not driven: MMD's sleeve physics hangs the drape there.
SLEEVE_GATHER = {'slide': 0.012, 'loose': 0.03, 'swell': 0.12, 'deflate': 0.8,
                 'r0': 0.05, 'elbow': (0.02, 0.09),
                 'band': (0.02, 0.16), 'shift': (0.3, 0.85), 'cuff': (0.9, 1.0),
                 'folds': (0.05, 0.035, 0.8)}
SLEEVE_GATHER_RISE = (0.0, 0.8)
SLEEVE_GATHER_KEYS = {'L': '左袖寄せ', 'R': '右袖寄せ'}
SLEEVE_SLIDE_KEYS = {'L': '左袖滑り', 'R': '右袖滑り'}
SLEEVE_GATHER_STRAIGHT = (0.55, 0.85)   # shoulder -> wrist / arm length: the slide fades out as the elbow bends
# ... and the gather to (1 - SLEEVE_GATHER_BENT[2]) of itself with the elbow folded (hands
# behind the head: the deflated bag compressed into the inside of the elbow, x0.118)
SLEEVE_GATHER_BENT = (0.3, 0.6, 0.7)
SLEEVE_RIDE_SMOOTH = 0.008   # m: the tails' sampled weights are averaged within this radius
SLEEVE_RIDE_IN = 0.75   # share of the bag's inward pull that the pieces lying on it follow


def _arm_arc(co, S, E, Wp):
    """(arc length along shoulder S -> elbow E -> wrist Wp of each point's nearest point,
    l1, l2); past the wrist it runs on along the forearm (as in _sleeve_weights)."""
    l1, l2 = float(np.linalg.norm(E - S)), float(np.linalg.norm(Wp - E))
    u = _polyline_u(co, np.array([S, E]), np.array([E, Wp]))
    a = np.where(u < 1.0, u * l1, l1 + (u - 1.0) * l2)
    past = (co - Wp) @ ((Wp - E) / l2)
    return np.where((u >= 1.999) & (past > 0), l1 + l2 + past, a), l1, l2


def _sleeve_gather_co(co, sp, S, E, Wp):
    """(still, full): gathered rest positions (SLEEVE_GATHER) of points `co` with sleeve
    parameters `sp` around the arm polyline S -> E -> Wp (one side), without and with the
    slide along the arm."""
    g = SLEEVE_GATHER
    a, l1, l2 = _arm_arc(co, S, E, Wp)
    du, df = (E - S) / l1, (Wp - E) / l2

    def axis(a):
        a = np.maximum(a, 0.0)[:, None]
        return np.where(a <= l1, S + a * du, E + (a - l1) * df)
    sp = np.clip(sp, 0.0, 1.0)
    q = co - axis(a)
    r = np.linalg.norm(q, axis=1)
    # the floor: an arm with a sleeve on it, wider round the elbow, whose skin bulges when
    # it bends (the point of a straight raised elbow showed through the deflated bag)
    r0 = g['r0'] + g['elbow'][0] * (1.0 - _smoothstep(0.0, g['elbow'][1], np.abs(a - l1)))
    # the fullness moves from the wrist half to above the band: one falling profile (no
    # waist between a band hump and a deflated wrist), back to 1 in the gathered cuff
    band = _smoothstep(*g['band'], sp)
    fall = _smoothstep(*g['shift'], sp) * (1.0 - _smoothstep(*g['cuff'], sp))
    k = 1.0 + band * (g['swell'] - (g['swell'] + g['deflate']) * fall)
    # cloth lying on the arm (the inside of a bent elbow) stays put; loose cloth slides
    slide = g['slide'] * np.sin(np.pi * sp) * _smoothstep(r0, r0 + g['loose'], r)
    if g.get('folds'):
        # soft bunching folds where the cloth gathers: ridges round the arm every `wave` m
        # of the gathered arc, wandering with the angle round the arm (measured from the
        # arm direction blended smoothly across the elbow, so the phase has no seam there)
        amp, wave, wob = g['folds']
        d = du + (df - du) * _smoothstep(l1 - 0.03, l1 + 0.03, a)[:, None]
        d /= np.linalg.norm(d, axis=1)[:, None]
        ref = np.array([0.0, 1.0, 0.0]) - d * d[:, 1:2]
        ref /= np.maximum(np.linalg.norm(ref, axis=1), 1e-9)[:, None]
        th = np.arctan2((np.cross(d, ref) * q).sum(1), (ref * q).sum(1))
        ph = 2.0 * np.pi * (a - slide) / wave + wob * np.sin(2.0 * th + 0.7) + 0.5 * wob * np.sin(3.0 * th + 2.1)
        k = k * (1.0 + amp * band * (1.0 - fall) * np.cos(ph))
    q = q * (np.where(r > r0, r0 + (r - r0) * k, r) / np.maximum(r, 1e-9))[:, None]
    return axis(a) + q, axis(a - slide) + q


def _rigid_islands(lab, co, new):
    """Small loose pieces (island labels `lab`; the bow's loops and knots: within
    RIGID_ISLAND, which skinning keeps rigid too) take their mean displacement, so they
    move, not warp."""
    out = new.copy()
    for k in np.unique(lab):
        m = lab == k
        if np.linalg.norm(co[m] - co[m].mean(0), axis=1).max() < RIGID_ISLAND:
            out[m] = co[m] + (new[m] - co[m]).mean(0)
    return out


def _ride_smooth(lab, co, ii, new):
    """The bow tails' ridden key displacement (rows ii of `new`) averaged within
    SLEEVE_RIDE_SMOOTH over the same strip (island label `lab`), as their weights are
    (_sleeve_ride_weights): the corners of the 0.5 mm thin strip sampled different bag
    vertices and folded it up as the bag gathered (round 9, idol_dance@81)."""
    if SLEEVE_RIDE_SMOOTH <= 0.0:
        return new
    out = new.copy()
    d = new[ii] - co[ii]
    tree = _kd(co[ii])
    for i in ii:
        nb = [k for _, k, _ in tree.find_range(co[i], SLEEVE_RIDE_SMOOTH) if lab[ii[k]] == lab[i]]
        out[i] = co[i] + d[nb].mean(0)
    return out


def _idw_near(tree, co, n=4):
    """(index (V, n), weight (V, n)): the n nearest points of a KD-tree for each of `co`,
    inverse-distance weights summing to 1."""
    idx, w = np.zeros((len(co), n), dtype=np.int64), np.zeros((len(co), n))
    for i, p in enumerate(co):
        for k, (_, j, d) in enumerate(tree.find_n(p, n)):
            idx[i, k], w[i, k] = j, 1.0 / max(d, 1e-4)
    return idx, w / np.maximum(w.sum(1, keepdims=True), 1e-12)


def _kd(co):
    from mathutils import kdtree
    tree = kdtree.KDTree(len(co))
    for i, p in enumerate(co):
        tree.insert(p, i)
    tree.balance()
    return tree


def _loose_labels(o, co):
    """(island label per vertex, True where the island is a long strip: >= RIGID_ISLAND)."""
    lab = _islands(len(co), _topology(o, co))
    long_ = np.zeros(len(co), dtype=bool)
    for k in np.unique(lab):
        m = lab == k
        long_[m] = np.linalg.norm(co[m] - co[m].mean(0), axis=1).max() >= RIGID_ISLAND
    return lab, long_


def _sleeve_host(objs):
    """The sleeve's bag: the sleeve object with the most vertices."""
    return max(objs, key=lambda o: len(o.data.vertices))


def _sleeve_ride_weights(objs):
    """The bow's tails (the long loose strips of a part marked obj['levi_sleeve_tails']) take
    the skin weights of the bag under them (inverse-distance blend of its 4 nearest
    vertices, the 4 largest bones kept), so they move exactly as the cloth they lie on: with
    their own positional weights they stood further from the arm than the bag and took a
    larger drape share, and a raised arm swung them through the gathered bag (round 8)."""
    if not objs:
        return
    host = _sleeve_host(objs)
    hco = _world_verts([host])
    rig_groups = set(host.get('levi_rig_groups', []))
    names = [g.name for g in host.vertex_groups if g.name in rig_groups]
    if not len(hco) or not names:
        return
    col = {g.index: names.index(g.name) for g in host.vertex_groups if g.name in rig_groups}
    hw = np.zeros((len(hco), len(names)))
    for v in host.data.vertices:
        for ge in v.groups:
            if ge.group in col:
                hw[v.index, col[ge.group]] = ge.weight
    tree = _kd(hco)
    for o in objs:
        if o is host or not o.get('levi_sleeve_tails'):
            continue
        co = _world_verts([o])
        lab, tails = _loose_labels(o, co)
        ti = np.nonzero(tails)[0]
        if not len(ti):
            continue
        idx, w = _idw_near(tree, co[ti])
        rows = np.zeros((len(co), len(names)))
        rows[ti] = (hw[idx] * w[:, :, None]).sum(1)
        # one set of weights across the strip's width and thickness (a strip whose corners
        # sampled different bag vertices tore, x2.1): averaged within SLEEVE_RIDE_SMOOTH
        own = _kd(co[ti])
        mine = set(o.get('levi_rig_groups', []))
        groups = {g.name: g for g in o.vertex_groups if g.name in mine}
        for i in ti:
            nb = [ti[k] for _, k, _ in own.find_range(co[i], SLEEVE_RIDE_SMOOTH) if lab[ti[k]] == lab[i]]
            row = rows[nb].mean(0)
            keep = np.argsort(row)[::-1][:4]
            keep = keep[row[keep] > 1e-6]
            if not len(keep):
                continue      # nothing under it: keep its own weights
            for g in groups.values():
                g.remove([int(i)])
            for j, wv in zip(keep, row[keep] / row[keep].sum()):
                g = groups.get(names[j]) or o.vertex_groups.new(name=names[j])
                groups[names[j]] = g
                g.add([int(i)], float(wv), 'REPLACE')
        o['levi_rig_groups'] = sorted(mine | set(groups))


def _sleeve_gather(arm, objs, bones):
    """SLEEVE_GATHER: the corrective keys on the sleeve objects and their Blender drivers."""
    if not SLEEVE_GATHER or not objs:
        return
    by = {b.name: b for b in bones}
    lo, hi = SLEEVE_GATHER_RISE
    s0, s1 = SLEEVE_GATHER_STRAIGHT
    b0, b1, bk = SLEEVE_GATHER_BENT
    # the bag (the sleeve object with the most vertices) is gathered by its own sleeve
    # parameter; the pieces lying on it (the bow's tails, the frill, the cuff) ride the bag's
    # displacement at their 4 nearest bag vertices, so a tail standing 1-2 mm off the cloth
    # stays on it (by their own projected parameter they sank into the deflated bag)
    host = _sleeve_host(objs)
    hco = _world_verts([host])
    hsp = _sleeve_param(host, hco)
    if hsp is None or not len(hco):
        print(f'rig: {host.name}: no sleeve parameter, no gather keys')
        return
    tree = _kd(hco)
    hmove = {}
    for o in [host] + [o for o in objs if o is not host]:
        co = _world_verts([o])
        if not len(co):
            continue
        mw_inv = np.array(o.matrix_world.inverted())
        near = None if o is host else _idw_near(tree, co)
        lab = _islands(len(co), _topology(o, co))
        for tag, sd, _ in SIDES:
            up = deform_arm(by, tag)
            src = [by.get(n) for n in (up, f'ひじ.{tag}', f'手首.{tag}')]
            if None in src:
                continue
            S, E, Wp = (np.array(b.head) for b in src)
            reach = float(np.linalg.norm(E - S) + np.linalg.norm(Wp - E))
            side = co[:, 0] * sd > 0.0
            ii = np.nonzero(side)[0]
            still, full = co.copy(), co.copy()
            if o is host:
                if len(ii):
                    still[ii], full[ii] = _sleeve_gather_co(co[ii], hsp[ii], S, E, Wp)
                hmove[tag] = (still - co, full - co)
            elif tag in hmove and len(ii):
                idx, w = near[0][ii], near[1][ii]
                a, l1, _ = _arm_arc(co[ii], S, E, Wp)
                ax = np.where((a <= l1)[:, None], S + np.maximum(a, 0.0)[:, None] * (E - S) / l1,
                              E + (a - l1)[:, None] * (Wp - E) / np.linalg.norm(Wp - E))
                rd = co[ii] - ax
                rd /= np.maximum(np.linalg.norm(rd, axis=1), 1e-9)[:, None]
                for out, mv in ((still, hmove[tag][0]), (full, hmove[tag][1])):
                    dlt = (mv[idx] * w[:, :, None]).sum(1)
                    # where the bag pulls in, a piece on it follows only SLEEVE_RIDE_IN of
                    # the way, so it stays on the outside
                    inward = np.maximum(-(dlt * rd).sum(1), 0.0)
                    out[ii] = co[ii] + dlt + (1.0 - SLEEVE_RIDE_IN) * inward[:, None] * rd
            still, full = _rigid_islands(lab, co, still), _rigid_islands(lab, co, full)
            if o is not host and o.get('levi_sleeve_tails') and len(ii):
                still, full = _ride_smooth(lab, co, ii, still), _ride_smooth(lab, co, ii, full)
            rise = f'smoothstep({lo!r}, {hi!r}, (zw - zs) / max(d, 1e-6))'
            keys = [(SLEEVE_GATHER_KEYS[tag], still,
                     f'{rise} * (1.0 - {bk!r} * (1.0 - smoothstep({b0!r}, {b1!r}, d / {reach!r})))'),
                    # the slide is a separate key (its delta on top of the first), only
                    # with the elbow fairly straight: shoulder -> wrist over the arm's length
                    (SLEEVE_SLIDE_KEYS[tag], co + (full - still),
                     f'{rise} * smoothstep({s0!r}, {s1!r}, d / {reach!r})')]
            for name, new, expr in keys:
                old = o.data.shape_keys.key_blocks.get(name) if o.data.shape_keys else None
                if np.abs(new - co).max() < 1e-4:
                    if old is not None:       # left from an earlier build
                        o.shape_key_remove(old)
                    continue
                if o.data.shape_keys is None:
                    o.shape_key_add(name='Basis', from_mix=False)
                kb = old or o.shape_key_add(name=name, from_mix=False)
                kb.data.foreach_set('co', (new @ mw_inv[:3, :3].T + mw_inv[:3, 3]).ravel())
                kb.value = 0.0
                kb.driver_remove('value')
                drv = kb.driver_add('value').driver
                drv.type = 'SCRIPTED'
                # the deforming arm (腕D under the shrug): the keys are built around it
                for vn, bn in (('zw', f'手首.{tag}'), ('zs', up)):
                    v = drv.variables.new()
                    v.name, v.type = vn, 'TRANSFORMS'
                    t = v.targets[0]
                    t.id, t.bone_target = arm, bn
                    t.transform_type, t.transform_space = 'LOC_Z', 'WORLD_SPACE'
                v = drv.variables.new()
                v.name, v.type = 'd', 'LOC_DIFF'
                for t, bn in zip(v.targets, (f'手首.{tag}', up)):
                    t.id, t.bone_target = arm, bn
                    t.transform_space = 'WORLD_SPACE'
                drv.expression = expr


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


# Nested cloth layers in separate objects (round 11: the petticoat's three frill tiers):
# after each object's own smoothing, every vertex's weights are blended toward
# the other layers' weights at their LAYER_K nearest vertices within LAYER_REACH (by
# (1 - d / reach) ** 2, so a layer sewn on, d = 0, takes the mean and the share fades out
# continuously where the layers part), LAYER_ITERS times, the change smoothed along each
# layer (LAYER_SMOOTH). Smoothed apart, each object's
# weights depend on where its own surface ends, and layers 3-4 mm apart crossed in lifted-
# leg poses (one weight field of angle and height shared by all the objects instead mixed
# 5-6 chain bones round the narrow hips and stretched the core x4-5 in high_kick). The
# core, sewn to the middle tier, keeps its own: shared, its sparse rings' pruned weights
# carried their steps into the tier's seam (x2.7 in walk). Since the integration of round
# 11 the core takes the plain blend (PLAIN_OBJECTS), and the tiers' weights at their
# seams on it (PLAIN_SEAM).
LAYER_PARTS = {'petticoat': 'petticoat_tier'}    # part -> name prefix of its layer objects
LAYER_REACH = 0.012
LAYER_K = 6
LAYER_ITERS = 2
LAYER_SMOOTH = 0.02  # m: the blend's change is smoothed along each layer (no steps where the nearest vertices switch)
_LAYER_SRC = {}      # part -> its objects (build_rig)
_LAYER = {}          # (part, bone names) -> {object name: shared weights}
# Skirt-family objects weighted by the plain angle x height blend of _skirt_weights alone:
# no smoothing, so at most four bones (two chains x two segments) by construction, and no
# prune or motion refit (_plain_weights). Round 11: the petticoat core's sparse rings,
# smoothed 6 cm, carried 6-12 bones per vertex; the refit picked four of them per vertex
# from the few generic samples that move the chains, so neighbouring vertices could land on
# different chains (chain 4 vs chain 6: x3.2 in cross_legged, x2.9 in lie_back_elbows),
# and where they did changed with every drape table (a skirt edit under the right hand
# moved the cliff onto the core). The plain blend stretches the core x1.6-2.0 in the same
# poses and does not depend on the drape at all.
PLAIN_OBJECTS = ('petticoat_core',)
# Where a layer (LAYER_PARTS) is sewn on, the plain object takes that layer's weights
# instead: those of its nearest layer vertex within PLAIN_SEAM[0], back to the plain blend
# by PLAIN_SEAM[1] (smoothstep), pruned and refitted like the layer's (_prune); on the
# petticoat core that is the ring the inner tier hangs from, so the seams stay as closed as
# round 10's (0.3-1 cm in the poses; the tiers' tops stood 1.5-2 cm off a fully plain core
# in walk and run). Wider bands mixed the two fields over the core's sparse rings (x2.4
# in cross_legged over 4 cm); blending the tiers to the plain blend near the core instead
# put the change of field into the visible frill (x2.0 and a strain jitter major at the
# front hem in the run clip over 2.5 cm, x3.3 over 1 cm).
PLAIN_SEAM = (0.006, 0.012)
# Round 11 (integration review 3): skirt-family layers whose weights are one analytic field of
# (angle round the body, height) instead of surface-smoothed per object: (name prefix,
# B-spline width in chain steps, ramp (chain units below the last segment's middle)). Round
# the ring a vertex blends the nearest chains by a quadratic B-spline of its angle (C1, a
# partition of unity: about (1/8, 3/4, 1/8) at a chain, halves midway, at most four chains;
# knots 1.05 chain steps apart: 1.0 left the tuck jump's inner hem x1.94, 1.1 the run's x1.83)
# where it rides the last segment alone, handing over within the ramp to the plain linear
# blend of the two nearest chains above it (where it also blends two segments), so it keeps
# at most four bones by construction: no smoothing, prune or refit, the same weights at the
# same (angle, height) on every tier (the nested tiers move together, the core's seam takes
# them too, PLAIN_SEAM). Smoothed along their own bells and lobes, then shared, pruned and
# refitted, the tiers' weights had the same mean profile round the ring but steps of +-20% in
# their local slope from lobe to lobe; the worst stretch sat wherever a step met the largest
# difference between two chains (the front hem in walk x1.81, a seated side hem x1.94), and
# the inner tiers crossed each other (cross_legged 89 face pairs, run_r 14, run 11; now 0).
# None: the tiers are smoothed along their own surfaces and shared (LAYER_PARTS).
TIER_FIELD = ('petticoat_tier', 1.05, (0.0, 0.25))


def _bspline2(x):
    """Quadratic B-spline (support |x| < 1.5, sum 1 over integer shifts)."""
    x = np.abs(x)
    return np.where(x < 0.5, 0.75 - x * x, np.where(x < 1.5, 0.5 * (1.5 - x) ** 2, 0.0))


def _tier_field(co, bones):
    """(V, B) weights of a TIER_FIELD layer at world points co (see there)."""
    _, width, ramp = TIER_FIELD
    chains = {}
    for i, b in enumerate(bones):
        if b.group == 'Skirt' and 'chain' in b.meta:
            chains.setdefault(b.meta['chain'], []).append((b.meta['seg'], i, b))
    keys = sorted(chains, key=lambda k: chains[k][0][2].meta['angle'])
    A = np.array([chains[k][0][2].meta['angle'] for k in keys])
    cy = chains[keys[0]][0][2].meta['cy']
    K, n = len(keys), len(chains[keys[0]])
    step = 360.0 / K
    d = (np.degrees(np.arctan2(co[:, 0], co[:, 1] - cy))[:, None] - A[None] + 180.0) % 360.0 - 180.0
    hat = np.maximum(0.0, 1.0 - np.abs(d) / step)
    hat /= np.maximum(hat.sum(1, keepdims=True), 1e-12)
    bs = _bspline2(d / (step * width))
    bs /= np.maximum(bs.sum(1, keepdims=True), 1e-12)
    # one height coordinate per vertex (along the hat-blended chains' joints), so every chain
    # takes the same split between its segments
    U = np.zeros((len(co), K))
    for c, k in enumerate(keys):
        segs = sorted(chains[k], key=lambda s: s[0])
        zj = np.array([s[2].head.z for s in segs] + [segs[-1][2].tail.z])
        U[:, c] = np.interp(-co[:, 2], np.maximum.accumulate(-zj), np.arange(n + 1.0))
    u = (U * hat).sum(1)
    m = _smoothstep(n - 0.5 + ramp[0], n - 0.5 + ramp[1], u)
    ang = (1.0 - m)[:, None] * hat + m[:, None] * bs
    uc = np.clip(u, 0.5, n - 0.5)
    W = np.zeros((len(co), len(bones)))
    for c, k in enumerate(keys):
        for i, j, _ in chains[k]:
            W[:, j] += ang[:, c] * np.maximum(0.0, 1.0 - np.abs(uc - (i + 0.5)))
    return W


def _tier_field_weights(co, bones):
    """(idx, ww) of a TIER_FIELD layer: its field's (at most MAX_INFLUENCE) bones."""
    W = _tier_field(co, bones)
    k = min(MAX_INFLUENCE, W.shape[1])
    idx = np.argsort(-W, axis=1, kind='stable')[:, :k]
    ww = np.take_along_axis(W, idx, axis=1)
    return idx, ww / np.maximum(ww.sum(1, keepdims=True), 1e-12)


def _plain_weights(w, co=None, part=None, bones=None):
    """(idx, ww) of a PLAIN_OBJECTS mesh: the MAX_INFLUENCE largest weights of each row,
    renormalized (no fold, no refit: the plain blend has at most that many bones), except
    near a layer of its part (PLAIN_SEAM), whose weights it takes there and prunes as the
    layer's own (_prune, guided by themselves)."""
    k = min(MAX_INFLUENCE, w.shape[1])
    if co is not None and part in LAYER_PARTS and PLAIN_SEAM:
        from mathutils.kdtree import KDTree
        shared = _layer_shared(part, bones)
        objs = [o for o in _LAYER_SRC.get(part, []) if o.name in shared]
        if objs:
            lco = np.concatenate([_world_verts([o]) for o in objs])
            lw = np.concatenate([shared[o.name] for o in objs])
            tree = KDTree(len(lco))
            for i, p in enumerate(lco):
                tree.insert(p, i)
            tree.balance()
            hit = [tree.find(p) for p in co]
            j = np.array([h[1] for h in hit])
            d = np.array([h[2] for h in hit])
            s = 1.0 - _smoothstep(PLAIN_SEAM[0], PLAIN_SEAM[1], d)
            w = (1.0 - s)[:, None] * w + s[:, None] * lw[j]
            near = s > 0.0
            if near.any():
                idx = np.argsort(-w, axis=1, kind='stable')[:, :k]
                ww = np.take_along_axis(w, idx, axis=1)
                ww = ww / np.maximum(ww.sum(1, keepdims=True), 1e-12)
                pi, pw = _prune(w[near], bones, None, co[near])
                idx[near], ww[near] = pi, pw
                return idx, ww
    idx = np.argsort(-w, axis=1, kind='stable')[:, :k]
    ww = np.take_along_axis(w, idx, axis=1)
    return idx, ww / np.maximum(ww.sum(1, keepdims=True), 1e-12)


def _layer_shared(part, bones):
    """{object name: weights} of a layered part: each object's smoothed plain weights, then
    blended toward the other objects' (see LAYER_PARTS)."""
    from mathutils.kdtree import KDTree
    key = (part, tuple(b.name for b in bones))
    if key in _LAYER:
        return _LAYER[key]
    objs = [o for o in _LAYER_SRC.get(part, []) if len(o.data.vertices) and o.name.startswith(LAYER_PARTS[part])]
    if TIER_FIELD and all(o.name.startswith(TIER_FIELD[0]) for o in objs):
        _LAYER[key] = {o.name: _tier_field(_world_verts([o]), bones) for o in objs}
        return _LAYER[key]
    co, w, edges = {}, {}, {}
    for o in objs:
        c = _world_verts([o])
        edges[o.name] = _topology(o, c)
        ww = _base_weights(part, c, bones)
        ww = ww / np.maximum(ww.sum(1, keepdims=True), 1e-12)
        co[o.name], w[o.name] = c, _smooth(ww, c, edges[o.name], SMOOTH_RADIUS.get(part, DEFAULT_SMOOTH))
    own = dict(w)
    near = {}       # (a, b) -> (indices (V, K), factors (V, K)) of b's vertices near a's
    for b in co:
        tree = KDTree(len(co[b]))
        for i, p in enumerate(co[b]):
            tree.insert(p, i)
        tree.balance()
        for a in co:
            if a == b:
                continue
            idx = np.zeros((len(co[a]), LAYER_K), dtype=np.int64)
            f = np.zeros((len(co[a]), LAYER_K))
            for v, p in enumerate(co[a]):
                for k, (_, i, d) in enumerate(tree.find_n(p, LAYER_K)):
                    if d < LAYER_REACH:
                        idx[v, k], f[v, k] = i, (1.0 - d / LAYER_REACH) ** 2 / LAYER_K
            near[(a, b)] = (idx, f)
    for _ in range(LAYER_ITERS):
        new = {}
        for a in w:
            acc, den = w[a].copy(), np.ones(len(w[a]))
            for b in w:
                if b == a:
                    continue
                idx, f = near[(a, b)]
                acc += np.einsum('vk,vkb->vb', f, w[b][idx])
                den += f.sum(1)
            new[a] = acc / den[:, None]
        w = new
    for a in w:
        w[a] = own[a] + _smooth(w[a] - own[a], co[a], edges[a], LAYER_SMOOTH)
        w[a] = np.maximum(w[a], 0.0)
        w[a] /= np.maximum(w[a].sum(1, keepdims=True), 1e-12)
    _LAYER[key] = w
    return w


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
            t = _smoothstep(SKIRT_ROOT_Z + SKIRT_BAND[0], SKIRT_ROOT_Z + SKIRT_BAND[1], co[:, 2])[:, None]
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
    if part in WRIST_PARTS:
        _split_wrist(w, co, bones)
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


# Round 11: the body's hands carry 风堇's own weights (levi/parts/_body_hand.py) as hints:
# float point attributes, named by obj[HAND_HINT_PROP] = {attribute: her bone name without
# side}, summing to a in 0..1 (1 on her hand and forearm stub, falling to 0 across the bridge
# to the procedural arm). _hand_hint blends them in last (after the smoothing and the finger
# rule), so her finger webs, knuckles and wrist deform as she was weighted. Her staged twist
# 手捩k (付与 k/4 of 手捩, children of ひじ) maps onto our 手捩 / ひじ split by that share.
HAND_HINT_PROP = 'levi_hand_weights'
HINT_TWIST = {'手捩1': 0.25, '手捩2': 0.5, '手捩3': 0.75, '手捩': 1.0}
HINT_FALLBACK = {'手捩': 'ひじ'}     # a missing bone's share goes here (fingers: 手首)
# m: her weights are smoothed this far over the hand (on its own ~2 mm edges): her joint blends
# were drawn on a cage ~4x coarser, and the subdivided crease edges at a curled finger's root
# stretched x1.88 and folded to x0.08 in the fist pose (3 mm: x1.48 / x0.11; 5 mm: x1.53 /
# x0.12, the knuckles still defined)
HINT_SMOOTH = 0.005
# Integration fix: the smoothed hints that leak past the bridge are cut below this. The smoothing
# runs over the whole skin, and its tail reached the elbow, 13 cm up the arm, as 1e-35 of ひじ /
# 手捩. That was enough to win _prune's tie between bones it folds to exactly zero, which it breaks
# by column order. At single vertices of the inner elbow ひじ (weight 0) then took the 4th slot
# from 上半身. Where 上半身 is kept, the motion refit (_motion_refit) gives it the vertex's ~2%
# torso share; where ひじ is kept, nothing carries it. So the share dropped to 0 between
# neighbours: x1.83 in dance_point, x1.88 in reach_up_back, x1.82 in dance_sway (round 10:
# x1.6-1.7). Cut, the inner elbow's weights are round 10's again.
HINT_EPS = 1e-9


def _hints(obj, n):
    """[(her bone name, (n,) weights)] of the hand hint attributes of `obj` (HAND_HINT_PROP)."""
    out = []
    for attr_name, bone in dict(obj.get(HAND_HINT_PROP) or {}).items():
        attr = obj.data.attributes.get(attr_name)
        if attr is None or attr.domain != 'POINT' or len(attr.data) != n:
            continue
        v = np.empty(n)
        attr.data.foreach_get('value', v)
        if v.any():
            out.append((bone, v))
    return out


def _hint_zone(obj, n):
    """(n,) bool: the vertices carrying hand weight hints (HAND_HINT_PROP: 风堇's hands, their
    stubs and bridges), else None."""
    z = np.zeros(n, dtype=bool)
    for _, v in _hints(obj, n):
        z |= v > 0.0
    return z if z.any() else None


def _smooth_zones(w, co, edges, radius, ref, zone):
    """_smooth with the `zone` vertices (_hint_zone) split off: the rest of the mesh is smoothed
    on its own graph against `ref` (SMOOTH_REF), the zone on its own graph against its own
    medians, so nothing outside the zone sees its density (the multilevel smoothing's pairing
    and medians are global) and the zone keeps its own smoothing in metres."""
    if zone is None:
        return _smooth(w, co, edges, radius, ref)
    out = w.copy()
    for m, r in ((~zone, ref), (zone, None)):
        idx = np.nonzero(m)[0]
        if not len(idx):
            continue
        new = -np.ones(len(co), dtype=np.int64)
        new[idx] = np.arange(len(idx))
        e = edges[m[edges[:, 0]] & m[edges[:, 1]]]
        out[idx] = _smooth(w[idx], co[idx], new[e], radius, r)
    return out


def _hand_hint(obj, w, co, bones, edges=None):
    """w <- (1 - a) w + hint on the vertices carrying hand weight hints (HAND_HINT_PROP),
    the hints smoothed HINT_SMOOTH along the surface (`edges`)."""
    hs = _hints(obj, len(co))
    if not hs:
        return w
    col = {b.name: j for j, b in enumerate(bones)}
    H = np.zeros_like(w)
    left = co[:, 0] >= 0.0
    for bone, v in hs:
        k = HINT_TWIST.get(bone)
        targets = [('手捩', k), ('ひじ', 1.0 - k)] if k is not None else [(bone, 1.0)]
        for tag, m in (('L', left), ('R', ~left)):
            for name, share in targets:
                j = col.get(f'{name}.{tag}')
                if j is None:
                    j = col.get(f"{HINT_FALLBACK.get(name, '手首')}.{tag}")
                if j is not None and share > 0.0:
                    H[m, j] += v[m] * share
    a = H.sum(1)
    if not a.any():
        return w
    if edges is not None and len(edges) and HINT_SMOOTH > 0:
        inside = (a[edges[:, 0]] > 0.0) & (a[edges[:, 1]] > 0.0)
        ref = _edge_ref(co, edges[inside])[1] if inside.any() else 0.0
        if ref > 0.0:
            H = _smooth(H, co, edges, HINT_SMOOTH, ref)
            H[H < HINT_EPS] = 0.0
            a = H.sum(1)
    a = np.clip(a, 0.0, 1.0)
    out = w * (1.0 - a)[:, None] + H
    s = out.sum(1, keepdims=True)
    out = np.where(s > 1e-12, out / np.maximum(s, 1e-12), w)
    return _palm_crease(obj, out, co, bones, edges, a > 0.0)


# Integration fix (fist). On the palm side of each knuckle, the split between the hand (手首)
# and the finger's root bone (親指０, X１) is relaxed by PALM_RELAX umbrella steps (0.5 each,
# over the hand's ~2 mm edges). This applies where that bone pair holds at least half of the
# weight (fading in up to 90%, so the vertices where it stops do not jump). It fades to nothing across PALM_SIDE (m) about the plane through the wrist pivot
# normal to the palm (the rig's palm normal: the hand direction x the index - little knuckle
# line), so the knuckles on the back keep her defined blend. In the fist, the palm-side crease
# at the finger roots folded into the finger: 9 faces per hand turned > 120 deg, and the edges
# compressed to x0.14. Per hand, after the prune:
#   steps  flipped  compress  stretch
#   0      9        x0.14     x1.50
#   5      2        x0.15     x1.53
#   10     1        x0.17     x1.54
#   20     0        x0.17     x1.54
#   35     0        x0.20     x1.54
# Sharpening the split instead (smoothstep 0.2-0.8 of the share) flipped 54 faces.
PALM_RELAX = 35
PALM_SIDE = 0.006
PALM_ROOTS = ('親指０', '人指１', '中指１', '薬指１', '小指１')


def _palm_crease(obj, w, co, bones, edges, zone):
    """PALM_RELAX on the hand weights `w` of the hint `zone` (_hand_hint)."""
    F = _stored_fingers([obj])
    J = obj.get('levi_joints') or {}
    if not PALM_RELAX or not F or 'wrist' not in J or edges is None or not len(edges):
        return w
    col = {b.name: j for j, b in enumerate(bones)}
    wr0 = np.array(tuple(J['wrist']), np.float64)
    d = np.array(F['中指'][0]) - wr0
    d /= np.linalg.norm(d)
    kn = np.array(F['人指'][0]) - np.array(F['小指'][0])
    kn -= d * (kn @ d)
    palm = np.cross(d, kn)
    palm /= np.linalg.norm(palm)
    w = w.copy()
    for tag, sx in (('L', 1.0), ('R', -1.0)):
        h = col.get(f'手首.{tag}')
        if h is None:
            continue
        half = zone & (co[:, 0] * sx > 0.0)
        side = ((co * np.array([sx, 1.0, 1.0])) - wr0) @ palm
        gate = np.clip(side / PALM_SIDE, -1.0, 1.0) * 0.5 + 0.5
        for root in PALM_ROOTS:
            j = col.get(f'{root}.{tag}')
            if j is None:
                continue
            tot = w[:, h] + w[:, j]
            on = half & (tot > 0.5)
            if not on.any():
                continue
            share = np.where(on, w[:, j] / np.maximum(tot, 1e-12), 0.0)
            rate = 0.5 * gate * _smoothstep(0.5, 0.9, tot)    # none where the pair's hold ends
            e = edges[on[edges[:, 0]] & on[edges[:, 1]]]
            cnt = np.bincount(e.ravel(), minlength=len(co)).astype(np.float64)
            for _ in range(PALM_RELAX):
                acc = np.bincount(e[:, 0], share[e[:, 1]], len(co)) + np.bincount(e[:, 1], share[e[:, 0]], len(co))
                avg = np.where(cnt > 0, acc / np.maximum(cnt, 1.0), share)
                share = np.where(on, share + rate * (avg - share), share)
            w[on, j] = tot[on] * share[on]
            w[on, h] = tot[on] * (1.0 - share[on])
    return w


def _island_rules(w, co, labels, bones, part):
    """Per loose part: a finger part belongs to its own finger chain only (neighbouring
    finger envelopes overlap at ~1 cm), and small ornaments (bows, leaves, beads) take
    their island's average weights so they move as one piece. Labels may split a loose
    part into finger regions (_part_labels): the finger rule then holds per region."""
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
# Round 11: the halter's straps end tucked under the bodice's top rim, and its X strands end
# on the straps. With the skin's weights the tucked ends took the clavicle (肩), which the
# bodice over them does not have (its four largest bones after a 3.5 cm smoothing), so a
# raised arm drew them out from under the rim (19-23 of 37 tucked vertices uncovered in
# hands_behind_head, dance_heart, idol_dance@48); and the X strands, smoothed along their own
# cord, came up to 4.4 mm off the strap they end on. The part marks both with point
# attributes (named by obj['levi_cord_ride'] / obj['levi_cord_join']): the tucked ends take
# the bodice's own weights (HALTER_RIDE_PART is skinned first, SKIN_LATE), and each strand's
# end takes the weights of the strap beside it.
HALTER_RIDE_PART = 'bodice'
HALTER_RIDE_K = 8        # nearest bodice vertices averaged (inverse distance, softened by SKIN_SOFT)
HALTER_JOIN_K = 24       # nearest strap vertices (three rings) a joined strand vertex takes its weights from ...
HALTER_JOIN_SOFT = 0.01   # ... inverse distance, softened by this (m): every vertex of a strand ring sees
                          # the same set (with 2 rings softened by 3 mm the ring's weights differed by ~1 %, and
                          # a raised arm's stage bones, ~8 cm away, flattened the ring to x0.05 in idol_dance@80)
SKIN_LATE = ('accessories',)   # parts skinned after the other garments (the halter reads the bodice)
# One set of weights per cord section: the shoulder stage bones' turn moves a chest point
# ~12 cm, so vertices of one 2.8 mm section ~1.5 % apart in them flattened an X strand's
# section at its junction to x0.05 in idol_dance@80. The strand's join is looked up, and the
# prune's motion refit run, at each vertex's position smoothed along the surface by this (m),
# about its section's centre.
HALTER_REFIT_AT = 0.004


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


def _part_skin(part, skip=()):
    """(points (N, 3), bone names, weights (N, B)) of the skinned meshes of `part` (its
    collection; object-name prefixes `skip` left out), or None if none is skinned yet."""
    col = bpy.data.collections.get(part)
    if col is None:
        return None
    pts, rows, names = [], [], {}
    for o in sorted(col.all_objects, key=lambda o: o.name):
        mine = set(o.get('levi_rig_groups', []))
        if o.type != 'MESH' or not mine or o.name.startswith(tuple(skip)) or not len(o.data.vertices):
            continue
        gn = {g.index: g.name for g in o.vertex_groups if g.name in mine}
        for v in o.data.vertices:
            rows.append([(names.setdefault(gn[g.group], len(names)), g.weight) for g in v.groups if g.group in gn])
        pts.append(_world_verts([o]))
    if not pts:
        return None
    W = np.zeros((sum(len(p) for p in pts), len(names)))
    for i, r in enumerate(rows):
        for c, wv in r:
            W[i, c] = wv
    return np.concatenate(pts), sorted(names, key=names.get), W


def _halter_ride(obj, sk, co, bones):
    """`sk` blended toward the bodice's own weights by the part's ride share (1 on the strap
    ends tucked under the rim): inverse-distance over the HALTER_RIDE_K nearest bodice
    vertices (its ornaments that keep their own skin sample, BODICE_RIDE, left out)."""
    r = _point_param(obj, co, 'levi_cord_ride')
    if r is None or not (r > 0).any():
        return sk
    host = _part_skin(HALTER_RIDE_PART, skip=BODICE_RIDE)
    if host is None:
        print(f'rig: WARNING {obj.name}: no skinned {HALTER_RIDE_PART}; the tucked cord ends keep the skin weights')
        return sk
    hco, names, hw = host
    col = {b.name: i for i, b in enumerate(bones)}
    m = np.zeros((len(names), len(bones)))
    for k, n in enumerate(names):
        if n in col:
            m[k, col[n]] = 1.0
    tree = _kd(hco)
    rows = np.nonzero(r > 0)[0]
    out = sk.copy()
    for v in rows:
        found = tree.find_n(co[v], HALTER_RIDE_K)
        wt = np.array([1.0 / (d + SKIN_SOFT) for _, _, d in found])
        bw = (wt @ hw[[j for _, j, _ in found]]) @ m
        tot = bw.sum()
        if tot < 0.5:      # the bodice there is on bones the halter may not take
            continue
        out[v] = sk[v] * (1.0 - r[v]) + bw / tot * r[v]
    return out


def _halter_joins(obj, sk, co, edges):
    """Each X-strand vertex blended toward the weights of the strap beside it by the part's
    join share (1 at the strand's end, on the strap's centre line): the inverse-distance
    blend of the HALTER_JOIN_K nearest vertices of the other cords (join share 0), so the
    strand's end moves with the strap it ends on, and the stretch that lies along the strap
    with the strap's own bend. (Riding the strap's weights at the end point alone, the
    strand's last centimetre turned rigidly with it and crossed the bending strap: a knot.)"""
    j = _point_param(obj, co, 'levi_cord_join')
    if j is None or not (j > 0).any() or edges is None:
        return sk
    lab = _islands(len(co), edges)
    # queried at each vertex's position smoothed along the surface (about its section's
    # centre), so the vertices of one strand section find the same strap vertices
    cq = _smooth(co, co, edges, HALTER_REFIT_AT)
    out = sk.copy()
    for isl in np.unique(lab[j > 0]):
        host = np.nonzero((j <= 0) & (lab != isl))[0]
        if not len(host):
            continue
        tree = _kd(co[host])
        for v in np.nonzero((lab == isl) & (j > 0))[0]:
            found = tree.find_n(cq[v], HALTER_JOIN_K)
            wt = np.array([1.0 / (d + HALTER_JOIN_SOFT) for _, _, d in found])
            wp = wt @ sk[host[[k for _, k, _ in found]]] / wt.sum()
            out[v] = sk[v] * (1.0 - j[v]) + wp * j[v]
    return out


def _neck_cord_weights(kind, w, co, bones, edges=None, obj=None):
    """The choker rides the neck skin (_choker_skin; without a skinned body: 首, with a
    little 上半身2 at its lower edge). The halter cords run from the choker over the shoulder
    slope to the bodice and take the weights of the skin under them (HALTER_REACH), so
    they stay on the neck and the shoulder slope as they move (without a skinned body: 首
    at the choker end, the smoothed envelope weights below); with `obj`, its tucked ends
    ride the bodice and its X strands' ends the straps (_halter_ride, _halter_joins)."""
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
            # the tucked strap ends take the bodice's weights before the smoothing (one set
            # across the section, and a transition spread along the cord: sampled per vertex
            # after it, the thinned end rings stretched x3 in idol_dance@78)
            if obj is not None:
                sk = _halter_ride(obj, sk, co, bones)
            # one set of weights across the cord's section (a 1.4 mm tube): smoothed wider
            # than its girth, so the section cannot shear
            if edges is not None:
                sk = _smooth(sk, co, edges, HALTER_SMOOTH)
            sk = sk / np.maximum(sk.sum(1, keepdims=True), 1e-12)
            # the X strands' ends take the strap's after it (smoothed along the strand, the end
            # drifted ~1 mm off the strap again and showed its end cap)
            if obj is not None:
                sk = _halter_joins(obj, sk, co, edges)
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


def _side_chain_weights(w, co, obj, bones):
    """Round 8: a hair_front family in SIDE_HAIR_CHAIN_WEIGHTS (the cheek wisps) rides its
    side's chain by position along it, as a back-hair lock does (_lock_weights): 頭 above
    the chain's top, handing over to the chain over its first bone, then hat
    functions of the position (so a wisp's tip curling back up stays on the last bone)."""
    fam = next((p for p, _, _ in SIDE_HAIR_FAMILIES if obj.name.startswith(p + '_')), None)
    if fam not in SIDE_HAIR_CHAIN_WEIGHTS:
        return
    tag = obj.name[len(fam) + 1:len(fam) + 2]
    cols = sorted((j for j, b in enumerate(bones) if b.meta.get('chain_weights') and b.meta.get('family') == fam
                   and b.name.endswith('.' + tag)), key=lambda j: bones[j].meta.get('seg', 0))
    head = next((j for j, b in enumerate(bones) if b.name == '頭'), None)
    if not cols or head is None:
        return
    A = np.array([bones[j].head for j in cols])
    B = np.array([bones[j].tail for j in cols])
    u = _polyline_u(co, A, B)
    n = len(cols)
    share = _smoothstep(0.0, SIDE_HAIR_ROOT_BLEND, u)
    uc = np.clip(u, 0.5, n - 0.5)
    w[:] = 0.0
    for i, j in enumerate(cols):
        w[:, j] = share * np.maximum(0.0, 1.0 - np.abs(uc - (i + 0.5)))
    w[:, head] = 1.0 - share


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
    if part == 'hair_front':
        _side_chain_weights(w, co, obj, bones)
    masked = w * _side_mask(co, labels, bones, part not in SIDED_PARTS_EXEMPT)
    ok = masked.sum(1) > 1e-9
    w = np.where(ok[:, None], masked, w)
    w = w / w.sum(1, keepdims=True)
    if TIER_FIELD and obj.name.startswith(TIER_FIELD[0]):
        return _tier_field_weights(co, bones)
    if part == 'bodice' and TAIL_FIELD and obj.name.startswith(TAIL_FIELD):
        tw = _tail_weights(w, co, obj, part, bones, edges)
        if tw is not None:
            return tw
    if obj.name.startswith(PLAIN_OBJECTS):
        return _plain_weights(w, co, part, bones)
    radius = SLEEVE_SMOOTH if part == 'sleeves' and SLEEVE_BUILD else SMOOTH_RADIUS.get(part, DEFAULT_SMOOTH)
    ref = SMOOTH_REF.get(part)
    zone = _hint_zone(obj, len(co))     # 风堇's hands: smoothed apart from the rest (_smooth_zones)
    shared = _layer_shared(part, bones).get(obj.name) if part in LAYER_PARTS else None
    w = _smooth_zones(w, co, edges, radius, ref, zone) if shared is None or len(shared) != len(co) else shared
    m = _crotch_mask(co, bones) if part in CROTCH_PARTS and CROTCH_SMOOTH > 0 else None
    if m is not None and m.max() > 0:
        # the crotch is pulled between both thighs in a stride: spread its L/R weight
        # change over a wider band than the rest of the skin
        w = w * (1.0 - m[:, None]) + _smooth_zones(w, co, edges, CROTCH_SMOOTH, ref, zone) * m[:, None]
    m = _armpit_mask(co, bones) if part in CROTCH_PARTS and ARMPIT_SMOOTH > 0 else None
    if m is not None and m.max() > 0:
        # a raised arm pulls the armpit skin between the ribs and the arm: spread the
        # torso / arm weight change over a wider band there too
        w = w * (1.0 - m[:, None]) + _smooth_zones(w, co, edges, ARMPIT_SMOOTH, ref, zone) * m[:, None]
    if part in CROTCH_PARTS and CROTCH_TAIL:
        w = _crotch_tail(w, co, edges, bones)
    if part in CROTCH_PARTS and HIP_AUX:
        _hat_remap(w, bones)
    if part == 'hair_back':
        w = _hair_head_fade(w, co, bones)
    if part in SHELL_PARTS:
        w = _shell_share(w, co, bones)
    if part in CROTCH_PARTS and ARM_CAP:
        w = _arm_cap(w, co, bones)
    if cord:
        w = _neck_cord_weights(cord, w, co, bones, edges, obj)
    elif part == 'bodice' and SKIN_FOLLOW and _SKIN is not None and obj.name.startswith(BODICE_RIDE):
        pass    # the shell's own per-point weights (skin sample, arm cap): no rigid island
    elif _skin_ornament(obj, part):
        roots = np.array([tuple(obj.matrix_world @ Vector(p)) for p in obj.get('levi_attach_points', [])]).reshape(-1, 3)
        w = _skin_ornament_weights(w, co, labels, part, bones, roots)
    else:
        w = _island_rules(w, co, _part_labels(obj, co, labels), bones, part)
    w = _hand_hint(obj, w, co, bones, edges)
    knot = _knot_weights(w, co, obj, part, bones) if part == 'bodice' else None
    if knot is not None:
        w = knot[0]
    if part in RIGID_FOOT and obj.name.startswith(RIGID_FOOT[part]):
        _rigid_foot(w, bones)
    # which bones a vertex keeps is decided on a wider-smoothed copy of its weights, so
    # the set changes gradually along the surface instead of wherever two weak bones swap
    if part in CROTCH_PARTS:
        w = _mirror_average(w, co, bones)
    guide = _smooth_zones(w, co, edges, PRUNE_SMOOTH, ref, zone) if PRUNE_SMOOTH > 0 and radius > 0 else None
    if guide is not None and part in SHELL_PARTS:
        guide = _shell_share(guide, co, bones)
    if guide is not None and part in CROTCH_PARTS:
        guide = _mirror_average(guide, co, bones)
    if guide is not None and cord == 'halter':
        guide = _halter_joins(obj, guide, co, edges)   # a strand's end keeps the strap's bones
    if cord == 'halter' and len(edges):
        # the prune's motion refit at each cord section's centre (HALTER_REFIT_AT), so a section
        # keeps one set of weights
        return _prune(w, bones, guide, _smooth(co, co, edges, HALTER_REFIT_AT))
    idx, ww = _prune(w, bones, guide, co)
    if part in CROTCH_PARTS and CROTCH_FIT and _CROTCH:
        ww = _crotch_fit(idx, ww, co, edges, _mesh_tris(obj), bones)
    return _knot_pin(idx, ww, knot, bones)


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


def _drape_prop(arm, pb, prop, tab, src):
    """pb[prop] = the drape row `tab` (rad over DRAPE_PHI) at the thigh's forward pitch,
    the custom property src = (pose bone, property) (_thigh_hub), through an F-curve
    holding the table as auto-clamped Bezier keys (C1, no overshoot past the samples),
    flat outside."""
    pb[prop] = 0.0
    fc = _prop_driver(arm, pb, f'["{prop}"]', 'p', [('p',) + tuple(src)])
    pts = sorted((math.radians(x), float(y)) for x, y in zip(DRAPE_PHI, tab))
    fc.keyframe_points.add(len(pts))
    for kp, (x, y) in zip(fc.keyframe_points, pts):
        kp.co = (x, y)
        kp.interpolation = 'BEZIER'
        kp.handle_left_type = kp.handle_right_type = 'AUTO_CLAMPED'
    fc.extrapolation = 'CONSTANT'
    fc.update()


def _prop_driver(arm, pb, path, expr, srcs):
    """A scripted driver on pb's `path` (a custom property or a channel) reading custom
    properties of pose bones: srcs = [(variable, bone, property)]."""
    fc = pb.driver_add(path, 0) if path == 'rotation_axis_angle' else pb.driver_add(path)
    drv = fc.driver
    drv.type = 'SCRIPTED'
    for name, bone, prop in srcs:
        v = drv.variables.new()
        v.name, v.type = name, 'SINGLE_PROP'
        tg = v.targets[0]
        tg.id_type, tg.id = 'OBJECT', arm
        tg.data_path = f'pose.bones["{bone}"]["{prop}"]'
    drv.expression = expr
    for m in list(fc.modifiers):
        fc.modifiers.remove(m)
    return fc


def _thigh_hub(arm, hub):
    """Blender only: the thighs' direction, measured once for every drape driver, as
    custom properties of the pose bone `hub` (the first chain's root R follow bone; only
    its yaw turns it, _skirt_yaw_driver):
    per thigh t, thigh_t_x / _y / _z (its hip -> knee direction in the pelvis frame, from
    the evaluated local quaternion, so IK counts), thigh_t_phi (its forward pitch seen
    from the side, from rest) and thigh_t_w (0 .. 1: how far it is swung out toward
    DRAPE_PSI seen from above, faded out unless it points forward)."""
    pb = arm.pose.bones[hub]
    if 'thigh_L_phi' in pb.keys():
        return
    for t, s in (('L', 1.0), ('R', -1.0)):
        thigh = f'足.{t}'
        M = arm.data.bones[thigh].matrix_local.to_3x3()
        v = ('(2*(x*y-w*z))', '(1-2*(x*x+z*z))', '(2*(y*z+w*x))')
        for r, c in enumerate('xyz'):
            prop = f'thigh_{t}_{c}'
            pb[prop] = float(M[r][1])
            fc = pb.driver_add(f'["{prop}"]')
            drv = fc.driver
            drv.type = 'SCRIPTED'
            for q in 'wxyz':
                var = drv.variables.new()
                var.name, var.type = q, 'TRANSFORMS'
                tg = var.targets[0]
                tg.id, tg.bone_target = arm, thigh
                tg.transform_type, tg.rotation_mode, tg.transform_space = \
                    f'ROT_{q.upper()}', 'QUATERNION', 'LOCAL_SPACE'
            drv.expression = '+'.join(f'{M[r][k]:.6f}*{v[k]}' for k in range(3))
            for m in list(fc.modifiers):
                fc.modifiers.remove(m)
        rest = math.atan2(-M[1][1], -M[2][1])
        src = [('x', hub, f'thigh_{t}_x'), ('y', hub, f'thigh_{t}_y'), ('z', hub, f'thigh_{t}_z')]
        pb[f'thigh_{t}_phi'] = 0.0
        # unwrapped past straight up (a thigh pulled to the chest reads +190, not -170 deg)
        _prop_driver(arm, pb, f'["thigh_{t}_phi"]',
                     f'atan2(-y,-z)-{rest:.6f}+(6.283185 if atan2(-y,-z)<-2.0 else 0)', src)
        pb[f'thigh_{t}_w'] = 0.0
        _prop_driver(arm, pb, f'["thigh_{t}_w"]',
                     f'min(max(atan2({s:g}*x,max(-y,1e-4))/{math.radians(DRAPE_PSI):.6f},0),1)'
                     f'*smoothstep(0.05,0.25,-y)', src)
    # seat_w: 0 .. 1 as both thighs rise through SEAT_PHI with a foot on the ground (seated: _skirt_seat)
    s0, s1 = (math.radians(v) for v in SEAT_PHI)
    pb['seat_w'] = 0.0
    # heights are read in world space and measured in shin lengths (the world distance from
    # knee to ankle, 'sh'), so a scaled or moved armature reads the same
    shin = max((arm.data.bones['ひざ.L'].head_local - arm.data.bones['足首.L'].head_local).length, 1e-3)
    g0, g1 = (v / shin for v in GROUNDED)
    fc = _prop_driver(arm, pb, '["seat_w"]', f'smoothstep({s0:.5f},{s1:.5f},a)*smoothstep({s0:.5f},{s1:.5f},b)'
                      f'*(1-smoothstep({g0:.4f},{g1:.4f},(min(fL,fR)-g)/max(sh,1e-6)))',
                      [('a', hub, 'thigh_L_phi'), ('b', hub, 'thigh_R_phi')])
    for nm, bn in (('fL', '足首.L'), ('fR', '足首.R'), ('g', '全ての親')):
        _world_z_var(fc.driver, nm, arm, bn)
    _shin_var(fc.driver, 'sh', arm, 'L')
    # floor_w: 1 with both shins level (seated on the floor), 0 with them hanging (a chair)
    pb['floor_w'] = 0.0
    fc = pb.driver_add('["floor_w"]')
    drv = fc.driver
    drv.type = 'SCRIPTED'
    terms = []
    for t in 'LR':
        _world_z_var(drv, f'k{t}', arm, f'ひざ.{t}')
        _world_z_var(drv, f'a{t}', arm, f'足首.{t}')
        _shin_var(drv, f's{t}', arm, t)
        terms.append(f'(1-smoothstep({FLOOR_SHIN[0]},{FLOOR_SHIN[1]},(k{t}-a{t})/max(s{t},1e-6)))')
    drv.expression = '*'.join(terms)
    for m in list(fc.modifiers):
        fc.modifiers.remove(m)


def _world_z_var(drv, name, arm, bone):
    """Driver variable `name`: the world height of pose bone `bone`'s head."""
    var = drv.variables.new()
    var.name, var.type = name, 'TRANSFORMS'
    tg = var.targets[0]
    tg.id, tg.bone_target = arm, bone
    tg.transform_type, tg.transform_space = 'LOC_Z', 'WORLD_SPACE'


def _shin_var(drv, name, arm, t):
    """Driver variable `name`: the world distance from knee to ankle of leg t."""
    var = drv.variables.new()
    var.name, var.type = name, 'LOC_DIFF'
    for tg, bone in zip(var.targets, (f'ひざ.{t}', f'足首.{t}')):
        tg.id, tg.bone_target = arm, bone
        tg.transform_space = 'WORLD_SPACE'


def _skirt_drape_driver(arm, pb, d):
    """Blender only: turn a skirt chain joint about the world X axis by the drape tables
    (_skirt_drape). The chain's L follow bone at joint i carries the absolute turn of
    segment i for each thigh alone at its pitch (_drape_prop, reading the hub's
    thigh_t_phi, _thigh_hub), split into its forward lift (drape_tp: the plain table
    blended to the abducted one by thigh_t_w) and its backward lift (drape_tn, both
    >= 0); `drape` is the two thighs combined (_drape_combine_expr) and the joint turns
    by its segment's `drape` less the one above's (read from the joint above's follow
    bone). The root R follow bone turns the chain round the body (_skirt_yaw_driver), the
    others stay at rest. (Blender keeps a driver expression to 256
    characters, hence the steps.) In the PMX the segments below the chain roots are
    physics bodies colliding with the legs, so only the linear share ('follow') is
    exported."""
    if d['own'] != 'L':
        if d['i'] == 0 and 'yL' in d:
            _skirt_yaw_driver(arm, pb, d)
        elif d['i'] > 0 and 'seat' in d:
            _skirt_seat_driver(arm, pb, d)
        return
    i, hub = d['i'], d['hub']
    _thigh_hub(arm, hub)
    for t in 'LR':
        phi = (hub, f'thigh_{t}_phi')
        tab = np.asarray(d[t][i], dtype=float)
        _drape_prop(arm, pb, f'drape_{t}p0', np.maximum(tab, 0.0), phi)
        _drape_prop(arm, pb, f'drape_{t}p1', np.maximum(np.asarray(d[t + 'a'][i], dtype=float), 0.0), phi)
        _drape_prop(arm, pb, f'drape_{t}n', np.maximum(-tab, 0.0), phi)
        _blend_props(arm, pb, f'drape_{t}p', [f'drape_{t}p0', f'drape_{t}p1'], hub, t)
    pb['drape'] = 0.0
    _prop_driver(arm, pb, '["drape"]', _drape_combine_expr('a', 'b') + '-' + _drape_combine_expr('c', 'd'),
                 [('a', pb.name, 'drape_Lp'), ('b', pb.name, 'drape_Rp'),
                  ('c', pb.name, 'drape_Ln'), ('d', pb.name, 'drape_Rn')])
    pb.rotation_mode = 'AXIS_ANGLE'      # about local Y (the bone points along -X): forward pitch
    pb.rotation_axis_angle = (0.0, 0.0, 1.0, 0.0)
    srcs = [('a', pb.name, 'drape')] + ([('b', d['above'], 'drape')] if i else [])
    _prop_driver(arm, pb, 'rotation_axis_angle', 'a-b' if i else 'a', srcs)


def _axis_angle_const(pb, ax):
    """Axis-angle rotation about the fixed local axis ax (normalized): the axis is held
    by constant drivers, since a pose reset (matrix_basis.identity()) puts it back to
    local Y."""
    pb.rotation_mode = 'AXIS_ANGLE'
    pb.rotation_axis_angle = (0.0, ax.x, ax.y, ax.z)
    for c in range(3):
        fc = pb.driver_add('rotation_axis_angle', c + 1)
        fc.driver.type = 'SCRIPTED'
        fc.driver.expression = f'{ax[c]:.6f}'
        for m in list(fc.modifiers):
            fc.modifiers.remove(m)


def _skirt_seat_driver(arm, pb, d):
    """Blender only: the seat swing (_skirt_seat) of joint i of a skirt chain, on its R
    follow bone (the parent of the L one that lifts it): the segment's swing less the
    one above's, about the horizontal axis across the chain, times the hub's seat_w; the
    chair's (back only) blended to the floor's (all round) by the hub's floor_w."""
    i, hub = d['i'], d['hub']
    rel = float(d['seat'][i] - d['seat'][i - 1])
    rel_c = float(d['seat_chair'][i] - d['seat_chair'][i - 1])
    if abs(rel) < 1e-4 and abs(rel_c) < 1e-4:
        return
    _thigh_hub(arm, hub)
    a = math.radians(d['angle'])
    ax = pb.bone.matrix_local.to_3x3().inverted() @ Vector((math.cos(a), -math.sin(a), 0.0))
    _axis_angle_const(pb, ax.normalized())
    _prop_driver(arm, pb, 'rotation_axis_angle', f'w*({rel_c:.6f}+f*{rel - rel_c:.6f})',
                 [('w', hub, 'seat_w'), ('f', hub, 'floor_w')])


def _blend_props(arm, pb, prop, srcs, hub, t):
    """pb[prop] = the two tables srcs (plain, abducted; properties of pb) blended by
    the hub's thigh_t_w (abduction) of thigh t."""
    pb[prop] = 0.0
    _prop_driver(arm, pb, f'["{prop}"]', 'a+w*(b-a)',
                 [(v, pb.name, s) for v, s in zip('ab', srcs)] + [('w', hub, f'thigh_{t}_w')])


DRAPE_YAW_OWN = 30.0    # deg: a chain the other thigh lifts this far takes none of this thigh's yaw


def _skirt_yaw_driver(arm, pb, d):
    """Blender only: turn a skirt chain round the body (about the vertical through its
    root, _yaw) by the gather tables (_skirt_drape's 'yL' / 'yR', plain blended to
    abducted by thigh_t_w like the lift). The chain's root R follow bone (the parent of
    the L follow bone that lifts it) carries it. Each thigh's yaw fades out as the other
    thigh lifts the chain itself (DRAPE_YAW_OWN): seated, the cloth on one thigh is not
    pulled toward the other, and the two pulls do not swap the front chains over."""
    hub = d['hub']
    _thigh_hub(arm, hub)
    for t in 'LR':
        phi = (hub, f'thigh_{t}_phi')
        _drape_prop(arm, pb, f'yaw_{t}0', np.asarray(d['y' + t], dtype=float), phi)
        _drape_prop(arm, pb, f'yaw_{t}1', np.asarray(d['y' + t + 'a'], dtype=float), phi)
        _drape_prop(arm, pb, f'lift_{t}', np.abs(np.asarray(d[t][0], dtype=float)), phi)
        _blend_props(arm, pb, f'yaw_{t}', [f'yaw_{t}0', f'yaw_{t}1'], hub, t)
    _axis_angle_const(pb, (pb.bone.matrix_local.to_3x3().inverted() @ Vector((0.0, 0.0, -1.0))).normalized())
    own, ref = math.radians(DRAPE_YAW_OWN), math.radians(DRAPE_YAW_MAX)
    _prop_driver(arm, pb, 'rotation_axis_angle',
                 f'max(-{ref:.5f},min({ref:.5f},a*(1-smoothstep(0,{own:.5f},d))+b*(1-smoothstep(0,{own:.5f},c))))',
                 [('a', pb.name, 'yaw_L'), ('b', pb.name, 'yaw_R'),
                  ('c', pb.name, 'lift_L'), ('d', pb.name, 'lift_R')])


def _drape_combine_expr(a, b):
    """Driver simple expression combining both thighs' lifts a, b >= 0 (one direction) of
    one segment: the smooth max (a + b + s) / 2 - e^2 / (2 s), s = sqrt((a - b)^2 + e^2),
    e = DRAPE_COMBINE_EPS. It is exact when the two are equal (seated) and when they are
    far apart (one leg raised), never more than 0.15 e below the max in between, nought
    at rest, and has no kink where the legs cross (the round-6 plain max kinked there: a
    one-frame pop at every crossing in walk and run)."""
    e2 = DRAPE_COMBINE_EPS ** 2
    s = f'sqrt(({a}-{b})*({a}-{b})+{e2:g})'
    return f'(({a}+{b}+{s})/2-{e2 / 2:g}/{s})'


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
        for src, k in b.meta.get('pitch_hang', ()):
            # Blender only, like the sideways gravity: turn back k of the source's pitch
            # (about this bone's local X, world X for 髪追従, which points up)
            c = pb.constraints.new('COPY_ROTATION')
            c.name = f'Hang {src}'
            c.target, c.subtarget = arm, src
            c.target_space, c.owner_space = 'LOCAL_OWNER_ORIENT', 'LOCAL'
            c.mix_mode = 'BEFORE'
            c.use_y = c.use_z = False
            c.invert_x = True
            c.influence = k
        for src, k in b.meta.get('arch_hang', ()):
            # Blender only: a torso bent BACK leaves the hair hanging from the head (her back
            # turns away from it), so the root turns back k of that pitch; a forward bend
            # is left to the lower segments' pitch gravity (the top rests on her back)
            _pitch_counter(arm, pb, src, k, forward=False, name=f'Arch hang {src}')
        for src, k in b.meta.get('pitch_gravity', ()):
            # Blender: turn back k of each torso bone's FORWARD pitch, about world X (spread
            # over the bone's local axes, _pitch_counter), so a segment running sideways (an
            # outer lock over the arm) swings down too. Bent back, the root hangs instead
            # (arch_hang).
            _pitch_counter(arm, pb, src, k, forward=True, name=f'Pitch gravity {src}')
        for src, k in b.meta.get('pelvis_follow', ()):
            # Blender only (round 8): the hair lying on the hips and skirt takes k of the
            # pelvis' pitch, forward and back (HAIR_PELVIS_FOLLOW)
            for fwd in (True, False):
                _pitch_counter(arm, pb, src, -k, forward=fwd, name=f'Pelvis {src} {"fwd" if fwd else "back"}')
        if 'ik' in b.meta:
            # a one-link IK turning this bone about its local X only, within (lo, hi) deg
            # (the hair's pitch-only helpers; exported as a PMX IK with that link limit)
            goal, (lo, hi) = b.meta['ik']
            c = pb.constraints.new('IK')
            c.name = 'IK'
            c.target, c.subtarget = arm, goal
            c.chain_count, c.iterations = 1, 40
            c.use_tail, c.use_stretch = True, False
            pb.lock_ik_y = pb.lock_ik_z = True
            pb.use_ik_limit_x = True
            pb.ik_min_x, pb.ik_max_x = math.radians(lo), math.radians(hi)
            pb.ik_stretch = 0.0
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
        if 'pmx_append' in b.meta:
            # the PMX's 回転付与 differs from what Blender evaluates (SHOULDER_PMX_SWING): the
            # drivers above stay, the export reads these properties
            src, k = b.meta['pmx_append']
            pb['mmd_append'] = src
            pb['mmd_append_influence'] = float(k)
        if 'pmx_local_x' in b.meta:
            pb['mmd_local_x'] = list(b.meta['pmx_local_x'])   # export_pmx: PMX local axes
        if 'ik_free' in b.meta:
            # a one-link IK with no limits: the bone swings to aim its tail at the goal (PMX
            # IK; in Blender it deforms nothing)
            c = pb.constraints.new('IK')
            c.name = 'IK'
            c.target, c.subtarget = arm, b.meta['ik_free']
            c.chain_count, c.iterations = 1, 40
            c.use_tail, c.use_stretch = True, False
            pb.ik_stretch = 0.0
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
        if KNEE_IK_PREBEND:
            _knee_prebend(arm, knee, arm.pose.bones[f'足首.{t}'])
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


def _motion_chain_samples(arm):
    """{deform bone: (K', 3, 4)} skinning matrices in MOTION_CHAIN_POSES, evaluated like
    _motion_samples (the drape drivers follow the thighs; IK muted, pose reset after)."""
    from mathutils import Quaternion
    pbs = arm.pose.bones
    muted = [c for pb in pbs for c in pb.constraints if c.type == 'IK' and not c.mute]
    for c in muted:
        c.mute = True
    deform = [pb for pb in pbs if pb.bone.use_deform]
    out = {pb.name: [] for pb in deform}
    for sample in MOTION_CHAIN_POSES:
        for pb in pbs:
            pb.matrix_basis.identity()
        for name, how, deg in sample:
            pb = pbs.get(name)
            if pb is None:
                continue
            side = -1.0 if name.endswith('.R') else 1.0
            ax = pb.bone.matrix_local.to_3x3()
            if how == 'side':
                axis = Vector((0.0, side, 0.0))
            else:
                tgt = Vector(how)
                tgt.x *= side
                axis = ax.col[1].cross(tgt)
            local = (ax.inverted() @ axis).normalized()
            pb.rotation_mode = 'QUATERNION'
            pb.rotation_quaternion = Quaternion(local, math.radians(deg)) @ pb.rotation_quaternion
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
    src = f", {FINGER_SRC['src']}" if F and FINGER_SRC.get('src') else ''
    print(f"rig fingers    {'mesh' if F else 'spec'}  ({len(F)} chains fitted to the body's fingers{src})")
    core = _core_bones(J, H, F)
    by = {b.name: b for b in core}
    hd, ey = by['頭'].head, by['目.L'].head
    print(f"rig head  頭             {'mesh' if 'head_y' in H else 'spec'}  ({hd.x:+.3f}, {hd.y:+.3f}, {hd.z:+.3f})")
    print(f"rig head  目.L           {H.get('eye_src', 'mesh') if 'eye' in H else 'spec'}  ({ey.x:+.3f}, {ey.y:+.3f}, {ey.z:+.3f})")
    bones = core + _secondary_bones(parts, core)
    arm = _create_armature(bones)
    global _ATTACH_HOST, _PARENTS, _MOTION, _CROTCH, _MOTION_CHAIN
    _MOTION = _motion_samples(arm) if PRUNE_MOTION else {}
    _CROTCH = _crotch_samples(arm) if CROTCH_FIT else {}
    _MOTION_CHAIN = {}
    if _MOTION and MOTION_CHAIN_POSES:
        extra = _motion_chain_samples(arm)
        _MOTION_CHAIN = {b: np.concatenate([m, extra[b]]) for b, m in _MOTION.items() if b in extra}
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
    _LAYER_SRC.clear()
    _LAYER_SRC.update({p: parts[p] for p in LAYER_PARTS if p in parts})
    _LAYER.clear()
    # the skin first (garments sample it); SKIN_LATE parts after the garments they read
    order = sorted(parts, key=lambda n: (n not in ('body', '_proxy'), n in SKIN_LATE))
    for part in order:
        for o in parts[part]:
            if o.parent is None:
                o.parent = arm
                o.matrix_parent_inverse = arm.matrix_world.inverted()
            _skin(o, part, bones, arm)
        if part in ('body', '_proxy') and _SKIN is None:
            _store_skin(parts[part])
    bpy.context.view_layer.update()
    _sleeve_ride_weights(parts.get('sleeves', []))
    _sleeve_gather(arm, parts.get('sleeves', []), bones)
    _hair_collision(arm, bones, parts)
    return arm
