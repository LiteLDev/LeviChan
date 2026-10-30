# r11 petticoat: three tiers of scalloped bells

Branch `r11/petticoat`, built on `r11/base`. Only `levi/parts/petticoat.py` changes geometry.
The petticoat-specific parts of `levi/rig.py` change, and `tools/motion_check.py` gets one
new count. Since the integration fix below, the branch also carries `r11/skirt` (merged at
e8b439f, unchanged), so it supersedes both parts. It carries `r11/integrate` up to bcd38b0;
the round-3 numbers below are from `r11/integrate` 415f85d with this branch merged in (no
conflicts).

## Integration review, round 3
The verifier's round-2 result: 16 skirt / petticoat stretch rows above min(round 10,
petticoat alone), summed excess 0.92 (walk, walk clip, curtsy, test-adjacent front hems;
sit_chair / sit_stand / jump_tuck / lie_back seated hems; seiza, dance rows), plus three p3s.
Now, on the full merge (`r11/integrate` 415f85d + this branch, full report): **1 row, summed
excess 0.009** (seiza skirt 1.502 against petticoat alone's 1.493; round 10 1.730). jump_tuck
is 1.921 against 1.920 (inside the 0.005 tolerance), dance_sway 1.237 against 1.238.

**What made the rows** (scratch tools and dumps in `work/integ_scratch/pt_r3`):
- *Front hems at walking pitches* (walk, walk clip, curtsy; skirt and tiers). A dump of the
  drape stages at 40 deg of thigh pitch: the chain over the forward thigh lifts its hem 38
  deg, and chains 0, 1 and 2 hang exactly the ring cap's step lower each (11.3 / 12.1 / 13.5
  deg): the cone, not the clearance, set the front's shape. The worst edges (1.6-2.2 mm ring
  edges of tier1's hem at -167 deg) grow by the forward-displacement difference of chains 0
  and 1 (157 vs 82 mm). Their weights are the petticoat-alone ones to 0.005; 1.81 against
  1.74 came from 2-6 deg of yaw.
- *Seated hems* (sit_chair, sit_stand, jump_tuck, lie_back). At 80 deg the cone carried one
  chain's hem kick (chain 14, 78 deg from the gather's 12 deg yaw) round the side in 14 deg
  steps as hem-only lifts, so chains 10-13 had their hem segments up to 10 deg above their
  middle ones; the inner tier's hem stretched x1.94 where chain 9 (12.6 deg) met chain 10
  (23.5 deg).
- *Tier weights.* Binned 4 deg round the hem, the surface-smoothed, shared, pruned and
  refitted weights follow a quadratic B-spline's profile (0.59 / 0.38 against 0.615 / 0.376),
  but their local slope changes +-20% from lobe to lobe. The worst stretch sat wherever a
  steep step met the biggest difference between two chains (edge decompositions: walk tier1
  at -167, run_l tier2 at -137, sit_chair tier2 at 49 deg).
- *The solve stays sensitive.* Tier geometry reshuffles the tables: `LIFT_PINCH` 0.06 / 0
  took walk to x1.51 / 1.58 but lie_back to x2.21 / 2.36 and the run clip to x2.02. With
  round 2's chains and tables forced (isolation runs), the same geometry gives x1.70 in walk
  and x1.96 in sit_chair, so the gain came from the reshuffle. Not used.

**Fix** (`levi/rig.py`, petticoat and drape sections):
- `TIER_FIELD`: the tiers take one analytic field of (angle, height). Round the ring a vertex
  blends the nearest chains by a quadratic B-spline of its angle, knots 1.05 chain steps
  apart, where it rides the last segment; above that it hands over (within a quarter
  segment) to the plain two-chain blend that also splits two segments. That is at most four
  bones by construction, with no smoothing, prune or refit. The same weights apply at the
  same (angle, height) on every tier, and the core's seam takes them too. Tier x tier
  crossings 114 -> 0 (cross_legged 89, run_r 14, run 11).
- `DRAPE_RING_CAP_PITCH` ((45, 75), 0.55): below 45 deg of thigh pitch the cone's steps are
  0.55 of `DRAPE_RING_CAP`, full again by 75 deg. Above 75 deg (seated, kicks) the cone is
  as before, where a narrower one made round 8's bowl. Where the cap is narrowed, the
  tables are smoothed over the pitch again after the cone (on or above it) and kept
  monotone (`_smooth_above`, `_monotone`). Without that, a hem the cone lifted at 48 deg
  dropped back by 63 deg and the run clip had a 0.27 strain spike at frame 14. Smoothed at
  every pitch, cross_legged's skirt x petticoat crossings went 226 -> 384.
- `DRAPE_UP` 10 -> 7: the middle segment follows a hem the cone lifted (no 10 deg kick at
  the lower joint, which the tiers straddle).
- `DRAPE_STRAIN` 0.3 -> 0.26: the gather keeps the ring tighter at the innermost cloth, now
  the inner tier's hem.

**Search** (41 poses and clip frames per variant, the motion report's metrics; rows over the
bound counted per pose and frame, so sit_stand counts three times; `pt_r3/variants_summary.txt`):

| variant | rows | excess | petticoat pen max | tier x tier |
|---|---|---|---|---|
| round 2 | 19 | 1.18 | 2.17 cm | 114 |
| tier smoothing 8 cm | 15 | 0.97 | 2.17 | 72 |
| tiers without refit | 31 | 5.56 | 2.17 | 136 |
| hem cap 11 deg at every pitch | 15 | 1.37 | 2.14 | 102 |
| `DRAPE_STRAIN` 0.2 | 12 | 0.70 | 2.58 | 125 |
| `LIFT_PINCH` 0.06 / 0 (geometry) | 20 / 13 | 1.18 / 1.13 | 2.84 / 3.08 | 101 / 51 |
| tier field alone | 21 | 1.01 | 2.17 | 0 |
| cap 0.7 below 45-75 deg | 14 | 0.84 | 2.17 | 112 |
| field + cap 0.55 | 9 | 0.38 | 2.17 | 0 |
| ... + finer yaw grid / `DRAPE_UP` 6 | 17 / 14 | 0.69 / 0.59 | 2.95 / 2.05 | 0 |
| ... + `DRAPE_STRAIN` 0.25, `DRAPE_UP` 6 / 7 | 8 / 7 | 0.16 / 0.09 | 2.55 / 2.54 | 0 |
| ... + `DRAPE_STRAIN` 0.26, `DRAPE_UP` 7 | 3 | 0.06 | 2.27 | 0 |
| ... + smoothing after the cone at every pitch | 6 | 0.09 | 2.84 | 0 |
| ... + smoothing where the cap is narrowed | 2 | 0.03 | 2.27 | 0 |
| ... + field knots 1.05 apart (this branch) | 1 | 0.009 | 2.27 | 0 |

Neighbours of the last settings (`DRAPE_UP` 5 / 8, `DRAPE_STRAIN` 0.22-0.28, cap 0.5 / 0.6,
ranges 40-75 / 50-80, knots 1.1 apart) gave 3-17 rows: the solve is still sensitive, and
the settings are the best of that neighbourhood, not a smooth optimum.

**Full merge, full report** (`motion_r3.txt`): round 10 / petticoat alone / round 2 / now.

| row | round 10 | petticoat alone | round 2 | now |
|---|---|---|---|---|
| walk petticoat / skirt | 1.740 / 1.514 | 1.744 / 1.521 | 1.806 / 1.551 | 1.567 / 1.481 |
| walk clip petticoat / skirt | 1.606 / 1.354 | 1.597 / 1.382 | 1.638 / 1.422 | 1.415 / 1.312 |
| curtsy petticoat / skirt | 1.443 / 1.321 | 1.535 / 1.344 | 1.580 / 1.387 | 1.349 / 1.270 |
| sit_chair / sit_stand petticoat | 2.030 | 1.808 / 1.818 | 1.944 | 1.759 |
| jump_tuck petticoat | 2.060 | 1.920 | 2.010 | 1.921 |
| lie_back petticoat | 2.249 | 2.151 | 2.159 | 2.040 |
| squat petticoat | 1.544 | 1.532 | 1.546 | 1.384 |
| seiza skirt | 1.730 | 1.493 | 1.555 | 1.502 |
| dance_sway petticoat | 1.354 | 1.238 | 1.244 | 1.237 |
| dance_clap skirt | 1.328 | 1.272 | 1.312 | 1.232 |
| cross_legged petticoat / skirt | 2.177 / 2.604 | 2.256 / 2.712 | 2.261 / 2.067 | 2.129 / 2.050 |
| lie_back petticoat pen, pen_frac | 0.54 cm, 0.5% | 0.95, 1.5% | 1.45, 2.4% | 1.15, 1.9% |
| kneel_one / sit_chair pen_frac | 0.9 / 2.1% | 0.7 / 1.5% | 1.3 / 2.2% | 0.9 / 1.9% |
| tier x tier crossings | - | 95 | 114 | 0 |
| skirt x petticoat crossings (cross_legged) | 214 | 212 | 218 | 226 |
| run clip pop | - | 66 mm (skirt) | 76 mm (tier2) | 55 mm (skirt) |

- No new stretch major (> 2.0). The run / idol_dance / sit_stand clip penetrations stay at
  round 2's level (run 0.5 cm, 0.0%; idol 0.7 cm, 0.4%; sit_stand 1.0 cm, 2.1%).
- Every skirt row is at or below round 10's, and every skirt and petticoat row except seiza
  skirt is at or below the bound.

**Seiza skirt, the row left** (1.502 against 1.493). It is the skirt's hem at chain 1 with
both thighs at 67 deg and the floor seat. Across the variants it moved between 1.454 and
1.570 with no trend, and it is 0.23 below round 10. The settings that took it under the
bound (`DRAPE_STRAIN` 0.25 without `DRAPE_UP` 7, or smoothing after the cone at every pitch)
brought back 10-11 other rows or the cross_legged crossings. Close-ups show no fold there.

**Side effects, all minor:**
- Skirt x petticoat crossings in cross_legged: 226 (round 2 218, round 10 214, the
  integration before round 2 226). Petticoat flips in cross_legged: 3 -> 7 (petticoat
  alone 6).
- Walk clip: skirt pop 9.6 mm at frame 20, at the front hem where the legs cross. The two
  thighs' lifts meet there, and the narrower cone gives both a share of the front chains.
  Round 10: 8 mm; round 2's worst was the knee's 8 mm.
- Run clip: the worst strain jitter row is now `bodice_ribbon_tails` 0.216 at frame 5
  (round 2: the knee's 0.21). The petticoat's own is at most 0.20 by the same test on the
  dumped frames (0.27 before the post-cone smoothing).
- The waist-bow ribbon tails (bodice) ride the skirt chains: their top edge below the bow
  stretches x1.68 in deep_lunge and kneel_one (round 2 1.50 / 1.54, round 10 1.52 / 1.54) and
  x1.60 in the run clip. The close-ups (`r3_ribbon_tails.jpg`) show no visible change.

**The round-2 p3 items:**
- *Front tiers in walk / curtsy:* fixed (above).
- *Core top ring in lie_back:* 1.45 -> 1.15 cm, 2.4 -> 1.9% (petticoat alone 0.95 cm, 1.5%).
  It is hidden under the skirt and bodice.
- *Ribbon tails in cross_legged:* 1.36 cm (round 2 1.32, round 10 1.39). Unchanged; this is
  the bodice's (its tails take the skirt chains' weights).

**Images:**
- `r3_heat.jpg`: stretch heat on the tier that sets each row (white 1.0, yellow 1.6, red 2.0),
  outer layers hidden. Walk tier1, curtsy, sit_chair and jump_tuck tier2, round 2 against
  now.
- `r3_walk_curtsy.jpg`: walk and curtsy, cel, and clay with the skirt hidden.
- `r3_seated_lying.jpg`: sit_chair and run_l with the skirt hidden, lie_back from below, and
  cross_legged.
- `r3_ribbon_tails.jpg`: the waist-bow tails in kneel_one and deep_lunge.

**Gates:**
- This branch: `check.py` CHECK OK (151,344; petticoat 25,920 / 28,000). `rig_check.py` RIG
  CHECK OK on the 17 core poses:
  - walk 1.57 on tier2 (round 2 1.81); worst squat 1.82 on the body;
  - worst pen side_bend 1.77 cm (skirt);
  - no backward knee; 66/66 PMX names.
- Full merge (`r11/integrate` 415f85d + this branch): `check.py` CHECK OK (153,186).
- Full report: 2395 s.
- Not run: `export_pmx`, `pmx_reimport`, `motion_vmd` (no mmd_tools on the cluster).


## Integration review, round 2
**Merge with `r11/body-legs` (review p2).** fd525db no longer merged cleanly into
`r11/integrate` f0395d7: two conflicts in `levi/rig.py` with `r11/body-legs`. The branch now
merges `r11/integrate` and keeps both sides: the drape's knee has `DRAPE_KNEE_OUT` and the
full-cloth `inner=`, and `build_rig` fills both `_CROTCH` and `_MOTION_CHAIN` (each resets the
pose). The result is identical to the verifier's union merge (e460124).

**Skirt waist in torso turns (`rig.CHAIN_BODY_KEEP`).** torso_left / torso_right / twist_bend /
look_over_shoulder stretched the skirt x1.53 / 1.45 / 1.64 / 1.56 (round 10: 1.33 / 1.38 /
1.37 / 1.35). The edges are 2.3 mm long, on the waist band above the chain roots (rest
(0.09, -0.15, 0.86), front-left and front-right).
- Cause: unpruned, those vertices carry six bones, with 上半身 at a smooth 0.045. The 4-bone
  prune tied 上半身 with the weak neighbouring chain roots, and kept 0.005 on one vertex and
  0.035 on the next. The turned 上半身 then sheared each edge by about 1 mm.
- Fix: when a skirt-family vertex picks its four bones, the body bones (上半身 / 下半身) rank at
  twice their weight. A neighbouring chain root moves like the vertex's own except in a drape;
  in a twist, 上半身 alone turns the waist. 上半身 now stays at 0.045.
- Result: x1.17 / 1.15 / 1.22 / 1.18 (`r2_waist_twist_heat.jpg`: stretch heat, white 1.0,
  yellow 1.6). Also lower: squat skirt 1.44 → 1.39, high_kick 1.90 → 1.87, deep_lunge
  1.65 → 1.61, kneel_one 1.72 → 1.60. The petticoat does not change: its tiers carry no body
  weight and the core is not pruned. A factor of 3 also moved the cross_legged hem
  (x2.07 → 2.21); 2 does not.

**Rows still above min(round 10, petticoat alone)** (`motion_r2.txt`, the full report on the
full merge). There are 16 such rows, with a summed excess of 0.93; round 1 had 22 rows and
1.69, and the integration before the fix had 33 rows and 4.00. The cross_legged petticoat row
has its own bound (round 10 + 0.1) and is not counted.
- Petticoat: walk 1.81 (bound 1.74), walk clip 1.64 (1.60), curtsy 1.58 (1.44), sit_chair /
  sit_stand 1.94 (1.81), jump_tuck 2.01 (1.92), lie_back 2.16 (2.15), squat 1.55 (1.53).
- Skirt: walk 1.55 (1.51), walk clip 1.42 (1.35), curtsy 1.39 (1.32), seiza 1.56 (1.49).
- Four dance / turn rows, each within 0.04 of the bound.

These rows are ring strain at the hems where the front chains lift. They come from the drape,
which the inner layers' clearance needs:
- *Swap test* (same petticoat mesh; weights and bone matrices exchanged between the rigs). The
  excess comes with the bone matrices, not the weights. Each row is: petticoat-alone weights
  with petticoat-alone matrices / this branch's weights with petticoat-alone matrices /
  petticoat-alone weights with this branch's matrices. walk tier1: 1.74 / 1.74 / 1.81.
  sit_chair tier2: 1.79 / 1.78 / 1.95. curtsy tier2: 1.53 / 1.52 / 1.59. jump_tuck tier2:
  1.90 / 1.89 / 1.96.
- *What lifts the front chains.* Clearance per cloth object, chain 15 (front-left), left thigh
  at 40 / 60 / 90 deg, turns of the three segments, root to hem:
  - skirt alone: 0-0-14 / 20-30-34 / 70-66-76 deg;
  - petticoat core: 12-22-0 / 36-46-22 / 108-84-60 deg.
  The inner tiers lie wholly on the hem segment. A joint bends at most 24 deg, so the tiers
  need the upper segments raised too: the least turn that clears them at 40 deg is 4-26-48.
  The chain solve raises an upper segment only for the cloth on it, which there is the core.
- *Without the core in the clearance* (experiment v2), every stretch row except the hem /
  twist ones drops under the bound: walk 1.48, curtsy 1.31, sit_chair 1.67, jump_tuck 1.95.
  But the thighs go 2.5-3.5 cm into the core and the inner tiers in 14 of the 34 poses and
  clips measured (this branch: none over 2.2 cm), including the gated test (2.9 cm) and squat
  (3.1 cm) poses
  (`r2_core_clearance_test.jpg`). Before the integration fix, the sparse sample of the core
  is what let the inner tiers go 2.9 cm into the thigh in run@18.
- *The solve is sensitive.* Other changes move these rows by ±0.1-0.2, in both directions:
  an 8-16 mm offset of the core in the clearance (v3 / v4), coarser clearance bins (v5), or
  the old rest-ring sample (v1). No variant beat the current tables without losing the
  clearance:

| variant (subset report) | rows over bound | summed excess | worst petticoat pen | worst pen_frac |
|---|---|---|---|---|
| round-1 fix (fd525db) | 18 | 1.62 | 1.45 cm | 2.5% |
| v1 rest ring from the chain points | 18 | 1.56 | 1.27 cm | 2.4% |
| v2 core left out of the clearance | 7 | 0.79 | 3.50 cm | 7.5% |
| v3 / v4 core 16 / 8 mm softer | 28 / 26 | 3.40 / 2.65 | 1.52 / 1.45 cm | 3.4% |
| v5 clearance bins 4 deg x 2 cm | 15 | 1.50 | 1.44 cm | 2.7% |
| core body handover 1.0 chain unit | 23 | 2.57 | 1.02 cm | 1.0% |
| **CHAIN_BODY_KEEP 2 (this branch)** | **13** | **0.86** | **1.45 cm** | **2.5%** |

(13 extended poses, the 17 core poses, clips run / walk / sit_stand / idol_dance; the
cross_legged petticoat row has its own bound, round 10 + 0.1, and is left out.)

**The other review items (p3).**
- *Front tiers in walk / curtsy:* the drape, as above; the verifier's close-ups show no fold.
- *Core top-ring pen* (lie_back 1.45 cm, hidden under the skirt and bodice). The back chains
  turn forward with the gathered drape and swing the core's upper back ring, 2.2 cm off the
  buttock at rest, into it. A longer body handover on the core alone (`ROOT_BLEND` 1.0 chain
  unit) brings lie_back to 0.78 cm and pen_frac to about 0 everywhere. But it stretches the
  core x2.1-2.2 in high_kick, deep_lunge, kneel_one and the run clip, so it is not used.
- *Unchanged:* the middle tier's front seam, the ribbon tails in cross_legged (bodice) and the
  sit_stand pops.

**Gates (this branch = the full merge).**
- `check.py`: CHECK OK, 151,376 / 200,000 faces (petticoat 25,920, skirt 22,680).
- `rig_check.py`: RIG CHECK OK on the 17 core poses, with the repeatability build. torso_left
  and torso_right go 1.53 / 1.45 → 1.24 / 1.24 (the worst object is now the bodice lacing);
  every other row is unchanged (worst squat 1.82, walk 1.81 on tier1; worst pen side_bend
  1.77 cm; no backward knee; 66/66 PMX names).
- Full motion report (1736 s) against round 1: no regression past minor. kneel_one skirt
  1.72 → 1.60 and twist_bend skirt 1.64 → 1.23.
- Not run: `export_pmx`, `pmx_reimport`, `motion_vmd` (no mmd_tools on the cluster).

## Integration fix: skirt x petticoat in motion
With `r11/skirt` merged, the petticoat core stretched x3.24 in cross_legged (x2.93
lie_back_elbows, x2.44 jump_tuck, x2.22 sit_chair; round 10 2.18 / 2.25 / 2.06 / 2.03),
and the inner tiers went 2.8 cm into the raised thigh in the run clip (idol_dance,
sit_stand, deep_lunge, run_l and seiza too). Hair, sleeves, torso and hands changed nothing.

**Causes** (`out/r3`, scratch merges under `work/integ_scratch/pt_reports`):
- *Core: the 4-bone prune's motion refit.* The core's 7 sparse rings, smoothed 6 cm,
  carry 6-12 bones per vertex. The refit picks 4 per vertex from the generic samples, of
  which only a few move the skirt chains, so neighbouring vertices landed on chain 4 vs
  chain 6 (rest azimuth -56, z 0.64: a purple column in `integ_core_heat.jpg`). Swap test:
  the merged rig's core weights with the petticoat-alone bone matrices still give x3.20,
  the petticoat-alone weights with the merged matrices x2.08; the unpruned weights x1.83.
- *Drape: an unstable clearance sample.* The clearance tested 300 sector points taken by
  index; the skirt fix moved the mean centre `cy` by 0.009 mm, points crossed sector
  edges and every sector got different samples. The clearance of the front chains changed
  by 20-40 deg, and with the gather the left-thigh table of chains 14-15 lifted 15 deg
  less at 58 deg of thigh pitch (run@18). The 5 mm petticoat grid also kept the first
  object's point per cell, dropping the inner tiers where they lie within 5 mm of the
  outer one.

**Fix (`levi/rig.py`, skirt / petticoat / drape sections only):**
- `PLAIN_OBJECTS`: the core takes the plain angle x height blend of `_skirt_weights` (at
  most 4 bones, no smoothing, no prune, no refit), so it no longer depends on the drape.
  `PLAIN_SEAM`: its ring that the inner tier hangs from takes the tiers' weights (within
  6 mm, plain again by 12 mm), so the seams stay closed (0.3-1 cm in poses; a fully plain
  core left the tiers' tops 1.5-2 cm off in walk and run).
- `DRAPE_BIN`: the clearance tests the innermost cloth point of each 2 deg x 1 cm cell of
  the sector over the full skirt and petticoat meshes; the rest ring's innermost cloth
  (`DRAPE_INNER`) reads the full meshes too. The drape tables for the petticoat-alone and
  merged cloth now agree within 0-2 deg (6 deg on one abducted table), against 19-23 deg
  before.
- `MOTION_CHAIN_POSES`: the skirt family's prune refit adds 15 thigh samples (each thigh
  alone and both, forward 45-120, back 30, in / out 35), with the chains following
  through their drape drivers. Pruned weights now stretch like the unpruned ones (the
  skirt's cross_legged 2.47 -> 2.07; unpruned 2.01).
- Tried and dropped: refit samples that turn every third chain alone (they fit unnatural
  ring strain: skirt x2.79 in cross_legged, x2.04 in the gated 'test' pose); no refit at
  all (core x2.6 in high_kick);
  smoothing the refitted weights (x2.2-3.0); blending the tiers to the plain blend near
  the core (front-hem x2.03 and a strain-jitter major in the run clip over a 2.5 cm band,
  x3.3 over 1 cm); a 4 cm core-side band (core x2.37); tier smoothing 4.5 / 8 cm (no gain).

**Motion, full merge** (`r11/integrate` ada6865 + this fix, full report;
`motion_integ.txt`), round 10 / petticoat alone / integrate before / now:

| | round 10 | petticoat alone | before | now |
|---|---|---|---|---|
| cross_legged petticoat | 2.18 | 2.26 | 3.24 | 2.26 |
| cross_legged skirt | 2.60 | 2.71 | 2.47 | 2.07 |
| lie_back petticoat | 2.25 | 2.15 | 2.93 | 2.16 |
| jump_tuck petticoat | 2.06 | 1.92 | 2.44 | 2.01 |
| sit_chair petticoat | 2.03 | 1.81 | 2.22 | 1.94 |
| high_kick petticoat / skirt | 2.17 / 1.90 | 2.05 / 2.16 | 1.96 / 2.09 | 2.00 / 1.88 |
| run clip petticoat | 2.30 | 1.98 | 1.89 | 1.90 |
| run clip petticoat pen | 0.5 cm, 0.0% | 1.1 cm, 0.8% | 2.8 cm, 3.6% | 0.4 cm, 0.0% |
| idol_dance pen | 0.7 cm, 0.2% | 0.5 cm, 0.1% | 2.7 cm, 4.1% | 0.7 cm, 0.3% |
| sit_stand pen | 1.1 cm, 2.6% | 0.9 cm, 1.8% | 2.8 cm, 4.1% | 1.0 cm, 2.1% |
| deep_lunge / run_l pen | 0.6 / 0.3 cm | 0.7 / 0.5 cm | 2.6 / 1.8 cm | 0.6 / 0.4 cm |
| run clip petticoat jitter | - | - | 0.28 | - |

- Every skirt stretch is at or below round 10 except, all minor: twist_bend 1.65 (round
  10 1.37, petticoat alone 1.60, before 1.63), look_over_shoulder 1.56 (1.35 / 1.52 /
  1.52), walk clip 1.40 (1.35 / 1.38 / 1.38) and curtsy 1.35 (1.32 / 1.34 / 1.34).
- No new major against round 10. Still above the petticoat-alone numbers: jump_tuck 2.01
  (inner tier hem, round 10 2.06), sit_chair 1.94, curtsy 1.55 (1.53).
- Core penetration at its hip ring (azimuth +-90, z 0.83-0.87, hidden under skirt and
  bodice): lie_back 1.4 cm / 2.2% (round 10 0.5 cm, petticoat alone 0.9 cm), high_kick
  1.3 cm (0.8 / 1.5). Minor, under 2 cm.
- Skirt x petticoat crossings in cross_legged 216 (round 10 214); tier x tier 82 (petticoat
  alone 84).
- With `r11/body-legs` merged as well (other thighs, `motion_legs.txt`) every row stays
  within 0.03 of these and the pen within 0.1 cm; without the fix that merge reproduces
  the x3.24 core and the 2.9 cm run penetration.

**Gates.** This branch: `check.py` CHECK OK (petticoat 25,920 / 28,000, skirt 22,680 /
24,000, total 121,868); `rig_check.py` RIG CHECK OK (17 core poses: fist 1.86, squat 1.85,
test 1.83, walk 1.78 on tier1; worst pen side_bend 1.76 cm; no backward knee; 66/66 PMX
names). Full merge: CHECK OK (148,540) and RIG CHECK OK.

**Images.** `integ_run18.jpg` / `integ_run18_zoom.jpg`: run@18 from the left and the front,
cel and clay, before / after (the thigh no longer cuts the front frill).
`integ_core_heat.jpg`: the core in cross_legged and lie_back_elbows coloured by edge
stretch (white 1.0, yellow 1.6, red 2.0, purple 2.6+), tiers and skirt hidden.

## What it is now
- **Three tiers plus a gathered core.** Petticoat: 25,920 faces (budget 28,000; round 10 had
  12,000). Model total: 121,888.
- **Shared layout.** All three tiers have 96 lobes at the same azimuths. The lobes are
  grouped into bells of 3-4, about 7 cm wide, so the bells of the three tiers stack in
  clusters, as on the sheet.
- **The bell is the main form.**
  - Each bell is a puffed tube carved inward from the band. The crests sit on the band and
    the pinches go 2 x 8-9 px inside it, with a pinch radius of about 5 mm.
  - The mouth flares, and the pinch between two bells rises 9-11 px.
  - Each bell's mouth is levelled to its own mean height. A sloping hem becomes a staircase
    of level mouths instead of a row of tilted tongues.
- **Lobes.** Each lobe is a soft puff across, with a round scallop whose notch is blurred.
  At a pinch, the lobe notch gives way to the bell's own rise.
- **Rolled hem.** Its frame is averaged over ±2 samples and turned toward the body axis.
  The return runs back up inside, but never past the last band segment.
- **Hanging, not slanted.**
  - The band flares just under the seam, inside the skirt, and hangs straight where it
    shows (`HANG_POW`). The outer tier's top ring is at 0.95 of its hem outline.
  - Under the front and back lift, the bells are shallower and the inner tiers tuck behind
    the outer one. Seen from the side, the frill ends no longer fan out into feathers.
- **Clearance.**
  - The clamp is measured at the gathered points' own height.
  - A nearest-point pass then keeps about 4 mm in 3D from the skirt and from the tiers
    around.
  - Rest gaps: tier0 to skirt 4.7 mm (4.1 mm with r11/skirt merged), tier to tier
    2.7-4 mm (round 11 first try: 0.67 mm). The legs are more than 8.7 cm away.

## Rig (`levi/rig.py`, petticoat-specific sections)
- **`LAYER_PARTS`: tiers share weights with their neighbours.**
  - Each tier is first smoothed on its own. Then its weights are blended toward the other
    tiers' weights at their 6 nearest vertices within 1.2 cm, weighted by
    (1 - d/r)^2, in two passes. The change is smoothed along the tier over 2 cm.
  - The core keeps its own weights. When it was shared too, its sparse pruned rings
    carried their steps into tier1's seam. (Since the integration fix the core takes the
    plain angle x height blend, and the tiers' weights at their seam: see above.)
  - Tried and dropped: one angle x height weight field for every petticoat object. It
    mixed 5-6 chain bones round the hips and stretched the core x4-5 in high_kick.
- **`DRAPE_GRID` now 5 mm, on petticoat points only** (the chain fit; since the
  integration fix the drape's clearance and rest ring read the full meshes, `DRAPE_BIN`).
  - The skirt chains and the drape see the petticoat thinned to a 5 mm grid, about as
    many points as round 10's petticoat had (12.9k). The skirt's points are taken as
    they are.
  - The first try thinned skirt and petticoat together to a 12 mm grid.
  - Chain joints are within 13 mm of round 10's (first try: 19 mm).

## tools/motion_check.py
- Adds `tier0` / `tier1` / `tier2` crossing groups, so tier-x-tier crossings show up in
  the motion report.

## Gates (full model, this branch)
- `check.py`: CHECK OK.
- `rig_check.py`: RIG CHECK OK on the 17 core poses.
  - The worst stretch is unchanged: fist 1.86, squat 1.85 (both on the body).
  - Walk 1.74 (round 10: 1.74). The worst penetration is unchanged: side_bend 1.76 cm, on
    the skirt.
  - No backward knee; 66/66 PMX bone names.
- Not run: `export_pmx`, `pmx_reimport` and `motion_vmd`. mmd_tools is not installed on
  the cluster.

## Motion report vs round 10 (`motion_petticoat.txt`, `motion_skirt.txt`)

### Petticoat: better than round 10
| pose | stretch, round 10 → now |
|---|---|
| sit_chair | 2.03 → 1.81 |
| high_kick | 2.17 → 2.05 |
| lie_back_elbows | 2.25 → 2.15 |
| jump_tuck | 2.06 → 1.92 |
| run_r | 2.17 → 1.95 |
| run (clip) | 2.30 → 1.98 |
| sit_stand (clip) | 2.03 → 1.82 |

- The core stays at or below round 10's stretch: high_kick 2.0, cross_legged 2.1,
  lie_back 1.9.
- No flips, except cross_legged 6 (round 10: 3; first try: 8). The first try's new
  back-hem flips (high_kick 17, kneel_one 13, deep_lunge 12, run_r 10) are gone.

### Petticoat: still worse than round 10
| metric | round 10 | first try | now |
|---|---|---|---|
| cross_legged stretch | 2.18 | 2.75 | 2.26 |
| run_l stretch | 1.78 | 1.90 | 1.88 |
| high_kick penetration (core, スカート10_0) | 0.83 cm | 1.26 cm | 1.54 cm |
| run clip penetration (inner tiers, front, frames 4-5) | 0.49 cm | 0.71 cm | 1.11 cm |
| lie_back penetration | 0.54 cm | 1.08 cm | 0.95 cm |

All of these are below 2 cm.

### Tier x tier crossings (BVH face pairs)
| pose | first try | now |
|---|---|---|
| high_kick | 66 | 0 |
| deep_lunge | 50 | 0 |
| kneel_one | 44 | 0 |
| run_l | 33 | 0 |
| cross_legged | 291 | 51 |

- The motion report's new metric counts 84 in cross_legged, 7 in run_r and 4 in the run
  clip.
- Skirt x petticoat in cross_legged: 212 (round 10: 214).

### Skirt
The skirt moves only because its chain fit sees the new petticoat.
- Better: sit_chair 2.16 → 2.00, lie_back 2.64 → 2.35, jump_tuck flips 32 → 10, run_l
  penetration 1.22 → 0.91 cm.
- Worse: torso_left / right 1.33 / 1.38 → 1.49 / 1.62, twist_bend 1.37 → 1.60,
  high_kick 1.90 → 2.16.
- In the variants tried, these twist values moved ±0.15 with every chain fit.

## Rest geometry
- No self-intersections.
- No dihedral over 105° outside the rolled hem: 3 edges on tier2, at most 140°. The first
  try had 41-69 edges per tier at 130-144°.

## Sheet metrics (reported, not chased; `metrics_delta_petticoat.txt`)
- **Petticoat IoU** fell a little against round 10, because the bells' crests now sit on
  the measured outline instead of 2 cm outside it. Front 0.293 → 0.279, side
  0.269 → 0.225, back 0.226 → 0.207.
- **Whole-model IoU**: 0.907 / 0.831 / 0.911, down 0.002-0.003 against round 10.
- **Petticoat shade islands**, round 10 → now:

| view | round 10 | now |
|---|---|---|
| front | 1/69 | 0/0 |
| side | 1/55 | 2/134 |
| back | 1/71 | 0/0 |
| q34_front_left | 4/169 | 1/40 |
| q34_back_right | 1/36 | 3/221 |
| high | 1/54 | 0/0 |

  The first try had 9/256 islands in the side view.

## Images
- `ortho_sheet_base_prev_new.jpg`: the sheet, round 10, round 11's first try and this
  branch (panel crops).
- `side_ends_12cm.jpg`, `side_ends_12cm_clay.jpg`: the side view's front and back ends at
  12 cm.
- `notch_macro.jpg`, `wire_q34z.jpg`: the 12 cm 3/4 view and the 5 cm macro. No thorns;
  the scallops are rounded.
- `poses_cel.jpg`: deep_lunge front, high_kick back, cross_legged lap, sit_chair from
  below.
- `below_q34_cel.jpg`: the view from below and the 3/4 view.
- `r2_waist_twist_heat.jpg`: integration review round 2. The skirt's front-left waist band in
  torso_left, twist_bend and look_over_shoulder, coloured by stretch (white 1.0, yellow 1.6),
  before and after `CHAIN_BODY_KEEP`.
- `r2_core_clearance_test.jpg`: the gated test pose with the core in the drape's clearance (this
  branch) and left out of it (experiment v2): the thigh comes through the core and the inner
  tiers hang into it (cel; clay zoomed, skirt and bodice hidden).
