# r11/hair-front: the plate behind the neck, the pointed head, the ahoge

Owner's request (round 11): 脑袋尖尖的，得优化，你看看风堇建模头发怎么搞的，尤其是呆毛。另外后发内部好像有个盘子，是不是有问题
(the head is pointed; look at how 风堇 builds hair, especially the ahoge; there seems to be a plate inside the back hair).

Earlier passes on this lane (kept): the crown is a round dome (`CROWN_DOME`, `check_cap_round`: outline ratio 0.93,
3D ratio 0.43); the ahoge is two wave locks; the cap's floor under the occiput was lifted onto a closure (round 2-R1,
R2); round 4 runs hair_back's lining up into the cap behind it.

Images in this folder: the round-4 sheets (`r4_*.jpg`, below); the first round-11 pass's sheets (r10 / r11-first /
r11-final: `overview_base_first_final.jpg`, `bangs_d7_d8_tips_base_first_final.jpg`,
`cheek_wisp_temple_base_first_final.jpg`, `curl_d5_base_first_final.jpg`, `side_locks_motion_base_first_final.jpg`),
the round crown (`crown_4x_cel_clay.jpg`) and the ahoge against 风堇's crescent forelock (`ahoge_vs_hyacine.jpg`).
The intermediate rounds' sheets named below (R2, R3 and the earlier ahoge / plate passes) were pruned in round 4 to
keep the folder small; they are in the history at a7fd563 (R3) and 457e88c (R2).

## Round 4 (integration, fourth verifier pass)

Commits b0029b6 (code), 67c1839 (the ahoge's back lock) and afd31e3 (the lining's weighting height) on
r11/hair-front, on r11/integrate 8a45214.
`levi/parts/hair_front.py`, and `levi/parts/hair_back.py` for the lining's top only (no lock moved: every
hair_back and hair_back_side vertex is where it was, checked vertex by vertex).

### The nape: the lining runs up into the cap (verifier p2 nape in clay, p3 lining cavity, p3 geometry)

Diagnosis (sections at x 0 / 3 / 6 / 9 / 11 cm, cap and lining alone, ray-cast visibility in 1 mm cells): the
cavity behind the ears and the "collar" were one problem. hair_back's lining stopped at its top edge (rows 140 /
190, z 1.26 in the middle, 1.19 at |x| 10 cm), its inner face held 4-5 cm behind the neck there by CAP_PROFILE's
rows 135-178 (empty since the closure was lifted under the skull), so between the neck and the hair the only
surface was the cap's closure: a dark collar in clay from front-low, low and below, with a polygonal rim where it
met the lining, and 6 cm of open cavity under the cap at |x| 6-10 cm.

- hair_back (`UNDER_TOP` and what derives from it): the top edge rises to rows 118 / 128, inside the cap; at the
  top the lining's depth is held by unit head's skull (`LINING_SKULL_IN`; `head.skull_points / skull_mesh`, pure
  functions, as the closure reads them), not by CAP_PROFILE; over the top 90 px a soft minimum of the side
  distances and a blur keep its inner face within the grid limits (`LINING_TOP_*`). The locks still settle on the
  under-layer as it was (`UNDER_SETTLE_TOP`, `_under_layer(settle=True)`): settling on the new one moved the
  primaries by up to 34 mm. Its weighting points (`_weight_coords`, the outer-face twins the rig weights both
  faces at) are held under z 1.262 by a soft minimum (`WEIGHT_TOP`): the raised top lay above the lock chains'
  roots (z 1.279-1.287), where the rig's head fade jumps from 頭 0.7-0.85 to all of 頭 between neighbouring
  vertices (the first gate run: x7.7 tears in head_left / right, x5.1 in test, x2.8 in side_bend). The part
  above moves with the lining just under it, as R3's top edge did. hair_back 30,490 -> 31,820 faces (34,000).
- hair_front: the closure shades with hair_back's own volume normal (`nape_normal`), the one the lining's inner
  face shades with (R3: +Z), so the two read as one surface; `NAPE_LINING` re-measured, and `check_nape_lining`
  now also fails the build unless the closure lies 3 mm under the lining's top out to |x| 8.5 cm; the wall under
  the lining's top (now hidden between the lining's faces) rises at half the slope from a wider foot; the lower
  pole sits at the last ring's middle (the cast pole lay off it and its fan folded: twelve 180° edges).

| | R3 (8a45214) | R4 |
|---|---|---|
| lining top outside the cap at abs(x) 0 / 2 / 4 / 6 / 8 / 10 cm, mm (- = inside) | 1.4 / 3.2 / 8.1 / 21.8 / 48.1 / 81.6 | -0.4 / -0.5 / -0.8 / -1.3 / -2.5 / 3.1 |
| lining inner face behind the back of the neck at x 0, z 1.20 / 1.22 / 1.24 / 1.26, mm | 45 / 59 / 72 / 84 | 29 / 32 / 35 / 47 |
| visible cap below z 1.28, mm²: front / front-low / low | 805 / 4536 / 4494 | 458 / 1926 / 3546 |
| q34 front-left / -right low; side-low left / right | 1255 / 1275; 671 / 672 | 646 / 682; 281 / 317 |
| cap edges over 60°: all / folded (> 170°) / with a ray escaping past the other meshes | 90 / 12 / 27 | 76 / 0 / 1 |

In clay the area behind the neck is one even dark tone from the jaw to the shoulders in front-low, low and from
below (hair and head only), no collar and no rim; cel unchanged (shade tone). In geo (custom normals cleared)
the lining's pleated inner face fills most of it; the closure beside the jaw keeps some lumps (fewer and
smaller). 75 of the 76 creases lie inside the neck, the face or between the lining's faces; the one exposed is
at (0.0, -2.5, 126.4) cm behind the throat, 3 of 98 directions escaping.

### The side curtain lock (verifier p2)

With the lining filling the notch behind the neck from behind, the lock is a lock again (`SIDE_CURTAIN`,
`CURTAIN_*`): one width curve (0.8x near the root behind the ear, 1.15x by mid-length, `CURTAIN_WIDEN`) closing
in the side locks' ogive past u 0.62 (R3: a x1.4 widening meeting the u 0.85 taper in a corner, a kite point);
its broad side turns from 1.2 to 0.75 toward the front over rows 125-205 (R3: 1.2 -> 0.3 over 125-165); a
rounder section (aspect 2.4, R3 2.8) shading with the hanging locks' own-normal share (`LOCK_KEEP`; R3 the
cap's volume normal: a flat paper sheet in clay); the path runs back half as far as R3 below row 145 and 2 px
further forward behind the ear, off hair_back_side's front edge.

| | R3 | R4 |
|---|---|---|
| kernel twist (deg / ring), rings, faces a side | 6.7, 28, 341 | 2.2, 29, 353 |
| triangle pairs through hair_back_side, a side; through hair_back (right) | 63, 63; 41 | 16, 16; 0 |
| side view behind the neck, background mm² (y -4..12, z 1.14..1.34 cm) | 5951 | 5918 |
| posed, same window: head_left / head_right / look_over_shoulder | 6089 / 5173 / 4968 | 6019 / 5153 / 4943 |

Rest views (12 ortho views round the neck, 1 mm cells): background no higher than R3 in 9; side-low +121 mm² a
side, q34 back-left / right +11 / +7. id renders at 3x / 4x: the side and side-low views trade slivers (side:
422 mm² newly open along the back of the shoulder under the lock's tip, 477 newly covered behind it), all along
silhouettes; nothing opens behind the neck. With the head turned (head_left side view) the gap under the jaw
in front of the far shoulder stays as in R3: the throat seen in profile with the far side's hair behind it.

### The ahoge (verifier p3)

The back lock is at most 7 mm wide (R3 10.2 mm at col 274, wider than the front lock under it: an egg from high
and behind-high), within the front lock's outline from above, its root on the scalp and its end narrowing to
2.4 mm (R3 4.4 / 3.6). Side, front and q34 outlines unchanged (its top line is): points at side cols
256.5 / 270.2, rows 12.3 / 12.9 (R3 12.3 / 12.8), notch 17.1; 12.0 % of the area inside the cap (R3 12.6);
back lock turn / rho 3.7 / 0.23 (R3 3.6 / 0.29); hair_crown 2 islands, 100 % 頭; round dome check unchanged
(0.93 / 0.43). 580 -> 622 faces.

### Faces, IoU, gates and motion

hair_front 15,944 -> 15,986 / 16,000; hair_back 30,490 -> 31,820 / 34,000; total 164,116 -> 165,488 / 200,000.
IoU front / side / back 0.8922 / 0.8070 / 0.8954 -> 0.8921 / 0.8075 / 0.8953.

Gates on afd31e3 (r11/integrate 8a45214 fast-forwards to it, so the lane and the full merge are the same tree):
`tools/check.py` CHECK OK (62 meshes identical in a second process, every budget met); `build.py --rig` exit 0;
`tools/rig_check.py` (full, 17 core poses) RIG CHECK OK, every pose's stretch / pen as on 8a45214 (head_left /
right 1.40 / 1.41 on hair_back, pen 0.02 / 0.01 cm; swing 1.53, 8a45214 1.56); PMX names 66/66; eye poke 0.00 mm.
The first gate runs (b0029b6 and 67c1839, before `WEIGHT_TOP`) failed: the lining's raised top tore x7.7 / x7.2 in head_left /
right, x5.1 in test, x2.8 in side_bend (see the lining above).

Full motion report on the full merge (r11/integrate 8a45214 + afd31e3; `rig_check.py --quick --no-core --extended
--report-core --motion`), row by row against the integrate-before report (8a45214, same tool) and round 10:

| issues (minor / major) | r10 | 8a45214 | R4 merge |
|---|---|---|---|
| all | 479 (327/152) | 442 (313/129) | 441 (314/127) |
| hair_front | 41 (25/16) | 29 (18/11) | 27 (18/9) |
| hair_back | 14 (12/2) | 10 (9/1) | 11 (10/1) |
| crossings on hair (all sets) | 36 (22/14) | 15 (6/9) | 15 (6/9) |

- No new major; two majors down to minor (jump_tuck `hair_curl_L/R` pen_frac 3.19 -> 2.95 %); hands_behind_head's
  two curtain pen minors gone. Every non-hair issue identical (no value moved by 1 %).
- One new minor: reach_up_back `hair_back_shell` stretch x1.74 at 後髪束7_2 (z 1.09). The lock chains' collision
  probes keep the lining's inner face off her trunk, and the deeper lining (z 1.12-1.26) makes them push chains
  7 / 8 further back there (their posed bones differ; the lining's weights at that spot are the same). Keeping
  the old depth under the nape (a blend back to the legacy depth over rows 172-196) broke the grid limits
  (17° down a column) and was dropped.
- Existing issues that grew: idol_dance `hair_curl_L/R` pen_frac 5.65 / 5.45 -> 6.11 / 5.80 % and `hair_cheek_R`
  (with dance_heart) 3.09 -> 3.81 % (majors: the side locks nest over the rounder curtain lock: main / curl /
  cheek locks lifted 4.1 / 5.6 / 1.4-2.5 mm further out); arms_up / dance_sway hair x garment crossings 684 -> 789, 855 -> 1096 (majors: the cheek locks over
  the raised sleeves); reach_up_back curtain pen_frac 0.59 -> 2.01 % (minor). Fell: idol_dance@80 `hair_curtain_L`
  pen_frac 8.90 -> 8.31 % (major; the target was R2's 6.0 %, not met), reach_up_back cheek 1.45 -> 1.25 %.
- Report: `integ_scratch/hf7/data/motion_m3/` (report.md, motion_report.json), comparison `hf7/data/mcmp_r4_final.txt`.

### Images (round 4)

- `r4_nape.jpg`: front-low and low clay at 8x, from below (hair and head only) in clay, front-low geo at 8x;
  R3 top, R4 bottom.
- `r4_lining.jpg`: sections at x 0 / 6 / 9 cm (R3 | R4: cap orange, lining green, neck brown), and the cap, the
  lining, head and body alone from side-low, low back and q34 front-left low (R3: the cavity behind the ears).
- `r4_curtain.jpg`: head_left q34 front-right in cel and clay, look_over_shoulder in clay, the rest side view at
  6x; R3 top, R4 bottom.
- `r4_ahoge.jpg`: high, behind-high and q34 behind-high in clay and the top view in cel at 16x; R3 top, R4 bottom.

### Not done / not verified (round 4)

- 76 cap edges still turn over 60° (target ~10); all but one lie inside the neck, the face or the lining.
- Motion: the new reach_up_back lining minor and the curl / cheek / crossing growth above; idol_dance@80's curtain
  pen_frac stays a major (8.3 %, target 6.0 %).
- Side-view slivers: the side and side-low views trade 300-420 mm² of background along the back of the shoulder
  for as much covered behind it (above); not under the ~100 mm² sliver allowance view by view.
- The ahoge's front view keeps its small base jogs at 16x and q34 front-left its short inner stroke near the notch
  (`AHOGE_LINE_RISE` 0.8 -> 2.5 mm changed nothing visible); from behind-high the back lock still reads as a
  smaller lock lying on the front one, not one lock splitting.
- export_pmx / pmx_reimport / motion_vmd not run (mmd_tools is not installed on the cluster).

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

### Images (round 3; pruned in round 4, see a7fd563)

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

### Images (round 2; pruned in round 4, see 457e88c)

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
