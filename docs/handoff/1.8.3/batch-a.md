# Batch A: shared layout and Overview

Owner: Frank / Yuqing Wu. Implementation: Codex. Verified in Linux Cloud on
17 November 2026 (America/Los_Angeles), from bd93bfc884b70be81bbf93ddf2c72b42cea7dafc.
The task branch is feat/integration/1-8-3-overview-layout.

## Result

Shared navigation retains visible labels and uses a native disclosure on narrow
windows. The root document scrolls without hiding horizontal overflow. Overview
uses a bounded message pane with the composer in normal flow; short windows use
document scrolling, and a container query exposes View brief when space is tight.

Only adopted facts appear in the compact Brief snapshot. Proposed changes have
a separate native dialog, exact draft-version checks, current/proposed values,
sources, editing, Keep current and explicit Apply updates. Claim adoption and
removal remain explicit. Missing adopted IDs in migrated drafts are retained.
A local editor does not silently adopt a newer draft version during polling.

Conversation jobs/messages carry unique attempt IDs and a durable stopped state.
Stop suppresses queued work, attempts to close this conversation's active HTTP
client, prevents subsequent research and guards all writes against old attempts.
Retry retains the user message and attachments while creating a new attempt.
Stopping before admission keeps the unsent composer without starting assistance.
Already-completed results win a completion/Stop race. A request already accepted
by the provider can still incur usage; no billing or provider policy was changed.

Intake asks at most one consequential question in a turn and defaults to at most
two proactive turns, then a limited reviewable draft. Explicit proceed and deeper
requests are distinguished. Sufficiency metadata is validated and rejected
question text cannot bypass the existing grounding/URL guards. These controls
were verified with authored provider responses, not live model-quality trials.

## Checks actually run

- Focused backend conversation/Stop/API/storage/release persistence: 147 passed.
- Full backend: 1053 passed, 1 skipped before the frontend build. The sole skipped
  managed-server launcher check was rerun after building and passed (1 passed).
- Frontend unit suite: 51 passed. TypeScript, ESLint, production build, Ruff,
  dependency and generated contract checks passed.
- Legacy browser suite: 55 passed; injected-provider browser suite: 4 passed.
- Nine new Overview browser cases passed in stable targeted runs. Other targeted
  Overview/workspace/reliability checks totalled 18 distinct passing cases.
- Native Chromium Page zoom: both 1440x900 and 1280x800 outer windows at
  100/125/150/200 percent passed reachability, root overflow, composer separation,
  dialog inertness and focus-return assertions. The receipt distinguishes native
  zoom from CSS zoom, pinch and viewport emulation.
- The first complete project suite ended 34 passed / 1 failed: a readiness
  assertion matched the saved proposal and the still-closing textarea. It now
  waits for the editor to close. Subsequent full project attempts were interrupted
  by execution-session loss; their partial counts are not reported as full passes.
  The final integration run must complete this suite again after all modules.

Representative actual UI captures are in evidence/batch-a/. They use synthetic
local projects or persisted injected job states; they are not concept images or
live-provider evidence. The helper frontend/scripts/check-overview-native-zoom.mjs
reproduces the native zoom assertions against a local synthetic project with saved
messages and at least one pending Brief change.

## Compatibility and next batch

Project fields are additive and both generated contract paths were regenerated.
Historical task contracts, media, applied Brief revisions and approvals remain.
The app/package release identity remains 1.8.2 at this batch boundary; update it
once on the final integrated 1.8.3 candidate. No real API calls, Safari/native Mac
checks, merge or release publication occurred.

The owner's later instruction authorizes continuing B, C, dashboard/Discover and
packaging without a batch review pause. This commit is the recoverable A boundary,
not a claim that all of 1.8.3 is complete.
