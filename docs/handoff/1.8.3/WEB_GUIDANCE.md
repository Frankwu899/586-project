# Modern Web Guidance — COMM_586 Cloud setup and evidence

This is a development-time helper, not a runtime dependency or the app's Overview chat policy. Upstream: [GoogleChrome/modern-web-guidance](https://github.com/GoogleChrome/modern-web-guidance#alternative-installation-methods). The written PRD consulted the upstream source, including commit `64a6d708f5a43f2cd3fde5d4d7db3905ba1bdf65`. That does not mean the skill is installed/active inside COMM_586. A local Mac plugin is not proof of availability in a separate Cloud task.

## Preferred when a supported Codex CLI/plugin environment is available
Check whether the skill is already present and usable in the target environment. With the official upstream source and the required permission in that environment, use the supported installer:
```sh
codex plugin marketplace add GoogleChrome/modern-web-guidance
codex plugin add modern-web-guidance@googlechrome
```
These are upstream Codex CLI commands; a Cloud worker may lack the CLI, plugin control or outbound GitHub access. Do not change global network policy or publish environment settings from the kickoff. A supported repo-scoped install may instead use the upstream package's `skills/modern-web-guidance` at `.agents/skills/modern-web-guidance/` on the reviewed shared docs/setup commit, with upstream version and license preserved; do not vendor other upstream skills. Verify discovery and working retrieval separately.

## Cloud fallback when plugin installation is not available
For immediate guidance the upstream CLI can search and retrieve **without** plugin installation:
```sh
DISABLE_TELEMETRY=1 npx -y modern-web-guidance@latest search "responsive data table"
DISABLE_TELEMETRY=1 npx -y modern-web-guidance@latest retrieve "size-aware-styling"
```
The search and retrieve commands are smoke checks of guidance access. Use the skill's actual version flag and returned guide IDs for implementation queries. Record the exact resolved package version; for team reproducibility use a verified pinned package in a supported Cloud environment setup, without adding the tool to the app's runtime dependencies. If the package cannot be fetched in the agent phase, try the allowed environment setup or cached package, where available. If offline setup cannot run, read the pinned upstream SKILL.md and relevant guide files from an accessible trusted source; record **reference-only**, not installed. The scoped PRD acceptance still applies. No private documents, project inputs, or user data are needed in a guidance query.

## Required proof and UI usage
- Record activation scope and real outcome: **skill discovered and CLI retrieval succeeded**, **CLI available only**, or **reference-only / unavailable**. Give source/installed version, an actual retrieved guide ID, and any failure. Recheck in a new Cloud task before assuming it inherited setup.
- Search for the specific problem before editing: responsive pane/scroll ownership, accessible dialog/focus, input-method-safe submit, readable data table and constrained player sizing. Apply relevant documented fallbacks. Avoid unrelated legacy scans.
- Verify actual UI independently: Chrome/Safari as available, narrow container and zoom, preserved focus and accessible state, nonclipped controls, readable graph states, local table/timeline horizontal scrolling only. The acceptance spec is the PRD, not a skill's sample code.
- Official setup references: [Codex skills and repository locations](https://learn.chatgpt.com/docs/build-skills) and [Codex Cloud environments](https://learn.chatgpt.com/docs/cloud).
