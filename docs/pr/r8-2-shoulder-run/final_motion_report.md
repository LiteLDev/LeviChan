# Motion test report

Model: 49 meshes, 100430 vertices, 99010 faces (without outlines). Run time 1044 s. Not gated: the exit code of rig_check covers the core poses only. No cloth or hair physics: chains move only as keyed or driven (MMD simulates them).

Thresholds (minor / major): stretch 1.60/2.00, compress 0.30/0.12, flip 10/100, pen 1.0/2.0, pen_frac 0.5%/3.0%, self 0.5/1.5, contact 3.0/6.0, cross 40/400, joint 0.85/0.70, vol 0.80/0.65, knee -0.5/-5.0, elbow -5.0/-15.0, pop 2.0/6.0, bone_pop 2.0/6.0, jitter 0.03/0.08, speed 12.00/20.00, eye 0.8/1.5, span 0.70/1.00.
Cells: plain = ok, *italic* = minor, **bold** = major (location, frame for clips). pen/self/contact in cm, pop in mm; joint = median skin radius ratio at the worst joint band, vol = its mean squared radius ratio; knee/elbow = least signed bend (negative = hyperextended).

## core

| name | stretch | compress | flip | pen cm | pen % | cross | joint | vol | knee | elbow | span |
|---|---|---|---|---|---|---|---|---|---|---|---|
| test | *1.69* (スカート12_2) | *0.15* (ひざ補助.L) | *12* (ひざ補助.L) | 0.4 | 0.0% | *226* (hair x skirt) | 0.95 | *0.72* (knee.L) | 59.8 | 69.2 | *0.95* (knee.L) |
| arms_up | *1.77* (腕捩.R) | 0.43 | 0 | 0.7 | *1.2%* (横髪巻_1.L) | **851** (hair x garment) | 0.93 | 0.87 | -0.0 | 41.5 | - |
| arms_forward | *1.73* (ひじ.L) | **0.07** (ひじ補助.R) | *80* (ひじ補助.L) | *1.2* (腕捩.L) | *1.6%* (腕捩.L) | 1 | 0.98 | 0.99 | 0.0 | 139.4 | **1.69** (elbow.R) |
| wrist_twist_pos | 1.31 | 0.60 | 0 | 0.0 | 0.0% | 0 | 0.90 | 0.81 | 0.0 | 56.7 | - |
| wrist_twist_neg | 1.31 | 0.60 | 0 | 0.0 | 0.0% | 0 | 0.91 | 0.80 | 0.0 | 56.7 | - |
| squat | *1.72* (ひざ.L) | *0.16* (ひざ補助.R) | *32* (ひざ補助.L) | 0.8 | *2.2%* (足首.L) | 0 | 0.95 | *0.69* (knee.L) | 113.2 | 29.7 | *0.96* (knee.L) |
| walk | 1.58 | 0.48 | 0 | *1.7* (後髪束14_2) | 0.1% | **1381** (hair x garment) | 0.97 | 0.88 | 29.5 | 38.3 | - |
| head_left | 1.46 | 0.55 | 1 | 0.2 | 0.0% | *249* (hair x garment) | 0.99 | 0.97 | 0.0 | 29.7 | - |
| head_right | 1.46 | 0.55 | 0 | 0.2 | 0.0% | *247* (hair x garment) | 0.99 | 0.97 | 0.0 | 29.7 | - |
| torso_left | 1.51 | 0.61 | 1 | 0.0 | 0.0% | *94* (hair x skirt) | 0.99 | 0.98 | 0.0 | 29.7 | - |
| torso_right | 1.37 | 0.49 | 1 | 0.1 | 0.0% | *60* (hair x garment) | 0.99 | 0.98 | 0.0 | 29.7 | - |
| swing | 1.51 | 0.82 | 1 | 0.0 | 0.0% | 1 | 1.00 | 1.00 | 0.0 | 29.7 | - |
| fist | *1.68* (手首.L) | *0.24* (手首.L) | 0 | 0.0 | 0.0% | 0 | 1.00 | 0.99 | 0.0 | 45.1 | - |
| raise_bend | 1.43 | 0.46 | 0 | 0.6 | 0.1% | *170* (hair x garment) | 0.99 | 1.00 | 0.0 | 69.2 | - |
| reach_forward | 1.56 | 0.31 | 0 | 0.0 | 0.0% | 0 | 0.98 | 0.98 | 0.0 | 95.3 | 0.53 |
| forward_bend | 1.28 | 0.72 | 0 | 0.3 | 0.0% | 23 | 0.98 | 0.94 | 21.0 | 50.5 | - |
| side_bend | 1.46 | 0.67 | 0 | *1.6* (下半身) | *1.5%* (袖_0.L) | *180* (hair x skirt) | 0.99 | 0.98 | 0.0 | 29.7 | - |

## extended

| name | stretch | compress | flip | pen cm | pen % | self cm | contact cm | cross | joint | vol | knee | elbow | span |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| sit_chair | *1.73* (足補助.L) | *0.15* (ひざ補助.R) | *14* (ひざ補助.L) | 0.6 | *1.2%* (スカート11_0) | - | - | 5 | 0.96 | *0.76* (knee.R) | 85.6 | 69.2 | *0.94* (knee.L) |
| seiza | *1.67* (スカート5_2) | **0.12** (ひざ補助2.L) | *54* (ひざ補助.L) | *1.5* (足首.L) | **4.9%** (足首.L) | *0.9* (foot.L x thigh.L) | 2.2 | 0 | 0.97 | **0.65** (knee.L) | 156.4 | 65.0 | *0.97* (knee.R) |
| kneel_one | *1.81* (ひざ.R) | *0.15* (ひざ補助.R) | *19* (ひざ補助.R) | *1.4* (足首.R) | *2.4%* (足首.R) | - | 0.3 | 23 | 0.95 | *0.68* (knee.R) | 83.9 | 35.4 | **1.47** (elbow.L) |
| cross_legged | **2.38** (足補助.L) | *0.15* (足補助.L) | *51* (ひざ補助.L) | **3.5** (スカート11_2) | **8.9%** (スカート9_0) | - | - | **582** (skirt x petticoat) | 0.96 | *0.67* (knee.L) | 124.7 | 52.7 | *0.97* (knee.R) |
| deep_lunge | *1.71* (スカート9_2) | *0.18* (ひざ補助.R) | 0 | 0.6 | *0.5%* (スカート11_0) | - | - | 0 | 0.96 | *0.79* (knee.R) | 55.8 | 52.7 | *0.93* (knee.R) |
| run_l | *1.69* (スカート11_2) | *0.15* (ひざ補助.L) | *16* (ひざ補助.L) | *1.1* (後髪束14_2) | *0.5%* (スカート11_0) | - | - | **1157** (hair x garment) | 0.95 | *0.68* (knee.L) | 16.4 | 95.3 | *0.97* (knee.L) |
| run_r | *1.91* (スカート15_2) | *0.15* (ひざ補助.R) | *16* (ひざ補助.R) | *1.2* (後髪束5_2) | *0.7%* (スカート4_0) | - | - | **1083** (hair x garment) | 0.95 | *0.68* (knee.R) | 16.4 | 95.3 | *0.97* (knee.R) |
| jump_tuck | *1.99* (スカート8_2) | *0.15* (ひざ補助.R) | *44* (ひざ補助.L) | *1.2* (横髪巻_1.L) | *1.9%* (横髪巻_1.L) | - | - | **2068** (hair x skirt) | *0.81* (shoulder.R) | *0.65* (knee.R) | 136.0 | 45.1 | *0.97* (knee.R) |
| high_kick | **2.00** (スカート12_0) | *0.27* (足補助.L) | 4 | **2.4** (横髪巻_1.R) | **15.9%** (横髪巻_1.R) | - | - | 34 | 0.95 | 0.94 | 0.0 | 35.4 | - |
| arms_crossed | *1.67* (袖胴.L) | *0.15* (ひじ補助.L) | 0 | *1.0* (袖胴.R) | 0.3% | **2.4** (forearm.L x forearm.R) | *4.0* (forearm.L x hand.R) | 0 | 0.97 | 0.99 | 0.0 | 109.2 | **1.67** (elbow.R) |
| hands_behind_head | *1.87* (袖胴.R) | *0.12* (ひじ補助.R) | *28* (袖_0.L) | *1.3* (ひじ補助.L) | *2.3%* (ひじ補助.L) | *1.0* (hand.L x hand.R) | *4.9* (forearm.R x hand.L) | **4519** (hair x garment) | *0.81* (shoulder.L) | **0.64** (shoulder.L) | 0.0 | 136.5 | **1.69** (elbow.L) |
| hands_behind_back | *1.68* (肩.R) | *0.24* (ひじ補助.R) | 0 | *1.4* (手捩.R) | *2.5%* (手捩.R) | *1.2* (forearm.L x forearm.R) | - | **946** (hair x garment) | *0.85* (shoulder.R) | *0.73* (shoulder.L) | 0.0 | 99.7 | *0.85* (elbow.R) |
| hand_to_shoulder | *1.66* (袖胴.L) | *0.19* (腕捩.L) | 0 | *1.9* (横髪長_2.L) | **4.2%** (横髪長_2.L) | - | - | *46* (hair x garment) | 0.96 | 0.94 | 0.0 | 32.9 | **1.00** (elbow.L) |
| hands_on_hips | 1.55 | 0.35 | 0 | *1.1* (スカート12_0) | 0.1% | - | - | *154* (hair x garment) | 0.92 | 0.89 | 0.0 | 86.6 | **1.94** (elbow.L) |
| reach_up_back | *1.73* (上半身2) | 0.34 | 10 | *1.5* (頭) | **13.0%** (頭) | 0.4 | - | **4486** (hair x garment) | 0.92 | 0.82 | -0.0 | 32.9 | - |
| hug_self | *1.80* (肩補助2.L) | *0.21* (ひじ補助.L) | 0 | **2.5** (手捩.L) | **13.0%** (手捩.L) | **1.9** (hand.R x upperarm.L) | *4.4* (forearm.R x upperarm.L) | 24 | 0.97 | 1.00 | 0.0 | 110.9 | *0.97* (elbow.L) |
| twist_bend | 1.60 | 0.57 | 1 | *1.6* (下半身) | *2.5%* (腕捩.L) | - | - | 0 | 0.98 | 0.92 | 23.5 | 29.7 | - |
| lie_back_elbows | *1.84* (スカート12_0) | *0.14* (ひじ補助.R) | 2 | *1.4* (下半身) | *1.7%* (スカート5_0) | - | - | *43* (hair x garment) | 0.98 | 0.96 | 8.0 | 99.7 | *0.85* (elbow.R) |
| look_over_shoulder | 1.53 | 0.59 | 0 | *2.0* (後髪0_1) | *1.3%* (後髪0_1) | - | - | *383* (hair x garment) | 0.98 | 0.95 | 0.0 | 38.3 | - |
| curtsy | 1.42 | *0.27* (ひざ補助.L) | 1 | 0.2 | 0.0% | - | - | 17 | 0.96 | 0.82 | 56.6 | 39.6 | *0.92* (knee.L) |
| dance_sway | *1.78* (上半身2) | *0.23* (袖_0.L) | 3 | *1.8* (横髪巻_1.L) | **7.2%** (横髪巻_1.L) | - | - | **1397** (hair x garment) | *0.84* (shoulder.L) | *0.66* (shoulder.L) | 37.9 | 41.5 | **2.02** (elbow.R) |
| dance_point | *1.77* (袖胴.L) | *0.14* (ひじ補助.L) | 1 | **2.3** (手捩.L) | **7.3%** (手捩.L) | - | - | *84* (hair x garment) | 0.87 | *0.76* (shoulder.R) | 38.4 | 32.9 | **1.05** (elbow.L) |
| dance_heart | *1.72* (上半身2) | *0.27* (ひじ補助.L) | 2 | *1.3* (頭) | **6.6%** (頭) | **2.5** (hand.L x hand.R) | *4.2* (forearm.L x hand.R) | **3165** (hair x garment) | *0.85* (shoulder.L) | *0.73* (shoulder.R) | 32.6 | 108.3 | **1.64** (elbow.R) |
| dance_clap | 1.60 | *0.20* (ひざ補助.R) | 0 | 0.7 | *0.6%* (手捩.R) | *0.9* (hand.L x hand.R) | *3.9* (forearm.L x hand.R) | 15 | 0.90 | *0.80* (knee.R) | 71.0 | 108.3 | **1.65** (elbow.R) |

## motion

| name | stretch | compress | flip | pen cm | pen % | self cm | contact cm | cross | joint | vol | knee | elbow | span | pop mm | bone pop mm | jitter | speed m/s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| walk | 1.59 | 0.33 | 1 | *1.1* (腕捩.R) | *1.8%* (腕捩.R) | - | - | *238* (hair x skirt) | 0.96 | 0.84 | 26.1 | 37.1 | *0.91* (knee.L) | **8.3** (ひざ補助2.R, f41) | **8.4** (ひざ補助.R, f11) | *0.03* (スカート15_2) | 1.22 |
| run | **2.15** (スカート15_2, f6) | *0.13* (ひざ補助2.L) | *26* (ひざ補助.R) | *1.6* (後髪束5_2) | **3.3%** (足首.R, f3) | - | *5.9* (pelvis x thigh.L) | **1137** (hair x garment, f18) | 0.95 | **0.65** (knee.R, f4) | 32.4 | 86.6 | **1.87** (elbow.L, f18) | **56.6** (スカート14_2, f7) | **51.8** (スカート14_2, f7) | **0.37** (後髪束17_3, f10) | 4.91 |
| turn | 1.40 | *0.28* (ひざ補助.L) | 1 | *1.1* (足首.R) | *1.0%* (足首.R) | **1.8** (foot.L x foot.R, f24) | - | *220* (hair x skirt) | 0.96 | 0.82 | 32.6 | 45.1 | *0.92* (knee.L) | **111.3** (後髪束2_4, f20) | **94.3** (後髪束2_4, f20) | **0.12** (後髪束2_2, f16) | 4.38 |
| sit_stand | *1.96* (スカート0_0) | *0.15* (ひざ補助.L) | *18* (ひざ補助.L) | *1.7* (スカート2_0) | *2.6%* (スカート2_1) | - | - | 4 | 0.96 | *0.74* (knee.R) | 0.0 | 35.4 | *0.94* (knee.L) | *3.3* (スカート5_2) | *3.4* (スカート5_2) | 0.02 | 0.81 |
| spin | **2.13** (スカート15_2, f19) | 0.49 | 2 | **2.5** (横髪巻_1.R, f40) | **19.3%** (横髪巻_1.R, f5) | - | - | **782** (hair x skirt, f10) | 0.95 | 0.88 | 25.8 | 35.4 | - | **82.4** (横髪巻_2.R, f6) | **78.0** (横髪巻_2.R, f6) | **0.09** (横髪巻_1.R, f6) | 3.94 |
| idol_dance | **2.01** (上半身2, f78) | **0.09** (肩補助3.L, f79) | *62* (袖_0.L) | **4.3** (手捩.L, f74) | **16.2%** (手捩.L, f74) | **4.7** (forearm.L x thigh.L, f74) | *4.9* (forearm.L x hand.R) | **4358** (hair x garment, f77) | **0.60** (shoulder.L, f79) | **0.46** (shoulder.L, f79) | 0.0 | 29.7 | **3.03** (elbow.R, f14) | **123.0** (後髪束2_4, f40) | **108.5** (後髪束2_4, f40) | **0.73** (腕D.L, f78) | 6.69 |

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
| 5 | major | jitter | body | 腕D.L (body) | 0.73 in idol_dance@78 | idol_dance@78 |
| 6 | major | pop | petticoat | スカート14_2 (petticoat_tier0) | 56.6 in run@7 | run@7 |
| 7 | major | bone_pop | rig | スカート14_2 (bones) | 51.8 in run@7 | run@7 |
| 8 | major | cross | hair/garment | hair x garment (hair x garment) | 4519 in hands_behind_head | hands_behind_head, reach_up_back, idol_dance@77, dance_heart, dance_sway, walk, run_l, run@18, run_r, hands_behind_back, arms_up, look_over_shoulder, head_le... |
| 9 | major | span | body | elbow.R (span:elbow.R) | 3.03 in idol_dance@14 | idol_dance@14, dance_sway, hands_on_hips, run@8, hands_behind_head, arms_forward, arms_crossed, dance_clap, dance_heart, hug_self, hands_behind_back, lie_bac... |
| 10 | major | pen_frac | hair_front | 横髪巻_1.R (hair_curl_R) | 19.3% in spin@5 | spin@5, high_kick, idol_dance@51, jump_tuck, arms_up |
| 11 | major | jitter | hair_back | 後髪束17_3 (hair_back_side) | 0.37 in run@10 | run@10 |
| 12 | major | span | body | elbow.L (span:elbow.L) | 2.70 in idol_dance@56 | idol_dance@56, hands_on_hips, run@18, hands_behind_head, arms_forward, dance_clap, dance_heart, kneel_one, dance_point, hand_to_shoulder, hug_self, arms_cros... |
| 13 | major | pen_frac | sleeves | 手捩.L (sleeve_cuff) | 16.2% in idol_dance@74 | idol_dance@74, hug_self, dance_point, hand_to_shoulder |
| 14 | major | cross | hair/skirt | hair x skirt (hair x skirt) | 2068 in jump_tuck | jump_tuck, spin@10, walk, idol_dance@71, run_l, walk@24, test, turn@19, side_bend, look_over_shoulder, dance_heart, head_right, torso_left, dance_point |
| 15 | major | pen_frac | accessories | 頭 (acc_leaves_L) | 13.0% in reach_up_back | reach_up_back, dance_heart, idol_dance@48 |
| 16 | major | self | body | body:forearm.L x thigh.L (body:forearm.L x thigh.L) | 4.7 in idol_dance@74 | idol_dance@74 |
| 17 | major | self | body | body:hand.L x thigh.L (body:hand.L x thigh.L) | 4.6 in idol_dance@74 | idol_dance@74 |
| 18 | major | pen_frac | hair_front | 頭 (hair_cheek_L) | 10.3% in reach_up_back | reach_up_back, idol_dance@81, dance_sway, idol_dance@45, dance_heart, idol_dance@48, arms_up, idol_dance@50 |
| 19 | major | pen_frac | hair_front | 横髪巻_1.L (hair_curl_L) | 10.3% in idol_dance@14 | idol_dance@14, dance_sway, jump_tuck, arms_up |
| 20 | major | pen_frac | petticoat | スカート9_0 (petticoat_core) | 8.9% in cross_legged | cross_legged, high_kick |
| 21 | major | pen | sleeves | 手捩.L (sleeve_cuff) | 4.3 in idol_dance@74 | idol_dance@74, hug_self, dance_point, hand_to_shoulder |
| 22 | major | self | body | body:hand.L x upperarm.R (body:hand.L x upperarm.R) | 3.5 in idol_dance@30 | idol_dance@30 |
| 23 | major | pen_frac | hair_front | 横髪奥_1.L (hair_curtain_L) | 7.8% in idol_dance@80 | idol_dance@80, dance_point, spin@6 |
| 24 | major | pen | petticoat | スカート11_2 (petticoat_tier1) | 3.5 in cross_legged | cross_legged |
| 25 | major | self | body | body:forearm.L x pelvis (body:forearm.L x pelvis) | 2.8 in idol_dance@75 | idol_dance@75 |
| 26 | major | vol | body | joint:shoulder.L (joint:shoulder.L) | 0.46 in idol_dance@79 | idol_dance@79, hands_behind_head, dance_sway, jump_tuck, dance_heart, hands_behind_back |
| 27 | major | pen_frac | petticoat | スカート11_2 (petticoat_tier1) | 5.8% in cross_legged | cross_legged |
| 28 | major | pen_frac | hair_front | 横髪奥_1.R (hair_curtain_R) | 5.7% in idol_dance@16 | idol_dance@16, dance_sway |
| 29 | major | pen_frac | hair_front | 横髪長_0.L (hair_lock_L) | 5.5% in idol_dance@81 | idol_dance@81, reach_up_back |
| 30 | major | self | body | body:hand.L x hand.R (body:hand.L x hand.R) | 2.5 in dance_heart | dance_heart, idol_dance@48, hands_behind_head, dance_clap |
| 31 | major | stretch | body | 足補助.L (body) | 2.38 in cross_legged | cross_legged, lie_back_elbows, sit_stand@58, sit_chair, jump_tuck |
| 32 | major | self | body | body:forearm.L x forearm.R (body:forearm.L x forearm.R) | 2.4 in arms_crossed | arms_crossed, hands_behind_back |
| 33 | major | pen_frac | shoes | 足首.L (shoes_shell) | 4.9% in seiza | seiza, squat |
| 34 | major | pen | petticoat | スカート9_0 (petticoat_core) | 2.7 in cross_legged | cross_legged, high_kick |
| 35 | major | pen_frac | hair_front | 横髪長_0.R (hair_lock_R) | 4.8% in reach_up_back | reach_up_back |
| 36 | major | jitter | hair_back | 後髪束2_2 (hair_back_side) | 0.12 in turn@16 | turn@16 |
| 37 | major | stretch | petticoat | スカート12_0 (petticoat_core) | 2.27 in cross_legged | cross_legged, high_kick, lie_back_elbows, kneel_one, sit_chair, sit_stand@36 |
| 38 | major | joint | body | joint:shoulder.L (joint:shoulder.L) | 0.60 in idol_dance@79 | idol_dance@79, jump_tuck, hands_behind_head, dance_sway, dance_heart, hands_behind_back |
| 39 | major | bone_pop | rig | ひざ補助.R (bones) | 8.4 in walk@11 | walk@11 |
| 40 | major | pop | body | ひざ補助2.R (body) | 8.3 in walk@41 | walk@41 |

## Issues by part (major / minor rows)

| part | major | minor |
|---|---|---|
| body | 42 | 146 |
| hair_front | 22 | 32 |
| hair/garment | 11 | 16 |
| sleeves | 10 | 69 |
| petticoat | 9 | 45 |
| accessories | 8 | 4 |
| rig | 5 | 1 |
| hair_back | 4 | 12 |
| hair/skirt | 3 | 11 |
| shoes | 2 | 10 |
| skirt | 1 | 31 |
| skirt/petticoat | 1 | 0 |
| bodice | 0 | 11 |
| head | 0 | 4 |
