# Video Anatomy 1.8.1 candidate handoff

- Owner: Frank / Yuqing Wu; implementation coordinated by Codex.
- Environment: Linux Codex Cloud. Local Mac installation was not executed.
- Branch: `fix/integration/video-anatomy-1-8-1`.
- Baseline: `5b72ac1f5a33a82c9aeeaa1e519edf8eefcfc5f8`, the verified open Draft
  PR #17 head. `main` remains `462bdd67b16a0883c9fd1a04e6778dd77ca4a566`.
- Arrangement: separate dependent PR targeting `feat/integration/video-anatomy-1-8`;
  PR #17's branch and scope remain unchanged. Neither PR is automatically merged.
- Exact delivered source commit: package manifest, About and final delivery report.

## Findings and changes

Legacy document-level overflow restrictions clipped the new workspace. The
project-mode root now explicitly owns document scrolling, wrapping and focus
visibility, with scoped overrides retaining the legacy workspace. Short and
zoom-equivalent viewports exercise expanded content, not just empty screens.

Saved project analysis already used transactional SQLite. No save-loss defect was
reproduced in the persistent store. User-visible causes included stacking reports,
scope selection, absent restoration of the last opened project, and archived
legacy Structure results not projected into Analysis. Finder uses the standard
library even when a prior Terminal session used an explicit custom directory.

Analysis now displays one current validated success per content/project scope.
History remains available behind an expansion. Invalid, stale-input, failed or
interrupted replacement cannot displace the last success. Real legacy Structure
graphs recover from frozen archives idempotently; newer project analysis remains
current. No fixed marketing template or synthetic fallback graph is generated.
The existing `LogicGraph`/layout implementation is adapted to per-resource
structures and exact source moments. The old all-in-one Structure workspace was
not mounted, since its task APIs and single-reference controls differ.

Exploratory concepts/directions accept empty instructions with usable context,
or usable references with missing context explicitly stated. Empty inputs receive
a starting question before job admission. An explicit visual-only choice filters
speech from provider context and permitted citations; input manifests and outputs
retain that limitation. Tailored production still requires confirmed context,
reviewed evidence and an approved direction. Existing production editing/export
behavior is retained.

Speech retries no longer stop just because partial evidence contains corrections.
They reuse successful results, request missing speech without unnecessary vision
calls, preserve corrected event identities/text/timing and distinguish no audio,
no speech detected, not analyzed and failed processing. Overlapping recovered
spans that cannot safely extend a correction remain an explicit review conflict;
text is never split across invented timestamps. Legacy diagnostic/coverage repair
must not overwrite successfully retried newer evidence.

The timestamped `whisper-1` adapter and endpoint remain unchanged. Existing
provider code distinguishes actual quota/billing codes from temporary 429 errors.
Prepared WAV cache validation checks actual samples and duration. User-facing
messages are readable; sanitized diagnostic categories stay in support details.

## Shared interfaces and ownership boundaries

`models.py` adds optional per-resource structures to Analysis, exploratory and
visual-only provenance to InputManifest, and sanitized diagnostic fields on
EvidenceRevision/Job. Existing project schema family stays 1.8.0, with additive
defaults for old records; application/release metadata is 1.8.1. Generated JSON
schema and TypeScript types stay synchronized.

Analysis and migration own current-success and archived-graph behavior. Speech
recovery is isolated in `speech_retry.py` plus the existing recognition adapter.
Planning owns readiness/context filtering. Integration owns HTTP admission,
release identity and packaging. UI changes stay under the project workspace;
Discovery remains reserved and production changes are limited to limitation
display and regression checks. These are implementation boundaries, not new
assignments for team members.

## Verification record

Final integration results are recorded here before delivery. Automated fixtures
are authored/synthetic and never evidence of live model quality.

| Category | Actual result |
| --- | --- |
| Backend regression | Final full run: 897 passed in 171.10 seconds. One Starlette TestClient dependency deprecation warning. |
| Frontend unit/type/lint/build | 46 unit tests passed; TypeScript, ESLint and production build passed. Nonblocking Vite bundle-size advisory (~520 kB). |
| Project browser | 22 passed in Chromium; after final scoped CSS fixes, all 12 layout cases passed again with stricter complete-control bounds and single-line timestamp checks. |
| Legacy browser / injected providers | 55 legacy tests and 4 injected-provider tests passed. These do not establish live provider quality. |
| Schema, lint, dependencies | Both Python/TypeScript contract paths, Ruff, pip check and git diff checks passed. |
| Extracted release package | Both archive variants passed CRC and all 142 file hashes, runtime instructions, version/commit metadata, static UI serving, and analysis persistence across relocated extracted installations with the same library. Final archives are regenerated from the clean delivered commit and rechecked. |
| Live provider / transcription accuracy | Not run: no API credential available. |
| macOS installation, signing, Keychain, Gatekeeper | Not run: Linux execution environment. ZIP remains unsigned and dependency-assisted. |

The layout matrix uses 1440×900, 1280×800, 1024×768 and 390×844, each at 100%, 125%
and 150% equivalents. Playwright sets effective CSS width/height to physical
viewport divided by zoom; this tests reflow equivalently but does not claim
Chrome's native menu zoom, device-pixel rasterization or OS scaling verification.
At 260 CSS px the graph uses deliberate panning and a full selected-node detail
surface. Node selection, keyboard panning and lower actions remain testable.
Screenshots show expanded resource coverage, player interaction, graph states and production export controls. The screenshot archive includes its matrix and inspection notes.
Screenshots are manually inspected; automated browser interaction is reported
separately from actual hands-on testing on the owner's operating system.

Package checks extract both ZIPs, verify manifest hashes and prerequisites,
load all professional generation modules from the extracted files, and exercise
the packaged local-server app against a temporary persistent library. No real
user media, keys, libraries or caches are bundled. Version and commit come from
the package manifest rather than whichever repository happens to surround it.

## Tester handoff

See [release notes and checklist](../releases/1.8.1.md) for safe existing-library
opening and custom-directory recovery. Use the existing team Google Sheet; no
URL is invented. Record version/commit, OS/browser, viewport/zoom,
project/reference, reproduction steps, expected/actual result, screenshot or
recording, severity and retest result. Frank reviews and assigns follow-up work.

Remaining limits: live API access and accuracy, creative usefulness, macOS/native
zoom behavior, optional OCR prerequisites and the existing sparse visual sampling
limits require representative testing. No merge, public deployment or release
signing is implied by this candidate.

Initial browser failures were stale test assumptions after intended project auto-reopen; the tests were updated and the complete 22-case suite passed. Manual screenshot review additionally caught graph-control contrast and a narrow export menu; both were fixed and the stricter layout matrix passed.
