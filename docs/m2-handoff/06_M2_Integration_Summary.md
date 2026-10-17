# M2 Decision Summary for Integration

Date: 2026-10-17. Chosen visual direction: **Editorial Studio**.

## Confirmed product decisions

- M2 is the user-provided brand/product/task input. M7 remains the generated production Creative brief and text storyboard.
- The current target is a single-task, single-reference demo. “Profile” is task-local brand/product information. Cross-task reuse, a brand library and complex exception handling are deferred.
- Inputs and reference upload/review can be completed in either order within one workspace; both converge at M6 readiness.
- Use readable information summaries, focused inline editing, optional pasted notes and one current question with concrete choices. Users do not need to know their creative direction in M2.
- Drafts may be incomplete. The generation-ready brief requires brand, product, at least one user-confirmed usable selling point, audience, one platform, one communication goal and target duration.
- AI extracts only supplied facts and proposes task choices. Explicit acceptance is required; no silent overwrite or invented product claim. Claim evidence is optional; confirmation means user permission, not verification.
- Draft saving and formal input application are separate. Meaningful Apply updates the formal revision and invalidates dependent current approval/output eligibility. Draft editing alone and no-op Apply do not invalidate history.
- Pending structured changes must be resolved before downstream generation/approval. Existing exact-revision approval, reference evidence and export rules remain.

## Implementation defaults, not separately confirmed product decisions

English UI copy with source-language content preserved; light Editorial Studio target; independent debounced server draft persistence; one deterministic missing-field question at a time; manual operation without an AI provider; proposed claim metadata and draft/proposal contract shapes detailed in document 03.

## Explicit M10 coordination items

Separate partial M2Draft/version/persistence; bounded assistance proposal types; immutable applied claim support/qualification metadata; atomic Apply/no-op/discard semantics; pending-input API gates; documented schema version and migration. Proposed target is 0.5.0 only if 0.4.0 remains current. No shared protocol has been changed by this documentation task.

## Verified baseline and unresolved validation

PR #3 remains open/draft/unmerged as checked on 2026-10-17. Inspected head: `da95ad3325a04b3b9f01cc7cb02a03af353208b5`, branch `feat/video-analysis/bilingual-provider-contracts`; PR-reported base main: `a456329e4fe8cab76669c8c8254cfed8ce11bbcb`. Recheck before coding and branch from a baseline containing the prerequisite. Do not confuse the PR's existence or its reported test counts with M2 acceptance or validated real API quality.

Critical integration finding: existing task writes increment task version and can invalidate running provider responses. M2 autosave must use an independent editor channel. Current brief saving also creates a revision on every call, so no-op Apply must be added explicitly.

This handoff produced specifications and a complete implementation prompt, not application code, a merge, deployment or live-provider acceptance. The next step is implementation on a correctly based feature branch, automated verification, a draft PR and focused manual demo review. Paid/live API evaluation remains a separate budgeted opt-in step.
