# Reference frame timing — v0.3

Decision date: 15 October 2026. Owner request: use frames for reference-video analysis across different frame rates, tolerate minor frame error, leave general storyboard suggestions in seconds, and defer new variables/categories.

## Contract and media clock

Reference events and sections use zero-based integer `start_frame` and exclusive `end_frame`. A single-frame event is valid. IDs, evidence links, correction restrictions and review/approval semantics are retained. The contract version is `0.3.0`; all v0.1/v0.2 schemas and examples remain historical snapshots.

Media intake uses ffprobe decoded presentation timestamps, stores rational FPS, decoded frame count, rate mode and a boundary map, and retains the first timestamp as `media_start_seconds`. Boundaries are relative to source frame zero, including a final exclusive boundary. Browser seeking adds the source origin; playback frame lookup subtracts it. This avoids average-FPS drift on variable-rate clips and handles MP4s whose playback begins after zero. Frames are indexed without generating image files.

The UI displays `HH:MM:SS:FF` at rounded nominal FPS and absolute frame indices. There are previous/next frame buttons and section/event seeks. Non-drop-frame timecode is approximate for fractional or variable FPS; actual presentation boundaries control seeking. Frame accuracy is sufficient for review and is not a promise of Premiere-compatible editing/export behavior. Supported input remains H.264 MP4 with optional AAC audio and the existing size/duration/dimension limits.

Recognition adapters normalize second-based provider results using the shared nearest-boundary conversion, preserving at least one frame and revalidating all relationships. This does not improve a provider's extraction accuracy. Real recognition remains unconfigured; the matching sample remains explicitly synthetic.

## Separate storyboard timing

Storyboard rows retain `start_seconds`/`end_seconds`, and the brand brief retains `target_duration_seconds`. Their duration comes from the new-video brief. Reference FPS never imposes an output FPS or changes these planned seconds. Categories and business variables are unchanged.

## Existing records

At startup/load, SQLite archives the exact original v0.2 payload and SHA-256 atomically with its replacement. All revisions of a video use the same verified source map. Artifact IDs, text edits, correction logs and output seconds remain intact; optimistic task version increments once. Matching available media preserves valid review/approval and current outputs. Reopening does not repeat migration.

When source media is missing, changed, unreadable or old subframe relationships cannot be represented without losing links, preserve legacy seconds with explicit null frame timing. Mark only affected creative content outdated and clear its dependent approval; keep historical review and user content. New confirmation/generation requires uploading and analyzing the source with known timing. No default frame rate is guessed.

## Verification and consequences

See `docs/handoff/frame-timing-review.md` for executed checks. Tests cover integer/fractional rates, actual VFR, one-frame/subsecond intervals, shifted media origins, overlapping evidence, unchanged storyboard seconds, exact archived payloads, migration rollback and the connected browser workflow.

The per-frame boundary map increases task JSON size and intake does additional frame probing. Under the current 180-second clip limit this is a practical tradeoff for predictable VFR seeking. Future long-form workflows may move the map into a separately cached asset; that optimization is outside this change.
