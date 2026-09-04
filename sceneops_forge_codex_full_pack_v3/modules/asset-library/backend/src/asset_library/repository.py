from __future__ import annotations

from typing import Dict, Iterable, Optional, Protocol

from .schemas import AssetRecord


class AssetRepository(Protocol):
    def get(self, asset_id: str) -> Optional[AssetRecord]: ...

    def list(self) -> Iterable[AssetRecord]: ...

    def save(self, record: AssetRecord) -> None: ...


class InMemoryAssetRepository:
    """Deterministic repository for module tests and composition-root adapters."""

    def __init__(self, records: Iterable[AssetRecord] = ()) -> None:
        self._records: Dict[str, AssetRecord] = {
            record.spec.asset_id: record.model_copy(deep=True) for record in records
        }

    def get(self, asset_id: str) -> Optional[AssetRecord]:
        record = self._records.get(asset_id)
        return record.model_copy(deep=True) if record else None

    def list(self) -> Iterable[AssetRecord]:
        return [self._records[key].model_copy(deep=True) for key in sorted(self._records)]

    def save(self, record: AssetRecord) -> None:
        self._records[record.spec.asset_id] = record.model_copy(deep=True)
