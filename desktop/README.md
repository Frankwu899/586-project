# Video Anatomy for macOS — native packaging source

Status: the Electron shell, authenticated local backend entrypoint and macOS build
pipeline are implemented in source. The current Linux executor cannot build,
sign, notarize or install-test a real Mac DMG. No DMG is claimed by these files.
Use the browser bundle described in `../LOCAL_API.md` until Mac acceptance passes.

## Runtime design

- One bounded Electron window loads the existing built React application.
- Python/FastAPI is frozen into an architecture-specific executable with PyInstaller.
  FFmpeg and ffprobe are separately bundled. End users of a verified native build
  do not need Homebrew, Node or a Python installation.
- The backend binds an OS-selected `127.0.0.1` port. A random per-process token is
  required for UI, API and media requests; the main process adds it only to that
  exact local origin. The renderer never receives the token. Unexpected hosts,
  cross-origin requests, in-app external navigations, popups and permissions are
  blocked. HTTPS source links open in the system browser without the session token.
- The setup window has a narrow isolated preload bridge. API keys move over IPC
  and the backend's inherited stdin pipe, never through process arguments. Optional
  saved keys use Electron safeStorage with macOS Keychain encryption; the encrypted
  blob lives under `Video Anatomy Desktop/credentials`. Session-only mode persists
  no key. Menu **Forget Saved API Key** removes the saved blob.
- The persistent library is `~/Library/Application Support/Video Anatomy/`, shared
  with the browser launcher. Chromium shell state is separate under
  `~/Library/Application Support/Video Anatomy Desktop/`.
- Setup offers a native folder chooser for the old `.local-data/live` library.
  Import copies/verifies into an absent destination, preserves the source, and
  refuses to merge an existing destination. Back up before changing machines.
- Closing the app terminates its backend, with a bounded graceful shutdown. If a
  running model request is interrupted, provider charges may already have occurred.
  Saved job recovery applies on next launch; closing is not a refund mechanism.

## Develop without packaging

On macOS, prepare the repository's Python 3.12 environment, FFmpeg and frontend:

```bash
npm --prefix frontend ci
npm --prefix frontend run build
npm --prefix desktop ci
npm --prefix desktop start
```

The development shell uses the root `.venv/bin/python`. It starts no paid request
automatically. Choose **Open offline** to inspect saved work or the fictional sample.
The shell is not an editor for credentials in the normal app page; its setup
window is local and only exposes the three setup IPC operations.

## Build the native runtime on a Mac

Build on each supported architecture separately. A matching Python 3.12, Node
and Apple command-line tools are build-time prerequisites. Supply a vetted
portable FFmpeg/ffprobe pair for that architecture and its distribution notices.
Do not copy an arbitrary Homebrew executable: unbundled dylibs can make it fail on
another Mac. The build rejects non-system dynamic-library references.

```bash
export VIDEO_ANATOMY_FFMPEG_DIR="/path/to/portable-macos-tools"
export VIDEO_ANATOMY_FFMPEG_NOTICES="/path/to/FFmpeg-distribution-notices.txt"
npm --prefix desktop run build:runtime:mac
npm --prefix desktop run package:mac:unsigned
```

The runtime builder installs pinned app dependencies and PyInstaller 6.16.0,
bundles backend modules, built frontend, data and contracts, and writes a file-hash
manifest. The packaging preflight verifies the manifest, platform, architecture,
media tools and notices. An unsigned development DMG is for explicit local testing;
it is not a signed or notarized release and may be rejected by Gatekeeper.

For normal distribution, use the owner's Developer ID signing configuration and
Apple notarization credentials with electron-builder, then run
`npm --prefix desktop run package:mac`. Do not put those credentials in Git.
Confirm notarization and stapling succeeded; producing a DMG alone does not prove
that. No public publishing occurs (`--publish never`).

## Required Mac acceptance before release

1. Install on a clean supported Mac without Python, FFmpeg or Homebrew.
2. Open offline; verify playback, seeking, upload, saved drafts, PDF/CSV export,
   locale input and the app menu. Confirm remote pages cannot receive the token.
3. Enter a test project key in session-only mode; confirm it does not appear in
   commands, logs, HTML, local API responses or retained project files.
4. Verify remembered-key use and removal with Keychain, including encryption
   unavailable/locked states. Do not fall back to plain text.
5. Import an old library containing edited tasks, media and paid results. Compare
   receipt hashes and project state. Verify existing-destination refusal and that
   the original remains usable. Upgrade the .app and confirm the same library opens.
6. Close during an operation; verify process shutdown and retained-state recovery.
7. Check arm64/x86_64 builds separately, signing, Gatekeeper and notarization on
   a machine distinct from the build host. Record the FFmpeg build license/source
   obligations and include all required notices before distributing binaries.

Linux checks cover Python behavior, JS syntax/helper tests and package contents.
They do not establish the Mac behaviors above. The native wrapper must not be
presented as a tested end-user installer until this checklist has real results.
