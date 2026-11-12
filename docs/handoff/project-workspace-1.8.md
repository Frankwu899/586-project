# Project workspace 1.8 implementation handoff

- **Task:** Implement the owner's reviewed Video Anatomy 1.8 project baseline.
- **Author/date:** Codex implementation team for Frank / Yuqing Wu; November 12, 2026 (UTC).
- **Execution environment:** Managed Codex Cloud, Linux; not the owner's Mac.
- **Repository:** `Frankwu899/586-project`.
- **Branch:** `feat/integration/video-anatomy-1-8`.
- **Starting commit:** `462bdd67b16a0883c9fd1a04e6778dd77ca4a566`.
- **Final commit / pushed SHA / PR:** Recorded by the integration owner in the final delivery response. This document does not imply a push, merge or deployment.
- **Product authority:** The current owner baseline and subsequent explicit “execute implementation” instruction. Historical single-reference/form-intake restrictions are superseded.

## Delivered behavior and source map

The default frontend opens a project-card dashboard and six destinations:
Overview, Resources, Discover, Analysis, Content plan and Production. It adds
persistent conversational context, explicit brief adoption, project-owned resource
files, multiple-reference selections, comparative analysis, optional series and
standalone videos, and four-document production packs. The current local stack,
user API-key connection and historical task APIs are retained.

The implemented architecture, API matrix, storage details, parser limits,
parallel ownership and verification commands are in
[Project workspace 1.8](../project-workspace-1.8.md). Read that document alongside
the code before making feature or readiness claims.

| Area | Primary changes |
| --- | --- |
| Domain/storage | `backend/app/project_workspace/models.py`, `store.py`, `migration.py`; project SQLite, local ownership, optimistic versions, duplication/Trash, non-destructive legacy import. |
| Conversation | `conversation.py`; source-grounded proposals, focused clarification/research, explicit adoption, no-op brief Apply and failure retention. |
| Resources | `resources.py`; bounded documents/media intake, local originals, extraction/correction history, previews, missing-file recovery. |
| Analysis | `analysis.py`, affected provider recognition caching; reusable per-source evidence, chunk retries, timing corrections and comparison. |
| Content/production | `planning.py`, `exports.py`; runtime instruction loading, exact provenance/approval, manual/generated directions and packs, document exports. |
| HTTP integration | `project_workspace/api.py`, legacy app installation and configuration; persisted background status and current credential handling. |
| Frontend | `ProjectApp.tsx`, `frontend/src/project/`; dashboard, six destinations, saved drafts, evidence views and production editing. |
| Contracts/checks | `contracts/v1.8.project.schema.json`, project schema/type scripts, focused backend tests, new project Playwright configuration/suite. |

Discovery is **Reserved — awaiting Frank’s specification.** The page is empty
apart from that status. Only the common completed-local-file import boundary is
reserved; no discovery search, sample results, ranking or downloading is added.
Existing bounded public-context lookup is conversation assistance, not Discovery.

## Preservation and migration

Old task records and files stay intact. Each legacy task imports once into a
project and standalone content item. Auxiliary task-owned tables are archived as
JSON plus a local archive SQLite record, including drafts, Structure history and
handoffs, operations, lifecycle and migration archives. The 1.8 projection does
not invent missing conversations, series, scripts, shot lists or timing.

The old workspace remains available through `?legacy=1`; `/api/tasks` is retained.
The old Structure graph and its detailed workbench are not presented as a newly
integrated graph in the 1.8 Analysis surface. Post-import changes in the legacy
workspace are not automatically synchronized into the independent new project.

Project duplication copies originals and saved work into independent storage,
preserves source approval provenance in a snapshot, and resets active copied
approval/review state. Cache clearing retains originals, paid extraction results,
transcripts/corrections, briefs, document history and exported snapshots. Cache
cleanup is separate from recoverable project Trash.

## Provider, format and quality boundaries

- The project runtime pins applicable LLM tasks to `gpt-6.1-sol`, reads the
  current user-provided key at operation time, and preserves the separate
  timestamped audio engine, normally `whisper-1`. No hosted shared key is added.
- DOCX/PPTX/XLSX/text/CSV/PDF have bounded extraction paths. Scanned PDFs/images
  need optional local OCR tools. Complex spreadsheets expose cached-formula and
  formatting limitations. Legacy DOC/XLS/PPT, RTF, encrypted or unsupported
  formats receive explicit guidance while retaining originals.
- Common video/audio containers are attempted through local FFmpeg validation,
  with measured source timing and suitable video proxies. HDR/10-bit inputs,
  multiple streams and configured resource limits still restrict compatibility.
  Browser playback of standalone audio depends on browser codec support.
- Scene-assisted sampling remains sparse, not exhaustive action/shot/visible-text
  coverage. Speech estimates do not establish exact speech alignment; music/SFX
  extraction is not implemented.
- The application distinguishes user permission to use a claim from independent
  truth verification. Declared generated claims are checked against complete
  approved wording; this does not prove absence of every undeclared semantic
  assertion. Real-content review remains necessary.
- Professional instructions are now loaded by the new generation path with
  recorded digests. Structured validation and mock-provider tests establish
  workflow boundaries, not professional usefulness or advertising effectiveness.
- Production documents are editable text. Generated shots also retain separate
  timing/dialogue/screen-text/sound fields. This is not a visual storyboard-image
  generator, video editor, renderer or social publisher.

## Verification record

The following checks ran in the shared Linux checkout. Backend counts come from
one final full run, not the sum of module-owner results.

| Check | Command / procedure | Integration result |
| --- | --- | --- |
| Project schema/type drift | `python scripts/export_project_contracts.py --check`; `npm --prefix frontend run project-contracts:check` | Passed. |
| Legacy schema/type compatibility | `python scripts/export_contracts.py --check`; `npm --prefix frontend run contracts:check` | Passed. |
| Backend checks | `.venv/bin/python -m pytest -q`; Ruff; `pip check`; `git diff --check` | 865 tests passed in 160.58 seconds; other checks passed. One dependency deprecation warning from Starlette's TestClient. |
| Frontend checks | TypeScript, ESLint, `test:unit`, production build | Passed; 41 unit tests passed. Build emits a nonblocking 507 kB bundle-size advisory. |
| Project browser workflow | `npm --prefix frontend run test:e2e:projects` | 5 passed in Chromium, including production persistence, project lifecycle, immediate-close draft saving, competing tabs and real synthetic-video playback during polling. |
| Preserved legacy browser workflow | `npm --prefix frontend run test:e2e` | 55 passed in Chromium. |
| Injected-provider browser workflow | `npm --prefix frontend run test:e2e:providers` | 4 passed with explicitly injected provider responses. |
| Live provider/account access and real media quality | No live paid calls in implementation tests | Not run. |
| Actual Mac launcher, Keychain, Gatekeeper and installer | Requires the target macOS environment | Not run. |

Browser tests use isolated temporary libraries with API keys unset. Synthetic
media and explicitly injected provider responses must stay labeled as such.
They cannot establish real transcription accuracy, visual recognition quality,
source claims, model availability or professional usefulness.

Review fixes include explicit per-resource recognition retries, preservation of
successful speech chunks, pending-evidence generation guards, assigned-series
dependency tracking, independent editor concurrency/checkpoints, original/proxy
clock handling, missing legacy-original relinking, and isolation of unreadable
project databases. Browser review also corrected legacy CSS interference, a
project action-menu state bug, and citation playback rewinding during polling.

`origin/main` was checked at `462bdd67b16a0883c9fd1a04e6778dd77ca4a566`
before delivery. No merge or deployment was performed.

## Handoff and next checks

Use the current feature branch and inspect the working tree before any follow-up;
several module owners share the same checkout. Root integration owns the final
commit, schema regeneration, full validation, PR metadata and synchronization
record. No main merge or deployment is implied by implementation authorization.

The next acceptance work is representative local use: reopen migrated projects,
test copied/missing media and cache recovery, verify current Sol/transcription
account permissions, measure independently annotated speech/OCR/visual cases,
review creative outputs with marketing users, and validate the launcher on the
owner's Mac. Discovery remains independently reserved for Frank.
