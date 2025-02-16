from . import references_overlays

def register():
    references_overlays.register()

def unregister():
    references_overlays.unregister()

if __name__ == "__main__":
    register()