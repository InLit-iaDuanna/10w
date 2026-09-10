from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from version_collaboration.base import ExecutionMode
from version_collaboration.errors import ErrorCode, VersionCollaborationError
from version_collaboration.git_adapter import GitCliAdapter, parse_lfs_pointer
from version_collaboration.git_models import GitChangeKind, GitRollbackCommand
from version_collaboration.git_runner import GitCommandOutput, GitCommandRunner


class GitCliAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self._git("init", "-b", "main")
        self._git("config", "user.name", "SceneOps Test")
        self._git("config", "user.email", "sceneops@example.invalid")
        self._write("gameplay.txt", "base\n")
        self._git("add", "gameplay.txt")
        self._git("commit", "-m", "base")
        self.base = self._git("rev-parse", "HEAD").stdout.strip()
        self.adapter = GitCliAdapter([self.root])

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_status_lists_branch_commit_and_dirty_state(self) -> None:
        self._write("gameplay.txt", "dirty\n")

        state = self.adapter.inspect("project_test", "repository_test", self.root)

        self.assertTrue(state.dirty)
        self.assertFalse(state.conflicted)
        self.assertEqual(state.version.branch, "main")
        self.assertEqual(state.version.object_format, "sha1")
        self.assertEqual(state.changes[0].kind, GitChangeKind.MODIFIED)
        self.assertTrue(state.branches[0].current)
        self.assertEqual(state.commits[0].subject, "base")
        self.assertEqual(state.mode, ExecutionMode.LIVE)

    def test_offline_repository_is_structured_blocked_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            outside = Path(directory)
            adapter = GitCliAdapter([outside])

            health = adapter.health_check(outside)
            self.assertFalse(health.connected)
            self.assertEqual(health.mode, ExecutionMode.BLOCKED)
            with self.assertRaises(VersionCollaborationError) as raised:
                adapter.inspect("project_test", "repository_test", outside)
            self.assertEqual(raised.exception.code, ErrorCode.GIT_OFFLINE)

    def test_project_root_allowlist_rejects_outside_path(self) -> None:
        with tempfile.TemporaryDirectory() as other:
            with self.assertRaises(VersionCollaborationError) as raised:
                self.adapter.health_check(Path(other))
            self.assertEqual(raised.exception.code, ErrorCode.PATH_OUTSIDE_PROJECT)

    def test_lfs_pointer_metadata_is_parsed_without_hashing_content(self) -> None:
        pointer_text = (
            "version https://git-lfs.github.com/spec/v1\n"
            f"oid sha256:{'a' * 64}\n"
            "size 4096\n"
        )
        self._write(".gitattributes", "*.glb filter=lfs diff=lfs merge=lfs -text lockable\n")
        self._write("Assets/Key.glb", pointer_text)
        self._git("add", ".gitattributes", "Assets/Key.glb")
        self._git("commit", "-m", "add lfs pointer")
        target = self._git("rev-parse", "HEAD").stdout.strip()

        result = self.adapter.compare_versions(
            "repository_test", self.root, self.base, target
        )

        self.assertEqual(len(result.lfs_pointers), 1)
        self.assertEqual(result.lfs_pointers[0].object_id, "a" * 64)
        self.assertEqual(result.lfs_pointers[0].size, 4096)
        self.assertEqual(result.lfs_pointers[0].algorithm, "sha256")
        self.assertTrue(result.lfs_pointers[0].lock_required)
        key_change = next(change for change in result.changes if change.path == "Assets/Key.glb")
        self.assertTrue(key_change.binary)

    def test_invalid_lfs_pointer_is_not_mislabeled(self) -> None:
        pointer = parse_lfs_pointer(
            "Assets/Broken.glb",
            "version https://git-lfs.github.com/spec/v1\noid sha256:not-valid\nsize 4\n",
        )
        self.assertIsNone(pointer)

    def test_deleted_lfs_pointer_stays_binary_and_retains_metadata(self) -> None:
        pointer_text = (
            "version https://git-lfs.github.com/spec/v1\n"
            f"oid sha256:{'c' * 64}\n"
            "size 8192\n"
        )
        self._write(".gitattributes", "*.glb filter=lfs diff=lfs merge=lfs -text lockable\n")
        self._write("Assets/Deleted.glb", pointer_text)
        self._git("add", ".gitattributes", "Assets/Deleted.glb")
        self._git("commit", "-m", "add deleted LFS fixture")
        with_asset = self._git("rev-parse", "HEAD").stdout.strip()
        self._git("rm", "Assets/Deleted.glb")
        self._git("commit", "-m", "delete LFS fixture")
        without_asset = self._git("rev-parse", "HEAD").stdout.strip()

        result = self.adapter.compare_versions(
            "repository_test", self.root, with_asset, without_asset
        )

        deleted = next(item for item in result.changes if item.path == "Assets/Deleted.glb")
        self.assertEqual(deleted.kind, GitChangeKind.DELETED)
        self.assertTrue(deleted.binary)
        self.assertEqual(result.lfs_pointers[0].object_id, "c" * 64)

    def test_directory_rename_keeps_non_lfs_binary_numstat(self) -> None:
        old_path = self.root / "Assets" / "OldGroup" / "mesh.bin"
        old_path.parent.mkdir(parents=True, exist_ok=True)
        old_path.write_bytes(b"\x00binary-before")
        self._git("add", "Assets/OldGroup/mesh.bin")
        self._git("commit", "-m", "add binary mesh")
        binary_base = self._git("rev-parse", "HEAD").stdout.strip()
        self._git("mv", "Assets/OldGroup", "Assets/NewGroup")
        self._git("commit", "-m", "rename binary directory")
        binary_target = self._git("rev-parse", "HEAD").stdout.strip()

        diff = self.adapter.compare_versions(
            "repository_test", self.root, binary_base, binary_target
        )

        self.assertEqual(diff.changes[0].old_path, "Assets/OldGroup/mesh.bin")
        self.assertEqual(diff.changes[0].path, "Assets/NewGroup/mesh.bin")
        self.assertTrue(diff.changes[0].binary)

    def test_unresolved_merge_conflict_is_detected(self) -> None:
        self._git("checkout", "-b", "feature")
        self._write("gameplay.txt", "feature\n")
        self._git("commit", "-am", "feature")
        self._git("checkout", "main")
        self._write("gameplay.txt", "main\n")
        self._git("commit", "-am", "main")
        merge = self._git("merge", "feature", check=False)
        self.assertNotEqual(merge.returncode, 0)

        state = self.adapter.inspect("project_test", "repository_test", self.root)

        self.assertTrue(state.dirty)
        self.assertTrue(state.conflicted)
        self.assertEqual(state.changes[0].kind, GitChangeKind.CONFLICT)

    def test_rollback_creates_forward_commit_and_is_idempotent(self) -> None:
        self._write("gameplay.txt", "target\n")
        self._git("commit", "-am", "target")
        target = self._git("rev-parse", "HEAD").stdout.strip()
        command = GitRollbackCommand(
            operation_id="operation_rollback_1",
            proposal_id="rollback_1",
            approval_id="approval_1",
            expected_head=target,
            target_commit=self.base,
            commit_message="Approved rollback test",
        )

        preview = self.adapter.dry_run_rollback(self.root, command)
        first = self.adapter.execute_rollback(self.root, command)
        second = self.adapter.execute_rollback(self.root, command)

        self.assertEqual(preview.blocked_reasons, ())
        self.assertEqual(self._read("gameplay.txt"), "base\n")
        self.assertEqual(first, second)
        self.assertEqual(first.previous_head, target)
        self.assertNotIn(first.resulting_head, {self.base, target})
        self.assertEqual(self._git("rev-list", "--count", "HEAD").stdout.strip(), "3")
        self.assertIn(
            "SceneOps-Operation: operation_rollback_1",
            self._git("show", "-s", "--format=%B", "HEAD").stdout,
        )

    def test_rollback_rejects_forged_operation_marker(self) -> None:
        self._write("gameplay.txt", "forged\n")
        self._git(
            "commit",
            "-am",
            "forged marker\n\nSceneOps-Operation: operation_forged_1",
        )
        forged_head = self._git("rev-parse", "HEAD").stdout.strip()
        command = GitRollbackCommand(
            operation_id="operation_forged_1",
            proposal_id="rollback_forged_1",
            approval_id="approval_forged_1",
            expected_head=forged_head,
            target_commit=self.base,
            commit_message="Approved rollback test",
        )

        with self.assertRaises(VersionCollaborationError) as raised:
            self.adapter.execute_rollback(self.root, command)

        self.assertEqual(raised.exception.code, ErrorCode.DUPLICATE_RECORD)

    def test_rollback_does_not_accept_an_exact_operation_on_another_ref(self) -> None:
        self._write("gameplay.txt", "target\n")
        self._git("commit", "-am", "target")
        target = self._git("rev-parse", "HEAD").stdout.strip()
        command = GitRollbackCommand(
            operation_id="operation_side_ref_1",
            proposal_id="rollback_side_ref_1",
            approval_id="approval_side_ref_1",
            expected_head=target,
            target_commit=self.base,
            commit_message="Approved rollback side ref",
        )
        tree = self._git("rev-parse", f"{self.base}^{{tree}}").stdout.strip()
        side_commit = self._git(
            "commit-tree",
            tree,
            "-p",
            target,
            "-m",
            self._rollback_message(command),
        ).stdout.strip()
        self._git("branch", "operation-side", side_commit)

        with self.assertRaises(VersionCollaborationError) as raised:
            self.adapter.execute_rollback(self.root, command)

        self.assertEqual(raised.exception.code, ErrorCode.DUPLICATE_RECORD)
        self.assertEqual(self._git("rev-parse", "HEAD").stdout.strip(), target)

    def test_rollback_does_not_report_success_before_worktree_sync(self) -> None:
        self._write("gameplay.txt", "target\n")
        self._git("commit", "-am", "target")
        target = self._git("rev-parse", "HEAD").stdout.strip()
        command = GitRollbackCommand(
            operation_id="operation_incomplete_sync_1",
            proposal_id="rollback_incomplete_sync_1",
            approval_id="approval_incomplete_sync_1",
            expected_head=target,
            target_commit=self.base,
            commit_message="Approved rollback incomplete sync",
        )
        tree = self._git("rev-parse", f"{self.base}^{{tree}}").stdout.strip()
        created = self._git(
            "commit-tree",
            tree,
            "-p",
            target,
            "-m",
            self._rollback_message(command),
        ).stdout.strip()
        self._git("update-ref", "HEAD", created, target)

        with self.assertRaises(VersionCollaborationError) as raised:
            self.adapter.execute_rollback(self.root, command)

        self.assertEqual(raised.exception.code, ErrorCode.GIT_DIRTY)

    def test_rollback_fails_closed_when_head_advances_after_restore(self) -> None:
        test_case = self

        class AdvanceAfterRestoreRunner(GitCommandRunner):
            def run(self, operation, args, **kwargs):
                result = super().run(operation, args, **kwargs)
                if operation == "rollback_worktree_sync":
                    test_case._git(
                        "commit",
                        "--allow-empty",
                        "-m",
                        "concurrent commit after rollback restore",
                    )
                return result

        self._write("gameplay.txt", "target\n")
        self._git("commit", "-am", "target")
        target = self._git("rev-parse", "HEAD").stdout.strip()
        adapter = GitCliAdapter(
            [self.root], runner=AdvanceAfterRestoreRunner()
        )
        command = GitRollbackCommand(
            operation_id="operation_postcondition_1",
            proposal_id="rollback_postcondition_1",
            approval_id="approval_postcondition_1",
            expected_head=target,
            target_commit=self.base,
            commit_message="Approved rollback postcondition",
        )

        with self.assertRaises(VersionCollaborationError) as raised:
            adapter.execute_rollback(self.root, command)

        self.assertEqual(raised.exception.code, ErrorCode.GIT_CONFLICT)

    def test_rollback_rejects_dirty_or_stale_head(self) -> None:
        self._write("gameplay.txt", "committed advance\n")
        self._git("add", "gameplay.txt")
        self._git("commit", "-m", "advance beyond approved base")
        self._write("gameplay.txt", "dirty\n")
        command = GitRollbackCommand(
            operation_id="operation_rollback_2",
            proposal_id="rollback_2",
            approval_id="approval_2",
            expected_head=self.base,
            target_commit=self.base,
            commit_message="Blocked rollback",
        )

        preview = self.adapter.dry_run_rollback(self.root, command)

        self.assertIn("stale_base", preview.blocked_reasons)
        self.assertIn("dirty_worktree", preview.blocked_reasons)
        with self.assertRaises(VersionCollaborationError) as raised:
            self.adapter.execute_rollback(self.root, command)
        self.assertEqual(raised.exception.code, ErrorCode.STALE_BASE)

    def test_lfs_lock_is_explicitly_unavailable_without_cli(self) -> None:
        if self.adapter.capabilities(self.root).lfs_cli_available:
            self.skipTest("Host has Git LFS; this test covers the unavailable capability path.")

        with self.assertRaises(VersionCollaborationError) as raised:
            self.adapter.acquire_lfs_lock(
                self.root, "Assets/Key.glb", "operation_lock_1"
            )

        self.assertEqual(raised.exception.code, ErrorCode.GIT_OFFLINE)
        self.assertIn("remains blocked", raised.exception.message)

    def test_lfs_unlock_parses_the_official_id_result_array(self) -> None:
        class UnlockRunner:
            def run(self, operation, args, **kwargs):
                self.operation = operation
                self.args = args
                return GitCommandOutput(
                    stdout='[{"id":"lock-42","unlocked":true}]',
                    stderr="",
                    return_code=0,
                )

        runner = UnlockRunner()
        self.adapter._runner = runner
        self.adapter._require_lfs = lambda project_root: project_root

        result = self.adapter.release_lfs_lock(
            self.root,
            "lock-42",
            "Assets/Key.glb",
            "operation_unlock_1",
        )

        self.assertEqual(result.external_lock_id, "lock-42")
        self.assertEqual(result.path, "Assets/Key.glb")
        self.assertEqual(
            runner.args,
            ("lfs", "unlock", "--json", "--id", "lock-42"),
        )

    def _git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ("git", *args),
            cwd=self.root,
            check=check,
            capture_output=True,
            text=True,
        )

    def _write(self, path: str, content: str) -> None:
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)

    def _read(self, path: str) -> str:
        return (self.root / path).read_text()

    @staticmethod
    def _rollback_message(command: GitRollbackCommand) -> str:
        return (
            f"{command.commit_message}\n\n"
            f"SceneOps-Operation: {command.operation_id}\n"
            f"SceneOps-Proposal: {command.proposal_id}\n"
            f"SceneOps-Approval: {command.approval_id}\n"
            f"SceneOps-Expected-Head: {command.expected_head}\n"
            f"SceneOps-Target: {command.target_commit}"
        )


if __name__ == "__main__":
    unittest.main()
