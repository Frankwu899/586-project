# Video Anatomy 1.8.3 approved handoff

The five specification files and eight UI references are verbatim copies of the
owner-provided handoff. SOURCE_MANIFEST.json records their SHA-256 digests.
The PRD defines planned behavior; screenshots supply layout direction.

## Current assignment

The owner's 17 November follow-up authorizes completing A, B and C, the shared
layout, Projects dashboard, reserved Discover page, integration regression and
one Mac testing ZIP without intermediate review stops. A is committed at
20e33d5. The original base remains bd93bfc884b70be81bbf93ddf2c72b42cea7dafc,
branch fix/integration/video-anatomy-1-8-2, open Draft PR #19. It depends on
open Draft #18 at fdfd57f7459050a2b3980d6c0ebe399d0c17749c and #17 at
5b72ac1f5a33a82c9aeeaa1e519edf8eefcfc5f8. Main was rechecked at
462bdd67b16a0883c9fd1a04e6778dd77ca4a566. No dependency merge is implied.

The single integration task branch is feat/integration/1-8-3-overview-layout;
its eventual Draft PR targets fix/integration/video-anatomy-1-8-2. Each batch
receives its own tested commit. Update the application/package version once on
the final 1.8.3 candidate. Deliver only Video-Anatomy-1.8.3-mac.zip, with exactly
README.txt and Video Anatomy.app at its root. No main merge, formal publication,
discovery crawler, editor, renderer or video generator is authorized.

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
