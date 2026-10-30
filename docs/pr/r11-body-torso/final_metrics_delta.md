## Metrics vs baseline `../../../../../work/body-torso/review_base`

Per view and region, `new (delta)`; `*` = whole view (silhouette IoU, island total). iou/tol up is better; dE/dEi (interior colour error), islands and island_px down is better; shade is the render's shade share (compare with the sheet in shade_stats.txt).

| view | region | iou | tol | dE | dEi | shade | islands | island_px |
|---|---|---|---|---|---|---|---|---|
| front | * | 0.909 (+0.000) |  |  |  |  | 45 (+0) | 1092 (-2) |
| front | green | 0.392 (+0.001) | 0.797 (-0.004) | 17.2 (+0.0) | 15.6 (+0.0) | 0.320 (+0.000) | 16 (+0) | 365 (+0) |
| front | skin | 0.744 (+0.000) | 0.942 (+0.000) | 6.6 (+0.0) | 3.3 (+0.0) | 0.170 (+0.000) | 9 (+0) | 305 (-2) |
| high | * |  |  |  |  |  | 46 (+0) | 1068 (-1) |
| high | skin |  |  |  |  |  | 4 (+0) | 162 (-1) |
| q34_front_left | * |  |  |  |  |  | 48 (-1) | 1068 (-11) |
| q34_front_left | skin |  |  |  |  |  | 10 (-1) | 331 (-11) |
| side | * | 0.833 (+0.000) |  |  |  |  | 35 (+0) | 865 (+0) |
| side | green | 0.307 (+0.000) | 0.623 (-0.002) | 17.9 (+0.0) | 15.0 (+0.0) | 0.450 (+0.000) | 8 (+0) | 264 (+0) |
| side | skin | 0.611 (-0.001) | 0.835 (-0.001) | 6.6 (+0.0) | 3.3 (+0.0) | 0.220 (+0.000) | 6 (+0) | 158 (+0) |

## Shape-master fit vs baseline

target->ours distance (mm, down is better) and covered share (up is better), from tools/shape_fit.py: `new (delta)`.

| part | p50 mm | p90 mm | covered |
|---|---|---|---|
| body | 6.9 (+0.0) | 23.6 (+0.0) | 0.404 (+0.002) |
| head | 5.8 (+0.0) | 19.9 (+0.0) | 0.446 (+0.000) |
| hair_front | 4.5 (+0.0) | 14.9 (+0.0) | 0.535 (+0.000) |
| hair_back | 24.6 (+0.0) | 73.4 (+0.0) | 0.173 (+0.000) |
| accessories | 4.1 (-0.4) | 10.8 (-0.3) | 0.578 (+0.032) |
| bodice | 9.2 (+0.0) | 21.2 (+0.0) | 0.259 (+0.000) |
| skirt | 13.7 (+0.0) | 37.1 (+0.0) | 0.260 (+0.000) |
| petticoat | 14.0 (+0.0) | 34.2 (+0.0) | 0.192 (+0.000) |
| sleeves | 9.5 (+0.0) | 24.2 (+0.0) | 0.309 (+0.000) |
| shoes | 7.4 (+0.0) | 18.7 (+0.0) | 0.347 (+0.000) |
