Historical v0.2 milestone. The current frame-timing implementation and latest verification are in [frame-timing-review.md](frame-timing-review.md).

Ready for review — the complete agreed sample skeleton and all required verification gates passed.

# Overnight skeleton morning review

- **Task:** implement the complete repository-root `overnight-skeleton-spec.md` mission.
- **Author/date:** Codex, 15 October 2026 (America/Los_Angeles).
- **Environment:** managed Codex Cloud, Linux, repository `/workspace/586-project`.
- **Repository:** `https://github.com/Frankwu899/586-project.git`.
- **Implementation branch / starting commit:** `docs/english-starter`, `0b7a73bf324b0a994f698cf758a4537e212bb120`.
- **Initial environment checkout:** `work` at `e98a33caa942e57ce9198d9ef34dc2f911cd263d`, clean but missing the specification. Read-only GitHub inspection located the root specification on `docs/english-starter`; that branch was fetched and checked out before implementation.
- **Git handoff:** all implementation changes remain uncommitted in the workspace. No manual commit, push, PR, merge, deployment, force-push, or history rewrite. The specification commit was already on GitHub; none of this implementation has been published there by this task.

## Feature and verification status

| Feature | Behavior | Verification |
|---|---|---|
| Task creation, brief entry, save/reopen, SQLite persistence | **working**; independent task histories and optimistic version checks | API, restart and browser checks |
| Upload and playback | **working** for tested H.264 MP4 with optional AAC; configured limits; local range serving | Media/API tests and actual Chromium playback/seek |
| Dedicated fictional reference analysis | **sample-backed**; matching generated clip, overlap, coverage, provenance and content hash | Contract, adapter, API and browser checks |
| Arbitrary-upload recognition | **unconfigured**; explicit failed state, no sample fallback | Identical sample bytes re-uploaded through ordinary intake still rejected as unconfigured |
| Analysis correction and separate review confirmation | **working**; text/visual/role permissions enforced server-side; originals and timing preserved | Contract, API, service and browser checks |
| Two directions, direct edits, saved selection and exact approval | **sample-backed** generation; **working** version/approval persistence | Gate, persistence and browser checks |
| Saved free-text refinement | **sample-backed** literal presenter-free demonstration; unsupported text retained as **not interpreted** | Adapter spy, service, browser checks |
| Editable production brief/storyboard and regeneration | **sample-backed** generation; **working** edits, exact dependencies, separate planned time | Contract, service and browser checks |
| Outdated outputs after upstream changes | **working**; previous content retained and approval invalidated | Brief/analysis/direction/refinement tests and browser checks |
| Markdown/CSV exports | **working**, with sample/currentness/input context, CSV escaping/formula protection | API round-trip and browser downloads |
| Human reference review | **working** guide, blank event template and fictional examples | CSV consistency and original-template preservation checks |
| Real creative provider and unrestricted prompt interpretation | **unconfigured** | Not run; intentionally outside sample baseline |
| Platform downloads, training, multi-video comparison, storyboard images, public deployment | **not implemented**, outside scope | Not run |

This is a single-user local team demonstration. It establishes internal connections, not recognition accuracy or creative effectiveness. It has no public hosting or multi-user security design.

## Exact setup and startup

The Cloud run used Python 3.12.14, Node.js 24.19.0, npm 11.9.0, FFmpeg/ffprobe 7.1.5, system Chromium 154.0.8037.57, and Playwright 1.56.1. FastAPI 0.141.1/Pydantic 2.13.4 and all Python dependencies are pinned in `requirements.lock`; frontend dependencies are pinned in `frontend/package-lock.json`. The Mac and Andrea's computer were **not configured or tested** by this task.

From the repository root, on a computer with Python 3.12, Node/npm and FFmpeg/ffprobe installed:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
npm --prefix frontend ci
```

Start the backend in terminal 1:

```bash
.venv/bin/python -m uvicorn backend.app.api:app --host 127.0.0.1 --port 8000
```

Start the frontend in terminal 2:

```bash
npm --prefix frontend run dev
```

Open `http://127.0.0.1:5173`. Use one backend worker. Default runtime storage is `.local-data/tasks.sqlite3` plus `.local-data/media/`, all ignored by Git. `.env.example` documents settings; export desired environment values before startup because `.env` is not loaded automatically. Git transfers neither local data nor installed environments.

Create a task and use **Load synthetic sample**, or seed a review-ready sample before starting the server for that data directory. Keep one service process per data directory so startup recovery cannot mistake another process's live job for an interrupted operation:

```bash
.venv/bin/python scripts/load_sample.py
```

For a complete fictional example containing **scripted** correction, review, approval, refinement and edited outputs:

```bash
.venv/bin/python scripts/load_sample.py --complete
```

Each invocation creates a new task. Scripted approval is only fixture setup, not Frank's or Andrea's real approval. The completed task JSON is also in `examples/v0.2.sample-task.json`; its media must be generated locally. A complete Cloud sample was created under `.local-data/morning-review` using:

```bash
.venv/bin/python scripts/load_sample.py --data-dir .local-data/morning-review --complete --write-fixture examples/v0.2.sample-task.json
```

Standalone matching-media setup:

```bash
.venv/bin/python scripts/generate_sample_media.py --output .local-data/sample/lumacup_shapes_v1.mp4
```

This produces ten seconds of original illustrations/text/tones, with no human speech. The inspected file was 98,327 bytes, 640×360, H.264/AAC. Intake tests also exercised H.264 without audio, actual unsupported MPEG-4 encoding, corrupt/empty/missing media, size/duration/dimension limits, and sample hash mismatch. These tests do not establish compatibility with every device or MP4 profile.

## Verification results

The final verification entry point is:

```bash
bash scripts/verify.sh
```

The script runs the exact ordered commands below. On a machine without system Chromium, install Playwright's browser first (`cd frontend && npx playwright install chromium`), or set `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` to an installed Chromium. The Cloud run used `/usr/bin/chromium`.

| Command / check | Final observed result |
|---|---|
| `.venv/bin/python -m pip check` | Passed; no broken requirements |
| `.venv/bin/python scripts/export_contracts.py --check` | Passed; generated JSON schemas match models |
| `.venv/bin/python -m ruff check backend tests scripts` | Passed after removing one unused test import |
| `.venv/bin/python -m pytest -q` | **72 passed**, 1 third-party deprecation warning, 22.80 seconds |
| `npm --prefix frontend run contracts:check` | Passed; generated frontend types match schema |
| `npm --prefix frontend run typecheck` | Passed |
| `npm --prefix frontend run lint` | Passed |
| `npm --prefix frontend run build` | Passed |
| `npm --prefix frontend run test:e2e` | **1 passed**, 10.0 seconds, including persisted selection and real playback/seek |
| Legacy schema/examples and original five CSVs | Byte-identical to starting commit |
| Documented migration CLI and HTTP example | Executed successfully against isolated storage/local backend |
| Independent provider/race probes | Passed: adapters cannot self-confirm/approve, delayed results preserve newer edits, 15 negative analysis-state gates |
| Real paid model/provider calls, platform download, public deployment | **NOT RUN**; outside the authorized sample baseline |
| Mac/Andrea machine validation | **NOT RUN**; those environments were not accessed |

`bash scripts/verify.sh` completed with exit code **0**. The final Cloud log is `.local-data/verification.log` (ignored runtime artifact). No required check is failed or unexecuted. The browser walkthrough uses isolated storage and local servers. It creates and saves a brief, loads the matching sample, plays/seeks real media, expands observations, corrects text/roles, confirms analysis, compares and edits directions, applies supported and unsupported instructions, approves, generates/edits/downloads outputs, refreshes/reopens, and changes an upstream input to verify outdated outputs. It also re-uploads the same MP4 through ordinary intake to verify the honest unconfigured-real state and reloads an unapproved selection before approval.

Resolved execution issues are not counted as passing runs: the default Cloud sandbox initially denied local server binding and stalled FastAPI TestClient's async wakeup; the supported network permission enabled local-only execution. One Python lint run found an unused import, which was removed. The first browser attempt found form hint text included in accessible field names; label/description associations were fixed and the full workflow rerun. A later consolidated browser run caught the selection test asserting a controlled radio's state before its asynchronous save completed. The test now waits for the successful save response, checks the exact chosen revision and unapproved state, and checks persistence after reload; it passed twice consecutively and in the final consolidated run. Earlier integration review also found and fixed storage-ID shape, atomic validation transitions, and adapter-owned approval bypasses. One Starlette TestClient deprecation warning was emitted for the pinned HTTPX integration; it was not a test failure.

## Contract and implementation map

Contract **v0.2.0** uses canonical timed `EvidenceEvent` records and sections that reference them. `backend/app/models.py` is authoritative; JSON schemas and TypeScript types are generated with drift checks. Cross-record validation enforces exact task/video/analysis revisions, unique IDs, finite source times, nonoverlapping sections, overlapping events, correction-log replay, provenance and dependency/approval rules. Storyboard planned times use the brief's target duration, separate from source-video evidence.

The v0.1 schema and both supplied analysis examples remain unchanged. Explicit migration in `backend/app/migration.py` preserves synthetic labels, unknown metrics, original and corrected revisions, and missing/unverified media. Corrected interpretations that no longer match revised observations are cleared; original text remains in revision 1 and the legacy files. Migration supports the supplied completed examples; it does not fabricate playable video or constitute a general-purpose provider importer.

The final change set contains **60 files: 6 modified baseline documents and 54 new source/configuration/schema/example/test/documentation files**. No original legacy JSON/schema or existing CSV content changed. Important changed/new files:

- `backend/app/{models,migration,storage,service,api}.py`: contracts, migration, persistent aggregate storage, workflow gates and routes.
- `backend/app/{media,adapters,sample}.py`: measured media intake, recognition/creative protocols, honest sample/unconfigured implementations.
- `frontend/src/`, generated contract types, package lock/config and `frontend/e2e/workflow.spec.ts`: connected interface and browser verification.
- `contracts/v0.2.*.schema.json`, `examples/v0.2.*.json`, sample manifest and review CSV examples: versioned shared artifacts and fictional data.
- `requirements.in`, `requirements.lock`, `pyproject.toml`, `.env.example`, `.gitignore`, `scripts/`, `tests/`: reproducible setup, checks and runtime-data separation.
- `README_SETUP.md`, `docs/interfaces.md`, architecture/brief/decision/review guides, AGENTS scope update: implementation and team handoff documentation.

## Prompting behavior and remaining work

Supported sample instructions are the case-insensitive literals `Make this direction presenter-free.`, `Make it presenter-free`, and `presenter-free`, with an optional final period/exclamation mark. They change Hook/narrative/production requirements and generate a new unapproved draft; approved production subsequently uses product-only imagery/text without spoken dialogue. Other wording remains saved with its exact target/input references as `not_interpreted` feedback. It is visible as a production note in feedback history, does not silently change the direction, and does not claim unrestricted understanding.

There are **no remaining blockers for the agreed sample baseline**. Remaining real integration work needs the team's chosen provider, permitted media, credentials and permitted network access; none was invented or called tonight. Single-worker storage and synchronous jobs are intentional demonstration limits. Partial analysis is representable but cannot be confirmed for creative use in this version. Draft-video purpose is reserved without an improve-draft workflow. Whole-output regeneration and text editing are supported; planned timing edits are not exposed.

**Andrea's first concrete task:** implement a real class behind `backend/app/adapters.py::RecognitionAdapter.analyze(request: RecognitionRequest) -> AnalysisResult`, then wire it as `WorkflowService.real_recognition`. The request supplies saved task/video/job identity and a resolved local media path. Return a new unconfirmed revision-1 result with normalized visual actions, on-screen text and speech, measured time bounds, explicit coverage, honest provider provenance, and useful structured errors. Start from `SampleRecognitionAdapter`, `examples/v0.2.sample-task.json`, `tests/test_adapters.py`, and `docs/interfaces.md`; keep provider transport/parser details outside the UI. Run one permitted real clip through correction, review, direction approval and production, while preserving every existing gate.

**Frank:** review the complete sample and shared contract, then commit/push the chosen changes. UI/UX refinement and a real creative adapter can follow without replacing the brief/evidence/feedback boundaries. Review and merge remain Frank's decisions.
