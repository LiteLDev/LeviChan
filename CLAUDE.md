# LeviChan — procedural Levi model

Levi is modeled **from scratch** with Blender Python (`bpy` + `bmesh`), about 30k faces. The cel-shaded orthographic renders must line up with the three-view `ref/levi_threeview.png`: FRONT / SIDE / BACK. No geometry is imported from other models; the old Nahida-based model under `ref/legacy/` is a visual reference only.

Blender: `C:/Program Files/Blender Foundation/Blender 5.2/blender.exe` (written as `$B` below). numpy is bundled; PIL and scipy are not.

## Layout
- `levi/spec.py`: the single source of truth.
  - Sheet ↔ world calibration and the `panel_px()` mapping.
  - Measured landmarks `spec.L[...]`.
  - Colour palette (base / shade / line per key).
  - Per-part face budgets.
- `levi/toon.py`: `toon_material(key, gradient=None)` gives the two-tone cel material. `add_outline(obj)` adds an inverted-hull outline.
- `levi/common.py`: helpers for parts — `part_collection`, `new_object`, `loft`, `ellipse_ring`, `tube_along`, `mirror_x`, `subsurf`, `apply_modifiers`, `set_gradient`, `z_gradient`, `shade_smooth`, `face_count`.
- `levi/parts/<name>.py`: one module per part, each exposing `build(col)`. They are discovered automatically; files starting with `_` are private helpers.
- `levi/regions.py`: colour regions (skin / hair / dress / green / petticoat / shoe), each a group of palette keys, used by `prep_ref.py`, `render.py` and `compare.py`.
- `levi/proxy.py`: a grey stand-in body (`--proxy`) that gives context before the real body exists.
- `build.py`, `render.py`, `tools/compare.py`, `tools/check.py`: the pipeline. `tools/prep_ref.py` regenerates `ref/<view>.png`, `ref/<view>_mask.png` and `ref/<view>_regions.png`.

## Coordinates
- Metres, Z up, the character faces −Y, and the origin is on the ground between the feet. +X is the character's left, which is image-right in the front view.
- The side view looks from +X, so the character faces image-left.
- One panel pixel is `1/643` m. `spec.panel_px(view, p)` maps a world point to a reference pixel.

## Pipeline
```
"$B" -b -P build.py -- --out out/levi.blend [--parts body,skirt] [--proxy]
"$B" -b out/levi.blend -P render.py -- --out out/render [--hide _proxy] [--views front,side,back] [--shadows] [--freestyle] [--no-regions]
"$B" -b --factory-startup -P tools/compare.py -- --render out/render --out out/cmp [--box x0,y0,x1,y1] [--part-region dress,petticoat]
"$B" -b -P tools/check.py -- [--parts body,skirt]      # exit code 1 on failure
```
`out/cmp/<view>_{overlay,diff,sbs}.png`:
- In the diff, red = render sticks out and blue = reference not covered.
- The tool also prints IoU against the reference silhouette.
- It also prints one `REGION <view> <region> iou .. dE ..` line per region. IoU compares `ref/<view>_regions.png` with the render's `<view>_regions.png`, which `render.py` writes from the materials' palette keys. dE is the mean CIE76 colour error over pixels both images give that region.
- `--part-region skin,hair` reports only those regions and writes `<view>_region_<name>.png` diffs.
- The reference regions come from colour plus spatial priors, so they are noisy where colours coincide. Mint hair tips read as mint cloth, and skin vs petticoat is decided by position. Use the region IoU for trends, not as an absolute score.

## Look-dev (cel shading)
- Light: one sun per view, placed relative to that view's camera. It comes from the viewer's upper left, nearly frontal (`render.SUN_AZIMUTH_DEG` / `SUN_ELEVATION_DEG`), so front, side and back are all mostly lit like the sheet.
- The world is black and the sun strength is π, so the toon ramp sees pure N·L in 0..1. Below `toon.RAMP_THRESHOLD` a surface takes the single shade tone: turned-away sides and undersides of hems, chin and strands.
- Cast shadows are off by default. Shadow maps give blocky self-shadow patches on medium-poly and custom-normal meshes, and the sheet has none. `render.py --shadows` turns them on for experiments.
- Colour: Standard view transform, no look, no dither. A flat lit surface renders exactly its `spec.PALETTE` `base` hex, and a shaded one exactly its `shade` hex (0/255 error). Renders are pixel- and byte-identical across runs.
- The palette was sampled from the sheet. If you need a different colour, ask for a palette change rather than adding a new material.
- Outlines: an inverted hull `spec.OUTLINE_WIDTH` thick (`OUTLINE_PX` = 1.25 panel px, which renders as about 1.25 px lines) in the key's `line` colour.
  - The hull material never casts shadows: it is transparent to shadow rays and back-face culled for shadows.
  - Parts no longer need `obj.visible_shadow = False` or private no-shadow outline materials. Drop those workarounds; leaving `visible_shadow = False` is harmless, but it would stop the object from casting shadows under `--shadows`.
  - Open single-sided sheets work with normals facing either way: with backface culling, the hull never covers the fill.
  - A hull only draws silhouettes, so the open border of a sheet that faces the camera gets no line. If a border line matters, give the sheet a little thickness or use `render.py --freestyle` (1 px crease and open-border lines in each material's line colour).

## Part rules
- A part only adds objects to the `col` passed to `build(col)`. It must not read or modify other parts' objects; align to `spec.L` landmarks instead.
- Materials always come from `toon_material`. Every visible mesh gets `add_outline` unless it sets `obj["no_outline"] = True` (e.g. eye decals).
- Stay within `spec.BUDGET[part]`, which counts evaluated faces excluding the outline hull.
- Builds must be deterministic and repeatable. No randomness without a fixed seed.
- Don't edit `spec.py`, `common.py`, `toon.py` or another part from a part PR. If a landmark is off, put a local correction in your part and explain it in the PR.
- Never commit `.blend` files or `out/`. PR screenshots go under `docs/pr/<part>/`.
- No Claude/AI attribution in commits or PRs.
