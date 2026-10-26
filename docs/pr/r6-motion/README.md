# R6-5: complex-motion test suite: baseline on main (7982380, 70,886 faces)

This unit only detects problems; it fixes none. The core 17 poses stay the `rig_check` gate, and they still pass. The extended poses and the clips are reported, not gated.

| file | what |
|---|---|
| `baseline_metrics.md` | `rig_check.py --extended --report-core --motion`: 17 core + 24 extended poses, 6 clips (381 frames, every frame), eyes. Tables per set, top problems grouped by metric / part / location, issues per part. |
| `baseline_codex_review.md` | `motion_review.py`: gpt-6-astra and gpt-6.1-sol rate every pose and clip (clean / minor / major / broken) with location and parts; last column = worst automated metric. |
| `baseline_gpt-6-astra.json`, `baseline_gpt-6.1-sol.json` | raw replies |
| `baseline_vmd.md` | `motion_vmd.py`: 6 clips, Blender rig -> PMX + VMD -> Blender |
| `baseline_p01/p02_poses.jpg` | 12 of the 24 extended poses, front + 3/4 |
| `baseline_c_run/idol_dance/sit_stand.jpg` | clip sheets: frames left to right, front over 3/4 (each clip's worst metric frames included) |

Run time on this machine, with other Blender jobs running: metrics about 11 min (about 1.5 s a frame under load, about 0.2 s alone). Renders and sheets 40 s. Codex about 6 min.

No MMD physics anywhere. In Blender the hair, skirt and sleeve chains move only as keyed or driven (drape and follow drivers). So a skirt that does not drape over a seat or a lifted thigh is partly expected. Both reviewers say so, and still rate clear leg-through-skirt as major.

## Codex verdict (worst of the two per item)
8 clean, 14 minor, 8 major, 0 broken. Major: sit_chair, kneel_one, cross_legged, deep_lunge, jump_tuck, high_kick, lie_back_elbows, sit_stand. Both models rank skirt / petticoat penetration by lifted or folded thighs first. Sleeve balloons that stay inflated and merge when the arms cross come second (arms_crossed, hug_self, dance_clap: minor). Neither model found stretching, collapsed joints, tearing or hyperextension. The 6-frame samples hide the pops below (astra: "the samples do not demonstrate an unequivocal temporal pop"), so the per-frame metrics catch what the sheets cannot.

## Top problems for round 7 (by priority)

1. **Sleeve follow flips in one frame (rig.py, 袖追従).** idol_dance@80->81: the sleeve chain 袖_1.L jumps 326 mm in one frame, against about 65 mm in the frames around it, while 腕.L moves smoothly. `袖追従.L` (the -75 % follow of 腕, a quaternion-power driver) switches branch when 腕's rotation passes the antipode. bone_pop 257 mm. It hits any motion that raises the arm overhead from the side or back. Fix: keep the follow quaternion in the hemisphere of the previous / rest frame, or limit the counter-rotation to the swing part.
2. **Skirt drape drivers kink and reverse the chains (rig.py, SKIRT_DRAPE).** The lowest skirt / petticoat segments (スカートN_2) change direction within one frame as the thigh pitch crosses the forward / backward switch (the larger of the two lifts). walk@7 (62 mm/frame² against 13-23 around it), run@35 155 mm, sit_stand@79 60 mm, turn@13 34 mm, idol_dance@66 125 mm. Petticoat strain jitter is 0.4-0.9 at the same frames. This is Blender-only (MMD simulates these chains), but it shows in any Blender render of the motion. Fix: blend the forward and backward lifts smoothly (soft max), and smooth the table in phi.
3. **Thighs through the skirt front when the hip flexes past about 60° (skirt / petticoat, rig drape).** sit_chair / sit_stand (pen 3.9 cm; bodice ribbon tails 44 % inside), kneel_one 3.9 cm, deep_lunge 3.8 cm, high_kick 3.5 cm, jump_tuck 3.1 cm, cross_legged 3.6 cm, lie_back_elbows 3.7 cm, run 3.3 cm. All four Codex major poses agree. The drape table stops at `DRAPE_PHI` and the front chains do not lift far enough at deep flexion. Seated poses also need the back of the skirt to spread over the seat. The bodice ribbon tails ride スカート0/15_0 into the lap.
4. **Leg IK snaps the knee near full extension (rig.py IK; motion design).** run@20->21: ひざ.R jumps about 25° in one frame (vertex pop 72 mm at ひざ補助2.R, jitter 0.3) as the push-off leg nears straight (hip-ankle 0.634 m of 0.641 m). MMD's CCD solver behaves differently: the Blender rig and PMX + VMD differ by up to 8 mm at the knees. Fix: a soft IK limit, or capping the stretch near full reach.
5. **Choker / halter stretch on a turned neck (accessories).** look_over_shoulder: acc_choker edge ×2.47 at 首, halter ×1.60, body neck ×1.99 (torso 35° + head 55°). Fix: the choker's 首 / 上半身2 split should follow the neck twist, not a fixed 30 % at the lower edge.
6. **Deep-flexion folding (body.py + rig.py).**
   - Knee crease: flipped faces at ひざ補助 in squat (78), seiza (172), jump_tuck (134), cross_legged (144); compress 0.10-0.15.
   - Elbow: sleeve balloon at ひじ補助 in arms_forward (220 flipped faces, compress 0.05).
   - Hip volume: cross_legged 0.48, seiza 0.64, sit_chair 0.76.
   - Shoulder band raised overhead: hands_behind_head median radius 0.61, volume 0.47; dance_sway volume 0.60.
   - Thigh × thigh crossing during the turn and spin (4.9 cm, turn@38, spin@26): the feet step across.
   - Calf × thigh contact 4-5 cm in seiza, lunge and kneel. This is normal LBS behaviour, reported as `contact`.
   This is R6-2's area (knees and shoulders).
7. **Side hair locks into the shoulders and chest with the arms up or the torso bent (hair_front).** hair_curl_R 29 % of its vertices inside the body (idol_dance@14, dance_sway, side_bend), hair_cheek_L 19 %, hair_lock_L 15 %. Raised shoulders push into the 横髪 chains, which follow 頭 only.
8. **Hair through garments (hair / sleeves / skirt).** hair × garment: 4804 new triangle crossings in hands_behind_head; hair × skirt: 3784 in jump_tuck, and in every torso twist and head turn (hair_back over the skirt waist). Expected without physics, but a large share of what MMD's rigid bodies will have to push apart.
9. **Sleeve cuffs and balloons into the chest when the arms fold across (sleeves).** sleeve_cuff 17-32 % inside (arms_crossed, hug_self, dance_point), balloon 2.5-5 cm. Codex also calls it out: the balloons do not compress when they meet.
10. **Shoe leaves and ribbons into the ankle (shoes).** shoes_leaves 28 % inside at turn@36 and spin@22 (foot yawed by IK), seiza and squat.

Eyes: the gaze limit alone comes 1.37 mm out at -10/+8 (minor, under the 1.5 mm gate). Half-closed まばたき = 0.5 gives 1.34 mm. A full blink and 笑い are clean. Knees and elbows never hyperextend. No forearm candy-wrapper: the forearm band stays at 0.90 or more with ±60° twist.

## VMD (mmd_tools)
All 6 clips round-trip exactly (≤ 0.01 mm). The Blender rig and PMX + VMD differ by up to 8 mm at the knees (IK solvers). Clips key only the input bones. Driven / append bones are never keyed; in MMD 付与 and physics move them. Physics was not simulated.
