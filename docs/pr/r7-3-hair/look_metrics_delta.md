## Metrics vs baseline `..\..\..\..\..\AppData\Local\Temp\claude\C--Users-futri-Desktop-LeviChan--claude-worktrees-levi-character-modeling-771bd2\adb9fe91-4f41-4ccb-9de8-2dd654b3b7a5\scratchpad\main_copy\out\review_main`

Per view and region, `new (delta)`; `*` = whole view (silhouette IoU, island total). iou/tol up is better; dE/dEi (interior colour error), islands and island_px down is better; shade is the render's shade share (compare with the sheet in shade_stats.txt).

| view | region | iou | tol | dE | dEi | shade | islands | island_px |
|---|---|---|---|---|---|---|---|---|
| back | * | 0.917 (+0.000) |  |  |  |  | 27 (+3) | 822 (+11) |
| back | dress | 0.630 (-0.002) | 0.827 (-0.001) | 6.4 (+0.0) | 5.5 (+0.0) | 0.180 (+0.000) | 4 (+0) | 91 (+0) |
| back | hair | 0.697 (-0.000) | 0.870 (+0.002) | 9.3 (+0.1) | 7.9 (+0.0) | 0.270 (+0.000) | 16 (+3) | 351 (+11) |
| q34_back_right | * |  |  |  |  |  | 28 (+2) | 676 (-8) |
| q34_back_right | dress |  |  |  |  |  | 1 (-1) | 41 (-76) |
| q34_back_right | hair |  |  |  |  |  | 18 (+3) | 373 (+68) |
| side | * | 0.859 (-0.003) |  |  |  |  | 32 (+1) | 562 (+37) |
| side | dress | 0.750 (+0.003) | 0.909 (+0.002) | 7.5 (+0.0) | 6.6 (+0.0) | 0.260 (+0.000) | 6 (+0) | 68 (+0) |
| side | hair | 0.670 (-0.004) | 0.853 (-0.004) | 11.0 (+0.0) | 9.9 (+0.1) | 0.520 (+0.010) | 13 (+1) | 164 (+37) |
