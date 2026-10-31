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
- **Raised arms.** In idol_dance@78, reach_up_back, arms_up and dance_heart the junctions and the rim entry are clean (that round's sheets were dropped for size; `integ2_raised.jpg` and `integ2_rim.jpg` show the same spots).
- **Arms down and back.** In hands_on_hips and hug_self the strand's lower end now dips into the bust's top: newly inside the skin up to 1.7 mm on 5-6 % of the visible cord vertices (before 0.6-0.8 mm, round 10 1.2-1.3 mm on 2-3 %).
  - At 4x zoom it shows as a broken outline along ~1.5 cm of the strand (fixed in round 2: `integ2_armsdown.jpg`, left column). In hug_self the sleeve covers it.
  - This is the price of spreading the skin's stage ramp along the cord. Any smoothing that cut the stretch to target put the ramp's start under skin that stays still with the arms back.
- **Rest.** No change at rest: the 4x rest crops differ in at most 3 anti-aliased pixels (`integ2_rest.jpg`).

**acc_flower_R pen_frac** (round 10 0.073, now 0.087, dance_heart and idol_dance@48).
- The right forearm passes through the head flower in both rounds (`integ_flower_heart.jpg`, sleeves hidden), and the balloon sleeve hides the whole flower in both.
- The fraction rose because the flower has 2.5x the vertices (1,584 vs 632) and a fuller centre. The depth is 12.8 mm (round 10: 11.0).
- The halter fix does not touch it.

**Gates** (this branch: r11/integrate 1b06af3 + the fix)
- **check:** CHECK OK, determinism included. Accessories 7,592 / 8,000; total 153,186 / 200,000; no seat warning with the merged hair.
- **rig_check, 17 core poses:** RIG CHECK OK. Worst stretch: squat 1.82 (body) and arms_up 1.81 (body). Worst pen: side_bend 1.76 cm (skirt). The accessories are never the worst object.
- **Not run:** export_pmx, pmx_reimport and motion_vmd, because mmd_tools is not installed.

**Images (integration round)**
- `integ_neck.jpg`: 4x strap root at the choker in idol_dance@78, arms_up and head_left.
- `integ_flower_heart.jpg`: the flower in dance_heart, round 10 vs round 11, with sleeves and without.

## Integration round 2: the halter sinking into the chest with the arms down, and the rim entry
The verifier of the round above found two defects that show at 4x zoom: with the arms down and back the cord sank into the chest skin (hands_on_hips 1.82 mm on 3.3 % of the visible cord, hug_self, hands_behind_back, hand_to_shoulder, arms_crossed, dance_point; deepest on the left strap ~2 cm above the junction and on the X strands' lower thirds), and the strap's last rings above the bodice rim narrowed and dipped in dance_sway and dance_heart.

**Diagnosis** (r11/integrate 9f30883, measured per ring and per bone on the posed meshes)
- **The cord's weights lead the skin's stage ramp.** At the deepest ring the halter carried 0.059 / 0.025 of 肩補助2 / 肩補助3 where the skin under it has 0.041 / 0. With the arms down these bones turn that chest point 31 / 44 mm into the chest per unit weight, so the 0.046 lead alone is 1.7 mm. The skin's own weights, sampled at the cord, sink it at most 1.0 mm in the same poses.
- **The rest gap was uneven.** The cord is fitted 1.0 mm above the torso's smooth subdivision, which over the upper bust lies up to 0.8 mm *under* the real torso. So the cord rested only 0.15-0.45 mm off the skin exactly where the lead bit (0.9-2.2 mm elsewhere). Every sink spot was a low-gap ring.
- **The rim.** By the rim the skin carries the shrug (肩補助, 0.03-0.04). The prune kept a trace of 首 brought in by the smoothing instead, and the bodice's weights (no shrug, less of the stages) were smoothed 1 cm up the visible strap. With the arm raised the last visible rings lagged the skin by ~2.8 mm.
- **The bodice collapses onto the skin by the straps.** With the arms raised, the bodice there comes from ~6.5 mm off the skin down to 0-2 mm (min -0.8 mm). So the strap has to bend toward the skin where it goes under the rim, and the halter can only choose where that bend goes: above the rim (a visible dip), under it (stretch, and the tucked end follows the skin out through the bodice front), or partly both.
- **Weights alone cannot fix the arms-down sink.** A motion-aware least-squares solve of the ring weights (stretch along the cord + normal motion against the skin, generic and test poses as samples) found no point with idol_dance <= 1.69 and every sink <= 1 mm, even with the test poses as samples: the stages' lever is into the chest with the arms down and out of it with the arms raised, so any smoothing leads on one side of the ramp and lags on the other.

**Fix**
- **Part (`accessories.py`):**
  - The cord is held `STRING_FLOOR` 0.9 mm off the real torso while it settles (smoothed along the cord with the other moves; at most the cord's own gap at the tuck and the under strand).
  - Over the upper slope of the bust (`STRING_LOW_BAND`, 34-3 px above the neckline) it stands `STRING_LOW_LIFT` 0.6 mm higher. The rest gap there is now 0.9-2.5 mm (the low spots were 0.15-0.45 mm; the junctions already stood 1.6-2.2 mm off the skin).
  - The bodice hand-over runs 2 -> 5 px under the neckline (`RIDE_FULL`, was 4).
- **Rig (`rig.py`, accessories section):**
  - The stage weights may lead the skin's own by at most `HALTER_LEAD_MAX` 0.01, the excess going to 上半身2 (`_halter_lead_cap`).
  - The straps follow the skin from `HALTER_RIM_FOLLOW` 30 mm above the tuck (was 25).
  - The bodice hand-over is smoothed over `HALTER_RIDE_SMOOTH` 8 mm (was 10).
  - The prune ranks the shrug above 首 (`HALTER_KEEP`: 肩補助 x1.5, 首 x0.5).
- **Unchanged:** the 20 mm smoothing, the ring sets, the joins, the choker and the geometry outside the lower chest. Faces 7,592 (unchanged).

**Variants tried and dropped** (partial rigs, 22 test poses; worst visible sink / idol_dance@78 stretch)
- Motion-aware weight solve, test poses as samples: 0.87 mm / 1.79-2.12. Generic samples were worse.
- The floor without the lift or the cap: 1.55 / 1.57. Lift 0.5 / 0.7 mm without the cap: 1.11 / 1.22; lift 0.4 mm with it: 1.07 / 1.71.
- Lead cap 0.005: 0.92 / 1.74. Cap 0.015 (straps only) / 0.02: 1.14 / 1.31.
- Strap smoothing 14 mm: the strap root compressed to 0.64-0.69 in head turns (before: 0.78), and the strand end stretched 1.73.
- Rim follow 25 / 35 mm (with the 2 -> 8 px hand-over): rim sink 0.86 / 0.51, idol 1.65 / 1.69.
- The hand-over over the whole tuck (2 -> 8 px), or only under the rim (masked smoothing): rim sink 0.6-0.8 mm, but the tucked end followed the skin out through the collapsing bodice in raised-arm poses. A 2 -> 4 px ramp with the old 10 mm smoothing: covered, but 1.45-1.57 mm sink above the rim.
- The tucked end dived into the skin under the rim: the strap's fit changed and idol_dance@78 went to 1.74-1.78.

**Result, the branch's full rig: every core and extended pose and every clip frame (417).**
Measures: visible cord new depth inside the skin (motion_check.inside_depth less rest, no floor) and the share of visible cord vertices past 0.5 mm; halter edge stretch and compress.

| Pose | Round 10 | 9f30883 | Now |
|---|---|---|---|
| hands_on_hips | 1.21 mm (1.0 %) / 1.100 | 1.82 (3.3 %) / 1.219 | **0.87 (0.1 %)** / 1.255 |
| hug_self | 1.32 (1.1 %) / 1.111 | 1.78 (3.3 %) / 1.112 | **0.80 (0.2 %)** / 1.132 |
| hands_behind_back | 0.85 (0.9 %) / 1.040 | 1.46 (2.3 %) / 1.064 | **0.49 (0.0 %)** / 1.088 |
| hand_to_shoulder | 0.96 (0.6 %) / 1.070 | 1.39 (0.9 %) / 1.038 | **0.38 (0.0 %)** / 1.043 |
| arms_crossed | 0.83 (0.4 %) / 1.002 | 1.09 (1.5 %) / 1.014 | **0.25 (0.0 %)** / 1.027 |
| dance_point | 1.47 (0.9 %) / 1.124 | 1.01 (1.1 %) / 1.101 | **0.45 (0.0 %)** / 1.083 |
| dance_sway | 0.76 (0.1 %) / 1.287 | 1.49 (2.0 %) / 1.181 | **0.63 (0.3 %)** / 1.239 |
| dance_heart | 2.10 (1.1 %) / 1.286 | 1.63 (1.6 %) / 1.120 | **0.96 (0.7 %)** / 1.115 |
| hands_behind_head | 1.54 (0.6 %) / 1.366 | 1.16 (1.0 %) / 1.183 | **0.58 (0.2 %)** / 1.227 |
| jump_tuck | 1.78 (0.6 %) / 1.191 | 1.30 (1.2 %) / 1.060 | **0.70 (0.3 %)** / 1.052 |
| arms_up | 1.82 (1.0 %) / 1.304 | 1.12 (0.8 %) / 1.262 | **0.66 (0.1 %)** / 1.286 |
| reach_up_back | 1.80 (0.6 %) / 1.379 | 1.24 (0.8 %) / 1.292 | **0.67 (0.1 %)** / 1.326 |
| idol_dance (clip, worst frame) | 2.17 (1.4 %) / 1.637 | 1.82 (3.3 %) / 1.634 | **0.96 (0.7 %)** / 1.673 |
| Poses + frames with sink > 1.0 mm | 34 of 417 | 60 | **0** |
| Poses + frames with > 1 % past 0.5 mm | 17 | 48 | **0** |

- **Stretch.** idol_dance 1.673 (<= 1.69), reach_up_back 1.326 (<= 1.43), arms_up 1.286 (<= 1.35). Every other pose and clip is at most round 10 + 0.05 except hands_on_hips, 1.255 against 1.150; the skin's own edges under the cord stretch 1.26 there (round 10: 1.08).
- **Compression.** At least round 10 - 0.05 everywhere but look_over_shoulder: 0.683 (round 10 0.740, 9f30883 0.693), on the right X strand's top ring. The same 0.683 with the old prune keep table, the old floor or no lift; no flips.
- **Rim entry** (dance_sway left, dance_heart right): sink 0.63 / 0.96 mm (was 1.49 / 1.63), full width at 4x (`integ2_rim.jpg`).
  - The halter compresses 0.727 / 0.799 there (9f30883: 0.754 / 0.810; round 10 0.761 / 0.827 overall).
  - About half of that is the ring itself: with the arm overhead the stage bones turn 90-120° against 上半身2, and a ~0.75 / 0.25 linear blend of those shrinks each cord section to ~0.75 across (the "around" edges of rings 46-52 read 0.744-0.78 before and now alike). The skin under the cord compresses ~0.73 along it there too.
  - The target 0.80 is not met. It would need the rim rings to lag the skin's stages, which sinks them; the tuck cannot go deeper as the bodice comes down onto the skin.
- **Tucked ends.** Tucked-end vertices that a ray toward a front viewer (straight, ±35° round, ±20° up / down) finds uncovered by the bodice, worst view: hands_behind_head 16 (9f30883: 9), idol_dance@48 9 (5), dance_heart 9 (5), dance_sway 6 (2), jump_tuck 6 (3), idol_dance@80 8 (8), 0 in the other raised poses.
  - These are the ring just under the rim's edge, seen mostly from 20° above: a 1-2 px sliver of green under the rim line at 4x, as before (`integ2_rim.jpg`).
- **Rest.** It looks the same at 4x (`integ2_rest.jpg`); the cord still reads as lying on the skin. The white skin slivers poking through the strands' outline at rest (the 0.15 mm spots) are gone.

**Full merge** (scratch worktree: r11/integrate 89f6117 + this branch, clean merge). Motion report (extended + clips + core, 2471 s) against round 10 and r11/integrate 9f30883:
- **acc_halter, worst:** stretch 1.637 / 1.634 / 1.673 (idol_dance, minor as before), compress 0.674 / 0.654 / 0.643 (idol_dance), pen 2.17 / 1.91 / 1.45 mm. No flips.
- **Halter pen, arms down and back:** hands_on_hips, hug_self, hands_behind_back, hand_to_shoulder, arms_crossed and dance_point now report 0 (9f30883: 1.1-1.8 mm). In the raised-arm poses it is the tucked end under the bodice: 1.1-1.4 mm (9f30883: 1.2-1.9).
- **Per pose**, halter stretch and compress match the branch's own rig to the third decimal.
- **acc_choker:** unchanged (1.264 / 0.539).
- **Accessory issues:** 15 (8 major), the same as round 10 and 9f30883: the halter's minor stretch in idol_dance and the flower and leaf hair-penetration ones.
- **Outside the accessories:** hair x garment crossings move by 1-5 pairs (the cord is part of the garment group). The joint, petticoat and skirt rows that differ come from 89f6117's own commits, not from this change.

**Gates**
- **check (this branch):** CHECK OK, build-twice determinism included. Accessories 7,592 / 8,000; total 162,561 / 200,000.
- **check (scratch full merge, r11/integrate's new check.py):** CHECK OK, "62 meshes identical in a second process".
- **rig_check, 17 core poses (this branch):** RIG CHECK OK. Worst stretch squat 1.82 and arms_up 1.81 (body); worst pen side_bend 1.76 cm (skirt); every knee ok. The accessories are never the worst object.
- **Not run:** export_pmx, pmx_reimport and motion_vmd, because mmd_tools is not installed.

**Images (integration round 2), 9f30883 vs now, cel / clay / wire (wire: red = halter vertices newly > 0.3 mm inside the body)**
- `integ2_armsdown.jpg`: hands_on_hips (left strap 2 cm above the junction), hug_self and hands_behind_back (the left junction and the strands' lower thirds).
- `integ2_rim.jpg`: the rim entry in dance_sway (left), dance_heart, hands_behind_head and idol_dance@48 (right).
- `integ2_raised.jpg`: the junctions in idol_dance@78, reach_up_back and arms_up (the raised-arm gains kept).
- `integ2_rest.jpg`: rest, side of the left junction (cel, clay), the left strap, and the chest.

## Integration round 3: the rim entry (elbow, first tucked ring) and the hidden end

The round-2 verifier passed the arms-down sink and the raised-arm stretch, and left these items, all p3:
- the strap turns 23-26° at one ring just above the bodice rim in raised-arm poses (before: 15-16°; rest: 7 → 15° at ring 48);
- the first tucked ring (ride 0.16) is uncovered at the rim's edge and 1.26-1.32 mm inside the skin in 11 frames;
- rim compress 0.727 / 0.799 in dance_sway / dance_heart (target 0.80);
- whole-object compress on the hidden tucked end (high_kick, raise_bend, spin, idol_dance@76-78), look_over_shoulder 0.683 (bound 0.690) and idol_dance@77 1.569 (bound 1.535);
- the docs were 1.64 MB.

**Result: the halter is unchanged.** I searched the rim entry thoroughly and found no setting that improves the elbow without bringing back the narrowing the round-2 brief removed. The round-2 halter sits at the corner of the trade-off. The cause is outside the halter: the bodice's top rim sinks into the skin beside the strap entries with the arms raised (below). This round only drops superseded sheets and scales others down (the PR's images 1.64 → 1.10 MB, 1.17 MB with this README) and adds the evidence.

**How the search was done.** I used a lab script on the full-merge rig (`acc_i6/tools/rimlab2.py`). It recomputes the halter's weights with the rig's own code (`rig._weights`, the bone list refitted from the file; identical to the stored weights) and rebuilds the halter in the same session from the part's own functions (identical to the built mesh). It then deforms the halter by numpy LBS, which matches the evaluated mesh to 2.6e-7 m. Each variant was measured in 25 poses (the 11 raised-arm frames, the 6 arms-down poses, high_kick, raise_bend, spin, look_over_shoulder, head turns, bends):
- the bend per ring centre (the verifier's kink.py rim zone);
- the depth newly inside the skin, on visible rings and on rings the bodice leaves uncovered;
- the bodice-coverage and poke-out of the tucked rings (vertices beyond the bodice's outer face);
- edge stretch and compress.

About 1,250 variants:
- **Weights:** the rim follow (20-40 mm), a new rim-weight smoothing (0-14 mm), the bodice hand-over (start 1.5-3.5 px, end 4-8 px, smoothing 6-16 mm), and the lead cap on or off.
- **Geometry:** the floor faded out near the rim, the upper-bust lift band moved, an extra lift by the rim, the slack fade, the tuck fade, a deeper dive under the rim, and halved ring spacing over the rim.
- **An optimizer** fitted the ring weights of the last 6 visible rings and the tucked rings directly on the 25 poses (smoothness + height over the posed skin + bodice coverage).

**Trade-off** (worst over the 25 lab poses, the raised-arm frames setting it; no tucked vertex beyond the bodice's outer face unless noted):

| Rim setting | Rim bend | Visible depth | Depth incl. uncovered rim ring | idol_dance stretch |
|---|---|---|---|---|
| now (round 2) | 26.1° | 0.96 mm | 1.31 mm | 1.673 |
| best with visible depth ≤ 1.0 mm | 24.8° | 0.98 | 1.32 | 1.690 |
| "mid": hand-over 1.5→6 px, smoothed 10 mm | 21.5° | 1.21 | 1.47 | 1.672 |
| "smooth": hand-over 1.5→4 px, smoothed 12 mm, rim smoothing 3 mm | 16.5° | 1.99 | 1.99 | 1.660 |
| the floor faded out by the rim (rest bend 13.5 → 5.8°) | 18.0° | 1.05 | 1.32 | 1.762 |
| optimizer on the test poses themselves | 18.1° / 14.4° | 1.24 / 2.78 | 1.60 / 2.78 | — |
| hand-over 3→8 px, smoothed 10 mm | 21.7° | 0.99 | 0.99 | 1.673, but 16 tucked vertices 0.86 mm outside the bodice (dance_heart) |

- `integ3_rim_tradeoff.jpg` shows now / mid / smooth in clay. In the 3/4 view, "smooth" has no elbow. In the side views it narrows above the rim (the 9f30883 look). "mid" softens the corner a little and narrows a little.
- Even fitted to the test poses, the weights cannot hold the cord within 1 mm of the skin and under 15° per ring. A visible depth ≤ 1.0 mm costs ≥ 24.8°; a bend ≤ 16.5° costs ~2 mm of narrowing.
- The rim compress follows the skin: 0.727 in dance_sway (round 10 0.761; the skin under the cord ~0.73). It reaches 0.748 only in the "smooth" setting.

**Why** (dance_heart / dance_sway, the strap's rings near the rim):
- **The bodice rim sinks into the skin.** Bodice shell vertices within 2 cm of the strap entries go newly into the skin by up to:
  - dance_sway 2.5 mm, dance_heart 2.6, hands_behind_head 2.4, reach_up_back 2.9, arms_up 2.9, idol_dance@78 4.2 mm;
  - 15-32 vertices past 0.5 mm, deepest at x ±0.088;
  - none in the arms-down poses.
- **There is no "under the rim" there.** Take the skin point 2.5 px below the neckline. At x ±0.065 the bodice stands 1.9-2.8 mm off it (rest 3.9). At x ±0.07-0.08, where the straps enter (x ±0.074), a ray along its normal finds no bodice within 3 cm in every raised pose (rest 4.9-6.7 mm). A cord riding the skin there is outside the bodice; a cord riding the bodice is inside the skin.
- **The elbow is the strap following both.** At the peak ring the bend is about half toward the skin (13-18°, the skin's own ridge: the skin's stage weights peak at the rim) and half sideways (13-20°, the bodice-ridden end moving apart from the skin-ridden strap). The weights along the strap are smooth: 肩補助2 0.15 → 0.17, 肩補助3 0.094 → 0.104 → 0.094 over the last 5 rings.
- **The first tucked ring.** Its centre is 0.17-0.33 mm inside the skin (dance_sway, dance_heart). The front ~1.1 mm of the cord stays outside, so it shows 97-99 % of its width from the front and meets the rim at full width in clay (verifier: "in clay the strap still meets the rim at full width"). Its deepest vertices are on the skin side of the cord. Keeping that ring under the rim needs a deeper hand-over, which pushes the end out through the bodice front (last row of the table).

**The other items** (the round-2 halter; numbers from the full merge below):
- **Hidden tucked end.** The compress on rings 52-53 (4.3-5.7 px under the neckline, the end of the hand-over) is below round 10 - 0.05 in:
  - high_kick 0.875, raise_bend 0.922, spin 0.874 and idol_dance@77 0.700;
  - the sweep finds no uncovered tucked vertex in high_kick, raise_bend and spin, and 3 at the rim's edge (0.0 mm deep) in idol_dance@77.
  - Round 10's strap ended 3 px under the rim on the skin's weights, so its end is not a like-for-like bound.
  - Softer hand-overs restore it (smoothed 10 mm: high_kick 0.897, raise_bend 0.940, idol@77 0.767), but they sink the visible rim rings 1.2 mm or push the end out of the bodice.
- **look_over_shoulder 0.683 (bound 0.690).** The right X strand's along-edges at ring 167-168 (rest -0.021, -0.083, 1.171). Without round 2's floor and upper-bust lift it is 0.693-0.696, but the arms-down sink comes back (hands_on_hips 1.37 mm, hug_self 1.24).
- **idol_dance@77 junction 1.569** (skin bound 1.535; the clip's worst frame 1.673 ≤ 1.69). A 20 mm rim follow gives 1.536, but the rim rings then sink 1.34 mm.

**Cross-part (for the bodice lane).** With the arms raised, the bodice shell's top rim at x 0.07-0.09 goes 2.4-4.2 mm into the skin. Keeping it ≥ ~2 mm off the skin there (as it is at x ≤ 0.065) would let the strap tuck under a real gap. The rim trade-off above would then go away.

**Full merge** (r11/integrate f5004c9 + this branch = the branch head 5266d89; the halter is the round-2 one):
- **Halter sweep** (all 417 core / extended poses and clip frames, the round-2 verifier's sweep2.py) reproduces round 2's numbers exactly (max difference 0). Visible-cord depth: 0.96 mm worst, 0 frames over 1 mm, 0 over 1 % past 0.5 mm.
  - Before (f5004c9 alone): 1.82 mm, 60 and 48 frames. Round 10: 2.17 mm, 34 and 17.
  - Counting rim-edge rings that the bodice leaves uncovered: 1.32 mm, 11 frames over 1 mm. Round 10, measured the same way: 1.32 mm, 8 frames.
- **Rim bends** (kink.py): the same as round 2. Rest 13.5° (ring 48), dance_heart 24.0, dance_sway 23.4, hands_behind_head 26.1, reach_up_back 25.3, idol_dance@81 25.1, arms_up 21.5, jump_tuck 17.7. Arms down: 9.8-10.2.
- **Motion report** (extended + clips + core, 2,498 s), against f5004c9 alone (2,502 s) and round 10:
  - The only rows that move are the halter's (the round-2 change; the same rows round 2's verifier found on 89f6117) and hair x garment crossings by up to 5 pairs.
  - acc_halter worst, round 10 / f5004c9 / now: stretch 1.637 / 1.634 / 1.673 (idol_dance, minor); compress 0.674 / 0.654 / 0.643; pen 2.2 / 1.9 / 1.4 mm; no flips. Halter pen is 0 in the six arms-down poses (f5004c9: 1.1-1.8 mm).
  - acc_choker is unchanged (1.264 / 0.539).
  - Issue counts per part are the same as f5004c9's (accessories 15, 8 major: the flower and leaf hair-pen ones round 10 already had).
  - Against round 2's full merge (89f6117 + this halter), no acc_* row changes. The rows that do differ are the bodice ribbon tails and the petticoat core, from f5004c9's own commits.
- **Gates on the full merge** (= the branch head):
  - check.py: CHECK OK, "62 meshes identical in a second process". Accessories 7,592 / 8,000; total 162,561 / 200,000.
  - rig_check, 17 core poses: RIG CHECK OK. Worst stretch squat 1.82 and arms_up 1.81 (body); worst pen side_bend 1.76 cm (skirt); knees ok; 66/66 PMX bone names.
  - Not run: export_pmx, pmx_reimport and motion_vmd (no mmd_tools).

**Images (integration round 3)**
- `integ3_rim_tradeoff.jpg`: the rim entry in clay, now / "mid" / "smooth" (see the trade-off table). hands_behind_head and reach_up_back (right strap, side), hands_behind_head (right strap, 3/4), dance_sway (left strap, side).
- `integ3_bodice_rim.jpg`: the bodice rim at the strap entries, at rest and in dance_heart, reach_up_back and dance_sway (cel, clay). With the arms up the rim's outer end sinks into the skin, and the trim line leaves the shell's edge and crosses the strap.


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
- **Integration round 2, `rig.py` accessories section only:** new `HALTER_LEAD_MAX`, `HALTER_LEAD_BONES` and `_halter_lead_cap` (called once in the halter branch of `_neck_cord_weights`); changed `HALTER_RIM_FOLLOW` (0.025 to 0.030), `HALTER_RIDE_SMOOTH` (0.010 to 0.008) and `HALTER_KEEP` (肩補助 x1.5, 首 x0.5). No shared-code lines.
- **Integration round 2, the part:** `STRING_FLOOR` (0 to 0.9 mm, now applied while the cord settles: `_floor_gap`, `_cage_height`, `_settle(..., floor)`), `STRING_LOW_LIFT` / `STRING_LOW_BAND`, and `RIDE_FULL` (4 to 5 px). Same face count; the geometry changes only on the lower chest.
- **Integration round 3:** no code change. The rim entry depends on the bodice's top rim by the straps (bodice lane): with the arms raised it sinks 2.4-4.2 mm into the skin at x ±0.07-0.09.

## Images
- `fix_choker_merged.jpg`: a scratch merge of r11/accessories with r11/head, hair-front, body-torso, bodice, hair-back, sleeves, skirt, petticoat and shoes (body-hands and body-legs conflict in `rig.py` and were left out), first build vs fixed, front / 3-4 / left / top.
- `fix_flower.jpg`: the centre (first build, fixed, bust scale, sheet), and the flower over r11/base's hair_front vs r11/hair-front.
- `choker.jpg`, `flower.jpg`, `halter.jpg`, `posed.jpg`: the first build vs round 10 beside the sheet and 风堇 (900 px).
- Integration round 3 dropped the sheets later rounds superseded (`fix_halter`, `fix_junction_macro`, `halter_zoom`, `integ_raised`, `integ_rest`, `integ_armsdown_rim`) and scaled `choker`, `flower`, `halter`, `posed`, `fix_choker_merged` and `fix_flower` to 900 px and `integ_neck` and `integ_flower_heart` to 800 px: the images are 1.10 MB in all (1.17 MB with this README).
