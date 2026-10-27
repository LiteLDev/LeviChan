# blender -b --factory-startup -P ab_pairs.py -- plan.json : writes each plan entry's side-by-side image
import json, os, sys
import bpy
import numpy as np
plan = json.load(open(sys.argv[sys.argv.index('--') + 1], encoding='utf-8'))


def load(p):
    im = bpy.data.images.load(os.path.abspath(p))
    w, h = im.size
    x = np.array(im.pixels[:], dtype=np.float32).reshape(h, w, 4)[::-1]
    bpy.data.images.remove(im)
    al = x[:, :, 3:4]
    return x[:, :, :3] * al + (1 - al)


def crop_content(a, b, pad=20):
    m = (a.min(2) < 0.99) | (b.min(2) < 0.99)
    ys, xs = np.nonzero(m)
    y0, y1 = max(0, ys.min() - pad), min(a.shape[0], ys.max() + pad)
    x0, x1 = max(0, xs.min() - pad), min(a.shape[1], xs.max() + pad)
    return a[y0:y1, x0:x1], b[y0:y1, x0:x1]


for p in plan:
    a, b = load(p['left']), load(p['right'])
    if p['box'] == 'top':           # the upper part of the posed figure (head, shoulders, arms)
        a, b = crop_content(a, b)
        h = int(a.shape[0] * 0.5)
        a, b = a[:h], b[:h]
    elif p['box']:
        x0, y0, x1, y1 = p['box']
        a, b = a[y0:y1, x0:x1], b[y0:y1, x0:x1]
    else:
        a, b = crop_content(a, b)
    gap = np.zeros((a.shape[0], 8, 3), np.float32)
    img = np.concatenate([a, gap, b], 1)
    H, W = img.shape[:2]
    rgba = np.concatenate([img, np.ones((H, W, 1), np.float32)], 2)
    o = bpy.data.images.new('o', W, H)
    o.pixels[:] = rgba[::-1].ravel()
    o.filepath_raw = p['image']
    o.file_format = 'PNG'
    o.save()
    bpy.data.images.remove(o)
print('PAIRS', len(plan))
