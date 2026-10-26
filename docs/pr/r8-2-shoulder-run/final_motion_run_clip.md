# Motion test report

Model: 49 meshes, 100430 vertices, 99010 faces (without outlines). Run time 95 s. Not gated: the exit code of rig_check covers the core poses only. No cloth or hair physics: chains move only as keyed or driven (MMD simulates them).

Thresholds (minor / major): stretch 1.60/2.00, compress 0.30/0.12, flip 10/100, pen 1.0/2.0, pen_frac 0.5%/3.0%, self 0.5/1.5, contact 3.0/6.0, cross 40/400, joint 0.85/0.70, vol 0.80/0.65, knee -0.5/-5.0, elbow -5.0/-15.0, pop 2.0/6.0, bone_pop 2.0/6.0, jitter 0.03/0.08, speed 12.00/20.00, eye 0.8/1.5, span 0.70/1.00.
Cells: plain = ok, *italic* = minor, **bold** = major (location, frame for clips). pen/self/contact in cm, pop in mm; joint = median skin radius ratio at the worst joint band, vol = its mean squared radius ratio; knee/elbow = least signed bend (negative = hyperextended).

## motion

| name | stretch | compress | flip | pen cm | pen % | contact cm | cross | joint | vol | knee | elbow | span | pop mm | bone pop mm | jitter | speed m/s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| run | **2.15** (スカート15_2, f6) | *0.13* (ひざ補助2.L) | *26* (ひざ補助.R) | *1.6* (後髪束5_2) | **3.1%** (足首.R, f3) | *5.9* (pelvis x thigh.L) | **1137** (hair x garment, f18) | 0.95 | **0.65** (knee.R, f4) | 32.4 | 86.6 | **1.87** (elbow.L, f18) | **56.5** (スカート14_2, f7) | **51.7** (スカート14_2, f7) | **0.37** (後髪束17_3, f10) | 4.88 |

## Top problems (grouped by metric, part and location)

| # | level | metric | part | location | worst | in |
|---|---|---|---|---|---|---|
| 1 | major | pop | petticoat | スカート14_2 (petticoat_tier0) | 56.5 in run@7 | run@7 |
| 2 | major | bone_pop | rig | スカート14_2 (bones) | 51.7 in run@7 | run@7 |
| 3 | major | jitter | hair_back | 後髪束17_3 (hair_back_side) | 0.37 in run@10 | run@10 |
| 4 | major | span | body | elbow.L (span:elbow.L) | 1.87 in run@18 | run@18 |
| 5 | major | span | body | elbow.R (span:elbow.R) | 1.87 in run@8 | run@8 |
| 6 | major | cross | hair/garment | hair x garment (hair x garment) | 1137 in run@18 | run@18 |
| 7 | major | stretch | petticoat | スカート15_2 (petticoat_tier1) | 2.15 in run@6 | run@6 |
| 8 | major | pen_frac | shoes | 足首.R (shoes_ribbons) | 3.1% in run@3 | run@3 |
| 9 | major | vol | body | joint:knee.L (joint:knee.L) | 0.65 in run@14 | run@14 |
| 10 | major | vol | body | joint:knee.R (joint:knee.R) | 0.65 in run@4 | run@4 |
| 11 | minor | contact | body | body:pelvis x thigh.L (body:pelvis x thigh.L) | 5.9 in run@16 | run@16 |
| 12 | minor | compress | body | ひざ補助2.L (body) | 0.13 in run@14 | run@14 |
| 13 | minor | span | body | knee.R (span:knee.R) | 0.97 in run@4 | run@4 |
| 14 | minor | span | body | knee.L (span:knee.L) | 0.97 in run@14 | run@14 |
| 15 | minor | contact | body | body:pelvis x thigh.R (body:pelvis x thigh.R) | 5.2 in run@6 | run@6 |
| 16 | minor | pen | hair_back | 後髪束5_2 (hair_back) | 1.6 in run@8 | run@8 |
| 17 | minor | stretch | skirt | スカート0_2 (skirt) | 1.77 in run@18 | run@18 |
| 18 | minor | stretch | petticoat | スカート0_1 (petticoat_core) | 1.74 in run@16 | run@16 |
| 19 | minor | stretch | petticoat | スカート0_2 (petticoat_tier0) | 1.73 in run@6 | run@6 |
| 20 | minor | compress | sleeves | ひじ補助.R (sleeve_balloon) | 0.24 in run@7 | run@7 |
| 21 | minor | stretch | shoes | ひざ.L (shoes_leaves) | 1.72 in run@13 | run@13 |
| 22 | minor | pen | shoes | 足首.R (shoes_ribbons) | 1.3 in run@3 | run@3 |
| 23 | minor | pen_frac | sleeves | 腕捩.R (sleeve_ruffle) | 1.2% in run@3 | run@3 |
| 24 | minor | flip | body | ひざ補助.R (body) | 26 in run@4 | run@4 |
| 25 | minor | pen | skirt | スカート3_0 (skirt) | 1.1 in run@8 | run@8 |
| 26 | minor | stretch | sleeves | 袖胴.L (sleeve_balloon) | 1.63 in run@4 | run@4 |

## Issues by part (major / minor rows)

| part | major | minor |
|---|---|---|
| body | 4 | 6 |
| petticoat | 2 | 2 |
| shoes | 1 | 2 |
| hair_back | 1 | 1 |
| rig | 1 | 0 |
| hair/garment | 1 | 0 |
| sleeves | 0 | 3 |
| skirt | 0 | 2 |
