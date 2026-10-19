# Local connection and Mac launcher recovery — 2026-10-19

- Repository: `Frankwu899/586-project`.
- Branch: `feat/workspace/structure-agent-redesign`, continuing Draft PR #8.
- Starting commit: `6d0f393da501b0c554edefd89e4e0ec4c91a0101`.
- Environment: Linux Cloud, Python 3.12; no native Mac execution.
- Scope: repair credential diagnosis/replacement and repeated local launch.

## Findings and resulting behavior

The screenshot's old `provider_authentication` code covered both OpenAI HTTP 401
and 403. The owner confirmed using the complete creation-time key. The exact
account-side rejection cannot be established from that combined message; no
owner credential or private provider response was available here. This release
does not claim to restore a revoked key or grant account permissions.

Safe provider errors now separate invalid credentials, permissions, model access,
quota, disabled account, region restrictions, timeout and network failures.
Pasted surrounding whitespace is normalized; obvious masked credentials are
rejected without a request. Redirects cannot forward the credential.

API connection is a local-only dialog for checking, replacing and forgetting a
key. Its bounded check reads model metadata without inference, video upload or
budget reservations. A successful check does not establish generation/audio
permissions or account balance. Restricted Models read is an unverified warning,
not an invalid-key diagnosis. Only safe static error details reach the page.

Changing credentials refreshes recognition, creative/production, M2 and
Structure agents together, retaining the exact budget and cache configuration.
Queued/running jobs, direct requests and Structure work prevent connection
changes or managed shutdown. No WorkflowService reinitialization or job replay
is used. Keys are transient password input and server memory; they are never
returned through GET/status or retained in browser storage or task records.

Remember on this Mac uses the native login Keychain API, without subprocess
credential arguments. Session replacement/removal suppresses an older saved key
before deletion, so a locked Keychain still permits temporary use without
resurrecting the old credential after restart. A nonsecret
`credential-preferences.json` stores only the suppression flag. Errors explicitly
distinguish disabled credentials from successful Keychain deletion.

The Finder `.app` launcher embeds source and the built UI, opens the normal
browser, and runs the server independently of Terminal. It reuses verified
running sessions; an OS-selected port avoids unrelated port collisions. Private
startup/discovery control tokens allow graceful idle-only shutdown. Library,
instance and package fingerprint checks prevent attaching to an unrelated server
or mixing a replaced frontend with an old backend. First-launch dependencies
live in a versioned cache, not in the application bundle. Importing the API
factory is lazy and no longer creates an incidental `.local-data` database
inside a read-only/translocated app bundle.

## Changed areas

- `backend/app/providers/auth.py`, `transport.py`: safe diagnostics/preflight.
- `scripts/local_connection.py`, `local_server.py`: local credential APIs,
  activity gates, managed startup identity and shutdown.
- `scripts/mac_keychain.py`, `mac_launcher.py`, `mac_app_bundle.py`: Keychain,
  repeat-open lifecycle and dependency-assisted app packaging.
- `backend/app/api.py`: lazy default ASGI app; factory imports have no writes.
- `frontend/src/ApiConnection.tsx`, its CSS and workspace integration: connection
  modal, direct repair actions, actual error visibility and accurate conflict
  guidance.
- Packaging/setup documentation and focused tests. No task schema change.

## Verification

| Check | Observed result |
| --- | --- |
| `pytest tests -q` | 644 passed; one existing Starlette/httpx deprecation warning |
| `ruff check backend scripts tests` | Passed |
| Frontend typecheck, lint, unit tests, production build | Passed; seven unit-test files |
| Connection Playwright scenarios | Five passed, including key rejection/replacement, no browser persistence, stored-key reuse and missing-route compatibility |
| Existing affected Structure browser scenarios | Two passed |
| Launcher tests within backend suite | 25 passed, including actual localhost subprocess start/reopen/stop/restart and retained task |
| Local connection tests within backend suite | 36 passed, including concurrent request gates, all provider instances, ledger preservation, Keychain failure and preference-write failure |
| Extracted final app archive | Manifest hashes, plist, executable mode and shell syntax passed; no private video/database/key files |
| Extracted backend and built UI | Started offline with empty library; connection dialog opened/reopened; no database inside app; graceful shutdown passed |
| Native Finder, Gatekeeper, Keychain, DMG signing/notarization | Not run on Linux |
| Owner-key connection and actual video model analysis | Not run; no project key/OpenAI network available in Cloud |

The archive is `video-anatomy-v0.7.2-macos-app.zip`. It is a dependency-assisted,
unsigned Finder launcher using installed Python 3.12 and FFmpeg, not a
self-contained Electron runtime or a DMG. All delivery text is English. No
owner case video is preloaded. The macOS library and shared budget ledger remain
outside the app and are not reset. No paid calls, training, deployment or main
merge occurred.

## Local acceptance

Stop the old Terminal server once, open the new `.app`, and use API connection
to check/save the complete key with Remember on this Mac. A 401 requires an
active replacement credential; a 403 requires investigating the displayed
project/model/endpoint permission issue. The source videos do not need to be
uploaded again. Verify one analysis, then Structure, and closing/reopening the
browser/app with the saved Keychain credential. See `MAC_APP.md` for Mac-specific
startup and error recovery.
