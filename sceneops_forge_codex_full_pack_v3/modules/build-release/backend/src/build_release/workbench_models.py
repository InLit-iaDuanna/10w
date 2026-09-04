"""Network models for local Unity/build proposal composition."""
from typing import Literal
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from engine_unity import ChangeSet, UnityWorkbenchSnapshot
from .models_build import BuildMatrix, BuildRun, BuildManifest
from .models_release import ReleaseCandidate, ReleaseGate

class ProposalInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=0)
    title: str = Field(min_length=1, max_length=160)
    notes: str = Field(max_length=4000)
    target: Literal["local", "judge"]
    change_set: ChangeSet

class LocalProposal(ProposalInput):
    proposal_id: str
    revision: int
    mode: Literal["planned"] = "planned"
    approval_state: Literal["pending"] = "pending"
    updated_at: datetime

class BuildScenario(BaseModel):
    slug: str
    mode: Literal["mock"] = "mock"
    matrix: BuildMatrix
    runs: list[BuildRun]
    manifests: list[BuildManifest]
    gates: list[ReleaseGate]
    candidate: ReleaseCandidate
    proposal: LocalProposal

class WorkbenchSnapshot(BaseModel):
    unity: UnityWorkbenchSnapshot
    scenarios: list[BuildScenario]
    external_mode: Literal["blocked"] = "blocked"
    external_reason: str = "未配置可信审批、Unity runner 与部署适配器；只能保存本地提案。"
