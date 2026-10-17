"""Deterministic fake model responses for offline integration tests only.

These observations are authored fixtures, never recognition of an uploaded file.
Production configuration cannot select this module. Tests still use actual
media preparation, provider normalization, persistence and workflow gates.
"""
from __future__ import annotations

import json
from pathlib import Path

from backend.app.providers.base import ProviderCapabilities
from backend.app.providers.config import ProviderSettings
from backend.app.providers.creative import OpenAICreativeAdapter
from backend.app.providers.recognition import ProviderRecognitionAdapter
from backend.app.providers.m2 import FakeM2AssistanceAdapter
from backend.app.service import WorkflowService


class FixtureVision:
    provider = "offline_fixture"
    model = "synthetic-bilingual-v1"
    capabilities = ProviderCapabilities(vision=True, structured_output=True)

    def extract(self, frames, *, metadata):
        details = {
            "subjects": {"status": "observations", "items": [{
                "subject_id": "subject_product", "kind": "physical_object",
                "label": "DemoCup 随行杯", "description": "Synthetic product observation; not real recognition.",
                "roles": ["product"],
            }], "error": None},
            "actions": {"status": "observations", "items": [{
                "action_type": "move", "actor_subject_ids": ["subject_product"],
                "target_subject_ids": [], "description": "Synthetic movement; target cannot be linked.",
            }], "error": None},
            "product_presentations": {"status": "observations", "items": [{
                "product_subject_ids": ["subject_product"], "presentation_type": "appearance",
                "description": "Synthetic product appearance for testing only.",
            }], "error": None},
        }
        return {"frames": [{"frame_index": frame.frame_index,
                            "description": "Synthetic fixture: DemoCup 杯子展示。",
                            "visual_details": details,
                            "on_screen_text": ["DemoCup 随行杯 · Shop now · 6 小时"],
                            "uncertainty": "Authored offline fixture; not extracted from this video.",
                            "roles": ["product_demo"], "interpretation": "Synthetic demonstration role."}
                           for frame in frames]}


class FixtureSpeech:
    provider = "offline_fixture"
    model = "synthetic-bilingual-v1"
    capabilities = ProviderCapabilities(timestamped_transcription=True)

    def transcribe(self, chunk, *, metadata):
        return {"text": "这款 DemoCup，take it anywhere。", "segments": [{
            "start": 0.0, "end": min(1.0, chunk.end_seconds - chunk.start_seconds),
            "text": "这款 DemoCup，take it anywhere。",
        }]}


class FixtureCreativeTransport:
    """Content provider substitute; no HTTP client and no credentials."""
    records: list = []

    def json_response(self, *, model, prompt, schema, schema_name, metadata):
        data = json.loads(prompt.split("INPUT_JSON:\n", 1)[1])
        brief, analysis = data["brief"], data["reviewed_analysis"]
        evidence = [{"event_id": analysis["events"][0]["event_id"],
                     "reason": "Synthetic offline test citation; no performance evidence."}]
        content = {
            "core_message": f"{brief['product']} · 合成测试草稿",
            "hook": "DemoCup 随行杯 — synthetic test opening",
            "narrative": "Synthetic product-only sequence; 方便携带 is a supplied claim, not verified efficacy.",
            "cta": "了解 DemoCup · Learn more",
            "production_requirements": ["Use approved product context; no fabricated effectiveness."],
            "evidence": evidence, "rationale": "Synthetic fixture for workflow validation only.",
            "hypotheses": [{"hypothesis": "Clear copy may help comprehension.",
                            "test_method": "Ask reviewers to recall the approved message."}],
            "production_notes": ["OFFLINE SYNTHETIC OUTPUT; not a live model result."],
        }
        if schema_name == "creative_directions":
            return {"directions": [content, {**content, "hook": "Synthetic alternate: 中文文字开场"}]}
        if schema_name == "creative_refine":
            instruction = data["feedback"]["instruction"]
            return {**content, "hook": f"Synthetic revision: {instruction}"}
        production = {key: content[key] for key in (
            "core_message", "hook", "narrative", "cta", "production_notes", "evidence")}
        return {"production_brief": {"title": "DemoCup 合成制作简报", **production}, "rows": [{
            "start_seconds": 0.0, "end_seconds": float(brief["target_duration_seconds"]),
            "visual": "Synthetic test scene: 展示 DemoCup 杯子。", "dialogue": None,
            "on_screen_text": "DemoCup 随行杯", "sound": "Proposed licensed sound, not source evidence.",
            "cta": content["cta"], "evidence": evidence,
        }]}


class FixtureRecognitionAdapter(ProviderRecognitionAdapter):
    def analyze(self, request):
        result = super().analyze(request)
        result.origin.description = "OFFLINE SYNTHETIC fixture; no real recognition or model request."
        return result


class FixtureCreativeAdapter(OpenAICreativeAdapter):
    def _origin(self):
        # The real adapter's normalization still executes; its return values are
        # explicitly relabeled below so a browser fixture cannot claim a live run.
        return {"kind": "sample", "description": "Offline synthetic creative provider fixture."}

    def generate_directions(self, *args):
        results = super().generate_directions(*args)
        for result in results:
            result.origin.description = "Offline synthetic creative provider fixture; no model request."
        return results

    def refine_direction(self, *args):
        result = super().refine_direction(*args)
        result.origin.description = "Offline synthetic creative refinement fixture; no model request."
        return result

    def generate_production(self, *args):
        results = super().generate_production(*args)
        for result in results:
            result.origin.description = "Offline synthetic production fixture; no model request."
        return results


def fixture_service(root: Path) -> WorkflowService:
    settings = ProviderSettings(max_frames=3, cache_dir=None)
    recognition = FixtureRecognitionAdapter(settings, vision_provider=FixtureVision(),
                                             transcription_provider=FixtureSpeech())
    creative = FixtureCreativeAdapter(settings, transport=FixtureCreativeTransport())
    return WorkflowService(root, real_recognition=recognition, real_creative=creative,
                           provider_settings=settings, m2_assistance=FakeM2AssistanceAdapter())
