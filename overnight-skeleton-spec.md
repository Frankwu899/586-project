# Video Anatomy — Overnight Skeleton Implementation Mission

Confirmed product decisions: 15 October 2026, America/Los_Angeles.

Suggested repository location: `docs/overnight-skeleton-spec.md`.

This is a self-contained coding mission for the repository `Frankwu899/586-project`. It incorporates the owner's confirmed answers and supersedes the earlier documentation-only milestone for this task. The owner has authorized implementation of the runnable skeleton, its shared data contracts, required development/runtime dependencies, sample data, and automated verification. It does not claim that any of that work is already complete.

The expandable HTML blueprint is optional background for people. This file supplies the implementation requirements. No access to the earlier chat, screenshot, HTML, or an installed grill-me skill is required.

## 1. Outcome and execution instructions

Implement a working foundation that Frank can review in the morning and hand to Andrea after review. Prioritize the video data contract and the working connections between modules. Do not stop after writing a plan, schemas, documentation, or disconnected screens.

The complete workflow must run using explicitly labeled sample analysis and sample creative generation. Real model integration, model accuracy, live platform downloads, and polished UI/UX are later work. A sample workflow must not be described as real recognition or validated creative effectiveness.

Work autonomously through routine technical choices, implementation, relevant tests, fixes, and handoff. Inspect facts available in the repository or environment yourself. Choose small reversible implementation defaults for details not specified here, record them in `docs/decisions/skeleton-v0.2.md` or an existing equivalent, and continue. Do not invent new product capabilities. Do not wait for another interview to resolve naming, directory structure, library choice, or simple layout decisions.

If an external access restriction prevents a required step, preserve completed work, continue independent work, and report the precise blocker and its effect on readiness. Do not repeatedly retry an unchanged failure, bypass access controls, or claim that an unexecuted check passed. Stop when this mission is sufficiently verified or a concrete external blocker prevents further progress; there is no requirement to consume the entire night.

### First inspect the actual checkout

1. Report the actual execution environment, repository remote, current branch, and starting commit. Confirm this is the intended project. Inspect working-tree changes and preserve unrelated work.
2. Read applicable `AGENTS.md` files, `README_SETUP.md` or current README, `docs/project-brief.md`, `docs/architecture.md`, `docs/interfaces.md`, `contracts/analysis.schema.json`, existing examples, and the latest relevant handoff if present.
3. Inspect actual implementation files, manifests, lockfiles, runtimes, media tooling, and available test commands. Do not assume the checkout matches the original starter.
4. If executable application code already establishes a suitable stack, extend it. If the repository is still a documentation starter, use its proposed React/Vite/TypeScript frontend and FastAPI/Python backend with simple persistent local application storage. Record the decision and tested versions before finalizing setup commands. Avoid a framework rewrite or infrastructure expansion.
5. Use the task branch supplied by the environment or create an isolated task branch if appropriate. Do not work directly on shared `main`. Do not switch away from or discard unrelated uncommitted changes.

The earlier starter may still prohibit claiming that a runnable skeleton exists, describe the stack as a candidate, or define only contract v0.1. Those are accurate historical statements, not a prohibition on this newly authorized task. Update relevant scope and interface documents to describe the resulting implementation honestly. Preserve unrelated instructions, security practices, and review safeguards.

## 2. Confirmed product behavior

- First scenario: a brand or agency prepares a new product-focused marketing video using **one brand/task brief and one reference video**.
- Brand input: brand/company, product, selling points or approved messages, target audience, publishing platform, and communication goal. Also collect target duration and optional available footage, presenters, locations, tone, production limits, and prohibited claims.
- Reference intake: local file upload. Support the formats/codecs actually implemented and tested, with explicit configured limits. Source URLs may be stored as provenance; downloading platform links remains deferred.
- Analysis: timestamped visual and audio observations, organized into broader content sections such as Hook, product presentation, demonstration/result, and CTA. Evidence events may overlap.
- Review: emphasize readable content sections with expandable visual/audio observations. Video editing and timestamp editing are unavailable. Users can correct recognized text, visual descriptions, and section roles. Preserve the original result and save corrections as a new revision.
- Confirmation: a single **Use this reviewed analysis** action confirms the current analysis for creative use. Optional corrections happen before confirmation. Confirmation does not claim every observation is accurate.
- Creative choice: offer **two distinct directions**. Users can edit the core message, Hook, narrative, and CTA. They must explicitly approve a direction before generating the production outputs.
- Free-text input: users can write instructions to refine a direction, in addition to direct field editing. Store the text and the exact draft it targets; pass it into the generation interface. A generated revision is a draft requiring approval.
- Outputs: an editable **production creative brief** and an editable **text storyboard** with new-video time, visuals, dialogue, on-screen text, sound, and CTA where applicable.
- The production creative brief is an output; the brand/task brief is an input. Keep their names and purposes distinct.
- Public views, likes, and comments are optional dated source context. Missing values are unknown. Do not fabricate retention, click, conversion, causal effectiveness, or confidence percentages.
- Analysis and creative-brief page visual design will be discussed later. Build a plain, usable interface that proves the behavior; avoid spending the task on styling or treating its layout as final.
- The product is initially a single-user, team-run Web demonstration. Cloud coding does not authorize public deployment.

## 3. Required feature modules

### M1 — Start, save, and reopen a task

Create a task; keep its records separate from other tasks; save/reopen progress after page refresh and backend restart; show the next usable action. Use server-side persistent storage behind a small storage interface. Frontend-only state is insufficient for the handoff.

**Output:** a persistent task connecting its brief, video, analysis revisions, selected direction, and production outputs.

### M2 — Enter and revise the brand/task brief

Provide the confirmed input fields, required-field validation, optional production constraints, and a versioned save operation. Store target duration as a positive value in seconds. Defaults, file limits, and supported language/format assumptions must be explicit and configurable rather than presented as user-confirmed facts.

**Output:** a brief revision that generation can consume without reading UI state directly.

### M3 — Upload and inspect a reference video

Validate the file and configured limits; use a server-generated storage identifier; save the media outside tracked source files; measure duration and available properties; serve playable media; expose seek-to-time. Handle unreadable files, missing media, unsupported codecs, and missing audio honestly. Document tested input formats.

**Output:** a validated `VideoAsset` and playback source. A valid upload alone does not mean recognition succeeded.

### M4 — Produce normalized video observations

Provide one documented recognition interface that receives a saved video reference and returns an analysis result in the shared contract. Keep provider-specific transport and parsing behind this interface.

Implement a deterministic sample recognition route for a dedicated synthetic task. Provide an unconfigured real-provider implementation or equivalent explicit error state. Do not send paid model requests or require provider credentials for the baseline. Never silently substitute prepared findings for a real upload.

Represent visual actions, on-screen text, speech, and extensible music/SFX observations. Sample records should exercise these kinds; this does not require real extraction of each category tonight. Report per-category coverage such as not analyzed, analyzed with observations, analyzed with none found, or failed. Missing extraction must not imply silence or absence.

**Output:** a validated original `AnalysisResult`, with honest sample/provider/manual provenance and processing state.

### M5 — Review the analysis and save corrections

Display readable content sections, expandable aligned observations, and source-video playback. Click a timestamp to seek when matching media is available. Allow simultaneous visual/audio events. Keep timing and original media read-only.

Support only the agreed content/role corrections. Enforce edit restrictions in the backend as well as the UI. Preserve the original extraction. Save new content revisions, keep event IDs stable when they refer to the same observation, and record the changes. Use a separate review-confirmation action.

**Output:** a current reviewed analysis revision suitable for creative generation.

### M6 — Compare, prompt, edit, and approve a direction

Use the current brief and reviewed analysis to produce two sample creative directions. Show a message, Hook, narrative, CTA, production implications, evidence references, and a short rationale for each. Explain intended benefits as hypotheses where outcome data is unavailable.

Implement direct edits and a free-text refinement field with an explicit apply action. Save the instruction, target direction/version, input versions, and resulting draft/version. The creative adapter must receive the instruction; merely displaying a textbox without saving or forwarding its content is insufficient.

In sample mode, use a clearly labeled deterministic refinement demonstration. Support at least one documented instruction scenario, such as making a sample direction presenter-free, and make its change visible in the next draft. Preserve arbitrary input as user production notes and explicitly report when the sample implementation has not interpreted it. Do not claim unrestricted language understanding. A later real provider must use the same request/response boundary.

Require explicit direction approval. Selection, direct edits, and prompting must not silently approve a draft. Approval always identifies an exact direction revision and its upstream input revisions.

**Output:** two inspectable directions and one explicit current approved choice.

### M7 — Generate and edit production materials

Generate the production creative brief and text storyboard from the exact approved direction. Sample/template output must visibly use the task's brief, selected direction, target duration, and supported refinement changes. Do not return unrelated identical canned output for every task.

Storyboard rows contain planned start/end times, visuals, dialogue, on-screen text, sound, and CTA where applicable. Reference-source timestamps and planned new-video timestamps are separate fields with separate meaning. Validate ordering and total planned duration. Keep claims consistent with the user's approved brand messages.

Allow text edits, save revisions, and make regeneration explicit so it does not silently destroy manual work. Whole-output regeneration is sufficient for this skeleton; per-row AI regeneration is deferred.

**Output:** saved, editable production materials tied to an approved direction version.

### M8 — Export the production plan

Provide simple readable brief and storyboard exports, such as Markdown/text and CSV. Preserve sample/current/outdated labels and source/version context. Escape CSV delimiters, line breaks, and formula-like cell content appropriately. Polished PDF design is deferred.

**Output:** files Frank and Andrea can open outside the app.

### M9 — Prepare the human reference-review template

Reuse or extend the existing team templates for source details, dated public metrics, timestamped observations, section roles, recognized errors, and separate creative hypotheses. A template and a clearly fictional example are sufficient. Do not build a training pipeline, retrieval database, or large content collection.

**Output:** a simple annotation guide/template consistent with the analysis contract.

### M10 — Establish shared contracts, dependencies, and module connections

Deliver the shared record definitions, executable validation, sample fixtures, documented interfaces, storage/revision behavior, processing/error states, dependency manifests, startup scripts, test commands, and developer handoff below. This is the principal foundation for Andrea's next work.

## 4. Data contract and migration requirements

Implement a versioned contract. Exact filenames may follow existing conventions; the following record names express the required concepts.

| Record | Required meaning and information |
|---|---|
| CreativeTask | Stable task ID, title, task mode, progress, active references to brief/video/analysis/direction/outputs. |
| BrandTaskBrief | ID/revision, confirmed brand inputs, approved messages, target duration, optional production constraints. |
| VideoAsset | Stable video ID, task association, input provenance/purpose, storage reference, measured duration, available media properties, intake status. Reserve reference/draft purpose without implementing an additional improve-draft workflow tonight. |
| EvidenceEvent | Stable event ID within the analysis, video ID, numeric start/end seconds, visual/audio lane, event kind, recognized text or visible/audible description, source/method, uncertainty when known. |
| ContentSegment | Segment ID, video/time interval, role labels, associated evidence IDs, separate role interpretation. |
| AnalysisResult | Contract version, analysis ID/revision, task/video identity, processing state, events, segments, coverage, origin, original/correction lineage, review state, useful errors. |
| CreativeDirection | ID/revision, exact brief/analysis versions, message/Hook/narrative/CTA, production requirements, evidence links, rationales/hypotheses, generation origin, draft/approval state. |
| CreativeFeedback | User's free-text instruction, target artifact ID/revision, task association, applied/resulting revision or unprocessed status. |
| ProductionCreativeBrief / TextStoryboard | Output ID/revision, approved direction ID/revision, exact upstream versions, output content, planned timing, evidence references, generation origin and currentness. |
| ProcessingJob / Error | Operation, task and relevant input IDs/versions, status, result reference or actionable error, retry/partial-coverage information. |

### Required rules

1. Use seconds relative to the original video for evidence and segments. Require finite numbers with `0 <= start < end <= measured video duration`.
2. Evidence events may overlap. Primary content segments remain ordered and nonoverlapping. An event can cross a segment boundary and be cited by more than one segment. Preserve understandable role labels, including uncertain/other cases.
3. Keep observation separate from interpretation and recommendation. A visual event describes a lid closing; a section may interpret it as a Hook; a direction may propose using a similar technique for the user's goal.
4. Make evidence events the canonical recognized content. Avoid independently editable copies of the same text in both events and segments. Derived section summaries must be recomputed or clearly marked outdated after relevant corrections.
5. Evidence references must resolve within the exact recorded analysis revision and video/task, not merely match an ID found anywhere in storage. Reject duplicate IDs and dangling/wrong-project references.
6. Preserve original extraction. Corrected content creates a new analysis content revision; confirmation alone need not create a new content revision. Disallow changing immutable IDs and timestamps through correction endpoints.
7. Record the exact brief, analysis, feedback, and direction versions used for outputs. Relevant upstream changes preserve older work but mark it outdated and invalidate dependent approvals. A revised direction requires approval again.
8. At the backend, direction generation and refinement must require the current confirmed analysis revision with a successful processing state and valid task/video identity. Explicitly partial analyses may proceed only under a documented coverage policy after review; failed or still-running analyses may not. Reject unconfirmed, outdated, wrong-project, or mismatched analysis inputs. Production generation must also reject unapproved, outdated, wrong-project, or mismatched direction/input versions. A disabled UI button alone is insufficient.
9. Sample, manually supplied, and real provider origins must remain distinguishable. User correction does not turn fictional evidence into real evidence. Never invent a provider/model run for a sample.
10. Unknown public metrics remain unknown, with optional collection dates. A missing analysis capability is distinct from a checked-absent event. Do not invent confidence scores.
11. Save/reopen and backend restart must preserve records, versions, selected direction, feedback, review status, and provenance. Avoid stale asynchronous results overwriting newer corrected work.
12. Put authoritative schema definitions in one maintained place. Generate types where practical or provide automated cross-language compatibility checks; do not maintain silently divergent Python and TypeScript contracts.

### Preserve and deliberately extend the existing starter

The starter previously defined `AnalysisResult` v0.1 with content segments and did not yet define the richer visual/audio event layer. Inspect the actual version first. If that baseline is present, introduce a documented new version such as v0.2 rather than slipping incompatible fields into v0.1.

Preserve legacy examples and explain how they relate to the new format. Implement and test a migration or explicit legacy import path for the supplied examples. Preserve missing/unknown source information and synthetic labels; do not create nonexistent media or fabricate extraction provenance. Update schemas, validators, examples, interface docs, and consumers together.

The old success shape may require a `model_run`; a sample success must use honest generation provenance instead. The old sample may reference `SYNTHETIC_LumaCup_demo_NO_MEDIA.mp4`, which is not evidence that a real file exists. Do not claim playback or seeking was verified using that name alone.

## 5. Interfaces and sample materials

Document and implement the module operations needed to create/reopen tasks, save briefs, upload/serve media, request/get analysis, save corrections, confirm review, request/refine/approve directions, generate/edit outputs, and export.

Use a small provider boundary for:

- **Video analysis:** saved video reference plus request/job context → normalized analysis/events/sections or a structured failure.
- **Creative directions:** brief revision + reviewed analysis revision + optional free-text feedback → draft directions with provenance and valid evidence references.
- **Production materials:** current approved direction and its exact inputs → creative brief and text storyboard.

Define processing states and retry behavior consistently; a simple implementation is sufficient. A message queue, microservices, general agent framework, and multi-provider routing system are unnecessary.

Create a complete, clearly fictional sample task yourself. Frank is not supplying a filled-out example. Include valid overlapping visual/audio events, content sections, a correction, direction choices, a free-text refinement scenario, approval, brief, and storyboard. Fixtures should validate through the same code used for real results.

Generate a tiny synthetic video matching the sample observations, preferably with a reproducible script and installed media tooling. Use simple actions/text/sounds that the generated clip actually contains; do not claim human speech, camera footage, or product behavior that is absent. Label any additional schema-only examples as such and exclude them from playback-evidence claims. Keep generated media in an ignored location; commit the generation script, manifest, and small text fixtures. If media generation is blocked, complete independent work and explicitly mark matched playback/seek verification incomplete.

For arbitrary user uploads, the unconfigured real analysis route must produce a clear “real analysis is not configured” result. A dedicated sample task may run from beginning to end; it must not masquerade as analysis of a user's unrelated video.

## 6. Install and document dependencies

Install the dependencies required to build and verify this skeleton in the actual Cloud environment using permitted mechanisms. Inspect available tools first. Include runtime/package version requirements, lockfiles or an equivalent reproducible dependency specification, necessary media tooling, and development/test dependencies. Avoid speculative installs for later AI capabilities.

Provide repeatable commands for dependency setup, starting the backend and frontend, generating/loading samples, and running verification. Include a placeholder-only `.env.example` and documented storage locations. The baseline must run without API keys or paid requests. Keep uploads, generated media, temporary test data, secrets, and build caches out of Git.

Document what Frank's Mac and Andrea's computer will need to run the app. Do not claim those machines were configured or tested from the Cloud. Cloud dependency installation and Git push do not transfer installed runtimes or media automatically.

## 7. Required autonomous verification

You must execute relevant checks yourself, investigate failures, fix the implementation, and rerun affected checks. Writing test files without running them is not completion. Do not weaken assertions, skip failures, or change the required behavior merely to make a check pass.

Create tests for meaningful boundaries and failure behavior, not a large suite of trivial implementation mirrors. Reuse existing tools and test conventions. At minimum, verify:

### A. Data and revisions

- The complete sample validates against the current contract; supported legacy examples migrate without losing synthetic provenance.
- Overlapping evidence is accepted; invalid/negative/out-of-bounds/nonfinite times and overlapping primary sections are rejected.
- Duplicate IDs, dangling citations, wrong-analysis-revision references, and wrong-project references are rejected.
- Allowed corrections change content/roles, preserve originals, reject ID/timing edits, and clear review confirmation as appropriate.
- Brief changes, analysis corrections, direct direction edits, and applied prompt feedback invalidate dependent currentness/approval while preserving earlier work.
- Reference time and planned-storyboard time are treated as distinct clocks.

### B. Module and API connections

- Create/save/reopen survives a backend restart, using isolated temporary test storage.
- Upload validation and unreadable media produce useful errors; sample setup does not depend on a nonexistent file.
- Sample analysis and generation traverse the actual module interfaces; a real unconfigured upload never silently receives sample findings.
- Free-text feedback is saved and reaches the creative adapter. The documented supported sample instruction visibly changes the relevant content and produces an unapproved draft. Unsupported instructions remain saved and explicitly marked not interpreted/applied; they may be retained as production notes, without claiming successful refinement or requiring a misleading generated draft.
- Direction generation/refinement rejects unconfirmed, failed, still-running, outdated, wrong-project, or mismatched analysis inputs. Any supported reviewed partial-analysis path follows its documented coverage policy.
- Production generation rejects unapproved, outdated, wrong-project, or mismatched direction versions at the backend.
- Retries and delayed results do not overwrite a newer reviewed analysis or edited output.
- Storyboard duration/order, export formatting, and sample/unknown-metric provenance remain correct.

### C. Executable application

- Run the backend's relevant checks and tests.
- Run frontend type checking and a production build; run the repository's lint command if configured or newly required.
- Start the app and run an automated end-to-end walkthrough using a headless browser test runner if the environment permits it. Install its required supported dependencies if permitted. Do not confuse an unavailable browser-control tool with proof that a CLI browser runner can or cannot run; check the actual environment.
- Walkthrough: create/enter a brief → load the dedicated sample → play/seek matching media → expand observations → correct content/role → confirm review → compare directions → apply free-text sample refinement → approve → generate/edit brief and storyboard → save/reopen → change an upstream input → verify outdated outputs.
- If browser execution is unavailable after a reasonable supported attempt, run API integration checks and frontend build/type checks, preserve the browser test, and mark browser/playback verification **not run**. Do not report a fully verified UI or complete readiness in that case.

Provide one documented verification command, or a clearly ordered small set, that Frank and Andrea can rerun. Capture actual commands, exit results, and short failure details. After fixing a defect, rerun its relevant check and the affected integration path. Stop expanding testing once the agreed risks and required gates are covered.

## 8. Required deliverables and morning report

Use existing equivalent paths where appropriate; document the mapping rather than duplicating files unnecessarily.

| Deliverable | What must be present |
|---|---|
| Runnable app | Connected task, brief, upload, sample analysis/review, direction prompting/approval, output/edit/export flow. |
| Shared contracts | Versioned schema definitions, runtime validation, compatible frontend/backend types, and legacy migration/import behavior. |
| Examples | A complete labeled sample, invalid boundary cases for tests, and reproducible matching-media setup or an explicit blocker. |
| Provider connections | Documented replaceable recognition and generation interfaces; functioning sample implementations; honest unconfigured real-provider behavior. |
| Dependencies and startup | Tested manifests/locks, configuration example, storage/ignore rules, setup/start/sample/test commands. |
| Interface guide | Inputs, outputs, errors, timing rules, ownership, version/approval behavior, and actual implementation paths. |
| Decisions | Technical defaults selected by Codex, stack/runtime versions, scope changes from the starter, and unresolved external blockers. |
| Verification | Executed contract/API/build checks and actual end-to-end result, distinguishing passed/failed/not run. |
| Morning handoff | `docs/handoff/overnight-skeleton-review.md` or an existing handoff-format equivalent. |

The morning report must begin with one of:

- **Ready for review:** the agreed sample skeleton and its required checks are complete.
- **Partially ready:** usable work exists, but specified features or verification gates remain incomplete.
- **Blocked:** a named dependency prevents the core workflow from running.

Then include:

1. A feature table with **working**, **sample-backed**, **unconfigured**, **failed**, or **not implemented** labels; separate behavior from verification status.
2. Exact startup and verification commands, supported/tested runtime versions, and how to open the sample task.
3. Contract version, migration behavior, key source files, and the recognition request/response entry point Andrea should implement.
4. Actual test commands and outcomes; explain any tests not run. Do not report planned or assumed results as completed.
5. What the free-text refinement demonstration supports and what requires the later real generation provider.
6. Remaining blockers, external access requirements, and the next concrete module tasks.
7. Current branch, starting commit, changed-file summary, and any commits created by the environment. State precisely what has and has not reached GitHub.

### Next developer tasks

- **Andrea:** implement real video analysis behind the existing recognition interface. Return normalized, validated evidence events and content sections; do not require the UI to understand provider-specific output. Begin with visual actions, on-screen text, and speech, extending optional audio/visual categories as verified.
- **Frank:** review the sample workflow and shared contract, integrate changes, refine UI/UX later, and implement or connect real creative generation using the same brief/evidence/feedback boundaries.
- **Together:** approve shared-format changes and test one real analysis through correction, direction approval, and storyboard production.

### Git handoff for this overnight task

Frank intends to review and commit/push the implementation himself after the morning review. Leave all changes reviewable in the task branch/workspace. Do not manually push, merge, deploy, force-push, delete branches, or rewrite shared history. Do not manually commit unless the environment requires commits to preserve or return the task result; if it does, report the resulting commit and leave publication/merge to Frank. Preserve the platform's normal task result or patch handoff.

This task-specific handoff preference supersedes the starter's general permission to prepare a push/PR. It does not authorize modifying unrelated files or suppressing a required check.

## 9. Definition of completion

The foundation is ready for review when Frank can run the sample workflow, the data passed between modules is validated and versioned, corrections and free-text refinement are preserved, approval gates work, dependency/setup instructions are reproducible, required checks have actually run, and Andrea can locate a tested analysis entry point with a valid example.

This establishes the skeleton and its agreed internal dependencies. It does not certify real recognition accuracy, unrestricted prompt understanding, creative effectiveness, third-party link access, public hosting, or local-machine readiness. Describe any gap plainly. Deliver the implementation and the morning report; do not finish with only a proposal to continue.
