# Project lifecycle menus

This additive change gives the workspace a reversible project Trash and rename
actions. The root project list omits trashed projects. Moving a project to Trash
does not delete videos, drafts, analysis history, Structure work, provider caches,
or the shared budget ledger. Restoring returns the same project identity and saved
work. Closing a project is a frontend navigation action, with drafts saved first.

## Interface

All writes use the current task's `expected_version` and return `TaskState`.

| Route | Request / result |
| --- | --- |
| `POST /api/tasks/{task_id}/rename` | `{expected_version, title}`; nonempty title |
| `POST /api/tasks/{task_id}/trash` | `{expected_version}`; reversible removal from active list |
| `POST /api/tasks/{task_id}/restore` | `{expected_version}`; recovery from Trash |
| `GET /api/trash/tasks` | `TaskState[]`, newest trashed first |

`task_lifecycle` is an auxiliary SQLite table; the canonical task contract and
artifact identities do not change. Trash and restore increment task versions and
update task timestamps. Exact retries after a lost response are idempotent, while
stale actions after an intervening change return a version conflict. Renaming to
the current title is a no-op. Normal task reads/writes, including independent
editor drafts, return `410 task_trashed` for a project in Trash.

Trash returns `409 task_busy` while the project has an unfinished processing job,
queued/running background operation, active Structure analysis/research/feedback,
or synchronous HTTP write. The project middleware reserves in-flight writes and
Trash separately, closing the race before job records exist. This reservation is
per project, so other projects remain usable. The supported local runtime uses a
single backend worker; the in-memory HTTP reservation is not a multi-worker lock.

## Verification

`tests/test_project_lifecycle.py` plus the affected M2 storage, workspace editor,
background operation and Structure API suites: **72 passed**. Coverage includes
restoring media/history/drafts, preserving the budget and cache files, restart,
optimistic conflicts, lost-response retries, stale-tab draft writes, busy work and
both directions of the Trash/synchronous-write race. Ruff passed for the changed
Python files. Tests use synthetic offline data; no paid API calls were made.

Files: `backend/app/storage.py`, `backend/app/project_api.py`,
`tests/test_project_lifecycle.py`. The integrator mounts `install_project_api`
inside `create_app` and owns the project menu UI. Branch:
`feat/workspace/structure-agent-redesign`; starting commit `70c08b0`. No commit,
merge or deployment was performed by this subtask.
