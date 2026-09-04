from __future__ import annotations

from pathlib import Path
from threading import RLock
from typing import NoReturn

from .base import ActionContext
from .diff_engine import combine_modes
from .errors import ErrorCode, VersionCollaborationError
from .git_models import LfsLockResult, validate_relative_path
from .review_models import AssetLockRecord, LockAction
from .service_runtime import ServiceRuntime


class LockOperations:
    def __init__(self, runtime: ServiceRuntime) -> None:
        self._runtime = runtime
        self._lock = RLock()

    def acquire_asset_lock(
        self,
        *,
        review_id: str,
        project_id: str,
        repository_id: str,
        resource_id: str,
        path: str,
        context: ActionContext,
    ) -> AssetLockRecord:
        with self._lock:
            return self._acquire_asset_lock(
                review_id=review_id,
                project_id=project_id,
                repository_id=repository_id,
                resource_id=resource_id,
                path=path,
                context=context,
            )

    def _acquire_asset_lock(
        self,
        *,
        review_id: str,
        project_id: str,
        repository_id: str,
        resource_id: str,
        path: str,
        context: ActionContext,
    ) -> AssetLockRecord:
        rt = self._runtime
        rt.authorize(context, "version:lock")
        path = validate_relative_path(path)
        review = rt.repository.get_review(review_id)
        if review.project_id != project_id:
            raise VersionCollaborationError(
                ErrorCode.INVALID_STATE,
                "Asset lock project does not match the review project.",
                details={"review_id": review_id, "project_id": project_id},
            )
        existing = rt.repository.get_active_lock(project_id, resource_id)
        if existing is not None:
            if (
                existing.owner_id == context.actor.actor_id
                and existing.path == path
                and existing.base_version.repository_id == repository_id
            ):
                remote = rt.git.inspect_lfs_lock(
                    rt.project_root(project_id), path
                )
                if (
                    remote is not None
                    and remote.external_lock_id == existing.external_lock_id
                    and remote.path == existing.path
                ):
                    return existing
                raise VersionCollaborationError(
                    ErrorCode.LOCK_RECONCILIATION_REQUIRED,
                    "The local lock projection no longer matches Git LFS.",
                    details={"lock_id": existing.lock_id, "path": existing.path},
                    suggested_actions=("integration.open",),
                )
            raise VersionCollaborationError(
                ErrorCode.LOCK_CONFLICT,
                "The resource already has a different active binary lock.",
                details={
                    "resource_id": resource_id,
                    "owner_id": existing.owner_id,
                    "held_path": existing.path,
                    "requested_path": path,
                },
            )

        state = rt.git.inspect(
            project_id, repository_id, rt.project_root(project_id)
        )
        external = rt.git.acquire_lfs_lock(
            rt.project_root(project_id), path, rt.ids.new("operation")
        )
        if external.path != path:
            self._undo_remote_acquire(
                rt.project_root(project_id),
                external,
                VersionCollaborationError(
                    ErrorCode.INCOMPATIBLE_SCHEMA,
                    "Git LFS locked a different path than requested.",
                    details={
                        "requested_path": path,
                        "actual_path": external.path,
                    },
                ),
            )
        record = AssetLockRecord(
            lock_record_id=rt.ids.new("lockevent"),
            lock_id=rt.ids.new("lock"),
            external_lock_id=external.external_lock_id,
            project_id=project_id,
            resource_id=resource_id,
            path=external.path,
            branch=state.version.branch or "detached",
            owner_id=context.actor.actor_id,
            action=LockAction.ACQUIRED,
            base_version=state.version,
            created_at=external.locked_at,
            mode=combine_modes((context.mode, external.mode)),
        )
        try:
            rt.repository.acquire_lock(record)
        except Exception as error:
            self._undo_remote_acquire(rt.project_root(project_id), external, error)
        rt.audit(
            review,
            "review.lock.recorded",
            record.lock_record_id,
            "已获取 Git LFS 二进制资产锁。",
            context,
            mode=record.mode,
        )
        return record

    def release_asset_lock(
        self,
        *,
        review_id: str,
        project_id: str,
        resource_id: str,
        context: ActionContext,
    ) -> AssetLockRecord:
        with self._lock:
            return self._release_asset_lock(
                review_id=review_id,
                project_id=project_id,
                resource_id=resource_id,
                context=context,
            )

    def _release_asset_lock(
        self,
        *,
        review_id: str,
        project_id: str,
        resource_id: str,
        context: ActionContext,
    ) -> AssetLockRecord:
        rt = self._runtime
        rt.authorize(context, "version:lock")
        review = rt.repository.get_review(review_id)
        if review.project_id != project_id:
            raise VersionCollaborationError(
                ErrorCode.INVALID_STATE,
                "Asset lock project does not match the review project.",
            )
        held = rt.repository.get_active_lock(project_id, resource_id)
        if held is None:
            raise VersionCollaborationError(
                ErrorCode.NOT_FOUND,
                "No active lock exists for this binary asset.",
                details={"resource_id": resource_id},
            )
        if held.owner_id != context.actor.actor_id:
            raise VersionCollaborationError(
                ErrorCode.LOCK_OWNERSHIP,
                "Only the lock owner can release this binary asset.",
                details={"owner_id": held.owner_id},
            )
        remote = rt.git.inspect_lfs_lock(
            rt.project_root(project_id), held.path
        )
        if (
            remote is None
            or remote.external_lock_id != held.external_lock_id
            or remote.path != held.path
        ):
            raise VersionCollaborationError(
                ErrorCode.LOCK_RECONCILIATION_REQUIRED,
                "The local lock projection does not match Git LFS; unlock was not attempted.",
                details={"lock_id": held.lock_id, "path": held.path},
                suggested_actions=("integration.open",),
            )
        external = rt.git.release_lfs_lock(
            rt.project_root(project_id),
            held.external_lock_id,
            held.path,
            rt.ids.new("operation"),
        )
        if (
            external.external_lock_id != held.external_lock_id
            or external.path != held.path
        ):
            self._restore_remote_lock(
                rt.project_root(project_id),
                held,
                context,
                VersionCollaborationError(
                    ErrorCode.INCOMPATIBLE_SCHEMA,
                    "Git LFS returned a different lock during release.",
                    details={"lock_id": held.lock_id},
                ),
            )
        record = held.model_copy(
            update={
                "lock_record_id": rt.ids.new("lockevent"),
                "action": LockAction.RELEASED,
                "created_at": rt.clock.now(),
                "mode": combine_modes((context.mode, external.mode)),
            }
        )
        try:
            rt.repository.release_lock(record)
        except Exception as error:
            self._restore_remote_lock(
                rt.project_root(project_id), held, context, error
            )
        rt.audit(
            review,
            "review.lock.recorded",
            record.lock_record_id,
            "已释放 Git LFS 二进制资产锁。",
            context,
            mode=record.mode,
        )
        return record

    def _undo_remote_acquire(
        self, root: Path, external: LfsLockResult, cause: Exception
    ) -> NoReturn:
        rt = self._runtime
        try:
            released = rt.git.release_lfs_lock(
                root,
                external.external_lock_id,
                external.path,
                rt.ids.new("operation"),
            )
            if (
                released.external_lock_id != external.external_lock_id
                or released.path != external.path
            ):
                raise VersionCollaborationError(
                    ErrorCode.INCOMPATIBLE_SCHEMA,
                    "Git LFS returned a different lock during compensation.",
                )
        except Exception as compensation_error:
            raise VersionCollaborationError(
                ErrorCode.LOCK_RECONCILIATION_REQUIRED,
                "Git LFS acquired a lock that could not be reconciled locally or compensated.",
                details={
                    "external_lock_id": external.external_lock_id,
                    "path": external.path,
                    "compensation_error": type(compensation_error).__name__,
                },
                suggested_actions=("integration.open",),
            ) from cause
        raise cause

    def _restore_remote_lock(
        self,
        root: Path,
        held: AssetLockRecord,
        context: ActionContext,
        cause: Exception,
    ) -> NoReturn:
        rt = self._runtime
        try:
            external = rt.git.acquire_lfs_lock(
                root, held.path, rt.ids.new("operation")
            )
            if external.path != held.path:
                raise VersionCollaborationError(
                    ErrorCode.INCOMPATIBLE_SCHEMA,
                    "Git LFS reacquired a different path during compensation.",
                )
            replacement = held.model_copy(
                update={
                    "lock_record_id": rt.ids.new("lockevent"),
                    "external_lock_id": external.external_lock_id,
                    "action": LockAction.ACQUIRED,
                    "created_at": external.locked_at,
                    "mode": combine_modes((context.mode, external.mode)),
                }
            )
            rt.repository.replace_active_lock(replacement)
        except Exception as compensation_error:
            raise VersionCollaborationError(
                ErrorCode.LOCK_RECONCILIATION_REQUIRED,
                "Git LFS release and local lock projection diverged and automatic compensation failed.",
                details={
                    "lock_id": held.lock_id,
                    "path": held.path,
                    "compensation_error": type(compensation_error).__name__,
                },
                suggested_actions=("integration.open",),
            ) from cause
        raise VersionCollaborationError(
            ErrorCode.INVALID_STATE,
            "Lock release did not complete; the remote lock was reacquired and the local projection reconciled.",
            details={"lock_id": held.lock_id, "path": held.path},
            suggested_actions=("review.lock.release",),
        ) from cause
