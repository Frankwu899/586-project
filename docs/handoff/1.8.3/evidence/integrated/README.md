# Integrated 1.8.3 browser evidence

Six representative screenshots are copied unchanged from the verified Linux
Chromium run. They show the actual application with locally generated media and
authored synthetic evidence, directions and shots. No real provider inference,
Safari or native macOS acceptance is demonstrated by these images.

| Screenshot | Meaning |
| --- | --- |
| `native-1440x900-100-source-review.png` | Desktop original-source player and evidence timeline at native 100% zoom. |
| `native-1440x900-100-analysis-graph.png` | Source-linked Analysis with readable graph labels. |
| `native-1440x900-100-production-table.png` | The structured Storyboard Sheet at desktop size. |
| `native-1280x800-200-production-table.png` | Native 200% page zoom; the sheet scrolls locally to its right-hand columns and retains an editable focused cell. |
| `narrow-390x844-100-source-review.png` | Source Review at a 390px CSS viewport, with native media controls and stacked evidence details. |
| `narrow-390x844-100-content-plan.png` | Standalone Video planning at a 390px CSS viewport. |

The desktop cases use Chromium 154.0.8037.57's real Page zoom, with
`settingsGetDefaultZoom` matching the requested zoom and CSS `zoom` remaining
`1`. Window dimensions include browser chrome; actual inner dimensions and
device pixel ratios are recorded in `native-full-receipts.json`. The 390px case
is a narrow CSS viewport at native 100%, not a claim that Chromium's outer
window is 390px wide. Screenshots are capture moments; a native loading
indicator is not evidence of failed recognition or proof of playback quality.

`summary.json` is the unchanged full-run summary: 63/63 surface checks, zero
failures and zero processing requests across eight native window/zoom
combinations plus the narrow viewport. Its 81 screenshots and nine CSV receipts
refer to the complete local run; only six screenshots are included here.
`native-full-receipts.json` preserves the detailed dimensions, control
reachability, scroll ownership and saved/exported revision receipts.
The separate `source-playback-receipt.json` records actual local synthetic-media
playback from 0 to 0.825 seconds, followed by pause and a seek to 3 seconds, with
`readyState` 4 and no media error. It does not change the matrix totals or
establish recognition quality.

Complete local artifacts and logs remain at:

- `/workspace/artifacts/video-anatomy-183/native-full/verified/`
- `/workspace/artifacts/video-anatomy-183/native-full/verified-run.log`

Those absolute paths describe this Cloud workspace, not files shipped in the
Mac test ZIP. No implementation changes or archive creation accompany this
evidence selection.
