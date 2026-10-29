# Generation skill publication — v0.7.6

- **Task:** Publish the confirmed generation skill and updated team documentation to GitHub.
- **Environment:** Cloud workspace; documentation-only changes.
- **Repository:** Frankwu899/586-project.
- **Branch:** `docs/project/generation-skill-v076`.
- **Fetched main baseline:** `1ec83af4f3958d0b0cec76c84cc6feef6ba6394f`.
- **Runtime source baseline:** `144aec5ef363a68416c7f0ba33c61da2e7913a2d` (v0.7.5).
- **Release meaning:** v0.7.6 is the skill/specification publication, not a new application build.

## Changes and reading order

1. [Team handoff](../generation/v0.7.6/TEAM_HANDOFF.md) or its
   [Word copy](../generation/v0.7.6/TEAM_HANDOFF.docx): updated version, owners and sequence.
2. [Skill entry](../../skills/video-anatomy-professional-generation/SKILL.md): common method and three module guides.
3. [Harness integration](../generation/v0.7.6/HARNESS_INTEGRATION.md): required backend/interface work.
4. [Decision register](../generation/v0.7.6/DECISIONS.md): all 32 confirmed choices.
5. [Version overview](../generation/v0.7.6/README.md) and validation report.

The standalone v0.1 draft is published as skill v0.7.6. The professional rules
are preserved; relative links and publication metadata are updated. README_SETUP
links the new entry points. Older application handoffs remain historical records.
No application source, schema, installed Mac package, credential or user library
is modified. This publication does not auto-load the skill into product requests.

## Checks and limitations

Documentation links, decision coverage, version consistency, Word readability at
the document-structure level, manifest hashes and Git diff scope are checked.
See [validation report](../generation/v0.7.6/VALIDATION_REPORT.md).

No application tests or paid model calls were needed or run for this text-only
publication. No model training, native Mac test, backend loading or deployment
is claimed. Earlier 730-test results apply to v0.7.5, not to the new rules' quality.

## Synchronization and next work

This branch was created from fetched main with a clean worktree. Publication
commit and remote SHA are recorded in Git and the associated PR. Historical
branches and v0.1 downloadable artifacts are retained; no force push or merge.

Frank owns integration; Natalie QA criteria; Andrea model/API comparison; Belinda
UI/UX design; Haoyang test video materials. Formal comparisons follow harness
merge into the agreed testing baseline and version freeze. Current code requires
exactly two Ideas and lacks the new safe discussion-draft flow, so prompt files
alone cannot implement all decisions. Read the integration brief before coding.
