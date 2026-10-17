"""Budget/permission gates only: these tests make no live provider requests."""
from argparse import Namespace
from datetime import date
from decimal import Decimal
import hashlib
import json

import httpx
import pytest

from backend.app.providers.base import ProviderError
from backend.app.providers.config import ProviderSettings
from backend.app.providers.transport import OpenAITransport
from scripts.live_validate import BudgetLedger, CASES, permitted_clips, run


def pricing():
    # Deliberately synthetic rates for arithmetic testing; not current prices.
    return {"operator_verified": True, "source_url": "https://openai.com/api/pricing/",
            "verified_on": date.today().isoformat(),
            "models": {"gpt-4.1-mini": {"input_usd_per_million_tokens": "1", "output_usd_per_million_tokens": "2"},
                       "whisper-1": {"usd_per_minute": "1"}}}


def args(tmp_path):
    return Namespace(manifest=None, pricing=None, output_dir=tmp_path, reviewed_state=None)


def test_default_off_does_not_read_inputs_or_create_output(tmp_path):
    output = tmp_path / "uncreated"
    assert run(args(output), {})["status"] == "not_run"
    assert not output.exists()


@pytest.mark.parametrize("environment", [
    {"RUN_LIVE_MODEL_TESTS": "1"},
    {"RUN_LIVE_MODEL_TESTS": "1", "OPENAI_API_KEY": "synthetic-test-key"},
    *[{"RUN_LIVE_MODEL_TESTS": "1", "OPENAI_API_KEY": "synthetic-test-key", "LIVE_TEST_MAX_COST_USD": value}
      for value in ("0", "-1", "nan", "inf", "")],
    {"RUN_LIVE_MODEL_TESTS": "1", "OPENAI_API_KEY": "synthetic-test-key", "LIVE_TEST_MAX_COST_USD": "20"},
])
def test_missing_key_explicit_budget_or_permission_manifest_blocks(environment, tmp_path):
    with pytest.raises(ValueError):
        run(args(tmp_path), environment)
    assert not (tmp_path / "budget.json").exists()


def test_reserve_before_each_attempt_including_retry_and_keep_prior_runs(tmp_path):
    ledger_path = tmp_path / "budget.json"
    ledger = BudgetLedger(ledger_path, "10", pricing())
    attempts = []

    def respond(request):
        reservations = json.loads(ledger_path.read_text())["reservations"]
        attempts.append(len(reservations))
        if len(attempts) == 1:
            return httpx.Response(503, json={"error": {"code": "unavailable"}})
        return httpx.Response(200, json={"status": "completed", "output": [
            {"content": [{"type": "output_text", "text": '{"ok":true}'}]}]})

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        transport = OpenAITransport(ProviderSettings(api_key="synthetic-test-key", max_retries=1, max_output_tokens=1000),
                                    client=client, before_attempt=ledger.reserve, sleep=lambda _: None)
        assert transport.json_response("gpt-4.1-mini", "test", {"type": "object"}, "test") == {"ok": True}
    assert attempts == [1, 2]  # persisted before either simulated HTTP request
    assert Decimal(ledger.summary()["reserved_upper_bound_usd"]) == Decimal("2.099152")
    reused = BudgetLedger(ledger_path, "2.1", pricing())
    with pytest.raises(ProviderError) as error:
        reused.reserve("gpt-4.1-mini", {"max_output_tokens": 1000})
    assert error.value.code == "live_budget_exhausted"
    assert reused.summary()["attempt_reservations"] == 2
    assert reused.summary()["provider_billed_cost_usd"] is None


def test_exhausted_budget_stops_network_before_first_attempt(tmp_path):
    calls = []
    ledger = BudgetLedger(tmp_path / "budget.json", "0.01", pricing())
    with httpx.Client(transport=httpx.MockTransport(lambda request: calls.append(request))) as client:
        transport = OpenAITransport(ProviderSettings(api_key="synthetic-test-key"), client=client,
                                    before_attempt=ledger.reserve, sleep=lambda _: None)
        with pytest.raises(ProviderError, match="remaining live budget"):
            transport.json_response("gpt-4.1-mini", "test", {"type": "object"}, "test")
    assert calls == []


def test_audio_upper_bound_rounds_up_and_unknown_price_or_input_blocks(tmp_path):
    ledger = BudgetLedger(tmp_path / "budget.json", "5", pricing())
    assert ledger.estimate("whisper-1", {"capability": "timestamped_transcription", "audio_seconds": 60.1, "audio_bytes": 100}) == 2
    for model, payload in [("other", {"max_output_tokens": 1000}),
                           ("gpt-4.1-mini", {}),
                           ("whisper-1", {"capability": "timestamped_transcription", "audio_seconds": 121, "audio_bytes": 100})]:
        with pytest.raises(ProviderError):
            ledger.reserve(model, payload)
    with pytest.raises(ValueError):
        ledger.reserve("whisper-1", {"capability": "timestamped_transcription", "audio_seconds": None, "audio_bytes": 100})
    assert not (tmp_path / "budget.json").exists()


@pytest.mark.parametrize("change", [
    {"operator_verified": False}, {"source_url": "https://example.com/prices"}, {"verified_on": "2000-01-01"},
])
def test_unverified_or_stale_pricing_blocked(tmp_path, change):
    with pytest.raises(ValueError):
        BudgetLedger(tmp_path / "budget.json", "10", {**pricing(), **change})


def permitted_manifest(tmp_path):
    clip = tmp_path / "synthetic.mp4"
    clip.write_bytes(b"synthetic bytes used only for permission hashing; not a real video")
    text = {"start_seconds": 0, "end_seconds": 1, "text": "DemoCup 随行杯"}
    manifest = {"clips": [{"case_id": case, "path": clip.name, "sha256": hashlib.sha256(clip.read_bytes()).hexdigest(),
                           "permitted": True, "rights_note": "Synthetic local unit-test bytes, not media or linguistic evidence.",
                           "expected_speech": [text], "expected_on_screen_text": [text]} for case in sorted(CASES)]}
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    return path, manifest


def test_permission_manifest_requires_all_bilingual_cases_and_exact_bytes(tmp_path):
    path, manifest = permitted_manifest(tmp_path)
    clips = permitted_clips(path)
    assert len(clips) == 4 and clips[0]["expected_speech"][0]["text"] == "DemoCup 随行杯"
    manifest["clips"][0]["sha256"] = "0" * 64
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="SHA-256"):
        permitted_clips(path)


@pytest.mark.parametrize("mutation", [
    lambda value: value["clips"][0].update(permitted=False),
    lambda value: value["clips"][0].update(rights_note=" "),
    lambda value: value["clips"][0].update(expected_speech=[]),
    lambda value: value["clips"][0].update(case_id="not_a_case"),
])
def test_unpermitted_or_unannotated_clips_blocked(tmp_path, mutation):
    path, manifest = permitted_manifest(tmp_path)
    mutation(manifest)
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        permitted_clips(path)
