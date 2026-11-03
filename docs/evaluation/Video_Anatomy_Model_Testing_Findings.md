Video Anatomy — Preliminary Model/API Testing Findings

Owner/workstream: Andrea — Model and API Evaluation
Date: 2026-11-03
Status: Repository review and local preflight completed; two live single-frame visual/OCR experiments completed; full-video baseline and controlled cross-model comparison pending
Repository location: docs/evaluation/ANDREA_MODEL_API_TESTING_STATUS_2026-11-03.md
Related test matrix: docs/evaluation/ANDREA_MODEL_TEST_MATRIX_2026-11-03.csv

Executive conclusion

Retain gpt-6.1-sol as the incumbent comparison baseline, not as a proven optimal model. Two standalone live visual/OCR experiments on the same Lei Jun frame succeeded and produced measurable latency, token usage, and estimated API cost.

Using the application’s production vision prompt and schema (OCR-002) instead of a simplified prompt (OCR-001) improved filtering of unrelated phone and social-media interface text. However, both tests mistranscribed the Chinese card-game term 掼蛋局 as 攒蛋局. A better structured extraction result does not by itself establish character-level OCR accuracy.

These results do not establish that another model would be better, nor do they measure the complete production recognition pipeline. The next useful diagnostic is to investigate the same text with clearer image presentation, then evaluate additional representative frames before deciding whether to compare challenger models. Formal model selection still requires a fixed harness, common evidence, and calibrated quality review.

Verified implementation observations from the supplied repository ZIP

• Runtime vs. specification: The project includes a v0.7.5-derived runnable application and later generation-specification documentation. Newer specification behavior must not be treated as implemented without checking the running commit.
• Model defaults: gpt-6.1-sol is configured for vision, Structure, creative/Ideas, and M2; gpt-6-luna for research; and whisper-1 for transcription. Actual runtime overrides and account access should be recorded. See backend/app/providers/config.py and the model catalog.
• Vision/OCR architecture: OCR is part of frame-based vision analysis, not a separately configured OCR engine. The normal vision request combines visual observations and text extraction; it does not independently time OCR. See backend/app/providers/recognition.py.
• Evaluation tooling: scripts/evaluate_modules.py, scripts/collect_evaluation_media.py, evaluation/manifests/workspace-redesign-v1.json, and docs/evaluation/ provide the starting point for baseline measurements and QA review.
• Historical QA: docs/evaluation/QA_TEST_RESULTS.csv contains 23 recorded cases: 15 pass, 3 need review, 2 fail, and 3 not tested. The documented Dior case includes missed on-screen text and an incomplete visual batch. This is an investigation lead, not proof of model-specific causation.
• Offline checks: A separate review environment previously reported 78 selected offline/mock test passes; the USC environment reported syntax/configuration checks but could not complete its full suite. These are environment-specific observations, not live-quality measurements or controlled comparisons.

Local setup and media verification

|Check                      |Observed result                                                   |Interpretation                                                                  |
|---------------------------|------------------------------------------------------------------|--------------------------------------------------------------------------------|
|Python environment         |Python 3.12.16; `pydantic` 2.13.4 available                       |Local Python environment is usable for the evaluator.                           |
|Media tools                |FFmpeg 7.1 available                                              |A video frame was successfully extracted.                                       |
|Received Lei Jun source    |`雷军掼蛋sample.mp4`                                                  |Local test file received; it is not byte-identical to the pinned shared fixture.|
|Received file SHA-256      |`d513429f8f93871e88f4db311228176c60d13a605f6edf049c3e0afa6346da69`|Locally verified against the received file.                                     |
|Shared manifest SHA-256    |`e4b54aae1bfeabd65ad6d68f0f24dd9da2648a3566ee00f153e3adea024d2af5`|**Does not match** the received file; do not overwrite the shared manifest.     |
|Local manifest             |`.local-data/evaluation/andrea-lei-jun.json`                      |Separate private manifest created for the received video.                       |
|Offline evaluator preflight|`preflight_only`; `paid_requests_sent: 0`                         |Local manifest accepted; this was not a video-quality or model test.            |
|Frame extraction           |`.local-data/evaluation/andrea-ocr/frame-003.jpg`                 |One frame extracted at approximately 00:03; reused for OCR-001 and OCR-002.     |

Media provenance: The hash mismatch establishes that the received MP4 is not byte-identical to the pinned shared fixture; it does not establish that either file is corrupt. The received file is a local exploratory input, not a substitute for the common comparison corpus. Permission for private evaluation was confirmed by the user; retain any team-required provenance and authorization records separately.

Preliminary live model testing results

OCR-001 — Simplified single-frame visual/OCR test (2026-11-03)

|Field                         |Recorded value                                                                                   |
|------------------------------|-------------------------------------------------------------------------------------------------|
|Model                         |`gpt-6.1-sol`                                                                                    |
|Input                         |Received Lei Jun MP4; frame at approximately `00:03`                                             |
|Frame artifact                |`.local-data/evaluation/andrea-ocr/frame-003.jpg` (local only)                                   |
|Test type                     |Standalone visual/OCR API request via repository transport                                       |
|Prompt/schema                 |Simplified extraction prompt and custom JSON schema; **not** production recognition prompt/schema|
|Output token limit            |1,200                                                                                            |
|Request status                |Successful structured response                                                                   |
|Provider attempts             |1                                                                                                |
|Elapsed time                  |6,574 ms (6.574 seconds)                                                                         |
|Input tokens                  |607                                                                                              |
|Output tokens                 |216                                                                                              |
|Total tokens                  |823                                                                                              |
|Estimated API cost            |$0.003374 USD                                                                                    |
|Output artifact               |`.local-data/evaluation/andrea-ocr/result.json` (local only)                                     |
|Human-calibrated quality score|**Not assigned**                                                                                 |

Observed findings: The model extracted prominent Chinese text, including 小米澎湃N90 Max, 仅供娱乐 禁止赌博, and 雷军. Manual frame review identified a meaningful character substitution: 掼 was rendered as 攒 in 掼蛋局. The output also contained phone status and engagement labels because this simplified prompt asked for all readable text.

Limitation: This is a one-frame standalone experiment, not a test of production prompt compliance, production frame sampling, multi-frame validation, or the full application pipeline.

OCR-002 — Production vision prompt/schema, same frame (2026-11-03)

|Field                         |Recorded value                                                                                                      |
|------------------------------|--------------------------------------------------------------------------------------------------------------------|
|Model                         |`gpt-6.1-sol`                                                                                                       |
|Input                         |**Same** received Lei Jun frame at approximately `00:03`                                                            |
|Frame artifact                |`.local-data/evaluation/andrea-ocr/frame-003.jpg` (local only)                                                      |
|Test type                     |Direct invocation of repository `OpenAIVisionProvider.extract()` with schema validation; **not** full-video analysis|
|Prompt version                |`visual-ocr-bounded-batches-v4-language`                                                                            |
|Prompt/schema                 |Application’s production vision prompt and `VisionOutput` schema                                                    |
|Explanation language          |English; source Chinese OCR preserved as written                                                                    |
|Output token limit            |5,000                                                                                                               |
|Request status                |Successful; validated structured response                                                                           |
|Provider attempts             |1                                                                                                                   |
|Elapsed time                  |11,089 ms (11.089 seconds)                                                                                          |
|Input tokens                  |1,956                                                                                                               |
|Output tokens                 |428                                                                                                                 |
|Total tokens                  |2,384                                                                                                               |
|Estimated API cost            |$0.0091685 USD                                                                                                      |
|Output artifact               |`.local-data/evaluation/andrea-ocr/result-production.json` (local only)                                             |
|Human-calibrated quality score|**Not assigned**                                                                                                    |

Extracted on-screen text:

仅供娱乐 禁止赌博
小米澎湃N90 Max
组了一个“攒蛋局”，大家有啥高招，求分享！

Observed findings: The production instructions filtered out unrelated phone status indicators, profile labels, and social-media engagement counts while retaining the principal text within the video. However, the model again rendered the card-game term 掼蛋局 as 攒蛋局.

Limitation: Only the production vision prompt and schema were exercised on one manually extracted frame; the production video sampler, batching, transcription, caching, and downstream modules were not executed. The output token limit and output schema also differed from OCR-001, so this experiment does not isolate the causal effect of prompt wording alone.

Side-by-side comparison — OCR-001 and OCR-002

|Metric / behavior            |OCR-001: simplified|OCR-002: production prompt/schema|
|-----------------------------|-------------------|---------------------------------|
|Model                        |`gpt-6.1-sol`      |`gpt-6.1-sol`                    |
|Input frame                  |Lei Jun at ~00:03  |**Same frame**                   |
|API attempts                 |1                  |1                                |
|Execution                    |Succeeded          |Succeeded; schema-validated      |
|Elapsed time                 |6.574 s            |11.089 s                         |
|Input tokens                 |607                |1,956                            |
|Output tokens                |216                |428                              |
|Total tokens                 |823                |2,384                            |
|Estimated cost               |$0.003374          |$0.0091685                       |
|External phone/social UI text|Included           |Excluded                         |
|Key Chinese OCR error        |`攒蛋局`              |`攒蛋局`                            |
|Calibrated human score       |Not assigned       |Not assigned                     |

Reference check for the key error:

|Evidence                 |Text                                                         |
|-------------------------|-------------------------------------------------------------|
|Text visible in the frame|`组了一个掼蛋局，大家有啥高招，求分享！`                                        |
|OCR-001                  |`组了一个攒蛋局，大家有啥高招，求分享！`                                        |
|OCR-002                  |`组了一个“攒蛋局”，大家有啥高招，求分享！`                                      |
|Meaningful difference    |`掼` → `攒`; the card-game term is mistranscribed in both runs.|

Interpretation: OCR-002 demonstrates improved filtering behavior relative to OCR-001 for this frame, but the observed Chinese-character error persisted. OCR-002 took longer and cost more for these individual requests. Because prompt length, schema complexity, output token limits, and output size differed, do not attribute those differences to model speed or claim a generally higher production cost from this sample.

Scope and measurement limits: Two paid single-frame requests were completed, with a combined 3,207 reported tokens and $0.0125425 estimated API cost. These sums are not an end-to-end application cost or a provider billing statement. There is no complete human-verified OCR transcript, CER/WER score, repeated-run reliability estimate, or controlled comparison against another model.

Test readiness and remaining blockers

|Item                                          |Current status                                                  |Meaning / next action                                                                                               |
|----------------------------------------------|----------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------|
|Repository source and evaluation harness      |Available in supplied ZIP and local Git clone                   |Record active Git commit, model settings, and exact harness version for formal tests.                               |
|Lei Jun local video                           |**Received and verified locally**                               |Received hash differs from pinned source; keep exploratory tests separate.                                          |
|Official shared/pinned video                  |**Not verified as available**                                   |Obtain the byte-identical approved fixture or coordinate an explicit shared-fixture revision for formal comparisons.|
|Reference transcript / OCR annotations        |**Incomplete**                                                  |Manual single-frame review exists; obtain independent timestamped OCR and speech references.                        |
|API credentials                               |Configured for the reported local test session                  |Never commit or display the secret; it may need reconfiguration in a new Terminal session.                          |
|API usage                                     |**Two paid standalone visual/OCR requests completed**           |3,207 total tokens and $0.0125425 combined estimated cost; not full-video cost or verified billing.                 |
|API credits                                   |User previously reported approximately $1 used and $20 remaining|Balance not independently verified; distinguish credits, cost estimates, and spending rules.                        |
|Frozen harness, common corpus, rubric         |**Not yet confirmed for formal comparison**                     |Coordinate traceable versions and shared human review before ranking models.                                        |
|Full-video quality, latency, success, and cost|**Not measured**                                                |Run a reproducible production-path baseline once required controls are in place.                                    |

Proposed near-term plan

1. Preserve OCR-001 and OCR-002: Keep raw result JSON and the test frame locally. Record both completed operations in the evaluation matrix without committing raw media or local cache files.
2. Investigate image clarity (OCR-003): Compare OCR on a clearer crop of the same subtitle with the same model and production vision prompt/schema, recording any changes to image presentation and resolution. This is a diagnostic, not a cross-model comparison.
3. Check another representative frame: Select a second approved frame with independently checked visible text to avoid overgeneralizing from a single Chinese subtitle.
4. Establish shared references: Obtain independent Chinese on-screen text and speech annotations and resolve the difference between the received MP4 and the pinned team fixture.
5. Run a full v0.7.5 baseline: After freezing the shared harness and inputs, measure recognition, transcription, Structure, research, Ideas, Storyboard, validation, overall time, result status, and cost wherever supported. Mark stages not independently timed.
6. Compare candidate configurations: Select only technically compatible model alternatives; hold inputs, upstream evidence, prompts, schema, harness, and cache condition fixed when comparing models. Ask Natalie to apply the calibrated human rubric.
7. Investigate Dior QA issues separately: Distinguish missing sampled-frame coverage, recognition errors, and batch/schema-validation failures before attributing causation.

Provisional model-selection decision

• Recommended now: Keep gpt-6.1-sol as the incumbent baseline for future comparison.
• Supported by current tests: Two standalone image requests succeeded; production prompting/schema improved exclusion of unrelated UI text; both tests showed the same meaningful Chinese-character transcription error.
• Not yet justified: Claims that gpt-6.1-sol is the best, cheapest, fastest, or most accurate model, or that a replacement OCR model will fix the observed error.
• Decision rule for later: Treat integrity and evidence grounding as minimum gates. Compare speed, cost, and reliability only among configurations that meet agreed quality and usability criteria.

Evidence plan for the next baseline and comparison

The test matrix is maintained in docs/evaluation/ANDREA_MODEL_TEST_MATRIX_2026-11-03.csv. Mark OCR-001 and OCR-002 as observed standalone experiments; keep full-pipeline and cross-model rows labeled as planned or blocked.

Controls: Record model ID and settings, app commit, prompt/skill version, input SHA-256, upstream evidence revision, cache condition, and execution status. Use identical prompts/schema and evidence when comparing different models. Clearly distinguish standalone single-frame tests from real pipeline runs.

Quality gates:

1. Record integrity and grounding failures separately from numerical quality scores.
2. Have human reviewers evaluate applicable rubric dimensions on a 0–3 scale; allow N/A with a reason.
3. Report reviewer disagreements and do not substitute model self-critique for human review.
4. Compare quality, latency, reliability, and cost using clear denominators, sample sizes, and agreed acceptance criteria.

Unit of evidence: One row per operation, model, input, and run. Record actual output status, attempts/repair, errors, elapsed time, usage, estimated cost, and QA notes. Leave unmeasured fields blank or mark them not measured; do not substitute zero.

Provenance and limitations

This report combines implementation observations from the supplied ZIP, historical team QA, reported offline checks, locally observed setup/preflight results, and two live single-frame visual/OCR experiments. It does not include a full-video production baseline, controlled cross-model comparison, complete independent transcript, calibrated human rubric score, or verified provider billing.

Do not commit API keys, .env files, raw private media, local .local-data/ artifacts, or unsanitized provider logs. Preserve the distinction between the received MP4 and the officially pinned corpus.

Immediate next step: Update the test matrix with the OCR-002 run and its observed metrics, then conduct a controlled image-clarity diagnostic (OCR-003). Do not present preliminary single-frame observations as a final model-selection result.