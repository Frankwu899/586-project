# Local Sol release — v0.7.8

- Author/date: Codex for Frank, November 3, 2026 (Los Angeles).
- Repository: `Frankwu899/586-project`.
- Release task: `feat/integration/local-sol-release`.
- Starting main: `542d7ec47116f9330ff0ef514e340fc3675c1dea`.
- Reviewed UI PR #13: `10e4f1a4a5b9954623fe5cce7547e6b39f9545b6`.
- Reviewed evaluation PR #14: `d938d5e5a6edf08d93ca94e7b802aa994359e7a6`.
- Owner decision: keep the existing local application and API-key connection
  flow, cancel paid shared hosting, merge current team work, and deliver a ZIP.
- Final merge SHA is recorded in the task response and archive BUILD_INFO.json.

## Delivered behavior

The local launcher pins vision, M2 assistance, Structure, research, Ideas,
refinement and production generation to `gpt-6.1-sol`. Old per-model shell
overrides cannot silently choose Luna or another model in this launcher.
Timestamped transcription stays on the approved `whisper-1` adapter. Direct
Cloud evaluation configuration remains separately selectable.

API connection controls, session/Keychain storage, persistent local projects,
approval gates and revision history retain their current behavior. This release
does not require a hosting subscription. Provider API usage still has its own
charges. No real API key, uploaded private video or saved task is bundled.

PR #13's readability, graph navigation, resizing and scrolling changes are
included. PR #14 now reports six OCR experiments (five live requests) and seven
live Sol Structure runs on synthetic evidence. These are Andrea's recorded
results, not calls reproduced during this release. Raw evaluation outputs remain
local-only; the formal real-video comparison and independent scoring are still
incomplete. Sol is the selected baseline, not a proven optimal model.

The proposed shared-server/Render changes in PR #15 are withdrawn and excluded.
The repository's v0.7.7 professional-generation instructions are included in the
ZIP as specifications; their runtime prompt integration remains pending.

## Checks and evidence

Release checks were executed in managed Linux with Python 3.12.14 and Node
24.22.1. The full backend suite result is recorded below after completion.

- Backend full suite: 731 passed; one Starlette/httpx deprecation warning.
- Local launcher/credential/preferences/usage subset: 81 passed.
- Frontend unit tests: 41 passed.
- Python dependency consistency, generated schemas, Ruff, frontend generated
  contracts, TypeScript, ESLint and production build: passed.
- Extracted ZIP smoke: app/static startup, local credential API availability,
  all five Sol model fields, project creation and synthetic media import passed.
  Provider requests were prohibited during this check.
- Archive integrity: manifest hashes, Finder executable mode, app version and
  absence of private data/hosting scripts checked before publication.
- Connected browser suite and provider browser suite: each attempted with
  fail-fast; Chromium failed before executing application assertions because
  the environment denied its process-singleton socket. They are **not passed**.
- Actual macOS Finder/Keychain/Gatekeeper checks and real provider calls: not run.

The Mac ZIP is the existing source-backed Finder launcher format. It requires
the installed Python/FFmpeg dependencies described in `MAC_APP.md`; it is not a
signed, self-contained native binary. See the ZIP's READ ME FIRST.md.

## Merge and review

The owner explicitly authorized merging. Preserve PR #13 and #14 history and
merge the small local-policy/version change using normal GitHub PR merges.
Main had no branch protection at the pre-merge check; no GitHub check runs were
published for #13/#14. The ordinary merge API must still enforce any new gates.
The independent code review found no blocker in the model policy or retained
credential flow. No force push, branch deletion, deployment or paid model call
is part of this release. Browser and Mac acceptance remain explicit follow-ups.
