"""Explicit typed registration. Registry entries never load code or start processes."""
import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable

from pydantic import BaseModel
from sceneops_core_contracts import ExecutionMode

from .contracts import CapabilityDefinition, ConnectorDefinition
from .run_contracts import CapabilityInvocation, CapabilityResult


class HarnessError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


class CancellationToken:
    def __init__(self, requested: Callable[[], bool]):
        self._requested = requested

    @property
    def cancelled(self) -> bool:
        return self._requested()

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            raise asyncio.CancelledError()


CapabilityHandler = Callable[[CapabilityInvocation, CancellationToken], Awaitable[CapabilityResult]]
RollbackHandler = Callable[[CapabilityInvocation, CapabilityResult, CancellationToken], Awaitable[CapabilityResult]]


@dataclass(frozen=True)
class CapabilityBinding:
    definition: CapabilityDefinition
    handler: CapabilityHandler | None
    input_model: type[BaseModel] | None
    output_model: type[BaseModel] | None
    rollback_handler: RollbackHandler | None = None


class ConnectorRegistry:
    def __init__(self):
        self._connectors: dict[str, ConnectorDefinition] = {}

    def register(self, connector: ConnectorDefinition) -> None:
        self._connectors[connector.id] = connector.model_copy(deep=True)

    def get(self, connector_id: str) -> ConnectorDefinition | None:
        entry = self._connectors.get(connector_id)
        return entry.model_copy(deep=True) if entry else None

    def list(self) -> list[ConnectorDefinition]:
        return [entry.model_copy(deep=True) for entry in self._connectors.values()]


class CapabilityRegistry:
    def __init__(self, connectors: ConnectorRegistry | None = None):
        self.connectors = connectors or ConnectorRegistry()
        self._bindings: dict[str, CapabilityBinding] = {}

    def register(self, definition: CapabilityDefinition, handler: CapabilityHandler | None = None,
                 *, input_model: type[BaseModel] | None = None,
                 output_model: type[BaseModel] | None = None,
                 rollback_handler: RollbackHandler | None = None) -> None:
        if definition.id in self._bindings:
            raise HarnessError("DUPLICATE_CAPABILITY", definition.id)
        entry = definition.model_copy(deep=True)
        if handler is not None:
            if input_model is None or output_model is None:
                raise HarnessError("TYPED_HANDLER_REQUIRED", "Executable handlers require input and output models")
            if entry.execution_mode not in (ExecutionMode.LIVE, ExecutionMode.MOCK):
                raise HarnessError("INVALID_EXECUTION_MODE", "Handlers must declare explicit live or mock execution")
            for field, model in (("input_schema", input_model), ("output_schema", output_model)):
                schema = model.model_json_schema()
                declared = getattr(entry, field)
                if declared and declared != schema:
                    raise HarnessError("SCHEMA_MISMATCH", f"{entry.id}: {field} differs from registered model")
                setattr(entry, field, schema)
        elif entry.execution_mode in (ExecutionMode.LIVE, ExecutionMode.MOCK):
            raise HarnessError("HANDLER_REQUIRED", "An executable claim needs a registered handler")
        if entry.supports_rollback != (rollback_handler is not None):
            raise HarnessError("ROLLBACK_HANDLER_REQUIRED", "Rollback declaration must match handler availability")
        self._bindings[entry.id] = CapabilityBinding(entry, handler, input_model, output_model, rollback_handler)

    def binding(self, capability_id: str) -> CapabilityBinding | None:
        entry = self._bindings.get(capability_id)
        if entry is None:
            return None
        return CapabilityBinding(entry.definition.model_copy(deep=True), entry.handler,
                                 entry.input_model, entry.output_model, entry.rollback_handler)

    def get(self, capability_id: str) -> CapabilityDefinition | None:
        binding = self.binding(capability_id)
        return binding.definition if binding else None

    def list(self) -> list[CapabilityDefinition]:
        return [entry.definition.model_copy(deep=True) for entry in self._bindings.values()]
