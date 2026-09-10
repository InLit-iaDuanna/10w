"""Saved document exports reuse the canonical compiler and portable package encoder."""
import base64
import json
from uuid import uuid4
from pathlib import Path
from .lookdev_glb import apply_pbr
from .lookdev_models import LookdevError, LookdevExport


async def export_document(service, project_id, request):
    document = service.get(project_id, request.document_id, request.document_version)
    source = service.source(project_id, document.target.asset_id, document.target.asset_version).read_bytes()
    warnings = []
    if request.format == 'pbr-glb':
        content = apply_pbr(source, document.state)
        suffix, media_type = '.glb', 'model/gltf-binary'
        if any(item.get('shaderGraph') or item.get('procedural', {}).get('type', 'none') != 'none' for item in document.state['materials']):
            warnings.append('GLB 仅保存基础 PBR，不包含 Shader 图、程序化图案或时间动画；请同时导出 Shader ZIP。')
        warnings.append('编辑器预览灯光、环境与相机设置不写入模型。')
    else:
        timeline = next((item for item in document.history if item.get('kind') == 'lookdev.history@1'), None)
        payload = {'action': 'export', 'format': request.format, 'project': document.state}
        if request.format == 'luma-zip':
            payload['sourceBase64'] = base64.b64encode(source).decode()
            payload['history'] = {'past': timeline['past'], 'future': timeline['future']} if timeline else {'past': [], 'future': []}
        result = await service.validator(payload)
        content = base64.b64decode(result['base64'], validate=True)
        suffix, media_type = ('.luma.zip' if request.format == 'luma-zip' else '.shader.zip'), 'application/zip'
    artifact_id = str(uuid4())
    directory = service.database.parent / 'lookdev-exports'
    directory.mkdir(parents=True, exist_ok=True)
    filename = artifact_id + suffix
    path = directory / filename
    artifact = LookdevExport(id=artifact_id, project_id=project_id, document_id=document.id,
        document_version=document.version, format=request.format, filename=filename,
        media_type=media_type, size_bytes=len(content), warnings=warnings,
        download_url=f'/api/lookdev/{project_id}/exports/{artifact_id}/download')
    path.write_bytes(content)
    try:
        with service.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS lookdev_exports (project_id TEXT NOT NULL, id TEXT NOT NULL, body TEXT NOT NULL, path TEXT NOT NULL, PRIMARY KEY(project_id,id))')
            db.execute('INSERT INTO lookdev_exports VALUES(?,?,?,?)', (project_id, artifact_id, artifact.model_dump_json(), str(path)))
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return artifact


def export_file(service, project_id, artifact_id):
    service.require_project(project_id)
    with service.connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS lookdev_exports (project_id TEXT NOT NULL, id TEXT NOT NULL, body TEXT NOT NULL, path TEXT NOT NULL, PRIMARY KEY(project_id,id))')
        row = db.execute('SELECT body,path FROM lookdev_exports WHERE project_id=? AND id=?', (project_id, artifact_id)).fetchone()
    if row is None or not Path(row[1]).is_file():
        raise LookdevError('EXPORT_NOT_FOUND', '导出制品不存在。', 404)
    return LookdevExport.model_validate_json(row[0]), Path(row[1])
