# M9: team sample collection and creative evaluation

This rubric implements the confirmed M9 scope for the v0.6 workspace. The team
collects reference materials and evaluates the current task's analysis, two
directions, production brief and text storyboard. M9 does not search the web,
query a case library, fetch source URLs or inject other examples into generation.
Future multiple-input and user-selected library workflows remain a separate
product stage; they are not prerequisites for this evaluation.

## Evidence levels

Keep these conclusions separate in every review report:

| Evidence | What it establishes | What it does not establish |
| --- | --- | --- |
| Unit, contract, fake-provider and browser checks | The tested lifecycle, revision gates, persistence, adapter inputs, exports and recovery behavior | Real recognition accuracy, model instruction following or creative quality |
| Dedicated illustrated sample | A playable, explicitly fictional end-to-end demonstration with deterministic templates | Unrestricted feedback interpretation, real product efficacy or authentic OCR/ASR quality |
| Authorized real-provider run on a supplied clip | That exact model/configuration produced the recorded result for those bytes | General accuracy, repeatability across models, or a guaranteed cost/latency target |
| Human review of that result | Concrete observed errors, usefulness and changes needed for that task | Market effectiveness, conversion lift or statistically representative quality |
| Creator/production-team acceptance | The reviewed version is useful for that team's intended next step | Evidence that the final advertisement will perform well |

Use `not_run`, `not_reviewed`, `media_unavailable` or `unknown` when appropriate.
Do not turn an unknown result into a pass. Product confirmation, implementation,
offline verification, live validation and human acceptance are separate statuses.

## Prepare a case

Use the existing UTF-8 worksheets under `data/templates/`. Preserve their headers;
their legacy `project_id` column identifies the application's `task_id`.

1. In `video_manifest.csv`, record the source name/URL, local file identity,
   content hash if available, permission/rights note, language, duration and
   expected useful observations. Record unknown rights as unknown. A stored URL
   is provenance; the application does not retrieve it.
2. Record the exact task, applied M2 brief revision, reference video ID, reviewed
   analysis revision, selected language, direction revision and production output
   revisions. Record provider/model and prompt/configuration identity for a live
   run. Never place credentials in a sheet or screenshot.
3. Write the intended brand goal, audience, approved selling points and their
   conditions before judging the generated creative. Preserve fixed copy, names,
   numbers and units exactly. Confirmation permits use; it does not verify truth.
4. For recognition evaluation, prepare independent human observations from the
   actual clip. Do not derive the expected transcript from the model's output.
   Include English, Chinese and mixed-language examples, plus at least one case
   whose requested output language differs from the reference language when
   those materials become available.
5. Use `reference_review_v0.3.csv` for event/timing findings and
   `creative_review.csv` for output-quality findings. The former is an existing
   frame-based human worksheet, not the v0.6 task JSON schema or an import format.
   Copy measured source-frame metadata; do not guess FPS. Storyboard timing is
   planned seconds for the new video and must not be entered as source frames.

No live API call is authorized by this rubric. When the owner supplies samples,
credentials and an explicit budget, follow `docs/live-validation.md` for opt-in,
permitted media, pricing and bounded attempt accounting. Purchasing API access or
providing a key alone is not a recorded test result or a blanket spend budget.

## Review criteria

Record `pass`, `needs_revision`, `blocked` or `not_reviewed` plus a concrete example
and exact artifact reference for each criterion. The existing optional 1–5 team
rating is a convenience for discussion, not a validated scale or an effectiveness
score; the written finding takes precedence. Do not collapse the rows below into
a marketing-performance score.

| Criterion | Review method | A useful result | Flag for correction |
| --- | --- | --- | --- |
| Hook and narrative divergence | Read A/B side by side; describe each opening and progression in one sentence | A uses the reviewed reference progression; B reorganizes useful elements into a materially different hook or story | Cosmetic wording changes, identical progression, or differences only in staff/resources |
| Brand, audience and goal fit | Trace each main choice back to applied M2 inputs | The direction explains why the opening, core message and CTA serve this task | Generic brand language, a different audience/goal, or invented audience research |
| Evidence grounding | Open each cited event in the exact reviewed analysis; compare reason with observed text/visuals | Citation identifies the specific borrowed element; the reason remains an interpretation | Missing/wrong event, wrong revision, a claim that the clip never showed, or popularity treated as causal proof |
| Coverage honesty | Compare UI/summary with observed coverage and attempted capabilities | Sparse visual samples are labeled as sampled; speech/OCR preserve timing and original wording; missing categories stay unknown | Continuous shot-boundary claims from sparse samples, fabricated audio, or `not_analyzed` presented as absence |
| Original production proposals | Inspect shots with no reference citation | An original shot can have an empty citation list and is identified as a proposed creative addition | A fabricated reference time attached to an original scene, or new product facts justified by the word “original” |
| Claims and qualifications | Trace every product assertion through M2 statement, qualification, supporting note and prohibition | Exact limitations, numbers, units and conditions survive in the brief and where the assertion is used | Broadened claims, dropped test conditions, new efficacy promises, or user-provided support presented as independently verified |
| Resource fit | Compare people, locations, footage and production notes with applied inputs | Proposed resources are feasible or clearly marked to prepare; missing resources are not asserted to exist | Presenter required despite a no-presenter constraint, unavailable locations assumed, or unexplained production scope |
| Production usefulness | Ask a teammate to explain what they would prepare and shoot | Brief states goal/message/structure/resources; shots name subjects, actions and settings; optional text/audio can remain empty | “Show the benefit” with no action, repetitive filler, or equipment/budget detail that obscures the basic plan |
| Planned timing and readability | Read aloud spoken copy and preview screen text against allocated shot seconds | Contiguous shots cover the requested target duration; text can be read/spoken at a reasonable pace | Source-video duration substituted for target duration, gaps/overlaps, or dense copy squeezed into a short shot |
| Bilingual and fixed-copy preservation | Compare reference transcription, M2 fixed copy and chosen output language separately | New narrative uses the selected language; source evidence, brand names and approved fixed copy remain exact | Silent translation or abbreviation of fixed copy; loss of Chinese characters, mixed-language words, numbers or units |
| Manual-edit auxiliary integrity | Change a hook/story materially, save and inspect explanations and later production | Earlier rationale/resources/citation reasons are marked as belonging to the earlier version; later production follows approved current text and M2 constraints | Old presenter requirements or evidence explanations silently reused as current after a presenter-free rewrite |
| Practical decision support | Ask which direction the team would choose and what needs revision | Reviewer can explain a choice and identify concrete next edits | Unsupported confidence percentages, effectiveness promises, or approval confused with factual verification |

Preserving a condition only in an appendix may be insufficient if the proposed
spoken or on-screen assertion is misleading without it. Review the assertion in
its intended scene, not just whether the condition appears somewhere in JSON.

## Lifecycle checks during a review

Exercise the behavior on a copied/demo task when a destructive step would remove
media needed for further evaluation:

- Apply and confirm an analysis correction; verify original evidence remains in
  history and new creative work uses the confirmed revision.
- Type M5/M6/M7 draft text, switch tasks, reopen and verify the text is retained.
  Pending edits must block the relevant new creative actions until resolved.
- Save a direction edit and approve the exact new revision. Selection alone must
  not authorize production; automatic draft saving must not silently approve it.
- Change generation language and verify old work becomes historical without
  re-running reference recognition or rewriting original evidence/fixed copy.
- Export after changing dialogue: save successfully before exporting, then
  compare file wording with that saved revision. A failed save must not download
  an older version as if it contained the edits.
- Export historical work and verify both filename and document identify it as
  historical. A deleted source must be labeled unavailable; its old analysis and
  creative work remain readable while video playback is unavailable.

## Record and triage a finding

For each finding, capture: reviewer/date, evidence level, case ID, exact artifact
and revision, criterion, expected behavior, observed example, impact, proposed
correction, owner and disposition. Include safe screenshots or short text excerpts
when they help reproduce the issue. Keep original observations separate from
interpretations and new creative suggestions.

Treat fabricated evidence, lost qualifications, unauthorized changes to approved
copy, silent draft loss and wrong-version approval/export as blockers for using
that output. Wording polish and optional production elaboration can be recorded
as revisions. If a source or API run is unavailable, leave that criterion untested
and continue with independent workflow checks.

After corrections, repeat the affected cases and retain both results. A report
should state the number and nature of reviewed cases, actual failures and
remaining gaps; it should not extrapolate a few team samples into an accuracy or
effectiveness claim. Additional supplied samples can strengthen creative review
without changing the current no-search/no-library runtime scope.
