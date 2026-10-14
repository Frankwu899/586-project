# Team Record Templates

**Proposed v0.1. CSV files contain headers only.**

Use Excel, Google Sheets, or a text editor. Agree on who maintains each master table; CSV files do not provide live collaboration. Preserve column names, ID columns, and UTF-8 encoding when exporting. The provided CSVs include a UTF-8 byte-order mark for spreadsheet compatibility.

## Template purposes

| Template | How to fill it |
|---|---|
| `video_manifest.csv` | One video per row. Record source, `rights_basis`/`permission_note`, language, duration, and metric collection time. If permission is unverified, record `unknown`; do not guess. |
| `annotation_review.csv` | One specific issue or review finding per row. Record the analysis revision, `segment_id`, observations, and suggested correction. Keep interpretations separate in `interpretation_comment`. |
| `creative_review.csv` | One evaluation criterion per row. Suggested criteria: `brief_fit`, `evidence_traceability`, `production_clarity`, and `actionability`. Concrete problems and reasons matter more than an isolated score. |
| `technical_spike.csv` | One actual attempt per row. Distinguish access to audiovisual content from metadata-only access. Record failures, latency, cost, fallback, and the actual execution environment. |
| `api_cost_log.csv` | One attributable call or billing entry per row. Keep estimated and billed costs separate and retain their source. Do not add different currencies without an explicit conversion. |

## Recording conventions

- Use UTC timestamps, for example `2026-10-08T08:00:00Z`. Reference-video timestamps are seconds from the original video's beginning. `file_size_mb_decimal` uses 1 MB = 1,000,000 bytes.
- Leave unknown numeric values blank. Enter zero only when it was observed. Use `true`/`false` for booleans and `|` to separate multiple roles or IDs.
- `suggested_roles_pipe_separated` contains the applicable subset of `hook`, `product_demo`, `proof`, `cta`, and `other`. Do not combine `other` with another role.
- `rating_1_to_5_or_blank` is an informal team rating: 1 = unusable; 2 = major revision needed; 3 = moderate revision needed; 4 = usable with minor changes; 5 = usable for the present task. Leave it blank if no evaluation occurred. This is not a validated scale or a market-performance score.
- Use `hypothesis_not_proven` for claims still requiring validation. Co-occurrence of a creative feature and high views/engagement does not establish causality.
- Record timestamp errors even though the midterm UI does not support timestamp editing. Verified timing and localization errors inform technical corrections.
- Never include API keys, passwords, or unnecessary personal information. Retain a request ID only if it is safe to share.
