# Codex (gpt-6-astra): close-ups, morph strip and head/neck motion

Images: head_base_cel/clay, head_final_cel/clay, morphs, head_poses_clay (hair hidden). Prompt: see the PR.

**A. The original lower-face P1 is substantially resolved in AFTER.** The pointed shield shape and abrupt chin corner are much reduced, and the jaw now connects to the throat through a curved transition. I would not retain the original finding at P1 based on these views.

**Lower-face naturalness: BEFORE 4/10 → AFTER 7/10.** The largest improvement is visible in clay, especially front, 3/4 and low views. Remaining issues are refinement-level:

| Priority | View | Remaining problem | Concrete geometric fix |
|---|---|---|---|
| **P2** | Side, 3/4 low; clay most clearly | The mouth-side cheek still forms a broad, somewhat flat projecting mass. The chin is rounder, but the lower face retains a mild muzzle-like profile. | Slightly recess the surface **around and below the mouth corners**, blending into the lateral cheeks. Preserve central lip/chin projection and the fixed eye-level width. |
| **P2** | Side and low | The underside of the jaw still has a relatively long, straight run before a tight turn into the throat. The fillet improves continuity, but its curvature remains concentrated near the neck. | Spread the transition across more of the under-jaw surface: gently round the underside and broaden the front/side neck transition, rather than enlarging only the local fillet. |
| **P3** | Front and low clay | The chin pad reads as a small central rounded bump, with a slight hollow immediately above it in some lighting. | Reduce the pad’s local prominence and distribute its volume farther laterally; soften the shallow fold below the lower lip. |

**B. Morphs**

These ratings describe the visible endpoints; the strip does not establish how cleanly they interpolate or combine.

| # | Morph | Rating | Short note |
|---|---|---|---|
| 1 | まばたき | **Natural** | Closed lid arcs look coherent; no obvious penetration. |
| 2 | ウィンク | **Natural** | Closed and open sides retain consistent surrounding face shape. |
| 3 | ウィンク右 | **Natural** | Opposite wink reads cleanly; the closed far eye is less inspectable in 3/4. |
| 4 | 笑い | **Acceptable** | Clean smiling-eye closure, but little cheek response makes it somewhat mechanical. |
| 5 | あ | **Acceptable** | Jaw opening reads, but the 3/4 mouth corner is angular and the inner opening looks uneven. |
| 6 | い | **Acceptable** | Plausible narrow opening; mouth corners could spread slightly more for a clearer “い.” |
| 7 | う | **Acceptable** | Small opening reads, but limited lip rounding/projection makes it look like a hole in the face. |
| 8 | え | **Acceptable** | Plausible wider opening; corner transitions are a little abrupt in 3/4. |
| 9 | お | **Acceptable** | Rounded opening reads; more lip rounding would distinguish it from a small “あ.” |

No unequivocal mouth penetration is visible at this scale.

**C. Anything worse**

- **The side-view throat transition now looks slightly scooped out.** The rounded chin against the relatively narrow neck makes the remaining under-jaw run more conspicuous, even though the connection itself is improved.
- The front chin is broader and softer, reducing the sheet’s sharp V shape. **That is an approved fidelity tradeoff, not a naturalness regression.**
- No clear new eye-placement or eye-level-width regression is visible.

**D. Motion**

**No major or broken deformation is evident in image 6.** The concerns are localized neck narrowing and tight curvature under compression. Still images cannot certify that there is no hidden intersection or transient failure between poses.

| Pose | Rating | Visible assessment |
|---|---|---|
| **head_left** | **Clean** | Face and jaw retain volume; the neck connection remains continuous. |
| **head_right** | **Clean** | No obvious facial distortion, neck separation or poke-through. |
| **forward_bend** | **Minor** | Side view shows a tight compressed turn beneath the jaw; no clear collapse. |
| **side_bend** | **Minor** | Compressed side of the upper neck looks pinched, especially in side view; head volume holds. |
| **nod_down** | **Minor** | Under-chin/upper-throat transition tightens sharply in side view; soften the compressed contour. |
| **nod_up** | **Minor** | Front throat becomes narrow and taut beneath the broad jaw; low view emphasizes the column-like neck. No visible tear or separation. |
| **tilt_l** | **Clean** | Mild lateral bend preserves a plausible continuous neck silhouette. |
| **turn_nod** | **Minor** | Combined rotation and bend produce the strongest localized neck narrowing; no definite collapse or intersection is visible. |

For the **minor** motion issues, distribute rotation and deformation over a longer neck region and add pose-dependent volume correction beneath the jaw. Keep the jaw/chin moving with the head while allowing the throat transition to compress and stretch more gradually.