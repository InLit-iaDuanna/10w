from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from threading import Event

from version_collaboration.base import Actor, ActionContext, ExecutionMode, VersionReference
from version_collaboration.diff_models import (
    BehaviorAssertion,
    BehaviorSnapshot,
    BehaviorStep,
    CameraPose,
    SemanticEntity,
    VisualCapture,
)
from version_collaboration.git_models import (
    GitBranch,
    GitCapabilities,
    GitCommit,
    GitFileChange,
    GitRepositoryState,
    GitRollbackCommand,
    GitRollbackResult,
    GitVersionDiff,
    IntegrationHealth,
    LfsLockResult,
    LfsUnlockResult,
    LfsPointer,
    RollbackPreview,
)
from version_collaboration.ports import (
    ApprovalBinding,
    ChangeSetDraft,
    ChangeSetReference,
    VerifiedApproval,
    ChangeSetGateway,
)
from version_collaboration.service import VersionCollaborationService
from version_collaboration.sqlite_repository import SqliteReviewRepository


NOW = datetime(2026, 9, 4, 1, 2, 3, tzinfo=timezone.utc)
BASE = "1" * 40
TARGET = "2" * 40
ROLLBACK_RESULT = "3" * 40


class FixedClock:
    def now(self) -> datetime:
        return NOW


class DeterministicIds:
    def __init__(self) -> None:
        self._next = 0

    def new(self, prefix: str) -> str:
        self._next += 1
        return f"{prefix}_{self._next:04d}"


class RecordingPublisher:
    def __init__(self) -> None:
        self.events: list[object] = []

    def publish(self, event: object) -> None:
        self.events.append(event)


class FakeChangeSetGateway:
    def __init__(self, mode: ExecutionMode = ExecutionMode.MOCK) -> None:
        self.mode = mode
        self.drafts: list[ChangeSetDraft] = []

    def create(self, draft: ChangeSetDraft) -> ChangeSetReference:
        self.drafts.append(draft)
        return ChangeSetReference(
            change_set_id="changeset_rollback_1",
            version=1,
            state="awaiting_approval",
            mode=self.mode,
        )


class FakeApprovalVerifier:
    def __init__(
        self,
        *,
        outcome: str = "approved",
        evidence_ids: tuple[str, ...] = ("evidence_review_1",),
        mode: ExecutionMode = ExecutionMode.MOCK,
    ) -> None:
        self.outcome = outcome
        self.evidence_ids = evidence_ids
        self.mode = mode
        self.bindings: list[ApprovalBinding] = []

    def verify(self, approval_id: str, binding: ApprovalBinding) -> VerifiedApproval:
        self.bindings.append(binding)
        return VerifiedApproval(
            approval_id=approval_id,
            binding=binding,
            approver_id="user_reviewer",
            outcome=self.outcome,
            rationale="Deterministic approval fixture.",
            evidence_ids=self.evidence_ids,
            approved_at=NOW,
            mode=self.mode,
        )


class FakeGitAdapter:
    def __init__(self, *, dirty: bool = False, conflicted: bool = False) -> None:
        self.head = TARGET
        self.dirty = dirty
        self.conflicted = conflicted
        self.rollback_calls = 0
        self.completed_rollbacks: dict[str, GitRollbackResult] = {}
        self.locked: dict[str, LfsLockResult] = {}

    def health_check(self, project_root: Path) -> IntegrationHealth:
        return IntegrationHealth(
            integration_id="git", connected=True, mode=ExecutionMode.MOCK, checked_at=NOW
        )

    def capabilities(self, project_root: Path) -> GitCapabilities:
        return GitCapabilities(
            adapter_id="git.fixture",
            adapter_version="1",
            git_version="fixture",
            lfs_cli_available=True,
            operations=("inspect", "compare", "lfs.lock.inspect", "lfs.lock.acquire", "lfs.lock.release", "rollback.execute"),
            mode=ExecutionMode.MOCK,
        )

    def inspect(self, project_id: str, repository_id: str, project_root: Path) -> GitRepositoryState:
        status_changes = (
            GitFileChange(path="Assets/Home/Door.prefab", kind="conflict" if self.conflicted else "modified"),
        ) if (self.dirty or self.conflicted) else ()
        return GitRepositoryState(
            project_id=project_id,
            version=version(self.head),
            dirty=self.dirty or self.conflicted,
            conflicted=self.conflicted,
            changes=status_changes,
            lfs_pointers=(),
            branches=(GitBranch(name="feature/key-door", commit_id=self.head, current=True),),
            commits=(
                GitCommit(commit_id=self.head, author="SceneOps Fixture", authored_at=NOW, subject="Add key branch"),
            ),
            mode=ExecutionMode.MOCK,
            captured_at=NOW,
        )

    def compare_versions(
        self, repository_id: str, project_root: Path, base_commit: str, target_commit: str
    ) -> GitVersionDiff:
        return git_diff(base_commit, target_commit)

    def dry_run_rollback(self, project_root: Path, command: GitRollbackCommand) -> RollbackPreview:
        reasons = () if command.expected_head == self.head and not self.dirty else ("stale_base",)
        return RollbackPreview(
            current_head=self.head,
            target_commit=command.target_commit,
            changes=(GitFileChange(path="src/gameplay.ts", kind="modified", additions=1, deletions=2),),
            blocked_reasons=reasons,
            mode=ExecutionMode.BLOCKED if reasons else ExecutionMode.MOCK,
        )

    def acquire_lfs_lock(self, project_root: Path, path: str, operation_id: str) -> LfsLockResult:
        result = LfsLockResult(
            external_lock_id=f"external-{len(self.locked) + 1}",
            path=path,
            owner_name="Fixture Reviewer",
            locked_at=NOW,
            mode=ExecutionMode.MOCK,
        )
        self.locked[result.external_lock_id] = result
        return result

    def inspect_lfs_lock(
        self, project_root: Path, path: str
    ) -> LfsLockResult | None:
        return next((item for item in self.locked.values() if item.path == path), None)

    def release_lfs_lock(
        self,
        project_root: Path,
        external_lock_id: str,
        expected_path: str,
        operation_id: str,
    ) -> LfsUnlockResult:
        released = self.locked.pop(external_lock_id)
        return LfsUnlockResult(
            external_lock_id=released.external_lock_id,
            path=expected_path,
            mode=released.mode,
        )

    def execute_rollback(
        self, project_root: Path, command: GitRollbackCommand, *, cancellation: Event | None = None
    ) -> GitRollbackResult:
        if command.operation_id in self.completed_rollbacks:
            return self.completed_rollbacks[command.operation_id]
        if command.expected_head != self.head:
            raise AssertionError("fake adapter received a stale rollback command")
        self.rollback_calls += 1
        previous = self.head
        self.head = ROLLBACK_RESULT
        result = GitRollbackResult(
            operation_id=command.operation_id,
            previous_head=previous,
            resulting_head=self.head,
            changed_paths=("src/gameplay.ts",),
            approval_id=command.approval_id,
            mode=ExecutionMode.MOCK,
        )
        self.completed_rollbacks[command.operation_id] = result
        return result


def version(commit_id: str = TARGET) -> VersionReference:
    return VersionReference(
        repository_id="repository_home",
        object_format="sha1",
        commit_id=commit_id,
        branch="feature/key-door",
    )


def context(actor_id: str = "user_author", mode: ExecutionMode = ExecutionMode.MOCK) -> ActionContext:
    return ActionContext(
        actor=Actor(actor_id=actor_id),
        correlation_id="correlation_test",
        causation_id="command_test",
        mode=mode,
        permissions=frozenset(
            {
                "review:read",
                "review:create",
                "review:comment",
                "review:assign",
                "review:approve",
                "version:lock",
                "version:rollback",
            }
        ),
    )


def git_diff(base: str = BASE, target: str = TARGET, *, binary: bool = False) -> GitVersionDiff:
    changes = (
        GitFileChange(
            path="Assets/Home/Key.glb" if binary else "src/gameplay.ts",
            kind="modified",
            additions=None if binary else 4,
            deletions=None if binary else 1,
            binary=binary,
        ),
    )
    pointers = (
        LfsPointer(path="Assets/Home/Key.glb", object_id="a" * 64, size=1024, lock_required=True),
    ) if binary else ()
    return GitVersionDiff(base=version(base), target=version(target), changes=changes, lfs_pointers=pointers, mode=ExecutionMode.MOCK)


def semantic_pair() -> tuple[tuple[SemanticEntity, ...], tuple[SemanticEntity, ...]]:
    common = {
        "entity_id": "sceneobject_door_01",
        "entity_kind": "scene_object",
        "schema_id": "sceneops.semantic.scene-object",
        "schema_version": 1,
        "producer_module": "world-composer",
        "mode": ExecutionMode.MOCK,
    }
    return (
        (SemanticEntity(artifact_id="artifact_semantic_before", values={"locked": True}, **common),),
        (SemanticEntity(artifact_id="artifact_semantic_after", values={"locked": False}, **common),),
    )


def visual_pair() -> tuple[VisualCapture, VisualCapture]:
    pose = CameraPose(
        position_m=(0.0, 1.6, -3.0),
        rotation_xyzw=(0.0, 0.0, 0.0, 1.0),
        projection="perspective",
        vertical_fov_degrees=50,
    )
    common = {
        "camera_id": "camera_review_fixed",
        "pose": pose,
        "width": 2,
        "height": 2,
        "channels": 1,
        "color_space": "srgb",
        "capture_recipe_version": "recipe-v1",
        "renderer_version": "renderer-fixture-v1",
        "mode": ExecutionMode.MOCK,
    }
    return (
        VisualCapture(artifact_id="artifact_visual_before", pixels=(0, 10, 20, 30), **common),
        VisualCapture(artifact_id="artifact_visual_after", pixels=(0, 12, 20, 40), **common),
    )


def behavior_pair() -> tuple[BehaviorSnapshot, BehaviorSnapshot]:
    common = {
        "test_case_id": "testcase_key_door",
        "protocol_version": "playtest-v1",
        "config_id": "config_key_door",
        "start_state_id": "start_home_hallway",
        "seed": 7,
        "mode": ExecutionMode.MOCK,
    }
    return (
        BehaviorSnapshot(
            run_id="playtestrun_before",
            build_id="build_before",
            objective_succeeded=False,
            assertions=(BehaviorAssertion(assertion_id="assertion_door_open", passed=False),),
            steps=(BehaviorStep(step_id="playstep_open", action_id="action_open", outcome="locked", goal_progress=0.4, target_sceneops_id="sceneobject_door_01"),),
            **common,
        ),
        BehaviorSnapshot(
            run_id="playtestrun_after",
            build_id="build_after",
            objective_succeeded=True,
            assertions=(BehaviorAssertion(assertion_id="assertion_door_open", passed=True),),
            steps=(BehaviorStep(step_id="playstep_open", action_id="action_open", outcome="opened", goal_progress=1.0, target_sceneops_id="sceneobject_door_01"),),
            **common,
        ),
    )


def make_service(
    *,
    repository: SqliteReviewRepository | None = None,
    git: FakeGitAdapter | None = None,
    approvals: FakeApprovalVerifier | None = None,
    change_sets: ChangeSetGateway | None = None,
) -> tuple[VersionCollaborationService, SqliteReviewRepository, FakeGitAdapter, FakeApprovalVerifier, RecordingPublisher]:
    repository = repository or SqliteReviewRepository()
    fake_git = git or FakeGitAdapter()
    verifier = approvals or FakeApprovalVerifier()
    events = RecordingPublisher()
    service = VersionCollaborationService(
        repository=repository,
        git=fake_git,
        project_roots={"project_home": Path("/tmp/sceneops-home")},
        change_sets=change_sets or FakeChangeSetGateway(),
        approvals=verifier,
        events=events,
        clock=FixedClock(),
        ids=DeterministicIds(),
    )
    return service, repository, fake_git, verifier, events
