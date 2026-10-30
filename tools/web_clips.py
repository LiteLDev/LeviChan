"""LeviChan's web motion clips (levimc.org), 30 fps: an idle loop, 50 actions (5-30 s) and locomotion.

Imported through motion_poses (LEVI_EXTRA_CLIPS=web_clips) or motion_vmd.py --extra-clips web_clips,
they add to motion_poses.CLIPS, so render.py --pose <clip>@<frame>, rig_check.py --motion and
motion_vmd.py (VMD export) take them like the test clips.

Contract (the web runtime chains and crossfades them over MMD physics):
  - every clip starts and ends in STANCE (= idle frame 0), feet on their rest marks;
  - in place, facing the viewer (-Y) at both ends; IK legs only;
  - no keys on hair, skirt or sleeve chains (physics drives them) and none on the eyes (the
    runtime drives gaze, blinks and the expressions of MANIFEST).

A clip is a list of key poses in a small parameter space (PARAMS: centre, whole-body turn,
pelvis / spine / head angles, per side the wrist position and elbow direction, forearm twist,
wrist bend, shrug, finger curls, foot offset / pitch / yaw / tiptoe). Keys are cumulative (a key
changes only what it names) and the parameters are interpolated per frame by monotone cubics
(no overshoot, eased at every extreme), each group a few frames behind the one that drives it
(LAG: pelvis -> spine -> head, upper arm -> forearm -> hand -> fingers), which gives overlap and
follow-through without hand-keyed in-betweens. The arm is placed by its wrist (rest-world
position relative to the chest, the side's own shoulder frame) and an elbow direction:
`reach` solves the two bones so the elbow flexes about the rig's own hinge (arm_pose's
semantics), so no twisted elbows. Directions and positions are for the character's left (+X)
and mirrored for .R; +yaw turns to her left, +pitch bends forward / tips the head down, +roll
leans to her left.
"""
import math

from mathutils import Quaternion, Vector

import motion_poses as mp
import rig_pose
from motion_poses import _m, _q_turn, centre, foot, foot_ref
from rig_pose import bend, turn, twist

FPS = mp.FPS
KEY_STEP = 2          # frames between the Blender keys sampled from the parameter curves
SMOOTH = 3            # half-width of the binomial low-pass on the sampled parameters (frames)

# ------------------------------------------------------------------ parameters

# the arms at rest hang naturally at her sides: the upper arms straight down (shoulder -> elbow ~8 deg
# off vertical in front, ~3 deg in the side view), the forearms down with the rig's natural ~30 deg
# carrying bend, palms to the body, fingers gently curled. Her bell skirt is 0.25-0.30 m round at hand
# height, so the forearm angles out (~40 deg from vertical in front) only far enough for the hand to
# rest on its surface; the upper arm is not abducted. (Arms held out over the skirt, an A-pose, or
# hands clasped in front all read as stiff or posed.)
REST_K = (-0.6, -0.1, -1.0)
REST_G, REST_GI, REST_GT = 0.35, 0.3, 0.3
_REST = dict(w=(0.285, -0.085, 0.765), k=REST_K, p=-35.0, b=-15.0, g=REST_G, gi=REST_GI, gt=REST_GT)
REST_SIDE = {'L': _REST, 'R': _REST}

STANCE = {
    'c': (0.0, 0.0, -0.006), 'turn': 0.0,                      # centre offset (m), body yaw (deg)
    'lp': 0.0, 'lr': 0.0, 'ly': 0.0,                           # pelvis (下半身) pitch / roll / yaw
    'sp': 2.0, 'sy': 0.0, 'sr': 0.0,                           # upper body pitch / yaw / roll
    'hp': 0.0, 'hy': 0.0, 'hr': 0.0,                           # head pitch / yaw / roll
}
for _t in 'LR':
    STANCE.update({
        f'w{_t}': REST_SIDE[_t]['w'],       # wrist position, rest world (left side), m
        f'k{_t}': REST_K,                   # where the elbow points
        f'p{_t}': REST_SIDE[_t]['p'],       # forearm twist (+ palm down / back)
        f'b{_t}': REST_SIDE[_t]['b'],       # wrist flexed toward the palm
        f'sh{_t}': 0.0,                     # clavicle raised
        f'g{_t}': REST_G, f'gm{_t}': REST_G,   # finger curl: ring-little, middle (K copies g to gm unless
        f'gi{_t}': REST_GI, f'gt{_t}': REST_GT,  # gm is given: a V sign curls g only), index, thumb
        f'f{_t}': (0.0, 0.0, 0.0),          # foot offset (x outward)
        f'fp{_t}': 0.0, f'fy{_t}': 3.0,     # foot pitch (+ heel up), yaw (+ toes out)
        f'tip{_t}': 0.0,                    # onto the toes (deg; the toe stays on the floor)
    })
PARAMS = list(STANCE)

# frames each parameter trails its key timing (overlap / follow-through)
LAG = {'c': 0.0, 'turn': 0.0, 'lp': 0.5, 'lr': 0.5, 'ly': 0.5, 'sp': 1.2, 'sy': 1.2, 'sr': 1.2,
       'hp': 2.6, 'hy': 2.4, 'hr': 2.8}
for _t in 'LR':
    LAG.update({f'w{_t}': 1.4, f'k{_t}': 1.4, f'sh{_t}': 1.0, f'p{_t}': 2.6, f'b{_t}': 3.2,
                f'g{_t}': 3.6, f'gm{_t}': 3.5, f'gi{_t}': 3.4, f'gt{_t}': 3.8,
                f'f{_t}': 0.0, f'fp{_t}': 0.0, f'fy{_t}': 0.0, f'tip{_t}': 0.0})

SHOULDER = Vector((0.116, -0.043, 1.143))     # 腕.L at rest: the centre wrists move about

SIDED = ('w', 'k', 'p', 'b', 'sh', 'g', 'gm', 'gi', 'gt', 'f', 'fp', 'fy', 'tip')


def K(frame, **kw):
    """A key: parameters by name; a sided name without L/R (w=, k=, g=, f=...) sets both sides.
    reset=True starts the key from STANCE instead of the previous key."""
    reset = kw.pop('reset', False)
    d = {}
    for k, v in kw.items():
        if k in SIDED:
            d[k + 'L'] = d[k + 'R'] = v
        elif k in STANCE:
            d[k] = v
        else:
            raise KeyError(f'unknown clip parameter {k}')
    for t in 'LR':
        if f'g{t}' in d and f'gm{t}' not in d:
            d[f'gm{t}'] = d[f'g{t}']
    return (frame, d, reset)


def S(frame):
    """Back to the stance."""
    return (frame, {}, True)


# ------------------------------------------------------------------ interpolation

def _monotone(xs, ys):
    """Fritsch-Carlson monotone cubic through (xs, ys): no overshoot, flat at every extreme."""
    n = len(xs)
    h = [xs[i + 1] - xs[i] for i in range(n - 1)]
    dlt = [(ys[i + 1] - ys[i]) / h[i] for i in range(n - 1)]
    m = [0.0] * n
    for i in range(1, n - 1):
        if dlt[i - 1] * dlt[i] > 0:
            w1, w2 = 2 * h[i] + h[i - 1], h[i] + 2 * h[i - 1]
            m[i] = (w1 + w2) / (w1 / dlt[i - 1] + w2 / dlt[i])
    # ends: flat (every clip starts and ends at rest in the stance)

    def f(x):
        if x <= xs[0]:
            return ys[0]
        if x >= xs[-1]:
            return ys[-1]
        i = max(j for j in range(n - 1) if xs[j] <= x)
        t = (x - xs[i]) / h[i]
        t2, t3 = t * t, t * t * t
        return ((2 * t3 - 3 * t2 + 1) * ys[i] + (t3 - 2 * t2 + t) * h[i] * m[i]
                + (-2 * t3 + 3 * t2) * ys[i + 1] + (t3 - t2) * h[i] * m[i + 1])
    return f


class Clip:
    """Key poses -> per-frame parameters (monotone cubic per channel, lagged per group)."""
    STEP = 0.25

    def __init__(self, frames, keys, loop_fn=None, root_end=(0.0, 0.0, 0.0)):
        self.frames = frames
        self.loop_fn = loop_fn
        assert all(0 <= k[0] <= frames for k in keys), 'a key outside the clip'
        full, cur = [], dict(STANCE)
        for f, d, reset in sorted(keys, key=lambda k: k[0]):
            cur = dict(STANCE) if reset else dict(cur)
            cur.update(d)
            if full and full[-1][0] == f:         # keys on one frame merge
                full[-1] = (f, cur)
            else:
                full.append((f, cur))
        if full[0][0] != 0:
            full.insert(0, (0, dict(STANCE)))
        if full[-1][0] < frames:
            assert not any(root_end), 'a displaced clip needs its own end key'
            full.append((frames, dict(STANCE)))
        last = dict(full[-1][1])
        # a clip may end displaced by root_end (climbing / jumping down: the centre and both feet
        # moved together) and a whole number of turns round
        for k in ('c', 'fL', 'fR'):
            last[k] = tuple(a - b for a, b in zip(last[k], root_end))
        assert all(_close(last[k], STANCE[k]) for k in STANCE if k != 'turn') and \
            abs(last['turn'] / 360.0 - round(last['turn'] / 360.0)) < 1e-9, 'a clip must end in the stance'
        xs = [f for f, _ in full]
        self.curves = {}
        for p in PARAMS:
            vals = [k[p] for _, k in full]
            if p in ('wL', 'wR'):
                # wrists move round the shoulder (direction and distance interpolated apart), not on
                # straight lines that can pass through the shoulder and whip the elbow over
                # (great-circle steps between the keys' directions, paced by one eased progress curve)
                rel = [Vector(v) - SHOULDER for v in vals]
                dirs = [r.normalized() for r in rel]
                self.curves[p] = ('polar', dirs, _monotone(xs, list(range(len(xs)))),
                                  _monotone(xs, [r.length for r in rel]))
            elif isinstance(STANCE[p], tuple):
                self.curves[p] = [_monotone(xs, [v[i] for v in vals]) for i in range(len(STANCE[p]))]
            else:
                self.curves[p] = _monotone(xs, vals)
        # elbow swing: a frame transported along each wrist path (grid STEP in key time), the keys'
        # swing angles in it, interpolated as angles
        self.swing = {}
        n = int(math.ceil(frames / self.STEP))
        for t in 'LR':
            dh = [(self._wrist(f'w{t}', i * self.STEP) - SHOULDER).normalized() for i in range(n + 1)]
            e1 = [_perp_unit(STANCE[f'k{t}'], dh[0])]
            for i in range(1, n + 1):
                v = dh[i - 1].rotation_difference(dh[i]) @ e1[-1]
                e1.append(_perp_unit(v, dh[i]))
            angs = []
            for x, k in full:
                i = min(int(round(x / self.STEP)), n)
                h = _perp_unit(k[f'k{t}'], dh[i])
                a = math.atan2(dh[i].cross(e1[i]).dot(h), e1[i].dot(h))
                if angs:
                    a += 2 * math.pi * round((angs[-1] - a) / (2 * math.pi))
                angs.append(a)
            self.swing[t] = (dh, e1, _monotone(xs, angs))

    def _wrist(self, p, x):
        c = self.curves[p]
        dirs, prog = c[1], c[2](x)
        i = min(int(math.floor(prog)), len(dirs) - 2)
        u = prog - i
        a, b = dirs[i], dirs[i + 1]
        ang = a.angle(b, 0.0)
        if ang < 1e-6:
            d = a
        else:
            q = a.rotation_difference(b)
            d = Quaternion(q.axis, q.angle * u) @ a
        return SHOULDER + d * c[3](x)

    def at(self, frame):
        """Parameters at `frame`, low-passed (binomial, +-SMOOTH frames): the monotone cubics are
        only C1, and their acceleration steps at the keys read as pops on fast keys (fingers,
        landings). The ends fade back to the exact curve, so frame 0 / the last are the stance."""
        if self.loop_fn:
            return self.loop_fn(frame)
        raw = self._at(frame)
        w = min(1.0, min(frame, self.frames - frame) / float(SMOOTH + 1))
        if w <= 0.0:
            return raw
        taps = [math.comb(2 * SMOOTH, i) / 4.0 ** SMOOTH for i in range(2 * SMOOTH + 1)]
        acc = None
        for i, k in enumerate(taps):
            P = self._at(min(max(frame + i - SMOOTH, 0), self.frames))
            if acc is None:
                acc = {p: (tuple(x * k for x in v) if isinstance(v, tuple) else v * k) for p, v in P.items()}
            else:
                for p, v in P.items():
                    acc[p] = tuple(a + x * k for a, x in zip(acc[p], v)) if isinstance(v, tuple) else acc[p] + v * k
        return {p: (tuple(r * (1 - w) + a * w for r, a in zip(raw[p], acc[p])) if isinstance(raw[p], tuple)
                    else raw[p] * (1 - w) + acc[p] * w) for p in raw}

    def _at(self, frame):
        out = {}
        for t in 'LR':
            x = min(max(frame - LAG[f'w{t}'], 0.0), self.frames)
            dh, e1, ang = self.swing[t]
            i = min(int(round(x / self.STEP)), len(e1) - 1)
            a = ang(x)
            out[f'n{t}'] = tuple(e1[i] * math.cos(a) + dh[i].cross(e1[i]) * math.sin(a))
        for p, c in self.curves.items():
            x = min(max(frame - LAG[p], 0.0), self.frames)
            if isinstance(c, tuple):
                out[p] = tuple(self._wrist(p, x))
            else:
                out[p] = tuple(ci(x) for ci in c) if isinstance(c, list) else c(x)
        return out


def _close(a, b):
    if isinstance(a, tuple):
        return all(abs(x - y) < 1e-9 for x, y in zip(a, b))
    return abs(a - b) < 1e-9


# ------------------------------------------------------------------ posing

# The elbow's swing about the shoulder -> wrist line: keys give an elbow direction; Clip carries
# a frame along the wrist's path by parallel transport (rotated minimally as the line turns) and
# interpolates each key's swing angle in that frame. Projecting interpolated directions flips the
# elbow wherever the direction passes along the shoulder -> wrist line; an angle from any fixed
# reference flips where the line passes that reference (or its opposite).
def _perp_unit(v, dh, fallback=Vector((0.0, 0.3, -1.0))):
    p = Vector(v) - dh * Vector(v).dot(dh)
    if p.length < 1e-4:
        p = fallback - dh * fallback.dot(dh)
    return p.normalized()


def elbow_of(arm, t, wrist, swing):
    """(shoulder, elbow, wrist) in rest world for reach(): the two-bone solution with the elbow
    swung toward `swing` (left-side convention, mirrored for .R; its part across the shoulder ->
    wrist line counts)."""
    up, lo, wr = (arm.pose.bones[f'{n}.{t}'].bone for n in ('腕', 'ひじ', '手首'))
    S = up.head_local
    L1 = (lo.head_local - S).length
    L2 = (wr.head_local - lo.head_local).length
    W = _m(t, wrist)
    d = W - S
    # no straighter than at rest: the rest arm is already bent ~29 deg (its carrying angle), so a
    # straight arm would bend the elbow backward
    dist = min(max(d.length, abs(L1 - L2) + 0.02), 0.995 * (wr.head_local - S).length)
    dh = d.normalized()
    W = S + dh * dist
    a = (L1 * L1 - L2 * L2 + dist * dist) / (2 * dist)
    r = math.sqrt(max(L1 * L1 - a * a, 0.0))
    n = _perp_unit(_m(t, swing), dh)
    return S, S + dh * a + n * r, W


def reach(arm, t, wrist, swing):
    """Arm .t: the wrist at `wrist` (rest world, left-side coordinates; relative to the chest,
    i.e. with the parents at rest) with the elbow toward elbow_dir. The upper arm (腕) is aimed
    and rolled (the elbow swung toward `swing`, see Clip), the elbow (ひじ) flexed about its own rest hinge (arm_pose's: the forearm swings
    toward -Y in the bone's rest frame), so the elbow bends the way the rig's skin expects."""
    up, lo, wr = (arm.pose.bones[f'{n}.{t}'].bone for n in ('腕', 'ひじ', '手首'))
    S, E, W = elbow_of(arm, t, wrist, swing)
    u = (E - S).normalized()
    v = (W - E).normalized()
    u0 = (lo.head_local - S).normalized()
    v0 = (wr.head_local - lo.head_local).normalized()
    h0 = v0.cross(Vector((0, -1, 0))).normalized()          # ひじ's hinge, rest frame
    q_aim = u0.rotation_difference(u)
    a0 = q_aim @ h0
    a_par = u * a0.dot(u)
    a_perp = a0 - a_par
    A, B, C = v.dot(a_perp), v.dot(u.cross(a_perp)), v.dot(a_par)
    R = math.hypot(A, B)
    base = math.atan2(B, A)
    spread = math.acos(max(-1.0, min(1.0, -C / R))) if R > 1e-9 else 0.0
    best = None
    for psi in (base + spread, base - spread):
        Q = Quaternion(u, psi) @ q_aim
        tgt = Q.inverted() @ v
        beta = math.atan2(v0.cross(tgt).dot(h0), v0.dot(tgt))
        # the elbow flexes (toward the palm side, -Y at rest): the solution with the larger flexion
        score = -beta
        if best is None or score < best[0]:
            best = (score, Q, beta)
    _, Q, beta = best
    _q_turn(arm, f'腕.{t}', Q)
    if abs(beta) > 1e-6:
        turn(arm, f'ひじ.{t}', h0, math.degrees(beta))


def finger_curl(arm, t, rest, index, thumb, middle=None):
    """Curl the fingers of .t: ring / little by `rest`, the middle by `middle` (default `rest`),
    the index by `index`, the thumb by `thumb` (0..1 of rig_pose.FIST)."""
    middle = rest if middle is None else middle
    for pb in arm.pose.bones:
        if not (pb.name.endswith('.' + t) and pb.bone.collections and pb.bone.collections[0].name == 'Fingers'):
            continue
        stem = pb.name.split('.')[0]
        deg = rig_pose.FIST.get(stem) or rig_pose.FIST.get(stem[-1], 0)
        k = (thumb if stem.startswith('親指') else index if stem.startswith('人指')
             else middle if stem.startswith('中指') else rest)
        if deg and k:
            turn(arm, pb.name, pb.bone.matrix_local.to_3x3().col[0], deg * k)


def _toe_lift(arm, t, deg):
    """Height the ankle rises when the foot pitches `deg` toes-down about the placement point
    with the toe kept on the floor."""
    ref = foot_ref(arm, t)
    d0 = arm.pose.bones[f'つま先ＩＫ.{t}'].bone.head_local - ref
    d1 = Quaternion((1, 0, 0), math.radians(deg)) @ d0
    return d0.z - d1.z


def apply(arm, P):
    """Pose the armature (from rest) with parameters P."""
    yaw = P['turn']
    centre(arm, P['c'], yaw=yaw)
    rest_c = arm.pose.bones['センター'].bone.head_local
    q = Quaternion((0, 0, 1), math.radians(yaw))
    for t in 'LR':
        s = 1 if t == 'L' else -1
        off = Vector(P[f'f{t}'])
        pitch = P[f'fp{t}'] + P[f'tip{t}']
        off.z += _toe_lift(arm, t, P[f'tip{t}']) if P[f'tip{t}'] else 0.0
        if abs(yaw) < 1e-6:
            foot(arm, t, tuple(off), pitch=pitch, yaw=P[f'fy{t}'])
            continue
        # turned: the foot's mark goes round the vertical through the centre
        a0v = foot_ref(arm, t)
        piv = Vector((rest_c.x, rest_c.y, a0v.z))
        offw = _m(t, off)
        pos = q @ (a0v + offw - piv) + piv
        dq = q @ Quaternion((0, 0, 1), math.radians(P[f'fy{t}'] * s)) @ Quaternion((1, 0, 0), math.radians(pitch))
        dd = dq @ (arm.pose.bones[f'つま先ＩＫ.{t}'].bone.head_local - a0v)
        o = pos - a0v
        foot(arm, t, (o.x * s, o.y, o.z), toe_dir=(dd.x * s, dd.y, dd.z))
    if P['lp']:
        turn(arm, '下半身', (1, 0, 0), P['lp'])
    if P['lr']:
        turn(arm, '下半身', (0, 1, 0), P['lr'])
    if P['ly']:
        turn(arm, '下半身', (0, 0, 1), P['ly'])
    mp.spine(arm, pitch=P['sp'], yaw=P['sy'], roll=P['sr'])
    mp.head(arm, yaw=P['hy'], pitch=P['hp'], roll=P['hr'])
    for t in 'LR':
        s = 1 if t == 'L' else -1
        if P[f'sh{t}']:
            bend(arm, f'肩.{t}', (0, 0, 1), P[f'sh{t}'])
        reach(arm, t, P[f'w{t}'], P.get(f'n{t}', P[f'k{t}']))
        if P[f'p{t}']:
            n = f'手捩.{t}' if f'手捩.{t}' in arm.pose.bones else f'手首.{t}'
            twist(arm, n, P[f'p{t}'] * s)
        if P[f'b{t}']:
            bend(arm, f'手首.{t}', (0, -1, 0), P[f'b{t}'])
        finger_curl(arm, t, P[f'g{t}'], P[f'gi{t}'], P[f'gt{t}'], P.get(f'gm{t}'))


# ------------------------------------------------------------------ poses used by several clips
# wrist positions (left side, rest world m); shoulder 腕.L at (0.116, -0.043, 1.143), arm ~0.43 m


def C(x=0.0, y=0.0, z=0.0):
    """A centre offset relative to the stance's."""
    return (x, y, STANCE['c'][2] + z)


C0 = C()
REST_ARMS = {**{k + 'L': v for k, v in REST_SIDE['L'].items()}, **{k + 'R': v for k, v in REST_SIDE['R'].items()},
             'shL': 0.0, 'shR': 0.0}
BODY0 = dict(c=C0, lp=0.0, lr=0.0, ly=0.0, sp=STANCE['sp'], sy=0.0, sr=0.0, hp=0.0, hy=0.0, hr=0.0)
FEET0 = dict(f=(0.0, 0.0, 0.0), fp=0.0, fy=STANCE['fyL'], tip=0.0)


def _side(d, t):
    """A both-sides pose dict for one side only."""
    return {k + t: v for k, v in d.items()}


def rest_arm(t):
    """The rest arm of side t."""
    return _side(dict(REST_SIDE[t], sh=0.0), t)


HIPS = dict(w=(0.17, -0.02, 1.00), k=(1.0, 0.5, -0.6), p=30.0, b=-10.0, g=1.0, gi=1.0, gt=0.7)     # fists on the hips
CHEST_HOLD = dict(w=(0.06, -0.22, 1.08), k=(1.0, 0.2, -0.8), p=-75.0, b=15.0, g=0.6, gi=0.55, gt=0.35)   # hands together at the chest
FACE_COVER = dict(w=(0.05, -0.18, 1.235), k=(0.45, -0.2, -1.0), p=75.0, b=-35.0, g=0.08, gi=0.05, gt=0.15)
CLASP_FRONT = dict(w=(0.05, -0.245, 0.925), k=(1.0, 0.25, -0.3), p=-45.0, b=10.0, g=0.45, gi=0.4, gt=0.3)
ARMS_OUT = dict(w=(0.52, -0.06, 1.10), k=(0.2, 0.6, -1.0), p=10.0, g=0.15, gi=0.1, gt=0.1)
FIST = dict(g=1.0, gi=1.0, gt=0.7)
HEART = dict(w=(0.075, -0.27, 1.16), k=(1.0, 0.2, -0.8), p=-90.0, b=20.0, g=0.6, gi=0.6, gt=0.0, sh=4.0)   # fingers curved into a heart at the chest
SKIRT_HOLD = dict(w=(0.28, -0.14, 0.83), k=(0.6, 0.5, -1.0), p=-35.0, b=10.0, g=0.65, gi=0.55, gt=0.6)   # pinching the skirt out
V_EYE = dict(w=(0.14, -0.17, 1.23), k=(1.0, -0.1, -1.0), p=-90.0, b=-10.0, g=1.0, gm=0.0, gi=0.0, gt=0.9, sh=5.0)  # a V by the eye
PAWS = dict(w=(0.11, -0.22, 1.16), k=(1.0, 0.0, -0.8), p=-60.0, b=55.0, g=0.8, gi=0.75, gt=0.4)       # cat paws at the chin
BUNNY = dict(w=(0.11, -0.04, 1.42), k=(1.0, 0.2, 0.0), p=-60.0, b=-10.0, g=1.0, gm=0.0, gi=0.0, gt=0.9, sh=6.0)  # V ears on the head
PRAY = dict(w=(0.02, -0.22, 1.12), k=(0.6, -0.2, -1.0), p=-10.0, b=-10.0, g=0.05, gi=0.05, gt=0.1)   # palms together
CUP = dict(w=(0.04, -0.20, 1.17), k=(1.0, 0.0, -0.9), p=-90.0, b=20.0, g=0.6, gi=0.6, gt=0.4)         # cupped hands under the chin
CHEEKS = dict(w=(0.07, -0.17, 1.19), k=(0.5, -0.3, -1.0), p=60.0, b=-20.0, g=0.2, gi=0.15, gt=0.2)    # cheeks in the hands
BEHIND = dict(w=(0.04, 0.10, 0.92), k=(0.3, 0.8, -1.0), p=-60.0, b=10.0, g=0.5, gi=0.4, gt=0.3)        # hands behind the back
TSUN = dict(w=(0.03, -0.21, 1.04), k=(1.0, 0.2, -0.8), p=-80.0, b=0.0, g=0.85, gi=0.0, gt=0.5)        # index fingertips together
GANBARE = dict(w=(0.13, -0.22, 1.08), k=(1.0, 0.1, -1.0), p=-60.0, b=0.0, g=1.0, gi=1.0, gt=0.7)     # little fists up
SELF_HUG = dict(wL=(-0.12, -0.15, 1.09), wR=(-0.11, -0.19, 1.06), k=(1.0, -0.2, -0.6), p=-60.0, b=0.0, g=0.3, gi=0.3, gt=0.3)
OPEN_UP = dict(w=(0.36, -0.14, 1.30), k=(0.5, 0.4, -1.0), p=-70.0, b=-5.0, g=0.08, gi=0.05, gt=0.1, sh=6.0)   # arms up in a V
TWIRL_ARMS = dict(w=(0.44, -0.10, 1.02), k=(0.3, 0.6, -1.0), p=15.0, b=0.0, g=0.1, gi=0.05, gt=0.1)
CLAP_OPEN = dict(w=(0.14, -0.27, 1.03), k=(1.0, 0.1, -0.6), p=-15.0, b=-10.0, g=0.05, gi=0.0, gt=0.1)
STARTLE_HANDS = dict(w=(0.17, -0.20, 1.10), k=(1.0, 0.1, -0.7), p=-60.0, b=-30.0, g=0.05, gi=0.0, gt=0.0, sh=10.0)
# right-hand only poses (sided names)
BROW_R = dict(wR=(0.10, -0.19, 1.33), kR=(1.0, -0.2, -0.6), pR=-30.0, bR=0.0, gR=0.1, giR=0.05, gtR=0.2, shR=6.0)
KISS_R = dict(wR=(0.04, -0.19, 1.19), kR=(1.0, -0.2, -1.0), pR=-60.0, bR=-20.0, gR=0.4, giR=0.3, gtR=0.4, shR=3.0)
SCRATCH_R = dict(wR=(0.08, -0.16, 1.20), kR=(1.0, -0.2, -1.0), pR=-30.0, bR=10.0, gR=0.9, giR=0.0, gtR=0.6, shR=4.0)
HAIR_R = dict(wR=(0.15, -0.10, 1.20), kR=(1.0, -0.2, -0.8), pR=-60.0, bR=10.0, gR=0.8, giR=0.0, gtR=0.3, shR=5.0)
CHIN_R = dict(wR=(0.05, -0.19, 1.15), kR=(1.0, -0.1, -1.0), pR=-70.0, bR=20.0, gR=0.7, giR=0.5, gtR=0.5)
WAVE_UP_R = dict(wR=(0.36, -0.10, 1.31), kR=(0.6, 0.2, -1.0), pR=-70.0, bR=0.0, gR=0.05, giR=0.0, gtR=0.1, shR=5.0)


def sway(s, a=1.0, **kw):
    """A soft weight shift onto her left (s=1) or right (s=-1) foot, the head tilting with it (kw
    override)."""
    d = dict(c=C(0.014 * s * a, 0.0, -0.004 * a), lr=-3.0 * s * a, sr=2.0 * s * a, hr=4.0 * s * a)
    d.update(kw)
    return d


# ------------------------------------------------------------------ expressions

def fx(m, a, b, w=1.0, r=6):
    """Morph m eased in from frame a, held, eased out by frame b."""
    return [(a, m, 0.0), (a + r, m, w), (b - r, m, w), (b, m, 0.0)]


def pulse(m, a, w=1.0, hold=2, r=3):
    """A quick morph (a wink, a blink-smile) peaking at frame a."""
    return [(a - r, m, 0.0), (a, m, w), (a + hold, m, w), (a + hold + r, m, 0.0)]


def _face_weights(face, frame):
    """Sum of the expression weights at `frame` (linear between keys)."""
    tot = 0.0
    by = {}
    for f, m, w in face:
        by.setdefault(m, []).append((f, w))
    for m, ks in by.items():
        ks.sort()
        for (f0, w0), (f1, w1) in zip(ks, ks[1:]):
            if f0 <= frame <= f1:
                tot += w0 + (w1 - w0) * (frame - f0) / max(f1 - f0, 1e-9)
                break
    return tot


_FACE_ERRORS = []


def _check_face(name, frames, face, loop):
    """Each morph's keys in time order; some expression on the face throughout (not just at the ends)."""
    by = {}
    for f, m, w in face:
        by.setdefault(m, []).append(f)
    for m, fs in by.items():
        if fs != sorted(fs) or len(set(fs)) != len(fs):
            _FACE_ERRORS.append(f'{name}: overlapping {m} keys {fs}')
    lo, hi = (0, frames) if loop else (8, frames - 8)
    blank = [f for f in range(lo, hi + 1) if _face_weights(face, f) < 0.12]
    if blank:
        _FACE_ERRORS.append(f'{name}: a blank face at frames {blank[0]}..{blank[-1]} ({len(blank)})')


# ------------------------------------------------------------------ the idle loop

def _idle(frame):
    """8 s: three soft breaths, a weight shift each way with the free knee easing, head tilts,
    the thumbs fidgeting; frame 0 / 240 = STANCE."""
    P = dict(STANCE)
    ph = 2 * math.pi * frame / 240.0
    br = math.sin(ph * 3)                 # three breaths a loop
    sw = math.sin(ph)                     # one slow sway, left then right
    P['c'] = (0.010 * sw, 0.0, -0.006 - 0.0025 * (1 - math.cos(ph * 6)) * 0.5 - 0.003 * sw * sw)
    P['lr'] = -2.0 * sw
    P['ly'] = 1.2 * math.sin(ph * 2)
    P['sr'] = 1.4 * sw
    P['sp'] = 2.0 - 0.8 * br
    P['sy'] = -1.0 * math.sin(ph * 2)
    P['hr'] = 3.0 * math.sin(ph) + 1.6 * math.sin(ph * 2)
    P['hy'] = 2.0 * math.sin(ph * 2) - 1.0 * math.sin(ph * 3)
    P['hp'] = 1.0 * math.sin(ph * 3 - 0.0) * 0.8 + 1.2 * math.sin(ph) ** 2
    P['tipL'] = 5.0 * max(0.0, -sw) ** 2   # the knee off the weight relaxes
    P['tipR'] = 5.0 * max(0.0, sw) ** 2
    for t in 'LR':
        s = 1 if t == 'L' else -1
        P[f'sh{t}'] = 1.2 * (1 - math.cos(ph * 3)) * 0.5
        w = Vector(STANCE[f'w{t}'])
        P[f'w{t}'] = (w.x + 0.003 * br, w.y - 0.004 * math.sin(ph * 3), w.z + 0.004 * br + 0.004 * s * sw)
        P[f'gt{t}'] = REST_GT + 0.12 * math.sin(ph * 2 + (0 if t == 'L' else math.pi)) ** 2
        P[f'gi{t}'] = REST_GI + 0.06 * math.sin(ph * 4) ** 2
    return P


# ------------------------------------------------------------------ locomotion (in place)
# The runtime moves her root along its path; these cycles keep the centre in place and slide each
# planted foot backward at the travel speed (stride per cycle / cycle length), so the feet do not
# skate when the root moves forward at that speed.

def _hermite(p0, p1, m0, m1, s):
    s2, s3 = s * s, s * s * s
    return (2 * s3 - 3 * s2 + 1) * p0 + (s3 - 2 * s2 + s) * m0 + (-2 * s3 + 3 * s2) * p1 + (s3 - s2) * m1


def _foot_cycle(ph, d, span, lift, toe, peak=0.5, hop=0.0):
    """One foot at cycle phase ph (0 = touchdown in front): (y, z, tip deg). Planted for d of the
    cycle, sliding back by `span` at a constant speed (heel peeling up `toe` deg at the end),
    then swinging forward through the air (`lift` m high, its height peaking at `peak` of the swing).
    `hop` lifts the planted foot that much mid-stance (a skip's hop)."""
    ph %= 1.0
    if ph < d:
        u = ph / d
        y = -span / 2 + span * u
        tipd = toe * max(0.0, (u - 0.55) / 0.45) ** 2
        z = hop * math.sin(math.pi * min(max((u - 0.4) / 0.35, 0.0), 1.0)) ** 2 if hop else 0.0
        if hop:
            tipd = max(tipd, toe * 0.8 * math.sin(math.pi * min(max((u - 0.3) / 0.55, 0.0), 1.0)) ** 2)
        return y, z, tipd
    s = (ph - d) / (1 - d)
    v = span / d * (1 - d)                    # the planted speed, in swing-phase units
    y = _hermite(span / 2, -span / 2, v, v, s)
    e = s ** (math.log(0.5) / math.log(peak))  # remap so the height peaks at `peak`
    z = lift * math.sin(math.pi * e) ** 2
    tipd = toe * (1 - s) ** 2
    return y, z, tipd


def _lerp(a, b, t):
    if isinstance(a, tuple):
        return tuple(x + (y - x) * t for x, y in zip(a, b))
    return a + (b - a) * t


def _gait(frame, n, stride, d, lift, toe, peak=0.5, hop=0.0, inward=0.012):
    """Both feet, the left half a cycle after the right; frame 0 = the right foot mid-stance."""
    span = stride * d
    u = frame / float(n)
    P = {}
    for t, off in (('R', d / 2), ('L', d / 2 + 0.5)):
        y, z, tipd = _foot_cycle(u + off, d, span, lift, toe, peak, hop)
        P[f'f{t}'] = (-inward, y, z)
        P[f'tip{t}'] = tipd
    return u, P


def _arm_swing(P, u, base, amp, up, lead, k=(1.0, 0.5, -0.6), p=-45.0, b=10.0, out=0.0):
    """Arms swinging opposite the legs: the left arm forward when the right foot lands (u=lead)."""
    for t, s in (('L', 1), ('R', -1)):
        a = s * math.cos(2 * math.pi * (u - lead))     # +1: this arm forward
        P[f'w{t}'] = (base[0] + out * max(a, 0.0), base[1] - amp * a, base[2] + up * a)
        P[f'k{t}'] = k
        P[f'p{t}'] = p
        P[f'b{t}'] = b - 8.0 * a


WALK_N, WALK_STRIDE = 32, 0.54
RUN_N, RUN_STRIDE = 20, 1.0
SKIP_N, SKIP_STRIDE = 36, 0.8
TIPTOE_N, TIPTOE_STRIDE = 48, 0.36


def _walk(frame):
    """A light girlish walk, 32 frames a cycle: feet close to one line, a soft bob, a little hip
    sway, the arms swinging gently with the hands flicking out."""
    P = dict(STANCE)
    d = 0.6
    u, feet = _gait(frame, WALK_N, WALK_STRIDE, d, 0.07, 22.0, peak=0.45, inward=0.018)
    P.update(feet)
    c2 = math.cos(4 * math.pi * u)
    a = math.cos(2 * math.pi * (u - 0.72))
    P['c'] = (-0.016 * math.cos(2 * math.pi * u), 0.0, -0.030 + 0.011 * c2)
    P['lr'] = 3.0 * math.cos(2 * math.pi * u)
    P['ly'] = 4.0 * a
    P['sy'] = -4.0 * a
    P['sp'] = 3.0
    P['sr'] = -1.2 * math.cos(2 * math.pi * u)
    P['hr'] = 2.0 * math.cos(2 * math.pi * u) + 2.0
    P['hp'] = -1.0 + 1.0 * c2
    P['hy'] = 1.5 * a
    _arm_swing(P, u, (0.13, -0.19, 0.90), 0.04, 0.015, 0.72, k=(0.15, -0.03, -1.0), p=-45.0, b=-5.0)
    for t in 'LR':
        P[f'g{t}'] = P[f'gm{t}'] = 0.35
        P[f'gi{t}'] = 0.25
        P[f'gt{t}'] = 0.3
    return P


def _run(frame):
    """A girlish run, 20 frames a cycle: short quick strides, heels kicking up behind, forearms
    pumping across in front with soft fists, a flight phase each step."""
    P = dict(STANCE)
    d = 0.38
    u, feet = _gait(frame, RUN_N, RUN_STRIDE, d, 0.17, 35.0, peak=0.35, inward=0.02)
    P.update(feet)
    a = math.cos(2 * math.pi * (u - 0.78))
    P['c'] = (-0.012 * math.cos(2 * math.pi * u), 0.0, -0.047 - 0.024 * math.cos(4 * math.pi * u))
    P['sp'] = 10.0
    P['lr'] = 2.0 * math.cos(2 * math.pi * u)
    P['ly'] = 6.0 * a
    P['sy'] = -7.0 * a
    P['hp'] = -6.0
    P['hy'] = 3.0 * a
    P['hr'] = 2.0 * math.cos(2 * math.pi * u)
    _arm_swing(P, u, (0.13, -0.20, 1.02), 0.07, 0.05, 0.78, k=(0.3, 0.4, -1.0), p=-60.0, b=10.0, out=0.01)
    for t in 'LR':
        P[f'g{t}'] = P[f'gm{t}'] = 0.65
        P[f'gi{t}'] = 0.6
        P[f'gt{t}'] = 0.45
        P[f'sh{t}'] = 3.0
    return P


def _skip(frame):
    """A happy skip, 36 frames a cycle (step-hop on each foot): the free knee lifts high, a bounce
    on each hop, the arms swinging up high."""
    P = dict(STANCE)
    d = 0.45
    u, feet = _gait(frame, SKIP_N, SKIP_STRIDE, d, 0.17, 30.0, peak=0.4, hop=0.03, inward=0.015)
    P.update(feet)
    a = math.cos(2 * math.pi * (u - 0.72))
    hopz = math.cos(2 * math.pi * (u - 0.17)) ** 2   # peaks at each hop
    P['c'] = (-0.014 * math.cos(2 * math.pi * u), 0.0, -0.052 + 0.052 * hopz)
    P['sp'] = 2.0 - 3.0 * hopz
    P['ly'] = 5.0 * a
    P['sy'] = -6.0 * a
    P['hp'] = -3.0 * hopz
    P['hr'] = 4.0 * math.cos(2 * math.pi * u)
    P['hy'] = 2.0 * a
    _arm_swing(P, u, (0.16, -0.21, 1.02), 0.09, 0.11, 0.72, k=(0.3, 0.4, -1.0), p=-55.0, b=-10.0, out=0.02)
    for t in 'LR':
        P[f'g{t}'] = P[f'gm{t}'] = 0.2
        P[f'gi{t}'] = 0.1
        P[f'gt{t}'] = 0.2
        P[f'sh{t}'] = 3.0 + 3.0 * hopz
    return P


def _tiptoe(frame):
    """Sneaking on tiptoe, 48 frames a cycle: knees soft and lifting high, leaning in, paws held
    up at the chest, the head peering left and right."""
    P = dict(STANCE)
    d = 0.7
    u, feet = _gait(frame, TIPTOE_N, TIPTOE_STRIDE, d, 0.09, 0.0, peak=0.45, inward=0.01)
    P.update(feet)
    for t in 'LR':
        P[f'tip{t}'] = 22.0 + feet[f'tip{t}']
    c2 = math.cos(4 * math.pi * u)
    P['c'] = (-0.018 * math.cos(2 * math.pi * u), 0.0, -0.055 + 0.008 * c2)
    P['sp'] = 14.0
    P['lr'] = 3.0 * math.cos(2 * math.pi * u)
    P['sr'] = -2.0 * math.cos(2 * math.pi * u)
    P['hp'] = -8.0
    P['hy'] = 18.0 * math.sin(2 * math.pi * u)
    P['hr'] = -5.0 * math.sin(2 * math.pi * u)
    for t, s in (('L', 1), ('R', -1)):
        bob = 0.012 * math.cos(2 * math.pi * u + (0 if t == 'L' else math.pi))
        P[f'w{t}'] = (0.12, -0.23, 1.09 + bob)
        P[f'k{t}'] = (1.0, 0.0, -0.8)
        P[f'p{t}'] = -60.0
        P[f'b{t}'] = 50.0
        P[f'g{t}'] = P[f'gm{t}'] = 0.7
        P[f'gi{t}'] = 0.6
        P[f'gt{t}'] = 0.4
        P[f'sh{t}'] = 6.0
    return P


def _blend_fn(n, a_fn, b_fn, extra=None):
    """0..n: from pose a_fn(f) to b_fn(f), eased; extra(f, s, P) may add an accent."""
    def fn(frame):
        s = min(max(frame / float(n), 0.0), 1.0)
        s = s * s * (3 - 2 * s)
        A, B = a_fn(frame), b_fn(frame)
        P = {p: _lerp(A[p], B[p], s) for p in PARAMS}
        if extra:
            extra(frame, s, P)
        return P
    return fn


CLIPS = {}
MANIFEST = {}


def clip(name, frames, keys, kind, desc, look=False, face=(), loop=False, loop_fn=None, root_end=None, **extra):
    """Register a clip. root_end (Blender axes, m: +x her left, -y forward, +z up) displaces the end
    pose; the manifest gives it in MMD axes ([x, up, z], -z toward the viewer)."""
    CLIPS[name] = Clip(frames, keys, loop_fn, root_end or (0.0, 0.0, 0.0))
    face = sorted(face, key=lambda k: (k[1], k[0]))     # per morph, in time
    _check_face(name, frames, face, loop)
    m = {'frames': frames, 'loop': loop, 'look': look, 'kind': kind, 'desc': desc}
    if root_end:
        m['root_end'] = [round(root_end[0], 4), round(root_end[2], 4), round(root_end[1], 4)]
    m.update(extra)
    m['face'] = [[f, mo, round(w, 3)] for f, mo, w in face]
    MANIFEST[name] = m


clip('idle', 240, [S(0), S(240)], 'ambient', 'Standing with her arms relaxed at her sides, breathing softly, '
     'shifting her weight and tilting her head.', look=True, loop=True, loop_fn=_idle,
     face=[(0, 'にこり', 0.25), (60, 'にこり', 0.4), (120, 'にこり', 0.2), (180, 'にこり', 0.45), (240, 'にこり', 0.25),
           (0, '口角上げ', 0.2), (120, '口角上げ', 0.35), (240, '口角上げ', 0.2)])

# ------------------------------------------------------------------ the clips the site already uses

# look_around: curious glances each way on her toes, a finger to the chin, then "ah!" at the viewer
clip('look_around', 210, [
    S(0), K(10, hp=5, sp=4, c=C(0, 0, -0.01)),
    K(28, hy=45, hp=-6, sy=12, ly=4, c=C(0.012), hr=8, tipR=10, wL=(0.10, -0.24, 0.98), pL=-70.0),
    K(50, hy=50, hp=-8, hr=10),
    K(62, hy=0, hp=2, sy=0, ly=0, c=C0, hr=0, tipR=0, **rest_arm('L')),
    K(80, hy=-46, hp=-4, sy=-11, ly=-4, hr=-8, c=C(-0.012), tipL=10, wR=(0.10, -0.24, 0.98), pR=-70.0),
    K(102, hy=-50, hr=-10),
    K(116, hy=-6, hp=6, sy=0, ly=0, hr=10, c=C(0, 0, -0.008), tipL=0, **CHIN_R, wL=(0.07, -0.21, 1.02), pL=-70.0, bL=10.0),
    K(136, hy=8, hp=2, **sway(1, hr=14)),
    K(152, hr=4, hy=0, hp=-4, c=C(0, 0, 0.0), tip=8, wR=(0.30, -0.22, 1.18), kR=(0.6, 0.3, -1.0), pR=-80.0, bR=0.0,
      gR=0.1, giR=0.0, gtR=0.1, shR=6.0, sr=0, lr=0),
    K(166, tip=0, hr=6, c=C0),
    K(186, **REST_ARMS, hr=2, hp=0, hy=0), S(210)],
    'ambient', 'Looks curiously left and right on her toes, puts a finger to her chin, then has an idea.',
    face=fx('口角上げ', 2, 208, 0.25) + fx('瞳小', 20, 108, 0.35) + fx('う', 26, 56, 0.35) + fx('はぅ', 76, 108, 0.4) + fx('真面目', 112, 152, 0.5)
    + fx('う', 116, 150, 0.3) + fx('びっくり', 150, 168, 0.5, r=4) + fx('笑い', 158, 204, 0.8) + fx('ワ', 150, 176, 0.6, r=4)
    + fx('にこり', 2, 30, 0.3))

# stretch: fingers laced overhead, up on the toes, a lean each way, a happy sigh, arms float down
STRETCH_UP = dict(w=(0.04, -0.10, 1.54), k=(1.0, 0.1, 0.25), p=-80.0, b=-25.0, g=0.55, gi=0.55, gt=0.3, sh=9.0)
clip('stretch', 210, [
    S(0), K(10, sp=8, hp=6, c=C(0, 0, -0.025), w=(0.06, -0.26, 0.95), k=(1.0, 0.3, -0.6), p=-70.0),
    K(30, **STRETCH_UP, sp=-6, hp=-14, c=C0, tip=14),
    K(52, sp=-9, hp=-16, tip=16), K(74, sr=12, lr=-6, hr=8, sp=-4, tip=4, c=C(-0.015), tipR=12),
    K(98, sr=-12, lr=6, hr=-8, c=C(0.015), tipR=0, tipL=12), K(116, sr=0, lr=0, hr=0, sp=-4, c=C0, tip=0),
    K(132, w=(0.46, -0.05, 1.28), k=(0.2, 0.7, -1.0), p=10.0, b=0.0, g=0.15, gi=0.1, gt=0.1, sh=3.0, hp=4, sp=2),
    K(150, w=(0.36, -0.12, 0.98), k=(0.8, 0.6, -0.6), p=-20.0, hp=2, hr=6, **{'c': C(0, 0, -0.012)}),
    K(166, **REST_ARMS, hr=8), K(184, hr=0), S(210)],
    'ambient', 'A big stretch with the fingers laced overhead, swaying each way on her toes, then a contented sigh.',
    face=fx('まばたき', 20, 76, 1.0) + fx('お', 22, 70, 0.6) + fx('なごみ', 70, 204, 0.7) + fx('ω', 124, 196, 0.5)
    + fx('にこり', 2, 30, 0.3) + fx('照れ', 150, 200, 0.3))

# yawn: hand over the mouth, head back, the other arm up; then rubs an eye and gives a sleepy smile
clip('yawn', 210, [
    S(0), K(8, hp=4, sp=4),
    K(26, hp=-16, sp=-5, shL=8, shR=10, wR=(0.012, -0.165, 1.19), kR=(0.6, -0.3, -1.0), pR=60.0, bR=-25.0,
      gR=0.12, giR=0.1, gtR=0.25, wL=(0.30, -0.03, 1.44), kL=(1.0, 0.3, 0.0), pL=-30.0, bL=-15.0, gL=0.3, giL=0.25,
      gtL=0.2, tip=8),
    K(56, hp=-19, shL=12, shR=12, wL=(0.31, -0.02, 1.47), tip=10), K(70, hp=6, sp=6, shL=0, shR=0, tip=0),
    K(84, wR=(0.08, -0.17, 1.27), kR=(1.0, -0.3, -1.0), pR=-20.0, bR=30.0, gR=0.8, giR=0.6, gtR=0.6, hp=10, hr=-8,
      **rest_arm('L')),
    K(94, wR=(0.09, -0.17, 1.285)), K(104, wR=(0.075, -0.17, 1.27)), K(114, wR=(0.09, -0.17, 1.285)),
    K(130, **rest_arm('R'), hp=4, **sway(-1, hr=6)), K(160, **sway(1), hp=2), K(184, hr=0, c=C0, lr=0, sr=0),
    S(210)],
    'ambient', 'A big yawn behind her hand with one arm stretching up, then rubs her eye and smiles sleepily.',
    face=fx('あ', 18, 70, 0.9) + fx('まばたき', 20, 120, 1.0) + fx('涙', 62, 150, 0.5) + fx('なごみ', 116, 204, 0.6)
    + fx('ω', 124, 196, 0.4) + fx('困る', 2, 24, 0.3))

# hair_tuck: tucks the hair behind her ear, then smooths it down and peeks at the viewer
clip('hair_tuck', 180, [
    S(0), K(10, hr=-4, hy=-6),
    K(30, wR=(0.10, -0.10, 1.25), kR=(0.6, -0.7, -0.3), pR=-60.0, bR=-10.0, gR=0.1, giR=0.05, gtR=0.15,
      shR=6, hr=-10, hy=-10, sr=-3),
    K(44, wR=(0.105, -0.04, 1.29), kR=(0.8, -0.5, -0.1), bR=-25.0, hr=-12),
    K(56, wR=(0.115, -0.01, 1.28), gR=0.3, giR=0.25),
    K(72, wR=(0.17, -0.07, 1.10), kR=(1.0, -0.2, -0.6), pR=-70.0, bR=10.0, gR=0.3, giR=0.2, hr=-6),
    K(88, wR=(0.18, -0.09, 1.02), hp=6, hy=-14),
    K(104, **rest_arm('R'), hy=4, hp=8, **sway(1, hr=6, sr=0)),
    K(126, hp=-2, hy=0), K(146, **sway(1, 0.5)), S(180)],
    'ambient', 'Tucks a lock of hair behind her ear, lets it slip through her fingers, and glances up shyly.',
    look=True, face=fx('にこり', 4, 174, 0.6) + fx('照れ', 26, 150, 0.5) + fx('ω', 30, 84, 0.5) + fx('はぅ', 100, 140, 0.4))

# heel_rock: hands clasped in front, rocking onto the toes and back, a little hum
_rock = []
for i, f in enumerate((18, 36, 54, 72, 90, 108, 126)):
    up = i % 2 == 0
    _rock.append(K(f, tip=14 if up else 0, c=C(0, 0, 0.0 if up else -0.014), sp=0 if up else 5,
                   hp=-4 if up else 4, hr=4 * (1 if i % 4 == 0 else -1), fp=0 if up else -4))
clip('heel_rock', 180, [S(0), K(10, **CLASP_FRONT, sp=4)] + _rock + [
    K(140, tip=0, hr=0, sp=2, fp=0, c=C0), K(156, **REST_ARMS), S(180)],
    'ambient', 'Rocks up onto her toes and back on her heels with her hands clasped, humming.',
    look=True, face=fx('にこり', 4, 174, 0.5) + fx('ω', 14, 150, 0.6) + fx('なごみ', 30, 120, 0.5))

# kick_pebble: eyes down, draws the foot back and flicks a pebble, watches it roll, a pleased little nod
clip('kick_pebble', 180, [
    S(0), K(12, hp=24, hy=-6, sp=6, **BEHIND),
    K(26, fR=(0.0, 0.16, 0.07), fpR=25, c=C(0.012, 0.01, -0.014), sp=2, lr=4),
    K(34, fR=(0.01, -0.22, 0.11), fpR=-8, c=C(0.01, -0.02, -0.004), sp=8),
    K(40, fR=(0.01, -0.24, 0.12)),
    K(52, fR=(0.0, -0.05, 0.0), fpR=0, c=C0, lr=0, hp=6, hy=-22, sy=-6, sp=2),
    K(80, hy=-34, hp=-2, sy=-9, tipL=8), K(96, hy=-4, sy=0, hp=0, fR=(0.0, 0.0, 0.0), tipL=0),
    K(108, hp=8), K(116, hp=-2, hr=8), K(130, **REST_ARMS, hr=4), K(150, hr=0), S(180)],
    'ambient', 'Kicks an imaginary pebble with her hands behind her back, watches it roll away and nods.',
    face=fx('口角上げ', 2, 178, 0.25) + fx('う', 8, 34, 0.4) + fx('真面目', 10, 34, 0.3) + fx('口角上げ', 30, 64, 0.5) + fx('にやり', 58, 110, 0.5)
    + fx('にこり', 104, 174, 0.6))

# hum_sway: swaying from foot to foot to a tune, hands behind her, head tilting with the beat
_sway = []
for i, f in enumerate(range(18, 216, 24)):
    s = 1 if i % 2 == 0 else -1
    _sway.append(K(f, c=C(0.03 * s, 0.0, -0.008), lr=-5 * s, sr=4 * s, hr=10 * s, hy=5 * s,
                   **{('tipR' if s > 0 else 'tipL'): 16, ('tipL' if s > 0 else 'tipR'): 0}))
clip('hum_sway', 240, [S(0), K(12, **BEHIND)] + _sway + [K(214, **REST_ARMS), S(240)], 'ambient',
     'Sways from foot to foot humming a tune, hands behind her back, head tilting to the beat.', look=True,
     face=fx('ω', 6, 234, 0.8) + fx('なごみ', 6, 234, 0.6) + pulse('にこり', 66, 0.6, 6, 6) + pulse('にこり', 162, 0.6, 6, 6))

# check_shoe: lifts the left foot behind her, looks back and down at the shoe, turns it, taps it down
clip('check_shoe', 180, [
    S(0), K(10, c=C(-0.02, 0.0, -0.004), lr=3),
    K(30, fL=(0.0, 0.10, 0.16), fpL=35, fyL=-4, c=C(-0.035, 0.0, -0.009), lr=5, sp=6, sy=22, hy=46, hp=30, hr=8,
      wL=(0.25, 0.02, 0.92), kL=(1.0, 0.5, -0.4), pL=-20.0, bL=0.0, gL=0.3, wR=(0.20, -0.18, 0.98), pR=-60.0),
    K(52, fyL=-24, fpL=40), K(70, fyL=14), K(86, fyL=-4, hp=26, hr=4),
    K(100, fL=(0.0, 0.0, 0.0), fpL=0, fyL=3, c=C(-0.01, 0.0, -0.004), lr=0, sp=2, sy=0, hy=0, hp=2, hr=0,
      **REST_ARMS),
    K(110, tipL=18, fL=(0.0, -0.02, 0.0)), K(116, tipL=0), K(122, tipL=18), K(128, tipL=0, fL=(0.0, 0.0, 0.0), hr=8),
    K(150, hr=0, c=C0), S(180)],
    'ambient', 'Lifts a foot behind her to check her shoe, turns it this way and that, then taps her toe twice.',
    face=fx('真面目', 26, 100, 0.5) + fx('う', 30, 92, 0.4) + fx('瞳小', 2, 30, 0.3) + fx('にこり', 96, 174, 0.6)
    + fx('ω', 104, 150, 0.4))

# sneeze: hitching breaths, the hand comes up, "kchu!", a head shake, rubs her nose, embarrassed
clip('sneeze', 165, [
    S(0), K(8, hp=-6, sp=-2, shL=3, shR=3),
    K(16, hp=-12, sp=-5, shL=6, shR=6, wR=(0.10, -0.20, 1.12), kR=(1.0, -0.2, -0.8), pR=-60.0, gR=0.3, giR=0.2),
    K(24, hp=-8, sp=-3), K(30, hp=-17, sp=-8, shL=9, shR=9, c=C(0.0, 0.02)),
    K(35, hp=24, sp=22, shL=0, shR=0, c=C(0.0, -0.02, -0.024), wR=(0.012, -0.17, 1.18), kR=(0.6, -0.3, -1.0), pR=60.0,
      gR=0.15, giR=0.1, tip=6),
    K(42, hp=18, sp=16, tip=0), K(52, hp=4, sp=4, hy=12, c=C0, wR=(0.04, -0.18, 1.17), kR=(1.0, -0.2, -1.0), pR=-20.0,
                                 bR=30.0, gR=0.7, giR=0.3),
    K(57, hy=-12), K(62, hy=9), K(67, hy=-5), K(72, hy=0, hp=6),
    K(80, wR=(0.05, -0.18, 1.18)), K(86, wR=(0.03, -0.18, 1.17)), K(92, wR=(0.05, -0.18, 1.18)),
    K(106, **CHEST_HOLD, hp=10, hr=8, sh=6.0), K(126, **sway(1, 0.6, hr=10)),
    K(144, **REST_ARMS, hr=0, c=C0, lr=0, sr=0, hp=2), S(165)],
    'both', 'Hitching breaths, a cute sneeze into her hand, a head shake, then rubs her nose, embarrassed.',
    face=fx('まばたき', 10, 52, 1.0) + fx('あ', 12, 34, 0.7, r=4) + fx('う', 33, 46, 0.8, r=2) + fx('困る', 4, 30, 0.5)
    + fx('困る', 46, 120, 0.7) + fx('照れ', 96, 160, 0.8) + fx('はぅ', 100, 156, 0.5))

# sit_rest: crouches down hugging the knees, rocks a little, hums, gets back up
SQUAT = dict(c=C(0.0, 0.05, -0.324), sp=30, lp=4, hp=-14)
HUG = dict(w=(0.16, -0.40, 0.95), k=(1.0, 0.35, -0.3), p=-20.0, b=-5.0, g=0.35, gi=0.3, gt=0.3)   # hands on the knees
clip('sit_rest', 330, [
    S(0), K(10, hp=10, sp=6),
    K(30, c=C(0.0, 0.03, -0.174), sp=24, w=(0.20, -0.26, 0.86), k=(1.0, 0.4, -0.4), f=(0.03, 0.0, 0.0), fy=10),
    K(52, **SQUAT, **HUG), K(70, hp=-10, hr=6),
    K(100, sr=4, lr=-3, hr=12, c=C(0.012, 0.05, -0.324)), K(130, sr=-4, lr=3, hr=-10, c=C(-0.012, 0.05, -0.324)),
    K(160, sr=3, lr=-2, hr=8, c=C(0.008, 0.05, -0.324)), K(190, sr=0, lr=0, hr=0, c=C(0.0, 0.05, -0.324), hp=-16),
    K(206, wR=(0.10, -0.30, 1.10), kR=(1.0, 0.2, -0.8), pR=-80.0, gR=0.1, giR=0.0, hp=-20),
    K(216, wR=(0.13, -0.32, 1.11)), K(226, wR=(0.10, -0.30, 1.10)), K(236, **_side(HUG, 'R'), hp=-6),
    K(262, c=C(0.0, 0.04, -0.194), sp=28, w=(0.22, -0.24, 0.88), k=(1.0, 0.4, -0.4), p=-30.0),
    K(286, c=C0, sp=4, hp=2, f=(0.0, 0.0, 0.0), fy=3.0, **REST_ARMS),
    K(300, hr=8), S(330)],
    'ambient', 'Squats down hugging her knees, rocks and hums, gives a little wave from down there, and stands back up.',
    look=True, face=fx('にこり', 2, 50, 0.4) + fx('なごみ', 40, 250, 0.7) + fx('ω', 90, 196, 0.6)
    + fx('笑い', 200, 244, 0.6) + fx('にこり', 240, 324, 0.6))

# head_pat: shoulders up, hands together at the chest, a bashful wiggle, leans into the pat
clip('head_pat', 180, [
    S(0), K(6, hp=-6, shL=8, shR=8, c=C(0, 0, -0.014)),
    K(20, **CHEST_HOLD, hp=10, hr=8, shL=10, shR=10, sp=4, tipR=10, fyR=-12),
    K(40, sy=8, ly=4, hr=12), K(60, sy=-8, ly=-4, hr=4), K(80, sy=6, ly=3, hr=11), K(100, sy=-3, ly=-1, hr=6),
    K(116, sy=0, ly=0, hr=14, hp=14, tipR=0, fyR=3, c=C(0.01, 0, -0.01)), K(132, hr=10, hp=10),
    K(146, **REST_ARMS, hp=2, hr=4, c=C0), S(180)],
    'reaction', 'Being patted on the head: shoulders up, hands at her chest, a bashful wiggle and a happy lean into it.',
    face=fx('照れ', 4, 176, 1.0) + fx('はぅ', 6, 110, 0.8) + fx('まばたき', 10, 150, 0.6) + fx('ω', 104, 170, 0.6))

# poke_startle: a hop back with the hands up, then a pout with fists on the hips, then forgives
clip('poke_startle', 180, [
    S(0), K(3, c=C(0, 0, -0.019)),
    K(9, **STARTLE_HANDS, c=C(0.0, 0.10, 0.036), f=(0.0, 0.08, 0.05), sp=-10, hp=-8),
    K(15, c=C(0.0, 0.12, -0.024), f=(0.0, 0.12, 0.0), sp=-4, hp=-2),
    K(28, sp=0, hp=4, **CHEST_HOLD, sh=4.0),
    K(42, fL=(0.0, 0.03, 0.05), c=C(0.0, 0.07, -0.004)), K(50, fL=(0.0, 0.0, 0.0), c=C(0.0, 0.05, -0.004)),
    K(58, fR=(0.0, 0.03, 0.05), c=C(0.0, 0.02, -0.004)), K(66, fR=(0.0, 0.0, 0.0), c=C0),
    K(78, **HIPS, sh=0.0, sp=-4, hp=-4, hy=-10, hr=-6), K(84, hy=-30, sy=-8), K(110, hy=-34, hr=-10),
    K(122, hy=0, hp=0, sy=0, **sway(1, 0.6, hr=6)),
    K(140, **REST_ARMS, hr=8), K(160, c=C0, lr=0, sr=0, hr=0), S(180)],
    'reaction', 'Startled by a poke: hops back with her hands up, pouts with fists on her hips, then forgives with a smile.',
    face=fx('びっくり', 2, 44, 1.0, r=4) + fx('瞳小', 4, 36, 0.8, r=3) + fx('ワ', 6, 26, 0.7, r=3) + fx('汗', 30, 80, 0.8)
    + fx('怒り', 72, 124, 0.6) + fx('▲', 74, 120, 0.7) + fx('にこり', 118, 176, 0.7))

# annoyed_stomp: hands on hips, two stomps, puffs her cheeks and looks away, peeks back, sticks her tongue out
clip('annoyed_stomp', 180, [
    S(0), K(8, sp=-2, c=C(0, 0, -0.006)),
    K(20, **HIPS, sp=-5, hp=-6, hy=0),
    K(30, fR=(0.0, -0.02, 0.10), fpR=-5, c=C(0.02), lr=4),
    K(35, fR=(0.0, -0.02, 0.0), fpR=0, c=C(0.012, 0.0, -0.024), lr=0, hp=4),
    K(44, fR=(0.0, -0.02, 0.10), c=C(0.02), lr=4, hp=-4),
    K(49, fR=(0.0, -0.02, 0.0), c=C(0.012, 0.0, -0.024), lr=0, hp=4),
    K(60, c=C(0, 0, -0.004), fR=(0.0, 0.0, 0.0), hy=-40, hp=-8, hr=-10, sy=-10, ly=-4),
    K(96, hy=-42, hr=-12), K(108, hy=-12, hp=0, hr=-4), K(116, hy=-40, hr=-10),
    K(132, hy=-8, hr=6, hp=-2), K(146, hy=0, hp=0, hr=0, sy=0, ly=0, **REST_ARMS), S(180)],
    'reaction', 'Fists on her hips, two little stomps, turns away in a huff, peeks back and sticks her tongue out.',
    face=fx('口角上げ', 2, 178, 0.25) + fx('怒り', 8, 150, 0.8) + fx('じと目', 8, 140, 0.7) + fx('▲', 60, 128, 0.7) + fx('ぺろっ', 128, 150, 0.9, r=4)
    + fx('ウィンク', 128, 150, 0.8, r=4) + fx('にこり', 144, 176, 0.4))

# twirl: wind-up, one full turn on the balls of the feet with the arms floating out, a little curtsy
clip('twirl', 165, [
    S(0), K(10, turn=-18, sy=-8, c=C(0, 0, -0.024), hy=-6),
    K(22, turn=40, sy=10, tip=12, c=C(0, 0, 0.002), **TWIRL_ARMS, hy=10),
    K(34, turn=150, tip=14), K(46, turn=265, tip=14), K(58, turn=345, tip=6, sy=2, hy=0),
    K(64, turn=360, tip=0, sy=0, c=C(0, 0, -0.014)),
    K(78, turn=360, c=C(0.0, 0.03, -0.06), **SKIRT_HOLD, fR=(-0.08, 0.12, 0.02), tipR=18, sp=10, hp=10, hr=-8),
    K(96, turn=360, c=C(0.0, 0.03, -0.065), sp=11, hp=12),
    K(112, turn=360, c=C0, sp=2, hp=0, hr=4, fR=(0.0, 0.0, 0.0), tipR=0),
    K(130, turn=360, **REST_ARMS, hr=0), K(165, reset=True, turn=360)],
    'both', 'Twirls once round on her toes with her arms floating out, then finishes with a little curtsy.',
    face=fx('笑い', 14, 100, 0.9) + fx('ワ', 20, 64, 0.5) + fx('にこり', 96, 160, 0.8) + fx('照れ', 70, 150, 0.4)
    + fx('にこり', 2, 22, 0.3))

# jump_happy: two happy hops with the arms swinging up, lands soft, little fists of joy
_hop = []
for i, f0 in enumerate((10, 46)):
    _hop += [K(f0, c=C(0.0, 0.02, -0.114), sp=14, hp=4, w=(0.26, 0.04, 0.88), k=(0.8, -0.4, -0.4), p=-40.0, b=0.0,
               g=0.3, gi=0.2, gt=0.2, sh=0.0),
             K(f0 + 8, c=C(0, 0, 0.176), f=(0.0, 0.01, 0.15), fp=28, sp=-6, hp=-10,
               w=(0.40, -0.12, 1.45), k=(0.6, 0.5, -0.8), g=0.05, gi=0.0, gt=0.0, sh=8.0),
             K(f0 + 14, c=C(0, 0, 0.206), f=(0.0, 0.01, 0.19), fp=22),
             K(f0 + 21, c=C0, f=(0.0, 0.0, 0.0), fp=0, sp=4),
             K(f0 + 27, c=C(0.0, 0.01, -0.094), sp=12, hp=4, w=(0.36, -0.12, 0.95), sh=0.0)]
clip('jump_happy', 165, [S(0)] + _hop + [
    K(88, c=C0, sp=2, hp=-2, **GANBARE, hr=8), K(96, w=(0.13, -0.22, 1.12), **sway(-1, 0.5, hr=-6)),
    K(104, w=(0.13, -0.22, 1.06), **sway(1, 0.5, hr=8)), K(112, w=(0.13, -0.22, 1.12), hr=-4),
    K(130, **REST_ARMS, hr=2, c=C0, lr=0, sr=0), S(165)],
    'both', 'Two happy hops with her arms flung up, then little fists of joy, wiggling side to side.',
    face=fx('キリッ', 4, 20, 0.6, r=4) + fx('笑い', 14, 160, 1.0) + fx('ワ', 14, 88, 0.9) + fx('ω', 86, 140, 0.6))

# shy_cover: hands over the face, turns away, peeks through the fingers, hides again, turns back shyly
clip('shy_cover', 180, [
    S(0), K(6, hp=-4, sh=6.0),
    K(18, **FACE_COVER, hp=10, sh=10.0, sp=6, c=C(0.0, 0.01, -0.014)),
    K(34, sy=-26, ly=-10, hy=-18, hr=-6, turn=-6, tipL=10), K(70, sy=-28, hy=-20),
    K(84, wL=(0.16, -0.20, 1.15), pL=40.0, bL=0.0, hy=-8, hp=4), K(106, hy=-10),
    K(114, wL=(0.05, -0.18, 1.235), pL=75.0, bL=-35.0, hy=-22, hp=10),
    K(130, sy=0, ly=0, hy=0, hr=8, turn=0, tipL=0, **CHEST_HOLD, sh=6.0, hp=8, sp=4, c=C0),
    K(150, **REST_ARMS, hp=4, hr=6, sp=2), S(180)],
    'reaction', 'Embarrassed: hides her face in her hands, turns away, peeks through her fingers, hides again.',
    face=fx('照れ', 4, 176, 1.0) + fx('はぅ', 10, 170, 0.7) + fx('まばたき', 20, 76, 0.5) + fx('ω', 140, 174, 0.4))

# wave_hello: right hand up, a cheerful wave with the whole body, head tilt, the left hand at the chest
def _wave(f0, side, n, hi=(0.36, -0.10, 1.31), lo=(0.30, -0.12, 1.30), step=7):
    t = side
    keys = []
    for i in range(n):
        x = hi if i % 2 == 0 else lo
        keys.append(K(f0 + i * step, **{f'w{t}': (x[0] + (0.06 if i % 2 == 0 else -0.04), x[1], x[2]),
                                        f'b{t}': 18.0 if i % 2 == 0 else -18.0}))
    return keys


clip('wave_hello', 165, [
    S(0), K(8, sr=-2, c=C(0.008, 0, -0.004)),
    K(18, **WAVE_UP_R, hr=8, sr=4, lr=-2, tipR=12, wL=(0.07, -0.22, 1.04), pL=-75.0, bL=15.0)] + _wave(26, 'R', 8) + [
    K(84, wR=(0.34, -0.10, 1.30), bR=0.0, hr=10, tipR=0),
    K(96, **sway(-1, 0.6, hr=-4)), K(108, wR=(0.38, -0.11, 1.33), bR=16.0), K(115, wR=(0.31, -0.11, 1.31), bR=-16.0),
    K(122, wR=(0.36, -0.11, 1.32), bR=8.0),
    K(140, **REST_ARMS, hr=0, sr=0, lr=0, c=C0), S(165)],
    'reaction', 'Waves hello with her whole body, rising on her toe, the other hand at her chest.',
    look=True, face=fx('口角上げ', 2, 163, 0.25) + fx('笑い', 8, 160, 0.9) + fx('あ', 16, 66, 0.5) + fx('ワ', 100, 130, 0.5) + fx('照れ', 60, 140, 0.3))

# wave_bye: both arms waving overhead, rising onto the toes with each swing, a last small wave
_bye = []
for i in range(8):
    s = 1 if i % 2 == 0 else -1
    _bye.append(K(24 + i * 9, sr=5 * s, c=C(-0.012 * s), hr=6 * s,
                  wL=(0.20 + 0.10 * s, -0.08, 1.50), wR=(0.20 - 0.10 * s, -0.08, 1.50), bL=-12.0 * s, bR=12.0 * s))
clip('wave_bye', 180, [
    S(0), K(10, c=C(0, 0, -0.024), sp=5),
    K(20, w=(0.25, -0.08, 1.50), k=(1.0, 0.3, -0.4), p=-70.0, g=0.05, gi=0.0, gt=0.1, sh=10.0, tip=10, sp=-2,
      c=C0)] + _bye + [
    K(102, sr=0, hr=0, w=(0.28, -0.08, 1.48), b=0.0, c=C0),
    K(116, **rest_arm('L'), wR=(0.24, -0.20, 1.12), kR=(1.0, 0.2, -1.0), pR=-80.0, bR=10.0, tip=0, sh=0.0, hr=8),
    K(124, bR=-20.0), K(130, bR=20.0), K(136, bR=-10.0),
    K(150, **REST_ARMS, hr=4), S(180)],
    'reaction', 'Waves goodbye with both arms overhead on her toes, then a last small wave by her chest.',
    look=True, face=fx('口角上げ', 2, 178, 0.25) + fx('笑い', 10, 120, 1.0) + fx('口横広げ', 40, 100, 0.5) + fx('にこり', 110, 174, 0.8)
    + fx('困る', 116, 170, 0.3))

# welcome_back: a bounce, a jump with both arms up in a V, then hands together "okaeri!"
clip('welcome_back', 180, [
    S(0), K(6, c=C(0, 0, -0.054), sp=8, hp=6),
    K(14, c=C0, sp=0, hp=-4, w=(0.36, -0.10, 1.10), k=(0.4, 0.6, -1.0), g=0.1, gi=0.05, gt=0.1, tip=10),
    K(22, c=C(0.0, 0.01, -0.094), sp=10, hp=4, w=(0.30, 0.02, 0.88), tip=0, g=0.4),
    K(31, c=C(0, 0, 0.166), f=(0.0, 0.0, 0.14), fp=26, sp=-6, hp=-12,
      w=(0.44, -0.07, 1.50), k=(1.0, 0.3, -0.6), g=0.05, gi=0.0, gt=0.0, sh=10.0),
    K(37, c=C(0, 0, 0.186), f=(0.0, 0.0, 0.17), fp=20),
    K(44, c=C0, f=(0.0, 0.0, 0.0), fp=0, sp=4),
    K(50, c=C(0, 0, -0.074), sp=10, hp=2),
    K(62, c=C0, sp=2, w=(0.42, -0.10, 1.40), sh=6.0, hp=-2),
    K(80, **PRAY, sh=4.0, hr=10, hp=4, tipR=10), K(100, **sway(1, 0.6, hr=12)), K(116, **sway(-1, 0.5, hr=-6)),
    K(136, **REST_ARMS, hr=4, tipR=0, c=C0, lr=0, sr=0), S(180)],
    'reaction', 'Welcome back! A bounce and a jump with both arms up, then palms together with a happy sway.',
    look=True, face=fx('口角上げ', 2, 178, 0.25) + fx('笑い', 8, 176, 1.0) + fx('ワ', 24, 54, 0.8) + fx('照れ', 60, 150, 0.5) + fx('ω', 80, 140, 0.5))

# bow: an ojigi with the hands folded, comes up with a smile and a head tilt
clip('bow', 150, [
    S(0), K(10, **CLASP_FRONT, hp=-2),
    K(30, sp=32, lp=8, hp=12, c=C(0.0, 0.035, -0.006)), K(54, sp=34, hp=14),
    K(74, sp=4, lp=0, hp=0, c=C0),
    K(90, **sway(1, 0.5, hr=10)), K(106, **REST_ARMS), K(124, hr=0, c=C0, lr=0, sr=0), S(150)],
    'both', 'A polite bow with her hands folded, then comes up with a smile and a tilt of the head.',
    face=fx('口角上げ', 2, 148, 0.25) + fx('にこり', 2, 30, 0.5) + fx('まばたき', 24, 64, 1.0) + fx('にこり', 66, 146, 0.9) + fx('照れ', 74, 130, 0.4))

# curtsy: holds the skirt out, right foot behind, dips with a head tilt, a second little bob
clip('curtsy', 165, [
    S(0), K(10, **SKIRT_HOLD, hp=2),
    K(26, fR=(-0.10, 0.16, 0.03), tipR=22, c=C(0.0, 0.03, -0.024)),
    K(42, c=C(0.0, 0.04, -0.104), sp=12, hp=12, hr=-7, fyL=8),
    K(62, c=C(0.0, 0.04, -0.114), sp=13, hp=13), K(76, c=C(0.0, 0.03, -0.024), sp=4, hp=2, hr=0),
    K(88, c=C(0.0, 0.03, -0.06), hp=8, hr=6), K(98, c=C(0.0, 0.03, -0.024), hp=0, hr=4),
    K(112, fR=(0.0, 0.0, 0.0), tipR=0, fyL=3, c=C0, **REST_ARMS),
    K(132, hr=0), S(165)],
    'both', 'A graceful curtsy, skirt held out and one foot behind, then a second little bob.',
    face=fx('にこり', 4, 160, 0.8) + fx('まばたき', 38, 74, 0.8) + fx('照れ', 30, 120, 0.5))


# point_left / point_right: "look, over there!" points with one arm, the other hand on the hip, looks there
def _point(t):
    o = 'R' if t == 'L' else 'L'
    s = 1 if t == 'L' else -1
    return [
        S(0), K(8, sy=-4 * s, hp=4, c=C(0, 0, -0.012)),
        K(22, **{f'w{t}': (0.27, -0.36, 1.22), f'k{t}': (0.2, -0.2, -1.0), f'p{t}': 55.0, f'b{t}': -8.0,
                 f'g{t}': 1.0, f'gi{t}': 0.0, f'gt{t}': 0.75, f'sh{t}': 6.0, f'tip{o}': 12.0},
          **_side(HIPS, o), sy=14 * s, hy=32 * s, hp=-4, hr=4 * s, sr=3 * s, c=C(0.012 * s)),
        K(28, **{f'w{t}': (0.28, -0.38, 1.24)}),
        K(36, **{f'w{t}': (0.26, -0.36, 1.21)}), K(44, **{f'w{t}': (0.28, -0.38, 1.23)}),
        K(66, hy=6 * s, hp=0, hr=8 * s, **{f'tip{o}': 0.0}),
        K(78, **{f'w{t}': (0.26, -0.36, 1.22)}), K(86, **{f'w{t}': (0.28, -0.38, 1.23)}, hy=26 * s, hr=2 * s),
        K(104, hy=4 * s, hr=10 * s),
        K(118, **rest_arm(t), sy=0, hy=0, hr=6 * s, sr=0, c=C0),
        K(128, **rest_arm(o)), K(140, hr=0), S(150)]


_POINT_FACE = fx('口角上げ', 2, 148, 0.25) + fx('ワ', 10, 40, 0.5) + fx('キリッ', 14, 66, 0.7) + fx('にこり', 60, 146, 0.8) + fx('あ', 76, 98, 0.4)
clip('point_left', 150, _point('L'), 'reaction', 'Points to her left: "look, over there!", a hand on her hip, '
     'glances back at the viewer and points again.', face=_POINT_FACE)
clip('point_right', 150, _point('R'), 'reaction', 'Points to her right: "look, over there!", a hand on her hip, '
     'glances back at the viewer and points again.', face=_POINT_FACE)

# clap_cheer: claps with a bounce in the knees, a hop, and a last little clap by her cheek
_clap = []
for i in range(6):
    f = 14 + i * 10
    _clap.append(K(f, w=(0.03, -0.29, 1.04), c=C(0, 0, -0.024), hr=3 * (1 if i % 2 else -1)))
    _clap.append(K(f + 5, w=(0.15, -0.27, 1.04), c=C0))
clip('clap_cheer', 165, [S(0), K(8, **CLAP_OPEN, sp=4, hp=-4)] + _clap + [
    K(80, c=C(0, 0, -0.064), sp=8, hr=0), K(87, c=C(0, 0, 0.086), f=(0.0, 0.0, 0.07), fp=18, sp=-2, w=(0.30, -0.10, 1.25),
                                          k=(0.6, 0.5, -1.0), hp=-6),
    K(94, c=C(0, 0, -0.034), f=(0.0, 0.0, 0.0), fp=0, sp=4, hp=0),
    K(106, c=C0, sp=2, wL=(0.12, -0.20, 1.17), wR=(0.02, -0.21, 1.18), k=(1.0, -0.1, -1.0), p=-80.0, b=-20.0,
      hr=10, **{'tipL': 10}),
    K(112, wL=(0.08, -0.20, 1.18), wR=(0.06, -0.21, 1.18)), K(130, hr=12),
    K(144, **REST_ARMS, hr=0, tipL=0), S(165)],
    'reaction', 'Claps excitedly with bouncing knees, a little hop, and a last clap held by her cheek.',
    look=True, face=fx('笑い', 6, 160, 1.0) + fx('ワ', 12, 100, 0.8) + fx('ω', 104, 150, 0.6) + fx('照れ', 104, 156, 0.4))

# thumbs_up: right thumb up toward the viewer, a wink and a nod, a second thumbs up with a hop
clip('thumbs_up', 150, [
    S(0), K(8, sp=3, hp=-2),
    K(20, wR=(0.18, -0.36, 1.12), kR=(0.6, 0.4, -1.0), pR=-85.0, bR=-6.0, gR=1.0, giR=1.0, gtR=0.0, shR=4.0,
      sy=-8, hr=8, hy=-4, c=C(0.006), **_side(HIPS, 'L')),
    K(26, wR=(0.19, -0.38, 1.15)), K(34, hp=10), K(40, hp=-2), K(46, hp=6),
    K(60, hp=0, hr=4),
    K(72, c=C(0, 0, -0.05), sp=6, wR=(0.20, -0.30, 1.04)), K(80, c=C(0, 0, 0.03), f=(0.0, 0.0, 0.04), fp=14, sp=0,
                                                         wR=(0.24, -0.37, 1.16), hr=-6),
    K(86, c=C(0, 0, -0.02), f=(0.0, 0.0, 0.0), fp=0), K(96, c=C0),
    K(118, **REST_ARMS, sy=0, hr=0, hy=0, c=C0), S(150)],
    'reaction', 'A confident thumbs up with a wink and a nod, then another with a little hop.',
    look=True, face=fx('にこり', 2, 30, 0.3) + fx('ウィンク', 16, 64, 1.0) + fx('笑い', 12, 146, 0.8) + fx('口角上げ', 18, 120, 0.8)
    + fx('ウィンク', 76, 104, 1.0))

# heart: a finger heart at the chest, a lean, a toe pop and a wink, then a big heart with both arms
BIG_HEART = dict(w=(0.10, -0.06, 1.45), k=(1.0, 0.3, 0.2), p=-60.0, b=30.0, g=0.3, gi=0.3, gt=0.3, sh=8.0)
clip('heart', 180, [
    S(0), K(8, c=C(0, 0, -0.019), sp=4),
    K(24, **HEART, sr=-6, hr=9, tipL=20, fL=(0.0, -0.04, 0.0), c=C(0.012, 0.0, -0.004), sp=0),
    K(40, hr=11, sr=-7), K(56, hr=7), K(70, hr=10),
    K(84, sr=0, hr=0, tipL=0, fL=(0.0, 0.0, 0.0), c=C0, w=(0.40, -0.10, 1.25), k=(0.8, 0.5, -0.6), p=-10.0,
      b=0.0, g=0.15),
    K(100, **BIG_HEART, hr=-6, tipR=14), K(118, hr=6, tipR=0, tipL=14), K(130, hr=-2, tipL=0),
    K(150, **REST_ARMS, hr=0), S(180)],
    'reaction', 'A finger heart at her chest with a wink and a toe pop, then a big heart over her head.',
    look=True, face=fx('にこり', 6, 176, 1.0) + fx('照れ', 20, 150, 0.6) + fx('ウィンク', 28, 78, 1.0) + fx('ω', 24, 90, 0.6)
    + fx('笑い', 96, 140, 0.6))

# balance_wobble: the floor tips, arms fly out, she wobbles and steadies, wipes her brow
_wob = []
for i, (f, a) in enumerate(((14, 1.0), (25, -0.85), (37, 0.65), (50, -0.45), (64, 0.25))):
    _wob.append(K(f, sr=12 * a, lr=-7 * a, c=C(-0.035 * a, 0.0, -0.014), hr=-8 * a,
                  **{('tipR' if a > 0 else 'tipL'): 0, ('tipL' if a > 0 else 'tipR'): 18 * abs(a)},
                  wL=(0.52, -0.06, 1.10 + 0.06 * a), wR=(0.52, -0.06, 1.10 - 0.06 * a)))
clip('balance_wobble', 165, [S(0), K(6, **ARMS_OUT, c=C(0, 0, -0.034), sh=4.0)] + _wob + [
    K(78, sr=0, lr=0, hr=0, tipL=0, tipR=0, c=C(0, 0, -0.004), wL=(0.52, -0.06, 1.10), wR=(0.52, -0.06, 1.10)),
    K(94, **rest_arm('L'), wR=(0.10, -0.19, 1.31), kR=(1.0, -0.2, -0.6), pR=60.0, bR=-10.0, gR=0.1, giR=0.05, gtR=0.2,
      sh=0.0, c=C0, hp=-4, hr=6),
    K(102, wR=(0.04, -0.19, 1.32)), K(110, wR=(0.11, -0.19, 1.31)),
    K(130, **REST_ARMS, hp=0, hr=4), K(146, hr=0), S(165)],
    'both', 'Loses her balance, arms flung out, wobbles side to side, steadies and wipes her brow. Phew!',
    face=fx('びっくり', 4, 76, 0.8) + fx('ワ', 6, 70, 0.6) + fx('汗', 70, 150, 0.8) + fx('困る', 70, 120, 0.5)
    + fx('にこり', 100, 160, 0.7))

# dizzy: the head and torso circle, she stumbles a step each way, shakes it off, a little laugh
_diz = []
for i in range(10):
    a = 2 * math.pi * i / 5
    k = 1.0 - i / 12
    _diz.append(K(10 + i * 10, hr=12 * k * math.sin(a), hp=8 * k * math.cos(a), hy=10 * k * math.sin(a + 1),
                  sr=6 * k * math.sin(a - 0.6), sp=3 + 4 * k * math.cos(a - 0.6), c=C(0.03 * k * math.sin(a - 1.0), 0.0, -0.024)))
clip('dizzy', 210, [S(0), K(6, wR=(0.08, -0.18, 1.30), kR=(1.0, -0.2, -0.6), pR=60.0, bR=-10.0, gR=0.1, giR=0.05,
                               gtR=0.2, wL=(0.07, -0.22, 1.04), pL=-70.0, bL=15.0)] + _diz + [
    K(46, fL=(0.04, 0.0, 0.0)), K(64, fR=(0.05, 0.02, 0.0)), K(84, fL=(0.0, 0.0, 0.0)), K(100, fR=(0.0, 0.0, 0.0)),
    K(112, hy=-14, hr=0, hp=4, sr=0, sp=2, c=C0), K(118, hy=13), K(124, hy=-9), K(130, hy=4), K(136, hy=0),
    K(146, **CHEST_HOLD, hr=8, hp=6), K(164, **sway(1, 0.5, hr=10)), K(182, **REST_ARMS, hr=2, c=C0, lr=0, sr=0),
    S(210)],
    'reaction', 'Dizzy: her head goes round, she stumbles a step each way, shakes it off and laughs at herself.',
    face=fx('困る', 4, 150, 0.8) + fx('ハイライト消', 10, 124, 0.8) + fx('う', 20, 110, 0.5) + fx('にこり', 140, 204, 0.7)
    + fx('照れ', 146, 196, 0.5))

# mining_swing: an imaginary pickaxe over the right shoulder, three strikes, a look at the haul, a happy hop
RAISE_R = dict(wR=(0.22, 0.0, 1.40), kR=(1.0, 0.2, -0.6), pR=-30.0, bR=-25.0, gR=1.0, giR=1.0, gtR=0.8, shR=8.0,
               wL=(-0.12, -0.07, 1.36), kL=(0.8, -0.5, -0.6), pL=-30.0, bL=-15.0, gL=1.0, giL=1.0, gtL=0.8)
STRIKE_R = dict(wR=(0.06, -0.40, 0.93), kR=(0.7, 0.3, -0.6), pR=-40.0, bR=10.0, shR=0.0,
                wL=(-0.02, -0.34, 0.97), kL=(1.0, 0.2, -0.5), pL=-40.0, bL=5.0)
_mine = []
for i in range(3):
    f = 20 + i * 26
    _mine += [K(f, **RAISE_R, sp=-6, sy=-10, hp=4, c=C(0.0, 0.01), lr=0),
              K(f + 9, **STRIKE_R, sp=26, sy=-4, hp=14, c=C(0.0, -0.01, -0.054), lr=2),
              K(f + 14, sp=22, hp=12, c=C(0.0, -0.01, -0.044))]
clip('mining_swing', 180, [S(0), K(8, f=(0.06, 0.0, 0.0), fy=12, c=C(0, 0, -0.014), hp=10)] + _mine + [
    K(112, sp=8, hp=20, hy=-8, sy=0, wR=(0.30, -0.12, 0.90), kR=(1.0, 0.4, -0.5), wL=(0.30, -0.12, 0.90), kL=(1.0, 0.4, -0.5),
      pR=-10.0, pL=-10.0, bR=0.0, bL=0.0, g=0.3, gi=0.2, gt=0.2, shR=0.0, c=C(0, 0, -0.004)),
    K(126, sp=2, hp=-2, hy=0, f=(0.0, 0.0, 0.0), fy=3.0, c=C0, **CUP, hr=8),
    K(140, hr=-6, tip=10), K(150, tip=0, hr=6),
    K(162, **REST_ARMS, hr=0, hp=0), S(180)],
    'ambient', 'Swings an imaginary pickaxe three times, then admires the haul in her cupped hands.',
    face=fx('口角上げ', 2, 178, 0.25) + fx('キリッ', 8, 104, 0.8) + fx('う', 26, 100, 0.3) + fx('笑い', 100, 176, 1.0) + fx('ワ', 120, 150, 0.6))

# idol_dance: 10 s at 120 bpm (15 frames a beat): step-touches, a point, claps, a turn, a heart
B = 15
_dance = [S(0)]
for i in range(4):                                    # bars 1-2: step-touch side to side, arms swing
    s = 1 if i % 2 == 0 else -1
    f = B * (1 + 2 * i)
    _dance += [K(f, c=C(0.05 * s, 0.0, -0.034), lr=-5 * s, sr=4 * s, hr=7 * s,
                 **{('fL' if s > 0 else 'fR'): (0.10, 0.0, 0.0), ('fR' if s > 0 else 'fL'): (-0.06, 0.0, 0.0)},
                 **{('tipR' if s > 0 else 'tipL'): 18, ('tipL' if s > 0 else 'tipR'): 0},
                 wL=(0.30, -0.20, 1.05 + 0.1 * s), wR=(0.30, -0.20, 1.05 - 0.1 * s), k=(1.0, 0.4, -0.6),
                 p=-40.0, b=0.0, g=0.4, gi=0.3, gt=0.3),
               K(f + B, c=C(0.03 * s, 0.0, -0.004))]
f = B * 9                                             # bar 3: point up-front, hand on hip
_dance += [K(f, fL=(0.0, 0.0, 0.0), fR=(0.0, 0.0, 0.0), tipL=0, tipR=0, c=C(0, 0, -0.014), lr=0, sr=-4, hr=-6, sy=-10,
             wR=(0.42, -0.33, 1.30), kR=(0.3, 0.3, -1.0), pR=50.0, gR=1.0, giR=0.0, gtR=0.75, shR=8.0,
             **_side(HIPS, 'L'), hy=-14, hp=-6),
           K(f + B, wR=(0.30, -0.36, 1.36), c=C(0, 0, -0.044)), K(f + 2 * B, wR=(0.42, -0.33, 1.30), c=C(0, 0, -0.014)),
           K(f + 3 * B, c=C(0, 0, -0.044))]
f = B * 13                                            # bar 4: three claps on the beat with knee bounces
for i in range(3):
    _dance += [K(f + i * B, w=(0.03, -0.29, 1.07), k=(1.0, 0.1, -0.6), p=-15.0, b=-10.0, g=0.05, gi=0.0, gt=0.1,
                 sh=0.0, c=C(0, 0, -0.054), sr=0, sy=0, hy=0, hr=0, hp=4),
               K(f + i * B + 7, w=(0.17, -0.25, 1.09), c=C(0, 0, -0.004), hp=-2)]
f = 238                                               # turn with the arms out, end in the heart
_dance += [K(f, turn=0, **TWIRL_ARMS, c=C(0, 0, -0.014), tip=0),
           K(f + 7, turn=90, tip=12), K(f + 13, turn=200, tip=14), K(f + 19, turn=300, tip=10),
           K(f + 24, turn=360, tip=0, c=C(0, 0, -0.024)),
           K(270, turn=360, **HEART, sr=-6, hr=9, tipL=20, fL=(0.0, -0.04, 0.0), c=C(0.012, 0.0, -0.004)),
           K(278, turn=360, hr=11),
           K(286, turn=360, sr=0, hr=4, tipL=0, fL=(0.0, 0.0, 0.0), c=C0, **REST_ARMS),
           K(300, reset=True, turn=360)]
clip('idol_dance', 300, _dance, 'both', 'A 10 s idol dance at 120 bpm: step-touches, a point, three claps, '
     'a spin and a finger heart.', look=False,
     face=fx('笑い', 6, 136, 1.0) + fx('ウィンク', 134, 186, 1.0) + fx('にこり', 130, 200, 0.8) + fx('笑い', 194, 296, 1.0)
     + fx('ワ', 14, 130, 0.6) + fx('ワ', 196, 262, 0.7) + fx('ω', 266, 296, 0.8) + fx('照れ', 266, 298, 0.6))

# ------------------------------------------------------------------ new clips

# peace_wink: a V by her eye with a wink and a toe pop, then a double peace under the chin
V_LOW = dict(w=(0.16, -0.25, 1.10), k=(1.0, 0.1, -1.0), p=-90.0, b=-10.0, g=1.0, gm=0.0, gi=0.0, gt=0.9, sh=4.0)
clip('peace_wink', 165, [
    S(0), K(8, c=C(0, 0, -0.02), hr=-4),
    K(20, **_side(V_EYE, 'R'), wL=(0.08, -0.22, 1.02), pL=-70.0, bL=10.0, sr=-5, hr=10, tipL=16, fL=(0.0, -0.03, 0.0),
      c=C(-0.01)),
    K(34, hr=12, c=C(-0.01, 0, -0.012)), K(46, hr=9, c=C(-0.01)), K(58, hr=12),
    K(72, **V_LOW, sr=0, hr=-8, tipL=0, fL=(0.0, 0.0, 0.0), tipR=14, fR=(0.0, -0.03, 0.0), c=C(0.01)),
    K(86, hr=-10, c=C(0.01, 0, -0.012)), K(100, hr=6, **{'tipR': 0, 'fR': (0.0, 0.0, 0.0)}, c=C0),
    K(112, w=(0.18, -0.25, 1.12)), K(120, w=(0.15, -0.25, 1.10)),
    K(138, **REST_ARMS, hr=0), S(165)],
    'reaction', 'A peace sign by her eye with a wink and a toe pop, then a double peace under her chin.',
    look=True, face=fx('口角上げ', 2, 163, 0.25) + fx('ウィンク', 18, 64, 1.0) + fx('笑い', 8, 160, 0.9) + fx('ω', 20, 64, 0.5) + fx('ワ', 70, 120, 0.6)
    + fx('照れ', 60, 140, 0.4))

# blow_kiss: fingers to the lips, eyes closed, throws a kiss with a leg pop, then hides her cheeks
clip('blow_kiss', 165, [
    S(0), K(10, hr=6, hp=-2),
    K(24, **KISS_R, hr=10, hp=4, sp=4, **_side(CHEST_HOLD, 'L')),
    K(38, hp=6), K(46, wR=(0.22, -0.42, 1.22), kR=(0.6, 0.3, -1.0), pR=-110.0, bR=-30.0, gR=0.0, giR=0.0, gtR=0.1,
                    shR=6.0, sp=6, hp=-4, hr=6, fL=(0.0, 0.12, 0.12), fpL=30, c=C(-0.025)),
    K(60, wR=(0.24, -0.43, 1.25)), K(74, fL=(0.0, 0.0, 0.0), fpL=0, c=C0, sp=2),
    K(88, **CHEEKS, hr=12, hp=6, sh=4.0), K(102, sy=8, hr=14), K(116, sy=-6, hr=8), K(126, sy=0),
    K(140, **REST_ARMS, hr=4, hp=0), S(165)],
    'reaction', 'Touches her fingers to her lips, blows the viewer a kiss with a leg pop, then holds her blushing cheeks.',
    look=True, face=fx('まばたき', 20, 44, 1.0) + fx('う', 20, 50, 0.8) + fx('ウィンク', 44, 80, 1.0) + fx('にこり', 4, 160, 0.7)
    + fx('照れ', 40, 150, 0.9) + fx('はぅ', 86, 130, 0.5))

# cat_paws: "nyan~": paws at the chin, beckoning one paw then the other, one paw up high
_nyan = []
for i in range(6):
    t, o = ('L', 'R') if i % 2 == 0 else ('R', 'L')
    s = 1 if t == 'L' else -1
    _nyan.append(K(30 + i * 11, **{f'w{t}': (0.13, -0.23, 1.22), f'b{t}': 75.0, f'w{o}': (0.11, -0.22, 1.15),
                                   f'b{o}': 45.0}, hr=8 * s, **{'c': C(0.012 * s), 'lr': -2.0 * s}))
clip('cat_paws', 180, [
    S(0), K(10, c=C(0, 0, -0.024), hp=4),
    K(22, **PAWS, hr=10, c=C0)] + _nyan + [
    K(100, **_side(dict(w=(0.17, -0.17, 1.32), k=(1.0, -0.1, -0.9), p=-60.0, b=60.0, g=0.8, gi=0.75, gt=0.4, sh=6.0), 'R'),
      wL=(0.11, -0.22, 1.15), bL=50.0, hr=-12, tipL=18, fL=(0.0, -0.03, 0.0), c=C(-0.01), lr=0),
    K(116, bR=80.0, hr=-14), K(124, bR=55.0), K(132, bR=80.0),
    K(152, **REST_ARMS, hr=0, tipL=0, fL=(0.0, 0.0, 0.0), c=C0), S(180)],
    'both', 'Cat paws at her chin, "nyan~": beckons with one paw then the other, then one paw raised by her face.',
    look=True, face=fx('ω', 16, 170, 1.0) + fx('にこり', 6, 176, 0.8) + fx('ウィンク', 100, 140, 1.0) + fx('照れ', 40, 150, 0.4))

# bunny_ears: V fingers on her head as ears, flops them, two little bunny hops
_bh = []
for f0 in (62, 82):
    _bh += [K(f0, c=C(0, 0, -0.05), sp=6), K(f0 + 6, c=C(0, 0, 0.05), f=(0.0, 0.0, 0.05), fp=18, sp=0),
            K(f0 + 12, c=C(0, 0, -0.04), f=(0.0, 0.0, 0.0), fp=0, sp=5)]
clip('bunny_ears', 165, [
    S(0), K(10, c=C(0, 0, -0.02), hp=4),
    K(24, **BUNNY, hr=8, c=C0, hp=-2),
    K(36, gm=0.6, gi=0.6, hr=12), K(44, gm=0.0, gi=0.0, hr=6), K(50, gmL=0.6, giL=0.6, hr=-6), K(56, gmL=0.0, giL=0.0)] + _bh + [
    K(104, c=C0, sp=2, hr=10, gmR=0.6, giR=0.6), K(112, gmR=0.0, giR=0.0, hr=-4),
    K(138, **REST_ARMS, hr=2), S(165)],
    'both', 'Makes bunny ears with her fingers, flops them, and does two little bunny hops.',
    look=True, face=fx('笑い', 6, 160, 0.9) + fx('ω', 20, 60, 0.6) + fx('ワ', 60, 100, 0.7) + fx('ウィンク', 102, 124, 1.0, r=4))

# skirt_spin: holds her skirt out and spins twice on her toes, settles with a sway
SKIRT_OUT = dict(w=(0.26, -0.16, 0.85), k=(1.0, 0.3, -0.4), p=-30.0, b=10.0, g=0.65, gi=0.55, gt=0.6, sh=3.0)
_spin = [K(30 + i * 11, turn=120 * (i + 1), tip=14, hr=6 * (1 if i % 2 else -1)) for i in range(6)]
clip('skirt_spin', 180, [
    S(0), K(10, **SKIRT_OUT), K(20, turn=-15, c=C(0, 0, -0.024), sy=-6, hy=-6)] + _spin + [
    K(100, turn=720, tip=0, c=C(0, 0, -0.03), hr=8, sy=0, hy=0),
    K(116, turn=720, **sway(1, 0.7)), K(132, turn=720, **sway(-1, 0.7)),
    K(150, turn=720, **REST_ARMS, c=C0, lr=0, sr=0, hr=0), K(180, reset=True, turn=720)],
    'ambient', 'Holds her skirt out and spins twice round on her toes, then sways to a stop.',
    face=fx('口角上げ', 2, 178, 0.25) + fx('笑い', 8, 120, 1.0) + fx('ワ', 30, 96, 0.5) + fx('にこり', 100, 176, 0.8) + fx('照れ', 100, 160, 0.4))

# ballet_pirouette: first position, relevé with the arms in fifth, an arabesque, a pirouette, a révérence
FIRST = dict(w=(0.12, -0.28, 0.98), k=(1.0, 0.2, -0.6), p=-80.0, b=0.0, g=0.2, gi=0.1, gt=0.2, sh=0.0)
FIFTH = dict(w=(0.12, -0.13, 1.50), k=(1.0, 0.2, 0.3), p=-80.0, b=0.0, g=0.2, gi=0.1, gt=0.2, sh=6.0)
clip('ballet_pirouette', 240, [
    S(0), K(14, **FIRST, fy=20, hp=-4),
    K(28, **FIFTH, tip=24, c=C(0, 0, 0.01), hp=-8),
    K(44, tip=0, tipL=24, fR=(0.0, 0.40, 0.28), fpR=40, fyR=20, c=C(0.03, 0.02, -0.02), sp=18, lp=6, hp=-12,
      wL=(0.20, -0.38, 1.30), kL=(0.6, 0.3, -1.0), pL=-80.0, wR=(0.46, -0.05, 1.12), kR=(0.2, 0.6, -1.0), pR=0.0),
    K(64, fR=(0.0, 0.42, 0.30), hp=-14), K(80, fR=(0.0, 0.0, 0.0), fpR=0, sp=2, lp=0, hp=-4, c=C(0, 0, -0.02),
                                         tipL=0, **FIRST),
    K(94, c=C(0, 0, -0.06), sp=4),
    K(104, turn=20, tipL=30, fR=(-0.07, 0.0, 0.30), fyR=40, c=C(0.02, 0, 0.0), hp=-6),
    K(116, turn=150, tipL=30), K(128, turn=290, tipL=30), K(136, turn=360, tipL=24),
    K(146, turn=360, tipL=0, fR=(0.0, 0.0, 0.0), fyR=20, c=C(0, 0, -0.05), **FIFTH),
    K(164, turn=360, c=C0, w=(0.46, -0.08, 1.12), k=(0.2, 0.6, -1.0), p=0.0, sh=2.0, hp=0),
    K(182, turn=360, fR=(-0.06, 0.12, 0.0), tipR=20, c=C(0.0, 0.03, -0.09), sp=14, hp=12, hr=-6,
      w=(0.40, -0.16, 0.92), k=(1.0, 0.4, -0.6), p=-40.0),
    K(198, turn=360, c=C(0.0, 0.03, -0.095), sp=15),
    K(214, turn=360, fR=(0.0, 0.0, 0.0), tipR=0, fy=3.0, c=C0, sp=2, hp=0, hr=0, **REST_ARMS),
    K(240, reset=True, turn=360)],
    'ambient', 'Ballet: arms through first and fifth on relevé, an arabesque, a pirouette, and a révérence.',
    face=fx('真面目', 6, 40, 0.4) + fx('なごみ', 30, 100, 0.7) + fx('にこり', 90, 236, 0.8) + fx('まばたき', 180, 206, 0.7)
    + fx('照れ', 170, 230, 0.4))

# smell_flower: spots a flower, bends to pick it, smells it with her eyes closed, offers it to the viewer
clip('smell_flower', 210, [
    S(0), K(10, hy=20, hp=24, sp=6),
    K(26, sp=30, lp=6, c=C(0.0, 0.03, -0.10), hp=10, hy=10, wL=(0.16, -0.32, 0.90), kL=(1.0, 0.3, -0.5), pL=-60.0,
      gL=0.2, giL=0.1, gtL=0.2, f=(0.0, 0.0, 0.0), fR=(0.0, 0.06, 0.0), tipR=14),
    K(38, gL=0.8, giL=0.85, gtL=0.85),
    K(54, sp=2, lp=0, c=C0, hy=0, tipR=0, fR=(0.0, 0.0, 0.0), **CUP, hp=8),
    K(66, w=(0.04, -0.18, 1.20), hp=10, hr=6), K(84, **sway(1, 0.5, hr=10)), K(102, **sway(-1, 0.4, hr=4)),
    K(122, wR=(0.22, -0.36, 1.16), kR=(0.6, 0.3, -1.0), pR=-85.0, bR=0.0, gR=0.8, giR=0.75, gtR=0.7,
      **_side(CHEST_HOLD, 'L'), hp=0, hr=10, c=C0, lr=0, sr=0, tipL=12),
    K(144, hr=12, wR=(0.23, -0.38, 1.18)), K(160, tipL=0),
    K(182, **REST_ARMS, hr=0), S(210)],
    'ambient', 'Notices a flower, bends to pick it, smells it with her eyes closed and offers it to the viewer.',
    face=fx('瞳小', 4, 28, 0.4) + fx('にこり', 20, 60, 0.6) + fx('まばたき', 60, 112, 1.0) + fx('なごみ', 58, 120, 0.8)
    + fx('笑い', 114, 204, 0.9) + fx('照れ', 120, 190, 0.5))

# hair_twirl: twirls a lock round her finger, looking off, then catches the viewer looking
_tw = []
for i in range(12):
    a = 2 * math.pi * i / 4
    _tw.append(K(22 + i * 7, wR=(0.155 + 0.012 * math.cos(a), -0.10 - 0.015 * math.sin(a), 1.19 + 0.012 * math.sin(a)),
                 pR=-60.0 + 15.0 * math.cos(a)))
clip('hair_twirl', 210, [
    S(0), K(12, **HAIR_R, hr=-8, hy=-14, **_side(dict(w=(0.08, -0.22, 1.02), p=-70.0, b=10.0), 'L'), **{'tipR': 10}),
    ] + _tw + [
    K(110, hy=0, hr=-4, hp=4), K(118, hp=8, hr=6),
    K(136, **rest_arm('R'), **_side(BEHIND, 'L'), tipR=0, **sway(1, 0.6)),
    K(160, **BEHIND, **sway(-1, 0.6)),
    K(186, **REST_ARMS, c=C0, lr=0, sr=0, hr=0), S(210)],
    'ambient', 'Twirls a lock of hair round her finger while gazing off, then notices the viewer and smiles shyly.',
    look=False, face=fx('なごみ', 6, 112, 0.6) + fx('ω', 20, 104, 0.4) + fx('びっくり', 106, 124, 0.4, r=4)
    + fx('照れ', 110, 196, 0.8) + fx('にこり', 116, 204, 0.8))

# daydream: cheeks in her hands, foot kicked up behind and swinging, a dreamy sigh
clip('daydream', 270, [
    S(0), K(14, sp=6, hp=-2),
    K(30, **CHEEKS, hr=12, fL=(0.0, 0.12, 0.14), fpL=40, c=C(-0.02), lr=2, sp=8),
    K(52, fpL=20, fL=(0.0, 0.10, 0.10)), K(72, fpL=45, fL=(0.0, 0.12, 0.15), hr=14), K(92, fpL=22, hr=8),
    K(112, hr=-10, fL=(0.0, 0.0, 0.0), fpL=0, c=C(0.02), lr=-2, fR=(0.0, 0.12, 0.14), fpR=40),
    K(134, fpR=20, fR=(0.0, 0.10, 0.10)), K(156, fpR=45, fR=(0.0, 0.12, 0.15), hr=-12), K(176, fpR=25),
    K(196, fR=(0.0, 0.0, 0.0), fpR=0, c=C0, lr=0, **CHEST_HOLD, hp=-8, hr=4, sp=2),
    K(220, hp=-4), K(244, **REST_ARMS, hp=0, hr=0), S(270)],
    'ambient', 'Daydreams with her cheeks in her hands, one foot kicked up and swinging behind her, then a dreamy sigh.',
    face=fx('なごみ', 6, 264, 0.8) + fx('ω', 24, 190, 0.6) + fx('照れ', 30, 230, 0.6) + fx('にこり', 190, 264, 0.5))

# finger_twiddle: shy つんつん, index fingers tapping together, toes turned in, peeks up
_tsun = []
for i in range(10):
    _tsun.append(K(28 + i * 8, w=(0.03 + (0.022 if i % 2 else 0.0), -0.21, 1.04), hr=6 + 3 * (i % 2)))
clip('finger_twiddle', 180, [
    S(0), K(10, hp=12, hr=4),
    K(20, **TSUN, hp=14, sh=6.0, tipR=10, fyR=-14, sy=-4)] + _tsun + [
    K(70, hy=-14, hp=6), K(84, hy=0, hp=14), K(116, hp=2, hr=10, sy=4),
    K(130, hp=6), K(152, **REST_ARMS, hp=0, hr=0, tipR=0, fyR=3, sy=0), S(180)],
    'reaction', 'Shyly taps her index fingers together, toes turned in, peeking up at the viewer.',
    face=fx('照れ', 4, 176, 1.0) + fx('はぅ', 10, 120, 0.6) + fx('う', 20, 110, 0.3) + fx('にこり', 110, 170, 0.6))

# hands_behind_sway: hands behind her back, rocks and sways, then leans in toward the viewer "ne?"
_hb = []
for i, f in enumerate(range(24, 100, 19)):
    s = 1 if i % 2 == 0 else -1
    _hb.append(K(f, **sway(s, 0.9), **{('tipR' if s > 0 else 'tipL'): 14, ('tipL' if s > 0 else 'tipR'): 0}, hy=4 * s))
clip('hands_behind_sway', 240, [S(0), K(14, **BEHIND, sh=3.0)] + _hb + [
    K(114, c=C(0.0, -0.03, -0.006), sp=14, hp=-10, hr=12, hy=0, lr=0, sr=0, tip=14),
    K(140, hr=14, sp=15), K(156, hr=-8, sp=4, tip=0, c=C0),
    K(176, **sway(-1, 0.8), tipL=12), K(196, **sway(1, 0.6), tipL=0),
    K(216, **REST_ARMS, c=C0, lr=0, sr=0, hr=0, sh=0.0), S(240)],
    'ambient', 'Hands behind her back, sways from foot to foot, then leans in toward the viewer with a tilt: "ne?"',
    look=True, face=fx('にこり', 4, 236, 0.7) + fx('ω', 20, 110, 0.5) + fx('ワ', 112, 156, 0.4) + fx('照れ', 110, 200, 0.4))

# make_a_wish: palms together, eyes closed, a wish; opens her hands to the sky
clip('make_a_wish', 210, [
    S(0), K(12, hp=-10),
    K(28, **PRAY, hp=14, sp=6, sh=4.0, c=C(0, 0, -0.012)),
    K(60, hp=16, hr=4), K(90, hp=14, hr=-3), K(118, hp=15, hr=2),
    K(132, hp=-12, sp=0, c=C0),
    K(148, w=(0.30, -0.22, 1.32), k=(0.6, 0.3, -1.0), p=-120.0, b=-20.0, g=0.1, gi=0.05, gt=0.15, sh=8.0, tip=14),
    K(170, w=(0.34, -0.18, 1.36), hp=-6, hr=8, tip=6),
    K(188, **REST_ARMS, hp=0, hr=0, tip=0, sh=0.0), S(210)],
    'ambient', 'Puts her palms together and makes a wish with her eyes closed, then opens her hands to the sky.',
    face=fx('にこり', 2, 30, 0.5) + fx('まばたき', 24, 130, 1.0) + fx('なごみ', 24, 130, 0.6) + fx('笑い', 128, 204, 0.9)
    + fx('ワ', 140, 180, 0.5))

# self_hug: hugs herself happily, wiggling side to side on her toes
_hug = []
for i in range(6):
    s = 1 if i % 2 == 0 else -1
    _hug.append(K(36 + i * 14, sy=8 * s, ly=4 * s, hr=10 * s, **{('tipL' if s > 0 else 'tipR'): 14,
                                                               ('tipR' if s > 0 else 'tipL'): 0}))
clip('self_hug', 180, [S(0), K(10, sh=8.0, hp=4), K(24, **SELF_HUG, sh=8.0, hp=8, sp=4)] + _hug + [
    K(126, sy=0, ly=0, hr=6, tip=0, hp=4), K(146, **REST_ARMS, hr=0, hp=0), S(180)],
    'both', 'Hugs herself happily, wiggling side to side on her toes.',
    face=fx('笑い', 6, 174, 0.9) + fx('まばたき', 20, 130, 0.8) + fx('照れ', 20, 160, 0.7) + fx('ω', 30, 130, 0.6))

# wake_up: dozing off and jerking awake, rubs her eyes, a big stretch and yawn, pats her cheeks, "yosh!"
RUB = dict(w=(0.06, -0.16, 1.27), k=(1.0, -0.3, -1.0), p=-20.0, b=30.0, g=0.8, gi=0.6, gt=0.6)
clip('wake_up', 300, [
    S(0), K(14, hp=20, sp=6), K(40, hp=28, c=C(0, 0, -0.016), sp=8, hr=6),
    K(50, hp=-4, sp=0, c=C0, hr=0), K(70, hp=24, sp=6, hr=-5),
    K(82, hp=4, sp=2, hr=0, **RUB), K(90, wL=(0.07, -0.16, 1.285), wR=(0.05, -0.16, 1.26)),
    K(98, wL=(0.05, -0.16, 1.26), wR=(0.07, -0.16, 1.285)), K(106, wL=(0.07, -0.16, 1.285), wR=(0.05, -0.16, 1.26)),
    K(126, w=(0.04, -0.10, 1.54), k=(1.0, 0.1, 0.25), p=-80.0, b=-25.0, g=0.55, gi=0.55, gt=0.3, sh=9.0, sp=-6,
      hp=-14, tip=14),
    K(158, hp=-16, tip=16), K(176, w=(0.42, -0.10, 1.18), k=(0.2, 0.6, -1.0), p=0.0, b=0.0, g=0.15, sh=2.0,
                                hp=2, tip=0, sp=2),
    K(190, hy=-12), K(196, hy=12), K(202, hy=-6), K(208, hy=0),
    K(220, **CHEEKS, hp=0), K(226, w=(0.08, -0.17, 1.19)), K(232, w=(0.07, -0.17, 1.19)),
    K(246, **GANBARE, c=C(0, 0, -0.03), hp=4), K(254, w=(0.13, -0.22, 1.12), c=C0, hp=-2),
    K(274, **REST_ARMS, hp=0), S(300)],
    'ambient', 'Dozes off and jerks awake, rubs her eyes, stretches with a big yawn, pats her cheeks: "yosh!"',
    face=fx('口角上げ', 2, 298, 0.25) + fx('まばたき', 8, 80, 1.0) + fx('なごみ', 8, 80, 0.5) + fx('困る', 76, 124, 0.5) + fx('じと目', 80, 124, 0.6)
    + fx('あ', 128, 170, 0.9) + fx('まばたき', 128, 172, 1.0) + fx('涙', 160, 220, 0.4) + fx('びっくり', 216, 236, 0.4, r=4)
    + fx('キリッ', 236, 270, 0.7) + fx('笑い', 240, 296, 0.8))

# peek_afar: hand at her brow, peering far off on tiptoe, spots something and waves at it
clip('peek_afar', 195, [
    S(0), K(12, tip=10),
    K(24, **BROW_R, **_side(HIPS, 'L'), sp=6, hy=24, sy=6, hp=-4, tip=14),
    K(44, tip=20, hy=28), K(62, hy=-22, sy=-6), K(82, hy=-26), K(96, hy=0, sy=0, hp=-8, tip=24, c=C(0, 0, 0.005)),
    K(110, hp=-10), K(118, tip=0, c=C(0, 0, -0.03)),
    K(126, tip=10, c=C0, **WAVE_UP_R, **rest_arm('L'), hr=6)] + _wave(132, 'R', 5) + [
    K(170, **REST_ARMS, tip=0, hr=0, hp=0), S(195)],
    'ambient', 'Shades her eyes with a hand and peers far off on tiptoe, spots something and waves at it.',
    face=fx('口角上げ', 2, 193, 0.25) + fx('真面目', 6, 100, 0.5) + fx('う', 20, 96, 0.4) + fx('びっくり', 104, 124, 0.7, r=4) + fx('笑い', 116, 190, 0.9)
    + fx('あ', 120, 160, 0.4))

# ganbare: little fists up "ganbare!", pumping, one fist high with a hop, a wink
clip('ganbare', 165, [
    S(0), K(10, c=C(0, 0, -0.03), hp=4),
    K(20, **GANBARE, c=C0, hp=-2), K(28, w=(0.13, -0.22, 1.14), c=C(0, 0, -0.024), hp=6),
    K(36, w=(0.13, -0.22, 1.05), c=C0, hp=-2), K(44, w=(0.13, -0.22, 1.14), c=C(0, 0, -0.024), hp=6),
    K(52, w=(0.13, -0.22, 1.08), c=C0, hp=0),
    K(64, c=C(0, 0, -0.05), sp=6), K(72, wR=(0.25, -0.18, 1.50), kR=(1.0, 0.2, -0.8), pR=-80.0, shR=10.0,
                                     c=C(0, 0, 0.05), f=(0.0, 0.0, 0.05), fp=16, sp=-2, hp=-8),
    K(80, c=C(0, 0, -0.03), f=(0.0, 0.0, 0.0), fp=0), K(92, c=C0, sp=2),
    K(104, **GANBARE, hp=4, hr=10), K(124, hr=8),
    K(140, **REST_ARMS, hr=0, hp=0), S(165)],
    'reaction', 'Cheers the viewer on: little fists up, "ganbare!", one fist high with a hop, then a wink.',
    look=True, face=fx('キリッ', 6, 100, 0.8) + fx('ワ', 16, 60, 0.7) + fx('あ', 66, 90, 0.7) + fx('ウィンク', 102, 132, 1.0)
    + fx('笑い', 96, 160, 0.9))

# catch_butterfly: follows a butterfly with her eyes, catches it in her hands, peeks in, it flutters away
clip('catch_butterfly', 240, [
    S(0), K(12, hy=-26, hp=-16),
    K(30, hy=8, hp=-20, sy=4, tip=8), K(44, hy=20, hp=-14, sy=6),
    K(56, w=(0.12, -0.26, 1.38), k=(1.0, 0.0, -0.8), p=-90.0, b=0.0, g=0.3, gi=0.25, gt=0.3, sh=8.0, hy=0, sy=0,
      hp=-18, tip=22, c=C(0, 0, 0.01)),
    K(66, w=(0.03, -0.27, 1.36), g=0.5, gi=0.45, b=15.0, c=C(0, 0, 0.02)),
    K(76, tip=0, c=C(0, 0, -0.03)),
    K(92, **CUP, hp=16, sh=2.0, c=C0), K(110, w=(0.07, -0.21, 1.18), g=0.2, gi=0.15, hp=18),
    K(124, hp=-18, hy=24, w=(0.14, -0.24, 1.22), g=0.1, gi=0.05, b=0.0),
    K(140, hy=30, hp=-24, **WAVE_UP_R, **_side(CHEST_HOLD, 'L')), K(150, bR=18.0), K(158, bR=-18.0), K(166, bR=14.0),
    K(186, hy=0, hp=0, **CHEST_HOLD, hr=8), K(212, **REST_ARMS, hr=0), S(240)],
    'ambient', 'Watches a butterfly flit about, catches it in her hands on tiptoe, peeks in, and waves as it flies off.',
    face=fx('口角上げ', 2, 238, 0.25) + fx('瞳小', 4, 60, 0.4) + fx('ワ', 10, 56, 0.4) + fx('キリッ', 50, 80, 0.6) + fx('にこり', 80, 110, 0.7)
    + fx('びっくり', 108, 134, 0.7, r=4) + fx('笑い', 130, 234, 0.9) + fx('あ', 140, 170, 0.4))

# ehehe: scratches her cheek with a finger, embarrassed giggle, tongue out
clip('ehehe', 165, [
    S(0), K(10, hp=6, hr=8),
    K(22, **SCRATCH_R, **_side(BEHIND, 'L'), hr=12, tipR=10),
    K(28, wR=(0.08, -0.16, 1.215)), K(34, wR=(0.08, -0.16, 1.195)), K(40, wR=(0.08, -0.16, 1.215)),
    K(46, wR=(0.08, -0.16, 1.195)), K(52, wR=(0.08, -0.16, 1.215)), K(58, wR=(0.08, -0.16, 1.20)),
    K(74, **sway(-1, 0.6, hr=6), hp=0), K(90, **sway(1, 0.6, hr=14)),
    K(106, **rest_arm('R'), hp=2, tipR=0), K(136, **REST_ARMS, c=C0, lr=0, sr=0, hr=0), S(165)],
    'reaction', 'Scratches her cheek with one finger, "ehehe~", an embarrassed giggle with her tongue out.',
    face=fx('照れ', 4, 160, 0.9) + fx('笑い', 16, 100, 0.8) + fx('困る', 20, 80, 0.4) + fx('ぺろっ', 84, 124, 0.9)
    + fx('ウィンク', 84, 124, 1.0) + fx('にこり', 116, 160, 0.6))

# idol_poses: a run of cute poses, one each beat of a slow count
CHEEK_POKE = dict(w=(0.08, -0.15, 1.19), k=(1.0, -0.2, -1.0), p=-30.0, b=10.0, g=0.9, gi=0.0, gt=0.6, sh=4.0)
POINT_YOU_R = dict(wR=(0.25, -0.40, 1.18), kR=(0.6, 0.3, -1.0), pR=55.0, bR=-8.0, gR=1.0, giR=0.0, gtR=0.75, shR=6.0)
clip('idol_poses', 300, [
    S(0), K(10, c=C(0, 0, -0.024)),
    K(22, **_side(V_EYE, 'R'), **_side(HIPS, 'L'), sr=-5, hr=10, tipL=18, fL=(0.0, -0.03, 0.0), c=C(-0.01)),
    K(46, hr=12),
    K(62, **BIG_HEART, sr=0, hr=-8, tipL=0, fL=(0.0, 0.0, 0.0), tipR=16, c=C(0.01)), K(84, hr=-10),
    K(102, **CHEEK_POKE, tipR=0, hr=10, c=C0, sp=6, hp=4), K(122, hr=12),
    K(140, **PAWS, hr=-10, sp=2, hp=0, tipL=16, fL=(0.0, -0.03, 0.0)), K(156, bL=75.0, hr=-12), K(164, bL=50.0),
    K(180, **POINT_YOU_R, **_side(HIPS, 'L'), tipL=0, fL=(0.0, 0.0, 0.0), sy=-8, hr=8), K(198, hr=10),
    K(218, **OPEN_UP, sy=0, hr=0, tip=16, c=C(0, 0, 0.01), hp=-6), K(236, hr=6),
    K(254, **KISS_R, **_side(CHEST_HOLD, 'L'), tip=0, c=C0, hp=4, hr=8),
    K(264, wR=(0.22, -0.42, 1.22), kR=(0.6, 0.3, -1.0), pR=-110.0, bR=-30.0, gR=0.0, giR=0.0, gtR=0.1, hp=-2),
    K(282, **REST_ARMS, hr=0, hp=0), S(300)],
    'both', 'A run of cute idol poses: a V by the eye, a big heart, cheek pokes, cat paws, pointing at you, arms up, a kiss.',
    look=True, face=fx('ウィンク', 18, 56, 1.0) + fx('笑い', 6, 296, 0.8) + fx('ω', 60, 130, 0.6) + fx('照れ', 96, 170, 0.6)
    + fx('ウィンク', 176, 210, 1.0) + fx('ワ', 214, 246, 0.7) + fx('う', 250, 262, 0.6, r=4) + fx('ウィンク', 260, 286, 1.0))

# long_dance: 28 s at 120 bpm (15 frames a beat): a sway intro, step-touch claps, skirt side steps and a
# twirl, cat-paw hops, a point and a heart, arms waving overhead with a spin, and an ending pose
B = 15
_ld = [S(0)]
for i in range(4):                                       # intro: hands behind, sway on the beat
    s = 1 if i % 2 == 0 else -1
    _ld.append(K(B * (i + 1), **BEHIND, **sway(s, 1.2), hy=5 * s, **{('tipR' if s > 0 else 'tipL'): 14,
                                                                      ('tipL' if s > 0 else 'tipR'): 0}))
f = B * 5
for i in range(6):                                       # step-touch with a clap on each touch
    s = 1 if i % 2 == 0 else -1
    _ld += [K(f, c=C(0.05 * s, 0.0, -0.034), lr=-5 * s, sr=4 * s, hr=7 * s, hy=0,
              **{('fL' if s > 0 else 'fR'): (0.10, 0.0, 0.0), ('fR' if s > 0 else 'fL'): (-0.06, 0.0, 0.0)},
              **{('tipR' if s > 0 else 'tipL'): 18, ('tipL' if s > 0 else 'tipR'): 0},
              w=(0.20, -0.25, 1.06), k=(1.0, 0.1, -0.6), p=-15.0, b=-10.0, g=0.05, gi=0.0, gt=0.1, sh=0.0),
            K(f + 8, w=(0.035, -0.29, 1.08 + 0.04 * s), c=C(0.03 * s, 0.0, -0.01))]
    f += 2 * B
for i in range(4):                                       # skirt held out, side steps, head tilts
    s = 1 if i % 2 == 0 else -1
    _ld += [K(f, **SKIRT_OUT, c=C(0.045 * s, 0.0, -0.03), lr=-5 * s, sr=5 * s, hr=10 * s, tip=0,
              **{('fL' if s > 0 else 'fR'): (0.08, 0.0, 0.0), ('fR' if s > 0 else 'fL'): (0.0, 0.0, 0.0)},
              **{('tipR' if s > 0 else 'tipL'): 20}),
            K(f + B, c=C(0.02 * s, 0.0, -0.006))]
    f += 2 * B
_ld += [K(f, fL=(0.0, 0.0, 0.0), fR=(0.0, 0.0, 0.0), tip=0, lr=0, sr=0, hr=0, c=C(0, 0, -0.02), turn=0,
          **TWIRL_ARMS),                                 # a twirl
        K(f + 8, turn=110, tip=14, c=C0), K(f + 16, turn=240, tip=14), K(f + 24, turn=360, tip=0, c=C(0, 0, -0.03))]
f += 2 * B + 4
for i in range(4):                                       # cat-paw hops side to side
    s = 1 if i % 2 == 0 else -1
    _ld += [K(f, turn=360, **PAWS, c=C(0.03 * s, 0.0, -0.05), hr=10 * s, sp=6, f=(0.0, 0.0, 0.0), fp=0),
            K(f + 7, turn=360, c=C(0.03 * s, 0.0, 0.04), f=(0.0, 0.0, 0.04), fp=16, sp=0, **{f'b{"L" if s > 0 else "R"}': 80.0}),
            K(f + 15, turn=360, c=C(0.02 * s, 0.0, -0.04), f=(0.0, 0.0, 0.0), fp=0, b=55.0)]
    f += 2 * B
_ld += [K(f, turn=360, c=C(0, 0, -0.014), hr=-6, sy=-10, hp=-6, **POINT_YOU_R, **_side(HIPS, 'L'), sp=2),   # point
        K(f + B, turn=360, c=C(0, 0, -0.044), wR=(0.30, -0.36, 1.30)), K(f + 2 * B, turn=360, c=C(0, 0, -0.014),
                                                                         wR=(0.25, -0.40, 1.18)),
        K(f + 3 * B, turn=360, **HEART, sy=0, hy=0, hp=0, sr=-6, hr=9, tipL=20, fL=(0.0, -0.04, 0.0), c=C(0.012)),
        K(f + 5 * B, turn=360, hr=11)]
f += 6 * B
for i in range(8):                                       # arms waving overhead side to side
    s = 1 if i % 2 == 0 else -1
    _ld.append(K(f + i * 10, turn=360, tipL=0, fL=(0.0, 0.0, 0.0), sr=5 * s, c=C(-0.015 * s), hr=6 * s, hp=-4,
                 wL=(0.20 + 0.10 * s, -0.08, 1.50), wR=(0.20 - 0.10 * s, -0.08, 1.50), k=(1.0, 0.3, -0.4),
                 p=-70.0, b=-12.0 * s, g=0.05, gi=0.0, gt=0.1, sh=10.0, tip=8))
f += 80
_ld += [K(f, turn=360, **TWIRL_ARMS, sh=0.0, sr=0, hr=0, hp=0, tip=0, c=C(0, 0, -0.02)),
        K(f + 8, turn=470, tip=14, c=C0), K(f + 16, turn=600, tip=14), K(f + 24, turn=720, tip=0, c=C(0, 0, -0.03))]
f += 36
_ld += [K(f, turn=720, **_side(V_EYE, 'R'), **_side(HIPS, 'L'), sr=-5, hr=10, tipL=18, fL=(0.0, -0.03, 0.0),
          c=C(-0.01)),                                   # ending: a V by the eye, a curtsy
        K(f + 30, turn=720, **SKIRT_HOLD, sr=0, hr=0, tipL=0, fL=(0.0, 0.0, 0.0), c=C0, sh=0.0),
        K(f + 44, turn=720, fR=(-0.10, 0.16, 0.03), tipR=22, c=C(0.0, 0.04, -0.10), sp=12, hp=12, hr=-7),
        K(f + 64, turn=720, fR=(0.0, 0.0, 0.0), tipR=0, c=C0, sp=2, hp=0, hr=0),
        K(f + 80, turn=720, **REST_ARMS)]
LONG_N = f + 104
_ld.append(K(LONG_N, reset=True, turn=720))
clip('long_dance', LONG_N, _ld, 'both', 'A 28 s dance at 120 bpm: a sway intro, step-touch claps, skirt side steps, '
     'a twirl, cat-paw hops, a point and a heart, arms waving overhead, a spin, and a curtsy.',
     face=fx('にこり', 4, 80, 0.7) + fx('ω', 6, 76, 0.6) + fx('笑い', 74, LONG_N - 4, 0.9) + fx('ワ', 76, 250, 0.6)
     + fx('照れ', 250, 380, 0.5) + fx('ω', 380, 500, 0.7) + fx('ウィンク', 500, 560, 1.0) + fx('ワ', 560, 700, 0.6)
     + fx('ウィンク', 700, LONG_N - 30, 1.0))

# ------------------------------------------------------------------ locomotion
# loops stay in place (the runtime moves the root by `stride` m per cycle, forward = her facing);
# root_end is where the root must be at the end of a clip that leaves her somewhere else (MMD axes,
# m: [x her left, up, z], -z toward the viewer / her front)

clip('walk', WALK_N, [S(0), S(WALK_N)], 'locomotion', 'A light girlish walk in place, one cycle (two steps); '
     'frame 0 = right foot planted under her, left foot passing.', look=True, loop=True, loop_fn=_walk,
     stride=WALK_STRIDE, face=[(0, 'にこり', 0.5), (WALK_N, 'にこり', 0.5), (0, '口角上げ', 0.3), (WALK_N, '口角上げ', 0.3)])
clip('run', RUN_N, [S(0), S(RUN_N)], 'locomotion', 'A girlish run in place, one cycle (two steps), forearms pumping.',
     look=True, loop=True, loop_fn=_run, stride=RUN_STRIDE,
     face=[(0, 'キリッ', 0.4), (RUN_N, 'キリッ', 0.4), (0, 'ワ', 0.4), (RUN_N, 'ワ', 0.4)])
clip('skip', SKIP_N, [S(0), S(SKIP_N)], 'locomotion', 'A happy skip in place (step-hop on each foot), arms swinging high.',
     look=True, loop=True, loop_fn=_skip, stride=SKIP_STRIDE,
     face=[(0, '笑い', 0.9), (SKIP_N, '笑い', 0.9), (0, 'ワ', 0.5), (SKIP_N, 'ワ', 0.5)])
clip('tiptoe', TIPTOE_N, [S(0), S(TIPTOE_N)], 'locomotion', 'Sneaking on tiptoe in place, paws up, peering left and right.',
     loop=True, loop_fn=_tiptoe, stride=TIPTOE_STRIDE,
     face=[(0, 'う', 0.5), (TIPTOE_N, 'う', 0.5), (0, '真面目', 0.4), (TIPTOE_N, '真面目', 0.4), (0, '瞳小', 0.2),
           (TIPTOE_N, '瞳小', 0.2)])
clip('walk_start', 16, [S(0), S(16)], 'locomotion', 'From the stance into the walk: ends on walk frame 0 (the root '
     'should start moving over these frames).', look=True, loop_fn=_blend_fn(16, lambda f: STANCE, lambda f: _walk(0)),
     face=fx('にこり', 0, 16, 0.5, r=4), ends_in='walk')
clip('walk_stop', 16, [S(0), S(16)], 'locomotion', 'From walk frame 0 back to the stance (the root should come to rest '
     'over these frames).', look=True, loop_fn=_blend_fn(16, lambda f: _walk(0), lambda f: STANCE),
     face=fx('にこり', 0, 16, 0.5, r=4), starts_in='walk')

# climb_up: a block 0.5 m high whose front face is 0.35 m ahead: hands on top, a knee up, push up, stand
CLIMB = (0.0, -0.45, 0.5)
clip('climb_up', 126, [
    S(0), K(10, hp=22, sp=8, c=C(0, 0, -0.02)),
    K(24, sp=45, lp=4, c=C(0.0, -0.10, -0.16), hp=-6, w=(0.15, -0.48, 0.92), k=(1.0, 0.3, -0.4), p=-80.0, b=-30.0,
      g=0.2, gi=0.15, gt=0.3, sh=6.0),
    K(32, fR=(0.0, -0.08, 0.34), fpR=10, c=C(0.0, -0.12, -0.14)),
    K(40, fR=(0.0, -0.45, 0.5), fpR=0, c=C(0.0, -0.16, -0.10), tipL=20),
    K(50, c=C(0.0, -0.26, 0.02), sp=36, tipL=40, hp=-10),
    K(58, c=C(0.0, -0.34, 0.16), fL=(0.0, -0.12, 0.28), tipL=0, fpL=30, sp=28, w=(0.22, -0.30, 0.92)),
    K(64, fL=(0.0, -0.30, 0.62), fpL=10),
    K(72, fL=(0.0, -0.45, 0.5), fpL=0, c=C(0.0, -0.42, 0.32), sp=20, w=(0.30, -0.20, 0.92), k=(1.0, 0.5, -0.5),
      p=-40.0, b=0.0),
    K(90, c=C(0.0, -0.45, 0.5), sp=2, lp=0, hp=0, **GANBARE),
    K(98, c=C(0.0, -0.45, 0.47), hp=6), K(106, c=C(0.0, -0.45, 0.5), hp=-2),
    K(116, **REST_ARMS, hp=0),
    K(126, reset=True, c=C(*CLIMB), f=CLIMB)],
    'locomotion', 'Climbs onto a block 0.5 m high whose front is 0.35 m ahead: hands on top, a knee up, pushes up and '
    'stands on it with a little "yatta". The root moves by root_end.', root_end=CLIMB,
    face=fx('口角上げ', 2, 124, 0.25) + fx('真面目', 4, 60, 0.6) + fx('う', 20, 70, 0.6) + fx('キリッ', 50, 80, 0.5) + fx('笑い', 80, 122, 0.9))

# jump_down: standing on a 0.5 m ledge, hops down forward and lands soft
DROP = (0.0, -0.40, -0.5)
clip('jump_down', 110, [
    S(0), K(10, hp=26, sp=8),
    K(22, c=C(0.0, 0.02, -0.12), sp=20, hp=10, w=(0.22, 0.06, 0.90), k=(1.0, 0.6, -0.2), p=-40.0, b=0.0, g=0.3, gi=0.2,
      gt=0.2, sh=0.0, f=(0.0, 0.0, 0.0)),
    K(30, c=C(0.0, -0.06, 0.03), tip=30, sp=-2, hp=0, w=(0.34, -0.25, 1.30), k=(0.6, 0.5, -1.0), p=-60.0, g=0.1, gi=0.05,
      gt=0.1, sh=8.0),
    K(34, c=C(0.0, -0.16, 0.05), f=(0.0, -0.14, 0.08), fp=20, tip=0),
    K(38, c=C(0.0, -0.28, -0.20), f=(0.0, -0.30, -0.30), fp=10),
    K(42, c=C(0.0, -0.39, -0.56), f=(0.0, -0.40, -0.5), fp=0, sp=14),
    K(48, c=C(0.0, -0.38, -0.70), sp=24, hp=12, w=(0.36, -0.30, 1.05), k=(0.8, 0.4, -0.8), sh=2.0),
    K(62, c=C(0.0, -0.40, -0.58), sp=10, hp=4),
    K(74, c=C(0.0, -0.40, -0.5), sp=2, hp=-2, w=(0.42, -0.14, 1.15), k=(0.4, 0.6, -1.0), p=-30.0, sh=4.0, tipL=14),
    K(88, **REST_ARMS, hp=0, tipL=0),
    K(110, reset=True, c=C(*DROP), f=DROP)],
    'locomotion', 'Standing on a 0.5 m ledge, hops down forward, lands soft in a crouch and pops up with a "ta-da". '
    'The root moves by root_end.', root_end=DROP,
    face=fx('瞳小', 4, 26, 0.4) + fx('キリッ', 18, 40, 0.6) + fx('ワ', 30, 56, 0.8) + fx('びっくり', 40, 58, 0.4, r=4)
    + fx('笑い', 56, 106, 0.9))

# hide_crouch: crouches small as if hiding behind something; frames 44-106 can loop
_HIDE = dict(c=C(0.0, 0.05, -0.34), sp=34, lp=4, hp=14, w=(0.18, -0.38, 0.97), k=(1.0, 0.35, -0.3), p=-20.0, b=-5.0,
             g=0.5, gi=0.45, gt=0.4, sh=8.0, f=(0.03, 0.0, 0.0), fy=10.0)
clip('hide_crouch', 150, [
    S(0), K(8, hy=30, hp=-4), K(16, hy=-30), K(24, hy=0, c=C(0, 0.02, -0.12), sp=14),
    K(38, **_HIDE), K(44, **_HIDE, hr=0, sr=0),
    K(56, hr=3, sr=1.5), K(66, hr=-2, sr=-1.0, hy=-6), K(76, hr=2, sr=1.0, hy=4), K(88, hr=-3, sr=-1.5, hy=0),
    K(98, hr=1, sr=0.5), K(106, **_HIDE, hr=0, sr=0, hy=0),
    K(122, c=C(0, 0.03, -0.17), sp=20, hp=4, w=(0.20, -0.26, 0.88), k=(1.0, 0.4, -0.4), sh=0.0),
    K(136, c=C0, sp=2, hp=0, f=(0.0, 0.0, 0.0), fy=3.0, **REST_ARMS), S(150)],
    'locomotion', 'Crouches down small, hugging her knees as if hiding behind something, trembling a little; '
    'frames hold[0]..hold[1] loop seamlessly while she stays hidden.', hold=[44, 106],
    face=fx('瞳小', 2, 30, 0.6) + fx('困る', 10, 146, 0.7) + fx('う', 30, 120, 0.5) + fx('汗', 40, 120, 0.6))


# peek_left / peek_right: from a crouch, leans out sideways to peek, ducks back, stands
def _peek(t):
    s = 1 if t == 'L' else -1
    return [
        S(0), K(12, c=C(0, 0.04, -0.24), sp=24, hp=6, w=(0.20, -0.30, 0.92), k=(1.0, 0.4, -0.4), p=-30.0,
                 f=(0.03, 0.0, 0.0), fy=10.0),
        K(26, c=C(0, 0.04, -0.26), hp=8),
        K(40, c=C(0.10 * s, 0.03, -0.22), lr=-6 * s, sr=16 * s, sp=14, hy=24 * s, hr=12 * s, hp=0,
          **{f'w{t}': (0.32, -0.30, 1.02), f'k{t}': (0.6, 0.3, -1.0), f'p{t}': -80.0, f'b{t}': -20.0, f'g{t}': 0.3,
             f'gi{t}': 0.2}),
        K(56, hy=14 * s, hr=16 * s), K(70, hy=28 * s, hr=10 * s),
        K(80, c=C(0, 0.04, -0.27), lr=0, sr=0, sp=26, hy=0, hr=0, hp=10, w=(0.20, -0.30, 0.92), k=(1.0, 0.4, -0.4),
          p=-30.0, b=0.0, g=0.5, gi=0.45),
        K(94, hp=8), K(112, c=C0, sp=2, hp=0, f=(0.0, 0.0, 0.0), fy=3.0, **REST_ARMS), S(135)]


_PEEK_FACE = (fx('う', 4, 40, 0.5) + fx('瞳小', 30, 82, 0.5) + fx('びっくり', 46, 84, 0.5) + fx('汗', 74, 126, 0.6)
              + fx('困る', 76, 130, 0.5))
clip('peek_left', 135, _peek('L'), 'locomotion', 'Crouches, leans out to her left to peek around something, '
     'ducks back and stands up.', face=_PEEK_FACE)
clip('peek_right', 135, _peek('R'), 'locomotion', 'Crouches, leans out to her right to peek around something, '
     'ducks back and stands up.', face=_PEEK_FACE)

# fall_land: frame 0 is in the air just before touchdown (legs tucked, arms up); lands in a squat, wobbles,
# stands and dusts off her skirt
clip('fall_land', 96, [
    K(0, c=C0, f=(0.0, 0.04, 0.14), fp=20, w=(0.42, -0.06, 1.38), k=(0.4, 0.5, -1.0), p=-60.0, b=0.0, g=0.1, gi=0.05,
      gt=0.1, sh=10.0, hp=-10, sp=-4),
    K(4, f=(0.0, 0.0, 0.0), fp=0, c=C(0, 0, -0.08), sp=6),
    K(10, c=C(0.0, 0.03, -0.30), sp=30, hp=-6, w=(0.30, -0.36, 0.90), k=(1.0, 0.4, -0.5), p=-40.0, sh=4.0),
    K(20, sr=6, c=C(0.02, 0.03, -0.29)), K(28, sr=-4, c=C(-0.012, 0.03, -0.29)),
    K(40, sr=0, c=C(0.0, 0.02, -0.16), sp=14, w=(0.20, -0.30, 0.90), sh=0.0),
    K(52, c=C0, sp=4, hp=6, w=(0.17, -0.20, 0.87), k=(1.0, 0.4, -0.6), p=-70.0, b=20.0, g=0.2, gi=0.1),
    K(58, w=(0.18, -0.20, 0.85)), K(64, w=(0.17, -0.20, 0.87)), K(70, w=(0.18, -0.20, 0.85)),
    K(80, **REST_ARMS, hp=0, hr=8), S(96)],
    'locomotion', 'Lands from a fall (frame 0 is just before touchdown, legs tucked, arms up): a deep squat, a wobble, '
    'stands up and dusts off her skirt.',
    face=[(0, 'びっくり', 0.9), (6, 'びっくり', 0.9), (12, 'びっくり', 0)] + [(0, 'ワ', 0.7), (8, 'ワ', 0.7), (14, 'ワ', 0)]
    + fx('困る', 6, 70, 0.8) + fx('涙', 10, 50, 0.3) + fx('にこり', 60, 92, 0.6))

# look_up_reach: on tiptoe reaching up for something just out of reach, a little hop, then a pout
REACH_R = dict(wR=(0.12, -0.12, 1.56), kR=(1.0, 0.2, 0.2), pR=-80.0, bR=-10.0, gR=0.05, giR=0.0, gtR=0.1, shR=12.0)
clip('look_up_reach', 120, [
    S(0), K(10, hp=-20),
    K(22, **REACH_R, **_side(CHEST_HOLD, 'L'), tip=24, sr=-4, hp=-24),
    K(34, tip=30, c=C(0, 0, 0.02), gR=0.2), K(42, tip=12, c=C0, gR=0.05),
    K(50, tip=32, c=C(0, 0, 0.025)), K(56, tip=10, c=C(0, 0, -0.03)),
    K(62, c=C(0, 0, 0.06), f=(0.0, 0.0, 0.05), fp=14, tip=0), K(70, c=C(0, 0, -0.03), f=(0.0, 0.0, 0.0), fp=0),
    K(76, wR=(0.14, -0.30, 1.12), kR=(0.6, -0.1, -1.0), pR=-60.0, gR=0.3, giR=0.2, shR=4.0, hp=-4),
    K(84, **REST_ARMS, c=C0, sr=0, hp=0, hr=8), K(100, hr=0), S(120)],
    'locomotion', 'Reaches up on tiptoe for something just out of reach, stretches, tries a little hop, then pouts.',
    face=fx('う', 4, 60, 0.6) + fx('真面目', 10, 60, 0.5) + fx('キリッ', 56, 74, 0.5, r=4) + fx('困る', 72, 116, 0.6)
    + fx('▲', 76, 112, 0.6))


WEB_CLIPS = list(CLIPS)
assert not _FACE_ERRORS, chr(10).join(_FACE_ERRORS)


# ------------------------------------------------------------------ registration

def _key_fn(c, frame):
    def key(arm):
        apply(arm, c.at(frame))
    return key


# web clips whose names are also test clips of motion_poses (walk, run, idol_dance) are registered,
# keyed and exported as web_<name>; the site gets them under their own names (rename the .vmd)
_RENAMED = set()


def _register():
    for name, c in CLIPS.items():
        if name in mp.CLIPS and not mp.CLIPS[name] is None:
            _RENAMED.add(name)
        frames = list(range(0, c.frames, KEY_STEP)) + [c.frames]
        mp.CLIPS[vmd_name(name)] = (c.frames, [(f, _key_fn(c, f)) for f in frames])


def vmd_name(name):
    return ('web_' + name) if name in _RENAMED else name


_register()


def manifest():
    """The web runtime's clips.json (names as the site uses them)."""
    return {'fps': FPS,
            'notes': {'stride': 'm the root travels per loop cycle (the clip stays in place)',
                      'root_end': 'm the root has moved by the end of the clip, MMD axes [x (her left), y (up), z]; '
                                  '-z is toward the viewer / her front',
                      'hold': 'frames [a, b] that loop seamlessly while she holds the pose',
                      'kind': 'ambient: on her own; reaction: answers the visitor; both; locomotion: moving about'},
            'clips': {n: MANIFEST[n] for n in WEB_CLIPS}}


if __name__ == '__main__':
    import json
    import sys
    out = sys.argv[sys.argv.index('--') + 1] if '--' in sys.argv else 'clips.json'
    with open(out, 'w', encoding='utf-8') as fh:
        json.dump(manifest(), fh, ensure_ascii=False, indent=1)
    print('wrote', out, len(WEB_CLIPS), 'clips; export names:', ','.join(vmd_name(n) for n in WEB_CLIPS))
