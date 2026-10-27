## Metrics vs baseline `out\review_main`

Per view and region, `new (delta)`; `*` = whole view (silhouette IoU, island total). iou/tol up is better; dE/dEi (interior colour error), islands and island_px down is better; shade is the render's shade share (compare with the sheet in shade_stats.txt).

| view | region | iou | tol | dE | dEi | shade | islands | island_px |
|---|---|---|---|---|---|---|---|---|
| back | * | 0.918 (-0.001) |  |  |  |  | 33 (+0) | 860 (+11) |
| back | green | 0.263 (+0.000) | 0.569 (+0.001) | 15.5 (+0.0) | 10.1 (+0.1) | 0.480 (+0.000) | 1 (+0) | 4 (+0) |
| back | hair | 0.693 (-0.001) | 0.867 (-0.000) | 9.4 (+0.0) | 7.9 (+0.0) | 0.270 (+0.000) | 22 (+0) | 425 (+11) |
| front | * | 0.916 (-0.000) |  |  |  |  | 41 (+2) | 765 (-89) |
| front | green | 0.394 (-0.000) | 0.804 (-0.000) | 17.3 (+0.0) | 15.6 (+0.0) | 0.320 (+0.000) | 16 (+0) | 394 (+0) |
| front | hair | 0.554 (-0.002) | 0.785 (-0.001) | 12.9 (+0.0) | 11.5 (+0.1) | 0.580 (+0.010) | 8 (+2) | 80 (-85) |
| front | skin | 0.784 (+0.000) | 0.959 (+0.000) | 6.4 (+0.0) | 3.4 (+0.0) | 0.150 (+0.000) | 9 (+0) | 214 (-4) |
| high | * |  |  |  |  |  | 44 (+6) | 897 (+60) |
| high | hair |  |  |  |  |  | 19 (+6) | 236 (+60) |
| q34_front_left | * |  |  |  |  |  | 45 (+3) | 942 (+99) |
| q34_front_left | hair |  |  |  |  |  | 15 (+3) | 251 (+97) |
| q34_front_left | skin |  |  |  |  |  | 12 (+0) | 344 (+2) |
| side | * | 0.858 (-0.003) |  |  |  |  | 38 (+4) | 792 (+33) |
| side | hair | 0.665 (-0.007) | 0.850 (-0.004) | 11.3 (+0.2) | 10.1 (+0.1) | 0.520 (+0.000) | 19 (+4) | 233 (+33) |
| side | skin | 0.652 (+0.000) | 0.854 (+0.000) | 6.1 (+0.0) | 3.2 (+0.0) | 0.220 (+0.000) | 4 (+0) | 135 (+0) |

## Shape-master fit vs baseline

target->ours distance (mm, down is better) and covered share (up is better), from tools/shape_fit.py: `new (delta)`.

| part | p50 mm | p90 mm | covered |
|---|---|---|---|
| body | 8.6 (+0.0) | 24.2 (+0.0) | 0.312 (+0.000) |
| head | 6.2 (+0.0) | 19.8 (+0.0) | 0.426 (+0.000) |
| hair_front | 3.6 (-0.9) | 12.2 (-2.7) | 0.603 (+0.068) |
| hair_back | 25.4 (+0.0) | 77.3 (+0.0) | 0.170 (+0.000) |
| accessories | 4.7 (+0.0) | 11.6 (+0.0) | 0.522 (+0.000) |
| bodice | 9.1 (+0.0) | 25.9 (+0.0) | 0.264 (+0.000) |
| skirt | 14.6 (+0.0) | 48.3 (+0.0) | 0.204 (+0.000) |
| petticoat | 13.7 (+0.0) | 34.5 (+0.0) | 0.190 (+0.000) |
| sleeves | 11.7 (+0.0) | 27.4 (+0.0) | 0.240 (+0.000) |
| shoes | 7.4 (+0.0) | 18.7 (+0.0) | 0.347 (+0.000) |
