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

## Images
- `fix_halter.jpg`: idol_dance@78, hands_behind_head, dance_heart and jump_tuck, first build vs fixed. The columns are the junction (cel), the rim (clay) and the side view (clay).
- `fix_junction_macro.jpg`: the lower-left X-strand junction at macro scale (cel + wire) in idol_dance@78 / @80, hands_behind_head and dance_sway, first build vs fixed.
- `fix_choker_merged.jpg`: a scratch merge of r11/accessories with r11/head, hair-front, body-torso, bodice, hair-back, sleeves, skirt, petticoat and shoes (body-hands and body-legs conflict in `rig.py` and were left out), first build vs fixed, front / 3-4 / left / top.
- `fix_flower.jpg`: the centre (first build, fixed, bust scale, sheet), and the flower over r11/base's hair_front vs r11/hair-front.
- `choker.jpg`, `flower.jpg`, `halter.jpg`, `halter_zoom.jpg`, `posed.jpg`: the first build vs round 10 beside the sheet and 风堇.
