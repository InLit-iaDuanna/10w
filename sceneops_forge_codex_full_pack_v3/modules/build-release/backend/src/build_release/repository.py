"""Module-owned repository contract and deterministic in-memory implementation."""

from __future__ import annotations

from contextlib import contextmanager
from threading import Lock
from typing import Dict, List, Optional

from .errors import ConflictError, NotFoundError
from .models_build import BuildManifest, BuildMatrix, BuildRun
from .models_release import (
    Deployment,
    FeedbackLink,
    PatchNote,
    ReleaseCandidate,
    RollbackPlan,
)


class InMemoryReleaseRepository:
    """An isolated repository used by tests and local composition.

    Production persistence is intentionally supplied by the application
    composition root; this class does not pretend to be durable.
    """

    def __init__(self) -> None:
        self._matrices: Dict[str, BuildMatrix] = {}
        self._runs: Dict[str, BuildRun] = {}
        self._manifests: Dict[str, BuildManifest] = {}
        self._candidates: Dict[str, ReleaseCandidate] = {}
        self._deployments: Dict[str, Deployment] = {}
        self._deployment_keys: Dict[str, str] = {}
        self._patch_notes: Dict[str, PatchNote] = {}
        self._rollback_plans: Dict[str, RollbackPlan] = {}
        self._feedback_links: Dict[str, FeedbackLink] = {}
        self._operation_lock_registry = Lock()
        self._operation_locks: Dict[str, Lock] = {}

    def add_build(self, matrix: BuildMatrix, run: BuildRun, manifest: BuildManifest) -> None:
        existing_matrix = self._matrices.get(matrix.matrix_id)
        if existing_matrix is not None and existing_matrix != matrix:
            raise ConflictError(
                "BuildMatrix already exists with different immutable content.",
                details={"entity": "BuildMatrix", "id": matrix.matrix_id},
            )
        for entity, entity_id, collection in (
            ("BuildRun", run.build_run_id, self._runs),
            ("BuildManifest", manifest.manifest_id, self._manifests),
        ):
            if entity_id in collection:
                raise ConflictError(
                    f"{entity} already exists.",
                    details={"entity": entity, "id": entity_id},
                )
        if existing_matrix is None:
            self._matrices[matrix.matrix_id] = matrix.model_copy(deep=True)
        self._runs[run.build_run_id] = run.model_copy(deep=True)
        self._manifests[manifest.manifest_id] = manifest.model_copy(deep=True)

    def get_manifest(self, manifest_id: str) -> BuildManifest:
        return self._get(self._manifests, "BuildManifest", manifest_id)

    def add_candidate(self, candidate: ReleaseCandidate) -> None:
        self._add(self._candidates, "ReleaseCandidate", candidate.candidate_id, candidate)

    def save_candidate(self, candidate: ReleaseCandidate) -> None:
        self._require(self._candidates, "ReleaseCandidate", candidate.candidate_id)
        self._candidates[candidate.candidate_id] = candidate.model_copy(deep=True)

    def get_candidate(self, candidate_id: str) -> ReleaseCandidate:
        return self._get(self._candidates, "ReleaseCandidate", candidate_id)

    def add_patch_note(self, patch_note: PatchNote) -> None:
        self._add(self._patch_notes, "PatchNote", patch_note.patch_note_id, patch_note)

    def save_patch_note(self, patch_note: PatchNote) -> None:
        self._require(self._patch_notes, "PatchNote", patch_note.patch_note_id)
        self._patch_notes[patch_note.patch_note_id] = patch_note.model_copy(deep=True)

    def get_patch_note(self, patch_note_id: str) -> PatchNote:
        return self._get(self._patch_notes, "PatchNote", patch_note_id)

    def deployment_for_key(self, idempotency_key: str) -> Optional[Deployment]:
        deployment_id = self._deployment_keys.get(idempotency_key)
        if deployment_id is None:
            return None
        return self.get_deployment(deployment_id)

    def add_deployment(self, deployment: Deployment) -> None:
        existing_id = self._deployment_keys.get(deployment.idempotency_key)
        if existing_id is not None and existing_id != deployment.deployment_id:
            raise ConflictError(
                "Deployment idempotency key already belongs to another operation.",
                details={"idempotency_key": deployment.idempotency_key},
            )
        self._add(self._deployments, "Deployment", deployment.deployment_id, deployment)
        self._deployment_keys[deployment.idempotency_key] = deployment.deployment_id

    @contextmanager
    def deployment_operation(self, deployment_id: str, idempotency_key: str):
        keys = sorted((f"deployment:{deployment_id}", f"key:{idempotency_key}"))
        with self._operation_lock_registry:
            locks = [self._operation_locks.setdefault(key, Lock()) for key in keys]
        for lock in locks:
            lock.acquire()
        try:
            yield
        finally:
            for lock in reversed(locks):
                lock.release()

    def assert_deployment_slot(
        self, deployment_id: str, idempotency_key: str
    ) -> None:
        if deployment_id in self._deployments:
            raise ConflictError(
                "Deployment ID already exists.",
                details={"deployment_id": deployment_id},
            )
        existing_id = self._deployment_keys.get(idempotency_key)
        if existing_id is not None:
            raise ConflictError(
                "Deployment idempotency key already belongs to another operation.",
                details={
                    "idempotency_key": idempotency_key,
                    "deployment_id": existing_id,
                },
            )

    def commit_new_deployment(
        self,
        deployment: Deployment,
        candidate: Optional[ReleaseCandidate] = None,
    ) -> None:
        deployments = dict(self._deployments)
        deployment_keys = dict(self._deployment_keys)
        candidates = dict(self._candidates)
        try:
            self.add_deployment(deployment)
            if candidate is not None:
                self.save_candidate(candidate)
        except Exception:
            self._deployments = deployments
            self._deployment_keys = deployment_keys
            self._candidates = candidates
            raise

    def commit_deployment_update(
        self,
        deployment: Deployment,
        candidate: Optional[ReleaseCandidate] = None,
    ) -> None:
        deployments = dict(self._deployments)
        candidates = dict(self._candidates)
        try:
            self.save_deployment(deployment)
            if candidate is not None:
                self.save_candidate(candidate)
        except Exception:
            self._deployments = deployments
            self._candidates = candidates
            raise

    def save_deployment(self, deployment: Deployment) -> None:
        self._require(self._deployments, "Deployment", deployment.deployment_id)
        self._deployments[deployment.deployment_id] = deployment.model_copy(deep=True)

    def get_deployment(self, deployment_id: str) -> Deployment:
        return self._get(self._deployments, "Deployment", deployment_id)

    def list_deployments(self) -> List[Deployment]:
        return [item.model_copy(deep=True) for item in self._deployments.values()]

    def add_rollback_plan(self, plan: RollbackPlan) -> None:
        self._add(self._rollback_plans, "RollbackPlan", plan.rollback_plan_id, plan)

    def save_rollback_plan(self, plan: RollbackPlan) -> None:
        self._require(self._rollback_plans, "RollbackPlan", plan.rollback_plan_id)
        self._rollback_plans[plan.rollback_plan_id] = plan.model_copy(deep=True)

    def commit_rollback(
        self,
        activation: Deployment,
        current: Deployment,
        current_candidate: ReleaseCandidate,
        target_candidate: ReleaseCandidate,
        plan: RollbackPlan,
    ) -> None:
        deployments = dict(self._deployments)
        deployment_keys = dict(self._deployment_keys)
        candidates = dict(self._candidates)
        rollback_plans = dict(self._rollback_plans)
        try:
            self.add_deployment(activation)
            self.save_deployment(current)
            self.save_candidate(current_candidate)
            self.save_candidate(target_candidate)
            self.save_rollback_plan(plan)
        except Exception:
            self._deployments = deployments
            self._deployment_keys = deployment_keys
            self._candidates = candidates
            self._rollback_plans = rollback_plans
            raise

    def get_rollback_plan(self, plan_id: str) -> RollbackPlan:
        return self._get(self._rollback_plans, "RollbackPlan", plan_id)

    def add_feedback_link(self, link: FeedbackLink) -> None:
        self._add(self._feedback_links, "FeedbackLink", link.feedback_link_id, link)

    @staticmethod
    def _require(collection: Dict[str, object], entity: str, entity_id: str) -> None:
        if entity_id not in collection:
            raise NotFoundError(entity, entity_id)

    @classmethod
    def _get(cls, collection: Dict[str, object], entity: str, entity_id: str):
        cls._require(collection, entity, entity_id)
        return collection[entity_id].model_copy(deep=True)

    @staticmethod
    def _add(collection: Dict[str, object], entity: str, entity_id: str, value: object) -> None:
        if entity_id in collection:
            raise ConflictError(
                f"{entity} already exists.",
                details={"entity": entity, "id": entity_id},
            )
        collection[entity_id] = value.model_copy(deep=True)
