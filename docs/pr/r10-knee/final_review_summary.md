# Review summary

| model | naturalness | animation | fidelity | findings |
|---|---|---|---|---|
| gpt-6.1-sol | 6 | 7 | 7 | 15 |
| gpt-6-astra | 5 | 6 | 6 | 14 |

**gpt-6.1-sol:** Levi is recognizable and holds together across the supplied angles, but the back hair remains the main obstacle to a convincing three-dimensional character: broad overlapping slabs terminate in angular hooks and blunt tabs that are especially apparent in clay. The next pass should repair those lock sections, curl transitions and overlaps, then clean the local normal fields responsible for the scattered cel-shade slivers. The rig survives the supplied poses without visible tearing or wholesale collapse, although the squat exposes angular knee deformation and the raised-arm pose compresses the sleeve bags unevenly. Animation readiness is promising, but these Blender stills do not establish equivalent deformation or secondary-motion behavior after PMX export. Fidelity work should follow those repairs, concentrating on the skirt's fold structure, the exposed petticoat gathers and the separation of the front hair.

**gpt-6-astra:** Levi is recognizable and has a coherent overall silhouette, but the rear hair still reads as a layered shell with hooked strips rather than a continuous arrangement of rounded locks. The clay and oblique views expose angular lower-hair transitions, abrupt overlap boundaries, and an overly rigid skirt and petticoat construction that the aligned silhouettes understate. The pose tests show no obvious catastrophic tearing, but the overhead sleeves and deeply bent knees need another deformation pass. Prioritize rebuilding the lower hair transitions and correcting those joint deformations, then improve cloth volume and local shading normals before tuning reference colours or silhouette metrics. These still images support a deformation review, but do not establish temporal stability or PMX playback parity for the Blender-driven corrections.

## Priority 1 across all parts

- **hair_back** (gpt-6.1-sol) [naturalness] Lower central and image-right locks, immediately above the skirt: The free ends read as thick cut slabs: several narrow into rectangular tabs or turn through abrupt corners before reaching their curls. These are visible form defects in clay, so cleaning the cel ramp alone will not resolve them.
- **hair_back** (gpt-6.1-sol) [naturalness] Three large lower curls across the back: The curls have angular inner openings and locally flattened bends, giving them the appearance of bent straps or molded hooks rather than soft hair clumps. Their silhouettes deteriorate markedly away from the calibrated back view.
- **hair_back** (gpt-6.1-sol) [naturalness] Overlapping locks from the shoulder blades to the lower back: Broad locks merge for long stretches and then separate into deep, abrupt slots and exposed ledges. The result reads as stacked shells rather than a coherent mass with individually flowing locks.
- **hair_back** (gpt-6.1-sol) [naturalness] Pale back-hair surface and the white-to-mint transition above the curls: Thin disconnected grey marks and jagged shade boundaries make the otherwise broad pale surface look chipped. The back view contains 22 small hair shade islands, and the three-quarter view exposes additional narrow strips along lock overlaps.
- **hair_back** (gpt-6-astra) [naturalness] Lower central back locks immediately above the curled ends: Several broad locks terminate in blunt, angular steps before joining the curls; the resulting rectangular notches and exposed overlap edges make the hair look assembled from cut strips.
- **hair_back** (gpt-6-astra) [naturalness] Large lower U-shaped curls across the back waist: The curls read as flat straps bent into hooks, with broad planar faces and relatively uniform-width arcs; the clay view confirms that this is a volume problem rather than only a toon-shadow artifact.
- **hair_back** (gpt-6-astra) [naturalness] Central rear hair mass from shoulder blades to waist: The upper back is a nearly uninterrupted shell while the lower half suddenly separates into deep channels and hanging strips. This abrupt change in structure makes the mass feel helmet-like above and fragmented below.
- **rig** (gpt-6.1-sol) [animation] Both knees, especially the inner bend and the front of the joint: The squat produces sharply cut inner corners and an angular thigh-to-shin turn instead of a rounded kneecap wrapping around a compressed rear crease. This is clearly visible at the pose-sheet scale.
- **rig** (gpt-6-astra) [animation] Both knees, particularly the inner bend and anterior knee contour: The deep squat produces pointed outer knees and a tightly pinched inner bend. The calf-to-thigh transition loses volume and reads as a folded tube.
- **sleeves** (gpt-6-astra) [animation] Both sleeve bags around the elbow-level gathering transition: Raising the arms changes the soft sleeve bags into squared, sharply folded blocks, with an abrupt narrowing below the fuller cuff section. The deformation loses the rounded fabric volume established in the rest pose.

## Per-pose rating

clean / minor / major / broken: parts at fault, note.

| pose | gpt-6.1-sol | gpt-6-astra |
|---|---|---|
| walk | **clean** The stride preserves visible limb continuity, and the skirt, sleeve cuffs and waist ribbons follow without an obvious clip or separation in either view. | **clean** The visible stride preserves leg, sleeve and skirt continuity without a clear new collapse or penetration in either view. |
| arms_up | **minor** (sleeves) The sleeve bags acquire small dents and abrupt changes of section immediately above their green upper bands, most clearly on the near arm in the three-quarter view. | **major** (sleeves, rig) Both raised sleeves compress into angular elbow-level blocks, especially in the three-quarter view, with a sharp transition between the inflated cuff section and the gathered lower section. |
| squat | **major** (body, rig) Both bent knees become angular hinges with deeply cut inner creases and insufficient rounded volume around the turn in the three-quarter view. | **major** (body, rig) The three-quarter view shows sharply pinched inner knees and angular outer knee contours instead of a rounded, volume-preserving bend. |
| forward_bend | **clean** The bodice, waist attachments and visible limbs remain continuous through the bend, with no definite new penetration visible in these views. | **minor** (bodice, rig) The front waist and lacing compress into a short angular crease, most apparent beneath the bust in the three-quarter view. |
| head_left | **clean** The face, head ornaments and neck cords follow the head turn without an obvious detached attachment or neck collapse. | **clean** The turned head and face-framing locks remain connected without an obvious neck tear or newly exposed gap. |
| swing | **minor** (skirt) The trailing skirt edge develops a narrow projecting point on image-right in the three-quarter view, making the moving hem look locally stretched. | **clean** The displaced hair and skirt retain continuity, with no definite new penetration or tearing visible at this sheet resolution. |

## By part

### hair_back

- **P1** [naturalness] (gpt-6.1-sol) *clay q34_back_right* - Lower central and image-right locks, immediately above the skirt: The free ends read as thick cut slabs: several narrow into rectangular tabs or turn through abrupt corners before reaching their curls. These are visible form defects in clay, so cleaning the cel ramp alone will not resolve them.
  - Fix: In hair_back.py, revise the last two width stations and terminal thickness of the affected primaries rather than ending a broad section abruptly. Extend the taper over roughly 4–6 cm, bring width and thickness smoothly toward zero, and insert intermediate sections wherever the terminal silhouette changes direction; retain a rounded lens section through the transition.
- **P1** [naturalness] (gpt-6.1-sol) *q34_back_right, clay q34_back_right* - Three large lower curls across the back: The curls have angular inner openings and locally flattened bends, giving them the appearance of bent straps or molded hooks rather than soft hair clumps. Their silhouettes deteriorate markedly away from the calibrated back view.
  - Fix: In hook() and the fitted MAIN curl definitions, enlarge the tightest inner bend and distribute section roll over the full curl entrance. Use approximately 2 px spine spacing and a maximum 3-degree turn between rings in these curls, then inspect the inner contour after _clear_rings(); smooth its clearance displacement along arc length so the skirt correction does not introduce a new elbow.
- **P1** [naturalness] (gpt-6.1-sol) *clay back, clay q34_back_right* - Overlapping locks from the shoulder blades to the lower back: Broad locks merge for long stretches and then separate into deep, abrupt slots and exposed ledges. The result reads as stacked shells rather than a coherent mass with individually flowing locks.
  - Fix: Adjust the per-lock lay and width schedules in primaries() so neighboring visible surfaces maintain a consistent overlap order. Replace abrupt exposed ledges with 4–8 cm transitions, keep approximately 0.3–0.5 cm separation where locks visibly overlap, and shorten or recess the backing curtain where it appears between free tips; preserve each lock as a separate riggable island.
- **P1** [naturalness] (gpt-6.1-sol) *back, q34_back_right, 05_islands back* - Pale back-hair surface and the white-to-mint transition above the curls: Thin disconnected grey marks and jagged shade boundaries make the otherwise broad pale surface look chipped. The back view contains 22 small hair shade islands, and the three-quarter view exposes additional narrow strips along lock overlaps.
  - Fix: After repairing the overlaps, smooth the own-normal contribution spatially in set_volume_normals(), tapering it toward the shared volume field near flush lock edges. Use a continuous transition into LOW_KEEP and CURL_KEEP rather than letting a narrow exposed edge suddenly take its full section normal; keep grad_global continuous across adjacent locks and their terminal rings.
- **P1** [naturalness] (gpt-6-astra) *q34_back_right, clay q34_back_right* - Lower central back locks immediately above the curled ends: Several broad locks terminate in blunt, angular steps before joining the curls; the resulting rectangular notches and exposed overlap edges make the hair look assembled from cut strips.
  - Fix: In hair_back.py clump(), _layer() and hook(), carry width and thickness continuously through the lock-to-curl transition instead of allowing a broad terminal section to end beside a narrow hook. Taper over roughly 4–6 cm, insert transition rings at 0.5–0.8 cm spacing, and bury covered ends fully beneath the next lock.
- **P1** [naturalness] (gpt-6-astra) *back, q34_back_right, clay back* - Large lower U-shaped curls across the back waist: The curls read as flat straps bent into hooks, with broad planar faces and relatively uniform-width arcs; the clay view confirms that this is a volume problem rather than only a toon-shadow artifact.
  - Fix: Give hook() a progressively rounder lens section through the bend, increasing CURL_TH from 0.38 toward 0.5–0.6 as an initial test. Vary the curl plane and depth by about 1–2 cm between neighbouring locks, and taper both width and thickness continuously through the final third of each curl.
- **P1** [naturalness] (gpt-6-astra) *clay back, clay q34_back_right, back* - Central rear hair mass from shoulder blades to waist: The upper back is a nearly uninterrupted shell while the lower half suddenly separates into deep channels and hanging strips. This abrupt change in structure makes the mass feel helmet-like above and fragmented below.
  - Fix: In primaries(), introduce shallow, staggered separations earlier along the spines and increase their depth gradually toward the waist. Recess curtain() behind the visible locks by approximately 0.5–1 cm where exposed, and blend each primary's layer offset over a longer span so the grooves do not start abruptly.
- **P2** [naturalness] (gpt-6-astra) *back, q34_back_right, islands back* - Pale rear hair surface and boundaries above the green tips: Narrow shadow slivers and isolated wedges interrupt the broad pale hair masses. The back view has 22 detected hair islands, and several coincide with visible lock transitions rather than useful strand definition.
  - Fix: After repairing the overlaps, make set_volume_normals() blend smoothly by spine distance and section angle, particularly where LOW_KEEP and CURL_KEEP take over. Remove abrupt changes in the custom-normal blend and test the same locks under intermediate camera angles; preserve their rounded form rather than replacing all normals with one flat field.

### rig

- **P1** [animation] (gpt-6.1-sol) *squat q34_front_left* - Both knees, especially the inner bend and the front of the joint: The squat produces sharply cut inner corners and an angular thigh-to-shin turn instead of a rounded kneecap wrapping around a compressed rear crease. This is clearly visible at the pose-sheet scale.
  - Fix: Retune the knee partition in _split_joint_aux() so front-of-knee vertices spread their rotation over roughly 5–7 cm while the rear crease uses a narrower 2–3 cm band. Adjust the existing knee helper shares to support the intermediate bend, and preserve the front section with a small outward correction of about 0.5–1 cm at deep flexion. Implement the support through exportable helper weights or an equivalent PMX corrective path.
- **P1** [animation] (gpt-6-astra) *squat q34_front_left* - Both knees, particularly the inner bend and anterior knee contour: The deep squat produces pointed outer knees and a tightly pinched inner bend. The calf-to-thigh transition loses volume and reads as a folded tube.
  - Fix: Spread thigh-to-shin weights across approximately 4–6 cm around the fitted knee pivot and add a bend corrective that restores the anterior knee volume while limiting compression behind the joint. In body.py, place supporting rings about 1 and 2 cm on either side of the pivot if the existing stations do not cover that bend zone; validate with PMX-compatible weighting or an explicitly supported corrective path.

### sleeves

- **P1** [animation] (gpt-6-astra) *arms_up front, arms_up q34_front_left* - Both sleeve bags around the elbow-level gathering transition: Raising the arms changes the soft sleeve bags into squared, sharply folded blocks, with an abrupt narrowing below the fuller cuff section. The deformation loses the rounded fabric volume established in the rest pose.
  - Fix: Retune _sleeve_gather_co() and _sleeve_weights() in rig.py to spread radial compression across several sleeve rings instead of concentrating it near the gather boundary. Reduce the local deflation first, preserve a rounded cross-section through the elbow, and recompute levi_sleeve_s from the revised sleeve centreline so the bag and its decorations follow the same transition.
- **P2** [naturalness] (gpt-6.1-sol) *front, q34_front_left, clay front* - Green upper-arm bands and their ruffled upper edges: The upper bands read as thick, jagged collars with isolated pointed projections. Their silhouette is harder and more mechanical than the soft gathered sleeve beneath them.
  - Fix: Reshape _ruffle_bm() so the ruffle has rounded lobes with a gradual rise from the band. Reduce the longest isolated projections by about 0.5–1 cm and roll the exposed edge through several sections; keep the band thin and let the gathering come from a curved cloth surface rather than a thick zigzag rim.
- **P2** [animation] (gpt-6.1-sol) *arms_up q34_front_left* - Sleeve bags immediately above the green upper bands, especially the near sleeve: Raising the arms creates small pinches and uneven section changes at the lower end of the now upright sleeve bags. The deformation looks locally compressed rather than gathered into soft folds.
  - Fix: In _sleeve_weights() and the SLEEVE_GATHER corrective, spread the arm-to-drape handover across an additional 2–3 cm near the band and limit radial deflation there. Drive the attached band and nearby ribbon roots from the same sampled sleeve field, while keeping the cuff anchored to the wrist.
- **P2** [fidelity] (gpt-6-astra) *front, q34_front_left* - Green upper-arm ornaments and sleeve silhouette: The sheet's layered leafy bows have become narrow dark bands with small projecting points, and the sleeve bags are more uniformly balloon-shaped. The characteristic leafy attachment and open bell-like drape are weakened.
  - Fix: In _bow() and _ruffle_bm(), give the major leaf or loop lobes distinct rounded volumes and stagger their depth by about 0.3–0.6 cm. In the sleeve profile, redistribute some mid-bag fullness toward the lower flare while retaining room for the forearm and the corrected overhead deformation.

### accessories

- **P2** [naturalness] (gpt-6.1-sol) *05_islands front, 05_islands high* - Head leaf clusters around the flowers: Small disconnected dark patches break up the leaves near their roots and tips. On these compact ornaments the patches obscure the intended central fold and make the leaf surfaces look irregular.
  - Fix: Give each blade a continuous shading field based on its broad cupped surface, preserving a deliberate change across the central fold. Smooth the root-to-tip bend and twist derivatives in the leaf builder, and keep vein normals and the blade's rolled edge from perturbing the broad face normals.

### hair_front

- **P2** [naturalness] (gpt-6-astra) *q34_front_left, high, clay q34_front_left* - Long face-framing locks beside the cheeks and shoulders: The framing locks read as narrow blades with abrupt tips and relatively little sectional fullness, particularly when viewed obliquely beside the face.
  - Fix: Round the lock cross-sections into shallow lenses and distribute the terminal taper over the last 2–3 cm. Add a small depth turn along each centreline so the broad face does not remain aligned to one viewing plane, while preserving the current face clearance.
- **P2** [fidelity] (gpt-6.1-sol) *front, q34_front_left* - Crown, fringe roots and face-framing locks: The crown and fringe read as a relatively smooth helmet with a short row of pointed bangs. The sheet has more clearly separated, longer flowing clumps, and the model's straight cheek-side pieces make the face framing more rigid.
  - Fix: Redistribute the front clump widths and root overlaps so a few distinct locks remain legible from the crown into the fringe. Add a gentle depth bend to the straight cheek-side locks, moving their middle sections outward by approximately 0.5–1 cm while keeping the tips tapered and the roots buried in the cap.

### petticoat

- **P2** [naturalness] (gpt-6.1-sol) *side, q34_front_left, clay q34_back_right* - Exposed pink tiers, particularly the rear side and outer corners: Several gathers read as straight accordion panels with triangular ends and tightly stacked rims. The sharp panel-like folds contrast with the rounded, airy fabric expected beneath this dress.
  - Fix: In petticoat.py, broaden the narrowest gather valleys and reduce their local depth by approximately 20–30%. Round each fold's exposed lower corner through the existing PROFILE and hem-roll rings, and vary neighboring tier heights by about 0.5–1 cm so their rims do not form a stack of parallel plates.
- **P2** [naturalness] (gpt-6-astra) *q34_front_left, clay side, clay q34_back_right* - Exposed pink tiers along the side and rear hem: The petticoat alternates between flat hanging bands and sharply folded accordion-like sections. Several exposed undersides read as stacked plates instead of soft gathered fabric.
  - Fix: Smooth the tier radius and height derivatives across fold boundaries in petticoat.py, reduce the deepest narrow gathers, and add cross-band samples where the cloth turns under. Keep the rolled edge thin and maintain roughly 0.3–0.5 cm separation between adjacent exposed tiers rather than allowing nearly coincident rims.
- **P2** [fidelity] (gpt-6.1-sol) *front, side* - Pink gathers visible beneath the front and side skirt openings: The visible petticoat is predominantly a thin continuous pink band instead of the fuller clustered ruffles in the sheet. Its front visible pixel area is only about 62% of the reference, consistent with the missing exposure seen in the comparison.
  - Fix: After opening the overskirt valleys, adjust the tier hem and cluster_rows() schedules to form rounded clusters under those openings. Lower selected exposed gathers by approximately 1–2 cm and increase their local outward fullness by 0.5–1 cm, retaining CLEAR beneath the actual skirt surface.
- **P2** [fidelity] (gpt-6-astra) *front, side* - Visible ruffle band below the main skirt: The front and side expose substantially less pink ruffle than the sheet, and the remaining band lacks its clustered, rounded fullness. The reported visible areas support this difference: 9,581 versus 15,353 pixels in front and 8,112 versus 11,895 at the side.
  - Fix: After softening the folds, lower selected outer-tier scallops by roughly 1–2 cm and increase their outward fullness locally beneath the skirt openings. Adjust front and side sectors independently; the back already exposes comparable total pink area and should not receive the same global enlargement.

### skirt

- **P2** [naturalness] (gpt-6.1-sol) *q34_front_left, high* - Front-right skirt panel and the broad lower front: The cel render alternates between large almost featureless panels and isolated tapered shadow wedges. The folds visible in clay do not consistently read as continuous fabric valleys in the final shading.
  - Fix: In _shade_normals(), preserve the low-frequency normals of the main godet folds and suppress only the smaller relief contribution. Make the normal blend vary smoothly from waist to hem, and broaden the narrow valley transitions that produce isolated wedges; retain the two-tone ramp rather than adding a global soft shading band.
- **P2** [naturalness] (gpt-6-astra) *high, clay high, q34_front_left* - Main skirt body from waist to the broad front and side hem lobes: The skirt reads as a stiff inflated bell with broad petal lobes and relatively little gathering between them. The high view exposes large uninterrupted surfaces that feel more like a moulded shell than light fabric.
  - Fix: In profiles() and fold_growth(), introduce a few shallow secondary folds that begin below the waist and merge into the existing hem folds. Use about 0.5–1 cm of radial relief initially, taper it out at the waistband, and soften the strongest outward hem turns without adding more silhouette scallops.
- **P2** [animation] (gpt-6.1-sol) *swing q34_front_left* - Trailing hem on image-right, behind the near hand: A narrow hem section projects outward as a pointed flap during the swing. Its sharper, longer shape makes the cloth look stretched between neighboring driven sectors.
  - Fix: Smooth the skirt-chain weight transition across the two sectors bordering this flap, including the corresponding hem roll and petticoat attachment. Reduce the local difference in chain rotation before adding mesh density, and distribute the trailing displacement over approximately 5–8 cm of hem arc rather than a single narrow lobe.
- **P2** [fidelity] (gpt-6.1-sol) *front, back* - Lower skirt silhouette and the raised valleys between its main lobes: The overskirt reads as a broad bell with a small number of dominant scallops, covering much of the petticoat where the sheet shows deeper openings and more distinct hanging panels. The high overall silhouette IoU conceals this internal design difference.
  - Fix: Revise the affected FOLDS crest and trough heights locally, raising selected valleys by approximately 2–4 cm and preserving the neighboring lobe bottoms. Blend each change upward over several skirt rings and around the circumference so the extra petticoat exposure comes from plausible folds rather than cutout notches.

### bodice

- **P2** [animation] (gpt-6-astra) *forward_bend front, forward_bend q34_front_left* - Front waist between the lower bust and waist bow: Forward bending concentrates compression into a narrow angular band, crowding the lacing and reducing the bodice to a sharp waist hinge.
  - Fix: Broaden the lower-to-upper torso weight transition over several bodice rings and add a mild forward-bend corrective that maintains the front-to-back section depth. Transfer the corrected surface motion to the lacing and eyelets so their spacing compresses gradually rather than converging at one row.

### shoes

- **P2** [fidelity] (gpt-6.1-sol) *front, back* - Toe boxes and rear heel counters: The front toe boxes are rounder and more upright than the sheet's tapered points, while the rear counters form broad dark vertical masses. The side silhouette is considerably closer than the front and back shapes.
  - Fix: In shoes.py, narrow the last two toe sections by approximately 10–15% and extend the tip forward by about 0.5–1 cm while retaining toe-box height. Taper the rear counter toward the heel seat and keep its outer silhouette distinct from the stiletto shaft, preserving clearance around the foot.
- **P2** [fidelity] (gpt-6-astra) *front, back, q34_back_right* - Toe boxes and rear heel-counter silhouettes: The shoes are rounder and bulkier in front and rear views than the reference's tapered pumps. The back view reads as two broad green columns with less separation between heel counter and stiletto.
  - Fix: Narrow the toe-box side sections by approximately 0.3–0.5 cm per side as a starting test, extend the taper toward the tip, and tighten the heel-counter section around the foot. Preserve the existing ankle pivot and sole contact while opening the silhouette between the heel counter and stiletto.

### lookdev

- **P3** [fidelity] (gpt-6-astra) *front, side, back* - Green ornaments and exposed pink petticoat: The green decorations and pink ruffles are consistently flatter and less shaded than the sheet, despite the green region's average colour being fairly close. This reduces depth and detail separation after the larger form differences.
  - Fix: Once the geometry and normals are stable, tune the relevant material thresholds separately in the existing per-key ramp controls. Increase broad shade coverage on green ornaments and pink tiers without changing the global light or adding a third tone, and reject settings that increase detached shade specks.

## Metrics vs baseline `..\..\..\..\..\AppData\Local\Temp\claude\C--Users-futri-Desktop-LeviChan--claude-worktrees-levi-character-modeling-771bd2\adb9fe91-4f41-4ccb-9de8-2dd654b3b7a5\scratchpad\k\base\out\review_base`

Per view and region, `new (delta)`; `*` = whole view (silhouette IoU, island total). iou/tol up is better; dE/dEi (interior colour error), islands and island_px down is better; shade is the render's shade share (compare with the sheet in shade_stats.txt).

| view | region | iou | tol | dE | dEi | shade | islands | island_px |
|---|---|---|---|---|---|---|---|---|

## Shape-master fit vs baseline

target->ours distance (mm, down is better) and covered share (up is better), from tools/shape_fit.py: `new (delta)`.

| part | p50 mm | p90 mm | covered |
|---|---|---|---|
| body | 8.6 (+0.0) | 24.2 (+0.0) | 0.312 (+0.000) |
| head | 6.2 (+0.0) | 19.8 (+0.0) | 0.426 (+0.000) |
| hair_front | 4.5 (+0.0) | 14.9 (+0.0) | 0.535 (+0.000) |
| hair_back | 25.4 (+0.0) | 77.3 (+0.0) | 0.170 (+0.000) |
| accessories | 4.7 (+0.0) | 11.6 (+0.0) | 0.522 (+0.000) |
| bodice | 9.1 (+0.0) | 25.9 (+0.0) | 0.264 (+0.000) |
| skirt | 14.6 (+0.0) | 48.3 (+0.0) | 0.204 (+0.000) |
| petticoat | 13.7 (+0.0) | 34.5 (+0.0) | 0.190 (+0.000) |
| sleeves | 11.7 (+0.0) | 27.4 (+0.0) | 0.240 (+0.000) |
| shoes | 7.4 (+0.0) | 18.7 (+0.0) | 0.347 (+0.000) |

