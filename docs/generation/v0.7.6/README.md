# Video Anatomy — Professional Generation Skill v0.7.6

Status: owner-confirmed behavioral specification; **not installed or deployed**.
Prepared for the intermediate release following app v0.7.5. Documentation only.

## Read in this order

1. [Team handoff](TEAM_HANDOFF.md): ownership, sequence, acceptance and scope.
2. [Skill entry](../../../skills/video-anatomy-professional-generation/SKILL.md): runtime instructions and module routing.
3. [Shared professional method](../../../skills/video-anatomy-professional-generation/references/PROFESSIONAL_METHOD.md).
4. The relevant [Structure](../../../skills/video-anatomy-professional-generation/references/STRUCTURE.md),
   [Ideas](../../../skills/video-anatomy-professional-generation/references/IDEAS.md), or [Storyboard](../../../skills/video-anatomy-professional-generation/references/STORYBOARD.md) instructions.
5. [Quality rubric](../../../skills/video-anatomy-professional-generation/references/QUALITY.md) and [illustrative examples](../../../skills/video-anatomy-professional-generation/references/EXAMPLES.md).
6. [Harness integration](HARNESS_INTEGRATION.md) and [decision register](DECISIONS.md).

The skill is an English, portable instruction package. Generated language follows
application settings; English documentation does not force English creative output.
It describes expert methods explicitly, not a fine-tuned or distilled model.

## How to use this draft

For a manual prompt evaluation, read SKILL.md, PROFESSIONAL_METHOD.md, the selected
module, and QUALITY.md together. Supply the real task, permitted evidence and an
explicit output contract. Examples are optional calibration material, not facts.
For backend integration, Frank must implement explicit loading, versioning,
context assembly, schema mapping, validation and bounded revision. A Markdown
file alone does not alter the app. Do not paste all three module instructions
into every request or silently add fields rejected by the current schema.

Owner-confirmed behavior is recorded by decision IDs. Detailed field names,
score scales, call scheduling and evaluation sizes are **implementation proposals**
where explicitly labeled. No additional decisions or measured improvements are implied.

## v0.7.6 release scope and baseline

**v0.7.6 publishes the generation skill and team specifications. It is not an
application-runtime upgrade.** The runnable app remains the v0.7.5 baseline;
no provider currently loads these new instructions automatically. Installing a
coding-assistant skill is not the same as integrating the backend harness.

The previous standalone draft was skill v0.1. This publication aligns its package
version to v0.7.6 without changing any confirmed interview choice.

Application source: `144aec5ef363a68416c7f0ba33c61da2e7913a2d`.
Verified fetched main baseline: `1ec83af4f3958d0b0cec76c84cc6feef6ba6394f`.
Publication branch: `docs/project/generation-skill-v076`.

Canonical skill: `skills/video-anatomy-professional-generation/`.
Versioned documents: `docs/generation/v0.7.6/`.
[Publication handoff](../../handoff/generation-skill-v076.md) records checks and limits.
[Team handoff — Word](TEAM_HANDOFF.docx) is the shareable copy of the Markdown document.

This change contains no application code, schema migration, runtime version bump,
API credential, video, paid test or deployment. The former local-only delivery
has been prepared for GitHub publication; historical v0.1 artifacts stay unchanged.
