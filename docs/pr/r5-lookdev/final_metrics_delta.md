## Metrics vs baseline `out\review_base`

Per view and region, `new (delta)`; `*` = whole view (silhouette IoU, island total). iou/tol up is better; dE/dEi (interior colour error), islands and island_px down is better; shade is the render's shade share (compare with the sheet in shade_stats.txt).

| view | region | iou | tol | dE | dEi | shade | islands | island_px |
|---|---|---|---|---|---|---|---|---|
| back | * | 0.933 (+0.000) |  |  |  |  | 59 (-1) | 845 (-14) |
| back | dress | 0.664 (+0.000) | 0.849 (+0.000) | 6.2 (+0.0) | 5.4 (-0.1) | 0.170 (-0.030) | 0 (-1) | 0 (-13) |
| back | hair | 0.700 (+0.000) | 0.870 (+0.000) | 9.4 (+0.0) | 7.9 (+0.0) | 0.190 (+0.000) | 55 (+0) | 657 (-1) |
| back | petticoat | 0.649 (+0.000) | 0.866 (+0.000) | 9.3 (-0.2) | 8.4 (-0.2) | 0.570 (-0.030) | 0 (+0) | 0 (+0) |
| back | skin | 0.682 (+0.000) | 0.867 (+0.000) | 5.6 (+0.2) | 3.2 (+0.3) | 0.210 (-0.070) | 2 (+0) | 147 (+0) |
| front | * | 0.931 (+0.000) |  |  |  |  | 58 (-1) | 1423 (-71) |
| front | petticoat | 0.596 (+0.000) | 0.820 (+0.000) | 8.8 (-0.1) | 7.8 (-0.1) | 0.230 (-0.150) | 2 (-1) | 112 (-71) |
| front | skin | 0.771 (+0.000) | 0.950 (+0.000) | 6.4 (+0.2) | 3.3 (+0.2) | 0.180 (-0.030) | 12 (+0) | 449 (+0) |
| q34_back_right | * |  |  |  |  |  | 54 (-1) | 888 (-95) |
| q34_back_right | dress |  |  |  |  |  | 3 (-1) | 25 (-45) |
| q34_back_right | hair |  |  |  |  |  | 41 (+0) | 538 (-50) |
| q34_front_left | * |  |  |  |  |  | 42 (+1) | 699 (+0) |
| q34_front_left | dress |  |  |  |  |  | 4 (+0) | 138 (-5) |
| q34_front_left | petticoat |  |  |  |  |  | 3 (+1) | 18 (+5) |
| side | dress | 0.679 (+0.000) | 0.860 (+0.000) | 7.2 (+0.0) | 6.2 (+0.0) | 0.250 (-0.030) | 7 (+0) | 70 (+0) |
| side | petticoat | 0.465 (+0.000) | 0.709 (+0.000) | 9.0 (+0.1) | 7.9 (+0.0) | 0.490 (-0.110) | 1 (+0) | 14 (+0) |
| side | skin | 0.618 (+0.000) | 0.832 (+0.000) | 5.9 (+0.0) | 3.1 (+0.1) | 0.270 (-0.030) | 3 (+0) | 91 (+0) |
