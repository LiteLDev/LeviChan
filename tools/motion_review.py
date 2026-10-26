"""Contact sheets of the extended poses and motion clips, rated by Codex for unrealistic deformation.

    python tools/motion_review.py [--rig out/levi.blend] [--build] [--out out/motion_review]
                                  [--poses all|a,b] [--clips all|a,b] [--frames 6]
                                  [--metrics out/motion/motion_report.json]
                                  [--models gpt-6-astra,gpt-6.1-sol] [--no-render] [--no-codex]
                                  [--docs docs/pr/<unit> --docs-prefix baseline_]

Stdlib only (like tools/review.py and tools/rig_rate.py, whose Blender / Codex helpers it uses):
  1. (--build) build.py --rig -> --rig.
  2. render.py --pose on the rigged .blend: every extended pose (motion_poses.EXTENDED) and
     --frames evenly spaced frames of every clip ('<clip>@<frame>'; with --metrics also the
     clip's worst frames), front + 3/4 front-left, cel.
  3. (inside Blender) contact sheets: p01..pNN_poses.png (6 poses per sheet, front + 3/4) and
     c_<clip>.png (one per clip: the frames left to right, front row over 3/4 row).
  4. Codex: each model (gpt-6-astra first, gpt-6.1-sol as a second opinion) rates every pose
     and clip clean / minor / major / broken for physically unrealistic deformation of a
     human body, cloth and hair (stretching, collapsing joints, rubbery limbs, clipping, cloth
     behaving rigidly, hair through the shoulders), with the location, the parts at fault and
     the frames (JSON schema). Writes <model>.json and review.md: one table, a column per
     model, plus the automated metrics' worst level per pose / clip when --metrics is given.
"""
import argparse
import ast
import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import review  # noqa: E402  (stdlib only at import time)
import rig_rate  # noqa: E402

VIEWS = ('front', 'q34_front_left')
RATINGS = ('clean', 'minor', 'major', 'broken')
PER_SHEET = 6
DEFAULT_MODELS = 'gpt-6-astra,gpt-6.1-sol'
SCHEMA = {
    'type': 'object', 'additionalProperties': False, 'required': ['summary', 'items'],
    'properties': {
        'summary': {'type': 'string'},
        'items': {'type': 'array', 'items': {
            'type': 'object', 'additionalProperties': False,
            'required': ['name', 'kind', 'rating', 'location', 'parts', 'frames', 'issue'],
            'properties': {
                'name': {'type': 'string'}, 'kind': {'type': 'string', 'enum': ['pose', 'clip']},
                'rating': {'type': 'string', 'enum': list(RATINGS)},
                'location': {'type': 'string'}, 'parts': {'type': 'array', 'items': {'type': 'string'}},
                'frames': {'type': 'string'}, 'issue': {'type': 'string'}}}},
    },
}
PROMPT = """You are reviewing how an anime character model (Levi) deforms in motion. She is rigged for
MikuMikuDance (PMX, linear blend skinning) and posed here without cloth or hair physics: in MMD the
hair, the skirt below the chain roots and the sleeve drapes are simulated, here they only follow the
keyed / driven chain bones (so a skirt that does not drape over a seat or a lifted leg is expected to
some degree; say so when it clips through the body).

The attached contact sheets are:

{images}

Poses (static, extreme but humanly plausible): {poses}.
Clips (30 fps; each clip sheet shows the frames left to right, the front view on top and the 3/4
front-left view below, captions name the frame as clip@frame): {clips}.

For EACH pose and EACH clip answer: is any deformation physically unrealistic for a human body and for
cloth / hair? Look for: limbs stretching or going rubbery, joints collapsing or losing volume (elbows,
knees, hips, shoulders, wrists, a candy-wrapper twist of the forearm), skin folding through itself
(thigh into thigh, arm into torso), clothes or hair passing through the body (skirt into the thighs,
sleeves into the chest, hair cutting through the shoulders), cloth behaving rigidly or tearing, and for
the clips anything that pops or jumps between frames.

Rate each as one of:
- "clean": nothing a viewer would notice;
- "minor": small artefacts visible on inspection, acceptable for animation;
- "major": a clearly visible problem that should be fixed before use;
- "broken": tearing, explosions, limbs bent the wrong way, garments deep through the body.

For each item give the location on the body, the parts at fault (body, skirt, petticoat, sleeves,
bodice, hair_back, hair_front, head, shoes, accessories, rig), the frames (clips; "" for poses) and a
one-sentence issue ("" when clean). Be calibrated: reserve "major" for problems clearly visible at the
sheet's scale. You may read tools/motion_poses.py for what each pose and clip is, and levi/rig.py for
context, but rate what the images show. In "summary", name the three most important deformation
problems and where they are.
"""


def _names_from(path, var):
    src = open(os.path.join(ROOT, 'tools', path), encoding='utf-8').read()
    node = next(n for n in ast.parse(src).body if isinstance(n, ast.Assign)
                and getattr(n.targets[0], 'id', '') == var)
    return [k.value for k in node.value.keys]


def _clip_lengths():
    """{clip: frames} read from motion_poses.CLIPS without importing bpy."""
    src = open(os.path.join(ROOT, 'tools', 'motion_poses.py'), encoding='utf-8').read()
    node = next(n for n in ast.parse(src).body if isinstance(n, ast.Assign)
                and getattr(n.targets[0], 'id', '') == 'CLIPS')
    return {k.value: v.elts[0].value for k, v in zip(node.value.keys, node.value.values)}


def clip_frames(clip, length, n, metrics=None):
    """n evenly spaced frames of the clip, plus up to two of its worst frames from the
    motion report (pen / self / pop / joint), sorted."""
    fr = {round(length * i / max(1, n - 1)) for i in range(n)}
    if metrics:     # issues are ranked worst first
        iss = [r for r in metrics.get('issues', []) if r.get('set') == 'motion' and r.get('name') == clip
               and 'frame' in r and r['metric'] in ('pen', 'self', 'pop', 'joint', 'stretch', 'flip')]
        for r in iss[:2]:
            fr.add(int(r['frame']))
    return sorted(fr)


def stage_sheets(argv):
    """Inside Blender: the pose sheets and one sheet per clip."""
    import contact
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--poses', default='')
    ap.add_argument('--clips', default='', help='clip:f,f,f;clip:f,f')
    a = ap.parse_args(argv)
    poses = [p for p in a.poses.split(',') if p]
    rd = os.path.join(a.out, 'renders')
    for k in range(0, len(poses), PER_SHEET):
        imgs, labels = [], []
        for p in poses[k:k + PER_SHEET]:
            for v in VIEWS:
                imgs.append(contact.load(os.path.join(rd, p, f'{v}.png')))
                labels.append(f'{p} {"front" if v == "front" else "3/4"}')
        name = f'p{k // PER_SHEET + 1:02d}_poses.png'
        contact.save(os.path.join(a.out, name), contact.tile(
            imgs, 4, labels, scale=0.5, crop=True, title='extended poses, cel (front, 3/4 front-left)'))
        print('SHEET', name)
    for item in filter(None, a.clips.split(';')):
        clip, _, frames = item.partition(':')
        frames = frames.split(',')
        imgs, labels = [], []
        for v in VIEWS:
            for f in frames:
                imgs.append(contact.load(os.path.join(rd, f'{clip}@{f}', f'{v}.png')))
                labels.append(f'{clip}@{f}' + ('' if v == 'front' else ' 3/4'))
        name = f'c_{clip}.png'
        contact.save(os.path.join(a.out, name), contact.tile(
            imgs, len(frames), labels, scale=0.5, crop=True,
            title=f'clip {clip}: frames left to right (30 fps), front row and 3/4 row'))
        print('SHEET', name)


def write_review(replies, poses, clips, out, metrics=None):
    models = list(replies)
    rate = {m: {r['name']: r for r in replies[m].get('items', [])} for m in models}
    worst_metric = {}
    if metrics:
        for r in metrics.get('issues', []):
            if r.get('set') in ('extended', 'motion'):
                k = r['name']
                lv = ('ok', 'minor', 'major').index(r['level'])
                if lv > worst_metric.get(k, (0, ''))[0]:
                    worst_metric[k] = (lv, f"{r['metric']} {r['where'] or r['object']}")
    lines = ['| kind | name | ' + ' | '.join(models) + (' | metrics (worst) |' if metrics else ' |'),
             '|---|---|' + '---|' * (len(models) + (1 if metrics else 0))]
    worst = {}
    for kind, names in (('pose', poses), ('clip', clips)):
        for n in names:
            cells = []
            for m in models:
                r = rate[m].get(n)
                if r is None:
                    cells.append('-')
                    continue
                txt = r['rating']
                if r['rating'] != 'clean':
                    txt += f": {r['location']}" + (f" [{', '.join(r['parts'])}]" if r['parts'] else '') + \
                        (f" (frames {r['frames']})" if r.get('frames') else '') + f" {r['issue']}"
                cells.append(txt.replace('|', '/'))
                worst[n] = max(worst.get(n, 0), RATINGS.index(r['rating']))
            if metrics:
                lv, what = worst_metric.get(n, (0, ''))
                cells.append(('ok', 'minor', 'major')[lv] + (f' ({what})' if what else ''))
            lines.append(f'| {kind} | {n} | ' + ' | '.join(cells) + ' |')
    counts = {r: sum(1 for v in worst.values() if RATINGS[v] == r) for r in RATINGS}
    lines += ['', 'worst rating per pose / clip: ' + ', '.join(f'{n} {r}' for r, n in counts.items() if n)]
    for m in models:
        lines += ['', f"**{m}:** {replies[m].get('summary', '')}"]
    txt = '\n'.join(lines) + '\n'
    with open(os.path.join(out, 'review.md'), 'w', encoding='utf-8') as f:
        f.write(txt)
    print(txt)
    return txt


def main():
    if '--stage' in sys.argv:
        argv = sys.argv[sys.argv.index('--') + 1:]
        argv.remove('--stage')
        stage_sheets(argv)
        return
    ap = argparse.ArgumentParser()
    ap.add_argument('--rig', default='out/levi.blend')
    ap.add_argument('--build', action='store_true', help='build --rig first (build.py --rig)')
    ap.add_argument('--out', default='out/motion_review')
    ap.add_argument('--poses', default='all')
    ap.add_argument('--clips', default='all')
    ap.add_argument('--frames', type=int, default=6, help='evenly spaced frames per clip')
    ap.add_argument('--metrics', default='out/motion/motion_report.json',
                    help='rig_check --extended --motion report: adds worst frames and a metrics column')
    ap.add_argument('--models', default=DEFAULT_MODELS)
    ap.add_argument('--no-render', action='store_true')
    ap.add_argument('--no-codex', action='store_true')
    ap.add_argument('--timeout', type=float, default=1500)
    ap.add_argument('--blender', default=review.DEFAULT_BLENDER)
    ap.add_argument('--codex', default=review.DEFAULT_CODEX)
    ap.add_argument('--docs', default='', help='copy sheets (JPEG) and review.md here')
    ap.add_argument('--docs-prefix', default='')
    ap.add_argument('--docs-sheets', default='', help='comma-separated sheet names (default: all)')
    a = ap.parse_args()
    out = review.abspath(a.out)
    os.makedirs(out, exist_ok=True)
    log = os.path.join(out, 'blender.log')
    rig = review.abspath(a.rig)
    if a.build:
        review.blender(['-P', 'build.py', '--', '--rig', '--out', rig], a.blender, log, 'build')
    poses = _names_from('motion_poses.py', 'EXTENDED') if a.poses == 'all' else [p for p in a.poses.split(',') if p]
    lengths = _clip_lengths()
    clips = list(lengths) if a.clips == 'all' else [c for c in a.clips.split(',') if c]
    metrics = None
    mpath = review.abspath(a.metrics) if a.metrics else ''
    if mpath and os.path.isfile(mpath):
        with open(mpath, encoding='utf-8') as f:
            metrics = json.load(f)
    frames = {c: clip_frames(c, lengths[c], a.frames, metrics) for c in clips}
    names = poses + [f'{c}@{f}' for c in clips for f in frames[c]]
    if not a.no_render:
        review.blender([rig, '-P', 'render.py', '--', '--out', os.path.join(out, 'renders'),
                        '--views', ','.join(VIEWS), '--pose', ','.join(names)], a.blender, log, 'render')
        print('RENDERED', len(names), 'poses / frames', flush=True)
    for f in os.listdir(out):
        if f.endswith('.png'):
            os.remove(os.path.join(out, f))
    review.blender(['--factory-startup', '-P', os.path.join('tools', 'motion_review.py'), '--', '--stage',
                    '--out', out, '--poses', ','.join(poses),
                    '--clips', ';'.join(f'{c}:{",".join(map(str, frames[c]))}' for c in clips)],
                   a.blender, log, 'sheets')
    sheets = sorted(os.path.join(out, f) for f in os.listdir(out) if f.endswith('.png'))
    if not a.no_codex:
        if not os.path.isfile(a.codex):
            raise SystemExit(f'codex not found at {a.codex} (set LEVI_CODEX or --codex)')

        def desc(s):
            b = os.path.basename(s)
            if b.startswith('c_'):
                c = b[2:-4]
                return f'clip {c}, frames {", ".join(map(str, frames[c]))} of {lengths[c]}'
            return 'extended poses, front and 3/4 front-left view each (cel render)'
        images = '\n'.join(f'{i + 1}. {os.path.basename(s)}: {desc(s)}' for i, s in enumerate(sheets))
        prompt = PROMPT.format(images=images, poses=', '.join(poses), clips=', '.join(clips))
        replies = rig_rate.run_codex(a.models.split(','), prompt, sheets, out, a.codex, a.timeout, schema=SCHEMA)
        if replies:
            write_review(replies, poses, clips, out, metrics)
        else:
            print('CODEX no replies; see', out)
    if a.docs:
        dst = review.abspath(a.docs)
        os.makedirs(dst, exist_ok=True)
        keys = [k for k in a.docs_sheets.split(',') if k]
        pick = [os.path.basename(s) for s in sheets if not keys or any(os.path.basename(s).startswith(k) for k in keys)]
        review.blender(['--factory-startup', '-P', os.path.join('tools', 'review.py'), '--', '--stage', 'docs',
                        '--src', out, '--dst', dst, '--prefix', a.docs_prefix, '--sheets', ','.join(pick)],
                       a.blender, log, 'docs')
        for n in ['review.md'] + [m + '.json' for m in a.models.split(',')]:
            if os.path.isfile(os.path.join(out, n)):
                shutil.copyfile(os.path.join(out, n), os.path.join(dst, a.docs_prefix + n))
        total = sum(os.path.getsize(os.path.join(dst, f)) for f in os.listdir(dst))
        print(f'DOCS {dst}: {total / 1e6:.2f} MB')


if __name__ == '__main__':
    main()
