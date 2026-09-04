"""Public backend surface for the Version and Collaboration module."""

from .base import ActionContext, Actor, ExecutionMode, VersionReference
from .errors import ErrorCode, VersionCollaborationError
from .git_adapter import GitCliAdapter
from .ports import ApprovalVerifier, ChangeSetGateway, GitAdapter
from .repository import ReviewRepository
from .router import create_router, version_collaboration_exception_handler
from .service import VersionCollaborationService
from .sqlite_repository import SqliteReviewRepository

__all__ = (
    "ActionContext",
    "Actor",
    "ApprovalVerifier",
    "ChangeSetGateway",
    "ErrorCode",
    "ExecutionMode",
    "GitAdapter",
    "GitCliAdapter",
    "ReviewRepository",
    "SqliteReviewRepository",
    "VersionCollaborationError",
    "VersionCollaborationService",
    "VersionReference",
    "create_router",
    "version_collaboration_exception_handler",
)
