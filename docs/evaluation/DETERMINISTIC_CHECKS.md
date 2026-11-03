# Video Anatomy v0.7.6 — Deterministic QA Checks

**Project:** COMM 586 — Video Anatomy  
**Specification:** Professional Generation Skill v0.7.6  
**Related Documents:** `QA_RUBRIC_v0.7.6.md`, `EXPECTED_BEHAVIORS.md`

---

## 1. Purpose

This document defines deterministic quality assurance checks for Video Anatomy v0.7.6.

Deterministic checks evaluate requirements that can be verified through explicit rules, structured data, artifact metadata, or recorded workflow events.

They provide a reproducible foundation for validating the Structure, Ideas, and Storyboard modules.

The checks complement human semantic evaluation. They do not independently establish the accuracy of creative interpretations, the originality of ideas, or the practical effectiveness of advertising content.

This document defines validation requirements and test expectations. It does not claim that every check is implemented or that the application has passed validation.

## 2. Validation Principles

The deterministic QA framework follows five principles.

### 2.1 Reproducibility

Given the same artifact, metadata, configuration, and validation rules, a deterministic check should produce the same result.

### 2.2 Explicit Evidence

Checks must use observable artifact content, structured fields, metadata, or workflow records rather than assumptions about system behavior.

### 2.3 Separation of Validation and Judgment

Structural compliance is evaluated independently of semantic quality.

For example, a valid evidence reference confirms that a referenced item exists; it does not establish that the reference supports the generated interpretation.

### 2.4 Version Awareness

Validation must account for the application version, generation specification, source revision, and relevant approval state.

### 2.5 Transparent Failure Handling

Validation failures must be recorded with sufficient detail to support debugging and regression testing.

Missing implementation support must not be reported as a successful check.

---

## 3. Validation Status Definitions

| Status | Meaning |
|---|---|
| Pass | The observed artifact satisfies the applicable deterministic rule. |
| Fail | The observed artifact violates the applicable deterministic rule. |
| Pending Implementation | The required functionality is not implemented in the tested application version. |
| Blocked | The required artifact, metadata, or environment is unavailable. |
| Not Tested | The check has not been executed. |
| Needs Review | The result cannot be established without additional interpretation or evidence. |
| N/A | The rule does not apply to the evaluated artifact. |

A check must not receive Pass solely because the required field or validation mechanism is unavailable.

---

## 4. Structure Module Checks

| Check ID | Validation Requirement | Pass Condition | Failure Condition | Rubric Mapping |
|---|---|---|---|---|
| DET-S-01 | Required artifact structure | The output conforms to the applicable Structure artifact schema. | Required schema fields are missing or invalid. | S-QA-06 |
| DET-S-02 | Evidence reference validity | Referenced evidence identifiers exist in the applicable source evidence set. | A reference is missing, invalid, or points to an incompatible source. | S-QA-01, X-QA-01 |
| DET-S-03 | Source revision consistency | Artifact references match the intended source revision. | References point to a superseded or incompatible revision. | S-QA-09, X-QA-02 |
| DET-S-04 | Evidence modality metadata | Evidence references retain their available modality classification. | A required modality identifier is absent or inconsistent with the referenced record. | S-QA-02 |
| DET-S-05 | Method card count | Zero method cards is accepted when the artifact otherwise satisfies its schema. | Validation incorrectly rejects a valid zero-card result. | S-QA-07 |
| DET-S-06 | Method card references | Each retained method card includes required valid references and structured fields. | A card lacks required fields or uses invalid references. | S-QA-07 |
| DET-S-07 | Repair attempt limit | No more than one targeted quality repair is recorded for the operation. | More than one targeted quality repair is recorded. | X-QA-05 |
| DET-S-08 | Output preservation | Valid analysis remains available when unsupported method cards are removed. | Removal of a method card unexpectedly deletes unrelated valid analysis. | S-QA-09, X-QA-09 |

### 4.1 Validation Notes

Evidence existence and source-revision checks are deterministic when the corresponding metadata is available.

Whether a source observation is factually accurate or a method card is meaningfully transferable requires human review.

A zero-card result is not automatically a quality failure.

---

## 5. Ideas Module Checks

| Check ID | Validation Requirement | Pass Condition | Failure Condition | Rubric Mapping |
|---|---|---|---|---|
| DET-I-01 | Required direction fields | Each direction contains the required structured fields for its artifact type. | Required fields are missing or invalid. | I-QA-06 |
| DET-I-02 | Qualified direction count | The validator accepts zero, one, or multiple qualifying directions where permitted by the specification. | Validation forces a fixed count of two directions. | I-QA-09 |
| DET-I-03 | Approved product references | Required product identifiers and fixed-copy fields match the approved input where exact matching applies. | Required identifiers or fixed wording are changed. | I-QA-02, X-QA-03 |
| DET-I-04 | Experimental status | An experimental direction retains its explicit experimental status field or label. | The required experimental status is absent. | I-QA-08 |
| DET-I-05 | Experimental validation fields | Required hypothesis and validation fields are present for experimental directions. | Required experimental fields are missing. | I-QA-08 |
| DET-I-06 | Direction revision identity | A saved direction retains a valid revision identifier. | Revision identity is missing or inconsistent. | I-QA-10, X-QA-02 |
| DET-I-07 | Approval state | Production handoff references an explicitly approved direction revision. | An unapproved or incompatible revision is used. | I-QA-10 |
| DET-I-08 | Repair attempt limit | No more than one targeted quality repair is recorded for the operation. | More than one targeted repair is recorded. | X-QA-05 |

### 5.1 Validation Notes

A validator can verify the number of returned directions but cannot determine whether they are meaningfully different through counting alone.

Creative differentiation, persuasive quality, and product relevance require semantic review.

Exact-copy checks should apply only to fields designated as fixed or immutable. They should not prevent legitimate creative rewriting of flexible content.

---

## 6. Storyboard Module Checks

| Check ID | Validation Requirement | Pass Condition | Failure Condition | Rubric Mapping |
|---|---|---|---|---|
| DET-P-01 | Required table columns | The main storyboard table contains Shot, Time, Visual, and Audio. | One or more required columns are missing. | P-QA-02 |
| DET-P-02 | Shot identifiers | Required shot identifiers are present and valid within the artifact. | Shot identifiers are missing or violate the applicable schema. | P-QA-03 |
| DET-P-03 | Time field validity | Each shot has a valid time representation under the applicable schema. | A required time field is missing or malformed. | P-QA-07 |
| DET-P-04 | Timeline consistency | Structured shot times are internally ordered and consistent with the configured timeline rules. | Invalid ordering, negative duration, or prohibited overlap is detected. | P-QA-07 |
| DET-P-05 | Required visual content | Each applicable shot includes a nonempty Visual field. | Required visual content is absent. | P-QA-05 |
| DET-P-06 | Required audio content | Each applicable shot includes an Audio field, including explicit silence where appropriate. | The Audio field is missing or violates the schema. | P-QA-06 |
| DET-P-07 | Approved direction reference | The storyboard references the exact approved direction revision. | The reference is missing, outdated, or unapproved. | P-QA-01 |
| DET-P-08 | Brief revision reference | The storyboard references a compatible production brief revision. | The brief reference is missing or incompatible. | P-QA-01 |
| DET-P-09 | Readiness status | An artifact with recorded unresolved critical issues is not marked Production Ready. | Production Ready conflicts with recorded unresolved critical issues. | P-QA-10 |
| DET-P-10 | Discussion Draft status | An artifact retained after unsuccessful critical-issue repair carries the required Discussion Draft status. | Required draft status is absent or incorrect. | P-QA-10 |
| DET-P-11 | Export status consistency | Exported content preserves the applicable readiness status and required warnings. | Status or warnings are lost during export. | P-QA-11 |
| DET-P-12 | Experimental metadata preservation | Experimental labels and required validation information remain attached where applicable. | Required experimental metadata is lost. | P-QA-11 |
| DET-P-13 | Repair attempt limit | No more than one targeted quality repair is recorded for the operation. | More than one targeted repair is recorded. | X-QA-05 |
| DET-P-14 | Required fixed wording | Exact-copy fields match their approved source values. | Required fixed wording is changed without authorization. | P-QA-06, X-QA-03 |

### 6.1 Validation Notes

Timeline validation should use the application's documented timing representation and overlap rules.

A nonempty Visual or Audio field does not guarantee that its content is sufficiently specific or production-ready.

Likewise, valid time intervals do not prove that dialogue, actions, or transitions can realistically fit within the assigned duration.

These questions require human evaluation.

---

## 7. Cross-Module Integrity Checks

| Check ID | Validation Requirement | Pass Condition | Failure Condition | Rubric Mapping |
|---|---|---|---|---|
| DET-X-01 | Artifact identity | Required artifact identifiers are present and valid. | Required identifiers are missing or invalid. | X-QA-02 |
| DET-X-02 | Source lineage | Downstream artifacts reference compatible upstream source and artifact revisions. | Incompatible or stale references are detected. | X-QA-02 |
| DET-X-03 | Approval lineage | Approval references identify the appropriate saved revision. | Approval is missing, stale, or associated with a different revision. | X-QA-02, X-QA-07 |
| DET-X-04 | Fixed-copy integrity | Designated immutable text matches the approved source. | Fixed wording changes unexpectedly. | X-QA-03 |
| DET-X-05 | Language configuration | Required language configuration fields are present and valid. | Required language settings are absent or invalid. | X-QA-04 |
| DET-X-06 | Repair count | Recorded targeted quality repairs remain within the one-repair limit per operation. | The operation exceeds the allowed repair count. | X-QA-05 |
| DET-X-07 | Warning preservation | Required warnings remain attached to relevant artifacts and exports. | A required warning is removed or omitted. | X-QA-06, X-QA-08 |
| DET-X-08 | Status consistency | Artifact status and recorded workflow state are compatible. | Status contradicts approval, readiness, or experimental metadata. | X-QA-07 |
| DET-X-09 | Revision continuity | Accepted revisions preserve the appropriate artifact relationships. | Required revision links are lost or incorrectly reassigned. | X-QA-09 |
| DET-X-10 | Required handoff references | Downstream handoff includes the identifiers required by the applicable workflow contract. | A required handoff identifier is missing or invalid. | X-QA-10 |

### 7.1 Scope of Automated Validation

Cross-module checks should validate explicit relationships rather than infer undocumented ones.

For example, an approval reference can be checked against saved approval metadata. Whether the approved creative direction is strategically appropriate remains a semantic evaluation question.

---

## 8. Validation Execution Procedure

### 8.1 Preparation

Before executing deterministic checks:

1. Identify the application version and commit.
2. Record the generation specification version.
3. Identify the module and operation under test.
4. Preserve the source inputs and relevant revision identifiers.
5. Confirm that the artifact and required metadata are available.
6. Identify the applicable validation rules for the tested implementation.

### 8.2 Execution

For each applicable check:

1. Read the required artifact field, metadata, or workflow record.
2. Apply the documented validation rule.
3. Compare the observed value against the pass condition.
4. Record Pass, Fail, or the appropriate non-execution status.
5. Capture the relevant evidence for failures.
6. Associate the result with the correct test case and application version.

### 8.3 Failure Reporting

A failed deterministic check should record:

- Check ID
- Test case ID
- Application and specification versions
- Artifact identifier
- Expected condition
- Observed condition
- Relevant field or reference
- Error description
- Defect severity
- Evidence location
- Retest status, when applicable

Failure descriptions should identify the violated requirement rather than merely report that validation failed.

---

## 9. Example Validation Scenarios

### Example A — Storyboard Missing Audio Column

**Related Check:** DET-P-01

**Input Condition:** A generated storyboard includes Shot, Time, and Visual but omits Audio.

**Expected Result:** Fail

**Reason:** The required four-column storyboard structure is incomplete.

**Verification:** Inspect the structured table representation or rendered output.

### Example B — Zero Method Cards

**Related Check:** DET-S-05

**Input Condition:** Structure produces valid analysis with zero qualified method cards.

**Expected Result:** Pass for the method-card-count rule.

**Reason:** Zero qualifying method cards is permitted.

**Verification:** Confirm the output schema allows zero cards and that the artifact remains structurally valid.

**Limitation:** This result does not establish the semantic quality of the retained analysis.

### Example C — Unapproved Direction Used for Storyboard

**Related Check:** DET-P-07

**Input Condition:** Storyboard generation references a saved direction revision without the required approval.

**Expected Result:** Fail

**Reason:** The required approval boundary is violated.

**Verification:** Compare the storyboard's direction reference with saved approval metadata.

### Example D — Excessive Quality Repairs

**Related Check:** DET-X-06

**Input Condition:** The operation trace records two targeted quality repairs for one generation operation.

**Expected Result:** Fail

**Reason:** The documented limit is one targeted quality repair per operation.

**Verification:** Inspect the operation trace or equivalent repair metadata.

### Example E — Missing Discussion Draft Warning

**Related Check:** DET-P-11

**Input Condition:** An unresolved Discussion Draft is exported without its required status warning.

**Expected Result:** Fail

**Reason:** The export does not preserve required readiness information.

**Verification:** Compare the in-application artifact with the exported output.

---

## 10. Relationship to Expected Behavior Test Cases

Deterministic checks provide objective validation for applicable scenarios in `EXPECTED_BEHAVIORS.md`.

| Expected Behavior Test | Relevant Deterministic Checks |
|---|---|
| STR-01 — Accurate Source Observation | DET-S-02, DET-S-04 |
| STR-04 — No Qualified Method Cards | DET-S-05, DET-S-06 |
| STR-06 — Method Card Repair | DET-S-07, DET-S-08 |
| IDE-01 — Product Fact Preservation | DET-I-03, DET-X-04 |
| IDE-03 — Only One Qualified Direction | DET-I-02 |
| IDE-04 — Zero Qualified Directions | DET-I-02 |
| IDE-05 — Experimental Creative Direction | DET-I-04, DET-I-05 |
| IDE-06 — Creative Direction Approval Boundary | DET-I-06, DET-I-07 |
| STB-01 — Required Storyboard Structure | DET-P-01, DET-P-02, DET-P-05, DET-P-06 |
| STB-02 — Approved Direction Fidelity | DET-P-07, DET-P-08 |
| STB-03 — Dialogue Timing Feasibility | DET-P-03, DET-P-04 |
| STB-05 — Discussion Draft Status | DET-P-09, DET-P-10, DET-P-13 |
| STB-06 — Export Warning Preservation | DET-P-11, DET-P-12 |
| XMD-01 — Evidence Traceability | DET-S-02, DET-X-02 |
| XMD-02 — Version and Revision Consistency | DET-X-01, DET-X-02, DET-X-03 |
| XMD-03 — Bilingual Content Integrity | DET-X-04, DET-X-05 |
| XMD-04 — One Targeted Repair Limit | DET-X-06 |
| XMD-05 — Unsupported Claim Propagation | DET-I-03, DET-P-14 |
| XMD-06 — Status Integrity Across Handoff | DET-X-07, DET-X-08, DET-X-10 |

A deterministic check may cover only part of a test case.

For example, DET-I-02 can verify the number of generated directions, but it cannot determine whether the directions are genuinely differentiated.

Such test cases require complementary human review.

---

## 11. Implementation and Automation Guidance

The checks in this document describe expected validation behavior.

They may be implemented through unit tests, schema validators, integration tests, workflow assertions, export comparisons, or other appropriate test mechanisms.

Automation should prioritize checks that are:

- Objective and reproducible
- Based on accessible structured data
- Relevant to critical integrity requirements
- Stable across equivalent inputs
- Easy to diagnose when they fail

Checks should not be considered implemented solely because they appear in this document.

Where the tested application does not expose required metadata or validation behavior, the limitation should be recorded explicitly.

Human semantic evaluation remains necessary for evidence interpretation, creative quality, and production usefulness.

---

## 12. Reporting and Regression Integration

Deterministic validation results should be recorded alongside human evaluation results.

Each regression comparison should preserve:

- Application and specification versions
- Relevant model configuration
- Input and artifact identifiers
- Executed check IDs
- Observed validation results
- Failure evidence
- Retest outcomes

Regression reports should distinguish newly introduced failures from previously known issues and implementation gaps.

A successful deterministic validation run does not independently establish that the generated content is semantically correct or ready for production.

---

## 13. Document Integration

This document operates alongside:

- `QA_RUBRIC_v0.7.6.md` — Evaluation criteria and quality dimensions
- `EXPECTED_BEHAVIORS.md` — Scenario-based test expectations
- `HUMAN_REVIEW_PROCEDURE.md` — Human semantic and contextual evaluation
- `QA_TEST_RESULTS.csv` — Execution-level validation results
- `REGRESSION_REPORT.md` — Verified regression findings


This document establishes the deterministic validation framework for Video Anatomy v0.7.6. Implementation status and actual validation outcomes are recorded separately through test execution and regression reporting.
