# M2 UIUX Specification — Editorial Studio

Status: selected visual direction; concrete implementation specification. This is an input workspace, not the M7 production document editor.

## 1. Design intent

Use a calm editorial work surface: warm paper, dark brown text, serif headings, a restrained rust accent, readable summaries and ample space. Structure comes from alignment and typography. The interface should feel like developing a concise working brief with a helpful editor.

Retain the selected prototype's visual identity. Do not substitute a generic analytics dashboard, a chat column or an uninterrupted multi-field form. The existing style prototype illustrated the direction; its example data and simulated actions are not production contracts.

## 2. Workspace composition

At desktop widths, use a restrained header, a slim workflow rail, and a main workspace. The main area contains a heading and two complementary columns: a wider summary/editing area on the left and one current-question sheet on the right. A task-details strip and action area follow the content.

| Region | Contents | Behavior |
|---|---|---|
| Header | `video anatomy.` wordmark, task name, save status | Task-level controls only; no account/profile settings added. |
| Workflow rail | Inputs; Reference; Directions; Production | Inputs and Reference are accessible in either order. Other entries explain unmet prerequisites. These labels group existing modules, not renumber M1–M10. |
| Page heading | “Shape the work.” + one short instruction | Heading changes to “Review your inputs.” in the review state. |
| Brand & product | Brand, product, claim list, optional messages/restrictions | Readable summary first; explicit Edit actions reveal compact inline controls. |
| Current question | One question, up to three choices, custom answer, “Decide later” | Changes only when the answer is accepted or the user chooses another field. No continuous unsolicited text generation. |
| Reference summary | Filename/thumbnail when actually available, actual status, “Open reference” | Uses M3–M5 state. Never fabricate thumbnail, analysis, confirmation or progress. |
| This task | Audience, platform, goal, duration; optional production details | Compact summary with focused editing. Required omissions visible. |
| Action area | Readiness explanation and one primary action | Uses state-specific copy below; sticky only if it never obscures content or keyboard focus. |

The rail communicates progress; it must not enforce an inputs-before-video sequence. On a new task, both “Add what you know” and “Add reference video” remain available in one workspace.

## 3. Tokens

Light appearance is the release target. Dark tokens are supplied for compatibility with an existing system-dark setting; do not add a new theme-switcher feature. Validate contrast against actual backgrounds.

| Token | Light | Dark compatibility | Use |
|---|---|---|---|
| `--m2-paper` | `#F8F4ED` | `#211F1B` | Workspace background |
| `--m2-surface` | `#FFFCF7` | `#2B2823` | Controls and current-question sheet |
| `--m2-ink` | `#342E28` | `#F1E9DC` | Main text |
| `--m2-muted` | `#796D61` | `#BAAD9C` | Secondary text; never essential state alone |
| `--m2-line` | `#E3DACE` | `#4D443A` | Decorative rules and grouping |
| `--m2-control-border` | `#8B7B6D` | `#A49484` | Required control boundaries; distinct from decorative rules |
| `--m2-accent` | `#9D4D35` | `#E4A486` | Primary action, active rail, focus |
| `--m2-on-accent` | `#FFFAF4` | `#302016` | Text on primary action |
| `--m2-tint` | `#F4E7DA` | `#493326` | Selected option and subtle guidance |
| `--m2-error` | `#A8322B` | `#FFB4AB` | Error text/icons, always with explanation |

Headings: Georgia, Times New Roman, a suitable system serif fallback. Body and controls: system sans with PingFang SC / Microsoft YaHei / sans-serif fallbacks for Chinese. Do not require downloaded fonts. Main heading 36–40px/1.15 desktop, 28–32px on narrow screens; section headings 21–24px/1.25. Body and editable fields 16px/1.5; compact summary text may be 14px; supporting labels 12–13px. Never use tiny all-caps labels for important instructions.

Spacing scale: 4, 8, 12, 16, 24, 32, 48px. Desktop content padding 28–32px; mobile 16px. Rail about 150–170px. Main content maximum width about 1200px; summary/question columns approximately 1.1:1, with at least 24px gap. These are layout targets, not fixed widths that create overflow.

Buttons and choice rows: 3–6px radius, modest 1px borders, clear selected state with text/check mark. The current-question sheet has a 3px accent top rule. Use little or no shadow. No gradients, glass panels, animated backgrounds, decorative charts or nested card stacks.

## 4. Input components

### Summary and edit region

Each section shows meaningful values in short readable rows. Empty values use “Not provided” or “Not decided,” never fabricated sample values. “Edit” expands relevant controls in place and preserves keyboard focus. Optional details live in one disclosure titled “Production details and restrictions”; they do not dominate the first screen.

Avoid a single giant text field. The optional notes disclosure may use a medium textarea with an example placeholder. Beside it: “Extract details.” Editing fields remains possible without using this action.

### Current-question sheet

Example: “What should viewers take away?” Choices: “See the product's everyday value,” “Remember the brand,” “Take a next step.” Include “Write my own” and “Decide later.” Example choices are suggestions, not claims about the user's objective. A chosen suggestion updates the draft only after an explicit click; no default selected card.

Do not create an endless interview. The missing-required-field list determines what is asked next; a user can edit any field or inspect the reference at any time. If nothing required is missing, the sheet becomes a short review checklist with the review action.

### Proposal review

Show extracted candidates as labeled field rows, each with its source excerpt and selection/dismiss controls. For a populated field, show “Current” and “Proposed” values before selection. Row selections and edits remain local until the user clicks “Use selected details,” which adopts the selected batch in one draft update. A compact review region is sufficient; no full comparison dashboard. If the draft changed since extraction, reject the stale batch and offer to rerun it.

Fact-extraction label: “From your notes.” Task-inference label: “Suggested — confirm before use.” Claim label: “Needs your confirmation.” No AI confidence percentage. A stale response displays “Your inputs changed. Run extraction again.” Do not apply any stale proposal automatically.

### Selling points

Each row shows the exact claim, expandable “Support and conditions,” and “Confirmed for use.” Supporting notes and URL inputs are optional. A confirmation checklist in the final review can consolidate confirmations without concealing individual wording. Unconfirmed claims appear under “Saved for later — excluded from this brief.”

Keep prohibited claims visible in the review alongside the usable claims. If the user or extraction identifies conflicting text, display the alternatives and ask for an edit or explicit choice; do not automatically choose the stronger claim.

## 5. State and action copy

| State | Status copy | Primary action | Supporting behavior |
|---|---|---|---|
| Empty | “Start with what you know.” | “Add product details” | Secondary “Add reference video.” |
| Incomplete draft | “Draft saved · 3 items still needed” | “Complete next item” | Missing list names actual fields; no invented completion score. |
| Saving | “Saving draft…” | Relevant editing/review action | A save-dependent action waits for acknowledgment; avoid losing text. |
| Save failed | “Changes aren’t saved yet.” | “Retry save” | Retain input and explain the failure; warn before leaving with unsaved input. |
| AI working | “Extracting details from your notes…” | Disabled extraction action | Manual work remains available; a changed draft makes the old result stale. |
| AI unavailable | “Couldn’t extract details. You can continue editing.” | “Try again” | No sample data substituted for real failure. |
| Ready to review | “Required details are ready to review.” | “Review inputs” | Still not applied or approved. |
| Review | “Confirm what the next step may use.” | “Apply inputs” | Show included/excluded claims and downstream impact if changing a prior brief. |
| Applied, reference incomplete | “Inputs applied · revision N” | “Review reference” | Describe the actual remaining reference prerequisite. |
| Applied and reference confirmed | “Ready for creative directions” | “Generate 2 directions” | Route through the existing M6 server gate. |
| Unreviewed structured changes | “Draft saved · changes not applied” | “Review changes” | Compare with the reviewed checkpoint; exclude raw notes/unaccepted proposals. Secondary “Discard changes”; generation/approval explains this blocker. |
| Formal change after outputs | “Inputs changed. Directions and production need updating.” | “Generate updated directions” | Old outputs remain historical, visibly stale and ineligible as current exports. |

Changing the brief is not “approving a direction.” Preserve the existing explicit M6 approval control and use the word “Approve” there only.

## 6. Responsive behavior and accessibility

At 1024px and wider, use rail plus two-column workspace if it fits. Below roughly 900px, stack the question sheet after the summaries and replace the rail with a compact wrapping navigation row. At 390px and 320px, use one column; no page-level horizontal scrolling or overlapping action bar. Do not shrink type to preserve desktop geometry.

All controls must be semantic, labeled and keyboard usable. Show a visible focus ring. Controls must provide clear non-color state cues; primary/coarse-pointer targets are at least 44×44px. Provide a predictable focus move to the review heading or first invalid input after an explicit action, not on background autosave. Associate errors with fields; announce actionable errors and save status without announcing every keystroke.

Use 120–180ms transitions for disclosure, selected state and saving feedback. Respect reduced motion. Avoid decorative entrance sequences or animated text. Motion communicates state change only.

Contrast targets: 4.5:1 for normal text, 3:1 for large text and meaningful control boundaries/focus indicators. The decorative line token is not sufficient as the sole boundary for a text field. Check light and any active dark appearance during implementation.

## 7. Integration and reference use

Apply shared typography, color and action tokens to M2 and its immediate workspace shell. Denser reference or storyboard screens may reuse those tokens without copying the M2 two-column layout. Do not redesign unrelated pages in this task.

Design references consulted: [UI UX Pro Max](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill), [Impeccable](https://github.com/pbakaus/impeccable), [React Bits](https://github.com/DavidHDev/react-bits), and [Karpathy Skills](https://github.com/multica-ai/andrej-karpathy-skills). Their applicable principles are intentional hierarchy, accessible controls, progressive disclosure, restrained useful motion, minimal scope and verifiable changes. These repositories were read as references; they were not installed or executed. Do not add their dependencies merely to imitate the style.

## 8. Required visual evidence

During implementation capture the actual empty, partial, proposal-review, applied and error states. Include desktop and narrow-screen evidence, keyboard behavior and reduced-motion checks. A design prototype is not evidence that the real application passed browser acceptance. No new production screenshot or application browser verification is claimed by this handoff.
