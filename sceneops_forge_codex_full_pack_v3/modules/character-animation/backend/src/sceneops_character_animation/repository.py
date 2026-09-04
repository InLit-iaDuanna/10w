"""Module-owned version metadata repository protocol and in-memory test implementation."""

from typing import Dict, Optional, Protocol, Union

from .animation_models import AnimationClipSpec
from .character_models import RigVersion
from .errors import InvalidVersionError


VersionEntity = Union[RigVersion, AnimationClipSpec]


class VersionRepository(Protocol):
    def save_rig(self, rig: RigVersion) -> None: ...

    def save_clip(self, clip: AnimationClipSpec) -> None: ...

    def get_rig(self, rig_version_id: str) -> RigVersion: ...

    def get_clip(self, clip_version_id: str) -> AnimationClipSpec: ...


class InMemoryVersionRepository:
    """Keeps only module version metadata; source assets remain in Asset Library."""

    def __init__(self) -> None:
        self._rigs: Dict[str, RigVersion] = {}
        self._clips: Dict[str, AnimationClipSpec] = {}

    def save_rig(self, rig: RigVersion) -> None:
        self._rigs[rig.rig_version_id] = rig

    def save_clip(self, clip: AnimationClipSpec) -> None:
        self._clips[clip.clip_version_id] = clip

    def get_rig(self, rig_version_id: str) -> RigVersion:
        try:
            return self._rigs[rig_version_id]
        except KeyError as exc:
            raise InvalidVersionError("Unknown rig version.", {"rig_version_id": rig_version_id}) from exc

    def get_clip(self, clip_version_id: str) -> AnimationClipSpec:
        try:
            return self._clips[clip_version_id]
        except KeyError as exc:
            raise InvalidVersionError("Unknown animation clip version.", {"clip_version_id": clip_version_id}) from exc
