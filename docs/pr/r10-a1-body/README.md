# R10-A1: body follows the shape master

`levi/parts/body.py` only. Each section function samples `levi/shape.py` (label `body`)
along its own ring directions and blends toward it by a reliability weight; topology,
loops, attributes and rig contracts are unchanged (7417 faces, same as main).

## What follows the master
- **Legs below the petticoat** (`leg_offset`, so `shoes.py` sees the same surface): per
  ring the radial delta to the master is fitted by a low-order Fourier series (order 1 =
  axis shift, order 2 = width / depth), smoothed along the leg (sigma 14 px). Our anatomy
  (kneecap, calf, tendon, malleoli) stays. Net effect: the shins and calves sit ~4 px
  (6 mm) nearer the midline and a little forward, the calf ~1-2 px slimmer. The correction
  of the first full row (628) is held up the hidden thigh and fades out by row 470, so the
  thigh runs into the knee without a waist at the hem; it fades out above the shoe
  ribbons (755-805), because `shoes.py` ties its laces to the plain `LEG_FRONT` /
  `LEG_SIDE` ellipses there.
- **Neck, shoulders, upper chest** (`build_torso`, so the halter in `accessories` follows):
  front and sides only, rows 163-232, not on the shoulder socket border.
- **Shoulder cap** (`arm_rings`): the first round arm rings (arc <= 50 px, fading by 75),
  above the sleeve band; the transition rings follow.
- **Hands, volume only**: the master's mitten hands are turned against ours, so palm width,
  palm thickness and finger thickness are measured in the master's own principal frame
  and take half the ratio, capped at +-15%: palm width x0.93, palm thickness x1.12,
  finger depth x1.15 (finger and thumb width and spacing follow the palm width). Five
  separate finger islands and our finger topology are kept.
- `LEVI_BODY_MASTER=0` builds round 9's body exactly (used for the motion baseline).

## Kept procedural (deliberately)
- **Knee**: `knee_joint()`, `KNEE_FWD`, `KNEECAP`, `KNEE_ROW` and the knee rig are as on
  main (R10-K owns the knee). The knee band takes only the low-order correction above;
  the pivot is not moved (the shift there is sideways, along the hinge axis, ~2 mm forward).
- **Thighs under the petticoat**: the master's thighs inside the skirt are partial and
  lumpy (front and back missing, cloth-fused patches); following them made bulky
  "jodhpur" thighs. Stays inside the master's skirt / petticoat (clearance clamp, 0 hits).
- **Torso under the bodice, the bust**: the master's bust stands ~1 cm proud of ours at the
  bodice's top edge; following it pushed a ridge across the chest and skin through the
  neckline. The back is under the hair (stray samples made a knob).
- **Arms inside the sleeves**: the master's skin there is stray (cuff ruffles and ribbons
  labelled body); following it pushed the upper arm through the sleeve band.
- **Ankle and foot** (laces contract), the hand's shape and orientation.

## Rejected first version
Following the master ring by ring (smoothed 2.5 samples x 5 rows, knee included) lost the
order-balanced pairwise A/B **2-22 (astra) and 0-20 (sol)**: "wavy lower legs", "kinked
knee", "narrowing above the calves" (`pairwise_ringfit_rejected.md`). Volume and smooth
transitions win; the master's relief does not survive on our 28-vertex rings.

## Pairwise A/B (final shape, `pairwise.md`, script `ab.py` / `ab_pairs.py`)
Order-balanced (each pair shown in both orders, only consistent picks count), 32 items:
rest cel + clay crops (legs front / side / back / q34, chest front / q34 / side, hand) and
8 poses (walk, squat, seiza, high_kick, sit_chair, deep_lunge, arms_up, cross_legged).

| model | new | old | tie |
|---|---|---|---|
| gpt-6-astra | 14 | 2 | 16 |
| gpt-6.1-sol | 23 | 2 | 7 |

The A/B ran on the version before the code-review fixes; the only geometric change since is
the thumb taking the same width / depth scale as the fingers (`build_fingers`).

## Fit (`tools/shape_fit.py --parts body`, target->ours p50 / p90 / p99 mm, covered)
| | p50 | p90 | p99 | covered |
|---|---|---|---|---|
| main (round 9) | 8.6 | 24.2 | 37.3 | 0.312 |
| this PR | 6.9 | 23.6 | 36.9 | 0.402 |

On the exposed shins (rows 620-790) the target->ours median went from ~2-8 mm to ~1 mm.
p90 is held up by target samples this part should not follow: ~20% of the `body` samples
are the master's thighs and hips inside the skirt, ~15% are sleeve-cuff ruffles and
ribbons labelled body round the forearm, the hands are turned ~70 deg against ours, and
the shoe ribbons at the ankle are labelled body.

## Gates
- `tools/check.py`: CHECK OK (body 7417 faces, total 107968).
- `tools/rig_check.py`: RIG CHECK OK, all 17 core poses (`final_core_gate.txt`).
- `export_pmx.py` + `tools/pmx_reimport.py`: REIMPORT OK (VMD round trip 0.00 mm).
- Rest-pose penetration of every garment into the skin: same as main (sleeves 10 verts
  > 1 mm, max 2.3 mm; bodice / accessories 0).

## Motion (`motion_delta.md`, base = main, new = this PR; extended + core + clips)
- `body`: 5 / 47 -> 5 / 46 (major / minor); no worse level on any body row except
  `spin` stretch ok -> minor 1.64 (腕捩.R, the forearm twist band; min-threshold 1.6).
  Fewer body rows in the extended poses (dance_clap and deep_lunge compress gone); the
  clips' body rows keep their levels with values within a few percent.
- All parts: 115 / 399 -> 121 / 391. New majors are all just past a threshold:
  `dance_sway` shoulder.L volume 0.659 -> 0.649 (major below 0.65), `cross_legged` /
  `spin` petticoat stretch 2.00 -> 2.02 / 2.15 (major from 2.0; the drape tables follow
  the moved legs), `reach_up_back` side-hair pen_frac 0.029 -> 0.032 / 0.050 (major from
  0.03), `look_over_shoulder` back-hair pen 19.1 -> 20.2 mm. Two majors gone
  (`jump_tuck` petticoat stretch, `walk` hair x garment crossings).
- The full motion run died twice in one process after `dance_heart` on a loaded machine;
  the report was run as two processes (extended + core, clips), same poses and clips.

## Three-view IoU (report only)
Whole silhouette -0.005 / -0.005 / -0.006 (front / side / back). Skin region -0.037 /
-0.032 / -0.049: the master puts the shins nearer the midline and further forward than
the sheet, so the shape master and the sheet disagree there by ~4 px.
