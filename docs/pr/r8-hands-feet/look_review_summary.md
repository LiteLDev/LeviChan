# Review summary

Focus: body,shoes

| model | naturalness | animation | fidelity | findings |
|---|---|---|---|---|
| gpt-6.1-sol | 7 | 6 | 7 | 6 |
| gpt-6-astra | 7 | 6 | 7 | 7 |

**gpt-6.1-sol:** The body and shoes are broadly coherent in three dimensions, but the squat exposes an angular knee bend and the raised-arm pose exposes a stretched underarm transition that should be corrected before animation approval. The shoes retain their shape in the supplied poses; their remaining problems are concentrated in the heavy rear silhouette, rounded front toe silhouette, and ankle-leaf colour. Prioritize the knee and shoulder skinning while preserving the rigid shoe shells, then refine the shoe cross-sections against both the clay review angles and the reference. These static images support a pose-level review, but do not establish continuous motion stability or equivalent deformation after PMX export.

**gpt-6-astra:** The body and shoes are coherent at rest, but the squat exposes a visibly pinched, angular knee bend that needs another deformation pass before animation approval. The shoes retain their structure in the supplied poses; their main remaining problems are the heavy rear silhouette, broad tan arch exposure, and blunt appearance of the toe boxes from the front. Body polish should concentrate on the knee-to-calf transition and the thin, uniformly splayed hands rather than adding general mesh density. Fix the knee deformation first, then refine shoe cross-sections and the supporting foot geometry together so clearance does not undo the shape improvements. These ratings cover the visible body and shoe behavior in the supplied stills; temporal stability and PMX playback equivalence are not established by this sheet.

## Priority 1 across all parts

- **body** (gpt-6.1-sol) [animation] both knees, from the lower thigh around the kneecap into the upper shin: The bent contour becomes a hooked, angular zigzag rather than a rounded knee over a folded posterior crease. The three-quarter view shows an abrupt shelf into the shin, while the front view shows a sudden narrowing below each knee. This is visible silhouette deformation, even though the mesh remains connected.
- **body** (gpt-6.1-sol) [animation] both axillary folds, immediately above the bodice side edges and below the upper-arm leaf bands: The exposed skin between the torso and raised arms becomes a long, pointed web with an abrupt change into the upper arm. The transition loses the rounded shoulder-to-chest volume visible at rest and reads as stretched skin rather than an opening underarm fold.
- **body** (gpt-6-astra) [animation] Both knees, particularly the inner knee fold and the forward-facing kneecap contour: The bent legs read as sharply folded tubes: the inner contour pinches into a tight notch while the outer knee becomes an angular projecting corner. This is visible at contact-sheet scale and interrupts the rounded thigh-to-shin transition.

## Per-pose rating

clean / minor / major / broken: parts at fault, note.

| pose | gpt-6.1-sol | gpt-6-astra |
|---|---|---|
| walk | **clean** No clear additional body collapse, shoe distortion, or ankle-strap separation is visible in the supplied stride. | **clean** The visible legs, ankles and shoes remain continuous in both views, without a clear deformation failure. |
| arms_up | **major** (body,rig) Both exposed underarms stretch into narrow, pointed transitions between the chest and raised upper arms, most visibly in the front view. | **clean** The exposed shoulders and upper arms retain continuous silhouettes; sleeves obscure the elbows, and the fingertips are partly cropped. |
| squat | **major** (body,rig) The knees form angular hooks with abrupt changes of width into the upper shins, most clearly in the three-quarter view. | **major** (body) Both knees develop an angular outer bend and a sharply constricted inner fold, most clearly in the three-quarter view. |
| forward_bend | **clean** The visible body and shoes retain their volumes without a clear new deformation defect at this bend angle. | **clean** No clear body or shoe collapse is visible in the exposed limbs, although the garment hides the hip deformation. |
| head_left | **clean** The exposed neck-to-shoulder area remains continuous, with no clear body or shoe deformation introduced by the head turn. | **clean** The visible neck-to-shoulder connection remains intact through the head turn. |
| swing | **clean** The visible body, ankles, and shoe shells remain coherent in both supplied swing views. | **clean** The exposed body and shoes show no clear new stretching or clipping in this pose. |

## By part

### body

- **P1** [animation] (gpt-6.1-sol) *squat q34_front_left, squat front* - both knees, from the lower thigh around the kneecap into the upper shin: The bent contour becomes a hooked, angular zigzag rather than a rounded knee over a folded posterior crease. The three-quarter view shows an abrupt shelf into the shin, while the front view shows a sudden narrowing below each knee. This is visible silhouette deformation, even though the mesh remains connected.
  - Fix: Keep the existing dense LEG_ROWS and two knee helpers, but revise the circumferential weight distribution in rig._split_joint_aux rather than adding more loops indiscriminately. In the anterior and lateral knee sectors, spread the helper transitions across at least three existing longitudinal rings per transition and remove abrupt changes where JOINT_HINGE_CAP takes over. Tune the posterior sector separately so the crease stays behind the joint instead of drawing the side contour inward. Compare the resulting silhouettes at 60, 90, and 120 degrees of flexion; retain the current KNEE_FWD initially so pivot changes do not obscure the weight correction.
- **P1** [animation] (gpt-6.1-sol) *arms_up front, arms_up q34_front_left* - both axillary folds, immediately above the bodice side edges and below the upper-arm leaf bands: The exposed skin between the torso and raised arms becomes a long, pointed web with an abrupt change into the upper arm. The transition loses the rounded shoulder-to-chest volume visible at rest and reads as stretched skin rather than an opening underarm fold.
  - Fix: In body.arm_rings, add two transition rings to SOCKET_STEPS, approximately at 0.12 and 0.90, so the ends of the socket transition have support. In the rig's socket-parameter weighting, make the inner axillary rows remain predominantly on the torso/shrug side while the outer deltoid progresses through the staged shoulder bones; blend this distinction smoothly around the socket. Start by moving the innermost stage transition 0.5–1 cm toward the arm, and check that the raised pose opens a rounded fold without pulling the chest side upward. Use weights and exported helper bones for the correction so it survives PMX export.
- **P1** [animation] (gpt-6-astra) *squat q34_front_left, squat front* - Both knees, particularly the inner knee fold and the forward-facing kneecap contour: The bent legs read as sharply folded tubes: the inner contour pinches into a tight notch while the outer knee becomes an angular projecting corner. This is visible at contact-sheet scale and interrupts the rounded thigh-to-shin transition.
  - Fix: Rework the existing knee helper partition in levi/rig.py together with body.py's knee rings; the mesh already has approximately 1 cm longitudinal spacing here, so a general subdivision increase is not the first fix. Redistribute the middle helper weights over adjacent rings to spread the outer bend, and reduce concentration of the rear fold around KNEE_CREASE. Start with a bend-dependent 0.3–0.5 cm outward correction on the collapsed side sectors and fade it across 3–4 rings. Keep the correction available to the PMX path through helper weights or an exported morph, and verify that it does not create a rear calf hook.
- **P2** [naturalness] (gpt-6-astra) *q34_front_left, clay q34_front_left, render front* - Both legs, transition from the exposed lower thigh through the knee into the upper calf: At rest the legs have a long narrow upper segment followed by a conspicuous lateral calf bulge, with little kneecap structure separating the two. The three-quarter silhouette reads as a smooth bowed tube rather than a lightly articulated knee and calf.
  - Fix: Adjust LEG_FRONT around rows 670–730 to soften the outer maximum near rows 690–710 by approximately 1–2 px, redistributing that volume toward the rear calf through CALF rather than widening the whole ring. Broaden KNEECAP's longitudinal support slightly and add only about 0.5–1 px of forward prominence initially. Check front, side and both three-quarter silhouettes before changing KNEE_ROW or the rig pivot.
- **P2** [naturalness] (gpt-6-astra) *q34_front_left, high, clay front* - Both hands, palm-to-finger roots and the four extended fingers: The hands read as thin fans with nearly parallel, uniformly straight fingers. Their shallow palm volume and abrupt finger separations become more apparent from the elevated view, making them feel less formed than the surrounding limbs.
  - Fix: In HAND_R and _palm_shape, add approximately 0.15–0.25 cm of localized thenar and knuckle-pad volume without thickening the wrist. In build_fingers, introduce a gentle metacarpal arch and differentiated resting flexion, roughly 3–8 degrees increasing toward the little finger. Seat each separate finger root inside its corresponding palm pad so the rig can retain its loose-component finger detection without exposing hard root seams.
- **P3** [fidelity] (gpt-6.1-sol) *front, side, back* - exposed legs and hands: The rendered skin is slightly lighter and pinker than the reference's warmer, more muted skin. This is a small discrepancy: the supplied overlap-only skin colour errors are much lower than those for hair or green details, so it should follow the volume and deformation fixes.
  - Fix: In the skin palette used by body.build, trial reducing the lit colour's lightness slightly and shifting it toward the reference's warmer beige, using a small 2–3 sRGB-value adjustment per channel as the first iteration. Adjust the shade colour by the same restrained amount, preserve the current skin ramp threshold initially, and recheck the exposed legs independently of the head.

### shoes

- **P2** [naturalness] (gpt-6.1-sol) *back, q34_back_right, clay back* - rear quarters and heel-seat-to-stiletto transitions on both shoes: The rear projection is heavy: the counter, descending arch silhouette, and heel shaft merge into broad, nearly continuous green forms. From three-quarter rear the arch is readable, but directly behind the shoes lose the delicate separation between a rounded heel cup and a narrow supporting heel.
  - Fix: Refine the rear STATIONS and WAIST together: trial a 1–2 px reduction in lower-quarter half-width through y=-8 to +12, approximately 0.16–0.31 cm per side, while preserving the opening around the actual heel. Preserve FOOT_CLEAR and reduce the hidden body's FOOT width locally if it prevents this taper. Keep the upper HEEL attachment embedded in the seat, but narrow the intermediate HEEL rings around rows 904.5–920 by roughly 10% and blend the flare smoothly. Judge the change in clay back and three-quarter rear before adjusting materials.
- **P2** [naturalness] (gpt-6-astra) *q34_back_right, clay q34_back_right, render back* - Both shoes, underside of the arch and transition from heel cup to heel shaft: The rear three-quarter view shows substantial tan wedges beneath the green uppers, while the heel cup and shaft merge into a heavy vertical mass from behind. The construction reads closer to a filled arch than a thin sole bridging to a distinct stiletto.
  - Fix: Refine STATIONS and WAIST in shoes.py over y=-22..+12 px: draw the lower sidewalls inward by an initial 1–2 px per side while preserving the upper heel seat. Where _clear_foot prevents this, narrow the corresponding hidden body.FOOT underside rather than reducing FOOT_CLEAR. Make the tan boundary follow an explicit thin sole strip instead of relying only on a fixed angular face selection, and preserve a readable concave separation between shank and heel shaft.
- **P2** [fidelity] (gpt-6.1-sol) *front, q34_front_left* - both toe boxes, especially their front-facing ends: The front render reads as a rounded, broad-ended pump, whereas the sheet has a more tapered, oblique point. The side view already has sufficient toe length, so extending the whole shoe would worsen the profile without addressing the front silhouette.
  - Fix: Adjust the plan taper in the forward STATIONS, particularly y=-83 through -62, rather than moving TOE_TIP farther forward. Trial reducing the half-widths there by 1–1.5 px, approximately 0.16–0.23 cm per side, with a monotone blend back into the ball width. Preserve the rounded vertical toe-box section and internal clearance; verify that the front point becomes sharper without producing a pinched ridge in clay q34_front_left.
- **P2** [fidelity] (gpt-6-astra) *render front versus sheet front, render back versus sheet back* - Toe-box front silhouette and rear heel-counter width: The front shoes end in rounded, almost squared lobes instead of the reference's slanted points, and the rear shoes occupy noticeably more area than the reference. The supplied back shoe pixel areas, 8054 rendered versus 6098 reference, support the visible excess bulk.
  - Fix: Refine the closed toe stations in shoes.py, especially y=-95..-66 px, to taper both width and top height more continuously toward TOE_TIP; do not simply extend the tip farther forward. Reduce rear counter lower widths by about 1 px per side initially and coordinate changes with body.FOOT so _clear_foot does not expand them again. Preserve realistic toe room and assess the result in three-quarter views as well as the aligned front and back.
- **P3** [naturalness] (gpt-6-astra) *q34_front_left, render back, high* - Leaf ornaments on the outer rear of each ankle: The ankle leaves still read as broad, relatively flat paddles with little visible central structure. This is particularly evident where one blade presents its full face to the camera.
  - Fix: In _leaf, increase the smooth longitudinal arch from 0.05 to approximately 0.07 of blade length and adjust the two blade rolls by about 5 degrees in opposite directions. Add a restrained raised midrib using the existing cross-section vertices rather than increasing overall thickness; keep the attachment point fixed and verify clearance against the shin in squat.
- **P3** [fidelity] (gpt-6.1-sol) *front, side, q34_front_left* - paired leaves attached to the outer-back ankle wraps: The ankle leaves read brighter and more uniformly fresh green than the darker leaves in the sheet, particularly beside the dark shoe shells. Their lighting distinction is weak enough that they appear to belong to a different trim palette.
  - Fix: Give shoes_leaves a shoe-specific leaf material variant instead of changing the shared leaf palette globally. Darken and slightly desaturate its lit green first, then use a distinctly darker shade green; preserve the existing cupped geometry and thickness. Check the material on both mirrored shoes under the current light so the correction retains readable leaf volume rather than making each blade uniformly dark.
- **P3** [fidelity] (gpt-6-astra) *render front, render back* - Green upper surfaces of both pumps: The shoes combine brighter green lit surfaces with a larger dark-tone share than the reference, producing a stronger two-block appearance. The discrepancy is most apparent in the front and back views, where rendered shade coverage is about 0.40–0.42 against 0.26–0.32 in the sheet.
  - Fix: After the shell shape changes, adjust the shoe-specific toon threshold to reduce the front and back dark coverage while retaining the already closer side result. Slightly darken the lit shoe green toward the reference before changing the shadow color. Keep this adjustment confined to the shoe material and judge the broad upper surfaces separately from the narrow lace and outline pixels.

## Metrics vs baseline `out\review_main`

Per view and region, `new (delta)`; `*` = whole view (silhouette IoU, island total). iou/tol up is better; dE/dEi (interior colour error), islands and island_px down is better; shade is the render's shade share (compare with the sheet in shade_stats.txt).

| view | region | iou | tol | dE | dEi | shade | islands | island_px |
|---|---|---|---|---|---|---|---|---|
| back | * | 0.919 (+0.001) |  |  |  |  | 28 (+1) | 818 (-4) |
| back | green | 0.265 (+0.001) | 0.577 (+0.001) | 15.5 (+0.0) | 10.1 (+0.0) | 0.480 (+0.000) | 1 (-1) | 79 (-69) |
| back | shoe | 0.537 (+0.010) | 0.868 (+0.003) | 12.8 (+0.0) | 10.1 (+0.1) | 0.420 (+0.000) | 0 (+0) | 0 (+0) |
| back | skin | 0.664 (+0.007) | 0.855 (+0.006) | 5.9 (+0.3) | 3.3 (+0.2) | 0.190 (+0.000) | 3 (+2) | 110 (+65) |
| front | * | 0.916 (+0.001) |  |  |  |  | 42 (-2) | 831 (-89) |
| front | dress | 0.786 (+0.000) | 0.931 (+0.000) | 6.1 (+0.0) | 5.1 (+0.0) | 0.200 (+0.000) | 8 (+0) | 105 (-3) |
| front | green | 0.394 (+0.000) | 0.803 (+0.000) | 17.3 (+0.0) | 15.7 (+0.0) | 0.330 (+0.000) | 16 (-1) | 394 (+4) |
| front | shoe | 0.512 (+0.006) | 0.874 (+0.007) | 13.4 (-1.0) | 9.2 (-1.3) | 0.390 (+0.000) | 1 (+1) | 31 (+31) |
| front | skin | 0.784 (+0.004) | 0.959 (+0.003) | 6.6 (+0.1) | 3.4 (+0.1) | 0.150 (+0.000) | 8 (-2) | 207 (-121) |
| high | * |  |  |  |  |  | 39 (-8) | 809 (-196) |
| high | green |  |  |  |  |  | 17 (-1) | 401 (-80) |
| high | skin |  |  |  |  |  | 3 (-7) | 158 (-116) |
| q34_back_right | * |  |  |  |  |  | 28 (+0) | 665 (-11) |
| q34_back_right | shoe |  |  |  |  |  | 1 (+0) | 68 (-6) |
| q34_back_right | skin |  |  |  |  |  | 3 (+0) | 51 (-5) |
| q34_front_left | * |  |  |  |  |  | 42 (+3) | 837 (+156) |
| q34_front_left | dress |  |  |  |  |  | 4 (+0) | 177 (-3) |
| q34_front_left | shoe |  |  |  |  |  | 2 (+1) | 19 (+11) |
| q34_front_left | skin |  |  |  |  |  | 9 (+2) | 296 (+148) |
| side | * | 0.861 (+0.002) |  |  |  |  | 33 (+1) | 587 (+21) |
| side | dress | 0.749 (-0.000) | 0.908 (-0.001) | 7.5 (+0.0) | 6.6 (+0.0) | 0.260 (+0.000) | 6 (+0) | 68 (+0) |
| side | green | 0.313 (+0.001) | 0.639 (+0.000) | 17.9 (+0.0) | 14.9 (+0.0) | 0.440 (+0.000) | 9 (+0) | 213 (+0) |
| side | shoe | 0.680 (+0.010) | 0.938 (+0.004) | 10.2 (-0.1) | 5.5 (+0.0) | 0.220 (+0.000) | 0 (+0) | 0 (+0) |
| side | skin | 0.642 (+0.006) | 0.851 (+0.004) | 6.2 (+0.2) | 3.2 (+0.1) | 0.220 (+0.000) | 5 (+1) | 142 (+21) |

