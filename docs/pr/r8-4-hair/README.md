# R8-4: hair in a forward bend, side locks clear of the shoulders, no collision pops

Baseline: main 52e5a67, 99,010 faces. Final: the same 99,010 faces, because only the rig changed (`levi/rig.py`, hair sections). `hair_front.py`, `hair_back.py` and `export_pmx.py` are unchanged.

## What changed
- **The limbs push the hair as capsules, not hulls.** Each capsule (`rig._Capsule`) covers the shoulder cap, upper arm, forearm or hand.
  - For each probe, a projector bone takes the probe's unpushed point (from an anchor bone) and clamps it onto the limb bone's axis segment. A Limit Distance then keeps the probe a fixed radius off that point.
  - The push is continuous everywhere except on the axis itself. The push fades out as the point nears the axis (`HAIR_CAPSULE_FADE`), so a limb sweeping right through the hair passes through it and does not fling it across.
  - Before, a probe that was inside a hull jumped between faces under the nearest-surface push (spin: 17 → 9 mm in one frame). A row of spheres was tried first and dropped: pushed one after another, they walked a probe along the arm by up to 100 mm.
- **Reach filter on the trunk, skirt and head hulls.** A probe no longer tests one of these hulls if it is more than 12 cm away at rest. The chest Shrinkwrap was misjudging a lock end at the hips as inside and threw it 29 cm, which caused the 111 / 123 mm back-hair pops in turn and idol_dance.
- **Curls.** A probe that lies inside the shoulder capsule at rest now keeps its rest distance from the capsule's axis. Before, such a probe was never tested, so a raised shoulder went straight into the curl. The curl's last segment follows the segment above it (`HAIR_CAP_TIP_FREE`). When pushed on its own, it switched in and out of the cap: a 108 mm pop.
- **Cheek wisps get a two-bone chain.** It starts at the cheekbone (`SIDE_HAIR_TOP`), and the wisps are weighted along it with 頭 at the roots (`_side_chain_weights`). The upper arm pushes only these wisps, and gently: 6° per stage, with a soft fade (`HAIR_COLLIDE_UPPERARM`, `*_BY`).
- **Forward bend.**
  - The pitch counter now turns about world X, spread over the bone's three local axes. In round 7 it turned about the single local axis nearest X, so on a sideways outer lock it only rolled the lock.
  - Segments whose rest middle is below the waist turn back the whole forward pitch (`HAIR_PITCH_HANG`).
  - Blender only: those segments also take the pelvis' pitch (`HAIR_PELVIS_FOLLOW`), so the hair lying on the hips stays on the skirt when the hips tip.
- **PMX.** The PMX keeps round 7's pitch-only 付与 profile, because it has no pelvis follow to go with the full hang. Collision is still stripped from the export (592 Blender-only bones are removed). The new cheek chain becomes 4 more hair bodies, 123 in total. No hair body overlaps a static body at rest.

## Results (`baseline_motion_report.md` → `final_motion_report.md`)
| | main | this PR |
|---|---|---|
| worst hair pop, idol_dance | 123 mm (後髪束2_4) | 52 mm (curl) |
| worst hair pop, turn | 111 mm (後髪束2_4) | none; the clip's worst is 7 mm at 足首 |
| worst hair pop, spin | 82 mm (curl) | 20 mm (後髪束7_4, unchanged) |
| cheek wisps inside the arm, reach_up_back | 10.3 % | < 3 % (minor) |
| curl inside the body: spin / high_kick / dance_sway | 19.3 / 15.9 / 7.2 % | 20.9 / 15.6 / 5.3 % |
| core gate (17 poses) | ok | ok (`core_gate.txt`, forward_bend stretch 1.23) |

Look (`look_metrics_delta.md`): every IoU, dE and island count is unchanged (+0). The rest pose is untouched.

## Codex
- **Motion review** (`final_review.md`): no pose or clip is rated major for hair. The only hair item is a minor in look_over_shoulder (the outer tips kink), the same as on main.
- **Core poses** (`look_review_summary.md` vs `look_baseline_summary.md`, both run with `--focus hair`):
  - forward_bend: main is clean / major, this PR is major / minor.
  - arms_up: main is clean / minor, this PR is major / major.
  - The renders are pixel-for-pixel the same in arms_up's hair; single ratings are noisy.
- **Pairwise, shuffled** (`pairwise_final.md`, 22 pairs): astra rated new 8 / old 12 / tie 2, sol new 2 / old 13 / tie 7.
  - Both models still prefer main's forward_bend and some of main's side locks. Main lets a curl hang into the sleeve; the final version lifts it a little.
  - A first round with stronger pushes (`pairwise_round1_rejected.md`: 2/17 and 2/15) lifted the curls out along a raised arm, which both models disliked. This PR backs off to gentler capsules (radius at the 60th percentile, 20° per stage) and round 7's outer-lock exponent.

## Left
- **The forward bend is not visibly better to Codex.** In the side view the outer lock now hangs, but the back curtain still lies on the back and its curled ends rest on the skirt top (`forward_bend_side_main_vs_final.jpg`). Every variant of how much the lower segments hang read the same or worse: full hang from the waist pushed the ends out horizontally over the skirt.
- **Curls over a raised shoulder (spin, high_kick) still sink 15–20 % into the deltoid.** Lifting them clear made them read as stiff (round 1). A fix needs the curl rerouted in `hair_front` so it falls in front of the shoulder, which is a look change.
- idol_dance still has a 52 mm curl pop at frame 15, from the arm swinging past the shoulder.
