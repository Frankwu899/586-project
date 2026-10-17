# Contract impact and ownership

The coordinator and backend owner select v0.6 for explicit shared changes; historical v0.1–v0.5 artifacts remain preserved. Regenerate canonical schemas/types, do not hand-edit frontend-only contract assumptions.

Planned fields: task `generation_language` (English/Chinese/null), video `deleted_at` tombstone, direction `auxiliary_status` (current/needs_review). Task collections retain multiple assets; one current reference is a workflow limit. Migration archives exact old JSON/hash and preserves histories/citations/approval/currentness; absent explicit language is not guessed for new generation.

Independent editor endpoints under `/api/tasks/{task_id}/editors/{scope}`: GET read/seed, POST save; `/discard` restores formal content. Scope is analysis, direction-{id}, or production. Draft contains task/scope/draft_version/base_refs/content/has_pending_changes/conflict/updated_at. Save supplies expected_draft_version, base_refs and content. Draft versions do not increment task.version.

Analysis content holds event/segment arrays; direction holds four editable text fields; production holds brief_fields and immutable-shape storyboard rows. Canonical server validation rejects forbidden identity/timing/relationship changes. Formal existing mutations can carry expected_editor_version, commit artifact and checkpoint atomically. Direct API callers cannot bypass pending edits. No-op application must not invent versions.

`POST /language` changes the explicit language with expected task version. `POST /videos/{video_id}/delete` removes only that task-owned original/proxy and leaves metadata/history. Foreign-task IDs and unsafe paths are rejected. Reference-dependent current work is invalidated; unrelated newer work remains.

Creative providers expose request-scoped language adaptation without mutating shared settings. Real and sample paths remain isolated. Provider errors never become sample successes. Original shot rows may have empty evidence lists. Stale manual-direction auxiliaries must not be unconditionally copied into production notes.

Final delivered shapes and migration details are recorded in the implementation report; deviations must preserve user-confirmed behavior and be explained.

Implemented addition: nullable `ProductionOutput.bundle_id` ties newly generated/edited brief and storyboard pairs. Legacy records remain null; historical exports never infer pairing from matching revision numbers.
