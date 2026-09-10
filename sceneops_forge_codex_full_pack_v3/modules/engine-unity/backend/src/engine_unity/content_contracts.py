"""Typed fields for the managed FBX/door editing roundtrip."""
from typing import Annotated, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator

Identifier = Annotated[str, Field(pattern=r'^[A-Za-z0-9_-]{1,120}$')]

class ContentNodes(BaseModel):
    model_config = ConfigDict(extra='forbid')
    frame: Identifier
    leaf: Identifier
    hinge: Identifier

    @model_validator(mode='after')
    def distinct(self):
        if len({self.frame, self.leaf, self.hinge}) != 3:
            raise ValueError('Frame, leaf and hinge require distinct source node identities.')
        return self

class ContentValues(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    position: tuple[float, float, float]
    interaction_distance: float = Field(ge=.2, le=10)
    requires_key: bool

class ContentEdit(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    instance_id: Identifier
    expected: ContentValues
    position: Optional[tuple[float, float, float]] = None
    interaction_distance: Optional[float] = Field(default=None, ge=.2, le=10)
    requires_key: Optional[bool] = None

    @model_validator(mode='after')
    def changed(self):
        if self.position is None and self.interaction_distance is None and self.requires_key is None:
            raise ValueError('At least one editable field is required.')
        return self

class ContentInput(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    move_x: float = Field(default=0, ge=-1, le=1)
    move_z: float = Field(default=0, ge=-1, le=1)
    interact: bool = False
    duration_frames: int = Field(default=1, ge=1, le=120)

class ContentPlay(BaseModel):
    model_config = ConfigDict(extra='forbid')
    operation: Literal['enter', 'exit', 'act']
    input: ContentInput = Field(default_factory=ContentInput)
