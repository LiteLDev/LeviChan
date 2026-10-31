# r11/hair-front: the plate behind the neck, the pointed head, the ahoge

Owner's request (round 11): 脑袋尖尖的，得优化，你看看风堇建模头发怎么搞的，尤其是呆毛。另外后发内部好像有个盘子，是不是有问题
(the head is pointed; look at how 风堇 builds hair, especially the ahoge; there seems to be a plate inside the back hair).

Earlier passes on this lane (kept): the crown is a round dome (`CROWN_DOME`, `check_cap_round`: outline ratio 0.93,
3D ratio 0.43); the ahoge is two wave locks; the cap's floor under the occiput was lifted onto a closure (round 2-R1,
R2).

## Round 3 (integration, third verifier pass)

All in `levi/parts/hair_front.py` (commit 67eee09 on r11/hair-front). `CAP_PROFILE` / `CAP_EXP` unchanged; the
cap's geometry is unchanged from R2 (only its shading normals on the closure).

### The side notch behind the neck (verifier p2): the side curtain lock, not the cap

Diagnosis (side-view occupancy along x over y -4..12 cm, z 1.14..1.34, 0.5 mm cells; sections; object colours):
the see-through R2 opened in the side view (635 mm² that 89f6117 covered) lies between the side curtain lock
`hair_curtain_L/R` (its back rim at y -1.0 cm, x 10.9 cm) and hair_back's side locks (front rim y -0.7..+1.6 cm,
x 11-13 cm), at z 1.205-1.26, under the cap. 89f6117 hid it with its cap floor 3-9 cm in from there (hits at x
3.3-9.1 cm, median 6.9), the part of the floor that was the plate from the front: everything in front of the
lining at |x| 3-9 cm is visible from the front between the neck and the side locks (front-view depth table), so
no cap surface can come back there.

Tried and dropped: hanging the cap's outer band behind the ears down to 8 mm under the lining's top as a curtain
(z-only drop in each column of the sheet cap, inside 4-16 mm of its plan outline, hidden behind the side locks
from the front): the whorl grid's rings cross the curtain's lower edge and front edge obliquely (180° folds, 17
self-intersecting pairs, jagged lower rim in clay; `drop_attempt.diff` kept in the scratch dir). The cap also
cannot reach the lining's top beside the neck: the lining's top runs down to z 1.217 / 1.193 at |x| 8 / 10 cm and
lies 2 cm behind CAP_PROFILE's section there (at row 155.6 the superellipse reaches y 3.2 cm at |x| 6 cm, the
lining's top is at y 5.1 cm); the cap only shrinks inside CAP_PROFILE (hair_back's envelope).

Fix: the curtain lock, whose job is to fill the gap to the back hair, now does. Round 11 narrowed it from u 0.55
to a 2-2.5 cm lance behind the neck; below row ~140 it now turns its broad side out (`CURTAIN_FORWARD` 1.2 -> 0.3:
its width runs back along the head), widens x1.4 (`CURTAIN_WIDEN`, u 0.5-0.7), runs ~1.5 cm further back (side
cols +4..+9 at rows 145-202) and closes in a blade past u 0.85 (`CURTAIN_TIP`). Its front rim stays put (variants
that moved it opened a slit toward the neck). 0 extra faces (curtain 401 -> 341 faces a side).

| side view behind the neck (mm²) | 89f6117 | R2 | R3 |
|---|---|---|---|
| background in the window (y -4..12, z 1.14..1.34 cm) | 6387 | 7022 | 5910 |
| new vs 89f6117 / newly covered | | 635 / 0 | 15 / 492 |
| posed, new vs 89f6117: head_left, head_right, look_over_shoulder, forward_bend, arms_up, hands_behind_head, reach_up_back | | | 0, 0, 7, 0, 0, 0, 5 (newly covered 0-43) |

The 15 mm² left are a sliver at y 0.9-1.2 cm, z 1.205-1.21 (the top of the slot that 89f6117 also had below
1.203). Fifteen rest views (front, front-low, low, below, q34 front-left/right and their -25° views, q34
back-left/right, back, low back, both sides, side-low; 1.5 mm cells): no new hole; at most 155 mm² of
silhouette sliver along the far side locks' outer rims in the q34 views, against 250-304 mm² newly covered.
Side IoU 0.8068 (89f6117) / 0.8055 (R2) -> 0.8078; front 0.8920 and back 0.8953 unchanged.

Not changed, and why: shown alone, cap and lining still leave a cavity behind the ears (lining top outside the
cap at |x| 4 / 6 / 8 cm: 89f6117 7.7 / 15.7 / 30.5 mm, R2 and R3 8.1 / 21.8 / 48.1 mm; the verifier's 10 mm
target needs the cap to grow back past CAP_PROFILE or the lining's top to stay higher at the sides, hair_back's
`UNDER_TOP` side rows). In the full model nothing looks into it (tables above).

### The lit cap under the right jaw (verifier p3) and the wall foot (p3)

The closure's shading normal was the cap's: the volume normal (horizontal under the head, `volume_normal` clamps
z) plus VOL_KEEP of its own, so the low views' key light (from in front and below) lit the right side behind the
jaw with a polygonal terminator on the coarse quads, and left the left side in shade. It now turns to +Z
(`NAPE_UP` 1 on the closure, fading out over `NAPE_LINE` above it): the underside of the hair takes the shade tone
in every view that can see it (the high views cannot).

| visible cap below z 1.28 at 4x, mm², visible / lit | R2 | R3 |
|---|---|---|
| front / front-low / low | 691/73, 3485/234, 3440/852 | 686/0, 3487/0, 3512/0 |
| q34 front-left / -right; their -25° views; side-low | 228/0, 226/9; 1196/93, 1087/33; 783/0 | 212/0, 216/0; 983/0, 879/0; 544/0 |

The wall foot in front of the lining (89-91° between rings at |x| 2.5-3.2 cm, y 4.9-5 cm, z 1.253) is unchanged
in the geometry: `NAPE_WALL_ROUND` 0.02 / 0.03 only took it to 88 / 87°, and adding rings there costs faces the
budget does not have (hair_front 15,944 / 16,000). With the upward shading normal it no longer shows in cel or
clay (8x front-low and low); it shows in geo (custom normals cleared).

### The ahoge (verifier p3s)

- The front lock's root now starts at side col 276.5 (R2 281), 4.5 mm wide (R2 6), on the back lock's line (+0.35
  px, R2 +1.0): its flat root lies inside the back lock's footprint. R2's ran on behind the back lock and 0.9 mm
  to one side: the thin flange and lip in q34-high / side-high, the forked outline at the back end, and part of
  the square root end from above.
- The back lock's root narrows from 4.4 mm (R2 6 mm: the square end from above), and resting on the scalp behind
  col 276.5 it stands 0.5-0.9 px higher, so its point keeps its row; its end thins to a 0.9 mm blade (R2 1.4).
- The front lock's spine is fuller behind the crest (cols 264-260: 1.2 / 3.5 px, R2 1.0 / 3.3), so the underside
  reaches the scalp under the point (R2: a 0.29 mm see-through slit there at 16x, 36 px; now 0 px in both side
  views), and the crest turns less (rho 0.43, R2 0.46); the top's peak holds full height over cols 256-257.
- `check_nape_lining()`: the build fails if `NAPE_LINING` is more than 3 mm off hair_back's lining top, measured
  the same way on hair_back's pure `_under_layer()` (now 0.0 mm). Costs ~1.6 s.

| | R2 | R3 | sheet / limit |
|---|---|---|---|
| area inside the cap (verifier's 5-ray count): total / front / back | 12.3 / 12.6 / 11.4 % | 12.7 / 13.3 / 11.0 % | <= 25 % |
| vertices inside the cap | 21.4 % | 22.7 % | |
| side points (col / row): front, back; notch row | 256.5/12.25, 270.0/12.86; 17.11 | 256.3/12.24, 270.1/12.58; 17.05 | 257/11.5, 269/12.5; 16 |
| kernel turn / rho: front, back | 4.8/0.46, 4.7/0.26 | 5.7/0.43, 3.6/0.29 | <= 8 / 0.5 |
| side slit at 16x (px, both sides) | 36 / 40 | 0 / 0 | 0 |
| hair_crown islands, faces | 2, 1860 | 2, 1884 | |

hair_front 15,944 / 16,000 faces (R2 15,968); total 163,876 / 200,000. hair_crown: 2 islands, every vertex 100 % 頭.

### Gates and motion

- Lane (r11/hair-front 67eee09, on r11/integrate 89f6117): `tools/check.py` CHECK OK (62 meshes identical in a
  second process); `build.py --rig` exit 0; `tools/rig_check.py` (full, 17 core poses) RIG CHECK OK
  (head_left / head_right worst pen 0.02 / 0.01 cm on hair_back, acc_choker 0.0; PMX names 66/66; eye poke 0.00 mm).
- Full merge (r11/integrate f5004c9 + 67eee09, a conflict-free merge): `tools/rig_check.py` (full) RIG CHECK OK
  with the same numbers; full motion report against a clean f5004c9 run (and round 10, motion15 78bca50, the
  verifier's clean 89f6117 and R2 runs):

| issues (minor / major) | r10 | 78bca50 | 89f6117 | R2 | f5004c9 | R3 merge |
|---|---|---|---|---|---|---|
| all | 479 (327/152) | 487 (348/139) | 484 (346/138) | 469 (332/137) | 471 (335/136) | 455 (320/135) |
| hair_front | 41 (25/16) | 33 (22/11) | 33 (22/11) | 30 (19/11) | 33 (22/11) | 29 (18/11) |
| hair x garment | 24 (13/11) | 24 (15/9) | 24 (15/9) | 12 (4/8) | 24 (15/9) | 12 (4/8) |

  Against f5004c9: no new issue, no new major, no minor turned major; every non-hair issue identical; run_r
  crossings major -> minor; 12 hair x garment crossing minors, 3 hair_cap pen minors and dance_point's curtain
  minor gone (all four hair x garment changes and the cap's were already in R2). One existing major grew:
  `hair_curtain_L` pen_frac in idol_dance@80 (the raised upper arm beside the head) 6.0 -> 8.9 % of the lock
  (its depth 1.56 -> 1.69 cm, minor); reach_up_back's curtain minors fell 1.5 -> 0.6 %.
  hair_cap pen in idol_dance 1.17 -> 1.36 mm (minor, as R2).

### Images (round 3)

- `r3_side_notch_89f6117_r2_r3.jpg`: side and q34 back-left at 3x, cel: 89f6117's pouch, R2's notch, R3.
- `r3_low_lit_cap_r2_r3.jpg`: low (-40°) and front-low (-20°) at 8x under the right jaw, cel and clay, R2 vs R3.
- `r3_ahoge_16x_r2_r3.jpg`: q34-high clay and cel, top cel, and the side slit (red) at 16x, R2 vs R3.

### Not done / not verified (round 3)

- Cap and lining alone still leave a cavity behind the ears (numbers above); not visible in the full model from
  any of the 15 rest views or the 7 posed side views checked, but the verifier's 10 mm target is not met.
- The wall foot in front of the lining keeps its 87-91° ring turn in geo views (invisible in cel and clay now).
- The ahoge front view keeps its small base jogs on both flanks at 16x, and q34 front-left / q34-high keep one
  short inner stroke near the notch (the front lock's hull where the back lock's rim rests on it).
- export_pmx / pmx_reimport / motion_vmd were not run (mmd_tools is not installed on the cluster).

## Round 2 (integration, second verifier pass)

All in `levi/parts/hair_front.py`. `CAP_PROFILE` / `CAP_EXP` (what hair_back reads) are unchanged.

### The plate (nape closure, `NAPE_*`, `nape_bounds`, `_low_layout`)

R1 left a pouch of cap under each ear (a flat floor at z 1.266 with the side walls' feet down to 1.23: a box
with a polygonal lower edge and a rim line), its closure crumpled by 14 rings spaced by polar angle. Now:

- The closure is the smooth minimum of four bounds, each keeping something covered: the **skull** (4 mm under the
  underside of unit head's skull behind the jaw, from `head.skull_points` / `skull_mesh`, the pure surface
  functions head_face keeps there, down to the nape hairline where it goes into the neck); the **ears** (under
  `head.ear_mesh`'s lowest point, over its plan grown out to the side walls); a **wall** in front of hair_back's
  lining top (measured table `NAPE_LINING`: the closure passes 8 mm under the top and rises at dz/dy 3.2, so the
  lining's inner face runs on up into the cap); a **ceiling** inside the face.
- The rings below the crown are laid out along each spoke by weighted arc length, split at the foot of the wall
  and smoothed round the spokes (`_low_layout`), 19 of them (R1: 14 by polar angle), 76 spokes (R1: 83).
- No outline on the closure (`line_min` 0 for the cap); the cap's own shading normals (own normals there printed
  lit islands beside the neck in the front-low and low cel views).

Numbers (full model; before = the R1 fix 1d6384f merged with r11/integrate 9f30883):

| | R1 | R2 |
|---|---|---|
| visible cap below z 1.28, mm² (4x): front / front-low (-20°) / low (-40°) | 3486 / 6883 / 5259 | 691 / 3485 / 3440 |
| q34 front-left / -right; q34-low left / right; side-low (-25°); side | 664 / 682; 1832 / 1820; 2099; 23 | 228 / 226; 1196 / 1087; 783; 0 |
| head skin behind the jaw above the nape hairline outside the cap (verts) | 55 | 0 |
| ears inside the cap | 682 / 682 each | 682 / 682 each |
| cap boundary / non-manifold edges, self-intersecting pairs | 0 / 0, 0 | 0 / 0, 0 |
| cap edges over 60°: exposed / at a contact line (neck, lining) / inside the skull | 34 / 2 / 8 | 32 / 16 / 64 |
| lining top outside the cap, mm, at abs(x) 0 / 2 / 4 / 6 / 8 cm | 1.6 / 3.2 / 7.6 / 14.9 / 30.6 | 1.4 / 3.2 / 8.1 / 21.8 / 48.1 |

What is left there from front-low and low is the underside of the hair round the ears and the wall above the
lining, in the cap's shade tone with no rim (cel), a soft dark shelf in clay. The lining's top lies under the
cap in the middle; beyond 5 cm out it lies 2-5 cm under the sheet cap's lowest point (the lift only raises the
sheet cap) behind the side locks, 3-17 mm further from the cap than in R1.

### The ahoge (`AHOGE_LOCKS`, `_conform`, `AHOGE_*`)

- One shared root: the front lock starts at the back lock's root (side col 281) and runs low on the scalp under
  it before rising to its point; the back lock rides on it and keeps to the midline (from the front it hides
  behind the front point). From above: one outline, widest at the root, the back lock's end an inner line on it.
- `_conform`: no ring vertex under the scalp before the root and the sunk end are pressed in (the fitted underside
  dipped 0.1-0.5 mm under it where the lock lies down); the sunk end goes under only near its end
  (`AHOGE_SINK_UNDER`); its outline starts 0.2 mm over the scalp (`AHOGE_LINE_RISE`). The build fails above 25 %
  of the area inside the cap (`AHOGE_MAX_BURIED_AREA`, counted honestly: triangle centres, ray parity).
- Shading normals keep 0.45 of their own (R1 0.6): no enclosed lit patch from behind-high.

| | R1 | R2 | sheet |
|---|---|---|---|
| area inside the cap (verifier's 5-ray count): total / front / back | 27.7 / 26.7 / 29.9 % | 12.3 / 12.6 / 11.4 % | <= 25 % |
| vertices inside the cap | 34.9 % | 21.4 % | |
| side points (col / row): front, back; notch row | 256.4/12.26, 269.9/13.51; 17.98 | 256.5/12.25, 270.0/12.86; 17.11 | 257/11.5, 269/12.5; 16 |
| kernel turn / rho (front, back) | 5.1/0.44, 4.2/0.28 | 4.8/0.46, 4.7/0.26 | <= 8 / 0.5 |
| enclosed lit patches (16x cel, 10 views) | behind-high 1, q34 back-left 1 | q34 back-left 3 (lit faces closed by the thin shade band at their base) | |

hair_front 15,968 / 16,000 faces.

### Gates and motion

- Lane (r11/hair-front, with r11/integrate 89f6117 merged): `tools/check.py` CHECK OK (62 meshes identical in a
  second process; total 163,900 / 200,000); `build.py --rig` exit 0; `tools/rig_check.py` RIG CHECK OK (17 core
  poses; head_left / head_right worst pen 0.02 / 0.01 cm on acc_choker; PMX names 66/66; eye poke 0.00 mm).
- Full motion report on r11/integrate 89f6117 + this branch, against a clean 89f6117 run (and round 10 / 78bca50):
  all issues 479 / 487 / 484 -> 469; majors 152 / 139 / 138 -> 137; hair_front 33 (22 minor, 11 major) -> 30
  (19, 11); hair x garment 24 (15, 9) -> 12 (4, 8); every other part identical. No new issue; one major down
  to minor (run_r crossings); hands_behind_head hair x garment crossings 7349 -> 7845 (already major);
  hair_cap pen in idol_dance 1.2 -> 1.4 mm (minor).
- Posed (head_left / right, look_over_shoulder, forward_bend, arms_up, hands_behind_head; 4x cel + id in seven
  views round the neck): no plate, hole or open edge; against R1 the only pixels that turned to background are the
  gap behind the neck under the jaw in the side view with the head turned (~1900 px at 4x), where R1's pouch hung.

### Images

- `r2_plate_8x_r1_r2.jpg`: front, front-low, low, q34 front-left low at 8x, cel and clay, R1 vs R2 (left of the neck).
- `r2_plate_capz_capwire_r1_r2.jpg`: the cap below z 1.28 in magenta (4x id) in five views; the cap, lining and
  head alone in wire from front-low, low and q34 back-left low.
- `r2_ahoge_16x_r1_r2.jpg`: top, high, front, behind-high, q34 back-left, side at 16x, cel and clay.

### Not done / not verified

- The front outline of the ahoge still has a small step on the right flank at its base at 16x (where the lying
  part's rim meets the scalp), and from above in clay the back lock's rounded end still shows on the front lock.
- Seen from below (-40° and lower) the shelf under the ears is still cap; it cannot rise past the ear lobes
  (z 1.279) without exposing them.
- export_pmx / pmx_reimport / motion_vmd were not run (mmd_tools is not installed on the cluster).
