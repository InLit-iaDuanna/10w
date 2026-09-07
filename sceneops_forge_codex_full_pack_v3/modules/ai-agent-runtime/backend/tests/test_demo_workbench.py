"""D4 public services, scripted model decisions, fixture builds and real retained HTTP serving."""
import asyncio
from datetime import timedelta
from urllib.request import urlopen
from unittest.mock import patch
from pathlib import Path
import pytest
from sceneops_harness import HarnessError
from sceneops_ai_agents import AuthorizeAgentTask
from sceneops_ai_agents.task_models import AgentAction, ContinueProjectDemoRequest, now
from sceneops_ai_agents.demo_workbench import content_index, save_content, resolve_target, validate_target_action, play_candidate
from sceneops_ai_agents.demo_workbench_models import DemoEditTarget, DemoContentSave
from sceneops_ai_agents.demo_continuation import prepare_demo_continuation
from test_project_demo_agent import make_service, settle


def test_sources_scope_conflicts_and_retained_sessions(tmp_path):
    asyncio.run(round_trip(tmp_path.resolve()))


async def round_trip(root):
    service, provider, assets, scenes, project, request = make_service(root, 'key-door')
    request = request.model_copy(update={'allow_browser_observation': False})
    # This test uses a scripted model; replace observe with status in its finite script.
    original = provider.key_door_action
    def decision():
        result = original()
        if result['capability_id'] == 'code.browser.observe':
            result['capability_id'] = 'code.project.status'
        return result
    provider.key_door_action = decision
    try:
        task = service.prepare(request)
        service.authorize(task.id, AuthorizeAgentTask(authorization_card_id=task.authorization_card.id, accept_unknown_cost=True))
        await settle(service)
        task = service.get(task.id)
        assert task.status == 'review_required', task.reason
        index = content_index(service, task.id)
        assert len(index.assets) == 1 and len(index.instances) == 2
        candidate = service.game_status(task.id).current_playable_candidate
        old_play = await play_candidate(service, task.id, candidate.id)
        target = DemoEditTarget(project_id=project.project_id, workspace_id=index.workspace_id,
            kind='behavior', id=index.instances[0].behavior.behavior_instance_id,
            source_version=index.scene_version, viewed_candidate_id=candidate.id)
        saved = save_content(service, task.id, DemoContentSave(target=target, interaction_distance_m=1))
        assert saved.content.instances[0].behavior.interaction_distance_m == 1
        assert saved.content.instances[1].behavior is None
        assert saved.content.unbuilt_changes
        with pytest.raises(HarnessError, match='较新版本'):
            save_content(service, task.id, DemoContentSave(target=target, interaction_distance_m=.5))
        with pytest.raises(HarnessError, match='当前项目'):
            resolve_target(service, task, target.model_copy(update={'project_id':'prj_other'}))
        with pytest.raises(HarnessError, match='试玩版本'):
            resolve_target(service, task, target.model_copy(update={'viewed_candidate_id':'other'}))
        task.observations['active_demo_target'] = {**target.model_dump(), 'resolved_object_id':index.instances[0].id}
        with pytest.raises(HarnessError, match='只允许修改选中'):
            validate_target_action(task, AgentAction(action_id='wrong', capability_id='code.file.write', rationale='test', inputs={'path':'src/main.ts'}))
        validate_target_action(task, AgentAction(action_id='right', capability_id='environment.key_door.configure', rationale='test', inputs={'object_id':index.instances[0].id}))
        asset = saved.content.assets[0]
        recipe = asset.versions[-1].recipe.model_copy(update={'thickness_m':.4})
        asset_target = target.model_copy(update={'kind':'asset','id':asset.id,'source_version':asset.current_version,'expected_scene_version':saved.content.scene_version})
        from world_composer import EnvironmentSceneError
        with patch.object(scenes, 'rebind_asset_version', side_effect=EnvironmentSceneError('SCENE_VERSION_CONFLICT', 'concurrent edit')):
            with pytest.raises(HarnessError, match='已保存'):
                save_content(service, task.id, DemoContentSave(target=asset_target, recipe=recipe))
        partial = content_index(service, task.id)
        assert partial.assets[0].current_version == 2
        assert all(item.asset_version == 1 for item in partial.instances)
        asset_target = asset_target.model_copy(update={'source_version':2})
        saved = save_content(service, task.id, DemoContentSave(target=asset_target, recipe=recipe))
        assert saved.content.assets[0].current_version == 2
        assert set(saved.affected_instance_ids) == {item.id for item in index.instances}
        assert len({item.asset_version for item in saved.content.instances}) == 1
        service.update_project_demo(task.id)
        await settle(service)
        fresh = service.game_status(task.id).current_playable_candidate
        assert fresh.id != candidate.id
        new_play = await play_candidate(service, task.id, fresh.id)
        assert new_play.preview_url != old_play.preview_url
        assert urlopen(old_play.preview_url).status == 200
        assert urlopen(new_play.preview_url).status == 200
        source = Path(project.root_path)/'src/game/sceneops-demo-content.ts'
        assert '"thickness_m": 0.4' in source.read_text()
        service.records.update(task.id, lambda record: setattr(record.grant,'expires_at',now()-timedelta(seconds=1)), 'test.expired')
        lifetime = service.get(task.id).model_calls_used
        renewed = prepare_demo_continuation(service, task.id, 'renew1')
        assert renewed.grant is None
        assert (await play_candidate(service, task.id, candidate.id)).candidate_id == candidate.id
        service.authorize(task.id, AuthorizeAgentTask(authorization_card_id=renewed.authorization_card.id, accept_unknown_cost=True))
        assert service.get(task.id).status == 'review_required'
        assert service.get(task.id).model_calls_used == lifetime
        assert task.id not in service.jobs
        # A stopped model can retain a reviewed same-task claim after committed edits.
        with service.records.connect() as connection:
            connection.execute("INSERT OR REPLACE INTO agent_project_claims VALUES(?,?,'review_required')",
                               (task.project_id, task.id))
        service.update_project_demo(task.id)
        await settle(service)
        assert service.get(task.id).status == 'review_required', service.get(task.id).reason
        assert service.get(task.id).model_calls_used == lifetime
    finally:
        await service.close()


def test_source_navigation_uses_real_write_identity_and_detects_external_edits(tmp_path):
    asyncio.run(source_navigation(tmp_path.resolve()))


async def source_navigation(root):
    service, provider, _, _, project, request = make_service(root, 'switch')
    try:
        task = service.prepare(request)
        service.authorize(task.id, AuthorizeAgentTask(authorization_card_id=task.authorization_card.id, accept_unknown_cost=True))
        await settle(service)
        first = content_index(service, task.id)
        module = next(item for item in first.sources if item.path.endswith('OrderedSwitches.ts'))
        assert len(first.sources) == 2  # module and its real entry wiring, not every project file
        assert not first.unbuilt_changes
        service.continue_project_demo(task.id, ContinueProjectDemoRequest(request_id='source-change',goal='把开关顺序改为右、左'))
        await settle(service)
        second = content_index(service, task.id)
        changed = next(item for item in second.sources if item.id == module.id)
        assert changed.source_version > module.source_version
        assert changed.content != module.content
        target = DemoEditTarget(project_id=project.project_id,workspace_id=second.workspace_id,
            kind='source',id=changed.id,source_version=changed.source_version,expected_source_content=changed.content)
        resolve_target(service,service.get(task.id),target)
        path = Path(project.root_path)/changed.path
        path.write_text(changed.content+'\n// user edit outside Agent\n')
        assert content_index(service,task.id).unbuilt_changes
        with pytest.raises(HarnessError,match='源码已改变'):
            resolve_target(service,service.get(task.id),target)
        scratch = Path(project.root_path)/'src/external.ts'
        scratch.write_text('export const external = true\n')
        assert content_index(service,task.id).unbuilt_changes
    finally:
        await service.close()
