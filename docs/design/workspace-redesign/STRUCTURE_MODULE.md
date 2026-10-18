# Structure: agent-driven video reasoning

Status: consolidated design proposal for owner review, based on confirmed S1-S11.
This document does not authorize implementation. It supersedes any earlier
suggestion that users should maintain a manual structure-graph editor or launch
background research separately.

## Product outcome

Help a user understand how a video's parts work together and which methods may
transfer to another creative task. Research has two complementary tabs:

- Timeline: inspect what appears or is said, and where it appears.
- Structure: explain the relationships among observations, narrative choices,
  audience/context hypotheses and communication intent.

Structure is driven by a dedicated product agent. New creative concepts and
scripts belong to Ideas. The user should receive useful analysis before supplying
extra context, and should not have to repair nodes or edges to obtain value.

## User flow

1. Start analysis for the uploaded video. Reuse available source observations.
2. Show a video-based logic graph as soon as a coherent draft is available, with
   analysis/research state near the work. No mandatory upfront interview.
3. The agent identifies relevant background gaps and researches them automatically.
   Scope is limited to facts or context that materially affect this video's
   interpretation, rather than a default market or competitor report.
4. Signal research-driven updates clearly. A failed lookup does not invalidate
   useful source-video analysis or block other project work.
5. Select a node to inspect evidence, jump to Timeline, ask a question, supply
   context or request a local reconsideration. These are optional exploration and
   feedback, not required labeling work.
6. Select nodes or transferable methods to bring into Ideas with their sources
   and applicability conditions. Selecting the complete analysis is also possible.
   Carrying research into Ideas does not automatically create or approve a concept.

## Primary surface

The default view is a persuasion/narrative logic graph with concise labels.
Relationships explain how content introduces, supports, contrasts with, reveals
or connects to other content. Do not force every video into hook/feature/CTA
or treat chronological adjacency alone as a meaningful logical relationship.

Node selection opens an inspector containing its explanation and supporting
video moments or external sources. Source-video nodes may point to several
moments; external background must not be assigned invented video timestamps.
Use the temporal precision actually supported by the analysis. Nodes linked to
sampled observations must not imply exact continuous scene coverage.

Distinguish observed video content, attributed source claims, user-supplied
context and analytical inference. Audience, intent and effectiveness explanations
must not be presented as established facts. Research can support an inference
without proving official targeting or measured campaign impact.

The owner has not selected a special parallel-hypothesis layout. Keep visual
clutter low and avoid adding one as a purported confirmed requirement.

## Agent responsibility

The agent owns initial grouping, relationship construction, background-gap
identification, focused retrieval, reasoning synthesis and quality checks.
It should explain why a method might transfer and its conditions, rather than
copying surface motifs such as Guandan into every unrelated brand.

Engineering recommendations to realize that behavior:

- Link meaningful claims and relationships to evidence, not just attach a general
  source list to the graph. Preserve analysis revision and source identity.
- Check entity matches, dates, source relevance and conflicting claims. A brand
  assertion, interview statement or show appearance is not independent proof.
- Check graph coherence and unsupported leaps before surfacing results. A model's
  self-check is a useful guard, not an independently measured accuracy guarantee.
- Apply bounded retrieval and repair attempts within the same run budget. Do not
  recursively search or regenerate without a stopping condition.

These are proposed mechanisms, not existing capabilities or selected providers.
The current application has no Structure service or retrieval tool integration.

## User control without a manual-editor burden

Do not prioritize a canvas editor for manually creating, splitting, merging or
rewiring nodes. Optional natural-language feedback lets the agent do that work.

Preserve user-supplied context and previously adopted corrections. If new research
or local reanalysis conflicts with them, offer a previewable change to the affected
material. Do not silently overwrite it or require whole-graph approval. Normal
initial generation must not turn into a stream of approval dialogs. Preserve
provenance so an adopted user hypothesis does not become a verified external fact.

## Completion and stopping

At the configured cost/time limit, stop and show completed useful portions.
There is no Continue research, Go deeper or quota-extension action. Do not pop up
an obligatory questionnaire, silently extend work or ask the user to finish it.

A quiet partial-result status is recommended when coverage is incomplete; it
must not claim that all research succeeded. Do not fill absent results with
guesses or display dangling graph dependencies as complete. Optional questions
about delivered results remain part of S2; they must not be used as a disguised
automatic continuation of the exhausted research run.

Exact budgets, selected models, retrieval provider and elapsed-time targets are
unresolved engineering choices. They require realistic cost/capability checks
before implementation; this design makes no promised price or latency claim.

## Model quality and training

Confirmed goal: improve the model/agent rather than shifting analysis quality
control to end users. The following sequence is recommended, not a claim that a
training job has been approved or completed:

1. Define an evaluation rubric and a diverse, permitted example set. The two
   discussed videos are seed cases, not a sufficient training or test corpus.
2. Record source-grounded interpretations, alternative defensible explanations,
   errors and transferable methods. Avoid treating one subjective interpretation
   as the sole correct answer; do not require ordinary users to label the corpus.
3. Improve prompts/examples, evidence extraction, retrieval and reasoning checks.
   Separate perception failures from reasoning failures before choosing a remedy.
4. Evaluate changes on held-out videos. Measure unsupported claims, useful source
   links, relationship quality, relevant background coverage, transfer usefulness
   and the need for user intervention. Do not invent accuracy thresholds/results.
5. Consider fine-tuning only if persistent errors, suitable data, provider support
   and cost justify it. Evaluation must remain independent of training examples.

No live API calls, training uploads or fine-tuning are performed by this design.

## Acceptance scenarios

- Guandan: identify the shared-interest/activity/product-use relationship while
  retaining audience targeting as inference and not inventing seat rotation.
- Fishing rod: distinguish visual novelty from configuration value; do not turn
  two interchangeable tips into two complete rods or exhibition presence into
  official endorsement. Attribute manufacturing claims to their source.
- An unfamiliar video: produce a useful first analysis without forcing the user
  to identify every cultural reference or manually build a graph.
- Source failure or budget exhaustion: retain completed analysis, indicate its
  scope quietly, and stop without an extra research action or blocked workspace.
- User correction: preserve supplied context and adopted changes while offering
  relevant, reviewable updates rather than rebuilding the whole graph for approval.
- Ideas handoff: selected reasoning retains its evidence and conditions, without
  becoming a new brand claim or an approved production direction automatically.

## Remaining review

Review this synthesis for shared understanding. No further speculative interview
branches are needed before that review. Implementation, real provider evaluation
and any training run remain separate work to be explicitly requested.
