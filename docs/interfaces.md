# Interface contract — v0.4.0

`backend/app/models.py` is the authoritative maintained record definition. Pydantic performs runtime and semantic validation; `scripts/export_contracts.py` generates `contracts/v0.4.task-state.schema.json` and `contracts/v0.4.analysis.schema.json`. Frontend types are generated from the task schema into `frontend/src/generated/contracts.ts`. Change the models, generated artifacts, validators, fixtures, and consumers together. The v0.1, v0.2 and v0.3 schemas/examples remain unchanged as historical snapshots; current records use v0.4.0. The TypeScript generator omits JSON Schema conditionals from its structural input because it cannot represent them; authoritative schemas and runtime validators retain those constraints.

## Records and ownership

| Record | Main information | Owner |
|---|---|---|
| `CreativeTask` | Stable task ID, mode/progress, optimistic `version`, current artifact references | Workflow service |
| `BrandTaskBrief` | Stable brief ID and revision, required brand inputs, positive target duration, optional production constraints | User through versioned save |
| `VideoAsset` | Task/video identity, reference/draft purpose, input/provenance, generated storage reference, measured media properties and intake status | Media intake |
| `EvidenceEvent` | Stable event/video ID, reference-video frame ranges, visual/audio lane and kind, canonical text/description, source/method, optional uncertainty | Recognition adapter; permitted content correction |
| `VisualDetails` | Event-local subject, action and product-presentation groups with independent coverage/errors and local references | Recognition adapter; restricted label correction |
| `PlaybackRepresentation` | Derived H.264 MP4 storage, codec, measured duration and independent frame clock | Media intake |
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

The loader reads actual frame timestamps with ffprobe; it does not export a separate image for every frame. Constant, fractional, and variable rates use the same frame map. Browser seeking uses `video.playback.frame_timing` when a derivative exists, otherwise `video.frame_timing`: map the source-frame index through that clock and add its own `media_start_seconds`. Recognition always uses original-source timing. Display uses `HH:MM:SS:FF` at the rounded nominal frame rate (non-drop-frame), alongside the authoritative frame indices; fractional/VFR timecodes are approximate and need not match elapsed wall-clock time. This is review-level accuracy, not an editing/export timebase.

Provider adapters that return seconds should call `backend/app/timing.py::seconds_to_frame_range(start_seconds, end_seconds, video.frame_timing)`. It chooses the nearest recorded boundaries, clamps to the video, and preserves at least one frame. Revalidate section order and citation overlaps after quantization; do not silently remove a citation to make a provider result fit. `frame_to_seconds` returns a normalized reference boundary for playback/adapter use; browser playback additionally needs the stored media origin.

Event kinds are `visual_action`, `on_screen_text`, `speech`, `music`, and `sfx`; the first two use lane `visual`, the remainder `audio`. Text or description must be present. Content sections contain `evidence_ids` and optional `interpretation`, not independently editable copies of recognized content. Roles are `hook`, `product_demo`, `proof`, `cta`, and `other`; `other` is exclusive. A `proof` role describes a rhetorical claim, not independent verification.

Coverage is recorded separately for every event kind:

| Value | Meaning |
|---|---|
| `not_analyzed` | No extraction was performed for this category; absence is unknown. |
| `observations` | One or more events of this category exist. |
| `none_found` | The category was checked and no observations were found. |
| `failed` | This category failed to extract; absence is unknown. |

Coverage must agree with the event collection. `succeeded` cannot contain failed categories or failed structured groups; `partial` must identify at least one such failure. A nested failure preserves the parent visual event and its `observations` coverage. Failed/pending/running analyses cannot contain usable observations or a review confirmation. A completed result without events requires `empty_result_reason`. A failed result requires an actionable error. The current workflow **does not allow partial analyses into creative generation**; only a current, confirmed `succeeded` result with known frame timing is accepted. `not_analyzed` categories can remain in a successful result and are shown honestly during review; confirmation does not imply they were checked.

A creative citation includes `analysis_id`, `analysis_revision`, `video_id`, `event_id`, and `reason`. It must resolve inside the exact recorded analysis revision in the same task. Storyboard rows retain `start_seconds` and `end_seconds` on a separate planned-new-video clock: ordered, nonoverlapping intervals starting at zero and finishing at the brief's `target_duration_seconds`. Cited reference frame ranges remain in the referenced analysis; source FPS and duration never set a storyboard frame rate or replace the target duration. Storyboard suggestions have no FPS setting.

### Structured visual observations

`EvidenceEvent.visual_details` is nullable and permitted only for `kind=visual_action`. Null means structured analysis was unavailable or not performed; it does not mean there were no visible subjects. Non-null details require all three groups: `subjects`, `actions`, and `product_presentations`. Each has required `status`, `items`, and nullable `error`: items are nonempty exactly for `observations`, and an `ErrorInfo` is required exactly for `failed`. Other statuses require empty items and null error. Each group reports coverage independently of `Coverage.visual_action`.

| Item | Fields and validation |
|---|---|
| `VisualSubject` | Local unique `subject_id`; nullable `kind`; nonempty `label`; nullable nonempty `description`; nullable nonempty unique `roles`. `other` is exclusive among roles and requires a description when used as kind or role. |
| `VisualAction` | Nullable `action_type`; unique `actor_subject_ids` and `target_subject_ids`; nonempty `description`. Nonempty references resolve locally. Empty references express unlinked participants; the description explains the limitation. |
| `ProductPresentation` | Nonempty unique `product_subject_ids`; nullable `presentation_type`; nonempty `description`. Every referenced local subject must have the `product` role. |

Enums remain stable English codes:

- Subject kind: `person`, `animal`, `plant`, `physical_object`, `digital_interface`, `graphic`, `environment`, `other`.
- Subject roles: `product`, `presenter`, `product_user`, `context`, `other`.
- Action type: `hold`, `pick_up`, `put_down`, `open`, `close`, `pour`, `apply`, `operate`, `assemble`, `disassemble`, `wear`, `eat_drink`, `point`, `move`, `other`.
- Presentation type: `appearance`, `feature_demo`, `use_case`, `result_display`, `comparison`, `packaging`, `unboxing`, `other`.

JSON null expresses an unknown category; the string `"null"`, empty roles, `[null]`, and whitespace-only required descriptions are invalid. An unknown category is not an extraction failure. Nested observations inherit the parent source-frame interval; there are no nested timestamps, cross-shot identities, language/confidence fields or bounding boxes. OCR and ASR retain original English, Chinese and mixed-language words as separate event kinds. `ANALYSIS_OUTPUT_LANGUAGE` and `CREATIVE_OUTPUT_LANGUAGE` configure explanatory narrative independently and do not translate source evidence. `examples/v0.4.visual-analysis.json` is a tested synthetic bilingual contract example, not a result from supplied media.

## Revision and approval rules

A task's optimistic `version` increases on every persisted mutation. Send the latest version with a mutation; `version_conflict` means reload the task and reconsider the pending edit. Artifact `revision` numbers identify content versions and have a different purpose.

- The original extraction stays at analysis revision 1. Content/role corrections append a revision with the same analysis/event/section IDs, preserve timing/provenance, record before/after changes, and clear review confirmation. Allowed corrections are OCR/speech text, visual description, section roles and restricted visual labels. Identity, timing, lanes/kinds, evidence links, and provenance are not correction fields. Affected interpretation is cleared.
- **Use this reviewed analysis** confirms the exact current revision separately. Confirmation metadata does not create an artificial content revision. Rerunning recognition creates a new analysis ID and preserves prior results.
- Direction generation and refinement require the current brief and successful, confirmed analysis for the task's current video. The backend rejects unconfirmed, incomplete, failed, partial, outdated, or mismatched inputs even if a client sends the request directly.
- Direct editing or supported prompt refinement produces an unapproved direction draft. Feedback records the instruction and exact target revision before processing, then its result or explicit `not_interpreted` outcome. Selection and generation never imply approval.
- `CreativeTask.chosen_direction` persists an exact unapproved draft choice across refresh/restart. `selected_direction` identifies the explicitly approved choice used for production. Choosing a different draft clears the previous approval and marks its outputs outdated; selecting a draft never grants approval.
- Production generation requires the exact selected, current, explicitly approved direction revision and matching upstream inputs. Brief/video/analysis changes invalidate downstream approval/currentness. Direction edits/refinement invalidate outputs for that direction. Older content remains available, marked `outdated`.
- Output edits append revisions; explicit whole-output regeneration preserves previous manual work. No partial row generation is implemented. Atomic storage/version checks prevent a delayed result or stale browser tab from overwriting newer work.

The handoff's baseline field catalog interchanges the descriptions of `chosen_direction` and `selected_direction`. The live implementation and approval rules above are authoritative: `chosen_direction` is draft selection; `selected_direction` is the explicitly approved production choice. Migration preserves these pointers without swapping them.

Structured corrections submit a full `visual_details` object in the event edit. The server captures full before/after values and validates them atomically. Editable leaves are subject `kind`, `roles`, `label`, `description`; action `action_type`, `description`; and presentation `presentation_type`, `description`. Existing item positions, subject IDs, relationship arrays, group status/errors and array sizes remain fixed. Null details cannot be created or removed through correction. Removing a product role while a presentation references that subject is rejected; the server does not silently remove relationships. Replay must reproduce every editable field from the original extraction and preserve prior available correction history. Accepted edits clear current review and invalidate dependent approval/currentness while preserving historical outputs.

## Saved v0.3 task migration

`backend/app/contract_migration.py::migrate_v03_task(payload)` validates the historical schema and adds `visual_details=null` to every event and `playback=null` to every video. It changes record schema versions to v0.4.0 and increments only the optimistic task version; it preserves artifact IDs/revisions, timestamps, corrections, exact citations, reviews and approvals. It neither reruns extraction nor creates a playback derivative. `TaskStore` runs this migration at startup or load, archiving the exact original JSON and SHA-256 in `task_migration_archive` within the same transaction. Failure rolls back both archive and replacement; reopening is idempotent. The archive remains readable through SQLite's `original_payload` column. Back up the full data directory and media before transferring it.

## Saved v0.2 task migration

`backend/app/frame_migration.py::migrate_v02_task(payload, media_root)` converts all reference intervals and analysis revisions using one actual frame map per video and emits v0.4.0 directly with null structured details and playback. `TaskStore` runs migration at startup and on loading a legacy row. It validates the preserved v0.2 schema, checks saved media identity when a SHA-256 is present, retains IDs, correction logs, exact references and output seconds, and increments the task version once. For available matching media, review/approval and current creative content remain valid. The SQLite `task_migration_archive` table stores the exact original JSON string and its SHA-256 in the same transaction as replacement; a failed migration leaves the old record unchanged. Reopening is idempotent. Back up the complete data directory, including media, before transferring it between machines.

If media is missing, changed, unreadable, or old subframe intervals cannot preserve section/citation relationships after rounding, the archived analysis keeps `legacy_seconds: {start_seconds, end_seconds}` with null frame fields/count. Its video's frame timing is null; no default FPS is invented. Content and historical review remain readable, but affected creative artifacts become outdated and approval is cleared. Confirmation and new creative use return `frame_timing_unavailable`; upload and analyze the source again to continue. This legacy fallback cannot mix with frame intervals in one analysis.

## Legacy v0.1 migration

The existing `examples/analysis_result.original.json`, `examples/analysis_result.json`, and `contracts/analysis.schema.json` are preserved unchanged. Use the explicit conversion API in `backend/app/migration.py`: `migrate_legacy_analysis(data, original=None)` returns an `AnalysisResult`; `migrate_legacy_examples(original, revised)` returns a validated `TaskState` with both analysis revisions. The migration CLI writes a new file:

```bash
.venv/bin/python -m backend.app.migration \
  --original examples/analysis_result.original.json \
  --revised examples/analysis_result.json \
  --output .local-data/legacy-migrated.json
```

The current migrated fixture is `examples/v0.4.legacy-migrated.json`; earlier versioned fixtures remain unchanged. Segment text/observations become canonical events with stable derived IDs, while sections reference them. Missing/unknown values and fictional provenance remain explicit. No real provider/model run is invented. The legacy media record has no storage ID and remains `missing`; `SYNTHETIC_LumaCup_demo_NO_MEDIA.mp4` is a historical fictional name, not a playback asset. Its source has no known FPS, so original intervals remain in `legacy_seconds` with null frame fields, structured details and playback. This CLI produces contract data, not an uploaded playable task. Do not substitute it for the dedicated generated sample workflow.

## HTTP operations

Routes are implemented in `backend/app/api.py`; the local OpenAPI reference is `http://127.0.0.1:8000/docs`. Requests and responses are JSON except multipart upload, video playback, and exports. Every task mutation returns the complete saved `TaskState`; use the returned `task.version` for the next mutation. IDs and revision references in this table come from that saved state, never from unsaved UI fields.

For compactness, `V` below means required `expected_version`; `I` means `V`, `brief_ref`, and `analysis_ref`. Each reference uses `{id, revision}`.

| Method and path | Request / response |
|---|---|
| `GET /api/health` | Version and explicit real-analysis/creative-mode status. |
| `GET /api/config` | Actual configured upload limits, supported media, sample-refinement phrase, and separate analysis/creative narrative language settings. |
| `POST /api/tasks` | `{title}` → new task (`201`). |
| `GET /api/tasks` | Array of saved task aggregates. |
| `GET /api/tasks/{task_id}` | Reopen one saved task aggregate. |
| `POST /api/tasks/{task_id}/brief` | `{V, brief}`; brief contains user input fields only, without server-owned identity/revision/timestamps. |
| `POST /api/tasks/{task_id}/sample` | `{V}`; requires a task with no video, creates matching synthetic media and a sample brief if no brief exists. |
| `POST /api/tasks/{task_id}/video` | Multipart `file`, `expected_version`, optional `source_url`; measures/validates media and sets real mode. |
| `GET /api/tasks/{task_id}/media/{video_id}` | Saved MP4 playback response; video must belong to this task. |
| `POST /api/tasks/{task_id}/recognize` | `{V, video_id?}`; operates on the current video and records analysis/job result. |
| `POST /api/tasks/{task_id}/analysis/correct` | `{V, analysis_ref, event_edits?, segment_edits?}`; event edits identify `event_id` and allowed `text`/`description`/full `visual_details`; section edits identify `segment_id` and `roles`. |
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

`backend/app/media.py::MediaStore` stores files under generated identifiers, never user-supplied paths. Intake accepts `.mp4` with one H.264 or supported SDR HEVC video stream and zero or one AAC audio stream. It probes metadata and presentation-order frames, retaining their timing map, and decodes the content; file extensions alone are insufficient. Missing audio is recorded as `has_audio=false`; recognition records speech `none_found` from this measured no-audio determination and skips ASR without claiming that a speech model ran.

Defaults are 52,428,800 bytes (50 MiB), 180 seconds, and at most 1920×1920 pixels, with 15-second probe, 60-second decode and 180-second derivative-transcode timeouts. Environment settings are listed in `.env.example`; `/api/config` returns active limits. `FFMPEG_BIN` and `FFPROBE_BIN` select the executables. Rejected inputs distinguish missing/unreadable/empty media, size/duration limits, unsupported format/codec/streams/dimensions, absent tooling, and inspection timeout. Do not infer broad camera/device compatibility from the narrow generated MP4 test fixture. Source URLs are stored as provenance only.

HEVC originals retain their stored bytes, SHA-256, `video_codec=hevc` and source timing. An H.264/AAC browser derivative is described by `VideoAsset.playback`: safe `storage_id`, `video_codec=h264`, nullable `audio_codec=aac`, measured `duration_seconds`, and its own `FrameTiming`. The derivative has one frame per source frame in presentation order, with validated timing correspondence; conversion never substitutes an FPS filter for the source clock. The model checks equal source/derivative frame counts and each duration against its own final boundary. The media pipeline performs the correspondence checks, with frame-distinguishable fixtures testing order. `playback=null` selects the original. Browser playback uses the derivative path/clock when present; recognition uses the original. MOV, HDR/Log color fidelity and unusual HEVC profiles are not implied by accepting a supported SDR fixture.

## Recognition and creative adapter entry points

`backend/app/adapters.py` defines `RecognitionAdapter` and `CreativeAdapter` protocols. The service in `backend/app/service.py` owns persistence, currentness, approval, and job transitions; adapters receive saved input snapshots and return normalized objects. Adapters do not edit SQLite or overwrite user content. A provider-specific transport/parser belongs inside an adapter.

### Recognition

The entry point remains `analyze(request: RecognitionRequest) -> AnalysisResult`. `RecognitionRequest` is a frozen dataclass with:

- `task_id`: the saved task's ID;
- `video`: its validated `VideoAsset`, including measured duration, probed frame timing and provenance;
- `job_id`: the current processing context;
- `task_mode`: `real` or `sample`;
- `media_path`: the backend-resolved local file path, never a frontend credential or arbitrary remote download request.

`WorkflowService.recognize` resolves the saved file, chooses the adapter, and validates the returned task/video association and aggregate contract before saving. Successful results use a new `analysis_id`, revision 1, matching task/video/duration/frame_count, canonical frame-based events, ordered sections, explicit coverage, honest origin, and an unconfirmed review. Provider output may need parsing and semantic normalization even if the provider advertises JSON output. Never fabricate a model run, confidence, absent extraction category, or success after an access failure.

`SampleRecognitionAdapter` verifies sample mode, sample provenance/key, expected duration, and the hash of the matching generated file. Otherwise it returns a failed result with `sample_media_mismatch`. `UnconfiguredRecognitionAdapter` returns a failed result with `real_analysis_not_configured`, `retryable=false`, no events, and a message explaining that the upload was saved but not recognized. It performs no paid request and has no silent sample fallback. A provider failure should likewise return a validated failed analysis or raise an exception exposing safe `code`, `message`, and `retryable` fields; raw provider response bodies and secrets do not belong in task records.

`backend/app/providers/recognition.py::ProviderRecognitionAdapter` implements the real path with independently injectable `VisionProvider` and `TranscriptionProvider` protocols from `providers/base.py`. OpenAI implementations use bounded source JPEG samples through Responses structured output and timestamped `whisper-1` transcription through Audio Transcriptions. `media_preparation.py` verifies the original hash, samples by actual source timing, and extracts bounded audio chunks aligned to the signed source origin. Sparse visual samples provide observations of sampled frames, not exhaustive shot-boundary detection; uncertainty remains explicit. Music/SFX remain `not_analyzed` in this implementation. A fake alternate provider in offline tests exercises the same provider-independent boundary; no second live provider is claimed.

Settings are capability-scoped in `providers/config.py`: `VIDEO_VISION_PROVIDER`, `VIDEO_TRANSCRIPTION_PROVIDER`, `VIDEO_CREATIVE_PROVIDER`, `OPENAI_VISION_MODEL`, `OPENAI_TRANSCRIPTION_MODEL`, and `OPENAI_CREATIVE_MODEL`; `OPENAI_API_KEY` stays server-side. Default model selections are `gpt-4.1-mini`, `whisper-1`, and `gpt-4.1-mini`, respectively. The transport checks supported capabilities, enforces finite timeouts and bounded transient retries/concurrency, and does not retry authentication or exhausted credit indefinitely. Provider refusal, incomplete JSON, semantic failure and missing timing are explicit failures, never a sample fallback.

Recognition cache keys include original content hash, source timing, preparation/normalization/prompt/schema versions, provider/model settings and relevant limits/language settings. Internal `provider-cache/runs.jsonl` diagnostics record capability, provider/model, job/output context where available, timing, attempts, cache status and safe failure codes. Usage includes explicit units when reported; unknown usage/cost is null with an explanation. Fixtures and mocked transports validate integration only. Live evaluation requires explicit opt-in, a positive budget, credentials and permitted media; successful offline checks do not establish English/Chinese recognition quality or provider latency.

A valid sample adapter exercise is the `recognize` operation in the HTTP example above, which resolves `backend/app/sample.py::sample_analysis` through the same request boundary. `examples/v0.4.sample-task.json` contains the full saved sample with overlapping visual/audio events; the legacy migrated fixture separately exercises fictional speech without claiming matched speech playback. Run `scripts/load_sample.py --complete` to regenerate a complete local walkthrough with actual matching media, instead of treating serialized storage references as files available on another computer.

### Creative generation

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

`providers/creative.py::OpenAICreativeAdapter` implements all three operations for real tasks. It requests content fields, grounds citations in supplied event IDs, and constructs domain objects with exact saved input references and new unapproved drafts. Requests preserve Unicode brand/evidence wording, separate proposed narrative language from source text, carry production limits/prohibited claims and frame effectiveness statements as hypotheses. Local validation rejects invented citations and invalid storyboard timing; generation is not automatic factual verification. The service revalidates returned artifacts and discards invalid or stale results. Provider failures do not invoke sample creative templates. Credentials are unnecessary for the explicitly labeled sample path.
