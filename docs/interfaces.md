# Interface contracts — projects 1.8 and retained tasks 0.7

The default project application uses `/api/projects` and the canonical
`backend/app/project_workspace/models.py` contract. See
[Project workspace 1.8](project-workspace-1.8.md) for source ownership,
conversation/brief adoption, independent draft concurrency, selections,
evidence corrections, content hierarchy, production manifests, and migration.
Generate/check its schema with `scripts/export_project_contracts.py` and its
TypeScript response types with `frontend/scripts/project-contracts.mjs`.

The contract below remains the supported legacy `/api/tasks` boundary. It does
not describe the default project's intake, navigation, or reference cardinality.

`backend/app/models.py` is the maintained task-record definition. Pydantic performs runtime and semantic validation; `scripts/export_contracts.py` generates `contracts/v0.7.task-state.schema.json`, `v0.7.analysis.schema.json`, `v0.7.m2.schema.json`, `v0.7.editors.schema.json` and `v0.7.structure.schema.json`. Structure endpoint models live in `backend/app/structure_models.py`. Frontend task types are generated from the merged M2/editor bundles into `frontend/src/generated/contracts.ts`; Structure has a separate client boundary. Change models, generated artifacts, validators and consumers together.

New records default to `0.7.0`; the runtime also accepts existing `0.6.0` records without rewriting saved content, IDs or approvals. Mixed retained v0.6 records and new v0.7 revisions are valid. The v0.1–v0.6 schemas/examples are immutable historical snapshots. Existing v0.2–v0.5 migration paths continue their archived, lossless v0.6 extension; accepting those records does not require a second migration. The TypeScript generator removes unsupported JSON Schema conditionals only from its structural input; canonical schemas and runtime validators retain them.

## Independent workspace v0.7

The UI has Research (Timeline / Structure), Ideas, Production, and independent project inputs. Source inspection does not require a brand brief. Original idea generation explicitly uses `use_reference=false` and `analysis_ref=null`; reference-driven generation still requires an exact, current, reviewed successful analysis. Applied brand inputs and an explicit generation-language choice remain prerequisites for creative provider calls. Production always requires the exact approved direction revision.

`CreativeDirection`, `CreativeFeedback` and production outputs now permit `analysis_ref=null`. Such artifacts must have no reference-evidence citations. Their planned shots remain independent seconds. Adding, correcting or deleting an unrelated reference does not invalidate original ideas/outputs; changes to their applied brief, language or approved direction still do. A research handoff is selected inspiration with attributed sources and applicability conditions, never approval, a new brand fact or automatically reviewed evidence. `CreativeDirection.structure_handoff_id` pins the exact immutable selected snapshot; refinement and production reuse that snapshot rather than silently replacing it with the newest selection. Unknown or wrong-task snapshots fail before provider use.

`POST /api/tasks/{task_id}/directions/manual` accepts `{expected_version, brief_ref, fields}` where `fields` contains exactly `core_message`, `hook`, `narrative` and `cta`. It creates a user-authored, unapproved direction with no reference dependency. The `idea` editor scope independently stores these four fields before a direction exists; its base reference is the applied brief when present.

### Background operations

`POST /api/tasks/{task_id}/operations` accepts `{operation, payload}` for `recognize`, `directions`, `refine` or `production` and returns `202` with a durable operation ticket. Payloads are the corresponding normal endpoint bodies; `refine` additionally includes `direction_id`. `GET /operations` lists task activity and `GET /operations/{operation_id}` polls a ticket. Status is `queued`, `running`, `succeeded` or `failed`; terminal tickets include the latest task aggregate as `result` and a safe error when applicable. Polling never starts a new provider request. Duplicate active operations of the same kind/task are rejected. On restart, interrupted tickets fail rather than replay paid work. Existing synchronous routes remain available for compatibility and tests. Run one backend process per local library.

### Structure agent and persistence

All paths below are under `/api/tasks/{task_id}/structure`:

| Method / path | Request and result |
|---|---|
| `GET /` | Latest `Workspace`, or null before analysis. |
| `POST /analyze` | `{analysis_ref?}` → `202 Workspace`; usable current video observations required, no brief/review gate. |
| `POST /feedback` | `{expected_version, node_id, instruction, kind}`; kind is `question`, `context` or `reconsider`; asynchronous answer/proposal using completed evidence, without extending web research. |
| `POST /proposals/{proposal_id}/adopt` | `{expected_version}`; adopts the previewed graph update only if its base graph revision is still current. |
| `POST /handoff` | `{expected_version, node_ids?, method_ids?, all?}` → saved exact selected `Handoff`; selected methods bring their required supporting nodes. |
| `GET /handoff` | Last selected handoff, or null. It is a historical snapshot; consumers verify its analysis/video currentness before new creative use. |

`Workspace` tracks its own optimistic `version`, `graph_revision`, exact task/video/analysis identity, graph, sources, supplied contexts, answers and proposals. Primary status is `analyzing`, `researching`, `ready`, `partial` or `failed`; `feedback_status` separately reports optional follow-up processing. Source changes are exposed as `outdated` or `source_deleted`. SQLite tables `structure_runs`, `structure_history` and `structure_handoffs` preserve these records independently of task aggregate versions.

A graph contains concise `nodes`, explanatory `edges`, transferable `methods` with conditions, and at most three relevant `research_gaps`. Node kinds are `observation`, `source_claim`, `inference` and `user_context`. Each node cites exact existing event IDs, returned external source IDs or saved context IDs. The server attaches measured `moments`; the provider cannot invent timestamps. One-frame visual samples remain points, speech intervals remain estimates, and external background has no video timestamp. Graphs cannot contain dangling references or duplicate identifiers. Semantic validation checks structural grounding, not whether every interpretation is correct.

The agent publishes the video-based graph first, then performs one bounded hosted-search phase and a structured synthesis. Returned source URLs must occur in actual transport citations/sources. Relevant user context or adopted changes prevent automatic conflicting replacement: updates become previewable proposals. Questions/context do not initiate deeper retrieval. At a budget/time/source failure, completed work remains partial and the run ends. There is no manual graph-edit or Continue research endpoint. Startup closes interrupted Structure work without a provider retry. Only the explicitly loaded matching fictional sample uses the deterministic Structure fixture; arbitrary uploads never fall back to it.

### Content-area treatment

`GET/POST /api/tasks/{task_id}/videos/{video_id}/content-region` loads/saves normalized crop and exclusion rectangles, and `POST .../suggest` proposes conservative edge-bar removal for user review. This is non-destructive provider preparation; originals remain intact. Region revisions participate in cache keys and in-flight source-change checks. Static brand marks, prices and subtitles are not automatically classified as noise. OCR grouping retains sampled timing and does not infer uninterrupted text duration. This is a crop/mask plus conservative suggestion implementation, not a trained phone/platform-UI classifier.

## Workspace v0.6 additions

`CreativeTask.generation_language` is `English`, `Chinese` or null (no implicit choice). `VideoAsset.deleted_at` is a nullable tombstone; identity/timing/provenance remain after media deletion. `CreativeDirection.auxiliary_status` is `current` or `needs_review`. `ProductionOutput.bundle_id` links newly generated/edited brief/storyboard pairs; legacy records remain null and must not be paired by revision number alone.

| Method and task-relative path | Contract |
|---|---|
| `GET /editors/{scope}` | `EditorDraft` with independent `draft_version`, exact `base_refs`, editable `content`, computed pending/conflict flags. |
| `POST /editors/{scope}` | `{expected_draft_version, base_refs, content}` → independently saved draft; no task version increment. |
| `POST /editors/{scope}/discard` | `{expected_draft_version}` → explicitly restored current content. |
| `POST /language` | `{expected_version, generation_language}` → task; changed language invalidates creative descendants, preserves reference review. |
| `POST /videos/{video_id}/delete` | `{expected_version}` → task; delete media and retain historical records with a tombstone. |

Scopes: `idea` stores an original idea draft; `analysis` content contains complete `events` and `segments`; `direction-{direction_id}` contains core message/Hook/narrative/CTA; `production` contains `brief_fields` and full `rows`. Server-side allowlists preserve identity, relationship, timing and coverage fields. Formal correction/edit endpoints accept `expected_editor_version` to atomically validate and checkpoint the exact draft submitted. No-op saves preserve formal revisions. Draft conflicts never silently overwrite saved content. Missing or malformed scopes return structured errors.

Analysis drafts block dependent creative admission and review confirmation until applied or discarded; production drafts block regeneration. Direction drafts block their refinement/approval/production path. Manual direction text revisions clear approval and mark auxiliary explanations for review. Pending edits alone do not invalidate existing saved artifacts. Historical export remains explicit and labels its exact source/version context. Original shots may have empty citation lists; claims still come from applied inputs.

`workspace_migration.py::migrate_v05_task` validates the archived v0.5 schema, adds the new metadata without inventing language/media/output pairing, and archives exact original JSON and hash transactionally with replacement. Existing v0.2–v0.5 import paths emit the retained compatible v0.6 representation. Historical schema and example snapshots remain unchanged. The v0.5 migration descriptions below remain historical context; newly created records default to v0.7.

## M2 editor and applied input contract

M2 is the user-provided **Brand & task** input. M7 remains the generated production creative brief. See [the v0.5 decision](decisions/m2-v0.5.md) for ownership and transaction rationale.

- `M2Fields`: nullable `brand_company`, `product`, `target_audience`, `platform`, `communication_goal`, `target_duration_seconds`, `available_footage`, `presenters`, `locations`, `tone`, `production_limits`; `approved_messages` and `prohibited_claims` lists. No hidden task defaults. Optional unknowns remain unset, distinct from explicit “none available.”
- `M2Claim`: `claim_id`, exact `statement`, optional `supporting_notes`, `source_urls`, `qualification`, and `confirmed_for_use`. Changed statement/qualification clears confirmation. At least one confirmed non-placeholder claim and all six required fields are necessary to Apply.
- `M2Draft`: `task_id`, independent `draft_version`, `based_on_brief`, `fields`, `claims`, `source_notes`, `reviewed_input_checkpoint`, `has_pending_inputs`, `legacy_review_required`, `missing_fields`, `updated_at`. Computed readiness is server-owned. The checkpoint covers structured values and excluded claims, not source notes or unaccepted proposals.
- `BrandTaskBrief.claim_details`: ordered `ClaimDetail` records with the same content as a draft claim and `confirmation_origin` instead of its editable boolean. Current applications use `user_confirmed`; legacy records use `legacy_unrecorded`. `selling_points` exactly matches the ordered statements. Only included, confirmed claims enter new provider snapshots. Qualifications, support, URLs and prohibitions reach M6/M7; user confirmation never certifies factual truth.
- `M2AssistanceRequest`: `draft_version`, `request_id`, `mode` (`extract` or `suggest_task_field`), and optional `requested_field` (audience/goal only). Source text/current context come from that saved draft.
- `M2AssistanceResponse`: `request_id`, `source_draft_version`, `provider_mode` (`real`/`fake`), bounded `candidates` and `unresolved_notes`. A candidate has `candidate_id`, allowlisted `target`, typed `value`, `origin` (`extracted`/`suggested`) and exact `source_excerpt` for extracted facts. Claims have no confirmation or server identity fields. UI selection/editing is local until one batch adoption.

| Method and task-relative path | Request → response |
|---|---|
| `GET /m2/draft` | Latest `M2Draft`; seeds from the applied brief if needed. |
| `POST /m2/draft` | `{expected_draft_version, fields, claims, source_notes}` → `M2Draft`; task version unchanged. |
| `POST /m2/apply` | `{expected_draft_version, expected_version, based_on_brief}` → `{changed, draft, task}`. |
| `POST /m2/discard` | `{expected_draft_version}` → restored applied draft, or empty input only; task/reference/history retained. |
| `POST /m2/assist` | `M2AssistanceRequest` → proposals; no persistence/task mutation; verifies source draft before and after provider response. |
| `POST /m2/adopt` | `{source_draft_version, request_id, candidates}` → one atomic `M2Draft` update; new claims remain unconfirmed. |

All paths are below `/api/tasks/{task_id}`. Saved draft optimistic conflicts return `m2_draft_conflict`; stale extraction/adoption returns `m2_stale_proposal`. Required-field, claim, pending-edit and legacy gates use `m2_incomplete`, `m2_unconfirmed_claims`, `m2_pending_changes`, `m2_legacy_review_required` in the existing error envelope. Local text remains visible on failed saves, with retry and explicit reload/discard choices.

Apply checks versions and complete input in a single SQLite transaction, compares every provider-relevant value (including optional details and claim IDs/conditions), and creates one new formal revision only for meaningful changes. Identical Apply preserves task version, approval and output eligibility. Exact retries are idempotent; failures roll back task and checkpoint. Changed Apply retains history and marks dependents outdated. Draft autosaves never pass through task update or overwrite the full task response in the UI.

Creative request `brief_ref` and `analysis_ref` may be null at HTTP admission so incomplete input gets an actionable error. A current applied brief is required. An exact reviewed analysis is required only for reference-driven generation; explicit original mode requires `analysis_ref=null` and rejects invented evidence.

Pending structured edits block new direction generation, refinement, approval and production admission transactionally. Reference operations remain available. Already admitted creative work may complete against its original applied input while a draft is edited; changed formal Apply still triggers the existing stale-response guard. Source notes and unaccepted proposals alone do not block generation.

### Saved v0.4 migration

`m2_migration.py::migrate_v04_task` validates the archived v0.4 schema, retains exact applied wording/revision pointers/content/history/reviews/approvals/currentness, adds deterministic claim metadata with `legacy_unrecorded`, and advances only the task concurrency version. SQLite archives the original JSON/hash and replacement in one transaction. A seeded partial draft requires explicit new claim review before creative actions; migration does not invalidate or regenerate saved outputs. Earlier imports now emit v0.6 with honest legacy metadata while preserving their existing timing rules. Historical v0.4 schema and fixture bytes remain intact.

### M2 assistance providers

`providers/m2.py::M2AssistanceAdapter.assist(request, draft)` is independent of M6. `OpenAIM2AssistanceAdapter` uses the existing bounded transport with `VIDEO_M2_PROVIDER` / `OPENAI_M2_MODEL`; `disabled` leaves the complete manual workflow available. Typed validation rejects unsupported fields, fabricated/untraceable excerpts, invalid values and permission fields. Exact qualified assertions are retained. HTTP(S) source links are stored only. `FakeM2AssistanceAdapter` is explicit test injection, never selected by real-provider failure. No `ProcessingJob.operation` enum or global brand/profile service is added. Live quality requires separate authorized evaluation; passing offline fixtures does not establish it.

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

A task's optimistic `version` increases on formal task mutations. Independent M2 draft writes and no-op Apply do not change it. Send the latest version with a mutation; `version_conflict` means reload the task and reconsider the pending edit. Artifact `revision` numbers identify content versions and have a different purpose.

- The original extraction stays at analysis revision 1. Content/role corrections append a revision with the same analysis/event/section IDs, preserve timing/provenance, record before/after changes, and clear review confirmation. Allowed corrections are OCR/speech text, visual description, section roles and restricted visual labels. Identity, timing, lanes/kinds, evidence links, and provenance are not correction fields. Affected interpretation is cleared.
- **Use this reviewed analysis** confirms the exact current revision separately. Confirmation metadata does not create an artificial content revision. Rerunning recognition creates a new analysis ID and preserves prior results.
- Direction generation/refinement require the current brief. Reference-driven artifacts additionally require successful, confirmed analysis for the current video. Original artifacts carry `analysis_ref=null` and no reference citations; they do not acquire a reference gate merely because a video was uploaded.
- Direct editing or supported prompt refinement produces an unapproved direction draft. Feedback records the instruction and exact target revision before processing, then its result or explicit `not_interpreted` outcome. Selection and generation never imply approval.
- `CreativeTask.chosen_direction` persists an exact unapproved draft choice across refresh/restart. `selected_direction` identifies the explicitly approved choice used for production. Choosing a different draft clears the previous approval and marks its outputs outdated; selecting a draft never grants approval.
- Production generation requires the exact selected, current, explicitly approved direction revision and matching upstream inputs. Brief and language changes invalidate dependent approval/currentness; video/analysis changes invalidate only artifacts that actually depend on that reference. Direction edits/refinement invalidate outputs for that direction. Older content remains available, marked `outdated`.
- Output edits append revisions; explicit whole-output regeneration preserves previous manual work. No partial row generation is implemented. Atomic storage/version checks prevent a delayed result or stale browser tab from overwriting newer work.

The handoff's baseline field catalog interchanges the descriptions of `chosen_direction` and `selected_direction`. The live implementation and approval rules above are authoritative: `chosen_direction` is draft selection; `selected_direction` is the explicitly approved production choice. Migration preserves these pointers without swapping them.

Structured corrections submit a full `visual_details` object in the event edit. The server captures full before/after values and validates them atomically. Editable leaves are subject `kind`, `roles`, `label`, `description`; action `action_type`, `description`; and presentation `presentation_type`, `description`. Existing item positions, subject IDs, relationship arrays, group status/errors and array sizes remain fixed. Null details cannot be created or removed through correction. Removing a product role while a presentation references that subject is rejected; the server does not silently remove relationships. Replay must reproduce every editable field from the original extraction and preserve prior available correction history. Accepted edits clear current review and invalidate dependent approval/currentness while preserving historical outputs.

## Saved v0.3 task migration

`backend/app/contract_migration.py::migrate_v03_task(payload)` validates the historical schema and adds `visual_details=null` to every event and `playback=null` to every video. It emits v0.6.0 with legacy-unrecorded claim metadata and increments only the optimistic task version; it preserves artifact IDs/revisions, timestamps, corrections, exact citations, reviews and approvals. It neither reruns extraction nor creates a playback derivative. `TaskStore` runs this migration at startup or load, archiving the exact original JSON and SHA-256 in `task_migration_archive` within the same transaction. Failure rolls back both archive and replacement; reopening is idempotent. The archive remains readable through SQLite's `original_payload` column. Back up the full data directory and media before transferring it.

## Saved v0.2 task migration

`backend/app/frame_migration.py::migrate_v02_task(payload, media_root)` converts all reference intervals and analysis revisions using one actual frame map per video and emits v0.6.0 directly with null structured details/playback and legacy-unrecorded claim metadata. `TaskStore` runs migration at startup and on loading a legacy row. It validates the preserved v0.2 schema, checks saved media identity when a SHA-256 is present, retains IDs, correction logs, exact references and output seconds, and increments the task version once. For available matching media, review/approval and current creative content remain valid. The SQLite `task_migration_archive` table stores the exact original JSON string and its SHA-256 in the same transaction as replacement; a failed migration leaves the old record unchanged. Reopening is idempotent. Back up the complete data directory, including media, before transferring it between machines.

If media is missing, changed, unreadable, or old subframe intervals cannot preserve section/citation relationships after rounding, the archived analysis keeps `legacy_seconds: {start_seconds, end_seconds}` with null frame fields/count. Its video's frame timing is null; no default FPS is invented. Content and historical review remain readable, but affected creative artifacts become outdated and approval is cleared. Confirmation and new creative use return `frame_timing_unavailable`; upload and analyze the source again to continue. This legacy fallback cannot mix with frame intervals in one analysis.

## Legacy v0.1 migration

The existing `examples/analysis_result.original.json`, `examples/analysis_result.json`, and `contracts/analysis.schema.json` are preserved unchanged. Use the explicit conversion API in `backend/app/migration.py`: `migrate_legacy_analysis(data, original=None)` returns an `AnalysisResult`; `migrate_legacy_examples(original, revised)` returns a validated `TaskState` with both analysis revisions. The migration CLI writes a new file:

```bash
.venv/bin/python -m backend.app.migration \
  --original examples/analysis_result.original.json \
  --revised examples/analysis_result.json \
  --output .local-data/legacy-migrated.json
```

The retained migration fixture is `examples/v0.6.legacy-migrated.json`; earlier versioned fixtures remain unchanged. Segment text/observations become canonical events with stable derived IDs, while sections reference them. Missing/unknown values and fictional provenance remain explicit. No real provider/model run is invented. The legacy media record has no storage ID and remains `missing`; `SYNTHETIC_LumaCup_demo_NO_MEDIA.mp4` is a historical fictional name, not a playback asset. Its source has no known FPS, so original intervals remain in `legacy_seconds` with null frame fields, structured details and playback. This CLI produces contract data, not an uploaded playable task. Do not substitute it for the dedicated generated sample workflow.

## HTTP operations

Routes are implemented in `backend/app/api.py`; the local OpenAPI reference is `http://127.0.0.1:8000/docs`. Requests and responses are JSON except multipart upload, video playback, and exports. Formal task mutations return the complete saved `TaskState`; use the returned `task.version` for the next mutation. M2 draft endpoints return only the separately versioned editor state. Apply returns `{changed, draft, task}`. IDs and revision references in this table come from that saved state, never from unsaved UI fields.

For compactness, `V` below means required `expected_version`; `I` means `V`, `brief_ref`, and `analysis_ref`. Each reference uses `{id, revision}`.

| Method and path | Request / response |
|---|---|
| `GET /api/health` | Version and explicit real-analysis/creative-mode status. |
| `GET /api/config` | Actual configured upload limits, supported media, sample-refinement phrase, and separate analysis/creative narrative language settings. |
| `POST /api/tasks` | `{title}` → new task (`201`). |
| `GET /api/tasks` | Array of saved task aggregates. |
| `GET /api/tasks/{task_id}` | Reopen one saved task aggregate. |
| `POST /api/tasks/{task_id}/brief` | Compatibility Apply: `{V, brief}` with explicit `user_confirmed` claim metadata; rejects pending drafts; identical content preserves task version/approval. No server-owned identity/revision/timestamps. |
| `POST /api/tasks/{task_id}/sample` | `{V}`; requires a task with no video, creates matching synthetic media and a sample brief if no brief exists. |
| `POST /api/tasks/{task_id}/video` | Multipart `file`, `expected_version`, optional `source_url`; measures/validates media and sets real mode. |
| `GET /api/tasks/{task_id}/media/{video_id}` | Saved MP4 playback response; video must belong to this task. |
| `POST /api/tasks/{task_id}/recognize` | `{V, video_id?}`; operates on the current video and records analysis/job result. |
| `POST /api/tasks/{task_id}/analysis/correct` | `{V, analysis_ref, event_edits?, segment_edits?}`; event edits identify `event_id` and allowed `text`/`description`/full `visual_details`; section edits identify `segment_id` and `roles`. |
| `POST /api/tasks/{task_id}/analysis/confirm` | `{V, analysis_ref}`; explicit review of the current successful revision. |
| `POST /api/tasks/{task_id}/directions/generate` | `{I, use_reference?}`; two drafts with exact inputs. `use_reference` defaults true; false requires `analysis_ref=null`. |
| `POST /api/tasks/{task_id}/directions/manual` | `{V, brief_ref, fields}`; create an original user-authored draft, without approval. |
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

The original compatibility routes execute synchronously; the workspace uses the background ticket API above. Neither polling nor restart automatically repeats a provider request. Retry by reopening the task and submitting a new explicit operation with current versions. A job completing after another write records `stale_result`, discards the delayed output, and preserves the newer saved work. The current job record and completed/failed jobs remain inspectable in task history. On backend startup, interrupted pending/running jobs become failed with `interrupted_job` and `retryable=true`; the task version increases. Reopen the task and retry explicitly. Run one backend worker so another worker cannot misclassify a live operation as interrupted. Do not retry permanent configuration/media errors without fixing their cause.

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

A valid sample adapter exercise is the `recognize` operation in the HTTP example above, which resolves `backend/app/sample.py::sample_analysis` through the same request boundary. `examples/v0.6.sample-task.json` contains the full saved sample with overlapping visual/audio events; the legacy migrated fixture separately exercises fictional speech without claiming matched speech playback. Run `scripts/load_sample.py --complete` to regenerate a complete local walkthrough with actual matching media, instead of treating serialized storage references as files available on another computer.

### Creative generation

`CreativeAdapter` defines three operations:

```python
generate_directions(brief: BrandTaskBrief,
                    analysis: AnalysisResult | None) -> list[CreativeDirection]

refine_direction(brief: BrandTaskBrief,
                 analysis: AnalysisResult | None,
                 target: CreativeDirection,
                 feedback: CreativeFeedback) -> CreativeDirection | None

generate_production(brief: BrandTaskBrief,
                    analysis: AnalysisResult | None,
                    direction: CreativeDirection) -> tuple[ProductionCreativeBrief, TextStoryboard]
```

Direction generation returns exactly two distinct drafts. Reference-driven drafts cite exact input revisions and existing event IDs. Original drafts have `analysis_ref=null` and empty evidence arrays; their two alternatives are independent creative approaches, not claims of following a nonexistent reference. Refinement receives the entire persisted `CreativeFeedback`, including the original instruction and exact target/input references. A supported refinement returns the next revision of that same direction, with `approval_status=draft`, no approval timestamp, and its feedback reference. `None` means no interpreted refinement; the service retains the instruction with `status=not_interpreted`, an explanation, and no invented resulting draft.

The deterministic sample accepts the case-insensitive literals **Make this direction presenter-free.**, **Make it presenter-free**, or **presenter-free** (with optional final period/exclamation mark). It visibly changes Hook, narrative, production requirements, and production notes; approved production output uses product-only imagery/text with no spoken dialogue. All other instructions are saved as user production notes in the feedback history and explicitly reported as uninterpreted; they do not silently modify a direction or establish unrestricted language understanding.

Production generation returns both outputs using the selected approved direction and its exact input/feedback references. The sample uses brand/product, approved messages, audience/platform/goal, optional constraints, direction text, and target duration to make a four-row plan. It preserves prohibited claims as production constraints and does not invent performance evidence. It is a template demonstration, not a claim that automatic generation can enforce every free-text production requirement or fact-check arbitrary user edits.

`providers/creative.py::OpenAICreativeAdapter` implements all three operations for real tasks. It requests content fields, grounds citations in supplied event IDs, and constructs domain objects with exact saved input references and new unapproved drafts. Requests preserve Unicode brand/evidence wording, separate proposed narrative language from source text, carry production limits/prohibited claims and frame effectiveness statements as hypotheses. Local validation rejects invented citations and invalid storyboard timing; generation is not automatic factual verification. The service revalidates returned artifacts and discards invalid or stale results. Provider failures do not invoke sample creative templates. Credentials are unnecessary for the explicitly labeled sample path.
