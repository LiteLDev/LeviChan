# Review summary

Focus: head

| model | naturalness | animation | fidelity | findings |
|---|---|---|---|---|
| gpt-6.1-sol | 6 | 7 | 7 | 4 |
| gpt-6-astra | 7 | 7 | 8 | 4 |

**gpt-6.1-sol:** The head holds together across the supplied views, but the three-quarter and clay renders still expose a broad, rather planar lower face and overly prominent eyelid volumes. The most useful next step is to refine the cheek-to-chin curvature and reduce the socket rims before making further silhouette adjustments against the sheet. Facial cel shading also needs a more continuous normal field: the cheek shadow reads as a separate angular strip, and small fragments around the eyes interrupt otherwise pale skin. No clear head-specific clipping, detached facial pieces, or neck collapse is visible in the six pose tests. These scores are head-focused; the pose sheet does not demonstrate blinking, mouth morphs, or eye-bone rotation, so those aspects of animation readiness remain unverified.

**gpt-6-astra:** The head is coherent across the supplied angles, but the lower face still reads as a broad front surface turning abruptly into an angular jaw, particularly in the three-quarter and clay views. The main correction should be a localized cheek-to-jaw volume adjustment, followed by refinement of the head's custom shading normals; increasing mesh density globally is unlikely to help because the build already has substantial lower-face loop coverage. Small shade fragments around the eyes and the profile add unnecessary visual noise, and the heavy upper lids make the neutral expression look sleepier than the reference. The six body poses show no clearly visible head-specific collapse, separation, or facial-feature drift at the supplied resolution. Scores are for the head-focused review; facial morph combinations, blinking, eye rotation, and PMX playback are not demonstrated by these images.

## Priority 1 across all parts

- **head** (gpt-6-astra) [naturalness] Lower cheek beside the mouth, continuing into the lateral jaw and underside of the chin: The exposed lower face reads as a relatively flat cheek ending in a pronounced diagonal jaw bevel. The clay views retain this angular transition, so the effect is not solely a toon-ramp artifact. It makes the head look more constructed and wedge-like when turned away from the calibrated front view.

## Per-pose rating

clean / minor / major / broken: parts at fault, note.

| pose | gpt-6.1-sol | gpt-6-astra |
|---|---|---|
| walk | **clean** No visible head or neck deformation fault appears in either walking view. | **clean** The head, facial features, and visible neck remain coherent in both walking views. |
| arms_up | **clean** The jaw, neck, and facial features remain intact with both arms raised. | **clean** The raised arms crowd the hair beside the head, but neither view establishes a visible head intersection or deformation failure. |
| squat | **clean** The head and neck retain their volume without visible facial displacement in either squat view. | **clean** Within the head review scope, the lowered pose preserves the face and neck without visible collapse or displaced features. |
| forward_bend | **clean** The inclined head remains connected to the neck without a visible throat crease, tear, or facial layer separation. | **clean** The head follows the bend consistently, with no visible neck opening or facial-component separation. |
| head_left | **clean** The turned head carries its eyes, mouth, and jaw together, with no obvious neck collapse or attachment left behind. | **clean** The turned head keeps its eyes, mouth, and jaw together, and the exposed neck shows no obvious tearing or severe twist. |
| swing | **clean** No head-specific stretching or clipping is visible during the supplied swing pose. | **clean** The head remains stable in both swing views without an observable deformation defect. |

## By part

### head

- **P1** [naturalness] (gpt-6-astra) *q34_front_left, clay q34_front_left, clay side* - Lower cheek beside the mouth, continuing into the lateral jaw and underside of the chin: The exposed lower face reads as a relatively flat cheek ending in a pronounced diagonal jaw bevel. The clay views retain this angular transition, so the effect is not solely a toon-ramp artifact. It makes the head look more constructed and wedge-like when turned away from the calibrated front view.
  - Fix: In levi/parts/head.py, reshape the lower-face cross-sections before changing the shader. As a starting adjustment, increase LOWER_CHEEK_FILL amplitude from 0.9 to approximately 1.5–1.8 panel pixels and broaden its row sigma from 6 to 8–9 pixels, adding roughly 0.1–0.14 cm of forward fullness beside the mouth. Ease LOWER_FRONT_EXP around rows 140–148 toward approximately 2.1–2.0 to spread the turn into the side plane. Keep the centerline profile and front silhouette anchored, and redistribute the existing LOOPS_UNDER across the resulting curved jaw transition rather than adding loops globally.
- **P2** [naturalness] (gpt-6.1-sol) *q34_front_left, clay q34_front_left, clay side* - Lower cheek between the outer eye, mouth corner, and chin: The lower face presents a broad, relatively flat cheek plane followed by a short turn into the chin and underside of the jaw. The three-quarter view consequently reads more like a beveled mask than a soft cheek wrapping around a skull; the clay view shows that shading alone is not responsible.
  - Fix: In levi/parts/head.py, bring LOWER_FRONT_EXP toward an elliptical section earlier: try approximately 2.15 at row 140 and 2.0 at row 148. Broaden LOWER_CHEEK_FILL's row sigma from 6 to about 9 px and add only 0.5–1 px of forward fullness across the middle cheek, fading to zero at the midline and silhouette. Rebuild the detail=False normal source from the revised surface and judge the result at intermediate turntable angles before changing TABLE's calibrated outline.
- **P2** [naturalness] (gpt-6.1-sol) *clay front, clay q34_front_left, clay high* - Lower eyelid rims and skin immediately below both eye openings: The eyelid surrounds form conspicuous raised cushions in clay, especially beneath the eyes. They give the sockets a swollen, applied-on appearance rather than a thin lid draped over an eyeball; the cel material conceals much of this excess relief.
  - Fix: Reduce the lower-lid forward displacement in relief() by roughly 30–40%, blending it into the cheek over 3–4 panel pixels instead of retaining a narrow ridge. Keep the opening edge seated on the fitted eyeball through hug(), and move the surrounding patch loops rather than shrinking the eyeball. Preserve the opening vertices and regenerate the lid morph targets so the correction does not introduce a gap during closure.
- **P2** [naturalness] (gpt-6.1-sol) *q34_front_left, side, high, islands front, islands high* - Outer cheek below the visible eye, jaw transition, and eye-opening corners: The peach shade forms a narrow angular cheek-to-jaw strip, while small disconnected fragments remain around the eyelids. Together these make the face look locally cut into planes despite its otherwise soft treatment. The red island diagnostic includes intentional facial marks, so its skin totals should not all be treated as shading defects.
  - Fix: After the geometry changes, adjust set_shading_normals() locally: lower the real-normal contribution around the outer eye and upper cheek toward 0.02–0.05, then blend continuously into the broad cheek normal over 6–10 px. Check that the opening-to-patch boundary has no abrupt normal change and retain the existing rim_of normal sharing. Tune the cheek normal field to produce one connected shadow boundary; exclude the mouth line, lashes, and painted features when assessing residual islands.
- **P2** [naturalness] (gpt-6-astra) *q34_front_left, side, high* - Visible cheek-to-jaw shadow boundary and the throat immediately beneath the chin: A sharply defined peach strip follows the lower cheek and jaw, reinforcing the impression of a separate beveled face plate. A hard cel boundary is appropriate, but this boundary tracks a narrow anatomical transition too insistently and competes with the otherwise soft facial styling.
  - Fix: After correcting the geometry, refine shade_keep() and set_shading_normals() locally over rows approximately 136–163. Trial a broad-face real-normal share of 0.10–0.12 instead of 0.18 in this region, blended smoothly back to the surrounding values, and smooth the proxy-normal direction across the cheek-to-under-jaw loops. Preserve a coherent underside shadow rather than suppressing it entirely. Keep shade_tilts() confined to the throat so its downward bias does not exaggerate the jaw edge; check the result at intermediate yaw angles as well as the supplied views.
- **P2** [naturalness] (gpt-6-astra) *islands front, islands side, islands high* - Skin immediately beside the eyelid corners and along the lower facial profile: The diagnostic overlay identifies small isolated shade fragments around the eyes and facial contour. At this scale they interrupt an otherwise simple face and can read as chips or stray marks. The supplied skin-island totals also include hands and legs, so those totals cannot be attributed entirely to the head.
  - Fix: In set_shading_normals(), extend the shared smooth-normal treatment beyond the opening-wall vertices into a narrow band of adjacent skin loops at the eye corners. Use a smooth spatial falloff over approximately 1–2 panel pixels, or 0.16–0.31 cm, and trial reducing the local real-normal contribution from 0.05 toward 0.02 where isolated skin patches persist. Retain deliberate lash, mouth, and eye-detail marks; evaluate head-only shade components before and after the change rather than optimizing the whole-skin count.
- **P2** [fidelity] (gpt-6-astra) *sheet front versus render front, q34_front_left* - Both upper eyelids, especially the outer half of the lash line: The neutral eyes read heavier and more downturned than the reference, producing a slightly tired expression. This is most noticeable in the upper-lash coverage and outer-corner descent, rather than a need to enlarge the whole eye or head.
  - Fix: In upper_lid(), trial reducing the outer-side drop coefficient from 5.4 to approximately 4.2–4.6 panel pixels. In lash_thick(), reduce the outer thickening term from 1.1 to about 0.7–0.8 while retaining the inner taper. Regenerate the eye-opening patches and lash decals from these curves together, then recheck closure morphs and lid-to-eyeball clearance so the expression adjustment does not create a blink gap.
- **P3** [fidelity] (gpt-6.1-sol) *front, q34_front_left* - Upper lash bands and visible opening of both eyes: The rendered eyes read slightly heavier and sleepier than the sheet: the dark upper lash mass occupies more of the visible eye, reducing the open green-eyed expression. This is a local feature-shape difference rather than a reason to enlarge the whole head or eyeballs.
  - Fix: In lash_thick(), trial a reduction of about 0.4–0.6 panel px through the middle of each upper lid, retaining the tapered corners and outer flick. Because lash_bottom() also defines the opening, rebuild the eye patches, lash geometry, and morph targets together. Compare the neutral front and three-quarter views before changing iris size or eye spacing.

## Metrics vs baseline `..\..\..\..\..\AppData\Local\Temp\claude\C--Users-futri-Desktop-LeviChan--claude-worktrees-levi-character-modeling-771bd2\adb9fe91-4f41-4ccb-9de8-2dd654b3b7a5\scratchpad\r8_face\review_base`

Per view and region, `new (delta)`; `*` = whole view (silhouette IoU, island total). iou/tol up is better; dE/dEi (interior colour error), islands and island_px down is better; shade is the render's shade share (compare with the sheet in shade_stats.txt).

| view | region | iou | tol | dE | dEi | shade | islands | island_px |
|---|---|---|---|---|---|---|---|---|
| front | * | 0.915 (+0.000) |  |  |  |  | 45 (+1) | 935 (+15) |
| front | green | 0.393 (-0.000) | 0.803 (-0.000) | 17.3 (+0.0) | 15.7 (+0.0) | 0.330 (+0.000) | 17 (+0) | 390 (+0) |
| front | skin | 0.780 (-0.000) | 0.956 (-0.000) | 6.4 (-0.1) | 3.3 (+0.0) | 0.150 (+0.000) | 11 (+1) | 343 (+15) |
| high | * |  |  |  |  |  | 47 (+0) | 1007 (+2) |
| high | green |  |  |  |  |  | 18 (+0) | 483 (+2) |
| q34_front_left | * |  |  |  |  |  | 40 (+1) | 691 (+10) |
| q34_front_left | skin |  |  |  |  |  | 8 (+1) | 158 (+10) |
| side | green | 0.312 (-0.000) | 0.639 (+0.000) | 18.0 (+0.1) | 14.9 (+0.0) | 0.440 (+0.000) | 9 (+0) | 213 (+0) |
| side | skin | 0.635 (+0.000) | 0.846 (-0.000) | 6.0 (+0.0) | 3.1 (+0.0) | 0.220 (+0.000) | 4 (+0) | 121 (+0) |

