"""Product-owned selection and finite Unity editing requests."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

class UnityContentModel(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)

class PrepareUnityAssetTask(UnityContentModel):
    asset_id: str = Field(min_length=1, max_length=120)
    source_version: int = Field(ge=1)

class UnityInstanceValues(UnityContentModel):
    position: tuple[float,float,float]
    interaction_distance: float = Field(ge=.2, le=10)
    requires_key: bool

class UnityContentInstance(UnityInstanceValues):
    instance_id: str

class UnityContentSnapshot(UnityContentModel):
    task_id: str
    project_id: str
    workspace_id: str
    source_asset_id: str
    available_source_version: int
    imported_source_version: int = 0
    editor_version: str = '2022.3.62f3c1'
    project_root: str
    scene_path: str | None = None
    mode: Literal['planned','live','cached'] = 'planned'
    status: str = 'not_started'
    dirty: bool = False
    playing: bool = False
    compiling: bool = False
    instances: list[UnityContentInstance] = Field(default_factory=list)
    readback: dict[str,JsonValue] = Field(default_factory=dict)
    notice: str | None = None

class UnitySourceInput(UnityContentModel):
    source_version: int = Field(ge=1)

class UnityImportInput(UnitySourceInput):
    expected_source_version: int = Field(ge=0)

class UnityEditInput(UnityContentModel):
    instance_id: str
    expected: UnityInstanceValues
    position: tuple[float,float,float] | None = None
    interaction_distance: float | None = Field(default=None,ge=.2,le=10)
    requires_key: bool | None = None

    @model_validator(mode='after')
    def has_change(self):
        if self.position is None and self.interaction_distance is None and self.requires_key is None:
            raise ValueError('请指定要修改的实例字段。')
        return self

class UnityFocusInput(UnityContentModel):
    instance_id: str

class UnitySaveInput(UnityContentModel):
    reopen: bool = False

class UnityPlayInput(UnityContentModel):
    operation: Literal['enter','exit','act']
    move_x: float = Field(default=0,ge=-1,le=1)
    move_z: float = Field(default=0,ge=-1,le=1)
    interact: bool = False
    duration_frames: int = Field(default=1,ge=1,le=120)

class UnityManualRequest(UnityContentModel):
    request_id: str = Field(pattern=r'^[A-Za-z0-9_-]{8,96}$')
    operation: Literal['import','inspect','edit','focus','save','reopen','play','stop','act','agent','reconcile','renew']
    source_version: int | None = Field(default=None,ge=1)
    instance_id: str | None = None
    expected: UnityInstanceValues | None = None
    position: tuple[float,float,float] | None = None
    interaction_distance: float | None = Field(default=None,ge=.2,le=10)
    requires_key: bool | None = None
    move_x: float = Field(default=0,ge=-1,le=1)
    move_z: float = Field(default=0,ge=-1,le=1)
    interact: bool = False
    duration_frames: int = Field(default=1,ge=1,le=120)
    goal: str | None = Field(default=None,min_length=1,max_length=4000)

    @model_validator(mode='after')
    def required_fields(self):
        if self.operation=='import' and self.source_version is None:
            raise ValueError('请选择资产版本。')
        if self.operation in ('edit','focus') and not self.instance_id:
            raise ValueError('请选择实际 Unity 实例。')
        if self.operation=='edit' and self.expected is None:
            raise ValueError('请先读取当前实例值。')
        if self.operation=='edit':
            UnityEditInput(instance_id=self.instance_id,expected=self.expected,position=self.position,
                interaction_distance=self.interaction_distance,requires_key=self.requires_key)
        if self.operation=='agent' and not self.goal:
            raise ValueError('请输入 Agent 修改目标。')
        if self.operation=='act':
            UnityPlayInput(operation='act',move_x=self.move_x,move_z=self.move_z,
                interact=self.interact,duration_frames=self.duration_frames)
        return self
