"""VMD round trip of the motion clips: Blender rig -> PMX + VMD -> Blender, bone by bone.

    blender -b out/levi.blend -P tools/motion_vmd.py -- [--pmx out/pmx/Levi.pmx]
                                [--clips walk,idol_dance,turn] [--out out/motion_vmd]
                                [--extra-clips web_clips]

Needs mmd_tools (no --factory-startup) and a PMX exported from the same build
(`export_pmx.py -- --out out/pmx/Levi.pmx`). For each clip of tools/motion_poses.py:
  1. the clip is keyed on the rigged .blend and every frame's world skinning matrix of each
     keyed bone (centre, IK targets, spine, arms, fingers, chains...) is recorded, with the
     world positions of the check bones (head, wrists, elbows, knees, ankles, toes, chest);
  2. the PMX is imported with mmd_tools (append / 付与 set up as pmx_reimport does) and the
     same motion is keyed on it, every frame, by PMX bone name (the IK targets drive the legs
     through mmd_tools' IK, like a VMD in MMD);
  3. exported as <out>/<clip>.vmd with mmd_tools, the keys cleared, the VMD imported back;
  4. compared per frame: VMD round trip (keyed PMX vs PMX + VMD, must stay within 2 mm),
     and Blender rig vs PMX + VMD (the PMX's evaluation of the same motion: IK solver, 付与);
     knees must bend forward in every frame; the shoulder helpers (SHOULDER) must not pop in
     the PMX playback (round 8: MMD's plain 付与 shares of 腕 flipped them past 180 deg).
MMD physics is not simulated here: the hair, skirt and sleeve chains are keyed bones in the
VMD and would be driven by rigid bodies in MMD, so their motion in MMD is not checked.
Writes <out>/vmd_report.md and .json. Exit code 1 if a round trip moves a bone > 2 mm, a
knee bends backward or a shoulder helper pops.
"""
import argparse
import importlib
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import motion_poses  # noqa: E402
import rig_pose  # noqa: E402

START = 1           # Blender frame of VMD frame 0 (as pmx_reimport.WALK_START)
CHECK = ('頭', '上半身2', '左手首', '右手首', '左ひじ', '右ひじ', '左ひざ', '右ひざ', '左足首', '右足首',
         '左つま先', '右つま先')
MAX_RT = 0.002      # m: VMD round trip
# shoulder helpers whose PMX evaluation is checked for pops (round 8: MMD's plain 付与 share of
# 腕 flipped them when 腕's turn passed 180 deg): the rest elbow carried by each one's skinning
# matrix, its acceleration frame to frame (m / frame^2) in the PMX + VMD playback
SHOULDER = ('左肩補助', '左肩補助2', '左肩補助3', '左腕D', '右肩補助', '右肩補助2', '右肩補助3', '右腕D')
MAX_SHOULDER_POP = 0.012   # m / frame^2: PMX shoulder helpers (or twice the Blender rig's, if more)
DEFAULT_CLIPS = 'walk,idol_dance,turn'


def record(arm, clip):
    """{frame: {name_j: world 4x4 skinning matrix}} for the keyed bones, and
    {frame: {name_j: world head}} for CHECK, of clip on our rig."""
    frames = motion_poses.build_clip(arm, clip)
    act = arm.animation_data.action
    keyed = [n for n in act.get('levi_bones', []) if arm.pose.bones[n].get('mmd_name_j')]
    jp = {pb.get('mmd_name_j'): pb for pb in arm.pose.bones if pb.get('mmd_name_j')}
    mw = arm.matrix_world
    mats, heads = {}, {}
    for f in range(frames + 1):
        bpy.context.scene.frame_set(f)
        bpy.context.view_layer.update()
        mats[f] = {arm.pose.bones[n]['mmd_name_j']: (mw @ arm.pose.bones[n].matrix @
                                                     arm.pose.bones[n].bone.matrix_local.inverted() @
                                                     mw.inverted()).copy() for n in keyed}
        heads[f] = {j: (mw @ jp[j].head).copy() for j in CHECK if j in jp}
        heads[f]['shoulder'] = _shoulder_points(jp, mw)
    motion_poses.clear_clip(arm)
    rig_pose.reset_pose(arm)
    return frames, mats, heads


def _mmd_pkg():
    for name in ('bl_ext.blender_org.mmd_tools', 'mmd_tools'):
        try:
            return importlib.import_module(name)
        except ImportError:
            pass
    return None


def _pbs(arm):
    return {pb.mmd_bone.name_j: pb for pb in arm.pose.bones if not pb.is_mmd_shadow_bone and pb.mmd_bone.name_j}


def _depth(pb):
    d = 0
    while pb.parent:
        pb, d = pb.parent, d + 1
    return d


def key_on_pmx(arm, frames, mats):
    """Key the recorded skinning matrices on the imported PMX armature, every frame."""
    pbs = _pbs(arm)
    names = sorted((j for j in mats[0] if j in pbs), key=lambda j: _depth(pbs[j]))
    missing = sorted(j for j in mats[0] if j not in pbs)
    mw = arm.matrix_world
    levels = sorted({_depth(pbs[j]) for j in names})
    for f in range(frames + 1):
        bpy.context.scene.frame_set(f + START)
        for pb in arm.pose.bones:
            pb.matrix_basis = Matrix.Identity(4)
        bpy.context.view_layer.update()
        for lv in levels:
            for j in names:
                pb = pbs[j]
                if _depth(pb) != lv:
                    continue
                pb.matrix = mw.inverted() @ mats[f][j] @ mw @ pb.bone.matrix_local
            bpy.context.view_layer.update()
        for j in names:
            pb = pbs[j]
            pb.rotation_mode = 'QUATERNION'
            pb.keyframe_insert('location', frame=f + START)
            pb.keyframe_insert('rotation_quaternion', frame=f + START)
    return names, missing


def _shoulder_points(pbs, mw):
    """{name_j: world point}: the rest elbow of its side carried by each SHOULDER bone."""
    out = {}
    for j in SHOULDER:
        el = pbs.get(j[0] + 'ひじ')
        if j in pbs and el is not None:
            pb = pbs[j]
            out[j] = (mw @ pb.matrix @ pb.bone.matrix_local.inverted() @ el.bone.head_local).copy()
    return out


def shoulder_pop(series, frames):
    """(worst acceleration m/frame^2, where) of the SHOULDER points over the frames."""
    worst, where = 0.0, ''
    for f in range(1, frames):
        for j, p in series[f]['shoulder'].items():
            a, c = series[f - 1]['shoulder'].get(j), series[f + 1]['shoulder'].get(j)
            if a is not None and c is not None:
                acc = (a - 2 * p + c).length
                if acc > worst:
                    worst, where = acc, f'{j} @ {f}'
    return worst, where


def sample(arm, frames):
    pbs = _pbs(arm)
    mw = arm.matrix_world
    out = {}
    for f in range(frames + 1):
        bpy.context.scene.frame_set(f + START)
        bpy.context.view_layer.update()
        out[f] = {j: (mw @ pbs[j].head).copy() for j in CHECK if j in pbs}
        out[f]['knee'] = [_knee(pbs, s, mw) for s in '左右']
        out[f]['shoulder'] = _shoulder_points(pbs, mw)
    return out


def _knee(pbs, side, mw):
    hip, knee, ankle = (mw @ pbs[f'{side}{n}'].head for n in ('足', 'ひざ', '足首'))
    ang = math.degrees((knee - hip).angle(ankle - knee, 0.0))
    d = ankle - hip
    t = (knee - hip).dot(d) / max(d.length_squared, 1e-12)
    off = knee - (hip + d * t)
    # forward = the way the pelvis faces (-Y turned with the hips)
    fwd = (mw.to_3x3() @ pbs['下半身'].matrix.to_3x3() @ pbs['下半身'].bone.matrix_local.to_3x3().inverted()
           @ Vector((0, -1, 0)))
    return ang if off.dot(fwd) >= -1e-4 or ang < 1.0 else -ang


def compare(a, b, frames):
    worst, where = 0.0, ''
    for f in range(frames + 1):
        for j in CHECK:
            if j in a[f] and j in b[f]:
                e = (a[f][j] - b[f][j]).length
                if os.environ.get('LEVI_DEBUG_VMD') and e > 0.002:
                    print('VMDDBG', f, j, round(e * 1000, 1))
                if e > worst:
                    worst, where = e, f'{j} @ {f}'
    return worst, where


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pmx', default='out/pmx/Levi.pmx')
    ap.add_argument('--clips', default=DEFAULT_CLIPS)
    ap.add_argument('--out', default='out/motion_vmd')
    ap.add_argument('--extra-clips', default='', help='modules in tools/ that add clips to motion_poses.CLIPS '
                    '(e.g. web_clips; the same as LEVI_EXTRA_CLIPS)')
    args = ap.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
    for mod in filter(None, args.extra_clips.split(',')):
        importlib.import_module(mod.strip())
    pkg = _mmd_pkg()
    if pkg is None:
        print('FAIL mmd_tools not available')
        sys.exit(1)
    out = os.path.join(ROOT, args.out)
    os.makedirs(out, exist_ok=True)
    arm = next((o for o in bpy.data.objects if o.type == 'ARMATURE'), None)
    if arm is None:
        print('FAIL no rigged model loaded (blender -b out/levi.blend -P tools/motion_vmd.py)')
        sys.exit(1)
    clips = [c for c in args.clips.split(',') if c]
    rec = {c: record(arm, c) for c in clips}
    print('RECORDED', ', '.join(f'{c} ({rec[c][0] + 1} frames, {len(rec[c][1][0])} keyed bones)' for c in clips))

    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    path = os.path.join(ROOT, args.pmx)
    bpy.ops.mmd_tools.import_model(filepath=path, scale=1.0 / 12.5, types={'MESH', 'ARMATURE', 'DISPLAY'},
                                   log_level='WARNING')
    parm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
    importlib.import_module(pkg.__name__ + '.core.bone').FnBone.apply_additional_transformation(parm)
    for o in bpy.context.view_layer.objects:
        o.select_set(o == parm)
    bpy.context.view_layer.objects.active = parm

    errors, rows = [], []
    for c in clips:
        frames, mats, heads = rec[c]
        names, missing = key_on_pmx(parm, frames, mats)
        keyed = sample(parm, frames)
        vmd = os.path.join(out, f'{c}.vmd')
        sc = bpy.context.scene      # mmd_tools writes VMD frames relative to the scene start
        sc.frame_start, sc.frame_end = START, frames + START
        bpy.ops.mmd_tools.export_vmd(filepath=vmd, scale=12.5, log_level='WARNING')
        parm.animation_data_clear()
        for pb in parm.pose.bones:
            pb.matrix_basis = Matrix.Identity(4)
        bpy.context.scene.frame_set(START)
        bpy.ops.mmd_tools.import_vmd(filepath=vmd, scale=1.0 / 12.5, bone_mapper='PMX', log_level='WARNING')
        got = sample(parm, frames)
        rt, rt_at = compare(keyed, got, frames)
        rg, rg_at = compare(heads, got, frames)
        knee = min(min(got[f]['knee']) for f in got)
        sp_rig, sp_rig_at = shoulder_pop(heads, frames)
        sp_pmx, sp_pmx_at = shoulder_pop(got, frames)
        # VMD stores bone names in 15 bytes of Shift-JIS: longer PMX names cannot be keyed
        long_names = sorted(j for j in names if len(j.encode('cp932', 'replace')) > 15)
        row = dict(clip=c, frames=frames + 1, keyed_bones=len(names), unmapped=missing, vmd_name_too_long=long_names,
                   vmd_bytes=os.path.getsize(vmd), roundtrip_mm=round(rt * 1000, 3), roundtrip_at=rt_at,
                   rig_vs_pmx_mm=round(rg * 1000, 2), rig_vs_pmx_at=rg_at, least_knee_deg=round(knee, 1),
                   shoulder_pop_rig_mm=round(sp_rig * 1000, 1), shoulder_pop_rig_at=sp_rig_at,
                   shoulder_pop_pmx_mm=round(sp_pmx * 1000, 1), shoulder_pop_pmx_at=sp_pmx_at)
        rows.append(row)
        print(f'VMD {c}: {frames + 1} frames, {len(names)} bones keyed, round trip {rt * 1000:.2f} mm ({rt_at}), '
              f'Blender rig vs PMX+VMD {rg * 1000:.1f} mm ({rg_at}), least knee bend {knee:.1f} deg, '
              f'shoulder helper accel rig {sp_rig * 1000:.1f} ({sp_rig_at}) / PMX {sp_pmx * 1000:.1f} mm/f^2 ({sp_pmx_at})'
              + (f', not in the PMX: {missing}' if missing else '')
              + (f', names too long for VMD (> 15 bytes): {long_names}' if long_names else ''))
        if rt > MAX_RT:
            errors.append(f'{c}: VMD round trip moves {rt_at} by {rt * 1000:.1f} mm')
        if knee < -0.5:
            errors.append(f'{c}: a knee bends backward ({knee:.1f} deg) after the VMD import')
        if sp_pmx > max(MAX_SHOULDER_POP, 2.0 * sp_rig):
            errors.append(f'{c}: a PMX shoulder helper pops ({sp_pmx_at}: {sp_pmx * 1000:.1f} mm/frame^2, '
                          f'Blender rig {sp_rig * 1000:.1f})')
        parm.animation_data_clear()
        for pb in parm.pose.bones:
            pb.matrix_basis = Matrix.Identity(4)
    lines = ['# VMD round trip of the motion clips', '',
             'Clips keyed on the Blender rig, retargeted by PMX bone name onto the mmd_tools import of the '
             'exported PMX (every frame), exported as VMD, re-imported and compared bone by bone '
             f'({", ".join(CHECK)}). MMD physics is not simulated: hair, skirt and sleeve chains are keyed '
             'bones here, rigid bodies in MMD.', '',
             'Shoulder: the worst frame-to-frame acceleration of the rest elbow carried by 肩補助 / 肩補助2 / '
             '肩補助3 / 腕D (mm / frame^2), on the Blender rig and in the PMX + VMD playback (a pop is a spike).', '',
             '| clip | frames | keyed bones | VMD KB | round trip mm (where) | rig vs PMX+VMD mm (where) | least knee deg '
             '| shoulder accel rig (where) | shoulder accel PMX (where) |',
             '|---|---|---|---|---|---|---|---|---|']
    for r in rows:
        lines.append(f"| {r['clip']} | {r['frames']} | {r['keyed_bones']} | {r['vmd_bytes'] // 1024} | "
                     f"{r['roundtrip_mm']:.2f} ({r['roundtrip_at']}) | {r['rig_vs_pmx_mm']:.1f} ({r['rig_vs_pmx_at']}) | "
                     f"{r['least_knee_deg']:.1f} | {r['shoulder_pop_rig_mm']:.1f} ({r['shoulder_pop_rig_at']}) | "
                     f"{r['shoulder_pop_pmx_mm']:.1f} ({r['shoulder_pop_pmx_at']}) |")
    longs = sorted({j for r in rows for j in r['vmd_name_too_long']})
    if longs:
        lines += ['', f'{len(longs)} keyed PMX bones have names longer than the 15 bytes (Shift-JIS) a VMD '
                  'key can hold, so mmd_tools truncates them and no VMD can drive them (they are physics or '
                  'append-driven in MMD, so only hand-keyed motion of them is lost): ' + ', '.join(longs)]
    lines += [''] + [f'FAIL {e}' for e in errors] + ['VMD ROUND TRIP ' + ('FAILED' if errors else 'OK')]
    with open(os.path.join(out, 'vmd_report.md'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
    with open(os.path.join(out, 'vmd_report.json'), 'w', encoding='utf-8') as f:
        json.dump(rows, f, indent=1, ensure_ascii=False)
    print('\n'.join(lines))
    sys.exit(1 if errors else 0)


if __name__ == '__main__':
    main()
