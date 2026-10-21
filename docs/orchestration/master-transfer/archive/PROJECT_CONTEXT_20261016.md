# Video Anatomy Project Context

Snapshot: October 16, 2026, Los Angeles time.
Purpose: shared context for module-specific product discussions and Codex implementation tasks.
Repository: https://github.com/Frankwu899/586-project
Owner and integrator: Frank. Andrea helps with coding; her availability is not yet reliable enough to make the next step depend on her delivery.

## Read this first

Use this document to understand the project, then read the current blueprint, module PRD, applicable AGENTS.md, and relevant code. Do not assume that another chat's complete transcript is available. Restate the module, current foundation, confirmed decisions and unresolved choices before asking questions.

This document is a dated snapshot. Recheck GitHub before choosing an implementation base. A discussion chat, a Git branch and a deployed application are separate things. Creating a new chat does not create a Git branch or merge code.

Communicate with Frank in plain Chinese. Keep repository documentation and coding prompts in English. Chinese text is expected in bilingual fixtures and product content.

## Product goal and confirmed demo scope

Video Anatomy helps a brand or agency prepare a new product-focused marketing video by combining its own brand/task brief with evidence from one reference video.

The core value is helping the user choose a creative direction and produce a usable creative brief and text storyboard. Video recognition is a necessary foundation, but recognition alone does not establish product value.

Confirmed first-demo flow:
1. Create or reopen a creative task.
2. Enter brand/product context, approved selling points, audience, publishing platform, communication goal, target duration and optional production constraints.
3. Upload one reference video.
4. Inspect the time-aligned analysis, correct permitted content and labels, and confirm review.
5. Compare two creative directions, give written feedback or edit them, and explicitly approve one current revision.
6. Generate and edit the production creative brief and text storyboard.
7. Export the current outputs with version/currentness information.

The user-input brand/task brief in M2 is different from the generated production creative brief in M7.

Constraints:
- One brand/task brief plus one reference video is the demo baseline.
- Product-selling-point short videos are the initial reference type.
- English, Chinese and mixed-language recognition/reading are required.
- Preserve source-language text; do not silently translate evidence.
- The user can write free-text input and feedback.
- The original video/timing sequence remains read-only; recognized text, descriptions, segment roles and permitted structured categories can be corrected.
- Preserve the original extraction and correction history.
- Changes to upstream inputs invalidate affected approvals and mark dependent outputs outdated.
- Selecting a direction is not the same as approving it.
- The storyboard is text, with time, visuals, dialogue/subtitles, sound and CTA.
- Only public views, likes and comments are currently available. Do not invent retention, clicks or conversions or claim causation from public engagement.
- Evidence-based hypotheses and explicit test methods are allowed when outcome data is absent.
- Team-led demonstration is the deployment target. Public independent-user access is not required.
- Upload is the first dependable input path. Platform-link acquisition needs a small feasibility investigation before committing support.
- JEV integration is deferred. Provider interfaces must remain replaceable; OpenAI is first.
- Examples collected by the team initially support prompts/templates and evaluation. They are not automatically a trained model or proof that a hook caused a video's success.
- Broad multi-video comparison, generated storyboard images, accounts/billing and model training are outside the confirmed first-demo scope.

## Foundation status at this snapshot

GitHub PR: https://github.com/Frankwu899/586-project/pull/3
State checked: open, draft, not merged.
Head branch: feat/video-analysis/bilingual-provider-contracts
Head commit: da95ad3325a04b3b9f01cc7cb02a03af353208b5
Base main commit: a456329e4fe8cab76669c8c8254cfed8ce11bbcb
Handoff source: docs/english-starter at c3f40ca184212ec52025810e6420a5e97d1fe37c

The PR describes implementation across M10, M3, M4 and M5, plus integration with existing M6-M8. Do not treat M1-M9 as nine empty modules or rebuild working functions.

Reported changes:
- Contract v0.4, typed subjects/actions/product presentations, coverage and errors.
- Archived transactional migration preserving analysis, revisions and citations.
- H.264 and supported H.265/HEVC intake with a separate H.264 playback derivative.
- Supported HEVC claim is SDR Main 8-bit; MOV and HEVC 10-bit/HDR/Log are not established.
- Replaceable OpenAI vision/OCR, timestamped speech and creative-generation adapters.
- English/Chinese/mixed source text handling.
- Structured corrections, review/approval invalidation and stale-output handling.

Reported checks in the PR:
- 320 backend tests including 31 FFmpeg media/preparation cases.
- 5 frontend unit tests and 4 browser tests.
- Schema/type consistency, lint and build checks.
These results are the implementation author's report; this planning handoff did not rerun the application.

Real paid API tests have not run. Real bilingual recognition accuracy and creative-output quality remain unverified. Sparse visual sampling may miss brief events.

Frank has chosen to postpone local/manual acceptance for now and continue product specification. This does not turn unverified behavior into accepted behavior. He intends to arrange API credit and live tests on October 17, 2026, Los Angeles time; no amount or paid-call budget is authorized by that intention.

## Module map and dependencies

| Module | User-facing function | Consumes | Produces |
| --- | --- | --- | --- |
| M1 | Create, save and reopen tasks | M10 IDs, persistence and states | Recoverable task and progress |
| M2 | Enter the brand and task brief | M1 task; M10 validation/versioning | Versioned input brief and constraints |
| M3 | Add and inspect one reference video | M1 task; M10 media/error contracts | Saved playable source and measured media timing |
| M4 | Recognize visual and audio content | M3 media; M10 analysis contracts | Evidence events, content segments and coverage |
| M5 | Organize, correct and confirm analysis | M3 playback; M4 observations; M10 revisions | Reviewed effective analysis revision |
| M6 | Compare, refine and approve a creative direction | M2 brief; M5 review; optional M9 examples; M10 | Two directions and one approved revision |
| M7 | Generate/edit creative brief and text storyboard | M6 approval; M2 constraints; M5 evidence; M10 | Production brief and timed text storyboard |
| M8 | Export the work | M7 outputs; M10 versioned serialization | Portable brief/storyboard files |
| M9 | Collect team-reviewed reference examples | M4/M5 definitions; M10 formats | Curated examples and evaluation material |
| M10 | Maintain shared contracts and infrastructure | Confirmed decisions and current code | Consistent models, schemas, providers and persistence |

Runtime order is M1 then M2 and M3/M4/M5, converging at M6, then M7 and M8. M9 can enrich M6 but is not a required gate for the one-reference workflow. M10 supports the whole flow.

Proposed interview order, not an already approved product decision:
1. M2: resolve which brand information is required, optional, inferred or prohibited from inference.
2. M5: settle what the user sees, corrects and confirms before generation.
3. M6: settle how directions differ, evidence/rationale, feedback and explicit approval.
4. M7: settle actual creative-brief/storyboard quality and editing behavior.
5. M8: settle usable export formats and currentness labels.
6. M1: finish navigation, task list, resumption and progress based on the agreed flow.

M3/M4 need focused gap reviews around their implemented foundation, including progress/errors and live-validation needs; they do not need another unrestricted redesign. Review their boundaries while specifying M5. M9 collection and an evaluation template can proceed in parallel; a full reference-library UI is lower priority.

Do not defer every UI decision until coding is finished. Set a minimal shared layout/navigation convention, then prototype each module as its behavior is clarified. Integrate the UI after the module flow is stable.

## One chat per module

Suggested titles:
- VA | 00 | Integration and decisions
- VA | M1 | Tasks and progress
- VA | M2 | Brand and task brief
- VA | M3 | Video upload and playback
- VA | M4 | Video recognition
- VA | M5 | Analysis review and corrections
- VA | M6 | Creative direction and approval
- VA | M7 | Creative brief and storyboard
- VA | M8 | Export
- VA | M9 | Reviewed references
- VA | UI | Shared navigation and visual system

Keep the current conversation as the integration/decision hub. Start new module chats inside the same ChatGPT project and make this document plus the current blueprint available as project sources. Project sources and instructions help share context; they are not a guarantee of full transcript synchronization.

After a module discussion, bring its accepted decisions back to the shared context/decision record. Other chats must reread that updated record before relying on the decision. Branching a conversation carries context up to the branch point when the interface supports it; later discussions must still be reconciled.

Do not claim that chats, project-memory settings or repository branches were created merely by drafting this handoff.

## Interview and module deliverables

For each module:
1. Read its existing behavior, inputs, outputs and neighboring contracts.
2. List what is confirmed, what is implemented/reported, and what remains undecided.
3. Use grill-me if available. If it is unavailable, state that and use the same structured clarification method without claiming installation.
4. Ask a small round of consequential questions in Chinese, with concrete alternatives and reasons. Do not ask again about settled scope.
5. Use a small prototype for questions that depend on seeing an interaction; do not invent a final UI from abstract answers alone.
6. After Frank confirms the decisions, produce an English module PRD, UI interaction specification, acceptance criteria and a complete Codex implementation prompt.
7. Record proposed shared-contract changes separately. Do not silently redefine M10 in an individual module chat.

Suggested repository deliverables, to be created when that module is specified:
- docs/prd/MXX_module.md
- docs/ui/MXX_module.md
- docs/prompts/MXX_module_codex.md

Each PRD should cover:
- Goal and boundaries.
- Function/sub-function tree.
- Inputs, outputs, field meanings and version relationships.
- Normal flow, empty/loading/error/stale/conflict states.
- User permissions for edits and explicit confirmation/approval.
- Acceptance criteria using concrete example scenarios.
- Dependencies, shared-file touch points and remaining decisions.

Each coding prompt should cover:
- Correct repository/base commit and prerequisite PRs.
- Read-first files and applicable instructions.
- What to extend and what already exists.
- Module implementation and necessary integration.
- Relevant automated tests and honest reporting.
- Branch/commit/PR delivery without automatic main merge.
- Live calls only with separately supplied credentials, explicit opt-in and budget.

## Development base and integration rules

While PR #3 remains unmerged, a task needing v0.4 cannot assume main contains it.
Start such a task from the inspected PR #3 head, or from a designated integration branch that contains it. If using stacked PRs, target the immediate prerequisite branch and record its commit. After that prerequisite merges, reconcile the child branch and target main appropriately.

If PR #3 has already merged when work starts, use updated main after verifying its content. Do not use an old docs branch as the application base.

Only create implementation branches when a coding task is ready. A module discussion does not need its own Git branch.
Respect existing scope names, for example:
- feat/workspace/m2-brief-experience
- feat/analysis-review/m5-review-experience
- feat/creative-direction/m6-decision-flow
- feat/production-output/m7-production-editor
- feat/production-output/m8-export

Coordinate shared edits to models, generated schemas/types, service/API wiring and application navigation. Sequence dependent coding tasks rather than running nine incompatible implementations from one stale base.

Use fixtures/mock providers for offline progress. Preserve meaningful automated checks even though manual acceptance is postponed. Live recognition quality is a separate evaluation.

## Evidence and reference locations

- PR #3: https://github.com/Frankwu899/586-project/pull/3
- Implementation handoff on the PR branch: docs/handoff/bilingual-provider-contracts.md
- Setup: README_SETUP.md
- Live validation: docs/live-validation.md
- Original requirements package: docs/video-anatomy-handoff/
- Blueprint: existing blueprint.html. Its observed implementation-status sections predate PR #3 and should not override current GitHub state.
- Shared-context product guidance: https://learn.chatgpt.com/docs/projects
- Interview method: https://www.aihero.dev/skills-grill-me

The current chat's attempted blueprint attachment failed to materialize. Planning used the available stored blueprint version 2 for the module map and the current PR #3 for implementation status. A newer blueprint, if one exists, must be read before treating it as authoritative.

