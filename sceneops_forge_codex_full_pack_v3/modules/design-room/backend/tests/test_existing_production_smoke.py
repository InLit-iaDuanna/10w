import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from fastapi import HTTPException
from sceneops_project_workspace import SqliteWorkspaceRepository
from sceneops_design_ai import PlanningJourneyService
from sceneops_design_ai.journey_models import JourneyCommand

DIRECTION = dict(core_experience='第一人称射击', perspective_style='低模竞技场',
                 simplified_scope='单武器，三波敌人', code_architecture='object-component',camera_mode='first-person')
OUTLINE = dict(title='竞技场',experience='射击',core_loop='生存三波',scope='单场景',acceptance='可重开',assumptions=[])
SOURCE = dict(id='source_weapon',path='src/game/Weapon.ts',content='export class Weapon {}',source_version=1)

class Provider:
    def settings(self): return SimpleNamespace(model='fixture',provider='codebuddycli')
    async def generate(self,prompt,**kwargs):
        assert 'source_weapon' in prompt
        return SimpleNamespace(provider='codebuddycli',model='fixture',text=json.dumps(dict(outline=OUTLINE,cards=[
            dict(id='weapon',title='武器与射击',description='已实现枪械，下一步调整外观',acceptance='原游戏内验证',source_ids=['source_weapon'],domain_ids=['gameplay','lookdev'])])))

class ExistingProductionSmoke(unittest.IsolatedAsyncioTestCase):
    async def test_organize_confirm_select_without_git_and_reject_missing_source(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();db=root/'state.sqlite3';folders=SqliteWorkspaceRepository(db)
            project=folders.create_folder_project(root,'game')
            data=dict(task_id='native-round',workspace_id='workspace',sources=[SOURCE],rounds=[])
            service=PlanningJourneyService(db,folders,Provider(),production_snapshot=lambda _:data)
            state=service.get(project.project_id)
            async def act(op,**values):
                nonlocal state
                state=await service.command(project.project_id,JourneyCommand(operation=op,request_id=f'r{state.revision}',expected_revision=state.revision,**values))
                return state
            await act('confirm_demo_direction',**DIRECTION)
            game=Path(state.root_path)/'src/game/Game.ts';before=game.read_text()
            with patch.object(folders,'ensure_project_git',side_effect=AssertionError('must not initialize Git')),patch.object(folders,'open_card_worktree',side_effect=AssertionError('must not fork')):
                await act('organize_production')
                self.assertEqual(state.stage,'outline');self.assertFalse(state.versions)
                with self.assertRaises(HTTPException):service.production_card_context(project.project_id,'weapon')
                await act('confirm_version')
                await act('select_card',card_id='weapon')
                self.assertEqual(state.stage,'cards');self.assertEqual(state.card_branches,[])
                self.assertEqual(state.card_messages,{})
                context=service.production_card_context(project.project_id,'weapon')
                self.assertEqual(context['sources'],[SOURCE])
                self.assertEqual(game.read_text(),before)
                self.assertEqual(service.get(project.project_id).production_basis.workspace_id,'workspace')
                original_cards=[card.id for card in state.cards]
                original_messages=state.card_messages.copy()
                from sceneops_project_workspace import PRODUCTION_DOMAINS
                for domain in PRODUCTION_DOMAINS:
                    await act('save_domain',domain_id=domain['id'],domain_work={'brief':domain['title'],'stage':'graybox'})
                await act('assign_card_domains',card_id='weapon',domain_ids=['gameplay','assets-animation','lookdev'])
                self.assertEqual(len(service.get(project.project_id).domain_work),7)
                self.assertEqual([card.id for card in state.cards],original_cards)
                self.assertEqual(state.card_messages,original_messages)
                self.assertEqual(service.production_card_context(project.project_id,'weapon')['sources'],[SOURCE])
                with self.assertRaises(HTTPException):
                    await service.command(project.project_id,JourneyCommand(operation='save_domain',request_id='stale-domain',expected_revision=state.revision-1,domain_id='world',domain_work={'brief':'stale'}))
                data['sources']=[]
                with self.assertRaises(HTTPException):service.production_card_context(project.project_id,'weapon')
