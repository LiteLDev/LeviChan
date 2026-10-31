# r11/hair-front: the plate behind the neck, the pointed head, the ahoge

Owner's request (round 11): 脑袋尖尖的，得优化，你看看风堇建模头发怎么搞的，尤其是呆毛。另外后发内部好像有个盘子，是不是有问题
(the head is pointed; look at how 风堇 builds hair, especially the ahoge; there seems to be a plate inside the back hair).

Earlier passes on this lane (kept): the crown is a round dome (`CROWN_DOME`, `check_cap_round`: outline ratio 0.93,
3D ratio 0.43); the ahoge is two wave locks; the cap's floor under the occiput was lifted onto a closure (round 2-R1).

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
