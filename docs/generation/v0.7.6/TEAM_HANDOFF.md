# Video Anatomy — Intermediate Release Team Handoff

**Shared baseline: app v0.7.5. New deliverable: generation skill specification v0.7.6.**
**v0.7.6 is the skill/documentation release; the runnable application is still v0.7.5.**
This is a plan and owner-confirmed behavioral specification. The harness and UI
changes below have not been implemented by this documentation delivery. There
are no new model-quality results, paid evaluations or fine-tuning results.

## Outcome for this iteration

Make generated work more accurate, consistent and professionally useful; identify
where latency and API consumption occur; improve the core user workflow. The
skill models professional decision-making, not just an output format. Faster
output is useful only if grounding and usability remain acceptable.

## Responsibilities

| Owner | Primary work | Concrete deliverable | Coordination / dependency |
| --- | --- | --- | --- |
| Yuqing Wu (Frank) | Generation rules, backend harness, data contracts and integration | Shared professional method; Structure/Ideas/Storyboard integration; standard storyboard; runnable intermediate candidate | Agree contracts with Natalie and Belinda; unblock Andrea with a frozen, traceable harness |
| Andrea Fernandez-Cruz | Model / API testing | Current performance baseline; controlled model comparisons; per-module quality, latency, success and usage/cost report; configuration recommendation | Setup and baseline work start now; formal comparison starts after harness merge into the agreed testing baseline and version freeze |
| Belinda | UI/UX design | Research → Ideas → Production flow audit; key screen/state designs; progress, scrolling, reload/reopen, recovery and storyboard display specification | Design in parallel; align output/status contracts with Frank before implementation |
| Natalie | QA metrics and acceptance | Rubric, annotated expected behaviors, deterministic checks, human review procedure and regression report | Start with Frank before harness implementation; score the same outputs Andrea measures |
| Haoyang | Test materials and creative scenarios; non-coding | Organized video corpus with source/usage notes, language/format, context and test purpose; factual observations distinguished from interpretation | Supply common inputs to Natalie and Andrea; keep development and held-out material separate |

Belinda's design delivery is not automatically a completed UI implementation.
Frank coordinates implementation of the highest-priority fixes; engineering
capacity for remaining UI work must be assigned before promising completion.
Names above follow the latest owner assignment; no identity mapping to earlier
team lists is assumed.

## Sequence and handoffs

**Phase 1 — Start together.** Frank and Natalie agree output requirements and
failure examples. Haoyang prepares the corpus. Andrea verifies installation and
records the v0.7.5 stage-time baseline. Belinda audits task completion and recovery.
Exit: common inputs, rubric draft, known defects and interface requirements.

**Phase 2 — Harness first.** Frank implements shared handling, then Structure,
Ideas and Storyboard. Natalie checks integrity and semantic cases continuously.
Belinda aligns result/status design with contracts. Exit: reproducible artifacts,
version/usage records, partial-result behavior and bounded revision.

**Phase 3 — Controlled testing and focused UI implementation.** Merge the tested
harness into the agreed testing baseline and freeze the candidate version. This
plan does not itself authorize a main merge. Andrea compares configurations without simultaneously changing prompts;
Natalie evaluates the same results. Implement agreed usability fixes in parallel.
Exit: interpretable quality/speed/cost findings, not just impressions.

**Phase 4 — Integrate and accept.** Frank integrates fixes; the team exercises real
user tasks and publishes a candidate with test evidence and known limitations.
No fixed calendar deadline or extra meeting time is invented here. The meeting's
“tomorrow after 8:00” needs its own date/time clarification before scheduling.

## Confirmed generation behavior

### Shared professional method

Consider the communication job, audience situation/motivation, product value and
proof, attention/persuasion mechanism, brand fit, medium, execution and counter-
evidence. Use existing information; research relevant facts when tools permit;
ask users only material choices. Flag strategic contradictions with alternatives,
but do not silently change the goal. Show concise rationale, assumptions and
tradeoffs; detailed explanation is expandable.

### Structure

Explain presentation → plausible viewer interpretation → communication role,
including evidence and inferential gaps. Keep supported interpretations parallel,
without selecting an official primary intent. Missing critical visuals permit a
limited hypothesis, not a method card depending on the missing observation.
Methods should be few and specific: original choice, mechanism, evidence,
conditions and what cannot simply be copied. One targeted revision; omit cards
that still fail. Preserve usable analysis even when no methods qualify.

Continue the previously confirmed graph-first interaction, bounded contextual
research, evidence/time navigation, preservation of user corrections, and selected
handoff into Ideas. Do not add a mandatory manual graph-editing workflow.

### Ideas

Offer substantively different concepts/mechanisms/perspectives, not fixed faithful
versus reorganized A/B routes. Each proposal contains a concept, opening,
mechanism, narrative beats, product integration and execution conditions.
Incomplete audience/goal information can be an explicit assumption; product facts
cannot be invented. Adapt or discard an unsuitable reference method with a reason.
One targeted revision; fewer qualifying directions, including one, are acceptable.

Experimental concepts may remain if labeled with goal hypotheses and validation
methods. They can proceed to Storyboard after explicit approval, preserving that
status. Experimental effectiveness is different from unsupported product claims.

### Storyboard

Use one shared audiovisual plan for live action or AI generation; mode-specific
instructions are optional additions. One row represents one shot/generation
segment. The main table has **Shot / Time / Visual / Audio** only. Beat/purpose,
photography, materials and resources belong in linked supporting notes.

Design ideal execution first and list required resources; subsequently compress
against actual conditions. Do not silently assume unavailable resources exist or
ignore known limits. Fit the requested duration; propose necessary cuts, obtaining
confirmation for core-message changes. After at most one targeted repair, unresolved
critical issues produce a clearly marked, exportable discussion draft—not a
production-ready plan. Estimated timing is not measured audio timing.

## Acceptance evidence and workstream priorities

The following evidence checklist is a **recommended release plan**, not a set of
already measured results or fixed numeric targets:

- Every factual claim and source link is traceable to its correct input type and
  version; missing visual coverage is visible downstream.
- More than one defensible interpretation can be retained; generic method cards
  and unsupported methods do not pass merely because their schema is valid.
- One qualifying Idea can be delivered; an experimental Idea retains its status
  through explicit approval, storyboard and export.
- Storyboard view is compact while technical detail remains accessible; overlong
  dialogue, continuity defects and core-message cuts are handled explicitly.
- Each generation operation has accountable attempts, bounded repair, meaningful
  progress/failure states and preserved saved work.
- Andrea and Natalie can associate quality, latency and usage with the exact same
  inputs, harness version, model settings and cache condition.
- Belinda's task scenarios include scrolling at relevant window sizes, locating
  current progress, retrying an eligible failure, reopening work and exporting a
  discussion draft without losing its warning. Exact reload behavior is a design
  task, not permission to duplicate an active paid request.

Use the [quality rubric](../../../skills/video-anatomy-professional-generation/references/QUALITY.md) to propose scores and thresholds.
Keep model judgments separate from human assessment and source facts. Existing
software tests do not prove creative quality. The observed slowness may come from
extraction, model latency, research, duplicate work, queues or rendering; measure
before attributing it to one cause.

## Scope, setup and constraints

- All development starts from the shared v0.7.5 runtime baseline plus the v0.7.6 skill specification; inspect current main
  before creating the next implementation branch. Do not reuse an old branch blindly.
- Current non-audio configuration remains GPT-6; Whisper is the approved speech
  exception. Model availability must be verified per account. No paid calls are
  authorized or run by this document handoff.
- The USD 3 allowance belonged to Cloud experiments. Do not reinstate it as a
  client spending cap. Track actual known/unknown usage transparently.
- The professor ZIP is not environment-free: Macs still need Python 3.12 and
  FFmpeg, first-run internet access and their own compatible OpenAI API account.
- Multi-video/library processing, integrated video generation and fine-tuning are
  future work, not compulsory deliverables in this intermediate iteration. If a
  generated example is needed, an external-tool storyboard demonstration can be
  explored separately and identified as not yet integrated.
- No deployment or automatic main merge follows from accepting the skill.

## Start here for implementation

Read [skill/SKILL.md](../../../skills/video-anatomy-professional-generation/SKILL.md), [HARNESS_INTEGRATION.md](HARNESS_INTEGRATION.md)
and [DECISIONS.md](DECISIONS.md). Crucially, v0.7.5 requires exactly two Ideas and
rejects some incomplete production outputs; prompts alone cannot implement the
new one-Idea and exportable-discussion-draft behavior. Frank must coordinate
contracts, persistence and UI consumers together.
