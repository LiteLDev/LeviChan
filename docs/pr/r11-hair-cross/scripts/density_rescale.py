"""density_rescale.py edges_r10.json edges_r11.json cd_r10.json cd_r11.json [poses]: per pose, hair x garment pairs and curve
for r10 and r11, and r11's pair count rescaled to r10's mesh density (each object pair's count x
(1/h_a + 1/h_b) at r10 over the same at r11, h = median edge length; an object new in r11 takes its
nearest r10 counterpart's edge)."""
import sys, json
E10, E11 = json.load(open(sys.argv[1])), json.load(open(sys.argv[2]))
C10, C11 = json.load(open(sys.argv[3])), json.load(open(sys.argv[4]))
POSES = sys.argv[5].split(',') if len(sys.argv) > 5 else list(C11)
ALIAS = {'sleeve_cuff_under': 'sleeve_cuff'}
SK = ('skirt', 'petticoat')
def h10(n):
    return E10.get(n) or E10.get(ALIAS.get(n, ''), None)
print(f"{'pose':20s} {'r10 pairs/mm':>15s} {'r11 pairs/mm':>15s} {'r11 pairs at r10 density':>26s}  pairs per mm r10 / r11")
for p in POSES:
    for grp in ('garment', 'skirt'):
        sel = lambda r: r['other'].startswith(SK) == (grp == 'skirt')
        a = [r for r in C10.get(p, []) if sel(r)]; b = [r for r in C11.get(p, []) if sel(r)]
        n10, m10 = sum(r['n'] for r in a), sum(r['mm'] for r in a)
        n11, m11 = sum(r['n'] for r in b), sum(r['mm'] for r in b)
        if not (n10 or n11):
            continue
        resc = 0.0
        for r in b:
            ha, hb = h10(r['hair']), h10(r['other'])
            if ha is None or hb is None:
                resc += r['n']; continue
            resc += r['n'] * (1 / ha + 1 / hb) / (1 / E11[r['hair']] + 1 / E11[r['other']])
        print(f"{p + ' ' + grp:20s} {n10:6d}/{m10:6.0f} {n11:7d}/{m11:6.0f} {resc:26.0f}  {n10 / max(m10, 1):.2f} / {n11 / max(m11, 1):.2f}")
