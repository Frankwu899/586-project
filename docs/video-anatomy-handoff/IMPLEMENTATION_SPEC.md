# Video Anatomy: First Real Recognition and Editable Data Contract

Status: implementation handoff, 16 October 2026. Requirements are not evidence of completed implementation.

## 1. Outcome and scope

Extend the existing Video Anatomy application so a team member can upload one product-marketing reference video, read a real time-aligned analysis, correct its text and structured labels, confirm that exact analysis revision, and use the existing creative-direction and production workflow. The first real model provider is OpenAI. Keep providers replaceable. Defer TypeSafe Jev.

The product context remains one brand/task brief plus one reference video; two editable creative directions; explicit direction approval; a creative brief and text storyboard. Retain the current application and its sample workflow. Do not rebuild the app, redesign its UI, add a general agent platform, or train a model.

Primary work: M10 contracts, M3 intake, M4 recognition and M5 review. M6–M8 require compatibility checks and minimal real OpenAI wiring through their existing interfaces, not new product features.

## 2. Decision register

### Confirmed product requirements

- Structure the analysis into timed evidence events and nonoverlapping narrative content segments. This is not an exhaustive record for every frame or a professional shot-cut detector.
- Retain natural-language observations and add structured subjects, visible actions and product-presentation methods.
- Support H.265/HEVC reading in addition to existing H.264 support.
- The first demo must recognize/read English, Chinese and mixed-language content. Test spoken and on-screen text separately. Preserve the original source wording.
- Accept and preserve English/Chinese brand information, prompts, corrections, saved content and exports.
- First integrate OpenAI. Separate model configuration by capability; future providers must not require changes throughout the UI and downstream data consumers.
- Users may correct recognized words, descriptions and segment roles. They may also correct subject categories, action categories and product-presentation labels. Preserve originals and correction history; invalidate dependent approvals/current outputs appropriately.
- Jev, model training and fine-tuning are deferred.
- Keep observed video evidence distinct from creative interpretation and unverified performance hypotheses. Only public views/likes/comments are presently available; do not invent retention, clicks or conversion data.

### Implementation defaults, not additional user promises

These defaults let implementation proceed without another interview. Document material deviations with reasons.

| Topic | Default |
| --- | --- |
| Contract version | Propose v0.4.0 if the live repo is still v0.3.0. If it has advanced, choose the next compatible version and migrate without downgrading. |
| Video containers | Require MP4 with H.264 or HEVC. MOV remains unconfirmed and is not required by this mission. Do not advertise universal codec/profile compatibility. |
| Upload limits | Preserve existing configurable duration/size/dimension limits, currently 180 seconds, 50 MiB and 1920 by 1920; verify live code. Explain rejected media clearly. |
| Output language | Preserve source OCR/ASR text. Use independently configurable analysis/creative narrative language, initially English for the English demo. No full UI localization or new language-selection workflow is required. |
| Music/SFX | Optional, truthful coverage. If not implemented, use not_analyzed; do not derive sounds from images or claim silence. |
| Unknown labels | Use null with meaningful descriptions/uncertainty. A field being present does not require fabricating a category. |
| Structured-group failure | Retain successful observations but mark the analysis partial if any attempted structured group failed. Extend partial-state validation consistently. Keep partial/failed results blocked from creative generation; do not weaken the existing success/review gate. |
| Live tests | Off by default. Require credentials, explicit live-test opt-in and an explicit budget. US$20 was suggested, not approved as spending authorization. |
| Performance | Measure end-to-end time and cost. Five minutes was a suggested target, not an agreed SLA or a proven result. |

### Deferred

Multiple references, platform link downloads, cross-shot identity tracking, exhaustive object detection, bounding boxes, demographic inference, exact camera reconstruction, detailed music analysis, image storyboards, public deployment and full UI redesign. HDR/Log and unusual HEVC profiles require actual compatibility testing before claims. Preserve the future extension points without building these features now.

## 3. Functional module tree

| Module | Sub-functions | Inputs | Deliverables |
| --- | --- | --- | --- |
| M10 Shared contracts | Versioned models; schema/types generation; migration; nested validation; correction replay; source references | Existing records and this contract extension | One canonical validated format consumed by all modules |
| M3 Video intake | Stream/codec probe; limits; original storage; source timing; HEVC decode; playback derivative | Uploaded MP4 | VideoAsset, playable source/proxy and authoritative source frame map |
| M4.1 Media preparation | Source-aligned frame sampling; audio extraction; bounded chunking; cache | Saved original and source timing | Provider inputs with explicit original time mapping |
| M4.2 Visual/text extraction | Observe visible content; read on-screen text; retain uncertainty | Time-labeled frames/short sequences | visual_action and on_screen_text events |
| M4.3 Speech extraction | Transcribe; handle English/Chinese switching; normalize timestamps | Extracted audio and source offset | speech events distinct from visual captions |
| M4.4 Classification/segmentation | Subject/action/presentation labels; narrative roles; evidence linking | Observations and transcript | visual_details and ContentSegments |
| M4.5 Normalization | IDs; frame conversion; schema and semantic checks; coverage; job errors | Raw provider results | AnalysisResult or explicit failed/partial result |
| M5 Review | Inspect evidence; edit permitted fields; validate; append revision; confirm exact revision | Successful or inspectable partial analysis | Preserved original, correction log and reviewed revision |
| M6–M8 Existing creative workflow | Two directions; written refinement; approval; brief/storyboard generation; export | Brand brief and exact reviewed evidence | Validated drafts and production outputs with precise citations |
| Provider access | Capability checks; routing; configuration; timeouts; usage accounting | Capability request and model configuration | Provider-independent normalized results and diagnostics |

## 4. M10: data-contract work

Read DATA_CONTRACT.md and the pinned reference files. The live repository's models remain the executable source of truth. Never copy the reference snapshot over live code.

1. Add the structured visual extension, playback representation and permitted correction field through a versioned migration.
2. Keep source reference timing as integer, zero-based, half-open [start_frame,end_frame). Keep storyboard planning in independent seconds.
3. Generate frontend types/JSON schemas from the canonical models using the repository's process; retain historical schemas and migrations.
4. Old visual events migrate to visual_details=null. This means structured analysis was not performed, not that the scene has no subjects. Old videos migrate to playback=null. Do not invent language tags or confidence scores.
5. Preserve original analysis content, all revisions and exact citations. A schema migration must not claim a new user review or silently rewrite historical meaning. Preserve an untouched backup/read path for old stored data as the repository already requires.
6. Full re-analysis creates a new analysis identity. Human correction preserves analysis_id and advances revision. Never overwrite an approved analysis with output from a different model.

## 5. M3: H.265 intake and playback

- Probe actual streams; do not decide compatibility solely from a filename. Preserve existing defenses against malformed files, excessive size, invalid durations, multiple unsupported streams and invalid paths.
- Keep original uploaded bytes and their content hash. video_codec must describe the original codec, including hevc; never report h264 just because a derivative was generated.
- Decode the original to obtain presentation-order frames and their measured timestamps. Preserve variable frame rates, signed media origin and rotation behavior. No guessed FPS or silent constant-frame-rate replacement of the source clock.
- For HEVC, create an H.264 playback representation when required for the supported browser path. Keep its clock separate from the original and validate frame correspondence. The proposed representation deliberately requires one output frame for each source frame, in the same order. Do not apply an fps filter that drops/duplicates frames.
- Probe both original and derivative. Reject or explicitly fail normalization if correspondence cannot be established. Use a synthetic frame-distinguishable fixture to test the mapping, not just a duration comparison. Browser seeks use the selected playback representation's own clock while event IDs remain source-frame based.
- Test H.264 regression, HEVC decoding/playback and audio/no-audio cases. Record supported profiles and actual limits. Do not claim HDR/Log color fidelity from a successful decode alone.
- Avoid uploading originals to unrelated services. Send only required frame/audio inputs to the explicitly configured provider.

## 6. Provider interfaces and real recognition

Preserve the public module interfaces unless a documented migration is necessary:

```text
RecognitionAdapter.analyze(RecognitionRequest) -> AnalysisResult
CreativeAdapter.generate_directions(brief, analysis) -> list[CreativeDirection]
CreativeAdapter.refine_direction(brief, analysis, target, feedback) -> CreativeDirection | None
CreativeAdapter.generate_production(brief, analysis, direction)
    -> (ProductionCreativeBrief, TextStoryboard)
```

Inside the implementation, isolate visual extraction, timestamped speech transcription and structured/text generation behind provider adapters. Keep source-media processing and domain validation independent of provider SDK response types.

- Implement OpenAI first and deterministic fakes for offline tests. A fake second provider should demonstrate that consumers do not rely on OpenAI response objects. Do not pretend a second real provider is integrated.
- Separate provider/model configuration for vision, transcription and creative generation. For example, use capability-scoped settings plus OPENAI_API_KEY; adapt names to current repository conventions.
- Check capability support before calling. A text-only endpoint cannot satisfy vision. A transcription endpoint without usable timing cannot silently satisfy timestamped transcription.
- Verify current official API documentation during implementation. Pick documented model IDs, record the selected IDs, and keep them configurable. Do not assume an arbitrary GPT model accepts MP4 or that all speech models expose word timestamps.
- Keep API credentials server-side and out of source, fixtures, exported files and logs. No keys are included in this handoff.
- Use structured response constraints where supported, then perform local semantic validation. Correct JSON syntax alone is insufficient.
- Apply finite timeouts, bounded transient retries and bounded concurrency. Do not retry authentication, exhausted-credit or malformed-request failures indefinitely. Include retries in usage and budget accounting.
- Cache only with source content hash, provider/model, extraction/prompt/schema versions and relevant settings in the key. A changed model or prompt must not silently return an old cached result as a new evaluation.

### Recognition sequence

1. Probe/decode and prepare timestamped source frames and an audio track.
2. Run visual extraction and speech extraction independently where safe. Carry source offsets through chunking.
3. Build visual observations and OCR events; merge overlapping frame observations carefully without inventing exact temporal boundaries from sparse samples.
4. Normalize speech timestamps with the repository timing helpers. Deduplicate overlap between audio chunks without dropping genuine repeated words.
5. Classify significant subjects/actions/presentations and identify narrative segments with explicit evidence references.
6. Validate and persist the full original AnalysisResult; expose truthful coverage and errors. Set review.user_confirmed=false.

For a no-audio video, record a documented no-audio determination; do not fabricate an ASR call or speech. For unreadable/inaudible content, preserve uncertainty and do not translate a guess into a claimed source quote. Disagreement between visible captions and speech is valid evidence, not necessarily a transcription error.

### Diagnostics

Persist capability, provider, requested/resolved model when available, prompt version, input/source hash, job ID, analysis identity/revision or output reference, start/end time, elapsed milliseconds, usage counts with explicit units, cache status, attempts and safe failure code. Save this in an internal run record or existing job metadata; it need not become a speculative user-facing API field. Unknown usage/cost is null with an explanation, never zero. Distinguish estimated cost from provider-billed cost.

## 7. English/Chinese acceptance

The following are required, not optional follow-ups:

- English speech transcription and Chinese speech transcription each have their own evaluation cases.
- English and Chinese on-screen text each have evaluation cases. Check important product words, numerals/units, prices and CTA phrases.
- Include intra-video language switching, English brand names inside Chinese text/speech and at least one case where audio language differs from on-screen text language.
- Keep OCR text and ASR text as separate event kinds with their own intervals. Preserve original wording and script, including mixed-language strings. Translation cannot overwrite evidence text.
- Brand briefs, prompts, corrections and existing exports round-trip Unicode text through the browser, API and persistence without mojibake or silent truncation.
- Schema keys, IDs and machine enums remain stable English codes. Display labels may be Chinese without changing stored enum values.
- Report narrative output-language configuration separately from source recognition. Full bilingual UI localization is not a requirement.
- Fixtures and mocked provider outputs demonstrate integration only. Real recognition quality needs permitted real sample clips and human reference annotations. If clips or credentials are unavailable, deliver the harness and clearly mark live linguistic evaluation not run.

## 8. M5: structured-label corrections

Add minimal readable controls to the existing review screen for subject kind/roles, action type and presentation type, with the descriptions needed to explain other/unknown values. Retain existing text/description and segment-role editing. This is a functional extension, not a UI redesign.

Use one validated atomic correction of an event's visual_details object, or an equivalent typed mechanism that preserves identical replay guarantees. The proposed correction contract adds field=visual_details for target_type=event. The server captures the full before/after values.

For this first implementation, allow changes only to category/role values and their explanatory labels/descriptions. Do not allow users to change event timing, event/subject IDs, array order, relationship references, coverage status or extraction error fields. Adding/deleting observations and repairing missing extraction groups are separate future workflows. Validate category-role references atomically: removing a product role cannot leave a ProductPresentation pointing at a non-product subject. Reject that inconsistent edit with an actionable message instead of silently fixing unrelated fields.

Every accepted edit must:

1. Check the expected task/analysis revision and reject stale writes.
2. Preserve original extraction and earlier revisions.
3. Append a replayable correction and advance the analysis revision.
4. Clear confirmation for the changed revision.
5. Invalidate the dependent creative approval/currentness through the existing workflow, preserving all old outputs.
6. Require explicit review confirmation before fresh creative generation.

Never enable a raw arbitrary JSON patch editor against the entire task state. Visual-details null/failed states are displayed honestly; this phase does not let the user fabricate missing model observations by toggling a status.

## 9. Existing creative workflow integration

Implement only the existing OpenAI-backed generate_directions, refine_direction and generate_production methods required for the established demo. Preserve two directions, user text feedback and explicit approval. The workflow service, not the model, owns IDs, review/approval state and persistence.

Consume the current exact confirmed AnalysisResult and brand brief. Preserve production constraints and prohibited claims. Cite existing event IDs and exact analysis revisions; reject dangling or mismatched citations. Distinguish observed source claims from independently established facts. Never infer that a creative change improves retention/conversion solely from public views/likes/comments.

Changing providers/models must work through adapters; it must not erase user-approved work. Do not silently fall back to sample templates on a real-provider failure. The explicitly labeled sample mode remains available independently.

## 10. Verification matrix

| Area | Required checks |
| --- | --- |
| Contract and migration | Old v0.3 tasks load; generated schemas/types agree; new types reject invalid enums, whitespace-only required descriptions, duplicate IDs/roles and dangling references; JSON null is not the string null. |
| Timing | Valid integer half-open frames; bounds; fractional/VFR conversion; nonzero source origin; original/proxy correspondence; storyboard times remain independent seconds. |
| Coverage | observations iff nonempty items; none_found vs not_analyzed; explicit group failure; consistent partial status; partial/failed analyses remain blocked from creative generation. |
| Corrections | Text and old segment edits still work; structured edits replay; stale-write rejection; immutable timing/IDs/relationships; inconsistent product-role changes rejected; original preserved; review/approval invalidated. |
| Providers | Fake OpenAI responses; fake alternate adapter; malformed/refused/incomplete JSON; missing capability; timeouts; transient retry cap; auth/quota failure; absent key; no real-to-sample substitution. |
| Media | Existing H.264 regression; HEVC original metadata correct; browser playback derivative; audio/no-audio; malformed/oversized/unsupported inputs; repeated upload/storage handling. |
| Languages | English, Chinese, mixed, cross-language audio/OCR, Unicode input/edit/save/export; source words preserved and kept distinct from narrative descriptions. |
| End-to-end offline | Existing sample flow plus mocked real-adapter flow: upload, analyze, correct tags, confirm, two directions, refine, approve, generate/export; edit upstream and observe stale downstream state. |
| Live smoke | Explicit opt-in plus credentials, budget and permitted sample inputs. Report actual provider/model, latency, usage/cost, observed errors and human-checked outputs separately from offline results. |

Reuse and run the repository verification command, currently bash scripts/verify.sh, after inspecting it. Add focused tests for the new contract/media/provider boundaries. Do not inflate test counts or weaken checks merely to obtain a green report.

Live test behavior: RUN_LIVE_MODEL_TESTS defaults to 0; enabling it also requires an explicit positive LIVE_TEST_MAX_COST_USD (or repository equivalent). Bound frame/audio inputs, requests, output size and retries, account for already-used budget, and stop scheduling further paid requests when the budget cannot be safely respected. Provider-side billing caps may propagate with delay; do not promise an exact invoice ceiling. If no safe cost bound is available, do not run an unbounded live suite. A missing key/budget/media is a live-test blocker, not a reason to leave offline implementation unfinished.

## 11. Final implementation deliverables

- Working task branch with actual code changes; no unrelated reset/rewrite.
- Updated authoritative models, migrations, generated JSON schemas and frontend types.
- HEVC intake/playback, OpenAI provider adapters, bilingual evidence handling and structured-label correction flow.
- Meaningful offline tests and a separately invoked live evaluation harness.
- Updated README_SETUP.md, .env.example with placeholders only, docs/interfaces.md and relevant English handoff documentation.
- A tested synthetic contract example and bilingual evaluation cases clearly distinguished from actual recognized clips.
- A final handoff reporting commit/branch, actual changed paths, passed/failed/not-run checks, schema version/migration, model settings, credentials needed and remaining limits.

Do not claim the new behavior is implemented or verified merely because this document, a fixture, a screenshot or a mocked test exists.
