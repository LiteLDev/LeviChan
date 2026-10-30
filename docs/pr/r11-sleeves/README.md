# R11: sleeves, ribbon bow, fluted band frill and a two-tier wrist ruffle

Files changed:
- `levi/parts/sleeves.py`
- `levi/rig.py`: a small shared hook, see "Rig fits".

Face counts:
- Sleeves: 8,664 → 16,952 (budget 18,000).
- Model: 107,968 → 116,256.

The source is the clothes-detail review (round 11 analysis). It found three problems:
- The band bow read as a green brick of slab loops.
- The band frill read as a low cup.
- The wrist ruffle read as a thin grey collar from the front and as an 11-point star end-on.

A first pass fixed the construction. An independent review then found that it had moved the rig and added kinks, outline breaks and a cuff that lay on the hand. This version fixes those findings.

## What the part does now

**Band bow (`_bow`, `_ribbon`, `_capsule`, `_tails`)**
- The loops:
  - Two triangular loops of narrow ribbon. Each is a closed path laid on the band, kept 0.9 px off the cloth and the frill.
  - The ribbon face is turned 55° toward the loop's outside. From the front each loop reads as a thin outlined triangle, from 3/4 as the ribbon's face.
  - Sections are stadiums, so there are no box corners. Loop sizes are round 10's.
- The knot is a closed, rounded wrap with no open end. The back knot is the same, smaller.
- The tails:
  - They are thin (2.7 px).
  - Each leaves the knot from its lower side, 1 px toward the cloth (`TAIL_START`). Until it is past the loops it runs 0.8 px off the cloth, under the loops' lowest edge (`TAIL_UNDER`).
  - Before this, the tails started at the knot's centre and ran through both loops: 241 intersecting triangle pairs. Now 34 remain (round 10: 98).
- Ribbon shading uses the normal of each ribbon's broad face (`SHADE_ATTR`), so a narrow ribbon is lit or shaded across its whole width.

**Band frill (`_ruffle_rings`, `_frill_ring`)**
- Shape:
  - The rim stands 31 px above the tie (round 10: 26.4).
  - Flutes are 0.165 deep (round 10: 0.07).
  - There are 144 ring points (round 10: 72).
  - A gentle secondary ripple (18 waves) runs inside the flutes.
- The flutes have rounded crests (`RUFFLE_ROUND` 0.5).
- The rise along the frill is now a plain wave of the *slid* angle (`_frill_ring`):
  - Before, it was computed at the unslid angle, so the whole rise crowded into the steep flanks. The rim stood in square steps (a crown in the side view) with an S-hook in the rolled rim.
  - The rim's largest turn at one vertex is now 33° (round 10: 44°, previous: 65°). The 90th percentile is 24° (37° / 41°).
  - The rim's height range is 6.6 mm (round 10: 7.0, previous: 12.5). The side view shows round tulip petals.
- Outer side (`RUFFLE_OUTER_FLAT` 0.7): the flutes' depth, rise and curl are reduced toward the rim, not just the radius. The front view now sees one broad rise there, instead of three stacked blade-like fins.
- Inner side (`RUFFLE_INNER_FLAT`): the flutes lie flatter against the chest. At rest no frill vertex is inside the body; the closest is 6.1 mm away.
- Shading uses the normals of a copy with the flutes 45% as deep.
- The shape-master girth is sampled as before.

**Wrist ruffle (`_cuff_rings`, `CUFF_TIERS`)**
- Two tiers:
  - `sleeve_cuff` is the upper tier, 22 px long.
  - `sleeve_cuff_under` is the under tier. It is longer and flares about 2.5 px wider than the upper rim.
- Each tier is a closed fold with thickness: outer face, rolled rim bead, inner face.
- 13 flutes shaped as scallops, with round crests and narrower valleys (`CUFF_ROUND` 0.3, `CUFF_PINCH` 1.3). Before, `CUFF_ROUND` 0.6 with even waves gave a cog of flat-topped teeth.
- Where the upper tier covers the under tier:
  - The under tier is nearly round (`CUFF_UNDER_AMP`) and stays clear of the upper tier's valleys.
  - Its flutes turn half a flute round there (`CUFF_UNDER_SHIFT`, via `rot` in `_frill_ring`). Below the upper rim they then grow between the upper tier's flutes. End-on this gives a second row of scallops instead of a doubled rim.
- Clearance between the tiers (`_cuff_clearance`, asserted in `build`):
  - Over the upper rim's last 8 px and past it: at least 1.8 px (2.8 mm) to the nearest point of the upper tier. It measures 2.04 px.
  - Further in: at least 0.5 px. It measures 1.04 px.
  - No intersecting triangle pairs.
  - The previous version had 1.4 px at the closest. That is less than the outline hull, so the upper rim's outline broke into white gaps and dark hooks.
- The under tier's outline is at full width only past the upper rim (`smooth(rim, rim + 3)`). Where the upper tier covers it, the outline is at 35% (`outline_w`, `min_factor`).
- Clearance from the hand:
  - On the hand side (`CUFF_UNDER_HAND`), the under tier's free part flares out by up to 5 px, so it stands 5.4 mm off the hand at rest. The previous version was 0.7 mm off.
  - The upper tier is 10.4 mm off.
- Tried and dropped: an extra forward and downward tilt of the under tier, so the front view would see the flutes' bellies (review p3). It brought the under tier's inner side within 0.35 px of the upper tier, which breaks the outlines again.

**Rig fits (`rig.RIG_FIT_PROP`, `rig._fit_verts`; `sleeves.RIG_FIT_SHARE`)**
- Two rig fits read the sleeves' vertices:
  - the sleeve drape chain, from the centroid of the vertices far from the arm bones and band centroids under it;
  - the hair colliders' arm capsules, from percentiles of the vertices.
- Both count vertices, so they moved with the new density:
  - The under tier and the 2–4× denser frill and cuff pulled the drape root 2.3 cm down the forearm. That re-weighted the bag, and the elbow showed through it in reach_up_back, dance_sway, hands_behind_head and arms_up.
  - The arm capsules moved too. That made `hair_curtain_R` go into the body in dance_sway and idol_dance.
- Leaving the frill and cuffs out of the fits does not restore round 10's values:
  - The shoulder capsule's radius drops from 5.1 to 2.7 cm.
  - The chain joints move 2–3 cm.
- The fix: an object property `levi_rig_fit` gives the share of its vertices that these fits sample, as an even, deterministic thinning. The sleeves set:

  | object | share |
  |---|---|
  | `sleeve_ruffle` | 0.5 |
  | `sleeve_cuff` | 0.625 |
  | `sleeve_ribbon` | 0.5 |
  | `sleeve_cuff_under` | 0 (left out) |

  These are about round 10's densities. Each share's period divides each half's vertex count, so both sides thin alike.
- Results against round 10:

  | | round 10 | previous | now |
  |---|---|---|---|
  | `袖_0.L` root | (0.2202, −0.0313, 0.9103) | (0.2369, −0.032, 0.8951) | (0.2227, −0.0314, 0.9080), 3.4 mm off round 10 |
  | joint 1 | (0.2407, −0.0363, 0.8340) | — | (0.2416, −0.0352, 0.8339), 1.4 mm off |
  | joint 2 | (0.2913, −0.0370, 0.7746) | — | (0.2883, −0.0355, 0.7772), 4.2 mm off |

  | capsule | round 10 | previous | now |
  |---|---|---|---|
  | shoulder | r 5.1, 0.0–8.6 cm | r 5.1, 2.1–9.0 | r 5.0, 0.0–9.0 |
  | upper arm | r 4.5, 4.4–15.9 | r 4.3, 6.8–15.1 | r 4.3, 5.1–15.7 |
  | forearm | r 5.2 | r 4.9 | r 5.2 |
  | hand | r 2.4, 0.8–6.0 | r 2.9, 0.1–6.0 | r 2.2, 0.8–6.0 |

- Elbow skin out through the bag (left arm skin under the bag at rest that ends up outside it in the pose; `rv_poke`):

  | pose | round 10 | previous | now |
  |---|---|---|---|
  | reach_up_back | 8 | 25 | 10 |
  | hands_behind_head | 6 | 14 | 8 |
  | dance_sway | 6 | 15 | 5 |
  | arms_up | 6 | 17 | 6 |

**Contracts**
- `sleeve_balloon` keeps the most vertices (asserted in `build`):

  | object | vertices |
  |---|---|
  | `sleeve_balloon` | 4,128 |
  | `sleeve_cuff_under` | 4,096 |
  | `sleeve_ruffle` | 4,032 |
  | `sleeve_ribbon` | 2,848 |
  | `sleeve_cuff` | 2,816 |

- Every sleeve object carries `levi_sleeve_s` and `levi_sleeve_param`.
- The ribbon keeps `levi_sleeve_tails`.
- The cuff tiers and the ribbon set `levi_cast_shadow = False`.

## Results

### Gates
- `tools/check.py`: CHECK OK.
- `tools/rig_check.py`: RIG CHECK OK on all 17 core poses. The worst stretch is unchanged (fist 1.86, squat 1.85). Penetration is within 0.3 mm of round 10:

  | pose | round 10 | previous | now |
  |---|---|---|---|
  | arms_up | 0.60 cm | 0.73 | 0.62 |
  | arms_forward | 0.44 cm | 0.58 | 0.47 |
  | raise_bend | 0.58 cm | 0.63 | 0.59 |

  Every other pose is identical to round 10.

### Motion
Command: `rig_check --quick --no-core --extended --report-core --motion`. The baseline is built from r11/base.

**All parts: 152 major / 332 minor (round 10) → 160 / 326 (previous: 162 / 331).**
- `hair_curtain_R` is back to round 10's values:

  | pose | pen | pen_frac |
  |---|---|---|
  | dance_sway | 3 mm | 0 |
  | idol_dance | 6 mm | 0.007 |

  The previous version had 10 and 12 mm.
- `look_over_shoulder` hair × garment crossings: 379 → 448 (previous: 475). This count rises with the garment triangle count.

**Sleeves: 9 major / 70 minor → 16 major / 67 minor.**
- 6 of the 7 new majors are `sleeve_cuff_under`, a new object. They are in the poses where the cuff was already major on round 10, with the hand pressed to the body. Its pen_frac is below the round-10 cuff's in all three poses. Its depth is 1–3 mm deeper in two of them:

  | pose | under tier pen / pen_frac | round-10 cuff |
  |---|---|---|
  | dance_point | 2.85 cm / 0.055 | 2.54 / 0.069 |
  | hug_self | 3.09 / 0.108 | 2.81 / 0.124 |
  | idol_dance | 5.28 / 0.150 | 5.35 / 0.162 |

- The 7th: `sleeve_cuff` pen_frac in hands_behind_back went 0.026 → 0.046 (depth 1.35 cm, minor).
- Flips:

  | pose | balloon (round 10 → previous → now) | ribbon (round 10 → previous → now) |
  |---|---|---|
  | idol_dance | 52 → 64 → 54 | 28 → 62 → 42 |
  | reach_up_back | 11 → 18 → 13 | 2 → 13 → 8 |
  | dance_sway | 14 → 15 → 14 | 8 → 19 → 12 |

  The ribbon rows are minor. The thinner tails fold more readily than round 10's.
- Frill: seiza pen_frac 0.012 → 0.029 (minor). Everything else is unchanged or lower.

### Look
- Silhouette IoU is unchanged: front 0.909, side 0.833, back 0.913.
- Green region IoU:

  | view | round 10 | now |
  |---|---|---|
  | front | 0.391 | 0.401 |
  | side | 0.306 | 0.321 |
  | back | 0.252 | 0.244 |

- Shape-master fit for sleeves:

  | | round 10 | now |
  |---|---|---|
  | target→ours p50 / p90 | 9.4 / 23.7 mm | 9.1 / 23.6 mm |
  | covered | 0.307 | 0.317 |

- Cuff rim turn per vertex: the upper tier's largest is 82° and its 90th percentile 54° (round 10: 77 / 57). These are the scallops' valleys.
- Remaining and seen:
  - A small dark tick on the frill's rolled rim at one valley, at macro scale. It is shading by the soft normals. Own normals there made a wider dark band.
  - At panel scale, the front view of the wrist ruffle still reads as flat plates (review p3; see the dropped tilt above).

### Not run
- `export_pmx.py`, `pmx_reimport.py` and `motion_vmd.py`: mmd_tools is not installed on the cluster Blender. The sleeve morphs on the new objects and the PMX physics fit of the sleeve drapes are unverified.
- No Codex review was run.

## Images
- `frill.jpg`: round 10 | previous | this.
  - Band side and band front (cel).
  - The rim's outer side (wire).
  - The frill's inner side in arms_up (cel, clay).
- `cuff.jpg`: round 10 | previous | this.
  - End-on (cel, clay).
  - Wrist outer side (cel).
  - Wrist side (cel, clay).
- `rig_fit.jpg`: the elbow inside the bag in dance_sway, reach_up_back and hands_behind_head (3/4 cel crops).
- `bow.jpg`: the bow from above and from 3/4 (cel).
- `panels.jpg`: sheet | round 10 | previous | this, at panel scale, enlarged. Rows: band front and side, wrist front and side.
