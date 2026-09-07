"""Native source domain boundaries, separate from real Blender/model acceptance."""
from pathlib import Path
from types import SimpleNamespace
import pytest
from asset_library import ProjectAssetVersion, ProjectAssetRegistration, ProjectAssetCatalogService, SqliteProjectAssetRepository, DoorRecipe
from sceneops_ai_agents.blender_content import candidate
from sceneops_ai_agents.blender_content_models import BlenderNodeEdit
from sceneops_harness import HarnessError
from asset_factory import preserve_native_source


def test_native_catalog_preserves_recipe_and_checks_base(tmp_path):
    service = ProjectAssetCatalogService(SqliteProjectAssetRepository(tmp_path/'assets.db'))
    request = ProjectAssetRegistration(project_id='p', workspace_id='w', source_asset_id='s',
        title='Door', source_type='generated', version=ProjectAssetVersion(source_version=1,
        asset_version_id='v1', source_kind='procedural', dimensions_m=(1.2,2.2,.15),
        vertex_count=24, triangle_count=12, operation='recipe-create', recipe=DoorRecipe()))
    original = service.register_version(request).entry
    native = ProjectAssetVersion(source_version=2, asset_version_id='v2', source_kind='blender',
        dimensions_m=(1.5,2.2,.3), vertex_count=48, triangle_count=24, blend_path='/source.blend',
        preview_path='/runtime.glb', operation='blender-edit', parent_source_version=1,
        runtime_artifacts=[dict(artifact_id='glb2',artifact_type='render',project_relative_path='public/door.glb')])
    changed = request.model_copy(update={'version':native,'expected_version':1})
    assert service.register_version(changed).version_created
    assert not service.register_version(changed).version_created
    assert service.get('p',original.id).versions[0] == original.versions[0]
    with pytest.raises(ValueError):
        service.register_version(request.model_copy(update={'expected_version':1,'version':native.model_copy(update={'source_version':3,'asset_version_id':'v3'})}))
    with pytest.raises(ValueError):
        BlenderNodeEdit(node_id='leaf',dimensions_m=(1,float('nan'),2))


def test_unknown_candidate_and_bad_export_preserve_sources(tmp_path):
    with pytest.raises(HarnessError):
        candidate(SimpleNamespace(observations={}), 'other', 'asset')
    folder=tmp_path/'blender';folder.mkdir()
    blend=folder/'source.blend';blend.write_bytes(b'BLENDERexisting')
    glb=folder/'source.glb';glb.write_bytes(b'broken')
    with pytest.raises(ValueError):
        preserve_native_source(tmp_path,'blend_'+'a'*32,blend,glb)
    assert blend.read_bytes()==b'BLENDERexisting'
    assert not (tmp_path/'public').exists()


def test_agent_cannot_stop_manual_editor_before_ownership_rejection():
    import asyncio
    from sceneops_ai_agents.blender_content import dispatch
    task=SimpleNamespace(id='t',project_id='p',grant=SimpleNamespace(workspace_id='w'),
        actions=[SimpleNamespace(run_ids=['run'],request_id='request',action=SimpleNamespace(action_id='agent-edit'))],
        observations={'blender_candidates':{'blend_'+'a'*32:{'asset_id':'asset','owner':'manual','status':'editing'}}})
    class Tools:
        task_id='t'
        service=SimpleNamespace(check_grant=lambda *a:task,
            project_assets=SimpleNamespace(get=lambda *a:SimpleNamespace(id='asset',workspace_id='w')))
        async def session(self,*args,**kwargs):
            raise AssertionError('An ownership rejection must not touch or stop the manual session')
    invocation=SimpleNamespace(run_id='run',capability_id='blender.asset.publish',inputs={
        'asset_id':'asset','candidate_id':'blend_'+'a'*32,'expected_scene_version':1})
    with pytest.raises(HarnessError,match='人工候选'):
        asyncio.run(dispatch(Tools(),invocation,None))
