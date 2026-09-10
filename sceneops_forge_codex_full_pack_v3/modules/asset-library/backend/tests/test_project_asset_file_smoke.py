import tempfile
import unittest
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient
from asset_library import ProjectAssetCatalogService,SqliteProjectAssetRepository,ProjectAssetRegistration,ProjectAssetVersion,create_project_catalog_router

class AssetFileSmoke(unittest.TestCase):
    def test_native_versions_and_project_scope_and_legacy_route(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); glb=root/'actual.glb'; glb.write_bytes(b'glTF-fixture')
            service=ProjectAssetCatalogService(SqliteProjectAssetRepository(root/'state.db'))
            request=ProjectAssetRegistration(project_id='project',workspace_id='workspace',source_asset_id='native',title='Model',source_type='import',version=ProjectAssetVersion(source_version=1,asset_version_id='version',source_kind='glb',runtime_artifacts=[dict(artifact_id='artifact',artifact_type='render',project_relative_path='public/actual.glb')],preview_path=str(glb),dimensions_m=(1,1,1),vertex_count=3,triangle_count=1,operation='import'))
            entry=service.register_version(request).entry
            app=FastAPI();app.include_router(create_project_catalog_router(service));client=TestClient(app)
            url=f'/api/project-assets/{entry.id}/versions/1/files/preview'
            self.assertEqual(client.get(url,params={'project_id':'project'}).content,b'glTF-fixture')
            self.assertEqual(client.get(url,params={'project_id':'another'}).status_code,404)
            self.assertEqual(client.get(url.replace('/1/','/9/'),params={'project_id':'project'}).status_code,404)
            glb.unlink();self.assertEqual(client.get(url,params={'project_id':'project'}).status_code,404)
            legacy=service.register_version(ProjectAssetRegistration(project_id='project',card_id='card',source_asset_id='legacy',title='Old',source_type='generated',version=ProjectAssetVersion(source_version=1,preview_path='a.glb',blend_path='a.blend',fbx_path='a.fbx',dimensions_m=(1,1,1),vertex_count=3,triangle_count=1,operation='generate'))).entry
            response=client.get(f'/api/project-assets/{legacy.id}/versions/1/files/preview?project_id=project',follow_redirects=False)
            self.assertEqual(response.status_code,307)
            self.assertEqual(response.headers['location'],'/api/card-assets/legacy/files/preview?version=1')
