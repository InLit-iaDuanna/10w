"""Turn an observed native project into editable planning, without forking its files."""
from fastapi import HTTPException
from .journey_models import ExistingProductionPlan, ProductionBasis
from .journey_changes import propose_change


def snapshot(service, state):
    if service.production_snapshot is None:
        raise HTTPException(409, '当前宿主尚未连接初版内容读取。')
    data = service.production_snapshot(state.project_id)
    if state.production_basis and data['workspace_id'] != state.production_basis.workspace_id:
        raise HTTPException(409, '当前工程已变化，请核对项目绑定。')
    return data


def validate_sources(cards, data):
    known = {source['id'] for source in data['sources']}
    if any(not card.source_ids or not set(card.source_ids) <= known for card in cards):
        raise HTTPException(409, '制作卡片关联的源码不存在或已移除，请重新整理策划。')


async def organize(service, state):
    if not state.technical_plan or not state.initial_demo_direction:
        raise HTTPException(409, '请先完成初版方向与工程准备。')
    if state.cards and not state.production_basis:
        raise HTTPException(409, '这个项目已有分支制作卡片，请沿用现有制作流程。')
    data = snapshot(service, state)
    result = await service.generate(state,
        '基于当前工程源码、已确认初版方向与制作记录，整理完整策划草稿和分项制作卡。'
        '保留已有玩法与代码架构，区分已实现、待核实、建议下一步；源码存在不等于玩法已验证。'
        '用户尚未决定的扩展写入 assumptions，不擅自新增必做系统。'
        '按实际可独立调整的部分拆卡，通常4至8张，例如武器与射击、敌人、场景、UI与反馈；'
        '这些仅是例子，按本项目实际内容命名，不强加枪战概念。'
        'cards是项目功能包，固定七生产领域由系统提供，不能修改。每包domain_ids关联一个或多个：planning、assets-animation、world、gameplay、lookdev、ui-audio、delivery。'
        '已有功能包必须保留原ID、会话和源码关联；可以补充领域归属。'
        '每张卡的 source_ids 必须选择下面实际源码的 id，不使用路径代替、不编造 ID。'
        '描述包含当前实现与下一步调整，acceptance 给出在同一游戏中可观察的验收条件。'
        '源码生成的几何体标为源码驱动，不能声称已登记为独立模型资产。'
        '文字简洁，大纲每项不超过300字，卡片描述与验收分别不超过200字。'
        '全部卡片保持 planned，输出 schema JSON。', ExistingProductionPlan, timeout=600,
        context={'direction': state.initial_demo_direction.model_dump(mode='json'),
                 'technical_plan': state.technical_plan.model_dump(mode='json'),
                 'existing_outline': state.outline.model_dump(mode='json') if state.outline else None,
                 'existing_cards': [card.model_dump(mode='json') for card in state.cards],
                 'production': data})
    proposal = ExistingProductionPlan.model_validate_json(result.text)
    if set(card.id for card in state.cards) - set(card.id for card in proposal.cards):
        raise HTTPException(409, '整理结果移除了已有功能包，请保留原功能包身份后重试。')
    validate_sources(proposal.cards, data)
    if state.outline:
        propose_change(state, proposal.outline, proposal.cards, '根据当前初版整理策划和源码关联，等待审阅。')
    else:
        state.outline, state.cards = proposal.outline, proposal.cards
    state.production_basis = ProductionBasis(task_id=data['task_id'], workspace_id=data['workspace_id'])
    state.stage = 'outline'


def card_context(service, state, card_id):
    if not state.production_basis or not state.versions:
        raise HTTPException(409, '先审阅并确认从初版整理的策划。')
    card = next((item for item in state.cards if item.id == card_id), None)
    if card is None:
        raise HTTPException(404, '制作卡片已移除。')
    data = snapshot(service, state)
    validate_sources([card], data)
    return {'workspace_id': data['workspace_id'], 'card': card.model_dump(mode='json'),
            'planning_revision': state.revision,
            'production_domains': {key:value.model_dump(mode='json') for key,value in state.domain_work.items() if key in card.domain_ids},
            'conversation_id': state.active_conversation_ids.get(card_id, 'original'),
            'outline': state.outline.model_dump(mode='json') if state.outline else None,
            'technical_plan': state.technical_plan.model_dump(mode='json'),
            'sources': [source for source in data['sources'] if source['id'] in card.source_ids],
            'discussion': [item.model_dump(mode='json') for item in state.card_messages.get(card_id, [])][-20:]}
