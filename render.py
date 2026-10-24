"""Cel-shaded orthographic renders aligned pixel-for-pixel with ref/<view>.png.

    blender -b out/levi.blend -P render.py -- [--out out/render] [--views front,side,back]
                                              [--hide _proxy] [--scale 1]

Writes <out>/<view>.png (RGBA, transparent background) at PANEL_W x PANEL_H.
--scale 2 renders at double resolution for close inspection (not comparable).
"""
import argparse
import math
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402

from levi import spec  # noqa: E402

# Key light: upper front-left of the character's facing, as on the sheet.
SUN_ROT_DEG = (50.0, 0.0, -30.0)
SUN_ENERGY = 3.0
AMBIENT = 0.25


def setup_scene(scale):
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_EEVEE'
    sc.render.resolution_x = spec.PANEL_W * scale
    sc.render.resolution_y = spec.PANEL_H * scale
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = True
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_mode = 'RGBA'
    sc.view_settings.view_transform = 'Standard'
    sc.view_settings.look = 'None'
    sc.render.filter_size = 1.0

    w = sc.world or bpy.data.worlds.new('World')
    sc.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes.get('Background')
    bg.inputs[0].default_value = (1, 1, 1, 1)
    bg.inputs[1].default_value = AMBIENT

    sun = bpy.data.objects.get('RenderSun')
    if not sun:
        sun = bpy.data.objects.new('RenderSun', bpy.data.lights.new('RenderSun', 'SUN'))
        sc.collection.objects.link(sun)
    sun.data.energy = SUN_ENERGY
    sun.data.angle = 0.0
    sun.rotation_euler = [math.radians(a) for a in SUN_ROT_DEG]

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
    return sc, cam


def place_camera(cam, view):
    c = spec.CAMERAS[view]
    z_center = (spec.SHEET_GROUND_Y - spec.PANEL_H / 2) / spec.PX_PER_M
    cam.location = (c['loc'][0], c['loc'][1], z_center)
    cam.rotation_euler = (math.radians(90), 0.0, math.radians(c['rot_z_deg']))
    # Panel centre column is PANEL_W/2 exactly, so no horizontal shift needed.
    cam.data.shift_x = 0.0
    cam.data.shift_y = 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='out/render')
    ap.add_argument('--views', default=','.join(spec.VIEWS))
    ap.add_argument('--hide', default='', help='comma-separated collections to hide')
    ap.add_argument('--scale', type=int, default=1)
    args = ap.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])

    for name in filter(None, args.hide.split(',')):
        col = bpy.data.collections.get(name)
        if col:
            col.hide_render = True

    sc, cam = setup_scene(args.scale)
    out = os.path.join(ROOT, args.out)
    os.makedirs(out, exist_ok=True)
    for view in args.views.split(','):
        place_camera(cam, view)
        sc.render.filepath = os.path.join(out, f'{view}.png')
        bpy.ops.render.render(write_still=True)
        print('RENDERED', sc.render.filepath)


main()
