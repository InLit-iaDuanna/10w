"""Read an explicit model-reported output manifest; never infer outputs from shell text."""
import json
from pathlib import PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from sceneops_harness import HarnessError
from .production_catalog import MODULE_TITLES
from .production_models import ProductionModuleId, ProductionStep
from .task_models import now


OUTPUT_MANIFEST_INSTRUCTION = (
    '任务结束前，在任务工作目录根保存 sceneops-outputs.json，内容严格为 '
    '{"version":1,"artifacts":[{"path":"outputs/example.png","module_id":"concept-assets"}]}。'
    'artifacts 最多 100 项，清单不超过 1 MiB；每项只含 path 和 module_id。'
    'path 必须是任务目录内真实存在文件的规范相对路径，用 / 分隔，不含 ..、符号链接或隐藏目录/文件。'
    'module_id 只能为 project-planning、concept-assets、character-animation、world-logic、ui-audio-vfx、'
    'render-ops、unity-build、ai-playtest、version-review、integration-ops。'
    '只列出本次实际交付的文件，不列密钥、令牌、认证文件、未生成文件或仅计划产物；同一路径只列一次。'
    '模块分类仅代表你的产物归属建议，不代表该模块已执行、通过验证或完成。'
    '若本次已明确授权原生图片生成，使用 Codex 登录态原生能力，把真实生成图片复制到任务目录后列入清单。'
    '不得以描述文字或占位图冒充生成结果；账户不支持时说明真实原因，不改用付费 API 或其他账户。'
)
MAX_MANIFEST_BYTES = 1024 * 1024


class OutputFile(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    path: str = Field(min_length=1, max_length=4096)
    module_id: ProductionModuleId

    @field_validator('path')
    @classmethod
    def canonical_relative(cls, value):
        path = PurePosixPath(value)
        if (path.is_absolute() or not path.parts or path.as_posix() != value or '\\' in value
                or any(part.startswith('.') for part in path.parts)
                or any(ord(character) < 32 or ord(character) == 127 for character in value)):
            raise ValueError('Expected canonical non-hidden relative path')
        return value


class OutputManifest(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    version: Literal[1]
    artifacts: list[OutputFile] = Field(max_length=100)


def _event(service, task, event_type, **payload):
    service.records.update(task.id, lambda current: None, event_type, payload)


def _read_manifest(service, task, root):
    path = root / 'sceneops-outputs.json'
    try:
        stream, metadata = service.production._open_regular(path)
    except HarnessError as error:
        if isinstance(error.__cause__, FileNotFoundError):
            _event(service, task, 'production.outputs.missing', code='OUTPUT_MANIFEST_MISSING')
        else:
            _event(service, task, 'production.outputs.rejected', code='OUTPUT_MANIFEST_PATH_INVALID')
        return None
    try:
        with stream:
            if metadata.st_size > MAX_MANIFEST_BYTES:
                raise ValueError('Manifest too large')
            data = stream.read(MAX_MANIFEST_BYTES + 1)
        if len(data) > MAX_MANIFEST_BYTES:
            raise ValueError('Manifest too large')
        value = json.loads(data)
        # bool equals int in Python; the version is a number, never a boolean.
        if not isinstance(value, dict) or type(value.get('version')) is not int:
            raise ValueError('Invalid version type')
        return OutputManifest.model_validate(value)
    except (ValueError, UnicodeError, ValidationError, OSError):
        _event(service, task, 'production.outputs.rejected', code='OUTPUT_MANIFEST_INVALID')
        return None


def register_output_manifest(service, task, entry):
    """Register only existing contained files; module association remains reported."""
    task = service.get(task.id)
    root = service.workspace_base / task.project_id
    persisted_entry = next((action for action in task.actions if action.action.action_id == entry.action.action_id), None)
    if (task.grant is None or task.grant.workspace_root != str(root)
            or task.grant.execution_mode != 'codex-full-access'
            or not service.records.owns_workspace(task.project_id, root)
            or persisted_entry is None or persisted_entry.action.capability_id != 'codex.task.execute'):
        raise HarnessError('OUTPUT_SCOPE_DENIED', '输出清单不属于当前已登记的 Codex 任务。')
    entry = persisted_entry
    manifest = _read_manifest(service, task, root)
    if manifest is None:
        return []
    registered, seen, modules = [], set(), set()
    for index, output in enumerate(manifest.artifacts):
        if output.path in seen:
            _event(service, task, 'production.outputs.rejected', code='OUTPUT_PATH_DUPLICATED', index=index)
            continue
        seen.add(output.path)
        try:
            candidate, _ = service.production._open_regular(root / output.path)
            candidate.close()
        except HarnessError as error:
            _event(service, task, 'production.outputs.rejected', code=error.code, index=index)
            continue
        module_id = output.module_id
        step_id = f'{task.id}:outputs:{module_id}'
        if module_id not in modules:
            service.production.upsert_step(ProductionStep(id=step_id, project_id=task.project_id,
                task_id=task.id, module_id=module_id, title=f'{MODULE_TITLES[module_id]} · 产物归属待审阅',
                capability_id='codex.task.execute', dependencies=[f'{task.id}:{entry.action.action_id}'],
                state='review_required', verification='reported', mode='live',
                run_id=entry.run_ids[-1] if entry.run_ids else None,
                reason='模块关联来自模型输出清单，不代表已执行该模块或已通过验收。', updated_at=now().isoformat()))
            modules.add(module_id)
        try:
            registered.append(service.production.record_artifact(task, step_id, module_id, root / output.path))
        except HarnessError as error:
            _event(service, task, 'production.outputs.rejected', code=error.code, index=index)
        except OSError:
            _event(service, task, 'production.outputs.rejected', code='OUTPUT_FILE_UNAVAILABLE', index=index)
    _event(service, task, 'production.outputs.registered', count=len(registered), declared_count=len(manifest.artifacts))
    return registered
