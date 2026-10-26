# Motion test report

Model: 50 meshes, 72051 vertices, 70886 faces (without outlines). Run time 628 s. Not gated: the exit code of rig_check covers the core poses only. No cloth or hair physics: chains move only as keyed or driven (MMD simulates them).

Thresholds (minor / major): stretch 1.60/2.00, compress 0.30/0.12, flip 10/100, pen 1.0/2.0, pen_frac 0.5%/3.0%, self 0.5/1.5, contact 3.0/6.0, cross 40/400, joint 0.85/0.70, vol 0.80/0.65, knee -0.5/-5.0, elbow -5.0/-15.0, pop 2.0/6.0, bone_pop 2.0/6.0, jitter 0.03/0.08, speed 12.00/20.00, eye 0.8/1.5.
Cells: plain = ok, *italic* = minor, **bold** = major (location, frame for clips). pen/self/contact in cm, pop in mm; joint = median skin radius ratio at the worst joint band, vol = its mean squared radius ratio; knee/elbow = least signed bend (negative = hyperextended).

## core

| name | stretch | compress | flip | pen cm | pen % | contact cm | cross | joint | vol | knee | elbow |
|---|---|---|---|---|---|---|---|---|---|---|---|
| test | *1.74* (ひざ.L) | *0.15* (ひざ補助.L) | *20* (ひざ補助.L) | 0.3 | 0.0% | - | **1202** (hair x skirt) | 0.95 | *0.75* (knee.L) | 59.8 | 69.2 |
| arms_up | *1.85* (手捩.R) | 0.34 | *14* (腕D.L) | *1.5* (腕捩.R) | **7.3%** (上半身2) | - | **827** (hair x garment) | 0.93 | *0.76* (shoulder.R) | -0.0 | 41.5 |
| arms_forward | *1.73* (ひじ.L) | **0.05** (ひじ補助.L) | **220** (ひじ補助.L) | *1.6* (ひじ.L) | *1.0%* (ひじ.L) | - | 0 | 0.96 | 0.97 | 0.0 | 139.4 |
| wrist_twist_pos | 1.36 | 0.54 | 0 | 0.0 | 0.0% | - | 0 | 0.90 | 0.81 | 0.0 | 56.7 |
| wrist_twist_neg | 1.36 | 0.54 | 0 | 0.0 | 0.0% | - | 0 | 0.91 | 0.80 | 0.0 | 56.7 |
| squat | *1.83* (ひざ.R) | *0.15* (ひざ補助.L) | *78* (ひざ補助.L) | 0.8 | *2.2%* (足首.L) | 1.3 | 0 | 0.95 | *0.72* (knee.L) | 113.2 | 29.7 |
| walk | 1.53 | 0.48 | 0 | *1.6* (後髪束12_2) | 0.1% | - | **1907** (hair x skirt) | 0.97 | 0.90 | 29.5 | 38.3 |
| head_left | 1.47 | 0.60 | 0 | 0.2 | 0.0% | - | **2152** (hair x skirt) | 0.99 | 0.97 | 0.0 | 29.7 |
| head_right | 1.47 | 0.60 | 0 | 0.3 | 0.0% | - | **1909** (hair x skirt) | 0.99 | 0.97 | 0.0 | 29.7 |
| torso_left | 1.20 | 0.78 | 0 | 0.0 | 0.0% | - | **2373** (hair x skirt) | 0.99 | 0.98 | 0.0 | 29.7 |
| torso_right | 1.22 | 0.82 | 0 | 0.0 | 0.0% | - | **2151** (hair x skirt) | 0.99 | 0.98 | 0.0 | 29.7 |
| swing | 1.54 | 0.79 | 0 | 0.1 | 0.0% | - | *90* (hair x skirt) | 1.00 | 1.00 | 0.0 | 29.7 |
| fist | *1.68* (手首.L) | *0.24* (手首.L) | 0 | 0.0 | 0.0% | - | 0 | 1.00 | 0.99 | 0.0 | 45.1 |
| raise_bend | 1.50 | 0.39 | 0 | 1.0 | *0.5%* (腕捩.R) | - | *102* (hair x garment) | 1.00 | 1.00 | 0.0 | 69.2 |
| reach_forward | *1.65* (ひじ.R) | *0.17* (ひじ補助.R) | 0 | 0.1 | 0.0% | - | 0 | 0.97 | 0.97 | 0.0 | 95.3 |
| forward_bend | 1.45 | *0.26* (首) | 0 | 0.3 | 0.0% | - | 18 | 0.98 | 0.95 | 21.0 | 50.5 |
| side_bend | 1.47 | 0.55 | 0 | *1.7* (下半身) | **6.5%** (横髪巻_2.R) | - | **2125** (hair x skirt) | 1.00 | 0.99 | 0.0 | 29.7 |

## extended

| name | stretch | compress | flip | pen cm | pen % | self cm | contact cm | cross | joint | vol | knee | elbow |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| sit_chair | *1.90* (足.L) | *0.15* (ひざ補助.L) | *20* (ひざ補助.L) | **3.9** (スカート15_0) | **44.3%** (スカート15_0) | - | - | 19 | 0.94 | *0.76* (hip.R) | 85.6 | 69.2 |
| seiza | **2.13** (ひざ.L) | **0.11** (ひざ補助2.L) | **172** (ひざ補助.L) | *1.9* (スカート14_0) | **4.7%** (足首.L) | *0.6* (foot.L x thigh.L) | *3.4* (shin.L x thigh.L) | *52* (hair x skirt) | 0.95 | **0.64** (knee.L) | 156.4 | 65.0 |
| kneel_one | *1.92* (足.L) | *0.15* (ひざ補助.R) | *50* (ひざ補助.R) | **3.9** (スカート15_0) | **12.5%** (スカート15_0) | - | *4.7* (pelvis x thigh.R) | 11 | 0.94 | *0.70* (knee.R) | 83.9 | 35.4 |
| cross_legged | **2.75** (足.R) | **0.10** (足.R) | **144** (ひざ補助.L) | **3.6** (スカート2_0) | *1.6%* (スカート2_0) | - | *5.1* (pelvis x thigh.L) | 0 | *0.76* (hip.L) | **0.48** (hip.L) | 124.7 | 52.7 |
| deep_lunge | **2.03** (足.L) | *0.17* (ひざ補助.R) | 0 | **3.8** (スカート15_1) | **18.4%** (スカート15_1) | - | *4.5* (pelvis x thigh.R) | 0 | 0.94 | *0.79* (hip.L) | 55.8 | 52.7 |
| run_l | *1.92* (スカート2_2) | **0.10** (ひじ補助.L) | *46* (ひざ補助.L) | **3.0** (スカート15_2) | **3.5%** (スカート15_0) | - | *4.5* (pelvis x thigh.R) | **939** (hair x garment) | 0.95 | *0.70* (knee.L) | 16.4 | 95.3 |
| run_r | **2.09** (スカート13_2) | **0.10** (ひじ補助.R) | *46* (ひざ補助.R) | **2.7** (スカート0_2) | **4.9%** (スカート1_0) | - | *4.1* (pelvis x thigh.L) | **887** (hair x garment) | 0.95 | *0.70* (knee.R) | 16.4 | 95.3 |
| jump_tuck | **2.27** (スカート15_2) | *0.13* (ひざ補助2.L) | **134** (ひざ補助.L) | **3.1** (スカート15_2) | **5.6%** (スカート1_0) | - | *3.2* (shin.L x thigh.L) | **3784** (hair x skirt) | *0.78* (shoulder.L) | **0.64** (shoulder.R) | 136.0 | 45.1 |
| high_kick | **2.07** (足.L) | *0.26* (下半身) | 0 | **3.5** (下半身) | **15.6%** (横髪巻_1.R) | - | *4.7* (pelvis x thigh.R) | **3229** (hair x skirt) | 0.92 | *0.70* (hip.L) | 0.0 | 35.4 |
| arms_crossed | *1.77* (ひじ.L) | **0.11** (腕捩.R) | 6 | *1.1* (手捩.R) | *1.0%* (手捩.R) | **2.4** (forearm.L x forearm.R) | *4.0* (forearm.L x hand.R) | 0 | 0.95 | 0.92 | 0.0 | 109.2 |
| hands_behind_head | **2.12** (ひじ.R) | *0.12* (ひじ補助.L) | **114** (ひじ補助.L) | *1.1* (頭) | **5.0%** (頭) | *0.9* (hand.L x hand.R) | - | **4804** (hair x garment) | **0.61** (shoulder.R) | **0.47** (shoulder.L) | 0.0 | 136.5 |
| hands_behind_back | *1.71* (ひじ.R) | **0.09** (ひじ補助.L) | 0 | *1.4* (手捩.L) | *2.5%* (手捩.L) | *1.2* (forearm.L x forearm.R) | - | **1016** (hair x garment) | *0.70* (shoulder.L) | **0.58** (shoulder.L) | 0.0 | 99.7 |
| hand_to_shoulder | *1.74* (ひじ.L) | *0.18* (ひじ補助.L) | *34* (ひじ補助.L) | *1.9* (横髪長_2.L) | **4.2%** (横髪長_2.L) | - | - | *60* (hair x garment) | 0.95 | 0.93 | 0.0 | 32.9 |
| hands_on_hips | *1.64* (ひじ.R) | *0.19* (ひじ補助.R) | 0 | *1.6* (横髪巻_2.L) | **6.5%** (横髪巻_2.L) | - | - | 0 | 0.86 | *0.77* (shoulder.L) | 0.0 | 86.6 |
| reach_up_back | *1.85* (手捩.R) | 0.33 | *16* (腕D.L) | *1.7* (頭) | **11.5%** (頭) | 0.4 | - | **4082** (hair x garment) | *0.85* (shoulder.L) | *0.71* (shoulder.R) | -0.0 | 32.9 |
| hug_self | *1.67* (上半身2) | *0.17* (腕捩.L) | *11* (ひじ補助.L) | **2.5** (手捩.L) | **12.9%** (手捩.L) | **1.8** (hand.R x upperarm.L) | *4.4* (forearm.R x upperarm.L) | 39 | 0.94 | 0.95 | 0.0 | 110.9 |
| twist_bend | 1.32 | 0.52 | 0 | *1.5* (下半身) | *2.3%* (腕捩.L) | - | - | 0 | 0.98 | 0.91 | 23.5 | 29.7 |
| lie_back_elbows | **2.41** (首) | **0.10** (ひじ補助.R) | *12* (ひじ補助.L) | **3.7** (スカート1_0) | **13.5%** (スカート15_0) | - | - | **2482** (hair x skirt) | 0.93 | *0.74* (hip.R) | 8.0 | 99.7 |
| look_over_shoulder | **2.47** (首) | 0.50 | 0 | 0.6 | 0.3% | - | - | **1689** (hair x skirt) | 0.98 | 0.95 | 0.0 | 38.3 |
| curtsy | 1.55 | *0.27* (ひざ補助.L) | 0 | 0.2 | 0.0% | - | - | 40 | 0.96 | 0.84 | 56.6 | 39.6 |
| dance_sway | *1.85* (手捩.L) | *0.22* (ひじ補助.R) | 2 | *1.6* (横髪巻_1.L) | **12.8%** (横髪巻_2.R) | - | - | **1744** (hair x skirt) | *0.77* (shoulder.L) | **0.60** (shoulder.L) | 37.9 | 41.5 |
| dance_point | *1.84* (ひじ.L) | *0.14* (ひじ補助.L) | *31* (ひじ補助.L) | **2.3** (手捩.L) | **7.3%** (手捩.L) | - | - | **1727** (hair x skirt) | *0.80* (shoulder.R) | *0.69* (shoulder.R) | 38.4 | 32.9 |
| dance_heart | *1.79* (上半身2) | *0.22* (ひじ補助.R) | 0 | *1.9* (横髪巻_1.R) | **7.2%** (横髪巻_1.R) | **2.3** (hand.L x hand.R) | *4.3* (forearm.R x hand.L) | **2819** (hair x garment) | *0.79* (shoulder.L) | *0.65* (shoulder.R) | 32.6 | 108.3 |
| dance_clap | *1.71* (ひじ.R) | *0.14* (ひじ補助.L) | 0 | 0.7 | *0.6%* (手捩.R) | *0.9* (hand.L x hand.R) | *3.9* (forearm.L x hand.R) | *232* (hair x skirt) | 0.90 | 0.80 | 71.0 | 108.3 |

## motion

| name | stretch | compress | flip | pen cm | pen % | self cm | contact cm | cross | joint | vol | knee | elbow | pop mm | bone pop mm | jitter | speed m/s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| walk | *1.76* (スカート15_2) | 0.32 | 0 | *1.2* (下半身) | *1.6%* (腕捩.R) | - | - | **953** (hair x skirt, f15) | 0.96 | 0.86 | 26.1 | 37.1 | **45.4** (スカート13_2, f7) | **39.9** (スカート13_2, f7) | **0.24** (スカート15_2, f9) | 1.60 |
| run | **2.30** (スカート13_2, f8) | **0.10** (ひじ補助.R, f10) | *53* (ひざ補助.R) | **3.3** (スカート0_2, f10) | **3.3%** (スカート15_2, f0) | - | 2.6 | **1014** (hair x garment, f0) | 0.94 | *0.69* (knee.R) | 25.2 | 95.3 | **154.9** (スカート13_2, f35) | **135.0** (スカート13_2, f35) | **0.93** (スカート0_2, f35) | 4.48 |
| turn | *1.61* (スカート15_2) | *0.30* (ひざ補助.R) | 0 | **2.5** (足首.R, f39) | **28.4%** (足首.L, f36) | **4.9** (thigh.L x thigh.R, f38) | *5.4* (shin.L x thigh.R) | **2388** (hair x skirt, f23) | 0.96 | 0.85 | 22.1 | 45.1 | **34.3** (スカート1_2, f13) | **33.4** (スカート1_1, f13) | **0.36** (スカート15_2, f13) | 1.13 |
| sit_stand | **2.03** (スカート13_2, f25) | *0.15* (ひざ補助.L) | *21* (ひざ補助.L) | **3.9** (スカート0_1, f33) | **46.1%** (スカート0_0, f35) | - | - | *258* (hair x skirt) | 0.92 | *0.76* (hip.R) | 0.0 | 35.4 | **60.4** (スカート13_2, f79) | **55.7** (スカート13_2, f79) | **0.41** (スカート4_2, f75) | 2.30 |
| spin | **2.71** (スカート15_2, f21) | 0.49 | 0 | **2.5** (横髪巻_2.L, f44) | **18.7%** (横髪巻_1.R, f4) | **4.4** (thigh.L x thigh.R, f26) | *5.3* (shin.L x thigh.R) | **3084** (hair x skirt, f38) | 0.95 | 0.90 | 25.8 | 35.4 | **11.9** (スカート1_2, f21) | **11.9** (スカート1_2, f21) | *0.06* (スカート15_2) | 1.08 |
| idol_dance | **2.20** (スカート2_2, f74) | **0.07** (ひじ補助.L, f74) | *46* (ひざ補助.L) | **4.5** (手捩.L, f74) | **28.7%** (横髪巻_2.R, f14) | **4.5** (forearm.L x thigh.L, f74) | *4.9* (forearm.L x hand.R) | **4085** (hair x garment, f77) | **0.70** (shoulder.L, f80) | **0.53** (shoulder.L, f80) | 0.0 | 29.7 | **125.0** (スカート14_2, f66) | **256.9** (袖_1.L, f81) | **0.89** (ひじ.L, f80) | 7.25 |

## eyes (gaze at the limits x eye morphs)

| case | poke mm | where |
|---|---|---|
| gaze | 1.37 (minor) | head_eye_R gaze -10/+8 |
| gaze+まばたき | 0.00 (ok) | eyes  |
| gaze+まばたき=0.5 | 1.34 (minor) | head_eye_R gaze +10/+8 |
| gaze+ウィンク | 1.37 (minor) | head_eye_R gaze -10/+8 |
| gaze+ウィンク右 | 1.37 (minor) | head_eye_L gaze +10/+8 |
| gaze+笑い | 0.00 (ok) | eyes  |

## Top problems (grouped by metric, part and location)

| # | level | metric | part | location | worst | in |
|---|---|---|---|---|---|---|
| 1 | major | bone_pop | rig | 袖_1.L (bones) | 256.9 in idol_dance@81 | idol_dance@81 |
| 2 | major | pop | petticoat | スカート13_2 (petticoat_tier1) | 154.9 in run@35 | run@35, sit_stand@79, walk@7 |
| 3 | major | bone_pop | rig | スカート13_2 (bones) | 135.0 in run@35 | run@35, sit_stand@79, walk@7 |
| 4 | major | pop | petticoat | スカート14_2 (petticoat_tier0) | 125.0 in idol_dance@66 | idol_dance@66 |
| 5 | major | pen_frac | bodice | スカート0_0 (bodice_ribbon_tails) | 46.1% in sit_stand@35 | sit_stand@35 |
| 6 | major | jitter | petticoat | スカート0_2 (petticoat_tier0) | 0.93 in run@35 | run@35 |
| 7 | major | pen_frac | bodice | スカート15_0 (bodice_ribbon_tails) | 44.3% in sit_chair | sit_chair, lie_back_elbows, kneel_one |
| 8 | major | jitter | sleeves | ひじ.L (sleeve_balloon) | 0.89 in idol_dance@80 | idol_dance@80 |
| 9 | major | cross | hair/garment | hair x garment (hair x garment) | 4804 in hands_behind_head | hands_behind_head, idol_dance@77, reach_up_back, dance_heart, walk, hands_behind_back, run@0, run_l, dance_sway, run_r, arms_up, lie_back_elbows, head_left, ... |
| 10 | major | pen_frac | hair_front | 横髪巻_2.R (hair_curl_R) | 28.7% in idol_dance@14 | idol_dance@14, dance_sway, side_bend, hands_on_hips |
| 11 | major | pen_frac | shoes | 足首.L (shoes_leaves) | 28.4% in turn@36 | turn@36, spin@22, seiza, squat |
| 12 | major | cross | hair/skirt | hair x skirt (hair x skirt) | 3784 in jump_tuck | jump_tuck, high_kick, reach_up_back, hands_behind_head, spin@38, lie_back_elbows, turn@23, torso_left, head_left, torso_right, side_bend, idol_dance@15, head... |
| 13 | major | pop | skirt | スカート1_2 (skirt) | 34.3 in turn@13 | turn@13 |
| 14 | major | bone_pop | rig | スカート1_1 (bones) | 33.4 in turn@13 | turn@13 |
| 15 | major | pen_frac | hair_front | 頭 (hair_cheek_L) | 19.4% in idol_dance@81 | idol_dance@81, reach_up_back, hands_behind_head, idol_dance@50, dance_heart, idol_dance@80, idol_dance@48 |
| 16 | major | jitter | petticoat | スカート4_2 (petticoat_tier1) | 0.41 in sit_stand@75 | sit_stand@75 |
| 17 | major | pen_frac | hair_front | 横髪巻_1.R (hair_curl_R) | 18.7% in spin@4 | spin@4, high_kick, dance_heart, arms_up, jump_tuck |
| 18 | major | pen_frac | bodice | スカート15_1 (bodice_ribbon_tails) | 18.4% in deep_lunge | deep_lunge |
| 19 | major | pen_frac | sleeves | 手捩.L (sleeve_cuff) | 17.4% in idol_dance@74 | idol_dance@74, hug_self, dance_point, hands_behind_back, lie_back_elbows, hand_to_shoulder |
| 20 | major | jitter | petticoat | スカート15_2 (petticoat_tier1) | 0.36 in turn@13 | turn@13, walk@9, spin@21 |
| 21 | major | pen_frac | hair_front | 横髪巻_2.L (hair_curl_L) | 15.9% in spin@0 | spin@0, hands_on_hips, high_kick |
| 22 | major | pen_frac | hair_front | 横髪長_0.L (hair_lock_L) | 15.0% in idol_dance@81 | idol_dance@81, reach_up_back |
| 23 | major | pen_frac | hair_front | 横髪巻_0.L (hair_curl_L) | 12.8% in idol_dance@81 | idol_dance@81 |
| 24 | major | self | body | body:thigh.L x thigh.R (body:thigh.L x thigh.R) | 4.9 in turn@38 | turn@38, spin@26 |
| 25 | major | pen_frac | accessories | 頭 (acc_leaves_L) | 10.9% in reach_up_back | reach_up_back, idol_dance@81, dance_heart, idol_dance@48 |
| 26 | major | self | body | body:forearm.L x thigh.L (body:forearm.L x thigh.L) | 4.5 in idol_dance@74 | idol_dance@74 |
| 27 | major | pen_frac | accessories | 上半身2 (acc_halter) | 10.5% in reach_up_back | reach_up_back, idol_dance@51, arms_up, dance_heart, high_kick, spin@0, dance_sway, hands_behind_head |
| 28 | major | pen_frac | hair_front | 横髪奥_1.L (hair_curtain_L) | 9.9% in idol_dance@80 | idol_dance@80, reach_up_back, dance_point, spin@5 |
| 29 | major | self | body | body:hand.L x thigh.L (body:hand.L x thigh.L) | 4.2 in idol_dance@75 | idol_dance@75 |
| 30 | major | pen_frac | hair_front | 横髪長_2.L (hair_lock_L) | 9.8% in hug_self | hug_self, hand_to_shoulder |
| 31 | major | pen_frac | petticoat | スカート15_2 (petticoat_core) | 9.7% in sit_stand@27 | sit_stand@27, jump_tuck, run@0, run_l, idol_dance@72 |
| 32 | major | pen | sleeves | 手捩.L (sleeve_cuff) | 4.5 in idol_dance@74 | idol_dance@74, hug_self, dance_point, lie_back_elbows, hands_behind_back, hand_to_shoulder |
| 33 | major | pen_frac | hair_front | 横髪奥_1.R (hair_curtain_R) | 9.2% in dance_sway | dance_sway, idol_dance@11, reach_up_back, turn@6 |
| 34 | major | self | body | body:hand.L x pelvis (body:hand.L x pelvis) | 3.8 in idol_dance@75 | idol_dance@75 |
| 35 | major | self | body | body:shin.L x shin.R (body:shin.L x shin.R) | 3.6 in turn@34 | turn@34, spin@20 |
| 36 | major | self | body | body:hand.L x upperarm.R (body:hand.L x upperarm.R) | 3.5 in idol_dance@30 | idol_dance@30 |
| 37 | major | pen | skirt | スカート0_1 (skirt) | 3.9 in sit_stand@33 | sit_stand@33 |
| 38 | major | pen | skirt | スカート15_0 (skirt) | 3.9 in sit_chair | sit_chair, kneel_one, jump_tuck |
| 39 | major | stretch | body | 足.R (body) | 2.75 in cross_legged | cross_legged, run_r |
| 40 | major | pen | bodice | スカート15_0 (bodice_ribbon_tails) | 3.9 in kneel_one | kneel_one, sit_chair, sit_stand@58, lie_back_elbows |

## Issues by part (major / minor rows)

| part | major | minor |
|---|---|---|
| petticoat | 41 | 35 |
| body | 38 | 134 |
| hair_front | 35 | 43 |
| sleeves | 20 | 83 |
| hair/skirt | 20 | 6 |
| bodice | 14 | 3 |
| hair/garment | 12 | 12 |
| accessories | 11 | 15 |
| skirt | 10 | 15 |
| shoes | 6 | 10 |
| rig | 6 | 0 |
| hair_back | 0 | 11 |
| head | 0 | 4 |
