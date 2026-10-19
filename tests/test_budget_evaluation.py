"""Safe evaluation entry point: default-off, exact files, mock-only module calls."""
from argparse import Namespace
import hashlib
import json

import httpx
import pytest

from backend.app.providers.transport import OpenAITransport
from scripts.evaluate_modules import load_manifest, run


def args(tmp_path, **overrides):
    return Namespace(manifest=None, data_dir=tmp_path / "data", output_dir=tmp_path / "report",
                     reviewed_state=None, check_cache=False, live=False, **overrides)


def test_preflight_has_no_requests_and_no_fake_measurements(tmp_path, monkeypatch):
    monkeypatch.setattr("scripts.evaluate_modules.OpenAITransport", lambda *_: pytest.fail("transport created during preflight"))
    report = run(args(tmp_path), {})
    assert report["status"] == "preflight_only" and report["paid_requests_sent"] == 0
    assert report["training"] == "not_run" and report["provider_billed_cost_usd"] is None
    assert all(row["status"] == "not_run" and row["estimated_cost_usd"] is None for row in report["modules"].values())
    assert not (tmp_path / "data" / "provider-budget.sqlite3").exists()
    assert (tmp_path / "report" / "report.json").exists()


def test_manifest_exact_bytes_and_eval_permission_do_not_imply_training(tmp_path):
    media = tmp_path / "fixture.mp4"
    media.write_bytes(b"not video; permission parser only")
    clip = {"id": "test", "path": media.name, "sha256": hashlib.sha256(media.read_bytes()).hexdigest(),
            "permitted": True, "rights_note": "Synthetic test bytes; not real media.", "rights": {"training_allowed": False}}
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"clips": [clip]}))
    assert load_manifest(manifest)[0]["rights"]["training_allowed"] is False
    media.write_bytes(b"changed")
    with pytest.raises(ValueError, match="SHA-256"):
        load_manifest(manifest)


def direction(hook="Show the removable lid"):
    return {"core_message": "LumaCup (fictional)", "hook": hook,
            "narrative": "Present the illustrated cup and invite color exploration.", "cta": "Explore three colors",
            "production_requirements": ["Only fictional product illustrations"], "evidence": [],
            "rationale": "An original proposal; no reference video was used.",
            "hypotheses": [{"hypothesis": "Viewers may understand the lid illustration.", "test_method": "Ask viewers to describe it."}],
            "production_notes": ["No performance claims."]}


def test_live_runner_mock_exercises_modules_under_one_persisted_guard(tmp_path, monkeypatch):
    names = []
    def handle(request):
        payload = json.loads(request.content)
        if request.url.path.endswith("input_tokens"):
            return httpx.Response(200, json={"object": "response.input_tokens", "input_tokens": 1000})
        name = payload["text"]["format"]["name"]
        names.append(name)
        if name == "m2_assistance":
            content = {"candidates": [], "unresolved_notes": []}
        elif name == "creative_directions":
            content = {"directions": [direction(), direction("Start with the three colors")]}
        elif name == "creative_refine":
            content = direction()
        else:
            common = {key: direction()[key] for key in ("core_message", "hook", "narrative", "cta", "evidence", "production_notes")}
            content = {"production_brief": {"title": "Fictional production fixture", **common}, "rows": [
                {"start_seconds": 0, "end_seconds": 15, "visual": "Illustrated cup and lid", "dialogue": None,
                 "on_screen_text": "Explore three colors", "sound": None, "cta": "Explore three colors", "evidence": []}]}
        return httpx.Response(200, json={"status": "completed", "model": "gpt-6.1-sol",
            "usage": {"input_tokens": 1000, "output_tokens": 200},
            "output": [{"content": [{"type": "output_text", "text": json.dumps(content)}]}]})
    client = httpx.Client(transport=httpx.MockTransport(handle))
    monkeypatch.setattr("scripts.evaluate_modules.OpenAITransport", lambda settings: OpenAITransport(settings, client=client))
    options = args(tmp_path)
    options.live = True
    report = run(options, {"RUN_LIVE_MODEL_TESTS": "1", "OPENAI_API_KEY": "synthetic-test-key"})
    client.close()
    assert names == ["m2_assistance", "creative_directions", "creative_refine", "creative_production"]
    assert report["status"] == "completed" and report["budget"]["attempts"] == 4
    assert report["budget"]["maximum_usd"] == "3" and report["budget"]["known_estimated_cost_usd"] == "0.018"
    assert report["creative_input"].startswith("fictional_fixture")
    assert all(report["modules"][module]["attempts"] == 1 for module in ("m2", "creative", "refinement", "production"))
    assert report["modules"]["vision"]["status"] == "not_run"
    assert "synthetic-test-key" not in (tmp_path / "report" / "report.json").read_text()
