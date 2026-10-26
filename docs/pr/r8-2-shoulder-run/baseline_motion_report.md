# Motion test report

Model: 49 meshes, 100430 vertices, 99010 faces (without outlines). Run time 1108 s. Not gated: the exit code of rig_check covers the core poses only. No cloth or hair physics: chains move only as keyed or driven (MMD simulates them).

Thresholds (minor / major): stretch 1.60/2.00, compress 0.30/0.12, flip 10/100, pen 1.0/2.0, pen_frac 0.5%/3.0%, self 0.5/1.5, contact 3.0/6.0, cross 40/400, joint 0.85/0.70, vol 0.80/0.65, knee -0.5/-5.0, elbow -5.0/-15.0, pop 2.0/6.0, bone_pop 2.0/6.0, jitter 0.03/0.08, speed 12.00/20.00, eye 0.8/1.5.
Cells: plain = ok, *italic* = minor, **bold** = major (location, frame for clips). pen/self/contact in cm, pop in mm; joint = median skin radius ratio at the worst joint band, vol = its mean squared radius ratio; knee/elbow = least signed bend (negative = hyperextended).

## extended

| name | stretch | compress | flip | pen cm | pen % | self cm | contact cm | cross | joint | vol | knee | elbow |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| sit_chair | *1.73* (足補助.L) | *0.15* (ひざ補助.R) | *14* (ひざ補助.L) | 0.6 | *1.2%* (スカート11_0) | - | - | 5 | 0.96 | *0.76* (knee.R) | 85.6 | 69.2 |
| seiza | *1.67* (スカート5_2) | **0.12** (ひざ補助2.L) | *54* (ひざ補助.L) | *1.5* (足首.L) | **4.9%** (足首.L) | *0.9* (foot.L x thigh.L) | 2.2 | 0 | 0.97 | **0.65** (knee.L) | 156.4 | 65.0 |
| kneel_one | *1.81* (ひざ.R) | *0.15* (ひざ補助.R) | *19* (ひざ補助.R) | *1.4* (足首.R) | *2.4%* (足首.R) | - | 0.3 | 23 | 0.95 | *0.68* (knee.R) | 83.9 | 35.4 |
| cross_legged | **2.38** (足補助.L) | *0.15* (足補助.L) | *51* (ひざ補助.L) | **3.5** (スカート11_2) | **8.9%** (スカート9_0) | - | - | **582** (skirt x petticoat) | 0.96 | *0.67* (knee.L) | 124.7 | 52.7 |
| deep_lunge | *1.71* (スカート9_2) | *0.18* (ひざ補助.R) | 0 | 0.6 | *0.5%* (スカート11_0) | - | - | 0 | 0.96 | *0.79* (knee.R) | 55.8 | 52.7 |
| run_l | *1.69* (スカート11_2) | *0.15* (ひざ補助.L) | *16* (ひざ補助.L) | *1.1* (後髪束14_2) | *0.5%* (スカート11_0) | - | - | **1157** (hair x garment) | 0.95 | *0.68* (knee.L) | 16.4 | 95.3 |
| run_r | *1.91* (スカート15_2) | *0.15* (ひざ補助.R) | *16* (ひざ補助.R) | *1.2* (後髪束5_2) | *0.7%* (スカート4_0) | - | - | **1083** (hair x garment) | 0.95 | *0.68* (knee.R) | 16.4 | 95.3 |
| jump_tuck | *1.99* (スカート8_2) | *0.15* (ひざ補助.R) | *44* (ひざ補助.L) | *1.2* (横髪巻_1.L) | *1.9%* (横髪巻_1.L) | - | - | **2068** (hair x skirt) | *0.81* (shoulder.L) | *0.65* (knee.R) | 136.0 | 45.1 |
| high_kick | **2.00** (スカート12_0) | *0.27* (足補助.L) | 4 | **2.4** (横髪巻_1.R) | **15.9%** (横髪巻_1.R) | - | - | 34 | 0.95 | 0.94 | 0.0 | 35.4 |
| arms_crossed | *1.67* (袖胴.L) | *0.15* (ひじ補助.L) | 0 | *1.0* (袖胴.R) | 0.3% | **2.4** (forearm.L x forearm.R) | *4.0* (forearm.L x hand.R) | 0 | 0.97 | 0.99 | 0.0 | 109.2 |
| hands_behind_head | *1.87* (袖胴.R) | *0.12* (ひじ補助.L) | *28* (袖_0.L) | *1.3* (ひじ補助.L) | *2.3%* (ひじ補助.L) | *1.0* (hand.L x hand.R) | *4.9* (forearm.R x hand.L) | **4519** (hair x garment) | *0.81* (shoulder.R) | **0.64** (shoulder.R) | 0.0 | 136.5 |
| hands_behind_back | *1.68* (肩補助2.L) | *0.24* (ひじ補助.R) | 0 | *1.4* (手捩.R) | *2.5%* (手捩.R) | *1.2* (forearm.L x forearm.R) | - | **946** (hair x garment) | *0.85* (shoulder.R) | *0.73* (shoulder.R) | 0.0 | 99.7 |
| hand_to_shoulder | *1.66* (袖胴.L) | *0.19* (腕捩.L) | 0 | *1.9* (横髪長_2.L) | **4.2%** (横髪長_2.L) | - | - | *46* (hair x garment) | 0.96 | 0.94 | 0.0 | 32.9 |
| hands_on_hips | 1.55 | 0.35 | 0 | *1.1* (スカート12_0) | 0.1% | - | - | *154* (hair x garment) | 0.92 | 0.89 | 0.0 | 86.6 |
| reach_up_back | *1.73* (上半身2) | 0.34 | 10 | *1.5* (頭) | **13.0%** (頭) | 0.4 | - | **4486** (hair x garment) | 0.92 | 0.82 | -0.0 | 32.9 |
| hug_self | *1.80* (肩補助2.L) | *0.21* (ひじ補助.L) | 0 | **2.5** (手捩.L) | **13.0%** (手捩.L) | **1.9** (hand.R x upperarm.L) | *4.4* (forearm.R x upperarm.L) | 24 | 0.97 | 1.00 | 0.0 | 110.9 |
| twist_bend | 1.60 | 0.57 | 1 | *1.6* (下半身) | *2.5%* (腕捩.L) | - | - | 0 | 0.98 | 0.92 | 23.5 | 29.7 |
| lie_back_elbows | *1.84* (スカート12_0) | *0.14* (ひじ補助.R) | 2 | *1.4* (下半身) | *1.7%* (スカート5_0) | - | - | *43* (hair x garment) | 0.98 | 0.96 | 8.0 | 99.7 |
| look_over_shoulder | 1.53 | 0.59 | 0 | *2.0* (後髪0_1) | *1.3%* (後髪0_1) | - | - | *383* (hair x garment) | 0.98 | 0.95 | 0.0 | 38.3 |
| curtsy | 1.42 | *0.27* (ひざ補助.L) | 1 | 0.2 | 0.0% | - | - | 17 | 0.96 | 0.82 | 56.6 | 39.6 |
| dance_sway | *1.78* (上半身2) | *0.23* (袖_0.L) | 3 | *1.8* (横髪巻_1.L) | **7.2%** (横髪巻_1.L) | - | - | **1397** (hair x garment) | *0.84* (shoulder.L) | *0.66* (shoulder.L) | 37.9 | 41.5 |
| dance_point | *1.77* (袖胴.L) | *0.14* (ひじ補助.L) | 1 | **2.3** (手捩.L) | **7.3%** (手捩.L) | - | - | *84* (hair x garment) | 0.87 | *0.76* (shoulder.R) | 38.4 | 32.9 |
| dance_heart | *1.72* (上半身2) | *0.27* (ひじ補助.L) | 2 | *1.3* (頭) | **6.6%** (頭) | **2.5** (hand.L x hand.R) | *4.2* (forearm.L x hand.R) | **3165** (hair x garment) | *0.85* (shoulder.L) | *0.73* (shoulder.R) | 32.6 | 108.3 |
| dance_clap | 1.60 | *0.20* (ひざ補助.R) | 0 | 0.7 | *0.6%* (手捩.R) | *0.9* (hand.L x hand.R) | *3.9* (forearm.L x hand.R) | 15 | 0.90 | *0.80* (knee.R) | 71.0 | 108.3 |

## motion

| name | stretch | compress | flip | pen cm | pen % | self cm | contact cm | cross | joint | vol | knee | elbow | pop mm | bone pop mm | jitter | speed m/s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| walk | 1.59 | 0.33 | 1 | *1.1* (腕捩.R) | *1.8%* (腕捩.R) | - | - | *238* (hair x skirt) | 0.96 | 0.84 | 26.1 | 37.1 | **8.3** (ひざ補助2.R, f41) | **8.4** (ひざ補助.R, f11) | *0.03* (スカート15_2) | 1.22 |
| run | **2.10** (スカート15_2, f8) | *0.15* (ひざ補助.R) | *20* (ひざ補助.R) | *1.6* (後髪束5_2) | *2.9%* (足首.R) | - | - | **1125** (hair x garment, f0) | 0.95 | *0.67* (knee.R) | 25.2 | 95.3 | **72.5** (ひざ補助2.R, f20) | **74.3** (ひざ補助.R, f20) | **0.37** (後髪束17_3, f28) | 4.00 |
| turn | 1.40 | *0.28* (ひざ補助.L) | 1 | *1.1* (足首.R) | *1.0%* (足首.R) | **1.8** (foot.L x foot.R, f24) | - | *220* (hair x skirt) | 0.96 | 0.82 | 32.6 | 45.1 | **111.3** (後髪束2_4, f20) | **94.3** (後髪束2_4, f20) | **0.12** (後髪束2_2, f16) | 4.38 |
| sit_stand | *1.96* (スカート0_0) | *0.15* (ひざ補助.L) | *18* (ひざ補助.L) | *1.7* (スカート2_0) | *2.6%* (スカート2_1) | - | - | 4 | 0.96 | *0.74* (knee.R) | 0.0 | 35.4 | *3.3* (スカート5_2) | *3.4* (スカート5_2) | 0.02 | 0.81 |
| spin | **2.13** (スカート15_2, f19) | 0.49 | 2 | **2.5** (横髪巻_1.R, f5) | **19.3%** (横髪巻_1.R, f5) | - | - | **782** (hair x skirt, f10) | 0.95 | 0.88 | 25.8 | 35.4 | **82.4** (横髪巻_2.R, f6) | **78.0** (横髪巻_2.R, f6) | **0.09** (横髪巻_1.R, f6) | 3.94 |
| idol_dance | **2.01** (上半身2, f78) | **0.09** (肩補助3.L, f79) | *62* (袖_0.L) | **4.3** (手捩.L, f74) | **16.2%** (手捩.L, f74) | **4.7** (forearm.L x thigh.L, f74) | *4.9* (forearm.L x hand.R) | **4358** (hair x garment, f77) | **0.60** (shoulder.L, f79) | **0.46** (shoulder.L, f79) | 0.0 | 29.7 | **123.0** (後髪束2_4, f40) | **108.5** (後髪束2_4, f40) | **0.73** (腕D.L, f78) | 6.69 |

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
| 1 | major | pop | hair_back | 後髪束2_4 (hair_back_side) | 123.0 in idol_dance@40 | idol_dance@40, turn@20 |
| 2 | major | bone_pop | rig | 後髪束2_4 (bones) | 108.5 in idol_dance@40 | idol_dance@40, turn@20 |
| 3 | major | pop | hair_front | 横髪巻_2.R (hair_curl_R) | 82.4 in spin@6 | spin@6 |
| 4 | major | bone_pop | rig | 横髪巻_2.R (bones) | 78.0 in spin@6 | spin@6 |
| 5 | major | bone_pop | rig | ひざ補助.R (bones) | 74.3 in run@20 | run@20, walk@11 |
| 6 | major | pop | body | ひざ補助2.R (body) | 72.5 in run@20 | run@20, walk@41 |
| 7 | major | jitter | body | 腕D.L (body) | 0.73 in idol_dance@78 | idol_dance@78 |
| 8 | major | cross | hair/garment | hair x garment (hair x garment) | 4519 in hands_behind_head | hands_behind_head, reach_up_back, idol_dance@77, dance_heart, dance_sway, run_l, run@0, run_r, hands_behind_back, look_over_shoulder, walk@14, jump_tuck, han... |
| 9 | major | pen_frac | hair_front | 横髪巻_1.R (hair_curl_R) | 19.3% in spin@5 | spin@5, high_kick, idol_dance@51, jump_tuck |
| 10 | major | jitter | hair_back | 後髪束17_3 (hair_back_side) | 0.37 in run@28 | run@28 |
| 11 | major | pen_frac | sleeves | 手捩.L (sleeve_cuff) | 16.2% in idol_dance@74 | idol_dance@74, hug_self, dance_point, hand_to_shoulder |
| 12 | major | cross | hair/skirt | hair x skirt (hair x skirt) | 2068 in jump_tuck | jump_tuck, spin@10, idol_dance@71, run_l, walk@24, turn@19, look_over_shoulder, dance_heart, dance_point |
| 13 | major | pen_frac | accessories | 頭 (acc_leaves_L) | 13.0% in reach_up_back | reach_up_back, dance_heart, idol_dance@48 |
| 14 | major | self | body | body:forearm.L x thigh.L (body:forearm.L x thigh.L) | 4.7 in idol_dance@74 | idol_dance@74 |
| 15 | major | self | body | body:hand.L x thigh.L (body:hand.L x thigh.L) | 4.6 in idol_dance@74 | idol_dance@74 |
| 16 | major | pen_frac | hair_front | 頭 (hair_cheek_L) | 10.3% in reach_up_back | reach_up_back, idol_dance@81, dance_sway, idol_dance@45, dance_heart, idol_dance@48, idol_dance@50 |
| 17 | major | pen_frac | hair_front | 横髪巻_1.L (hair_curl_L) | 10.3% in idol_dance@14 | idol_dance@14, dance_sway, jump_tuck |
| 18 | major | pen_frac | petticoat | スカート9_0 (petticoat_core) | 8.9% in cross_legged | cross_legged, high_kick |
| 19 | major | pen | sleeves | 手捩.L (sleeve_cuff) | 4.3 in idol_dance@74 | idol_dance@74, hug_self, dance_point, hand_to_shoulder |
| 20 | major | self | body | body:hand.L x upperarm.R (body:hand.L x upperarm.R) | 3.5 in idol_dance@30 | idol_dance@30 |
| 21 | major | pen_frac | hair_front | 横髪奥_1.L (hair_curtain_L) | 7.8% in idol_dance@80 | idol_dance@80, dance_point, spin@6 |
| 22 | major | pen | petticoat | スカート11_2 (petticoat_tier1) | 3.5 in cross_legged | cross_legged |
| 23 | major | self | body | body:forearm.L x pelvis (body:forearm.L x pelvis) | 2.8 in idol_dance@75 | idol_dance@75 |
| 24 | major | vol | body | joint:shoulder.L (joint:shoulder.L) | 0.46 in idol_dance@79 | idol_dance@79, hands_behind_head, dance_sway, jump_tuck, dance_heart, hands_behind_back |
| 25 | major | pen_frac | petticoat | スカート11_2 (petticoat_tier1) | 5.8% in cross_legged | cross_legged |
| 26 | major | pen_frac | hair_front | 横髪奥_1.R (hair_curtain_R) | 5.7% in idol_dance@16 | idol_dance@16, dance_sway |
| 27 | major | pen_frac | hair_front | 横髪長_0.L (hair_lock_L) | 5.5% in idol_dance@81 | idol_dance@81, reach_up_back |
| 28 | major | self | body | body:hand.L x hand.R (body:hand.L x hand.R) | 2.5 in dance_heart | dance_heart, idol_dance@48, hands_behind_head, dance_clap |
| 29 | major | stretch | body | 足補助.L (body) | 2.38 in cross_legged | cross_legged, lie_back_elbows, sit_stand@58, sit_chair, jump_tuck |
| 30 | major | self | body | body:forearm.L x forearm.R (body:forearm.L x forearm.R) | 2.4 in arms_crossed | arms_crossed, hands_behind_back |
| 31 | major | pen_frac | shoes | 足首.L (shoes_shell) | 4.9% in seiza | seiza |
| 32 | major | pen | petticoat | スカート9_0 (petticoat_core) | 2.7 in cross_legged | cross_legged, high_kick |
| 33 | major | pen_frac | hair_front | 横髪長_0.R (hair_lock_R) | 4.8% in reach_up_back | reach_up_back |
| 34 | major | jitter | hair_back | 後髪束2_2 (hair_back_side) | 0.12 in turn@16 | turn@16 |
| 35 | major | stretch | petticoat | スカート12_0 (petticoat_core) | 2.27 in cross_legged | cross_legged, high_kick, lie_back_elbows, kneel_one, sit_chair, sit_stand@36 |
| 36 | major | joint | body | joint:shoulder.L (joint:shoulder.L) | 0.60 in idol_dance@79 | idol_dance@79, jump_tuck, hands_behind_head, dance_sway, dance_heart, hands_behind_back |
| 37 | major | pen | hair_front | 横髪巻_1.R (hair_curl_R) | 2.5 in spin@5 | spin@5, high_kick, idol_dance@51, jump_tuck |
| 38 | major | cross | skirt/petticoat | skirt x petticoat (skirt x petticoat) | 582 in cross_legged | cross_legged |
| 39 | major | pen_frac | hair_front | 横髪長_2.L (hair_lock_L) | 4.2% in hand_to_shoulder | hand_to_shoulder |
| 40 | major | stretch | skirt | スカート14_1 (skirt) | 2.15 in cross_legged | cross_legged |

## Issues by part (major / minor rows)

| part | major | minor |
|---|---|---|
| body | 22 | 94 |
| hair_front | 22 | 28 |
| sleeves | 9 | 61 |
| hair/garment | 9 | 9 |
| petticoat | 8 | 41 |
| accessories | 8 | 4 |
| rig | 5 | 1 |
| hair_back | 4 | 11 |
| hair/skirt | 2 | 7 |
| skirt | 1 | 29 |
| shoes | 1 | 9 |
| skirt/petticoat | 1 | 0 |
| bodice | 0 | 10 |
| head | 0 | 4 |
