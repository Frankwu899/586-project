"""Non-destructive, idempotent import of legacy task workspaces into projects.

All original records (including auxiliary tables) are archived verbatim. Visible
1.8 projections do not invent chat, series, source timing or missing documents.
"""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3

from ..models import TaskState
from ..providers.base import ProviderError
from ..workflow_errors import WorkflowError
from .models import (Analysis, BriefRevision, ContentItem, Direction, EvidenceEvent,
                     EvidenceRevision, Fact, InputManifest, ProductionPack,
                     Project, ReferenceStructure, Resource, Selection, SourceRef,
                     StructureEdge, StructureNode)
from .store import _digest
from .speech_retry import public_failure

_FIELDS = ("brand_company", "product", "target_audience", "platform", "communication_goal",
           "target_duration_seconds", "available_footage", "presenters", "locations", "tone",
           "production_limits", "approved_messages", "prohibited_claims")


def _value(value):
    if isinstance(value, list):
        return "\n".join(str(item) for item in value)
    return str(value)


def _facts(fields, claims, *, confirmed):
    result = []
    for key in _FIELDS:
        value = fields.get(key)
        if value is not None and value != [] and str(value).strip():
            result.append(Fact(key=key, value=_value(value), origin="legacy",
                               status="confirmed" if confirmed else "suggested"))
    for claim in claims:
        permitted = claim.get("confirmation_origin") == "user_confirmed" if confirmed else claim.get("confirmed_for_use", False)
        wording = claim.get("statement", "")
        if claim.get("qualification"):
            wording += f"\nQualification: {claim['qualification']}"
        if wording.strip():
            result.append(Fact(id=claim["claim_id"], key="claim", value=wording, origin="legacy",
                               status="confirmed" if permitted else "unresolved", permitted_for_use=bool(permitted),
                               sources=[SourceRef(url=url, locator="Legacy claim source", excerpt=claim["statement"])
                                        for url in claim.get("source_urls", [])]))
    return result


def _snapshot(db, task_id):
    """Archive exact owned columns/values without executing stored schema SQL."""
    tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    snapshots = {}
    structures = []
    if "structure_runs" in tables:
        structures = [row[0] for row in db.execute("SELECT structure_id FROM structure_runs WHERE task_id=?", (task_id,))]
    for table in sorted(tables):
        if table.startswith("sqlite_"):
            continue
        quoted = '"' + table.replace('"', '""') + '"'
        columns = [row[1] for row in db.execute(f"PRAGMA table_info({quoted})")]
        if table == "tasks":
            query, values = "id=?", (task_id,)
        elif "task_id" in columns:
            query, values = "task_id=?", (task_id,)
        elif table == "structure_history" and structures:
            query, values = f"structure_id IN ({','.join('?' for _ in structures)})", tuple(structures)
        else:
            continue
        rows = db.execute(f"SELECT * FROM {quoted} WHERE {query}", values).fetchall()
        snapshots[table] = {"columns": columns, "rows": [[{"base64": base64.b64encode(value).decode()} if isinstance(value, bytes) else value for value in row] for row in rows]}
    return snapshots


def _rows(snapshot, table):
    data = snapshot.get(table, {"columns": [], "rows": []})
    return [dict(zip(data["columns"], row, strict=True)) for row in data["rows"]]


def _structure_reports(project, state, snapshot):
    """Project genuine saved legacy graphs; never infer a graph from extraction."""
    from ..structure_models import Workspace
    saved = {}
    # A failed replacement may retain its earlier successful graph in history.
    for row in [*_rows(snapshot, "structure_history"), *_rows(snapshot, "structure_runs")]:
        try:
            workspace = Workspace.model_validate_json(row["payload"])
        except (ValueError, TypeError, KeyError):
            continue
        if workspace.task_id != state.task.task_id or not workspace.graph or workspace.status not in {"ready", "partial"}:
            continue
        previous = saved.get(workspace.structure_id)
        if previous is None or workspace.version > previous.version:
            saved[workspace.structure_id] = workspace
    content_id = f"content_legacy_{hashlib.sha256(state.task.task_id.encode()).hexdigest()[:24]}"
    if not any(item.id == content_id for item in project.contents):
        return []
    reports = []
    for workspace in sorted(saved.values(), key=lambda value: value.updated_at):
        resource = next((item for item in project.resources if item.id == workspace.video_id), None)
        original = [item for item in state.analyses if item.video_id == workspace.video_id]
        revision = next((index + 1 for index, item in enumerate(original)
                         if item.analysis_id == workspace.analysis_ref.id and item.revision == workspace.analysis_ref.revision), None)
        evidence = next((item for item in resource.evidence if item.revision == revision), None) if resource else None
        if resource is None or evidence is None:
            continue
        events = {event.id: event for event in evidence.events}
        external = {item.id: item for item in workspace.sources}
        contexts = {item.id: item for item in workspace.contexts}
        nodes = []
        incomplete = False
        for node in workspace.graph.nodes:
            refs = []
            for event_id in node.event_ids:
                event = events.get(event_id)
                if event is None:
                    incomplete = True
                    continue
                refs.append(SourceRef(resource_id=resource.id, evidence_revision=revision,
                    event_id=event.id, locator=node.label, excerpt=event.text,
                    start_seconds=event.start_seconds, end_seconds=event.end_seconds))
            for source_id in node.source_ids:
                source = external.get(source_id)
                if source:
                    refs.append(SourceRef(url=source.url, locator=source.title, excerpt=source.claim))
                else:
                    incomplete = True
            for context_id in node.context_ids:
                context = contexts.get(context_id)
                if context:
                    refs.append(SourceRef(locator=f"Archived user context: {context.id}", excerpt=context.text))
                else:
                    incomplete = True
            if not refs:
                incomplete = True
                continue
            nodes.append(StructureNode(id=node.id, label=node.label, detail=node.explanation,
                kind="interpretation" if node.kind == "inference" else node.kind, sources=refs))
        if not nodes:
            continue
        node_ids = {node.id for node in nodes}
        edges = [StructureEdge(source=edge.from_node, target=edge.to_node, label=edge.relation,
                    explanation=edge.explanation) for edge in workspace.graph.edges
                    if edge.from_node in node_ids and edge.to_node in node_ids]
        sources = [source for node in nodes for source in node.sources]
        graph = ReferenceStructure(resource_id=resource.id, summary=workspace.graph.summary, nodes=nodes, edges=edges)
        limits = ["Restored saved legacy Structure analysis. Original graph and full history remain in the local legacy archive."]
        if incomplete:
            limits.append("Some archived graph sources could not be resolved; unsupported nodes/links remain in the archive instead of receiving invented timestamps.")
        if workspace.origin == "sample":
            limits.append("This is an explicitly fictional sample analysis, not a live provider result.")
        if workspace.research_note:
            limits.append(workspace.research_note)
        reports.append(Analysis(id="analysis_legacy_structure_" + hashlib.sha256(
            f"{workspace.structure_id}:{workspace.graph_revision}".encode()).hexdigest()[:24],
            content_id=content_id, conclusion=workspace.graph.summary,
            findings=[method.title for method in workspace.graph.methods][:5],
            opportunities=[method.explanation for method in workspace.graph.methods],
            inputs=InputManifest(resource_ids=[resource.id], evidence_revisions={resource.id: revision},
                                 instruction_version="legacy-structure"),
            sources=sources, structures=[graph], limitations=limits,
            needs_review=workspace.outdated or incomplete, created_at=workspace.updated_at))
    return reports


def _restore_extraction_diagnostics(project, state):
    changed = False
    for resource in project.resources:
        originals = [item for item in state.analyses if item.video_id == resource.id]
        for revision, original in enumerate(originals, start=1):
            evidence = next((item for item in resource.evidence if item.revision == revision), None)
            if evidence is None:
                continue
            affected = [evidence]
            if revision == len(originals):
                # 1.8 correction revisions inherit their extraction processor.
                # Stop at the first actual recognition result: its processor is
                # different, and its success must not be undone by old failures.
                for descendant in sorted(resource.evidence, key=lambda item: item.revision):
                    if descendant.revision <= revision:
                        continue
                    if descendant.processor != evidence.processor or not descendant.correction_note:
                        break
                    affected.append(descendant)
            for channel, error in original.extraction_failures.items():
                code, _ = public_failure(ProviderError(error.code, error.message))
                for item in affected:
                    if channel not in item.diagnostics:
                        item.diagnostics[channel] = code
                        changed = True
                    # Retained partial speech can have observations plus a
                    # failed later chunk. The archived failure is authoritative.
                    if item.coverage.get(channel) != "failed":
                        item.coverage[channel] = "failed"
                        changed = True
                    if item is resource.evidence[-1] and resource.status == "ready":
                        resource.status = "partial"
                        changed = True
    return changed


def _project(state: TaskState, snapshot: dict, media_root: Path):
    task = state.task
    identifier = "project_legacy_" + hashlib.sha256(task.task_id.encode()).hexdigest()[:32]
    project = Project(id=identifier, title=task.title, legacy_task_id=task.task_id,
                      created_at=task.created_at.isoformat(), updated_at=task.updated_at.isoformat())
    lifecycle = _rows(snapshot, "task_lifecycle")
    if lifecycle:
        project.trashed_at = lifecycle[0].get("trashed_at")
    brief_refs = {}
    for brief in state.briefs:
        revision = len(project.briefs) + 1
        project.briefs.append(BriefRevision(revision=revision, facts=_facts(brief.model_dump(),
            [claim.model_dump() for claim in brief.claim_details], confirmed=True), created_at=brief.created_at.isoformat()))
        brief_refs[(brief.brief_id, brief.revision)] = revision
    project.brief_draft = project.briefs[-1].facts.copy() if project.briefs else []
    for row in _rows(snapshot, "m2_drafts"):
        draft = json.loads(row["payload"])
        project.editor_drafts["legacy:m2"] = draft
        project.brief_draft = _facts(draft.get("fields", {}), draft.get("claims", []), confirmed=False)
    for row in _rows(snapshot, "editor_drafts"):
        project.editor_drafts[f"legacy:{row['scope']}"] = json.loads(row["payload"])
    copies = []
    resources = {}
    evidence_refs = {}
    for video in state.videos:
        name = Path((video.original_file_name or f"{video.video_id}.mp4").replace("\\", "/")).name
        original_relative = f"sources/media/{video.video_id}/{name}"
        source = media_root / video.storage_id if video.storage_id else None
        exists = bool(source and source.is_file() and not source.is_symlink() and source.resolve().parent == media_root.resolve() and video.deleted_at is None)
        sha256 = video.content_sha256 or (_digest(source) if exists else "")
        valid = exists and (not sha256 or _digest(source) == sha256)
        resource = Resource(id=video.video_id, name=name, kind="video", role="reference" if video.purpose == "reference" else "asset",
            folder_id="folder_references" if video.purpose == "reference" else "folder_production_assets",
            origin="legacy", source_url=video.source_url, provenance=video.origin.description,
            original_path=original_relative, sha256=sha256, size_bytes=source.stat().st_size if exists else 0,
            mime_type="video/mp4", duration_seconds=video.duration_seconds, created_at=video.created_at.isoformat(),
            status="ready" if valid else "missing", error=None if valid else "The original was missing, deleted, or changed in the legacy library. Historical evidence is retained.",
            media_metadata={"legacy_video": video.model_dump(mode="json"),
                "frame_timing": video.frame_timing.model_dump(mode="json") if video.frame_timing else None,
                "width": video.width, "height": video.height, "video_codec": video.video_codec,
                "audio_codec": video.audio_codec, "has_audio": video.has_audio})
        if valid:
            copies.append((source, original_relative, sha256))
        if video.playback and valid:
            proxy = media_root / video.playback.storage_id
            if proxy.is_file() and not proxy.is_symlink() and proxy.resolve().parent == media_root.resolve():
                relative = f"cache/playback/{video.playback.storage_id}"
                resource.playback_path = relative
                resource.media_metadata["playback_frame_timing"] = video.playback.frame_timing.model_dump(mode="json")
                resource.media_metadata["playback_duration_seconds"] = video.playback.duration_seconds
                copies.append((proxy, relative, _digest(proxy)))
        for analysis in [item for item in state.analyses if item.video_id == video.video_id]:
            events = []
            limitations = ["Imported legacy extraction; its coverage and original records remain archived."]
            for event in analysis.events:
                if event.legacy_seconds:
                    start, end = event.legacy_seconds.start_seconds, event.legacy_seconds.end_seconds
                elif video.frame_timing and event.start_frame is not None and event.end_frame is not None:
                    boundaries = video.frame_timing.frame_boundaries_seconds
                    start, end = boundaries[event.start_frame], boundaries[event.end_frame]
                else:
                    limitations.append(f"Event {event.event_id} is retained in the legacy archive because its timing cannot be mapped.")
                    continue
                events.append(EvidenceEvent(id=event.event_id,
                    kind={"visual_action": "visual", "speech": "speech", "on_screen_text": "on_screen_text"}.get(event.kind, "sound"),
                    text=event.text or event.description or "", start_seconds=start, end_seconds=end,
                    start_frame=event.start_frame, end_frame=event.end_frame))
            revision = len(resource.evidence) + 1
            coverage = analysis.coverage.model_dump()
            diagnostics = {}
            for channel, error in analysis.extraction_failures.items():
                coverage[channel] = "failed"
                code, message = public_failure(ProviderError(error.code, error.message))
                diagnostics[channel] = code
                limitations.append(message)
            resource.evidence.append(EvidenceRevision(revision=revision, events=events, coverage=coverage, diagnostics=diagnostics,
                limitations=limitations, processor=analysis.origin.description, created_at=analysis.created_at.isoformat(),
                reviewed=analysis.review.user_confirmed, correction_note="Imported correction history is preserved in legacy/task-state.json." if analysis.corrections else None))
            evidence_refs[(analysis.analysis_id, analysis.revision)] = (video.video_id, revision)
        project.resources.append(resource)
        resources[video.video_id] = resource
    if task.current_video_id and task.current_video_id in resources:
        project.selection = Selection(resource_ids=[task.current_video_id])
    content = ContentItem(id=f"content_legacy_{hashlib.sha256(task.task_id.encode()).hexdigest()[:24]}",
                          title=task.title, selection=project.selection.model_copy(deep=True))

    def inputs(artifact):
        manifest = InputManifest(brief_revision=brief_refs.get((artifact.brief_ref.id, artifact.brief_ref.revision)))
        if artifact.analysis_ref:
            matched = evidence_refs.get((artifact.analysis_ref.id, artifact.analysis_ref.revision))
            if matched:
                manifest.resource_ids = [matched[0]]
                manifest.evidence_revisions = {matched[0]: matched[1]}
        if hasattr(artifact, "direction_ref"):
            manifest.direction_id, manifest.direction_revision = artifact.direction_ref.id, artifact.direction_ref.revision
        return manifest

    def sources(artifact):
        manifest = inputs(artifact)
        refs = []
        for citation in artifact.evidence:
            revision = manifest.evidence_revisions.get(citation.video_id)
            resource = resources.get(citation.video_id)
            evidence = next((item for item in resource.evidence if item.revision == revision), None) if resource else None
            event = next((item for item in evidence.events if item.id == citation.event_id), None) if evidence else None
            refs.append(SourceRef(resource_id=citation.video_id, event_id=citation.event_id,
                evidence_revision=revision, locator=citation.reason, excerpt=event.text if event else "",
                start_seconds=event.start_seconds if event else None, end_seconds=event.end_seconds if event else None))
        return refs

    for direction in state.directions:
        content.directions.append(Direction(id=direction.direction_id, revision=direction.revision, title=direction.core_message,
            concept=direction.rationale, hook=direction.hook, narrative=direction.narrative, cta=direction.cta,
            inputs=inputs(direction), sources=sources(direction), approved=direction.approval_status == "approved",
            approved_at=direction.approved_at.isoformat() if direction.approved_at else None,
            needs_review=direction.currentness == "outdated", created_at=direction.created_at.isoformat()))
    if task.selected_direction:
        content.approved_direction_id, content.approved_direction_revision = task.selected_direction.id, task.selected_direction.revision
    project.contents.append(content)
    project.active_content_id = content.id
    project.analyses.extend(_structure_reports(project, state, snapshot))
    paired = set()
    for brief in state.production_briefs:
        board = next((item for item in state.storyboards if brief.bundle_id and item.bundle_id == brief.bundle_id and item.direction_ref == brief.direction_ref and item.brief_ref == brief.brief_ref and item.analysis_ref == brief.analysis_ref), None)
        if board:
            paired.add((board.output_id, board.revision))
        text = "\n\n".join([brief.title, brief.core_message, f"Hook: {brief.hook}", brief.narrative, f"CTA: {brief.cta}", *brief.production_notes])
        project.packs.append(ProductionPack(id=brief.output_id, revision=brief.revision, content_id=content.id,
            inputs=inputs(brief), production_brief=text, storyboard=_storyboard(board) if board else "",
            script="", shot_list="", sources=sources(brief), needs_review=brief.currentness == "outdated" or board is None,
            created_at=brief.created_at.isoformat()))
    for board in state.storyboards:
        if (board.output_id, board.revision) not in paired:
            project.packs.append(ProductionPack(id=board.output_id, revision=board.revision, content_id=content.id,
                inputs=inputs(board), production_brief="", storyboard=_storyboard(board), script="", shot_list="",
                needs_review=True, created_at=board.created_at.isoformat()))
    return project, copies


def _storyboard(board):
    def cell(value):
        return (value or "").replace("|", "\\|").replace("\n", " ")
    rows = ["| Time | Visual | Dialogue | Screen text | Sound |", "| --- | --- | --- | --- | --- |"]
    rows.extend(f"| {row.start_seconds:g}–{row.end_seconds:g}s | {cell(row.visual)} | {cell(row.dialogue)} | {cell(row.on_screen_text)} | {cell(row.sound)} |" for row in board.rows)
    return "\n".join(rows)


def migrate_legacy(store, legacy_service) -> list[Project]:
    """Import each legacy task once; source DB/media are never changed or removed."""
    database = Path(legacy_service.store.path)
    if not database.is_file():
        return []
    imported = []
    store.migration_errors = []
    with sqlite3.connect(f"{database.resolve().as_uri()}?mode=ro", uri=True, timeout=15) as db:
        db.execute("BEGIN")
        tasks = db.execute("SELECT id,payload FROM tasks ORDER BY rowid").fetchall()
        for task_id, payload in tasks:
            try:
                project = _import_one(store, legacy_service, db, task_id, payload)
                if project is not None:
                    imported.append(project)
            except (OSError, ValueError, WorkflowError, sqlite3.Error) as error:
                code = error.code if isinstance(error, WorkflowError) else "legacy_import_failed"
                store.migration_errors.append(f"{task_id}: {code}. This older project's original records and files are intact; inspect it in the legacy workspace.")
    return imported


def _import_one(store, legacy_service, db, task_id, payload):
    identifier = "project_legacy_" + hashlib.sha256(task_id.encode()).hexdigest()[:32]
    if store.project_dir(identifier).exists():
        existing = store.get(identifier, include_trashed=True)
        if existing.legacy_task_id != task_id:
            raise WorkflowError("legacy_destination_conflict", "The destination belongs to another project.", 409)
        # 1.8.0 archived Structure runs but did not project them into Analysis.
        # Recover only that frozen archive, never resync later legacy edits.
        archive = store.resolve_path(identifier, "legacy/related-records.json")
        saved_state = store.resolve_path(identifier, "legacy/task-state.json")
        if archive.is_file() and saved_state.is_file():
            records = json.loads(archive.read_text(encoding="utf-8"))
            old_state = TaskState.model_validate_json(saved_state.read_text(encoding="utf-8"))
            candidates = _structure_reports(existing, old_state, records)
            def backfill(current):
                known = {item.id for item in current.analyses}
                missing = [item for item in candidates if item.id not in known]
                changed = _restore_extraction_diagnostics(current, old_state)
                if not missing and not changed:
                    return False
                # Existing successful 1.8 analysis stays current.
                current.analyses = [*missing, *current.analyses]
            store._update(identifier, None, backfill, include_trashed=True)
        return None
    state = TaskState.model_validate_json(payload)
    snapshot = _snapshot(db, task_id)
    project, copies = _project(state, snapshot, legacy_service.media.root)

    def prepare(stage):
        archive = stage / "legacy"
        archive.mkdir()
        (archive / "task-state.json").write_text(payload, encoding="utf-8")
        (archive / "related-records.json").write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
        with sqlite3.connect(archive / "records.sqlite3") as saved:
            saved.execute("CREATE TABLE legacy_records (table_name TEXT PRIMARY KEY, columns_json TEXT NOT NULL, rows_json TEXT NOT NULL)")
            for table, record in snapshot.items():
                saved.execute("INSERT INTO legacy_records VALUES (?,?,?)", (table, json.dumps(record["columns"]), json.dumps(record["rows"], ensure_ascii=False)))
        for source, relative, digest in copies:
            destination = stage / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            if digest and _digest(destination) != digest:
                raise WorkflowError("legacy_source_changed", "A source changed during import. The original library is intact; retry after closing the older app.", 409)
    return store.import_project(project, prepare)
