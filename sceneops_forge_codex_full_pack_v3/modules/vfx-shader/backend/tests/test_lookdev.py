"""Native material document persistence and conflict smoke tests."""
import asyncio
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from vfx_shader.lookdev_models import LookdevDocument, LookdevTarget, SaveLookdevRequest, LookdevError
from vfx_shader.lookdev_service import LookdevService
from vfx_shader.lookdev_glb import normalize_glb, read_glb, write_glb


class LookdevTests(unittest.IsolatedAsyncioTestCase):
    async def test_save_reopen_conflict_and_project_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            glb = root / 'source.glb'
            glb.write_bytes(write_glb({'asset': {'version': '2.0'}, 'nodes': [{'mesh': 0}], 'meshes': [{'primitives': []}]}, []))
            catalog = SimpleNamespace(get=lambda project, asset: SimpleNamespace(versions=[SimpleNamespace(source_version=1, preview_path=str(glb))]))
            async def validator(payload):
                return {'valid': True, 'project': payload['project'], 'code': '// generated'}
            service = LookdevService(root / 'test.sqlite3', SimpleNamespace(exists=lambda project: project == 'p'), catalog, None, validator)
            document = LookdevDocument(id='d', project_id='p', target=LookdevTarget(asset_id='a', asset_version=1), state={})
            request = SaveLookdevRequest(document=document, expected_version=0)
            saved = await service.save('p', request)
            self.assertEqual(saved.version, 1)
            self.assertEqual(service.get('p', 'd'), saved)
            self.assertEqual(len(service.list('p', 'a')), 1)
            with self.assertRaisesRegex(LookdevError, '版本已更新'):
                await service.save('p', request)
            with self.assertRaisesRegex(LookdevError, '项目不存在'):
                service.get('other', 'd')
            first = service.source('p', 'a', 1).read_bytes()
            self.assertEqual(first, service.source('p', 'a', 1).read_bytes())
            self.assertTrue(read_glb(first)[0]['nodes'][0]['extras']['sceneops_id'])

    async def test_invalid_validation_does_not_save(self):
        with tempfile.TemporaryDirectory() as directory:
            async def validator(payload):
                raise LookdevError('LOOKDEV_INVALID', 'invalid', 422)
            service = LookdevService(Path(directory) / 'test.sqlite3', SimpleNamespace(exists=lambda _: True), None, None, validator)
            service.source = lambda *_: None
            document = LookdevDocument(id='d', project_id='p', target=LookdevTarget(asset_id='a', asset_version=1), state={})
            with self.assertRaises(LookdevError):
                await service.save('p', SaveLookdevRequest(document=document, expected_version=0))
            self.assertEqual(service.list('p'), [])

    def test_normalization_rejects_duplicate_identity(self):
        data = write_glb({'asset': {'version': '2.0'}, 'nodes': [
            {'mesh': 0, 'extras': {'sceneops_id': 'duplicate'}},
            {'mesh': 0, 'extras': {'sceneops_id': 'duplicate'}}],
            'meshes': [{'primitives': [{}]}]}, [])
        with self.assertRaisesRegex(LookdevError, '重复对象身份'):
            normalize_glb(data)

    def test_normalization_preserves_existing_identity_and_binary(self):
        data = write_glb({'asset': {'version': '2.0'}, 'nodes': [{'mesh': 0, 'extras': {'sceneops_id': 'stable'}}], 'meshes': [{'primitives': [{}, {}]}]}, [(0x004E4942, b'1234')])
        document, chunks = read_glb(normalize_glb(data))
        self.assertEqual(document['nodes'][0]['extras']['sceneops_id'], 'stable')
        self.assertEqual(chunks, [(0x004E4942, b'1234')])
        ids = [item['extras']['sceneops_id'] for item in document['meshes'][0]['primitives']]
        self.assertEqual(len(set(ids)), 2)

class PbrApplicationTests(unittest.TestCase):
    def test_authoritative_pbr_preserves_geometry_and_isolates_shared_material(self):
        from vfx_shader.lookdev_glb import apply_pbr
        original = {'asset': {'version': '2.0'}, 'nodes': [
            {'mesh': 0, 'extras': {'sceneops_id': 'left'}},
            {'mesh': 0, 'extras': {'sceneops_id': 'right'}}],
            'meshes': [{'primitives': [{'material': 0, 'attributes': {'POSITION': 0}}]}],
            'materials': [{'extras': {'lookdevSourceMaterialId': 'source-shared'}, 'pbrMetallicRoughness': {'baseColorFactor': [0.2, 0.3, 0.4, 1], 'baseColorTexture': {'index': 0}}}]}
        material = dict(id='m', name='PBR', baseColor='#ff0000', opacity=1,
            metalness=0.5, roughness=0.7, emissive='#000000', alphaMode='OPAQUE',
            alphaCutoff=0.5, normalScale=1, emissiveIntensity=1, transmission=0,
            ior=1.5, clearcoat=0, clearcoatRoughness=0)
        state = {'objects': [{'id': identity, 'materialSlots': [{'slot': 0, 'materialId': mid, 'sourceMaterialId': 'source-shared'}]} for identity, mid in [('left', 'm'), ('right', 'n')]],
                 'materials': [material, {**material, 'id': 'n', 'baseColor': '#00ff00'}]}
        output, chunks = read_glb(apply_pbr(write_glb(original, [(0x004E4942, b'abcd')]), state))
        self.assertEqual(chunks, [(0x004E4942, b'abcd')])
        indices = [output['meshes'][node['mesh']]['primitives'][0]['material'] for node in output['nodes']]
        self.assertNotEqual(*indices)
        self.assertEqual([output['materials'][index]['extras']['lookdevMaterialId'] for index in indices], ['m', 'n'])
        self.assertEqual([output['materials'][index]['extras']['lookdevSourceMaterialId'] for index in indices], ['source-shared', 'source-shared'])
        self.assertEqual(output['materials'][indices[0]]['pbrMetallicRoughness']['baseColorFactor'], [1, 0, 0, 1])
        self.assertEqual(output['materials'][indices[1]]['pbrMetallicRoughness']['baseColorFactor'], [0, 1, 0, 1])
        self.assertEqual(output['materials'][indices[0]]['pbrMetallicRoughness']['baseColorTexture'], {'index': 0})
        state['objects'][0]['materialSlots'][0]['sourceMaterialId'] = 'replaced-slot'
        with self.assertRaisesRegex(LookdevError, 'left:replaced-slot'):
            apply_pbr(write_glb(original, [(0x004E4942, b'abcd')]), state)
        state['objects'] = state['objects'][1:]
        with self.assertRaisesRegex(LookdevError, 'left'):
            apply_pbr(write_glb(original, [(0x004E4942, b'abcd')]), state)

class NativeValidatorIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_validator_save_and_catalog_application(self):
        import subprocess
        from asset_library import (ProjectAssetCatalogService, SqliteProjectAssetRepository,
            ProjectAssetRegistration, ProjectAssetVersion, RuntimeArtifactReference)
        from vfx_shader import NodeLookdevValidator, LookdevAssetApplication, ApplyLookdevRequest, ExportLookdevRequest
        root = Path(__file__).resolve().parents[4]
        output = subprocess.check_output(['node', '--import', 'tsx', '--input-type=module', '-e',
            "import {createDemoProject} from './src/core/lookdev.ts';process.stdout.write(JSON.stringify(createDemoProject()));"],
            cwd=root / 'modules/vfx-shader/frontend')
        state = json.loads(output)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            source = path / 'source.glb'
            source.write_bytes(write_glb({'asset': {'version': '2.0'},
                'nodes': [{'mesh': index, 'extras': {'sceneops_id': item['id']}} for index, item in enumerate(state['objects'])],
                'meshes': [{'primitives': [{'material': index}]} for index, _ in enumerate(state['objects'])],
                'materials': [{'extras': {'lookdevSourceMaterialId': item['materialSlots'][0]['sourceMaterialId']}} for item in state['objects']]}, [(0x004E4942, b'1234')]))
            database = path / 'data.sqlite3'
            catalog = ProjectAssetCatalogService(SqliteProjectAssetRepository(database))
            entry = catalog.register_version(ProjectAssetRegistration(project_id='p', workspace_id='w',
                source_asset_id='source', title='Test', source_type='import',
                version=ProjectAssetVersion(source_version=1, asset_version_id='v1', source_kind='glb',
                    dimensions_m=(1, 1, 1), vertex_count=0, triangle_count=0,
                    preview_path=str(source), operation='import', runtime_artifacts=[RuntimeArtifactReference(
                        artifact_id='r1', artifact_type='render', project_relative_path=str(source))]))).entry
            scenes = SimpleNamespace(get=lambda _: SimpleNamespace(version=0, objects=[]))
            service = LookdevService(database, SimpleNamespace(exists=lambda _: True), catalog, None,
                NodeLookdevValidator(root), LookdevAssetApplication(path / 'outputs', catalog, scenes))
            document = LookdevDocument(id='d', project_id='p', target=LookdevTarget(asset_id=entry.id, asset_version=1), state=state)
            saved = await service.save('p', SaveLookdevRequest(document=document, expected_version=0))
            self.assertIn('applySceneopsLookdev', saved.runtime_module)
            result = service.apply('p', ApplyLookdevRequest(document_id='d', document_version=1, expected_target_version=1))
            self.assertEqual(result.asset_version, 2)
            self.assertEqual(len(service.runtime_bindings('p', 'w')), 1)
            applied = catalog.get('p', entry.id).versions[-1]
            self.assertEqual(read_glb(Path(applied.preview_path).read_bytes())[1], [(0x004E4942, b'1234')])
            import zipfile
            for format in ('pbr-glb', 'shader-zip', 'luma-zip'):
                artifact = await service.export('p', ExportLookdevRequest(document_id='d', document_version=1, format=format))
                metadata, file = service.export_file('p', artifact.id)
                self.assertEqual(file.stat().st_size, metadata.size_bytes)
                if format == 'pbr-glb':
                    self.assertEqual(read_glb(file.read_bytes())[1], [(0x004E4942, b'1234')])
                    self.assertTrue(metadata.warnings)
                else:
                    with zipfile.ZipFile(file) as archive:
                        self.assertIn('project.json', archive.namelist())
                        self.assertIn('assets/source.glb' if format == 'luma-zip' else 'sceneops-lookdev.ts', archive.namelist())
            self.assertEqual(catalog.get('p', entry.id).current_version, 2)
            with self.assertRaises(LookdevError):
                service.export_file('other-project', artifact.id)


class ProposalBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_validator_fixed_scope_invalid_operations_and_cancellation(self):
        import copy
        import subprocess
        from vfx_shader import NodeLookdevValidator, LookdevProposalRequest
        root = Path(__file__).resolve().parents[4]
        state = json.loads(subprocess.check_output(['node', '--import', 'tsx', '--input-type=module', '-e',
            "import {createDemoProject} from './src/core/lookdev.ts';process.stdout.write(JSON.stringify(createDemoProject()));"],
            cwd=root / 'modules/vfx-shader/frontend'))
        original = copy.deepcopy(state)
        material_id = state['materials'][0]['id']
        target = LookdevTarget(asset_id='asset-fixed', asset_version=3, sceneops_id=state['objects'][0]['id'])
        document = LookdevDocument(id='document-fixed', project_id='p', version=2, target=target, state=state)
        with tempfile.TemporaryDirectory() as directory:
            provider_result = {'status': 'applied', 'summary': '调整粗糙度。', 'operations': [
                {'kind': 'material.update', 'targetId': material_id, 'patch': {'roughness': 0.2}}]}
            async def structured(prompt, schema, **kwargs):
                self.assertIn('Shader', prompt)
                self.assertIn('operations', schema['properties'])
                return provider_result
            service = LookdevService(Path(directory) / 'data.sqlite3', SimpleNamespace(exists=lambda _: True),
                None, SimpleNamespace(structured=structured), NodeLookdevValidator(root))
            service.source = lambda *_: None
            request = LookdevProposalRequest(turn_id='success', document=document, prompt='调整粗糙度', material_ids=[material_id])
            result = await service.propose('p', request)
            self.assertEqual(result.target, target)
            self.assertEqual(result.base_version, 2)
            self.assertEqual(service.history('p')[0].status, 'proposed')
            self.assertEqual(result.state['materials'][0]['roughness'], 0.2)
            self.assertEqual(document.state, original)
            for turn_id, operation in [
                ('light-denied', {'kind': 'light.update', 'targetId': state['lights'][0]['id'], 'patch': {'intensity': 4}}),
                ('graph-invalid', {'kind': 'material.graph.set', 'targetId': material_id, 'graph': {'version': 1, 'nodes': []}}),
            ]:
                provider_result = {'status': 'applied', 'summary': '测试提案。', 'operations': [operation]}
                with self.assertRaises(LookdevError):
                    await service.propose('p', request.model_copy(update={'turn_id': turn_id}))
                self.assertEqual(service.history('p')[-1].status, 'failed')
                self.assertEqual(document.state, original)
            started = asyncio.Event()
            async def blocked_provider(*args, **kwargs):
                started.set()
                await asyncio.Event().wait()
            service.provider = SimpleNamespace(structured=blocked_provider)
            task = asyncio.create_task(service.propose('p', request.model_copy(update={'turn_id': 'cancelled'})))
            await asyncio.wait_for(started.wait(), 10)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
            self.assertEqual(service.history('p')[-1].status, 'cancelled')
