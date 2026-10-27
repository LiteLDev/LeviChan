| object | base major / minor | new major / minor |
|---|---|---|
| acc_halter | 0 / 0 | 0 / 1 |
| bodice_ribbon_tails | 0 / 5 | 0 / 6 |
| bodice_shell | 0 / 7 | 0 / 5 |
| body | 5 / 47 | 5 / 46 |
| hair x garment | 11 / 14 | 10 / 15 |
| hair_back_shell | 0 / 4 | 1 / 3 |
| hair_cap | 0 / 4 | 0 / 3 |
| hair_cheek_L | 0 / 5 | 1 / 4 |
| hair_cheek_R | 0 / 4 | 1 / 2 |
| hair_curtain_L | 2 / 5 | 3 / 4 |
| hair_curtain_R | 0 / 4 | 1 / 3 |
| joint:shoulder.L | 3 / 9 | 4 / 8 |
| petticoat_core | 3 / 21 | 4 / 20 |
| petticoat_tier0 | 0 / 21 | 0 / 19 |
| skirt | 8 / 22 | 8 / 23 |
| sleeve_balloon | 3 / 42 | 3 / 43 |
| sleeve_ribbon | 0 / 15 | 0 / 16 |
| **all** | 115 / 399 | 121 / 391 |

Issues on `body` (worst per pose / clip, metric):

| pose / clip | metric | base | new | |
|---|---|---|---|---|
| arms_forward | stretch | minor 1.69 | minor 1.69 | same level |
| arms_up | stretch | minor 1.71 | minor 1.78 | same level |
| cross_legged | compress | minor 0.153 | minor 0.165 | same level |
| cross_legged | flip | minor 53 | minor 52 | same level |
| cross_legged | stretch | major 2.39 | major 2.37 | same level |
| dance_clap | compress | minor 0.297 | ok | better |
| dance_heart | stretch | minor 1.66 | minor 1.68 | same level |
| dance_point | stretch | minor 1.6 | minor 1.62 | same level |
| dance_sway | stretch | minor 1.71 | minor 1.72 | same level |
| deep_lunge | compress | minor 0.278 | ok | better |
| deep_lunge | stretch | minor 1.64 | minor 1.64 | same level |
| fist | stretch | minor 1.82 | minor 1.86 | same level |
| hand_to_shoulder | stretch | minor 1.61 | minor 1.62 | same level |
| hands_behind_back | stretch | minor 1.66 | minor 1.66 | same level |
| hands_behind_head | stretch | minor 1.7 | minor 1.7 | same level |
| high_kick | compress | minor 0.272 | minor 0.272 | same level |
| high_kick | stretch | minor 1.76 | minor 1.76 | same level |
| hug_self | stretch | minor 1.76 | minor 1.76 | same level |
| idol_dance | compress | major 0.0917 | major 0.103 | same level |
| idol_dance | flip | minor 26 | minor 24 | same level |
| idol_dance | jitter | major 0.734 | major 0.698 | same level |
| idol_dance | pop | major 0.0366 | major 0.0365 | same level |
| idol_dance | stretch | minor 1.98 | minor 1.92 | same level |
| jump_tuck | compress | minor 0.164 | minor 0.18 | same level |
| jump_tuck | flip | minor 47 | minor 43 | same level |
| jump_tuck | stretch | minor 1.71 | minor 1.7 | same level |
| kneel_one | compress | minor 0.134 | minor 0.136 | same level |
| kneel_one | flip | minor 17 | minor 16 | same level |
| kneel_one | stretch | minor 1.9 | minor 1.9 | same level |
| lie_back_elbows | compress | minor 0.205 | minor 0.2 | same level |
| lie_back_elbows | stretch | minor 1.84 | minor 1.83 | same level |
| reach_up_back | stretch | minor 1.67 | minor 1.72 | same level |
| run | compress | minor 0.16 | minor 0.15 | same level |
| run | flip | minor 23 | minor 20 | same level |
| run | stretch | minor 1.71 | minor 1.71 | same level |
| run_l | compress | minor 0.171 | minor 0.168 | same level |
| run_l | flip | minor 16 | minor 16 | same level |
| run_r | compress | minor 0.171 | minor 0.168 | same level |
| run_r | flip | minor 16 | minor 16 | same level |
| seiza | compress | minor 0.15 | minor 0.152 | same level |
| seiza | flip | minor 52 | minor 40 | same level |
| seiza | stretch | minor 1.67 | minor 1.67 | same level |
| sit_chair | compress | minor 0.164 | minor 0.159 | same level |
| sit_chair | stretch | minor 1.74 | minor 1.72 | same level |
| sit_stand | compress | minor 0.163 | minor 0.154 | same level |
| sit_stand | stretch | minor 1.74 | minor 1.73 | same level |
| spin | stretch | ok | minor 1.64 | worse (腕捩.R) |
| squat | compress | minor 0.169 | minor 0.155 | same level |
| squat | flip | minor 24 | minor 22 | same level |
| squat | stretch | minor 1.66 | minor 1.67 | same level |
| test | compress | minor 0.163 | minor 0.15 | same level |
| turn | pop | minor 0.00571 | minor 0.00567 | same level |
| walk | pop | major 0.00785 | major 0.00791 | same level |
