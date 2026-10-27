# R10-A3: the outer skirt follows the shape master

`levi/parts/skirt.py` only (plus an "obsolete" note in its private helper `_skirt_fit.py`). No rig.py change.

## What changed
- `_target()` samples the shape master (`levi.shape.radial` over all labels) on a 0.5 deg x 2 px grid of
  polar angle x panel row round the body axis and keeps the outermost hits labelled `skirt`.
  - Filtered: flute pockets (a sample further in than the cloth above and below it), anything within
    14 rows / 3 deg of hair, sleeves or body hits (hair locks and hands are partly labelled skirt), samples
    that jump off their column's surface (followed from a seed above the hem), runs shorter than 10 samples.
  - Gaps are filled as an offset from the sheet's bell, along the column and round the ring, by inverse
    distance. Above a column's first sample a monotone cubic eases to 0 at the waist, so the folds seen
    under the back hair run on up without a kink.
  - Below row 470 the cloth may turn in or out only gently (`TGT_TUCK` / `TGT_FLARE`): the master's
    flounce rolls in under the lobes (inflated lobes on a single sheet) and kicks its ruffle edge out.
  - Hem row: the lowest skirt sample, extended through the flounce where it is labelled petticoat (round
    the sides it read as flat-topped high arches), stray label columns filled.
- `_dense()` takes the hem row and, below the waistband (`TGT_TOP`, rows 342-392), the radius from the
  master; the waistband under the bodice stays procedural.
- `section()` is the master's bell (the cloth low-passed round the skirt), blended into the sheet's
  sections under the bodice. `fold_table()` is read off the master (13 crests: offset maxima above the hem,
  hem rows at crest / arch top, half-depths), so `hem_terms` / `fold_index` (petticoat clusters, streaks,
  trough flare) describe the built cloth. `profiles`, `front_surface_y`, `THICK`, `T_STEPS`, topology,
  rings, shell (outer / inner / hem roll coincident) and attributes are unchanged; 22680 faces (budget 24000).

## Fit (tools/shape_fit.py, skirt, target -> ours p50 / p90 / p99 mm)
| | p50 | p90 | p99 | covered |
|---|---|---|---|---|
| main (r9) | 14.6 | 48.3 | 96.7 | 0.204 |
| this | 14.0 | 36.9 | 64.4 | 0.254 |

Followers improved too (review.py run): hair_back p90 -3.9 mm, bodice p90 -4.7 mm; petticoat 34.5 -> 34.2.

## Gates
- `tools/check.py`: CHECK OK. `tools/rig_check.py` (full, 17 core poses): RIG CHECK OK (`final_core_gate.txt`).
- `export_pmx.py` + `tools/pmx_reimport.py`: REIMPORT OK, VMD round trip 0.00 mm (`final_pmx.txt`).

## Motion (rig_check --extended --report-core --motion; `motion_delta.txt`, `motion_skirt_values.txt`)
Skirt + petticoat (pose x part x metric) rows at minor / major: main 50 / 14, this 44 / 15.
- Majors resolved: run_r skirt stretch 2.15 -> 1.71, run skirt stretch 2.23 -> 1.82, run skirt jitter 0.40 -> ok,
  run petticoat pop 83 mm -> ok, spin petticoat stretch 2.09 -> 1.97, jump_tuck petticoat stretch 2.02 -> 1.97,
  sit_chair / sit_stand skirt stretch 2.07 -> 2.01 / 1.96.
- New majors (all near the threshold): petticoat stretch in cross_legged 2.00 -> 2.13, high_kick 1.95 -> 2.11,
  lie_back_elbows 1.93 -> 2.09, run_r 1.94 -> 2.09 (petticoat_tier1 hem, whose rest shape in front is
  unchanged: it rides the re-fitted skirt chains); cross_legged skirt pen 1.09 -> 2.02 cm; walk petticoat
  pop 8.0 mm (frame 11); run petticoat jitter 0.42 (run had a skirt jitter major of 0.40 before).
- Tried and dropped (probes on the same poses + walk / run): DRAPE_CLEAR 0.012, DRAPE_BEND 20, SEAT_BEND 14,
  DRAPE_STRAIN 0.4, 24-deg fold spacing (9 folds), hem 15 px lower, wider fold smoothing: each moved the
  majors around or made them worse (the petticoat pen jumped to 2-3 cm in several), so the drape parameters
  are unchanged.
- No bowl: sit_chair, seiza, kneel_one, cross_legged, deep_lunge, high_kick, jump_tuck, run_r inspected
  (`main_vs_final_poses.jpg`: left three main, right three this).
- Codex motion_review (`motion_review_delta.txt`, skirt/petticoat-implicated ratings): astra 3 better
  (kneel_one, run_l, run_r minor -> clean), 0 worse; sol 1 worse (kneel_one clean -> minor, "broad stiff
  section of skirt raised with the thigh"), 0 better. cross_legged stays major in both, for both models.

## Looks: order-balanced pairwise Codex A/B vs main (`pairwise.md`, script `ab.py`)
32 items (6 rest cel + 6 rest clay close-ups, 10 poses x front / 3/4), each shown in both orders (64 images);
only picks consistent across the two orders count.

| model | new | old | tie |
|---|---|---|---|
| gpt-6-astra | 28 | 4 | 0 |
| gpt-6.1-sol | 29 | 3 | 0 |

Losses: astra high_kick front + 3/4 (the front panel lifts higher, toward the chest) and cross_legged
front + 3/4 (a sharper fold across the lap); sol high_kick 3/4, kneel_one 3/4, deep_lunge 3/4 (a stiffer
crest over the raised thigh).
All 12 rest views won by both models. Earlier iterations: first cut 9-23 (spikes
under the hair, boxy flounce, balloon lobes), fixed by the filters and the flare limits above.

## Shade islands / three-view (report only; `final_metrics_delta.md`)
Island total 209 -> 213 (front +3, high +8, back -5, side -4). IoU: front 0.915 (-0.001), side 0.840
(-0.021), back 0.919 (+0.001); the master's skirt is shorter in front and fuller behind than the sheet.

## Notes for later units
- The hair_back lock ends ride the fuller back (`hair_back.skirt_sx`); one curl lies more horizontally.
- The petticoat (wave 2) shows a little more under the shorter front hem.
- `_skirt_fit.py` / `FOLDS` no longer drive the build (kept as a record).
- Importing skirt (or petticoat, which calls `skirt.section` at import) now loads the shape master (~1.5 s).
