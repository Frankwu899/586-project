# Budgeted module evaluation

This revision introduces one **USD 3 maximum** for the owner's current experiment.
This is an application request-admission limit, not an account-wide OpenAI spending
limit and not a claim about the provider's invoice. No fine-tuning job is started.

## One retained ledger

Every real transport created by the application uses the same
`VIDEO_ANATOMY_DATA_DIR/provider-budget.sqlite3`. The local launcher explicitly
uses the stable application data directory. `VIDEO_EXPERIMENT_BUDGET_PATH` may
point to an already retained shared ledger; it must not be varied per worker,
module or evaluation run. Preserve this file when moving or upgrading the app.
Deleting it or supplying a fresh path loses the historical experiment accounting.

SQLite `BEGIN IMMEDIATE` and synchronous commits serialize reservations across
threads and processes. Before each HTTP attempt, including a retry, the transport
reserves a conservative maximum. If the remaining cap cannot cover the attempt,
it sends no request. Restarting the process or repeating the runner does not
reset the ledger. A later configuration can lower the retained cap, but cannot
silently increase it. Values over USD 3 are rejected.

- Text/image requests reserve the documented full GPT-4.1 mini context plus the
  configured output limit. Images are covered by the context bound; image tokens
  are not guessed from pixel dimensions.
- Hosted web research reserves a full context for every possible model/tool turn,
  the maximum number of search fees and the documented fixed mini search-content
  blocks. Only `web_search`, low context and one to three maximum calls are allowed.
- Whisper reserves the measured submitted duration, rounded up to whole minutes.
  Audio chunks remain bounded at 120 seconds and 24 MiB.
- A successfully returned, recognized text model with valid usage can settle the
  reservation at undiscounted input/output rates, plus maximum search costs. This
  conservative estimate intentionally ignores cached-token discounts.
- Unknown usage, transport errors, invalid JSON and failed HTTP attempts keep the
  entire reservation. An accounting-write failure stops further attempts. An
  unexpected service tier, exceeded usage limit or excessive tool calls blocks
  subsequent reservations pending review.

`held_usd` is the amount currently counted against the USD 3 cap. It includes
known usage estimates and unresolved reservations. `reserved_upper_bound_usd`
is cumulative request admission over the experiment's history; it is **not
spend**, and can exceed USD 3 when earlier successful reservations settle lower.
`provider_billed_cost_usd` stays `null`; only the provider's billing records could
supply that figure. This ledger cannot include requests from other applications
or a second machine using a different ledger.

## Reviewed price and capability basis

Verified against official sources on **2026-10-18**:

| Capability | Reviewed configuration | Standard rate / bound |
| --- | --- | --- |
| Structured text and vision | `gpt-4.1-mini` and `gpt-4.1-mini-2025-04-14` | USD 0.40 input / USD 1.60 output per million tokens; 1,047,576 context tokens |
| Timestamped transcription | `whisper-1` | USD 0.006 per minute |
| Background research | Responses hosted `web_search` with GPT-4.1 mini | USD 0.01 per tool call, plus 8,000 input tokens per non-preview search call |

Sources:

- <https://developers.openai.com/api/docs/models/gpt-4.1-mini>
- <https://developers.openai.com/api/docs/models/whisper-1>
- <https://developers.openai.com/api/docs/pricing>
- <https://developers.openai.com/api/docs/guides/tools-web-search>
- <https://raw.githubusercontent.com/openai/openai-python/main/src/openai/types/responses/response_create_params.py>

The official SDK describes `max_tool_calls` as a total built-in-tool-call bound,
not a per-tool bound. Source URLs come from hosted-search result/citation fields;
the local backend does not fetch arbitrary model-provided URLs. Search summaries
remain attributed source material, not independently verified truth.

Unknown model/tool configurations fail closed. The pinned pricing check expires
after 30 days; recheck official rates and bounds before changing the verification
date. Requests explicitly select standard (`default`) service pricing.

## Reports

All real transport operations record module, model, timestamps, latency, attempt
count, available token usage, prepared image count, submitted audio duration,
reservation details and estimated cost. No prompt, image bytes or API key is
written to these diagnostics. The shared transport appends to
`provider-cache/usage.jsonl`; existing adapter diagnostics remain separate.

The runner reports M2 input assistance, vision, speech, creative directions,
refinement, production, Structure and research individually. A module not exercised
is `not_run`, with unknown cost and quality. A real application-cache hit is zero
incremental API cost; an OpenAI prompt-cache hit still uses a paid request and is
not called free. Unknown or failed-attempt cost is never converted to zero.

## Run locally

From the repository root, validate inputs without calling a provider:

```bash
.venv/bin/python scripts/evaluate_modules.py \
  --manifest evaluation/manifests/workspace-redesign-v1.json \
  --output-dir .local-data/evaluation/module-preflight
```

The manifest's `assets` paths are relative to the repository root. The runner uses
only entries with `skip_default_paid=false`, in `paid_priority` order. Every
selected file must exist, match its recorded SHA-256 and have explicit evaluation
permission. Online candidates and the deliberately overlength intake control are
not submitted. Evaluation permission does not grant training or redistribution
rights.

Live mode requires `OPENAI_API_KEY` already configured in the backend environment,
`RUN_LIVE_MODEL_TESTS=1`, and the explicit `--live` flag:

```bash
RUN_LIVE_MODEL_TESTS=1 .venv/bin/python scripts/evaluate_modules.py \
  --live --check-cache \
  --manifest evaluation/manifests/workspace-redesign-v1.json \
  --data-dir "$VIDEO_ANATOMY_DATA_DIR"
```

Use the same stable data directory as the running app. Do not put the key in a
command argument, committed file, report or chat. No key is requested by this
script and no automatic API run occurs at installation/startup.

Real clips run recognition and, if usable observations exist, Structure. Only
material background gaps trigger research. Recognized real video is **not
automatically confirmed** to unlock creative generation.

By default M2 and creative/refinement/production exercise clearly fictional,
predefined evaluation inputs. Administrative approval flags on those fixtures
are test conditions, not user approval and not an evaluation of real advertising
quality. `--reviewed-state path.json` instead uses an already reviewed/approved
saved state; any referenced real video must belong to the permitted manifest.
Generated proposals never replace the app's saved task state.

Each real clip gets a review worksheet containing the corpus's independent
expected checks. A reviewer must compare the source and output for observation
accuracy, UI exclusion, useful logic, inference labeling, source relevance and
transfer conditions. Schema validity and API completion are not quality scores.

## Current execution limits

The managed build environment has no backend API key and does not permit
`api.openai.com` egress. Its preflight report therefore records **zero requests
sent**, and real model usage, latency, billing and quality remain unmeasured.
Mock transport tests validate accounting and request contracts; they do not
establish live model quality. This documentation does not claim a paid run or
trained model.
