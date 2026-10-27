# R10-A5: front hair follows the shape master

`levi/parts/hair_front.py` only.

## What changed

- **Crown from the master.** The scalp cap is still the sheet superellipsoid loft (topology,
  128 x ~46 rings, `hf_keep` / `hf_line` unchanged). A fit table (256 az x 1 px rows) casts a ray in
  along each sheet-cap point's `head_normal` to find the master's outermost hair surface. The cap
  moves along that normal by `FIT_STRENGTH(row) x weight x (target - 1.5 mm - sheet)`, smoothed
  to the mass.
  - The weight is 1 where the master's outermost label is `hair_front` or `head`. Bang surfaces over
    the face are labelled `head`, because their nearest object was ours. The weight is 0 where
    `hair_back` or the leaves/flowers are outermost.
  - It fades out below the crown (rows 72-94).
  - The cap is kept 2 mm off the forehead (`_clear_face`, a BVH of `head.ring`, which is a pure
    surface function).
- **`CAP_PROFILE`** keeps its name and layout `(row, half width, front col, back col)`. It is now
  measured on the reshaped cap: every 4 rows above row 116, with the half width and depth grown
  until the `CAP_EXP` superellipse contains the section's back half. It is computed lazily
  (module `__getattr__`), so `hair_back`'s `from .hair_front import CAP_EXP, CAP_PROFILE` still
  works, and hair_back builds cleanly. The sheet table is now `CAP_PROFILE_SHEET`.
- **Everything on the cap rides it.**
  - `cap_shift` moves the fringe root stations, the ahoge, and the buried root and first point of
    the long lock, curl and curtain along `head_normal` by the local offset. The shift is applied
    after mirroring, so `_R` uses its own side's offset.
  - The cheek wisps keep round 9's roots exactly: they settle on the sheet cap. Their temple roots
    moving ~4 mm alone took their pen_frac in dance_heart / idol_dance@48 from minor to major.
  - `cap_front_sc` now solves for the moved cap's front at the requested height. On the dome the
    offset moves points off their sheet row.
- **Fix: inside-out strands.** `orient_outward` flips any closed strand island with negative signed
  volume after `recalc_face_normals`. A thin crescent clump lying close over the cap came out inside
  out (black in cel and clay, outline hull inside). The bug did not trigger on main; FIT off
  renders the same as main (12/12 ties).
- **Kept procedural:** all strand construction (`strand`, `side_set`, `settle`), the layouts
  (`BANG_CLUMPS`, `CHEEK_LOCKS`, `CURL_PATH`, ...), the object names (rig side-hair families), the
  procedural crown grooves, the normals and the outlines.

## Fit (tools/shape_fit.py, hair_front)

| | target->ours p50 / p90 / p99 mm | ours->target p50 / p90 / p99 mm | covered |
|---|---|---|---|
| main | 4.5 / 15.2 / 30.1 | 8.7 / 22.5 / 28.6 | 0.537 |
| full-strength fit (v2) | 2.3 / 11.2 / 30.1 | 4.3 / 15.3 / 28.1 | 0.709 |
| **this PR (half strength)** | **3.6 / 12.2 / 30.1** | **7.1 / 16.4 / 28.0** | **0.607** |

- p99 does not move: about 5% of the area labelled `hair_front` is neck/choker and the eye sockets
  (label slips; see `docs/pr/r10-phase0/labels.jpg`).
- The side locks already lie on the master: per-object mean distance is 1.2-6 mm, the curl 8-10 mm.
  A spine fit along the nearest target normal (capped at 8 mm) changed p90 by under 0.1 mm, so it
  was not kept.

## Pairwise Codex A/B vs main (order-balanced; a pick counts only when it is the same in both orders)

| variant | items | gpt-6-astra new/old/tie | gpt-6.1-sol new/old/tie |
|---|---|---|---|
| full fit (strength 1, target lock relief 0.6, fringe arch on the master, tips from head.face_point) | 26 | 0 / 26 / 0 | 0 / 26 / 0 |
| half strength, fringe arch halfway, head-based face | 12 rest | 0 / 12 / 0 | 0 / 12 / 0 |
| half strength, cap only (fringe as main) | 12 rest | 5 / 7 / 0 | 0 / 12 / 0 |
| ... crown top untouched (0 above row 45) | 12 rest | 0 / 10 / 2 | 0 / 12 / 0 |
| control: FIT off | 12 rest | 0 / 0 / 12 | 0 / 0 / 12 |
| half strength, first full run (cheek roots still shifted) | 26 | 0 / 18 / 8 | 0 / 24 / 2 |
| **this PR** | 26 | **0 / 26 / 0** | **0 / 26 / 0** |

Both models consistently prefer main's taller, rounder sheet dome. The master's crown is 2-3 cm
lower and flatter at the front top. Every variant that moves the crown toward it reads as
"flattened / notched top", "stepped forehead contour" or "far-side ornament protrudes". The
leaves and flowers (unit accessories) stay where they were and stand out past the narrower crown.
Details: `pairwise_final.md` and `pairwise_rest_half_strength_bangs_main.md`. Scripts: `ab.py`,
`ab_pairs.py` (adapted from r9-4-sleeves: head crops, face close-ups, upper-body pose crops).

## Gates

- `check.py`: OK (107,988 faces). `rig_check.py`: all 17 core poses OK. PMX export and reimport: OK.
- Motion (`motion_delta_hair_front.md`): hair_front went from 12 major / 31 minor to 11 major /
  33 minor.
  - No new major.
  - The idol_dance curl_R pen goes from major to minor.
  - One new minor: hair_cap pen_frac 0.8% in dance_heart.
  - jump_tuck curl pen_frac stays at 6.5%; the curl path is unchanged.
  - hair_back, accessories, head and body issue counts are unchanged.
- Shade islands on the hair (`metrics_delta.md`): +2 front, +6 high, +3 q34, +4 side, 0 back.
- Three-view IoU (report only): hair -0.002 front, -0.007 side.

**The A/B gate fails.** Set `FIT_STRENGTH` to 0 (or `FIT = False`) to get main's look back exactly,
while keeping the fixes. The crown shape is the open question for the coordinator.

`main_vs_final_cel.jpg` / `main_vs_final_clay.jpg`: top row is main, bottom row is this PR (front,
3/4, side, high).
