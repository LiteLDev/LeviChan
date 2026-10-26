# R8-1: skirt that drapes over the lap, not a bowl

Round 7's drape (`rig._skirt_drape`) kept the thighs out of the cloth, but every neighbour of a lifted chain was lifted too (a cone round the ring, 13/11/9° per chain step). In sit_chair, seiza, kneel_one, cross_legged, deep_lunge, lie_back_elbows, jump_tuck, high_kick and the seated frames of sit_stand, the whole skirt and petticoat ring swung up into a rigid bowl that showed the pink underside.

All changes are in `levi/rig.py` (the skirt drape section and its drivers) and in the CLAUDE.md drape notes. The part meshes, the PMX export code and the skinning are unchanged.

## What changed (Blender rig; the PMX keeps its linear shares)

- **Gather instead of a cone** (`_drape_gather`). Each segment still gets its least clearance turn off the thigh (`_drape_clear`). That clearance is now tabulated at five yaws, `DRAPE_YAW_GRID`.
  - A coordinate descent then picks each chain's yaw round the body (±30°) and an extra root lift, per thigh and per pitch sample.
  - It trades off four costs: ring strain against the innermost cloth's spacing (`DRAPE_TAUT`, `DRAPE_INNER`), how far the joints move (rising and moving into her cost most), yaw, and yaw change.
  - Result: the chains on the thigh lie on it, the side cloth gathers forward at its own height and hangs, and the cloth between the legs follows only as far as the narrow front needs.
  - The back keeps its place round the body (`DRAPE_YAW_BACK`). Otherwise both thighs' gathers fan it apart.
- **Ring cap** (`DRAPE_RING_CAP` 18/16/14° per step, applied last). It is narrowed where the inner cloth lies close (`DRAPE_RING_CAP_MIN`, the front between the thighs). It is wider than round 7's cone.
- **Yaw** turns the chain round the body. It sits on the root `追従右` bone (`_skirt_yaw_driver`).
  - Both thighs' yaws are added.
  - Each thigh's yaw fades out smoothly as the other thigh lifts the chain (`DRAPE_YAW_OWN`).
  - The total is clamped to ±`DRAPE_YAW_MAX`.
- **Seat** (`_skirt_seat`, on the lower `追従右` bones). It only acts when both thighs are raised and a foot is on the ground. The joints below the roots then swing out just enough to stay above the seat, `SEAT_DROP` below the hips.
  - On a chair (shins hanging) only the back lies on the seat and the sides hang beside the hips.
  - On the floor (shins level: seiza, cross-legged, legs out) the sides spread too.
  - Heights are read in world space and measured in shin lengths.
- Smoother tables (`DRAPE_SMOOTH` 8). With 5, a 6 mm pop showed when rising from the seat.
- Clearance is now sampled with 300 points per sector at 2° steps (was 900 points at 1°). This pays for the five-yaw grid. The build takes about 1–2 min longer.
- Tried and dropped:
  - A bent-knee table set: it changed nothing, because the hem ends at the knee.
  - Bending the hem joint 36°: x2.9 on the petticoat in run_r.
  - A hard body-limit clamp: x3–5 stretch.
  - Tighter caps (16/14/12, 14/12/10): they cut the stretch maxima but brought the bowl back, and pairwise Codex (astra) preferred 18/16/14 over them, 8–2 and 7–2 (`ab_cap18_vs_cap14.md`, `ab_v17_vs_final.md`).

PMX: `_drape_share` still exports the drape's linear part at 60° of thigh pitch. It now reads the new tables, so the starting point for the physics bodies has lower sides. The leg and skirt physics bodies are unchanged.

## Results

Sheets: `baseline_p01/p02_poses.jpg` (main) vs `final_p01/p02_poses.jpg`, plus `final_c_sit_stand.jpg` and `final_c_run.jpg`.

**Pairwise, shuffled A/B, main vs this PR** (`ab_main_vs_final.md`, 17 poses / clip frames):

- gpt-6-astra: new 14, old 0, tie 3.
- gpt-6.1-sol: new 11, old 1 (cross_legged), tie 5.

Every target pose went to new with medium or high confidence, except jump_tuck and lie_back_elbows, which gpt-6.1-sol called a tie. walk, spin and curtsy were ties, so nothing got worse there.

**Single ratings** (`final_review.md` vs `baseline_review.md`, astra / sol):

| pose / clip | main | this PR |
|---|---|---|
| sit_chair | major / major | major / minor |
| jump_tuck | major / major | major / minor |
| lie_back_elbows | major / major | minor / minor |
| sit_stand | major / major | major / minor |
| high_kick | minor / major | major / minor |
| cross_legged | major / major | major / major |
| seiza, kneel_one, deep_lunge, run_l/r, run, idol_dance | minor | minor or clean |
| walk, turn, curtsy | clean | clean |

Worst rating per pose / clip, over all 30: main 13 clean, 10 minor, 7 major; this PR 10 clean, 15 minor, 5 major.

Single ratings are noisy. One earlier run of nearly the same rig scored 14 clean, 14 minor, 2 major, with sit_chair, jump_tuck and sit_stand at minor/minor. The pairwise A/B is the stable signal.

astra still calls the seated lining a "rigid shell". With physics off, the petticoat under a lap-level hem stays visible from the front; in MMD the drape below the roots is simulated.

**Metrics** (`rig_check --extended --motion`, worst skirt/petticoat values, main → this PR):

| | stretch | pen cm | pen % |
|---|---|---|---|
| sit_chair | 1.71 → 2.14 | 0.6 → 0.7 | 1.2 → 1.4 |
| seiza | 1.67 → 1.64 | 0.7 → 0.6 | 1.6 → 0.3 |
| kneel_one | 1.66 → 1.84 | 0.7 → 0.6 | 0.5 → 0.3 |
| cross_legged | 2.27 → 2.47 | 3.5 → 3.3 | 8.9 → 6.9 |
| deep_lunge | 1.71 → 1.83 | 0.6 → 0.6 | 0.5 → 0.3 |
| run_r | 1.91 → 2.09 | 1.1 → 0.9 | 0.7 → 0.1 |
| jump_tuck | 1.99 → 2.47 | 0.5 → 0.6 | 0.2 → 0.3 |
| high_kick | 2.00 → 1.90 | 1.8 → 0.7 | 1.2 → 0.5 |
| lie_back_elbows | 1.84 → 2.22 | 1.4 → 1.4 | 1.7 → 1.0 |
| run (clip) | 2.10 → 2.19 | 1.1 → 1.1 | |
| sit_stand (clip) | 1.96 → 2.14, pop 3.3 → 3.5 mm | 1.7 → 1.7 | 2.6 → 2.1 |
| walk (clip) | 1.59 → 1.65 | 0.8 → 0.7 | |

- Penetration is the same or lower everywhere, and flips in cross_legged went from 49 to 9.
- No new pops: the worst skirt pop is 3.5 mm in sit_stand.
- **Known regression: peak edge stretch.** It is now 2.1–2.5, at the outer skirt between the back-side chains (スカート5_1) where the pulled front meets the hanging back, in sit_chair, sit_stand, lie_back_elbows and jump_tuck, and at スカート14_1 in run_r. It is above the 2.0 "major" line where main was 1.8–2.0.
  - This is the price of letting the sides hang instead of lifting them. Every cap or strain setting that brought it under 2.0 brought the bowl back, and the pairwise reviews rejected it.
  - The core 17 poses all stay ≤ 1.77 (gate 1.85, rig check OK, repeatable).
- Rest look is unchanged: `review.py --baseline` metrics and shade islands are byte-identical to main.
- PMX: `export_pmx.py` (195 bodies, 171 joints), `pmx_reimport.py` (REIMPORT OK) and `motion_vmd.py` (round trip 0.00 mm) all pass.
- `check.py`: OK, 99,010 faces.

## Review findings fixed

From the code-review pass:

- The gather's previous-sample term now compares against the turns actually chosen.
- Clearance between tabulated yaws uses the larger of the two bracketing samples.
- Missing sectors break the ring.
- The yaw is clamped.
- The seat and floor drivers are scale-invariant.
- Fixed axis-angle axes are held by constant drivers, so a pose reset cannot turn the yaw into a pitch.
- The stale `DRAPE_RING_STEP` constant is gone and the docs are updated.

The ring strain still counts from the innermost cloth's spacing (`DRAPE_TAUT`), on purpose. Measuring only the growth pulled the back into her when seated, and pairwise review preferred the taut version.

## Tripo fold-depth reference (optional, not kept)

Tripo's hem has deeper tube folds, so I tried deeper folds through mid-skirt: `skirt.MID_CREST` 0.35 → 0.6. The troughs, the petticoat clearance and the hem outline stay put. Against this PR's look baseline (`review.py --baseline`):

- side silhouette IoU went from 0.859 to 0.853 (dress region −0.009);
- front and back dress IoU dropped by 0.003;
- the 3/4 front view gained 3 dress shade islands.

The hard constraint was that nothing may get worse, so the change is reverted and the skirt part is unchanged. Deeper relief without moving the silhouette would need the folds deepened inward (troughs), which the petticoat clearance and SKIRT_GAP constrain. That is a separate part task.
