| pose | gpt-6.1-sol | gpt-6-astra |
|---|---|---|
| test | clean | clean |
| arms_up | minor: The exposed upper arms pinch slightly at the shoulder/armpit transitions, most visibly in the front view. | minor: The raised upper arms show slight narrowing and angular transitions at the armpits beneath the sleeve attachments, most apparent in the front view. |
| arms_forward | clean | clean |
| wrist_twist_pos | clean | minor: The wrists show a small pinched transition between the cuffs and rotated hands, most noticeable in the front view. |
| wrist_twist_neg | clean | clean |
| squat | minor: The bent knee regions show localized pinching and lumpy thigh-to-calf transitions in the 3/4 view, confirmed by the clay render. | minor: The deeply bent knees develop angular compression creases and slightly flattened contours at the thigh–calf folds, clearest in the 3/4 cel and clay views. |
| walk | clean | clean |
| head_left | clean | clean |
| head_right | clean | clean |
| torso_left | clean | clean |
| torso_right | clean | clean |
| swing | clean | clean |
| fist | clean | clean |
| raise_bend | clean | clean |
| reach_forward | clean | clean |
| forward_bend | minor: The front waist of the bodice compresses into a small, abrupt horizontal crease just above the bow. | clean |
| side_bend | minor: The bodice develops a slight angular pinch at the waist on the compressed side of the bend. | clean |

worst rating per pose: 12 clean, 5 minor

**gpt-6.1-sol:** The most noticeable remaining issue is compression around the bent knees in squat: the thigh-to-calf transitions look pinched and lumpy in the 3/4 view, also visible in clay. Overall, the rig holds up well at the sheet's scale; the remaining issues are minor, with no clearly major or broken deformation visible. Static hair, skirt and sleeve-drape positioning was not counted as a deformation defect.

**gpt-6-astra:** The most important remaining deformation issue is knee compression in squat: the 3/4 view shows angular, pinched contours where the thighs fold against the calves, also visible in the clay render. This is a minor issue at the supplied sheet scale; no pose shows clear major or broken deformation. Ratings account for the absence of hair, skirt and sleeve-drape physics, and do not count framing crops as rig defects.
