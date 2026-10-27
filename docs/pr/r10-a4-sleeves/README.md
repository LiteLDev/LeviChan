# R10-A4: sleeves follow the shape master

Changed file: `levi/parts/sleeves.py` (rig.py untouched). Face count unchanged: 8,664 (budget 18,000). Topology, ring and vertex counts, folds, attributes and object names are all unchanged.

## What changed

**1. Balloon girth from the target (`_target_q`, used by `_ring` / `_balloon_rings`)**

Per ring (the 40 `_ring_params` stations) and per ring vertex (48), we cast a ray from 2 procedural radii out toward the station centre, along the vertex's own direction in the ring plane. The outermost `sleeves` surface it hits gives a factor `q` = target radius / procedural radius. The factor multiplies the procedural ellipse under the procedural folds.

- **Missing samples.** Rays occluded by the hair are dropped: the target's sleeve is fused into the hair there. Where the skirt, bodice or body lies outside the bag (the inner side), we look through that cloth from 1.4 radii out, but those samples may only take cloth in (`TARGET_NEAR_MAX`). Samples beyond the clamp + `TARGET_FLAP` are dropped, not clipped: they are the target's pointed hem wing that curls up past the wrist.
- **Smoothing.** Validity-weighted (`_weighted_smooth`): missing samples count as procedural, renormalised by the smoothed validity. 12 passes round the ring and 3 along the sleeve. The result is clamped to (0.75, 1.30).
- **Inner side.** Taken in no further than `TARGET_INNER_MIN` (0.97). A bag taken in closer on the inside of the elbow compressed past the limits (hands_behind_head 0.113 and idol_dance 0.110 against the 0.12 major threshold).
- **Fades.** The factor fades in below the band (`TARGET_BAND`, s 0.03–0.16), so the drawstring pleats, the bow and the tails' knot sit as before. It hands back to the procedural hem toward the wrist (`TARGET_HEM`, s 0.75–1): fully where the target is narrower, so the cuff root stays behind the facing, and 85% where it is wider. The lip and facing follow the hem ring.
- **Net shape.** The bell is fuller to the front and outside in its lower half (up to +30%) and slimmer behind and above the elbow (down to −25%), as the target hangs.

**2. Heading frill (`_ruffle_rings`, `_frill_q`)**

- A girth factor per ring angle, sampled the same way over the opening and the rim. It is clamped (0.82, 1.08) and applies from 4–14 px above the drawstring. In practice it is 0.93–1.0: the rim comes in slightly.
- It is a radius factor inside `_frill_ring` (`girth`), so the lobes' lift keeps its height. It never takes a ring inside the drawstring radius.

**3. Cuff kept procedural**

- The target's cuff is a scrunchie mixed up with the hem wing. Sampled like the frill, it only widened our flare by up to 6%.
- That widening pushed the cuff 2–3 mm further into the body in the existing cuff majors: dance_point pen 0.026 → 0.028, hug_self 0.028 → 0.031. With it off, both match main exactly.

**Kept procedural:** the station spline (centre line), ring and vertex counts, every fold (valleys, wrist pleats, drawstring pleats, swell), the soft shading normals, the hem lip and facing, the bow, the tails, the cuff and the frill lobes. The bow and tails are still laid on the folds' crest envelope, which now has the new girth.

## Contracts
- `sleeve_balloon` is still the sleeve object with the most vertices (same topology).
- `levi_sleeve_s`: the factors change the girth round the unchanged station spline, so the centre line and the balloon's per-ring values are the same as on main.
  - The balloon writes its attribute fresh at every build.
  - The other pieces are projected onto that same centre line, so no value is stale.
- `levi_sleeve_tails` on the ribbon: unchanged.
- Gather/slide keys are rebuilt at rig time. PMX reimport finds all 4 morphs:
  - 左袖寄せ 1,866 vertices move (main 2,026), 左袖滑り 1,426 (main 1,595).
  - Fewer vertices move because cloth taken in near the arm lies inside the gather floor `r0` and stays put.
  - The poses below show the gather working.

## Results

### Shape-master fit (`tools/shape_fit.py`, target→ours, mm)
| | p50 | p90 | p99 | covered |
|---|---|---|---|---|
| main, `--parts sleeves` | 11.6 | 27.1 | 54.1 | 0.236 |
| this PR, `--parts sleeves` | 9.4 | **23.7** | 48.6 | 0.307 |
| main → this PR, in review.py (all parts, other RNG draw) | 11.7 → 9.5 | 27.4 → 24.2 | | 0.240 → 0.309 |

ours→target p90 went from 20.0 to 17.9 mm.

The rest of the p90 comes from target surfaces our bag cannot or should not follow:
- the hem wing hook past the wrist;
- the target's inner sleeve lining, a second shell 15–25 mm inside;
- stray sleeve labels on the skirt.

Following the hook (clamp 1.45) gave p90 22.8. It boxed the wrist end, and Codex rejected it.

### Gates
- `tools/check.py`: CHECK OK.
- `tools/rig_check.py`: RIG CHECK OK, all 17 core poses (`final_core_gate.txt` vs `baseline_core_gate.txt`). The worst sleeve stretch is arms_forward at 1.80 (main 1.69; limit 2.0).
- PMX: `export_pmx.py` + `tools/pmx_reimport.py` give REIMPORT OK, with the 4 sleeve morphs present.

### Motion (`rig_check --extended --report-core --motion`, `motion_delta_sleeves.md`, `motion_delta.py`)
- Sleeves: 9 major / 78 minor → **9 major / 68 minor**. No new majors.
- Every major is equal or better: arms_forward compress improves from 0.071 to 0.064, and the cuff and idol_dance rows are identical. idol_dance's borderline balloon pen_frac stays at 0.031.
- All parts: 115 / 404 → 115 / 394.

### Look (`metrics_delta.md`)
- Silhouette IoU is unchanged (−0.001 at most).
- Shade islands over the six views: +7 in total (front +3, q34_front_left +3, side +2, high −1, back 0, q34_back_right 0).
- These come from the fuller lower bell's terminator, not from specks.

### Order-balanced pairwise Codex A/B vs main (`pairwise.md`, `pairwise_run2.md`)
The 26 items are 5 rest views × cel and clay, plus 8 poses × front and 3/4. The poses are arms_up, reach_up_back, hands_behind_head, arms_crossed, arms_forward, walk, dance_point and idol_dance@81. Every item is shown in both orders, and only consistent picks count. We ran it twice on the final renders, because single runs swing by several items.

| model | run 1 new / old / tie | run 2 | pooled |
|---|---|---|---|
| gpt-6-astra | 10 / 14 / 2 | 9 / 15 / 2 | 19 / 29 / 4 |
| gpt-6.1-sol | 13 / 12 / 1 | 21 / 5 / 0 | 34 / 17 / 1 |
| both | | | **53 / 46 / 5** |

- **Wins.** New wins the rest cel and clay front and 3/4 views, and hands_behind_head, in all runs: "visible compression toward the wrist", "less like a padded pod".
- **Losses.** Astra keeps picking main on these, calling them "pinches" and "angular ribbon turns":
  - arms_forward;
  - the back view, where the fuller outer edge peeks out beside the hair;
  - walk 3/4;
  - arms_crossed.
- **The cuff variant.** The same bag with the cuff girth on scored astra 15/9/2 and sol 17/7/2. It was dropped for the cuff pen above (animation first).
- **Tried and dropped:**
  - Curve-smoothing the rings (Taubin) plus 8 along-sleeve passes, to round the back-view point: fit 25.3. A/B 14/12 and 11/15, then 13/13 and 7/19.
  - An affine ring fit (centre shift + axis scales + ±10% residual): fit 26.8–27.5, too timid.

Images (JPEG; left main, right this PR): `base_vs_final_rest.jpg` (clay and cel front), `base_vs_final_side_back.jpg` (clay side and back), `base_vs_final_poses.jpg` (arms_up, hands_behind_head, idol_dance@81).

The A/B renders were made one fix before the final build. That fix (from the code review) stops the frill's girth floor from widening its lowest, cinched rings, which had been 0.4–2% wider and are tucked into the bag top. The fit, islands, gates and motion numbers above are from the final build.

`ab.py` / `ab_pairs.py` are R9-4's harness. This copy adds arms_crossed to the poses and says in the prompt that the bag's shape may differ.
