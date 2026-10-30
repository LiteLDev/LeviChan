# r11/hair-kernel: shared hair-strand kernel

`levi/parts/_hair_kernel.py` is a private helper that hair_front and hair_back can both build their locks with. It turns the 风堇 hair study (analysis report `hair-technique`) into code. Smooth hair there comes from four habits, not from density: crescent sections, curvature limits everywhere, curls that tighten as they thin, and flat blade tips. The kernel enforces all four and checks every strand at build time. No part uses it yet, so the model is unchanged (107,968 faces). The hair-front and hair-back agents start from this branch.

## What it gives a part

```python
from . import _hair_kernel as hk
st = hk.strand(points, name='lock_A', width=0.03, aspect=3.0, facing=outward,
               curl=hk.curl(turn=220, toward='in', face='plane', radius=0.022),
               split=hk.split(at=0.85), grad=(0.55, 0.95))
hk.emit(bm, st)        # quads + toon_grad + UVs into the part's BMesh; validate() already ran
```

- **Centreline.** A C2 spline sampled every 1 mm, either through the points (chord-length knots) or as a B-spline over them (for one arch through a bulge point). Masked implicit fairing (`relax`) then opens every bend to R ≥ max(12 mm, 0.6 w) and ρ ≤ 0.45, measured with the real sections. Anchors stay fixed. A shape that could only be fixed by moving the curve more than 8 mm raises an error naming the place, such as a U-turn narrower than its lock (the old D1 crescent hook).
- **Frames.** A rotation-minimising frame (double reflection) plus a roll toward the authored facing, limited to 3°/mm. There are no per-ring sign flips.
- **Sections.** A crescent of 12, 14 or 16 vertices by width, cos-spaced so each rim gets two vertices. It has a mid-surface wrap, a flatter underside (k_in) and a 1 mm rim. Thickness follows t ∝ w^1.4 with a 1 mm floor, so tips are flat blades.
- **Curl.** Grown from the spine's end with G2 continuity. Curvature ramps in from the spine's own over ≥ 1.5 w, then κ = κc (wc / w)^0.8, capped by ρ ≤ 0.4 and the radius floor. The strand narrows to `core` before the curl tightens. `face='centre'` turns the broad face toward the centre (a ribbon wound round the curl). `face='plane'` keeps the width in the bend plane, a flat C-blade like 风堇's end curls. An optional pitch makes a ringlet.
- **Split tips.** Cut across the width at shares such as 0.6 / 0.4. The cut columns slide to the exact share and are grooved before the split. The sub-tips fan out by `diverge` and then run side by side, never into a bend's centre. They share the split ring, so the lock stays one island, which the rig's lock detection needs.
- **Rings.** A new ring at min(8 mm, 0.35 w) of arc, or at 6° of accumulated turn or twist, or at a width ratio of 1.15. Rings are never closer than max(1.5 mm, 0.12 w) unless 7° would be passed. The width never falls faster than ×0.84 per mm. The apex sits about 1.2 w past the last ring, so tips close in a point, not a stub.
- **Shingling.** `rest_on` / `strand_on` lift a lock so its underside rests on the locks below plus 0.5–1 mm. The lift is one smooth step along the spine, not a per-vertex push, and the call reports the share of the width that overlaps.
- **validate().** Checks turn ≤ 8° per ring, ρ ≤ 0.5, no folded quads, twist ≤ 10° per ring, a width ratio of 0.8–1.25 between rings (except the last two), ring spacing ≤ 10 mm and the apex within 12° of the last tangent. On failure it raises with the strand, ring, arc and point.

## Proof

`tools/hair_kernel_demo.py` builds the strands on a CPU node, validates each one, and checks that each mesh is closed and manifold, forms one island and faces outward. It then renders cel / clay / wire close-ups on a GPU node, both whole and zoomed. The strands are: straight, sideways S-wave, C end-curl, 270° spiral that tightens as it thins, 0.6 / 0.4 split tip, end curl with two sub-tips, pitched ringlet, and two shingled locks.

| strand | faces | max turn / ring | ρ | folds | twist / ring |
|---|---|---|---|---|---|
| straight | 533 | 0.5° | 0.01 | 0 | 0.0° |
| S-wave | 737 | 6.9° | 0.30 | 0 | 0.3° |
| C end-curl | 857 | 7.2° | 0.29 | 0 | 0.0° |
| 270° spiral | 917 | 7.2° | 0.13 | 0 | 6.9° |
| split tip | 758 | 1.1° | 0.03 | 0 | 0.0° |
| curl + sub-tips | 863 | 6.8° | 0.28 | 0 | 0.0° |
| ringlet | 917 | 7.1° | 0.09 | 0 | 7.2° |
| shingled upper (overlap 29%, lift 9 mm, clears the lock below by the 0.75 mm gap past its 2 cm root fade) | 426 | 6.9° | 0.11 | 0 | 0.0° |

For comparison, round 10's worst values were 94° of turn per ring, ρ 4.3, 23 folded quads and 81° of twist. A seeded fuzz test of 1,800 random strands (random paths, widths 6–50 mm, curls, splits, B-spline mode) produced no validation failure. Three (0.2%) raised a clear authoring error: a split placed inside a curl too tight for the inner sub-tip. A strand builds in 0.01–0.04 s.

- `endcurl_hy_kernel_r10.jpg`: 风堇's end curl (texture, geometry, wire), the kernel's curl with sub-tips (cel, clay, wire, q34 clay) and round 10's back curl, on the same patch.
- `locktip_hy_kernel_r10.jpg`: 风堇's hooked lock tip, the kernel's C end-curl and split tip, and round 10's claw tip.
- `demo_strands.jpg`: every demo strand zoomed (cel, q34 clay, q34 wire) and whole (cel, side clay).
- `demo_sections.jpg`: ring polygons along each strand in its own frame, on a 1 cm grid.

## Gates

- `tools/check.py`: CHECK OK, 107,968 faces (no part uses the kernel yet).
- `tools/rig_check.py`: RIG CHECK OK, identical to the round-10 baseline (worst stretch fist ×1.86 / squat ×1.85, worst pen side_bend 1.76 cm). The model is unchanged, so the motion report is the baseline's and was not rerun.
- `export_pmx.py` / `pmx_reimport.py` / `motion_vmd.py` were not run: mmd_tools is not installed on the cluster Blender, and the kernel adds no geometry yet.

## Notes for the hair parts

- Wrap mathutils facing functions as `facing=lambda p: head_normal(Vector(p))`. The kernel passes numpy points.
- For left / right pairs, build one side and `mirrored()` it. B = T × N flips under a mirror, so a rebuilt mirror needs `toward` '+B' ↔ '-B' and the split shares reversed.
- A strand's custom-normal share and outline weights can ride along as `attrs={'hf_keep': fn(p, u)}`. They are written as float vertex layers.
- Skirt clearance belongs in the authored points (a smooth envelope), not in per-vertex projection. `relax` will refuse a path that a projection bent too tightly.
- `strand(..., check=False)` plus `validate(st, raise_=False)` gives the metrics without raising, which is useful while authoring.
