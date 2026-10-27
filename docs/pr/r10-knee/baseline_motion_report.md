# Motion test report

Model: 61 meshes, 109658 vertices, 107968 faces (without outlines). Run time 2258 s. Not gated: the exit code of rig_check covers the core poses only. No cloth or hair physics: chains move only as keyed or driven (MMD simulates them).

Thresholds (minor / major): stretch 1.60/2.00, compress 0.30/0.12, flip 10/100, pen 1.0/2.0, pen_frac 0.5%/3.0%, self 0.5/1.5, contact 3.0/6.0, cross 40/400, joint 0.85/0.70, vol 0.80/0.65, knee -0.5/-5.0, elbow -5.0/-15.0, pop 2.0/6.0, bone_pop 2.0/6.0, jitter 0.03/0.08, speed 12.00/20.00, eye 0.8/1.5, span 0.70/1.00.
Cells: plain = ok, *italic* = minor, **bold** = major (location, frame for clips). pen/self/contact in cm, pop in mm; joint = median skin radius ratio at the worst joint band, vol = its mean squared radius ratio; knee/elbow = least signed bend (negative = hyperextended).

## core

| name | stretch | compress | flip | pen cm | pen % | cross | joint | vol | knee | elbow | span |
|---|---|---|---|---|---|---|---|---|---|---|---|
| test | *1.61* (スカート15_2) | *0.16* (ひざ補助.L) | 7 | 0.4 | 0.0% | *121* (hair x skirt) | 0.96 | *0.75* (knee.L) | 59.8 | 69.2 | *0.94* (knee.L) |
| arms_up | *1.71* (腕捩.L) | *0.30* (袖_0.R) | 0 | 0.6 | 0.2% | **829** (hair x garment) | 0.93 | 0.86 | 0.0 | 41.5 | - |
| arms_forward | *1.69* (ひじ.R) | **0.07** (ひじ補助.L) | *84* (ひじ補助.L) | 0.5 | 0.0% | 0 | 0.98 | 0.99 | 0.0 | 139.4 | **1.29** (elbow.R) |
| wrist_twist_pos | 1.30 | 0.59 | 0 | 0.0 | 0.0% | 0 | 0.90 | 0.81 | 0.0 | 56.7 | - |
| wrist_twist_neg | 1.30 | 0.59 | 0 | 0.0 | 0.0% | 0 | 0.91 | 0.80 | 0.0 | 56.7 | - |
| squat | *1.66* (ひざ.L) | *0.17* (ひざ補助.L) | *24* (ひざ補助.L) | 0.8 | *2.3%* (ひざ.R) | *393* (hair x skirt) | 0.96 | *0.72* (knee.R) | 101.1 | 29.7 | *0.95* (knee.L) |
| walk | *1.79* (スカート0_2) | 0.52 | 0 | *1.7* (後髪束12_2) | 0.1% | **1295** (hair x garment) | 0.97 | 0.88 | 26.0 | 38.3 | - |
| head_left | 1.46 | 0.57 | 1 | 0.2 | 0.0% | *275* (hair x garment) | 0.99 | 0.97 | 0.0 | 29.7 | - |
| head_right | 1.46 | 0.57 | 0 | 0.2 | 0.0% | *273* (hair x garment) | 0.99 | 0.97 | 0.0 | 29.7 | - |
| torso_left | 1.53 | 0.62 | 1 | 0.0 | 0.0% | 18 | 0.99 | 0.98 | 0.0 | 29.7 | - |
| torso_right | 1.35 | 0.47 | 1 | 0.1 | 0.0% | 18 | 0.99 | 0.98 | 0.0 | 29.7 | - |
| swing | 1.55 | 0.77 | 1 | 0.0 | 0.0% | *201* (hair x skirt) | 1.00 | 1.00 | 0.0 | 29.7 | - |
| fist | *1.82* (手首.L) | 0.34 | 2 | 0.0 | 0.0% | 0 | 1.00 | 1.00 | 0.0 | 45.1 | - |
| raise_bend | 1.41 | 0.44 | 0 | 0.6 | 0.1% | *62* (hair x garment) | 0.99 | 1.00 | 0.0 | 69.2 | - |
| reach_forward | 1.59 | 0.30 | 0 | 0.0 | 0.0% | 0 | 0.98 | 0.98 | 0.0 | 95.3 | **1.31** (elbow.R) |
| forward_bend | 1.33 | 0.73 | 0 | 0.3 | 0.0% | *103* (hair x skirt) | 0.98 | 0.95 | 18.7 | 50.5 | - |
| side_bend | 1.44 | 0.57 | 0 | *1.6* (下半身) | *1.3%* (袖_0.L) | *141* (hair x skirt) | 0.99 | 0.98 | 0.0 | 29.7 | - |

## extended

| name | stretch | compress | flip | pen cm | pen % | self cm | contact cm | cross | joint | vol | knee | elbow | span |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| sit_chair | **2.07** (スカート5_1) | *0.16* (ひざ補助.R) | 1 | 0.7 | *1.4%* (スカート11_0) | - | - | 14 | 0.96 | *0.76* (knee.R) | 85.8 | 69.2 | *0.94* (knee.L) |
| seiza | *1.78* (スカート5_2) | *0.15* (ひざ補助.R) | *52* (ひざ補助.L) | *1.4* (足首.R) | *2.8%* (足首.R) | - | - | 0 | 0.97 | *0.66* (knee.R) | 143.6 | 65.0 | *0.95* (knee.L) |
| kneel_one | *1.90* (ひざ.R) | *0.13* (ひざ.R) | *17* (ひざ補助.R) | *1.0* (腕捩.R) | *1.1%* (足首.R) | - | 2.5 | 24 | 0.96 | *0.71* (knee.R) | 83.2 | 35.4 | **1.32** (elbow.L) |
| cross_legged | **2.40** (スカート14_2) | *0.15* (足補助.L) | *53* (ひざ補助.L) | **3.4** (スカート4_2) | **7.1%** (スカート11_1) | - | - | *128* (skirt x petticoat) | 0.96 | *0.68* (knee.L) | 124.7 | 52.7 | *0.95* (knee.L) |
| deep_lunge | *1.82* (スカート0_2) | *0.28* (ひざ補助.R) | 0 | 0.6 | 0.3% | - | - | 0 | 0.96 | 0.82 | 61.1 | 52.7 | *0.94* (knee.R) |
| run_l | *1.88* (スカート0_2) | *0.17* (ひじ補助.L) | *16* (ひざ補助.L) | *1.0* (スカート13_0) | 0.3% | - | - | **1071** (hair x garment) | 0.96 | *0.70* (knee.L) | 16.1 | 95.3 | **1.31** (elbow.R) |
| run_r | **2.15** (スカート14_2) | *0.17* (ひじ補助.R) | *16* (ひざ補助.R) | *1.1* (後髪束3_3) | 0.1% | **5.1** (thigh.L x thigh.R) | - | **931** (hair x garment) | 0.96 | *0.70* (knee.R) | 16.1 | 95.3 | **1.31** (elbow.L) |
| jump_tuck | **2.35** (スカート5_1) | *0.16* (ひざ補助.R) | *47* (ひざ補助.L) | *1.6* (横髪巻_1.L) | **6.5%** (横髪巻_1.L) | - | - | **1090** (hair x skirt) | *0.80* (shoulder.L) | *0.68* (knee.L) | 129.7 | 45.1 | *0.95* (knee.R) |
| high_kick | *1.95* (スカート12_0) | *0.27* (足補助.L) | 0 | *1.2* (スカート10_0) | *0.9%* (スカート10_0) | - | *5.8* (pelvis x thigh.L) | 0 | 0.95 | 0.94 | 0.0 | 35.4 | - |
| arms_crossed | *1.72* (袖胴.L) | *0.14* (ひじ補助.L) | 0 | 1.0 | *0.9%* (手捩.L) | **4.3** (forearm.L x forearm.R) | *4.7* (forearm.L x hand.R) | 0 | 0.97 | 0.99 | 0.0 | 109.2 | **1.29** (elbow.R) |
| hands_behind_head | *1.85* (袖胴.R) | *0.12* (ひじ補助.L) | *36* (袖_0.L) | *1.0* (頭) | *0.7%* (横髪奥_1.L) | *1.1* (hand.L x hand.R) | - | **6116** (hair x garment) | *0.81* (shoulder.L) | **0.64** (shoulder.L) | 0.0 | 136.4 | **1.17** (elbow.R) |
| hands_behind_back | *1.66* (肩.R) | *0.22* (ひじ補助.R) | 0 | *1.2* (手捩.L) | *2.5%* (手捩.L) | *1.2* (forearm.L x forearm.R) | - | **1228** (hair x garment) | *0.84* (shoulder.R) | *0.73* (shoulder.R) | 0.0 | 99.6 | **1.30** (elbow.L) |
| hand_to_shoulder | *1.72* (袖胴.L) | *0.18* (腕捩.L) | 0 | *1.5* (手捩.L) | *1.4%* (手捩.L) | - | - | *71* (hair x garment) | 0.96 | 0.94 | 0.0 | 32.9 | **1.27** (elbow.L) |
| hands_on_hips | 1.58 | 0.34 | 0 | *1.1* (スカート12_0) | 0.1% | - | - | 22 | 0.92 | 0.89 | 0.0 | 86.6 | **1.21** (elbow.R) |
| reach_up_back | *1.78* (上半身2) | 0.30 | *27* (袖_0.L) | *1.5* (頭) | **13.0%** (頭) | 0.4 | - | **4438** (hair x garment) | 0.92 | 0.82 | 0.0 | 32.9 | - |
| hug_self | *1.76* (肩補助2.L) | *0.19* (ひじ補助.L) | 0 | **2.8** (手捩.L) | **13.2%** (手捩.L) | **1.9** (hand.R x upperarm.L) | - | 33 | 0.97 | 1.00 | 0.0 | 110.9 | **1.27** (elbow.R) |
| twist_bend | *1.63* (スカート7_0) | 0.58 | 1 | *1.7* (下半身) | *2.5%* (腕捩.L) | - | - | *258* (hair x skirt) | 0.98 | 0.92 | 20.7 | 29.7 | - |
| lie_back_elbows | **2.10** (スカート5_1) | *0.12* (ひじ補助.R) | 2 | *1.4* (袖胴.L) | *1.2%* (袖胴.L) | - | - | *85* (hair x garment) | 0.98 | 0.96 | 8.0 | 99.6 | **1.26** (elbow.R) |
| look_over_shoulder | 1.56 | 0.60 | 0 | *1.9* (後髪0_1) | *1.0%* (後髪0_1) | - | - | *394* (hair x garment) | 0.98 | 0.96 | 0.0 | 38.3 | - |
| curtsy | 1.50 | 0.36 | 1 | 0.3 | 0.0% | - | - | 31 | 0.97 | 0.84 | 51.4 | 39.6 | *0.94* (knee.L) |
| dance_sway | *1.84* (上半身2) | *0.29* (袖_0.L) | *33* (袖_0.L) | *1.3* (横髪巻_1.L) | *2.8%* (横髪巻_1.L) | - | - | **1372** (hair x garment) | *0.84* (shoulder.L) | *0.66* (shoulder.L) | 33.6 | 41.5 | **1.21** (elbow.R) |
| dance_point | *1.83* (袖胴.L) | *0.14* (ひじ補助.L) | 1 | **2.6** (手捩.L) | **7.8%** (横髪奥_1.L) | - | - | *89* (hair x garment) | 0.87 | *0.75* (shoulder.R) | 33.9 | 32.9 | **1.28** (elbow.L) |
| dance_heart | *1.78* (上半身2) | *0.26* (ひじ補助.R) | 2 | *1.3* (頭) | **6.6%** (頭) | **1.6** (hand.L x hand.R) | *5.0* (forearm.L x hand.R) | **3746** (hair x garment) | *0.84* (shoulder.L) | *0.73* (shoulder.R) | 28.8 | 108.3 | **1.28** (elbow.L) |
| dance_clap | *1.64* (袖胴.R) | *0.23* (ひじ補助.R) | 0 | 0.7 | *0.6%* (手捩.R) | *1.1* (hand.L x hand.R) | - | 25 | 0.90 | 0.81 | 63.9 | 108.3 | **1.30** (elbow.R) |

## motion

| name | stretch | compress | flip | pen cm | pen % | self cm | contact cm | cross | joint | vol | knee | elbow | span | pop mm | bone pop mm | jitter | speed m/s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| walk | *1.62* (スカート15_2) | 0.41 | 1 | *1.1* (腕捩.R) | *1.8%* (腕捩.R) | - | - | *248* (hair x garment) | 0.97 | 0.85 | 22.2 | 37.1 | *0.94* (knee.L) | **7.8** (ひざ補助2.R, f31) | **7.9** (ひざ補助.R, f11) | *0.05* (スカート0_2) | 1.22 |
| run | **2.23** (スカート14_2, f8) | *0.16* (ひざ補助.L) | *23* (ひざ補助.R) | *1.6* (後髪束12_2) | *1.9%* (ひざ.R) | - | *5.9* (pelvis x thigh.L) | **1195** (hair x garment, f18) | 0.96 | *0.67* (knee.L) | 28.0 | 86.6 | **1.31** (elbow.R, f19) | **83.3** (スカート1_2, f6) | **76.2** (スカート1_2, f6) | **0.40** (スカート5_1, f6) | 3.60 |
| turn | 1.41 | 0.38 | 1 | 0.8 | *0.7%* (横髪奥_1.R) | *1.2* (foot.L x foot.R) | - | *146* (hair x garment) | 0.97 | 0.84 | 28.6 | 45.1 | *0.94* (knee.L) | *5.7* (ひざ補助2.R) | *5.3* (ひざ補助.R) | *0.03* (スカート15_2) | 1.62 |
| sit_stand | **2.07** (スカート5_1, f36) | *0.16* (ひざ補助.R) | 4 | *1.8* (スカート13_0) | *2.3%* (スカート11_0) | - | - | 13 | 0.96 | *0.76* (knee.R) | 0.0 | 35.4 | *0.94* (knee.R) | *4.5* (後髪束12_4) | *4.0* (後髪束12_4) | *0.05* (スカート0_2) | 0.81 |
| spin | **2.09** (スカート14_2, f27) | 0.55 | 2 | 0.8 | *0.7%* (横髪奥_1.L) | - | - | **1000** (hair x skirt, f6) | 0.94 | 0.89 | 22.8 | 35.4 | - | **30.6** (後髪束9_4, f4) | **27.0** (後髪束9_4, f4) | *0.07* (後髪束9_3) | 3.93 |
| idol_dance | *1.98* (上半身2) | **0.09** (肩補助3.L, f79) | *85* (袖_0.L) | **5.4** (手捩.L, f74) | **16.3%** (手捩.L, f74) | **4.9** (hand.L x pelvis, f75) | *5.2* (forearm.R x hand.L) | **4733** (hair x garment, f77) | **0.60** (shoulder.L, f79) | **0.45** (shoulder.L, f79) | 0.0 | 29.7 | **1.33** (elbow.R, f31) | **36.6** (ひざ補助2.L, f60) | **36.6** (ひざ補助.L, f60) | **0.73** (腕D.L, f78) | 6.65 |

## eyes (gaze at the limits x eye morphs)

| case | poke mm | where |
|---|---|---|
| gaze | 1.36 (minor) | head_eye_L gaze +10/+8 |
| gaze+まばたき | 0.00 (ok) | eyes  |
| gaze+まばたき=0.5 | 1.46 (minor) | head_eye_hilite_R gaze +0/-8 |
| gaze+ウィンク | 1.36 (minor) | head_eye_R gaze -10/+8 |
| gaze+ウィンク右 | 1.36 (minor) | head_eye_L gaze +10/+8 |
| gaze+笑い | 0.40 (ok) | head_eye_L gaze +10/+8 |
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
| 1 | major | pop | petticoat | スカート1_2 (petticoat_tier1) | 83.3 in run@6 | run@6 |
| 2 | major | bone_pop | rig | スカート1_2 (bones) | 76.2 in run@6 | run@6 |
| 3 | major | cross | hair/garment | hair x garment (hair x garment) | 6116 in hands_behind_head | hands_behind_head, idol_dance@77, reach_up_back, dance_heart, dance_sway, walk, hands_behind_back, run@18, run_l, run_r, arms_up, look_over_shoulder, head_le... |
| 4 | major | jitter | body | 腕D.L (body) | 0.73 in idol_dance@78 | idol_dance@78 |
| 5 | major | bone_pop | rig | ひざ補助.L (bones) | 36.6 in idol_dance@60 | idol_dance@60 |
| 6 | major | pop | body | ひざ補助2.L (body) | 36.6 in idol_dance@60 | idol_dance@60 |
| 7 | major | jitter | skirt | スカート5_1 (skirt) | 0.40 in run@6 | run@6 |
| 8 | major | pop | hair_back | 後髪束9_4 (hair_back) | 30.6 in spin@4 | spin@4 |
| 9 | major | pen_frac | sleeves | 手捩.L (sleeve_cuff) | 16.3% in idol_dance@74 | idol_dance@74, hug_self, dance_point, hands_behind_back, hand_to_shoulder, arms_crossed |
| 10 | major | bone_pop | rig | 後髪束9_4 (bones) | 27.0 in spin@4 | spin@4 |
| 11 | major | pen_frac | hair_front | 横髪巻_1.L (hair_curl_L) | 13.1% in idol_dance@54 | idol_dance@54, jump_tuck, dance_sway |
| 12 | major | pen_frac | accessories | 頭 (acc_leaves_L) | 13.0% in reach_up_back | reach_up_back, dance_heart, idol_dance@48 |
| 13 | major | self | body | body:thigh.L x thigh.R (body:thigh.L x thigh.R) | 5.1 in run_r | run_r |
| 14 | major | self | body | body:hand.L x pelvis (body:hand.L x pelvis) | 4.9 in idol_dance@75 | idol_dance@75 |
| 15 | major | pen | sleeves | 手捩.L (sleeve_cuff) | 5.4 in idol_dance@74 | idol_dance@74, hug_self, dance_point, hand_to_shoulder, hands_behind_back |
| 16 | major | self | body | body:forearm.L x thigh.L (body:forearm.L x thigh.L) | 4.6 in idol_dance@74 | idol_dance@74 |
| 17 | major | self | body | body:hand.L x thigh.L (body:hand.L x thigh.L) | 4.4 in idol_dance@75 | idol_dance@75 |
| 18 | major | self | body | body:forearm.L x forearm.R (body:forearm.L x forearm.R) | 4.3 in arms_crossed | arms_crossed, hands_behind_back |
| 19 | major | pen_frac | hair_front | 横髪巻_1.R (hair_curl_R) | 8.1% in idol_dance@43 | idol_dance@43, jump_tuck |
| 20 | major | pen_frac | hair_front | 横髪奥_1.L (hair_curtain_L) | 7.8% in dance_point | dance_point, idol_dance@23, hands_behind_head, spin@14 |
| 21 | major | cross | hair/skirt | hair x skirt (hair x skirt) | 1090 in jump_tuck | jump_tuck, spin@6, squat, walk, twist_bend, idol_dance@71, swing, run_l, walk@27, side_bend, test, head_right, forward_bend, turn@9 |
| 22 | major | self | body | body:hand.L x upperarm.R (body:hand.L x upperarm.R) | 3.3 in idol_dance@30 | idol_dance@30 |
| 23 | major | pen_frac | petticoat | スカート11_1 (petticoat_core) | 7.1% in cross_legged | cross_legged |
| 24 | major | pen | petticoat | スカート4_2 (petticoat_tier1) | 3.4 in cross_legged | cross_legged |
| 25 | major | vol | body | joint:shoulder.L (joint:shoulder.L) | 0.45 in idol_dance@79 | idol_dance@79, hands_behind_head, dance_sway, jump_tuck, dance_heart, hands_behind_back |
| 26 | major | pen_frac | petticoat | スカート4_2 (petticoat_tier1) | 6.1% in cross_legged | cross_legged |
| 27 | major | self | body | body:forearm.L x pelvis (body:forearm.L x pelvis) | 2.7 in idol_dance@74 | idol_dance@74 |
| 28 | major | span | body | elbow.R (span:elbow.R) | 1.33 in idol_dance@31 | idol_dance@31, run@19, run_l, reach_forward, dance_clap, hands_behind_back, arms_crossed, arms_forward, dance_heart, run_r, hug_self, lie_back_elbows, hands_... |
| 29 | major | span | body | elbow.L (span:elbow.L) | 1.32 in kneel_one | kneel_one, run@7, run_r, reach_forward, idol_dance@28, dance_clap, hands_behind_back, arms_forward, arms_crossed, dance_heart, dance_point, hand_to_shoulder,... |
| 30 | major | stretch | skirt | スカート14_2 (skirt) | 2.40 in cross_legged | cross_legged, run@8, run_r |
| 31 | major | stretch | body | 足補助.L (body) | 2.39 in cross_legged | cross_legged, lie_back_elbows, sit_chair, sit_stand@58, jump_tuck |
| 32 | major | pen_frac | hair_front | 横髪長_0.L (hair_lock_L) | 5.3% in idol_dance@81 | idol_dance@81, reach_up_back |
| 33 | major | stretch | skirt | スカート5_1 (skirt) | 2.35 in jump_tuck | jump_tuck, lie_back_elbows, sit_chair, sit_stand@36 |
| 34 | major | pen | petticoat | スカート11_1 (petticoat_core) | 2.9 in cross_legged | cross_legged |
| 35 | major | joint | body | joint:shoulder.L (joint:shoulder.L) | 0.60 in idol_dance@79 | idol_dance@79, jump_tuck, hands_behind_head, dance_sway, dance_heart, hands_behind_back |
| 36 | major | pen_frac | hair_front | 横髪長_0.R (hair_lock_R) | 4.7% in reach_up_back | reach_up_back |
| 37 | major | bone_pop | rig | ひざ補助.R (bones) | 7.9 in walk@11 | walk@11, turn@41 |
| 38 | major | pop | body | ひざ補助2.R (body) | 7.8 in walk@31 | walk@31, turn@41 |
| 39 | major | self | body | body:hand.R x upperarm.L (body:hand.R x upperarm.L) | 1.9 in hug_self | hug_self |
| 40 | major | stretch | petticoat | スカート14_2 (petticoat_tier1) | 2.16 in run@8 | run@8, spin@27, run_r |

## Issues by part (major / minor rows)

| part | major | minor |
|---|---|---|
| body | 51 | 133 |
| hair_front | 12 | 31 |
| hair/garment | 11 | 15 |
| sleeves | 9 | 78 |
| petticoat | 9 | 57 |
| skirt | 8 | 22 |
| accessories | 8 | 6 |
| rig | 4 | 2 |
| hair/skirt | 2 | 12 |
| hair_back | 1 | 14 |
| head | 0 | 13 |
| bodice | 0 | 12 |
| shoes | 0 | 6 |
| skirt/petticoat | 0 | 1 |
