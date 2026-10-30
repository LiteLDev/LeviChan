"""Order-balanced pairwise Codex A/B of the outer skirt from pre-rendered images (adapted from
docs/pr/r10-a3-skirt/ab.py; renders are made on a GPU node beforehand).

python3 docs/pr/r11-skirt/ab.py --old DIR --new DIR --out DIR [--poses a,b] [--models ...]   (from the repo root)
DIR/cel/<view>.png, DIR/clay/<view>.png (render.py --scale 3), DIR/pose/<pose>/<view>.png (render.py --pose).
Every item is shown twice (old|new and new|old); a pick counts only when it is the same version in both orders.
Needs PIL (not in Blender's Python)."""
import argparse, json, os, sys
from PIL import Image
ROOT = os.getcwd()
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import review, rig_rate  # noqa

_BOX = (60, 900, 1860, 2000)
REST = {'front': _BOX, 'side': _BOX, 'back': _BOX, 'q34_front_left': _BOX, 'q34_back_right': _BOX,
        'high': (60, 900, 1860, 2150)}
SCHEMA = {'type': 'object', 'additionalProperties': False, 'required': ['items'],
          'properties': {'items': {'type': 'array', 'items': {
              'type': 'object', 'additionalProperties': False, 'required': ['image', 'better', 'reason'],
              'properties': {'image': {'type': 'integer'},
                             'better': {'type': 'string', 'enum': ['left', 'right', 'tie']},
                             'reason': {'type': 'string'}}}}}}
PROMPT = """You compare two versions of the same anime character's outer skirt.
Each attached image shows the SAME view or pose twice, LEFT and RIGHT; mainly the white outer skirt
differs (the depth of its godet folds toward the hem and how the hem edge turns); the pink petticoat
under it and the hair lying on it follow it. Rest views are cel or clay renders; pose images show the
whole posed character (MMD rig, no cloth physics: the skirt is driven by bones).

Judge which side is better overall, in this order of importance:
1. natural, believable cloth in 3D (a flared skirt hanging in real godet folds, not inflated
   lobes or a stiff shell; folds that make sense; a hem that reads as cloth);
2. no unrealistic deformation in poses (collapse, pinching, stretching, intersection, kinks);
3. clean cel shading (no specks or chipped shade fragments) and closeness to a typical
   anime design of such a skirt (deep godet folds whose hem turns out at the troughs).
Answer "left", "right" or "tie" (only if you truly cannot see a meaningful difference), with a
one- or two-sentence reason naming what differs.

Images (attached in this order):
{lines}
"""


def load(p):
    im = Image.open(p).convert('RGBA')
    bg = Image.new('RGBA', im.size, (255, 255, 255, 255))
    bg.alpha_composite(im)
    return bg.convert('RGB')


def bbox_union(a, b, pad=20):
    import numpy as np
    m = (np.asarray(a).min(2) < 250) | (np.asarray(b).min(2) < 250)
    ys, xs = np.nonzero(m)
    return (max(0, xs.min() - pad), max(0, ys.min() - pad), min(a.width, xs.max() + pad), min(a.height, ys.max() + pad))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--old', required=True); ap.add_argument('--new', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--poses', default='')
    ap.add_argument('--no-rest', action='store_true')
    ap.add_argument('--models', default='gpt-6-astra,gpt-6.1-sol')
    ap.add_argument('--timeout', type=float, default=2400)
    a = ap.parse_args()
    out = os.path.abspath(a.out)
    os.makedirs(out, exist_ok=True)
    items = []
    if not a.no_rest:
        for kind in ('cel', 'clay'):
            for v, box in REST.items():
                items.append((f'rest {kind} {v}', os.path.join(a.old, kind, f'{v}.png'),
                              os.path.join(a.new, kind, f'{v}.png'), box))
    for p in [p for p in a.poses.split(',') if p]:
        for v in ('front', 'q34_front_left'):
            items.append((f'pose {p} {v}', os.path.join(a.old, 'pose', p, f'{v}.png'),
                          os.path.join(a.new, 'pose', p, f'{v}.png'), None))
    plan = []
    for i, (name, po, pn, box) in enumerate(items):
        for order in ('old_left', 'new_left'):
            left, right = (po, pn) if order == 'old_left' else (pn, po)
            plan.append(dict(item=i, name=name, order=order, left=left, right=right, box=box))
    plan = plan[0::2] + plan[1::2]
    for n, p in enumerate(plan):
        p['n'] = n + 1
        p['image'] = os.path.join(out, f'pair_{n + 1:03d}.png')
        A, B = load(p['left']), load(p['right'])
        box = p['box'] or bbox_union(A, B)
        A, B = A.crop(box), B.crop(box)
        S = Image.new('RGB', (A.width * 2 + 8, A.height), (0, 0, 0))
        S.paste(A, (0, 0)); S.paste(B, (A.width + 8, 0))
        if S.width > 2400:
            S = S.resize((2400, S.height * 2400 // S.width), Image.LANCZOS)
        S.save(p['image'])
    json.dump(plan, open(os.path.join(out, 'plan.json'), 'w'), indent=1)
    lines = '\n'.join(f'{p["n"]}. {p["name"]}' for p in plan)
    replies = rig_rate.run_codex(a.models.split(','), PROMPT.format(lines=lines), [p['image'] for p in plan], out,
                                 review.DEFAULT_CODEX, a.timeout, schema=SCHEMA)
    rows = ['| item | ' + ' | '.join(replies) + ' |', '|---|' + '---|' * len(replies)]
    tally = {m: {'new': 0, 'old': 0, 'tie': 0, 'inconsistent': 0} for m in replies}
    for i, (name, *_r) in enumerate(items):
        cells = []
        for m, r in replies.items():
            got = {it['image']: it for it in r.get('items', [])}
            picks, reasons = [], []
            for p in plan:
                if p['item'] != i:
                    continue
                it = got.get(p['n'])
                if not it:
                    picks.append('?')
                    continue
                b = it['better']
                who = 'tie' if b == 'tie' else (('old' if p['order'] == 'old_left' else 'new') if b == 'left'
                                                else ('new' if p['order'] == 'old_left' else 'old'))
                picks.append(who)
                reasons.append(it['reason'])
            if len(picks) == 2 and picks[0] == picks[1] and picks[0] in ('new', 'old'):
                v = picks[0]
            else:
                v = 'tie'
                if len(picks) == 2 and picks[0] != picks[1]:
                    tally[m]['inconsistent'] += 1
            tally[m][v] += 1
            cells.append(f'**{v}** ({"/".join(picks)}): {reasons[0] if reasons else ""}'.replace('|', '/'))
        rows.append(f'| {name} | ' + ' | '.join(cells) + ' |')
    rows.append('')
    for m, t in tally.items():
        rows.append(f"**{m}**: new {t['new']}, old {t['old']}, tie {t['tie']} "
                    f"(of which inconsistent across the two orders: {t['inconsistent']})")
    txt = '\n'.join(rows) + '\n'
    open(os.path.join(out, 'pairwise.md'), 'w', encoding='utf-8').write(txt)
    print(txt)


if __name__ == '__main__':
    main()
