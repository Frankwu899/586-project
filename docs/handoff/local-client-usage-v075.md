# Local client usage reporting — v0.7.5

- **Task:** Remove experiment-budget restrictions from local client generation.
- **Author/date/environment:** Codex, 2026-10-19, Linux Cloud with Python 3.12.
- **Repository/branch:** Frankwu899/586-project, `feat/workspace/structure-agent-redesign`.
- **Baseline:** `ca1642a9685f2c101ac6e03db49551e00642121c` (v0.7.4).
- **Review:** Draft PR https://github.com/Frankwu899/586-project/pull/8, stacked on PR #7. No main merge or deployment.

## Decision and behavior

The owner clarified that USD 3 was authorized only for Cloud experiments, not
local client use. Local Finder/command launchers explicitly disable experiment
budget enforcement across visual analysis, speech, Structure, background research,
input assistance, Ideas and Production. The separately invoked experiment harness
and default Cloud provider settings retain the shared USD 3 guard.

Local requests do not construct or consult the experiment ledger, reserve funds,
run budget input-token preflight, or stop because of an accounting pause, unresolved
reservation, expired price table or missing cost estimate. Historical ledger bytes
are preserved. Usage reporting reads sanitized transport records and never controls
request admission. Estimates can be incomplete and do not represent an invoice or
OpenAI account balance. Provider access/rate/quota limits and normal output/timeout
contracts still apply. Existing interrupted operations are not automatically retried.

API connection shows API usage and No client-side spending cap, with recorded
estimates, attempts and unknown costs. It has no local Remaining balance or
reservation-recovery controls. The existing API endpoint remains compatible and
returns `enforced: false`, `maximum_usd: null`, `remaining_usd: null` locally. Legacy
reconciliation is a read-only no-op in this mode. Credential and language updates
preserve the mode without rebuilding the workflow service or resetting data.

GPT-6 model selection and the approved Whisper speech exception are unchanged.
Cache identities exclude the new policy flag, retaining compatible paid results.
No credentials, case videos or saved projects are bundled.

## Changed files

- Provider config/transport and new `local_usage.py`: separate Cloud enforcement
  from non-blocking local reporting; recognition cache policy exclusion.
- Local server/connection: explicit local mode and read-only usage endpoint.
- BudgetStatus and browser coverage: local usage view plus retained legacy view.
- Mac bundle version, current delivery docs, environment example and AGENTS:
  correct budget scope; historical model/budget handoff links this clarification.
- `tests/test_local_usage.py`: local bypass, reporting, retention and Cloud guard.

## Verification

- `.venv/bin/pytest -q`: **730 passed**, one existing Starlette deprecation warning.
- `.venv/bin/ruff check backend scripts tests`, generated backend contract check,
  frontend TypeScript/ESLint, production build, seven unit-test files and frontend
  contract check: passed.
- Playwright `e2e/budget-status.spec.ts e2e/api-connection.spec.ts`: **8 passed**.
- Regression fixtures cover all six provider capability labels with a blocked,
  exhausted old ledger; generation proceeds without token preflight and old ledger
  bytes remain identical. Unknown/stale estimates do not invalidate responses.
  Default Cloud settings still enforce the cap. No real paid request was made.
- Extracted final archive: **115 manifest files match source**; plist/version,
  executable mode and shell syntax pass. Actual localhost startup, empty library,
  English/Chinese preferences, no-cap usage endpoint, Trash/Restore, built UI and
  authenticated shutdown pass. No database/media/key is packaged.

## Delivery and preservation

Artifact: `video-anatomy-v0.7.5-macos-app.zip`, **495228 bytes**.
SHA-256: `d99a2570073ca2546e45c36af3a0469dbe267952ae068ea1182ab9c6fd5a292a`.

Extract and open the new Video Anatomy.app. Its existing idle-server handover loads
this version. Keep the shared library and Keychain credential; no reset or new key
is required. Retry the previously failed action explicitly. The app should show
API usage / No client-side spending cap. If it still shows Local test budget, the
old app/server is running.

The repository was clean at the baseline; all edits belong to this update. Commit
and remote synchronization are recorded in Git and PR #8 after validation. Preserve
the current feature branch and do not merge main. The Mac library remains at
`~/Library/Application Support/Video Anatomy/`; back it up intact after closing.

## Remaining verification

Live model permissions, actual cost/quality/latency and native Mac
Finder/Keychain/Gatekeeper execution were **not run**. Cloud has no project secret
or permitted OpenAI connection. The package uses installed Python 3.12 and FFmpeg,
opens the browser, and is neither a signed/notarized installer nor a DMG.
No model training was performed. Next acceptance: open the new app on the owner's
Mac and retry analysis/generation with its existing key and saved projects.
