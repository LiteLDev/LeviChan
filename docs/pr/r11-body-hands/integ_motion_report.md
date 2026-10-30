# Motion test report

Model: 64 meshes, 150683 vertices, 148540 faces (without outlines). Run time 1404 s. Not gated: the exit code of rig_check covers the core poses only. No cloth or hair physics: chains move only as keyed or driven (MMD simulates them).

Thresholds (minor / major): stretch 1.60/2.00, compress 0.30/0.12, flip 10/100, pen 1.0/2.0, pen_frac 0.5%/3.0%, self 0.5/1.5, contact 3.0/6.0, cross 40/400, joint 0.85/0.70, vol 0.80/0.65, knee -0.5/-5.0, elbow -5.0/-15.0, pop 2.0/6.0, bone_pop 2.0/6.0, jitter 0.03/0.08, speed 12.00/20.00, eye 0.8/1.5, span 0.70/1.00.
Cells: plain = ok, *italic* = minor, **bold** = major (location, frame for clips). pen/self/contact in cm, pop in mm; joint = median skin radius ratio at the worst joint band, vol = its mean squared radius ratio; knee/elbow = least signed bend (negative = hyperextended).

## core

| name | stretch | compress | flip | pen cm | pen % | contact cm | cross | joint | vol | knee | elbow | span |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| test | *1.83* (足.L) | **0.09** (足.L) | 8 | 0.2 | 0.0% | 0.2 | *182* (hair x skirt) | 0.97 | 0.80 | 59.8 | 69.3 | 0.58 |
| arms_up | *1.81* (腕捩.L) | 0.34 | 0 | 0.6 | 0.2% | - | **766** (hair x garment) | 0.93 | 0.86 | 0.0 | 41.4 | - |
| arms_forward | *1.80* (腕捩.L) | **0.07** (ひじ補助.R) | *40* (ひじ補助.L) | 0.4 | 0.0% | - | 0 | 0.98 | 0.99 | 0.0 | 139.4 | **1.28** (elbow.L) |
| wrist_twist_pos | 1.33 | 0.62 | 0 | 0.0 | 0.0% | - | 0 | 0.90 | 0.82 | 0.0 | 56.7 | - |
| wrist_twist_neg | 1.33 | 0.62 | 0 | 0.0 | 0.0% | - | 0 | 0.90 | 0.82 | 0.0 | 56.7 | - |
| squat | *1.85* (足.R) | **0.07** (足.L) | *26* (足.L) | 1.0 | *1.2%* (ひざ.L) | 2.9 | 0 | 0.97 | *0.77* (knee.R) | 106.4 | 29.3 | 0.61 |
| walk | 1.55 | 0.50 | 0 | 0.2 | 0.0% | - | **799** (hair x garment) | 0.99 | 0.92 | 30.7 | 38.1 | - |
| head_left | 1.40 | 0.47 | 0 | 0.4 | 0.0% | - | *111* (hair x garment) | 0.99 | 0.97 | 0.0 | 29.3 | - |
| head_right | 1.41 | 0.47 | 0 | 0.4 | 0.0% | - | *98* (hair x garment) | 0.99 | 0.97 | 0.0 | 29.3 | - |
| torso_left | 1.50 | 0.47 | 0 | 0.0 | 0.0% | - | 0 | 0.99 | 0.98 | 0.0 | 29.3 | - |
| torso_right | 1.55 | 0.51 | 0 | 0.1 | 0.0% | - | 0 | 0.99 | 0.98 | 0.0 | 29.3 | - |
| swing | 1.42 | 0.56 | 0 | 0.0 | 0.0% | - | *176* (hair x skirt) | 1.00 | 1.00 | 0.0 | 29.3 | - |
| fist | 1.55 | *0.22* (薬指１.L) | 0 | 0.0 | 0.0% | 0.3 | 0 | 1.00 | 1.00 | 0.0 | 45.0 | - |
| raise_bend | 1.45 | 0.49 | 0 | 0.6 | 0.1% | - | 0 | 0.99 | 1.00 | 0.0 | 69.3 | - |
| reach_forward | 1.59 | 0.32 | 0 | 0.0 | 0.0% | - | 0 | 0.99 | 0.98 | 0.0 | 95.5 | **1.29** (elbow.L) |
| forward_bend | 1.36 | 0.64 | 0 | 0.2 | 0.0% | - | 33 | 1.00 | 0.97 | 23.2 | 50.3 | - |
| side_bend | 1.48 | 0.65 | 0 | *1.8* (下半身) | *0.6%* (ひじ補助.L) | - | 32 | 0.99 | 0.98 | 0.0 | 29.3 | - |

## extended

| name | stretch | compress | flip | pen cm | pen % | self cm | contact cm | cross | joint | vol | knee | elbow | span |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| sit_chair | **2.22** (スカート5_2) | **0.10** (足.L) | 9 | 0.8 | *1.5%* (スカート11_0) | - | 0.1 | 18 | 0.97 | 0.82 | 91.0 | 69.3 | 0.56 |
| seiza | *1.78* (足.R) | **0.06** (足.R) | 10 | *1.4* (スカート14_1) | **3.0%** (腕捩.L) | - | *3.3* (shin.R x thigh.R) | 0 | 0.89 | **0.64** (knee.R) | 150.0 | 65.1 | 0.69 |
| kneel_one | *1.99* (スカート2_1) | **0.09** (足.R) | *19* (足.R) | 0.9 | *1.0%* (腕捩.R) | - | 2.6 | 21 | 0.96 | *0.75* (ankle.R) | 88.3 | 35.2 | **1.29** (elbow.L) |
| cross_legged | **3.24** (スカート5_2) | **0.04** (足.R) | *36* (足.L) | **3.3** (スカート3_1) | **8.2%** (スカート3_1) | **3.1** (thigh.L x thigh.R) | 1.9 | *226* (skirt x petticoat) | 0.96 | *0.70* (knee.L) | 124.7 | 52.7 | 0.65 |
| deep_lunge | *1.92* (スカート2_1) | *0.25* (足.R) | 0 | **2.6** (スカート14_2) | *2.4%* (スカート14_2) | - | - | 0 | 0.98 | 0.86 | 66.2 | 52.7 | 0.51 |
| run_l | *1.86* (足.L) | **0.05** (足.L) | 10 | *1.8* (スカート14_1) | **3.1%** (スカート14_2) | - | 1.5 | *259* (hair x garment) | 0.96 | *0.72* (knee.L) | 17.6 | 95.5 | **1.29** (elbow.R) |
| run_r | *1.86* (足.R) | **0.05** (足.R) | 10 | *1.3* (スカート2_0) | 0.3% | **5.1** (thigh.L x thigh.R) | 1.5 | *359* (hair x garment) | 0.96 | *0.72* (knee.R) | 17.6 | 95.5 | **1.29** (elbow.L) |
| jump_tuck | **2.44** (スカート5_2) | **0.09** (足.L) | *19* (足.L) | *1.6* (横髪巻_1.R) | **3.3%** (横髪巻_1.L) | - | 2.7 | *344* (hair x skirt) | *0.80* (shoulder.L) | *0.66* (knee.L) | 134.9 | 45.0 | 0.67 |
| high_kick | **2.09** (スカート9_2) | *0.22* (足補助.L) | 0 | *1.2* (スカート10_0) | *2.1%* (スカート10_0) | - | *5.7* (pelvis x thigh.L) | 0 | 0.95 | 0.92 | -0.0 | 35.2 | - |
| arms_crossed | *1.69* (袖胴.L) | *0.21* (ひじ補助.L) | 0 | *1.3* (袖胴.R) | *2.3%* (手捩.L) | **2.9** (forearm.L x forearm.R) | *3.6* (forearm.L x hand.R) | 0 | 0.97 | 0.98 | 0.0 | 109.4 | **1.27** (elbow.R) |
| hands_behind_head | *1.87* (袖胴.R) | *0.13* (ひじ補助.L) | *12* (袖_0.L) | 0.9 | *1.3%* (頭) | **4.6** (index.L x index.R) | *4.6* (index.L x middle.R) | **8254** (hair x garment) | *0.80* (shoulder.L) | **0.63** (shoulder.L) | 0.0 | 136.8 | **1.15** (elbow.R) |
| hands_behind_back | *1.66* (肩補助2.L) | 0.32 | 4 | *1.4* (手捩.L) | **4.8%** (手捩.L) | *1.1* (forearm.L x forearm.R) | - | *140* (hair x garment) | *0.85* (shoulder.R) | *0.73* (shoulder.R) | 0.0 | 99.9 | **1.28** (elbow.L) |
| hand_to_shoulder | *1.74* (袖胴.L) | *0.18* (腕捩.L) | 0 | **2.1** (手捩.L) | *2.2%* (手捩.L) | - | - | *70* (hair x garment) | 0.96 | 0.94 | 0.0 | 32.6 | **1.16** (elbow.L) |
| hands_on_hips | 1.57 | 0.36 | 2 | 0.8 | 0.3% | - | - | 0 | 0.92 | 0.87 | 0.0 | 86.7 | **1.20** (elbow.L) |
| reach_up_back | *1.72* (上半身2) | 0.35 | 8 | *1.4* (頭) | **12.1%** (頭) | 0.4 | - | **4727** (hair x garment) | 0.92 | 0.82 | 0.0 | 32.6 | - |
| hug_self | *1.76* (肩補助2.L) | *0.24* (ひじ補助.L) | 0 | **3.2** (手捩.L) | **11.9%** (手捩.L) | **3.3** (thumb.R x upperarm.L) | *3.6* (forearm.R x upperarm.L) | *53* (hair x garment) | 0.96 | 1.00 | 0.0 | 111.1 | **1.26** (elbow.L) |
| twist_bend | *1.63* (スカート14_0) | 0.63 | 0 | *1.7* (下半身) | *2.5%* (腕捩.L) | - | - | 1 | 0.98 | 0.93 | 25.3 | 29.3 | - |
| lie_back_elbows | **2.93** (スカート5_2) | *0.20* (下半身) | 2 | *1.2* (袖胴.L) | *1.0%* (スカート10_0) | - | - | *99* (hair x garment) | 0.98 | 0.94 | 8.0 | 99.9 | **1.24** (elbow.R) |
| look_over_shoulder | 1.59 | 0.45 | 0 | 0.5 | 0.0% | - | - | *110* (hair x garment) | 0.98 | 0.96 | 0.0 | 38.1 | - |
| curtsy | *1.65* (足.L) | 0.33 | 0 | 0.2 | 0.0% | 0.3 | - | 38 | 0.97 | 0.88 | 55.7 | 39.4 | 0.48 |
| dance_sway | *1.72* (上半身2) | 0.32 | *14* (袖_0.L) | *1.3* (横髪巻_1.L) | *1.7%* (横髪巻_1.L) | - | - | **966** (hair x garment) | *0.84* (shoulder.L) | **0.65** (shoulder.L) | 38.4 | 41.4 | **1.19** (elbow.R) |
| dance_point | *1.78* (袖胴.L) | *0.15* (ひじ補助.L) | 1 | **3.0** (手捩.L) | **6.4%** (手捩.L) | 0.3 | - | *125* (hair x garment) | 0.87 | *0.74* (shoulder.R) | 38.8 | 32.6 | **1.26** (elbow.L) |
| dance_heart | *1.68* (腕捩.L) | 0.31 | 2 | *1.4* (頭) | **8.7%** (頭) | **1.7** (hand.L x hand.R) | *4.0* (hand.R x thumb.L) | **5454** (hair x garment) | *0.84* (shoulder.L) | *0.71* (shoulder.L) | 33.5 | 108.6 | **1.31** (elbow.L) |
| dance_clap | *1.70* (足.L) | *0.26* (足.R) | 0 | *1.1* (手捩.R) | *1.5%* (手捩.R) | **2.5** (forearm.L x forearm.R) | *3.5* (hand.L x thumb.R) | 29 | 0.90 | 0.82 | 69.0 | 108.6 | **1.28** (elbow.R) |

## motion

| name | stretch | compress | flip | pen cm | pen % | self cm | contact cm | cross | joint | vol | knee | elbow | span | pop mm | bone pop mm | jitter | speed m/s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| walk | *1.62* (足.L) | 0.39 | 0 | *1.3* (スカート12_1) | *2.1%* (腕捩.R) | - | - | 34 | 0.99 | 0.89 | 26.9 | 36.9 | 0.47 | **8.0** (ひざ.R, f31) | **7.7** (中指３.L, f7) | *0.04* (スカート15_2) | 1.22 |
| run | *1.89* (スカート0_0) | **0.05** (足.R, f2) | *11* (足.R) | **2.8** (スカート15_2, f18) | **3.6%** (スカート15_2, f18) | **5.4** (thigh.L x thigh.R, f6) | *5.8* (pelvis x thigh.L) | **493** (hair x garment, f8) | 0.92 | *0.65* (knee.L) | 31.9 | 86.7 | **1.30** (elbow.L, f9) | **74.0** (スカート15_2, f16) | **68.1** (スカート15_2, f16) | **0.28** (スカート15_2, f5) | 3.55 |
| turn | *1.65* (足.L) | 0.35 | 0 | *1.1* (足首.R) | *1.0%* (足首.R) | *1.3* (foot.L x foot.R) | - | *97* (hair x garment) | 0.99 | 0.89 | 33.4 | 45.0 | 0.48 | *5.8* (ひざ.R) | *5.2* (足.R) | 0.02 | 1.62 |
| sit_stand | **2.22** (スカート5_2, f36) | **0.09** (足.L, f64) | 10 | **2.8** (スカート14_2, f69) | **4.1%** (スカート14_2, f70) | - | 0.1 | 15 | 0.97 | 0.81 | 0.0 | 35.2 | 0.57 | 1.7 | 0.0 | *0.05* (スカート0_2) | 0.82 |
| spin | *1.95* (スカート5_2) | 0.52 | 0 | 0.8 | 0.2% | - | - | **1109** (hair x skirt, f27) | 0.95 | 0.93 | 27.2 | 35.2 | - | **12.2** (後髪束6_4, f5) | **7.1** (後髪束8_3, f40) | 0.03 | 3.92 |
| idol_dance | **2.31** (上半身2, f78) | **0.05** (足.L, f72) | *48* (袖_0.L) | **5.4** (手捩.L, f74) | **15.8%** (手捩.L, f75) | **5.2** (forearm.L x thigh.L, f74) | *4.9* (hand.R x index.L) | **5454** (hair x garment, f48) | **0.58** (shoulder.L, f79) | **0.44** (shoulder.L, f79) | 0.0 | 29.3 | **1.31** (elbow.R, f51) | **54.8** (ひざ.L, f60) | **53.8** (ひざ.L, f60) | **0.69** (腕D.L, f78) | 6.59 |

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
| 1 | major | cross | hair/garment | hair x garment (hair x garment) | 8254 in hands_behind_head | hands_behind_head, dance_heart, idol_dance@48, reach_up_back, dance_sway, walk, arms_up, run@8, run_r, jump_tuck, run_l, hands_behind_back, test, dance_point... |
| 2 | major | pop | skirt | スカート15_2 (skirt) | 74.0 in run@16 | run@16 |
| 3 | major | bone_pop | rig | スカート15_2 (bones) | 68.1 in run@16 | run@16 |
| 4 | major | jitter | body | 腕D.L (body) | 0.69 in idol_dance@78 | idol_dance@78 |
| 5 | major | pop | body | ひざ.L (body) | 54.8 in idol_dance@60 | idol_dance@60 |
| 6 | major | bone_pop | rig | ひざ.L (bones) | 53.8 in idol_dance@60 | idol_dance@60 |
| 7 | major | pen_frac | sleeves | 手捩.L (sleeve_cuff) | 15.8% in idol_dance@75 | idol_dance@75, idol_dance@74, hug_self, dance_point, hands_behind_back, arms_crossed, hand_to_shoulder |
| 8 | major | jitter | petticoat | スカート15_2 (petticoat_core) | 0.28 in run@5 | run@5, walk@41 |
| 9 | major | self | body | body:thigh.L x thigh.R (body:thigh.L x thigh.R) | 5.4 in run@6 | run@6, run_r, cross_legged |
| 10 | major | self | body | body:forearm.L x thigh.L (body:forearm.L x thigh.L) | 5.2 in idol_dance@74 | idol_dance@74 |
| 11 | major | pen_frac | accessories | 頭 (acc_leaves_L) | 12.1% in reach_up_back | reach_up_back, dance_heart, idol_dance@48 |
| 12 | major | pen | sleeves | 手捩.L (sleeve_cuff) | 5.4 in idol_dance@74 | idol_dance@74, idol_dance@75, hug_self, dance_point, hand_to_shoulder, hands_behind_back, arms_crossed |
| 13 | major | self | body | body:ring.L x thigh.L (body:ring.L x thigh.L) | 4.7 in idol_dance@75 | idol_dance@75 |
| 14 | major | stretch | petticoat | スカート5_2 (petticoat_core) | 3.24 in cross_legged | cross_legged, lie_back_elbows, jump_tuck, sit_chair, sit_stand@36, spin@28, seiza |
| 15 | major | self | body | body:index.L x index.R (body:index.L x index.R) | 4.6 in hands_behind_head | hands_behind_head |
| 16 | major | self | body | body:ring.L x ring.R (body:ring.L x ring.R) | 4.5 in hands_behind_head | hands_behind_head, idol_dance@45 |
| 17 | major | self | body | body:middle.L x middle.R (body:middle.L x middle.R) | 4.4 in hands_behind_head | hands_behind_head, idol_dance@44 |
| 18 | major | self | body | body:hand.L x thigh.L (body:hand.L x thigh.L) | 4.1 in idol_dance@75 | idol_dance@75 |
| 19 | major | self | body | body:little.L x thigh.L (body:little.L x thigh.L) | 3.7 in idol_dance@75 | idol_dance@75 |
| 20 | major | pen_frac | petticoat | スカート3_1 (petticoat_core) | 8.2% in cross_legged | cross_legged |
| 21 | major | cross | hair/skirt | hair x skirt (hair x skirt) | 1109 in spin@27 | spin@27, jump_tuck, test, swing |
| 22 | major | self | body | body:middle.L x thigh.L (body:middle.L x thigh.L) | 3.5 in idol_dance@74 | idol_dance@74 |
| 23 | major | self | body | body:thumb.L x thumb.R (body:thumb.L x thumb.R) | 3.4 in idol_dance@38 | idol_dance@38, dance_heart |
| 24 | major | self | body | body:thumb.R x upperarm.L (body:thumb.R x upperarm.L) | 3.3 in hug_self | hug_self |
| 25 | major | self | body | body:index.L x thigh.L (body:index.L x thigh.L) | 3.2 in idol_dance@74 | idol_dance@74 |
| 26 | major | self | body | body:forearm.L x pelvis (body:forearm.L x pelvis) | 3.2 in idol_dance@75 | idol_dance@75 |
| 27 | major | self | body | body:forearm.L x forearm.R (body:forearm.L x forearm.R) | 3.1 in idol_dance@35 | idol_dance@35, arms_crossed, dance_clap, hands_behind_back |
| 28 | major | self | body | body:hand.L x hand.R (body:hand.L x hand.R) | 3.1 in idol_dance@35 | idol_dance@35, dance_heart, dance_clap |
| 29 | major | pop | hair_back | 後髪束6_4 (hair_back_side) | 12.2 in spin@5 | spin@5 |
| 30 | major | vol | body | joint:shoulder.L (joint:shoulder.L) | 0.44 in idol_dance@79 | idol_dance@79, hands_behind_head, dance_sway, jump_tuck, dance_heart, hands_behind_back |
| 31 | major | pen | petticoat | スカート3_1 (petticoat_core) | 3.3 in cross_legged | cross_legged |
| 32 | major | pen_frac | hair_front | 横髪奥_0.L (hair_curtain_L) | 6.0% in idol_dance@80 | idol_dance@80, reach_up_back |
| 33 | major | stretch | skirt | スカート6_2 (skirt) | 2.47 in cross_legged | cross_legged, lie_back_elbows, jump_tuck, sit_chair, sit_stand@36 |
| 34 | major | pen_frac | hair_front | 横髪巻_1.L (hair_curl_L) | 5.9% in idol_dance@54 | idol_dance@54, jump_tuck, dance_sway |
| 35 | major | pen_frac | hair_front | 横髪巻_1.R (hair_curl_R) | 5.8% in idol_dance@53 | idol_dance@53, jump_tuck |
| 36 | major | stretch | body | 足補助.L (body) | 2.44 in cross_legged | cross_legged, lie_back_elbows |
| 37 | major | pen_frac | hair_front | 頭 (hair_bangs) | 5.7% in idol_dance@45 | idol_dance@45, dance_heart, idol_dance@49, idol_dance@48, hands_behind_head |
| 38 | major | span | body | elbow.R (span:elbow.R) | 1.31 in idol_dance@51 | idol_dance@51, dance_heart, run@17, run_l, reach_forward, dance_clap, hands_behind_back, arms_forward, arms_crossed, hug_self, run_r, lie_back_elbows, hands_... |
| 39 | major | span | body | elbow.L (span:elbow.L) | 1.31 in idol_dance@51 | idol_dance@51, dance_heart, run@9, run_r, reach_forward, kneel_one, dance_clap, hands_behind_back, arms_forward, arms_crossed, dance_point, hug_self, run_l, ... |
| 40 | major | stretch | petticoat | スカート6_2 (petticoat_tier1) | 2.35 in cross_legged | cross_legged, lie_back_elbows, jump_tuck, sit_chair, sit_stand@36 |

## Issues by part (major / minor rows)

| part | major | minor |
|---|---|---|
| body | 84 | 118 |
| petticoat | 32 | 70 |
| sleeves | 18 | 66 |
| hair_front | 11 | 21 |
| accessories | 9 | 7 |
| hair/garment | 8 | 14 |
| skirt | 6 | 22 |
| rig | 4 | 1 |
| bodice | 1 | 10 |
| hair_back | 1 | 6 |
| hair/skirt | 1 | 3 |
| head | 0 | 13 |
| shoes | 0 | 7 |
| skirt/petticoat | 0 | 1 |
| tier1/tier2 | 0 | 1 |
