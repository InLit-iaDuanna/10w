from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from engine_unity.contracts import ApprovalState, CommandName, ExecutionMode
from engine_unity.errors import ErrorCode, UnityIntegrationError
from engine_unity.security import validate_command_request
from engine_unity.versioning import validate_unity_version

from engine_unity.tests.support import (
    PROJECT_ROOT,
    approved_change_set,
    context,
    context_for,
    request,
)


class ContractAndSecurityTests(unittest.TestCase):
    def test_command_enum_has_exact_allowlist_and_no_execute_csharp(self) -> None:
        values = {command.value for command in CommandName}
        self.assertEqual(values, {
            "unity.prototype.compose", "unity.prototype.inspect", "unity.prototype.play", "unity.prototype.capture",
            "unity.health", "unity.project.scan", "unity.asset.import", "unity.identity.map",
            "unity.prefab.upsert", "unity.game_object.inspect", "unity.component_property.set",
            "unity.collider.upsert", "unity.navmesh.run", "unity.play.enter", "unity.play.exit",
            "unity.capture", "unity.console.read", "unity.tests.run", "unity.profiler.snapshot", "unity.build.run",
        })
        self.assertNotIn("unity.csharp.execute", values)
        self.assertFalse(any("script" in value or "shell" in value for value in values))

    def test_unknown_command_is_rejected_by_typed_request(self) -> None:
        data = request(CommandName.HEALTH).model_dump(mode="json")
        data["command"] = "unity.csharp.execute"
        with self.assertRaises(ValidationError):
            type(request(CommandName.HEALTH)).model_validate(data)

    def test_path_must_stay_inside_configured_project_root(self) -> None:
        command = request(CommandName.SCAN_PROJECT, root=PROJECT_ROOT.parent)
        with self.assertRaises(UnityIntegrationError) as captured:
            validate_command_request(command, context())
        self.assertEqual(ErrorCode.PATH_OUTSIDE_PROJECT, captured.exception.code)

    def test_symlink_escape_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            root.mkdir()
            (root / "Assets").mkdir()
            (root / "ProjectSettings").mkdir()
            (root / "ProjectSettings" / "ProjectVersion.txt").write_text(
                "m_EditorVersion: 2022.3.62f3c1\n", encoding="utf-8"
            )
            outside = Path(temporary) / "outside"
            outside.mkdir()
            (root / "Builds").symlink_to(outside, target_is_directory=True)
            command = request(
                CommandName.CAPTURE,
                {"output_path": "Builds/capture.png"},
                root=root,
            )
            with self.assertRaises(UnityIntegrationError) as captured:
                validate_command_request(command, context(root))
            self.assertEqual(ErrorCode.PATH_OUTSIDE_PROJECT, captured.exception.code)

    def test_component_property_allowlist_rejects_script_field(self) -> None:
        command = request(
            CommandName.SET_COMPONENT_PROPERTY,
            {
                "sceneops_id": "sobj_home_key",
                "component_type": "MonoBehaviour",
                "property_path": "m_Script",
                "value": "Assets/Evil.cs",
            },
        )
        with self.assertRaises(UnityIntegrationError) as captured:
            validate_command_request(command, context_for(command))
        self.assertEqual(ErrorCode.COMMAND_NOT_ALLOWED, captured.exception.code)

    def test_missing_permission_is_rejected_before_adapter_execution(self) -> None:
        read_only_context = context().model_copy(update={"permissions": {"unity:read"}})
        command = request(
            CommandName.SET_COMPONENT_PROPERTY,
            {
                "sceneops_id": "sobj_home_key",
                "component_type": "BoxCollider",
                "property_path": "m_IsTrigger",
                "value": True,
            },
        )
        with self.assertRaises(UnityIntegrationError) as captured:
            validate_command_request(command, read_only_context)
        self.assertEqual(ErrorCode.PERMISSION_DENIED, captured.exception.code)

    def test_mutation_requires_changeset(self) -> None:
        command = request(
            CommandName.SET_COMPONENT_PROPERTY,
            {
                "sceneops_id": "sobj_home_key",
                "component_type": "BoxCollider",
                "property_path": "m_IsTrigger",
                "value": True,
            },
            change_set=None,
        )
        with self.assertRaises(UnityIntegrationError) as captured:
            validate_command_request(command, context())
        self.assertEqual(ErrorCode.CHANGESET_REQUIRED, captured.exception.code)

    def test_pending_approval_is_valid_for_dry_run_only(self) -> None:
        pending = approved_change_set().model_copy(
            update={"approval_state": ApprovalState.PENDING}
        )
        command = request(
            CommandName.SET_COMPONENT_PROPERTY,
            {
                "sceneops_id": "sobj_home_key",
                "component_type": "BoxCollider",
                "property_path": "m_IsTrigger",
                "value": True,
            },
            mode=ExecutionMode.PLANNED,
            change_set=pending,
        )
        validate_command_request(command, context(), enforce_approval=False)
        with self.assertRaises(UnityIntegrationError) as captured:
            validate_command_request(command, context(), enforce_approval=True)
        self.assertEqual(ErrorCode.APPROVAL_REQUIRED, captured.exception.code)

    def test_self_reported_approval_without_trusted_record_is_rejected(self) -> None:
        command = request(
            CommandName.SET_COMPONENT_PROPERTY,
            {
                "sceneops_id": "sobj_home_key",
                "component_type": "BoxCollider",
                "property_path": "m_IsTrigger",
                "value": True,
            },
        )
        with self.assertRaises(UnityIntegrationError) as captured:
            validate_command_request(command, context())
        self.assertEqual(ErrorCode.APPROVAL_REQUIRED, captured.exception.code)

    def test_approved_changeset_cannot_be_reused_for_a_different_payload(self) -> None:
        original = request(
            CommandName.SET_COMPONENT_PROPERTY,
            {
                "sceneops_id": "sobj_home_key",
                "component_type": "BoxCollider",
                "property_path": "m_IsTrigger",
                "value": True,
            },
        )
        changed_payload = {
            "sceneops_id": "sobj_home_key",
            "component_type": "BoxCollider",
            "property_path": "m_IsTrigger",
            "value": False,
        }
        reused = request(
            CommandName.SET_COMPONENT_PROPERTY,
            changed_payload,
            change_set=approved_change_set(
                CommandName.SET_COMPONENT_PROPERTY, changed_payload
            ),
        )
        with self.assertRaises(UnityIntegrationError) as captured:
            validate_command_request(reused, context_for(original))
        self.assertEqual(ErrorCode.APPROVAL_REQUIRED, captured.exception.code)

    def test_changeset_must_match_command_payload_and_stable_targets(self) -> None:
        command = request(
            CommandName.SET_COMPONENT_PROPERTY,
            {
                "sceneops_id": "sobj_home_key",
                "component_type": "BoxCollider",
                "property_path": "m_IsTrigger",
                "value": True,
            },
        )
        mismatched = command.model_copy(
            update={
                "change_set": command.change_set.model_copy(
                    update={"target_object_ids": ["sobj_other"]}
                )
            }
        )
        with self.assertRaises(UnityIntegrationError) as captured:
            validate_command_request(mismatched, context_for(command))
        self.assertEqual(ErrorCode.CHANGESET_MISMATCH, captured.exception.code)

    def test_import_rejects_executable_and_extension_confusion(self) -> None:
        for source_path, destination in [
            ("Assets/Staging/Evil.cs", "Assets/Imported/Evil.cs"),
            ("Assets/Staging/Evil.dll", "Assets/Imported/Evil.dll"),
            ("Assets/Staging/Evil.asmdef", "Assets/Imported/Evil.asmdef"),
            ("Assets/Staging/Evil.rsp", "Assets/Imported/Evil.rsp"),
            ("Assets/Staging/Model.fbx", "Assets/Imported/Model.obj"),
        ]:
            with self.subTest(source_path=source_path, destination=destination):
                command = request(
                    CommandName.IMPORT_ASSET,
                    {
                        "source_asset_id": "ast_fixture",
                        "source_asset_version_id": "astv_fixture_001",
                        "source_path": source_path,
                        "destination_asset_path": destination,
                        "manifest_path": "Assets/Staging/model.sceneops-unity.json",
                    },
                    change_set=None,
                )
                with self.assertRaises(UnityIntegrationError) as captured:
                    validate_command_request(command, context())
                self.assertEqual(ErrorCode.INVALID_PAYLOAD, captured.exception.code)

    def test_base_version_mismatch_is_rejected(self) -> None:
        command = request(CommandName.HEALTH)
        mismatched_context = context(base_version="git:newer")
        with self.assertRaises(UnityIntegrationError) as captured:
            validate_command_request(command, mismatched_context)
        self.assertEqual(ErrorCode.BASE_VERSION_MISMATCH, captured.exception.code)

    def test_unity_version_policy_accepts_only_the_pinned_editor(self) -> None:
        validate_unity_version("2022.3.62f3c1")
        for unsupported in ["2021.3.45f1", "2022.3.61f1", "2023.2.0f1"]:
            with self.subTest(version=unsupported):
                with self.assertRaises(UnityIntegrationError) as captured:
                    validate_unity_version(unsupported)
                self.assertEqual(ErrorCode.VERSION_INCOMPATIBLE, captured.exception.code)


if __name__ == "__main__":
    unittest.main()
