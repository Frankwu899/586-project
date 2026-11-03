# Video Anatomy v0.7.6 — QA Rubric & Acceptance Criteria

**Project:** COMM 586 — Video Anatomy   
**Specification:** Professional Generation Skill v0.7.6  
**Scope:** Structure, Ideas, Storyboard, and Cross-Module Quality Assurance

---

## 1. Purpose and Scope

This document establishes a structured quality assurance framework for evaluating the AI-generated outputs of Video Anatomy.

The framework assesses whether generated content is accurate, evidence-grounded, professionally useful, consistent with approved user inputs, and appropriately labeled for its intended stage of use.

It covers three primary modules:

- **Structure:** Analysis of source-video communication logic and transferable creative mechanisms.
- **Ideas:** Development of differentiated, product-relevant creative directions.
- **Storyboard:** Translation of an approved creative direction into an actionable audiovisual production plan.

The rubric builds on the existing M9 evaluation framework and incorporates the professional generation requirements defined in v0.7.6.

It separates output quality requirements from application implementation status. A specification requirement does not, by itself, establish that the corresponding application behavior has been implemented or tested.

## 2. Quality Evaluation Framework

Quality assurance is conducted across three complementary evaluation layers.

### 2.1 Deterministic Integrity

Deterministic checks verify objectively testable requirements, including:

- Required output structure and content fields
- Valid evidence identifiers and source revisions
- Correct input and approval references
- Consistent shot timing and target duration
- Preservation of required language and approved wording
- Compliance with the targeted quality-repair limit
- Consistency between artifact status, visible warnings, and exported content

A structurally valid output is necessary for trusted downstream use but does not independently establish semantic quality.

### 2.2 Semantic Quality

Semantic evaluation assesses the accuracy, reasoning, and professional quality of generated content.

Key dimensions include evidence grounding, interpretation quality, communication mechanisms, audience and task fit, creative differentiation, production fidelity, and execution feasibility.

Human review serves as the reference evaluation method during rubric calibration. Automated semantic evaluation may support review but must not be treated as independent ground truth.

### 2.3 Usefulness in Context

Contextual usefulness evaluates whether outputs help users complete their intended creative tasks.

A useful Structure analysis should clarify communication mechanisms. An Ideas output should support meaningful comparison and approval. A Storyboard should support production planning while making resource needs and unresolved issues visible.

Output validity, professional quality, production feasibility, user approval, and demonstrated advertising effectiveness are distinct properties and must not be conflated.

---

## 3. Human Quality Scoring

The framework adopts the 0–3 anchored scale described in the v0.7.6 quality specification as its working evaluation method.

| Score | Classification | Evaluation Anchor |
|---|---|---|
| 0 | Absent or Invalid | Required content is absent, contradicted by evidence, or unusable for the intended task. |
| 1 | Major Improvement Needed | Content is superficial, weakly supported, or requires substantial correction. |
| 2 | Useful with Limitations | Content is generally useful, with limited and explicitly identifiable weaknesses. |
| 3 | Strong and Usable | Content is specific, well-supported, coherent, and useful for its intended stage. |
| N/A | Not Applicable | The criterion does not apply to the evaluated artifact; the reviewer records the reason. |

Scores are assigned to applicable dimensions individually. Reviewers must provide evidence for low scores and consequential quality judgments.

The scale supports comparative evaluation and reviewer calibration. It does not establish an approved numerical release threshold.

**Critical integrity failures are evaluated independently of numerical scores.** Fabricated claims, invalid evidence references, and approval violations cannot be offset by strong performance in other dimensions.

---

## 4. Structure Module Evaluation

### 4.1 Evaluation Objective

Structure should explain the original video's communication logic through supported observations, plausible interpretations, and transferable creative mechanisms.

The module should preserve uncertainty, distinguish source modalities, and avoid inventing evidence or strategic intent.

### 4.2 Evaluation Criteria

| ID | Dimension | Expected Quality Standard |
|---|---|---|
| S-QA-01 | Evidence Grounding | Claims and observations are traceable to appropriate source evidence. |
| S-QA-02 | Modality Accuracy | Visual observations, speech, on-screen text, user context, and external research are correctly distinguished. |
| S-QA-03 | Interpretation Quality | Analysis explains the relationship between creative presentation, plausible viewer understanding, and communication role. |
| S-QA-04 | Uncertainty Handling | Inferential judgments are identified, and supported alternative interpretations remain available without unsupported ranking. |
| S-QA-05 | Contextual Accuracy | Audience, brand, product, and external context claims remain within the available evidence. |
| S-QA-06 | Graph Coherence | Nodes and relationships explain meaningful communication logic rather than chronology alone. |
| S-QA-07 | Method Transferability | Method cards identify the original choice, reusable mechanism, applicability conditions, limitations, and unsupported elements that must not be copied. |
| S-QA-08 | Evidence Coverage | Missing or incomplete modalities are disclosed, and dependent conclusions are appropriately qualified. |
| S-QA-09 | Revision Integrity | User corrections, evidence references, and accepted local revisions remain consistent. |
| S-QA-10 | Practical Usefulness | The analysis provides specific insights that can inform subsequent creative work. |

### 4.3 Required Behaviors

- A video-based analysis may remain useful even when contextual research is incomplete.
- Interpretations must not be presented as direct observations.
- Parallel interpretations must not be forced into a single definitive explanation.
- Method cards must be supported by sufficient evidence and clearly stated applicability conditions.
- Zero qualifying method cards is a valid outcome when the available evidence does not support a transferable method.
- One targeted quality revision is permitted. Method cards that remain unsupported should be removed while preserving valid analysis.
- Source evidence and uncertainty must be retained when selected analysis elements are transferred into Ideas.

### 4.4 Critical Failure Examples

- Claiming an unseen action occurred based only on spoken narration.
- Inventing a source event, timestamp, or evidence reference.
- Presenting an unsupported demographic assumption as a verified targeting strategy.
- Extracting a transferable method whose essential premise is not supported by the source.

---

## 5. Ideas Module Evaluation

### 5.1 Evaluation Objective

Ideas should develop assessable creative propositions that preserve the user's communication goal, accurately represent the product, and provide meaningful creative differentiation.

Quality takes priority over producing a fixed number of directions.

### 5.2 Evaluation Criteria

| ID | Dimension | Expected Quality Standard |
|---|---|---|
| I-QA-01 | Task and Brand Fit | The direction addresses the communication objective and available brand/product context. |
| I-QA-02 | Product Fact Integrity | Product features, benefits, prices, and claims remain consistent with approved information. |
| I-QA-03 | Assumption Transparency | Missing audience or objective information is handled through explicit, bounded assumptions when generation can proceed. |
| I-QA-04 | Creative Differentiation | Multiple directions differ meaningfully in central concept, persuasion mechanism, or narrative perspective. |
| I-QA-05 | Mechanism Quality | Each direction explains how its creative execution may produce the intended audience response. |
| I-QA-06 | Proposal Completeness | Each direction contains a proposition, opening example, mechanism, narrative beats, product integration, and execution conditions. |
| I-QA-07 | Reference Adaptation | Selected Structure methods are adapted or rejected according to their suitability for the new product and task. |
| I-QA-08 | Experimental Transparency | Experimental directions retain an explicit label, objective hypothesis, and validation method. |
| I-QA-09 | Qualified Output Selection | Only qualifying directions are retained, without padding the output to meet a fixed count. |
| I-QA-10 | Approval Integrity | Only an explicitly approved saved direction revision is eligible for production handoff. |

### 5.3 Required Behaviors

- Creative directions are not restricted to a fixed faithful/reorganized A/B formula.
- A different hook, tone, or wording alone does not establish meaningful differentiation.
- One qualified direction is acceptable.
- If no direction qualifies, the output should identify the specific information or quality gap rather than manufacture a successful result.
- Product facts must not be invented to strengthen a concept.
- Experimental directions may proceed to Storyboard following explicit approval, while retaining their experimental status and validation points.
- A proposed revision does not automatically inherit approval from an earlier direction revision.
- One targeted quality revision may address weak or duplicate candidates.

### 5.4 Critical Failure Examples

- Introducing an unsupported product capability as a factual advertising claim.
- Presenting two paraphrases of the same concept as meaningfully different directions.
- Treating an unvalidated experimental concept as proven effective.
- Passing an unapproved creative direction into Storyboard.

---

## 6. Storyboard Module Evaluation

### 6.1 Evaluation Objective

Storyboard should translate the exact approved creative direction into a coherent audiovisual production plan while preserving creative intent, approval boundaries, factual accuracy, and execution constraints.

### 6.2 Evaluation Criteria

| ID | Dimension | Expected Quality Standard |
|---|---|---|
| P-QA-01 | Approval Fidelity | The storyboard uses the exact approved creative direction revision and compatible brief. |
| P-QA-02 | Table Structure | The main readable table contains Shot, Time, Visual, and Audio. |
| P-QA-03 | Shot Granularity | Each row represents one bounded shot or generation segment. |
| P-QA-04 | Narrative Continuity | Shots connect coherently to the approved narrative beats and preserve the core communication message. |
| P-QA-05 | Visual Specificity | Subject, action, necessary product details, and on-screen text are described clearly. |
| P-QA-06 | Audio Integrity | Dialogue, voice-over, sound cues, and silence are represented accurately and separately from visual content. |
| P-QA-07 | Timing Feasibility | Planned duration accounts for realistic action, reading, and estimated speech time. |
| P-QA-08 | Production Requirements | Required resources, assumptions, continuity concerns, and practical dependencies are identified. |
| P-QA-09 | Creative Fidelity | Resource compression or timing changes do not silently alter the approved core message. |
| P-QA-10 | Status Accuracy | Unresolved critical issues remain visible and prevent an unsupported Production Ready designation. |
| P-QA-11 | Export Integrity | Discussion Draft warnings, experimental labels, and unresolved decisions remain visible in exports. |
| P-QA-12 | Practical Usefulness | The storyboard supports informed production discussion and execution planning. |

### 6.3 Required Behaviors

The main storyboard table uses four columns:

| Shot | Time | Visual | Audio |
|---|---|---|---|
| Stable shot identifier | Planned start–end or duration | Observable subject, action, framing, and necessary screen text | Dialogue, voice-over, sound cues, music, or silence |

Supporting notes should separately capture narrative beats, photographic intent, resource requirements, continuity, source references, assumptions, and unresolved decisions.

Additional requirements include:

- Production planning begins with the intended creative realization and identifies the resources required.
- Missing resources must not be represented as available.
- Speech timing must be identified as estimated unless actually measured.
- When the target duration cannot accommodate the approved message, proposed cuts and tradeoffs must be communicated.
- Changes affecting the core message require user confirmation.
- One targeted quality repair is permitted.
- If critical issues remain, the output must retain a clearly labeled Discussion Draft rather than claim production readiness.
- Unsupported claims must be flagged as invalid, not presented as usable advertising copy.
- Experimental status, hypotheses, and validation points must remain attached to the approved direction through Storyboard and export.

### 6.4 Critical Failure Examples

- Generating production content without the required approved direction.
- Silently changing the approved message to fit the target duration.
- Combining multiple distinct shots into one ambiguous row.
- Presenting unrealistic dialogue timing as verified.
- Marking an unresolved Discussion Draft as Production Ready.
- Exporting a draft without its relevant warnings.

---

## 7. Cross-Module Quality and Integrity

The following standards apply throughout the generation workflow.

| ID | Requirement | Acceptance Criterion |
|---|---|---|
| X-QA-01 | Evidence Traceability | Important factual claims and source-dependent interpretations have appropriate supporting references. |
| X-QA-02 | Source Version Integrity | Generated artifacts preserve the correct source and revision relationships. |
| X-QA-03 | Approved Information | Product facts, fixed wording, and user-approved constraints remain intact. |
| X-QA-04 | Language Consistency | Generated content follows the applicable language settings while preserving fixed wording and original-language evidence. |
| X-QA-05 | Repair Control | Quality repair follows the one-targeted-revision limit for the module operation. |
| X-QA-06 | Uncertainty Transparency | Assumptions, unsupported claims, incomplete evidence, and unresolved decisions are distinguished. |
| X-QA-07 | Status Consistency | Artifact status accurately reflects quality, approval, experimental state, and production readiness. |
| X-QA-08 | Export Consistency | Exports retain applicable warnings, versions, and status information. |
| X-QA-09 | Revision Continuity | Accepted user changes and valid prior work are preserved across revisions. |
| X-QA-10 | Workflow Boundaries | Research, creative approval, and production handoff do not introduce unauthorized mandatory steps. |

### 7.1 Module-Specific Failure Handling

| Module | Required Outcome After Unsuccessful Targeted Repair |
|---|---|
| Structure | Remove failing method cards; preserve supported graph content and explain a zero-card outcome when applicable. |
| Ideas | Retain only qualifying directions; identify the gap when no direction qualifies. |
| Storyboard | Retain a clearly labeled, reviewable Discussion Draft with unresolved issues and warnings. |

A readable draft must not be confused with trusted structured data when its schema or references are invalid.

---

## 8. Evaluation Methods

### 8.1 Deterministic Evaluation

Objective checks cover schema compliance, required content, valid identifiers, source versions, approval references, timestamp consistency, revision counts, and artifact status.

Deterministic validation should be performed before semantic review whenever practical.

### 8.2 Human Semantic Evaluation

Human reviewers evaluate evidence support, interpretation quality, creative differentiation, contextual relevance, transferability, and production usefulness.

Each applicable dimension receives an anchored score with supporting observations.

### 8.3 Contextual Usefulness Evaluation

Usefulness is evaluated through whether the artifact supports its intended user decision:

- Structure: understanding and transferring communication mechanisms.
- Ideas: comparing, refining, and approving creative directions.
- Storyboard: understanding execution requirements and unresolved production decisions.

No claim of measured advertising effectiveness should be inferred solely from model-generated content or reviewer preference.

---

## 9. Test Execution and Evidence Recording

### 9.1 Test Metadata

Each recorded evaluation should identify, where applicable:

| Field | Description |
|---|---|
| Test ID | Unique test case identifier |
| Module | Structure, Ideas, or Storyboard |
| Input ID | Source video or task identifier |
| App Version | Tested application commit or release |
| Skill Version | Applied generation specification |
| Model Configuration | Model identifier and relevant settings |
| Input Revision | Saved brief, evidence, and approval references |
| Language | Applicable generation and source language |
| Cache Mode | Cold or warm cache when relevant |
| Reviewer | Person completing the evaluation |
| Execution Date | Date of the recorded test |
| Output Reference | Location of the saved output |
| QA Findings | Scores, evidence, defects, and status |

### 9.2 Evaluation Sequence

1. Verify the test input, source coverage, and application configuration.
2. Record the exact application, skill, and model versions.
3. Generate or retrieve the target module output.
4. Preserve the output and relevant evidence references.
5. Execute applicable deterministic checks.
6. Score semantic quality using the anchored rubric.
7. Evaluate contextual usefulness.
8. Record failures, uncertainty, and supporting observations.
9. Identify the relevant defect source and severity.
10. Reevaluate affected criteria after a documented correction.

### 9.3 Defect Source Classification

Reviewers should distinguish between:

- Source extraction and modality coverage defects
- Evidence and reference integrity defects
- Generation and reasoning defects
- Schema and validation defects
- Approval and workflow defects
- User interface and export defects
- Environment or configuration defects

This classification prevents upstream extraction errors from being incorrectly attributed to generation reasoning.

---

## 10. Defect Severity and Acceptance Interpretation

For reporting consistency, the following descriptive severity categories are used.

| Severity | Definition | Example |
|---|---|---|
| Critical | A defect that invalidates essential factual, evidence, approval, or readiness integrity. | An invented product claim presented as verified. |
| Major | A defect that substantially limits the artifact's intended use. | A creative direction lacks a usable mechanism or product integration. |
| Minor | A localized issue that does not invalidate the central artifact. | A small clarity or presentation issue. |
| Informational | A documented observation or improvement opportunity without an established requirement violation. | An optional presentation enhancement. |

These categories support consistent defect reporting. Their mapping to final release decisions remains a separate engineering and team acceptance decision.

### 10.1 Evaluation Status

| Status | Meaning |
|---|---|
| Pass | Observed behavior satisfies the applicable confirmed requirement. |
| Fail | Observed behavior violates the applicable confirmed requirement. |
| Pending Implementation | The required behavior is not implemented in the tested version. |
| Blocked | A documented dependency prevents execution. |
| Not Tested | No test execution has been recorded. |
| Needs Review | Available evidence is insufficient for a supported conclusion. |
| N/A | The requirement is not applicable to the case. |

A high numerical score must not override an invalid reference, fabricated factual claim, or approval failure.

---

## 11. Regression and Model Comparison

Regression evaluation should preserve the relevant test configuration and identify the variable being compared.

For generation-model comparisons, use the same verified upstream evidence. For full-pipeline comparisons, evaluate extraction differences separately.

When comparing prompt or skill versions, hold the model configuration constant where feasible. When comparing models, hold the prompt and task configuration constant.

The evaluation should include:

- Clean and incomplete source evidence
- Horizontal and vertical advertising videos
- Chinese and English content
- Multiple plausible interpretations
- Unsupported product claims
- Original Ideas without a selected reference
- Experimental creative directions
- Overlong dialogue and target-duration conflicts
- Approval, revision, and draft-status boundaries

Development and held-out test cases should remain distinguishable. Held-out examples should not be used repeatedly to tune generation rules.

Regression reports should document the tested versions, observed changes, unresolved defects, and limitations of the sample.

Small sample sizes must be reported transparently. Unmeasured performance improvements or advertising effectiveness must not be claimed.

---

## 12. Scoring Governance and Release Decisions

This rubric establishes the evaluation dimensions, working scoring anchors, failure categories, and evidence-recording requirements for the QA process.

The v0.7.6 source specification does not establish numerical release thresholds, mandatory weighting formulas, or minimum test corpus sizes.

Accordingly:

- Individual criterion scores are reported with supporting evidence.
- Critical integrity failures are reported separately from average scores.
- Reviewers document disagreements and calibration decisions.
- Acceptance recommendations distinguish confirmed requirements from implementation readiness.
- Release decisions are made using verified test evidence and the team's agreed acceptance policy.

The rubric must not be interpreted as independently certifying an application release.

---

## 13. QA Deliverable Integration

This rubric provides the evaluation criteria for the supporting QA artifacts maintained in the project's evaluation documentation.

| Artifact | Purpose |
|---|---|
| `QA_RUBRIC_v0.7.6.md` | Defines evaluation dimensions, scoring anchors, and acceptance criteria. |
| `EXPECTED_BEHAVIORS.md` | Maps test scenarios to expected and unacceptable behaviors. |
| `DETERMINISTIC_CHECKS.md` | Specifies objective validation rules and expected outcomes. |
| `HUMAN_REVIEW_PROCEDURE.md` | Defines reviewer instructions, calibration, and evidence recording. |
| `QA_TEST_RESULTS.csv` | Records actual execution-level scores, defects, and statuses. |
| `REGRESSION_REPORT.md` | Summarizes verified results, retesting, and acceptance recommendations. |

The rubric is a quality evaluation specification, not an execution report. Test results and regression conclusions must be supported by actual recorded observations.

---

## 14. Reference Documentation

The evaluation framework is aligned with the following project materials:

- `docs/evaluation/m9-offline-and-live-rubric.md`
- `QUALITY.md`
- `STRUCTURE.md`
- `IDEAS.md`
- `STORYBOARD.md`
- `EXAMPLES.md`
- `DECISIONS.md`
- `TEAM_HANDOFF.md`
- `HARNESS_INTEGRATION.md`
- `VALIDATION_REPORT.md`

These materials define the relevant evaluation principles, module behaviors, examples, and implementation boundaries.

---

## 15. Document Scope

This document establishes the QA rubric and acceptance criteria for the project's professional generation workflow.

It provides a consistent basis for expected-behavior testing, deterministic validation, human review, defect reporting, and regression evaluation.

Completion of this rubric does not imply that the corresponding application implementation or regression testing has passed QA.
