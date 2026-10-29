# Generation quality and evaluation

Owner-confirmed behavior: grounding, professional usefulness, explicit uncertainty,
meaningful differentiation, controlled revision and truthful partial/draft status.
The scoring scale, test design and instrumentation below are **proposals for
Natalie and Andrea to calibrate**, not agreed numerical release thresholds or
measured improvements. No model can certify its own advertising effectiveness.

## Check in three layers

1. **Deterministic integrity:** supported schema, required content, valid IDs and
   source revisions, approved-direction reference, allowed claims, time ordering
   and duration, language settings, revision count, and status/export consistency.
   A failed reference cannot be excused by a high semantic score.
2. **Semantic quality:** whether cited evidence actually supports the explanation;
   whether the mechanism is specific and useful; whether candidate ideas differ;
   whether the storyboard faithfully realizes the direction. Human review is the
   reference during calibration. An optional model critic is an aid, not ground truth.
3. **Usefulness in context:** a user can interpret the result, compare or approve
   a direction, and identify what is required to produce it. Evaluate this with
   observed tasks and feedback; do not infer it from JSON validity.

## Proposed anchored scale for human review

Use 0 = absent/invalid; 1 = superficial or requires major correction;
2 = useful with limited, stated weaknesses; 3 = specific, well-supported and
usable for its intended stage. Score applicable dimensions only; use N/A with a
reason. Do not average away an invented claim, broken citation or approval failure.
Natalie should calibrate examples and acceptance cutoffs with Frank before the
formal model comparison. Report disagreement, not invented evaluator consensus.

| Dimension | Weak example | Stronger evidence of quality |
| --- | --- | --- |
| Grounding | Transcription treated as visual proof | Claims use the correct modality, source type and exact revision |
| Mechanism | “This creates engagement” | Explains creative choice, plausible interpretation, communication role and inferential gap |
| Audience/context | A demographic stereotype | A supported or labeled situational motive and relevant boundary |
| Transferability | “Use a hook” | Concrete mechanism, original choice, conditions and counterexample |
| Task/brand fit | Interesting but unexplained connection | Clear task rationale, or explicit experimental hypothesis and validation plan |
| Differentiation | Same story with different opening words | Different central idea, mechanism or perspective |
| Production fidelity | Adds a new product promise | Preserves exact approved message and flags proposed core changes |
| Executability | One dense row contains several shots | Bounded shots, plausible timing, consistent objects and explicit resource needs |
| Transparency/usability | Long rationale hides a missing premise | Concise rationale, visible uncertainty and actionable next step |

## Failure and repair policy

Evaluate the initial artifact and, if required, one targeted revision. Keep the
revision focused on named defects; preserve validated work and user changes.
A repair is not a full new analysis/search cycle. Do not automatically research
more or keep retrying because the artifact is still imperfect.

| Module | After one unsuccessful targeted revision |
| --- | --- |
| Structure methods | Remove failing cards; retain supported graph content. Zero cards is acceptable with a reason. |
| Ideas | Retain qualifying directions only, including one. If none qualify, identify the specific gap rather than manufacture success. |
| Storyboard | Keep a marked discussion draft, with affected shots and unresolved decisions visible. Export may be allowed for discussion, never labeled ready. |

Strategic uncertainty is not automatically a defect. Experimental Ideas can meet
quality criteria and proceed after approval while their effect remains untested.
Schema corruption or fabricated IDs are not exportable as trusted structured data;
a safe draft representation must preserve readable content without claiming valid
references. The host controls persistence and output status.

## Proposed evaluation design

- Freeze app commit, skill/rubric version, model IDs/settings, input/media hashes,
  brief revisions, source analysis and research snapshots, language and cache mode.
- First validate the harness on a small development set. Keep a separate held-out
  set not used to tune rules. Include unfamiliar videos, not only Xiaomi and rod.
- Include clean videos, screen recordings, Chinese/English, missing modalities,
  unsupported claims, multiple plausible interpretations, original Ideas with no
  reference, experimental directions, overlong dialogue and core-message cuts.
- For generation-model comparison, use the same verified upstream evidence.
  For full-pipeline comparison, allow extraction to vary but score it separately.
  This prevents weak visual extraction from being mislabeled as a reasoning failure.
- Separate cold-cache and warm-cache runs. Fix prompts when comparing models;
  fix models when comparing prompt/harness versions. Report small sample sizes.
- For a first human calibration pass, independently score an overlapping subset,
  discuss disagreements, then revise rubric wording. Do not use a single “gold”
  creative answer; define acceptable claims, mechanisms and forbidden leaps.

## Proposed measurement record

For each module/operation: input and output revision; skill and rubric versions;
model/settings; coverage; queue time; processing time; provider latency; time to
first usable result; total time; initial/repair attempts; validation defects;
quality dimensions; final delivery status; cache hits; input/output tokens and
reported audio usage; known estimated cost; unknown cost; provider request IDs
where available. Log no secret keys and avoid raw private media in telemetry.

Report per-module success and partial-result rates with denominators, quality
before/after repair, distributions of latency, and cost per usable result,
including failures and repair calls. Use p50/p95 only with adequate samples;
otherwise show individual runs or ranges. Separate model cost estimates from
provider billing; do not claim measured totals when usage is unknown.

## Performance diagnosis order

Measure upload/media preparation, frame selection, visual/OCR batches,
transcription, research, synthesis, validation/revision and rendering separately.
Check cache behavior, repeated requests and serialization before concluding that
model choice causes all latency. No extra critic or search call should be hidden
inside “generation time.” This specification authorizes no paid evaluation run.
