## r11 hair × garment crossings (hair-cross lane)

The integration review counted more hair × garment crossings in the arm-near-head poses than round 10. This lane measured them by length as well as by count, tried to make the back locks give way to a swinging arm, and looked at what lies in the hair in the arm-on-head poses.

Where it stands after integration round 2:
- **Measure.** `tools/motion_check.py` gives each crossing row its curve length in mm. Clip pops and jitter now have one row per part.
- **Back locks against the arms.** The round-1 push (`HAIR_COLLIDE_BACK_ARMS`) is off again. The hair moves exactly as on `r11/integrate`: 0.0 mm difference over all 418 poses and clip frames.
- **Named poses.** The brief's arm-on-head poses still fail its count AND curve target. Their hands, cuffs and upper sleeves lie in hair that rides the head. In hands_behind_head and dance_heart the hands are inside the head itself, in round 10 as in round 11.

### 1. Crossing curve length (tools/motion_check.py, round 1)
`cross` counts new crossing triangle pairs. That count grows with mesh density: round 11's sleeves have 18k faces and hair_back has 30k. Each cross row now also carries:
- `mm`: the length of the new intersection curve, summed over the crossing pairs (edge against triangle, both ways);
- `top`: the three object pairs with the most curve.

The report gains a "cross mm" column, which is not gated; for a clip it shows the longest frame. Run on round 10's `main` with only this column added, the counts match the round-10 report exactly. Over all hair rows, `r11/integrate` has 29.2 m of curve against round 10's 44.1 m.

### 2. Pop and jitter per part (tools/motion_check.py, round 2)
A clip used to keep a single worst pop row and a single worst jitter row. A skirt or body pop of 55 mm then hid any hair pop: the round-1 push's 21 mm hair pops in the run never reached the report.

`run_clip` now adds one pop row and one jitter row for every other part (`by_part: True`), and `report.md` has a table "Clips: pop mm / jitter per part". The clip table still shows the worst row.

These rows are new issues that older reports do not have. Compare issue counts without them (section 5 does).

### 3. Back locks against a swinging arm: tried, measured, off (rig.py)
Round 1 let the back locks beside the arms meet bag-sized arm capsules. The verifier found two problems:
- The pushed locks stood out as stiff rods: 35-47° at one joint, lower segments up to 88° from straight down.
- They flicked out and back within a frame or two: new hair pops of 21 mm (run) and 15 mm (idol_dance), where `r11/integrate` has none.

Round 2 tried two fixes:
- **Drape:** a helper `_hcg` hangs each segment from its parent's ghost, and the segment's ghost turns `HAIR_COLLIDE_BACK_DRAPE` (0.8) of the way back toward it. This fades in with the parent's contact.
- **Soft push:** the push starts `HAIR_COLLIDE_BACK_AHEAD` before contact and rises as a smoothstep of the depth to at most `HAIR_COLLIDE_BACK_TURN`. It has no corner where it starts or where it is capped.

Outer back locks (後髪束0-2 and 11-13) in walk, run and idol_dance@56-80. Pops use motion_check's `_spike` per object (major is 6 mm):

| variant | max bend at a joint | max segment angle from straight down | run pop hair_back / hair_back_side | idol_dance pop hair_back / hair_back_side |
|---|---|---|---|---|
| `r11/integrate`, and now (push off) | 24° | 52° | 0 / 0 | 7.1 / 0 |
| round 1: hard push | 47° | 88° | 20.9 / 7.0 | 12.0 / 15.2 |
| drape + soft onset | 45° | 79° | 20.1 / 19.6 | 9.5 / 20.1 |
| soft push 12° / 6° + drape | 29° | 62° | 13.9 / 9.3 | 7.1 / 10.8 |
| soft push 8° / 4° + drape | 27° | 55° | 11.2 / 6.0 | 7.1 / 9.6 |

The drape and the soft push remove the rods (01, middle column), and the run's hair jitter falls from 0.080 to 0.009. The pops do not go away, because the run's arm passes a lock in about 6 frames a stride. A lift that clears the bag within that time is a bump in the lock's acceleration, and the spike test reads that as a pop: run frames 5-11 lift the lock end 4.8 cm and drop it again.

So the push is off: `HAIR_COLLIDE_BACK_ARMS = ()`. The code stays, with these measurements in its comment, and turning it back on is a one-line change. Without the push:
- The rig is the same as `r11/integrate`'s: 746 bones; hair collision with 68 segments, 353 tests and 25 colliders.
- The walk and run crossings are back to `r11/integrate`'s level, which is still below round 10's (table in section 5).
- MMD's physics does this job in the PMX.

### 4. The brief's arm-on-head poses: the arms are in head-rigid hair
The rig weights the hair to 頭 above the eyes and fades it to the chains by the choker (`HAIR_HEAD_FADE`). Collision moves chain segments only, so hair that rides the head cannot give way to an arm. What lies there, measured on the `r11/integrate` rig (r10: round 10's rig):
- **hands_behind_head:** the wrists sit at (±0.060, −0.003, 1.321), 6 cm from the midline at ear height. The rest hair cap spans x ±0.10, y −0.141…0.065, so the wrists are inside the head. The hand skin is 72 mm (p90) inside the hair cap's closed surface; round 10 has 70 mm, with the wrists at ±0.068. With the hair hidden, the hands overlap the skull at the ears (02, top row).
- **dance_heart** (= idol_dance@48): the wrists sit at (0.004 / −0.035, −0.097, 1.37), in the bangs at the brow. The hand skin is 34 mm (p90) inside the cap, and the cuffs 48-53 mm. The docstring says "a heart over the head" (02, third row).
- **reach_up_back:** the hands are clear. The upper sleeves and the elbow frill lie in the nape hair behind the head (02, bottom row). That hair rests at z ≈ 1.28, where 82% of its weight is on 頭 (`HAIR_HEAD_FADE` runs 1.155 → 1.329 m).
- **jump_tuck:** the long side lock's second segment (横髪長_1) crosses the shoulder frill (`sleeve_ruffle`), 119 mm per side (round 10: 61 mm per side). The shoulder capsule already tests that segment. The frill stands outside the capsule, which is sized to the arm (`HAIR_CAPSULE_Q` 60). A frill-sized capsule for this family would also push the lock and curl roots by the jaw in raised-arm poses (round 8: a 330 mm pop in idol_dance).

Pose variants were measured in both rounds and are **not committed**: `tools/motion_poses.py` is outside this lane, and changing a test pose moves every lane's numbers. Each cell gives hair × garment pairs / curve mm; the top object pairs are round 11's.

| pose | r10 | r11 | r11 top pairs |
|---|---|---|---|
| hands_behind_head (as defined) | 5978 / 6995 | 7349 / 6900 | hair_cap × sleeve_cuff 1394, hair_back × sleeve_balloon 907 |
| hbh_d: hands clasped behind the hair (wrists y 0.131) | 1178 / 1138 | 2781 / 2243 | hair_back × sleeve_ruffle 827, × sleeve_cuff_under 642 |
| dance_heart (as defined) | 3678 / 4340 | 6042 / 5232 | hair_bangs × sleeve_cuff_under 1194, hair_cap × sleeve_cuff_under 716 |
| heart_a: hands 4 cm higher | 2995 / 3234 | 4081 / 3753 | hair_bangs × sleeve_cuff_under 755, hair_cap × sleeve_cuff_under 538 |
| reach_up_back (as defined) | 4231 / 6424 | 4709 / 4798 | hair_back × sleeve_ruffle 688, hair_cap × sleeve_balloon 560 |
| rub_c: arms further out (0.45 for 0.30) | 2803 / 4149 | 4311 / 3549 | hair_back × sleeve_ruffle 649, × sleeve_balloon 254 |

Over 18 such variants:
- The count is above round 10's in all 18. It follows mesh density.
- The curve is below round 10's in 15. In the other three (dance_heart, heart_a, hbh_d), round 11's own sleeve parts carry the excess: the cuff's new under tier (`sleeve_cuff_under`, 0.8-1.9 m) and the denser shoulder frill. Both are the sleeves lane's.

Even with the poses corrected, the brief's "count at or below round 10 AND curve below" cannot be met from the hair side.

### 5. Full-merge motion report
Reports compared:
- **r10**: round 10's `main`, ab69d8b, with the mm column added.
- **integ**: `r11/integrate` 89f6117, with the mm column added (the verifier's report).
- **round 1**: 89f6117 + a768bc5, which had the hard push.
- **now**: `r11/integrate` 89f6117 + this branch, fdf5f45, run in a scratch merge.

Hair × garment and hair × skirt crossings, as new pairs / curve mm. A clip's count is its worst-count frame, and its curve its longest frame.

| row | r10 | integ | round 1 | now |
|---|---|---|---|---|
| hands_behind_head | 5978 / 6995 | 7349 / 6900 | 7349 / 6900 | 7349 / 6900 |
| dance_heart | 3678 / 4340 | 6042 / 5232 | 6042 / 5232 | 6042 / 5232 |
| idol_dance clip | 4573 / 7366 | 6042 / 5259 | 6042 / 5259 | 6042 / 5259 |
| reach_up_back | 4231 / 6424 | 4709 / 4798 | 4709 / 4798 | 4709 / 4798 |
| jump_tuck, hair × garment | 112 / 122 | 312 / 239 | 312 / 239 | 312 / 239 |
| jump_tuck, hair × skirt | 1720 / 1172 | 198 / 138 | 198 / 138 | 198 / 138 |
| spin clip, hair × skirt | 1352 / 1723 | 1044 / 1307 | 1044 / 1307 | 1044 / 1307 |
| walk (core) | 1201 / 2397 | 1012 / 1381 | 324 / 481 | 1012 / 1381 |
| run_r | 876 / 1576 | 407 / 588 | 165 / 173 | 407 / 588 |
| run clip | 1184 / 2315 | 534 / 699 | 284 / 343 | 534 / 699 |
| all hair rows | 32621 / 44.07 m | 31382 / 29.18 m | 30116 / 27.36 m | 31382 / 29.18 m |

Without the new per-part rows, "now" matches integ row for row:
- No row differs by more than 0.1%.
- No issue is new or gone, and no level changes.
- Issues: 484, majors 138; hair issues 71, hair majors 22. Round 10 had 479 / 152 / 91 / 32.

With the per-part pop and jitter rows the report lists 518 issues and 163 majors. Of those, 34 issue rows and 25 majors are the new rows; 6 are hair rows.

Clip hair pops, per part (mm):
- run: hair_back 0.0, hair_front 4.3 (hair_curl_L@3).
- idol_dance: hair_back 7.1@73, hair_front 49.2 (hair_lock_L@18).
- spin: hair_back 15.7@40, hair_front 5.3.
- walk: hair_back 3.2.

All are as on integ; the round-1 push had added run hair_back 20.9 and idol_dance hair_back_side 15.2. Hair motion over all 418 poses and clip frames differs from integ by 0.0 mm.

### Gates (this branch)
- check.py: CHECK OK. hair_back 30,490 / 34,000, sleeves 17,752 / 18,000, total 162,561 / 200,000.
- rig_check.py, full run with the repeatability checks: RIG CHECK OK.
  - 746 bones (round 1 had 944); hair collision with 68 segments, 353 tests and 25 colliders, as on `r11/integrate`.
  - 66/66 standard PMX bone names; IK knee 0.04 mm; eyes 0.00 mm.
  - Worst stretch: squat 1.82; head_left / head_right 1.40 / 1.41 (hair_back); swing 1.56 (hair_back_shell).
  - Worst penetration: side_bend 1.76 cm.
- The soft push and drape with the push switched on (8° / 4°) were built and rigged on this code. The rig builds, and every driver is a simple expression within 255 characters.
- `strip_blender_only` was run on both rigs:
  - push on: removes 604 of 954 bones;
  - push off: removes 396 of 746 bones.

  Both leave the same 350 bones as `r11/integrate`, with no dangling driver targets and no colliders left.

### Images
- `01_back_locks_arm_push.jpg`: the outer back locks over a swinging arm in walk, run@8, idol_dance@68 and @70, zoomed on the lock. Left: round 1's hard push (rods). Middle: soft push 8° / 4° with the drape, which is off (no rods, but 10-11 mm pops). Right: now, the same as `r11/integrate` (the lock hangs and passes through the bag).
- `02_head_poses_hands_in_head.jpg`, rows:
  1. hands_behind_head as defined: round 10 and 11 side with the hair hidden, round 11 from above with the hair hidden (face up), and from behind.
  2. The hbh_d variant: round 10 and 11 from behind, then round 11 side and top with the hair hidden.
  3. dance_heart: round 10 and 11 side with the hair hidden, round 11 top without and with the hair.
  4. reach_up_back: round 10 and 11 from behind in object colours, round 11 from behind with the hair hidden, and from the side.

### Not done / open
- The brief's arm-on-head targets (section 4) are not met. Meeting them needs one of these, outside this lane:
  - a pose decision (hands_behind_head and dance_heart put the hands inside the head);
  - smaller cuff under tiers and frills (sleeves);
  - letting the hair at the nape yield to the arms, which also gives up the head-rigid weighting that keeps the curtain off the shoulders in head turns.
- jump_tuck: the long side lock through the shoulder frill (2 × 119 mm) is as on `r11/integrate`.
- The back locks pass through a swinging arm's bag in walk and run, at `r11/integrate`'s level.
- The spin pop on lock 後髪束8_4@40 (15.7 mm) and the idol_dance side-lock pops (hair_lock 49.8 mm, hair_curl 45.2 mm) are older than this lane and unchanged. The per-part rows now show them.
- Not run: export_pmx, pmx_reimport and motion_vmd (no mmd_tools on the cluster), and the Codex review.
