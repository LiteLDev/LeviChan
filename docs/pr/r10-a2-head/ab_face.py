"""Order-balanced pairwise Codex A/B of the head/face, old (main) vs new, from pre-rendered dirs.

python ab_face.py --old DIR --new DIR --out DIR [--kinds cel,clay,m_<morph>...] [--models ...]
Each DIR holds <kind>/<view>.png (render.py --scale 4). Every item is shown in both orders;
a model's pick counts only when the same version wins both."""
import argparse, json, os, subprocess, sys
ROOT = os.getcwd()   # run from the repo root
sys.path.insert(0, os.path.join(ROOT, 'tools'))
os.chdir(ROOT)
import review, rig_rate  # noqa
B = review.DEFAULT_BLENDER
PAIRS = os.path.join(ROOT, 'docs', 'pr', 'r9-4-sleeves', 'ab_pairs.py')
BOX = {'front': (1060, 330, 1460, 730), 'q34_front_left': (900, 330, 1300, 730),
       'side': (800, 330, 1200, 730), 'turn_020': (970, 330, 1370, 730)}
SCHEMA = {'type': 'object', 'additionalProperties': False, 'required': ['items'],
          'properties': {'items': {'type': 'array', 'items': {
              'type': 'object', 'additionalProperties': False, 'required': ['image', 'better', 'reason'],
              'properties': {'image': {'type': 'integer'},
                             'better': {'type': 'string', 'enum': ['left', 'right', 'tie']},
                             'reason': {'type': 'string'}}}}}}
PROMPT = """You compare two versions of the same anime character's head and face (an MMD-style 3D model,
cel shaded or plain grey clay). Each attached image shows the SAME view twice, LEFT and RIGHT; only the
face shape may differ (forehead, nose, cheeks, mouth area, jaw, chin, profile). Some images show a facial
expression morph (blink, wink, smile, vowel mouth shapes...).

Judge which side is better overall, in this order of importance:
1. a natural, appealing, believable face in 3D for this anime style (proportions and profile, a clean
   nose, cheeks and chin that read well from the front, three-quarter and side views; no lumps, dents,
   ridges, snout or mask-like look);
2. for expression images: the expression reads cleanly (no tearing, eyelids through the eyeball,
   lips crossing, odd creases);
3. clean cel shading (no specks, broken shade fragments).
Answer "left", "right" or "tie" (only if you truly cannot see a meaningful difference), with a one- or
two-sentence reason naming what differs.

Images (attached in this order):
{lines}
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--old'); ap.add_argument('--new'); ap.add_argument('--out', required=True)
    ap.add_argument('--kinds', default='cel,clay')
    ap.add_argument('--views', default=','.join(BOX))
    ap.add_argument('--models', default='gpt-6-astra,gpt-6.1-sol')
    a = ap.parse_args()
    out = os.path.abspath(a.out)
    os.makedirs(out, exist_ok=True)
    items = []
    for kind in a.kinds.split(','):
        for v in a.views.split(','):
            po, pn = os.path.join(a.old, kind, v + '.png'), os.path.join(a.new, kind, v + '.png')
            if os.path.exists(po) and os.path.exists(pn):
                label = kind if not kind.startswith('m_') else 'cel, expression ' + kind[2:]
                items.append((f'{label} {v}', os.path.abspath(po), os.path.abspath(pn), BOX[v]))
    plan = []
    for i, (name, po, pn, box) in enumerate(items):
        for order in ('old_left', 'new_left'):
            left, right = (po, pn) if order == 'old_left' else (pn, po)
            plan.append(dict(item=i, name=name, order=order, left=left, right=right, box=box))
    plan = plan[0::2] + plan[1::2]
    for n, p in enumerate(plan):
        p['n'] = n + 1
        p['image'] = os.path.join(out, f'pair_{n + 1:03d}.png')
    json.dump(plan, open(os.path.join(out, 'plan.json'), 'w', encoding='utf-8'), indent=1)
    subprocess.run([B, '-b', '--factory-startup', '-P', PAIRS, '--', os.path.join(out, 'plan.json')], check=True,
                   stdout=open(os.path.join(out, 'pairs.log'), 'w'), stderr=subprocess.STDOUT)
    lines = '\n'.join(f'{p["n"]}. {p["name"]}' for p in plan)
    replies = rig_rate.run_codex(a.models.split(','), PROMPT.format(lines=lines), [p['image'] for p in plan], out,
                                 review.DEFAULT_CODEX, 2400, schema=SCHEMA)
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
                if picks[0] != picks[1]:
                    tally[m]['inconsistent'] += 1
            tally[m][v] += 1
            cells.append(f'**{v}** ({"/".join(picks)}): {reasons[0] if reasons else ""}'.replace('|', '/'))
        rows.append(f'| {name} | ' + ' | '.join(cells) + ' |')
    rows.append('')
    for m, t in tally.items():
        rows.append(f"**{m}**: new {t['new']}, old {t['old']}, tie {t['tie']} "
                    f"(inconsistent across the two orders: {t['inconsistent']})")
    txt = '\n'.join(rows) + '\n'
    open(os.path.join(out, 'pairwise.md'), 'w', encoding='utf-8').write(txt)
    print(txt)


if __name__ == '__main__':
    main()
