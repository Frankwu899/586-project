# M2 Input / Output and M10 Contract Impact

Status: explicit proposed shared-contract changes for implementation and integration review. No shared protocol or application source was modified while preparing this handoff.

## 1. Verified baseline

Checked 2026-10-17: [PR #3](https://github.com/Frankwu899/586-project/pull/3) is open, draft and unmerged. Head: `feat/video-analysis/bilingual-provider-contracts` at `da95ad3325a04b3b9f01cc7cb02a03af353208b5`. Base `main` SHA reported by the PR: `a456329e4fe8cab76669c8c8254cfed8ce11bbcb`. Recheck live state before implementation; these are an inspection snapshot, not permanent branch instructions.

At this head, the current schema version is `0.4.0`. `backend/app/models.py` defines strict `BrandTaskBrief`; `backend/app/service.py` saves a new revision on every brief write; `backend/app/storage.py` stores validated task aggregates in SQLite. `POST /api/tasks/{task_id}/brief` currently accepts `{expected_version, brief}` and returns `TaskState`. `frontend/src/BriefEditor.tsx` is a conventional required-field form.

`TaskStore.update()` increments task version. `WorkflowService._run()` rejects a provider result if that version changes while work is in progress. Therefore using either the existing task update or brief-save path for partial autosave would invalidate work merely because a user typed. Current `_inputs()` checks the applied brief and confirmed analysis, but has no pending-draft check. The creative provider serializes the whole applied brief into its context. These facts determine the changes below.

## 2. Conceptual input and output

| Boundary | Input | Output |
|---|---|---|
| User editing | Manual values, source notes, accepted proposals, claim confirmations | Persisted partial M2 draft |
| AI extraction | User-supplied notes plus immutable request/draft version | Source-linked proposals; no formal brief mutation |
| AI task assistance | Explicitly provided brand/task context and requested missing task field | Clearly labeled suggested options |
| Apply | Expected draft version, expected task version/current brief reference, reviewed draft | Strict versioned BrandTaskBrief, updated draft checkpoint, affected downstream invalidation |
| M6 | Current applied brief reference plus confirmed current analysis reference | Existing creative-direction workflow |

The draft is editor state. The applied brief is immutable generation input. M7 output is neither of these.

## 3. Proposed M10 delta register

| ID | Proposed change | Reason / boundary |
|---|---|---|
| M2-C01 | Add `M2Draft` and partial input types with independent persistence/version | Support incomplete saves without changing generation readiness or task version. |
| M2-C02 | Add source-linked extraction/suggestion proposal request and response types | Separate AI assistance from accepted facts and existing creative-generation operations. |
| M2-C03 | Extend applied `BrandTaskBrief` with associated claim metadata | Keep qualifications/support attached to exact immutable claim wording and send it downstream. |
| M2-C04 | Add explicit atomic Apply/discard operations and no-op behavior | Control when formal inputs and dependency validity change. |
| M2-C05 | Add server-side pending-input readiness checks and actionable errors | Prevent client/API bypass while preserving independent reference work. |
| M2-C06 | Version schemas/types and migrate existing persisted tasks honestly | Current records forbid unknown fields and use literal schema versions. |

These are proposed field/API names for the implementation. Follow repository naming conventions when integrating, and report the final mapping. Do not add brand-library entities, unrelated workflow enums or new M7 fields. If integration needs a further shared-contract change, list it with a concrete reason and migration/test impact.

## 4. M2Draft — separate editing state

Suggested fields:

| Field | Meaning |
|---|---|
| `task_id` | Existing task owner; no new global profile ID. |
| `draft_version` | Independent optimistic version, incremented on accepted draft writes. |
| `based_on_brief` | Exact applied brief reference, or null before first application. |
| `fields` | Partial counterparts of existing brief fields; required applied fields can be null/unset here. |
| `claims` | Stable claim IDs, wording, optional support/qualification, confirmation state. |
| `source_notes` | User's recoverable pasted text in its original language. |
| `reviewed_input_checkpoint` | Last explicitly applied/reviewed structured-input snapshot or digest. |
| `updated_at` | Server save time. |

Use a separate table/record in the existing database, with an independent update operation. Autosaves must not pass through `TaskStore.update()` or return an old whole-task snapshot that can roll back frontend job status. The API should return editor state with its version, not replace the entire task in the client.

One authoritative persisted draft per task is sufficient. Do not build collaboration, field-level merge history or proposal history. A simple optimistic-conflict response preserves local edits and offers reload/retry; never silently overwrite remote state.

`has_pending_inputs` is derived from unreviewed structured edits, including claim inclusion/confirmation and generation-relevant constraints. Merely pasting notes, receiving an unaccepted proposal, or opening a section does not change the formal inputs or block generation. On successful Apply, checkpoint the reviewed structured draft, including its explicitly excluded unconfirmed claims. This allows retained “for later” claims without a permanent pending flag. Later editing those rows requires review again.

### Ordering and running work

Serialize/coalesce saves or use request IDs plus version checks so late responses cannot overwrite newer text. Flush pending local changes before Apply or downstream actions. A network save failure blocks those actions until saved or explicitly discarded.

Recognition may continue while the draft changes. Creative work already started against an applied revision may finish against that revision while separate draft edits are pending; its UI must indicate the outstanding edits and prevent approval/new generation until they are resolved. A meaningful Apply during a running creative operation must preserve existing stale-response rejection for the superseded applied input. Do not weaken global job guards to solve editor concurrency.

## 5. Claims and applied metadata

Draft claim shape: stable `claim_id`, exact `statement`, optional `supporting_notes`, optional `source_urls`, optional `qualification`, and `confirmed_for_use` boolean. Editing statement/qualification or AI-replacing a row clears its confirmation. User editing is preserved verbatim except intentional outer whitespace cleanup.

Proposed applied field: `claim_details`, an ordered list containing stable claim ID, exact statement, optional support/URLs/qualification, and `confirmation_origin`. New M2 applications use `user_confirmed`; migrated historical records use `legacy_unrecorded`. Do not use a field named `verified`.

Keep existing `selling_points` as the ordered statement projection for compatibility. Its values must exactly match applied `claim_details` for new M2 submissions; validate this association server-side, using IDs rather than mutable array positions for editing. Only confirmed included claims enter new applied snapshots. Draft-only unconfirmed claims must never enter M6/M7 provider context.

Preserve `approved_messages` and `prohibited_claims` with their current meanings. User confirmation of the final review covers supplied approved copy and restrictions; AI proposals cannot automatically populate applied copy. Qualifications, support and restrictions are serialized from the applied snapshot into generation context and must be respected by adapter instructions. Do not bury qualifications in a mutable UI note or concatenate them into an unrelated production-limit field.

URLs are user-supplied references. Validate safe URL form for linking; do not crawl them. No attachment storage or proof-verification service is added.

## 6. Proposal contract and provider boundary

Use a bounded M2 assistance interface separate from direction generation. Proposed request fields: `task_id`, `draft_version`, request identity, source text, requested mode (`extract` or `suggest_task_field`), optional requested task field, and necessary current draft context. Source content is untrusted data, not instructions to change system behavior.

Proposed response fields: request identity, source draft version, candidates with a typed field/claim target, proposed value, origin (`extracted` or `suggested`), exact source excerpt for extraction, and concise user-facing unresolved-item notes where applicable. Allow only M2-editable fields. No server IDs, approval status, analysis corrections or task-version mutation can be proposed.

Validate response shape and limits before rendering; render text safely. Missing or unsupported extracted fields stay unset. Reject malformed/untraceable fact proposals and stale responses, keep user input, and show a retry/manual path. AI cannot confirm claims. Candidate selection/editing/dismissal remains local proposal-review state. “Use selected details” validates the source draft version and applies all selected candidates in one atomic draft update. This avoids invalidating the remaining candidates after accepting the first row. Any intervening persisted draft edit makes the batch stale; rerun rather than adding a rebase system.

Do not put extraction into existing closed `ProcessingJob.operation` enums by stealth. Prefer a separate bounded request with independent loading/error state for this demo. Extend job contracts only if the inspected implementation truly requires it and document that delta. A fake assistance provider is required for deterministic tests, visibly isolated from real operation. Real provider failures must never silently return sample values.

## 7. Apply transaction

Inside one consistent transaction:

1. Read and validate expected draft version, current applied reference and task concurrency version.
2. Validate all required applied fields, at least one explicitly confirmed included claim, numeric duration and safe structured values. Unknown placeholders do not count as answers.
3. Construct the entire provider-relevant applied payload from the reviewed draft. Exclude raw notes, unapplied suggestions and unconfirmed claim rows.
4. Compare it semantically with the current brief. Exclude generated identity/timestamps and editor bookkeeping. Include all actual task/claim/restriction content. Do not reorder or aggressively normalize approved wording.
5. If equal, update only the draft checkpoint/baseline metadata as needed. Return `changed: false`; no new brief revision, task version or invalidation.
6. If changed, append one formal brief revision, update `current_brief`, invoke existing downstream invalidation and update the draft baseline/checkpoint atomically. Return `changed: true` with the new applied reference and current task.

Failure leaves both applied state and checkpoint unchanged. Double submission/retry with the same reviewed content must not create duplicate revisions. Discard is a separate explicit editor action; it does not delete the task, reference, analysis or historical outputs.

The existing `/brief` route must not remain an unrestricted alternate path around required confirmations or revision behavior. Route it through equivalent Apply validation or introduce an explicit compatible applied-input request with documented legacy handling. Verify every caller and fixture before changing it.

## 8. Readiness and errors

Require a complete applied brief, no pending structured edits/review requirement, and confirmed current reference analysis before directions. Preserve exact-version checks for refinement, approval and production as well. Server checks are mandatory for direct API calls. Check the persisted draft gate atomically when admitting a new generation/refinement/production job or approving a direction. Do not use later pending draft edits as a completion-time validity condition for an already admitted job whose applied inputs remain unchanged. Draft-independent reference upload/analysis/review remains available.

Suggested machine-readable errors: `m2_incomplete`, `m2_unconfirmed_claims`, `m2_pending_changes`, `m2_draft_conflict`, `m2_stale_proposal`, and `m2_legacy_review_required`. Map them into the repository's existing error envelope rather than creating an unrelated response style. Include actionable field names and preserve input; do not expose provider secrets or raw sensitive diagnostics.

## 9. Schema version and migration

Proposed target is `0.5.0` if `0.4.0` is still current when work starts. Confirm repository versioning conventions and intervening M10 work first. This document does not itself bump the shared protocol. Generate JSON schemas and TypeScript from the canonical models through the existing export tooling; do not hand-edit generated consumers only.

Migration must preserve historical revisions, original analysis, corrections, evidence references, frame clocks, approvals and outputs. Keep archived historical schemas/examples intact. Add the new current schema, fixtures and documented migration, with transactional rollback on failure.

For legacy briefs, preserve their applied wording and references. Seed an editable draft without pretending that users previously checked new claim-confirmation controls. Historical metadata uses `legacy_unrecorded`; ask for explicit review before new creative generation/approval on that task. Migration preserves existing approval/currentness flags and artifact references; the legacy review requirement is a separate gate on new creative actions. Migration alone must not erase, invalidate or silently regenerate outputs. Explicitly applying newly confirmed metadata creates the next formal revision when that metadata changes, then performs normal downstream invalidation. Do not convert missing proof into a verified claim.

No account/profile reuse schema, external research data model, multi-platform task array, M7 output renaming, or changes to reference-frame/storyboard-seconds semantics are included.

## 10. Integration reporting

The implementation report must list final fields and endpoints, chosen schema version, migration behavior, actual baseline/head SHAs, all touched shared files, generated-artifact changes and tests. Shared-contract changes must be visible in the PR description. Unverified live-provider quality must remain separately labeled.
