# R8-6: face details (ears, eye layers, lashes, mouth interior, expression set)

Files: `levi/parts/head.py`; the morph table in `export_pmx.py` (`MORPH_INFO` only); the morph checks in `tools/pmx_reimport.py`; the eye-check morph list in `tools/motion_check.py`. No other part, `spec`, `common`, `toon` or `rig` changes.

- Head budget: 8,757 → 12,021 faces (of 18,000).
- Model total: 102,274 faces (of 200,000).

## What changed

### Ears
- The old ears were 2 cm blobs, entirely below the eye. They are now about 2.95 cm tall and run from the upper lid to the nose tip, so they span eye level as both references' ears do. They sit a little behind the head's widest point, with the top leaning back 12°.
- Construction: an oval plate on the side of the head.
  - Its back plane is sunk into the skin at the front edge and bent top to bottom to follow the head's curve.
  - The back edge stands out 20°.
  - The outer face has a rolled helix rim over the top and back, the scapha groove, the antihelix ridge, a concha bowl, the tragus and a soft lobe.
- They are hidden under the hair in every review view (the old ear peeked out on the front view; that is gone). They ride 頭.

### Eyes
- **Real lashes** (`head_eye_lash_L/R`, rigid on 頭):
  - The upper lash is now a thin solid over the painted lash mass, plus an outer flick ribbon.
  - It stands forward along −y only, so the front view is unchanged. Its lower edge stands 0.4–1.2 px forward of the lid, tapering at both ends, so it reads in profile and 3/4.
  - It rides the lid band through every eye and brow morph (`SkinDecal`: a root on the eye patch plus an offset that turns with the triangle under it), so the lashes follow the blink.
- **Lid-shadow layer** (`head_eye_shade_L/R`, on 頭):
  - A band just in front of the white and behind the iris, so the turning iris covers it.
  - It carries the upper lid's soft blue-grey shadow, which used to be painted on the white (and mostly hidden under the lash).
  - Its shape keys ride the upper lid's edge, so the shadow stays under the lid in なごみ, じと目, びっくり and a blink in progress.
- **Highlights** (`head_eye_hilite_L/R`): two discs just in front of the iris, no longer painted on it.
  - They ride the eye bone with the iris. A static highlight would leave the iris at the gaze limits: the eyeball has a 36 px radius, so the iris moves about 6 px there, and the iris radius is only 8.4 px.
  - They do not shrink with 瞳小, and ハイライト消 puts them out.
- The white texture is now plain white. The iris keeps its lash-shadow band.

### Mouth
- The pouch is now a rounded cavity (`POUCH_RINGS`): three rings plus a back centre.
  - The lips' inner rim and the cavity are 'mouth' material, so an open mouth is no longer ringed by the stretched painted lip line.
  - The cavity floor rides the jaw and the roof stays with the head (`pouch_share`).
- **Upper teeth** (`head_mouth_teeth`, palette 'cuff'):
  - A curved band under the roof, its lower edge just above the slit.
  - It is hidden while the mouth is closed and shows in あ/い/え/ワ/▲/にやり (the upper lip now lifts 0.75–1.4 px in those).
  - 歯無し上 lifts it into the gum.
- **Tongue** (`head_mouth_tongue`): a flattened ellipsoid on the floor that rides the jaw.
  - ぺろっ pushes its front out over the lower lip.
- The outline hull thins toward the slit (`MOUTH_OUTLINE`), which removes the dark hull wedges that showed at the corners of an open mouth (they were there on main too).

### Expression set: 9 → 36 morphs, all in their PMX panels
| panel | morphs |
|---|---|
| eye (11) | まばたき, ウィンク, ウィンク右, 笑い, はぅ, なごみ, びっくり, じと目, キリッ, 瞳小, ハイライト消 |
| brow (6) | 真面目, 困る, にこり, 怒り, 上, 下 |
| mouth (16) | あ, い, う, え, お, ワ, ん, ∧, ω, ▲, にやり, 口角上げ, 口角下げ, 口横広げ, ぺろっ, 歯無し上 |
| other (3) | 照れ, 涙, 汗 |

- **Eye morphs:**
  - 笑い now closes on an upward arch (the middle above both corners).
  - はぅ closes the lids on a line rising from the inner corner, which forms the upper stroke of `>` / `<`. The lower stroke is an overlay.
  - The open-eye morphs (なごみ, びっくり, じと目, キリッ) shift the upper and lower lid edges. The inner edge is interpolated in order, so the lids never cross.
- **Brows:**
  - The painted brow moves with the skin: the front-view shift is fully applied on the brow line, fades over the forehead, and reaches nothing at the lash band, so the eye keeps its shape.
  - The shifted points go back on the face.
  - The brow morphs are subtle by design, since the brows are mostly under the bangs.
- **Overlays** (照れ, 涙, 汗, and the はぅ stroke):
  - They are small geometry that waits 10 px inside the head at rest, and their key moves them 0.15 px off the skin.
  - They also carry the face's own morphs (piecewise linear over the eye patch, else the nearest skin), so 照れ + 笑い and 涙 + 笑い add up without the cheek coming through.
- Names and English names are in `export_pmx.MORPH_INFO`.
- `pmx_reimport` now checks:
  - every morph's panel and English name against `MORPH_INFO`, read from the source;
  - that the head's whole set (`head.ALL_MORPHS`) is present.

## Verification
| check | result |
|---|---|
| `tools/check.py` | OK (head 12,021 / 18,000; total 102,274), repeatable |
| `tools/rig_check.py` (core gate) | RIG CHECK OK. Eye poke at the gaze limits 1.36 mm (main: 1.36). Four objects on 目: the irises and the highlights. |
| weights | Lashes, lid shadow, overlays and ears: 頭 100%. Teeth and tongue: 頭 ≥ 98% (the cavity around them has the same small 上半身2 share). |
| motion eye check (gaze limits × eye + brow morphs, now including 瞳小 / ハイライト消) | see below |
| `export_pmx.py` + `tools/pmx_reimport.py` | REIMPORT OK. 36 vertex morphs, panels brow 6 / eye 11 / mouth 16 / other 3, all moving and in the 表情 frame |
| visibility probe (scratch, per morph and combinations) | At rest, no overlay, tooth or tongue vertex can be seen. In their morphs, overlays sit in front of the skin; 照れ+笑い, 涙+笑い, 汗+ワ and 照れ+涙+汗+笑い+あ stay clear (照れ: 4 of 340 vertices at the cheek's silhouette edge). ぺろっ: no tongue vertex behind the skin. |
| `review.py --focus head` vs main | Silhouette IoU unchanged (front 0.915). Skin regions ±0.000. Skin shade islands +1 on the front and the 3/4 view. Every pose is clean for the head (both models). Metrics: `final_metrics_delta.md`. |

Motion eye check (`rig_check --extended`; mm the eyes come further out of the face than at rest, with the gaze at the limits; minor 0.8, major 1.5; not gated):

| case | main | this PR |
|---|---|---|
| gaze alone, ウィンク, ウィンク右, every brow morph, 瞳小, ハイライト消 | 1.36 | 1.36 |
| まばたき | 0.00 | 0.00 |
| まばたき=0.5 | 1.34 | 1.46 (a highlight disc, 0.015 px in front of the iris) |
| 笑い | 0.00 | 0.42 |
| はぅ / はぅ=0.5 | – | 0.01 / 1.48 |
| なごみ, びっくり, じと目, キリッ | – | 0.00 |

Every case is under the 1.5 mm major level.
- はぅ=0.5 was 1.59 before the follow-up. The lids now meet lower (`HAU_LINE` 120 / 7 px rise, was 118.5 / 7.5), which shortens the lower lid's travel.
- A denser iris disc (10 rings) for 瞳小 made the metric sample the closed lids' inner rim and report 6.7 mm in 笑い, although nothing changed on screen. The disc uses 8 rings.

### Codex
- **Pairwise A/B** of face close-ups (A = main, B = this PR; front / 30° / 45° / side / high / low / 3/4 low, cel and clay, plus with the hair against the sheet; `ab_face_*.jpg`). Both models prefer **B, 4/5**, in both rounds:
  - the ears now attach and read as ears;
  - the cheek–jaw–ear relation is better.
  
  Their main reservation is the lid/lash assembly in clay.
- **Morph strip** (all 36, front / 3/4 / side: `morphs_*.jpg`; replies in `codex_morphs_final_*.md`):
  - No morph is rated broken, and neither model finds penetration or tearing.
  - Rated unnatural in the final round: はぅ (both: a wedge in 3/4), ぺろっ (both: the tongue does not clearly hang out), ▲ (astra: not triangular enough), 笑い (astra: the lash tips at the outer corner), 瞳小 (sol: it shrinks the iris, not only the pupil).
  - Everything else is natural or acceptable.
- **Round 1 → final.** Fixed after round 1:
  - 笑い (now an upward arch);
  - ∧ (a monotone inverted V);
  - ▲ (an apex and a flat lower lip);
  - ワ (wider);
  - the tears (they now run down the front of the cheek instead of sweeping sideways);
  - the tongue (lifted over the lower lip, lighter than the cavity);
  - the はぅ stroke (bowed and tapered);
  - the lash ends (tapered, no end caps);
  - the highlights moved closer to the iris (0.095 px in front of the white; the iris is at 0.08 px).

### Follow-up (coordinator review)
- **キリッ:** renamed from the half-width ｷﾘｯ to the full-width spelling most VMD motions key. The change covers `head.EYE_OPEN`, `MORPH_INFO` and the eye check list.
- **はぅ=0.5:** 1.59 → 1.48 mm, by having the lids meet lower (see the eye check above).
- **瞳小:** only the painted pupil shrinks now (to 50% about its own centre, `pupil_squeeze`). The iris disc and its rim stay.
- **ぺろっ:** the tongue (now lighter than the cavity) hangs out over the lower lip.
- **▲:** wider base, flatter lower lip, 3° of jaw.
- **笑い / はぅ:** the lash flick folds in to 45% of its length while the lids are closed.
- **Codex round 3** on the final build (all 36 morphs; `codex_morphs_round3_*.md`):
  - No morph is broken, and neither model reports penetration.
  - ぺろっ and 瞳小 are no longer flagged.
  - Still rated unnatural: はぅ (both: the strokes are long and separate in 3/4 and side), 笑い (astra: pinched outer corner), ▲ (astra: still not clearly triangular) and キリッ (astra: reads like another half-lidded state).

### Remaining (not addressed here)
- The head review's P1 is the lower cheek → jaw bevel in 3/4 and clay. That is lower-face construction from round 6, outside this unit.
- In clay, the lash solid reads as a separate strip over the lid. In cel it is the dark lash and reads correctly.
- The はぅ strokes separate in depth in 3/4. ▲ and キリッ read weakly.
