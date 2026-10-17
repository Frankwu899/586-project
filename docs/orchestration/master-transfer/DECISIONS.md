# Video Anatomy — Decision Register

Snapshot: 2026-10-17, America/Los_Angeles.
Statuses: CONFIRMED means explicit user agreement; OPEN means not decided;
REPORTED/VERIFIED applies to implementation evidence separately.

## Durable confirmed decisions
| ID | Decision | Source | Affects |
| --- | --- | --- | --- |
| VA-D001 | Creative decision support and usable production output are the main value | Available prior project context | All |
| VA-D002 | Single task-local brief and one reference video for the first demo | Prior scope and M2 receipt | M1–M9 |
| VA-D003 | M2 input brief and M7 generated production brief are distinct | Explicit prior/M2 agreement | M2/M7 |
| VA-D004 | M2 and reference upload/analysis/review may happen in either order; converge at M6 | M2 receipt and seven-file spec | M1–M6 |
| VA-D005 | English, Chinese and mixed-language recognition/content handling; preserve original evidence | Explicit previous language confirmation | M2–M8/M10 |
| VA-D006 | Corrections include text/descriptions/roles and allowed structured labels; retain originals/history | Explicit previous correction confirmation | M4/M5/M10 |
| VA-D007 | Two directions; selection separate from explicit exact-revision approval; production follows approval | Prior workflow agreement | M6/M7 |
| VA-D008 | Editorial Studio is the M2 visual direction | M2 receipt/spec | M2; shared design reference |
| VA-D009 | Partial drafts, manual/pasted/optional AI proposals with explicit adoption | M2 receipt/spec | M2 |
| VA-D010 | Required Apply fields and user-confirmed usable claim; evidence optional, permission not verification | M2 receipt/spec | M2/M6/M7 |
| VA-D011 | Separate draft autosave and meaningful formal Apply, no-op preservation and downstream invalidation | M2 receipt/spec | M2/M10/M6–M8 |
| VA-D012 | Defer brand library/reuse/complex cases and preserve a minimal core demo | M2 receipt | All |
| VA-D013 | Parallel agents may investigate remaining modules; one coordinator consolidates decisions | User asked for multi-agent grill and agreed to proposed workflow | Orchestration |

M2's exact seven-file specification supplies detail, including claim qualification,
pending-edit gates and migration behavior. Current v0.5 implementation supplies
actual interfaces. Do not interpret this table as permission to change their semantics.

## Latest accepted round — do not ask these again
Source: preceding assistant asked Q1–Q3 with recommended yes answers; Frank replied
“现在codex的M2已经执行完毕。同意你的这些内容。” at approximately
2026-10-17 00:54 America/Los_Angeles, then asked about transferring the controller.

### VA-D014 — M5 sampled-evidence first demo — CONFIRMED
Show sampled visual evidence and timestamped speech/visible text with truthful
coverage. Defer accurate continuous shot segmentation. Preserve needed role labels
without implying exhaustive segment boundaries.
This narrows early aspirational shot-splitting ideas for the first demo only.

### VA-D015 — M6 direction contrast — CONFIRMED
A follows the reference structure more closely; B recombines useful elements into
a different narrative. At least Hook or narrative should differ meaningfully.
Explain fit to the brand and production needs. No unvalidated effectiveness score.
This is a generation/quality requirement, not proof an existing provider meets it.

### VA-D016 — M7 text-only editing scope — CONFIRMED
Allow text editing for visual descriptions, dialogue, subtitles, sound and CTA.
Retain generated order and durations in the first demo. Defer row add/delete,
reordering and timing editing.
Do not remove existing version/history/evidence protections.

### VA-D017 — discussion before execution — CONFIRMED working requirement
Frank wants an informed Codex master controller that can discuss/grill, receive
answers and then implement. Initial transfer turn is read-only takeover.
Product answers are not blanket permission for unrelated merges/deploys/paid calls.

## Open product decisions — recommendations are not approvals
| ID | Question | Dependency/handling |
| --- | --- | --- |
| VA-O001 | M5 formal correction and review controls, unsaved-edit behavior | Build on D014 and existing revision gates |
| VA-O002 | M3/M4 explicit Analyze/retry and status/error presentation | Inspect current code; do not expand media scope by default |
| VA-O003 | M6 comparison summary, evidence access and feedback/edit UX | Build on D015; align with M5 |
| VA-O004 | After manual direction edits, how to treat previously generated rationale/evidence/hypotheses | Preserve provenance; do not claim stale rationale is refreshed |
| VA-O005 | M7 detailed output quality/content and output-language UX | Build on D016, current M2 constraints and source-language rules |
| VA-O006 | M8 initial deliverable formats, dirty-state and outdated export policy | Existing Markdown/CSV and explicit historical exports are baseline, not a newly confirmed restriction |
| VA-O007 | M1 stage navigation, task recovery and readiness cues | Use v0.5 state; no competing autosave model |
| VA-O008 | M9 evaluation-first only or runtime reference retrieval | Do not block core workflow on an unapproved library |
| VA-O009 | Global Editorial Studio extension, navigation and shared UI details | M2 style stays settled; prototype consequential layout choices |

Ask at most three independent questions at a time. Discover facts before asking
Frank. Missing decisions should not block unrelated discovery.

## Historical/provisional items
- US$20 live-test budget: proposed in earlier discussion, not explicit spend permission.
- About five minutes to analyze a 1–3 minute video: provisional target, not measured.
- MOV, HEVC HDR/10-bit/Log: do not infer support from H.265 requirement.
- Batch comparison, performance scoring, organic/paid inference, training/JEV:
  earlier possible directions; not required first-demo implementation scope.
- Agent recommendations about Markdown/CSV-only exports, latest-only export,
  M9 evaluation-only and automatic last-section restore remain unconfirmed.
- Source-language evidence preservation is distinct from final-output language UX.

## Update discipline
Append or supersede decisions with source and affected modules. Never silently
rewrite a user decision, turn an implementation accident into product intent, or
count assistant advice as user approval. Broadcast each shared change to agents.

