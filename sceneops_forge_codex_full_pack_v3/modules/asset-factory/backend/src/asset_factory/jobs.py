from __future__ import annotations

from typing import List, NamedTuple


class JobDefinition(NamedTuple):
    id: str
    cancellable: bool
    retryable: bool
    resumable: bool


JOBS: List[JobDefinition] = [
    JobDefinition("asset.preflight", True, True, True),
    JobDefinition("asset.blender.process", True, True, True),
    JobDefinition("asset.validate", True, True, True),
    JobDefinition("asset.publish", False, False, False),
]
