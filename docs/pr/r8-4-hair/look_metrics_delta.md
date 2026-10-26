## Metrics vs baseline `out\review_main`

Per view and region, `new (delta)`; `*` = whole view (silhouette IoU, island total). iou/tol up is better; dE/dEi (interior colour error), islands and island_px down is better; shade is the render's shade share (compare with the sheet in shade_stats.txt).

| view | region | iou | tol | dE | dEi | shade | islands | island_px |
|---|---|---|---|---|---|---|---|---|
| side | shoe | 0.671 (+0.000) | 0.934 (+0.000) | 10.3 (+0.0) | 5.5 (+0.0) | 0.220 (+0.000) | 0 (+0) | 0 (+0) |
| side | skin | 0.635 (+0.000) | 0.847 (+0.000) | 6.0 (+0.0) | 3.1 (+0.0) | 0.220 (+0.000) | 4 (+0) | 121 (+0) |
