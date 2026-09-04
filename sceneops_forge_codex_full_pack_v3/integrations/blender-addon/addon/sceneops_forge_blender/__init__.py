bl_info = {
    "name": "SceneOps Forge Typed Bridge",
    "author": "SceneOps Forge",
    "version": (0, 1, 0),
    "blender": (4, 2, 0),
    "location": "Scene > SceneOps Forge",
    "description": "Allowlisted SceneOps health and asset operations",
    "category": "Pipeline",
}


def register():
    # The headless typed bridge imports the dispatcher directly. No console or
    # arbitrary-script operator is registered into Blender.
    return None


def unregister():
    return None
