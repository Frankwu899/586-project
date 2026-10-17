# Codex execution prompt

Implement the first real OpenAI-backed Video Anatomy workflow in Frankwu899/586-project using the attached handoff package. This is an implementation task: finish the authorized code, documentation and verification work; do not return only a plan.

## Read first

Locate README_FIRST.md, IMPLEMENTATION_SPEC.md and DATA_CONTRACT.md in docs/video-anatomy-handoff/, video-anatomy-handoff/, or the attached package. Read them completely. If the package is attached as a ZIP, inspect and extract it safely into a documentation directory. Reference snapshots under reference/ are historical documentation, not files to copy into backend/app.

Read applicable AGENTS.md instructions, current README_SETUP.md, docs/interfaces.md, backend/app/models.py, adapters.py, media.py, timing.py, service/persistence code, generated frontend types, relevant migrations and the existing verification script. Inspect the actual Git state and current main before editing. The handoff observed main a456329e4fe8cab76669c8c8254cfed8ce11bbcb with v0.3 contracts; it is a snapshot, not a command to reset to that commit.

Precedence: explicit user instructions and confirmed requirements in the handoff; live code for current implementation facts; the handoff's clearly labeled implementation defaults for undecided routine details. Do not apply the old skeleton-integration prompt embedded in historical documents. Do not ask product questions already answered. Resolve reversible implementation choices, record them, and proceed. Ask only if a genuinely contradictory requirement or inaccessible essential input prevents safe progress; finish all independent work first.

## Required implementation

1. Extend the existing app instead of rebuilding it. Create or safely resume a focused task branch such as feat/video-analysis/bilingual-provider-contracts. Preserve unrelated changes; use an isolated worktree when needed. Never discard, reset or force-push existing work.

2. Update M10 through a versioned contract change. Add visual_details with subjects, actions and product_presentations, explicit group coverage/error states, local subject references, nullable unknown categories and semantic validation. Use DATA_CONTRACT.md for exact definitions. Propose v0.4.0 only if the current repo is still v0.3.0. Add backward migration and regenerate schemas/types using existing tooling. Retain historical schemas, original analyses and exact versioned citations.

3. Add H.265/HEVC MP4 reading alongside H.264. Preserve original bytes/hash/codec and actual source frame timestamps. Produce a validated H.264 playback derivative where needed and keep its playback clock separate. Preserve one-to-one frame correspondence or fail explicitly; do not overwrite the source clock with transcode timing. MOV, HDR/Log fidelity and unrestricted profiles are not silently promised.

4. Implement OpenAI adapters for real visual/OCR extraction, timestamped speech transcription and the existing creative-generation methods. Keep vision, transcription and creative provider/model settings independently configurable. Check current official provider documentation and supported modalities when selecting models. Isolate SDK shapes behind adapters; return the stable M10 domain types. Demonstrate replacement with a fake alternate provider without claiming a second real service was integrated. Defer TypeSafe Jev and all training/fine-tuning.

5. Make English, Chinese and mixed-language content required. Keep OCR and speech as distinct events, retain original-language text, normalize time ranges using the shared timing helpers, and support Unicode throughout brief input, user prompts, corrections, persistence and exports. Narrative output-language configuration is separate from original evidence. Never claim frame-accurate semantic recognition solely because the contract stores frame indices.

6. Add user correction of subject kind/roles, action type and product-presentation type, plus explanatory labels/descriptions, to the existing review flow. Preserve original extraction, use server-validated allowlisted changes, append replayable revisions, reject stale writes, clear review and invalidate affected downstream approval/currentness. Timing, identity, relationship references, array shape/order and extraction status remain immutable through this edit path. Do not replace this with arbitrary whole-task JSON editing.

7. Preserve the established workflow: one brief and reference, review and confirm, two creative directions, written refinement, explicit approval, creative brief and text storyboard. Wire only the minimal existing OpenAI creative methods needed to run it. Preserve success/review/approval gates. Partial or failed analysis must not silently become usable. A failed structured group retains successful observations but requires a consistent partial state under the documented default. Unimplemented music/SFX remains not_analyzed. Real failures never silently become sample results.

8. Add finite timeouts, bounded transient retries, capability checks, meaningful error states, usage/latency diagnostics and model/prompt/version-aware caching. Keep credentials server-side and out of source/logs. Existing sample mode must continue to work without a key.

## Test autonomously

Run existing verification, currently bash scripts/verify.sh, after reading it. Add focused contract/migration, HEVC/timing/proxy, correction replay/invalidation, provider failure and bilingual round-trip tests. Exercise the browser workflow with deterministic fake provider outputs. Fix defects and rerun affected checks, then complete required regression checks. Do not weaken tests to make them pass.

Default tests must make no paid model requests. Live tests require all of: explicitly enabled RUN_LIVE_MODEL_TESTS (or documented equivalent), a configured secret, permitted input clips and an explicit positive LIVE_TEST_MAX_COST_USD. The earlier US$20 suggestion is NOT spending authorization. Include retries and repeated attempts in budget accounting and stop before scheduling requests that cannot be bounded. Never print keys or ask me to paste them into source/chat.

If credentials, budget or real sample clips are missing, finish all offline implementation, mocked end-to-end tests, setup documentation and the live evaluation harness. Report live recognition and quality evaluation as not run with the exact missing inputs. Do not stop coding merely because live tests cannot run; do not claim mocked success demonstrates real bilingual accuracy.

## Documentation and delivery

Update English setup/interface/handoff docs and .env.example with placeholders. Include the exact capability/model settings, supported media matrix, migration behavior, default-off live-test instructions and test results. Do not mark provider-dependent features validated without evidence.

Create meaningful commits on the task branch. Ordinary push of that branch and creation/update of a draft PR are authorized when available and consistent with repository rules; otherwise use the environment's normal reviewable diff/PR handoff and report what was actually published. Do not merge into main, deploy, alter branch protections, delete branches or rewrite history in this task.

Finish with the branch/commit and PR or diff status; actual changed files; contract version and migration; what works with sample, mocked and real providers separately; exact checks passed/failed/not run; actual live-test spend if any; remaining limitations; and the shortest next steps for Frank and Andrea. Do not claim Frank's Mac or Andrea's environment was updated by cloud execution.
