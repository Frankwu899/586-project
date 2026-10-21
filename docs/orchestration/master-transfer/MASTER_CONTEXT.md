# Video Anatomy — Current Master Context

Snapshot: 2026-10-17, America/Los_Angeles.
Owner/coordinator: Frank (Yuqing Wu). Course project: USC COMM586.
Read DECISIONS.md and STATUS.md alongside this document.

## Why this project exists
Video Anatomy helps a brand, advertiser, agency or content team prepare a product
marketing video. Recognition is a foundation; the main value is turning reference
evidence plus the brand's own needs into a creative decision and usable production
instructions. Frank explicitly wants to avoid a product that only dissects videos
without helping someone decide what to create.

The demonstration story: a brand is preparing a new video, provides its context
and one reference, reviews the evidence, compares creative directions, approves
one, and obtains a production creative brief plus a timed text storyboard.

An early course proposal included rich analysis of 1–3 minute videos, tags, hooks,
speech/OCR, timeline/shot structure; possible later work included batch comparison,
creative/hook/pacing scoring, A/B suggestions and organic-versus-paid inference.
Those aspirational ideas do not override the narrower confirmed demo. In particular,
accurate exhaustive shot segmentation is NOT required in the latest first-demo
scope; see the newly accepted sampled-evidence decision.

Open-source recognizers and JEV/RAG were explored earlier. Current foundation uses
replaceable providers with OpenAI first. JEV and model training are deferred.
Do not invent a requirement to train a model merely because earlier coursework
discussion explored it. Collected examples are not automatically a training set.

## Team and working environment
The course team is approximately five people; earlier plans allocated two or three
to coding and others to data collection/evaluation. Frank leads product decisions
and integration. Andrea has been discussed as a coding/recognition collaborator,
but do not assume her availability or assign her work that blocks independent progress.
Use GitHub collaboration and clear module ownership.

Frank uses a home PC and a MacBook Pro at school. Cloud development is preferred
for unattended coding; local startup remains necessary for the eventual team demo.
Git commits transfer source, not Python/Node environments, databases, videos,
API secrets or private conversation histories.

Frank is relatively unfamiliar with Git branching. Explain necessary actions in
ordinary Chinese, automate authorized Git operations, and avoid making him copy
folders or assemble many prompt fragments when tools can handle the transfer.
Differentiate conversation branches, repository branches, PRs and deployments.

The user likes module-by-module grill, confirmation, English implementation
documents, Codex execution, tests and a concise return receipt. He now wants the
same process coordinated within one Codex conversation with parallel specialists.
The controller must support ordinary discussion; a request to discuss is not a
request to edit application code immediately.

## Confirmed core user journey
1. Create or reopen a creative task.
2. Provide task-local brand/product facts and task goals.
3. Upload one reference video and run recognition.
4. Inspect evidence, correct permitted text/labels, and explicitly confirm review.
5. Generate two directions, refine/select, then explicitly approve one exact revision.
6. Generate a production creative brief and a text storyboard.
7. Edit allowed content and export using the agreed currentness/version rules.

Steps 2 and 3–4 can occur in either order; M6 is where ready formal inputs and
reviewed analysis converge. Do not enforce brand entry before reference exploration.
The current product is one task with one brief and one reference, not a public
multi-user asset platform or multi-video comparison system.

## Module responsibilities
| Module | Responsibility | Main dependency/output |
| --- | --- | --- |
| M1 | Task creation, saving/resumption and progress/navigation | Persistent task; consumes readiness states |
| M2 | User-supplied brand/product/task inputs | Applied input brief, claims and constraints |
| M3 | Reference upload, playback and supported media | Measured media and playable derivative |
| M4 | Vision/OCR, speech and normalized evidence | Observations, coverage, failures, references |
| M5 | Analysis presentation, permitted corrections and review | Reviewed effective analysis revision |
| M6 | Two directions, feedback, selection and explicit approval | Approved current direction revision |
| M7 | Generated production brief and text storyboard | Versioned editable production output |
| M8 | Export/delivery | Portable saved output with currentness/source metadata |
| M9 | Team-reviewed examples and evaluation material | Optional supporting material; no mandatory gate |
| M10 | Contracts, provider boundaries, storage, validation/migration | Shared consistent infrastructure |

Do not confuse M2 and M7 because both are sometimes called brief.
Do not rebuild M1–M9 from scratch: foundations already span those modules.

## M2 product agreement
- Task-local brand/product profile. Brand libraries, cross-task reuse and complex
  exception flows are deferred.
- Editorial Studio visual style: warm paper surface, serif headings, rust accent.
  Organize around readable summaries, focused edits and one current question.
- Manual filling, pasted notes, optional AI extraction/suggestions.
- AI proposes; user adopts. No invented product facts or silent input replacement.
- Drafts may be incomplete. Formal Apply requires brand, product, audience,
  one main platform, one main objective, positive target duration, and at least
  one user-confirmed usable selling point.
- Supporting evidence is optional. User confirmation grants permission to use a
  statement; it is not proof the statement is true.
- Preserve qualifications, supporting notes and prohibitions downstream.
- Draft autosave and formal Apply are separate. Draft edits alone do not make
  existing outputs stale. A meaningful Apply versions inputs and invalidates
  affected approval/currentness. No-op Apply preserves the formal revision.
- Pending structured edits must be resolved before specified new creative actions.
  Notes/unaccepted proposals alone are not equivalent to pending applied content.
- Preserve histories. Do not silently overwrite edited work with regenerated content.

The M2 implementation has now landed on its feature branch as PR #4, with v0.5.
Older statements that these contracts are proposals-only are superseded by the
implementation report, while human/live quality acceptance remains pending.
Details live in docs/handoff/m2-brief-experience.md and docs/decisions/m2-v0.5.md.
Do not reimplement the independent editor channel or bypass atomic admission gates.

## Newly confirmed first-demo choices
On 2026-10-17 around 00:54 Los Angeles, Frank said M2 was done and agreed to the
previous response's Q1–Q3:
- M5: sampled visual evidence plus timestamped speech/visible text, with honest
  sampling coverage; accurate continuous shot segmentation deferred.
- M6: A follows the reference structure more closely; B reuses useful elements
  with a different narrative organization. Hook or narrative must differ
  meaningfully. Show brand fit and production needs; no unvalidated effect score.
- M7: edit descriptions, dialogue, subtitles, sound and CTA first; retain generated
  shot order and durations. Add/delete/reorder/timing editing deferred.

These settle those three choices only. They do not complete every remaining
module's PRD or approve every recommendation from the four discovery agents.

## Evidence, languages and timing
English, Chinese and mixed content are requirements for speech, visible text,
user inputs, corrections, persistence and exports. Keep original-language evidence;
field keys/enums remain stable English identifiers. Real language quality is still
unverified. Do not call Unicode storage tests recognition-accuracy tests.

Reference coordinates: measured zero-based integer frame ranges with exclusive
ends, stable IDs, real frame boundaries and rational FPS. Preserve playback/source
alignment and original uploaded assets. Production storyboard planning uses seconds
independently of the reference frame rate. Follow current schema rather than
inventing units or editing immutable timing/ID fields in a free-form UI.

Observed evidence and inferred interpretation must remain distinguishable.
Corrections may change recognized text, visual descriptions, section roles and
permitted subject/action/product-presentation labels. Preserve machine originals
and versioned corrections. Review does not assert universal machine correctness.

Only public engagement indicators such as views/likes/comments were available in
earlier data discussions. Do not invent retention, clicks, conversion or causal
improvement. Unverified effectiveness statements must remain hypotheses with
proposed tests, not evidence of success.

Upload is the dependable first input path. A saved source URL does not prove
download/ingestion from that platform. Inspect support before promising link intake.
Current foundation's supported HEVC claim is limited; see STATUS.md.
Do not describe the sparse recognition output as exhaustive scene/shot detection.

## Known historical discovery findings and remaining work
Four read-only agents inspected PR #3 head before M2 finished:
- M3/M4/M5 already provided media, recognition interfaces, correction/review.
- Recognition samples were one-frame sections, not continuous narrative segments;
  independent speech events need honest presentation.
- M6 already compared/edited/refined/selected/approved directions. Semantic
  distinctness and real creative usefulness were not quality-validated.
- M7/M8 shared Production.tsx; Markdown/CSV exports already existed. Text editing,
  currentness and unsaved edits require careful product UX.
- M1 already created/listed/reopened tasks. M9 had manual guides and templates.

M2 subsequently changed shared UI, services, migration, readiness and exports.
Treat the above as a discovery baseline and inspect the PR #4 delta before changes.
In particular, do not repeat obsolete claims that M2 cannot autosave independently
or that pending-input gates have not been implemented.

Remaining discussion can cover:
- M5 formal correction vs review actions and unsaved-edit handling.
- M3/M4 start/retry/status UI within existing scope.
- M6 comparison summaries, evidence access, feedback and stale rationale after edits.
- M7 content quality/depth and language behavior.
- M8 usable formats and handling unsaved/current/historical results.
- M1 navigation, recovery and readiness cues.
- M9 evaluation-only material versus runtime example use.
- Shared visual/navigation specification using M2 as the existing design reference.

## Execution and communication rules
Use at most three independent consequential questions per round, recommendations
and concrete examples. Research code facts yourself. Respect prerequisite decisions.
Show a small UI prototype when a visual choice cannot be judged in prose.
Keep the latest decision frontier and reasons so future chats do not restart.

After the user confirms a coherent module and authorizes implementation, generate
English PRD, UIUX, contract impact, acceptance criteria, execution prompt and receipt.
Perform permitted implementation/Git/testing steps autonomously.
Do not infer merge/deploy/paid-call approval from product confirmation.

The user postponed manual local verification to advance product/UI work. That
choice does not convert reported implementation into acceptance. He plans to obtain
API credits and test separately; there is still no confirmed paid-test amount.
A historically suggested US$20 and approximately five-minute analysis target were
provisional, not measured performance or spending permission.

Keep the actual stack (React/Vite/TypeScript, FastAPI/Python, SQLite, FFmpeg/provider
adapters) unless an authorized change requires otherwise. Current versions/commands
come from lockfiles and README_SETUP.md, not remembered installation instructions.

## Context and continuity limits
This handoff transfers known project knowledge, decisions and source pointers.
It does not guarantee literal reproduction of the entire master conversation.
Earlier excerpts were incomplete; missing screenshots and exact wording cannot
be invented. The previous Codex chat error cannot be diagnosed without evidence.
Keep these limitations explicit and narrow; they do not block known project work.

