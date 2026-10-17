# Run the interactive app with your OpenAI API key

This entrypoint serves the built React workspace and persistent backend together
on your own computer. It enables real providers. The existing `start-demo`
launcher continues to disable paid providers.

## macOS

1. Extract the local API bundle to a new folder. Keep the folder together; do not
   replace an older folder containing saved tasks.
2. Double-click **Start Video Anatomy.command**. Alternatively, in Terminal run
   `bash scripts/start-local.sh` from the extracted folder. On macOS, right-click
   the launcher and select **Open** if Finder requires an explicit opening.
3. The launcher needs Python 3.12 and FFmpeg/ffprobe. If Homebrew is already
   installed, it installs missing prerequisites automatically. Otherwise install
   [Homebrew](https://brew.sh/) and run `brew install python@3.12 ffmpeg`, then
   launch again. The first run installs pinned Python dependencies over the
   internet. The bundle already includes the built frontend; Node is unnecessary.
4. Paste the complete key at the **API Key:** prompt and press Return. No dots or
   characters are echoed. The launcher retains it only in backend process memory;
   it does not write it to a file or send it to the browser. Existing
   `OPENAI_API_KEY` environment configuration also works. `.env.local` is not
   automatically sourced. Never send the key through chat or commit it to Git.
5. The browser opens **http://127.0.0.1:8000**. Leave Terminal open. Stop the server
   with Ctrl+C. Reopen the same launcher/folder to resume saved tasks; enter the
   key again if it was not supplied by the environment.

If port 8000 is occupied, stop the old demo or run
`bash scripts/start-local.sh --port 8001`. The launcher stops before asking for a
key when its requested port is occupied. Data remains under `.local-data/live`;
offline-demo data remains under `.local-data/demo`. Back up the entire data folder
to preserve SQLite records, originals, derivatives and provider caches.

On Windows, install Python 3.12 (including `py`) and FFmpeg/ffprobe on PATH, then
double-click **Start Video Anatomy.cmd**. On Linux use `bash scripts/start-local.sh`
after installing the same prerequisites. macOS and Windows execution still need
verification on those actual operating systems; Linux checks are recorded in the
handoff.

## First supplied-video experiment

The private local bundle may contain `samples/guandan-reference.mp4`, the clip
supplied by the owner. Startup imports it as a real task named
**掼蛋视频 · 真实识别实验** once, by content hash. It neither analyzes it nor
creates a brand brief, invents product facts, or confirms/approves anything.
Repeated startup respects previously deleted media. The video is excluded from
Git and must not be treated as a redistributable repository fixture.

1. Select the experiment task and open **Reference**. Confirm playback first.
2. Click **Start analysis** once. This sends bounded sampled frames and audio
   to OpenAI and can incur charges. Wait for the result; inspect the job/analysis
   status as well as any visible error. Key configuration at startup is not proof
   of accepted credentials, available model permissions or billing balance.
3. Check Chinese subtitles/speech, scene observations, hook/product/CTA roles,
   and the separation between visible evidence and interpretation. Correct the
   result before **Use this reviewed analysis**; the launcher never confirms it.
4. To evaluate new creative directions, enter the actual target brand/task and
   approved claims in **Inputs**, then Apply. Reference-video product facts and
   audience assumptions are not automatically facts about the new target brand.
   Choose Chinese or English in **Directions**, generate, review and explicitly
   approve a direction before generating **Production** materials.

Use the owner's commentary as a separate human evaluation reference for the
first pass. A second pass can compare the same task with explicit contextual
notes. This distinguishes visible evidence, background knowledge and hypotheses
instead of presenting supplied commentary as independently discovered research.
See [the case checklist](docs/evaluation/guandan-context-case.md).

## Models, costs and API failures

The current compatibility baseline is `gpt-4.1-mini` for visual analysis, M2 and
creative generation, and `whisper-1` for segment-timestamped speech. These are the
models supported by the existing adapter, not a claim that they are the latest
model families. Newer families require adapter/format validation; changing an
arbitrary model name alone is insufficient. Provider IDs remain configurable as
documented in [README_SETUP.md](README_SETUP.md).

The local launcher defaults to Chinese analysis, 12 sampled frames, a 90-second
timeout per request and **zero automatic retries**. Separate recognition
capabilities may still make multiple requests. Startup and media import make no
model requests. The dedicated fictional sample still uses deterministic sample
adapters. Ordinary real-task analysis and AI assistance/generation use the API
when explicitly triggered in the UI.

This app does not impose a cumulative dollar cap. Track actual project spending
in [OpenAI Usage](https://platform.openai.com/usage); a project budget is an alert,
not a hard stop. Keep auto refill off for the owner's $20 project balance and
begin with one short clip. The default-off automated live harness has its own
budget controls; it has not been run by this launcher.

- Authentication/permission failure: check the key's project and access to
  Responses and Audio Transcriptions. Restart to supply a corrected key.
- Credit/quota failure: check billing for the same organization/project.
- Request/model rejection: check model availability and supported configuration.
- Connection failure: the local computer must reach `api.openai.com`; a managed
  cloud run additionally needs that domain allowed in its environment settings.

Do not put a real key in a command argument, screenshot, browser field or error
report. Share the application's safe error code and model names when diagnosing
an unsuccessful run. Automatic web research is not included in this version.
