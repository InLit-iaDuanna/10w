import tempfile
import unittest
from pathlib import Path
from sceneops_project_workspace import SqliteWorkspaceRepository, EntityStore

class EntitySmoke(unittest.TestCase):
    def test_reuse_adoption_conflict_and_project_isolation(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace=SqliteWorkspaceRepository(Path(directory)/'state.db')
            project=workspace.create_project('test')
            store=EntityStore(workspace)
            values=dict(title='model',source_ids=['source'],feature_id='feature',asset_id='asset',adopted_asset_version=1,required_node_ids=['body'])
            entity=store.register(project.project_id,'workspace','source',**values)
            self.assertEqual(entity,store.register(project.project_id,'workspace','source',**values))
            adopted=store.adopt(project.project_id,'workspace',entity.id,2,1,'apply')
            self.assertEqual(adopted.adopted_asset_version,2)
            self.assertEqual(adopted,store.adopt(project.project_id,'workspace',entity.id,2,1,'apply'))
            with self.assertRaises(ValueError):store.adopt(project.project_id,'workspace',entity.id,3,1,'other')
            with self.assertRaises(ValueError):store.adopt(project.project_id,'foreign',entity.id,3,2,'other')
            restored=store.adopt(project.project_id,'workspace',entity.id,1,2,'restore')
            self.assertEqual(restored.adopted_asset_version,1)
