# Video Anatomy for your Mac

This ZIP contains **Video Anatomy.app**, a Finder launcher for the local browser
workspace. It uses the Python 3.12 and FFmpeg already installed on your Mac; it is
not the self-contained Electron installer or a DMG. The launcher source and
Linux integration tests are verified. Finder, Keychain prompts and Gatekeeper
still require a real Mac acceptance run. The app is not signed or notarized.

## Open and reconnect

1. Stop the old Terminal launcher once with **Control+C**. Keep the old folder
   and your saved library; do not delete either to fix a startup problem.
2. Extract the ZIP fully. Move **Video Anatomy.app** to a stable folder, such as
   your user Applications folder. Open it from Finder. If macOS asks for approval
   for this downloaded app, use its per-app Open option in Finder or Privacy &
   Security; do not disable system security checks.
3. First launch prepares the pinned Python dependencies in your local cache.
   This may take a few minutes and needs internet access. The workspace opens in
   your normal browser when it is ready; no Terminal window is needed.
4. Open **API connection**, paste your complete OpenAI project secret key, and
   choose **Save key**. Keep **Remember on this Mac** selected to store
   it in the macOS login Keychain. Allow Keychain access if macOS asks. The key is
   not saved in the app, task database, browser storage, logs or ZIP.
5. Reopen the saved task and start analysis once. To reopen after closing the
   browser, double-click the same app again. It reconnects to the existing local
   server instead of starting a second copy. Restarting the Mac starts a new
   server next time and reloads the saved Keychain credential.

Closing the browser leaves the local server available to finish work and reopen.
When switching to a newer or moved app, its launcher verifies the old session
and closes it only when idle. If work is running, wait for it to finish. Saved
work is not deleted, and interrupted paid work is never automatically retried.

If Python or FFmpeg is missing, install Homebrew and run this **once** in Terminal:

```bash
brew install python@3.12 ffmpeg
```

No case video is preloaded. Import the video you choose. Existing tasks and media
remain in `~/Library/Application Support/Video Anatomy/`, shared with v0.7.
Keep the `provider-budget.sqlite3` ledger; upgrading or changing a key does not
reset the experiment budget. Launcher/runtime logs are under
`~/Library/Caches/Video Anatomy/` and contain no API key.

## If the connection fails

**Check connection** makes a non-generating request for model metadata. It sends
no video and consumes no model tokens. A successful check establishes that the
key is accepted for that metadata request; it does not prove generation/audio
permissions, account balance, or model output quality.

- **HTTP 401:** OpenAI rejected the credential. Create a replacement project
  secret key at https://platform.openai.com/api-keys and save the complete string
  in API connection. Never use the masked key displayed in the list.
- **HTTP 403:** OpenAI denied access. Check project and key permissions for
  Responses and the configured models. A Models
  read restriction alone is shown as an unverified check, not an invalid key.
- **Billing/quota:** inspect billing for the project/organization owning this
  key. Buying credit does not itself establish key permissions.
- **Network or certificate:** verify that the Mac can reach `api.openai.com`.
- **Keychain:** unlock your login Keychain and allow access, or save for this
  session only. Replacing with session-only mode removes this app's old saved
  credential, so it cannot return on restart.

Errors appear inside API connection and beside the failed operation. If one
persists, share only the displayed error/code, never the key. Saving a new key
updates Timeline, Structure, Ideas and input assistance together without a
restart. Finish running operations before changing or forgetting the key.

## Workspace controls and language

Use **New project** to create a workspace. Each project's **•••** menu offers
Open project, Rename project and Move to Trash. **Close project** is below the
project list. Deletion moves a project to **Trash**;
Restore returns its drafts, videos and history. It does not erase source files.
Running work must finish before deletion. Closing a project saves its draft.

The app starts in English. Change **App language** to Chinese to update the
interface and newly generated Research explanations. Saved analyses keep their
original language; explicitly generate a new version to change it. Original
speech and visible text remain verbatim. Ideas' **Generation language** remains
independent. Panels adapt to window size; narrower windows use the Projects
toggle and internal scrolling instead of stretching the entire page.

## Models, missing analysis and budget

Visual analysis, Structure synthesis, Ideas, Production and input assistance use
GPT-6.1 Sol. Bounded background research uses GPT-6 Luna. These models do not accept
audio. The owner-approved speech exception uses Whisper (`whisper-1`) for
transcription with segment timestamps. New speech analysis is enabled in v0.7.4;
all other inference keeps the GPT-6 models above. Existing speech, source wording
and compatible caches are retained. The key needs Audio Transcriptions access in
addition to Responses access.

Visuals and visible text are extracted in small batches. If one fails, completed
batches remain usable; **Retry missing analysis** reuses validated cached results.
It creates a new analysis revision rather than overwriting reviewed history.
Structure displays a limitation when its source analysis is incomplete.

**API connection** also shows the shared local USD 3 test budget. It is separate
from OpenAI credit. **Release rejected requests**, when available, removes only
reservations for explicit authentication/permission refusals. Unknown charges
stay reserved, and the ceiling is not increased. If the ledger shows an accounting
pause, this action does not clear that pause. No paid call runs merely by opening
the app, switching languages or reading a saved project.
