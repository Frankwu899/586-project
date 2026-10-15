# Video Anatomy — local sample skeleton

The v0.3 application connects task/brief persistence, local video upload, sample analysis review, two creative directions, saved feedback and approval, production brief/storyboard editing, and export. Recognition and creative generation in the complete demonstration are explicitly fictional/sample. Arbitrary uploads are saved and inspected, but real analysis returns **not configured**. No API key or paid request is required.

Start with the [integration handoff](docs/handoff/skeleton-integration-and-branches.md) for current integration checks and publication status. The [frame-timing handoff](docs/handoff/frame-timing-review.md) and initial [skeleton handoff](docs/handoff/overnight-skeleton-review.md) record earlier runs. `overnight-skeleton-spec.md` records the original task scope; `docs/decisions/skeleton-v0.2.md` records the technical defaults. Cloud verification does not mean Frank's Mac or Andrea's computer has been configured or tested.

## Team Git workflow

Read [branch workflow](docs/branch-workflow.md) for the beginner walkthrough and [module ownership](docs/module-ownership.md) for actual source files and shared-file coordination. `main` is the only permanent shared branch. Create temporary `<type>/<module>/<specific-task>` branches from updated `main`, make coherent commits, push, open a PR, review/test, then merge through the permitted route. Every branch contains the complete app; module scopes do not require new directories.

Andrea owns the next real recognition adapter task; Frank owns the next real creative-generation task. Their intended branches are `feat/video-analysis/first-real-provider` and `feat/creative-direction/first-real-provider`. Preparation remains **pending until verified after baseline integration**; use the final integration report for actual branch names and exact base commits. This setup does not implement providers or make paid API calls.

On your Mac, first inspect `git status --short`, `git branch --show-current`, and `git remote -v`, then run `git fetch origin`. Preserve local changes on their current task branch or in a separate worktree before switching. With a clean checkout, run `git switch main` and `git pull --ff-only origin main`; if a fast-forward fails, inspect the divergent work without resetting it. Cloud work does not update this checkout or install its dependencies. Follow the runtime/setup steps below. The older `docs/cloud-workflow.md` is a historical starter guide; this README describes the runnable application.

## Runtime requirements

Install these on each computer that will run the application:

| Requirement | Version / use |
|---|---|
| Python | 3.12; Cloud runtime inspected: 3.12.14. Use a project virtual environment. |
| Node.js / npm | Node ≥22.12 and npm ≥10; Cloud inspected: Node 24.19.0, npm 11.9.0. |
| FFmpeg and ffprobe | Both on PATH, with H.264 (`libx264`) and AAC support for sample generation/intake; Cloud inspected: 7.1.5. |
| Browser | A modern local browser for the app. Playwright Chromium is needed for automated browser checks. |
| Git | Obtain the source checkout; GitHub CLI is optional. |

Python packages are pinned in `requirements.lock`; `requirements.in` identifies direct dependencies. Frontend packages are pinned by `frontend/package-lock.json`. Do not reuse the previously reported Mac Python 3.9 environment; install Python 3.12 and check the active executable. A Git pull does not transfer Python environments, Node packages, API keys, task data, or media.

## Install dependencies

The commands below use a macOS/Linux shell. Run from the repository root after the required runtimes are installed:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
npm --prefix frontend ci
```

Install the Chromium browser used by Playwright for verification:

```bash
cd frontend
npx playwright install chromium
cd ..
```

On supported Linux hosts, Playwright may also need system browser libraries (`npx playwright install --with-deps chromium` from `frontend/` when installation permissions are available). If an existing Chromium is available, set `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` to its absolute path instead. A missing automated-browser runtime does not change the app's sample/provider labels; report any browser check that could not execute.

## Start the app

Use two terminals from the repository root. Backend:

```bash
.venv/bin/python -m uvicorn backend.app.api:app --host 127.0.0.1 --port 8000
```

Frontend:

```bash
npm --prefix frontend run dev
```

Open [the local app](http://127.0.0.1:5173). Vite proxies `/api` to port 8000; [the API reference](http://127.0.0.1:8000/docs) documents the actual routes. Use one backend worker for this team demonstration. The app is not publicly deployed.

The backend stores SQLite task data in `.local-data/tasks.sqlite3` and media under `.local-data/media/`. Set `VIDEO_ANATOMY_DATA_DIR` before starting to use another directory. `.env.example` documents all supported settings; the application does **not** automatically load a `.env` file. Export desired values in the terminal, for example:

```bash
export VIDEO_ANATOMY_DATA_DIR="$PWD/.local-data"
```

Keep uploads, generated media, runtime task data, secrets, and caches out of Git. Back up or transfer the entire data directory separately if local progress needs to move between computers. Source checkout and generated JSON fixture alone do not transfer playable media.

## Open the fictional sample

In the app, create a task, enter/save a brief if desired, and load the dedicated synthetic sample into that task before uploading a real video. With no existing brief, sample loading supplies a fictional LumaCup brief. Request sample recognition, expand observations, play/seek the matching video using frame timecode or previous/next frame, save a content/role correction if needed, and use **Use this reviewed analysis**.

Generate two directions, try **Make it presenter-free**, inspect the changed draft, explicitly approve it, and generate the production brief/storyboard. Edit/save output text and export. Refresh/reopen to check persistence. Saving an upstream brief or analysis revision keeps earlier work but marks dependent creative work outdated and removes dependent approval.

A radio-button direction choice is saved separately from approval and survives refresh. Selecting a different draft does not approve it; explicit approval of the current revision is still required for production.

Alternatively, seed a task through the same persistent services before starting the backend for that data directory, then open the app's task list. The demo assumes one service process; startup recovery must not run beside active generation using the same storage:

```bash
.venv/bin/python scripts/load_sample.py
```

This creates matching media and sample analysis ready for human review. To inspect a fully populated fictional walkthrough, including **scripted** correction, review/approval, refinement, and edited outputs:

```bash
.venv/bin/python scripts/load_sample.py --complete
```

Scripted approval is demonstration data, not Frank's or Andrea's real approval. `--data-dir PATH` selects storage; `--write-fixture PATH` additionally saves a validated JSON snapshot. Each run creates a new task.

For standalone sample-media generation:

```bash
.venv/bin/python scripts/generate_sample_media.py --output .local-data/sample/lumacup_shapes_v1.mp4
```

The clip is ten seconds at 640×360, 20 fps, H.264/AAC: original cup-shaped graphics, on-screen English labels, a synthetic melody, and two chimes. There is no human speech, real footage, or measured product effectiveness. Loading an unrelated upload does not enable sample recognition. Schema-only legacy examples contain a fictional `NO_MEDIA.mp4` name and are not playback assets.

## Media limits and sample refinement

Implemented intake is `.mp4` with exactly one H.264 video stream and zero or one AAC audio stream. Default limits are 50 MiB, 180 seconds, and 1920×1920 pixels. The backend reads the rational frame rate and each decoded frame timestamp, then validates media. Reference observations use zero-based frame ranges; the player shows `HH:MM:SS:FF` with absolute frame indices. Constant, fractional (for example 29.97), and variable-rate clips use their own measured timing. Timecode is nominal non-drop-frame and approximate for fractional/variable rates. Storyboard suggestions continue to use seconds without an FPS setting. The backend reports unsupported/unreadable inputs, missing media, or missing tooling. Limits and inspection timeouts are configurable in `.env.example`, and the active configuration appears at `/api/config`. Source URLs are provenance only; platform downloading is deferred. See the handoff for the precise media cases actually tested.

The creative sample recognizes case-insensitive `Make this direction presenter-free.`, `Make it presenter-free`, and `presenter-free`, with optional final period/exclamation mark. It changes the draft and later approved production plan to product-only visuals/text with no spoken dialogue. Other instructions remain saved in feedback history as **not interpreted**, without pretending a new draft was generated. Real providers and broader prompt interpretation remain future work.

## Verify the checkout

After dependencies and the browser runtime are available, run the ordered gate script from the repository root:

```bash
bash scripts/verify.sh
```

It checks installed Python dependency consistency, generated schemas, Python lint/tests, generated frontend types, timing unit tests, TypeScript, frontend lint/build, and the automated browser walkthrough. The browser tests start isolated local servers. Read the actual output; a written test or a successful HTTP response alone is not evidence that recognition or the full UI passed. Current integration results and unexecuted checks are recorded in [the integration handoff](docs/handoff/skeleton-integration-and-branches.md); the frame-timing handoff records the earlier run.

For a contract change, regenerate and verify the shared artifacts:

```bash
.venv/bin/python scripts/export_contracts.py
npm --prefix frontend run contracts:generate
.venv/bin/python scripts/export_contracts.py --check
npm --prefix frontend run contracts:check
```

## Developer map

| Path | Purpose |
|---|---|
| `backend/app/models.py` | Authoritative v0.3 records and semantic validation. |
| `contracts/v0.3.*.schema.json`, `frontend/src/generated/contracts.ts` | Generated schemas and frontend types. |
| `backend/app/api.py`, `backend/app/service.py` | HTTP routes, version/approval/currentness gates and workflow operations. |
| `backend/app/adapters.py` | Andrea's recognition boundary and Frank's creative/production boundary. |
| `backend/app/media.py`, `backend/app/storage.py` | Media validation/storage and persistent task storage. |
| `backend/app/migration.py`, `backend/app/frame_migration.py` | Explicit v0.1 fixture import and automatic archived v0.2 migration; no invented FPS. |
| `backend/app/timing.py`, `frontend/src/timing.ts` | Frame/media-time conversion and timecode display. |
| `frontend/src/` | Plain usable application UI. |
| `scripts/load_sample.py`, `scripts/generate_sample_media.py` | Reproducible sample records and matching media. |
| `docs/interfaces.md` | Actual requests/results/errors, adapter entry points, valid examples, timing and revision rules. |
| `docs/architecture.md`, `docs/project-brief.md` | Module boundaries and confirmed product scope. |
| `docs/reference-review-guide.md`, `data/templates/` | Human annotation guide and preserved/extended team worksheets. |
| `docs/branch-workflow.md`, `docs/module-ownership.md` | Module task naming, actual source map, owners and shared-file coordination. |
| `docs/handoff/skeleton-integration-and-branches.md` | Current integration verification, limitations and Git handoff. |
| `docs/handoff/frame-timing-review.md` | Earlier frame-timing verification and limitations. |

All v0.1 and v0.2 schemas/examples are preserved unchanged. Saved v0.2 tasks migrate automatically at startup, with exact original JSON archived transactionally in SQLite. Matching available media supplies the frame map; unknown timing retains legacy seconds and disables new creative use until the source is uploaded and analyzed again. See `docs/interfaces.md` for the explicit migration command and the `examples/v0.3.legacy-migrated.json` schema-only result. Existing CSV templates remain compatible; the current `reference_review_v0.3.csv` worksheet uses frames; old worksheets retain their original seconds columns. Never treat synthetic fixtures or public engagement counts as evidence of recognition accuracy or marketing effectiveness.
