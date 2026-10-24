"""Compare renders against the three-view reference.

    blender -b --factory-startup -P tools/compare.py -- [--render out/render] [--out out/cmp]
                                                        [--views front,side,back]
                                                        [--box x0,y0,x1,y1]

For each view writes:
  <view>_overlay.png  reference and render blended 50/50
  <view>_diff.png     silhouette diff: grey = both, red = render only (too big),
                      blue = reference only (missing)
  <view>_sbs.png      reference | render side by side
and prints silhouette IoU (whole panel, and inside --box if given, panel pixels).
"""
import argparse
import os
import sys

import bpy
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from levi import spec  # noqa: E402


def load(path):
    im = bpy.data.images.load(path)
    im.colorspace_settings.name = 'sRGB'
    w, h = im.size
    a = np.array(im.pixels[:], dtype=np.float32).reshape(h, w, 4)[::-1]
    bpy.data.images.remove(im)
    return a


def save(path, rgb):
    h, w = rgb.shape[:2]
    rgba = np.ones((h, w, 4), dtype=np.float32)
    rgba[:, :, :3] = np.clip(rgb, 0, 1)
    im = bpy.data.images.new(os.path.basename(path), w, h, alpha=False)
    im.pixels[:] = rgba[::-1].ravel()
    im.filepath_raw = path
    im.file_format = 'PNG'
    im.save()
    bpy.data.images.remove(im)


def iou(a, b):
    u = (a | b).sum()
    return float((a & b).sum() / u) if u else 1.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--render', default='out/render')
    ap.add_argument('--out', default='out/cmp')
    ap.add_argument('--views', default=','.join(spec.VIEWS))
    ap.add_argument('--box', default='', help='x0,y0,x1,y1 panel pixels for a local IoU')
    args = ap.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
    out = os.path.join(ROOT, args.out)
    os.makedirs(out, exist_ok=True)

    for view in args.views.split(','):
        ref = load(os.path.join(ROOT, 'ref', f'{view}.png'))[:, :, :3]
        ref_m = load(os.path.join(ROOT, 'ref', f'{view}_mask.png'))[:, :, 0] > 0.5
        r = load(os.path.join(ROOT, args.render, f'{view}.png'))
        if r.shape[:2] != ref.shape[:2]:
            print(f'{view}: render size {r.shape[1]}x{r.shape[0]} != panel; use --scale 1')
            continue
        alpha = r[:, :, 3:4]
        rgb = r[:, :, :3] * alpha + (1 - alpha)  # over white
        ren_m = alpha[:, :, 0] > 0.5

        save(os.path.join(out, f'{view}_overlay.png'), 0.5 * ref + 0.5 * rgb)
        diff = np.ones_like(ref)
        diff[ref_m & ren_m] = (0.6, 0.6, 0.6)
        diff[ren_m & ~ref_m] = (0.9, 0.1, 0.1)
        diff[ref_m & ~ren_m] = (0.1, 0.3, 0.95)
        save(os.path.join(out, f'{view}_diff.png'), diff)
        save(os.path.join(out, f'{view}_sbs.png'), np.concatenate([ref, rgb], axis=1))

        line = f'IOU {view:5s} {iou(ref_m, ren_m):.4f}'
        if args.box:
            x0, y0, x1, y1 = map(int, args.box.split(','))
            line += f'  box {iou(ref_m[y0:y1, x0:x1], ren_m[y0:y1, x0:x1]):.4f}'
        print(line)


main()
