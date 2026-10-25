"""Compare renders against the three-view reference.

    blender -b --factory-startup -P tools/compare.py -- [--render out/render] [--out out/cmp]
                                                        [--views front,side,back]
                                                        [--box x0,y0,x1,y1]
                                                        [--part-region skin,hair]

For each view writes:
  <view>_overlay.png  reference and render blended 50/50
  <view>_diff.png     silhouette diff: grey = both, red = render only (too big),
                      blue = reference only (missing)
  <view>_sbs.png      reference | render side by side
  <view>_regions_sbs.png  reference regions | render regions (levi.regions colours)
and prints silhouette IoU (whole panel, and inside --box if given, panel pixels).

Per-region report (one REGION line per view and region):
  iou   overlap of ref/<view>_regions.png and the render's region labels
  tol   overlap forgiving up to regions.TOL_PX px of misplacement (thin
        zones like ribbons: low iou but high tol = aligned but offset)
  dE    mean CIE76 colour difference, render vs reference, over the pixels
        both label as that region (shading included, so ~5-10 is typical
        for a good match; >15 means wrong palette or lit/shade balance)
  shade share of the region's pixels in a shade tone (nearest palette
        base vs shade), reference vs render: the lit/shade balance
  ref / ren   mean sRGB colour of the region in each image
  dEi   interior dE: like dE, but only over pixels at least CORE_PX px inside
        the region in both images (no line art, anti-aliasing or thin-zone
        misplacement), with that pixel count: the palette / ramp comparison
Render labels come from <render>/<view>_regions.png (written by render.py);
renders without it are classified by colour like the reference (approximate).
Green below the ankles is folded into shoe on both sides (regions.fold_feet).
Outline hulls take their palette key's region, also on gradient materials
(e.g. a hair->hair_tip strand's hull is labelled hair along its green tip).
--part-region restricts the report to the listed regions (and --box, if
given) and writes <view>_region_<name>.png diffs (grey = both, red = render
only, blue = reference only) so a part worker can check just their zone.
"""
import argparse
import os
import sys

import bpy
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from levi import regions, spec  # noqa: E402


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


def diff_image(ref_m, ren_m):
    diff = np.ones(ref_m.shape + (3,), dtype=np.float32)
    diff[ref_m & ren_m] = (0.6, 0.6, 0.6)
    diff[ren_m & ~ref_m] = (0.9, 0.1, 0.1)
    diff[ref_m & ~ren_m] = (0.1, 0.3, 0.95)
    return diff


def hexs(c):
    return '#%02X%02X%02X' % tuple(int(round(v * 255)) for v in np.clip(c, 0, 1))


CORE_PX = 2


def region_report(view, ref, rgb, ref_lbl, ren_lbl, names, box, out):
    """Print per-region IoU / colour error; returns {name: (iou, dE)}."""
    valid = (ref_lbl != regions.UNKNOWN) & (ren_lbl != regions.UNKNOWN)
    if box is not None:
        x0, y0, x1, y1 = box
        inside = np.zeros_like(valid)
        inside[y0:y1, x0:x1] = True
        valid &= inside
    res = {}
    for name in names:
        k = regions.LABEL[name]
        a = (ref_lbl == k) & valid
        b = (ren_lbl == k) & valid
        both = a & b
        if not (a.any() or b.any()):
            continue
        de = float(regions.delta_e(ref[both], rgb[both]).mean()) if both.any() else float('nan')
        # Interior colour error: only pixels >= CORE_PX inside the region in
        # both images, so line art, anti-aliasing and a 1-2 px misplacement
        # of thin zones (ribbons) do not swamp the palette comparison.
        core = both & ~regions.dilate(~a, CORE_PX) & ~regions.dilate(~b, CORE_PX)
        dei = float(regions.delta_e(ref[core], rgb[core]).mean()) if core.any() else float('nan')
        ref_c = hexs(ref[a].mean(0)) if a.any() else '-------'
        ren_c = hexs(rgb[b].mean(0)) if b.any() else '-------'
        sh_ref = regions.shade_share(ref, np.where(a, k, 0), name, spec.SHEET_PALETTE)[0]
        sh_ren = regions.shade_share(rgb, np.where(b, k, 0), name)[0]
        res[name] = (iou(a, b), de)
        print(f'REGION {view:5s} {name:9s} iou {res[name][0]:.4f}  tol {regions.tolerant_overlap(a, b):.4f}  '
              f'dE {de:5.1f}  shade ref {sh_ref:.2f} ren {sh_ren:.2f}  '
              f'ref {ref_c} ren {ren_c}  px ref {int(a.sum())} ren {int(b.sum())}  '
              f'dEi {dei:5.1f} px {int(core.sum())}')
        if out:
            save(os.path.join(out, f'{view}_region_{name}.png'), diff_image(a, b))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--render', default='out/render')
    ap.add_argument('--out', default='out/cmp')
    ap.add_argument('--views', default=','.join(spec.VIEWS))
    ap.add_argument('--box', default='', help='x0,y0,x1,y1 panel pixels for a local IoU')
    ap.add_argument('--part-region', default='',
                    help=f'comma-separated regions to report ({",".join(regions.REGION_NAMES)})')
    args = ap.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
    out = os.path.join(ROOT, args.out)
    os.makedirs(out, exist_ok=True)
    try:
        part_ids = regions.parse_regions(args.part_region)
    except ValueError as e:
        print('ERROR', e)
        sys.exit(2)
    names = [regions.REGION_NAMES[i - 1] for i in part_ids] or list(regions.REGION_NAMES)
    box = tuple(map(int, args.box.split(','))) if args.box else None

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
        save(os.path.join(out, f'{view}_diff.png'), diff_image(ref_m, ren_m))
        save(os.path.join(out, f'{view}_sbs.png'), np.concatenate([ref, rgb], axis=1))

        line = f'IOU {view:5s} {iou(ref_m, ren_m):.4f}'
        if box:
            x0, y0, x1, y1 = box
            line += f'  box {iou(ref_m[y0:y1, x0:x1], ren_m[y0:y1, x0:x1]):.4f}'
        print(line)

        ref_reg_path = os.path.join(ROOT, 'ref', f'{view}_regions.png')
        if not os.path.exists(ref_reg_path):
            print(f'{view}: no {ref_reg_path}; run tools/prep_ref.py -- --regions-only')
            continue
        ref_lbl = regions.decode(load(ref_reg_path)[:, :, :3])
        ref_lbl[~ref_m] = regions.BG
        ren_reg_path = os.path.join(ROOT, args.render, f'{view}_regions.png')
        if os.path.exists(ren_reg_path):
            rr = load(ren_reg_path)
            ren_lbl = regions.fold_feet(regions.decode(rr[:, :, :3], rr[:, :, 3]))
        else:
            print(f'{view}: no {view}_regions.png in render dir; classifying render by colour (approximate)')
            ren_lbl = regions.classify_reference(rgb, ren_m, view)
        save(os.path.join(out, f'{view}_regions_sbs.png'),
             np.concatenate([regions.encode(ref_lbl), regions.encode(ren_lbl)], axis=1))
        region_report(view, ref, rgb, ref_lbl, ren_lbl, names, box,
                      out if args.part_region else None)


main()
