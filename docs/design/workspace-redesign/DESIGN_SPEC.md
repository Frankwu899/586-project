# Video Anatomy: a workspace organized around user intent

**Status: proposed design, pending product review.** This document separates
explicit owner requirements from recommendations and existing behavior. It does
not supersede every previously confirmed decision or claim new implementation.

## 1. What the product should help someone accomplish

A creator or brand planner may arrive with a video worth understanding, a product
that needs an idea, or an existing idea that needs a shootable plan. Those are
different starting points with connected materials, not stages every person must
complete in one order.

The current application overexposes its internal dependencies: numbered stages,
large explanatory headings, multiple save/apply/confirm concepts and global
blocking state. The user experiences a workflow obligation before receiving value.
Removing the numbers or adding translucent cards alone would preserve that problem.

The proposed product is a project workspace for **research, ideas and production**.
Each area has its own useful outcome. Project context, media and chosen evidence
connect them when the user chooses to make that connection.

### Requirements received in this review

| Owner request | Proposed response | Status |
| --- | --- | --- |
| Revisit actual needs and use scenarios before implementation | Three intent-based entry paths; walkthrough before application changes | Confirmed process |
| Remove the forced 1–2–3–4 experience and disconnected modules | Shared project context, independently useful workspaces, action-specific prerequisites | Confirmed direction; exact gates need review |
| Prevent phone/platform UI from polluting reference analysis | Content-area tool, reversible masks, classification and separate duplicate grouping | Required outcome; implementation approach proposed |
| Visible processing and errors where users act | Local button/panel feedback plus persistent activity center | Required |
| Premiere-like reference analysis | Video stage, inspector and synchronized multitrack timeline | Required direction; precision/data scope distinguished below |
| Desktop window rather than an endless document | Viewport shell, resizable internal panes, stable tools and navigation | Required |
| Explore a Mac-installable DMG | Self-contained .app, stable user-data store and tested macOS packaging | Feasible; packaging implementation is a later milestone |
| Use the specified new skill and prefer Glassmorphism | Verified active Glassmorphism; restrained glass shell with readable content | Skill installed; treatment proposed |
| Reduce explanatory clutter | Short action labels, contextual help, details on demand | Required |
| Explain local file mapping and missing-file recovery | Audit existing copied media; propose visible storage settings and repair flow | Audit complete; management UI proposed |
| Deliver installers, launchers and package documentation in English | English release UI/instructions and delivery checklist | Confirmed for future delivery |

## 2. Entry paths and user touch flow

Entrypoints express intent; they do not lock the project into a mode. A project
retains notes, media, ideas and plans and reopens where the user left it.

### A. “Help me understand this video”

1. Drop a video on the project surface or choose **Import video**. Create/reuse a
   project with a sensible editable name; do not demand a brand form.
2. Show immediate playback. If a screen recording is suspected, suggest a content
   area directly on the preview. The user can adjust it, accept it, or keep the
   full frame; the tool is available later too.
3. **Analyze** starts an explicit task. State appears beside the control and in
   the activity center. The rest of the project stays usable.
4. Review evidence against the video in the timeline and inspector. Correct text,
   make notes, exclude capture UI, and review source limitations in context.
5. The user can finish with research notes, or choose **Use in an idea** for
   selected evidence. No brand brief is required to get value from research.

Analysis export and manual annotation are useful proposed research outcomes,
not features established by the existing application. Their initial format and
editing scope should be chosen in the next implementation brief.

### B. “Help me make something for my product”

1. Start an idea. Ask for the purpose/product only when it improves that action;
   allow a rough, manually written concept immediately.
2. Bring brand facts, constraints and optional references into a context drawer.
   Retain one authoritative project-context editor, rather than another unrelated
   form in every workspace. Previously entered facts are reused.
3. Ask only for missing information needed by the requested output. A rough
   brainstorm can clearly expose assumptions; usable product claims still require
   explicit permission. Missing facts must not become invented benefits.
4. Generate/compare/edit ideas. Selecting a reference is optional in this proposed
   path. Evidence-based claims cite selected reviewed material; an idea without
   reference material contains no fabricated citations.
5. **Approve for production** selects and approves the exact saved idea in one
   user action. Approval remains deliberate; autosave never approves work.

When no reference is selected, the current A-follows-reference/B-reorganizes-
reference rule cannot literally apply. Two alternatives would instead explore
different hooks/narratives for the task. That is a product change requiring review.

### C. “I already have an idea; help me prepare the shoot”

1. Open an existing idea or enter the user's own idea in Ideas.
2. Explicitly approve the intended text for production. Add missing constraints
   only when required to produce a useful plan.
3. Generate/edit the production brief and storyboard, then export saved content.
4. Return to ideas or evidence without losing drafts or the current plan.

This proposed path keeps approval before AI production while eliminating the
requirement to first conduct reference research. It is not permission to silently
bypass the current service's evidence/revision rules.

### Actions, not whole workspaces, have prerequisites

| User action | Needed now | Should remain possible if something is missing |
| --- | --- | --- |
| Play/import/reference notes | A readable local asset for playback; notes may exist independently | Edit project context, open ideas and existing plans |
| Analyze a reference | Available media, valid content area, configured provider | Playback, manual review, other tasks and workspaces |
| Draft a rough idea manually | No reference requirement | Save, reopen, revise and add context later |
| AI brainstorm without reference | A useful task prompt and permitted facts; mark assumptions | Add context or write manually; keep prior candidates |
| Generate with selected reference evidence | Valid selected evidence and explicit source review | Generate without that source only by user choice; retain source warning |
| Generate production | Explicitly approved saved idea plus necessary task/production inputs | Inspect/edit/export existing work; prepare inputs |
| Export existing output | A coherent saved version | If dirty, save successfully or cancel; never silently export old text |

If reference analysis is partial, successful material should remain inspectable.
Using a selected successful subset downstream is a proposal, not an automatic
relaxation of the current all-success rule. The same applies to pending edits:
new drafts should not freeze unrelated actions; a running operation can use an
explicit input snapshot, and the user decides whether to adopt changed inputs.
The old snapshot and result remain labeled and available. These changes require
service/contract work, not just enabling buttons in the browser.

## 3. One desktop workspace

Use a bounded app shell, initially designed around 1440×900 and 1280×800 desktop
windows, with graceful smaller-window behavior. Keep system zoom and accessibility
available; adapt/collapse inspectors instead of clipping controls or banning zoom.

- **Top bar:** project switcher/name, saved state, activity and contextual actions.
- **Left rail:** Research, Ideas, Production. Project media and context stay
  available without becoming another mandatory stage.
- **Main canvas:** the currently useful work, with the same visual hierarchy and
  source/context controls in all areas.
- **Right inspector:** details for the selected event, idea or shot.
- **Bottom timeline in Research:** persistent time context and controls.
- **Activity center:** pending/running/failed jobs with a link back to their action.

Do not stack enormous headings, banners, all event forms, raw JSON and process
explanations above one another. Panels may scroll internally. Timeline navigation
may scroll horizontally. The goal is stable spatial context, not a literal ban on
all scrolling. At small sizes collapse the inspector into a focusable panel and
provide list/transcript alternatives for keyboard and assistive technology.

### Research interactions

| Surface | Interaction |
| --- | --- |
| Video stage | Play/pause, seek, frame step, fit/zoom, content-area tool |
| Timeline | Click/time input sets playhead; selecting an item selects the corresponding inspector; zoom/fit changes scale |
| Inspector | Show/edit the selected observation or interpretation, time/source and review state; jump to evidence |
| Tracks | Visual observations, on-screen text, speech and narrative interpretation; labels and shapes distinguish types, not color alone |
| Source/context drawer | Capture metadata and sourced background are distinct from in-video speech/text |
| Evidence-to-idea | Explicitly add selected observations to the creative context without copying every detected element into the idea |

Support Space for playback when focus is not inside an editor, keyboard event
navigation, visible focus and button alternatives for drag-only gestures.
Resizing panels should preserve usable minimum sizes and be reversible.

### What the reference screenshot requires

The supplied concept is the target spatial arrangement: player above a timeline,
right-hand selected-annotation inspector, source-aligned playhead and readable
tracks. The image's price bounding box and exact text duration imply capabilities
the current model does not supply.

| Capability | Current implementation | Honest first redesign / later extension |
| --- | --- | --- |
| Visual/OCR timing | Sparse sampled frames; current events span one frame | Show samples as points or explicitly sampled observations, not exact continuous scenes |
| Speech timing | Model segment estimates normalized to measured frames | Display speech intervals with their timing caveat |
| Scene boundaries | No exhaustive shot segmentation | Add shot detection and manual boundary review before presenting exact scene bars |
| Repeated visible text | Separate OCR event per sampled frame | Group repeats while preserving observed appearances/gaps; do not infer continuous visibility |
| Object/price highlight | No spatial boxes in current contract | Add localization and source/derived-frame coordinate mapping before accurate overlays |
| Audio waveform | No persisted peaks for the UI | Compute peaks locally from audio, without paying a model |
| Narrative roles | Interpretations linked to observations | Separate interpretation track with editable reasoning |

A first timeline is useful before continuous vision tracking exists. It must not
visually claim stronger evidence coverage than the underlying data supports.

## 4. Screen recordings: content-area preparation

The current prompt asks for all readable text and receives the entire recorded
frame. Every sample's OCR becomes separate evidence. It has no distinction between
the film being studied and the phone/player interface that contains it.

Add a **Content area** tool to the media preview and research toolbar. It is a
reference preparation capability, not a new global stage everyone must finish.

1. Suggest the film rectangle using framing, recurring UI placement and interface
   cues. Show a non-destructive preview; uncertainty remains visible.
2. Let the user adjust the rectangle, keep the whole frame, and add exclusion
   masks for controls floating inside the content rectangle. Check beginning,
   middle and end; later support time-varying masks where needed.
3. Preserve the original. Analyze a derived view, recording spatial transforms,
   region/mask version and how that affects cached recognition results.
4. Separate **exclude platform UI** from **group repeated content**. The former
   must not become creative evidence; the latter preserves actual occurrence
   records and keeps real persistent price/logo/CTA content.
5. Make excluded items inspectable/reversible. Publisher/account metadata may be
   useful capture context, but is not spoken or on-screen content of the film.

**Stationary is not equivalent to irrelevant.** A logo, price card, native video
subtitle, or deliberate product interface demonstration may remain fixed. A
screen recording can also contain an intentionally filmed phone interface.

Do not begin by training a model. First evaluate automatic suggestions plus manual
region/mask confirmation on permitted recordings. Collect failure cases and
labels, then compare heuristics, an existing detector and a trained model if the
measured error warrants it. One supplied clip is not a training/evaluation corpus.

Acceptance should measure both capture-UI leakage and legitimate-content removal.
Use clean-source/recording pairs, static product logos/prices, transient controls,
moving comments and interface-within-film cases. Verify unchanged original hashes,
correct coordinate/time mapping and cache invalidation after region changes.

## 5. Feedback that travels with the action

**Analyze** should immediately become **Analyzing…** with a local busy indicator,
followed by real stage text such as **Preparing frames**, **Transcribing audio**,
**Analyzing visuals**, **Saving results** when the backend exposes those stages.
Unknown completion time uses elapsed time/indeterminate feedback, never a fake
percentage or fabricated stage progress.

The action panel retains its space through pending, running, success and error.
Errors appear there with a direct recovery action. The activity center remains
visible after workspace/task navigation and can return to that result. Do not
steal focus on completion. Announce meaningful status changes accessibly once.

Disable duplicate submission for the affected action, not the entire project.
Keep previous results visible during retry. A failure in transcription must not
erase successful visual observations or block unrelated manual work. Autosave,
generation and media processing use distinct labels. Technical error codes and
revision IDs live in expandable details/copy-diagnostics, not normal product copy.

Cancel/stop is only shown with truthful semantics. Once an external request is
sent, cancellation may not cancel its charge. The implementation needs persistent
background jobs and input snapshots before promising navigation, restart recovery
or stage progress. Current synchronous requests plus global `busy` cannot provide
those guarantees through CSS alone.

## 6. Visual direction and writing

Use the owner's selected **Glassmorphism** from the verified active skill catalog.
Apply subtle frost to the window shell, sidebars, toolbars and overlays. Keep
video, time tracks, text and editing surfaces sufficiently opaque and stable.
Avoid stacking translucent panels over moving footage or using glow as hierarchy.

- Neutral slate surfaces, restrained teal/blue action accents and distinct track
  colors with text/shape labels. No oversized marketing headline or hero section.
- System UI typography with Chinese fallbacks; tabular time values; compact but
  readable labels and clear focus states. No remote font required to use the app.
- Short motion that explains changes; respect reduced motion and an opaque-surface
  preference/fallback. Measure contrast against the composed background.
- Normal text contrast target 4.5:1; meaningful controls/graphics 3:1. These are
  acceptance targets, not claims about an untested theme.
- Replace “Find the story worth making” with the actual workspace name/action.
  Replace global “Saving or processing” with the specific active operation.
- Keep explanatory prose in contextual help, tooltips or details. Never hide a
  prerequisite, error recovery instruction or uncertainty essential to a decision.

The skill's automatic design-system generator suggested Hero-centric marketing
patterns even after one narrower retry. Those portions were rejected. Explicit
style/UX/product searches support a timeline workspace and local action feedback;
the owner's workflow requirements take priority over generic database defaults.

## 7. Current files and the proposed managed library

### What happens today

The upload sends file bytes to the local backend. The backend copies them to a
random storage filename and records an asset ID, original filename and content
hash. Playback uses a task/media URL, and the backend resolves the stored ID. It
does not repeatedly reopen the original file from Downloads or Photos.

For the owner's current Desktop bundle, the default paths are:

```text
/Users/yuqingwu/Desktop/video-anatomy-local/.local-data/live/
  tasks.sqlite3
  media/<storage-id>.mp4
  provider-cache/<request-hash>.json
  provider-cache/runs.jsonl
```

An H.264 source can play directly; supported HEVC inputs get an H.264 playback
derivative. Prepared frame JPEGs/audio chunks use temporary directories and are
cleaned after analysis. Browser storage mainly remembers interface/draft-recovery
state; it is not the primary video store.

| Change outside the app | Current consequence |
| --- | --- |
| Move/delete the originally uploaded MP4 after successful import | Managed copy remains usable |
| Extract a new application folder and start it | It gets a different default data directory; old tasks remain in the old folder |
| Move the whole bundle including hidden data | Relative data relationships remain, but the moved Python environment still needs verification |
| Delete/move managed media itself | Missing-media error; no current relink/repair workflow |
| Clear browser cache | Saved backend tasks/media remain; unsynced browser-only recovery state can be lost |

### Recommended desktop storage

```text
~/Library/Application Support/Video Anatomy/
  projects/             persistent project records and histories
  media/originals/      managed original assets
  sources/              retained source/background research records

~/Library/Caches/Video Anatomy/
  thumbnails/           regenerable previews
  waveforms/            regenerable audio peaks
  proxies/              regenerable playback/analysis derivatives
```

The exact subdirectory/database arrangement is an implementation decision. The
important product rule is that installation and user data are separate, and
**original media, reviewed evidence, paid results and drafts are not disposable
cache**. Only derived data that can be rebuilt without losing work belongs behind
Clear cache. Paid result reuse needs explicit retention semantics, not blanket
cache deletion.

Default to managed import. Settings should show storage location, size, **Open
folder**, **Move library**, **Clear derived cache**, and backup/export options.
Move library copies and verifies data before switching the active root. Missing
media offers **Locate file**, **Restore copy**, or **Remove reference**; only an
identical hash restores the original evidence relationship. Different bytes create
a replacement rather than silently reusing prior analysis. Missing proxies can
be rebuilt from the retained original. Keep multiple assets/user-selected library
extension possible without expanding this release into full library search.

This behavior is independent of HTML versus native rendering. The browser plus
local backend can already manage files. A native shell improves system integration
but does not automatically repair workflow, storage or missing-file behavior.

## 8. Mac installation and delivery

A real `.app` inside a `.dmg` is feasible. The intended experience is drag to
Applications, launch a single window, configure the key in Settings, and keep
projects through upgrades. Users should not install Homebrew or run a terminal
for normal operation of that release.

Evaluate Electron with the existing React app and bundled Python/FFmpeg as the
shortest reuse path; compare Tauri if package size is a stronger constraint.
Electron offers familiar Chromium behavior; Tauri uses system WebView and adds
separate media/print/bridge validation. The outer shell is an engineering choice
after agreement on the interaction, not the product's organizing principle.

The build must bundle runtime dependencies per supported architecture, manage
backend lifecycle and local authenticated communication, store keys in macOS
Keychain, migrate the current hidden data directory safely, and separate upgrades
from user assets. Packaging FFmpeg also requires checking the shipped build's
license/notices. No binary distribution is claimed by this design document.

The current executor is Linux and has no macOS build/signing tools. A tested DMG
requires a macOS machine/runner, architecture-specific build and fresh-install/
upgrade tests. Smooth distribution also needs Developer ID signing and Apple
notarization with the owner's credentials. A local unsigned development build is
a separate limited milestone; renaming a ZIP is not a DMG delivery.

All future launcher text, installer prompts, package READMEs, handoffs and release
instructions are English. Source-language evidence and chosen output language
remain independent of that delivery requirement.

## 9. Preserve, reconsider and decide

Preserve task/draft recovery, original evidence/history, meaningful source
uncertainty, exact citations, explicit approval before production, and saved-version
exports. The redesign must reduce user effort while retaining these protections.

Reconsider the consequences of the prior four-area workflow decision (Q22), the
blanket pending-correction gate (Q5), and always requiring reference-backed A/B
directions. These are reopened by this feedback; they are not silently revoked.
Do not re-ask already confirmed Q1–Q3.

The owner previously added a desire for cultural/product background research.
Keep it visible as a related requirement: **Research context** with explicit
sources, dates and uncertainty, attached to an asset/idea. User notes, retrieved
sources, in-video observations and marketing hypotheses remain distinct. Active
external search is not implemented by this UI prototype. Its trigger, source
quality, cost and acceptance should be discussed separately after the core flow.

Two current questions were presented to the owner:

1. Prioritize reference-first study, brand-first creation, or both equally?
2. Allow starting creative ideas before reference analysis is complete/without
   a reference, with clear origin labels?

Recommended working assumption for this proposal: reference-first initial surface,
with an equally reachable independent idea path. A recommendation is not an
accepted scope decision. Another follow-up is whether entering an existing idea
and approving it is sufficient to start production without reference research.

## 10. Delivery sequence and acceptance

This is a development sequence, not a user-facing mandatory workflow.

1. **Review the concept:** walk the three scenarios in the separate clickable
   prototype. Confirm entry priorities and dependency changes; revise wording and
   panel behavior before wiring the backend.
2. **Build the interaction foundation:** desktop shell, selected-item inspector,
   truthful initial timeline, local action state and independent background jobs.
   Keep old saved projects/drafts intact; migrate only with versioned contracts.
3. **Improve capture preparation:** content-area confirmation, reversible masks,
   duplicate grouping and evaluated capture-UI suppression. Add localization/scene
   tracking only when the corresponding accuracy can be demonstrated.
4. **Decouple creative dependencies:** optional selected references, minimal
   action-specific context, manual ideas and explicit production approval, subject
   to the decisions above. Preserve trustworthy provenance without fake IDs.
5. **Deliver the desktop app:** stable data root, import/repair/migration settings,
   Keychain, bundled runtimes and macOS packaging validation. Maintain a browser
   development path without shipping its operational burden to the user.

Acceptance walkthroughs:

- Understand the supplied Guandan recording without completing any brand fields.
- Start an idea while analysis runs; navigation remains usable and the correct
  project's activity/result remains discoverable after switching.
- Hit an API error at the action and recover without scrolling to the page top,
  losing drafts or overwriting the previous successful result.
- Create a brand concept without video under the proposed independent path; it
  does not invent reference citations or product facts.
- Bring an existing idea through explicit approval into a production plan.
- Move the original imported file and still play the managed copy; upgrade the
  app without losing tasks; repair a missing asset with honest identity checks.
- Use the timeline by keyboard; inspect source uncertainty; recover a mistakenly
  excluded fixed product logo/price; clear only regenerable cache.

No application code, paid API calls, public deployment or DMG build are part of
this review round. The clickable concept uses illustrative data and simulated
activity; it is evidence of an interaction proposal, not product implementation.
