"""Order-balanced pairwise Codex A/B of the front hair, old (main) vs new (adapted from r9-4-sleeves).

python ab.py --old-blend B --new-blend B --old-rig R --new-rig R --out DIR [--poses a,b] [--no-render]
Every item is shown twice (old|new and new|old). A model's pick counts only when it is
the same version in both orders; otherwise it is a tie (position bias).
Run from the repo root (render.py, tools/review.py)."""
import argparse, json, os, subprocess, sys
ROOT = os.getcwd()
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import review, rig_rate  # noqa
HERE = os.path.dirname(os.path.abspath(__file__))
B = review.DEFAULT_BLENDER

# rest views: render scale 3 (1920 x 3072), crop of the head and hair (x0, y0, x1, y1)
REST = {'front': (576, 30, 1344, 740), 'q34_front_left': (576, 30, 1344, 740), 'side': (576, 30, 1344, 740),
        'high': (576, 30, 1344, 740), 'q34_back_right': (576, 30, 1344, 740)}
# face close-ups (cel only): the fringe over the eyes
CLOSE = {'front': (730, 60, 1190, 420), 'q34_front_left': (730, 60, 1190, 420)}

SCHEMA = {'type': 'object', 'additionalProperties': False, 'required': ['items'],
          'properties': {'items': {'type': 'array', 'items': {
              'type': 'object', 'additionalProperties': False, 'required': ['image', 'better', 'reason'],
              'properties': {'image': {'type': 'integer'},
                             'better': {'type': 'string', 'enum': ['left', 'right', 'tie']},
                             'reason': {'type': 'string'}}}}}}

PROMPT = """You compare two versions of the same anime character's front hair: the crown / scalp,
the fringe (bangs) over the forehead and eyes, and the face-framing side locks. Each attached image
shows the SAME view or pose twice, LEFT and RIGHT; only the front hair may differ (the long back
hair follows the crown's shape). Rest views are cel or clay close-ups of the head; pose images show
the upper body of the posed character (MMD rig, no hair physics).

Judge which side is better overall, in this order of importance:
1. natural, believable hair in 3D (a head of hair with real volume and lock structure that sits
   on a plausible skull, a fringe with readable locks, both eyes readable);
2. no unrealistic deformation in poses (hair passing through the face, body or arms, kinks,
   stretching, locks detaching from the head);
3. clean cel shading (no specks or chipped shade fragments) and closeness to a typical
   anime design of such a hairstyle.
Answer "left", "right" or "tie" (only if you truly cannot see a meaningful difference), with a
one- or two-sentence reason naming what differs.

Images (attached in this order):
{lines}
"""


def render(blend, out, args, log):
    review.blender([os.path.abspath(blend), '-P', 'render.py', '--', '--out', out, '--no-regions'] + args, B, log,
                   'render ' + out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--old-blend'); ap.add_argument('--new-blend')
    ap.add_argument('--old-rig'); ap.add_argument('--new-rig')
    ap.add_argument('--out', required=True)
    ap.add_argument('--poses', default='head_left,look_over_shoulder,jump_tuck,high_kick,spin@14,'
                                       'idol_dance@54,arms_up')
    ap.add_argument('--no-render', action='store_true')
    ap.add_argument('--no-rest', action='store_true')
    ap.add_argument('--models', default='gpt-6-astra,gpt-6.1-sol')
    a = ap.parse_args()
    out = os.path.abspath(a.out)
    os.makedirs(out, exist_ok=True)
    log = os.path.join(out, 'blender.log')
    poses = [p for p in a.poses.split(',') if p]
    if not a.no_render:
        for tag in ('old', 'new'):
            blend, rig = getattr(a, f'{tag}_blend'), getattr(a, f'{tag}_rig')
            if not a.no_rest:
                render(blend, os.path.join(out, tag, 'cel'), ['--views', ','.join(REST), '--scale', '3'], log)
                render(blend, os.path.join(out, tag, 'clay'), ['--views', ','.join(REST), '--scale', '3', '--clay'], log)
            if poses:
                render(rig, os.path.join(out, tag, 'pose'), ['--views', 'front,q34_front_left', '--scale', '2',
                                                              '--pose', ','.join(poses)], log)
    items = []          # (name, old image path, new image path, crop or None)
    if not a.no_rest:
        for kind in ('cel', 'clay'):
            for v, box in REST.items():
                items.append((f'rest {kind} {v}', os.path.join(out, 'old', kind, f'{v}.png'),
                              os.path.join(out, 'new', kind, f'{v}.png'), box))
        for v, box in CLOSE.items():
            items.append((f'face close-up cel {v}', os.path.join(out, 'old', 'cel', f'{v}.png'),
                          os.path.join(out, 'new', 'cel', f'{v}.png'), box))
    for p in poses:
        for v in ('front', 'q34_front_left'):
            items.append((f'pose {p} {v}', os.path.join(out, 'old', 'pose', p, f'{v}.png'),
                          os.path.join(out, 'new', 'pose', p, f'{v}.png'), 'top'))
    plan = []
    for i, (name, po, pn, box) in enumerate(items):
        for order in ('old_left', 'new_left'):
            left, right = (po, pn) if order == 'old_left' else (pn, po)
            plan.append(dict(item=i, name=name, order=order, left=left, right=right, box=box,
                             image=os.path.join(out, f'pair_{len(plan):03d}.png')))
    # interleave so the two orders of one item are far apart
    plan = plan[0::2] + plan[1::2]
    for n, p in enumerate(plan):
        p['n'] = n + 1
        p['image'] = os.path.join(out, f'pair_{n + 1:03d}.png')
    with open(os.path.join(out, 'plan.json'), 'w', encoding='utf-8') as f:
        json.dump(plan, f, indent=1)
    subprocess.run([B, '-b', '--factory-startup', '-P', os.path.join(HERE, 'ab_pairs.py'), '--',
                    os.path.join(out, 'plan.json')], check=True, stdout=open(log, 'a'), stderr=subprocess.STDOUT)
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
                    f"(of which inconsistent across the two orders: {t['inconsistent']})")
    txt = '\n'.join(rows) + '\n'
    open(os.path.join(out, 'pairwise.md'), 'w', encoding='utf-8').write(txt)
    print(txt)


if __name__ == '__main__':
    main()
