# Bend spans (limb diameters), body-only rig, every pose / clip worst frame

Columns: round 8's metric on the pre-#67 body (66be672, i.e. main without R8-5) and on main (bae3160); round 9's metric (`motion_check._span_profile`) on the same two, and on this PR. The motion clips of the pre-#67 tree are its own (R8-2 later smoothed the run clip), so its clip rows differ for that reason too.

| pose | joint | pre-#67, r8 metric | main, r8 metric | pre-#67, r9 metric | main, r9 metric | this PR, r9 metric |
|---|---|---|---|---|---|---|
| squat | knee.L | 0.962 | 0.966 | 0.981 | 0.991 | 0.946 |
| reach_forward | elbow.L | 0.531 | 0.862 | 1.302 | 1.310 | 1.310 |
| arms_forward | elbow.L | 1.692 | 1.695 | 1.314 | 1.287 | 1.287 |
| run_l | knee.L | 0.965 | 1.030 | 0.982 | 0.993 | 0.948 |
| run_l | elbow.L | 0.612 | 0.648 | 1.284 | 1.268 | 1.267 |
| run_l | elbow.R | 0.580 | 0.833 | 1.300 | 1.311 | 1.310 |
| kneel_one | knee.L | 0.937 | 0.948 | 0.976 | 0.988 | 0.943 |
| kneel_one | knee.R | 0.966 | 1.203 | 0.982 | 0.991 | 0.946 |
| kneel_one | elbow.L | 1.466 | 1.433 | 1.305 | 1.320 | 1.320 |
| seiza | knee.L | 0.970 | 0.981 | 0.985 | 0.995 | 0.950 |
| hands_behind_head | elbow.L | 1.695 | 1.696 | 1.160 | 1.167 | 1.168 |
| deep_lunge | knee.L | 0.862 | 0.878 | 0.969 | 0.981 | 0.937 |
| sit_chair | knee.L | 0.938 | 0.950 | 0.977 | 0.988 | 0.944 |
| hug_self | elbow.L | 0.974 | 1.014 | 1.273 | 1.256 | 1.256 |
| lie_back_elbows | elbow.L | 0.847 | 0.894 | 1.282 | 1.264 | 1.263 |
| clip:run | elbow.L | 0.630 | 1.872 | 1.301 | 1.312 | 1.312 |
| clip:run | knee.R | 0.967 | 1.036 | 0.982 | 0.994 | 0.949 |
| clip:run | knee.L | 0.967 | 1.036 | 0.982 | 0.994 | 0.949 |
| clip:walk | knee.R | 0.913 | 0.865 | 0.973 | 0.980 | 0.936 |
| clip:walk | knee.L | 0.913 | 0.866 | 0.973 | 0.980 | 0.936 |
