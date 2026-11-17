# Video Anatomy 1.8.3 — COMM_586 handoff
Prepared 2026-11-17. Target version 1.8.3; design/specification handoff only.

## Use this package
1. Open a **new Cloud conversation in COMM_586**, with the environment for `Frankwu899/586-project`. Upload this ZIP and paste the short prompt below. If that conversation cannot extract the ZIP, unzip it and attach the two Markdown specs, `MODULE_TASKS.md`, `WEB_GUIDANCE.md`, and any images the first task needs. Ask it to enumerate the received files; a screenshot of a filename is not evidence of access.
2. Start with **Phase 0 (baseline and integration setup)**. Have it verify checkout and dependency PRs and report the skill status. Do not assume the environment name selects a branch. The observed 1.8.2 package is at `bd93bfc884b70be81bbf93ddf2c72b42cea7dafc`; PR #19 was open Draft, based on 1.8.1, at handoff. If there is more recent work, compare it before choosing a base; do not silently start from main or an old docs branch.
3. Once this packet has been received and the base is agreed, keep the approved handoff in a **docs-only commit** on the selected shared integration base (suggested path `docs/handoff/1.8.3/`), if authorized. Share the exact Git ref and path with each module conversation. If repo-stored images are undesirable, point to a stable asset location and verify that each task can read it. Do not drop the approved handoff into unrelated app source changes.
4. Use one integrator and three bounded implementation streams per `MODULE_TASKS.md`. If Frank is building alone, sequential tasks in the same execution conversation are fine; keep the same module gates. Do not assign all app changes as one open-ended prompt. Finish with a single integrated 1.8.3 release candidate on its final verified commit.

## Paste this into the new COMM_586 Cloud conversation

> The attached package is the canonical Video Anatomy **1.8.3** handoff. Read START_HERE, the PRD, the Master Handoff, MODULE_TASKS and WEB_GUIDANCE. Inspect the UI reference images relevant to the current phase. Do Phase 0 only: verify your repository/branch/commit and the open/merged dependency chain, identify which docs and images you can actually read, and check whether Modern Web Guidance can be invoked in this Cloud workspace. If skill setup is missing, follow the setup-only instructions in WEB_GUIDANCE where supported, or report the exact limitation and use its fallback. Reply in Chinese with the proposed shared base, owner/contract boundaries, baseline and skill evidence. Do not implement application changes, open a PR, merge, publish or run paid inference from this kickoff. Wait for the module assignment.

## File map

| Source | Purpose |
| --- | --- |
| Video_Anatomy_Product_UX_PRD.md | Approved scope and execution defaults, in Chinese |
| Video_Anatomy_Codex_Master_Handoff.md | Controller role, source precedence, cross-module rules |
| MODULE_TASKS.md | Phase 0, three copyable implementation assignments, release gate |
| WEB_GUIDANCE.md | Official Developer skill setup, evidence, and offline fallback |
| ui/01_Projects.png | Project grid and recoverable trash |
| ui/02_Overview.png | Short intake, draft brief, and busy Send → Stop state |
| ui/03_Media_Pool.png | All files and four bins, separate focus and analysis selection |
| ui/04_Source_Review.png | Same Resources tab, recorded reference timeline and evidence inspector |
| ui/05_Discover.png | Reserved state |
| ui/06_Analysis.png | Key insights first, readable structure flow, source jumps |
| ui/07_Content_Plan.png | Standalone default, optional Series, approved direction |
| ui/08_Production.png | Same Video, compact brief, one sheet with one shot per row |

Images are layout examples. Preserve the PRD's behavior when illustrative states/displays in images differ. Use the actual app's asset and UI system. Do not commit fake sample media or captions as functionality.
