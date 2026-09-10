"""Attach searchable art direction and reusable agent prompts; draw original pixel sprites."""
import json
import struct
from pathlib import Path
from PIL import Image, ImageDraw

SOURCE=Path(__file__).resolve().parent
ROOT=SOURCE.parents[1]/'backend/src/asset_library/builtin_assets'
STYLES={
 '黏土':('提供已绑定角色与独立物件','使用手塑圆润体块、自然的大小比例与哑光黏土材质，避免镜面高光；以真实几何表现鼻子、纽扣、帽沿与四肢连接。角色使用分段骨骼与归一化蒙皮，保留衣物体积。输出 Idle、Walk、Run、Wave 四段动画及静止参考姿态，自包含 GLB。'),
 '搪瓷':('提供已绑定机器人与独立物件','使用复古工业搪瓷外壳、厚边缘、可辨认的机械关节与抛光金属连接件。搪瓷采用低粗糙度和透明涂层，金属连接件具有明确金属度；几何上区分外壳、关节、面板和灯。机器人关节采用刚性蒙皮，避免把硬质外壳拉成橡皮；交付四段动画及统一命名骨骼。'),
 '低多边形':('现有场景主体','使用有设计感的低多边形几何，保持清晰的一级轮廓、结构分件和适量倒角。统一暖冷配色，粗糙度以 0.6–0.85 为主。建筑必须有门窗、边框、基础、屋檐或屋顶设施；道具必须有支撑、连接或把手等功能结构。不要把场景简化为散放方块，也不要用随机小物件填满通路。'),
 '体素':('提供实际 GLB 示例','以 0.08m 或其整数倍为构造网格，使用网格对齐的方块与阶梯轮廓，避免圆滑倒角。限制在 16–24 个协调色；以体素层次表现屋檐、帽子、树冠和道具把手。物体之间尺度一致；删除完全不可见的内部面。注意体素三维模型与二维像素图是不同交付物。'),
 '像素':('提供角色方向与步行动画图集','制作真正的二维像素资产：角色单帧 32×48 像素，4列步行帧×4行方向（下、左、右、上），透明背景；底部脚点对齐到 (16,46)。使用不超过 24 色的固定调色板、清楚的明暗色块与单像素细节，不使用抗锯齿或柔焦。地块使用 32×32 像素，建筑按同一透视与比例制作；整数倍最近邻放大。输出 PNG 与帧尺寸、方向、帧率元数据。不要把像素滤镜截图当作像素资产。'),
 '纸艺':('提供实际 GLB 场景示例','使用折纸或剪纸造型，薄片、折面、拼接缝和有限厚度表现构造；哑光纸材，柔和粉彩，避免塑料金属高光。重要轮廓通过真实折面表现，不依靠纹理伪装。保留薄片背面或设置双面材质，避免侧面消失；零件与场景仍采用真实米制尺寸。'),
 '写实':('生成指南；当前仅有 PBR 材质工坊示例，不是完整写实场景','按真实物理比例和结构制作，参考真实物体的装配关系、材质与使用痕迹。采用 PBR 金属度/粗糙度工作流，提供 BaseColor（sRGB）、Metallic/Roughness 与 Normal（线性）贴图，主要物件 2K、次要物件 1K，并打包进 GLB。合理布置 UV 和纹素密度，磨损与污渍应遵循接触、雨水、热源和搬运的因果关系。人物需正确解剖比例、衣物厚度、面部结构和适合变形的拓扑；不得把高细分光滑几何或随机噪声等同于写实。以真实灯光和中性材质检查细节，不夸大“照片级”完成度。'),
 '手绘':('生成指南，尚无独立手绘贴图套装','采用风格化手绘贴图：色彩分组明确，材质笔触跟随表面结构，边缘提亮与接触暗部克制，避免把强方向光永久画入漫反射。先完成低中模和 UV，再绘制统一笔触尺度的贴图。人物、建筑、植被共享轮廓与色彩规则，保持高识别度；贴图需真实交付并嵌入 GLB，不能仅改名称声称已完成手绘。'),
}

COMMON='''技术与复用要求：米制、右手系、Y 向上、正面 +Z，地面道具原点在接地点；角色高度参考 1.7–1.9m。把可独立复用的建筑、人物、家具、植被与设施分别导出，自包含 GLB，不依赖外部文件，不导出预览相机与灯光。保留稳定 source_asset_id 与独立 scene_instance_id；材质和对象使用语义名称。场景中心与南侧入口留出连续通道，检查出生点中心和半径 0.35m 的四向位置；入口不要被人物或装饰遮挡。提交正面/侧面/三分之四视图、三角面数、包围尺寸、许可和实际验证结果。静态网格、骨骼动画、碰撞、导航和玩法逻辑分别说明完成状态，不得以提示词代替已生成文件。涉及动画时另交绑定和动画检查结果。'''

def prompt(entry,style,labels):
    components=[labels[key] for key in entry.get('reusable_asset_ids',[]) if key in labels]
    rig_note=('共用骨架 sceneops-humanoid-v1 与动作集 sceneops-basic-locomotion-v1，可从 shared-humanoid-v1.blend 模板制作新角色并复用 shared-motions-v1.glb；必须保持骨骼静止位置、旋转、层级与命名一致，网格单独绑定权重。体型比例改变时重新检查关节与蒙皮兼容性。已绑定角色：16 根骨骼（Root/Hips/Spine/Head、左右 UpperArm/Forearm/Hand/Thigh/Shin/Foot），Idle/Walk/Run/Wave 四段原地动作；保持骨骼层级与网格权重归一化。不要把本条重新生成为静态模型。' if entry.get('rig',{}).get('status')=='skinned' else '')
    composition='场景需有主地标、辅助建筑、近中远景层次与通行空间；参照原始暖陶村落的结构密度，制作可理解的生活或功能关系。' if entry['kind']=='scene' else '这是可独立复用的单件资产；保留接地点、朝向与功能结构，不要附带大块场景地板。'
    return f'''任务：生成或扩展「{entry['label']}」。目标美术方向：{style}。
使用情境：{entry['description']}
参考尺寸：{' × '.join(str(v) for v in entry['dimensions_m'])}m（X/Y/Z）；跨风格改造应维持大体尺度与接地点。
构图与复用：{composition}
骨骼与动画要求：{rig_note}
已有可复用部件：{'、'.join(components) if components else entry['label']}。优先使用同风格部件，缺少的部件单独制作并记录来源，不把不一致风格直接拼接。
美术要求：{STYLES[style][1]}
{COMMON if style!='像素' else '二维交付：PNG 图集与帧布局 JSON；保持方向、脚点、色板一致。三维场景仅作为空间参考，不强制二维图集导出 GLB。附原始像素尺寸与最近邻放大预览。'}
交付说明：当前素材来源为 SceneOps 原创 CC0；仅使用原创或有明确授权的参考。当前目标风格状态：{STYLES[style][0]}。不要声称未执行的生成、绑定或运行时测试已完成。'''

def sprite(entry,destination):
    # Original grid artwork; coordinates are authored pixels, not filtered renders.
    key=entry['asset_id']
    color='#58A6BD'
    for token,c in [('medic','#9BCEC0'),('engineer','#D5A343'),('chef','#EEEAD9'),('guard','#8B979F'),('explorer','#6094B5'),('astronaut','#D7E4E5'),('robot','#88BCC0'),('enemy','#BB6367'),('npc','#D8B257'),('ally','#72AE8D')]:
        if token in key:color=c
    sheet=Image.new('RGBA',(128,192),(0,0,0,0))
    for row in range(4):
        for frame in range(4):
            tile=Image.new('RGBA',(32,48),(0,0,0,0));d=ImageDraw.Draw(tile)
            step=[0,-2,0,2][frame];skin='#DEB494';hair='#403D44';dark='#344954'
            d.rectangle((10+step,29,14+step,42),fill=dark);d.rectangle((18-step,29,22-step,42),fill=dark)
            d.rectangle((9+step,42,14+step,45),fill='#273642');d.rectangle((18-step,42,23-step,45),fill='#273642')
            d.rectangle((8,19,24,31),fill=color);d.rectangle((10,30,22,32),fill='#796148')
            d.rectangle((6,21+step,8,31+step),fill=color);d.rectangle((24,21-step,26,31-step),fill=color)
            d.rectangle((6,31+step,8,34+step),fill=skin);d.rectangle((24,31-step,26,34-step),fill=skin)
            d.rectangle((10,7,22,18),fill=skin);d.rectangle((9,5,23,9),fill=hair)
            d.rectangle((10,8,11,13),fill=hair)
            if row==3:d.rectangle((10,8,22,16),fill=hair)
            elif row==1:d.rectangle((10,12,11,13),fill=dark);d.rectangle((9,14,10,15),fill=skin)
            elif row==2:d.rectangle((21,12,22,13),fill=dark);d.rectangle((22,14,23,15),fill=skin)
            else:
                d.rectangle((12,12,13,13),fill=dark);d.rectangle((19,12,20,13),fill=dark)
                d.line((15,17,17,17),fill='#AC7868')
            if 'medic' in key:
                d.rectangle((9,4,23,8),fill='#F1F1E9');d.line((15,4,15,8),fill='#C8535E');d.line((13,6,17,6),fill='#C8535E')
            elif 'chef' in key:
                d.rectangle((10,1,22,7),fill='#F1F1E9');d.rectangle((12,21,20,30),fill='#F1F1E9')
            elif 'engineer' in key:
                d.rectangle((8,6,24,8),fill='#E2B347');d.rectangle((10,3,22,6),fill='#E2B347')
                d.line((11,21,11,28),fill='#F0E7BD');d.line((21,21,21,28),fill='#F0E7BD')
            elif 'guard' in key:
                d.rectangle((9,5,23,10),fill='#87969B');d.rectangle((3,23,7,34),fill='#788B91')
            elif 'astronaut' in key:
                d.rectangle((8,5,24,18),fill='#E0E8E7')
                if row==0:d.rectangle((10,8,22,15),fill='#476C85')
                elif row==1:d.rectangle((8,8,14,15),fill='#476C85')
                elif row==2:d.rectangle((18,8,24,15),fill='#476C85')
                else:d.rectangle((12,9,20,14),fill='#BCCFD0')
            elif 'robot' in key:
                d.rectangle((9,6,23,18),fill='#7198A0');d.line((16,2,16,5),fill='#B1CAD0')
                if row in [0,1]:d.rectangle((11,11,13,13),fill='#A4ECED')
                if row in [0,2]:d.rectangle((19,11,21,13),fill='#A4ECED')
                if row==3:d.rectangle((12,10,20,14),fill='#4D737E')
            elif 'explorer' in key:
                d.rectangle((7,7,25,9),fill='#B99868');d.rectangle((11,3,21,6),fill='#B99868')
            if row==3 and 'explorer' in key:d.rectangle((11,21,21,30),fill='#4F7663')
            sheet.alpha_composite(tile,(frame*32,row*48))
    sheet.save(destination)

def main():
    doc=json.loads((ROOT/'catalog.json').read_text());labels={entry['asset_id']:entry['label'] for entry in doc['entries']}
    sprite_root=ROOT/f"revisions/v{doc['version']}/sprites";sprite_root.mkdir(parents=True,exist_ok=True)
    guidance={'styles':{key:{'status':value[0],'prompt':value[1]} for key,value in STYLES.items()},'entries':[]}
    for entry in doc['entries']:
        if entry['kind']=='scene' and not entry.get('reusable_asset_ids'):
            payload=(ROOT/entry['glb_path']).read_bytes()
            length=struct.unpack_from('<I',payload,12)[0]
            gltf=json.loads(payload[20:20+length])
            entry['reusable_asset_ids']=sorted({node.get('extras',{}).get('source_asset_id') for node in gltf.get('nodes',[]) if node.get('extras',{}).get('source_asset_id') in labels})
        entry.setdefault('art_style','体素' if 'voxel' in entry['asset_id'] else 'PBR材质' if 'pbr-pump' in entry['asset_id'] else '低多边形')
        if entry['kind']=='character':
            filename=entry['asset_id']+'.png';sprite(entry,sprite_root/filename)
            entry['sprite_path']=f"revisions/v{doc['version']}/sprites/"+filename
            entry['sprite_layout']={'frame_width':32,'frame_height':48,'columns':4,'rows':4,'directions':['down','left','right','up'],'fps':6,'foot_anchor':[16,46]}
        entry['style_prompts']={style:prompt(entry,style,labels) for style in STYLES}
        default='写实' if entry['art_style']=='PBR材质' else entry['art_style']
        entry['generation_prompt']=entry['style_prompts'][default]
        guidance['entries'].append({'asset_id':entry['asset_id'],'label':entry['label'],'style_prompts':entry['style_prompts']})
    (ROOT/'catalog.json').write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n')
    (SOURCE.parent/'agent-prompts.json').write_text(json.dumps(guidance,ensure_ascii=False,indent=2)+'\n')
    text=['# 场景库美术方向与 agent 生成指南','',COMMON,'']
    for style,(status,body) in STYLES.items():text += ['## '+style,'', '**当前状态：** '+status,'',body,'']
    text+=['## 按资产生成','', '完整可复制提示词位于 `agent-prompts.json`；包含每项资产的尺寸、已有复用部件与各目标风格。内置资产详情也可选择目标风格并复制提示词。','', '提示词是生成指导，不能当作实际交付证明。角色是否绑定及其动画以条目的 rig 和 animations 字段、实际 GLB 检查为准；像素图集为独立二维资源。']
    (SOURCE.parent/'AGENT_GUIDE.md').write_text('\n'.join(text)+'\n')
    print('GUIDANCE_COMPLETE',len(doc['entries']))

if __name__=='__main__':main()
