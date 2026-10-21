"""Provider-independent capability boundaries and safe operational failures."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class ProviderError(ValueError):
    """Only static, operator-actionable messages may cross the API boundary."""

    def __init__(self, code: str, message: str, retryable: bool = False):
        super().__init__(message)
        self.code, self.message, self.retryable = code, message, retryable


@dataclass(frozen=True)
class ProviderCapabilities:
    vision: bool = False
    structured_output: bool = False
    timestamped_transcription: bool = False


class VisionProvider(Protocol):
    provider: str
    model: str
    capabilities: ProviderCapabilities

    def extract(self, frames: tuple, *, metadata: dict) -> dict[str, Any]: ...


class TranscriptionProvider(Protocol):
    provider: str
    model: str
    capabilities: ProviderCapabilities

    def transcribe(self, chunk: Any, *, metadata: dict) -> dict[str, Any]: ...
