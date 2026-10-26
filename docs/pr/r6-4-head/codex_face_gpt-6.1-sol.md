# Codex (gpt-6.1-sol): close-ups, morph strip and head/neck motion

Images: head_base_cel/clay, head_final_cel/clay, morphs, head_poses_clay (hair hidden). Prompt: see the PR.

**A. The original lower-face P1 is substantially resolved in AFTER.** The chin now has volume, the jaw turns into the underside more smoothly, and the underside connects to the throat instead of reading as a ledge resting on it. I would close the original P1; the remaining issues are P2/P3 refinement.

**Lower-face naturalness: BEFORE 4/10 → AFTER 7/10.** The improvement is clearest in the side, low and 3/4-low views, and in clay.

| Remaining issue | Priority | Where visible | Concrete geometric fix |
|---|---|---|---|
| The mouth-side cheek still has a broad, somewhat flat plane; the lower face remains slightly muzzle-like in profile. | P2 | Clay Q34, side and low | Add gentle convexity between the mouth corner and lateral cheek, and slightly reduce forward projection immediately beside/below the mouth. Preserve eye-level width and eye placement. |
| The under-chin-to-throat transition is continuous but tight; the neck still reads as a fairly straight column entering a rounded jaw. | P2 | Side and low, especially clay | Spread the transition over a longer curved surface, with a little more fullness behind the chin and a softer anterior-neck contour. Preserve a readable chin–neck angle rather than filling it completely. |
| The chin pad looks a little isolated from the surrounding lower face under lighting. | P3 | Clay front and low | Broaden and soften the chin pad’s lateral falloff; blend the shallow lower-lip fold more gradually into the mouth-side surface. |

The sharp cel-shadow boundary on the cheek is **not by itself evidence of a mesh crease**; clay is the stronger evidence for the remaining flatness.

**B. Morphs**

Here, “natural” means natural within this stylized anime design.

| # | Morph | Verdict | Short note |
|---|---|---|---|
| 1 | まばたき | Natural | Closed lids follow a coherent arc; no visible penetration. |
| 2 | ウィンク | Natural | Open/closed eye combination reads cleanly. |
| 3 | ウィンク右 | Natural | Opposite wink reads cleanly; no obvious cheek disturbance. |
| 4 | 笑い | Acceptable | Reads primarily as closed eyes; little cheek lift or mouth participation for a smile. |
| 5 | あ | Acceptable | Jaw opening reads, but the 3/4 mouth corner is slightly lumpy/angular. Smooth the corner and its transition into the cheek. |
| 6 | い | Acceptable | Clean small opening, though slightly restrained horizontally for “い”. |
| 7 | う | Acceptable | Small rounded opening reads; lip rounding/projection is minimal. |
| 8 | え | Acceptable | Readable, but close to a smaller “あ”; a wider, less tall opening would distinguish it. |
| 9 | お | Acceptable | Vertical rounded opening reads; slightly tube-like at 3/4, so soften the lip perimeter. |

No obvious mouth penetration is visible in this strip. These small stills cannot establish whether the internal mouth surfaces remain clean throughout interpolation.

**C. Anything worse**

- The front chin is broader and blunter, reducing fidelity to the sheet’s V shape. That is within the approved tradeoff and improves 3D naturalness.
- The fuller chin makes the tight throat transition more noticeable in low views. The actual junction is still considerably better than BEFORE.
- I see no clear regression in eye placement, eye-level face width, or overall cheek symmetry.

**D. Motion / deformation**

**No major or broken deformation is evident in image 6.** I see no clear poke-through, neck separation or collapsed jaw. The recurring concern is localized compression or a tight bend beneath the jaw. “Minor” below marks a visible shape concern, not a confirmed physically impossible deformation.

| Pose | Rating | Visible result |
|---|---|---|
| head_left | **Clean** | Jaw and chin retain volume; neck connection stays continuous through the views. |
| head_right | **Clean** | No obvious collapse or separation; the dark side-view region alone does not establish pinching. |
| forward_bend | **Minor** | Side view shows a concentrated bend beneath/behind the jaw; distribute the neck bend over more of its length. |
| side_bend | **Minor** | Compressed side of the jaw–neck junction looks tight; preserve lateral neck volume and allow a broader compression fold. |
| nod_down | **Minor** | Under-chin clearance becomes tight, with a somewhat abrupt jaw-to-front-neck turn; soften compression over several loops. |
| nod_up | **Minor** | Front throat becomes rather straight and taut in side/low views; distribute extension along the neck and preserve some anterior curvature. |
| tilt_l | **Clean** | Mild tilt preserves face and neck volume; no visible structural failure. |
| turn_nod | **Minor** | Combined motion crowds the compressed jaw–neck junction, especially in low view; spread twist and bend through the neck rather than concentrating them at its top. |

The stills support **“no visible severe failure in these sampled poses,”** rather than full animation clearance: intermediate frames and a wireframe/intersection check are needed to confirm that.