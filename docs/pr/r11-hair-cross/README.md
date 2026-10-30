## r11 hair × garment crossings (hair-cross lane)

The integration review counted more hair × garment crossings in the arm-near-head poses than round 10. This lane measured where they are and fixed the part the hair rig can fix: the back locks beside the arms now lie over a swinging arm instead of passing through the sleeve. The rest is the forearms, hands and cuffs inside the head-rigid hair, where the poses put them; no hair-side change can clear that.

### A density-normalised measure (tools/motion_check.py)
`cross` counts new crossing triangle pairs. That count grows with mesh density: round 11's sleeves have 18k faces and hair_back has 30k. Each cross row now also carries:
- `mm`: the length of the new intersection curve, summed over the crossing pairs. Each pair's segment comes from an edge-against-triangle test both ways.
- `top`: the three object pairs with the most curve.

The report gains a "cross mm" column, which is not gated; for a clip it gives the longest frame. The count is unchanged: run on round 10's `main` with only this column added, the counts match the round-10 report exactly.

On this measure, the merge before this lane (r11/integrate 78bca50) was already 34% below round 10 over all poses (29.2 m against 44.0 m). Most of the brief's "regressions" in pair counts come from the denser meshes. The real increases are two:
- dance_heart, +0.9 m: the new under-tier of the cuff;
- jump_tuck, hair × garment, +0.12 m.

Hair crossings in the full motion report (new crossing triangle pairs / intersection curve, mm):
- **r10**: round 10's `main`, ab69d8b, with the column added.
- **before**: r11/integrate 78bca50.
- **after**: 78bca50 with this branch (721b46c) merged in.

For a clip, the count is taken at its worst-count frame and the curve at its longest frame.

| pose | r10 | before | after |
|---|---|---|---|
| hands_behind_head | 5978 / 6995 | 7350 / 6900 | 7350 / 6900 |
| dance_heart (= idol_dance@48) | 3678 / 4340 | 6037 / 5231 | 6037 / 5231 |
| reach_up_back | 4231 / 6424 | 4704 / 4796 | 4704 / 4796 |
| idol_dance clip (@48 count, @77 curve) | 4573 / 7366 | 6037 / 5261 | 6037 / 5261 |
| jump_tuck, hair × garment | 112 / 122 | 312 / 239 | 312 / 239 |
| jump_tuck, hair × skirt | 1720 / 1172 | 198 / 138 | 198 / 138 |
| spin clip, hair × skirt | 1352 / 1723 | 1044 / 1307 | 1044 / 1307 |
| walk (core) | 1201 / 2397 | 1012 / 1381 | **324 / 481** |
| run_l | 1069 / 1981 | 325 / 398 | **239 / 251** |
| run_r | 876 / 1576 | 406 / 588 | **164 / 174** |
| run clip (@18) | 1184 / 2315 | 534 / 699 | **284 / 343** |
| all hair rows (sum) | 32566 / 44031 | 31335 / 29183 | **30069 / 27366** |

Whole report:
- Issues: 487 before and after.
- Majors: 139 → 136. The three that leave are the hair × garment crossings in walk, run_r and the run clip, which drop from major to minor.
- Hair issues: 71 → 71, with majors 22 → 19.
- Every other row differs only at float noise (rest-pose hair differs by 0.4 µm).
- No hair pop, jitter, flip, stretch or penetration changed.
- The spin pop on 後髪束8_4@40 (15.7 mm) and the spin jitter on the lining (0.032) are as before.

### Diagnosis (per object pair, `crossdiag`)
**Arm-on-head poses: the arms lie in hair that rides the head.** In hands_behind_head, dance_heart, reach_up_back and idol_dance@48/@80, 95-99% of the crossing curve is on hair that rides the head rigidly (頭), in both rounds:
- the cap;
- the bangs and crown;
- the back hair above the choker;
- the roots of the side locks.

- hands_behind_head: the hands lie inside the hair cap's closed surface by 72 mm (p90) in both rounds. That is through the hair and into the skull.
- dance_heart: the cuffs lie about 50 mm (p90) inside it.
- reach_up_back: the hands are clear. The upper sleeves and their frills lie in the nape hair behind the head, which rides 頭.

With the hair hidden, the cuffs sit on the scalp (02). Round 11's two-tier cuff adds the `sleeve_cuff_under` surface. In dance_heart that surface carries 2.0 m of curve while the upper cuff's falls by 0.5 m, a net +0.9 m.

I tried pose variants (not committed; tools/motion_poses.py is outside this lane):
- hands_behind_head: with the hands moved out to the back of the hair (hand vertices inside the cap, p90 14-26 mm), 4.4-5.1 m of crossing remains (from 6.9 m). The forearms wrap through the side hair on their way round the head.
- dance_heart: with the hands raised (elbow 90-95°), 3.8-4.5 m remains (from 5.2 m).

The chains' collision cannot reach this hair, because it does not move.

**Arm swings: the back locks went through the sleeve.** This happened in walk, run, hands_behind_back and idol_dance@72-77. The back locks met only the trunk and the skirt; the arms reached them "only by sweeping through". In walk and run, the locks beside the arms (lock_angle 45-63°) were cut by the sleeve's bag from the side (01, before). In hands_behind_back and idol_dance@77, the forearm folded behind her back passes through the central locks and the lining.

### Fix (rig.py, hair collision section)
- `HAIR_COLLIDE_BACK_ARMS`: back-hair lock probes below `HAIR_COLLIDE_BACK_TOP` (shoulder - 8 cm) test the upper arm and forearm. Each test uses a capsule of its own, as fat as the sleeve's bag (`HAIR_COLLIDE_BACK_Q` 85th percentile: r 5.1 / 6.3 cm, against the side locks' 4.3 / 5.2 cm).
- `HAIR_COLLIDE_BACK_MIN_ANGLE` 40°: only the locks beside the arms are tested. These are the locks hair_back's lining does not ride.
  - A first version pushed every lock, including the primaries. An arm folded behind her back swept across them: in idol_dance@74-78 the central lock was dragged 19 cm sideways and snapped back in one frame (a 376 mm pop), which tore the lining ×3.1 and flipped 201 of its faces.
  - The primaries are left as before.
- `HAIR_COLLIDE_BACK_SIDE` / `_ROOM`: where the arm lies close behind her, the push goes outward only. The gate reads the arm's position against the trunk's axis from above, as a simple driver expression (no Python). A lock between the arm and her back stays put, instead of being pushed into the bodice.
- The rest is unchanged:
  - the capsule fade, the push cap (8 cm) and the turn cap (20° per stage);
  - which locks meet which colliders, apart from the new tests above;
  - the rest pose: a probe inside a capsule at rest keeps its rest distance.
- `strip_blender_only` removes the new probes and projectors like the old ones: they are the same bone kinds, flagged `levi_blender_only`.

### Gates (this branch, 721b46c)
- check.py: CHECK OK. hair_back 30,490 / 34,000, hair_front 14,629 / 16,000, total 162,561 / 200,000.
- rig_check.py, full run with the repeatability checks: RIG CHECK OK.
  - 66/66 standard PMX bone names; no backward knee.
  - Hair worst: head_left / head_right 1.40 / 1.41; swing 1.56 (hair_back_shell).
- Full-merge motion report: the table above.

### Images
- `01_side_locks_over_swung_arm.jpg`: walk (q34 back-left, cel and object colours; back), run_r (q34 back-right) and run@18 (q34 back-left cel; back clay), before and after. The side lock now lies over the bag instead of cutting through it.
- `02_head_poses_cuffs_on_scalp.jpg`: hands_behind_head (back cel; side in object colours; side and top with the hair hidden), dance_heart (front cel; top; front with the hair hidden) and reach_up_back (back, object colours). These are unchanged: cuffs and hands lie on the scalp, inside the head-rigid hair.

### Not done / open
- Head-rigid crossings in the arm-on-head poses (above). They need a pose decision. MMD models usually accept hands in the hair there.
- idol_dance@77 and hands_behind_back: the forearm folded behind her back still passes through the central locks and the lining. That is 5.3 m of curve at @77, still below round 10's 7.4 m. A push there drags the locks across and lets them snap back (the first version, above).
- jump_tuck: the long side lock (横髪長_1) crosses the sleeve frill, 119 mm per side (round 10: 61). Above `HAIR_COLLIDE_ARM_Z`, the side locks other than the cheek wisps do not meet the upper arm (the round-8 330 mm pop history). This is left as is.
- The lifted side lock is stiff. It rises over the bag as a whole (run@18: about 45° out) instead of draping back down beyond the arm.
- The spin pop on lock 後髪束8_4@40 (15.7 mm) is unchanged. The skirt's push sits at the turn cap during the spin, and the lock drops as soon as the push falls below the cap. That is a velocity step at the clamp, not a flip.
- export_pmx, pmx_reimport and motion_vmd were not run (no mmd_tools). The Codex review was not run.
