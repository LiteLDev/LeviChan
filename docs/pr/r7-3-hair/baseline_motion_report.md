# Motion test report

Model: 49 meshes, 99422 vertices, 98002 faces (without outlines). Run time 910 s. Not gated: the exit code of rig_check covers the core poses only. No cloth or hair physics: chains move only as keyed or driven (MMD simulates them).

Thresholds (minor / major): stretch 1.60/2.00, compress 0.30/0.12, flip 10/100, pen 1.0/2.0, pen_frac 0.5%/3.0%, self 0.5/1.5, contact 3.0/6.0, cross 40/400, joint 0.85/0.70, vol 0.80/0.65, knee -0.5/-5.0, elbow -5.0/-15.0, pop 2.0/6.0, bone_pop 2.0/6.0, jitter 0.03/0.08, speed 12.00/20.00, eye 0.8/1.5.
Cells: plain = ok, *italic* = minor, **bold** = major (location, frame for clips). pen/self/contact in cm, pop in mm; joint = median skin radius ratio at the worst joint band, vol = its mean squared radius ratio; knee/elbow = least signed bend (negative = hyperextended).

## extended

| name | stretch | compress | flip | pen cm | pen % | self cm | contact cm | cross | joint | vol | knee | elbow |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| sit_chair | *1.90* (足.L) | *0.15* (ひざ補助.R) | *42* (ひざ補助.L) | **4.0** (スカート15_0) | **49.5%** (スカート15_0) | - | 1.6 | 19 | 0.94 | *0.76* (hip.R) | 85.6 | 69.2 |
| seiza | *1.97* (ひざ補助.R) | **0.12** (ひざ補助.R) | **160** (ひざ補助.L) | **3.3** (スカート1_1) | **6.4%** (スカート1_1) | *0.6* (foot.L x thigh.L) | *3.3* (shin.L x thigh.L) | 0 | 0.95 | **0.61** (knee.L) | 156.4 | 65.0 |
| kneel_one | *1.92* (足.L) | *0.15* (ひざ補助.L) | *51* (ひざ補助.R) | **4.0** (スカート14_0) | **9.9%** (スカート15_0) | - | *4.7* (pelvis x thigh.R) | 23 | 0.94 | *0.65* (knee.R) | 83.9 | 35.4 |
| cross_legged | **2.75** (足.R) | **0.10** (足.R) | **126** (下半身) | **3.9** (スカート2_0) | *1.5%* (スカート2_0) | - | *5.1* (pelvis x thigh.L) | 0 | *0.76* (hip.L) | **0.48** (hip.L) | 124.7 | 52.7 |
| deep_lunge | **2.03** (足.L) | *0.15* (ひざ補助.L) | *22* (ひざ補助.R) | **3.5** (スカート15_1) | **16.1%** (スカート15_1) | - | *4.5* (pelvis x thigh.R) | 22 | 0.94 | *0.79* (hip.L) | 55.8 | 52.7 |
| run_l | *1.91* (足.L) | **0.10** (ひじ補助.L) | *35* (ひざ補助.L) | **2.8** (スカート14_1) | **3.5%** (スカート14_1) | - | *4.5* (pelvis x thigh.R) | **1183** (hair x garment) | 0.95 | *0.66* (knee.L) | 16.4 | 95.3 |
| run_r | **2.02** (スカート5_1) | **0.10** (ひじ補助.R) | *35* (ひざ補助.R) | **3.8** (スカート1_1) | **4.2%** (スカート1_1) | - | *4.1* (pelvis x thigh.L) | **1035** (hair x garment) | 0.95 | *0.66* (knee.R) | 16.4 | 95.3 |
| jump_tuck | *1.96* (スカート15_2) | *0.15* (ひざ補助.R) | **120** (ひざ補助.L) | **3.8** (スカート14_0) | **7.3%** (スカート14_0) | - | 3.0 | **5734** (hair x skirt) | *0.84* (shoulder.R) | **0.61** (knee.R) | 136.0 | 45.1 |
| high_kick | **2.07** (足.L) | *0.26* (下半身) | 0 | **3.8** (下半身) | **15.6%** (横髪巻_1.R) | - | *4.7* (pelvis x thigh.R) | **1647** (hair x skirt) | 0.92 | *0.70* (hip.L) | 0.0 | 35.4 |
| arms_crossed | *1.77* (ひじ.L) | **0.11** (腕捩.R) | 6 | *1.1* (手捩.R) | *1.0%* (手捩.R) | **2.4** (forearm.L x forearm.R) | *4.0* (forearm.L x hand.R) | 0 | 0.96 | 0.96 | 0.0 | 109.2 |
| hands_behind_head | **2.12** (ひじ.R) | *0.12* (ひじ補助.L) | **114** (ひじ補助.L) | *1.2* (上半身2) | **12.9%** (上半身2) | *0.9* (hand.L x hand.R) | - | **4991** (hair x garment) | *0.74* (shoulder.R) | **0.57** (shoulder.L) | 0.0 | 136.5 |
| hands_behind_back | **2.22** (上半身2) | **0.09** (ひじ補助.L) | 2 | *1.4* (手捩.L) | *2.5%* (手捩.L) | *1.2* (forearm.L x forearm.R) | - | **1165** (hair x garment) | *0.81* (shoulder.R) | *0.69* (shoulder.R) | 0.0 | 99.7 |
| hand_to_shoulder | *1.87* (上半身2) | *0.18* (ひじ補助.L) | *34* (ひじ補助.L) | **2.0** (横髪長_2.L) | **4.2%** (横髪長_2.L) | - | - | *60* (hair x garment) | 0.96 | 0.94 | 0.0 | 32.9 |
| hands_on_hips | *1.72* (上半身2) | *0.19* (ひじ補助.R) | 0 | *1.6* (横髪巻_2.L) | **6.5%** (横髪巻_2.L) | - | - | 0 | 0.89 | 0.85 | 0.0 | 86.6 |
| reach_up_back | *1.85* (手捩.R) | 0.33 | *18* (上半身2) | *1.7* (頭) | **12.2%** (頭) | 0.4 | - | **4331** (hair x skirt) | 0.92 | 0.80 | -0.0 | 32.9 |
| hug_self | **2.11** (上半身2) | *0.17* (腕捩.L) | *11* (ひじ補助.L) | **2.5** (手捩.L) | **12.9%** (手捩.L) | **1.8** (hand.R x upperarm.L) | *4.4* (forearm.R x upperarm.L) | 39 | 0.96 | 0.99 | 0.0 | 110.9 |
| twist_bend | 1.33 | 0.56 | 0 | *1.6* (下半身) | *2.4%* (腕捩.L) | - | - | **694** (hair x skirt) | 0.98 | 0.91 | 23.5 | 29.7 |
| lie_back_elbows | **2.41** (首) | **0.10** (ひじ補助.R) | *12* (ひじ補助.L) | **4.0** (スカート1_0) | **14.6%** (スカート1_0) | - | - | *352* (hair x skirt) | 0.93 | *0.74* (hip.R) | 8.0 | 99.7 |
| look_over_shoulder | **2.47** (首) | 0.50 | 1 | *1.8* (後髪0_1) | *0.6%* (後髪0_1) | - | - | **1129** (hair x skirt) | 0.98 | 0.95 | 0.0 | 38.3 |
| curtsy | 1.53 | *0.15* (ひざ補助.R) | *18* (ひざ補助.L) | 0.2 | 0.0% | - | - | 40 | 0.96 | 0.85 | 56.6 | 39.6 |
| dance_sway | **2.10** (上半身2) | *0.16* (ひざ補助.R) | 9 | *1.8* (横髪巻_1.L) | **14.3%** (横髪巻_2.R) | - | - | **1463** (hair x skirt) | 0.87 | *0.72* (shoulder.L) | 37.9 | 41.5 |
| dance_point | *1.84* (ひじ.L) | *0.14* (ひじ補助.L) | *31* (ひじ補助.L) | **2.3** (手捩.L) | **7.3%** (手捩.L) | - | - | **1770** (hair x skirt) | 0.86 | *0.79* (shoulder.R) | 38.4 | 32.9 |
| dance_heart | *1.88* (上半身2) | *0.22* (ひじ補助.R) | 0 | *2.0* (横髪巻_1.R) | **11.2%** (上半身2) | **2.3** (hand.L x hand.R) | *4.3* (forearm.R x hand.L) | **2826** (hair x garment) | 0.87 | *0.78* (shoulder.R) | 32.6 | 108.3 |
| dance_clap | *1.71* (ひじ.R) | *0.14* (ひじ補助.L) | *28* (ひざ補助.L) | 0.7 | *0.6%* (手捩.R) | *0.9* (hand.L x hand.R) | *3.9* (forearm.L x hand.R) | **4119** (hair x skirt) | 0.90 | 0.80 | 71.0 | 108.3 |

## motion

| name | stretch | compress | flip | pen cm | pen % | self cm | contact cm | cross | joint | vol | knee | elbow | pop mm | bone pop mm | jitter | speed m/s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| walk | 1.43 | *0.15* (ひざ補助.L) | 8 | *1.1* (腕捩.R) | *1.8%* (腕捩.R) | - | - | **1184** (hair x skirt, f29) | 0.96 | 0.87 | 26.1 | 37.1 | **45.8** (スカート1_2, f21) | **40.9** (スカート1_2, f21) | **0.13** (スカート3_2, f21) | 1.22 |
| run | *1.96* (スカート12_2) | **0.10** (ひじ補助.R, f10) | *41* (ひざ補助.R) | *1.6* (後髪束14_2) | *2.9%* (足首.R) | - | 2.4 | **1094** (hair x garment, f0) | 0.94 | **0.64** (knee.L, f15) | 25.2 | 95.3 | **78.9** (スカート13_1, f20) | **74.3** (ひざ補助.R, f20) | **0.79** (ひざ補助.R, f21) | 4.00 |
| turn | 1.39 | *0.15* (ひざ補助.L) | 8 | **2.5** (足首.R, f39) | **29.1%** (足首.L, f36) | **4.9** (thigh.L x thigh.R, f38) | *5.5* (shin.L x thigh.R) | **2327** (hair x skirt, f26) | 0.96 | 0.86 | 22.1 | 45.1 | **8.1** (足首.L, f30) | **7.9** (スカート13_2, f13) | *0.05* (スカート14_2) | 0.78 |
| sit_stand | **2.22** (スカート5_1, f65) | *0.15* (ひざ補助.L) | *42* (ひざ補助.L) | **4.1** (スカート1_0, f32) | **54.6%** (スカート0_0, f61) | - | 1.6 | 16 | 0.92 | *0.76* (hip.R) | 0.0 | 35.4 | **78.4** (スカート2_2, f65) | **66.6** (スカート2_2, f65) | **0.41** (スカート5_1, f65) | 2.05 |
| spin | **2.33** (スカート15_2, f15) | *0.23* (ひざ補助.R) | 0 | **2.5** (横髪巻_1.R, f2) | **19.9%** (横髪巻_1.R, f3) | **4.4** (thigh.L x thigh.R, f26) | *5.1* (shin.L x thigh.R) | **4071** (hair x skirt, f34) | 0.94 | 0.91 | 25.8 | 35.4 | *4.1* (スカート14_2) | *4.2* (スカート14_2) | *0.04* (スカート15_2) | 0.91 |
| idol_dance | **2.33** (肩.L, f80) | **0.07** (ひじ補助.L, f74) | *35* (ひざ補助.L) | **4.5** (手捩.L, f74) | **31.8%** (横髪巻_2.R, f14) | **4.5** (forearm.L x thigh.L, f74) | *4.9* (forearm.L x hand.R) | **4318** (hair x garment, f77) | *0.80* (shoulder.L) | **0.59** (shoulder.L, f80) | 0.0 | 29.7 | **107.4** (袖_1.L, f81) | **430.9** (肩補助2.L, f80) | **0.99** (上半身2, f80) | 7.25 |

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
| 1 | major | bone_pop | rig | 肩補助2.L (bones) | 430.9 in idol_dance@80 | idol_dance@80 |
| 2 | major | pop | sleeves | 袖_1.L (sleeve_balloon) | 107.4 in idol_dance@81 | idol_dance@81 |
| 3 | major | pen_frac | bodice | スカート0_0 (bodice_ribbon_tails) | 54.6% in sit_stand@61 | sit_stand@61, jump_tuck |
| 4 | major | pen_frac | bodice | スカート15_0 (bodice_ribbon_tails) | 49.5% in sit_chair | sit_chair, kneel_one, high_kick |
| 5 | major | pop | petticoat | スカート13_1 (petticoat_core) | 78.9 in run@20 | run@20 |
| 6 | major | jitter | body | 上半身2 (body) | 0.99 in idol_dance@80 | idol_dance@80 |
| 7 | major | pop | petticoat | スカート2_2 (petticoat_tier1) | 78.4 in sit_stand@65 | sit_stand@65 |
| 8 | major | bone_pop | rig | ひざ補助.R (bones) | 74.3 in run@20 | run@20 |
| 9 | major | bone_pop | rig | スカート2_2 (bones) | 66.6 in sit_stand@65 | sit_stand@65 |
| 10 | major | cross | hair/skirt | hair x skirt (hair x skirt) | 5734 in jump_tuck | jump_tuck, reach_up_back, dance_clap, idol_dance@36, spin@34, hands_behind_head, turn@26, dance_point, high_kick, dance_sway, walk@29, look_over_shoulder, da... |
| 11 | major | jitter | body | ひざ補助.R (body) | 0.79 in run@21 | run@21 |
| 12 | major | cross | hair/garment | hair x garment (hair x garment) | 4991 in hands_behind_head | hands_behind_head, idol_dance@77, reach_up_back, dance_heart, run_l, hands_behind_back, run@0, run_r, dance_sway, walk@0, lie_back_elbows, look_over_shoulder... |
| 13 | major | pen_frac | hair_front | 横髪巻_2.R (hair_curl_R) | 31.8% in idol_dance@14 | idol_dance@14, dance_sway, hands_on_hips |
| 14 | major | pen_frac | shoes | 足首.L (shoes_leaves) | 29.1% in turn@36 | turn@36, spin@22, seiza |
| 15 | major | pop | petticoat | スカート1_2 (petticoat_tier0) | 45.8 in walk@21 | walk@21 |
| 16 | major | bone_pop | rig | スカート1_2 (bones) | 40.9 in walk@21 | walk@21 |
| 17 | major | pen_frac | hair_front | 横髪巻_1.R (hair_curl_R) | 19.9% in spin@3 | spin@3, high_kick, dance_heart, jump_tuck |
| 18 | major | jitter | skirt | スカート5_1 (skirt) | 0.41 in sit_stand@65 | sit_stand@65 |
| 19 | major | pen_frac | hair_front | 頭 (hair_cheek_L) | 19.6% in idol_dance@81 | idol_dance@81, reach_up_back, hands_behind_head, idol_dance@50, dance_heart, idol_dance@80, idol_dance@48 |
| 20 | major | pen_frac | sleeves | 手捩.L (sleeve_cuff) | 17.4% in idol_dance@74 | idol_dance@74, hug_self, dance_point, hands_behind_back, lie_back_elbows, hand_to_shoulder |
| 21 | major | pen_frac | hair_front | 横髪巻_2.L (hair_curl_L) | 17.1% in spin@1 | spin@1, hands_on_hips, high_kick |
| 22 | major | pen_frac | hair_front | 横髪長_1.L (hair_lock_L) | 16.8% in idol_dance@81 | idol_dance@81, dance_heart, dance_sway |
| 23 | major | pen_frac | hair_front | 横髪巻_1.L (hair_curl_L) | 16.5% in idol_dance@81 | idol_dance@81, dance_sway, dance_heart, jump_tuck |
| 24 | major | pen_frac | bodice | スカート15_1 (bodice_ribbon_tails) | 16.1% in deep_lunge | deep_lunge |
| 25 | major | pen_frac | bodice | スカート1_0 (bodice_ribbon_tails) | 14.6% in lie_back_elbows | lie_back_elbows |
| 26 | major | pen_frac | accessories | 上半身2 (acc_halter) | 12.9% in hands_behind_head | hands_behind_head, dance_heart, idol_dance@48, dance_sway, reach_up_back, jump_tuck, spin@0, high_kick |
| 27 | major | self | body | body:thigh.L x thigh.R (body:thigh.L x thigh.R) | 4.9 in turn@38 | turn@38, spin@26 |
| 28 | major | pen_frac | hair_front | 横髪奥_1.L (hair_curtain_L) | 11.3% in idol_dance@80 | idol_dance@80, reach_up_back, dance_point, spin@7 |
| 29 | major | pen_frac | hair_front | 横髪長_2.L (hair_lock_L) | 11.0% in hug_self | hug_self, hand_to_shoulder |
| 30 | major | pen_frac | accessories | 頭 (acc_leaves_L) | 10.9% in reach_up_back | reach_up_back, idol_dance@81, dance_heart, idol_dance@48 |
| 31 | major | self | body | body:forearm.L x thigh.L (body:forearm.L x thigh.L) | 4.5 in idol_dance@74 | idol_dance@74 |
| 32 | major | pen_frac | hair_front | 横髪奥_1.R (hair_curtain_R) | 9.9% in dance_sway | dance_sway, idol_dance@11, reach_up_back, turn@5 |
| 33 | major | self | body | body:hand.L x thigh.L (body:hand.L x thigh.L) | 4.2 in idol_dance@75 | idol_dance@75 |
| 34 | major | pen | sleeves | 手捩.L (sleeve_cuff) | 4.5 in idol_dance@74 | idol_dance@74, hug_self, dance_point, lie_back_elbows, hands_behind_back, hand_to_shoulder |
| 35 | major | self | body | body:hand.L x pelvis (body:hand.L x pelvis) | 3.8 in idol_dance@75 | idol_dance@75 |
| 36 | major | pen_frac | bodice | 上半身2 (bodice_shell) | 8.6% in reach_up_back | reach_up_back, hands_behind_head, dance_heart, idol_dance@48, dance_sway, spin@0, high_kick |
| 37 | major | pen_frac | petticoat | スカート14_1 (petticoat_core) | 8.5% in sit_stand@64 | sit_stand@64, run_l, idol_dance@72 |
| 38 | major | self | body | body:shin.L x shin.R (body:shin.L x shin.R) | 3.7 in turn@41 | turn@41, spin@20 |
| 39 | major | pen | skirt | スカート1_0 (skirt) | 4.1 in sit_stand@32 | sit_stand@32, run_r |
| 40 | major | pen | bodice | スカート1_0 (bodice_ribbon_tails) | 4.0 in lie_back_elbows | lie_back_elbows |

## Issues by part (major / minor rows)

| part | major | minor |
|---|---|---|
| body | 41 | 113 |
| hair_front | 36 | 41 |
| petticoat | 31 | 35 |
| bodice | 19 | 10 |
| sleeves | 18 | 72 |
| hair/skirt | 16 | 1 |
| skirt | 13 | 20 |
| accessories | 12 | 15 |
| hair/garment | 9 | 9 |
| shoes | 7 | 9 |
| rig | 5 | 1 |
| hair_back | 0 | 11 |
| head | 0 | 4 |
