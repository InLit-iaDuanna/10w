from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class JobDefinition:
    job_id: str
    description: str
    required_integrations: Tuple[str, ...] = ()


JOB_DEFINITIONS = (
    JobDefinition(
        job_id="logic.graph.validate",
        description="Run deterministic structural and semantic graph validation.",
    ),
    JobDefinition(
        job_id="logic.test_plan.generate",
        description="Generate Edit Mode, Play Mode, and behavior test references.",
    ),
    JobDefinition(
        job_id="logic.unity.code.validate",
        description="Dry-run an approved C# diff and compile/test it through Unity.",
        required_integrations=("unity",),
    ),
)
