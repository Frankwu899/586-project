# Module-based Git workflow

`main` is the only permanent shared branch. It holds the reviewed baseline. A task branch is a temporary workspace for one change; it contains the complete repository, not just its named module. Module names identify the work and reviewer, not directories or separate products. Existing historical branches are preserved during this setup.

Read [module ownership](module-ownership.md), [interfaces](interfaces.md), and the [integration handoff](handoff/skeleton-integration-and-branches.md) before starting. The handoff records actual verification and publication status. Earlier skeleton handoffs describe earlier runs; they do not establish that a new checkout passed.

## Choose a task name

Use `<type>/<module>/<specific-task>` with lowercase words separated by hyphens. Types are `feat` (new behavior), `fix` (repair), `docs` (documentation), `test` (verification), and `chore` (maintenance).

| Module scope | Work covered | Example branch |
|---|---|---|
| `contracts` | M10: shared models, schemas, types, migrations, timing | `fix/contracts/preserve-missing-frame-timing` |
| `workspace` | M1/M2: tasks and brand briefs | `feat/workspace/brief-validation-hints` |
| `video-input` | M3: upload, validation, media probing | `fix/video-input/explain-unsupported-codec` |
| `video-analysis` | M4: recognition and normalization | `feat/video-analysis/first-real-provider` |
| `analysis-review` | M5: timeline, corrections, confirmation | `fix/analysis-review/preserve-corrected-content` |
| `creative-direction` | M6: alternatives, prompting, approval | `feat/creative-direction/first-real-provider` |
| `production-output` | M7/M8: production brief, storyboard, exports | `fix/production-output/escape-export-text` |
| `reference-library` | M9: team examples and annotations | `docs/reference-library/annotation-guide` |
| `integration` | Coordinated work spanning modules | `chore/integration/overnight-skeleton` |
| `project` | Documentation spanning the application | `docs/project/update-team-setup` |

Do not create permanent module branches or move directories to match these names. Older branch and commit names remain part of the history.

## One task, from start to merge

1. **Inspect and update `main`.** Run the commands below from your existing checkout. Fetching is safe with local edits; switching branches requires first accounting for those edits.

   ```bash
   git status --short
   git branch --show-current
   git remote -v
   git fetch origin
   ```

   If there are changes, review them and either commit the intended work on its current task branch or use a separate worktree for the new task. Do not discard changes, automatically stash them, or commit secrets/runtime data. With a clean working tree:

   ```bash
   git switch main
   git pull --ff-only origin main
   ```

   If the fast-forward pull fails, inspect the divergent commits with the integrator; do not reset or force-push. If this checkout has no local `main`, use `git switch --track origin/main` instead of `git switch main`.

2. **Create one task branch.** Agree on scope and any shared-file edits before parallel work. For a new example task:

   ```bash
   git switch -c fix/analysis-review/preserve-corrected-content
   ```

   If that name already exists locally or remotely, inspect it. Resume the existing task only when appropriate; otherwise choose a clear unused suffix. Never reset an existing branch to claim its name. The two provider branches below have a separate post-integration preparation rule.

3. **Make coherent commits.** Keep each commit focused on a meaningful change. Inspect `git diff`, stage the intended paths explicitly, inspect `git diff --cached`, then commit. Example messages:

   ```text
   feat(video-analysis): normalize provider output
   fix(analysis-review): preserve corrected content
   docs(project): explain module ownership
   ```

   Do not rewrite old commits to adopt this convention. Keep credentials, uploaded media, local environments, and `.local-data/` out of commits.

4. **Verify and push.** Run checks relevant to the change; use `bash scripts/verify.sh` for this integration and changes affecting the connected workflow. Record commands, results, and anything not run in the PR and handoff. Check processing-job and analysis statuses; HTTP 200 alone does not prove generation succeeded. Push the current task branch:

   ```bash
   git push -u origin HEAD
   ```

5. **Open a pull request into `main`.** Use the GitHub page for the pushed branch, or `gh pr create --base main` if GitHub CLI is available. Explain the problem, resulting behavior, module/shared-file changes, and actual checks using the repository template. A push publishes the branch; it does not merge it.

6. **Review, test, and merge.** Frank is the integrator; involve Andrea for recognition/interface changes. Satisfy the repository's current required checks and reviews. If `main` changed, fetch and merge `origin/main` into the task branch, resolve conflicts while preserving documented behavior, rerun affected checks, and push. Recheck the PR head and current `main` before using the permitted PR merge route. Preserve submitted commit history for this integration; do not squash or rebase it. Never bypass protection or required review. Permission to prepare a PR alone does not authorize an agent to merge; the current integration request explicitly authorizes merging after its gates pass.

7. **Start the next task from updated `main`.** Fetch, switch to `main`, and fast-forward pull again. Do not branch new unrelated work from an old feature branch. Branch deletion is not part of this setup: retain existing historical branches and do not use automatic deletion as a cleanup step.

## The two prepared next tasks

Preparation is **pending at the time this guide is committed**. Create and publish these branches only after the accepted baseline is merged and verified on `origin/main`. The final integration report must provide their verified names and exact base commit. This table is intent, not evidence that either branch exists.

| Intended branch | Owner | First task |
|---|---|---|
| `feat/video-analysis/first-real-provider` | Andrea | Implement real recognition behind `RecognitionAdapter.analyze`. |
| `feat/creative-direction/first-real-provider` | Frank | Connect real creative generation behind `CreativeAdapter`. |

The integrator must inspect any existing names and work first; preserve existing branches and use an unused task suffix when necessary. Both new branches must start at the same verified `origin/main` commit, without empty commits. If integration is blocked, preparation stays deferred. This setup does not implement either provider, choose a provider budget, or authorize API charges.

After the final report confirms a branch is ready, its owner fetches and switches to it. For example, Andrea can use `git switch --track origin/feat/video-analysis/first-real-provider` if there is no local branch yet; if one exists, inspect it and use `git switch feat/video-analysis/first-real-provider` followed by `git pull --ff-only`. Frank follows the same steps for the creative branch. Use any actual replacement names from the final report.

## Bring Cloud changes to a Mac

Cloud work does not update your Mac. In the existing Mac repository, run the inspection/fetch commands in step 1. Preserve local edits before switching, then run `git switch main` and `git pull --ff-only origin main`. If local work must stay open, use a separate checkout/worktree rather than discarding it. Stop and inspect a fast-forward failure; do not reset to make it disappear.

Follow [README_SETUP.md](../README_SETUP.md) to install the required local runtimes/dependencies and run the app. Git does not transfer Python/Node environments, API keys, task data, downloaded videos, or generated sample media. Keep any data transfer separate and preserve both SQLite records and their media. A Cloud test result is not a Mac test result.
