# Pose A/B, shuffled (main vs this PR)

Key (order, pose, which version is A and B). Prompt: `prompt_ab_poses.md`.

```
1 sit_chair A=main B=PR
2 sit_chair A=PR B=main
1 seiza A=PR B=main
2 seiza A=main B=PR
1 kneel_one A=main B=PR
2 kneel_one A=PR B=main
1 deep_lunge A=PR B=main
2 deep_lunge A=main B=PR
1 cross_legged A=main B=PR
2 cross_legged A=PR B=main
1 walk@14 A=PR B=main
2 walk@14 A=main B=PR
1 run@8 A=main B=PR
2 run@8 A=PR B=main
1 spin@20 A=PR B=main
2 spin@20 A=main B=PR
```

## pz1_gpt-6-astra

POSE 1: A (low) - The overskirt follows the knees more smoothly, and the pink front hem has slightly more even, rounded folds; B adds some angular bunching near the lap.
POSE 2: A (low) - The white skirt transitions more cleanly from waist to lap, especially in the three-quarter view; B has a sharper crease and shadow patch above the knees.
POSE 3: B (low) - The three-quarter overskirt falls in a more continuous curve beside the raised knee; A has a more pronounced hooked outer hem and a sharper transition into the pink layers.
POSE 4: A (low) - The white outer hem and pink ruffles read slightly more cleanly in three-quarter view; B introduces extra angular waviness without clearly improving the cloth’s response to the pose.
POSE 5: B (medium) - The overskirt curves and gathers more convincingly around the crossed legs, with better overlap between white and pink layers; A looks more like a broad, flat flap across the lap.
POSE 6: A (low) - Both have similar silhouettes, but A keeps the white skirt’s shading more coherent; B adds small isolated crease shadows that make the cel surface look slightly uneven.
POSE 7: B (low) - The added shallow folds give the flared overskirt more cloth structure, particularly on the front-left portion; A looks slightly more uniformly inflated.
POSE 8: B (low) - The rear three-quarter hem has slightly more believable variation and separation between the pink layers, though both versions retain a fairly stiff, shelf-like flare.
TOTAL: A=4 B=4 tie=0

## pz1_gpt-6.1-sol

POSE 1: B (low) - The overskirt drapes slightly more smoothly across the lap, with a less abrupt hem transition in the 3/4 view; both retain a somewhat bowl-like petticoat.
POSE 2: B (low) - The pink folds around the tucked knees look slightly less pinched, and the front hem reads more cleanly while preserving the layered silhouette.
POSE 3: A (low) - The overskirt flows a little more continuously over the raised knee; B has a slightly sharper gathered ridge there, most visible from the front.
POSE 4: A (low) - The 3/4 overskirt hem has a slightly smoother descending contour; B introduces a more abrupt inward kink near the trailing side.
POSE 5: tie (medium) - Both show the same broad, shelf-like overskirt across the crossed legs and stretched-looking pink side panels; the fold differences do little to improve the cloth behavior.
POSE 6: tie (medium) - Both have a clean, readable walking silhouette and similar shallow hem waves; neither shows a clear advantage in folds, layering, or visible intersections.
POSE 7: B (low) - The flared overskirt has slightly softer fold transitions and a more continuous hem in the 3/4 view, giving the cel shading a cleaner flow.
POSE 8: tie (medium) - The rear and side silhouettes, pink layering, and hem flow are nearly equivalent; both retain a broad, rigid-looking flare rather than convincing twisting folds.
TOTAL: A=2 B=3 tie=3

## pz2_gpt-6-astra

POSE 1: B (low) - The overskirt gathers more convincingly across the lap and the pink hem hangs slightly more evenly, although both retain a broad bowl-like petticoat.
POSE 2: A (low) - The side-view overskirt settles into a rounder outline around the folded legs; B has a more extended, pointed flap near the rear hem.
POSE 3: B (medium) - The fabric transitions more smoothly over the raised knee, with less pinching in the pink ruffles and a cleaner overskirt silhouette in the three-quarter view.
POSE 4: B (medium) - The overskirt has more coherent fold shading across the lap and flank; A's angular light patches make the cloth look more faceted and dented.
POSE 5: tie (low) - Both show similar broad bridging over the crossed legs and a shelf-like front fold; the small hem and shading differences do not clearly improve the cloth behavior.
POSE 6: A (low) - The overskirt has broader, more continuous fold shapes and a calmer hem; B adds narrow, angular creases near the side that look slightly pinched.
POSE 7: A (medium) - The long folds flow more clearly from the waist toward the flared hem; B breaks them into smaller angular patches that weaken the clean cel-shaded cloth shape.
POSE 8: tie (low) - Both have essentially the same flared, slightly rigid skirt profile and layered pink hem; the changed shadow patches offer no clear improvement in deformation or fold believability.
TOTAL: A=3 B=3 tie=2

## pz2_gpt-6.1-sol

POSE 1: A (low) - The front petticoat has slightly broader, smoother folds; B looks more pinched along the upper pink ruffle.
POSE 2: A (low) - The pink hem gathers more softly around the tucked legs; B has slightly sharper, more crowded creases in the 3/4 view.
POSE 3: tie (low) - Both show similar skirt clearance and plausible asymmetric draping, with some crowded folds around the raised knee.
POSE 4: tie (low) - Both retain a somewhat stiff, projecting overskirt over the bent thigh; neither clearly improves the hem or cloth clearance.
POSE 5: tie (medium) - Both form a broad, bowl-like petticoat beneath the crossed legs, with similarly abrupt overskirt folds around the shoes.
POSE 6: tie (low) - Both have a clean flared silhouette and readable cel shading; the small fold differences do not clearly improve the walking drape.
POSE 7: A (low) - The moving hem reads slightly more continuously; B has a few sharper, busier pink folds beneath the front-left overskirt edge.
POSE 8: A (low) - The rear overskirt has smoother, broader shading shapes; B adds small angular patches without a clear improvement in the spinning drape.
TOTAL: A=4 B=0 tie=4
