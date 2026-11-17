Video Anatomy for your Mac — team testing candidate

START HERE

1. Extract the ZIP completely. Its only two top-level items are this README.txt
   and Video Anatomy.app. Keep the app in a stable folder and open it in Finder.
2. Your Mac needs Python 3.12 and FFmpeg/ffprobe. If they are missing, install
   Homebrew, then run this once in Terminal:

       brew install python@3.12 ffmpeg

   First launch also needs internet access to install the pinned Python
   dependencies in your local cache. The workspace opens in your normal browser
   when it is ready. Node is not needed for the included, prebuilt interface.
3. Check the version and full source commit in Settings against the team's delivery
   message. Include them with every test report. No sample video is preloaded.

This is an unsigned, dependency-assisted Finder launcher for the local browser
workspace. It is not a self-contained Electron installer, a DMG, or a notarized
release. Linux package and runtime checks do not establish Finder, Gatekeeper,
Keychain, or installation behavior on a real Mac. If macOS blocks this downloaded
app, use its per-app Open option in Finder or Privacy & Security. Do not disable
system security checks. Optional document OCR needs Tesseract/Poppler.

UPGRADE FROM 1.8.2 AND KEEP YOUR WORK

Let running requests finish. A closed browser tab does not stop the local server.
Before backing up, stop the previous Terminal launcher with Control+C. For the
previous Finder app, its launcher supports a graceful stop from Terminal:

    "/path/to/previous/Video Anatomy.app/Contents/MacOS/VideoAnatomy" --stop

Replace the example path with the location of your previous app. It verifies the
old session and refuses to stop running work. Do not force-stop a paid request.

With the previous server stopped, copy the entire library folder to a backup:

    ~/Library/Application Support/Video Anatomy/

Keep the original library and the previous app. The new app uses that same
library, preserving projects, originals, conversations, adopted briefs, source
evidence, corrections, previous analyses, output revisions, and export history.
Do not delete a library, retranscribe a source, reset the historical usage ledger,
or replace an API key merely to upgrade or open saved work.

Open the new app, inspect an existing project, then close and reopen the browser
workspace to confirm its saved state. Double-clicking the same app reconnects to
its verified local server. A moved or updated app switches away from an idle old
server; if the old server is busy, let it finish and try again.

For rollback, use the previous app with a separate copy of the pre-upgrade library
backup. Keep the newer library intact; an older app may reject newly saved fields.

API CONNECTION AND KEYS

Existing remembered credentials remain in the macOS login Keychain, separate from
the app and library. Allow Keychain access if macOS asks. When setup is needed,
open API connection, paste the complete OpenAI project secret key, and Save key.
Remember on this Mac stores it in Keychain. Session-only mode stores no key for
the next launch and removes this app's previously remembered credential.

Keys are not included in this ZIP, project databases, browser storage, or logs.
Finish running operations before changing or forgetting a key. Never include a
key or private source contents in a test report.

Check connection requests model metadata without generating content. It does
not prove generation/audio permissions, account balance, or output quality.
For a failure, use the displayed actionable message and optional support details.
HTTP 401 indicates a rejected credential; HTTP 403 concerns access/permissions;
billing or quota problems concern the project or organization owning the key.
For Keychain problems, unlock the login Keychain and allow access, or choose
session-only mode. For network problems, check access to api.openai.com.

WHAT TO TEST

Use the project's Overview, Resources, Discover, Analysis, Content plan, and
Production tabs. Describe the assignment in Overview; review and explicitly apply
a brief draft. Stop interrupts the current conversation attempt without erasing
your saved message or applied brief. Import your own permitted files in Resources,
keep the focused file separate from the references selected for analysis, and
open a source or saved evidence in Source Review. Inspect source-linked insights
in Analysis. Plan a standalone Video or optionally place it in a Series, approve
an exact direction, then open Production on that same Video to edit/save/export
the Storyboard Sheet. Existing production packs remain historical documents.

Discovery remains: Reserved — awaiting Frank’s specification.
The app does not edit/render video, generate video, publish, or provide a hosted
shared-key service. The previous workspace is available with ?legacy=1; edits
there do not synchronize into independent project workspaces.

Use the team's existing test sheet. Record version/source, Mac/browser versions,
browser zoom, steps, expected/actual behavior, and a screenshot when useful. The
release notes and detailed handoff are inside the app at
Contents/Resources/app/docs/releases/ and Contents/Resources/app/docs/handoff/.
Use Finder's Show Package Contents if those technical notes are needed.

MODELS, USAGE, AND LOCAL STORAGE

Visual analysis, Structure, planning, Production, and input assistance retain
gpt-6.1-sol. Timestamped speech retains whisper-1; the key also needs Audio
Transcriptions access. Completed recognition and human corrections survive a
partial failure; retry a failed operation explicitly. Opening saved work does
not automatically repeat interrupted paid requests.

API usage is informational, not an invoice or account balance. The local client
has no client-side spending cap. OpenAI's billing, permissions, and rate limits
still apply. The separate Cloud experiment allowance is not a client quota, and
the historical provider-budget.sqlite3 ledger is preserved without resetting it.
Opening the app or reading a saved project starts no paid inference.

Projects and media stay in ~/Library/Application Support/Video Anatomy/.
Derived runtime/cache files and launcher logs stay in
~/Library/Caches/Video Anatomy/. Do not remove either to resolve an unexplained
failure; preserve your work and share only sanitized support details.
