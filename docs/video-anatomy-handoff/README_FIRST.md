# Video Anatomy implementation handoff

Prepared for Frank and Andrea on 16 October 2026. Repository: Frankwu899/586-project.

## What to do

1. Extract the video-anatomy-handoff folder into your repository's docs/ folder. The expected path is docs/video-anatomy-handoff/.
2. Commit and push these documentation files to the branch that the Codex Cloud task will use. A file that exists only on your Mac is not automatically visible to a GitHub-backed cloud task. Alternatively attach the ZIP directly when the coding environment supports attachments.
3. Start the coding task from the intended branch and paste the contents of CODEX_PROMPT.md. Do not paste an API key.
4. Let Codex complete the code and offline tests. Configure an API secret and an explicit live-test budget in the execution environment when you are ready for paid tests.
5. Review its actual diff, verification results and limitations before integrating into main.

## Files

| File | Purpose |
| --- | --- |
| IMPLEMENTATION_SPEC.md | Confirmed scope, implementation defaults, modules, acceptance and delivery requirements. |
| DATA_CONTRACT.md | Complete current field catalog plus the proposed structured visual, correction and playback extensions. |
| CODEX_PROMPT.md | Full implementation prompt to paste into Codex. |
| docs/blueprint.html | Updated expandable team blueprint; historical integration information is marked as historical. |
| docs/Video_Anatomy_Data_Dictionary.html | Chinese explanations with English variable names; includes confirmed bilingual recognition and editable-label requirements. |
| reference/current-v0.3/ | Observed source model/interface/schema snapshots. Never overwrite live code with these. |
| schemas/proposed/visual-details.schema.json | Standalone proposed structure validator; semantic references still need application validation. |
| examples/ | A current synthetic contract fixture, a proposed visual extension and bilingual evaluation cases. No real recognition results or video media are included. |
| MANIFEST.json | Snapshot identities, file sizes and checksums for the delivered package. |

## Status and precedence

This package specifies work; it does not implement or deploy that work. The observed main was a456329e4fe8cab76669c8c8254cfed8ce11bbcb. Its real providers were unconfigured, sample recognition/creative templates existed, and media intake accepted H.264 MP4 with optional AAC audio.

Use current repository code to establish actual implementation state. Confirmed new requirements supersede historical feature limits in reference documents. Proposed names/defaults in the English specification are concrete starting points; they do not mean every earlier suggestion received individual user approval.

Confirmed now: H.265 reading; English/Chinese/mixed recognition and text handling; OpenAI first with replaceable providers; three structured visual groups; user correction of the new labels; preserved originals/revisions and downstream invalidation; Jev deferred. Existing review/approval workflow and source-frame timing remain.

Not an authorization to spend: the previously suggested US$20 test budget. Not a required promise: MOV support, a five-minute SLA, universal HDR/Log support, complete UI translation or a production-quality recognition-accuracy claim. Use the documented defaults and report real measurements.

The implementation and contract documents are English. Chinese strings in examples are intentional bilingual test data; the human-facing HTML data dictionary remains bilingual.
