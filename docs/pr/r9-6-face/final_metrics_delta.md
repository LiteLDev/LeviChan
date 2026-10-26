## Metrics vs baseline `out\review_base`

Per view and region, `new (delta)`; `*` = whole view (silhouette IoU, island total). iou/tol up is better; dE/dEi (interior colour error), islands and island_px down is better; shade is the render's shade share (compare with the sheet in shade_stats.txt).

| view | region | iou | tol | dE | dEi | shade | islands | island_px |
|---|---|---|---|---|---|---|---|---|
| front | * | 0.916 (+0.000) |  |  |  |  | 43 (+0) | 838 (-8) |
| front | green | 0.393 (-0.000) | 0.803 (-0.000) | 17.3 (+0.0) | 15.7 (+0.0) | 0.330 (+0.000) | 16 (+0) | 394 (+0) |
| front | skin | 0.784 (+0.000) | 0.959 (+0.000) | 6.6 (+0.0) | 3.4 (+0.0) | 0.150 (+0.000) | 9 (+0) | 214 (-8) |
| q34_front_left | * |  |  |  |  |  | 43 (+0) | 843 (-4) |
| q34_front_left | skin |  |  |  |  |  | 10 (+0) | 302 (-4) |
| side | * | 0.861 (+0.000) |  |  |  |  | 33 (+0) | 591 (+4) |
| side | green | 0.313 (-0.000) | 0.639 (+0.000) | 18.0 (+0.0) | 14.9 (+0.0) | 0.440 (+0.000) | 9 (+0) | 213 (+0) |
| side | skin | 0.641 (+0.000) | 0.850 (-0.000) | 6.2 (+0.0) | 3.2 (+0.0) | 0.220 (+0.000) | 5 (+0) | 146 (+4) |
