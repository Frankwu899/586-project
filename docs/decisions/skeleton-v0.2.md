# Skeleton v0.2 implementation decisions

Task authorized by the repository-root `overnight-skeleton-spec.md`, confirmed 15 October 2026 (America/Los_Angeles). This supersedes the earlier documentation-only milestone for this task.

## Stack and environment

- Keep the proposed React / Vite / TypeScript frontend and FastAPI / Python backend.
- Tested Cloud runtimes: Python 3.12.14, Node.js 24.19.0, npm 11.9.0, FFmpeg/ffprobe 7.1.5. Chromium 154.0.8037.57 ran the automated sample workflow with Playwright 1.56.1, including H.264 playback and seeking.
- Python packages selected: FastAPI 0.141.1, Pydantic 2.13.4, uvicorn 0.52.1, python-multipart 0.0.32, httpx 0.28.1, jsonschema 4.26.0. Test/lint dependencies are pinned in the generated lockfile after installation.
- Frontend packages selected: React 19.2.0, Vite 7.1.12, TypeScript 5.9.3, React Vite plugin 5.0.4; Playwright 1.56.1 and ESLint for verification. The npm lockfile is authoritative for complete installed versions.
- Pydantic v2 models are the authoritative v0.2 definitions. Export JSON Schema and generate frontend types. Preserve the v0.1 schema and both existing examples unchanged; provide an explicit migration.
- Use SQLite task aggregates behind `TaskStore`, with atomic task updates and optimistic version checks. Run a single backend worker for the team demonstration. On startup, interrupted pending/running jobs become failed/retryable; there is no message queue or external database service.
- Synchronous deterministic sample adapters establish the boundaries; real recognition remains explicitly unconfigured. No paid API calls.

## Reversible technical defaults

- Local development uses backend port 8000 and frontend port 5173; Vite proxies `/api` to the backend.
- Store runtime data under ignored `.local-data/`, configurable with `VIDEO_ANATOMY_DATA_DIR`; generated media is never tracked.
- One reference video per task. Replacing a video preserves historical records and invalidates downstream currentness.
- Recognized events are canonical. Sections reference events and contain role interpretation only. Corrections clear affected interpretations rather than silently reuse invalidated reasoning.
- `chosen_direction` preserves the current radio choice separately from the explicitly approved `selected_direction`. Selection never approves a draft. An upstream change preserves content history, clears dependent choice/approval, and marks outputs outdated.
- Represent partial analysis coverage, but require a successful confirmed analysis for creative generation in this version. Categories marked `not_analyzed` remain visibly unknown; confirmation does not imply extraction occurred.
- Tested intake is MP4/H.264 with optional AAC audio. Defaults are 50 MiB, 180 seconds, 1920×1920 pixels, with 15-second probe and 60-second decode timeouts. These are configurable implementation defaults, not product promises of broad codec compatibility.
- Sample refinement deliberately recognizes a documented presenter-free instruction. Other text remains saved as uninterpreted production notes.
- No public deployment, provider calls, platform downloading, image generation, or model training.

The interface guide records actual module boundaries, media settings, coverage policy and version rules. The morning handoff records executed checks and remaining unconfigured providers; setup commands are in `README_SETUP.md`. Cloud checks do not establish Mac/Andrea-machine readiness.
