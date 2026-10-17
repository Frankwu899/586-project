# Bilingual provider foundation handoff

- **Task:** Implement the committed Video Anatomy handoff across M10, M3, M4, M5 and existing M6–M8.
- **Author/date/environment:** Codex, 16 October 2026 (America/Los_Angeles), managed Codex Cloud. No Mac/Andrea-machine validation claimed.
- **Repository:** Frankwu899/586-project.
- **Implementation branch:** `feat/video-analysis/bilingual-provider-contracts`.
- **Base:** latest fetched `origin/main`, `a456329e4fe8cab76669c8c8254cfed8ce11bbcb`; refetched before delivery, unchanged.
- **Handoff source:** `origin/docs/english-starter`, `c3f40ca184212ec52025810e6420a5e97d1fe37c`.
- **Implementation commit before documentation:** `a782be4a86dd64ee3e9e6828b2ef7a04008d58f6`.
- **Publication:** prepared for ordinary push and a draft PR into main; final publication confirmation belongs to the PR/chat delivery record. No merge or deployment is authorized/performed.

## Baseline and requirement decisions

The initial working tree was clean on `work`. Fetch required the environment's network-enabled command sandbox and succeeded. The implementation branch was created from current main. Only `docs/video-anatomy-handoff/` was copied from the older documentation branch; a staged comparison confirmed its bytes match that source. Main had no conflicting package. No application reference snapshot replaced current source.

The skeleton and frame-timing changes were already merged. `origin/feat/video-analysis/first-real-provider`, `origin/feat/creative-direction/first-real-provider`, `origin/feat/video-anatomy-frame-timing` and `origin/chore/integration/overnight-skeleton` contained no commits outside main. No unmerged dependency was imported and no existing branch was removed/reset.

Apply confirmed handoff requirements over earlier sample-only limits. Use v0.4.0, MP4 H.264 plus explicitly supported HEVC Main SDR 8-bit, English narrative defaults independent of source text, and conservative partial-state gating. Preserve the live meanings `chosen_direction` = draft selection and `selected_direction` = explicit approval; two baseline field descriptions in DATA_CONTRACT.md were swapped, while live code and the requirement prose agree on these meanings. No speculative per-token language/confidence metadata was added.

## Changed modules and interfaces

| Module | Delivered behavior and source |
|---|---|
| M10 contracts | `models.py`, `contract_migration.py`, storage/frame migration, v0.4 schemas/types/examples. Three typed visual groups, unknown nulls, explicit coverage/errors, event-local references, category/role validation and nested failure => partial. |
| M3 media | `media.py`, `media_preparation.py`. Original byte/hash/codec/timing preservation; HEVC H.264 playback derivative with separate clock and verified frame correspondence; bounded original-frame JPEG/audio extraction. |
| M4 providers | `providers/base.py`, `config.py`, `transport.py`, `recognition.py`. OpenAI image/OCR + timestamped speech; replaceable plain capability interfaces, finite retries/timeouts/concurrency, safe errors, exact diagnostic references and scoped recognition cache. |
| M5 review | `service.py`, `api.py`, minimal existing React review controls. Server-allowlisted category/description edits, original retention, replayable revisions, stale-write rejection, confirmation clearing and downstream invalidation. Partial observations stay visible without status editing. |
| M6–M8 | `providers/creative.py` and service routing. Two directions, written refinement, explicit approval, production brief/storyboard, exact evidence revisions and hypotheses with test methods. Real failures never fall back to sample templates. |
| Verification | New contract/migration/media/provider/workflow/harness tests, fake-provider HEVC/bilingual browser flow, generated types and existing sample regression. `scripts/live_validate.py` is separate and off by default. |

Shared-file ownership was coordinated: contract editor owned models/storage/migration; media editor owned intake/preparation; provider and creative editors owned separate implementation files; UI editor owned frontend consumers; integrator owned adapters/service/API wiring and final type generation. Contract work preceded consumer integration. No unrestricted task editor, JEV, platform download, extra reference workflow, training, storyboard images or broad redesign was added.

## Compatibility and persistence

v0.3 task payloads are validated against their retained schema, archived exactly in `task_migration_archive`, then migrated transactionally. `visual_details` and `playback` become null; content revisions/citations/review meaning remain unchanged, and only optimistic task version advances. v0.2 measured-frame migration and v0.1 explicit import remain supported. Historic v0.1/v0.2/v0.3 schema/fixture bytes are preserved and tested.

Source observations remain integer half-open original frame intervals; derivative timing serves only playback, and storyboard timing remains independent planned seconds. Provider-only schema projection removes composition clauses unsupported by OpenAI strict output. TypeScript generation likewise projects structural types. Full canonical schemas and local semantic validation retain the original constraints.

Provider attempt diagnostics distinguish provisional `proposed_output_refs` from service `persisted_job_result` records carrying authoritative saved IDs/revisions. This also covers production regeneration, which keeps existing output IDs and advances revisions. Failed/stale results never become committed outputs. Cache and diagnostics are ignored private runtime data.

## Actual verification

Baseline `a456329`: dependency consistency, schema drift, Ruff, **171 backend tests**, frontend type drift, **5 timing tests**, TypeScript, ESLint, build and **2 sample browser tests** passed. Baseline browser setup first failed due an accidental temporary dependency symlink/two Playwright copies; removing the temporary link resolved it. Default-sandbox loopback restrictions caused one bind failure and hung API checks; those processes were stopped and network-enabled reruns passed. These were environment/setup failures, not suppressed assertions.

Final verification commands:

| Check | Actual result |
|---|---|
| `bash scripts/verify.sh` (network-enabled cloud command) | Dependency consistency, schema drift, Python Ruff/tests, frontend type drift/unit/typecheck/lint/build, sample and provider browsers. See final result below. |
| `.venv/bin/python -m pytest -q` | **320 passed**, no failures/skips. Existing Starlette/httpx deprecation warning remains; dependency pins were not changed to hide it. |
| Media subsets included above | **31 actual FFmpeg tests** across intake/preparation: H.264/HEVC, VFR, shifted origins, rotated display, delayed/no audio, source/proxy correspondence, corrupt/unsupported/oversized cases, cleanup and repeated uploads. Media is generated synthetic footage, not real recognition evidence. |
| Frontend timing unit suite | **5 passed**. |
| Original browser suite | **2 passed**: full sample workflow and shifted-source frame stepping. |
| Provider browser suite | **2 passed**: real local HEVC decoding/playback with fake bilingual providers through corrections/review/refinement/approval/export/invalidation; partial/legacy coverage and immutable status UI. |
| Schema/type drift, TypeScript, both linters, production build, `git diff --check` | Passed. |
| `.venv/bin/python scripts/live_validate.py` | Returned `not_run` as designed with default-off configuration; no provider call. |

The initial integrated suite passed 313 tests. Subsequent review added regressions for source-aligned chunk bounds, custom media tooling, OpenAI schema projection, persisted diagnostic IDs and safe failures. A transient Pydantic serializer warning during structured corrections was fixed by assigning the validated nested model. No tests were weakened or disabled; the provider browser suite has its own explicit command in `verify.sh`.

## Live status and limitations

**No live model tests were run; no live API spend was incurred.** `OPENAI_API_KEY`, `RUN_LIVE_MODEL_TESTS` and `LIVE_TEST_MAX_COST_USD` are absent. No permitted real clips/annotations or verified pricing file were supplied. The current cloud network policy also does not list `api.openai.com`; a future cloud live run needs supported network configuration. Package/GitHub access and offline checks succeeded. No key value was printed or committed.

Official OpenAI model/vision/structured-output/transcription docs were read during implementation. Defaults: independent vision/creative `gpt-4.1-mini`, transcription `whisper-1`. This is API compatibility research and offline implementation, not a successful paid smoke test. Sample/fake bilingual success does not prove Chinese/English accuracy.

Remaining manual checks: human-scored English/Chinese/mixed/cross-language OCR and ASR, brand/number/unit preservation, short-lived text/actions, speech across chunk boundaries, and actual creative constraint quality. Sparse visual samples cover only observed sampled frames, not exhaustive action/shot boundaries. ASR-to-frame conversion does not prove frame-accurate semantics. HEVC 10-bit/HDR/Log/unusual profiles and MOV are not supported claims. Single-worker local operation, synchronous bounded calls and approximate nominal VFR timecode remain. Public views/likes/comments do not establish retention, conversion or causal improvement.

## Frank: start and review safely

Preserve existing local edits. A separate review worktree avoids switching the current checkout:

```bash
git fetch origin
git worktree add ../586-provider-review origin/feat/video-analysis/bilingual-provider-contracts
cd ../586-provider-review
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
npm --prefix frontend ci
cd frontend
npx playwright install chromium
cd ..
bash scripts/verify.sh
```

Then start backend and frontend in separate terminals using [README_SETUP.md](../../README_SETUP.md), open `http://127.0.0.1:5173`, and follow the dedicated sample workflow. Review the draft PR and migration backup behavior before integration. Worktree review is detached by design; create a separate task branch before making follow-up commits. Git does not transfer dependencies, keys, uploads, proxies or task databases.

For permitted paid evaluation, follow [live-validation.md](../live-validation.md): four-case hashed/rights-confirmed media and independent timed OCR/ASR annotations, explicit positive authorized budget, opt-in, credentials and current operator-verified prices. The ledger reserves a conservative bound before every attempt including retries and prior runs; it is not an exact invoice ceiling. Do not auto-confirm new live results to bypass human review.

## Next bounded tasks

- **Frank:** review and integrate this draft after checks; evaluate correction/approval UX and generated production outputs. Keep UI refinements in frontend files, coordinate any service/shared-contract changes.
- **Andrea:** collect permitted bilingual clips and independent annotations, execute the budgeted harness when authorized, review sparse sampling/chunk-boundary errors, then improve recognition in `providers/recognition.py` and media preparation. Do not fork incompatible contracts from the older provider preparation branches.
- **Shared:** begin subsequent implementation from accepted updated main; agree on models/adapters/service/API edits before concurrent changes. No merge, deployment, branch deletion or history rewrite is part of this delivery.
