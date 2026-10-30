"""LeviChan's web motion clips (levimc.org): an idle loop and 30 short actions, 30 fps.

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

# the arms at rest: hanging beside the skirt, palms turned in to it, fingers relaxed (a straight-out
# A-pose with flat palms read as stiff)
REST_W, REST_K = (0.24, -0.12, 0.85), (1.0, 0.5, -0.4)
REST_P, REST_B, REST_G, REST_GI, REST_GT = -35.0, 5.0, 0.4, 0.3, 0.3

STANCE = {
    'c': (0.0, 0.0, -0.006), 'turn': 0.0,                      # centre offset (m), body yaw (deg)
    'lp': 0.0, 'lr': 0.0, 'ly': 0.0,                           # pelvis (下半身) pitch / roll / yaw
    'sp': 2.0, 'sy': 0.0, 'sr': 0.0,                           # upper body pitch / yaw / roll
    'hp': 0.0, 'hy': 0.0, 'hr': 0.0,                           # head pitch / yaw / roll
}
for _t in 'LR':
    STANCE.update({
        f'w{_t}': REST_W,                   # wrist position, rest world (left side), m
        f'k{_t}': REST_K,                   # where the elbow points
        f'p{_t}': REST_P,                   # forearm twist (+ palm down / back)
        f'b{_t}': REST_B,                   # wrist flexed toward the palm
        f'sh{_t}': 0.0,                     # clavicle raised
        f'g{_t}': REST_G, f'gi{_t}': REST_GI, f'gt{_t}': REST_GT,   # finger curl: middle-little, index, thumb
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
                f'g{_t}': 3.6, f'gi{_t}': 3.4, f'gt{_t}': 3.8,
                f'f{_t}': 0.0, f'fp{_t}': 0.0, f'fy{_t}': 0.0, f'tip{_t}': 0.0})

SHOULDER = Vector((0.116, -0.043, 1.143))     # 腕.L at rest: the centre wrists move about

SIDED = ('w', 'k', 'p', 'b', 'sh', 'g', 'gi', 'gt', 'f', 'fp', 'fy', 'tip')


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

    def __init__(self, frames, keys, loop_fn=None):
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
            full.append((frames, dict(STANCE)))
        last = full[-1][1]
        # the body may end a whole number of turns round
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


def finger_curl(arm, t, rest, index, thumb):
    """Curl the fingers of .t: middle / ring / little by `rest`, the index by `index`, the thumb
    by `thumb` (0..1 of rig_pose.FIST)."""
    for pb in arm.pose.bones:
        if not (pb.name.endswith('.' + t) and pb.bone.collections and pb.bone.collections[0].name == 'Fingers'):
            continue
        stem = pb.name.split('.')[0]
        deg = rig_pose.FIST.get(stem) or rig_pose.FIST.get(stem[-1], 0)
        k = thumb if stem.startswith('親指') else index if stem.startswith('人指') else rest
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
        finger_curl(arm, t, P[f'g{t}'], P[f'gi{t}'], P[f'gt{t}'])


# ------------------------------------------------------------------ poses used by several clips
# wrist positions (left side, rest world m); shoulder 腕.L at (0.116, -0.043, 1.143), arm ~0.43 m

HIPS = dict(w=(0.17, -0.02, 1.00), k=(1.0, 0.5, -0.6), p=30.0, b=-10.0, g=1.0, gi=1.0, gt=0.7)     # fists on the hips
CHEST_HOLD = dict(w=(0.06, -0.22, 1.08), k=(1.0, 0.2, -0.8), p=-75.0, b=15.0, g=0.6, gi=0.55, gt=0.35)   # hands together at the chest
FACE_COVER = dict(w=(0.05, -0.18, 1.235), k=(0.45, -0.2, -1.0), p=75.0, b=-35.0, g=0.08, gi=0.05, gt=0.15)
CLASP_FRONT = dict(w=(0.05, -0.245, 0.925), k=(1.0, 0.25, -0.3), p=-45.0, b=10.0, g=0.45, gi=0.4, gt=0.3)
ARMS_OUT = dict(w=(0.52, -0.06, 1.10), k=(0.2, 0.6, -1.0), p=10.0, g=0.15, gi=0.1, gt=0.1)
FIST = dict(g=1.0, gi=1.0, gt=0.7)


def _side(d, t):
    """A both-sides pose dict for one side only."""
    return {k + t: v for k, v in d.items()}


# ------------------------------------------------------------------ the clips

def _idle(frame):
    """Breathing (4 s) with a slow weight shift; frame 0 / 120 = STANCE."""
    P = dict(STANCE)
    ph = 2 * math.pi * frame / 120.0
    br = math.sin(ph * 2)                 # two breaths per loop
    sw = math.sin(ph)                     # one slow sway
    P['c'] = (0.006 * sw, 0.0, -0.006 + 0.003 * (1 - math.cos(ph * 2)) * -0.5)
    P['lr'] = -1.2 * sw
    P['sr'] = 1.0 * sw
    P['sp'] = 2.0 - 0.8 * br
    P['hr'] = 1.5 * math.sin(ph - 0.6)
    P['hp'] = 0.8 * math.sin(ph * 2 - 0.9)
    for t in 'LR':
        s = 1 if t == 'L' else -1
        P[f'sh{t}'] = 1.2 * max(0.0, br) + 0.6 * br
        w = Vector(STANCE[f'w{t}'])
        P[f'w{t}'] = (w.x + 0.004 * br, w.y - 0.004 * math.sin(ph * 2 - 0.5), w.z + 0.004 * br + 0.004 * s * sw)
    return P


def _wave(f0, side, n, hi=(0.36, -0.10, 1.31), lo=(0.30, -0.12, 1.30)):
    t = side
    keys = []
    for i in range(n):
        x = hi if i % 2 == 0 else lo
        keys.append(K(f0 + i * 7, **{f'w{t}': (x[0] + (0.06 if i % 2 == 0 else -0.04), x[1], x[2]),
                                     f'b{t}': 18.0 if i % 2 == 0 else -18.0}))
    return keys


CLIPS = {}
MANIFEST = {}


def clip(name, frames, keys, look=False, face=(), loop=False, loop_fn=None):
    CLIPS[name] = Clip(frames, keys, loop_fn)
    face = sorted(face, key=lambda k: (k[1], k[0]))     # per morph, in time
    MANIFEST[name] = {'frames': frames, 'loop': loop, 'look': look, 'face': [list(f) for f in face]}


clip('idle', 120, [S(0), S(120)], look=True, loop=True, loop_fn=_idle)

# 1 look_around: curious glances, the torso following the head
clip('look_around', 150, [
    S(0), K(10, hp=5, sp=4),
    K(26, hy=48, hp=-4, sy=12, ly=4, c=(0.01, 0.0, -0.006), hr=6), K(48, hy=52, hp=-6, hr=8),
    K(60, hy=0, hp=2, sy=0, ly=0, c=(0.0, 0.0, -0.006), hr=0),
    K(76, hy=-46, hp=-2, sy=-11, ly=-4, hr=-7, c=(-0.01, 0.0, -0.006)), K(96, hy=-50, hr=-9),
    K(110, hy=8, hp=-20, sy=0, ly=0, sp=-2, hr=3, c=(0.0, 0.0, -0.006), tip=6),
    K(126, hp=-16, tip=0), S(150)],
    look=False, face=[(0, '瞳小', 0), (26, '瞳小', 0.3), (60, '瞳小', 0), (110, '口角上げ', 0.0), (118, '口角上げ', 0.6), (140, '口角上げ', 0),
          (26, 'う', 0), (34, 'う', 0.35), (56, 'う', 0), (76, 'はぅ', 0), (84, 'はぅ', 0.4), (100, 'はぅ', 0)])

# 2 stretch: fingers laced overhead, up on the toes, a lean each way, arms circle down
STRETCH_UP = dict(w=(0.04, -0.10, 1.54), k=(1.0, 0.1, 0.25), p=-80.0, b=-25.0, g=0.55, gi=0.55, gt=0.3, sh=9.0)
clip('stretch', 180, [
    S(0), K(10, sp=8, hp=6, c=(0.0, 0.0, -0.03), w=(0.2, -0.18, 0.95), k=(1.0, 0.2, -0.5), p=-40.0),
    K(28, **STRETCH_UP, sp=-6, hp=-14, c=(0.0, 0.0, 0.0), tip=12),
    K(50, sp=-9, hp=-16, tip=14), K(70, sr=12, lr=-6, hr=6, sp=-4, tip=4, c=(-0.015, 0.0, -0.006)),
    K(92, sr=-12, lr=6, hr=-6, c=(0.015, 0.0, -0.006)), K(110, sr=0, lr=0, hr=0, sp=-4, c=(0.0, 0.0, -0.006), tip=0),
    K(126, w=(0.46, -0.05, 1.28), k=(0.2, 0.7, -1.0), p=10.0, b=0.0, g=0.15, gi=0.1, gt=0.1, sh=3.0, hp=2, sp=2),
    K(142, w=(0.40, -0.06, 0.93), k=(0.8, 0.6, -0.6)), S(166), S(180)],
    face=[(18, 'まばたき', 0), (26, 'まばたき', 1.0), (60, 'まばたき', 1.0), (68, 'まばたき', 0),
          (22, 'お', 0), (30, 'お', 0.6), (55, 'お', 0.6), (66, 'お', 0), (120, 'なごみ', 0), (130, 'なごみ', 0.7), (170, 'なごみ', 0),
          (130, 'ω', 0), (138, 'ω', 0.5), (166, 'ω', 0)])

# 3 yawn: right hand covers the mouth, head back, shoulders up, the left arm stretches up
clip('yawn', 120, [
    S(0), K(8, hp=4, sp=4),
    K(24, hp=-16, sp=-5, shL=8, shR=10, wR=(0.012, -0.165, 1.19), kR=(0.6, -0.3, -1.0), pR=60.0, bR=-25.0,
      gR=0.12, giR=0.1, gtR=0.25, wL=(0.30, -0.03, 1.44), kL=(1.0, 0.3, 0.0), pL=-30.0, bL=-15.0, gL=0.3, giL=0.25,
      gtL=0.2),
    K(52, hp=-19, shL=12, shR=12, wL=(0.31, -0.02, 1.47)), K(66, hp=6, sp=6, shL=0, shR=0),
    K(76, wR=(0.20, -0.20, 1.20), kR=(1.0, -0.2, -0.6), pR=-30.0, bR=10.0, gR=0.5, giR=0.4, gtR=0.4, hp=10, hy=-6),
    K(90, wR=REST_W, kR=REST_K, pR=REST_P, bR=REST_B, gR=REST_G, giR=REST_GI, gtR=REST_GT,
      wL=REST_W, pL=REST_P, gL=REST_G, giL=REST_GI, gtL=REST_GT, hp=4, hy=0),
    S(108), S(120)],
    face=[(16, 'あ', 0), (30, 'あ', 0.9), (56, 'あ', 0.9), (66, 'あ', 0), (20, 'まばたき', 0), (28, 'まばたき', 1.0),
          (62, 'まばたき', 1.0), (72, 'まばたき', 0.2), (90, 'まばたき', 0), (60, '涙', 0), (68, '涙', 0.5), (110, '涙', 0)])

# 4 hair_tuck: right hand tucks the hair behind the ear, head tilting into it
clip('hair_tuck', 120, [
    S(0), K(10, hr=-4, hy=-6),
    K(30, wR=(0.10, -0.10, 1.25), kR=(0.6, -0.7, -0.3), pR=-60.0, bR=-10.0, gR=0.1, giR=0.05, gtR=0.15,
      shR=6, hr=-10, hy=-10, sr=-3),
    K(44, wR=(0.105, -0.04, 1.29), kR=(0.8, -0.5, -0.1), bR=-25.0, hr=-12),
    K(56, wR=(0.115, -0.01, 1.28), gR=0.3, giR=0.25),
    K(74, wR=(0.30, -0.10, 0.92), kR=(1.0, 0.5, -0.4), pR=-10.0, bR=0.0, gR=0.25, shR=0, hr=4, hy=4, sr=0),
    S(100), S(120)],
    look=True, face=[(20, 'にこり', 0), (40, 'にこり', 0.6), (90, 'にこり', 0),
          (26, '照れ', 0), (40, '照れ', 0.5), (86, '照れ', 0), (30, 'ω', 0), (42, 'ω', 0.5), (80, 'ω', 0)])

# 5 heel_rock: hands clasped in front, rocking up onto the toes and back
_rock = []
for i, f in enumerate((18, 34, 50, 66, 82, 98)):
    up = i % 2 == 0
    _rock.append(K(f, tip=14 if up else 0, c=(0.0, 0.0, -0.006 if up else -0.02), sp=0 if up else 5,
                   hp=-4 if up else 4, hr=3 * (1 if i % 4 == 0 else -1)))
clip('heel_rock', 150, [S(0), K(10, **CLASP_FRONT, sp=4)] + _rock + [K(112, tip=0, hr=0, sp=2, c=(0.0, 0.0, -0.006)),
                                                                     K(124, **CLASP_FRONT), S(140), S(150)],
     look=True, face=[(10, 'にこり', 0), (24, 'にこり', 0.5), (130, 'にこり', 0),
          (14, 'ω', 0), (26, 'ω', 0.6), (120, 'ω', 0), (30, 'なごみ', 0), (40, 'なごみ', 0.5), (110, 'なごみ', 0)])

# 6 kick_pebble: eyes down, the right foot draws back and flicks forward, she watches it roll
clip('kick_pebble', 120, [
    S(0), K(12, hp=24, hy=-6, sp=6),
    K(26, fR=(0.0, 0.16, 0.07), fpR=25, c=(0.012, 0.01, -0.02), sp=2, lr=4, wL=(0.30, -0.15, 0.88),
      wR=(0.27, 0.0, 0.86)),
    K(34, fR=(0.01, -0.22, 0.11), fpR=-8, c=(0.01, -0.02, -0.01), sp=8, wL=(0.28, 0.0, 0.86),
      wR=(0.29, -0.16, 0.88)),
    K(40, fR=(0.01, -0.24, 0.12)),
    K(52, fR=(0.0, -0.05, 0.0), fpR=0, c=(0.0, 0.0, -0.006), lr=0, hp=6, hy=-22, sy=-6, sp=2,
      wL=REST_W, wR=REST_W),
    K(78, hy=-34, hp=-2, sy=-9), K(92, hy=-4, sy=0, hp=0, fR=(0.0, 0.0, 0.0)), S(110), S(120)],
    face=[(30, '口角上げ', 0), (40, '口角上げ', 0.5), (60, 'にやり', 0), (70, 'にやり', 0.5), (100, 'にやり', 0), (60, '口角上げ', 0),
          (12, 'う', 0), (20, 'う', 0.4), (30, 'う', 0)])

# 7 hum_sway: swaying from foot to foot, head tilting with the beat
_sway = []
for i, f in enumerate(range(15, 166, 25)):
    s = 1 if i % 2 == 0 else -1
    _sway.append(K(f, c=(0.03 * s, 0.0, -0.012), lr=-5 * s, sr=4 * s, hr=9 * s, hy=4 * s,
                   **{('tipR' if s > 0 else 'tipL'): 16, ('tipL' if s > 0 else 'tipR'): 0},
                   wL=(0.25 + 0.02 * s, -0.13, 0.86), wR=(0.25 - 0.02 * s, -0.13, 0.86)))
clip('hum_sway', 180, [S(0)] + _sway + [S(180)], look=True,
     face=[(6, 'ω', 0), (16, 'ω', 0.8), (160, 'ω', 0.8), (176, 'ω', 0), (6, 'なごみ', 0), (18, 'なごみ', 0.6), (170, 'なごみ', 0)])

# 8 check_shoe: lifts the left foot behind her, looks back and down at the shoe, turns it
clip('check_shoe', 150, [
    S(0), K(10, c=(-0.02, 0.0, -0.01), lr=3),
    K(30, fL=(0.0, 0.10, 0.16), fpL=35, fyL=-4, c=(-0.035, 0.0, -0.015), lr=5, sp=6, sy=22, hy=46, hp=30, hr=8,
      wL=(0.29, 0.02, 0.90), wR=(0.31, -0.14, 0.92)),
    K(52, fyL=-24, fpL=40), K(70, fyL=14), K(86, fyL=-4, hp=26, hr=4),
    K(100, fL=(0.0, 0.0, 0.0), fpL=0, fyL=3, c=(-0.01, 0.0, -0.01), lr=0, sp=2, sy=0, hy=0, hp=2, hr=0,
      wL=REST_W, wR=REST_W),
    S(130), S(150)],
    face=[(30, '真面目', 0), (40, '真面目', 0.5), (90, '真面目', 0.5), (100, '真面目', 0), (100, 'にこり', 0), (110, 'にこり', 0.5), (140, 'にこり', 0),
          (30, 'う', 0), (40, 'う', 0.4), (92, 'う', 0)])

# 9 sneeze: hitching breaths, the hand comes up, the sneeze snaps forward, a head shake
clip('sneeze', 90, [
    S(0), K(8, hp=-6, sp=-2, shL=3, shR=3),
    K(16, hp=-12, sp=-5, shL=6, shR=6, wR=(0.10, -0.20, 1.12), kR=(1.0, -0.2, -0.8), pR=-60.0, gR=0.3, giR=0.2),
    K(24, hp=-8, sp=-3), K(30, hp=-17, sp=-8, shL=9, shR=9, c=(0.0, 0.02, -0.006)),
    K(35, hp=24, sp=22, shL=0, shR=0, c=(0.0, -0.02, -0.03), wR=(0.012, -0.17, 1.18), kR=(0.6, -0.3, -1.0), pR=60.0,
      gR=0.15, giR=0.1),
    K(42, hp=18, sp=16), K(52, hp=4, sp=4, hy=12, wR=(0.30, -0.10, 0.85), kR=(1.0, 0.5, -0.3), pR=-10.0),
    K(57, hy=-12), K(62, hy=9), K(67, hy=-5), K(72, hy=0, hp=2), S(84), S(90)],
    face=[(10, 'まばたき', 0), (16, 'まばたき', 0.5), (30, 'まばたき', 0.8), (35, 'まばたき', 1.0), (44, 'まばたき', 1.0), (50, 'まばたき', 0),
          (14, 'あ', 0), (30, 'あ', 0.7), (34, 'あ', 0), (34, 'う', 0), (36, 'う', 0.8), (44, 'う', 0), (46, '困る', 0), (52, '困る', 0.7), (84, '困る', 0)])

# 10 sit_rest: crouches down hugging the knees, rocks a little, gets back up
SQUAT = dict(c=(0.0, 0.05, -0.33), sp=30, lp=4, hp=-14)
HUG = dict(w=(0.16, -0.40, 0.95), k=(1.0, 0.35, -0.3), p=-20.0, b=-5.0, g=0.35, gi=0.3, gt=0.3)   # hands on the knees
clip('sit_rest', 300, [
    S(0), K(10, hp=10, sp=6),
    K(30, c=(0.0, 0.03, -0.18), sp=24, w=(0.28, -0.22, 0.86), k=(1.0, 0.4, -0.4), f=(0.03, 0.0, 0.0), fy=10),
    K(52, **SQUAT, **HUG), K(70, hp=-10, hr=6),
    K(100, sr=4, lr=-3, hr=10, c=(0.012, 0.05, -0.33)), K(130, sr=-4, lr=3, hr=-8, c=(-0.012, 0.05, -0.33)),
    K(160, sr=3, lr=-2, hr=6, c=(0.008, 0.05, -0.33)), K(190, sr=0, lr=0, hr=0, c=(0.0, 0.05, -0.33), hp=-16),
    K(222, hp=-4), K(240, c=(0.0, 0.04, -0.20), sp=28, w=(0.28, -0.20, 0.88), k=(1.0, 0.4, -0.4), p=-10.0),
    K(262, c=(0.0, 0.0, -0.006), sp=4, hp=2, f=(0.0, 0.0, 0.0), fy=3.0, w=REST_W, k=REST_K,
      p=REST_P, b=REST_B, g=REST_G, gi=REST_GI, gt=REST_GT),
    S(286), S(300)],
    look=True, face=[(40, 'なごみ', 0), (60, 'なごみ', 0.7), (200, 'なごみ', 0.7), (230, 'なごみ', 0),
                     (90, 'まばたき', 0), (96, 'まばたき', 0.6), (180, 'まばたき', 0.6), (190, 'まばたき', 0)])

# 11 head_pat: shoulders up, hands together at the chest, a bashful wiggle
clip('head_pat', 150, [
    S(0), K(6, hp=-6, shL=8, shR=8, c=(0.0, 0.0, -0.02)),
    K(20, **CHEST_HOLD, hp=10, hr=8, shL=10, shR=10, sp=4, tipR=10, fyR=-12),
    K(40, sy=8, ly=4, hr=12), K(60, sy=-8, ly=-4, hr=4), K(80, sy=6, ly=3, hr=11), K(100, sy=-3, ly=-1, hr=6),
    K(116, sy=0, ly=0, hr=3, tipR=0, fyR=3),
    K(126, w=REST_W, k=REST_K, p=REST_P, b=REST_B, g=REST_G, gi=REST_GI, gt=REST_GT, shL=0, shR=0, hp=2),
    S(140), S(150)],
    face=[(4, '照れ', 0), (16, '照れ', 1.0), (130, '照れ', 1.0), (146, '照れ', 0), (6, 'はぅ', 0), (18, 'はぅ', 0.8), (120, 'はぅ', 0.8), (136, 'はぅ', 0),
          (10, 'まばたき', 0), (16, 'まばたき', 0.6), (124, 'まばたき', 0.6), (132, 'まばたき', 0)])

# 12 poke_startle: a hop back, hands up, then steps back to her mark
STARTLE_HANDS = dict(w=(0.17, -0.20, 1.10), k=(1.0, 0.1, -0.7), p=-60.0, b=-30.0, g=0.05, gi=0.0, gt=0.0, sh=10.0)
clip('poke_startle', 90, [
    S(0), K(3, c=(0.0, 0.0, -0.025)),
    K(9, **STARTLE_HANDS, c=(0.0, 0.10, 0.03), f=(0.0, 0.08, 0.05), sp=-10, hp=-8),
    K(15, c=(0.0, 0.12, -0.03), f=(0.0, 0.12, 0.0), sp=-4, hp=-2),
    K(28, sp=0, hp=4, sh=4.0, w=(0.24, -0.16, 0.98)),
    K(42, fL=(0.0, 0.03, 0.05), c=(0.0, 0.07, -0.01)), K(50, fL=(0.0, 0.0, 0.0), c=(0.0, 0.05, -0.01)),
    K(58, fR=(0.0, 0.03, 0.05), c=(0.0, 0.02, -0.01)), K(66, fR=(0.0, 0.0, 0.0), c=(0.0, 0.0, -0.006)),
    K(70, w=REST_W, k=REST_K, p=REST_P, b=REST_B, g=REST_G, gi=REST_GI, gt=REST_GT, sh=0.0, sp=2, hp=0),
    S(84), S(90)],
    face=[(2, 'びっくり', 0), (6, 'びっくり', 1.0), (30, 'びっくり', 1.0), (44, 'びっくり', 0), (4, '瞳小', 0), (7, '瞳小', 0.8), (36, '瞳小', 0),
          (6, 'ワ', 0), (9, 'ワ', 0.7), (24, 'ワ', 0), (30, '汗', 0), (40, '汗', 0.8), (80, '汗', 0)])

# 13 annoyed_stomp: hands on hips, two stomps, looks away pouting
clip('annoyed_stomp', 150, [
    S(0), K(8, sp=-2, c=(0.0, 0.0, -0.012)),
    K(20, **HIPS, sp=-5, hp=-6, hy=0),
    K(30, fR=(0.0, -0.02, 0.10), fpR=-5, c=(0.02, 0.0, -0.006), lr=4),
    K(35, fR=(0.0, -0.02, 0.0), fpR=0, c=(0.012, 0.0, -0.03), lr=0, hp=4),
    K(44, fR=(0.0, -0.02, 0.10), c=(0.02, 0.0, -0.006), lr=4, hp=-4),
    K(49, fR=(0.0, -0.02, 0.0), c=(0.012, 0.0, -0.03), lr=0, hp=4),
    K(60, c=(0.0, 0.0, -0.01), fR=(0.0, 0.0, 0.0), hy=-40, hp=-8, hr=-10, sy=-10, ly=-4),
    K(96, hy=-42, hr=-12), K(108, hy=-12, hp=0, hr=-4), K(116, hy=-40, hr=-10),
    K(126, hy=0, hp=0, hr=0, sy=0, ly=0, w=REST_W, k=REST_K, p=REST_P, b=REST_B, g=REST_G, gi=REST_GI, gt=REST_GT),
    S(144), S(150)],
    face=[(8, '怒り', 0), (20, '怒り', 0.8), (120, '怒り', 0.8), (136, '怒り', 0), (8, 'じと目', 0), (20, 'じと目', 0.7), (130, 'じと目', 0),
          (60, '▲', 0), (66, '▲', 0.7), (120, '▲', 0), (100, 'ぺろっ', 0), (104, 'ぺろっ', 0.9), (110, 'ぺろっ', 0.9), (114, 'ぺろっ', 0)])

# 14 twirl: wind-up, one full turn to her left on the balls of the feet, a little bow of the head
TWIRL_ARMS = dict(w=(0.44, -0.10, 1.02), k=(0.3, 0.6, -1.0), p=15.0, g=0.1, gi=0.05, gt=0.1)
clip('twirl', 120, [
    S(0), K(10, turn=-18, sy=-8, c=(0.0, 0.0, -0.03), hy=-6),
    K(22, turn=40, sy=10, tip=12, c=(0.0, 0.0, -0.004), **TWIRL_ARMS, hy=10),
    K(34, turn=150, tip=14), K(46, turn=265, tip=14), K(58, turn=345, tip=6, sy=2, hy=0),
    K(64, turn=360, tip=0, sy=0, c=(0.0, 0.0, -0.02)),
    K(76, turn=360, c=(0.0, 0.0, -0.006), hp=8, hr=8, w=(0.30, -0.10, 0.86), k=(1.0, 0.5, -0.4)),
    K(94, turn=360, hp=0, hr=0, w=REST_W, k=REST_K, p=REST_P, g=REST_G, gi=REST_GI, gt=REST_GT),
    K(120, reset=True, turn=360)],
    face=[(16, '笑い', 0), (26, '笑い', 0.9), (80, '笑い', 0.9), (110, '笑い', 0),
          (20, 'ワ', 0), (28, 'ワ', 0.5), (60, 'ワ', 0.5), (74, 'ワ', 0), (70, '照れ', 0), (80, '照れ', 0.4), (110, '照れ', 0)])

# 15 jump_happy: crouch, jump with the arms swinging up, land soft
clip('jump_happy', 90, [
    S(0), K(10, c=(0.0, 0.02, -0.12), sp=14, hp=4, w=(0.30, 0.08, 0.86), k=(0.8, -0.4, -0.4)),
    K(18, c=(0.0, 0.0, 0.17), f=(0.0, 0.01, 0.15), fp=28, sp=-6, hp=-10,
      w=(0.40, -0.12, 1.45), k=(0.6, 0.5, -0.8), g=0.05, gi=0.0, gt=0.0, sh=8.0),
    K(24, c=(0.0, 0.0, 0.20), f=(0.0, 0.01, 0.19), fp=22),
    K(31, c=(0.0, 0.0, 0.0), f=(0.0, 0.0, 0.0), fp=0, sp=4),
    K(37, c=(0.0, 0.01, -0.10), sp=12, hp=4, w=(0.36, -0.12, 0.95), sh=0.0),
    K(50, c=(0.0, 0.0, -0.006), sp=2, hp=0, w=REST_W, k=REST_K, g=REST_G, gi=REST_GI, gt=REST_GT),
    S(80), S(90)],
    face=[(4, 'キリッ', 0), (10, 'キリッ', 0.6), (16, 'キリッ', 0), (14, '笑い', 0), (20, '笑い', 1.0), (60, '笑い', 1.0), (80, '笑い', 0),
          (14, 'ワ', 0), (19, 'ワ', 0.9), (40, 'ワ', 0.9), (56, 'ワ', 0)])

# 16 shy_cover: hands over the face, turns away, peeks through the fingers, turns back
clip('shy_cover', 150, [
    S(0), K(6, hp=-4, sh=6.0),
    K(18, **FACE_COVER, hp=10, sh=10.0, sp=6, c=(0.0, 0.01, -0.02)),
    K(34, sy=-26, ly=-10, hy=-18, hr=-6, turn=-6), K(70, sy=-28, hy=-20),
    K(84, wL=(0.16, -0.20, 1.15), pL=40.0, bL=0.0, hy=-8, hp=4), K(106, hy=-10),
    K(114, wL=(0.05, -0.18, 1.235), pL=75.0, bL=-35.0, hy=-22, hp=10),
    K(126, sy=0, ly=0, hy=0, hr=0, turn=0, w=REST_W, k=REST_K, p=REST_P, b=REST_B, g=REST_G, gi=REST_GI,
      gt=REST_GT, sh=0.0, hp=2, sp=2, c=(0.0, 0.0, -0.006)),
    S(144), S(150)],
    face=[(4, '照れ', 0), (14, '照れ', 1.0), (136, '照れ', 1.0), (148, '照れ', 0), (10, 'はぅ', 0), (20, 'はぅ', 0.7), (126, 'はぅ', 0)])

# 17 wave_hello: right hand up, a few waves, head tilt
WAVE_UP_R = dict(wR=(0.36, -0.10, 1.31), kR=(0.6, 0.2, -1.0), pR=-70.0, bR=0.0, gR=0.05, giR=0.0, gtR=0.1, shR=5.0)
clip('wave_hello', 120, [
    S(0), K(8, sr=-2, c=(0.008, 0.0, -0.01)),
    K(18, **WAVE_UP_R, hr=8, sr=4, lr=-2)] + _wave(26, 'R', 7) + [
    K(76, wR=(0.34, -0.10, 1.30), bR=0.0, hr=6),
    K(92, wR=REST_W, kR=REST_K, pR=REST_P, gR=REST_G, giR=REST_GI, gtR=REST_GT, shR=0.0, hr=0, sr=0, lr=0,
      c=(0.0, 0.0, -0.006)),
    S(110), S(120)],
    look=True, face=[(10, '笑い', 0), (20, '笑い', 0.9), (90, '笑い', 0.9), (110, '笑い', 0),
          (18, 'あ', 0), (26, 'あ', 0.55), (40, 'あ', 0.2), (52, 'あ', 0.5), (66, 'あ', 0)])

# 18 wave_bye: both arms waving overhead, rising onto the toes with each swing
_bye = []
for i in range(8):
    s = 1 if i % 2 == 0 else -1
    _bye.append(K(24 + i * 9, sr=5 * s, c=(-0.012 * s, 0.0, -0.006), hr=6 * s,
                  wL=(0.20 + 0.10 * s, -0.08, 1.50), wR=(0.20 - 0.10 * s, -0.08, 1.50), bL=-12.0 * s, bR=12.0 * s))
clip('wave_bye', 150, [
    S(0), K(10, c=(0.0, 0.0, -0.03), sp=5),
    K(20, w=(0.25, -0.08, 1.50), k=(1.0, 0.3, -0.4), p=-70.0, g=0.05, gi=0.0, gt=0.1, sh=10.0, tip=10, sp=-2,
      c=(0.0, 0.0, -0.006))] + _bye + [
    K(102, sr=0, hr=0, w=(0.28, -0.08, 1.48), b=0.0, c=(0.0, 0.0, -0.006)),
    K(118, w=(0.36, -0.12, 0.95), k=(1.0, 0.5, -0.5), p=-20.0, sh=0.0, tip=0),
    K(130, w=REST_W, k=REST_K, p=REST_P, g=REST_G, gi=REST_GI, gt=REST_GT),
    S(144), S(150)],
    look=True, face=[(10, '笑い', 0), (22, '笑い', 1.0), (110, '笑い', 1.0), (140, '笑い', 0), (40, '口横広げ', 0), (50, '口横広げ', 0.5), (100, '口横広げ', 0)])

# 19 welcome_back: a bounce, then a jump with both arms up in a V
clip('welcome_back', 120, [
    S(0), K(6, c=(0.0, 0.0, -0.06), sp=8, hp=6),
    K(14, c=(0.0, 0.0, 0.0), sp=0, hp=-4, w=(0.36, -0.10, 1.10), k=(0.4, 0.6, -1.0), g=0.1, gi=0.05, gt=0.1, tip=10),
    K(22, c=(0.0, 0.01, -0.10), sp=10, hp=4, w=(0.30, 0.02, 0.88), tip=0, g=0.4),
    K(31, c=(0.0, 0.0, 0.16), f=(0.0, 0.0, 0.14), fp=26, sp=-6, hp=-12,
      w=(0.44, -0.07, 1.50), k=(1.0, 0.3, -0.6), g=0.05, gi=0.0, gt=0.0, sh=10.0),
    K(37, c=(0.0, 0.0, 0.18), f=(0.0, 0.0, 0.17), fp=20),
    K(44, c=(0.0, 0.0, 0.0), f=(0.0, 0.0, 0.0), fp=0, sp=4),
    K(50, c=(0.0, 0.0, -0.08), sp=10, hp=2),
    K(62, c=(0.0, 0.0, -0.006), sp=2, w=(0.42, -0.10, 1.40), sh=6.0, hp=-2),
    K(82, w=REST_W, k=REST_K, g=REST_G, gi=REST_GI, gt=REST_GT, sh=0.0, hp=0),
    S(108), S(120)],
    look=True, face=[(10, '笑い', 0), (20, '笑い', 1.0), (100, '笑い', 1.0), (114, '笑い', 0), (26, 'ワ', 0), (32, 'ワ', 0.8), (50, 'ワ', 0),
          (60, '照れ', 0), (70, '照れ', 0.5), (110, '照れ', 0)])

# 20 bow: an ojigi, hands folded in front
clip('bow', 120, [
    S(0), K(10, **CLASP_FRONT, hp=-2),
    K(30, sp=32, lp=8, hp=12, c=(0.0, 0.035, -0.012)), K(52, sp=34, hp=14),
    K(70, sp=4, lp=0, hp=0, c=(0.0, 0.0, -0.006)),
    K(84, w=REST_W, k=REST_K, p=REST_P, b=REST_B, g=REST_G, gi=REST_GI, gt=REST_GT, hr=6),
    K(98, hr=0), S(110), S(120)],
    face=[(24, 'まばたき', 0), (32, 'まばたき', 1.0), (54, 'まばたき', 1.0), (62, 'まばたき', 0), (70, 'にこり', 0), (80, 'にこり', 0.8), (112, 'にこり', 0),
          (74, '照れ', 0), (84, '照れ', 0.4), (110, '照れ', 0)])

# 21 curtsy: holds the skirt out, right foot behind, dips with a head tilt
SKIRT_HOLD = dict(w=(0.31, -0.12, 0.81), k=(1.0, 0.3, -0.4), p=-35.0, b=10.0, g=0.65, gi=0.55, gt=0.6)
clip('curtsy', 120, [
    S(0), K(10, **SKIRT_HOLD, hp=2),
    K(26, fR=(-0.10, 0.16, 0.03), tipR=22, c=(0.0, 0.03, -0.03)),
    K(42, c=(0.0, 0.04, -0.11), sp=12, hp=12, hr=-7, fyL=8),
    K(60, c=(0.0, 0.04, -0.12), sp=13, hp=13), K(74, c=(0.0, 0.03, -0.03), sp=4, hp=2, hr=0),
    K(88, fR=(0.0, 0.0, 0.0), tipR=0, fyL=3, c=(0.0, 0.0, -0.006),
      w=REST_W, k=REST_K, p=REST_P, b=REST_B, g=REST_G, gi=REST_GI, gt=REST_GT),
    S(110), S(120)],
    face=[(10, 'にこり', 0), (30, 'にこり', 0.8), (100, 'にこり', 0.8), (114, 'にこり', 0), (40, 'まばたき', 0), (46, 'まばたき', 0.8), (62, 'まばたき', 0.8), (70, 'まばたき', 0),
          (30, '照れ', 0), (44, '照れ', 0.5), (96, '照れ', 0)])


# 22 / 23 point_left / point_right: points with one arm, the other hand on the hip, looks there
def _point(t):
    o = 'R' if t == 'L' else 'L'
    s = 1 if t == 'L' else -1
    return [
        S(0), K(8, sy=-4 * s, hp=4),
        K(22, **{f'w{t}': (0.47, -0.27, 1.20), f'k{t}': (0.4, 0.4, -1.0), f'p{t}': 55.0, f'b{t}': -8.0,
                 f'g{t}': 1.0, f'gi{t}': 0.0, f'gt{t}': 0.75, f'sh{t}': 6.0},
          **_side(HIPS, o), sy=14 * s, hy=32 * s, hp=-4, hr=4 * s, sr=3 * s, c=(0.012 * s, 0.0, -0.006)),
        K(28, **{f'w{t}': (0.49, -0.29, 1.22)}),
        K(36, **{f'w{t}': (0.46, -0.27, 1.18)}), K(44, **{f'w{t}': (0.49, -0.29, 1.21)}),
        K(70, hy=6 * s, hp=0, hr=8 * s),
        K(86, **{f'w{t}': REST_W, f'k{t}': REST_K, f'p{t}': REST_P, f'b{t}': REST_B,
                 f'g{t}': REST_G, f'gi{t}': REST_GI, f'gt{t}': REST_GT, f'sh{t}': 0.0}, sy=0, hy=0, hr=0, sr=0, c=(0.0, 0.0, -0.006)),
        K(96, **{f'w{o}': REST_W, f'k{o}': REST_K, f'p{o}': REST_P, f'b{o}': REST_B, f'g{o}': REST_G,
                 f'gi{o}': REST_GI, f'gt{o}': REST_GT}),
        S(110), S(120)]


_POINT_FACE = [(14, 'キリッ', 0), (24, 'キリッ', 0.7), (60, 'キリッ', 0.7), (70, 'キリッ', 0), (64, 'にこり', 0), (72, 'にこり', 0.8), (110, 'にこり', 0)]
clip('point_left', 120, _point('L'), face=_POINT_FACE)
clip('point_right', 120, _point('R'), face=_POINT_FACE)

# 24 clap_cheer: claps with a bounce in the knees, then a little hop
CLAP_OPEN = dict(w=(0.14, -0.27, 1.03), k=(1.0, 0.1, -0.6), p=-15.0, b=-10.0, g=0.05, gi=0.0, gt=0.1)
_clap = []
for i in range(6):
    f = 14 + i * 10
    _clap.append(K(f, w=(0.03, -0.29, 1.04), c=(0.0, 0.0, -0.03)))
    _clap.append(K(f + 5, w=(0.15, -0.27, 1.04), c=(0.0, 0.0, -0.006)))
clip('clap_cheer', 120, [S(0), K(8, **CLAP_OPEN, sp=4, hp=-4)] + _clap + [
    K(80, c=(0.0, 0.0, -0.07), sp=8), K(87, c=(0.0, 0.0, 0.08), f=(0.0, 0.0, 0.07), fp=18, sp=-2, w=(0.30, -0.10, 1.25),
                                       k=(0.6, 0.5, -1.0), hp=-6),
    K(94, c=(0.0, 0.0, -0.04), f=(0.0, 0.0, 0.0), fp=0, sp=4, hp=0),
    K(102, c=(0.0, 0.0, -0.006), sp=2, w=REST_W, k=REST_K, p=REST_P, b=REST_B, g=REST_G, gi=REST_GI, gt=REST_GT),
    S(114), S(120)],
    look=True, face=[(8, '笑い', 0), (16, '笑い', 1.0), (104, '笑い', 1.0), (116, '笑い', 0),
          (12, 'ワ', 0), (20, 'ワ', 0.8), (96, 'ワ', 0.8), (108, 'ワ', 0)])

# 25 thumbs_up: right thumb up toward the viewer, a wink and a nod
clip('thumbs_up', 90, [
    S(0), K(8, sp=3, hp=-2),
    K(20, wR=(0.22, -0.34, 1.10), kR=(0.6, 0.4, -1.0), pR=-85.0, bR=-6.0, gR=1.0, giR=1.0, gtR=0.0, shR=4.0,
      sy=-8, hr=8, hy=-4, c=(0.006, 0.0, -0.006)),
    K(26, wR=(0.23, -0.36, 1.13)), K(34, hp=10), K(40, hp=-2), K(46, hp=6),
    K(60, hp=0, hr=4),
    K(72, wR=REST_W, kR=REST_K, pR=REST_P, bR=REST_B, gR=REST_G, giR=REST_GI, gtR=REST_GT, shR=0.0, sy=0, hr=0, hy=0,
      c=(0.0, 0.0, -0.006)),
    S(84), S(90)],
    look=True, face=[(16, 'ウィンク', 0), (22, 'ウィンク', 1.0), (50, 'ウィンク', 1.0), (58, 'ウィンク', 0), (14, '笑い', 0), (22, '笑い', 0.8), (80, '笑い', 0),
          (18, '口角上げ', 0), (24, '口角上げ', 0.8), (70, '口角上げ', 0)])

# 26 heart: a finger heart at the chest for the viewer, a lean, a toe pop and a wink
HEART = dict(w=(0.075, -0.27, 1.16), k=(1.0, 0.2, -0.8), p=-90.0, b=20.0, g=0.6, gi=0.6, gt=0.0, sh=4.0)   # fingers curved into a heart at the chest
clip('heart', 120, [
    S(0), K(8, c=(0.0, 0.0, -0.025), sp=4),
    K(24, **HEART, sr=-6, hr=9, tipL=20, fL=(0.0, -0.04, 0.0), c=(0.012, 0.0, -0.01), sp=0),
    K(40, hr=11, sr=-7), K(56, hr=7), K(70, hr=10),
    K(84, sr=0, hr=0, tipL=0, fL=(0.0, 0.0, 0.0), c=(0.0, 0.0, -0.006), w=(0.40, -0.10, 1.25), k=(0.8, 0.5, -0.6), p=-10.0,
      b=0.0, g=0.15),
    K(98, w=REST_W, k=REST_K, p=REST_P, g=REST_G, gi=REST_GI, gt=REST_GT, sh=0.0),
    S(112), S(120)],
    look=True, face=[(10, 'にこり', 0), (22, 'にこり', 1.0), (92, 'にこり', 1.0), (110, 'にこり', 0), (20, '照れ', 0), (30, '照れ', 0.6), (90, '照れ', 0),
                     (28, 'ウィンク', 0), (34, 'ウィンク', 1.0), (72, 'ウィンク', 1.0), (78, 'ウィンク', 0),
          (24, 'ω', 0), (32, 'ω', 0.6), (84, 'ω', 0)])

# 27 balance_wobble: the floor tips, arms fly out, she wobbles and steadies
_wob = []
for i, (f, a) in enumerate(((14, 1.0), (25, -0.85), (37, 0.65), (50, -0.45), (64, 0.25))):
    _wob.append(K(f, sr=12 * a, lr=-7 * a, c=(-0.035 * a, 0.0, -0.02), hr=-8 * a,
                  **{('tipR' if a > 0 else 'tipL'): 0, ('tipL' if a > 0 else 'tipR'): 18 * abs(a)},
                  wL=(0.52, -0.06, 1.10 + 0.06 * a), wR=(0.52, -0.06, 1.10 - 0.06 * a)))
clip('balance_wobble', 120, [S(0), K(6, **ARMS_OUT, c=(0.0, 0.0, -0.04), sh=4.0)] + _wob + [
    K(78, sr=0, lr=0, hr=0, tipL=0, tipR=0, c=(0.0, 0.0, -0.01), wL=(0.52, -0.06, 1.10), wR=(0.52, -0.06, 1.10)),
    K(94, w=REST_W, k=REST_K, p=REST_P, g=REST_G, gi=REST_GI, gt=REST_GT, sh=0.0, c=(0.0, 0.0, -0.006)),
    S(112), S(120)],
    face=[(4, 'びっくり', 0), (10, 'びっくり', 0.8), (60, 'びっくり', 0.4), (80, 'びっくり', 0), (6, 'ワ', 0), (12, 'ワ', 0.6), (70, 'ワ', 0),
          (70, '汗', 0), (80, '汗', 0.8), (110, '汗', 0)])

# 28 dizzy: the head and torso circle, she stumbles a step each way, shakes it off
_diz = []
for i in range(10):
    a = 2 * math.pi * i / 5
    k = 1.0 - i / 12
    _diz.append(K(10 + i * 10, hr=12 * k * math.sin(a), hp=8 * k * math.cos(a), hy=10 * k * math.sin(a + 1),
                  sr=6 * k * math.sin(a - 0.6), sp=3 + 4 * k * math.cos(a - 0.6), c=(0.03 * k * math.sin(a - 1.0), 0.0, -0.03)))
clip('dizzy', 180, [S(0), K(6, w=(0.42, -0.06, 0.92), k=(0.6, 0.6, -0.8), p=15.0, g=0.1)] + _diz + [
    K(46, fL=(0.04, 0.0, 0.0)), K(64, fR=(0.05, 0.02, 0.0)), K(84, fL=(0.0, 0.0, 0.0)), K(100, fR=(0.0, 0.0, 0.0)),
    K(112, hy=-14, hr=0, hp=4, sr=0, sp=2, c=(0.0, 0.0, -0.006)), K(118, hy=13), K(124, hy=-9), K(130, hy=4), K(136, hy=0),
    K(146, w=REST_W, k=REST_K, p=REST_P, g=REST_G),
    S(168), S(180)],
    face=[(4, '困る', 0), (14, '困る', 0.8), (120, '困る', 0.8), (150, '困る', 0), (10, 'ハイライト消', 0), (20, 'ハイライト消', 0.8), (110, 'ハイライト消', 0.8), (124, 'ハイライト消', 0),
          (20, 'う', 0), (30, 'う', 0.5), (110, 'う', 0)])

# 29 mining_swing: an imaginary pickaxe over the right shoulder, three strikes, a look at the haul
RAISE_R = dict(wR=(0.22, 0.0, 1.40), kR=(1.0, 0.2, -0.6), pR=-30.0, bR=-25.0, gR=1.0, giR=1.0, gtR=0.8, shR=8.0,
               wL=(-0.12, -0.07, 1.36), kL=(0.8, -0.5, -0.6), pL=-30.0, bL=-15.0, gL=1.0, giL=1.0, gtL=0.8)
STRIKE_R = dict(wR=(0.06, -0.40, 0.93), kR=(0.7, 0.3, -0.6), pR=-40.0, bR=10.0, shR=0.0,
                wL=(-0.02, -0.34, 0.97), kL=(1.0, 0.2, -0.5), pL=-40.0, bL=5.0)
_mine = []
for i in range(3):
    f = 20 + i * 26
    _mine += [K(f, **RAISE_R, sp=-6, sy=-10, hp=4, c=(0.0, 0.01, -0.006), lr=0),
              K(f + 9, **STRIKE_R, sp=26, sy=-4, hp=14, c=(0.0, -0.01, -0.06), lr=2),
              K(f + 14, sp=22, hp=12, c=(0.0, -0.01, -0.05))]
clip('mining_swing', 150, [S(0), K(8, f=(0.06, 0.0, 0.0), fy=12, c=(0.0, 0.0, -0.02), hp=10)] + _mine + [
    K(112, sp=8, hp=20, hy=-8, sy=0, wR=(0.30, -0.12, 0.90), kR=(1.0, 0.4, -0.5), wL=(0.30, -0.12, 0.90), kL=(1.0, 0.4, -0.5),
      pR=-10.0, pL=-10.0, bR=0.0, bL=0.0, g=0.3, gi=0.2, gt=0.2, shR=0.0, c=(0.0, 0.0, -0.01)),
    K(126, sp=2, hp=0, hy=0, f=(0.0, 0.0, 0.0), fy=3.0, c=(0.0, 0.0, -0.006),
      w=REST_W, k=REST_K, p=REST_P, g=REST_G, gi=REST_GI, gt=REST_GT),
    S(144), S(150)],
    face=[(10, 'キリッ', 0), (20, 'キリッ', 0.8), (96, 'キリッ', 0.8), (104, 'キリッ', 0), (100, '笑い', 0), (112, '笑い', 1.0), (140, '笑い', 0)])

# 30 idol_dance: 10 s at 120 bpm (15 frames a beat): step-touches, a point, claps, a turn, a heart
B = 15
_dance = [S(0)]
for i in range(4):                                    # bars 1-2: step-touch side to side, arms swing
    s = 1 if i % 2 == 0 else -1
    f = B * (1 + 2 * i)
    _dance += [K(f, c=(0.05 * s, 0.0, -0.04), lr=-5 * s, sr=4 * s, hr=7 * s,
                 **{('fL' if s > 0 else 'fR'): (0.10, 0.0, 0.0), ('fR' if s > 0 else 'fL'): (-0.06, 0.0, 0.0)},
                 **{('tipR' if s > 0 else 'tipL'): 18, ('tipL' if s > 0 else 'tipR'): 0},
                 wL=(0.38, -0.14, 1.05 + 0.1 * s), wR=(0.38, -0.14, 1.05 - 0.1 * s), k=(1.0, 0.4, -0.6),
                 g=0.4, gi=0.3, gt=0.3),
               K(f + B, c=(0.03 * s, 0.0, -0.01))]
f = B * 9                                             # bar 3: point up-front, hand on hip
_dance += [K(f, fL=(0.0, 0.0, 0.0), fR=(0.0, 0.0, 0.0), tipL=0, tipR=0, c=(0.0, 0.0, -0.02), lr=0, sr=-4, hr=-6, sy=-10,
             wR=(0.42, -0.33, 1.30), kR=(0.3, 0.3, -1.0), pR=50.0, gR=1.0, giR=0.0, gtR=0.75, shR=8.0,
             **_side(HIPS, 'L'), hy=-14, hp=-6),
           K(f + B, wR=(0.30, -0.36, 1.36), c=(0.0, 0.0, -0.05)), K(f + 2 * B, wR=(0.42, -0.33, 1.30), c=(0.0, 0.0, -0.02)),
           K(f + 3 * B, c=(0.0, 0.0, -0.05))]
f = B * 13                                            # bar 4: three claps on the beat with knee bounces
for i in range(3):
    _dance += [K(f + i * B, w=(0.03, -0.29, 1.07), k=(1.0, 0.1, -0.6), p=-15.0, b=-10.0, g=0.05, gi=0.0, gt=0.1,
                 sh=0.0, c=(0.0, 0.0, -0.06), sr=0, sy=0, hy=0, hr=0, hp=4),
               K(f + i * B + 7, w=(0.17, -0.25, 1.09), c=(0.0, 0.0, -0.01), hp=-2)]
f = 238                                               # turn with the arms out, end in the heart
_dance += [K(f, turn=0, **TWIRL_ARMS, c=(0.0, 0.0, -0.02), tip=0),
           K(f + 7, turn=90, tip=12), K(f + 13, turn=200, tip=14), K(f + 19, turn=300, tip=10),
           K(f + 24, turn=360, tip=0, c=(0.0, 0.0, -0.03)),
           K(273, turn=360, **HEART, sr=-6, hr=9, tipL=20, fL=(0.0, -0.04, 0.0), c=(0.012, 0.0, -0.01)),
           K(280, turn=360, hr=11),
           K(288, turn=360, sr=0, hr=0, tipL=0, fL=(0.0, 0.0, 0.0), c=(0.0, 0.0, -0.006), w=(0.40, -0.10, 1.25),
             k=(0.8, 0.5, -0.6), p=-10.0, b=0.0, g=0.15),
           K(296, reset=True, turn=360), K(300, reset=True, turn=360)]
clip('idol_dance', 300, _dance, look=False,
     face=[(10, '笑い', 0), (20, '笑い', 1.0), (130, '笑い', 1.0), (140, '笑い', 0.3), (195, '笑い', 1.0), (290, '笑い', 1.0), (299, '笑い', 0),
           (135, 'ウィンク', 0), (140, 'ウィンク', 1.0), (175, 'ウィンク', 1.0), (182, 'ウィンク', 0), (290, 'ウィンク', 0),
          (15, 'ワ', 0), (22, 'ワ', 0.7), (60, 'ワ', 0.3), (75, 'ワ', 0.8), (120, 'ワ', 0.3), (135, 'ワ', 0), (195, 'ワ', 0), (202, 'ワ', 0.8), (240, 'ワ', 0.6), (270, 'ω', 0), (276, 'ω', 0.8), (296, 'ω', 0), (268, '照れ', 0), (276, '照れ', 0.6), (299, '照れ', 0)])

WEB_CLIPS = list(CLIPS)


# ------------------------------------------------------------------ registration

def _key_fn(c, frame):
    def key(arm):
        apply(arm, c.at(frame))
    return key


def _register():
    for name, c in CLIPS.items():
        if name in mp.CLIPS and not name.startswith('idol_dance'):
            raise ValueError(f'web clip {name} would replace a test clip')
        frames = list(range(0, c.frames, KEY_STEP)) + [c.frames]
        mp.CLIPS[('web_' + name) if name in mp.CLIPS else name] = (c.frames, [(f, _key_fn(c, f)) for f in frames])


# 'idol_dance' is also a test clip: the web one is registered as web_idol_dance (exported under that
# name and renamed by the manifest writer)
_register()


def manifest():
    """The web runtime's clips.json (names as the site uses them)."""
    return {'fps': FPS, 'clips': {n: MANIFEST[n] for n in WEB_CLIPS}}


def vmd_name(name):
    return ('web_' + name) if name == 'idol_dance' else name


if __name__ == '__main__':
    import json
    import sys
    out = sys.argv[sys.argv.index('--') + 1] if '--' in sys.argv else 'clips.json'
    with open(out, 'w', encoding='utf-8') as fh:
        json.dump(manifest(), fh, ensure_ascii=False, indent=1)
    print('wrote', out, len(WEB_CLIPS), 'clips')
