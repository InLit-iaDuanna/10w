"""Public contracts for local playable exports (not release approval)."""
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field

ExportPlatform = Literal['android', 'mac-arm64', 'mac-x64', 'win-x64']
ExportStatus = Literal['pending', 'queued', 'running', 'succeeded', 'failed', 'cancelled', 'interrupted', 'blocked']

class ExportSettings(BaseModel):
    model_config = ConfigDict(extra='forbid')
    app_name: str = Field(default='', max_length=120)
    app_id: str = Field(default='', max_length=160, pattern=r'^$|^[a-zA-Z][a-zA-Z0-9_]*(\.[a-zA-Z][a-zA-Z0-9_]*)+$')
    orientation: Literal['landscape', 'portrait'] = 'landscape'
    allow_dependency_install: bool = False

class CreateExportRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    execution_mode: Literal['native', 'fixed'] = 'fixed'
    accept_full_access: bool = False
    platforms: list[ExportPlatform] = Field(min_length=1, max_length=4)
    settings: ExportSettings = Field(default_factory=ExportSettings)

class ExportConsentRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    allow_dependency_install: bool

class ExportMessageRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    content: str = Field(min_length=1, max_length=16000)
    execution_mode: Literal['native', 'discuss'] = 'discuss'
    accept_full_access: bool = False
    provider_id: Optional[str] = None
    model: Optional[str] = None

class ExportVerificationRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    status: Literal['pending', 'passed', 'failed']
    notes: str = Field(default='', max_length=4000)
    device: str = Field(default='', max_length=200)
    attempt_id: str

class ExportLog(BaseModel):
    timestamp: str
    stage: str
    message: str

class ExportArtifact(BaseModel):
    id: str
    name: str
    size: int
    download_url: str

class ExportAttempt(BaseModel):
    id: str
    number: int
    status: ExportStatus
    settings: ExportSettings = Field(default_factory=ExportSettings)
    stage: str = 'queued'
    cancel_requested: bool = False
    logs: list[ExportLog] = Field(default_factory=list)
    error: Optional[str] = None
    artifacts: list[ExportArtifact] = Field(default_factory=list)
    started_at: str
    finished_at: Optional[str] = None

class ExportPlatformRun(BaseModel):
    platform: ExportPlatform
    status: ExportStatus = 'queued'
    attempts: list[ExportAttempt] = Field(default_factory=list)
    verification: Literal['pending', 'passed', 'failed'] = 'pending'
    verification_notes: str = ''
    verification_device: str = ''
    verification_attempt_id: Optional[str] = None

class ExportMessage(BaseModel):
    id: str
    role: Literal['user', 'assistant', 'system']
    content: str
    created_at: str
    agent_task_id: Optional[str] = None
    provider_id: Optional[str] = None
    model: Optional[str] = None
    usage: dict = Field(default_factory=dict)
    proposed_development: Optional[str] = None
    invocation: dict = Field(default_factory=dict)

class ExportNativeRun(BaseModel):
    id: str
    agent_task_id: Optional[str] = None
    status: ExportStatus = 'queued'
    logs: list[ExportLog] = Field(default_factory=list)
    error: Optional[str] = None
    cancel_requested: bool = False
    started_at: str
    finished_at: Optional[str] = None

class ExportTask(BaseModel):
    id: str
    project_id: str
    source_version: str
    previous_task_id: Optional[str] = None
    settings: ExportSettings
    created_at: str
    updated_at: str
    mode: Literal['live', 'mock', 'blocked', 'planned'] = 'live'
    platforms: list[ExportPlatformRun]
    messages: list[ExportMessage] = Field(default_factory=list)
    native_runs: list[ExportNativeRun] = Field(default_factory=list)
    revision: int = 0
