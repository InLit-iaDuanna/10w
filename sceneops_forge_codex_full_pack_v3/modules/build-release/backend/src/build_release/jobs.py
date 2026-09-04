"""Static job contribution metadata consumed by the module runtime."""

from typing import List

from pydantic import BaseModel, ConfigDict


class JobDefinition(BaseModel):
    model_config = ConfigDict(frozen=True)
    job_id: str
    input_model: str
    output_model: str
    cancellable: bool
    retryable: bool


JOB_DEFINITIONS: List[JobDefinition] = [
    JobDefinition(
        job_id="build.manifest.verify",
        input_model="RecordBuildRequest",
        output_model="BuildManifest",
        cancellable=False,
        retryable=False,
    ),
    JobDefinition(
        job_id="release.candidate.assemble",
        input_model="CreateCandidateRequest",
        output_model="ReleaseCandidate",
        cancellable=False,
        retryable=False,
    ),
    JobDefinition(
        job_id="release.deployment.publish",
        input_model="DeployRequest",
        output_model="Deployment",
        cancellable=True,
        retryable=True,
    ),
    JobDefinition(
        job_id="release.rollback.execute",
        input_model="ExecuteRollbackRequest",
        output_model="RollbackPlan",
        cancellable=True,
        retryable=True,
    ),
]
