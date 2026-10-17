# Creative workspace v0.6 delivery

Date: 17 October 2026. Owner: main orchestrator with six bounded implementation agents (backend contracts/storage, creative adapters, task shell/drafts, reference review, directions, production/export). Scope follows Frank's confirmed Q1–Q22 decisions and explicit implementation authorization.

## Baseline and review order

- Repository: `Frankwu899/586-project`.
- Started from verified transfer `dba985b20d0a012a7b1e90b174fe8b30c96b58eb`, a documentation-only child of PR #4 head `243db859353abf5a8ccc70de2028ed0b706da70c`.
- PR #4 remains dependent on PR #3 (`da95ad3325a04b3b9f01cc7cb02a03af353208b5`). Main at takeover was `a456329e4fe8cab76669c8c8254cfed8ce11bbcb`; it is not the implementation baseline.
- Branch: `feat/integration/creative-workspace-demo`. Draft PR targets `feat/workspace/m2-brief-experience`, keeping prerequisites explicit. Review/merge prerequisites in order; this delivery performs no merge.
- Original working tree was clean. Historical transfer files and v0.1–v0.5 contract snapshots remain intact.

## Resulting behavior

The application now presents a persistent task panel and four work areas: Brand & task, Reference analysis, Creative directions, and Production & export. Reopening restores the active task/area. M2 retains its independent draft and Apply semantics. M5–M7 gain separate serialized server drafts, local failed-save recovery, exact formal checkpoints, conflict handling, and explicit discard.

Reference review presents sampled visual observations alongside every extracted speech/text event, with timing, source, uncertainty and separate role interpretation. Correction and review confirmation are distinct. Uploading only prepares playback; analysis/reanalysis remains explicit. Deleting reference media removes original/proxy files and playback, retains tombstoned provenance and historical analysis/creative text, and invalidates dependent current work. One active reference is a stage limit; the asset collection retains future multi-input/library extension room.

Directions require an explicit English/Chinese choice and show comparable idea, Hook, story, brand fit and resources. A follows the reference structure; B reorganizes useful elements. Source words, brand names and approved fixed wording retain their language. Manual text edits invalidate copied auxiliary explanations; users may acknowledge and approve their exact text without an AI round trip. Stale explanations do not constrain production. Each refinement creates a new draft requiring approval.

Production contains an editable brief and text storyboard with fixed shot count/order/planned seconds. Original shot ideas may have no citation and are labeled. Save and export uses the newly returned saved version; failures never download an older version as the requested latest content. PDF uses a dedicated combined document and the browser's **Print / Save as PDF** dialog, with no added PDF service. CSV and optional Markdown are downloadable. Historical exports require explicit selection and identify source/deletion status and exact revisions. New paired outputs use `bundle_id`; legacy records are not paired by matching revision numbers.

M9 is a team collection/evaluation workflow documented in [the rubric](../evaluation/m9-offline-and-live-rubric.md); no active network/library search was added.

## Contracts and implementation choices

Pydantic remains canonical. v0.6 adds generation language, media tombstones, auxiliary review status, output bundle IDs and independent editor endpoint models. SQLite migration archives exact original payload/hash and does not infer old language, output pairing or fresh review. Generated JSON Schema and TypeScript stay synchronized. Source evidence uses original integer half-open frame intervals; production retains separate planned seconds.

The demo launcher serves the built UI and API on one loopback port with explicitly disabled paid providers even if the shell contains a key. See [DEMO.md](../../DEMO.md) for macOS/Linux and Windows launchers, persistence and walkthrough. The source bundle includes built frontend assets but excludes credentials, installed dependencies, media, databases and local runtime artifacts. It needs Python 3.12 and FFmpeg; initial dependency installation needs internet. This is a local demo, not a hosted deployment.

## Verification

Verified in the managed Linux workspace using Python 3.12, Node 24, system Chromium and FFmpeg. No live provider calls were made.

- Full Python suite: **448 passed**. One existing FastAPI/Starlette TestClient deprecation warning remains.
- Frontend unit checks: **30 cases passed** across six files (also executed directly to report individual cases; the environment's aggregate runner reports six file results).
- Full offline browser workflow suite: **21 passed**, covering original M2 races/keyboard/responsive behavior, M5 draft/apply/confirm, M6 language/approval/history, task and area restoration, reference deletion/replacement, M7 draft/export and complete sample workflow.
- Final navigation-recovery correction: **12 passed** in the scoped M2/shell rerun, including one new hidden-conflict regression. The default suite now contains 22 distinct cases; combined with the provider suite, **26 distinct browser cases passed** across the full and final affected reruns.
- Deterministic provider browser suite: **4 passed**, including real HEVC playback/proxy clocks, bilingual correction, explicit approval, saved exports, partial coverage and M2 proposal/error behavior. Providers are injected fixtures, not real model calls.
- `pip check`, Ruff, authoritative schema drift check, generated TypeScript check, TypeScript build, ESLint, production Vite build and whitespace checks passed.
- Opened the built single-port app in Chromium and completed sample analysis → review → Chinese directions → explicit approval → production → PDF. Desktop and 390px views were inspected. A deliberately long bilingual PDF produced five A4 pages; text extraction retained all repeated Chinese/English content and the final shot.

Integration caught and corrected outdated contract fixtures and old browser selectors after the reading-first UI change. Independent review also found and fixed historical-direction draft recovery, competing-tab draft conflict handling, historical export filenames, literal Markdown text escaping, and access to a hidden editor when its draft cannot flush. Additional recovery regression results are recorded in the final orchestration status.

## Remaining acceptance and limits

Human visual/product acceptance remains pending. Passing offline checks establishes workflow correctness for these cases, not actual recognition accuracy, creativity, marketing effect, API latency/cost or unrestricted feedback understanding. The fictional sample uses deterministic templates and a documented presenter-free refinement; unsupported instructions are retained honestly. M2 assistance is unavailable in the offline demo while manual input remains usable.

Tomorrow's evaluation needs the user's permitted sample videos, intended brand/task brief, exact approved claims and qualifications, production resources, chosen language, and explicit live-test authorization/budget. Record recognition, A/B distinction, grounded citations, qualification propagation, resource feasibility and production usefulness separately. Broader codecs/profiles, exhaustive segmentation, multiple active inputs, library retrieval, account systems and public hosting remain future work. The Windows launcher is provided but has not been executed on Windows; neither teammate's local machine has been configured by these cloud checks.

No main merge, public deployment or paid API call was performed.
