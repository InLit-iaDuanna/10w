import unittest
from sceneops_design_ai.journey import PlanningJourneyService
from sceneops_design_ai.journey_models import PlanningJourney, JourneyCommand, JourneyMessage, ProductionCard


class CardConversationTests(unittest.IsolatedAsyncioTestCase):
    async def test_switch_preserves_messages_alignment_and_drafts(self):
        service = object.__new__(PlanningJourneyService)
        state = PlanningJourney(project_id='project', root_path='/tmp/project', active_card_id='core',
            cards=[ProductionCard(id='core', title='Core', description='Build', acceptance='Check')],
            card_messages={'core':[JourneyMessage(id='message', role='user', text='Original goal', created_at='2026-09-07')]},
            card_alignment_summaries={'core':'Original scope'}, card_alignment_summary_ids={'core':'summary'})
        await service.apply(state, JourneyCommand(request_id='new', expected_revision=0, operation='new_conversation', context_draft='original draft'))
        new_id = state.active_conversation_ids['core']
        self.assertEqual(state.card_messages['core'], [])
        self.assertNotIn('core', state.card_alignment_summaries)
        self.assertEqual(len(state.card_conversations['core']), 2)
        state.card_messages['core'].append(JourneyMessage(id='new-message', role='user', text='New goal', created_at='2026-09-07'))
        state = PlanningJourney.model_validate_json(state.model_dump_json())
        await service.apply(state, JourneyCommand(request_id='switch', expected_revision=0, operation='select_conversation', conversation_id='original', context_draft='new draft'))
        self.assertEqual(state.card_messages['core'][0].text, 'Original goal')
        self.assertEqual(state.card_alignment_summaries['core'], 'Original scope')
        self.assertEqual(state.composer_draft, 'original draft')
        await service.apply(state, JourneyCommand(request_id='back', expected_revision=0, operation='select_conversation', conversation_id=new_id))
        self.assertEqual(state.card_messages['core'][0].text, 'New goal')
        self.assertEqual(state.composer_draft, 'new draft')
        self.assertNotIn('core', state.card_alignment_summaries)

    async def test_unknown_conversation_does_not_replace_current(self):
        from fastapi import HTTPException
        service = object.__new__(PlanningJourneyService)
        state = PlanningJourney(project_id='project', root_path='/tmp/project', active_card_id='core',
            cards=[ProductionCard(id='core', title='Core', description='Build', acceptance='Check')])
        with self.assertRaises(HTTPException):
            await service.apply(state, JourneyCommand(request_id='missing', expected_revision=0, operation='select_conversation', conversation_id='other-card'))
        self.assertEqual(state.active_conversation_ids, {})

    async def test_delete_conversation_selects_a_neighbor_and_keeps_card_usable(self):
        service = object.__new__(PlanningJourneyService)
        state = PlanningJourney(project_id='project', root_path='/tmp/project', active_card_id='core',
            cards=[ProductionCard(id='core', title='Core', description='Build', acceptance='Check')],
            card_messages={'core':[JourneyMessage(id='original-message', role='user', text='Original', created_at='2026-09-07')]})
        await service.apply(state, JourneyCommand(request_id='new', expected_revision=0,
            operation='new_conversation'))
        created = state.active_conversation_ids['core']
        state.card_messages['core'] = [JourneyMessage(id='new-message', role='user', text='New', created_at='2026-09-07')]
        await service.apply(state, JourneyCommand(request_id='delete', expected_revision=0,
            operation='delete_conversation', conversation_id=created))
        self.assertEqual(state.active_conversation_ids['core'], 'original')
        self.assertEqual(state.card_messages['core'][0].text, 'Original')
        await service.apply(state, JourneyCommand(request_id='delete-last', expected_revision=0,
            operation='delete_conversation', conversation_id='original'))
        self.assertEqual(len(state.card_conversations['core']), 1)
        self.assertEqual(state.card_messages['core'], [])
        self.assertEqual(state.card_conversations['core'][0].title, '新对话')
