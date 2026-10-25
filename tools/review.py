"""One-command model review: renders, contact sheets and a two-model Codex review.

    python tools/review.py [--blend out/levi.blend] [--rig out/levi_rig.blend] [--build]
                           [--out out/review] [--focus hair_back] [--turntable 8]
                           [--poses walk,arms_up,...] [--models gpt-6.1-sol,gpt-6-astra]
                           [--no-codex] [--timeout 900] [--baseline out/review_main]

Runs in any Python 3.9+ (stdlib only), including Blender's bundled one. Steps:
  1. (--build) build.py -> --blend, and build.py --rig -> --rig
  2. render.py: the sheet views + q34_front_left / q34_back_right / high in cel
     (with region labels) and in --clay; the --rig .blend in a few POSES
     (front + 3/4); --turntable N extra angles
  3. tools/compare.py on the sheet views (IoU / per-region report -> metrics.txt)
  4. this file again inside Blender (--stage sheets): contact sheets
       01_ortho_sbs.png   reference (top) vs cel render (bottom): front, side, back
       02_angles_cel.png  cel: q34_front_left, q34_back_right, high
       03_clay.png        clay: front, side, back, q34_front_left, q34_back_right, high
       04_poses.png       rigged model posed (front + 3/4 per pose), if --rig exists
       turntable.png      --turntable N
       05_islands.png     cel renders with the small shade islands painted red
     and shade_stats.txt: per-view, per-region share of the shade tone (the cel
     look should stay mostly lit, with a similar balance, at every angle), and
     shade_islands.txt: per-view, per-region count / area of small shade
     islands (regions.shade_islands: specks and slivers; fewer is cleaner)
     (--baseline DIR) metrics_delta.md: metrics.txt / shade_islands.txt changes
     against an earlier review dir, also appended to summary.md
  5. Codex: every --models model reviews the sheets concurrently (real child
     processes, waited on, --timeout s each), read-only, structured JSON output
     (--output-schema), prioritised naturalness > animation > fidelity, per part.
Writes <out>/<model>.md (+ .json, .log), <out>/summary.md (merged by part) and
<out>/prompt.md. Paths may be relative to the repo root.

Environment: LEVI_BLENDER (default: Blender 5.2 under Program Files), LEVI_CODEX
(default: %LOCALAPPDATA%/Programs/OpenAI/Codex/bin/codex.exe).
"""
import argparse
import glob
import json
import math
import os
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_BLENDER = os.environ.get(
    'LEVI_BLENDER', r'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe')
DEFAULT_CODEX = os.environ.get('LEVI_CODEX', os.path.join(
    os.environ.get('LOCALAPPDATA', ''), 'Programs', 'OpenAI', 'Codex', 'bin', 'codex.exe'))
DEFAULT_MODELS = 'gpt-6.1-sol,gpt-6-astra'
DEFAULT_POSES = 'walk,arms_up,squat,forward_bend,head_left,swing'
SHEET_VIEWS = ('front', 'side', 'back')
REVIEW_VIEWS = ('q34_front_left', 'q34_back_right', 'high')
POSE_VIEWS = ('front', 'q34_front_left')
CATEGORIES = ('naturalness', 'animation', 'fidelity')


def parts():
    names = sorted(os.path.splitext(os.path.basename(p))[0]
                   for p in glob.glob(os.path.join(ROOT, 'levi', 'parts', '*.py')))
    return [n for n in names if not n.startswith('_')]


def abspath(p):
    return p if os.path.isabs(p) else os.path.join(ROOT, p)


# ------------------------------------------------------------ Blender stage
def stage_sheets(argv):
    """Inside Blender: tile the renders into contact sheets + shade stats."""
    sys.path.insert(0, ROOT)
    sys.path.insert(0, os.path.join(ROOT, 'tools'))
    import contact
    from levi import regions, spec

    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--poses', default='')
    a = ap.parse_args(argv)
    out = a.out
    cel, clay, poses_dir = (os.path.join(out, d) for d in ('cel', 'clay', 'poses'))

    def ld(path):
        return contact.load(path)

    sheets = []
    imgs = [ld(os.path.join(ROOT, 'ref', f'{v}.png')) for v in SHEET_VIEWS] + \
           [ld(os.path.join(cel, f'{v}.png')) for v in SHEET_VIEWS]
    sheets.append(('01_ortho_sbs.png', contact.tile(
        imgs, 3, [f'sheet {v}' for v in SHEET_VIEWS] + [f'render {v}' for v in SHEET_VIEWS],
        crop=True, title='top: three-view sheet  bottom: cel render (ortho, aligned)')))
    sheets.append(('02_angles_cel.png', contact.tile(
        [ld(os.path.join(cel, f'{v}.png')) for v in REVIEW_VIEWS], 3, list(REVIEW_VIEWS),
        crop=True, title='cel render, review angles (no reference exists)')))
    views = SHEET_VIEWS + REVIEW_VIEWS
    sheets.append(('03_clay.png', contact.tile(
        [ld(os.path.join(clay, f'{v}.png')) for v in views], 3, [f'clay {v}' for v in views],
        crop=True, title='clay: grey diffuse, no outlines (form, faceting, intersections)')))
    pose_names = [p for p in a.poses.split(',') if p and
                  all(os.path.isfile(os.path.join(poses_dir, p, f'{v}.png')) for v in POSE_VIEWS)]
    if pose_names:
        imgs, labels = [], []
        for p in pose_names:
            for v in POSE_VIEWS:
                imgs.append(ld(os.path.join(poses_dir, p, f'{v}.png')))
                labels.append(f'{p} {v}')
        sheets.append(('04_poses.png', contact.tile(
            imgs, 4, labels, scale=0.5, crop=True,
            title='rigged model posed with tools/rig_pose.py POSES (cel)')))
    for name, img in sheets:
        contact.save(os.path.join(out, name), img)
        print('SHEET', os.path.join(out, name), f'{img.shape[1]}x{img.shape[0]}')
    tt = os.path.join(cel, 'turntable.png')
    if os.path.isfile(tt):
        shutil.copyfile(tt, os.path.join(out, 'turntable.png'))
        print('SHEET', os.path.join(out, 'turntable.png'))

    # Shade share per region at every angle (render palette), vs the sheet's.
    lines = ['# share of each region painted in its shade tone (cel render; sheet in brackets)',
             'view            ' + ' '.join(f'{r:>15s}' for r in regions.REGION_NAMES)]
    for v in views:
        lp = os.path.join(cel, f'{v}_regions.png')
        if not os.path.isfile(lp):
            continue
        r = ld(os.path.join(cel, f'{v}.png'))
        rgb = contact.over_white(r)
        lr = ld(lp)
        lbl = regions.decode(lr[..., :3], lr[..., 3])
        ref = ref_lbl = None
        if v in SHEET_VIEWS:
            ref = ld(os.path.join(ROOT, 'ref', f'{v}.png'))[..., :3]
            ref_lbl = regions.decode(ld(os.path.join(ROOT, 'ref', f'{v}_regions.png'))[..., :3])
        cells = []
        for name in regions.REGION_NAMES:
            s, n = regions.shade_share(rgb, lbl, name)
            cell = '-' if n == 0 else f'{s:.2f}'
            if ref is not None:
                sr, nr = regions.shade_share(ref, ref_lbl, name, spec.SHEET_PALETTE)
                cell += f' [{sr:.2f}]' if nr else ' [-]'
            cells.append(f'{cell:>15s}')
        lines.append(f'{v:15s} ' + ' '.join(cells))
    with open(os.path.join(out, 'shade_stats.txt'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
    print('\n'.join(lines))

    lines, marked = shade_island_stats(cel, views)
    with open(os.path.join(out, 'shade_islands.txt'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
    print('\n'.join(lines))
    if marked:
        img = contact.tile([m for _v, m in marked], 3, [f'islands {v}' for v, _m in marked], crop=True,
                           title='small shade islands (red) in the cel render: specks and slivers')
        contact.save(os.path.join(out, '05_islands.png'), img)
        print('SHEET', os.path.join(out, '05_islands.png'), f'{img.shape[1]}x{img.shape[0]}')


def shade_island_stats(cel, views):
    """Small shade islands per view and region (regions.shade_islands) in the
    cel renders under `cel`. Returns (report lines, [(view, RGBA image with
    the islands painted red)])."""
    import contact
    import numpy as np
    from levi import regions
    lines = [f'# small shade islands per region: count / area px '
             f'({regions.SHADE_ISLAND_MIN_PX}-{regions.SHADE_ISLAND_SMALL_PX} px shade patches '
             f'cut off from the broad shade; fewer = cleaner cel shading)',
             'view            ' + ' '.join(f'{r:>11s}' for r in regions.REGION_NAMES) + '       total']
    marked = []
    for v in views:
        lp = os.path.join(cel, f'{v}_regions.png')
        if not os.path.isfile(lp):
            continue
        r = contact.load(os.path.join(cel, f'{v}.png'))
        rgb = contact.over_white(r)
        lr = contact.load(lp)
        lbl = regions.decode(lr[..., :3], lr[..., 3])
        cells, tot_n, tot_a = [], 0, 0
        allm = np.zeros(lbl.shape, dtype=bool)
        for name in regions.REGION_NAMES:
            n, area, m = regions.shade_islands(rgb, lbl, name)
            tot_n, tot_a = tot_n + n, tot_a + area
            allm |= m
            cells.append(f'{f"{n}/{area}":>11s}')
        lines.append(f'{v:15s} ' + ' '.join(cells) + f' {f"{tot_n}/{tot_a}":>11s}')
        img = r.copy()
        img[allm] = (1.0, 0.0, 0.0, 1.0)
        marked.append((v, img))
    return lines, marked


# --------------------------------------------------------------- Codex
SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'required': ['summary', 'scores', 'findings'],
    'properties': {
        'summary': {'type': 'string'},
        'scores': {'type': 'object', 'additionalProperties': False,
                   'required': list(CATEGORIES),
                   'properties': {c: {'type': 'integer'} for c in CATEGORIES}},
        'findings': {'type': 'array', 'items': {
            'type': 'object', 'additionalProperties': False,
            'required': ['part', 'priority', 'category', 'view', 'location', 'issue', 'fix'],
            'properties': {
                'part': {'type': 'string'},
                'priority': {'type': 'integer'},
                'category': {'type': 'string', 'enum': list(CATEGORIES)},
                'view': {'type': 'string'},
                'location': {'type': 'string'},
                'issue': {'type': 'string'},
                'fix': {'type': 'string'},
            }}},
    },
}

PROMPT = """You are a senior character artist and technical rigger reviewing a procedural anime
character model, "Levi". It is built from scratch with Blender Python (bpy/bmesh, about 30,000
faces) and cel-shaded (two-tone toon ramp with coloured inverted-hull outlines). The target is the
hand-painted three-view sheet ref/levi_threeview.png (front / side / back). The repo is your
working directory (read-only): CLAUDE.md explains the pipeline, and each part is built by
levi/parts/<part>.py. Read code only when it makes a fix concrete; the images are the main input.

Goal, in strict priority order:
  1. NATURALNESS IN 3D. The model must read as a believable, well-formed character from ANY angle,
     not only from the three calibrated orthographic views. Look for: flat or cardboard-like
     shapes seen at 3/4, faceting or triangular shading breaks, pinched or collapsing volumes,
     intersections and poke-through, floating or disconnected pieces, implausible thickness,
     hard-edged or patchy cel shadows that would never appear in the sheet's style, colour
     gradients that turn into hard bands, silhouettes that only work head-on.
  2. ANIMATION READINESS. It is rigged for MMD (PMX export). From the pose sheet and the rest
     geometry, judge: deformation at shoulders, elbows, wrists, hips, knees; cloth, hair and skirt
     following the body; candy-wrapper twists; stretching; interpenetration in poses; pieces that
     will clip or tear when animated; geometry that lacks the edge loops to bend.
  3. FIDELITY to the three-view sheet: proportions, silhouette, shapes, colours and details,
     only where they do not conflict with 1 and 2.

Images (in the order attached):
{images}

Metrics (silhouette IoU and per-region scores vs the sheet, from tools/compare.py; shade share
per region at every angle):
```
{metrics}
```

Parts (use exactly these names for "part"): {parts}; plus "lookdev" (lighting, ramp, palette,
outlines, anything global to the shading), "rig" (bones, weights, deformation) and "global".
{focus}
Return JSON matching the schema:
- summary: 3-6 sentences, overall state and the most important next steps.
- scores: 1-10 per category (10 = production-ready).
- findings: at most {max_findings}, most important first. priority 1 = clearly visible or breaks
  animation, fix this round; 2 = noticeable; 3 = polish. category is naturalness / animation /
  fidelity. view names the image tile (e.g. "q34_front_left", "clay high", "walk front").
  location is where on the model (be specific: "left sleeve cuff, inner side"). issue says what is
  wrong and why it matters. fix is a concrete, actionable change for the part's build code
  (shape, loop count, normals, weights, offsets in cm), not a generic suggestion.
Do not report things that are fine. Do not pad. Be specific and visual.
"""

IMAGE_DESC = {
    '01_ortho_sbs.png': 'three-view sheet (top row) vs cel render (bottom row), front / side / back, '
                        'orthographic and pixel-aligned',
    '02_angles_cel.png': 'cel render from angles the sheet does not show: 3/4 front-left, 3/4 back-right, '
                         'high front (30 deg down), orthographic, key light from the viewer\'s upper left',
    '03_clay.png': 'clay render (grey diffuse, no outlines): all six angles, for form and faceting',
    '04_poses.png': 'rigged model in test poses (front + 3/4 each), cel',
    '05_islands.png': 'the cel renders of the sheet and review views with every small shade island '
                      '(4-80 px shade patch cut off from the broad shade) painted red: specks and '
                      'slivers that make pale surfaces look chipped (counts in shade_islands below)',
    'turntable.png': 'turntable: evenly spaced angles around the model, cel',
}


def build_prompt(sheets, metrics, focus, max_findings):
    images = '\n'.join(f'  {i + 1}. {os.path.basename(s)}: {IMAGE_DESC.get(os.path.basename(s), "")}'
                       for i, s in enumerate(sheets))
    focus_txt = ''
    if focus:
        focus_txt = (f'\nFOCUS: this review is for the part(s) "{focus}". Report findings for it '
                     f'first and in the most detail (all priorities); for other parts report only '
                     f'priority-1 problems that interact with it.\n')
    return PROMPT.format(images=images, metrics=metrics.strip() or '(none)', parts=', '.join(parts()),
                         focus=focus_txt, max_findings=max_findings)


def run_codex(models, prompt_path, sheets, out, codex, timeout):
    """Run one `codex exec` child per model concurrently (prompt on stdin from
    prompt_path); wait for all of them. Returns {model: exit code | 'timeout' | error}."""
    schema_path = os.path.join(out, 'review_schema.json')
    with open(schema_path, 'w', encoding='utf-8') as f:
        json.dump(SCHEMA, f, indent=1)
    procs, results = {}, {}
    for m in models:
        last = os.path.join(out, f'{m}.json')
        if os.path.exists(last):
            os.remove(last)
        cmd = [codex, 'exec', '-', '--skip-git-repo-check', '--ephemeral', '-m', m,
               '-s', 'read-only', '-C', ROOT, '--color', 'never',
               '--output-schema', schema_path, '-o', last]
        if os.name == 'nt':
            # The default (elevated) Windows sandbox needs a UAC-approved helper
            # and cannot start from a background run; unelevated read-only works.
            cmd += ['-c', 'windows.sandbox="unelevated"']
        for s in sheets:
            cmd += ['-i', s]
        log = open(os.path.join(out, f'{m}.log'), 'w', encoding='utf-8')
        try:
            with open(prompt_path, 'rb') as stdin:
                p = subprocess.Popen(cmd, stdin=stdin, stdout=log, stderr=subprocess.STDOUT, cwd=ROOT)
        except OSError as e:
            log.close()
            results[m] = f'error: {e}'
            print('CODEX failed to start', m, e, flush=True)
            continue
        procs[m] = (p, log, time.time())
        print('CODEX started', m, 'pid', p.pid, flush=True)
    deadline = time.time() + timeout
    for m, (p, log, t0) in procs.items():
        try:
            rc = p.wait(timeout=max(1.0, deadline - time.time()))
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait()
            rc = 'timeout'
        log.close()
        results[m] = rc
        print(f'CODEX done {m} rc={rc} after {time.time() - t0:.0f}s', flush=True)
    return results


def load_reply(path):
    try:
        with open(path, encoding='utf-8') as f:
            txt = f.read()
    except OSError:
        return None, ''
    try:
        return json.loads(txt), txt
    except ValueError:
        # tolerate a fenced or prefixed JSON object
        i, j = txt.find('{'), txt.rfind('}')
        try:
            return json.loads(txt[i:j + 1]), txt
        except ValueError:
            return None, txt


def fmt_finding(f, tag=''):
    return (f'- **P{f.get("priority", "?")}** [{f.get("category", "?")}]{tag} '
            f'*{f.get("view", "")}* - {f.get("location", "")}: {f.get("issue", "")}\n'
            f'  - Fix: {f.get("fix", "")}')


def finding_key(f):
    """Sort findings by priority, then category order (naturalness first)."""
    cat = f.get('category')
    return (f.get('priority', 9), CATEGORIES.index(cat) if cat in CATEGORIES else 9)


def write_model_md(m, data, raw, rc, out):
    lines = [f'# Codex review: {m}', '']
    if data is None:
        lines += [f'No structured reply (exit {rc}). Raw output:', '', '```', raw.strip(), '```']
    else:
        sc = data.get('scores', {})
        lines += [data.get('summary', ''), '',
                  'Scores: ' + ', '.join(f'{c} {sc.get(c, "?")}/10' for c in CATEGORIES), '']
        by_part = {}
        for f in data.get('findings', []):
            by_part.setdefault(f.get('part', 'global'), []).append(f)
        for part in sorted(by_part, key=lambda p: (min(map(finding_key, by_part[p])), p)):
            lines += [f'## {part}', '']
            for f in sorted(by_part[part], key=finding_key):
                lines.append(fmt_finding(f))
            lines.append('')
    path = os.path.join(out, f'{m}.md')
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(lines) + '\n')
    return path


def write_summary(replies, out, focus, delta=''):
    """Merge every model's findings by part (priority, then category order);
    `delta` (metrics_delta() markdown) is appended."""
    lines = ['# Review summary', '']
    if focus:
        lines += [f'Focus: {focus}', '']
    lines += ['| model | naturalness | animation | fidelity | findings |', '|---|---|---|---|---|']
    for m, (data, _raw, rc) in replies.items():
        if data:
            sc = data.get('scores', {})
            lines.append(f'| {m} | ' + ' | '.join(str(sc.get(c, '?')) for c in CATEGORIES)
                         + f' | {len(data.get("findings", []))} |')
        else:
            lines.append(f'| {m} | - | - | - | no reply (exit {rc}) |')
    lines.append('')
    for m, (data, _raw, _rc) in replies.items():
        if data:
            lines += [f'**{m}:** {data.get("summary", "")}', '']
    merged = {}
    for m, (data, _raw, _rc) in replies.items():
        for f in (data or {}).get('findings', []):
            merged.setdefault(f.get('part', 'global'), []).append((m, f))

    def key(item):
        return finding_key(item[1])

    p1 = sorted((x for xs in merged.values() for x in xs if x[1].get('priority') == 1), key=key)
    if p1:
        lines += ['## Priority 1 across all parts', '']
        lines += [f'- **{f.get("part")}** ({m}) [{f.get("category")}] {f.get("location")}: {f.get("issue")}'
                  for m, f in p1]
        lines.append('')
    order = sorted(merged, key=lambda p: (min(key(x) for x in merged[p]), p))
    lines += ['## By part', '']
    for part in order:
        lines += [f'### {part}', '']
        lines += [fmt_finding(f, f' ({m})') for m, f in sorted(merged[part], key=key)]
        lines.append('')
    if delta:
        lines += [delta]
    path = os.path.join(out, 'summary.md')
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(lines) + '\n')
    return path


# ------------------------------------------------------- baseline deltas
def parse_metrics(out):
    """metrics.txt + shade_islands.txt of a review dir ->
    {(view, region or '*'): {field: value}} (missing files give {})."""
    res = {}
    try:
        with open(os.path.join(out, 'metrics.txt'), encoding='utf-8') as f:
            for line in f:
                t = line.split()
                if t[:1] == ['IOU'] and len(t) >= 3:
                    res.setdefault((t[1], '*'), {})['iou'] = float(t[2])
                elif t[:1] == ['REGION'] and len(t) >= 3:
                    d = res.setdefault((t[1], t[2]), {})
                    # ... shade ref <s> ren <s> ...: the render's share is 4 tokens on
                    pairs = [(w, t[i + 1]) for i, w in enumerate(t[3:-1], 3)
                             if w in ('iou', 'tol', 'dE', 'dEi')]
                    if 'shade' in t and t.index('shade') + 4 < len(t):
                        pairs.append(('shade', t[t.index('shade') + 4]))
                    for w, v in pairs:
                        try:
                            d[w] = float(v)
                        except ValueError:
                            pass
    except OSError:
        pass
    try:
        with open(os.path.join(out, 'shade_islands.txt'), encoding='utf-8') as f:
            rows = [l.split() for l in f if l.strip() and not l.startswith('#')]
    except OSError:
        rows = []
    head = rows[0][1:] if rows else []
    for r in rows[1:]:
        for name, cell in zip(head, r[1:]):
            try:
                n, area = map(float, cell.split('/'))
            except ValueError:
                continue
            key = (r[0], '*' if name == 'total' else name)
            res.setdefault(key, {}).update({'islands': n, 'island_px': area})
    return res


DELTA_FIELDS = ('iou', 'tol', 'dE', 'dEi', 'shade', 'islands', 'island_px')


def metrics_delta(base_dir, out):
    """Markdown table: current metrics vs a baseline review dir, rows with any change."""
    old, new = parse_metrics(base_dir), parse_metrics(out)
    if not old or not new:
        return ''
    try:
        shown = os.path.relpath(base_dir, ROOT)
    except ValueError:   # another drive (Windows)
        shown = base_dir
    lines = [f'## Metrics vs baseline `{shown}`', '',
             'Per view and region, `new (delta)`; `*` = whole view (silhouette IoU, island total). '
             'iou/tol up is better; dE/dEi (interior colour error), islands and island_px down is better; '
             'shade is the render\'s shade share (compare with the sheet in shade_stats.txt).', '',
             '| view | region | ' + ' | '.join(DELTA_FIELDS) + ' |',
             '|---|---|' + '---|' * len(DELTA_FIELDS)]
    for key in sorted(set(old) | set(new), key=lambda k: (k[0], k[1] != '*', k[1])):
        o, n = old.get(key, {}), new.get(key, {})
        cells, changed = [], False
        for fld in DELTA_FIELDS:
            fmt = '%.0f' if fld.startswith('island') else ('%.1f' if fld.startswith('dE') else '%.3f')
            if fld not in n:
                if fld in o:
                    changed = True
                    cells.append(f'gone (was {fmt % o[fld]})')
                else:
                    cells.append('')
                continue
            if fld in o:
                d = n[fld] - o[fld]
                if math.isnan(d):
                    changed |= math.isnan(n[fld]) != math.isnan(o[fld])
                    cells.append(f'{fmt % n[fld]} (was {fmt % o[fld]})')
                else:
                    changed |= abs(d) > 1e-9
                    cells.append(f'{fmt % n[fld]} ({"+" if d >= 0 else ""}{fmt % d})')
            else:
                changed = True
                cells.append(fmt % n[fld])
        if changed:
            lines.append(f'| {key[0]} | {key[1]} | ' + ' | '.join(cells) + ' |')
    return '\n'.join(lines) + '\n'


# ------------------------------------------------------------ orchestration
def blender(args, exe, log_path):
    """Run Blender in the background; returns stdout text, raises on failure."""
    r = subprocess.run([exe, "-b", "--python-exit-code", "1"] + args, cwd=ROOT,
                       capture_output=True, text=True,
                       encoding='utf-8', errors='replace')
    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(f'$ blender -b {" ".join(args)}\n{r.stdout}\n{r.stderr}\n')
    if r.returncode != 0:
        raise SystemExit(f'blender failed ({r.returncode}): {" ".join(args)}; see {log_path}')
    return r.stdout


def main():
    if '--stage' in sys.argv:   # inside Blender: blender -b -P tools/review.py -- --stage sheets ...
        argv = sys.argv[sys.argv.index('--') + 1:]
        argv.remove('--stage')
        stage = argv.pop(0)
        if stage != 'sheets':
            raise SystemExit(f'unknown stage {stage}')
        return stage_sheets(argv)

    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--blend', default='out/levi.blend')
    ap.add_argument('--rig', default='out/levi_rig.blend',
                    help='rigged .blend for the pose sheet (skipped if missing; "" to skip)')
    ap.add_argument('--build', action='store_true', help='build --blend (and --rig) first')
    ap.add_argument('--out', default='out/review')
    ap.add_argument('--focus', default='', help='part name(s) to review in most detail')
    ap.add_argument('--turntable', type=int, default=0, metavar='N')
    ap.add_argument('--poses', default=DEFAULT_POSES)
    ap.add_argument('--models', default=DEFAULT_MODELS)
    ap.add_argument('--no-codex', action='store_true', help='renders and sheets only')
    ap.add_argument('--baseline', default='',
                    help='an earlier review dir: write metrics_delta.md (and a section in summary.md) '
                         'with the metrics.txt / shade_islands.txt changes against it')
    ap.add_argument('--no-render', action='store_true', help='reuse the renders already in --out')
    ap.add_argument('--timeout', type=float, default=900, help='seconds per Codex run (they run concurrently)')
    ap.add_argument('--max-findings', type=int, default=25)
    ap.add_argument('--blender', default=DEFAULT_BLENDER)
    ap.add_argument('--codex', default=DEFAULT_CODEX)
    a = ap.parse_args()

    if a.focus:
        bad = [p for p in a.focus.split(',') if p not in parts() + ['lookdev', 'rig', 'global']]
        if bad:
            ap.error(f'--focus: unknown part(s) {bad}; choose from {parts()}, lookdev, rig, global')
    out = abspath(a.out)
    os.makedirs(out, exist_ok=True)
    log = os.path.join(out, 'blender.log')
    blend = abspath(a.blend)
    rig_blend = abspath(a.rig) if a.rig else ''

    if a.build:
        open(log, 'w').close()
        blender(['-P', 'build.py', '--', '--out', blend], a.blender, log)
        if rig_blend:
            blender(['-P', 'build.py', '--', '--rig', '--out', rig_blend], a.blender, log)
    if not os.path.isfile(blend):
        ap.error(f'{blend} not found (build it, or pass --build)')
    poses = a.poses if rig_blend and os.path.isfile(rig_blend) else ''

    if not a.no_render:
        if not a.build:
            open(log, 'w').close()
        for d in ('cel', 'clay', 'poses', 'cmp'):
            shutil.rmtree(os.path.join(out, d), ignore_errors=True)
        print('RENDER cel', flush=True)
        cmd = ['-P', 'render.py', '--', '--out', os.path.join(out, 'cel'), '--views', 'review']
        if a.turntable:
            cmd += ['--turntable', str(a.turntable)]
        blender([blend] + cmd, a.blender, log)
        print('RENDER clay', flush=True)
        blender([blend, '-P', 'render.py', '--', '--out', os.path.join(out, 'clay'),
                 '--views', 'review', '--clay'], a.blender, log)
        if poses:
            print('RENDER poses', poses, flush=True)
            blender([rig_blend, '-P', 'render.py', '--', '--out', os.path.join(out, 'poses'),
                     '--views', ','.join(POSE_VIEWS), '--pose', poses], a.blender, log)
        print('COMPARE', flush=True)
        txt = blender(['--factory-startup', '-P', 'tools/compare.py', '--',
                       '--render', os.path.join(out, 'cel'), '--out', os.path.join(out, 'cmp')],
                      a.blender, log)
        with open(os.path.join(out, 'metrics.txt'), 'w', encoding='utf-8') as f:
            f.write(''.join(l + '\n' for l in txt.splitlines() if l.startswith(('IOU', 'REGION'))))
    print('SHEETS', flush=True)
    names = ['01_ortho_sbs.png', '02_angles_cel.png', '03_clay.png', '04_poses.png', '05_islands.png',
             'turntable.png']
    for n in names + ['shade_stats.txt', 'shade_islands.txt', 'metrics_delta.md']:
        # never send a stale sheet from an earlier run
        if os.path.isfile(os.path.join(out, n)):
            os.remove(os.path.join(out, n))
    txt = blender(['--factory-startup', '-P', os.path.join('tools', 'review.py'), '--',
                   '--stage', 'sheets', '--out', out, '--poses', poses], a.blender, log)
    print(''.join(l + '\n' for l in txt.splitlines() if l.startswith('SHEET')), end='')

    sheets = [os.path.join(out, n) for n in names if os.path.isfile(os.path.join(out, n))]
    if not a.turntable:
        sheets = [s for s in sheets if not s.endswith('turntable.png')]
    metrics = ''
    for n in ('metrics.txt', 'shade_stats.txt', 'shade_islands.txt'):
        p = os.path.join(out, n)
        if os.path.isfile(p):
            with open(p, encoding='utf-8') as f:
                metrics += f.read() + '\n'
    delta = ''
    if a.baseline:
        delta = metrics_delta(abspath(a.baseline), out)
        if delta:
            with open(os.path.join(out, 'metrics_delta.md'), 'w', encoding='utf-8') as f:
                f.write(delta)
            print('DELTA', os.path.join(out, 'metrics_delta.md'))
        else:
            print('DELTA skipped: no metrics in', a.baseline)
    prompt = build_prompt(sheets, metrics, a.focus, a.max_findings)
    prompt_path = os.path.join(out, 'prompt.md')
    with open(prompt_path, 'w', encoding='utf-8') as f:
        f.write(prompt)
    if a.no_codex:
        print('PROMPT', prompt_path)
        return
    if not os.path.isfile(a.codex):
        raise SystemExit(f'codex not found at {a.codex} (set LEVI_CODEX or --codex)')
    models = [m for m in a.models.split(',') if m]
    rcs = run_codex(models, prompt_path, sheets, out, a.codex, a.timeout)
    replies = {}
    for m in models:
        data, raw = load_reply(os.path.join(out, f'{m}.json'))
        replies[m] = (data, raw, rcs[m])
        print('REVIEW', write_model_md(m, data, raw, rcs[m], out))
    print('SUMMARY', write_summary(replies, out, a.focus, delta))
    if not any(d for d, _, _ in replies.values()):
        raise SystemExit('no model returned a review; see the <model>.log files')


if __name__ == '__main__':
    main()
