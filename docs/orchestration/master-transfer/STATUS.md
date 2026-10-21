# Video Anatomy — State and Dependencies

Checked 2026-10-17 after Frank reported M2 completion.
This transfer inspected GitHub metadata and committed reports; it did not rerun tests.

## Current baseline
| Item | Verified state |
| --- | --- |
| Repository | Frankwu899/586-project |
| PR #3 | Open Draft, not merged |
| PR #3 head | da95ad3325a04b3b9f01cc7cb02a03af353208b5 |
| PR #3 branch | feat/video-analysis/bilingual-provider-contracts |
| PR #3 base | main at a456329e4fe8cab76669c8c8254cfed8ce11bbcb |
| M2 design docs | 0c54231db2cd778797e7ec0bc555188f7eda4ed7 |
| PR #4 | Open Draft, not merged; based on PR #3 branch |
| PR #4 branch | feat/workspace/m2-brief-experience |
| M2 implementation commit | 6d73254bb45deebf93a9030be9d86b0ca53d3865 |
| PR #4 report/head | 243db859353abf5a8ccc70de2028ed0b706da70c |
| Current protocol on M2 branch | v0.5 |
| Paid/live API evaluation | Not run per both handoffs |
| Human M2 UI acceptance | Pending |
| Main merge / deployment | Neither performed for PR #3/#4 |

PR links:
- https://github.com/Frankwu899/586-project/pull/3
- https://github.com/Frankwu899/586-project/pull/4

The master-transfer documentation branch is based on verified PR #4 head. Its
creation preserves M2 and PR #3 ancestry; it is not a merge to main.
Recheck current refs before coding. If dependencies merge later, compare content,
choose the updated base and bring the transfer records forward without duplication.

## Reported M2 outcome, verified report availability
docs/handoff/m2-brief-experience.md reports:
- Independent SQLite draft channel/version, atomic Apply/discard, no-op and retry
  idempotency, pending-input admission checks and stale-job protection.
- v0.5 claim metadata, draft/proposal APIs and archived migration.
- Bounded optional assistance, explicit proposal adoption, claim permission review.
- Editorial Studio summaries, one question, source-language content and manual mode.
- Independent typing/autosave during reference or assistance jobs.
- 428 Python tests, 10 frontend unit tests, 15 browser tests in full verification;
  a later focused browser copy test and lint/typecheck/build reruns also passed.
- Synthetic agent-inspected UI captures and targeted accessibility checks.
- No live-provider quality evaluation, human visual signoff, complete sequential
  Tab audit, native leave-dialog exercise or independent screen-reader audit.

These are the implementing agent's committed results. The transfer did not claim
a fresh test run or human acceptance. Read the report's exact AC/UX coverage.

## Provider foundation
PR #3 reports v0.4 normalized evidence, replaceable OpenAI vision/OCR/speech/creative
adapters, versioned correction and invalidation, H.264 plus supported HEVC
preprocessing. M2 evolves the current protocol to v0.5 while preserving timing.
Historical v0.1–v0.4 schemas/examples remain archives.

Supported HEVC claim: SDR Main 8-bit within current validation. Do not promise
MOV, 10-bit/HDR/Log or arbitrary profiles. Sparse vision sampling can miss brief
events. Actual recognition/linguistic/creative quality remains unverified.

## Module status is multidimensional
| Module | Product/spec state | Implementation/evidence state |
| --- | --- | --- |
| M1 | Core existing; detailed progress/resumption UX open | Task create/list/reopen foundation exists |
| M2 | Product/UIUX docs confirmed | PR #4 submitted; reported offline checks pass; live/human acceptance pending |
| M3 | Core intake established; focused UX decisions open | Media/playback foundation exists |
| M4 | D014 accepts sampled first-demo evidence | Providers/normalization exist; live quality pending |
| M5 | D014 settled; corrections/review UX still open | Correction/review foundation exists; new full spec not finalized |
| M6 | D015 contrast settled; detailed UX/quality open | Direction/refinement/selection/approval foundation exists |
| M7 | D016 text-only edit scope settled; content UX open | Output generation/editing foundation exists |
| M8 | Final export UX choices open | Markdown/CSV and historical export behavior exist |
| M9 | Runtime role not settled | Team templates/manual guides; not mandatory retrieval service |
| M10 | Current protocol v0.5 on M2 branch | Shared contracts/migration/provider/storage foundation submitted |

Do not label all modules complete because an end-to-end sample passes.

## Integration ownership
One coordinator owns shared decisions, state records and integration.
Delegate product discovery independently, but serialize competing shared-file edits.
Worktrees isolate working directories; they do not resolve contradictory contracts.

Shared contracts/migrations: backend/app/models.py, current schemas and generated
frontend/src/generated/contracts.ts; regenerate through repository scripts.
Shared integration: service.py, api.py, adapters.py and current domain helpers.
Common UI: App.tsx, styles.css, ui.tsx, api.ts.
M7/M8 share Production.tsx; use one writer or agree a split before parallel edits.
M2 also updated Directions.tsx and Production.tsx; inspect the delta, do not restore
older components. Current M2 domain/storage modules are already implemented.

Suggested dependency order:
1. Incorporate/read completed M2 v0.5 and common visual/state foundations.
2. Refine M5 and M3/M4 UX within D014's sampled scope.
3. Refine M6 using applied M2 and reviewed M5.
4. M7/M8 use current approved M6 and agreed outputs.
5. M1/common navigation follows settled readiness semantics.
M9 preparation can proceed independently. Discussion may happen in parallel even
when final coding must await an upstream contract.

## Next controller action
Start discussion-only. Read transfer and current repo. Give the takeover receipt.
Do not repeat the three accepted questions. Ask the next independent unresolved
choices; prepare relevant prototypes. Do not implement a module before its coherent
scope is settled and implementation is authorized.

## Costs and execution
Use fake/mocked tests without paid calls. A live run needs valid credentials,
explicit opt-in, positive authorized budget and permitted test media.
Keep keys/media/runtime databases out of ordinary commits and handoff text.
No merge/deployment is authorized by this transfer.

