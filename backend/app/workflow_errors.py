"""Shared safe workflow error envelope."""


class WorkflowError(Exception):
    def __init__(self, code: str, message: str, status: int = 409, retryable: bool = False):
        self.code, self.message, self.status, self.retryable = code, message, status, retryable
        super().__init__(message)
