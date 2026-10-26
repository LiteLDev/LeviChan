# Codex review: gpt-6.1-sol

The head is recognizable and reasonably aligned with the sheet, but the three-quarter clay views expose an abrupt cheek-to-jaw transition and prominent eye-cover bulges that the frontal cel render conceals. The first correction should be to round the lower face into a coherent jaw and neck junction while preserving the measured front silhouette. Next, refine the eye fit and surrounding skin together so the eyes sit within the face rather than reading as raised oval inserts. Local facial shading also needs cleanup: the high view produces a block-like nose mark, and thin shade fragments interrupt the otherwise restrained face treatment. Scores and pose ratings are scoped to the head and its immediate attachments; the supplied poses show no clear head deformation failure, but they do not establish blink, gaze or mouth-morph quality.

Scores: naturalness 6/10, animation 7/10, fidelity 7/10

## Per-pose rating

clean / minor / major / broken: parts at fault, note.

| pose | gpt-6.1-sol |
|---|---|
| walk | **clean** The face, eyes and upper neck remain aligned in both walking views, with no visible head-specific stretching or separation. |
| arms_up | **clean** The raised arms leave the head and facial features intact, with no visible sleeve penetration into the face or head ornaments. |
| squat | **clean** The head retains its shape and facial alignment in both squat views, without visible compression or detached features. |
| forward_bend | **clean** The head follows the bent torso without visible tearing at the neck or displacement of the eyes relative to their openings. |
| head_left | **clean** The eyes, face and framing hair follow the head turn together, while the angular jaw junction remains a rest-form problem rather than a demonstrated deformation failure. |
| swing | **clean** The head and facial features remain stable while the surrounding hair shifts, with no visible facial penetration or pieces left behind. |

## head

- **P1** [naturalness] *clay q34_front_left, clay side, q34_front_left, head_left front* - Lower cheeks, mandibular underside and the upper-neck junction beneath the rear half of the jaw: The lower face reads as a shallow wedge with a long, nearly straight underside perched over the neck. In three-quarter view, a conspicuous angular corner separates the broad cheek from the narrow throat; the clay render confirms that this is a volume transition, rather than only an outline or toon-shadow artifact. Turning the head makes the shelf especially apparent.
  - Fix: In levi/parts/head.py, reshape TABLE over rows 140–158 so the widest-point depth and back depth roll beneath the cheeks progressively instead of closing into a thin wedge. Start by moving the underside vertices around rows 148–155 downward by 0.2–0.4 cm, fading the change to zero at the front chin and lateral silhouette. Adjust neck_mesh() rows 146–158 to meet that revised underside tangentially, keeping the overlap buried inside the jaw. Preserve the existing front half-widths initially and assess the actual surface in side and both three-quarter clay views before retuning set_neck_normals().
- **P2** [naturalness] *clay q34_front_left, clay side, clay high* - Visible eye cover and the skin immediately below and outside each lower eyelid: The eye region projects as a distinct convex oval, with a noticeable ledge where its surrounding skin returns to the cheek. This makes the eye look mounted on the face instead of seated within an orbital volume. Cel shading reduces the effect, but it remains evident in the clay angles.
  - Fix: In fit_eyeball(), add a penalty for the displacement that hug() would impose on skin outside the eyelid opening, rather than optimizing only the rim-to-sphere fit. Trial moving each fitted sphere centre 0.2–0.3 cm rearward along +Y, refitting the radius to retain rim clearance. In hug(), broaden HUG_BAND's outer transition from 5 to approximately 7–8 panel pixels and reduce the far-field push onto the lower cheek. Rebuild the white cap and iris from the revised fit, then check blink interpolation and the existing gaze limits so the smoother socket does not introduce penetration.
- **P2** [naturalness] *high, q34_front_left, islands high, islands side* - Nose tip and underside, outer eye corners, and narrow shade strips along the lower cheek: The high view turns the nose into a small, hard rectangular shade mark, while other angles retain thin facial shade fragments around the eye and jaw. These isolated marks make the pale skin look chipped and emphasize the procedural surface structure. The supplied skin-island counts include the entire body, so they should not be treated as a head-only defect count.
  - Fix: In set_shading_normals(), replace the narrow feature-centred normal blend with a continuous broad facial field through the nose tip and lower cheeks; start by reducing SHADE_KEEP at the nose from 0.05 to approximately 0.02 and widening the nose mask from 7 to 9 panel pixels. Inspect patch-to-grid boundaries for normal discontinuities and keep the eyelid wall normals matched to their opening loops. Use the existing soft nose-tip texture mark for the small drawn accent, and retain a connected under-jaw shade instead of eliminating facial shading globally. Verify the result at intermediate turntable angles as well as high.

