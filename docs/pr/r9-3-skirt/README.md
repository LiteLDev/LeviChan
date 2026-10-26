# R9-3: skirt hem relief (deeper, doubled godet folds toward the hem)

Round 9 compared our Levi with a new reference model, an AI image-to-3D mesh (`strengths_guide.md` items 2, 3 and 6). Its skirt folds are about 3× deeper toward the hem, and it shows twice as many across the front. This PR takes the shape idea only. No reference geometry was imported, copied or traced.

**Files:** only `levi/parts/skirt.py` changed. `petticoat.py`, `_skirt_fit.py` and `rig.py` are untouched. The rolled hem lip and the petticoat changes were tried and dropped (see below). Exported names are unchanged.

## What changed (`skirt.hem_relief`, `RELIEF_*`)

The relief only moves cloth **inward**, in narrow valleys:

- **Main troughs:** every main trough sinks by up to `RELIEF_TROUGH` (20 px). The valley is `RELIEF_TROUGH_W` (0.35) of the half-fold wide.
- **Secondary valleys:** every fold's broad rise gets a secondary valley at u = −0.45, up to `RELIEF_SUB` (14 px) deep. A second, smaller crest stands between it and the trough before, so the lower skirt shows 16 folds round the body instead of 8.
- **Height profile:** there is none over the hips. The relief grows from t = 0.42 as s^1.6 and closes again at the edge (`RELIEF_MOUTH` 1.0 from t 0.7). The valleys are deepest in the lower skirt and open into each fold's lobe at the hem.
  - Valleys that stayed open at the edge pinched the petticoat under every trough into creases. That gave +3 or +4 shade islands on the back petticoat and side petticoat IoU −0.007.

The crests carry the three views' outlines and the hem rows stay where they were, so the silhouettes hold.

- **Shading** (`RELIEF_SHADE` 0.6): the outer face's shading normals are 60% their own and 40% those of the same cloth without the relief. This works like the petticoat's `FOLD_SHADE`. The cel split stays clean, while the outline and silhouette keep the full folds.
- **Lighter inner outline** (`skirt_line` vertex group, `HEM_LINE_MIN` 0.45): full width on the outer face, lighter round the hem roll and inside the cloth.
- **Code:** `profiles(folds, relief)` and `_dense(folds, relief)` take the relief share. The cache is keyed per table and relief and keeps at most 4 entries. `azimuths()` always samples the built cloth.

## Tried and dropped

- **Rolled hem lip, 7 mm, built inward.** The outline was kept, and the petticoat's clearance followed it.
  - Look: petticoat IoU +0.01 in every view.
  - Review: both Codex models called the edge "a substantial lip".
  - Motion: it changed the rig. The skirt chains' joints are band centroids of the skirt + petticoat vertices (`rig._band_chain`), and the drape is solved from the innermost cloth. The lip moved both, so run's petticoat stretch went from 2.2 to 2.85 and high_kick got a new major (1.92 → 2.38).
- **Petticoat hem roll 0.6 → 1.5 px with 3 more profile rings.** Petticoat IoU was +0.011–0.014, but the run clip got petticoat penetration of 2.5 cm (main: 1.15 cm) and stretch of 2.96.
- **Petticoat free-edge curl, 60° and 110°.** The lit underside replaced the bottom outline. Petticoat IoU dropped by up to 0.029, with +4 to +14 islands.
- **Deeper relief open nearer the edge, with a thinner lip** (mouth 0.9 from t 0.6). Codex preferred main: "inflated lobes".
- **Smaller tweaks:**
  - The round-8 hem thickening built inward, and less crest tuck (`CURL_K` 0.15): neither removed the shelf above the back hem, which main also has. The lower tuck cost 0.003 of side IoU.
  - A wider petticoat clamp spread: petticoat IoU −0.009 to −0.015.

## Results

### Look gate (`review.py`, against main bae3160)

`final_metrics_delta.md` has the full table; the sheets are `final_01/02/05`.

| view | silhouette IoU | dress IoU | petticoat IoU | shade islands (all regions) |
|---|---|---|---|---|
| front | 0.916 (±0) | 0.786 (±0) | 0.363 (+0.001) | 44 (+1) |
| side | 0.861 (±0) | 0.749 (±0) | 0.353 (±0) | 33 (±0) |
| back | 0.919 (±0) | 0.629 (−0.001) | 0.402 (±0) | 26 (−2) |
| q34 front-left | | | | 43 (±0) |
| q34 back-right | | | | 26 (−2) |
| high | | | | 40 (+1) |

- **Islands:** 212 in total, against main's 214. Dress islands: front +1, high +1, back −1.
- **Back dress IoU:** −0.001 is the one regression.
- **Fold relief** (the guide's `measure.py` method on the skirt sheet, front 120°, Fourier residual):

  | z | rms, main → this PR |
  |---|---|
  | 0.65 | 0.91 → 1.02 cm |
  | 0.70 | 1.00 → 1.19 cm |
  | 0.80 | 1.01 → 1.03 cm |

  - That method keeps the outermost cloth per 2.5° bin, so it mostly misses inward valleys. `ab_rest_clay.jpg` (top = main, bottom = this PR) shows the change better.
  - The guide's ≥ 2 cm target was not reached. A deeper version lost the A/B.

### Pairwise Codex A/B, order-balanced

Every pair was shown in both orders: A = main / B = PR, then A = PR / B = main. A pick counts only when it holds in both orders; anything else is a tie. With single-order counting, one model picked the same position in both orders.

**Rest views:** front, 3/4, high and back, cel + clay (`ab_rest.md`).

| model | A = main | A = PR | order-balanced |
|---|---|---|---|
| gpt-6-astra | PR | PR | **PR** |
| gpt-6.1-sol | PR | main | tie |

**Poses:** sit_chair, seiza, kneel_one, deep_lunge, cross_legged, walk@14, run@8 and spin@20, front + 3/4 (`ab_poses.md`, `ab_poses_q34.jpg`).

| pose | astra | sol |
|---|---|---|
| sit_chair | main | PR |
| seiza | tie | main |
| kneel_one | tie | tie |
| deep_lunge | PR | tie |
| cross_legged | tie | tie |
| walk@14 | tie | tie |
| run@8 | PR | PR |
| spin@20 | tie | tie |
| **total** | PR 2, main 1, tie 5 | PR 2, main 1, tie 5 |

- **Overall:** order-balanced, this PR leads 4–2 on the poses (10 ties) and 1–0 on the rest views (1 tie). run@8 went to this PR consistently with both models.
- **The win is narrow.** Most pairs are inconsistent between orders.
- **The lap drape still moves.** It is rebuilt from the meshes, and the valleys bring cloth nearer the thighs, so `_drape_clear` and the gather pick slightly different turns. Compare cross_legged's front panel in `ab_poses_q34.jpg`.

### Rig and export

- **Core rig check** (17 poses, repeatable): OK, worst stretch 1.84 (fist, body). See `core_gate.txt`.
- **Motion** (`rig_check --extended --motion`, against main): no new major in the skirt or petticoat, and no change in any other part.
  - New minors, all small:
    - high_kick: petticoat core penetration 0.67 → 1.24 cm (hidden core).
    - run_l and run_r: skirt root penetration 0.99 → 1.03 cm and 1.00 → 1.01 cm.
    - seiza and jump_tuck: core pen_frac 0.35% → 0.52%.
  - Better: hair × skirt crossings in run_l and idol_dance (526 → 305).
- **PMX:** `export_pmx.py` exports, and `pmx_reimport.py` gives REIMPORT OK.
- **check.py:** CHECK OK, 102,562 faces. Skirt 22,680 / 24,000.

## Tunables

To dial back:

- **Relief depth:** `RELIEF_TROUGH`, `RELIEF_SUB`. 0 is main's cloth.
- **Relief start and growth:** `RELIEF_T0`, `RELIEF_POW`.
- **Mouth at the edge:** `RELIEF_MOUTH`, `RELIEF_MOUTH_T`.
- **Shading:** `RELIEF_SHADE`. 1 gives true normals.
- **Inner line:** `HEM_LINE_MIN`. 1 gives a uniform line.
