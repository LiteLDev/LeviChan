# VMD round trip of the motion clips

Clips keyed on the Blender rig, retargeted by PMX bone name onto the mmd_tools import of the exported PMX (every frame), exported as VMD, re-imported and compared bone by bone (頭, 上半身2, 左手首, 右手首, 左ひじ, 右ひじ, 左ひざ, 右ひざ, 左足首, 右足首, 左つま先, 右つま先). MMD physics is not simulated: hair, skirt and sleeve chains are keyed bones here, rigid bodies in MMD.

Shoulder: the worst frame-to-frame acceleration of the rest elbow carried by 肩補助 / 肩補助2 / 肩補助3 / 腕D (mm / frame^2), on the Blender rig and in the PMX + VMD playback (a pop is a spike).

| clip | frames | keyed bones | VMD KB | round trip mm (where) | rig vs PMX+VMD mm (where) | least knee deg | shoulder accel rig (where) | shoulder accel PMX (where) |
|---|---|---|---|---|---|---|---|---|
| walk | 61 | 28 | 185 | 0.00 (左ひざ @ 29) | 1.8 (右ひざ @ 11) | 31.2 | 3.1 (左腕D @ 19) | 4.6 (左腕D @ 49) |
| idol_dance | 91 | 49 | 483 | 0.00 (左ひざ @ 71) | 8.0 (左ひざ @ 72) | 6.0 | 51.0 (左肩補助 @ 78) | 45.6 (左肩補助3 @ 79) |
| turn | 46 | 11 | 54 | 0.00 (左ひじ @ 30) | 2.4 (左ひざ @ 9) | 37.6 | 2.5 (右腕D @ 40) | 2.6 (右腕D @ 40) |

VMD ROUND TRIP OK
