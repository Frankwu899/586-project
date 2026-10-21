# M2 — Brand & Task Input PRD

Status: implementation handoff, 2026-10-17. Product direction: single-task demo. Visual direction: Editorial Studio, selected by the project owner.

## 1. Purpose and terminology

M2 captures what the user knows about their brand, product and current communication task. It turns supplied information into a user-confirmed input brief that downstream generation can use safely and predictably.

**M2 input brief is not M7 Creative brief.** M7 produces the production Creative brief and text storyboard after M6 direction selection, refinement and explicit approval. Use “Brand & task” in M2 navigation and “Apply inputs” for its confirmation action. Never label M2 as the generated Creative brief.

“Profile” means the brand/product information inside this task. It is not an account profile, organization database or reusable brand library in this release.

## 2. Confirmed scope and design defaults

Confirmed: one task, one reference video, one primary platform and one primary communication goal; incomplete information may be saved; reference upload/review can start before M2 completion; structured cards work with short free-text input; AI proposes and the user accepts; user-confirmed claims need not have mandatory supporting documents; Editorial Studio is the selected style; cross-task reuse and complex exceptions are deferred.

Implementation defaults specified by this handoff, rather than new owner confirmations: English interface copy; original English/Chinese/mixed input preserved; server-backed debounced draft saving; a light Editorial Studio theme as the release target; deterministic missing-field guidance with optional AI assistance; no automatically selected audience, platform, goal or duration. These defaults make the agreed scope executable without introducing new product branches.

## 3. Users and primary scenario

A brand or agency teammate has a product to promote and a reference video that may help them find a creative direction. They may know the product facts while remaining unsure about the desired creative treatment.

Primary scenario: create/open a task; add the information already available; attach and inspect one reference; complete and confirm the minimum task inputs; generate two directions; refine and explicitly approve one; generate the M7 Creative brief and text storyboard; export.

M2 must support “I have the details” and “I need help deciding” inside this same flow. These are input states, not separate onboarding modes, personas or branching workflows. Knowing a hook, pacing, visual style or creative direction is not an M2 prerequisite.

## 4. Upstream and downstream boundaries

| Module | Relationship to M2 |
|---|---|
| M1 | Owns the task and reopening it. M2 belongs to one task. |
| M3–M5 | Own reference upload, analysis and correction/review. They do not require a complete M2 brief. M2 displays only a compact reference status and links into those existing views. |
| M6 | Requires a complete applied M2 revision and confirmed current reference analysis. Produces two creative directions, handles creative refinement and explicit direction approval. |
| M7 | Requires the approved current direction and matching upstream revisions. Produces the Creative brief and text storyboard. |
| M8 | Exports current eligible outputs. Existing stale-output and approval safeguards remain. |
| M10 | Owns shared models, schemas, generated types, migrations and provider contracts. Explicit proposed changes are isolated in document 03. |

## 5. Function and subfunction tree

```text
M2 Brand & task
├── 1. Task-local input workspace
│   ├── Brand & product summary and inline editing
│   ├── This task summary and inline editing
│   ├── Compact reference status / open reference review
│   └── Completion and next required action
├── 2. Capture information
│   ├── Manual field editing
│   ├── Paste supplied notes
│   ├── One current question with concrete choices / custom answer
│   └── Optional details disclosure
├── 3. AI assistance
│   ├── Extract facts from supplied text with source excerpts
│   ├── Propose task choices when requested
│   ├── Review, edit, accept or dismiss proposals
│   └── Preserve manual input on failure or stale response
├── 4. Claims and constraints
│   ├── Selling-point wording
│   ├── Optional supporting notes / source links / qualifications
│   ├── User confirmation that a claim may be used
│   └── Approved messages and prohibited claims
├── 5. Draft and applied input lifecycle
│   ├── Persist incomplete draft and resume
│   ├── Validate and review the applied payload
│   ├── Apply a meaningful new brief revision
│   ├── Discard unapplied draft changes
│   └── Preserve history and invalidate dependent current results
└── 6. Downstream readiness
    ├── Required input and reference review checklist
    ├── Pending-change and stale-proposal protection
    └── Hand off exact applied revision to M6
```

## 6. Information rules

All fields may be incomplete in a draft. “Required” below means required before applying a complete brief and generating directions, not required to open the task, save a draft or analyze a video.

| Group | Information | Required at application / M6 | Rule |
|---|---|---|---|
| Brand & product | Brand/company | Yes | A working brand label is acceptable; a legal entity name is unnecessary. |
| Brand & product | Product/service | Yes | Name plus enough description to identify what is being promoted. |
| Brand & product | Selling points | At least one usable claim | User confirms the exact wording and any supplied qualification. |
| Brand & product | Claim support | No | Optional user notes and links. Links are stored as references, not fetched or verified in this release. |
| Brand & product | Approved messages | No | Additional user-authorized copy. Do not populate by guessing. |
| Brand & product | Prohibited claims | No | Explicit “do not say” restrictions. Blank means not supplied, not “no restrictions exist.” |
| This task | Target audience | Yes | Plain language, such as “office commuters carrying a drink.” A formal persona is unnecessary. |
| This task | Primary platform | Yes | One value; allow a custom named platform. No platform-dependent validation that requires live platform specifications. |
| This task | Primary communication goal | Yes | One value, such as demonstrate everyday usefulness, build brand recall, or encourage a product-page visit. Custom wording allowed. |
| This task | Target duration | Yes | Explicit positive number of seconds accepted by the current contract; preserve any existing repository bounds. Placeholder examples are not defaults. |
| This task | Footage, presenters, locations | No | Free text. “Unknown” differs from “none available.” |
| This task | Tone, production limits | No | Free text; constraints remain visible in final review. |
| Creative exploration | Hook, pacing, creative treatment | No | May remain undecided until M6. Do not require an invented direction in M2. |

Do not add a separate CTA, output-language, audience-demographics or campaign-budget schema in this demo. An action objective may be expressed in the communication goal. Additional task intentions can be expressed in the goal or existing optional text without generating multiple deliverables.

## 7. Interaction and AI behavior

### 7.1 Structured information with natural input

The primary screen contains a readable brand/product summary, a task summary and one contextual question. Users can edit any summary item directly. A compact “Paste your notes” disclosure accepts existing product/campaign text. It is an input source, not a permanent conversation transcript.

The next question targets a missing requirement. Ask brand/product/claim facts first when needed; ask audience, platform, goal and duration next. Users may skip a question for now or move to the reference. “I’m not sure yet” leaves the value unset and never becomes the literal value sent downstream.

Show two or three concrete suggestions only where useful; always offer a custom answer. Choices based on examples must be labeled as suggestions. The manual path works with no AI provider configured.

### 7.2 AI extraction and suggestions

Extraction reads only the supplied notes and proposes supported facts. Each fact proposal includes a short exact source excerpt. An absent fact stays absent. Brand identity, product capabilities, quantitative performance, certifications, endorsements and legal permission are never invented.

Task suggestions, such as a possible audience or communication goal, must be labeled “Suggested”; they require explicit acceptance. Creative opinions from the reference cannot establish facts about the user's product. This release does not add web research or another video-analysis pass to M2.

Proposals are separate from draft values until accepted. Selecting, editing or dismissing candidate rows happens locally in proposal review. “Use selected details” adopts the selected batch in one atomic draft update if its source draft version is still current; it does not change the applied brief. Existing populated values display a current/proposed comparison before replacement. Unselected and dismissed proposals have no effect. A response based on an older draft cannot overwrite newer edits; the user can rerun it.

### 7.3 Claim handling

Each selling-point row has wording, optional support, optional qualifications and a “Confirmed for use” control. Editing wording or qualifications clears that confirmation. AI extraction never prechecks it. Confirmation means the user permits that wording; the interface must not say “verified” or imply evidence validation.

Example: supplied “keeps drinks warm for up to 6 hours in our indoor test” must retain “up to” and the indoor-test condition. A suggestion cannot silently become “keeps drinks hot all day.” A prohibition such as “do not claim dishwasher safety” remains part of downstream context.

Unconfirmed rows can remain in the saved draft but are explicitly excluded from the applied usable claims. The review shows included and excluded rows before application. At least one included, confirmed claim is required. A simple user review is required for conflicting source statements; no universal semantic contradiction detector or evidence-verification engine is promised.

## 8. Persistence and revisions

1. Edit: maintain local input immediately and persist a partial task draft after a short debounce. Show “Saving draft…” until acknowledged, then “Draft saved.”
2. Review: show the exact proposed usable inputs, exclusions and missing requirements. Required omissions block application; they do not block saving or reference work.
3. Apply: explicitly confirm the complete input. Atomically create a new formal brief revision only when the semantic applied payload changes. Reflect invalidation in the same committed operation.
4. Resume: load the latest saved draft and the applied brief separately. Make unapplied differences visible. A previously saved draft survives refresh and reopening on the same persisted installation.
5. Discard changes: after a clear confirmation, restore the editable draft from the last applied brief. With no applied brief, reset only the input draft; retain the task and reference.

Draft saving alone does not invalidate directions or outputs. Applying changed formal inputs invalidates the current dependent direction approval and production outputs under the repository's revision rules; historical records remain available. A no-op apply does not increment the formal revision or invalidate anything. Changes to optional facts actually sent to generation, including restrictions and claim qualifications, count as meaningful changes.

Any unreviewed structured-input differences from the reviewed checkpoint must be applied or discarded before new downstream generation or approval. Source notes and unaccepted proposals are excluded. The checkpoint includes explicitly excluded draft claims, so retaining them does not leave the task permanently pending. The server enforces this gate; the client also flushes pending local saves before those actions. Editing while a job runs does not let its response overwrite the draft or become approved under incompatible inputs. Existing task/job stale-result protection must remain intact.

## 9. Essential states

| State | User sees | Available action |
|---|---|---|
| Empty | One opening question, blank summaries, optional notes entry, add-reference action | Enter known facts or start the reference |
| In progress | Current values, one useful question, missing items, saving state | Edit, accept/dismiss proposals, save, inspect reference |
| Saved draft | “Draft saved”; incomplete or unapplied label when relevant | Resume edits, review, discard changes |
| Review needed | Claims/values to confirm and excluded draft claims | Confirm/edit, then apply |
| Applied | “Inputs applied · revision N”; accurate readiness checklist | Continue when reference is also confirmed |
| Error | Specific local message plus retained text | Retry save/AI or continue manual editing |
| Changed after generation | Unapplied indicator or explicit stale-result label after apply | Apply/discard, regenerate and reapprove as needed |

## 10. Out of scope

Reusable brand library, copy-from-task, shared brand records, multi-user collaboration, cross-tab merge UI, multiple platforms/goals/references, mandatory proof documents, URL crawling, automated legal/factual certification, a full chat agent, unlimited adaptive interviews, complex conflict resolution, brand account settings, new M6 generation algorithms, storyboard images and redesign of all M3–M8 screens.

No fabricated quality score or conversion estimate. No claim that real API quality or all product modules are accepted merely because PR #3 exists.

## 11. Completion definition

The primary task can proceed end to end with manual input and deterministic test providers; incomplete inputs can be saved and resumed; assistance never silently supplies facts; formal input revisions and existing approval gates remain correct; Editorial Studio is recognizably implemented and usable at supported widths. Documents 03 and 04 specify contract changes and observable acceptance cases.
