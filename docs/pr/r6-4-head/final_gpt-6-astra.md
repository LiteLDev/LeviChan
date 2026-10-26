# Codex review: gpt-6-astra

The head is coherent across the turntable and remains attached and recognisable in all six supplied poses, but the cheek-to-jaw shading still reads as a hard bevel in the side and three-quarter views. The main correction is to separate that shading problem from the underlying lower-face shape: soften the broad shading transition first, then adjust the chin and jaw only where the clay silhouette supports it. The reference also has a slightly softer, shorter-looking lower face and more open eyes than the render. The supplied poses show no clear head-specific collapse, tearing or detachment; they do not demonstrate blinking, gaze extremes or mouth morphs, so facial animation readiness remains unverified. Scores and pose ratings below are scoped to the head and its immediate attachments; unrelated garment and leg defects are excluded.

Scores: naturalness 7/10, animation 7/10, fidelity 7/10

## Per-pose rating

clean / minor / major / broken: parts at fault, note.

| pose | gpt-6-astra |
|---|---|
| walk | **clean** No visible head or neck deformation fault in either supplied walk view. |
| arms_up | **clean** The head retains its shape and attachment with the arms raised, with no clear face or skull penetration visible. |
| squat | **clean** The head and visible neck remain continuous through the crouch in both views. |
| forward_bend | **clean** The face follows the forward bend without visible stretching or separation at the jaw and neck. |
| head_left | **clean** The face, eyes and crown turn together without an obvious displaced feature or torn neck seam at the shown angle. |
| swing | **clean** No head-specific deformation or attachment failure is visible in the two swing views. |

## head

- **P1** [naturalness] *q34_front_left, side, high* - Lateral cheek below the outer eye, continuing diagonally along the jaw toward the chin: A salmon-coloured shade strip separates the pale face from the jaw with an unusually straight, abrupt boundary. At three-quarter view this makes the face read like a flat mask with a bevel underneath; the high view reinforces the angular lower-face boundary. A two-tone edge is appropriate, but this edge describes a harder plane change than the surrounding soft facial forms.
  - Fix: In levi/parts/head.py, revise set_shading_normals() so the cheek and jaw use a continuous rounded proxy normal field rather than relying predominantly on the current detail=False surface, which retains the broad cross-section transitions. Blend that field across approximately reference rows 125–157 and the outer half of each cheek, retaining the actual normals at the silhouette. Keep shade_tilts() confined to the throat below the jaw so it cannot extend the facial shade strip. Compare cel and clay renders at side, 45-degree and high angles before changing the skin ramp globally.
- **P2** [naturalness] *clay side, clay q34_front_left, side* - Lower lip-to-chin profile and the forward end of the mandibular underside: The lower face still has a relatively straight descending profile followed by a compact turn under the chin. It is continuous rather than broken, but the small radius of that turn gives the chin a slightly projecting, wedge-like character at oblique angles. This is a shape issue distinct from the stronger cel-shading bevel.
  - Fix: Adjust the lower-face source in levi/parts/head.py before increasing mesh density: move TABLE's front-profile samples around rows 153.5–159.5 back by an initial 1–2 reference pixels, approximately 0.16–0.31 cm in +Y, and spread that change smoothly into the neighbouring rows. Reduce the positive chin contribution in LOWER_RELIEF if it restores the projection after the table edit. Preserve a rounded terminal chin and distribute the under-jaw loop spacing through the turn; retain the existing front-view width until the side and three-quarter clay contours improve.
- **P2** [fidelity] *01_ortho_sbs front and side* - Lower cheeks, mouth-to-chin interval and chin height: The rendered face reads slightly longer and more tapered below the eyes than the reference, particularly around the mouth and chin. This gives Levi a more solemn, narrow-faced expression even though the main eye placement is close. The difference is modest and should be corrected after the jaw shading, since the dark strip exaggerates the apparent taper.
  - Fix: After the shading and profile pass, test raising the terminal chin region by 1–2 reference pixels, approximately 0.16–0.31 cm, with a smooth falloff to zero above row 145. Apply the change to the lower-face source used by both the detailed and smooth builds, rather than translating the finished head or moving the eyes. Rebuild the mouth patch and morph targets from that same surface so the neutral correction does not create a separate jaw shape during vowel morphs.
- **P3** [fidelity] *01_ortho_sbs front, q34_front_left* - Both upper eyelids, especially over the central iris: The upper lids cover slightly more of the irises than in the sheet, giving the neutral face a heavier-lidded expression. This remains visible in the three-quarter view and contributes more to the expression mismatch than a small global skin-colour adjustment would.
  - Fix: In levi/parts/head.py, raise the central section of the upper eye-opening curve by an initial 0.5–1 reference pixel, approximately 0.08–0.16 cm, fading to zero at both corners. Update the painted upper lash boundary to follow the revised opening, while preserving the iris centres and eye pivots. Regenerate the eye patches and blink targets together, then verify full closure and intermediate blink values before accepting the change.

