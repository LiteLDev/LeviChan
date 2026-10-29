"""Demo and visual test of the shared hair kernel (levi/parts/_hair_kernel.py).

Builds sample strands with the kernel, each validated (a failing strand stops
the build), renders close-ups of every strand in cel / clay / wire, whole and
zoomed on its tip or curl, and tiles them into sheets.

    "$B" -b --factory-startup -P tools/hair_kernel_demo.py -- --out out/hair_kernel_demo   # build (CPU)
    "$B" -b out/hair_kernel_demo/demo.blend -P tools/hair_kernel_demo.py -- --render out/hair_kernel_demo
                                                                                            # renders (GPU)
    python3 tools/hair_kernel_demo.py --sheet out/hair_kernel_demo                          # sheets (PIL)

Strands (side by side along +X, hanging down, outer face toward -Y = the front
camera): a straight lock, a sideways S-wave lock, a C end-curl (flat blade in the
bend plane, 风堇's end curls), a 270 deg spiral that tightens as it thins (the
broad face toward the centre), a split tip (0.6 / 0.4), an end curl with two
sub-tips, a pitched ringlet, and two shingled locks (the upper resting on the
lower with strand_on()). The build writes demo.blend, metrics.txt (validate()
per strand) and rings.npz (ring polygons for the section sheet).
"""
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

try:
    import bpy  # noqa: F401
    IN_BLENDER = True
except ImportError:
    IN_BLENDER = False

SPACING = 0.11      # m between strands along X
TOP_Z = 0.32        # root height


def specs():
    """(name, kwargs for hk.strand / hk.strand_on) of the demo strands, rooted at x = 0."""
    import numpy as np
    from levi.parts import _hair_kernel as hk
    face = (0.0, -1.0, 0.0)
    grad = (0.55, 0.95)
    z = TOP_Z
    wave = [(0.010 * math.sin(2 * math.pi * t / 0.11), -0.004 * math.sin(math.pi * t / 0.25), z - t)
            for t in np.linspace(0.0, 0.26, 14)]
    out = [
        ('straight', dict(points=[(0, 0, z), (0.004, -0.006, z - 0.12), (0.0, 0.0, z - 0.26)],
                          width=0.020, aspect=3.0, facing=face, grad=grad)),
        ('s_wave', dict(points=wave, width=0.018, aspect=3.0, facing=face, grad=grad)),
        ('c_curl', dict(points=[(0, 0, z), (0.004, -0.004, z - 0.09), (0.0, 0.0, z - 0.16)],
                        width=0.016, aspect=4.5, facing=face, grad=grad,
                        curl=hk.curl(turn=240, toward='+B', face='plane', radius=0.019, core=0.7))),
        ('spiral_270', dict(points=[(0, 0, z), (0.0, -0.004, z - 0.09), (0.0, 0.0, z - 0.15)],
                            width=0.018, aspect=4.5, facing=face, grad=grad,
                            curl=hk.curl(turn=270, toward='+B', face='centre', radius=0.026, core=0.5,
                                         exp=0.8))),
        ('split_tip', dict(points=[(0, 0, z), (0.003, -0.006, z - 0.13), (0.0, 0.0, z - 0.26)],
                           width=0.024, aspect=3.5, facing=face, grad=grad,
                           split=hk.split(at=0.72, shares=(0.6, 0.4), diverge=7.0, lengths=(1.0, 0.8)))),
        ('curl_subtips', dict(points=[(0, 0, z), (0.004, -0.004, z - 0.09), (0.0, 0.0, z - 0.15)],
                              width=0.018, aspect=4.5, facing=face, grad=grad,
                              curl=hk.curl(turn=250, toward='+B', face='plane', radius=0.022, core=0.7),
                              split=hk.split(at=0.86, shares=(0.55, 0.45), diverge=8.0, lengths=(1.0, 0.75)))),
        ('ringlet', dict(points=[(0, 0, z), (0.0, -0.004, z - 0.08), (0.0, 0.0, z - 0.13)],
                         width=0.018, aspect=4.0, facing=face, grad=grad,
                         curl=hk.curl(turn=300, toward='in', face='centre', radius=0.022, core=0.6,
                                      pitch=(0.03, (0.0, 0.0, -1.0))))),
    ]
    return out


def build_demo(outdir):
    import bmesh
    import numpy as np
    from levi import common
    from levi.parts import _hair_kernel as hk
    from levi.builder import reset_scene
    reset_scene()
    col = common.part_collection('hair_kernel_demo')
    mat = common.toon_material('hair', gradient='hair_tip')
    lines, rings_dump, meta = [], {}, {}

    def make(name, st, x):
        bm = bmesh.new()
        hk.emit(bm, st)
        bmesh.ops.translate(bm, verts=bm.verts, vec=(x, 0.0, 0.0))
        obj = common.new_object(col, name, bm, [mat])
        common.shade_smooth(obj, 50.0)
        common.add_outline(obj)
        return obj

    def report(name, st, x):
        v = hk.validate(st)       # raises on any violation
        lines.append(f'{name:14s} len {1000 * st.length:6.1f} mm  n {st.n:2d}  rings {v["rings"]:3d}  '
                     f'faces {v["faces"]:5d}  max turn {v["max_turn"]:4.1f} deg  rho {v["max_rho"]:.2f}  '
                     f'folds {v["folds"]}  twist {v["max_twist"]:4.1f} deg  wratio {v["wratio"][0]:.2f}-'
                     f'{v["wratio"][1]:.2f}  gap {1000 * v["min_gap"]:.1f}-{1000 * v["max_gap"]:.1f} mm'
                     + (f'  overlap {100 * st.meta["overlap"]:.0f}%  lift {1000 * st.meta["lift_max"]:.1f} mm'
                        if 'overlap' in st.meta else ''))
        for tb in st.all_tubes():
            rings_dump[f'{name}|{tb.name}'] = tb.rings + np.array([x, 0.0, 0.0])
            rings_dump[f'{name}|{tb.name}|N'] = tb.N
            rings_dump[f'{name}|{tb.name}|B'] = tb.B
            rings_dump[f'{name}|{tb.name}|arc'] = tb.arc
        lo = np.min([tb.rings.reshape(-1, 3).min(0) for tb in st.all_tubes()], 0) + [x, 0, 0]
        hi = np.max([tb.rings.reshape(-1, 3).max(0) for tb in st.all_tubes()], 0) + [x, 0, 0]
        # the zoom box: the curl / split / tip region (last 30% of the length)
        sel = [tb.rings[tb.arc >= 0.70 * st.length].reshape(-1, 3) for tb in st.all_tubes()]
        sel = np.concatenate([a for a in sel if len(a)] + [st.all_tubes()[-1].apex[None]]) + [x, 0, 0]
        meta[name] = {'lo': lo.tolist(), 'hi': hi.tolist(), 'zlo': sel.min(0).tolist(), 'zhi': sel.max(0).tolist(),
                      'faces': v['faces']}
        return v

    x = 0.0
    total = 0
    for name, kw in specs():
        st = hk.strand(name=name, check=True, **kw)
        report(name, st, x)
        make(name, st, x)
        total += st.face_count()
        x += SPACING
    # two shingled locks: the upper rests its underside on the lower's top
    z = TOP_Z
    face = (0.0, -1.0, 0.0)
    low = hk.strand([(-0.012, 0.0, z), (-0.010, -0.004, z - 0.12), (-0.012, 0.0, z - 0.24)], name='shingle_low',
                    width=0.026, aspect=3.0, facing=face, grad=(0.55, 0.95))
    up = hk.strand_on([low], gap=0.00075, name='shingle_up',
                      points=[(0.006, -0.002, z - 0.02), (0.008, -0.006, z - 0.12), (0.006, -0.002, z - 0.23)],
                      width=0.024, aspect=3.0, facing=face, grad=(0.55, 0.95), root_fade=0.02)
    report('shingle_low', low, x)
    report('shingle_up', up, x)
    make('shingle_low', low, x)
    make('shingle_up', up, x)
    meta['shingle'] = {'lo': (np.minimum(meta['shingle_low']['lo'], meta['shingle_up']['lo'])).tolist(),
                       'hi': (np.maximum(meta['shingle_low']['hi'], meta['shingle_up']['hi'])).tolist(),
                       'zlo': meta['shingle_up']['zlo'], 'zhi': meta['shingle_up']['zhi']}
    total += low.face_count() + up.face_count()
    # mirrored copy check: faces still face out (signed volume > 0)
    mir = hk.mirrored(low, name='shingle_low_M')
    bm = bmesh.new()
    hk.emit(bm, mir)
    vol = bm.calc_volume(signed=True)
    bm.free()
    lines.append(f'mirrored shingle_low signed volume {vol * 1e6:.2f} cm3 (> 0: faces out)')
    # every object: one island per strand, closed, outward
    for obj in col.objects:
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        nonman = sum(1 for e in bm.edges if not e.is_manifold)
        vol = bm.calc_volume(signed=True)
        seen, isl = set(), 0
        for v0 in bm.verts:
            if v0.index in seen:
                continue
            isl += 1
            stack = [v0]
            seen.add(v0.index)
            while stack:
                v = stack.pop()
                for e in v.link_edges:
                    o = e.other_vert(v)
                    if o.index not in seen:
                        seen.add(o.index)
                        stack.append(o)
        bm.free()
        amin = min(p.area for p in obj.data.polygons)
        lines.append(f'{obj.name:14s} mesh: {len(obj.data.polygons)} faces, {isl} island(s), '
                     f'non-manifold edges {nonman}, signed volume {vol * 1e6:.2f} cm3, '
                     f'smallest face {amin * 1e6:.3f} mm2')
    lines.append(f'TOTAL faces {total}')
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, 'metrics.txt'), 'w') as f:
        f.write('\n'.join(lines) + '\n')
    with open(os.path.join(outdir, 'meta.json'), 'w') as f:
        json.dump(meta, f, indent=1)
    np.savez_compressed(os.path.join(outdir, 'rings.npz'), **rings_dump)
    print('\n'.join(lines))
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(outdir, 'demo.blend'), compress=True)
    print('SAVED', os.path.join(outdir, 'demo.blend'))


# ---------------------------------------------------------------- renders
VIEWS = {   # (azimuth from the front camera toward +X, elevation) deg
    'front': (0.0, 0.0),
    'side': (90.0, 0.0),
    'q34': (-40.0, 18.0),
    'low': (25.0, -35.0),
}


def render_demo(outdir):
    import bmesh  # noqa: F401
    from mathutils import Vector
    import render as R
    from levi import toon
    rdir = os.path.join(outdir, 'render')
    os.makedirs(rdir, exist_ok=True)
    meta = json.load(open(os.path.join(outdir, 'meta.json')))
    sc = bpy.context.scene
    toon.sync_materials()
    sc_, cam, sun = R.setup_scene(1)      # transparent film: the sheets put it on white
    objs = [o for o in bpy.data.objects if o.type == 'MESH']
    groups = {k: [k] for k in meta if not k.startswith('shingle')}
    groups['shingle'] = ['shingle_low', 'shingle_up']

    def shots():
        for g, names in groups.items():
            m = meta[g]
            for zoom in ('full', 'zoom'):
                lo, hi = (m['lo'], m['hi']) if zoom == 'full' else (m['zlo'], m['zhi'])
                c = Vector([(a + b) / 2 for a, b in zip(lo, hi)])
                ext = max(b - a for a, b in zip(lo, hi))
                for view, (az, el) in VIEWS.items():
                    if zoom == 'zoom' and view == 'low':
                        continue
                    yield g, names, zoom, view, az, el, c, ext

    def place(az, el, c, ext):
        a, e = math.radians(az), math.radians(el)
        d = Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e)))
        cam.location = c + 2.0 * d
        cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
        cam.data.type = 'ORTHO'
        cam.data.ortho_scale = ext * 1.15 + 0.01
        cam.data.clip_start, cam.data.clip_end = 0.05, 10.0
        cam.data.shift_x = cam.data.shift_y = 0.0
        sc.render.resolution_x = sc.render.resolution_y = 700

    def show_only(names):
        for o in objs:
            o.hide_render = o.name not in names

    # cel
    for g, names, zoom, view, az, el, c, ext in shots():
        show_only(names)
        place(az, el, c, ext)
        R.place_sun(sun, cam)
        sc.render.filepath = os.path.join(rdir, f'{g}_{zoom}_{view}_cel.png')
        bpy.ops.render.render(write_still=True)
    # clay (render.py's clay look: grey by N.L, no outlines)
    R.set_clay_materials()
    for g, names, zoom, view, az, el, c, ext in shots():
        show_only(names)
        place(az, el, c, ext)
        R.place_sun(sun, cam, *R.CLAY_SUN)
        sc.render.filepath = os.path.join(rdir, f'{g}_{zoom}_{view}_clay.png')
        bpy.ops.render.render(write_still=True)
    # wire: workbench studio + a black wireframe copy
    sc.render.engine = 'BLENDER_WORKBENCH'
    sh = sc.display.shading
    sh.light = 'STUDIO'
    sh.color_type = 'OBJECT'
    sh.show_backface_culling = False
    sh.show_cavity = False
    wires = {}
    wmat = bpy.data.materials.new('wire_black')
    for o in objs:
        o.color = (0.86, 0.86, 0.86, 1)
        w = o.copy()
        w.data = o.data
        for md in list(w.modifiers):
            w.modifiers.remove(md)
        wm = w.modifiers.new('wire', 'WIREFRAME')
        wm.thickness = 0.00022
        wm.use_even_offset = True
        wm.use_replace = True
        w.color = (0.03, 0.03, 0.03, 1)
        w.data.materials.append(wmat) if not w.data.materials else None
        sc.collection.objects.link(w)
        wires[o.name] = w
    for g, names, zoom, view, az, el, c, ext in shots():
        show_only(names)
        for n_, w in wires.items():
            w.hide_render = n_ not in names
        place(az, el, c, ext)
        sc.render.filepath = os.path.join(rdir, f'{g}_{zoom}_{view}_wire.png')
        bpy.ops.render.render(write_still=True)
    print('RENDERED', rdir)


# ---------------------------------------------------------------- sheets (PIL, outside Blender)
def sheets(outdir):
    import numpy as np
    from PIL import Image, ImageDraw
    rdir = os.path.join(outdir, 'render')
    meta = json.load(open(os.path.join(outdir, 'meta.json')))
    groups = [k for k in meta if not k.startswith('shingle_')]

    def tile(paths, labels, h=330):
        ims = []
        for p, lab in zip(paths, labels):
            im = Image.open(p).convert('RGBA')
            bg = Image.new('RGBA', im.size, (255, 255, 255, 255))
            im = Image.alpha_composite(bg, im).convert('RGB')
            im = im.resize((round(im.width * h / im.height), h), Image.LANCZOS)
            d = ImageDraw.Draw(im)
            d.rectangle((0, 0, 7 + 6 * len(lab), 14), fill=(255, 255, 255))
            d.text((3, 2), lab, fill=(190, 0, 0))
            ims.append(im)
        W = sum(i.width for i in ims) + 4 * (len(ims) - 1)
        S = Image.new('RGB', (W, h), 'white')
        xx = 0
        for i in ims:
            S.paste(i, (xx, 0))
            xx += i.width + 4
        return S

    def stack(rows, path):
        W = max(r.width for r in rows)
        H = sum(r.height for r in rows) + 4 * (len(rows) - 1)
        S = Image.new('RGB', (W, H), 'white')
        y = 0
        for r in rows:
            S.paste(r, (0, y))
            y += r.height + 4
        S.save(path, quality=88)
        print('SHEET', path, S.size)

    for g in groups:
        rows = []
        for zoom, views in (('full', ('front', 'side', 'q34', 'low')), ('zoom', ('front', 'side', 'q34'))):
            for mode in ('cel', 'clay', 'wire'):
                ps = [os.path.join(rdir, f'{g}_{zoom}_{v}_{mode}.png') for v in views]
                rows.append(tile(ps, [f'{g} {zoom} {v} {mode}' for v in views]))
        stack(rows, os.path.join(outdir, f'sheet_{g}.jpg'))
    # sections: ring polygons in each ring's own (B, N) frame, 1 cm grid, 4 px / mm
    D = np.load(os.path.join(outdir, 'rings.npz'))
    keys = sorted({k.split('|')[0] + '|' + k.split('|')[1] for k in D.files if k.count('|') == 1})
    tiles = []
    for key in keys:
        R, N, B, arc = D[key], D[key + '|N'], D[key + '|B'], D[key + '|arc']
        if len(R) < 3:
            continue
        pick = np.unique(np.linspace(0, len(R) - 1, 6).round().astype(int))
        sc_ = 4000.0
        im = Image.new('RGB', (6 * 170, 190), 'white')
        d = ImageDraw.Draw(im)
        for col, j in enumerate(pick):
            ox, oy = 85 + 170 * col, 95
            for g_ in range(-80, 81, 40):
                d.line((ox + g_, 10, ox + g_, 180), fill=(225, 225, 235))
                d.line((ox - 80, oy + g_, ox + 80, oy + g_), fill=(225, 225, 235))
            c = R[j].mean(0)
            q = R[j] - c
            px = [(ox + sc_ * float(v @ B[j]), oy - sc_ * float(v @ N[j])) for v in q]
            d.polygon(px, outline=(30, 40, 90), fill=(200, 205, 220))
            for p in px:
                d.ellipse((p[0] - 1.5, p[1] - 1.5, p[0] + 1.5, p[1] + 1.5), fill=(20, 80, 200))
            d.text((ox - 78, 12), f'{1000 * arc[j]:.0f} mm', fill=(0, 0, 0))
        d.text((4, 176), key.replace('|', ' / ') + '  (grid 1 cm, B right, N up)', fill=(150, 0, 0))
        tiles.append(im)
    W = max(t.width for t in tiles)
    S = Image.new('RGB', (W, sum(t.height for t in tiles)), 'white')
    y = 0
    for t in tiles:
        S.paste(t, (0, y))
        y += t.height
    S.save(os.path.join(outdir, 'sheet_sections.jpg'), quality=88)
    print('SHEET', os.path.join(outdir, 'sheet_sections.jpg'), S.size)


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    args = {}
    for k in ('--out', '--render', '--sheet'):
        if k in argv:
            args[k] = argv[argv.index(k) + 1]
    if '--sheet' in args:
        sheets(os.path.join(ROOT, args['--sheet']))
    elif '--render' in args:
        sys.path.insert(0, ROOT)
        render_demo(os.path.join(ROOT, args['--render']))
    else:
        build_demo(os.path.join(ROOT, args.get('--out', 'out/hair_kernel_demo')))


if __name__ == '__main__':
    main()
