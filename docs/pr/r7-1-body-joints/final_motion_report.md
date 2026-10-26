# Motion test report

Model: 49 meshes, 99422 vertices, 98002 faces (without outlines). Run time 646 s. Not gated: the exit code of rig_check covers the core poses only. No cloth or hair physics: chains move only as keyed or driven (MMD simulates them).

Thresholds (minor / major): stretch 1.60/2.00, compress 0.30/0.12, flip 10/100, pen 1.0/2.0, pen_frac 0.5%/3.0%, self 0.5/1.5, contact 3.0/6.0, cross 40/400, joint 0.85/0.70, vol 0.80/0.65, knee -0.5/-5.0, elbow -5.0/-15.0, pop 2.0/6.0, bone_pop 2.0/6.0, jitter 0.03/0.08, speed 12.00/20.00, eye 0.8/1.5.
Cells: plain = ok, *italic* = minor, **bold** = major (location, frame for clips). pen/self/contact in cm, pop in mm; joint = median skin radius ratio at the worst joint band, vol = its mean squared radius ratio; knee/elbow = least signed bend (negative = hyperextended).

## extended

| name | stretch | compress | flip | pen cm | pen % | self cm | contact cm | cross | joint | vol | knee | elbow |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| sit_chair | *1.73* (足補助.L) | *0.15* (ひざ補助.R) | *14* (ひざ補助.L) | **4.0** (スカート15_0) | **45.1%** (スカート0_0) | - | - | 8 | 0.96 | *0.76* (knee.R) | 85.6 | 69.2 |
| seiza | *1.70* (スカート11_2) | **0.12** (ひざ補助2.L) | *54* (ひざ補助.L) | **3.0** (スカート1_1) | **5.4%** (スカート1_1) | *0.9* (foot.L x thigh.L) | 2.2 | 0 | 0.97 | **0.65** (knee.L) | 156.4 | 65.0 |
| kneel_one | *1.70* (下半身) | *0.15* (ひざ補助.R) | *19* (ひざ補助.R) | **4.0** (スカート14_0) | **9.9%** (スカート15_0) | - | 0.3 | 23 | 0.95 | *0.68* (knee.R) | 83.9 | 35.4 |
| cross_legged | **2.38** (足補助.L) | *0.15* (足補助.L) | *51* (ひざ補助.L) | **3.8** (スカート2_0) | *1.3%* (スカート2_0) | - | - | 0 | 0.96 | *0.67* (knee.L) | 124.7 | 52.7 |
| deep_lunge | *1.66* (下半身) | *0.18* (ひざ補助.R) | 0 | **3.5** (スカート15_1) | **13.1%** (スカート15_1) | - | - | 22 | 0.96 | *0.79* (knee.R) | 55.8 | 52.7 |
| run_l | *1.79* (ひじ.L) | **0.10** (ひじ補助.L) | *16* (ひざ補助.L) | **2.9** (スカート15_2) | **3.5%** (スカート14_1) | - | - | **1161** (hair x garment) | 0.95 | *0.68* (knee.L) | 16.4 | 95.3 |
| run_r | **2.02** (スカート5_1) | **0.10** (ひじ補助.R) | *16* (ひざ補助.R) | **3.9** (スカート1_1) | **4.2%** (スカート1_1) | - | - | **1013** (hair x garment) | 0.95 | *0.68* (knee.R) | 16.4 | 95.3 |
| jump_tuck | *1.96* (スカート15_2) | *0.15* (ひざ補助.R) | *44* (ひざ補助.L) | **3.4** (スカート1_0) | **7.8%** (スカート1_0) | - | - | **5736** (hair x skirt) | *0.81* (shoulder.L) | *0.65* (knee.R) | 136.0 | 45.1 |
| high_kick | *1.79* (下半身) | *0.27* (足補助.L) | 1 | **3.7** (スカート14_0) | **16.8%** (横髪巻_1.R) | - | - | **1647** (hair x skirt) | 0.95 | 0.94 | 0.0 | 35.4 |
| arms_crossed | *1.77* (ひじ.L) | **0.11** (腕捩.R) | 6 | *1.1* (手捩.R) | *1.0%* (手捩.R) | **2.4** (forearm.L x forearm.R) | *4.0* (forearm.L x hand.R) | 0 | 0.97 | 0.99 | 0.0 | 109.2 |
| hands_behind_head | **2.12** (ひじ.R) | *0.12* (ひじ補助.L) | **114** (ひじ補助.L) | *1.0* (頭) | **5.0%** (横髪奥_1.L) | *1.0* (hand.L x hand.R) | *4.9* (forearm.R x hand.L) | **4215** (hair x garment) | *0.81* (shoulder.R) | **0.64** (shoulder.R) | 0.0 | 136.5 |
| hands_behind_back | *1.71* (ひじ.R) | **0.09** (ひじ補助.L) | 0 | *1.4* (手捩.R) | *2.5%* (手捩.R) | *1.2* (forearm.L x forearm.R) | - | **1230** (hair x garment) | *0.85* (shoulder.R) | *0.73* (shoulder.R) | 0.0 | 99.7 |
| hand_to_shoulder | *1.74* (ひじ.L) | *0.18* (ひじ補助.L) | *34* (ひじ補助.L) | *1.9* (横髪長_2.L) | **4.2%** (横髪長_2.L) | - | - | 38 | 0.96 | 0.94 | 0.0 | 32.9 |
| hands_on_hips | *1.64* (ひじ.R) | *0.19* (ひじ補助.L) | 0 | *1.6* (横髪巻_2.L) | **6.5%** (横髪巻_2.L) | - | - | 0 | 0.92 | 0.89 | 0.0 | 86.6 |
| reach_up_back | *1.85* (手捩.L) | 0.33 | 10 | *1.5* (頭) | **13.0%** (頭) | 0.4 | - | **4447** (hair x garment) | 0.92 | 0.82 | -0.0 | 32.9 |
| hug_self | *1.80* (肩補助2.L) | *0.17* (腕捩.L) | *11* (ひじ補助.L) | **2.5** (手捩.L) | **13.0%** (手捩.L) | **1.9** (hand.R x upperarm.L) | *4.4* (forearm.R x upperarm.L) | 21 | 0.97 | 1.00 | 0.0 | 110.9 |
| twist_bend | 1.33 | 0.63 | 0 | *1.6* (下半身) | *2.5%* (腕捩.L) | - | - | **696** (hair x skirt) | 0.98 | 0.92 | 23.5 | 29.7 |
| lie_back_elbows | *1.84* (ひじ.R) | **0.10** (ひじ補助.R) | *12* (ひじ補助.L) | **4.0** (スカート1_0) | **14.7%** (スカート1_0) | - | - | *352* (hair x skirt) | 0.98 | 0.96 | 8.0 | 99.7 |
| look_over_shoulder | 1.51 | 0.65 | 1 | *1.8* (後髪0_1) | *0.6%* (後髪0_1) | - | - | **1129** (hair x skirt) | 0.98 | 0.95 | 0.0 | 38.3 |
| curtsy | 1.42 | *0.27* (ひざ補助.L) | 0 | 0.2 | 0.0% | - | - | 20 | 0.96 | 0.82 | 56.6 | 39.6 |
| dance_sway | *1.85* (手捩.L) | *0.22* (ひじ補助.R) | 3 | *1.8* (横髪巻_1.L) | **14.3%** (横髪巻_2.R) | - | - | **1463** (hair x skirt) | *0.84* (shoulder.L) | *0.66* (shoulder.L) | 37.9 | 41.5 |
| dance_point | *1.84* (ひじ.L) | *0.14* (ひじ補助.L) | *31* (ひじ補助.L) | **2.3** (手捩.L) | **7.3%** (手捩.L) | - | - | **1770** (hair x skirt) | 0.87 | *0.76* (shoulder.R) | 38.4 | 32.9 |
| dance_heart | *1.77* (手捩.R) | *0.22* (ひじ補助.L) | 2 | *1.4* (横髪巻_1.R) | **6.6%** (頭) | **2.5** (hand.L x hand.R) | *4.2* (forearm.L x hand.R) | **3042** (hair x garment) | *0.85* (shoulder.L) | *0.73* (shoulder.R) | 32.6 | 108.3 |
| dance_clap | *1.71* (ひじ.R) | *0.14* (ひじ補助.R) | 0 | 0.7 | *0.6%* (手捩.R) | *0.9* (hand.L x hand.R) | *3.9* (forearm.L x hand.R) | **4120** (hair x skirt) | 0.90 | *0.80* (knee.R) | 71.0 | 108.3 |

## motion

| name | stretch | compress | flip | pen cm | pen % | self cm | contact cm | cross | joint | vol | knee | elbow | pop mm | bone pop mm | jitter | speed m/s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| walk | 1.43 | 0.33 | 0 | *1.1* (腕捩.R) | *1.8%* (腕捩.R) | - | - | **1184** (hair x skirt, f29) | 0.96 | 0.84 | 26.1 | 37.1 | **45.8** (スカート1_2, f21) | **40.9** (スカート1_2, f21) | **0.13** (スカート3_2, f21) | 1.22 |
| run | *1.96* (スカート12_2) | **0.10** (ひじ補助.R, f10) | *20* (ひざ補助.R) | *1.6* (後髪束14_2) | *2.9%* (足首.R) | - | - | **1072** (hair x garment, f0) | 0.95 | *0.67* (knee.R) | 25.2 | 95.3 | **78.9** (スカート13_1, f20) | **74.3** (ひざ補助.R, f20) | **0.34** (スカート11_2, f16) | 4.00 |
| turn | 1.28 | *0.28* (ひざ補助.L) | 0 | *1.1* (足首.R) | *1.0%* (足首.R) | **1.8** (foot.L x foot.R, f24) | - | **2361** (hair x skirt, f26) | 0.96 | 0.82 | 32.6 | 45.1 | **7.1** (足首.L, f30) | **6.8** (足首.L, f30) | *0.06* (スカート13_2) | 1.63 |
| sit_stand | **2.22** (スカート5_1, f65) | *0.15* (ひざ補助.L) | *18* (ひざ補助.L) | **4.1** (スカート0_0, f61) | **51.8%** (スカート0_0, f61) | - | - | 6 | 0.96 | *0.74* (knee.R) | 0.0 | 35.4 | **78.4** (スカート2_2, f65) | **66.6** (スカート2_2, f65) | **0.41** (スカート5_1, f65) | 2.05 |
| spin | **2.23** (スカート15_2, f19) | 0.49 | 0 | **2.5** (横髪巻_2.R, f1) | **20.2%** (横髪巻_2.R, f3) | - | - | **4045** (hair x skirt, f36) | 0.95 | 0.88 | 25.8 | 35.4 | *4.0* (足首.R) | 0.0 | 0.01 | 3.94 |
| idol_dance | **2.01** (上半身2, f78) | **0.07** (ひじ補助.L, f74) | *31* (ひじ補助.L) | **4.3** (手捩.L, f74) | **30.5%** (横髪巻_2.R, f14) | **4.7** (forearm.L x thigh.L, f74) | *4.9* (forearm.L x hand.R) | **4294** (hair x garment, f77) | **0.60** (shoulder.L, f79) | **0.46** (shoulder.L, f79) | 0.0 | 29.7 | **85.6** (ひじ.L, f80) | **209.2** (袖_1.L, f81) | **0.89** (ひじ.L, f80) | 6.69 |

## eyes (gaze at the limits x eye morphs)

| case | poke mm | where |
|---|---|---|
| gaze | 1.36 (minor) | head_eye_L gaze +10/+8 |
| gaze+まばたき | 0.00 (ok) | eyes  |
| gaze+まばたき=0.5 | 1.34 (minor) | head_eye_L gaze -10/+8 |
| gaze+ウィンク | 1.36 (minor) | head_eye_R gaze -10/+8 |
| gaze+ウィンク右 | 1.36 (minor) | head_eye_L gaze +10/+8 |
| gaze+笑い | 0.00 (ok) | eyes  |

## Top problems (grouped by metric, part and location)

| # | level | metric | part | location | worst | in |
|---|---|---|---|---|---|---|
| 1 | major | bone_pop | rig | 袖_1.L (bones) | 209.2 in idol_dance@81 | idol_dance@81 |
| 2 | major | pop | sleeves | ひじ.L (sleeve_ribbon) | 85.6 in idol_dance@80 | idol_dance@80 |
| 3 | major | pen_frac | bodice | スカート0_0 (bodice_ribbon_tails) | 51.8% in sit_stand@61 | sit_stand@61, sit_chair, jump_tuck |
| 4 | major | pop | petticoat | スカート13_1 (petticoat_core) | 78.9 in run@20 | run@20 |
| 5 | major | pop | petticoat | スカート2_2 (petticoat_tier1) | 78.4 in sit_stand@65 | sit_stand@65 |
| 6 | major | bone_pop | rig | ひざ補助.R (bones) | 74.3 in run@20 | run@20 |
| 7 | major | jitter | sleeves | ひじ.L (sleeve_balloon) | 0.89 in idol_dance@80 | idol_dance@80 |
| 8 | major | bone_pop | rig | スカート2_2 (bones) | 66.6 in sit_stand@65 | sit_stand@65 |
| 9 | major | cross | hair/skirt | hair x skirt (hair x skirt) | 5736 in jump_tuck | jump_tuck, reach_up_back, dance_clap, idol_dance@36, spin@36, hands_behind_head, turn@26, dance_point, high_kick, dance_sway, walk@29, look_over_shoulder, da... |
| 10 | major | cross | hair/garment | hair x garment (hair x garment) | 4447 in reach_up_back | reach_up_back, idol_dance@77, hands_behind_head, dance_heart, dance_sway, hands_behind_back, run_l, run@0, run_r, walk@0, lie_back_elbows, look_over_shoulder... |
| 11 | major | pen_frac | hair_front | 横髪巻_2.R (hair_curl_R) | 30.5% in idol_dance@14 | idol_dance@14, spin@3, dance_sway, hands_on_hips |
| 12 | major | pop | petticoat | スカート1_2 (petticoat_tier0) | 45.8 in walk@21 | walk@21 |
| 13 | major | bone_pop | rig | スカート1_2 (bones) | 40.9 in walk@21 | walk@21 |
| 14 | major | jitter | skirt | スカート5_1 (skirt) | 0.41 in sit_stand@65 | sit_stand@65 |
| 15 | major | pen_frac | hair_front | 横髪巻_2.L (hair_curl_L) | 17.4% in spin@0 | spin@0, hands_on_hips, high_kick |
| 16 | major | pen_frac | hair_front | 横髪巻_1.R (hair_curl_R) | 16.8% in high_kick | high_kick, dance_heart, jump_tuck |
| 17 | major | pen_frac | sleeves | 手捩.L (sleeve_cuff) | 16.2% in idol_dance@74 | idol_dance@74, hug_self, dance_point, lie_back_elbows, hand_to_shoulder |
| 18 | major | jitter | petticoat | スカート11_2 (petticoat_tier1) | 0.34 in run@16 | run@16 |
| 19 | major | pen_frac | bodice | スカート1_0 (bodice_ribbon_tails) | 14.7% in lie_back_elbows | lie_back_elbows |
| 20 | major | pen_frac | bodice | スカート15_1 (bodice_ribbon_tails) | 13.1% in deep_lunge | deep_lunge |
| 21 | major | pen_frac | accessories | 頭 (acc_leaves_L) | 13.0% in reach_up_back | reach_up_back, dance_heart, idol_dance@48 |
| 22 | major | pen_frac | hair_front | 横髪奥_1.R (hair_curtain_R) | 11.3% in dance_sway | dance_sway, idol_dance@11, reach_up_back, hands_behind_head, turn@5 |
| 23 | major | pen_frac | hair_front | 横髪巻_1.L (hair_curl_L) | 11.2% in idol_dance@53 | idol_dance@53, dance_sway, jump_tuck |
| 24 | major | pen_frac | hair_front | 横髪長_2.L (hair_lock_L) | 11.1% in hug_self | hug_self, hand_to_shoulder |
| 25 | major | self | body | body:forearm.L x thigh.L (body:forearm.L x thigh.L) | 4.7 in idol_dance@74 | idol_dance@74 |
| 26 | major | self | body | body:hand.L x thigh.L (body:hand.L x thigh.L) | 4.6 in idol_dance@74 | idol_dance@74 |
| 27 | major | pen_frac | hair_front | 横髪奥_1.L (hair_curtain_L) | 10.6% in idol_dance@80 | idol_dance@80, reach_up_back, hands_behind_head, dance_point, spin@6 |
| 28 | major | pen_frac | hair_front | 頭 (hair_cheek_L) | 10.3% in reach_up_back | reach_up_back, idol_dance@81, dance_sway, idol_dance@45, dance_heart, idol_dance@48, idol_dance@50 |
| 29 | major | pen_frac | bodice | スカート15_0 (bodice_ribbon_tails) | 9.9% in kneel_one | kneel_one, high_kick |
| 30 | major | pen_frac | petticoat | スカート14_1 (petticoat_core) | 8.9% in sit_stand@64 | sit_stand@64, run_l, idol_dance@72, deep_lunge |
| 31 | major | pen | sleeves | 手捩.L (sleeve_cuff) | 4.3 in idol_dance@74 | idol_dance@74, hug_self, dance_point, lie_back_elbows, hand_to_shoulder |
| 32 | major | pen | bodice | スカート0_0 (bodice_ribbon_tails) | 4.1 in sit_stand@61 | sit_stand@61, sit_chair, jump_tuck |
| 33 | major | pen | skirt | スカート14_0 (skirt) | 4.0 in kneel_one | kneel_one, high_kick |
| 34 | major | pen | skirt | スカート1_0 (skirt) | 4.0 in sit_stand@61 | sit_stand@61, lie_back_elbows |
| 35 | major | pen | bodice | スカート1_0 (bodice_ribbon_tails) | 4.0 in lie_back_elbows | lie_back_elbows |
| 36 | major | self | body | body:hand.L x upperarm.R (body:hand.L x upperarm.R) | 3.5 in idol_dance@30 | idol_dance@30 |
| 37 | major | pen | skirt | スカート15_0 (skirt) | 4.0 in sit_chair | sit_chair |
| 38 | major | pen_frac | petticoat | スカート1_0 (petticoat_core) | 7.8% in jump_tuck | jump_tuck |
| 39 | major | pen | petticoat | スカート1_1 (petticoat_core) | 3.9 in sit_stand@29 | sit_stand@29, run_r, seiza |
| 40 | major | pen | skirt | スカート2_0 (skirt) | 3.8 in cross_legged | cross_legged |

## Issues by part (major / minor rows)

| part | major | minor |
|---|---|---|
| hair_front | 40 | 33 |
| petticoat | 37 | 32 |
| body | 19 | 94 |
| sleeves | 19 | 73 |
| hair/skirt | 16 | 1 |
| skirt | 13 | 18 |
| bodice | 13 | 10 |
| hair/garment | 9 | 8 |
| accessories | 8 | 4 |
| rig | 5 | 0 |
| shoes | 2 | 8 |
| hair_back | 0 | 11 |
| head | 0 | 4 |
