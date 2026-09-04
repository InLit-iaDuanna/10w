from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from .jobs import GENERATION_JOB_DEFINITION


@dataclass(frozen=True)
class BackendModuleContribution:
    manifest_id: str
    router_factory: str
    jobs: List[Dict[str, Any]]
    event_types: List[str]
    policy_gates: List[str]


module_contribution = BackendModuleContribution(
    manifest_id="concept-lab",
    router_factory="concept_lab.create_router",
    jobs=[GENERATION_JOB_DEFINITION],
    event_types=[
        "concept.version.created@1",
        "concept.variant.recorded@1",
        "concept.variant.reviewed@1",
        "concept.asset_spec_draft.compiled@1",
    ],
    policy_gates=["concept.reference.permission", "concept.required_views"],
)
