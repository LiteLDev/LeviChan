# VMD round trip of the motion clips

Clips keyed on the Blender rig, retargeted by PMX bone name onto the mmd_tools import of the exported PMX (every frame), exported as VMD, re-imported and compared bone by bone (頭, 上半身2, 左手首, 右手首, 左ひじ, 右ひじ, 左ひざ, 右ひざ, 左足首, 右足首, 左つま先, 右つま先). MMD physics is not simulated: hair, skirt and sleeve chains are keyed bones here, rigid bodies in MMD.

| clip | frames | keyed bones | VMD KB | round trip mm (where) | rig vs PMX+VMD mm (where) | least knee deg |
|---|---|---|---|---|---|---|
| walk | 61 | 28 | 185 | 0.00 (左ひざ @ 29) | 1.8 (右ひざ @ 11) | 31.2 |
| run | 41 | 146 | 648 | 0.00 (左ひざ @ 39) | 7.7 (左ひざ @ 18) | 30.3 |
| turn | 46 | 11 | 54 | 0.00 (右手首 @ 34) | 7.0 (左ひざ @ 30) | 27.2 |
| sit_stand | 91 | 12 | 118 | 0.01 (左ひざ @ 67) | 6.3 (左ひざ @ 36) | 6.0 |
| spin | 46 | 113 | 563 | 0.00 (右手首 @ 2) | 3.2 (右ひざ @ 24) | 30.9 |
| idol_dance | 91 | 49 | 483 | 0.00 (左ひざ @ 71) | 8.0 (左ひざ @ 72) | 6.0 |

VMD ROUND TRIP OK
