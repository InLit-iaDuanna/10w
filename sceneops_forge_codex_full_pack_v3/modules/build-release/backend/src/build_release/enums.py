"""Stable enum values used by public build-release contracts."""

from enum import Enum


class ExecutionMode(str, Enum):
    LIVE = "live"
    CACHED = "cached"
    MOCK = "mock"
    PLANNED = "planned"
    BLOCKED = "blocked"


class BuildProfile(str, Enum):
    DEVELOPMENT = "development"
    QA = "qa"
    JUDGE = "judge"
    RELEASE_CANDIDATE = "release_candidate"


class RunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"


class GateCategory(str, Enum):
    ASSET = "asset"
    SCENE = "scene"
    CODE = "code"
    RENDER = "render"
    UNITY_TESTS = "unity_tests"
    PERFORMANCE = "performance"
    AI_REGRESSION = "ai_regression"


class GateStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    BLOCKED = "blocked"


class CandidateStatus(str, Enum):
    BLOCKED = "blocked"
    WAITING_APPROVAL = "waiting_approval"
    READY = "ready"
    DEPLOYED = "deployed"
    ROLLED_BACK = "rolled_back"


class ApprovalAction(str, Enum):
    CREATE_CANDIDATE = "create_candidate"
    DEPLOY = "deploy"
    ROLLBACK = "rollback"
    MARK_KNOWN_GOOD = "mark_known_good"


class ApprovalDecision(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"


class DeploymentTarget(str, Enum):
    LOCAL = "local"
    JUDGE = "judge"


class DeploymentStatus(str, Enum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    BLOCKED = "blocked"


class RollbackStatus(str, Enum):
    WAITING_APPROVAL = "waiting_approval"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class PatchNoteStatus(str, Enum):
    DRAFT = "draft"
    APPROVED = "approved"


class FeedbackKind(str, Enum):
    ISSUE = "issue"
    PLAYTEST = "playtest"
    USER_FEEDBACK = "user_feedback"
