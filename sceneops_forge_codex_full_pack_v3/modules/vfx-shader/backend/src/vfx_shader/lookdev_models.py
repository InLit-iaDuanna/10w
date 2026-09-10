"""Network and durable document contracts for native material editing."""
from datetime import datetime, timezone
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


class LookdevModel(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class LookdevTarget(LookdevModel):
    asset_id: str = Field(min_length=1)
    asset_version: int = Field(ge=1)
    scene_instance_id: str | None = None
    sceneops_id: str | None = None
    material_slot: int | None = Field(default=None, ge=0)


class LookdevDocument(LookdevModel):
    schema_version: Literal[1] = 1
    id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    version: int = Field(default=0, ge=0)
    target: LookdevTarget
    state: dict[str, Any]
    runtime_module: str | None = None
    history: list[dict[str, Any]] = Field(default_factory=list)
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)


class SaveLookdevRequest(LookdevModel):
    document: LookdevDocument
    expected_version: int = Field(ge=0)


class LookdevProposalRequest(LookdevModel):
    turn_id: str | None = Field(default=None, min_length=1, max_length=120)
    document: LookdevDocument
    prompt: str = Field(min_length=1, max_length=16000)
    allow_lighting: bool = False
    model: str | None = None
    material_ids: list[str] = Field(default_factory=list)


class LookdevProposal(LookdevModel):
    turn_id: str
    operations: list[dict[str, Any]]
    summary: str
    base_version: int
    target: LookdevTarget
    state: dict[str, Any]
    status: Literal['applied', 'declined', 'noop'] = 'applied'
    execution_mode: Literal['live'] = 'live'


class ApplyLookdevRequest(LookdevModel):
    document_id: str
    document_version: int = Field(ge=1)
    expected_target_version: int = Field(ge=1)
    expected_scene_version: int | None = Field(default=None, ge=0)


class LookdevApplication(LookdevModel):
    document_id: str
    document_version: int
    asset_id: str
    asset_version: int
    scene_instance_id: str | None = None
    state: dict[str, Any]
    runtime_module: str
    scene_version: int | None = None
    needs_build: bool = True


class LookdevError(Exception):
    def __init__(self, code, message, status_code=409):
        self.code, self.message, self.status_code = code, message, status_code
        super().__init__(message)


class FinishLookdevTurnRequest(LookdevModel):
    status: Literal['applied', 'failed', 'cancelled', 'declined', 'noop']
    summary: str | None = Field(default=None, max_length=4000)


class LookdevTurn(LookdevModel):
    id: str
    prompt: str
    target: LookdevTarget
    summary: str = ''
    status: Literal['pending', 'proposed', 'applied', 'failed', 'cancelled', 'declined', 'noop'] = 'pending'
    created_at: str = Field(default_factory=utc_now)
    model: str = ''
    provider: str = ''


class ExportLookdevRequest(LookdevModel):
    document_id: str
    document_version: int = Field(ge=1)
    format: Literal['pbr-glb', 'shader-zip', 'luma-zip']


class LookdevExport(LookdevModel):
    id: str
    project_id: str
    document_id: str
    document_version: int
    format: Literal['pbr-glb', 'shader-zip', 'luma-zip']
    filename: str
    media_type: str
    size_bytes: int
    download_url: str
    warnings: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=utc_now)
