import bpy

from . import(
    references_overlays,
    preference
)

module_list = (
    references_overlays,
    preference,
)

def register():
    for mod in module_list:
        mod.register()

def unregister():
    for mod in reversed(module_list):
        mod.unregister()
