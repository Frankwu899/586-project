# Workspace redesign: product and interaction review

Status: design discussion, not an application implementation milestone.

## Context and requirements

The owner completed an initial live macOS trial and reported major workflow/UI
problems: a rigid four-stage funnel, disconnected areas, record-player/phone UI
polluting video evidence, status/errors outside the viewport, and an analysis
layout built from vertically stacked cards instead of a timeline workbench.

The owner requests PM/UX reconsideration before implementation, the new
`nextlevelbuilder/ui-ux-pro-max-skill` with Glassmorphism preference, a desktop
window experience, a feasibility answer for Mac DMG delivery, and clear media
storage/missing-file behavior. All future installers, launchers, package READMEs
and handoff materials must be English. The earlier design skill is no longer the
design authority. Chinese discussion and explicitly chosen Chinese output remain
valid.

## Where to continue

Read [the design review](../design/workspace-redesign/README.md), then its
specification and standalone clickable concept. All new workspaces and relaxed
prerequisites in that concept are proposals, not implemented application features.
Preserve the original evidence, recovery, approval and export protections while
reviewing which global gates should become action-specific.

The two questions presented in chat concern entry-path priority and allowing
creative drafting before/without reference analysis. Do not reinterpret the
absence of an answer as approval or repeat already confirmed Q1–Q3. Reconcile any
new owner answer with the design spec before implementing the changed contracts.

## Current implementation findings

- Imported media is already copied to `.local-data/live/media` in the local
  launcher's folder; SQLite maps task/video/storage IDs. Moving the original
  uploaded file does not break the retained copy. A fresh extracted app folder
  has a different default data root. Relinking and storage migration UI are absent.
- Vision/OCR sees full uncropped recording frames, and repeated OCR is emitted per
  sample. There is no content-region/mask/UI-exclusion contract.
- Current visual observations span sampled frames; precise scene/text-duration
  bars and spatial annotation overlays need additional data capabilities.
- Global busy state and top-only status/error rendering explain the observed
  interaction failures; proper background activity needs service support too.
- The current Linux executor cannot establish a built/tested macOS DMG. Native
  runtime bundling, stable app data, Keychain, macOS build/signing and install tests
  are future engineering work after the interaction is agreed.

## Scope and preservation

Design branch: `docs/design/workspace-redesign-review`, starting from
`a6d46b1b7f8a2619e6df787123152cf5afad8716` (citation fix, PR #7). Working tree was
clean at start. Three read-only parallel reviews covered product flow, media/native
delivery, and recording-noise/timeline constraints. A separate agent produced only
the standalone design prototype.

The requested skill was installed project-locally from pinned upstream commit
`56ea9cf174ed86786187daa9de0e6247cb0747e4`, using the upstream Codex template. Its
local search works and confirms Glassmorphism as an active style. See the
provenance document; this does not install a global skill on the owner's Mac.

No application files, saved data, providers or contracts were changed. No paid API,
public deployment, main merge, native packaging or model training occurred. The
review package contains English documentation and a self-contained simulated
HTML prototype, not credentials or user media. Actual prototype checks and their
limits are recorded in `docs/design/workspace-redesign/CHECKS.md`. Both local-HTTP
Playwright scripts passed, including local video preview, inline feedback,
independent drafting, approval invalidation and concurrent simulated operations.
Direct-file opening on macOS remains unverified; managed Cloud Chromium blocks
`file://`. The package documents a local HTTP fallback.
