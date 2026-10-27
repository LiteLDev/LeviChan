# Review summary

Focus: skirt

| model | naturalness | animation | fidelity | findings |
|---|---|---|---|---|
| gpt-6.1-sol | 5 | 6 | 6 | 7 |
| gpt-6-astra | 5 | 5 | 6 | 7 |

**gpt-6.1-sol:** The skirt reads as a continuous bell, but the clay and three-quarter views expose a broad, relatively flat rear-side panel and an uneven ridge above the hem that make it feel more like a molded shell than hanging fabric. Its most urgent animation issue is the squat: the front lifts into a broad shelf while the side stretches into a long wedge, exposing the petticoat instead of gathering into rounded folds around the thighs. Reconstruct the lower-skirt surface with continuous longitudinal curvature before adjusting its shading normals, then refine the sector drape around the raised legs. Fidelity work should concentrate on the hem's fold rhythm and the amount of pink underskirt revealed, rather than pursuing the already high front and back silhouette IoU. These ratings assess the supplied Blender stills; they do not establish equivalent deformation or collision behavior after PMX export.

**gpt-6-astra:** The skirt has a continuous, adequately sampled shell, but its lower half still reads as a stiff bell with localized dents and a projecting rear panel rather than softly supported fabric. The clearest naturalness problems are the shelf-like rear hem in side and three-quarter views, uneven lower-fold curvature in clay, and fragmented cel-shadow boundaries. Walk and squat expose an animation issue: the front panels lift and spread into broad shelves, with insufficient gathering between the raised cloth and the hanging sides. Fix the sampled surface and skirt-chain response before refining reference fidelity; the reference's deeper hem scallops and greater petticoat exposure should then be recovered through coordinated outer-layer shaping. These scores are skirt-focused, and the supplied Blender pose stills do not establish that the different PMX follow-and-physics setup will reproduce their behavior.

## Priority 1 across all parts

- **skirt** (gpt-6.1-sol) [naturalness] Rear-side lower skirt, from approximately mid-thigh height to the trailing hem: A broad side panel descends almost as a straight triangular sheet and finishes in a projecting rear corner. The three-quarter view exposes a large planar area between the rounded front folds and the back, so the volume reads as a rigid cone panel rather than cloth supported by the petticoat.
- **skirt** (gpt-6.1-sol) [naturalness] Lower front and front-side folds, roughly 3–6 cm above the hem: Several folds swell into rounded knobs and then cross an approximately horizontal ridge before reaching the edge. This interruption is visible without cel shading, so changing the ramp alone will leave the skirt looking inflated or molded.
- **skirt** (gpt-6-astra) [naturalness] Rear lower third, from below the hair tips to the trailing hem at image-right in the side view: The rear panel projects into a long, comparatively straight wedge with an abrupt terminal edge. The clay view confirms that this is a surface-shape problem, not just a cel outline; it makes the skirt look like a stiff plate extending behind the wearer.
- **skirt** (gpt-6.1-sol) [animation] Front hem over both thighs and the transition into the side skirt panels: The front is lifted as a wide shelf, while the side remains stretched into a long diagonal wedge. The large exposed pink underside makes the loss of hanging cloth especially apparent; the skirt clears the legs at the expense of believable fold compression.
- **skirt** (gpt-6-astra) [animation] Front hem above the advancing thigh and its transition into the adjacent side panels: The stride lifts a wide area of the front skirt into a shelf, with a sharp change between the lifted section and the hanging cloth. This reads as neighboring panels being carried by the thigh rather than fabric redistributing its folds around it; there is no need to infer hidden leg penetration to identify the visible deformation problem.
- **skirt** (gpt-6-astra) [animation] Lower front panel spanning both knees, especially the front-to-side hem transition: With both thighs raised, the front becomes a broad outward-facing apron and the adjacent hem forms a stiff ledge. The skirt opens around the pose, but does not develop enough local hanging folds to make the displacement look like cloth.

## Per-pose rating

clean / minor / major / broken: parts at fault, note.

| pose | gpt-6.1-sol | gpt-6-astra |
|---|---|---|
| walk | **minor** (skirt) The lifted front hem develops a short, angular crest above the advancing thigh, most visible in the three-quarter view, although the shell remains continuous. | **major** (skirt) Above the advancing thigh, the front hem rises into a broad, nearly horizontal shelf, particularly in the three-quarter view, instead of gathering locally around the leg. |
| arms_up | **clean** No visible skirt deformation or new skirt intersection appears when the arms rise. | **clean** The skirt remains attached at the waist without a visible new collapse, tear or intersection in either supplied view. |
| squat | **major** (skirt, rig) The front skirt rises into a broad shelf above the knees while the three-quarter side forms a stretched wedge rather than gathering around the bent thighs. | **major** (skirt) The front skirt spreads into a lifted apron across both knees while the side and rear panels remain extended, creating an overly rigid shelf in the three-quarter view. |
| forward_bend | **clean** The skirt retains a continuous waist and hem without a clearly visible new collapse, tear or penetration. | **clean** The skirt maintains its waist connection and continuous surface without an unambiguous new skirt deformation defect at this bend depth. |
| head_left | **clean** The head turn causes no visible skirt deformation or new contact problem. | **clean** No visible skirt deformation or new skirt intersection is introduced by the head turn. |
| swing | **clean** The skirt remains continuous and shows no clearly visible deformation failure in this sampled pose. | **clean** The supplied swing stills show no clear skirt collapse, tearing or clipping. |

## By part

### skirt

- **P1** [naturalness] (gpt-6.1-sol) *clay side, clay q34_back_right, q34_front_left* - Rear-side lower skirt, from approximately mid-thigh height to the trailing hem: A broad side panel descends almost as a straight triangular sheet and finishes in a projecting rear corner. The three-quarter view exposes a large planar area between the rounded front folds and the back, so the volume reads as a rigid cone panel rather than cloth supported by the petticoat.
  - Fix: In skirt.py, regularize the sampled radius field in _target() over the rear-side sectors before profiles() builds the shell. Replace the long straight radial descent with a gently curved longitudinal profile and two broad fold transitions; start by reducing the projecting lower corner by 1–2 cm and distributing that change across the lower 8–12 cm. Use a monotone cubic profile through the corrected samples instead of relying on slope clipping followed by linear interpolation, and preserve the existing inner clearance when rebuilding the petticoat.
- **P1** [naturalness] (gpt-6.1-sol) *clay front, clay q34_front_left, clay high* - Lower front and front-side folds, roughly 3–6 cm above the hem: Several folds swell into rounded knobs and then cross an approximately horizontal ridge before reaching the edge. This interruption is visible without cel shading, so changing the ramp alone will leave the skirt looking inflated or molded.
  - Fix: In _target(), smooth the longitudinal second differences of the radius residual specifically through the lower fold band, while retaining broad circumferential crest positions. Blend out isolated radial bulges by about 0.5–1 cm over a 4–6 cm vertical span, with a continuous first derivative at both ends. Make each principal fold run into its hem lobe without the common transverse shoulder; retain the shell's existing thin rounded edge.
- **P1** [naturalness] (gpt-6-astra) *side; q34_back_right; clay side* - Rear lower third, from below the hair tips to the trailing hem at image-right in the side view: The rear panel projects into a long, comparatively straight wedge with an abrupt terminal edge. The clay view confirms that this is a surface-shape problem, not just a cel outline; it makes the skirt look like a stiff plate extending behind the wearer.
  - Fix: In levi/parts/skirt.py, revise the rear-sector radius field in _target() before _dense() consumes it. Start by pulling the last 20–25% of the rear profiles inward by approximately 2–3 cm, fading the correction smoothly around the rear quarters and upward. Replace the prolonged outward slope with a curved transition that becomes more vertical near the hem; make TGT_FLARE sector-dependent rather than flattening all folds with a global reduction. Keep section(), profiles() and front_surface_y() derived from the corrected field so dependent layers follow.
- **P1** [animation] (gpt-6.1-sol) *squat front, squat q34_front_left* - Front hem over both thighs and the transition into the side skirt panels: The front is lifted as a wide shelf, while the side remains stretched into a long diagonal wedge. The large exposed pink underside makes the loss of hanging cloth especially apparent; the skirt clears the legs at the expense of believable fold compression.
  - Fix: Refine the skirt drape in rig.py so clearance lift stays local to the thigh-facing sectors and adjacent side sectors gather toward them at a lower height. In _drape_gather, trial reducing the free ring strain DRAPE_STRAIN from 0.30 to 0.20 and increasing the strain cost, while retaining the existing neighbor caps initially. If the three-segment chains still force a single long side plane, use four segments with a joint near the lower fold transition and recompute the drape tables and _skirt_weights interpolation. Keep outer, inner and rolled-hem vertices sharing the same cloth weights, and check both squat views after each adjustment so reduced stretch does not recreate a lifted bowl.
- **P1** [animation] (gpt-6-astra) *walk front; walk q34_front_left* - Front hem above the advancing thigh and its transition into the adjacent side panels: The stride lifts a wide area of the front skirt into a shelf, with a sharp change between the lifted section and the hanging cloth. This reads as neighboring panels being carried by the thigh rather than fabric redistributing its folds around it; there is no need to infer hidden leg penetration to identify the visible deformation problem.
  - Fix: Retain the existing 30 longitudinal rings and 360 azimuth samples. In levi/rig.py, adjust _skirt_drape() and its neighbor-gather calculation so thigh clearance is solved locally first, then adjacent sectors gather circumferentially without inheriting unnecessary root lift. Penalize changes in deformed ring-edge lengths and abrupt differences between adjacent segment tangents, not only differences in chain angles. Inspect _skirt_weights() at the lifted-to-hanging transition and soften its angular blend while retaining the four-influence PMX limit. Rebuild the drape tables after reshaping the rest skirt.
- **P1** [animation] (gpt-6-astra) *squat front; squat q34_front_left* - Lower front panel spanning both knees, especially the front-to-side hem transition: With both thighs raised, the front becomes a broad outward-facing apron and the adjacent hem forms a stiff ledge. The skirt opens around the pose, but does not develop enough local hanging folds to make the displacement look like cloth.
  - Fix: Add a bilateral-thigh correction to _skirt_drape() rather than relying solely on the combination of independent thigh solutions. Preserve necessary clearance at the upper segment, then let the lower two segments hang downward where the knee and shin envelopes permit. Couple the center-front and neighboring sectors through a ring-length constraint so gathering replaces outward spreading. Validate the correction on the shared skirt/petticoat envelope, and reproduce the intended response in PMX follow shares and joint limits rather than relying on a Blender-only correction.
- **P2** [naturalness] (gpt-6.1-sol) *high, q34_front_left, islands high* - Front-right fold faces and scattered lower-front and hem shadow boundaries: The pale cloth has stepped, narrow shadow streaks and disconnected slivers rather than a few broad fold shadows. The high view contains 13 dress-region islands covering 315 pixels; that region also includes the bodice and sleeves, but several marked fragments are visibly on the skirt.
  - Fix: After correcting the surface, reduce the amount of fine sampled relief retained by skirt.py's _shade_normals: trial RELIEF_SHADE at 0.35–0.45 instead of 0.60 and increase RELIEF_SOFT_PX from 10 to approximately 14. Smooth the reference normals vertically as well as around the circumference, then normalize and blend them continuously through the hem-roll transition. Retain the broad fold turns; do not remove islands by changing the global ramp until the skirt's own normal field is clean.
- **P2** [naturalness] (gpt-6-astra) *clay front; clay q34_front_left; clay high* - Lower third of the front and front-quarter panels, just above the hem: Several folds end in swollen bumps and shallow transverse dents instead of flowing continuously down to the edge. These irregularities are visible in diffuse clay and make the fabric look molded or crumpled at isolated points.
  - Fix: Regularize the target radius residual in _target() along height as well as around the circumference. Replace bilinear target_radius() sampling with slope-continuous, bounded interpolation along rows, and blend across the points where the TGT_TUCK/TGT_FLARE slope clamp engages. As an initial local correction, reduce short residual bumps by about 30–50% over the last 8–12 cm while preserving the broad fold crests. Do not increase N_PHI globally; the current topology already samples these unwanted shapes densely.
- **P2** [naturalness] (gpt-6-astra) *high; q34_front_left; islands high; islands front* - Front-right fold-shadow boundary in image space, scattered mid-skirt slivers and small dark wedges along the hem: The pale fabric has jagged, intermittently detached shade fragments instead of a few deliberate fold shadows. The high-view dress mask reports 13 islands totaling 315 pixels, although that mask also includes the bodice and sleeves; the visible skirt slivers independently confirm the problem.
  - Fix: After correcting the geometry, make the Nsoft field used by _shade_normals() smooth along height as well as azimuth. Trial RELIEF_SHADE around 0.35–0.45 instead of 0.6, with the additional smoothing confined to noisy lower-fold areas and faded out at silhouette-defining creases. Recompute the hem-roll normal transition from the same field so small dark wedges do not reappear at the edge. Validate through intermediate camera angles with a fixed light as well as the supplied camera-relative lighting; do not move the global toon threshold merely to erase skirt artifacts.
- **P2** [animation] (gpt-6.1-sol) *walk front, walk q34_front_left* - Front hem immediately above the advancing thigh: The lifted lobe has a localized angular peak where the raised panel joins the neighboring hem. It is a small deformation defect here, but it interrupts the rounded fold contour during an ordinary stride.
  - Fix: In rig.py, inspect the two skirt chains bracketing this peak and spread their lift difference over the adjacent sectors using the existing gather stage. Smooth the vertical weight transition around the lower segment boundary over approximately 1–2 cm, preserving the maximum four influences and shared shell weights. Evaluate the walk pose at intermediate thigh pitches to check that the peak does not simply move to the next sector.
- **P2** [fidelity] (gpt-6.1-sol) *front, side, back in 01_ortho_sbs* - Entire hem circumference, especially the front-side arches and back edge: The model's edge is comparatively level and shallowly scalloped, with a narrow pink strip beneath it. The reference has larger alternating dropped lobes and raised arches that reveal substantially more petticoat. The missing rhythm changes the skirt's design even where the overall silhouette overlaps well.
  - Fix: Adjust target_hem() and the hem rows used in _dense() with a smooth periodic correction tied to the existing broad fold crests. Begin by raising the shallow arches by 1–2 cm, leaving the lowest lobes close to their current height, and ease the height correction through the lower 6–8 cm of profiles(). Keep SMOOTH_ROW_PX sufficient to round the arch tops. Rebuild the dependent petticoat from the revised surface and inspect the newly revealed inner hem in three-quarter views before increasing the correction.
- **P2** [fidelity] (gpt-6-astra) *sheet front versus render front; sheet back versus render back; sheet side versus render side* - Entire lower outline, particularly the lifted arches between the front and rear hem lobes: The outer hem has become a shallow, nearly continuous scalloped band. The reference alternates substantially deeper hanging lobes with lifted arches and turned edges, exposing much more pink underskirt. The current outer layer conceals that structure and makes the dress read as a simpler cone; low petticoat coverage supports this observation but does not by itself identify which layer caused it.
  - Fix: In target_hem() and the hem-row construction in _dense(), introduce a sparse, smooth correction curve that raises selected inter-lobe arches by an initial 2–4 cm while keeping the lowest lobes and waistband stable. Blend each change over a broad angular interval and the final 15–20% of the profile so it produces a rounded cloth turn rather than a notch. Recompute dependent petticoat clearance from shell() after the change, retaining roughly 0.5–1 cm separation where the two layers overlap. Recover the reference rhythm without tracing its painted contour into narrow fins.
- **P3** [fidelity] (gpt-6.1-sol) *front, back, q34_back_right* - Broad lower-skirt fold faces between the waist and hem: Large areas of the skirt remain nearly uniform ivory, while the reference separates its folds with more deliberate pale mint coloration. This contributes to the broad panels reading as empty areas; the supplied dress shade shares are also lower than the reference in front and back, although those measurements include other garments.
  - Fix: Once the geometry and normal field are stable, derive skirt.py's mint tint from the final sampled fold residual rather than only the approximate fold-table streak positions. Apply a broad, smoothly feathered tint on the recessed fold faces, increasing local gradient weight by approximately 0.05–0.10 as an initial trial. Keep the upper skirt light and evaluate the gradient in both toon tones so the added mint does not become a separate hard stripe.
- **P3** [fidelity] (gpt-6-astra) *render front; render back; q34_front_left* - Broad lower skirt panels between the main folds: Large panels remain nearly uniform ivory, so the pale mint turning planes contribute less depth than in the reference. This is separate from the small dark shade fragments: increasing shadow coverage alone would not restore the soft fabric coloration.
  - Fix: After the shape and shading fixes, drive the dress_mint attribute from the corrected broad fold field, with continuous height interpolation. Trial a modest increase of STREAK from 0.08 toward 0.12–0.16 on the broad turned-away faces, retaining the existing feathering and excluding tiny target residuals. Inspect the color attribute separately from lighting before adjusting Z_MINT, and keep the mint transition continuous rather than quantizing it into another hard band.

## Metrics vs baseline `out\main_src\out\review_main`

Per view and region, `new (delta)`; `*` = whole view (silhouette IoU, island total). iou/tol up is better; dE/dEi (interior colour error), islands and island_px down is better; shade is the render's shade share (compare with the sheet in shade_stats.txt).

| view | region | iou | tol | dE | dEi | shade | islands | island_px |
|---|---|---|---|---|---|---|---|---|
| back | * | 0.919 (+0.001) |  |  |  |  | 28 (-5) | 640 (-209) |
| back | dress | 0.638 (+0.011) | 0.832 (+0.006) | 6.5 (+0.1) | 5.6 (+0.1) | 0.190 (+0.010) | 2 (-2) | 78 (-86) |
| back | green | 0.262 (-0.001) | 0.568 (-0.001) | 15.5 (+0.0) | 10.0 (+0.0) | 0.480 (+0.000) | 1 (+0) | 4 (+0) |
| back | hair | 0.695 (+0.000) | 0.867 (-0.001) | 9.3 (-0.1) | 7.9 (+0.0) | 0.270 (+0.000) | 21 (-1) | 377 (-37) |
| back | petticoat | 0.224 (-0.178) | 0.453 (-0.201) | 11.4 (+1.2) | 9.4 (+0.6) | 0.450 (+0.230) | 1 (-2) | 71 (-86) |
| back | skin | 0.680 (+0.014) | 0.868 (+0.011) | 5.8 (-0.2) | 3.1 (-0.2) | 0.210 (+0.030) | 3 (+0) | 110 (+0) |
| front | * | 0.915 (-0.001) |  |  |  |  | 42 (+3) | 949 (+95) |
| front | dress | 0.763 (-0.022) | 0.917 (-0.013) | 6.1 (-0.1) | 5.1 (-0.1) | 0.180 (-0.020) | 9 (+3) | 72 (+41) |
| front | green | 0.394 (+0.000) | 0.803 (-0.002) | 17.2 (-0.1) | 15.6 (+0.0) | 0.320 (+0.000) | 16 (+0) | 394 (+0) |
| front | petticoat | 0.293 (-0.070) | 0.535 (-0.083) | 9.8 (+0.2) | 8.2 (+0.1) | 0.280 (+0.070) | 1 (+0) | 69 (+54) |
| front | skin | 0.782 (-0.002) | 0.958 (-0.001) | 6.3 (-0.1) | 3.3 (-0.1) | 0.170 (+0.020) | 9 (+0) | 218 (+0) |
| high | * |  |  |  |  |  | 46 (+8) | 1061 (+224) |
| high | dress |  |  |  |  |  | 13 (+7) | 315 (+169) |
| high | green |  |  |  |  |  | 16 (+0) | 358 (+1) |
| high | petticoat |  |  |  |  |  | 1 (+1) | 54 (+54) |
| q34_back_right | * |  |  |  |  |  | 22 (-1) | 589 (-58) |
| q34_back_right | dress |  |  |  |  |  | 7 (+5) | 180 (+63) |
| q34_back_right | hair |  |  |  |  |  | 9 (-4) | 177 (-109) |
| q34_back_right | petticoat |  |  |  |  |  | 1 (-2) | 36 (-12) |
| q34_front_left | * |  |  |  |  |  | 45 (+3) | 892 (+49) |
| q34_front_left | dress |  |  |  |  |  | 4 (+1) | 128 (-22) |
| q34_front_left | petticoat |  |  |  |  |  | 4 (+3) | 169 (+119) |
| q34_front_left | skin |  |  |  |  |  | 11 (-1) | 294 (-48) |
| side | * | 0.840 (-0.021) |  |  |  |  | 30 (-4) | 662 (-97) |
| side | dress | 0.654 (-0.095) | 0.841 (-0.067) | 7.4 (-0.2) | 6.5 (-0.2) | 0.270 (+0.000) | 3 (-3) | 43 (-98) |
| side | green | 0.321 (+0.006) | 0.648 (+0.011) | 18.0 (+0.1) | 15.1 (+0.0) | 0.460 (+0.010) | 8 (-1) | 252 (-31) |
| side | hair | 0.671 (-0.001) | 0.852 (-0.002) | 11.2 (+0.1) | 10.1 (+0.1) | 0.520 (+0.000) | 14 (-1) | 177 (-23) |
| side | petticoat | 0.270 (-0.083) | 0.505 (-0.104) | 10.4 (-0.2) | 8.3 (-0.9) | 0.320 (-0.020) | 1 (+1) | 55 (+55) |
| side | skin | 0.647 (-0.004) | 0.851 (-0.003) | 6.1 (+0.0) | 3.2 (+0.0) | 0.230 (+0.010) | 4 (+0) | 135 (+0) |

## Shape-master fit vs baseline

target->ours distance (mm, down is better) and covered share (up is better), from tools/shape_fit.py: `new (delta)`.

| part | p50 mm | p90 mm | covered |
|---|---|---|---|
| body | 8.6 (+0.0) | 24.2 (+0.0) | 0.312 (+0.000) |
| head | 6.2 (+0.0) | 19.8 (+0.0) | 0.426 (+0.000) |
| hair_front | 4.5 (+0.0) | 14.9 (+0.0) | 0.535 (+0.000) |
| hair_back | 24.6 (-0.8) | 73.4 (-3.9) | 0.173 (+0.003) |
| accessories | 4.7 (+0.0) | 11.6 (+0.0) | 0.522 (+0.000) |
| bodice | 9.2 (+0.1) | 21.2 (-4.7) | 0.259 (-0.005) |
| skirt | 13.7 (-0.9) | 37.1 (-11.2) | 0.260 (+0.056) |
| petticoat | 14.0 (+0.3) | 34.2 (-0.3) | 0.192 (+0.002) |
| sleeves | 11.7 (+0.0) | 27.4 (+0.0) | 0.240 (+0.000) |
| shoes | 7.4 (+0.0) | 18.7 (+0.0) | 0.347 (+0.000) |

