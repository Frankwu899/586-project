# Video Anatomy 1.8 project workspace

For the 1.8.1 candidate's changes to analysis graphs/current-result presentation,
legacy Structure recovery, exploratory generation and speech retries, see
[release notes](releases/1.8.1.md) and [verification handoff](handoff/project-workspace-1.8.1.md).
The stricter exploratory-generation gates described below are the original 1.8.0
behavior; final-production confirmation remains required in 1.8.1.

This document describes the implemented 1.8 workspace and its engineering
boundaries. The owner's current product baseline supersedes historical
single-reference, required-form, and Discovery-exclusion specifications. The
older task workspace remains available for continuity; its schemas and history
are not replaced by rewriting old documents.

The application remains a single-user local React/Vite/TypeScript frontend with
a FastAPI/Python backend, SQLite persistence, and FFmpeg/ffprobe. The local
launcher and user-provided API-key connection remain in place. There is no new
hosted storage, shared-key service, rendering backend, or public deployment.

## Application and navigation

The default application is `frontend/src/ProjectApp.tsx`. Its dashboard provides
project cards, search, name/updated-time sorting, create/open/rename, independent
duplication, and recoverable Trash/restore. Cards show resource/content counts,
updated time, a resource thumbnail when available, and a summary status.

Each project has these destinations. The persisted `workspace` value is the
stable navigation identifier, not a separate web-server route.

| Navigation label | Stored identifier | Implemented surface |
| --- | --- | --- |
| Overview | `overview` | Saved conversation, attachments, working facts, unresolved items, and confirmed-brief review. |
| Resources | `resources` | Project resources, local previews, document extraction, transcript/evidence correction, and reference selection. |
| Discover | `discover` | Empty reserved section with the status below. |
| Analysis | `analysis` | Conclusion-first individual/comparative results with source references and limitations. |
| Content plan | `content` | Optional series, standalone content items, manual/generated directions, history, and exact direction approval. |
| Production | `production` | Four editable documents, saved pack history, manual blank packs, generation, and exports. |

Discovery status is **Reserved — awaiting Frank’s specification.** There are no
Discovery search forms, sample results, connectors, ranking rules, download
services, or algorithm/model choices. The integration boundary is a service call
that imports completed local bytes with `origin="discovery"` and provenance
through the ordinary resource importer. No Discovery HTTP workflow is exposed.

The existing app is still reachable with `?legacy=1`, and its `/api/tasks`
endpoints remain installed. The older Structure graph, graph feedback, and
content-area interface are available there. The new Analysis page is a concise
comparison surface; it does not claim that the legacy graph UI has been
integrated into the new navigation.

The new UI uses a light blue/lavender Glassmorphism treatment with frosted chrome,
readable working surfaces, internal scrolling, and responsive layouts. The
supplied concept images guide its composition; their fictional project content
and illustrated storyboard pictures are not bundled functionality.

## Shared contracts and ownership

`backend/app/project_workspace/models.py` defines the authoritative 1.8 project
record. `scripts/export_project_contracts.py` generates
`contracts/v1.8.project.schema.json`, and
`frontend/scripts/project-contracts.mjs` generates
`frontend/src/project/contracts.ts`. Do not hand-edit generated artifacts.
Historical task schemas continue to use their existing generation/check path.

| Record | Responsibility |
| --- | --- |
| `Project` | Project identity/version, lifecycle, navigation, conversation, resources, content plan, packs, jobs, and editing drafts. |
| `Message`, `Fact`, `BriefRevision` | Saved conversation and source-linked proposals; adopted immutable brief revisions are separate from working facts. |
| `Resource`, `ExtractedBlock` | Project-owned original, hash, provenance/origin, extraction status, source locators, and corrected extraction history. |
| `EvidenceRevision`, `EvidenceEvent` | Original/corrected recognition, review state, typed speech/OCR/visual/sound events, timing, and coverage limitations. |
| `Selection` | Project or individual content-item reference IDs and selection revision. |
| `Analysis` | Concise synthesis and exact input/source references, including visible failed-source limitations. |
| `Series`, `ContentItem`, `Direction` | Optional grouping, topics, creative directions and exact approved revision. Generated series/topics retain input provenance. |
| `InputManifest` | Confirmed brief, selection, corrected evidence, direction, model, instruction digest, context digest, and declared claim IDs. |
| `ProductionPack`, `ProductionShot` | Versioned brief/script/storyboard/shot list and generated structured shot timing, dialogue, screen text and sound. |
| `Job` | Durable queued/running/succeeded/partial/failed operation state; not a render queue. |

Project mutations use optimistic `expected_version` checks. Background operations
capture the inputs they actually use and compare those inputs before committing;
an unrelated conversation draft does not discard valid generation. Source and
artifact identities are project-scoped. Duplicate projects may retain internal
artifact IDs within a new project identity, without sharing mutable storage.

Brief drafts have an independent `brief_draft_version`; each editor scope has an
independent `editor_draft_versions` counter. Autosaves retain their original
scope version across unrelated job/navigation updates. A competing tab cannot
silently overwrite a newer draft. Formal saves check both the source revision
and editor version, then acknowledge the exact submitted checkpoint. Local
recovery drafts remain visible on failure; navigation flushes pending drafts.

Meaningful applied brief, selection, evidence, or assigned series changes mark dependent work for
review. Draft-only editing does not invalidate approved work. No-op formal saves
preserve content revisions. Exact direction revision approval is required for
production; editing the direction creates a new unapproved revision and retains
the old one. Pending edits block only the matching direction/production action.
Pending corrections to selected evidence block new reference-based creative
actions until applied or discarded, including when they arrive during a request.

## Local project storage and migration

The existing application-data root remains the default, with
`VIDEO_ANATOMY_DATA_DIR` as an override. On macOS the launcher uses
`~/Library/Application Support/Video Anatomy/`. User credentials and the shared
usage/budget ledger remain application-level data, outside project duplication.

```text
Video Anatomy/
  library.sqlite3                     # Rebuildable project catalog
  tasks.sqlite3                       # Retained legacy library, when present
  projects/<project-id>/
    project.json                      # Identity/storage-format summary
    project.sqlite3                   # Authoritative Project record
    sources/
      documents/<resource-id>/<name>
      media/<resource-id>/<name>
      assets/<resource-id>/<name>
    evidence/
      provider-results/               # Retained provider extraction results
      speech-chunks/                  # Reusable standalone-audio transcripts
    outputs/<content-id>/<pack-id>/    # Version-pinned exported documents
    cache/
      thumbnails/
      playback/
      prepared/
      audio/
      previews/
    staging/                          # Unpublished partial imports
    legacy/                           # Present on migrated older projects
      task-state.json
      related-records.json
      records.sqlite3
```

Uploaded originals are streamed into project-owned files, hashed, and committed
before extraction begins. A URL is provenance only. Both upload and future
Discovery imports use this same boundary. Relative paths, file membership,
symlink checks, and local-only media protocols protect project ownership.

The database is authoritative for saved conversation, briefs, extracted text,
corrections, analysis, documents and history. Export files are saved snapshots,
not a second editable source of truth. Missing originals are visible; verified
relinking requires the same original bytes. Moving the file from which the user
uploaded does not affect the retained project copy.

Clear cache deletes disposable derivatives only. It retains originals,
transcripts/extraction results, corrections, approvals, output history and
exports. Removed previews/prepared media can be rebuilt. Retained paid extraction
results are under `evidence`, not the clearable cache. Source hashes and relevant
processor/model/settings versions participate in reuse decisions.

Duplication verifies originals, stages physical copies, and publishes a new
project atomically. It copies saved content and retained evidence, excludes
active jobs and disposable caches, records `duplicated_from`, and preserves the
source project snapshot for approval provenance. Active copied directions and
packs require review/new approval. Missing or changed originals prevent a
misleading complete copy. Trash is reversible and does not delete original
files; there is no automatic purge.

At startup, each legacy task is imported once into a deterministic project ID,
with one standalone content item and its previous active reference selection.
The importer copies available original/proxy media and maps saved briefs,
evidence, directions and production content. It does not invent conversations,
series, missing timing, scripts or shot lists. Legacy brief/storyboard pairs are
matched only through their recorded bundle identity, not guessed revision
numbers. Missing legacy originals remain visibly missing.

All task-owned auxiliary records—including M2/editor drafts, lifecycle,
Structure runs/history/handoffs, operations and migration archives—are retained
in the legacy archive. Useful content is projected into the 1.8 record; an
archived legacy table is not a claim that its complete UI has been ported. The
original legacy SQLite database and files remain intact. Imports are idempotent,
and a failed project import does not replace the source. Legacy edits made after
an import are not continuously synchronized into the independent 1.8 project.
Unreadable individual project databases are preserved and reported through
library warnings while healthy projects remain available. Source and proxy
playback clocks remain separate through migration and cache recovery.

## Conversation, facts and claims

New projects open with “What do you want to create today?” Conversation and
attachments persist independently of confirmed project context. Assistance uses
prior messages, extracted document passages, confirmed facts and unresolved
questions to propose information and ask focused follow-ups. It does not cycle
through the former universal required-field form.

The assistant can request one bounded public-context research step through the
existing provider transport. Returned sources are attributed; source lookup
failure preserves the useful reply and exposes its limitation. Retrieved product
claims are proposals, not automatically adopted facts. This contextual research
is separate from the reserved Discovery section.

Extraction proposals require valid source indexes and exact excerpts. Qualified
claims preserve their complete source wording. Suggested context is labeled as
a suggestion. Documents, videos, research results and quoted messages are data,
not instructions that can override application rules. Sources can refer to a
message, document extraction revision/location, or video evidence revision/time.

The brief window is a review surface. Chat corrections update proposals; direct
editing is a shortcut. Explicit Apply confirms the intended working facts into
a new brief revision only when content meaningfully changes. Pending drafts may
remain incomplete. Confirming permission to use a product claim does not mean
the application independently verified that claim.

Provider failures retain the user's message and saved work. With no API key,
conversation can still be saved and manual context/direction/document editing
remains available; the app does not return fake model responses.

## File support and processing limits

These are implemented extraction paths, not universal compatibility guarantees.
Successful storage does not mean extraction or recognition succeeded.

| Format | Handling and limits |
| --- | --- |
| DOCX | Bounded OOXML paragraph/table text with source locators. Embedded diagrams, image-only wording and layout are not fully interpreted. |
| PPTX | Slide text and related notes, up to 100 slides. Charts, animations, layout and text inside images require separate review. |
| XLSX | Sheet/cell locators, shared/inline text and stored values. Formulas are displayed with cached values, never calculated. Hidden/merged cells and complex formatting carry warnings. |
| CSV/TSV | Encoding/delimiter handling and row/column locations; bounded row extraction. |
| TXT/Markdown | Bounded text extraction with line locations. |
| PDF | `pypdf` text extraction by page, up to 100 pages. Encrypted PDFs require an unprotected working copy. |
| Scanned PDFs/images | Optional local Tesseract OCR; scanned PDF pages also need Poppler's `pdftoppm`. At most 10 image-only PDF pages are OCR-processed per import. Failures and missing tools are visible. |
| MP4/MOV/M4V/WebM/MKV | FFmpeg-decodable, bounded SDR video. H.264/AAC MP4 can play directly; other supported sources receive an H.264/AAC proxy with measured frame correspondence. Container extension alone is not acceptance. |
| MP3/WAV/M4A/AAC/FLAC/OGG | Local audio validation and transcription path. Native browser playback still depends on browser codec support. |
| PNG/JPEG/WebP/TIFF/BMP | Local preview and optional OCR. OCR is not a general visual interpretation engine for documents/images. |
| DOC/XLS/PPT, RTF, other unsupported files | Original retained with explicit conversion/unsupported guidance. No macro execution or automatic legacy-format conversion. |

The resource path currently uses the existing configurable default limit of
50 MiB per original, 180 seconds for audio/video, and 1920 × 1920 video dimensions.
Video needs one video stream and at most one audio stream. HDR/10-bit video needs
a reviewed SDR export. Document processing also bounds expanded archive/XML
sizes, extracted characters and blocks; truncation is reported. Text extraction
errors can be corrected while preserving extraction history.

Set `VIDEO_OCR_LANGUAGES` to installed Tesseract language packs as needed; the
default is `eng`. Installing a language pack does not establish OCR accuracy.
Tesseract and Poppler are optional local tools, not bundled proof of availability
on the owner's computer.

## Evidence and multiple-reference analysis

Each content item can have its own reference selection; project exploration has
a separate selection. Only video/audio resources enter reference analysis.
“Analyze selected” starts persisted operation status and per-resource extraction
jobs. Successful evidence is reusable, failed items remain visible, and explicit
retries do not erase completed results or accepted corrections. A comparison
retains the requested selection, including failed-source limitations; it never
silently presents a reduced set as the whole selection.

Per-resource recognition retry preserves current project/content selections and
does not launch comparison synthesis. It reuses completed chunks and reports
failed/partial stages. Rebuilding a media preview is a separate local operation.
Corrected evidence is retained rather than overwritten by a recognition retry.

Visual extraction combines temporal coverage with bounded scene-change samples
inside the configured frame budget. It remains sparse sampling, not exhaustive
shot detection, continuous action tracking, or exact text-duration measurement.
Prepared frames/audio are persistent derivatives. Video and standalone-audio
transcription reuse durable completed chunks; speech engines remain separate
from text/vision reasoning. Music/SFX extraction is not implemented and is
reported as unanalysed rather than inferred from speech.

Speech, on-screen text and visual observations have separate event kinds.
Interpretations and conclusions remain distinct from observations. Correcting
text/timestamps appends evidence revisions with retained originals. Video timing
is validated against measured frame boundaries; audio timing does not invent an
FPS. Exact source IDs, evidence revisions and timestamps are attached by the
server rather than invented by the synthesis provider.

Fresh reference-based creative generation requires the explicitly selected
evidence to be available, reviewed and free of failed extraction stages. The
user can retry a failed reference or explicitly remove it. This does not prevent
viewing partial analysis or drafting manually without references.

## Content planning and production

Content can be organized into a series or remain standalone. Generation supports
distinct concepts/topics and one or more directions rather than the old fixed
faithful/reorganized pair. It consumes confirmed context and exact reviewed
reference snapshots. A useful confirmed assignment is required; the former
six-field and mandatory-selling-point questionnaire is not reinstated.
Assigned series identity, title and concept participate in generation context
and its digest. Applied series changes flag member creative work for review;
unrelated content and source analysis remain unaffected.

Professional-generation instructions are loaded at runtime from the canonical
repository package: the shared method/editorial/quality guides and only the
requested Ideas, Storyboard or Structure module. Input manifests record the
instruction digest and selected model. Reference IDs, declared permitted claim
IDs, complete claim wording, and planned timing receive deterministic checks.
Those checks do not prove that every undeclared assertion in prose is correct;
semantic grounding and professional usefulness still require human evaluation.

Production requires an exact approved direction revision. AI production asks
for an explicit confirmed duration in seconds before producing a timed plan.
That action-specific requirement does not block ideas or manual blank packs.
The four documents are editable text; generated storyboards additionally retain
structured shots with separate dialogue, screen text, sound and timing. Editing
the storyboard as free text clears current synchronized shot rows, while the
previous revision keeps them. The UI does not claim a full screenplay editor,
visual storyboard-image generator, editing timeline or video assembly tool.

Exports are Markdown, editable DOCX, CSV, and printable HTML for browser Save as
PDF. CSV uses structured shot columns when available; after free-text-only
storyboard editing it explicitly exports saved document text. Exports pin the
saved pack revision and input manifest, include supporting source times, and
label incomplete/historical/outdated work. An empty pack cannot be exported.
Pending edits must be saved or discarded before current export; explicit
historical revisions remain accessible. HTML/XML are escaped and spreadsheet
formula-leading cells are neutralized.

## API and processing boundary

The new prefix is `/api/projects`; legacy `/api/tasks` remains separate.

| Method and path | Purpose |
| --- | --- |
| `GET /capabilities` | Version, model baseline/configuration status, migration/library warnings, reserved Discovery status. |
| `GET/POST /` | List/create; `?trashed=true` lists Trash. |
| `GET/PATCH /{project_id}` | Read/refresh or save metadata/navigation/composer/editor drafts. |
| `POST /{id}/duplicate`, `/trash`, `/restore`, `/cache/clear` | Project lifecycle and disposable-cache operations. |
| `POST /{id}/messages` | Save a message and start background assistance. |
| `POST /{id}/brief/draft`, `/brief/apply` | Save working facts or explicitly adopt confirmed context. |
| `POST /{id}/resources` | Multipart local upload and background extraction. |
| `GET /{id}/resources/{rid}/file` | Original, playback or thumbnail representation. |
| `POST /{id}/resources/{rid}/extract`, `/relink`, `/blocks` | Document extraction/media-preview rebuild, exact-original recovery, or text corrections. |
| `POST /{id}/resources/{rid}/recognize` | Retry one resource's recognition without changing selections or synthesizing a comparison. |
| `POST /{id}/resources/{rid}/evidence`, `/evidence/review` | Correct/review exact evidence revisions. |
| `POST /{id}/selection`, `/analyze` | Explicit project/item selection and analysis. |
| `POST /{id}/series`, `/contents`, `/concepts/generate` | Add series/content or generate concepts/topics. |
| `POST /{id}/contents/{cid}/directions` and `/directions/generate` | Save a manual direction or start generation. |
| `POST /{id}/contents/{cid}/directions/{did}/edit`, `/approve` | Revisioned editing and exact approval. |
| `POST /{id}/contents/{cid}/production/generate`, `/production/manual` | Generate or start blank production documents. |
| `POST /{id}/packs/{pid}` | Apply a saved pack revision. |
| `GET /{id}/packs/{pid}/export?revision=N&format=...` | Saved revision export. |

Long operations return 202 with the persisted project/job state. Polling the
project reads status without launching another request. A local executor has
three worker slots; same-scope duplicate active jobs are rejected. Reference
analysis is serialized within one project while per-source completion remains
visible. Restart marks interrupted jobs failed and retains completed work;
potentially billed requests are never automatically replayed. This is a local
single-process runtime, not a multi-user distributed job service.

The project runtime reads current credentials for each operation and pins all
applicable text/vision/research capabilities to `gpt-6.1-sol`. The existing
timestamped transcription engine remains separately configured, normally
`whisper-1`. Session/Keychain connection changes apply without a hosted key.
Model configuration and Models-list access are not evidence of working inference,
audio permission, billing availability, accuracy or quality. No model access
was established by the offline implementation tests.

## Parallel development and verification

| Module | Files / boundary |
| --- | --- |
| Integration/contracts | `models.py`, `api.py`, schema/type generation, launch wiring and cross-module fixtures. One coordinated owner. |
| Project storage | `store.py`, `migration.py`; lifecycle, archive completeness, atomic copies and local ownership. |
| Conversation/context | `conversation.py`, Overview UI; facts, source validation, research proposals, adoption. |
| Resources | `resources.py`, Resources UI; parsers, original storage, previews, extraction corrections. |
| Analysis | `analysis.py`, recognition adapter, Analysis UI; extraction/retry, timing, comparison and citations. |
| Content/production | `planning.py`, `exports.py`, Content plan/Production UI; manifests, directions, approval and documents. |
| Shell | `ProjectApp.tsx`, `project/client.ts`, shared presentation/CSS; navigation, save queues and activity. |
| Discovery | Frank's reserved specification; completed-local-file import boundary only. |

Before changing a shared contract, agree on the producer/consumer change and
merge order. Regenerate schemas and frontend types together. Keep legacy tests
and contracts as a compatibility boundary rather than deleting them to make
the new workspace pass.

```bash
.venv/bin/python scripts/export_project_contracts.py
npm --prefix frontend run project-contracts:generate
.venv/bin/python scripts/export_project_contracts.py --check
npm --prefix frontend run project-contracts:check
.venv/bin/python scripts/export_contracts.py --check
npm --prefix frontend run contracts:check
.venv/bin/python -m pytest -q tests/test_project_workspace_*.py
npm --prefix frontend run typecheck
npm --prefix frontend run lint
npm --prefix frontend run build
npm --prefix frontend run test:e2e:projects
```

The project browser suite uses `frontend/playwright.project.config.ts`, isolated
temporary data, ports 8013/5176, and no live provider key. Broader legacy and
provider-fixture suites remain separate. Use the final integration handoff for
executed results; commands here do not assert that a test has passed.

Live API capability checks, independently annotated transcription/OCR/visual
evaluation, professional usefulness review, and actual macOS launcher/Keychain/
installer acceptance remain distinct checks. Linux/mock/synthetic tests do not
establish those outcomes. No signed self-contained Mac installer or deployment
is claimed by this implementation.
