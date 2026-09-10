"""Reimport the shipped GLBs and check geometry, identity, role shape and spawn clearance."""
import json
import struct
from pathlib import Path
import bpy
from mathutils import Vector

SOURCE_ROOT=Path(__file__).resolve().parents[1]
ROOT=SOURCE_ROOT.parent/'backend/src/asset_library/builtin_assets'
catalog=json.loads((ROOT/'catalog.json').read_text())
results=[];role_shapes=[];role_colors=[]
for entry in catalog['entries']:
    filename=ROOT/entry['glb_path']
    payload=filename.read_bytes()
    magic,version,size=struct.unpack_from('<4sII',payload)
    assert magic==b'glTF' and version==2 and size==len(payload),filename
    json_size,json_type=struct.unpack_from('<II',payload,12)
    assert json_type==0x4e4f534a
    document=json.loads(payload[20:20+json_size])
    assert not document.get('cameras')
    assert not document.get('extensions',{}).get('KHR_lights_punctual')
    assert all(not buffer.get('uri') for buffer in document['buffers'])
    ids=[node.get('extras',{}).get('sceneops_id') for node in document.get('nodes',[]) if 'mesh' in node]
    assert all(ids) and len(ids)==len(set(ids)),entry['asset_id']
    for obj in list(bpy.context.scene.objects):bpy.data.objects.remove(obj,do_unlink=True)
    bpy.ops.import_scene.gltf(filepath=str(filename))
    bpy.context.view_layer.update()
    # Blender's importer creates mesh objects for bone display; these are not GLB asset geometry.
    bone_shapes={bone.custom_shape for obj in bpy.context.scene.objects if obj.type=='ARMATURE' for bone in obj.pose.bones if bone.custom_shape}
    objects=[obj for obj in bpy.context.scene.objects if obj.type=='MESH' and obj not in bone_shapes]
    points=[obj.matrix_world@Vector(corner) for obj in objects for corner in obj.bound_box]
    low=[min(p[i] for p in points) for i in range(3)]
    high=[max(p[i] for p in points) for i in range(3)]
    dimensions=[high[0]-low[0],high[2]-low[2],high[1]-low[1]]
    assert all(abs(a-b)<.005 for a,b in zip(dimensions,entry['dimensions_m'])),(filename,dimensions,entry['dimensions_m'])
    triangles=0
    for obj in objects:
        obj.data.calc_loop_triangles();triangles+=len(obj.data.loop_triangles)
    assert triangles==entry['triangle_count'],(filename,triangles,entry['triangle_count'])
    if entry['kind']=='character' and entry.get('silhouette_family')==f"{catalog['pack_id']}/traveler-v1":
        shape=[]
        for obj in objects:
            world_vertices=sorted(tuple(round(v,5) for v in obj.matrix_world@vertex.co) for vertex in obj.data.vertices)
            shape.append((obj.get('sceneops_id').split('/')[-1],world_vertices))
        role_shapes.append(sorted(shape))
        role_material=next(mat for obj in objects for mat in obj.data.materials if mat.name.split('.')[0]==entry['role'])
        principled=next(node for node in role_material.node_tree.nodes if node.type=='BSDF_PRINCIPLED')
        role_colors.append(tuple(round(v,5) for v in principled.inputs['Base Color'].default_value))
    if entry['kind']=='scene':
        depsgraph=bpy.context.evaluated_depsgraph_get()
        for spawn in entry['spawn_points']:
            x,y,z=spawn['position']
            for dx,dz in [(0,0),(.35,0),(-.35,0),(0,.35),(0,-.35)]:
                hit,point,*_=bpy.context.scene.ray_cast(depsgraph,Vector((x+dx,-z-dz,20)),Vector((0,0,-1)))
                assert hit and -.02<=point.z<=.13,(entry['asset_id'],spawn,point[:])
    assert (ROOT/entry['preview_path']).is_file()
    results.append({'asset_id':entry['asset_id'],'glb_bytes':len(payload),'triangles':triangles,'reimport':'passed',
                    'dimensions_m':[round(n,3) for n in dimensions]})
assert len(role_shapes)==4 and all(shape==role_shapes[0] for shape in role_shapes)
assert len(set(role_colors))==4
report={'pack_id':catalog['pack_id'],'blender_version':bpy.app.version_string,'checked_entries':len(results),
        'role_silhouettes':'original four travelers share geometry; new profession characters have separate silhouettes','spawn_clearance':'all scene spawns and 0.35m cardinal offsets clear',
        'external_dependencies':'none','checks':results}
(SOURCE_ROOT/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print('HAVEN_KIT_VERIFIED',len(results),flush=True)
