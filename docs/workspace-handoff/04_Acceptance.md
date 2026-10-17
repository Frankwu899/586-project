# Acceptance criteria

Run meaningful backend, unit, browser and visual checks with deterministic sample/fake providers. Actual results belong in the final handoff, not this plan.

| ID | Observable requirement |
|---|---|
| WS-01 | Create two tasks, switch/reopen, retain correct task/area/draft without cross-task mixing |
| WS-02 | M2 inputs and reference processing work in either order; existing M2 cases still pass |
| WS-03 | Visual samples are labeled samples; every speech/text event is accessible independently |
| WS-04 | M5 draft survives refresh/switch; explicit Apply produces correct revision and clears review; confirm remains separate |
| WS-05 | Draft save does not increment task version or reject an otherwise valid in-flight job; formal change rejects stale results |
| WS-06 | Pending analysis/direction/production edits block precisely dependent operations on client and direct API |
| WS-07 | Concurrent stale saves, duplicate formal submits and transaction failure preserve data; no-op does not invent revisions |
| WS-08 | Explicit language selection gates first generation; language change preserves reviewed analysis and invalidates creative approval/output |
| WS-09 | A/B substantive contrast instructions, source-language preservation and exact M2 qualification propagation tested offline |
| WS-10 | Manual direction edits label old auxiliaries; production excludes stale rationale/resources while preserving M2 constraints |
| WS-11 | Original shots accept empty citations, invalid supplied citations fail; rows retain total duration and text-edit boundaries |
| WS-12 | M6/M7 drafts restore; dirty export saves first or cancels; failure never exports older content as newly saved |
| WS-13 | PDF saved-document view, CSV and Markdown contain exact versions/currentness, safe text and deleted-source labels |
| WS-14 | Delete original/proxy, playback unavailable, history retained; unrelated active source/output remains valid |
| WS-15 | v0.5 migration archive exact, reopen idempotent, historical contracts unchanged, failed migration rolls back |
| WS-16 | Offline sample completes all four areas through approved output/export with no key or network model calls |
| WS-17 | Desktop/narrow layouts, keyboard core actions, focus/error labels, reduced motion and bilingual print capture checked |

Use `bash scripts/verify.sh` after integration. Keep old substantive assertions, adapt navigation and newly explicit language selection rather than suppress tests. Report provider quality, human visual acceptance and checks not run separately. No fake test establishes actual recognition/marketing quality.
