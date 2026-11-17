"""Reviewed capability/pricing catalog, checked against OpenAI on 2026-10-19.

GPT-6 has no audio input. Timed transcription remains a separate capability;
never replace its model name with a GPT-6 ID that cannot accept audio.
"""
from dataclasses import dataclass
from decimal import Decimal


DEFAULT_REASONING_MODEL = "gpt-6.1-sol"
DEFAULT_RESEARCH_MODEL = "gpt-6-luna"
DEFAULT_TRANSCRIPTION_MODEL = "whisper-1"


@dataclass(frozen=True)
class TranscriptionProfile:
    response_format: str
    timing: str


# Profiles checked against the official file-transcription guide on 2026-11-17:
# https://developers.openai.com/api/docs/guides/speech-to-text
# gpt-transcribe returns text, not provider sentence/word timestamps. Its
# interval is the measured PCM input chunk; never infer sub-chunk alignment.
TRANSCRIPTION_PROFILES = {
    "whisper-1": TranscriptionProfile("verbose_json", "segment"),
    "gpt-transcribe": TranscriptionProfile("json", "chunk"),
}
TRANSCRIPTION_MODELS = frozenset(TRANSCRIPTION_PROFILES)


@dataclass(frozen=True)
class ModelPrice:
    context_tokens: int
    input_per_million: Decimal
    output_per_million: Decimal
    cache_write_per_million: Decimal
    long_context_threshold: int | None = None


GPT6_PRICES = {
    "gpt-6.1-sol": ModelPrice(1_050_000, Decimal("2"), Decimal("10"), Decimal("2.5"), 272_000),
    "gpt-6-luna": ModelPrice(1_050_000, Decimal("0.1"), Decimal("0.5"), Decimal("0.125"), 272_000),
}
GPT6_MODELS = frozenset(GPT6_PRICES)


def current_model(value: str | None, default: str = DEFAULT_REASONING_MODEL) -> str:
    """Upgrade old saved environment defaults without silently changing GPT-6 choices."""
    if not value or value.startswith(("gpt-4", "gpt-5")):
        return default
    return value
