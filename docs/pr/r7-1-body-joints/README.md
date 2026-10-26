# R7-1: body joints and temporal stability

Rig-side only (`levi/rig.py` body/IK/helper/neck/hip/weighting sections). Two test-infra bug fixes (`tools/motion_poses.py`, `tools/motion_check.py`). `export_pmx.py`, `body.py` and the motion thresholds are unchanged.

## Changes

1. **Shoulder: no more flip (idol_dance@80, 肩補助2 bone pop 431 mm).**
   - Cause: 腕's turn passes 180° on the run → overhead transition, and the old q^k shares took the shortest path, so they flipped sides.
   - Blender now drives the stages and 腕D by **swing + twist**: a swing from a reference direction (out, a little up and back; every pose stays ≥64° from its singular direction) plus a twist about the arm. The twist share fades out between 120° and 180°.
   - The clavicle 肩補助 keeps round 6's q^0.15 below 100° of turn and blends to swing + twist by 175°, so the shoulder joint, and therefore the hands, stay where the poses put them.
   - 腕D is computed relative to the blended shrug. It matches 腕 to 2e-6, and forward and reverse playback give identical results (no driver lag).
   - All drivers are simple expressions under 255 characters, chained through `sh_*` custom properties.
   - The PMX keeps the plain 付与 shares, so MMD itself still flips at 180°.
   - Arm bone pops in idol_dance: 431 → 4.7 mm.
2. **Stage knots** moved from −3/−0.5/1.5/3.5 to −3/−0.5/2/4.5 cm. **Armpit smoothing** no longer reaches above the shoulder joint (`ARMPIT_TOP`); it used to smear the arm over the trapezius.
3. **Garments sample the shrug and the stage bones directly** (bodice, halter cords) instead of seeing them folded into 肩補助/腕D. This fixed the existing bodice/halter majors in 6 poses and idol_dance (they were 5–13 % inside the chest).
4. **Neck split** (`NECK_KNOTS`): the spine weight of the skin around the neck goes 上半身2 → 首 → 頭 by height. The choker takes the split at its centreline.
   - Choker stretch: 2.47 → 1.26 (look_over_shoulder) and 2.41 → 1.10 (lie_back_elbows).
   - Body nape stretch: 1.99 → 1.5.
5. **Hip helpers 足補助** (50 % of 足, 付与 after IK). Wherever the pelvis/thigh blend runs, it goes through the helper (hat remap). The crotch zone and its smoothing are wider.
   - Hip volume: 0.48–0.75 → 0.9+.
   - Stretch: high_kick 2.07 → 1.79, deep_lunge 2.03 → 1.66, cross_legged 2.75 → 2.38.
6. **Knee hollow**: the back band is longer (4.5 cm, knots ±80/±27°) and `JOINT_HINGE_CAP` keeps the band off the ankle and hip.
   - Flips: seiza 160 → 54, jump_tuck 120 → 44, cross_legged 126 → 51.
   - Knee volume: 0.61 → 0.65–0.67.
   - A 7 cm band cut flips to 32 but swelled the squatting calf into a hook (`knee_band.jpg`), so I rejected it.
7. **Test-infra bug fixes** (both shared files; please note):
   - `motion_poses.centre()` dropped the yaw whenever an offset was also given. The turn and spin clips never turned the body while the feet walked round it, so the legs crossed (thigh × thigh 4.9 cm).
   - `motion_check`: the 肩補助2/3 and 足補助 stems now map to their segments (they used to be 'other') and stay in the shoulder and hip volume bands.
   - The baseline below was re-run on main's rig with both fixes, so before and after are comparable.

## Results (motion suite, body/rig rows; `motion_delta_body_rig.md`)

Major rows: **42 → 24**. Across all parts, 38 majors were fixed and 21 rows are newly major (`majors_all_parts.txt`). Of those 21:
- Some are only unmasked: the temporal rows list one object per clip, so once a worse object is fixed, the next one shows (sleeve and petticoat jitter, sleeve pop).
- The real new ones are:
  - petticoat tier1 4.2 % (jump_tuck) and 3.1 % (run_l): the fuller knee now meets the petticoat (R7-2).
  - side-lock hair and head flowers in the raised-arm dance poses: 4–6 %, against hands and arms (R7-3).

Core gate: OK. All 17 poses are equal to main; arms_up 1.85 is the sleeve, as on main. check.py OK. PMX export and reimport OK, with 198 append bones (the 2 new hip helpers export as 付与).

## Codex

- Ratings (`codex_ratings_before_after.md`): body is no longer named in any skirt-intersection major. cross_legged went from broken to major (skirt). arms_crossed and hug_self are now minor.
- The run clip is rated major (body, rig) by astra, minor by sol.
- Pairwise, shuffled old vs new (`pairwise_*.md`), across 30 items:
  - astra: new 8, old 6, same 16. sol: new 5, old 7, same 18.
  - Clear win: hands_behind_head.
  - Slight losses: squat, kneel_one, dance_sway, dance_heart.

## Not fixed, and why

- **run@20 knee pop (ひざ補助.R 74 mm):** this is not an IK flip. The knee bends smoothly (30→64→99°) and the thigh twist stays within ±8°. The IK target itself (足ＩＫ.R) has an 85 mm/frame² spike at run@21, from the clip's foot path. The bones repeat what the target does, and no stateless rig change (pole, limits) can remove it. I tried smoothing the clip (squared and quartic lift, keys every 2 frames), but the 1.5 Hz sprint still spiked 60 mm at other frames, so I reverted. Near-straight IK amplification gives 37 mm in idol_dance@60 and 8 mm in walk (currently masked by worse rows).
- **idol_dance@77–80 shoulder (vol 0.46, compress 0.09):** the clip's keys carry 腕 a full turn round in SU(2), so the stages cannot follow the arm's twist through 180° without a jump. They now fade instead of popping.
- **cross_legged stretch 2.38** between the buttocks. A pelvis floor at the cleft and wider smoothing both made it worse; a 0.4 hip share gave 2.25 but pushed the thighs 6.5 cm into each other.
- **hands_behind_head shoulder volume 0.56 → 0.64** (major ≤ 0.65); seiza knee volume 0.65. Gaining more traded against the core gate's arms_up stretch.
- **Pose contacts:** arms_crossed, hug_self, dance_heart, and the idol forearm/hand × thigh contacts. The limbs are posed into each other.
- **turn:** foot × foot 1.8 cm and a 6.8 mm foot pop come from the step choreography.
- **Sleeve 袖追従 flip** (idol 209 mm bone pop): the same q^k mechanism, in R7-4's sleeve code.
