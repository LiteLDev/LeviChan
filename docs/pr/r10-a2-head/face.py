"""Render a .blend with optional morphs through render.py (cel, or --clay). Run from the repo root:
blender -b X.blend -P docs/pr/r10-a2-head/face.py -- --out DIR [--morph NAME=V,...] [render.py args...]
(the A/B used --views front,q34_front_left,side,turn_020 --scale 4 --no-regions, crops in ab_face.BOX)"""
import os, sys, runpy
import bpy
argv = sys.argv[sys.argv.index('--') + 1:]
morph = ''
if '--morph' in argv:
    i = argv.index('--morph'); morph = argv[i + 1]; del argv[i:i + 2]
for item in filter(None, morph.split(',')):
    name, v = item.rsplit('=', 1)
    n = 0
    for o in bpy.data.objects:
        kb = o.data.shape_keys.key_blocks.get(name) if o.type == 'MESH' and o.data.shape_keys else None
        if kb:
            kb.value = float(v); n += 1
    print('MORPH', name, v, 'on', n, 'objects')
ROOT = os.getcwd()
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'tools'))
sys.argv = [sys.argv[0], '--'] + argv
runpy.run_path(os.path.join(ROOT, 'render.py'), run_name='__main__')
