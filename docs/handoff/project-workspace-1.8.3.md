# Video Anatomy 1.8.3 integrated candidate handoff

- **Task:** Complete A/B/C, shared workspace, Projects/Discover and one Mac test ZIP.
- **Owner:** Frank / Yuqing Wu; implementation coordinated by Codex.
- **Date/environment:** 17 November 2026, America/Los_Angeles; Linux Codex Cloud.
- **Repository:** Frankwu899/586-project at `/workspace/586-project`.
- **Branch:** `feat/integration/1-8-3-overview-layout` (retained as scope expanded).
- **Base:** `bd93bfc884b70be81bbf93ddf2c72b42cea7dafc`, open Draft #19;
  depends on Draft #18 at `fdfd57f7459050a2b3980d6c0ebe399d0c17749c` and
  Draft #17 at `5b72ac1f5a33a82c9aeeaa1e519edf8eefcfc5f8`.
  Main was checked at `462bdd67b16a0883c9fd1a04e6778dd77ca4a566`.
- **Authority:** The owner's full-delivery follow-up supersedes the earlier A-only
  review stop. The approved PRD and eight UI references remain canonical; copied
  kickoff instructions do not independently authorize actions.
- **Release/source receipt:** The final delivery response, attached Draft PR and
  ZIP manifest record the exact final source commit and archive SHA-256. No main
  merge, dependency merge or formal publication is authorized.

## Implementation boundaries

- `20e33d5`: shared layout and bounded Overview/Brief, persistent Stop attempts.
- `748a6a2`: exact Mac archive layout, clean-source provenance and wrapper hashes.
- `b2427a0`: stable folders, trash, exact insight links and shared B/C contracts.
- `0d669d2`: accessible dashboard, recent openings and reserved Discover.
- `10a38a7`: structured production, explicit references, topics and legacy exports.
- `c1f6156`: Media Pool, Source Review, source-linked Analysis and attachment reuse.
- `0ec97b5`: standalone Video planning and the authoritative sheet UI.
- `e0ac55e`: independent old-project and source/sheet integration checks.
- `4026349`: 1.8.3 candidate identity and reproducible native Chromium zoom QA.
- `3b2bf26`: one release identity for health, API metadata and provider diagnostics.
- `a8d3310`: explicit playback choices survive late media metadata callbacks.
- `660e820`: preserved task-workspace tests explicitly open `?legacy=1`.

Integration owns generated contracts, root navigation and final identity. Shared
model/API changes were reviewed before B/C consumers; generated JSON/TypeScript
were updated together. Workers used bounded file ownership. Per-module test
counts overlap and must not be added to obtain a full-suite result.

The storage/schema family remains 1.8.0 with additive defaults. Logical folders
never replace originals. Historical evidence, source/proxy clocks, human
corrections, adopted Briefs, approvals and legacy free-text packs remain. New
Video references are explicit; viewing Analysis or Resources does not choose
another production Video. A sheet revision is the source for editing and CSV.

## Verification record

The final acceptance components ran in Linux with live inference disabled:

| Component | Actual final result |
| --- | --- |
| Python dependencies, Ruff, authoritative/generated schema drift | Passed |
| Complete backend, `.venv/bin/python -m pytest -q` | **1,115 passed**, 218.53 seconds; no skips |
| Frontend unit tests | **54 passed** |
| Frontend contracts, TypeScript, ESLint, production build | Passed |
| Preserved-workspace Chromium group | **52 passed**, 3.8 minutes |
| Injected-provider Chromium group | **4 passed**, 26.4 seconds |
| Complete project/compatibility Chromium group | **77 passed**, 5.5 minutes |
| Desktop Node tests and JavaScript syntax checks | **3 passed**; syntax checks passed |
| Release identity, package and Mac-launcher scoped tests | **57 passed**, also covered by the backend suite |
| Full-workspace native Chromium zoom / narrow viewport | **63/63 surface checks**; 81 CDP screenshots, 9 saved-revision CSV receipts, zero processing requests |

The 133 browser cases above are distinct tests. The project group includes three
preserved `/api/tasks` menu/locale guards with explicit `?legacy=1` routing; the
other 52 preserved-workspace tests remain in their own group. Native zoom checks
are a separate surface matrix, not an additional count of those browser tests.
See [screenshots, dimensions and receipts](1.8.3/evidence/integrated/README.md).

The combined `bash scripts/verify.sh` run completed all components through the
52/4 browser groups, then exposed three legacy menu tests opening the modern
default homepage. That project run was deliberately interrupted (27 passed,
3 failed, 1 interrupted, 46 not run); it is **not** recorded as a successful
command. After fixing only their explicit entry URLs and passing all three
independently, the entire 77-case project group was rerun successfully with
`npm --prefix frontend run test:e2e:projects`. No application code changed in
that test-entry correction.

An earlier full backend candidate had 1,110 passes / five old-version diagnostic
assertion failures. Updating those checks also exposed a hardcoded health/API
metadata version; it now shares `release.VERSION`, and the 35-case diagnostic
group plus the complete 1,115-case backend passed. Independent review reproduced
a late `loadedmetadata` callback restoring an old citation after an explicit
playback choice. Its new regression failed before the fix and passed afterward;
it is included in the successful 77-case run. Earlier interrupted/partial A-only
runs are not counted as final acceptance.

Implementation is frozen at `a8d3310`; `660e820` changes only legacy test entry
URLs. The final documentation/evidence commit supplies the package source SHA.
After that clean commit, the single Mac ZIP must pass
`scripts/check_release_package.py --version 1.8.3 --expected-commit FULL_SHA`.
The exact final commit, archive SHA-256 and extracted-package results are
recorded in the integration Draft PR and delivery response, avoiding a
self-referencing archive digest in its source documentation.

Nonblocking diagnostics: Starlette TestClient/httpx deprecation, Vite's 581 kB
JavaScript chunk advisory and the test runner's color-environment warning.

## Modern Web Guidance

Official plugin 1.0.1 is installed/enabled from reviewed upstream commit
`64a6d708f5a43f2cd3fde5d4d7db3905ba1bdf65`. Pinned npm retrieval uses
`--skill-version 2026_11_10-47b4c80e`. Installation and scope evidence are in
[the setup receipt](1.8.3/modern-web-guidance-setup.md).

- **css-layout:** I used flexible tracks and shrinking content, following
  “Do NOT use `overflow: hidden` to mask layout issues”. Root overflow remains
  observable; intended panes own their scrolling.
- **responsive-design:** I adapted components with “`@container` queries” and
  retained ordinary document scrolling in short windows.
- **dialog:** I used native modal dialogs because the browser provides
  “inert page, focus containment, top layer”. Default Escape and focus return
  remain native; regular source navigation restores its own invoker separately.
- **accessibility:** I used the rule “Explicitly associate `<label>` with its
  control via `for`/`id`”, visible focus and ordered graph/shot reading alternatives.
- **ime-safe-enter-submit:** I paired `isComposing` with “`keyCode === 229`”
  to avoid the Safari confirming-Enter ordering pitfall; real Safari is untested.
- **forms:** I applied “`type="button"` on secondary or helper buttons” so Stop,
  review, file actions and navigation do not implicitly submit a form.
- **responsive-table:** I used semantic column/row headers and a named,
  keyboard-reachable local scroll region; eight UI columns become nine CSV
  fields because planned Start/End are numeric and separate.
- **lazy-load-video-and-audio / slider:** Media Pool creates no idle players;
  Source Review loads only opened media, uses native playback/range controls
  with source-time accessible values and a real saved-evidence alternative.

## Limits and morning handoff

Fixtures contain real locally generated bytes and authored provider/evidence
records. They establish state, persistence, timing boundaries and UI behavior;
they do not prove transcription accuracy, marketing conclusions, real account
access or creative usefulness. No paid inference or training was performed.
Safari and actual Mac installation, Finder, Gatekeeper, Keychain and signing were
not run. The single ZIP remains an unsigned dependency-assisted Finder launcher
requiring Python 3.12 and FFmpeg/ffprobe, not a self-contained DMG.

Source-only references with no evidence revision never borrow current evidence;
unknown legacy precision is preserved. Missing role segments or sound evidence
are not invented. Newly issued requests can already incur provider usage before
Stop reaches the provider, even though stale result writes remain blocked.

Use the short [release checklist](../releases/1.8.3.md). Keep the complete 1.8.2
library backup until Mac acceptance. No library, private media, credentials,
provider cache or generated ZIP is committed to source.
