import json
import shutil
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
from asset_library import ProjectAssetCatalogService, SqliteProjectAssetRepository
from sceneops_project_workspace import SqliteWorkspaceRepository
from sceneops_harness import HarnessError
from sceneops_ai_agents import entity_production as production
from sceneops_ai_agents.native_bridge_assets import RegisterNativeAssetInput, register_native_asset
from vfx_shader.lookdev_glb import read_glb, write_glb

class EntityProductionSmoke(unittest.TestCase):
    def test_second_model_registration_conflicts_and_missing_interfaces(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve()
            shutil.copy2(Path(__file__).parent/'fixtures/entity-simple.glb',root/'model.glb')
            initial,chunks=read_glb((root/'model.glb').read_bytes())
            initial['animations']=[{'name':'Run','channels':[],'samplers':[],'extras':{'sceneops_id':'simple_run'}}]
            (root/'model.glb').write_bytes(write_glb(initial,chunks))
            workspace=SqliteWorkspaceRepository(root/'state.db')
            project=workspace.create_project('second model').project_id
            task=NS(id='task',project_id=project,grant=NS(workspace_id='work',workspace_root=str(root)),authorization_card=NS(workspace_id='work'),observations={})
            def update(tid,fn,*args):fn(task);return task
            service=NS(workspace=workspace,project_assets=ProjectAssetCatalogService(SqliteProjectAssetRepository(root/'assets.db')),
                records=NS(manual_edit=lambda _:nullcontext(),update=update),get=lambda _:task,
                game=NS(invalidate_project_workspace=lambda *args:None,snapshot=lambda _:NS(current_playable_candidate=None)))
            body=production.OrganizeEntity(request_id='register',title='simple model',feature_id='simple',path='model.glb',source_versions={'source':1})
            with patch.object(production,'project_task',return_value=task),patch.object(production,'content_index',return_value=NS(sources=[NS(id='source',source_version=1)])):
                entity=production.organize(service,task.id,body)
                self.assertEqual(entity.id,production.organize(service,task.id,body).id)
                with patch.object(service,'check_grant',create=True,side_effect=HarnessError('TASK_SCOPE_DENIED','no claim')):
                    with self.assertRaises(HarnessError):production.organize(service,task.id,body,native=True)
                    with self.assertRaises(HarnessError):production.adopt(service,task.id,entity.id,production.AdoptEntity(request_id='denied',expected_revision=1,asset_version=1),native=True)
                self.assertEqual(entity.material_interfaces,{'simple_body':['simple_surface']})
                request=production.AdoptEntity(request_id='adopt',expected_revision=1,asset_version=1)
                saved=production.adopt(service,task.id,entity.id,request)
                self.assertEqual(saved.revision,2)
                with self.assertRaises(HarnessError):production.adopt(service,task.id,entity.id,request.model_copy(update={'request_id':'conflict'}))
                for field in ['node','material','animation']:
                    doc,chunks=read_glb((root/'model.glb').read_bytes())
                    if field=='node':doc['nodes'][0]['extras']['sceneops_id']='different'
                    elif field=='material':doc['materials'][0]['extras']['lookdevSourceMaterialId']='different'
                    else:doc['animations'][0]['extras']['sceneops_id']='different'
                    (root/'changed.glb').write_bytes(write_glb(doc,chunks))
                    current=service.project_assets.get(project,entity.asset_id)
                    result=register_native_asset(service,task,RegisterNativeAssetInput(path='changed.glb',title='simple model',asset_id=entity.asset_id,expected_version=current.current_version))
                    with self.assertRaises(HarnessError) as raised:
                        production.adopt(service,task.id,entity.id,production.AdoptEntity(request_id=field,expected_revision=2,asset_version=result['asset']['current_version']))
                    self.assertIn('simple',str(raised.exception))
                    self.assertEqual(production.list_entities(service,task.id)[0].adopted_asset_version,1)
                (root/'broken.glb').write_bytes(b'invalid')
                with self.assertRaises(HarnessError):production.proposal(service,task.id,body.model_copy(update={'path':'broken.glb'}))
                self.assertEqual(len(production.list_entities(service,task.id)),1)

    def test_first_import_assigns_identity_without_changing_animation_or_binary(self):
        from asset_factory import register_glb_identity_bytes
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'model.glb'
            document,chunks=read_glb((Path(__file__).parent/'fixtures/entity-simple.glb').read_bytes())
            document['nodes'][0].pop('extras')
            document['nodes'].append({'name':'bone','translation':[0,1,0]})
            document['materials'][0].pop('extras')
            document['animations']=[{'name':'Idle','channels':[],'samplers':[]}]
            path.write_bytes(write_glb(document,chunks))
            first,binary=read_glb(register_glb_identity_bytes(path))
            self.assertEqual(binary,chunks)
            self.assertEqual(first['nodes'][1]['translation'],[0,1,0])
            self.assertEqual(first['animations'][0]['channels'],[])
            self.assertTrue(first['animations'][0]['extras']['sceneops_id'])
            self.assertEqual(len({n['extras']['sceneops_id'] for n in first['nodes']}),2)
            path.write_bytes(write_glb(first,binary))
            second,second_binary=read_glb(register_glb_identity_bytes(path))
            self.assertEqual(first,second)
            self.assertEqual(binary,second_binary)
            first['nodes'][1]['extras']['sceneops_id']=first['nodes'][0]['extras']['sceneops_id']
            path.write_bytes(write_glb(first,binary))
            with self.assertRaises(ValueError):register_glb_identity_bytes(path)
