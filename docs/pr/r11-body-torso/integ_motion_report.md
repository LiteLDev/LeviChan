# Motion test report

Model: 62 meshes, 163924 vertices, 162561 faces (without outlines). Run time 2246 s. Not gated: the exit code of rig_check covers the core poses only. No cloth or hair physics: chains move only as keyed or driven (MMD simulates them).

Thresholds (minor / major): stretch 1.60/2.00, compress 0.30/0.12, flip 10/100, pen 1.0/2.0, pen_frac 0.5%/3.0%, self 0.5/1.5, contact 3.0/6.0, cross 40/400, joint 0.85/0.70, vol 0.80/0.65, knee -0.5/-5.0, elbow -5.0/-15.0, pop 2.0/6.0, bone_pop 2.0/6.0, jitter 0.03/0.08, speed 12.00/20.00, eye 0.8/1.5, span 0.70/1.00.
Cells: plain = ok, *italic* = minor, **bold** = major (location, frame for clips). pen/self/contact in cm, pop in mm; joint = median skin radius ratio at the worst joint band, vol = its mean squared radius ratio; knee/elbow = least signed bend (negative = hyperextended).

## core

| name | stretch | compress | flip | pen cm | pen % | contact cm | cross | joint | vol | knee | elbow | span |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| test | *1.80* (足.L) | *0.12* (ひざ.L) | 1 | 0.4 | 0.0% | 0.2 | *162* (hair x skirt) | 0.97 | 0.81 | 59.9 | 69.3 | 0.60 |
| arms_up | *1.81* (腕捩.L) | 0.34 | 0 | 0.6 | 0.2% | - | **764** (hair x garment) | 0.93 | 0.86 | 0.0 | 41.4 | - |
| arms_forward | *1.80* (腕捩.L) | **0.06** (ひじ補助.L) | *40* (ひじ補助.L) | 0.4 | 0.0% | - | 0 | 0.98 | 0.99 | 0.0 | 139.4 | **1.28** (elbow.L) |
| wrist_twist_pos | 1.33 | 0.62 | 0 | 0.0 | 0.0% | - | 0 | 0.90 | 0.82 | 0.0 | 56.7 | - |
| wrist_twist_neg | 1.33 | 0.62 | 0 | 0.0 | 0.0% | - | 0 | 0.90 | 0.82 | 0.0 | 56.7 | - |
| squat | *1.82* (足.L) | **0.11** (足首.R) | 6 | *1.2* (ひざ.L) | *1.3%* (ひざ.L) | 0.7 | 0 | 0.97 | *0.79* (knee.L) | 106.4 | 29.3 | 0.62 |
| walk | 1.57 | 0.43 | 0 | 0.2 | 0.0% | - | **1012** (hair x garment) | 0.99 | 0.91 | 30.7 | 38.1 | 0.41 |
| head_left | 1.40 | 0.47 | 0 | 0.2 | 0.0% | - | *133* (hair x garment) | 0.98 | 0.96 | 0.0 | 29.3 | - |
| head_right | 1.41 | 0.47 | 0 | 0.2 | 0.0% | - | *113* (hair x garment) | 0.98 | 0.96 | 0.0 | 29.3 | - |
| torso_left | 1.24 | 0.77 | 0 | 0.0 | 0.0% | - | 0 | 0.99 | 0.98 | 0.0 | 29.3 | - |
| torso_right | 1.24 | 0.77 | 0 | 0.0 | 0.0% | - | 0 | 0.99 | 0.98 | 0.0 | 29.3 | - |
| swing | 1.56 | 0.73 | 0 | 0.0 | 0.0% | - | *176* (hair x skirt) | 1.00 | 1.00 | 0.0 | 29.3 | - |
| fist | 1.55 | *0.22* (薬指１.L) | 0 | 0.0 | 0.0% | 0.3 | 0 | 1.00 | 1.00 | 0.0 | 45.0 | - |
| raise_bend | 1.45 | 0.49 | 0 | 0.6 | 0.1% | - | 0 | 0.99 | 1.00 | 0.0 | 69.3 | - |
| reach_forward | 1.59 | 0.32 | 0 | 0.0 | 0.0% | - | 0 | 0.99 | 0.98 | 0.0 | 95.5 | **1.29** (elbow.L) |
| forward_bend | 1.28 | 0.50 | 0 | 0.2 | 0.0% | - | *41* (hair x garment) | 0.99 | 0.96 | 23.3 | 50.3 | - |
| side_bend | 1.48 | 0.65 | 0 | *1.8* (下半身) | 0.3% | - | 0 | 0.99 | 0.99 | 0.0 | 29.3 | - |

## extended

| name | stretch | compress | flip | pen cm | pen % | self cm | contact cm | cross | joint | vol | knee | elbow | span |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| sit_chair | *1.79* (足.L) | *0.14* (ひざ.L) | 0 | 0.9 | *1.9%* (スカート3_0) | - | - | 19 | 0.98 | 0.81 | 91.0 | 69.3 | 0.58 |
| seiza | *1.78* (足.L) | *0.15* (ひざ.L) | *14* (足.L) | 0.9 | **3.0%** (腕捩.L) | - | *3.1* (shin.L x thigh.L) | 0 | 0.91 | **0.65** (knee.L) | 149.9 | 65.1 | *0.71* (knee.R) |
| kneel_one | *1.83* (足.R) | **0.09** (足.R) | *14* (足首.R) | 0.8 | *1.0%* (腕捩.R) | - | 1.7 | 21 | 0.96 | *0.70* (ankle.R) | 88.3 | 35.2 | **1.29** (elbow.L) |
| cross_legged | **2.27** (足補助.R) | **0.05** (スカート14_2) | *12* (足.L) | **2.3** (スカート4_1) | **6.0%** (スカート4_1) | - | 1.9 | *226* (skirt x petticoat) | 0.93 | *0.71* (knee.L) | 124.9 | 52.7 | 0.66 |
| deep_lunge | *1.80* (スカート3_2) | *0.27* (足.R) | 0 | 0.6 | *0.6%* (スカート12_0) | - | - | 0 | 0.97 | 0.80 | 66.2 | 52.7 | 0.53 |
| run_l | *1.83* (足.L) | **0.11** (ひざ.L) | 6 | *1.3* (スカート13_0) | 0.1% | - | 1.4 | *325* (hair x garment) | 0.97 | *0.74* (knee.L) | 17.7 | 95.5 | **1.29** (elbow.R) |
| run_r | *1.83* (足.R) | **0.11** (足.R) | 5 | *1.2* (スカート2_0) | 0.1% | - | 1.4 | **406** (hair x garment) | 0.97 | *0.74* (knee.R) | 17.7 | 95.5 | **1.29** (elbow.L) |
| jump_tuck | *1.92* (スカート13_2) | *0.14* (ひざ.L) | *16* (下半身) | *1.6* (横髪巻_1.L) | **3.3%** (横髪巻_1.L) | - | 2.6 | *312* (hair x garment) | *0.80* (shoulder.L) | *0.67* (shoulder.L) | 134.8 | 45.0 | 0.67 |
| high_kick | *1.88* (スカート2_0) | 0.36 | 2 | *1.2* (スカート10_0) | *1.5%* (スカート10_0) | - | - | 0 | 0.95 | *0.75* (hip.L) | 0.0 | 35.2 | - |
| arms_crossed | *1.69* (袖胴.L) | *0.21* (ひじ補助.L) | 0 | *1.3* (袖胴.R) | *2.2%* (手捩.L) | **2.9** (forearm.L x forearm.R) | *3.6* (forearm.L x hand.R) | 0 | 0.97 | 0.98 | 0.0 | 109.4 | **1.27** (elbow.R) |
| hands_behind_head | *1.87* (袖胴.R) | *0.13* (ひじ補助.L) | *12* (袖_0.L) | *1.1* (頭) | *1.3%* (頭) | **4.6** (index.L x index.R) | *4.6* (index.L x middle.R) | **7348** (hair x garment) | *0.80* (shoulder.L) | **0.63** (shoulder.L) | 0.0 | 136.8 | **1.15** (elbow.L) |
| hands_behind_back | *1.66* (肩補助2.L) | 0.32 | 4 | *1.5* (手捩.L) | **4.4%** (手捩.L) | *1.1* (forearm.L x forearm.R) | - | *110* (hair x garment) | *0.85* (shoulder.R) | *0.73* (shoulder.L) | 0.0 | 99.9 | **1.28** (elbow.L) |
| hand_to_shoulder | *1.74* (袖胴.L) | *0.18* (腕捩.L) | 0 | *1.2* (スカート3_1) | *2.5%* (手捩.L) | - | - | *85* (hair x garment) | 0.96 | 0.94 | 0.0 | 32.6 | **1.16** (elbow.L) |
| hands_on_hips | 1.55 | 0.36 | 2 | 0.8 | 0.3% | - | - | 0 | 0.92 | 0.87 | 0.0 | 86.7 | **1.20** (elbow.L) |
| reach_up_back | *1.72* (上半身2) | 0.34 | 8 | *1.4* (頭) | **12.1%** (頭) | 0.4 | - | **4704** (hair x garment) | 0.92 | 0.82 | 0.0 | 32.6 | - |
| hug_self | *1.76* (肩補助2.L) | *0.24* (ひじ補助.L) | 0 | **2.8** (手捩.L) | **12.8%** (手捩.L) | **3.3** (thumb.R x upperarm.L) | *3.6* (forearm.R x upperarm.L) | *45* (hair x garment) | 0.96 | 1.00 | 0.0 | 111.1 | **1.26** (elbow.L) |
| twist_bend | 1.32 | 0.62 | 0 | *1.7* (下半身) | *2.5%* (腕捩.L) | - | - | 0 | 0.98 | 0.93 | 25.4 | 29.3 | - |
| lie_back_elbows | **2.04** (スカート5_2) | *0.22* (ひじ補助.R) | 0 | *1.2* (袖胴.R) | *1.9%* (スカート10_0) | - | - | *81* (hair x garment) | 0.95 | 0.82 | 8.0 | 99.9 | **1.24** (elbow.R) |
| look_over_shoulder | 1.55 | 0.65 | 0 | 0.5 | 0.0% | - | - | *100* (hair x garment) | 0.98 | 0.95 | 0.0 | 38.1 | - |
| curtsy | *1.64* (ひざ.L) | 0.35 | 0 | 0.2 | 0.0% | 0.3 | - | 33 | 0.97 | 0.89 | 55.8 | 39.4 | 0.51 |
| dance_sway | *1.72* (上半身2) | 0.31 | *13* (袖_0.L) | *1.3* (横髪巻_1.L) | *1.7%* (横髪巻_1.L) | - | - | **985** (hair x garment) | *0.84* (shoulder.L) | **0.65** (shoulder.L) | 38.5 | 41.4 | **1.19** (elbow.R) |
| dance_point | *1.78* (袖胴.L) | *0.16* (ひじ補助.L) | 1 | **2.3** (手捩.L) | **7.6%** (手捩.L) | 0.3 | - | *147* (hair x garment) | 0.87 | *0.74* (shoulder.R) | 38.8 | 32.6 | **1.26** (elbow.L) |
| dance_heart | *1.68* (腕捩.L) | 0.31 | 2 | *1.4* (頭) | **8.7%** (頭) | **1.7** (hand.L x hand.R) | *4.0* (hand.R x thumb.L) | **6032** (hair x garment) | *0.84* (shoulder.L) | *0.71* (shoulder.L) | 33.6 | 108.6 | **1.31** (elbow.L) |
| dance_clap | *1.68* (ひざ.L) | *0.27* (ひじ補助.R) | 0 | *1.2* (手捩.L) | *2.8%* (手捩.L) | **2.5** (forearm.L x forearm.R) | *3.5* (hand.L x thumb.R) | 17 | 0.90 | 0.82 | 69.0 | 108.6 | **1.28** (elbow.L) |

## motion

| name | stretch | compress | flip | pen cm | pen % | self cm | contact cm | cross | joint | vol | knee | elbow | span | pop mm | bone pop mm | jitter | speed m/s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| walk | *1.60* (ひざ.L) | 0.41 | 0 | *1.3* (スカート12_1) | *2.1%* (腕捩.R) | - | - | *49* (hair x garment) | 0.99 | 0.90 | 26.9 | 36.9 | 0.49 | **9.6** (スカート15_2, f20) | **8.6** (スカート15_2, f50) | *0.04* (スカート15_2) | 1.22 |
| run | *1.88* (スカート1_2) | **0.10** (足.R, f6) | 7 | *1.3* (スカート13_0) | *0.8%* (腕捩.R) | - | 2.8 | **532** (hair x garment, f18) | 0.94 | *0.66* (knee.L) | 32.0 | 86.7 | **1.30** (elbow.L, f7) | **55.0** (スカート1_2, f6) | **52.8** (スカート1_2, f6) | **0.22** (スカート0_0, f5) | 3.55 |
| turn | *1.63* (ひざ.L) | 0.37 | 0 | *1.4* (足首.R) | *1.2%* (足首.R) | *1.2* (foot.L x foot.R) | - | *118* (hair x garment) | 0.99 | 0.89 | 33.4 | 45.0 | 0.50 | *5.8* (ひざ.R) | *5.2* (ひざ.R) | 0.02 | 1.62 |
| sit_stand | *1.79* (足.L) | *0.13* (ひざ.L) | 1 | *1.6* (スカート2_0) | *2.1%* (スカート3_0) | - | 0.1 | 15 | 0.98 | 0.81 | 0.0 | 35.2 | 0.59 | *3.7* (スカート3_2) | *4.0* (スカート3_2) | *0.04* (スカート13_2) | 0.82 |
| spin | *1.76* (スカート1_2) | 0.52 | 0 | 0.8 | 0.2% | - | - | **1044** (hair x skirt, f8) | 0.95 | 0.93 | 27.3 | 35.2 | - | **15.7** (後髪束8_4, f40) | **13.5** (後髪束8_4, f40) | *0.03* (後髪束9_2) | 3.92 |
| idol_dance | **2.25** (上半身2, f78) | **0.09** (ひざ.L, f74) | *48* (袖_0.L) | **4.9** (手捩.L, f74) | **16.7%** (手捩.L, f74) | **4.9** (middle.L x thigh.L, f74) | *4.9* (hand.R x index.L) | **6032** (hair x garment, f48) | **0.58** (shoulder.L, f79) | **0.44** (shoulder.L, f79) | 0.0 | 29.3 | **1.31** (elbow.R, f51) | **55.0** (ひざ.L, f60) | **54.0** (足.L, f60) | **0.69** (腕D.L, f78) | 6.59 |

## eyes (gaze at the limits x eye morphs)

| case | poke mm | where |
|---|---|---|
| gaze | 0.00 (ok) | eyes  |
| gaze+まばたき | 0.64 (ok) | head_eye_L gaze -10/-8 |
| gaze+まばたき=0.5 | 0.54 (ok) | head_eye_L gaze -10/+8 |
| gaze+ウィンク | 0.00 (ok) | eyes  |
| gaze+ウィンク右 | 0.00 (ok) | eyes  |
| gaze+笑い | 0.00 (ok) | eyes  |
| gaze+はぅ | 0.00 (ok) | eyes  |
| gaze+はぅ=0.5 | 0.05 (ok) | head_eye_L gaze -10/+8 |
| gaze+なごみ | 0.00 (ok) | eyes  |
| gaze+びっくり | 0.00 (ok) | eyes  |
| gaze+じと目 | 0.00 (ok) | eyes  |
| gaze+キリッ | 0.00 (ok) | eyes  |
| gaze+瞳小 | 0.00 (ok) | eyes  |
| gaze+ハイライト消 | 0.00 (ok) | eyes  |
| gaze+真面目 | 0.00 (ok) | eyes  |
| gaze+困る | 0.00 (ok) | eyes  |
| gaze+にこり | 0.00 (ok) | eyes  |
| gaze+怒り | 0.00 (ok) | eyes  |
| gaze+上 | 0.00 (ok) | eyes  |
| gaze+下 | 0.00 (ok) | eyes  |

## Top problems (grouped by metric, part and location)

| # | level | metric | part | location | worst | in |
|---|---|---|---|---|---|---|
| 1 | major | cross | hair/garment | hair x garment (hair x garment) | 7348 in hands_behind_head | hands_behind_head, dance_heart, idol_dance@48, reach_up_back, walk, dance_sway, arms_up, run@18, run_r, run_l, jump_tuck, dance_point, head_left, turn@17, te... |
| 2 | major | jitter | body | 腕D.L (body) | 0.69 in idol_dance@78 | idol_dance@78 |
| 3 | major | pop | skirt | スカート1_2 (skirt) | 55.0 in run@6 | run@6 |
| 4 | major | pop | body | ひざ.L (body) | 55.0 in idol_dance@60 | idol_dance@60 |
| 5 | major | bone_pop | rig | 足.L (bones) | 54.0 in idol_dance@60 | idol_dance@60 |
| 6 | major | bone_pop | rig | スカート1_2 (bones) | 52.8 in run@6 | run@6 |
| 7 | major | pen_frac | sleeves | 手捩.L (sleeve_cuff) | 16.7% in idol_dance@74 | idol_dance@74, idol_dance@75, hug_self, dance_point, hands_behind_back, dance_clap, hand_to_shoulder, arms_crossed |
| 8 | major | pen_frac | accessories | 頭 (acc_leaves_L) | 12.1% in reach_up_back | reach_up_back, dance_heart, idol_dance@48 |
| 9 | major | self | body | body:middle.L x thigh.L (body:middle.L x thigh.L) | 4.9 in idol_dance@74 | idol_dance@74 |
| 10 | major | self | body | body:forearm.L x thigh.L (body:forearm.L x thigh.L) | 4.8 in idol_dance@74 | idol_dance@74 |
| 11 | major | self | body | body:index.L x index.R (body:index.L x index.R) | 4.6 in hands_behind_head | hands_behind_head |
| 12 | major | self | body | body:ring.L x ring.R (body:ring.L x ring.R) | 4.5 in hands_behind_head | hands_behind_head, idol_dance@45 |
| 13 | major | self | body | body:middle.L x middle.R (body:middle.L x middle.R) | 4.4 in hands_behind_head | hands_behind_head, idol_dance@44 |
| 14 | major | pen | sleeves | 手捩.L (sleeve_cuff) | 4.9 in idol_dance@74 | idol_dance@74, hug_self, dance_point, hands_behind_back, arms_crossed, dance_clap, hand_to_shoulder |
| 15 | major | self | body | body:hand.L x thigh.L (body:hand.L x thigh.L) | 4.4 in idol_dance@75 | idol_dance@75 |
| 16 | major | jitter | bodice | スカート0_0 (bodice_ribbon_tails) | 0.22 in run@5 | run@5 |
| 17 | major | self | body | body:index.L x thigh.L (body:index.L x thigh.L) | 4.1 in idol_dance@75 | idol_dance@75 |
| 18 | major | pop | hair_back | 後髪束8_4 (hair_back) | 15.7 in spin@40 | spin@40 |
| 19 | major | self | body | body:forearm.L x pelvis (body:forearm.L x pelvis) | 3.5 in idol_dance@74 | idol_dance@74 |
| 20 | major | self | body | body:thumb.L x thumb.R (body:thumb.L x thumb.R) | 3.4 in idol_dance@38 | idol_dance@38, dance_heart |
| 21 | major | bone_pop | rig | 後髪束8_4 (bones) | 13.5 in spin@40 | spin@40 |
| 22 | major | self | body | body:thumb.R x upperarm.L (body:thumb.R x upperarm.L) | 3.3 in hug_self | hug_self |
| 23 | major | cross | hair/skirt | hair x skirt (hair x skirt) | 1044 in spin@8 | spin@8, jump_tuck, swing, test |
| 24 | major | self | body | body:forearm.L x forearm.R (body:forearm.L x forearm.R) | 3.1 in idol_dance@35 | idol_dance@35, arms_crossed, dance_clap, hands_behind_back |
| 25 | major | self | body | body:hand.L x hand.R (body:hand.L x hand.R) | 3.1 in idol_dance@35 | idol_dance@35, dance_heart, dance_clap |
| 26 | major | vol | body | joint:shoulder.L (joint:shoulder.L) | 0.44 in idol_dance@79 | idol_dance@79, hands_behind_head, dance_sway, jump_tuck, dance_heart, hands_behind_back |
| 27 | major | pen_frac | hair_front | 横髪奥_0.L (hair_curtain_L) | 6.0% in idol_dance@80 | idol_dance@80, reach_up_back |
| 28 | major | pen_frac | petticoat | スカート4_1 (petticoat_core) | 6.0% in cross_legged | cross_legged |
| 29 | major | pen_frac | hair_front | 横髪巻_1.L (hair_curl_L) | 5.9% in idol_dance@54 | idol_dance@54, jump_tuck, dance_sway |
| 30 | major | pen_frac | hair_front | 横髪巻_1.R (hair_curl_R) | 5.9% in idol_dance@53 | idol_dance@53, jump_tuck |
| 31 | major | pen_frac | hair_front | 頭 (hair_bangs) | 5.6% in idol_dance@45 | idol_dance@45, dance_heart, idol_dance@49, idol_dance@48, hands_behind_head, idol_dance@46 |
| 32 | major | self | body | body:little.L x thigh.L (body:little.L x thigh.L) | 2.5 in idol_dance@75 | idol_dance@75 |
| 33 | major | span | body | elbow.R (span:elbow.R) | 1.31 in idol_dance@51 | idol_dance@51, dance_heart, run@19, run_l, reach_forward, dance_clap, hands_behind_back, arms_forward, arms_crossed, hug_self, run_r, lie_back_elbows, hands_... |
| 34 | major | span | body | elbow.L (span:elbow.L) | 1.31 in idol_dance@51 | idol_dance@51, dance_heart, run@7, run_r, reach_forward, kneel_one, dance_clap, hands_behind_back, arms_forward, arms_crossed, dance_point, hug_self, run_l, ... |
| 35 | major | pop | skirt | スカート15_2 (skirt) | 9.6 in walk@20 | walk@20 |
| 36 | major | joint | body | joint:shoulder.L (joint:shoulder.L) | 0.58 in idol_dance@79 | idol_dance@79, jump_tuck, hands_behind_head, dance_sway, dance_heart, hands_behind_back |
| 37 | major | stretch | body | 足補助.R (body) | 2.27 in cross_legged | cross_legged |
| 38 | major | bone_pop | rig | スカート15_2 (bones) | 8.6 in walk@50 | walk@50 |
| 39 | major | self | body | body:ring.L x thigh.L (body:ring.L x thigh.L) | 2.1 in idol_dance@75 | idol_dance@75 |
| 40 | major | stretch | accessories | 上半身2 (acc_halter) | 2.25 in idol_dance@78 | idol_dance@78, reach_up_back |

## Issues by part (major / minor rows)

| part | major | minor |
|---|---|---|
| body | 74 | 117 |
| sleeves | 17 | 64 |
| hair_front | 11 | 22 |
| hair/garment | 9 | 15 |
| accessories | 9 | 7 |
| petticoat | 7 | 60 |
| skirt | 4 | 23 |
| rig | 4 | 2 |
| bodice | 2 | 15 |
| hair_back | 1 | 9 |
| hair/skirt | 1 | 3 |
| shoes | 0 | 8 |
| skirt/petticoat | 0 | 1 |
