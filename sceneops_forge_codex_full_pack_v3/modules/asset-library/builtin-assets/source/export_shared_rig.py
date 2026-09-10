"""Publish the one shared skeleton/action library separately from character geometry."""
import json,struct
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[2]/'backend/src/asset_library/builtin_assets'
folder=ROOT/'revisions/v5'
bpy.ops.wm.open_mainfile(filepath=str(folder/'blend/character-player.blend'))
for obj in list(bpy.context.scene.objects):
    if obj.type!='ARMATURE':bpy.data.objects.remove(obj,do_unlink=True)
rig=next(obj for obj in bpy.context.scene.objects if obj.type=='ARMATURE')
rig.name='SceneOpsHumanoid';rig.data.name='SceneOpsHumanoidV1'
bpy.context.view_layer.objects.active=rig;rig.select_set(True)
bpy.ops.wm.save_as_mainfile(filepath=str(folder/'blend/shared-humanoid-v1.blend'))
bpy.ops.export_scene.gltf(filepath=str(folder/'glb/shared-motions-v1.glb'),export_format='GLB',use_selection=True,
 export_animations=True,export_animation_mode='NLA_TRACKS',export_force_sampling=True,export_nla_strips=True,
 export_yup=True,export_cameras=False,export_lights=False)
b= (folder/'glb/shared-motions-v1.glb').read_bytes();d=json.loads(b[20:20+struct.unpack_from('<I',b,12)[0]])
assert {a['name'] for a in d.get('animations',[])}=={'Idle','Walk','Run','Wave'}
assert not d.get('meshes')
metadata={'skeleton_id':'sceneops-humanoid-v1','animation_set_id':'sceneops-basic-locomotion-v1',
 'coordinate_system':'Blender source: Z-up, meters; GLB: Y-up, meters',
 'bones':[{'name':b.name,'parent':b.parent.name if b.parent else None,'head':list(b.head_local),'tail':list(b.tail_local),'rest_matrix':[list(row) for row in b.matrix_local]} for b in rig.data.bones],
 'clips':list({'Idle':2,'Walk':1,'Run':20/30,'Wave':2}.items()),
 'usage':'GLTFLoader 加载 shared-motions-v1.glb 的 animations，再用目标角色的 AnimationMixer.clipAction(clip) 播放；同 skeleton_id 无需重定向。保留骨骼名称、层级、静止矩阵及网格蒙皮；不同体型需重新检查权重和关节位置。'}
(folder/'shared-rig.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n')
catalog=json.loads((ROOT/'catalog.json').read_text())
for entry in catalog['entries']:
    if entry.get('rig',{}).get('status')=='skinned':
        entry['rig'].update(skeleton_id='sceneops-humanoid-v1',animation_set_id='sceneops-basic-locomotion-v1')
        entry['motion_path']='revisions/v5/glb/shared-motions-v1.glb'
        entry['rig_template_path']='revisions/v5/blend/shared-humanoid-v1.blend'
(ROOT/'catalog.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n')
print('SHARED_RIG_EXPORTED',len(d['animations']))
