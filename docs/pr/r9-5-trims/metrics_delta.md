## Metrics vs baseline `main` (bae3160)

Per view and region, `new (delta)`; `*` = whole view (silhouette IoU, island total). iou/tol up is better; dE/dEi (interior colour error), islands and island_px down is better; shade is the render's shade share (compare with the sheet in shade_stats.txt).

| view | region | iou | tol | dE | dEi | shade | islands | island_px |
|---|---|---|---|---|---|---|---|---|
| front | * | 0.916 (+0.000) |  |  |  |  | 43 (+0) | 841 (-5) |
| front | green | 0.393 (+0.000) | 0.803 (+0.000) | 17.3 (+0.0) | 15.6 (-0.1) | 0.330 (+0.000) | 16 (+0) | 390 (-4) |
| front | skin | 0.784 (+0.000) | 0.959 (+0.000) | 6.6 (+0.0) | 3.4 (+0.0) | 0.150 (+0.000) | 9 (+0) | 221 (-1) |
| high | * |  |  |  |  |  | 39 (+0) | 812 (+1) |
| high | dress |  |  |  |  |  | 4 (+0) | 82 (+1) |
| q34_front_left | * |  |  |  |  |  | 43 (+0) | 858 (+11) |
| q34_front_left | green |  |  |  |  |  | 13 (+0) | 141 (+10) |
| q34_front_left | skin |  |  |  |  |  | 10 (+0) | 307 (+1) |
| side | * | 0.861 (-0.000) |  |  |  |  | 33 (+0) | 604 (+17) |
| side | dress | 0.749 (+0.000) | 0.908 (-0.000) | 7.5 (+0.0) | 6.6 (+0.0) | 0.260 (+0.000) | 6 (+0) | 68 (+0) |
| side | green | 0.312 (-0.001) | 0.638 (-0.001) | 18.1 (+0.1) | 15.1 (+0.2) | 0.440 (+0.000) | 9 (+0) | 230 (+17) |
