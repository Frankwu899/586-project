# Shared backend with GPT-6.1 Sol

- **Task:** Pull current PR work and prepare an owner-funded shared backend.
- **Author and date:** Codex for Frank, 2026-11-03.
- **Environment:** Managed Linux cloud; Python 3.12.14, Node 24.22.1, npm 11.9.0.
- **Repository:** `Frankwu899/586-project`.
- **Branch:** `feat/integration/shared-backend-sol`.
- **Base main:** `542d7ec47116f9330ff0ef514e340fc3675c1dea`.
- **Integrated PR #13 head:** `10e4f1a4a5b9954623fe5cce7547e6b39f9545b6`.
- **Integrated PR #14 head:** `e1564c81adb0e062d734c4092a40c1a1ac61518e`.
- **Publication:** Prepared for a Draft PR. Its final remote SHA/URL are recorded
  in the PR and task response, rather than embedding a commit's own SHA here.
- **Acceptance:** One operator-owned server credential; no client API-key entry;
  shared text/vision/research baseline pinned to Sol; retained speech adapter;
  access controls and persistent project storage.

## Changes and coordination

PR #13 contributes its full readability/navigation work, tests and screenshots.
PR #14 contributes Andrea's model evaluation report and test matrix. Both were
still open at the last remote check. Their histories are retained as parents of
the integration commit; this does not merge either PR into main.

Andrea's report is explicitly preliminary. Its live quality, latency and cost
matrix is unmeasured; it is not evidence that paid comparison tests passed or
that Sol was proven superior. The owner selected Sol as the operational baseline.

New `scripts/shared_server.py` wraps the existing local app with mandatory team
HTTP Basic authentication, exact host/origin checks, a mutation header, and
operator-only credential/runtime controls. Only `/healthz` is public. It pins
all five text/vision/research model fields to `gpt-6.1-sol`, all providers to
OpenAI, and transcription to `whisper-1`. Preferences preserve this policy.
The entrypoint holds the existing process lock for its persistent directory.

`frontend/src/ApiConnection.tsx` does not mount the key dialog or show its button
in shared mode. `api.ts` adds the same-origin mutation header. `App.tsx` and
`i18n.tsx` identify the shared workspace. Existing local launchers retain their
credential flow. `Dockerfile.shared`, `.dockerignore`, `SHARED_SERVER.md` and the
README setup link provide deployment instructions without embedding secrets.

No shared domain models, schemas or workflow service/API files were changed by
this server task. PR #13's edits remain preserved. Frank owns integration;
Andrea's evaluation remains an independent report. The v0.7.7 professional
generation instructions are still not integrated into runtime prompts here.

## Verification

| Check | Procedure | Observed result |
|---|---|---|
| Full backend | `bash scripts/verify.sh` backend phase | 752 tests passed, one Starlette/httpx deprecation warning |
| Hosted boundary | `pytest -q tests/test_shared_server.py` | 22 passed; included in the full backend count |
| Python dependencies/schema/lint | Verification script before pytest | Passed |
| Frontend contracts | `npm --prefix frontend run contracts:check` | Passed |
| Frontend unit tests | `npm --prefix frontend run test:unit` | 41 passed |
| Frontend types/lint/build | Verification script frontend phases | Passed |
| Hosted browser | `npx playwright test --config playwright.shared.config.ts` | Blocked before test execution: Chromium process-singleton socket permission denied |
| Existing connected browser suite | Verification script browser phase | Same browser-launch environment failure; not a UI pass |
| Provider browser suite | Last verification-script phase | Not reached after browser failure |
| Docker image | `Dockerfile.shared` | Not built; Docker is unavailable in this environment |
| Live provider calls | None | Not run; no key or API access is claimed |
| Public deployment / Mac | None | Not run |

Tests use fake keys and synthetic data. The hosted browser test is added for a
browser-capable environment and covers absent key controls, project creation,
reload, language changes and anonymous access rejection. A passing backend test
does not establish that this browser scenario or real generation works.

## Synchronization and next steps

The isolated source snapshot preserves the prior packaged application directory.
Main was rechecked before publication and remained at the SHA above. PR #13 and
#14 heads also remained unchanged. No force push, branch deletion, main merge,
existing project-data migration or credential transfer is part of this task.

Read `SHARED_SERVER.md` first. The owner must select a Docker-capable host with
HTTPS ingress and persistent storage, then configure `OPENAI_API_KEY`,
`VIDEO_TEAM_PASSWORD`, `VIDEO_PUBLIC_ORIGIN` and the documented optional settings
through that host's secrets/configuration controls. Never put the real key in
chat, Git, the frontend or an app ZIP.

This initial service shares projects, default language and owner API usage
across the trusted team. It does not implement individual accounts, tenants,
in-app logout or login rate limiting. Use the host's access controls and provider
project spending controls. Run one replica, keep port 8000 private behind HTTPS,
and back up the entire persistent disk.

Before rollout: rerun browser checks and build the Docker image on a capable
host; inspect required PR checks/reviews; deploy only to the chosen host; verify
restart persistence and HTTPS access; then authorize a bounded real API check.
The current request authorizes preparing this PR, not merging it into main.
