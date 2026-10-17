# Budgeted live evaluation

[`scripts/live_validate.py`](../scripts/live_validate.py) runs real OpenAI recognition only after explicit opt-in, backend credentials, an approved positive budget, permitted local clips, independent human annotations, and operator-verified pricing are supplied. The implementation's offline tests use synthetic responses and establish integration behavior; they do not establish English/Chinese recognition quality. No paid run or human linguistic evaluation is claimed by this guide.

Run commands from the repository root after following [README_SETUP.md](../README_SETUP.md). Python dependencies and ffmpeg/ffprobe are required. The harness uses a file-locking budget ledger on Linux/macOS; native Windows operation has not been implemented.

## Default-off behavior

This command makes no provider requests and does not create evaluation output:

```bash
RUN_LIVE_MODEL_TESTS=0 .venv/bin/python scripts/live_validate.py
```

It prints `status=not_run`. Omitting `RUN_LIVE_MODEL_TESTS` has the same result. The ordinary offline verification command does not opt in to this harness.

## Prepare permitted clips and reference annotations

Keep local inputs under ignored `.local-data/live-inputs/`. Supply four to eight MP4 clips, with at least one of each `case_id`: `english`, `chinese`, `mixed`, and `cross_language`. Each case must include both spoken content and on-screen text because this suite evaluates the two channels separately. A no-audio regression is covered by offline media/provider tests and does not replace a bilingual acceptance case.

For every file, record the right to send its required frame/audio excerpts to the configured provider, its actual SHA-256, and separate human transcriptions of speech and screen text. The manifest's paths resolve relative to the manifest file. The harness checks the permitted hash before intake and against the saved original afterward. It preserves the original and applies the existing intake limits: MP4, supported H.264 or SDR HEVC, at most 50 MiB by the harness, and the configured duration/dimension limits, normally 180 seconds and 1920 by 1920.

The JSON below is an **unusable template with synthetic example wording**, not permission, real annotations, or recognized results. Replace every placeholder and all timing/text with what the actual clips contain. Set `permitted` to `true` only after establishing rights for that particular file. Include additional spans where needed. A required nonempty annotation cannot stand in for inaudible or absent content; choose a suitable acceptance clip and record ambiguities honestly.

Save the completed manifest as `.local-data/live-inputs/manifest.json`:

```json
{
  "clips": [
    {
      "case_id": "english",
      "path": "clips/english.mp4",
      "sha256": "REPLACE_WITH_ACTUAL_64_CHARACTER_SHA256",
      "permitted": false,
      "rights_note": "REPLACE_WITH_SPECIFIC_SOURCE_AND_PERMISSION",
      "expected_speech": [
        {"start_seconds": 0.5, "end_seconds": 2.8, "text": "Open the DemoCup lid."}
      ],
      "expected_on_screen_text": [
        {"start_seconds": 1.0, "end_seconds": 3.5, "text": "500 ml · $19.99 · Shop now"}
      ]
    },
    {
      "case_id": "chinese",
      "path": "clips/chinese.mp4",
      "sha256": "REPLACE_WITH_ACTUAL_64_CHARACTER_SHA256",
      "permitted": false,
      "rights_note": "REPLACE_WITH_SPECIFIC_SOURCE_AND_PERMISSION",
      "expected_speech": [
        {"start_seconds": 0.4, "end_seconds": 2.7, "text": "旋开杯盖，随时喝水。"}
      ],
      "expected_on_screen_text": [
        {"start_seconds": 0.8, "end_seconds": 3.2, "text": "500 毫升 · ¥99 · 立即选购"}
      ]
    },
    {
      "case_id": "mixed",
      "path": "clips/mixed.mp4",
      "sha256": "REPLACE_WITH_ACTUAL_64_CHARACTER_SHA256",
      "permitted": false,
      "rights_note": "REPLACE_WITH_SPECIFIC_SOURCE_AND_PERMISSION",
      "expected_speech": [
        {"start_seconds": 0.6, "end_seconds": 3.3, "text": "这款 DemoCup，take it anywhere。"}
      ],
      "expected_on_screen_text": [
        {"start_seconds": 0.8, "end_seconds": 3.8, "text": "DemoCup 随行杯 · Shop now"}
      ]
    },
    {
      "case_id": "cross_language",
      "path": "clips/cross-language.mp4",
      "sha256": "REPLACE_WITH_ACTUAL_64_CHARACTER_SHA256",
      "permitted": false,
      "rights_note": "REPLACE_WITH_SPECIFIC_SOURCE_AND_PERMISSION",
      "expected_speech": [
        {"start_seconds": 0.5, "end_seconds": 2.0, "text": "Twist to open."}
      ],
      "expected_on_screen_text": [
        {"start_seconds": 0.5, "end_seconds": 2.8, "text": "旋转开盖"}
      ]
    }
  ]
}
```

Reference times are seconds relative to source frame zero, with an exclusive end. They must be finite, satisfy `0 <= start < end`, and fit the measured video duration. They are independent of the output storyboard's planned seconds. Keep English brand names inside Chinese sentences, spelling, numerals, units, currency symbols, and language switches exactly as observed. Do not translate a source quote to match the other channel.

Compute hashes locally without uploading files:

```bash
.venv/bin/python - <<'PY'
import hashlib
from pathlib import Path
for path in sorted(Path('.local-data/live-inputs/clips').glob('*.mp4')):
    with path.open('rb') as source:
        print(hashlib.file_digest(source, 'sha256').hexdigest(), path.name)
PY
```

## Verify prices and authorize a bounded run

The harness supplies **no price or spending authorization**. Check current [OpenAI pricing](https://openai.com/api/pricing/) and the configured model's terms before filling this template. Use conservative rates applicable to the account and deployment being used, and do not assume a cached-input discount. The date must be within the previous 30 days; this freshness check does not independently verify the rates. Save `.local-data/live-inputs/pricing.json`:

```json
{
  "operator_verified": false,
  "source_url": "https://openai.com/api/pricing/",
  "verified_on": "REPLACE_WITH_YYYY-MM-DD",
  "models": {
    "gpt-4.1-mini": {
      "input_usd_per_million_tokens": "REPLACE_WITH_VERIFIED_POSITIVE_RATE",
      "output_usd_per_million_tokens": "REPLACE_WITH_VERIFIED_POSITIVE_RATE"
    },
    "whisper-1": {
      "usd_per_minute": "REPLACE_WITH_VERIFIED_POSITIVE_RATE"
    }
  }
}
```

Set `operator_verified=true` only after checking and replacing these values. The currently reviewed live budget implementation accepts `gpt-4.1-mini` or `gpt-4.1-mini-2025-04-14` for vision/creative work, and `whisper-1` for timed speech. If selecting the dated text model, provide rates under that exact model ID as well. Unsupported models or absent rates block the run. The application's broader capability allowlist does not imply that this harness has reviewed cost bounds for those models.

Configure `OPENAI_API_KEY` in the backend execution environment using the available secret-management mechanism; do not put it in this guide, the manifest, shell history, exported data, or Git. Separately set `LIVE_TEST_MAX_COST_USD` to the explicitly approved positive amount for this ledger. There is no default amount. Once those decisions and files are complete, this command enables the run:

```bash
# These checks require existing environment values; they do not print the key.
: "${OPENAI_API_KEY:?Configure the backend key before running}"
: "${LIVE_TEST_MAX_COST_USD:?Set the explicitly approved positive budget before running}"

RUN_LIVE_MODEL_TESTS=1 \
OPENAI_VISION_MODEL=gpt-4.1-mini \
OPENAI_CREATIVE_MODEL=gpt-4.1-mini \
OPENAI_TRANSCRIPTION_MODEL=whisper-1 \
ANALYSIS_OUTPUT_LANGUAGE=English \
CREATIVE_OUTPUT_LANGUAGE=English \
.venv/bin/python scripts/live_validate.py \
  --manifest .local-data/live-inputs/manifest.json \
  --pricing .local-data/live-inputs/pricing.json \
  --output-dir .local-data/live-evaluation
```

All selected clips are validated and copied through intake before model calls begin. Finite provider timeouts, bounded sampling/audio chunks, capped output tokens, and bounded transient retries apply. The defaults are 12 sampled frames, 60-second audio chunks, at most three chunks, 8,000 output tokens, and at most two retries. Language configuration controls narrative descriptions/creative writing; OCR and speech evidence must retain the source script regardless of these settings.

The budget guard persists a reservation **before every HTTP attempt**, including retries. Text/vision requests reserve the full documented 1,047,576-token context of [GPT-4.1 mini](https://developers.openai.com/api/docs/models/gpt-4.1-mini), plus the configured output cap, at the supplied rates. This intentionally avoids guessing image-token costs and can reserve substantially more than a short request consumes. Transcription reserves each audio chunk rounded up to whole minutes. The guard rejects a request when its reservation would exceed the remaining budget.

`budget.json` includes prior reservations in the same output directory, even after failed requests, interrupted runs, or lower reported usage. Keep the same output directory and ledger for one authorized budget; deleting the ledger or switching directories loses that previous-use accounting. A larger budget must be explicitly authorized. The ledger does not account for unrelated application/API calls or other provider consumers. Normal application requests do not inherit the harness's budget guard.

Reserved cost is a conservative scheduling bound based on the verified rates; it is **not a provider invoice**. Actual billed cost stays `null` when not supplied by the provider. Retry reservations are retained even if a failed request appears unbilled. Check the account's billing records separately; provider-side caps may propagate with delay, so this is not a promise of an exact invoice ceiling.

## Inspect outputs and perform human review

Files stay in the selected local output directory:

| File | Meaning |
| --- | --- |
| `budget.json`, `budget.lock` | Persistent reservations and coordination lock; keep them across runs. |
| `media/` | Saved permitted original clips and any required playback derivative. |
| `<run>-<index>-<case>-video.json` | Video identity, original hash, measured source frame clock, and playback metadata. |
| `<run>-<index>-<case>-analysis.json` | Validated original recognition result with unconfirmed review state. |
| `<run>-<index>-<case>-human-review.json` | Independent expected words, recognized OCR/ASR events, and initially blank human checks. |
| `<run>-report.json` | Cases, safe errors, provider/model diagnostics, measured elapsed time, usage when available, and budget reservations. |

The report's `elapsed_ms` measures the run from input/budget preflight and intake through recognition and optional creative evaluation; individual request timings are recorded separately. No five-minute SLA is asserted. Preflight failures print a blocked result before provider execution; completed reports distinguish successful processing, partial/errors, and budget stops. Exit code `0` means default-off or a completed run, `1` means a reported run failure/error/budget stop, and `2` means blocked input/setup or a local data/output error. `completed` is a processing result, not a human quality verdict.

Creative request diagnostics list `proposed_output_refs` with `persistence=adapter_candidate_not_committed`. These identify the adapter's validated candidates, not saved application revisions: the workflow may reject a stale result or assign existing output IDs and later revisions during persistence. Service job-result diagnostics record the final saved references separately. Harness outputs remain local evaluation candidates and are never application commits.

A reviewer fluent in the relevant languages must view/listen to the actual clips and independently compare the annotations and results. Fill `reviewer`, `review_status`, and each check's `verdict`/`notes` in the review files. Use explicit results such as `pass`, `fail`, or `not_assessable`, with concrete examples and source intervals; the harness does not calculate or certify a score.

Check these separately:

- **English speech and Chinese speech:** compare original spoken words, omissions, additions, inaudible passages, repeated words, and timestamp/frame alignment. Any translation replacing source speech is a failure of preservation.
- **English OCR and Chinese OCR:** compare visible source text independently of speech. Pay special attention to product/brand words, punctuation that changes meaning, numerals, decimal prices, currency, units, and CTA phrases. Missing text between sparsely sampled frames must be recorded as a coverage limitation.
- **Mixed-language content:** inspect language switches within one utterance and English brand tokens inside Chinese speech/text. Record whether script and spelling survive output, correction, persistence, and export.
- **Different audio and caption languages:** keep the two quotations and their intervals separate. A valid caption/speech mismatch is evidence to preserve, not something to merge into a single translated quote.
- **Visual labels and uncertainty:** assess subject/action/presentation categories and explanatory descriptions against visible evidence. Check that unreadable text, inaudible speech, occlusion, and sparse temporal coverage remain uncertain rather than invented. Music/SFX are not analyzed by this implementation; that is not a claim of silence.

Use `frame_timing.frame_boundaries_seconds` from the corresponding video file to compare source frame ranges with the independent reference seconds. A half-open event range `[start_frame,end_frame)` maps to those two boundaries. Its browser media clock additionally uses the selected representation's `media_start_seconds`; a proxy's playback clock is not a substitute for source evidence timing.

The human review files are evaluation artifacts, not application approval commands. Editing them never changes `AnalysisResult.review`, marks an analysis confirmed, or approves a creative direction. Report actual errors and unresolved human checks separately from offline test results.

## Optional evaluation from an already reviewed application state

The harness does not automatically approve its newly generated analysis. To test creative generation, use an existing application task for one of the manifest's permitted source hashes. In the app, review/correct the exact current analysis and explicitly choose **Use this reviewed analysis**. If evaluating production, separately approve the exact direction revision through the existing UI. These normal application provider calls, if needed to prepare the state, require their own authorized spending; the harness ledger does not cover them.

Save the full current state using the read-only API. Replace the task ID through `VIDEO_TASK_ID`; keep this file private under `.local-data/`:

```bash
: "${VIDEO_TASK_ID:?Set the already reviewed application task ID}"
curl --fail --silent --show-error \
  "http://127.0.0.1:8000/api/tasks/${VIDEO_TASK_ID}" \
  --output .local-data/live-inputs/reviewed-task.json
```

Repeat the enabled command above with this additional argument:

```text
--reviewed-state .local-data/live-inputs/reviewed-task.json
```

This repeats the permitted recognition evaluation and then generates two new, unapproved creative drafts from the snapshot's exact confirmed analysis and brief. It writes `<run>-creative-directions.json`. If the snapshot already contains applicable pending written feedback, it evaluates that saved instruction against its exact target and writes `<run>-refined-direction.json`; do not fabricate a pending status or alter approval flags to force a test. If an exact selected, approved direction already exists, production generation uses that saved direction and writes `<run>-production.json`. The newly generated drafts are never auto-approved, and the harness does not write these artifacts back into the application.

Human creative review should assess preservation of production constraints/prohibited claims, distinct approaches, interpretation of the saved instruction, precise citations, source claims versus established product facts, hypotheses/test methods, and planned timing. A schema-valid draft does not prove that every creative instruction was understood.

## Cache scope and reproducibility

Normal recognition caches successful normalized extraction using the source hash, provider/models, preparation/normalization/prompt/schema versions, timing, and relevant settings. Reads undergo validation and produce a new unreviewed analysis identity; they do not certify a fresh provider evaluation. Cache status is recorded in diagnostics. Changed models or prompts change the cache key.

Creative provider responses are **not cached**. Each explicit generation/refinement/regeneration requests fresh content, while the workflow preserves earlier saved revisions and approved work. The handoff's rule that caching must include the complete identity/settings applies where a cache exists; it does not require adding a creative cache. The creative diagnostic `input_sha256` identifies the exact request context and is not a cache lookup.

The live harness explicitly disables recognition response caching so a reported live attempt exercises the configured provider. Each attempt remains budgeted. Preserve manifests, exact model settings, source hashes, reports, and completed human review files to reproduce or compare an evaluation without claiming that synthetic fixtures are live-quality evidence.
