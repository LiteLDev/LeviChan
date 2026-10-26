# Run clip: pairwise Codex A/B against round 7

The same frame numbers in both clips, front + 3/4 + side, cel. Each pair is shuffled. The question: which version is the more realistic sprint stride (foot placement, knee drive, arm swing) and has better body deformation. Round 7's renders were made with round 7's clip code.

## Final keys (this PR)

| item | gpt-6-astra | gpt-6.1-sol |
|---|---|---|
| run@0 | new (clear): In the three-quarter and side views, A has a more convincing bent-knee recovery with the heel lifted behind the body, while B’s trailing leg stays extended and its frontal legs look nearly parallel, weakening the sprint stride. | new (clear): In the three-quarter and side views, A has a more convincing recovery leg with a distinctly bent knee and heel lifted behind, while B leaves the trailing leg extended low with little knee recovery. |
| run@4 | old (slight): B’s side view shows a more readable recovery leg with a distinct knee bend and heel rising behind it, while A’s lifted leg looks tightly tucked beneath the skirt with a less convincing knee-to-foot relationship. | old (slight): B’s recovering leg forms a more readable knee bend with the heel lifting behind the body, while A’s tucked leg looks cramped beneath the skirt in the three-quarter and side views. |
| run@8 | old (slight): A shows clearer forward knee drive and a bent recovery leg in the three-quarter and side views, whereas B’s lower forward knee and more extended legs give the pose a flatter, less convincing sprint action. | old (slight): A shows more knee drive and clearer separation between the bent advancing leg and the extended trailing leg, while B’s advancing knee stays lower and its stride looks more stretched out. |
| run@12 | old (clear): A’s trailing knee and calf form a more open, readable recovery bend, while B folds the trailing leg tightly against the other leg, making the knee region look compressed in the three-quarter and side views. | old (clear): A’s recovering knee and calf form a more open, readable bend, while B folds the heel tightly toward the thigh and gives the knee a pinched, hooked contour in the side view. |
| run@16 | new (clear): B shows a more convincing forward knee lift with the opposite leg extending behind, while A’s lifted leg folds across the supporting leg in a cramped, hooked shape in the three-quarter and side views. | new (clear): B’s advancing thigh and descending shin form a more plausible sprint knee drive, while A’s folded leg appears crowded across the supporting leg with a compressed, hooked knee contour. |
| run@20 | new (clear): As in run@0, A’s raised trailing heel and clearly flexed knee read as sprint recovery, while B’s extended trailing leg and nearly parallel frontal leg placement look less convincing for a sprint. | new (clear): In the three-quarter and side views, A has a more convincing recovery leg with a distinctly bent knee and heel lifted behind, while B leaves the trailing leg extended low with little knee recovery. |

**gpt-6-astra**: new better 3, old better 3, same 0
**gpt-6.1-sol**: new better 3, old better 3, same 0

## The keys before the last tweak (heel tuck and toe-off pitch 5–15° higher)

| item | gpt-6-astra | gpt-6.1-sol |
|---|---|---|
| run@0 | new (clear): B shows a more convincing running recovery, with the trailing knee bent and heel lifted behind the body, whereas A’s straighter legs and low trailing foot read more like a scissoring stride. | new (clear): B shows a more convincing recovery stride, with the trailing knee flexed and the heel lifted behind the body, while A leaves the trailing leg extended with both feet low. |
| run@4 | old (slight): A’s lifted leg has a more readable knee-to-calf transition in the three-quarter and side views, while B’s knee looks more tightly hooked beneath the skirt. | old (slight): A folds the recovering leg more compactly beneath the body, whereas B lets the knee hang lower and the foot trail farther behind, making the sprint recovery less convincing. |
| run@8 | new (slight): A’s forward knee and shin form a smoother, more open running stride, while B’s forward leg has a more abrupt hooked bend, most visible in the three-quarter view. | old (slight): B shows clearer forward knee drive and a more flexed leading leg in the oblique and side views, while A's leading leg reaches downward in a more extended position. |
| run@12 | old (slight): B’s recovering leg has a more open bend and smoother knee contour, while A’s heel folds tightly toward the thigh and makes the knee look compressed in the three-quarter view. | new (slight): A brings the recovering heel closer toward the back of the thigh with a tighter knee fold, while B leaves the lower leg projecting farther backward with less convincing sprint recovery. |
| run@16 | new (clear): A shows stronger forward knee drive with clearer separation between the legs, while B’s recovering leg folds tightly across the other leg and produces a cramped, hooked silhouette. | new (clear): A carries the raised knee farther forward and higher in the oblique and side views, while B keeps it low with the recovering foot crossing close to the opposite shin, weakening the knee drive. |
| run@20 | new (clear): A’s bent trailing knee and raised heel form a more convincing running recovery, whereas B’s straighter trailing leg and low foot make the stride look more like a scissor motion. | new (clear): A shows a flexed trailing knee and lifted heel that read as active sprint recovery, while B leaves the trailing leg extended and both feet low, producing a less convincing running stride. |

**gpt-6-astra**: new better 4, old better 2, same 0
**gpt-6.1-sol**: new better 4, old better 2, same 0

