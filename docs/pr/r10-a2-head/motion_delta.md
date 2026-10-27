# Motion report vs main (`rig_check.py -- --quick --no-core --extended --report-core --motion`)

## Issues by part (major / minor rows)
This table is identical to main for every part: head has 0 major and 13 minor in both.

| part | main | this PR |
|---|---|---|
| head | 0 / 13 | 0 / 13 |
| all other parts | | unchanged |

## Eyes (gaze at the limits × eye morphs, mm beyond rest)

| case | main | this PR |
|---|---|---|
| gaze | 1.36 (minor) | 1.38 (minor) |
| gaze+まばたき=0.5 | 1.46 (minor) | 1.44 (minor) |
| gaze+ウィンク / ウィンク右 | 1.36 (minor) | 1.38 (minor) |
| gaze+笑い | 0.40 (ok) | 0.52 (ok) |
| gaze+はぅ | 0.01 (ok) | 0.00 (ok) |
| gaze+はぅ=0.5 | 1.48 (minor) | 1.48 (minor) |
| gaze+まばたき, なごみ, びっくり, じと目, キリッ | 0.00 (ok) | 0.00 (ok) |
| gaze + brow / iris / highlight morphs | 1.36 (minor) | 1.38 (minor) |

Two intermediate versions failed this gate and were fixed in `master_offset`. The first took the ramp across the eye opening, which tilted the rim: まばたき=0.5 went to 1.54 mm and はぅ=0.5 to 1.60 mm. The second moved the eye back rigidly but still faded the outer corner at the face's side, and キリッ went to 7.9 mm (its socket sleeve crossed the line of sight). In the final version the eye region moves back rigidly, with no fade.
