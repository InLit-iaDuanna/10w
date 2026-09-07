"""Developer-only acceptance fixture, never reachable through adapter commands.

Simulates a human adding free geometry in Blender; does not claim a UI action.
"""
import sys
from pathlib import Path
import bpy

source = Path(sys.argv[sys.argv.index('--') + 1]).resolve(strict=True)
bpy.ops.wm.open_mainfile(filepath=str(source))
leaf = next(obj for obj in bpy.context.scene.objects if obj.get('sceneops_role') == 'leaf')
bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=8, radius=0.06)
handle = bpy.context.object
handle.name = 'Developer simulated manual handle'
handle.parent = leaf
handle.location = (0.4, -0.14, 0)
assert handle.get('sceneops_id') is None
bpy.ops.wm.save_as_mainfile(filepath=str(source), compress=False)
