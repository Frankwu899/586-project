# Run Video Anatomy locally

For the Finder app with saved Keychain credentials and repeat-open behavior, use
[MAC_APP.md](MAC_APP.md). This browser launcher serves the built workspace and backend on your own computer.
The native Mac application has a separate build path in [desktop/README.md](desktop/README.md).
A source ZIP is not a DMG. All installation and launcher messages are English;
the app defaults to English and can switch to Chinese. New Research explanations
follow the app language. Verbatim evidence keeps its source language; Ideas has
an independent generation language.

## Start on macOS

1. Extract the new bundle. Keep your previous bundle until any saved library has
   been copied and verified.
2. Double-click **Start Video Anatomy.command**, or run
   `bash scripts/start-local.sh` from the extracted folder. If Finder requires it,
   right-click the launcher and choose **Open**.
3. This browser launcher requires Python 3.12 and FFmpeg/ffprobe. If Homebrew is
   installed, missing prerequisites are installed on the first run. Otherwise
   install [Homebrew](https://brew.sh/), then run `brew install python@3.12 ffmpeg`.
   The first run installs pinned Python packages. The bundle contains the built
   frontend; Node is needed only when building from source.
4. Configure your key in **API connection** in the workspace. On macOS, Remember
   on this Mac stores it in the login Keychain. Otherwise it stays in server
   memory for this session. It is never returned to the page or written to task
   storage. An existing `OPENAI_API_KEY` environment variable works for the
   Terminal launcher; the Finder app ignores inherited keys. Use `--prompt-key`
   only if you specifically want the older hidden Terminal prompt.
5. The browser opens `http://127.0.0.1:8000`. Keep Terminal open. Stop with Ctrl+C.

To open saved work without any paid provider, run:

```bash
bash scripts/start-local.sh --offline
```

If port 8000 is occupied, close the old server or add `--port 8001`. Only one server
may open a given library at a time, including when different ports are used.

Windows: install Python 3.12 with `py`, plus FFmpeg/ffprobe on PATH, then open
**Start Video Anatomy.cmd**. Linux: use `bash scripts/start-local.sh` after
installing the same dependencies. Native macOS/Windows execution must be verified
on those operating systems; Linux tests do not establish Mac compatibility.

## Your files survive app upgrades

The default persistent library is outside the installation folder:

| System | Library |
| --- | --- |
| macOS | `~/Library/Application Support/Video Anatomy/` |
| Windows | `%LOCALAPPDATA%/Video Anatomy/` |
| Linux | `${XDG_DATA_HOME:-~/.local/share}/video-anatomy/` |

`tasks.sqlite3` retains projects, histories and saved editor drafts. `media/`
contains copied uploads and their current playback derivatives. `provider-cache/`
retains reusable paid results and sanitized usage records;
`provider-budget.sqlite3` retains the historical Cloud experiment ledger without
limiting local requests. Despite the historical name, **provider-cache is persistent
project data, not a disposable preview cache**. Back up the whole library after
closing the app. Moving the original upload does not break its managed copy.

A separate derived-cache location is reserved under
`~/Library/Caches/Video Anatomy/` on macOS. Existing originals and playback files
have not been moved out of the persistent library. This release does not expose a
bulk cache-delete button that could remove paid results or user media.

The launcher prints both locations. `/api/local/runtime` reports the active paths,
retained size and import outcome to the local application. `--data-dir PATH` or
`VIDEO_ANATOMY_DATA_DIR` selects an explicit library; `--cache-dir PATH` or
`VIDEO_ANATOMY_CACHE_DIR` selects a derived-cache location.

## Preserve an earlier local test

Stop the old application before importing. If the new launcher is in the same
folder as an earlier `.local-data/live` and the stable destination does not yet
exist, it copies the old library automatically. SQLite backup includes committed
WAL content; every other retained file is checked by SHA-256. The new folder is
activated only after verification. The old folder is left in place.

When the old bundle is elsewhere, import it explicitly on the first launch:

```bash
bash scripts/start-local.sh --migrate-from "$HOME/Desktop/video-anatomy-local/.local-data/live"
```

If the destination already exists, explicit import stops instead of merging or
overwriting projects. To examine another library safely, choose an absent path:

```bash
bash scripts/start-local.sh --data-dir "$HOME/Library/Application Support/Video Anatomy Imported" --migrate-from "/path/to/old/.local-data/live"
```

Use that same `--data-dir` on later launches. If import fails, its temporary copy is
removed and the original remains. A `library-import-*.json` receipt records source,
verification hashes and date after success. Going back to the untouched old
bundle is possible, but new edits made in the imported library are not copied back.
No silent merge or destructive rollback is performed.

## API usage and experiments

Starting the app, importing media and opening saved work do not call models.
Real analysis, Structure research and AI generation can incur charges when
requested. A fictional sample remains deterministic. Credentials being configured
does not establish billing availability or model access.

The local app pins `gpt-6.1-sol` for visual analysis, Structure synthesis,
Ideas, Production, input assistance and bounded background retrieval, including
when an older shell still contains Luna or other model overrides. Separately
invoked Cloud evaluation retains independently selected models. The
owner-approved audio exception uses `whisper-1` for transcription
with segment timestamps. Speech is enabled; no other capability falls
back to an older model. Existing speech and compatible caches are retained.
The launcher defaults to zero automatic retries. Provider
configuration is backend-only. Since v0.7.5, local launchers disable experiment
budget enforcement. There is no client-side spending ceiling, reservation gate,
accounting pause or budget token precheck. Old ledger files remain untouched;
upgrading does not require clearing data or replacing your key. Separately invoked
Cloud experiments retain their authorized USD 3 shared limit. OpenAI billing and
provider rate/access limits still apply. The provider's billing page remains the
source for actual billed totals. A local build or simulated test is not a live
API result.

Delivery bundles contain no owner-supplied videos or preloaded case projects.
Import the video you choose after opening the app.

API connection shows **API usage**, recorded estimates and attempts without a
known cost. **Refresh usage** reads existing records without making a model call.
Incomplete or unavailable estimates do not block generation. The old experiment
ledger, reservations and accounting pause are not shown as client restrictions.

## Troubleshooting

- **Key or quota failure:** verify the key's project, model permissions and balance.
  Use API connection to replace the key. Do not share the key in chat.
- **Connection failure:** the local machine must reach the configured provider.
  Managed cloud environments also need explicit network access to that domain.
- **Missing media:** use the original-file repair control to choose the identical
  uploaded file. Its SHA-256 must match; another edit/export must be uploaded as a
  new reference. A missing HEVC playback copy can be rebuilt if the stored frame
  mapping is reproduced exactly. Deliberately deleted references are not restored
  by relinking. Restore a full library backup if the original is unavailable.
- **Existing library/import conflict:** close the old app and use the import steps
  above. The launcher intentionally refuses to replace a populated library.

Share safe error codes and model names for support, not API keys or full private
logs. Saved work remains in the library when the application closes.
