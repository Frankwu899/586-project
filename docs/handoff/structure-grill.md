# Structure module: active product interview

Status: interview decisions consolidated into a design proposal; no application
implementation authorized in this round. See
`../design/workspace-redesign/STRUCTURE_MODULE.md` for the current synthesis.

## Confirmed owner instructions

- Research has two complementary sub-tabs: a timeline/player and Structure.
- Structure visually explains the uploaded video's logic and relationships.
- The owner requested a dedicated agent to drive the Structure module. Its
  responsibility and basic interaction are confirmed below; detailed tools,
  runtime behavior and research limits remain to be defined. Do not confuse this
  product agent with a temporary coding sub-agent.
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

## First round: confirmed answers

The owner explicitly answered all three interactive questions on 2026-10-18
(America/Los_Angeles). Do not re-ask them.

- S1: Explain the source video's structure and communication logic, and extract
  transferable methods. New-video creative proposals belong in Ideas.
- S2: After the user starts analysis, produce an editable structure graph first.
  The user can select nodes to ask follow-up questions, supply background or
  request local reanalysis. Do not require an upfront interview. S10 later
  clarifies that direct graph editing must not become the main workflow.
- S3: The agent automatically identifies external-context gaps and researches
  them online during analysis. Present sourced context alongside explicitly
  unverified interpretations. The owner selected automatic research rather than
  the recommended separate research action. Do not retain that rejected gate.

S3 supersedes the earlier no-active-search limit for the planned Structure
capability. It is a product-scope decision, not a statement that search exists or
permission to run paid experiments in this discussion. Source provenance,
observation-versus-interpretation separation and actual outcome uncertainty still
apply. Do not make the user provide background that this agent is meant to find.

## Second round: confirmed answers

The owner answered S4-S6 through the interactive UI on 2026-10-18
(America/Los_Angeles), with an additional free-text clarification for S6.

- S4: Automatically research key context that affects interpretation of this
  specific video. Do not default to a broad market or competitor report.
- S5: Show a video-based structure draft and visible research status first.
  Clearly signal subsequent research updates. Research failure must not prevent
  use of the draft or unrelated work.
- S6: Keep analytical judgments explicitly labeled as inferences; do not present
  the analysis as 100-percent-certain facts. The owner did not specifically select
  a parallel-candidate or expandable-alternatives layout; do not infer that UI
  detail from this answer. Distinguish observed content, attributed source claims
  and inferred audience/intent/effect. A source about a general audience does not
  prove this video's official targeting or actual effectiveness.

## Third round: confirmed answers

The owner explicitly selected the recommended answer for S7-S9 on 2026-10-18
(America/Los_Angeles).

- S7: Default to a persuasion/narrative logic graph. Nodes identify corresponding
  source times and can navigate back to Timeline. Do not impose a fixed
  hook/feature/CTA template on every video or turn Structure into another timeline.
- S8: Preserve user edits. New research or local reanalysis proposes previewable,
  adoptable changes to affected material, without requiring whole-graph approval.
  Do not silently overwrite edits or recreate a global review gate. After S10,
  this chiefly protects user-supplied context and adopted corrections; it does
  not authorize building a manual node/edge editor by default.
- S9: Users select nodes or transferable methods to bring into Ideas, carrying
  their evidence and applicability conditions. Selecting the whole analysis is
  also possible. Do not automatically create or approve a new creative direction.

## Fourth round: confirmed answers

The owner answered through the interactive UI on 2026-10-18
(America/Los_Angeles), rejecting the recommended manual-editor scope and
continue-research action.

- S10: Minimize manual editing and intervention. Prioritize model training and
  analysis quality instead of making users repair the graph. Do not include a
  full manual node/edge editor as a confirmed requirement. Node questions,
  optional feedback/context and local agent reanalysis remain available under S2.
  Training is a quality objective, not authorization for an immediate paid
  fine-tuning job or proof that fine-tuning is the appropriate method.
- S11: At a cost/time limit, show only completed portions and stop. Do not offer
  a continue/deeper-research action. Do not interrupt with a questionnaire or
  silently extend the run. Exact numeric limits remain an engineering decision
  after the provider/search approach is selected. A minimal partial-result status
  is proposed to avoid falsely claiming that all research completed.

After this round, synthesize the agreed module behavior into a concrete reviewable
proposal, keeping any remaining engineering recommendations separate from owner
decisions. Do not continue low-value questions or start implementation implicitly.

The synthesis separates confirmed behavior from engineering recommendations
(evaluation, source checking, budget enforcement and training method selection).
Do not reopen S1-S11 unless the owner changes scope. Design acceptance does not
authorize application implementation, paid provider calls or model training jobs.

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
