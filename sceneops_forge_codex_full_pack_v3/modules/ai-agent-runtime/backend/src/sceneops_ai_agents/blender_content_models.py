"""Typed native asset edits: callers select identities, never paths or programs."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from .demo_workbench_models import DemoEditTarget

class NativeModel(BaseModel):
    model_config = ConfigDict(extra='forbid')

class BlenderBeginInput(NativeModel):
    asset_id: str
    expected_version: int = Field(ge=1)
    owner: Literal['agent', 'manual'] = 'agent'

class BlenderNodeEdit(NativeModel):
    node_id: str
    dimensions_m: tuple[float, float, float] | None = None
    base_color: tuple[float, float, float, float] | None = None

    @model_validator(mode='after')
    def bounded(self):
        import math
        if self.dimensions_m is None and self.base_color is None:
            raise ValueError('提交尺寸或材质修改。')
        if self.dimensions_m and not all(math.isfinite(v) and .001 <= v <= 100 for v in self.dimensions_m):
            raise ValueError('尺寸必须在 0.001–100 米之间。')
        if self.base_color and not all(math.isfinite(v) and 0 <= v <= 1 for v in self.base_color):
            raise ValueError('颜色必须在 0–1 之间。')
        return self

class BlenderEditInput(NativeModel):
    asset_id: str
    candidate_id: str = Field(pattern=r'^blend_[a-f0-9]{32}$')
    edits: list[BlenderNodeEdit] = Field(min_length=1, max_length=32)

class BlenderPublishInput(NativeModel):
    asset_id: str
    candidate_id: str = Field(pattern=r'^blend_[a-f0-9]{32}$')
    expected_scene_version: int = Field(ge=0)
    object_ids: list[str] | None = None
    apply_to_scene: bool = True

class BlenderManualRequest(NativeModel):
    request_id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,120}$')
    target: DemoEditTarget
    operation: Literal['begin', 'edit', 'publish', 'reconcile', 'close_candidate']
    edits: list[BlenderNodeEdit] = Field(default_factory=list)
    apply_to_scene: bool = True
    candidate_id: str | None = None
