# Frame timing follow-up — ready for review

- **Task:** change reference-video timing to frames across source frame rates; keep storyboard suggestions in seconds; defer new variables/categories.
- **Author/date:** Codex, 15 October 2026 (UTC).
- **Environment/repository:** managed Codex Cloud Linux, `/workspace/586-project`, `Frankwu899/586-project`.
- **Branch / working-copy commit:** `docs/english-starter` / `0b7a73bf324b0a994f698cf758a4537e212bb120`.
- **Publication follow-up:** after reviewing this implementation, the owner authorized commit and push of the overnight skeleton and frame-timing follow-up together to `docs/english-starter`. The verification below predates publication; use Git history and the remote branch for the resulting commit. No merge or deployment is part of this authorization.
- **Acceptance:** integer source-frame ranges, mixed source FPS support, practical frame seeking/timecode, preserved revisions and saved data, independent storyboard seconds.

## Changes and behavior

`backend/app/models.py` and new `contracts/v0.3.*.schema.json` define zero-based `start_frame` and exclusive `end_frame`. One-frame events are valid; overlaps, section order, citation bounds and immutable correction timing are validated. `VideoAsset.frame_timing` records rational FPS, decoded count, actual presentation boundaries, source origin and constant/variable rate mode. Generated frontend types consume the new schemas. Old v0.1/v0.2 schemas/examples remain byte-identical.

`backend/app/media.py` probes actual frame timestamps without splitting the video into image files. `backend/app/timing.py` converts provider seconds to nearest frame boundaries with a minimum one-frame duration. Intake handles integer, fractional and variable FPS, source timestamps beginning after zero, and audio longer than the video. The sample and failed-recognition adapters include the saved frame count. Confirmation and creative generation require available reference frame timing.

`frontend/src/timing.ts`, `App.tsx` and `AnalysisReview.tsx` show `HH:MM:SS:FF`, frame ranges and source rate, and provide previous/next-frame controls. Seeking uses actual presentation timestamps plus the source playback origin. The browser regressions verify actual media playback and frame stepping, including a 24 fps clip beginning at timestamp 2 seconds.

`backend/app/frame_migration.py`, `migration.py` and `storage.py` migrate prior records. The exact original JSON and SHA-256 are archived in SQLite atomically. Matching media preserves content revisions, review, approval and current outputs. Missing, changed or unrepresentable timing retains explicit legacy seconds and historical user content; affected creative outputs become outdated and require new source analysis. Source content hashes are checked before conversion. The v0.1 importer and new v0.3 fixtures preserve unknown FPS honestly.

The existing `.local-data/morning-review/tasks.sqlite3` was first tested as a copy, then migrated: 200 source frames at 20 fps, zero media origin, one exact original archive row, preserved approved direction and edited outputs. Reopening did not repeat conversion. `.local-data/backups/pre-frame-source.tar.gz` preserves the pre-change source snapshot; runtime data remains ignored and must be transferred separately with media if needed.

Storyboard rows retain `start_seconds`/`end_seconds`; target duration comes from the brand brief. Source FPS has no effect on output planning. Variables/categories and the existing approval workflow are unchanged. Updated setup, architecture, interface, decision and review documents explain the new boundary; a v0.3 frame-based human review CSV supplements unchanged historical worksheets.

## Verification

Final consolidated command: `bash scripts/verify.sh`, exit 0. Full output: `.local-data/frame-verification.log`.

| Check | Observed result |
|---|---|
| Python dependency consistency, schema drift, Ruff | Passed |
| Backend contract/media/migration/adapter/workflow/API tests | **158 passed** in 28.63 seconds |
| Frontend generated type drift | Passed |
| Frontend timing unit tests | **5 passed**, including rational/VFR timing, short events and source offsets |
| TypeScript, ESLint and production Vite build | Passed |
| Connected Chromium browser tests | **2 passed** in 12.9 seconds |
| Historical v0.1/v0.2 JSON schema/example comparison against pre-change archive | **8 files byte-identical** |
| v0.3 review CSVs | BOM, matching 30-column rows, frame bounds and version verified; old CSV hashes unchanged |
| `git diff --check` | Passed |

Generated real MP4 fixtures covered 24, 25, 30, 60, 24000/1001, 30000/1001 and 60000/1001 fps, plus the 20 fps matching sample and actual VFR footage. Tests also cover nonzero source PTS, longer audio tails, one-frame/subsecond intervals, exact migration backup/idempotence/rollback and unavailable-media gates. Browser coverage includes the complete correction/refinement/approval/export/history workflow, the sample chime at frames `[60, 65)`, frame stepping, and an independent 18-second storyboard.

Nonblocking test output includes the existing Starlette/httpx deprecation warning, pip cache permissions, npm update notices and terminal color warnings. No dependency upgrade was needed.

## Environment, limits and next steps

Verified with Python 3.12.14, Node 24.19.0 / npm 11.9.0, FFmpeg/ffprobe 7.1.5 and system Chromium 154 through Playwright 1.56.1. Existing environment settings and dependency versions remain unchanged. Local Mac/PC checks and real camera/device libraries were **not run**.

Input remains H.264 MP4 with optional AAC, with existing 50 MiB / 180-second / 1920×1920 defaults. Timecode uses rounded nominal FPS without drop-frame numbering; it is approximate for fractional/VFR sources. Actual frame boundaries drive seeking, but browser review is not a frame-perfect editing/export guarantee. Frame maps add JSON size and one probing pass. Real recognition and unrestricted creative generation remain unconfigured/sample as documented in the overnight handoff.

No blocker remains for the requested timing change. Review `docs/interfaces.md`, `docs/decisions/frame-timing-v0.3.md` and the contract/media/UI files before integrating. Continue on the same branch and preserve the complete overnight implementation. Frank is the intended reviewer; merging remains a separate action.
