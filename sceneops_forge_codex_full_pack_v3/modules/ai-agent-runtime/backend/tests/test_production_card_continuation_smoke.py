from types import SimpleNamespace as NS
from unittest import TestCase
from unittest.mock import Mock
from sceneops_ai_agents.native_production import continue_production
from sceneops_ai_agents.task_models import ContinueProjectDemoRequest
from sceneops_harness import HarnessError

class ProductionCardContinuationSmoke(TestCase):
    def test_context_and_session_are_inherited_and_foreign_workspace_is_rejected(self):
        card=NS(workspace_id='workspace',workspace_root='/tmp/game',permission_mode='full',alignment_id='direction_11111111111111111111111111111111',
                allow_game_execution=True,allow_dependency_install=True,allow_image_generation=False,
                allow_blender_edit=False,allow_browser_observation=True,allow_browser_interaction=True)
        task=NS(id='old',project_id='project',provider_id='codebuddycli',status='review_required',owner_pid=None,
                created_at='2026-09-09',authorization_card=card,
                observations={'native_session_id':'same-session','creation_brief':{'content':'original'}})
        next_task=NS(id='new',observations={},authorization_card=NS(id='auth'))
        context={'workspace_id':'workspace','card':{'id':'weapon'},'sources':[{'id':'real-source'}]}
        service=NS(provider=NS(settings=lambda:NS(provider='codebuddycli')),list=lambda _: [task],
                   project_demo_workspace=Mock(),workspace=NS(open_project_demo_workspace=lambda _:dict(workspace_root='/tmp/game',workspace_id='workspace')),
                   production_card_context=Mock(return_value=context),prepare=Mock(return_value=next_task),authorize=Mock(return_value=next_task),
                   records=NS(update=lambda task_id,fn,event:fn(next_task)))
        request=ContinueProjectDemoRequest(request_id='request',planning_card_id='weapon',goal='调整枪身颜色')
        continue_production(service,task,request)
        self.assertEqual(next_task.observations['native_session_id'],'same-session')
        self.assertEqual(next_task.observations['planning_card_id'],'weapon')
        self.assertEqual(next_task.observations['production_card_context'],context)
        self.assertEqual(service.prepare.call_args.args[0].alignment_id,'direction_11111111111111111111111111111111')
        service.prepare.reset_mock();service.authorize.reset_mock()
        service.production_card_context.return_value={**context,'workspace_id':'foreign'}
        with self.assertRaises(HarnessError):continue_production(service,task,request)
        service.prepare.assert_not_called();service.authorize.assert_not_called()

import asyncio
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock
import test_project_native_authorization as fixture
from sceneops_ai_agents import AuthorizeAgentTask, production_snapshot

class ProductionCardRoundTripSmoke(IsolatedAsyncioTestCase):
    asyncSetUp = fixture.ProjectNativeAuthorizationSmoke.asyncSetUp
    asyncTearDown = fixture.ProjectNativeAuthorizationSmoke.asyncTearDown
    request = fixture.ProjectNativeAuthorizationSmoke.request

    async def test_native_card_reuses_source_identity_and_updates_same_playable(self):
        sessions=[];prompts=[]
        async def execute(prompt,**kwargs):
            sessions.append(kwargs.get('session_id'));prompts.append(prompt)
            await kwargs['on_event']({'type':'session_started','session_id':'same-project-session'})
            (kwargs['workspace_root']/'src/weapon.ts').write_text('export const color = '+('1' if len(sessions)==1 else '2')+';')
            return {'result':'fixture','session_id':'same-project-session','cli_version':'fixture'}
        self.provider.execute_task=AsyncMock(side_effect=execute)
        task=self.service.prepare(self.request().model_copy(update={'native_production':True,'permission_mode':'scoped'}))
        self.service.authorize(task.id,AuthorizeAgentTask(authorization_card_id=task.authorization_card.id,
            accept_unknown_cost=True,creation_brief_version=1))
        await asyncio.gather(*list(self.service.jobs.values()))
        initial=production_snapshot(self.service,self.project.project_id)
        source=next(item for item in initial['sources'] if item['path']=='src/weapon.ts')
        self.service.production_card_context=lambda project,card:dict(workspace_id=initial['workspace_id'],
            card={'id':card,'title':'武器'},sources=[source],conversation_id='original')
        next_task=self.service.continue_project_demo(task.id,ContinueProjectDemoRequest(
            request_id='weapon-adjust',goal='调整武器颜色',planning_card_id='weapon'))
        await asyncio.gather(*list(self.service.jobs.values()))
        result=self.service.get(next_task.id)
        self.assertEqual(result.status,'review_required',result.reason)
        self.assertEqual(sessions,[None,'same-project-session'])
        self.assertIn('当前制作卡片',prompts[-1]);self.assertIn(source['id'],prompts[-1])
        current=production_snapshot(self.service,self.project.project_id)
        changed=next(item for item in current['sources'] if item['path']=='src/weapon.ts')
        self.assertEqual(changed['id'],source['id']);self.assertGreater(changed['source_version'],source['source_version'])
        self.assertEqual(current['workspace_id'],initial['workspace_id'])
        self.assertEqual(result.observations['planning_card_id'],'weapon')
        self.assertIsNotNone(self.service.game_status(result.id).current_playable_candidate)
