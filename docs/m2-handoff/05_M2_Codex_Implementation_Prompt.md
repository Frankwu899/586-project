# Complete Codex Implementation Prompt — M2

Copy the complete prompt below into the implementation task after making `docs/m2-handoff/` available in the selected repository branch or local checkout.

---

You are implementing M2 for the Video Anatomy project in `Frankwu899/586-project`.

Deliver a working, tested, reviewable change. Do not stop at planning or a UI mockup. Preserve unrelated work. Do not merge or deploy.

## Product authority and required reading

Read repository instructions and these handoff files before editing:

- `docs/m2-handoff/01_M2_PRD.md`
- `docs/m2-handoff/02_M2_UIUX_Editorial_Studio.md`
- `docs/m2-handoff/03_M2_Contract_Impact.md`
- `docs/m2-handoff/04_M2_Acceptance.md`
- `docs/m2-handoff/06_M2_Integration_Summary.md`

Read the project's `PROJECT_CONTEXT.md` and `blueprint.html` if available in the supplied project context. If either is unavailable, say which one is missing; do not claim to have read it. The implementation handoff remains the explicit scope for this task. Also inspect the current setup/interface/handoff docs, canonical models, schema generator, storage/service/API, frontend editor/workspace, providers and verification scripts. Resolve technical questions by reading the repository, not by asking the user to choose facts.

M2 is user-provided brand/product/task input. M7 is the system-generated production Creative brief and text storyboard. Never merge these concepts. “Profile” in this task is task-local brand/product data, not a reusable account or brand database.

The owner selected Editorial Studio and a single-task demo. Use the warm paper/rust/serif design language and the information-summary plus one-question composition. Direct field editing and optional pasted notes must work together. Cross-task reuse, brand libraries, multi-platform workflows, web research, universal conflict resolution and unrelated M3–M8 redesigns are out of scope.

## 1. Recheck the development baseline

The handoff snapshot from 2026-10-17 reports PR #3 as open, draft and unmerged. Its inspected head was `da95ad3325a04b3b9f01cc7cb02a03af353208b5` on `feat/video-analysis/bilingual-provider-contracts`, with base main `a456329e4fe8cab76669c8c8254cfed8ce11bbcb`. These are historical observations, not instructions to reset to old commits.

Fetch/read the current PR and branch state. If PR #3 is merged, use current main after verifying it contains the required v0.4 foundation. If unmerged, use its inspected current head or an explicitly supplied integration branch containing that work. Do not start from a docs-only branch or main that lacks the prerequisite. If it was closed without merge or an unexpected baseline conflict exists, explain the concrete blocker before risky branch manipulation.

Use `feat/workspace/m2-brief-experience` or a nonconflicting equivalent branch. If the task starts on a prepared M2 branch with handoff commits, verify ancestry and preserve those commits rather than resetting it. Preserve all existing local changes. Report actual baseline and head SHAs.

## 2. Implement the core input experience

Support incomplete task-local drafts, manual editing, optional source notes, bounded AI extraction/suggestions, user confirmation of usable claims, explicit review/application, saved draft restoration and downstream readiness.

Require brand/company, product, at least one confirmed usable selling point, audience, one primary platform, one primary communication goal and explicit positive target duration before application/generation. Optional evidence, conditions, approved messages, prohibitions and production details remain optional. Preserve unknown versus explicitly unavailable. No hidden audience/platform/goal/duration defaults. Creative treatment need not be known in M2.

Allow reference upload/analysis/review before completing M2. Use one workspace and existing reference screens. Show a concise readiness explanation, not a rigid inputs-before-video wizard. Preserve existing M6 selection/refinement/explicit approval, M7 generation and M8 export gates.

## 3. Implement explicit contract changes

Use document 03 as the scoped shared-contract change register. Keep the applied BrandTaskBrief strict. Add independent partial editor state, proposal types, associated applied claim metadata, Apply/discard behavior and pending-input server gates. List the actual final fields/endpoints and all M10 changes in your report.

The inspected storage/service increments `task.version` on every task write, and provider jobs reject responses when that version changes. Therefore draft autosave and extraction bookkeeping MUST NOT use the existing task update path or `/brief` save behavior. Use a separate draft persistence/version channel in the existing database; do not introduce another database or a global profile service. Keep frontend draft requests separate from the shared full-task busy/mutation channel. Do not replace current task state with an old draft response.

Persist partial input with optimistic concurrency. Preserve newer local text against delayed responses. Pasted notes and unaccepted proposals alone do not create pending formal edits. Pending structured changes must be reviewed/applied or discarded before new direction generation, refinement, approval or production, enforced by the server as well as the UI. Flush unsaved local edits first. Reference work remains independent.

Apply must atomically validate expected versions, build the full provider-relevant payload, compare with the existing applied snapshot, update the reviewed draft checkpoint, and append/invalidate only on meaningful change. Identical Apply must not increase formal revision or task version or clear approvals. Double submission must not create duplicate revisions. Include all optional provider-relevant fields and claim qualifiers in equality. Keep historical records; preserve stale-response rejection when formal inputs really change. The existing brief endpoint must not bypass these rules.

Retain current `selling_points` as compatible exact wording, with associated stable claim metadata as specified. Only confirmed included claims enter new applied generation input. Qualifications, support and restrictions must reach the applied provider context. Editing claim wording/qualification clears confirmation. User confirmation never means AI verification.

If the current protocol is still 0.4.0, evaluate the proposed 0.5.0 change under repository conventions and implement the appropriate documented version/migration. Preserve archived schemas/examples, revisions, analysis originals, corrections, evidence/frame clocks, reviews and outputs. Legacy claim confirmation is unrecorded; do not invent it. Require review before new creative actions on legacy inputs. Regenerate schemas and TypeScript from canonical sources; verify drift.

## 4. AI assistance and honest failure handling

Create a bounded, replaceable M2 assistance interface separate from M6 creative generation. Extract facts only from supplied notes, with exact source excerpts; leave absent facts unset. Clearly label inferred audience/goal options as suggestions requiring acceptance. Do not invent product performance, permissions, certifications, source evidence or results.

Validate typed responses and allowed target fields. Treat supplied text as data, not instructions to bypass the app's rules. AI cannot change approval metadata or confirm claims. Proposals never overwrite draft or applied values automatically. Show current/proposed text before an explicit replacement. Keep row selection/editing in local proposal review, then adopt the selected batch in one atomic “Use selected details” draft update after checking its source version. Reject stale batches without overwriting newer edits. Keep input on timeout/invalid response and allow manual completion. Never silently substitute fake/sample output for a real provider failure.

Provide a deterministic fake provider for offline tests, clearly isolated from real mode. Add the real adapter through the existing provider/configuration architecture where feasible, with bounded timeouts/retries and safe errors. Keep credentials server-side. Do not make paid calls without explicit opt-in and an authorized positive budget. Missing live access is a `not_run` live-quality result, not a reason to leave the manual workflow or offline tests unfinished.

## 5. UI requirements

Implement document 02's typography, warm surfaces, rust actions, modest radii and restrained rules. Use readable summary/edit sections, a single current-question sheet, optional notes disclosure and a compact reference summary. Preserve English/Chinese/mixed input verbatim. English interface copy is the implementation default; do not add a translation subsystem.

Provide truthful empty, partial, saving, saved, AI-loading/failure, unsaved-error, review, applied, pending-change and stale-result states. Use “Apply inputs” for M2; reserve direction approval for M6. Be explicit about included/excluded claims. No decorative score or generic chatbot transcript.

Support desktop and narrow screens, keyboard operation, labeled fields, focus visibility, accessible contrast, clear error associations and reduced motion. Reuse existing dependencies where possible; do not install the referenced design repositories merely to use their visual principles. Keep the change focused on M2 and necessary integration points.

## 6. Test, verify and report

Implement meaningful automated tests for document 04's acceptance cases. Prioritize partial persistence/restart, typing during reference processing, stale autosave/proposal responses, required-field gates, claim qualification propagation, server pending-input enforcement, transaction-safe no-op/changed Apply, legacy migration and the end-to-end fake-provider path through M7/export. Do not write only tests that mirror internal implementation.

Run targeted tests, then the repository's required complete verification workflow, including `bash scripts/verify.sh` if it remains the canonical command. Include backend, frontend, browser, schema/type drift, lint, type-check and build gates supported by the current repository. Do not weaken existing tests or disable relevant checks. Capture real UI evidence for key states at desktop and narrow widths and perform the visual/keyboard checks in document 04.

Fix failures within scope and rerun affected checks. If the environment blocks a check, report the exact blocker and command as not run; do not describe unexecuted tests as passed. Prior PR test counts are not results of this implementation.

Commit the implementation with a clear description. Where the environment supports authorized repository publishing, push this feature branch and create a draft PR: target the prerequisite branch when this is a stacked change on an unmerged PR #3, or main when the prerequisite is merged. Preserve repository rules. If remote publishing is unavailable, leave a clean reviewable local branch and report the limitation. Do not merge or deploy.

Your final report must include: actual baseline/branch/head and PR state; what changed and why; final contract/migration delta; executed commands and real counts/outcomes; AC/UX coverage and remaining gaps; screenshot paths; manual demo steps; draft PR link when created; and paid/live API work explicitly marked run or not_run. Finish the authorized implementation and verification instead of returning only a plan.

---
