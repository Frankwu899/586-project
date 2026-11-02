# Video Anatomy v0.7.6 — Human Review Procedure

**Project:** COMM 586 — Video Anatomy  
**Specification:** Professional Generation Skill v0.7.6  
**Scope:** Structure, Ideas, Storyboard, and Cross-Module Human Evaluation  
**Related Documents:** `QA_RUBRIC_v0.7.6.md`, `EXPECTED_BEHAVIORS.md`, `DETERMINISTIC_CHECKS.md`

---

## 1. Purpose

This document defines the human review procedure for evaluating the semantic quality and practical usefulness of Video Anatomy outputs.

Human review complements deterministic validation by assessing qualities that cannot be reliably established through schema checks, field presence, reference existence, or other objective rules alone.

The procedure is designed to:

- Apply consistent quality criteria across Structure, Ideas, and Storyboard outputs.
- Evaluate evidence accuracy, interpretation quality, creative relevance, and production usefulness.
- Support repeatable scoring through shared rating anchors.
- Record observations and defects with traceable supporting evidence.
- Distinguish implementation failures from generation-quality problems.
- Support reviewer calibration, regression analysis, and evidence-based acceptance recommendations.

This document defines the review method. It does not represent completed test execution or independently certify application readiness.

---

## 2. Evaluation Principles

### 2.1 Evidence Before Judgment

Reviewers should inspect the relevant source material and input constraints before evaluating generated conclusions.

An output should not receive a high score solely because it is fluent, detailed, or professionally formatted.

### 2.2 Separate Observation from Interpretation

Reviewers must distinguish between:

- Directly observable source facts
- Interpretations supported by available evidence
- Reasonable but unverified assumptions
- Unsupported or fabricated claims

Interpretive uncertainty should be assessed in relation to the available evidence rather than automatically treated as a weakness.

### 2.3 Evaluate the Intended Task

Each module should be judged according to its intended function.

Structure should support communication analysis. Ideas should support creative exploration and selection. Storyboard should support practical production planning.

A well-written output that fails its intended purpose should not receive the highest usefulness score.

### 2.4 Preserve Approval and Version Context

Reviewers should evaluate outputs against the correct source revision, creative brief, approved direction, and applicable specification.

An output based on the wrong approved revision is not acceptable merely because its content appears useful.

### 2.5 Distinguish Quality from Implementation

A missing feature, unavailable workflow, or unsupported application behavior should be recorded separately from the semantic quality of an output.

Reviewers must not infer that a specification requirement has passed testing without observing the relevant behavior.

---

## 3. Review Materials and Preparation

### 3.1 Required Review Materials

Reviewers should have access to the following materials when applicable:

| Material | Purpose |
|---|---|
| Source video | Verify observations, audiovisual content, and timing. |
| Extracted evidence | Inspect frames, transcripts, metadata, and source references. |
| User brief | Verify objective, audience, product facts, and constraints. |
| Structure output | Evaluate source analysis and transferable mechanisms. |
| Ideas output | Evaluate creative directions and product relevance. |
| Approved direction | Verify the exact approved creative revision. |
| Storyboard output | Evaluate production structure, timing, and execution detail. |
| Application configuration | Identify the tested application and model settings. |
| QA rubric | Apply consistent evaluation dimensions and scoring anchors. |
| Deterministic results | Identify objective failures requiring separate reporting. |

Not every material applies to every test case.

Missing essential review evidence should be recorded as a limitation rather than silently replaced with assumptions.

### 3.2 Review Preparation

Before scoring an output:

1. Identify the test case and module.
2. Confirm the application and specification versions.
3. Review the relevant source video or user input.
4. Identify applicable product facts, fixed wording, and approval constraints.
5. Inspect available deterministic validation results.
6. Confirm which rubric criteria apply.
7. Record any missing evidence or review limitations.

The reviewer should evaluate the actual saved output rather than a reconstructed description of the output.

---

## 4. Human Rating Scale

Human reviewers use the 0–3 anchored rating scale defined in `QA_RUBRIC_v0.7.6.md`.

| Score | Classification | Reviewer Interpretation |
|---|---|---|
| 0 | Absent or Invalid | The criterion is not satisfied, or the relevant content is unusable. |
| 1 | Major Improvement Needed | Substantial correction is required before the content can serve its intended purpose. |
| 2 | Useful with Limitations | The content is generally useful but contains identifiable weaknesses. |
| 3 | Strong and Usable | The content is specific, supported, coherent, and useful for its intended stage. |
| N/A | Not Applicable | The criterion does not apply; the reviewer records the reason. |

### 4.1 Scoring Rules

- Assign scores to individual applicable criteria.
- Evaluate the saved output against the relevant evidence and constraints.
- Provide a written explanation for scores of 0 or 1.
- Record specific evidence for consequential quality judgments.
- Do not treat N/A as zero.
- Do not infer a numerical release decision from an average score.
- Record critical integrity failures independently of numerical scores.

### 4.2 Interpretation of a Score of 2

A score of 2 indicates that an output is useful but has limited weaknesses.

It does not automatically mean the artifact is approved or production-ready.

For example, a storyboard may communicate the intended narrative clearly while still requiring additional production resources or approval decisions.

### 4.3 Interpretation of a Score of 3

A score of 3 indicates strong performance against the evaluated criterion.

It does not establish that the content will achieve a particular advertising outcome.

Human review assesses quality and usefulness, not unmeasured campaign effectiveness.

---

## 5. Structure Module Human Review

### 5.1 Review Objective

Determine whether the Structure output accurately interprets the source video's communication logic and identifies useful, evidence-grounded creative mechanisms.

### 5.2 Review Dimensions

| Rubric ID | Dimension | Human Review Question |
|---|---|---|
| S-QA-01 | Evidence Grounding | Are the observations and claims supported by the actual source? |
| S-QA-02 | Modality Accuracy | Does the analysis correctly distinguish visual, audio, text, and contextual evidence? |
| S-QA-03 | Interpretation Quality | Does the analysis explain meaningful communication relationships rather than simply summarize events? |
| S-QA-04 | Uncertainty Handling | Are ambiguous interpretations appropriately qualified? |
| S-QA-05 | Contextual Accuracy | Are brand, audience, and product assumptions supported or clearly identified? |
| S-QA-06 | Graph Coherence | Do the identified nodes and relationships explain communication logic? |
| S-QA-07 | Method Transferability | Are the proposed methods sufficiently grounded and transferable? |
| S-QA-08 | Evidence Coverage | Are missing modalities and evidence limitations reflected appropriately? |
| S-QA-09 | Revision Integrity | Are relevant user corrections and source revisions respected? |
| S-QA-10 | Practical Usefulness | Does the analysis provide insights that could inform creative development? |

### 5.3 Review Procedure

1. Watch the relevant source video.
2. Inspect the extracted evidence and available modality coverage.
3. Compare major generated observations with the original source.
4. Identify unsupported or overstated interpretations.
5. Review whether multiple plausible interpretations are handled appropriately.
6. Evaluate communication mechanisms and method cards.
7. Confirm that method cards do not introduce unsupported transfer assumptions.
8. Score applicable rubric dimensions.
9. Record specific examples supporting the evaluation.

### 5.4 Important Review Considerations

A Structure output should not be penalized simply because it contains no method cards.

A zero-card outcome may be appropriate when no transferable mechanism is sufficiently supported.

However, reviewers should still evaluate whether the retained analysis is accurate and useful.

Similarly, multiple interpretations are acceptable when supported by the evidence. Reviewers should not reward artificial certainty.

### 5.5 Example Finding

**Observation:** The analysis describes a close-up product shot as proof that the product delivers a specific performance benefit.

**Assessment:** The visual evidence supports the presence of the product shot but does not establish the claimed performance benefit.

**Relevant Criteria:** S-QA-01, S-QA-04, S-QA-05

**Recommended Classification:** Evidence-grounding defect.

---

## 6. Ideas Module Human Review

### 6.1 Review Objective

Determine whether generated creative directions are relevant, sufficiently differentiated, factually responsible, and useful for comparison and approval.

### 6.2 Review Dimensions

| Rubric ID | Dimension | Human Review Question |
|---|---|---|
| I-QA-01 | Task and Brand Fit | Does the direction respond to the communication objective and available brand context? |
| I-QA-02 | Product Fact Integrity | Are product facts and claims consistent with approved information? |
| I-QA-03 | Assumption Transparency | Are important missing inputs handled through appropriate assumptions? |
| I-QA-04 | Creative Differentiation | Are multiple directions conceptually distinct rather than cosmetic variations? |
| I-QA-05 | Mechanism Quality | Does the direction explain how its creative mechanism supports the intended audience response? |
| I-QA-06 | Proposal Completeness | Does the proposal contain sufficient detail to evaluate and develop the concept? |
| I-QA-07 | Reference Adaptation | Are source methods adapted appropriately to the new product and task? |
| I-QA-08 | Experimental Transparency | Are experimental hypotheses and validation needs clearly identified? |
| I-QA-09 | Qualified Output Selection | Are weak or duplicate directions excluded rather than retained to meet a fixed count? |
| I-QA-10 | Approval Integrity | Is the approval status of the evaluated direction represented accurately? |

### 6.3 Review Procedure

1. Read the creative brief and verified product information.
2. Identify required constraints and fixed wording.
3. Review each generated creative direction independently.
4. Evaluate relevance, product integration, and persuasive mechanism.
5. Compare directions to assess meaningful differentiation.
6. Identify unsupported product claims or audience assumptions.
7. Review experimental labels and validation requirements.
8. Evaluate whether each retained direction meets the intended quality standard.
9. Score applicable criteria and record supporting examples.

### 6.4 Differentiation Assessment

When multiple directions are provided, reviewers should compare:

- Central creative proposition
- Persuasive mechanism
- Narrative perspective
- Product integration
- Intended audience interpretation
- Execution approach

Different opening lines, visual styles, or tone do not necessarily establish different creative concepts.

A direction should be considered meaningfully differentiated when its underlying creative approach provides a distinct option for the user's decision.

### 6.5 Qualified Direction Count

Reviewers should assess the quality of the retained directions rather than reward a particular number of outputs.

One strong direction may be preferable to two weak or redundant directions.

A zero-direction outcome may also be appropriate when the available constraints do not support a qualified proposal.

### 6.6 Example Finding

**Observation:** Two generated directions use different opening sentences but follow the same persuasive mechanism, product integration, and narrative structure.

**Assessment:** The directions lack meaningful conceptual differentiation.

**Relevant Criteria:** I-QA-04, I-QA-09

**Recommended Classification:** Creative differentiation defect.

---

## 7. Storyboard Module Human Review

### 7.1 Review Objective

Determine whether the storyboard accurately translates the approved direction into a coherent and feasible audiovisual production plan.

### 7.2 Review Dimensions

| Rubric ID | Dimension | Human Review Question |
|---|---|---|
| P-QA-01 | Approval Fidelity | Does the storyboard follow the correct approved direction and brief? |
| P-QA-02 | Table Structure | Is the required four-column structure present and usable? |
| P-QA-03 | Shot Granularity | Does each row represent a clear, bounded shot or generation segment? |
| P-QA-04 | Narrative Continuity | Does the sequence preserve the intended communication logic? |
| P-QA-05 | Visual Specificity | Are visual instructions concrete enough for production planning? |
| P-QA-06 | Audio Integrity | Are dialogue, voice-over, sound, and silence represented accurately? |
| P-QA-07 | Timing Feasibility | Can the planned actions and speech plausibly fit within the assigned duration? |
| P-QA-08 | Production Requirements | Are required assets, resources, and dependencies identified? |
| P-QA-09 | Creative Fidelity | Are approved message and concept preserved through execution decisions? |
| P-QA-10 | Status Accuracy | Does the readiness status reflect unresolved critical issues? |
| P-QA-11 | Export Integrity | Are relevant warnings and experimental labels preserved? |
| P-QA-12 | Practical Usefulness | Could a production team use the storyboard to plan the next steps? |

### 7.3 Review Procedure

1. Read the approved creative direction and production brief.
2. Confirm the correct approval and revision references.
3. Review the complete storyboard sequence.
4. Assess whether each shot communicates a clear visual action.
5. Evaluate dialogue and audio requirements.
6. Assess timing feasibility, including speech and reading time.
7. Identify missing resources, dependencies, or continuity information.
8. Compare the storyboard's message with the approved direction.
9. Inspect readiness labels and unresolved issues.
10. Review exported content where export behavior is part of the test.
11. Score applicable criteria and document findings.

### 7.4 Production Readiness Assessment

Reviewers should distinguish between:

**Production Ready:** The artifact satisfies applicable readiness requirements and contains no recorded unresolved critical issues that prevent the intended production handoff.

**Discussion Draft:** The artifact remains useful for review or discussion but contains unresolved issues that must remain visible.

A readable or visually polished storyboard is not automatically production-ready.

If an unresolved critical problem remains after the permitted repair, reviewers should confirm that the artifact retains Discussion Draft status.

### 7.5 Example Finding

**Observation:** A 15-second storyboard includes dialogue that would require substantially more than the available time at a realistic speaking pace.

**Assessment:** The timing is not feasible as presented.

**Relevant Criteria:** P-QA-07, P-QA-09

**Recommended Classification:** Timing and production feasibility defect.

---

## 8. Cross-Module Review

Human review should also evaluate whether information remains accurate and consistent across the workflow.

| Rubric ID | Review Focus | Review Question |
|---|---|---|
| X-QA-01 | Evidence Traceability | Are source-dependent claims appropriately grounded across modules? |
| X-QA-02 | Source Version Integrity | Are outputs based on compatible source and artifact revisions? |
| X-QA-03 | Approved Information | Are verified product facts and required wording preserved? |
| X-QA-04 | Language Consistency | Is meaning preserved across Chinese and English content? |
| X-QA-05 | Repair Control | Does the observed operation follow the specified repair limit? |
| X-QA-06 | Uncertainty Transparency | Are assumptions and unresolved issues clearly identified? |
| X-QA-07 | Status Consistency | Are draft, experimental, approval, and readiness states represented accurately? |
| X-QA-08 | Export Consistency | Are warnings and relevant status information preserved? |
| X-QA-09 | Revision Continuity | Are accepted changes preserved across related artifacts? |
| X-QA-10 | Workflow Boundaries | Are approval and handoff requirements respected? |

Deterministic validation should be used for objective relationships where possible.

Human reviewers should focus on meaning, contextual appropriateness, and the consequences of inconsistencies.

---

## 9. Critical Failure Identification

A critical failure is an issue that compromises essential factual integrity, evidence integrity, approval integrity, or production-readiness representation.

Examples include:

- Fabricated source evidence
- Unsupported product claims presented as verified
- Invalid evidence used to justify consequential conclusions
- Unapproved creative directions treated as approved
- Silent changes to the approved core message
- Unresolved critical storyboard issues concealed by a Production Ready label
- Required warnings removed from exported materials

Critical failures must be recorded separately from numerical scores.

Reviewers should not use an overall average to override a critical failure.

Severity classifications should follow `QA_RUBRIC_v0.7.6.md`.

---

## 10. Reviewer Calibration

### 10.1 Calibration Objective

Calibration helps reviewers apply the same scoring criteria consistently.

It is particularly important for subjective dimensions such as creative differentiation, interpretation quality, and production usefulness.

### 10.2 Calibration Procedure

When multiple reviewers are available:

1. Select a small shared set of representative outputs.
2. Provide each reviewer with the same source materials and rubric.
3. Have reviewers score the outputs independently.
4. Compare criterion-level scores and supporting explanations.
5. Discuss disagreements using source evidence and rubric anchors.
6. Document any agreed interpretation of ambiguous criteria.
7. Apply the clarified interpretation consistently in subsequent reviews.

Calibration should not be used to force agreement without examining evidence.

### 10.3 Single-Reviewer Evaluation

When only one reviewer is available:

- Apply the same rubric anchors across all outputs.
- Preserve evidence supporting important judgments.
- Use consistent scoring examples.
- Identify uncertain or borderline cases.
- Avoid presenting individual judgment as independently verified reviewer consensus.

### 10.4 Calibration Record

Where calibration is conducted, record:

- Reviewed artifact IDs
- Participating reviewers
- Initial criterion scores
- Main disagreement points
- Evidence considered
- Agreed scoring interpretation
- Remaining unresolved disagreements

No inter-reviewer agreement statistic should be reported unless the corresponding review data has actually been collected and analyzed.

---

## 11. Handling Reviewer Disagreement

Reviewer disagreement should be resolved through evidence-based discussion.

### 11.1 Resolution Procedure

1. Identify the specific criterion with differing scores.
2. Compare the reviewers' evidence and reasoning.
3. Revisit the applicable rubric anchor.
4. Determine whether the disagreement concerns facts, interpretation, or the scoring definition.
5. Record the final assessment and supporting rationale.
6. Preserve unresolved disagreement when consensus cannot be justified.

### 11.2 Escalation

Cases involving unsupported factual claims, approval violations, or production-readiness conflicts should be prioritized for additional review.

If reviewers cannot resolve a consequential issue, the result should remain Needs Review until the appropriate evidence or decision is available.

A consensus score should not be invented when only one reviewer has evaluated the artifact.

---

## 12. Human Review Record Format

Each completed review should preserve the following information.

| Field | Description |
|---|---|
| Test Case ID | Corresponding scenario from `EXPECTED_BEHAVIORS.md` |
| Artifact ID | Identifier of the reviewed output |
| Module | Structure, Ideas, Storyboard, or cross-module |
| Application Version | Version or commit under evaluation |
| Specification Version | Applicable generation specification |
| Reviewer | Person conducting the evaluation |
| Review Date | Date of review |
| Rubric Criterion | Applicable S-QA, I-QA, P-QA, or X-QA identifier |
| Score | 0, 1, 2, 3, or N/A |
| Supporting Evidence | Relevant source reference or output excerpt |
| Reviewer Notes | Explanation of the score |
| Defect Severity | Critical, Major, Minor, or Informational when applicable |
| Test Status | Pass, Fail, Pending Implementation, Blocked, Not Tested, Needs Review, or N/A |
| Follow-Up | Relevant correction, clarification, or retest requirement |

Scores, defect severity, and test execution status represent different information and should be recorded separately.

---

## 13. Example Review Records

The following examples illustrate the expected recording format. They are hypothetical and are not actual test results.

### Example A — Structure Evidence Grounding

**Test Case:** STR-02  
**Rubric Criterion:** S-QA-01  
**Illustrative Score:** 1  
**Observation:** The output identifies a blurred object as a specific product without sufficient visual evidence.  
**Reasoning:** The conclusion exceeds the available source evidence.  
**Potential Severity:** Major, subject to the consequence of the claim.  
**Follow-Up:** Qualify the interpretation or remove the unsupported identification.

### Example B — Ideas Differentiation

**Test Case:** IDE-02  
**Rubric Criterion:** I-QA-04  
**Illustrative Score:** 1  
**Observation:** Two directions use different wording but the same central mechanism and narrative structure.  
**Reasoning:** The alternatives do not provide meaningful conceptual choice.  
**Potential Severity:** Major.  
**Follow-Up:** Develop a genuinely distinct creative mechanism or retain only the qualified direction.

### Example C — Storyboard Production Usefulness

**Test Case:** STB-04  
**Rubric Criterion:** P-QA-08  
**Illustrative Score:** 2  
**Observation:** The storyboard provides specific shot instructions but leaves one production resource unconfirmed.  
**Reasoning:** The plan is useful for discussion but requires an explicit resource decision.  
**Potential Severity:** Minor or Major, depending on the resource's importance.  
**Follow-Up:** Record the resource dependency and assess its effect on readiness.

---

## 14. Relationship to Deterministic Checks

Human review and deterministic validation should be complementary.

| Quality Dimension | Deterministic Validation | Human Review |
|---|---|---|
| Evidence reference | Confirms that the reference exists | Determines whether it supports the claim |
| Direction count | Confirms the number of returned directions | Determines whether directions are qualified and distinct |
| Storyboard columns | Confirms required fields are present | Evaluates whether the instructions are useful |
| Shot timing | Checks structural time consistency | Evaluates realistic action and speech duration |
| Approval reference | Checks saved approval identity | Evaluates fidelity to the approved concept |
| Experimental status | Confirms required labels are present | Evaluates whether hypotheses and validation needs are clear |
| Export warnings | Confirms required warnings are retained | Evaluates whether limitations are understandable |

A deterministic Pass does not automatically imply a human quality score of 3.

Likewise, a strong semantic output does not excuse an applicable deterministic failure.

---

## 15. Regression Review Procedure

Human regression review compares output quality across relevant application, model, or specification versions.

### 15.1 Comparison Requirements

Where practical, reviewers should use:

- The same source input
- Equivalent user constraints
- Identical upstream evidence for isolated generation comparisons
- Documented model and configuration settings
- The same applicable rubric criteria
- Consistent scoring anchors

### 15.2 Regression Questions

Reviewers should evaluate:

1. Did a previously observed issue improve?
2. Did the updated output introduce a new problem?
3. Did evidence grounding improve or deteriorate?
4. Did creative usefulness change?
5. Did approval, version, or readiness integrity change?
6. Are the observed differences attributable to the component being tested?
7. Are limitations and uncertainties still communicated appropriately?

### 15.3 Reporting

Regression findings should include specific before-and-after observations.

A quality improvement claim must be supported by recorded evidence.

Where the sample is limited, reviewers should avoid generalizing results beyond the evaluated cases.

---

## 16. Review Completion and Reporting

A human review is complete when:

- The relevant source materials have been inspected.
- Applicable rubric criteria have been evaluated.
- Scores and supporting evidence have been recorded.
- Critical failures and other defects have been identified.
- Missing evidence and unresolved questions have been documented.
- The review status accurately reflects the available evidence.

Completion of a human review does not independently establish that the application has passed release acceptance.

Review findings should be transferred into the project's QA results and regression reporting artifacts.

---

## 17. Related Documentation

- `QA_RUBRIC_v0.7.6.md` — Evaluation criteria and rating anchors
- `EXPECTED_BEHAVIORS.md` — Scenario-based test expectations
- `DETERMINISTIC_CHECKS.md` — Objective validation requirements
- `QA_TEST_RESULTS.csv` — Recorded evaluation results
- `REGRESSION_REPORT.md` — Version comparisons and verified findings

This procedure provides a consistent method for evaluating semantic quality and practical usefulness across the Video Anatomy generation workflow.

It supports evidence-based QA reporting while preserving the distinction between review methodology, observed test results, and release acceptance.
