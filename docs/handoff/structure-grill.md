# Structure module: active product interview

Status: discussion only; no application implementation authorized in this round.

## Confirmed owner instructions

- Research has two complementary sub-tabs: a timeline/player and Structure.
- Structure visually explains the uploaded video's logic and relationships.
- The owner requested a dedicated agent to drive the Structure module. Its
  responsibility, interaction model, tools and runtime triggers remain to be
  defined; do not confuse this product agent with a temporary coding sub-agent.
- Continue grilling in this conversation using the requested grill-me skill.
- Every interview question must use the native interactive question UI, not a
  plain-text list. The rule is written into the installed local skills.
- Preserve confirmed Q1-Q3 and subsequent owner decisions; do not restart the
  old interview or infer implementation approval from design discussion.

## Installed interview skill

Entry: `../../.agents/skills/grill-me/SKILL.md`.
Required method: `../../.agents/skills/grilling/SKILL.md`.

The requested page `https://www.aihero.dev/skills-grill-me` returned HTTP 403 in
this environment and was not read. Installation instead uses the author's
`https://github.com/mattpocock/skills` repository, commit
`49dd158d1076134a641b33efb035946536778336`, paths
`skills/productivity/grill-me/SKILL.md` and
`skills/productivity/grilling/SKILL.md`. Both files and the accompanying author
documentation were read. Unmodified source snapshots, MIT licenses and provenance
manifests are retained alongside the customized skills.

The wrapper now supports direct file reading in Codex when no Skill invocation
tool exists. The underlying method replaces Markdown question formatting with
`functions.request_user_input_async` in Default mode, retains decision-dependent
rounds, and explicitly rejects silence/preselected options as approval. This is
a project-local installation in the current Cloud workspace, not a global
installation on the owner's Mac. Automatic discovery by a fresh Codex process
has not been tested; the current session has read and applied the files directly.

## First round: pending answers

These questions were sent together through the interactive UI. Do not treat the
recommended options as decisions, and do not resend while they remain pending.

- S1: Responsibility boundary: explain structure plus transferable methods
  (recommended), explain only, or also generate target-brand creative work.
- S2: Interaction: generate an initial graph then allow node-specific questions,
  corrections and reanalysis (recommended), interview first, or direct editing only.
- S3: Missing external context: mark gaps and research after an explicit user
  action (recommended), automatically research during analysis, or no retrieval
  in the first version.

After answers, resolve only newly available decisions: required outputs and
graph semantics, source/uncertainty presentation, user edits and regeneration,
relationship to Timeline, background-source policy, agent tool and cost limits,
partial failure behavior, and handoff to Ideas. Do not assume all of those need
separate questions if existing evidence or earlier answers settle them.

## Case studies already discussed

- Guandan recording: shared interest, vehicle use scene and an invitation to
  contribute tips. The user's cultural/demographic and product context is
  distinct from observed video facts and independently verified sources.
- DreamCatcher fishing rod video: unusual handle, trade-show context, hands-on
  remarks, interchangeable-tip value explanation, brand manufacturing claims
  and a shop CTA. Two tips do not establish two complete rods or a buy-one-get-one
  offer. Exhibition presence does not establish official endorsement.
- Both chat samples used inspected frames and readable subtitles with approximate
  segmentation; they are illustrative product-analysis examples, not results of
  an implemented Structure agent or independently transcribed full audio.

## Scope and checks

Read-only implementation review found no product Structure service or graph
contract. Existing recognition provides frame-based visual/OCR/speech events,
IDs, revisions and local interpretations (`backend/app/models.py`,
`backend/app/providers/recognition.py`). The creative provider constrains
citations to supplied event IDs, a useful foundation rather than a Structure
implementation. Current transport has no external search tools
(`backend/app/providers/transport.py`). Existing correction APIs also do not
support editing structural relationships. A temporary review sub-agent verified
these facts; it is separate from the proposed product agent.

This round changes only local interview skills, their provenance, AGENTS.md and
this handoff. No application code, paid API, model training, deployment or main
merge. Skill entry/dependency existence, preserved upstream hashes, local
interactive-tool rules and whitespace are checked before delivery.
