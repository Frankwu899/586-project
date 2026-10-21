# Module evaluation report — 2026-10-18

## Result

**Live API evaluation is not run.** This implementation run sent **0 paid API
requests** and incurred **USD 0 in new API requests**. No training or fine-tuning
job ran. The provider account invoice was not accessed or independently audited.

The environment check found no backend `OPENAI_API_KEY`. Its HTTP egress policy is
restricted, with no rule matching `api.openai.com`, and no general TCP egress.
No provider connection was attempted. A developer tool or ChatGPT session does
not establish that the project's paid API is configured.

## Per-module measurements

| Module | Live status | Requests sent | Tokens / audio | Live latency | API cost measured | Model quality |
| --- | --- | ---: | --- | --- | --- | --- |
| M2 input assistance | Not run | 0 | Not measured | Not measured | No request; no invoice measurement | Not evaluated |
| Vision and OCR | Not run | 0 | Not measured | Not measured | No request; no invoice measurement | Not evaluated |
| Timestamped speech | Not run | 0 | Not measured | Not measured | No request; no invoice measurement | Not evaluated |
| Creative directions | Not run | 0 | Not measured | Not measured | No request; no invoice measurement | Not evaluated |
| Direction refinement | Not run | 0 | Not measured | Not measured | No request; no invoice measurement | Not evaluated |
| Production brief / storyboard | Not run | 0 | Not measured | Not measured | No request; no invoice measurement | Not evaluated |
| Structure reasoning | Not run | 0 | Not measured | Not measured | No request; no invoice measurement | Not evaluated |
| Hosted background research | Not run | 0 | Not measured | Not measured | No request; no invoice measurement | Not evaluated |

These are deliberately not fake zero-latency or perfect-quality measurements.
Mock HTTP tests establish the request/accounting behavior; they do not measure a
real model's speed, usefulness or bill. Local intake checks and browser workflow
checks are reported separately.

## Inputs prepared

The checked corpus manifest is
`evaluation/manifests/workspace-redesign-v1.json`. The following four paid-eligible
inputs passed exact-byte preflight:

1. Owner-supplied Guandan phone recording.
2. Owner-supplied DreamCatcher fishing-rod ad.
3. A manually masked derivative of the Guandan recording, a paired control rather
   than an independent video or proof of automatic UI detection.
4. A licensed 30-second excerpt from *A Shared Culture*, an independently obtained
   public advocacy campaign, not a commercial-product or WeChat advertisement.

The full 200-second public campaign remains an intake-limit control and is
excluded from paid evaluation. The corpus records rights, provenance, independent
review criteria and the online candidates which could not be acquired. None of
these files has been declared eligible for model training.

## Retained USD 3 experiment ledger

The single prepared ledger for this build task is:

```text
/workspace/586-project/.local-data/evaluation/live-experiment/provider-budget.sqlite3
```

At preflight it contains **0 attempts, USD 0 held and USD 3 remaining**. All future
paid testing for this task must point `VIDEO_EXPERIMENT_BUDGET_PATH` to this same
retained ledger. Do not create a separate USD 3 allowance for each module, agent
or rerun. If execution moves to another machine, transfer the ledger together
with the authorized experiment instead of resetting it.

The ledger preserves unknown attempt costs as conservative holds. Cumulative
reservations are not spend; known usage settles at full standard token rates and
maximum tool costs. See [budget and runner details](BUDGET_AND_MODULE_EVALUATION.md)
for the official pricing sources and bounds.

Machine-readable preflight evidence is saved locally at
`.local-data/evaluation/final-preflight/report.json`. It includes every module,
corpus hashes, environment-check time and the retained budget summary. No key or
private prompt content is in that report.

## Remaining live work

Once the backend credential and allowed provider connection are available, the
bounded runner can execute actual recognition, Structure and focused research on
the corpus, plus explicit fictional creative provider checks or a supplied
already reviewed state. It will report actual response usage, latency and
conservative cost estimates. Independent review worksheets must then be completed
before making any quality claim or choosing an optimization/training strategy.

## Offline implementation verification

The full backend suite passed **545 tests** in **106.35 seconds**, with the API key
removed and live model tests disabled. This covered durable workflow operations,
recovery, schema/history preservation, actual local media handling, mock provider
contracts and Structure behavior.

After that full-suite run started, the final budget review closed an additional
injected-client path: real or unknown injected HTTP clients must use the shared
ledger; only an explicit offline `httpx.MockTransport` may omit it in unit tests.
The affected budget, evaluator, HTTP transport, prior live gates, creative and M2
suites then passed **139 tests**, including one new regression which rejects an
unfunded injected client before its `post` method can run. These 139 checks overlap
the full suite; they are not 139 additional independent tests and the earlier
545-test run is not presented as testing this later guard change.

Scoped Ruff and whitespace checks passed. Machine-readable check details are in
`.local-data/evaluation/backend-final-checks.json`; the full-suite JUnit report is
`/tmp/video-anatomy-backend-suite-final.xml`. Browser/native packaging checks have
separate owners and are not included in these counts. None of these checks called
a paid model or established real model quality.
