# Video Anatomy — English Repository Starter

**English edition: 14 October 2026. Based on the proposed v0.1 baseline of 8 October 2026. Contract version remains `0.1.0`.**

This package contains documentation, a proposed analysis schema, synthetic examples, and empty team record templates. It is not a running application. The English edition preserves the original 16 file paths and adds two handoff/workflow documents. The JSON schema, JSON examples, and CSV headers are unchanged.

## Replace the earlier starter

1. Keep your existing Git repository and its history. Do not create a new repository or copy this package into a second nested project folder.
2. If you have edited any starter files since copying them, preserve those edits and compare the corresponding files before replacing them. Replace matching starter files individually; merge folder contents so unrelated files remain intact. Do not delete whole repository folders.
3. Copy the contents of `repository-starter-en` into your existing repository root. `AGENTS.md`, `CLAUDE.md`, and this file should sit directly at the root, alongside `docs`, `contracts`, `examples`, and `data`.
4. Ask the local coding agent to read the updated documents and inspect the diff using Prompt A in `docs/cloud-workflow.md`.
5. Commit and push the starter on a documentation task branch. Review its pull request and merge it into `main` as the project integrator, or explicitly select the pushed branch for Cloud work. A file copied onto your Mac is not yet available in the GitHub repository.
6. Create or select a Codex Cloud environment connected to the same GitHub repository, then begin a new Cloud task. Use Prompt C in `docs/cloud-workflow.md` after the setup is ready.

This package does not create a GitHub repository, configure permissions, install runtimes, or move an existing local conversation into Cloud.

## Read in this order

1. `AGENTS.md` — shared agent instructions.
2. `docs/project-brief.md` — product goal, scope, and unresolved decisions.
3. `docs/architecture.md` — candidate modules and stack.
4. `docs/interfaces.md` — shared data semantics and workflow rules.
5. `docs/handoff/2026-10-14-setup.md` — reported setup progress and remaining work.
6. `docs/cloud-workflow.md` — local replacement, GitHub handoff, Cloud setup, and copyable prompts.

When changing shared data, also read the schema and both JSON examples. Claude Code's project entry point is `CLAUDE.md`.

## File map

| File or directory | Purpose |
|---|---|
| `AGENTS.md` / `CLAUDE.md` | Shared coding-agent instructions and Claude entry point |
| `docs/project-brief.md` | Confirmed product decisions and midterm boundaries |
| `docs/architecture.md` | Candidate architecture; implementation choices remain proposals |
| `docs/interfaces.md` | Data exchange, review, revision, and dependency rules |
| `contracts/analysis.schema.json` | Proposed structural validation for AnalysisResult |
| `examples/analysis_result.original.json` | Synthetic original model-result example, revision 1 |
| `examples/analysis_result.json` | Synthetic user-revised example, revision 2 |
| `data/templates/README.md` | Instructions for the five CSV templates |
| `data/templates/*.csv` | Empty collection, annotation, creative review, spike, and cost records |
| `docs/handoff/TEMPLATE.md` | Reusable task, device, and agent handoff template |
| `docs/handoff/2026-10-14-setup.md` | Initial setup handoff based on the owner's reports |
| `docs/cloud-workflow.md` | Local-to-Cloud workflow and starter prompts |

## Contract authority and evidence limits

`contracts/analysis.schema.json` governs fields, types, and structural constraints. `docs/interfaces.md` governs cross-field rules, revision dependencies, and business semantics. Resolve any conflict together in the same PR, including affected examples and consumers.

No real videos, brand performance data, API keys, or actual model outputs are included. Both JSON files are synthetic; they cannot establish model accuracy. CSV files contain headers only. Unknown numeric values remain blank in CSV and `null` in JSON. Zero means an observed zero. Keep the source and collection time for public metrics.

`start_seconds` and `end_seconds` refer to the original reference video, in seconds, not milliseconds or a newly generated video's timeline. Schema validation alone cannot enforce every time boundary, revision lineage, or dependency rule. Backend semantic validation is also required.

## Installation and runtime status

There are no application startup commands yet: no application code, `package.json`, or dependency manifest is included. The React/Vite/TypeScript and FastAPI/Python combination remains a candidate. Record the stack decision, validate it, and then pin versions and document actual installation and startup commands.

The owner prefers Cloud for ongoing coding and unattended tasks. The team still plans to run and inspect the demo locally. These are separate choices: Cloud coding does not deploy the application, and a local demo does not require local-only coding. Install the chosen application's runtimes on each machine that will actually run it.

## Verification of this edition

The English edition was checked for completeness against the original 16 paths and for remaining Chinese text. The schema, both JSON examples, and all five CSV templates were compared byte-for-byte with the original starter. Both examples were parsed and checked for time bounds, stable IDs, revision lineage, edited fields, date/time ordering, and metric-source consistency. A full JSON Schema validator was not rerun for this translation; the schema and example bytes are unchanged.

These checks concern the documentation package and fixtures only. No application, provider integration, deployed service, or browser workflow was executed.
