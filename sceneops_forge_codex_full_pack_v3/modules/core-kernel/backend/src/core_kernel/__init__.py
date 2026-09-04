"""Public backend entrypoint for Core Kernel."""

from .generated_manifest import GENERATED_MODULE_MANIFEST
from .runtime import ALLOWED_RUN_TRANSITIONS, InvalidRunTransition, transition_run


backend_module_contribution = {
    "manifest": GENERATED_MODULE_MANIFEST,
    "router": None,
    "jobs": ("core.run.transition",),
    "event_handlers": (),
    "policy_gates": ("core.changeset.approval",),
}

__all__ = [
    "ALLOWED_RUN_TRANSITIONS",
    "InvalidRunTransition",
    "backend_module_contribution",
    "transition_run",
]
