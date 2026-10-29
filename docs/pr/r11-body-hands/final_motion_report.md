# Motion test report

Model: 61 meshes, 114110 vertices, 112338 faces (without outlines). Run time 2093 s. Not gated: the exit code of rig_check covers the core poses only. No cloth or hair physics: chains move only as keyed or driven (MMD simulates them).

Thresholds (minor / major): stretch 1.60/2.00, compress 0.30/0.12, flip 10/100, pen 1.0/2.0, pen_frac 0.5%/3.0%, self 0.5/1.5, contact 3.0/6.0, cross 40/400, joint 0.85/0.70, vol 0.80/0.65, knee -0.5/-5.0, elbow -5.0/-15.0, pop 2.0/6.0, bone_pop 2.0/6.0, jitter 0.03/0.08, speed 12.00/20.00, eye 0.8/1.5, span 0.70/1.00.
Cells: plain = ok, *italic* = minor, **bold** = major (location, frame for clips). pen/self/contact in cm, pop in mm; joint = median skin radius ratio at the worst joint band, vol = its mean squared radius ratio; knee/elbow = least signed bend (negative = hyperextended).

## core

| name | stretch | compress | flip | pen cm | pen % | contact cm | cross | joint | vol | knee | elbow | span |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| test | *1.83* (スカート12_2) | **0.09** (足.L) | 8 | 0.3 | 0.0% | 0.2 | *332* (hair x skirt) | 0.97 | 0.80 | 59.8 | 69.3 | 0.58 |
| arms_up | *1.81* (腕捩.L) | *0.28* (袖_0.R) | 2 | 0.6 | 0.1% | - | **787** (hair x garment) | 0.93 | 0.86 | 0.0 | 41.4 | - |
| arms_forward | *1.80* (腕捩.L) | **0.06** (ひじ補助.L) | *38* (ひじ補助.L) | 0.4 | 0.0% | - | 0 | 0.98 | 0.99 | 0.0 | 139.4 | **1.31** (elbow.L) |
| wrist_twist_pos | 1.33 | 0.61 | 0 | 0.0 | 0.0% | - | 0 | 0.90 | 0.82 | 0.0 | 56.7 | - |
| wrist_twist_neg | 1.33 | 0.61 | 0 | 0.0 | 0.0% | - | 0 | 0.90 | 0.82 | 0.0 | 56.7 | - |
| squat | *1.85* (足.R) | **0.07** (足.L) | *26* (足.L) | *1.0* (ひざ.L) | **3.4%** (ひざ.L) | 2.9 | **408** (hair x skirt) | 0.97 | *0.77* (knee.L) | 106.4 | 29.3 | 0.61 |
| walk | *1.74* (スカート12_2) | 0.50 | 3 | *1.7* (後髪束12_2) | 0.1% | - | **1202** (hair x garment) | 0.99 | 0.92 | 30.7 | 38.1 | - |
| head_left | 1.46 | 0.56 | 1 | 0.2 | 0.0% | - | *188* (hair x garment) | 0.99 | 0.97 | 0.0 | 29.3 | - |
| head_right | 1.46 | 0.56 | 3 | 0.2 | 0.0% | - | *193* (hair x garment) | 0.99 | 0.97 | 0.0 | 29.3 | - |
| torso_left | 1.33 | 0.63 | 2 | 0.0 | 0.0% | - | 17 | 0.99 | 0.98 | 0.0 | 29.3 | - |
| torso_right | 1.38 | 0.69 | 3 | 0.1 | 0.0% | - | *46* (hair x skirt) | 0.99 | 0.98 | 0.0 | 29.3 | - |
| swing | 1.51 | 0.77 | 0 | 0.0 | 0.0% | - | *154* (hair x skirt) | 1.00 | 1.00 | 0.0 | 29.3 | - |
| fist | 1.53 | *0.12* (中指１.L) | 4 | 0.0 | 0.0% | - | 0 | 1.00 | 1.00 | 0.0 | 45.0 | - |
| raise_bend | 1.46 | 0.49 | 0 | 0.6 | 0.1% | - | 24 | 0.99 | 1.00 | 0.0 | 69.3 | - |
| reach_forward | 1.60 | 0.32 | 0 | 0.0 | 0.0% | - | 0 | 0.99 | 0.98 | 0.0 | 95.5 | **1.36** (elbow.L) |
| forward_bend | 1.41 | 0.71 | 2 | 0.2 | 0.0% | - | *96* (hair x skirt) | 1.00 | 0.97 | 23.2 | 50.3 | - |
| side_bend | 1.48 | 0.65 | 2 | *1.8* (下半身) | *0.6%* (ひじ補助.L) | - | *278* (hair x skirt) | 0.99 | 0.98 | 0.0 | 29.3 | - |

## extended

| name | stretch | compress | flip | pen cm | pen % | self cm | contact cm | cross | joint | vol | knee | elbow | span |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| sit_chair | **2.16** (スカート5_1) | **0.10** (足.L) | 9 | 0.8 | *2.1%* (スカート4_0) | - | 0.1 | 9 | 0.97 | 0.82 | 91.0 | 69.3 | 0.56 |
| seiza | *1.78* (足.R) | **0.06** (足.R) | 10 | *1.1* (足首.R) | *1.7%* (足首.R) | - | *3.3* (shin.R x thigh.R) | 0 | 0.89 | **0.64** (knee.R) | 150.0 | 65.0 | 0.69 |
| kneel_one | *1.93* (ひざ.R) | **0.09** (足.R) | *19* (足.R) | *1.0* (腕捩.R) | *1.2%* (ひざ.R) | - | 2.6 | 17 | 0.96 | *0.75* (ankle.R) | 88.3 | 35.2 | **1.32** (elbow.L) |
| cross_legged | **2.62** (足補助.R) | **0.04** (足.R) | *48* (足補助.L) | **3.4** (スカート11_1) | **8.0%** (スカート11_1) | **3.6** (thigh.L x thigh.R) | *4.0* (pelvis x thigh.L) | *214* (skirt x petticoat) | 0.96 | *0.70* (knee.L) | 124.7 | 52.7 | 0.65 |
| deep_lunge | *1.90* (スカート12_2) | *0.25* (足.R) | 1 | 0.6 | *0.7%* (スカート11_0) | - | - | 0 | 0.98 | 0.86 | 66.2 | 52.7 | 0.51 |
| run_l | *1.86* (足.L) | **0.05** (足.L) | 10 | *1.3* (スカート13_0) | 0.2% | - | 1.5 | **1059** (hair x garment) | 0.96 | *0.72* (knee.L) | 17.6 | 95.5 | **1.32** (elbow.R) |
| run_r | **2.17** (スカート15_2) | **0.05** (足.R) | 10 | *1.0* (後髪束3_2) | 0.2% | **4.5** (thigh.L x thigh.R) | *4.9* (pelvis x thigh.R) | **864** (hair x garment) | 0.96 | *0.72* (knee.R) | 17.6 | 95.5 | **1.32** (elbow.L) |
| jump_tuck | **2.21** (スカート0_0) | **0.09** (足.L) | *32* (下半身) | *1.6* (横髪巻_1.L) | **7.8%** (横髪巻_1.L) | - | 2.7 | **1720** (hair x skirt) | *0.80* (shoulder.L) | *0.66* (knee.L) | 134.9 | 45.0 | 0.67 |
| high_kick | **2.17** (スカート15_2) | *0.22* (足補助.L) | 0 | 0.8 | *1.4%* (スカート10_0) | - | *5.6* (pelvis x thigh.L) | 0 | 0.95 | 0.93 | -0.0 | 35.2 | - |
| arms_crossed | *1.69* (袖胴.L) | *0.21* (ひじ補助.L) | 0 | *1.3* (袖胴.R) | *1.2%* (手捩.L) | **2.9** (forearm.L x forearm.R) | *3.6* (forearm.L x hand.R) | 0 | 0.97 | 0.99 | 0.0 | 109.4 | **1.27** (elbow.R) |
| hands_behind_head | *1.87* (袖胴.R) | *0.14* (ひじ補助.R) | *12* (袖_0.L) | *1.2* (頭) | *0.7%* (横髪奥_1.L) | *1.3* (hand.L x hand.R) | *4.6* (forearm.R x hand.L) | **5735** (hair x garment) | *0.80* (shoulder.R) | **0.63** (shoulder.R) | 0.0 | 136.8 | **1.15** (elbow.L) |
| hands_behind_back | *1.66* (肩補助2.L) | 0.32 | 0 | *1.2* (袖胴.R) | *2.7%* (手捩.L) | *1.1* (forearm.L x forearm.R) | - | **1122** (hair x garment) | *0.85* (shoulder.R) | *0.73* (shoulder.L) | 0.0 | 99.9 | **1.28** (elbow.L) |
| hand_to_shoulder | *1.74* (袖胴.L) | *0.18* (腕捩.L) | 0 | *1.5* (手捩.L) | *1.2%* (手捩.L) | - | - | *73* (hair x garment) | 0.96 | 0.94 | 0.0 | 32.6 | **1.16** (elbow.L) |
| hands_on_hips | 1.51 | 0.36 | 0 | 0.8 | 0.0% | - | - | 0 | 0.92 | 0.87 | 0.0 | 86.7 | **1.23** (elbow.R) |
| reach_up_back | *1.88* (ひじ補助.R) | 0.34 | 4 | *1.4* (頭) | **12.3%** (頭) | 0.4 | - | **4219** (hair x garment) | 0.92 | 0.82 | 0.0 | 32.6 | - |
| hug_self | *1.76* (肩補助2.L) | *0.24* (ひじ補助.L) | 0 | **2.9** (手捩.L) | **12.8%** (手捩.L) | **2.0** (hand.R x upperarm.L) | *3.6* (forearm.R x upperarm.L) | 28 | 0.96 | 1.00 | 0.0 | 111.1 | **1.26** (elbow.L) |
| twist_bend | 1.37 | 0.66 | 2 | *1.7* (下半身) | *2.2%* (腕捩.L) | - | - | *44* (hair x garment) | 0.98 | 0.93 | 25.3 | 29.3 | - |
| lie_back_elbows | **2.64** (スカート6_1) | *0.20* (下半身) | 2 | *1.2* (スカート2_0) | *1.2%* (スカート2_0) | - | - | *71* (hair x garment) | 0.98 | 0.95 | 8.0 | 99.9 | **1.25** (elbow.L) |
| look_over_shoulder | 1.49 | 0.61 | 4 | **2.0** (後髪0_1) | *1.3%* (後髪0_1) | - | - | *378* (hair x garment) | 0.98 | 0.96 | 0.0 | 38.1 | - |
| curtsy | *1.65* (足.L) | 0.33 | 0 | 0.2 | 0.0% | - | - | 31 | 0.97 | 0.88 | 55.7 | 39.4 | 0.48 |
| dance_sway | *1.82* (腕捩.L) | 0.31 | *13* (袖_0.L) | *1.1* (横髪巻_1.L) | *2.8%* (横髪長_1.L) | - | - | **1081** (hair x garment) | *0.84* (shoulder.L) | **0.65** (shoulder.L) | 38.4 | 41.4 | **1.22** (elbow.R) |
| dance_point | *1.83* (ひじ補助.R) | *0.16* (ひじ補助.L) | 3 | **2.6** (手捩.L) | **7.8%** (横髪奥_1.L) | - | - | *90* (hair x garment) | 0.87 | *0.74* (shoulder.R) | 38.8 | 32.6 | **1.27** (elbow.L) |
| dance_heart | *1.79* (腕捩.L) | 0.31 | 2 | *1.3* (頭) | **9.2%** (頭) | **1.7** (hand.L x hand.R) | *3.5* (forearm.R x hand.L) | **3809** (hair x garment) | *0.84* (shoulder.L) | *0.71* (shoulder.L) | 33.5 | 108.5 | **1.31** (elbow.L) |
| dance_clap | *1.70* (足.L) | *0.26* (足.R) | 1 | 0.7 | *0.6%* (手捩.R) | **2.5** (forearm.L x forearm.R) | *3.0* (forearm.L x hand.R) | 28 | 0.90 | 0.82 | 69.0 | 108.5 | **1.31** (elbow.L) |

## motion

| name | stretch | compress | flip | pen cm | pen % | self cm | contact cm | cross | joint | vol | knee | elbow | span | pop mm | bone pop mm | jitter | speed m/s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| walk | *1.62* (足.L) | 0.39 | 3 | *1.4* (スカート12_1) | *1.7%* (腕捩.R) | - | - | *240* (hair x garment) | 0.99 | 0.89 | 26.9 | 36.9 | 0.47 | **8.2** (スカート15_2, f50) | **7.7** (中指３.L, f7) | *0.05* (スカート15_2) | 1.22 |
| run | **2.30** (スカート15_2, f7) | **0.05** (足.R, f2) | *11* (足.R) | *1.6* (後髪束3_2) | *1.3%* (ひざ.R) | **4.6** (thigh.L x thigh.R, f7) | *5.8* (pelvis x thigh.L) | **1168** (hair x garment, f18) | 0.92 | *0.65* (knee.L) | 31.9 | 86.7 | **1.33** (elbow.L, f8) | **68.5** (スカート14_2, f16) | **59.3** (スカート14_2, f16) | **0.56** (スカート2_1, f4) | 4.84 |
| turn | *1.65* (足.L) | 0.35 | 2 | 0.8 | *0.7%* (横髪奥_1.R) | *1.3* (foot.L x foot.R) | - | *139* (hair x garment) | 0.99 | 0.89 | 33.4 | 45.0 | 0.48 | *5.8* (ひざ.R) | *5.2* (足.R) | 0.03 | 1.62 |
| sit_stand | **2.26** (スカート0_0, f60) | **0.09** (足.L, f64) | 10 | *1.7* (スカート13_0) | *2.6%* (スカート11_0) | - | 0.1 | 6 | 0.97 | 0.81 | 0.0 | 35.2 | 0.57 | **10.3** (スカート2_2, f69) | **10.3** (スカート2_2, f69) | *0.06* (スカート1_2) | 0.84 |
| spin | *1.99* (スカート0_1) | 0.52 | 2 | 0.8 | *0.7%* (横髪奥_1.L) | - | - | **1352** (hair x skirt, f16) | 0.95 | 0.93 | 27.2 | 35.2 | - | **8.1** (後髪束11_4, f37) | **7.0** (横髪長_2.L, f3) | *0.04* (後髪束11_4) | 3.92 |
| idol_dance | *1.92* (上半身2) | **0.05** (足.L, f72) | *49* (袖_0.L) | **5.2** (手捩.L, f74) | **16.3%** (手捩.L, f74) | **4.8** (hand.L x thigh.R, f75) | *4.7* (forearm.L x hand.R) | **4572** (hair x garment, f77) | **0.58** (shoulder.L, f79) | **0.44** (shoulder.L, f79) | 0.0 | 29.3 | **1.59** (elbow.R, f33) | **54.8** (ひざ.L, f60) | **53.8** (ひざ.L, f60) | **0.70** (腕D.L, f78) | 6.59 |

## eyes (gaze at the limits x eye morphs)

| case | poke mm | where |
|---|---|---|
| gaze | 1.38 (minor) | head_eye_R gaze -10/+8 |
| gaze+まばたき | 0.00 (ok) | eyes  |
| gaze+まばたき=0.5 | 1.44 (minor) | head_eye_hilite_L gaze +0/-8 |
| gaze+ウィンク | 1.38 (minor) | head_eye_R gaze -10/+8 |
| gaze+ウィンク右 | 1.38 (minor) | head_eye_L gaze +10/+8 |
| gaze+笑い | 0.52 (ok) | head_eye_L gaze +10/+8 |
| gaze+はぅ | 0.00 (ok) | eyes  |
| gaze+はぅ=0.5 | 1.48 (minor) | head_eye_R gaze -10/+8 |
| gaze+なごみ | 0.00 (ok) | eyes  |
| gaze+びっくり | 0.00 (ok) | eyes  |
| gaze+じと目 | 0.00 (ok) | eyes  |
| gaze+キリッ | 0.00 (ok) | eyes  |
| gaze+瞳小 | 1.38 (minor) | head_eye_R gaze -10/+8 |
| gaze+ハイライト消 | 1.38 (minor) | head_eye_R gaze -10/+8 |
| gaze+真面目 | 1.38 (minor) | head_eye_R gaze -10/+8 |
| gaze+困る | 1.38 (minor) | head_eye_R gaze -10/+8 |
| gaze+にこり | 1.38 (minor) | head_eye_R gaze -10/+8 |
| gaze+怒り | 1.38 (minor) | head_eye_R gaze -10/+8 |
| gaze+上 | 1.38 (minor) | head_eye_R gaze -10/+8 |
| gaze+下 | 1.38 (minor) | head_eye_R gaze -10/+8 |

## Top problems (grouped by metric, part and location)

| # | level | metric | part | location | worst | in |
|---|---|---|---|---|---|---|
| 1 | major | pop | petticoat | スカート14_2 (petticoat_tier0) | 68.5 in run@16 | run@16 |
| 2 | major | cross | hair/garment | hair x garment (hair x garment) | 5735 in hands_behind_head | hands_behind_head, idol_dance@77, reach_up_back, dance_heart, walk, run@18, hands_behind_back, dance_sway, run_l, run_r, arms_up, look_over_shoulder, walk@0,... |
| 3 | major | bone_pop | rig | スカート14_2 (bones) | 59.3 in run@16 | run@16 |
| 4 | major | jitter | body | 腕D.L (body) | 0.70 in idol_dance@78 | idol_dance@78 |
| 5 | major | pop | body | ひざ.L (body) | 54.8 in idol_dance@60 | idol_dance@60 |
| 6 | major | bone_pop | rig | ひざ.L (bones) | 53.8 in idol_dance@60 | idol_dance@60 |
| 7 | major | jitter | skirt | スカート2_1 (skirt) | 0.56 in run@4 | run@4 |
| 8 | major | pen_frac | sleeves | 手捩.L (sleeve_cuff) | 16.3% in idol_dance@74 | idol_dance@74, hug_self, dance_point, hands_behind_back, hand_to_shoulder, arms_crossed |
| 9 | major | pen_frac | hair_front | 横髪巻_1.L (hair_curl_L) | 12.8% in idol_dance@54 | idol_dance@54, jump_tuck, dance_sway |
| 10 | major | pen_frac | accessories | 頭 (acc_leaves_L) | 12.3% in reach_up_back | reach_up_back, dance_heart, idol_dance@48 |
| 11 | major | cross | hair/skirt | hair x skirt (hair x skirt) | 1720 in jump_tuck | jump_tuck, spin@16, squat, test, side_bend, swing, head_right, forward_bend, dance_heart, idol_dance@48, run_l, torso_right |
| 12 | major | self | body | body:hand.L x thigh.R (body:hand.L x thigh.R) | 4.8 in idol_dance@75 | idol_dance@75 |
| 13 | major | pen | sleeves | 手捩.L (sleeve_cuff) | 5.2 in idol_dance@74 | idol_dance@74, hug_self, dance_point, hand_to_shoulder, hands_behind_back |
| 14 | major | self | body | body:forearm.L x thigh.L (body:forearm.L x thigh.L) | 4.7 in idol_dance@74 | idol_dance@74 |
| 15 | major | self | body | body:thigh.L x thigh.R (body:thigh.L x thigh.R) | 4.6 in run@7 | run@7, run_r, cross_legged |
| 16 | major | self | body | body:hand.L x thigh.L (body:hand.L x thigh.L) | 4.0 in idol_dance@75 | idol_dance@75 |
| 17 | major | self | body | body:hand.L x upperarm.R (body:hand.L x upperarm.R) | 4.0 in idol_dance@30 | idol_dance@30 |
| 18 | major | pen_frac | hair_front | 横髪巻_1.R (hair_curl_R) | 9.0% in idol_dance@43 | idol_dance@43, jump_tuck |
| 19 | major | pen_frac | petticoat | スカート11_1 (petticoat_core) | 8.0% in cross_legged | cross_legged |
| 20 | major | span | body | elbow.R (span:elbow.R) | 1.59 in idol_dance@33 | idol_dance@33, reach_forward, run@18, run_l, arms_forward, dance_clap, dance_heart, hands_behind_back, arms_crossed, hug_self, run_r, lie_back_elbows, hands_... |
| 21 | major | pen_frac | hair_front | 横髪奥_1.L (hair_curtain_L) | 7.8% in dance_point | dance_point, idol_dance@23, hands_behind_head, spin@10 |
| 22 | major | self | body | body:hand.L x hand.R (body:hand.L x hand.R) | 3.2 in idol_dance@35 | idol_dance@35, dance_heart, dance_clap, hands_behind_head |
| 23 | major | self | body | body:forearm.L x pelvis (body:forearm.L x pelvis) | 3.2 in idol_dance@75 | idol_dance@75 |
| 24 | major | stretch | skirt | スカート6_1 (skirt) | 2.64 in lie_back_elbows | lie_back_elbows, cross_legged, spin@27 |
| 25 | major | self | body | body:forearm.L x forearm.R (body:forearm.L x forearm.R) | 3.1 in idol_dance@35 | idol_dance@35, arms_crossed, dance_clap, hands_behind_back |
| 26 | major | stretch | body | 足補助.R (body) | 2.62 in cross_legged | cross_legged |
| 27 | major | vol | body | joint:shoulder.L (joint:shoulder.L) | 0.44 in idol_dance@79 | idol_dance@79, hands_behind_head, dance_sway, jump_tuck, dance_heart, hands_behind_back |
| 28 | major | pen | petticoat | スカート11_1 (petticoat_core) | 3.4 in cross_legged | cross_legged |
| 29 | major | pen | petticoat | スカート11_2 (petticoat_tier1) | 3.3 in cross_legged | cross_legged |
| 30 | major | pen_frac | hair_front | 頭 (hair_bangs) | 6.0% in idol_dance@45 | idol_dance@45, dance_heart, idol_dance@47, idol_dance@48 |
| 31 | major | span | body | elbow.L (span:elbow.L) | 1.36 in reach_forward | reach_forward, run@8, run_r, kneel_one, arms_forward, idol_dance@39, dance_clap, dance_heart, hands_behind_back, arms_crossed, dance_point, hug_self, run_l, ... |
| 32 | major | bone_pop | rig | スカート2_2 (bones) | 10.3 in sit_stand@69 | sit_stand@69 |
| 33 | major | pop | skirt | スカート2_2 (skirt) | 10.3 in sit_stand@69 | sit_stand@69 |
| 34 | major | pen_frac | hair_front | 横髪奥_0.L (hair_curtain_L) | 5.0% in reach_up_back | reach_up_back |
| 35 | major | pen_frac | hair_front | 横髪奥_0.R (hair_curtain_R) | 5.0% in reach_up_back | reach_up_back |
| 36 | major | joint | body | joint:shoulder.L (joint:shoulder.L) | 0.58 in idol_dance@79 | idol_dance@79, jump_tuck, hands_behind_head, dance_sway, dance_heart, hands_behind_back |
| 37 | major | stretch | petticoat | スカート15_2 (petticoat_tier1) | 2.30 in run@7 | run@7, run_r, high_kick, spin@23, kneel_one, walk@12 |
| 38 | major | pen_frac | hair_front | 横髪長_0.L (hair_lock_L) | 4.8% in idol_dance@81 | idol_dance@81, reach_up_back |
| 39 | major | pen_frac | hair_front | 横髪長_0.R (hair_lock_R) | 4.7% in reach_up_back | reach_up_back |
| 40 | major | stretch | bodice | スカート0_0 (bodice_ribbon_tails) | 2.26 in sit_stand@60 | sit_stand@60, jump_tuck, sit_chair, cross_legged, high_kick, lie_back_elbows, run@6 |

## Issues by part (major / minor rows)

| part | major | minor |
|---|---|---|
| body | 69 | 95 |
| petticoat | 19 | 47 |
| hair_front | 18 | 27 |
| hair/garment | 11 | 13 |
| sleeves | 9 | 72 |
| skirt | 9 | 24 |
| accessories | 8 | 7 |
| rig | 5 | 1 |
| bodice | 3 | 12 |
| hair/skirt | 3 | 9 |
| hair_back | 2 | 12 |
| shoes | 1 | 6 |
| head | 0 | 13 |
| skirt/petticoat | 0 | 1 |
