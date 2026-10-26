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
     hair / skirt / sleeve chains, joints parent -> chain -> chain; hair-only static
     capsules on the real arm, torso and skirt surfaces (rig.HAIR_CAPSULES_PROP).
The rig's Blender-only hair collision (probe bones, colliders) is removed first
(rig.strip_blender_only): MMD's physics does that job.
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

from levi import rig, spec, toon  # noqa: E402

MMD_SCALE = 12.5          # MMD units per metre
TOON_SIZE = 32
GRAD_SIZE = 64
MMD_LIGHT = 154.0 / 255.0   # MMD's default light colour: lit = diffuse * light + ambient
TEX_DIR = 'tex'             # textures and toon ramps, relative to the PMX

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
    merge_shape_keys(active)
    mw = active.matrix_world.copy()
    active.parent = arm
    active.matrix_world = mw
    return active, no_edge


def merge_shape_keys(obj):
    """Joining objects that carry the same shape key (both eyelids' まばたき) leaves one
    copy per object (まばたき, まばたき.001): fold the numbered copies into the first, so
    each morph is one PMX vertex morph."""
    keys = obj.data.shape_keys
    if keys is None:
        return
    import re
    blocks = keys.key_blocks
    n = len(obj.data.vertices)
    basis = np.empty(n * 3)
    blocks[0].data.foreach_get('co', basis)
    for kb in list(blocks[1:]):
        m = re.fullmatch(r'(.+)\.\d{3}', kb.name)
        if not m or m.group(1) not in blocks:
            continue
        dst = blocks[m.group(1)]
        a, b = np.empty(n * 3), np.empty(n * 3)
        dst.data.foreach_get('co', a)
        kb.data.foreach_get('co', b)
        dst.data.foreach_set('co', a + (b - basis))
        obj.shape_key_remove(kb)


def _save_png(name, px, path):
    """Write float RGBA rows (bottom row first, Blender's order) as an 8-bit PNG,
    values taken as sRGB-encoded (no colour transform)."""
    h, w = px.shape[:2]
    img = bpy.data.images.new(name, w, h, alpha=True)
    img.colorspace_settings.name = 'Non-Color'
    img.pixels.foreach_set(np.ascontiguousarray(px, dtype=np.float32).ravel())
    img.filepath_raw = path
    img.file_format = 'PNG'
    img.save()
    bpy.data.images.remove(img)
    return path


def toon_split(key):
    """Fraction of the toon texture (from the top) that is lit. MMD reads the toon at
    v = 0.5 - 0.5 * N.L, so a lit/shade edge at the render's ramp threshold T sits at
    v = 0.5 - 0.5 * T."""
    return 0.5 - 0.5 * toon.ramp_threshold(key)


def toon_ramp(key, out_dir):
    """MMD toon texture: white where the cel render is lit, shade/base below the
    key's ramp threshold, so MMD's toon pass gives the palette shade tone."""
    pal = spec.PALETTE[key]
    base, shade = hex_rgb(pal['base']), hex_rgb(pal['shade'])
    ratio = [min(1.0, s / max(b, 1e-3)) for s, b in zip(shade, base)]
    px = np.ones((TOON_SIZE, TOON_SIZE, 4), dtype=np.float32)
    lit_rows = int(round(TOON_SIZE * toon_split(key)))
    px[:TOON_SIZE - lit_rows, :, :3] = ratio    # Blender rows go bottom -> top: the bottom is shade
    return _save_png(f'toon_{key}', px, os.path.join(out_dir, f'toon_{key}.png'))


def gradient_texture(key, grad, out_dir):
    """1-D base-colour ramp key -> grad (left -> right) for a gradient material; the
    vertices' toon_grad value becomes their U coordinate."""
    # blended in linear light like the cel material's mix (toon.srgb), then encoded
    a, b = (np.array(toon.srgb(spec.PALETTE[k]['base'])[:3]) for k in (key, grad))
    t = (np.arange(GRAD_SIZE) + 0.5) / GRAD_SIZE
    lin = a[None] * (1 - t[:, None]) + b[None] * t[:, None]
    row = np.where(lin <= 0.0031308, lin * 12.92, 1.055 * np.power(np.maximum(lin, 0.0), 1 / 2.4) - 0.055)
    px = np.ones((4, GRAD_SIZE, 4), dtype=np.float32)
    px[..., :3] = row[None]
    return _save_png(f'grad_{key}_{grad}', px, os.path.join(out_dir, f'grad_{key}_{grad}.png'))


def image_texture(mat, out_dir):
    """Save the image of a part material's own image texture (the painted face) as a
    PNG. Its alpha is a shading mask in the cel material, not transparency, so the
    PNG is written opaque."""
    # the part's own texture (mmd_tools renames it mmd_base_tex); never a toon / sphere map
    node = next((n for n in mat.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image
                 and n.name not in ('mmd_toon_tex', 'mmd_sphere_tex')), None) if mat.node_tree else None
    if node is None:
        return None
    img = node.image
    w, h = img.size
    px = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    px = px.reshape(h, w, 4)
    px[..., 3] = 1.0
    name = ''.join(c if c.isalnum() or c in '_-' else '_' for c in img.name)
    return _save_png(f'tex_{name}', px, os.path.join(out_dir, f'{name}.png'))


def gradient_uvs(mesh):
    """U = toon_grad (0..1) on every loop, V = 0.5: what gradient_texture() expects.
    Only loops of gradient materials are read through this UV, the face keeps its own."""
    me = mesh.data
    attr = me.attributes.get(toon.GRAD_ATTR)
    if attr is None or attr.domain != 'POINT':      # common.set_gradient writes per-vertex values
        return
    # the PMX's UV is the first layer (mmd_tools skips names starting with '_'), which
    # also holds the face's UVs; joining can leave another layer active
    base = [layer for layer in me.uv_layers if not layer.name.startswith('_')]
    uv = base[0] if base else me.uv_layers.new(name='UVMap')
    grad_mats = {i for i, m in enumerate(me.materials) if m and m.get('toon_gradient') and m.get('toon_std')}
    if not grad_mats:
        return
    vals = np.empty(len(me.vertices))
    attr.data.foreach_get('value', vals)
    lv = np.empty(len(me.loops), dtype=np.int64)
    me.loops.foreach_get('vertex_index', lv)
    co = np.empty(len(me.loops) * 2)
    uv.data.foreach_get('uv', co)
    co = co.reshape(-1, 2)
    for p in me.polygons:
        if p.material_index in grad_mats:
            s = slice(p.loop_start, p.loop_start + p.loop_total)
            co[s, 0] = np.clip(vals[lv[s]], 0.0, 1.0)
            co[s, 1] = 0.5
    uv.data.foreach_set('uv', co.ravel())


# ---------------------------------------------------------------- mmd conversion
def _ancestors(pb):
    p = pb.parent
    while p is not None:
        yield p
        p = p.parent


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
        pb = arm.pose.bones[name]
        mb = pb.mmd_bone
        mb.name_j, mb.name_e = jp, en
        src = pb.get('mmd_append')
        if src:                      # 回転付与 (skirt / hair follow bones), evaluated after IK
            mb.has_additional_rotation = True
            mb.additional_transform_bone = src
            mb.additional_transform_influence = float(pb.get('mmd_append_influence', 1.0))
        if src or any(pb.get('mmd_append') for pb in _ancestors(pb)):
            mb.transform_order = 1
        bone = pb.bone
        axis = bone.matrix_local.to_3x3()
        if pb.get('mmd_fixed_axis'):  # 捩 bones turn only about their own length
            mb.enabled_fixed_axis = True
            mb.fixed_axis = axis.col[1].xzy
        if bone.collections and bone.collections[0].name == 'Fingers':   # curl about local X
            mb.enabled_local_axes = True
            mb.local_axis_x = axis.col[0].xzy
            mb.local_axis_z = axis.col[2].xzy

    for t in 'LR':
        # the rig locks the thigh's twist for Blender's IK solver only; in the PMX the
        # 足 link stays unlimited like the standard model's (a muted custom limit with
        # no axes is mmd_tools' way to say so), the knee keeps its limit
        ik = arm.pose.bones.get(f'足ＩＫ.{t}')
        if ik is not None and 'mmd_ik_limit_custom1' not in ik.constraints:
            c = ik.constraints.new('LIMIT_ROTATION')
            c.name = 'mmd_ik_limit_custom1'
            c.mute = True
    write_materials(mesh, no_edge, out_dir)
    setup_display_frames(root, arm)
    add_vertex_morphs(root, mesh)
    return root


# shape key -> (PMX morph panel, English name) for the standard MMD facial morphs; any
# other key goes to the 'other' panel under its own name
MORPH_INFO = {
    'まばたき': ('EYE', 'Blink'), '笑い': ('EYE', 'Smile'), 'ウィンク': ('EYE', 'Wink'),
    'ウィンク右': ('EYE', 'Wink_R'), 'ウィンク２': ('EYE', 'Wink 2'), 'ｳｨﾝｸ２右': ('EYE', 'Wink 2_R'),
    'はぅ': ('EYE', 'Close><'), 'なごみ': ('EYE', 'Calm'), 'びっくり': ('EYE', 'Surprised'),
    'じと目': ('EYE', 'Slant'), 'あ': ('MOUTH', 'a'), 'い': ('MOUTH', 'i'), 'う': ('MOUTH', 'u'),
    'え': ('MOUTH', 'e'), 'お': ('MOUTH', 'o'), 'ん': ('MOUTH', 'n'), 'ワ': ('MOUTH', 'Wa'),
    'ω': ('MOUTH', 'Omega'), '∧': ('MOUTH', 'Mouth_Hu'), 'にやり': ('MOUTH', 'Grin'),
    'ぺろっ': ('MOUTH', 'Tongue'), '真面目': ('EYEBROW', 'Serious'), '困る': ('EYEBROW', 'Trouble'),
    'にこり': ('EYEBROW', 'Smily'), '怒り': ('EYEBROW', 'Angry'), '上': ('EYEBROW', 'Up'),
    '下': ('EYEBROW', 'Down'),
}
# PMX panel numbers (pmx morph.category) of mmd_tools' category names
PANEL_NUM = {'SYSTEM': 0, 'EYEBROW': 1, 'EYE': 2, 'MOUTH': 3, 'OTHER': 4}


def add_vertex_morphs(root, mesh):
    """Every shape key of the joined mesh (parts' MMD morphs, e.g. the head's まばたき) as a
    PMX vertex morph in its panel, listed in the 表情 display frame."""
    keys = mesh.data.shape_keys
    if keys is None:
        return []
    names = [kb.name for kb in keys.key_blocks[1:] if not kb.name.startswith('_')]
    frame = next((f for f in root.mmd_root.display_item_frames if f.name == '表情'), None)
    for n in names:
        cat, en = MORPH_INFO.get(n, ('OTHER', n))
        vm = next((m for m in root.mmd_root.vertex_morphs if m.name == n), None)   # convert may list it already
        vm = vm or root.mmd_root.vertex_morphs.add()
        vm.name, vm.name_e, vm.category = n, en, cat
        if frame is not None and not any(it.type == 'MORPH' and it.name == n for it in frame.data):
            it = frame.data.add()
            it.type, it.name, it.morph_type = 'MORPH', n, 'vertex_morphs'
    return names


def write_materials(mesh, no_edge, out_dir):
    """Per material: palette colours set so MMD's lit colour (diffuse x light + ambient,
    at MMD's default light) is exactly the palette base; a toon ramp that switches to the
    palette shade at the render's ramp threshold; no sphere map (the cel look has no
    highlight); edge in the palette line colour. Image textures (the painted face) and
    gradient materials (hair -> hair_tip) get PNG textures. Everything is written under
    <out_dir>/tex and referenced by relative paths, so the folder can be moved."""
    from importlib import import_module
    FnMaterial = import_module(mmd_tools().__name__ + '.core.material').FnMaterial
    tex_dir = os.path.join(out_dir, TEX_DIR)
    os.makedirs(tex_dir, exist_ok=True)
    gradient_uvs(mesh)
    ramps, grads = {}, {}
    for mat in mesh.data.materials:
        key = mat.get('toon_key', 'dress')
        pal = spec.PALETTE[key]
        mm = mat.mmd_material
        mm.name_j = MAT_JP.get(key, key) + ('' if mat.name == f'toon_{key}' else '_' + mat.name.split('__')[-1])
        mm.name_e = mat.name
        grad = mat.get('toon_gradient') if mat.get('toon_std') else None
        tex = image_texture(mat, tex_dir) if not grad else None
        if grad in spec.PALETTE:
            tex = grads.get((key, grad)) or grads.setdefault((key, grad), gradient_texture(key, grad, tex_dir))
        fn = FnMaterial(mat)
        if tex:
            fn.create_texture(tex)
            mm.texture_rel_path = f'{TEX_DIR}/{os.path.basename(tex)}'
            base = (1.0, 1.0, 1.0)       # the texture carries the colour
        else:
            if fn.get_texture() is not None:
                fn.remove_texture()
            base = hex_rgb(pal['base'])
        mm.diffuse_color = base
        mm.ambient_color = [c * (1.0 - MMD_LIGHT) for c in base]
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
        mm.sphere_texture_type = '0'
        path = ramps.get(key) or ramps.setdefault(key, toon_ramp(key, tex_dir))
        mm.is_shared_toon_texture = False
        mm.toon_texture_rel_path = f'{TEX_DIR}/{os.path.basename(path)}'
        mm.toon_texture = path


# display frames (PMX 表示枠): (frame name, English name, bone-name stems in order)
FRAMES = (
    ('センター', 'Center', ('センター', 'グルーブ')),
    ('ＩＫ', 'IK', ('足ＩＫ', 'つま先ＩＫ')),
    ('体(上)', 'Upper Body', ('上半身', '上半身2', '首', '頭', '両目', '目')),
    ('腕', 'Arms', ('肩', '腕', '腕捩', 'ひじ', '手捩', '手首')),
    ('指', 'Fingers', tuple(f'{f}{n}' for f in ('親指',) for n in '０１２') +
     tuple(f'{f}{n}' for f in ('人指', '中指', '薬指', '小指') for n in '１２３')),
    ('体(下)', 'Lower Body', ('腰', '下半身')),
    ('足', 'Legs', ('足', 'ひざ', '足首')),
)
CHAIN_FRAMES = (('髪', 'Hair', 'Hair'), ('スカート', 'Skirt', 'Skirt'), ('袖', 'Sleeves', 'Sleeve'))


def frame_bones(arm):
    """[(frame jp, frame en, [blender bone names])]: every bone an animator keys.
    Helper bones driven by 回転付与 (補助 / 追従) and the つま先 IK targets are left out
    (and hidden, as in the standard model)."""
    names = [b.name for b in arm.data.bones]
    out = []
    for jp, en, stems in FRAMES:
        sel = [n for st in stems for n in names if n.split('.')[0] == st]
        out.append((jp, en, sel))
    for jp, en, group in CHAIN_FRAMES:
        sel = [b.name for b in arm.data.bones if b.collections and b.collections[0].name == group]
        out.append((jp, en, sel))
    return [f for f in out if f[2]]


def is_helper(pb):
    """Bones that only follow others (回転付与 helpers, the hair / skirt / sleeve follow roots,
    the deforming arm 腕D under the shoulder shrug)."""
    groups = {c.name for c in pb.bone.collections}
    return ((bool(pb.get('mmd_append')) and not pb.bone.use_deform) or '補助' in pb.name or bool(pb.get('mmd_helper'))
            or bool(groups & {'HairFollow', 'SkirtFollow'}))


def setup_display_frames(root, arm):
    from importlib import import_module
    FnModel = import_module(mmd_tools().__name__ + '.core.model').FnModel
    FnModel.initalize_display_item_frames(root, reset=True)
    frames = root.mmd_root.display_item_frames
    for jp, en, bones in frame_bones(arm):
        fr = frames.add()
        fr.name, fr.name_e = jp, en
        for n in bones:
            it = fr.data.add()
            it.type, it.name = 'BONE', n
    for pb in arm.pose.bones:       # helpers follow other bones, つま先 is the toe IK's target: not for the animator
        if not pb.is_mmd_shadow_bone and (is_helper(pb) or pb.name.split('.')[0] == 'つま先'):
            pb.mmd_bone.is_controllable = False
            pb.bone.hide = True


# ---------------------------------------------------------------- physics
# bone-following bodies the hair / skirt / sleeve chains collide with (group 0)
STATIC_BODIES = ['頭', '首', '上半身', '上半身2', '下半身'] + \
    [f'{n}.{t}' for n in ('足', 'ひざ', '腕', 'ひじ') for t in 'LR']
# the hands (group HAND_GROUP) push swinging hair and skirt off them; the sleeve drapes,
# which hang right next to the wrists at rest, ignore them
HAND_BODIES = [f'手首.{t}' for t in 'LR']
HAND_GROUP, HAND_RADIUS = 4, 0.022
# Hair (round 7): the head body has its own group (HEAD_GROUP; the other chains still
# collide with it as before), so a hair body lying inside it at rest can ignore the head
# alone; every hair body ignores the static groups it already overlaps at rest (it would
# be shot out on the first frame). HAIR_ONLY_GROUP holds rig.HAIR_CAPSULES_PROP's capsules
# fitted to the real surfaces (upper arms, forearms, hands with their sleeves, chest and
# waist with the bodice, the skirt top behind the hips), which only hair collides with:
# the hair drapes over her shoulders, back, arms and skirt instead of sinking to the thin
# bone capsules, and nothing else changes.
HEAD_GROUP = 5
HAIR_ONLY_GROUP = 6
CHAIN_GROUP = {'Hair': 1, 'Skirt': 2, 'Sleeve': 3}
# the right sleeve's drapes have a group of their own, so the two sleeves collide (arms
# folded or crossed: the bags press against each other instead of passing through)
SLEEVE_R_GROUP = 7   # 5 is HEAD_GROUP, 6 HAIR_ONLY_GROUP
CHAIN_LIMIT = {'Hair': (20, 8, 20), 'Skirt': (30, 8, 15), 'Sleeve': (25, 8, 25)}   # degrees x, y, z


def _seg_seg_dist(p1, q1, p2, q2):
    """Closest distance between segments p1-q1 and p2-q2 (sampled; capsules are short)."""
    t = np.linspace(0.0, 1.0, 9)
    a = p1[None] + t[:, None] * (q1 - p1)[None]
    b = p2[None] + t[:, None] * (q2 - p2)[None]
    return float(np.linalg.norm(a[:, None] - b[None], axis=2).min())


CHAIN_RADIUS = {'Hair': 0.018, 'Skirt': 0.025, 'Sleeve': 0.025}
CHAIN_CLEARANCE = 0.005     # rest gap (m) two chain groups need before they may collide
# Leg bodies about as thick as the legs (the thigh is 5-7 cm round, the calf ~4.5 cm), so
# the skirt and petticoat chain bodies (CHAIN_RADIUS) stop at the skin instead of sinking
# 3-4 cm into the thigh as they did against 3 cm capsules. Each is held CHAIN_CLEARANCE
# off every dynamic chain body at rest (leg_radius), so nothing starts inside a leg.
LEG_RADIUS = {'足': 0.055, 'ひざ': 0.04}
LEG_RADIUS_MIN = 0.03


def _chain_root(b, grp):
    """Whether chain bone b (collection grp) is the root of its chain: the nearest chain
    bone above it, skipping the skirt follow bones between segments, is not in grp."""
    up = b.parent
    while up is not None and up.collections and up.collections[0].name == 'SkirtFollow':
        up = up.parent
    return up is None or not up.collections or up.collections[0].name != grp


def leg_radius(bones, leg, want):
    """Radius for the leg body on bone `leg`: `want`, less whatever would bring it within
    CHAIN_CLEARANCE of a chain body that collides with it (below its chain's root) at
    rest; at least LEG_RADIUS_MIN. Returns (radius, the chain bone that limited it or '')."""
    h, t = np.array(leg.head_local), np.array(leg.tail_local)
    ax = (t - h) / max(np.linalg.norm(t - h), 1e-9)
    r, by = want, ''
    for b in bones:
        grp = b.collections[0].name if len(b.collections) else ''
        if grp not in CHAIN_GROUP or _chain_root(b, grp):
            continue
        # a capsule reaches half its radius past each end of its bone (mmd height = length
        # - radius); the leg's is taken at the full `want`, the larger
        p, q = np.array(b.head_local), np.array(b.tail_local)
        u = (q - p) / max(np.linalg.norm(q - p), 1e-9) * CHAIN_RADIUS[grp] / 2
        d = _seg_seg_dist(h - ax * want / 2, t + ax * want / 2, p - u, q + u)
        if d - CHAIN_RADIUS[grp] - CHAIN_CLEARANCE < r:
            r, by = d - CHAIN_RADIUS[grp] - CHAIN_CLEARANCE, b.name
    return max(LEG_RADIUS_MIN, r), by


def chain_groups_overlapping(bones):
    """{(group a, group b)} pairs of chain collision groups whose bodies overlap (or nearly)
    somewhere at rest: those keep ignoring each other."""
    segs = {}
    for b in bones:
        grp = b.collections[0].name if len(b.collections) else ''
        if grp in CHAIN_GROUP:
            segs.setdefault(grp, []).append((np.array(b.head_local), np.array(b.tail_local)))
    out = set()
    names = sorted(segs)
    for i, ga in enumerate(names):
        for gb in names[i + 1:]:
            lim = CHAIN_RADIUS[ga] + CHAIN_RADIUS[gb] + CHAIN_CLEARANCE
            hit = any(_seg_seg_dist(p1, q1, p2, q2) < lim for p1, q1 in segs[ga] for p2, q2 in segs[gb])
            if hit:
                out |= {(CHAIN_GROUP[ga], CHAIN_GROUP[gb]), (CHAIN_GROUP[gb], CHAIN_GROUP[ga])}
            print(f'physics: {ga} / {gb} ' + ('overlap at rest: no collision' if hit else 'collide'))
    return out


def _rest_overlaps(b, rad, geo, mask):
    """Static groups (not already in `mask`) with a body that the chain capsule of bone `b`
    (radius rad) touches at rest: that chain body must ignore them."""
    d = (b.tail_local - b.head_local).normalized()
    mid = (b.head_local + b.tail_local) / 2
    half = d * max(0.01, b.length - rad) / 2
    p, q = np.array(mid - half), np.array(mid + half)
    return {g for _n, a, c, r, g in geo if g not in mask and _seg_seg_dist(p, q, a, c) < rad + r}


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
    geo = []      # (bone, segment a, segment b, radius, group) of every static body, rest

    def body(bname, shape, size, dyn, group, mask, mass=1.0, location=None, axis=None, name=None):
        b = bones[bname]
        mb = arm.pose.bones[bname].mmd_bone
        m = b.matrix_local.to_3x3() if axis is None else Vector(axis).to_track_quat('Y', 'Z').to_matrix()
        rot = m.to_euler('YXZ')
        rot.rotate_axis('X', math.pi / 2)
        loc = location if location is not None else (b.head_local + b.tail_local) / 2
        obj = FnRigidBody.setup_rigid_body_object(
            obj=FnRigidBody.new_rigid_body_object(ctx, rgroup), shape_type=rb.shapeType(shape),
            location=loc, rotation=rot, size=Vector(size), dynamics_type=dyn,
            name=name[0] if name else mb.name_j, name_e=name[1] if name else mb.name_e, collision_group_number=group,
            collision_group_mask=[i in mask for i in range(16)], mass=mass, friction=0.5,
            linear_damping=0.5 if dyn else 0.0, angular_damping=0.5 if dyn else 0.0, bounce=0.0, bone=bname)
        if not name:
            bodies[bname] = obj
        if not dyn:
            half = m.col[1] * (size[1] / 2 if shape == 'CAPSULE' else 0.0)
            geo.append((bname, np.array(loc - half), np.array(loc + half), float(size[0]), group))
        return obj

    for bname in STATIC_BODIES:
        # with the shoulder shrug 腕 is only the keyed input; the arm body follows 腕D
        if bname.startswith('腕.'):
            bname = rig.deform_arm(bones.keys(), bname[2:])
        if bname not in bones:
            continue
        b = bones[bname]
        # kept inside the skin so chains hanging from the surface don't start inside them
        if bname == '頭':
            center = Vector((0.0, spec.L['head_center_y'], (spec.L['head_top_z'] + spec.L['chin_z']) / 2))
            body(bname, 'SPHERE', (spec.L['head_half_w'] * 1.05, 0, 0), 0, HEAD_GROUP, set(), location=center)
        else:
            r = 0.045 if bname in ('上半身', '上半身2', '下半身') else 0.03
            if bname.split('.')[0] in LEG_RADIUS:
                r, by = leg_radius(bones, b, LEG_RADIUS[bname.split('.')[0]])
                print(f'physics: leg body {bname} radius {r:.3f}' + (f' (held clear of {by})' if by else ''))
            body(bname, 'CAPSULE', (r, max(0.01, b.length - r), 0), 0, 0, set())
    for bname in HAND_BODIES:
        if bname in bones:
            b = bones[bname]
            body(bname, 'CAPSULE', (HAND_RADIUS, max(0.01, b.length - HAND_RADIUS), 0), 0, HAND_GROUP, set())
    for cap in json.loads(arm.get(rig.HAIR_CAPSULES_PROP, '[]')):
        if cap['bone'] not in bones:
            continue
        a, b = Vector(cap['a']), Vector(cap['b'])
        jp = arm.pose.bones[cap['bone']].mmd_bone.name_j
        body(cap['bone'], 'CAPSULE', (cap['r'], max(0.005, (b - a).length), 0), 0, HAIR_ONLY_GROUP,
             set(range(16)) - {CHAIN_GROUP['Hair']}, location=(a + b) / 2,
             axis=(b - a) if (b - a).length > 1e-6 else Vector((0, 0, 1)),
             name=(f'{jp}髪当{cap["name"]}', f'HairCollider_{cap["name"]}'))
    if rig.HAIR_ROOT in bones:
        # the back hair hangs from the head-follow bone (rig.HAIR_FOLLOW of the head's turn,
        # as in Blender): a small bone-following body there anchors their joints; it collides with nothing
        body(rig.HAIR_ROOT, 'SPHERE', (0.01, 0, 0), 0, 0, set(range(16)), location=bones[rig.HAIR_ROOT].head_local)
        geo.pop()     # (collides with nothing)

    chain_groups = set(CHAIN_GROUP.values())
    overlapping = chain_groups_overlapping(bones)
    n_joints = 0
    hair_ignores = {}
    for b in bones:          # parents come before children in armature order
        grp = b.collections[0].name if len(b.collections) else ''
        if grp not in CHAIN_GROUP:
            continue
        rad = CHAIN_RADIUS[grp]
        root_of_chain = _chain_root(b, grp)
        # a chain ignores its own group and any chain group its bodies already overlap at
        # rest (they would explode apart on the first frame); hair, skirt and sleeves that
        # are clear of each other collide. Chain roots sit on the body: no collision there.
        mine = CHAIN_GROUP[grp]
        mask = {mine} | {g for g in chain_groups if (mine, g) in overlapping} | ({0, HAND_GROUP, HEAD_GROUP} if root_of_chain else set())
        if grp != 'Sleeve' and CHAIN_GROUP['Sleeve'] in mask:   # a chain that ignores the sleeves ignores both
            mask.add(SLEEVE_R_GROUP)
        if grp == 'Sleeve':
            mask |= {HAND_GROUP}
            if b.name.endswith('.R'):
                mask = (mask - {mine}) | {SLEEVE_R_GROUP}
                mine = SLEEVE_R_GROUP
        if grp == 'Hair':
            # (a PMX mask is per group, so a body touching one static body at rest ignores its
            # whole group; export prints how many do: none on the current model, the capsules
            # are fitted inside the surfaces the hair lies on)
            extra = _rest_overlaps(b, rad, geo, mask)
            mask |= extra
            for g in extra:
                hair_ignores[g] = hair_ignores.get(g, 0) + 1
            hair_ignores['bodies'] = hair_ignores.get('bodies', 0) + 1
        # skirt chain roots follow the bone (their follow parents add the thighs' rotation);
        # everything below them is simulated
        dyn = 0 if grp == 'Skirt' and root_of_chain else 1
        body(b.name, 'CAPSULE', (rad, max(0.01, b.length - rad), 0), dyn, mine, mask, mass=0.3)
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
    print(f'physics: {hair_ignores.get("bodies", 0)} hair bodies; ignoring at rest-overlap: '
          + ', '.join(f'group {g}: {n}' for g, n in sorted((k, v) for k, v in hair_ignores.items() if k != 'bodies'))
          + f'; {sum(1 for g in geo if g[4] == HAIR_ONLY_GROUP)} hair-only colliders')
    return len(bodies) + sum(1 for g in geo if g[4] == HAIR_ONLY_GROUP), n_joints


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
    # the hair's Blender-only collision probes and colliders: MMD physics does that job
    n_strip = rig.strip_blender_only(arm)
    print(f'export: removed {n_strip} Blender-only hair collision bones')

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
        'bones': sum(1 for pb in arm.pose.bones if not pb.is_mmd_shadow_bone),   # mmd_tools adds shadow bones for 付与
        'materials': len(mesh.data.materials),
        'vertex_morphs': [m.name for m in root.mmd_root.vertex_morphs],
        'morph_panels': {m.name: PANEL_NUM.get(m.category, 4) for m in root.mmd_root.vertex_morphs},
        'mesh_vertices': len(mesh.data.vertices),
        'mesh_faces': len(mesh.data.polygons),
        'rigid_bodies': n_rb,
        'joints': n_j,
        'append_bones': sum(1 for pb in arm.pose.bones if pb.mmd_bone.has_additional_rotation),
        'fixed_axis_bones': sum(1 for pb in arm.pose.bones if pb.mmd_bone.enabled_fixed_axis),
        'local_axes_bones': sum(1 for pb in arm.pose.bones if pb.mmd_bone.enabled_local_axes),
        'ik_bones': sorted({c.subtarget for pb in arm.pose.bones for c in pb.constraints if c.type == 'IK'}),
        'textured_materials': sorted(m.mmd_material.name_j for m in mesh.data.materials
                                     if m.mmd_material.texture_rel_path),
        'display_frames': [f.name for f in root.mmd_root.display_item_frames],
        'hidden_helpers': sum(1 for pb in arm.pose.bones if not pb.is_mmd_shadow_bone and is_helper(pb)),
    }
    with open(os.path.splitext(out)[0] + '.json', 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)
    if args.save_blend:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.splitext(out)[0] + '_mmd.blend', compress=True)
    print('EXPORTED', out, os.path.getsize(out), json.dumps(summary, ensure_ascii=False))


main()
