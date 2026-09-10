"""Conversation-owned first playable brief; model output never grants execution."""
from uuid import uuid4
from fastapi import HTTPException
from .journey_models import JourneyMessage, ProjectDiscussionReply


async def discuss_game(service, state, command):
    from .journey import timestamp
    if state.active_card_id or state.active_modeling_id:
        raise HTTPException(409, '请回到项目主对话继续讨论游戏。')
    messages = state.messages
    latest = next((item for item in reversed(messages) if item.question), None)
    unanswered = latest and not any(item.reply_to == latest.id for item in messages)
    text = command.text.strip()
    reply_to = None
    if command.question_message_id:
        if not unanswered or latest.id != command.question_message_id:
            raise HTTPException(409, '这道问题已回答或已更新，请查看当前问题。')
        reply_to = latest.id
        if command.option_index is not None:
            if command.option_index >= len(latest.question.options):
                raise HTTPException(422, '选项不存在。')
            text = latest.question.options[command.option_index].label
    elif command.option_index is not None:
        raise HTTPException(422, '选项必须绑定当前问题。')
    elif unanswered:
        reply_to = latest.id
    if not text:
        raise HTTPException(422, '请输入内容。')
    messages.append(JourneyMessage(id=uuid4().hex, role='user', text=text,
        created_at=timestamp(), reply_to=reply_to))
    result = await service.generate(state,
        '这是项目主对话：用户只需讨论想法、回答关键问题，然后开始制作。'
        '主动澄清真正影响玩法或范围的未知项，每轮最多一个问题；给2至3个选择并推荐一个，也允许自由回答。'
        '不要让用户先开启grill、填写表单、选择代码架构、确认大纲或制作卡片。'
        '技术实现由你推荐；已有technical_plan时必须沿用其架构。'
        '制作摘要必须根据视角与玩法明确camera_mode：一屏场景fit-scene；大型可移动场景follow-player；第一人称first-person；横向关卡side-scroll。'
        '在text中用普通语言说明相机看什么或跟随谁、可玩范围与适配大小，不让用户填写相机技术参数。'
        '信息足以完成初版时停止追问，返回direction作为可审阅的制作摘要，text简短说明核心玩法、风格和范围。'
        '用户说由你决定时采用合理且明确说明的方案，不继续追问。'
        '普通讨论可以只返回text；有question时direction必须为空。'
        '不要声称已制作，不决定权限；开始制作由用户操作，权限由独立选择器管理。只返回schema JSON。',
        ProjectDiscussionReply)
    reply = ProjectDiscussionReply.model_validate_json(result.text)
    if reply.direction and state.technical_plan and reply.direction.code_architecture != state.technical_plan.code_architecture:
        raise HTTPException(409, '建议与当前工程架构不一致，请重新讨论；不会自动迁移已有工程。')
    state.demo_direction_draft = reply.direction
    messages.append(JourneyMessage(id=result.memory_message_id, role='assistant', text=reply.text,
        question=reply.question, created_at=timestamp(), provider=result.provider, model=result.model))
    state.composer_draft = ''
