# Video Anatomy — M2 Implementation Handoff

Version: 1.0, 2026-10-17. Selected design: Editorial Studio. Scope: the single-task demo.

## Contents

| File | Purpose |
|---|---|
| `01_M2_PRD.md` | Product scope, functional tree, input rules and lifecycle |
| `02_M2_UIUX_Editorial_Studio.md` | Layout, design tokens, components, interactions and states |
| `03_M2_Contract_Impact.md` | Explicit proposed M10 changes, baseline findings and migration |
| `04_M2_Acceptance.md` | Observable test cases and required implementation evidence |
| `05_M2_Codex_Implementation_Prompt.md` | Complete ready-to-use English implementation prompt |
| `06_M2_Integration_Summary.md` | Decision summary for the coordinating conversation |

These files belong under `docs/m2-handoff/` in the repository. The ZIP already contains that directory structure. No application source has been implemented in this handoff. Shared project `sources/` files remain reference-only.

## Fast start when this folder is already on GitHub

If `docs/m2-handoff/` is already present on `feat/workspace/m2-brief-experience`, branch creation and document upload are complete. Start a Codex implementation task using that repository and branch, then ask it to read and execute `docs/m2-handoff/05_M2_Codex_Implementation_Prompt.md` in full. No local ZIP copy, additional document commit or GitHub Desktop branch switch is required for cloud implementation. Leave unrelated uncommitted local changes on their current branch. The implementation prompt still rechecks the prerequisite and branch ancestry.

## Manual preparation steps (only when the handoff is not yet in the repository)

1. Open `Frankwu899/586-project` in GitHub Desktop or your existing development checkout. Fetch origin and recheck [PR #3](https://github.com/Frankwu899/586-project/pull/3).
2. At the time of this handoff PR #3 is still unmerged. Select the current `feat/video-analysis/bilingual-provider-contracts` branch and create `feat/workspace/m2-brief-experience` from it. If PR #3 has since merged, update main, verify it contains that work, and create the M2 branch from main instead. Preserve any existing work; use a different branch name if needed.
3. Extract the ZIP and copy its `docs/m2-handoff/` folder into your local repository's `docs/` directory. Do not copy the entire project mirror or replace synced source references. Review the seven Markdown files, then commit them as `docs: add M2 Editorial Studio implementation handoff`. Publish the M2 branch if using remote Codex.
4. In the implementation environment, select this repository and prepared M2 branch, or open that local checkout. Paste the complete prompt from `05_M2_Codex_Implementation_Prompt.md`. Keep this handoff directory available to the task. The prompt rechecks ancestry and current PR status again before implementation.
5. Let Codex implement, run tests and prepare a draft PR. No API key is required for the manual workflow and offline fake-provider acceptance. Do not paste secrets into a chat. Live testing requires separate server-side secret configuration and an explicit spending limit.
6. Review the result report and actual changes. A stacked M2 PR targets the prerequisite branch while PR #3 remains unmerged; after the prerequisite merges, update the branch and retarget according to repository policy. Do not automatically merge either PR based on this handoff.
7. Run the demo using the current repository's `README_SETUP.md`. Verify: partial input survives reopen; reference-first entry works; extracted facts require acceptance; confirmed claims retain qualifiers; complete inputs plus reviewed reference enable two directions; explicit direction approval enables M7; an applied input change invalidates current downstream eligibility without erasing history.
8. Bring `06_M2_Integration_Summary.md` plus the implementation report/PR link back to the coordinating conversation. Distinguish automated pass, manual acceptance and untested real API quality.

## What to approve after implementation

Inspect the actual empty/partial/review/applied/error screens, not only design screenshots. Check the test report against document 04 and check that final M10 deltas are listed. A good visual result alone does not establish correct persistence, approvals or provider behavior.

## Sources and limits of this handoff

The project context, blueprint, uploaded grill-me instructions and earlier accepted decisions informed scope. The selected Editorial Studio direction informed document 02. Current repository facts were checked read-only at the PR head stated in document 03. No application test suite, paid API evaluation, merge or deployment was performed in preparing these documents.

The original style exploration remains a design reference in the conversation. This package contains implementation specifications, not a production-ready mockup component or a claim of browser-verified final screens. Any unresolved details outside the stated scope should be deferred rather than expanded into extra demo branches.
