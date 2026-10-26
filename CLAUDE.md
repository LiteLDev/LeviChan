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
         [--views review|q34_front_left,q34_back_right,high,turn_<AZ>] [--clay] [--turntable N] [--pose NAME,...|all]
python tools/review.py [--focus <part>] [--build] [--turntable 8]   # renders + contact sheets + Codex review (see Review)
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
  - Skirt chains (`rig.SKIRT_SECTORS` = 16 around the body) hang from `スカートN追従左/右`. Each of these appends (回転付与) a share of one thigh's rotation (`rig.skirt_follow`): 100% at centre front and 50% at the back, split between the two legs by angle. The root takes `rig.SKIRT_SEG_FOLLOW[0]` (65%) of it and the next joint 10% more through `スカートN追従左/右1`.
    - Blender only: that joint also gets a collision-like push (`rig.SKIRT_PUSH`): 80% of the thigh's swing past 15°, through a driver on its constraint's influence. A stride leaves the hem hanging and a squat folds the lower skirt over the thighs. In the PMX the segments below the roots are physics bodies colliding with the legs, so only the linear share is exported.
  - Back hair hangs from `髪追従`, which takes 15% of the head's turn; the hair is weighted to 頭 above the eyes, fading to the chains by the choker (`rig.HAIR_HEAD_FADE`), so a turned head doesn't sweep the curtain into the shoulders.
    - Each long, narrow loose part of hair_back (a lock: at least `rig.HAIR_LOCK_LEN` long, spanning less than `rig.HAIR_LOCK_SPAN` around the skull) gets its own chain `後髪束N` along its centreline and rides it alone, so it bends along its length.
    - The rest (the curtain) hangs from sector chains `後髪N`.
  - Side locks hang from 頭. Each hair_front family (`rig.SIDE_HAIR_FAMILIES`: hair_cheek / hair_lock / hair_curl / hair_curtain + `_L`/`_R`) gets its own short chain (横髪, 横髪長, 横髪巻, 横髪奥), so the families sway apart. Bangs and crown then follow 頭 only. Without those objects there is one 横髪 chain per side.
  - Joint helpers take part of the lower bone's bend and carry the band of skin and cloth around the joint, which avoids collapse and outer-side stretch at deep bends: `ひじ補助` 50%; the knee has two, `ひざ補助` 35% and `ひざ補助2` 70% (`rig.JOINT_AUX_CHAIN`), so no blend spans more than ~40° of a deep squat.
  - Shoulder shrug (`rig.SHOULDER_SHRUG` 15%): `腕` is the standard bone motions key, a non-deforming child of 肩. `肩補助` (deforms the outer shoulder) turns 15% of 腕's rotation about the inner end of the clavicle. The deforming arm `腕D` hangs from it and turns the other 85%. So the arm points exactly where 腕 aims, from a joint that rises as the arm does, and no bone appends a bone below itself (mmd_tools would make that a dependency cycle). Children of the arm (腕捩, ひじ…) hang from 腕D.
  - Sleeve drapes hang from `袖追従`, which turns back 40% of 腕's rotation (negative 付与), so raised arms let the bags fall back instead of standing up. In MMD the drape segments are physics bodies (gravity does this), so the append matters only with physics off.
  - A shoulder helper `腕補助` exists behind `rig.SHOULDER_AUX` but is off: any border between helper and no helper around the arm becomes a seam (×2.0–3.0 in arms_up).
  - Blender evaluates these follows with Copy Rotation constraints, or with drivers on the quaternion (`follow_q`: the shrug, 腕D, 袖追従, which share 腕's rest frame). `export_pmx.py` writes them as PMX append (negative shares allowed), fixed-axis and local-axis bones; append-driven helpers (and 腕D) are hidden and not controllable.
  - Leg IK: the knee bends forward only (IK limit, exported as the standard PMX link limit). Blender also locks the thigh's IK twist so its solver doesn't cross the legs; the PMX 足 link stays unlimited.
- Skinning, per part:
  - Garments are positional, but skirt and petticoat weights are angle × height blends of the two nearest skirt chains plus 上半身/下半身. They are never weighted to the legs directly, because the chains follow the legs. This holds for any skirt-family layer, including one between the thighs.
  - Sleeves use arm bones only. The drape chains fade in away from the arm, and are split between their segments by position along the chain (not envelopes), so moving a ring shifts the weights smoothly.
  - Back hair uses the skirt's scheme: angle × height between the two nearest of its chains (`rig.HAIR_SECTORS` = 10; `rig.HAIR_RING` switches it), so neighbouring locks move together (no chain blending across the face gap).
  - The choker is 首 with 30% 上半身2 at its lower edge; the halter cords take the skin's weights, handing over to 首 near the choker (`rig.NECK_CORDS`).
  - The skin in the armpits is smoothed wider (`rig.ARMPIT_SMOOTH`), like the crotch.
  - Shoes and feet are all 足首 below the ankle.
  - Bodice pieces hand over to the skirt weights from 6 cm above the hip to 2 cm below it, so ribbons hanging over the skirt ride it.
  - .L/.R bones are masked off the other side.
  - Small loose ornaments move rigidly with the weights of the surface they sit on: the part's weights at the closest vertex of any larger skinned piece within `rig.ATTACH_REACH` (shoe leaves ride the ankle wrap, flowers the hair). The exception is an ornament that straddles 上半身/下半身 (the waist bow): it rides the waist like the cloth under it.
  - Eyelid sheets (head objects named *lid*, carrying the blink shape key) are 頭 only and left out of the eye fit.
  - Weights are smoothed along the surface (wider at the crotch, `rig.CROTCH_SMOOTH`, where a stride pulls the skin between the thighs, and in the armpits) and pruned to 4 continuously (no jumps).
- `tools/rig_check.py` deforms the model with every pose in `rig_pose.POSES` (17, including `forward_bend` and `side_bend` for the torso). Each pose must stay within these limits (`--poses a,b` and `--quick` for iteration):
  - any edge at most ×2.0;
  - clothes and hair no more than 2 cm newly inside the body, measured with a winding-number test;
  - no knee bent backward.
  It also checks that the standard PMX bone names motions bind to are all there.
- Pose renders: save each pose with `rig_pose.py --pose NAME --out out/poses/NAME.blend`, then render it with `render.py -- --out out/poses/NAME --no-regions`. `tools/rig_sheet.py` tiles the results into front | side | back sheets on white.
- PMX (`export_pmx.py`, then `tools/pmx_reimport.py`):
  - Shape keys become PMX vertex morphs in the 表情 frame (`export_pmx.MORPH_INFO` gives the panel: まばたき → eye). Copies of one key from several objects are merged into one morph. pmx_reimport checks that every exported morph is there, moves vertices and is listed in a frame.
  - Textures and toon ramps are written to `<pmx dir>/tex/` and referenced by relative paths: the painted face (opaque; its alpha is a shading mask), one 1-D ramp per gradient material (the vertices' `toon_grad` becomes U), and one toon per palette key that switches to `shade/base` at the key's ramp threshold (MMD reads the toon at v = 0.5 − 0.5·N·L). Lit colour is exactly the palette base at MMD's default light (diffuse × 154/255 + ambient). No sphere maps.
  - Display frames: センター, ＩＫ, 体(上), 腕, 指, 体(下), 足, 髪, スカート, 袖. Physics: bone-following bodies on the torso, head, limbs and hands; dynamic hair, skirt and sleeve chains collide with them.
  - `pmx_reimport.py` checks counts, names, standard bones, display frames, knee IK limits, textures, 回転付与, and runs a VMD round trip: a procedural walk keyed on the standard bones is exported with mmd_tools, re-imported and compared bone by bone (knees must bend forward). It saves `reimport.blend`, `reimport_preview.blend` (materials that evaluate MMD's toon shading under `render.py`'s sun) and `reimport_walk.blend` (Blender frame 9 = VMD frame 8 of the walk).
`out/cmp/<view>_{overlay,diff,sbs}.png`:
- In the diff, red = render sticks out and blue = reference not covered.
- The tool also prints IoU against the reference silhouette.
- It also prints one `REGION <view> <region> iou .. tol .. dE .. shade ref .. ren ..` line per region. IoU compares `ref/<view>_regions.png` with the render's `<view>_regions.png`, which `render.py` writes from the materials' palette keys. dE is the mean CIE76 colour error over pixels both images give that region.
  - `dEi` is the interior colour error: dE over pixels at least 2 px inside the region in both images. Line art, anti-aliasing and thin-zone offsets don't count, so use it for palette and ramp tuning.
  - `tol` forgives up to 2 px of misplacement. For thin zones (ribbons, laces) a low `iou` with a high `tol` means aligned but offset; a low `tol` means missing or misplaced parts.
  - `shade` is the share of the region painted in a shade tone (nearest palette base vs shade) in the sheet and in the render: the lit/shade balance look-dev tunes.
- `--part-region skin,hair` reports only those regions and writes `<view>_region_<name>.png` diffs.
- The reference regions come from colour plus spatial priors (`levi/regions.py`):
  - The pale regions (hair / dress / skin) are grouped into components bounded by the sheet's line art, and each component takes its majority label. This removes most speckle from highlights and painted shading.
  - The hair's white-to-mint gradient is sampled too (`regions.GRADIENTS`), so half-mint strands read as hair, not mint cloth.
  - Skin vs petticoat is decided by position. Green below the ankles counts as shoe in both the sheet and the render (`regions.fold_feet`).
  - Small enclosed patches (`regions.fill_islands`, up to 1500 px) take the region that surrounds at least 85% of them, looking through the line art. This cleans the hair/dress speckle around the back hair lobes and beside the bodice.
  - Remaining known errors: the palest mint parts of the back hair lobes that touch the skirt over a long edge still read as dress, and the holes inside the curls are ambiguous. Use the region numbers for trends, not as an absolute score.
- Rerun `tools/prep_ref.py -- --regions-only` after changing `spec.SHEET_PALETTE` or `levi/regions.py`.

## Look-dev (cel shading)
- Light: one sun per view, placed relative to that view's camera. It comes from the viewer's upper left, nearly frontal and low (`render.SUN_AZIMUTH_DEG` 20 / `SUN_ELEVATION_DEG` 12), so front, side and back are all mostly lit like the sheet.
- The world is black and the sun strength is π, so the toon ramp sees pure N·L × shadow in 0..1. Below the ramp threshold a surface takes the single shade tone: turned-away sides, undersides of hems, chin and strands, and cast shadows.
  - The threshold is `toon.RAMP_THRESHOLD` (0.30), overridden per palette key by `toon.RAMP_BY_KEY`. The sheet shades cloth and hair much more than skin, so dress/sleeve keys use 0.48, hair 0.42, green/leaf 0.50. Shoes use 0.10: the sheet paints them almost flat base.
- Cast shadows are on (`render.CAST_SHADOWS`). On the full model they give the sheet's contact shadows: skirt onto petticoat and thighs, chin onto neck, sleeves onto the hair behind them. `render.py --no-shadows` turns them off.
  - Thin strips don't cast: the objects named in `render.NO_CAST_OBJECTS` (ribbon tails, lacing, sleeve and shoe ribbons, halter, choker, leaf veins, seam strips, facings). They still receive shadows. If they cast, they print hard, narrow copies of themselves onto the pale cloth a few mm away, which the sheet never paints.
  - Bulky ornaments (bows, leaves) still cast. Turning them off also drops their self-shadowing, and their N·L shading then breaks into more islands.
  - A part decides for its own objects with `obj["levi_cast_shadow"] = True/False`, which wins over the list. Prefer that, and drop the name from the list. `render.py` warns when a listed name is missing.
  - `--thin-casters` restores the old behaviour for comparison.
  - Round 4 tested the shadow map itself (`--shadow FILTER,ANGLE,MAXRES`): filter 0.5–10 texels, sun angle 0–8°, max resolution 1 or 0.5 mm. None of them cleaned the cel shading. A wide filter (6) rounds the cast-shadow contours on the thighs, but thresholding the filtered edge leaves more specks on the dress (front islands 29 → 42), so the filter stays 0.5. The resolution and the angle change nothing measurable. There is no shadow acne.
  - Most remaining small shade islands come from N·L, not from cast shadows: with `--no-shadows` round 4 still counts most of them. They are coarse or noisy normals at the terminator, so fix them in the part (`05_islands.png` shows where they are).
  - The scalloped skirt and petticoat shadow on the thighs comes from the ruffle geometry. Stopping the petticoat from casting brings skin shade near the sheet's (back 0.31 → 0.26, sheet 0.18), but the petticoat then loses the tier-on-tier shade the sheet has (side 0.47 → 0.31, sheet 0.44). So a fix belongs in the petticoat: for example, ruffles with `levi_cast_shadow = False` plus a smooth caster.
- `render.py` re-applies the current ramp and palette to the materials in the `.blend` (`toon.sync_materials()`), so look-dev changes need no rebuild. These flags override settings for experiments:
  - `--sun AZ,EL`: the key light.
  - `--ramp T` and `--ramp-key KEY=T,...`: the ramp thresholds.
  - `--palette KEY.TONE=#RRGGBB,...`: palette colours.
  - `--shadow FILTER,ANGLE,MAXRES`: the shadow map.
- No highlight tone: the sheet's lit hair and cloth are flat base colour with no distinct highlight band, so the ramp stays two-tone.
- Colour: Standard view transform, no look, no dither. A flat lit surface renders exactly its `spec.PALETTE` `base` hex, and a shaded one exactly its `shade` hex (0/255 error). Renders are pixel- and byte-identical across runs.
- `spec.SHEET_PALETTE` holds the colours measured on the sheet; `spec.PALETTE` (what renders) is that plus the round-2 look-dev retune `spec.PALETTE_TUNING`. The reference classifier and the sheet's shade share use `SHEET_PALETTE`, so retuning the render palette does not move the reference regions. If you need a different colour, ask for a palette change rather than adding a new material.
- Outlines: an inverted hull `spec.OUTLINE_WIDTH` thick (`OUTLINE_PX` = 1.25 panel px, which renders as about 1.25 px lines) in the key's `line` colour.
  - For the gradients in `toon.GRADIENT_LINES` (hair → hair_tip) the line colour follows `toon_grad` too, so a mint tip gets the mint line. Other gradients keep the first key's line.
  - `add_outline(obj, width, vertex_group=..., min_factor=...)` scales the hull thickness per vertex: weight 1 = full width, 0 = `width * min_factor`. Use it for internal overlaps or a rolled hem lip, so that minor edges read lighter than the silhouette.
  - The hull material never casts shadows: it is transparent to shadow rays and back-face culled for shadows.
  - Parts no longer need `obj.visible_shadow = False` or private no-shadow outline materials. Drop those workarounds; leaving `visible_shadow = False` is harmless, but it stops the object from casting shadows.
  - Open single-sided sheets work with normals facing either way: with backface culling, the hull never covers the fill.
  - A hull only draws silhouettes, so the open border of a sheet that faces the camera gets no line. If a border line matters, give the sheet a little thickness or use `render.py --freestyle` (1 px crease and open-border lines in each material's line colour).

- Any angle: the key light follows the camera, so the review views (`q34_front_left`, `q34_back_right`, `high`, `turn_<AZ>`) get the same upper-left key as the sheet views. Round 3 checked them: they stay mostly lit with one shade tone, with shade shares close to the ortho views (`out/review/shade_stats.txt`). The remaining hard bands and triangular shade breaks come from the parts, not the light: coarse or flat normals at the terminator, and short `toon_grad` ramps on the hair tips. Fix them in the part.

## Review
One command renders everything a reviewer needs and asks two Codex models for a structured review:
```
python tools/review.py [--blend out/levi.blend] [--rig out/levi_rig.blend] [--build] [--focus hair_back]
                       [--turntable 8] [--poses walk,arms_up,...] [--no-codex] [--timeout 900]
```
- It runs in any Python 3.9+ with only the stdlib, including Blender's bundled `python.exe`. It drives Blender for every image step; `LEVI_BLENDER` / `LEVI_CODEX` (or `--blender` / `--codex`) override the executables.
- `--build` builds both .blends first. Without a rigged .blend, the pose sheet is skipped.
- Output in `out/review/`:
  - `01_ortho_sbs.png`: the sheet over the cel render, front / side / back.
  - `02_angles_cel.png`: the 3/4 front-left, 3/4 back-right and high views.
  - `03_clay.png`: all six views in clay.
  - `04_poses.png`: `rig_pose` poses, front + 3/4.
  - `turntable.png` (with `--turntable`).
  - `metrics.txt`: `compare.py` IoU / REGION lines. `shade_stats.txt`: the per-region shade share at every angle.
  - `shade_islands.txt` and `05_islands.png`: small shade islands per view and region (`regions.shade_islands`), drawn in red on the render. An island is an 8-connected shade patch of 4–80 px with at least one interior pixel, so 1 px anti-aliased fringes along line art are ignored. This metric makes the chipped look of specks and slivers measurable. Fewer is better.
  - `--baseline <earlier review dir>` writes `metrics_delta.md`, which gives every metric as new (delta). It is also appended to `summary.md`, so rounds compare numerically. Keep a run on `main` (e.g. `--out out/review_main`) as the baseline.
- Codex: `gpt-6.1-sol` and `gpt-6-astra` (`--models`) run concurrently as child processes, `codex exec -s read-only` in the repo, with every sheet attached and a JSON schema for the reply. The tool waits for both (`--timeout` seconds, default 900).
  - The prompt ranks naturalness in 3D first, animation-readiness second and fidelity third, and asks for findings per part with priority, view, location, issue and a concrete fix. `--focus <part>` makes it review that part in most detail.
  - Replies go to `out/review/<model>.md` (and `.json`, `.log`); `summary.md` merges them by part, with every priority-1 finding listed first. `prompt.md` keeps the exact prompt.
- A single run takes about 25 s of rendering plus a few minutes per model. `--no-codex` stops after the sheets; `--no-render` reuses the renders already in `--out`.
- `docs/pr/r3-review/` holds the round-3 baseline sheets and summary. `docs/pr/r4-lookdev/` holds the round-4 look-dev baseline and final, with the islands sheets and `metrics_delta.md`.

## Part rules
- A part only adds objects to the `col` passed to `build(col)`. It must not read or modify other parts' objects; align to `spec.L` landmarks instead.
  - Exception: a part may import another part's *measurement data or pure surface functions* (e.g. `shoes` reads `body`'s foot tables, `bodice` calls `skirt.front_surface_y()`) so fitted layers follow the layer underneath. Import data/functions only — never objects — and say so in the PR. The owning part must keep those names stable.
- Materials always come from `toon_material`. Every visible mesh gets `add_outline` unless it sets `obj["no_outline"] = True` (e.g. eye decals).
- Stay within `spec.BUDGET[part]`, which counts evaluated faces excluding the outline hull.
- Builds must be deterministic and repeatable. No randomness without a fixed seed.
- Don't edit `spec.py`, `common.py`, `toon.py` or another part from a part PR. If a landmark is off, put a local correction in your part and explain it in the PR.
- Never commit `.blend` files or `out/`. PR screenshots go under `docs/pr/<part>/`.
  - Keep PR images small: JPEG (quality ~85) or downscaled PNG, at most ~1.5 MB per PR in total. Contact sheets can be downscaled to ~1200 px wide.
- No Claude/AI attribution in commits or PRs.
