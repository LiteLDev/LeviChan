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
- `levi/proxy.py`: a grey stand-in body (`--proxy`) that gives context before the real body exists.
- `build.py`, `render.py`, `tools/compare.py`, `tools/check.py`: the pipeline. `tools/prep_ref.py` regenerates `ref/<view>.png` and `ref/<view>_mask.png`.

## Coordinates
- Metres, Z up, the character faces −Y, and the origin is on the ground between the feet. +X is the character's left, which is image-right in the front view.
- The side view looks from +X, so the character faces image-left.
- One panel pixel is `1/643` m. `spec.panel_px(view, p)` maps a world point to a reference pixel.

## Pipeline
```
"$B" -b -P build.py -- --out out/levi.blend [--parts body,skirt] [--proxy]
"$B" -b out/levi.blend -P render.py -- --out out/render [--hide _proxy] [--views front,side,back]
"$B" -b --factory-startup -P tools/compare.py -- --render out/render --out out/cmp [--box x0,y0,x1,y1]
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

## Part rules
- A part only adds objects to the `col` passed to `build(col)`. It must not read or modify other parts' objects; align to `spec.L` landmarks instead.
- Materials always come from `toon_material`. Every visible mesh gets `add_outline` unless it sets `obj["no_outline"] = True` (e.g. eye decals).
- Stay within `spec.BUDGET[part]`, which counts evaluated faces excluding the outline hull.
- Builds must be deterministic and repeatable. No randomness without a fixed seed.
- Don't edit `spec.py`, `common.py`, `toon.py` or another part from a part PR. If a landmark is off, put a local correction in your part and explain it in the PR.
- Never commit `.blend` files or `out/`. PR screenshots go under `docs/pr/<part>/`.
- No Claude/AI attribution in commits or PRs.
