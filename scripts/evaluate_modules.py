"""Local module evaluation with one persisted USD 3 budget, never training by default.

Default is preflight: it validates permitted media without making network requests.
Live mode additionally requires --live, RUN_LIVE_MODEL_TESTS=1 and OPENAI_API_KEY.
All modules and reruns share VIDEO_ANATOMY_DATA_DIR/provider-budget.sqlite3 unless
VIDEO_EXPERIMENT_BUDGET_PATH explicitly points at the existing shared ledger.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.adapters import RecognitionRequest, SampleCreativeAdapter
from backend.app.m2_assistance_models import M2AssistanceRequest
from backend.app.media import MediaStore
from backend.app.models import CreativeFeedback, M2Draft, TaskState, VersionRef, utc_now
from backend.app.providers.base import ProviderError
from backend.app.providers.budget import ExperimentBudget, PRICING_SOURCES, PRICING_VERIFIED_ON
from backend.app.providers.config import ProviderSettings
from backend.app.providers.creative import OpenAICreativeAdapter
from backend.app.providers.m2 import OpenAIM2AssistanceAdapter
from backend.app.providers.recognition import OpenAITranscriptionProvider, OpenAIVisionProvider, ProviderRecognitionAdapter
from backend.app.providers.transport import OpenAITransport
from backend.app.providers.usage import summarize_usage
from backend.app.sample import sample_brief


def write_json(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def load_manifest(path):
    if path is None:
        return []
    path = Path(path).resolve()
    document = json.loads(path.read_text(encoding="utf-8"))
    catalog = "assets" in document
    clips = document.get("assets" if catalog else "clips")
    if catalog and isinstance(clips, list):
        clips = sorted((item for item in clips if not item.get("skip_default_paid", False)), key=lambda item: item.get("paid_priority") or 999)
    if not isinstance(clips, list) or not 1 <= len(clips) <= 8:
        raise ValueError("The manifest must contain one to eight permitted clips")
    ids, results = set(), []
    for item in clips:
        identifier = item.get("id", item.get("case_id"))
        if not isinstance(identifier, str) or not identifier or not all(c.isalnum() or c in "_-" for c in identifier) or identifier in ids:
            raise ValueError("Clip IDs must be unique and contain letters, numbers, hyphens or underscores")
        ids.add(identifier)
        if item.get("permitted") is not True or not str(item.get("rights_note", "")).strip():
            raise ValueError("Each clip needs permitted=true and a meaningful rights note")
        root = Path(__file__).resolve().parents[1] if catalog else path.parent
        source = (root / item["path"]).resolve()
        if not source.is_file() or source.suffix.lower() != ".mp4" or not 0 < source.stat().st_size <= 50 * 1024 * 1024:
            raise ValueError("Each clip must be an existing MP4 no larger than 50 MiB")
        with source.open("rb") as file:
            digest = hashlib.file_digest(file, "sha256").hexdigest()
        if digest != item.get("sha256"):
            raise ValueError("Clip bytes differ from the reviewed manifest SHA-256")
        results.append({**item, "id": identifier, "source_path": source})
    return results


def quality_review(case_id, kind):
    return {"case_id": case_id, "source_kind": kind, "status": "not_human_reviewed", "score": None,
            "checks": {name: {"verdict": None, "notes": None} for name in (
                "source_words_and_script", "phone_platform_ui_excluded_without_removing_content",
                "sampled_visual_time_not_invented_duration", "logical_edges_explain_relationships",
                "intent_audience_and_effect_labeled_inference", "sources_relevant_attributed_and_traceable",
                "transfer_conditions_useful", "no_invented_product_claims", "production_matches_approved_input")},
            "instruction": "Compare original footage and independent reference notes. Schema success is not a quality score or evidence of marketing effectiveness."}


def evaluation_settings(data_dir, environment):
    settings = ProviderSettings.from_env()
    path = Path(environment.get("VIDEO_EXPERIMENT_BUDGET_PATH", str(data_dir / "provider-budget.sqlite3")))
    return replace(settings, api_key=environment.get("OPENAI_API_KEY", ""), budget_path=path,
                   experiment_max_usd=environment.get("VIDEO_EXPERIMENT_MAX_USD", "3"),
                   max_retries=0, cache_dir=data_dir / "provider-cache")


def run(args, environment=None):
    environment = os.environ if environment is None else environment
    data_dir = Path(args.data_dir or environment.get("VIDEO_ANATOMY_DATA_DIR", ".local-data")).resolve()
    run_id = uuid4().hex
    output = Path(args.output_dir).resolve() if args.output_dir else data_dir / "evaluations" / run_id
    clips = load_manifest(args.manifest)
    settings = evaluation_settings(data_dir, environment)
    report = {"run_id": run_id, "started_at": datetime.now(timezone.utc).isoformat(), "status": "preflight_only",
              "paid_requests_sent": 0, "provider_billed_cost_usd": None, "training": "not_run",
              "pricing_verified_on": PRICING_VERIFIED_ON.isoformat(), "pricing_sources": PRICING_SOURCES,
              "shared_budget_path": str(settings.budget_path), "maximum_usd": settings.experiment_max_usd,
              "cases": [{"id": c["id"], "sha256": c["sha256"], "status": "not_run", "kind": c.get("kind", "real")} for c in clips],
              "modules": summarize_usage([]), "quality": "not_human_reviewed",
              "reasons": ["Live provider quality, latency and usage require an actual completed paid request."]}
    if not args.live or environment.get("RUN_LIVE_MODEL_TESTS") != "1" or not settings.api_key.strip():
        if not settings.api_key.strip():
            report["reasons"].append("OPENAI_API_KEY is not configured in this execution environment.")
        if not args.live or environment.get("RUN_LIVE_MODEL_TESTS") != "1":
            report["reasons"].append("Live mode is off; both --live and RUN_LIVE_MODEL_TESTS=1 are required.")
        write_json(output / "report.json", report)
        return report

    # Construct every media input before the first paid request. This does not
    # write to the application's task database or approve real analyses.
    budget = ExperimentBudget(settings.budget_path, settings.experiment_max_usd)
    media = MediaStore(output / "media")
    prepared = []
    for clip in clips:
        task_id = "task_eval_" + uuid4().hex
        with clip["source_path"].open("rb") as source:
            video = media.save_upload(task_id, clip["source_path"].name, source)
        if video.content_sha256 != clip["sha256"]:
            raise ValueError("Source changed during preparation; no paid requests were sent")
        prepared.append((clip, task_id, video))
    transport = OpenAITransport(settings)
    recognition = ProviderRecognitionAdapter(settings, media_store=media,
        vision_provider=OpenAIVisionProvider(settings, transport),
        transcription_provider=OpenAITranscriptionProvider(settings, transport))
    started = time.monotonic()
    report.update(status="completed", cases=[], reasons=[])
    no_request_records = []
    operations = []

    def measure(name, operation, filename):
        began = time.monotonic()
        entry = {"module": name, "status": "running", "quality": "not_human_reviewed"}
        operations.append(entry)
        try:
            value = operation()
            serializable = ([item.model_dump(mode="json") for item in value] if isinstance(value, (list, tuple))
                            else value.model_dump(mode="json") if hasattr(value, "model_dump") else value)
            write_json(output / filename, serializable)
            entry.update(status="completed", output=filename)
            return value
        except (ProviderError, ValueError, OSError) as exc:
            entry.update(status="failed", error_code=getattr(exc, "code", "invalid_input_or_output"))
            report["status"] = "completed_with_errors"
            return None
        finally:
            entry["elapsed_ms"] = round((time.monotonic() - began) * 1000)

    try:
        for clip, task_id, video in prepared:
            case = {"id": clip["id"], "sha256": clip["sha256"], "kind": clip.get("kind", "real"), "status": "not_run"}
            report["cases"].append(case)
            request = RecognitionRequest(task_id, video, "job_eval_" + uuid4().hex, "real", media.path_for(video))
            before = len(recognition.records)
            analysis = measure("recognition", lambda: recognition.analyze(request), clip["id"] + "-analysis.json")
            no_request_records.extend(row for row in recognition.records[before:] if row.get("attempts", 0) == 0)
            if analysis is None:
                continue
            case["status"] = analysis.status
            if analysis.status != "succeeded":
                report["status"] = "completed_with_errors"
            write_json(output / (clip["id"] + "-review.json"), {**quality_review(clip["id"], case["kind"]),
                "source_expected_checks": clip.get("expected_checks", []), "rights_note": clip.get("rights_note")})
            if args.check_cache and analysis.status == "succeeded":
                before = len(recognition.records)
                measure("recognition_cache", lambda: recognition.analyze(replace(request, job_id="job_eval_" + uuid4().hex)), clip["id"] + "-cached-analysis.json")
                no_request_records.extend(row for row in recognition.records[before:] if row.get("attempts", 0) == 0)
            if (analysis.status in {"succeeded", "partial"} and analysis.events
                    and "structure" in clip.get("module_tags", ["structure"])):
                from backend.app.structure_provider import OpenAIStructureAgent
                from backend.app.structure_models import Workspace
                from backend.app.structure_service import validate_graph
                agent = OpenAIStructureAgent(settings, transport)
                metadata = {"capability": "structure", "task_id": task_id, "analysis_id": analysis.analysis_id,
                            "analysis_revision": analysis.revision, "_deadline": time.monotonic() + settings.structure_max_seconds}
                graph = measure("structure", lambda: validate_graph(agent.draft(analysis, video, settings.analysis_language, metadata), analysis, video), clip["id"] + "-structure.json")
                if graph and graph.research_gaps:
                    workspace = Workspace(structure_id="structure_eval_" + uuid4().hex, task_id=task_id, video_id=video.video_id,
                        analysis_ref=VersionRef(id=analysis.analysis_id, revision=analysis.revision), graph=graph, origin="provider")
                    def research():
                        researched, sources = agent.research(workspace, analysis, video, settings.analysis_language, metadata)
                        researched = validate_graph(researched, analysis, video, sources)
                        return {"graph": researched.model_dump(mode="json"), "sources": [source.model_dump(mode="json") for source in sources]}
                    measure("research", research, clip["id"] + "-research.json")

        # These fixtures test provider contracts, not actual-video approval or
        # analysis quality. No real analysis is silently confirmed for creativity.
        brief, analysis = sample_brief("task_eval_fictional"), None
        fixture_direction = SampleCreativeAdapter().generate_directions(brief, analysis)[0]
        approval = utc_now()
        fixture_direction = fixture_direction.model_copy(update={"approval_status": "approved", "approved_at": approval, "updated_at": approval})
        if args.reviewed_state:
            state = TaskState.model_validate(json.loads(Path(args.reviewed_state).read_text(encoding="utf-8")))
            def resolve(items, ref, key):
                return next(item for item in items if ref and getattr(item, key) == ref.id and item.revision == ref.revision)
            brief = resolve(state.briefs, state.task.current_brief, "brief_id")
            analysis = resolve(state.analyses, state.task.current_analysis, "analysis_id") if state.task.current_analysis else None
            fixture_direction = resolve(state.directions, state.task.selected_direction, "direction_id")
            if analysis:
                video = next(v for v in state.videos if v.video_id == analysis.video_id)
                if video.content_sha256 not in {c["sha256"] for c in clips}:
                    raise ValueError("Reviewed creative state must cite a manifest-permitted video")
            report["creative_input"] = "explicit_previously_reviewed_state"
        else:
            report["creative_input"] = "fictional_fixture_administrative_flags_not_user_approval_or_real_quality"
        draft = M2Draft(task_id="task_eval_inputs", reviewed_input_checkpoint="fixture", source_notes="Brand: Luma Studio (fictional)\nProduct: LumaCup (fictional)\nSelling point: Removable lid")
        measure("m2", lambda: OpenAIM2AssistanceAdapter(settings, transport=transport).assist(
            M2AssistanceRequest(draft_version=1, request_id="request_eval_m2"), draft), "m2.json")
        creative = OpenAICreativeAdapter(settings, transport)
        measure("creative", lambda: creative.generate_directions(brief, analysis), "creative.json")
        feedback = CreativeFeedback(feedback_id="feedback_eval", task_id=brief.task_id,
            instruction="Use product-only visuals without an on-camera presenter; preserve supplied claims and qualifications.",
            target_direction=VersionRef(id=fixture_direction.direction_id, revision=fixture_direction.revision),
            brief_ref=fixture_direction.brief_ref, analysis_ref=fixture_direction.analysis_ref)
        measure("refinement", lambda: creative.refine_direction(brief, analysis, fixture_direction, feedback), "refinement.json")
        measure("production", lambda: creative.generate_production(brief, analysis, fixture_direction), "production.json")
        write_json(output / "creative-review.json", quality_review("creative", report["creative_input"]))
    finally:
        report.update(elapsed_ms=round((time.monotonic() - started) * 1000), operations=operations,
                      modules=summarize_usage([*transport.records, *no_request_records]), requests=transport.records,
                      budget=budget.summary(), paid_requests_sent=sum(row.get("attempts", 0) for row in transport.records))
        write_json(output / "report.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--reviewed-state", type=Path)
    parser.add_argument("--check-cache", action="store_true")
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    try:
        report = run(args)
        print(json.dumps({key: report[key] for key in ("run_id", "status", "paid_requests_sent", "quality")}))
        return 0 if report["status"] in {"preflight_only", "completed"} else 1
    except (ValueError, OSError, KeyError, StopIteration):
        print("Evaluation blocked: check the manifest, shared budget, credentials and reviewed inputs. No private content is printed.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
