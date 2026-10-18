# Workspace and Structure implementation boundary

The owner authorized implementing the redesigned workspace, tests and a shared
USD 3 provider experiment after confirming Structure decisions S1–S11. Earlier
review documents remain design history; their discussion-only status is not the
current task authorization. This implementation does not authorize merging main
or public deployment.

## Implemented in this branch

- A bounded desktop-style browser workspace with Research / Timeline and
  Structure tabs, independent Ideas and Production areas, persistent drafts and
  local operation feedback. The layout uses restrained glass surfaces around
  readable, opaque work areas.
- Background tickets for recognition and creative operations. Polling and
  application restart never replay billed requests. Completed work and draft
  state remain separate from processing indicators.
- Source-timed Timeline inspection, selected-event details and grouped repeated
  OCR. Non-destructive Content area crop/exclusion settings and a conservative
  edge-bar suggestion operate before provider frame extraction. This does not
  claim a trained platform-interface classifier or exact shot detection.
- A dedicated Structure service and OpenAI adapter. It publishes a grounded
  video-based graph before focused automatic web research, keeps source claims
  separate from inference, attaches exact source-event timing on the server,
  and rejects invented citations/URLs. Every transferable method carries its
  supporting nodes and applicability conditions.
- Optional node questions/context/reconsideration, with previewable proposals
  instead of manual graph construction. User-supplied context and adopted
  corrections survive concurrent research. Stale proposals cannot overwrite
  later adopted changes. Budget/time/source failures preserve completed partial
  work, without a Continue research endpoint.
- Explicit selection from Structure into Ideas. Saved handoffs remain immutable;
  the direction pins its `structure_handoff_id` for refinement and production.
  Context does not become a verified brand fact, reviewed video evidence or an
  approved direction merely by being selected.
- Original direction generation and user-authored ideas without a reference.
  Their `analysis_ref` is null and reference citations are prohibited. Exact
  direction approval remains required for production. Changing unrelated
  reference media does not invalidate an original idea's approval.
- Additive SQLite Structure run/history/handoff tables, independent idea drafts,
  and v0.7 generated contracts. Existing v0.6 records are accepted intact;
  historical schemas/examples are preserved. The local launcher supports stable
  application data and non-destructive legacy-library import.
- Shared provider budget reservations and per-module usage/elapsed-time records.
  The experiment limit cannot exceed USD 3. Unknown usage/charges remain unknown,
  rather than being recorded as zero. Local mocks are not live measurements.
- Electron packaging source and macOS build/runtime verification instructions.
  Installation materials and launcher copy are English.

## Verified boundary

Focused offline checks executed during this implementation include:

- `tests/test_structure_service.py`, `tests/test_structure_provider.py`,
  `tests/test_structure_api.py`, and `tests/test_independent_workspace.py`:
  24 passing tests at the recorded implementation checkpoint.
- `tests/test_contracts.py` plus the independent-workspace tests: 97 passing tests
  at that checkpoint. Counts overlap and must not be added together.
- Generated schema/type drift checks and lint of the added Structure boundary.

The focused cases exercise unknown-upload honesty, exact citations and timing,
partial research recovery, deadline admission, proposal adoption, preserved
context/history, source invalidation, task isolation, restart behavior and
reference-free approval/export invariants. Cloud TestClient checks require
loopback socket permission; no external paid request is part of these tests.

The final integrated test/evaluation report is authoritative for checks rerun
on the delivered commit. This document does not claim that focused tests validate
all browser paths, macOS installation, real recognition quality, search quality,
actual provider latency or campaign effectiveness.

## Remaining limits

- Live API usage, cost, efficiency and quality must be read from the actual
  evaluation report. A configured key, test fixture or successful HTTP response
  alone is not evidence that a live module succeeded.
- Original source videos are retained; Content area processing is not a learned
  screen-recording UI detector. Stationary brand marks, prices and captions must
  not be discarded merely because they are stationary.
- Sparse visual samples do not establish continuous text/action duration,
  precise scene boundaries or spatial tracking. Speech timings are estimates.
- Research citations establish attribution and grounding, not independent truth.
  Target audience, intent and effectiveness remain analytical inferences unless
  independently supported. The agent has no exhaustive fact-checking guarantee.
- Sample Structure is scripted and clearly labeled; it never runs a live model
  or interprets arbitrary feedback as though it did. Real uploads do not receive
  this fixture on failure.
- No fine-tuning job or trained custom model is represented by prompt changes.
  Evaluation and held-out examples must precede claims of improved accuracy.
- macOS runtime bundling, DMG installation, signing/notarization and device-level
  behavior require their documented macOS build/test steps. Linux verification
  does not establish a working signed DMG.

See [interfaces](../../interfaces.md), [setup](../../../README_SETUP.md),
[provider evaluation](../../evaluation/BUDGET_AND_MODULE_EVALUATION.md),
[local delivery](../../../LOCAL_API.md), and [desktop packaging](../../../desktop/README.md).
