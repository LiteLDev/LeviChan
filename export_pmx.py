"""Build + rig Levi and export an MMD model with mmd_tools.

    blender -b -P export_pmx.py -- [--out out/pmx/Levi.pmx] [--parts body,skirt]
                                   [--proxy] [--fixtures] [--no-physics] [--save-blend]

Needs the mmd_tools extension (installed in the user profile), so do not pass
--factory-startup. Steps:
  1. builder.build_all + rig.build_rig (same rig as `build.py --rig`).
  2. Inverted-hull outlines are dropped (MMD draws its own edge) and all meshes
     are joined into one skinned mesh.
  3. convert_to_mmd_model; bones get their PMX Japanese/English names; each toon
     material becomes an MMD material: diffuse = palette base, ambient = base/2,
     a generated toon ramp (white -> shade/base) for the cel shadow, edge colour
     = palette line, edge on (off for objects marked no_outline).
  4. Optional physics: static bodies on the core bones, dynamic capsules on the
     hair / skirt / sleeve chains, joints parent -> chain -> chain.
  5. Export at 12.5 MMD units per metre, write <out>.json with the counts.
--fixtures adds the throwaway rig test meshes (tools/rig_fixtures.py) for any
missing body/hair/skirt/sleeves; it is on automatically when levi/parts is empty.
"""
import argparse
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Euler, Vector  # noqa: E402

from levi import rig, spec  # noqa: E402

MMD_SCALE = 12.5          # MMD units per metre
TOON_SIZE = 32

MAT_JP = {
    'skin': '肌', 'hair': '髪', 'hair_tip': '髪先', 'eye': '目', 'green': '緑', 'leaf': '葉',
    'dress': '服', 'dress_mint': '服2', 'sleeve': '袖', 'sleeve_dark': '袖2', 'petticoat': 'ペチコート',
    'cuff': 'カフス', 'flower': '花', 'shoe': '靴', 'mouth': '口',
}


def mmd_tools():
    import importlib
    for name in ('bl_ext.blender_org.mmd_tools', 'mmd_tools'):
        try:
            return importlib.import_module(name)
        except ImportError:
            pass
    raise SystemExit('mmd_tools extension not found (run Blender without --factory-startup)')


def hex_rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


# ---------------------------------------------------------------- mesh prep
def strip_outlines_and_join(arm):
    """Drop Outline modifiers + outline slots, join every skinned mesh into one.
    Returns (mesh object, set of material names that should have no MMD edge)."""
    meshes = sorted((o for o in bpy.data.objects if o.type == 'MESH' and
                     any(m.type == 'ARMATURE' and m.object == arm for m in o.modifiers)), key=lambda o: o.name)
    no_edge = set()
    for o in meshes:
        mod = o.modifiers.get('Outline')
        if mod:
            o.modifiers.remove(mod)
        me = o.data
        while len(me.materials) and me.materials[-1] and me.materials[-1].get('is_outline'):
            me.materials.pop()
        if o.get('no_outline'):
            no_edge.update(m.name for m in me.materials if m)
    # keep edges on any material also used by an outlined object
    for o in meshes:
        if not o.get('no_outline'):
            no_edge.difference_update(m.name for m in o.data.materials if m)
    for o in meshes:
        live = [m.name for m in o.modifiers if m.type != 'ARMATURE']
        if live:   # join keeps only the active object's modifiers
            print(f'warning: {o.name} still has modifiers {live}; they are lost in the join')
    for o in meshes:   # objects may share mesh data; make each single-user before joining
        if o.data.users > 1:
            o.data = o.data.copy()
    active = meshes[0]
    with bpy.context.temp_override(active_object=active, object=active, selected_objects=meshes,
                                   selected_editable_objects=meshes):
        bpy.ops.object.join()
    active.name = active.data.name = 'Levi_mesh'
    mw = active.matrix_world.copy()
    active.parent = arm
    active.matrix_world = mw
    return active, no_edge


def toon_ramp(key, out_dir):
    """MMD toon texture: top half white (lit), bottom half shade/base (cel shadow)."""
    pal = spec.PALETTE[key]
    base, shade = hex_rgb(pal['base']), hex_rgb(pal['shade'])
    ratio = [min(1.0, s / max(b, 1e-3)) for s, b in zip(shade, base)]
    px = np.ones((TOON_SIZE, TOON_SIZE, 4), dtype=np.float32)
    px[:TOON_SIZE // 2, :, :3] = ratio           # Blender rows go bottom -> top
    path = os.path.join(out_dir, f'toon_{key}.png')
    img = bpy.data.images.new(f'toon_{key}', TOON_SIZE, TOON_SIZE, alpha=False)
    img.colorspace_settings.name = 'Non-Color'
    img.pixels.foreach_set(px.ravel())
    img.filepath_raw = path
    img.file_format = 'PNG'
    img.save()
    return path


# ---------------------------------------------------------------- mmd conversion
def convert(arm, mesh, no_edge, out_dir):
    bpy.context.view_layer.objects.active = arm
    for o in bpy.context.view_layer.objects:
        o.select_set(o == arm)
    bpy.ops.mmd_tools.convert_to_mmd_model(scale=1.0 / MMD_SCALE)
    root = arm.parent
    root.name = 'Levi'
    root.mmd_root.name = 'Levi'
    root.mmd_root.name_e = 'Levi'
    txt = bpy.data.texts.get('Levi_comment') or bpy.data.texts.new('Levi_comment')
    txt.from_string('Levi - procedural model built from scratch (LeviChan).')
    root.mmd_root.comment_text = txt.name
    root.mmd_root.comment_e_text = txt.name

    for name, jp, en in rig.bone_table(arm):
        mb = arm.pose.bones[name].mmd_bone
        mb.name_j, mb.name_e = jp, en

    toon_dir = os.path.join(out_dir, 'toon')
    os.makedirs(toon_dir, exist_ok=True)
    ramps = {}
    for mat in mesh.data.materials:
        key = mat.get('toon_key', 'dress')
        pal = spec.PALETTE[key]
        mm = mat.mmd_material
        mm.name_j = MAT_JP.get(key, key) + ('' if mat.name == f'toon_{key}' else '_' + mat.name.split('__')[-1])
        mm.name_e = mat.name
        base = hex_rgb(pal['base'])
        mm.diffuse_color = base
        mm.ambient_color = [c * 0.5 for c in base]
        mm.specular_color = (0.0, 0.0, 0.0)
        mm.shininess = 5.0
        mm.alpha = 1.0
        mm.is_double_sided = True
        mm.enabled_drop_shadow = True
        mm.enabled_self_shadow_map = True
        mm.enabled_self_shadow = True
        mm.enabled_toon_edge = mat.name not in no_edge
        mm.edge_color = (*hex_rgb(pal['line']), 1.0)
        mm.edge_weight = 1.0
        path = ramps.get(key) or ramps.setdefault(key, toon_ramp(key, toon_dir))
        mm.is_shared_toon_texture = False
        mm.toon_texture_rel_path = f'toon/{os.path.basename(path)}'
        mm.toon_texture = path
    return root


# ---------------------------------------------------------------- physics
STATIC_BODIES = ['頭', '首', '上半身', '上半身2', '下半身'] + \
    [f'{n}.{t}' for n in ('足', 'ひざ', '腕', 'ひじ') for t in 'LR']
CHAIN_GROUP = {'Hair': 1, 'Skirt': 2, 'Sleeve': 3}
CHAIN_LIMIT = {'Hair': (20, 8, 20), 'Skirt': (30, 8, 15), 'Sleeve': (25, 8, 25)}   # degrees x, y, z


def add_physics(root, arm):
    m = mmd_tools()
    from importlib import import_module
    rb = import_module(m.__name__ + '.core.rigid_body')
    FnRigidBody, FnModel = rb.FnRigidBody, import_module(m.__name__ + '.core.model').FnModel
    ctx = bpy.context
    if ctx.scene.rigidbody_world is None:
        bpy.ops.rigidbody.world_add()
    rgroup = FnModel.ensure_rigid_group_object(ctx, root)
    jgroup = FnModel.ensure_joint_group_object(ctx, root)
    disp = FnModel.get_empty_display_size(root)
    bones = arm.data.bones
    bodies = {}

    def body(bname, shape, size, dyn, group, mask, mass=1.0, location=None):
        b = bones[bname]
        mb = arm.pose.bones[bname].mmd_bone
        rot = b.matrix_local.to_euler('YXZ')
        rot.rotate_axis('X', math.pi / 2)
        obj = FnRigidBody.setup_rigid_body_object(
            obj=FnRigidBody.new_rigid_body_object(ctx, rgroup), shape_type=rb.shapeType(shape),
            location=location if location is not None else (b.head_local + b.tail_local) / 2, rotation=rot, size=Vector(size), dynamics_type=dyn,
            name=mb.name_j, name_e=mb.name_e, collision_group_number=group,
            collision_group_mask=[i in mask for i in range(16)], mass=mass, friction=0.5,
            linear_damping=0.5 if dyn else 0.0, angular_damping=0.5 if dyn else 0.0, bounce=0.0, bone=bname)
        bodies[bname] = obj
        return obj

    for bname in STATIC_BODIES:
        if bname not in bones:
            continue
        b = bones[bname]
        # kept inside the skin so chains hanging from the surface don't start inside them
        if bname == '頭':
            center = Vector((0.0, spec.L['head_center_y'], (spec.L['head_top_z'] + spec.L['chin_z']) / 2))
            body(bname, 'SPHERE', (spec.L['head_half_w'] * 1.05, 0, 0), 0, 0, set(), location=center)
        else:
            r = 0.045 if bname in ('上半身', '上半身2', '下半身') else 0.03
            body(bname, 'CAPSULE', (r, max(0.01, b.length - r), 0), 0, 0, set())

    chain_groups = set(CHAIN_GROUP.values())
    n_joints = 0
    for b in bones:          # parents come before children in armature order
        grp = b.collections[0].name if len(b.collections) else ''
        if grp not in CHAIN_GROUP:
            continue
        rad = 0.018 if grp == 'Hair' else 0.025
        root_of_chain = b.parent is None or b.parent.collections[0].name != grp
        mask = chain_groups | ({0} if root_of_chain else set())   # chain roots sit on the body: no collision
        body(b.name, 'CAPSULE', (rad, max(0.01, b.length - rad), 0), 1, CHAIN_GROUP[grp], mask, mass=0.3)
        parent = b.parent
        while parent is not None and parent.name not in bodies:
            parent = parent.parent
        if parent is None:
            continue
        lim = [math.radians(a) for a in CHAIN_LIMIT[grp]]
        rot = b.matrix_local.to_euler('YXZ')
        rot.rotate_axis('X', math.pi / 2)
        FnRigidBody.setup_joint_object(
            obj=FnRigidBody.new_joint_object(ctx, jgroup, disp), name=bodies[b.name].mmd_rigid.name_j,
            name_e=bodies[b.name].mmd_rigid.name_e, location=b.head_local.copy(), rotation=rot,
            rigid_a=bodies[parent.name], rigid_b=bodies[b.name],
            maximum_location=Vector((0, 0, 0)), minimum_location=Vector((0, 0, 0)),
            maximum_rotation=Euler(lim), minimum_rotation=Euler([-a for a in lim]),
            spring_angular=Vector((0, 0, 0)), spring_linear=Vector((0, 0, 0)))
        n_joints += 1
    return len(bodies), n_joints


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='out/pmx/Levi.pmx')
    ap.add_argument('--parts', default='')
    ap.add_argument('--proxy', action='store_true')
    ap.add_argument('--fixtures', action='store_true')
    ap.add_argument('--no-physics', action='store_true')
    ap.add_argument('--save-blend', action='store_true', help='also save the MMD scene next to the PMX')
    args = ap.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
    mmd_tools()

    from rig_pose import build_scene
    arm = build_scene(args.parts, args.proxy, args.fixtures)

    out = os.path.join(ROOT, args.out)
    out_dir = os.path.dirname(out)
    os.makedirs(out_dir, exist_ok=True)
    mesh, no_edge = strip_outlines_and_join(arm)
    root = convert(arm, mesh, no_edge, out_dir)
    n_rb = n_j = 0
    if not args.no_physics:
        n_rb, n_j = add_physics(root, arm)

    bpy.context.view_layer.objects.active = root
    for o in bpy.context.view_layer.objects:
        o.select_set(o == root)
    res = bpy.ops.mmd_tools.export_pmx(filepath=out, scale=MMD_SCALE, copy_textures_mode='NONE',
                                       sort_materials=False, visible_meshes_only=False, log_level='WARNING')
    if 'FINISHED' not in res:
        raise SystemExit(f'export failed: {res}')

    summary = {
        'bones': len(arm.data.bones),
        'materials': len(mesh.data.materials),
        'mesh_vertices': len(mesh.data.vertices),
        'mesh_faces': len(mesh.data.polygons),
        'rigid_bodies': n_rb,
        'joints': n_j,
        'ik_bones': sorted({c.subtarget for pb in arm.pose.bones for c in pb.constraints if c.type == 'IK'}),
    }
    with open(os.path.splitext(out)[0] + '.json', 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)
    if args.save_blend:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.splitext(out)[0] + '_mmd.blend', compress=True)
    print('EXPORTED', out, os.path.getsize(out), json.dumps(summary, ensure_ascii=False))


main()
