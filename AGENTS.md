# Video Anatomy — Agent Instructions

Every coding agent must read this file and the relevant interface documents before starting a task. The repository now extends the preserved v0.1 documentation baseline with the v0.3 frame-based sample application. Read the current implementation and latest handoff before making readiness claims.

## Read first

1. `docs/project-brief.md`
2. `docs/architecture.md`
3. `docs/interfaces.md` and `contracts/v0.3.task-state.schema.json` when touching shared data (v0.1/v0.2 artifacts are historical snapshots)
4. The current task and latest relevant handoff in `docs/handoff/`
5. `docs/cloud-workflow.md` when setting up or handing work between local and Cloud environments

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
- Work on a task branch. The team workflow authorizes preparing a Commit, Push, and PR for the assigned task; describe changes and actual validation. Never infer permission to merge into `main` from permission to prepare a PR.
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
