## r11 hair × garment crossings (hair-cross lane)

The integration review counted more hair × garment crossings in the arm-near-head poses than round 10. This lane measures crossings by curve length as well as by pair count. It looked at what lies in the hair in each named pose. In integration round 3 it traced the side-lock pops to the shoulder capsule and softened the push where that does not put hair into the body.

Where it stands after integration round 3:
- **Side-lock pops (round-2 verifier p2): partly fixed** in `rig._hair_collision`.
  - idol_dance per-object pops: long lock 49 / 35 → 28 / 33 mm; curls 45 / 45 mm as before. Round 10 has 21 / 19 and 8 / 8.
  - Every push soft enough to bring all four below round 10's put the lock or the curls into the shoulder: new hair pen majors, 15-26 % of the lock or curl (section 1, `06_soft_push_pen.jpg`). The brief also asks for no new hair pen, so the curls keep the hard push.
- **spin back-lock pop: fixed.** The last segment of a back lock pushes at most half its turn cap: 15.7 → 9.2 mm (round 10: 8.1).
- **Named poses (T2 / T3):** the crossings are as on `r11/integrate`.
  - jump_tuck: +13 pairs, +7 mm.
  - spin hair × skirt: +50 pairs from the tip push, still below round 10's.
  - What is above round 10's pair count is mesh density, hands inside the head (a test-pose fault), or the hair cap's floor inside the neck (hidden; the hair-front lane is rebuilding it). Section 3 has the numbers.
- **Issue totals** no longer count the clips' per-part pop / jitter rows (round-2 verifier p3). Those rows stay in their own table. The rig.py comment and CLAUDE.md now quote the back-arm push's measured bends.

### 1. Side locks flicked by the shoulder cap (rig.py, round 3)
Tracing every chain bone of idol_dance and spin frame by frame found the cause. The pops come from the shoulder capsule (`shoulder`, r 5.0 cm, 0-9 cm along 腕D), not the forearm or the hand:
- **Long lock (`横髪長_1/2`, @18).** The swinging shoulder sank 3 cm into the lock's unpushed point (axis distance 28 mm, kept 62 mm). The lock's mid probe sat at its turn cap (11.7 mm) for five frames. Then the shoulder left at 16 mm a frame, and the push fell from the cap to zero in one frame, a 46 mm spike at the lock tip.
- **Curls (`横髪巻_1`, @6 and @52).** The shoulder rose through the curl: its axis passed within 9-10 mm of the curl's unpushed point. Inside the near-axis fade (0.1-0.45 r), the push that held the curl out of the shoulder turned round in two frames: up 22 mm, then down 23.

Round 10 has the same capsules and almost the same distances (curl: 10.4 mm at @6). Its curl moved as far but over one more frame, under the spike test's ratio.

Variants were tried by editing the drivers of the integrate rig in place:
- pops: per-object, from vertex dumps (`scripts/object_pops.py`);
- crossings: pairs over the 41 poses and 7 clip frames (`scripts/crossings_by_pair.py`);
- pen: motion_check's idol_dance rows on the edited rig (major ≥ 0.03).

| shoulder push | idol_dance pops (lock L / R, curl L / R, mm) | new hair pen (pen_frac) | crossing pairs changed |
|---|---|---|---|
| hard (integrate) | 49 / 35 / 45 / 45 | — | — |
| lock, curl, curtain: exp cap 0.7, fade 0-0.8 r; lock as 'plane' | 16 / 13 / 12 / 7 | curl_L 6 → 26 %, curl_R 6 → 17 % (@53-56), lock_R 0 → 21 % (@20), dance_point curtain 2 → 5 % | jump_tuck 312 → 135, hand_to_shoulder 85 → 195, kneel_one 21 → 81, spin 92 → 174 |
| the same, curls with exp cap 1.0 and the common fade | 17 / 15 / 35 / 26 | curl_L 18 % (@6), lock_R 19 % | hand_to_shoulder 167, kneel_one 63 |
| lock as 'plane' only, hard or soft | 16-35 / 13-22 / 45 / 45 | lock_R 15-21 % (@20) | jump_tuck 135, hand_to_shoulder 89-195 |
| lock, both probes, exp cap 1.0 | 21 / 38 / 45 / 45 | none | hand_to_shoulder 199, kneel_one 55 |
| **lock mid probe, exp cap 1.0 (chosen)** | **28 / 33 / 45 / 45** | **none** | **jump_tuck 312 → 325** |

'exp cap': a push of depth x is k (1 − e^(−x/k)), k a share of the probe's turn cap. It has no corner where it saturates, so a push held at the cap leaves gradually. 'plane': the push keeps the side of the arm the hair lies on at rest; its centre lies 0.3 m beyond the axis point. It also moved the jump_tuck lock off the frill, but as the arm rose in idol_dance the lock's rest side turned toward her and pushed the lock in.

A curl's pop is the push that keeps it out of the shoulder as the shoulder rises through it. Without memory, a smoother push leaves it inside (`06_soft_push_pen.jpg`: with the soft push the curl at @56-57 sinks into the shoulder and the frill).

The code keeps the general form (`rig.HAIR_CAPSULE_SOFT`: per family 'fade' or 'plane', `_SOFT_CAPS`, `_SOFT_PROBES`, `_SOFT_CAP`, `_SOFT_FADE`, `HAIR_CAPSULE_PLANE`), with these measurements in its comment. It is set to the long lock's mid probe only. The rig is otherwise unchanged: 746 bones; hair collision 68 segments, 353 tests and 25 colliders; every driver is a simple expression.

Per-object hair pops (mm, frame). The round-10 values are the round-2 verifier's:

| clip | round 10 | integrate | now |
|---|---|---|---|
| idol_dance hair_lock_L | 20.6@85 | 49.2@18 | 28.4@84 |
| idol_dance hair_lock_R | 18.8@42 | 34.9@18 | 33.1@18 |
| idol_dance hair_curl_L / R | 8.1 / 7.6 | 44.6@6 / 44.6@52 | as integrate |
| idol_dance hair_cheek_L | 25.3@82 | 17.2@81 | 17.2@81 |
| spin hair_back | 8.1@37 | 15.7@40 | 9.2@40 |
| run hair_curl_L / R | 5.3 | 4.3 | 4.3 |

`03_lock_pop_strip.jpg` shows idol_dance @15-20 in object colours (rows: round 10, integrate, now). In integrate the long lock is pushed in against the neck at @16-17 and dropped; now it is pushed less and hangs.

### 2. The back-lock end in spin (rig.py, round 3)
At spin@40 the skirt's envelope collider (one per skirt chain, riding its root) swung away under lock 8's last segment. That segment was held 4-5 cm out at its turn cap and dropped 4.5 cm in a frame. The last segment of each back lock now pushes at most half its turn cap (`HAIR_COLLIDE_TIP_PUSH`): 15.7 → 9.2 mm (`05_spin_lock_end.jpg`).

The cost is in spin's hair × skirt: 1044 / 1307 → 1094 / 1430 (pairs / mm). That is still below round 10's 1352 / 1723. jump_tuck's hair × skirt drops from 198 to 186.

### 3. The named poses, object by object
Measured with `scripts/crossings_by_pair.py`:
- **Depth** is the p90 distance from the other surface of the vertices within 4 cm of the crossing that changed side since rest. It is a proxy; on the thin, ruffled frill it reads high.
- **At r10 density** scales each object pair's count by (1/h_a + 1/h_b) at round 10 over the same now, where h is the median edge length (`data/median_edge_mm_*.json`, `scripts/density_rescale.py`). For one curve, the pair count grows with how many edges of either mesh it crosses.

Round 11's meshes are finer where these poses cross:

| object | round 10 (mm) | now (mm) |
|---|---|---|
| sleeve_ruffle | 4.79 | 2.50 |
| sleeve_cuff | 4.32 | 3.00 |
| hair_back_shell | 16.2 | 4.0 |
| hair_bangs | 6.9 | 4.1 |
| hair_curl | 7.9 | 3.2 |

The same curve therefore gives 25-45% more pairs now.

Pairs / curve mm per pose:

| pose | round 10 | integrate = now | at r10 density | top pairs now (curve mm, depth p90 mm) |
|---|---|---|---|---|
| hands_behind_head | 5978 / 6995 | 7349 / 6900 | 5961 | hair_cap × sleeve_cuff 1394, 25; hair_back × sleeve_balloon 907, 17; hair_cap × cuff_under 593, 23 |
| dance_heart (= idol_dance@48) | 3678 / 4340 | 6042 / 5232 | 4564 | hair_bangs × cuff_under 1194, 29; hair_cap × cuff_under 716, 33; hair_bangs × cuff 695, 31 |
| reach_up_back | 4231 / 6424 | 4709 / 4798 | 3079 | hair_back × sleeve_ruffle 688; hair_cap × balloon 560 (nape, 頭-weighted) |
| jump_tuck | 112 / 122 | 312 / 239 (now 325 / 246) | 75 | hair_lock_L / R × ruffle 119 + 119 |
| test | 88 / 46 | 107 / 47 | 109 | hair_cap × acc_choker 30, hair_cap × acc_halter 18 |
| dance_point | 90 / 51 | 151 / 61 | 138 | hair_cap × choker 31, × halter 19, curl × ruffle 11 |
| lie_back_elbows | 71 / 41 | 85 / 34 | 87 | hair_cap × choker 19, × halter 14 |
| hug_self | 28 / 20 | 44 / 18 | 45 | hair_cap × choker 13, × halter 5 |
| swing, hair × skirt | 154 / 207 | 176 / 200 | 162 | hair_back_side × skirt 200 |

What lies there:
- **hands_behind_head, dance_heart: the hands are inside the head** (`02`, round 2).
  - The wrists sit at (±0.060, −0.003, 1.321) and (0.004 / −0.035, −0.097, 1.37). The hand skin is 72 mm and 34 mm (p90) inside the hair cap; round 10's is 70 mm.
  - The cuffs are 25-35 mm deep in the cap, the bangs and the scalp-side locks. All of that hair is 頭-rigid, so no chain can move it.
  - At round 10's density, hands_behind_head matches round 10's count (5961 vs 5978), and its curve is lower.
  - dance_heart's excess is the cuff's new under tier (`sleeve_cuff_under`, sleeves lane), which round 10 did not have: 1194 + 716 mm.
  - The 18 pose variants with the hands behind the head instead are committed (`scripts/pose_variants.py` and `pose_variants_measure.py`; results in `data/pose_variants_r10.json` and `data/pose_variants_r11.json`). 15 of their 18 curves are below round 10's.
- **reach_up_back:** the shoulder frill and the upper balloons lie behind the nape, where the hair is 50-80% 頭 (`HAIR_HEAD_FADE`). The curve is 25% below round 10's, and the count at round 10's density is 3079 against 4231.
- **jump_tuck:** with the arm raised forward, the long lock lies through the frill on the inner side of the arm. The radial push is at the lock's mid-probe turn cap (11.7 mm against a 24 mm depth). The 'plane' push cleared it (135 / 109) but put the lock into the shoulder in idol_dance (section 1). At round 10's density the count is 75 against 112.
- **test, dance_point, lie_back_elbows, hug_self:** the extra pairs are the hair cap's floor crossing the choker and halter inside the neck.
  - The cap reaches down to z 1.20 behind the neck; the choker sits at z 1.20-1.22.
  - The curves are 13-61 mm, at round 10's level: 46-51 mm, the same object pairs.
  - With the head and face shown, the crossing is inside the jaw and neck (`07_cap_floor_hidden.jpg`).
  - The hair-front lane is rebuilding that floor (a nape closure, r11/hair-front 67eee09), so the crossing is left to it.
- **swing:** the side lock ends cross the skirt's flare. The curve is below round 10's (200 vs 207); the count at round 10's density is 162 against 154.

### 4. Measures in tools/motion_check.py
- Each cross row carries `mm`, the length of the new intersection curve (`tri_cut_length`), and `top`, its three longest object pairs. The report shows them in the 'cross mm' column, not gated; a clip shows its longest frame.
- The clips get one pop and one jitter row per part (`by_part`; the report's 'Clips: pop mm / jitter per part' table), so a skirt pop no longer hides a hair pop.
  - Round 3: `issues()` skips the by_part rows, so totals compare with older reports.
  - On round 10's `main` with this tool, the totals and every row match the round-10 report.

### 5. Earlier rounds: back locks against a swinging arm (off)
Round 1 let the back locks beside the arms meet bag-sized arm capsules (`HAIR_COLLIDE_BACK_ARMS`). The locks stood out as stiff rods and popped (run 21 mm). Round 2 tried a soft push with a drape. Outer back locks (後髪束0-2 and 11-13) in walk, run and idol_dance@56-80:

| variant | max bend at a joint | max segment from straight down | run pop hair_back / _side | idol_dance pop hair_back / _side |
|---|---|---|---|---|
| off (integrate and now) | 24° | 52° | 0 / 0 | 7.1 / 0 |
| hard push (round 1) | 47° | 88° | 20.9 / 7.0 | 12.0 / 15.2 |
| soft push 12° / 6° + drape | 29° | 62° | 13.9 / 9.3 | 7.1 / 10.8 |
| soft push 8° / 4° + drape | 27° | 55° | 11.2 / 6.0 | 7.1 / 9.6 |

The run's arm passes a lock in about 6 frames a stride, so any lift that clears the bag pops. The push stays off.
- The code and these numbers are in `rig.py` and CLAUDE.md; round 3 corrected their bend figures to this table.
- `01_back_locks_arm_push.jpg` shows the variants.

### 6. Full-merge motion report
Scratch worktree: `r11/integrate` f5004c9 with this branch merged (ac7bd8b, a fast-forward), run with `rig_check.py -- --quick --no-core --extended --report-core --motion`, 2228 s.

Reports compared:
- **r10**: round 10's `main` with the mm column.
- **integrate**: f5004c9 plus the lane's tools, before round 3 (3685f32). Its geometry and motion are those of `r11/integrate`.
- **now**: the merge above.

Issues are counted without the per-part pop / jitter rows on every side, so the totals compare:

| | issues | majors | hair issues | hair majors |
|---|---|---|---|---|
| r10 | 484 | 152 | 92 | 32 |
| integrate | 471 | 136 | 71 | 22 |
| now | 471 | 136 | 71 | 22 |

Against integrate: no issue is new or gone and no level changes. The integrate report lists 505 / 161 with the per-part rows counted; the tool now leaves them out.

The brief's rows, as pairs / curve mm. A clip's count is its worst-count frame and its curve its longest frame:

| row | r10 | integrate | now |
|---|---|---|---|
| hands_behind_head | 5978 / 6995 | 7349 / 6900 | 7349 / 6900 |
| dance_heart | 3678 / 4340 | 6042 / 5232 | 6042 / 5232 |
| idol_dance clip | 4573 / 7366 | 6042 / 5259 | 6042 / 5259 |
| reach_up_back | 4231 / 6424 | 4709 / 4798 | 4709 / 4798 |
| jump_tuck, hair × garment | 112 / 122 | 312 / 239 | 325 / 246 |
| jump_tuck, hair × skirt | 1720 / 1172 | 198 / 138 | 186 / 136 |
| spin clip, hair × skirt | 1352 / 1723 | 1044 / 1307 | 1094 / 1430 |
| spin clip, hair × garment | 74 / 44 | 92 / 39 | 92 / 39 |
| swing, hair × skirt | 154 / 207 | 176 / 200 | 176 / 200 |
| test | 88 / 46 | 107 / 47 | 107 / 47 |
| dance_point | 90 / 51 | 151 / 61 | 151 / 61 |
| lie_back_elbows | 71 / 41 | 85 / 34 | 85 / 34 |
| hug_self | 28 / 20 | 44 / 18 | 44 / 18 |
| walk (core) | 1201 / 2397 | 1012 / 1381 | 1012 / 1381 |
| run clip | 1184 / 2315 | 534 / 699 | 534 / 699 |
| all hair rows | 32621 / 44.07 m | 31382 / 29.18 m | 31431 / 29.30 m |

Clip hair pops, from the per-part table (mm):
- idol_dance: hair_front 49.2 (hair_lock_L@18) → 44.6 (hair_curl_R@52); hair_back 7.1@73.
- spin: hair_back 15.7 → 9.2@40; hair_front 5.3 → 4.8.
- run: hair_front 4.3. walk: hair_back 3.2.

A second run of the same code in the lane worktree, on another node, gives the same issue set.

### Gates (r11/hair-back-plate = r11/integrate f5004c9 + this lane)
- check.py: CHECK OK. REPEAT: 62 meshes identical in a second process. Budgets: hair_back 30,490 / 34,000, hair_front 14,629 / 16,000, sleeves 17,752 / 18,000, total 162,561 / 200,000. The geometry is unchanged; this lane changes the rig only.
- rig_check.py, full run with the repeatability checks: RIG CHECK OK.
  - 746 bones; 66/66 standard PMX bone names; IK knee 0.04 mm, toe 0.03 mm; eyes 0.00 mm; weight asymmetry max 0.0022.
  - Hair collision: 68 segments, 353 tests, 25 colliders, as on `r11/integrate`.
  - Worst stretch: squat 1.82; head_left / head_right 1.40 / 1.41 (hair_back); swing 1.56 (hair_back_shell).
  - Worst penetration: side_bend 1.76 cm.
- `strip_blender_only` removes 396 of 746 bones. It leaves the same 350 bone names as `r11/integrate`, with no dangling driver targets, no invalid drivers and no colliders.
- The rig built from the code reproduces the chosen driver variant exactly: every per-object pop and every crossing pair over the 41 poses and 7 clip frames.

### Images
- `01_back_locks_arm_push.jpg` (round 2): the outer back locks over a swinging arm. Columns: hard push (rods), soft push with drape (off), now.
- `02_head_poses_hands_in_head.jpg` (round 2): hands_behind_head, the hbh_d variant, dance_heart and reach_up_back. Several views have the hair hidden, which shows the hands in the head.
- `03_lock_pop_strip.jpg`: idol_dance @15-20 at the long lock, object colours. Rows: round 10, integrate, now.
- `04_jump_tuck_spin11.jpg`: the jump_tuck lock and frill (front cel, front and side object colours) and spin@11 from behind (cel, object colours). Rows: round 10, integrate, now.
- `05_spin_lock_end.jpg`: spin @37-42 from behind at lock 8's end. Rows: integrate, now.
- `06_soft_push_pen.jpg`: idol_dance @54-57 at the left curl, integrate | the rejected soft push (object colours, clay @57). With the soft push the curl sinks into the shoulder and frill.
- `07_cap_floor_hidden.jpg`: test, under the chin. Cel and object colours with everything shown, then the hair cap alone: its floor meets the choker inside the neck.

### Not done / open
- **Curl pops.** idol_dance's curl pops (45 mm @6 / @52) and the long lock's (28 / 33 mm) stay above round 10's. Lowering them further trades for hair inside the shoulder (section 1). A push with memory (MMD physics, or a cached previous frame) would be needed.
- **Pair counts above round 10.** hands_behind_head, dance_heart (= idol_dance@48), reach_up_back, jump_tuck, test, dance_point, lie_back_elbows, hug_self and swing are all above round 10's count. hands_behind_head, reach_up_back, jump_tuck, lie_back_elbows, hug_self and swing are below its curve. Meeting the count needs:
  - a pose decision (the hands are inside the head);
  - the sleeves lane (the cuff's under tier, the frill);
  - the hair-front lane (the cap floor at the choker).
- **Back locks against a swinging arm.** They pass through the arm's bag in walk and run, at integrate's level, below round 10's.
- **Not run:** export_pmx, pmx_reimport and motion_vmd (no mmd_tools on the cluster), and the Codex review.
