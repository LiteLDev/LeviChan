# R9-4: sleeves, deeper lengthwise folds and a fuller cuff

Files:
- `levi/parts/sleeves.py`: the bag's folds, the cuff ruffle, the shading normals and where the ribbons lie.
- `levi/rig.py`: one helper in the sleeve section (`_ride_smooth`) plus a two-line call in `_sleeve_gather`.

`sleeve_param` / `levi_sleeve_s` are unchanged. The sleeves go from 7,896 to 8,664 faces (budget 18,000), and the model from 102,602 to 103,370.

Source: strengths guide item 7 (the new FBX reference): lengthwise folds that deepen toward the wrist, a gathered wrist, and a 10–14-lobe ruffled cuff. The band, bow and tails stay as on the sheet; there is no rosette. All changes are module parameters, so each can be dialled back.

## What changed

**1. Bag folds (`_fold`)**
- The five lengthwise valleys are deeper toward the wrist:
  - `VALLEY_AMP` 0.07/0.12 → 0.08/0.22.
  - They deepen later, `VALLEY_RAMP` (0.55, 0.95), so the elbow keeps round 8's depth. With the old ramp, hands_behind_head's inner-elbow compress became a major.
  - The ring is inflated by `VALLEY_INFLATE` 0.4 of their depth, so the ridges stand proud.
- The wrist gather is new: `GATHER_K` 8 pleats, `GATHER_CUFF` 0.15 (was 0.05 over the last quarter).
  - They grow from s = 0.6 (`GATHER_RISE`, `_POW` 1.6) and fan up the lower bell as lengthwise folds.
  - Narrow valleys and broad crests (`GATHER_PINCH`), uneven widths (`GATHER_IRR`), and a slight wander round the arm (`GATHER_TWIST`).
  - `GATHER_BIAS` 0.5: the pleats swing half outward, so their valleys don't sink into the forearm.
  - The turned-in lip and facing take `HEM_FOLD` 0.4 of the folds. Fully crinkled, they caught the light as bright flecks at the opening.

**2. Cuff ruffle (`_cuff_bm`)**
- 11 rounded lobes (was 8, nearly flat).
- Fluting grows toward the free edge: `CUFF_AMP` 0.12, `CUFF_LIFT` 1.2 px, both ∝ s^0.7.
- Each crest turns outward near the rim (`CUFF_CURL`, a new `curl` argument of `_frill_ring`).
- The rim rolls into a bead about 3 mm across. Lobe amplitude and lift are now functions of s, so the outer and inner faces stay parallel round every lobe.
- The root sits about 1 px further inside the hem, clear of the pleat valleys. Before, it poked through as a bright notch in clay.

**3. Shading normals (`_soft_normals`, `FOLD_SHADE` / `FOLD_SOFT`, `CUFF_SHADE` / `CUFF_SOFT`)**
- The cel ramp sees the bag as if its valleys and wrist pleats were 45% as deep.
- The cuff gets 20% of its lobes' own normal over the un-lobed bell's.
- Silhouette, outline and clay keep the full relief.
- The lip and facing keep their own split normals: a blended normal smeared the hem crease into flecks.
- This is the petticoat's `FOLD_SHADE` idea, mirrored for the right side.

**4. Ribbons lie on the folds' crest envelope (`_fold(env=True)`)**
- The bow and the tails are placed on the bag with the valleys and wrist pleats removed, so a tail bridges a fold instead of dipping into it.
- Laid into the deeper valleys, a tail kinked and folded up at idol_dance@81: a ribbon compress major (0.061), and with another setting a jitter major (0.81).

**5. rig.py, sleeve section: `_ride_smooth`**
- The tails' ridden gather/slide key displacement is averaged within `SLEEVE_RIDE_SMOOTH` over the same strip, as their weights already are.
- Before, the corners of the 0.5 mm-thin strip sampled different bag vertices, and the strip folded up as the bag gathered.
- The round-8 gather and slide keys are still built from the mesh at rig time. The PMX check finds the 4 morphs: 左袖寄せ moves 2,026 vertices, 左袖滑り 1,595.

## Results

### Order-balanced pairwise Codex A/B (`pairwise.md`)
- 26 items: 5 rest views × cel and clay, plus 8 poses × front and 3/4. Each item was shown in **both orders** (old | new and new | old).
- A pick counts only if a model chose the same version both times; otherwise it is a tie. No pick was inconsistent.

| model | new | old | tie |
|---|---|---|---|
| gpt-6-astra | 18 | 4 | 4 |
| gpt-6.1-sol | 20 | 4 | 2 |

- New wins every rest cel view with astra, and every pose with a visible cuff with both models: arms_up, reach_up_back, arms_forward, walk, dance_point, idol_dance@81. The reason given: "the cuff reads as gathered cloth instead of a stiff flared band".
- The old picks are mostly clay close-ups of the wrist join ("puckering at the sleeve-to-cuff join"). Sol also picked old on two cel views.
- An earlier run of the same harness, with the hem crease fully crinkled, scored 20/3/3 and 23/1/2. The reviewers count the gathered hem as pinching in clay. `HEM_FOLD` dials that back.
- `ab.py` and `ab_pairs.py` reproduce the run.

### Hard gate
- **Silhouette / regions** (`metrics_delta.md`): IoU unchanged (dress −0.001 at most, green +0.000…+0.001).
- **Shade islands**:
  - Total over the six views: 214 → 214.
  - Per view: front −3, q34_front_left −2, side −1, back +2, q34_back_right +1, high +2.
  - The sweeps over shading blends, lobe counts and normals found nothing lower. Rejected:
    - the folds' own normals: +19 dress islands;
    - 12 lobes: 217 in total;
    - 14 lobes: 221 in total;
    - per-corner normals keeping creases past 40–75°: 216–220 in total.
- **Core rig check** (`baseline_core_gate.txt`, `final_core_gate.txt`): RIG CHECK OK. Every pose is within ±0.03 of main (wrist_twist 1.32 → 1.30, raise_bend 1.43 → 1.40, reach_forward 1.56 → 1.59). `tools/check.py`: CHECK OK.
- **Motion** (`motion_delta_sleeves.md`, `motion_delta_all.md`):
  - Sleeves: 8 major / 78 minor → 9 / 78. 7 rows better, 9 worse.
  - The one new major is idol_dance `pen_frac` on the bag, 0.0296 → 0.0310 against a 0.03 threshold: about 6 more of 4,128 vertices.
    - It does not come from the deeper folds. It stays at 0.0303–0.0305 with round 8's valleys and no wrist pleats at all, and its depth (`pen`) is unchanged.
    - It comes from losing round 8's inward cuff pleats, whose vertices sat inside the forearm at rest.
  - No other new majors. The all-parts total is 115 → 116 majors (this one).
  - Tried and dropped:
    - `RING_N` 72 with 12 pleats: flips at the elbow, idol 101 and arms_forward 152.
    - The guide's `GATHER_K` 12 on 48 vertices would be 4 vertices per pleat.
- **PMX** (`final_pmx.txt`): export and reimport OK, VMD round trip 0.00 mm.

### Not done
- The hands_behind_head inner-elbow crease (R9-7 traced it to `SLEEVE_ELBOW_SPREAD` / `SLEEVE_ARM_KNOTS`) was left alone. The pairwise review sees no difference there (tie with both models), and its compress stays minor.

Images:
- `base_vs_final_cel.jpg`: top row main, bottom row this PR. Front, side, 3/4, back.
- `base_vs_final_clay.jpg`: the same in clay, with high instead of back.
