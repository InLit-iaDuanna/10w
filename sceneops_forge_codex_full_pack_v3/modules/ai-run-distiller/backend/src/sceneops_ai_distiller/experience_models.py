"""Public experience contracts. Evidence status is not an execution permission."""
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix):
    return f"{prefix}_{uuid4().hex}"


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


EvidenceStatus = Literal["historical", "user_statement", "reported", "observed", "verified", "unknown"]
EntryStatus = Literal["unverified", "supported", "disputed", "superseded"]
ExperienceTopicId = Literal["build_delivery", "motion_interaction", "scene_animation",
                            "asset_performance", "runtime_lifecycle", "engineering_workflow"]


class ExperienceTopic(Model):
    id: ExperienceTopicId
    label: str
    description: str


class ExperienceEvidence(Model):
    id: str
    summary: str
    source_kind: str
    source_project_id: str | None = None
    source_ref: str
    verification: EvidenceStatus = "unknown"


class ExperienceEntry(Model):
    id: str
    project_id: str | None = None
    scope: Literal["project", "shared"]
    kind: Literal["fact", "case", "procedure"]
    memory_category: Literal["decision", "constraint", "fact"] | None = None
    title: str = Field(min_length=1, max_length=240)
    content: str = Field(min_length=1, max_length=16000)
    applicability: str = Field(default="", max_length=4000)
    topics: list[ExperienceTopicId] = Field(default_factory=list, max_length=3)
    domains: list[str] = Field(default_factory=list)
    platforms: list[str] = Field(default_factory=list)
    status: EntryStatus = "unverified"
    enabled: bool = True
    revision: int = 1
    evidence: list[ExperienceEvidence] = Field(default_factory=list)
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)


class ExperienceRevision(Model):
    entry: ExperienceEntry
    reason: str
    created_at: str


class ExperienceSettings(Model):
    use_enabled: bool = True
    learn_enabled: bool = True
    batch_call_limit: int = Field(default=2, ge=1, le=2)
    daily_call_limit: int = Field(default=20, ge=1)
    enabled_at: str = Field(default_factory=utc_now)
    timezone: Literal["Asia/Shanghai"] = "Asia/Shanghai"


class ExperienceSettingsUpdate(Model):
    use_enabled: bool | None = None
    learn_enabled: bool | None = None
    batch_call_limit: int | None = Field(default=None, ge=1, le=2)
    daily_call_limit: int | None = Field(default=None, ge=1)


class EntryUpdate(Model):
    memory_category: Literal["decision", "constraint", "fact"] | None = None
    expected_revision: int = Field(ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=240)
    content: str | None = Field(default=None, min_length=1, max_length=16000)
    applicability: str | None = Field(default=None, max_length=4000)
    topics: list[ExperienceTopicId] | None = Field(default=None, max_length=3)
    domains: list[str] | None = None
    platforms: list[str] | None = None
    status: EntryStatus | None = None
    enabled: bool | None = None


class RestoreRequest(Model):
    expected_revision: int = Field(ge=1)
    revision: int = Field(ge=1)


class LearnRequest(Model):
    project_id: str | None = None


class ContextItem(ExperienceEntry):
    truncated: bool = False


class ProjectMemoryReference(Model):
    id: str
    project_id: str
    title: str
    content: str
    category: Literal["decision", "constraint", "fact"]
    revision: int
    source_ref: str
    editable: bool = False


class ExperienceUse(Model):
    failure_reason: str | None = None
    persisted: bool = True
    id: str
    project_id: str | None = None
    use_key: str
    items: list[ContextItem] = Field(default_factory=list)
    origin_key: str | None = None
    project_memories: list[ProjectMemoryReference] = Field(default_factory=list)
    notice: str = "历史经验仅供参考，不改变本轮目标、权限或预算；提供不等于采用或验证。"
    truncated: bool = False
    created_at: str = Field(default_factory=utc_now)


class LearningBatch(Model):
    id: str
    project_id: str | None = None
    status: Literal["pending", "running", "completed", "failed", "budget_wait", "paused", "interrupted"]
    reason: str = ""
    provider: str | None = None
    model: str | None = None
    calls: int = 0
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)


class ExperienceStatus(Model):
    settings: ExperienceSettings
    day: str
    calls_used: int
    cost_usd: float | None = None
    pending_sources: int
    batches: list[LearningBatch]
    last_error: str | None = None


class ExperienceSource(Model):
    origin_key: str | None = None
    id: str
    kind: Literal["message", "action", "verification"]
    role: Literal["user", "assistant", "tool"]
    text: str
    created_at: str
    evidence_status: EvidenceStatus = "unknown"


class LearningChange(Model):
    operation: Literal["create", "revise"]
    entry_id: str | None = None
    expected_revision: int | None = None
    scope: Literal["project", "shared"] = "project"
    kind: Literal["fact", "case", "procedure"]
    title: str = Field(min_length=1, max_length=240)
    content: str = Field(min_length=1, max_length=16000)
    applicability: str = Field(default="", max_length=4000)
    topics: list[ExperienceTopicId] = Field(default_factory=list, max_length=3)
    domains: list[str] = Field(default_factory=list)
    platforms: list[str] = Field(default_factory=list)
    status: EntryStatus = "unverified"
    source_ids: list[str] = Field(min_length=1)
    reason: str = Field(min_length=1, max_length=2000)


class LearningProposal(Model):
    changes: list[LearningChange] = Field(default_factory=list, max_length=26)
    needs_review: bool = False
    review_reason: str = ""


class ProjectMemoryCollection(Model):
    project_id: str | None = None
    references: list[ProjectMemoryReference] = Field(default_factory=list)
    entries: list[ExperienceEntry] = Field(default_factory=list)


class MemoryProposal(Model):
    intent: Literal["explicit", "candidate"] = "explicit"
    source_quote: str = ""
    source_id: str
    title: str = Field(min_length=1, max_length=240)
    content: str = Field(min_length=1, max_length=16000)
    category: Literal["decision", "constraint", "fact"] = "fact"
    entry_id: str | None = None
    reference_id: str | None = None
    expected_revision: int | None = Field(default=None, ge=1)


class MemoryWrite(MemoryProposal):
    resolves_event_id: str | None = None
    request_id: str | None = Field(default=None, max_length=240)
    project_id: str | None = None
    origin_key: str


class MemoryUndo(Model):
    project_id: str | None = None
    expected_revision: int = Field(ge=1)


class MemoryEvent(Model):
    persisted: bool = True
    resolved_by: str | None = None
    proposal: MemoryWrite | None = None
    evidence_status: EvidenceStatus = "unknown"
    state: Literal["saved", "pending", "failed"] = "saved"
    reason: str = ""
    id: str = Field(default_factory=lambda: new_id("memoryevent"))
    project_id: str | None = None
    origin_keys: list[str] = Field(default_factory=list)
    operation: Literal["remember", "correct", "restore", "learn", "reference", "verify"]
    entry_id: str | None = None
    before: ExperienceEntry | None = None
    after: ExperienceEntry | None = None
    reference: ProjectMemoryReference | None = None
    previous_reference: ProjectMemoryReference | None = None
    source_ids: list[str] = Field(default_factory=list)
    batch_id: str | None = None
    created_at: str = Field(default_factory=utc_now)


class MemoryActivity(Model):
    origin_key: str
    events: list[MemoryEvent] = Field(default_factory=list)
    batches: list[LearningBatch] = Field(default_factory=list)
    pending: bool = False


class MemoryUsageRecord(Model):
    project_id: str | None = None
    use_key: str
    origin_key: str
    entry_id: str
    revision: int = Field(ge=1)
    source_id: str
    operation: Literal["reference", "verify"]
