# R11: sleeves, ribbon bow, fluted band frill and a two-tier wrist ruffle

Files changed:
- `levi/parts/sleeves.py`
- `levi/rig.py`: a small shared hook, see "Rig fits".

Face counts:
- Sleeves: 8,664 → 17,032 (budget 18,000).
- Model: 107,968 → 116,336.

The source is the clothes-detail review (round 11 analysis). It found three problems:
- The band bow read as a green brick of slab loops.
- The band frill read as a low cup.
- The wrist ruffle read as a thin grey collar from the front and as an 11-point star end-on.

A first pass fixed the construction. An independent review then found that it had moved the rig and added kinks, outline breaks and a cuff that lay on the hand; a second pass fixed those. The owner then looked at the dressed model at 4× and found that from the front the wrist ruffle read as a fan of sharp triangular shards, worst in clay (HD review, p1). This version rebuilds the ruffle's shape for that (see "HD review: the wrist ruffle").

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
  - The rim's largest turn at one vertex is now 33° (round 10: 44°, first pass: 65°). The 90th percentile is 24° (37° / 41°).
  - The rim's height range is 6.6 mm (round 10: 7.0, first pass: 12.5). The side view shows round tulip petals.
- Outer side (`RUFFLE_OUTER_FLAT` 0.7): the flutes' depth, rise and curl are reduced toward the rim, not just the radius. The front view now sees one broad rise there, instead of three stacked blade-like fins.
- Inner side (`RUFFLE_INNER_FLAT`): the flutes lie flatter against the chest. At rest no frill vertex is inside the body; the closest is 6.1 mm away.
- Shading uses the normals of a copy with the flutes 45% as deep.
- The shape-master girth is sampled as before.

**Wrist ruffle (`_cuff_rings`, `CUFF_TIERS`)**
- Two tiers, each a closed fold with thickness (outer face, rolled rim bead ~3 mm across, inner face):
  - `sleeve_cuff` is the upper tier, 22.6 px long.
  - `sleeve_cuff_under` is the under tier, 31.8 px long, about 2 px wider than the upper rim.
- Both are bells: they open out of the gather and turn to hang along the centre line before the rim.
- 10 flutes with round crests and narrower valleys (`CUFF_LOBES`, `CUFF_PINCH` 1.3, `CUFF_ROUND` 0.25), about as deep as a semicircle, spiralling 0.14 rad round the cuff from root to rim (`CUFF_TWIST`).
- The flutes' edges roll (`CUFF_ROLL`): see "HD review" below.
- Where the upper tier covers the under tier:
  - The under tier is nearly round (`CUFF_UNDER_AMP`) and stays clear of the upper tier's valleys.
  - Its flutes turn half a flute round there (`CUFF_UNDER_SHIFT`, via `rot` in `_frill_ring`). Below the upper rim they grow between the upper tier's flutes: end-on a second row of scallops, not a doubled rim.
  - Its edge rolls in step with the upper tier's (`roll_shift`), so both tiers move alike where they overlap.
- Clearance between the tiers (`_cuff_clearance`, asserted in `build`):
  - Over the upper rim's last 8 px and past it: at least 1.8 px (2.8 mm) to the nearest point of the upper tier. It measures 2.11 px.
  - Further in: at least 0.5 px. It measures 1.05 px.
  - No intersecting triangle pairs.
- The under tier's outline is at full width only past the upper rim (`smooth(rim, rim + 3)`). Where the upper tier covers it, the outline is at 35% (`outline_w`, `min_factor`).
- Clearance from the hand: on the hand's back, both tiers flare out (`CUFF_HAND`, 3.2 px) and the under tier's free part a further 7 px (`CUFF_UNDER_HAND`), over a sector centred 0.5 rad round toward the back (`CUFF_HAND_AT`), where the hand's back comes closest.

  | | first pass | second pass | now (r11/base hands) | now (r11/integrate, 风堇 hands) |
  |---|---|---|---|---|
  | under tier to the hand | 0.7 mm | 5.4 mm | 7.0 mm | 4.4 mm (second pass there: 4.2) |
  | upper tier to the hand | — | 10.4 mm | 10.9 mm | 10.8 mm (second pass there: 9.3) |

**HD review: the wrist ruffle (owner, 4× renders)**
- Problem: "from the front the frill reads as a fan of sharp triangular shards, worst in clay; from the side it looks like a normal ruffle". The lobes were flat pointed blades seen edge-on, with knife tips and straight edges radiating from the cuff.
- Diagnosis, on 4× crops of the owner's views plus per-object id, wire and clay close-ups:
  - Each tier flared like a lampshade, its radius still growing at the rim, so the free part fanned out flat.
  - 13 deep flutes (peak to valley about 2/3 of a flute's width) ran as straight radial troughs from root to rim.
  - The crests rose along the axis in step with their radial push (`CUFF_LIFT` 1.6). The front view looks across the hanging forearm, i.e. side-on to the ruffle. There a flute's rim projected onto one straight segment, which met the straight crest line in a point: one knife tip per flute near the silhouette, in both tiers (the comb under the wrist is the under tier).
  - The flutes shaded with a fluteless cone's normals (`CUFF_SHADE` 0.2, `CUFF_SOFT` 0). In clay they showed as flat cut-outs with jagged outlines.
  - End-on (arms_up, arms_forward, reach_forward) the same flutes made a 13-tooth cog.
- Fix (`levi/parts/sleeves.py` only):
  - Bell profiles: each tier opens out of the gather and hangs along the centre line before a rounder rim bead (`CUFF_TIERS`).
  - 10 flutes instead of 13 (`CUFF_LOBES`, `CUFF_N` 120 = 12 per flute), at full depth from d = 17 px (`CUFF_AMP_D`), turning 0.14 rad round the cuff (`CUFF_TWIST`), so no crest or valley is a straight radial line.
  - The rise is a quarter wave out of step with the flutes (`_frill_ring(roll=...)`, `CUFF_ROLL` 1.8 px, `CUFF_LIFT` 0.3). Each flute's edge leans like a rolling wave: side-on it projects onto a round loop, not a segment ending in a point.
  - The flutes shade with 55% of their own normal, the rest from a copy with half-depth flutes (`CUFF_SHADE` 0.55, `CUFF_SOFT` 0.5): the bellies read round in clay and cel.
  - Tried: a stronger roll (2.5 px). The loops were a little rounder but the tier gap dropped to 1.94 px and the hand clearance to 4.1 mm; kept 1.8.
- Result (`cuff_hd.jpg`): from the front, from above, from the back and end-on in arms_up / arms_forward / reach_forward the ruffle reads as rolled, gathered cloth, and the lobe ends read as round loops in cel and clay. The shards, the comb under the wrist and the cog are gone. The side view still reads as a ruffle.
- Remaining: a few lobes seen exactly edge-on at the silhouette (3/4 back-left at rest, reach_forward from the side) end in a rounded point rather than a full loop.
- Faces: the cuff went 6,400 → 6,480 (two more rings on the upper tier; 120 instead of 128 points per ring).

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

  | object | share (second pass) | share (now) |
  |---|---|---|
  | `sleeve_ruffle` | 0.5 | 0.5 |
  | `sleeve_cuff` | 0.625 | 1/3 |
  | `sleeve_ribbon` | 0.5 | 0.5 |
  | `sleeve_cuff_under` | 0 (left out) | 0.1 |

  These are about round 10's densities. Each share's period divides each half's vertex count, so both sides thin alike. The HD fix's bell-shaped tiers keep more of their vertices more than 5 cm off the arm bones; at the second pass's shares they put the drape root 8.2 mm down the forearm from round 10's (joints 6.4 / 3.3 mm off), so the shares were refitted with an offline replica of the fit (checked against the built rig).
- Results against round 10:

  | | round 10 | first pass | second pass | now |
  |---|---|---|---|---|
  | `袖_0.L` root | (0.2202, −0.0313, 0.9103) | (0.2369, −0.032, 0.8951) | 3.4 mm off | (0.2217, −0.0314, 0.9090), 2.0 mm off |
  | joint 1 | (0.2407, −0.0363, 0.8340) | — | 1.4 mm off | (0.2424, −0.0336, 0.8331), 3.3 mm off |
  | joint 2 | (0.2913, −0.0370, 0.7746) | — | 4.2 mm off | (0.2893, −0.0354, 0.7762), 3.0 mm off |

  | capsule | round 10 | first pass | second pass | now |
  |---|---|---|---|---|
  | shoulder | r 5.1, 0.0–8.6 cm | r 5.1, 2.1–9.0 | r 5.0, 0.0–9.0 | r 5.0, 0.0–9.0 |
  | upper arm | r 4.5, 4.4–15.9 | r 4.3, 6.8–15.1 | r 4.3, 5.1–15.7 | r 4.3, 5.1–15.7 |
  | forearm | r 5.2 | r 4.9 | r 5.2 | r 5.3, 0.0–20.9 |
  | hand | r 2.4, 0.8–6.0 | r 2.9, 0.1–6.0 | r 2.2, 0.8–6.0 | r 2.3, 0.8–6.0 |

- Elbow skin out through the bag (left arm skin under the bag at rest that ends up outside it in the pose; `rv_poke`; measured on the second pass, whose drape chain is within 2 mm of this one's):

  | pose | round 10 | first pass | second pass |
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
  | `sleeve_ruffle` | 4,032 |
  | `sleeve_cuff_under` | 3,840 |
  | `sleeve_cuff` | 3,120 |
  | `sleeve_ribbon` | 2,848 |

- Every sleeve object carries `levi_sleeve_s` and `levi_sleeve_param`.
- The ribbon keeps `levi_sleeve_tails`.
- The cuff tiers and the ribbon set `levi_cast_shadow = False`.

## Results

### Gates
- `tools/check.py`: CHECK OK.
- `tools/rig_check.py`: RIG CHECK OK on all 17 core poses. The worst stretch is unchanged (fist 1.86, squat 1.85). Penetration is within 0.1 mm of round 10:

  | pose | round 10 | first pass | second pass | now |
  |---|---|---|---|---|
  | arms_up | 0.60 cm | 0.73 | 0.62 | 0.61 |
  | arms_forward | 0.44 cm | 0.58 | 0.47 | 0.45 |
  | raise_bend | 0.58 cm | 0.63 | 0.59 | 0.59 |

  Every other pose is identical to round 10.

### Motion
Command: `rig_check --quick --no-core --extended --report-core --motion`. The baseline is built from r11/base.

**All parts: 152 major / 332 minor (round 10) → 160 / 325 (second pass: 160 / 326; first pass: 162 / 331).** The HD fix adds no major and removes none against the second pass.
- `hair_curtain_R` is at round 10's values (dance_sway pen 3 mm, pen_frac 0; idol_dance 6 mm, 0.007); the first pass had 10 and 12 mm.
- `look_over_shoulder` hair × garment crossings: 379 → 448 (first pass: 475). Other crossing counts (already major on round 10) moved by under 10%, walk 1,387 → 1,515 the most. These counts rise with the garment triangle count near the hair.

**Sleeves: 9 major / 70 minor → 16 major / 66 minor (second pass: 16 / 67).**
- 6 of the 7 majors new against round 10 are `sleeve_cuff_under`, a new object, in the poses where the cuff was already major on round 10, with the hand pressed to the body:

  | pose | under tier pen / pen_frac (second pass → now) | round-10 cuff |
  |---|---|---|
  | dance_point | 2.85 cm / 0.055 → 2.82 / 0.061 | 2.54 / 0.069 |
  | hug_self | 3.09 / 0.108 → 3.09 / 0.112 | 2.81 / 0.124 |
  | idol_dance | 5.28 / 0.150 → 4.95 / 0.145 | 5.35 / 0.162 |

- The 7th: `sleeve_cuff` pen_frac in hands_behind_back: round 10 0.026, second pass 0.046, now 0.042 (depth 1.6 cm, minor).
- The upper cuff in the same poses: dance_point 2.8 → 2.5 cm (pen_frac 0.064 → 0.066), idol_dance 5.4 → 5.3 cm.
- Flips:

  | pose | balloon (round 10 → first pass → now) | ribbon (round 10 → first pass → now) |
  |---|---|---|
  | idol_dance | 52 → 64 → 54 | 28 → 62 → 42 |
  | reach_up_back | 11 → 18 → 12 | 2 → 13 → 8 |
  | dance_sway | 14 → 15 → 14 | 8 → 19 → 9 |

  The ribbon rows are minor (dance_sway now below the minor threshold). The thinner tails fold more readily than round 10's.
- Frill: seiza pen_frac 0.012 → 0.029 (minor). Everything else is unchanged or lower.

### Look
- Silhouette IoU is unchanged: front 0.9085, side 0.8331, back 0.9126 (second pass: 0.9125).
- Green region IoU:

  | view | round 10 | now |
  |---|---|---|
  | front | 0.391 | 0.401 |
  | side | 0.306 | 0.321 |
  | back | 0.252 | 0.244 |

- Dress region IoU (the cuff is in it) moved by under 0.002: front 0.7599 → 0.7596, back 0.6297 → 0.6286.

- Shape-master fit for sleeves:

  | | round 10 | now |
  |---|---|---|
  | target→ours p50 / p90 | 9.4 / 23.7 mm | 9.1 / 23.6 mm |
  | covered | 0.307 | 0.317 |

- Remaining and seen:
  - A small dark tick on the frill's rolled rim at one valley, at macro scale. It is shading by the soft normals. Own normals there made a wider dark band.
  - At panel scale the front view of the wrist ruffle now reads as a soft rolled puff (`panels.jpg`), not the flat plates the second review noted (its p3).
  - End-on the cuff is 10 round scallops; in cel the valleys between them still show the background through small closed notches, as the sheet's two-tier ruffle does.

### Not run
- `export_pmx.py`, `pmx_reimport.py` and `motion_vmd.py`: mmd_tools is not installed on the cluster Blender. The sleeve morphs on the new objects and the PMX physics fit of the sleeve drapes are unverified.
- No Codex review was run.

## Images
- `frill.jpg`: round 10 | first pass | second pass (the frill is unchanged since).
  - Band side and band front (cel).
  - The rim's outer side (wire).
  - The frill's inner side in arms_up (cel, clay).
- `cuff_hd.jpg`: the HD review fix, before (the owner's state) | after, 4× crops of the dressed model (r11/integrate with this branch): the owner's front crop in cel and clay, the left hand from the front, from 30° above, 3/4 back-left, and arms_up, arms_forward and reach_forward (clay).
- `rig_fit.jpg`: the elbow inside the bag in dance_sway, reach_up_back and hands_behind_head (3/4 cel crops).
- `bow.jpg`: the bow from above and from 3/4 (cel).
- `panels.jpg`: sheet | round 10 | first pass | now, at panel scale, enlarged. Rows: band front and side, wrist front and side.
