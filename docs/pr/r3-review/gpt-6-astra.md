# Codex review: gpt-6-astra

Levi retains the reference’s overall silhouette, but the three-quarter and clay views expose substantial shape problems that the 0.92–0.94 silhouette IoU scores do not capture. The largest issues are flat, overlapping hair clumps, abruptly hooked hair ends, and a skirt hem that reads as angular folded shells rather than soft cloth. Animation is functional at the broad posing level, but the raised-arm sleeve ties and squat deformation need another pass before production use. Fix these volumes and their deformation first, then refine hair coverage, petticoat exposure, and local shading; tuning global shade percentages now would conceal some defects without resolving them. This assessment is based on the supplied stills and targeted code inspection: motion continuity and PMX playback are unverified, and the test named forward_bend exercises the arms rather than a torso bend.

Scores: naturalness 5/10, animation 5/10, fidelity 7/10

## hair_back

- **P1** [naturalness] *q34_back_right; clay back; clay side* - Central back hair from shoulder-blade height through the lower clump overlaps: The hair reads as stacked flat strips over a broad curtain. Several strips end or overlap with abrupt ledges and dark slits, breaking the impression of a continuous, rounded hair mass. This remains conspicuous without outlines.
  - Fix: In hair_back.py, reshape curtain() into a recessed inner volume and bury clump roots into it by approximately 0.5–1 cm. In clump(), replace the sharply edged lens section with a fuller oval on the principal locks, starting with thickness/width ratios of 0.4–0.5. Stagger the overlap endpoints and taper their thickness over several rings rather than terminating full-width surfaces against adjacent locks.
- **P1** [naturalness] *q34_front_left; q34_back_right; clay high* - Long outer locks behind both sleeves and curled ends over the rear skirt: The outer locks resemble rigid straps with abrupt upward hooks. The lower curls have broad, nearly planar faces and blunt changes of direction, so they read as cut-out ornaments rather than flowing hair.
  - Fix: Revise OUTER_LEFT and the hook() control paths to introduce a gradual S-curve before each curl and vary the curl plane through depth. Transport the cross-section frame smoothly along the path; add 4–6 samples around each tight bend and taper both width and thickness through the last third. Preserve a rounded section through the bend instead of relying on custom normals to give a flat strip volume.
- **P1** [naturalness] *back; q34_back_right* - White-to-mint transition above the bottom curls: The mint transition becomes a series of abrupt, uneven patches across neighboring locks. It looks like a cut-off color band rather than color flowing along the strands, especially where the rear curtain and clumps meet.
  - Fix: Replace the world-height-driven gradient in clump() with a smooth normalized arc-length gradient for each lock. Spread the transition over approximately 8–12 cm, with sufficient rings through that span, and give curtain() a compatible gradient that remains hidden under the outer clumps. Remove the accumulated gmax dependence where it creates a plateau around an upward curl.
- **P2** [naturalness] *back; q34_back_right; clay back* - Broad rear hair mass from the crown to the mid-back: The rear mass is nearly uniformly lit in cel despite obvious ridges and overlaps in clay. The broad flat fill and thin internal lines suppress depth, while local edges remain harsh. The back hair shade share of 0.17 versus 0.37 in the reference supports this visible imbalance.
  - Fix: In set_volume_normals(), stop applying the same 70% proxy-volume normal blend throughout the mass. Use stronger strand-normal contributions around overlap valleys and lower curls, and smoother proxy normals only across the crown and broad upper surfaces. Start with local own-normal weights around 0.5–0.65 at those valleys, then inspect all turntable angles before changing the hair ramp threshold.
- **P2** [fidelity] *sheet back versus render back; sheet side versus render side* - Lower third of the back hair over the waist and rear skirt: The reference has larger interwoven S-shaped locks and open curls. The model replaces much of that structure with a straight central curtain and small, similarly shaped hooked ends, changing the hairstyle’s internal silhouette despite the close overall outline.
  - Fix: After correcting the cross-sections, rebuild MAIN and SWEEP around three or four larger alternating S-shaped clumps. Recess and shorten the visible lower curtain, enlarge selected curl openings, and vary curl height and depth. Match the major negative spaces in the reference before adding small surface strands.

## hair_front

- **P1** [naturalness] *q34_front_left; high; clay q34_front_left* - Forehead fringe and long locks bordering the cheeks: The fringe resolves into a row of narrow spikes, while the cheek locks present broad, flat faces at three-quarter angles. Together they form a stiff cage around the face and obscure the eyes much more strongly from above.
  - Fix: In hair_front.py, regroup bangs() into fewer broad primary clumps with smaller secondary splits. Use 8–10 cross-section vertices in strand() for the prominent face-framing locks, round their sections, and curve their centerlines around the temples before they descend. Shorten the tips directly over the pupils by roughly 0.5–1 cm and turn the cheek-lock sections gradually instead of holding a predominantly fixed normal hint.

## skirt

- **P1** [naturalness] *q34_front_left; q34_back_right; clay front; clay high* - Lower skirt edge, particularly the side troughs and upturned fold mouths: The hem forms angular sockets and thick-looking rolled corners. Several troughs look pinched or folded into little boxes, and the silhouette changes direction sharply between adjacent lobes. These are geometry defects visible in clay.
  - Fix: In skirt.py, replace the two LIP_A bend samples with 5–6 samples around a smooth roll, reduce ROLL_R from 7 px toward 3–4 px, and soften the extreme per-fold crest curl values in FOLDS. Blend the trough-to-crest transition over a wider azimuth interval and check that the inward solidify surface does not cross itself at the tightest troughs.
- **P1** [animation] *squat front; squat q34_front_left* - Front skirt panel between the waist bow and the hem over the thighs: The front skirt compresses into sharp, irregular folds, and the long decorative tails acquire abrupt zigzags. The deformation reads as a shell buckling under thigh-follow rotation rather than cloth gathering over bent legs.
  - Fix: Increase T_STEPS from eight to approximately 14–16 longitudinal stations, concentrating the extra loops between the hip and lower thigh. In rig.py, reduce the front skirt-chain thigh follow from 100% to an initial 50–65%, then distribute the remaining lift over the child skirt bones. Transfer the hanging bodice-tail weights from the corresponding skirt surface so the trim follows the same deformation field.

## body

- **P1** [animation] *squat q34_front_left; walk q34_front_left* - Bent knees, especially the exposed knee at image-left in the squat three-quarter view: The bent knee has an angular, shelf-like silhouette with a tight inner crease and insufficient rounded volume at the front. The problem is most obvious in the deep squat.
  - Fix: In body.py, add supporting leg rings approximately 1 and 2 cm above and below the fitted knee, including an explicit front kneecap bulge. In rig.py, localize the knee helper weights to these rings and bias the front knee vertices toward the half-angle helper while allowing the rear crease to compress. Validate the shape at 60, 90, and 120 degrees using the same linear skinning exported to PMX.

## sleeves

- **P1** [animation] *arms_up front; arms_up q34_front_left* - Green ribbon tails extending from both upper sleeve bows: The ribbon tails project diagonally upward and outward as stiff wires when the arms rise. They retain the rest-pose drape relative to the sleeve instead of hanging or bending plausibly.
  - Fix: Give each long tail generated by _tails() a dedicated 3–4-bone chain. Anchor only its root to the sleeve knot, blend successive sections along that chain, and provide PMX rigid bodies and angular limits for gravity-driven motion. Keep the bow loops rigid at the attachment, while allowing the hanging tails to move independently of the sleeve balloon.
- **P2** [naturalness] *q34_front_left; clay front; clay side* - Main sleeve balloons between the upper leaf trim and wrist cuffs: The sleeves have large smooth, almost straight-sided expanses with a boxy flare and an abrupt rolled opening at the wrist. They resemble inflated cones more than fabric gathered at two openings.
  - Fix: In _balloon_bm(), round the station profile through the elbow and add shallow longitudinal gathers that taper to zero over the central belly. Add 2–3 transition rings before the cuff so the balloon narrows smoothly into it. Replace the abrupt 0.82-scaled terminal return with a curved return approximately 2–3 mm thick.

## lookdev

- **P2** [naturalness] *side; q34_front_left; back* - Hand shadow on the side skirt and skirt shadow across the upper legs: The skirt receives a conspicuous, sharply finger-shaped hand shadow, and the upper legs carry abrupt irregular shadow cutoffs. These high-frequency cast-shadow shapes compete with the broad, restrained shading of the character design.
  - Fix: Separate direct-light cel shading from cast-shadow attenuation in the render lookdev where supported, using a softer shadow contribution while retaining the two-tone diffuse ramp. First verify hand-to-skirt clearance and shadow bias so contact is not exaggerated. Test a modestly broader shadow source rather than lowering the global toon threshold, which would also change the form shading.

## petticoat

- **P2** [naturalness] *q34_front_left; q34_back_right; clay side* - Exposed pink tiers around the left and right side hems: The tiers read as repeated stacked plates, with straight radial pleats at the sides and nearly identical scallops. Their depth and regularity make the underside look heavier and more rigid than soft gathered fabric.
  - Fix: In petticoat.py, increase SEG from 7 to about 10 for the exposed scallops and add intermediate RINGS through each tier’s belly and return. Reduce FLUTE_DIP and FLUTE_RISE initially by 25–35%, and vary scallop width and phase deterministically between tiers. Keep the tier surfaces separated by a small consistent clearance rather than allowing their fold sides to bunch together.
- **P2** [fidelity] *sheet side versus render side; q34_front_left* - Pink band below the side and rear skirt hem: Too much petticoat is exposed in profile, producing a thick continuous pink band. The side-region pixel count is about 41% above the reference, consistent with the visible excess.
  - Fix: Adjust TIERS and the side-dependent lift in hem_z() to tuck the upper tier approximately 1–2 cm farther beneath the outer skirt at the side sectors. Reduce the visible tier height there without shrinking the entire petticoat width or removing the softer scallops visible at the front.

## shoes

- **P2** [naturalness] *q34_back_right; back; front* - Rear heel counters and upper edge around the toe openings: The rear shoes show large pale vertical patches framed by green strips, and the front opening edges appear jagged. From behind, the footwear reads as an exposed or segmented shell instead of a coherent pump.
  - Fix: In shoes.py, inspect _shell() face orientation and material assignment around the heel counter, ensuring outsole material is limited to the actual underside. Raise RING from 11 to approximately 17 and add longitudinal stations around the opening and rear counter. Shape the topline as a continuous curve with a small inward lip and keep the foot surface about 1–2 mm inside the upper.

## rig

- **P2** [animation] *forward_bend front; forward_bend q34_front_left* - Torso, waist, and bodice-to-skirt transition: This test leaves the torso upright and only moves the arms. Code inspection confirms pose_forward_bend() rotates the arm and elbow bones, so the sheet does not test waist compression, back stretching, or torso-driven hair and bodice clearance.
  - Fix: Rename the current pose to describe its arm action and add an actual torso-forward-bend test with approximately 25–35 degrees distributed over the available spine bones, plus a counter-rotation at the hips. Render side and three-quarter views and evaluate the bodice hem, chest straps, rear hair, and skirt waist before considering torso deformation approved.

