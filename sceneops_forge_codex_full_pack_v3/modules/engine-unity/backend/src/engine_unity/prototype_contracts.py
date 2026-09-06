"""Bounded gameplay authoring and physical player input; no code or path fields."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PrototypeSpec(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    prototype_id: str = Field(pattern=r'^sobj_[A-Za-z0-9_-]{1,120}$')
    title: str = Field(min_length=1, max_length=80)
    seed: int = Field(default=1, ge=0, le=2147483647)
    arena_size: int = Field(default=20, ge=12, le=40)
    enemy_count: int = Field(default=4, ge=1, le=12)
    enemy_speed: float = Field(default=1.2, ge=.5, le=3)
    player_health: int = Field(default=100, ge=20, le=200)
    weapon_damage: int = Field(default=25, ge=5, le=100)
    enemy_health: int = Field(default=50, ge=10, le=150)
    enemy_damage: int = Field(default=10, ge=1, le=30)
    player_speed: float = Field(default=4, ge=2, le=8)
    fire_interval: float = Field(default=.25, ge=.1, le=1)
    goal_kills: int = Field(default=4, ge=1, le=30)


class PrototypeInput(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    move_x: float = Field(default=0, ge=-1, le=1)
    move_z: float = Field(default=0, ge=-1, le=1)
    yaw_delta: float = Field(default=0, ge=-180, le=180)
    pitch_delta: float = Field(default=0, ge=-90, le=90)
    fire: bool = False
    jump: bool = False
    duration_frames: int = Field(default=1, ge=1, le=120)
    width: int = Field(default=1280, ge=320, le=1920)
    height: int = Field(default=720, ge=240, le=1080)


class PrototypePlayPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    operation: Literal['enter', 'exit', 'reset', 'act', 'capture']
    input: PrototypeInput = Field(default_factory=PrototypeInput)
