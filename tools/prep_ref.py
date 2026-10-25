"""Crop the three-view sheet into per-view panels and silhouette masks.

Run once (outputs are committed):
    blender -b --factory-startup -P tools/prep_ref.py [-- --regions-only]

Writes ref/{front,side,back}.png (RGB crop) and ref/{front,side,back}_mask.png
(white = character, black = background), each PANEL_W x PANEL_H, aligned so
that spec.panel_px() maps world coordinates onto them.

Then writes ref/{front,side,back}_regions.png: the character segmented into
levi.regions regions (skin / hair / dress / green / petticoat / shoe) by
nearest spec.PALETTE colour plus spatial priors, colour-coded with
regions.LABEL_RGB. --regions-only rebuilds just these from the committed
panels and masks (rerun it after retuning spec.PALETTE).
"""
import argparse
import os
import sys

import bpy
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from levi import regions, spec  # noqa: E402

CLOSE_PX = 3


def load_rgb(path):
    im = bpy.data.images.load(path)
    w, h = im.size
    a = np.array(im.pixels[:], dtype=np.float32).reshape(h, w, 4)[::-1, :, :3]
    bpy.data.images.remove(im)
    return a  # row 0 = top


def save_rgb(path, a):
    h, w = a.shape[:2]
    rgba = np.ones((h, w, 4), dtype=np.float32)
    rgba[:, :, :3] = a if a.ndim == 3 else a[:, :, None]
    im = bpy.data.images.new(os.path.basename(path), w, h, alpha=False)
    im.pixels[:] = rgba[::-1].ravel()
    im.filepath_raw = path
    im.file_format = 'PNG'
    im.save()
    bpy.data.images.remove(im)


def dilate(m):
    o = m.copy()
    o[1:] |= m[:-1]
    o[:-1] |= m[1:]
    o[:, 1:] |= m[:, :-1]
    o[:, :-1] |= m[:, 1:]
    return o


def grow(seed, allowed):
    cur = seed & allowed
    while True:
        nxt = dilate(cur) & allowed
        if (nxt == cur).all():
            return cur
        cur = nxt


def write_regions():
    for view in spec.VIEWS:
        rgb = load_rgb(os.path.join(ROOT, 'ref', f'{view}.png'))
        mask = load_rgb(os.path.join(ROOT, 'ref', f'{view}_mask.png'))[:, :, 0] > 0.5
        labels = regions.classify_reference(rgb, mask, view)
        save_rgb(os.path.join(ROOT, 'ref', f'{view}_regions.png'), regions.encode(labels))
        counts = {r: int((labels == regions.LABEL[r]).sum()) for r in regions.REGION_NAMES}
        counts['unknown'] = int((labels == regions.UNKNOWN).sum())
        print(view, 'regions px', counts)


def crop_panels():
    sheet = load_rgb(os.path.join(ROOT, 'ref', 'levi_threeview.png'))
    h, w = sheet.shape[:2]
    whiteish = sheet.min(axis=2) > 0.90
    # Labels live below the feet; never count them as character.
    whiteish[spec.SHEET_GROUND_Y + 8:, :] = True
    # Thicken the line art so the flood fill cannot leak through small gaps
    # in the strokes, then give the thickness back at the boundary.
    lines = ~whiteish
    for _ in range(CLOSE_PX):
        lines = dilate(lines)
    border = np.zeros_like(whiteish)
    border[0, :] = border[-1, :] = border[:, 0] = border[:, -1] = True
    bg = grow(border, ~lines)
    for _ in range(CLOSE_PX):
        bg = dilate(bg) & whiteish | bg
    fg = ~bg
    fg[spec.SHEET_GROUND_Y + 8:, :] = False

    # Assign foreground to panels by growing from a seed on each figure's legs,
    # then give leftovers to the nearest panel centre.
    owner = np.full((h, w), -1, dtype=np.int8)
    for i, view in enumerate(spec.VIEWS):
        cx = spec.SHEET_CENTER_X[view]
        seed = np.zeros_like(fg)
        seed[spec.SHEET_GROUND_Y - 260, cx - 30:cx + 30] = True
        region = grow(seed, fg & (owner < 0))
        owner[region] = i
    xs = np.arange(w)[None, :].repeat(h, 0)
    centers = np.array([spec.SHEET_CENTER_X[v] for v in spec.VIEWS])
    nearest = np.abs(xs[..., None] - centers[None, None, :]).argmin(-1)
    left = fg & (owner < 0)
    owner[left] = nearest[left]

    for i, view in enumerate(spec.VIEWS):
        cx = spec.SHEET_CENTER_X[view]
        x0 = cx - spec.PANEL_W // 2
        crop = np.ones((spec.PANEL_H, spec.PANEL_W, 3), dtype=np.float32)
        mask = np.zeros((spec.PANEL_H, spec.PANEL_W), dtype=np.float32)
        sx0, sx1 = max(x0, 0), min(x0 + spec.PANEL_W, w)
        mine = owner[:spec.PANEL_H, sx0:sx1] == i
        src = sheet[:spec.PANEL_H, sx0:sx1]
        dst = slice(sx0 - x0, sx1 - x0)
        crop[:, dst] = np.where(mine[..., None], src, 1.0)
        mask[:, dst] = mine
        save_rgb(os.path.join(ROOT, 'ref', f'{view}.png'), crop)
        save_rgb(os.path.join(ROOT, 'ref', f'{view}_mask.png'), mask)
        print(view, 'mask px', int(mask.sum()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--regions-only', action='store_true')
    args = ap.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
    if not args.regions_only:
        crop_panels()
    write_regions()


main()
