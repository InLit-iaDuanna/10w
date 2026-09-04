from .schemas import PipelineState


class PipelineConflictError(ValueError):
    pass


class PipelineNotFoundError(LookupError):
    pass


class PipelineExecutionError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        state: PipelineState,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.state = state
        self.retryable = retryable
