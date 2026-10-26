# Rest-view A/B, shuffled (main vs this PR)

Order rg1: A = main, B = this PR. Order rg2: A = this PR, B = main. Images: cel and clay; front, 3/4 front-left, high and back; skirt crop. Prompt: `prompt_ab_rest.md`.

## rg1_gpt-6-astra

**Image 1 — cel-shaded: B, by a small margin.**  
B gives the overskirt a clearer sense of cloth hanging from the waist. In the front and 3/4 views, the longer shadow shapes describe folds running down into the hem lobes more coherently; A’s broader, quieter shading makes parts of the skirt look like a smooth inflated shell. B’s back view also has a more legible fold on the right half, although its narrow shadow strip is a little too abrupt.

The **hem silhouette is very similar** in both versions. B’s fold shading helps explain the waves, but neither fully resolves the slightly stiff, petal-like quality of the edge. The cel image does not show a decisive improvement in actual edge thickness.

The **pink petticoat is close to a tie**. B reads slightly more clearly as a separate layer in places, but the front still presents a broad, relatively flat pink band with small scallops along its lower edge. The back has more convincing layered ruffles than the front in both versions. B wins primarily on the overskirt’s fold readability, not on a substantial ruffle improvement.

**Image 2 — clay: B, with reservations.**  
The clay render makes B’s advantage clearer: in the front and 3/4 views, its deeper channels and narrower ridges give the skirt more structure between the waist and the hem. The alternating projecting and receding sections feel more like fabric folding around a flared volume. A is smoother, but several large areas read as rounded bulges with limited internal folding.

B sometimes pushes that improvement too far. In the high-front view, the narrow crease just right of the central hanging ribbons is sharper than the surrounding folds, and the back has a conspicuously straight, concentrated groove on the right half. These give local areas a sculpted or pressed appearance.

The **hem remains somewhat thick-looking and rolled** in both versions, especially around the central front lobe. The broad dark area beneath it includes shadow and exposed underside, so I would not interpret all of that band as literal mesh thickness. Nevertheless, the rounded transition into the edge makes the cloth look heavier than the intended lightweight dress.

The **petticoat still has a fairly regular fluted construction** in both versions. B does not clearly solve that: the exposed front ruffles resemble repeated little fans, while the back reads as a continuous corrugated strip. Their depth is useful, but their rhythm and attachment need more variation.

OVERALL: B — confidence: medium

Remaining problems in **B**, ordered by your priorities. The fixes below are based on the visible result; the crops do not establish the underlying mesh or shader cause.

| Priority | View | Location | Remaining problem | Concrete fix |
|---|---|---|---|---|
| **1 — believable cloth** | Front and 3/4 front-left | Main overskirt folds, from mid-skirt to hem | The stronger folds improve the form, but several still terminate in broad, rounded lobes that feel like sculpted petals. | Vary fold width and depth gradually along their length. Let a few secondary folds fade out before the hem, and make adjacent valleys reach the hem at slightly different angles. Preserve the overall flare. |
| **1 — believable cloth** | High front | Immediately right of the hanging ribbons | A narrow, deep channel contrasts too strongly with the broad surrounding cloth surfaces. | Broaden the valley and soften its cross-section; taper its depth more gradually toward the waist so it does not read as a sharply pressed groove. |
| **1 — believable cloth** | Back | Right half of the skirt, below the hair | The prominent near-vertical fold is unusually straight and concentrated. | Give the fold a gentle lateral drift, soften the ridge, and spread its curvature across a wider area before it joins the hem. |
| **1 — believable cloth** | Front and 3/4 front-left | Central overskirt hem and adjacent lobes | The edge looks rounded and substantial, especially in clay. | Reduce the edge’s rounded profile or bevel. If the geometry is already thin, adjust the local curvature and normals so the face does not roll broadly into the underside. Retain a small, consistent physical thickness. |
| **1 — believable cloth** | Front; back | Exposed petticoat beneath the central lobe; long rear ruffle band | Front ruffles look like isolated regular fans; rear ruffles look uniformly corrugated. The cel front also loses much of their gathered depth. | Vary gather spacing, amplitude and tilt modestly. Carry each gather upward into the concealed attachment area, and vary overlap and exposure so the ruffles read as a continuous gathered fabric layer. |
| **2 — unrealistic shapes / pinches** | 3/4 front-left | Small hem notch on the image-right side, above the petticoat | A tight notch and small light underside patch create an eye-catching, hole-like detail in clay. It is not clearly an intersection, but the local shape feels cramped. | Open and smooth that notch, then check clearance between overskirt and petticoat through nearby viewing angles. Remove any local collision or excessively folded-back edge if present. |
| **3 — clean cel appearance** | Front, high front and back | Narrow fold-shadow tips and the rear vertical shadow strip | Some shadow shapes end abruptly or become thin slivers, making the surface look harder than the intended cloth. | Refine the geometry and normals in those regions first, then tune the toon threshold so fold shadows form deliberate, continuous shapes without losing the depth that makes B stronger. |

I do not see an obvious isolated shading speck on the skirt in these supplied crops. The remaining concerns are principally fold curvature, the hem’s apparent weight, and the regularity of the petticoat gathers.

## rg1_gpt-6.1-sol

**Image 1 — cel render: B, by a small margin.**

- **Skirt folds:** B gives the front and front-left views a clearer downward flow. The additional narrow folds help connect the upper skirt to the larger waves at the hem, making the fabric feel more responsive to gravity. A is cleaner, but its broad, uninterrupted areas—especially in the high-front view—read a little more like a smooth molded shell. B’s drawback is that a few of those extra folds become thin, isolated shadow streaks.
- **Hem edge:** B has slightly better definition where the folds meet the hem, particularly at the back. However, both versions retain a conspicuously even band along parts of the back edge, which makes the white fabric look thicker and stiffer than the rest of the dress suggests.
- **Petticoat:** B’s exposed pink layer has a somewhat more varied, gathered rhythm in the front-left and back views. The improvement is modest: several scallops still resemble flat, overlapping lobes, and the relationship between the white hem and pink ruffles could be more convincing.

**Image 2 — clay render: B, with reservations.**

- **Skirt folds:** B’s narrower secondary folds give the broad godet shapes more internal structure. In the front and high-front views, this helps the skirt read as cloth falling into folds instead of a uniformly inflated surface. A has smoother shading, but several of its large rounded lobes look overly full and rigid. B still needs a more deliberate transition between its shallow upper folds and deep lower valleys; adding narrow grooves alone does not fully solve that.
- **Hem edge:** B slightly reduces the heavy, rolled appearance of the back hem, though a broad horizontal strip remains. The fold tips and valleys also need more variation in curvature: some transitions remain rounded like molded plastic, while others tighten abruptly.
- **Petticoat:** The clay makes the remaining weakness clearer in both versions. The exposed ruffles have deep, fairly regular flutes, with some pointed troughs and a dark, continuous recess beneath the overskirt. B is marginally more articulated, but the petticoat still feels more like a corrugated ring than soft gathered fabric. This is the largest remaining form issue.

**Remaining problems in B**, ordered by your priorities. These are visual diagnoses from the renders; the exact mesh or shader cause would need inspection.

| Priority | View | Location and problem | Concrete fix |
|---|---|---|---|
| **1 — cloth form** | Front, front-left, high front | The overskirt still consists of very full, rounded lobes, with a few narrow creases laid between them. Some creases fade before meaningfully changing the hem. | Rebalance the main fold cross-sections: use broader transitions into the valleys, reduce some convex bulges, and carry selected folds continuously into corresponding hem rises or dips. Vary their depth and spacing. |
| **1 — petticoat** | Front and front-left; also visible at back | Exposed ruffles form relatively regular flutes, with sharp troughs and small fan-like sections. They do not consistently convey a gathered upper attachment opening into a softer lower edge. | Concentrate smaller gathers near the attachment, then let them broaden and relax downward. Round the tightest troughs, vary scallop width and amplitude, and introduce controlled overlaps between adjacent ruffles. |
| **1 — hem thickness** | Back, across the broad central white hem | The continuous horizontal band makes the hem resemble a thick rolled rim. | Reduce the visible edge thickness and soften the broad bevel or rounded transition. Keep a thin fabric edge whose orientation changes with each fold instead of maintaining a uniform frontal band. |
| **2 — local pinching** | High front and front-left | Some inward hem notches and the petticoat immediately beneath them turn tightly, producing small bright tips beside deep dark recesses. | Relax the curvature at these notches, spread the turn over a wider area, and check the layer spacing so the pink fabric does not bunch into narrow wedges beneath the white edge. |
| **2 — layer separation** | Front-left and back | The dark gap between skirt and petticoat sometimes reads as a continuous cavity rather than intermittent cloth overlap. | Bring the petticoat closer beneath selected portions of the hem, vary the clearance, and check contact shading after the geometry is settled. Preserve local gaps where the skirt lifts. |
| **3 — cel readability** | Front, near the central hanging ribbons; high front, central skirt | Several narrow fold shadows read as detached tapered marks rather than part of a larger fold pattern. | First broaden or reduce the shallow creases responsible. Then tune the toon threshold and lighting so the surviving shadows form coherent shapes that explain the cloth volume. |

OVERALL: B — confidence: medium

## rg2_gpt-6-astra

**Image 1 — cel render: A, narrowly.** The overskirt is very similar in both versions: both retain the broad godet folds and a clear, wavy silhouette. The stronger distinction is the petticoat. In A, particularly in the **back view**, the pink ruffles have a looser rhythm, with more variation in the spacing and size of the scallops. B’s lower ruffle reads as a tighter, more repetitive series of small waves, and the closely spaced contour lines make that area look busier. A also gives slightly clearer separation between the large overskirt waves and the smaller petticoat gathers.

The overskirt hem is reasonably clean in both. Neither version fully resolves its slightly thick, rounded appearance, although cel shading hides much of this. B does not offer a sufficiently clear improvement in the main skirt folds or hem to outweigh A’s more relaxed petticoat treatment.

**Image 2 — clay render: A, narrowly.** The clay views make the shared limitations more apparent. Both skirts have broad, smooth fold volumes, but the lower portions sometimes resemble inflated lobes rather than fabric opening into godet folds. This is especially visible in the **high-front view**, where the large rounded hem waves dominate the form and their connection to the folds above is less convincing.

A’s advantage is again primarily the petticoat: its exposed folds read a little more as individual gathered cloth flutes. In B, especially at the **back**, the narrower, more regular rippling approaches a corrugated trim. The main overskirt is close enough that I would not claim a decisive improvement in fold depth or surface quality for either version. Both also have a conspicuous dark band beneath parts of the hem; the clay render suggests a combination of rounded edge geometry and occlusion, rather than an outline-only issue.

**Remaining problems in A, ordered by your priorities:**

| Priority | View | Location / problem | Concrete fix |
|---|---|---|---|
| **1 — Cloth form** | High front; front | The large lower skirt waves are rather bulbous. Some read as rounded masses with shallow valleys between them, instead of folds that progressively open toward the hem. | Carry the principal fold valleys farther upward and taper their depth gradually toward the waist. Concentrate the outward flare nearer the bottom, reducing the inflated curvature immediately above each hem lobe. |
| **1 — Cloth rhythm** | Front; 3/4 front-left | The fold transitions are very smooth and similarly scaled, giving the skirt a somewhat molded appearance. | Introduce modest variation in adjacent fold widths and depths, with a few subordinate folds that merge into the main folds. Keep those secondary folds tied to gathering or tension rather than adding surface noise. |
| **1 — Hem construction** | Front; high front; back | Several hem sections look rounded and substantial, particularly where the edge turns over into the dark underside. This contributes to the padded appearance. | Reduce the edge’s rounded cross-section and any excessive thickness or bevel. Preserve a thin fabric edge with a restrained turned hem; retain the broad silhouette waves without rounding their entire lower boundary into a tube. |
| **1 — Petticoat** | Back; exposed front sections | A is less repetitive than B, but the petticoat still resembles a continuous fluted strip in places. The visible layered edges do not always communicate how the cloth is gathered. | Give the ruffle a clearer attachment region, with narrower folds near the gathering line that fan outward toward the free edge. Vary fold amplitude and spacing gently, and offset the folds between overlapping layers. |
| **2 — Local shape / contact** | 3/4 front-left; high front | At the lateral hem troughs, the petticoat emerges through narrow, dark gaps. Some transitions look crowded and abrupt. These crops do not establish actual intersections. | Check these locations in a close solid view. Where necessary, adjust the layer clearance and relax the tightest ruffle folds so the petticoat emerges continuously without clipping or collapsing into a narrow wedge. |
| **3 — Cel readability** | Back, along the pink lower hem | Multiple nearby ruffle contours form a dense band of lines, making the petticoat look heavier than its pastel material suggests. | After correcting the geometry, reduce outline weight on the inner ruffle edges or omit redundant hidden contours. Preserve the outer silhouette and the few overlap lines that explain the layers. |

The differences are small at this crop size. I would select A for its petticoat rhythm, while treating the overskirt’s cloth behavior as largely unresolved in both.

OVERALL: A — confidence: medium

## rg2_gpt-6.1-sol

**Image 1 — cel shading: B, by a small margin.**

- **Skirt folds:** B reads slightly more clearly as fabric hanging from the waist. In the front and three-quarter views, the folds have a little more definition as they descend into the hem lobes. A looks marginally smoother and more inflated across those areas. The difference is subtle; the silhouette and the toon shadow shapes are very similar.
- **Hem edge:** Neither has a decisive advantage here. Both have a clean, readable outline, but the large, rounded hem lobes can suggest a molded shell. B’s clearer folds help explain the waviness slightly better, though they do not fully resolve that impression.
- **Petticoat:** B’s exposed ruffles are a little more legible as folded fabric, especially in the front and three-quarter views. Some of the tighter scallops still look angular or stacked. The pink fill and outline also hide much of the depth, so I would give the clay render more weight on this point.

**Image 2 — clay: B, again narrowly.**

- **Skirt folds:** B has somewhat clearer transitions between the broad hanging panels and the valleys separating them. This gives the front and three-quarter views a more convincing downward flow. A’s softer transitions occasionally read as rounded bulges in a continuous surface. B still retains some of that inflated quality, particularly in the high-front view.
- **Hem edge:** Both versions show a substantial rounded turnover at parts of the lower edge. The dark band beneath the white skirt is partly the underside and occlusion, so I would not interpret all of it as actual edge thickness. Nevertheless, the visible silhouette and rounded shading make the edge feel heavier than light dress fabric.
- **Petticoat:** B gives the gathers slightly stronger depth, which helps separate the petticoat from the overskirt. The remaining weakness is the construction of the ruffles: several exposed sections resemble individual fluted wedges or teeth rather than a continuous gathered strip. This is particularly noticeable beneath the front-right hem and along the back.

**Remaining problems in B**, ordered by your priorities. These are observations from the renders; the suggested fixes describe the intended form rather than assuming a particular mesh setup.

| Priority | View | Location / problem | Concrete fix |
|---|---|---|---|
| **1 — believable cloth** | Front, three-quarter, high front | Some large skirt lobes still look inflated. Fold valleys and broad convex panels do not always explain how the fabric falls from the waist into the wavy edge. | Carry the main valleys farther up the skirt, letting them gradually soften toward their origins. Reduce the roundness of the broad panels between them, and vary fold width and depth slightly. Preserve the broad godet rhythm rather than adding many small wrinkles. |
| **1 — believable cloth** | Front and three-quarter | The hem reads as a thick, rounded lip at the bottoms of the largest lobes. | Reduce the edge’s rounded cross-section and any excessive local thickness. Keep a small fabric turnover, with a clearer distinction between the hanging outer surface and its underside. Check the silhouette in clay before judging the outline. |
| **1 — believable cloth** | Front, especially image-right; three-quarter, beneath the forward hem | Exposed petticoat sections form isolated triangular fans with abrupt peaks and troughs. | Make the ruffle flow continuously around the skirt. Broaden the tightest troughs, soften pointed tips, and stagger the gathers of adjacent layers so their peaks do not repeatedly line up. |
| **1 — believable cloth** | Back | The exposed petticoat forms a fairly uniform corrugated strip, while the overskirt above it has broad, regular waves. | Vary ruffle spacing, exposure and overlap modestly. Let some gathers compress beneath the overskirt and others open out, while maintaining a continuous fabric edge. |
| **2 — unwanted shapes / pinches** | Three-quarter and high front | A few narrow openings between the white hem and petticoat end in sharp, dark wedges. They make the layering look locally pinched. | Inspect these junctions from nearby angles. Ease any compressed folds, maintain clearance between layers, and smooth abrupt changes in the underside. The render alone does not establish whether these are intersections or tight occlusion. |
| **3 — clean cel look** | Front and three-quarter | Small pale shading islands on the lower puff sleeves, near the skirt, draw attention away from the larger clean shadow shapes. | If they persist during rotation, smooth the local normals or surface curvature so they merge into a deliberate highlight region. They are secondary to the skirt form and petticoat work. |

The visible differences are small enough that I would treat B as a modest improvement, with the **petticoat continuity and the overskirt’s rounded hem** still offering the largest gains.

OVERALL: B — confidence: medium
