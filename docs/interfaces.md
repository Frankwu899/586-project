# Interface contract — v0.3.0

`backend/app/models.py` is the authoritative maintained record definition. Pydantic performs runtime and semantic validation; `scripts/export_contracts.py` generates `contracts/v0.3.task-state.schema.json` and `contracts/v0.3.analysis.schema.json`. Frontend types are generated from the task schema into `frontend/src/generated/contracts.ts`. Change the models, generated artifacts, validators, fixtures, and consumers together. The original v0.1 schema/examples and all v0.2 schema/examples remain unchanged as historical snapshots; current records use v0.3.0.

## Records and ownership

| Record | Main information | Owner |
|---|---|---|
| `CreativeTask` | Stable task ID, mode/progress, optimistic `version`, current artifact references | Workflow service |
| `BrandTaskBrief` | Stable brief ID and revision, required brand inputs, positive target duration, optional production constraints | User through versioned save |
| `VideoAsset` | Task/video identity, reference/draft purpose, input/provenance, generated storage reference, measured media properties and intake status | Media intake |
| `EvidenceEvent` | Stable event/video ID, reference-video frame ranges, visual/audio lane and kind, canonical text/description, source/method, optional uncertainty | Recognition adapter; permitted content correction |
| `ContentSegment` | Stable section/video ID, reference-video interval, roles, event IDs, separate interpretation | Recognition adapter; permitted role correction |
| `AnalysisResult` | Exact task/video identity, processing state, events/sections, per-category coverage, origin, correction lineage and review | Recognition plus workflow service |
| `CreativeDirection` | Exact brief/analysis/feedback references, message/Hook/narrative/CTA, production requirements, evidence/rationale/hypotheses, draft/approval/currentness | Creative adapter plus user edits/approval |
| `CreativeFeedback` | Saved instruction, exact target draft and upstream references, result draft or explicit uninterpreted status | Workflow and creative adapter |
| `ProductionCreativeBrief`, `TextStoryboard` | Output revisions, exact approved direction and upstream references, content/planned timing, origin/currentness | Production adapter plus user edits |
| `ProcessingJob`, `ErrorInfo` | Operation and exact inputs, processing/result state, error code/message/retryability | Workflow service |
| `TaskState` | Task aggregate with all revision collections and jobs | Persistent storage boundary |

Every versioned reference is `{"id":"artifact_id","revision":1}`. IDs are stable identifiers, not file paths. Record timestamps include a timezone and normalize to UTC. Unknown metrics are `null`; observed zero is `0`. A metric snapshot must match its video's source URL. Origin is explicitly `sample`, `provider`, `manual`, or `legacy`, with a description. A correction retains the original origin: editing fictional evidence does not make it real.

## Time, evidence, coverage, and validation

Evidence events and content sections use zero-based integer frame indices from the original reference video, with half-open intervals `[start_frame, end_frame)`: `0 <= start < end <= frame_count`. A one-frame event is valid, such as `[60, 61)`; `[60, 65)` contains five frames. Evidence may overlap, including visual and audio events; an event may cross a section boundary and be referenced by both sections. Primary sections must be ordered and nonoverlapping. A section's cited event must overlap it. Duplicate IDs, dangling event IDs, wrong-video/task references, and wrong-revision citations are rejected.

`VideoAsset.frame_timing` supplies the exact rational rate (`fps_numerator` / `fps_denominator`), decoded `frame_count`, `rate_mode` (`constant` or `variable`), `source="probed"`, and `frame_boundaries_seconds`. The boundary array has `frame_count + 1` finite, strictly increasing entries, begins at zero, and ends at `duration_seconds`. Its first `frame_count` entries are decoded presentation timestamps relative to the first frame. `media_start_seconds` preserves that first frame's timestamp on the media playback clock, including files whose playback begins after zero. Source frame indices remain zero-based regardless of this offset. `AnalysisResult.frame_count` must match the associated video. Duration remains measured metadata, not the source event unit.

The loader reads actual frame timestamps with ffprobe; it does not export a separate image for every frame. Constant, fractional, and variable rates use the same frame map. Browser seeking converts a frame boundary to seconds and adds `media_start_seconds`. Display uses `HH:MM:SS:FF` at the rounded nominal frame rate (non-drop-frame), alongside the authoritative frame indices; fractional/VFR timecodes are approximate and need not match elapsed wall-clock time. This is review-level accuracy, not an editing/export timebase.

Provider adapters that return seconds should call `backend/app/timing.py::seconds_to_frame_range(start_seconds, end_seconds, video.frame_timing)`. It chooses the nearest recorded boundaries, clamps to the video, and preserves at least one frame. Revalidate section order and citation overlaps after quantization; do not silently remove a citation to make a provider result fit. `frame_to_seconds` returns a normalized reference boundary for playback/adapter use; browser playback additionally needs the stored media origin.

Event kinds are `visual_action`, `on_screen_text`, `speech`, `music`, and `sfx`; the first two use lane `visual`, the remainder `audio`. Text or description must be present. Content sections contain `evidence_ids` and optional `interpretation`, not independently editable copies of recognized content. Roles are `hook`, `product_demo`, `proof`, `cta`, and `other`; `other` is exclusive. A `proof` role describes a rhetorical claim, not independent verification.

Coverage is recorded separately for every event kind:

| Value | Meaning |
|---|---|
| `not_analyzed` | No extraction was performed for this category; absence is unknown. |
| `observations` | One or more events of this category exist. |
| `none_found` | The category was checked and no observations were found. |
| `failed` | This category failed to extract; absence is unknown. |

Coverage must agree with the event collection. `succeeded` cannot contain failed categories; `partial` must identify a failed category. Failed/pending/running analyses cannot contain usable observations or a review confirmation. A completed result without events requires `empty_result_reason`. A failed result requires an actionable error. The current workflow **does not allow partial analyses into creative generation**; only a current, confirmed `succeeded` result with known frame timing is accepted. `not_analyzed` categories can remain in a successful result and are shown honestly during review; confirmation does not imply they were checked.

A creative citation includes `analysis_id`, `analysis_revision`, `video_id`, `event_id`, and `reason`. It must resolve inside the exact recorded analysis revision in the same task. Storyboard rows retain `start_seconds` and `end_seconds` on a separate planned-new-video clock: ordered, nonoverlapping intervals starting at zero and finishing at the brief's `target_duration_seconds`. Cited reference frame ranges remain in the referenced analysis; source FPS and duration never set a storyboard frame rate or replace the target duration. Storyboard suggestions have no FPS setting.

## Revision and approval rules

A task's optimistic `version` increases on every persisted mutation. Send the latest version with a mutation; `version_conflict` means reload the task and reconsider the pending edit. Artifact `revision` numbers identify content versions and have a different purpose.

- The original extraction stays at analysis revision 1. Content/role corrections append a revision with the same analysis/event/section IDs, preserve timing/provenance, record before/after changes, and clear review confirmation. Allowed corrections are event text, visual description, and section roles. Identity, timing, lanes/kinds, evidence links, and provenance are not correction fields. Affected interpretation is cleared.
- **Use this reviewed analysis** confirms the exact current revision separately. Confirmation metadata does not create an artificial content revision. Rerunning recognition creates a new analysis ID and preserves prior results.
- Direction generation and refinement require the current brief and successful, confirmed analysis for the task's current video. The backend rejects unconfirmed, incomplete, failed, partial, outdated, or mismatched inputs even if a client sends the request directly.
- Direct editing or supported prompt refinement produces an unapproved direction draft. Feedback records the instruction and exact target revision before processing, then its result or explicit `not_interpreted` outcome. Selection and generation never imply approval.
- `CreativeTask.chosen_direction` persists an exact unapproved draft choice across refresh/restart. `selected_direction` identifies the explicitly approved choice used for production. Choosing a different draft clears the previous approval and marks its outputs outdated; selecting a draft never grants approval.
- Production generation requires the exact selected, current, explicitly approved direction revision and matching upstream inputs. Brief/video/analysis changes invalidate downstream approval/currentness. Direction edits/refinement invalidate outputs for that direction. Older content remains available, marked `outdated`.
- Output edits append revisions; explicit whole-output regeneration preserves previous manual work. No partial row generation is implemented. Atomic storage/version checks prevent a delayed result or stale browser tab from overwriting newer work.

## Saved v0.2 task migration

`backend/app/frame_migration.py::migrate_v02_task(payload, media_root)` converts all reference intervals and analysis revisions using one actual frame map per video. `TaskStore` runs migration at startup and on loading a legacy row. It validates the preserved v0.2 schema, checks saved media identity when a SHA-256 is present, retains IDs, correction logs, exact references and output seconds, and increments the task version once. For available matching media, review/approval and current creative content remain valid. The SQLite `task_migration_archive` table stores the exact original JSON string and its SHA-256 in the same transaction as replacement; a failed migration leaves the old record unchanged. Reopening is idempotent. Back up the complete data directory, including media, before transferring it between machines.

If media is missing, changed, unreadable, or old subframe intervals cannot preserve section/citation relationships after rounding, the archived analysis keeps `legacy_seconds: {start_seconds, end_seconds}` with null frame fields/count. Its video's frame timing is null; no default FPS is invented. Content and historical review remain readable, but affected creative artifacts become outdated and approval is cleared. Confirmation and new creative use return `frame_timing_unavailable`; upload and analyze the source again to continue. This legacy fallback cannot mix with frame intervals in one analysis.

## Legacy v0.1 migration

The existing `examples/analysis_result.original.json`, `examples/analysis_result.json`, and `contracts/analysis.schema.json` are preserved unchanged. Use the explicit conversion API in `backend/app/migration.py`: `migrate_legacy_analysis(data, original=None)` returns an `AnalysisResult`; `migrate_legacy_examples(original, revised)` returns a validated `TaskState` with both analysis revisions. The migration CLI writes a new file:

```bash
.venv/bin/python -m backend.app.migration \
  --original examples/analysis_result.original.json \
  --revised examples/analysis_result.json \
  --output .local-data/legacy-migrated.json
```

The supplied migrated fixture is `examples/v0.3.legacy-migrated.json`. Segment text/observations become canonical events with stable derived IDs, while sections reference them. Missing/unknown values and fictional provenance remain explicit. No real provider/model run is invented. The legacy media record has no storage ID and remains `missing`; `SYNTHETIC_LumaCup_demo_NO_MEDIA.mp4` is a historical fictional name, not a playback asset. Its source has no known FPS, so v0.3 stores original intervals in `legacy_seconds` and leaves frame fields null. This CLI produces contract data, not an uploaded playable task. Do not substitute it for the dedicated generated sample workflow.

## HTTP operations

Routes are implemented in `backend/app/api.py`; the local OpenAPI reference is `http://127.0.0.1:8000/docs`. Requests and responses are JSON except multipart upload, video playback, and exports. Every task mutation returns the complete saved `TaskState`; use the returned `task.version` for the next mutation. IDs and revision references in this table come from that saved state, never from unsaved UI fields.

For compactness, `V` below means required `expected_version`; `I` means `V`, `brief_ref`, and `analysis_ref`. Each reference uses `{id, revision}`.

| Method and path | Request / response |
|---|---|
| `GET /api/health` | Version and explicit real-analysis/creative-mode status. |
| `GET /api/config` | Actual configured upload limits, supported media, sample-refinement phrase, and language assumption. |
| `POST /api/tasks` | `{title}` → new task (`201`). |
| `GET /api/tasks` | Array of saved task aggregates. |
| `GET /api/tasks/{task_id}` | Reopen one saved task aggregate. |
| `POST /api/tasks/{task_id}/brief` | `{V, brief}`; brief contains user input fields only, without server-owned identity/revision/timestamps. |
| `POST /api/tasks/{task_id}/sample` | `{V}`; requires a task with no video, creates matching synthetic media and a sample brief if no brief exists. |
| `POST /api/tasks/{task_id}/video` | Multipart `file`, `expected_version`, optional `source_url`; measures/validates media and sets real mode. |
| `GET /api/tasks/{task_id}/media/{video_id}` | Saved MP4 playback response; video must belong to this task. |
| `POST /api/tasks/{task_id}/recognize` | `{V, video_id?}`; operates on the current video and records analysis/job result. |
| `POST /api/tasks/{task_id}/analysis/correct` | `{V, analysis_ref, event_edits?, segment_edits?}`; event edits identify `event_id` and allowed `text`/`description`; section edits identify `segment_id` and `roles`. |
| `POST /api/tasks/{task_id}/analysis/confirm` | `{V, analysis_ref}`; explicit review of the current successful revision. |
| `POST /api/tasks/{task_id}/directions/generate` | `{I}`; two current draft directions with exact inputs. |
| `POST /api/tasks/{task_id}/directions/{direction_id}/select` | `{V, direction_revision}`; persist a current draft choice separately from approval. |
| `POST /api/tasks/{task_id}/directions/{direction_id}/edit` | `{V, direction_revision, fields}`; editable fields are `core_message`, `hook`, `narrative`, `cta`. |
| `POST /api/tasks/{task_id}/directions/{direction_id}/refine` | `{I, direction_revision, instruction}`; instruction is 1–10,000 characters; saves exact target and adapter outcome. |
| `POST /api/tasks/{task_id}/directions/{direction_id}/approve` | `{I, direction_revision}`; explicitly selects and approves that exact current revision. |
| `POST /api/tasks/{task_id}/outputs/generate` | `{I, direction_ref}`; generate or explicitly regenerate production materials. |
| `POST /api/tasks/{task_id}/outputs/edit` | `{V, production_brief_ref, storyboard_ref, brief_fields?, rows?}`; save production text revisions. |
| `GET /api/tasks/{task_id}/export/brief.md` | Readable Markdown, including origin/currentness and exact input references. |
| `GET /api/tasks/{task_id}/export/storyboard.csv` | CSV with planned timing, text, reference citations, origin/currentness and input versions. |

Production brief edits allow `title`, `core_message`, `hook`, `narrative`, `cta`, and `production_notes`. When editing storyboard text, send complete current rows with unchanged row IDs/order, times, and evidence links. Editable text is `visual`, `dialogue`, `on_screen_text`, `sound`, and `cta`. Planned timing edits are not exposed in this skeleton. CSV quoting preserves commas/newlines; formula-like cell contents are prefixed with an apostrophe. Markdown escapes active markup from user content.

### Valid request example

With the backend running, this example creates an isolated dedicated sample task, recognizes its matching media, saves a visual-description correction, and confirms that exact revision. It uses actual returned IDs rather than fictional hard-coded media references. It calls only local sample operations, not a model provider:

```python
import httpx

api = httpx.Client(base_url="http://127.0.0.1:8000", timeout=120)
response = api.post("/api/tasks", json={"title": "Fictional API walkthrough"})
response.raise_for_status()
state = response.json()
task_id = state["task"]["task_id"]

def mutate(path, **fields):
    global state
    response = api.post(f"/api/tasks/{task_id}/{path}", json={
        "expected_version": state["task"]["version"], **fields,
    })
    response.raise_for_status()
    state = response.json()
    failed = [job for job in state["jobs"] if job["status"] == "failed"]
    if failed:
        raise RuntimeError(failed[-1]["error"])

mutate("sample")
mutate("recognize", video_id=state["task"]["current_video_id"])
mutate("analysis/correct", analysis_ref=state["task"]["current_analysis"],
       event_edits=[{"event_id": "event_lid_shape",
                     "description": "An orange illustrated lid rises during seconds 3–4 and then stays above the blue shape."}])
mutate("analysis/confirm", analysis_ref=state["task"]["current_analysis"])
mutate("directions/generate", brief_ref=state["task"]["current_brief"],
       analysis_ref=state["task"]["current_analysis"])
print(task_id, state["task"]["version"])
```

For a valid brief payload, use the user-input fields in `backend/app/sample.py::sample_brief`, omitting `brief_id`, `task_id`, revision, schema version, and timestamps. Complete validated artifact examples live under `examples/`; generated video files remain in ignored storage.

### Errors, jobs, and retries

Rejected requests use `{"error":{"code":"...","message":"...","retryable":false}}`. Invalid input is `422`; missing task/video/media/export is `404`; revision/workflow conflicts usually use `409`. Codes distinguish `version_conflict`, `outdated_inputs`, `analysis_unconfirmed`, `analysis_not_succeeded`, `frame_timing_unavailable`, `direction_unapproved`, `outdated_direction`, `immutable_analysis_field`, and other actionable restrictions. Read the response message; do not erase local drafts or automatically approve to bypass a conflict.

Generation operations persist `ProcessingJob` transitions and return the saved task even if the operation failed. Therefore an HTTP `200` does **not** establish recognition/generation success: inspect the job status/error and the analysis processing state. An unconfigured real upload records `real_analysis_not_configured` and produces no sample observations. A malformed adapter result records `invalid_adapter_result` without saving invalid generated content.

A failed, stale, or interrupted refinement closes its linked pending feedback as `not_interpreted`, with an explanation containing the failure code. The original instruction and prior draft remain saved; this status does not turn the failed job into a success. The sample-loading CLI checks each new job's terminal status and expected result before advancing or reporting a completed walkthrough.

The sample operations are synchronous; there is no background polling requirement or automatic retry loop. Retry by reopening the task and submitting a new explicit operation with current versions. A job completing after another write records `stale_result`, discards the delayed output, and preserves the newer saved work. The current job record and completed/failed jobs remain inspectable in task history. On backend startup, interrupted pending/running jobs become failed with `interrupted_job` and `retryable=true`; the task version increases. Reopen the task and retry explicitly. Run one backend worker so another worker cannot misclassify a live operation as interrupted. Do not retry permanent configuration/media errors without fixing their cause.

## Media boundary

`backend/app/media.py::MediaStore` stores files under generated identifiers, never user-supplied paths. The implemented intake accepts `.mp4` with one H.264 video stream and zero or one AAC audio stream. It probes metadata and presentation-order frames, retaining their timing map, and decodes the content; file extensions alone are insufficient. Missing audio is recorded as `has_audio=false`, not recognition success or evidence that a speech extractor ran.

Defaults are 52,428,800 bytes (50 MiB), 180 seconds, and at most 1920×1920 pixels, with 15-second probe and 60-second decode timeouts. Environment settings are listed in `.env.example`; `/api/config` returns active limits. `FFMPEG_BIN` and `FFPROBE_BIN` select the executables. Rejected inputs distinguish missing/unreadable/empty media, size/duration limits, unsupported format/codec/streams/dimensions, absent tooling, and inspection timeout. Do not infer broad camera/device compatibility from the narrow generated MP4 test fixture. Source URLs are stored as provenance only.

## Recognition and creative adapter entry points

`backend/app/adapters.py` defines `RecognitionAdapter` and `CreativeAdapter` protocols. The service in `backend/app/service.py` owns persistence, currentness, approval, and job transitions; adapters receive saved input snapshots and return normalized objects. Adapters do not edit SQLite or overwrite user content. A provider-specific transport/parser belongs inside an adapter.

### Andrea: recognition

Implement `analyze(request: RecognitionRequest) -> AnalysisResult`. `RecognitionRequest` is a frozen dataclass with:

- `task_id`: the saved task's ID;
- `video`: its validated `VideoAsset`, including measured duration, probed frame timing and provenance;
- `job_id`: the current processing context;
- `task_mode`: `real` or `sample`;
- `media_path`: the backend-resolved local file path, never a frontend credential or arbitrary remote download request.

`WorkflowService.recognize` resolves the saved file, chooses the adapter, and validates the returned task/video association and aggregate contract before saving. Successful results use a new `analysis_id`, revision 1, matching task/video/duration/frame_count, canonical frame-based events, ordered sections, explicit coverage, honest origin, and an unconfirmed review. Provider output may need parsing and semantic normalization even if the provider advertises JSON output. Never fabricate a model run, confidence, absent extraction category, or success after an access failure.

`SampleRecognitionAdapter` verifies sample mode, sample provenance/key, expected duration, and the hash of the matching generated file. Otherwise it returns a failed result with `sample_media_mismatch`. `UnconfiguredRecognitionAdapter` returns a failed result with `real_analysis_not_configured`, `retryable=false`, no events, and a message explaining that the upload was saved but not recognized. It performs no paid request and has no silent sample fallback. A provider failure should likewise return a validated failed analysis or raise an exception exposing safe `code`, `message`, and `retryable` fields; raw provider response bodies and secrets do not belong in task records.

A valid adapter exercise is the `recognize` operation in the HTTP example above, which resolves `backend/app/sample.py::sample_analysis` through the same request boundary. `examples/v0.3.sample-task.json` contains the full saved sample with overlapping visual/audio events; the legacy migrated fixture separately exercises fictional speech without claiming matched speech playback. Run `scripts/load_sample.py --complete` to regenerate a complete local walkthrough with actual matching media, instead of treating serialized storage references as files available on another computer.

### Frank: creative generation

`CreativeAdapter` defines three operations:

```python
generate_directions(brief: BrandTaskBrief,
                    analysis: AnalysisResult) -> list[CreativeDirection]

refine_direction(brief: BrandTaskBrief,
                 analysis: AnalysisResult,
                 target: CreativeDirection,
                 feedback: CreativeFeedback) -> CreativeDirection | None

generate_production(brief: BrandTaskBrief,
                    analysis: AnalysisResult,
                    direction: CreativeDirection) -> tuple[ProductionCreativeBrief, TextStoryboard]
```

Direction generation returns exactly two distinct drafts. Each cites the exact input revisions and real event IDs from that analysis. Refinement receives the entire persisted `CreativeFeedback`, including the original instruction and exact target/input references. A supported refinement returns the next revision of that same direction, with `approval_status=draft`, no approval timestamp, and its feedback reference. `None` means no interpreted refinement; the service retains the instruction with `status=not_interpreted`, an explanation, and no invented resulting draft.

The deterministic sample accepts the case-insensitive literals **Make this direction presenter-free.**, **Make it presenter-free**, or **presenter-free** (with optional final period/exclamation mark). It visibly changes Hook, narrative, production requirements, and production notes; approved production output uses product-only imagery/text with no spoken dialogue. All other instructions are saved as user production notes in the feedback history and explicitly reported as uninterpreted; they do not silently modify a direction or establish unrestricted language understanding.

Production generation returns both outputs using the selected approved direction and its exact input/feedback references. The sample uses brand/product, approved messages, audience/platform/goal, optional constraints, direction text, and target duration to make a four-row plan. It preserves prohibited claims as production constraints and does not invent performance evidence. It is a template demonstration, not a claim that automatic generation can enforce every free-text production requirement or fact-check arbitrary user edits.

The service revalidates returned artifacts and discards invalid or stale results. Provider implementations must preserve these rules and origin labels. No UI changes or provider credentials are needed to run the current sample path.
