"""Static job contributions consumed by the module runtime."""

from typing import List, Literal

from pydantic import Field

from .common import StrictModel


class JobDefinition(StrictModel):
    id: str = Field(min_length=3)
    title: str
    input_model: str
    result_model: str
    cancellable: bool
    retry_policy: Literal["never", "safe_once"]
    resumable: bool


JOBS: List[JobDefinition] = [
    JobDefinition(
        id="character.inspect",
        title="检查角色、Rig、Skin 与动画片段",
        input_model="CharacterInspectionRequest",
        result_model="CharacterInspectionResult",
        cancellable=False,
        retry_policy="never",
        resumable=False,
    ),
    JobDefinition(
        id="animation.preview.capture",
        title="生成固定相机动画预览",
        input_model="PreviewCaptureRequest",
        result_model="PreviewArtifact",
        cancellable=True,
        retry_policy="safe_once",
        resumable=True,
    ),
    JobDefinition(
        id="character.unity.map",
        title="应用已批准的 Unity 角色映射",
        input_model="UnityMappingExecutionRequest",
        result_model="UnityCharacterMapping",
        cancellable=True,
        retry_policy="safe_once",
        resumable=True,
    ),
]
