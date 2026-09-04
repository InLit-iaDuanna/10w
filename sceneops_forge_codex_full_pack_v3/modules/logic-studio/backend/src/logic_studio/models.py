from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ExecutionMode(str, Enum):
    LIVE = "live"
    CACHED = "cached"
    MOCK = "mock"
    PLANNED = "planned"
    BLOCKED = "blocked"


class ValueType(str, Enum):
    BOOLEAN = "boolean"
    INTEGER = "integer"
    NUMBER = "number"
    STRING = "string"
    STRING_SET = "string_set"


class NodeKind(str, Enum):
    START = "start"
    STATE = "state"
    INTERACTION = "interaction"
    QUEST = "quest"
    DIALOGUE = "dialogue"
    FEEDBACK = "feedback"
    ENDING = "ending"


class ConditionOperator(str, Enum):
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    GREATER_THAN = "greater_than"
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"
    LESS_THAN = "less_than"
    LESS_THAN_OR_EQUAL = "less_than_or_equal"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"


class EffectOperation(str, Enum):
    SET = "set"
    INCREMENT = "increment"
    DECREMENT = "decrement"
    ADD = "add"
    REMOVE = "remove"
    TOGGLE = "toggle"


class StateVariable(StrictModel):
    variable_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    value_type: ValueType
    initial_value: Any


class GameplayEvent(StrictModel):
    event_id: str = Field(min_length=1)
    description: str = Field(min_length=1)


class Condition(StrictModel):
    condition_id: str = Field(min_length=1)
    variable_id: str = Field(min_length=1)
    operator: ConditionOperator
    value: Any


class Effect(StrictModel):
    effect_id: str = Field(min_length=1)
    variable_id: str = Field(min_length=1)
    operation: EffectOperation
    value: Any = None


class QuestNodeConfig(StrictModel):
    quest_id: str = Field(min_length=1)
    objective_key: str = Field(min_length=1)
    completion_event_id: str = Field(min_length=1)


class DialogueChoice(StrictModel):
    choice_id: str = Field(min_length=1)
    text_key: str = Field(min_length=1)
    target_node_id: str = Field(min_length=1)
    conditions: List[Condition] = Field(default_factory=list)


class DialogueNodeConfig(StrictModel):
    dialogue_id: str = Field(min_length=1)
    speaker_sceneops_id: str = Field(min_length=1)
    line_key: str = Field(min_length=1)
    choices: List[DialogueChoice] = Field(default_factory=list)


class GameplayNode(StrictModel):
    node_id: str = Field(min_length=1)
    kind: NodeKind
    label: str = Field(min_length=1)
    sceneops_ids: List[str] = Field(default_factory=list)
    conditions: List[Condition] = Field(default_factory=list)
    effects: List[Effect] = Field(default_factory=list)
    emitted_event_ids: List[str] = Field(default_factory=list)
    acceptance_criterion_ids: List[str] = Field(default_factory=list)
    quest: Optional[QuestNodeConfig] = None
    dialogue: Optional[DialogueNodeConfig] = None


class GameplayEdge(StrictModel):
    edge_id: str = Field(min_length=1)
    source_node_id: str = Field(min_length=1)
    target_node_id: str = Field(min_length=1)
    event_id: Optional[str] = None
    conditions: List[Condition] = Field(default_factory=list)
    effects: List[Effect] = Field(default_factory=list)
    emitted_event_ids: List[str] = Field(default_factory=list)


class InteractionRelationship(StrictModel):
    relationship_id: str = Field(min_length=1)
    source_sceneops_id: str = Field(min_length=1)
    target_sceneops_id: str = Field(min_length=1)
    relation_type: str = Field(min_length=1)
    template_id: str = Field(min_length=1)


class SceneObjectRef(StrictModel):
    sceneops_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    scene_id: str = Field(min_length=1)


class AcceptanceCriterion(StrictModel):
    criterion_id: str = Field(min_length=1)
    description: str = Field(min_length=1)


class GeneratedTestReference(StrictModel):
    test_id: str = Field(min_length=1)
    test_kind: Literal["edit_mode", "play_mode", "behavior"]
    target_node_ids: List[str] = Field(min_length=1)
    acceptance_criterion_ids: List[str] = Field(min_length=1)


class GameplayGraph(StrictModel):
    schema_version: Literal[1]
    graph_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    feature_spec_id: str = Field(min_length=1)
    version: int = Field(ge=1)
    mode: ExecutionMode
    state_variables: List[StateVariable] = Field(default_factory=list)
    events: List[GameplayEvent] = Field(default_factory=list)
    scene_objects: List[SceneObjectRef] = Field(default_factory=list)
    nodes: List[GameplayNode] = Field(min_length=1)
    edges: List[GameplayEdge] = Field(default_factory=list)
    relationships: List[InteractionRelationship] = Field(default_factory=list)
    acceptance_criteria: List[AcceptanceCriterion] = Field(default_factory=list)
    generated_tests: List[GeneratedTestReference] = Field(default_factory=list)


class ValidationIssue(StrictModel):
    code: str = Field(min_length=1)
    severity: Literal["error", "warning"]
    location: str = Field(min_length=1)
    message: str = Field(min_length=1)


class GraphValidationReport(StrictModel):
    graph_id: str
    graph_version: int
    valid: bool
    issues: List[ValidationIssue]
    mode: ExecutionMode = ExecutionMode.LIVE


class GraphDiffEntry(StrictModel):
    entity_type: str
    entity_id: str
    change: Literal["added", "removed", "modified"]
    previous: Optional[Dict[str, Any]] = None
    proposed: Optional[Dict[str, Any]] = None


class GameplayGraphDiff(StrictModel):
    graph_id: str
    base_version: int
    proposed_version: int
    entries: List[GraphDiffEntry]


class GeneratedTestCase(StrictModel):
    test_id: str
    test_kind: Literal["edit_mode", "play_mode", "behavior"]
    graph_id: str
    graph_version: int
    target_node_ids: List[str]
    acceptance_criterion_ids: List[str]
    assertions: List[str]


class GeneratedTestPlan(StrictModel):
    graph_id: str
    graph_version: int
    tests: List[GeneratedTestCase]
    mode: ExecutionMode = ExecutionMode.LIVE


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class CodeChangeProposal(StrictModel):
    proposal_id: str = Field(min_length=1)
    graph_id: str = Field(min_length=1)
    graph_version: int = Field(ge=1)
    base_version: str = Field(min_length=1)
    target_paths: List[str] = Field(min_length=1)
    target_sceneops_ids: List[str] = Field(default_factory=list)
    unified_diff: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    expected_result: str = Field(min_length=1)
    impact_scope: str = Field(min_length=1)
    risk: RiskLevel
    validation_plan: List[str] = Field(min_length=1)
    rollback_plan: List[str] = Field(min_length=1)
    mode: ExecutionMode


class ApprovalRequirement(StrictModel):
    permission: str
    reason: str


class ApprovalRecord(StrictModel):
    approver_id: str
    approved_at: str
    permission: str


class AdapterProvenance(StrictModel):
    adapter_id: str
    adapter_version: str
    command: str
    request_id: str
    correlation_id: str
    mode: ExecutionMode


class CompileTestResult(StrictModel):
    compile_succeeded: bool
    edit_mode_succeeded: bool
    play_mode_succeeded: bool
    logs: List[str]
    mode: ExecutionMode
    provenance: AdapterProvenance

    @property
    def succeeded(self) -> bool:
        return (
            self.compile_succeeded
            and self.edit_mode_succeeded
            and self.play_mode_succeeded
        )


class RollbackResult(StrictModel):
    succeeded: bool
    logs: List[str]
    mode: ExecutionMode
    provenance: AdapterProvenance


class AdapterHealth(StrictModel):
    adapter_id: str
    adapter_version: str
    status: Literal["online", "offline"]
    mode: ExecutionMode
    reason: Optional[str] = None


class UnityCodeCapability(StrictModel):
    adapter_id: str
    adapter_version: str
    allowed_commands: List[
        Literal[
            "unity.code_change.dry_run",
            "unity.code_change.apply",
            "unity.compile_and_test",
            "unity.code_change.rollback",
        ]
    ]
    allowed_project_roots: List[str]
    timeout_seconds: int = Field(gt=0)
    max_attempts: int = Field(ge=1)
    supports_cancellation: bool
    supports_progress: bool
    supports_rollback: bool
    mode: ExecutionMode


class ChangePreview(StrictModel):
    accepted: bool
    impacted_paths: List[str]
    summary: str
    mode: ExecutionMode
    rejection_code: Optional[str] = None
    provenance: AdapterProvenance


class ApplyReceipt(StrictModel):
    receipt_id: str
    rollback_token: str
    logs: List[str]
    mode: ExecutionMode
    provenance: AdapterProvenance


class ChangeSetStatus(str, Enum):
    WAITING_APPROVAL = "waiting_approval"
    APPROVED = "approved"
    APPLYING = "applying"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class CodeChangeSet(StrictModel):
    change_set_id: str
    proposal_id: str
    graph_id: str
    graph_version: int
    base_version: str
    target_integration: Literal["unity"] = "unity"
    target_objects: List[str]
    target_paths: List[str]
    previous_values: Dict[str, Any]
    proposed_values: Dict[str, Any]
    rationale: str
    expected_result: str
    impact_scope: str
    risk: RiskLevel
    validation_plan: List[str]
    rollback_plan: List[str]
    approval_requirements: List[ApprovalRequirement]
    approval: Optional[ApprovalRecord] = None
    status: ChangeSetStatus
    dry_run: Literal[True] = True
    mode: ExecutionMode
    execution_receipt_id: Optional[str] = None
    rollback_token: Optional[str] = None
    validation_result: Optional[CompileTestResult] = None
    rollback_result: Optional[RollbackResult] = None
    last_error: Optional[str] = None


class CompileTemplateRequest(StrictModel):
    template_id: str
    project_id: str
    feature_spec_id: str
    bindings: Dict[str, Any]
    mode: ExecutionMode = ExecutionMode.PLANNED


class ApproveChangeSetRequest(StrictModel):
    change_set: CodeChangeSet
    approver_id: str
    permissions: List[str]

    @model_validator(mode="after")
    def path_id_matches(self) -> "ApproveChangeSetRequest":
        if not self.change_set.change_set_id:
            raise ValueError("change_set_id is required")
        return self
