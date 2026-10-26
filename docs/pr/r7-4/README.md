# R7-4: sleeves, shoe leaves and neck ornaments in motion

The unit covers the sleeves, the shoe leaves and the small ornaments: `levi/parts/shoes.py` and the sleeve-drape and ornament-weight sections of `levi/rig.py`, plus a small physics change in `export_pmx.py`. No geometry changed. The face counts stay at sleeves 7,896, shoes 3,452 and accessories 3,264.

## What changed

**Sleeve drape counter-rotation is continuous (Blender only).**
- `袖追従` used to be driven by 腕's quaternion to the power −0.75. That branch switches when 腕 passes 180°, and the drape jumped 300 mm in one frame (idol_dance@81, pop 107 mm).
- `袖重力` is a new helper. It is a child of ひじ and turns back all of 腕, using the conjugate quaternion, which has no branch.
- 袖追従 Copy-Rotates toward `袖重力`. The influence is 0.75, as before, and ramps to 1 between 150° and 180° of 腕's turn (`SLEEVE_COUNTER_FULL`). At 180°, where shortest-arc blending switches sides, the two sides give the same result.
- The drape now only follows the arm. At idol_dance@80–81 its acceleration equals the wrist's, about 112 mm.
- The remaining arm pop at that frame is R7-1's 肩補助2 / 腕D flip.
- The PMX keeps the −0.75 append, so nothing changes in MMD with physics off.
- Rejected: turning back the forearm's whole world rotation (gravity style) folded bags bent overhead into the upper arm, with 130–330 flipped faces.

**Crowded sleeves compress (Blender only).**
- The sleeve's forearm share now rides `袖胴`, a deforming copy of ひじ. In MMD it just follows ひじ.
- 袖胴's local X/Z scale flattens the bag toward the forearm by up to 50%. This happens when the two drape roots come within 32 → 12 cm of each other (arms crossed or folded), or when the wrist comes within 18 → 10 cm of 上半身 / 上半身2 / 首 (a hand on the flank, an arm across the chest).
- The drapes also shrink about their roots by the first measure.
- Copies of 手捩 and 手首 were tried and dropped. They also flattened the hem and the cuff ruffle into the wrist and into the other forearm (arms_crossed cuff 0.2% → 4% inside).

**Wider elbow band for cloth that stands off the arm.**
- For cloth near the elbow, the distance along the arm is scaled by b / (b + c (d − r0)), where d is the distance from the arm axis (`SLEEVE_ELBOW_SPREAD`). The inner side of the bag then folds instead of collapsing.
- The drape now fades in from sleeve parameter 0.35 (was 0.12) and out from 0.7 (was 0.85). This takes the stretch out of the cuff transition.

**PMX physics.** The right sleeve's drape bodies have their own collision group (`export_pmx.SLEEVE_R_GROUP` = 5). The two sleeves now collide in MMD; before, both sleeves were in group 3 and ignored each other.

**Choker.**
- It rides the neck skin. The skin's weights at the tube's centre line are sampled at 72 stations round the loop and smoothed over 12°.
- A whole cross-section of the tube shares one set of weights, so it cannot shear. Before, 首 / 上半身2 were split across the tube's height.

**Halter cords.**
- They take the weights of the skin under them, with at most 12% of the arm, like the bodice.
- The weights are smoothed wider than the cord's girth.
- Before, they used envelope weights.

**Shoe leaves.**
- At the root they keep the ankle wrap's weights. The part now stores where the leaves spring from (`obj['levi_attach_points']`).
- Further out they blend toward the shin skin's weights. The blend is one rising function of the distance from the root, so both faces of the 1.6 mm blade share their weights.
- Before, each leaf was rigid on the wrap's ankle blend and swung into the leg when the foot turned or pointed.

## Motion metrics on these parts (`metrics_delta.md`)

Worst value per pose / clip and object, before (main, 34dc8c8) and after:

| | major | minor |
|---|---|---|
| sleeves + shoes + accessories rows, before | 37 | 96 |
| after | 21 | 83 |
| report "issues by part": sleeves | 18 → 9 | 72 → 62 |
| accessories | 12 → 6 | 15 → 9 |
| shoes | 7 → 6 | 9 → 12 |

Fixed majors:

| metric | before | after |
|---|---|---|
| sleeve_balloon pop, idol_dance@81 | 107 mm | gone |
| sleeve_balloon flip, hands_behind_head | 114 faces | 6 |
| sleeve_balloon stretch, hands_behind_head | ×2.12 | ×1.87 |
| sleeve_balloon compress at the elbow (arms_crossed, hands_behind_back, lie_back_elbows, run, run_l/r, idol_dance@74) | 0.07–0.11 | 0.14–0.24 |
| acc_choker stretch, look_over_shoulder / lie_back_elbows | ×2.47 / ×2.41 | ×1.15 / ×1.01 |
| acc_halter inside, dance_heart / dance_sway / reach_up_back / idol_dance@48 | 11.2 / 6.6 / 5.2 / 11.2% | 0.4 / 0.4 / 0.0 / 1.1% |
| shoes_leaves inside, turn / spin | 29.1% (2.5 cm) / 14.9% | 6.8% (1.4 cm) / 3.4% |

The core gate passes. arms_up was at the 1.85 cap with sleeve_balloon; now its worst is body at ×1.79, with sleeve_balloon about ×1.75. No core pose is worse than ×1.79 (`baseline_rig_check.txt`, `final_rig_check.txt`).

Majors that remain, with causes:
- **sleeve_cuff inside the body** in hug_self (12.9%), dance_point (7.3%) and idol_dance@74 (17.5%). The hands press into the flanks, and at idol_dance@74 the forearm passes through the thigh (a body self-intersection). These numbers are unchanged. Flattening the cuff (see above) moved the problem into the wrist.
- **Hair leaves (acc_leaves / veins) inside the raised upper arm** in reach_up_back and idol_dance@81. The arm passes through the leaves at the ears, which are rigid on 頭. Unchanged.
- **acc_halter, hands_behind_head: 12.9% → 4.5%.** The chest skin bulges forward under the raised arms. bodice_shell shows the same at the same spot (6.5%).
- **shoes_leaves, turn@35 6.8% and spin@19 3.4%.** This is the right leaf inside the left shin: the clip's legs pass through each other there (body thigh × thigh and shin × shin majors). shoes_shell in turn (feet crossing) and seiza (heels into the seat) is the same contact, and the shell pop at turn@30 is the IK foot.
- **New: sleeve_ribbon compress 0.10 at idol_dance@80**, in one frame. That frame is just before 腕 passes 180°, where the counter-rotation now ramps to 1; this is the cost of removing the pop at frame 81. The bow tails fold over the bag there.
- **Not a regression: petticoat pop 63 mm at idol_dance@76** now shows in the report. Only each clip's worst pop is reported, and the sleeve's 107 mm pop used to hide it.

## Codex (motion_review, gpt-6-astra / gpt-6.1-sol; `baseline_review.md`, `final_review.md`)

No extended pose or clip is rated major for sleeves, shoes or ornaments. cross_legged and high_kick list the shoes because legs and shoes go through the skirt; that is the skirt's problem.

| | astra before | astra after | sol before | sol after |
|---|---|---|---|---|
| hug_self | **major** (sleeves merge into one mass) | minor | minor | clean |
| arms_crossed | minor | minor | minor | clean |
| turn | minor (ankles / shoes overlap) | clean | clean | clean |
| spin | minor (crossed ankles / shoes) | clean | clean | minor (skirt disk) |
| hand_to_shoulder, dance_clap | clean | clean | clean | clean |
| dance_heart | minor (fingers in the fringe: hair) | minor (hands and cuffs crowd above the forehead: body, sleeves) | clean | clean |

Overall: 11 clean / 9 minor / 10 major before, and 12 clean / 10 minor / 8 major after. The majors left are skirt / leg and run@8–9.

## Pairwise old vs new (`pairwise.md`)

Each image shows the same pose from both versions, top and bottom, shuffled per pose (`pairwise_xy.json`). The crop is the upper body, front and 3/4 view. Codex judged only the sleeves, shoes and ornaments. Results over 16 poses:

| model | new | old | tie |
|---|---|---|---|
| gpt-6-astra | 6 | 3 | 7 |
| gpt-6.1-sol | 7 | 2 | 7 |

- Both models prefer the new version in hug_self, arms_crossed, hand_to_shoulder, dance_heart, dance_point and dance_sway: flatter sleeves where they meet, and less rigid inflated volume against the chest.
- Both prefer the old version in idol_dance@74 and idol_dance@81:
  - idol_dance@74: a crease under the upper-arm frill on the arm held behind the torso.
  - idol_dance@81: the raised bag now hangs where the old one had flipped away, so the hair leaves show through it.
- astra alone prefers the old version in reach_up_back.

An earlier gain c = 0.8 (instead of 0.65) for the elbow band made both models prefer the old version in arms_forward, because of a dent at the inner elbow. 0.65 makes it a tie.

The images below show the top row as X and the bottom row as Y:
- `pair_hug_self.jpg`: X = new.
- `pair_hand_to_shoulder.jpg`: Y = new.
- `pair_idol_dance_74.jpg`: Y = new. This is a pose the old version wins.

## Notes for the other units

The shared helpers changed in backward-compatible ways:
- `_skin_sample(..., reach=None)`.
- `_attach_weights(..., exclude=None)`.
- In `_create_armature`, the `follow_q` branch now dispatches the `sleeve_counter` meta, and there are new `conj_of` / `crowd` hooks.
- `_weights` has one new branch for skin-riding ornaments and passes `edges` to the neck cords.

The halter's no-skin fallback is unchanged. All of the skin paths are gated on `SKIN_FOLLOW`.

## Verification

- `tools/check.py`: OK.
- `rig_check.py` core: OK, 17 poses ≤ ×1.79.
- `rig_check.py --extended --motion` before and after.
- `motion_review.py` before and after.
- `review.py --build --baseline` on main.
- `export_pmx.py` + `pmx_reimport.py`: OK, 187 rigid bodies.
