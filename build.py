"""Build Levi from scratch into a .blend.

    blender -b -P build.py -- [--out out/levi.blend] [--parts body,skirt] [--proxy] [--rig]

--rig adds the MMD armature (levi/rig.py) and skins every part to it.
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402

from levi import builder, common  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='out/levi.blend')
    ap.add_argument('--parts', default='', help='comma-separated part names (default: all)')
    ap.add_argument('--proxy', action='store_true', help='add the grey stand-in body for context')
    ap.add_argument('--rig', action='store_true', help='build the MMD armature and skin the parts')
    args = ap.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])

    names = [p for p in args.parts.split(',') if p]
    cols = builder.build_all(names, with_proxy=args.proxy)
    total = 0
    for name, col in cols.items():
        n = common.face_count(col.all_objects)
        total += 0 if name.startswith('_') else n
        print(f'PART {name:12s} faces={n}')
    print(f'TOTAL faces={total}')
    if args.rig:
        from levi import rig
        arm = rig.build_rig()
        print(f'RIG bones={len(arm.data.bones)}')

    out = os.path.join(ROOT, args.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    print('SAVED', out)


main()
