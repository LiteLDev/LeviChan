# r11 petticoat: three tiers of scalloped bells

Branch `r11/petticoat`, built on `r11/base`. Only `levi/parts/petticoat.py` changes geometry.
The petticoat-specific parts of `levi/rig.py` change, and `tools/motion_check.py` gets one
new count.

## What it is now
- **Three tiers plus a gathered core.** Petticoat: 25,920 faces (budget 28,000; round 10 had
  12,000). Model total: 121,888.
- **Shared layout.** All three tiers have 96 lobes at the same azimuths. The lobes are
  grouped into bells of 3-4, about 7 cm wide, so the bells of the three tiers stack in
  clusters, as on the sheet.
- **The bell is the main form.**
  - Each bell is a puffed tube carved inward from the band. The crests sit on the band and
    the pinches go 2 x 8-9 px inside it, with a pinch radius of about 5 mm.
  - The mouth flares, and the pinch between two bells rises 9-11 px.
  - Each bell's mouth is levelled to its own mean height. A sloping hem becomes a staircase
    of level mouths instead of a row of tilted tongues.
- **Lobes.** Each lobe is a soft puff across, with a round scallop whose notch is blurred.
  At a pinch, the lobe notch gives way to the bell's own rise.
- **Rolled hem.** Its frame is averaged over ±2 samples and turned toward the body axis.
  The return runs back up inside, but never past the last band segment.
- **Hanging, not slanted.**
  - The band flares just under the seam, inside the skirt, and hangs straight where it
    shows (`HANG_POW`). The outer tier's top ring is at 0.95 of its hem outline.
  - Under the front and back lift, the bells are shallower and the inner tiers tuck behind
    the outer one. Seen from the side, the frill ends no longer fan out into feathers.
- **Clearance.**
  - The clamp is measured at the gathered points' own height.
  - A nearest-point pass then keeps about 4 mm in 3D from the skirt and from the tiers
    around.
  - Rest gaps: tier0 to skirt 4.7 mm (4.1 mm with r11/skirt merged), tier to tier
    2.7-4 mm (round 11 first try: 0.67 mm). The legs are more than 8.7 cm away.

## Rig (`levi/rig.py`, petticoat-specific sections)
- **`LAYER_PARTS`: tiers share weights with their neighbours.**
  - Each tier is first smoothed on its own. Then its weights are blended toward the other
    tiers' weights at their 6 nearest vertices within 1.2 cm, weighted by
    (1 - d/r)^2, in two passes. The change is smoothed along the tier over 2 cm.
  - The core keeps its own weights. When it was shared too, its sparse pruned rings
    carried their steps into tier1's seam.
  - Tried and dropped: one angle x height weight field for every petticoat object. It
    mixed 5-6 chain bones round the hips and stretched the core x4-5 in high_kick.
- **`DRAPE_GRID` now 5 mm, on petticoat points only.**
  - The skirt chains and the drape see the petticoat thinned to a 5 mm grid, about as
    many points as round 10's petticoat had (12.9k). The skirt's points are taken as
    they are.
  - The first try thinned skirt and petticoat together to a 12 mm grid.
  - Chain joints are within 13 mm of round 10's (first try: 19 mm).

## tools/motion_check.py
- Adds `tier0` / `tier1` / `tier2` crossing groups, so tier-x-tier crossings show up in
  the motion report.

## Gates (full model, this branch)
- `check.py`: CHECK OK.
- `rig_check.py`: RIG CHECK OK on the 17 core poses.
  - The worst stretch is unchanged: fist 1.86, squat 1.85 (both on the body).
  - Walk 1.74 (round 10: 1.74). The worst penetration is unchanged: side_bend 1.76 cm, on
    the skirt.
  - No backward knee; 66/66 PMX bone names.
- Not run: `export_pmx`, `pmx_reimport` and `motion_vmd`. mmd_tools is not installed on
  the cluster.

## Motion report vs round 10 (`motion_petticoat.txt`, `motion_skirt.txt`)

### Petticoat: better than round 10
| pose | stretch, round 10 → now |
|---|---|
| sit_chair | 2.03 → 1.81 |
| high_kick | 2.17 → 2.05 |
| lie_back_elbows | 2.25 → 2.15 |
| jump_tuck | 2.06 → 1.92 |
| run_r | 2.17 → 1.95 |
| run (clip) | 2.30 → 1.98 |
| sit_stand (clip) | 2.03 → 1.82 |

- The core stays at or below round 10's stretch: high_kick 2.0, cross_legged 2.1,
  lie_back 1.9.
- No flips, except cross_legged 6 (round 10: 3; first try: 8). The first try's new
  back-hem flips (high_kick 17, kneel_one 13, deep_lunge 12, run_r 10) are gone.

### Petticoat: still worse than round 10
| metric | round 10 | first try | now |
|---|---|---|---|
| cross_legged stretch | 2.18 | 2.75 | 2.26 |
| run_l stretch | 1.78 | 1.90 | 1.88 |
| high_kick penetration (core, スカート10_0) | 0.83 cm | 1.26 cm | 1.54 cm |
| run clip penetration (inner tiers, front, frames 4-5) | 0.49 cm | 0.71 cm | 1.11 cm |
| lie_back penetration | 0.54 cm | 1.08 cm | 0.95 cm |

All of these are below 2 cm.

### Tier x tier crossings (BVH face pairs)
| pose | first try | now |
|---|---|---|
| high_kick | 66 | 0 |
| deep_lunge | 50 | 0 |
| kneel_one | 44 | 0 |
| run_l | 33 | 0 |
| cross_legged | 291 | 51 |

- The motion report's new metric counts 84 in cross_legged, 7 in run_r and 4 in the run
  clip.
- Skirt x petticoat in cross_legged: 212 (round 10: 214).

### Skirt
The skirt moves only because its chain fit sees the new petticoat.
- Better: sit_chair 2.16 → 2.00, lie_back 2.64 → 2.35, jump_tuck flips 32 → 10, run_l
  penetration 1.22 → 0.91 cm.
- Worse: torso_left / right 1.33 / 1.38 → 1.49 / 1.62, twist_bend 1.37 → 1.60,
  high_kick 1.90 → 2.16.
- In the variants tried, these twist values moved ±0.15 with every chain fit.

## Rest geometry
- No self-intersections.
- No dihedral over 105° outside the rolled hem: 3 edges on tier2, at most 140°. The first
  try had 41-69 edges per tier at 130-144°.

## Sheet metrics (reported, not chased; `metrics_delta_petticoat.txt`)
- **Petticoat IoU** fell a little against round 10, because the bells' crests now sit on
  the measured outline instead of 2 cm outside it. Front 0.293 → 0.279, side
  0.269 → 0.225, back 0.226 → 0.207.
- **Whole-model IoU**: 0.907 / 0.831 / 0.911, down 0.002-0.003 against round 10.
- **Petticoat shade islands**, round 10 → now:

| view | round 10 | now |
|---|---|---|
| front | 1/69 | 0/0 |
| side | 1/55 | 2/134 |
| back | 1/71 | 0/0 |
| q34_front_left | 4/169 | 1/40 |
| q34_back_right | 1/36 | 3/221 |
| high | 1/54 | 0/0 |

  The first try had 9/256 islands in the side view.

## Images
- `ortho_sheet_base_prev_new.jpg`: the sheet, round 10, round 11's first try and this
  branch (panel crops).
- `side_ends_12cm.jpg`, `side_ends_12cm_clay.jpg`: the side view's front and back ends at
  12 cm.
- `notch_macro.jpg`, `wire_q34z.jpg`: the 12 cm 3/4 view and the 5 cm macro. No thorns;
  the scallops are rounded.
- `poses_cel.jpg`: deep_lunge front, high_kick back, cross_legged lap, sit_chair from
  below.
- `below_q34_cel.jpg`: the view from below and the 3/4 view.
