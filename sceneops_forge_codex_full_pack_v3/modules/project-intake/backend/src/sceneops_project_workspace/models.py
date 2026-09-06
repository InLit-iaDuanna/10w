"""Local workspace records are drafts, never production execution evidence."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue

ModuleId = Literal["project-planning", "concept-assets", "character-animation", "world-logic",
    "ui-audio-vfx", "render-ops", "unity-build", "version-review", "ai-playtest", "integration-ops"]
SampleId = Literal["remember-home", "warehouse-escape"]


class WorkspaceModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProjectCreate(WorkspaceModel):
    name: str = Field(min_length=1, max_length=160, pattern=r".*\S.*")


class Project(WorkspaceModel):
    project_id: str
    name: str
    mode: Literal["planned"] = "planned"
    created_at: datetime
    updated_at: datetime


class ProjectList(WorkspaceModel):
    projects: list[Project]


class FolderEntry(WorkspaceModel):
    name: str
    path: str
    kind: Literal["directory", "symlink"]
    selectable: bool


class FolderListing(WorkspaceModel):
    path: str
    parent_path: str | None
    entries: list[FolderEntry]


class FolderProjectCreate(WorkspaceModel):
    parent_path: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=160, pattern=r".*\S.*")


class FolderProject(WorkspaceModel):
    project_id: str
    name: str
    root_path: str
    project_kind: Literal["sceneops_created", "existing_unadopted", "legacy"] = "legacy"
    root_available: bool = True


class ProjectIdentity(WorkspaceModel):
    schema_version: Literal[1] = 1
    project_id: str = Field(pattern=r"^prj_[A-Za-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=160, pattern=r".*\S.*")
    created_at: datetime
    copied_from_project_id: str | None = Field(default=None, pattern=r"^prj_[A-Za-z0-9_-]+$")


class FolderProjectInspect(WorkspaceModel):
    path: str = Field(min_length=1)


class FolderProjectIdentityInspection(WorkspaceModel):
    path: str
    status: Literal["registered", "recoverable", "move_candidate", "identity_conflict", "missing_identity"]
    project_id: str | None = None
    name: str | None = None
    registered_root_path: str | None = None
    registered_root_exists: bool | None = None
    allowed_resolutions: list[Literal["restore", "move", "copy"]] = Field(default_factory=list)
    message: str


class FolderProjectRecover(WorkspaceModel):
    path: str = Field(min_length=1)
    resolution: Literal["restore", "move", "copy"]


class FolderProjectList(WorkspaceModel):
    projects: list[FolderProject]


class StructuredDesignArtifact(WorkspaceModel):
    project_id: str
    kind: Literal["draft", "snapshot"]
    version: int | None = Field(default=None, ge=1)
    path: str


class ModuleDocument(WorkspaceModel):
    project_id: str
    module_id: ModuleId
    revision: int = Field(ge=0)
    sample_id: SampleId | None = None
    payload: dict[str, JsonValue] = Field(default_factory=dict)


class DocumentSave(WorkspaceModel):
    expected_revision: int = Field(ge=0)
    payload: dict[str, JsonValue]


class SampleImport(WorkspaceModel):
    sample_id: SampleId
    expected_revision: int = Field(default=0, ge=0)


class WorkbenchRegistration(WorkspaceModel):
    module_id: str
    title: str
    mode: Literal["planned"] = "planned"


class ModuleList(WorkspaceModel):
    modules: list[WorkbenchRegistration]


class WorkspaceError(WorkspaceModel):
    code: str
    message: str
    retryable: bool = False
