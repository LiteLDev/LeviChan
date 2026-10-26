# Combined check: this branch (with #59 merged) + #60 + #61 (scratch merge, not pushed)

- Build, check.py, core rig_check: OK (17 poses, max stretch 1.77).
- PMX export + pmx_reimport: OK; 199 append bones; VMD walk round trip 0.00 mm.
- Merging #61 conflicts with #59 in export_pmx.py: both use PMX collision group 5 (#59 SLEEVE_R_GROUP, #61 HEAD_GROUP). The scratch merge moved SLEEVE_R_GROUP to 7.

## Motion suite: major rows by part, main (re-run with the fixed tools) vs combined

| part | main | combined |
|---|---|---|
| body | 37 | 22 |
| hair_front | 36 | 22 |
| petticoat | 31 | 8 |
| bodice | 19 | 0 |
| sleeves | 18 | 9 |
| hair/skirt | 16 | 2 |
| skirt | 13 | 1 |
| accessories | 12 | 8 |
| hair/garment | 9 | 9 |
| rig | 5 | 5 |
| shoes | 2 | 1 |
| skirt/petticoat | 0 | 1 |
| hair_back | 0 | 4 |
| **total** | **198** | **92** |

| clip | metric | main | combined |
|---|---|---|---|
| idol_dance | bone_pop | 430.9 mm (肩補助2.L@80) | 108.5 mm (後髪束2_4@40) |
| idol_dance | pop | 107.4 mm (袖_1.L@81) | 123.0 mm (後髪束2_4@40) |
| run | bone_pop | 74.3 mm (ひざ補助.R@20) | 74.3 mm (ひざ補助.R@20) |
| run | pop | 78.9 mm (スカート13_1@20) | 72.5 mm (ひざ補助2.R@20) |
| sit_stand | bone_pop | 66.6 mm (スカート2_2@65) | 3.4 mm (スカート5_2@72) |
| sit_stand | pop | 78.4 mm (スカート2_2@65) | 3.3 mm (スカート5_2@72) |
| spin | bone_pop | 0.0 mm (上半身@3) | 78.0 mm (横髪巻_2.R@6) |
| spin | pop | 4.0 mm (足首.R@22) | 82.4 mm (横髪巻_2.R@6) |
| turn | bone_pop | 6.8 mm (足首.L@30) | 94.3 mm (後髪束2_4@20) |
| turn | pop | 7.1 mm (足首.L@30) | 111.3 mm (後髪束2_4@20) |
| walk | bone_pop | 40.9 mm (スカート1_2@21) | 8.4 mm (ひざ補助.R@11) |
| walk | pop | 45.8 mm (スカート1_2@21) | 8.3 mm (ひざ補助2.R@41) |

Shoulder: the 431 mm pop of 肩補助2.L at idol_dance@80 is gone (the worst arm bone pop in idol_dance is now 4.7 mm). Sleeve: 209 mm (袖_1.L@81, this branch alone) and 107 mm (sleeve vertex pop) are gone. #59 alone left 47 mm at 袖_0.L@81. The combination's worst sleeve bone moves 17.5 mm at 袖_1.R@86 with 腕.R at or below 95° and the counter ramp at 0, which is the arm's smooth return to rest, not a branch switch.

The worst pops in idol_dance, turn and spin are now #61's hair locks (後髪束2_4 and 横髪巻_2.R, 78-111 mm). The run pop at ひざ補助.R@20 (74 mm) comes from the clip's IK target path (足ＩＫ.R accelerates 85 mm/frame² there).
