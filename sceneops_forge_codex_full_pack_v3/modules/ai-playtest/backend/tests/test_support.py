from __future__ import annotations

import json
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


MODULE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(MODULE_ROOT / "backend" / "src"))
sys.path.insert(0, str(MODULE_ROOT))

from adapters import DeterministicPlaytestRunnerAdapter  # noqa: E402
from ai_playtest import AIPlaytestService, InMemoryPlaytestRepository  # noqa: E402
from ai_playtest.schemas import ExecutionMode, RunRequest, TestCase  # noqa: E402


EXAMPLES = MODULE_ROOT / "contracts" / "examples"
FIXED_NOW = datetime(2026, 9, 4, 4, 0, tzinfo=timezone.utc)


def fixed_clock() -> datetime:
    return FIXED_NOW


def load_json(filename: str) -> dict:
    return json.loads((EXAMPLES / filename).read_text(encoding="utf-8"))


def load_test_case(filename: str = "find-my-way-home-key-door.test-case.json") -> TestCase:
    return TestCase.model_validate(load_json(filename))


def make_adapter(filename: str, **overrides) -> DeterministicPlaytestRunnerAdapter:
    fixture = deepcopy(load_json(filename))
    fixture.update(overrides)
    return DeterministicPlaytestRunnerAdapter(fixture)


def run_fixture(
    runtime_filename: str,
    run_id: str,
    repository: Optional[InMemoryPlaytestRepository] = None,
    test_case: Optional[TestCase] = None,
    **fixture_overrides,
):
    adapter = make_adapter(runtime_filename, **fixture_overrides)
    repository = repository or InMemoryPlaytestRepository()
    service = AIPlaytestService(adapter, repository, clock=fixed_clock)
    case = test_case or load_test_case()
    request = RunRequest(
        run_id=run_id,
        test_case=case,
        build=adapter.build,
        execution_mode=ExecutionMode.MOCK,
    )
    return service.run(request), adapter, service, repository
