# Modern Web Guidance setup evidence

Verified in the COMM_586 Cloud task on 2026-11-17. This is a development tool; it is not an application runtime dependency or an Overview conversation policy.

## Source and installation

- Official source: [GoogleChrome/modern-web-guidance](https://github.com/GoogleChrome/modern-web-guidance).
- Reviewed and installed source commit: `64a6d708f5a43f2cd3fde5d4d7db3905ba1bdf65`, the reference named in the 1.8.3 handoff.
- Codex CLI: `0.159.2`; Node: `v24.19.0`; npm: `11.9.0`.
- Plugin and npm CLI package version: `1.0.1`.
- Search protocol flag from the installed skill: `--skill-version 2026_11_10-47b4c80e`.

The owner explicitly requested installation after the read-only Phase 0 inspection. The official Codex installation succeeded:

```sh
codex plugin marketplace add GoogleChrome/modern-web-guidance --ref 64a6d708f5a43f2cd3fde5d4d7db3905ba1bdf65 --json
codex plugin add modern-web-guidance@googlechrome --json
codex plugin list
codex plugin marketplace list
```

The installation receipt identifies `modern-web-guidance@googlechrome`, version `1.0.1`, installed at `/home/agent/.codex/plugins/cache/googlechrome/modern-web-guidance/1.0.1`. The local plugin listing reports **installed, enabled**. The marketplace checkout's `git rev-parse HEAD` equals the reviewed source commit above.

Activation scope is this Cloud user's Codex CLI plugin registry. The installed `skills/modern-web-guidance/SKILL.md` was read explicitly before implementation guidance was retrieved. This verifies local plugin discovery and working CLI retrieval; it does not establish that an already-running chat refreshed its advertised skill catalog or that another Cloud task inherits the installation. Recheck in each new task.

The official plugin also bundles the upstream `chrome-extensions` skill. It was not separately installed or used for this task. No skill files were vendored into this repository, and no application dependency manifests were changed. Upstream licensing remains intact in the installed package: Apache-2.0 for software and CC-BY-4.0 for guide content, per its README and license notices.

## Retrieval evidence

All commands ran with telemetry disabled and generic UI queries, outside application dependencies:

```sh
DISABLE_TELEMETRY=1 npx -y modern-web-guidance@1.0.1 --version
DISABLE_TELEMETRY=1 npx -y modern-web-guidance@1.0.1 search "responsive scroll panes" --skill-version 2026_11_10-47b4c80e
DISABLE_TELEMETRY=1 npx -y modern-web-guidance@1.0.1 search "accessible modal dialog" --skill-version 2026_11_10-47b4c80e
DISABLE_TELEMETRY=1 npx -y modern-web-guidance@1.0.1 search "composition safe submit" --skill-version 2026_11_10-47b4c80e
DISABLE_TELEMETRY=1 npx -y modern-web-guidance@1.0.1 retrieve "css-layout,responsive-design,dialog,accessibility,ime-safe-enter-submit,forms"
```

The version command and the resolved npm cache's `package.json` both report `1.0.1`. Each search returned matching real guide IDs. Retrieval succeeded, producing 1,687 lines; the complete output was read in line ranges from its CLI-generated temporary file. That temporary file is session evidence, not a stable project asset.

| Guide ID | Relevant requirement reviewed |
| --- | --- |
| `css-layout` | Use flexible grid/flex sizing, allow long-content children to shrink with `min-inline-size: 0`, fix overflow at its source, and give intended scroll regions `overflow: auto`. Avoid hiding controls with clipping. |
| `responsive-design` | Adapt components to their container, reserve media space using aspect ratio, and use dynamic viewport units where viewport height is constrained. |
| `dialog` | Use native `dialog.showModal()` for blocking review; give it an accessible name and safe initial focus. Preserve native containment and focus return. Treat `closedby` as progressive enhancement, including on Safari. |
| `accessibility` | Keep DOM and keyboard order aligned, expose control names and state, preserve visible focus, and independently test keyboard behavior. |
| `ime-safe-enter-submit` | Check native `isComposing` and Safari's confirming-Enter `keyCode === 229` fallback before submitting; preserve a real submit button and associated label. |
| `forms` | Use a semantic form, explicit button types, persistent labels, linked errors, and accessible disclosure state. Secondary actions such as Stop must not implicitly submit. |

These are implementation inputs, not evidence that the app passes browser acceptance. The approved 1.8.3 PRD governs product behavior and scope. Chrome/Chromium checks, Safari/native Mac acceptance, zoom, narrow containers and IME behavior need their own implementation verification receipts.

## Observed limitations

- `codex plugin list` warns that the remote global catalog request to `https://chatgpt.com/backend-api/ps/plugins/list` failed. The configured local Google Chrome marketplace, install receipt and local installed/enabled listing still succeed. No network policy was changed.
- The Git plugin distribution contains the skill and guides but no `skills/modern-web-guidance/modern-web.mjs` executable. A direct Node probe returned `MODULE_NOT_FOUND`; use the skill's documented pinned `npx` command above. npm retrieval succeeds.
- The earlier Phase 0 state was **CLI available only**. The authorized installation supersedes that state for this Cloud CLI; it does not prove automatic chat activation elsewhere.

No application dependencies, application models, billing settings or global network policy were changed by this setup. No paid inference, commit, push, PR, merge or release publication was performed by the setup task.
