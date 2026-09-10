"""Publish exported material GLBs through the existing asset and scene APIs."""
import threading
from pathlib import Path
from uuid import uuid4
from asset_library import ProjectAssetRegistration, ProjectAssetVersion, RuntimeArtifactReference
from world_composer import RebindAssetVersionRequest
from .lookdev_models import LookdevApplication, LookdevError
from .lookdev_glb import read_glb, apply_pbr


class LookdevAssetApplication:
    def __init__(self, root, catalog, scenes):
        self.root, self.catalog, self.scenes = Path(root), catalog, scenes
        self.lock = threading.RLock()
        self.source = None

    def apply(self, project_id, document, request):
        with self.lock:
            entry = self.catalog.get(project_id, document.target.asset_id)
            if entry.current_version != request.expected_target_version:
                raise LookdevError('ASSET_VERSION_CONFLICT', '资产已更新，请重新读取后应用。')
            source = next((v for v in entry.versions if v.source_version == document.target.asset_version), None)
            if source is None:
                raise LookdevError('ASSET_VERSION_NOT_FOUND', '原始资产版本不存在。', 404)
            scene = self.scenes.get(project_id)
            instance_id = document.target.scene_instance_id
            affected = [item.id for item in scene.objects if item.asset_id == entry.id and item.asset_version == request.expected_target_version and (instance_id is None or item.id == instance_id)]
            if affected and scene.version != request.expected_scene_version:
                raise LookdevError('SCENE_VERSION_CONFLICT', '场景已更新，请重新读取后应用。')
            if instance_id:
                instance = next((item for item in scene.objects if item.id == instance_id), None)
                if not instance or instance.asset_id != entry.id or instance.asset_version != request.expected_target_version:
                    raise LookdevError('INSTANCE_CHANGED', '场景实例的模型引用已变化，请重新绑定。')
                if scene.version != request.expected_scene_version:
                    raise LookdevError('SCENE_VERSION_CONFLICT', '场景已更新，请重新读取后应用。')
            if self.source is None:
                raise LookdevError('SOURCE_UNAVAILABLE', '材质源服务不可用。', 503)
            binary = apply_pbr(self.source(project_id, entry.id, source.source_version).read_bytes(), document.state)
            ids = {item['id'] for item in document.state['objects']}
            directory = self.root / uuid4().hex
            directory.mkdir(parents=True)
            target = directory / 'model.glb'
            target.write_bytes(binary)
            version = ProjectAssetVersion(source_version=entry.current_version + 1,
                asset_version_id='lookdev_' + uuid4().hex, source_kind='glb',
                dimensions_m=source.dimensions_m, vertex_count=source.vertex_count,
                triangle_count=source.triangle_count, preview_path=str(target),
                parent_source_version=source.source_version,
                geometry_source_version=source.geometry_source_version or source.source_version,
                lookdev_document_id=document.id, lookdev_document_version=document.version, node_ids={value: value for value in ids},
                operation='import', model_rotation_quaternion_xyzw=source.model_rotation_quaternion_xyzw,
                runtime_artifacts=[RuntimeArtifactReference(artifact_id='lookdev_' + uuid4().hex,
                    artifact_type='render', project_relative_path=str(target))])
            try:
                self.catalog.register_version(ProjectAssetRegistration(project_id=project_id,
                    card_id=entry.card_id, workspace_id=entry.workspace_id,
                    source_asset_id=entry.source_asset_id, title=entry.title,
                    source_type=entry.source_type, version=version, expected_version=entry.current_version))
            except Exception:
                target.unlink(missing_ok=True)
                directory.rmdir()
                raise
            if affected:
                rebound = self.scenes.rebind_asset_version(project_id, entry.id, RebindAssetVersionRequest(
                    expected_version=scene.version, from_asset_version=request.expected_target_version,
                    to_asset_version=version.source_version, object_ids=affected))
            return LookdevApplication(document_id=document.id, document_version=document.version,
                asset_id=entry.id, asset_version=version.source_version,
                scene_instance_id=instance_id, state=document.state, runtime_module=document.runtime_module or '',
                scene_version=rebound.scene.version if affected else scene.version)
