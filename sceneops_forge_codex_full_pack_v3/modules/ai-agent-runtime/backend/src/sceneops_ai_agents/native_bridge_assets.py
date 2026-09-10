"""Register actual GLB geometry as immutable, workspace-owned asset versions."""
import math
import shutil
import struct
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field
from sceneops_harness import HarnessError
from asset_factory import inspect_native_glb, register_glb_identity_bytes
from asset_library import ProjectAssetRegistration, ProjectAssetVersion, RuntimeArtifactReference


class RegisterNativeAssetInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    path: str = Field(min_length=1, description='Workspace-relative self-contained GLB 2 path')
    title: str = Field(min_length=1, max_length=120)
    assign_missing_identities: bool = Field(default=False, description='Explicit first import only: persist missing object, material and animation IDs in the new artifact')
    asset_id: str | None = Field(default=None, description='Existing asset ID for a new version')
    expected_version: int | None = Field(default=None, ge=1)


def _multiply(a, b):
    return [sum(a[row + k * 4] * b[k + col * 4] for k in range(4)) for col in range(4) for row in range(4)]


def _transform(node):
    if 'matrix' in node:
        if len(node['matrix']) != 16:
            raise ValueError('GLB node matrix must contain 16 values')
        return node['matrix']
    x, y, z, w = node.get('rotation', [0, 0, 0, 1])
    sx, sy, sz = node.get('scale', [1, 1, 1])
    tx, ty, tz = node.get('translation', [0, 0, 0])
    return [(1-2*y*y-2*z*z)*sx, (2*x*y+2*z*w)*sx, (2*x*z-2*y*w)*sx, 0,
            (2*x*y-2*z*w)*sy, (1-2*x*x-2*z*z)*sy, (2*y*z+2*x*w)*sy, 0,
            (2*x*z+2*y*w)*sz, (2*y*z-2*x*w)*sz, (1-2*x*x-2*y*y)*sz, 0, tx, ty, tz, 1]


def inspect_geometry(path):
    document = inspect_native_glb(path)
    if not document.get('buffers') or document['buffers'][0].get('uri'):
        raise ValueError('GLB geometry must use its embedded binary buffer')
    raw = path.read_bytes()
    json_size = struct.unpack_from('<I', raw, 12)[0]
    offset = 20 + json_size
    if offset + 8 > len(raw):
        raise ValueError('GLB has no binary geometry chunk')
    size, kind = struct.unpack_from('<II', raw, offset)
    if kind != 0x004E4942 or offset + 8 + size > len(raw):
        raise ValueError('GLB binary chunk is invalid')
    binary = raw[offset + 8:offset + 8 + size]
    points, vertices, triangles = [], 0, 0
    scenes = document.get('scenes', [])
    if not scenes:
        raise ValueError('GLB has no scene')
    identity = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]

    def visit(index, parent, ancestors):
        nonlocal vertices, triangles
        if index in ancestors:
            raise ValueError('GLB node hierarchy is cyclic')
        node = document['nodes'][index]
        matrix = _multiply(parent, _transform(node))
        if 'mesh' in node:
            for primitive in document['meshes'][node['mesh']]['primitives']:
                accessor = document['accessors'][primitive['attributes']['POSITION']]
                if (accessor.get('componentType') != 5126 or accessor.get('type') != 'VEC3'
                        or 'sparse' in accessor or 'bufferView' not in accessor
                        or 'KHR_draco_mesh_compression' in primitive.get('extensions', {})):
                    raise ValueError('Register an uncompressed GLB with float VEC3 positions')
                view = document['bufferViews'][accessor['bufferView']]
                if view.get('buffer', 0) != 0 or view.get('extensions'):
                    raise ValueError('GLB geometry buffer must be embedded and uncompressed')
                start = view.get('byteOffset', 0) + accessor.get('byteOffset', 0)
                stride = view.get('byteStride', 12)
                if stride < 12 or start < 0:
                    raise ValueError('GLB position buffer range is invalid')
                count = accessor['count']
                if count < 1 or start + (count-1)*stride + 12 > len(binary):
                    raise ValueError('GLB position buffer range is invalid')
                for point in range(count):
                    values = struct.unpack_from('<fff', binary, start + point*stride)
                    transformed = tuple(sum(matrix[row + k*4]*values[k] for k in range(3)) + matrix[row+12] for row in range(3))
                    if not all(math.isfinite(value) for value in transformed):
                        raise ValueError('GLB has non-finite geometry')
                    points.append(transformed)
                vertices += count
                count = document['accessors'][primitive['indices']]['count'] if 'indices' in primitive else count
                mode = primitive.get('mode', 4)
                triangles += count // 3 if mode == 4 else max(0, count-2) if mode in (5, 6) else 0
        for child in node.get('children', []):
            visit(child, matrix, {*ancestors, index})

    for index in scenes[document.get('scene', 0)].get('nodes', []):
        visit(index, identity, set())
    if not points:
        raise ValueError('GLB active scene contains no geometry')
    dimensions = tuple(max(p[i] for p in points) - min(p[i] for p in points) for i in range(3))
    return dimensions, vertices, triangles


def register_native_asset(service, task, body):
    root = Path(task.grant.workspace_root).resolve()
    source = root / body.path
    if (Path(body.path).is_absolute() or source.resolve() != source or not source.is_relative_to(root)
            or source.suffix.lower() != '.glb' or not source.is_file()):
        raise HarnessError('TASK_SCOPE_DENIED', 'GLB 必须是当前工作区内真实文件，不能穿越目录或符号链接。')
    asset = service.project_assets.get(task.project_id, body.asset_id) if body.asset_id else None
    if asset is not None and asset.workspace_id != task.grant.workspace_id:
        raise HarnessError('TASK_SCOPE_DENIED', '资产不属于当前工作区。')
    if (asset is not None and body.expected_version != asset.current_version) or (asset is None and body.expected_version is not None):
        raise HarnessError('ASSET_SOURCE_CONFLICT', '读取当前资产版本后提交 expected_version。')
    if body.assign_missing_identities and asset is not None:
        raise HarnessError('ASSET_IDENTITY_CONFLICT', '已有资产版本必须保留原有身份，不能重新分配。')
    identity_bytes = register_glb_identity_bytes(source) if body.assign_missing_identities else None
    dimensions, vertices, triangles = inspect_geometry(source)
    version_id = 'aver_' + uuid4().hex
    target = root / 'public' / 'sceneops-assets' / (version_id + '.glb')
    for parent in (target.parent.parent, target.parent):
        if parent.is_symlink():
            raise HarnessError('TASK_SCOPE_DENIED', '资产输出目录不能为符号链接。')
        parent.mkdir(exist_ok=True)
    with target.open('xb') as output, source.open('rb') as original:
        output.write(identity_bytes) if identity_bytes is not None else shutil.copyfileobj(original, output)
    version = ProjectAssetVersion(source_version=asset.current_version+1 if asset else 1,
        asset_version_id=version_id, source_kind='glb', operation='import',
        dimensions_m=dimensions, vertex_count=vertices, triangle_count=triangles,
        parent_source_version=asset.current_version if asset else None, preview_path=str(target),
        runtime_artifacts=[RuntimeArtifactReference(artifact_id='artifact_' + uuid4().hex,
            artifact_type='render', project_relative_path=target.relative_to(root).as_posix())])
    saved = service.project_assets.register_version(ProjectAssetRegistration(project_id=task.project_id,
        workspace_id=task.grant.workspace_id, source_asset_id=asset.source_asset_id if asset else 'native_' + uuid4().hex,
        card_id=asset.card_id if asset else None, source_type=asset.source_type if asset else 'import',
        title=body.title, expected_version=body.expected_version, version=version))
    return {'tool': 'project_asset_source', 'mode': 'live', 'effect_state': 'COMMITTED',
            'asset': saved.entry.model_dump(mode='json'), 'operation': 'glb-register'}
