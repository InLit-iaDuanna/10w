"""Card-owned modeling briefs. Transport and production authority remain separate."""
from uuid import uuid4
from fastapi import HTTPException
from .journey_models import CardModelingSession


MODELING_BLOCKS = (
    {'id': 'shape', 'label': '用途与整体轮廓',
     'focus': '明确模型在游戏中的用途、视觉风格、辨识特征和整体轮廓'},
    {'id': 'scale', 'label': '比例与尺寸',
     'focus': '明确真实单位、主要部件比例、朝向和与玩家或场景的尺度关系'},
    {'id': 'surface', 'label': '材质与配色',
     'focus': '明确材质语言、主辅色、表面细节和低多边形表现'},
    {'id': 'interaction', 'label': '场景关系与交互',
     'focus': '明确碰撞、动画或静态要求、摆放方式以及后续 Three.js 使用约束'},
    {'id': 'performance', 'label': '几何复杂度与性能',
     'focus': '明确同屏数量、轮廓优先级、几何细节预算和远近观看需求'},
    {'id': 'variation', 'label': '复用与造型变化',
     'focus': '明确是否需要模块化部件、造型变体、随机旋转缩放或成组摆放'},
    {'id': 'lighting', 'label': '光照与可读性',
     'focus': '明确投射或接收阴影、明暗层次和在目标镜头中的识别要求'},
    {'id': 'acceptance', 'label': '边界与验收偏好',
     'focus': '明确必须保留、明确禁止和最终人工审阅时最重要的判断标准'},
)


def modeling_block_for_turn(turn: int):
    if turn < len(MODELING_BLOCKS):
        return MODELING_BLOCKS[turn]
    return {'id': 'refinement', 'label': '后续微调', 'focus': '只处理用户本轮明确提出的模型调整'}


def active_modeling(state):
    if not state.active_modeling_id:
        return None
    session = next((item for item in state.modeling_sessions if item.id == state.active_modeling_id), None)
    if session is None or session.card_id != state.active_card_id:
        raise HTTPException(409, '建模对话与当前卡片不一致，请重新选择卡片。')
    return session


def modeling_command(state, command):
    if command.operation == 'close_modeling':
        state.active_modeling_id = None
        return
    if not state.active_card_id or command.card_id != state.active_card_id:
        raise HTTPException(409, '请先进入对应卡片的 Git 分支。')
    if not any(item.card_id == state.active_card_id for item in state.card_branches):
        raise HTTPException(409, '卡片分支尚未准备完成。')
    if command.operation == 'open_modeling':
        session = next((item for item in state.modeling_sessions
                        if item.id == command.modeling_id and item.card_id == state.active_card_id), None)
        if session is None:
            raise HTTPException(409, '该卡片没有这条建模对话。')
    elif command.operation == 'new_modeling':
        if command.model_source not in ('create', 'import'):
            raise HTTPException(422, '请选择导入模型或新建模型。')
        session = CardModelingSession(id='modeling_' + uuid4().hex, card_id=state.active_card_id,
            source=command.model_source,
            stage='brief' if command.model_source == 'create' else 'awaiting_import')
        state.modeling_sessions.append(session)
    else:
        if command.model_source is None:
            raise HTTPException(422, '请选择导入已有模型或新建模型。')
        # Re-entering a source resumes it; switching never destroys the other conversation.
        session = next((item for item in state.modeling_sessions
                        if item.card_id == state.active_card_id and item.source == command.model_source), None)
        if session is None:
            session = CardModelingSession(id='modeling_' + uuid4().hex, card_id=state.active_card_id,
                source=command.model_source, stage='brief' if command.model_source == 'create' else 'awaiting_import')
            state.modeling_sessions.append(session)
    state.active_modeling_id = session.id


def modeling_prompt(state, session, policy, answered):
    card = next(item for item in state.cards if item.id == session.card_id)
    blocks = MODELING_BLOCKS[:policy['limit']]
    if answered >= policy['limit']:
        turn = (f"{policy['label']}对齐的 {policy['limit']} 个建模块已完成。"
            '不要再提出问题或选项；用 text 简短总结模型用途、轮廓、尺度、材质和交互约束。'
            '用户以后仍可继续发送微调要求，每次微调都会成为新的草稿版本。')
    else:
        block = blocks[answered]
        turn = (f"当前采用{policy['label']}对齐，进入第 {answered + 1}/{policy['limit']} 块“{block['label']}”：{block['focus']}。"
            'text 先用一句话说明上一轮已记录并会形成右侧模型草稿，再只针对这一大块提出一个关键决定；'
            'question 给 2 至 3 个有明显差异的选项。不要拆成连续的小参数问题。')
    sequence = '、'.join(block['label'] for block in blocks)
    return ('当前是卡片关联建模子对话，不是项目总策划。只对齐该模型需求，不修改大纲或卡片。'
        f"本档对齐按这些大块推进：{sequence}。"
        '已明确的决定不要重复追问。模型草稿由独立资产执行器异步生成；只能说答案已记录，'
        '不能宣称某个版本已经生成成功，实际状态和 Three.js 预览以右侧面板为准。'
        '不要要求用户填写技术路径、端口或 Blender 参数。'
        f'{turn}只返回schema JSON。\n'
        f'项目技术路线：{state.stack or "待确认"}。'
        f'项目大纲：{state.outline.model_dump_json() if state.outline else "尚未生成"}\n'
        f'卡片：{card.model_dump_json()}\n建模记录：{session.model_dump_json()}')
