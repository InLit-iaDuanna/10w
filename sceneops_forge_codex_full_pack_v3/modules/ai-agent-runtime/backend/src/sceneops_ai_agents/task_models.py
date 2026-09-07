"""Task authorization and observable, bounded action contracts."""
from datetime import datetime, timezone
from typing import Annotated, Literal
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator
from sceneops_harness import ChangeSet, RuntimeBudget


def now():
    return datetime.now(timezone.utc)


def identifier(prefix):
    return f"{prefix}_{uuid4().hex}"


class TaskModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


TASK_CAPABILITIES = ["agent.next_action", "blender.asset.create", "blender.scene.inspect",
                     "blender.asset.export", "unity.asset.import", "unity.scene.inspect", "agent.finish"]
PROTOTYPE_CAPABILITIES = ["agent.next_action", "unity.prototype.compose", "unity.prototype.inspect",
    "unity.prototype.play", "unity.prototype.capture", "unity.prototype.verify", "agent.finish"]
TASK_CAPABILITIES.extend(['agent.history.read', 'agent.report_blocked'])
PROTOTYPE_CAPABILITIES.extend(['agent.history.read', 'agent.report_blocked'])
CODE_CAPABILITIES = ['agent.next_action', 'code.workspace.inspect', 'code.file.read',
                     'code.file.write', 'agent.history.read', 'agent.finish', 'agent.report_blocked']
ENVIRONMENT_SCENE_CAPABILITIES = ['agent.next_action', 'project.assets.list',
    'environment.scene.read', 'environment.object.transform', 'agent.history.read',
    'agent.finish', 'agent.report_blocked']
GAME_EXECUTION_CAPABILITIES = ['code.project.status', 'code.project.check', 'code.project.build',
                               'code.preview.start', 'code.preview.stop']
DEPENDENCY_CAPABILITY = 'code.dependencies.prepare'


def card_code_capabilities(value):
    capabilities = list(CODE_CAPABILITIES)
    if value.allow_game_execution:
        capabilities[4:4] = GAME_EXECUTION_CAPABILITIES
        if value.allow_browser_observation:
            capabilities.insert(4, 'code.browser.observe')
        if value.allow_browser_interaction:
            capabilities[4:4] = ['code.project.build_test', 'code.browser.interact']
        if value.allow_dependency_install:
            capabilities.insert(4, DEPENDENCY_CAPABILITY)
    return capabilities
TaskProfile = Literal['asset-exchange', 'survival-prototype', 'auto', 'card-development',
                      'environment-scene']
ExecutionMode = Literal["typed-tools", "codex-full-access"]
EffectState = Literal["NONE", "STAGED", "APPLIED", "COMMITTED", "UNKNOWN"]
VerificationExecutionStatus = Literal["COMPLETED", "FAILED", "CANCELLED", "INTERRUPTED"]
VerificationVerdict = Literal["PASS", "FAIL", "INCONCLUSIVE"]


class ArtifactReference(TaskModel):
    artifact_id: str
    version: int = Field(ge=1)


class VerificationRecord(TaskModel):
    """A business verdict bound to the exact revision, run, suite and evidence."""
    project_revision: str = Field(min_length=1, max_length=200)
    run_id: str = Field(min_length=1, max_length=200)
    run_ids: list[str] = Field(default_factory=list)
    suite_id: str = Field(min_length=1, max_length=200)
    suite_version: int = Field(ge=1)
    checker_version: str = Field(min_length=1, max_length=200)
    execution_status: VerificationExecutionStatus
    verdict: VerificationVerdict
    artifact_refs: list[ArtifactReference] = Field(default_factory=list)
    assertions: list[dict[str, JsonValue]] = Field(default_factory=list)

    @model_validator(mode="after")
    def verdict_requires_completed_execution(self):
        if self.execution_status != "COMPLETED" and self.verdict != "INCONCLUSIVE":
            raise ValueError("A non-completed checker execution can only be INCONCLUSIVE")
        return self


class PrepareAgentTask(TaskModel):
    allow_browser_interaction: bool = False
    allow_browser_observation: bool = False
    goal: str = Field(min_length=1, max_length=8000)
    project_id: str | None = None
    card_id: str | None = Field(default=None, pattern=r'^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$')
    execution_mode: ExecutionMode = "typed-tools"
    allow_image_generation: bool = False
    allow_playtest: bool = False
    allow_game_execution: bool = False
    allow_dependency_install: bool = False
    task_profile: TaskProfile = 'asset-exchange'
    selected_scene_object_ids: list[str] = Field(default_factory=list, max_length=16)

    @model_validator(mode='after')
    def card_scope(self):
        if self.allow_browser_interaction and (self.task_profile != 'card-development' or not self.allow_game_execution):
            raise ValueError('浏览器输入检查需要卡片工程运行授权。')
        if self.allow_browser_observation and (self.task_profile != 'card-development' or not self.allow_game_execution):
            raise ValueError('浏览器观察需要卡片工程运行授权。')
        if self.task_profile == 'card-development':
            if not self.project_id or not self.card_id or self.execution_mode != 'typed-tools':
                raise ValueError('卡片开发需要项目、已登记卡片和 typed-tools 权限。')
            if self.allow_playtest or self.allow_image_generation:
                raise ValueError('卡片代码开发不包含图片生成或游测执行。')
            if self.allow_dependency_install and not self.allow_game_execution:
                raise ValueError('依赖准备只能与游戏工程执行权限一起授权。')
        elif self.task_profile == 'environment-scene':
            if not self.project_id or self.execution_mode != 'typed-tools':
                raise ValueError('环境场景编辑需要当前项目和 typed-tools 权限。')
            if len(self.selected_scene_object_ids) != 1:
                raise ValueError('环境场景编辑需要且只接受一个已选场景对象。')
            if (self.card_id is not None or self.allow_playtest or self.allow_image_generation
                    or self.allow_game_execution or self.allow_dependency_install):
                raise ValueError('环境场景编辑不包含卡片开发、图片生成、工程执行或游测。')
        elif self.allow_game_execution or self.allow_dependency_install:
            raise ValueError('游戏工程执行权限仅用于 card-development。')
        elif self.card_id is not None:
            raise ValueError('card_id 仅用于 card-development。')
        elif self.selected_scene_object_ids:
            raise ValueError('选中场景对象上下文仅用于 environment-scene 任务。')
        return self


class AuthorizeAgentTask(TaskModel):
    authorization_card_id: str
    accept_unknown_cost: Literal[True]
    accept_full_access: bool = False


class AuthorizationCard(TaskModel):
    allow_browser_interaction: bool = False
    allow_browser_observation: bool = False
    id: str = Field(default_factory=lambda: identifier("card"))
    workspace_root: str
    card_id: str | None = None
    branch: str | None = None
    execution_mode: ExecutionMode = "typed-tools"
    allow_image_generation: bool = False
    allow_playtest: bool = False
    allow_game_execution: bool = False
    allow_dependency_install: bool = False
    task_profile: TaskProfile = 'asset-exchange'
    capability_ids: list[str] = Field(default_factory=lambda: list(TASK_CAPABILITIES))
    scene_write_object_ids: list[str] = Field(default_factory=list, max_length=16)
    max_model_calls: int | None = 8
    max_cli_invocations: int | None = None
    max_duration_seconds: int = 1200
    max_attempts_per_action: int = 2
    max_repair_rounds: int = Field(default=2, ge=0, le=2)
    max_assets: int = 1
    scope: str = "仅此独立空项目：创建有界立方体、检查、导出 FBX、导入和放置到 Unity；不修改已有项目，不构建、渲染或游测。"
    cost_notice: str = "最多 8 次模型请求（含规划和修复），20 分钟，每动作最多 2 次尝试；CLI 费用可能未知，这不是美元或 token 硬限额。"

    @model_validator(mode="before")
    @classmethod
    def preserve_historical_playtest_authorization(cls, value):
        if isinstance(value, dict):
            value = dict(value)
            if 'allow_playtest' not in value:
                value['allow_playtest'] = 'unity.prototype.verify' in value.get('capability_ids', [])
            value.setdefault('allow_game_execution', False)
            value.setdefault('allow_dependency_install', False)
        return value

    @model_validator(mode='after')
    def dependency_scope(self):
        if self.allow_dependency_install and not self.allow_game_execution:
            raise ValueError('依赖准备需要游戏工程执行权限。')
        return self


class TaskGrant(TaskModel):
    allow_browser_interaction: bool = False
    allow_browser_observation: bool = False
    id: str = Field(default_factory=lambda: identifier("grant"))
    task_id: str
    project_id: str
    workspace_root: str
    card_id: str | None = None
    branch: str | None = None
    execution_mode: ExecutionMode = "typed-tools"
    allow_image_generation: bool = False
    allow_game_execution: bool = False
    allow_dependency_install: bool = False
    capability_ids: list[str]
    scene_write_object_ids: list[str] = Field(default_factory=list, max_length=16)
    max_repair_rounds: int = Field(default=2, ge=0, le=2)
    actor_id: str = "usr_local_workspace"
    budget: RuntimeBudget = Field(default_factory=lambda: RuntimeBudget(max_steps=32,
        max_attempts_per_step=2, max_duration_seconds=1200, max_metered_calls=8, usage_policy="bounded_calls"))
    authorized_at: datetime = Field(default_factory=now)
    expires_at: datetime
    revoked: bool = False


class AgentAction(TaskModel):
    action_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,100}$")
    capability_id: str
    rationale: str = Field(min_length=1, max_length=2000)
    inputs: dict[str, JsonValue] = Field(default_factory=dict)


class NextActionInput(TaskModel):
    goal: str
    context_summary: dict[str, JsonValue] = Field(default_factory=dict)
    observations: dict[str, JsonValue]
    history: list[dict[str, JsonValue]]
    capabilities: list[dict[str, JsonValue]]
    expected_provider: str
    expected_model: str
    input_schemas: dict[str, JsonValue] = Field(default_factory=dict)


SceneCoordinate = Annotated[float, Field(ge=-10000, le=10000, allow_inf_nan=False)]


class SceneTransformInput(TaskModel):
    object_id: str = Field(pattern=r"^sobj_[A-Za-z0-9_-]{1,160}$")
    expected_version: int = Field(ge=0)
    position_m: tuple[SceneCoordinate, SceneCoordinate, SceneCoordinate]
    rotation_y_deg: float = Field(ge=-360000, le=360000, allow_inf_nan=False)
    scale: float = Field(gt=0.01, le=100, allow_inf_nan=False)


class CreateCubeInput(TaskModel):
    asset_id: str = Field(pattern=r"^ast_[A-Za-z0-9_-]{8,100}$")
    sceneops_id: str = Field(pattern=r"^sobj_[A-Za-z0-9_-]{8,100}$")
    name: str = Field(min_length=1, max_length=100, pattern=r"^[^/\\\x00-\x1f]+$")
    dimensions_m: tuple[Annotated[float, Field(ge=0.001, le=100, allow_inf_nan=False)],
                        Annotated[float, Field(ge=0.001, le=100, allow_inf_nan=False)],
                        Annotated[float, Field(ge=0.001, le=100, allow_inf_nan=False)]]


class AssetInput(TaskModel):
    asset_id: str = Field(pattern=r"^ast_[A-Za-z0-9_-]{8,100}$")


class EmptyActionInput(TaskModel):
    pass


GameOperation = Literal['prepare', 'check', 'build', 'build_test', 'preview_start', 'preview_test', 'preview_stop', 'observe', 'interact']
GameRunStatus = Literal['running', 'succeeded', 'failed', 'stale', 'stopped', 'interrupted']


class GameOperationRequest(TaskModel):
    operation: Literal['prepare', 'check', 'build', 'build_test', 'preview_start', 'preview_stop', 'observe']


class BrowserKeyStep(TaskModel):
    keys: list[Literal['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'w', 'a', 's', 'd', 'Space', 'Enter']] = Field(default_factory=list, max_length=2)
    duration_ms: int = Field(ge=16, le=2000)


class BrowserInteractionRequest(TaskModel):
    check: Literal['input-readback', 'movement-collection', 'current-input'] = 'input-readback'
    state_id: str = Field(default='start', min_length=1, max_length=80)
    steps: list[BrowserKeyStep] = Field(min_length=1, max_length=8)

    @model_validator(mode='after')
    def bounded_time(self):
        if sum(step.duration_ms for step in self.steps) > 8000:
            raise ValueError('输入序列的受控时间总计不得超过8000毫秒。')
        if self.check == 'movement-collection' and (len(self.steps) < 4 or self.steps[1].keys):
            raise ValueError('移动收集检查至少需要移动、松键、离开和再次经过四段输入。')
        return self


class GameExecutionRun(TaskModel):
    build_kind: Literal['delivery', 'test'] = 'delivery'
    build_run_id: str | None = None
    preview_run_id: str | None = None
    observation: dict[str, JsonValue] | None = None
    artifact_ids: list[str] = Field(default_factory=list)
    id: str = Field(default_factory=lambda: identifier('game_run'))
    operation: GameOperation
    status: GameRunStatus = 'running'
    mode: Literal['live'] = 'live'
    project_id: str
    card_id: str
    task_id: str
    workspace_root: str
    branch: str
    started_at: datetime = Field(default_factory=now)
    finished_at: datetime | None = None
    exit_code: int | None = None
    passed: bool | None = None
    failure_code: str | None = None
    log: str = ''
    artifact_path: str | None = None
    preview_url: str | None = None
    source_stale: bool = False


class GameProjectExecution(TaskModel):
    test_build: GameExecutionRun | None = None
    interaction: GameExecutionRun | None = None
    observation: GameExecutionRun | None = None
    project_id: str
    card_id: str
    workspace_root: str
    branch: str
    dependencies_ready: bool = False
    dependency: GameExecutionRun | None = None
    check: GameExecutionRun | None = None
    build: GameExecutionRun | None = None
    preview: GameExecutionRun | None = None
    browser_errors_verified: bool = False
    gameplay_verified: bool = False


class CodeReadInput(TaskModel):
    path: str = Field(min_length=1, max_length=240)


class CodeWriteInput(CodeReadInput):
    expected_content: str | None = Field(max_length=65536)
    content: str = Field(max_length=65536)


class CapabilityGapInput(TaskModel):
    reason: str = Field(min_length=1, max_length=1500)
    needed_capabilities: list[str] = Field(default_factory=list, max_length=10)


class HistoryReadInput(TaskModel):
    reference: str = Field(pattern=(r"^task-action://[A-Za-z0-9_-]{1,100}/"
                                    r"(?:input/(?:expected_content|content)|result)$"))


class PrototypeVerifyInput(TaskModel):
    composition_action_id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,100}$')


class CodexTaskInput(TaskModel):
    goal: str = Field(min_length=1, max_length=8000)


class FinishInput(TaskModel):
    summary: str = Field(min_length=1, max_length=2000)


class ToolResult(TaskModel):
    evidence: dict[str, JsonValue]


class ActionRecord(TaskModel):
    action: AgentAction
    assigned_role: str = "producer"
    request_id: str = Field(default_factory=lambda: identifier("request"))
    run_ids: list[str] = Field(default_factory=list)
    attempts: int = 0
    state: Literal["planned", "running", "succeeded", "failed", "uncertain", "blocked"] = "planned"
    effect_state: EffectState = "NONE"
    verification_result: VerificationRecord | None = None
    change_set: ChangeSet | None = None
    approval_id: str | None = None
    result: dict[str, JsonValue] | None = None
    reason: str | None = None

    @model_validator(mode="before")
    @classmethod
    def migrate_effect_state(cls, value):
        """Old records did not prove external effect state; never upgrade them optimistically."""
        if not isinstance(value, dict) or "effect_state" in value:
            return value
        migrated = dict(value)
        action = migrated.get("action") or {}
        capability_id = (action.get("capability_id", "") if isinstance(action, dict)
                         else getattr(action, "capability_id", ""))
        state = migrated.get("state", "planned")
        mutating = capability_id in {
            "blender.asset.create", "blender.asset.export", "unity.asset.import",
            "unity.prototype.compose", "unity.prototype.play", "unity.prototype.capture",
            "unity.prototype.verify", "codex.task.execute",
            "code.dependencies.prepare", "code.project.check", "code.project.build",
            "code.preview.start", "code.preview.stop",
            "environment.object.transform",
        }
        migrated["effect_state"] = "UNKNOWN" if mutating and state != "planned" else "NONE"
        return migrated


class BrowserObservationAuthorization(TaskModel):
    task_id: str
    project_id: str
    workspace_root: str
    card_id: str
    branch: str
    expires_at: datetime
    revoked: bool = False


class AgentTaskRecord(TaskModel):
    browser_interaction_authorization: BrowserObservationAuthorization | None = None
    browser_authorization: BrowserObservationAuthorization | None = None
    id: str = Field(default_factory=lambda: identifier("task"))
    project_id: str
    goal: str
    status: Literal["awaiting_authorization", "queued", "running", "blocked", "needs_approval", "completed", "review_required", "failed", "cancel_pending", "cancelled", "interrupted"] = "awaiting_authorization"
    authorization_card: AuthorizationCard
    grant: TaskGrant | None = None
    model_calls_used: int = 0
    cli_invocations_used: int = 0
    repair_rounds_used: int = Field(default=0, ge=0)
    model_tokens_known: int = 0
    cost_usd: float | None = None
    budget_accounting_complete: bool = False
    actions: list[ActionRecord] = Field(default_factory=list)
    model_run_ids: list[str] = Field(default_factory=list)
    current_run_id: str | None = None
    pending_action_id: str | None = None
    observations: dict[str, JsonValue] = Field(default_factory=dict)
    reason: str | None = None
    cancel_requested: bool = False
    owner_pid: int | None = None
    provider_id: str | None = None
    provider_model: str | None = None
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)
    finished_at: datetime | None = None


class AgentTaskEvent(TaskModel):
    sequence: int
    task_id: str
    project_id: str
    occurred_at: datetime
    event_type: str
    payload: dict[str, JsonValue]


class AgentTaskEvents(TaskModel):
    events: list[AgentTaskEvent]
    next_cursor: int


class AgentTaskList(TaskModel):
    tasks: list[AgentTaskRecord]
