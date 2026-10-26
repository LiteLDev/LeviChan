# Pairwise A/B judgements

Absolute per-pose ratings swing between runs on identical geometry (the same arms_up got clean / minor / major in three runs), so the variants were also ranked side by side: both Codex models saw cel crops of squat + walk (knee) or arms_up (shoulder), front and 3/4, one row per variant, in shuffled order.

## Knee: A = hinge partition (final knee), B = baseline, C = shorter hinge + slimmer knee tables (rejected)

### gpt-6.1-sol

A > C > B

A — Slight fullness at the outer knee in the squat 3/4 view, but the bend retains rounded volume and the smoothest overall contours. **minor**

C — The bent knee in the squat 3/4 view looks slightly flattened underneath, with a tighter crease; the front squat knees also show small contour indentations. **minor**

B — The bent knee in the squat 3/4 view forms a low, bulbous protrusion with an abrupt underside transition; the walk-front leg also has a more angular knee-to-shin contour. **major**

### gpt-6-astra

A > C > B

A — Slightly bulbous outer knee in the squat 3/4 view, but the bend retains rounded volume and the contours transition most smoothly. **minor**

C — The squat 3/4 knee looks slightly flattened underneath; the diagonal leg in the walk 3/4 view has a more abrupt angular transition at the knee. **minor**

B — The squat 3/4 knee has the strongest pinching at the inner fold and an angular, protruding lower contour, making the joint look compressed and knobby. **major**

## Shoulder: A = staged shoulder (final), B = baseline, C = explicit SHOULDER_JOINT (70, -27, 210) without stages (rejected)

### gpt-6.1-sol

A > B > C

A — Best overall volume and shoulder transition; the 3/4-view armpit still has a slightly sharp crease and a flat inner upper-arm plane.

B — The front-view shoulders form a conspicuously horizontal shelf beside the neck; the 3/4-view armpit ends in an angular transition into the torso.

C — Similar shoulder flattening to B, with slightly more stretched, narrow-looking upper arms immediately below the cuffs, most apparent in front view.

Ratings: A — minor; B — minor; C — minor.

### gpt-6-astra

A > B > C

A — Best overall volume and shoulder-to-chest transition; the 3/4 view still has a slightly sharp, elongated crease at the visible armpit. **minor**

B — The front-view shoulder line looks too horizontal and shelf-like beside the neck, flattening the transition into the raised upper arms. **minor**

C — Similar flat shoulder line to B, with a more abrupt, narrow-looking upper-arm transition immediately below the green sleeve cuffs, especially in the 3/4 view. **minor**
