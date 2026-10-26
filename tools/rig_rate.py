"""Render every rig_pose pose and ask the Codex models to rate each one's deformation.

    python tools/rig_rate.py [--rig out/levi.blend] [--out out/rig_rate] [--poses all]
                             [--models gpt-6.1-sol,gpt-6-astra] [--no-render] [--no-codex]

Stdlib only, like tools/review.py (whose Blender / Codex settings it shares). Steps:
  1. render.py --pose on the rigged .blend: front + 3/4 front-left per pose, cel; with
     --clay also a clay pass of the same poses (form only: knees, shoulders, cloth folds).
  2. (inside Blender) contact sheets: 01..03_poses.png (all poses, half scale) and
     04_detail.png (DETAIL_POSES at full scale, cel and clay).
  3. Codex: each model rates every pose clean / minor / major / broken with a one-line
     note (JSON schema), concurrently. Writes <model>.json and ratings.md (one table, a
     column per model; the worst rating per pose last).
"""
import argparse
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import review  # noqa: E402  (stdlib only at import time)

VIEWS = ('front', 'q34_front_left')
DETAIL_POSES = ('squat', 'walk', 'arms_up')
RATINGS = ('clean', 'minor', 'major', 'broken')
SCHEMA = {
    'type': 'object', 'additionalProperties': False, 'required': ['summary', 'poses'],
    'properties': {
        'summary': {'type': 'string'},
        'poses': {'type': 'array', 'items': {
            'type': 'object', 'additionalProperties': False, 'required': ['pose', 'rating', 'note'],
            'properties': {'pose': {'type': 'string'}, 'rating': {'type': 'string', 'enum': list(RATINGS)},
                           'note': {'type': 'string'}}}},
    },
}
PROMPT = """You are reviewing the skeletal deformation of an anime character model (Levi) rigged for
MikuMikuDance (PMX, linear blend skinning). The attached images are:

{images}

The test poses are static stills without cloth or hair physics (in MMD the hair, the skirt below the
chain roots and the sleeve drapes are physics-driven). Poses: {poses}.

For EACH pose, rate the deformation as one of:
- "clean": no visible deformation problem a viewer would notice;
- "minor": small artefacts visible on inspection, acceptable for animation;
- "major": a clearly visible problem that should be fixed before use;
- "broken": tearing, explosions, limbs bent the wrong way, garments through the body.

Give a one-sentence note for each pose that is not clean, naming the location. Be consistent and
calibrated: reserve "major" for problems clearly visible at the sheet's scale. You may read
levi/rig.py and tools/rig_pose.py for context, but rate what the images show. In "summary", name the
most important remaining deformation problem and where it is.
"""


def stage_sheets(argv):
    """Inside Blender: tile the pose renders."""
    sys.path.insert(0, ROOT)
    import contact
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--poses', required=True)
    a = ap.parse_args(argv)
    poses = a.poses.split(',')
    cel, clay = os.path.join(a.out, 'poses'), os.path.join(a.out, 'clay')
    per = 6
    for k in range(0, len(poses), per):
        imgs, labels = [], []
        for p in poses[k:k + per]:
            for v in VIEWS:
                imgs.append(contact.load(os.path.join(cel, p, f'{v}.png')))
                labels.append(f'{p} {v}')
        name = f'{k // per + 1:02d}_poses.png'
        img = contact.tile(imgs, 4, labels, scale=0.5, crop=True, title='rigged model in rig_pose poses (cel)')
        contact.save(os.path.join(a.out, name), img)
        print('SHEET', name)
    imgs, labels = [], []
    for p in DETAIL_POSES:
        if p not in poses:
            continue
        for d, tag in ((cel, 'cel'), (clay, 'clay')):
            for v in VIEWS:
                f = os.path.join(d, p, f'{v}.png')
                if os.path.isfile(f):
                    imgs.append(contact.load(f))
                    labels.append(f'{p} {v} {tag}')
    if imgs:
        img = contact.tile(imgs, 4, labels, scale=0.75, crop=True, title='detail: cel and clay (no outlines)')
        contact.save(os.path.join(a.out, '04_detail.png'), img)
        print('SHEET 04_detail.png')


def run_codex(models, prompt, sheets, out, codex, timeout):
    schema = os.path.join(out, 'rate_schema.json')
    with open(schema, 'w', encoding='utf-8') as f:
        json.dump(SCHEMA, f, indent=1)
    prompt_path = os.path.join(out, 'prompt.md')
    with open(prompt_path, 'w', encoding='utf-8') as f:
        f.write(prompt)
    procs = {}
    for m in models:
        last = os.path.join(out, f'{m}.json')
        if os.path.exists(last):
            os.remove(last)
        cmd = [codex, 'exec', '-', '--skip-git-repo-check', '--ephemeral', '-m', m, '-s', 'read-only',
               '-C', ROOT, '--color', 'never', '--output-schema', schema, '-o', last]
        if os.name == 'nt':
            cmd += ['-c', 'windows.sandbox="unelevated"']
        for s in sheets:
            cmd += ['-i', s]
        log = open(os.path.join(out, f'{m}.log'), 'w', encoding='utf-8')
        with open(prompt_path, 'rb') as stdin:
            procs[m] = (subprocess.Popen(cmd, stdin=stdin, stdout=log, stderr=subprocess.STDOUT, cwd=ROOT), log)
        print('CODEX started', m, flush=True)
    deadline = time.time() + timeout
    for m, (p, log) in procs.items():
        try:
            p.wait(timeout=max(1.0, deadline - time.time()))
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait()
        log.close()
    replies = {}
    for m in models:
        try:
            with open(os.path.join(out, f'{m}.json'), encoding='utf-8') as f:
                replies[m] = json.load(f)
        except (OSError, ValueError):
            print('CODEX no reply from', m)
    return replies


def write_table(replies, poses, out):
    models = list(replies)
    rate = {m: {r['pose']: r for r in replies[m].get('poses', [])} for m in models}
    lines = ['| pose | ' + ' | '.join(models) + ' |', '|---|' + '---|' * len(models)]
    worst = {}
    for p in poses:
        cells = []
        for m in models:
            r = rate[m].get(p, {'rating': '-', 'note': ''})
            cells.append(r['rating'] + (f": {r['note']}" if r.get('note') else ''))
            if r['rating'] in RATINGS:
                worst[p] = max(worst.get(p, 0), RATINGS.index(r['rating']))
        lines.append(f'| {p} | ' + ' | '.join(cells) + ' |')
    counts = {r: sum(1 for v in worst.values() if RATINGS[v] == r) for r in RATINGS}
    lines += ['', 'worst rating per pose: ' + ', '.join(f'{n} {r}' for r, n in counts.items() if n)]
    for m in models:
        lines += ['', f"**{m}:** {replies[m].get('summary', '')}"]
    txt = '\n'.join(lines) + '\n'
    with open(os.path.join(out, 'ratings.md'), 'w', encoding='utf-8') as f:
        f.write(txt)
    print(txt)


def main():
    if '--stage' in sys.argv:
        argv = sys.argv[sys.argv.index('--') + 1:]
        argv.remove('--stage')
        stage_sheets(argv)
        return
    ap = argparse.ArgumentParser()
    ap.add_argument('--rig', default='out/levi.blend')
    ap.add_argument('--out', default='out/rig_rate')
    ap.add_argument('--poses', default='all')
    ap.add_argument('--models', default=review.DEFAULT_MODELS)
    ap.add_argument('--no-render', action='store_true')
    ap.add_argument('--no-codex', action='store_true')
    ap.add_argument('--timeout', type=float, default=900)
    ap.add_argument('--blender', default=review.DEFAULT_BLENDER)
    ap.add_argument('--codex', default=review.DEFAULT_CODEX)
    a = ap.parse_args()
    out = review.abspath(a.out)
    os.makedirs(out, exist_ok=True)
    log = os.path.join(out, 'blender.log')
    if a.poses == 'all':
        import ast
        src = open(os.path.join(ROOT, 'tools', 'rig_pose.py'), encoding='utf-8').read()
        node = next(n for n in ast.parse(src).body if isinstance(n, ast.Assign)
                    and getattr(n.targets[0], 'id', '') == 'POSES')
        poses = [k.value for k in node.value.keys]
    else:
        poses = a.poses.split(',')
    if not a.no_render:
        rig = review.abspath(a.rig)
        review.blender([rig, '-P', 'render.py', '--', '--out', os.path.join(out, 'poses'),
                        '--views', ','.join(VIEWS), '--pose', ','.join(poses)], a.blender, log)
        detail = [p for p in DETAIL_POSES if p in poses]
        if detail:
            review.blender([rig, '-P', 'render.py', '--', '--out', os.path.join(out, 'clay'), '--clay',
                            '--views', ','.join(VIEWS), '--pose', ','.join(detail)], a.blender, log)
        print('RENDERED', len(poses), 'poses', flush=True)
    review.blender(['--factory-startup', '-P', os.path.join('tools', 'rig_rate.py'), '--', '--stage',
                    '--out', out, '--poses', ','.join(poses)], a.blender, log)
    sheets = sorted(os.path.join(out, f) for f in os.listdir(out) if f.endswith('.png'))
    if a.no_codex:
        return
    desc = {'04_detail.png': 'close-ups of ' + ', '.join(DETAIL_POSES) +
            ' at larger scale: cel (outlines, toon shade) and clay (grey, no outlines: form only)'}
    images = '\n'.join(f'{i + 1}. {os.path.basename(s)}: ' +
                       desc.get(os.path.basename(s), 'the poses, front and 3/4 front-left view each, cel render')
                       for i, s in enumerate(sheets))
    replies = run_codex(a.models.split(','), PROMPT.format(images=images, poses=', '.join(poses)),
                        sheets, out, a.codex, a.timeout)
    write_table(replies, poses, out)


if __name__ == '__main__':
    main()
