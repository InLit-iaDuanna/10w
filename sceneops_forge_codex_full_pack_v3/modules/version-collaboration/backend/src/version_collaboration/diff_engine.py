from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from typing import Any

from .base import ExecutionMode, VersionReference
from .diff_models import (
    BehaviorChange,
    BehaviorDiffLayer,
    BehaviorSnapshot,
    ConflictCode,
    DiffState,
    FileDiffLayer,
    FourLayerDiff,
    ReviewConflict,
    SemanticChange,
    SemanticChangeKind,
    SemanticDiffLayer,
    SemanticEntity,
    VisualCapture,
    VisualDiffLayer,
)
from .git_models import GitRepositoryState, GitVersionDiff
from .review_models import AssetLockRecord, LockAction


def combine_modes(modes: Iterable[ExecutionMode]) -> ExecutionMode:
    precedence = {
        ExecutionMode.LIVE: 0,
        ExecutionMode.CACHED: 1,
        ExecutionMode.MOCK: 2,
        ExecutionMode.PLANNED: 3,
        ExecutionMode.BLOCKED: 4,
    }
    values = tuple(modes)
    return max(values, key=precedence.__getitem__) if values else ExecutionMode.PLANNED


class FourLayerDiffEngine:
    def build(
        self,
        *,
        diff_bundle_id: str,
        git_diff: GitVersionDiff,
        repository_state: GitRepositoryState,
        semantic_before: tuple[SemanticEntity, ...] | None,
        semantic_after: tuple[SemanticEntity, ...] | None,
        visual_before: VisualCapture | None,
        visual_after: VisualCapture | None,
        behavior_before: BehaviorSnapshot | None,
        behavior_after: BehaviorSnapshot | None,
        target_ids: tuple[str, ...],
        active_locks: tuple[AssetLockRecord, ...],
        actor_id: str,
        sealed_at: datetime,
    ) -> FourLayerDiff:
        conflicts = self._repository_conflicts(repository_state)
        conflicts.extend(self._binary_lock_conflicts(git_diff, active_locks, actor_id))
        semantic, semantic_conflicts = self.compare_semantic(
            semantic_before, semantic_after, target_ids
        )
        visual, visual_conflicts = self.compare_visual(visual_before, visual_after)
        behavior, behavior_conflicts = self.compare_behavior(behavior_before, behavior_after)
        conflicts.extend(semantic_conflicts)
        conflicts.extend(visual_conflicts)
        conflicts.extend(behavior_conflicts)
        file_layer = FileDiffLayer(
            state=DiffState.SUCCEEDED if git_diff.changes else DiffState.EMPTY,
            changes=git_diff.changes,
            lfs_pointers=git_diff.lfs_pointers,
            mode=git_diff.mode,
        )
        layers = (file_layer, semantic, visual, behavior)
        return FourLayerDiff(
            diff_bundle_id=diff_bundle_id,
            base_version=git_diff.base,
            target_version=git_diff.target,
            file=file_layer,
            semantic=semantic,
            visual=visual,
            behavior=behavior,
            conflicts=tuple(conflicts),
            sealed_at=sealed_at,
            mode=combine_modes(layer.mode for layer in layers),
        )

    def compare_semantic(
        self,
        before: tuple[SemanticEntity, ...] | None,
        after: tuple[SemanticEntity, ...] | None,
        target_ids: tuple[str, ...] = (),
    ) -> tuple[SemanticDiffLayer, list[ReviewConflict]]:
        if before is None or after is None:
            return self._unavailable_semantic(), []
        before_by_id, duplicate_before = self._index_entities(before)
        after_by_id, duplicate_after = self._index_entities(after)
        duplicates = duplicate_before | duplicate_after
        if duplicates:
            conflict = self._schema_conflict(
                f"Semantic snapshots contain duplicate stable IDs: {', '.join(sorted(duplicates))}"
            )
            return self._incompatible_semantic(), [conflict]

        conflicts: list[ReviewConflict] = []
        changes: list[SemanticChange] = []
        for entity_id in sorted(before_by_id.keys() | after_by_id.keys()):
            base = before_by_id.get(entity_id)
            target = after_by_id.get(entity_id)
            if base is None:
                changes.append(self._whole_entity_change(target, SemanticChangeKind.ADDED))
                continue
            if target is None:
                changes.append(self._whole_entity_change(base, SemanticChangeKind.REMOVED))
                if entity_id in target_ids:
                    conflicts.append(
                        ReviewConflict(
                            code=ConflictCode.DELETED_TARGET,
                            message=f"Target {entity_id} no longer exists in the reviewed version.",
                            blocking=True,
                            target_id=entity_id,
                        )
                    )
                continue
            if not self._compatible_entity(base, target):
                conflicts.append(
                    self._schema_conflict(
                        f"Entity {entity_id} changed semantic schema without a declared provider migration.",
                        target_id=entity_id,
                    )
                )
                continue
            changes.extend(self._diff_values(base, target))

        incompatible = any(conflict.code == ConflictCode.INCOMPATIBLE_SCHEMA for conflict in conflicts)
        state = DiffState.INCOMPATIBLE if incompatible else (
            DiffState.SUCCEEDED if changes else DiffState.EMPTY
        )
        mode = combine_modes(entity.mode for entity in (*before, *after))
        if incompatible:
            mode = ExecutionMode.BLOCKED
        return SemanticDiffLayer(state=state, changes=tuple(changes), mode=mode), conflicts

    def compare_visual(
        self, before: VisualCapture | None, after: VisualCapture | None
    ) -> tuple[VisualDiffLayer, list[ReviewConflict]]:
        if before is None or after is None:
            return VisualDiffLayer(state=DiffState.UNAVAILABLE, mode=ExecutionMode.PLANNED), []
        if self._visual_descriptor(before) != self._visual_descriptor(after):
            conflict = self._schema_conflict(
                "Fixed-camera captures use incompatible camera, recipe, renderer, color, or dimensions."
            )
            return (
                VisualDiffLayer(
                    state=DiffState.INCOMPATIBLE,
                    base_artifact_id=before.artifact_id,
                    target_artifact_id=after.artifact_id,
                    camera_id=before.camera_id,
                    mode=ExecutionMode.BLOCKED,
                ),
                [conflict],
            )
        errors = tuple(abs(left - right) for left, right in zip(before.pixels, after.pixels))
        changed = sum(error > 0 for error in errors)
        mean = sum(errors) / len(errors) if errors else 0.0
        state = DiffState.SUCCEEDED if changed else DiffState.EMPTY
        return (
            VisualDiffLayer(
                state=state,
                base_artifact_id=before.artifact_id,
                target_artifact_id=after.artifact_id,
                camera_id=before.camera_id,
                changed_samples=changed,
                sample_count=len(errors),
                mean_absolute_error=mean,
                maximum_absolute_error=max(errors, default=0),
                mode=combine_modes((before.mode, after.mode)),
            ),
            [],
        )

    def compare_behavior(
        self, before: BehaviorSnapshot | None, after: BehaviorSnapshot | None
    ) -> tuple[BehaviorDiffLayer, list[ReviewConflict]]:
        if before is None or after is None:
            return BehaviorDiffLayer(state=DiffState.UNAVAILABLE, changes=(), mode=ExecutionMode.PLANNED), []
        if self._behavior_descriptor(before) != self._behavior_descriptor(after):
            conflict = self._schema_conflict(
                "Playtest evidence uses incompatible test, protocol, configuration, seed, or start state."
            )
            return (
                BehaviorDiffLayer(
                    state=DiffState.INCOMPATIBLE,
                    changes=(),
                    before_run_id=before.run_id,
                    after_run_id=after.run_id,
                    mode=ExecutionMode.BLOCKED,
                ),
                [conflict],
            )
        changes = self._behavior_changes(before, after)
        return (
            BehaviorDiffLayer(
                state=DiffState.SUCCEEDED if changes else DiffState.EMPTY,
                changes=tuple(changes),
                before_run_id=before.run_id,
                after_run_id=after.run_id,
                mode=combine_modes((before.mode, after.mode)),
            ),
            [],
        )

    def _repository_conflicts(self, state: GitRepositoryState) -> list[ReviewConflict]:
        conflicts: list[ReviewConflict] = []
        if state.dirty:
            conflicts.append(
                ReviewConflict(
                    code=ConflictCode.DIRTY_WORKTREE,
                    message="The working tree has uncommitted changes; immutable commit diff remains viewable.",
                    blocking=False,
                )
            )
        if state.conflicted:
            conflicts.append(
                ReviewConflict(
                    code=ConflictCode.MERGE_CONFLICT,
                    message="The working tree contains unresolved Git conflicts.",
                    blocking=True,
                )
            )
        return conflicts

    def _binary_lock_conflicts(
        self,
        git_diff: GitVersionDiff,
        lock_records: tuple[AssetLockRecord, ...],
        actor_id: str,
    ) -> list[ReviewConflict]:
        active = {
            record.path: record
            for record in lock_records
            if record.action == LockAction.ACQUIRED
        }
        conflicts: list[ReviewConflict] = []
        for change in git_diff.changes:
            if not change.binary:
                continue
            lock = active.get(change.path)
            if lock is not None and lock.owner_id == actor_id:
                continue
            reason = "is locked by another collaborator" if lock else "has no active lock"
            conflicts.append(
                ReviewConflict(
                    code=ConflictCode.LOCKED_BINARY_ASSET,
                    message=f"Binary asset {change.path} {reason}; use lock/branch/review instead of merging.",
                    blocking=True,
                    target_id=lock.resource_id if lock else None,
                    path=change.path,
                )
            )
        return conflicts

    def _index_entities(
        self, entities: tuple[SemanticEntity, ...]
    ) -> tuple[dict[str, SemanticEntity], set[str]]:
        indexed: dict[str, SemanticEntity] = {}
        duplicates: set[str] = set()
        for entity in entities:
            if entity.entity_id in indexed:
                duplicates.add(entity.entity_id)
            indexed[entity.entity_id] = entity
        return indexed, duplicates

    def _whole_entity_change(
        self, entity: SemanticEntity | None, kind: SemanticChangeKind
    ) -> SemanticChange:
        assert entity is not None
        return SemanticChange(
            entity_id=entity.entity_id,
            entity_kind=entity.entity_kind,
            path="/",
            kind=kind,
            before=entity.values if kind == SemanticChangeKind.REMOVED else None,
            after=entity.values if kind == SemanticChangeKind.ADDED else None,
        )

    def _compatible_entity(self, before: SemanticEntity, after: SemanticEntity) -> bool:
        return (
            before.entity_kind,
            before.schema_id,
            before.schema_version,
            before.producer_module,
        ) == (
            after.entity_kind,
            after.schema_id,
            after.schema_version,
            after.producer_module,
        )

    def _diff_values(
        self, before: SemanticEntity, after: SemanticEntity
    ) -> list[SemanticChange]:
        changes: list[SemanticChange] = []
        for path, left, right in self._walk_values(before.values, after.values):
            changes.append(
                SemanticChange(
                    entity_id=before.entity_id,
                    entity_kind=before.entity_kind,
                    path=path,
                    kind=SemanticChangeKind.CHANGED,
                    before=left,
                    after=right,
                )
            )
        return changes

    def _walk_values(self, before: Any, after: Any, path: str = "") -> Iterable[tuple[str, Any, Any]]:
        if isinstance(before, Mapping) and isinstance(after, Mapping):
            for key in sorted(before.keys() | after.keys()):
                child_path = f"{path}/{self._escape_pointer(str(key))}"
                if key not in before:
                    yield child_path, None, after[key]
                elif key not in after:
                    yield child_path, before[key], None
                else:
                    yield from self._walk_values(before[key], after[key], child_path)
            return
        if isinstance(before, Sequence) and not isinstance(before, (str, bytes)) and isinstance(after, Sequence) and not isinstance(after, (str, bytes)):
            if before != after:
                yield path or "/", before, after
            return
        if before != after:
            yield path or "/", before, after

    def _visual_descriptor(self, capture: VisualCapture) -> tuple[Any, ...]:
        return (
            capture.camera_id,
            capture.pose,
            capture.width,
            capture.height,
            capture.channels,
            capture.color_space,
            capture.capture_recipe_version,
            capture.renderer_version,
        )

    def _behavior_descriptor(self, snapshot: BehaviorSnapshot) -> tuple[Any, ...]:
        return (
            snapshot.test_case_id,
            snapshot.protocol_version,
            snapshot.config_id,
            snapshot.start_state_id,
            snapshot.seed,
        )

    def _behavior_changes(
        self, before: BehaviorSnapshot, after: BehaviorSnapshot
    ) -> list[BehaviorChange]:
        changes: list[BehaviorChange] = []
        if before.objective_succeeded != after.objective_succeeded:
            changes.append(
                BehaviorChange(
                    key="objective_result",
                    category="objective",
                    before=before.objective_succeeded,
                    after=after.objective_succeeded,
                )
            )
        changes.extend(self._compare_keyed("assertion", before.assertions, after.assertions, "assertion_id"))
        changes.extend(self._compare_keyed("step", before.steps, after.steps, "step_id"))
        return changes

    def _compare_keyed(
        self, category: str, before: tuple[Any, ...], after: tuple[Any, ...], key_name: str
    ) -> list[BehaviorChange]:
        left = {getattr(item, key_name): item.model_dump(mode="json") for item in before}
        right = {getattr(item, key_name): item.model_dump(mode="json") for item in after}
        return [
            BehaviorChange(key=key, category=category, before=left.get(key), after=right.get(key))
            for key in sorted(left.keys() | right.keys())
            if left.get(key) != right.get(key)
        ]

    def _unavailable_semantic(self) -> SemanticDiffLayer:
        return SemanticDiffLayer(state=DiffState.UNAVAILABLE, changes=(), mode=ExecutionMode.PLANNED)

    def _incompatible_semantic(self) -> SemanticDiffLayer:
        return SemanticDiffLayer(state=DiffState.INCOMPATIBLE, changes=(), mode=ExecutionMode.BLOCKED)

    def _schema_conflict(self, message: str, target_id: str | None = None) -> ReviewConflict:
        return ReviewConflict(
            code=ConflictCode.INCOMPATIBLE_SCHEMA,
            message=message,
            blocking=True,
            target_id=target_id,
        )

    def _escape_pointer(self, value: str) -> str:
        return value.replace("~", "~0").replace("/", "~1")
