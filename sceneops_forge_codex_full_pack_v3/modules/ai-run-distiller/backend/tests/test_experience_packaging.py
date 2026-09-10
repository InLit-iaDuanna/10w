"""Installed-wheel seed regression, isolated from the checkout's distiller package.

This test builds locally with Hatchling; it never installs dependencies or calls a model.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


class ExperiencePackagingTests(unittest.TestCase):
    def test_wheel_imports_seed_from_unrelated_working_directory(self):
        backend = Path(__file__).resolve().parents[1]
        checkout_source = backend / "src"
        # Preserve the test environment's dependencies, excluding this source package.
        dependency_paths = [str(Path(value).resolve()) for value in sys.path
            if value and Path(value).resolve() != checkout_source]
        with TemporaryDirectory() as directory:
            temporary = Path(directory)
            wheel_directory = temporary / "wheels"
            wheel_directory.mkdir()
            unrelated = temporary / "unrelated"
            unrelated.mkdir()
            environment = dict(os.environ)
            environment["PYTHONPATH"] = os.pathsep.join(dependency_paths)
            built = subprocess.run(
                [sys.executable, "-c",
                 "from hatchling.build import build_wheel; import sys; print(build_wheel(sys.argv[1]))",
                 str(wheel_directory)],
                cwd=backend, env=environment, capture_output=True, text=True, timeout=60,
            )
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            wheels = list(wheel_directory.glob("sceneops_ai_run_distiller-*.whl"))
            self.assertEqual(len(wheels), 1, built.stdout)
            script = r'''
import asyncio
import json
from pathlib import Path
import sys

wheel, database, source, paths = sys.argv[1:]
source = Path(source).resolve()
sys.path[:] = [wheel] + [p for p in json.loads(paths) if Path(p).resolve() != source]
import sceneops_ai_distiller
from sceneops_ai_distiller import ExperienceService

assert ".whl/sceneops_ai_distiller/" in sceneops_ai_distiller.__file__, sceneops_ai_distiller.__file__
assert str(source) not in sys.path

class NeverCalledProvider:
    def settings(self):
        raise AssertionError("Seed import must not inspect a model")
    async def generate(self, *args, **kwargs):
        raise AssertionError("Seed import must not invoke a model")

service = ExperienceService(database, NeverCalledProvider())
entries = service.entries(None, scope="shared")
evidence_ids = {evidence.id for entry in entries for evidence in entry.evidence}
assert len(entries) == 26, len(entries)
assert evidence_ids == {f"S{i:02d}" for i in range(1, 52)}, evidence_ids
assert service.status().pending_sources == 0
assert service.status().calls_used == 0
asyncio.run(service.close())
print(json.dumps({"entries": len(entries), "evidence": len(evidence_ids)}))
'''
            imported = subprocess.run(
                [sys.executable, "-c", script, str(wheels[0]), str(temporary / "seed.sqlite3"),
                 str(checkout_source), json.dumps(dependency_paths)],
                cwd=unrelated, env=environment, capture_output=True, text=True, timeout=60,
            )
            self.assertEqual(imported.returncode, 0, imported.stdout + imported.stderr)
            self.assertEqual(json.loads(imported.stdout), {"entries": 26, "evidence": 51})
