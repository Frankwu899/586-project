# Workspace usability and Research recovery — v0.7.3

## Context and scope

The owner could run analysis but could not delete projects, saw an exhausted
shared experiment budget, received speech-only timelines and Chinese Structure
results, and found transferable methods too generic. The authorized change adds
basic project operations, English/Chinese application language, GPT-6+ model
defaults, better extraction and analysis inputs, and responsive workspace layouts.

Repository: `Frankwu899/586-project`. Branch:
`feat/workspace/structure-agent-redesign`, building on `70c08b0`. Draft PR #8 stays
stacked on #7 (`fix/creative-direction/constrain-reviewed-citations`). No merge,
deployment, real API call or training is included in this update.

## Resulting behavior

- Project menus expose open, rename and move to Trash; close saves drafts and
  clears the active selection. Trash and restore preserve media, drafts, analysis
  and output history. Running operations prevent destructive lifecycle races.
- The application defaults to English, with Chinese available in the header.
  Local preferences persist separately from credentials. Changes rebuild all
  relevant adapters without restarting or resetting the task store or ledger.
  Newly generated Research and context assistance follow app language. Ideas'
  generation language remains independent. Source quotes and saved outputs are
  never silently rewritten or re-generated.
- Visual/OCR extraction runs in batches of up to three frames. Validated batches
  survive failures elsewhere and are reused when inputs match. Each failed
  channel exposes its safe error rather than implying nothing was in the video.
  Immutable analysis history retains extraction failures and output language.
- Structure receives actual structured visual details and coverage limits. Its
  methods must explain an evidenced communication mechanism, applicability and
  limits, rather than list generic hooks or summarize topics. Analysis guidance
  contains no hardcoded owner-case answers. Partial evidence stays explicit.
- Eligible generation uses GPT-6.1 Sol; bounded background retrieval uses GPT-6
  Luna. Missing model permissions do not silently fall back to old models. See
  [the capability and pricing record](gpt6-budget-recovery.md).
- GPT-6 does not accept audio input. The owner's dedicated speech-model exception
  remains unanswered. Normal local launchers therefore disable new transcription,
  including stale Whisper environment defaults. Existing saved transcripts remain
  readable. Compatible, validated legacy speech caches can be reused without a
  new call, with their original model and cached provenance retained. Without
  such a cache, speech is marked not analyzed, not failed or empty.
- Budget preflight counts input before generation instead of reserving an entire
  context for every small request. The existing USD 3 ledger remains authoritative.
  Settings show estimated usage, available allowance and unresolved reservations.
  An explicit recovery action releases only historical authentication/permission
  refusals; unknown charges, original audit records and the ceiling are retained.
  Accounting pauses remain visible and are not automatically cleared.
- Desktop panels remain bounded; smaller windows stack panels and collapse the
  project sidebar. Timeline scrolling stays within its own panel. Research errors
  are local to the operation rather than duplicated at the top of the window.

## Shared-file integration

Root owned API mounting, `AnalysisResult`/Structure metadata and generated schemas,
local preference routes, budget settings display and release packaging. Separate
agents owned project storage/routes, project shell, locale dictionaries/modules,
Research extraction/Structure guidance, provider/budget accounting, and responsive
Research components. Independent review prompted deadline propagation, broader
language coverage and explicit blocked-budget display before final verification.

New contract fields are optional/defaulted for historical payloads. Original
v0.3–v0.6 schemas and examples remain unchanged; migration tests verify that all
legacy content survives after accounting for the new empty metadata.

## Verification and limitations

The full offline backend regression and focused browser suites cover library
retention, exact revisions, active-request races, locale persistence, model
selection, conservative budget settlement, partial vision recovery, background
deadline enforcement and project menus. Browser coverage includes 1440×900,
1280×720, 1024×768, 768×1024 and 390×844 windows. Source, contracts and production
build checks passed. Final results: **717 backend tests**, **30 distinct browser
scenarios**, seven frontend unit-test files, TypeScript, ESLint, Ruff and generated
contract checks passed. Browser counts include successful focused reruns after
test fixture/selector corrections, not a second execution of the entire suite.

The final archive's 114 source/UI manifest hashes match this worktree. Extracted
package verification checked plist/version, executable permission, shell syntax,
real localhost startup, empty library, persisted preferences, zero-attempt budget,
Trash/Restore, served built UI, absence of bundle-relative data, and authenticated
shutdown. ZIP SHA-256:
`00941028b56ef0b69fedf986224cba7ee0248236f6d6ff633b9bafc617edec91`.

No owner credential is available in this Cloud environment and its network policy
does not permit OpenAI. Therefore no claim is made about the exact cause of the
owner's previous local vision failure, actual GPT-6 access, model latency, real
analysis quality or billed cost. Better prompts and complete visual inputs still
need human acceptance on real videos. Native Finder, Keychain and Gatekeeper
behavior remains untested on an actual Mac; the package is unsigned and uses
installed Python 3.12 and FFmpeg rather than bundling a standalone runtime.

## Delivery and local acceptance

The v0.7.3 ZIP contains `Video Anatomy.app`, a Finder launcher for the local browser
workspace, and English setup instructions. It is not a DMG. No owner case video,
task database, credential, ledger or local cache is bundled.

Keep the original library. Extract the new app and reopen it; verified idle old
instances can hand over to the new build. In API connection, inspect the budget
and release explicit rejected-request reservations if offered. Retry missing
visual analysis, then create a new Structure result in the selected app language.
Compare methods only after checking that the source has the expected modalities.
Use the project menu to test Trash/Restore and close/reopen draft preservation.

Related records: [project lifecycle](project-lifecycle-menus.md),
[application language](application-language.md),
[Research extraction](research-extraction-quality-repair.md), and
[Mac setup](../../MAC_APP.md).
