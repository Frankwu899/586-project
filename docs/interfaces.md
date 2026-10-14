# Interface Contract — Proposed v0.1

This is a contract proposal for team review, not an implemented backend API. `contracts/analysis.schema.json` governs fields, types, and structural constraints. This document governs business semantics and cross-field/workflow rules. Update the schema, documentation, examples, and affected producers/consumers together; do not independently change names or units.

## 1. AnalysisResult

| Field | Convention |
|---|---|
| `schema_version` | Fixed at `0.1.0`; evaluate compatibility when structure changes |
| `project_id`, `video_id`, `analysis_id` | Stable string IDs, not file paths; editing an analysis does not change these IDs |
| `revision` | Positive integer; the first completed model result is revision 1, and later content changes create new revisions |
| `created_at`, `updated_at` | RFC 3339 timestamps with timezone; store as UTC using `Z` |
| `status` | `pending`, `running`, `succeeded`, or `failed` |
| `video` | `input_method` is `file` or `url`; file input requires `original_file_name`, URL input requires `source_url`; successful analysis requires positive `duration_seconds` |
| `public_metrics` | `null` when no snapshot is available; otherwise the same video's snapshot with `source_url`, `captured_at`, `views`, `likes`, and `comments`; unknown metrics are `null`, not zero |
| `model_run` | `provider`, `model`, and `prompt_version`; required for success to support reproduction/debugging; never include API keys |
| `segments` | Content-segment array; successful analysis may return `[]` with an explanation |
| `empty_result_reason` | A nonempty string only when status is `succeeded` and `segments` is empty; otherwise `null` |
| `review` | `editor_type` is `system`, `model`, or `user`; `original_revision` identifies the original model result; `user_confirmed` and `confirmed_at` record user review |
| `error` | `{code, message, retryable}` only for `failed`; otherwise `null` |

`pending`, `running`, and `failed` results have no segments. Partial analysis results are outside this proposal. No usable segments is not necessarily a failure: `succeeded` with `[]` and an `empty_result_reason` means the operation finished without usable segments. Do not disguise a failure as a successful empty result.

A metric snapshot must describe the same source video. Public views, likes, and comments do not establish causality, retention, click-through rate, or conversion performance. Zero represents an observed zero.

## 2. Segment

Each segment contains stable `segment_id`, `start_seconds`, `end_seconds`, `roles`, `spoken_text`, `on_screen_text`, `visual_description`, `interpretation`, and `edited_fields`.

- **Time:** decimal seconds from the original reference video's beginning, with interval `[start_seconds, end_seconds)`. Enforce `0 <= start_seconds < end_seconds <= duration_seconds`. Sort by start time. Primary content segments do not overlap; gaps are allowed. Use multiple roles for a segment with several purposes instead of duplicating it.
- **Roles:** any applicable selection from `hook`, `product_demo`, `proof`, `cta`, and `other`. Roles may recur across segments; no Hook or fixed sequence is required. Use `other` alone. `proof` identifies a rhetorical proof claim in the video, not independently verified efficacy.
- **Text:** `spoken_text` is heard speech; `on_screen_text` is visible writing. `null` means unavailable or not analyzed; an empty string means checked and absent. Do not interchange these meanings.
- **Observation and interpretation:** put observable content in `visual_description`. Keep reasoning in `interpretation`, or use `null`. Do not present an unobserved effect as a fact.
- **Midterm edits:** users may change `roles`, `spoken_text`, `on_screen_text`, and `visual_description`. `edited_fields` records fields changed relative to the original model revision. Times, IDs, and `interpretation` are not direct midterm UI editing fields.

## 3. Revisions and downstream outputs

Preserve the first completed model result as revision 1. Save user content changes as new immutable revisions while retaining segment IDs. Set `review.original_revision` to 1. A content change clears `user_confirmed` until explicit review; confirmation records `confirmed_at`. Timestamp editing and segment merging/splitting require later rules and are not enabled by default for the midterm.

A model rerun also preserves old results. Give it a new `analysis_id`; do not assume newly detected segments inherit old IDs. Never overwrite user corrections silently. In the examples, `editor_type=model` simulates origin only; `model_run` explicitly identifies synthetic fixtures.

The analysis schema does not yet encode the following workflow objects. Their proposed minimum fields are documented here:

| Object | Proposed minimum fields |
|---|---|
| BrandBrief input | `brief_id`, `revision`, `brand_or_product`, `selling_points`, `target_audience`, `platform`, `communication_goal` |
| CreativeDirection output | `direction_id`, `revision`, `brief_id`/`brief_revision`, `analysis_id`/`analysis_revision`, `core_message`, `hook`, `narrative`, `cta`, `evidence` containing `segment_id` and `reason`, `hypotheses`, `approval_status` |
| TextStoryboard output | `storyboard_id`, `revision`, `direction_id`/`direction_revision`, `rows` containing new-video start/end seconds, `visual`, `dialogue`, `on_screen_text`, `sound`, and `cta` |

The user reviews and explicitly approves the direction with `approval_status=approved` before storyboard generation. Storyboard times belong to the **new video**; evidence timestamps belong to the **reference video**. Evidence references must exist in the recorded analysis revision.

A content-revision change to the brief or analysis makes dependent directions and storyboards stale. Preserve the old content, request renewed review, and let the user decide whether to regenerate. A confirmation-state change alone must not rewrite content. If a correction invalidates an interpretation, flag it for review or clear it before reuse; do not keep treating it as confirmed fact.

## 4. Validation responsibilities

The adapter normalizes actual provider output into the shared structure, then performs schema validation and semantic validation. Native strict JSON support must not be assumed.

Semantic checks include:

- Unique IDs within the relevant collection and valid references.
- Time bounds, ordering, and nonoverlap.
- Exclusive use of `other` when selected.
- Matching video and public-metric sources.
- Valid `revision`/`original_revision` lineage.
- `created_at <= updated_at`, and confirmation time consistent with review state.
- User-edit permissions and correctly recorded `edited_fields`.
- Existing evidence references and current dependency versions.

History, dependency, and permission checks may require project records; a single JSON object cannot prove all of them.

A contract-change PR must update the schema, explanation, examples, producers, consumers, and relevant validation together. API routes, a complete error-code catalog, supported formats, and operational limits remain implementation decisions. This package is not evidence of a live API.
