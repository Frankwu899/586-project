# GPT-6 configuration and local budget recovery

> Local-client budget behavior below is superseded by [v0.7.5](local-client-usage-v075.md). The USD 3 limit applies only to Cloud experiments.

Date: 19 October 2026. Environment: managed Linux workspace. This is an offline
implementation/verification record, not a completed real-model evaluation or a
Mac validation report.

## Provider selection

- Visual recognition, project-context assistance, Structure interpretation,
  Ideas and Production default to `gpt-6.1-sol`.
- Background source retrieval defaults to `gpt-6-luna`; Structure synthesis
  continues to use Sol. Both support structured Responses and hosted web search.
- Legacy GPT-4/GPT-5 environment defaults migrate to these selections. No
  automatic older-model fallback runs when a project lacks GPT-6 access.
- GPT-6 models do **not** accept audio or direct video inputs. Frames are image
  inputs. Timed audio transcription is a distinct capability; using Whisper is
  not a GPT-6 upgrade. In v0.7.4 the owner approved the dedicated speech exception:
  normal profiles use `whisper-1` with segment timestamps. Other capabilities keep
  their GPT-6 defaults. See [the speech update](speech-exception-v074.md).
- Responses explicitly request standard service and low reasoning effort.
  The bounded output limit includes reasoning tokens. This is a latency and
  cost choice, not evidence of improved analysis quality.

## Budget behavior

The existing shared SQLite ledger and its USD 3 maximum remain intact. The local
limit is not an OpenAI account balance. Unknown network failures continue to hold
their reservations; restarting, changing models or removing projects does not
reset spending records.

Sol text/image requests first call the non-generating Responses input-token count
endpoint. The generation reservation uses that count plus a conservative UTF-8
schema byte allowance and request overhead, rather than charging an entire
million-token context for a small prompt. Count failures and inputs beyond the
reviewed 272,000-token short-context bound stop before generation. This avoids
assuming an image multiplier from a different model.

Hosted search has no documented hard token limit for `search_context_size=low`.
Search therefore reserves a full context for each permitted model/tool turn,
including cache-write and long-context premiums. Luna keeps that bound below the
small shared experiment ceiling. Sol remains available for explicit research
configuration, but its full-context bound will not fit USD 3. No guessed search
token cap is presented as a hard spending guarantee.

Successful usage is estimated with published rates, including cache writes. No
cache-hit discount is assumed. Unknown or inconsistent usage retains the
reservation; it never becomes a claimed zero-dollar request.

Explicit HTTP 401/403 refusals occur before model generation and now settle at
zero estimated generation cost. `reconcile_rejected_attempts()` can recover old
reservations with those precise failure codes. It preserves original reserved
amounts and failure codes, adds an explanatory basis, and never releases timeout,
5xx or unclassified failures. The UI invokes that method as an explicit recovery
action; it does not enlarge the cap.

The Structure run's absolute deadline now reaches token preflight, reservation,
request-slot acquisition and generation. Each HTTP phase uses the remaining time;
generation cannot begin after preflight has consumed the run's allowance. A
reservation cancelled before any generation request is sent releases its hold
with an auditable `generation_request_not_sent` basis. In-flight request failures
remain unknown and keep their holds.

## Primary sources checked

- [GPT-6.1 Sol capabilities and rates](https://developers.openai.com/api/docs/models/gpt-6.1-sol)
- [GPT-6 Luna capabilities and rates](https://developers.openai.com/api/docs/models/gpt-6-luna)
- [Current API pricing, cache writes and web search](https://developers.openai.com/api/docs/pricing)
- [Responses input-token count endpoint](https://developers.openai.com/api/reference/resources/responses/subresources/input_tokens/methods/count)
- [File transcription and timestamp capabilities](https://developers.openai.com/api/docs/guides/speech-to-text)
- [Vision input sizing](https://developers.openai.com/api/docs/guides/images-vision)

Sol standard rates are USD 2 input / 10 output per million tokens; cache writes
cost USD 2.50 per million. Luna rates are USD 0.10 input / 0.50 output, with cache
writes at USD 0.125. More than 272,000 input tokens doubles input/cache rates and
multiplies output rates by 1.5. Hosted web search costs USD 0.01 per call plus
model-priced retrieved content. The catalog was reviewed on this document's date;
the existing pricing-expiry guard remains active.

## Verification

Targeted offline tests exercise token-count ordering, bounded image requests,
malformed and oversized counts, cache-write accounting, hidden search context,
concurrent reservations, retry holds, old authentication recovery, credential
diagnostics and module evaluation mocks. No user video, API key or paid inference
was used. End-to-end analysis quality and project-specific model permissions
remain for local verification.
