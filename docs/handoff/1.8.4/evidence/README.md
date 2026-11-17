# Video Anatomy 1.8.4 selected browser evidence

This directory contains nine representative screenshots and seven original JSON
receipts selected from `/workspace/artifacts/video-anatomy-184/native/`.
`evidence-manifest.json` records their original paths, sizes, image dimensions and
SHA-256 digests. It is an inventory, not an additional test result. The copied
receipts are unchanged; screenshots referenced by them but not selected here
remain in the local artifact directory.

These are offline Linux Chromium checks using authored synthetic project,
analysis, transcript and provider-diagnostic records, plus real generated local
MP4/WAV bytes. Authentication and partial-speech examples are authored test
states. They do not demonstrate live API/model quality, the owner's actual
Ro8/Ro10 failure, macOS installation, Gatekeeper, Safari or OS-level IME behavior.

## Counts and source boundaries

The evidence covers **72 UI checks and one real local playback/seek check**,
across two separately recorded source snapshots:

| Phase | Checks | Source evidence |
| --- | ---: | --- |
| Original frozen working tree | 63 surface checks + 6 speech/Activity checks + 1 player check | `frozen-source-snapshot.json`; HEAD was `76d9815a52e51e14fc4736acc42b7d652e5a8cd8`, with the tested working-tree file hashes recorded individually |
| Later saved-evidence bridge | 3 Analyze-dialog configurations | `postchange-source-snapshot.json`; HEAD was `559ce38f191cd75290cd51fe16a9efd14dd37662`, with the two later application-file hashes recorded below and per case |

All recorded checks passed. The original full matrix was **not** rerun after the
bridge. These results must not be attributed to one final clean source SHA or to
the later packaging commit. The bridge changed
`frontend/src/project/ActivityPanel.tsx` and
`frontend/src/project/Resources.tsx`. The supplement also records a change to the
test fixture during its run; per-case hashes identify the unchanged application
files it actually checked.

| Application file | Original SHA-256 | Bridge SHA-256 |
| --- | --- | --- |
| `ActivityPanel.tsx` | `0cc387bb88626360317841936615b378136f1d6955bf9d82394ff1ce6325fbf7` | `d860603de6ed830e35354386a3900ce0e25367caa5b9acefd437b0563dd98d78` |
| `Resources.tsx` | `d809f8256426865b1753d88a392efe9e6cf140ef4cd4a56b5bce43062bb64d72` | `ade0e8665c3804f2d6b0e96e009c9eb8a4526842dc241e043bda55064310f815` |

The native checks recorded **zero processing POST requests**; supplementary
checks also confirmed saved jobs and evidence unchanged. In particular, the
bridge supplement checked the controls, default unchecked state, disabled model
selector, Cancel and Escape focus return, but **did not click Generate**. The
separate automated saved-evidence API case did submit offline and received the
expected `provider_not_configured` failure without recognition or evidence
changes; its local log is listed below.

## Selected screenshots

| Screenshot | Meaning |
| --- | --- |
| [Desktop Content plan](verified/native-1440x900-100-content-plan.png) | Video/series management, native 100%; original frozen phase |
| [390px Content plan](verified/narrow-390x844-100-content-plan.png) | Management at a narrow CSS viewport, native 100%; original frozen phase |
| [Production table at 200%](verified/native-1280x800-200-production-table.png) | Readable saved table and local scrolling at actual Page zoom; original frozen phase |
| [Activity processing details at 200%](extra/wide-native-200-activity-partial-failure-details.png) | Named historical source, saved revision and partial diagnostics; original frozen phase |
| [Partial speech and model choice at 390px](extra/narrow-native-100-speech-model.png) | Latest authored authentication failure alongside saved speech and an explicit model choice; original frozen phase |
| [GPT whole-chunk evidence at 200%](extra/wide-native-200-gamma-whole-chunk.png) | Authored audio-chunk range; word/sentence alignment is not claimed; original frozen phase |
| [Saved-evidence controls at 200%](dialog-supplement/native-1280x800-200-speech-model-disabled.png) | Dialog scrolled to the disabled model control and reachable Cancel/Generate buttons; bridge phase |
| [Saved-evidence dialog at 390px](dialog-supplement/narrow-390x844-100-cancel-and-submit.png) | Narrow dialog controls; bridge phase |
| [Local player paused at three seconds](native-player-paused-seek.png) | Actual generated MP4 playback advanced to about 0.597s, then paused seek reached 3s without a media error; original frozen phase |

Desktop 100/125/150/200% cases used actual Chromium **Page zoom**, verified through
`chrome.settingsPrivate` and recorded viewport/device-pixel-ratio values. They
did not use CSS `zoom` or CDP page-scale emulation: receipts report CSS zoom `1`
and visual viewport scale `1`. The 390px cases are explicitly **CSS viewports at
native 100%**, not mobile-device or native-zoom claims. Desktop filenames contain
the requested outer-window dimensions; actual content viewport dimensions are
in the receipts. Screenshots use CDP `Page.captureScreenshot` with
`fromSurface: true` and `captureBeyondViewport: false`, preserving the physical
native-zoom rendering rather than a full-page screenshot approximation.

## Receipts and complete local logs

- `native-summary.json`: aggregate counts, limitations and the two-phase scope.
- `verified/native-full-receipts.json`: all 63 original surface checks, dimensions,
  reachable controls, no failures and no prohibited processing calls.
- `extra/receipts.json`: six speech/Activity checks, model behavior, exact-history
  navigation and retained saved state.
- `native-player-receipt.json`: one real local MP4 playback and paused seek.
- `dialog-supplement/receipts.json`: three postchange dialog cases and their exact
  application-file hashes.
- The two `*-source-snapshot.json` files: source provenance for the original and
  bridge phases; neither is a final packaging receipt.

Full local artifacts and logs remain under
`/workspace/artifacts/video-anatomy-184/`, including:

- `native/native-full.log`, `native/extra/receipts.json` and
  `native/dialog-supplement.log`;
- `reliability-browser-final.log` (seven independent reliability cases passed)
  and `reliability-saved-only-final.log` (the explicit legacy-scope bridge case
  passed);
- `integrated-final-verify.log` and `integrated-project-final.log` for the parent
  integration run. Their completion is reported by the main handoff, not inferred
  from this screenshot selection.

The original native set contains 81 surface screenshots, ten supplementary
speech/Activity screenshots, one player screenshot and nine bridge screenshots.
Only the nine listed above are copied here. Preflight captures, initial harness
navigation failures, browser profiles and failed-test traces are not selected as
passing product evidence.
