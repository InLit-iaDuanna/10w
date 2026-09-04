"""Module-local job definitions for registration by a future root runtime."""

from dataclasses import dataclass
from typing import Callable

from .models import OperationResult, PreviewPlan, PublicationRequest, VfxShaderRecipe
from .service import VfxShaderService, plan_preview


@dataclass(frozen=True)
class JobDefinition:
    id: str
    input_type: type
    result_type: type
    run: Callable[..., object]


def publication_job(service: VfxShaderService) -> JobDefinition:
    return JobDefinition("vfx.recipe.publish", PublicationRequest, OperationResult, service.publish)


PREVIEW_JOB = JobDefinition("vfx.preview.plan", VfxShaderRecipe, PreviewPlan, plan_preview)
