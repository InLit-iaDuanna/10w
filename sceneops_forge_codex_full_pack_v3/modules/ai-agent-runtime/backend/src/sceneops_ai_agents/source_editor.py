"""Card source browsing and explicit manual saves through the existing task writer."""
from pathlib import PurePosixPath
from pydantic import Field
from sceneops_harness import HarnessError
from .task_models import TaskModel, PrepareAgentTask, AuthorizeAgentTask, AgentAction
from .code_workspace import read_source, source_inventory, PROJECT_DEMO_DERIVED_PATHS


class SourceEntry(TaskModel):
    path: str
    section: str
    size_bytes: int
    editable: bool


class CardSourceIndex(TaskModel):
    project_id: str
    card_id: str
    branch: str
    architecture: str
    files: list[SourceEntry]
    truncated: bool


class CardSourceFile(TaskModel):
    path: str
    content: str


class SaveCardSource(TaskModel):
    allow_game_execution: bool = False
    path: str = Field(min_length=1, max_length=240)
    expected_content: str = Field(max_length=65536)
    content: str = Field(max_length=65536)


def source_index(service, project_id, card_id):
    workspace = service.card_workspace(project_id, card_id)
    files, truncated = source_inventory(workspace['worktree_path'])
    # Browsing reads the registered engineering brief, not the execution-readiness callback.
    context = (workspace.get('card_brief') or {}).get('card') or {}
    plan = context.get('technical_plan') or {}
    return CardSourceIndex(project_id=project_id, card_id=card_id, branch=workspace['branch'],
        architecture=plan.get('architecture_label') or plan.get('code_architecture') or '未登记架构',
        files=[SourceEntry(**file, section=str(PurePosixPath(file['path']).parent),
            editable=file['path'] not in PROJECT_DEMO_DERIVED_PATHS) for file in files], truncated=truncated)


def source_file(service, project_id, card_id, path):
    workspace = service.card_workspace(project_id, card_id)
    content = read_source(workspace['worktree_path'], path)
    if content is None:
        raise HarnessError('CODE_FILE_MISSING', '该源码文件已不存在，请刷新文件列表。')
    return CardSourceFile(path=path, content=content)


async def save_source(service, project_id, card_id, body):
    current = source_file(service, project_id, card_id, body.path)
    if current.content != body.expected_content:
        raise HarnessError('CODE_PREIMAGE_CONFLICT', '文件已被其他修改更新；草稿仍保留，请重新读取后合并。')
    if current.content == body.content:
        raise HarnessError('CODE_NO_CHANGE', '文件内容没有改变。')
    task = service.prepare(PrepareAgentTask(project_id=project_id, card_id=card_id,
        task_profile='card-development', source_write_paths=[body.path],
        allow_game_execution=body.allow_game_execution, goal='手动编辑 ' + body.path))
    actions = [
        AgentAction(action_id='manual_source_save', capability_id='code.file.write',
            rationale='用户保存已编辑源码', inputs=body.model_dump(exclude={'allow_game_execution'})),
    ]
    if body.allow_game_execution:
        actions.extend(AgentAction(action_id='manual_' + operation, capability_id=capability,
            rationale='用户要求保存后更新试玩', inputs={}) for operation, capability in [
            ('check', 'code.project.check'), ('build', 'code.project.build'), ('preview', 'code.preview.start')])
    actions.append(AgentAction(action_id='manual_source_finish', capability_id='agent.finish',
            rationale='回读当前源码', inputs={'summary':'手动源码保存完成。'}))
    service.authorize(task.id, AuthorizeAgentTask(authorization_card_id=task.authorization_card.id,
        accept_unknown_cost=True), actions=actions)
    job = service.jobs.get(task.id)
    if job is not None:
        await job
    return service.get(task.id)
