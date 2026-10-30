# r11 / body-hands: 风堇's hands on Levi's arms

Levi's procedural palms and fingers are replaced by 风堇's hand. The old hand was a pillow-shaped palm with tube fingers plugged into it, 6 loose parts per hand. Hers is one piece with a real palm, a thenar mound, finger webs, knuckles, tapered jointed fingers and nails. It is re-posed onto Levi's hand frame and welded to the procedural forearm. The rig's finger contract is adapted so that her fingers keep their own chains and her own weights.

## What changed

- **Asset.** `tools/prep_hyacine_hands.py` writes `assets/hyacine/hands.npz` (23 KB).
  - It contains her left 肌 hand, with the 指甲 nails welded on by position so the fingertips close, and the UV-seam duplicates welded.
  - The triangles are joined into quads (join_triangles at 40°: 636 quads and 173 tris).
  - It also stores her weights by bone, a finger id per vertex and the bone heads.
  - The tool checks that the right hand is the exact mirror of the left. Re-running it gives the same md5.
- **Build.** The new code is in `levi/parts/_body_hand.py`; the change to `body.py` is about 25 lines.
  - The hand is placed rigidly from her wrist frame onto `body.hand_frame()` at `body.WRIST`, so the palm faces the thigh and the thumb points forward and down. It is scaled to Levi's hand length (126 mm, ×0.93).
  - Her 2.4 cm forearm stub is bent onto Levi's forearm with linear-blend skinning by her own forearm weights. Levi's wrist is extended ~12° and hers ~4°.
  - The stub is tapered to the arm's last ring, and the hand gets one Catmull-Clark level.
  - The procedural arm now stops 1.2 cm before `rig.WRIST_BAND`. A bridge of 3 rings joins it to the hand:
    - per-vertex Hermite paths, tangent-continuous at both seams;
    - a rotation-minimising frame, so the bridge does not twist;
    - one 24→22 zipper row (22 quads and 2 tris).
  - The body is still one closed manifold: 5 loose parts instead of 15, with no open or non-manifold edges. `levi_socket_s` is positive on the hands. Each hand has 3,141 vertices and about 3,150 faces.
  - On the palm side the outline thins in her cage's sharpest concave creases (vertex group `levi_outline`, down to 0.3 of its width), so the thumb's line tapers into the web.
  - `LEVI_HYACINE_HANDS=0` builds the round-10 hands.
- **Rig (shared functions, as the task allowed).**
  - `fit_fingers` uses `obj['levi_fingers']`, her bones after placement. Without them it falls back to loose parts split by the `levi_finger` id attribute. The log still reads `5 chains fitted to the body's fingers`.
  - `_island_rules` applies its finger rule per finger region.
  - `_hand_hint` blends her weights in after the smoothing. Her staged twist bones 手捩k map onto our 手捩 / ひじ split by k/4, and her weights are smoothed 5 mm on the hand.
  - Finger bones are rolled to the palm normal of the knuckle line. Round 10's generic palm vector was ~42° off, so the fist curled the fingers sideways.
  - The thumb's three bones are rolled per bone (`THUMB_ROLL`, −30° / 75° / 75° about the thumb from that palm normal): the metacarpal swings out in front of the palm and the phalanges close across the fingers.
  - The body's smoothing uses fixed reference edges, one per level of the multilevel smoothing (`SMOOTH_REF`, measured on r11/base's body), and leaves the hands out of its graph (`_smooth_zones`). The hands are smoothed on their own.
- **Tools.** `rig_check` fails when the skin's left and right weights differ by more than 0.02 (`check_symmetry`). `motion_check` gives each finger its own segment (`FINGER_SEGMENT`).
- **CLAUDE.md** describes the finger contract, the hand asset, the hint weights, the thumb roll, the smoothing references and the finger segments.

## Review fixes (second round)

The independent review found one p1, one p2 and three p3 issues.

- **p1: hip and crotch weights.**
  - *Problem.* The dense hands had changed the coarse graph that the crotch smoothing pass runs on. The hips lost their left/right symmetry (up to 0.142) and moved up to 0.16 from r11/base.
  - *Fix.* Per-level reference edges plus the hands split off the smoothing graph.
  - *Result.* Position-matched against r11/base:
    - crotch and legs (|x| < 17 cm, z < 85 cm): max |Δw| 7e-8, so bit-for-bit to float32;
    - torso and shoulders: at most 2.1e-3;
    - waist skin beside the elbow: at most 0.017. Its forearm envelope weights follow the forearm bones, which moved with the wrist pivot.
    - Mirror asymmetry is 0.0012, the same as r11/base.

  `fix_hip_weights.jpg` paints asymmetry in red, from r11/base through the previous head to this one.
- **p2: the thumb passed through the curled index in the fist.**
  - *Cause.* One roll for all three thumb bones put the metacarpal on the palm.
  - *Measurement.* A scan of the rolls showed that the index fingertip goes 5–7 mm into the palm or the thumb's base at every single roll, so the roll alone could not fix it. Rolling the metacarpal separately could.
  - *Result.*
    - No index vertex lies inside the thumb any more (before: 280 vertices, up to 6.8 mm deep). The fingertip touches the palm 2.8 mm deep (before 6.9 mm).
    - The thumb rests on the index and middle fingers' middle phalanges.
    - Fist worst stretch is ×1.50 (base ×1.86).
  - *Side effect.* 18 flipped faces (before 4). They are in the palm-side crease at the index root, inside the closed fist; the roll changes the motion-refit sample poses there. See `fix_fist.jpg`.
- **p3: thumb-web arrowhead.**
  - *Fix.* The outline thins on the palm side's creases.
  - *Result.* The thumb's line now tapers into the web (`fix_outline_wrist.jpg`, top left).
- **p3: scratch on the back of the hand.**
  - *Where.* A pick ray put it in the groove between the middle and ring metacarpals, not the index–middle groove the review named.
  - *Tried.* Thinning the hull there lengthened the line. Relaxing or filling the groove in the cage did not remove it.
  - *Status.* It stays as a 1 px, 2 mm line. It is visible only in the 7 cm close-up; at the hand-back zoom it disappears (`fix_outline_wrist.jpg`).
- **p3: wrist notch.**
  - *Cause.* It is Levi's 12° wrist extension meeting her hypothenar flare, not a regression.
  - *Measured from plane sections.* The pinky-side silhouette turns at most 19.3° per 4 mm. r11/base's procedural palm turns 18.6°, and her own untapered wrist 20.4°.
  - *Tried.* A longer taper (TAPER_END 25 or 40 mm) changed it by less than 1°.
  - `fix_outline_wrist.jpg`, bottom right, puts r11/base beside this branch.

## Integration fixes (round-11 merge)

The round-11 integration found arm-skin regressions that appear only with this branch merged (bisect v3 → r11/integrate). The diagnosis scripts are in `work/integ_scratch/hands/` on the cluster. `diag.py` and `ana.py` map the worst posed edges to their vertices and weights; `wtrace.py` dumps the body's weights and prune guide before `_prune`.

**Inner elbow (dance_point, reach_up_back, dance_sway, dance_heart, hands_behind_head, hands_on_hips, idol_dance span)**
- *Where.* The worst edges were 5–12 mm edges 2.8–3.3 cm above the elbow on the inner side. One end kept ~2% torso weight (上半身 0.017) and the other none. In a raised-arm pose the torso and the arm are 25 cm apart, so 0.017 of that moves one end 4 mm: ×1.83–1.88 on a 5 mm edge. In round 10 both ends kept 上半身.
- *Cause.*
  - `_prune` folds both ひじ (weight 0) and 上半身 (weight 0.0105) away there: their prune guides tie (0.01031 / 0.01028).
  - It then keeps the larger of their tiny remnants. In round 10 both remnants were exactly 0, and column order kept 上半身.
  - `_hand_hint` smoothed her hint weights over the whole skin. Their tail reached the elbow, 13 cm up the arm, as 1e-35 of ひじ / 手捩. That remnant won, so ひじ took the 4th slot.
  - Where 上半身 is kept, `_motion_refit` gives it the vertex's whole torso share. Where ひじ is kept, nothing carries the share.
  - The forearm bones' move with the wrist pivot (7.7 mm) changed these weights by only about 1e-4. That was not the cause.
- *Fix.* Hint weights below `rig.HINT_EPS` (1e-9) are cut after the smoothing. The inner elbow's kept bones and weights are round 10's again.
- *Result.* On the full merge, every arm stretch, compress and elbow span row is back at round 10, within +0.03 (table below).
  - Arm-only metrics, from `armdiag.py`: body edges within 16 cm of either elbow, off the hand, over all 41 core and extended poses and every frame of all 6 clips.
  - Per pose and per clip, the maximum is at most +0.024 over round 10 (arms_up ×1.806 against ×1.782). The clip maxima are idol_dance ×1.787 (round 10 ×1.768) and spin ×1.652 (×1.637).
  - Single idol_dance frames are up to +0.057 over the same round-10 frame (frame 51, ×1.728). That is at round 10's own torso-share switch 8 cm up the upper arm, and it stays below the clip's round-10 maximum.
  - `integ_elbow.jpg` shows the 6 cm close-ups, clay and wire, round 10 / before / after. Before, one column of the wireframe kinks sideways and the clay shows a dent. After, the arm matches round 10.

**Fist: palm-side crease**
- *Problem.* The palm-side crease at the index, middle and ring roots folded into the fingers: 9 faces per hand turned more than 120°, with compress ×0.14.
- *Fix.* `rig._palm_crease` relaxes the 手首 / finger-root split on the palm side only, by `PALM_RELAX` 35 umbrella steps.
  - It applies where that bone pair holds at least half of the weight, fading in up to 90%.
  - It ramps across `PALM_SIDE` (6 mm) about the palm's mid-plane, so the knuckles on the back keep her blend.
  - Sharpening the split instead flipped 54 faces.
- *Result.*
  - Flips 18 → 0; compress ×0.14 → ×0.22; stretch ×1.50 → ×1.55 (round 10 ×1.86).
  - The thumb is still clear of the curled index. The index tip sits 2.8 mm into the palm, as before, and the ring tip no longer touches it.
  - dance_point's curled right hand: compress ×0.29 → ×0.43.
  - `integ_fist.jpg` shows the fist from the palm, low and three-quarter sides plus three 3 cm close-ups of the finger roots, cel and clay. Before has the flipped faces in red, which show between the fingers. After is clean. Compress stays below round 10's ×0.38 because the curled finger root's skin really does fold. Round 10's fingers were separate tubes with no crease.

**Hand self-contacts (explained, not changed)**
- Measured with the same finger-level segments on round 10's procedural hands (bisect v3 rig) and on this branch (`selfdiag.py`), the deepest crossings are:

| pose | round-10 hands | 风堇 hands |
|---|---|---|
| hands_behind_head | ring × ring 5.0 cm, hand × hand 4.5 | index × index 4.6, ring × ring 4.5 |
| dance_heart | forearm × hand 5.0, hand × thumb 4.7 | hand × thumb 4.0, forearm × hand 3.5 |
| dance_clap | hand × thumb 4.9 | hand × thumb 3.5, forearm × forearm 2.5 |
| idol_dance@51 | hand × ring 5.0 | hand × index 4.9 |
| hug_self | thumb × upper arm 3.7 | forearm × upper arm 3.6, thumb × upper arm 3.3 |

- The poses bring both wrists to one point, so the palms (or a hand and the other arm) pass through each other as rigid shapes, as deep with round 10's hands. That is placement, not deformation.
- The old report's whole-hand segment hid these crossings: it measured only the nearest face, which often belonged to another finger.
- dance_clap and idol_dance@35 now list forearm × forearm (2.5 / 3.1 cm). The pressed wrists' skin is her 手捩 stub, labelled forearm; in round 10 the same place was hand skin.
- `integ_hand_contacts.jpg` shows the back and top close-ups, clay, round 10 against this branch.

| row (full merge, `integ_motion_report.md`) | round 10 | r11/integrate ada6865, unfixed (integ8 at 88efe3d reads the same) | ada6865 + this head |
|---|---|---|---|
| dance_point stretch | 1.631 (足.L) | 1.834 (ひじ補助.R) | 1.631 (足.L); arm 1.601 |
| reach_up_back stretch | 1.723 | 1.881 (ひじ補助.L) | 1.722 (上半身2); arm 1.685 (r10 1.673) |
| dance_sway stretch | 1.716 | 1.820 (腕捩.L) | 1.718 (上半身2); arm 1.677 (r10 1.666) |
| dance_heart stretch | 1.676 | 1.794 (腕捩.L) | 1.685 |
| hands_behind_head stretch | 1.702 | 1.763 (腕捩.L) | 1.698 |
| hands_on_hips compress | 0.564 | 0.376 (ひじ補助.L) | 0.565 |
| idol_dance elbow span | 1.323 | 1.584 (@33) | 1.310 |
| reach_forward / arms_forward span | 1.304 / 1.282 | 1.356 / 1.314 | 1.293 / 1.275 |
| dance_point compress | 0.369 | 0.287 (中指１.R) | 0.369 (足.L); hand 0.433 |
| fist flips / compress / stretch | 2 / 0.382 / 1.865 | 18 / 0.142 / 1.501 | 0 / 0.219 / 1.549 |

- Body issues: 86 major / 120 minor (unfixed, same tree) → 84 / 118. Round 10: 66 / 88.
  - 21 / 36 of them are hand / finger self and contact rows, where round 10 had 6 / 7 (see above).
  - The rest are 63 / 82; round 10 had 60 / 81. The differences:
    - forearm × forearm in dance_clap and idol_dance (see above);
    - arms_up ×1.806 against ×1.780;
    - the fist's ×0.22 compress;
    - walk's ひざ.R pop at frame 31. It is in r11/integrate already and is not this branch's.
- Other parts, against the unfixed r11/integrate on the same tree: every part's issue count is unchanged. 17 penetration rows move, because they are measured against the changed hands. Each moves by at most 1.2 mm or 0.06 %; sleeve_cuff's worst in dance_heart moves from 4.9 mm on the right to 4.4 mm on the left.
- The full merge's `rig_check` (structure, weights, symmetry 0.0012) passes.

## Gates

| | r11/base | this branch |
|---|---|---|
| check.py | OK, body 7,417 faces | OK, body 11,787 / 24,000 (total 112,338) |
| rig_check, full (repeat build included) | OK | OK; skin weight asymmetry 0.0012 |
| fist, worst stretch / compress / flips | ×1.86 / ×0.38 / 2 | ×1.55 / ×0.22 / 0 (previous head ×1.50 / ×0.14 / 18) |
| arms_up / squat / side_bend, worst stretch | ×1.78 / ×1.85 / ×1.47 | ×1.80 / ×1.85 / ×1.48 |
| side_bend / walk penetration | 1.76 / 1.71 cm | 1.77 / 1.71 cm |
| IoU front / side / back (first round; the rest geometry is unchanged since) | 0.9090 / 0.8331 / 0.9132 | 0.9076 / 0.8331 / 0.9117 |
| hand clearance under the cuff (p5 / p50) | 11.0 / 22.8 mm | 7.6 / 14.1 mm, no pokes |

Motion report (`rig_check.py -- --quick --no-core --extended --report-core --motion`), r11/base → this branch. `final_motion_report.md` holds the whole report, `baseline_motion_report.md` r11/base's.

- **Legs and hips are back at r11/base.** The diff against r11/base has no thigh, pelvis or crotch row. The previous head's new rows are gone:
  - cross_legged: flips 48 and pelvis × thigh contact 4.0 cm;
  - run_r: pelvis × thigh.R 4.9 cm.
- **fist:**
  - stretch ×1.86 → ×1.50;
  - compress ×0.38 → ×0.14 (minor, the palm-side crease at the middle-finger root);
  - flips 2 → 18 (minor, the palm-side crease at the index root, inside the closed fist; previous head 4).
- **Body issue count:** 66 major / 88 minor → 85 / 120.
  - Outside the new finger-level rows: 68 / 91, about where the previous head was (69 / 95).
  - Finger-level rows: 17 / 29. They come from `FINGER_SEGMENT`. The whole-hand segment missed them, because the nearest face of the other hand belonged to another finger.
  - Most of the finger rows are hands passing through each other in poses and clips that put the hands together: idol_dance@37–52, dance_clap thumb × thumb 2.8 cm, hands_behind_head's interlaced middle fingers 4.6 cm. Her hand is larger than round 10's (palm 58 mm against 53 mm). These are pose-authoring cases, not deformation.
- **Unchanged since the first round:**
  - dance_point's inner elbow ×1.83 and the idol_dance@33 elbow span of 1.59 were fixed in the integration round (above). They were the hint-weight tail at the inner elbow, not the bridge.
  - hair_front pen_frac in dance_heart, 3.8% (her larger hands over the head).
- **Other parts:** hair_front 16 / 25 → 18 / 27 and sleeves 9 / 70 → 9 / 72, as in the first round. Every other part is unchanged.

## Notes

- **Wrist pivot.** The rig's wrist is now her 手首 at `body.WRIST`, and `levi_joints['wrist']` and `['fingertip']` are stored. That is 7.7 mm further along the forearm than round 10's fitted wrist.
- **Smoothing references.** `SMOOTH_REF['body']` holds r11/base's per-level reference edges. A body that becomes denser elsewhere (the legs or torso branches) and tunes a radius against its own median should re-measure them with `rig.smooth_levels`, or remove them to fall back to the medians.
- **Not run.**
  - `export_pmx.py`, `pmx_reimport.py` and `motion_vmd.py`: mmd_tools is not installed on the cluster.
  - The Codex review.
  - compare.py: the hand's rest geometry is the same as in the first round.

## Sheets

- `fix_hip_weights.jpg`: weight asymmetry (red ≥ 0.05) at the hips, r11/base → previous head → final.
- `fix_fist.jpg`: the fist, previous thumb roll against the final one (cel and clay).
- `integ_elbow.jpg`: the inner elbow in dance_point, reach_up_back and dance_sway, 6 cm close-ups, clay and wire, round 10 / r11/integrate / fixed.
- `integ_fist.jpg`: the fist before / after the palm-crease relax, cel and clay, flipped faces in red; fist views and 3 cm close-ups of the finger roots.
- `integ_hand_contacts.jpg`: the poses that bring the hands together, round 10's hands against 风堇's, clay.
- `integ_motion_report.md`: the motion report of r11/integrate with this branch's head merged.
- `fix_outline_wrist.jpg`: the thumb web and the back-of-hand groove, before and after; the hand back at normal zoom; the wrist, r11/base against final.
- `hands_rest.jpg`: the back, palm and thumb side at rest, r10 vs r11 vs 风堇 (clay, cel and wire).
- `hands_detail.jpg`: knuckles, thumb root and the wrist weld (clay and wire).
- `hands_poses.jpg`: fist (first-round thumb roll), hand_to_shoulder and reach_up_back, r10 vs r11.
- `hands_context.jpg`: the hand under the sleeve cuff, cel.
