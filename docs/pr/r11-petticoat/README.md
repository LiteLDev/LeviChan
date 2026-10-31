# r11 petticoat: three tiers of scalloped bells

Branch `r11/petticoat`, built on `r11/base`. Only `levi/parts/petticoat.py` changes geometry.
Rounds 5-7 (integration reviews 5-7) fast-forwarded the branch to `r11/integrate` b71fd46 and
change only the rig's skirt drape section, `tools/drape_perturb.py`, `tools/drape_ref.py`,
`tools/rig_check.py` (one check), `assets/drape/drape_ref.npz`, CLAUDE.md and these docs.
The petticoat-specific parts of `levi/rig.py` change, and `tools/motion_check.py` gets one
new count. Since the integration fix below, the branch also carries `r11/skirt` (merged at
e8b439f, unchanged), so it supersedes both parts. It carries `r11/integrate` up to 1b06af3
(fast-forward); the round-4 numbers below are from `r11/integrate` 78bca50 with this branch
merged in (no conflicts), the round-3 ones from 415f85d + this branch.

## Integration review, round 7: the run clip's strain spike at the thigh's turn-back
The verifier of round 6: the continuation holds (T1, T2, T4, T5 met, no regression), but the run
clip's petticoat_core strain jitter stayed at integ17's 0.2073 (frame 6, スカート13_1), 0.007 over
the brief's 0.20 bound (T3 partly met), since the tables were kept on purpose.

**Diagnosis** (`work/integ_scratch/pt_r7`: `tools/jdiag.py` records every frame's edge strains, the
drape drivers' values and the bone matrices on the merge rig; `tools/apply.py` re-runs only the drape's
post pass on the captured raw turns with other settings and rewrites the 1454 driver F-curves in place,
~10 s per clip, ~5 min with 41 poses; on the unchanged settings it reproduces the tables and every
number exactly).
- The spike is one edge row on the core's front-left hem (x 0.13, y -0.14, z 0.68, 12 mm long),
  weighted half and half to chains 13 and 14 (123.75° and 146.25°, the left front). Its strain over
  frames 3-9: 1.24, 1.36, 1.56, **1.775**, 1.72, 1.55, 1.43; the strain acceleration at frame 6 is
  0.278 against 0.071 / 0.042 two frames either side (the metric's excess 0.207).
- Frame 6 is where the right thigh turns back: pitch 62.8° / 71.5° / 68.9° at frames 5 / 6 / 7 (a
  second difference of -11.4° per frame²). The left thigh is at rest. The edge's strain is a function
  of that pitch with a slope of ~0.024 per degree between 63° and 72°, so the turn-back alone makes the
  spike (0.024 x 11.4°).
- The slope comes from the ring cap. Chains 15, 14 and 13 beside the lifted front chain 0 step down
  from it by about the cone's step (the roots at 70°: 62.3 / 45.8 / 28.8 / 12.2°, steps of 16.5 / 17.0 /
  16.6° against a cap of 17.4° there), and below 75° the cone is narrowed (`DRAPE_RING_CAP_PITCH`, 55%
  below 45°, smoothstep to the full cap by 75°), its fastest widening at 55-65°. Chains 14 - 13 at the
  root: 10.7° / 12.7° / 16.6° / 18.0° apart at 60 / 65 / 70 / 75°: 0.78° per degree of pitch where the
  run's thigh turns.
  At frame 6 the difference's second difference is -8.4° (root) and -6.6° (middle segment).
- The tiers (0.196 / 0.195), the skirt (0.156) and the run pop (55.4 mm skirt) peak at the same frame
  for the same reason. The run clip's worst jitter row overall is the body's (0.2235 at 足.R, frame 7,
  the IK leg itself), which the drape does not touch.

**Fix: the full cap by 77° instead of 75°** (`DRAPE_RING_CAP_PITCH = ((45, 77), 0.55)`; the post-cone
smoothing follows the same range). Both halves of it help: the cone alone (smoothing to 75) gives core
0.173, the smoothing alone 0.190, both 0.157. The tables move at most 0.024 rad (41 of 64 chain tables
past 0.01 rad); `tools/drape_ref.py` on the same inputs keeps every discrete choice bit-identical
(t_ref, m_ref, psi_ref, lift_ref, the seat) and rewrites only the reference's tables, so the build
continues from it with the tables 0.0000 rad from the reference's, and the merge rig's 1454 driver
F-curves are bit-identical to the harness's. The edge above: strain acceleration 0.278 -> 0.228, excess
0.207 -> 0.140; chains 14 - 13 second difference at frame 6 -8.4 -> -7.8° (root), -6.6 -> -5.3° (middle).

Swept in the harness (run clip jitter per object; rows of the 41-pose harness against the unchanged
rig with the brief's bounds):

| full cap by | core | tier0 | tier1 | tier2 | skirt | tails | run pop | tables moved | rows past the bounds | worst row |
|---|---|---|---|---|---|---|---|---|---|---|
| 75° (shipped) | 0.207 | 0.166 | 0.196 | 0.195 | 0.156 | 0.134 | 55.4 mm | - | - | - |
| 76° | 0.192 | 0.149 | 0.180 | 0.176 | 0.143 | 0.134 | 54.2 | 0.012 | 0 | run_r core +0.014 |
| **77°** | **0.157** | 0.137 | 0.146 | 0.154 | 0.130 | 0.133 | 53.3 | 0.024 | 0 | run_r tier2 +0.017 |
| 78° | 0.153 | 0.139 | 0.146 | 0.154 | 0.131 | 0.133 | 52.7 | 0.036 | 0 | run_r skirt +0.021 |
| 80° | 0.149 | 0.132 | 0.146 | 0.154 | 0.131 | 0.132 | 51.9 | 0.060 | 1 | run_r skirt +0.052 |
| 82° | 0.168 | 0.133 | 0.145 | 0.154 | 0.130 | 0.130 | 51.4 | 0.082 | 3 | run_r skirt +0.083 |
| 85° | 0.171 | 0.135 | 0.146 | 0.154 | 0.130 | 0.127 | 50.8 | 0.113 | (clips only) | |
| 75°, 65% below 45° | 0.171 | 0.136 | 0.144 | 0.151 | 0.128 | 0.134 | 55.5 | 0.107 | (clips only) | |
| 40-70° | 0.228 | 0.190 | 0.232 | 0.243 | 0.193 | 0.130 | 66.2 | 0.111 | (clips only) | |
| `DRAPE_SMOOTH` 10 | 0.209 | 0.157 | 0.200 | 0.182 | 0.168 | 0.135 | 53.6 | 0.106 | (clips only) | |

77° is the least change that clears the bound with margin (76° leaves the core at 0.19). Its frame-6
spike is 0.152; the core's worst is now frame 14's 0.157 (the left thigh rising through 48°, 0.163
before). Walk, turn, spin, sit_stand and idol_dance jitter / pop are unchanged within 0.003 / 1 mm
(sit_stand core pop 2.5 -> 1.4 mm). The PMX's 回転付与 shares (`_drape_share`, read at 60°) move by at
most 0.0105 (chain 2 L root 0.146 -> 0.157).

**Continuity (T2) kept**: `tools/drape_perturb.py` on the branch with the new reference: every table
within 0.0088 rad, 0 of 512 past 0.01 (knee 0.0027, hip 0.0041, radii 0.0088, cloth 0.0051), as in
round 6: the cap's range is a constant of the post pass, which stays 1-Lipschitz in the raw turns.

**T3 on the full merge** (r11/integrate 04ba5c9 + this branch 0dc9448, merge 6faf2e4, no conflicts;
`motion_r7.txt`; report 2737 s on cpu-00171). The build continues from the rewritten reference (tables
0.0000 rad from it); check.py CHECK OK, 164,116 faces (petticoat 25,920 / 28,000, skirt 22,680 / 24,000);
rig_check RIG CHECK OK, the core table as round 6's (squat x1.85, test x1.83, side_bend 1.76 cm on the
skirt; test's pen 0.35 -> 0.36 cm on the core), 66/66 PMX names, drape pin 0.000 mm.

| row | r10 | integ17 | round 6 | now |
|---|---|---|---|---|
| **run clip jitter, petticoat (core)** | - | 0.207 | 0.207 | **0.157** |
| run clip jitter, skirt / tails | 0.560 / - | 0.156 / 0.134 | 0.156 / 0.134 | 0.130 / 0.133 |
| run clip pop, skirt | 68.5 mm (petticoat) | 55.4 mm | 55.4 mm | 53.3 mm |
| walk clip pop | 8.2 mm | 8.4 mm | 8.4 mm | 8.4 mm |
| cross_legged skirt compress | x0.069 | x0.407 | x0.407 | x0.407 |
| lie_back_elbows core pen_frac | 0.52% | 0 | 0 | 0 |
| cross_legged skirt x petticoat | 214 | 0 | 0 | 0 |
| sit_chair skirt / petticoat stretch | 2.16 / 2.03 | 1.657 / 1.777 | same | 1.658 / 1.779 |
| seiza | 1.73 / 1.78 | 1.480 / 1.620 | same | 1.482 / 1.624 |
| jump_tuck | 2.20 / 2.06 | 1.700 / 1.921 | same | same |
| high_kick | 1.90 / 2.17 | 1.737 / 1.830 | same | same |
| run_r | 1.75 / 2.17 | 1.583 / 1.775 | same | 1.589 / 1.792 |
| run_l | 1.70 / 1.78 | 1.525 / 1.750 | same | 1.532 / 1.750 |
| tails cross_legged / kneel_one / run | 1.74 / 1.54 / 1.63 | 1.580 / 1.537 / 1.339 | same | same |
| tier x tier crossings (all poses) | 0 | 0 | 0 | 0 |
| hair x skirt jump_tuck / spin | 1720 / 1352 | 198 / 1042 | 186 / 1080 | 186 / 1080 |

Against integ17: 1,415 skirt-family rows, none past the brief's bounds; the one flagged row, spin hair x
skirt 1042 -> 1080, is the hair lanes' (round 6 and integ18 have it too). Against round 6's merge:
1,440 rows, none past the bounds, 403 differ: one stretch row worse by more than 0.01 (run_r tier2
+0.017), six better (run clip tier1 1.832 -> 1.819, run_l / idol_dance@72 core 1.702 -> 1.689 and
tier1 1.646 -> 1.631, run clip tier0 1.688 -> 1.677); non-family rows by at most 0.0027 (body,
cross-node noise; hair_back by 0.001 where the skirt hulls ride the chain roots).

Branch alone (0dc9448): check.py CHECK OK (162,801 faces); rig_check (17 core poses) RIG CHECK OK, the
same core table, drape pin 0.000 mm. Not run: export_pmx, pmx_reimport, motion_vmd (no mmd_tools).

**Images**
- `r7_jitter.png`: the run clip's frames 0-20: the right thigh's pitch; chains 14 - 13's middle segment
  turn; the jitter excess per frame of the core and of the tiers (max of the three), before (orange,
  dashed) and now (blue), against the 0.20 bound.
- `r7_heat.jpg`: the jitter test painted on the cloth (each vertex the largest excess of its edges at
  that frame, blue 0 -> red 0.22; skirt hidden, and tiers hidden in the middle row): run@6 front-low
  and low (the spike between chains 13 and 14 on the core and tiers, red -> orange), run@14 (unchanged);
  clay beside. Camera fixed on the left hip joint.
- `r7_hem.jpg`: the hem over the raised thigh (seiza, run_l, sit_chair, deep_lunge, jump_tuck, run@14,
  run@6, run_r, rest), before | now in cel, then clay, then the changed pixels in red: the tier frills
  move by a few pixels in seiza, run_l, run@6 and run_r, nothing elsewhere (sit_chair 80 px, jump_tuck 2,
  rest 0); no poke-through, no bowl.

## Integration review, round 6: a drape that moves continuously with its inputs
The verifier of round 5: the pin kept the leg bones out of the drape, but the solve itself was
unchanged, so moving all the cloth by 0.1 mm still moved 85 of 512 tables by up to 0.735 rad
(T2 not met, p2), and nothing checked the pinned thigh line against the fitted thigh (p3).

**Why the solve from scratch cannot simply be smoothed** (scratch harness and pose harness in
`work/integ_scratch/pt_r6`). The solve has bifurcations in every step: a segment's turn is the first
2° candidate under a threshold (a far crossing behind a plateau: 0° or 104° for a cloth point 2 mm
either side of the threshold), the slack pick on a wavy deep curve, binned cloth with hard masks,
and the gather's argmin, which turns 0.0005 rad of noise on the clearance into 0.14-0.24 rad of
table (`gx.py` replays). I replaced each step with a continuous one and measured both the
perturbations and the drape (pose harness: rig build + 41 poses / clip frames; rows of the brief's
skirt / petticoat / tail bounds, against the shipped solve):

| variant | worst table change (knee, hip, radii, cloth set) | rows worse / better past +-0.03 | mean stretch change |
|---|---|---|---|
| shipped solve, all cloth +0.1 mm (the noise floor) | (0.735) | 11 / 3 | +0.004 |
| every cloth point, soft masks, capped crossing (5°/mm), hard gather | 0.32 | 181 / 46 | +0.046 |
| ... + mean-field gather (T 0.03) | 0.23 | 201 / 55 | +0.031 |
| ... + exact Gibbs gather round the ring (T 0.03) | 0.012 on clearance noise | 202 / 72 | +0.009 (compress -0.026, crossings +350) |
| ... + no gather (ring cap only) | 0.083 | 207 / 108 | +0.077 |
| ... + Gibbs over the yaws only | 0.20 | 305 / 32 | +0.259 |

Continuity and the tuned drape pull apart: a continuous rule must blend where the solve jumps, and
every blend I tried moved the drape far off the one rounds 1-5 tuned (the soft versions were
continuous, the tuned rows were not kept).

**Fix: the drape is continued from a committed reference solve** (`rig.DRAPE_REF`,
`assets/drape/drape_ref.npz`, 121 KB, written by `tools/drape_ref.py` from a build). The reference
keeps the solve's discrete choices: each of the 11,200 clearance calls' turns before the zigzag pass
and their margins over the threshold on the full cloth (`_drape_cloth`: every skirt and petticoat
point, the sector / band / keep / rest-thigh masks as penalties that grow 1-2.5 mm per mm), the
gather's yaw and root lift at each of the 140 thigh pitches, and the seat swing's crossing. A build
moves each turn by a regularized Newton step that keeps its margin, measured with the segments
above at their reference turns (`_drape_track`, `DRAPE_TRACK_EPS` 0.02 m/rad: at most 0.025 rad per
mm of depth), keeps the gather's choices and takes the clearance at that yaw
(`_drape_gather_frozen`), and runs the post passes as before. At the reference's inputs the tables
are the reference's bit for bit (`drape_ref.py` checks it before writing); elsewhere every table
moves continuously and in proportion. The build log prints how far the tables moved from the
reference's; a reference made for other chains or grids falls back to the solve from scratch with a
warning. Tried on the way: the Newton steps passed down the chain (a segment's step grew up to 5x
the one above: 0.042 worst) and a 6 cm penalty cut-off (a point dropped there moved one yawed call
by 0.1 rad).

**T2, the acceptance test** (`tools/drape_perturb.py`, now with the cloth variants in its default
set; it passes the moved hip / knee to the solve directly, so it runs without the pin). Max table
change over the 512 driver tables (and PMX shares), worst table:

| change | continued: worst table (rad), tables > 0.01 | from scratch: worst table, tables > 0.01 |
|---|---|---|
| knee x +-0.05 / +-0.1 mm | 0.0011 (kx+0.1), 0 | 0.198 (kx+0.1), 70 |
| knee y | 0.0027 (ky-0.1), 0 | 0.204 (ky+0.1), 74 |
| knee z | 0.0004 (kz-0.1), 0 | 0.024 (kz-0.05), 23 |
| hip x / y / z +-0.1 mm | 0.0041 (hx-0.1), 0 | 0.198 (hx+0.1), 81 |
| thigh radii +-0.2 mm | 0.0088 (p-0.2), 0 | 0.159 (p-0.2), 123 |
| all cloth x +-0.05 / +-0.1 mm | 0.0051 (cx-0.1), 0 | 0.244 (cx-0.05), 143 |
| all cloth y | 0.0041 (cy-0.1), 0 | 0.735 (cy+0.1), 137 |
| all cloth z | 0.0044 (cz+0.1), 0 | 0.235 (cz-0.05), 99 |
| **all 32** | **0.0088**, 0 of 512 | 0.735 |

With the pin, the knee and hip variants change nothing by construction (as in round 5). Larger
changes stay in proportion: at 0.5-1 mm the continued tables move at most 0.031 rad (knee 1 mm 0.011, hip
1 mm 0.022, radii +1 mm 0.031, all cloth 1 mm 0.021-0.029), from scratch 0.16-0.74.

**Noise floor in the poses** (pose harness, all cloth moved +0.1 mm in y, against the unmoved
build): the solve from scratch moves 11 rows past the bounds and 3 the other way (cross_legged
inner tier x1.81 -> x2.21, run_l / idol_dance@72 tier0 x1.73 -> x1.83, lie_back_elbows skirt
x1.85 -> x1.90); continued, none (every row within 0.002; the tables moved 0.003 rad at most). `r6_cloth_shift.jpg`: base | from scratch +0.1 mm |
continued +0.1 mm, with the pixels that changed in red (cel and clay, ~4-5x crops).

**p3** (the stale pin): the rig build prints the pinned thigh line's distance from the fitted 足.L,
and `tools/rig_check.py` fails past `rig.DRAPE_THIGH_PIN_WARN` (1 mm): 0.000 mm on this build.

**T3 / T5 on the full merge** (r11/integrate 04ba5c9 + this branch 047eb85, merge 06d8439, no
conflicts; e6db0f6 only changes the step's regularization and the penalty cut-off, which act off the
reference's inputs, and rewrites the reference's margins; numbers in `motion_r6.txt`). The build
continues from the reference with the tables 0.0000 rad from it: the drape is the shipped one bit for
bit. check.py CHECK OK, 164,116 faces (petticoat 25,920 / 28,000, skirt 22,680 / 24,000, REPEAT
identical); rig_check RIG CHECK OK, the core table identical to integ18's (worst stretch squat x1.85,
worst pen side_bend 1.76 cm, drape pin 0.000 mm); the motion report (2749 s) against integ18
(8a45214): 96 of 15,190 rows differ, all `acc_halter` (the accessories lane in 04ba5c9), no skirt /
petticoat / tail row. Against integ17 (b71fd46): 1,415 skirt-family rows, none past the bounds; the
one flagged row, spin hair x skirt 1042 -> 1080, is the hair lanes' (integ18: 1080). Quoted rows
(r10 / integ17 / now): cross_legged skirt compress 0.069 / 0.407 / 0.407; lie_back_elbows core pen_frac
0.52% / 0 / 0; cross_legged skirt x petticoat 214 / 0 / 0; run pop 68.5 (petticoat) / 55.4 / 55.4 mm;
walk pop 8.2 / 8.4 / 8.4 mm; sit_chair skirt / petticoat 2.16 / 2.03 -> 1.66 / 1.78 -> same; seiza
1.73 / 1.78 -> 1.48 / 1.62 -> same; jump_tuck 2.20 / 2.06 -> 1.70 / 1.92 -> same; high_kick 1.90 /
2.17 -> 1.74 / 1.83 -> same; tails cross_legged / kneel_one / run 1.74 / 1.54 / 1.63 -> 1.58 / 1.54 /
1.34 -> same; tier x tier 0. The run clip's petticoat_core strain jitter stays at integ17's 0.207 (the
tables are the same), still 0.007 over the brief's 0.20: changing it means re-tuning the drape, which
this round was not to do (the pre-11a9b3a knee gave 0.199 but moved 35 rows past the bounds, round 5).

Branch alone (69d3287): check.py CHECK OK (162,801 faces); rig_check (17 core poses) RIG CHECK OK,
worst stretch squat x1.85, test x1.83 (body), worst pen side_bend 1.76 cm (skirt), no backward knee,
66/66 PMX names, drape pin 0.000 mm. Not run: export_pmx, pmx_reimport, motion_vmd (no mmd_tools); the
PMX's 回転付与 shares (`_drape_share`) read the same tables, so they are unchanged here and follow the
continuation elsewhere. The drape step of a rig build takes ~4 min (the continuation evaluates every
cloth point's depth curve) where the solve from scratch took ~2.5-3.

**Images**
- `r6_cloth_shift.jpg`: all cloth moved 0.1 mm in y (what the drape sees; the cloth itself is not
  moved): base | from scratch | its changed pixels (red) | continued | its changed pixels, for run_l
  (front, clay and cel), lie_back_elbows (side, clay), cross_legged (side, cel), deep_lunge and seiza
  (below, clay); ~4-5x crops. From scratch 128k changed pixels over the 36 crops (lie_back's tier
  hangs elsewhere, run_l's hem, cross_legged's inner tier); continued 28k, line-art edges only.
- `r6_perturb.png`: the worst table change of each of the 32 perturbations, from scratch (grey) and
  continued (blue), log scale, against the 0.01 rad target.

## Integration review, round 5: the drape solve and sub-mm inputs
The brief: r11/body-legs moved the fitted knee joint by 0.087 mm and nothing else the drape reads;
64 driver tables changed by up to 0.198 rad and skirt bones moved up to 31 mm (seiza). This round
is about why, and about keeping lanes that touch the legs from re-tuning the cloth.

**Harness** (`tools/drape_perturb.py`; the scratch version with call-order records and replays is
`work/integ_scratch/pt_r5/tools/perturb.py`). It builds the rig until `rig._skirt_drape` is
called, keeps its inputs and rebuilds only the drape (16 chains x 43 pitches x 4 tables x 5
tabulated yaws, ~160 s) with the knee moved +-0.05 / 0.1 mm along x, y, z, the hip +-0.1 mm and
every thigh radius +-0.2 mm, then compares each step by call order: the clearance turns, the
gather's turns and yaws, and the 512 tables the drivers hold (plus the PMX shares and the seat).
The unchanged rebuild matches the build's own tables exactly, and moving the knee by r11/body-legs'
0.09 / 0.04 mm reproduces the brief's 0.1983 on スカート15追従左1 drape_Lp0.

**Per step, the original solve (no pin)**: clearance max change (grid steps of 2°), gather max,
table max (tables over 0.01 of 512):

| change | clearance | gather | tables |
|---|---|---|---|
| knee x +0.05 / -0.05 | 0.35 (10) / 0.63 (18) | 0.05 / 0.14 | 0.007 (0) / 0.024 (24) |
| knee x +0.1 / -0.1 | 0.35 (10) / 1.01 (29) | 0.21 / 0.14 | **0.198 (70)** / 0.024 (24) |
| knee y +0.1 / -0.1 | 1.01 (29) / 0.28 (8) | 0.21 / 0.14 | **0.204 (74)** / 0.007 (0) |
| knee z +0.1 / -0.1 | 0.63 (18) / 0.03 (1) | 0.14 / 0.07 | 0.007 (0) / 0.024 (23) |
| hip x / y / z +0.1 | 0.35 / 0.45 / 0.63 | 0.37 / 0.28 / 0.31 | 0.198 / 0.024 / 0.079 |
| hip x / y / z -0.1 | 1.01 / 1.01 / 1.50 (43) | 0.18 / 0.37 / 0.21 | 0.079 / 0.079 / 0.198 |
| radii +0.2 / -0.2 | 0.73 / 0.98 | 0.42 / 0.24 | 0.124 / 0.159 |
| r11/body-legs' knee | 0.38 (11) | 0.21 | **0.198 (70)** |

Worst 0.204 rad. What turns a sub-mm change into a jump (depth curves in
`work/integ_scratch/pt_r5/evidence_depcurves.txt`):
1. *Clearance, first candidate under the threshold.* R thigh at 65°, chain 0, yaw +15°: the root's
   depth at 54° is +0.004 mm before and -0.01 mm after the knee moves 0.1 mm, so the root takes 56°
   or 54°. That 2° moves the middle segment's depth curve by up to 3 mm, and the curve lies on a
   plateau within 2.5 mm of the threshold for 20°: its first crossing moves 48° -> 68°, the hem
   54° -> 44°.
2. *Clearance, where nothing clears.* L thigh at 55°, chain 15: the middle segment's cloth is
   54-58 mm deep at every candidate, the threshold is the least depth + `DRAPE_SLACK`, and one
   candidate 0.03 mm over it moves the turn 0° -> 2°; the hem's range then ends 2° later, its least
   depth drops 57.9 -> 53.4 mm and its turn jumps 0° -> 16°.
3. *The free mask.* One cloth point of chains 4-5 (R) lies within 0.1 mm of the rest thigh's
   surface; the hip -0.1 mm or the radii -0.2 mm flip it into the test (0.14 rad on the R tables).
4. *The gather.* Replaying the build's own clearance with 0.002 rad of noise moves the tables by
   0.07-0.08 rad: the argmin re-picks neighbouring candidates (2 lift or 3 yaw steps). Some pitches
   have two near-equal gathers (L 65-75°: chains 15 / 0 yawed 30° vs chains 0-3 lifted 46°; La 60°,
   R 80-85°), so a soft minimum switches basin there too.
5. The post passes (monotone, early lift, smoothing, ring cap) are 1-Lipschitz; they pass the jumps
   on, and the smoothed shortfall keeps a spike at its height.

**Fix: the drape's thigh line is a constant** (`rig.DRAPE_THIGH_JOINTS`, like `DRAPE_THIGH_PROFILE`):
r11/integrate b71fd46's 足.L head and tail, so the tables are bit-identical to the ones integ17
measured and a lane that moves the leg bones no longer reaches them. Checked end to end (rig build
with the body's `levi_joints` knee moved +0.1 mm in x, -0.1 mm in y, and -0.09 / -0.04 mm): every
table identical to the pinned build (max 0.0); without the pin, +0.1 mm in x and the original knee
change move the tables by 0.198.

**Continuity switches, off** (`rig.DRAPE_SOFT`, `rig.DRAPE_READOUT`). DRAPE_SOFT: the clearance
crossing interpolated within the grid interval where the depth falls through the threshold, at most
a candidate's turn + 30°/mm of depth past it, over a fixed number of candidates. DRAPE_READOUT: the
tables read the gather's descent softened (4 soft sweeps at T 0.02 from its candidates). With both,
unpinned: knee changes 0.001-0.020 rad but one 0.167 (ky -0.1: a gather that changes basin), hip /
radii 0.016-0.24 (deep-cloth slack picks and cascades remain); the 0.002 rad replay noise gives
0.004 instead of 0.07. They move the drape off the one rounds 1-4 tuned: in the pose harness (rig
build + 41 poses and clip frames, against the same harness on the original solve) 58 skirt /
petticoat / tail rows move past the brief's bounds (cross_legged tier0 x1.80 -> x2.20, run_r skirt
x1.58 -> x1.71, 34 compress rows 0.03-0.06 lower); the clearance interpolation alone 36. Also tried
and dropped: a soft minimum in the descent itself (T 0.003-0.08, annealed or not: the two-basin
pitches still switch up to T 0.05; at 0.08, with a 10°/mm cap, the yaw blurs and 193 rows move past
the bounds), the clearance capped at 2-4°/mm or deep cloth counted as at most 24 mm deep (the
abducted table drops 17-35° at 85-140°), a rest-depth allowance for the free mask (the root swings
back 45° more at backward pitches), a continuous yaw interpolation in the gather (no fewer basin
switches).

Pinning the joints from before 11a9b3a instead brings the earlier tables back (the brief's "before"
row for スカート15追従左1 exactly): run strain jitter on petticoat_core 0.207 -> 0.199, but in the pose
harness 35 skirt / petticoat rows move past the bounds, both ways, as much as the 0.09 mm itself
moved them. The b71fd46 joints keep integ17's drape.

**Gates.** Branch (683515e; ffe09dd adds comments and docs): check.py CHECK OK, 162,801 faces
(petticoat 25,920 / 28,000, skirt 22,680 / 24,000); rig_check (17 core poses) RIG CHECK OK, worst
stretch squat x1.85 / test x1.83 (body), worst pen side_bend 1.76 cm (skirt), no backward knee. Full
merge (r11/integrate b71fd46 + this branch, a fast-forward; `motion_r5.txt`): all 15,082 rows against
integ17, none of the 1,128 skirt / petticoat / tail / crossing rows past the brief's bounds; 209
rows differ by at most 0.0027 (body 150 around the crotch fit, garments at most 4e-5), build noise,
since the drape tables are bit-identical. Rows the brief quotes (round 10 / integ17 / now):

| row | r10 | integ17 | now |
|---|---|---|---|
| cross_legged skirt compress | x0.069 | x0.407 | x0.407 |
| lie_back_elbows core pen_frac | 0.5% | 0.0% | 0.0% |
| cross_legged skirt x petticoat crossings | 214 | 0 | 0 |
| run clip skirt pop | 68.5 mm (tier0) | 55.4 mm | 55.4 mm |
| walk clip skirt pop | 8.2 mm | 8.4 mm | 8.4 mm |
| sit_chair skirt / petticoat stretch | 2.16 / 2.03 | 1.66 / 1.78 | 1.66 / 1.78 |
| seiza skirt / petticoat stretch | 1.73 / 1.78 | 1.48 / 1.62 | 1.48 / 1.62 |
| jump_tuck skirt / petticoat stretch | 2.20 / 2.06 | 1.70 / 1.92 | 1.70 / 1.92 |
| high_kick skirt / petticoat stretch | 1.90 / 2.17 | 1.74 / 1.83 | 1.74 / 1.83 |
| tails stretch cross_legged / kneel_one / run clip | 1.74 / 1.54 / 1.63 | 1.58 / 1.54 / 1.34 | 1.58 / 1.54 / 1.34 |
| hair x skirt crossings jump_tuck / spin | 1720 / 1352 | 198 / 1042 | 198 / 1042 |
| tier x tier crossings (summed) | 0 | 0 | 0 |

Run clip strain jitter (the verifier's `jit.py` on the branch rig): petticoat_core 0.207 (frame 6,
the core's front hem), tiers 0.166-0.196, skirt 0.156, tails 0.134. The 0.263 at frame 14 the brief
cites was measured before the round-4 core weights (`PLAIN_BODY`) were merged; on b71fd46 that spike
is gone, and 0.207 is integ17's own value (with the pre-11a9b3a joints: 0.199).

Not run: export_pmx, pmx_reimport, motion_vmd (no mmd_tools). The PMX's `_drape_share` reads the
same tables, so its 回転付与 shares are unchanged and no longer follow the leg bones either.

**Images**
- `r5_pin_diff.jpg` (dropped from the PR for size; later rounds' crops supersede it): what the 0.09 mm knee change did to the drape (clay, 4x crops): this branch
  (= integ17) | the knee before 11a9b3a | pixels that differ (red), seiza / run_l / deep_lunge
  (front hem over the raised thigh), sit_chair, jump_tuck (below), run@14.
- `r5_hem_side.jpg` (dropped from the PR for size; later rounds' crops supersede it), `r5_hem_front.jpg` (dropped from the PR for size; later rounds' crops supersede it): the hem over the raised thigh in seiza, run_l, sit_chair,
  deep_lunge, jump_tuck, run@14 and rest, round 10 | now (= integ17) | knee before 11a9b3a, cel then
  clay, side and front-low cameras at ~4x.

## Integration review, round 4
The integrate run 1b06af3 (i14) left three skirt x petticoat rows this lane owns: cross_legged
skirt compress x0.050 at スカート14_2 (round 10 x0.069, integrate before rounds 1-3 x0.097),
lie_back_elbows petticoat_core pen_frac 1.9% (round 10 0.5%), cross_legged skirt x petticoat
crossings 226 (round 10 214). Both fixes are weight-only (`levi/rig.py`, skirt shell and
petticoat sections), so the drape tables, the tiers and every round-3 row stay as they were.

**Diagnosis** (scratch tools and dumps in `work/integ_scratch/pt_r4`)
- *Bisect.* In a rig harness on the full model (each run: rig build + 41 poses and clip
  frames), round 3's settings one at a time (`DRAPE_UP` 10, `DRAPE_STRAIN` 0.3, no
  `DRAPE_RING_CAP_PITCH`) leave the compress at x0.040-0.052; only all of rounds 1-3's drape
  changes reverted together (`DRAPE_BIN` off too) give x0.097, with 24 stretch rows over the
  bound. `DRAPE_BIN` alone off: x0.068, 210 crossings, 17 rows. So the drape only moves the
  symptom; its cause is in the weights.
- *The skirt rim.* The worst edge is a 1.1 mm edge of the rolled hem's rim at 138 deg (front
  left, between chains 13 and 14, over the raised thigh). There chain 13's hem stands 117 mm
  above chain 14's (the same rest point under each chain's transform: 129 mm apart), so the
  blend's weight gradient moves points by 0.13 mm per 0.001 of weight. Across that edge the
  weight changes by 0.009, where the angle alone accounts for 0.0035: the rest is a slope
  with height. The shell share (`_shell_share`) averages each 1.5 deg x 4 mm cell's members
  into its node, and the members sit off the node by up to half a cell (0.03 of the ring
  blend) differently in each height row, so the rim's four rows took weights up to 0.01 per
  mm apart. On the real mesh the plain angle blend has a height slope of at most 0.0044 per
  mm on these edges (measurement floor), the shell share 0.013. The weight step cancels the
  edge's own length and the rim flattens (`r4_hem_rim.jpg`: purple strip before).
- *The core.* All 226 new crossings are skirt x core: the core's side (76-110 deg, its top
  rings) against the skirt's front-left waist (114-135 deg). All 13 lie_back vertices are the
  core's top two rings at the sides and back-sides. The core lies 6-10 cm inside the chain
  roots' pivots, and its top rings ride the root segments (80% at the top ring, the plain
  blend's hand-over): a root's forward turn swings a point that far inside the pivot about
  three times as far as the skirt at the same height. In cross_legged the side of the core
  came forward through the skirt's waist fold; in lie_back its top went into the hips
  (`r4_core_sections.jpg`, plane cuts of the posed meshes).
- *What did not work* (fast LBS search on dumped skinning matrices, 73 + 19 weight fields,
  then the harness): a wider plain hand-over for the core (`ROOT_BLEND` 0.65 / 0.8 / 1.0, with
  上半身) 238 / 210 / 0 crossings, but 3 / 13 / 20 stretch rows (x2.2 in the kicks and
  seated poses). A pelvis share only at the sides (angle window) x3.6 at the window's edge.
  The pelvis share added to the plain blend between the root and middle segments makes a
  fifth bone; pruned and refitted, it stretched the core x1.99 at chain 13 in jump_tuck and
  high_kick (6 rows). A local linear fit in the shell share instead of the cell mean
  (compress x0.14) helps less than the hem rule below.

**Fix**
- `SHELL_HEM` (0.25 deg, ramp 0-0.25 chain units): where the shell rides its chains' last
  segment alone, its weights are one function of the angle (the band's mean per 0.25 deg,
  read back linearly). cross_legged skirt compress x0.050 -> x0.41; the shell's own
  rows fall or hold (seiza x1.502 -> x1.463, the run's front hem x1.68 -> x1.64, walk clip
  x1.31 -> x1.27; sit_chair x1.621 -> x1.630).
- `PLAIN_BODY` (0.5, 1.3, 2.0): the core hands half its weight to 下半身 at its top, fading
  out by 1.3 chain units below the roots, and rides the root segments alone down to there;
  its segment blend then catches up with the plain one by 2.0 (above the tiers' seams). At
  most four bones by construction (no prune), the seams unchanged. Crossings 226 -> 0, lie_back
  core pen_frac 1.9% -> 0%, and the core stretches less where the roots turn most
  (jump_tuck x1.85 -> 1.73, sit_chair x1.74 -> 1.69, high_kick x1.88 -> 1.83), a little more
  in strides under the tiers' values (curtsy x1.25 -> 1.29, run x1.79 -> 1.80).

**Full merge** (`r11/integrate` 78bca50 + this branch 0f3b98a, scratch merge af2f695, no
conflicts; full motion report 3516 s, `motion_r4.txt`), against round 10 and i14 (1b06af3):

| target | round 10 | i14 | now |
|---|---|---|---|
| cross_legged skirt compress (>= 0.069) | 0.069 | 0.050 | **0.406** |
| lie_back_elbows core pen_frac (<= 1.3%) | 0.5% | 1.9% | **0.0%** |
| cross_legged skirt x petticoat crossings (<= 220) | 214 | 226 | **0** |
| stretch rows over min(round 10, petticoat alone) | 42 | 1 | **0** |
| tier x tier crossings (all poses) | 0 | 0 | 0 |
| run clip skirt pop | - | 55.0 mm | 55.0 mm |
| walk clip skirt pop | 8.2 mm | 9.6 mm | 9.6 mm |
| cross_legged petticoat flips | 3 | 7 | 2 |

The petticoat's pen falls wherever it changed: high_kick 1.24 -> 0.60 cm (pen_frac 1.5% ->
0.45%), lie_back 1.15 -> 0.46 cm, sit_chair 0.87 -> 0.66 cm (1.9% -> 1.3%), jump_tuck 1.8%
-> 0.9%, kneel_one 0.9% -> 0.15%, deep_lunge 0.6% -> 0%, sit_stand clip 2.1% -> 1.6%. No skirt
or petticoat row regresses against i14 (`mdiff`); the regressions it lists are hair x garment
/ hair x skirt crossings and one hair_back stretch, which come with `r11/integrate`'s new hair
merges after 1b06af3: on one model with only this round's change (the rig harness, 41 poses
and clip frames), every hair crossing count is identical before and after.

**Ribbon tails** (bodice; they ride the skirt chains through `SKIRT_BAND`, whose weights this
round does not touch, and the drape is unchanged): kneel_one x1.683, deep_lunge x1.678,
lie_back x1.700, cross_legged x2.091, run clip x1.604, run jitter 0.216, cross_legged
pen_frac 2.0%, all as in i14. The harness shows `DRAPE_BIN` (round 1) is what raised them
(off: kneel_one x1.51, deep_lunge x1.40, run x1.34; but cross_legged x2.14 and 17 skirt /
petticoat rows), so it stays; the tails' own weights are r11/bodice's fix.

**Gates (branch, 0f3b98a = r11/integrate 1b06af3 + this round):** `check.py` CHECK OK, 153,186
faces (petticoat 25,920 / 28,000, skirt 22,680 / 24,000, unchanged). `rig_check.py` RIG CHECK
OK: walk x1.57 (petticoat_tier2), worst squat x1.82 / arms_up x1.81 (body); worst pen
side_bend 1.76 cm (skirt); no backward knee; 66/66 PMX names. Full merge: CHECK OK, 162,561
faces. Not run: export_pmx, pmx_reimport, motion_vmd (mmd_tools is not installed).

**Images**
- `r4_hem_rim.jpg`: cross_legged, the skirt's hem rim at the worst edge, 2 cm wide, same
  camera before / after, from the front-left and from below: faces by their shortest
  edge's ratio (white >= 0.92, yellow 0.5, red 0.25, purple <= 0.08), and clay. Before, a
  purple strip along the rim (the roll flattened to a hard edge in clay); after, yellow at
  worst and a round roll.
- `r4_core_sections.jpg`: plane cuts of the posed body (grey), skirt (green, both faces) and
  core (magenta). Top: cross_legged at z = 0.21 m (the crossing band): before, the core runs
  through the skirt's waist fold; after, it stays under it. Bottom: lie_back_elbows at x =
  0.07 m: before, the core's top crosses into the hip; after, it follows the hip's outline.
- `r4_core_visible.jpg`: the same places with everything shown (ids and cel): the core is
  hidden in both, nothing visible changes.
- `r4_poses.jpg`: jump_tuck, sit_chair (skirt hidden) and high_kick from below, clay and
  cel, before / after: the core's gathers cover the hips in high_kick instead of opening a
  dark gap, the rest as before.

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
  x1.60 in the run clip. The close-ups (`r3_ribbon_tails.jpg` (dropped from the PR for size; later rounds' crops supersede it)) show no visible change.

**The round-2 p3 items:**
- *Front tiers in walk / curtsy:* fixed (above).
- *Core top ring in lie_back:* 1.45 -> 1.15 cm, 2.4 -> 1.9% (petticoat alone 0.95 cm, 1.5%).
  It is hidden under the skirt and bodice.
- *Ribbon tails in cross_legged:* 1.36 cm (round 2 1.32, round 10 1.39). Unchanged; this is
  the bodice's (its tails take the skirt chains' weights).

**Images:**
- `r3_heat.jpg` (dropped from the PR for size; later rounds' crops supersede it): stretch heat on the tier that sets each row (white 1.0, yellow 1.6, red 2.0),
  outer layers hidden. Walk tier1, curtsy, sit_chair and jump_tuck tier2, round 2 against
  now.
- `r3_walk_curtsy.jpg` (dropped from the PR for size; later rounds' crops supersede it): walk and curtsy, cel, and clay with the skirt hidden.
- `r3_seated_lying.jpg` (dropped from the PR for size; later rounds' crops supersede it): sit_chair and run_l with the skirt hidden, lie_back from below, and
  cross_legged.
- `r3_ribbon_tails.jpg` (dropped from the PR for size; later rounds' crops supersede it): the waist-bow tails in kneel_one and deep_lunge.

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
- Result: x1.17 / 1.15 / 1.22 / 1.18 (`r2_waist_twist_heat.jpg` (dropped from the PR for size; later rounds' crops supersede it): stretch heat, white 1.0,
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
  (`r2_core_clearance_test.jpg` (dropped from the PR for size; later rounds' crops supersede it)). Before the integration fix, the sparse sample of the core
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
  chain 6 (rest azimuth -56, z 0.64: a purple column in `integ_core_heat.jpg` (dropped from the PR for size; later rounds' crops supersede it)). Swap test:
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

**Images.** `integ_run18.jpg` (dropped from the PR for size; later rounds' crops supersede it) / `integ_run18_zoom.jpg` (dropped from the PR for size; later rounds' crops supersede it): run@18 from the left and the front,
cel and clay, before / after (the thigh no longer cuts the front frill).
`integ_core_heat.jpg` (dropped from the PR for size; later rounds' crops supersede it): the core in cross_legged and lie_back_elbows coloured by edge
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
- `r2_waist_twist_heat.jpg` (dropped from the PR for size; later rounds' crops supersede it): integration review round 2. The skirt's front-left waist band in
  torso_left, twist_bend and look_over_shoulder, coloured by stretch (white 1.0, yellow 1.6),
  before and after `CHAIN_BODY_KEEP`.
- `r2_core_clearance_test.jpg` (dropped from the PR for size; later rounds' crops supersede it): the gated test pose with the core in the drape's clearance (this
  branch) and left out of it (experiment v2): the thigh comes through the core and the inner
  tiers hang into it (cel; clay zoomed, skirt and bodice hidden).
