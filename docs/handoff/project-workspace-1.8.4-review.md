# Video Anatomy 1.8.4 review corrections

- **Owner/request:** Frank / Yuqing Wu requested review and fixes using the
  installed engineering skills.
- **Environment/date:** Codex Cloud Linux, November 17, 2026 (Los Angeles).
- **Repository:** `Frankwu899/586-project`.
- **Reviewed candidate:** `9e9c0fd9265957fc6630808f8a7e3d56bc9062af`, PR #21,
  branch `fix/integration/1-8-4-reliability-planning`.
- **Comparison baseline:** 1.8.3 source
  `c3c8ebf95ab9381b9eeb0de9b9b8a24d1bfcc45c`.
- **Correction branch:** `fix/integration/1-8-4-review-corrections`, based on the
  reviewed candidate. The final response and correction PR record the pushed SHA.
- **Correction PR:** <https://github.com/Frankwu899/586-project/pull/22>, stacked
  onto PR #21's branch. No main merge is performed.

## Method and scope

Read the current agent instructions, release requirements, implementation
handoff, changed code and its callers/tests. Apply `architecture-patterns`,
`requesting-code-review`, `systematic-debugging`,
`verification-before-completion`, and the TDD dependency installed in the prior
task. The installed source versions are Superpowers
`22f0b463e7a5e579904dd6211a520321035526f7` and wshobson/agents
`9c61ab243def98f72da12abd41cfcf5bcd91af9d`.

Independent reviews covered evidence/speech, plan lifecycle/readiness, and the
client/recovery UI. The integrator checked runtime admission, shared interfaces
and integration. Findings required concrete triggers; new regressions failed
against the candidate before the implementation changed.

## Confirmed findings and fixes

### P2: replace machine speech by recovered audio scope

Switching from GPT whole-chunk text to Whisper segments retained the old entire
chunk next to the new segments, even with no human corrections. Individual new
segments did not contain the previous coarse interval, especially across silence.
The result was reported as successful speech evidence with duplicate text.

Use accepted, measured transcription-chunk boundaries to identify replaceable
machine evidence. Silence is part of the submitted audio interval; it must not
be inferred from word timestamps. Successful empty chunks can replace obsolete
machine text. Failed or partial chunks retain saved evidence. Preserve exact
human corrections, conflicting candidates and earlier revisions. Complete video
speech-cache reuse must carry the same measured replacement-scope records.

Keep native machine speech intervals separately from video frame display timing.
Frame quantization can extend a saved event beyond its real input chunk or make
a tiny failed-neighbor span look like part of a successful chunk. Replacement
therefore uses host-recorded native interval provenance, preserved across merged
event IDs. Unknown historical frame-only intervals are handled conservatively;
their ownership is never guessed by expanding chunk bounds or adding a tolerance.
An ambiguous overlap remains partial and visibly requires review. Correction
markers compare the user's submitted values with the saved values, so host-only
frame snapping during an unrelated edit does not turn machine speech into a
human correction. Preserve known native intervals before that conversion.

### P2: protect a Series during topic generation

Topic jobs did not identify their Series, and the Trash guard only examined
member Video jobs. Even an empty Series could be trashed during its provider
request; the eventual result then failed to save.

Persist the topic Series ID in existing job diagnostics and reject Trash while
that Series has a queued/running topic job. Explicit standalone or other-Series
jobs do not block it. Legacy active jobs without scope receive conservative
protection. No new persisted schema field is required.

### P2: make model changes explicit in source recovery

The generic Source Review retry always sent the project-wide selected speech
model. A preference chosen for another source could therefore switch the saved
source's profile, including historical views where the selector was hidden.

Generic Retry recognition omits the override and uses the backend's existing
saved-profile recovery. Explicitly labeled selected-model actions still send the
chosen model. A browser regression checks historical and current generic retries
and the explicit alternative, intercepting requests to avoid paid inference.

## Architecture and compatibility

These fixes strengthen three existing boundaries: measured evidence coverage,
persisted task ownership, and explicit user commands. Keep the current modular
monolith, provider adapters, SQLite stores and generated contracts. Original
files, correction identities, past evidence, approvals and saved production
remain intact. No dependency, application version or schema migration changes.

Context selection/token budgeting, aggregate growth and global queue capacity
remain worthwhile separate architecture reviews. They were not treated as
reproduced regressions or used to justify a speculative redesign in this patch.
Offline checks do not establish recognition accuracy or creative usefulness.

## Verification

During investigation, the candidate passed the existing 67 focused backend cases
and 54 frontend unit tests; that did not cover the newly reproduced failures.

An initial integration run was intentionally interrupted for the independent
reviewer's video-quantization finding. Before interruption, it also exposed the
existing legacy-import regression that requires earlier frame-only speech to
survive recovery. Its original assertion was preserved. Interrupted backend and
browser runs are not passing final verification; complete reruns follow the
final provenance correction.

Final application source is `977d599c6b9c75df1d54e3c65e38bdf257e67e03`.
Commit `6085ae6516496cea368a1b3a844c5e762d1a9ccc` changes only a browser setup
helper; later changes are documentation only.

The first completed project-browser run had 94 passes and one timeout before
feature assertions. The fixture helper briefly saw the dashboard and then raced
automatic restoration of the last project. Its error snapshot showed the target
project already open while it waited for a dashboard Open button. Use the
supported `?project=<id>` URL to pin the fixture; all original feature assertions
remain. The corrected case passed alone (7.2 seconds), and independent review
confirmed dashboard behavior remains covered in its dedicated tests. The final
complete project group is rerun from the test-helper correction.

| Check | Actual result |
| --- | --- |
| Complete backend, `env -u OPENAI_API_KEY RUN_LIVE_MODEL_TESTS=0 .venv/bin/python -m pytest -q` | **1,204 passed**, no skips, 312.48 seconds |
| Frontend unit suite, `npm --prefix frontend run test:unit` | **54 passed** |
| Python dependency consistency, Ruff, both authoritative/generated schema paths | Passed |
| Frontend generated contracts, TypeScript, ESLint and production build | Passed |
| Preserved-workspace Chromium, `npm --prefix frontend run test:e2e` | **52 passed**, 4.9 minutes |
| Injected-provider Chromium, `npm --prefix frontend run test:e2e:providers` | **4 passed**, 26.3 seconds; no live inference |
| Complete project Chromium, `npm --prefix frontend run test:e2e:projects` | **95 passed**, 5.8 minutes; exit 0 after the setup-helper correction |
| Independent final review | No remaining actionable findings; eight targeted regressions independently passed |

Focused backend, browser and reviewer runs overlap the complete suites; their
counts are not added to the complete results. The three complete browser groups
contain 151 distinct cases. Local logs are outside source under
`/tmp/video-anatomy-184-review-977d599-*.log`; the final project rerun is
`/tmp/video-anatomy-184-review-projects-clean.log`.
The verification components ran individually; this handoff does not claim an
exit-zero invocation of the combined `scripts/verify.sh` command.

Nonblocking diagnostics remain the upstream TestClient/httpx deprecation and
Vite's existing JavaScript chunk-size advisory. No test assertion was weakened
to pass these fixes.

## Delivery and limits

No paid inference, training, ledger reset, main merge or deployment is performed.
Real account access, the owner's original incident media and native Mac/Safari
acceptance remain outside the offline checks. The 1.8.4 binary archive predates
these corrections; a package must be rebuilt from the accepted correction commit
before claiming the delivered app includes them.
