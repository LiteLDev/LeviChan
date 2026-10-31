def hbh(up, el, fl, shrug=5, pitch=-5):
    def f(arm, M, R):
        for t in 'LR':
            M.arm_pose(arm, t, up, el, fl, shrug=shrug)
        M.head(arm, pitch=pitch)
    return f
def heart(up, el, fl, shrug=6, wrist=0.0):
    def f(arm, M, R):
        for t in 'LR':
            M.arm_pose(arm, t, up, el, fl, shrug=shrug, wrist=wrist)
            M.fingers(arm, t, 0.4)
        M.centre(arm, (0.03, 0.0, -0.03)); M.spine(arm, roll=-6); M.foot(arm, 'L', (0.0, -0.05, 0.02), pitch=20); M.head(arm, roll=8)
    return f
def rub(up, el=10, fl=(0, -1, 0), shrug=10, sp=-14, hp=-12):
    def f(arm, M, R):
        M.move(arm, '全ての親', (0.0, 0.0, -0.17))
        for t in 'LR':
            M.arm_pose(arm, t, up, el, fl, shrug=shrug)
        M.spine(arm, pitch=sp); M.head(arm, pitch=hp)
    return f
def named(n):
    return lambda arm, M, R: R.apply_pose(arm, n)
VARIANTS = [
    ('hands_behind_head', named('hands_behind_head')),
    ('hbh_a', hbh((0.70, 0.60, 0.60), 125, (-0.6, 0.6, 0.4))),
    ('hbh_b', hbh((0.65, 0.70, 0.60), 125, (-0.6, 0.6, 0.4))),
    ('hbh_c', hbh((0.70, 0.70, 0.55), 120, (-0.6, 0.6, 0.4))),
    ('hbh_d', hbh((0.65, 0.75, 0.55), 115, (-0.5, 0.7, 0.3))),
    ('hbh_e', hbh((0.60, 0.80, 0.60), 120, (-0.5, 0.7, 0.4))),
    ('hbh_f', hbh((0.70, 0.65, 0.65), 120, (-0.5, 0.7, 0.4))),
    ('dance_heart', named('dance_heart')),
    ('heart_a', heart((0.60, -0.25, 0.85), 90, (-1.0, 0.0, 0.5))),
    ('heart_b', heart((0.50, -0.15, 1.00), 95, (-1.0, 0.0, 0.4))),
    ('heart_c', heart((0.45, -0.10, 1.00), 100, (-1.0, 0.1, 0.4))),
    ('heart_d', heart((0.50, -0.05, 1.00), 105, (-1.0, 0.1, 0.3))),
    ('heart_e', heart((0.40, -0.10, 1.00), 95, (-1.0, 0.0, 0.5))),
    ('heart_f', heart((0.55, -0.20, 0.95), 95, (-1.0, 0.0, 0.6))),
    ('reach_up_back', named('reach_up_back')),
    ('rub_a', rub((0.35, 0.18, 1.0))),
    ('rub_b', rub((0.40, 0.22, 1.0))),
    ('rub_c', rub((0.45, 0.30, 1.0))),
]
