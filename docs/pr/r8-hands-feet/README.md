# R8-5: natural hands and feet (wrist and ankle joints)

Hands, wrists, feet, ankles and the lower shin were rebuilt against the reference analysis (`detail_guide.md` §A/B, `joint_guide.md` §2.3/§2.6). Every step was checked by pairwise Codex A/B against main (52e5a67), and only changes that won were kept. The knee, hip, shoulder and chest are untouched.

## Result

**Final pairwise A/B against main.** There are 9 close-ups:
- hand: rest, fist, forearm twist, wrist flexed 60°, wrist extended 50°;
- foot: rest, seiza, heel raised 30°, toes raised 20°.

Each pair was shown in both orders (A/B and B/A, to cancel the judges' position bias), in two separate shuffles: 36 judgements per model.

| | new | old | same |
|---|---|---|---|
| gpt-6-astra | **36** | 0 | 0 |
| gpt-6.1-sol | **32** | 4 | 0 |

sol's four "old" votes are both orders of the raised-toe foot (`flex`) and both orders of wrist extension in the second shuffle. Details are in `pairwise_final.md`; the images are `hands_ab.jpg` and `feet_ab.jpg` (top = main, bottom = this PR; cel row, then clay row).

**Gates:**
- `tools/check.py`: OK, 99,338 faces.
- `tools/rig_check.py` (core, with the repeatability checks): OK (`core_gate.txt`).
- PMX export and `pmx_reimport.py`: OK.
- `motion_vmd.py`: round trip OK (`vmd_report.md`).

## Hands (`body.py`: `HAND_R`, `HAND_P`, `THENAR`, `_palm_shape`, `FINGERS`, `finger()`, `THUMB`)

- **Thumb.**
  - It is rooted at the heel of the palm, inside the thumb ball: 9 px along the hand (≈22% of wrist → knuckles; round 7: 14 px / 35%) and 3.2 px toward the palm.
  - It leaves the side of the palm heel rather than the middle of the palm.
  - Its metacarpal (19 px, thick, `THUMB_TAPER`) lies mostly inside the ball, so the outline runs from the wrist into the thumb. Round 7's thumb hung from mid-palm like a separate stick.
  - The rig's 親指０ pivot now sits inside the pad.
  - The free thumb is 25 px long (round 7: 22).
- **Thenar pad.** A thumb ball (`THENAR` 3…31 px) about 5 mm proud, plus a side swell along the metacarpal.
- **Palm.**
  - About 5% wider and 12% thicker, with squarer edges (superellipse 2.3).
  - The back is domed over the metacarpals into the knuckle row, highest over the middle and ring fingers (transverse arch).
  - An earlier +12% / +20% version read as "a swollen mitten" and lost.
- **Fingers.**
  - Held together, 1–2 mm apart at the proximal segment.
  - Splay 3 / 0 / −3 / −7° (round 7: 5.5 / −0.5 / −5 / −12°). The proximal segment is about 46% of the finger.
  - Middle and ring knuckles sit about 2.5 px (4 mm) higher on the back of the hand than the index and little ones.
  - Sections are about 10% deeper than wide (round 7: 15% flatter than wide).
  - Joints have a dorsal knuckle bump and a palm-side crease (`JOINT_BUMP`, `JOINT_CREASE`), with pads between them (`FINGER_PAD`).
  - Fingertips are rounded domes (`TIP_DOME`; round 7 had a cone to a pole, which looked like a pencil point in clay).
  - Each finger is still its own loose part, so the rig fits all five chains as before.
- **No nails.** The sheet paints none, and neither does Nahida. They would add small cel islands at this scale.
- **Rejected:**
  - More rest curl (7/9/11/13°) with the outer knuckles dropped toward the palm: it lost 0/8 and 0/10 against this version (`pairwise_finger_curl.md`).
  - The extra curl one reviewer still asks for in the look review ("flat fans") therefore stays out.

## Wrist (`rig.py`: `WRIST_BAND`, `_split_wrist`; `body.py`: `ARM_R` wrist rows)

- **Weights.** The hand vs forearm share is an explicit band along the hand about the 手首 pivot: −4…+2.5 cm, 10–90% over about 4 cm.
  - Round 7 used envelopes: 5–6 cm, and only 55% hand 1.2 cm into the palm. The palm heel is now about 98% hand.
  - The band runs before the twist split, so 手捩 still takes the forearm's share near the wrist as before (compatible with the PMX 手捩 ramp).
  - It applies to the skin only (`WRIST_PARTS`); the sleeves build their own arm weights.
- **Shape.** The wrist section is a little fuller: 22.4 × 14.6 px, 1.53 : 1 (round 7: 21 × 14).
- **Band width was tested in A/B.**
  - ±1.5 cm and ±2.2 cm were each judged "a pinched notch at the flexed wrist" and lost the flex / extension pairs.
  - −4…+2.5 cm won the hand set 8/2 and 10/0 (`pairwise_wrist_band.md`, before the wrist widening).
  - Wrist flexion was the one pose round 7 had kept winning.

## Feet and ankles (`body.py`: `LEG_FRONT/LEG_SIDE` rows ≥ 820, `LEG_ROWS`, `ANKLE_ROW`, malleoli / Achilles / heel; `rig.py`: `ANKLE_BAND`, `_split_ankle`, `RIGID_FOOT`)

- **Ankle pivot.**
  - Moved from spec `ankle_z` (row 830, z 0.188, 12.8% H) to the real joint inside the shoe: row 868, z 0.129, 4.5 cm above the heel seat (`body.ankle_joint()`, stored in `levi_joints['ankle']`).
  - The heel is 8 cm, so 0.129 is the floor for this shoe. The guide's 5.5–6.2% H is for flat-shod feet.
  - A foot turn now pivots inside the shoe instead of bending the shin at its thinnest point (the hourglass pinch).
- **Lower shin.**
  - The sheet's skin stays about 25 px wide and 33 px deep down into the shoe opening (rows 800–860). Round 7 narrowed it to 16 × 22 px.
  - Narrowest visible section, at rows 820–842: 3.6 × 4.9 cm (round 7: 2.2 × 3.2 cm at row 842, 1.7 × 2.8 cm at 856).
  - Below the malleoli the leg runs on into the heel round the pivot (rows 859–873, inside the shoe).
- **Anatomy** (`_leg_shape`):
  - malleoli: the inner one 1 cm higher than the outer, about 2.5 mm proud, broad (a narrow bump read as a knob when the foot turned; a smaller one lost the rest pose: "constricted where it enters the shoe");
  - hollows either side of the Achilles tendon;
  - a heel swell behind, under the counter.
  - The heel arch and the toes are inside the shoe and were not modelled.
- **Weights.**
  - Foot vs shin along the shin axis about the pivot, with an angle-dependent band (`ANKLE_BAND`): instep side −1…+4.5 cm (the instep's skin rises in front of the joint), heel side 0…+3.5 cm (the tendon bends up to the counter's top), blended round the leg.
  - The laces take these positional weights.
  - The shoe shell is rigid on 足首 (`RIGID_FOOT`). Blended, its heel counter, which rises above the pivot, stretched ×2.16 in squat (core gate failure).
  - Starting the heel side inside the counter (+0.8 / +1.6 cm) stretched the tendon ×2.3 / ×2.8 with the toes tucked (kneel_one), so the heel side starts at the pivot.
- **Leg IK.**
  - `tools/motion_poses.foot()` now places and turns the foot about `foot_ref`, the shin axis at spec `ankle_z` (within 4 mm of the round-7 pivot), so every pose keeps its feet: seiza, kneel, lunge, run, walk, turn and spin.
  - Its turn is yaw then pitch, not the shortest arc between toe directions. With a pivot below the placement point, the shortest arc tilted the foot in the turn clip and gave a 7 mm ankle pop.
  - The core rig_pose poses move 足ＩＫ by translation only and are unaffected.
  - IK reach 0.03 / 0.02 mm; the knees still bend forward in every pose.
- **Shoes** (`shoes.py`).
  - The shell is cleared off the leg as well as the foot (`_clear_leg`, from `body.leg_section()` / `body.leg_offset()`), because the leg now runs on into the heel.
  - Clearance of shell and laces off the skin is unchanged from main: the only points under 0 px are the four buried stiletto-seat / sole points that main has too. The laces' minimum is 0.53 px (main 0.13).
  - **Cross-part imports** (CLAUDE.md "Part rules"): `shoes` now also imports `body.LEG_ROWS`, `body.leg_section()` and `body.leg_offset()`, besides `FOOT`, `LEG_FRONT`, `LEG_SIDE` and `MARGIN`. They are pure data and functions, and body keeps those names stable.

## Metrics

**Look** (`review.py --baseline` against main, `look_metrics_delta.md`):
- The skin and shoe IoU go up in every view. Skin: +0.004 front, +0.006 side, +0.007 back. Shoe: +0.006 / +0.010 / +0.010.
- Shade islands: front −2 (−89 px). The 3/4 front-left skin view has +2 islands (+148 px).
- The look review's P1 findings are the squat knee and the raised-arm armpit, both outside this unit.

**Motion** (`motion_compare.md`: main vs this PR, body / shoes / wrist / ankle columns, all core, extended and clip poses; run with the bend-span metric from #64):

- **Issues.** Body and shoe issues go from 40 major / 157 minor to 42 / 143. The shoes have no major left (main had 1).
  - Body majors by metric (main → this PR): stretch 2 → 1, compress 2 → 1, vol 5 → 3, pop 2 → 1, self 9 → 10, span 17 → 24 (see notes).
  - All parts: 113 / 393 → 112 / 392.
- **Leg and foot poses.**
  - Stretch, main → this PR: squat ×1.72 → 1.66, kneel_one 1.81 → 1.90, seiza 1.67 → 1.69.
  - Shoe pen in seiza: 1.5 cm / 4.9% → 1.4 cm / 2.8%. In kneel_one, the shoe's 1.4 cm / 2.4% is gone (the worst is now the skirt).
  - Turn clip: the ankle pen 1.1 cm → none; no ankle pop.
  - Seiza knee 156° → 144° (the IK with the new pivot sits a little less deep, with the feet in the same place).
- **Ankle band volume** (`vol ankle`) reads lower in 20 poses, because the band is now measured round a pivot inside the shoe: it holds the heel and instep, not a slice of shin. The wrist and forearm bands are unchanged.
- **Fist:** stretch ×1.68 → 1.84 on 手首 (the thicker palm heel under the curled fingers), still minor.

**Motion review** (`motion_review.md`: both Codex models, every extended pose and clip):
- Worst rating per pose or clip: 17 clean, 12 minor, 1 major. The main baseline (52e5a67, `docs/pr/r8-2-shoulder-run/baseline_motion_review.md` in #64) had 11 / 13 / 6.
- The one major is the cross-legged lap: skirt and sleeves.
- No hand, wrist, ankle or foot finding is rated major. The body findings are the trailing knee in deep_lunge and the run clip's folded knees, both minor.

## Not done / notes

- **Toe-box flex bone** (guide §B.4): not added. It is low priority in an 8 cm heel.
- **The weakest pose is raised toes** (`flex`, dorsiflexion 20°). astra calls the front of the ankle "a shelf-like fold" in some runs.
  - A wider instep band (−1.5…+5 cm, with the heel side wider too) did not win.
- **Knee and elbow bend spans** (#64's metric) moved in some poses: run knee 0.97 → 1.20, reach_forward elbow 0.53 → 0.86.
  - Reverting the forearm shape, the wrist band or the ankle pivot does not change them.
  - The cause is the changed vertex count of the body mesh. The weight smoothing coarsens the mesh by pairing neighbouring vertices in index order, so the knee and elbow weights shift slightly.
  - Not a design change; the core gate is unchanged.
- **The motion close-up tool and pairwise judge used here are scratch scripts**, not in `tools/`. The PNG sheets are rendered from the rigged `.blend` with each model's own `motion_poses`.
- **wrist_flex / wrist_ext / tiptoe / flex** are local test poses: the wrist bent about the fingers' curl axis, and the foot pitched ±.
