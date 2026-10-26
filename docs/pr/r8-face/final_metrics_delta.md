## Metrics vs baseline `..\..\..\..\..\AppData\Local\Temp\claude\C--Users-futri-Desktop-LeviChan--claude-worktrees-levi-character-modeling-771bd2\adb9fe91-4f41-4ccb-9de8-2dd654b3b7a5\scratchpad\r8_face\review_base`

Per view and region, `new (delta)`; `*` = whole view (silhouette IoU, island total). iou/tol up is better; dE/dEi (interior colour error), islands and island_px down is better; shade is the render's shade share (compare with the sheet in shade_stats.txt).

| view | region | iou | tol | dE | dEi | shade | islands | island_px |
|---|---|---|---|---|---|---|---|---|
| front | * | 0.915 (+0.000) |  |  |  |  | 45 (+1) | 935 (+15) |
| front | green | 0.393 (-0.000) | 0.803 (-0.000) | 17.3 (+0.0) | 15.7 (+0.0) | 0.330 (+0.000) | 17 (+0) | 390 (+0) |
| front | skin | 0.780 (-0.000) | 0.956 (-0.000) | 6.4 (-0.1) | 3.3 (+0.0) | 0.150 (+0.000) | 11 (+1) | 343 (+15) |
| high | * |  |  |  |  |  | 47 (+0) | 1007 (+2) |
| high | green |  |  |  |  |  | 18 (+0) | 483 (+2) |
| q34_front_left | * |  |  |  |  |  | 40 (+1) | 691 (+10) |
| q34_front_left | skin |  |  |  |  |  | 8 (+1) | 158 (+10) |
| side | green | 0.312 (-0.000) | 0.639 (+0.000) | 18.0 (+0.1) | 14.9 (+0.0) | 0.440 (+0.000) | 9 (+0) | 213 (+0) |
| side | skin | 0.635 (+0.000) | 0.846 (-0.000) | 6.0 (+0.0) | 3.1 (+0.0) | 0.220 (+0.000) | 4 (+0) | 121 (+0) |
