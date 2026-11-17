# Video Anatomy 1.8.3 approved handoff

The five specification files and eight UI references are verbatim copies of the
owner-provided handoff. SOURCE_MANIFEST.json records their SHA-256 digests.
The PRD defines planned behavior; screenshots supply layout direction.

## Current assigned batch

Only the shared layout foundation and stream A (Overview) are assigned.
The implementation base is bd93bfc884b70be81bbf93ddf2c72b42cea7dafc,
branch fix/integration/video-anatomy-1-8-2, open Draft PR #19. It depends on
open Draft #18 at fdfd57f7459050a2b3980d6c0ebe399d0c17749c and #17 at
5b72ac1f5a33a82c9aeeaa1e519edf8eefcfc5f8. Main was rechecked at
462bdd67b16a0883c9fd1a04e6778dd77ca4a566. No dependency merge is implied.

The task branch is feat/integration/1-8-3-overview-layout; its Draft PR targets
fix/integration/video-anatomy-1-8-2 to expose this batch only. Application and
package release identities remain 1.8.2 until the final integrated candidate.
Resources, Source Review, Analysis, Content plan and Production redesigns are
reserved for later assignments. No paid inference, release publication or merge
is part of this batch.

## Coordinated ownership

- Integration: ProjectApp, shared workspace CSS/client/status, API/model contract
  review, generated schemas/types, validation and delivery.
- Backend A: conversation policy, persisted attempts, scoped Stop/retry, the
  necessary project model/API additions and backend regression checks.
- Frontend A: Overview and its own component/styles, brief review, composer,
  keyboard/focus behavior and Overview browser checks.
- Guidance setup: official upstream plugin installation and retrieval evidence.

Shared edits are coordinated before implementation. The Stop route binds a
saved message to a unique attempt; replaying or completing an older attempt
cannot change the newer attempt. Brief drafts and adopted revisions stay
separate, with existing independent draft concurrency preserved. Generated
project schemas and TypeScript contracts are regenerated together, never edited
independently.
