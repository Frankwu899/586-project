# QA Regression and Current-Version Evaluation Report

**Project:** Video Anatomy  
**Report Type:** Current-Version QA Evaluation and Regression Readiness  
**Evaluation Scope:** Structure, Ideas, Production/Storyboard, and Cross-Stage Workflow  
**Test Evidence:** LumaCup Synthetic Sample, REAL-01 Spoken Toddler Cup, REAL-02 Dior Visual TVC  
**Test Results Reference:** `docs/evaluation/QA_TEST_RESULTS.csv`  
**Evaluation Status:** Completed targeted manual evaluation; historical regression comparison not performed

---

## 1. Executive Summary

This report documents observed behavior from targeted quality assurance testing of the Video Anatomy application.

Testing covered a synthetic sample workflow and two real advertising videos with different content characteristics:

- **LumaCup Synthetic Sample:** Sample-mode analysis, creative direction generation, approval, production handoff, version persistence, and storyboard output.
- **REAL-01 Spoken Toddler Cup:** A 28.8-second TikTok-style testimonial advertisement containing spoken narration, product demonstration, and on-screen text.
- **REAL-02 Dior Visual TVC:** A 30-second luxury cosmetics advertisement featuring music lyrics, visual styling, product application, brand imagery, and on-screen product claims.

The evaluation found that the application successfully supported the reviewed end-to-end workflow for REAL-01, including evidence extraction, Structure interpretation, creative direction generation, approval, editing, and Production handoff.

REAL-02 exposed important limitations in visual evidence validation and on-screen text extraction. These limitations reduced the completeness of the available evidence and potentially affected downstream interpretation.

**Overall assessment:** The reviewed workflow demonstrated functional capability, but evidence extraction completeness and failure recovery require further validation before broader reliability claims can be made.

**Regression determination:** Not established. No controlled historical-version baseline was executed.

## 2. Test Scope and Methodology

### 2.1 Evaluated Areas

The manual evaluation examined:

1. Video ingestion and multimodal evidence extraction.
2. Visual observation and speech transcription accuracy.
3. On-screen text extraction and completeness.
4. Structure interpretation and evidence grounding.
5. Creative direction generation, editing, and approval.
6. Production brief and storyboard handoff.
7. Version persistence and selected export behavior.
8. Partial extraction failure handling.
9. Cross-stage evidence consistency.

### 2.2 Evaluation Approach

Testing combined direct UI interaction, manual comparison against source videos, inspection of generated outputs, and workflow verification.

Observed results were recorded in `QA_TEST_RESULTS.csv` using the following status categories:

- **Pass:** The specific observed behavior met the tested expectation.
- **Fail:** The observed behavior did not meet the tested expectation.
- **Needs Review:** The behavior was partially acceptable or requires further investigation.
- **Blocked:** A dependency prevented the intended test from proceeding.
- **Not Tested:** The check was not executed or sufficient evidence was unavailable.

A Pass applies only to the documented test case. It does not imply complete system-level verification.

### 2.3 Limitations

This evaluation was limited to one synthetic sample and two real video assets. It was not a statistically representative benchmark.

The complete deterministic check suite was documented but not executed as an automated test run.

No controlled historical-version comparison, cross-browser compatibility matrix, load test, or comprehensive frame-by-frame accuracy benchmark was performed.

The exact source commit and runtime configuration for the tested application were not independently recorded in this report. The GitHub commit used to submit QA documentation should not be treated as the application build identifier.

## 3. Test Asset Findings

### 3.1 LumaCup Synthetic Sample

**Scope:** Sample-mode functional and workflow testing.

Observed results included:

- A timeline containing 10 visual observations and 4 text groups, with no speech segments.
- Successful generation of two sample creative directions.
- Selection and approval of direction B.
- Production brief and three-shot storyboard generation.
- Successful saving and restoration of production versions.

The sample storyboard totaled 15 seconds, while the reference sample was 10 seconds. This is a duration-alignment observation rather than a confirmed defect because the applicable output-duration requirement was not independently established.

**Assessment:** The tested sample workflow passed its functional checks.

**Limitation:** Synthetic sample outputs do not validate real-video recognition accuracy or production quality across diverse advertisements.

### 3.2 REAL-01 — Spoken Toddler Cup

**Asset:** `Spoken-9-29s.mp4`  
**Duration:** Approximately 28.8 seconds  
**Content Type:** Vertical, spoken testimonial advertisement for a toddler straw cup.

#### Evidence Extraction

The successful analysis produced:

- 40 visual observations.
- 18 on-screen text groups.
- Timestamped speech transcription segments.

Manual review found that the reviewed transcript content and timestamps aligned with the source video.

Some transcript segments were divided in the middle of natural spoken sentences. This did not establish a transcription-content error, but it affected segmentation readability.

The reviewed visual observations were consistent with the source material, and no clear unsupported brand identification was found in the examined outputs.

#### Structure Interpretation

The generated Structure interpretation centered on a leak-frustration argument supported by product demonstration and repeat ownership.

This interpretation reflected the observed testimonial, including the leaking-cup problem, handling and lid demonstration, and repeated purchase references.

The interpretation appropriately treated the testimonial as an advertiser-presented experience rather than independent proof of product performance.

#### Ideas and Production

The user entered and saved project context, including target audience, platform, product positioning, and relevant product features.

After an initial provider timeout was addressed, the application generated two distinct creative directions.

Direction A was selected, edited, saved as a new version, and approved.

The Production workflow then generated a brief and storyboard based on the approved direction. PDF export was verified, producing a five-page document.

#### Assessment

**Result:** The reviewed REAL-01 end-to-end workflow passed its primary functional checks.

**Remaining concern:** Speech segmentation boundaries require review. Successful completion after timeout adjustment does not establish reliability under default provider timeout settings.

### 3.3 REAL-02 — Dior Visual TVC

**Asset:** `TVC-24-30s.mp4`  
**Duration:** Approximately 30 seconds  
**Content Type:** Landscape luxury cosmetics advertisement with background music, product visuals, and on-screen claims.

#### Evidence Extraction Failure

The application reported:

> A visual batch failed evidence validation. Completed samples are retained.

The UI indicated partial analysis completion and preserved available observations.

Retained evidence included visual descriptions of product styling, lip application, dessert imagery, product arrangements, and the closing brand imagery.

This behavior demonstrated partial-result preservation, but the visual and on-screen text channels did not complete successfully.

#### On-Screen Text Completeness

Manual comparison against the source video identified missing or incomplete text evidence:

| Approximate Timestamp | Source Video Text | Observed Issue |
|---|---|---|
| 00:05 | PH-ACTIVATED COLOUR | Not captured in reviewed output |
| 00:15 | ULTRA SHINE | Not captured in reviewed output |
| 00:18 | 24H HYDRATION | Not captured in reviewed output |
| 00:28–00:30 | DIOR ADDICT | Only DIOR captured in reviewed output |
| 00:28–00:30 | THE NEW LIP GLOW OIL | Not captured in reviewed output |

These are advertised product claims and branding elements appearing in the source video. Their presence in the advertisement does not independently establish product efficacy.

The omissions are confirmed at the reviewed-output level. The underlying cause was not isolated and may involve sampling coverage, extraction behavior, or the incomplete visual batch.

#### Structure Interpretation

Despite incomplete evidence, the application produced a Structure interpretation emphasizing sensory association, stylized product imagery, application, and recognizable brand identity.

Reviewed descriptions were generally grounded in available observations.

The interpretation also included appropriate uncertainty statements and avoided unsupported conclusions, such as treating dessert imagery as proof of edible ingredients or product flavor.

However, the missing on-screen claims limited the completeness of the resulting product-message analysis.

The downstream impact is plausible, but direct causation between a specific extraction failure and a specific Structure omission was not experimentally verified.

#### Music Lyrics

The speech channel included English lyrics from the background music.

This behavior requires further review to determine whether the application consistently distinguishes musical lyrics from spoken advertising narration in downstream interpretation.

#### Assessment

**Result:** Visual evidence validation and on-screen text completeness failed the reviewed expectations.

**Positive behavior:** Partial evidence was preserved, and the generated Structure output disclosed uncertainty.

**Remaining concern:** Downstream interpretation may omit important product messaging when extraction is incomplete.

A complete REAL-02 Ideas-to-Production workflow was not verified.

## 4. Issue Register

| Issue ID | Severity | Finding | Evidence | Recommended Action |
|---|---|---|---|---|
| QA-ISSUE-01 | High | Visual batch evidence validation failure | REAL-02; QA-014 | Investigate batch validation failure and improve retry or recovery diagnostics |
| QA-ISSUE-02 | High | Incomplete on-screen product claim extraction | REAL-02; QA-015 | Evaluate OCR coverage, sampling strategy, and missing-text detection |
| QA-ISSUE-03 | Medium | Downstream Structure coverage limited by incomplete evidence | REAL-02; QA-019 | Improve evidence-completeness signaling and require review of missing claim coverage |
| QA-ISSUE-04 | Low | Speech segments split at unnatural sentence boundaries | REAL-01; QA-007 | Review transcription segmentation and sentence-boundary handling |
| QA-ISSUE-05 | Medium | Provider timeout interrupted initial creative direction generation | REAL-01; QA-011 | Evaluate timeout defaults, user feedback, and retry behavior |
| QA-ISSUE-06 | Low | Music lyrics appear in the speech channel | REAL-02; QA-018 | Clarify speech-versus-music labeling and downstream treatment |

**Severity note:** Severity values are QA triage recommendations based on the observed impact. They are not confirmed engineering priorities or root-cause classifications.

## 5. Cross-Stage Assessment

### 5.1 Evidence to Structure

REAL-01 demonstrated a grounded transition from observed evidence to an interpretable persuasive structure.

REAL-02 demonstrated that Structure generation can continue using partial evidence, but missing on-screen claims create a risk of incomplete message interpretation.

### 5.2 Structure to Ideas

REAL-01 successfully generated two creative directions after project context was applied.

The evaluation did not establish whether REAL-02's incomplete evidence would propagate into specific creative direction errors because that downstream workflow was not fully tested.

### 5.3 Ideas to Production

REAL-01 demonstrated successful direction editing, version saving, approval, and Production handoff.

The generated brief and storyboard were based on the approved creative direction.

The synthetic sample also supported the tested approval-to-production workflow.

### 5.4 Overall Cross-Stage Finding

The application demonstrated coherent cross-stage workflow behavior for the reviewed successful case.

However, successful stage transitions should not be interpreted as proof that all upstream evidence is complete or accurate.

## 6. Regression Evaluation

### 6.1 Historical Baseline Availability

**Historical baseline: Unavailable for controlled comparison.**

No previous application version was executed with the same source assets under a controlled comparison procedure.

As a result, the evaluation cannot establish whether the observed defects:

- Were introduced by the current version.
- Already existed in earlier versions.
- Were resolved relative to a previous version.
- Vary according to provider or runtime configuration.

### 6.2 Regression Status

**Regression status: Not Tested / Unverified.**

This report should not be interpreted as a regression pass or as evidence that no regressions exist.

### 6.3 Recommended Future Regression Baseline

For a future release comparison:

1. Record the exact application commit, model/provider configuration, and relevant runtime settings.
2. Reuse the same video assets and documented project context.
3. Execute the same deterministic checks and manual review procedures.
4. Compare evidence completeness, grounding, workflow success, and export behavior.
5. Record new failures, resolved issues, and unchanged limitations separately.

The current QA results provide a documented observation baseline for that future work, but not a historical regression comparison.

## 7. Recommended Follow-Up Priorities

**Priority 1 — Evidence extraction reliability**

Investigate the REAL-02 visual batch validation failure and the missing on-screen text elements. Retest using the same source video after a targeted fix.

**Priority 2 — Evidence completeness and downstream safeguards**

Make incomplete visual and text evidence more actionable for reviewers. Evaluate whether important missing product claims can be detected or flagged before downstream interpretation.

**Priority 3 — Provider resilience**

Review timeout behavior and user-facing recovery options for creative direction generation.

**Priority 4 — Transcription quality**

Improve sentence segmentation and evaluate whether music lyrics require separate labeling from spoken narration.

**Priority 5 — Repeatable regression testing**

Execute the documented deterministic checks and establish a controlled build-to-build baseline.

## 8. Final QA Conclusion

The targeted evaluation demonstrated that Video Anatomy can support a complete reviewed workflow from real-video evidence analysis through Structure interpretation, creative direction approval, and Production generation.

The strongest observed result was REAL-01, where the reviewed evidence and generated interpretation remained grounded in the source video and the workflow completed successfully.

REAL-02 revealed material weaknesses in visual batch validation and on-screen text completeness. These issues should be prioritized because incomplete evidence can reduce the usefulness of downstream analysis even when generated interpretations are cautious and internally coherent.

**Final disposition:** Targeted manual QA documented; known issues remain open; historical regression comparison unverified.

This report does not certify production readiness or comprehensive system reliability.

---

## 9. Supporting QA Documentation

- `docs/evaluation/QA_RUBRIC_v0.7.6.md`
- `docs/evaluation/EXPECTED_BEHAVIORS.md`
- `docs/evaluation/DETERMINISTIC_CHECKS.md`
- `docs/evaluation/HUMAN_REVIEW_PROCEDURE.md`
- `docs/evaluation/QA_TEST_RESULTS.csv`

**Evidence integrity statement:** All test findings are based on documented observations. Unexecuted checks and unavailable historical baselines are explicitly identified rather than reported as passing results.
