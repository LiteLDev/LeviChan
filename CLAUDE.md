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
"$B" -b -P tools/rig_pose.py -- --out out/levi_pose.blend [--pose squat]  # posed model for render.py
"$B" -b -P export_pmx.py -- --out out/pmx/Levi.pmx       # needs mmd_tools: no --factory-startup
"$B" -b -P tools/pmx_reimport.py                         # re-import + count check
```
The body part may store fitted limb joints for the rig as `obj["levi_joints"] = {"elbow": (x, y, z), ...}`
(left side, +X; keys in `rig.JOINT_KEYS`). Without it the rig fits joints to the body mesh.

## Rig (levi/rig.py)
- Fitted from the real meshes (the build log says `mesh` or `spec` per item):
  - Limb joints come from body cross-sections. The knee sits at sheet row 700 (`spec.L['knee_z']`).
  - 頭 depth and 目 come from the head mesh.
  - Each of the five fingers gets its own chain, fitted to that finger's loose part in the body mesh. Finger bones are rolled so that +X curls toward the palm.
  - Fingers must therefore stay separate loose parts per finger, or the rig falls back to a generic hand.
- Semi-standard bones:
  - Twist bones 腕捩 and 手捩 have a fixed axis.
  - Skirt chains hang from `スカートN追従左/右`. Each of these appends (回転付与) a share of one thigh's rotation (`rig.skirt_follow`): 100% at centre front and 50% at the back, split between the two legs by angle. The share is spread down the chain (`rig.SKIRT_SEG_FOLLOW`: 90% at the hip, +20% at the next joint through `スカートN追従左/右1`), so a raised thigh lifts the skirt in a curve.
  - Back hair hangs from `髪追従`, which takes 15% of the head's turn; the hair is weighted to 頭 above the eyes, fading to the chains by the choker (`rig.HAIR_HEAD_FADE`), so a turned head doesn't sweep the curtain into the shoulders. Side locks (横髪) hang from 頭.
  - Joint helpers take part of the lower bone's bend and carry the band of skin and cloth around the joint, which avoids collapse and outer-side stretch at deep bends: `ひじ補助` 50% and `ひざ補助` 60%. A shoulder helper `腕補助` exists behind `rig.SHOULDER_AUX` but is off: on the closed-shoulder body it made arms_up worse than the plain envelope blend.
  - Blender evaluates these follows with Copy Rotation constraints. `export_pmx.py` writes them as PMX append, fixed-axis and local-axis bones; append-driven helpers are hidden and not controllable.
  - Leg IK: the knee bends forward only (IK limit, exported as the standard PMX link limit). Blender also locks the thigh's IK twist so its solver doesn't cross the legs; the PMX 足 link stays unlimited.
- Skinning, per part:
  - Garments are positional, but skirt and petticoat weights are angle × height blends of the two nearest skirt chains plus 上半身/下半身. They are never weighted to the legs directly, because the chains follow the legs. This holds for any skirt-family layer, including one between the thighs.
  - Sleeves use arm bones only. The drape chains fade in away from the arm.
  - Shoes and feet are all 足首 below the ankle.
  - Bodice pieces hand over to the skirt weights from 6 cm above the hip to 2 cm below it, so ribbons hanging over the skirt ride it.
  - .L/.R bones are masked off the other side.
  - Small loose ornaments move rigidly, unless they straddle 上半身/下半身 (the waist bow), which then ride the waist like the cloth under them.
  - Weights are smoothed along the surface (wider at the crotch, `rig.CROTCH_SMOOTH`, where a stride pulls the skin between the thighs) and pruned to 4 continuously (no jumps).
- `tools/rig_check.py` deforms the model with every pose in `rig_pose.POSES` (17, including `forward_bend` and `side_bend` for the torso). Each pose must stay within these limits (`--poses a,b` and `--quick` for iteration):
  - any edge at most ×2.0;
  - clothes and hair no more than 2 cm newly inside the body, measured with a winding-number test;
  - no knee bent backward.
  It also checks that the standard PMX bone names motions bind to are all there.
- Pose renders: save each pose with `rig_pose.py --pose NAME --out out/poses/NAME.blend`, then render it with `render.py -- --out out/poses/NAME --no-regions`. `tools/rig_sheet.py` tiles the results into front | side | back sheets on white.
- PMX (`export_pmx.py`, then `tools/pmx_reimport.py`):
  - Textures and toon ramps are written to `<pmx dir>/tex/` and referenced by relative paths: the painted face (opaque; its alpha is a shading mask), one 1-D ramp per gradient material (the vertices' `toon_grad` becomes U), and one toon per palette key that switches to `shade/base` at the key's ramp threshold (MMD reads the toon at v = 0.5 − 0.5·N·L). Lit colour is exactly the palette base at MMD's default light (diffuse × 154/255 + ambient). No sphere maps.
  - Display frames: センター, ＩＫ, 体(上), 腕, 指, 体(下), 足, 髪, スカート, 袖. Physics: bone-following bodies on the torso, head, limbs and hands; dynamic hair, skirt and sleeve chains collide with them.
  - `pmx_reimport.py` checks counts, names, standard bones, display frames, knee IK limits, textures, 回転付与, and runs a VMD round trip: a procedural walk keyed on the standard bones is exported with mmd_tools, re-imported and compared bone by bone (knees must bend forward). It saves `reimport.blend`, `reimport_preview.blend` (materials that evaluate MMD's toon shading under `render.py`'s sun) and `reimport_walk.blend` (Blender frame 9 = VMD frame 8 of the walk).
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
