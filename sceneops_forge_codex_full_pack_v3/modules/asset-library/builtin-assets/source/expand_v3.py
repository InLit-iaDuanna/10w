"""Original v3 environments. Run after generate.py and expand.py in Blender.
Adds new IDs and files; existing assets retain their original geometry and version.
"""
import math
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import expand as e
import generate as g

g.COLORS.update(copper='B87545', jade='487F6B', ink='38434B', mint='A9D9C5',
                candy='F7B8CE', lemon='F3D675', ocean='356B8C', lava='F2753E')

def bench():
    for x in [-.7,.7]:g.box('bench-leg',(x,0,.25),(.12,.5,.5),'metal')
    g.box('bench-seat',(0,0,.5),(1.8,.55,.12),'wood_light')
    g.box('bench-back',(0,.22,.85),(1.8,.12,.55),'wood_light')

def desk():
    for x in [-.6,.6]:
        for y in [-.35,.35]:g.box('desk-leg',(x,y,.4),(.09,.09,.8),'metal')
    g.box('desk-top',(0,0,.85),(1.5,1,.12),'wood_light')
    g.box('notebook',(.2,0,.94),(.4,.5,.05),'cream')

def shelf():
    for x in [-.8,.8]:g.box('shelf-side',(x,0,1.1),(.12,.5,2.2),'wood')
    for z in [.1,.8,1.5,2.2]:
        g.box('shelf-board',(0,0,z),(1.7,.55,.1),'wood_light')
        if z<2:
            for i in range(7):g.box('book',(-.6+i*.2,0,z+.28),(.14,.4,.45),['red','jade','gold'][i%3])

def conveyor():
    g.box('conveyor-belt',(0,0,.7),(1.6,3.4,.2),'dark')
    for y in [-1.5,-.9,-.3,.3,.9,1.5]:g.box('belt-slat',(0,y,.82),(1.5,.08,.05),'metal')
    for x in [-.65,.65]:
        for y in [-1.3,1.3]:g.box('conveyor-leg',(x,y,.35),(.1,.1,.7),'metal')

def boiler():
    g.cylinder('boiler',(0,0,1.2),.8,2.4,'copper',16)
    g.cylinder('chimney',(.3,0,3),.17,1.4,'dark')
    for z in [.2,1.9]:g.cylinder('tank-band',(0,0,z),.83,.12,'metal',16)
    g.box('pressure-gauge',(0,-.82,1.6),(.4,.08,.4),'cream')
    g.beam('gauge-needle',(0,-.87,1.6),(.1,-.87,1.72),.025,'red')

def cactus():
    g.cylinder('cactus-stem',(0,0,1.2),.24,2.4,'jade',8)
    for x,z in [(-.6,1.5),(.6,1.9)]:
        g.beam('cactus-arm',(0,0,z-.6),(x,0,z-.6),.24,'jade')
        g.cylinder('cactus-finger',(x,0,z-.3),.15,.6,'jade',8)

def coral():
    for x,y,h in [(-.5,0,1),(.1,.2,1.5),(.55,-.2,.8)]:
        g.beam('coral-stem',(x,y,0),(x,y,h),.16,'pink')
        for dx in [-.3,.3]:g.beam('coral-branch',(x,y,h*.55),(x+dx,y,h),.12,'pink')

def candy():
    g.cylinder('candy-stick',(0,0,.9),.08,1.8,'cream',8)
    obj=g.cylinder('lollipop',(0,0,2),.65,.2,'candy',24);obj.rotation_euler.x=math.pi/2
    for x in [-.3,0,.3]:g.box('candy-stripe',(x,-.12,2),(.12,.04,.85),'cream',rotation=.2)

def statue():
    g.box('plinth',(0,0,.25),(1.2,1.2,.5),'stone_light')
    g.ico('sculpture',(0,0,1.35),(.6,.5,.85),'gold',1)
    g.ico('sculpture-crown',(0,0,2.2),(.3,.3,.3),'gold',1)

def hoop():
    g.box('hoop-pole',(0,0,1.8),(.12,.12,3.6),'metal')
    g.box('backboard',(0,-.2,3.25),(1.8,.12,1),'cream')
    bpy=e.bpy
    bpy.ops.mesh.primitive_torus_add(major_segments=16,minor_segments=4,location=(0,-.75,2.9),major_radius=.33,minor_radius=.035)
    g.finish(bpy.context.object,'basket-ring','red')
    for x in [-.25,.25]:g.beam('basket-net',(x,-.75,2.9),(x*.6,-.75,2.5),.02,'cream')

def arcade():
    g.box('arcade-body',(0,0,.9),(.9,.75,1.8),'night')
    g.box('arcade-header',(0,-.4,1.65),(.8,.08,.2),'neon')
    g.box('arcade-screen',(0,-.4,1.18),(.65,.08,.6),'cyan')
    g.box('arcade-controls',(0,-.55,.75),(.9,.4,.12),'lavender')
    g.cylinder('joystick',(-.2,-.55,.87),.035,.2,'red',8)

def plane():
    g.ico('fuselage',(0,0,.75),(.65,2.8,.6),'cream',2)
    g.box('wing',(0,0,.7),(6.2,.85,.12),'cream')
    g.box('tail-wing',(0,2,.85),(2,.6,.12),'cyan')
    g.box('tail-fin',(0,2,1.2),(.12,.65,.9),'cyan')
    g.ico('cockpit',(0,-1.25,1.1),(.45,.8,.3),'ocean',2)
    for x in [-.5,.5]:g.cylinder('wheel',(x,0,.2),.18,.15,'boots').rotation_euler.y=math.pi/2

NEW={
 'park-bench':('公园长椅','城市家具',bench),'study-desk':('课桌与笔记本','室内家具',desk),
 'bookcase':('彩色藏书架','室内家具',shelf),'conveyor':('滚道传送带','工业设备',conveyor),
 'copper-boiler':('铜制蒸汽炉','蒸汽设备',boiler),'cactus':('分枝仙人掌','沙漠植被',cactus),
 'pink-coral':('粉色珊瑚','海底自然',coral),'lollipop':('糖果路标','幻想道具',candy),
 'gallery-statue':('几何雕塑','展览道具',statue),'basketball-hoop':('篮球架','运动设施',hoop),
 'arcade-cabinet':('街机机台','娱乐设备',arcade),'small-airplane':('轻型飞机','交通工具',plane),
}

def room(surface,wall):
    g.terrain(surface)
    g.box('rear-wall',(0,8,1.7),(19,.25,3.4),wall)
    g.box('side-wall',(-9,1,1.7),(.25,14,3.4),wall)

def scene(theme):
    if theme=='hospital':
        room('cream','mint')
        for x in [-6,6]:
            for y in [-1,3,6]:
                g.box('bed-frame',(x,y,.5),(1.6,2.4,.18),'metal')
                g.box('mattress',(x,y,.7),(1.5,2.2,.25),'snow')
                g.box('blanket',(x,y-.3,.86),(1.5,1.4,.08),'mint')
                g.box('pillow',(x,y+.7,.9),(1,.45,.15),'cream')
        g.box('medical-cross-v',(0,7.8,2.3),(.25,.05,1),'red');g.box('medical-cross-h',(0,7.77,2.3),(1,.05,.25),'red')
        g.instance('holo-terminal',3,6)
    elif theme=='school':
        room('path','cream')
        g.box('chalkboard',(0,7.8,2),(7,.1,1.8),'jade')
        for x in [-6,-3,3,6]:
            for y in [-1,2,5]:g.instance('study-desk',x,y)
        g.instance('bookcase',-7,6);g.instance('park-bench',5,-3)
    elif theme=='museum':
        room('stone_light','cream')
        for x in [-5,5]:
            for y in [-2,2,6]:g.instance('gallery-statue',x,y)
        for x in [-5,0,5]:
            g.box('picture-frame',(x,7.7,2.1),(2,.15,1.5),'gold')
            g.box('artwork',(x,7.6,2.1),(1.7,.03,1.2),'lavender' if x else 'ocean')
        g.instance('park-bench',0,2)
    elif theme=='kitchen':
        room('path','plaster')
        for x in [-6,6]:
            g.box('worktop',(x,2,1),(2.5,9,.2),'stone_light')
            g.box('cabinet',(x,2,.5),(2.3,8.8,1),'mint')
            for y in [-1,2,5]:g.cylinder('cooking-pot',(x,y,1.35),.45,.5,'metal',16)
        g.box('extractor',(6,3,2.8),(2.6,5,.3),'metal')
        g.box('cold-storage',(-5,6,1.3),(2,1.4,2.6),'cream')
        g.instance('market-stall',0,6)
    elif theme=='arcade':
        room('night','dark')
        for x in [-6,6]:
            for y in [-2,1,4,6]:g.instance('arcade-cabinet',x,y)
        for x in [-2,0,2]:
            for y in [0,2,4]:g.box('dance-tile',(x,y,.03),(1.6,1.6,.06),'neon' if y==2 else 'cyan')
    elif theme=='underwater':
        g.terrain('ocean')
        for x,y in [(-7,-3),(-5,3),(6,-2),(7,5),(-2,6)]:
            g.instance('pink-coral',x,y,scale=1.5);g.instance('rock-cluster',x-1,y,scale=.7)
        g.instance('ruin-arch',0,5)
        for x in [-5,5]:g.ico('undersea-pod',(x,3,1.3),(1.6,1.6,1.3),'ice',2)
        g.instance('holo-terminal',3,0)
    elif theme=='volcano':
        g.terrain('dark')
        for x in [-6,6]:
            g.box('lava-channel',(x,0,.03),(1.6,15,.06),'lava')
            for y in [-3,2,6]:g.instance('rock-cluster',x+1,y,scale=1.2)
        g.cylinder('volcano',(0,5,1.7),3,3.4,'stone_dark',10,1.2)
        g.cylinder('crater',(0,5,3.43),1.1,.06,'lava',10)
        g.instance('road-barrier',-3,-2);g.instance('road-barrier',3,-2)
    elif theme=='bamboo':
        g.terrain('mint');g.path_line((0,-7),(0,6))
        for x in [-7,-5,5,7]:
            for y in [-3,1,5]:
                g.cylinder('bamboo',(x,y,1.8),.1,3.6,'jade',8)
                for z in [.6,1.3,2,2.7]:
                    g.cylinder('bamboo-joint',(x,y,z),.13,.07,'leaf_light',8)
                    g.ico('bamboo-leaf',(x+.4,y,z+.25),(.6,.12,.13),'jade')
        g.instance('torii',0,5);g.instance('park-bench',3,1)
    elif theme=='gothic':
        g.terrain('stone_dark')
        for x in [-6,6]:
            g.box('gothic-tower',(x,4,2.3),(2.2,2.2,4.6),'ink')
            g.cylinder('spire',(x,4,5.5),1.6,2,'dark',4,0)
            g.box('stained-glass',(x,2.85,2.6),(.8,.05,1.8),'lavender')
        g.instance('ruin-arch',0,5,scale=1.3)
        for x in [-5,5]:
            for y in [-3,0]:
                g.box('gravestone',(x,y,.65),(.6,.3,1.3),'stone')
                g.box('grave',(x,y-.6,.08),(.8,1.5,.16),'stone_light')
    elif theme=='steampunk':
        g.terrain('path')
        for x in [-6,6]:
            for y in [0,5]:g.instance('copper-boiler',x,y)
            g.beam('overhead-pipe',(x,0,3),(x,5,3),.25,'copper')
            g.instance('conveyor',x,-3)
        g.instance('watchtower',0,6);g.instance('holo-terminal',3,2)
    elif theme=='western':
        g.terrain('sand')
        for x in [-6,6]:
            g.box('saloon',(x,4,1.5),(4,4,3),'wood_light')
            g.box('false-front',(x,1.9,2.8),(4.5,.2,1.8),'wood')
            g.box('saloon-sign',(x,1.76,3),(2.8,.05,.55),'gold')
            g.box('porch',(x,1,.15),(4.5,2,.3),'wood_light')
            for dx in [-1,1]:g.box('swing-door',(x+dx*.45,1.8,1.1),(.8,.1,1),'roof')
        for x,y in [(-8,-4),(8,-4),(-3,6)]:g.instance('cactus',x,y)
        g.instance('barrel',4,-2);g.instance('signpost',-3,-2)
    elif theme=='candy':
        g.terrain('candy')
        for x in [-6,6]:
            g.box('cake-house',(x,4,1.2),(3.5,3.5,2.4),'lemon',.25)
            g.ico('icing-roof',(x,4,2.8),(2.2,2.2,.8),'cream',2)
            for y in [-3,0,5]:g.instance('lollipop',x,y,scale=1.3)
        for x,y in [(-2,1),(2,3),(-2,5)]:g.cylinder('cookie-platform',(x,y,.18),.8,.36,'roof_light',12)
    elif theme=='boardgame':
        g.terrain('wood')
        for x in range(-4,5):
            for y in range(-2,7):g.box('board-square',(x*1.5,y*1.25,.03),(1.48,1.23,.06),'cream' if (x+y)%2 else 'jade',0)
        for x in [-6,-3,3,6]:
            g.cylinder('game-piece',(x,6,.5),.35,1,'gold',12,.2)
            g.ico('piece-head',(x,6,1.2),(.35,.35,.35),'gold',2)
        g.instance('gallery-statue',-8,2);g.instance('gallery-statue',8,2)
    elif theme=='basketball':
        g.terrain('roof')
        for x in [-7,7]:g.box('court-sideline',(x,0,.03),(.08,15,.06),'cream')
        for y in [-7,7,0]:g.box('court-line',(0,y,.03),(14,.08,.06),'cream')
        for x in [-5,5]:g.instance('basketball-hoop',x,5)
        for x in [-8,8]:g.instance('park-bench',x,0,90)
    elif theme=='factory':
        room('stone','stone_light')
        for x in [-5,5]:
            for y in [-2,2,6]:g.instance('conveyor',x,y)
            for y in [-2,3,6]:g.instance('crate',x,y,height=.85,scale=.7)
            g.box('robot-base',(x,1,1),(1,1,2),'gold')
            g.beam('robot-arm',(x,1,2),(x-1.3,1,2.8),.3,'gold')
        g.instance('holo-terminal',2,6)
    elif theme=='airport':
        g.terrain('stone_dark')
        g.instance('small-airplane',-5,2,20);g.instance('small-airplane',5,3,-20)
        g.box('terminal-building',(0,7,1.3),(11,2,2.6),'cream')
        g.box('terminal-glass',(0,5.95,1.5),(10,.05,1.4),'ice')
        for x in [-2,2]:g.box('taxiway-line',(x,-1,.03),(.1,11,.06),'gold')
        g.instance('watchtower',8,6,scale=.7)
    elif theme=='temple':
        g.terrain('sand')
        for x in [-6,-3,3,6]:
            for y in [2,6]:
                g.cylinder('marble-column',(x,y,1.8),.32,3.6,'cream',12)
                g.box('capital',(x,y,3.6),(.9,.9,.25),'cream')
        g.box('temple-lintel',(0,6,3.85),(14,1,.4),'cream')
        g.instance('gallery-statue',0,5,scale=1.3)
        for x in [-6,6]:g.instance('rock-cluster',x,-3)
    elif theme=='rooftop':
        g.terrain('stone_light')
        for x in [-9,9]:g.box('parapet',(x,0,.55),(.25,16,1.1),'stone')
        for x,y,h in [(-5,1,.6),(4,2,1),(0,5,1.5),(-6,6,1.1)]:
            g.box('parkour-platform',(x,y,h/2),(2.5,2,h),'mint')
        for x in [-6,6]:
            g.box('planter',(x,-3,.3),(2,1.5,.6),'wood_light')
            g.instance('broadleaf',x,-3,scale=.65,height=.6)
        g.instance('park-bench',5,6)

THEMES=[
 ('hospital','薄荷康复中心','现代医疗','医院经营、护理模拟、健康科普导览'),
 ('school','晨光教室','清新校园','校园剧情、课堂互动、教育模拟'),
 ('museum','留白艺术馆','现代展陈','博物馆导览、艺术展览、线索解谜'),
 ('kitchen','忙碌后厨','温馨餐饮','烹饪、餐厅经营、合作时间管理'),
 ('arcade','电光游艺厅','复古电子','节奏游戏、街机合集、社交大厅'),
 ('underwater','珊瑚沉城','海底幻想','潜水探索、生态教育、采集生存'),
 ('volcano','熔火峡谷','火山荒境','动作闯关、生存挑战、首领战'),
 ('bamboo','竹影秘径','东方水墨配色','武侠探索、冥想漫游、寻物解谜'),
 ('gothic','暮鸦钟庭','哥特暗黑','悬疑叙事、恐怖探索、密室逃脱'),
 ('steampunk','铜雾机坊','蒸汽朋克','机械解谜、自动化经营、资源建造'),
 ('western','落日边镇','复古西部','赏金冒险、对决、贸易经营'),
 ('candy','奶油糖镇','糖果童话','休闲收集、平台跳跃、儿童探索'),
 ('boardgame','翡翠棋盘','几何桌游','棋类、回合策略、战棋原型'),
 ('basketball','橙光球场','街头运动','体育竞技、投篮挑战、运动教学'),
 ('factory','智造物流车间','现代工业','流水线经营、物流调度、工业培训'),
 ('airport','云际小机场','航空卡通','飞行模拟、机场经营、交通教学'),
 ('temple','白柱神殿','古典神话','考古探索、历史导览、神话角色扮演'),
 ('rooftop','空中花园','都市生态','跑酷、城市摄影、空间跳跃'),
]

if __name__=='__main__':
    g.BUILDERS.update(e.NEW)
    e.main(builders=NEW,themes=THEMES,build_scene=scene,version=3,generator=__file__)
