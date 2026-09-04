"""Isolated, memory-only workbench composition. Never touches a Git checkout."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import Field

from .base import ActionContext, Actor, ExecutionMode, FrozenModel, VersionReference
from .errors import ErrorCode, VersionCollaborationError
from .git_models import GitFileChange, GitRepositoryState, GitVersionDiff, LfsPointer
from .ports import ApprovalBinding, UnavailableChangeSetGateway, VerifiedApproval
from .review_models import ApprovalObservation, CreateReviewCommand, ReviewSession
from .router import create_router, version_collaboration_exception_handler
from .service import VersionCollaborationService
from .sqlite_repository import SqliteReviewRepository


class DemoEntry(FrozenModel):
    label: str
    review: ReviewSession
    inputs: CreateReviewCommand


class DemoCatalog(FrozenModel):
    mode: str = "mock"
    persistence: str = "内存 SQLite；重启恢复演示数据"
    entries: tuple[DemoEntry, ...]


class DemoApprovalRequest(FrozenModel):
    rationale: str = Field(min_length=1, max_length=10000)
    outcome: str = Field(pattern="^(approved|rejected)$")


def demo_context(request: Request | None = None) -> ActionContext:
    return ActionContext(
        actor=Actor(actor_id="user.demo-reviewer"),
        correlation_id=f"correlation.{uuid4().hex}",
        causation_id="command.demo-workbench", mode=ExecutionMode.MOCK,
        permissions=frozenset({"review:read", "review:create", "review:comment",
                               "review:assign", "review:approve"}),
    )


class DemoGit:
    """Fixture-backed read-only Git port; no CLI, filesystem or remote operations."""
    def __init__(self, fixtures: list[dict]) -> None:
        self.fixtures = {item["command"]["repository_id"]: item for item in fixtures}

    def version(self, repository_id: str, commit: str) -> VersionReference:
        return VersionReference(repository_id=repository_id, object_format="sha1",
                                commit_id=commit, branch="demo/review")

    def inspect(self, project_id: str, repository_id: str, project_root: Path) -> GitRepositoryState:
        item = self.fixtures[repository_id]["command"]
        return GitRepositoryState(
            project_id=project_id, version=self.version(repository_id, item["target_commit"]),
            dirty=False, conflicted=False, changes=(), lfs_pointers=(), branches=(), commits=(),
            mode=ExecutionMode.MOCK, captured_at=datetime.now(timezone.utc),
        )

    def compare_versions(self, repository_id: str, project_root: Path,
                         base_commit: str, target_commit: str) -> GitVersionDiff:
        fixture = self.fixtures[repository_id]
        command, expected = fixture["command"], fixture["expected"]
        if (base_commit, target_commit) != (command["base_commit"], command["target_commit"]):
            raise VersionCollaborationError(ErrorCode.INVALID_STATE, "演示仓库只提供预置版本对。")
        return GitVersionDiff(
            base=self.version(repository_id, base_commit), target=self.version(repository_id, target_commit),
            changes=tuple(GitFileChange.model_validate(x) for x in expected["file_changes"]),
            lfs_pointers=tuple(LfsPointer.model_validate(x) for x in expected["lfs_pointers"]),
            mode=ExecutionMode.MOCK,
        )


class DemoApprovals:
    def __init__(self) -> None:
        self.records: dict[str, VerifiedApproval] = {}

    def verify(self, approval_id: str, binding: ApprovalBinding) -> VerifiedApproval:
        record = self.records.get(approval_id)
        if record is None or record.binding != binding:
            raise VersionCollaborationError(ErrorCode.APPROVAL_REQUIRED, "没有匹配当前版本的 MOCK 审批。")
        return record


class DemoEvents:
    def __init__(self) -> None:
        self.events: list[object] = []

    def publish(self, event: object) -> None:
        self.events.append(event)


def create_demo_router(service: VersionCollaborationService, catalog: DemoCatalog,
                       approvals: DemoApprovals) -> APIRouter:
    router = APIRouter(prefix="/api/lab", tags=["version-review-demo"])

    @router.get("/catalog")
    def get_catalog() -> DemoCatalog:
        return catalog

    @router.post("/reviews/{review_id}/mock-approval", status_code=201)
    def mock_approval(review_id: str, body: DemoApprovalRequest) -> ApprovalObservation:
        review = service.get_review(review_id)
        approval_id = f"approval.demo.{uuid4().hex}"
        binding = ApprovalBinding(
            review_id=review_id, review_revision_id=review.review_revision_id,
            diff_bundle_id=review.diff.diff_bundle_id, subject_kind="review", subject_id=review_id,
            subject_version=review.revision, base_version=review.target_version,
        )
        approvals.records[approval_id] = VerifiedApproval(
            approval_id=approval_id, binding=binding, approver_id="user.mock-approver",
            outcome=body.outcome, rationale=body.rationale, evidence_ids=review.evidence_ids,
            approved_at=datetime.now(timezone.utc), mode=ExecutionMode.MOCK,
        )
        return service.observe_approval(
            review_id=review_id, approval_id=approval_id, subject_kind="review",
            subject_id=review_id, subject_version=review.revision,
            current_base=review.target_version, context=demo_context(),
        )

    return router


def create_demo_app() -> FastAPI:
    fixture_root = Path(__file__).resolve().parents[3] / "contracts" / "examples"
    fixtures = [json.loads((fixture_root / name).read_text()) for name in
                ("remember-home-review.json", "warehouse-escape-review.json")]
    git, approvals = DemoGit(fixtures), DemoApprovals()
    service = VersionCollaborationService(
        repository=SqliteReviewRepository(), git=git,
        project_roots={x["command"]["project_id"]: fixture_root for x in fixtures},
        change_sets=UnavailableChangeSetGateway(), approvals=approvals, events=DemoEvents(),
    )
    entries = []
    for fixture, label in zip(fixtures, ("Remember Home · 钥匙与门", "Warehouse Escape · 出口联动")):
        command = CreateReviewCommand.model_validate({**fixture["command"], "title": label})
        review = service.create_review(command, demo_context())
        entries.append(DemoEntry(label=label, review=review, inputs=command))
    app = FastAPI(title="Version Review 独立演示 API", version="0.1.0")

    @app.middleware("http")
    async def local_writes_only(request: Request, call_next):
        # Same-origin proxy only for browser mutations; loopback CLI remains usable.
        origin = request.headers.get("origin")
        if request.method not in ("GET", "HEAD", "OPTIONS") and origin:
            from urllib.parse import urlparse
            if urlparse(origin).netloc != request.headers.get("host"):
                return JSONResponse(status_code=403, content={"message": "仅允许同源本地操作。"})
        return await call_next(request)

    app.add_exception_handler(VersionCollaborationError, version_collaboration_exception_handler)
    app.include_router(create_router(service, demo_context))
    app.include_router(create_demo_router(service, DemoCatalog(entries=tuple(entries)), approvals))
    return app
