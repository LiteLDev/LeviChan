"""Part discovery and full-model build."""
import importlib
import os
import pkgutil

import bpy

from . import common, parts, proxy


def available_parts():
    """Part modules in levi/parts (files starting with '_' are private helpers)."""
    return sorted(m.name for m in pkgutil.iter_modules(parts.__path__) if not m.name.startswith('_'))


def reset_scene():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for c in list(bpy.data.collections):
        bpy.data.collections.remove(c)
    for block in (bpy.data.meshes, bpy.data.materials, bpy.data.curves, bpy.data.images, bpy.data.armatures):
        for x in list(block):
            if x.users == 0:
                block.remove(x)


def build_part(name):
    mod = importlib.import_module(f'levi.parts.{name}')
    importlib.reload(mod)
    col = common.part_collection(name)
    mod.build(col)
    return col


def build_all(names=None, with_proxy=False):
    """Build the given parts (default: all) into a clean scene; returns {name: collection}."""
    reset_scene()
    names = available_parts() if not names else names
    out = {}
    for n in names:
        out[n] = build_part(n)
    if with_proxy:
        out[proxy.NAME] = proxy.build()
    bpy.context.view_layer.update()
    return out


def repo_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
