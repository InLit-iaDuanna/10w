from __future__ import annotations

from typing import Dict, Optional, Sequence

from .adapters import ConceptGenerationAdapter
from .domain_helpers import (
    Clock,
    IdFactory,
    attach_reference_to_spec,
    new_variant,
    set_spec_status,
)
from .errors import ConceptLabError
from .events import ConceptEventEmitter
from .generation_schemas import (
    GeneratedViewArtifact,
    GenerationOutcome,
    GenerationRequest,
    GenerationRun,
)
from .jobs import transition_generation_run
from .repository import ConceptRepository
from .schemas import (
    ConceptReference,
    ConceptStatus,
    ExecutionMode,
    GenerationState,
    ReferenceKind,
)


class ConceptGenerationService:
    def __init__(
        self,
        repository: ConceptRepository,
        adapters: Sequence[ConceptGenerationAdapter],
        events: ConceptEventEmitter,
        id_factory: IdFactory,
        clock: Clock,
    ) -> None:
        self.repository = repository
        self.adapters: Dict[str, ConceptGenerationAdapter] = {
            adapter.adapter_id: adapter for adapter in adapters
        }
        self.events = events
        self.id_factory = id_factory
        self.clock = clock

    def generate_variant(
        self,
        request: GenerationRequest,
        *,
        actor_id: str,
        correlation_id: str,
        causation_id: str,
    ) -> GenerationOutcome:
        record = self.repository.get(request.concept_id)
        spec = record.spec_at(request.concept_version)
        now = self.clock()
        run = GenerationRun(
            run_id=self.id_factory("run"),
            request=request,
            state=GenerationState.QUEUED,
            execution_mode=request.execution_mode,
            created_at=now,
            updated_at=now,
        )
        record.generation_runs[run.run_id] = run
        adapter = self.adapters.get(request.adapter_id)
        block_reason = self._block_reason(adapter, request)
        if block_reason:
            run = transition_generation_run(
                run, GenerationState.BLOCKED, self.clock(), reason=block_reason
            )
            record.generation_runs[run.run_id] = run
            self.repository.save(request.concept_id, record)
            return GenerationOutcome(run=run)

        run = transition_generation_run(run, GenerationState.RUNNING, self.clock())
        record.generation_runs[run.run_id] = run
        self.repository.save(request.concept_id, record)
        try:
            plan = adapter.dry_run(request)  # type: ignore[union-attr]
            if plan.execution_mode != request.execution_mode:
                raise ConceptLabError(
                    "DRY_RUN_MODE_MISMATCH",
                    "Adapter dry-run mode differs from the request.",
                )
            output = adapter.execute(request)  # type: ignore[union-attr]
            if output.execution_mode != request.execution_mode:
                raise ConceptLabError(
                    "EXECUTION_MODE_MISMATCH",
                    "Adapter returned an execution mode different from the request.",
                )
            self._validate_output(request, output)
            references = self._record_references(
                record,
                spec,
                output.artifacts,
                output.execution_mode,
                output.generation,
            )
            variant = new_variant(
                spec,
                request.title,
                references,
                output.execution_mode,
                self.id_factory,
                self.clock,
                output.generation,
            )
            record.variants[variant.variant_id] = variant
            set_spec_status(record, spec.version, ConceptStatus.IN_REVIEW)
            run = transition_generation_run(
                run,
                GenerationState.SUCCEEDED,
                self.clock(),
                result_variant_id=variant.variant_id,
            )
        except Exception as error:
            reason = (
                error.message
                if isinstance(error, ConceptLabError)
                else "adapter execution failed with an unmapped error"
            )
            run = transition_generation_run(
                run, GenerationState.FAILED, self.clock(), reason=reason
            )
            record.generation_runs[run.run_id] = run
            self.repository.save(request.concept_id, record)
            return GenerationOutcome(run=run)

        record.generation_runs[run.run_id] = run
        self.repository.save(request.concept_id, record)
        self.events.variant_recorded(
            spec, variant, actor_id, correlation_id, causation_id
        )
        return GenerationOutcome(run=run, variant=variant)

    @staticmethod
    def _block_reason(
        adapter: Optional[ConceptGenerationAdapter], request: GenerationRequest
    ) -> Optional[str]:
        if request.execution_mode in {ExecutionMode.PLANNED, ExecutionMode.BLOCKED}:
            return "planned and blocked modes cannot execute generation"
        if adapter is None:
            return f"adapter {request.adapter_id} is not configured"
        health = adapter.health_check()
        if not health.available:
            return health.reason or f"adapter {request.adapter_id} is offline"
        if health.execution_mode != request.execution_mode:
            return "adapter health mode does not match requested execution mode"
        capabilities = adapter.capabilities()
        if request.model and request.model not in capabilities.models:
            return f"model {request.model} is not supported"
        requested = set(request.requested_views)
        if not requested.issubset(set(capabilities.supported_views)):
            return "one or more requested views are unsupported"
        if any(view.value == "turnaround" for view in requested):
            if not capabilities.supports_turnaround:
                return "turnaround generation is unsupported"
        return None

    def _record_references(self, record, spec, artifacts, mode, generation):
        references = []
        for artifact in artifacts:
            self._validate_artifact(spec.project_id, artifact, mode, generation)
            reference = ConceptReference(
                reference_id=self.id_factory("ref"),
                concept_id=spec.concept_id,
                concept_version=spec.version,
                title=artifact.title,
                view=artifact.view,
                artifact_uri=artifact.artifact_uri,
                source=artifact.source,
                provenance=artifact.provenance,
                imported_at=self.clock(),
            )
            record.references[reference.reference_id] = reference
            attach_reference_to_spec(record, reference.reference_id, spec.version)
            references.append(reference)
        return references

    @staticmethod
    def _validate_artifact(project_id, artifact, mode, generation) -> None:
        if artifact.source.kind != ReferenceKind.GENERATED:
            raise ConceptLabError(
                "GENERATED_REFERENCE_KIND_INVALID",
                "Generated output must declare kind=generated.",
            )
        if artifact.provenance.source_project_id != project_id:
            raise ConceptLabError(
                "PROVENANCE_PROJECT_MISMATCH",
                "Generated provenance must match the concept project.",
            )
        if artifact.provenance.execution_mode != mode:
            raise ConceptLabError(
                "PROVENANCE_MODE_MISMATCH",
                "Generated artifact provenance must match the adapter output mode.",
            )
        if artifact.provenance.approval_state != "unreviewed":
            raise ConceptLabError(
                "GENERATED_ARTIFACT_PREAPPROVED",
                "A generated concept artifact cannot bypass human review.",
            )
        if artifact.provenance.ai is None:
            raise ConceptLabError(
                "AI_PROVENANCE_REQUIRED",
                "Generated artifacts must preserve AI prompt, seed, model, and workflow metadata.",
            )
        if artifact.provenance.ai != generation:
            raise ConceptLabError(
                "AI_PROVENANCE_MISMATCH",
                "Generated artifact AI provenance differs from the executed generation metadata.",
            )

    @staticmethod
    def _validate_output(request, output) -> None:
        views = [artifact.view for artifact in output.artifacts]
        if len(set(views)) != len(views):
            raise ConceptLabError(
                "DUPLICATE_GENERATED_VIEW",
                "A generation output may contain each view only once.",
            )
        missing = set(request.requested_views) - set(views)
        if missing:
            raise ConceptLabError(
                "GENERATED_VIEWS_MISSING",
                "Generation output omitted one or more requested views.",
                details={"missing_views": sorted(view.value for view in missing)},
            )
