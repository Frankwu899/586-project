# Evaluation corpus: workspace redesign

Prepared on 2026-10-18 for the owner's authorized USD 3 experiment. Collection,
probing and control preparation made **zero model API calls** and incurred **USD 0
in API charges**. These preparation results are not model-quality measurements.

## Runnable local inputs

The machine-readable catalog is
[`workspace-redesign-v1.json`](../../evaluation/manifests/workspace-redesign-v1.json).
Paths are relative to the repository. Media files remain under ignored
`.local-data/evaluation/`, never in Git or the application distribution.

| ID | Actual duration | Role | Provenance and limits |
| --- | ---: | --- | --- |
| `lei-jun-recording` | 15.53 s | Chinese recording with phone/platform noise | Owner upload, independently hashed; official account identity and product authenticity are not verified. |
| `lei-jun-ui-masked` | 15.53 s | Paired exclusion control | The same clip with manually specified opaque masks; **not** a clean original, independent example, or output of an automatic detector. |
| `dreamcatcher-product-ad` | 55.52 s | English product-ad control | Owner upload; no phone UI in inspected samples. Brand text, captions and exhibition signage remain valid content. Original-export provenance is not established. |
| `shared-culture-30s-excerpt` | 30.03 s | Public campaign control, obtained online | Opening excerpt of Jesse Dylan's *A Shared Culture*, not a complete consumer-product ad. Frame alignment makes the encoded duration slightly longer than 30 s. |
| `shared-culture-full` | 200.30 s | Intake rejection boundary | Full public source; exceeds the app's default 180 s limit. Excluded from default paid runs. |

There are **three independent sources**, not five independent test examples. The
masked pair and the excerpt share their parents' provenance. Do not split either
pair between training and held-out evaluation or claim representative accuracy
from this small collection. All sources have audio; a broad genre, language or
codec benchmark has not been assembled.

## What was actually found online

### Acquired and inspected

[A Shared Culture](https://creativecommons.org/about/videos/a-shared-culture/) is
an official Creative Commons mission/fundraising video by Jesse Dylan, published
for its 2008 campaign. The publisher identifies a CC BY-NC-SA license and supplies
image/music credits. Its downloadable EPUB sample is hosted by
[IDPF](https://github.com/IDPF/epub3-samples/tree/7651e2002b631e6577fadf7e9e0692fa6efb8746/30/cc-shared-culture).
The MP4, publisher-provided captions and package metadata were retrieved from
that commit through the permitted GitHub host. The video SHA-256 is pinned in the
manifest. It is useful as an independently sourced, clean-layout advocacy control;
it is not presented as a WeChat Channels video or a retail advertising campaign.

Attribution: *A Shared Culture* by Jesse Dylan / Creative Commons, licensed
[CC BY-NC-SA 3.0](https://creativecommons.org/licenses/by-nc-sa/3.0/). Refer to the
publisher page for the original photo and music attributions. The 30-second
excerpt was created for noncommercial project evaluation. Neither the original
nor the excerpt is included in the application package. Commercial reuse and
model fine-tuning have not been cleared by this evaluation work.

### Located, but not runnable media

| Resource | Verified finding | Why it is not a tested video |
| --- | --- | --- |
| [MG-VAU](https://github.com/Reforged-Labs/mg-vau) | Publisher lists 13 real mobile-game ads and analysis criteria. | Videos are on Google Drive, outside the current executor network allowlist. Its license separately reserves the underlying ads to game publishers for research/evaluation. No media downloaded. |
| [Ads-1k](https://github.com/yunlong10/Ads-1k) | A Chinese-ad dataset with segment annotations and extracted features. | Reviewed distribution provides metadata/features rather than acquired runnable original clips. Repository code licensing does not establish rights to all ad footage. |
| [AdShot](https://github.com/ostadabbas/AdShot) | Shot mappings and gated derived keyframes/audio. | No raw MP4 release; underlying ads are explicitly not licensed by the dataset. No gate accepted or media acquired. |
| [Tencent Ads Channels case library](https://training.tencentads.com/uploads/202306/iiP4sj9B_EQId5g.pdf) | Official-domain case-library PDF discovered in the search index. | Direct web fetch failed. A search result is not a downloaded video or an inspected full document. |
| [Tencent Ads Channels case review](https://training.tencentads.com/uploads/202410/C9X4m4Nq_sc7QRG.pdf) | Official 13-page PDF successfully opened, with industry examples and screenshot commentary. | A document resource, not a complete MP4. No video extraction, account login, or training license established. |

**No additional clean original WeChat Channels MP4 was acquired online.** The
owner's recording remains the runnable Chinese Channels-context example.
Document discovery must not be reported as video testing. No proxy bypass,
authenticated scraping, paywall/DRM workaround or unauthorized rehosting was used.

## Evidence labels and useful checks

Each manifest expectation is labeled `observation`, `source_statement`,
`user_context`, `hypothesis` or `guardrail`. Sampled manual review supports the
listed visible facts. It is not a full-frame temporal annotation dataset or an
independently adjudicated gold set. Prior assistant interpretations are not
ground-truth graph labels. Publisher captions are a reference transcription, not
a guarantee of independently checked word timings.

Important test distinctions:

- Phone clock, battery, follow status and engagement counters belong to recording
  context. Their repetition must not inflate the creative-content analysis.
- The recording's fixed right-side warning, main subtitles, ad branding and price
  claims must not disappear simply because they are stationary. The manual masks
  intentionally retain the warning `仅供娱乐 禁止赌博`.
- The 2.8 s recording subtitle says `小米澎程N90 Max`. This is observed text, not
  independent confirmation of a real vehicle, official release or feature set.
- DreamCatcher's two tips/configurations do not establish a two-complete-rods or
  buy-one-get-one offer. A participant or exhibition badge does not establish
  expert independence or event endorsement.
- A 30-second excerpt cannot support invented later scenes, a closing purchase
  CTA or complete-video outcomes.
- Background hypotheses, such as target demographics and buying intent, remain
  interpretations unless a suitable external source supports the narrower claim.

Keep these expected checks outside the model's analysis request when evaluating
unassisted output. Otherwise the test measures answer copying rather than
recognition or reasoning. Review real outputs against each applicable check as
`pass`, `fail`, `uncertain` or `not run`, citing output evidence. Report useful
completion rate, schema/citation validity, UI-noise errors, retained-content
errors, unsupported claims, latency, tokens/audio duration and metered cost
separately. A valid schema does not establish a useful analysis.

## Reproduce collection

With FFmpeg and Python available, run from the repository:

```bash
python3 scripts/collect_evaluation_media.py --derive
```

This copies matching owner uploads from `/workspace/attachments` only after a
SHA-256 match, reuses already present public source media, prepares the labeled
controls and writes `.local-data/evaluation/corpus-readiness.json`. Use
`--attachments-root /your/authorized/uploads` on another machine. Original files
are preserved. Existing mismatched originals are reported, never overwritten.

To retrieve the pinned public MP4 on a permitted connection:

```bash
python3 scripts/collect_evaluation_media.py --fetch-public --derive
```

The downloader accepts only the reviewed commit-pinned GitHub source, rejects
redirects and files over 32 MiB, and verifies SHA-256 before replacing its temporary
file. It uses the environment's normal proxy and TLS checks. It does not fetch the
blocked candidate datasets or make any model call. Current readiness comes from
the generated report, not the catalog's historical preparation status. Derived
encoding bytes can vary with FFmpeg versions; their actual hash is recorded.

## Preparation verification

- All five files were probed successfully; source hashes matched the pinned
  values. The manual-mask derivative retains the original 418 frames, 592×1280
  dimensions and 15.533333 s timeline.
- Manual contact-sheet review covered the source recording at 0.5/2.8/4/8/13 s,
  the fishing ad at 1/18/28/53 s, and the public campaign at 1/10/20/25 s. The
  derived mask was inspected at 2.8 s; this is sampled review, not exhaustive
  pixel-level certification.
- No video was submitted for fine-tuning. `training_allowed: false` is deliberate
  for every catalog entry; evaluation access is not treated as training consent.
- Live provider quality, spend and latency are separate run results. They cannot
  be inferred from successful media preparation.
