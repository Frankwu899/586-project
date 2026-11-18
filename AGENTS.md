# Video Anatomy — Agent Instructions

## Current 1.8 baseline

For the 1.8.5 candidate, read `docs/releases/1.8.5.md` and
`docs/handoff/project-workspace-1.8.5.md`. Source evidence feeds durable,
brief-independent single-video analysis; synthesis consumes compact saved cores.
Keep exact input keys, citations, coverage limits and historical provenance.
PR22 and PR23 are unmerged dependencies, not an authorization to merge or deploy.
Use the candidate handoff's actual verification and remaining evidence limits.

For the 1.8.1 shared testing candidate, also read `docs/releases/1.8.1.md` and
`docs/handoff/project-workspace-1.8.1.md`. Exploratory ideas may use references
without a confirmed profile; tailored final production retains confirmation and
approval gates. Visual-only continuation is explicit and recorded. Show one
current successful analysis per scope, preserving history and failed-replacement
recovery. PR #17 is an unmerged dependency, not permission to merge either PR.

The owner's November 12, 2026 baseline and explicit implementation request
supersede the older single-reference, form-intake, and three-workspace scope
below. Read `docs/project-workspace-1.8.md` and
`docs/handoff/project-workspace-1.8.md` first. The default app now uses project
folders, conversation-derived briefs, optional series/standalone content,
multiple references, and four-document production packs. Legacy task APIs and
the `?legacy=1` workspace remain available for continuity.

Discovery is **Reserved — awaiting Frank’s specification.** Keep its destination
empty; only the shared local-file import boundary exists. Do not add discovery
search, download, ranking, or model behavior. Editing, rendering, AI video
generation, and social publishing remain outside 1.8. Preserve local keys and
the `gpt-6.1-sol` application baseline, with separate timestamped transcription.
No live-quality or Mac-delivery claim follows from offline checks.

New contracts live in `backend/app/project_workspace/models.py`; regenerate
`contracts/v1.8.project.schema.json` and `frontend/src/project/contracts.ts`
together. Preserve historical task contracts. Coordinate edits to these shared
models and `project_workspace/api.py` before parallel work. Draft scopes and the
brief draft have independent concurrency versions; do not rebase stale draft
writes merely because background jobs changed the aggregate version.

Every coding agent must read this file and the relevant interface documents before starting a task. The repository now extends the preserved v0.1 documentation baseline with the v0.5 frame-based application and replaceable providers. Read the current implementation and latest handoff before making readiness claims.

## Read first

The owner's 2026-10-18 request authorizes implementing and testing the workspace
redesign and confirmed Structure S1-S11, with a total USD 3 live API/training
budget. This supersedes the earlier discussion-only status below. Centralize
paid calls through the shared persisted budget; never allocate USD 3 per agent
or reset the ledger between modules. No main merge or deployment is authorized.

The owner clarified on 2026-10-19 that USD 3 applies only to Cloud experiments,
not the local client. Local launcher requests use non-blocking usage reporting:
do not reapply the Cloud cap, old reservation holds or accounting-pause gate to
client generation. Preserve the historical ledger without resetting it. Cloud
experiment transports remain capped. Whisper is approved for timestamped speech;
other local inference stays on the configured GPT-6 models.

For the current UI/UX redesign discussion, start with
`docs/handoff/workspace-redesign-review.md` and its linked design review. The owner
requested product-flow review before implementation and selected UI UX Pro Max
as the new design source, with a Glassmorphism preference. Proposed dependency
changes are not confirmed merely because they appear in the prototype. All future
installer/launcher text, package documentation and handoffs must be English.

When the owner invokes grill-me, read `.agents/skills/grill-me/SKILL.md` and its
local `grilling` dependency. The owner requires native interactive question boxes
for all interview questions, never plain-text question lists. Preserve previously
confirmed decisions. The current Structure discussion is product design; its
dedicated product agent is requested but not yet implemented.

1. `docs/project-brief.md`
2. `docs/architecture.md`
3. `docs/interfaces.md` and `contracts/v0.5.task-state.schema.json` when touching shared data (v0.1/v0.2/v0.3/v0.4 artifacts are historical snapshots)
4. The current task and latest relevant handoff in `docs/handoff/`; start with `docs/handoff/m2-brief-experience.md` for M2 and `docs/handoff/bilingual-provider-contracts.md` for the provider foundation and actual verification
5. `docs/branch-workflow.md` and `docs/module-ownership.md` for task naming, actual file boundaries and shared-file coordination
6. `README_SETUP.md` for current setup and Cloud-to-local use. `docs/cloud-workflow.md` preserves the earlier documentation-only starter workflow; its old setup assumptions and prompts are historical.

Use English for repository documentation and new handoffs unless the owner requests otherwise. Keep schema keys, enums, IDs, and API identifiers stable when editing prose.

The conversation supplies product intent. Repository files supply the current shared contract. Surface disagreements; do not silently invent a new convention.

## Scope and implementation

- The overnight implementation milestone is authorized by `overnight-skeleton-spec.md`. Its sample workflow uses React/Vite/TypeScript and FastAPI/Python; see `docs/decisions/skeleton-v0.2.md` and the latest handoff for actual validation. Sample behavior does not establish real recognition, public deployment, or link ingestion.
- Keep the recorded stack and reproducible dependencies unless the owner approves a scope change. Distinguish Cloud checks from unexecuted local-machine checks.
- Implement the smallest end-to-end workflow in the brief. Keep multi-video comparison, model training, generated storyboard images, and public hosting outside the midterm must-have scope unless the owner changes it.
- Use zero-based integer reference frames with exclusive ends and stable IDs. Intake supplies actual frame boundaries and rational FPS; do not guess missing frame rates. Storyboard suggestions retain seconds independently of reference FPS. Follow the canonical analysis schema and semantic rules. Preserve observations separately from interpretations.
- Keep provider-specific results behind an adapter. Do not assume every model supports strict JSON output, direct video URLs, identical timestamps, or the same transport.
- Retain original analysis revisions. User-approved creative direction is required before storyboard generation. Do not overwrite edited work with a regenerated result.
- Do not fabricate metrics, completed tests, accuracy, source rights, or successful API access. Label synthetic data.

## Git and review

- Before editing, inspect the repository, current branch, working-tree changes, and relevant recent commits. Preserve unrelated changes.
- Keep `main` as the only permanent shared branch. Use temporary `<type>/<module>/<specific-task>` branches as documented in `docs/branch-workflow.md`; scopes name work, not separate repositories or directory layouts. Preserve existing historical branches during integration setup.
- The team workflow authorizes preparing a commit, push, and PR for the assigned task; describe changes and actual validation. Never infer permission to merge into `main` from permission to prepare a PR. An explicit task authorization to merge applies after required checks and repository review rules are satisfied; do not bypass protections.
- Coordinate changes to `backend/app/models.py`, `backend/app/adapters.py`, `backend/app/service.py`, and `backend/app/api.py` before parallel work. Record the shared edits, responsible editor and merge order; regenerate contracts/types together with consumers. Keep provider-specific implementations separate where practical.
- Use meaningful new commit messages such as `feat(video-analysis): normalize provider output`; do not rename historical commits. Start subsequent tasks from updated `main`, after inspecting and preserving local changes.
- Do not force-push, delete branches, rewrite shared history, discard changes, or clean untracked files as a routine sync step.
- If a remote integration is unavailable, provide exact commands or instructions and report what remains undone. Do not claim that a local commit reached GitHub.
- Run only relevant checks for the current change. A provider, browser, or end-to-end check that was not executed must be marked “not run.”

## Execution environment

- The owner prefers Codex Cloud for ongoing and unattended coding tasks. Keep local application testing and the team demonstration reproducible.
- At task start, verify the actual execution environment, repository, branch, and commit. Do not assume Mac paths or tools exist in Cloud.
- A new conversation must read repository context and the latest relevant handoff. Do not rely on access to earlier private chats or another task's uncommitted work.
- Inspect dependencies where commands will run. Install only what the assigned task needs after the stack/version decision; never report Cloud checks as Mac checks.
- Cloud coding does not imply application deployment. Missing Mac runtimes do not block Cloud work, but the chosen runtimes are required wherever the application is run.

## Configuration and handoff

- Keep API keys out of frontend code, Git history, logs, screenshots, and handoff text. Use a backend environment variable and a placeholder-only configuration example once implementation starts.
- Do not commit real video files or local media/output directories by default. Sample manifests may record references and rights notes. Decide actual storage and ignore rules during skeleton setup.
- A Git Push transfers committed repository content; it does not transfer the local Python environment, API keys, downloaded videos, or private chat history.
- Finish each task with files changed, verification performed, current branch/commit, remaining blockers, and next steps, using `docs/handoff/TEMPLATE.md`.
