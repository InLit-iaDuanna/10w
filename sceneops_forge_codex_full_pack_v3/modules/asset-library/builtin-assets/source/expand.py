"""Add original genre environments without rewriting the original shipped assets.
Run in Blender with --python expand.py. Geometry is static, CC0, Z-up in source.
"""
import json
import bpy
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import generate as g

# Dedicated materials keep the original pack's material palette unchanged.
g.COLORS.update(neon='DA49CA', cyan='42DCE8', night='252C48', snow='E4F3FA', ice='81BDD9',
                pink='EFA5C1', red='B83D48', gold='D6AB50', dark='39333F', lavender='AA93D4')

def portal():
    for x in [-1.5,1.5]: g.box('portal-pillar',(x,0,1.8),(.4,.6,3.6),'night')
    g.box('portal-lintel',(0,0,3.6),(3.4,.6,.4),'night')
    for x in [-1.25,1.25]: g.box('portal-strip',(x,-.32,1.8),(.08,.04,3.2),'cyan')
    g.box('portal-strip',(0,-.32,3.4),(2.5,.04,.08),'neon')

def terminal():
    g.box('terminal-base',(0,0,.55),(.85,.65,1.1),'night')
    g.box('terminal-screen',(0,-.35,1.05),(.7,.08,.55),'cyan')
    for x in [-.2,0,.2]: g.box('terminal-key',(x,-.38,.65),(.1,.04,.07),'neon')

def crystal():
    for x,y,h in [(-.4,0,1.1),(.1,.1,1.8),(.5,-.1,.8)]:
        g.cylinder('crystal',(x,y,h/2),.3,h,'ice',5,.13)
        g.cylinder('crystal-tip',(x,y,h+.2),.13,.4,'cyan',5,0)

def torii():
    for x in [-1.4,1.4]: g.cylinder('torii-post',(x,0,1.7),.16,3.4,'red')
    for z,w in [(2.8,3.6),(3.4,4.2)]: g.box('torii-beam',(0,0,z),(w,.35,.22),'red')
    g.box('torii-cap',(0,0,3.56),(4.4,.4,.12),'dark')

def stall():
    for x in [-1,1]:
        for y in [-.6,.6]: g.box('stall-post',(x,y,1.1),(.1,.1,2.2),'wood')
    g.box('counter',(0,0,.9),(2.3,1.4,.2),'wood_light')
    for i in range(6): g.box('awning',(-1+i*.4,0,2.2),(.4,1.7,.15),'cream' if i%2 else 'red')
    for x in [-.6,0,.6]: g.ico('produce',(x,0,1.15),(.23,.24,.24),'roof_light')

def mushroom():
    g.cylinder('stem',(0,0,.65),.19,1.3,'cream')
    g.ico('mushroom-cap',(0,0,1.4),(1,1,.5),'lavender',2)
    for x,y in [(-.4,-.3),(.3,-.4),(0,.4)]: g.ico('cap-dot',(x,y,1.8),(.13,.13,.07),'cream')

def turbine():
    g.cylinder('mast',(0,0,1.7),.15,3.4,'metal')
    for angle in [0,120,240]:
        import math
        a=math.radians(angle)
        g.beam('rotor',(0,-.2,3.4),(1.25*math.cos(a),-.2,3.4+1.25*math.sin(a)),.15,'cream')

def barricade():
    g.box('barrier',(0,0,.55),(2.4,.5,1.1),'stone_dark')
    for x in [-.8,-.4,0,.4,.8]: g.box('hazard-stripe',(x,-.26,.65),(.18,.02,.65),'gold')

NEW={'neon-portal':('霓虹通行门','科幻建筑',portal),'holo-terminal':('全息终端','科幻道具',terminal),
     'ice-crystal':('冰晶簇','冰雪自然',crystal),'torii':('朱红鸟居','日式建筑',torii),
     'market-stall':('条纹摊位','经营道具',stall),'giant-mushroom':('梦境巨菇','幻想植被',mushroom),
     'wind-turbine':('小型风机','工业道具',turbine),'road-barrier':('警示路障','城市道具',barricade)}

# Layouts intentionally reserve the south entrance and center for runtime gameplay.
def scene(theme):
    surface={'cyber':'night','space':'stone_dark','zen':'sand','snow':'snow','dungeon':'dark',
             'farm':'ground','harbor':'sand','desert':'sand','dream':'lavender','race':'stone_dark',
             'arena':'earth','market':'path'}[theme]
    g.terrain(surface)
    if theme=='cyber':
        for x in [-6,6]:
            for y,h in [(0,4),(5,6)]:
                g.box('city-tower',(x,y,h/2),(3,3,h),'night')
                for z in range(1,h): g.box('neon-window',(x,y-1.52,z),(2.5,.05,.13),'cyan' if x<0 else 'neon')
        g.instance('neon-portal',0,5);g.instance('holo-terminal',3,-2)
        for x in [-2,2]: g.box('lane-light',(x,0,.03),(.07,14,.04),'neon')
    elif theme=='space':
        for x in [-6,6]:
            g.box('habitat',(x,3,1.5),(4,5,3),'cream')
            g.box('habitat-window',(x,.45,1.8),(3,.08,.7),'cyan')
            g.instance('wind-turbine',x,6)
        g.instance('neon-portal',0,6)
        for x in [-3,3]: g.instance('holo-terminal',x,0)
        g.cylinder('landing-pad',(0,0,.025),2.3,.05,'metal',32)
    elif theme=='zen':
        g.instance('torii',0,4);g.path_line((0,-7),(0,4))
        for x in [-6,6]:
            for y in [-2,5]:
                g.cylinder('cherry-trunk',(x,y,1),.2,2,'wood')
                g.ico('cherry-blossoms',(x,y,2.7),(1.8,1.6,1.3),'pink',2)
        g.box('pond',(5,1,.015),(3,3,.03),'water',.3)
        g.instance('rock-cluster',-5,1);g.instance('lamp',-2,4)
    elif theme=='snow':
        for x in [-6,6]:
            g.box('polar-lab',(x,4,1.2),(4,4,2.4),'cream')
            g.box('snow-roof',(x,4,2.45),(4.3,4.3,.2),'snow')
            g.instance('wind-turbine',x,6)
        for x,y in [(-7,-4),(7,-3),(-3,6),(3,6)]:g.instance('ice-crystal',x,y,scale=1.3)
        g.instance('holo-terminal',3,0)
    elif theme=='dungeon':
        for x in [-7,7]:
            g.box('dungeon-wall',(x,2,1.3),(.7,11,2.6),'dark')
            for y in [-2,2,6]:g.instance('ruin-arch',x,y,90,.7)
        g.instance('ruin-arch',0,6);g.instance('crate',-4,3);g.instance('barrel',4,3)
        for x in [-4,4]:g.instance('campfire',x,-2)
    elif theme=='farm':
        g.instance('cottage',-5,5);g.instance('market-stall',5,5)
        for x in [-6,5]:
            for y in [-3,-1,1]:
                g.box('raised-bed',(x,y,.1),(3.5,1.2,.2),'earth')
                for dx in [-1.2,-.4,.4,1.2]:g.instance('grass-clump',x+dx,y,scale=1.5)
        for x in [-7,7]:g.instance('fence',x,7)
        g.instance('well',0,5)
    elif theme=='harbor':
        g.box('sea',(0,5,.015),(19,7,.03),'water')
        for x in [-5,0,5]:
            g.box('jetty',(x,3,.08),(2,9,.16),'wood_light')
            for y in [0,3,6]:g.cylinder('mooring-post',(x+.85,y,.5),.12,1,'wood')
        g.instance('watchtower',-7,-3);g.instance('market-stall',6,-3)
        for x in [3,4.2,5.4]:g.instance('crate',x,-1)
    elif theme=='desert':
        for x in [-6,6]:
            g.box('adobe-house',(x,4,1.6),(3.6,4,3.2),'sand')
            for dx in [-1.3,0,1.3]:g.box('battlement',(x+dx,4,3.45),(.5,4,.5),'plaster')
        g.instance('ruin-arch',0,5,scale=1.2)
        g.box('oasis',(5,-2,.02),(3,3,.04),'water',.4)
        for x,y in [(-7,-3),(-5,-4),(7,0)]:g.instance('rock-cluster',x,y)
    elif theme=='dream':
        for x,y,s in [(-6,-3,1.4),(6,-2,1.8),(-5,5,2),(5,5,1.2)]:g.instance('giant-mushroom',x,y,scale=s)
        for x,y in [(-3,2),(3,4),(-7,1)]:g.instance('ice-crystal',x,y)
        g.instance('neon-portal',0,6);g.path_line((0,-7),(0,4))
    elif theme=='race':
        for x in [-7,7]:g.box('track-edge',(x,0,.03),(.18,15,.06),'cream')
        for y in [-5,-2,1,4,7]:g.box('lane-dash',(0,y,.025),(.12,1.3,.05),'gold')
        for x in [-5,-3,-1,1,3,5]:g.box('finish-line',(x,5,.03),(1,1,.06),'cream')
        for x,y in [(-8,-4),(8,-4),(-8,3),(8,3)]:g.instance('road-barrier',x,y,90)
        g.instance('neon-portal',0,6,scale=1.5)
    elif theme=='arena':
        for x in [-7,7]:
            for y in [-4,4]:g.instance('watchtower',x,y,scale=.8)
        for x in [-4,4]:
            for y in [-2,3]:g.instance('road-barrier',x,y)
        g.instance('ruin-arch',0,6);g.instance('crate',-6,0);g.instance('barrel',6,0)
    elif theme=='market':
        for x in [-5,5]:
            for y in [-3,1,5]:g.instance('market-stall',x,y)
        for x in [-2,2]:
            for y in [-2,3]:g.instance('lamp',x,y)
        g.instance('cottage',0,6,scale=.8)

THEMES=[
 ('cyber','霓虹雨巷','赛博霓虹','潜行、动作冒险、任务据点'),
 ('space','远星前哨','洁净科幻','太空生存、基地建设、资源管理'),
 ('zen','樱风庭院','日式和风','叙事探索、摄影、休闲解谜'),
 ('snow','极地研究站','冰雪极简','生存探索、科考模拟、合作冒险'),
 ('dungeon','幽影地牢','暗黑奇幻','Roguelike、地牢探索、回合制战斗'),
 ('farm','丰收田园','温暖田园','种田、模拟经营、生活模拟'),
 ('harbor','晴湾码头','海滨卡通','钓鱼、贸易经营、海岛冒险'),
 ('desert','金沙遗城','沙漠史诗','寻宝、开放区域探索、环境解谜'),
 ('dream','蘑菇梦境','糖果幻想','平台跳跃、收集、童话冒险'),
 ('race','极速试车场','工业运动','街机竞速、驾驶训练、计时挑战'),
 ('arena','边境攻防场','废土战术','塔防、俯视角射击、战术对抗'),
 ('market','暮灯集市','复古市井','商店经营、社交任务、生活角色扮演'),
]

def main(*, builders=NEW, themes=THEMES, build_scene=scene, version=2, generator=__file__):
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    g.BUILDERS.update(builders);g.bake_assets();bpy.context.view_layer.update()
    document=json.loads((g.ROOT/'catalog.json').read_text())
    additions=[]
    for key,(label,category,_) in builders.items():
        objects=g.ASSETS[key];g.export(key,objects)
        record=g.entry(key,label,category,objects,description=f'原创{label}，适合主题场景搭建，可单独复用。')
        g.presentation(objects);bpy.context.scene.render.filepath=str(g.ROOT/'previews'/f'{key}.png')
        bpy.ops.render.render(write_still=True);g.clean_presentation();additions.append(record)
        for obj in objects:obj.hide_render=True;obj.hide_set(True)
    for theme,label,style,genres in themes:
        key='world-'+theme
        g.SCENES[key]=None;g.CURRENT_SCENE=key;g.INSTANCE_COUNTS.clear();g.OBJECTS.clear()
        build_scene(theme);objects=list(g.OBJECTS)
        for i,obj in enumerate(objects):
            if 'sceneops_id' not in obj:obj['sceneops_id']=f'{g.PACK}/{key}/part-{i}'
        bpy.context.view_layer.update();g.export(key,objects)
        record=g.entry(key,label,'场景 · '+style,objects,
            description=f'{style}主题场景。适用游戏：{genres}。预留南侧入口和中央活动区；包含静态建筑与道具，玩法、碰撞和导航需在项目中配置。',spawns=[(0,-6,.12),(1,-4,.12)])
        g.presentation(objects,True);bpy.context.scene.render.filepath=str(g.ROOT/'previews'/f'{key}.png')
        bpy.ops.render.render(write_still=True);g.clean_presentation();additions.append(record)
        for obj in objects:bpy.data.objects.remove(obj,do_unlink=True)
        print('EXPANDED_SCENE',key,flush=True)
    for record in additions:
        record['source']['generator']='modules/asset-library/builtin-assets/source/'+Path(generator).name
    ids={e['asset_id'] for e in additions}
    document['entries']=[e for e in document['entries'] if e['asset_id'] not in ids]+additions
    document['version']=max(document['version'],version)
    document['label']='万象场景库 · 原创可复用资产'
    counts={kind:sum(e['kind']==kind for e in document['entries']) for kind in ['scene','prop','character']}
    document['description']=f"{counts['scene']} 套完整场景，覆盖幻想、科幻、都市与生活空间，适用于探索、经营、生存、竞速、解谜和教育导览；含 {counts['prop']} 件独立建筑与物件、{counts['character']} 位角色。"
    (g.ROOT/'catalog.json').write_text(json.dumps(document,ensure_ascii=False,indent=2)+'\n')
    print('EXPANSION_COMPLETE',len(document['entries']),flush=True)

if __name__=='__main__': main()
