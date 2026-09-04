from __future__ import annotations

import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from version_collaboration.errors import VersionCollaborationError
from version_collaboration.review_models import CreateReviewCommand
from version_collaboration.router import create_router, version_collaboration_exception_handler

from support import (
    BASE,
    TARGET,
    behavior_pair,
    context,
    make_service,
    semantic_pair,
    version,
    visual_pair,
)


class VersionCollaborationApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service, _, _, _, _, = make_service()
        app = FastAPI()
        app.include_router(create_router(self.service, lambda request: context("user_api")))
        app.add_exception_handler(
            VersionCollaborationError, version_collaboration_exception_handler
        )
        self.app = app
        self.client = TestClient(app)

    def test_create_read_summarize_and_comment_review(self) -> None:
        semantic_before, semantic_after = semantic_pair()
        visual_before, visual_after = visual_pair()
        behavior_before, behavior_after = behavior_pair()
        command = CreateReviewCommand(
            project_id="project_home",
            repository_id="repository_home",
            title="API 评审",
            base_commit=BASE,
            target_commit=TARGET,
            semantic_before=semantic_before,
            semantic_after=semantic_after,
            visual_before=visual_before,
            visual_after=visual_after,
            behavior_before=behavior_before,
            behavior_after=behavior_after,
            evidence_ids=("evidence_api",),
        )

        created = self.client.post(
            "/api/version-collaboration/reviews",
            json=command.model_dump(mode="json"),
        )
        self.assertEqual(created.status_code, 201)
        review = created.json()
        review_id = review["review_id"]

        revision = self.client.get(
            f"/api/version-collaboration/reviews/{review_id}/revisions/{review['review_revision_id']}"
        )
        self.assertEqual(revision.status_code, 200)
        self.assertEqual(
            revision.json()["review_revision_id"], review["review_revision_id"]
        )

        revision_summary = self.client.get(
            f"/api/version-collaboration/reviews/{review_id}/revisions/{review['review_revision_id']}/summary"
        )
        self.assertEqual(revision_summary.status_code, 200)

        summary = self.client.get(
            f"/api/version-collaboration/reviews/{review_id}/summary"
        )
        self.assertEqual(summary.status_code, 200)
        self.assertEqual(len(summary.json()["layer_summaries"]), 4)

        comment = self.client.post(
            f"/api/version-collaboration/reviews/{review_id}/comments",
            json={
                "body": "请核对开门状态。",
                "anchor": {
                    "kind": "scene_object",
                    "review_revision_id": review["review_revision_id"],
                    "diff_bundle_id": review["diff"]["diff_bundle_id"],
                    "version": review["target_version"],
                    "target_id": "sceneobject_door_01",
                },
            },
        )
        self.assertEqual(comment.status_code, 201)
        self.assertEqual(comment.json()["anchor"]["target_id"], "sceneobject_door_01")

    def test_stale_base_returns_structured_error_contract(self) -> None:
        semantic_before, semantic_after = semantic_pair()
        review = self.service.create_review(
            CreateReviewCommand(
                project_id="project_home",
                repository_id="repository_home",
                title="过期基线评审",
                base_commit=BASE,
                target_commit=TARGET,
                semantic_before=semantic_before,
                semantic_after=semantic_after,
            ),
            context("user_api"),
        )

        response = self.client.post(
            f"/api/version-collaboration/reviews/{review.review_id}/approvals",
            headers={"x-request-id": "request_api_stale"},
            json={
                "approval_id": "approval_stale",
                "subject_kind": "review",
                "subject_id": review.review_id,
                "subject_version": 1,
                "current_base": version(BASE).model_dump(mode="json"),
            },
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["code"], "STALE_BASE")
        self.assertEqual(response.json()["request_id"], "request_api_stale")
        self.assertIn("review.session.create", response.json()["suggested_actions"])

    def test_openapi_has_typed_routes_and_never_accepts_project_paths(self) -> None:
        schema = self.app.openapi()
        create = schema["paths"]["/api/version-collaboration/reviews"]["post"]

        self.assertIn("requestBody", create)
        serialized = str(schema)
        self.assertNotIn("project_root", serialized)
        self.assertNotIn("argv", serialized)


if __name__ == "__main__":
    unittest.main()
