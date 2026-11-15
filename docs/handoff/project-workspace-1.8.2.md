# Video Anatomy 1.8.2 reliability handoff

- **Task:** Overview reliability, transcription recovery and actionable diagnostics.
- **Owner / implementation:** Frank / Yuqing Wu; Codex implementation.
- **Date:** 14 November 2026, America/Los_Angeles.
- **Environment:** Linux Codex Cloud; `/workspace/586-project`.
- **Remote:** `https://github.com/Frankwu899/586-project.git`.
- **Initial checkout:** clean `work` at `462bdd67b16a0883c9fd1a04e6778dd77ca4a566`.
- **Implementation branch:** `fix/integration/video-anatomy-1-8-2`.
- **Verified baseline:** `fdfd57f7459050a2b3980d6c0ebe399d0c17749c`, open Draft #18.
  #18 depends on open Draft #17 at `5b72ac1f5a33a82c9aeeaa1e519edf8eefcfc5f8`.
  Main and both prior PR heads were fetched/checked before editing. The 1.8.2 PR
  targets #18's branch, `fix/integration/video-anatomy-1-8-1`. No merge, reset,
  force push or release publication is performed.
- **Delivered commit:** `PACKAGE_MANIFEST.json`, About, pushed branch and final
  delivery report record the exact full SHA. ZIP hashes are in `SHA256SUMS.txt`.

## Confirmed mechanisms and changes

Controlled tests reproduce 1.8.1's coupled chat/proposal rejection, whole-line
claim restriction, chunk loop stopping, strict boundary rejection and billing
code misclassification. The teammate's actual rejected provider response and
failing media were unavailable; these mechanisms do not identify its exact cause.

`conversation.py` validates prose, proposal schemas and grounding independently.
It retains a valid reply when a proposal fails, and retains valid independent
proposals when the reply cannot safely be used. Invalid proposals stay out of
the working brief. Source sentence evidence retains adjacent qualifiers and
negation. Marketing recommendations are distinct from extracted facts and
unresolved decisions. Product assertions, permission/verification claims and
invented source URLs receive conservative deterministic guards. These checks
are not a semantic proof or independent product-claim verification.

Persisted turn states distinguish failed, partial and completed responses. The
retry route reuses the saved user message and rejects completed, foreign,
already-running or superseded turns. No deterministic failure triggers an
automatic repair call. Background job outcomes follow the saved turn outcome;
restart interrupts unfinished work without replay. Context fingerprints preserve
newer edits and adopted facts. Explicit brief review/adoption remains unchanged.
On upgrade, only an unambiguously latest failed 1.8.1 assistant reply gains a
correlated retry; completed and superseded historical turns are never replayed.

Speech stays on `whisper-1` and `/v1/audio/transcriptions`, with the existing
180-second/50-MiB source defaults and three 60-second chunks. Multiple tracks
require the intended single track. Prepared PCM is validated for readable
samples, 16-kHz mono 16-bit format, duration and source boundaries; damaged cache
files rebuild before use. Delayed source audio starts remain aligned.

The validator permits at most 0.10 seconds of provider boundary rounding and
reports any clamp. This bounded tolerance addresses estimates at a chunk edge,
not arbitrary invalid timing; no text receives invented proportional intervals.
Valid segments remain available when another segment is invalid, with incomplete
coverage. Valid completed chunks are reused; other independent chunks can finish
after a chunk-specific error. Known account/configuration failures stop further
requests. Retry preserves saved corrections and reports unresolved overlap.
No speech detected is distinct from no audio, disabled transcription, preparation
failure, provider failure, invalid timestamps and partial transcription.

Shared `auth.py`/`transport.py` distinguish all four reported credit/spend codes,
permissions, authentication, quota, known throttling, unknown 429, timeout,
refusal, incomplete output and schema errors. Transient retry remains bounded by
configured attempts and deadlines and respects `Retry-After`; local defaults
remain 90 seconds with zero automatic retries. The persisted shared experiment
ledger is unchanged. Models lookup describes its limited verification scope.

Operational diagnostics retain release/source identity, project/resource/job/turn
correlation, stage, timing, model, attempts, cache origin, safe HTTP metadata,
validation rules and chunk boundaries. Final domain outcomes are persisted after
HTTP parsing; validation logging does not duplicate usage accounting. The UI
provides expandable copy/export details without full prompts, source text,
credentials, raw media or stack traces. Saved correction and evidence histories
remain local and intact.

## Shared-file coordination

Integration owns project `models.py`, `api.py`, `store.py`, release identity and
generated contracts. Chat owns conversation; speech owns preparation,
recognition, resources and speech recovery; provider work owns shared auth,
transport and diagnostics; frontend owns Overview/Resources/support consumers.
Models were updated first and both generated contract paths checked with their
consumers. Legacy shared service/adapters and approval rules were preserved.
Application/package version is 1.8.2; project schema family remains 1.8.0 with
defaulted additive fields. See release notes for backup and rollback instructions.

## Verification record

Final verification and package results are recorded before delivery. Categories
below are kept separate to avoid implying live accuracy from authored fixtures.

| Category | Observed result |
| --- | --- |
| Automated/injected provider | Final backend: 1,035 passed in 194.98 seconds. Frontend: 51 unit tests passed; TypeScript, ESLint, production build, both Python/TypeScript contract paths, Ruff and dependency consistency passed. |
| Real media preparation | FFmpeg decoded synthesized speech, speech/music, silence and generated video; corrupt PCM/cache, delayed starts and short final chunks are exercised. Provider replies remain injected. |
| Browser | 55 legacy tests and 4 injected-provider tests passed. Final project rerun: 26 passed in 2.5 minutes, including 12 viewport/zoom-equivalent cases and the Overview/Resources reliability flows. 51 screenshots captured; three reliability surfaces were visually inspected. |
| Package integrity/extracted smoke | Both payload variants passed precommit CRC, all 145 manifest hashes, runtime instruction loading, static UI serving and saved conversation/analysis reopening after installation relocation. Final archives are generated from the clean commit; exact source/checksum and post-commit checks accompany the delivered ZIPs. |
| Live API / incident media | Not run: no configured credential or representative failing videos available. No paid calls or ledger reset. |
| Actual macOS installation | Not run: Linux only. Gatekeeper, Keychain, signing/notarization and native installation remain unverified. |

Runtime versions: Python 3.12.14, Node 24.19.0, npm 11.9.0, FFmpeg 7.1.5,
Chromium 154.0.8037.57. Pinned dependencies were installed without changing the
stack. Playwright's browser download was blocked by the environment's domain
policy; installed `/usr/bin/chromium` runs the existing configurations.

The integration command is `bash scripts/verify.sh`; it clears live credentials
and runs the full offline checks. Its final run passed every component except
one newly authored project fixture: the padded ` benefit ` label normalized on
save and correctly cleared permission under the existing edit rule. The fixture
now uses the canonical `benefit` emitted by proposal validation; trim handling
remains unit-tested. The complete project suite was rerun with
`npm --prefix frontend run test:e2e:projects` and all 26 passed. Production
permission rules were not weakened to pass the fixture. Nonblocking output: Starlette TestClient's
httpx deprecation warning and Vite's roughly 528-kB chunk advisory. An earlier
run exposed a transport regression conflating a per-request timeout with a
whole-operation retry deadline; fixed with the existing legacy tests unchanged.
The new project browser spec is explicitly excluded from the legacy UI suite.

For each final ZIP, run
`.venv/bin/python scripts/check_release_package.py PACKAGE.zip --version 1.8.2 --expected-commit FULL_SHA`.
The checker rejects mismatched provenance, missing files, private runtime/media
files and unsafe archive paths before exercising the extracted application with
provider requests prohibited. Mac checks inspect wrapper/plist/executable
metadata on Linux, not actual Finder/Gatekeeper behavior.

## Working copy, transfer and next testing

No unrelated changes existed initially. Generated packages, test media, temporary
libraries and browser captures remain outside committed source. User libraries,
credentials and budget databases are excluded from packages. The Finder ZIP is
unsigned and requires installed Python/FFmpeg; first launch downloads pinned
Python dependencies. It is not a self-contained DMG.

Use [release notes and tester checklist](../releases/1.8.2.md) in the existing
team Google Sheet. Frank reviews reports and assigns follow-up work. Inspect
[official provider review](../decisions/provider-reliability-1.8.2.md) for the
separate Whisper migration deadline, timestamp-contract gap and pricing evidence;
no speech-model migration was introduced here.

Remaining account/media questions are the actual provider rejection code/body,
credential permissions and billing state, exact failing audio tracks/preparation,
and observed transcription accuracy on the team's representative media. No
universal transcription fix or verified professional model quality is claimed.
