# Codex review: gpt-6.1-sol

The head holds together across the supplied views, but the three-quarter and clay renders still expose a broad, rather planar lower face and overly prominent eyelid volumes. The most useful next step is to refine the cheek-to-chin curvature and reduce the socket rims before making further silhouette adjustments against the sheet. Facial cel shading also needs a more continuous normal field: the cheek shadow reads as a separate angular strip, and small fragments around the eyes interrupt otherwise pale skin. No clear head-specific clipping, detached facial pieces, or neck collapse is visible in the six pose tests. These scores are head-focused; the pose sheet does not demonstrate blinking, mouth morphs, or eye-bone rotation, so those aspects of animation readiness remain unverified.

Scores: naturalness 6/10, animation 7/10, fidelity 7/10

## Per-pose rating

clean / minor / major / broken: parts at fault, note.

| pose | gpt-6.1-sol |
|---|---|
| walk | **clean** No visible head or neck deformation fault appears in either walking view. |
| arms_up | **clean** The jaw, neck, and facial features remain intact with both arms raised. |
| squat | **clean** The head and neck retain their volume without visible facial displacement in either squat view. |
| forward_bend | **clean** The inclined head remains connected to the neck without a visible throat crease, tear, or facial layer separation. |
| head_left | **clean** The turned head carries its eyes, mouth, and jaw together, with no obvious neck collapse or attachment left behind. |
| swing | **clean** No head-specific stretching or clipping is visible during the supplied swing pose. |

## head

- **P2** [naturalness] *q34_front_left, clay q34_front_left, clay side* - Lower cheek between the outer eye, mouth corner, and chin: The lower face presents a broad, relatively flat cheek plane followed by a short turn into the chin and underside of the jaw. The three-quarter view consequently reads more like a beveled mask than a soft cheek wrapping around a skull; the clay view shows that shading alone is not responsible.
  - Fix: In levi/parts/head.py, bring LOWER_FRONT_EXP toward an elliptical section earlier: try approximately 2.15 at row 140 and 2.0 at row 148. Broaden LOWER_CHEEK_FILL's row sigma from 6 to about 9 px and add only 0.5–1 px of forward fullness across the middle cheek, fading to zero at the midline and silhouette. Rebuild the detail=False normal source from the revised surface and judge the result at intermediate turntable angles before changing TABLE's calibrated outline.
- **P2** [naturalness] *clay front, clay q34_front_left, clay high* - Lower eyelid rims and skin immediately below both eye openings: The eyelid surrounds form conspicuous raised cushions in clay, especially beneath the eyes. They give the sockets a swollen, applied-on appearance rather than a thin lid draped over an eyeball; the cel material conceals much of this excess relief.
  - Fix: Reduce the lower-lid forward displacement in relief() by roughly 30–40%, blending it into the cheek over 3–4 panel pixels instead of retaining a narrow ridge. Keep the opening edge seated on the fitted eyeball through hug(), and move the surrounding patch loops rather than shrinking the eyeball. Preserve the opening vertices and regenerate the lid morph targets so the correction does not introduce a gap during closure.
- **P2** [naturalness] *q34_front_left, side, high, islands front, islands high* - Outer cheek below the visible eye, jaw transition, and eye-opening corners: The peach shade forms a narrow angular cheek-to-jaw strip, while small disconnected fragments remain around the eyelids. Together these make the face look locally cut into planes despite its otherwise soft treatment. The red island diagnostic includes intentional facial marks, so its skin totals should not all be treated as shading defects.
  - Fix: After the geometry changes, adjust set_shading_normals() locally: lower the real-normal contribution around the outer eye and upper cheek toward 0.02–0.05, then blend continuously into the broad cheek normal over 6–10 px. Check that the opening-to-patch boundary has no abrupt normal change and retain the existing rim_of normal sharing. Tune the cheek normal field to produce one connected shadow boundary; exclude the mouth line, lashes, and painted features when assessing residual islands.
- **P3** [fidelity] *front, q34_front_left* - Upper lash bands and visible opening of both eyes: The rendered eyes read slightly heavier and sleepier than the sheet: the dark upper lash mass occupies more of the visible eye, reducing the open green-eyed expression. This is a local feature-shape difference rather than a reason to enlarge the whole head or eyeballs.
  - Fix: In lash_thick(), trial a reduction of about 0.4–0.6 panel px through the middle of each upper lid, retaining the tapered corners and outer flick. Because lash_bottom() also defines the opening, rebuild the eye patches, lash geometry, and morph targets together. Compare the neutral front and three-quarter views before changing iris size or eye spacing.

