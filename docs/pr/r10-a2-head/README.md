# R10-A2: head and face follow the shape master

File changed: `levi/parts/head.py` only.
- Unchanged: spec, common, toon, shape, `assets/shape/`, other parts and the rig.
- No morph names changed.
- Head: 12,021 faces, the same as main (budget 18,000). Model: 107,968 faces.

## What changed
`master_fit()` reads the face depth from the master's `head` surface once per build (~0.2 s):
- It casts front rays at ±X into the master's `head` triangles and subtracts our own analytic section (`front_y_vec(..., master=False)`).
- It drops samples that are not the face:
  - facing sideways;
  - more than 4 px in front of ours or 32 px behind (bang strands labelled head);
  - near the eye opening (the master has blank sockets);
  - around the mouth slit (the master has no mouth).
- Over the cheek band beside the nose (X 6–26 px), the per-row median set-back is fitted by one ramp, `A · smoothstep(112, r1, row)`. The fit gives A = 18.2 px (2.8 cm) and r1 = 146 (rms 5.2 px over 45 rows). Our lower face really is a muzzle in front of the master's flatter face.
- `MASTER_FOLLOW` = 0.25 of it is applied: about 4.5 px (7 mm) from the mouth down, fading in from mid-eye.

`master_offset()` adds the set-back inside the section functions: `_front_y` (rings) and `front_y_vec` (the lower-face field).
- It is added to the base form, before the nose and the relief, so the shading-normal head gets the same offset.
- So the rings, the lower field, `face_point`/`surf`, the eye and mouth patches, the eyeball fit, `levi_eye_pivot`/`levi_eye_radius`, the ears and all 40 morph targets follow it. No vertex is moved after the build.
- `master_depth()` fades the ramp out toward the sides and saturates it within 75 % of each point's depth in front of the section's widest point. So the jaw and the front-view half-width stay ours, and no section folds.
- The offset is along −Y only, so the front-projected face texture stays on its panel pixels.

## Zones kept procedural
- **Eyes, lids, lashes, iris, eyeball:** ours.
  - The opening and its rim move back rigidly, by the ramp's value on the lower lid (1.37 px, 2.1 mm). This blends into the ramp over 2–14 px from the opening (`MASTER_EYE_KEEP`).
  - So the rim keeps its exact shape. `fit_eyeball` refits the same sphere 2.3 mm further back: pivot L (0.0140, −0.0640 → −0.0617, 1.3017), radius 36 px. The lids' morph paths stay ours.
- **Mouth, lips, pouch, teeth, tongue:** ours. They ride the set-back with their own relief.
- **Nose:** ours, riding the set-back. The master's small, sharp nose with its nostril hollow carved a groove and a pinched nose root when followed.
- **Chin:** ours (the owner's soft chin). The master's V chin is not copied; only the depth ramp reaches the chin.
- **Forehead, skull, crown, ears:** ours. The ramp is 0 above row 112.
  - The master's upper face already meets ours.
  - Under the hair the master has no head surface. Its ears are fused into the hair.
  - The skull does not grow toward the hair_front cap.

## A/B: order-balanced pairwise Codex vs main
- Face close-ups: cel and clay; front, 3/4 front-left, side, turn 20°.
- Every pair is shown in both orders. A pick counts only when both orders agree; otherwise it is a tie.
- Models: gpt-6-astra and gpt-6.1-sol.
- Script: `ab_face.py`, with renders from `face.py` (`render.py --scale 4` with shape keys set). Prompt: `prompt_ab.md`. Replies are in `ab_*.md`.

### How far to follow (8 rest close-ups; new–old)

| variant | astra | sol | judges' reasons |
|---|---|---|---|
| sample by sample (smoothed field) | 2–6 | 2–6 | lumps, a ridge across the midface, pinched nose root, notched profile |
| ramp, follow 1.0 | 0–8 | 0–8 | scooped mouth, hooked chin (the chin's thin wedge saturates while the mouth goes back) |
| ramp, follow 0.6 | 0–8 | 0–8 | same, milder (`variant_follow_0.6_side.jpg`) |
| ramp, follow 0.45 | 0–8 | 6–2 | astra: "chin pad", "recessed mouth" |
| ramp, follow 0.35 | 6–2 | 8–0 | |
| ramp, follow 0.25 | 8–0 | 8–0 | "shorter, rounder chin", "cleaner cheek-to-jaw curve", "less nose projection" |

### Handling the eye at follow 0.25 (the ramp alone failed the eye gate, see Gates)

| variant | astra | sol | note |
|---|---|---|---|
| eye held at 0 within 2–8 px of the opening | 3–5 | 4–4 | "groove / crease under the eye" |
| ramp from row 120, eye held at 0 within 2–24 px | 2–6 | 0–0 (8 inconsistent) | "ledge under the nose", "muzzle" |
| **eye moved back rigidly, blended over 2–14 px (ships)** | **8–0** | **8–0** | `ab_final_rest.md` |

### Final build: expressions
The final build was also compared with 9 morphs (まばたき, ウィンク, 笑い, あ, い, う, お, はぅ, キリッ), each in front and 3/4 (`ab_final_morphs.md`):
- astra: 18–0–0 (new–old–tie);
- sol: 9–0–9; the 9 ties are order-inconsistent picks.

The judges found no tearing, no lids through the eyeball and no crossed lips. The preference is the lower-face shape.

Sheets:
- `ab_rest_cel.jpg` and `ab_rest_clay.jpg`: main left, new right; front | 3/4 on top, side | turn 20° below.
- `morphs_main_vs_final.jpg`: main | new pairs, front then 3/4, in the order above.

## Shape-master fit (`tools/shape_fit.py --parts head`, mm)

| | p50 | p90 | p99 | covered |
|---|---|---|---|---|
| main | 6.2 | 20.5 | 31.6 | 0.417 |
| this PR | 6.0 | 20.7 | 31.6 | 0.438 |
| review.py's run | 5.8 (−0.4) | 19.9 (+0.1) | | 0.446 (+0.020) |

The head p90 does **not** drop.
- It is set by a cluster of master triangles labelled 'head' behind the nape: rows 137–149, columns 303–333 px, inside our hair_back shell.
- That is the underside of the master's welded hair mass, labelled head because our neck was nearest. It is 14 % of the samples, median 24 mm. It is identical in both builds.
- Following it would mean growing skin under the hair, moving with 頭 into the hair chains, so it stays procedural.

On the face itself (columns < 290, rows 112–162, |X| < 30 px):

| | p50 | p90 | p99 |
|---|---|---|---|
| main | 5.3 | 10.6 | 13.5 |
| this PR | 4.6 | 9.1 | 11.8 |

Following further lowers the face p90 to 7.8 mm at follow 1.0, but that version loses the A/B 0–16.

## Gates (final build)

| check | main | this PR |
|---|---|---|
| `tools/check.py` | OK | CHECK OK (head 12,021, total 107,968) |
| `tools/rig_check.py` (17 core poses + eye test) | OK, eye 1.36 mm | RIG CHECK OK, eye 1.38 mm (limit 1.5) |
| `export_pmx.py` + `pmx_reimport.py` | OK, 40 morphs | REIMPORT OK. All 40 morphs are present, move, and sit in their panels (brow 6, eye 11, mouth 16, other 7). |
| motion report, issues per part | head 0 major / 13 minor | identical for every part (`motion_delta.md`) |
| motion eye metric, worst | はぅ=0.5 1.48, まばたき=0.5 1.46 | 1.48 / 1.44; all minor or ok, as in main |
| three-view IoU (report only) | front 0.916, side 0.860 | front ±0.000, side −0.001 (side skin −0.004) |
| shade islands (front / q34 / side / high) | 39 / 42 / 34 / 38 | 39 / 41 / 35 / 39 (px −1 / −7 / −32 / +63) |

Intermediate versions that failed the eye gate:
- The ramp taken across the eye opening tilted the rim: まばたき=0.5 1.54 mm and はぅ=0.5 1.60 mm (major).
- With the outer corner still faded at the face's side, キリッ went to 7.9 mm.

Both are fixed in `master_offset`.
