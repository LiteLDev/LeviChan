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

## Gates

| | r11/base | this branch |
|---|---|---|
| check.py | OK, body 7,417 faces | OK, body 11,787 / 24,000 (total 112,338) |
| rig_check, full (repeat build included) | OK | OK; skin weight asymmetry 0.0012 |
| fist, worst stretch / compress | ×1.86 / ×0.38 | ×1.50 / ×0.14 |
| arms_up / squat / side_bend, worst stretch | ×1.78 / ×1.85 / ×1.47 | ×1.81 / ×1.85 / ×1.48 |
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
  - dance_point's inner elbow ×1.83 (minor) and the idol_dance@33 elbow span of 1.59. The span reads near the bridge and is unverified.
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
- `fix_outline_wrist.jpg`: the thumb web and the back-of-hand groove, before and after; the hand back at normal zoom; the wrist, r11/base against final.
- `hands_rest.jpg`: the back, palm and thumb side at rest, r10 vs r11 vs 风堇 (clay, cel and wire).
- `hands_detail.jpg`: knuckles, thumb root and the wrist weld (clay and wire).
- `hands_poses.jpg`: fist (first-round thumb roll), hand_to_shoulder and reach_up_back, r10 vs r11.
- `hands_context.jpg`: the hand under the sleeve cuff, cel.
