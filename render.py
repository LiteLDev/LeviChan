"""Cel-shaded orthographic renders aligned pixel-for-pixel with ref/<view>.png.

    blender -b out/levi.blend -P render.py -- [--out out/render] [--views front,side,back]
                                              [--hide _proxy] [--scale 1]
                                              [--no-regions] [--freestyle] [--[no-]shadows]
                                              [--sun AZ,EL] [--ramp T] [--ramp-key KEY=T,...]
                                              [--clay] [--turntable N] [--pose NAME,...|all]

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
# EEVEE's diffuse response to a sun of strength E is E * N.L / pi, so E = pi
# makes ShaderToRGB return exactly N.L x shadow (0..1) for the toon ramp.
SUN_ENERGY = math.pi
AMBIENT = 0.0        # world strength (kept 0: the toon ramp needs pure N.L)
TAA_SAMPLES = 16     # edge anti-aliasing only; flat interiors are exact
SHADOW_FILTER = 0.5  # sun shadow PCF radius: crisp cel shadow edges

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
    sun.data.angle = 0.0
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
    ap.add_argument('--sun', default='', help='AZ,EL degrees: override the key light (look-dev experiments)')
    ap.add_argument('--ramp', type=float, default=None, help='override toon.RAMP_THRESHOLD (look-dev experiments)')
    ap.add_argument('--ramp-key', default='', help='KEY=T,...: override toon.RAMP_BY_KEY entries (look-dev experiments)')
    ap.add_argument('--clay', action='store_true',
                    help='neutral grey diffuse, outlines off, no regions (form review)')
    ap.add_argument('--turntable', type=int, default=0, metavar='N',
                    help='also render N evenly spaced turn_<AZ> views and <out>/turntable.png')
    ap.add_argument('--pose', default='',
                    help='NAME,... or all: pose a rigged .blend with tools/rig_pose.py POSES and '
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
        bad = [p for p in poses if p not in rig_pose.POSES]
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

    if args.ramp is not None:
        toon.RAMP_THRESHOLD = args.ramp
    toon.RAMP_BY_KEY.update(ramp_key)
    # Re-apply the current ramp / palette to materials saved in the .blend, so
    # look-dev changes take effect without rebuilding the model.
    print('SYNCED', toon.sync_materials(), 'materials')
    sc, cam, sun = setup_scene(args.scale, shadows=args.shadows)
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
            place_sun(sun, cam, az, el)
            sc.render.filepath = os.path.join(folder, f'{view}{suffix}.png')
            bpy.ops.render.render(write_still=True)
            print('RENDERED', sc.render.filepath)

    if poses:
        # Pose sheet input: <out>/<pose>/<view>.png per pose (rigged .blend).
        for name in poses:
            rig_pose.apply_pose(arm, name)
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
