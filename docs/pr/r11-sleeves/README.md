# R11: sleeves, ribbon bow, fluted band frill and a two-tier wrist ruffle

Changed file: `levi/parts/sleeves.py` (rig.py untouched). Sleeves go from 8,664 to 15,816 faces (budget 18,000); the model from 107,968 to 115,120.

Source: the clothes-detail review (round 11 analysis). The band bow read as a green brick of slab loops. The band frill read as a low cup. The wrist ruffle read as a thin grey collar from the front and as an 11-point star end-on.

## What changed

**Band bow (`_bow`, `_ribbon`, `_capsule`)**
- Two triangular loops of narrow ribbon, as the sheet draws them.
  - Each loop is a closed Catmull-Rom path (44 samples) traced in the bow's plane: x runs round the band, y down the arm.
  - The loops are laid on the band, wrapping 50% of its curvature, and kept 0.9 px off both the bag's crest envelope and the frill.
  - The band rises toward the outer side, so the droops are set in the bow's plane: the outer loop lies about level and the front loop hangs about 30°.
- The ribbon face is turned 55° from the cloth's normal toward the loop's outside, so each loop is a ring of ribbon: a thin outlined triangle from the front, the ribbon's face from 3/4.
- Sections are stadiums (rounded edges, no box corners).
- Sizes stay at round 10's (loops about 22 px long and 12 px tall; round 9 rejected larger bow loops).
- The knot is a closed wrap: a short capsule with a soft crease across its middle, pinched and capped where the loops enter. It has no open end.
- Tails are thin: 2.7 px wide (was 3.8), tapering to a narrow tip. They keep round 10's paths, sampling and stand-off.
- The back knot is the same closed capsule, smaller.
- Shading: every ribbon vertex shades with the normal of the broad face it belongs to (`SHADE_ATTR`, custom normals after the mirror). A narrow ribbon then shades lit or shaded across its whole width, instead of its rounded edges turning past the terminator as hairline slivers.

**Band frill (`_ruffle_rings`, `_frill_ring`)**
- Height and flutes:
  - The rim stands 31 px above the tie (was 26.4).
  - Flutes are 0.165 deep (was 0.07) with up to 3.4 px of rise (was 1.8).
  - A secondary ripple (22 waves) runs inside the flutes.
  - Ring points go from 72 to 120.
- Rounded flutes (`rnd`): vertices slide round the ring by the lobe phase, so crests and valleys are broad and the flanks steep. With a plain sine as deep as these flutes, both crests and valleys turn into points.
- `_even_params`: every ring uses parameters spaced evenly along the deepest ring, so a round crest gets as many vertices as a flank.
- Ears on the outer side:
  - The frame turns from the band axis (34°) to the rim normal (11.5°), which laid the outer wall over: the deeper flutes stood out there as ears.
  - The outer side is now taken in toward the rim (`RUFFLE_TAPER` 0.18), and flute depths vary by 10% instead of 22% (`var`).
- Inner side: the flutes lie 90% flatter against the chest (`RUFFLE_INNER_FLAT`). Full-depth flutes there reached 7.8 mm into the skin at rest. Now no frill vertex is inside the body at rest, as on round 10.
- Soft shading: like the bag, the cel ramp sees the normals of a copy with the flutes 45% as deep.
- The shape-master girth is still sampled on the plain, untapered frill.

**Wrist ruffle (`_cuff_rings`, `CUFF_TIERS`)**
- Two tiers:
  - `sleeve_cuff`: the upper tier, 22 px long.
  - `sleeve_cuff_under`: a new object, 31 px long, showing about 9 px below the upper tier.
- Both tiers share one centre line, frame and flute pattern, measured by the distance along that line. The under tier therefore nests inside the upper one at every point:
  - the build asserts the gap (`_cuff_clearance`, 1.41 px at the closest);
  - the tiers take the same positional weights.
- 13 round flutes (was 11), 128 points per ring, even vertex spacing along the flutes.
- Each tier is a closed fold with thickness: outer face, rolled rim bead, inner face.
- Where the under tier lies beneath the upper one, its outline thins to 35% (`outline_w` vertex group, `min_factor`).
- Neither tier casts shadows (as before).

**Contracts**
- `sleeve_balloon` keeps the most vertices (4,128; asserted in `build`). The other pieces:

  | object | vertices |
  |---|---|
  | `sleeve_cuff_under` | 3,584 |
  | `sleeve_ruffle` | 3,360 |
  | `sleeve_cuff` | 2,816 |
  | `sleeve_ribbon` | 2,848 |

- Every sleeve object carries `levi_sleeve_s` and `levi_sleeve_param`.
- The ribbon keeps `levi_sleeve_tails`: tails are long strips; the loops and knots are rigid islands.
- The cuff tiers and the ribbon set `levi_cast_shadow = False`.

## Results

### Gates
- `tools/check.py`: CHECK OK (sleeves 15,816 / 18,000).
- `tools/rig_check.py`: RIG CHECK OK, all 17 core poses. Changes vs round 10:
  - arms_up pen: 0.60 → 0.73 cm (sleeve_balloon, 4 → 8 vertices).
  - arms_forward pen: 0.44 → 0.58 cm; stretch 1.80 → 1.79.
  - raise_bend pen: 0.58 → 0.63 cm.
  - Everything else is unchanged.
- Rest pose: no cuff, ribbon or frill vertex is inside the body. The balloon has 5 vertices, 2.35 mm in, as on round 10.

### Motion (`rig_check --quick --no-core --extended --report-core --motion`, baseline built from r11/base)

**Sleeves: 9 major / 70 minor → 16 major / 71 minor.**
- 6 of the 7 new majors are `sleeve_cuff_under`, a new object. They are in the poses where `sleeve_cuff` was already major on round 10: the hand is pressed to the body.

  | pose | under tier, pen / pen_frac | upper cuff, round 10 → new |
  |---|---|---|
  | dance_point | 0.024 / 0.055 | 0.025 / 0.069 → 0.028 / 0.062 |
  | hug_self | 0.027 / 0.108 | 0.028 / 0.124 → 0.031 / 0.116 |
  | idol_dance | 0.051 / 0.142 | 0.054 / 0.162 → 0.055 / 0.158 |

- The 7th: hands_behind_back `sleeve_cuff` pen_frac 0.026 → 0.045. Its depth stays minor, 1.3 cm.
- Tails: back at round 10's sampling (4 points per span). Seven points per span let the thin tails fold with the bag's local folds: 20–109 flipped faces. Ribbon flips are now minor:
  - dance_sway 8 → 19;
  - reach_up_back 2 → 13;
  - idol_dance 28 → 62.
- Several ribbon stretch / compress rows got better (arms_up, arms_forward, dance_point, idol_dance).
- Frill: seiza pen_frac 0.012 → 0.030 (minor, at the threshold). Earlier iterations: 0.053 with full-depth flutes on the inner side, 0.034 with them 60% flatter (both major).

**Effects on other parts (all parts: 152 / 332 → 162 / 331)**
- `hair_curtain_R` pen_frac is new major in dance_sway (0 → 0.057) and idol_dance (0.007 → 0.071), 1.0–1.2 cm deep.
  - The cause: the rig fits its hair-collision arm capsules (`rig.HAIR_COLLIDERS`) to the skin plus every sleeve vertex dominated by an arm bone. The taller, denser frill and the longer cuff move those capsules:

    | capsule | round 10 | new |
    |---|---|---|
    | shoulder.L | 0.0–8.6 cm | 2.1–9.0 cm |
    | upperarm.L | r 4.5, 4.4–15.9 cm | r 4.3, 6.7–15.1 cm |
    | forearm.L | r 5.2 | r 4.9 |
    | hand.L | r 2.4, 0.8–6.0 cm | r 2.9, 0.1–6.0 cm |

  - The mirror case, `hair_curtain_L` in idol_dance, was already 0.078 on round 10.
- Hair × garment crossing counts rise with the garment triangle count. look_over_shoulder 379 → 475 crosses the major threshold; the others were major already.

### Look
- Silhouette IoU is unchanged: front 0.909, side 0.833, back 0.913.
- Green region IoU:
  - front 0.391 → 0.400;
  - side 0.306 → 0.326;
  - back 0.252 → 0.246.
- Shade islands over the six views: 225 → 223.

  | view | change |
  |---|---|
  | front | +3 |
  | side | +3 |
  | back | +1 |
  | q34_front_left | −6 |
  | q34_back_right | +1 |
  | high | −4 |

- Shape-master fit for sleeves:
  - p50 9.5 → 9.0 mm;
  - p90 24.2 → 23.8 mm;
  - covered 0.309 → 0.320.

### Not run
- `export_pmx.py`, `pmx_reimport.py` and `motion_vmd.py`: mmd_tools is not installed on the cluster Blender. Two things are unverified:
  - the sleeve gather / slide morphs on the new objects;
  - the PMX physics fit of the sleeve drapes.
- No Codex pairwise review was run.

## Images
- `band_cel.jpg`: band front, bow face-on (3/4) and band side, cel; round 10 on the left, this PR on the right.
- `band_clay_wire.jpg`: band 3/4 (clay), the bow (wireframe, zoomed) and band back (clay).
- `wrist.jpg`: wrist side (cel), end-on (cel), 3/4 from below (clay), front (wireframe).
- `sheet_panels.jpg`: sheet | round 10 | this PR at panel scale, enlarged ×4–4.4: band front and side, wrist front and side.
- `poses.jpg`: arms_up (wrist, band), hands_behind_head, wrist_twist_pos, idol_dance@81 and arms_crossed.
