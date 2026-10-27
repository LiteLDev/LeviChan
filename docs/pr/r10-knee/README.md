# R10-K: knee joint in the 风堇 MMD style

The user decided on the knee style: it follows the 风堇 (Hyacine) MMD model's knee, a compact, angular knee with a defined corner instead of our wide "rubber hose" arc. This unit changes the rig and the pivot only. No geometry was copied, and the kneecap shape is unchanged.

## What changed

- **Knee weights** (`rig.JOINT_ALONG['ひざ']`, `rig._split_joint_aux`).
  - The round 6–9 hinge partition (`JOINT_HINGE`, `JOINT_HINGE_CAP`) and the two knee helpers `ひざ補助` / `ひざ補助2` are gone.
  - The thigh and shin now blend directly (2 bones per vertex, like Hyacine).
  - The blend is a smoothstep along the limb from the pivot, with knots ±3.25 cm at the front, ±4.5 cm at the sides and ±6 cm at the back.
  - The knots are interpolated round the limb as a quadratic in the cosine toward the front.
- **Pivot.** `body.KNEE_FWD` goes from 15 px to 5 px. The pivot moves from 23% to 43% of the leg's depth behind the front skin.
- **Leg IK** (Blender only, `rig.KNEE_IK_PREBEND`, `rig._knee_prebend`).
  - With the pivot near the hip–ankle line, Blender's solver starting from a straight leg found no bend: seiza folded to 18° instead of 150°, and jump_tuck to 28°.
  - A Limit Rotation `IK prebend` (X ≥ 20°) now sits first on ひざ, so every solve starts from a bent knee. The IK still solves the whole chain, and rest stays straight.
  - Its influence follows the 足首 IK's mute, which `leg_fk` toggles together with the knee's, so FK knees still straighten.
  - Reading the knee's own IK made a depsgraph cycle. Reading the 足首 IK does not.
  - `strip_blender_only` removes the prebend before the PMX export, because mmd_tools would export any Limit Rotation on the knee as its IK link limit.
  - The PMX knee keeps the standard limit (−180…0° about X, checked by `pmx_reimport`).
- **Skirt drape** (`rig.DRAPE_KNEE_FWD`, one argument in the skirt section).
  - The drape's thigh line still runs through round 9's knee point, 10 px ahead of the new pivot. The skin did not move, and the drape tables were tuned on that line.
  - Through the new pivot, the petticoat stretched ×2.0–2.4 in cross_legged, high_kick, run and spin.
- **CLAUDE.md**: the knee paragraph and the Leg IK paragraph are rewritten, and the round-8 "tried and dropped" note is marked as overruled.

## Hyacine vs main vs this PR

Measured with the same script on all three (`kneeprof.py`: share of ひざ's turn against the distance along the limb, per 45° sector) and with `motion_check` (span, vol, flips).

| | Hyacine (PMX) | main (round 9) | this PR |
|---|---|---|---|
| band 10→90%, front / sides / back | 7.5 / 8.2–8.5 / 8.4 cm (2.1–2.3 R) | 17.7 / 17.6–18.1 / 16.7 cm | 4.3 / 5.6–6.0 / 7.5 cm |
| t50 | −0.0 … −0.3 cm | 0 … −0.5 cm | 0 … +0.2 cm |
| bones per vertex in the band | 2 | 2–3 (2 helpers) | 2 |
| pivot depth (from the front skin) | 51% (this script; the earlier guide: 40%) | 24% | 43% |
| bend span, squat / seiza | 0.51 / 0.66 (guide's script) | 0.95 / 0.95 | **0.63 / 0.71** |
| knee vol, squat / seiza | 0.63 / 0.59 (guide) | 0.72 / 0.66 | 0.74 / 0.62 |
| flipped faces, squat / seiza | 7 / 8 (guide) | 24 / 52 | 34 / 8 |

Hyacine's own profile (variant H0, ±6.6 cm, the same all round) still bent over a long arc on our ~3× denser loft: span 0.83 in squat and 0.95 in seiza. Her rings are 2.3 cm apart, so her turn lands on a single ring. The narrower front brings our span into her range.

Knee angles (`rig_check.knee_bends`, relative to rest):

| pose | main | this PR |
|---|---|---|
| squat | 101.1° | 106.4° |
| seiza | 143.6° | 150.0° |
| jump_tuck | 129.7° | 134.9° |
| kneel_one | 83.2° | 88.3° |
| sit_chair | 85.8° | 91.0° |

The poses place the same feet, and the rest leg now has less forward kink, so every IK knee bends about 5° more than before. Seiza now folds further, not less. FK knees (cross_legged, high_kick, test) are unchanged.

Full per-pose knee metrics are in `knee_metrics.md`.

## Variants and pairwise Codex A/B

Nine knee poses (squat, walk, seiza, kneel_one, deep_lunge, run_l, jump_tuck, curtsy, sit_chair) were rendered cel and clay, each as a front + 3/4 + side strip with the skirt, petticoat and back hair hidden. Both models (gpt-6-astra, gpt-6.1-sol) saw every pair in both orders, and a pick counts only when both orders agree. Full tables are in `pairwise_knee.md`.

| variant | profile | vs main (astra, sol) | vs H0 (astra, sol) |
|---|---|---|---|
| H0 | Hyacine's: ±6.6 cm all round, no helper | 16–2, 18–0 | — |
| H1 | ±5.6 cm with a 50% helper at the pivot | 2–16, 16–2 | 2–16, 4–8 |
| N1 | Nahida's: narrow back ±2.1 cm, front −3.5…+7.5 cm (t50 +2 cm), 50% helper | 8–10, 18–0 | 0–18, 0–18 |
| H2 | H1 with the front shifted 1.5 cm down | 6–12, 18–0 | — |
| H0n5 / H0n4 | ±5 / ±4 cm all round | 16–2 / 18–0, 16–0 / 18–0 | ties (position bias) |
| H0f2 | H0 with the pivot at 47% (KNEE_FWD 2.5) | 12–6, 12–6 | 0–6, 0–8 |
| H0b / H0c | front ±3.5 / ±4, sides ±4.5, back ±6 / ±5.5 cm | 18–0, 18–0 | ties |
| **H0e (chosen)** | front ±3.25, sides ±4.5, back ±6 cm | **18–0, 18–0** | ties |

- Every helperless compact variant beat main with both models.
  - The reasons given: "clearer front corner", "firmer thigh and shin", "main spreads the bend into a rubbery arc". The only picks for main were astra's two seiza items against H0 ("pointed, flattened knee fronts").
- Within the helperless family both models only tied: each picked whichever side was shown on a fixed side.
  - So the metrics chose: the span target (≤ 0.7) in squat / seiza, and the hollow's flips and compression.
  - Front ±3.0 cm (H0d) reached span 0.61 / 0.69 but stretched the kneecap ×1.91 in squat, too close to the ×2.0 gate. H0e reaches 0.63 / 0.71 at ×1.82.
- A helper or Nahida's asymmetric profile made the knee rounder (H1) or bulbous (N1), and lost to the plain blend.
  - N1 also flipped 92–126 faces in seiza / cross_legged.
- The pivot at 52% (KNEE_FWD 0) widened the span (squat 0.98). The pivot at 47% lost the A/B, and with an 8° prebend its IK failed in sit_chair, kneel_one and sit_stand. At 43% the IK reaches all 170 core / extended poses and clip frames (every 3rd) with no miss.

Before / after (main on top, this PR below; front, 3/4 and side of the legs, skirt hidden):
- `knee_clay_main_vs_new.jpg`: squat, seiza, kneel_one, jump_tuck.
- `knee_cel_main_vs_new.jpg`: squat, sit_chair, run_l, deep_lunge.

## Gates

| gate | result |
|---|---|
| `tools/check.py` | CHECK OK (107,968 faces) |
| `tools/rig_check.py`, 17 core poses | RIG CHECK OK. Max stretch ×1.82 (squat, walk, fist), max cloth penetration 1.71 cm (walk, hair_back), no backward knee (`final_core_gate.txt`). |
| leg IK, every core / extended pose and every 3rd clip frame | 0 misses in 170 (`iktest`), no depsgraph cycles |
| `export_pmx.py` + `tools/pmx_reimport.py` | REIMPORT OK. Knee IK limit −180…0° about X (L / R), VMD walk round trip 0.00 mm, least knee bend 22.9°. |
| `review.py --baseline` (main) | ortho IoU, regions and shade islands identical to main (the rest mesh is unchanged) |

## Motion suite (`rig_check -- --quick --no-core --extended --report-core --motion`)

Full reports: `baseline_motion_report.md` (main) and `final_motion_report.md`.

- **Knee.**
  - Span: 0.51–0.71 in every bent pose (main 0.94–0.95).
  - Flips: seiza 52 → 8, jump_tuck 47 → 21, cross_legged 53 → 44. Squat 24 → 34, kneel_one 17 → 31, sit_chair 0 → 23.
  - Volume: deep folds 0.62–0.66 (main 0.66–0.68; Hyacine 0.59–0.63). New vol majors (< 0.65): seiza, jump_tuck, run.
  - Compression in the hollow: 0.08–0.12 (main 0.13–0.17), which gives new compress majors (< 0.12) in most bent poses. This is what the short back band costs.
  - Knee stretch: ≤ ×1.93 (kneel_one, as main ×1.90).
- **idol_dance@60** (the clip steps the leg through full extension and back): the knee pops 5.4 cm (main: 3.7 cm on ひざ補助). A near-straight chain moves the knee further for the same foot travel.
- **Outside the knee**, majors that are new by location:
  - The petticoat stretches ×2.10 in cross_legged (main ×2.00 there).
  - sit_chair / sit_stand skirt ×2.08 on chain 5_2. Main had ×2.07 on 5_1.
  - The run pop moved from skirt chain 1_2 to 2_2, at the same size (8 cm).
  - The thigh × thigh self-contact moved from run_r (5.1 cm) to cross_legged (3.0 cm).
  - squat shoe-leaf penetration 3.4% (main 2.3%, minor). The leaves ride the shin.
  - A walk finger bone pop of 8 mm.
- Total majors: 125 vs main 108. 22 of the new rows are the knee's own compress / vol / pop rows.

## Single-pose review (`review.py`)

The squat is rated major by both models ("angular hinges", "pinched inner creases"). Main's was minor (sol, for the petticoat) / major (astra, "tight inner notches"). Both models also ask for more kneecap fullness at deep flexion.

No kneecap change is in this PR. The corner reads from the weights and the pivot, and round 8's flatter kneecap face lost the review. A flexion corrective that restores kneecap projection would be the next step if wanted.

## Motion review

`motion_review.py` was run on the knee poses and the walk, run and sit_stand clips. Its ratings are in `final_motion_review.md`.
