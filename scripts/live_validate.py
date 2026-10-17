"""Explicitly budgeted live evaluation; never part of the default test suite.

RUN_LIVE_MODEL_TESTS=1, OPENAI_API_KEY, LIVE_TEST_MAX_COST_USD, permitted
media/annotation manifest, and operator-verified pricing are all required. Prices
are intentionally not supplied here. Reservations conservatively charge an
entire model context and bounded output for EVERY attempt, including retries.
They are retained across runs even when an attempt fails or reported usage is
lower. Reservations are not provider-billed costs or an exact invoice ceiling.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_CEILING
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from urllib.parse import urlsplit
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.adapters import RecognitionRequest
from backend.app.media import MediaStore
from backend.app.models import TaskState
from backend.app.providers.base import ProviderError
from backend.app.providers.config import ProviderSettings
from backend.app.providers.creative import OpenAICreativeAdapter
from backend.app.providers.recognition import (OpenAITranscriptionProvider, OpenAIVisionProvider,
                                               ProviderRecognitionAdapter)
from backend.app.providers.transport import OpenAITransport

# Verified official model limits (2026-10-16):
# https://developers.openai.com/api/docs/models/gpt-4.1-mini
# Other models require a reviewed cost-bound implementation before live testing.
CONTEXT_LIMITS = {"gpt-4.1-mini": 1_047_576, "gpt-4.1-mini-2025-04-14": 1_047_576}
CASES = {"english", "chinese", "mixed", "cross_language"}


def positive_decimal(value, label):
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be an explicit positive decimal") from exc
    if not number.is_finite() or number <= 0:
        raise ValueError(f"{label} must be an explicit positive decimal")
    return number


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


class BudgetLedger:
    def __init__(self, path: Path, maximum, pricing: dict):
        self.path, self.maximum = Path(path), positive_decimal(maximum, "LIVE_TEST_MAX_COST_USD")
        if pricing.get("operator_verified") is not True:
            raise ValueError("Pricing needs explicit operator_verified=true after checking current official rates")
        if urlsplit(pricing.get("source_url", "")).hostname not in {"openai.com", "developers.openai.com", "platform.openai.com"}:
            raise ValueError("Pricing must record the official OpenAI source URL")
        verified = date.fromisoformat(pricing.get("verified_on", ""))
        if not 0 <= (date.today() - verified).days <= 30:
            raise ValueError("Verify current pricing within 30 days before a live run")
        self.pricing = pricing
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _read(self):
        if not self.path.exists():
            return {"version": 1, "reservations": []}
        data = load_json(self.path)
        if data.get("version") != 1 or not isinstance(data.get("reservations"), list):
            raise ValueError("Existing live budget ledger is invalid; preserve it and resolve manually")
        for entry in data["reservations"]:
            positive_decimal(entry["reserved_usd"], "Saved reservation")
        return data

    def estimate(self, model: str, payload: dict):
        rates = self.pricing.get("models", {}).get(model)
        if not isinstance(rates, dict):
            raise ProviderError("live_cost_bound_missing", "No operator-verified cost bound exists for this model.")
        if payload.get("capability") == "timestamped_transcription":
            if model != "whisper-1":
                raise ProviderError("live_cost_bound_missing", "Live audio budgeting currently supports whisper-1 only.")
            seconds = positive_decimal(payload.get("audio_seconds"), "Audio duration")
            if seconds > 120 or type(payload.get("audio_bytes")) is not int or not 0 < payload["audio_bytes"] <= 24 * 1024 * 1024:
                raise ProviderError("live_input_limit", "Audio exceeds the bounded live request limits.")
            minutes = (seconds / 60).to_integral_value(rounding=ROUND_CEILING)
            return minutes * positive_decimal(rates.get("usd_per_minute"), "Transcription rate")
        if model not in CONTEXT_LIMITS:
            raise ProviderError("live_cost_bound_missing", "This text model needs a reviewed context/token cost bound before live use.")
        output_limit = payload.get("max_output_tokens")
        if type(output_limit) is not int or not 1 <= output_limit <= 16000:
            raise ProviderError("live_output_limit", "Every live text request requires a bounded output token limit.")
        if len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) > 180 * 1024 * 1024:
            raise ProviderError("live_input_limit", "The live request exceeds the bounded payload size.")
        # Full documented context covers text AND image tokens without guessing an
        # image-token conversion or trusting a tokenizer estimate. Cached-input
        # discounts are ignored. Output is additionally reserved at its cap.
        return (Decimal(CONTEXT_LIMITS[model]) * positive_decimal(rates.get("input_usd_per_million_tokens"), "Input rate")
                + Decimal(output_limit) * positive_decimal(rates.get("output_usd_per_million_tokens"), "Output rate")) / 1_000_000

    def reserve(self, model: str, payload: dict):
        amount = self.estimate(model, payload)
        with self.path.with_suffix(".lock").open("a") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            data = self._read()
            used = sum((Decimal(entry["reserved_usd"]) for entry in data["reservations"]), Decimal(0))
            if used + amount > self.maximum:
                raise ProviderError("live_budget_exhausted", "The next paid attempt cannot be safely reserved within the remaining live budget.")
            data["reservations"].append({"model": model, "reserved_usd": str(amount),
                                         "reserved_at": datetime.now(timezone.utc).isoformat()})
            temporary = self.path.with_suffix(".pending")
            write_json(temporary, data)
            # Persist before network access. Unknown/failed usage never releases a
            # reservation, so reruns include every previously attempted request.
            with temporary.open("rb") as saved:
                os.fsync(saved.fileno())
            temporary.replace(self.path)
            directory = os.open(self.path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    def summary(self):
        data = self._read()
        return {"maximum_usd": str(self.maximum),
                "reserved_upper_bound_usd": str(sum((Decimal(row["reserved_usd"]) for row in data["reservations"]), Decimal(0))),
                "attempt_reservations": len(data["reservations"]), "provider_billed_cost_usd": None,
                "explanation": "Conservative pre-request reservations, including retries and past runs; actual invoice cost was not supplied."}


def permitted_clips(manifest_path: Path):
    manifest_path = Path(manifest_path).resolve()
    clips = load_json(manifest_path).get("clips", [])
    if not isinstance(clips, list) or not 4 <= len(clips) <= 8:
        raise ValueError("Supply four to eight permitted clips covering the four bilingual cases")
    observed = set()
    for clip in clips:
        if clip.get("case_id") not in CASES or clip.get("permitted") is not True or not str(clip.get("rights_note", "")).strip():
            raise ValueError("Each clip needs a supported case_id, permitted=true and a nonempty rights_note")
        observed.add(clip["case_id"])
        source = (manifest_path.parent / clip["path"]).resolve()
        if not source.is_file() or source.suffix.lower() != ".mp4" or source.stat().st_size > 50 * 1024 * 1024:
            raise ValueError("Each permitted clip must be an existing MP4 no larger than 50 MiB")
        with source.open("rb") as stream:
            actual_hash = hashlib.file_digest(stream, "sha256").hexdigest()
        if actual_hash != clip.get("sha256"):
            raise ValueError("A clip's bytes do not match its explicitly permitted SHA-256")
        for field in ("expected_speech", "expected_on_screen_text"):
            annotations = clip.get(field)
            if not isinstance(annotations, list) or not annotations:
                raise ValueError("Every bilingual case requires separate human speech and on-screen-text annotations")
            for annotation in annotations:
                if not isinstance(annotation.get("text"), str) or not annotation["text"].strip():
                    raise ValueError("Reference annotations require original-language source words")
                start = Decimal(str(annotation.get("start_seconds")))
                end = positive_decimal(annotation.get("end_seconds"), "Annotation end")
                if not start.is_finite() or start < 0 or start >= end or end > 180:
                    raise ValueError("Reference annotations require valid source seconds within 180 seconds")
        clip["source_path"] = source
    if observed != CASES:
        raise ValueError("Include English, Chinese, mixed-language and cross-language audio/OCR cases")
    return clips


def human_review(clip, analysis):
    return {"case_id": clip["case_id"], "analysis_id": analysis.analysis_id, "analysis_revision": analysis.revision,
            "source_sha256": clip["sha256"], "review_status": "not_reviewed", "reviewer": None,
            "expected_speech": clip["expected_speech"], "expected_on_screen_text": clip["expected_on_screen_text"],
            "observed_speech": [event.model_dump(mode="json") for event in analysis.events if event.kind == "speech"],
            "observed_on_screen_text": [event.model_dump(mode="json") for event in analysis.events if event.kind == "on_screen_text"],
            "checks": {key: {"verdict": None, "notes": None} for key in (
                "speech_source_words_and_script", "ocr_source_words_and_script", "mixed_language_switches",
                "english_brand_tokens", "numerals_units_prices_cta", "audio_and_ocr_kept_separate",
                "source_frame_interval_alignment", "unreadable_inaudible_uncertainty", "visual_subject_action_presentation")},
            "instruction": "A human must compare the permitted source clip and independent annotations to these outputs. No quality score or pass is inferred from schema validity."}


def run(args, environment=None):
    env = os.environ if environment is None else environment
    if env.get("RUN_LIVE_MODEL_TESTS", "0") != "1":
        return {"status": "not_run", "reason": "Live tests default off; explicit RUN_LIVE_MODEL_TESTS=1 is required."}
    if not env.get("OPENAI_API_KEY", "").strip():
        raise ValueError("Live tests require backend OPENAI_API_KEY")
    started = time.monotonic()
    maximum = positive_decimal(env.get("LIVE_TEST_MAX_COST_USD"), "LIVE_TEST_MAX_COST_USD")
    if not args.manifest or not args.pricing:
        raise ValueError("Live tests require --manifest with permitted clips and --pricing with verified rates")
    clips = permitted_clips(args.manifest)
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    budget = BudgetLedger(output / "budget.json", maximum, load_json(args.pricing))
    settings = replace(ProviderSettings.from_env(), api_key=env["OPENAI_API_KEY"], cache_dir=None)
    if settings.vision_model not in CONTEXT_LIMITS or settings.creative_model not in CONTEXT_LIMITS:
        raise ValueError("Live text evaluation currently requires the documented gpt-4.1-mini model family")
    # Fail before any request if any configured capability lacks an explicit cost bound.
    for model in {settings.vision_model, settings.creative_model}:
        budget.estimate(model, {"max_output_tokens": settings.max_output_tokens})
    budget.estimate(settings.transcription_model, {"capability": "timestamped_transcription", "audio_seconds": 1, "audio_bytes": 1})
    media = MediaStore(output / "media")
    prepared = []
    for clip in clips:
        task_id = f"task_live_{uuid4().hex}"
        with clip["source_path"].open("rb") as source:
            video = media.save_upload(task_id, clip["source_path"].name, source)
        if video.content_sha256 != clip["sha256"]:
            raise ValueError("Permitted media changed during intake; no requests sent")
        if any(row["end_seconds"] > video.duration_seconds for key in ("expected_speech", "expected_on_screen_text") for row in clip[key]):
            raise ValueError("Human annotation exceeds measured source duration; no requests sent")
        prepared.append((clip, task_id, video))
    transport = OpenAITransport(settings, before_attempt=budget.reserve)
    recognition = ProviderRecognitionAdapter(settings, media_store=media,
        vision_provider=OpenAIVisionProvider(settings, transport),
        transcription_provider=OpenAITranscriptionProvider(settings, transport))
    run_id = uuid4().hex
    report = {"run_id": run_id, "status": "completed", "cases": [], "human_quality": "not_reviewed",
              "analysis_language": settings.analysis_language, "creative_language": settings.creative_language,
              "creative": "not_run_without_explicit_reviewed_state", "provider_billed_cost_usd": None}
    try:
        for index, (clip, task_id, video) in enumerate(prepared):
            analysis = recognition.analyze(RecognitionRequest(task_id, video, f"job_live_{uuid4().hex}", "real", media.path_for(video)))
            stem = f"{run_id}-{index}-{clip['case_id']}"
            write_json(output / f"{stem}-video.json", video.model_dump(mode="json"))
            write_json(output / f"{stem}-analysis.json", analysis.model_dump(mode="json"))
            write_json(output / f"{stem}-human-review.json", human_review(clip, analysis))
            report["cases"].append({"case_id": clip["case_id"], "status": analysis.status,
                                    "error_code": analysis.error.code if analysis.error else None,
                                    "video_file": f"{stem}-video.json",
                                    "analysis_file": f"{stem}-analysis.json", "review_file": f"{stem}-human-review.json"})
            if analysis.status != "succeeded":
                report["status"] = "completed_with_errors"
            if any(record.get("failure_code") == "live_budget_exhausted" for record in transport.records):
                report["status"] = "budget_stopped"
                break
        if args.reviewed_state and report["status"] != "budget_stopped":
            state = TaskState.model_validate(load_json(args.reviewed_state))
            def resolve(items, reference, key):
                return next(item for item in items if reference and getattr(item, key) == reference.id and item.revision == reference.revision)
            brief = resolve(state.briefs, state.task.current_brief, "brief_id")
            analysis = resolve(state.analyses, state.task.current_analysis, "analysis_id")
            video = next(video for video in state.videos if video.video_id == analysis.video_id)
            if video.content_sha256 not in {clip["sha256"] for clip in clips}:
                raise ValueError("Reviewed creative input must cite one of the explicitly permitted source clips")
            creative = OpenAICreativeAdapter(settings, transport)
            directions = creative.generate_directions(brief, analysis)
            write_json(output / f"{run_id}-creative-directions.json", [item.model_dump(mode="json") for item in directions])
            report["creative"] = "two_unapproved_drafts_generated"
            pending = next((feedback for feedback in reversed(state.feedback)
                            if feedback.status == "pending" and feedback.brief_ref == state.task.current_brief
                            and feedback.analysis_ref == state.task.current_analysis), None)
            if pending:
                target = resolve(state.directions, pending.target_direction, "direction_id")
                refined = creative.refine_direction(brief, analysis, target, pending)
                write_json(output / f"{run_id}-refined-direction.json", refined.model_dump(mode="json"))
            if state.task.selected_direction:
                direction = resolve(state.directions, state.task.selected_direction, "direction_id")
                production, storyboard = creative.generate_production(brief, analysis, direction)
                write_json(output / f"{run_id}-production.json", {"brief": production.model_dump(mode="json"), "storyboard": storyboard.model_dump(mode="json")})
                report["creative"] = "drafts_and_production_from_previously_approved_direction"
    except ProviderError as exc:
        report["status"], report["error_code"] = "failed", exc.code
    except (ValueError, OSError, KeyError, TypeError, StopIteration):
        report["status"], report["error_code"] = "failed", "invalid_live_input_or_local_output"
        raise
    finally:
        report.update(elapsed_ms=round((time.monotonic() - started) * 1000), budget=budget.summary(), requests=transport.records)
        write_json(output / f"{run_id}-report.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--pricing", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path(".local-data/live-evaluation"))
    parser.add_argument("--reviewed-state", type=Path, help="Optional saved state already reviewed/approved by a human; never auto-confirm new recognition")
    args = parser.parse_args()
    try:
        report = run(args)
        print(json.dumps({key: report[key] for key in ("status", "reason", "run_id", "human_quality") if key in report}))
        return 0 if report["status"] in {"not_run", "completed"} else 1
    except (ValueError, OSError, KeyError, TypeError, StopIteration) as exc:
        # No provider body, key, or user clip content is printed by this harness.
        print(f"Live validation blocked: {type(exc).__name__}. Check opt-in, credentials, budget, pricing and permitted manifest.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
