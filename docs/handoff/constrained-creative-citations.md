# Constrain generated citations to reviewed evidence

- **Task:** Fix the live creative-generation failure reported as “Creative evidence must cite an event from the exact reviewed analysis.”
- **Author and date:** Main orchestrator, 17 October 2026.
- **Execution environment:** Managed Linux workspace; owner operates the macOS bundle.
- **Repository:** Frankwu899/586-project.
- **Branch:** `fix/creative-direction/constrain-reviewed-citations`.
- **Baseline:** `228d5e768d3da4727a17a815d54e705610a20bcc`, PR #6; clean worktree at start. Draft PR targets `feat/integration/local-api-launcher`.
- **Objective:** Prevent arbitrary model-generated event identifiers without weakening reference validation or replacing the owner's reviewed analysis.

## Diagnosis and change

The supplied screenshot shows applied inputs and a reviewed reference. Its exact
message originates from `_evidence` when at least one returned citation event ID
is absent from the supplied analysis. The owner's exact provider response/invalid
ID is not available in Cloud. Inspection found that the strict output schema
accepted any nonempty string for `Citation.event_id`: only the prompt requested
valid IDs. Two new regression tests failed against the baseline because the
outbound schema lacked the required input-specific choices.

`backend/app/providers/creative.py` now supplies a fresh enum containing the exact
reviewed analysis's event IDs in every generation, refinement and production
request. The prompt distinguishes event IDs from other identities and prohibits
invented/abbreviated/segment IDs. Prompt version advances to
`creative-v4-constrained-citations`. Existing post-response membership, duplicate
and exact revision checks remain; no fuzzy matching, removed citations, arbitrary
substitution or automatic paid repair/retry is introduced. Citation-free original
production shots remain supported. The failure message explains that the reviewed
analysis is unchanged and no draft was saved.

This restricts valid references; it does not prove that a chosen event supports
the generated rationale. Human evidence/creative review remains necessary.
Shared persisted contracts, frontend assets and migrations are unchanged.

## Verification

| Check | Actual result |
| --- | --- |
| New tests against old code | 2 failed: outbound citation enum absent. |
| `pytest -q tests/test_creative_provider.py tests/test_provider_workflow.py tests/test_providers.py tests/test_workspace_editors.py` | 72 passed; existing TestClient deprecation warning only. |
| Actual HTTP adapter with `httpx.MockTransport` | Outbound strict schema limits IDs for generation/refinement/production; JSON Schema rejects a foreign ID. Long opaque IDs and reviewed revision 3 survive; original shot may have empty evidence. No network/model calls. |
| Sequential input isolation | New analysis changes citation choices without mutating the previous request or shared Pydantic schema. |
| Existing adversarial provider cases | Unknown citations still fail without sample fallback; review/approval and persistence checks pass. |
| Ruff and whitespace | Passed for changed files. |
| Private patch installer smoke | Exact file replacement and backup, spaces in path, repeated install, preservation of task sentinel and rejection of modified source passed on Linux. Shell syntax passed. |

## Local delivery and state preservation

`scripts/package_citation_fix.py` builds a small private ZIP containing the updated
provider file, before/after SHA-256 values and an executable macOS installer. The
installer defaults to the owner's observed Desktop `video-anatomy-local` folder,
or offers a folder picker when it cannot find it. It refuses mismatched source,
backs up the original file, and replaces only `backend/app/providers/creative.py`.
No credentials, SQLite database, media, cache or draft files are included/touched.
The full local bundle can also be regenerated for future fresh installations.

The owner should stop the old server, run the patch, restart from the same original
folder and re-enter the key. Reopen the existing task and generate directions
once. Do not re-upload, re-analyze or re-confirm the reference just for this fix.
Historical failed processing records remain intact. The next generation is a new
potentially billable request, not recovery of a saved provider response.

## Remaining validation

No live OpenAI test was run: the managed environment still has no configured key
and does not allow `api.openai.com`. Mac patch execution and the owner's next live
generation remain pending. No claim that the owner's exact failed response was
replayed, that all live output problems are resolved, or that charges were undone.
No main merge or deployment is part of this change.
