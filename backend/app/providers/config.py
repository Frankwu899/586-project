"""Backend-only, independently selected capability configuration."""
from __future__ import annotations

from dataclasses import dataclass, field
import math
import os
from pathlib import Path


@dataclass(frozen=True)
class ProviderSettings:
    api_key: str = field(default="", repr=False)
    vision_provider: str = "openai"
    transcription_provider: str = "openai"
    creative_provider: str = "openai"
    vision_model: str = "gpt-4.1-mini"
    transcription_model: str = "whisper-1"
    creative_model: str = "gpt-4.1-mini"
    creative_language: str = "English"
    analysis_language: str = "English"
    timeout_seconds: float = 45
    max_retries: int = 2
    max_output_tokens: int = 8000
    max_frames: int = 12
    audio_chunk_seconds: float = 60
    max_audio_chunks: int = 3
    cache_dir: Path | None = None

    def __post_init__(self):
        if not math.isfinite(self.timeout_seconds) or not 0 < self.timeout_seconds <= 180:
            raise ValueError("Provider timeout must be finite and at most 180 seconds")
        if type(self.max_retries) is not int or not 0 <= self.max_retries <= 3:
            raise ValueError("Provider retries must be between zero and three")
        for name, low, high in (("max_output_tokens", 256, 16000), ("max_frames", 1, 24), ("max_audio_chunks", 1, 10)):
            if type(getattr(self, name)) is not int or not low <= getattr(self, name) <= high:
                raise ValueError(f"{name} outside supported bounded range")
        if not math.isfinite(self.audio_chunk_seconds) or not 1 <= self.audio_chunk_seconds <= 120:
            raise ValueError("Audio chunks must be between 1 and 120 seconds")
        for name in ("vision_model", "transcription_model", "creative_model", "analysis_language", "creative_language"):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} cannot be blank")

    @classmethod
    def from_env(cls):
        data_dir = Path(os.getenv("VIDEO_ANATOMY_DATA_DIR", ".local-data"))
        return cls(
            api_key=os.getenv("OPENAI_API_KEY", ""),
            vision_provider=os.getenv("VIDEO_VISION_PROVIDER", "openai"),
            transcription_provider=os.getenv("VIDEO_TRANSCRIPTION_PROVIDER", "openai"),
            creative_provider=os.getenv("VIDEO_CREATIVE_PROVIDER", "openai"),
            vision_model=os.getenv("OPENAI_VISION_MODEL", "gpt-4.1-mini"),
            transcription_model=os.getenv("OPENAI_TRANSCRIPTION_MODEL", "whisper-1"),
            creative_model=os.getenv("OPENAI_CREATIVE_MODEL", "gpt-4.1-mini"),
            creative_language=os.getenv("CREATIVE_OUTPUT_LANGUAGE", "English"),
            analysis_language=os.getenv("ANALYSIS_OUTPUT_LANGUAGE", "English"),
            timeout_seconds=float(os.getenv("OPENAI_TIMEOUT_SECONDS", "45")),
            max_retries=int(os.getenv("OPENAI_MAX_RETRIES", "2")),
            max_output_tokens=int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "8000")),
            max_frames=int(os.getenv("VIDEO_ANALYSIS_MAX_FRAMES", "12")),
            audio_chunk_seconds=float(os.getenv("VIDEO_AUDIO_CHUNK_SECONDS", "60")),
            max_audio_chunks=int(os.getenv("VIDEO_MAX_AUDIO_CHUNKS", "3")),
            cache_dir=data_dir / "provider-cache",
        )
