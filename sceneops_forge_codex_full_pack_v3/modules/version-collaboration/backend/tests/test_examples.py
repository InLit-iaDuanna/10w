from __future__ import annotations

import json
import unittest
from pathlib import Path

from version_collaboration.base import ExecutionMode, VersionReference
from version_collaboration.diff_engine import FourLayerDiffEngine
from version_collaboration.git_models import (
    GitFileChange,
    GitRepositoryState,
    GitVersionDiff,
    LfsPointer,
)
from version_collaboration.review_models import CreateReviewCommand

from support import NOW


MODULE_ROOT = Path(__file__).resolve().parents[2]


class ExampleFixtureTests(unittest.TestCase):
    def test_hero_and_second_game_use_same_four_layer_implementation(self) -> None:
        results = {
            name: self._load_and_build(name)
            for name in ("remember-home-review.json", "warehouse-escape-review.json")
        }

        self.assertEqual(set(results), {"remember-home-review.json", "warehouse-escape-review.json"})
        self.assertTrue(all(result.mode == ExecutionMode.MOCK for result in results.values()))
        self.assertEqual(results["remember-home-review.json"].visual.changed_samples, 2)
        self.assertEqual(results["warehouse-escape-review.json"].visual.changed_samples, 1)
        self.assertTrue(all(result.semantic.changes for result in results.values()))
        self.assertTrue(all(result.behavior.changes for result in results.values()))

    def test_every_fixture_execution_claim_is_mock(self) -> None:
        for name in ("remember-home-review.json", "warehouse-escape-review.json"):
            payload = json.loads((MODULE_ROOT / "contracts" / "examples" / name).read_text())
            serialized = json.dumps(payload)
            self.assertNotIn('"mode": "live"', serialized)
            self.assertNotIn('"mode": "cached"', serialized)
            self.assertEqual(payload["expected"]["mode"], "mock")

    def _load_and_build(self, name: str):
        payload = json.loads((MODULE_ROOT / "contracts" / "examples" / name).read_text())
        command = CreateReviewCommand.model_validate(payload["command"])
        base = VersionReference(
            repository_id=command.repository_id,
            commit_id=command.base_commit,
            branch="fixture/base",
        )
        target = VersionReference(
            repository_id=command.repository_id,
            commit_id=command.target_commit,
            branch="fixture/target",
        )
        git_diff = GitVersionDiff(
            base=base,
            target=target,
            changes=tuple(GitFileChange.model_validate(item) for item in payload["expected"]["file_changes"]),
            lfs_pointers=tuple(LfsPointer.model_validate(item) for item in payload["expected"]["lfs_pointers"]),
            mode=ExecutionMode.MOCK,
        )
        state = GitRepositoryState(
            project_id=command.project_id,
            version=target,
            dirty=False,
            conflicted=False,
            changes=(),
            lfs_pointers=(),
            branches=(),
            commits=(),
            mode=ExecutionMode.MOCK,
            captured_at=NOW,
        )
        return FourLayerDiffEngine().build(
            diff_bundle_id=f"diff_fixture_{name.removesuffix('.json').replace('-', '_')}",
            git_diff=git_diff,
            repository_state=state,
            semantic_before=command.semantic_before,
            semantic_after=command.semantic_after,
            visual_before=command.visual_before,
            visual_after=command.visual_after,
            behavior_before=command.behavior_before,
            behavior_after=command.behavior_after,
            target_ids=command.target_ids,
            active_locks=(),
            actor_id="user_fixture",
            sealed_at=NOW,
        )


if __name__ == "__main__":
    unittest.main()
