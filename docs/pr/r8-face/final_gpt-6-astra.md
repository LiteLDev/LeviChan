# Codex review: gpt-6-astra

The head is coherent across the supplied angles, but the lower face still reads as a broad front surface turning abruptly into an angular jaw, particularly in the three-quarter and clay views. The main correction should be a localized cheek-to-jaw volume adjustment, followed by refinement of the head's custom shading normals; increasing mesh density globally is unlikely to help because the build already has substantial lower-face loop coverage. Small shade fragments around the eyes and the profile add unnecessary visual noise, and the heavy upper lids make the neutral expression look sleepier than the reference. The six body poses show no clearly visible head-specific collapse, separation, or facial-feature drift at the supplied resolution. Scores are for the head-focused review; facial morph combinations, blinking, eye rotation, and PMX playback are not demonstrated by these images.

Scores: naturalness 7/10, animation 7/10, fidelity 8/10

## Per-pose rating

clean / minor / major / broken: parts at fault, note.

| pose | gpt-6-astra |
|---|---|
| walk | **clean** The head, facial features, and visible neck remain coherent in both walking views. |
| arms_up | **clean** The raised arms crowd the hair beside the head, but neither view establishes a visible head intersection or deformation failure. |
| squat | **clean** Within the head review scope, the lowered pose preserves the face and neck without visible collapse or displaced features. |
| forward_bend | **clean** The head follows the bend consistently, with no visible neck opening or facial-component separation. |
| head_left | **clean** The turned head keeps its eyes, mouth, and jaw together, and the exposed neck shows no obvious tearing or severe twist. |
| swing | **clean** The head remains stable in both swing views without an observable deformation defect. |

## head

- **P1** [naturalness] *q34_front_left, clay q34_front_left, clay side* - Lower cheek beside the mouth, continuing into the lateral jaw and underside of the chin: The exposed lower face reads as a relatively flat cheek ending in a pronounced diagonal jaw bevel. The clay views retain this angular transition, so the effect is not solely a toon-ramp artifact. It makes the head look more constructed and wedge-like when turned away from the calibrated front view.
  - Fix: In levi/parts/head.py, reshape the lower-face cross-sections before changing the shader. As a starting adjustment, increase LOWER_CHEEK_FILL amplitude from 0.9 to approximately 1.5–1.8 panel pixels and broaden its row sigma from 6 to 8–9 pixels, adding roughly 0.1–0.14 cm of forward fullness beside the mouth. Ease LOWER_FRONT_EXP around rows 140–148 toward approximately 2.1–2.0 to spread the turn into the side plane. Keep the centerline profile and front silhouette anchored, and redistribute the existing LOOPS_UNDER across the resulting curved jaw transition rather than adding loops globally.
- **P2** [naturalness] *q34_front_left, side, high* - Visible cheek-to-jaw shadow boundary and the throat immediately beneath the chin: A sharply defined peach strip follows the lower cheek and jaw, reinforcing the impression of a separate beveled face plate. A hard cel boundary is appropriate, but this boundary tracks a narrow anatomical transition too insistently and competes with the otherwise soft facial styling.
  - Fix: After correcting the geometry, refine shade_keep() and set_shading_normals() locally over rows approximately 136–163. Trial a broad-face real-normal share of 0.10–0.12 instead of 0.18 in this region, blended smoothly back to the surrounding values, and smooth the proxy-normal direction across the cheek-to-under-jaw loops. Preserve a coherent underside shadow rather than suppressing it entirely. Keep shade_tilts() confined to the throat so its downward bias does not exaggerate the jaw edge; check the result at intermediate yaw angles as well as the supplied views.
- **P2** [naturalness] *islands front, islands side, islands high* - Skin immediately beside the eyelid corners and along the lower facial profile: The diagnostic overlay identifies small isolated shade fragments around the eyes and facial contour. At this scale they interrupt an otherwise simple face and can read as chips or stray marks. The supplied skin-island totals also include hands and legs, so those totals cannot be attributed entirely to the head.
  - Fix: In set_shading_normals(), extend the shared smooth-normal treatment beyond the opening-wall vertices into a narrow band of adjacent skin loops at the eye corners. Use a smooth spatial falloff over approximately 1–2 panel pixels, or 0.16–0.31 cm, and trial reducing the local real-normal contribution from 0.05 toward 0.02 where isolated skin patches persist. Retain deliberate lash, mouth, and eye-detail marks; evaluate head-only shade components before and after the change rather than optimizing the whole-skin count.
- **P2** [fidelity] *sheet front versus render front, q34_front_left* - Both upper eyelids, especially the outer half of the lash line: The neutral eyes read heavier and more downturned than the reference, producing a slightly tired expression. This is most noticeable in the upper-lash coverage and outer-corner descent, rather than a need to enlarge the whole eye or head.
  - Fix: In upper_lid(), trial reducing the outer-side drop coefficient from 5.4 to approximately 4.2–4.6 panel pixels. In lash_thick(), reduce the outer thickening term from 1.1 to about 0.7–0.8 while retaining the inner taper. Regenerate the eye-opening patches and lash decals from these curves together, then recheck closure morphs and lid-to-eyeball clearance so the expression adjustment does not create a blink gap.

