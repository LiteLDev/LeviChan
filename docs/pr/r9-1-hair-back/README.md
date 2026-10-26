# R9-1 Back hair: big, voluminous locks

Strengths guide item 1: the back as a few big S-waved locks instead of a smooth sheet with thin strands.
Shape inspiration only. Nothing was imported from, traced from or sampled from the reference mesh.

## What changed (`levi/parts/hair_back.py` only, no rig changes)

- **Primary locks** (`primaries()`, `PRIM_*`). The back is a row of 8 primaries across the mass, set by the measured mass edges (`PRIM_EDGES`).
  - Neighbours sit 3.5–5 cm apart. Each is `PRIM_OVERLAP` (2.0) times that spacing wide, so they overlap; widths and placement vary per lock (`PRIM_LOCKS`), so they don't read as a row of equal tubes.
  - They are thicker than before (`PRIM_TH` 0.5) and alternate over and under their neighbours (each lock's layer), so steps and grooves open between them from the shoulder blades down.
  - Each lock is an S-wave (`PRIM_WAVE`: 14 px sideways, 128-row wavelength), a quarter period out of phase with the next. The waves start at the shoulder blades (`PRIM_WAVE_ROWS` 150–230; `WAVE_ROWS` was 175–260).
  - The depth wave is 2 px, below half the layer step between neighbours, so the locks don't pass through each other. At 6 px they swapped depth order along their length and printed abrupt shade patches.
- **Curls.** Three of the eight places are the sheet-fitted curled primaries A, D and F of `MAIN` (`PRIM_FITTED_CURLS`), raised 1 px over their neighbours. With the SWEEP side-view curl and the outer crescents, that gives 4 big open curls on the back, at staggered heights.
  - Generated curls (`PRIM_LOCKS`' curl entries, wider and less tightened, `PRIM_SHRINK` / `PRIM_CURL_*`) exist behind the switch. In pairwise A/B they read as "bunched hooks" from the 3/4 view, so the fitted ones stay.
  - The fitted locks keep their own depth wave (`PRIM_FITTED_DEPTH` None). Capping it at 2 px closed the right lobe's curl into an angular notch in the posed 3/4 views (sol 3–5 against main, order-balanced).
- The other five primaries end in soft points tucked under the mass, at staggered heights (392–410).
- **Shading.**
  - The over-locks keep `PRIM_KEEP` 0.42 of their own normal, rising from the shared volume normal over rows 200–290 (`keep_rows`), so the crown stays one smooth mass and the lock forms read lower down.
  - The parting filler lies deep under its neighbours, and the lower SWEEP lock sinks under the primaries (`PRIM_SWEEP_LAY`). Both used to print the two-lobe shade wedge as one long stripe.
  - The old narrow wave locks (`WAVES`) are off (`PRIM_SECONDARY`): they added skirt crossings in jump_tuck and spin.
- **Skirt clearance.** `SKIRT_GAP` is 7 px (4 px with `PRIMARY_LOCKS` off). The big locks lie on the skirt over a wider band; 7 px halves the hair × skirt majors (below).
- **Scalp seam.** The roots and the crown envelope (`env_sx`, `hair_front.CAP_PROFILE`) are unchanged.
- **Dial back.** `PRIMARY_LOCKS = False` goes back to main's code path (MAIN + WAVES, 4 px skirt gap; checked: the same 20,170 faces). Every other new behaviour is a `PRIM_*` parameter.
- Faces: 20,310 (budget 40,000; main 20,170).

## Rig

No `rig.py` change. Every primary is a long, narrow loose part, so `_hair_locks` gives each one its own `後髪束N` chain: 16 lock chains, against main's 18 (fewer, wider locks, so fewer chains to cross each other). The build log lists them.

## Gate (against main bae3160, baseline built from an exported copy of HEAD)

- **Core `rig_check`:** RIG CHECK OK. All 17 poses are identical to main's numbers (`core_gate.txt`).
- **Unit checks:** `tools/check.py` passes (CHECK OK).
- **PMX:** `export_pmx.py` and `tools/pmx_reimport.py` pass (REIMPORT OK; the VMD round trip is 0.00 mm).
- **Motion** (`rig_check --extended --motion`), hair issues, main → R9-1:

  | | main | R9-1 |
  |---|---|---|
  | hair × skirt majors | 4 (jump_tuck 1482, spin@9 1083, run_l 526, idol_dance@72 526) | **2** (jump_tuck 1172, spin@6 1012) |
  | hair × skirt minors | 4 | 6 (run_l 282, idol_dance@71 284, twist_bend 258 new, walk 199, turn 142, look_over_shoulder 94) |
  | hair_back majors | 1 (pop 後髪束7_4 spin@40) | 1 (pop 後髪束9_4 spin@4, 0.031) |
  | hair_back minors | 13 | 13 |
  | hair × garment, hair_front | unchanged | unchanged |

  There are no new majors. Two majors became minors, and every hair × skirt crossing count that was there before is lower. twist_bend (258) is a new minor.
- **Three-view metrics** (`final_metrics_delta.md`):
  - Hair IoU is back 0.696 (−0.001) and side 0.668 (−0.002). Those are tiny trades, justified by the A/B below.
  - Shade islands over all views: 214 → 212. Back +4 and 3/4 back −6; the other views are unchanged.
- **Relief** (`ref_fbx/measure2.py` slice at z 1.0, rms / peak-to-peak of the back profile): 11.9 / 58 mm → **15.1 / 94 mm** (guide target ≥ 15 mm).
  - The slice's crest count does not drop: lens edges and the steps between overlapping locks count as crests. Visually the back now reads as 8 broad locks rather than a sheet with strands.

## Pairwise A/B (order-balanced; gpt-6-astra and gpt-6.1-sol)

Each item is shown **twice, once each way round** (A = main, then A = R9-1), in a shuffled sheet order. A pick counts only when both orders agree; otherwise it is a tie.

- **Rest** (`pairwise_rest.md`): a 4-view composite plus single views (back, 3/4 back, high, side, turn 210, 3/4 front). **astra 5–0 (2 ties), sol 5–0 (2 ties).**
- **Poses** (`pairwise_poses.md`): forward_bend, swing, head_right, walk@14, run@10, spin@20, turn@20, idol_dance@81, look_over_shoulder, twist_bend, jump_tuck, in back / 3/4 back / side views. **astra 6–2 (3 ties), sol 8–2 (1 tie).**
  - Losses: twist_bend (both models), forward_bend (sol) and turn@20 (astra), each "slight", over angular light breaks near the lower tips.

Earlier variants that lost and were dropped:
- all-generated curls (rest 0–1 / 0–1, single order);
- tilted-flat curls;
- a shorter backing curtain;
- the depth-capped fitted curls (poses sol 3–5).

## Images

- `back_hair_main_vs_r9.jpg`: main (top) against R9-1 (bottom), cel and clay, back and 3/4 back.
- `final_02_angles_cel.jpg`, `final_04_poses.jpg`, `final_05_islands.jpg`: the review sheets of the final build.
