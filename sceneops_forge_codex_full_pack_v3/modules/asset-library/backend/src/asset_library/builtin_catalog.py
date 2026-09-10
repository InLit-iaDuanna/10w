"""Read-only original assets shipped with the workbench; adoption is injected."""
from copy import deepcopy
from functools import cached_property
import json
import mimetypes
from pathlib import Path
from threading import Lock
from typing import Callable, Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .atlas_pack import ShippedBuiltinPack, ShippedBuiltinRecord, load_atlas100_pack
from .project_catalog import SaveProjectAssetResult


class BuiltinAssetLod(BaseModel):
    level: int = Field(ge=0, le=2)
    triangle_count: int | None = Field(default=None, ge=0)
    distance_m: float | None = Field(default=None, ge=0)
    asset_url: str


class BuiltinPackSummary(BaseModel):
    pack_id: str = Field(pattern=r'^[a-zA-Z0-9_-]+$')
    version: str
    title: str
    description: str
    license: str
    entry_count: int = Field(ge=1)
    catalog_url: str | None = None
    resource_base_url: str | None = None


class BuiltinAsset(BaseModel):
    asset_id: str = Field(pattern=r'^[a-zA-Z0-9_-]+$')
    label: str
    kind: Literal['prop', 'character', 'scene']
    pack_id: str = Field(pattern=r'^[a-zA-Z0-9_-]+$')
    pack_title: str
    pack_version: str
    license: str
    category: str = ''
    asset_category: str = ''
    art_style: str = '低多边形'
    game_genres: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    reusable_asset_ids: list[str] = Field(default_factory=list)
    generation_prompt: str = ''
    style_prompts: dict[str, str] = Field(default_factory=dict)
    sprite_url: str | None = None
    sprite_layout: dict = Field(default_factory=dict)
    rig: dict = Field(default_factory=dict)
    rig_source_url: str | None = None
    shared_motion_url: str | None = None
    rig_template_url: str | None = None
    animations: list[dict] = Field(default_factory=list)
    description: str = ''
    dimensions_m: list[float]
    footprint_m: list[float]
    spawn_points: list[dict] = Field(default_factory=list)
    lighting: dict = Field(default_factory=dict)
    triangle_count: int | None = None
    lods: list[BuiltinAssetLod] = Field(default_factory=list)
    physics_url: str | None = None
    scene_url: str | None = None
    uv_sets: list[str] = Field(default_factory=list)
    material_channels: list[str] = Field(default_factory=list)
    embedded_texture_resolution: list[int] | None = None
    source_texture_resolution: list[int] | None = None
    preview_source: Literal['asset', 'scene'] = 'asset'
    preview_note: str = ''
    runtime: dict = Field(default_factory=dict)
    provenance: dict = Field(default_factory=dict)
    asset_url: str
    preview_url: str
    mode: Literal['cached'] = 'cached'


class BuiltinCatalog(BaseModel):
    pack_id: str = Field(pattern=r'^[a-zA-Z0-9_-]+$')
    version: int = Field(ge=1)
    title: str
    description: str
    license: str
    packs: list[BuiltinPackSummary]
    entries: list[BuiltinAsset]


class AdoptBuiltinAsset(BaseModel):
    project_id: str = Field(min_length=1)
    card_id: str | None = None


class BuiltinAssetCatalog:
    def __init__(self, root: Path | None = None):
        self.root = root or Path(__file__).parent / 'builtin_assets'
        self.adoption_lock = Lock()

    def _primary_pack(self) -> ShippedBuiltinPack:
        document = json.loads((self.root / 'catalog.json').read_text(encoding='utf-8'))
        records = []
        file_fields = {
            'glb': 'glb_path', 'preview': 'preview_path', 'sprite': 'sprite_path',
            'blend': 'blend_path', 'motion': 'motion_path',
            'rig_template': 'rig_template_path',
        }
        for source_entry in document['entries']:
            entry = deepcopy(source_entry)
            entry.update({
                'pack_id': document['pack_id'],
                'pack_title': document['label'],
                'pack_version': str(document['version']),
                'license': document['license'],
                'asset_category': entry.get('category', ''),
                'tags': list(dict.fromkeys([
                    entry.get('category', ''), entry.get('art_style', ''),
                    *entry.get('game_genres', []),
                ])),
                'lods': [{
                    'level': 0,
                    'triangle_count': entry.get('triangle_count'),
                    'distance_m': 0,
                }],
                'uv_sets': [],
                'material_channels': [],
                'preview_source': 'asset',
                'preview_note': '',
                'runtime': {},
                'provenance': entry.get('source', {}),
            })
            files = {
                kind: self.root / entry[field]
                for kind, field in file_fields.items() if entry.get(field)
            }
            files['lod0'] = files['glb']
            records.append(ShippedBuiltinRecord(entry=entry, files=files))
        return ShippedBuiltinPack(root=self.root, summary={
            'pack_id': document['pack_id'],
            'version': str(document['version']),
            'title': document['label'],
            'description': document['description'],
            'license': document['license'],
            'entry_count': len(records),
        }, records=tuple(records))

    @cached_property
    def _packs(self) -> tuple[ShippedBuiltinPack, ...]:
        packs = [self._primary_pack()]
        atlas = load_atlas100_pack(self.root / 'packs' / 'atlas100-v2')
        if atlas is not None:
            packs.append(atlas)
        return tuple(packs)

    @cached_property
    def _records(self) -> dict[str, ShippedBuiltinRecord]:
        records = {}
        for pack in self._packs:
            for record in pack.records:
                asset_id = record.entry['asset_id']
                if asset_id in records:
                    raise RuntimeError(f'内置资产 ID 重复：{asset_id}')
                records[asset_id] = record
        return records

    @cached_property
    def _pack_roots(self) -> dict[str, Path]:
        return {pack.summary['pack_id']: pack.root for pack in self._packs}

    def document(self):
        licenses = list(dict.fromkeys(pack.summary['license'] for pack in self._packs))
        return {
            'pack_id': 'sceneops-builtin-catalog',
            'version': 5 + len(self._packs) - 1,
            'label': 'SceneOps 内置资产库',
            'description': '工作台随包安装的原创场景、角色、装备、建筑与物件。',
            'license': ' / '.join(licenses),
            'packs': [deepcopy(pack.summary) for pack in self._packs],
            'entries': [deepcopy(record.entry) for record in self._records.values()],
        }

    def entry(self, asset_id: str):
        record = self._records.get(asset_id)
        if record is None:
            raise HTTPException(404, '内置资产不存在。')
        return deepcopy(record.entry)

    def file(self, asset_id: str, kind: str) -> Path:
        record = self._records.get(asset_id)
        if record is None:
            raise HTTPException(404, '内置资产不存在。')
        target = record.files.get(kind)
        if target is None:
            raise HTTPException(404, '此资产没有该资源。')
        if (target.is_symlink() or not target.is_file()
                or not target.resolve().is_relative_to(self.root.resolve())):
            raise HTTPException(500, '内置资产文件不完整，请检查应用安装。')
        return target

    def pack_file(self, pack_id: str, resource_path: str) -> Path:
        root = self._pack_roots.get(pack_id)
        if root is None:
            raise HTTPException(404, '内置资产包不存在。')
        relative = Path(resource_path)
        allowed_directories = {
            'assets', 'scenes', 'lods', 'physics', 'previews', 'textures',
            'runtime', 'schemas', 'glb', 'revisions',
        }
        allowed_files = {
            'catalog.json', 'recipes.json', 'provenance.json', 'LICENSE.txt',
            'STYLE_OVERVIEW.png',
        }
        if (relative.is_absolute() or '..' in relative.parts or not relative.parts
                or (len(relative.parts) == 1 and relative.name not in allowed_files)
                or (len(relative.parts) > 1 and relative.parts[0] not in allowed_directories)):
            raise HTTPException(404, '内置资产包资源不存在。')
        target = root / relative
        if (target.is_symlink() or not target.is_file()
                or not target.resolve().is_relative_to(root.resolve())):
            raise HTTPException(404, '内置资产包资源不存在。')
        return target

    def public_catalog(self):
        document = self.document()
        entries = []
        excluded_urls = {
            'asset_url', 'preview_url', 'sprite_url', 'rig_source_url',
            'shared_motion_url', 'rig_template_url', 'physics_url', 'scene_url', 'mode',
        }
        for entry in document['entries']:
            asset_id = entry['asset_id']
            record = self._records[asset_id]
            values = {key: value for key, value in entry.items()
                      if key in BuiltinAsset.model_fields and key not in excluded_urls}
            values['lods'] = [BuiltinAssetLod(
                **lod, asset_url=f'/api/builtin-assets/{asset_id}/lod/{lod["level"]}')
                for lod in entry.get('lods', [])]
            entries.append(BuiltinAsset(
                **values,
                shared_motion_url=f'/api/builtin-assets/{asset_id}/motions'
                if 'motion' in record.files else None,
                rig_template_url=f'/api/builtin-assets/{asset_id}/rig-template'
                if 'rig_template' in record.files else None,
                rig_source_url=f'/api/builtin-assets/{asset_id}/blend'
                if 'blend' in record.files else None,
                sprite_url=f'/api/builtin-assets/{asset_id}/sprite'
                if 'sprite' in record.files else None,
                physics_url=f'/api/builtin-assets/{asset_id}/physics'
                if 'physics' in record.files else None,
                scene_url=f'/api/builtin-assets/{asset_id}/scene'
                if 'scene' in record.files else None,
                asset_url=f'/api/builtin-assets/{asset_id}/glb',
                preview_url=f'/api/builtin-assets/{asset_id}/preview',
            ))
        packs = [{**pack,
                  'catalog_url': f"/api/builtin-assets/packs/{pack['pack_id']}/resources/catalog.json",
                  'resource_base_url': f"/api/builtin-assets/packs/{pack['pack_id']}/resources"}
                 for pack in document['packs']]
        return BuiltinCatalog(pack_id=document['pack_id'], version=document['version'],
            title=document['label'], description=document['description'],
            license=document['license'], packs=packs, entries=entries)


def create_builtin_asset_router(catalog: BuiltinAssetCatalog,
                                adopt: Callable | None = None):
    router = APIRouter(prefix='/api/builtin-assets', tags=['builtin-assets'])

    @router.get('', response_model=BuiltinCatalog, operation_id='listBuiltinAssets')
    def list_assets():
        return catalog.public_catalog()

    @router.get('/packs/{pack_id}/resources/{resource_path:path}',
                operation_id='readBuiltinPackResource')
    def pack_resource(pack_id: str, resource_path: str):
        path = catalog.pack_file(pack_id, resource_path)
        media_type = {
            '.glb': 'model/gltf-binary',
            '.mjs': 'text/javascript',
        }.get(path.suffix, mimetypes.guess_type(path.name)[0])
        return FileResponse(path, media_type=media_type)

    @router.get('/{asset_id}/glb', operation_id='readBuiltinAssetGlb')
    def model(asset_id: str):
        return FileResponse(catalog.file(asset_id, 'glb'), media_type='model/gltf-binary')

    @router.get('/{asset_id}/preview', operation_id='readBuiltinAssetPreview')
    def preview(asset_id: str):
        return FileResponse(catalog.file(asset_id, 'preview'), media_type='image/png')

    @router.get('/{asset_id}/lod/{level}', operation_id='readBuiltinAssetLod')
    def lod(asset_id: str, level: int):
        return FileResponse(catalog.file(asset_id, f'lod{level}'),
                            media_type='model/gltf-binary')

    @router.get('/{asset_id}/physics', operation_id='readBuiltinAssetPhysics')
    def physics(asset_id: str):
        return FileResponse(catalog.file(asset_id, 'physics'), media_type='application/json')

    @router.get('/{asset_id}/scene', operation_id='readBuiltinSceneDefinition')
    def scene(asset_id: str):
        return FileResponse(catalog.file(asset_id, 'scene'), media_type='application/json')

    @router.get('/{asset_id}/sprite', operation_id='readBuiltinAssetSprite')
    def sprite(asset_id: str):
        return FileResponse(catalog.file(asset_id, 'sprite'), media_type='image/png')

    @router.get('/{asset_id}/blend', operation_id='readBuiltinAssetRigSource')
    def rig_source(asset_id: str):
        return FileResponse(catalog.file(asset_id, 'blend'), media_type='application/octet-stream',
                            filename=f'{asset_id}.blend')

    @router.get('/{asset_id}/motions', operation_id='readBuiltinSharedMotions')
    def shared_motions(asset_id: str):
        return FileResponse(catalog.file(asset_id, 'motion'), media_type='model/gltf-binary', filename='shared-motions-v1.glb')

    @router.get('/{asset_id}/rig-template', operation_id='readBuiltinSharedRig')
    def shared_rig(asset_id: str):
        return FileResponse(catalog.file(asset_id, 'rig_template'), media_type='application/octet-stream', filename='shared-humanoid-v1.blend')

    @router.post('/{asset_id}/adopt', response_model=SaveProjectAssetResult,
                 operation_id='adoptBuiltinAsset')
    def adopt_asset(asset_id: str, body: AdoptBuiltinAsset):
        entry = catalog.entry(asset_id)
        if adopt is None:
            raise HTTPException(503, '当前宿主尚未连接项目资产导入。')
        with catalog.adoption_lock:
            return adopt(entry, catalog.file(asset_id, 'glb'), body)

    return router
