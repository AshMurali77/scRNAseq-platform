class PipelineStepError(Exception):
    """Raised when a pipeline step fails.

    Attributes:
        step: Name of the pipeline step that failed (e.g. 'qc', 'normalize').
        message: Human-readable description of the failure.
    """

    def __init__(self, step: str, message: str) -> None:
        self.step = step
        self.message = message
        super().__init__(f"[{step}] {message}")
