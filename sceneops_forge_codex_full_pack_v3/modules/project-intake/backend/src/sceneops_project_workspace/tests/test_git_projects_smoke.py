"""Real Git smoke confined to standard-library temporary folders."""
import subprocess
from pathlib import Path

import tempfile
import unittest
from unittest.mock import patch

from sceneops_project_workspace import GitProjectError, SqliteWorkspaceRepository


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


class GitProjectsSmokeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="sceneops-git-smoke-")
        self.addCleanup(temporary.cleanup)
        self.tmp_path = Path(temporary.name).resolve()

    def test_confirm_version_preserves_index_and_reuses_card_worktree(self):
        tmp_path = self.tmp_path
        repository = SqliteWorkspaceRepository(tmp_path / "data" / "workspace.sqlite")
        project = repository.create_folder_project(tmp_path, "game")
        root = Path(project.root_path)
        (root / "existing.txt").write_text("user staged content")
        git(root, "add", "existing.txt")
        staged = git(root, "ls-files", "--stage", "--", "existing.txt")
        payload = {"title": "A tiny game", "version": 1}
        version = repository.commit_design_version(project.project_id, 1, payload)
        assert git(root, "ls-files", "--stage", "--", "existing.txt") == staged
        assert git(root, "diff", "--cached", "--name-status") == "A\texisting.txt"
        assert git(root, "ls-tree", "--name-only", "-r", version["commit"]) == ".sceneops/design/snapshots/v1.json"
        assert repository.commit_design_version(project.project_id, 1, payload) == version
        first = repository.open_card_worktree(project.project_id, "card_one", "First card", {"goal": "Prototype"})
        second = repository.open_card_worktree(project.project_id, "card_one", "First card")
        assert first == second
        worktree = Path(first["worktree_path"])
        assert git(worktree, "branch", "--show-current") == "codex/card-card_one"
        assert git(root, "branch", "--show-current") == "codex/integration"
        assert (worktree / ".sceneops" / "card-brief.json").is_file()
        assert (root / "existing.txt").read_text() == "user staged content"


    def test_unconfirmed_and_unknown_card_worktrees_are_refused(self):
        tmp_path = self.tmp_path
        repository = SqliteWorkspaceRepository(tmp_path / "data" / "workspace.sqlite")
        project = repository.create_folder_project(tmp_path, "game")
        with self.assertRaisesRegex(GitProjectError, "正式策划版本"):
            repository.open_card_worktree(project.project_id, "card_one", "First")
        repository.commit_design_version(project.project_id, 1, {"version": 1})
        root = Path(project.root_path)
        git(root, "branch", "codex/card-card_one")
        with self.assertRaisesRegex(GitProjectError, "占用"):
            repository.open_card_worktree(project.project_id, "card_one", "First")

    def test_registered_card_lookup_never_creates_a_worktree(self):
        repository = SqliteWorkspaceRepository(self.tmp_path / 'data' / 'workspace.sqlite')
        project = repository.create_folder_project(self.tmp_path, 'game')
        repository.commit_design_version(project.project_id, 1, {'version': 1})
        with self.assertRaises(GitProjectError):
            repository.get_card_worktree(project.project_id, 'missing_card')
        self.assertFalse((self.tmp_path / 'data' / 'card-worktrees').exists())
        opened = repository.open_card_worktree(project.project_id, 'card_one', 'Card', {'goal': 'source'})
        worktree = Path(opened['worktree_path'])
        before = git(worktree, 'status', '--porcelain')
        record = repository.get_card_worktree(project.project_id, 'card_one')
        self.assertEqual(record['worktree_path'], str(worktree))
        self.assertEqual(record['project_id'], project.project_id)
        self.assertEqual(git(worktree, 'status', '--porcelain'), before)
        git(worktree, 'checkout', '-b', 'codex/changed-branch')
        with self.assertRaises(GitProjectError):
            repository.get_card_worktree(project.project_id, 'card_one')


    def test_snapshot_staged_conflict_is_preserved(self):
        tmp_path = self.tmp_path
        repository = SqliteWorkspaceRepository(tmp_path / "data" / "workspace.sqlite")
        project = repository.create_folder_project(tmp_path, "game")
        root = Path(project.root_path)
        payload = {"version": 1}
        artifact = repository.create_design_snapshot(project.project_id, payload, 1)
        snapshot = Path(artifact.path)
        original = snapshot.read_bytes()
        snapshot.write_text('{"user_staged": true}')
        git(root, "add", ".sceneops/design/snapshots/v1.json")
        snapshot.write_bytes(original)
        staged = git(root, "ls-files", "--stage")
        with self.assertRaisesRegex(GitProjectError, "暂存修改"):
            repository.commit_design_version(project.project_id, 1, payload)
        assert git(root, "ls-files", "--stage") == staged
        assert not (root / ".git" / "index.lock").exists()


    def test_pending_version_recovers_index_without_phantom_deletion(self):
        tmp_path = self.tmp_path
        repository = SqliteWorkspaceRepository(tmp_path / "data" / "workspace.sqlite")
        project = repository.create_folder_project(tmp_path, "game")
        root = Path(project.root_path)
        from sceneops_project_workspace.git_projects import GitProjects

        with patch.object(GitProjects, "_finish_index", side_effect=OSError("Interrupted before publishing prepared index")):
            with self.assertRaisesRegex(OSError, "Interrupted"):
                repository.commit_design_version(project.project_id, 1, {"version": 1})
        commit = git(root, "rev-parse", "HEAD")
        result = repository.commit_design_version(project.project_id, 1, {"version": 1})
        assert result["commit"] == commit
        assert git(root, "status", "--porcelain") == ""


if __name__ == "__main__":
    unittest.main()
