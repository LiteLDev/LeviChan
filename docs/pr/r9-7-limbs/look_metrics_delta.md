## Metrics vs baseline `main (bae3160) review`

Per view and region, `new (delta)`; `*` = whole view (silhouette IoU, island total). iou/tol up is better; dE/dEi (interior colour error), islands and island_px down is better; shade is the render's shade share (compare with the sheet in shade_stats.txt).

| view | region | iou | tol | dE | dEi | shade | islands | island_px |
|---|---|---|---|---|---|---|---|---|
| back | skin | 0.665 (+0.001) | 0.856 (+0.001) | 6.0 (+0.1) | 3.3 (+0.0) | 0.180 (-0.010) | 3 (+0) | 110 (+0) |
| front | * | 0.916 (-0.000) |  |  |  |  | 43 (+0) | 846 (+0) |
| front | skin | 0.784 (+0.000) | 0.959 (+0.000) | 6.4 (-0.2) | 3.4 (+0.0) | 0.150 (+0.000) | 9 (+0) | 222 (+0) |
