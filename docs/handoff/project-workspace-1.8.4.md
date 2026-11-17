# Video Anatomy 1.8.4 implementation handoff

- Owner: Frank / Yuqing Wu. Implementation coordinated by Codex.
- Scope: reference-report reliability, speech recovery/profile choice, Video and
  Series lifecycle management, useful Activity/recovery UI and larger file intake.
- Baseline: merged PR #20 at `d4f939f8904b345a05e7a05d818a72860a1b9bbe` on
  `fix/integration/video-anatomy-1-8-2`; its source tree matches delivered 1.8.3
  `c3c8ebf95ab9381b9eeb0de9b9b8a24d1bfcc45c`.
- Task branch: `fix/integration/1-8-4-reliability-planning`.
- Main was checked at `462bdd67b16a0883c9fd1a04e6778dd77ca4a566`; no automatic
  main merge, formal publication or deployment is authorized.

## Ownership and contracts

Integration owns models/API coordination, root navigation, Activity, Resources,
Source Review, release identity and packaging. Planning owns Video/Series
lifecycle and its UI. Synthesis and speech changes use separate function
boundaries in `analysis.py`, with explicit profile/parent/progress arguments.

Additive fields cover plan Trash, safe Series reassignment, original creative
title provenance and exact job parent/source scope. Both generated schema and
TypeScript are regenerated from the Pydantic model. Schema family remains 1.8.0.
Historical evidence, human edits, approvals and production/export revisions are
retained. Restore does not silently choose a Video or overwrite newer grouping.

## Findings and implementation

The owner supplied screenshots of 108-second and 75.8-second partial sources,
a 29.5-second source with available evidence, and a failed cross-source report.
They establish saved source observations and incomplete coverage, not the exact
provider failure. Their original diagnostics/media are not present in Cloud.

Static review and deterministic regressions establish two independent seams:
the old synthesis schema permitted an empty redundant citation index that host
validation then rejected; speech recovery treated overlapping old machine spans
like protected human corrections, producing persistent merge conflicts. Both
are addressed without accepting invalid source references or weakening timing
bounds. GPT file transcription is opt-in and marked as measured chunk-level
evidence; no unsupported phrase alignment is invented.

Project-runtime jobs now have exact parent IDs and frozen resource IDs. Phase
updates use real processing stages; no percentage or ETA is fabricated. Local
modal failures use actionable inline errors. The import limit is configurable
and displayed; only its default byte bound increases to 500 MiB.
Older jobs with no frozen scope are not assigned guessed source lists. Resources
offers an explicit saved-evidence-only report action with a previewed selection.
The model selector is disabled for that action; admission errors remain inside
the confirmation dialog. This final UI addition has separate focused and zoom
checks, rather than being attributed to an earlier frozen-source matrix.

## Verification

| Check actually run | Result |
| --- | --- |
| Complete Python suite (`.venv/bin/python -m pytest -q`) | 1,182 passed; one upstream Starlette/httpx deprecation warning |
| Python dependency check, generated schemas/types, Ruff | Passed |
| Frontend unit suite | 54 passed |
| TypeScript, ESLint and production build | Passed, including a fresh run after the final saved-evidence dialog change |
| Preserved legacy browser suite | 52 passed |
| Injected-provider browser suite | 4 passed; authored responses, not live inference |
| Complete project browser suite (`npm --prefix frontend run test:e2e:projects`) | 94 passed in 6.9 minutes; exit 0 |
| Desktop Node tests and syntax checks | 3 passed; syntax checks passed |
| Real Chromium Page zoom / narrow viewport | 63 main surface checks + 6 source/Activity checks + 3 final dialog checks passed |
| Local generated MP4 playback and paused seek | 1 passed; no recognition request |

`bash scripts/verify.sh` completed its backend, frontend unit/static/build,
legacy-browser and injected-provider groups. An execution-environment restart
interrupted the project group after 49 of its then-93 cases; that invocation is
not recorded as an exit-zero full script. After adding the legacy-job regression,
the complete 94-case project group was restarted separately. Results above count
complete groups, not the interrupted partial run or overlapping focused runs.

The first completed 94-case browser run had 93 passes and one old wording
assertion: Source Review now explains the saved `audio_timestamps_invalid`
diagnostic instead of showing only generic partial-transcript text. The test
was updated to require that precise explanation and independently verify saved
coverage remains `partial` with the same code. All original retry, busy-state,
sanitized-export, human-correction and reload assertions were retained. That
case passed independently before the final complete group was rerun; application
behavior was not changed to satisfy the old string.

The first full Python candidate exposed a real speech migration/retry regression
(1,173 passed, one failed). The implementation was corrected without weakening
the existing migration test; the final complete suite passed all 1,182 tests.
Transient development/HMR and harness-setup failures were resolved before the
reported final browser runs. The build retains a nonblocking Vite advisory for
a JavaScript chunk over 500 kB; no size/performance improvement is claimed.

Browser coverage includes zero/one/two Overview follow-ups, Stop/retry and late
reply exclusion; per-source partial status, saved-revision versus last-attempt
diagnostics, exact parent/source scope, report-only retries, and old jobs without
that scope; explicit speech profiles/chunk labels, import receipts and one-time
pre-admission version-conflict recovery; Video/Series lifecycle, busy errors,
readiness changes, retained approval/production history and exact sheet exports.
The 51 MiB intake check uses real streamed synthetic bytes to establish the byte
boundary, not a valid 51 MiB movie or decoder-quality test.

Native zoom used Chromium Page zoom at 100/125/150/200% in 1440×900 and 1280×800
outer windows (`visualViewport.scale=1`, CSS `zoom=1`, actual zoom/DPR recorded).
The 390 CSS-pixel case is a viewport check at native 100%, explicitly separate
from browser zoom. The main 63 checks, six supplementary checks and playback
use the frozen source snapshot in the evidence receipts. Resources/Activity
subsequently gained the saved-evidence dialog bridge; its three supplementary
checks retain the later file hashes. The earlier complete native matrix was not
rerun after those two application-file edits. There were zero processing POSTs;
the final dialog supplement checked reachability, Cancel/Escape and focus return
without clicking Generate. The separate browser regression exercises submission
with a deliberately unconfigured provider and verifies no recognition jobs or
evidence changes. Its expected `provider_not_configured` job is a test outcome,
not successful AI generation.

See [committed evidence](1.8.4/evidence/README.md) for representative screenshots,
receipts and source snapshots. Full local execution logs are retained outside
the checkout under `/workspace/artifacts/video-anatomy-184/`. The final source
commit, ZIP digest and archive-check result belong in the Draft PR and delivery
response, avoiding a self-referencing source/archive digest.

## Implementation commits

- `76d9815`: coordinated backend/models/generated contracts, report validation,
  speech recovery, plan lifecycle/readiness and larger configurable intake.
- `a43a911`: Content plan management UI, Production readiness and browser tests.
- `559ce38`: source diagnostics, job lineage, speech choices, import receipts
  and reliability browser tests.
- `7626dea`: explicit saved-evidence-only report generation for old jobs without
  frozen request scope, with an independent migration/browser regression.
- `5a27feb`: checks the specific speech timing explanation and persisted partial
  status while retaining the prior recovery assertions; application unchanged.
- The following release-evidence commit sets the consistent 1.8.4 identity and
  includes this handoff. Its full SHA is the archive's reviewed source identity.

## Tooling and limits

Modern Web Guidance uses the already verified official 1.0.1 plugin and pinned
CLI guide revision `2026_11_10-47b4c80e`. Planning consulted dialog, menu, forms,
CSS layout and responsive guides. Activity and intake consulted progress, forms
and accessibility, including indeterminate native progress, named controls and
centralized announcements. No application dependency was added for this tooling.

The retrieved guidance specifically says “put `autofocus` on the safe action”
for destructive dialogs, “DON'T auto-submit” for select changes, “Do NOT use
overflow: hidden to mask layout issues”, “Omit `value` for an indeterminate
state”, and “Announce completion without stealing focus”. These informed native
dialogs with safe initial focus, explicit Move buttons, scrollable responsive
layouts and truthful indeterminate progress. Actions use normal keyboard Tab
navigation instead of an incomplete ARIA menu with unsupported arrow behavior.
Source: [Google Chrome Modern Web Guidance](https://github.com/GoogleChrome/modern-web-guidance).

No paid inference or provider-budget reset is performed. Authored responses and
real local synthetic bytes establish state/timing/persistence behavior, not live
recognition accuracy. Actual Mac/Finder/Gatekeeper/Keychain/signing, Safari and
the owner's real Ro8/Ro10 requests remain untested when unavailable. Use the
[release checklist](../releases/1.8.4.md) for acceptance.
