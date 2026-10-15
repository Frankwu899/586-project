# Local-to-Cloud Workflow and Starter Prompts

**Updated: 14 October 2026.** This guide supports a Cloud-first coding workflow while keeping the existing Mac repository for review and demonstrations.

## 1. Replace the local starter files

Unzip this package. Copy the contents of `repository-starter-en` into the existing `586 Project` repository root. Do not place the enclosing folder inside the repository. Replace matching starter files, merging directory contents. Preserve any new application files, edited records, local configuration, and the existing Git history. If a starter file has been edited since the original copy, compare and merge those edits before replacing it.

The original 16 paths remain present. Two files are added: this guide and `docs/handoff/2026-10-14-setup.md`. The schema version remains `0.1.0`. This is an English documentation edition, not an application upgrade.

## 2. Ask the local Codex chat to read the new files

Select **This computer / Local** and the existing repository. Use Prompt A below. Reading the local files checks this copy; it does not synchronize the files or conversation to Cloud.

### Prompt A — local review only

```text
I replaced the Video Anatomy repository starter with the English edition dated 14 October 2026. Work in the existing local repository; do not create another repository or nested project folder.

First verify the current directory, repository root, branch, working-tree changes, and remote. The intended GitHub repository is Frankwu899/586-project. Preserve unrelated work.

Read AGENTS.md, README_SETUP.md, docs/project-brief.md, docs/architecture.md, docs/interfaces.md, docs/cloud-workflow.md, docs/handoff/2026-10-14-setup.md, contracts/analysis.schema.json, both analysis examples, and data/templates/README.md.

Confirm which files you read. Summarize the agreed midterm scope, unresolved decisions, and what is actually implemented. Check that the starter is at the repository root, that its documentation is in English, and that the schema and examples are coherent. Report any missing files or contradictions without inventing decisions.

Inspect whether these files are committed and present on the remote branch. Distinguish verified facts from checks not run. Do not assume earlier chat history is available.

For this task, do not modify files, install tools, generate application code, commit, push, or create a PR. End with the exact next steps for making this English baseline available to a new Codex Cloud task.
```

## 3. Make the baseline available through GitHub

Use a documentation branch such as `docs/english-starter`. Review and commit only the intended starter changes, then push the branch and open a PR. The project integrator reviews and merges into `main`. Alternatively, start Cloud on the exact pushed branch if your environment supports selecting it. In either case, verify the branch and commit used by Cloud.

GitHub Desktop can handle the commit and push; GitHub CLI is optional. If you prefer an agent-driven handoff, send Prompt B after reviewing the local inspection. The authorization in that prompt applies when you send it to the local agent; the text being stored here is not an instruction to perform these actions during a read-only task.

### Prompt B — prepare the documentation handoff

```text
Prepare the reviewed English Video Anatomy starter for Cloud work. This task authorizes creating a documentation branch, committing the intended starter files, pushing that branch, and preparing a pull request. Do not merge into main.

Follow AGENTS.md. Inspect the current branch, remote, and working-tree changes first. Use docs/english-starter or another unused descriptive branch name. Preserve unrelated files and changes; do not force-push, rewrite history, or discard work.

Review the English starter diff and confirm the schema, examples, and CSV templates are consistent. Stage only the intended starter files. Commit with a clear English message and push to the matching remote branch. If a required capability or authentication is unavailable, finish the feasible steps and provide exact GitHub Desktop/browser instructions for the remaining step; do not claim success for an action you did not complete.

Return the actual branch, commit SHA, verified push result, PR link if created, checks performed, and remaining steps. Do not install application dependencies, implement features, or invoke paid model APIs for this documentation handoff.
```

Review the PR and merge it as the integrator before starting from `main`. Pull the merged baseline into the local repository. The agent's permission to prepare the PR does not include permission to merge it.

## 4. Set up the Cloud environment

In a new Codex task, choose **Work in > Cloud**, open **Select environment**, and choose **Create environment** if needed. Select `Frankwu899/586-project`, then let setup inspect the repository. Review the setup report, save, and publish the environment; after it is published, start a new task.

During setup, explain that this repository currently contains documentation and fixtures only. There is no application dependency manifest or valid application startup command yet. Treat a runnable scaffold as a separate implementation task. When the stack is established, configure and test its dependencies in Cloud and document reproducible versions/commands.

Publishing a Cloud environment prepares a reusable coding setup; it does not publish the product website or make the private repository public. Keep access settings appropriate for the team.

Cloud tasks have their own files and runtime. The Mac's missing Node.js/npm do not block a Cloud documentation task. The Mac will need the selected runtimes when it must run the application. Existing Apple-provided Python is not proof of compatibility; establish project requirements first.

## 5. Start the first Cloud chat

Use Prompt C in a **Cloud** task connected to the repository. It is an onboarding and planning task; a later explicit implementation task can authorize coding. Keep discussing and reviewing related work in the same Cloud task as useful. A separate task should read the repository and latest handoff again.

### Prompt C — Cloud onboarding

```text
You are helping develop Video Anatomy for COMM-586. This task is intended to run in Codex Cloud against Frankwu899/586-project.

Verify your actual execution environment, repository root, remote, checked-out branch, commit SHA, and working-tree status. Confirm that the English starter dated 14 October 2026 is present. If the expected files are missing or the checkout is stale, report that before drawing conclusions. Do not use Mac-specific paths or assume local tools and private chat history were transferred here.

Read AGENTS.md, README_SETUP.md, docs/project-brief.md, docs/architecture.md, docs/interfaces.md, docs/cloud-workflow.md, docs/handoff/2026-10-14-setup.md and any newer relevant handoffs, contracts/analysis.schema.json, both analysis examples, and data/templates/README.md.

Summarize the confirmed scope: one brand brief and one product-benefit reference video; timed content segments; user corrections to roles, text, and visual descriptions; an explicit human creative-direction choice/approval; a Creative brief and a text storyboard. File upload is the baseline; link support awaits a small spike. Only public views/likes/comments are currently available. Do not claim performance causality or expand the scope silently.

Check the actual Cloud tool availability and distinguish it from the earlier Mac report. State what is implemented, what is proposed, and which checks have not been run. Propose the smallest next implementation task, with acceptance criteria and any stack/provider decisions needed first. Preserve the requirement for a local team demo even though coding happens in Cloud.

For this onboarding task, do not change files, install additional dependencies, implement the app, push, create a PR, deploy, or call paid APIs. End with a concrete next task and only the decisions that would materially block it. Respond in English.
```

## 6. Continue development and preserve context

For each implementation task, provide an objective, scope, acceptance criteria, and any required assets. Use a task branch and ask for the actual checks, changed files, and unresolved issues. Write a new handoff in `docs/handoff/` with `TEMPLATE.md`, recording relevant decisions and verified results. Update product/architecture/interface documents when an approved decision changes them.

Repository documents carry shared project context. Exporting this entire planning conversation is unnecessary; add any missing material decision to the appropriate document instead. Keep technical identifiers stable when editing prose. Ask the agent to read project files explicitly when starting in a new tool or environment.

Commit and push work that must be available elsewhere. Cloud setup changes may require updating and republishing the environment; an existing task retains its own state. Verify the working branch/commit before each handoff. Do not assume the Mac and Cloud are live-synchronized or that a new task inherits another task's uncommitted work.

Review Cloud changes and relevant test results, then fetch the task branch on the Mac and run any local checks needed for the demo. Merge after review and pull the updated `main`. Avoid simultaneous edits to the same files across Mac and Cloud while establishing the workflow.

Cloud tasks can continue while the Mac sleeps. Give each task a concrete endpoint; a finished task or one blocked on missing access/input does not imply continuous unattended development. Cloud coding remains separate from hosting the application for users.

## Official setup reference

Official references checked for this workflow: [OpenAI — Cloud environments](https://learn.chatgpt.com/docs/environments/cloud-environments) and [OpenAI — Codex environments](https://learn.chatgpt.com/docs/environments/modes). Accessed 14 October 2026. Interface labels and account availability may change; use the actual settings presented in your app. This guide does not establish that your Cloud environment has already been created or tested.
