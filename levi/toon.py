"""Cel-shading materials: two-tone toon ramp + inverted-hull outlines (EEVEE).

Every visible material in the model comes from toon_material(); outlines come
from add_outline(). Look-dev tuning (ramp threshold, light, line weight) lives
here and in render.py so all parts change together.

Shading model (matches the sheet's flat anime style):
  intensity = N.L x shadow   from one camera-relative sun of strength 1 and a
                             black world (render.py), so 0..1 and noise-free
  colour    = shade if intensity < ramp_threshold(key) else base   (palette
                             hexes, emitted, so they land in the PNG exactly)
Outlines are coloured (palette 'line'), never black, and do not cast shadows.
"""
import bpy

from . import spec

# N.L below which a surface takes the shade colour. With the light ~23 deg off
# the view axis this keeps surfaces mostly lit and puts the single shade tone
# on turned-away sides plus cast shadows (under the chin, hair, skirt hem).
# Tuned on the full model (round 2) against the per-region shade share
# (tools/compare.py 'shade ref .. ren ..'): 0.30 with cast shadows gives skin
# ~17-20% shade like the sheet's ~18%; higher values over-shade skin.
RAMP_THRESHOLD = 0.30
# Per-palette-key thresholds (look-dev, not per part): the sheet paints cloth
# and hair with much more shade than skin (anime convention), so with one
# global threshold either skin is over-shaded or the dress/hair stay almost
# flat. Keys not listed use RAMP_THRESHOLD; gradient materials use the
# threshold of their first key.
# Values from the round-2 full-model sweep, balancing the shade share against
# dE and visual review: at 0.55/0.50 the hair and skirt shade read too broad
# and grey next to the sheet, so cloth and hair sit a little lower, with
# lighter shade tones (spec.PALETTE) so misplaced shade costs less.
RAMP_BY_KEY = {
    'dress': 0.48, 'dress_mint': 0.48, 'sleeve': 0.48, 'sleeve_dark': 0.48,
    'hair': 0.42, 'green': 0.50, 'leaf': 0.50,
    # Round 4: the sheet paints the shoes almost flat base (shade share
    # 0.18-0.32, and the sheet pixels under the render's shoe shade are base
    # coloured); at 0.30 the low sun put the upward-facing vamp and toe box in
    # shade (front 0.45). Only surfaces really turned away now go dark.
    'shoe': 0.10,
}
# Half-width of the lit/shade transition. 0 = hard cel edge (CONSTANT ramp):
# every pixel is exactly base or shade, and only TAA anti-aliases the
# terminator. >0 blends linearly over that N.L range.
RAMP_SOFTNESS = 0.0
GRAD_ATTR = 'toon_grad'  # per-vertex float 0..1 blending palette A -> B
# Gradient materials whose outline colour follows toon_grad too (round 4):
# the hair's mint tips get the mint line, as on the sheet. Other gradients
# keep the first key's line: the sleeves' pale-mint fade would otherwise get
# sleeve_dark's near-black green line.
GRADIENT_LINES = {('hair', 'hair_tip')}


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


def ramp_threshold(key=None):
    """N.L threshold for palette `key` (RAMP_BY_KEY, else RAMP_THRESHOLD)."""
    return RAMP_BY_KEY.get(key, RAMP_THRESHOLD)


def _tune_ramp(ramp, key=None):
    """Set a 'ToonRamp' ColorRamp node to the current RAMP_* settings."""
    t = ramp_threshold(key)
    e = ramp.color_ramp.elements
    if RAMP_SOFTNESS > 0:
        ramp.color_ramp.interpolation = 'LINEAR'
        e[0].position = max(0.0, t - RAMP_SOFTNESS)
        e[1].position = min(1.0, t + RAMP_SOFTNESS)
    else:
        ramp.color_ramp.interpolation = 'CONSTANT'
        e[0].position = 0.0
        e[1].position = t
    e[0].color = (0, 0, 0, 1)
    e[1].color = (1, 1, 1, 1)


def _ramp(nodes, links, intensity_socket, key=None):
    ramp = nodes.new('ShaderNodeValToRGB')
    ramp.name = 'ToonRamp'
    _tune_ramp(ramp, key)
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


def _default_name(key, gradient=None):
    return f'toon_{key}' if not gradient else f'toon_{key}__{gradient}'


def toon_material(key, gradient=None, name=None):
    """Return (creating once) the toon material for palette `key`.

    gradient: optional second palette key. The mesh's float attribute
    'toon_grad' (0 -> key, 1 -> gradient) blends between the two palettes,
    e.g. toon_material('hair', gradient='hair_tip').
    """
    name = name or _default_name(key, gradient)
    mat = bpy.data.materials.get(name)
    if mat:
        return mat
    mat = bpy.data.materials.new(name)
    mat['toon_key'] = key
    if gradient:
        mat['toon_gradient'] = gradient
    mat['toon_std'] = True  # tree owned by _build_toon_tree; sync_materials() rebuilds it
    _build_toon_tree(mat)
    return mat


def _build_toon_tree(mat):
    key, gradient = mat['toon_key'], mat.get('toon_gradient')
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
    ramp = _ramp(nodes, links, bw.outputs['Val'], key)

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


def sync_materials():
    """Re-apply the current look-dev (RAMP_* and spec.PALETTE) to the toon and
    outline materials already in the file, so a .blend built before a look-dev
    change renders with current settings (render.py calls this).

    toon_material() trees are rebuilt; custom part materials that reuse
    _ramp() (e.g. the face) get their 'ToonRamp' node re-tuned; outline hulls
    get their palette line colour. Returns the number of materials touched.
    """
    n = 0
    for mat in bpy.data.materials:
        key = mat.get('toon_key')
        if key not in spec.PALETTE or not mat.node_tree:
            continue
        if mat.get('is_outline'):
            n += _set_outline_colour(mat)
        elif (mat.get('toon_std')
              or mat.name.split('.')[0] == _default_name(key, mat.get('toon_gradient'))) \
                and mat.get('toon_gradient', key) in spec.PALETTE:
            _build_toon_tree(mat)
            n += 1
        else:
            ramp = mat.node_tree.nodes.get('ToonRamp')
            if ramp:
                _tune_ramp(ramp, key)
                n += 1
    return n


def _set_outline_colour(mat):
    """Palette line colour(s) of an outline material (gradient: by toon_grad)."""
    key, grad = mat['toon_key'], mat.get('toon_gradient')
    nodes = mat.node_tree.nodes
    mix = nodes.get('LineGrad')
    if grad and mix and grad in spec.PALETTE:
        mix.inputs[6].default_value = srgb(spec.PALETTE[key]['line'])
        mix.inputs[7].default_value = srgb(spec.PALETTE[grad]['line'])
    else:
        emit = nodes.get('ToonEmission')
        if not emit:
            return False
        emit.inputs['Color'].default_value = srgb(spec.PALETTE[key]['line'])
    mat.diffuse_color = srgb(spec.PALETTE[key]['line'])
    return True


def outline_material(key, gradient=None):
    """Flat line-colour emission for the inverted hull.

    gradient: second palette key of a gradient toon material; the line colour
    then follows the mesh's toon_grad like the fill (a white-to-mint hair
    lock gets the mint line along its mint tip, not the white hair's grey).

    The hull wraps its mesh, so it must never cast shadows (otherwise every
    outlined object sits in its own hull's shadow and renders in the shade
    tone): it is transparent to shadow rays and back-face culled for shadows.
    """
    name = f'outline_{key}' if not gradient else f'outline_{key}__{gradient}'
    mat = bpy.data.materials.get(name)
    if mat:
        return mat
    mat = bpy.data.materials.new(name)
    mat['toon_key'] = key
    if gradient:
        mat['toon_gradient'] = gradient
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
    if gradient:
        attr = nt.nodes.new('ShaderNodeAttribute')
        attr.attribute_type = 'GEOMETRY'
        attr.attribute_name = GRAD_ATTR
        mix = nt.nodes.new('ShaderNodeMix')
        mix.name = 'LineGrad'
        mix.data_type = 'RGBA'
        nt.links.new(attr.outputs['Fac'], mix.inputs['Factor'])
        nt.links.new(mix.outputs[2], emit.inputs['Color'])
    _set_outline_colour(mat)
    path = nt.nodes.new('ShaderNodeLightPath')
    clear = nt.nodes.new('ShaderNodeBsdfTransparent')
    mix = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(path.outputs['Is Shadow Ray'], mix.inputs['Fac'])
    nt.links.new(emit.outputs['Emission'], mix.inputs[1])
    nt.links.new(clear.outputs['BSDF'], mix.inputs[2])
    nt.links.new(mix.outputs['Shader'], out.inputs['Surface'])
    return mat


def add_outline(obj, width=None, vertex_group=None, min_factor=0.0):
    """Inverted-hull outline: Solidify (flipped) using per-slot line colours.

    width: hull thickness in metres (default spec.OUTLINE_WIDTH, ~1.25 panel
    px). On screen the line is about width * spec.PX_PER_M pixels wide.
    vertex_group: optional group scaling the thickness per vertex (weight 1 =
    width, 0 = width * min_factor), e.g. a thinner line on an internal hair
    overlap or a rolled hem lip while the outer silhouette keeps full weight.
    Gradient materials listed in GRADIENT_LINES get a line colour that
    follows toon_grad too.
    """
    width = spec.OUTLINE_WIDTH if width is None else width
    n = len(obj.data.materials)
    if n == 0:
        raise ValueError(f'{obj.name}: assign toon materials before add_outline')
    for i in range(n):
        m = obj.data.materials[i]
        key = m.get('toon_key', 'hair')
        grad = m.get('toon_gradient')
        obj.data.materials.append(outline_material(key, grad if (key, grad) in GRADIENT_LINES else None))
    mod = obj.modifiers.new('Outline', 'SOLIDIFY')
    mod.thickness = width
    mod.offset = 1.0
    mod.use_flip_normals = True
    mod.use_rim = False
    mod.use_quality_normals = True
    mod.material_offset = n
    mod.material_offset_rim = n
    if vertex_group:
        if vertex_group not in obj.vertex_groups:
            raise ValueError(f'{obj.name}: no vertex group {vertex_group!r} for the outline width')
        mod.vertex_group = vertex_group
        mod.thickness_vertex_group = min_factor
    return mod
