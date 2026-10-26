# Motion test report

Model: 61 meshes, 104316 vertices, 102602 faces (without outlines). Run time 2067 s. Not gated: the exit code of rig_check covers the core poses only. No cloth or hair physics: chains move only as keyed or driven (MMD simulates them).

Thresholds (minor / major): stretch 1.60/2.00, compress 0.30/0.12, flip 10/100, pen 1.0/2.0, pen_frac 0.5%/3.0%, self 0.5/1.5, contact 3.0/6.0, cross 40/400, joint 0.85/0.70, vol 0.80/0.65, knee -0.5/-5.0, elbow -5.0/-15.0, pop 2.0/6.0, bone_pop 2.0/6.0, jitter 0.03/0.08, speed 12.00/20.00, eye 0.8/1.5, span 0.70/1.00.
Cells: plain = ok, *italic* = minor, **bold** = major (location, frame for clips). pen/self/contact in cm, pop in mm; joint = median skin radius ratio at the worst joint band, vol = its mean squared radius ratio; knee/elbow = least signed bend (negative = hyperextended).

## core

| name | stretch | compress | flip | pen cm | pen % | cross | joint | vol | knee | elbow | span |
|---|---|---|---|---|---|---|---|---|---|---|---|
| test | *1.66* (スカート0_2) | *0.16* (ひざ補助.L) | 7 | 0.4 | 0.0% | *130* (hair x skirt) | 0.95 | *0.74* (knee.L) | 59.8 | 69.2 | *0.96* (knee.L) |
| arms_up | *1.70* (上半身2) | *0.19* (袖_0.R) | 0 | 0.6 | 0.3% | **831** (hair x garment) | 0.93 | 0.86 | 0.0 | 41.5 | - |
| arms_forward | *1.69* (袖胴.R) | **0.07** (ひじ補助.L) | *80* (ひじ補助.L) | 0.5 | 0.0% | 0 | 0.98 | 0.99 | 0.0 | 139.4 | **1.70** (elbow.R) |
| wrist_twist_pos | 1.32 | 0.60 | 0 | 0.0 | 0.0% | 0 | 0.90 | 0.81 | 0.0 | 56.7 | - |
| wrist_twist_neg | 1.32 | 0.60 | 0 | 0.0 | 0.0% | 0 | 0.91 | 0.80 | 0.0 | 56.7 | - |
| squat | *1.66* (ひざ.L) | *0.17* (ひざ補助.R) | *24* (ひざ補助.L) | 0.8 | *2.3%* (ひざ.R) | 0 | 0.96 | *0.72* (knee.R) | 101.1 | 29.7 | *0.97* (knee.L) |
| walk | *1.74* (スカート0_2) | 0.52 | 0 | *1.7* (後髪束14_2) | 0.1% | **1330** (hair x garment) | 0.97 | 0.88 | 26.0 | 38.3 | - |
| head_left | 1.46 | 0.58 | 1 | 0.2 | 0.0% | *251* (hair x garment) | 0.99 | 0.97 | 0.0 | 29.7 | - |
| head_right | 1.46 | 0.58 | 0 | 0.2 | 0.0% | *249* (hair x garment) | 0.99 | 0.97 | 0.0 | 29.7 | - |
| torso_left | 1.51 | 0.61 | 1 | 0.0 | 0.0% | *86* (hair x skirt) | 0.99 | 0.98 | 0.0 | 29.7 | - |
| torso_right | 1.37 | 0.49 | 1 | 0.1 | 0.0% | 18 | 0.99 | 0.98 | 0.0 | 29.7 | - |
| swing | 1.54 | 0.77 | 1 | 0.0 | 0.0% | *201* (hair x skirt) | 1.00 | 1.00 | 0.0 | 29.7 | - |
| fist | *1.84* (手首.L) | 0.37 | 2 | 0.0 | 0.0% | 0 | 1.00 | 1.00 | 0.0 | 45.1 | - |
| raise_bend | 1.43 | 0.46 | 0 | 0.6 | 0.1% | *138* (hair x garment) | 0.99 | 1.00 | 0.0 | 69.2 | - |
| reach_forward | 1.56 | 0.31 | 0 | 0.0 | 0.0% | 0 | 0.98 | 0.98 | 0.0 | 95.3 | *0.86* (elbow.L) |
| forward_bend | 1.32 | 0.73 | 0 | 0.3 | 0.0% | 23 | 0.98 | 0.95 | 18.7 | 50.5 | - |
| side_bend | 1.42 | 0.58 | 0 | *1.6* (下半身) | *1.5%* (袖_0.L) | *152* (hair x skirt) | 0.99 | 0.98 | 0.0 | 29.7 | - |

## extended

| name | stretch | compress | flip | pen cm | pen % | self cm | contact cm | cross | joint | vol | knee | elbow | span |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| sit_chair | **2.14** (スカート5_1) | *0.16* (ひざ補助.R) | 1 | 0.7 | *1.4%* (スカート11_0) | - | - | 5 | 0.96 | *0.76* (knee.R) | 85.8 | 69.2 | *0.95* (knee.L) |
| seiza | *1.73* (スカート4_2) | *0.15* (ひざ補助.R) | *52* (ひざ補助.L) | *1.4* (足首.R) | *2.8%* (足首.R) | - | - | 0 | 0.97 | *0.65* (knee.R) | 143.6 | 65.0 | *0.98* (knee.R) |
| kneel_one | *1.90* (ひざ.R) | *0.13* (ひざ.R) | *17* (ひざ補助.R) | *1.0* (腕捩.R) | *1.1%* (ひざ.R) | - | 2.5 | 24 | 0.96 | *0.71* (knee.R) | 83.2 | 35.4 | **1.43** (elbow.L) |
| cross_legged | **2.47** (スカート14_1) | *0.15* (足補助.L) | *53* (ひざ補助.L) | **3.2** (スカート3_2) | **7.1%** (スカート11_1) | - | - | *106* (skirt x petticoat) | 0.96 | *0.67* (knee.L) | 124.7 | 52.7 | *0.98* (knee.L) |
| deep_lunge | *1.83* (スカート15_2) | *0.28* (ひざ補助.R) | 0 | 0.6 | 0.3% | - | - | 0 | 0.96 | 0.81 | 61.1 | 52.7 | *0.93* (knee.R) |
| run_l | *1.86* (スカート0_2) | *0.17* (ひざ補助.L) | *16* (ひざ補助.L) | *1.0* (後髪束14_2) | 0.1% | - | - | **1185** (hair x garment) | 0.96 | *0.69* (knee.L) | 16.1 | 95.3 | **1.03** (knee.L) |
| run_r | **2.10** (スカート14_1) | *0.17* (ひざ補助.R) | *16* (ひざ補助.R) | *1.1* (後髪束5_3) | 0.1% | **5.1** (thigh.L x thigh.R) | - | **1223** (hair x garment) | 0.96 | *0.69* (knee.R) | 16.1 | 95.3 | **1.03** (knee.R) |
| jump_tuck | **2.47** (スカート5_1) | *0.17* (ひざ補助.L) | *47* (ひざ補助.L) | 1.0 | *1.9%* (横髪巻_1.L) | - | - | **1482** (hair x skirt) | *0.80* (shoulder.L) | *0.67* (knee.L) | 129.7 | 45.1 | *0.98* (knee.R) |
| high_kick | *1.92* (スカート12_0) | *0.27* (足補助.L) | 0 | **2.3** (横髪巻_1.R) | **15.6%** (横髪巻_1.R) | - | *5.8* (pelvis x thigh.L) | 32 | 0.95 | 0.94 | 0.0 | 35.4 | - |
| arms_crossed | *1.67* (袖胴.L) | *0.15* (ひじ補助.L) | 0 | *1.1* (袖胴.R) | 0.4% | **4.3** (forearm.L x forearm.R) | *4.7* (forearm.L x hand.R) | 0 | 0.97 | 0.99 | 0.0 | 109.2 | **1.67** (elbow.R) |
| hands_behind_head | *1.81* (袖胴.L) | *0.12* (ひじ補助.L) | *20* (袖_0.L) | *1.0* (頭) | *0.7%* (横髪奥_1.L) | *1.1* (hand.L x hand.R) | - | **4522** (hair x garment) | *0.81* (shoulder.R) | **0.64** (shoulder.L) | 0.0 | 136.4 | **1.70** (elbow.R) |
| hands_behind_back | *1.66* (肩.R) | *0.24* (ひじ補助.L) | 0 | *1.4* (手捩.R) | *2.5%* (手捩.R) | *1.2* (forearm.L x forearm.R) | - | **938** (hair x garment) | *0.84* (shoulder.R) | *0.73* (shoulder.R) | 0.0 | 99.6 | *0.85* (elbow.R) |
| hand_to_shoulder | *1.66* (袖胴.L) | *0.19* (腕捩.L) | 0 | *1.0* (腕捩.R) | *1.1%* (手捩.L) | - | - | *49* (hair x garment) | 0.96 | 0.94 | 0.0 | 32.9 | **1.01** (elbow.L) |
| hands_on_hips | 1.55 | 0.35 | 0 | *1.1* (スカート12_0) | 0.1% | - | - | *113* (hair x garment) | 0.92 | 0.89 | 0.0 | 86.6 | **1.94** (elbow.L) |
| reach_up_back | *1.79* (上半身2) | *0.23* (袖胴.R) | *15* (袖_0.L) | *1.5* (頭) | **13.0%** (頭) | 0.4 | - | **4325** (hair x garment) | 0.92 | 0.82 | 0.0 | 32.9 | - |
| hug_self | *1.76* (肩補助2.L) | *0.21* (ひじ補助.L) | 0 | **2.5** (手捩.L) | **13.1%** (手捩.L) | **1.9** (hand.R x upperarm.L) | - | 24 | 0.96 | 1.00 | 0.0 | 110.9 | **1.01** (elbow.L) |
| twist_bend | *1.60* (スカート7_0) | 0.57 | 1 | *1.7* (下半身) | *2.5%* (腕捩.L) | - | - | 0 | 0.98 | 0.92 | 20.7 | 29.7 | - |
| lie_back_elbows | **2.22** (スカート5_1) | *0.14* (ひじ補助.R) | 2 | *1.4* (下半身) | *1.1%* (下半身) | - | - | *42* (hair x garment) | 0.98 | 0.96 | 8.0 | 99.6 | *0.89* (elbow.R) |
| look_over_shoulder | 1.53 | 0.59 | 1 | *1.9* (後髪0_1) | *1.1%* (後髪0_1) | - | - | *366* (hair x garment) | 0.98 | 0.96 | 0.0 | 38.3 | - |
| curtsy | 1.51 | 0.37 | 1 | 0.3 | 0.0% | - | - | 19 | 0.96 | 0.84 | 51.4 | 39.6 | *0.87* (knee.L) |
| dance_sway | *1.85* (上半身2) | *0.26* (袖_0.L) | *24* (袖_0.L) | *1.6* (横髪巻_1.L) | **5.3%** (横髪巻_1.L) | - | - | **1271** (hair x garment) | *0.84* (shoulder.L) | *0.66* (shoulder.L) | 33.6 | 41.5 | **2.02** (elbow.R) |
| dance_point | *1.76* (袖胴.L) | *0.14* (ひじ補助.L) | 1 | **2.3** (手捩.L) | **7.8%** (横髪奥_1.L) | - | - | *57* (hair x garment) | 0.87 | *0.75* (shoulder.R) | 33.9 | 32.9 | **1.05** (elbow.L) |
| dance_heart | *1.78* (上半身2) | *0.27* (ひじ補助.R) | 2 | *1.3* (頭) | **6.6%** (頭) | **1.6** (hand.L x hand.R) | *5.0* (forearm.L x hand.R) | **3035** (hair x garment) | *0.84* (shoulder.L) | *0.73* (shoulder.R) | 28.8 | 108.3 | **1.65** (elbow.L) |
| dance_clap | 1.59 | *0.24* (ひじ補助.L) | 0 | 0.8 | *0.8%* (手捩.R) | *1.1* (hand.L x hand.R) | - | 14 | 0.90 | 0.81 | 63.9 | 108.3 | **1.65** (elbow.L) |

## motion

| name | stretch | compress | flip | pen cm | pen % | self cm | contact cm | cross | joint | vol | knee | elbow | span | pop mm | bone pop mm | jitter | speed m/s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| walk | *1.65* (スカート15_2) | 0.41 | 1 | *1.1* (腕捩.R) | *1.8%* (腕捩.R) | - | - | *282* (hair x skirt) | 0.97 | 0.85 | 22.2 | 37.1 | *0.87* (knee.L) | **7.8** (ひざ補助2.R, f31) | **7.9** (ひざ補助.R, f11) | *0.05* (スカート15_2) | 1.22 |
| run | **2.20** (スカート14_2, f8) | *0.16* (ひざ補助.L) | *23* (ひざ補助.R) | *1.6* (後髪束14_2) | *1.9%* (ひざ.R) | - | *5.9* (pelvis x thigh.L) | **1228** (hair x garment, f18) | 0.96 | *0.66* (knee.L) | 28.0 | 86.6 | **1.87** (elbow.L, f18) | **86.2** (スカート2_2, f6) | **78.7** (スカート1_2, f6) | **0.43** (スカート5_1, f6) | 3.60 |
| turn | 1.41 | 0.38 | 1 | 0.8 | *0.7%* (横髪奥_1.R) | *1.2* (foot.L x foot.R) | - | *114* (hair x garment) | 0.96 | 0.84 | 28.6 | 45.1 | *0.87* (knee.L) | *5.7* (ひざ補助2.R) | *5.3* (ひざ補助.R) | 0.03 | 1.62 |
| sit_stand | **2.14** (スカート5_1, f36) | *0.16* (ひざ補助.R) | 4 | *1.7* (スカート13_0) | *2.4%* (スカート11_0) | - | - | 4 | 0.96 | *0.75* (knee.R) | 0.0 | 35.4 | *0.95* (knee.L) | *4.8* (後髪束8_4) | *4.3* (後髪束8_4) | *0.04* (スカート5_1) | 0.81 |
| spin | **2.08** (スカート15_2, f28) | 0.54 | 2 | **2.4** (横髪巻_2.R, f4) | **20.9%** (横髪巻_2.R, f4) | - | - | **1083** (hair x skirt, f9) | 0.94 | 0.89 | 22.8 | 35.4 | - | **20.0** (後髪束7_4, f40) | **17.9** (後髪束7_4, f40) | *0.03* (後髪束11_3) | 3.93 |
| idol_dance | *1.97* (上半身2) | **0.09** (肩補助3.L, f79) | *56* (袖_0.L) | **4.3** (手捩.L, f74) | **15.5%** (手捩.L, f74) | **4.9** (hand.L x pelvis, f75) | *5.2* (forearm.R x hand.L) | **4470** (hair x garment, f77) | **0.60** (shoulder.L, f79) | **0.45** (shoulder.L, f79) | 0.0 | 29.7 | **3.02** (elbow.R, f14) | **53.9** (横髪巻_2.R, f15) | **49.9** (横髪巻_2.R, f15) | **0.74** (腕D.L, f78) | 6.65 |

## eyes (gaze at the limits x eye morphs)

| case | poke mm | where |
|---|---|---|
| gaze | 1.36 (minor) | head_eye_L gaze +10/+8 |
| gaze+まばたき | 0.00 (ok) | eyes  |
| gaze+まばたき=0.5 | 1.46 (minor) | head_eye_hilite_R gaze +0/-8 |
| gaze+ウィンク | 1.36 (minor) | head_eye_R gaze -10/+8 |
| gaze+ウィンク右 | 1.36 (minor) | head_eye_L gaze +10/+8 |
| gaze+笑い | 0.42 (ok) | head_eye_L gaze +10/+8 |
| gaze+はぅ | 0.01 (ok) | head_eye_R gaze -10/+8 |
| gaze+はぅ=0.5 | 1.48 (minor) | head_eye_L gaze +10/+8 |
| gaze+なごみ | 0.00 (ok) | eyes  |
| gaze+びっくり | 0.00 (ok) | eyes  |
| gaze+じと目 | 0.00 (ok) | eyes  |
| gaze+キリッ | 0.00 (ok) | eyes  |
| gaze+瞳小 | 1.36 (minor) | head_eye_L gaze +10/+8 |
| gaze+ハイライト消 | 1.36 (minor) | head_eye_L gaze +10/+8 |
| gaze+真面目 | 1.36 (minor) | head_eye_L gaze +10/+8 |
| gaze+困る | 1.36 (minor) | head_eye_L gaze +10/+8 |
| gaze+にこり | 1.36 (minor) | head_eye_L gaze +10/+8 |
| gaze+怒り | 1.36 (minor) | head_eye_L gaze +10/+8 |
| gaze+上 | 1.36 (minor) | head_eye_L gaze +10/+8 |
| gaze+下 | 1.36 (minor) | head_eye_L gaze +10/+8 |

## Top problems (grouped by metric, part and location)

| # | level | metric | part | location | worst | in |
|---|---|---|---|---|---|---|
| 1 | major | pop | petticoat | スカート2_2 (petticoat_tier1) | 86.2 in run@6 | run@6 |
| 2 | major | bone_pop | rig | スカート1_2 (bones) | 78.7 in run@6 | run@6 |
| 3 | major | jitter | body | 腕D.L (body) | 0.74 in idol_dance@78 | idol_dance@78 |
| 4 | major | pop | hair_front | 横髪巻_2.R (hair_curl_R) | 53.9 in idol_dance@15 | idol_dance@15 |
| 5 | major | cross | hair/garment | hair x garment (hair x garment) | 4522 in hands_behind_head | hands_behind_head, idol_dance@77, reach_up_back, dance_heart, walk, dance_sway, run@18, run_r, run_l, hands_behind_back, arms_up, look_over_shoulder, head_le... |
| 6 | major | bone_pop | rig | 横髪巻_2.R (bones) | 49.9 in idol_dance@15 | idol_dance@15 |
| 7 | major | pen_frac | hair_front | 横髪巻_2.R (hair_curl_R) | 20.9% in spin@4 | spin@4 |
| 8 | major | jitter | skirt | スカート5_1 (skirt) | 0.43 in run@6 | run@6, sit_stand@68 |
| 9 | major | span | body | elbow.R (span:elbow.R) | 3.02 in idol_dance@14 | idol_dance@14, dance_sway, hands_on_hips, run@8, hands_behind_head, arms_forward, arms_crossed, dance_heart, dance_clap, hug_self, lie_back_elbows, reach_for... |
| 10 | major | pen_frac | hair_front | 横髪巻_1.R (hair_curl_R) | 15.6% in high_kick | high_kick, idol_dance@51, jump_tuck |
| 11 | major | pen_frac | sleeves | 手捩.L (sleeve_cuff) | 15.5% in idol_dance@74 | idol_dance@74, hug_self, dance_point, hand_to_shoulder |
| 12 | major | span | body | elbow.L (span:elbow.L) | 2.29 in idol_dance@55 | idol_dance@55, hands_on_hips, run@18, hands_behind_head, arms_forward, dance_heart, dance_clap, kneel_one, dance_point, hug_self, hand_to_shoulder, arms_cros... |
| 13 | major | pen_frac | accessories | 頭 (acc_leaves_L) | 13.0% in reach_up_back | reach_up_back, dance_heart, idol_dance@48 |
| 14 | major | self | body | body:thigh.L x thigh.R (body:thigh.L x thigh.R) | 5.1 in run_r | run_r |
| 15 | major | pop | hair_back | 後髪束7_4 (hair_back) | 20.0 in spin@40 | spin@40 |
| 16 | major | self | body | body:hand.L x pelvis (body:hand.L x pelvis) | 4.9 in idol_dance@75 | idol_dance@75 |
| 17 | major | pen_frac | hair_front | 横髪巻_1.L (hair_curl_L) | 10.9% in idol_dance@53 | idol_dance@53, dance_sway, jump_tuck |
| 18 | major | self | body | body:forearm.L x thigh.L (body:forearm.L x thigh.L) | 4.6 in idol_dance@74 | idol_dance@74 |
| 19 | major | cross | hair/skirt | hair x skirt (hair x skirt) | 1482 in jump_tuck | jump_tuck, spin@9, run_l, idol_dance@72, walk, walk@0, look_over_shoulder, swing, side_bend, head_right, test, dance_heart, turn@10, torso_left |
| 20 | major | bone_pop | rig | 後髪束7_4 (bones) | 17.9 in spin@40 | spin@40 |
| 21 | major | self | body | body:hand.L x thigh.L (body:hand.L x thigh.L) | 4.4 in idol_dance@75 | idol_dance@75 |
| 22 | major | self | body | body:forearm.L x forearm.R (body:forearm.L x forearm.R) | 4.3 in arms_crossed | arms_crossed, hands_behind_back |
| 23 | major | pen | sleeves | 手捩.L (sleeve_cuff) | 4.3 in idol_dance@74 | idol_dance@74, hug_self, dance_point, hand_to_shoulder |
| 24 | major | pen_frac | hair_front | 横髪奥_1.L (hair_curtain_L) | 7.8% in dance_point | dance_point, idol_dance@23, hands_behind_head, spin@14 |
| 25 | major | self | body | body:hand.L x upperarm.R (body:hand.L x upperarm.R) | 3.3 in idol_dance@30 | idol_dance@30 |
| 26 | major | pen_frac | petticoat | スカート11_1 (petticoat_core) | 7.1% in cross_legged | cross_legged |
| 27 | major | pen_frac | petticoat | スカート3_2 (petticoat_tier1) | 6.7% in cross_legged | cross_legged |
| 28 | major | vol | body | joint:shoulder.L (joint:shoulder.L) | 0.45 in idol_dance@79 | idol_dance@79, hands_behind_head, dance_sway, jump_tuck, dance_heart, hands_behind_back |
| 29 | major | pen | petticoat | スカート3_2 (petticoat_tier1) | 3.2 in cross_legged | cross_legged, sit_stand@62 |
| 30 | major | stretch | skirt | スカート14_1 (skirt) | 2.47 in cross_legged | cross_legged, run@7, run_r |
| 31 | major | stretch | skirt | スカート5_1 (skirt) | 2.47 in jump_tuck | jump_tuck, lie_back_elbows, sit_chair, sit_stand@36, seiza |
| 32 | major | self | body | body:forearm.L x pelvis (body:forearm.L x pelvis) | 2.7 in idol_dance@74 | idol_dance@74 |
| 33 | major | stretch | body | 足補助.L (body) | 2.40 in cross_legged | cross_legged, lie_back_elbows, sit_chair, sit_stand@58, jump_tuck |
| 34 | major | pen_frac | hair_front | 横髪長_0.L (hair_lock_L) | 5.3% in idol_dance@81 | idol_dance@81, reach_up_back |
| 35 | major | pen | petticoat | スカート11_1 (petticoat_core) | 2.9 in cross_legged | cross_legged |
| 36 | major | span | body | knee.L (span:knee.L) | 1.21 in idol_dance@69 | idol_dance@69, run@16, run_l, seiza, cross_legged, jump_tuck, squat, test, sit_stand@29, sit_chair, kneel_one, dance_clap, deep_lunge, curtsy, turn@30, dance... |
| 37 | major | span | body | knee.R (span:knee.R) | 1.20 in kneel_one | kneel_one, run@6, run_r, seiza, cross_legged, jump_tuck, squat, sit_stand@64, sit_chair, deep_lunge, test, dance_clap, idol_dance@36, dance_sway, turn@17, wa... |
| 38 | major | joint | body | joint:shoulder.L (joint:shoulder.L) | 0.60 in idol_dance@79 | idol_dance@79, jump_tuck, hands_behind_head, dance_sway, dance_heart, hands_behind_back |
| 39 | major | pen_frac | hair_front | 横髪長_0.R (hair_lock_R) | 4.7% in reach_up_back | reach_up_back |
| 40 | major | stretch | petticoat | スカート14_2 (petticoat_tier1) | 2.20 in run@8 | run@8, run_r |

## Issues by part (major / minor rows)

| part | major | minor |
|---|---|---|
| body | 44 | 137 |
| hair_front | 16 | 29 |
| hair/garment | 11 | 14 |
| petticoat | 10 | 49 |
| sleeves | 8 | 78 |
| skirt | 8 | 22 |
| accessories | 8 | 6 |
| hair/skirt | 5 | 9 |
| rig | 4 | 2 |
| hair_back | 1 | 14 |
| head | 0 | 13 |
| bodice | 0 | 12 |
| shoes | 0 | 6 |
| skirt/petticoat | 0 | 1 |
