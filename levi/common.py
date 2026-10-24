"""Shared helpers for part modules. Parts import from here; do not edit per-part."""
import math

import bmesh
import bpy
from mathutils import Vector

from . import spec
from .toon import GRAD_ATTR, add_outline, toon_material  # noqa: F401  (re-export)


# ---------------------------------------------------------------- scene
def part_collection(name):
    """Fresh collection for a part (removes a previous build of it)."""
    old = bpy.data.collections.get(name)
    if old:
        for o in list(old.all_objects):
            bpy.data.objects.remove(o, do_unlink=True)
        bpy.data.collections.remove(old)
    col = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(col)
    return col


def new_object(col, name, bm_or_mesh, materials=()):
    """Create a mesh object in `col` from a BMesh (freed) or Mesh."""
    if isinstance(bm_or_mesh, bmesh.types.BMesh):
        me = bpy.data.meshes.new(name)
        bm_or_mesh.to_mesh(me)
        bm_or_mesh.free()
    else:
        me = bm_or_mesh
    for m in materials:
        me.materials.append(m)
    obj = bpy.data.objects.new(name, me)
    col.objects.link(obj)
    return obj


def shade_smooth(obj, angle_deg=40.0):
    obj.data.shade_smooth()
    obj.data.set_sharp_from_angle(angle=math.radians(angle_deg))


def set_gradient(obj, fn):
    """Write the 'toon_grad' point attribute: fn(world_co: Vector) -> 0..1."""
    me = obj.data
    attr = me.attributes.get(GRAD_ATTR) or me.attributes.new(GRAD_ATTR, 'FLOAT', 'POINT')
    mw = obj.matrix_world
    for i, v in enumerate(me.vertices):
        attr.data[i].value = max(0.0, min(1.0, fn(mw @ v.co)))


def z_gradient(z_start, z_end):
    """Gradient fn: 0 at z_start, 1 at z_end (smoothstep)."""
    def f(co):
        t = (co.z - z_start) / (z_end - z_start)
        t = max(0.0, min(1.0, t))
        return t * t * (3 - 2 * t)
    return f


def mirror_x(obj, merge=True, threshold=1e-4):
    mod = obj.modifiers.new('MirrorX', 'MIRROR')
    mod.use_axis = (True, False, False)
    mod.use_clip = merge
    mod.use_mirror_merge = merge
    mod.merge_threshold = threshold
    return mod


def subsurf(obj, levels=1):
    mod = obj.modifiers.new('Subsurf', 'SUBSURF')
    mod.levels = levels
    mod.render_levels = levels
    return mod


def apply_modifiers(obj, keep=('Outline',)):
    """Apply all modifiers except those named in `keep` (outline stays live)."""
    bpy.context.view_layer.update()
    for m in list(obj.modifiers):
        if m.name in keep:
            continue
        with bpy.context.temp_override(object=obj, active_object=obj,
                                       selected_objects=[obj], selected_editable_objects=[obj]):
            bpy.ops.object.modifier_apply(modifier=m.name)


# ---------------------------------------------------------------- geometry
def loft(rings, closed=True, cap_start=False, cap_end=False):
    """BMesh from a list of rings (each a list of Vector, same length).

    Faces connect ring i to ring i+1. closed: each ring is a loop.
    """
    bm = bmesh.new()
    vs = [[bm.verts.new(p) for p in r] for r in rings]
    n = len(rings[0])
    seg = n if closed else n - 1
    for a, b in zip(vs, vs[1:]):
        for j in range(seg):
            k = (j + 1) % n
            bm.faces.new((a[j], a[k], b[k], b[j]))
    if cap_start and closed:
        bm.faces.new(list(reversed(vs[0])))
    if cap_end and closed:
        bm.faces.new(vs[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def ellipse_ring(center, rx, ry, n, z=None, phase=0.0):
    """Ring of n points around `center` in the XY plane (radii rx, ry)."""
    c = Vector(center)
    zz = c.z if z is None else z
    return [Vector((c.x + rx * math.cos(phase + 2 * math.pi * i / n),
                    c.y + ry * math.sin(phase + 2 * math.pi * i / n), zz)) for i in range(n)]


def tube_along(points, radii, n=8):
    """BMesh tube following a polyline (list of Vector) with per-point radius."""
    pts = [Vector(p) for p in points]
    rings = []
    prev_side = None
    for i, p in enumerate(pts):
        t = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        side = prev_side if prev_side is not None else t.orthogonal().normalized()
        side = (side - t * side.dot(t)).normalized()
        up = t.cross(side)
        prev_side = side
        r = radii[i] if hasattr(radii, '__len__') else radii
        rings.append([p + (side * math.cos(2 * math.pi * k / n) + up * math.sin(2 * math.pi * k / n)) * r
                      for k in range(n)])
    return loft(rings, closed=True, cap_start=True, cap_end=True)


def face_count(objs):
    """Evaluated polygon count, excluding outline hull duplicates."""
    dg = bpy.context.evaluated_depsgraph_get()
    total = 0
    for o in objs:
        if o.type != 'MESH':
            continue
        outline = o.modifiers.get('Outline')
        if outline:
            outline.show_viewport = False
        dg.update()
        total += len(o.evaluated_get(dg).data.polygons)
        if outline:
            outline.show_viewport = True
    return total


__all__ = [
    'spec', 'part_collection', 'new_object', 'shade_smooth', 'set_gradient', 'z_gradient',
    'mirror_x', 'subsurf', 'apply_modifiers', 'loft', 'ellipse_ring', 'tube_along',
    'face_count', 'toon_material', 'add_outline', 'GRAD_ATTR',
]
