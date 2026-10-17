# Local API launcher and first supplied-video experiment

Date: 17 October 2026. Owner: main orchestrator.

## Change and baseline

The owner requested API setup and an interactive product on macOS, with complex
setup handled by the agent. The prior offline launcher intentionally disables
providers; it cannot validate a real key. This change adds a separate local live
launcher serving the built UI and API together on loopback. A hidden terminal
prompt keeps the key in backend process memory only. Existing environment-based
credentials remain supported. Startup/import do not call a model or imply API
authentication success. The offline launcher remains unchanged.

Branch: `feat/integration/local-api-launcher`, based on PR #5's integration commit
`0518ae3163e1ce16cb95e2b69ceeed1be6062ba0`. The Draft PR targets
`feat/integration/creative-workspace-demo`. PR #5 depends on #4 and #3; main is not
the complete application baseline. The starting worktree was clean. No merge,
force push, public deployment, credentials or runtime media in Git.

## Files and behavior

- `scripts/local_server.py`: backend-only key prompt, adapter-compatible settings,
  pre-reserved loopback port, persistent real-task import, built UI mount and
  automatic browser opening. Chinese analysis, 90-second timeout and zero
  automatic retries are local-entrypoint defaults; environment overrides remain.
- `scripts/start-local.sh`, `Start Video Anatomy.command`: macOS entrypoint;
  discovers Homebrew under Finder's PATH, installs missing Python 3.12/FFmpeg via
  existing Homebrew, then installs pinned Python dependencies. No Node is needed
  with the bundled UI. If Homebrew/runtimes are absent, reports the prerequisite.
- Windows launchers are included but not executed on Windows.
- `scripts/package_demo.py`: optional local API bundle naming and explicitly
  requested private MP4 inclusion. Default offline packaging excludes media as
  before. No API key, database, cache or installed dependency is packaged.
- `LOCAL_API.md` and the setup link describe startup and actual UI actions.
- `docs/evaluation/guandan-context-case.md` preserves the supplied video's
  observation/context/hypothesis distinctions and a staged evaluation plan.

The private supplied clip imports once by content hash as a **real**, unanalyzed
task. Restart does not duplicate it or restore explicitly deleted media. No M2
brief, analysis, review confirmation or creative approval is invented. Recognition
can run before a target brand brief is applied; creative generation still requires
the established input/review/language/approval gates. Shared models, migrations,
frontend and provider request formats are unchanged.

## Verification

Verified in the managed Linux workspace, not on the user's Mac:

- Targeted Python suite: **10 passed**, including secret handling, refusal of
  echoed input, supported-model validation, live UI/API serving, persistence,
  no automatic paid work, idempotent import/tombstone handling, and the existing
  offline-credential isolation test. Existing TestClient deprecation warning only.
- Ruff for changed Python files, shell syntax checks and `git diff --check` passed.
- Interactive PTY smoke: hidden placeholder key entry did not echo; server started
  with the supplied real video. No real credential was supplied or sent.
- Chromium checked the built single-port UI/API, supplied-video playback, enabled
  explicit analysis action (not clicked), task creation/refresh persistence and
  area restoration, with no browser errors. Saved tasks had no analysis jobs.
- The private ZIP was extracted to a separate directory and smoke-tested again:
  built UI/API, automatic import and playback of the bundled clip passed with no
  model jobs. This reused the installed Linux interpreter/dependencies; a fresh
  Mac/Homebrew installation was not tested. ZIP inspection confirmed executable
  macOS launcher metadata, one explicitly included MP4, and no environment files
  except the placeholder example, installed dependencies or runtime directories.
- An occupied loopback port exited before requesting a key or opening a browser.

## Remaining work and product scope

The current cloud environment has no configured OpenAI key and its enforced
destination policy does not include `api.openai.com`. This task therefore prepares
local execution; it does not claim a successful paid request. The user must enter
the key on their Mac, run one explicit analysis and report/review the result.
The app has no aggregate dollar cap; the owner's $20 project allocation and
disabled auto refill are not an application-side spending limit. First-pass
compatibility models remain gpt-4.1-mini / whisper-1; newer families need a separate
adapter compatibility change and actual evaluation.

The owner now wants cultural, audience and product-background research to inform
analysis. This extends the earlier no-active-search scope as a future requirement.
It is recorded, not silently implemented. First evaluate video-only evidence and
then explicitly supplied background; later source-backed research must preserve
attribution and distinguish claims/hypotheses from visible evidence.

Human Mac startup, API authorization/model access, real OCR/ASR accuracy and
creative quality remain unverified. No full regression suite was repeated for
this isolated launcher change; the prior integration's results are in its handoff.
