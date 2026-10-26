# Knee variants: pairwise Codex A/B against round 7

Nine knee poses (squat, walk, seiza, kneel_one, deep_lunge, run_l, jump_tuck, curtsy, sit_chair), front + 3/4 + side, cel. Each pair is shuffled (A/B), and both models are asked only which version deforms more like a real body at the knees and legs.

Counts are new / old / same for each model. None of the variants was kept (`knee_variants.jpg`).

| variant | what changed | gpt-6-astra | gpt-6.1-sol |
|---|---|---|---|
| kH (= v3o) | hinge band ±8 cm: d 4 / 3.5 / 3.5 cm, knots ±65 / ±22° (round 7: ±16 cm) | 1 / 8 / 0 | 2 / 7 / 0 |
| v3o | the same, separate build | 1 / 7 / 1 | 1 / 6 / 2 |
| v2o | hinge ±10 cm: d 4.5 / 4 / 4 cm, knots ±70 / ±24° | 0 / 6 / 3 | 1 / 6 / 2 |
| v1 | along-limb band like the reference MMD models: front −3.5…+6, back ±3 cm, plus a flat kneecap face | 0 / 9 / 0 | 2 / 7 / 0 |
| v2, v3 | v2o and kH plus the flat kneecap face | 1 / 6 / 2 · 2 / 7 / 0 | 0 / 4 / 5 · 2 / 7 / 0 |
| k5 | round 7 band, helpers turning 1 cm in front of the knee pivot | 0 / 0 / 9 | 0 / 0 / 9 |
| k7 | … 1.5 cm in front | 1 / 6 / 2 | 0 / 0 / 9 |
| **k6** | … 2 cm in front | 3 / 3 / 3 | 3 / 3 / 3 |
| k6, 2nd shuffle | | 2 / 5 / 2 | 3 / 3 / 3 |
| k9 | … 2.5 cm in front | 2 / 4 / 3 | 1 / 5 / 3 |
| k10 | … 2 / 3 cm (helper 1 / 2) | 1 / 5 / 3 | 1 / 7 / 1 |
| k11 | … 3 / 2 cm | 3 / 3 / 3 | 1 / 6 / 2 |
| kS | k6, plus back partners turning about the joint for the skin behind the knee (switching over ±0.4 of the cosine) | 0 / 5 / 4 | 1 / 1 / 7 |
| kT | the same, window −0.1…0.6 | 2 / 3 / 4 | 0 / 6 / 3 |
| kU | the same, window −0.85…−0.35 | 0 / 6 / 3 | 1 / 3 / 5 |
| kV | the same, back partners 1 cm forward, window −0.7…0 | 1 / 6 / 2 | 0 / 1 / 8 |

## What the reviewers say

- **Narrower bands lose almost every pose.** The reasons given: "pinched", "angular notch", "flattened knee tip", "ring-like creases across the front of both knees" (the flat kneecap face), "squared-off".
  - Both models consistently prefer round 7's rounder, fuller knee.
  - The joint guide's recommendation (a ±4 cm band like the reference models') therefore does not survive this judge on our mesh.
- **Moving the knee pivot back** (`body.KNEE_FWD` 3 / 10 px instead of 15) breaks the leg IK.
  - A knee behind the hip–ankle line gives the solver no forward bend direction.
  - Seiza then folds only to 88° instead of 161°, and squat to 5°.
- **k6 (helpers 2 cm forward) is about even** with round 7 over two shuffles: astra 5 / 8 / 5, sol 6 / 6 / 6.
  - Single ratings (`tools/rig_rate.py`): squat was minor / minor with k6. Round 7 rated minor / major in the first run and minor / minor in a second.
  - The cost: the hollow's skin swings round the forward point into the calf.
    - Folded faces: seiza 54 → 162, jump_tuck 44 → 108.
    - Knee volume: 0.65–0.68 → 0.60.
  - The bend span (`motion_check`) grows: squat knee 0.96 → 1.19 diameters, because the kneecap rounds more.
  - Given that cost, it was not kept.
- **Back partners (kS–kV) keep the metrics at round 7's values** but blend two pivots round the sides of the knee.
  - Reviewers called kS "knobby" and gave it **major / major** for squat in the single ratings.
