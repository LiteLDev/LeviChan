## Metrics vs baseline `out\review_base`

Per view and region, `new (delta)`; `*` = whole view (silhouette IoU, island total). iou/tol up is better; dE/dEi (interior colour error), islands and island_px down is better; shade is the render's shade share (compare with the sheet in shade_stats.txt).

| view | region | iou | tol | dE | dEi | shade | islands | island_px |
|---|---|---|---|---|---|---|---|---|
| back | * | 0.931 (-0.002) |  |  |  |  | 61 (+1) | 872 (+13) |
| back | dress | 0.666 (+0.003) | 0.851 (+0.002) | 6.2 (+0.0) | 5.5 (+0.0) | 0.200 (+0.000) | 1 (+0) | 13 (+0) |
| back | petticoat | 0.641 (-0.008) | 0.865 (-0.002) | 9.9 (+0.4) | 8.9 (+0.3) | 0.430 (-0.170) | 1 (+1) | 13 (+13) |
| back | skin | 0.681 (-0.001) | 0.866 (-0.001) | 5.5 (+0.1) | 3.0 (+0.1) | 0.250 (-0.030) | 2 (+0) | 147 (+0) |
| front | * | 0.929 (-0.002) |  |  |  |  | 56 (-3) | 1311 (-183) |
| front | petticoat | 0.589 (-0.007) | 0.819 (-0.002) | 9.0 (+0.1) | 8.0 (+0.1) | 0.320 (-0.060) | 0 (-3) | 0 (-183) |
| front | skin | 0.769 (-0.002) | 0.949 (-0.001) | 6.4 (+0.2) | 3.2 (+0.1) | 0.170 (-0.040) | 12 (+0) | 449 (+0) |
| q34_back_right | * |  |  |  |  |  | 54 (-1) | 962 (-21) |
| q34_back_right | petticoat |  |  |  |  |  | 1 (-1) | 51 (-21) |
| q34_front_left | * |  |  |  |  |  | 42 (+1) | 706 (+7) |
| q34_front_left | petticoat |  |  |  |  |  | 3 (+1) | 20 (+7) |
| side | * | 0.872 (+0.005) |  |  |  |  | 41 (-1) | 650 (-14) |
| side | dress | 0.678 (-0.001) | 0.859 (-0.001) | 7.2 (+0.0) | 6.2 (+0.0) | 0.280 (+0.000) | 7 (+0) | 70 (+0) |
| side | petticoat | 0.480 (+0.015) | 0.722 (+0.013) | 9.2 (+0.3) | 8.1 (+0.2) | 0.470 (-0.130) | 0 (-1) | 0 (-14) |
| side | skin | 0.625 (+0.007) | 0.837 (+0.005) | 6.0 (+0.1) | 3.2 (+0.2) | 0.230 (-0.070) | 3 (+0) | 91 (+0) |
