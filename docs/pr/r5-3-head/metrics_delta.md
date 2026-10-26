## Metrics vs baseline `out\review_base`

Per view and region, `new (delta)`; `*` = whole view (silhouette IoU, island total). iou/tol up is better; dE/dEi (interior colour error), islands and island_px down is better; shade is the render's shade share (compare with the sheet in shade_stats.txt).

| view | region | iou | tol | dE | dEi | shade | islands | island_px |
|---|---|---|---|---|---|---|---|---|
| front | * | 0.931 (+0.000) |  |  |  |  | 58 (-1) | 1490 (-4) |
| front | green | 0.397 (+0.001) | 0.807 (+0.001) | 17.2 (+0.0) | 16.1 (+0.0) | 0.320 (+0.000) | 14 (+0) | 282 (+0) |
| front | hair | 0.567 (+0.000) | 0.796 (+0.000) | 12.3 (+0.0) | 10.6 (+0.0) | 0.490 (+0.000) | 15 (+0) | 198 (+0) |
| front | skin | 0.770 (-0.000) | 0.950 (-0.000) | 6.2 (+0.0) | 3.1 (+0.0) | 0.210 (+0.000) | 11 (-1) | 445 (-4) |
| high | * |  |  |  |  |  | 40 (+3) | 1110 (+205) |
| high | green |  |  |  |  |  | 11 (+2) | 260 (+154) |
| high | skin |  |  |  |  |  | 9 (+1) | 324 (+51) |
| q34_front_left | * |  |  |  |  |  | 43 (+2) | 814 (+115) |
| q34_front_left | skin |  |  |  |  |  | 10 (+2) | 277 (+115) |
| side | * | 0.867 (-0.000) |  |  |  |  | 43 (+1) | 683 (+19) |
| side | green | 0.309 (+0.002) | 0.630 (+0.002) | 17.4 (+0.0) | 14.0 (+0.0) | 0.410 (+0.000) | 8 (+0) | 144 (-3) |
| side | skin | 0.619 (+0.001) | 0.833 (+0.002) | 5.9 (+0.0) | 3.1 (+0.1) | 0.300 (+0.000) | 4 (+1) | 113 (+22) |
