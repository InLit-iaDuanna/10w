"""Reusable character and prop geometry for the detailed collection, CC0."""
import math
import generate as g

def person(job):
    role={'medic':'ally','engineer':'npc','chef':'npc','guard':'enemy','explorer':'player','astronaut':'player'}[job]
    g.character(role)
    if job=='medic':
        g.box('medical-coat',(0,-.24,.9),(.59,.05,.5),'cream')
        g.box('medical-cap',(0,0,1.73),(.54,.46,.14),'cream')
        for dims in [(.05,.02,.14),(.14,.02,.05)]:g.box('red-cross',(0,-.245,1.73),dims,'red')
        g.box('medical-bag',(.6,0,.52),(.24,.35,.32),'cream')
    elif job=='engineer':
        g.cylinder('hardhat-brim',(0,0,1.7),.36,.06,'gold',16)
        g.ico('hardhat-dome',(0,0,1.72),(.31,.28,.2),'gold',2)
        for x in [-.2,.2]:g.box('vest-reflector',(x,-.22,.9),(.06,.02,.43),'cream')
        g.box('tool-case',(.63,0,.53),(.35,.3,.22),'metal')
    elif job=='chef':
        g.box('apron',(0,-.25,.77),(.52,.03,.55),'cream')
        g.cylinder('chef-hat',(0,0,1.8),.27,.38,'cream',12)
        for x in [-.16,0,.16]:g.ico('hat-fold',(x,0,2),(.14,.23,.14),'cream',2)
        g.cylinder('pan',(.65,-.12,.83),.21,.07,'metal',16)
        g.beam('pan-handle',(.4,-.12,.83),(.65,-.12,.83),.055,'wood')
    elif job=='guard':
        g.box('breastplate',(0,-.25,.94),(.59,.08,.42),'metal')
        g.box('helmet',(0,0,1.68),(.56,.47,.24),'stone_dark')
        g.box('shield',(-.57,-.16,.83),(.1,.52,.8),'metal')
        g.box('shield-boss',(-.64,-.16,.83),(.04,.2,.2),'gold')
    elif job=='explorer':
        g.cylinder('hat-brim',(0,0,1.72),.4,.06,'wood_light',12)
        g.cylinder('hat-crown',(0,0,1.84),.26,.21,'wood_light',12)
        g.box('backpack',(0,.36,.9),(.53,.28,.55),'leaf_dark')
        g.cylinder('bedroll',(0,.35,1.22),.12,.62,'cloth',10).rotation_euler.y=math.pi/2
    elif job=='astronaut':
        g.ico('helmet-shell',(0,0,1.5),(.39,.36,.4),'cream',3)
        g.ico('visor',(0,-.29,1.5),(.3,.12,.25),'ocean',3)
        g.box('life-support',(0,.4,.97),(.6,.32,.63),'cream')
        g.box('chest-console',(0,-.26,.96),(.4,.09,.3),'cream')
        for x in [-.1,.1]:g.box('console-button',(x,-.32,.98),(.06,.03,.06),'cyan')

def robot():
    for x in [-.25,.25]:
        g.box('robot-foot',(x,-.06,.12),(.3,.5,.24),'metal')
        g.cylinder('robot-leg',(x,0,.45),.1,.5,'copper',12)
    g.box('robot-body',(0,0,.96),(.7,.46,.65),'cream',.1)
    g.box('robot-face',(0,-.05,1.53),(.65,.5,.4),'metal',.1)
    for x in [-.18,.18]:g.box('robot-eye',(x,-.315,1.55),(.12,.04,.09),'cyan')
    for x in [-.5,.5]:
        g.cylinder('robot-arm',(x,0,.96),.08,.6,'copper',12)
        g.ico('robot-hand',(x,0,.64),(.13,.13,.13),'metal',2)
    g.cylinder('antenna',(0,0,1.9),.025,.3,'metal',8)
    g.ico('antenna-tip',(0,0,2.05),(.07,.07,.07),'neon',2)

def voxel_person():
    # Grid-aligned shapes, intentionally no rounded or beveled edges.
    for x in [-.16,.16]:
        g.box('voxel-boot',(x,-.04,.12),(.24,.4,.24),'boots',0)
        g.box('voxel-leg',(x,0,.4),(.24,.24,.4),'night',0)
    g.box('voxel-body',(0,0,.9),(.64,.32,.64),'cyan',0)
    g.box('voxel-head',(0,0,1.5),(.48,.48,.48),'skin',0)
    g.box('voxel-hair',(0,.04,1.74),(.48,.4,.16),'wood_dark',0)
    for x in [-.44,.44]:g.box('voxel-arm',(x,0,.88),(.24,.24,.64),'skin',0)
    for x in [-.12,.12]:g.box('pixel-eye',(x,-.245,1.54),(.08,.01,.08),'boots',0)

def storefront():
    g.box('shop-base',(0,0,.15),(3.8,2.8,.3),'stone')
    g.box('shop-walls',(0,0,1.55),(3.5,2.5,2.8),'plaster')
    for x in [-1.5,1.5]:g.box('shop-corner',(x,-1.3,1.5),(.15,.15,2.7),'wood')
    for x in [-.9,.9]:
        g.box('shop-window',(x,-1.28,1.5),(1.25,.07,1.5),'window')
        for dx in [-.62,0,.62]:g.box('window-mullion',(x+dx,-1.34,1.5),(.05,.06,1.5),'cream')
    g.box('shop-sign',(0,-1.38,2.6),(3.3,.12,.4),'wood')
    for i in range(8):g.box('striped-canopy',(-1.6+i*.45,-1.7,2.25),(.45,1,.1),'roof' if i%2 else 'cream')
    g.box('flat-roof',(0,0,3.02),(3.9,2.9,.18),'stone_dark')
    for x in [-1.7,1.7]:g.box('roof-trim',(x,0,3.2),(.12,2.8,.3),'plaster')

def planter():
    g.box('planter-body',(0,0,.32),(1.8,.8,.64),'wood_light')
    for x in [-.7,-.35,0,.35,.7]:g.box('planter-slat',(x,-.42,.32),(.05,.04,.64),'wood')
    g.box('planter-soil',(0,0,.65),(1.65,.65,.05),'earth')
    for x in [-.6,0,.6]:
        g.ico('plant-leaves',(x,0,.92),(.35,.3,.4),'leaf',2)
        g.ico('flower',(x,-.05,1.23),(.13,.13,.1),'pink',2)

def utility():
    g.box('utility-post',(0,0,2),(.17,.17,4),'wood')
    g.box('utility-crossarm',(0,0,3.6),(1.5,.15,.15),'wood_dark')
    for x in [-.6,0,.6]:g.cylinder('insulator',(x,0,3.78),.07,.25,'cream',8)
    g.box('junction-box',(.2,0,1.3),(.4,.25,.6),'metal')

def medical_cart():
    for z in [.25,.8]:g.box('cart-tray',(0,0,z),(.85,.6,.07),'cream')
    for x in [-.38,.38]:
        for y in [-.25,.25]:
            g.cylinder('cart-post',(x,y,.5),.025,.8,'metal',8)
            g.ico('caster',(x,y,.1),(.08,.08,.08),'boots',2)
    for x in [-.2,0,.2]:g.cylinder('medicine-bottle',(x,0,.95),.06,.23,'ice',12)

def dining():
    g.cylinder('table-post',(0,0,.4),.12,.8,'metal',12)
    g.cylinder('tabletop',(0,0,.85),.75,.1,'wood_light',24)
    for y in [-1.1,1.1]:
        g.box('chair-seat',(0,y,.45),(.6,.6,.1),'wood_light')
        g.box('chair-back',(0,y+(.25 if y>0 else -.25),.85),(.6,.08,.7),'wood')
        for x in [-.23,.23]:
            for dy in [-.23,.23]:g.box('chair-leg',(x,y+dy,.22),(.06,.06,.44),'wood')
    for y in [-.35,.35]:g.cylinder('plate',(0,y,.92),.2,.04,'cream',24)
    g.cylinder('cup',(.35,0,1),.08,.18,'cream',16)

def display():
    g.box('display-plinth',(0,0,.5),(1.4,.9,1),'cream')
    for x in [-.65,.65]:
        for y in [-.4,.4]:g.box('display-frame',(x,y,1.4),(.04,.04,.8),'gold')
    g.box('display-top',(0,0,1.8),(1.4,.9,.05),'gold')
    g.ico('exhibit',(0,0,1.28),(.3,.25,.3),'copper',2)
    g.box('exhibit-caption',(0,-.46,.8),(.5,.03,.2),'metal')

def railing():
    for x in [-1,0,1]:g.box('rail-post',(x,0,.55),(.07,.07,1.1),'metal')
    for z in [.25,.6,1.1]:g.box('rail-horizontal',(0,0,z),(2.15,.06,.06),'metal')

def pipe():
    g.beam('pipe',(-1,0,.6),(1,0,.6),.22,'copper')
    for x in [-.8,.8]:
        o=g.cylinder('flange',(x,0,.6),.23,.1,'metal',16);o.rotation_euler.y=math.pi/2
    g.beam('valve-stem',(0,0,.6),(0,0,1),.06,'metal')
    import bpy
    bpy.ops.mesh.primitive_torus_add(major_segments=16,minor_segments=6,location=(0,0,1),major_radius=.2,minor_radius=.035)
    g.finish(bpy.context.object,'valve-wheel','red')

def vending():
    g.box('vending-body',(0,0,1),(1.1,.8,2),'night',.06)
    for x in [-.3,0,.3]:
        for z in [.85,1.2,1.55]:g.cylinder('can',(x,-.44,z),.08,.23,'roof' if x<0 else 'cyan',12)
    g.box('vending-output',(0,-.42,.3),(.75,.06,.25),'boots')
    g.box('vending-header',(0,-.44,1.85),(.9,.05,.18),'neon')

def luggage():
    g.box('suitcase',(0,0,.45),(.6,.35,.8),'roof',.08)
    for x in [-.24,.24]:g.cylinder('suitcase-wheel',(x,0,.06),.07,.06,'boots',12).rotation_euler.x=math.pi/2
    for x in [-.15,.15]:g.box('handle-rail',(x,0,.95),(.025,.025,.35),'metal')
    g.box('luggage-handle',(0,0,1.12),(.34,.06,.06),'boots')

def voxel_tree():
    g.box('voxel-trunk',(0,0,1),(.32,.32,2),'wood',0)
    for z,w in [(1.8,1.6),(2.3,1.2),(2.8,.8)]:g.box('voxel-crown',(0,0,z),(w,w,.6),'leaf',0)

def pump():
    # Smooth curved parts and physically based metal, exported without procedural shader dependencies.
    import bpy
    g.COLORS.update(pbr_copper='B87545',pbr_steel='84929B')
    for name,metallic,roughness in [('pbr_copper',.85,.28),('pbr_steel',.92,.3)]:
        node=next(n for n in g.mat(name).node_tree.nodes if n.type=='BSDF_PRINCIPLED')
        node.inputs['Metallic'].default_value=metallic;node.inputs['Roughness'].default_value=roughness
    g.cylinder('pump-base',(0,0,.12),.7,.24,'pbr_steel',48)
    g.cylinder('pump-body',(0,0,.75),.4,1.2,'pbr_copper',48)
    g.cylinder('pump-neck',(0,0,1.5),.17,.4,'pbr_steel',48)
    for i in range(8):
        a=i*math.tau/8;g.cylinder('base-bolt',(.55*math.cos(a),.55*math.sin(a),.27),.045,.08,'pbr_steel',6)
    g.beam('pump-lever',(-.7,0,1.8),(.5,0,1.8),.08,'pbr_steel')
    for obj in g.OBJECTS:
        if obj.name.startswith('pump-'):
            for polygon in obj.data.polygons:polygon.use_smooth=True

def toolbench():
    g.box('bench-top',(0,0,.9),(2.3,.9,.13),'wood_light')
    for x in [-1,1]:
        for y in [-.35,.35]:g.box('bench-support',(x,y,.45),(.1,.1,.9),'metal')
    g.box('pegboard',(0,.4,1.55),(2.3,.08,1.1),'wood')
    for x in [-.8,-.4,0,.4,.8]:
        g.box('tool-handle',(x,.32,1.5),(.07,.07,.35),'roof')
        g.box('tool-head',(x,.32,1.75),(.2,.07,.12),'metal')

PROPS={
 'detailed-storefront':('模组沿街商铺','建筑',storefront),'flower-planter':('花卉种植箱','环境道具',planter),
 'utility-pole':('电力设施杆','城市设施',utility),'medical-cart':('医疗推车','室内道具',medical_cart),
 'dining-set':('双人餐桌椅','室内家具',dining),'exhibit-case':('开放式展品柜','展览道具',display),
 'metal-railing':('模组金属栏杆','建筑',railing),'valve-pipe':('法兰阀门管','工业设备',pipe),
 'vending-machine':('饮料自动售货机','城市设施',vending),'rolling-luggage':('拉杆行李箱','生活道具',luggage),
 'voxel-tree':('体素方冠树','体素植被',voxel_tree),'pbr-pump':('精细金属水泵','PBR设备',pump),
 'tool-bench':('挂板维修工作台','工业家具',toolbench),
}
CHARACTERS={f'person-{job}':(label,'职业角色',lambda job=job:person(job)) for job,label in [
 ('medic','医护人员'),('engineer','维修工程师'),('chef','餐厅厨师'),('guard','装甲守卫'),('explorer','背包探险家'),('astronaut','舱外宇航员')]}
CHARACTERS.update({'person-robot':('服务机器人','机械角色',robot),'person-voxel':('体素冒险者','体素角色',voxel_person)})
