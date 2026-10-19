# Recognition startup configuration hotfix — 2026-10-19

- Task: repair the v0.7 classroom launcher's real-recognition failure.
- Environment: Linux Cloud; Python 3.12. Native macOS was not tested.
- Branch: `feat/workspace/structure-agent-redesign`, continuing Draft PR #8.
- Starting commit: `a62811c63afc2e3e2e7e6b4c6002dd9541ed320a`.

## Root cause and change

The local launcher and environment configuration supply `budget_path` as a
`pathlib.Path`. Recognition included that value in its JSON cache-key payload.
After media preparation, serialization raised `TypeError: Object of type
PosixPath is not JSON serializable` before any model request. The workflow
converted the unexpected exception to the generic `generation_failed` message.
Without usable observations, Structure could not start either.

Exclude the accounting file location from recognition cache identity, alongside
the existing exclusions for the API key and cache directory. The shared budget
ledger, reservations, cap and transport enforcement are unchanged. No schema,
saved task, media, or approval migration is needed.

Earlier recognition fixtures constructed `ProviderSettings()` directly, leaving
the ledger path unset, so they missed the deployed configuration. Two new
parameterized cases use `from_env()` and the actual `local_settings()` factory.
They both failed before the fix and pass afterward. They also verify cache reuse
after ledger relocation and invalidation after an output-language change.
A third test uses actual FFmpeg preparation, HTTP recognition, fake providers,
and the Structure source gate with the local launcher's configuration.

## Verification

- `pytest tests/test_providers.py -q`: 34 passed.
- `pytest tests/test_provider_workflow.py tests/test_local_server.py tests/test_structure_provider.py tests/test_budget_guard.py -q`: 31 passed.
- Ruff on the three changed Python files: passed.
- Live OpenAI calls, owner-video analysis quality and native Mac launch: not run.
- No paid calls or model training. No merge or deployment.

The updated classroom archive excludes private reference videos and user data.
Stop the existing server, extract to a new folder, and start the updated launcher.
The default macOS library remains `~/Library/Application Support/Video Anatomy/`.
Reopen the saved task and run video analysis once; then run Structure. Do not
delete the library, replace its budget ledger, or re-upload retained media.

The reproducible defect explains failure under the supplied launcher settings;
the owner's local logs were not available. Any subsequent provider-specific
failure still needs its actual error rather than an assumption about credits.
