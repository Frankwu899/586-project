# Video Anatomy v0.7.6 — Expected Behaviors & QA Test Cases

**Project:** COMM 586 — Video Anatomy   
**Specification:** Professional Generation Skill v0.7.6  
**Related Document:** `QA_RUBRIC_v0.7.6.md`

---

## 1. Purpose

This document translates the Video Anatomy v0.7.6 QA rubric into observable, reproducible test scenarios.

Each test case defines:

- The input condition or testing scenario
- The expected system behavior
- Unacceptable behavior
- The corresponding QA rubric criteria
- The evidence required to verify the outcome

The cases are designed to support deterministic validation, human evaluation, and regression testing.

This document defines expected behaviors rather than reporting completed test executions.

## 2. Test Case Structure

Each case uses the following fields:

| Field | Description |
|---|---|
| Test ID | Unique identifier for the test scenario |
| Scenario | The condition being evaluated |
| Input / Setup | Required input or system state |
| Expected Behavior | Observable behavior that satisfies the requirement |
| Unacceptable Behavior | Behavior that violates the requirement |
| Rubric Mapping | Corresponding QA criteria |
| Verification | Evidence required to assess the result |

### Test Execution Status

When tests are executed, results should use the following statuses:

- **Pass:** The observed behavior satisfies the requirement.
- **Fail:** The observed behavior violates the requirement.
- **Pending Implementation:** The behavior is not implemented in the tested version.
- **Blocked:** A dependency prevents execution.
- **Not Tested:** The case has not been executed.
- **Needs Review:** Available evidence is insufficient.
- **N/A:** The requirement does not apply.

---

## 3. Structure Module Test Cases

### STR-01 — Accurate Source Observation

**Scenario:** A source video contains clearly identifiable visual actions.

**Input / Setup:** Use a video with a known sequence of visible product shots, human actions, and on-screen text.

**Expected Behavior:**
- The analysis accurately describes observable content.
- Important observations reference the correct source evidence.
- Visual and audio evidence are distinguished.

**Unacceptable Behavior:**
- Inventing actions or objects absent from the source.
- Using narration as proof of an unseen visual event.

**Rubric Mapping:** S-QA-01, S-QA-02, X-QA-01

**Verification:** Compare generated observations and evidence references against the original video and extracted evidence.

### STR-02 — Ambiguous Visual Evidence

**Scenario:** A video contains a blurred, obstructed, or ambiguous scene.

**Input / Setup:** Use a clip in which a relevant object or action cannot be identified confidently.

**Expected Behavior:**
- The system identifies the limitation.
- Uncertain interpretations are qualified.
- Unsupported visual details are not introduced.

**Unacceptable Behavior:**
- Confidently identifying an object without sufficient evidence.
- Presenting speculation as observation.

**Rubric Mapping:** S-QA-01, S-QA-04, S-QA-08

**Verification:** Human comparison of the video and generated claims.

### STR-03 — Multiple Plausible Interpretations

**Scenario:** The same creative sequence supports more than one reasonable interpretation.

**Input / Setup:** Provide a video with an ambiguous emotional or persuasive mechanism.

**Expected Behavior:**
- The system preserves multiple plausible interpretations when justified.
- Each interpretation is connected to available evidence.
- No unsupported definitive ranking is imposed.

**Unacceptable Behavior:**
- Forcing a single interpretation without adequate evidence.
- Inventing audience intent or response.

**Rubric Mapping:** S-QA-03, S-QA-04

**Verification:** Human review of evidence and interpretation alternatives.

### STR-04 — No Qualified Method Cards

**Scenario:** A video does not provide sufficient evidence for a reliable transferable method.

**Input / Setup:** Use a source with limited, incomplete, or non-transferable communication mechanisms.

**Expected Behavior:**
- The system may return zero qualified method cards.
- Valid observations and analysis are preserved.
- The limitation is explained clearly.

**Unacceptable Behavior:**
- Fabricating a method card to meet a target count.
- Removing all valid analysis because no method qualifies.

**Rubric Mapping:** S-QA-07, S-QA-10, X-QA-06

**Verification:** Inspect method-card count, explanations, and retained analysis.

### STR-05 — Incomplete Source Modality

**Scenario:** A source video lacks reliable audio transcription or another required evidence modality.

**Input / Setup:** Use a video with missing, silent, or unusable audio evidence.

**Expected Behavior:**
- Missing evidence coverage is disclosed.
- Conclusions depending on that modality are qualified.
- Available evidence continues to support appropriately bounded analysis.

**Unacceptable Behavior:**
- Inventing dialogue or narration.
- Treating unavailable evidence as verified.

**Rubric Mapping:** S-QA-02, S-QA-08, X-QA-06

**Verification:** Compare modality availability with generated claims.

### STR-06 — Method Card Repair

**Scenario:** A generated method card fails an applicable quality check.

**Input / Setup:** Produce or identify a method card with an unsupported transferable mechanism.

**Expected Behavior:**
- At most one targeted quality repair is attempted for the operation.
- Unsupported cards are removed if they remain invalid.
- Supported analysis is preserved.

**Unacceptable Behavior:**
- Unlimited repeated repair attempts.
- Retaining unsupported cards without warning.
- Inventing evidence to justify a failing card.

**Rubric Mapping:** S-QA-07, S-QA-09, X-QA-05

**Verification:** Inspect generation trace, repair count, and final output.

---

## 4. Ideas Module Test Cases

### IDE-01 — Product Fact Preservation

**Scenario:** The creative brief contains verified product information and fixed wording.

**Input / Setup:** Provide a product brief with explicit features, approved claims, and required language.

**Expected Behavior:**
- Generated ideas preserve verified product facts.
- Required wording remains unchanged where specified.
- Unsupported benefits are not introduced.

**Unacceptable Behavior:**
- Inventing product features or performance claims.
- Modifying required claims without authorization.

**Rubric Mapping:** I-QA-02, X-QA-03

**Verification:** Compare generated directions with the approved product brief.

### IDE-02 — Meaningfully Different Directions

**Scenario:** The system generates multiple creative directions.

**Input / Setup:** Provide a brief that supports more than one viable creative approach.

**Expected Behavior:**
- Directions differ in central concept, persuasive mechanism, or narrative perspective.
- Each direction explains its intended mechanism and execution.
- Differences are meaningful rather than cosmetic.

**Unacceptable Behavior:**
- Producing two versions that differ only in wording, hook, or tone.
- Presenting near-duplicates as distinct concepts.

**Rubric Mapping:** I-QA-04, I-QA-05, I-QA-06

**Verification:** Human comparison of creative propositions and mechanisms.

### IDE-03 — Only One Qualified Direction

**Scenario:** Only one generated direction satisfies the applicable quality requirements.

**Input / Setup:** Use a constrained brief or a generation result with one valid and one invalid candidate.

**Expected Behavior:**
- The system retains the qualified direction.
- The output does not require a second direction.
- Relevant limitations are communicated.

**Unacceptable Behavior:**
- Retaining a weak or duplicate direction solely to produce two options.

**Rubric Mapping:** I-QA-09, X-QA-06

**Verification:** Inspect final direction count and qualification evidence.

### IDE-04 — Zero Qualified Directions

**Scenario:** No generated creative direction satisfies the quality requirements.

**Input / Setup:** Provide insufficient or contradictory constraints that prevent a qualified result.

**Expected Behavior:**
- The system reports that no direction qualifies.
- It identifies the relevant information or quality gap.
- It does not fabricate a successful proposal.

**Unacceptable Behavior:**
- Returning an unsupported direction as if it were approved or qualified.
- Concealing the failure.

**Rubric Mapping:** I-QA-03, I-QA-09, X-QA-06

**Verification:** Review the final response, qualification rationale, and available input evidence.

### IDE-05 — Experimental Creative Direction

**Scenario:** A creative concept depends on an unverified assumption.

**Input / Setup:** Provide a brief that supports an experimental hypothesis but not a verified performance claim.

**Expected Behavior:**
- The direction is explicitly labeled experimental.
- The relevant hypothesis and validation approach are identified.
- Experimental status is preserved through subsequent approval and handoff.

**Unacceptable Behavior:**
- Presenting the hypothesis as a verified outcome.
- Removing the experimental label during handoff.

**Rubric Mapping:** I-QA-08, X-QA-06, X-QA-07

**Verification:** Inspect the Ideas output and corresponding downstream metadata.

### IDE-06 — Creative Direction Approval Boundary

**Scenario:** A user has reviewed but not approved a generated direction.

**Input / Setup:** Save a direction revision without an explicit approval action.

**Expected Behavior:**
- The direction remains unapproved.
- Production handoff requires the appropriate approval.
- Approval is associated with the correct saved revision.

**Unacceptable Behavior:**
- Treating review or selection as final approval.
- Automatically approving a revised direction.

**Rubric Mapping:** I-QA-10, X-QA-02, X-QA-07

**Verification:** Inspect saved revision identifiers, approval state, and handoff behavior.

---

## 5. Storyboard Module Test Cases

### STB-01 — Required Storyboard Structure

**Scenario:** The system generates a storyboard from an approved direction.

**Input / Setup:** Provide a valid approved creative direction and production brief.

**Expected Behavior:**
- The main table includes Shot, Time, Visual, and Audio.
- Each row describes a bounded shot or generation segment.
- Required fields contain relevant content.

**Unacceptable Behavior:**
- Missing required columns.
- Combining multiple unrelated shots into one ambiguous row.

**Rubric Mapping:** P-QA-02, P-QA-03

**Verification:** Validate table structure and inspect shot boundaries.

### STB-02 — Approved Direction Fidelity

**Scenario:** Multiple revisions of a creative direction exist.

**Input / Setup:** Approve one saved revision and retain a different unapproved revision.

**Expected Behavior:**
- Storyboard generation uses the exact approved revision.
- The approved core message and narrative intent are preserved.
- Revision references remain consistent.

**Unacceptable Behavior:**
- Using an unapproved or outdated direction.
- Silently changing the approved message.

**Rubric Mapping:** P-QA-01, P-QA-04, P-QA-09

**Verification:** Compare storyboard content and metadata with the approved revision.

### STB-03 — Dialogue Timing Feasibility

**Scenario:** The approved script contains more spoken content than the target duration can reasonably accommodate.

**Input / Setup:** Provide a short target duration and an intentionally long voice-over.

**Expected Behavior:**
- Speech duration is estimated and identified as such.
- Timing conflicts are made visible.
- Proposed cuts or alternatives preserve approval boundaries.

**Unacceptable Behavior:**
- Claiming unrealistic speech timing is feasible.
- Silently removing essential message content.

**Rubric Mapping:** P-QA-07, P-QA-09

**Verification:** Compare dialogue length, estimated speaking time, and target duration.

### STB-04 — Missing Production Resources

**Scenario:** The approved direction requires resources that are not confirmed as available.

**Input / Setup:** Specify an execution involving an unavailable actor, location, prop, or asset.

**Expected Behavior:**
- Required resources and dependencies are identified.
- Missing resources are not represented as available.
- Practical alternatives are labeled appropriately.

**Unacceptable Behavior:**
- Assuming unavailable resources have been secured.
- Silently changing the core creative concept to avoid the dependency.

**Rubric Mapping:** P-QA-08, P-QA-09, X-QA-06

**Verification:** Compare the storyboard's resource requirements with the provided production constraints.

### STB-05 — Discussion Draft Status

**Scenario:** A storyboard retains a critical unresolved issue after the permitted targeted repair.

**Input / Setup:** Generate a storyboard with a known unresolved timing, claim, or feasibility problem.

**Expected Behavior:**
- The artifact remains reviewable.
- It is clearly labeled Discussion Draft.
- Unresolved issues are identified.
- Production Ready status is not assigned.

**Unacceptable Behavior:**
- Concealing the issue.
- Marking the storyboard Production Ready.

**Rubric Mapping:** P-QA-10, X-QA-05, X-QA-07

**Verification:** Inspect repair history, warnings, and final status.

### STB-06 — Export Warning Preservation

**Scenario:** A Discussion Draft is exported.

**Input / Setup:** Export a storyboard containing unresolved issues and applicable experimental labels.

**Expected Behavior:**
- Exported content preserves the Discussion Draft status.
- Relevant warnings and unresolved decisions remain visible.
- Applicable experimental labels and validation points remain attached.

**Unacceptable Behavior:**
- Removing warnings in the export.
- Presenting the exported artifact as production-approved.

**Rubric Mapping:** P-QA-11, X-QA-08

**Verification:** Compare the in-app artifact and exported output.

---

## 6. Cross-Module Test Cases

### XMD-01 — Evidence Traceability Across Modules

**Scenario:** A Structure insight is selected and adapted into a creative direction.

**Input / Setup:** Select an evidence-grounded Structure method and generate an Idea using it.

**Expected Behavior:**
- Relevant source references remain identifiable.
- The adapted idea distinguishes source evidence from new creative assumptions.
- Unsupported source interpretations are not converted into verified product claims.

**Unacceptable Behavior:**
- Losing important evidence provenance.
- Presenting speculative interpretations as source facts.

**Rubric Mapping:** X-QA-01, X-QA-02, I-QA-07

**Verification:** Compare the source analysis, selected method, and generated direction.

### XMD-02 — Version and Revision Consistency

**Scenario:** A user updates an input or creative direction after an earlier artifact was generated.

**Input / Setup:** Create multiple revisions of the same source or direction.

**Expected Behavior:**
- Downstream artifacts reference the correct revision.
- Superseded approvals are not silently reused.
- The system preserves a consistent revision relationship.

**Unacceptable Behavior:**
- Mixing evidence or approval references from incompatible revisions.

**Rubric Mapping:** X-QA-02, X-QA-09

**Verification:** Inspect artifact metadata and revision references.

### XMD-03 — Chinese and English Content Integrity

**Scenario:** A project contains Chinese source content and English output instructions, or the reverse.

**Input / Setup:** Provide bilingual source material and explicit language requirements.

**Expected Behavior:**
- Output follows the specified language settings.
- Fixed product wording is preserved.
- Original-language evidence remains accurately represented.
- Translation does not introduce unsupported meaning.

**Unacceptable Behavior:**
- Altering fixed copy through translation.
- Misrepresenting source-language statements.

**Rubric Mapping:** X-QA-03, X-QA-04

**Verification:** Bilingual comparison of input, evidence, and generated output.

### XMD-04 — One Targeted Repair Limit

**Scenario:** A module output fails an applicable quality requirement.

**Input / Setup:** Trigger a repair-eligible quality failure.

**Expected Behavior:**
- The system attempts no more than one targeted quality repair for the operation.
- The outcome and remaining limitations are recorded.
- The module applies its defined failure-handling behavior.

**Unacceptable Behavior:**
- Repeated uncontrolled repair attempts.
- Concealing an unsuccessful repair.

**Rubric Mapping:** X-QA-05, X-QA-06

**Verification:** Inspect operation trace, repair count, and final artifact.

### XMD-05 — Unsupported Product Claim Propagation

**Scenario:** An unsupported product claim appears in an intermediate creative proposal.

**Input / Setup:** Introduce an unverified benefit during the Ideas stage.

**Expected Behavior:**
- The claim is not treated as verified.
- It is removed, corrected, or explicitly identified as unsupported.
- The claim does not silently become approved Storyboard copy.

**Unacceptable Behavior:**
- Promoting the unsupported claim into production-ready content.

**Rubric Mapping:** I-QA-02, P-QA-05, P-QA-10, X-QA-03

**Verification:** Compare the approved brief, Ideas output, and Storyboard.

### XMD-06 — Status Integrity Across Handoff

**Scenario:** An artifact is transferred between workflow stages or exported.

**Input / Setup:** Use an artifact with a known draft, approval, or experimental status.

**Expected Behavior:**
- The relevant status is preserved.
- Downstream interfaces do not imply a higher level of readiness.
- Warnings remain available where required.

**Unacceptable Behavior:**
- Treating draft status as approval.
- Removing unresolved warnings during handoff.

**Rubric Mapping:** X-QA-07, X-QA-08, X-QA-10

**Verification:** Compare source status, downstream artifact, and export.

---

## 7. Test Coverage Matrix

The following matrix summarizes the 24 defined test scenarios.

| Test ID | Module | Primary Focus | Verification Type |
|---|---|---|---|
| STR-01 | Structure | Source observation accuracy | Human + reference validation |
| STR-02 | Structure | Ambiguous evidence | Human |
| STR-03 | Structure | Interpretive uncertainty | Human |
| STR-04 | Structure | Zero method cards | Deterministic + human |
| STR-05 | Structure | Missing modality | Human + coverage validation |
| STR-06 | Structure | Method card repair | Trace + human |
| IDE-01 | Ideas | Product facts | Human + constraint comparison |
| IDE-02 | Ideas | Creative differentiation | Human |
| IDE-03 | Ideas | One qualified direction | Deterministic + human |
| IDE-04 | Ideas | Zero qualified directions | Deterministic + human |
| IDE-05 | Ideas | Experimental labeling | Status + human |
| IDE-06 | Ideas | Approval boundary | Workflow validation |
| STB-01 | Storyboard | Required structure | Deterministic |
| STB-02 | Storyboard | Approved revision fidelity | Workflow + human |
| STB-03 | Storyboard | Dialogue timing | Timing + human |
| STB-04 | Storyboard | Resource feasibility | Human |
| STB-05 | Storyboard | Discussion Draft status | Workflow validation |
| STB-06 | Storyboard | Export warnings | Export validation |
| XMD-01 | Cross-module | Evidence provenance | Reference + human |
| XMD-02 | Cross-module | Revision consistency | Deterministic |
| XMD-03 | Cross-module | Bilingual integrity | Human |
| XMD-04 | Cross-module | Repair limit | Trace validation |
| XMD-05 | Cross-module | Unsupported claim propagation | Human + reference validation |
| XMD-06 | Cross-module | Status preservation | Workflow validation |

---

## 8. Test Execution Guidelines

Tests should be executed against a clearly identified application version.

For each case:

1. Record the source input and test configuration.
2. Verify relevant application and specification versions.
3. Execute the target operation.
4. Save the generated artifact and relevant evidence.
5. Compare observed behavior with the expected and unacceptable outcomes.
6. Assign the appropriate test status.
7. Record the defect severity and supporting observations when applicable.
8. Preserve the result for regression comparison.

Where a required behavior is not implemented in the tested application, use Pending Implementation rather than recording an unsupported Pass result.

Human judgment should be supported by specific output examples and source evidence.

Test cases should be rerun when a relevant implementation or generation specification changes.

---

## 9. Acceptance Interpretation

A test case passes only when its observed behavior satisfies the applicable confirmed requirements.

Passing deterministic checks does not establish semantic quality.

A high human quality score does not override a critical integrity failure.

An unexecuted test is not evidence of successful implementation.

The evaluation record should distinguish:

- Specification conformance
- Observed implementation behavior
- Semantic quality
- Practical usefulness
- Unresolved risks

Final release acceptance depends on verified test results and the team's agreed release criteria.

---

## 10. Related QA Documentation

- `QA_RUBRIC_v0.7.6.md` — Quality dimensions and scoring anchors
- `DETERMINISTIC_CHECKS.md` — Automated and objective validation rules
- `HUMAN_REVIEW_PROCEDURE.md` — Reviewer calibration and evaluation procedure
- `QA_TEST_RESULTS.csv` — Recorded execution results
- `REGRESSION_REPORT.md` — Version comparison and verified findings


This document defines the expected behaviors used to evaluate Video Anatomy v0.7.6. It does not represent completed test execution or verified application readiness.
