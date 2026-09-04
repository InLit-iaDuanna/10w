from dataclasses import dataclass
from .contracts import ExecutionMode, UiFlow, ValidationReport
from .service import UiStudioService

@dataclass(frozen=True)
class UiValidationJob:
    id: str = "ui.validation.run"
    state: str = "succeeded"
    mode: ExecutionMode = ExecutionMode.MOCK

    def run(self, service: UiStudioService, *args) -> ValidationReport:
        return service.validate_flow(*args)
