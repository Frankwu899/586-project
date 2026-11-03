## Video Anatomy — Preliminary Model/API Testing Findings

**Owner/workstream:** Andrea — Model and API Evaluation
**Date:** 2026-11-03
**Status:** Repository review and local preflight completed; one live single-frame visual/OCR test completed; full-video baseline and controlled model comparison pending
**Repository location:** docs/evaluation/ANDREA_MODEL_API_TESTING_STATUS_2026-11-03.md
Related test matrix: docs/evaluation/ANDREA_MODEL_TEST_MATRIX_2026-11-03.csv

**Executive conclusion**

Retain the currently configured gpt-6.1-sol as the incumbent comparison baseline, not as a proven optimal choice. The first standalone live visual/OCR test succeeded and returned measurable latency, usage, and estimated cost. A manual review of the sampled frame identified at least one meaningful Chinese-character transcription error.

This is not evidence that gpt-6.1-sol is better or worse than another model: no controlled model comparison or full-video application baseline has been completed. The next meaningful experiment is to test the same verified input using the application’s production vision/OCR prompt and schema, then compare compatible model candidates under fixed conditions.

Verified implementation observations from the supplied repository ZIP

• Runtime vs. specification: The project includes a v0.7.5-derived runnable application and later generation-specification documentation. Newer specification behavior must not be treated as implemented without checking the running commit.
• Model defaults: gpt-6.1-sol is configured for vision, Structure, creative/Ideas, and M2; gpt-6-luna for research; and whisper-1 for transcription. Actual runtime overrides and account access should be recorded. See backend/app/providers/config.py and the model catalog.
• Vision/OCR architecture: OCR is part of frame-based vision analysis, not a separately configured OCR engine. The normal vision request combines visual observations and text extraction; it does not independently time OCR. See backend/app/providers/recognition.py.
• Evaluation tooling: scripts/evaluate_modules.py, scripts/collect_evaluation_media.py, evaluation/manifests/workspace-redesign-v1.json, and docs/evaluation/ provide the starting point for baseline measurements and QA review.
• Historical QA: docs/evaluation/QA_TEST_RESULTS.csv contains 23 recorded cases: 15 pass, 3 need review, 2 fail, and 3 not tested. The documented Dior case includes missed on-screen text and an incomplete visual batch. This is an investigation lead, not proof of model-specific causation.
• Offline checks: A separate review environment previously reported 78 selected offline/mock test passes; the USC environment reported syntax/configuration checks but could not complete its full suite. These are environment-specific observations, not live-quality measurements or controlled comparisons.

**Local setup and media verification**

|Check                      |Observed result                                                   |Interpretation                                                             |
|---------------------------|------------------------------------------------------------------|---------------------------------------------------------------------------|
|Python environment         |Python 3.12.16; `pydantic` 2.13.4 available                       |Local Python environment is usable for the evaluator.                      |
|Media tools                |FFmpeg 7.1 available                                              |A video frame was successfully extracted.                                  |
|Received Lei Jun source    |`雷军掼蛋sample.mp4`                                                  |Local test file received; it is not the pinned shared fixture.             |
|Received file SHA-256      |`d513429f8f93871e88f4db311228176c60d13a605f6edf049c3e0afa6346da69`|Locally verified against the received file.                                |
|Shared manifest SHA-256    |`e4b54aae1bfeabd65ad6d68f0f24dd9da2648a3566ee00f153e3adea024d2af5`|**Does not match** the received file; do not overwrite the shared manifest.|
|Local manifest             |`.local-data/evaluation/andrea-lei-jun.json`                      |Separate private manifest created for the received video.                  |
|Offline evaluator preflight|`preflight_only`; `paid_requests_sent: 0`                         |Local manifest accepted; this is not a video-quality or model test.        |
|Frame extraction           |`.local-data/evaluation/andrea-ocr/frame-003.jpg`                 |One frame extracted at approximately 00:03.                                |

Media provenance note: The hash mismatch establishes that the received MP4 is not byte-identical to the pinned shared fixture. It does not establish that either file is corrupt. The received file is a local exploratory input, not a substitute for the common comparison corpus. The user confirmed permission for private evaluation of the received video; the exact source revision and any team-required approval should remain documented separately.

**Preliminary live model testing results**

OCR-001 — Lei Jun single-frame visual/OCR test (2026-11-03)

**Configuration and measurements**

|Field                         |Recorded value                                                                                                          |
|------------------------------|------------------------------------------------------------------------------------------------------------------------|
|Model                         |`gpt-6.1-sol`                                                                                                           |
|Input                         |Received Lei Jun MP4, single extracted frame at approximately `00:03`                                                   |
|Frame artifact                |`.local-data/evaluation/andrea-ocr/frame-003.jpg` (local only)                                                          |
|Test type                     |Standalone visual/OCR API request using repository transport                                                            |
|Prompt/schema                 |Simplified single-frame extraction prompt and small custom JSON schema; **not** the production recognition prompt/schema|
|Request status                |Successful structured response                                                                                          |
|Provider attempts             |1                                                                                                                       |
|Elapsed time                  |6,574 ms (6.574 seconds)                                                                                                |
|Input tokens                  |607                                                                                                                     |
|Output tokens                 |216                                                                                                                     |
|Total tokens                  |823                                                                                                                     |
|Estimated API cost            |$0.003374 USD                                                                                                           |
|Output artifact               |`.local-data/evaluation/andrea-ocr/result.json` (local only)                                                            |
|Human-calibrated quality score|**Not assigned**                                                                                                        |

**Observed OCR and visual findings**

The model returned multiple prominent Chinese text elements, including 小米澎湃N90 Max, 仅供娱乐 禁止赌博, and 雷军. In a manual comparison against the supplied frame, one semantically meaningful character substitution was observed:

|Evidence             |Text                                                         |
|---------------------|-------------------------------------------------------------|
|Text visible in frame|`组了一个掼蛋局，大家有啥高招，求分享！`                                        |
|Model-extracted text |`组了一个攒蛋局，大家有啥高招，求分享！`                                        |
|Difference           |`掼` was transcribed as `攒`, changing the card-game term `掼蛋`.|

The response also included phone status and social-media engagement text, such as 2:25, On, and engagement counts. This is not a confirmed application defect: the simplified test prompt asked for all readable text, while the application’s production prompt contains instructions to exclude external interface chrome.

The visual description was broadly consistent with the visible vehicle interior and seated subject, but descriptive detail should be checked against the actual frame before being scored as grounded. No complete character error rate (CER), word error rate (WER), or calibrated human rubric score was calculated.

**Interpretation and limitations**

• The configured model/API connection returned a structured result successfully for one frame.
• The measured 6.574-second elapsed time and $0.003374 estimated cost apply only to this request, not to end-to-end video processing or provider billing.
• At least one OCR character error was identified by manual review. A complete reference transcription and standardized OCR score are still needed.
• This standalone experiment does not exercise production frame sampling, batch validation, transcription, Structure, Ideas, Storyboard, UI rendering, or recovery behavior.
• The simplified prompt and output schema differ from the production recognition pipeline, so production-prompt compliance and model-selection conclusions remain untested.

Provisional finding: gpt-6.1-sol demonstrated functional single-frame Chinese OCR and structured output, with a meaningful transcription error requiring follow-up. This is a useful baseline observation, not a model-selection winner.

**Test readiness and remaining blockers**

|Item                                          |Current status                                                  |Meaning / next action                                                                                                      |
|----------------------------------------------|----------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------|
|Repository source and evaluation harness      |Available in supplied ZIP and local Git clone                   |Record the active Git commit, model settings, and exact harness version for formal tests.                                  |
|Lei Jun local video                           |**Received and verified locally**                               |The received hash differs from the pinned source; keep local experiments separate.                                         |
|Official shared/pinned video                  |**Not verified as available**                                   |Obtain the byte-identical approved fixture or coordinate an explicit shared-fixture revision before formal comparisons.    |
|Reference transcript / OCR annotations        |**Incomplete**                                                  |A manual single-frame review exists; obtain independent, timestamped OCR and speech references for formal accuracy scoring.|
|API credentials                               |Configured in the local Terminal session                        |Do not commit, paste, or log the secret. Credential presence alone does not document spending authority.                   |
|API usage                                     |**One paid single-frame call completed**                        |823 tokens; $0.003374 estimated for this call. Full-video cost and provider billing not established.                       |
|API credits                                   |User previously reported approximately $1 used and $20 remaining|Balance not independently verified; distinguish credits, estimates, and any team spending rules.                           |
|Frozen harness, common corpus, rubric         |**Not yet confirmed for formal comparison**                     |Coordinate traceable versions and shared human review before ranking models.                                               |
|Full-video quality, latency, success, and cost|**Not measured**                                                |Perform a reproducible production-path baseline after required controls are in place.                                      |

**Proposed near-term plan**

1. Record OCR-001: Keep the raw output JSON and video frame locally; add one clearly labeled completed test row to the evaluation matrix. Do not commit the raw media or local cache.
2. Repeat with production behavior: Test the same frame using the repository’s actual vision/OCR prompt and schema, while holding model and input constant. Record prompt version, response, latency, usage, validation behavior, and estimated cost.
3. Establish shared references: Obtain or create independent Chinese on-screen text and speech annotations. Confirm permissions and keep the received video’s revision separate from the pinned team fixture.
4. Run the full v0.7.5 baseline: Once the shared harness/input is fixed, measure recognition, transcription, Structure, research, Ideas, Storyboard, validation, overall time, success/partial results, and cost where supported. Clearly mark stages that cannot be timed independently.
5. Compare candidates: Andrea selects technically compatible candidates and varies one model/configuration factor at a time, using the same input evidence, prompts, harness, and cache condition. Natalie calibrates and applies human quality scoring.
6. Investigate historical Dior OCR issues: Distinguish missing sampled-frame coverage, text recognition errors, and batch/schema-validation failures before attributing causation.

**Provisional model-selection decision**

• Recommended now: Keep gpt-6.1-sol as the incumbent baseline for future comparison.
• Supported by the new test: One standalone single-frame API request succeeded and surfaced a specific Chinese-character OCR error.
• Not yet justified: Claims that gpt-6.1-sol is the best, cheapest, fastest, or most accurate model; claims that the production OCR pipeline passes; or claims that replacing the model would fix the Dior issue.
• Decision rule for later: Treat deterministic integrity and evidence grounding as minimum requirements; compare speed and cost only among configurations that meet the team’s agreed quality and usability criteria.

**Evidence plan for the next baseline and comparison**

The test matrix is maintained in docs/evaluation/ANDREA_MODEL_TEST_MATRIX_2026-11-03.csv. Mark OCR-001 as a completed standalone experiment; keep the remaining planned cases clearly labeled as not run.

Controls: Record the model ID and settings, app commit, prompt/skill version, input SHA-256, upstream evidence revision, cache condition, and execution status. Use identical prompts and evidence when comparing models. Distinguish standalone single-frame results from real pipeline runs.

**Quality gates:**

1. Record integrity and grounding failures independently of numerical quality scores.
2. Have human reviewers evaluate applicable rubric dimensions on a 0–3 scale; allow N/A with a reason.
3. Report reviewer disagreements and do not substitute model self-critique for human review.
4. Compare cost, latency, reliability, and usable result rates only with clearly stated sample sizes and quality thresholds.

Unit of evidence: One row per operation, model, input, and run. Record actual output status, attempts/repair, errors, elapsed time, usage, estimated cost, and QA notes. Leave unmeasured fields blank or mark them not measured rather than entering zero.

**Provenance and limitations**

This report combines implementation observations from the supplied ZIP, historical team QA, reported offline checks, locally observed setup/preflight results, and one new live single-frame visual/OCR request. It does not contain a controlled model comparison, a complete independent reference transcript, a calibrated human quality score, a measured full-video baseline, or a verified provider billing statement.

Do not commit an API key, .env file, raw private media, local .local-data/ artifacts, or unsanitized provider logs. Keep the distinction between the received MP4 and the officially pinned corpus explicit.

**Immediate next step:** Add the OCR-001 measurements to the test matrix and review a production-prompt single-frame test plan. Continue using the local input only for exploratory testing; wait for the shared pinned fixture and frozen evaluation controls before presenting a formal model comparison to Frank and Natalie.