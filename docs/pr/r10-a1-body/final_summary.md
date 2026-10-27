# Review summary

Focus: body

| model | naturalness | animation | fidelity | findings |
|---|---|---|---|---|
| gpt-6.1-sol | 7 | 6 | 7 | 5 |
| gpt-6-astra | 7 | 6 | 7 | 5 |

**gpt-6.1-sol:** The body is generally coherent in the rest views, with rounded limb volumes and no obvious open seams, but the squat exposes a significant knee deformation problem: the thigh-to-shin transition bends into a continuous rubbery hook rather than retaining a distinct knee. Fix that deformation first, then refine the shoulder-to-armpit transition visible with the arms overhead. The existing body code already provides closely spaced joint loops, so the next pass should concentrate on cross-section shape and the distribution of helper-bone weights. Hand volume and the exposed leg silhouette need smaller refinements after those changes. These scores are body-focused; clothing obscures most elbow and hip deformation, and the supplied Blender poses do not establish equivalent behavior after PMX export.

**gpt-6-astra:** The body is broadly coherent in the standing views, but the squat exposes the main remaining weakness: the knee bends through an overly long, rounded section, making the knee-to-shin transition look rubbery. The raised-arm pose also shows some narrowing through the shoulder and armpit, although the supplied views do not show an open seam or a detached limb. Rest-pose improvements should concentrate on the knee-to-calf transition and the palm-to-finger construction rather than changing the overall proportions. The build already provides substantial joint-loop density and staged deformation helpers, so the next pass should refine local shape and weight distribution rather than add subdivision indiscriminately. These scores concern the body; the still images do not establish motion stability or equivalent deformation after PMX export.

## Priority 1 across all parts

- **body** (gpt-6.1-sol) [animation] both knees, from the lower thigh around the front of the joint into the upper shin: The bent legs form broad, continuous hooks: the front of each knee has little distinct patellar structure, while the lower contour develops a flattened shelf before reaching the shin. This makes the legs read as flexible tubing under a routine squat, even though the surfaces remain connected. The existing dense LEG_ROWS make insufficient loop count an unlikely primary cause.
- **body** (gpt-6-astra) [animation] Both knees, from the lower thigh across the kneecap into the upper shin: The bent knee reads as a rounded hose bend: the front projects into a broad lobe while the upper shin curves back sharply before reaching the ankle. This is conspicuous in the three-quarter squat and makes the leg appear to bend along its length rather than around a supported joint. The code already has closely spaced knee rings, so insufficient subdivision is not the main problem.

## Per-pose rating

clean / minor / major / broken: parts at fault, note.

| pose | gpt-6.1-sol | gpt-6-astra |
|---|---|---|
| walk | **clean** The visible knees, ankles and wrists remain connected through the stride without a clear deformation defect. | **clean** The exposed legs, ankles and hands maintain continuous silhouettes in both views, with no clearly visible deformation failure. |
| arms_up | **minor** (body) The near shoulder narrows into a pointed axillary crease above the bodice, losing some of the rounded transition visible with the arm lowered. | **minor** (body) Both exposed shoulder-to-armpit transitions narrow into stretched strips beneath the raised upper arms, most visibly in the front view. |
| squat | **major** (body) Both knees, especially in the three-quarter view, bend into broad hooks with flattened lower contours and an indistinct kneecap. | **major** (body, rig) Both knees form broad rounded lobes flowing into strongly curved upper shins, particularly in the three-quarter view, weakening the sense of a localized knee joint. |
| forward_bend | **clean** The exposed neck, shoulders and wrists remain continuous, with no clearly visible skin collapse or poke-through. | **clean** The visible skin retains its volume without a clear tear, pinch or intersection, although clothing conceals most of the hip and torso deformation. |
| head_left | **clean** The neck maintains a continuous connection beneath the turned and tilted head without an obvious twist pinch. | **clean** The visible neck-to-shoulder connection stays continuous during the head turn, with no obvious body deformation defect. |
| swing | **clean** The visible body maintains its shape as the secondary elements swing, with no clear new skin intersection. | **clean** No clear deformation or clipping problem appears on the exposed body in either supplied swing view. |

## By part

### body

- **P1** [animation] (gpt-6.1-sol) *squat q34_front_left, squat front* - both knees, from the lower thigh around the front of the joint into the upper shin: The bent legs form broad, continuous hooks: the front of each knee has little distinct patellar structure, while the lower contour develops a flattened shelf before reaching the shin. This makes the legs read as flexible tubing under a routine squat, even though the surfaces remain connected. The existing dense LEG_ROWS make insufficient loop count an unlikely primary cause.
  - Fix: In the body's section of levi/rig.py, preserve the existing broad posterior JOINT_HINGE transition but give the anterior knee a more localized rotation distribution. Add a patella helper taking approximately half the knee rotation, weight a 2–3 cm anterior patch predominantly to it, and blend back into the existing thigh and shin helpers over another 3–4 cm. In body.py, keep that patch rounded through KNEECAP and leg_offset rather than enlarging the whole knee ring. Compare the resulting outer contour at 60, 90 and 120 degrees of flexion before changing KNEE_FWD.
- **P1** [animation] (gpt-6-astra) *squat q34_front_left; squat front* - Both knees, from the lower thigh across the kneecap into the upper shin: The bent knee reads as a rounded hose bend: the front projects into a broad lobe while the upper shin curves back sharply before reaching the ankle. This is conspicuous in the three-quarter squat and makes the leg appear to bend along its length rather than around a supported joint. The code already has closely spaced knee rings, so insufficient subdivision is not the main problem.
  - Fix: Keep body.py's existing LEG_ROWS and KNEE_FWD as the starting point. In rig.py, refine the knee's JOINT_HINGE partition so the anterior kneecap rings retain a more coherent volume and the distal upper-shin rings return to the shin bone sooner, while preserving the broader posterior blend needed for the knee hollow. Introduce a separate anterior/side falloff instead of narrowing the entire hinge band uniformly; start by shortening only the distal anterior transition by 1–2 cm. Compare 60, 90 and 120 degree bends from the side and three-quarter views, checking both the lobe and posterior face inversion before adopting the change.
- **P2** [naturalness] (gpt-6.1-sol) *clay q34_front_left, q34_front_left* - character's left hand, across the distal palm and the four finger roots: The palm reads as a smooth oval pad with nearly parallel cylindrical fingers attached to its end. The rounded palm-to-finger transition is weaker than the wrist-to-palm transition, making the hand look assembled from separate primitives in the clay view.
  - Fix: Refine _palm_shape(), the distal HAND_R entries and the FINGERS base positions in body.py together. Stagger the finger roots by approximately 0.2–0.4 cm along the hand, form shallow web valleys between them, and carry each metacarpal dome into its finger root. Retain the five separate finger islands required by fit_fingers(), but bury their proximal caps approximately 0.3 cm inside the palm and taper that overlap so it does not produce visible root collars.
- **P2** [naturalness] (gpt-6-astra) *q34_front_left; clay q34_front_left; render side* - Both legs, immediately above the knee and along the upper calf: The resting leg has a noticeable inward transition above a relatively abrupt calf swell. In three-quarter view the knee is less clearly articulated than the calf bulge, producing a mildly wavy outline that becomes more conspicuous when the leg bends.
  - Fix: In body.py, isolate the shape-master contribution around rows 650–735. Test reducing KNEE_MASTER_W from 1.0 to approximately 0.6–0.75 while retaining the low-order radial fit, then adjust LEG_SIDE and the local leg_offset contribution to move the upper-calf fullness slightly downward and fill the pre-knee hollow by about 0.2–0.3 cm. Blend that correction over at least 3 cm and preserve the anterior shin line; do not enlarge KNEE_WIDE globally.
- **P2** [naturalness] (gpt-6-astra) *q34_front_left; high; clay front* - Both hands, across the knuckle row and thumb-to-palm junction: The hands still read as broad, fairly flat palms with similarly aligned tubular fingers. The thumb junction is abrupt, and the knuckle row does not provide enough visible transition between the palm mass and the individual digits. This is a form issue in the supplied views; they do not demonstrate finger-animation failure.
  - Fix: Refine _palm_shape() and HAND_R locally rather than increasing the whole palm's thickness: add approximately 0.1–0.2 cm of dorsal arch beneath the middle and ring knuckles, fading toward the index and little-finger edges. Adjust the FINGERS base positions and first two rings to bury their roots more smoothly into that arch, and broaden the thenar-to-thumb transition by about 0.1 cm. Preserve the five separate finger islands required by rig.fit_fingers, and check that the root overlaps remain concealed during finger curl.
- **P2** [animation] (gpt-6.1-sol) *arms_up q34_front_left* - character's left axilla and inner upper arm, immediately above the bodice neckline: The raised upper arm retains its outer volume, but the inner shoulder transition runs down into a narrow, pointed crease at the chest. It is a small deformation defect rather than a tear, yet it makes the shoulder look attached through a tapered strip instead of rolling into an axillary hollow.
  - Fix: Refine the inner quadrant of arm_rings() and its SOCKET_STEPS transition in body.py, spreading the turn across the existing transition rings and filling the pointed end by roughly 0.2–0.4 cm. In the body's _shoulder_stages weighting, introduce a smooth angular bias around the socket so the axillary vertices retain more chest/shrug influence while the outer cap follows the arm stages. Keep the partition continuous around the socket; do not move all SHOULDER_STAGES knots together or inflate the entire deltoid.
- **P2** [animation] (gpt-6-astra) *arms_up front; arms_up q34_front_left* - Both shoulder sockets, especially the inner upper arm and armpit beneath the sleeve attachment: Raising the arms leaves a narrow, stretched-looking skin connection beside the chest instead of a fuller shoulder flowing into a compact armpit fold. The surface remains connected, but the volume loss is visible compared with the relaxed shoulder.
  - Fix: Use the signed levi_socket_s parameter already generated by body.py to inspect the socket transition rings separately from the arm shaft. In rig.py, bias the inner socket toward the intermediate shoulder helpers rather than letting it reach full arm rotation as quickly as the outer cap; start with a 0.5–1 cm local extension of the inner transition. If the contour remains hollow, add only 0.2–0.3 cm of front/back fullness to the inner transition in arm_rings(), fading to zero at the socket border and first full arm ring. Recompute the socket attribute after the shape change and verify overhead and lowered arms.
- **P2** [fidelity] (gpt-6.1-sol) *sheet side / render side, sheet front / render front* - exposed lower thighs immediately below the petticoat, continuing to the upper calf: The rendered legs narrow more strongly just below the hem and then expand into a pronounced calf bulge. The reference carries more fullness through the upper exposed leg, giving a gentler transition. This is particularly visible in the side comparison and contributes to the reduced rendered skin area there; correcting it should remain subordinate to the squat fix.
  - Fix: Adjust the exposed-leg profile around rows 620–670 in LEG_FRONT and LEG_SIDE, adding roughly 0.2–0.4 cm to the deficient anterior and lateral contours and easing the change toward the calf over 4–6 cm. Check the contribution from _leg_master() in that interval and reduce its local influence where it reinstates the constriction. Keep knee_joint(), ankle_joint() and the lower ankle profile fixed during this proportion pass so the rig and shoe fit do not drift.
- **P3** [naturalness] (gpt-6.1-sol) *islands q34_front_left, islands back* - thumb webs and palm edges adjacent to the sleeve cuffs: Small detached shade fragments occur around the hand contours and thumb webs. They are minor at full-character scale, but they make the pale skin look chipped when the hands are inspected closely. The supplied skin-island totals also include the head, so those totals should not be treated as body-only counts.
  - Fix: Inspect the body hand's fill normals separately from its outline hull. Smooth the local section derivatives across the distal wrist, thenar pad and thumb-root overlap in _palm_shape() and build_fingers(), using the existing rings before adding subdivisions. Where an overlapping finger cap affects the visible root, move it farther inside the palm. Verify that each hand keeps one connected principal shade patch across the review angles without changing the global skin ramp.
- **P3** [fidelity] (gpt-6-astra) *render front; render side; render back* - Exposed legs, upper chest and arms: The body skin is consistently lighter and slightly pinker than the reference, particularly over the large leg surfaces. The supplied regional measurements support this difference, although the skin region also includes the head and should not be treated as a body-only measurement.
  - Fix: After the shape changes, make a small adjustment to the skin palette used by body.py: test lowering the base colour's lightness by roughly 2–3 Lab units and reducing its pink saturation slightly. Keep the current skin shade threshold initially, since the measured shade shares are already close to the sheet, and compare masked body areas under the same lighting before changing the shade colour.

## Metrics vs baseline `out\review_main`

Per view and region, `new (delta)`; `*` = whole view (silhouette IoU, island total). iou/tol up is better; dE/dEi (interior colour error), islands and island_px down is better; shade is the render's shade share (compare with the sheet in shade_stats.txt).

| view | region | iou | tol | dE | dEi | shade | islands | island_px |
|---|---|---|---|---|---|---|---|---|
| back | * | 0.912 (-0.006) |  |  |  |  | 33 (+0) | 890 (+41) |
| back | dress | 0.627 (-0.000) | 0.825 (-0.001) | 6.4 (+0.0) | 5.5 (+0.0) | 0.180 (+0.000) | 4 (+0) | 164 (+0) |
| back | petticoat | 0.405 (+0.002) | 0.657 (+0.003) | 10.2 (+0.0) | 8.8 (+0.0) | 0.220 (+0.000) | 3 (+0) | 157 (+0) |
| back | skin | 0.617 (-0.049) | 0.836 (-0.021) | 6.2 (+0.2) | 3.0 (-0.3) | 0.190 (+0.010) | 3 (+0) | 151 (+41) |
| front | * | 0.910 (-0.006) |  |  |  |  | 39 (+0) | 944 (+90) |
| front | dress | 0.785 (+0.000) | 0.931 (-0.000) | 6.2 (+0.0) | 5.2 (+0.0) | 0.200 (+0.000) | 6 (+0) | 31 (+0) |
| front | green | 0.392 (-0.002) | 0.803 (-0.002) | 17.2 (-0.1) | 15.6 (+0.0) | 0.320 (+0.000) | 16 (+0) | 394 (+0) |
| front | hair | 0.556 (+0.000) | 0.786 (+0.000) | 12.9 (+0.0) | 11.4 (+0.0) | 0.570 (+0.000) | 6 (+0) | 165 (+0) |
| front | skin | 0.747 (-0.037) | 0.944 (-0.015) | 6.6 (+0.2) | 3.4 (+0.0) | 0.150 (+0.000) | 9 (+0) | 308 (+90) |
| high | * |  |  |  |  |  | 38 (+0) | 778 (-59) |
| high | skin |  |  |  |  |  | 3 (+0) | 99 (-59) |
| q34_back_right | * |  |  |  |  |  | 22 (-1) | 636 (-11) |
| q34_back_right | skin |  |  |  |  |  | 2 (-1) | 40 (-11) |
| q34_front_left | * |  |  |  |  |  | 43 (+1) | 904 (+61) |
| q34_front_left | skin |  |  |  |  |  | 13 (+1) | 403 (+61) |
| side | * | 0.855 (-0.005) |  |  |  |  | 34 (+0) | 751 (-8) |
| side | dress | 0.750 (+0.001) | 0.909 (+0.000) | 7.6 (+0.0) | 6.7 (+0.0) | 0.270 (+0.000) | 6 (+0) | 141 (+0) |
| side | green | 0.316 (+0.001) | 0.640 (+0.003) | 18.0 (+0.1) | 15.1 (+0.0) | 0.450 (+0.000) | 8 (-1) | 218 (-65) |
| side | skin | 0.619 (-0.032) | 0.840 (-0.014) | 6.6 (+0.5) | 3.3 (+0.1) | 0.220 (+0.000) | 5 (+1) | 192 (+57) |

## Shape-master fit vs baseline

target->ours distance (mm, down is better) and covered share (up is better), from tools/shape_fit.py: `new (delta)`.

| part | p50 mm | p90 mm | covered |
|---|---|---|---|
| body | 6.9 (-1.7) | 23.6 (-0.6) | 0.402 (+0.090) |
| head | 6.2 (+0.0) | 19.8 (+0.0) | 0.426 (+0.000) |
| hair_front | 4.5 (+0.0) | 14.9 (+0.0) | 0.535 (+0.000) |
| hair_back | 25.4 (+0.0) | 77.3 (+0.0) | 0.170 (+0.000) |
| accessories | 4.5 (-0.2) | 11.1 (-0.5) | 0.546 (+0.024) |
| bodice | 9.1 (+0.0) | 25.9 (+0.0) | 0.264 (+0.000) |
| skirt | 14.6 (+0.0) | 48.3 (+0.0) | 0.204 (+0.000) |
| petticoat | 13.7 (+0.0) | 34.5 (+0.0) | 0.190 (+0.000) |
| sleeves | 11.7 (+0.0) | 27.4 (+0.0) | 0.240 (+0.000) |
| shoes | 7.4 (+0.0) | 18.7 (+0.0) | 0.347 (+0.000) |

