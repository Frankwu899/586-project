# Human reference review — contract v0.3

This guide is for a human reviewing one reference video and its analysis. It is a team worksheet, not a training dataset or an accuracy benchmark. Use `data/templates/reference_review_v0.3.csv` for event-level review, the existing `video_manifest.csv` for source and dated public metrics, and `creative_review.csv` for evaluation of creative outputs. The original five templates and the v0.2 reference-review worksheet remain unchanged for historical records.

## Record the source before reviewing

Use the saved task, video, analysis ID, and exact analysis revision from the application. Record the video's source URL if known, local file name, duration, language, and the basis for using it in `video_manifest.csv`. A URL is provenance only; the application does not download platform links. Do not infer rights from public availability. Use `unknown` when permission is not established.

The legacy manifest column `project_id` means the current `task_id`; keep its header when adding rows to an existing sheet. The manifest's duration remains measured in seconds. Record metric source and capture time with any observed views, likes, or comments. Leave unknown numbers blank; zero means an observed zero. Metrics may be unavailable. Never infer retention, clicks, conversion, causal effectiveness, or confidence percentages from public metrics.

## Review observations and sections separately

1. Open the exact reference media associated with the analysis. If it is missing, mark `media_unavailable`; do not claim that playback or observations were verified.
2. Play each section and expand its evidence. Record a review row for a particular event or section, including its stable ID and the analysis revision. Event text/description is the canonical observation. Sections refer to events and describe their role; do not create another editable transcript in a section.
3. Use integer frames from the **reference video**, with `0 <= start_frame < end_frame <= frame_count`. The first frame is `0`; the end is exclusive. At 20 fps, `[60, 65)` includes five frames and lasts about a quarter-second. A one-frame observation is valid. Visual and audio events may overlap or cross section boundaries. Primary sections are ordered and nonoverlapping. Planned storyboard intervals remain in seconds for the proposed new video and never belong in these reference-frame columns.
4. For a visual observation, describe only what is visible. For speech or on-screen text, transcribe what is actually heard or shown. Music/SFX descriptions must distinguish an observation from a guess. Coverage `not_analyzed` or `failed` is not evidence of silence or absence.
5. Put section-role interpretation in `interpretation_comment`. Put creative suggestions in `creative_hypothesis`; identify them as hypotheses and state a practical check in `proposed_test`. A `proof` role identifies a rhetorical claim in the source, not independently verified product performance.
6. Use the application's correction controls for recognized text, visual description, or section roles. Save the correction as a new revision. Keep original records and stable event IDs. Record timing/ID mistakes in this sheet for the developer; the application does not support timing, split/merge, or ID edits.
7. Review the saved correction, then use **Use this reviewed analysis**. This separate confirmation makes the current revision eligible for creative generation; it is not a certification that every observation is accurate. An upstream change makes dependent creative work outdated and requires renewed approval.

## Read frame timing

The loader records the source video's frame rate as `fps_numerator / fps_denominator`, its `frame_count`, and `rate_mode` (`constant` or `variable`). For example, `30000 / 1001` is approximately 29.97 fps. It also stores `frame_boundaries_seconds` on `VideoAsset.frame_timing`, with one playback boundary per frame plus the exclusive final boundary. This map lets the player locate frames using their measured timestamps, including videos whose frame durations vary. The worksheet records the map's video identity and summary metadata; do not copy the full map into a cell or derive frames by multiplying seconds by an assumed frame rate.

The review UI displays `HH:MM:SS:FF` and absolute frame indices. The timecode uses a rounded nominal frame rate without drop-frame conventions; fractional-rate and variable-rate timecodes are approximate labels. Use the absolute frame indices for this worksheet and the video's timestamp map for playback. Frame stepping and seeking support review with minor frame error; they are not a promise of frame-perfect editing accuracy.

Older records may have seconds but no available media or known frame rate. Their preserved `legacy_seconds` are historical values, not frame indices. If `frame_timing` or frame ranges are unavailable, leave the frame and frame-rate cells blank, record the limitation in `notes`, and use `media_unavailable` when playback is unavailable. Do not guess an FPS or reinterpret old second values as frames. These records remain readable but cannot be confirmed for new creative generation until usable frame timing is available.

## Worksheet conventions

- One specific finding per row. `record_type` is `event_review`, `section_review`, `timing_issue`, or `creative_hypothesis`. A blank unrelated cell means not applicable, not an absent observation.
- `schema_version` is `0.3.0`. Use the actual IDs and integer revision. The worksheet is a human record, not an API import format; CSV row content is never silently applied to application data.
- `lane` and `kind` describe the target evidence event. Use the values in the current analysis; do not invent an event because a category was not analyzed. Leave both blank for a section-only finding.
- `observed_start_frame` and `observed_end_frame` record the human observation with an exclusive end. They do not alter stored timing. Copy `fps_numerator`, `fps_denominator`, `frame_count`, and `rate_mode` from the saved video's `frame_timing`; do not substitute the intended storyboard duration or a future export frame rate. Identify a timing problem with `issue_type=timing`; send it to the recognition owner.
- `field_reviewed` identifies the event content or section `roles`. Copy the current value into `original_content` and place the proposed replacement in `suggested_content`. Do not put recommendation text in an observation field.
- Use `|` for multiple IDs or roles. Valid roles are `hook`, `product_demo`, `proof`, `cta`, and `other`; use `other` alone. Roles may repeat in different sections.
- Suggested issue types: `text`, `visual_description`, `role`, `timing`, `missing_observation`, `coverage`, `media_unavailable`, or `none`. Suggested statuses: `open`, `corrected_in_app`, `reviewed_no_change`, `deferred`, or `hypothesis_not_tested`.
- `resulting_analysis_revision` is filled only after the change is saved in the app. Do not claim a proposed correction was applied. Store UTC review timestamps; keep reviewers' names only if needed for team coordination.
- Export CSV as UTF-8. The supplied blank template includes a UTF-8 byte-order mark for spreadsheet compatibility. Preserve quotes and comma/newline escaping. When placing untrusted text into spreadsheets, treat formula-like content as literal text; this worksheet does not provide an import/sanitization pipeline.

## Fictional example

`examples/reference_review_v0.3.fictional.csv` and the historical source context in `examples/video_manifest.fictional.csv` are a deliberately fictional paper exercise, with invented reviewer, IDs, timestamps, and review findings. The v0.3 rows explicitly assume an invented constant-rate source of 20/1 fps and 200 frames; this metadata was not probed from real media or inferred during a migration. They illustrate source/unknown-metric recording, a content correction, a role correction, a timing issue, and a separate creative hypothesis. They are not an executed review, API import, model result, or playback test. No review row is evidence of measured accuracy or effectiveness. The unchanged v0.2 example uses seconds and remains a historical worksheet.

For the executable demonstration, load the dedicated synthetic task in the app. Its generated media contains illustrated shapes, on-screen labels, and synthetic tones; it contains no human speech or real product footage. Inspect its actual IDs and measured frame timing before recording a review. The original v0.1 examples mention a file ending in `NO_MEDIA.mp4`; that file name does not establish playable media and should not be substituted for the generated sample.
