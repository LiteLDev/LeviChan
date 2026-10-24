"""Cel-shaded orthographic renders aligned pixel-for-pixel with ref/<view>.png.

    blender -b out/levi.blend -P render.py -- [--out out/render] [--views front,side,back]
                                              [--hide _proxy] [--scale 1]
                                              [--no-regions] [--freestyle] [--shadows]

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

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from levi import regions, spec  # noqa: E402
from levi.toon import GRAD_ATTR, srgb  # noqa: E402

# Key light, relative to the camera of each view, like the sheet's: every
# panel (front, side and back alike) is lit from the viewer's upper left,
# almost from the front, so each view is mostly lit. Azimuth is measured from
# the view axis toward image-left, elevation upward. Surfaces turned away
# (sides, undersides of hems, chin, hair strands) fall into the shade tone.
SUN_AZIMUTH_DEG = 20.0
SUN_ELEVATION_DEG = 20.0
# Cast shadows are off by default: shadow maps on medium-poly / custom-normal
# geometry give blocky self-shadow patches and stair-stepped terminators that
# the sheet never has, while N.L alone already shades undersides and sides.
# --shadows turns them on (short cast shadows under the skirt/chin/hair).
CAST_SHADOWS = False
# EEVEE's diffuse response to a sun of strength E is E * N.L / pi, so E = pi
# makes ShaderToRGB return exactly N.L x shadow (0..1) for the toon ramp.
SUN_ENERGY = math.pi
AMBIENT = 0.0        # world strength (kept 0: the toon ramp needs pure N.L)
TAA_SAMPLES = 16     # edge anti-aliasing only; flat interiors are exact
SHADOW_FILTER = 0.5  # sun shadow PCF radius: crisp cel shadow edges


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


def place_camera(cam, view):
    c = spec.CAMERAS[view]
    z_center = (spec.SHEET_GROUND_Y - spec.PANEL_H / 2) / spec.PX_PER_M
    cam.location = (c['loc'][0], c['loc'][1], z_center)
    cam.rotation_euler = (math.radians(90), 0.0, math.radians(c['rot_z_deg']))
    # Panel centre column is PANEL_W/2 exactly, so no horizontal shift needed.
    cam.data.shift_x = 0.0
    cam.data.shift_y = 0.0


def place_sun(sun, cam):
    """Aim the sun from the camera's upper left (camera-relative key light)."""
    az, el = math.radians(SUN_AZIMUTH_DEG), math.radians(SUN_ELEVATION_DEG)
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
    ap.add_argument('--shadows', action='store_true', help='enable sun cast shadows')
    args = ap.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])

    for name in filter(None, args.hide.split(',')):
        col = bpy.data.collections.get(name)
        if col:
            col.hide_render = True

    sc, cam, sun = setup_scene(args.scale, shadows=args.shadows or CAST_SHADOWS)
    if args.freestyle:
        setup_freestyle(sc)
    out = os.path.join(ROOT, args.out)
    os.makedirs(out, exist_ok=True)
    views = args.views.split(',')
    passes = [''] if args.no_regions else ['', '_regions']
    for suffix in passes:
        if suffix == '_regions':
            set_region_materials()
            sc.render.use_freestyle = False
            # Exact labels: no sub-pixel jitter or filter blending two label
            # colours into a third at region boundaries.
            sc.eevee.taa_render_samples = 1
            sc.render.filter_size = 0.0
        for view in views:
            place_camera(cam, view)
            place_sun(sun, cam)
            sc.render.filepath = os.path.join(out, f'{view}{suffix}.png')
            bpy.ops.render.render(write_still=True)
            print('RENDERED', sc.render.filepath)


main()
