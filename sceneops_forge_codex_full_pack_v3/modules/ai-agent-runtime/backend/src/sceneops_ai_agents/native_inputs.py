"""Registered per-project inputs for native production rounds."""
import base64
import binascii
from pathlib import Path
import re
from uuid import uuid4

from pydantic import Field
from sceneops_harness import HarnessError
from .task_models import TaskModel


MAX_INPUT_BYTES = 10 * 1024 * 1024
INPUT_PATH = re.compile(r'^\.sceneops/inputs/in_[a-f0-9]{32}(?:_[A-Za-z0-9._-]{1,80})?$')
IMAGE_SUFFIXES = {'.png', '.jpg', '.jpeg', '.webp', '.gif'}


class NativeInputUpload(TaskModel):
    name: str = Field(min_length=1, max_length=180)
    media_type: str = Field(default='application/octet-stream', min_length=1, max_length=120)
    content_base64: str = Field(min_length=1, max_length=14_000_000)


class NativeInputReference(TaskModel):
    id: str
    path: str
    name: str
    media_type: str
    size_bytes: int
    kind: str


def _input_directory(root: Path) -> Path:
    sceneops = root / '.sceneops'
    destination = sceneops / 'inputs'
    for item in (sceneops, destination):
        if item.is_symlink():
            raise HarnessError('TASK_SCOPE_DENIED', '制作输入目录不能是符号链接。')
    destination.mkdir(parents=True, exist_ok=True)
    return destination


def save_native_input(service, project_id: str, body: NativeInputUpload) -> NativeInputReference:
    service.workspace.get_project(project_id)
    workspace = service.workspace.open_project_demo_workspace(project_id)
    root = Path(workspace['workspace_root']).resolve(strict=True)
    try:
        content = base64.b64decode(body.content_base64, validate=True)
    except (binascii.Error, ValueError) as error:
        raise HarnessError('NATIVE_INPUT_INVALID', '附件内容不是有效编码。') from error
    if not content or len(content) > MAX_INPUT_BYTES:
        raise HarnessError('NATIVE_INPUT_SIZE', '单个制作附件必须在 10 MiB 以内。')
    original = Path(body.name).name
    if original != body.name or original in ('.', '..'):
        raise HarnessError('NATIVE_INPUT_INVALID', '附件名称无效。')
    safe = re.sub(r'[^A-Za-z0-9._-]+', '_', original).strip('._')[:80] or 'input'
    identifier = 'in_' + uuid4().hex
    target = _input_directory(root) / f'{identifier}_{safe}'
    if target.is_symlink():
        raise HarnessError('TASK_SCOPE_DENIED', '附件目标不能是符号链接。')
    with target.open('xb') as stream:
        stream.write(content)
    relative = target.relative_to(root).as_posix()
    return NativeInputReference(id=identifier, path=relative, name=original,
        media_type=body.media_type, size_bytes=len(content),
        kind='image' if target.suffix.lower() in IMAGE_SUFFIXES else 'file')


def resolve_native_inputs(root: Path, paths: list[str]) -> list[dict]:
    records = []
    for value in dict.fromkeys(paths):
        if not INPUT_PATH.fullmatch(value):
            raise HarnessError('NATIVE_INPUT_INVALID', '制作附件不是当前项目的已登记输入。')
        path = root / value
        try:
            resolved = path.resolve(strict=True)
        except OSError as error:
            raise HarnessError('NATIVE_INPUT_MISSING', '制作附件已不存在，请重新选择。') from error
        if path.is_symlink() or resolved.parent != (root / '.sceneops' / 'inputs').resolve(strict=True) \
                or not resolved.is_file() or resolved.stat().st_size > MAX_INPUT_BYTES:
            raise HarnessError('TASK_SCOPE_DENIED', '制作附件超出已登记项目输入范围。')
        records.append({'path': value, 'name': path.name, 'size_bytes': resolved.stat().st_size,
            'kind': 'image' if path.suffix.lower() in IMAGE_SUFFIXES else 'file',
            'absolute_path': resolved})
    return records
