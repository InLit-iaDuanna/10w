"""Project production read models; execution remains owned by Harness."""
from typing import Literal
from pydantic import Field, model_validator
from .task_models import (TaskModel, AgentTaskRecord, AgentTaskEvent, EffectState,
                          VerificationRecord)

ProductionModuleId = Literal['project-planning', 'concept-assets', 'character-animation',
    'world-logic', 'ui-audio-vfx', 'render-ops', 'unity-build', 'ai-playtest',
    'version-review', 'integration-ops']


class ProductionStep(TaskModel):
    id: str
    project_id: str
    task_id: str
    module_id: ProductionModuleId
    title: str
    capability_id: str
    dependencies: list[str] = Field(default_factory=list)
    state: Literal['planned', 'running', 'blocked', 'failed', 'cancelled', 'review_required', 'completed']
    verification: Literal['unverified', 'reported', 'passed', 'failed', 'inconclusive'] = 'unverified'
    verification_result: VerificationRecord | None = None
    effect_state: EffectState = 'UNKNOWN'
    mode: Literal['planned', 'live', 'cached', 'mock', 'blocked'] = 'planned'
    run_id: str | None = None
    artifact_ids: list[str] = Field(default_factory=list)
    reason: str | None = None
    started_at: str | None = None
    updated_at: str

    @model_validator(mode='after')
    def canonical_verification_projection(self):
        if self.verification_result is not None:
            self.verification = {'PASS': 'passed', 'FAIL': 'failed', 'INCONCLUSIVE': 'inconclusive'}[self.verification_result.verdict]
        elif self.verification in ('passed', 'failed'):
            # Old scalar records have no revision/run/suite binding and are not current proof.
            self.verification = 'inconclusive'
        return self


class ProductionArtifact(TaskModel):
    id: str
    project_id: str
    task_id: str
    step_id: str
    module_id: ProductionModuleId
    name: str
    version: int
    source_path: str
    kind: Literal['image', 'model', 'audio', 'text', 'file']
    media_type: str
    size_bytes: int
    mode: Literal['live', 'cached', 'mock'] = 'live'
    verification: Literal['unverified', 'format_checked', 'passed', 'failed'] = 'unverified'
    created_at: str


class ProductionModule(TaskModel):
    id: ProductionModuleId
    title: str
    handler_status: Literal['implemented', 'not_connected']
    verification: str = '待用户实测'
    capability_ids: list[str] = Field(default_factory=list)
    readiness_notice: str = ''


class ProductionSnapshot(TaskModel):
    project_id: str
    cursor: int
    tasks: list[AgentTaskRecord]
    steps: list[ProductionStep]
    artifacts: list[ProductionArtifact]
    modules: list[ProductionModule]


class ProductionEvents(TaskModel):
    events: list[AgentTaskEvent]
    next_cursor: int
