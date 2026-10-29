# Motion test report

Model: 61 meshes, 109810 vertices, 108120 faces (without outlines). Run time 1339 s. Not gated: the exit code of rig_check covers the core poses only. No cloth or hair physics: chains move only as keyed or driven (MMD simulates them).

Thresholds (minor / major): stretch 1.60/2.00, compress 0.30/0.12, flip 10/100, pen 1.0/2.0, pen_frac 0.5%/3.0%, self 0.5/1.5, contact 3.0/6.0, cross 40/400, joint 0.85/0.70, vol 0.80/0.65, knee -0.5/-5.0, elbow -5.0/-15.0, pop 2.0/6.0, bone_pop 2.0/6.0, jitter 0.03/0.08, speed 12.00/20.00, eye 0.8/1.5, span 0.70/1.00.
Cells: plain = ok, *italic* = minor, **bold** = major (location, frame for clips). pen/self/contact in cm, pop in mm; joint = median skin radius ratio at the worst joint band, vol = its mean squared radius ratio; knee/elbow = least signed bend (negative = hyperextended).

## core

| name | stretch | compress | flip | pen cm | pen % | contact cm | cross | joint | vol | knee | elbow | span |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| test | *1.83* (スカート12_2) | **0.09** (足.L) | 8 | 0.3 | 0.0% | 0.2 | *332* (hair x skirt) | 0.97 | 0.80 | 59.8 | 69.4 | 0.58 |
| arms_up | *1.77* (腕捩.R) | *0.28* (袖_0.R) | 2 | 0.6 | 0.1% | - | **780** (hair x garment) | 0.93 | 0.86 | 0.0 | 41.6 | - |
| arms_forward | *1.80* (腕捩.L) | **0.06** (ひじ補助.R) | *40* (ひじ補助.L) | 0.5 | 0.0% | - | 1 | 0.98 | 0.99 | 0.0 | 139.5 | **1.31** (elbow.R) |
| wrist_twist_pos | 1.34 | 0.61 | 0 | 0.0 | 0.0% | - | 0 | 0.90 | 0.81 | 0.0 | 56.8 | - |
| wrist_twist_neg | 1.34 | 0.61 | 0 | 0.0 | 0.0% | - | 0 | 0.91 | 0.80 | 0.0 | 56.8 | - |
| squat | *1.85* (足.R) | **0.07** (足.L) | *26* (足.L) | *1.0* (ひざ.L) | **3.4%** (ひざ.L) | 2.9 | **408** (hair x skirt) | 0.97 | *0.77* (knee.L) | 106.4 | 29.6 | 0.61 |
| walk | *1.74* (スカート12_2) | 0.50 | 3 | *1.7* (後髪束12_2) | 0.1% | - | **1200** (hair x garment) | 0.99 | 0.92 | 30.7 | 38.4 | - |
| head_left | 1.46 | 0.52 | 1 | 0.3 | 0.0% | - | *188* (hair x garment) | 0.99 | 0.97 | 0.0 | 29.6 | - |
| head_right | 1.46 | 0.52 | 3 | 0.3 | 0.0% | - | *187* (hair x garment) | 0.99 | 0.97 | 0.0 | 29.6 | - |
| torso_left | 1.33 | 0.63 | 2 | 0.0 | 0.0% | - | 17 | 0.99 | 0.98 | 0.0 | 29.6 | - |
| torso_right | 1.38 | 0.69 | 3 | 0.1 | 0.0% | - | *46* (hair x skirt) | 0.99 | 0.98 | 0.0 | 29.6 | - |
| swing | 1.51 | 0.77 | 0 | 0.0 | 0.0% | - | *154* (hair x skirt) | 1.00 | 1.00 | 0.0 | 29.6 | - |
| fist | *1.86* (手首.L) | 0.38 | 2 | 0.0 | 0.0% | - | 0 | 1.00 | 1.00 | 0.0 | 45.2 | - |
| raise_bend | 1.43 | 0.49 | 0 | 0.6 | 0.1% | - | *54* (hair x garment) | 0.99 | 1.00 | 0.0 | 69.4 | - |
| reach_forward | *1.60* (ひじ補助.R) | 0.32 | 0 | 0.0 | 0.0% | - | 0 | 0.98 | 0.98 | 0.0 | 95.5 | **1.32** (elbow.L) |
| forward_bend | 1.41 | 0.71 | 2 | 0.2 | 0.0% | - | *96* (hair x skirt) | 1.00 | 0.97 | 23.2 | 50.6 | - |
| side_bend | 1.46 | 0.66 | 2 | *1.8* (下半身) | *0.6%* (ひじ補助.L) | - | *278* (hair x skirt) | 0.99 | 0.98 | 0.0 | 29.6 | - |

## extended

| name | stretch | compress | flip | pen cm | pen % | self cm | contact cm | cross | joint | vol | knee | elbow | span |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| sit_chair | **2.16** (スカート5_1) | **0.10** (足.L) | 9 | 0.8 | *2.1%* (スカート4_0) | - | 0.1 | 12 | 0.97 | 0.82 | 91.0 | 69.4 | 0.56 |
| seiza | *1.78* (足.R) | **0.06** (足.R) | 10 | *1.1* (足首.R) | *1.7%* (足首.R) | - | *3.3* (shin.R x thigh.R) | 0 | 0.89 | **0.64** (knee.R) | 150.0 | 65.2 | 0.69 |
| kneel_one | *1.93* (ひざ.R) | **0.09** (足.R) | *19* (足.R) | *1.0* (腕捩.R) | *1.2%* (ひざ.R) | - | 2.6 | 16 | 0.96 | *0.75* (ankle.R) | 88.3 | 35.4 | **1.32** (elbow.L) |
| cross_legged | **2.60** (スカート6_1) | **0.04** (足.R) | *36* (足.L) | **3.4** (スカート11_1) | **6.6%** (スカート11_1) | **3.1** (thigh.L x thigh.R) | 1.9 | *214* (skirt x petticoat) | 0.96 | *0.70* (knee.L) | 124.7 | 52.8 | 0.65 |
| deep_lunge | *1.90* (スカート12_2) | *0.25* (足.R) | 1 | 0.6 | *0.7%* (スカート11_0) | - | - | 0 | 0.98 | 0.86 | 66.2 | 52.8 | 0.51 |
| run_l | *1.86* (足.L) | **0.05** (足.L) | 10 | *1.2* (スカート13_0) | 0.1% | - | 1.5 | **1046** (hair x garment) | 0.96 | *0.72* (knee.L) | 17.6 | 95.5 | **1.32** (elbow.R) |
| run_r | **2.17** (スカート15_2) | **0.05** (足.R) | 10 | *1.1* (後髪束3_2) | 0.2% | **5.1** (thigh.L x thigh.R) | 1.5 | **859** (hair x garment) | 0.96 | *0.72* (knee.R) | 17.6 | 95.5 | **1.32** (elbow.L) |
| jump_tuck | **2.21** (スカート0_0) | **0.09** (足.L) | *32* (下半身) | *1.6* (横髪巻_1.L) | **7.8%** (横髪巻_1.L) | - | 2.7 | **1720** (hair x skirt) | *0.80* (shoulder.L) | *0.66* (knee.L) | 134.9 | 45.2 | 0.67 |
| high_kick | **2.17** (スカート15_2) | *0.22* (足補助.L) | 0 | 0.8 | *1.4%* (スカート10_0) | - | *5.7* (pelvis x thigh.L) | 0 | 0.95 | 0.92 | -0.0 | 35.4 | - |
| arms_crossed | *1.78* (袖胴.L) | *0.21* (ひじ補助.L) | 0 | 0.9 | *0.9%* (手捩.L) | **4.4** (forearm.L x forearm.R) | *4.6* (forearm.L x hand.R) | 0 | 0.97 | 0.98 | 0.0 | 109.4 | **1.31** (elbow.R) |
| hands_behind_head | *1.97* (袖胴.R) | *0.14* (ひじ補助.R) | *12* (袖_0.L) | *1.1* (頭) | *0.7%* (横髪奥_1.L) | *1.3* (hand.L x hand.R) | - | **6085** (hair x garment) | *0.81* (shoulder.L) | **0.63** (shoulder.L) | 0.0 | 136.7 | **1.21** (elbow.L) |
| hands_behind_back | *1.66* (肩補助2.L) | 0.32 | 0 | *1.2* (袖胴.L) | *2.5%* (手捩.L) | *1.2* (forearm.L x forearm.R) | - | **1138** (hair x garment) | *0.85* (shoulder.L) | *0.73* (shoulder.R) | 0.0 | 99.9 | **1.31** (elbow.R) |
| hand_to_shoulder | *1.85* (袖胴.L) | *0.18* (腕捩.L) | 0 | *1.8* (手捩.L) | *2.1%* (手捩.L) | - | - | *72* (hair x garment) | 0.96 | 0.94 | 0.0 | 32.9 | **1.29** (elbow.L) |
| hands_on_hips | 1.53 | 0.36 | 0 | 0.8 | 0.0% | - | - | 0 | 0.92 | 0.87 | 0.0 | 86.8 | **1.23** (elbow.R) |
| reach_up_back | *1.72* (上半身2) | 0.34 | *11* (袖_0.L) | *1.4* (頭) | **14.9%** (頭) | 0.4 | - | **4249** (hair x garment) | 0.92 | 0.82 | 0.0 | 32.9 | - |
| hug_self | *1.79* (袖胴.L) | *0.24* (袖胴.L) | 0 | **2.9** (手捩.L) | **13.6%** (手捩.L) | **2.1** (hand.R x upperarm.L) | - | *41* (hair x garment) | 0.96 | 1.00 | 0.0 | 111.1 | **1.30** (elbow.L) |
| twist_bend | 1.37 | 0.66 | 2 | *1.7* (下半身) | *2.2%* (腕捩.L) | - | - | *44* (hair x garment) | 0.98 | 0.93 | 25.3 | 29.6 | - |
| lie_back_elbows | **2.64** (スカート6_1) | *0.19* (下半身) | 2 | *1.2* (下半身) | *0.9%* (下半身) | - | - | *77* (hair x garment) | 0.98 | 0.94 | 8.0 | 99.9 | **1.28** (elbow.R) |
| look_over_shoulder | 1.59 | 0.61 | 4 | **2.0** (後髪0_1) | *1.3%* (後髪0_1) | - | - | *376* (hair x garment) | 0.98 | 0.96 | 0.0 | 38.4 | - |
| curtsy | *1.65* (足.L) | 0.33 | 0 | 0.2 | 0.0% | - | - | 37 | 0.97 | 0.88 | 55.7 | 39.6 | 0.48 |
| dance_sway | *1.72* (上半身2) | 0.31 | *14* (袖_0.L) | *1.1* (横髪巻_1.L) | *3.0%* (横髪長_1.L) | - | - | **1119** (hair x garment) | *0.84* (shoulder.L) | **0.65** (shoulder.L) | 38.4 | 41.6 | **1.22** (elbow.R) |
| dance_point | *1.87* (袖胴.L) | *0.16* (腕捩.L) | 3 | **2.7** (手捩.L) | **7.8%** (横髪奥_1.L) | - | - | *97* (hair x garment) | 0.87 | *0.74* (shoulder.R) | 38.8 | 32.9 | **1.30** (elbow.L) |
| dance_heart | *1.69* (腕捩.L) | 0.32 | 2 | *1.4* (頭) | **6.6%** (頭) | **1.7** (hand.L x hand.R) | *5.0* (forearm.R x hand.L) | **3795** (hair x garment) | *0.84* (shoulder.L) | *0.71* (shoulder.L) | 33.5 | 108.5 | **1.34** (elbow.R) |
| dance_clap | *1.70* (足.L) | *0.26* (足.L) | 1 | 0.7 | *0.6%* (手捩.R) | *1.2* (hand.L x hand.R) | - | 26 | 0.90 | 0.81 | 69.0 | 108.5 | **1.32** (elbow.L) |

## motion

| name | stretch | compress | flip | pen cm | pen % | self cm | contact cm | cross | joint | vol | knee | elbow | span | pop mm | bone pop mm | jitter | speed m/s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| walk | *1.62* (足.L) | 0.39 | 3 | *1.3* (スカート12_1) | *1.7%* (腕捩.R) | - | - | *231* (hair x garment) | 0.99 | 0.89 | 26.9 | 37.1 | 0.47 | **8.2** (スカート15_2, f50) | **7.7** (中指３.L, f7) | *0.05* (スカート15_2) | 1.22 |
| run | **2.30** (スカート15_2, f7) | **0.05** (足.R, f2) | *11* (足.R) | *1.6* (後髪束12_3) | *1.3%* (ひざ.R) | **4.7** (thigh.L x thigh.R, f6) | *5.8* (pelvis x thigh.L) | **1166** (hair x garment, f18) | 0.92 | *0.65* (knee.L) | 31.9 | 86.8 | **1.32** (elbow.L, f6) | **68.5** (スカート14_2, f16) | **59.3** (スカート14_2, f16) | **0.56** (スカート2_1, f4) | 4.84 |
| turn | *1.65* (足.L) | 0.35 | 2 | 0.8 | *0.7%* (横髪奥_1.R) | *1.3* (foot.L x foot.R) | - | *143* (hair x garment) | 0.99 | 0.89 | 33.4 | 45.2 | 0.48 | *5.8* (ひざ.R) | *5.2* (足.R) | 0.03 | 1.62 |
| sit_stand | **2.26** (スカート0_0, f60) | **0.09** (足.L, f64) | 10 | *1.7* (スカート13_0) | *2.6%* (スカート11_0) | - | 0.1 | 10 | 0.97 | 0.81 | 0.0 | 35.4 | 0.57 | **10.3** (スカート2_2, f69) | **10.3** (スカート2_2, f69) | *0.06* (スカート1_2) | 0.84 |
| spin | *1.99* (スカート0_1) | 0.52 | 2 | 0.8 | *0.7%* (横髪奥_1.L) | - | - | **1352** (hair x skirt, f16) | 0.95 | 0.93 | 27.2 | 35.4 | - | **8.1** (後髪束11_4, f37) | **7.1** (横髪長_2.L, f3) | *0.04* (後髪束11_4) | 3.93 |
| idol_dance | *1.91* (上半身2) | **0.05** (足.L, f72) | *54* (袖_0.L) | **5.3** (手捩.L, f74) | **16.2%** (手捩.L, f74) | **5.0** (hand.L x pelvis, f75) | *5.2* (forearm.L x hand.R) | **4574** (hair x garment, f77) | **0.58** (shoulder.L, f79) | **0.44** (shoulder.L, f79) | 0.0 | 29.6 | **1.34** (elbow.R, f47) | **54.8** (ひざ.L, f60) | **53.8** (ひざ.L, f60) | **0.69** (腕D.L, f78) | 6.64 |

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
| 1 | major | cross | hair/garment | hair x garment (hair x garment) | 6085 in hands_behind_head | hands_behind_head, idol_dance@77, reach_up_back, dance_heart, walk, run@18, hands_behind_back, dance_sway, run_l, run_r, arms_up, look_over_shoulder, walk@14... |
| 2 | major | pop | petticoat | スカート14_2 (petticoat_tier0) | 68.5 in run@16 | run@16 |
| 3 | major | bone_pop | rig | スカート14_2 (bones) | 59.3 in run@16 | run@16 |
| 4 | major | jitter | body | 腕D.L (body) | 0.69 in idol_dance@78 | idol_dance@78 |
| 5 | major | pop | body | ひざ.L (body) | 54.8 in idol_dance@60 | idol_dance@60 |
| 6 | major | bone_pop | rig | ひざ.L (bones) | 53.8 in idol_dance@60 | idol_dance@60 |
| 7 | major | jitter | skirt | スカート2_1 (skirt) | 0.56 in run@4 | run@4 |
| 8 | major | pen_frac | sleeves | 手捩.L (sleeve_cuff) | 16.2% in idol_dance@74 | idol_dance@74, hug_self, dance_point, hands_behind_back, hand_to_shoulder, arms_crossed |
| 9 | major | pen_frac | accessories | 頭 (acc_leaves_L) | 14.9% in reach_up_back | reach_up_back, dance_heart, idol_dance@48 |
| 10 | major | pen_frac | hair_front | 横髪巻_1.L (hair_curl_L) | 13.1% in idol_dance@54 | idol_dance@54, jump_tuck, dance_sway |
| 11 | major | cross | hair/skirt | hair x skirt (hair x skirt) | 1720 in jump_tuck | jump_tuck, spin@16, squat, test, side_bend, swing, head_right, forward_bend, dance_heart, idol_dance@48, run_l, torso_right |
| 12 | major | self | body | body:thigh.L x thigh.R (body:thigh.L x thigh.R) | 5.1 in run_r | run_r, run@6, cross_legged |
| 13 | major | self | body | body:hand.L x pelvis (body:hand.L x pelvis) | 5.0 in idol_dance@75 | idol_dance@75 |
| 14 | major | pen | sleeves | 手捩.L (sleeve_cuff) | 5.3 in idol_dance@74 | idol_dance@74, hug_self, dance_point, hand_to_shoulder, hands_behind_back |
| 15 | major | self | body | body:forearm.L x thigh.L (body:forearm.L x thigh.L) | 4.5 in idol_dance@74 | idol_dance@74 |
| 16 | major | self | body | body:forearm.L x forearm.R (body:forearm.L x forearm.R) | 4.4 in arms_crossed | arms_crossed, hands_behind_back |
| 17 | major | self | body | body:hand.L x thigh.L (body:hand.L x thigh.L) | 4.3 in idol_dance@75 | idol_dance@75 |
| 18 | major | pen_frac | hair_front | 横髪巻_1.R (hair_curl_R) | 9.0% in idol_dance@43 | idol_dance@43, jump_tuck |
| 19 | major | pen_frac | hair_front | 横髪奥_1.L (hair_curtain_L) | 7.8% in dance_point | dance_point, idol_dance@23, hands_behind_head, spin@10 |
| 20 | major | self | body | body:hand.L x upperarm.R (body:hand.L x upperarm.R) | 3.2 in idol_dance@30 | idol_dance@30 |
| 21 | major | stretch | skirt | スカート6_1 (skirt) | 2.64 in lie_back_elbows | lie_back_elbows, cross_legged, spin@27 |
| 22 | major | pen_frac | petticoat | スカート11_1 (petticoat_core) | 6.6% in cross_legged | cross_legged |
| 23 | major | vol | body | joint:shoulder.L (joint:shoulder.L) | 0.44 in idol_dance@79 | idol_dance@79, hands_behind_head, dance_sway, jump_tuck, dance_heart, hands_behind_back |
| 24 | major | pen | petticoat | スカート11_1 (petticoat_core) | 3.4 in cross_legged | cross_legged |
| 25 | major | pen | petticoat | スカート11_2 (petticoat_tier1) | 3.3 in cross_legged | cross_legged |
| 26 | major | span | body | elbow.R (span:elbow.R) | 1.34 in dance_heart | dance_heart, idol_dance@47, run@16, run_l, reach_forward, dance_clap, hands_behind_back, arms_crossed, arms_forward, hug_self, run_r, lie_back_elbows, hands_... |
| 27 | major | span | body | elbow.L (span:elbow.L) | 1.34 in idol_dance@47 | idol_dance@47, dance_heart, run@6, run_r, reach_forward, dance_clap, kneel_one, hands_behind_back, arms_forward, arms_crossed, dance_point, hug_self, hand_to... |
| 28 | major | stretch | body | 足補助.L (body) | 2.44 in cross_legged | cross_legged, lie_back_elbows |
| 29 | major | bone_pop | rig | スカート2_2 (bones) | 10.3 in sit_stand@69 | sit_stand@69 |
| 30 | major | self | body | body:forearm.L x pelvis (body:forearm.L x pelvis) | 2.6 in idol_dance@74 | idol_dance@74 |
| 31 | major | pop | skirt | スカート2_2 (skirt) | 10.3 in sit_stand@69 | sit_stand@69 |
| 32 | major | pen_frac | hair_front | 横髪奥_0.L (hair_curtain_L) | 5.0% in reach_up_back | reach_up_back |
| 33 | major | pen_frac | hair_front | 横髪奥_0.R (hair_curtain_R) | 5.0% in reach_up_back | reach_up_back |
| 34 | major | joint | body | joint:shoulder.L (joint:shoulder.L) | 0.58 in idol_dance@79 | idol_dance@79, jump_tuck, hands_behind_head, dance_heart, dance_sway, hands_behind_back |
| 35 | major | stretch | petticoat | スカート15_2 (petticoat_tier1) | 2.30 in run@7 | run@7, run_r, high_kick, spin@23, kneel_one, walk@12 |
| 36 | major | pen_frac | hair_front | 横髪長_0.L (hair_lock_L) | 4.8% in idol_dance@81 | idol_dance@81, reach_up_back |
| 37 | major | pen_frac | hair_front | 横髪長_0.R (hair_lock_R) | 4.7% in reach_up_back | reach_up_back |
| 38 | major | stretch | bodice | スカート0_0 (bodice_ribbon_tails) | 2.26 in sit_stand@60 | sit_stand@60, jump_tuck, sit_chair, cross_legged, high_kick, lie_back_elbows, run@6 |
| 39 | major | stretch | petticoat | スカート5_2 (petticoat_tier1) | 2.25 in lie_back_elbows | lie_back_elbows, cross_legged, sit_chair, sit_stand@36, jump_tuck |
| 40 | major | self | body | body:hand.R x upperarm.L (body:hand.R x upperarm.L) | 2.1 in hug_self | hug_self |

## Issues by part (major / minor rows)

| part | major | minor |
|---|---|---|
| body | 66 | 88 |
| petticoat | 19 | 47 |
| hair_front | 16 | 27 |
| hair/garment | 11 | 16 |
| sleeves | 9 | 71 |
| skirt | 9 | 23 |
| accessories | 8 | 7 |
| rig | 5 | 1 |
| bodice | 3 | 12 |
| hair/skirt | 3 | 9 |
| hair_back | 2 | 12 |
| shoes | 1 | 6 |
| head | 0 | 13 |
| skirt/petticoat | 0 | 1 |
