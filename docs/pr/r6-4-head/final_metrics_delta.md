## Metrics vs baseline `out\review_base`

Per view and region, `new (delta)`; `*` = whole view (silhouette IoU, island total). iou/tol up is better; dE/dEi (interior colour error), islands and island_px down is better; shade is the render's shade share (compare with the sheet in shade_stats.txt).

| view | region | iou | tol | dE | dEi | shade | islands | island_px |
|---|---|---|---|---|---|---|---|---|
| front | * | 0.925 (+0.000) |  |  |  |  | 45 (-1) | 1062 (-73) |
| front | green | 0.390 (-0.000) | 0.798 (-0.000) | 17.3 (+0.0) | 15.7 (+0.0) | 0.330 (+0.000) | 17 (+0) | 390 (+0) |
| front | hair | 0.555 (-0.000) | 0.786 (+0.000) | 12.8 (+0.0) | 11.4 (+0.0) | 0.570 (+0.000) | 8 (+0) | 79 (+0) |
| front | skin | 0.768 (-0.000) | 0.949 (-0.000) | 6.4 (+0.1) | 3.3 (+0.1) | 0.180 (+0.000) | 10 (-1) | 328 (-73) |
| high | * |  |  |  |  |  | 51 (-1) | 1110 (-48) |
| high | skin |  |  |  |  |  | 10 (-1) | 273 (-48) |
| q34_front_left | * |  |  |  |  |  | 40 (-1) | 592 (-34) |
| q34_front_left | hair |  |  |  |  |  | 13 (-1) | 163 (-34) |
| side | * | 0.864 (+0.000) |  |  |  |  | 34 (+0) | 598 (+14) |
| side | green | 0.309 (+0.000) | 0.632 (+0.000) | 17.8 (+0.0) | 14.9 (+0.0) | 0.430 (+0.000) | 8 (+0) | 182 (+0) |
| side | skin | 0.629 (+0.000) | 0.842 (+0.000) | 5.8 (+0.0) | 2.9 (+0.0) | 0.260 (+0.000) | 4 (+0) | 121 (+14) |
