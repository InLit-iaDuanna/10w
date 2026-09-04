import json
import subprocess
import sys
import unittest
from datetime import datetime
from pathlib import Path

from pydantic import ValidationError

from sceneops_core_contracts import (
    ActorReference,
    ArtifactProvenance,
    ChangeSet,
    CommandEnvelope,
    ExecutionMode,
    WorkbenchContext,
)


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


class CoreContractTests(unittest.TestCase):
    def test_valid_changeset_fixture_is_reviewable(self):
        fixture = json.loads(
            (PACKAGE_ROOT / "fixtures" / "valid-changeset.json").read_text()
        )
        change_set = ChangeSet.model_validate(fixture)
        self.assertEqual(change_set.target.object_ids, ["sobj_fixture001"])
        self.assertTrue(change_set.dry_run_supported)

    def test_broad_changeset_without_approval_fails(self):
        fixture = json.loads(
            (PACKAGE_ROOT / "fixtures" / "valid-changeset.json").read_text()
        )
        fixture["approval_requirements"] = []
        with self.assertRaisesRegex(ValidationError, "approval_requirements"):
            ChangeSet.model_validate(fixture)

    def test_cached_provenance_requires_real_source_run(self):
        fixture = json.loads(
            (PACKAGE_ROOT / "fixtures" / "invalid-cached-provenance.json").read_text()
        )
        with self.assertRaisesRegex(ValidationError, "cached_from_run_id"):
            ArtifactProvenance.model_validate(fixture)

    def test_actor_type_and_id_prefix_must_agree(self):
        with self.assertRaisesRegex(ValidationError, "usr_"):
            ActorReference(type="user", id="agt_fixture0001")

    def test_timestamp_must_be_utc(self):
        with self.assertRaisesRegex(ValidationError, "UTC"):
            CommandEnvelope(
                command_id="cmd_fixture0001",
                command_type="fixture.run",
                issued_at=datetime(2026, 9, 4),
                correlation_id="corr_fixture001",
                actor={"type": "user", "id": "usr_fixture0001"},
                mode="mock",
                payload={},
            )

    def test_workbench_context_rejects_wrong_id_kind(self):
        with self.assertRaises(ValidationError):
            WorkbenchContext(project_id="scn_fixture0001")

    def test_execution_modes_are_complete(self):
        self.assertEqual(
            {mode.value for mode in ExecutionMode},
            {"live", "cached", "mock", "planned", "blocked"},
        )

    def test_generated_contracts_are_current(self):
        result = subprocess.run(
            [sys.executable, str(PACKAGE_ROOT / "tools" / "generate.py"), "--check"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
