# Video Anatomy — Preliminary Model/API Testing Findings

**Owner/workstream:** Andrea — model and API evaluation  
**Date:** 2026-11-03  
**Status:** Preliminary repository review and offline checks; no authorized live model comparison has been performed  
**Suggested repository location:** `docs/evaluation/ANDREA_MODEL_API_TESTING_STATUS_2026-11-03.md`

## Executive conclusion

Retain the currently configured GPT-6.1 Sol family as the comparison baseline, not as a proven optimal choice. Available repository QA observations and offline validation do not establish that a replacement model offers better quality, latency, reliability, or cost.

The next meaningful step is to establish a measured baseline on permission-cleared test videos, then compare one model variable at a time after the harness, inputs, and rubric are frozen.

## Verified implementation observations from the supplied repository ZIP

- **Runtime vs. specification:** The project includes a v0.7.5-derived runnable app and later generation-specification documentation. Do not assume that newer specification behavior is implemented without checking the running commit.
- **Model defaults:** `gpt-6.1-sol` is configured for vision, Structure, creative/Ideas, and M2; `gpt-6-luna` for research; and `whisper-1` for transcription. Runtime environment overrides and account access need verification. See `backend/app/providers/config.py` and the model catalog.
- **Vision/OCR architecture:** OCR is captured within frame-based vision analysis, not by a separately configured OCR engine. OCR latency is therefore not independently measured by the current combined vision request. See `backend/app/providers/recognition.py`.
- **Evaluation tooling:** `scripts/evaluate_modules.py`, `evaluation/manifests/workspace-redesign-v1.json`, and `docs/evaluation/` provide a reusable starting point for baseline metrics and quality review.
- **Historical QA:** `docs/evaluation/QA_TEST_RESULTS.csv` contains 23 QA cases: 15 pass, 3 need review, 2 fail, and 3 not tested. The reported Dior visual/OCR case shows missing on-screen text and an incomplete visual batch. This is an investigation lead, not proof of model-specific causation.
- **Offline checks:** One separate review environment successfully ran 78 selected offline/mock tests. The USC environment reported syntax/configuration checks but could not install everything needed for the full offline suite. These are environment-specific results, not live quality measurements. Neither environment completed a paid model-comparison run.

## Test readiness and blockers

| Item | Status | Meaning / next action |
|---|---|---|
| Repository source and evaluation harness | Available in supplied ZIP | Confirm the active deployment and commit before interpreting runtime results. |
| `lei-jun-recording` source media | **Blocked: waiting on teammate** | Obtain the approved original video, check its manifest hash, and perform non-paid preflight. |
| Reference transcript / OCR annotations | Not yet available | Obtain or create human-verified timestamps and text for accuracy scoring. |
| API credentials | User reports access to an API key | Keep the key in the local environment. Do not include it in commits, chats, screenshots, or reports. |
| API credits | User reports approximately $1 used and approximately $20 remaining | This balance is not independently verified. Keep spending permission distinct from credential access. |
| Frozen harness, test set, and rubric | Awaiting agreement on shared versions and inputs | Andrea can shortlist technically compatible model candidates, but comparisons should use the same frozen harness and calibrated review criteria. |
| Live quality, latency, success, and cost metrics | **Not measured** | Run only after authorization and successful preflight. |

## Proposed near-term plan

1. Obtain the permission-cleared `雷军掼蛋sample.mp4` and independent annotations. Follow the repository collector and manifest preflight without paid calls.
2. Coordinate with Frank on the fixed app commit, harness, and cache condition, and with Natalie on human scoring. Andrea owns selecting a shortlist of technically compatible model candidates. Perform paid tests only when evaluation spending is permitted.
3. Run the v0.7.5 baseline on the agreed inputs. Record the operation, model, input/evidence revision, validation status, attempts, quality score and reviewer, processing time, token/audio usage, estimated cost, and errors.
4. Investigate Dior OCR defects by separating sampled-frame coverage, vision text recognition, and batch/schema validation. Do not infer a model defect from missed text alone.
5. Compare candidate models using identical prompts and upstream evidence, changing only the model or configuration under evaluation. Report module-wise quality, latency, successful/partial results, and cost per usable result, including failures and repair calls.

## Provisional model-selection decision

- **Recommended now:** Keep GPT-6.1 Sol as the incumbent baseline and defer replacement decisions.
- **Not yet justified:** Any claim that GPT-6.1 Sol is best, cheapest, or fastest, or that a different OCR model will resolve known failures.
- **Decision rule for later:** Prioritize deterministic integrity and evidence grounding, then usable quality. Compare speed and cost only among configurations that meet the team’s agreed quality bar.

## Provenance and limitations

This report summarizes source inspection and previously recorded QA/offline observations. It contains no new live-video tests, no human-rated model-comparison dataset, and no verified provider billing statement. It is a draft for review with Frank and Natalie before inclusion in the project repository.

Never commit an API key, `.env` file, raw private media, or unsanitized provider logs.

## Evidence plan for the next baseline and comparison

A prepared test matrix is in `docs/evaluation/ANDREA_MODEL_TEST_MATRIX_2026-11-03.csv`. Its rows are planned, not completed. The matrix references repository cases and QA failures; it contains no new scores or latency measurements.

**Controls:** Preserve the model ID and parameters, app commit, prompt/skill version, input SHA-256, upstream evidence revision, cache condition, and execution status. First use the current `gpt-6.1-sol` defaults to establish a baseline. For later candidate comparisons, change only the model/configuration under evaluation; preserve verified upstream inputs and prompts. Check model availability and compatibility with the account and transport before choosing a challenger.

**Quality gates:**

1. Record integrity and grounding failures as failures, independent of scores.
2. Have a human reviewer evaluate applicable rubric dimensions on a 0–3 scale, with `N/A` allowed when accompanied by a reason.
3. Compare latency and cost only for candidates that meet agreed quality criteria.

Natalie owns rubric calibration; Andrea owns measurement and candidate comparison.

**Unit of evidence:** One row per operation, model, input, and run. Record the actual output status, attempts/repair, errors, elapsed time, reported usage, estimated cost, and QA notes. Do not fill blank measurements with zero. Keep historical QA observations separate from new live runs.

**Immediate next step:** Wait for the approved `雷军掼蛋sample.mp4`, collect it using `scripts/collect_evaluation_media.py`, verify the manifest/hash, and perform preflight-only validation. Until then, submit this memo and the matrix as a documentation-only pull request for review; do not claim that live testing or the proposed v0.7.6 behaviors have passed.