"""Backend module-runtime contribution."""

from dataclasses import dataclass
from typing import List

from fastapi import APIRouter

from .jobs import JOBS, JobDefinition
from .router import router


@dataclass(frozen=True)
class BackendModuleContribution:
    manifest_id: str
    router: APIRouter
    jobs: List[JobDefinition]
    event_handlers: List[object]
    policy_gates: List[str]


backend_module_contribution = BackendModuleContribution(
    manifest_id="character-animation",
    router=router,
    jobs=JOBS,
    event_handlers=[],
    policy_gates=[
        "character.skeleton",
        "character.skin-weights",
        "animation.clip",
        "character.version-approval",
    ],
)
