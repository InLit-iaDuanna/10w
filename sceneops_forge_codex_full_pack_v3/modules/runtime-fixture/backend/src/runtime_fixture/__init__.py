"""Public backend entrypoint for the deterministic runtime fixture."""

from .generated_manifest import GENERATED_MODULE_MANIFEST


class RuntimeFixtureError(RuntimeError):
    code = "FIXTURE_REQUESTED_FAILURE"
    status = "failed"
    mode = "mock"
    retryable = False


def run_runtime_fixture(should_fail=False):
    if should_fail:
        raise RuntimeFixtureError("Fixture 请求失败。")
    return {
        "status": "succeeded",
        "mode": "mock",
        "value": "runtime-fixture-v1",
    }


backend_module_contribution = {
    "manifest": GENERATED_MODULE_MANIFEST,
    "router": None,
    "jobs": ("runtime.fixture.execute",),
    "event_handlers": (),
    "policy_gates": (),
}

__all__ = [
    "RuntimeFixtureError",
    "backend_module_contribution",
    "run_runtime_fixture",
]
