"""Original SceneOps Haven Kit. Run with Blender 5.1 in background mode.
All construction coordinates are Z-up meters; glTF export converts to Y-up.
No downloaded meshes, textures, models, or AI services are used.
"""
import argparse
import json
import math
from pathlib import Path
import sys
import bpy
from mathutils import Vector

SOURCE_ROOT = Path(__file__).resolve().parents[1]
ROOT = SOURCE_ROOT.parent / 'backend/src/asset_library/builtin_assets'
(ROOT/'glb').mkdir(parents=True, exist_ok=True)
(ROOT/'previews').mkdir(parents=True, exist_ok=True)
PACK = 'sceneops-haven-kit'
M = {}
COLORS = {
    'plaster':'EADAC0', 'cream':'FFF1D5', 'roof':'C66C4C', 'roof_light':'E19062',
    'wood':'715443', 'wood_light':'B58A5C', 'wood_dark':'413D3C',
    'leaf':'438C76', 'leaf_light':'68AE8A', 'leaf_dark':'306858',
    'stone':'8C9DA2', 'stone_light':'B8BEB0', 'stone_dark':'596B76',
    'ground':'A1AF82', 'grass':'789B75', 'earth':'75685A', 'sand':'C5AC83',
    'path':'D8C7A8', 'water':'5EBCBF', 'metal':'4B6571', 'window':'A5DAD4',
    'lamp':'FFE09A', 'skin':'E4B997', 'boots':'384853', 'player':'528FC8',
    'enemy':'C86761', 'npc':'DBB65D', 'ally':'66AB8B', 'cloth':'D4C69D',
}

def mat(name):
    if name in M: return M[name]
    value = COLORS[name]
    c = tuple(int(value[i:i+2],16)/255 for i in (0,2,4))
    c = tuple(v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4 for v in c)
    material = bpy.data.materials.new(name)
    material.diffuse_color = (*c,1)
    material.use_nodes = True
    material.node_tree.nodes.clear()
    bsdf = material.node_tree.nodes.new('ShaderNodeBsdfPrincipled')
    output = material.node_tree.nodes.new('ShaderNodeOutputMaterial')
    material.node_tree.links.new(bsdf.outputs['BSDF'],output.inputs['Surface'])
    bsdf.inputs['Base Color'].default_value = (*c,1)
    bsdf.inputs['Roughness'].default_value = .82
    if name == 'lamp':
        bsdf.inputs['Emission Color'].default_value = (*c,1)
        bsdf.inputs['Emission Strength'].default_value = .6
    M[name] = material
    return material

OBJECTS = []
def finish(obj, name, surface):
    obj.name = name
    obj.data.materials.append(mat(surface))
    OBJECTS.append(obj)
    return obj

def box(name, loc, scale, surface, bevel=.04, rotation=0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    obj = bpy.context.object
    obj.dimensions = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.rotation_euler.z = rotation
    if bevel:
        modifier = obj.modifiers.new('Crafted soft edges','BEVEL')
        modifier.width = bevel; modifier.segments = 1
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.modifier_apply(modifier=modifier.name)
    return finish(obj,name,surface)

def cylinder(name,loc,radius,depth,surface,vertices=10,radius_top=None):
    bpy.ops.mesh.primitive_cone_add(vertices=vertices, radius1=radius,
        radius2=radius if radius_top is None else radius_top, depth=depth, location=loc)
    return finish(bpy.context.object,name,surface)

def ico(name,loc,scale,surface,subdivisions=1):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=subdivisions,radius=1,location=loc)
    obj=bpy.context.object;obj.scale=scale
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    return finish(obj,name,surface)

def beam(name,a,b,width,surface):
    midpoint=(Vector(a)+Vector(b))*.5
    obj=box(name,midpoint,(width,width,(Vector(b)-Vector(a)).length),surface,.015)
    obj.rotation_euler=(Vector(b)-Vector(a)).to_track_quat('Z','Y').to_euler()
    return obj

def roof(name, width=3.8, depth=3.0, base=2.2, peak=3.3):
    vertices=[(-width/2,-depth/2,base),(width/2,-depth/2,base),(0,-depth/2,peak),
              (-width/2,depth/2,base),(width/2,depth/2,base),(0,depth/2,peak)]
    mesh=bpy.data.meshes.new(name)
    mesh.from_pydata(vertices,[],[(0,2,1),(3,4,5),(0,1,4,3),(0,3,5,2),(1,2,5,4)])
    obj=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(obj)
    finish(obj,name,'roof')
    beam('roof-ridge',(0,-depth/2-.06,peak),(0,depth/2+.06,peak),.14,'roof_light')
    for y in [-depth/2,depth/2]:
        beam('roof-edge',(-width/2,y,base),(0,y,peak),.13,'wood')
        beam('roof-edge',(width/2,y,base),(0,y,peak),.13,'wood')
    # Narrow raised strips read as hand-built roofing rather than a flat triangle.
    for y in [-depth*.3,0,depth*.3]:
        beam('roof-seam',(-width/2,y,base+.035),(0,y,peak+.035),.045,'roof_light')
        beam('roof-seam',(width/2,y,base+.035),(0,y,peak+.035),.045,'roof_light')

def cottage():
    box('foundation',(0,0,.17),(3.3,2.6,.34),'stone',.1)
    box('plaster-walls',(0,0,1.24),(3,2.35,2.15),'plaster',.08)
    for x in [-1.48,1.48]:
        for y in [-1.16,1.16]: box('corner-post',(x,y,1.35),(.17,.17,2.2),'wood')
    box('door-frame',(-.5,-1.22,.98),(.86,.15,1.62),'wood')
    box('door',(-.5,-1.32,.96),(.65,.07,1.42),'wood_light',.03)
    cylinder('door-handle',(-.29,-1.39,.95),.045,.055,'metal',8).rotation_euler.x=math.pi/2
    for x in [.85]:
        box('window-frame',(x,-1.24,1.45),(.74,.15,.83),'wood',.03)
        box('window-glass',(x,-1.33,1.46),(.56,.05,.64),'window',.02)
        box('window-cross',(x,-1.37,1.46),(.06,.035,.68),'cream',.008)
        box('window-cross',(x,-1.37,1.46),(.6,.035,.06),'cream',.008)
        box('flower-box',(x,-1.44,.98),(.9,.32,.22),'wood_light')
        for dx in [-.25,0,.25]: ico('herbs',(x+dx,-1.44,1.17),(.18,.19,.23),'leaf')
    roof('cottage-roof')
    box('chimney',(.93,.6,2.99),(.44,.5,1.1),'stone_light')
    box('chimney-cap',(.93,.6,3.55),(.57,.61,.17),'stone_dark')
    box('door-step',(-.5,-1.53,.1),(1,.6,.2),'stone_light',.08)

def watchtower():
    for x in [-.84,.84]:
        for y in [-.84,.84]: box('tower-leg',(x,y,1.45),(.22,.22,2.9),'wood')
    for y in [-.84,.84]:
        beam('tower-brace',(-.84,y,.25),(.84,y,2.4),.14,'wood_light')
        beam('tower-brace',(.84,y,.25),(-.84,y,2.4),.14,'wood_light')
    box('tower-deck',(0,0,2.7),(2.3,2.3,.18),'wood_light')
    for z in [2.98,3.35]:
        for y in [-1.03,1.03]:box('guard-rail',(0,y,z),(2.2,.11,.13),'wood')
        for x in [-1.03,1.03]:box('guard-rail',(x,0,z),(.11,2.2,.13),'wood')
    for x in [-1,1]:
        for y in [-1,1]:box('roof-support',(x,y,3.6),(.13,.13,1.9),'wood')
    roof('tower-canopy',2.65,2.65,4.22,4.92)
    for x in [-.34,.34]:beam('ladder-rail',(x,-1.52,.05),(x,-1.08,2.65),.1,'wood')
    for i in range(8):box('ladder-rung',(0,-1.48+i*.05,.25+i*.31),(.8,.09,.09),'wood_light',.01)

def ruin_arch():
    # A true open arch, with individually cut voussoirs and an unobstructed opening.
    for x in [-1.55,1.55]:
        for i in range(4):box('pillar-stone',(x,0,.28+i*.53),(.65,.75,.5),'stone_light' if i%2 else 'stone',.065)
        box('pillar-foot',(x,0,.12),(.9,.98,.24),'stone_dark',.06)
    for i in range(9):
        angle=math.pi*i/8
        x=1.55*math.cos(angle);z=2.1+1.55*math.sin(angle)
        obj=box('arch-stone',(x,0,z),(.6,.77,.55),'stone_light' if i%3 else 'stone',.06)
        obj.rotation_euler.y=math.pi/2-angle
    ico('fallen-masonry',(-2.1,-.45,.24),(.5,.44,.36),'stone')
    ico('moss',(-1.6,-.37,.12),(.47,.18,.17),'leaf_dark')

def pine():
    cylinder('pine-trunk',(0,0,.72),.19,1.44,'wood',7,.14)
    for z,r,h,s in [(1.5,1.08,1.6,'leaf_dark'),(2.2,.85,1.4,'leaf'),(2.8,.56,1.15,'leaf_light')]:
        cylinder('pine-crown',(0,0,z),r,h,s,7,0)

def broadleaf():
    cylinder('tree-trunk',(0,0,1.05),.23,2.1,'wood',7,.14)
    for a,b in [((0,0,1.2),(-.55,.1,2.05)),((0,0,1.5),(.63,.05,2.2))]:beam('branch',a,b,.14,'wood')
    for loc,scale,s in [((-.55,0,2.4),(1.02,.95,.95),'leaf'),((.57,.12,2.6),(.98,.88,1.1),'leaf_light'),((0,.2,3.08),(.9,.9,.9),'leaf')]:ico('canopy',loc,scale,s,2)

def rock_cluster():
    for loc,scale,s in [((0,0,.48),(.95,.72,.67),'stone'),((.76,.16,.23),(.52,.48,.38),'stone_light'),((-.62,-.32,.18),(.43,.37,.28),'stone_dark')]:ico('rock',loc,scale,s)

def crate():
    box('crate-body',(0,0,.44),(.86,.86,.86),'wood_light')
    for z in [.09,.79]:
        for y in [-.44,.44]:box('crate-rail',(0,y,z),(.96,.085,.14),'wood',.015)
    for x in [-.4,.4]:
        for y in [-.44,.44]:box('crate-upright',(x,y,.44),(.14,.085,.88),'wood',.01)
    beam('crate-diagonal',(-.33,-.5,.14),(.33,-.5,.74),.1,'wood')

def barrel():
    cylinder('barrel',(0,0,.5),.42,1,'wood_light',12,.37)
    for z,r in [(.12,.418),(.52,.399),(.89,.382)]:cylinder('iron-band',(0,0,z),r,.08,'metal',12)
    cylinder('barrel-lid',(0,0,1.01),.36,.06,'wood',12)
    for x in [-.16,0,.16]:box('lid-joint',(x,0,1.045),(.016,.61,.014),'wood_dark',0)

def lamp():
    box('lamp-base',(0,0,.1),(.45,.45,.2),'stone_dark',.07)
    box('lamp-post',(0,0,1.25),(.12,.12,2.35),'wood')
    beam('lamp-arm',(0,0,2.32),(.5,0,2.32),.11,'wood')
    beam('lamp-brace',(0,0,2.02),(.42,0,2.32),.08,'wood')
    box('lantern',(.47,0,1.94),(.3,.3,.44),'lamp',.035)
    for z in [1.68,2.2]:box('lantern-cap',(.47,0,z),(.4,.4,.09),'metal',.045)
    for x in [.32,.62]:
        for y in [-.15,.15]:box('lantern-frame',(x,y,1.94),(.035,.035,.48),'metal',.005)

def fence():
    for x in [-1,0,1]:box('fence-post',(x,0,.6),(.16,.18,1.2),'wood',.035)
    for z in [.43,.92]:box('fence-rail',(0,0,z),(2.3,.12,.14),'wood_light',.025)

def well():
    for i in range(12):
        a=i*math.tau/12
        box('well-stone',(math.cos(a)*.75,math.sin(a)*.75,.43),(.43,.33,.7),'stone_light' if i%2 else 'stone',.035,rotation=a+math.pi/2)
    cylinder('water',(0,0,.26),.64,.06,'water',24)
    for x in [-.92,.92]:box('well-post',(x,0,1.2),(.15,.17,2.4),'wood')
    roof('well-roof',2.25,1.7,2.2,2.85)
    beam('axle',(-.95,0,1.72),(.95,0,1.72),.11,'wood_light')
    cylinder('rope',(0,0,1.2),.025,.94,'cloth',6)
    cylinder('bucket',(0,0,.79),.19,.3,'wood_light',10,.22)

def campfire():
    for i in range(8):
        a=i*math.tau/8
        ico('hearth-stone',(math.cos(a)*.53,math.sin(a)*.53,.13),(.22,.18,.17),'stone')
    for a in [-.5,.5]:
        beam('firewood',(-.4,a*.4,.12),(.4,-a*.4,.16),.13,'wood_dark')
    ico('flame',(0,0,.44),(.28,.24,.51),'roof_light')
    ico('flame-core',(0,-.1,.32),(.15,.14,.32),'lamp')

def tent():
    mesh=bpy.data.meshes.new('tent-cloth')
    mesh.from_pydata([(-1.4,-1.1,0),(1.4,-1.1,0),(0,-1.1,1.9),(-1.4,1.1,0),(1.4,1.1,0),(0,1.1,1.9)],[],[(0,3,5,2),(1,2,5,4),(3,4,5)])
    obj=bpy.data.objects.new('tent-cloth',mesh);bpy.context.collection.objects.link(obj);finish(obj,'tent-cloth','cloth')
    for y in [-1.1,1.1]:beam('tent-pole',(0,y,0),(0,y,2.05),.085,'wood')
    beam('tent-ridge',(0,-1.2,1.9),(0,1.2,1.9),.085,'wood')
    # Dark inner mat keeps the front visibly open.
    box('sleeping-mat',(0,.1,.055),(1.45,1.75,.08),'leaf_dark',.06)
    for x in [-1.8,1.8]:
        for y in [-1.45,1.45]:
            cylinder('tent-peg',(x,y,.09),.045,.18,'wood',6)
            beam('guy-rope',(x,y,.15),(x*.76,y*.74,.4),.022,'cream')

def signpost():
    box('sign-post',(0,0,.9),(.13,.15,1.8),'wood')
    box('direction-sign',(.18,-.035,1.47),(1.22,.17,.3),'wood_light',.04,rotation=-.05)
    box('direction-sign',(-.12,-.04,1.05),(1,.17,.28),'wood_light',.04,rotation=.08)
    # Symbolic trail marks rather than unreadable fake text.
    for x in [-.14,.03,.2]:box('painted-mark',(x,-.128,1.47),(.07,.01,.11),'cream',.005)

def path_tile():
    for loc,scale in [((-.4,-.32,.055),(.76,.58,.11)),((.39,-.3,.055),(.7,.61,.11)),((-.34,.36,.055),(.85,.58,.11)),((.48,.37,.055),(.55,.65,.11))]:box('paving-stone',loc,scale,'path',.075)

def grass_clump():
    for x,y,h in [(-.21,0,.32),(0,.07,.44),(.21,-.06,.27),(.08,-.2,.24)]:
        cylinder('grass-blade',(x,y,h/2),.075,h,'grass',3,0)

def ground_tile():
    box('ground',(0,0,-.15),(4,4,.3),'ground',.17)

def character(role):
    # Same construction for every role; the role affects only tunic/scarf colors.
    for x in [-.18,.18]:
        box('boot',(x,-.065,.11),(.27,.44,.22),'boots',.055)
        box('leg',(x,0,.38),(.22,.26,.42),'wood_dark',.035)
    box('tunic',(0,0,.84),(.65,.4,.68),role,.10)
    box('belt',(0,-.005,.68),(.68,.425,.1),'wood',.02)
    box('belt-buckle',(0,-.232,.68),(.11,.035,.105),'lamp',.01)
    for x in [-.44,.44]:
        box('sleeve',(x,0,.92),(.22,.31,.39),role,.055)
        box('hand',(x,-.005,.68),(.19,.25,.2),'skin',.05)
    cylinder('neck',(0,0,1.23),.11,.16,'skin',8)
    box('head',(0,-.02,1.43),(.49,.43,.44),'skin',.11)
    box('hair',(0,.015,1.61),(.53,.47,.2),'wood_dark',.065)
    box('hair-back',(0,.17,1.48),(.5,.14,.31),'wood_dark',.035)
    for x in [-.1,.1]:box('eye',(x,-.245,1.45),(.055,.022,.062),'boots',.009)
    box('scarf',(0,0,1.18),(.54,.47,.15),role,.045)
    box('scarf-tail',(.2,.25,.98),(.15,.055,.37),role,.025)
    box('satchel',(.34,.11,.62),(.22,.25,.25),'wood_light',.045)

BUILDERS = {
    'cottage':('暖陶小屋','建筑',cottage), 'watchtower':('木构瞭望塔','建筑',watchtower),
    'ruin-arch':('遗迹石拱','建筑',ruin_arch), 'pine':('层叠松树','植被',pine),
    'broadleaf':('团簇阔叶树','植被',broadleaf), 'rock-cluster':('风化岩簇','自然',rock_cluster),
    'crate':('加固木箱','道具',crate), 'barrel':('铁箍木桶','道具',barrel),
    'lamp':('暖光路灯','道具',lamp), 'fence':('双横木篱','建筑',fence),
    'well':('覆顶石井','道具',well), 'campfire':('石圈营火','道具',campfire),
    'tent':('旅人帐篷','建筑',tent), 'signpost':('岔路指示牌','道具',signpost),
    'grass-clump':('野草簇','植被',grass_clump),
    'path-tile':('错缝石径','地面',path_tile), 'ground-tile':('草土地块','地面',ground_tile),
}
for role,label in [('player','蓝衣旅人'),('enemy','红衣对手'),('npc','金衣居民'),('ally','绿衣伙伴')]:
    BUILDERS['character-'+role]=(label,'角色',lambda role=role:character(role))

ASSETS={}
def bake_assets():
    for key,(label,category,builder) in BUILDERS.items():
        OBJECTS.clear();builder();objects=list(OBJECTS)
        for i,obj in enumerate(objects):
            obj['sceneops_id']=f'{PACK}/{key}/part-{i:02d}'
            obj['source_asset_id']=f'{PACK}-{key}'
            obj.hide_render=True;obj.hide_set(True)
        ASSETS[key]=objects

def instance(key,x,y,rotation=0,scale=1,height=0):
    items=[]
    rot=math.radians(rotation)
    for source in ASSETS[key]:
        obj=source.copy();obj.data=source.data
        bpy.context.collection.objects.link(obj)
        p=source.location*scale
        obj.location=(x+math.cos(rot)*p.x-math.sin(rot)*p.y,
                      y+math.sin(rot)*p.x+math.cos(rot)*p.y,p.z+height)
        obj.rotation_euler=source.rotation_euler.copy();obj.rotation_euler.z+=rot
        obj.scale=source.scale*scale
        obj.hide_render=False;obj.hide_set(False)
        obj['sceneops_id']=f'{PACK}/{CURRENT_SCENE}/{key}-{INSTANCE_COUNTS.get(key,0)}/{source.name}'
        items.append(obj)
    INSTANCE_COUNTS[key]=INSTANCE_COUNTS.get(key,0)+1
    OBJECTS.extend(items)
    return items

CURRENT_SCENE='';INSTANCE_COUNTS={}
def terrain(surface='ground'):
    box('terrain-stratum',(0,0,-.45),(21,18,.88),'earth',.8)
    box('terrain-top',(0,0,-.13),(20.8,17.8,.25),surface,.7)

def path_line(a,b):
    distance=(Vector(b)-Vector(a)).length
    steps=max(1,round(distance/1.25))
    for i in range(steps+1):
        t=i/steps;instance('path-tile',a[0]*(1-t)+b[0]*t,a[1]*(1-t)+b[1]*t)

def village():
    terrain();path_line((0,-7.5),(0,5.5));path_line((-7.5,-1),(7.5,-1))
    instance('cottage',-5,4,-12);instance('cottage',5,4,12)
    instance('watchtower',7.8,6.5,-8,.82);instance('well',0,2.4,0,.9)
    for x,y,s in [(-8,6,1.1),(-8,-4,1),(-5,-6,.9),(8,-5,1),(3.5,7,1.05)]:instance('broadleaf',x,y,0,s)
    for x,y in [(-7,1.6),(-7,-.7),(7,1.6)]:instance('fence',x,y,90)
    for x,y in [(-2.1,-2.2),(2.1,4.5),(6,-2.3)]:instance('lamp',x,y)
    instance('crate',-3.1,3);instance('barrel',-3.3,4.1);instance('signpost',-1.6,-6)
    instance('rock-cluster',7,-6.5,20,.8);instance('rock-cluster',-8,3,40,.7)
    instance('character-npc',-4,1.7,10);instance('character-ally',3.7,.8,-30)
    for x,y in [(-7.1,5.4),(-7.2,-3.8),(-5.5,-5.5),(7.6,-4.4),(4,6.5),(-3.7,4.9),(6,4.9),(7.4,2.4),(-8,1)]:instance('grass-clump',x,y,25,1.2)
    instance('character-player',0,-4.7,0,height=.12)

def forest():
    terrain();path_line((-3,-7),(-1,-2));path_line((-1,-2),(4,2))
    for x,y,s in [(-8,-4,1.1),(-8,0,1.3),(-7,5,1.2),(-4,7,1.25),(0,7.2,1.1),(6,6.5,1.3),(8,3,1.2),(8,-2,1),(6,-6,1.1)]:instance('pine',x,y,0,s)
    instance('broadleaf',-6,-6,0,.85);instance('tent',4,2,-20,1.1)
    instance('campfire',0,.6,0,1.25);instance('ruin-arch',-4.5,4,20,.8)
    for x,y,r in [(-1.6,1.3,25),(1.5,1.6,-30)]:instance('rock-cluster',x,y,r,.65)
    instance('crate',5.7,.5);instance('barrel',6,1.6);instance('signpost',-4,-4.5,-15)
    instance('lamp',2.2,3.8);instance('character-player',-1.2,-2.2,height=.12)
    instance('character-ally',1.3,.3,65);instance('character-npc',3.3,1.1,15)
    for x,y in [(-6,5),(-5,6),(-7,-3),(7,2),(6,5),(5,-4),(-5,-5)]:instance('grass-clump',x,y,35,1.5)
    instance('rock-cluster',-7,2,30,1.4);instance('rock-cluster',5,-5,-40,1.2)

def outpost():
    terrain('sand');path_line((0,-7),(0,5));path_line((-6,-1),(6,-1))
    instance('ruin-arch',0,4.8,0,1.15);instance('watchtower',6,3.5,-10,1.1)
    instance('cottage',-5.4,4,5,.9)
    for x,y,s,r in [(-8,-5,1.4,15),(-8,1.5,1.3,70),(8,-5,1.4,0),(7,7,1,30),(-5,7,1.3,15)]:instance('rock-cluster',x,y,r,s)
    for x,y,r in [(-5.8,-3.1,0),(4.8,-3.3,0),(-7,-1.8,90),(7,-1.8,90)]:instance('fence',x,y,r)
    for x,y in [(-2.4,2.8),(2.4,2.8),(-2,-4.8)]:instance('lamp',x,y)
    for x,y,r in [(4,1,0),(4.8,.9,15),(-4.3,1.1,-10)]:instance('crate',x,y,r)
    instance('barrel',5.5,.5);instance('barrel',-4.4,2.1);instance('signpost',1.8,-5.8,-15)
    instance('character-enemy',1.4,3.7,0);instance('character-npc',-4,.2,20);instance('character-player',0,-4.6,0,height=.12)

SCENES={
    'village-courtyard':('暖陶村落广场','场景',village,'以覆顶石井为中心的村落。石径连接双侧小屋，树冠和路灯围合出清楚的可行走广场。',[(0,-6,.12),(2,-1,.12)],'afternoon'),
    'forest-camp':('松影林间营地','场景',forest,'松树环抱的旅人营地。帐篷、营火与旧石拱形成三角构图，入口小径通往宽敞的中央空地。',[(-2,-5,.12),(2,-1,.12)],'morning'),
    'abandoned-outpost':('余晖荒原驿站','场景',outpost,'暖沙色荒原上的旧驿站。石拱、木塔和陶顶屋构成远景轮廓，中轴与横向街道留出连续通行空间。',[(0,-6,.12),(-2,-1,.12)],'sunset'),
}

def bounds(objects):
    points=[obj.matrix_world@Vector(corner) for obj in objects if obj.type=='MESH' for corner in obj.bound_box]
    low=[min(p[i] for p in points) for i in range(3)]
    high=[max(p[i] for p in points) for i in range(3)]
    # glTF x/y/z = Blender x/z/-y.
    return [round(high[0]-low[0],3),round(high[2]-low[2],3),round(high[1]-low[1],3)]

def triangles(objects):
    count=0
    for obj in objects:
        if obj.type=='MESH':obj.data.calc_loop_triangles();count+=len(obj.data.loop_triangles)
    return count

def export(key,objects):
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects:obj.hide_set(False);obj.hide_render=False;obj.select_set(True)
    bpy.context.view_layer.update()
    bpy.ops.export_scene.gltf(filepath=str(ROOT/'glb'/f'{key}.glb'),export_format='GLB',
        use_selection=True,export_yup=True,export_extras=True,export_animations=False,
        export_cameras=False,export_lights=False,export_materials='EXPORT')

RENDER_OBJECTS=[]
def presentation(objects,is_scene=False,mood='afternoon'):
    for obj in bpy.context.scene.objects:obj.hide_render=True
    for obj in objects:obj.hide_render=False
    scene=bpy.context.scene
    scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=24 if is_scene else 12
    scene.cycles.use_denoising=True
    scene.render.resolution_x=1200 if is_scene else 480
    scene.render.resolution_y=900 if is_scene else 480
    scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG';scene.render.film_transparent=False
    scene.world.color=(.3,.3,.3)
    world=scene.world;world.use_nodes=True
    world.node_tree.nodes.clear()
    background=world.node_tree.nodes.new('ShaderNodeBackground')
    output=world.node_tree.nodes.new('ShaderNodeOutputWorld')
    world.node_tree.links.new(background.outputs[0],output.inputs[0])
    background.inputs[0].default_value=(.33,.43,.52,1)
    background.inputs[1].default_value=.45
    scene.view_settings.view_transform='AgX'
    scene.view_settings.look='AgX - Medium High Contrast'
    scene.view_settings.exposure=.4
    # Seamless studio surface catches true rendered shadows beyond the display island.
    floor=box('preview-studio',(0,0,-1.03 if is_scene else -.03),(200,200,.05),'cream',0)
    floor.hide_render=False;RENDER_OBJECTS.append(floor)
    bpy.ops.object.light_add(type='AREA',location=(-7,-10,17))
    key=bpy.context.object;key.name='preview-key';key.data.energy=2100 if is_scene else 900
    key.data.shape='DISK';key.data.size=8 if is_scene else 5
    key.data.color=(1,.78,.57) if mood=='sunset' else (1,.9,.75)
    key.rotation_euler=(Vector((0,0,0))-key.location).to_track_quat('-Z','Y').to_euler();RENDER_OBJECTS.append(key)
    bpy.ops.object.light_add(type='AREA',location=(9,3,12))
    fill=bpy.context.object;fill.name='preview-fill';fill.data.energy=1200 if is_scene else 650;fill.data.size=10
    fill.data.color=(.65,.8,1);fill.rotation_euler=(-fill.location).to_track_quat('-Z','Y').to_euler();RENDER_OBJECTS.append(fill)
    bpy.ops.object.camera_add()
    camera=bpy.context.object;camera.name='preview-camera';camera.data.type='ORTHO';RENDER_OBJECTS.append(camera)
    dimensions=bounds(objects)
    center=Vector((0,0,1 if is_scene else dimensions[1]*.43))
    camera.location=center+Vector((23,-29,24) if is_scene else (7,-10,7))
    camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
    camera.data.ortho_scale=31 if is_scene else max(dimensions[0],dimensions[1],dimensions[2])*1.8+.5
    camera.data.lens=45;scene.camera=camera
    for obj in RENDER_OBJECTS:obj.hide_render=False


def clean_presentation():
    for obj in RENDER_OBJECTS:bpy.data.objects.remove(obj,do_unlink=True)
    RENDER_OBJECTS.clear()

def entry(key,label,category,objects,description='',spawns=None,mood='afternoon'):
    dimensions=bounds(objects)
    is_scene=key in SCENES
    return {'asset_id':f'{PACK}-{key}','label':label,'description':description or f'暖陶与青绿配色的原创低多边形{label}，可独立复用。',
      'kind':'scene' if is_scene else 'character' if key.startswith('character-') else 'prop',
      'category':category,'version':1,'mode':'cached','glb_path':f'glb/{key}.glb',
      'preview_path':f'previews/{key}.png','dimensions_m':dimensions,'footprint_m':[dimensions[0],dimensions[2]],
      'triangle_count':triangles(objects),'coordinate_system':'right-handed, Y-up, meters',
      'spawn_points':[{'id':f'spawn-{i+1}','position':[x,z,-y],'heading_radians':0} for i,(x,y,z) in enumerate(spawns or [])],
      'lighting':{'preset':mood,'ambient_color':'#9BB7CC','ambient_intensity':.7,
        'key_color':'#FFD0A0' if mood=='sunset' else '#FFF1D5','key_position':[ -7,17,10 ],'key_intensity':2.5},
      'source':{'creator':'SceneOps','method':'original procedural Blender geometry','generation_mode':'live',
         'generator':'modules/asset-library/builtin-assets/source/generate.py','license':'CC0-1.0'},
      **({'role':key.removeprefix('character-'),'role_color':'#'+COLORS[key.removeprefix('character-')],
          'silhouette_family':f'{PACK}/traveler-v1'} if key.startswith('character-') else {})}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--only',default='');parser.add_argument('--skip-render',action='store_true')
    options=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    bake_assets();bpy.context.view_layer.update();catalog=[]
    for key,(label,category,_) in BUILDERS.items():
        objects=ASSETS[key]
        if not options.only or key in options.only.split(','):
            export(key,objects)
            if not options.skip_render:
                presentation(objects);bpy.context.scene.render.filepath=str(ROOT/'previews'/f'{key}.png');bpy.ops.render.render(write_still=True);clean_presentation()
        catalog.append(entry(key,label,category,objects))
        for obj in objects:obj.hide_render=True;obj.hide_set(True)
    global CURRENT_SCENE
    for key,(label,category,builder,description,spawns,mood) in SCENES.items():
        CURRENT_SCENE=key;INSTANCE_COUNTS.clear();OBJECTS.clear();builder();objects=list(OBJECTS)
        for i,obj in enumerate(objects):
            if 'sceneops_id' not in obj:obj['sceneops_id']=f'{PACK}/{key}/terrain-{i}'
        bpy.context.view_layer.update()
        if not options.only or key in options.only.split(','):
            export(key,objects)
            if not options.skip_render:
                presentation(objects,True,mood);bpy.context.scene.render.filepath=str(ROOT/'previews'/f'{key}.png');bpy.ops.render.render(write_still=True);clean_presentation()
        catalog.append(entry(key,label,category,objects,description,spawns,mood))
        for obj in objects:bpy.data.objects.remove(obj,do_unlink=True)
    (ROOT/'catalog.json').write_text(json.dumps({'pack_id':PACK,'version':1,'label':'暖陶与松影 · 可复用场景套装','license':'CC0-1.0',
        'description':'同一美术语言的旅人角色、村落道具和三套可直接使用的完整场景。','entries':catalog},ensure_ascii=False,indent=2)+'\n')
    print('HAVEN_KIT_COMPLETE',len(catalog),flush=True)

if __name__=='__main__':main()
