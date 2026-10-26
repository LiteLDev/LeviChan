# R9-5: cords, ribbons, bows, leaves and petals at full-body size

Strengths-guide items 8, 10 and 11: make the trims read at full-body size. Owned files are `levi/parts/accessories.py`, `levi/parts/bodice.py` and `levi/parts/shoes.py` (ribbons, laces, bow and ankle leaves only), plus one hunk in the bodice section of `levi/rig.py`.

## Result

**The guide's thickness targets lost the pairwise A/B, so they were not adopted.** As with round 8's narrow knee band, the reference's numbers made our sheet-faithful trims heavier rather than more readable. Every size is now a named, tunable constant, kept at the value that won.

What ships:

1. **Bodice leaf cluster rides the shell** (`rig.BODICE_RIDE`, bodice section of `rig.py`).
   - Before: the three neckline leaves were a small rigid island, carried on the weights of one neckline vertex. Raised arms swing the shell under them through the shoulder stages, so in `arms_up` the cluster sank up to **7.3 mm** into the bodice, with 33 % of its vertices more than 0.5 mm inside.
   - Now: the leaves keep the bodice's own per-point skin sample (same arm cap as the shell). In `arms_up` the worst point is −1.5 mm and 4 % of vertices are inside.
   - Both Codex models flagged the swallowed leaves in every `arms_up` crop; this is the change that wins the A/B.
   - The branch only runs when `SKIN_FOLLOW` is on and a skinned body exists. Otherwise the leaves fall back to the rigid-island rule as before.
2. **Bodice leaves with volume** (`LEAF_CUP` 1.8 → 2.4 px, `LEAF_RIB` 0.6 → 0.9 px, thickness `LEAF_THICK` 0.7 → 1.2 mm).
   - That is a cup of about 3.7 mm, a 1.4 mm midrib and 1.2 mm thickness, inside the guide's ranges.
   - `LEAF_OFF` now follows the thickness, so the back face keeps its clearance from the shell.
3. **Named knobs** for the sizes that stayed: `STRING_R`, `LACE_W` / `LACE_T` / `LACE_UNDER` / `LACE_CLEAR` (the over strand's lift follows the thickness), `EYELET_R`, `PETAL_THICK`, `FLOWER_DOME`, `RIB_CROSS` (follows `RIB_T`) and `RIB_KNOT_W`.
   - Comments at each knob record what was tried and why it lost.

## A/B (shuffled pairwise, gpt-6-astra and gpt-6.1-sol, against `main`)

The shots are close-ups at rest (torso front, 3/4 and high; tails front and 3/4; head leaves front, 3/4 and back; feet 3/4 and side; full body front and 3/4) and posed (`forward_bend`, `arms_up`, `head_left`, `walk` × torso front, torso 3/4, tails 3/4, feet 3/4).

| version | what | rest (astra / sol, new-old-tie) | poses (astra / sol) |
|---|---|---|---|
| v1 | guide targets: halter 4.4 mm, lacing 2.4 × 2 mm, bow 11 × 2 mm + 30° root twist + bead, tails ×1.4 / 1.3 at 1.8 mm, shoe laces 4.2 × 1.4 mm, thicker petals and leaves | 1-7-4 / 2-5-5 | 1-11-8 / 6-10-4 |
| v12 | moderate: halter 3.4 mm, lacing 2.0 × 1.3 mm, bow 8.7 mm, tails ×1.2, laces 2.6 mm | 1-4-7 / 0-1-11 | – |
| v13 | v12 + the leaf-riding fix | 2-3-7 / 2-3-7 | 8-4-4 / 5-8-3 |
| v14 | round-8 sizes + leaf fix + bow twist and bead + tails ×1.1 | 3-2-7 / 0-0-12 | 5-2-9 / 5-6-5 |
| v16 | v14 without the twist and bead (the "pinched knot") and tails ×1.1 | 0-0-12 / 0-0-12 | 3-1-12 / 2-0-14 |
| **final** | v16 with traced tail widths; shoe leaves unchanged | **0-0-12 / 0-0-12** | **2-1-13 / 2-0-14** |

What the reviewers said about the thicker trims:
- **Halter:** "heavier chest crossing", "swollen junctions".
- **Lacing and eyelets:** "crowded", "draws attention to the hardware".
- **Bow root twist:** "loop squeezed / pinched at the knot".
- **Tails:** split. Astra liked the fuller twists; sol preferred the finer ones.
- **Shoe laces:** "heavier without resolving contact".

The final version wins only where it fixes a defect: the `arms_up` leaf cluster, 2/2 for both models. The one "old" vote (astra, `forward_bend_torso_front`) concerns a shading sliver on the upright bodice leaf.

The full tables are in `pairwise_*.md`. The images are side-by-side pairs, and the file name says which side is new:
- `final_arms_up_front_new-left.jpg`, `final_arms_up_q34_new-right.jpg`: the leaf cluster in `arms_up`.
- `rejected_thick_torso_front_new-right.jpg`, `rejected_thick_tails_q34_new-left.jpg`: the v1 guide sizes.

## Gate (final build vs `main` bae3160)

- **IoU / REGION** (`metrics_delta.md`):
  - Silhouette is unchanged.
  - Green region IoU: front +0.000, back +0.000, side −0.001 (the cupped bodice leaves in profile).
  - Every other region is unchanged within 0.001.
- **Shade islands:** 43 / 33 / 28 / 43 / 28 / 39, the same counts as `main` in all six views.
  - Thicker cords, wider tails and bows, thicker petals and the cupped or ridged shoe leaves each added 1–5 islands, which is a second reason they stay out.
- **Core `rig_check`:** RIG CHECK OK, all 17 poses.
- **Motion report** (`--extended --report-core --motion`): identical to `main`'s.
  - accessories 8 major / 6 minor, bodice 0 / 12, shoes 0 / 6.
  - The only difference is the run time.
- **Clearance over the host surface** (scratch script, min mm and share of vertices > 0.5 mm inside):

  | pose | bodice leaves on shell | halter on body |
  |---|---|---|
  | rest | +0.19 / 0 % (main +0.18) | +0.07 / 0 % |
  | `arms_up` | **−1.53 / 4.0 %** (main −7.28 / 32.6 %) | −1.68 / 0.7 % (main −1.68) |
  | `forward_bend` | +0.55 / 0 % | −0.05 / 0 % |
  | `walk`, `squat`, `head_left` | ≥ +0.15 / 0 % | ≥ −0.36 / 0 % |

- **Budgets:** accessories 3,264 / 8,000, bodice 6,742 / 14,000, shoes 3,452 / 8,000. Faces are unchanged from `main` (102,602).
- **PMX:** export OK and `pmx_reimport` REIMPORT OK.

## Not done / notes

- The optional raised waistband (guide 3.6.4) belongs at the bodice / skirt seam, which the skirt part owns, so it was not attempted.
- The shoe laces sink up to 8.7 mm into the front of the ankle in `squat`, the same on `main`: the ankle crease folds the skin through them. That is left for the shoe / ankle owner.
- Data and functions only, as before: `accessories` reads `body.build_torso` and the bodice profile; `bodice` reads `skirt.front_surface_y`.
