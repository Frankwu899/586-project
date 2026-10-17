# Product scope

The user creates a durable creative task, supplies task-local brand facts and one current reference in either order, reviews sampled evidence, compares two distinct creative directions, approves an exact revision, and receives a useful production brief and timed text storyboard. The product helps decide what to make; recognition alone is not the value proposition.

## Functional tree

- M1: list/create/reopen tasks; remember the last work area; show real readiness and contextual history.
- M2: retain independent draft/autosave, explicit Apply, confirmed claims, optional source notes and explicit AI proposal adoption.
- M3/M4: upload/probe/play; source asset collection with one current reference; explicit analyze/retry; retain original timing; delete media with historical tombstones. No actual network/library search.
- M5: sampled visual summaries plus all timestamped speech/text; expandable details and permitted corrections; recoverable independent draft; explicit Apply and separate review confirmation.
- M6: explicitly select generation language; summary comparison, complete direction, evidence seeks, manual text edits, targeted feedback, selection then approval. A follows reference structure, B reorganizes it. Changed manual text makes older auxiliary explanations stale.
- M7: concrete production brief and flexible planned shot rows; visuals/dialogue/subtitles/sound/CTA; honor claims, duration and practical constraints. Only text editing, with recoverable drafts and explicit saves. Original suggested shots can have no reference citation.
- M8: saved-document PDF via native Print / Save as PDF, CSV storyboard, optional Markdown; save-before-export; historical labeling; safe CSV/markup handling.
- M9: team annotations and creative-usefulness review, no runtime retrieval.
- M10: canonical models/types, archived migrations, independent draft concurrency, safe admission/currentness and provider boundaries.

## State rules

Autosave preserves incomplete edits, does not approve or create a formal artifact revision, and does not invalidate admitted work. Formal application/save creates a revision when content changes. Pending edits must be resolved before dependent generation/approval/regeneration. Save failure retains text and blocks a dependent action. Stale bases are explicit conflicts; no silent overwrite.

Changing language invalidates downstream creative eligibility but retains analysis review. Deleting source media retains historical text, provenance and outputs, labels missing playback, and invalidates only dependent current work. Multi-video assets and future source selection must remain possible without implementing multi-reference generation now.

English/Chinese/mixed evidence remains original. A language choice governs new creative prose, not source translation or silent replacement of fixed approved claims. Fixed-copy translation requires user review outside automatic generation. Current outputs do not imply factual or performance verification.
