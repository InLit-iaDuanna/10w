"""Additive contracts for the isolated, local Render Ops workbench."""

from typing import Dict, List, Literal

from pydantic import Field

from .schemas import (
    AovArtifact, PortableRecipeDefinition, RenderBrief, RenderComparison,
    RenderJob, RenderRecipe, RenderVariant, StrictModel, WritebackProposal,
)


CodeBuddyModel = Literal[
    "cli-default", "hy4-preview", "hy3", "hy3-x", "glm-5.3", "glm-5.3-flash",
    "glm-5.2", "glm-5.1", "glm-5v-turbo", "minimax-m3", "minimax-m2.7",
    "kimi-k3-1", "kimi-k2.7", "kimi-k2.6", "deepseek-v4-pro", "deepseek-v4-flash",
]


class LabRecipeInput(StrictModel):
    recipe_id: str = Field(min_length=1)
    prompt: str = Field(min_length=1, max_length=8000)
    negative_prompt: str = Field(default="不改变门体和固定相机", max_length=8000)
    seed: int = Field(default=42, ge=0, le=2147483647)
    samples: int = Field(default=64, ge=1, le=4096)
    geometry_version: str = Field(default="geometry-v8", min_length=1, max_length=80)
    camera_version: str = Field(default="camera-v4", min_length=1, max_length=80)
    ai_provider: Literal["codebuddycli"] = "codebuddycli"
    ai_model: CodeBuddyModel = "cli-default"


class LabImage(StrictModel):
    width: int
    height: int
    values: List[int]
    label: str
    execution_mode: Literal["mock"] = "mock"


class LabJob(StrictModel):
    job: RenderJob
    recipe: RenderRecipe
    input: LabRecipeInput
    aovs: List[AovArtifact] = Field(default_factory=list)
    variants: List[RenderVariant] = Field(default_factory=list)
    proposals: List[WritebackProposal] = Field(default_factory=list)
    images: Dict[str, LabImage] = Field(default_factory=dict)


class LabState(StrictModel):
    execution_mode: Literal["mock"] = "mock"
    brief: RenderBrief
    recipes: List[PortableRecipeDefinition]
    jobs: List[LabJob]
    activity: List[str]
    external_status: Literal["blocked"] = "blocked"
    external_reason: str = "本工作台只读取固定 mock 样本；真实渲染、AI 生成和工程写回未启用。"


class LabProposalInput(StrictModel):
    variant_id: str
    intensity: float = Field(ge=0, le=10000)
    rationale: str = Field(min_length=1, max_length=1000)


class LabCompareInput(StrictModel):
    before_id: str
    after_id: str


class LabComparison(StrictModel):
    comparison: RenderComparison
    before: LabImage
    after: LabImage
