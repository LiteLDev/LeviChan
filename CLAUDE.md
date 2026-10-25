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
"$B" -b out/levi.blend -P render.py -- --out out/render [--hide _proxy] [--views front,side,back] [--no-shadows] [--freestyle] [--no-regions] [--sun AZ,EL] [--ramp T] [--ramp-key KEY=T,...]
"$B" -b --factory-startup -P tools/compare.py -- --render out/render --out out/cmp [--box x0,y0,x1,y1] [--part-region dress,petticoat]
"$B" -b -P tools/check.py -- [--parts body,skirt]      # exit code 1 on failure
"$B" -b -P build.py -- --rig ...                         # + MMD armature, skinned (levi/rig.py)
"$B" -b -P tools/rig_check.py                            # rig tests, exit code 1 on failure
"$B" -b -P tools/rig_pose.py -- --out out/levi_pose.blend  # test pose for render.py
"$B" -b -P export_pmx.py -- --out out/pmx/Levi.pmx       # needs mmd_tools: no --factory-startup
"$B" -b -P tools/pmx_reimport.py                         # re-import + count check
```
The body part may store fitted limb joints for the rig as `obj["levi_joints"] = {"elbow": (x, y, z), ...}`
(left side, +X; keys in `rig.JOINT_KEYS`). Without it the rig fits joints to the body mesh.
`out/cmp/<view>_{overlay,diff,sbs}.png`:
- In the diff, red = render sticks out and blue = reference not covered.
- The tool also prints IoU against the reference silhouette.
- It also prints one `REGION <view> <region> iou .. tol .. dE .. shade ref .. ren ..` line per region. IoU compares `ref/<view>_regions.png` with the render's `<view>_regions.png`, which `render.py` writes from the materials' palette keys. dE is the mean CIE76 colour error over pixels both images give that region.
  - `tol` forgives up to 2 px of misplacement. For thin zones (ribbons, laces) a low `iou` with a high `tol` means aligned but offset; a low `tol` means missing or misplaced parts.
  - `shade` is the share of the region painted in a shade tone (nearest palette base vs shade) in the sheet and in the render: the lit/shade balance look-dev tunes.
- `--part-region skin,hair` reports only those regions and writes `<view>_region_<name>.png` diffs.
- The reference regions come from colour plus spatial priors (`levi/regions.py`):
  - The pale regions (hair / dress / skin) are grouped into components bounded by the sheet's line art, and each component takes its majority label. This removes most speckle from highlights and painted shading.
  - The hair's white-to-mint gradient is sampled too (`regions.GRADIENTS`), so half-mint strands read as hair, not mint cloth.
  - Skin vs petticoat is decided by position. Green below the ankles counts as shoe in both the sheet and the render (`regions.fold_feet`).
  - Remaining known errors: the back view's palest mint hair lobes over the skirt still read partly as dress, and small skin highlights between the halter straps read as dress. Use the region numbers for trends, not as an absolute score.
- Rerun `tools/prep_ref.py -- --regions-only` after changing `spec.SHEET_PALETTE` or `levi/regions.py`.

## Look-dev (cel shading)
- Light: one sun per view, placed relative to that view's camera. It comes from the viewer's upper left, nearly frontal and low (`render.SUN_AZIMUTH_DEG` 20 / `SUN_ELEVATION_DEG` 12), so front, side and back are all mostly lit like the sheet.
- The world is black and the sun strength is π, so the toon ramp sees pure N·L × shadow in 0..1. Below the ramp threshold a surface takes the single shade tone: turned-away sides, undersides of hems, chin and strands, and cast shadows.
  - The threshold is `toon.RAMP_THRESHOLD` (0.30), overridden per palette key by `toon.RAMP_BY_KEY`. The sheet shades cloth and hair much more than skin, so dress/sleeve keys use 0.48, hair 0.42, green/leaf 0.50.
- Cast shadows are on (`render.CAST_SHADOWS`). On the full model they give the sheet's contact shadows: skirt onto petticoat and thighs, chin onto neck, sleeves onto the hair behind them. `render.py --no-shadows` turns them off.
- `render.py` re-applies the current ramp and palette to the materials in the `.blend` (`toon.sync_materials()`), so look-dev changes need no rebuild. `--sun AZ,EL`, `--ramp T` and `--ramp-key KEY=T,...` override the light and thresholds for experiments.
- No highlight tone: the sheet's lit hair and cloth are flat base colour with no distinct highlight band, so the ramp stays two-tone.
- Colour: Standard view transform, no look, no dither. A flat lit surface renders exactly its `spec.PALETTE` `base` hex, and a shaded one exactly its `shade` hex (0/255 error). Renders are pixel- and byte-identical across runs.
- `spec.SHEET_PALETTE` holds the colours measured on the sheet; `spec.PALETTE` (what renders) is that plus the round-2 look-dev retune `spec.PALETTE_TUNING`. The reference classifier and the sheet's shade share use `SHEET_PALETTE`, so retuning the render palette does not move the reference regions. If you need a different colour, ask for a palette change rather than adding a new material.
- Outlines: an inverted hull `spec.OUTLINE_WIDTH` thick (`OUTLINE_PX` = 1.25 panel px, which renders as about 1.25 px lines) in the key's `line` colour.
  - The hull material never casts shadows: it is transparent to shadow rays and back-face culled for shadows.
  - Parts no longer need `obj.visible_shadow = False` or private no-shadow outline materials. Drop those workarounds; leaving `visible_shadow = False` is harmless, but it stops the object from casting shadows.
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
