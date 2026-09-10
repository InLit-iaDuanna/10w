"""Detailed composition additions, with clear entry and central traversal lanes."""
import math
import generate as g

def place(key,points,scale=1):
    for x,y in points:g.instance(key,x,y,scale=scale)

def enrich(theme):
    roles={'hospital':('medic','robot'),'school':('explorer','engineer'),'museum':('guard','explorer'),
      'kitchen':('chef','chef'),'arcade':('explorer','robot'),'underwater':('astronaut','robot'),
      'volcano':('explorer','guard'),'bamboo':('explorer','guard'),'gothic':('guard','explorer'),
      'steampunk':('engineer','robot'),'western':('explorer','guard'),'candy':('chef','explorer'),
      'boardgame':('guard','robot'),'basketball':('explorer','engineer'),'factory':('engineer','robot'),
      'airport':('engineer','explorer'),'temple':('explorer','guard'),'rooftop':('explorer','robot'),
      'cyber':('robot','guard'),'space':('astronaut','robot'),'zen':('explorer','chef'),
      'snow':('astronaut','engineer'),'dungeon':('guard','explorer'),'farm':('chef','explorer'),
      'harbor':('engineer','explorer'),'desert':('explorer','guard'),'dream':('explorer','robot'),
      'race':('engineer','robot'),'arena':('guard','engineer'),'market':('chef','explorer')}
    for role,x,y in [(roles[theme][0],-2.6,-3),(roles[theme][1],2.7,-1.6)]:
        g.instance('person-'+role,x,y,rotation=20 if x<0 else -30)
    indoor=theme in ['hospital','school','museum','kitchen','arcade','factory']
    if indoor:
        # Ceiling is deliberately absent for inspection; rear trim and skirting finish the cutaway.
        for z in [.16,3.28]:g.box('interior-trim',(0,7.8,z),(17.8,.1,.12),'wood_light')
        for x in [-7,-3,3,7]:
            g.box('wall-sconce',(x,7.65,2.8),(.5,.15,.12),'lamp')
        place('flower-planter',[(-7,-5),(7,-5)],.7)
    else:
        # Repeated boundary fixtures make the display island read as a finished environment.
        nature=theme in ['bamboo','zen','farm','dream','desert','western','temple','underwater','volcano']
        fixture='rock-cluster' if nature else 'metal-railing'
        place(fixture,[(-8,-6),(8,-6),(-8,7),(8,7)],.7)
    if theme=='cyber':
        for x in [-6,6]:
            for y in [0,5]:
                for z in [1,2,3]:
                    for dx in [-1,0,1]:g.box('facade-mullion',(x+dx,y-1.56,z),(.06,.06,.7),'metal')
                g.box('rooftop-ac',(x,y,4.25 if y==0 else 6.25),(1.2,.8,.5),'metal')
            g.instance('vending-machine',x,-2.4)
            g.instance('utility-pole',x,-5)
        for x in [-6,6]:
            for y,h in [(0,4),(5,6)]:
                for z in range(1,h):
                    for dx in [-.9,0,.9]:
                        g.box('recessed-window',(x+dx,y-1.54,z),(.68,.06,.62),'ocean')
                        g.box('window-hood',(x+dx,y-1.66,z+.34),(.78,.25,.07),'metal')
                g.box('shopfront-awning',(x,y-1.95,2.15),(3.3,.9,.12),'neon' if x>0 else 'cyan')
                g.box('shop-door-frame',(x,y-1.62,.95),(1.05,.12,1.9),'metal')
                g.box('shop-door',(x,y-1.71,.96),(.86,.05,1.72),'night')
                g.box('door-handle',(x+.3,y-1.77,1),(.04,.04,.36),'cyan')
                for dx in [-1.25,1.25]:
                    g.box('service-column',(x+dx,y-1.63,1),(.17,.2,2),'metal')
                g.beam('roof-antenna',(x+.8,y,h),(x+.8,y,h+1),.04,'metal')
                g.box('antenna-crossbar',(x+.8,y,h+.7),(.7,.05,.04),'metal')
        place('flower-planter',[(-3,3),(3,3)])
        g.instance('rolling-luggage',-2,-2)
    elif theme in ['space','snow']:
        for x in [-6,6]:
            for dx in [-1.3,0,1.3]:
                g.box('habitat-panel-seam',(x+dx,1.95 if theme=='snow' else .44,1.2),(.035,.04,2),'metal')
            g.instance('valve-pipe',x,-.5)
            g.instance('tool-bench',x,-3)
            for y in [2,4,6]:
                g.box('solar-panel',(x+(-3 if x<0 else 3),y,1),(1.3,1.4,.12),'ocean')
                for dx in [-.4,0,.4]:g.box('solar-cell',(x+(-3 if x<0 else 3)+dx,y,1.07),(.02,1.3,.02),'ice')
        for x in [-6,6]:
            front=1.94 if theme=='snow' else .43
            g.box('airlock-frame',(x,front,1.2),(1.5,.18,2.3),'metal')
            g.box('airlock-door',(x,front-.12,1.2),(1.25,.06,2.05),'ice')
            g.box('door-seal',(x,front-.16,1.2),(.06,.025,2.05),'metal')
            for dx in [-.42,.42]:g.box('airlock-handle',(x+dx,front-.2,1.2),(.05,.04,.35),'gold')
            for z in [.4,.8,1.2,1.6,2,2.4]:g.box('service-ladder',(x+1.65,front-.1,z),(.6,.1,.05),'metal')
            g.box('roof-vent',(x,4,2.65 if theme=='snow' else 3.15),(1.3,.8,.3),'metal')
        place('crate',[(-3,5),(3,5)],.75)
    elif theme in ['zen','bamboo']:
        for x in [-3,3]:
            for y in [0,4]:g.instance('lamp',x,y,scale=.6)
        place('flower-planter',[(-3,-4),(3,-4)])
        g.instance('dining-set',-3,2,scale=.7)
        for x in [-6,6]:
            for y in [0,3]:g.instance('grass-clump',x,y,scale=1.4)
        g.instance('signpost',2,-6)
    elif theme=='dungeon':
        for x in [-5,5]:
            for y in [-1,2,5]:
                g.box('wall-buttress',(x,y,1.3),(.5,.5,2.6),'stone_dark')
                g.box('pillar-cap',(x,y,2.65),(.8,.8,.18),'stone')
            g.instance('gallery-statue',x,6,scale=.8)
        g.instance('tool-bench',-4,0)
        place('barrel',[(4,0),(4.7,.2)])
        place('rock-cluster',[(-6,-4),(6,-4)],.5)
    elif theme=='farm':
        for x in [-6,5]:
            for y in [-3,-1,1]:
                for dx in [-1.1,-.4,.4,1.1]:
                    g.ico('ripe-crop',(x+dx,y,.45),(.18,.18,.22),'roof_light')
        place('fence',[(-8,2),(8,2)],1)
        g.instance('tool-bench',-2,5,scale=.7)
        g.instance('pbr-pump',2,5,scale=.8)
        g.instance('dining-set',2,1,scale=.7)
        place('crate',[(-3,1),(-3,2)])
    elif theme=='harbor':
        for x in [-5,0,5]:
            for y in [1,4,6]:
                g.box('dock-plank-seam',(x,y,.17),(1.9,.035,.02),'wood_dark')
                g.instance('lamp',x+.7,y,scale=.55)
        place('barrel',[(-3,-1),(-3.8,-1)])
        g.instance('dining-set',4,-5,scale=.75)
        g.instance('rolling-luggage',2,-3)
        g.instance('tool-bench',-5,-5,scale=.7)
    elif theme in ['desert','western']:
        for x in [-6,6]:
            for dx in [-1,1]:
                g.box('shutter-window',(x+dx,1.87 if theme=='desert' else 1.72,1.9),(.6,.08,.8),'wood')
                for dz in [-.2,0,.2]:g.box('shutter-slat',(x+dx,1.8 if theme=='desert' else 1.65,1.9+dz),(.55,.06,.035),'wood_light')
            g.instance('dining-set',x,-.5,scale=.7)
        place('cactus',[(-8,0),(8,-2)])
        place('market-stall',[(-3,6)],.65)
        place('barrel',[(3,4),(3.6,4.3)],.7)
        g.instance('utility-pole',3,-5)
    elif theme in ['dream','candy']:
        place('lollipop',[(-3,-4),(3,-4),(-7,2),(7,2)],.75)
        for x,y in [(-4,0),(4,0),(-3,5),(3,6)]:
            g.instance('grass-clump',x,y,scale=1.8)
            g.ico('dream-pebble',(x+.3,y,.15),(.24,.2,.15),'pink',2)
        g.instance('dining-set',-3,3,scale=.65)
        g.instance('flower-planter',3,2,scale=.75)
    elif theme=='race':
        g.instance('tool-bench',-5,-1)
        g.instance('vending-machine',5,-2)
        g.instance('copper-boiler',-5,2,scale=.55)
        for x in [-8,8]:
            for y in [-1,1,5]:g.instance('lamp',x,y,scale=.8)
        for x in [-4,4]:g.instance('road-barrier',x,-4,scale=.7)
        place('crate',[(5,1),(5,2)],.65)
    elif theme=='arena':
        for x in [-4,4]:
            g.instance('crate',x,1,scale=.8)
            g.instance('barrel',x+.8,1,scale=.8)
            g.instance('lamp',x,5)
        place('fence',[(-7,0),(7,0)])
        g.instance('tool-bench',-4,-5,scale=.7)
        g.instance('medical-cart',4,-5)
    elif theme=='market':
        for x in [-5,5]:
            for y in [-3,1,5]:
                g.instance('crate',x+1.3,y,scale=.6)
                g.instance('flower-planter',x,y+1,scale=.7)
        g.instance('dining-set',-2,1,scale=.6)
        g.instance('rolling-luggage',2,4)
        place('utility-pole',[(-8,0),(8,0)])
    elif theme=='hospital':
        for x in [-4.6,4.6]:
            for y in [0,4]:g.instance('medical-cart',x,y,scale=.8)
        g.instance('study-desk',0,6)
        g.instance('vending-machine',7,-3)
        g.instance('park-bench',-5,-4)
        g.instance('exhibit-case',3,6,scale=.8)
    elif theme=='school':
        for x in [-6,-3,3,6]:
            for y in [-1,2,5]:
                g.box('class-chair',(x,y-.65,.45),(.48,.48,.1),'wood_light')
                g.box('class-chair-back',(x,y-.9,.75),(.48,.08,.55),'wood')
                for dx in [-.18,.18]:g.box('chair-leg',(x+dx,y-.65,.22),(.05,.35,.44),'metal')
        g.instance('bookcase',6,6,rotation=10,scale=.8)
        g.instance('study-desk',0,6)
    elif theme=='museum':
        place('exhibit-case',[(-2,5),(2,5),(-7,0),(7,0)])
        for x in [-5,5]:
            for y in [-2,2,6]:g.instance('metal-railing',x,y-1,scale=.75)
        g.instance('study-desk',-3,-4,scale=.8)
    elif theme=='kitchen':
        for x in [-6,6]:
            for y in [-1,2,5]:
                g.cylinder('pot-lid',(x,y,1.62),.47,.06,'metal',24)
                g.cylinder('lid-knob',(x,y,1.7),.06,.13,'boots',12)
                for dx in [-.7,.7]:g.box('kitchen-drawer',(x+dx,y-1,.6),(.08,.4,.05),'metal')
        place('dining-set',[(-3,2),(3,2)],.7)
        g.instance('medical-cart',-3,5)
        g.instance('crate',3,5,scale=.8)
    elif theme=='arcade':
        for x in [-4.8,4.8]:
            for y in [-2,1,4,6]:g.cylinder('arcade-stool',(x,y,.38),.25,.75,'neon',12)
        place('vending-machine',[(-7,6),(7,-4)])
        g.instance('park-bench',-5,-4)
        g.instance('utility-pole',8,6,scale=.6)
    elif theme=='underwater':
        for x,y in [(-4,-4),(4,-4),(-8,3),(8,1),(-3,4),(3,6)]:
            g.instance('pink-coral',x,y,scale=.75)
            g.instance('grass-clump',x+.5,y,scale=2)
        for x in [-5,5]:
            g.instance('valve-pipe',x,1)
            g.instance('crate',x+2,3,scale=.7)
        g.instance('exhibit-case',-3,0,scale=.7)
    elif theme=='volcano':
        for x,y in [(-4,2),(4,2),(-3,4),(3,4),(-8,1),(8,-1)]:g.instance('rock-cluster',x,y,scale=.8)
        g.instance('tool-bench',-3,-1,scale=.65)
        g.instance('medical-cart',3,-1)
        place('lamp',[(-3,-5),(3,-5)],.8)
    elif theme=='gothic':
        for x in [-6,6]:
            for dx in [-1.2,1.2]:g.box('tower-buttress',(x+dx,3,2),(.35,.65,4),'stone_dark')
            g.instance('gallery-statue',x,0,scale=.75)
        place('lamp',[(-3,2),(3,2)],.8)
        place('fence',[(-7,-5),(7,-5)])
        place('rock-cluster',[(-2,6),(2,6)],.5)
    elif theme=='steampunk':
        for x in [-6,6]:
            g.instance('valve-pipe',x,2)
            g.instance('tool-bench',x,-5,scale=.8)
        place('utility-pole',[(-3,5),(3,5)],.8)
        place('crate',[(-3,2),(3,2)],.75)
    elif theme=='boardgame':
        for x in [-6,-3,3,6]:
            g.cylinder('opposing-piece',(x,-2,.35),.3,.7,'red',12,.17)
            g.ico('opposing-head',(x,-2,.85),(.27,.27,.27),'red',2)
        for y in [-2,1,4,7]:
            g.box('board-rim',(-7.2,y,.2),(.18,2.8,.4),'gold')
            g.box('board-rim',(7.2,y,.2),(.18,2.8,.4),'gold')
        place('park-bench',[(-8,-4),(8,-4)],.75)
    elif theme=='basketball':
        for x in [-8,8]:
            for y in [-4,3,6]:g.instance('metal-railing',x,y,rotation=90)
        g.instance('vending-machine',-5,-5)
        g.instance('rolling-luggage',5,-5)
        for x in [-4,4]:g.ico('basketball',(x,2,.24),(.24,.24,.24),'roof_light',3)
        g.box('scoreboard',(0,7,2.4),(3,.2,1),'night')
        for x in [-.8,.8]:g.box('score-digit',(x,6.87,2.4),(.4,.04,.65),'lamp')
    elif theme=='factory':
        for x in [-7,7]:
            g.instance('tool-bench',x,4,scale=.8)
            g.instance('valve-pipe',x,0)
        place('copper-boiler',[(-7,6),(7,6)],.7)
        g.instance('medical-cart',-3,5)
        place('road-barrier',[(-3,-2),(3,-2)],.7)
    elif theme=='airport':
        for x in [-5,5]:
            g.instance('rolling-luggage',x,-1)
            g.instance('tool-bench',x,-4,scale=.75)
            g.instance('lamp',x,5,scale=.8)
        for x in [-3,0,3]:g.instance('park-bench',x,5,scale=.65)
        g.instance('vending-machine',-7,5)
        place('road-barrier',[(-8,1),(8,1)],.7)
    elif theme=='temple':
        for x in [-6,-3,3,6]:
            for y in [2,6]:
                for z in [.15,3.3]:g.cylinder('column-ring',(x,y,z),.43,.12,'stone_light',16)
        place('exhibit-case',[(-4,-1),(4,-1)],.8)
        place('campfire',[(-7,-4),(7,-4)],.7)
        place('rock-cluster',[(-8,4),(8,4)],.7)
    elif theme=='rooftop':
        place('flower-planter',[(-6,-5),(6,-5),(-7,4),(7,4)])
        place('dining-set',[(-4,4),(4,6)],.7)
        g.instance('vending-machine',7,0)
        place('lamp',[(-8,0),(8,0)],.75)

EXTRA=[('voxel-village','方块冒险村','体素像素风','沙盒建造、资源采集、像素冒险'),
 ('pbr-workshop','材质研究工坊','PBR写实材质练习','工业展示、维修模拟、产品演示'),
 ('paper-garden','折纸小花园','纸艺风','轻解谜、儿童故事、艺术互动')]

def extra_scene(theme):
    g.terrain('ground' if theme=='voxel-village' else 'stone_light' if theme=='pbr-workshop' else 'cream')
    if theme=='voxel-village':
        for x in [-5,5]:
            g.box('voxel-house',(x,4,1.3),(3.2,3.2,2.6),'plaster',0)
            for z,w in [(2.8,4),(3.2,3.2),(3.6,2.4),(4,1.6)]:g.box('stepped-roof',(x,4,z),(w,3.6,.4),'roof',0)
            for dx in [-.8,.8]:
                g.box('pixel-window',(x+dx,2.38,1.6),(.64,.04,.64),'cyan',0)
                g.box('pixel-sill',(x+dx,2.3,1.2),(.8,.16,.16),'wood',0)
        place('voxel-tree',[(-8,-4),(8,-4),(-8,5),(8,5)],1)
        place('person-voxel',[(-2,-2),(3,1)])
        place('crate',[(-3,4),(3,4)],.75)
        for x in [-5,5]:
            for y in [-3,0]:g.box('voxel-flower-bed',(x,y,.2),(2,1,.4),'wood',0)
        for y in [-6,-4,-2,0,2,4]:g.box('voxel-path',(0,y,.04),(1.5,1.5,.08),'path',0)
    elif theme=='pbr-workshop':
        for x in [-6,6]:
            g.instance('tool-bench',x,4,scale=1.2)
            g.instance('pbr-pump',x,0,scale=1.2)
            g.instance('valve-pipe',x,-3)
            g.instance('copper-boiler',x,6,scale=.8)
        place('metal-railing',[(-8,2),(8,2)])
        place('person-engineer',[(-2,-2)])
        g.instance('medical-cart',3,2)
        for x in [-3,0,3]:
            g.box('material-plinth',(x,5,.4),(1.5,1.5,.8),'cream')
            g.ico('material-sample',(x,5,1.35),(.55,.55,.55),'copper' if x<0 else 'metal' if x else 'wood_light',4)
    else:
        for x in [-5,5]:
            # Four thin cardstock walls and two genuinely folded roof panels.
            for dx in [-1.5,1.5]:g.box('paper-side',(x+dx,4,1.1),(.025,2.5,2.2),'pink',0)
            for y in [2.75,5.25]:g.box('paper-front',(x,y,1.1),(3,.025,2.2),'pink',0)
            import bpy
            mesh=bpy.data.meshes.new('folded-paper-roof')
            mesh.from_pydata([(-1.75,-1.4,2.2),(0,-1.4,3.2),(1.75,-1.4,2.2),
                             (-1.75,1.4,2.2),(0,1.4,3.2),(1.75,1.4,2.2)],[],[(0,3,4,1),(1,4,5,2)])
            obj=bpy.data.objects.new('folded-paper-roof',mesh);bpy.context.collection.objects.link(obj)
            obj.location=(x,4,0);g.finish(obj,'folded-paper-roof','cream')
            modifier=obj.modifiers.new('Cardstock thickness','SOLIDIFY');modifier.thickness=.025
            bpy.context.view_layer.objects.active=obj;bpy.ops.object.modifier_apply(modifier=modifier.name)
            g.box('folded-door',(x,2.72,.8),(.65,.02,1.6),'jade',0)
            for dx in [-.95,.95]:g.box('paper-window',(x+dx,2.72,1.3),(.48,.015,.48),'cream',0)
        for x,y in [(-7,-3),(7,-3),(-8,4),(8,4),(-4,0),(4,0)]:
            g.cylinder('paper-trunk',(x,y,.7),.09,1.4,'wood',4)
            g.cylinder('folded-canopy',(x,y,1.8),1,1.8,'jade',4,0)
        place('flower-planter',[(-3,3),(3,3)],.7)
        place('person-explorer',[(-2,-2)])
        place('park-bench',[(-5,-4),(5,-4)])
        g.path_line((0,-6),(0,5))
