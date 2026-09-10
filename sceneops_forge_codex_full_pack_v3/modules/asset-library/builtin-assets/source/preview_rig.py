"""Render actual evaluated poses from the saved, skinned Blender assets."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
import generate as g
import expand,expand_v3
ROOT=g.ROOT/'revisions/v5'
for key in ['person-clay','person-enamel','person-engineer']:
    for clip,frame in [('Run',5),('Wave',30)]:
        bpy.ops.wm.open_mainfile(filepath=str(ROOT/'blend'/f'{key}.blend'))
        rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
        action=next(track.strips[0].action for track in rig.animation_data.nla_tracks if track.name==clip)
        for track in rig.animation_data.nla_tracks:track.mute=True
        rig.animation_data.action=action;bpy.context.scene.frame_set(frame);bpy.context.view_layer.update()
        objects=[o for o in bpy.context.scene.objects if o.type=='MESH']
        g.M.clear();g.presentation(objects);rig.hide_render=False
        bpy.context.scene.render.filepath=str(ROOT/'previews'/f'{key}-{clip}.png');bpy.ops.render.render(write_still=True);g.clean_presentation()
print('RIG_POSES_RENDERED',flush=True)
