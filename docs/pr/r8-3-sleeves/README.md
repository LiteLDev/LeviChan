# R8-3: sleeves with the arms raised

Files: `levi/rig.py` (new sleeve-gather section after `_sleeve_weights`, plus two calls at the end of `build_rig`) and `levi/parts/sleeves.py` (one marker property). No geometry changed. Sleeves stay at 7,896 faces, the model at 99,010.

## The problem

With the arms overhead, the sleeve bags kept their rest inflation. Skinning alone cannot move cloth along the arm. The bag stayed a stiff column, full at the wrist and pinched into a waist above the band (gpt-6.1-sol: arms_up **major**).

Real fabric behaves differently. The bag is tied at the band and at the wrist, so gravity along a raised arm slides the loose cloth toward the band, where it bunches. The wrist half is pulled against the forearm.

## What changed

**1. Corrective shape keys driven by gravity (Blender).** Each side has two keys on every sleeve object, built at rig time from the rest mesh. They are measured around the rest arm axis (腕D → ひじ → 手首) and the part's sleeve parameter s (0 at the band, 1 at the wrist).

- `左袖寄せ` / `右袖寄せ` (gather):
  - Only the cloth beyond a floor radius r0 = 5 cm is rescaled; r0 grows by 2 cm within 9 cm of the elbow.
  - The scale follows one falling profile along the sleeve: 1.12 near the band, down to 0.2 toward the wrist, and back to 1 in the cuff gather.
  - Soft folds run round the arm where the cloth bunches.
  - There is no separate hump next to a deflated zone, so no waist forms between them.
- `左袖滑り` / `右袖滑り` (slide):
  - Loose cloth moves toward the band along the arm, by 1.2 cm × sin(πs).
  - This key is a delta on top of the gather key.
- Drivers read world positions only, so nothing jumps when 腕 passes 180° (idol_dance shows no pop).
  - Both keys follow the rise: smoothstep(0, 0.8) of the sine of the 腕D → wrist chord's elevation. They are 0 with the arm hanging or horizontal.
  - The slide fades out as the elbow bends (chord ÷ arm length, 0.55 → 0.85). Cloth cannot slide through a bent elbow; without the fade, arms_forward had 67 sleeve vertices up to 1.5 cm inside the arm.
  - The gather falls to 30% with the elbow folded. In hands_behind_head the deflated bag compressed into the elbow crook (×0.118).
- The pieces lying on the bag ride the bag's own key displacement, taken at their 4 nearest bag vertices. These are the bow tails and the cuff.
  - Where the bag pulls in, they follow only 75% of the way, so they stay outside it.
- PMX: the four keys export as vertex morphs in the 'other' panel and are not driven. MMD's sleeve physics hangs the drape there, and an animator can key the morphs with physics off.

**2. The bow tails take the bag's skin weights (`_sleeve_ride_weights`, Blender and PMX).**
- Each long ribbon strip (`obj['levi_sleeve_tails']`, an island ≥ `RIGID_ISLAND`) gets the inverse-distance blend of its 4 nearest bag vertices' weights. The 4 largest bones are kept. Weights are averaged within 8 mm, so a strip's cross-section shares one set; without that, the 0.8 px strip tore at ×2.1.
- Before, the tails had positional weights of their own. They stand off the arm, so they took a larger drape share than the cloth under them. A raised arm then swung them through the bag; the old metrics show "dashes" in dance_point and arms_up, and idol_dance had a ribbon compress **major** of 0.096.

**Rejected:**
- Flipping the tails toward the shoulder with a key: they crossed the face.
- A stronger band swell (0.15): reviewers saw "a projecting shelf".
- The original 2.2 cm slide: reach_up_back flipped 67 faces.

## Results

### Core gate (`baseline_core_gate.txt`, `final_core_gate.txt`)

RIG CHECK OK.
- Every pose is equal to main or better.
- arms_up stays at ×1.77, and its worst object is still the body.
- arms_forward penetration goes from 1.18 to 0.45 cm.
- wrist_twist goes from ×1.31 to ×1.32.

`tools/check.py` passes. The PMX export, `pmx_reimport` (13 morphs: the 9 facial ones and the 4 sleeve keys) and `motion_vmd` all pass (`final_pmx_vmd.txt`).

### Look (`tools/review.py --baseline`)

`metrics.txt` and `shade_islands.txt` are byte-identical to the baseline. The rest mesh is unchanged.

Per-pose sleeve ratings (`baseline_look_review.md`, `final_look_review.md`):

| pose | sol before | astra before | sol after | astra after |
|---|---|---|---|---|
| arms_up | **major** (ribbon tails across the bags) | minor | minor | minor |
| reach_up_back | **major** | minor | minor | minor |
| hands_behind_head | **major** | **major** | **major** | **major** |
| walk, squat, forward_bend, head_left, swing | clean | clean | clean | clean |

- **arms_up** reaches the target: minor from both models.
- **hands_behind_head**:
  - The models now name the sharp inner-elbow fold, which is the elbow band's job (R8-2).
  - One intermediate run rated it minor from both, so single ratings of it vary.
  - The pairwise test shows no improvement there; see below.

### Pairwise shuffled A/B, old vs new (`pairwise.md`, `pairwise_xy.json`)

13 poses, sleeves only, front + 3/4 view crops.

| model | new | old | tie |
|---|---|---|---|
| gpt-6-astra | 10 | 1 | 2 |
| gpt-6.1-sol | 6 | 3 | 4 |

- Both models prefer new in arms_up, reach_up_back, dance_heart, dance_point, hug_self and idol_dance@81. The reasons given: "slimmer near the raised wrists, volume gathered toward the bands", "no pronounced upper bulb and inward pinch".
- Where one model prefers old:
  - hands_behind_head (astra): "more angular folds at the outer elbow".
  - arms_forward, dance_sway, idol_dance@80 (sol).

Images:
- `pair_arms_up.jpg`: X = new.
- `pair_reach_up_back.jpg`: Y = new.
- `pair_dance_point.jpg`: Y = new.
- `base_vs_final_raised.jpg`: rows are arms_up, reach_up_back, dance_sway and hands_behind_head. Columns are base front | 3/4 | side, then final front | 3/4 | side.

### Motion suite (`motion_delta_sleeves.md`, `motion_delta_all.md`)

| | base | new |
|---|---|---|
| all majors | 92 | 91 |
| all minors | 308 | 316 |
| sleeve majors | 9 | 8 |
| sleeve minors | 61 | 69 |

- No new major anywhere.
- The idol_dance ribbon compress major is gone (0.096 → 0.175).
- hands_behind_head ribbon penetration is gone.
- dance_heart and reach_up_back balloon stretch improve.
- The new minors:
  - ribbon compress of 0.23–0.27 in the run and lie_back poses: the tails now follow the bag's skin;
  - balloon flips of 15–24 in reach_up_back, dance_sway and hands_behind_head: these are the gathered folds.
- idol_dance (through 180°) has no pop. `baseline_c_idol_dance.jpg` and `final_c_idol_dance.jpg` show the clip.

Motion review (`baseline_motion_review.md`, `final_motion_review.md`): no sleeve pose or clip is rated major.
- reach_up_back: astra says "the openings bunch into angular folds … rather than hanging". That is the intended gathering, rated minor.
- arms_crossed: rated minor, both before and after in the pairwise test (tie).

## Remaining

- The bow tails still lie along the raised bag instead of hanging toward the shoulder. sol mentions this in arms_up (minor). Making them hang needs tail bones or physics; a shape-key flip crossed the face.
- hands_behind_head: the inner-elbow crease belongs to the elbow band. It is not tested against R8-2's narrower elbow and shoulder bands, because that branch was not pushed yet. The sleeves weight along the arm with their own knots (`SLEEVE_ARM_KNOTS`, cloth standing off the arm), and the keys are built around 腕D / ひじ / 手首 heads, so they adapt to moved pivots.
- I did not try the optional Tripo bag-fullness reference in this PR. It changes the rest mesh, so three-view IoU, shade islands and every pose would need a new baseline. Taking that risk on top of the main fix did not seem worth it. A tunable `SAG` / cuff gather in `sleeves.py` is the natural place for it.

## Notes for other units

Shared code:
- `build_rig` calls `_sleeve_ride_weights` and `_sleeve_gather` after skinning, before `_hair_collision`. These are two new lines.
- The helpers `_kd`, `_idw_near`, `_loose_labels`, `_arm_arc` and `_rigid_islands` are new and local to the sleeve section.
- Nothing existing changed signature.
- Sleeve meshes now carry shape keys. `_bake_modifiers` already handles keyed meshes.
