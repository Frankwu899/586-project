# Video Anatomy 1.8.5 candidate handoff

- **Task/owner:** Frank / prepare the next reviewable candidate, without merge, deployment or new paid inference.
- **Author/date/environment:** Codex integration and independent reviewers; November 17, 2026, America/Los_Angeles; Codex Cloud Linux.
- **Repository/branch:** `Frankwu899/586-project`, `feat/integration/1-8-5-candidate`.
- **Starting working copy:** clean `work` at `462bdd67b16a0883c9fd1a04e6778dd77ca4a566`; inspected remotes, branch, recent commits and AGENTS before edits.
- **Source baseline:** PR23 `a592119fc0fc39176d426eee96ffda28feefae69`, verified to contain PR22 `98d124d42bc5d534d5e891f23e58a0b51bdfba3b`. Both remained unmerged at initial inspection. The candidate is stacked on PR23, not main.
- **Final commit/PR/package:** recorded in the delivery section below and in the package's exact source manifest. No historical branch is rewritten or removed.

## Changes and shared interfaces

Read the [issue/fix matrix](1.8.5/issue-matrix.md), [architecture and migration](1.8.5/architecture.md), [offline first/cache measurements](1.8.5/offline-measurements.json), and [release notes](../releases/1.8.5.md).

Source-only cores now persist before synthesis; single and multiple entry points share this stage. Reuse keys cover original hash, evidence content/version, model, instruction, language/configuration and visual-only mode. Synthesis binds the exact cores, selection and brief. It reads compact source results/citation indexes and retains independently completed work on failure or Stop. Synthesis jobs persist the typed frozen input manifest before requesting a model; failed attempts retain their original version bindings and old jobs default to unknown inputs. No workflow-level automatic paid rerun was added.

The report contract and STRUCTURE generation instructions require short insight titles and compact method/flow/borrowing fields for new results. Host validation preserves material limitations, exact citations and source support. The default UI shows those fields and coverage limits; detailed graphs, observations/inferences, context and full references expand on request. Old reports retain missing fields and unknown core provenance.

Evidence recovery replaces complete accepted OCR samples before admitting distinct simultaneous lines. Native speech intervals and human corrections, including changed OCR timing/IDs, remain protected. Valid unordered speech is retained with a truthful partial/order issue. Timestamp and PCM tolerances were not enlarged.

Conversation grounding handles bounded faithful facts/restrictions and independently valid qualified content. Exact source input from QA is tested with explicitly synthetic returned responses; the original rejected raw response is unavailable. Duration is proposed for confirmation, not adopted; ambiguous/negated/conflicting timing stays unresolved. Production prerequisites appear before approval and existing brief invalidation stays intact. New creative audio is independent of unobserved reference audio; explicit silence/narration requirements and fixed approved claims remain protected.

Structured shots are authoritative for HTML, Markdown and CSV. Print layout, escaping, platform newlines, exact references and historical pack identities are preserved. Playback recovery validates actual original/proxy formats, full decode and frame mapping. Explicit preview reconstruction also repairs decodable wrong/truncated audio. Successful reconstruction or relink changes the player URL generation; repair does not invoke recognition.

Shared edits were coordinated: the analysis owner edited project models/analysis and regenerated schema/TypeScript together; evidence, conversation/planning, media/exports, report UI and release identity had separate owners. The integrator owned API/store lifecycle, client concurrency and operational support fields. Existing tests target the new source stage where graph validation moved; original feature assertions remain. Legacy schemas/task APIs remain intact.

## Verification method and intermediate failures

Used the repository-recorded exact skill versions: Superpowers `22f0b463e7a5e579904dd6211a520321035526f7` for systematic debugging, TDD, verification and review; wshobson/agents `9c61ab243def98f72da12abd41cfcf5bcd91af9d` for architecture patterns. The prior environment's skill files were absent, so those exact sources were recovered and read before implementation. Independent reviews used isolated context and read-only checkout access.

Meaningful red regressions preceded fixes. They covered same-time OCR/group recovery/correction provenance, grounded safe/unsafe statements and qualifications, held-request background conflicts, core reuse/stale input/Stop/peer failures, compact fields/support, audio/duration choices, actual broken previews, structured export and Markdown rendering. Unchanged characterization tests that already passed were not presented as red-first discoveries.

The first complete backend run had **1302 passed / 1 failed**: a duration suggestion accidentally suppressed the full reviewable assignment. The original assignment assertion was retained by identity, the source behavior was corrected, and duration remained unconfirmed. Final results below supersede that run. An intermediate report test correctly failed because its fixture had no confirmed context; the fixture was corrected without changing approval protection. A browser artifact-directory collision and one shared-port startup rejection were isolated with separate output directories and complete reruns; neither was counted as a product pass. The first complete project run had 109 passed / 2 failed: one old graph test needed to expand details after switching report scope, and one Series restore test read state before the successful POST completed (trace GET began 6 ms after the POST, which took 24.738 ms). The tests now expand the intended detail and await the restore response; all original assertions remain. Both corrected cases passed together before the complete rerun. A subsequent full run had 110 passed / 1 fixture teardown error: the saved-profile retry mock counted a request before its async fixture response finished and the API context closed. Counting only completed fixture responses removes that race while preserving all model-choice assertions; it was checked alone before the final full run.

Independent core review closed OCR timing/identity, Stop, limitations, exact citation union and diagnostic-attempt findings. Independent generation/runtime review covered grounding qualifications, sentence-order retention, duration negation, audio choices, scope conflicts and phase-clock truthfulness. Independent media/UI review closed cache reuse, wrong/truncated proxy audio, exact citation support, duplicate attribution, Markdown punctuation/newlines and print formatting.

Final checks run individually, with live inference disabled. No exit-zero invocation of combined `scripts/verify.sh` is claimed. Focused suites overlap complete suites; their counts must not be added together.

The final [verification record](1.8.5/verification.md) lists commands, actual results and intermediate failures.

Final backend verification passed **1347 tests**, with **58 frontend unit tests**. The complete project browser group passed **111** cases before a final report-text-only correction; all **16 affected report cases** passed afterward, including a condition beyond 500 characters. See the linked record for exact scope and package results.

## Evidence and environment limits

The uploaded standalone QA handoff was read, including the exact original Overview input and quoted OCR/speech example. Its companion screenshots/project JSON/raw model responses, original and human-edited production files, source videos and native Mac Chrome diagnostics were not supplied. No access to its Drive links or other local projects is claimed. The tests contain fictional WellPath and independent generic examples; the application has no fixed WellPath/medical industry behavior.

Real FFmpeg media and Chromium exercise playback and local recovery. The 36-shot synthetic historical-r1 sheet printed to 10 landscape pages with repeated headers and every marker once; first/third pages were visually inspected. This is authored synthetic content, never evidence that the original generated r1 was good or that human-edited r2 validates it.

First/cache measurements record local fake-provider/SQLite work only: first 83.788 ms (2 recognition adapters, 2 cores, 1 synthesis), reused upstream 18.013 ms (0 recognition/core, 1 synthesis), zero network calls. Tokens and billed cost are unknown. These measurements establish reuse, not provider speed, savings, accuracy or Mac performance. Total operation time is separate from network timeout/attempt configuration.

No paid API calls, ledger reset, model-baseline switch, merge or deployment occurred. Native macOS launcher/Keychain/Chrome/Safari acceptance and the cause of the original Ro-8 first-load failure remain **not verified**. The test archive is a source-based local launcher package; a Linux extraction smoke test does not replace native Mac acceptance.

Preserve the full application-data directory when moving/upgrading; do not transfer keys through Git. New defaulted fields allow old project records to load without fabricated core provenance. Completed analyses, evidence, corrections, approvals and pack histories remain durable; unfinished source attempts stop on restart and require explicit retry.

## Delivery provenance

The PR and package manifest record the published source commit. The companion archive-check receipt records SHA256, complete wrapper/payload hashes, archive structure and the extracted Linux smoke test. The archive contains only `README.txt` and `Video Anatomy.app` at the top level; its embedded English release packet preserves the issue, migration and verification notes. No native Mac or live model acceptance follows from package integrity.
