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
