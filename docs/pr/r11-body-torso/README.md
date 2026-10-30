# r11 / body-torso: neck, collarbones, upper chest and back

风堇 has no torso, shoulders, elbows or forearms, so Levi's upper body stays procedural. This
branch fixes the defects the round-11 analysis found there. It also adds the anatomy that the
strapless dress shows, kept soft enough that the cel ramp draws at most one clean terminator
per form. Only `levi/parts/body.py` changes. It now reads the bodice's pure surface functions
(see "Cross-part").

The review of the first pass found four problems, and this pass fixes them:

- the collarbone relief kinked the halter cords;
- the faired chest hid the bodice's rim line;
- the rounded elbow cost bend span;
- the neck contract could not be met at the chin.

## What changed

- **Upper chest without the ridge** (`UPPER_CHEST`).
  - Round 10's exposed chest stayed flat down to row 230 and then stepped 18 px forward in
    5 rows, which left a ridge at the bodice's top edge.
  - Each front column is now one cubic Hermite from row 203 to the neckline ring. It fades
    out over the 4 steps beside the socket.
  - The cleavage is a shallow valley about 5 px deep.
- **Bodice rim clearance** (`_rim_clearance`, new in this pass).
  - Each front column's profile is checked around the bodice's neckline row against the
    shell's front: `bodice.profile`, `neck_row_t` and `front_y`, the backmost of either
    side, with and without folds.
  - Where the column comes closer than `RIM_CLEAR` (2.6 px), it is pushed back by a smooth
    bump in the row (`RIM_DENT`, 4 px sigma), so the interpolated mesh clears the rim.
  - Minimum rim clearance at |angle| < 40° from the front: round 10 1.21 mm, first pass
    0.98 mm, now **2.68 mm**.
  - The rim line is continuous in the high and 3/4 views, with no skin slivers
    (`bodice_rim.jpg`).
  - The bodice shell is inside the body at 6 vertices, at worst 0.21 mm, all at the side by
    the armpit. Round 10: 9 vertices, 0.85 mm.
- **Anatomy relief** (`_torso_relief`), applied after the shape master along the surface
  normal and faded out over the socket border.
  - Collarbones, the hollow above them, the jugular notch and its two tendons. The
    trapezius at the neck's base, a shallow spine groove and faint shoulder-blade plates
    sit on the back, under the hair.
  - This pass made the collarbones broader rather than higher, because the halter strap
    lies right on them:
    - `CLAVICLE_AMP` stays at 1.6 px, but its row sigmas go 2.6 / 4.5 → 4.5 / 6.0;
    - the hollow above them (`SUPRACLAV`) goes 2.4 → 1.4 px deep, with a row sigma of
      2.8 → 4.2.
  - Halter strap curvature at the collarbone, L / R (`halter.jpg`):
    - round 10: 3.8 / 4.1 °/mm;
    - first pass: 25.5 / 42.9 °/mm;
    - now: **4.9 / 4.5 °/mm**.
  - The strap and the X junction are smooth again, now cleaner than round 10's zigzag.
  - The notch is 1.0 px deep (was 1.6) and 5.5 px wide at its base (was 4), with a softer
    top fade. The side view no longer shows the outline hull's tick (`neck_clavicles.jpg`).
- **Denser front rings** (unchanged from the first pass).
  - The rings from the neck down to row 256 split the middle 4 steps of the front arc:
    36 vertices instead of 32.
  - The back, the socket arcs and the 3 steps beside each socket keep round-10 spacing.
  - A quad+triangle band between rows 256 and 266 returns to 32 vertices. Every ring from
    row 266 down is round 10's.
  - The socket border, `cut_socket`, `SOCKET_ROWS` and `levi_socket_s` are unchanged:
    48 border vertices at 0.
- **Neck** (unchanged from the first pass): two more rings, at rows 154.5 and 165.5, and
  the jaw tilt fades out linearly to row 178.
- **Elbow: back to round 10.** The 8 px centre-line fillet and the elbow bumps are
  dropped.
  - The rest elbow is inside the sleeve balloon, so neither could be seen.
  - Both cost bend span. Elbow span by variant (extended subset), with round 10 at 1.171
    in hand_to_shoulder and 1.160 in hands_behind_head:

    | variant | hand_to_shoulder | hands_behind_head |
    |---|---|---|
    | fillet 8, no bumps | 1.291 | 1.216 |
    | fillet 4, no bumps | 1.276 | 1.191 |
    | fillet 8 + olecranon 0.6 px | 1.289 | 1.209 |
    | neither | 1.170 | 1.160 |

  - Every rig joint is round 10's again, the elbow included.

## Gates (cluster, Blender 5.2.3, final code)

| | r11/base | first pass | this branch |
|---|---|---|---|
| check.py | OK, body 7,417 | OK, 7,569 | OK, body 7,569 / 24,000, total 108,120 / 200,000 |
| rig_check, 17 core, with the repeat build | OK | OK | OK (`final_core_gate.txt`) |
| core stretch: arms_up / fist / squat / side_bend | 1.78 / 1.86 / 1.85 / 1.47 | 1.77 / 1.86 / 1.85 / 1.46 | 1.78 / 1.86 / 1.85 / 1.47 |
| core pen cm: arms_forward / head_left / side_bend | 0.44 / 0.21 / 1.76 | 0.48 / 0.26 / 1.76 | 0.44 / 0.26 / 1.76 |
| rig joints | | elbow 1.4 mm out | all identical to r11/base |
| IoU front / side / back | 0.9090 / 0.8331 / 0.9132 | 0.9090 / 0.8334 / 0.9132 | 0.9090 / 0.8334 / 0.9132 |
| skin region IoU front / side | 0.744 / 0.612 | 0.744 / 0.611 | 0.744 / 0.611 |
| shade islands, q34_front_left skin | 11 | 10 | 10 |
| bodice rim, minimum clearance at the front | 1.21 mm | 0.98 mm | 2.68 mm |
| clearance p5: bodice / choker / halter | 1.97 / 0.61 / 1.00 mm | 1.96 / 0.60 / 0.99 mm | 2.08 / 0.60 / 0.99 mm |
| body: open edges, loose parts, mirror error | 0, 15, exact | 0, 15, exact | 0, 15, exact |
| shape_fit p50 / p90: body; accessories | 6.9 / 23.6; 4.5 / 11.1 mm | | 6.9 / 23.6; 4.1 / 10.8 mm |

## Motion report

`rig_check.py -- --quick --no-core --extended --report-core --motion`, compared with the
r11/base report. The full report is `final_motion_report.md`.

- **Issue counts**: 479 → 478 in total (first pass: 485).
  - body major 66 → 65;
  - sleeves minor 70 → 68;
  - hair/garment minor 13 → 15. The two new minors are hair × garment crossings: 51 pairs in
    forward_bend and 41 in hug_self, against a minor threshold of 40.
- **Elbow span**: identical to r11/base in every pose (first pass: +0.02 to +0.12).
- **Body**:
  - look_over_shoulder 首 stretch 1.49 → 1.59, below the minor level of 1.60;
  - head_left / right stretch 1.31 → 1.35 and compress 0.81 → 0.75. These come from the
    neck's extra rings, as in the first pass;
  - everything else is within ±0.003.
- **Halter** (accessories part; its weights are sampled from the skin under it):
  - idol_dance stretch 1.64 → 1.83 (first pass 1.91), minor in both;
  - hands_on_hips stretch 1.10 → 1.30;
  - head_right compress 0.77 → 0.67 (first pass 0.675).
- **Why the halter metric did not come back.** The collarbone relief was not the cause.
  With the relief broadened, which brings the strap's curvature back to round 10's level,
  idol_dance still reads 1.92 on the subset (first pass 1.91).
  - The stretch sits on the strap's last segment above the tuck: x 43 px, row 231, an
    edge 15 mm long. Its two ends take 肩補助2 0.10 and 0.21 + 0.06 肩補助3 from the skin.
  - The faired chest beside the armpit is further from the socket border, so the stage
    weights there ramp from 0.03 (x 34) to 0.30 (x 45). Round 10's ramp went from 0.12 to
    0.29.
  - The value moves with the strap's Catmull samples: 1.92 on the subset, 1.83 in the full
    run after a 0.06 mm change.
  - More fairing toward the socket (`UPPER_CHEST_EDGE` 2) makes it worse: 1.97, and
    reach_up_back 1.50.
  - Smoothing the halter's sampled weights wider (`rig.HALTER_SMOOTH` 8 → 20 mm) brings it
    to 1.68. But the cord then sinks into the skin in idol_dance (pen_frac 0.9%, a new
    minor), so this branch leaves it.
  - With r11/accessories' taut-cord halter, idol_dance reads 1.82 on the r11/base body and
    1.90 on this one.
- **Better than r11/base**:
  - bodice_shell compress in dance_heart, hands_behind_head and dance_sway (0.48–0.56 →
    0.56–0.63);
  - halter compress in hands_behind_back and arms_crossed (0.82 → 0.91);
  - body idol_dance stretch 1.92 → 1.89.

## Neck contract for the head part (restated)

The body's neck is the visible neck, round the axis x = 0, y = −30.5 px (−47.4 mm). The
radius (px) of the build's surface about that axis, by row and direction (0° = front):

| row | 0° | 30° | 60° | 90° | 120° | 150° | 180° |
|---|---|---|---|---|---|---|---|
| 148 | 11.5 | 11.7 | 12.3 | 12.9 | 13.3 | 13.4 | 13.5 |
| 152 | 12.1 | 12.3 | 12.8 | 13.2 | 13.4 | 13.4 | 13.5 |
| 156 | 12.7 | 12.9 | 13.2 | 13.5 | 13.4 | 13.4 | 13.5 |
| 160 | 13.4 | 13.4 | 13.5 | 13.5 | 13.4 | 13.4 | 13.5 |
| 164 | 13.5 | 13.5 | 13.4 | 13.4 | 13.5 | 13.4 | 13.5 |
| 168 | 13.5 | 13.4 | 13.2 | 13.3 | 13.7 | 14.0 | 13.8 |
| 172 | 13.9 | 13.7 | 13.4 | 13.7 | 14.7 | 15.1 | 14.3 |
| 176 | 14.4 | 14.2 | 14.0 | 14.6 | 15.7 | 16.2 | 15.1 |

The rings rise toward the back: ring 161 spans rows 151.8 (back) to 161 (front).

- **From the crease down, the head stays inside.** The head's surface must be at most
  12.2 px (19 mm) from the axis, at least 1 px inside the body (the body's outline hull
  adds 1.25 px). The crease row is row_in(θ) = 168 − 19.5 × (1 − cos θ) / 2: front 168,
  sides 158.5, back 149.
- **Above the crease, the head may stand out.** Its under-jaw surface may be outside the
  body's neck and meets it there in a crease. At the front, the chin and the under-chin
  plane come down to the throat at row 167–168, over a body neck of 13.0–13.5 px (rows
  158–167).
- The old wording, "within 12.5 px from row 158 at every angle", could not be met at the
  chin (spec chin_z is row 161).
- r11/head already follows this contract: `_head_graft.BODY_NECK` = (13.5, −44, −17) px,
  `NECK_TUCK` 2.6 px (a 10.9 px tube), and the tube top at z 1.217 in front (row 168.5)
  and 1.247 at the back (row 149).

## Cross-part

`body._rim_row` and `_rim_clearance` import `levi.parts.bodice` lazily and call only its
pure surface functions: `profile`, `neck_row_t` and `front_y`. A hidden layer kept inside the
outer layer minus a clearance follows the bodice if the bodice's neckline changes;
r11/bodice does not change these functions.

## Sheets

All sheets compare round 10 (r11/base), the first pass and the final build.

- `halter.jpg`: the strap close-up (cel, clay), the strap from the side, and the halter
  from the front.
- `bodice_rim.jpg`: the rim from above on either side, at 3/4 right, and the strap's tuck.
- `neck_clavicles.jpg`: the neck base from the side (cel), the notch (clay), and the
  collarbones at 3/4 (raking light, clay).
- `chest_rest.jpg`: the upper chest from the front, at 3/4, from above and from below.
  Columns: round 10 clay, final clay, wireframe and cel.
- `poses.jpg`: round 10 vs final, clay and cel: idol_dance@78, reach_up_back, arms_up,
  hands_behind_head (back) and look_over_shoulder (neck).
- `final_core_gate.txt`, `final_motion_report.md`, `final_metrics_delta.md`.

## Not run

- `export_pmx.py`, `pmx_reimport.py` and `motion_vmd.py`: mmd_tools is not installed on the
  cluster.
- The Codex review step.
