# VMD round trip of the motion clips

Clips keyed on the Blender rig, retargeted by PMX bone name onto the mmd_tools import of the exported PMX (every frame), exported as VMD, re-imported and compared bone by bone (頭, 上半身2, 左手首, 右手首, 左ひじ, 右ひじ, 左ひざ, 右ひざ, 左足首, 右足首, 左つま先, 右つま先). MMD physics is not simulated: hair, skirt and sleeve chains are keyed bones here, rigid bodies in MMD.

Shoulder: the worst frame-to-frame acceleration of the rest elbow carried by 肩補助 / 肩補助2 / 肩補助3 / 腕D (mm / frame^2), on the Blender rig and in the PMX + VMD playback (a pop is a spike).

| clip | frames | keyed bones | VMD KB | round trip mm (where) | rig vs PMX+VMD mm (where) | least knee deg | shoulder accel rig (where) | shoulder accel PMX (where) |
|---|---|---|---|---|---|---|---|---|
| run | 41 | 146 | 648 | 0.01 (右ひざ @ 5) | 11.6 (右ひざ @ 6) | 37.5 | 22.1 (右腕D @ 8) | 24.7 (左腕D @ 18) |

VMD ROUND TRIP OK
