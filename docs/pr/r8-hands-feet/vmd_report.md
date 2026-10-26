# VMD round trip of the motion clips

Clips keyed on the Blender rig, retargeted by PMX bone name onto the mmd_tools import of the exported PMX (every frame), exported as VMD, re-imported and compared bone by bone (頭, 上半身2, 左手首, 右手首, 左ひじ, 右ひじ, 左ひざ, 右ひざ, 左足首, 右足首, 左つま先, 右つま先). MMD physics is not simulated: hair, skirt and sleeve chains are keyed bones here, rigid bodies in MMD.

| clip | frames | keyed bones | VMD KB | round trip mm (where) | rig vs PMX+VMD mm (where) | least knee deg |
|---|---|---|---|---|---|---|
| walk | 61 | 28 | 185 | 0.00 (右ひざ @ 44) | 2.3 (右ひざ @ 11) | 28.8 |
| idol_dance | 91 | 49 | 483 | 0.01 (左ひざ @ 70) | 12.8 (左ひざ @ 72) | 7.1 |
| turn | 46 | 11 | 54 | 0.00 (右手首 @ 24) | 3.2 (左ひざ @ 9) | 35.1 |

VMD ROUND TRIP OK
