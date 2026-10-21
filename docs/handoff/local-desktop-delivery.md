# Local delivery, stable storage and exact-media repair

## Scope

Implemented on `feat/workspace/structure-agent-redesign` as part of the owner's
authorized workspace revision. No main merge, public deployment, API charge,
model training, macOS binary build, signing or notarization was performed by this
workstream. Other workstreams own UI integration, Structure, recognition and the
shared experiment ledger.

## Delivered behavior

- English browser-launcher messages and focused package documentation.
- Stable OS user-data roots outside the installation folder, including macOS
  `~/Library/Application Support/Video Anatomy/`. The default browser and Mac
  desktop shell share that library. Derived-cache paths are separate; existing
  playback files remain beside retained originals. No bulk deletion is exposed.
- Non-destructive old-library import: SQLite backup including committed WAL,
  integrity/logical-record checks, SHA-256 verification of other files, staging
  followed by directory activation, retained originals and unique import receipts.
  Existing destination libraries are not merged or replaced. Active new-version
  libraries have a process lock. Users must stop the old app before importing.
- `--offline`, `--migrate-from`, `--data-dir` and `--cache-dir`; local runtime metadata
  at `/api/local/runtime`. Explicit experiment-ledger configuration is respected;
  otherwise the one ledger stays in the persistent data directory.
- `backend/app/media_repair.py` exports `create_media_repair_router(service)`.
  POST `/api/tasks/{task_id}/videos/{video_id}/relink` accepts multipart `file` and
  `expected_version`, returning TaskState. It restores only matching original
  bytes to the recorded managed storage ID. It rejects substitutions, tombstones,
  stale versions, oversized streams, symlinks and occupied conflicting files.
  Atomic no-replace installation and rollback preserve unrelated files. Missing
  HEVC playback files are rebuilt only if the exact saved timing metadata matches.
  Analyses, review state, asset identity and pending editor drafts are preserved.
- Electron source with isolated setup IPC, session-only or optional macOS Keychain
  encryption, private stdin transfer, per-process loopback authentication,
  restricted navigation, app lifecycle and library import chooser.
- A macOS-only PyInstaller/portable-FFmpeg runtime assembly pipeline and
  electron-builder configuration with manifest/architecture preflight. Build and
  installer instructions explicitly distinguish untested Mac behavior.
- `package_demo.py --local-api --include-working-tree` includes new integration
  source before committing, built UI and English delivery docs with a SHA-256
  manifest. It excludes user data, credentials, native runtime build directories,
  videos and old patch-generator tooling. An owner video is included only through
  the existing explicit `--private-reference` flag.

## Verification performed

- `pytest tests/test_media_repair.py tests/test_local_storage.py tests/test_local_server.py -q`:
  **29 passed**, including real FFmpeg HEVC reconstruction, missing-original repair,
  prior-analysis and pending-draft retention, failure rollback, committed WAL
  import, secret boundaries and desktop authentication. One existing Starlette
  TestClient/httpx deprecation warning remains.
- Desktop JS syntax checks passed. Node's actual test runner with network-enabled
  sandbox support reported **3 helper tests passed**: session origins/tokens,
  bundled runtime paths and secret removal from child environment.
- Shell syntax and Ruff checks for the owned Python modules/tests passed.
- A real no-key desktop backend subprocess started on an ephemeral loopback port;
  private handshake, runtime metadata and unauthorized HTTP 401 were verified.
  SIGTERM stopped the process. Uvicorn re-raises the received signal on exit
  (`-15` on Linux), which is not an application startup failure.
- A temporary focused ZIP was built and inspected: manifest hashes matched;
  required new modules and frontend build were included; user data, keys and media
  were absent. This was a packaging smoke test, not the final integrated UI bundle.

Managed sandbox note: async TestClient/Node test subprocesses needed the execution
environment's network-capable sandbox for local socket behavior. No external
provider request was involved in those checks.

## Not verified / integration work

- The root integrator mounts the media-repair router in `backend/app/api.py` and
  coordinates the existing timeline UI's relink control.
- Final bundle generation must follow the final frontend build and integrated
  tests; the ZIP smoke used whichever build existed at that point.
- macOS/Windows native launcher execution, Electron UI/Keychain behavior,
  clean-machine runtime portability, .app/DMG installation, Gatekeeper, signing
  and notarization remain unexecuted. See `desktop/README.md` for acceptance.
- External FFmpeg distribution must supply vetted portable binaries and their
  applicable license/source-offer notices. No binaries were downloaded or shipped
  by this workstream.
- Separate derived-cache paths are visible, but existing playback proxies are
  intentionally retained with originals until a verified storage transition is
  implemented. Persistent paid results must not be deleted by cache cleanup.

No commits were created by this workstream; the integrator owns the combined
review and Draft PR.

## Integrated provider-browser follow-up

The integrator additionally assigned `frontend/e2e/providers.spec.ts` and its
provider Playwright configuration. Tests now await persisted asynchronous
operation tickets and select timeline observations through the inspector, with
an explicit reviewed-reference choice for the reference-backed creative case.
The fixture server environment explicitly clears `OPENAI_API_KEY` and sets
`RUN_LIVE_MODEL_TESTS=0`.

`npm --prefix frontend run test:e2e:providers`: **4 passed (20.5 seconds)**.
Coverage retains actual HEVC-to-H.264 playback/frame stepping, bilingual visual/
OCR/speech corrections, rejected broken product relationships, review, direction
refinement/approval, Markdown/CSV export, reload and stale output behavior, partial
structured coverage, and M2 proposal adoption/stale/error recovery. Outputs remain
explicitly synthetic fixture results. ESLint passed for the changed test/config.

## Final local archive smoke

After the integrator's final frontend changes, `npm --prefix frontend run build`
passed and the private local ZIP was generated at
`/workspace/video-anatomy-artifacts/video-anatomy-v0.7-macos-local.zip`. The English
artifact report `video-anatomy-v0.7-release-checks.md` records its hash/build assets.
Fresh extraction passed manifest, permissions, exclusion and private-reference
checks. The extracted source/built UI ran with an isolated offline library; the
supplied reference imported unanalyzed, a fictional Structure graph rendered,
and an independent original notebook retained text through reload. No page errors,
external browser requests or paid provider calls occurred. The smoke reused Linux
Python dependencies; macOS first installation and DMG remain untested.
