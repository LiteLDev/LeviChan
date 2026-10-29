# r11 / body-torso: neck, collarbones, upper chest, back and elbow

风堇 has no torso, shoulders, elbows or forearms, so Levi's upper body stays procedural. This
branch fixes the defects the round-11 analysis found there. It also adds the anatomy that the
strapless dress shows, kept soft enough that the cel ramp draws at most one clean
terminator per form. Only `levi/parts/body.py` changes.

## What changed

- **Upper chest without the ridge.**
  - Round 10's exposed chest stayed flat down to row 230. It then stepped 18 px forward in
    5 rows into the bust fill under the neckline, which left a horizontal ridge at the
    bodice's top edge.
  - Each front column is now faired with one cubic Hermite from row 203 to the neckline ring
    (`UPPER_CHEST`). The curve runs through the rings' own values, so the bodice fit at the
    neckline is kept.
  - The fairing fades out over 4 steps beside the socket (`UPPER_CHEST_EDGE`).
  - The cleavage is a shallow valley about 5 px deep (`BUST_PUSH` centre share) instead of
    a 7 px groove.
- **Anatomy relief** (`_torso_relief`).
  - It is applied along the surface normal after the shape master, which would otherwise
    flatten it, and fades out over the socket border.
  - Front: the collarbones, rising a little toward the shoulder; the hollow above them,
    which turns round 10's flat shoulder ledge into a slope; the notch at the base of the
    neck; and the two neck tendons running up from it.
  - Back (under the hair): the trapezius thickening the base of the neck at the back-sides,
    a shallow spine groove and soft shoulder-blade plates.
- **Denser front rings.**
  - The rings from the neck down to row 256 split the middle four steps of their front arc
    (`TORSO_DENSE`, `TORSO_DENSE_KEEP`), giving 36 vertices instead of 32. The notch, the
    tendons and the inner collarbones are sampled about every 1 cm.
  - The back, the socket arcs and the three steps beside each socket edge keep round 10's
    spacing. The rig smooths weights along the mesh graph, so a denser patch beside the
    shoulder shifted the shrug and stage weights. Variants that split more of the ring
    stretched the back armpit to x2.25 (arms_up) and x2.05–2.13 (dance_sway, idol_dance).
  - The band between rows 256 and 266, hidden under the bodice, joins each pair of dense
    segments to the plain ring with a quad and a triangle.
  - Every ring from row 266 down (waist and pelvis) is identical to round 10.
  - The 24-vertex socket border, `cut_socket`, `SOCKET_ROWS` and `levi_socket_s` are
    unchanged: 48 border vertices at 0, the same as before.
- **Neck.**
  - Two more rings, at rows 154.5 and 165.5.
  - The tilt toward the jaw now fades out linearly to row 178. Round 10 tilted the rings
    fully down to row 161 and not at all from 170, which left a 25 px gap at the nape.
- **Elbow.**
  - The loft's centre line is rounded over ±8 px (`ELBOW_FILLET`) instead of mitring at
    `ELBOW`.
  - The rings carry the olecranon, the two epicondyles and a soft crook (`ELBOW_BUMPS`).
  - A 16 px fillet was rounder at rest, but it spread the bent elbow: the elbow span in
    hands_behind_head went from 1.16 to 1.35, against 1.21 with 8 px.

## Gates (cluster, Blender 5.2.3)

| | r11/base | this branch |
|---|---|---|
| check.py | OK, body 7,417 | OK, body 7,569 / 24,000 (total 108,120) |
| rig_check (17 core, repeat build) | OK | OK (`final_core_gate.txt`) |
| arms_up / fist / side_bend, worst stretch | x1.78 / 1.86 / 1.47 | x1.77 / 1.86 / 1.46 |
| arms_forward / head_left, pen cm | 0.44 / 0.21 | 0.48 / 0.26 |
| rig joints | | elbow 1.4 mm out, the others unchanged |
| IoU front / side / back | 0.9090 / 0.8331 / 0.9132 | 0.9090 / 0.8334 / 0.9132 |
| skin region IoU front / side | 0.744 / 0.612 | 0.744 / 0.611 |
| shade islands q34_front_left, skin | 11 | 10 |
| shape_fit body p50 / p90 | 6.9 / 23.6 mm | 6.9 / 23.6 mm (covered +0.002) |
| bodice shell inside the body at rest | 5 verts, 0.85 mm | 3 verts, 0.21 mm |
| clearance p5: bodice / choker / halter | 1.73 / 0.61 / 0.98 mm | 1.71 / 0.60 / 0.87 mm |
| body: open or non-manifold edges, loose parts, median edge | 0, 15, 9.35 mm | 0, 15, 9.35 mm |

## Motion report

`rig_check.py -- --quick --no-core --extended --report-core --motion`, compared with the
r11/base report. The full report is in `final_motion_report.md`.

- **Issue counts.**
  - body 66 major / 88 minor, unchanged.
  - hair/garment minor 13 → 16: new crossings of 41–58 in forward_bend, raise_bend and
    hug_self. The halter follows the fuller chest.
  - hair_front minor 25 → 27.
  - sleeves minor 70 → 71: the cuff in hand_to_shoulder goes 1.46 → 1.76 cm into the
    shoulder.
  - Every other part is unchanged.
- **Better.**
  - torso_left / right: compress 0.82 → 0.94, stretch 1.19 → 1.10.
  - Compress: arms_up 0.52 → 0.56, reach_up_back 0.48 → 0.53, dance_heart 0.42 → 0.46.
  - idol_dance: the chest × upper-arm contact is gone, and the body stretch is 1.92 → 1.89.
- **Worse, all below the major level.**
  - Elbow span: +0.02–0.05 in most bent poses, and 1.17 → 1.29 in hand_to_shoulder. The
    elbow-point bumps account for most of it; with bumps alone the span is about the same as
    with the 8 px fillet. The posed close-ups show an equal or cleaner fold.
  - Neck (首): look_over_shoulder stretch 1.49 → 1.59 (minor is 1.60); head_left / right
    1.31 → 1.35, compress 0.81 → 0.75. These come from the denser, evenly tilted neck rings.
  - Halter (accessories): idol_dance@78 stretch 1.64 → 1.91, which is minor in both. It is
    1.38 → 1.45 in reach_up_back. The strap takes its weights from the reshaped lateral
    upper chest.

## Neck contract for the head part

The body's neck is the visible neck. Its rings, from the bottom of `TORSO_ROWS`, sit round the
axis x = 0, y = −30.5 px (−47.4 mm):

| front row | z (m) | radius (px / mm) |
|---|---|---|
| 148 (top, capped) | 1.249 | 12.5 / 19.4 |
| 154.5 | 1.239 | 13.0 / 20.2 |
| 161–170 | 1.229–1.215 | 13.5 / 21.0 (front y −44, back −17) |
| 175 | 1.207 | 13.4–15.6 (trapezius at the back-sides) |
| 178 | 1.202 | 14.5–16.4 |

The rings rise toward the back by 0.6 × (depth behind the front) × (178 − row) / 30. Ring
161 therefore spans rows 151.8 (back) to 161 (front).

The face's neck end must stay inside a radius of 12.5 px (19 mm) about that axis from row
158 to row 176. That is at least 1 px inside the body, and the body's outline hull adds
another 1.25 px. Round 10's head neck (14.8 px at row 174) is outside it.

## Sheets

- `chest_rest.jpg`: the upper chest from the front, at 3/4, from above and from below.
  Columns are r10 clay, r11 clay, r11 wire and r11 cel with the clothes.
- `neck_clavicles.jpg`: the sheet's collarbones and notch, then the notch and the
  collarbones from above, and the neck at 3/4.
- `elbow.jpg`: the rest elbow from the side, front and back, then the elbow bent 120° in
  arms_forward.
- `poses.jpg`: the upper chest in arms_up, the back in hands_behind_head, the shoulder in
  twist_bend and the neck in look_over_shoulder. Columns are r10 and r11, clay and cel.
- `final_metrics_delta.md` (review metrics against r11/base), `final_core_gate.txt`,
  `final_motion_report.md`.

## Not run

- `export_pmx.py`, `pmx_reimport.py` and `motion_vmd.py`: mmd_tools is not installed on the
  cluster.
- The Codex review step: `review.py` rebuilds its sheets with Blender before calling Codex,
  and Blender is not run on the login node.
