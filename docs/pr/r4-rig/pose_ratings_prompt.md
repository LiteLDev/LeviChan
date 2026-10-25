You are reviewing the skeletal deformation of an anime character model (Levi) rigged for MikuMikuDance (PMX, linear blend skinning). The attached images are:

1-3. The rigged model in 17 test poses (front and 3/4 front-left view each, cel render): test, arms_up, arms_forward, wrist_twist_pos, wrist_twist_neg, squat, walk, head_left, head_right, torso_left, torso_right, swing, fist, raise_bend, reach_forward, forward_bend, side_bend.
4-8. Close-ups, each with row 1 = the previous rig and row 2 = the current rig: squat knees (clay, garments hidden), arms-up shoulders (sleeves and hair hidden), squat and walk skirt, hair swing and head turn, sleeves with arms up and forward.

The test poses are static stills without cloth or hair physics (in MMD the hair, skirt below the chain roots and sleeve drapes are physics-driven). Judge only the CURRENT rig (the pose sheets and row 2 of the close-ups).

For EACH of the 17 poses, rate the deformation as one of:
- "clean": no visible deformation problem a viewer would notice;
- "minor": small artefacts visible on inspection, acceptable for animation;
- "major": a clearly visible problem that should be fixed before use;
- "broken": tearing, explosions, limbs bent the wrong way, garments through the body.

Give a one-sentence note for each pose that is not clean, naming the location. Be consistent and calibrated: reserve "major" for problems clearly visible at the sheet's scale. You may read levi/rig.py and tools/rig_pose.py for context, but rate what the images show.
