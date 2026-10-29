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
  - `LEVI_HYACINE_HANDS=0` builds the round-10 hands.
- **Rig (shared functions, as the task allowed).**
  - `fit_fingers` uses `obj['levi_fingers']`, her bones after placement. Without them it falls back to loose parts split by the `levi_finger` id attribute. The log still reads `5 chains fitted to the body's fingers`.
  - `_island_rules` applies its finger rule per finger region.
  - `_hand_hint` blends her weights in after the smoothing. Her staged twist bones 手捩k map onto our 手捩 / ひじ split by k/4, and her weights are smoothed 5 mm on the hand.
  - Finger bones are rolled to the palm normal of the knuckle line, and the thumb toward the index knuckle. Round 10's generic palm vector was ~42° off, so the fist curled the fingers sideways.
  - The body's smoothing counts its radii against a fixed 9.35 mm reference edge (`SMOOTH_REF`). Her dense hands had halved the body's median edge, which re-tuned the whole skin (arms_up armpit ×1.78 → ×2.39).
- **CLAUDE.md** describes the finger contract, the hand asset, the hint weights and `SMOOTH_REF`.

## Gates

| | r11/base | this branch |
|---|---|---|
| check.py | OK, body 7,417 faces | OK, body 11,787 / 24,000 (total 112,338) |
| rig_check | OK | OK (the repeat-build check included) |
| fist, worst edge stretch / compress | ×1.86 / ×0.38 (body) | ×1.53 / ×0.12 (body) |
| arms_up / squat / side_bend, worst stretch | ×1.78 / ×1.85 / ×1.47 | ×1.81 / ×1.85 / ×1.48 |
| IoU front / side / back | 0.9090 / 0.8331 / 0.9132 | 0.9076 / 0.8331 / 0.9117 |
| skin region IoU front / side / back | 0.744 / 0.612 / 0.631 | 0.736 / 0.608 / 0.623 |
| hand clearance under the cuff (p5 / p50) | 11.0 / 22.8 mm | 7.6 / 14.1 mm, no pokes |
| shape_fit body, target→ours p50 / p90 | 6.9 / 23.6 mm | 7.0 / 23.9 mm |

Hand-related rows of the motion report (`rig_check.py -- --quick --no-core --extended --report-core --motion`), r11/base → this branch:

- **fist**: stretch ×1.86 → ×1.53; compress ×0.38 → ×0.12 (minor, the palm-side crease at the middle-finger root); flipped faces 2 → 4.
- **Hand self-contact** (hand × hand): dance_clap 1.2 → 1.5 cm, dance_heart 1.6 → 1.7 cm, hands_behind_head 1.2 → 1.3 cm. Her hand is a little wider (palm ~58 mm against 53 mm).
- **Forearm × forearm** in dance_clap: 1.2 → 2.5 cm (minor → major). The "forearm" segment now reaches her wrist (her stub and the bridge are 手捩-dominant), and the forearm is 7.7 mm longer (the wrist pivot below).
- **hair_front and accessories inside the body near 頭**, with the hands over the head: dance_heart 2.5 → 3.8% (minor → major), idol_dance@45 3.8 → 6.1%. The hair is inside her larger hands, not the head. Fitting the hand capsule to thinned points did not change it.
- **Elbow**: dance_point's inner elbow ×1.63 → ×1.83 (minor). A 1.5% 上半身 weight is pruned on one side of an edge, because the twist and helper shares moved with the longer forearm. idol_dance elbow span jumps to 1.46 / 1.59 on frames 31 and 33 only (1.31 on the frames between), which looks like noise in the column tracking near the bridge.
- **Totals**: body issues 66 major / 88 minor → 69 / 95; hair_front 16 / 25 → 18 / 27; sleeves 9 / 70 → 9 / 72; every other part is unchanged.

## Notes

- The rig's wrist is now her 手首 at `body.WRIST`: `levi_joints['wrist']` and `['fingertip']` are stored. That is 7.7 mm further along the forearm than round 10's fitted wrist, which kept the landmark forearm length and sat inside the forearm before the procedural palm.
- `SMOOTH_REF` changes how the body's smoothing counts its radii, and other body work (legs, torso) inherits it. In metres the smoothing is now independent of mesh density, and the result equals round 10's on round 10's density.
- Not run: `export_pmx.py`, `pmx_reimport.py`, `motion_vmd.py` (mmd_tools is not installed on the cluster), and the Codex review.

## Sheets

- `hands_rest.jpg`: the back, palm and thumb side at rest, r10 vs r11 vs 风堇 (clay, cel and wire).
- `hands_detail.jpg`: knuckles, thumb root and the wrist weld (clay and wire).
- `hands_poses.jpg`: fist, hand_to_shoulder and reach_up_back, r10 vs r11.
- `hands_context.jpg`: the hand under the sleeve cuff, cel.
