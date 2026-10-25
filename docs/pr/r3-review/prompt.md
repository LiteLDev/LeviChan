You are a senior character artist and technical rigger reviewing a procedural anime
character model, "Levi". It is built from scratch with Blender Python (bpy/bmesh, about 30,000
faces) and cel-shaded (two-tone toon ramp with coloured inverted-hull outlines). The target is the
hand-painted three-view sheet ref/levi_threeview.png (front / side / back). The repo is your
working directory (read-only): CLAUDE.md explains the pipeline, and each part is built by
levi/parts/<part>.py. Read code only when it makes a fix concrete; the images are the main input.

Goal, in strict priority order:
  1. NATURALNESS IN 3D. The model must read as a believable, well-formed character from ANY angle,
     not only from the three calibrated orthographic views. Look for: flat or cardboard-like
     shapes seen at 3/4, faceting or triangular shading breaks, pinched or collapsing volumes,
     intersections and poke-through, floating or disconnected pieces, implausible thickness,
     hard-edged or patchy cel shadows that would never appear in the sheet's style, colour
     gradients that turn into hard bands, silhouettes that only work head-on.
  2. ANIMATION READINESS. It is rigged for MMD (PMX export). From the pose sheet and the rest
     geometry, judge: deformation at shoulders, elbows, wrists, hips, knees; cloth, hair and skirt
     following the body; candy-wrapper twists; stretching; interpenetration in poses; pieces that
     will clip or tear when animated; geometry that lacks the edge loops to bend.
  3. FIDELITY to the three-view sheet: proportions, silhouette, shapes, colours and details,
     only where they do not conflict with 1 and 2.

Images (in the order attached):
  1. 01_ortho_sbs.png: three-view sheet (top row) vs cel render (bottom row), front / side / back, orthographic and pixel-aligned
  2. 02_angles_cel.png: cel render from angles the sheet does not show: 3/4 front-left, 3/4 back-right, high front (30 deg down), orthographic, key light from the viewer's upper left
  3. 03_clay.png: clay render (grey diffuse, no outlines): all six angles, for form and faceting
  4. 04_poses.png: rigged model in test poses (front + 3/4 each), cel
  5. turntable.png: turntable: evenly spaced angles around the model, cel

Metrics (silhouette IoU and per-region scores vs the sheet, from tools/compare.py; shade share
per region at every angle):
```
IOU front 0.9423
REGION front skin      iou 0.7878  tol 0.9587  dE   6.2  shade ref 0.17 ren 0.21  ref #EFDBD1 ren #F5DDD4  px ref 42432 ren 39534
REGION front hair      iou 0.5385  tol 0.7773  dE  12.8  shade ref 0.53 ren 0.59  ref #C0CBC3 ren #C5CFC8  px ref 45963 ren 32307
REGION front dress     iou 0.8124  tol 0.9471  dE   6.8  shade ref 0.23 ren 0.20  ref #E8EEE1 ren #E7EDE0  px ref 105692 ren 117560
REGION front green     iou 0.4204  tol 0.8284  dE  16.5  shade ref 0.57 ren 0.30  ref #468753 ren #488054  px ref 14929 ren 15495
REGION front petticoat iou 0.6794  tol 0.8847  dE   9.0  shade ref 0.39 ren 0.48  ref #EDCFC8 ren #F1CFC9  px ref 15353 ren 15243
REGION front shoe      iou 0.4881  tol 0.8527  dE  11.4  shade ref 0.26 ren 0.42  ref #366E47 ren #377048  px ref 4995 ren 4905
IOU side  0.9220
REGION side  skin      iou 0.6035  tol 0.8213  dE   6.2  shade ref 0.19 ren 0.23  ref #EEDBD1 ren #F5DCD2  px ref 23453 ren 16194
REGION side  hair      iou 0.6918  tol 0.8691  dE  12.1  shade ref 0.37 ren 0.53  ref #CAD4CD ren #C8D2CC  px ref 47339 ren 48177
REGION side  dress     iou 0.7520  tol 0.9100  dE   8.4  shade ref 0.25 ren 0.32  ref #E5EADD ren #E1E8DB  px ref 54308 ren 54184
REGION side  green     iou 0.3742  tol 0.6984  dE  16.5  shade ref 0.70 ren 0.44  ref #488A56 ren #457E53  px ref 6460 ren 6474
REGION side  petticoat iou 0.6059  tol 0.8141  dE   9.1  shade ref 0.44 ren 0.58  ref #EDCDC5 ren #EECBC5  px ref 11895 ren 16628
REGION side  shoe      iou 0.6746  tol 0.9320  dE   8.3  shade ref 0.18 ren 0.24  ref #326E44 ren #306942  px ref 5146 ren 5019
IOU back  0.9444
REGION back  skin      iou 0.6919  tol 0.8740  dE   5.8  shade ref 0.18 ren 0.34  ref #EBD8CD ren #F3D9CF  px ref 29375 ren 24613
REGION back  hair      iou 0.7057  tol 0.8722  dE   9.6  shade ref 0.37 ren 0.17  ref #CAD5CE ren #D2DDD6  px ref 91547 ren 104109
REGION back  dress     iou 0.6754  tol 0.8614  dE   7.3  shade ref 0.30 ren 0.22  ref #E5ECDE ren #E5EBDE  px ref 78992 ren 68698
REGION back  green     iou 0.2985  tol 0.6112  dE  17.5  shade ref 0.59 ren 0.50  ref #458654 ren #418051  px ref 7465 ren 3979
REGION back  petticoat iou 0.6570  tol 0.8693  dE  10.0  shade ref 0.38 ren 0.49  ref #EFCFC8 ren #EFCEC8  px ref 14941 ren 15860
REGION back  shoe      iou 0.5278  tol 0.8708  dE  11.1  shade ref 0.32 ren 0.40  ref #356C45 ren #3B6D48  px ref 6098 ren 7814

# share of each region painted in its shade tone (cel render; sheet in brackets)
view                       skin            hair           dress           green       petticoat            shoe
front               0.21 [0.17]     0.59 [0.53]     0.20 [0.23]     0.29 [0.57]     0.48 [0.39]     0.45 [0.26]
side                0.23 [0.19]     0.53 [0.37]     0.32 [0.25]     0.48 [0.70]     0.58 [0.44]     0.27 [0.18]
back                0.34 [0.18]     0.17 [0.37]     0.22 [0.30]     0.55 [0.59]     0.49 [0.38]     0.46 [0.32]
q34_front_left             0.20            0.54            0.19            0.33            0.62            0.43
q34_back_right             0.25            0.23            0.28            0.59            0.65            0.30
high                       0.32            0.57            0.25            0.43            0.79            0.41
```

Parts (use exactly these names for "part"): accessories, bodice, body, hair_back, hair_front, head, petticoat, shoes, skirt, sleeves; plus "lookdev" (lighting, ramp, palette,
outlines, anything global to the shading), "rig" (bones, weights, deformation) and "global".

Return JSON matching the schema:
- summary: 3-6 sentences, overall state and the most important next steps.
- scores: 1-10 per category (10 = production-ready).
- findings: at most 25, most important first. priority 1 = clearly visible or breaks
  animation, fix this round; 2 = noticeable; 3 = polish. category is naturalness / animation /
  fidelity. view names the image tile (e.g. "q34_front_left", "clay high", "walk front").
  location is where on the model (be specific: "left sleeve cuff, inner side"). issue says what is
  wrong and why it matters. fix is a concrete, actionable change for the part's build code
  (shape, loop count, normals, weights, offsets in cm), not a generic suggestion.
Do not report things that are fine. Do not pad. Be specific and visual.
