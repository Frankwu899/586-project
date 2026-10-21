# Timestamped speech restored — v0.7.4

- **Task:** Restore dedicated speech transcription under the owner-approved exception.
- **Author/date:** Codex, 19 October 2026.
- **Environment:** Managed Linux Cloud; no configured OpenAI secret or permitted OpenAI endpoint.
- **Repository/branch:** `Frankwu899/586-project`, `feat/workspace/structure-agent-redesign`.
- **Starting commit:** `a87f024175993a2a02882deb4c417bc2d8971862`, clean working tree.
- **Review:** Draft PR #8, stacked on PR #7. No merge or deployment.

## Changes

The owner approved a usable dedicated speech model while keeping all other
inference on GPT-6. Defaults now use `whisper-1` for segment-timestamped
transcription. The local launcher restores this setting even when an old
environment carries the v0.7.3 `disabled` value. Vision, Structure synthesis,
Ideas, Production and context assistance continue using GPT-6.1 Sol; bounded
background retrieval continues using GPT-6 Luna.

The Speech lane describes missing historical transcription without falsely
claiming that transcription is currently disabled. Those analyses expose the
existing missing-analysis retry action. Valid speech caches remain reusable;
an empty result saved while speech was disabled cannot suppress new transcription.
Source words and timing remain unchanged, and no model call runs on startup.

Changed files: provider configuration, local launcher, example environment, Mac
version metadata, analysis coverage UI/translations, English setup docs and
targeted regression tests. No shared schema or library migration is required.
The existing USD 3 budget ledger is preserved and applies to speech as well.

## Verification

- Targeted backend regression: **147 passed** across launcher/configuration,
  GPT-6 budget, recognition/cache recovery, providers, credential replacement,
  Mac launcher and budget guard tests.
- Research browser suite: **3 passed**, including recovery from an old
  untranscribed analysis, partial-channel recovery and five viewport sizes.
- TypeScript/production build, ESLint, scoped Ruff and diff checks passed.
- Extracted v0.7.4 archive: source hashes, plist/version, executable mode, shell
  syntax, real localhost startup, empty library, language preferences, zero-call
  budget, Trash/Restore, served built UI and authenticated shutdown passed.

All provider tests used synthetic/mocked inputs. Real paid API calls, speech
accuracy, account permissions, native Finder/Keychain/Gatekeeper and a full
historical suite rerun were **not run** for this narrow update. The previous
v0.7.3 full regression remains recorded separately; counts are not cumulative.

## Delivery and next step

Use `video-anatomy-v0.7.4-macos-app.zip`. The package contains no owner video,
credential, task database or ledger. It uses the existing local library and
Keychain credential. Reopen a project and choose **Retry missing analysis** or
**Analyze again** to create a new result with speech. The key requires Audio
Transcriptions access. Paid work starts only on explicit analysis/generation.
There is no remaining speech-policy approval question.
