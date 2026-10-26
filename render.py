"""Cel-shaded orthographic renders aligned pixel-for-pixel with ref/<view>.png.

    blender -b out/levi.blend -P render.py -- [--out out/render] [--views front,side,back]
                                              [--hide _proxy] [--scale 1]
                                              [--no-regions] [--freestyle] [--[no-]shadows]
                                              [--sun AZ,EL] [--ramp T] [--ramp-key KEY=T,...]
                                              [--clay] [--turntable N] [--pose NAME,...|all]
                                              [--thin-casters] [--shadow FILTER,ANGLE,MAXRES]
                                              [--caster-policy on|off] [--hem-lift NAME=M,...]
                                              [--palette KEY.TONE=#RRGGBB,...]

Review views (no reference; same ortho scale and frame centre, key light
still camera-relative): --views q34_front_left,q34_back_right,high, or
--views review for the sheet views plus these three, or turn_<AZ> (degrees
from the front toward the character's left). --turntable N adds N evenly
spaced turn_<AZ> views and tiles them into <out>/turntable.png. --clay renders
neutral grey diffuse with the outline hulls off (form review, no regions).
--pose renders a rigged .blend in tools/rig_pose.py POSES into
<out>/<pose>/<view>.png (no regions). The calibrated front/side/back output is
unchanged by any of these.

Writes <out>/<view>.png (RGBA, transparent background) at PANEL_W x PANEL_H,
and <out>/<view>_regions.png: the same frame with every toon material flat-
coloured by its levi.regions region (used by tools/compare.py for per-region
IoU). --scale 2 renders at double resolution for close inspection (not
comparable). --freestyle adds 1 px crease/border lines in each material's
palette line colour on top of the inverted-hull outlines (off by default; the
sheet's interior lines are mostly painted detail, not geometric creases).

Colour management is Standard / sRGB with no look, exposure 0, gamma 1 and no
dither, so an emitted palette hex is written to the PNG as exactly that hex.
Renders are deterministic (fixed TAA sequence, no shadow jitter, no GI).
"""
import argparse
import math
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
sys.path.insert(1, os.path.join(ROOT, 'tools'))   # contact, rig_pose (imported on demand)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from levi import regions, spec, toon  # noqa: E402
from levi.toon import GRAD_ATTR, srgb  # noqa: E402

# Key light, relative to the camera of each view, like the sheet's: every
# panel (front, side and back alike) is lit from the viewer's upper left,
# almost from the front, so each view is mostly lit. Azimuth is measured from
# the view axis toward image-left, elevation upward. Surfaces turned away
# (sides, undersides of hems, chin, hair strands) fall into the shade tone.
SUN_AZIMUTH_DEG = 20.0
SUN_ELEVATION_DEG = 12.0  # round 2: lower sun keeps cast shadows short, so skin
# shade share matches the sheet's (~18%) with shadows on
# Cast shadows are on: on the full model they give the sheet's contact
# shadows (skirt onto petticoat and thighs, chin onto neck, sleeves onto the
# hair behind them), which N.L alone cannot, and the petticoat's shade share
# goes from ~3% to ~20-37% (sheet ~40%). Sun-only shadow maps with no
# jitter stay deterministic. --no-shadows turns them off for comparison.
CAST_SHADOWS = True
# Thin strips don't cast (round 4). Ribbons, ties, laces, the halter and
# choker, leaf veins and seam strips would print narrow, hard shadow copies of
# themselves onto the pale cloth and skin a few mm away, which the sheet never
# paints and which read as dark slivers beside every ribbon. They still
# receive shadows. Bulky ornaments (bows, leaves) keep casting: turning them
# off also drops their self-shadowing, and their own N.L shading then breaks
# into more small islands (tools/review.py shade_islands.txt: green +7..+12).
# An object casts unless:
#   obj['levi_cast_shadow'] is set: that value decides (parts opt in or out);
#   otherwise its name is in NO_CAST_OBJECTS (parts should prefer setting
#   obj['levi_cast_shadow'] = False themselves; then drop the name here).
# `render.py --thin-casters` restores casting for comparison.
NO_CAST_OBJECTS = (
    'bodice_ribbon_tails', 'bodice_lacing', 'bodice_seams', 'bodice_facings',
    'sleeve_ribbon', 'shoes_ribbons', 'acc_halter', 'acc_choker',
    'acc_leaf_veins_L', 'acc_leaf_veins_R',
)
# EEVEE's diffuse response to a sun of strength E is E * N.L / pi, so E = pi
# makes ShaderToRGB return exactly N.L x shadow (0..1) for the toon ramp.
SUN_ENERGY = math.pi
AMBIENT = 0.0        # world strength (kept 0: the toon ramp needs pure N.L)
TAA_SAMPLES = 16     # edge anti-aliasing only; flat interiors are exact
SHADOW_FILTER = 0.5  # sun shadow PCF radius: crisp cel shadow edges
SUN_ANGLE_DEG = 0.0  # sun angular diameter (0 = hard shadow edges)
SHADOW_MAX_RES = 0.001  # finest sun shadow-map texel, metres (Blender default)

# Review views (not on the sheet, no reference): the same ortho camera and
# camera-relative key light orbited around the model. (azimuth, elevation)
# in degrees; azimuth from the front camera toward the character's left (+X),
# so 90 is the sheet's side view and 180 its back view.
REVIEW_CAMERAS = {
    'q34_front_left': (45.0, 0.0),    # between front and side (character's front-left)
    'q34_back_right': (225.0, 0.0),   # the opposite diagonal: back and the unseen right side
    'high': (0.0, 30.0),              # front, looking down 30 deg (tops of shoulders, hair, skirt)
}
TURNTABLE_ELEVATION_DEG = 0.0  # turn_<AZ> views (--turntable N)
TURNTABLE_ANGLES = {}          # --turntable view name -> exact azimuth
# --clay: neutral grey diffuse, outlines off, to judge form and flatness. The
# key light sits higher and further round than the cel key so planes read.
CLAY_SUN = (35.0, 35.0)
CLAY_GREY = (0.16, 0.62, 0.18)  # display value = a + b * N.L x shadow + c * facing


def setup_scene(scale, shadows=CAST_SHADOWS):
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_EEVEE'
    sc.render.resolution_x = spec.PANEL_W * scale
    sc.render.resolution_y = spec.PANEL_H * scale
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = True
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_mode = 'RGBA'
    sc.render.image_settings.color_depth = '8'
    sc.render.filter_size = 1.0
    sc.render.dither_intensity = 0.0
    sc.render.use_freestyle = False
    # No date / render-time metadata in the PNGs, so reruns are byte-identical.
    for prop in sc.render.bl_rna.properties:
        if prop.identifier.startswith('use_stamp') and not prop.is_readonly:
            setattr(sc.render, prop.identifier, False)
    sc.display_settings.display_device = 'sRGB'
    sc.view_settings.view_transform = 'Standard'
    sc.view_settings.look = 'None'
    sc.view_settings.exposure = 0.0
    sc.view_settings.gamma = 1.0
    sc.view_settings.use_curve_mapping = False

    ee = sc.eevee
    ee.taa_render_samples = TAA_SAMPLES
    ee.use_shadows = shadows
    ee.use_raytracing = False
    ee.use_fast_gi = False
    ee.shadow_ray_count = 1
    ee.shadow_step_count = 6
    ee.shadow_resolution_scale = 1.0

    w = sc.world or bpy.data.worlds.new('World')
    sc.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes.get('Background')
    bg.inputs[0].default_value = (0, 0, 0, 1)
    bg.inputs[1].default_value = AMBIENT

    sun = bpy.data.objects.get('RenderSun')
    if not sun:
        sun = bpy.data.objects.new('RenderSun', bpy.data.lights.new('RenderSun', 'SUN'))
        sc.collection.objects.link(sun)
    sun.data.energy = SUN_ENERGY
    sun.data.color = (1, 1, 1)
    sun.data.angle = math.radians(SUN_ANGLE_DEG)
    sun.data.shadow_maximum_resolution = SHADOW_MAX_RES
    sun.data.use_shadow = shadows
    sun.data.use_shadow_jitter = False
    sun.data.shadow_filter_radius = SHADOW_FILTER

    cam = bpy.data.objects.get('RenderCam')
    if not cam:
        cam = bpy.data.objects.new('RenderCam', bpy.data.cameras.new('RenderCam'))
        sc.collection.objects.link(cam)
    cam.data.type = 'ORTHO'
    cam.data.ortho_scale = spec.PANEL_H / spec.PX_PER_M
    cam.data.clip_start = 0.1
    cam.data.clip_end = 20.0
    cam.data.sensor_fit = 'VERTICAL'
    sc.camera = cam
    return sc, cam, sun


def casts_shadow(obj):
    """Whether `obj` should cast sun shadows (see NO_CAST_OBJECTS)."""
    if 'levi_cast_shadow' in obj:
        return bool(obj['levi_cast_shadow'])
    return obj.name.split('.')[0] not in NO_CAST_OBJECTS


def set_shadow_casters(thin=False):
    """Turn shadow casting off for thin accessories (unless `thin`).
    Returns the names of the objects that no longer cast."""
    names = {o.name.split('.')[0] for o in bpy.data.objects}
    missing = [n for n in NO_CAST_OBJECTS if n not in names]
    if missing:   # a part renamed one: it casts again; set obj['levi_cast_shadow'] there
        print('WARNING render.NO_CAST_OBJECTS not found:', ','.join(missing))
    off = []
    for obj in bpy.data.objects:
        if obj.type != 'MESH' or not obj.visible_shadow:
            continue
        if not thin and not casts_shadow(obj):
            obj.visible_shadow = False
            off.append(obj.name)
    return sorted(off)


# Round 5: which casters each surface receives (EEVEE light + shadow linking).
# The sheet is flat anime cel: it paints a few large contact shadows (the
# skirt onto the petticoat and thighs, the chin onto the neck, the hair and
# sleeves onto what is right behind them) and never the shadow of a hand or
# a sleeve on the pale skirt. One sun cannot pick casters per receiver, so
# the key light is split into identical suns, one per receiver group: each
# lights only its group's objects (receiver collection) and is shadowed only
# by that group's casters (blocker collection). Groups are part collections
# ('*' = every mesh not claimed by an earlier group). Blockers name part
# collections ('*' = all of them, '-name' removes one) and hem proxies
# ('+name', HEM_PROXIES). Per-object opt-outs (obj['levi_cast_shadow'],
# NO_CAST_OBJECTS) still apply to every group.
#   skirt:     shades only from the skirt family itself (folds, lobes), not
#              from the hands, the sleeve balloons, the hair or the bodice
#              ribbons hanging over it (the round-4 finger prints).
#   petticoat: its own tiers plus a smooth stand-in for the skirt hem, so the
#              under-skirt shadow is one soft-edged band, not a print of
#              every skirt lobe.
#   skin:      the body takes the skirt's shadow from a smooth stand-in for
#              skirt + petticoat (one even band across the thighs, not the
#              scalloped print of every ruffle); everything else that casts
#              on it still does (hair, head, sleeves, bodice).
#   rest:      every other object, every caster (as before round 5).
# Measured (round 5, review shade_stats): skin shade front/side/back
# 0.21/0.30/0.28 -> ~0.18/0.27/0.21 (sheet 0.17/0.19/0.18); the finger and
# sleeve prints on the skirt are gone. Light linking costs one shadow map per
# group (4 suns); see CLAUDE.md for timings.
# `render.py --caster-policy off` goes back to one sun and all casters.
CASTER_POLICY = (
    ('skirt', ('skirt',), ('skirt', 'petticoat')),
    ('petticoat', ('petticoat',), ('petticoat', '+skirt_hem')),
    ('skin', ('body',), ('*', '-skirt', '-petticoat', '+hem')),
    ('rest', ('*',), ('*',)),
)
# Skirt hem shadow proxy (shadow rays only, never seen by the camera): a
# surface of revolution through the lowest skirt/petticoat point in each of
# HEM_PROXY_SECTORS sectors around the skirt's axis, smoothed circularly
# (gaussian, HEM_PROXY_SMOOTH_DEG), with a wall up to the waist and a cap
# under the hem. Its shadow edge on the legs is one smooth curve.
# name -> (source part collections, lift in metres: raises the proxy hem
# above the smoothed lowest point, so the band is no longer than the real
# hem's average shadow). Blockers refer to them as '+name'.
HEM_PROXIES = {
    'hem': (('skirt', 'petticoat'), 0.04),
    'skirt_hem': (('skirt',), 0.02),
}
PROXY_PREFIX = '_shadow_'
HEM_PROXY_SECTORS = 96
HEM_PROXY_SMOOTH_DEG = 20.0


def _part_meshes(name):
    col = bpy.data.collections.get(name)
    return [o for o in col.all_objects if o.type == 'MESH'] if col and not col.hide_render else []


def _world_verts(objs):
    """Evaluated world-space vertices of `objs` as an (N, 3) array."""
    import numpy as np
    dg = bpy.context.evaluated_depsgraph_get()
    chunks = []
    for o in objs:
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        try:
            co = np.empty(len(me.vertices) * 3, dtype=np.float64)
            me.vertices.foreach_get('co', co)
        finally:
            ev.to_mesh_clear()
        co = co.reshape(-1, 3)
        m = np.array(ev.matrix_world)
        chunks.append(co @ m[:3, :3].T + m[:3, 3])
    return np.concatenate(chunks) if chunks else np.zeros((0, 3))


def remove_proxies():
    for o in [o for o in bpy.data.objects if o.name.startswith(PROXY_PREFIX)]:
        me = o.data
        bpy.data.objects.remove(o, do_unlink=True)
        if me is not None and me.users == 0:
            bpy.data.meshes.remove(me)


def build_hem_proxy(name, sources, lift=0.0):
    """Build the hem shadow proxy PROXY_PREFIX + name from the evaluated
    `sources` part collections (so a posed skirt gets a posed proxy).
    Returns the object, or None when the sources are missing."""
    import numpy as np
    v = _world_verts([o for n in sources for o in _part_meshes(n)])
    if len(v) < 16:
        return None
    n = HEM_PROXY_SECTORS
    c = v[:, :2].mean(0)
    d = v[:, :2] - c
    r = np.hypot(d[:, 0], d[:, 1])
    sec = (np.floor((np.arctan2(d[:, 1], d[:, 0]) + np.pi) / (2 * np.pi) * n).astype(int)) % n
    z_top = float(v[:, 2].max())
    z_hem = np.full(n, np.nan)
    r_hem = np.full(n, np.nan)
    r_top = np.full(n, np.nan)
    for i in range(n):
        m = sec == i
        if not m.any():
            continue
        z_hem[i] = v[m, 2].min()
        r_hem[i] = r[m].max()
        top = m & (v[:, 2] > z_top - 0.03)
        r_top[i] = np.median(r[top]) if top.any() else np.nan
    for a in (z_hem, r_hem, r_top):   # fill empty sectors from their neighbours
        ok = ~np.isnan(a)
        if not ok.any():
            return None
        idx = np.arange(n)
        a[~ok] = np.interp(idx[~ok], idx[ok], a[ok], period=n)
    # circular gaussian smoothing
    sig = max(1e-6, HEM_PROXY_SMOOTH_DEG / 360.0 * n)
    k = np.arange(-n // 2, n // 2)
    w = np.exp(-0.5 * (k / sig) ** 2)
    w /= w.sum()

    def smooth(a):
        return np.array([np.dot(w, a[(i + k) % n]) for i in range(n)])
    z_hem, r_hem, r_top = smooth(z_hem) + lift, smooth(r_hem), smooth(r_top)
    ang = (np.arange(n) + 0.5) / n * 2 * np.pi - np.pi
    cs, sn = np.cos(ang), np.sin(ang)
    verts = [(c[0] + r_hem[i] * cs[i], c[1] + r_hem[i] * sn[i], z_hem[i]) for i in range(n)]
    verts += [(c[0] + r_top[i] * cs[i], c[1] + r_top[i] * sn[i], z_top) for i in range(n)]
    verts.append((c[0], c[1], float(z_hem.mean())))
    ctr = 2 * n
    faces = [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    faces += [((i + 1) % n, i, ctr) for i in range(n)]
    me = bpy.data.meshes.new(PROXY_PREFIX + name)
    me.from_pydata([tuple(map(float, p)) for p in verts], [], faces)
    me.validate()
    obj = bpy.data.objects.new(PROXY_PREFIX + name, me)
    bpy.context.scene.collection.objects.link(obj)
    obj.visible_camera = False
    obj.visible_diffuse = False
    obj.visible_glossy = False
    obj.visible_transmission = False
    obj.visible_volume_scatter = False
    obj.visible_shadow = True
    obj['levi_cast_shadow'] = True
    obj['no_outline'] = True
    return obj


def _policy_collection(name, objs):
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)   # not linked to the scene: a set only
    for o in list(col.objects):
        col.objects.unlink(o)
    for o in objs:
        col.objects.link(o)
    return col


def setup_caster_policy(sun, policy=CASTER_POLICY, use_proxies=True):
    """Split the key light into one sun per receiver group (light linking)
    with that group's blockers (shadow linking). Returns the suns (the first
    is `sun`); all must be aimed alike (place_sun). An empty or None policy
    clears any linking and returns [sun]. With use_proxies=False a '+name'
    blocker stands for the proxy's source collections instead (Freestyle
    would treat the invisible proxy as an occluder and drop lines)."""
    if not use_proxies and policy:
        policy = [(g, r, tuple(x for b in block for x in
                               (HEM_PROXIES[b[1:]][0] if b.startswith('+') and b[1:] in HEM_PROXIES
                                else (b,))))
                  for g, r, block in policy]
    for o in [o for o in bpy.data.objects if o.name.startswith('RenderSun.')]:
        bpy.data.objects.remove(o, do_unlink=True)
    sun.light_linking.receiver_collection = None
    sun.light_linking.blocker_collection = None
    remove_proxies()
    if not policy:
        return [sun]
    meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    part_names = [c.name for c in bpy.context.scene.collection.children]
    wanted = {b[1:] for _g, _r, block in policy for b in block if b.startswith('+')}
    unknown = wanted - set(HEM_PROXIES)
    if unknown:
        raise ValueError(f'CASTER_POLICY: unknown proxies {sorted(unknown)}')
    proxies = {}
    for name in sorted(wanted):
        obj = build_hem_proxy(name, *HEM_PROXIES[name])
        if obj is not None:
            proxies[name] = obj
    in_parts = {o.name for n in part_names for o in _part_meshes(n)}
    claimed = set()
    suns = []
    for group, recv, block in policy:
        if '*' in recv:
            rx = [o for o in meshes if o.name not in claimed]
        else:
            rx = [o for n in recv for o in _part_meshes(n) if o.name not in claimed]
        claimed |= {o.name for o in rx}
        names = set()
        for b in block:
            if b == '*':
                names |= set(part_names)
            elif b.startswith('-'):
                names.discard(b[1:])
            elif not b.startswith('+'):
                names.add(b)
        bk = [o for n in sorted(names) for o in _part_meshes(n)]
        if '*' in block:   # meshes outside any part collection (e.g. _proxy) too
            bk += [o for o in meshes if o.name not in in_parts]
        bk += [proxies[b[1:]] for b in block if b.startswith('+') and b[1:] in proxies]
        if not rx:
            continue
        s = sun if not suns else bpy.data.objects.new(f'RenderSun.{group}', sun.data)
        if s is not sun:
            bpy.context.scene.collection.objects.link(s)
        s.light_linking.receiver_collection = _policy_collection(f'_rx_{group}', rx)
        if not bk:   # no blocker collection = every object casts
            print('WARNING caster group', group, 'has no blockers; every object casts on it')
        s.light_linking.blocker_collection = _policy_collection(f'_bk_{group}', bk) if bk else None
        suns.append(s)
        print('CASTERS', group, 'receivers', len(rx), 'blockers', len(bk))
    return suns or [sun]


def view_angles(view):
    """(azimuth, elevation) degrees of a review view, or None for the
    calibrated sheet views (spec.CAMERAS). Azimuth is measured from the front
    camera (-Y) toward the character's left (+X): 90 = side, 180 = back."""
    if view in REVIEW_CAMERAS:
        return REVIEW_CAMERAS[view]
    if view in TURNTABLE_ANGLES:
        return TURNTABLE_ANGLES[view], TURNTABLE_ELEVATION_DEG
    if view.startswith('turn_'):
        try:
            return float(view[5:]), TURNTABLE_ELEVATION_DEG
        except ValueError:
            pass
    return None


def known_view(view):
    return view in spec.CAMERAS or view_angles(view) is not None


def place_camera(cam, view):
    z_center = (spec.SHEET_GROUND_Y - spec.PANEL_H / 2) / spec.PX_PER_M
    cam.data.shift_x = 0.0
    cam.data.shift_y = 0.0
    if view in spec.CAMERAS:
        c = spec.CAMERAS[view]
        cam.location = (c['loc'][0], c['loc'][1], z_center)
        cam.rotation_euler = (math.radians(90), 0.0, math.radians(c['rot_z_deg']))
        # Panel centre column is PANEL_W/2 exactly, so no horizontal shift needed.
        return
    # Review views: the same ortho scale and frame centre, orbiting the
    # vertical axis through the origin (between the feet).
    az, el = (math.radians(a) for a in view_angles(view))
    d = Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el)))
    cam.location = Vector((0.0, 0.0, z_center)) + 6.0 * d
    cam.rotation_euler = (math.radians(90) - el, 0.0, az)


def place_sun(sun, cam, azimuth=None, elevation=None):
    """Aim the sun from the camera's upper left (camera-relative key light)."""
    az = math.radians(SUN_AZIMUTH_DEG if azimuth is None else azimuth)
    el = math.radians(SUN_ELEVATION_DEG if elevation is None else elevation)
    # Camera space: +X image right, +Y image up, +Z toward the viewer.
    to_light_cam = Vector((-math.sin(az) * math.cos(el), math.sin(el), math.cos(az) * math.cos(el)))
    cam_rot = cam.rotation_euler.to_matrix()
    to_light = (cam_rot @ to_light_cam).normalized()
    # A sun shines along its local -Z, so point local +Z at the light.
    sun.rotation_euler = to_light.to_track_quat('Z', 'Y').to_euler()


def set_region_materials():
    """Swap every toon/outline material to flat region colours (exact labels).

    Gradient materials switch region where toon_grad crosses 0.5. Outlines
    take their key's region, matching the reference, whose majority filter
    absorbs the thin line art into the neighbouring region.
    """
    def lin(label):
        return srgb('#%02X%02X%02X' % regions.LABEL_RGB[label])

    unknown = lin(regions.UNKNOWN)
    for mat in bpy.data.materials:
        if not mat.use_nodes or not mat.node_tree:
            continue
        nt = mat.node_tree
        key = mat.get('toon_key')
        region = regions.REGION_OF_KEY.get(key)
        col_a = lin(regions.LABEL[region]) if region else unknown
        emit = nt.nodes.new('ShaderNodeEmission')
        emit.inputs['Strength'].default_value = 1.0
        grad = mat.get('toon_gradient')
        if grad and not mat.get('is_outline') and grad in regions.REGION_OF_KEY:
            attr = nt.nodes.new('ShaderNodeAttribute')
            attr.attribute_type = 'GEOMETRY'
            attr.attribute_name = GRAD_ATTR
            step = nt.nodes.new('ShaderNodeMath')
            step.operation = 'GREATER_THAN'
            step.inputs[1].default_value = 0.5
            nt.links.new(attr.outputs['Fac'], step.inputs[0])
            mix = nt.nodes.new('ShaderNodeMix')
            mix.data_type = 'RGBA'
            nt.links.new(step.outputs['Value'], mix.inputs['Factor'])
            mix.inputs[6].default_value = col_a
            mix.inputs[7].default_value = lin(regions.LABEL[regions.REGION_OF_KEY[grad]])
            nt.links.new(mix.outputs[2], emit.inputs['Color'])
        else:
            emit.inputs['Color'].default_value = col_a
        for out in [n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL']:
            nt.links.new(emit.outputs['Emission'], out.inputs['Surface'])


def set_clay_materials():
    """Swap every material to a neutral grey diffuse and turn the outline
    hulls off, so form, flat spots and faceting read without the palette.

    grey = a + b * (N.L x shadow) + c * facing (CLAY_GREY, display values),
    smooth (no ramp), so shading follows the normals continuously.
    """
    a, b, c = CLAY_GREY
    for mat in bpy.data.materials:
        if not mat.use_nodes or not mat.node_tree:
            continue
        nt = mat.node_tree
        diff = nt.nodes.new('ShaderNodeBsdfDiffuse')
        diff.inputs['Color'].default_value = (1, 1, 1, 1)
        s2r = nt.nodes.new('ShaderNodeShaderToRGB')
        nt.links.new(diff.outputs['BSDF'], s2r.inputs['Shader'])
        bw = nt.nodes.new('ShaderNodeRGBToBW')
        nt.links.new(s2r.outputs['Color'], bw.inputs['Color'])
        lw = nt.nodes.new('ShaderNodeLayerWeight')
        lw.inputs['Blend'].default_value = 0.5
        facing = nt.nodes.new('ShaderNodeMath')
        facing.operation = 'SUBTRACT'
        facing.inputs[0].default_value = 1.0
        nt.links.new(lw.outputs['Facing'], facing.inputs[1])
        lit = nt.nodes.new('ShaderNodeMath')
        lit.operation = 'MULTIPLY_ADD'
        lit.inputs[1].default_value = b
        lit.inputs[2].default_value = a
        nt.links.new(bw.outputs['Val'], lit.inputs[0])
        val = nt.nodes.new('ShaderNodeMath')
        val.operation = 'MULTIPLY_ADD'
        val.inputs[1].default_value = c
        val.use_clamp = True
        nt.links.new(facing.outputs['Value'], val.inputs[0])
        nt.links.new(lit.outputs['Value'], val.inputs[2])
        # display value -> scene linear (Standard view transform)
        lin = nt.nodes.new('ShaderNodeMath')
        lin.operation = 'POWER'
        lin.inputs[1].default_value = 2.2
        nt.links.new(val.outputs['Value'], lin.inputs[0])
        emit = nt.nodes.new('ShaderNodeEmission')
        nt.links.new(lin.outputs['Value'], emit.inputs['Color'])
        for out in [n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL']:
            nt.links.new(emit.outputs['Emission'], out.inputs['Surface'])
    for obj in bpy.data.objects:
        for mod in obj.modifiers:
            if mod.name == 'Outline' and mod.type == 'SOLIDIFY':
                mod.show_render = False


def find_armature():
    arms = [o for o in bpy.data.objects if o.type == 'ARMATURE']
    return arms[0] if arms else None


def setup_freestyle(sc):
    """1 px crease/border lines coloured by each material's line_color."""
    sc.render.use_freestyle = True
    sc.render.line_thickness_mode = 'ABSOLUTE'
    sc.render.line_thickness = 1.0
    vl = bpy.context.view_layer
    vl.use_freestyle = True
    fs = vl.freestyle_settings
    fs.crease_angle = math.radians(120)
    ls = fs.linesets[0] if fs.linesets else fs.linesets.new('LineSet')
    ls.select_by_visibility = True
    ls.select_by_edge_types = True
    ls.select_silhouette = False
    ls.select_border = True
    ls.select_crease = True
    style = ls.linestyle
    style.thickness = 1.0
    style.color = (0, 0, 0)
    for m in list(style.color_modifiers):
        style.color_modifiers.remove(m)
    mod = style.color_modifiers.new('MaterialLine', 'MATERIAL')
    mod.material_attribute = 'LINE'
    mod.blend = 'MIX'
    mod.influence = 1.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='out/render')
    ap.add_argument('--views', default=','.join(spec.VIEWS))
    ap.add_argument('--hide', default='', help='comma-separated collections to hide')
    ap.add_argument('--scale', type=int, default=1)
    ap.add_argument('--no-regions', action='store_true', help='skip the <view>_regions.png pass')
    ap.add_argument('--freestyle', action='store_true', help='add Freestyle crease/open-border lines')
    ap.add_argument('--shadows', action=argparse.BooleanOptionalAction, default=CAST_SHADOWS,
                    help=f'sun cast shadows (default: {"on" if CAST_SHADOWS else "off"})')
    ap.add_argument('--caster-policy', choices=('on', 'off'), default='on',
                    help='per-receiver caster groups (CASTER_POLICY); off = one sun, every caster')
    ap.add_argument('--hem-lift', default='',
                    help='NAME=M,...: override HEM_PROXIES lifts in metres (look-dev experiments)')
    ap.add_argument('--thin-casters', action='store_true',
                    help='let thin strips (NO_CAST_OBJECTS) cast shadows too')
    ap.add_argument('--sun', default='', help='AZ,EL degrees: override the key light (look-dev experiments)')
    ap.add_argument('--shadow', default='',
                    help='FILTER,ANGLE,MAXRES: override SHADOW_FILTER, SUN_ANGLE_DEG, SHADOW_MAX_RES '
                         '(look-dev experiments; empty fields keep the default)')
    ap.add_argument('--ramp', type=float, default=None, help='override toon.RAMP_THRESHOLD (look-dev experiments)')
    ap.add_argument('--ramp-key', default='', help='KEY=T,...: override toon.RAMP_BY_KEY entries (look-dev experiments)')
    ap.add_argument('--palette', default='',
                    help='KEY.TONE=#RRGGBB,...: override spec.PALETTE entries, TONE base/shade/line '
                         '(look-dev experiments)')
    ap.add_argument('--clay', action='store_true',
                    help='neutral grey diffuse, outlines off, no regions (form review)')
    ap.add_argument('--turntable', type=int, default=0, metavar='N',
                    help='also render N evenly spaced turn_<AZ> views and <out>/turntable.png')
    ap.add_argument('--pose', default='',
                    help='NAME,... or all: pose a rigged .blend with tools/rig_pose.py POSES (also extended '
                         'poses and <clip>@<frame>, tools/motion_poses.py) and '
                         'render <out>/<pose>/<view>.png for each (no regions)')
    args = ap.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
    try:
        az, el = map(float, args.sun.split(',')) if args.sun else (None, None)
        ramp_key = {}
        for item in filter(None, args.ramp_key.split(',')):
            k, t = item.split('=')
            ramp_key[k] = float(t)
    except ValueError:
        ap.error('--sun takes AZ,EL and --ramp-key takes KEY=T,... (numbers in degrees / N.L)')
    bad = [k for k in ramp_key if k not in spec.PALETTE]
    if bad:
        ap.error(f'--ramp-key: unknown palette key(s) {bad}')
    for item in filter(None, args.palette.split(',')):
        try:
            kt, hx = item.split('=')
            k, t = kt.split('.')
            ok = (k in spec.PALETTE and t in ('base', 'shade', 'line')
                  and re.fullmatch(r'#?[0-9A-Fa-f]{6}', hx) is not None)
        except ValueError:
            ok = False
        if not ok:
            ap.error(f'--palette: bad entry {item!r} (KEY.TONE=#RRGGBB)')
        spec.PALETTE[k] = {**spec.PALETTE[k], t: '#' + hx.lstrip('#').upper()}
    views = []
    for v in filter(None, args.views.split(',')):
        for x in (list(spec.VIEWS) + list(REVIEW_CAMERAS) if v == 'review' else [v]):
            if x not in views:
                views.append(x)
    turntable = []
    if args.turntable:
        for i in range(args.turntable):
            a = 360.0 * i / args.turntable
            name = 'turn_%03d' % round(a) if abs(a - round(a)) < 1e-6 else 'turn_%07.3f' % a
            TURNTABLE_ANGLES[name] = a   # exact angle, not re-parsed from the name
            turntable.append(name)
        views += [v for v in turntable if v not in views]
    bad = [v for v in views if not known_view(v)]
    if bad:
        ap.error(f'--views: unknown view(s) {bad}; choose from '
                 f'{list(spec.CAMERAS) + list(REVIEW_CAMERAS)}, turn_<AZ> or "review"')
    poses, arm, rig_pose = [], None, None
    if args.pose:
        import rig_pose
        poses = sorted(rig_pose.POSES) if args.pose == 'all' else args.pose.split(',')
        bad = [p for p in poses if not (rig_pose.known(p) if hasattr(rig_pose, 'known') else p in rig_pose.POSES)]
        if bad:
            ap.error(f'--pose: unknown pose(s) {bad}; choose from {sorted(rig_pose.POSES)}')
        arm = find_armature()
        if arm is None:
            ap.error('--pose needs a rigged .blend (build.py -- --rig)')
        if args.turntable:
            ap.error('--pose and --turntable do not combine')

    for name in filter(None, args.hide.split(',')):
        col = bpy.data.collections.get(name)
        if col:
            col.hide_render = True

    global SHADOW_FILTER, SUN_ANGLE_DEG, SHADOW_MAX_RES
    try:
        sh = (args.shadow.split(',') + ['', '', ''])[:3]
        SHADOW_FILTER, SUN_ANGLE_DEG, SHADOW_MAX_RES = (
            float(v) if v else d for v, d in zip(sh, (SHADOW_FILTER, SUN_ANGLE_DEG, SHADOW_MAX_RES)))
    except ValueError:
        ap.error('--shadow takes FILTER,ANGLE,MAXRES numbers')
    if args.ramp is not None:
        toon.RAMP_THRESHOLD = args.ramp
    toon.RAMP_BY_KEY.update(ramp_key)
    # Re-apply the current ramp / palette to materials saved in the .blend, so
    # look-dev changes take effect without rebuilding the model.
    print('SYNCED', toon.sync_materials(), 'materials')
    sc, cam, sun = setup_scene(args.scale, shadows=args.shadows)
    for item in filter(None, args.hem_lift.split(',')):
        try:
            k, m = item.split('=')
            HEM_PROXIES[k] = (HEM_PROXIES[k][0], float(m))
        except (ValueError, KeyError):
            ap.error(f'--hem-lift: bad entry {item!r} (NAME=M, NAME in {sorted(HEM_PROXIES)})')
    # Clay shows form with every real contact shadow: no caster policy there.
    policy = (CASTER_POLICY if args.shadows and args.caster_policy == 'on' and not args.clay
              else None)
    if args.hem_lift and not policy:
        print('WARNING --hem-lift has no effect without the caster policy '
              '(--caster-policy off, --no-shadows or --clay)')
    if args.shadows:
        print('NO_CAST', ','.join(set_shadow_casters(thin=args.thin_casters)) or '-')
    # --pose builds the policy per pose (the proxies follow the posed skirt)
    # (Freestyle would draw and occlude with the invisible hem proxies: there
    # the real skirt and petticoat cast instead.)
    use_proxies = not args.freestyle
    suns = setup_caster_policy(sun, None if poses else policy, use_proxies)
    if args.freestyle:
        setup_freestyle(sc)
    if args.clay:
        set_clay_materials()
        if az is None:
            az, el = CLAY_SUN
    out = os.path.join(ROOT, args.out)
    os.makedirs(out, exist_ok=True)

    def render_views(folder, views, suffix=''):
        os.makedirs(folder, exist_ok=True)
        for view in views:
            place_camera(cam, view)
            for s in suns:
                place_sun(s, cam, az, el)
            sc.render.filepath = os.path.join(folder, f'{view}{suffix}.png')
            bpy.ops.render.render(write_still=True)
            print('RENDERED', sc.render.filepath)

    if poses:
        # Pose sheet input: <out>/<pose>/<view>.png per pose (rigged .blend).
        for name in poses:
            rig_pose.apply_pose(arm, name)
            if policy:   # the hem proxy follows the posed skirt
                suns[:] = setup_caster_policy(sun, policy, use_proxies)
            render_views(os.path.join(out, name), views)
        rig_pose.reset_pose(arm)
        return
    render_views(out, views)
    if turntable:
        import contact
        sheet = contact.tile([contact.load(os.path.join(out, f'{v}.png')) for v in turntable],
                             cols=min(len(turntable), 8), labels=turntable, scale=0.5, crop=True)
        contact.save(os.path.join(out, 'turntable.png'), sheet)
        print('SHEET', os.path.join(out, 'turntable.png'))
    # Region labels: the sheet views (compared with ref/) and the review views
    # (per-region shade share at any angle, tools/review.py); not the
    # turntable, and not in clay.
    region_views = [v for v in views if v in spec.CAMERAS or v in REVIEW_CAMERAS]
    if args.no_regions or args.clay or not region_views:
        return
    set_region_materials()
    sc.render.use_freestyle = False
    # Exact labels: no sub-pixel jitter or filter blending two label
    # colours into a third at region boundaries.
    sc.eevee.taa_render_samples = 1
    sc.render.filter_size = 0.0
    render_views(out, region_views, '_regions')


if __name__ == '__main__':
    main()
