"""Cel-shading materials: two-tone toon ramp + inverted-hull outlines (EEVEE).

Every visible material in the model comes from toon_material(); outlines come
from add_outline(). Look-dev tuning (ramp threshold, light, line weight) lives
here and in render.py so all parts change together.

Shading model (matches the sheet's flat anime style):
  intensity = N.L x shadow   from one camera-relative sun of strength 1 and a
                             black world (render.py), so 0..1 and noise-free
  colour    = shade if intensity < RAMP_THRESHOLD else base   (palette hexes,
                             emitted, so they land in the PNG exactly)
Outlines are coloured (palette 'line'), never black, and do not cast shadows.
"""
import bpy

from . import spec

# N.L below which a surface takes the shade colour. With the light ~35 deg off
# the view axis this keeps surfaces mostly lit and puts the single shade tone
# on turned-away sides plus cast shadows (under the chin, hair, skirt hem).
RAMP_THRESHOLD = 0.22
# Half-width of the lit/shade transition. 0 = hard cel edge (CONSTANT ramp):
# every pixel is exactly base or shade, and only TAA anti-aliases the
# terminator. >0 blends linearly over that N.L range.
RAMP_SOFTNESS = 0.0
GRAD_ATTR = 'toon_grad'  # per-vertex float 0..1 blending palette A -> B


def srgb(hex_str):
    """'#RRGGBB' -> linear RGBA tuple for Blender colour sockets.

    Blender colour sockets are scene-linear; with the Standard view transform
    (render.py) the PNG gets the inverse transfer, so the hex comes back out.
    """
    h = hex_str.lstrip('#')
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255.0
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return (*out, 1.0)


def _ramp(nodes, links, intensity_socket):
    ramp = nodes.new('ShaderNodeValToRGB')
    ramp.name = 'ToonRamp'
    e = ramp.color_ramp.elements
    if RAMP_SOFTNESS > 0:
        ramp.color_ramp.interpolation = 'LINEAR'
        e[0].position = max(0.0, RAMP_THRESHOLD - RAMP_SOFTNESS)
        e[1].position = min(1.0, RAMP_THRESHOLD + RAMP_SOFTNESS)
    else:
        ramp.color_ramp.interpolation = 'CONSTANT'
        e[0].position = 0.0
        e[1].position = RAMP_THRESHOLD
    e[0].color = (0, 0, 0, 1)
    e[1].color = (1, 1, 1, 1)
    links.new(intensity_socket, ramp.inputs['Fac'])
    return ramp


def _mix(nodes, links, fac, a, b):
    m = nodes.new('ShaderNodeMix')
    m.data_type = 'RGBA'
    if isinstance(fac, float):
        m.inputs['Factor'].default_value = fac
    else:
        links.new(fac, m.inputs['Factor'])
    for sock, val in ((m.inputs[6], a), (m.inputs[7], b)):
        if isinstance(val, tuple):
            sock.default_value = val
        else:
            links.new(val, sock)
    return m.outputs[2]


def toon_material(key, gradient=None, name=None):
    """Return (creating once) the toon material for palette `key`.

    gradient: optional second palette key. The mesh's float attribute
    'toon_grad' (0 -> key, 1 -> gradient) blends between the two palettes,
    e.g. toon_material('hair', gradient='hair_tip').
    """
    name = name or (f'toon_{key}' if not gradient else f'toon_{key}__{gradient}')
    mat = bpy.data.materials.get(name)
    if mat:
        return mat
    mat = bpy.data.materials.new(name)
    mat['toon_key'] = key
    if gradient:
        mat['toon_gradient'] = gradient
    mat.use_nodes = True
    nt = mat.node_tree
    nodes, links = nt.nodes, nt.links
    nodes.clear()
    out = nodes.new('ShaderNodeOutputMaterial')
    diff = nodes.new('ShaderNodeBsdfDiffuse')
    diff.inputs['Color'].default_value = (1, 1, 1, 1)
    s2r = nodes.new('ShaderNodeShaderToRGB')
    links.new(diff.outputs['BSDF'], s2r.inputs['Shader'])
    bw = nodes.new('ShaderNodeRGBToBW')
    links.new(s2r.outputs['Color'], bw.inputs['Color'])
    ramp = _ramp(nodes, links, bw.outputs['Val'])

    pa = spec.PALETTE[key]
    base, shade = srgb(pa['base']), srgb(pa['shade'])
    if gradient:
        pb = spec.PALETTE[gradient]
        attr = nodes.new('ShaderNodeAttribute')
        attr.name = 'ToonGrad'
        attr.attribute_type = 'GEOMETRY'
        attr.attribute_name = GRAD_ATTR
        base = _mix(nodes, links, attr.outputs['Fac'], base, srgb(pb['base']))
        shade = _mix(nodes, links, attr.outputs['Fac'], shade, srgb(pb['shade']))
    col = _mix(nodes, links, ramp.outputs['Color'], shade, base)
    emit = nodes.new('ShaderNodeEmission')
    emit.name = 'ToonEmission'
    emit.inputs['Strength'].default_value = 1.0
    links.new(col, emit.inputs['Color'])
    links.new(emit.outputs['Emission'], out.inputs['Surface'])
    mat.diffuse_color = srgb(pa['base'])  # viewport / PMX fallback
    mat.line_color = srgb(pa['line'])     # Freestyle (render.py --freestyle)
    return mat


def outline_material(key):
    """Flat line-colour emission for the inverted hull.

    The hull wraps its mesh, so it must never cast shadows (otherwise every
    outlined object sits in its own hull's shadow and renders in the shade
    tone): it is transparent to shadow rays and back-face culled for shadows.
    """
    name = f'outline_{key}'
    mat = bpy.data.materials.get(name)
    if mat:
        return mat
    mat = bpy.data.materials.new(name)
    mat['toon_key'] = key
    mat['is_outline'] = True
    mat.use_nodes = True
    mat.use_backface_culling = True
    mat.use_backface_culling_shadow = True
    mat.use_transparent_shadow = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    emit = nt.nodes.new('ShaderNodeEmission')
    emit.name = 'ToonEmission'
    emit.inputs['Color'].default_value = srgb(spec.PALETTE[key]['line'])
    emit.inputs['Strength'].default_value = 1.0
    path = nt.nodes.new('ShaderNodeLightPath')
    clear = nt.nodes.new('ShaderNodeBsdfTransparent')
    mix = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(path.outputs['Is Shadow Ray'], mix.inputs['Fac'])
    nt.links.new(emit.outputs['Emission'], mix.inputs[1])
    nt.links.new(clear.outputs['BSDF'], mix.inputs[2])
    nt.links.new(mix.outputs['Shader'], out.inputs['Surface'])
    mat.diffuse_color = srgb(spec.PALETTE[key]['line'])
    return mat


def add_outline(obj, width=None):
    """Inverted-hull outline: Solidify (flipped) using per-slot line colours.

    width: hull thickness in metres (default spec.OUTLINE_WIDTH, ~1.25 panel
    px). On screen the line is about width * spec.PX_PER_M pixels wide.
    """
    width = spec.OUTLINE_WIDTH if width is None else width
    n = len(obj.data.materials)
    if n == 0:
        raise ValueError(f'{obj.name}: assign toon materials before add_outline')
    for i in range(n):
        key = obj.data.materials[i].get('toon_key', 'hair')
        obj.data.materials.append(outline_material(key))
    mod = obj.modifiers.new('Outline', 'SOLIDIFY')
    mod.thickness = width
    mod.offset = 1.0
    mod.use_flip_normals = True
    mod.use_rim = False
    mod.use_quality_normals = True
    mod.material_offset = n
    mod.material_offset_rim = n
    return mod
