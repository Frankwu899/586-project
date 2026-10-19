# Timeline and capture-area implementation handoff

- Task: Replace the vertically stacked reference notebook with a bounded playback/timeline/inspector workspace and reversible recording cleanup.
- Environment: Codex Cloud Linux; Python 3.12, FFmpeg, Chromium and Playwright. No macOS execution.
- Branch: `feat/workspace/structure-agent-redesign`.
- Starting commit: `a636ff1e0d864e871a85aa222a8c1258bbc822e7`; integration commit and PR are owned by the coordinating agent.
- Scope: Application implementation authorized by the owner on 18 October 2026. No paid calls, model training, merge or deployment were performed by this workstream.

## Delivered behavior

- Research Timeline is a bounded three-pane workspace: original/managed playback, one selected annotation inspector, and visual/text/speech/interpretation tracks. Other saved audio events remain accessible when present.
- Visual/OCR sampling is represented by points, not invented continuous shots. Speech uses existing measured-frame intervals. Role interpretation stays explicitly separate. Buttons and arrow keys select evidence and seek original frame indices.
- Repeated OCR wording is grouped for browsing; every source event ID and sampled time remains intact. Multiple text observations at one sample are accessible in the inspector selector. Grouping never treats a stationary price/logo as noise.
- Existing correction drafts, explicit application, original revision history and separate review confirmation are preserved. Errors, retry controls and running states are local to the operation/inspector.
- Content-area editing is a native modal with source preview, start/middle/end checks, edge trim controls and optional floating-control masks. Coordinates are normalized to the displayed original after autorotation. Source bytes, audio and timing are unchanged.
- Region persistence and task invalidation share one SQLite transaction. Unchanged saves are no-ops. Only pending analysis corrections block a changed content area; unrelated idea drafts survive.
- Conservative local suggestions inspect five sampled frames for persistent near-flat edge bars. They remain suggestions until saved. The recognition prompt separately excludes clearly external platform chrome while retaining valid subtitles, prices, logos and filmed app demonstrations.
- Vision cache identity includes region revision/source/fingerprint. Unchanged source-aligned speech has an independent cache, avoiding repeated transcription after a visual crop or vision-model change.
- Source-media tools include exact-original relink controls connected to the desktop delivery workstream's hash-checked endpoint. Different bytes must be imported as a new reference.

## Files owned by this workstream

- `backend/app/content_region.py`
- `backend/app/media_preparation.py`
- `backend/app/providers/recognition.py`
- `frontend/src/ReferenceWorkspace.tsx`
- `frontend/src/AnalysisReview.tsx`
- `frontend/src/ContentAreaEditor.tsx`
- `frontend/src/analysisReviewModel.ts`
- `frontend/src/m5.css`
- `tests/test_content_region.py`
- `tests/test_providers.py` (cache expectations updated for independent ASR reuse)
- `frontend/tests/analysis-review.test.mjs`
- `frontend/e2e/analysis-review.spec.ts`

Root-owned integration adds the optional recognition request region, captures/checks immutable region fingerprints, mounts the router and connects the new async operations. The region side table is additive and does not require embedded per-asset schema migration.

## Verification

- Focused capture/preparation/media/provider tests: 72 passed, including rotated-HEVC and independent-idea regressions (`pytest tests/test_content_region.py tests/test_media_preparation.py tests/test_media.py tests/test_providers.py -q`). The broader integrated suite is reported by the coordinator.
- Browser checks: four focused Playwright scenarios passed using isolated temporary ports; the temporary config was removed after verification, and these scenarios remain in the default Playwright suite. Covered bounded windows at 1440x900 and 1280x800, one inspector, keyboard frame seek, draft reload, exact review confirmation, local failed-save retry and real uploaded-media crop saving without recognition calls. An additional 1024x768 fit check passed.
- TypeScript typecheck and scoped ESLint passed after initial UI integration. Scoped Ruff passed.
- Real browser screenshots were visually inspected and saved outside Git as `workspace-timeline.png` and `workspace-content-area.png` in `/workspace/video-anatomy-artifacts/`.
- The rotated-HEVC regression discovered during the broader media suite was fixed: transforms now use decoded display dimensions after FFmpeg autorotation rather than encoded width/height. Both source-frame identity and crop dimensions are asserted.

## Offline sample measurements and limits

| Owner-provided source | Suggestion runtime observed | Result | API spend |
|---|---:|---|---:|
| `Video-82834.mp4` | 1.534 s | No reliable edge bars; full frame retained | $0 |
| Lei Jun Guandan screen recording | 0.325 s | Suggested bottom-edge trim of 4.375% | $0 |

These are single local preprocessing runs, not a latency benchmark. The Guandan recording contains floating phone/app chrome over the content; the edge-bar heuristic does **not** fully identify or remove it. Manual non-destructive masks and the semantic vision instruction address that path, but real model output accuracy remains unmeasured without authorized live evaluation. There is no trained screen-chrome detector and no fabricated accuracy score.

The crop preview and schema preserve valid interior static content. Independent semantic segmentation, object boxes, continuous OCR tracking, exact shot detection and real audio waveforms are not implemented by this workstream. The timeline exposes the actual available evidence rather than drawing fabricated data.
