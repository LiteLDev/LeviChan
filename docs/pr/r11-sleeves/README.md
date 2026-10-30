# R11: sleeves, ribbon bow, fluted band frill and a two-tier wrist ruffle

Files changed:
- `levi/parts/sleeves.py`
- `levi/rig.py`: a small shared hook, see "Rig fits".

Face counts:
- Sleeves: 8,664 → 17,752 (budget 18,000).
- Model: 107,968 → 117,056.

The source is the clothes-detail review (round 11 analysis). It found three problems:
- The band bow read as a green brick of slab loops.
- The band frill read as a low cup.
- The wrist ruffle read as a thin grey collar from the front and as an 11-point star end-on.

A first pass fixed the construction. An independent review then found that it had moved the rig and added kinks, outline breaks and a cuff that lay on the hand; a second pass fixed those. The owner then looked at the dressed model at 4× and found that from the front the wrist ruffle read as a fan of sharp triangular shards, worst in clay (HD review, p1). The HD fix rebuilt the ruffle's shape for that (see "HD review: the wrist ruffle"). An independent 4× verification of it then found that the under tier passed through itself and still showed a fang from above and tapered tongues from the palm side; a second pass reshaped the under tier for that (see "HD verify (round 2)"). A third 4× verification found one more pointed tip, a small thorn at the cuff's edge in both 3/4 front views and a horn in reach_forward; this version removes it (see "HD verify (round 3)").

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
  - `sleeve_cuff` is the upper tier, 23.0 px long (verify round 2: 22.6).
  - `sleeve_cuff_under` is the under tier, 34.5 px long, about 1 px wider than the upper rim (HD fix: 31.8 px, 2 px wider).
- Both are bells: they open out of the gather and turn to hang along the centre line before the rim. The under tier opens in a short shoulder just below the upper rim, then hangs.
- Each tier's inner face is its outer face taken in radially at the outer face's own stations (`_offset_tier`), so the two cannot cross.
- 10 flutes with round crests and narrower valleys (`CUFF_LOBES`, `CUFF_PINCH` 1.3, `CUFF_ROUND` 0.25), about as deep as a semicircle, spiralling 0.14 rad round the cuff from root to rim (`CUFF_TWIST`).
- The flutes' edges roll (`CUFF_ROLL`): see "HD review" below.
- Each tier's flutes lose part of their depth over the last px before its rim (`CUFF_RIM_EASE`: the upper tier 70% over 10 px, the under tier 60% over 6 px), so a flute ends under a belly in a round nose: see "HD verify (round 3)".
- Where the upper tier covers the under tier:
  - The under tier is nearly round (`CUFF_UNDER_AMP`) and stays clear of the upper tier's valleys.
  - Its flutes turn half a flute round there (`CUFF_UNDER_SHIFT`, via `rot` in `_frill_ring`). Below the upper rim they grow between the upper tier's flutes: end-on a second row of scallops, not a doubled rim.
  - Its edge rolls in step with the upper tier's (`roll_shift`), so both tiers move alike where they overlap.
- Clearance between the tiers (`_cuff_clearance`, asserted in `build`):
  - Over the upper rim's last 8 px and past it: at least 1.8 px (2.8 mm) to the nearest point of the upper tier. It measures 2.56 px (verify round 2: 2.07; HD fix: 2.11).
  - Further in: at least 0.5 px. It measures 1.05 px.
  - No intersecting triangle pairs between the tiers, and none within a tier (`_cuff_self_overlap`, asserted since verify round 2).
- The under tier's outline is at full width only past the upper rim (`smooth(rim, rim + 3)`). Where the upper tier covers it, the outline is at 35% (`outline_w`, `min_factor`).
- Clearance from the hand: on the hand's back (a sector centred 0.5 rad round toward the back, `CUFF_HAND_AT`), both tiers flare out (`CUFF_HAND`, 3.2 px). The under tier opens a further 1.5 px under the upper tier and 3.2 px in its shoulder over a wider sector (`CUFF_UNDER_HAND`), and its hanging part is shorter there (`CUFF_UNDER_SHORT`).

  | | first pass | second pass | HD fix (r11/base / r11/integrate) | now (r11/base / r11/integrate) |
  |---|---|---|---|---|
  | under tier to the hand | 0.7 mm | 5.4 mm | 7.0 / 4.4 mm | 7.6 / 4.5 mm |
  | upper tier to the hand | — | 10.4 mm | 11.1 / 10.8 mm | 11.1 / 10.8 mm |

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

**HD verify (round 2): the under tier**
- The independent 4× verification of the HD fix found (`cuff_verify.jpg`; "before" there is the HD fix on r11/integrate):
  - p2: the under tier passed through itself, ~880 triangle pairs a side (1,756 in all; 1,008 before the HD fix). In clay: hard-edged crescents inside the bell end-on and a serrated line under the upper rim; in cel, jagged shade islands. Cause: its inner face had stations of its own (d 25.8 / 19.5 px). Between them its rings ran a straight chord across the bell's inward curve, outside the outer face over d 21.5–25.
  - p2, and the HD p1 still "partly": from above, one under-tier flute hung under the wrist as a cone ending in a point; from the palm side, 2–3 flutes showed as tapered tongues with V tips. The free part kept opening to its rim (50–70° off the centre line), plus 7 px more over a narrow sector by the hand's back. Seen edge-on, a flute of such a skirt is a wedge whose tip is the thin rim bead.
- Fix (`levi/parts/sleeves.py` only):
  - `_offset_tier`: the inner face is made at the outer face's own stations, taken in radially by a thickness (0.5–1.3 px). At one d both faces get the same flutes, turn, rise and flare, so ring by ring they cannot cross. A station is skipped only where the outer face curves outward. `_cuff_self_overlap` counts triangle pairs that cross within a tier; `build` asserts 0 for both tiers.
  - Profile: below the upper rim the under tier opens in a short shoulder (d 24–29 px), then hangs to a rim at d 34.5 (was 31.8), ~1 px wider than the upper rim (was 2 px). Under the upper tier it keeps only its root and d 21.5, so it still has 16 rings and the face count stays 17,032.
  - Hand side: the 7 px narrow flare is gone. The under tier opens 1.5 px under the upper tier, as far as the tier gap allows, and 3.2 px in its shoulder over a wider sector (`CUFF_UNDER_HAND`). Its hanging part is 65% shorter at the hand's back (`CUFF_UNDER_SHORT`): a hem that curves up over the hand.
  - Its edge rolls twice as much in the hanging part and its crests no longer turn outward (`CUFF_UNDER_FREE`). Its flutes are 0.8 as deep as the upper tier's (`CUFF_UNDER_AMP`). A lobe seen edge-on now ends in a curl. (Round 3 takes the doubled roll back: it curled some lobe ends past the loop into hooks.)
  - It is 1.2 px narrower on the side the wrist flexes toward (`CUFF_UNDER_FLEX`). Its free part takes more of 手首 than the upper rim does; in wrist_twist_pos (forearm twist plus a 20° flex) its shoulder pressed into the upper rim there.
  - Tried and dropped:
    - A later shoulder (d 24.4–29). It is flatter on the inner side, where the rings fan with the droop: an 88° step, and the offset faces crossed there.
    - Less ring tilt past the upper rim. It moved the gap problem to the other side (1.77 px).
- Results (r11/integrate with this branch; overlap counts per model, both sides):

  | | HD fix | now |
  |---|---|---|
  | under tier self-intersecting pairs, rest / arms_up / arms_forward / reach_forward / hands_on_hips | 1,756 / 1,746 / 1,756 / 1,756 / 1,760 | 0 in each |
  | the same in wrist_twist_pos / _neg | 1,752 / 1,752 | 0 / 0 |
  | upper × under tier pairs, wrist_twist_pos / _neg | 84 / 32 | 32 / 0 |
  | under tier to the hand at rest / hands_on_hips | 4.4 / 2.8 mm | 4.5 / 3.1 mm |

  - In clay the crescents end-on and the serrated line under the upper rim are gone; in cel, the shade islands there too.
  - From above, the fang is now a loop with a round end. From the palm side, the lobes end in curls (cel and clay).
  - The owner's 4× front, side, back and 3/4 crops read as before (`cuff_verify.jpg`, last row).
- Remaining:
  - From the palm side (a camera inside the body), some lobes still show as narrow tongues, now with curled ends.
  - A lobe seen exactly edge-on at the silhouette still shows its ~2 mm rim bead as a thin point: the under tier's far side in the 3/4 front-left close-up at rest. A thin sheet's rim seen along its length cannot be a round arc.
  - `sleeve_cuff` × `sleeve_balloon`: 92 / 88 / 130 / 520 pairs in arms_forward / reach_forward / wrist_twist_pos / _neg. This is the upper tier's root inside the bag's hem, unchanged since the HD fix and not visible.

**HD verify (round 3): the thorn**
- The independent 4× verification of round 2 found one pointed tip left of the owner's p1 (`cuff_verify3.jpg`; "before" there is round 2, 6880e88, merged into r11/integrate):
  - In the owner's q34_front_left view (left hand) and in q34_front_right (right hand): a small thorn at the cuff's edge, about 10 × 5 px at 4×, a `<` in cel and a thin cone in clay.
  - In reach_forward, a horn on the outer side of the wrist. From the palm side, hooked points.
  - The verifier put the thorn down to the under tier's rim, whose roll round 2 had doubled, curling into a J.
- Diagnosis (4× crops of the owner's views, then close-ups of the spot with per-tier id colours, with the under tier hidden, and wire):
  - The thorn belongs to the upper tier (`sleeve_cuff`). With the under tier hidden it stays, and shows as a long fin: the upper tier's outer face, rim bead and inner face. The under tier's J is the curl in front of the fin. It hides the fin's root, so only the pointed end shows. Lowering only the under tier's roll (2.0 → 1.4 → 1.0) left the thorn as it was.
  - The fin is one flute crest at the silhouette, seen from below and in front. The crest ran at full depth (about 5 px out) all the way to the rim, where the rim bead turned it in one corner.
  - The roll that makes the lobes read as loops from the front tilts the rim across each crest. At an oblique view, about atan(roll × flutes / radius) ≈ 30° off side-on, that loop collapses into a cusp. The owner's 3/4 views are close to that angle for the flute on the cuff's inner-front side.
  - The roll stays. With 0.5 or 0.8 px instead of 1.8, the front view went back to straight flat plates with pointed ends: the owner's round-1 complaint.
- Fix (`levi/parts/sleeves.py` only):
  - `CUFF_RIM_EASE`: each tier's flutes lose part of their depth (and their rise and rounding) over the last px before its rim: the upper tier 70% over 10 px, the under tier 60% over 6 px. The crest turns in under a belly above the rim, so a flute seen side-on or obliquely ends in a round nose. The rim's loop is also rounder, as its depth comes closer to the roll.
  - The upper tier's belly has two more rings, at d 16.6 and 20.0 px (Catmull-Rom of their neighbours). With the inward turn on the old stations, the crest line bent at one ring (d 18.5), and the stub moved up there.
  - The upper tier's rim bead is fuller: about 2 px across and 1.8 px past the last outer station (was 1.4 px).
  - `CUFF_CURL` 0.02 → 0: the crests no longer turn outward at the upper rim. That kick re-sharpened the nose.
  - `CUFF_UNDER_FREE`: the under tier's doubled roll in its hanging part (round 2) goes back to the plain roll. With the rim ease its lobes still end in curls, without the hooks.
  - Faces: sleeves 17,032 → 17,752 (three more rings on the upper tier).
- Measure: a silhouette-corner count. Each tier alone is projected along 300 directions over the sphere at 4× (4 px per panel px). Along the silhouette contour, the metric takes the turn over ±4 px of arc. A round arc of radius r px turns 8 / r rad: 76° for a 1.5 panel px radius, 176° for the end of the old ~0.7 px bead. Corners at the tier's root (inside the bag) are left out.

  | sharpest silhouette corner, 300 views | round 2 (6880e88) | now |
  |---|---|---|
  | upper tier: views with a corner > 120° / > 150° | 119 / 31 | 13 / 0 |
  | upper tier: median / 90th percentile of the views' sharpest corner | 115° / 150° | 89° / 113° |
  | under tier: views > 120° / > 150° | 127 / 13 | 23 / 1 |
  | under tier: median / 90th percentile | 116° / 145° | 86° / 116° |
  | upper tier, the owner's q34_front_left direction | 151° | 120° |

- Results on r11/integrate (`cuff_verify3.jpg`):
  - q34_front_left and q34_front_right (4×, cel and clay): the thorns are gone on both hands. The spot shows a small round tab.
  - Close-up of the spot: the upper tier alone ends in a round nose instead of a long fin. With both tiers, a rounded nub shows beside the under tier's curl.
  - reach_forward from the outer side: the horn (a hooked lobe top) is a rounded lobe top.
  - From the palm side and in the 4× low views, the lobe ends are rounder, without hooked points.
  - The owner's 4× front crops keep the rolled loops. The side, back, high and 3/4 back crops read as before, with softer lobe ends.
- Remaining:
  - End-on, the scallops at the rims are shallower than round 2's (the rim ease). The flutes stay full above the rims.
  - In the q34_front_left cel crop, the upper tier's nose shows a short closed outline where its inner face shows under the rim bead (about 12 × 5 px at 4×). It is not a point.
  - A rim seen exactly along its length still shows the ~2 mm bead's width. The metric's remaining > 120° views are those, at rounded drops of the under tier and at small notches.

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

  | object | share (second pass) | share (HD fix, verify round 2) | share (verify round 3) |
  |---|---|---|---|
  | `sleeve_ruffle` | 0.5 | 0.5 | 0.5 |
  | `sleeve_cuff` | 0.625 | 1/3 | 1/4 |
  | `sleeve_ribbon` | 0.5 | 0.5 | 0.5 |
  | `sleeve_cuff_under` | 0 (left out) | 0.1 | 0.1 |

  These are about round 10's densities. Each share's period divides each half's vertex count, so both sides thin alike. The HD fix's bell-shaped tiers keep more of their vertices more than 5 cm off the arm bones; at the second pass's shares they put the drape root 8.2 mm down the forearm from round 10's (joints 6.4 / 3.3 mm off), so the shares were refitted with an offline replica of the fit (checked against the built rig). Verify round 3's three more upper-tier rings at 1/3 put the root 4 mm further down the forearm again (r11/integrate: (0.2241, −0.0315, 0.9067)); at 1/4 the replica and the built rig agree within 0.5 mm.
- Results against round 10:

  | | round 10 | first pass | second pass | HD fix | verify round 2 | verify round 3 |
  |---|---|---|---|---|---|---|
  | `袖_0.L` root | (0.2202, −0.0313, 0.9103) | (0.2369, −0.032, 0.8951) | 3.4 mm off | (0.2217, −0.0314, 0.9090), 2.0 mm off | (0.2218, −0.0314, 0.9088), 2.2 mm off | (0.2220, −0.0314, 0.9086), 2.5 mm off |
  | joint 1 | (0.2407, −0.0363, 0.8340) | — | 1.4 mm off | (0.2424, −0.0336, 0.8331), 3.3 mm off | (0.2396, −0.0334, 0.8347), 3.2 mm off | (0.2407, −0.0345, 0.8327), 2.2 mm off |
  | joint 2 | (0.2913, −0.0370, 0.7746) | — | 4.2 mm off | (0.2893, −0.0354, 0.7762), 3.0 mm off | (0.2891, −0.0366, 0.7763), 2.8 mm off | (0.2903, −0.0358, 0.7756), 1.9 mm off |

  The under tier keeps its share (0.1): reshaped, it moved the chain by at most 0.4 mm.

  | capsule | round 10 | first pass | second pass | HD fix | verify round 2 | verify round 3 |
  |---|---|---|---|---|---|---|
  | shoulder | r 5.1, 0.0–8.6 cm | r 5.1, 2.1–9.0 | r 5.0, 0.0–9.0 | r 5.0, 0.0–9.0 | r 5.0, 0.0–9.0 | r 5.0, 0.0–9.0 |
  | upper arm | r 4.5, 4.4–15.9 | r 4.3, 6.8–15.1 | r 4.3, 5.1–15.7 | r 4.3, 5.1–15.7 | r 4.3, 5.1–15.7 | r 4.3, 5.1–15.7 |
  | forearm | r 5.2 | r 4.9 | r 5.2 | r 5.3, 0.0–20.9 | r 5.4, 0.0–20.9 | r 5.5, 0.0–20.9 |
  | hand | r 2.4, 0.8–6.0 | r 2.9, 0.1–6.0 | r 2.2, 0.8–6.0 | r 2.3, 0.8–6.0 | r 2.4, 0.8–6.0 | r 2.4, 0.8–6.0 |

  These are on r11/base with this branch. On r11/integrate (its own body and hands) the capsules are unchanged from round 2 except the forearm, r 5.1 → 5.2 cm.

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
  | `sleeve_cuff` | 3,840 (verify round 2: 3,120) |
  | `sleeve_ribbon` | 2,848 |

- Every sleeve object carries `levi_sleeve_s` and `levi_sleeve_param`.
- The ribbon keeps `levi_sleeve_tails`.
- The cuff tiers and the ribbon set `levi_cast_shadow = False`.

## Results

### Gates
All on r11/base with this branch (verify round 3).
- `tools/check.py`: CHECK OK, determinism included. Sleeves 17,752 faces of 18,000, model 117,056.
- `tools/rig_check.py`: RIG CHECK OK on all 17 core poses. The worst stretch is unchanged (fist 1.86, squat 1.85), and so is the worst penetration (side_bend 1.76 cm, skirt). Sleeve penetration is within 0.2 mm of round 10:

  | pose | round 10 | first pass | second pass | verify round 2 | now |
  |---|---|---|---|---|---|
  | arms_up | 0.60 cm | 0.73 | 0.62 | 0.61 | 0.62 |
  | arms_forward | 0.44 cm | 0.58 | 0.47 | 0.45 | 0.46 |
  | raise_bend | 0.58 cm | 0.63 | 0.59 | 0.59 | 0.59 |

  Every other pose is identical to round 10.
- On r11/integrate with this branch (before = round 2, 6880e88): check OK (sleeves 17,752, model 152,144); rig_check OK, every row as before except arms_up pen 0.61 → 0.62 cm. The cuff tiers pass through themselves in none of rest, arms_up, arms_forward, reach_forward, hands_on_hips, wrist_twist_pos / _neg, raise_bend, hug_self and dance_point; upper × under tier pairs are 0 in all of them (round 2: 32 in wrist_twist_pos). The under tier stays 4.5 mm off the hand at rest and 3.2 mm in hands_on_hips (round 2: 4.5 / 3.1 mm).

### Motion
Command: `rig_check --quick --no-core --extended --report-core --motion`. The baseline is built from r11/base.

**All parts: 152 major / 332 minor (round 10) → 160 / 325 (second pass: 160 / 326; first pass: 162 / 331).** The HD fix adds no major and removes none against the second pass. Verify round 2, counted from the report's issue list (round 10 / HD fix / now): 152 / 327, 160 / 320, 160 / 317. No major added or removed.
- `hair_curtain_R` is at round 10's values (dance_sway pen 3 mm, pen_frac 0; idol_dance 6 mm, 0.007); the first pass had 10 and 12 mm.
- `look_over_shoulder` hair × garment crossings: 379 → 448 (first pass: 475). Other crossing counts (already major on round 10) moved by under 10%, walk 1,387 → 1,515 the most. These counts rise with the garment triangle count near the hair.

Verify round 3 (r11/base): all parts 160 major / 317 minor and sleeves 16 / 63, the same counts as round 2. On r11/integrate, round 2 → now: all parts 164 / 349 → 163 / 349, sleeves 18 / 63 → 17 / 64: the verifier's one new major, `sleeve_cuff_under` pen_frac in dance_clap (0.031), is minor again (0.028). The changes against round 2 (r11/base):
- `sleeve_cuff` goes in less deep where the hands press on the body (dance_point 2.5 → 2.1 cm, hug_self 3.1 → 2.8 cm, idol_dance 5.3 → 5.0 cm, hand_to_shoulder 1.5 → 1.1 cm) with a slightly larger share of its vertices (dance_point 0.066 → 0.075, hug_self 0.117 → 0.126, idol_dance 0.160 → 0.164). The fuller rim bead adds vertices near the hand; all were majors before.
- `sleeve_cuff_under`: dance_point 2.3 → 2.2 cm, idol_dance 4.7 → 4.4 cm, hug_self pen_frac 0.136 → 0.132.
- Flips in idol_dance: balloon 50 → 54, ribbon 27 → 42 (both minor; round 10: 52 / 28, the HD fix 54 / 42). The thin ribbon tails are sensitive to the drape fit, which moved 0.3 mm.
- `hair_curtain_R` and every other part are unchanged.

**Sleeves: 9 major / 70 minor → 16 major / 66 minor (second pass: 16 / 67); verify round 2 and 3: 16 / 63.**
- 6 of the 7 majors new against round 10 are `sleeve_cuff_under`, a new object, in the poses where the cuff was already major on round 10, with the hand pressed to the body:

  | pose | under tier pen / pen_frac (second pass → HD fix → verify round 2) | round-10 cuff |
  |---|---|---|
  | dance_point | 2.85 cm / 0.055 → 2.82 / 0.061 → 2.3 / 0.070 | 2.54 / 0.069 |
  | hug_self | 3.09 / 0.108 → 3.09 / 0.112 → 2.6 / 0.136 | 2.81 / 0.124 |
  | idol_dance | 5.28 / 0.150 → 4.95 / 0.145 → 4.7 / 0.146 | 5.35 / 0.162 |

  Verify round 2: the longer under tier goes in less deep but with more of its vertices; dance_clap pen_frac 0.016 → 0.022 (minor), hand_to_shoulder 0.016 → 0.009, hands_behind_back pen gone.

- The 7th: `sleeve_cuff` pen_frac in hands_behind_back: round 10 0.026, second pass 0.046, now 0.042 (depth 1.6 cm, minor).
- The upper cuff in the same poses: dance_point 2.8 → 2.5 cm (pen_frac 0.064 → 0.066), idol_dance 5.4 → 5.3 cm.
- Flips:

  | pose | balloon (round 10 → first pass → HD fix → verify round 2) | ribbon (round 10 → first pass → HD fix → verify round 2) |
  |---|---|---|
  | idol_dance | 52 → 64 → 54 → 50 | 28 → 62 → 42 → 27 |
  | reach_up_back | 11 → 18 → 12 → 12 | 2 → 13 → 8 → below minor |
  | dance_sway | 14 → 15 → 14 → 14 | 8 → 19 → 9 → below minor |

  The ribbon rows are minor (dance_sway now below the minor threshold). The thinner tails fold more readily than round 10's.
- Frill: seiza pen_frac 0.012 → 0.029 (minor). Everything else is unchanged or lower.

### Look
- Silhouette IoU is unchanged: front 0.9085, side 0.8331, back 0.9126 (second pass: 0.9125). Verify round 2: 0.9089, 0.8331, 0.9129. Verify round 3: 0.9091, 0.8331, 0.9131.
- Green region IoU:

  | view | round 10 | now |
  |---|---|---|
  | front | 0.391 | 0.401 |
  | side | 0.306 | 0.321 |
  | back | 0.252 | 0.244 |

- Dress region IoU (the cuff is in it) moved by under 0.002: front 0.7599 → 0.7596, back 0.6297 → 0.6286. Verify round 2: 0.7600, side 0.6538, back 0.6297; green unchanged. Verify round 3: front 0.7615, side 0.6536, back 0.6308; green unchanged (0.401 / 0.321 / 0.244).

- Shape-master fit for sleeves:

  | | round 10 | now |
  |---|---|---|
  | target→ours p50 / p90 | 9.4 / 23.7 mm | 9.1 / 23.6 mm |
  | covered | 0.307 | 0.317 |

- Remaining and seen:
  - A small dark tick on the frill's rolled rim at one valley, at macro scale. It is shading by the soft normals. Own normals there made a wider dark band.
  - At panel scale the front view of the wrist ruffle now reads as a soft rolled puff (`panels.jpg`), not the flat plates the second review noted (its p3).
  - End-on the cuff is 10 round scallops; in cel the valleys between them still show the background through small closed notches, as the sheet's two-tier ruffle does. Since verify round 3 the scallops at the rims are shallower (the rim ease).

### Not run
- `export_pmx.py`, `pmx_reimport.py` and `motion_vmd.py`: mmd_tools is not installed on the cluster Blender. The sleeve morphs on the new objects and the PMX physics fit of the sleeve drapes are unverified.
- No Codex review was run.

## Images
- `frill.jpg`: round 10 | first pass | second pass (the frill is unchanged since).
  - Band side and band front (cel).
  - The rim's outer side (wire).
  - The frill's inner side in arms_up (cel, clay).
- `cuff_hd.jpg`: the HD review fix, before (the owner's state) | after, 4× crops of the dressed model (r11/integrate with this branch): the owner's front crop in cel and clay, the left hand from the front, from 30° above, 3/4 back-left, and arms_up, arms_forward and reach_forward (clay).
- `cuff_verify.jpg`: verify round 2, before (the HD fix) | after, on r11/integrate with this branch. Rows:
  - 4× high view of the right wrist, zoomed (clay, cel): the fang;
  - palm-side close-up (clay, cel): the tongues;
  - end-on close-ups at rest and in arms_up (clay): the crescents inside the bell;
  - the owner's 4× front crop (cel).
- `cuff_verify3.jpg`: verify round 3, before (round 2, 6880e88) | after, on r11/integrate with this branch. Rows:
  - the owner's q34_front_left view (left hand) and q34_front_right (right hand) at 4×, zoomed, cel and clay: the thorn;
  - the same spot in close-up: the upper tier alone (id colours) and both tiers (clay);
  - reach_forward from the left cuff's outer side (clay, cel): the horn;
  - the palm side and the 4× low view (clay): hooked lobe ends;
  - the owner's 4× front crops (cel): the rolled loops are kept.
- `cuff_hd.jpg` and `cuff_verify.jpg` were downscaled in verify round 3 to keep this folder near 1.3 MB.
- `rig_fit.jpg`: the elbow inside the bag in dance_sway, reach_up_back and hands_behind_head (3/4 cel crops).
- `bow.jpg`: the bow from above and from 3/4 (cel).
- `panels.jpg`: sheet | round 10 | first pass | now, at panel scale, enlarged. Rows: band front and side, wrist front and side.
