"""U1 service boundaries with registered fixtures; no Editor or model execution."""
import asyncio
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError
from asset_library import ProjectAssetRegistration, ProjectAssetVersion, DoorRecipe
from sceneops_ai_agents import AuthorizeAgentTask
from sceneops_ai_agents.task_models import AgentAction, now
from sceneops_ai_agents.task_loop import changeset, record_action, MUTATIONS
from sceneops_ai_agents.task_tools import TaskTools
from sceneops_ai_agents.unity_content_models import PrepareUnityAssetTask, UnityManualRequest
from sceneops_ai_agents.unity_tasks import prepare_unity_task, unity_target, unity_source, UNITY_CONTENT_CAPABILITIES
from sceneops_ai_agents.unity_content import content_snapshot
from sceneops_harness import HarnessError, HarnessRuntime
from test_project_demo_agent import make_service


def fixture_source(root):
    service, provider, assets, scenes, project, request = make_service(root, 'key-door')
    source = service.prepare(request)
    blend = Path(source.authorization_card.workspace_root) / 'fixture-source.blend'
    blend.write_bytes(b'BLENDER explicitly synthetic U1 service fixture; never open in Editor')
    registration = ProjectAssetRegistration(project_id=project.project_id,
        workspace_id=source.authorization_card.workspace_id, source_asset_id='u1-fixture-source',
        title='U1 fixture door', source_type='generated', version=ProjectAssetVersion(
            source_version=2, asset_version_id='u1-fixture-version', source_kind='blender',
            dimensions_m=(1,2,.2), vertex_count=8, triangle_count=12,
            operation='blender-edit', blend_path=str(blend), preview_path=str(root/'fixture.glb'),
            parent_source_version=1, runtime_artifacts=[dict(artifact_id='glb_fixture',artifact_type='render',project_relative_path='public/fixture.glb')],
            node_ids={'root':'node_fixture'}))
    assets.register_version(registration.model_copy(update={'version':ProjectAssetVersion(source_version=1,asset_version_id='fixture-parent',source_kind='procedural',dimensions_m=(1,2,.2),vertex_count=8,triangle_count=12,operation='recipe-create',recipe=DoorRecipe(width_m=1,height_m=2,thickness_m=.2))}))
    asset = assets.register_version(registration.model_copy(update={'expected_version':1})).entry
    return service, provider, source, asset, blend


async def authorize_without_execution(service, task):
    async def record_idle(task_id, **kwargs):
        service.records.update(task_id, lambda current: setattr(current, 'status', 'review_required'),
            'agent.task.fixture_idle')
    with patch.object(service, '_run', record_idle):
        service.authorize(task.id, AuthorizeAgentTask(
            authorization_card_id=task.authorization_card.id, accept_unknown_cost=True))
        await asyncio.gather(*list(service.jobs.values()))
    return service.get(task.id)


def test_unity_separate_finite_grant_preserves_web_workspace_and_source(tmp_path):
    async def scenario():
        service, provider, source, asset, blend = fixture_source(tmp_path)
        try:
            web = await authorize_without_execution(service, source)
            service.records.update(web.id, lambda current: setattr(current, 'owner_pid', None),
                'agent.task.worker_released')
            old_grant = web.grant.model_dump(mode='json')
            body = PrepareUnityAssetTask(asset_id=asset.id, source_version=2)
            target = prepare_unity_task(service, source.id, body)
            assert target.grant is None
            assert prepare_unity_task(service, source.id, body).id == target.id
            assert not provider.requests
            assert not Path(target.authorization_card.workspace_root).exists()
            unity = await authorize_without_execution(service, target)
            assert unity.grant.workspace_root != web.grant.workspace_root
            assert unity.grant.workspace_id != web.grant.workspace_id
            assert unity.grant.capability_ids == UNITY_CONTENT_CAPABILITIES
            assert unity.grant.budget.max_steps == 64
            assert unity.grant.budget.max_metered_calls == 16
            assert 0 < (unity.grant.expires_at-now()).total_seconds() <= 1800
            assert service.get(source.id).grant.model_dump(mode='json') == old_grant
            assert service.records.owns_workspace(web.project_id, web.grant.workspace_root)
            assert not service.records.owns_workspace(web.project_id, unity.grant.workspace_root)
            assert service.check_grant(unity.id).id == unity.id
            assert unity_source(service, unity, 2)[2] == blend
            assert blend.read_bytes().startswith(b'BLENDER explicitly synthetic')
            assert not provider.requests
        finally:
            await service.close()
    asyncio.run(scenario())


def test_unity_rejects_arbitrary_or_mismatched_scope(tmp_path):
    async def scenario():
        service, _, source, asset, _ = fixture_source(tmp_path)
        try:
            with pytest.raises(ValidationError):
                PrepareUnityAssetTask(asset_id=asset.id, source_version=2, workspace_root='/arbitrary')
            target = prepare_unity_task(service, source.id, PrepareUnityAssetTask(asset_id=asset.id,source_version=2))
            tampered = target.model_copy(deep=True)
            tampered.authorization_card.workspace_root = '/arbitrary'
            with pytest.raises(HarnessError,match='不一致'):
                unity_target(service,tampered)
            tampered = target.model_copy(deep=True)
            tampered.observations['unity_target']['project_id'] = 'other-project'
            with pytest.raises(HarnessError,match='不一致'):
                unity_target(service,tampered)
            authorized = await authorize_without_execution(service,target)
            service.records.update(authorized.id, lambda current: setattr(current.grant,'workspace_root',source.authorization_card.workspace_root),'agent.fixture_tamper')
            with pytest.raises(HarnessError,match='不一致'):
                service.check_grant(authorized.id)
        finally:
            await service.close()
    asyncio.run(scenario())


def test_empty_manual_edit_rejected_before_task_ownership(tmp_path):
    service, _, source, asset, _ = fixture_source(tmp_path)
    try:
        target=prepare_unity_task(service,source.id,PrepareUnityAssetTask(asset_id=asset.id,source_version=2))
        before=service.get(target.id).model_dump(mode='json')
        with pytest.raises(ValidationError):
            UnityManualRequest(request_id='empty_edit_request',operation='edit',instance_id='instance',
                expected={'position':[0,0,0],'interaction_distance':1,'requires_key':True})
        after=service.get(target.id)
        assert after.model_dump(mode='json') == before
        assert after.owner_pid is None
        with pytest.raises(ValidationError):
            UnityManualRequest(request_id='invalid-play-input',operation='act',move_z=2,duration_frames=121)
    finally:
        asyncio.run(service.close())


def test_unity_capabilities_project_and_mutations_have_changesets(tmp_path):
    async def scenario():
        service, _, source, asset, _ = fixture_source(tmp_path)
        try:
            task=await authorize_without_execution(service,prepare_unity_task(service,source.id,
                PrepareUnityAssetTask(asset_id=asset.id,source_version=2)))
            registry=TaskTools(service,task.id).registry()
            assert set(UNITY_CONTENT_CAPABILITIES) <= {cap.id for cap in registry.list()}
            instance=task.observations['unity_target']['instance_ids'][0]
            values={'position':[0,0,0],'interaction_distance':1,'requires_key':True}
            inputs={'blender.asset.derive_unity':{'source_version':2},
                'unity.content.import':{'source_version':2,'expected_source_version':0},
                'unity.content.inspect':{},'unity.content.edit':{'instance_id':instance,'expected':values,'position':[1,0,0]},
                'unity.content.focus':{'instance_id':instance},'unity.content.save':{'reopen':False},
                'unity.content.play':{'operation':'enter'}}
            for index,(cap,body) in enumerate(inputs.items()):
                action=AgentAction(action_id=f'u1-fixture-{index}',capability_id=cap,rationale='Fixture contract projection',inputs=body)
                record_action(service,task.id,action)
                updated=service.get(task.id)
                entry=next(item for item in updated.actions if item.action.action_id==action.action_id)
                projected=next(step for step in service.production.snapshot(task.project_id).steps if step.id==f'{task.id}:{action.action_id}')
                assert projected.module_id == ('concept-assets' if cap.startswith('blender.') else 'unity-build')
                assert (cap in MUTATIONS) == (cap != 'unity.content.inspect')
                if cap in MUTATIONS:
                    change=changeset(updated,entry)
                    assert change.target.module_id=='ai-agent-runtime'
                    assert list(change.target.object_ids)==[task.project_id]
            assert not service.provider.requests
        finally:
            await service.close()
    asyncio.run(scenario())


def test_expired_unity_snapshot_returns_cached_without_editor_call(tmp_path):
    async def scenario():
        service, _, source, asset, _ = fixture_source(tmp_path)
        try:
            task=await authorize_without_execution(service,prepare_unity_task(service,source.id,
                PrepareUnityAssetTask(asset_id=asset.id,source_version=2)))
            def expire(current):
                current.grant.expires_at=now()-timedelta(seconds=1)
                current.observations['unity_content']={'source_version':'1','instances':[],'dirty':False}
            service.records.update(task.id,expire,'agent.fixture_expired')
            sync=AsyncMock(side_effect=AssertionError('Expired snapshots must not contact Editor'))
            service.tools[task.id]=SimpleNamespace(sessions={'unity':SimpleNamespace(stop=lambda:None)},sync=sync)
            snapshot=await content_snapshot(service,task.id)
            assert snapshot.mode=='cached'
            assert snapshot.imported_source_version==1
            sync.assert_not_called()
        finally:
            service.tools.clear()
            await service.close()
    asyncio.run(scenario())


def test_explicit_unity_renewal_preserves_target_and_lifetime_usage(tmp_path):
    async def scenario():
        from sceneops_ai_agents.unity_continuation import prepare_unity_continuation
        from sceneops_ai_agents.demo_continuation import demo_window_usage
        service,_,source,asset,_=fixture_source(tmp_path)
        try:
            task=await authorize_without_execution(service,prepare_unity_task(service,source.id,
                PrepareUnityAssetTask(asset_id=asset.id,source_version=2)))
            with pytest.raises(HarnessError,match='仍有效'):
                prepare_unity_continuation(service,task.id,'renew-first')
            def expire(current):
                current.grant.expires_at=now()-timedelta(seconds=1)
                current.model_calls_used=3
            service.records.update(task.id,expire,'agent.fixture_expired')
            old=service.get(task.id);target=dict(old.observations['unity_target'])
            prepared=prepare_unity_continuation(service,task.id,'renew-first')
            assert prepared.grant is None and prepared.status=='awaiting_authorization'
            service.authorize(task.id,AuthorizeAgentTask(authorization_card_id=prepared.authorization_card.id,accept_unknown_cost=True))
            renewed=service.get(task.id)
            assert renewed.grant.id!=old.grant.id and renewed.model_calls_used==3
            assert renewed.observations['unity_target']==target
            assert demo_window_usage(renewed)['model_calls']==0
            assert renewed.status=='review_required' and task.id not in service.jobs
            assert service.check_grant(task.id).grant.workspace_root==old.grant.workspace_root
        finally:await service.close()
    asyncio.run(scenario())


def test_unity_blender_session_is_scoped_to_the_current_grant(tmp_path):
    async def scenario():
        service,_,source,asset,_=fixture_source(tmp_path)
        captured={}
        class Session:
            def __init__(self,root,state):captured.update(root=Path(root),state=Path(state))
            def bind_authorization(self,binding):self.binding=binding
            def start(self):
                return {'mode':'live','session_id':'blender-fixture','workspace_root':str(captured['root'])}
            def stop(self):pass
        service.blender_factory=Session
        try:
            task=await authorize_without_execution(service,prepare_unity_task(service,source.id,
                PrepareUnityAssetTask(asset_id=asset.id,source_version=2)))
            tools=TaskTools(service,task.id)
            await tools.session('blender',headless=True)
            assert captured['state']==service.state_base/task.id/'blender'/task.grant.id
            assert captured['root']==Path(task.grant.workspace_root)
        finally:await service.close()
    asyncio.run(scenario())


def test_import_precondition_is_no_effect_and_never_starts_unity(tmp_path):
    async def scenario():
        from sceneops_ai_agents.task_loop import execute_action
        service,_,source,asset,_=fixture_source(tmp_path)
        try:
            task=await authorize_without_execution(service,prepare_unity_task(service,source.id,
                PrepareUnityAssetTask(asset_id=asset.id,source_version=2)))
            service.unity_factory=lambda *_:(_ for _ in ()).throw(AssertionError('Unity must not start'))
            service.tools[task.id]=TaskTools(service,task.id)
            service.runtimes[task.id]=HarnessRuntime(service.database_path,service.tools[task.id].registry())
            action=AgentAction(action_id='import-without-export',capability_id='unity.content.import',
                rationale='Fixture precondition check',inputs={'source_version':2,'expected_source_version':0})
            record_action(service,task.id,action)
            await execute_action(service,task.id,action.action_id)
            entry=next(item for item in service.get(task.id).actions if item.action.action_id==action.action_id)
            assert entry.state=='failed' and entry.effect_state=='NONE'
            assert entry.result['evidence']['code']=='UNITY_EXPORT_REQUIRED'
        finally:await service.close()
    asyncio.run(scenario())


def test_manual_import_stops_when_derivation_is_blocked(tmp_path):
    async def scenario():
        from sceneops_ai_agents.unity_manual import execute_unity_manual
        service,_,source,asset,_=fixture_source(tmp_path)
        class BlockedBlender:
            def __init__(self,*_):pass
            def bind_authorization(self,_):pass
            def start(self):raise RuntimeError('fixture Blender unavailable')
            def stop(self):pass
        service.blender_factory=BlockedBlender
        try:
            task=await authorize_without_execution(service,prepare_unity_task(service,source.id,
                PrepareUnityAssetTask(asset_id=asset.id,source_version=2)))
            result=await execute_unity_manual(service,task.id,UnityManualRequest(
                request_id='manual-import-stop',operation='import',source_version=2))
            matching=[item for item in result.actions if item.action.action_id.startswith('unity_manual_manual-import-stop')]
            assert len(matching)==1
            assert matching[0].action.capability_id=='blender.asset.derive_unity'
            assert matching[0].state=='blocked' and matching[0].effect_state=='NONE'
        finally:await service.close()
    asyncio.run(scenario())


def test_reconcile_missing_export_and_dispatch_as_no_effect(tmp_path):
    async def scenario():
        from sceneops_ai_agents.unity_continuation import reconcile_unity
        service,_,source,asset,_=fixture_source(tmp_path)
        try:
            task=await authorize_without_execution(service,prepare_unity_task(service,source.id,
                PrepareUnityAssetTask(asset_id=asset.id,source_version=2)))
            action=AgentAction(action_id='uncertain-before-dispatch',capability_id='unity.content.import',
                rationale='Fixture interrupted precondition',inputs={'source_version':2,'expected_source_version':0})
            record_action(service,task.id,action)
            def uncertain(current):
                entry=next(item for item in current.actions if item.action.action_id==action.action_id)
                entry.state='uncertain';entry.effect_state='UNKNOWN';current.status='needs_approval'
                current.pending_action_id=action.action_id
            service.records.update(task.id,uncertain,'agent.fixture_uncertain')
            result=reconcile_unity(service,task.id)
            entry=next(item for item in result.actions if item.action.action_id==action.action_id)
            assert entry.state=='failed' and entry.effect_state=='NONE'
            assert entry.result['evidence']['outcome']=='not_dispatched'
            assert result.status=='review_required' and result.pending_action_id is None
        finally:await service.close()
    asyncio.run(scenario())


def test_cached_unity_session_rechecks_editor_liveness(tmp_path):
    async def scenario():
        service,_,source,asset,_=fixture_source(tmp_path)
        starts=[]
        class Session:
            def __init__(self,root,_):self.root=Path(root)
            def bind_authorization(self,binding):self.binding=binding
            def start(self):
                starts.append(self.binding['grant_id'])
                return {'mode':'live','session_id':'unity-fixture','workspace_root':str(self.root)}
            def stop(self):pass
        service.unity_factory=Session
        try:
            task=await authorize_without_execution(service,prepare_unity_task(service,source.id,
                PrepareUnityAssetTask(asset_id=asset.id,source_version=2)))
            tools=TaskTools(service,task.id)
            first=await tools.session('unity')
            second=await tools.session('unity')
            assert first is second and starts==[task.grant.id,task.grant.id]
        finally:await service.close()
    asyncio.run(scenario())
