# R9-6: 笑い, ▲, はぅ and the eye-corner outline; chin and lid rim tried and left off

File: `levi/parts/head.py` only. No morph names changed, so `export_pmx.MORPH_INFO` is untouched.
- Head: 12,021 faces, the same as main (budget 18,000).
- Model: 102,602 faces, the same as main.

## Summary
- 笑い, ▲ and はぅ beat main in the order-balanced pairwise Codex A/B.
- The outline hull no longer draws the bunched lid skin around the eye.
- The two rest-shape items from guide item 9 are built as tunable parameters, but they ship **off**: neither won the A/B.
  - the chin about 5 mm lower and narrower;
  - a 1.5–2 mm upper-lid rim.
- キリッ stays at main: no variant won.
- The rest geometry is identical to main. IoU and shade islands are unchanged.

### How the A/B was run (order-balanced)
- Every comparison is a sheet of pairs, one row per view, with the two versions shuffled per row. Both gpt-6.1-sol and gpt-6-astra judged it, and every sheet was judged again with each row's order inverted.
- A row counts for a version only when **both orders pick it** for that model. Inconsistent rows count as ties.
- Both models show a strong position bias. Single-order runs gave misleading tallies: one round 8 vs new run went 14–1 in one order and about even in the other.
- The tallies are in `ab_tally.txt`, the keys in `ab_keys.txt`, and the replies in `codex_*.md`.
- The one exception: the 5 mm chin drop was judged in one order only (`codex_ab1_*`). It is off anyway.

## What ships

### 笑い
- The outer corner rises 0.4 px instead of 1.4 (`SMILE_CORNER`). The corner then shears less.
- The lash flick folds in to 15 % while the lids are closed (`FLICK_CLOSED`; it was 45 %).
- A/B (笑い rows, consistent picks): sol 2–0, astra 2–0. The front view is a tie.
- Strip ratings: sol natural, astra acceptable. Round 8 had astra at unnatural ("pinched outer corner").

### ▲ (`TRI_MOUTH`, `TEETH_TRI`)
- The opening has straight sides from the two corners, which sit on a flat base 1.3 px down, to an apex 2.7 px up.
- The jaw stays still. Round 8 turned it 3°, which dropped the lower lip as a rounded box.
- The upper teeth move 1.6 px back and 0.7 px up, so their edge no longer cuts across the apex. This key adds to 歯無し上 and stays inside.
- A/B: sol 2–0, astra 3–0.
- Strip ratings: acceptable for both. Round 8 had astra at unnatural ("not triangular enough").

### はぅ (`HAU_*`)
- The lower stroke starts on the shared apex and is shorter: 42 % of the eye's width, dropping 7.5 rows (`HAU_ARM`, `HAU_DROP`).
- It stands 0.9 px off the skin at the apex (`HAU_APEX_LIFT`), so it covers the bunched inner corner.
- The flick folds in to 15 %.
- A/B: sol 1–1, astra 2–0, so 3–1 overall.
- Absolute ratings are still unnatural for both: "the junction with the thick upper lash looks like separate sharp pieces".
- A version that also drew the closed eye in toward the nose (`HAU_SQUEEZE` 4.5 px, `HAU_LINE` 120.5 / 9) won the A/B 6–0 with both models. **It is off**, because half way its lid rim (rolled into the eyeball) swept over the iris at the gaze limits:
  - the eye check went 1.48 → 1.83 mm (limit 1.5);
  - 8 variants of the line and the squeeze stayed above 1.5;
  - so did extra path clearance (diagonals, a larger `LID_PATH`) and a shallower rim.

### Eye-patch outline (`EYE_HULL`, `eye_hull_weight`)
- Hiding the hull on the whole eye patch removed the long brown spikes beyond the lashes and the line across the cheek in 笑い, はぅ and blinks. They were hull lines drawn over bunched skin.
- The lid rim (the opening and its partner loop) keeps its outline, except:
  - at the outer corner, where it fades out;
  - at the inner corner, where it drops to 30 % (the knot at the はぅ apex).
- The loops further out have no outline inside the eye region. It returns before the temple's silhouette and on the nose side.
- A/B at rest (only this changes at rest): sol 0–0, astra 4–0. All four are 3/4 rows, where the brown corner spikes are gone.

## Tried and left off (tunable; the defaults are main's)

| change | consistent picks (sol / astra), new–main | note |
|---|---|---|
| chin tip 3.5 px (5 mm) lower + 0.5 px narrower (`CHIN_DROP`, `CHIN_NARROW`) | lost, both models (one order) | "stretched", "a hanging point" in 3/4 and nods (`ab_chin_drop_cel.jpg`) |
| chin 1.3 px narrower per side, lid as main (`CHIN_NARROW`) | 0–0 / 2–6 | lost |
| 1.0 / 1.2 px lid rim (`UPPER_RIM`, `RIM_TAPER`) + 1.3 px narrower chin | 3–3 / 2–0 | sol consistently preferred main's outer upper lid in 3/4: "less like a projecting strip" |
| キリッ slanted and narrowed (`KIRI_*`) | tie (single-morph pairs: 1–1 each) | |
| キリッ with a straight slanted lid | 0–2 / 1–1 | "a kinked peak" in profile (removed) |
| はぅ squeeze (`HAU_SQUEEZE`) | 6–0 for the old morph set | over the eye-check limit, see はぅ above |

A non-zero `CHIN_DROP` is an experiment: the neck table, `LOWER_W_ROWS`, `LOWER_CHEEK_FILL` and `NECK_SHADE_ROW` keep their rows.

## Verification (final build)

| check | main | this PR |
|---|---|---|
| `tools/check.py` | OK | OK (head 12,021, total 102,602) |
| core `rig_check.py` (17 poses) | RIG CHECK OK, eye poke 1.36 mm | RIG CHECK OK, eye poke 1.36 mm |
| silhouette IoU front / side | 0.916 / 0.861 | ±0.000 (skin region ±0.000) |
| shade islands front / q34 / side | 43 / 43 / 33 | 43 / 43 / 33 (px −8 / −4 / +4) |
| motion eye check, worst case | はぅ=0.5 1.48 mm, まばたき=0.5 1.46 mm | 1.48 / 1.46 mm (all cases equal to main) |
| PMX export + reimport | REIMPORT OK, 40 morphs | REIMPORT OK, 40 morphs, all in their panels |
| `rig_check --extended --motion`, issues per part | head 0 major / 13 minor | identical per-part table (head 0 / 13) |

## Remaining
- **はぅ:** it still reads as two graphic strokes rather than a squeezed lid. The squeeze that won the A/B needs a rim that does not sweep over a turned iris (for example a rim that follows the closing lid at a constant depth), then the eye check again.
- **キリッ:** a determined look needs the brows, which sit under the bangs. Lid-only variants did not beat main.
- **Chin and lid rim (guide item 9):** the mechanism is in, the defaults are off. Codex prefers the compact round-8 chin and the thinner lid.
- **Jaw shade strip (round-6 P2):** unchanged. Both models still name the jaw-to-neck transition in nod-up and low views.
- 瞳小 and ん still read weakly in the strip ratings (out of scope).
