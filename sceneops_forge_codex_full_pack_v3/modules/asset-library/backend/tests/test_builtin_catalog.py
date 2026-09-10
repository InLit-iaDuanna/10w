import unittest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from asset_library import BuiltinAssetCatalog, create_builtin_asset_router


class BuiltinCatalogTests(unittest.TestCase):
    def test_shipped_catalog_and_every_preview_are_real_files(self):
        catalog = BuiltinAssetCatalog()
        public = catalog.public_catalog()
        self.assertEqual(len(public.entries), 877)
        self.assertEqual(sum(item.kind == 'scene' for item in public.entries), 136)
        self.assertEqual(sum(item.kind == 'character' for item in public.entries), 14)
        self.assertEqual(len({item.asset_id for item in public.entries}), 877)
        self.assertEqual([(pack.pack_id, pack.entry_count) for pack in public.packs],
                         [('sceneops-haven-kit', 102), ('atlas100', 775)])
        for item in public.entries:
            with self.subTest(asset=item.asset_id):
                self.assertEqual(catalog.file(item.asset_id, 'glb').read_bytes()[:4], b'glTF')
                self.assertEqual(catalog.file(item.asset_id, 'preview').read_bytes()[:8], b'\x89PNG\r\n\x1a\n')
                self.assertTrue(all(value > 0 for value in item.dimensions_m))

    def test_atlas_pack_preserves_lod_physics_scene_and_preview_truth(self):
        catalog = BuiltinAssetCatalog()
        public = catalog.public_catalog()
        fallback = next(item for item in public.entries
                        if item.asset_id == 'atlas100-s001-a01')
        self.assertEqual(fallback.pack_version, '2.0.0')
        self.assertEqual(fallback.preview_source, 'scene')
        self.assertEqual(catalog.file(fallback.asset_id, 'preview').name,
                         'atlas100-s001.png')
        self.assertEqual([lod.level for lod in fallback.lods], [0, 1, 2])
        self.assertEqual(catalog.file(fallback.asset_id, 'lod2').read_bytes()[:4], b'glTF')
        self.assertEqual(catalog.file(fallback.asset_id, 'physics').suffix, '.json')
        self.assertEqual(fallback.uv_sets, ['TEXCOORD_0', 'TEXCOORD_1'])
        self.assertEqual(len(fallback.material_channels), 8)

        scene = next(item for item in public.entries if item.asset_id == 'atlas100-s001')
        self.assertEqual(scene.kind, 'scene')
        self.assertIsNotNone(scene.scene_url)
        self.assertEqual(catalog.file(scene.asset_id, 'scene').name, 'atlas100-s001.json')

        app = FastAPI()
        app.include_router(create_builtin_asset_router(catalog))
        client = TestClient(app)
        self.assertEqual(client.get(fallback.lods[1].asset_url).headers['content-type'],
                         'model/gltf-binary')
        self.assertEqual(client.get(fallback.physics_url).headers['content-type'],
                         'application/json')
        self.assertEqual(client.get(scene.scene_url).headers['content-type'],
                         'application/json')

        atlas_pack = next(pack for pack in public.packs if pack.pack_id == 'atlas100')
        self.assertEqual(client.get(atlas_pack.catalog_url).status_code, 200)
        texture = f'{atlas_pack.resource_base_url}/textures/solarpunk/body/basecolor.png'
        self.assertEqual(client.get(texture).headers['content-type'], 'image/png')
        runtime = f'{atlas_pack.resource_base_url}/runtime/atlas-runtime.mjs'
        self.assertIn('javascript', client.get(runtime).headers['content-type'])
        with self.assertRaises(HTTPException):
            catalog.pack_file('atlas100', '../catalog.json')

    def test_guidance_reuse_and_pixel_resources(self):
        catalog = BuiltinAssetCatalog()
        public = catalog.public_catalog()
        ids = {entry.asset_id for entry in public.entries}
        for entry in public.entries:
            with self.subTest(asset=entry.asset_id):
                self.assertTrue(set(entry.reusable_asset_ids).issubset(ids))
                if entry.pack_id == 'sceneops-haven-kit':
                    self.assertEqual(set(entry.style_prompts), {'低多边形','体素','像素','纸艺','写实','手绘','黏土','搪瓷'})
                    self.assertIn(entry.label, entry.generation_prompt)
                if entry.kind == 'character':
                    self.assertIsNotNone(entry.rig_source_url)
                    self.assertTrue(catalog.file(entry.asset_id, 'blend').is_file())
                    self.assertEqual(entry.rig['status'], 'skinned')
                    self.assertEqual(entry.rig['bone_count'], 16)
                    self.assertEqual(entry.rig['skeleton_id'], 'sceneops-humanoid-v1')
                    self.assertIsNotNone(entry.shared_motion_url)
                    self.assertTrue(catalog.file(entry.asset_id,'motion').is_file())
                    self.assertEqual({clip['name'] for clip in entry.animations}, {'Idle','Walk','Run','Wave'})
                    self.assertIsNotNone(entry.sprite_url)
                    payload = catalog.file(entry.asset_id, 'sprite').read_bytes()
                    self.assertEqual(payload[:8], b'\x89PNG\r\n\x1a\n')
                    import struct
                    self.assertEqual(struct.unpack('>II', payload[16:24]), (128, 192))
                    self.assertEqual(entry.sprite_layout['directions'], ['down','left','right','up'])
        app = FastAPI()
        app.include_router(create_builtin_asset_router(catalog))
        client = TestClient(app)
        character = next(entry for entry in public.entries if entry.kind == 'character')
        self.assertEqual(client.get(character.sprite_url).headers['content-type'], 'image/png')
        self.assertEqual(client.get(character.rig_source_url).headers['content-type'], 'application/octet-stream')
        prop = next(entry for entry in public.entries if entry.kind == 'prop')
        self.assertEqual(client.get(f'/api/builtin-assets/{prop.asset_id}/sprite').status_code, 404)

    def test_http_catalog_does_not_expose_filesystem_paths_or_accept_unknown_ids(self):
        app = FastAPI()
        app.include_router(create_builtin_asset_router(BuiltinAssetCatalog()))
        client = TestClient(app)
        result = client.get('/api/builtin-assets')
        self.assertEqual(result.status_code, 200)
        self.assertNotIn(str(BuiltinAssetCatalog().root), result.text)
        asset = result.json()['entries'][0]
        self.assertEqual(client.get(asset['asset_url']).headers['content-type'], 'model/gltf-binary')
        self.assertEqual(client.get('/api/builtin-assets/unknown/glb').status_code, 404)
        self.assertEqual(client.post(f"/api/builtin-assets/{asset['asset_id']}/adopt",
            json={'project_id':'fixture'}).status_code, 503)


if __name__ == '__main__':
    unittest.main()
