"""Author segmented character skins and four reusable clips. Blender 5.1, CC0."""
import argparse,json,math,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
import bmesh
from mathutils import Vector
import generate as g
import expand,expand_v3
import detail_assets as a

BASE=g.ROOT
OUT=BASE/'revisions/v5'
CLIPS={'Idle':(60,30),'Walk':(30,30),'Run':(20,30),'Wave':(60,30)}

def uv(name,loc,scale,material):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24,ring_count=12,location=loc)
    obj=bpy.context.object;obj.scale=scale
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    for face in obj.data.polygons:face.use_smooth=True
    return g.finish(obj,name,material)

def clay():
    for x in [-.18,.18]:
        uv('boot',(x,-.05,.13),(.16,.25,.13),'clay_dark')
        uv('leg',(x,0,.4),(.13,.14,.3),'clay_coat')
        uv('sleeve',(x/abs(x)*.42,0,.96),(.14,.16,.26),'clay_coat')
        uv('hand',(x/abs(x)*.44,0,.66),(.13,.13,.15),'skin')
    uv('tunic',(0,0,.91),(.36,.24,.4),'clay_coat')
    uv('neck',(0,0,1.25),(.11,.11,.12),'skin')
    uv('head',(0,-.02,1.5),(.29,.26,.31),'skin')
    uv('hair',(0,.08,1.67),(.3,.24,.19),'clay_dark')
    for x in [-.11,.11]:uv('eye',(x,-.265,1.53),(.035,.022,.045),'boots')
    uv('nose',(0,-.28,1.46),(.055,.055,.07),'skin')
    for z in [.8,.97,1.12]:uv('coat-button',(0,-.23,z),(.035,.025,.035),'cream')

def enamel():
    a.robot()
    for obj in g.OBJECTS:
        material=obj.data.materials[0]
        obj.data.materials.clear();obj.data.materials.append(g.mat('enamel_red' if material.name.startswith('cream') else 'polished_metal' if material.name.startswith(('metal','copper')) else material.name.split('.')[0]))
    for x in [-.49,.49]:uv('shoulder-hub',(x,0,1.14),(.15,.17,.15),'polished_metal')
    uv('robot-face',(0,.04,1.53),(.4,.28,.3),'enamel_red')
    # Preserve forward eyes on a separate faceplate.
    g.box('robot-faceplate',(0,-.26,1.54),(.58,.1,.24),'polished_metal',.09)
    for x in [-.17,.17]:uv('robot-eye',(x,-.33,1.55),(.065,.04,.065),'cyan')

def clay_mushroom():
    uv('clay-stem',(0,0,.55),(.26,.24,.6),'cream')
    uv('clay-cap',(0,0,1.2),(.85,.8,.45),'clay_coat')
    for x,y in [(-.35,-.3),(.35,-.3),(0,.4)]:uv('clay-dot',(x,y,1.55),(.15,.13,.065),'cream')

def enamel_lamp():
    g.cylinder('lamp-base',(0,0,.1),.42,.2,'polished_metal',32)
    g.cylinder('lamp-pole',(0,0,1.1),.055,2,'polished_metal',24)
    g.cylinder('lamp-shade',(0,0,2),.55,.45,'enamel_red',32,.24)
    uv('lamp-bulb',(0,0,1.82),(.2,.2,.12),'lamp')

NEW={'person-clay':('黏土旅人','黏土',clay,'character'),'person-enamel':('搪瓷机器人','搪瓷',enamel,'character')}
NEW.update({'clay-mushroom':('手塑黏土蘑菇','黏土',clay_mushroom,'prop'),'enamel-lamp':('复古搪瓷落地灯','搪瓷',enamel_lamp,'prop')})

def materials():
    g.COLORS.update(clay_coat='B77961',clay_dark='675A54',enamel_red='C45549',polished_metal='9DAEB5')
    for name,metallic,roughness in [('clay_coat',0,.94),('clay_dark',0,.96),('enamel_red',.18,.22),('polished_metal',.9,.25)]:
        mat=g.mat(name);node=next(n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
        node.inputs['Metallic'].default_value=metallic;node.inputs['Roughness'].default_value=roughness
        if name=='enamel_red':node.inputs['Coat Weight'].default_value=.65

# Semantic bindings are authored for each source part, rather than proximity guesses.
HEAD={'head','hair','hair-back','eye','nose','neck','helmet','hardhat-brim','hardhat-dome','medical-cap','red-cross','chef-hat','hat-fold','hat-brim','hat-crown','helmet-shell','visor','robot-face','robot-faceplate','robot-eye','antenna','antenna-tip','voxel-head','voxel-hair','pixel-eye'}
CHEST={'tunic','belt','belt-buckle','scarf','scarf-tail','satchel','medical-coat','vest-reflector','apron','breastplate','backpack','bedroll','life-support','chest-console','console-button','robot-body','voxel-body','coat-button'}
HAND={'hand','medical-bag','tool-case','pan','pan-handle','shield','shield-boss','robot-hand'}
ARM={'sleeve','robot-arm','voxel-arm','shoulder-hub'}
LEG={'leg','robot-leg','voxel-leg'}
FOOT={'boot','robot-foot','voxel-boot'}

def split_rigid_limbs(objects):
    result=[]
    for obj in objects:
        name=obj.name.split('.')[0]
        if name not in {'robot-leg','voxel-leg','robot-arm','voxel-arm'}:
            result.append(obj);continue
        side='L' if obj.location.x>=0 else 'R'
        leg=name.endswith('leg');pivot=.34 if leg else .87
        for upper in [True,False]:
            part=obj.copy();part.data=obj.data.copy();bpy.context.collection.objects.link(part)
            mesh=bmesh.new();mesh.from_mesh(part.data)
            cut=bmesh.ops.bisect_plane(mesh,geom=list(mesh.verts)+list(mesh.edges)+list(mesh.faces),dist=1e-6,
                plane_co=part.matrix_world.inverted()@Vector((0,0,pivot)),
                plane_no=part.matrix_world.to_3x3().transposed()@Vector((0,0,1)),
                clear_inner=upper,clear_outer=not upper)
            edges=[edge for edge in cut['geom_cut'] if isinstance(edge,bmesh.types.BMEdge) and edge.is_boundary]
            if edges:bmesh.ops.holes_fill(mesh,edges=edges,sides=0)
            mesh.to_mesh(part.data);mesh.free()
            part['rig_bone']=(('Thigh.' if upper else 'Shin.') if leg else ('UpperArm.' if upper else 'Forearm.'))+side
            result.append(part)
        bpy.data.objects.remove(obj,do_unlink=True)
    return result

def make_rig(objects,key):
    objects=split_rigid_limbs(objects)
    arm=bpy.data.armatures.new(key+'-skeleton');rig=bpy.data.objects.new(key+'-rig',arm);bpy.context.collection.objects.link(rig)
    bpy.context.view_layer.objects.active=rig;rig.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
    def bone(name,head,tail,parent=None):
        b=arm.edit_bones.new(name);b.head=head;b.tail=tail
        if parent:b.parent=arm.edit_bones[parent]
    bone('Root',(0,0,0),(0,0,.15));bone('Hips',(0,0,.62),(0,0,.78),'Root')
    bone('Spine',(0,0,.78),(0,0,1.12),'Hips');bone('Head',(0,0,1.22),(0,0,1.7),'Spine')
    for side,x in [('L',1),('R',-1)]:
        bone('UpperArm.'+side,(x*.36,0,1.13),(x*.44,0,.87),'Spine')
        bone('Forearm.'+side,(x*.44,0,.87),(x*.44,0,.66),'UpperArm.'+side)
        bone('Hand.'+side,(x*.44,0,.66),(x*.44,0,.55),'Forearm.'+side)
        bone('Thigh.'+side,(x*.18,0,.62),(x*.18,0,.34),'Hips')
        bone('Shin.'+side,(x*.18,0,.34),(x*.18,0,.14),'Thigh.'+side)
        bone('Foot.'+side,(x*.18,0,.14),(x*.18,-.22,.1),'Shin.'+side)
    bpy.ops.object.mode_set(mode='OBJECT')
    for obj in objects:
        name=obj.name.split('.')[0];x=(obj.matrix_world@Vector((0,0,0))).x;side='L' if x>=0 else 'R'
        if 'rig_bone' in obj:binding=obj['rig_bone']
        elif name in HEAD:binding='Head'
        elif name in CHEST:binding='Spine'
        elif name in HAND:binding='Hand.'+side
        elif name in ARM:binding='UpperArm.'+side
        elif name in LEG:binding='Thigh.'+side
        elif name in FOOT:binding='Foot.'+side
        else:raise ValueError(f'Unmapped semantic mesh: {key}/{name}')
        # Rigid hard-surface pieces retain volume. Cloth limbs use linear weights
        # through authored elbow/knee zones, the standard linear skinning model.
        blend=name in {'sleeve','leg'} and key not in {'person-voxel'}
        if blend:
            secondary=('Forearm.' if name=='sleeve' else 'Shin.')+side
            pivot=.87 if name=='sleeve' else .34
            group=obj.vertex_groups.new(name=binding);other=obj.vertex_groups.new(name=secondary)
            for vertex in obj.data.vertices:
                z=(obj.matrix_world@vertex.co).z
                weight=max(0,min(1,(z-pivot+.07)/.14))
                if weight:group.add([vertex.index],weight,'REPLACE')
                if weight<1:other.add([vertex.index],1-weight,'REPLACE')
        else:obj.vertex_groups.new(name=binding).add(list(range(len(obj.data.vertices))),1,'REPLACE')
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects:obj.select_set(True)
    bpy.context.view_layer.objects.active=objects[0];bpy.ops.object.join();body=bpy.context.object
    body.name=key+'-skin';body['sceneops_id']=f'{g.PACK}/{key}/skinned-body';body['source_asset_id']=g.PACK+'-'+key
    body.parent=rig;modifier=body.modifiers.new('Armature deformation','ARMATURE');modifier.object=rig
    for b in rig.pose.bones:b.rotation_mode='XYZ'
    return rig,body

def animate(rig):
    rig.animation_data_create()
    for name,(duration,fps) in CLIPS.items():
        rig.animation_data.action=None
        for frame in range(0,duration+1,2):
            t=frame/duration;cycle=math.sin(t*math.tau)
            for b in rig.pose.bones:b.rotation_euler=(0,0,0);b.location=(0,0,0)
            if name=='Idle':
                rig.pose.bones['Spine'].rotation_euler.x=.018*cycle
                rig.pose.bones['Head'].rotation_euler.z=.025*cycle
            elif name in ['Walk','Run']:
                amplitude=.42 if name=='Walk' else .65
                for side,sign in [('L',1),('R',-1)]:
                    rig.pose.bones['Thigh.'+side].rotation_euler.x=amplitude*cycle*sign
                    rig.pose.bones['Shin.'+side].rotation_euler.x=-.45*max(0,cycle*sign)
                    rig.pose.bones['UpperArm.'+side].rotation_euler.x=-amplitude*.75*cycle*sign
                    rig.pose.bones['Forearm.'+side].rotation_euler.x=-.12*(1-math.cos(t*math.tau))
                rig.pose.bones['Hips'].location.y=.018*(1-math.cos(t*math.tau*2))
            else:
                envelope=math.sin(math.pi*t)**2
                rig.pose.bones['UpperArm.L'].rotation_euler.z=-2.45*envelope
                rig.pose.bones['Forearm.L'].rotation_euler.x=.45*math.sin(t*math.tau*3)*envelope
            for b in rig.pose.bones:
                b.keyframe_insert(data_path='rotation_euler',frame=frame,group=b.name)
                b.keyframe_insert(data_path='location',frame=frame,group=b.name)
        action=rig.animation_data.action;action.name=name
        track=rig.animation_data.nla_tracks.new();track.name=name
        strip=track.strips.new(name,0,action);strip.name=name
        track.mute=True
    rig.animation_data.action=None
    for b in rig.pose.bones:b.rotation_euler=(0,0,0);b.location=(0,0,0)
    for track in rig.animation_data.nla_tracks:track.mute=False
    bpy.context.scene.frame_set(0)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--only',default='');opts=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    chosen=set(opts.only.split(',')) if opts.only else None
    for folder in ['glb','previews','blend']:(OUT/folder).mkdir(parents=True,exist_ok=True)
    catalog=json.loads((BASE/'catalog.json').read_text());updates={}
    targets=[(e['asset_id'].removeprefix(g.PACK+'-'),e) for e in catalog['entries'] if e['kind']=='character']
    targets += [(key,None) for key in NEW if key not in {k for k,_ in targets}]
    for key,old in targets:
        if chosen and key not in chosen:continue
        bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False);g.M.clear();g.OBJECTS.clear();materials()
        if key in NEW:
            label,style,builder,kind=NEW[key];builder();objects=list(g.OBJECTS)
            for i,obj in enumerate(objects):obj['sceneops_id']=f'{g.PACK}/{key}/part-{i}';obj['source_asset_id']=g.PACK+'-'+key
            bpy.context.view_layer.update();entry=g.entry(key,label,style,objects,description=f'{style}风格的原创可复用{label}。')
            entry.update(kind=kind,art_style=style,silhouette_family=f'{g.PACK}/{key}-v5')
        else:
            bpy.ops.import_scene.gltf(filepath=str(BASE/old.get('rig_source_glb_path',old['glb_path'])))
            objects=[o for o in bpy.context.scene.objects if o.type=='MESH'];entry=dict(old);kind='character'
            entry['rig_source_glb_path']=old.get('rig_source_glb_path',old['glb_path'])
        bpy.context.view_layer.update()
        if kind=='character':
            rig,body=make_rig(objects,key);objects=[body];animate(rig)
            entry['rig']={'status':'skinned','bone_count':len(rig.data.bones),'skeleton':'SceneOps segmented humanoid v1','skeleton_id':'sceneops-humanoid-v1','animation_set_id':'sceneops-basic-locomotion-v1','root_motion':False,'facial_rig':False}
            entry['animations']=[{'name':n,'duration_seconds':frames/fps,'loop':n!='Wave'} for n,(frames,fps) in CLIPS.items()]
            entry['description']=entry['label']+'，已绑定骨骼与蒙皮，内含 Idle、Walk、Run、Wave 四段原地动画。可独立复用；没有面部或手指控制器。'
        bpy.ops.object.select_all(action='DESELECT')
        for obj in objects:obj.select_set(True)
        if kind=='character':rig.select_set(True)
        bpy.context.scene.render.fps=30;bpy.context.scene.frame_set(0);bpy.context.view_layer.update()
        entry['dimensions_m']=g.bounds(objects);entry['footprint_m']=[entry['dimensions_m'][0],entry['dimensions_m'][2]];entry['triangle_count']=g.triangles(objects)
        bpy.ops.export_scene.gltf(filepath=str(OUT/'glb'/f'{key}.glb'),export_format='GLB',use_selection=True,export_yup=True,export_extras=True,
            export_animations=kind=='character',export_animation_mode='NLA_TRACKS',export_force_sampling=True,export_nla_strips=True,
            export_skins=True,export_cameras=False,export_lights=False)
        # Keep a native authoring file with the actual armature and editable actions.
        if kind=='character':
            bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'blend'/f'{key}.blend'))
            entry['blend_path']=f'revisions/v5/blend/{key}.blend'
        g.presentation(objects)
        if kind=='character':rig.hide_render=False
        bpy.context.scene.render.filepath=str(OUT/'previews'/f'{key}.png');bpy.ops.render.render(write_still=True);g.clean_presentation()
        entry.update(version=5,glb_path=f'revisions/v5/glb/{key}.glb',preview_path=f'revisions/v5/previews/{key}.png')
        entry['source']['generator']='modules/asset-library/builtin-assets/source/rig_collection.py'
        updates[entry['asset_id']]=entry
        print('RIGGED_ASSET',key,flush=True)
    catalog['entries']=[updates.pop(e['asset_id'],e) for e in catalog['entries']]+list(updates.values());catalog['version']=5
    catalog['description']='36 套场景、52 件建筑与物件、14 个可动画角色；支持低多边形、体素、纸艺、黏土和搪瓷等风格，附像素图集与生成提示词。'
    (BASE/'catalog.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n')
    print('RIG_COLLECTION_COMPLETE',len(catalog['entries']),flush=True)

if __name__=='__main__':main()
