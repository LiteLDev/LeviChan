"""Re-import an exported PMX with mmd_tools and check nothing was lost. Exit 1 on failure.

    blender -b -P tools/pmx_reimport.py -- [--pmx out/pmx/Levi.pmx] [--save out/pmx/reimport.blend] [--no-vmd]

Compares against <pmx>.json written by export_pmx.py: bone, material, rigid body
and joint counts; that every bone has a Japanese and an English name; that the
leg/toe IK bones are IK in the file; that vertex count in Blender after import
equals the PMX vertex count and every vertex is weighted. Saves a .blend that
render.py can render.

MMD readiness: the standard bone names motions bind to (センター ... 足ＩＫ, 捩, 親指０);
every animator-facing bone in a display frame; the knee IK links limited to forward
bending; texture / toon files present next to the PMX under relative paths, no sphere
maps, a textured face; 回転付与 followers turning by their share; the morph count.
VMD round trip: a procedural walk keyed on the standard bones is exported with
mmd_tools, cleared, imported back and compared bone by bone, and the knees must
bend forward in every sampled frame (<save>_walk.blend keeps it, at Blender frame 9 = VMD frame 8).
"""
import argparse
import importlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402


def check_append(arm, errors, source='左足', deg=40.0):
    """Turn bone `source` and check every bone that appends its rotation (回転付与) turns
    by its influence times as much in the re-imported model."""
    import math
    from mathutils import Matrix, Quaternion, Vector
    pbs = [pb for pb in arm.pose.bones if not pb.is_mmd_shadow_bone]
    leg = next((pb for pb in pbs if pb.mmd_bone.name_j == source), None)
    users = [pb for pb in pbs if pb.mmd_bone.has_additional_rotation and leg is not None
             and pb.mmd_bone.additional_transform_bone == leg.name]
    if leg is None or not users:
        print(f'append check   no bones append {source}')
        return
    def own(pb):       # rotation relative to the parent: followers may hang from followers
        m = pb.parent.matrix.inverted() @ pb.matrix if pb.parent else pb.matrix
        return m.to_quaternion()
    rest = {pb.name: own(pb) for pb in users}
    ik = [c for pb in arm.pose.bones for c in pb.constraints if c.type == 'IK' and not c.mute]
    for c in ik:                 # FK test: the leg IK would otherwise hold the thigh in place
        c.mute = True
    leg.rotation_mode = 'QUATERNION'
    leg.rotation_quaternion = Quaternion((1, 0, 0), math.radians(deg))
    bpy.context.view_layer.update()
    # the source's turn axis in world space (its parent stays at rest in this FK test)
    src_axis = (leg.bone.matrix_local.to_3x3() @ Vector((1, 0, 0))).normalized()
    worst = 0.0
    for pb in users:
        d = own(pb) @ rest[pb.name].inverted()        # turn since rest, in the parent's frame
        got = math.degrees(d.angle)
        if got > 1e-3:
            # signed by the turn axis (in world space) against the source's, so a negative
            # share (cancel bones) must turn the other way
            par = pb.parent.matrix.to_3x3() if pb.parent else Matrix.Identity(3)
            if (par @ d.axis).dot(src_axis) < 0:
                got = -got
        want = deg * pb.mmd_bone.additional_transform_influence
        worst = max(worst, abs(got - want))
    print(f'append check   {len(users)} bones follow {source}, worst error {worst:.2f} deg')
    if worst > 1.0:
        errors.append(f'回転付与 of {source} off by {worst:.1f} deg after reimport')
    leg.rotation_quaternion = Quaternion()
    for c in ik:
        c.mute = False
    bpy.context.view_layer.update()




def check_morphs(pmx, want, errors, panels=None):
    """Every exported vertex morph (e.g. まばたき) is in the PMX, moves some vertices, and is
    listed in a display frame so MMD's facial panel shows it."""
    got = {m.name: m for m in pmx.morphs}
    shown = {i for d in pmx.display for t, i in d.data if t == 1}     # type 1: morph items
    for n in want:
        m = got.get(n)
        if m is None:
            errors.append(f'vertex morph {n} missing after export')
            continue
        moved = sum(1 for o in m.offsets if max(abs(c) for c in o.offset) > 1e-6)
        idx = pmx.morphs.index(m)
        print(f'morph {n}: {moved} vertices move, panel {m.category}')
        if not moved:
            errors.append(f'vertex morph {n} moves no vertices')
        if idx not in shown:
            errors.append(f'vertex morph {n} is in no display frame')
        if panels and n in panels and m.category != panels[n]:
            errors.append(f'vertex morph {n} in panel {m.category}, expected {panels[n]}')
    # independently of the export's own record: every standard name sits in its MORPH_INFO
    # panel with its English name, and a model with the head's blink has the whole set
    MORPH_INFO, PANEL_NUM = _export_tables('MORPH_INFO', 'PANEL_NUM')
    for n, m in got.items():
        if n in MORPH_INFO:
            cat, en = MORPH_INFO[n]
            if m.category != PANEL_NUM[cat]:
                errors.append(f'morph {n} in panel {m.category}, MORPH_INFO says {cat} ({PANEL_NUM[cat]})')
            if m.name_e != en:
                errors.append(f'morph {n} English name {m.name_e!r}, MORPH_INFO says {en!r}')
    if 'まばたき' in got:
        if ROOT not in sys.path:
            sys.path.insert(0, ROOT)
        from levi.parts import head       # the expression set the head ships
        missing = [n for n in head.ALL_MORPHS if n not in got]
        if missing:
            errors.append(f'head morphs missing: {" ".join(missing)}')
    panels_used = {}
    for m in pmx.morphs:
        panels_used[m.category] = panels_used.get(m.category, 0) + 1
    print('morph panels (1 brow, 2 eye, 3 mouth, 4 other): '
          + ', '.join(f'{k}: {v}' for k, v in sorted(panels_used.items())))


def _export_tables(*names):
    """Literal tables of export_pmx.py (read from its source: importing it runs the export)."""
    import ast
    with open(os.path.join(ROOT, 'export_pmx.py'), encoding='utf-8') as f:
        tree = ast.parse(f.read())
    found = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and getattr(node.targets[0], 'id', '') in names:
            found[node.targets[0].id] = ast.literal_eval(node.value)
    return tuple(found[n] for n in names)


def check_names(pmx, errors):
    """MMD motions bind by bone name: every standard bone must exist under its exact
    PMX name, and names must be unique."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    standard = importlib.import_module('levi.rig').STANDARD_PMX_BONES
    names = [b.name for b in pmx.bones]
    missing = [n for n in standard if n not in names]
    dup = sorted({n for n in names if names.count(n) > 1})
    print(f'standard bones {len(standard) - len(missing)}/{len(standard)} present')
    if missing:
        errors.append(f'standard bones missing: {missing}')
    if dup:
        errors.append(f'duplicate bone names: {dup}')


def check_frames(pmx, errors):
    """Every bone an animator can select (visible and controllable) is in a display frame."""
    shown = {i for d in pmx.display for t, i in d.data if t == 0}
    loose = [b.name for i, b in enumerate(pmx.bones) if b.visible and b.isControllable and i not in shown]
    print(f'display frames {[d.name for d in pmx.display]}, {len(shown)} bones shown')
    if loose:
        errors.append(f'{len(loose)} controllable bones in no display frame: {loose[:8]}')
    if not pmx.display or pmx.display[0].name != 'Root':
        errors.append('first display frame is not Root')


def check_ik_limits(pmx, errors):
    """The leg IK may only bend the knees forward: the ひざ link of each 足ＩＫ carries the
    standard limit (about X only, never past straight)."""
    import math
    for side in '左右':
        ik = next((b for b in pmx.bones if b.name == f'{side}足ＩＫ'), None)
        if ik is None or not ik.ik_links:
            errors.append(f'{side}足ＩＫ has no IK links')
            continue
        knee = ik.ik_links[0]
        name = pmx.bones[knee.target].name
        lo, hi = knee.minimumAngle, knee.maximumAngle
        print(f'IK limit {name}: min {None if lo is None else [round(math.degrees(a), 1) for a in lo]} '
              f'max {None if hi is None else [round(math.degrees(a), 1) for a in hi]}')
        if name != f'{side}ひざ' or lo is None or hi is None:
            errors.append(f'{side}足ＩＫ: first link {name} has no angle limit')
            continue
        # MMD axes: a forward knee bend is a negative turn about X
        if hi[0] > 0.0 or lo[0] < -math.pi - 1e-3 or max(abs(lo[1]), abs(lo[2]), abs(hi[1]), abs(hi[2])) > 1e-4:
            errors.append(f'{name}: IK limit allows reverse or sideways bending')


def check_textures(pmx, path, errors):
    """Texture and toon files sit next to the PMX under relative paths; no sphere maps;
    the face is textured."""
    base = os.path.dirname(path)
    for t in pmx.textures:
        p = getattr(t, 'raw_path', t.path).replace('\\', '/')
        if os.path.isabs(p) or p.startswith('..') or ':' in p:
            errors.append(f'texture path not relative to the PMX: {p}')
        elif not os.path.isfile(os.path.join(base, p)):
            errors.append(f'texture file missing: {p}')
    textured = []
    for m in pmx.materials:
        if m.texture >= 0:
            textured.append(m.name)
        if m.is_shared_toon_texture or m.toon_texture < 0:
            errors.append(f'material {m.name}: no own toon ramp')
        if m.sphere_texture_mode != 0:
            errors.append(f'material {m.name}: sphere map on')
    print(f'textures {len(pmx.textures)}: {[getattr(t, "raw_path", t.path) for t in pmx.textures if "toon_" not in t.path]}; '
          f'textured materials {textured}')
    if not any('face' in m.name_e for m in pmx.materials if m.texture >= 0):
        errors.append('the face material has no texture')


WALK_FRAMES = 32
WALK_START = 1      # mmd_tools maps Blender frame 1 to VMD frame 0
WALK_CHECK = (0, 4, 8, 12, 16, 20, 24, 28)
WALK_BONES = ('頭', '左手首', '右手首', '左足首', '右足首', '左ひざ', '右ひざ', '上半身2')


def _pb(arm, jp):
    return next(pb for pb in arm.pose.bones if not pb.is_mmd_shadow_bone and pb.mmd_bone.name_j == jp)


def key_walk(arm):
    """A procedural walk cycle keyed on the standard bones only (センター, 足ＩＫ, 腕, ひじ,
    上半身, 頭), as a dance/walk VMD would drive them."""
    import math
    from mathutils import Quaternion, Vector
    sc = bpy.context.scene
    rest = {}
    for jp in ('センター', '左足ＩＫ', '右足ＩＫ'):
        rest[jp] = _pb(arm, jp).bone.matrix_local.copy()

    def rot(jp, axis, deg):
        pb = _pb(arm, jp)
        pb.rotation_mode = 'QUATERNION'
        local = (pb.bone.matrix_local.to_3x3().inverted() @ Vector(axis)).normalized()
        pb.rotation_quaternion = Quaternion(local, math.radians(deg))
        pb.keyframe_insert('rotation_quaternion')

    for f in range(0, WALK_FRAMES + 1, 2):
        sc.frame_set(f + WALK_START)
        ph = 2 * math.pi * f / WALK_FRAMES
        for jp, sgn in (('左足ＩＫ', 1), ('右足ＩＫ', -1)):
            pb = _pb(arm, jp)
            m = rest[jp].copy()
            m.translation += Vector((0.0, -0.13 * sgn * math.sin(ph), 0.05 * max(0.0, sgn * math.cos(ph))))
            pb.matrix = m
            pb.keyframe_insert('location')
        c = _pb(arm, 'センター')
        m = rest['センター'].copy()
        m.translation += Vector((0.0, 0.0, -0.025 + 0.012 * math.cos(2 * ph)))
        c.matrix = m
        c.keyframe_insert('location')
        rot('上半身', (0, 0, 1), 7 * math.sin(ph))
        rot('頭', (1, 0, 0), 4 * math.cos(2 * ph))
        for jp, sgn in (('左腕', 1), ('右腕', -1)):
            rot(jp, (1, 0, 0), 22 * sgn * math.sin(ph))
        for jp in ('左ひじ', '右ひじ'):
            rot(jp, (1, 0, 0), 15 + 10 * math.sin(ph) ** 2)
        bpy.context.view_layer.update()


def sample_walk(arm):
    sc = bpy.context.scene
    out = {}
    for f in WALK_CHECK:
        sc.frame_set(f + WALK_START)
        bpy.context.view_layer.update()
        out[f] = {jp: _pb(arm, jp).head.copy() for jp in WALK_BONES}
        out[f]['knee'] = [_knee_bend(arm, s) for s in '左右']
    return out


def _knee_bend(arm, side):
    """Knee bend (deg) between thigh and shin, negative when the knee points backward
    (hyperextended): the knee must lie in front (-Y, the way she faces) of the
    hip-ankle line whenever the leg is bent."""
    import math
    hip, knee, ankle = (_pb(arm, f'{side}{n}').head for n in ('足', 'ひざ', '足首'))
    ang = math.degrees((knee - hip).angle(ankle - knee))
    d = ankle - hip
    t = (knee - hip).dot(d) / max(d.length_squared, 1e-12)
    off = knee - (hip + d * t)
    return ang if off.y <= 1e-4 or ang < 1.0 else -ang


def vmd_round_trip(root, arm, out_dir, errors):
    """Key a walk on the re-imported PMX, export it as VMD with mmd_tools, clear it, import
    the VMD back and compare bone positions frame by frame; the knees must bend forward
    throughout."""
    vmd = os.path.join(out_dir, 'walk_test.vmd')
    key_walk(arm)
    want = sample_walk(arm)
    for o in bpy.context.view_layer.objects:
        o.select_set(o == arm)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.mmd_tools.export_vmd(filepath=vmd, scale=12.5, log_level='WARNING')
    arm.animation_data_clear()
    for pb in arm.pose.bones:
        pb.matrix_basis.identity()
    bpy.context.scene.frame_set(WALK_START)   # the importer places the motion relative to the current frame
    bpy.ops.mmd_tools.import_vmd(filepath=vmd, scale=1.0 / 12.5, bone_mapper='PMX', log_level='WARNING')
    got = sample_walk(arm)
    worst, where, knee_min = 0.0, '', 180.0
    for f in WALK_CHECK:
        for jp in WALK_BONES:
            e = (want[f][jp] - got[f][jp]).length
            if os.environ.get('LEVI_DEBUG_VMD'):
                print('VMDDBG', f, jp, round(e * 1000, 1))
            if e > worst:
                worst, where = e, f'{jp} @ frame {f}'
        knee_min = min(knee_min, *got[f]['knee'], *want[f]['knee'])
    print(f'VMD round trip {os.path.basename(vmd)}: {len(WALK_CHECK)} frames, worst bone offset '
          f'{worst * 1000:.2f} mm ({where}), least knee bend {knee_min:.1f} deg')
    if worst > 0.002:
        errors.append(f'VMD round trip moves bones by {worst * 1000:.1f} mm')
    if knee_min < -0.5:
        errors.append(f'knee hyperextends ({knee_min:.1f} deg) in the walk')
    bpy.context.scene.frame_set(8 + WALK_START)


MMD_LIGHT = 154.0 / 255.0


def mmd_preview_materials(meshes):
    """Swap each imported material for an emission shader that evaluates what MMD draws
    for it: texture x saturate(diffuse x light + ambient) x toon(v = 0.5 - 0.5 N.L),
    with N.L from render.py's sun as in the cel materials. mmd_tools' own preview shader
    lights differently, so this is how the PMX's colours, textures and toon ramps are
    checked against the cel render (same light, same palette expected)."""
    done = {}
    for o in meshes:
        for i, mat in enumerate(o.data.materials):
            if mat is None or mat.name in done:
                if mat is not None:
                    o.data.materials[i] = done[mat.name]
                continue
            mm = mat.mmd_material
            nodes = mat.node_tree.nodes if mat.node_tree else {}
            base_img = nodes.get('mmd_base_tex').image if nodes.get('mmd_base_tex') else None
            toon_img = nodes.get('mmd_toon_tex').image if nodes.get('mmd_toon_tex') else None
            new = bpy.data.materials.new(mat.name + '_mmdpreview')
            if new.node_tree is None:      # Blender < 5 materials start without nodes
                new.use_nodes = True
            nt = new.node_tree
            nt.nodes.clear()
            n, ln = nt.nodes, nt.links
            out = n.new('ShaderNodeOutputMaterial')
            diff = n.new('ShaderNodeBsdfDiffuse')
            diff.inputs['Color'].default_value = (1, 1, 1, 1)
            s2r = n.new('ShaderNodeShaderToRGB')
            ln.new(diff.outputs['BSDF'], s2r.inputs['Shader'])
            bw = n.new('ShaderNodeRGBToBW')
            ln.new(s2r.outputs['Color'], bw.inputs['Color'])
            col = [min(1.0, d * MMD_LIGHT + a) for d, a in zip(mm.diffuse_color, mm.ambient_color)]
            # sRGB-encoded MMD colour -> linear socket value
            lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in col]
            rgb = n.new('ShaderNodeRGB')
            rgb.outputs[0].default_value = (*lin, 1.0)
            cur = rgb.outputs[0]
            if base_img is not None:
                tex = n.new('ShaderNodeTexImage')
                tex.image = base_img
                tex.interpolation = 'Linear'
                tex.extension = 'EXTEND'
                uvn = n.new('ShaderNodeUVMap')
                ln.new(uvn.outputs['UV'], tex.inputs['Vector'])
                mul = n.new('ShaderNodeMix')
                mul.data_type, mul.blend_type = 'RGBA', 'MULTIPLY'
                mul.inputs['Factor'].default_value = 1.0
                ln.new(cur, mul.inputs[6])
                ln.new(tex.outputs['Color'], mul.inputs[7])
                cur = mul.outputs[2]
            if toon_img is not None:
                toon_img.colorspace_settings.name = 'sRGB'
                # Blender's v runs bottom -> top: v_bl = 1 - (0.5 - 0.5 N.L) = 0.5 + 0.5 N.L
                mad = n.new('ShaderNodeMath')
                mad.operation = 'MULTIPLY_ADD'
                ln.new(bw.outputs['Val'], mad.inputs[0])
                mad.inputs[1].default_value = 0.5
                mad.inputs[2].default_value = 0.5
                xyz = n.new('ShaderNodeCombineXYZ')
                xyz.inputs['X'].default_value = 0.5
                ln.new(mad.outputs['Value'], xyz.inputs['Y'])
                tt = n.new('ShaderNodeTexImage')
                tt.image = toon_img
                tt.interpolation = 'Closest'
                tt.extension = 'EXTEND'
                ln.new(xyz.outputs['Vector'], tt.inputs['Vector'])
                mul = n.new('ShaderNodeMix')
                mul.data_type, mul.blend_type = 'RGBA', 'MULTIPLY'
                mul.inputs['Factor'].default_value = 1.0
                ln.new(cur, mul.inputs[6])
                ln.new(tt.outputs['Color'], mul.inputs[7])
                cur = mul.outputs[2]
            emit = n.new('ShaderNodeEmission')
            ln.new(cur, emit.inputs['Color'])
            ln.new(emit.outputs['Emission'], out.inputs['Surface'])
            done[mat.name] = new
            o.data.materials[i] = new


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pmx', default='out/pmx/Levi.pmx')
    ap.add_argument('--save', default='out/pmx/reimport.blend')
    ap.add_argument('--no-vmd', action='store_true', help='skip the VMD walk round trip')
    args = ap.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
    path = os.path.join(ROOT, args.pmx)
    with open(os.path.splitext(path)[0] + '.json', encoding='utf-8') as f:
        expect = json.load(f)

    pkg = None
    for name in ('bl_ext.blender_org.mmd_tools', 'mmd_tools'):
        try:
            pkg = importlib.import_module(name)
            break
        except ImportError:
            pass
    if pkg is None:
        print('FAIL mmd_tools not available')
        sys.exit(1)
    pmx_mod = importlib.import_module(pkg.__name__ + '.core.pmx')

    def tex_load(self, fs):        # keep the path as written in the file (the loader makes it absolute)
        self.raw_path = fs.readStr()
        p = self.raw_path.replace('\\', os.path.sep)
        self.path = p if os.path.isabs(p) else os.path.normpath(os.path.join(os.path.dirname(fs.path()), p))
    pmx_mod.Texture.load = tex_load
    pmx = pmx_mod.load(path)

    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.ops.mmd_tools.import_model(filepath=path, scale=1.0 / 12.5,
                                   types={'MESH', 'ARMATURE', 'PHYSICS', 'DISPLAY', 'MORPHS'}, log_level='WARNING')

    errors = []

    def same(label, got, want):
        print(f'{label:14s} file={got} expected={want}')
        if got != want:
            errors.append(f'{label}: {got} != {want}')

    same('bones', len(pmx.bones), expect['bones'])
    same('materials', len(pmx.materials), expect['materials'])
    same('rigid_bodies', len(pmx.rigids), expect['rigid_bodies'])
    same('joints', len(pmx.joints), expect['joints'])
    for b in pmx.bones:
        if not b.name or not b.name_e:
            errors.append(f'bone {b.name!r}/{b.name_e!r} missing a name')
    if 'append_bones' in expect:
        same('append bones', sum(1 for b in pmx.bones if b.hasAdditionalRotate), expect['append_bones'])
        same('fixed axis', sum(1 for b in pmx.bones if b.axis is not None), expect['fixed_axis_bones'])
        same('local axes', sum(1 for b in pmx.bones if b.localCoordinate is not None), expect['local_axes_bones'])
    ik = sorted(b.name for b in pmx.bones if b.isIK)
    print('IK bones', ik)
    for want in ('左足ＩＫ', '右足ＩＫ', '左つま先ＩＫ', '右つま先ＩＫ'):
        if want not in ik:
            errors.append(f'{want} is not an IK bone in the PMX')

    arms = [o for o in bpy.data.objects if o.type == 'ARMATURE']
    meshes = [o for o in bpy.data.objects if o.type == 'MESH' and getattr(o, 'mmd_type', 'NONE') == 'NONE']
    same('blender bones', sum(1 for pb in arms[0].pose.bones if not pb.is_mmd_shadow_bone) if arms else 0,
         expect['bones'])
    nv = sum(len(o.data.vertices) for o in meshes)
    same('vertices', nv, len(pmx.vertices))
    nmat = sum(len(o.data.materials) for o in meshes)
    same('blender mats', nmat, expect['materials'])
    unweighted = 0
    for o in meshes:
        for v in o.data.vertices:
            if not any(g.weight > 0 for g in v.groups):
                unweighted += 1
    if unweighted:
        errors.append(f'{unweighted} vertices without weights after reimport')
    if arms:
        importlib.import_module(pkg.__name__ + '.core.bone').FnBone.apply_additional_transformation(arms[0])
        for source in ('左足', '左ひざ', '左ひじ', '左腕', '頭', '両目'):
            check_append(arms[0], errors, source)
    rb = [o for o in bpy.data.objects if getattr(o, 'mmd_type', '') == 'RIGID_BODY']
    same('blender rigid', len(rb), expect['rigid_bodies'])
    check_names(pmx, errors)
    check_frames(pmx, errors)
    check_ik_limits(pmx, errors)
    check_textures(pmx, path, errors)
    print(f'morphs {len(pmx.morphs)}' + ('' if pmx.morphs else ' (none: the eyes and mouth are painted in the face texture)'))
    check_morphs(pmx, expect.get('vertex_morphs', []), errors, expect.get('morph_panels'))

    if args.save:
        out = os.path.join(ROOT, args.save)
        bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
        print('SAVED', out)
    if args.save:      # the same model with MMD-equivalent preview materials, for render.py
        mmd_preview_materials(meshes)
        out = os.path.splitext(os.path.join(ROOT, args.save))[0] + '_preview.blend'
        bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
        print('SAVED', out)
    if arms and not args.no_vmd:
        roots = [o for o in bpy.data.objects if getattr(o, 'mmd_type', '') == 'ROOT']
        vmd_round_trip(roots[0] if roots else None, arms[0], os.path.dirname(path), errors)
        if args.save:
            out = os.path.splitext(os.path.join(ROOT, args.save))[0] + '_walk.blend'
            bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
            print('SAVED', out)
    for e in errors:
        print('FAIL', e)
    print('REIMPORT', 'FAILED' if errors else 'OK')
    sys.exit(1 if errors else 0)


main()
