# R9-7: limb fullness, and the bend-span regression

## What changed

1. **The bend-span "regression" was the metric, not the knees.** `tools/motion_check.bend_span` (#64) now measures the turn on the mesh's own edges along the limb (`_span_profile`) instead of differencing per-bin averages of all outer points.
2. **Weight smoothing takes fractional steps** (`rig._diffuse`), so a small radius no longer jumps with the mesh's median edge. The body's radius is 0.008 → 0.009 m, which gives the same smoothing as main.
3. **Knee and calf** (guide item 12):
   - The knee is about 4.5 mm wider at the condyles (`body.KNEE_WIDE`). This is a broad swell on the sides only, slightly more on the inner side.
   - The inner calf head peaks about 1.7 cm lower than the outer one (`body.CALF_INNER_DROP`).
   - The rounded knee is kept.
4. **No deltoid change.** Every deltoid variant tied or lost the pairwise review (details under "Pairwise A/B").

`legs_ab.jpg`: main is on the left and this PR on the right, in three rows: front legs, front knee, and inner 3/4 knee. `poses_ab.jpg` shows squat, seiza, run_l and hands_behind_head, laid out the same way.

## The bend-span regression: cause

R8-5 reported run knee 0.97 → 1.20 and reach_forward elbow 0.53 → 0.86 without touching those joints. Measured on body-only rigs (`bend_spans.md`):

- **Bisection.**
  - The jump is caused by R8-5's `body.py`, not by its rig, motion poses, wrist band or ankle pivot.
    - main with round 7's foot placement: no change.
    - main with `WRIST_BAND` off: no change.
    - main with R8-5's forearm radii reverted: no change.
    - main without the stored ankle joint: the IK angles return, but the spans don't.
  - It goes away with the body's weight smoothing off: pre-#67 and main then read the same, 0.619 for the reach_forward elbow.
- **Why smoothing mattered.**
  - The body's 8 mm smoothing radius sits on a ~9.1–9.3 mm median edge.
  - `_smooth_ml` rounded 2·(r/edge)² = 1.47 → 1 step before R8-5. R8-5's denser hands lowered the median edge by 2%, so it now rounded 1.54 → 2 steps.
  - That doubled the smoothing, but the weights change only slightly.
- **Why a small weight change read as a large one.**
  - The turn profiles of pre-#67 and main are nearly identical. One knee bin went 0.901 → 0.895 of the bend, and one elbow bin 0.076 → 0.108.
  - The old metric averaged every outer point per 5 mm bin (1–4 points each, from different columns) and differenced the bins. So the profile zigzags by up to ±0.4 of the bend at the elbow.
  - Its running maximum then jumps a whole bin when a single value crosses 0.1 or 0.9. That bin is 1.5 cm, or 0.17 knee diameters.
- **The new measure.**
  - Every mesh edge running along the limb gives its own turn about the bend axis, in the upper bone's frame and the bend plane.
  - Pre-#67 and main now agree within 0.01–0.02 in every pose. Knees read 0.97–0.99 and elbows 1.16–1.32.
  - The old measure gave knees 0.86–1.20 and elbows 0.53–1.87 on the same geometry.
- **Result: this PR vs pre-#67, same measure.**
  - Knees: 0.94–0.95 against 0.97–0.985.
  - Elbows: within ±0.015 (1.17–1.32). The shape of the elbow band is unchanged.
  - The knees' lower value is partly the wider knee: the span is measured in knee diameters.
- **Thresholds.** `THRESH['span']` (0.7 / 1.0) is unchanged. Knees stay minor. Elbows read 1.2–1.3 where the old measure gave 0.5–1.9.

## Pairwise A/B (both models, both orders)

The judges show a strong **position bias**: whichever version is on the right tends to win. In fixed-order runs every leg variant "won" or "lost" 4–0 depending only on its side.

So every pair here is shown in both orders in one session, and a side counts only when both orders pick it. The scripts are scratch (`jshots.py`, `pairmake.py`, `judge.py`).

- **Final knee and calf vs main, rest** (front, 3/4 and back legs, plus knee close-ups front / inner / outer / back; `pairwise_knee_rest.md`, three runs):
  - astra: 16 new / 4 old / 1 tie.
  - sol: 7 new / 5 old / 9 tie.
- **Final vs main, bent poses** (squat, seiza, kneel_one, walk, run_l, deep_lunge, sit_chair, arms_up, hands_behind_head, reach_forward, fist; `pairwise_poses.md`): 0 / 0 / 11 for both models. No pose got worse, and none visibly better.
- **Rejected variants** (`pairwise_rejected.md`):
  - Deltoid +1.5 / 0 / 2 px (outer / front / back) tied on every shoulder view. +2.5 / 0 / 3 px lost ("squared off", "swollen above the sleeve").
  - Any front fullness (0.6–2.4 px) cut a new shade island off the armpit shadow above the bodice. The outer term also costs front skin and hair IoU.
  - A narrower knee swell lost 0 / 7 and 0 / 5: sigma 12 px, inner / outer 1.8 / 1.3 px ("knob over a waisted shin").
  - An extra inner calf swell read as "a small inward kink" between knee and calf.
  - Fading the inner calf tail out by row 815 lost: 2 / 2 and 8 / 12 over three runs. Code review had suggested it to keep the inner Achilles hollow full depth.

## Gate (main bae3160 → this PR)

- **Look** (`look_metrics_delta.md`):
  - Silhouette IoU is unchanged in every view.
  - Front skin is 0.784 (+0.000) and back skin +0.001.
  - Shade islands are unchanged in every view and region.
- **Core rig check: `RIG CHECK OK`.** This covers the 17 core poses and the repeatability check.
  - `tools/check.py`: `CHECK OK`. Body 7,417 faces against a budget of 24,000; total 102,602.
- **Motion** (`motion_compare.md`, extended poses and clips, both runs with the new span measure):
  - Body issue counts are unchanged.
  - All parts: 388 minor / 121 major → 386 / 121.
  - Body stretch moves by −0.02…+0.03 at most (spin 1.56 → 1.59). Flips and volumes are unchanged.
- **PMX:** export and re-import OK. VMD round trip: 0.00 mm worst bone offset.

## Notes

- **The hands_behind_head "sharp crease inside the bent elbow" is the sleeve, not the body.**
  - The body's elbow is hidden under the sleeve in every pose, and its bend span is unchanged.
  - The crease comes from the sleeve's own elbow band: `rig._sleeve_weights`, `SLEEVE_ARM_KNOTS` and `SLEEVE_ELBOW_SPREAD`, which is the sleeve section. It is not touched here.
  - Both models rated the hands_behind_head elbow a tie between main and this PR.
- **Fractional smoothing touches every part's `_smooth`.** The other parts sit at 4 or more steps, where the change from rounding is under 1/8 of a step.
- **Rest-pose leg differences are close to what Codex can resolve.** astra prefers the new knee clearly; sol is about even.
