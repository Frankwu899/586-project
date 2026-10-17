# Real provider boundary, v0.4

Implementation decision recorded 16 October 2026. This file records API choices and offline behavior, not observed recognition accuracy or a successful paid request.

## Selected APIs and verified documentation

The implementation session read the following current official documentation on 16 October 2026:

- [GPT-4.1 mini](https://developers.openai.com/api/docs/models/gpt-4.1-mini): text/image input, Responses API and structured output support. Video/audio input is not assumed.
- [Images and vision](https://developers.openai.com/api/docs/guides/images-vision): Responses `input_image` accepts a base64 JPEG data URL.
- [Structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs): Responses uses `text.format` with `type=json_schema`, `strict=true`, required properties and closed objects. The transport removes unsupported conditional composition (`allOf`, `if`/`then`/`else`, `not`, dependent-schema keywords) and array uniqueness/contains constraints only from the provider request schema. Canonical exported schemas and local semantic validation retain these rules; provider JSON is revalidated locally before acceptance.
- [Speech to text](https://developers.openai.com/api/docs/guides/speech-to-text): `timestamp_granularities[]` is supported by `whisper-1`; the implementation requests `verbose_json` and segment timestamps from `/v1/audio/transcriptions`. Newer transcription model IDs are not assumed to expose this timing contract.

Defaults are `gpt-4.1-mini` independently for vision and creative generation, and `whisper-1` for timed speech. Supported snapshot IDs are in `providers/transport.py`. Unsupported configured IDs fail before a provider request. Adding a model requires verifying its specific capabilities and updating the adapter capability registry. Narration languages are separate settings; OCR and transcription retain source English/Chinese/mixed wording and are never translated into narrative output language.

## Inputs and honest timing

Only the required temporary JPEG frames and mono PCM audio chunks are sent to OpenAI. The default preparation budget is at most 12 frames, each at most 1024 pixels on its longest side, and three 60-second audio chunks. Original uploads and playback derivatives are not directly uploaded to OpenAI. `store=false` is requested for Responses.

Vision/OCR events cover exactly `[sampled_frame, sampled_frame+1)`. A successful sparse-frame extraction does not establish full-video coverage or exact shot/action/text boundaries. Narrative segments also cover only the observed sampled frames and carry explicit interpretation/uncertainty. The first version does not infer action continuity between distant sampled views. This conservative timing makes evidence inspectable without inventing precision; denser or separately measured intervals are future work.

Audio timestamps are relative to each prepared chunk. The adapter adds the chunk's source-relative offset, then uses the existing measured VFR/CFR frame-boundary mapping. Audio is chunked without overlap, so no repeated words are removed heuristically. Transcription can lose words at chunk boundaries; real evaluation must inspect them. There is no automatic language forcing, translation, speaker identity assignment or music/SFX recognition. No-audio media records the intake determination, skips the speech request and reports `speech=none_found`; music/SFX remain `not_analyzed`.

Vision and speech failures are isolated. A successful category remains reviewable in a partial result. The current Coverage contract permits either observations or failure for an entire category, so if any speech chunk fails, speech observations from that run are withheld and `speech=failed`; no complete-speech claim is made. Nested structured visual failure also produces a partial analysis. Partial results remain blocked from creative use by the service. Real-provider failure never substitutes sample findings.

## Replaceability, limits and diagnostics

`RecognitionAdapter.analyze(RecognitionRequest)` is unchanged. Internally, vision and timestamped transcription providers expose capability flags, provider/model identifiers and plain normalized dictionaries. Offline alternate-provider tests demonstrate this boundary, not a second real integration. Creative generation uses its existing methods and exact input revisions.

Transport calls have finite per-operation HTTP timeouts, at most three configured retries, a process-wide limit of two active HTTP requests, bounded output tokens, and no automatic redirects. Authentication, quota exhaustion, unsupported capability, invalid request and malformed/refused/incomplete output are not retried. Only transient network/HTTP failures receive bounded retry/backoff. Every attempted paid request invokes the live harness's reservation callback, including retries. API keys are backend-only and are omitted from settings representations, cache keys and diagnostics.

Recognition run records are appended to the configured cache directory's `runs.jsonl`. They identify capability, provider, requested/resolved model when available, prompt/normalization versions, source hash, job and new analysis identity/revision, times, elapsed milliseconds, attempts, cache status, safe failure code and provider-reported usage with units. Missing usage and cost are null with an explanation. Reported response usage does not establish usage of failed attempts or billed cost. Records omit provider raw errors, prompts, recognized text and media bytes. Cache files themselves contain private recognized content and belong only in ignored local data storage.

The cache key covers source SHA-256, preparation version, source timing, audio presence, provider/model IDs, prompt version, full visual schema, normalization version and relevant configuration. A cache hit creates a fresh analysis identity, preserves cached source findings and records the hit without claiming a new provider request. Failed/partial results are not cached, and cached payloads are locally revalidated before reuse. User corrections are never cache entries and are never overwritten.

## Verification boundary

`tests/test_providers.py` uses fake HTTP and alternate plain-dictionary adapters to check mixed-language separation, no-audio handling, VFR/offset mapping, cache invalidation, malformed/refused/incomplete output, missing configuration/capabilities, bounded transient retry and permanent errors. The service's broader tests exercise approval and revision rules. The separately invoked live evaluation harness requires explicit enablement, credentials, permitted clips and a positive conservative cost budget. No paid provider request or human-scored linguistic result is established by these offline tests.
