"""Explicit adoption and authorized game copies of shipped original GLB assets."""
from collections.abc import Iterable, Mapping
import json
import os
import re
from pathlib import Path

from asset_library import SaveProjectAssetResult
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .card_asset_models import CardAssetError


class BuiltinAssetSelection(BaseModel):
    """A preparation recommendation that identifies one shipped catalog asset."""

    model_config = ConfigDict(extra='forbid', frozen=True)

    asset_id: str = Field(pattern=r'^[a-zA-Z0-9_-]+$')
    purpose: str | None = Field(default=None, max_length=240)
    reason: str | None = Field(default=None, max_length=1200)


class BuiltinProjectAssets:
    def __init__(self, catalog, card_assets, project_assets, workspace, resolve_card):
        self.catalog, self.card_assets = catalog, card_assets
        self.project_assets, self.workspace = project_assets, workspace
        self.resolve_card = resolve_card

    def adopt(self, entry, source, request):
        document = self.catalog.public_catalog()
        pack_id = entry.get('pack_id', document.pack_id)
        pack_version = entry.get('pack_version', str(document.version))
        source_id = f"builtin:{pack_id}:{pack_version}:{entry['asset_id']}"
        self.workspace.get_project(request.project_id)
        existing = next((asset for asset in self.project_assets.list(request.project_id)
                         if asset.modeling_session_id == source_id), None)
        if existing:
            return SaveProjectAssetResult(entry=existing, version_created=False)
        card = self.resolve_card(request.project_id, request.card_id)
        self.workspace.open_card_worktree(request.project_id, card.id, card.title,
                                         card.model_dump(mode='json'))
        record = self.card_assets.import_asset(request.project_id, card.id, source,
                                              entry['label'] + '.glb', session_id=source_id)
        return self.card_assets.save_to_library(record.id, record.current_version)

    def install_pack(self, project_id, card_id):
        document = self.catalog.public_catalog()
        with self.card_assets._lock(project_id, card_id):
            _, root = self.card_assets._binding(project_id, card_id)
            return self._install_selected_at_root(
                root, [entry.asset_id for entry in document.entries])

    @staticmethod
    def _selection_list(selections) -> list[BuiltinAssetSelection]:
        if isinstance(selections, (str, bytes)) or not isinstance(selections, Iterable):
            raise CardAssetError('BUILTIN_ASSET_SELECTION_INVALID',
                                 '内置资产选择必须是资产列表。', status_code=422)
        normalized = []
        try:
            for value in selections:
                if isinstance(value, str):
                    selection = BuiltinAssetSelection(asset_id=value)
                elif isinstance(value, Mapping):
                    selection = BuiltinAssetSelection.model_validate(value)
                elif isinstance(value, BuiltinAssetSelection):
                    selection = value
                else:
                    raise ValueError('unsupported selection')
                if all(existing.asset_id != selection.asset_id for existing in normalized):
                    normalized.append(selection)
        except (TypeError, ValueError, ValidationError) as error:
            raise CardAssetError('BUILTIN_ASSET_SELECTION_INVALID',
                                 '内置资产选择格式无效。', status_code=422) from error
        return normalized

    @staticmethod
    def _relative_url(relative: Path) -> str:
        return '/' + relative.relative_to('public').as_posix()

    def _copy_selected_resource(self, asset_id, kind, destination, root,
                                installed, preserved, *, source=None):
        relative = destination.relative_to(root).as_posix()
        try:
            self.card_assets._copy_exclusive(
                source if source is not None else self.catalog.file(asset_id, kind), destination)
            installed.append(relative)
            return 'copied'
        except FileExistsError:
            if destination.is_symlink() or not destination.is_file():
                raise CardAssetError('BUILTIN_ASSET_PATH_UNSAFE',
                                     '内置资产目标必须为普通文件。', status_code=409)
            if relative not in preserved:
                preserved.append(relative)
            return 'preserved'

    def _install_selected_resources(self, entry, relative, directory, root,
                                    installed, preserved, resource_states):
        resources = [('glb', f'{entry.asset_id}.glb')]
        if entry.sprite_url:
            resources.append(('sprite', f'{entry.asset_id}-sprites.png'))
        if entry.shared_motion_url:
            resources.append(('motion', 'shared-motions-v1.glb'))
        for lod in entry.lods:
            if lod.level > 0:
                resources.append((f'lod{lod.level}',
                                  f'{entry.asset_id}.lod{lod.level}.glb'))
        if entry.physics_url:
            resources.append(('physics', f'{entry.asset_id}.physics.json'))
        if entry.scene_url:
            resources.append(('scene', f'{entry.asset_id}.scene.json'))
        states = []
        for kind, filename in resources:
            resource_key = (relative.as_posix(), filename)
            if resource_key not in resource_states:
                resource_states[resource_key] = self._copy_selected_resource(
                    entry.asset_id, kind, directory / filename, root, installed, preserved)
            states.append({'kind': kind, 'path': (relative / filename).as_posix(),
                           'copy_state': resource_states[resource_key]})
        return states

    def _selected_runtime_entry(self, entry, selection, relative):
        excluded_urls = {'asset_url', 'preview_url', 'sprite_url', 'rig_source_url',
                         'shared_motion_url', 'rig_template_url', 'physics_url',
                         'scene_url', 'lods'}
        dumped = entry.model_dump(exclude=excluded_urls)
        lods = [{**lod.model_dump(exclude={'asset_url'}),
                 'url': self._relative_url(relative / (
                     f'{entry.asset_id}.glb' if lod.level == 0
                     else f'{entry.asset_id}.lod{lod.level}.glb'))}
                for lod in entry.lods]
        dumped.update({
            'source_asset_id': entry.asset_id,
            'source_pack_id': entry.pack_id,
            'source_pack_version': entry.pack_version,
            'project_asset_id': None,
            'recommendation_state': 'recommended',
            'provision_state': 'provided',
            'purpose': selection.purpose,
            'reason': selection.reason,
            'url': self._relative_url(relative / f'{entry.asset_id}.glb'),
            'shared_motion_url': self._relative_url(relative / 'shared-motions-v1.glb')
            if entry.shared_motion_url else None,
            'sprite_url': self._relative_url(relative / f'{entry.asset_id}-sprites.png')
            if entry.sprite_url else None,
            'lods': lods,
            'physics_url': self._relative_url(relative / f'{entry.asset_id}.physics.json')
            if entry.physics_url else None,
            'scene_url': self._relative_url(relative / f'{entry.asset_id}.scene.json')
            if entry.scene_url else None,
        })
        return dumped

    @staticmethod
    def _selected_materialization(entry, states):
        return {
            'source_asset_id': entry.asset_id,
            'source_pack_id': entry.pack_id,
            'source_pack_version': entry.pack_version,
            'project_asset_id': None,
            'recommendation_state': 'recommended',
            'provision_state': 'provided',
            'copy_state': ('copied' if any(item['copy_state'] == 'copied' for item in states)
                           else 'preserved'),
            'resources': states,
        }

    @staticmethod
    def _write_selected_catalog(directory, root, runtime, installed, preserved):
        serialized = json.dumps(runtime, ensure_ascii=False, indent=2)
        ordinal = 1
        while True:
            name = 'catalog.selected.json' if ordinal == 1 else f'catalog.selected.{ordinal}.json'
            manifest = directory / name
            relative = manifest.relative_to(root).as_posix()
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            if hasattr(os, 'O_NOFOLLOW'):
                flags |= os.O_NOFOLLOW
            try:
                descriptor = os.open(manifest, flags, 0o600)
                with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
                    stream.write(serialized)
                installed.append(relative)
                return manifest
            except FileExistsError:
                if manifest.is_symlink() or not manifest.is_file():
                    raise CardAssetError('BUILTIN_ASSET_PATH_UNSAFE',
                                         '内置资产目录索引必须为普通文件。', status_code=409)
                try:
                    matches = json.loads(manifest.read_text(encoding='utf-8')) == runtime
                except (OSError, UnicodeError, json.JSONDecodeError):
                    matches = False
                if relative not in preserved:
                    preserved.append(relative)
                if matches:
                    return manifest
                ordinal += 1

    def install_selected(self, project_id, card_id, selections):
        """Install only recommended catalog assets into an authorized card worktree."""
        with self.card_assets._lock(project_id, card_id):
            _, root = self.card_assets._binding(project_id, card_id)
            return self._install_selected_at_root(root, selections)

    def install_selected_in_project(self, project_id, selections):
        """Install a selection into the registered project Demo workspace."""
        workspace = self.workspace.open_project_demo_workspace(project_id)
        root = Path(workspace['workspace_root']).resolve(strict=True)
        with self.card_assets._lock(project_id, '__project_demo__'):
            return self._install_selected_at_root(root, selections)

    def install_selected_project_assets(self, project_id, selections, target_card_id=None):
        """Copy selected registered GLB versions into an authorized game workspace."""
        if isinstance(selections, (str, bytes)) or not isinstance(selections, Iterable):
            raise CardAssetError('PROJECT_ASSET_SELECTION_INVALID',
                                 '项目资产选择必须是资产列表。', status_code=422)
        workspace = None
        if target_card_id is not None:
            _, root = self.card_assets._binding(project_id, target_card_id)
        else:
            workspace = self.workspace.open_project_demo_workspace(project_id)
            root = Path(workspace['workspace_root']).resolve(strict=True)
        relative_root = Path('public/sceneops-project-assets')
        installed, preserved, entries, materialization = [], [], [], []
        seen = set()
        lock_key = target_card_id or '__project_demo_assets__'
        with self.card_assets._lock(project_id, lock_key):
            for raw in selections:
                if not isinstance(raw, Mapping):
                    raise CardAssetError('PROJECT_ASSET_SELECTION_INVALID',
                                         '项目资产选择格式无效。', status_code=422)
                asset_id = raw.get('project_asset_id')
                version_text = raw.get('version')
                if (not isinstance(asset_id, str)
                        or re.fullmatch(r'[A-Za-z0-9_-]+', asset_id) is None):
                    raise CardAssetError('PROJECT_ASSET_SELECTION_INVALID',
                                         '项目资产 ID 无效。', status_code=422)
                try:
                    version_number = int(version_text)
                    entry = self.project_assets.get(project_id, asset_id)
                except (TypeError, ValueError, LookupError) as error:
                    raise CardAssetError('PROJECT_ASSET_NOT_FOUND',
                                         '所选项目资产或版本不存在。', status_code=404) from error
                identity = (asset_id, version_number)
                if identity in seen:
                    continue
                seen.add(identity)
                version = next((item for item in entry.versions
                                if item.source_version == version_number), None)
                if version is None or not version.preview_path:
                    raise CardAssetError('PROJECT_ASSET_RUNTIME_UNAVAILABLE',
                                         '所选项目资产没有可复制的 GLB 运行版本。', status_code=409)
                if entry.card_id:
                    _, source_root = self.card_assets._binding(project_id, entry.card_id)
                else:
                    workspace = workspace or self.workspace.open_project_demo_workspace(project_id)
                    if entry.workspace_id != workspace['workspace_id']:
                        raise CardAssetError('PROJECT_ASSET_SCOPE_INVALID',
                                             '所选项目资产不属于当前项目工作区。', status_code=409)
                    source_root = Path(workspace['workspace_root']).resolve(strict=True)
                source = source_root / version.preview_path
                try:
                    source_metadata = source.lstat()
                    resolved_source = source.resolve(strict=True)
                except OSError as error:
                    raise CardAssetError('PROJECT_ASSET_RUNTIME_UNAVAILABLE',
                                         '项目资产运行文件不可读取。', status_code=409) from error
                if (source.is_symlink() or not source.is_file() or source_metadata.st_nlink < 1
                        or not resolved_source.is_relative_to(source_root)):
                    raise CardAssetError('PROJECT_ASSET_PATH_UNSAFE',
                                         '项目资产运行文件路径无效。', status_code=409)
                relative = relative_root / asset_id / f'v{version_number}'
                directory = self.card_assets._safe_directory(root, relative)
                target = directory / 'model.glb'
                copy_state = self._copy_selected_resource(
                    asset_id, 'project-glb', target, root, installed, preserved,
                    source=resolved_source)
                url = self._relative_url(relative / 'model.glb')
                entries.append({'project_asset_id': entry.id, 'source_asset_id': entry.source_asset_id,
                    'asset_version': version_number, 'asset_version_id': version.asset_version_id,
                    'title': entry.title, 'dimensions_m': version.dimensions_m,
                    'model_rotation_quaternion_xyzw': version.model_rotation_quaternion_xyzw,
                    'node_ids': version.node_ids, 'purpose': raw.get('purpose'),
                    'reason': raw.get('reason'), 'url': url})
                materialization.append({'candidate_id': f'project:{entry.id}',
                    'project_asset_id': entry.id, 'asset_version': version_number,
                    'recommendation_state': 'recommended', 'provision_state': 'provided',
                    'copy_state': copy_state,
                    'resources': [{'kind': 'glb', 'path': target.relative_to(root).as_posix(),
                                   'copy_state': copy_state}]})
        return {'installed_files': installed, 'preserved_files': preserved,
                'catalog_path': None, 'catalog': {'kind': 'selected-project-assets',
                                                  'entries': entries},
                'materialization': materialization,
                'usage': '只从 entries 的真实 URL 加载所选项目资产版本。'}

    def _install_selected_at_root(self, root, selections):
        selected = self._selection_list(selections)
        document = self.catalog.public_catalog()
        entries_by_id = {entry.asset_id: entry for entry in document.entries}
        unknown = [item.asset_id for item in selected if item.asset_id not in entries_by_id]
        if unknown:
            raise CardAssetError('BUILTIN_ASSET_NOT_FOUND',
                                 '内置资产不存在：' + '、'.join(unknown), status_code=404)

        catalog_directory = self.card_assets._safe_directory(root, Path('public/sceneops-assets'))
        installed, preserved = [], []
        resource_states = {}
        runtime_entries, materialization = [], []

        for selection in selected:
            entry = entries_by_id[selection.asset_id]
            relative = (Path('public/sceneops-assets') / entry.pack_id
                        / f'v{entry.pack_version}')
            directory = self.card_assets._safe_directory(root, relative)
            states = self._install_selected_resources(
                entry, relative, directory, root, installed, preserved, resource_states)
            runtime_entries.append(
                self._selected_runtime_entry(entry, selection, relative))
            materialization.append(
                self._selected_materialization(entry, states))

        runtime = {
            'pack_id': 'sceneops-selected-assets',
            'version': 1,
            'license': document.license,
            'packs': [pack.model_dump(mode='json',
                                      exclude={'catalog_url', 'resource_base_url'})
                      for pack in document.packs
                      if any(entry.pack_id == pack.pack_id for entry in
                             (entries_by_id[item.asset_id] for item in selected))],
            'entries': runtime_entries,
        }
        manifest = self._write_selected_catalog(
            catalog_directory, root, runtime, installed, preserved)
        return {
            'installed_files': installed,
            'preserved_files': preserved,
            'catalog_path': manifest.relative_to(root).as_posix(),
            'catalog': runtime,
            'materialization': materialization,
            'usage': ('读取 catalog_path，只加载 entries 中提供的所选资产。LOD、物理绑定'
                      '和场景定义使用条目内 URL；materialization 区分推荐、提供、复制和保留状态。'),
        }
