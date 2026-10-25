"""Re-import an exported PMX with mmd_tools and check nothing was lost. Exit 1 on failure.

    blender -b -P tools/pmx_reimport.py -- [--pmx out/pmx/Levi.pmx] [--save out/pmx/reimport.blend]

Compares against <pmx>.json written by export_pmx.py: bone, material, rigid body
and joint counts; that every bone has a Japanese and an English name; that the
leg/toe IK bones are IK in the file; that vertex count in Blender after import
equals the PMX vertex count and every vertex is weighted. Saves a .blend that
render.py can render.
"""
import argparse
import importlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pmx', default='out/pmx/Levi.pmx')
    ap.add_argument('--save', default='out/pmx/reimport.blend')
    args = ap.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
    path = os.path.join(ROOT, args.pmx)
    with open(os.path.splitext(path)[0] + '.json', encoding='utf-8') as f:
        expect = json.load(f)

    pkg = None
    for name in ('bl_ext.blender_org.mmd_tools', 'mmd_tools'):
        try:
            pkg = importlib.import_module(name)
            break
        except ImportError:
            pass
    if pkg is None:
        print('FAIL mmd_tools not available')
        sys.exit(1)
    pmx = importlib.import_module(pkg.__name__ + '.core.pmx').load(path)

    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.ops.mmd_tools.import_model(filepath=path, scale=1.0 / 12.5,
                                   types={'MESH', 'ARMATURE', 'PHYSICS', 'DISPLAY', 'MORPHS'}, log_level='WARNING')

    errors = []

    def same(label, got, want):
        print(f'{label:14s} file={got} expected={want}')
        if got != want:
            errors.append(f'{label}: {got} != {want}')

    same('bones', len(pmx.bones), expect['bones'])
    same('materials', len(pmx.materials), expect['materials'])
    same('rigid_bodies', len(pmx.rigids), expect['rigid_bodies'])
    same('joints', len(pmx.joints), expect['joints'])
    for b in pmx.bones:
        if not b.name or not b.name_e:
            errors.append(f'bone {b.name!r}/{b.name_e!r} missing a name')
    ik = sorted(b.name for b in pmx.bones if b.isIK)
    print('IK bones', ik)
    for want in ('左足ＩＫ', '右足ＩＫ', '左つま先ＩＫ', '右つま先ＩＫ'):
        if want not in ik:
            errors.append(f'{want} is not an IK bone in the PMX')

    arms = [o for o in bpy.data.objects if o.type == 'ARMATURE']
    meshes = [o for o in bpy.data.objects if o.type == 'MESH' and getattr(o, 'mmd_type', 'NONE') == 'NONE']
    same('blender bones', len(arms[0].data.bones) if arms else 0, expect['bones'])
    nv = sum(len(o.data.vertices) for o in meshes)
    same('vertices', nv, len(pmx.vertices))
    nmat = sum(len(o.data.materials) for o in meshes)
    same('blender mats', nmat, expect['materials'])
    unweighted = 0
    for o in meshes:
        for v in o.data.vertices:
            if not any(g.weight > 0 for g in v.groups):
                unweighted += 1
    if unweighted:
        errors.append(f'{unweighted} vertices without weights after reimport')
    rb = [o for o in bpy.data.objects if getattr(o, 'mmd_type', '') == 'RIGID_BODY']
    same('blender rigid', len(rb), expect['rigid_bodies'])

    if args.save:
        out = os.path.join(ROOT, args.save)
        bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
        print('SAVED', out)
    for e in errors:
        print('FAIL', e)
    print('REIMPORT', 'FAILED' if errors else 'OK')
    sys.exit(1 if errors else 0)


main()
