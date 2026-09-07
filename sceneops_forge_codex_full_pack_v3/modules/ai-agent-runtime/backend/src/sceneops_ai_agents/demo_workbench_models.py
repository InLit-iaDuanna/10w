"""Small public contracts for navigating existing Demo sources and targeting edits."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from asset_library import DoorRecipe, ProjectAssetEntry
from world_composer import EnvironmentObject, EnvironmentTransform


class DemoEditTarget(BaseModel):
    model_config = ConfigDict(extra='forbid')
    project_id: str
    workspace_id: str
    kind: Literal['asset', 'instance', 'behavior', 'source']
    id: str
    source_version: int = Field(ge=0)
    viewed_candidate_id: str | None = None
    expected_scene_version: int | None = Field(default=None, ge=0)
    expected_source_content: str | None = Field(default=None, max_length=65536)


class DemoSourceEntry(BaseModel):
    id: str
    latest_write_request_id: str
    path: str
    content: str
    source_version: int
    edit_mode: Literal['source-agent'] = 'source-agent'


class DemoContentIndex(BaseModel):
    project_id: str
    workspace_id: str
    scene_version: int
    assets: list[ProjectAssetEntry]
    instances: list[EnvironmentObject]
    sources: list[DemoSourceEntry]
    unbuilt_changes: bool
    source_notice: str


class DemoContentSave(BaseModel):
    model_config = ConfigDict(extra='forbid')
    target: DemoEditTarget
    recipe: DoorRecipe | None = None
    transform: EnvironmentTransform | None = None
    interaction_distance_m: float | None = Field(default=None, gt=0, le=20)
    open_angle_deg: float | None = Field(default=None, ge=-180, le=180)
    required_key_asset_id: str | None = None

    @model_validator(mode='after')
    def appropriate_fields(self):
        permitted = {'asset': {'recipe'}, 'instance': {'transform'},
            'behavior': {'interaction_distance_m', 'open_angle_deg', 'required_key_asset_id'}, 'source': set()}
        submitted = self.model_fields_set - {'target'}
        if submitted - permitted[self.target.kind]:
            raise ValueError('编辑参数与选中内容类型不一致。')
        return self


class DemoContentSaved(BaseModel):
    content: DemoContentIndex
    affected_instance_ids: list[str]
    notice: str


class DemoPlayRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    candidate_id: str


class DemoPlaySession(BaseModel):
    candidate_id: str
    sequence: int
    preview_url: str


class DemoContinuationAuthorizationRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,120}$')
