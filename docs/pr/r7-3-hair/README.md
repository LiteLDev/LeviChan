# R7-3: hair in motion, with no body or clothes clipping

Baseline: main 34dc8c8. Final: this branch, 98,146 faces (hair_back +144). Budget 200,000.

## What changed
- **hair_back: real skirt clearance at rest.** The round-2 table of the skirt's back surface missed the godet fold crests by up to 1.2 cm, so at rest the lock ends already lay inside the skirt: 1,332 hair × skirt triangle pairs. Any motion then shuffled them into thousands of "new" crossings. `skirt_sx` now samples `skirt.profiles(skirt.fold_table())` (pure surface functions, no objects), and the curtain checks its narrower inner face and the rows between its samples. Rest overlap with the skirt: 1,332 → 0.
- **One-sided torso hang (Blender).** Arched back, the hair now hangs from the head (`HAIR_ARCH_HANG`); before, it swung 11 cm forward into the skirt (reach_up_back). Pitch gravity now acts on forward bends only. `髪追従` also turns back 85 % of 首's pitch (`HAIR_NECK_HANG`): a 2.5° look-up had swung the lock ends 2 cm into her back.
- **Collision probes (Blender only, `rig._hair_collision`).** Each hair segment has a ghost copy, with probes on its tail and middle. Shrinkwraps push the probes out of rigid, rounded colliders: shoulder cap, forearm, hand, chest, waist, neck, head, and radial skirt envelopes that ride 下半身 and each skirt chain root. The segment Damped-Tracks the probe. The rest pose is untouched (0.005 mm). Limits that keep a kinematic push from flipping or kinking the hair:
  - The arms push only the side locks.
  - A push is at most 5 / 8 cm, and at most 20° per stage.
  - A curtain segment shares its push with the neighbouring chains, so the sheet does not tear (torso_left stretch stays 1.29).
  - The PMX export strips all of this.
- **PMX: pitch only (review flag).** The hair segments now append the IK pitch helper `髪ピッチ`, not 上半身. Under mmd_tools: a 30° forward bend gives 29.4° pitch, a 30° twist 0.0°, a 20° side bend 0.0°. Arched back, `髪反り追従` counters 19.6 of 20°. Physics overrides all of this when it is on.
- **PMX physics.** Eight hair-only static capsules (upper arms, forearms, chest, waist, two across the skirt top) are fitted to the real surfaces, and only hair collides with them. The head has its own group. No hair body overlaps a static body at rest (export log). With physics on, MMD rests the hair chains on the shoulders, back, arms and skirt top, where before they sank to the 3–4.5 cm bone capsules.

## Results (`hair_motion_delta.md`: every hair-area cell, before → after)
Hair-area major cells: **40 → 25**.
| | main | this PR |
|---|---|---|
| hair × skirt crossings, worst extended / clip | 5,734 (jump_tuck) / 4,119 (idol_dance) | 1,066 (jump_tuck) / 659 (spin) |
| poses/clips with hair × skirt major | 16 | 3 (jump_tuck, spin, idol_dance 446) |
| side-lock pen_frac: dance_sway / hands_on_hips / hug_self / idol_dance | 14.3 / 6.5 / 11.0 / 31.8 % | 5.3 / 0.0 / 0.2 / 19.6 % |
| high_kick / spin curl | 15.6 / 19.9 % | 12.5 / 16.5 % |
| core gate (17 poses) | max 1.85 | max 1.85, identical table (`core_gate.txt`) |

Codex (`final_codex_motion_review.md`): neither model rates any pose or clip major for hair. Only minors remain: an outer lock tip kinks in look_over_shoulder, and the wrists sink into the hair in hands_behind_head. The 8 majors are the skirt / thigh ones, as on main. Pairwise, shuffled (`pairwise.md`, 28 pairs): astra 4 new / 3 old / 21 tie; sol 3 / 11 / 14. Sol prefers main's lock tips at the skirt in the back views: the new tips sit outside the skirt and look flatter ("pinched", "squared off"). On main they curl into the cloth. Both prefer main in look_over_shoulder (one outer lock kinks sideways).

Look (`look_metrics_delta.md`): IoU ±0.004, hair islands +3 back, +1 side.

## Combined with R7-2 (#60, skirt drape)
A scratch merge of the two branches, full motion suite (`hair_motion_delta_with_r7-2.md`). Hair × skirt: walk 238 (R7-2 alone 1,650, main 1,184), run 20, run_l 248, run_r 30, idol_dance 252, turn 122. Still major: jump_tuck 1,136 and spin 864. The skirt colliders ride the skirt chain roots, so they follow the new drape. Conflicts: CLAUDE.md only (both edited the skirt/hair bullets). rig.py and export_pmx.py merge cleanly.

## Left (not fixable from the hair, or traded)
- **Hair × garment, around 1,000–5,000 pairs.** These are the sleeves inside head-rigid hair (cap, cheek wisps), with hands behind the head or raised beside it, and arms swinging through the back hair (run, hands_behind_back). Kinematic pushes from limbs that sweep through the hair flipped the chains by 0.3–0.8 m in a frame, so the back hair does not meet the arms in Blender. In the PMX, the hair-only arm capsules handle this.
- **hair_cheek (頭-weighted, no chain: it hangs only 2.4 cm below the eye line)** into raised arms: reach_up_back 12.2 %, idol_dance@81 19.6 %.
- **Curls in spin / high_kick (arms horizontal, the deltoid rises 2 cm into the curl).** spin pop 93 mm. idol_dance@81's curl pop follows 肩補助2's own 431 mm bone pop (R7-1).
