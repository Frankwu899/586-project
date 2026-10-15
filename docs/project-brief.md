# Video Anatomy — Project Brief

**Confirmed product scope: 15 October 2026. The v0.3 skeleton uses labeled sample recognition and creative generation; real providers remain later work.** The implementation mission is `overnight-skeleton-spec.md`; actual checks and limitations belong in the latest handoff.

## Goal and value

Help a brand or agency combine observations from one reference video with its business objectives to choose a creative direction for a new product-focused marketing video. The outcome is a production decision: an approved creative direction, an editable production creative brief, and an editable text storyboard.

## Confirmed workflow

1. Create and save a task. Enter a versioned **brand/task brief**: brand/company, product, approved messages or selling points, audience, publishing platform, communication goal, and positive target duration. Available footage, presenters, locations, tone, production limits, and prohibited claims are optional.
2. Upload one local reference video, or load the separate, clearly fictional sample task. Validate media and record provenance. Source URLs may be stored, but platform downloading is deferred.
3. Review frame-timed visual/audio observations grouped into readable content sections such as Hook, demonstration, and CTA. Observations may overlap; primary sections do not. Coverage distinguishes missing extraction from checked absence. Source FPS and actual frame boundaries are read during intake; timecode and frame stepping support review across frame rates. Video and timing remain read-only.
4. Correct recognized text, visual descriptions, or section roles as needed. Preserve the original extraction and save corrections as a new revision. Use the separate **Use this reviewed analysis** action to confirm the current revision for creative use.
5. Compare two directions with a core message, Hook, narrative, CTA, production implications, evidence references, and rationale. Edit fields or apply free-text feedback to a particular draft. Sample refinement demonstrates a limited presenter-free instruction; arbitrary text is saved honestly as uninterpreted notes. Explicitly approve one exact direction revision.
6. Generate and edit the **production creative brief** and **text storyboard** from that approval. Storyboard suggestions keep general timing in seconds and have no FPS setting; cited evidence uses frames from the reference video. Save revisions and explicitly regenerate if wanted. Export readable Markdown and CSV.
7. Reopen saved progress after browser refresh or backend restart. Changed upstream content preserves earlier work, marks dependent work outdated, and requires approval again.

The brand/task brief is an input. The production creative brief is a generated and editable output. Neither confirmation nor approval certifies observation accuracy or creative effectiveness.

## Evidence and demonstration boundaries

The dedicated sample uses a reproducible illustrated LumaCup clip with text and tones, plus deterministic sample adapters. It establishes the workflow and data boundary, not recognition accuracy, unrestricted language understanding, real product behavior, or validated marketing results. An arbitrary upload never receives these prepared findings; real analysis returns an explicit unconfigured state until Andrea implements the provider.

Public views, likes, and comments are optional dated source context; unknown values remain unknown. They do not establish retention, click-through, conversion, or causal effectiveness. Recommendations cite the exact reviewed evidence revision and remain hypotheses where outcome evidence is missing. Team/TA feedback is preliminary usefulness feedback, not external market validation.

## Development and team workflow

The selected stack is React/Vite/TypeScript and FastAPI/Python, with server-side local persistent task storage and local media. See `docs/architecture.md`, `docs/interfaces.md`, and `README_SETUP.md` for boundaries and setup. The initial product is a single-user, team-run Web demonstration. Codex Cloud development does not deploy it publicly or install its dependencies on Frank's Mac or Andrea's computer.

Frank reviews the sample workflow and shared contract, integrates changes, and later refines UI/UX and real creative generation. Andrea implements real recognition behind the documented adapter, beginning with visual actions, on-screen text, and speech. Other team members record sources, dated public metrics, and human review findings using `docs/reference-review-guide.md` and the templates. The integrator reviews changes before merging.

## Scope and remaining decisions

The original 11 October target covered architecture and working guides. The 15 October mission extends that baseline to a runnable sample skeleton; it does not retroactively claim earlier implementation or acceptance. Consult `docs/handoff/overnight-skeleton-review.md` for the initial milestone and `docs/handoff/frame-timing-review.md` for the frame timing follow-up.

New variables and custom categories are deferred. Real provider/model choice and budget, real-input accuracy, broader tested media coverage, and final page design remain open. Midterm/final dates still need to be recorded. Multi-video comparison, draft-improvement workflows, custom model training, generated storyboard images, unrestricted prompt interpretation, platform downloads, and public hosting remain outside this skeleton.
