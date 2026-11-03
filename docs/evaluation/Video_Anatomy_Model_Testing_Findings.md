Video Anatomy — Preliminary Model/API Testing Findings

Owner/workstream: Andrea — Model and API Evaluation
Date: 2026-11-03
Status: Repository review and local preflight completed; four successful standalone visual/OCR experiments, one locally blocked challenger attempt, and one challenger response rejected by application validation. Full-video baseline and successful controlled cross-model quality comparison pending.
Repository location: docs/evaluation/ANDREA_MODEL_API_TESTING_STATUS_2026-11-03.md
Related test matrix: docs/evaluation/ANDREA_MODEL_TEST_MATRIX_2026-11-03.csv

⸻

Executive conclusion

Retain gpt-6.1-sol as the incumbent comparison baseline, not as a proven optimal model.

Six exploratory experiments have been recorded using the locally received Lei Jun video. Four successful single-frame visual/OCR requests used gpt-6.1-sol. A fifth experiment attempted gpt-6.1-terra but was blocked by repository capability configuration before any API request. A sixth experiment used gpt-6-luna, which returned an API response but failed application-level narrative-role validation.

Summary of findings:

* OCR-001 — Simplified prompt, full frame: gpt-6.1-sol misread the Chinese card-game term 掼蛋局 as 攒蛋局 and included unrelated phone/social interface text.
* OCR-002 — Production prompt/schema, full frame: gpt-6.1-sol correctly filtered unrelated interface text but repeated the 掼 → 攒 substitution.
* OCR-003 — Production prompt/schema, cropped and enlarged subtitle: gpt-6.1-sol correctly transcribed 掼蛋局 in this attempt.
* OCR-004 — Production prompt/schema, second full frame: gpt-6.1-sol correctly extracted the three principal manually checked Chinese text regions, including 掼蛋局.
* OCR-005 — Terra challenger: gpt-6.1-terra was rejected locally because the repository did not configure it for structured vision requests. No API request was sent.
* OCR-006 — Luna challenger: gpt-6-luna returned a response, but the application’s validator rejected its narrative-role assignments. The original response was not retained in the accessible result or usage logs, so OCR accuracy could not be determined.

OCR-003 suggests that image presentation may influence recognition, but cropping and enlargement changed simultaneously. The experiment cannot isolate the effect of scale, cropping, surrounding context, or sampling variability.

OCR-004 demonstrates that the baseline can correctly recognize the previously problematic term on another frame, but does not establish consistent accuracy.

The challenger attempts revealed two different compatibility issues: repository capability configuration for Terra and application-level output validation for Luna. Neither establishes that the underlying model is incapable of recognizing Chinese text.

Preliminary decision: Continue using gpt-6.1-sol as the working production baseline. A successful, quality-scored cross-model comparison has not yet been completed. Formal model selection remains pending the approved shared fixture, independent reference annotations, frozen evaluation controls, and calibrated human review.

⸻

Verified implementation observations from the supplied repository ZIP

* Runtime vs. specification: The project includes a v0.7.5-derived runnable application and later generation-specification documentation. Newer specification behavior must not be treated as implemented without checking the running commit.
* Model defaults: gpt-6.1-sol is configured for vision, Structure, creative/Ideas, and M2; gpt-6-luna for research; and whisper-1 for transcription. Actual runtime overrides and account access should be recorded. See backend/app/providers/config.py and the model catalog.
* Vision/OCR architecture: OCR is part of frame-based vision analysis, not a separately configured OCR engine. The normal vision request combines visual observations and text extraction; it does not independently time OCR. See backend/app/providers/recognition.py.
* Structured vision compatibility: The inspected repository’s STRUCTURED_VISION_MODELS allowlist includes reviewed GPT-4.1/GPT-4o variants and the models in GPT6_MODELS. The inspected GPT-6 catalog lists gpt-6.1-sol and gpt-6-luna, but not gpt-6.1-terra or gpt-6-sol. See backend/app/providers/transport.py and backend/app/providers/catalog.py.
* Local output validation: The production visual validator rejects duplicate narrative roles and combinations containing "other" alongside another role. This validation rule caused the observed OCR-006 rejection. See backend/app/providers/recognition.py.
* Evaluation tooling: scripts/evaluate_modules.py, scripts/collect_evaluation_media.py, evaluation/manifests/workspace-redesign-v1.json, and docs/evaluation/ provide the starting point for baseline measurements and QA review.
* Historical QA: docs/evaluation/QA_TEST_RESULTS.csv contains 23 recorded cases: 15 pass, 3 need review, 2 fail, and 3 not tested. The documented Dior case includes missed on-screen text and an incomplete visual batch. This is an investigation lead, not proof of model-specific causation.
* Offline checks: A separate review environment previously reported 78 selected offline/mock test passes; the USC environment reported syntax/configuration checks but could not complete its full suite. These are environment-specific observations, not live-quality measurements or controlled comparisons.

⸻

Local setup and media verification

Check	Observed result	Interpretation
Python environment	Python 3.12.16; pydantic 2.13.4 available	Local Python environment usable for evaluation.
Media tools	FFmpeg 7.1 available	Video frames successfully extracted.
Received Lei Jun source	雷军掼蛋sample.mp4	Local test file received; not byte-identical to pinned shared fixture.
Received file SHA-256	d513429f8f93871e88f4db311228176c60d13a605f6edf049c3e0afa6346da69	Locally verified against received file.
Shared manifest SHA-256	e4b54aae1bfeabd65ad6d68f0f24dd9da2648a3566ee00f153e3adea024d2af5	Does not match received file; do not overwrite shared manifest.
Local manifest	.local-data/evaluation/andrea-lei-jun.json	Separate private manifest created for received video.
Offline evaluator preflight	preflight_only; paid_requests_sent: 0	Manifest accepted; not a video-quality or model test.
Original frame	.local-data/evaluation/andrea-ocr/frame-003.jpg	Frame at approximately 00:03; used in OCR-001, OCR-002, OCR-005, and OCR-006.
Cropped subtitle frame	.local-data/evaluation/andrea-ocr/frame-003-subtitle-bottom.jpg	Cropped/enlarged version of original frame; used in OCR-003.
Second full frame	.local-data/evaluation/andrea-ocr/frame-004.jpg	Selected at approximately 60% of video duration; used in OCR-004.
API access	Key configured during testing; model listing retrieved	Access established for observed requests; key may need reconfiguration in new Terminal sessions.
Local provider cache	.local-data/provider-cache/usage.jsonl	Usage metadata retained; no raw OCR-006 response found in inspected cache directory.

Media provenance: The hash mismatch establishes that the received MP4 is not byte-identical to the pinned shared fixture; it does not establish that either file is corrupt.

The received file is a local exploratory input, not a substitute for the common comparison corpus. Permission for private evaluation was confirmed by the user; retain any team-required provenance and authorization records separately.

⸻

Preliminary live model testing results

OCR-001 — Simplified single-frame visual/OCR test (2026-11-03)

Field	Recorded value
Model	gpt-6.1-sol
Input	Received Lei Jun MP4; frame at approximately 00:03
Frame artifact	.local-data/evaluation/andrea-ocr/frame-003.jpg (local only)
Test type	Standalone visual/OCR API request via repository transport
Prompt/schema	Simplified extraction prompt and custom JSON schema; not production recognition prompt/schema
Output token limit	1,200
Request status	Successful structured response
Provider attempts	1
Elapsed time	6,574 ms (6.574 seconds)
Input tokens	607
Output tokens	216
Total tokens	823
Estimated API cost	$0.003374 USD
Output artifact	.local-data/evaluation/andrea-ocr/result.json (local only)
Human-calibrated quality score	Not assigned

Observed findings: The model extracted prominent Chinese text, including 小米澎湃N90 Max, 仅供娱乐 禁止赌博, and 雷军.

Manual frame review identified a meaningful character substitution: 掼 was rendered as 攒 in 掼蛋局.

The output also contained phone status and engagement labels because the simplified prompt asked for all readable text.

Limitation: This is a one-frame standalone experiment, not a test of production prompt compliance, production frame sampling, multi-frame validation, or the full application pipeline.

OCR-002 — Production vision prompt/schema, same frame (2026-11-03)

Field	Recorded value
Model	gpt-6.1-sol
Input	Same received Lei Jun frame at approximately 00:03
Frame artifact	.local-data/evaluation/andrea-ocr/frame-003.jpg (local only)
Test type	Direct invocation of repository OpenAIVisionProvider.extract() with schema validation; not full-video analysis
Prompt version	visual-ocr-bounded-batches-v4-language
Prompt/schema	Application’s production vision prompt and VisionOutput schema
Explanation language	English; source Chinese OCR preserved as written
Output token limit	5,000
Request status	Successful; validated structured response
Provider attempts	1
Elapsed time	11,089 ms (11.089 seconds)
Input tokens	1,956
Output tokens	428
Total tokens	2,384
Estimated API cost	$0.0091685 USD
Output artifact	.local-data/evaluation/andrea-ocr/result-production.json (local only)
Human-calibrated quality score	Not assigned

Extracted on-screen text:

仅供娱乐 禁止赌博
小米澎湃N90 Max
组了一个“攒蛋局”，大家有啥高招，求分享！

Observed findings: The production instructions filtered out unrelated phone status indicators, profile labels, and social-media engagement counts while retaining the principal text within the video.

However, the model again rendered the card-game term 掼蛋局 as 攒蛋局.

Limitation: Only the production vision prompt and schema were exercised on one manually extracted frame; the production video sampler, batching, transcription, caching, and downstream modules were not executed.

The output token limit and output schema also differed from OCR-001, so this experiment does not isolate the causal effect of prompt wording alone.

OCR-003 — Production vision prompt/schema, cropped and enlarged subtitle (2026-11-03)

Field	Recorded value
Model	gpt-6.1-sol
Source	Same Lei Jun frame at approximately 00:03 as OCR-001 and OCR-002
Image input	.local-data/evaluation/andrea-ocr/frame-003-subtitle-bottom.jpg (local only)
Transformation	Bottom subtitle area cropped and enlarged 3× using FFmpeg/Lanczos; surrounding video and interface context removed
Test type	Direct invocation of repository OpenAIVisionProvider.extract() with VisionOutput schema validation; not full-video analysis
Prompt version	visual-ocr-bounded-batches-v4-language (same as OCR-002)
Explanation language	English; Chinese OCR preserved as written
Output token limit	5,000 (same as OCR-002)
Request status	Successful; validated structured response
Provider attempts	1
Elapsed time	9,594 ms (9.594 seconds)
Input tokens	2,006
Output tokens	330
Total tokens	2,336
Estimated API cost	$0.0083135 USD
Output artifact	.local-data/evaluation/andrea-ocr/result-production-bottom-crop.json (local only)
Human-calibrated quality score	Not assigned

Extracted on-screen text:

组了一个“掼蛋局”，大家有啥高招，求分享！
弹

Observed findings: Unlike OCR-001 and OCR-002, the model correctly rendered the previously incorrect card-game term as 掼蛋局.

The cropped image contains only part of the original video frame, so it was not expected to preserve other visible text such as the product label or warning.

The 弹 output is a partial on-screen symbol/label and should not be scored without an independently checked reference for that region.

Interpretation and limitations: OCR-002 and OCR-003 used the same model, production prompt version, schema, and output token limit but different image presentations.

This is evidence that cropped/enlarged presentation changed the output on this input; it does not prove whether crop selection, loss of surrounding context, scale, sampling variability, or a combination caused the correction.

This is still not a production media-preparation run, repeated trial, calibrated quality score, or cross-model comparison.

OCR-004 — Production vision prompt/schema, second full frame (2026-11-03)

Field	Recorded value
Model	gpt-6.1-sol
Input	Second manually extracted frame from received Lei Jun MP4, selected at approximately 60% of video duration
Frame artifact	.local-data/evaluation/andrea-ocr/frame-004.jpg (local only)
Test type	Standalone production vision extraction and schema validation; not full-video analysis
Prompt version	visual-ocr-bounded-batches-v4-language
Prompt/schema	Production vision prompt and VisionOutput schema
Explanation language	English; source Chinese OCR preserved as written
Output token limit	5,000
Request status	Successful; validated structured response
Provider attempts	1
Elapsed time	5,105 ms (5.105 seconds)
Input tokens	1,956
Output tokens	224
Total tokens	2,180
Estimated API cost	$0.0071285 USD
Output artifact	.local-data/evaluation/andrea-ocr/result-production-frame004.json (local only)
Human-calibrated quality score	Not assigned

Extracted on-screen text:

逢五出对
仅供娱乐 禁止赌博
组了一个“掼蛋局”，大家有啥高招，求分享！

Observed findings: All three principal Chinese text regions matched the manually checked reference for this frame, including the previously problematic character 掼.

The output excluded unrelated phone/social interface text.

Interpretation: The baseline model demonstrated correct recognition of the card-game term on a second frame under the same production prompt/schema used in OCR-002 and OCR-003.

This does not prove that the model consistently recognizes the term or that image clarity alone explains the difference.

Limitations: This was one manually selected frame, not a production video-sampling or batching run. The test script recorded a placeholder source timestamp of 0.0 seconds; the actual extraction timestamp should be recovered and documented.

No independent complete OCR reference, character error rate, or calibrated human score was recorded.

OCR-005 — GPT-6.1 Terra challenger, locally blocked (2026-11-03)

Field	Recorded value
Candidate model	gpt-6.1-terra
Baseline model	gpt-6.1-sol (OCR-002)
Intended input	.local-data/evaluation/andrea-ocr/frame-003.jpg
Intended prompt/schema	Production visual-ocr-bounded-batches-v4-language and VisionOutput
Output token limit	5,000
Execution status	Blocked before API request
Error type	ProviderError
Error code	unsupported_model_capability
Error message	This model has not been configured for structured text/image responses; select a documented supported model.
Provider attempts	0
Elapsed time	Not recorded
Token usage	Not applicable; no request sent
Estimated API cost	No API request; no generation cost attributable to this attempt
Output artifact	.local-data/evaluation/andrea-ocr/result-terra-frame003.json (local only)
OCR quality score	Not applicable — model not executed

Observed findings: The account’s model listing included gpt-6.1-terra, but the repository’s structured-vision capability allowlist did not include it.

Inspection of backend/app/providers/transport.py showed that json_response() checks membership in STRUCTURED_VISION_MODELS before preparing and sending the request.

The catalog’s GPT6_MODELS is derived from GPT6_PRICES, which listed only gpt-6.1-sol and gpt-6-luna in the inspected checkout.

Interpretation: This is a repository compatibility/configuration limitation, not evidence of a model-level OCR failure.

Terra’s vision capabilities, structured-output behavior, accuracy, latency, and cost remain unmeasured.

Disposition: Preserve OCR-005 as a blocked challenger experiment. Do not assign an OCR quality score or modify the production capability allowlist solely to force this comparison.

OCR-006 — GPT-6 Luna challenger, production validation failure (2026-11-03)

Field	Recorded value
Candidate model	gpt-6-luna
Baseline model	gpt-6.1-sol (OCR-002)
Input	Same original frame at approximately 00:03
Frame artifact	.local-data/evaluation/andrea-ocr/frame-003.jpg (local only)
Test type	Standalone production vision request and local VisionOutput validation
Prompt version	visual-ocr-bounded-batches-v4-language
Explanation language	English
Output token limit	5,000
Retries	0
API request status	Response received
Application validation	Failed
Validation error	ValueError: invalid narrative roles
Provider attempts	1
Elapsed time	6,297 ms (6.297 seconds)
Input tokens	1,956
Output tokens	412
Total tokens	2,368
Estimated API cost	$0.000450425 USD
Output artifact	.local-data/evaluation/andrea-ocr/result-luna-frame003.json (local only; contains error/usage, not raw model response)
Human-calibrated quality score	Not assigned — validated OCR output unavailable

Observed findings: The API request completed and reported token usage. However, ProviderRecognitionAdapter._validate_visual() rejected the returned frame with invalid narrative roles.

Inspection of backend/app/providers/recognition.py identified the validation rule:

if len(set(frame.roles)) != len(frame.roles) or (
    "other" in frame.roles and len(frame.roles) > 1
):
    raise ValueError("invalid narrative roles")

This rule rejects duplicate narrative roles or an "other" role combined with additional roles.

The local result JSON preserved the validation error and request metrics but not the raw model response.

Inspection of .local-data/provider-cache/ found only usage.jsonl, which contained usage metadata without the generated visual observations.

Interpretation: Luna produced an API response but failed the application’s downstream acceptance criteria.

This is an observed production-schema/domain-validation compatibility failure for one request, not proof that Luna incorrectly transcribed the Chinese subtitle.

Cost observation: Luna’s estimated cost for this request was substantially below Sol’s estimated cost in OCR-002, but the responses had different lengths and Luna’s result was rejected.

This is not a valid cost-effectiveness ranking among usable outputs.

Disposition: Record OCR-006 as an attempted challenger comparison with failed application validation and unmeasured OCR accuracy.

Do not repair or silently normalize the roles for the primary production-compliance result. A future diagnostic may capture the raw response locally, subject to project privacy and logging rules, to distinguish text recognition from role-assignment failures.

⸻

Side-by-side comparison — OCR-001 through OCR-006

Metric / behavior	OCR-001	OCR-002	OCR-003	OCR-004	OCR-005	OCR-006
Model	gpt-6.1-sol	gpt-6.1-sol	gpt-6.1-sol	gpt-6.1-sol	gpt-6.1-terra	gpt-6-luna
Image input	Original frame	Same original frame	Cropped/enlarged original	Second full frame	Original frame intended	Original frame
Prompt/schema	Simplified/custom	Production	Production	Production	Production intended	Production
API attempts	1	1	1	1	0	1
Execution	Succeeded	Validated	Validated	Validated	Blocked locally	Validation failed
Elapsed time	6.574 s	11.089 s	9.594 s	5.105 s	N/A	6.297 s
Input tokens	607	1,956	2,006	1,956	N/A	1,956
Output tokens	216	428	330	224	N/A	412
Total tokens	823	2,384	2,336	2,180	N/A	2,368
Estimated cost	$0.003374	$0.0091685	$0.0083135	$0.0071285	No request	$0.000450425
Card-game term	Incorrect	Incorrect	Correct	Correct	Not evaluated	Unknown
Calibrated human score	Not assigned	Not assigned	Not assigned	Not assigned	N/A	Not assigned

Reference check: The visually checked subtitle contains:

组了一个“掼蛋局”，大家有啥高招，求分享！

OCR-001 and OCR-002 substituted 攒 for 掼. OCR-003 returned the correct 掼 after cropping and enlarging the original frame. OCR-004 also returned the correct 掼 on a second full frame.

OCR-005 produced no model response. OCR-006 produced a response that failed local validation, and the raw text was not retained in the accessible evaluation artifacts.

Interpretation: The four successful Sol tests demonstrate that production prompt compliance and character-level OCR accuracy are separate evaluation dimensions.

The Terra and Luna attempts also demonstrate that account-level model availability, repository capability support, and application-level output acceptance are separate gates.

The different elapsed times and estimated costs are individual observations, not statistically reliable speed or efficiency rankings.

⸻

Scope and measurement limits

Across OCR-001 through OCR-006:

Measure	Recorded total
Experiments	6
API requests sent	5
Successful application-validated OCR requests	4
Locally blocked attempts	1
API responses rejected by local validation	1
Total reported input tokens	8,481
Total reported output tokens	1,610
Total reported tokens	10,091
Combined estimated API cost	$0.028434925 USD

These totals combine five standalone API requests, including one whose response failed application-level validation.

They exclude OCR-005, which was blocked locally and made no API request.

The estimated costs are based on the repository’s pricing/accounting logic and are not independently verified provider billing.

No full-video recognition run, calibrated human quality score, complete OCR reference/CER, or successful cross-model quality comparison has been completed.

The model comparison remains preliminary: Sol produced four validated responses, Terra was blocked locally, and Luna returned a response that did not pass the application’s narrative-role validation.

No reliable comparative OCR accuracy ranking is possible from these results.

⸻

Test readiness and remaining blockers

Item	Current status	Meaning / next action
Repository source and evaluation harness	Available in supplied ZIP and local Git clone	Record active Git commit, model settings, and exact harness version for formal tests.
Lei Jun local video	Received and verified locally	Received hash differs from pinned source; keep exploratory tests separate.
Official shared/pinned video	Not verified as available	Obtain byte-identical approved fixture or coordinate explicit shared-fixture revision.
Reference transcript / OCR annotations	Incomplete	Manual review of selected regions exists; obtain independent timestamped OCR and speech references.
API credentials	Configured during reported test sessions	Never commit or display secret; may need reconfiguration in new Terminal sessions.
API usage	Five API requests across six experiments	10,091 tokens and $0.028434925 combined estimated cost; not full-video cost or verified billing.
API credits	User previously reported approximately $1 used and $20 remaining	Balance not independently verified; distinguish credits, cost estimates, and spending rules.
Sol production OCR	Four successful standalone requests	Preliminary baseline evidence; no full-video or calibrated accuracy measurement.
Terra challenger	Blocked by repository capability configuration	No API request or OCR quality result; determine whether a documented supported configuration exists before retesting.
Luna challenger	API response rejected by narrative-role validator	Raw output unavailable in inspected logs; investigate output compliance before further comparative testing.
Frozen harness, common corpus, rubric	Not yet confirmed for formal comparison	Coordinate traceable versions and shared human review before ranking models.
Full-video quality, latency, success, and cost	Not measured	Run reproducible production-path baseline once required controls are in place.

⸻

Proposed near-term plan

1. Preserve OCR-001 through OCR-006: Retain local raw results, frames, usage records, and error details. Record each operation separately in the evaluation matrix, including locally blocked and validation-failed attempts. Do not commit private media or local cache files.
2. Interpret the crop diagnostic cautiously: The 掼 error was corrected in OCR-003, but cropping and enlargement changed together. Do not treat the difference as proof that increasing resolution alone fixes OCR.
3. Expand representative-frame coverage: OCR-004 provided a second frame with manually checked Chinese text. Add further approved frames and independent references to assess whether observed recognition behavior generalizes.
4. Resolve the shared fixture: Obtain the byte-identical approved Lei Jun video or an explicitly revised shared fixture. Preserve the distinction between exploratory local tests and formal comparison inputs.
5. Investigate challenger compatibility: Terra was blocked by the repository allowlist; Luna returned an invalid narrative-role combination. Distinguish repository configuration, provider/API response behavior, and local validation before interpreting either as a model-quality failure.
6. Run a full v0.7.5 baseline: After freezing shared inputs and harness settings, measure recognition, transcription, Structure, research, Ideas, Storyboard, validation, overall elapsed time, result status, and cost wherever supported. Mark stages not independently timed.
7. Compare candidate configurations: Select technically compatible alternatives. Hold inputs, upstream evidence, prompts, schema, harness, and cache condition fixed. Ask Natalie to apply the calibrated human rubric.
8. Investigate Dior QA issues separately: Distinguish missing sampled-frame coverage, recognition errors, and batch/schema-validation failures before attributing causation.

⸻

Provisional model-selection decision

Recommended now: Retain gpt-6.1-sol as the incumbent production baseline for subsequent formal comparisons.

Evidence supporting this decision:

* Four standalone Sol vision requests completed successfully and passed the tested structured-output validation.
* Sol correctly filtered unrelated interface text under the production prompt in the full-frame experiments.
* Sol misread 掼 as 攒 in OCR-001 and OCR-002, but recognized 掼 correctly in OCR-003 and OCR-004.
* Terra was not configured for structured vision requests in the inspected repository and was blocked before execution.
* Luna was configured for structured vision and returned an API response, but its output failed narrative-role validation.

Not yet justified: Claims that Sol is the most accurate, fastest, cheapest, or universally most reliable model. The evidence does not establish Terra’s underlying capabilities or Luna’s Chinese OCR accuracy.

Decision rule for later: Require valid structured output, evidence grounding, and acceptable human-reviewed quality before comparing usable configurations on latency, reliability, and cost.

Preserve failed and blocked attempts in the evaluation denominator, distinguishing configuration failures from provider failures and application-validation failures.

Next comparison requirements: Use the approved shared media fixture, independent OCR annotations, a frozen prompt/schema/harness, identical frames and cache conditions, and a calibrated reviewer rubric.

Capture failure diagnostics safely without changing production validation behavior for the primary test.

⸻

Evidence plan for the next baseline and comparison

The test matrix is maintained in docs/evaluation/ANDREA_MODEL_TEST_MATRIX_2026-11-03.csv.

Mark OCR-001 through OCR-004 as observed successful standalone experiments, OCR-005 as locally blocked, and OCR-006 as an API response rejected by application validation.

Keep full-pipeline rows labeled as planned or blocked until executed.

Controls: Record model ID and settings, app commit, prompt/skill version, input SHA-256, upstream evidence revision, cache condition, and execution status.

Use identical prompts/schema and evidence when comparing different models. Clearly distinguish standalone single-frame tests from real pipeline runs.

Quality gates:

1. Record integrity, configuration, validation, and grounding failures separately from numerical quality scores.
2. Have human reviewers evaluate applicable rubric dimensions on a 0–3 scale; allow N/A with a reason.
3. Report reviewer disagreements and do not substitute model self-critique for human review.
4. Compare quality, latency, reliability, and cost using clear denominators, sample sizes, and agreed acceptance criteria.
5. Do not treat locally blocked requests or rejected responses as successful OCR outputs.
6. Retain failed attempts in reliability reporting without assigning unmeasured OCR accuracy scores.

Unit of evidence: One row per operation, model, input, and run.

Record actual output status, attempts/repair, errors, elapsed time, usage, estimated cost, and QA notes.

Leave unmeasured fields blank or mark them not measured; do not substitute zero.

⸻

Provenance and limitations

This report combines implementation observations from the supplied repository ZIP, historical team QA, reported offline checks, locally observed setup/preflight results, and six exploratory visual/OCR experiments.

Four experiments produced successful standalone Sol visual outputs. One Terra attempt was blocked before any API request. One Luna request returned an API response but failed application-level validation.

The tests used the locally received Lei Jun MP4, whose SHA-256 differs from the team’s pinned manifest.

These results do not constitute a full-video production baseline, successful controlled cross-model quality comparison, complete independent transcript, calibrated human rubric score, or verified provider billing.

The current evidence supports retaining Sol as the incumbent comparison baseline, not declaring it the optimal model.

Do not commit API keys, .env files, raw private media, local .local-data/ artifacts, or unsanitized provider logs.

Preserve the distinction between the received MP4 and the officially pinned corpus.

Immediate next step: Update the evaluation matrix with OCR-004, OCR-005, and OCR-006, preserving their distinct execution outcomes. Retain local JSON artifacts and usage logs without committing private media or secrets. Await the approved shared fixture and reference annotations before conducting a formal, quality-scored model-selection comparison.