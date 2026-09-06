"""Reviewable planning edits; accepting changes never creates a formal version."""
from uuid import uuid4
from fastapi import HTTPException
from .journey_models import CardProposal, JourneyChange


def propose_change(state, outline, cards, rationale):
    if cards: CardProposal(cards=cards)
    if outline == state.outline and cards == state.cards: return
    state.changes.append(JourneyChange(id='change_' + uuid4().hex, base_revision=state.revision,
        before_outline=state.outline.model_copy(deep=True) if state.outline else None,
        before_cards=[card.model_copy(deep=True) for card in state.cards],
        after_outline=outline, after_cards=cards, rationale=rationale))


def resolve_change(state, change_id, accept):
    change = next((item for item in state.changes if item.id == change_id), None)
    if not change or change.status != 'pending':
        raise HTTPException(409, '修改提案不存在或已处理，请重新读取。')
    if not accept:
        change.status = 'rejected'
        return
    # Chat/autosave revisions do not invalidate a proposal, but design changes do.
    if state.outline != change.before_outline or state.cards != change.before_cards:
        raise HTTPException(409, '大纲或卡片已变化，不能覆盖新内容。请重新提出修改。')
    state.outline = change.after_outline.model_copy(deep=True) if change.after_outline else None
    state.cards = [card.model_copy(deep=True) for card in change.after_cards]
    if state.active_card_id not in {card.id for card in state.cards}:
        state.active_card_id = None
        state.active_modeling_id = None
    change.status = 'accepted'
