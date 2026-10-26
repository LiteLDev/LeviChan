# R8-2: MMD shoulder flip, run clip, bend-span metric (knee experiments documented)

Files touched:
- `levi/rig.py`: the shoulder / PMX bone section, plus a comment on the knee experiments;
- `export_pmx.py`: local axes for the new followers;
- `tools/pmx_reimport.py`, `tools/motion_vmd.py`: the shoulder checks;
- `tools/motion_check.py`: the bend-span metric, a shared file;
- `tools/motion_poses.py`: the run clip's keys only (name and length unchanged);
- `CLAUDE.md`: the rig and motion-test sections.

`body.py` is unchanged.

## 1. MMD 180° shoulder flip: fixed in the PMX

**Cause.** In the PMX, 肩補助 / 肩補助2 / 肩補助3 / 腕D were plain 回転付与 shares of 腕. MMD slerps a share from identity along the shortest path, so a share flips sides when 腕's turn passes 180°. Blender had used swing + twist drivers since round 7, but those cannot be exported.

**Construction** (`rig.SHOULDER_PMX_SWING`, `rig._shoulder_pmx_swing`), PMX-expressible and stateless:
- `肩スイング` is a hidden one-link IK bone: a child of 肩 at the shoulder joint, pointing along `SHOULDER_SWING_REF` (out, a little up and back). It aims at `肩スイングIK`, which rides 腕 at the elbow. Its turn is B, the swing from the reference direction to the arm.
- `肩基準` is the same IK aimed at a goal fixed on 肩 at the rest elbow, so it holds the constant A.
- Hidden parents chain shares of B and A, so every bone turns by B^t A^−t. That is identity at rest, and Blender's stages without their twist share:
  - 肩補助親 (+s B) → 肩補助 (−s A) = B^s A^−s;
  - 肩補助 → 肩補助Na (+s A) → Nb (+(t−s) B) → 肩補助N (−t A) = B^t A^−t;
  - 肩補助 → 腕Da (+s A) → 腕Db (−s B) → 腕D (+1 腕) = **腕 exactly**.
- The arm's twist goes to 腕D, and 腕捩 carries it down the limb.
- B is continuous everywhere except with the arm pointing straight across the front of the body to her other side, the same singular direction as Blender's stages. Every pose and clip stays at least 64° from it.
- In Blender the new parents have no constraints and stay at rest, the IK bones deform nothing, and the round-7 drivers still run. **Blender's deformation is unchanged**: core gate and look metrics are identical to main.
- mmd_tools emulates a 付与 share by scaling the source's Euler angles in the follower's frame, not by slerp. Two measures keep that emulation exact or stable:
  - Every follower gets PMX local axes with X along A's axis (`mmd_local_x` → export_pmx). MMD itself ignores local axes when it deforms.
  - The hidden followers point along the reference, which keeps B's Euler Y below 90°. Without this, an Euler gimbal flip in mmd_tools gave a 439 mm/frame² pop at idol_dance@31.
- The PMX gains 26 hidden bones (13 per side, including 4 IK). Totals: 389 bones, 213 append bones, 52 with local axes.

**Verification.**

| check | round 7 PMX | this PR |
|---|---|---|
| `pmx_reimport` sweep: 腕 turned 210° sideways past overhead, worst step of 肩補助 / 2 / 3 per 5° | **53 / 154 / 106°** | 0.9 / 2.6 / 4.2° |
| … the same, raised forward (new sweep) | — | 1.4 / 3.9 / 5.9° |
| `motion_vmd` idol_dance, PMX + VMD: shoulder helpers' worst acceleration (Blender rig: 51.0) | **455.1** mm/f² (左肩補助2 @ 81) | 45.6 mm/f² (左肩補助3 @ 79) |
| `motion_vmd` walk / turn | 3.1 / 2.5 | 4.6 / 2.6 |
| VMD round trip, rig vs PMX | 0.00 mm, 8.0 mm | 0.00 mm, 8.0 mm |

- The checks themselves are new: `pmx_reimport.check_shoulder` (two sweeps per side) and the shoulder-acceleration columns and gate in `motion_vmd`.
- In MMD the chain returns 腕D = 腕 exactly. mmd_tools' Euler emulation leaves 腕D up to 4.7° (left) / 12° (right) off 腕 at the top of a sweep; round 7's plain shares gave 5.2°, with the flips.
- PMX vs Blender: the PMX stages take no twist share, and the PMX shrug is swing-based at every angle, whereas Blender's clavicle keeps q^0.15 below 100°. The clips differ from the Blender rig no more than before: 8.0 mm in idol_dance, 1.8 mm in walk.

Files: `final_shoulder_check.txt`, `baseline_shoulder_check.txt`, `final_vmd_report.md`, `baseline_vmd_report.md`.

## 2. Run clip: re-authored as a smooth stride

- **Each ankle path** (the IK target: forward, up, foot pitch) is a periodic uniform cubic B-spline over 12 control points per cycle (`motion_poses.RUN_FOOT`).
  - It is C2, so velocity and acceleration never jump.
  - It stays inside its control polygon, so the stance never dips below the ground.
- **The stride:** stance is ~35% of the cycle, so the run has two flight phases. Toe-off is on the toes, the heel kicks up behind, the knee drives forward, and the foot reaches out to strike.
- **The rest of the body:**
  - The pelvis is lowest at mid-stance and highest in flight.
  - The arms swing opposite the legs, with the elbows at 80–96°.
  - Torso and pelvis counter-rotate.
  - Every channel is a smooth function of the phase.
- **Keys:** every frame, 41 keys, still 40 frames and 1.5 strides/s. Round 7 keyed every 2.5 frames rounded to 2 or 3, and its rectified sines kinked the foot path.

| run clip metric | round 7 | this PR |
|---|---|---|
| bone pop (worst) | **74.3** mm ひざ補助.R @20 (IK target spike) | 51.7 mm スカート14_2 @7 (skirt drape chain); no body or knee bone in the list |
| vertex pop | **78.9** mm petticoat @20 | 56.5 mm petticoat_tier0 @7 |
| jitter | 0.37 hair (後髪束17_3) | 0.37 hair (後髪束17_3) |
| least knee bend (Blender rig) | 25.2° | 32.4° |
| knee volume | 0.67 | 0.65 (deeper heel kick; seiza and run_l are 0.65 / 0.60 on main) |
| shoes_ribbons inside the ankle | 2.9% | 3.1% (pointed toe-off) |

- Codex: both models rate the run clip **minor / minor**, as on main. The notes are about skirt stiffness without physics, not body or knee.
- Pairwise A/B against round 7 (`pairwise_run.md`, `run_ab.jpg`): final keys 3 / 3 for both models. The previous iteration scored 4 / 2 for both; it had a 5–15° deeper heel tuck and toe pitch, which I relaxed to keep the shoe ribbons out of the ankle.
  - The reviewers like the flexed recovery knee and the heel lifted behind.
  - At frames 8–12 they still prefer round 7's more open knee.
- Sheets: `baseline_c_run.jpg`, `final_c_run.jpg`.

## 3. Bend span metric (`motion_check.SPAN_JOINTS`, reported, not gated)

- **What it measures:** for the knee, elbow and wrist bent more than 45° since rest, the outer (convex) skin line's points are averaged per 5 mm of rest length. The metric is the rest distance over which that line turns from 10% to 90% of the joint's bend, in limb diameters.
  - It is geometric: weights and helper pivots don't matter.
  - Thresholds are 0.7 / 1.0, following the joint guide's target.
- **Round 7 values:** knee ~0.95 in squat / seiza (minor); elbow ~1.7 at 120° (major).
  - The new elbow rows are what add body majors to the report. Without span, the motion majors are 92 → 95. Every changed row is in the run clip (see above): shoe ribbons 3.1%, knee volume 0.65, and the petticoat pop, now on a different object; the knee-helper pop is gone.
- **The ankle is left out.** Its bone runs from above the shoe to the toe, and the value was noise.

## 4. Squat knee: nothing kept (`pairwise_knee.md`, `knee_variants.jpg`)

I followed the joint guide's direction and then the other options in the brief, judging each by a pairwise shuffled Codex A/B against round 7 over 9 knee poses:
- **Narrower bands**, down to the reference models' ±2.5–5 cm, with or without a flat kneecap face: lost 7–9 of 9 poses in every build ("pinched", "angular notch", "ring creases"). Both models consistently prefer the rounder, fuller round-7 knee.
- **Knee pivot moved back** (`KNEE_FWD` 3 / 10 px): the leg IK then folds seiza only to 88° (squat to 5°).
- **Translating helpers** (the knee helpers turning about points 1–3 cm in front of the joint, which PMX 付与 expresses as is):
  - At 2 cm the A/B is about even (astra 5 / 8 / 5 new / old / same, sol 6 / 6 / 6 over two shuffles), and squat was rated minor / minor.
  - But folded faces in the hollow tripled (seiza 54 → 162, jump_tuck 44 → 108), knee volume fell 0.65 → 0.60, and the bend span grew 0.96 → 1.19.
  - Back partners about the joint fixed those metrics but turned the squat "knobby" (major / major).

**Status:** squat is rated **minor / minor** in a second `rig_rate` run on round 7's knee (first run: minor / major). review.py's sheet-scale pose rating stays major / major, as on main.

## Gates and reviews

- **Core gate:** OK. All 17 poses are identical to main (arms_up 1.77, squat 1.72): `final_core_gate.txt`. `check.py` OK, 99,010 faces.
- **PMX:** `export_pmx.py`, `pmx_reimport.py` and `motion_vmd.py` (walk, idol_dance, turn, run) are OK.
- **`review.py --build --baseline` (round 7):** `metrics.txt` and `shade_islands.txt` are byte-identical to the baseline, so the look has not changed. Summary in `final_look_review_summary.md`.
- **Motion suite:** `final_motion_report.md` and `baseline_motion_report.md`; the run clip at the final keys is in `final_motion_run_clip.md`.
- **Codex per pose / clip:** `final_motion_review.md` and `baseline_motion_review.md`. Body and rig are unchanged apart from the run clip.
