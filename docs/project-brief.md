# Video Anatomy — Project Brief

**Proposed baseline v0.1, 8 October 2026. English edition and development-workflow update: 14 October 2026. Product decisions below reflect the confirmed discussion; implementation choices remain proposals.**

## Goal and value

Help a brand or agency combine evidence from a reference video with its own business objectives to choose a creative direction for a new product-benefit short video. Explaining the reference video alone is insufficient: the output and interface must help the team make a concrete creative decision or improve its production strategy.

## Midterm workflow

One brand brief and one reference video lead to segment-level analysis, user review and correction, creative-direction development, explicit human approval, and a Creative brief plus text storyboard.

- **Brand input:** brand/product, selling points, target audience, publishing platform, and communication goal.
- **Video input:** file upload is the baseline. Validate YouTube/TikTok link ingestion in a small technical spike before deciding support. Publish format, codec, size, and duration limits only after testing.
- **Reference type:** product-benefit short videos demonstrating a feature, effect, or use case. The specific product category and sample set remain to be selected.
- **Analysis granularity:** timed content segments such as Hook, product demonstration, proof, and CTA. Categories can be absent or repeated, and one segment can serve multiple roles. Shot-level segmentation is not a midterm requirement.
- **User corrections:** segment roles, recognized speech/on-screen text, and visual descriptions. Record timestamp errors in the human review table; editing timestamps is not a required midterm UI capability.
- **Creative choice:** the user must choose or revise a direction and explicitly approve it before storyboard generation. A prototype will compare choosing reference techniques first with reviewing suggested directions first; this interaction detail is not yet settled.
- **Creative brief output:** core message, Hook, narrative direction, and CTA, informed by the brand brief and reviewed reference evidence.
- **Text storyboard output:** time, visual description, dialogue/on-screen text, sound, and CTA. Generating storyboard images is not required.
- **Available performance data:** public views, likes, and comments, with a source and observation time. Retention, CTR, and conversion data are not currently available; do not invent them.
- **Evidence for advice:** reference segment IDs and time ranges, plus a reason tied to the user's brief. Performance judgments remain hypotheses with a practical test. Public engagement does not prove that a creative choice caused performance.

## Development, demonstration, and team workflow

Existing model APIs are allowed; custom model training is not required. Start with a team-operated demo running on a team computer and preserve sensible configuration, API, and storage boundaries for possible future deployment. There is currently no requirement for outside users to operate the product independently.

As of 14 October 2026, the owner prefers Codex Cloud for ongoing and unattended coding tasks, with the Mac used for local checks, review, and demonstrations. GitHub carries committed code and documentation between environments. This development preference does not change the planned local demonstration or imply that the application is publicly hosted.

The project owner builds and integrates first; 2–3 members progressively take coding tasks. Other members collect reference videos, source/brand context and public metrics, and manually review segment labels, content, and errors. Prompts drive agent development and Git operations. The project integrator reviews and merges changes.

Team and TA feedback will provide preliminary evidence of creative usefulness. It is not external market validation.

## Milestones and open decisions

The original Sunday target, 11 October 2026, covered architecture direction, interfaces, and collaboration instructions. The runnable skeleton was a later deliverable. This package records that historical target; it does not claim the application was completed or the target was formally accepted.

Midterm/final dates and the API budget still need to be recorded. The stack, model/provider, link-ingestion path, operational limits, and specific sample product category require investigation or testing.

Multi-video comparison, custom model training, generated storyboard images, and public hosting are outside the midterm must-have scope. Revisit them only through an explicit scope decision.
