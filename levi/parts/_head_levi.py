"""Levi's temperament on 风堇's face (round 11): the constants levi/parts/head.py and
tools/prep_hyacine_head.py share (no bpy here).

ref/setting.png, ref/illustration.png and ref/levi_threeview.png draw Levi gentle,
quiet and shy, a little dreamy (温柔、安静、内向羞怯，带一点迷离): heavy flat upper lids
over the iris top, a thin even lash line ending in one flat outer blade, brows whose
inner ends rise a little, a small level mouth. 风堇's face is the base (her mesh,
topology and morphs); her rest is moved toward Levi's by a little of her own morphs
(the bakes below: every key is then W(p + bake + her offset)) and by Levi's paint and
decal shapes.
"""

# her upper lids lowered and flattened: k of her なごみ (まばたき 0.42 + 慈愛 1.0); the
# lid edge is 5.8 mm in front of the iris, so seen from above the lid covers more (0.24:
# the lowest of the 0.24 .. 0.30 band; it puts the margin 0.356 D over the widest iris row
# and the iris 0.83 as tall as wide in front, the design's; pairwise Codex 0.24 / 0.28: 2-2)
LID_K = 0.24
NEUTRAL_LID = (('まばたき', 0.42 * LID_K), ('慈愛', LID_K))
# ... taken in full over the iris's middle, less toward the corners (x' [D] from the iris centre, +
# toward the nose): her lid lowered as it was kept her round dome; this way the lowered lid is long
# and flat (the design's lid line rises 0.06-0.07 IPD from its ends): (outer: from, to x', share left
# at the corner), (inner: from, to x', share left at the end)
LID_SHAPE = ((0.20, 0.85, 0.10), (0.20, 0.55, 0.50))


def lid_weight(xp):
    """The share of the lid bake at x' (array)."""
    import numpy as np
    xp = np.asarray(xp, float)
    (o0, o1, ow), (i0, i1, iw) = LID_SHAPE

    def sm(e0, e1, x):
        t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
        return t * t * (3.0 - 2.0 * t)
    return np.where(xp < 0, 1.0 - (1.0 - ow) * sm(o0, o1, -xp), 1.0 - (1.0 - iw) * sm(i0, i1, xp))


# the mouth small and level (15.4 mm wide, the corners 0.1 mm over the middle: at 0.25 they stood
# 0.3 mm over it and the line bowed into a faint polite smile); the brows' inner ends up (her
# 困る, ~+9 deg at 1.0; pairwise Codex 0.85 over 0.70 4-0, 1.0 over 0.85 4-0)
NEUTRAL_MOUTH = (('口横缩げ', 0.95), ('口角下げ', 0.31))
NEUTRAL_BROW = (('困る', 1.0),)
NEUTRAL = NEUTRAL_MOUTH + NEUTRAL_BROW
# keys whose lids meet: on the side they close they start from her own rest lid (no lid
# bake), so they close exactly as hers; the open side of a wink keeps the bake
LID_MEET = ('まばたき', 'ウィンク', 'ウィンク右', '笑い', 'はぅ', 'ウィンク２', 'ウィンク２右', '笑い2', '笑い3')

# upper lash thickness above the lid margin [D = iris width incl. its rim], by x' (from
# the iris centre in D, + toward the nose): a thin even line, heavier in the outer third,
# tapering out at the nasal end (ref/setting.png front, levelled)
LASH_T = ((-0.85, 0.15), (-0.75, 0.17), (-0.50, 0.145), (-0.25, 0.12), (0.0, 0.115), (0.25, 0.105),
          (0.40, 0.095), (0.50, 0.07), (0.62, 0.03))
LASH_WALL_T = (0.06, 0.03)         # D: the outer wall line under the wing: at its top, at its lower end
LASH_FEATHER = (0.42, 0.62)        # x' [D]: the nasal end feathers from navy to mauve
