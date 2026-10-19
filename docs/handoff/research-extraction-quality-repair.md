# Research extraction and reasoning repair

- Task: recover useful visual/OCR results, explain partial extraction, and improve
  Structure evidence and language handling after the classroom feedback.
- Environment: Linux Cloud, Python 3.12; no native Mac or live provider validation.
- Branch: `feat/workspace/structure-agent-redesign`; starting commit `70c08b0`.

## Findings and changes

The prior visual adapter sent up to twelve sampled frames through one deeply
nested structured response. Any invalid or incomplete output discarded both
visual and OCR categories. Only a wholly successful combined result was cached.
The user's local provider logs are unavailable, so this is a verified failure
path, not a claim that output truncation caused those exact local failures.

Vision now uses at most three frames per request, with exact supplied frame IDs
and a concise observation prompt. Each validated batch is cached independently.
One failed batch preserves other successful observations and reports its safe
failure code through `AnalysisResult.extraction_failures`. Auth/configuration/
budget failures stop further uncached visual requests; cached later batches stay
available. No failed batch is automatically repeated by this orchestration.
Transport retry policy remains separately configured. A user-requested retry
reuses valid batches and the existing independently cached source transcription.
Original OCR and speech wording and measured frame timing remain unchanged.

The parent integration adds the optional category-error and output-language
fields, their immutable correction rules, generated contracts, and UI consumers.
Existing saved results default to unknown output language; their content is not
silently translated or relabeled. A complete multi-chunk transcript is cached only
when all speech chunks validate; chunk-level transcription recovery is unchanged.

Structure now receives nested visual subject/action/product evidence as well as
text and descriptions, plus explicit coverage limitations and failure metadata.
The prompt distinguishes speech claims from actual visual demonstration. Methods
must identify a specific creative choice, its mechanism, the audience-relevant
reason to care, supporting nodes, transfer prerequisites, and a limitation.
Generic hook/feature/CTA lists are discouraged. The prompt uses general grounding
rules rather than hardcoding the owner's two videos. This is prompt/evidence
improvement, not model training or demonstrated real-world quality improvement.

New Structure analyses follow the application analysis language independently of
Ideas generation language. The saved graph records its language; node feedback
keeps that language if the application setting later changes. New analyses can
use the new language without modifying history. The explicitly loaded fictional
Structure sample also supports English and Chinese.

## Verification

`pytest tests/test_providers.py tests/test_recognition_resilience.py
tests/test_structure_provider.py tests/test_structure_service.py
tests/test_content_region.py tests/test_provider_workflow.py -q`:
**78 passed**, one existing Starlette/httpx deprecation warning.

Meaningful regression cases cover retained partial batches, exact channel
failures, retrying only missing batches, avoiding duplicate speech requests,
corrupt cache revalidation, language changes, preservation of source quotations,
Structure coverage/evidence payloads, and saved graph language after an app switch.
Ruff for changed Python files and `git diff --check` passed.

No paid requests, fine-tuning, deployment, or main merge were performed. Provider
model/budget upgrades and application menus/settings are separate coordinated
changes in this same integration. Real-video reasoning quality still needs human
review after a successful live run with complete visual evidence.

## Integration follow-up

Application language now also governs authored M2 suggestions and unresolved
notes, while exact source excerpts, extracted values, and approved wording stay
unchanged. Recognition prompts cover all authored structured visual descriptions
and uncertainty; built-in uncertainty/timing annotations use the recorded output
language. English/Chinese original OCR and speech remain verbatim.

The coordinated GPT-6-only default disables timestamped transcription because
the selected GPT-6 models do not accept audio. Recognition skips that provider
without making a paid request. An already cached, validated `openai/whisper-1`
transcript with identical source hash, timing, chunk boundaries, preparation,
speech prompt and normalization versions is reused without an API call. Its
events identify the cached transcription method and original provider/model;
coverage remains `observations` (or `none_found` for a validated empty transcript).
Without a compatible cache, speech is `not_analyzed`, rather than claiming no
speech exists or reporting extraction failure. Historical tasks and user-edited
transcript records are never used as substitute cache inputs. Existing saved
speech remains in history. Intake-confirmed absence of an audio stream still means
`none_found`. An explicit separate transcription configuration can use the
existing timestamped provider capability; it is not enabled by these changes.

Structure forwards the absolute run deadline through both structured generation
and research so the coordinated transport can enforce it across input-token
preflight and generation. Private deadline metadata is filtered by transport.

The focused follow-up suite for M2 language, M2 assistance, recognition recovery,
providers, and Structure provider passed **106 tests**. This overlaps the earlier
78-test run; the counts are not additive. All provider calls used offline fakes.
