## Metrics vs baseline `out\review_base`

Per view and region, `new (delta)`; `*` = whole view (silhouette IoU, island total). iou/tol up is better; dE/dEi (interior colour error), islands and island_px down is better; shade is the render's shade share (compare with the sheet in shade_stats.txt).

| view | region | iou | tol | dE | dEi | shade | islands | island_px |
|---|---|---|---|---|---|---|---|---|
| back | * | 0.919 (+0.000) |  |  |  |  | 32 (+4) | 894 (+76) |
| back | dress | 0.629 (-0.001) | 0.826 (-0.001) | 6.4 (+0.0) | 5.5 (+0.0) | 0.180 (+0.000) | 4 (+0) | 91 (+0) |
| back | green | 0.261 (-0.004) | 0.569 (-0.008) | 15.6 (+0.1) | 10.0 (-0.1) | 0.490 (+0.010) | 1 (+0) | 79 (+0) |
| back | hair | 0.696 (-0.001) | 0.869 (-0.001) | 9.3 (+0.0) | 8.0 (+0.1) | 0.270 (+0.000) | 20 (+4) | 427 (+76) |
| q34_back_right | * |  |  |  |  |  | 22 (-6) | 570 (-95) |
| q34_back_right | hair |  |  |  |  |  | 12 (-6) | 278 (-95) |
| side | * | 0.860 (-0.001) |  |  |  |  | 33 (+0) | 573 (-14) |
| side | dress | 0.750 (+0.001) | 0.908 (+0.000) | 7.6 (+0.1) | 6.7 (+0.1) | 0.260 (+0.000) | 6 (+0) | 68 (+0) |
| side | hair | 0.668 (-0.002) | 0.850 (-0.002) | 11.0 (+0.0) | 9.9 (+0.0) | 0.520 (+0.000) | 13 (+0) | 150 (-14) |
