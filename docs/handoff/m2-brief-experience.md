# M2 implementation handoff

- **Task:** Implement the committed M2 handoff: task-local Brand & task inputs, separate draft persistence, reviewed claims, explicit Apply and bounded optional assistance.
- **Author/date/environment:** Codex, 2026-10-17, managed Linux cloud workspace `/workspace/586-project`.
- **Repository/branch:** `Frankwu899/586-project`, `feat/workspace/m2-brief-experience`.
- **Prepared baseline:** `0c54231db2cd778797e7ec0bc555188f7eda4ed7`. Its committed handoff and prerequisite ancestry are preserved. Initial working tree was clean.
- **Prerequisite:** PR [#3](https://github.com/Frankwu899/586-project/pull/3) was rechecked before implementation and publication: open, draft, unmerged; head `da95ad3325a04b3b9f01cc7cb02a03af353208b5`, base main `a456329e4fe8cab76669c8c8254cfed8ce11bbcb`. Explicit fetch and `git merge-base --is-ancestor` confirmed both prerequisite and prepared branch ancestry.
- **Implementation commit:** `6d73254bb45deebf93a9030be9d86b0ca53d3865` (this report-only commit follows it).
- **Remote synchronization/PR:** Implementation SHA `6d73254bb45deebf93a9030be9d86b0ca53d3865` was pushed and verified with `git ls-remote`. Draft [PR #4](https://github.com/Frankwu899/586-project/pull/4) is open/unmerged against `feat/video-analysis/bilingual-provider-contracts`. The final report-only branch tip is recorded in the delivery response and PR head; no history was rewritten.
- **Scope authority:** All six numbered M2 handoff documents, repository instructions/current docs, canonical implementation, and `docs/video-anatomy-handoff/docs/blueprint.html` were read. `PROJECT_CONTEXT.md` was not available and was not claimed as read.

## Result and important files

The former required form is now a warm paper/rust/serif Editorial Studio: editable information summaries, one selected question, optional notes/details, and a compact reference summary. Incomplete input persists without fabricating a formal brief or interrupting reference recognition. English, Chinese and mixed text stays in its source language. No audience, platform, goal, duration or treatment default is inserted.

The draft and applied snapshot have separate lifecycles. Apply requires brand/company, product, audience, one platform, one goal, positive duration and at least one confirmed claim. Review displays included claims and retained excluded alternatives. Claim wording/qualification changes clear permission; confirmation means permission to use the wording, not verification. Pending structured edits block new creative generation, refinement, approval and production on both client and server. Notes and unaccepted proposals alone do not block them. Existing reference, direction selection/refinement/approval, production and export workflows remain available under their existing revision rules.

| Area | Main files and behavior |
|---|---|
| Canonical contracts | `backend/app/models.py`, `m2_assistance_models.py`, `scripts/export_contracts.py`, `frontend/scripts/generate-contracts.mjs`; generated v0.5 schemas, examples and TypeScript |
| Draft/Apply persistence | `m2_domain.py`, `m2_storage.py`, `storage.py`; independent SQLite `m2_drafts` table, optimistic draft versions, immediate transactions, no-op/retry/rollback semantics |
| Migration | `m2_migration.py`, `contract_migration.py`, `frame_migration.py`; historical-schema validation and exact original JSON/hash archives |
| Integration | `service.py`, `api.py`, `workflow_errors.py`; independent editor requests, atomic new-creative-work gates, unchanged job completion stale guards |
| Providers | `providers/m2.py`, `providers/config.py`, `adapters.py`, `providers/creative.py`, `sample.py`, `.env.example`; separate assistance boundary and exact applied qualifiers/support/restrictions in creative context |
| Frontend | `BriefEditor.tsx`, `M2Proposals.tsx`, `m2DraftSession.ts`, `App.tsx`, `Directions.tsx`, `Production.tsx`, `api.ts`, `styles.css`; serialized/coalesced autosave, separate editor status, reviewed batch adoption and explicit historical exports |
| Verification/docs | `tests/test_m2_*.py`, existing migration/workflow/API fixtures, frontend unit/browser suites, this report, setup/interface/architecture/decision docs |

Typing remains possible during assistance and reference jobs. A delayed draft acknowledgement cannot overwrite newer text. Task navigation flushes again after asynchronous loading so edits typed during a switch are saved. A delayed Apply response cannot reactivate another task. Save conflicts/errors preserve local input with retry/reload choices. Before-unload protection is implemented for unsaved local work.

## Final M10 contract and migration mapping

| Handoff register | Final implementation |
|---|---|
| M2-C01 | `M2Fields`, `M2Claim`, `M2Draft`, `M2DraftUpdate`; independent `draft_version`, not `task.version`; one draft per existing task/database |
| M2-C02 | `M2AssistanceRequest`, `M2AssistanceResponse`, `M2Candidate`, `M2ProposedClaim`, `M2AdoptRequest`; proposals never write task/applied state or grant confirmation |
| M2-C03 | Required ordered `BrandTaskBrief.claim_details`; `selling_points` must be its exact statement projection; stable IDs, support, HTTP(S) URLs, qualification and `user_confirmed` / `legacy_unrecorded` origin |
| M2-C04 | `M2ApplyRequest`, `M2ApplyResult`, `M2DiscardRequest`; atomic version/reference validation, complete provider payload comparison, checkpoint, append/invalidation only when changed, exact retry idempotency |
| M2-C05 | Admission gates inside the task transaction; actionable M2 errors; creative HTTP input refs accept null to reach the missing-input explanation, while exact current refs remain required before creative work starts |
| M2-C06 | Protocol/package 0.5.0; `v0.5.task-state`, `v0.5.analysis`, `v0.5.m2` schemas; current v0.5 examples; generated frontend types from a canonical bundle containing TaskState and independent endpoints |

`M2Fields` contains nullable `brand_company`, `product`, `target_audience`, `platform`, `communication_goal`, `target_duration_seconds`, `available_footage`, `presenters`, `locations`, `tone`, `production_limits`, plus `approved_messages` and `prohibited_claims` lists. Null/blank optional fields remain unspecified; explicit “none available” remains text. Duration rejects booleans, strings, nonpositive and nonfinite values. `M2Claim` contains `claim_id`, `statement`, `supporting_notes`, `source_urls`, `qualification`, `confirmed_for_use`.

`M2Draft` contains `task_id`, `draft_version`, `based_on_brief`, `fields`, `claims`, `source_notes`, `reviewed_input_checkpoint`, server-derived `has_pending_inputs`, `legacy_review_required`, `missing_fields`, and `updated_at`. The checkpoint includes excluded rows so retaining an unconfirmed alternative after review does not permanently block work. Notes are excluded from its structured-input digest.

All new routes are under `/api/tasks/{task_id}`:

| Route | Request → response |
|---|---|
| `GET /m2/draft` | Read/lazily seed → `M2Draft` |
| `POST /m2/draft` | `{expected_draft_version, fields, claims, source_notes}` → `M2Draft` |
| `POST /m2/apply` | `{expected_draft_version, expected_version, based_on_brief}` → `{changed, draft, task}` |
| `POST /m2/discard` | `{expected_draft_version}` → restored/cleared `M2Draft` |
| `POST /m2/assist` | `{draft_version, request_id, mode, requested_field?}` → `{request_id, source_draft_version, provider_mode, candidates, unresolved_notes}` |
| `POST /m2/adopt` | `{source_draft_version, request_id, candidates}` → one atomic `M2Draft` update |

Candidates contain `candidate_id`, allowlisted `target`, typed `value`, `origin` and extraction `source_excerpt`. Extraction uses saved notes; suggestions are limited to audience/goal and explicitly labeled. Selected proposals may be edited locally and adopted together, then still require review/Apply. Unsupported fields, unsafe URLs, fabricated excerpts, permission metadata and stale batches are rejected. Real assistance uses existing bounded OpenAI transport with `VIDEO_M2_PROVIDER` and `OPENAI_M2_MODEL`; serialized context is capped at 64,000 UTF-8 bytes. Extracted claim excerpts must cover a complete source line and preserve its qualified assertion, preventing the tested same-line qualification/negation truncations. This is deliberately conservative, not universal semantic verification. Fake assistance exists only through test injection; failures never substitute sample content.

The old `/brief` endpoint requires explicit confirmed metadata, rejects bypass of pending edits and uses the same no-op/revision transaction. An identical compatibility save also retains excluded claim rows, ordering and source notes. `WorkflowError` moved to a small shared module to avoid circular imports. No processing-job enum, M7 content shape, global profile service, reference-frame unit or storyboard-second unit changed.

Migration validates archived v0.4 data, archives exact source bytes/hash transactionally, adds deterministic claim IDs with `legacy_unrecorded`, and increments only the task concurrency version. Brief/artifact IDs and revisions, analysis originals/corrections, evidence/frame clocks, reviews, approvals, outputs and their currentness remain intact. A separate review gate prevents new creative actions until the user confirms and applies; only that changed Apply appends/invalidate. Earlier migration paths now end at v0.5 while retaining their existing timing behavior. Valid long legacy input is preserved rather than truncated. Historical v0.1–v0.4 schemas/examples and the prepared M2 documents were not edited.

## Verification: observed outcomes

All tests below used authored synthetic data, fake adapters or mocked provider transports. Real FFmpeg media tests ran; live model quality did not.

| Command/check | Actual outcome |
|---|---|
| `bash scripts/verify.sh` (final complete run) | Exit 0: **428 Python tests**, **10 frontend unit tests**, **11 default browser tests + 4 provider browser tests**; one existing Starlette/httpx deprecation warning |
| `.venv/bin/python -m pip check` | Passed, no broken requirements |
| `.venv/bin/python scripts/export_contracts.py --check` | Passed, canonical schemas match |
| `.venv/bin/python -m ruff check backend tests scripts` | Passed |
| `npm --prefix frontend run contracts:check` | Passed, generated TypeScript matches |
| `npm --prefix frontend run test:unit` | 10 passed: 5 existing timing + 5 independent-draft tests |
| `npm --prefix frontend run typecheck`, `run lint`, `run build` | All passed |
| `npm --prefix frontend run test:e2e`, `run test:e2e:providers` | 11 and 4 passed in the final script; existing video/correction/approval assertions retained |
| `.venv/bin/python -m pytest -q tests/test_m2_assistance.py` | 47 passed |
| `.venv/bin/python -m pytest -q tests/test_m2_api.py` | 5 passed: concurrent assistance/autosave and safe provider error cases |
| `.venv/bin/python -m pytest -q tests/test_m2_storage.py tests/test_m2_workflow.py tests/test_api.py` | 59 passed after compatibility no-op preservation fix |
| `.venv/bin/python -m pytest -q tests/test_frame_migration.py tests/test_migration.py tests/test_visual_contracts.py` | 70 passed after current fixture/migration expectation updates |
| `npm --prefix frontend run test:e2e -- --grep 'switching tasks\|delayed Apply'` | 2 passed after task-navigation race regressions |
| Final focused question-copy/browser rerun | `npm --prefix frontend run test:e2e -- --grep 'empty and partial'`: 1 passed (5.7s); lint, typecheck and build passed again |
| `git diff --check` | Passed |
| Historical artifacts/prepared handoff diff against prerequisite/prepared baseline | Empty; retained files unchanged |
| Independent temporary-DB failure probe | Passed: raised after formal task SQL update but before draft checkpoint write; both persisted task and draft exactly rolled back. Additional read-only verification, not counted as a committed test |
| `.venv/bin/python scripts/live_validate.py` | **not_run**: default-off harness requires explicit opt-in; no live API call or paid spend |

The first broad Python run during implementation reported **404 passed / 6 failed** while new fixtures and migration expectations were being integrated. Failures were fixed, the affected 70 cases rerun, and both later complete workflows passed (427 before the final added regression, then 428). Early shell dependency/loopback restrictions and a TestClient run under default network isolation were resolved using permitted network/loopback access; a blocked run was stopped, not counted as passing. Initial browser harness focus/accessible-name assumptions were corrected without removing product assertions. The final question copy clarification and stronger question/control assertions were verified separately after the complete script. No test was disabled.

Complete-run local log: `/tmp/m2-verify-final.log`. Browser screenshot source directory: `.local-data/m2-ui-evidence/`. These logs/runtime directories are local and ignored; the curated evidence below is committed.

## Acceptance coverage and limits

| IDs | Evidence and status |
|---|---|
| AC-01, 02, 05, 06 | Browser empty/partial/no-default/decide-later/reopen/Apply scenarios; storage/API restart and placeholder rejection; passed |
| AC-03 | True in-flight recognition + autosave integration passes. Browser holds the completed processing response and verifies editing/restoration independence; it does not substitute for the backend in-flight test |
| AC-04, 17, 18 | Direct API missing/pending gates at atomic admission, notes-only independence, browser pending-output preservation; passed |
| AC-07, 08 | English/Chinese/mixed deterministic extraction; exact excerpts, current/proposed replacements, local row edits/selection/dismissal and one-batch draft adoption; passed |
| AC-09, 10 | Real concurrent HTTP draft change, stale response/batch rejection, mocked timeout/malformed/unsupported/untraceable output, safe retry/manual UI; passed offline |
| AC-11, 12 | Zero-confirmation rejection, exact included/excluded projection, server/client permission reset on statement/qualification edits; passed |
| AC-13 | Exact qualified claim, supporting notes and prohibition asserted in fake M6/M7 context and export; browser applied metadata inspection; passed |
| AC-14 | Browser retains/excludes manually supplied stronger “all day” alternative while confirmed “up to 6 hours” remains. Agent screenshot/content inspection found no silent strengthening. Universal conflict detection and independent human source QA are not claimed |
| AC-15, 16 | Transaction no-op, every optional provider field/claim support/URL equality, changed Apply invalidation with preserved history; passed |
| AC-19, 20 | True in-flight creative races: changed Apply rejects old result; separate draft edits permit completion on original applied revision while new work remains gated; passed |
| AC-21, 22 | Serialized delayed-save unit/browser checks, optimistic stale rejection, concurrent duplicate Apply and transaction rollback; passed |
| AC-23, 24 | Applied/new discard, failed-save text retention/retry, flush before creative actions/task changes, delayed task-response isolation; passed. Native browser before-unload dialog not directly exercised |
| AC-25, 26 | Archived v0.4 migration with histories, failure rollback, honest legacy review, compatibility validation/no-op/pending gates; passed |
| AC-27, 28 | Full manual sample M2 → reference confirmation → two directions → explicit approval → M7/export, then pending/changed inputs, historical output and regenerate/reapprove; passed |
| UX-01, 02 | Actual agent-inspected warm editorial screens; automated no horizontal overflow at 1440/1024/390/320. Human owner visual acceptance remains pending |
| UX-03 | Keyboard activation, text entry, disclosure, confirmation, review/Apply, proposal selection/adoption and visible focus tested. Tests use targeted focus plus keys, with Tab/Shift-Tab checks; not a full sequential Tab-only audit |
| UX-04 | Labeled controls, field error associations and focus assertions; contrast measured: ink/paper 12.22, muted/paper 4.59, muted/surface 4.92, white/rust 5.92, control-border/surface 3.98, rust/paper 5.40. No independent screen-reader audit |
| UX-05, 06 | Reduced-motion browser run; empty/partial/saving/saved/failure/review/applied/pending/stale copy asserted; passed |
| UX-07, 08 | Explicit fake/suggestion/permission copy, manual route with optional notes, reference-first access, no treatment requirement; passed offline |

Screenshots were actually viewed by Codex agents, including the main implementer. This is agent visual inspection, not a human signoff or a claim that DOM tests alone establish visual/accessibility acceptance. No outstanding known product failure was found in final review.

## Committed UI evidence

All images are actual Playwright Chromium captures of synthetic fixtures; none is a mockup or a live-provider result.

| State | Evidence |
|---|---|
| Empty desktop/narrow | [1440 input area](assets/m2/empty-inputs-1440.png), [390 input area](assets/m2/empty-inputs-390.png) |
| Partial bilingual draft | [Desktop](assets/m2/partial-1440.png) |
| Review, exact qualification and excluded alternative | [Desktop](assets/m2/review-inputs-1440.png) |
| Keyboard review/focus | [390](assets/m2/review-inputs-keyboard-390.png) |
| Applied inputs | [Desktop](assets/m2/applied-1440.png) |
| Current/proposed replacement | [Proposal details](assets/m2/proposal-details-1440.png) |
| Recoverable save failure | [390](assets/m2/save-error-390.png) |
| Stale assistance | [390](assets/m2/stale-proposal-390.png) |

Additional full-page empty captures at 1440/1024/390/320, applied keyboard390 and proposal1440 remain in `.local-data/m2-ui-evidence/`. Reproduce by running the browser commands above; `frontend/e2e/m2.spec.ts` and `providers.spec.ts` specify viewports and capture points.

## Manual demo

1. Follow `README_SETUP.md`; start the backend and frontend. No key is needed for the synthetic demo. Create a new task and observe empty inputs and available reference upload.
2. Enter only brand/product, wait for “Draft saved,” then refresh. No applied brief exists. Use “Decide later” for an unknown task answer; it remains unset.
3. Enter a selling point such as the fictional “Keeps drinks warm for up to 6 hours,” add “Indoor test only” and a supplied support note, then explicitly confirm its wording. Add an unconfirmed stronger alternative to see it retained but excluded. Enter audience, one platform, goal and positive duration.
4. Review inputs, inspect included/excluded wording and click **Apply inputs**. Repeating Apply preserves the formal revision. Editing a qualification clears its permission.
5. Load the clearly labeled synthetic reference, analyze it, review/correct observations and use the reviewed analysis. Loading sample media after partial input preserves those inputs; it only seeds fictional inputs when the editor is otherwise blank.
6. Generate two directions, choose/refine one, explicitly approve it, then generate and export the production creative brief and storyboard. M2 inputs and M7 output remain separately labeled.
7. Edit an optional production restriction. The draft saves while existing outputs/history remain; new creative actions are blocked. Discard restores applied input, or review/Apply once to invalidate dependents. Historical exports are explicitly labeled; regenerate/reapprove for current outputs.
8. Optional offline assistance review uses the test-only server exercised by `npm --prefix frontend run test:e2e:providers`: paste literal bilingual fixture notes, extract, compare current/proposed values, select/edit candidates, then **Use selected details** once. This is not live model quality. In ordinary unconfigured mode, failure leaves manual input available.

## Environment, synchronization and remaining review

The implementation and this report are separate commits. At handoff, all intended changes are committed and the branch is pushed; no unrelated local modifications were found. Final remote tip and clean working tree were checked after pushing the report. No merge conflicts or ancestry divergence were found.

- Runtimes actually used: Python 3.12.14, Node 24.19.0, npm 11.9.0; FastAPI 0.141.1, Pydantic 2.13.4, pytest 8.4.2; Playwright 1.56.1, FFmpeg 7.1.5; repository-locked frontend and Chromium dependencies.
- Relevant configuration names only: `VIDEO_ANATOMY_DATA_DIR`, `VIDEO_M2_PROVIDER`, `OPENAI_M2_MODEL`, `OPENAI_API_KEY`, existing vision/transcription/creative settings, `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH`, `RUN_LIVE_MODEL_TESTS`, `LIVE_TEST_MAX_COST_USD`. No credential is committed or included in evidence.
- Source transfers through this branch. SQLite, media, caches and local evidence stay under ignored `.local-data/`; transfer a backup of the complete data directory privately if needed. No runtime database, uploaded media, dependency directory or secret is part of the PR.
- Paid/live API work: **not_run**, no paid calls/spend. No authorized positive budget, live opt-in or supplied permitted evaluation set. Offline results establish contracts/workflow, not extraction/recognition/creative quality.
- Remaining review: human visual/keyboard/accessibility acceptance and optional separately authorized live linguistic/content evaluation. M2 assistance is bounded and conservative; universal semantic conflict detection is out of scope.
- No merge or deployment performed. Continue on `feat/workspace/m2-brief-experience`; read this report, `docs/interfaces.md`, `docs/decisions/m2-v0.5.md` and the original M2 handoff first. Draft PR targets the still-unmerged prerequisite branch; retarget only after separately authorized integration changes.
