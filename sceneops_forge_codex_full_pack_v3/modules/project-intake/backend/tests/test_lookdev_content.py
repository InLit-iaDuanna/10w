import tempfile
import unittest
from pathlib import Path
from sceneops_project_workspace.lookdev_content import write_lookdev_content
from sceneops_project_workspace.demo_content import demo_content_source

class LookdevContentTests(unittest.TestCase):
    def test_materializes_catalog_binary_and_runtime_without_private_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);(root/'src/game').mkdir(parents=True)
            source=root/'source.glb';source.write_bytes(b'catalog-binary')
            manifest={'assets':[{'asset_id':'a','asset_version':2}], 'lookdev':[{
                'asset_id':'a','asset_version':2,'document_id':'d','scene_instance_id':'i',
                'source_path':str(source),'runtime_module':'export const material = 1',
                'state':{'materials':[{'shaderGraph':{'version':1}}]}}]}
            write_lookdev_content(root,manifest,lambda path,text:path.write_text(text))
            asset=manifest['assets'][0]
            self.assertEqual((root/asset['runtime_artifacts'][0]['project_relative_path']).read_bytes(),b'catalog-binary')
            self.assertNotIn('source_path',manifest['lookdev'][0])
            self.assertNotIn('state',manifest['lookdev'][0])
            registry=(root/'src/game/sceneops-lookdev/index.ts').read_text()
            self.assertIn('requiresGpu:true',registry)
            self.assertIn('popErrorScope',registry)
            self.assertIn('item.version===version',registry)
            self.assertIn('applyProjectLookdev(gltf,asset.asset_id',demo_content_source(manifest))

    def test_plain_projects_keep_original_runtime(self):
        source=demo_content_source({'assets':[],'objects':[]})
        self.assertNotIn('applyProjectLookdev',source)
