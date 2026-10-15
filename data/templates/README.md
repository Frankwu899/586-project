# Team Record Templates

**Current reference review uses frames in v0.3. Original v0.1 templates and the v0.2 worksheet are preserved. All template CSV files contain headers only.**

Use Excel, Google Sheets, or a text editor. Agree on who maintains each master table; CSV files do not provide live collaboration. Preserve column names, ID columns, and UTF-8 encoding when exporting. The provided CSVs include a UTF-8 byte-order mark for spreadsheet compatibility.

## Template purposes

| Template | How to fill it |
|---|---|
| `video_manifest.csv` | One video per row. Record source, `rights_basis`/`permission_note`, language, duration, and metric collection time. If permission is unverified, record `unknown`; do not guess. |
| `reference_review_v0.3.csv` | One event/section finding with exact task/video/analysis revision, source frame ranges and copied frame-rate metadata, separate observation, interpretation, and creative hypothesis. Follow `docs/reference-review-guide.md`; this is a human worksheet, not an API import. |
| `reference_review_v0.2.csv` | Historical reference-review worksheet using seconds. Retain existing records with their original headers; use v0.3 for new frame-based reviews. |
| `annotation_review.csv` | One specific issue or review finding per row. Record the analysis revision, `segment_id`, observations, and suggested correction. Keep interpretations separate in `interpretation_comment`. |
| `creative_review.csv` | One evaluation criterion per row. Suggested criteria: `brief_fit`, `evidence_traceability`, `production_clarity`, and `actionability`. Concrete problems and reasons matter more than an isolated score. |
| `technical_spike.csv` | One actual attempt per row. Distinguish access to audiovisual content from metadata-only access. Record failures, latency, cost, fallback, and the actual execution environment. |
| `api_cost_log.csv` | One attributable call or billing entry per row. Keep estimated and billed costs separate and retain their source. Do not add different currencies without an explicit conversion. |

## Recording conventions

- Use UTC timestamps, for example `2026-10-08T08:00:00Z`. Current reference intervals use zero-based integer frames with an exclusive end: `0 <= observed_start_frame < observed_end_frame <= frame_count`. A one-frame interval is valid. Legacy sheets retain their original seconds columns; video duration and planned storyboard intervals still use seconds. `file_size_mb_decimal` uses 1 MB = 1,000,000 bytes.
- Copy `fps_numerator`, `fps_denominator`, `frame_count`, and `rate_mode` from the source video's saved `frame_timing`. Fractional and variable frame rates are supported; the application uses the stored frame-boundary map for playback. UI `HH:MM:SS:FF` is a nominal, non-drop-frame label, approximate for fractional or variable rates. Use absolute frame indices in the worksheet. Leave unknown timing blank rather than guessing an FPS or treating archived seconds as frames.
- Leave unknown numeric values blank. Enter zero only when it was observed. Use `true`/`false` for booleans and `|` to separate multiple roles or IDs.
- `suggested_roles_pipe_separated` contains the applicable subset of `hook`, `product_demo`, `proof`, `cta`, and `other`. Do not combine `other` with another role.
- `rating_1_to_5_or_blank` is an informal team rating: 1 = unusable; 2 = major revision needed; 3 = moderate revision needed; 4 = usable with minor changes; 5 = usable for the present task. Leave it blank if no evaluation occurred. This is not a validated scale or a market-performance score.
- Use `hypothesis_not_proven` for claims still requiring validation. Co-occurrence of a creative feature and high views/engagement does not establish causality.
- Record timestamp errors even though the midterm UI does not support timestamp editing. Verified timing and localization errors inform technical corrections.
- Never include API keys, passwords, or unnecessary personal information. Retain a request ID only if it is safe to share.

The current guide and `examples/reference_review_v0.3.fictional.csv` provide a clearly fictional filled example with explicitly invented 20/1 fps source metadata. The v0.2 example remains unchanged as a historical seconds-based worksheet. The existing manifest and creative-review `project_id` columns map to current `task_id`; keep original headers for compatibility. Legacy segment-level sheets remain useful for historical records, while current recognized content belongs to evidence events. These worksheets neither import changes nor convert historical timing automatically.
