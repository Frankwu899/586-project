Video Anatomy — Preliminary Model/API Testing Findings

Owner/workstream: Andrea — Model and API Evaluation
Date: 2026-11-03
Status: Repository review and local preflight completed; three live single-frame visual/OCR experiments completed; full-video baseline and controlled cross-model comparison pending
Repository location: docs/evaluation/ANDREA_MODEL_API_TESTING_STATUS_2026-11-03.md
Related test matrix: docs/evaluation/ANDREA_MODEL_TEST_MATRIX_2026-11-03.csv

Executive conclusion

Retain gpt-6.1-sol as the incumbent comparison baseline, not as a proven optimal model. Three standalone live visual/OCR experiments on the same Lei Jun frame have succeeded and produced measured elapsed times, token usage, and estimated API costs. These are exploratory single-frame tests, not a full-video baseline.

• OCR-001 — simplified prompt, full frame: misread the Chinese card-game term 掼蛋局 as 攒蛋局; included external phone and social interface text.
• OCR-002 — production prompt/schema, full frame: correctly filtered unrelated interface text but repeated the 掼 → 攒 error.
• OCR-003 — same production prompt/schema, cropped and enlarged subtitle: correctly transcribed 掼蛋局 in this attempt.

The OCR-003 result suggests that image presentation affects recognition on this example. Cropping removed contextual content and scaling enlarged existing pixels; this experiment cannot isolate the effect of scale from cropping, establish that the original image lacked resolution, or prove a general fix. No controlled comparison between different models has occurred. A second independently checked frame should be evaluated before choosing challenger models or revising production preprocessing.

Verified implementation observations from the supplied repository ZIP

• Runtime vs. specification: The project includes a v0.7.5-derived runnable application and later generation-specification documentation. Newer specification behavior must not be treated as implemented without checking the running commit.
• Model defaults: gpt-6.1-sol is configured for vision, Structure, creative/Ideas, and M2; gpt-6-luna for research; and whisper-1 for transcription. Actual runtime overrides and account access should be recorded. See backend/app/providers/config.py and the model catalog.
• Vision/OCR architecture: OCR is part of frame-based vision analysis, not a separately configured OCR engine. The normal vision request combines visual observations and text extraction; it does not independently time OCR. See backend/app/providers/recognition.py.
• Evaluation tooling: scripts/evaluate_modules.py, scripts/collect_evaluation_media.py, evaluation/manifests/workspace-redesign-v1.json, and docs/evaluation/ provide the starting point for baseline measurements and QA review.
• Historical QA: docs/evaluation/QA_TEST_RESULTS.csv contains 23 recorded cases: 15 pass, 3 need review, 2 fail, and 3 not tested. The documented Dior case includes missed on-screen text and an incomplete visual batch. This is an investigation lead, not proof of model-specific causation.
• Offline checks: A separate review environment previously reported 78 selected offline/mock test passes; the USC environment reported syntax/configuration checks but could not complete its full suite. These are environment-specific observations, not live-quality measurements or controlled comparisons.

Local setup and media verification

|Check                      |Observed result                                                   |Interpretation                                                                                                          |
|---------------------------|------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------|
|Python environment         |Python 3.12.16; `pydantic` 2.13.4 available                       |Local Python environment is usable for the evaluator.                                                                   |
|Media tools                |FFmpeg 7.1 available                                              |A video frame was successfully extracted.                                                                               |
|Received Lei Jun source    |`雷军掼蛋sample.mp4`                                                  |Local test file received; it is not byte-identical to the pinned shared fixture.                                        |
|Received file SHA-256      |`d513429f8f93871e88f4db311228176c60d13a605f6edf049c3e0afa6346da69`|Locally verified against the received file.                                                                             |
|Shared manifest SHA-256    |`e4b54aae1bfeabd65ad6d68f0f24dd9da2648a3566ee00f153e3adea024d2af5`|**Does not match** the received file; do not overwrite the shared manifest.                                             |
|Local manifest             |`.local-data/evaluation/andrea-lei-jun.json`                      |Separate private manifest created for the received video.                                                               |
|Offline evaluator preflight|`preflight_only`; `paid_requests_sent: 0`                         |Local manifest accepted; this was not a video-quality or model test.                                                    |
|Frame extraction           |`.local-data/evaluation/andrea-ocr/frame-003.jpg`                 |One frame extracted at approximately 00:03; reused for OCR-001 and OCR-002; OCR-003 used an enlarged crop of this frame.|

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

OCR-003 — Production vision prompt/schema, cropped and enlarged subtitle (2026-11-03)

|Field                         |Recorded value                                                                                                                            |
|------------------------------|------------------------------------------------------------------------------------------------------------------------------------------|
|Model                         |`gpt-6.1-sol`                                                                                                                             |
|Source                        |Same Lei Jun frame at approximately `00:03` as OCR-001 and OCR-002                                                                        |
|Image input                   |`.local-data/evaluation/andrea-ocr/frame-003-subtitle-bottom.jpg` (local only)                                                            |
|Transformation                |Bottom subtitle area cropped from the original frame and enlarged 3× using FFmpeg/Lanczos; surrounding video and interface context removed|
|Test type                     |Direct invocation of repository `OpenAIVisionProvider.extract()` with `VisionOutput` schema validation; **not** full-video analysis       |
|Prompt version                |`visual-ocr-bounded-batches-v4-language` (**same as OCR-002**)                                                                            |
|Explanation language          |English; source Chinese OCR preserved as written                                                                                          |
|Output token limit            |5,000 (**same as OCR-002**)                                                                                                               |
|Request status                |Successful; structured output returned                                                                                                    |
|Provider attempts             |1                                                                                                                                         |
|Elapsed time                  |9,594 ms (9.594 seconds)                                                                                                                  |
|Input tokens                  |2,006                                                                                                                                     |
|Output tokens                 |330                                                                                                                                       |
|Total tokens                  |2,336                                                                                                                                     |
|Estimated API cost            |$0.0083135 USD                                                                                                                            |
|Output artifact               |`.local-data/evaluation/andrea-ocr/result-production-bottom-crop.json` (local only)                                                       |
|Human-calibrated quality score|**Not assigned**                                                                                                                          |

Extracted on-screen text:

组了一个“掼蛋局”，大家有啥高招，求分享！
弹

Observed findings: Unlike OCR-001 and OCR-002, the model correctly rendered the previously incorrect card-game term as 掼蛋局 in this single request. The cropped image contains only part of the original video frame, so it was not expected to preserve other visible text such as the product label or warning. The 弹 output is a partial on-screen symbol/label and should not be scored without an independently checked reference for that region.

Interpretation and limitations: OCR-002 and OCR-003 used the same model, production prompt version, schema, and output token limit but different image presentations. This is evidence that cropped/enlarged presentation changed the output on this input; it does not prove whether crop selection, loss of surrounding context, scale, sampling variability, or a combination caused the correction. This is still not a production media-preparation run, a repeated trial, a calibrated quality score, or a cross-model comparison.

Side-by-side comparison — OCR-001 through OCR-003

|Metric / behavior            |OCR-001: simplified |OCR-002: production/full frame|OCR-003: production/cropped subtitle         |
|-----------------------------|--------------------|------------------------------|---------------------------------------------|
|Model                        |`gpt-6.1-sol`       |`gpt-6.1-sol`                 |`gpt-6.1-sol`                                |
|Image input                  |Full frame at ~00:03|**Same full frame**           |Cropped and enlarged region of **same frame**|
|Prompt/schema                |Simplified/custom   |Production `VisionOutput`     |**Same production** `VisionOutput` as OCR-002|
|Output token limit           |1,200               |5,000                         |5,000                                        |
|API attempts                 |1                   |1                             |1                                            |
|Execution                    |Succeeded           |Succeeded; schema-validated   |Succeeded; schema-validated                  |
|Elapsed time                 |6.574 s             |11.089 s                      |9.594 s                                      |
|Input tokens                 |607                 |1,956                         |2,006                                        |
|Output tokens                |216                 |428                           |330                                          |
|Total tokens                 |823                 |2,384                         |2,336                                        |
|Estimated cost               |$0.003374           |$0.0091685                    |$0.0083135                                   |
|External phone/social UI text|Included            |Excluded                      |Mostly absent from crop; **not comparable**  |
|Card-game term               |**Incorrect** `攒蛋局` |**Incorrect** `攒蛋局`           |**Correct** `掼蛋局`                            |
|Calibrated human score       |Not assigned        |Not assigned                  |Not assigned                                 |

Reference check: The visually checked subtitle contains 组了一个“掼蛋局”，大家有啥高招，求分享！. OCR-001 and OCR-002 substituted 攒 for 掼 (with minor punctuation variation). OCR-003 returned the correct 掼 in its cropped image.

Interpretation: OCR-003 corrected the specific Chinese character error under a changed image presentation. Comparing OCR-002 to OCR-003 is more controlled than OCR-001 to OCR-002, but cropping and enlargement both changed together, and request-to-request variation is not measured. The different elapsed times and costs are individual observations, not speed or efficiency rankings.

Scope and measurement limits: Three paid standalone single-frame requests yielded 5,543 total reported tokens (4,569 input; 974 output) and $0.020856 estimated combined API cost. These totals are not an end-to-end application cost or verified provider bill. No full-video recognition run, human-calibrated score, complete OCR reference/CER, or cross-model comparison has been performed.

Test readiness and remaining blockers

|Item                                          |Current status                                                  |Meaning / next action                                                                                               |
|----------------------------------------------|----------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------|
|Repository source and evaluation harness      |Available in supplied ZIP and local Git clone                   |Record active Git commit, model settings, and exact harness version for formal tests.                               |
|Lei Jun local video                           |**Received and verified locally**                               |Received hash differs from pinned source; keep exploratory tests separate.                                          |
|Official shared/pinned video                  |**Not verified as available**                                   |Obtain the byte-identical approved fixture or coordinate an explicit shared-fixture revision for formal comparisons.|
|Reference transcript / OCR annotations        |**Incomplete**                                                  |Manual single-frame review exists; obtain independent timestamped OCR and speech references.                        |
|API credentials                               |Configured for the reported local test session                  |Never commit or display the secret; it may need reconfiguration in a new Terminal session.                          |
|API usage                                     |**Three paid standalone visual/OCR requests completed**         |5,543 total tokens and $0.020856 combined estimated cost; not full-video cost or verified billing.                  |
|API credits                                   |User previously reported approximately $1 used and $20 remaining|Balance not independently verified; distinguish credits, cost estimates, and spending rules.                        |
|Frozen harness, common corpus, rubric         |**Not yet confirmed for formal comparison**                     |Coordinate traceable versions and shared human review before ranking models.                                        |
|Full-video quality, latency, success, and cost|**Not measured**                                                |Run a reproducible production-path baseline once required controls are in place.                                    |

Proposed near-term plan

1. Preserve OCR-001 through OCR-003: Keep raw result JSON, the test frame, and the enlarged crop locally. Record all three completed operations in the evaluation matrix without committing raw media or local cache files.
2. Interpret the crop diagnostic cautiously: The 掼 error was corrected in OCR-003, but cropping and enlargement changed together. Do not treat the difference as proven evidence that increasing resolution alone fixes OCR.
3. Check another representative frame: Select a second approved frame with independently checked visible text to avoid overgeneralizing from a single Chinese subtitle.
4. Establish shared references: Obtain independent Chinese on-screen text and speech annotations and resolve the difference between the received MP4 and the pinned team fixture.
5. Run a full v0.7.5 baseline: After freezing the shared harness and inputs, measure recognition, transcription, Structure, research, Ideas, Storyboard, validation, overall time, result status, and cost wherever supported. Mark stages not independently timed.
6. Compare candidate configurations: Select only technically compatible model alternatives; hold inputs, upstream evidence, prompts, schema, harness, and cache condition fixed when comparing models. Ask Natalie to apply the calibrated human rubric.
7. Investigate Dior QA issues separately: Distinguish missing sampled-frame coverage, recognition errors, and batch/schema-validation failures before attributing causation.

Provisional model-selection decision

• Recommended now: Keep gpt-6.1-sol as the incumbent baseline for future comparison.
• Supported by current tests: Three standalone image requests succeeded. Production prompting/schema filtered unrelated interface text on the full frame. OCR-001 and OCR-002 misread 掼 as 攒; OCR-003 recognized 掼 correctly after cropping and enlarging the subtitle.
• Not yet justified: Claims that gpt-6.1-sol is the best, cheapest, fastest, or most accurate model, or that a replacement OCR model will fix the observed error.
• Decision rule for later: Treat integrity and evidence grounding as minimum gates. Compare speed, cost, and reliability only among configurations that meet agreed quality and usability criteria.

Evidence plan for the next baseline and comparison

The test matrix is maintained in docs/evaluation/ANDREA_MODEL_TEST_MATRIX_2026-11-03.csv. Mark OCR-001, OCR-002, and OCR-003 as observed standalone experiments; keep full-pipeline and cross-model rows labeled as planned or blocked.

Controls: Record model ID and settings, app commit, prompt/skill version, input SHA-256, upstream evidence revision, cache condition, and execution status. Use identical prompts/schema and evidence when comparing different models. Clearly distinguish standalone single-frame tests from real pipeline runs.

Quality gates:

1. Record integrity and grounding failures separately from numerical quality scores.
2. Have human reviewers evaluate applicable rubric dimensions on a 0–3 scale; allow N/A with a reason.
3. Report reviewer disagreements and do not substitute model self-critique for human review.
4. Compare quality, latency, reliability, and cost using clear denominators, sample sizes, and agreed acceptance criteria.

Unit of evidence: One row per operation, model, input, and run. Record actual output status, attempts/repair, errors, elapsed time, usage, estimated cost, and QA notes. Leave unmeasured fields blank or mark them not measured; do not substitute zero.

Provenance and limitations

This report combines implementation observations from the supplied ZIP, historical team QA, reported offline checks, locally observed setup/preflight results, and three live single-frame visual/OCR experiments. It does not include a full-video production baseline, controlled cross-model comparison, complete independent transcript, calibrated human rubric score, or verified provider billing.

Do not commit API keys, .env files, raw private media, local .local-data/ artifacts, or unsanitized provider logs. Preserve the distinction between the received MP4 and the officially pinned corpus.

Immediate next step: Add OCR-003 to the test matrix, then select another permission-cleared frame with independently checked on-screen text and run a comparable controlled test. Preserve the current frame and raw outputs locally. Do not present exploratory single-frame observations as a final model-selection result.