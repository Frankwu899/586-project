# M2 Acceptance Criteria and Verification Plan

Status: tests to implement/run during application implementation. These tests were not run against application code while preparing the handoff. PR #3's reported earlier results are not M2 acceptance.

Use deterministic fake providers and seeded local tasks for required automation. Include at least one new task with no brief, one applied task with approved direction/production, and one legacy v0.4 persisted task. A sample product is test data only: LumaCup travel tumbler, office commuters, TikTok, demonstrate everyday usefulness, 20 seconds, with one explicitly user-confirmed claim. Never use test claims as verified real product facts.

## 1. Behavioral acceptance matrix

| ID | Given / action | Expected observable result | Required level |
|---|---|---|---|
| AC-01 | Open a new task with no inputs | Empty editorial workspace; no invented defaults; reference upload remains accessible | Browser |
| AC-02 | Save only brand and product, restart/reopen the persisted task | Partial input survives; no formal brief is fabricated; missing requirements are named | API/storage + browser |
| AC-03 | Start reference recognition and edit/autosave M2 while it runs | Draft version changes, task version is not changed by autosave; recognition completes without draft-induced stale-result rejection | Integration + browser |
| AC-04 | Input is incomplete; call direction generation directly | Server rejects with actionable missing-input error; draft/reference retained | API |
| AC-05 | Enter “not sure” via the undecided control for audience/goal/duration | The field remains unset; no placeholder passes readiness validation | Unit/API + browser |
| AC-06 | Supply all minimum fields and confirm one claim, then review/apply | Exactly one complete brief revision created; optional blank fields stay unspecified | API + browser |
| AC-07 | Extract from English, Chinese and mixed notes with fixture-supported values | Original text and source excerpts preserved; missing facts not invented; candidates not applied automatically | Adapter + component |
| AC-08 | Receive three proposals including a replacement for a populated field | Current/proposed comparison shown; row selection/dismissal is local; “Use selected details” adopts the selected batch in one draft update; no formal brief change | Component/browser |
| AC-09 | Edit the draft after extraction starts or before using a returned batch | No overwrite; stale batch cannot be adopted; newer text retained and rerun offered | Integration/component |
| AC-10 | Fake provider times out, returns invalid JSON, unsupported fields or invented excerpt | Safe error/manual path; no auto sample fallback; draft and applied brief unchanged | Adapter/API + component |
| AC-11 | Try applying with zero confirmed claims; then confirm one | First attempt rejected; second includes only confirmed claims; excluded rows remain visible in draft | API + browser |
| AC-12 | Edit a confirmed claim's wording or qualification | Confirmation cleared; old applied revision unchanged until explicit Apply | Unit/API + browser |
| AC-13 | Apply “up to 6 hours, indoor test” with support and a prohibition | Exact qualifier/support/prohibition arrive in fake M6 and M7 provider context; no unconfirmed claim leaks | Adapter/integration |
| AC-14 | Extract or manually supply conflicting claim alternatives | No silent resolution/strengthening; user can edit or exclude; no promise of universal semantic detection | Browser/manual content check |
| AC-15 | Apply identical reviewed provider-relevant content again | `changed: false`; same formal revision/task version, approvals and outputs remain valid | Transaction/API |
| AC-16 | Change an optional qualification or prohibition and Apply | One new formal revision; affected current approvals/outputs invalidated; old history preserved | Integration |
| AC-17 | Change only a saved draft after producing outputs | Applied revision/output history unchanged; pending indicator visible; direct API generation/refinement/approval/production blocked | API + browser |
| AC-18 | Paste notes or receive a proposal without adopting structured edits | No formal mutation/invalidation; existing ready inputs are not blocked merely by unaccepted text | Unit/API |
| AC-19 | Apply a changed brief while prior creative work is running | Superseded result cannot become current/approved; existing stale-result protection retained | Race integration |
| AC-20 | Make draft changes while creative work against old applied input completes | Completion stays tied to original applied revision; draft not overwritten; pending gate remains | Race integration |
| AC-21 | Two draft saves return out of order; attempt stale Apply | Latest text retained; stale version rejected without partial writes; retry/reload possible | API/component |
| AC-22 | Retry/double-submit the same Apply; inject transaction failure | No duplicate revisions; failed transaction leaves task and checkpoint consistent | Transaction/API |
| AC-23 | Discard edits from applied task; discard from new task | Restore last applied values or clear only input draft; retain reference/task/history | API + browser |
| AC-24 | Save fails and user attempts to continue/leave | Text retained, unsaved state visible, flush/retry required; truthful leave warning where supported | Browser |
| AC-25 | Load/migrate legacy v0.4 task with history | Values/references/history and existing currentness preserved; no fabricated confirmation; review gate on new creative actions; applying newly confirmed metadata creates the next revision; migration failure rolls back | Migration/integration |
| AC-26 | Call old `/brief` route with payload bypassing new rules | Equivalent validation/no-op/revision behavior; no confirmation bypass | API |
| AC-27 | Complete manual M2 → confirmed reference → two directions → explicit approval → M7 → export using fake providers | Existing exact-revision gates work; M2/M7 labels distinct; exported current outputs use confirmed input | Browser end-to-end |
| AC-28 | Edit brief after AC-27 and reapply | Old current export is unavailable or explicitly historical under existing rules; regenerate/reapprove path works | Browser end-to-end |

## 2. UI acceptance

| ID | Check | Pass condition |
|---|---|---|
| UX-01 | Editorial identity | Warm paper, serif headings, rust primary action, modest rules/radii, readable summaries and one question; no generic dashboard/chat replacement |
| UX-02 | Layout | Desktop 1440/1024 and narrow 390/320 widths have no horizontal page overflow, hidden primary actions or overlapping text |
| UX-03 | Keyboard | Complete manual input, disclosure, proposal acceptance, claim confirmation and Apply without pointer; visible focus, logical order |
| UX-04 | Accessibility | Labeled controls; errors associated with fields; status announcements restrained; normal text contrast ≥4.5:1; meaningful controls/focus ≥3:1 |
| UX-05 | Reduced motion | State remains clear with reduced motion; no required animated sequence |
| UX-06 | State copy | Empty, partial, saving, saved, AI failure, unsaved error, review, applied and stale states are distinguishable without color alone |
| UX-07 | Honest AI | No “verified” label for user claims, no fake confidence score, no unmarked suggestions, no real-failure sample substitution |
| UX-08 | Input freedom | Notes entry is optional; direct editing works; reference can come first; users need not specify creative treatment |

Automate browser state and structural accessibility assertions where the repository supports them. Capture actual screenshots and perform a concise human visual/keyboard review for judgment-based layout criteria. Do not report a DOM-only test or screenshot capture as a complete visual acceptance pass.

## 3. Required commands and reporting

Inspect the current `README_SETUP.md`, dependency scripts and `scripts/verify.sh`; use their actual commands. At the inspected baseline the repository uses Python/backend tests, frontend tests/browser checks, schema/type generation/drift checks, lint, type-check and build. Extend those suites; do not invent passing command names.

Run focused tests after each meaningful change, then the repository's required complete verification script before handoff. Do not disable tests or weaken existing video/frame/correction/approval assertions to obtain green results. Avoid paid calls in default tests.

The final implementation report must include:

1. Actual baseline/branch/head and prerequisite PR state.
2. Changed behavior, important files and contract/migration mapping.
3. Each executed command with outcome and actual test counts; failures and reruns clearly distinguished.
4. AC/UX IDs covered automatically, manually inspected, failed or not run.
5. Actual screenshot/artifact locations and reproduction steps.
6. Known limitations and what remains unverified.
7. Draft PR link if created; no merge or deployment claim.

Live API quality is a separate opt-in stage requiring available secrets, permitted test material and an explicitly authorized positive spending limit. If those are absent, report `not_run` and complete offline verification. A passing fake-provider test does not establish real extraction, video recognition or creative quality.
