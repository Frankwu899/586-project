# 1.8.5 verification record

All inference checks are offline or injected-provider tests. API credentials were unset and live tests disabled. Synthetic fixtures measure host behavior, not account quality or incident equivalence. Focused runs overlap complete runs and are not added to their counts.

| Check | Actual command / procedure | Result |
| --- | --- | --- |
| Complete backend, final source | `env -u OPENAI_API_KEY RUN_LIVE_MODEL_TESTS=0 .venv/bin/python -m pytest -q` | **1347 passed**, 273.47 s, no skips; `/tmp/185-backend-final-job-inputs.log` |
| Frontend complete unit suite | `npm --prefix frontend run test:unit` | **58 passed**, no skips/failures |
| Authoritative schemas | `.venv/bin/python scripts/export_contracts.py --check` and `scripts/export_project_contracts.py --check` | Passed |
| Generated TypeScript contracts | `npm --prefix frontend run contracts:check` and `project-contracts:check` | Passed |
| Dependencies and Python lint | `.venv/bin/python -m pip check`; `.venv/bin/python -m ruff check backend tests scripts` | Passed |
| Frontend checks/build | `npm --prefix frontend run typecheck`; `lint`; `build` | Passed; existing Vite >500 kB chunk advisory |
| Desktop script tests and syntax | `npm --prefix desktop test`; `npm --prefix desktop run check` | **3 passed**, syntax checks passed; not native installation |
| Complete preserved Chromium workspace | `npm --prefix frontend run test:e2e` | **52 passed**, 3.9 min; `/tmp/185-browser-legacy.log` |
| Complete project Chromium before the final report-text-only correction | `npm --prefix frontend run test:e2e:projects -- --output=/tmp/185-project-complete-results` | **111 passed**, 6.4 min; `/tmp/185-browser-project-complete.log` |
| Injected-provider Chromium | `npm --prefix frontend run test:e2e:providers` | **4 passed**, 28.4 s; `/tmp/185-browser-providers.log` |
| Affected report Chromium after final no-truncation fix | `npm --prefix frontend run test:e2e:projects -- project-analysis-185.spec.ts project-analysis-183.spec.ts --output=/tmp/185-report-limits-final-results` | **16 passed**, 1 min; `/tmp/185-report-limits-final.log` |
| Actual preview repair and print Chromium | `npm --prefix frontend run test:e2e:projects -- project-export-playback-185.spec.ts project-resources-183.spec.ts` | **20 passed**, 1.6 min; `/tmp/185-playback-export-browser-green.log` |
| Print pagination | Chromium PDF, 36 authored historical-r1 rows | **10 landscape pages**, repeated sheet headers, all markers once; first/third pages visually inspected; root independently opened the raster/PDF |
| Markdown renderer verification | Installed `marked` and `pandoc`, punctuation plus CRLF/CR fixtures | **6 passed**, no new runtime dependency; `/tmp/185-markdown-renderers.log` |
| Corrected whole-suite setup cases | Project planning restore and report scope/detail cases | **2 passed**, 14.7 s; original feature assertions preserved; `/tmp/185-project-targeted-final.log` |
| Independent final code review | Three separate read-only reviewers: core/evidence, generation/runtime, playback/export/report UI | No remaining actionable blocker in reviewed scopes; core **123 passed**, generation-boundaries/diagnostics **64 passed**, playback/exports **15 passed** independently. Last API diagnostic addition separately **5 passed**. These counts overlap full suites. A final frozen-job-input review independently passed 57 tests; old jobs retain null inputs and support exports exclude saved manifests. |

The prior complete backend run (1302 passed / 1 failed) exposed assignment loss from the new duration proposal; source behavior was corrected. Expanded runs passed 1341 and then 1344 before final frozen-job-input regressions; they are superseded by the 1347-case run above. The first complete project browser run was 109 passed / 2 failed due to missing details expansion and a premature read before restore completion. Both corrected tests passed together before the complete rerun. A second full project run passed 110 with one async mock teardown error; its saved-profile request was counted before the fixture response finished. Counting only completed responses preserves all model-choice assertions and the corrected case passed alone (10.4 s). Additional complete runs found in-flight route callback cleanup and a creation test entering background search before its modal closed. Explicit route draining (wait, never ignoreErrors) and dialog-closure waits fixed these without changing application behavior or feature assertions. The complete suite then passed all 111 cases.

The existing Starlette/httpx TestClient deprecation is the backend warning. No assertion was disabled, skipped or shortened to pass. Generated contracts were produced from authoritative models; old projects/reports retain unknown core provenance and their prior histories.

Runtime versions: Python 3.12.14, Node 24.19.0, npm 11.9.0, FFmpeg 7.1.5, installed Chromium on Linux. Browser output directories are isolated; interrupted/artifact-collision/port-rejected runs are not passing evidence.

No live model, original Ro-8, native Mac Chrome/Safari, Keychain installation, signing/notarization or real advertising/clinical quality check was performed. No total-time-to-network-timeout equivalence or paid-call speed/cost saving is claimed. See the separately recorded first/reused offline workflow measurements.

## Final report text correction

The full 111-case project run passed before a final requirement audit found that report coverage prose still used `failureMessage`, whose diagnostic formatter truncates at 500 characters. The new long-limit regression failed on the missing tail condition, then passed after rendering the report limitation as an escaped React text node. Error notices and support redaction were unchanged. After this two-line production change, all **16 affected report browser cases**, **58 frontend unit tests**, TypeScript, ESLint and production build passed. The 111-case group was not rerun after that narrow rendering change; it must not be reported as a post-fix full-suite run. An independent reviewer approved the privacy/escaping boundary.

Package preflight: **32 passed** in `tests/test_release_package.py tests/test_release_identity.py`. The actual clean-commit archive checker and SHA256 receipt are delivered alongside the archive and recorded in the PR; native Mac acceptance remains not run.
