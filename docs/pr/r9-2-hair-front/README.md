# R9-2: thicker bangs, crown grooves, and side curls moved in front of the shoulder

Baseline: main bae3160 (102,602 faces in total; `hair_front` 9,146). Final: `hair_front` 11,418 faces, under its 18,000 budget. Only `levi/parts/hair_front.py` changed. `CAP_PROFILE` and `CAP_EXP`, which hair_back imports, are unchanged. All four side-hair families keep their object names, so the rig still gives each one its own chain.

## What changed (all tunable)
- **Bangs** (`BANG_CLUMPS`, `BANG_BACK`, `BANG_WRAP`, `BANG_SINK`). The layout is the same as before, but every clump now has its own thickness (the last tuple field).
  - The three primary locks are the central sweep and one over each eye. They are 27 px (about 4.2 cm) wide, up from 24–25 px, and 22–24 mm thick. The secondary locks are 14–17 mm thick. Round 8 used 10–11.5 mm everywhere.
  - Each clump's section is now a crescent: `BANG_BACK` = −0.15 gives a concave underside, and the edges curl back (`BANG_WRAP`). A primary lock is about 1 cm thick at the middle and thinner at the edges.
  - The centreline moves back by the extra half-thickness (`BANG_SINK`, applied in full at the root and 0.3× at the tip). This keeps the outline and the tips' gap to the face as they were. Both eyes stay visible.
  - A full rebuild as 3 wide primaries plus 4 small locks was tried and dropped. Both models preferred main's fringe in the front view (`pairwise_rejected_rebuild.md`).
- **Crown** (`CROWN_*`, `CAP_AZ` 40 → 128, `CROWN_RING_SPLIT`).
  - Seven grooves radiate from a whorl slightly behind the apex. They have uneven spacing and depths, a cosine profile, a depth of 5 mm and a half-width of 10 mm.
  - The grooves are cut into the cap. The crests stay on the measured profile, so no silhouette moves; the skull lies 2.5–5 cm under the cap.
  - The front sector (±35°) has no grooves, because the bang roots form the locks there. The grooves fade out toward the hairline. Inside them the cap keeps 0.5 of its own normal.
  - The cap grid was made denser. At 40 sections the grooves aliased into a stitched, braid-like pattern.
  - In cel the grooves show only faintly, which matches the flat crown on the sheet. In clay and in oblique light they read as relief.
  - `CROWN_DEPTH = 0` restores the smooth cap.
- **Side curl (横髪巻)** (`CURL_PATH`, `CURL_FRONT`, `CURL_FRONT_ROWS`, `CURL_IN`, `CURL_FORWARD`).
  - Problem: round 8's curl crossed the top of the shoulder at the arm's own depth (side columns 276–292; the deltoid spans about 277–313) and hooked over the outer upper arm. Every raised arm therefore swept up into it.
  - Below row 170 the curl now comes forward over the front of the shoulder. At the hook it sits 22 px (3.4 cm) in front of its old path, in front of the plane the arm moves through when it is raised to the side. Its upper part stays behind the long front lock.
  - The hook keeps 0.9 of its outward reach (`CURL_IN`): 0.8 read as hugging the arm, 1.0 as floating.
  - Its broad side turns more to the side (`CURL_FORWARD` 0.7, previously 1.2), so it no longer reads as a thin strip in profile.
  - The rest pose keeps at least 27 mm of clearance to the body. `CURL_FRONT = 0`, `CURL_IN = (92, 1)` and `CURL_FORWARD = 1.2` restore round 8.

## Gate
- **Core rig check:** all 17 poses pass, as does `check.py` (`core_gate.txt`).
- **PMX:** export and re-import both pass (VMD round trip: 0.00 mm).
- **Look** (`look_metrics_delta.md`, against main):
  - Hair IoU: front 0.556 (−0.003), side 0.675 (+0.005), back 0.696 (−0.001). The small front and back losses come from the curl tip, which now flips 4 px less far out. Silhouette IoU: front −0.001, side +0.001, back −0.001.
  - Shade islands: 213 in total against 214, and 82 hair islands against 83. By view: front −2, high −3, back +1, side +2 and q34_front_left +1. The back and side extras are on hair_back lobes and the crown edge, which the old curl used to cover.
- **Motion** (`final_motion_report.md` against `baseline_motion_report.md`): hair_front has 12 major / 31 minor issue rows, against 16 / 29 on main.

  | | main | this PR |
  |---|---|---|
  | curl inside the body, spin | 20.9 % (横髪巻_2.R, f4) | 0.7 %; the clip's worst hair item is now the curtain |
  | curl inside the body, high_kick | 15.6 % | 0.5 %; the pose's worst item is now a skirt chain |
  | curl inside the body, dance_sway | 5.3 % | 2.8 % |
  | curl pop, idol_dance@15 | 53.9 mm (major) | gone |
  | curl inside the body, idol_dance@53–54 (left) | 10.9 % | 13.1 % |
  | curl inside the body, jump_tuck (left) | 1.9 % | 6.5 % |
  | curl inside the body, idol_dance@43 (right) | below threshold | 8.1 % (new major row) |
  | arms_up / look_over_shoulder / reach_up_back / hug_self | unchanged | unchanged |

  This is a trade. Arms raised to the side or overhead no longer pass through the curl. An arm that sweeps across the front of the body (the tuck and two idol_dance frames) now reaches it instead. The curl's major rows fall from 4 to 2, and the rig's bone_pop row for the curl is gone.

## Pairwise Codex A/B (`pairwise_final.md`)
Every item was shown twice, with X and Y swapped, so position bias cancels out. Main was compared against the final version: 5 rest views and 14 poses, 38 images per model.
- **gpt-6-astra:** new 25, old 10, tie 3.
- **gpt-6.1-sol:** new 20, old 14, tie 4.

**Both models prefer the new version, in both orderings,** for high_kick, arms_up, arms_forward, dance_sway, dance_point, idol_dance@14, hug_self and reach_up_back.

**The models split** on:
- spin@4 and spin@12: astra prefers new, sol prefers old;
- head_left: astra prefers old, sol prefers new;
- hands_on_hips and look_over_shoulder: astra prefers new, sol prefers old;
- the rest side view: astra prefers old, sol prefers new.

**Both models prefer main** for:
- idol_dance@81;
- the rest views from above and from the 3/4 front, where the new curl reads as less separated from the sleeve rim.

Rejected along the way:
- `pairwise_rejected_rebuild.md`: the full bang rebuild plus a 32 px curl offset. astra 5–12, sol 11–7.
- `pairwise_rejected_curl_in.md`: `CURL_IN` 0.8. astra 26–10 but sol 14–22: the curl hugged the arm.

## Left
- Arms that sweep across the front of the chest (jump_tuck, idol_dance@43 and @54) can now reach the curl. A shorter forward offset (`CURL_FRONT`) trades these against the side-raise cases. A rig-side fix would let the forearm capsules push the curl higher up.
- A head turn (head_left) still swings the curl out, because the side chains ride 頭. The two models disagree on this pose.
- From above, the curl now overlaps the sleeve rim at rest.
