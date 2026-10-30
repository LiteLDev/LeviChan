# r11-accessories: choker, halter cords, head flower and leaves

Part: `accessories` (`levi/parts/accessories.py`) plus its section of `levi/rig.py`.
Faces 7,576 / 8,000 (round 10: 3,264). Thin pieces set `levi_cast_shadow = False`: the choker, the halter and the leaf veins.

## First build
- **Choker.** Round 10's choker was a single 7-sided tube that bulged into faceted double cones. It is now 24 closed round beads (12 x 7 spheres, slightly long along the cord) on a thin closed 6-sided cord. The beads are spaced by arc length round the neck loop, which is fitted to the body's neck. The weights still use `rig._choker_skin` (the skin at the centre line), so the average weights match round 10.
- **Halter cords.**
  - The cords are resampled evenly (2.8 mm rings, 8 Catmull-Rom samples per span). They are fitted like a taut cord to the torso after one smooth subdivision: Phong projection, smoothed settling, and hollows bridged by at most 2.5 mm. The worst turn is now 12° per ring; round 10 had 55-61°, a kink about every centimetre.
  - The X strands start and end on the strap's centre line and thin to 0.8 R there.
  - Each strap starts inside a choker bead.
- **Head ornaments.** The petals now have 13 x 7 samples and the leaves 27 x 7, which gives rounder outlines.

## Review fixes (this round)
1. **Halter junctions and tucked ends in motion.** These are skinning marks the part writes (point attributes) and the rig reads in the accessories section.
   - **`levi_cord_join` (the X strands).** Over the last 30 mm of a strand, its weights blend to those of the strap beside it (`rig._halter_joins`).
     - The blend is the inverse-distance mix of the 24 nearest strap vertices, softened by 1 cm. It is looked up at each vertex's position smoothed along the surface (about its section's centre), so every vertex of a section gets one set of weights.
     - The prune's motion refit also runs at those smoothed positions (`HALTER_REFIT_AT`).
     - With per-vertex lookups, the section's vertices came out about 1.5 % apart in the shoulder stage bones, whose turn moves a chest point about 12 cm. The strand's section at the junction then flattened to x0.05 in idol_dance@80.
     - Taking the strap's weights at the end point alone turned the strand's last centimetre rigidly, and it crossed the bending strap like a knot.
     - Junction drift is now at most 0.33 mm over the 17 core and 24 extended poses (first build: 4.35 mm in hands_behind_head). On the merged model it is at most 0.69 mm.
   - **`levi_cord_ride` (the tucked strap ends).** The tucked end takes the bodice's own skinned weights (`rig._halter_ride`): none above the bodice's real rim, all of them 2 px further down.
     - This happens before the cord's smoothing, so each section shares one set of weights and the change spreads along the cord. To make it possible, the accessories are now skinned after the bodice (`rig.SKIN_LATE`).
     - The straps now end 8 px under the neckline (`STRAP_UNDER`). The real rim runs about 2 px below `bodice.neck_row_t`, so the old 3 px left only two rings under it.
     - Under the rim the strap thins to 0.7 R (`TUCK_TIP`). This leaves 2.5-3.3 mm of room under the bodice at rest.
     - Variants that were tried and dropped:
       - Riding the bodice above the rim too: the chest skin moved out under it in raised-arm poses, and the visible cord sank up to 3.5 mm into the chest.
       - Staying on the skin alone, or riding only 30 %: the deeper end came out through the bodice front.
       - Sampling the bodice per vertex after the smoothing: the end rings stretched x3.
     - Now no ring past the rim's edge comes out in any raised-arm pose. The idol_dance@78 stub is gone (one pixel is left at macro zoom). What dips into the skin, at most 1.9 mm in dance_heart, stays under the bodice.
2. **Choker on the merged model.** The choker no longer imports any head data; it fits the body's neck only.
   - The first build also rested the choker on round 10's head-neck table (`head.neck_at` + `HEAD_DX`). r11/head keeps those names, but its neck is now tucked inside the body's, so on the merged model the left beads floated 2-5 mm off the skin.
   - Merged per-bead gaps are now 0.15-0.31 mm on both sides (mean left 0.26, right 0.24).
   - On r11/base alone, the round-10 head's neck stands about 3 px proud on the left, so the left beads sink into it, as in round 10.
3. **Flower and cheek wisp.**
   - With r11/hair-front (f0ce382), wisp 0 passes under the flower: every petal clears the hair by at least 1.9 mm along the flower's normal, and no petal face crosses hair_front.
   - On r11/base's hair_front (round 10's wisp), the wisp still cuts the lower petals by up to 3.1 mm. That is the same depth as round 10 main, so the flower's seat is kept rather than tuned to the old wisp.
   - `tools/check.py` now prints a `WARN` (not a failure) when the flower's petal faces cross hair_front (`SEATED`). The concealed stalk under the centre is exempt. On r11/base this warns about 54 / 80 face pairs; with r11/hair-front there is no warning.
4. **Flower centre.** The centre is now smaller (0.25 of the radius) and has no outline of its own. The sheet paints a small soft yellow dot with no ring.
   - An inverted hull round a dome among the petals cannot draw a clean ring: its visible part lies below the dome's widest ring, among the petals' raised edges.
   - Two variants were tried and dropped: a 1 mm ring showed a petal sliver, and a 0.5 mm line on a drum stood off the fill as a hairline.

## Integration round (r11/integrate): halter stretch on the merged torso
The integration motion report (r11/integrate 1b06af3) put the halter at x2.32 in idol_dance@78 (major; round 10 x1.64), with 20 more poses above round 10 + 0.05 and compression down to x0.45 (idol_dance@22).

**Diagnosis**
- The merged torso skin hands the upper chest from the clavicle (肩) to the shoulder stages (肩補助2 / 肩補助3) over ~3 cm, right under the X strands' lower ends.
  - In these poses 肩 moves a chest point at most 8 mm against 上半身2. The stages move it 3-12 cm.
  - Five bones meet there: 上半身2, 肩, 首, 肩補助2 and 肩補助3.
- The plain prune gave up the young 肩補助3 ramp and refitted 肩 in its place.
  - The strap then took 肩補助3 back within ~1 cm at the junction: 0 to 0.09 over 3 rings, with 肩 dropping from 0.14 to 0.05.
  - That made a visible jog and stub at both junctions in raised-arm poses: x2.07 on the strap and x2.32 on the strand's end ring.
- The vertices of one ring were ~1 % apart in the stages, which squashed the strand's end rings (x0.59 in hands_behind_head).
- On the neck, the head turn stretched the strap root x1.40.
- The skin under the cord, measured along the cord on the body triangles under each ring, round 10 / merged:
  - idol_dance@78: x1.92 / x2.08.
  - reach_up_back: x1.62 / x1.60.
  - hands_on_hips: x1.48 / x1.45.
  - The body edges within 4 mm of the cord: 1.63 / 1.74 (idol), 1.39 / 1.47 (reach) and 1.08 / 1.26 (hands_on_hips).
  - With 8 mm smoothing the cord followed the skin's local stretch. Round 10's 1 cm rings averaged it.

**Fix** (accessories section of `rig.py`, plus one new attribute in the part)
- **Skin sample.** The skin is sampled at each ring's centre on the nearest skin triangle (`_halter_skin`). The inverse-distance sample led the stage ramp by ~2 rings.
- **Smoothing.** The weights are smoothed along the cord over 20 mm (`HALTER_SMOOTH`, was 8).
- **Rim.** Within 25 mm of the tucked ends the straps blend back to the skin's own weights (`HALTER_RIM_FOLLOW`).
  - Without it, the smoothing's end lagged the skin, and in dance_heart the strap sank 2.3 mm into the chest just above the bodice rim, cut off before it.
- **Tucked ends.** They take the bodice's weights after the smoothing, looked up at the ring centres and blended over 10 mm (`HALTER_RIDE_SMOOTH`).
  - Applied before, they were carried 2 cm up the visible strap. Over 5 mm the hand-over compressed x0.85 at the rim in spin and high_kick.
- **Prune.** It keeps the stages before the clavicle where five bones meet (`HALTER_KEEP`: guide x2 for 肩補助2/3, x0.2 for 肩), with no motion refit (`_halter_prune`).
  - The generic refit put the folded clavicle into the stages, which sank the strands' ends ~0.4 mm deeper with the arms down.
- **Rings.** The part numbers its rings (`cord_ring`, `obj['levi_cord_ring']`), and every vertex of a ring takes the ring's weights.

**Variants tried and dropped** (partial rigs, same poses)
- 8 / 12 / 16 mm smoothing: idol x2.10 / x1.99 / x1.89.
- 25 mm smoothing, or a 45-60 mm lower strand join: the strand sank 2-3 mm with the arms down and back.
- A 15 mm lower join: x2.15.
- 1D Gaussian smoothing along the rings, with reflected tucked ends: the neck went back to x1.33, and idol to x1.86 at σ 10 mm.
- A taut-string (box-constrained) stage profile: kinks.
- Clipping the smoothed weights to the skin's: x3.5.
- Folding 肩 explicitly by the stage share: the same as without the guide demotion (x1.96).
- A longer ride (7 px): compression x0.83-0.87 at the rim.

**Full merge** (scratch worktree: r11/integrate 78bca50 + this branch). Motion report, extended + clips + core:

| Halter | Round 10 | Integrate 1b06af3 | Fixed |
|---|---|---|---|
| idol_dance (worst frame) | 1.637 | **2.316** | 1.647 |
| reach_up_back | 1.379 | 1.728 | 1.299 |
| arms_up | 1.304 | 1.614 | 1.258 |
| hands_on_hips | 1.100 | 1.593 | 1.223 |
| dance_sway | 1.287 | 1.587 | 1.203 |
| hands_behind_head | 1.366 | 1.478 | 1.206 |
| high_kick | 1.203 | 1.497 | 1.220 |
| spin | 1.191 | 1.475 | 1.213 |
| head_left | 1.294 | 1.395 | 1.168 |
| look_over_shoulder | 1.324 | 1.380 | 1.237 |
| Compress, worst | 0.674 | **0.453** | 0.658 |
| Flipped faces | 0 | 4 | 0 |
| Accessory issues | 15 (8 major) | 17 (9 major) | 15 (8 major) |

- **Stretch.** Every pose and clip frame is at most round 10 + 0.05, except hands_on_hips: 1.223 against 1.150.
  - In hands_on_hips the body's own edges under the cord stretch 1.26 (round 10: 1.08), and the halter stays below that.
- **Compression** is at most round 10 - 0.05 everywhere: idol 0.658 vs 0.674, look_over_shoulder 0.702 vs 0.740.
- **Junction.** The strand's end stays on the strap: drift 0.07 mm (before: 0.92).
- **Pen.** Halter pen is 0.2 cm, as before.

**Trade-off.**
- **Raised arms.** In idol_dance@78, reach_up_back, arms_up and dance_heart the junctions and the rim entry are clean (`integ_raised.jpg`, `integ_armsdown_rim.jpg`).
- **Arms down and back.** In hands_on_hips and hug_self the strand's lower end now dips into the bust's top: newly inside the skin up to 1.7 mm on 5-6 % of the visible cord vertices (before 0.6-0.8 mm, round 10 1.2-1.3 mm on 2-3 %).
  - At 4x zoom it shows as a broken outline along ~1.5 cm of the strand (`integ_armsdown_rim.jpg`, top row). In hug_self the sleeve covers it.
  - This is the price of spreading the skin's stage ramp along the cord. Any smoothing that cut the stretch to target put the ramp's start under skin that stays still with the arms back.
- **Rest.** No change at rest: the 4x rest crops differ in at most 3 anti-aliased pixels (`integ_rest.jpg`).

**acc_flower_R pen_frac** (round 10 0.073, now 0.087, dance_heart and idol_dance@48).
- The right forearm passes through the head flower in both rounds (`integ_flower_heart.jpg`, sleeves hidden), and the balloon sleeve hides the whole flower in both.
- The fraction rose because the flower has 2.5x the vertices (1,584 vs 632) and a fuller centre. The depth is 12.8 mm (round 10: 11.0).
- The halter fix does not touch it.

**Gates** (this branch: r11/integrate 1b06af3 + the fix)
- **check:** CHECK OK, determinism included. Accessories 7,592 / 8,000; total 153,186 / 200,000; no seat warning with the merged hair.
- **rig_check, 17 core poses:** RIG CHECK OK. Worst stretch: squat 1.82 (body) and arms_up 1.81 (body). Worst pen: side_bend 1.76 cm (skirt). The accessories are never the worst object.
- **Not run:** export_pmx, pmx_reimport and motion_vmd, because mmd_tools is not installed.

**Images (integration round)**
- `integ_raised.jpg`: 4x junction crops, cel + clay, integrate vs fixed. idol_dance@78 (left and right), reach_up_back and arms_up.
- `integ_neck.jpg`: 4x strap root at the choker in idol_dance@78, arms_up and head_left.
- `integ_rest.jpg`: rest, before / after.
- `integ_armsdown_rim.jpg`: hands_on_hips (the trade-off) and the right strap entering the bodice rim in dance_heart.
- `integ_flower_heart.jpg`: the flower in dance_heart, round 10 vs round 11, with sleeves and without.

## Gates (this branch, other parts as on r11/base)
- **check:** CHECK OK. Accessories 7,576 / 8,000 faces; total 112,280. The build-twice determinism check passed. The seat check warns on r11/base's hair_front, as expected.
- **rig_check, 17 core poses:** RIG CHECK OK, with every row the same as round 10 (worst stretch fist 1.86, squat 1.85; worst pen side_bend 1.76 cm).
- **Motion report** (extended + clips + core), round 10 / first build / now:

  | Measure | Round 10 | First build | Now |
  |---|---|---|---|
  | Accessory issues | 15 (8 major) | 15 (8 major) | 15 (8 major) |
  | Halter stretch (idol_dance@78) | 1.64 | 1.82 | 1.87 (minor) |
  | Halter compress | 0.67 | 0.60 | 0.58 |
  | Choker stretch | 1.26 | 1.29 | 1.24 |
  | Choker compress | 0.56 | 0.545 | 0.61 |

  - The halter's stretch peak is the strap at the skin there, 1.85, the same spot as in the first build.
  - No flips. The major issues are the leaf and flower hair-penetration ones that round 10 already had.
- **Not run:** `export_pmx`, `pmx_reimport` and `motion_vmd` (mmd_tools is not installed).

## Cross-part
- **Data imports:** `body.build_torso` (neck and chest surface) and `bodice.profile` / `bodice.neck_row_t` (the rim the straps tuck under). The `head` import was removed.
- **`rig.py`, accessories section:** `_part_skin`, `_halter_ride`, `_halter_joins`, `HALTER_RIDE_*`, `HALTER_JOIN_*`, `HALTER_REFIT_AT` and `SKIN_LATE`.
- **`rig.py`, one-line touches in shared code:**
  - `_weights` passes `obj` to `_neck_cord_weights`, applies `_halter_joins` to the halter's prune guide, and runs the halter's prune refit at smoothed positions.
  - `build_rig` sorts the `SKIN_LATE` parts last.
  - The halter reads the bodice's final vertex groups (every bodice mesh except the `bodice_leaves` ornaments).
- **`tools/check.py`:** the `SEATED` warning.
- **Integration round, `rig.py` accessories section:**
  - New: `HALTER_RIM_FOLLOW`, `HALTER_RIDE_SMOOTH`, `HALTER_KEEP`, `_halter_sections`, `_ring_mean`, `_halter_skin`, `_halter_rim_follow` and `_halter_prune`.
  - Changed: `HALTER_SMOOTH` (0.008 to 0.020), `_halter_joins` (optional section centres) and the halter branch of `_neck_cord_weights`.
- **Integration round, the one shared-code line in `_weights`:** the halter's two-line guide-join + prune hook became `return _halter_prune(obj, w, guide, co, edges, bones)`.
- **Integration round, the part:** the new `cord_ring` point attribute (`obj['levi_cord_ring']`). `_write_point` takes `clamp=False` for it.

## Images
- `fix_halter.jpg`: idol_dance@78, hands_behind_head, dance_heart and jump_tuck, first build vs fixed. The columns are the junction (cel), the rim (clay) and the side view (clay).
- `fix_junction_macro.jpg`: the lower-left X-strand junction at macro scale (cel + wire) in idol_dance@78 / @80, hands_behind_head and dance_sway, first build vs fixed.
- `fix_choker_merged.jpg`: a scratch merge of r11/accessories with r11/head, hair-front, body-torso, bodice, hair-back, sleeves, skirt, petticoat and shoes (body-hands and body-legs conflict in `rig.py` and were left out), first build vs fixed, front / 3-4 / left / top.
- `fix_flower.jpg`: the centre (first build, fixed, bust scale, sheet), and the flower over r11/base's hair_front vs r11/hair-front.
- `choker.jpg`, `flower.jpg`, `halter.jpg`, `halter_zoom.jpg`, `posed.jpg`: the first build vs round 10 beside the sheet and 风堇.
