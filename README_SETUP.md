# Video Anatomy — v0.4 local workflow

Combine one brand/task brief and one reference video with reviewed evidence, two creative directions, explicit approval, an editable production brief and a text storyboard. The dedicated fictional sample works offline. Real tasks use replaceable OpenAI adapters for visual/OCR evidence, timestamped speech and creative generation when configured. Offline and real-media tests passed; live recognition accuracy has **not** been evaluated in this delivery.

Read [the implementation handoff](docs/handoff/bilingual-provider-contracts.md), [interfaces](docs/interfaces.md) and [provider decisions](docs/decisions/real-provider-v0.4.md). The committed [requirements package](docs/video-anatomy-handoff/README_FIRST.md) is preserved documentation; its historical snapshots must not replace current application files.

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

Create a task, save a brief, and load the dedicated sample before uploading anything to that task. Analyze, inspect/correct observations, and click **Use this reviewed analysis**. Generate two directions, edit/refine one, explicitly approve it, then generate/edit/export the production brief and storyboard. Upstream edits preserve history, clear dependent approval and mark outputs outdated. The sample understands the literal presenter-free instruction; other instructions remain saved as uninterpreted feedback.

For an actual reference, create another task and upload an MP4. Without a backend key, analysis reports unconfigured. With providers configured, the same review/approval steps apply. Partial observations are inspectable and their existing labels editable, but extraction status cannot be repaired through corrections. Rerun recognition and obtain a successful result before confirmation and creative use.

## Configure providers

`.env.example` documents settings; the app does **not** automatically load `.env`. Export settings in the backend terminal or use the environment's secret mechanism. Never put a key in frontend code, Git, screenshots or chat.

| Setting | Default / purpose |
|---|---|
| `OPENAI_API_KEY` | Unset; backend only. |
| `VIDEO_VISION_PROVIDER`, `VIDEO_TRANSCRIPTION_PROVIDER`, `VIDEO_CREATIVE_PROVIDER` | `openai`; independent capabilities. |
| `OPENAI_VISION_MODEL`, `OPENAI_CREATIVE_MODEL` | `gpt-4.1-mini`; independent settings. |
| `OPENAI_TRANSCRIPTION_MODEL` | `whisper-1`, for usable segment timestamps. |
| `ANALYSIS_OUTPUT_LANGUAGE`, `CREATIVE_OUTPUT_LANGUAGE` | `English`; descriptive/generated prose only. OCR/ASR retain original English, Chinese or mixed wording. |
| `OPENAI_TIMEOUT_SECONDS`, `OPENAI_MAX_RETRIES` | `45`, `2`; finite timeout and transient retries. |
| `OPENAI_MAX_OUTPUT_TOKENS` | `8000`. |
| `VIDEO_ANALYSIS_MAX_FRAMES` | `12`; sparse source JPEGs, configurable up to 24. |
| `VIDEO_AUDIO_CHUNK_SECONDS`, `VIDEO_MAX_AUDIO_CHUNKS` | `60`, `3`; nonoverlapping mono 16 kHz WAV chunks. |

Ordinary real-task actions call the configured provider and may incur charges. The separate live-test harness additionally requires explicit opt-in/budget. An API key alone never causes the offline suite to make paid calls. Supported model IDs/capabilities are in `backend/app/providers/transport.py`; unsupported models fail before requests. Only required sampled images/audio are sent; original videos are not directly uploaded. See [verified official API references](docs/decisions/real-provider-v0.4.md).

To add another provider, implement `VisionProvider.extract` and/or `TranscriptionProvider.transcribe`, inject into `ProviderRecognitionAdapter`, and return the same normalized records. Creative adapters retain `generate_directions`, `refine_direction` and `generate_production`. Inject using `WorkflowService(real_recognition=..., real_creative=...)`; downstream records/UI remain unchanged. Alternate-provider tests demonstrate substitution, not a second real vendor. Jev and training are deferred.

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

`VIDEO_ANATOMY_DATA_DIR` defaults to ignored `.local-data/`, containing SQLite aggregates, original/proxy media and `provider-cache/`. Cache keys include source hash, model/provider, prompt/schema/preparation versions and settings. Hits create a fresh analysis identity without claiming a new provider run. Corrections never overwrite original extraction or enter recognition cache. Safe diagnostics in `provider-cache/runs.jsonl` record usage/timing/references; unknown usage/billed cost stays null. Cache content is private local data.

Back up the entire data directory before upgrading/moving machines. Saved v0.3 tasks migrate to v0.4 with `visual_details=null` and `playback=null`; exact original JSON is archived transactionally in SQLite. No labels, language guesses, proxy or fresh review are invented. Existing v0.2 timing migration and explicit v0.1 import remain supported. Historic schemas/examples remain unchanged. See [interfaces](docs/interfaces.md).

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

The TypeScript generator omits unsupported conditional clauses only from its generation input; full JSON schemas and Python semantic validation remain authoritative. Current examples are `examples/v0.4.*.json`. Seed playable synthetic media with `.venv/bin/python scripts/load_sample.py --complete`; scripted confirmation/approval is demo data, not human review.

## Live evaluation and team review

No live model calls were made for this delivery. Follow [the live-validation procedure](docs/live-validation.md). The harness requires explicit `RUN_LIVE_MODEL_TESTS=1`, a key, an authorized positive `LIVE_TEST_MAX_COST_USD`, permitted hashed four-case clips and current verified pricing. It reserves a conservative bound before every attempt/retry and retains previous reservations. Reservations are not an invoice or an exact billing ceiling.

Frank can run the offline demo and review correction/approval UX. Andrea can annotate permitted English, Chinese, mixed and cross-language clips, then evaluate sampling and chunk-boundary accuracy. Coordinate changes to shared models/adapters/service/API. Keep main unchanged until authorized review/merge. Git transfers source, not keys, dependencies, media or task data.
