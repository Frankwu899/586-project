# Skeleton integration and module branches

**Pre-publication handoff — 15 October 2026 (America/Los_Angeles).** This records the integration branch before publication. PR merge and next-work branch creation are pending at this snapshot; the final task report will record verified remote results and the merged main SHA. Historical handoffs describe earlier runs and environments, not fresh results from this task.

## Source and integration

- Repository: `Frankwu899/586-project`; managed Codex Cloud Linux.
- Original checkout: `/workspace/586-project`, branch `work`, clean at `e98a33caa942e57ce9198d9ef34dc2f911cd263d`; preserved untouched.
- Fetched main: `e98a33caa942e57ce9198d9ef34dc2f911cd263d`.
- Submitted branch: `feat/video-anatomy-frame-timing`, still at `cd990cbdb0681a530daefc9c0869eb64065a55c3` when inspected.
- Source ancestry: `74b820f66c9af48782d324a3433fd0824c7d14a9` (English starter) → `0b7a73bf324b0a994f698cf758a4537e212bb120` (overnight specification) → `cd990cbdb0681a530daefc9c0869eb64065a55c3` (sample implementation and v0.3 timing). Main already contained the starter through PR #1, but not the latter two commits.
- Isolated worktree: `/workspace/586-integration`, branch `chore/integration/overnight-skeleton`, created from current `origin/main`.
- History-preserving integration merge: `ed604b3df22cec769c3799d07f08e68f6d86cde3`, with parents `e98a33c` and `cd990cb`. No conflicts; no cherry-pick, squash, rebase, forced push, branch deletion/rename, automatic stash, or runtime-data cleanup.
- Failure-handling fix commit: `bdd4e96928b9522833667e6f3e5d1ec9a091bd35`. This handoff and workflow guidance follow it in a separate documentation commit; their own commit SHA is intentionally not embedded in their contents.
- Existing local `work` and remote source branch remain intact. Only the intended submitted implementation was integrated.

Read for this task: `AGENTS.md`, `CLAUDE.md`, `README_SETUP.md`, project brief, architecture, interfaces, both skeleton/frame timing decisions and handoffs, historical Cloud workflow, root overnight specification, and applicable schemas/tests. The user's integration request explicitly authorizes commits, push, PR and normal merge after verification, superseding the earlier overnight publication hold. v0.3 timing decisions supersede the older seconds-based reference requirement in that specification.

## Changes

The submitted application is reused. Reference events and sections keep zero-based `start_frame` and exclusive `end_frame`, measured frame maps and rational rates, with no invented FPS. New storyboard planning remains in seconds. Original analysis, corrections, archived migrations, provenance, feedback, revisions, and human approval gates remain preserved.

Integration review repaired two failure-handling gaps: sample setup now verifies each new processing job and its expected result before reporting a completed walkthrough; failed, stale, invalid, or interrupted refinement resolves its saved feedback as `not_interpreted` with an explanation instead of leaving it pending indefinitely. The instruction and prior drafts remain saved, and the job remains failed. Thirteen focused regression cases accompany the fixes in `tests/test_workflow.py` and `tests/test_load_sample.py`; `docs/interfaces.md` documents the behavior. No provider implementation, credentials, paid API calls, dependency upgrades, or directory reorganization are included.

New workflow documents are `docs/branch-workflow.md`, `docs/module-ownership.md`, and `.github/pull_request_template.md`, with current links/instructions in `AGENTS.md` and `README_SETUP.md`. `main` is the only permanent shared branch. Temporary branches follow `<type>/<module>/<specific-task>`; meaningful commits use the relevant module, for example `feat(video-analysis): normalize provider output`.

No updated blueprint HTML was supplied or found in the submitted repository tree or uploaded attachments. `docs/blueprint.html` was therefore **not added**. The root specification and current architecture/interfaces were inspected; no replacement HTML or expandable content was invented.

## Fresh verification

Setup: `python3.12 -m venv .venv`, `.venv/bin/python -m pip install -r requirements.lock`, and `npm --cache /workspace/.npm-integration-cache --prefix frontend ci --loglevel=error`.

Actual Cloud runtimes: Python 3.12.14, Node 24.19.0, npm 11.9.0, FFmpeg/ffprobe 7.1.5, system Chromium 154.0.8037.57, Playwright 1.56.1. Python and npm lockfiles are unchanged.

| Check | Fresh result |
|---|---|
| Initial `bash scripts/verify.sh` on the submitted runtime | Exit 0: 158 backend tests, 5 frontend timing tests, 2 Chromium browser tests; dependency consistency, schemas/types, lint, typecheck, build passed. |
| Final `bash scripts/verify.sh` after failure-handling fixes | **Exit 0**: dependency consistency and schema drift passed; Ruff passed; **171 backend tests passed** in 35.67 seconds; generated frontend types passed; **5 timing unit tests passed**; TypeScript, ESLint and Vite production build passed; **2 Chromium browser tests passed** in 11.0 seconds. No required check failed or was skipped. Log: `.local-data/integration-verification-final.log`. |
| Focused failure regressions | `.venv/bin/python -m pytest -q tests/test_workflow.py tests/test_load_sample.py`: 29 passed in 29.80 seconds; Ruff passed. |
| Direct processing-job inspection | Complete sample: `analyze`, `directions`, `refine`, `production` all `succeeded`; both original/corrected analysis revisions `succeeded`. Re-uploading matching sample bytes as an ordinary upload returned HTTP 200 with job and analysis `failed`, error `real_analysis_not_configured`, zero events. Audit assertions passed; `.local-data/processing-job-audit.json` records results. |
| Historical schemas/examples/templates | No diff from submitted `cd990cb` for `contracts/`, `examples/`, or `data/templates/`. |
| Whitespace, documentation links and diff review | `git diff --check` passed; all relative links in updated integration guidance resolve. Runtime fixes reviewed against the submitted implementation; no contract/schema/fixture changes. |
| Real provider calls/accuracy, unrestricted prompting, platform downloads, public deployment | Not run; capabilities remain unconfigured or outside scope. |
| Frank's Mac / Andrea's computer | Not run; neither machine was accessed or configured. |

The initial Git fetch failed in the default network sandbox; the supported network permission allowed the ordinary fetch. The first npm install failed because `/home/agent/.npm/_cacache` was not writable; retrying with a writable workspace cache succeeded without changing dependencies. Nonblocking output includes a pip cache warning, the pinned Starlette/httpx deprecation warning, npm version notices and terminal color warnings. These setup failures are not counted as passed runs.

Browser verification exercises matching synthetic-media playback and frame seeking/stepping, corrections, review confirmation, direction selection distinct from approval, supported and unsupported feedback, production edits/exports, refresh/reopen, upstream invalidation, ordinary-upload unconfigured recognition, and a shifted-origin 24 fps clip. Backend checks cover contracts, migrations/archives/rollback, measured integer/fractional/VFR media timing, stale writes and approval boundaries. HTTP 200 alone is never treated as a successful generation job.

Logs and generated data live under ignored `.local-data/` or temporary test directories. No real user database or media was present in the original checkout; none was discarded or replaced. Source control does not transfer these runtime artifacts.

## Module-to-file map

These scopes name work, not permanent branches or new directories. Every branch contains the entire repository. Detailed operations and review guidance are in [module-ownership.md](../module-ownership.md).

| Scope / module | Actual source and supporting files |
|---|---|
| `contracts` — M10 | `backend/app/models.py`, `timing.py`, `migration.py`, `frame_migration.py`, `storage.py`; `contracts/`; `scripts/export_contracts.py`; `frontend/src/generated/contracts.ts`, `timing.ts`; contract/migration/timing tests and fixtures. |
| `workspace` — M1/M2 | `frontend/src/App.tsx`, `BriefEditor.tsx`; task/brief operations in `backend/app/service.py` and `api.py`; `storage.py`. |
| `video-input` — M3 | `backend/app/media.py`; upload/playback routes in `api.py`, operations in `service.py`; input/player controls in `frontend/src/App.tsx`; `tests/test_media.py`. |
| `video-analysis` — M4 | `RecognitionRequest`, `RecognitionAdapter`, sample/unconfigured recognition in `backend/app/adapters.py`; `sample.py`; recognition operations in `service.py`/`api.py`; `tests/test_adapters.py`. |
| `analysis-review` — M5 | `frontend/src/AnalysisReview.tsx`; correction/confirmation operations in `service.py`/`api.py`; frame helpers and workflow tests. |
| `creative-direction` — M6 | `frontend/src/Directions.tsx`; `CreativeAdapter` direction/refinement methods in `adapters.py`; selection/edit/refinement/approval operations in `service.py`/`api.py`. |
| `production-output` — M7/M8 | `frontend/src/Production.tsx`; production adapter in `adapters.py`; generation/edit/Markdown/CSV export in `service.py`/`api.py`; API/workflow/browser tests. |
| `reference-library` — M9 | `docs/reference-review-guide.md`, `data/templates/`, fictional review/video manifests in `examples/`; no retrieval library or training pipeline implemented. |
| `integration`, `project` | Coordinated gates (`scripts/verify.sh`, browser workflow) and cross-application documentation/handoffs. |

## Shared-file coordination

`backend/app/models.py`, `backend/app/adapters.py`, `backend/app/service.py`, and `backend/app/api.py` span modules. Before parallel edits, Frank and Andrea agree on signatures, fields, units, errors, revision/approval behavior and which task owns each shared change. Land a coordinated contract/interface change first where both provider tasks depend on it; update models, generated schemas/types, documentation, fixtures, validators and consumers together. The other task then incorporates updated main through an ordinary merge, preserving its work.

Keep provider transport/parsing in separate provider-specific files where practical, behind the existing protocols. Adapters do not own storage or approval, must preserve measured timing and explicit provenance, and must not turn a failed/unconfigured operation into sample success. Use `seconds_to_frame_range` for measured conversion when a provider returns seconds and revalidate relationships. Do not hand-edit generated types or add guessed `CODEOWNERS` usernames. Andrea's GitHub username is unknown; ownership here is a human task assignment.

## Publication and intended next work

At this pre-publication snapshot, the integration PR is pending. Remote inspection reports main unprotected, no required status contexts, merge commits allowed and automatic branch deletion disabled. Detailed protection inspection returned connector permission 403; rulesets returned a private-plan feature 403. Use a normal PR merge with the expected reviewed head, recheck current main and PR checks/reviews immediately beforehand, and respect any gate GitHub reports. No administrator bypass or protection changes are authorized or used.

After normal PR merge, fetch and verify `origin/main` contains the submitted source, reviewed integration head and this committed handoff. Only then create and publish both task branches from that exact accepted main SHA, without empty commits. Existing names must be inspected and preserved; never reset an existing branch to claim its name.

| Intended branch | Owner and next bounded task | Creation/base status at this snapshot |
|---|---|---|
| `feat/video-analysis/first-real-provider` | Andrea — implement real recognition behind `RecognitionAdapter.analyze(RecognitionRequest) -> AnalysisResult`. | Pending verified main integration; base must be the accepted main SHA. |
| `feat/creative-direction/first-real-provider` | Frank — connect real direction/refinement/production generation behind `CreativeAdapter`. | Pending verified main integration; same accepted main SHA. |

This task prepares those branches only. The final task report records creation outcomes and exact base commit; it must not call them ready if integration is blocked. Existing historical branches remain intact.

Both developers first read `AGENTS.md`, this handoff, `docs/branch-workflow.md`, `docs/module-ownership.md`, `docs/interfaces.md`, and `docs/decisions/frame-timing-v0.3.md`, then run the sample locally. Before provider work, agree on the provider/model, budget, permitted media and backend credential configuration; those choices are still open. Andrea begins with normalized visual actions, on-screen text and speech with honest coverage/errors. Frank preserves saved feedback, exact evidence revisions, draft status and explicit human approval for generated directions/production. Coordinate shared-file changes before editing; do not begin implementation or incur charges as part of this setup.

## Mac synchronization and remaining limits

Cloud changes do not update the Mac or install its dependencies. In the existing Mac repository, first run `git status`. If tracked or untracked work exists, preserve it on its own task branch/commit or make a backup outside the repository and inspect conflicts; do not discard it, auto-stash it, or overwrite local runtime data. Stop before switching if unsure. Once the working tree is safely clean:

```bash
git fetch origin
git switch main
git pull --ff-only origin main
```

If local main has diverged, the fast-forward-only pull stops safely: inspect and integrate those commits separately. Then use the published assigned task branch. If no local branch by that name exists, for Andrea:

```bash
git switch --track origin/feat/video-analysis/first-real-provider
```

For Frank, use `git switch --track origin/feat/creative-direction/first-real-provider`. If the local task branch already exists, inspect it and switch to it without recreating or resetting it. Install the runtimes/dependencies and follow startup/sample commands in `README_SETUP.md` on each machine. Keep a separate backup of the full data directory, including media, before transferring runtime records.

The complete workflow remains sample-backed. Real recognition and creative providers are unconfigured; presenter-free sample refinement is deliberately limited and other feedback remains saved as not interpreted. Input is tested H.264 MP4 with optional AAC, under configured limits. Frame seeking is for review; nominal fractional/VFR timecode is approximate. Single-worker local storage, no platform downloading, no public hosting, no storyboard images, and no measured real-model accuracy remain explicit limitations.
