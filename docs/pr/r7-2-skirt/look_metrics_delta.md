## Metrics vs baseline `out\base\review`

Per view and region, `new (delta)`; `*` = whole view (silhouette IoU, island total). iou/tol up is better; dE/dEi (interior colour error), islands and island_px down is better; shade is the render's shade share (compare with the sheet in shade_stats.txt).

| view | region | iou | tol | dE | dEi | shade | islands | island_px |
|---|---|---|---|---|---|---|---|---|
| front | * | 0.915 (+0.000) |  |  |  |  | 44 (-1) | 920 (-59) |
| front | dress | 0.786 (-0.000) | 0.931 (+0.000) | 6.1 (+0.0) | 5.1 (+0.0) | 0.200 (+0.000) | 8 (+0) | 108 (+0) |
| front | green | 0.393 (-0.000) | 0.803 (-0.000) | 17.3 (+0.1) | 15.7 (+0.0) | 0.330 (+0.010) | 17 (-1) | 390 (-59) |
| side | * | 0.862 (-0.000) |  |  |  |  | 31 (+0) | 529 (+4) |
| side | dress | 0.747 (+0.000) | 0.907 (-0.000) | 7.5 (+0.0) | 6.6 (+0.0) | 0.260 (+0.000) | 6 (+0) | 68 (+0) |
| side | green | 0.312 (-0.000) | 0.639 (-0.000) | 17.9 (+0.0) | 14.9 (+0.0) | 0.440 (+0.000) | 9 (+0) | 213 (+4) |
