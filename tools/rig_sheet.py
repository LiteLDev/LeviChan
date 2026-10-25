"""Tile per-pose renders into one front | side | back sheet per pose.

    blender -b --factory-startup -P tools/rig_sheet.py -- --dir out/poses --out docs/pr/r2-rig [--scale 0.5]

--dir holds one sub-folder per pose with render.py's front.png / side.png / back.png
(see the pose-render loop in CLAUDE.md); writes <out>/<pose>.png. Only bpy + numpy.
"""
import argparse
import os
import sys

import bpy
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIEWS = ('front', 'side', 'back')


def load(path):
    img = bpy.data.images.load(path)
    w, h = img.size
    px = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    return px.reshape(h, w, 4)


def shrink(a, scale):
    step = max(1, int(round(1.0 / scale)))
    if step == 1:
        return a
    h, w = (a.shape[0] // step) * step, (a.shape[1] // step) * step
    return a[:h, :w].reshape(h // step, step, w // step, step, 4).mean((1, 3))


def save(a, path):
    h, w = a.shape[:2]
    img = bpy.data.images.new(os.path.basename(path), w, h, alpha=True)
    img.pixels.foreach_set(np.ascontiguousarray(a, dtype=np.float32).ravel())
    img.filepath_raw = path
    img.file_format = 'PNG'
    img.save()
    bpy.data.images.remove(img)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', default='out/poses')
    ap.add_argument('--out', default='out/poses/sheets')
    ap.add_argument('--scale', type=float, default=1.0)
    args = ap.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
    src, out = os.path.join(ROOT, args.dir), os.path.join(ROOT, args.out)
    os.makedirs(out, exist_ok=True)
    for pose in sorted(os.listdir(src)):
        files = [os.path.join(src, pose, f'{v}.png') for v in VIEWS]
        if not all(os.path.isfile(f) for f in files):
            continue
        tiles = [shrink(load(f), args.scale) for f in files]
        h = min(t.shape[0] for t in tiles)
        gap = np.ones((h, 4, 4), dtype=np.float32)
        row = [tiles[0][:h]]
        for t in tiles[1:]:
            row += [gap, t[:h]]
        path = os.path.join(out, f'{pose}.png')
        save(np.concatenate(row, axis=1), path)
        print('SHEET', path)


main()
