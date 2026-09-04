from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from build_release.adapters import (
    FileArtifactCatalog,
    LocalFileDeploymentAdapter,
    NeverCancelled,
)
from build_release.checksum import file_sha256
from build_release.enums import (
    ApprovalAction,
    ApprovalDecision,
    DeploymentStatus,
    DeploymentTarget,
    ExecutionMode,
)
from build_release.errors import AdapterExecutionError, ConflictError, PolicyError
from build_release.models_common import Approval, ArtifactRef
from build_release.ports import DeploymentCommand
from build_release.ports import ArtifactInspection
from build_release.requests import (
    DeployRequest,
    PrepareDeploymentRequest,
    RetryDeploymentRequest,
)

from support import (
    BASE_TIME,
    create_patch_note,
    create_ready_candidate,
    make_build_pair,
    make_service,
    record_pair,
)


def deployment_approvals(plan, deployment_id: str, *, known_good: bool = False):
    approvals = [
        Approval(
            approval_id=f"approval.{deployment_id}.deploy.{index}",
            action=ApprovalAction.DEPLOY,
            target_id=deployment_id,
            scope_fingerprint=plan.operation_scope_fingerprint,
            role=role,
            actor_id=f"user.{role}",
            decision=ApprovalDecision.APPROVED,
            rationale="Approve exact deterministic deployment scope.",
            decided_at=BASE_TIME,
        )
        for index, role in enumerate(plan.required_approval_roles)
    ]
    if known_good:
        approvals.extend(
            Approval(
                approval_id=f"approval.{deployment_id}.known-good.{index}",
                action=ApprovalAction.MARK_KNOWN_GOOD,
                target_id=deployment_id,
                scope_fingerprint=plan.operation_scope_fingerprint,
                role=role,
                actor_id=f"user.{role}",
                decision=ApprovalDecision.APPROVED,
                rationale="Approve exact known-good designation scope.",
                decided_at=BASE_TIME,
            )
            for index, role in enumerate(plan.mark_known_good_approval_roles)
        )
    return approvals


class DeploymentServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service, self.catalog, self.adapter, _ = make_service()
        self.pair = make_build_pair("deploy")
        record_pair(self.service, self.catalog, self.pair)
        self.candidate = create_ready_candidate(
            self.service, self.pair, "candidate.deploy"
        )
        self.note = create_patch_note(
            self.service, self.pair, self.candidate, "patch-note.deploy"
        )

    def prepare(self, deployment_id="deployment.deploy", known_good=False):
        request = PrepareDeploymentRequest(
            deployment_id=deployment_id,
            candidate_id=self.candidate.candidate_id,
            target=DeploymentTarget.LOCAL,
            patch_note_id=self.note.patch_note_id,
            patch_note_revision=self.note.revision,
            idempotency_key=f"key-{deployment_id}",
            expected_mode=ExecutionMode.MOCK,
            mark_known_good=known_good,
        )
        return request, self.service.prepare_deployment(request)

    def test_deploy_requires_exact_approval_and_records_history(self) -> None:
        prepared, plan = self.prepare(known_good=True)
        with self.assertRaisesRegex(PolicyError, "Explicit approval"):
            self.service.deploy(DeployRequest(**prepared.model_dump(), approvals=[]))

        approvals = deployment_approvals(
            plan, prepared.deployment_id, known_good=True
        )
        deployment = self.service.deploy(
            DeployRequest(**prepared.model_dump(), approvals=approvals)
        )
        self.assertEqual(deployment.status, DeploymentStatus.SUCCEEDED)
        self.assertEqual(deployment.mode, ExecutionMode.MOCK)
        self.assertEqual(deployment.artifact_source_mode, ExecutionMode.MOCK)
        self.assertTrue(deployment.known_good)
        self.assertEqual(len(deployment.attempts), 1)
        self.assertTrue(deployment.attempts[0].logs)

    def test_idempotency_returns_same_operation_and_rejects_changed_intent(self) -> None:
        prepared, plan = self.prepare()
        request = DeployRequest(
            **prepared.model_dump(),
            approvals=deployment_approvals(plan, prepared.deployment_id),
        )
        first = self.service.deploy(request)
        second = self.service.deploy(request)
        self.assertEqual(first, second)
        self.assertEqual(self.adapter.activations, [prepared.deployment_id])

        changed = request.model_copy(update={"target": DeploymentTarget.JUDGE})
        with self.assertRaisesRegex(ConflictError, "different immutable inputs"):
            self.service.deploy(changed)

        collision = request.model_copy(update={"idempotency_key": "key-new-collision"})
        with self.assertRaisesRegex(ConflictError, "Deployment ID already exists"):
            self.service.deploy(collision)
        self.assertEqual(self.adapter.activations, [prepared.deployment_id])

    def test_adapter_failure_is_visible_and_retry_appends_attempt(self) -> None:
        service, catalog, adapter, _ = make_service(fail_attempts=1)
        pair = make_build_pair("retry")
        record_pair(service, catalog, pair)
        candidate = create_ready_candidate(service, pair, "candidate.retry")
        note = create_patch_note(service, pair, candidate, "patch-note.retry")
        prepared = PrepareDeploymentRequest(
            deployment_id="deployment.retry",
            candidate_id=candidate.candidate_id,
            target=DeploymentTarget.LOCAL,
            patch_note_id=note.patch_note_id,
            patch_note_revision=note.revision,
            idempotency_key="key-deployment.retry",
            expected_mode=ExecutionMode.MOCK,
        )
        plan = service.prepare_deployment(prepared)
        approvals = deployment_approvals(plan, prepared.deployment_id)
        failed = service.deploy(DeployRequest(**prepared.model_dump(), approvals=approvals))
        self.assertEqual(failed.status, DeploymentStatus.FAILED)
        self.assertTrue(failed.attempts[0].retryable)

        succeeded = service.retry_deployment(
            RetryDeploymentRequest(
                deployment_id=failed.deployment_id,
                approvals=approvals,
            )
        )
        self.assertEqual(succeeded.status, DeploymentStatus.SUCCEEDED)
        self.assertEqual([item.attempt for item in succeeded.attempts], [1, 2])
        self.assertEqual(adapter.activations, [failed.deployment_id])

    def test_wrong_mode_and_stale_patch_note_revision_are_rejected(self) -> None:
        prepared, _ = self.prepare()
        with self.assertRaisesRegex(PolicyError, "requested execution mode"):
            self.service.prepare_deployment(
                prepared.model_copy(update={"expected_mode": ExecutionMode.LIVE})
            )

        entry = self.note.entries[0].model_copy(update={"body": "重新措辞。"})
        from build_release.requests import EditPatchNoteRequest

        self.service.edit_patch_note(
            EditPatchNoteRequest(
                patch_note_id=self.note.patch_note_id,
                editor_id="user.editor",
                entries=[entry],
            )
        )
        with self.assertRaisesRegex(PolicyError, "revision"):
            self.service.prepare_deployment(prepared)

    def test_artifact_drift_after_candidate_approval_blocks_deployment(self) -> None:
        prepared, _ = self.prepare()
        artifact = self.candidate.release_artifact
        self.catalog.register_inspection(
            ArtifactInspection(
                artifact_id=artifact.artifact_id,
                available=True,
                checksum_matches=False,
                size_matches=True,
                observed_checksum="f" * 64,
                observed_size_bytes=artifact.size_bytes,
                reason="Artifact changed after candidate approval.",
            )
        )
        with self.assertRaisesRegex(PolicyError, "missing or corrupt"):
            self.service.prepare_deployment(prepared)

    def test_approval_for_another_scope_is_rejected(self) -> None:
        prepared, plan = self.prepare()
        approvals = deployment_approvals(plan, prepared.deployment_id)
        approvals[0] = approvals[0].model_copy(
            update={"scope_fingerprint": "e" * 64}
        )
        with self.assertRaisesRegex(PolicyError, "exact release action scope"):
            self.service.deploy(
                DeployRequest(**prepared.model_dump(), approvals=approvals)
            )


class LocalFileAdapterTests(unittest.TestCase):
    def test_live_local_publish_verifies_and_atomically_activates(self) -> None:
        with tempfile.TemporaryDirectory() as root_name:
            root = Path(root_name)
            artifacts = root / "artifacts"
            target = root / "target"
            artifacts.mkdir()
            target.mkdir()
            source = artifacts / "player.bin"
            source.write_bytes(b"sceneops-live-local-fixture")
            artifact = ArtifactRef(
                artifact_id="artifact.local.live",
                project_id="project.local",
                game_id="game.local",
                build_run_id="run.local.live",
                artifact_type="unity_player",
                version="1",
                uri="player.bin",
                checksum=file_sha256(source),
                size_bytes=source.stat().st_size,
                source_commit="c" * 40,
                mode=ExecutionMode.LIVE,
                created_at=BASE_TIME,
            )
            catalog = FileArtifactCatalog(artifacts)
            inspection = catalog.inspect(artifact)
            self.assertTrue(inspection.checksum_matches)
            adapter = LocalFileDeploymentAdapter(
                artifacts, {DeploymentTarget.LOCAL: target}
            )
            command = DeploymentCommand(
                operation_id="deployment.local.live",
                candidate_id="candidate.local.live",
                project_id="project.local",
                game_id="game.local",
                build_target_id="target.local",
                target=DeploymentTarget.LOCAL,
                artifact=artifact,
                idempotency_key="key-local-live",
            )
            progress = []
            result = adapter.execute(command, NeverCancelled(), progress.append)
            replay = adapter.execute(command, NeverCancelled(), progress.append)
            self.assertEqual(result.mode, ExecutionMode.LIVE)
            self.assertEqual(result.deployed_checksum, artifact.checksum)
            self.assertEqual(replay.deployed_checksum, artifact.checksum)
            scope = (
                target
                / "targets"
                / "local"
                / "projects"
                / "project.local"
                / "game.local"
                / "target.local"
            )
            active = json.loads((scope / "active.json").read_text(encoding="utf-8"))
            self.assertEqual(active["operation_id"], command.operation_id)
            self.assertEqual(len(list((target / "releases").rglob("player.bin"))), 1)

            newer_command = command.model_copy(
                update={
                    "operation_id": "deployment.local.newer",
                    "candidate_id": "candidate.local.newer",
                    "idempotency_key": "key-local-newer",
                }
            )
            adapter.execute(newer_command, NeverCancelled(), progress.append)
            adapter.execute(command, NeverCancelled(), progress.append)
            active = json.loads((scope / "active.json").read_text(encoding="utf-8"))
            self.assertEqual(active["operation_id"], newer_command.operation_id)
            self.assertTrue(
                (scope / "receipts" / f"{command.operation_id}.json").is_file()
            )

    def test_adapter_rejects_path_escape_and_hardlinks(self) -> None:
        with tempfile.TemporaryDirectory() as root_name:
            root = Path(root_name)
            artifacts = root / "artifacts"
            target = root / "target"
            artifacts.mkdir()
            target.mkdir()
            source = artifacts / "player.bin"
            source.write_bytes(b"safe")
            escaped = ArtifactRef(
                artifact_id="artifact.path.escape",
                project_id="project.local",
                game_id="game.local",
                build_run_id="run.local.path",
                artifact_type="unity_player",
                version="1",
                uri="../outside.bin",
                checksum=file_sha256(source),
                size_bytes=4,
                source_commit="d" * 40,
                mode=ExecutionMode.LIVE,
                created_at=BASE_TIME,
            )
            adapter = LocalFileDeploymentAdapter(
                artifacts, {DeploymentTarget.LOCAL: target}
            )
            command = DeploymentCommand(
                operation_id="deployment.path.escape",
                candidate_id="candidate.path.escape",
                project_id="project.local",
                game_id="game.local",
                build_target_id="target.local",
                target=DeploymentTarget.LOCAL,
                artifact=escaped,
                idempotency_key="key-path-escape",
            )
            with self.assertRaisesRegex(
                AdapterExecutionError, "path or receipt validation"
            ):
                adapter.dry_run(command)

            hardlink = artifacts / "hardlink.bin"
            os.link(source, hardlink)
            linked = escaped.model_copy(
                update={"artifact_id": "artifact.path.hardlink", "uri": "hardlink.bin"}
            )
            inspection = FileArtifactCatalog(artifacts).inspect(linked)
            self.assertFalse(inspection.available)
            self.assertIn("non-hardlinked", inspection.reason)

    def test_adapter_rejects_precreated_release_symlinks_before_writing(self) -> None:
        with tempfile.TemporaryDirectory() as root_name:
            root = Path(root_name)
            artifacts = root / "artifacts"
            target = root / "target"
            outside = root / "outside"
            artifacts.mkdir()
            target.mkdir()
            outside.mkdir()
            source = artifacts / "player.bin"
            source.write_bytes(b"safe-release-bytes")
            (target / "targets").symlink_to(outside, target_is_directory=True)
            artifact = ArtifactRef(
                artifact_id="artifact.local.symlink",
                project_id="project.local",
                game_id="game.local",
                build_run_id="run.local.symlink",
                artifact_type="unity_player",
                version="1",
                uri="player.bin",
                checksum=file_sha256(source),
                size_bytes=source.stat().st_size,
                source_commit="e" * 40,
                mode=ExecutionMode.LIVE,
                created_at=BASE_TIME,
            )
            adapter = LocalFileDeploymentAdapter(
                artifacts, {DeploymentTarget.LOCAL: target}
            )
            command = DeploymentCommand(
                operation_id="deployment.local.symlink",
                candidate_id="candidate.local.symlink",
                project_id="project.local",
                game_id="game.local",
                build_target_id="target.local",
                target=DeploymentTarget.LOCAL,
                artifact=artifact,
                idempotency_key="key-local-symlink",
            )

            with self.assertRaisesRegex(
                AdapterExecutionError, "path or receipt validation"
            ):
                adapter.execute(command, NeverCancelled(), lambda _: None)
            self.assertEqual(list(outside.iterdir()), [])

            (target / "targets").unlink()
            scope = (
                target
                / "targets"
                / "local"
                / "projects"
                / command.project_id
                / command.game_id
                / command.build_target_id
            )
            scope.mkdir(parents=True)
            outside_pointer = outside / "active.json"
            outside_pointer.write_text("do-not-overwrite", encoding="utf-8")
            (scope / "active.json").symlink_to(outside_pointer)

            with self.assertRaisesRegex(
                AdapterExecutionError, "path or receipt validation"
            ):
                adapter.execute(command, NeverCancelled(), lambda _: None)
            self.assertEqual(
                outside_pointer.read_text(encoding="utf-8"), "do-not-overwrite"
            )

    def test_local_active_pointer_is_isolated_by_project_game_and_target(self) -> None:
        with tempfile.TemporaryDirectory() as root_name:
            root = Path(root_name)
            artifacts = root / "artifacts"
            target = root / "target"
            artifacts.mkdir()
            target.mkdir()
            source = artifacts / "player.bin"
            source.write_bytes(b"shared-player-bytes")
            adapter = LocalFileDeploymentAdapter(
                artifacts, {DeploymentTarget.LOCAL: target}
            )

            def command_for(slug: str) -> DeploymentCommand:
                artifact = ArtifactRef(
                    artifact_id=f"artifact.{slug}",
                    project_id=f"project.{slug}",
                    game_id=f"game.{slug}",
                    build_run_id=f"run.{slug}",
                    artifact_type="unity_player",
                    version="1",
                    uri="player.bin",
                    checksum=file_sha256(source),
                    size_bytes=source.stat().st_size,
                    source_commit="f" * 40,
                    mode=ExecutionMode.LIVE,
                    created_at=BASE_TIME,
                )
                return DeploymentCommand(
                    operation_id=f"deployment.{slug}",
                    candidate_id=f"candidate.{slug}",
                    project_id=f"project.{slug}",
                    game_id=f"game.{slug}",
                    build_target_id=f"target.{slug}",
                    target=DeploymentTarget.LOCAL,
                    artifact=artifact,
                    idempotency_key=f"key-local-{slug}",
                )

            first = command_for("remember-home")
            second = command_for("warehouse-escape")
            adapter.execute(first, NeverCancelled(), lambda _: None)
            adapter.execute(second, NeverCancelled(), lambda _: None)

            for command in (first, second):
                pointer = (
                    target
                    / "targets"
                    / "local"
                    / "projects"
                    / command.project_id
                    / command.game_id
                    / command.build_target_id
                    / "active.json"
                )
                self.assertEqual(
                    json.loads(pointer.read_text(encoding="utf-8"))["operation_id"],
                    command.operation_id,
                )


if __name__ == "__main__":
    unittest.main()
