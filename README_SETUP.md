# Video Anatomy — v0.7 local workspace

For the macOS Finder launcher with in-page API setup, Keychain storage and repeat
opening, use [MAC_APP.md](MAC_APP.md). For the Terminal/developer launcher, use
[LOCAL_API.md](LOCAL_API.md). Classroom bundles do not preload private videos.

For the single-port demo with paid providers disabled, use [DEMO.md](DEMO.md). The current implementation boundary is recorded in [the workspace implementation notes](docs/design/workspace-redesign/IMPLEMENTATION.md); the earlier [workspace handoff](docs/handoff/creative-workspace-demo.md) remains historical. These instructions also support development and later explicitly authorized provider evaluation.

Research a video through Timeline and an agent-driven Structure graph, develop Ideas with or without a reference, or save a user-authored idea before explicitly approving it for Production. Project inputs and editing drafts persist independently. The dedicated fictional sample works offline. Real tasks use server-side OpenAI adapters for visual/OCR evidence, timestamped speech, creative generation and focused Structure research. Passing offline integration checks does not establish live recognition accuracy or creative effectiveness; consult the evaluation report for actual measured calls.

Read [the M2 implementation handoff](docs/handoff/m2-brief-experience.md), [the provider foundation](docs/handoff/bilingual-provider-contracts.md), [interfaces](docs/interfaces.md) and [provider decisions](docs/decisions/real-provider-v0.4.md). The committed [requirements package](docs/video-anatomy-handoff/README_FIRST.md) is preserved documentation; its historical snapshots must not replace current application files.

## Install

Use Python 3.12, Node >=22.12, npm >=10, FFmpeg/ffprobe with `libx264`, HEVC decoding and AAC support. HEVC fixture tests also need `libx265`. Automated browser checks need Chromium. Cloud used Python 3.12.14, Node 24.19.0 and npm 11.9.0; this does not configure either teammate's computer.

From the repository root:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
npm --prefix frontend ci
cd frontend
npx playwright install chromium
cd ..
```

An installed Chromium can be selected with `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium`. In a cloud workspace with a read-only npm home cache, use `npm --cache /tmp/video-anatomy-npm-cache --prefix frontend ci`. Browser servers and FastAPI TestClient checks need loopback socket access. No external model request is part of offline verification.

## Start and review

Run these in separate terminals:

```bash
.venv/bin/python -m uvicorn backend.app.api:app --host 127.0.0.1 --port 8000
```

```bash
npm --prefix frontend run dev
```

Open [the app](http://127.0.0.1:5173) or [API reference](http://127.0.0.1:8000/docs). Use one backend worker. No public deployment or authentication is provided.

Create a task and choose the work you need:

- **Research / Timeline:** import a reference, optionally adjust its Content area, analyze it and inspect source-timed observations. A brand brief is not required. Sampled visual points do not imply complete scene coverage. Optional corrections remain available; **Use this reviewed analysis** is required when reference evidence will drive creative generation.
- **Research / Structure:** start source analysis to receive a narrative/persuasion graph and transferable methods. The agent shows a video-based draft before focused background research finishes. Select nodes to inspect evidence or provide optional feedback; changes are proposed for adoption instead of silently replacing supplied context. A failed research phase preserves useful results. Select methods/nodes or the complete analysis for **Use in Ideas**.
- **Ideas:** apply usable project inputs and choose English or Chinese. Generate two original directions without a reference, use exact reviewed reference evidence, or save your own idea. Reference-free work carries no invented video citations. Draft selection is not approval; explicitly approve the exact direction to start production generation.
- **Production:** generate from the approved direction, edit the brief/storyboard, and export PDF through the browser print dialog or download CSV/Markdown. Prior work remains visible. Save pending output edits before exporting current content.

Project inputs save partially and independently. Applying inputs still requires the necessary brand/product/audience/platform/goal/duration fields and a confirmed usable claim; this confirmation permits use rather than certifying factual truth. Draft edits alone do not overwrite applied inputs. Applying changed inputs preserves history and invalidates affected approval. Changing unrelated reference media does not invalidate an original idea that never depended on that reference.

Long recognition and generation operations return activity tickets, with local progress/error feedback. You can change workspaces while processing continues. Restart closes interrupted work without replaying a possibly billed request. The fictional sample is clearly labeled and uses authored observations/Structure; arbitrary sample feedback is saved honestly rather than presented as model reasoning.

For real media, an absent backend key produces an explicit configuration failure, never sample findings. Partial video observations can support a limited Structure explanation; reference-driven creative generation still requires a successful, reviewed analysis. Original creative drafting remains available independently of that review.

## Configure providers

`.env.example` documents settings; the app does **not** automatically load `.env`. Export settings in the backend terminal or use the environment's secret mechanism. Never put a key in frontend code, Git, screenshots or chat.

| Setting | Default / purpose |
|---|---|
| `OPENAI_API_KEY` | Unset; backend only. |
| `VIDEO_M2_PROVIDER`, `OPENAI_M2_MODEL` | `openai`, `gpt-4.1-mini`; independent bounded notes extraction/task suggestions. `disabled` keeps manual editing available. |
| `VIDEO_VISION_PROVIDER`, `VIDEO_TRANSCRIPTION_PROVIDER`, `VIDEO_CREATIVE_PROVIDER` | `openai`; independent capabilities. |
| `OPENAI_VISION_MODEL`, `OPENAI_CREATIVE_MODEL` | `gpt-4.1-mini`; independent settings. |
| `OPENAI_STRUCTURE_MODEL`, `OPENAI_RESEARCH_MODEL` | `gpt-4.1-mini`; structured reasoning and bounded hosted search. |
| `STRUCTURE_RESEARCH_MAX_CALLS`, `STRUCTURE_MAX_SECONDS` | `2`, `120`; finite automatic research/run bounds. |
| `VIDEO_EXPERIMENT_MAX_USD` | `3`; cannot exceed the authorized experiment limit. Shared persistent reservations apply before requests. |
| `VIDEO_EXPERIMENT_BUDGET_PATH` | `<data-dir>/provider-budget.sqlite3`; preserve this ledger across evaluation modules/restarts. |
| `OPENAI_TRANSCRIPTION_MODEL` | `whisper-1`, for usable segment timestamps. |
| `ANALYSIS_OUTPUT_LANGUAGE`, `CREATIVE_OUTPUT_LANGUAGE` | `English`; analysis descriptive prose only. Creative workspace choice overrides the environment for M6/M7. OCR/ASR and approved fixed wording retain their original language. |
| `OPENAI_TIMEOUT_SECONDS`, `OPENAI_MAX_RETRIES` | `45`, `2`; finite timeout and transient retries. |
| `OPENAI_MAX_OUTPUT_TOKENS` | `8000`. |
| `VIDEO_ANALYSIS_MAX_FRAMES` | `12`; sparse source JPEGs, configurable up to 24. |
| `VIDEO_AUDIO_CHUNK_SECONDS`, `VIDEO_MAX_AUDIO_CHUNKS` | `60`, `3`; nonoverlapping mono 16 kHz WAV chunks. |

Ordinary real-task actions call the configured provider and may incur charges. The separate live-test harness additionally requires explicit opt-in/budget. An API key alone never causes the offline suite to make paid calls. Supported model IDs/capabilities are in `backend/app/providers/transport.py`; unsupported models fail before requests. Recognition sends required sampled images/audio; original videos are not directly uploaded. Structure sends extracted observations and focused research queries, and may invoke hosted web search. See [verified official API references](docs/decisions/real-provider-v0.4.md).

To add another provider, implement `VisionProvider.extract` and/or `TranscriptionProvider.transcribe`, inject into `ProviderRecognitionAdapter`, and return the same normalized records. Creative adapters retain `generate_directions`, `refine_direction` and `generate_production`. Inject using `WorkflowService(real_recognition=..., real_creative=...)`; downstream records/UI remain unchanged. Alternate-provider tests demonstrate substitution, not a second real vendor. Fine-tuning is not part of this implementation; model-quality work begins with sourced evaluation and prompt/evidence improvements.

## Media and timing

| Input | Handling |
|---|---|
| H.264 MP4, optional AAC | Original playback and measured source frame map. |
| HEVC MP4, Main SDR 8-bit `yuv420p`, optional AAC | Original bytes/hash/codec/timing retained; validated H.264 browser derivative with its own measured clock. |
| VFR, fractional FPS, shifted origin, display rotation | Actual frame boundaries; source/proxy count and decoded frame correspondence checked. |
| No audio stream | No ASR request; explicit no-audio determination. Music/SFX remain `not_analyzed`. |
| MOV, HEVC 10-bit/HDR/PQ/HLG, unusual profiles, unsupported streams or corrupt media | Actionable rejection; no universal profile/color fidelity claim. |

Defaults remain 50 MiB original upload, 180 seconds, 1920×1920. Probe/decode/transcode timeout defaults are 15/60/180 seconds; configure through `.env.example`. Derivatives can exceed the original upload size cap. Reference intervals use original zero-based integer frames with exclusive ends; the player maps those indices through the selected playback clock. Storyboards retain independent planned seconds. Fractional/VFR nominal timecode is approximate.

Visual/OCR findings cover sampled frames, not every frame or precise shot boundaries. Sparse sampling can miss brief text/actions. Speech timestamps are model estimates normalized to measured frames; frame indices do not prove semantic frame accuracy. Nonoverlapping audio chunks can split words. Validate these limitations using permitted annotated clips.

## Storage and migration

Direct developer Uvicorn startup defaults to ignored `.local-data/`. The local launcher uses a stable application-data location; on macOS this is `~/Library/Application Support/Video Anatomy/`, overridable by `VIDEO_ANATOMY_DATA_DIR`. See [LOCAL_API.md](LOCAL_API.md) for non-destructive import of an older bundle. The data directory contains SQLite aggregates, original/proxy media and persistent provider results. Moving an original upload after a successful import does not break its retained copy. Cache keys include source hash, model/provider, prompt/schema/preparation versions and settings. Hits create a fresh analysis identity without claiming a new provider run. Corrections never overwrite original extraction or enter recognition cache. Safe diagnostics in `provider-cache/runs.jsonl` record usage/timing/references; unknown usage/billed cost stays null. Cache content is private local data.

Back up the entire data directory before upgrading/moving machines. M2 and idea/analysis/direction/production drafts live in separate SQLite tables with independent versions. Background operation tickets and Structure runs/history/handoffs also use separate tables; they do not rewrite task aggregates. Keep original media, saved work, paid provider results and budget reservations; they are not disposable browser cache. New records default to v0.7, while existing v0.6 records remain compatible without rewriting their content or approval. Saved v0.5 tasks migrate transactionally to v0.6 with an unset generation language, nullable media tombstone and output bundle metadata, and auxiliary review flags. Earlier v0.4 tasks additionally receive claim metadata, retaining history/approval and recording claim confirmation as `legacy_unrecorded`; review and confirm before new creative actions. Earlier v0.3 tasks additionally gain `visual_details=null` and `playback=null`. Exact original JSON is archived transactionally in SQLite. No labels, language guesses, proxy or fresh review are invented. Existing v0.2 timing migration and explicit v0.1 import remain supported. Historic schemas/examples remain unchanged. See [interfaces](docs/interfaces.md).

## Verify offline

```bash
bash scripts/verify.sh
```

Runs dependency consistency, schema/type drift, Python lint/tests, frontend timing tests, TypeScript, ESLint, build, original sample browser tests and separate fake-provider HEVC/bilingual browser tests. Those use `scripts.mock_provider_server:app`, a **test-only** entry point with authored synthetic outputs. Production configuration cannot select it; never use it to claim real recognition.

Focused checks and regeneration:

```bash
.venv/bin/python -m pytest -q tests/test_media.py tests/test_media_preparation.py
.venv/bin/python -m pytest -q tests/test_providers.py tests/test_creative_provider.py tests/test_provider_workflow.py
npm --prefix frontend run test:e2e:providers
.venv/bin/python scripts/export_contracts.py
npm --prefix frontend run contracts:generate
```

The TypeScript generator omits unsupported conditional clauses only from its generation input; full JSON schemas and Python semantic validation remain authoritative. Current generated contracts are `contracts/v0.7.*.schema.json`. Retained examples include `examples/v0.6.*.json`; all v0.1–v0.6 schemas/examples remain historical and are not rewritten to manufacture new feature examples. Seed playable synthetic media with `.venv/bin/python scripts/load_sample.py --complete`; scripted confirmation/approval is demo data, not human review.

## Live evaluation and team review

The new bounded experiment is described in [the module evaluation guide](docs/evaluation/BUDGET_AND_MODULE_EVALUATION.md); use its report to distinguish measured results from unavailable calls. Do not infer live success from the fictional sample or mock tests. The earlier [live-validation procedure](docs/live-validation.md) remains a separate provider-foundation harness. The harness requires explicit `RUN_LIVE_MODEL_TESTS=1`, a key, an authorized positive `LIVE_TEST_MAX_COST_USD`, permitted hashed four-case clips and current verified pricing. It reserves a conservative bound before every attempt/retry and retains previous reservations. Reservations are not an invoice or an exact billing ceiling.

Frank can run the offline demo and review correction/approval UX. Andrea can annotate permitted English, Chinese, mixed and cross-language clips, then evaluate sampling and chunk-boundary accuracy. Coordinate changes to shared models/adapters/service/API. Keep main unchanged until authorized review/merge. Git transfers source, not keys, dependencies, media or task data.

## Desktop packaging

The Electron packaging source and macOS build instructions are in `desktop/`. A Linux browser/build test does not validate a macOS installer. A DMG requires a macOS build with bundled backend/runtime tools and installation testing; Developer ID signing/notarization is needed for the intended distribution experience. Refer to the desktop README for actual build status and limits. All launchers and delivery documentation are English.
