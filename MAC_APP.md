# Video Anatomy 1.8.1 for your Mac

This is the shared testing candidate. Read **RELEASE NOTES.md** for the testing
checklist and record the version/commit shown in About with every bug report.

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
5. Open or create a project. To reopen after closing the
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

No case video is preloaded. Import the videos and documents you choose. Projects
and media remain in `~/Library/Application Support/Video Anatomy/`, shared with
v0.7. Back up that entire folder with the old app stopped before upgrading.
Version 1.8 imports legacy work once into independent project folders while
retaining the old task library. Each new project's originals, conversations,
briefs, corrected evidence and output history live under `projects/<id>/`.
The historical `provider-budget.sqlite3` ledger is preserved but no longer
limits client requests. No ledger reset or key replacement is needed. Launcher/runtime logs are under
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

Use **New project** on the project-card dashboard. Project actions include
Rename, Duplicate and Move to Trash. Restore from Trash retains saved work;
duplicates own independent local files. **All projects** returns to the dashboard
and flushes pending drafts. Running work must finish before deletion.

The English 1.8 workspace has Overview, Resources, Discover, Analysis, Content
plan and Production. Describe the assignment in Overview, review the suggested
brief and explicitly apply confirmed facts. Choose local references in Resources
and use **Analyze selected**. Content can belong to a series or stand alone;
approve a direction before producing its four-document production pack.

Discovery is **Reserved — awaiting Frank’s specification.** The previous bilingual
workspace remains available by adding `?legacy=1` to the local address. Its
post-import edits do not synchronize into the independent 1.8 project.

## Models, missing analysis and usage

Visual analysis, Structure synthesis, Ideas, Production, input assistance and
bounded background research all use GPT-6.1 Sol (`gpt-6.1-sol`). The local app
pins this baseline even when older shell model settings are present. GPT-6 does not accept
audio. The owner-approved speech exception uses Whisper (`whisper-1`) for
transcription with segment timestamps. Speech analysis is enabled;
all other inference keeps the Sol baseline above. Existing speech, source wording
and compatible caches are retained. The key needs Audio Transcriptions access in
addition to Responses access.

Visuals and visible text are extracted in small batches. Completed results remain
usable after partial failure. **Retry recognition** retries one resource without
changing the selected references; **Rebuild media preview** handles local playback
preparation separately. Recognition preserves user corrections and reports
incomplete evidence. Clear cache retains originals and corrected evidence.

**API connection** shows **API usage** and **No client-side spending cap** in
the local launcher. The USD 3 allowance applies only to separately run Cloud experiments.
Local generation does not reserve experiment funds, require budget token
prechecks, or stop because of an old accounting pause or unresolved reservation.
Recorded estimates are informational and may be incomplete; they are not an
invoice or your OpenAI account balance. OpenAI's own billing, rate limits and
permissions still apply. No paid call runs merely by opening the app, switching
languages or reading a saved project. After upgrading, retry a failed operation
explicitly; the app does not automatically repeat previously interrupted calls.
