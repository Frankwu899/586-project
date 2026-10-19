"""Backend-only, independently selected capability configuration."""
from __future__ import annotations

from dataclasses import dataclass, field
import math
import os
from pathlib import Path

from .catalog import DEFAULT_REASONING_MODEL, DEFAULT_RESEARCH_MODEL, current_model


@dataclass(frozen=True)
class ProviderSettings:
    api_key: str = field(default="", repr=False)
    vision_provider: str = "openai"
    transcription_provider: str = "openai"
    creative_provider: str = "openai"
    m2_provider: str = "openai"
    vision_model: str = DEFAULT_REASONING_MODEL
    transcription_model: str = "whisper-1"
    creative_model: str = DEFAULT_REASONING_MODEL
    m2_model: str = DEFAULT_REASONING_MODEL
    structure_model: str = DEFAULT_REASONING_MODEL
    research_model: str = DEFAULT_RESEARCH_MODEL
    structure_research_max_calls: int = 2
    structure_max_seconds: float = 120
    budget_path: Path | None = None
    experiment_max_usd: str = "3"
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
        if type(self.structure_research_max_calls) is not int or not 1 <= self.structure_research_max_calls <= 3:
            raise ValueError("Research requires one to three maximum search calls")
        if not math.isfinite(self.structure_max_seconds) or not 1 <= self.structure_max_seconds <= 180:
            raise ValueError("Structure run time must be bounded at 180 seconds")
        from .budget import MAXIMUM_USD, _number
        if _number(self.experiment_max_usd) > MAXIMUM_USD:
            raise ValueError("The authorized experiment budget cannot exceed USD 3")
        for name in ("vision_model", "transcription_model", "creative_model", "m2_model", "structure_model", "research_model", "analysis_language", "creative_language"):
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
            m2_provider=os.getenv("VIDEO_M2_PROVIDER", "openai"),
            vision_model=current_model(os.getenv("OPENAI_VISION_MODEL")),
            # GPT-6 cannot transcribe audio. Normal profiles do not silently
            # invoke an older speech model under a GPT-6-only model policy.
            transcription_model=os.getenv("OPENAI_TRANSCRIPTION_MODEL", "disabled"),
            creative_model=current_model(os.getenv("OPENAI_CREATIVE_MODEL")),
            m2_model=current_model(os.getenv("OPENAI_M2_MODEL")),
            structure_model=current_model(os.getenv("OPENAI_STRUCTURE_MODEL")),
            research_model=current_model(os.getenv("OPENAI_RESEARCH_MODEL"), DEFAULT_RESEARCH_MODEL),
            structure_research_max_calls=int(os.getenv("STRUCTURE_RESEARCH_MAX_CALLS", "2")),
            structure_max_seconds=float(os.getenv("STRUCTURE_MAX_SECONDS", "120")),
            budget_path=Path(os.getenv("VIDEO_EXPERIMENT_BUDGET_PATH", str(data_dir / "provider-budget.sqlite3"))),
            experiment_max_usd=os.getenv("VIDEO_EXPERIMENT_MAX_USD", "3"),
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
