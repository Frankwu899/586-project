# Provider reliability review for 1.8.2

Official documentation reviewed on 14 November 2026 (America/Los_Angeles).
This review establishes documented contracts, not access to the team's account
or the cause of the teammate's unavailable provider response.

## Error classification and bounded retries

The [OpenAI error guide](https://developers.openai.com/api/docs/guides/error-codes)
and [billing troubleshooting guide](https://help.openai.com/en/articles/6614457-why-am-i-getting-an-error-me)
distinguish these causes, even when `error.type` is `insufficient_quota`:

| Provider code | Action shown by the application | Automatic retry |
| --- | --- | --- |
| `credit_balance_exhausted` | Check API billing and add credit. | No |
| `project_spend_limit_exceeded` | Check the project's enforced spend limit. | No |
| `organization_spend_limit_exceeded` | Check the organization's enforced spend limit. | No |
| `organization_usage_limit_exceeded` | Review the approved usage limit/request an increase. | No |
| `rate_limit_exceeded`, `slow_down`, or `rate_limit_error` | Wait, then retry. | Configured bounded retry |

Older `insufficient_quota`/`billing_hard_limit_reached` and the broader quota type
remain nonretryable. An unexplained 429 does not identify credit exhaustion or
temporary throttling. Authentication, permission and rejected inputs remain
nonretryable. The [rate-limit guidance](https://developers.openai.com/api/docs/guides/rate-limits)
requires waiting for `Retry-After` when supplied. The transport accepts seconds
or an HTTP date; delays over 60 seconds or beyond the current run's remaining
time defer to explicit retry rather than sending early. Otherwise it retains
the configured retry count with bounded exponential delay and small jitter.
Local defaults remain 90 seconds and zero automatic retries. The shared
experiment ledger and per-attempt reservations remain intact.

## Speech endpoint contract retained

The [file transcription guide](https://developers.openai.com/api/docs/guides/speech-to-text)
and [transcription reference](https://developers.openai.com/api/reference/resources/audio/subresources/transcriptions/methods/create)
still document `whisper-1`, `/v1/audio/transcriptions`, `verbose_json`, and
`timestamp_granularities[]=segment` for the existing timestamped integration.
The guide sets a 25 MB upload limit. Our conservative 24 MiB prepared-chunk
limit and bounded source/chunk limits remain; this release neither switches
models nor routes speech through Responses. Provider timing is an estimate;
safe boundary rounding does not establish word-level alignment accuracy.

## Separate follow-up: speech-model migration

The [deprecation schedule](https://developers.openai.com/api/docs/deprecations)
now lists a **26 February 2027** shutdown for `whisper-1`, with `gpt-transcribe`
or `gpt-live-transcribe` as replacements. Migration needs a separate reviewed
change before that date. 1.8.2 deliberately retains the requested engine.

For completed files, evaluate `gpt-transcribe` first, behind a separate adapter.
The current guide says `timestamp_granularities[]` is specific to Whisper;
therefore changing a model string is not evidence of compatible segments.
Before adoption, verify the replacement's actual timestamp response contract,
source alignment, original-language output, empty-output handling and correction
history with representative annotated recordings. If compatible timing cannot
be established, keep the migration blocked rather than inventing intervals.

Current model pages list [Whisper](https://developers.openai.com/api/docs/models/whisper-1)
at USD 0.006/minute and [GPT-Transcribe](https://developers.openai.com/api/docs/models/gpt-transcribe)
at USD 0.0045/minute. Three submitted minutes would be USD 0.018 versus
USD 0.0135 at those listed rates before retries or any separate alignment
cost. These are pricing illustrations, not measured bills or approved new
spend. Recheck pricing, update the conservative cost estimator, and use the
existing shared ledger for any separately authorized migration experiment.

## Diagnostics and connection check

The Models lookup verifies that the key can reach/list configured models only.
It does not verify transcription/Responses permissions, paid generation, or
available billing. Both the returned message and Settings explain this.

Transport records include release version/commit, correlation IDs, stage/model,
attempt count, cache status, elapsed time, HTTP status and allowlisted provider
code/type/request ID. Raw bodies, prompts, credentials and authorization headers
are excluded. Post-HTTP parsing and domain validation use `validation_result`
to append final sanitized outcomes to `validation.jsonl`; usage remains one
record per request in `usage.jsonl`, so validation does not double-count cost.
Consumers expose rule/field and per-chunk coverage behind support details.

Injected HTTP tests exercise quota/spend/auth/permission/rate/timeout failures,
malformed fields, refusal/incomplete output, Retry-After, and final persisted
validation. They establish application behavior only. No live provider or
account-specific diagnosis is asserted by this document.
