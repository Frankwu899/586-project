# Source Review playback recovery

- Owner/request: Frank reported unavailable local playback in Chrome alongside
  partial speech and a separate multi-reference report timeout.
- Environment/date: Codex Cloud Linux, November 17, 2026 (Los Angeles).
- Branch: `fix/analysis-review/playback-recovery`.
- Base: PR #22 at `98d124d42bc5d534d5e891f23e58a0b51bdfba3b`.
  This fix depends on that unmerged 1.8.4 candidate; main remains unchanged.
- Final commit, publication and package verification are recorded in the delivery.

## Evidence and confirmed defects

The supplied support export contains successful HTTP transcription responses
with rejected segment bounds (`audio_timestamps_invalid`). It contains neither
a browser MediaError nor a report-synthesis timeout record. Version 1.8.3 in
those records identifies the original evidence run, not necessarily the current
application. Source recognition and browser playback use different decoders.
The original Ro-8 file and the owner's local file requests are unavailable here;
the cause of its initial playback failure remains unconfirmed.

Source Review displayed saved recognition diagnostics under its playback error.
It also retained an errored media element after asynchronous preview preparation
because its resource key and playback URL did not change. Two new Chromium
regressions failed on those exact behaviors before the implementation changed.

## Changes

- `SourceReview.tsx`: report browser media error code/name, ready/network state,
  resource identity and saved source codecs separately from recognition details.
  Do not export browser error strings, file paths or raw media URLs. Keep saved
  evidence diagnostics available in their existing recovery section.
- Replace the media element after a newly successful file-preparation job or
  exact-original relink, and when the preview path changes. Queued/running jobs
  do not trigger the preparation reload. A loaded metadata event clears the
  playback failure. Report and recognition jobs do not reset the player.
- `status.ts`: allow only the new operational media fields in support exports.
- Browser fixture/tests: simulate a failed media request, retain an independent
  saved speech failure, then restore real local media delivery and run the real
  preview-preparation job. Check metadata loading, subsequent seeking and exact
  preservation of saved evidence and original hash.

No provider, persisted schema, media conversion or original-file changes.
Multi-reference architecture/output changes are a separate task.

## Verification

- Red: both new regressions failed for unrelated speech diagnostics and an
  errored player remaining at readyState 0 after preparation.
- Green: both regressions passed using real local FFmpeg media and Chromium.
- Frontend: 54 unit tests, ESLint and TypeScript/production build passed.
  Vite retains its existing bundle-size advisory.
- Complete resource browser suite: 18 passed with
  `npm run test:e2e:projects -- project-resources-183.spec.ts`.
- Live model calls, the owner's Ro-8 media, native macOS Chrome and macOS
  launcher behavior: not tested. Tests use synthetic media and no API key.

## Next diagnosis

Check whether Open original plays in the owner's Chrome. With this candidate,
export the playback-specific support details if the source still fails. A code
4 can mean an unsupported source or a failed file response; it alone does not
establish a codec cause. Inspect local file HTTP status/ranges and actual media
streams before changing conversion policy. Re-running paid recognition is not
a playback repair. Do not delete the library, evidence or human corrections.
