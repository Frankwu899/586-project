# Run the workspace demo

This local demo serves the real React UI and persistent FastAPI/SQLite workflow on one port. The demo launcher explicitly disables paid providers, even if an API key exists in the shell. The fictional sample exercises the workflow with deterministic prepared content; it does not demonstrate real recognition or open-ended AI quality.

Prerequisites: Python 3.12 and FFmpeg/ffprobe on PATH. A source checkout additionally needs Node >=22.12 and npm >=10 to build the UI. The downloadable demo bundle includes the built UI, so Node is unnecessary for that bundle. The first launch installs Python packages from the pinned lockfile and requires internet access.

macOS/Linux, from the extracted bundle or repository:

```bash
bash scripts/start-demo.sh
```

Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start-demo.ps1
```

Open **http://127.0.0.1:8000** on the same machine where the command runs. A server inside a remote development container is not automatically available at your desktop's localhost. Use `--port 8001` if port 8000 is occupied. Stop the server with Ctrl+C; saved tasks and drafts remain in `.local-data/demo` for the next launch. Use one server process per data directory.

## Walkthrough

1. Create a task. Open **Reference** and load the explicitly labeled synthetic sample. This supplies a fictional brief and an illustrated reference clip.
2. Run sample analysis, read the visual observations and the complete speech/text tracks, optionally edit and save corrections, then confirm the reviewed analysis.
3. Open **Inputs** to inspect and apply brand, claim permissions/conditions, audience and production resources. Draft autosave does not apply changes to the formal brief.
4. Open **Directions**, explicitly choose English or Chinese, save the language, and generate two sample directions. Read and edit a direction, save it, and explicitly approve that exact version. The sample supports the documented “Make it presenter-free” instruction; arbitrary feedback is retained with an honest unsupported status.
5. Open **Production**, generate the production brief and storyboard, edit text, and save. Export storyboard CSV or open the combined print view and choose **Save as PDF** in your browser's print dialog. Dirty output offers **Save and export** or **Cancel**.
6. Switch tasks, refresh, or stop and restart the server. Reopen the task to continue from the stored work area and drafts. Source deletion removes media playback while keeping labeled historical text and provenance.

Ordinary video uploads remain real inputs. Without configured providers, analysis returns an explicit unavailable error; uploads never silently receive the fictional sample's results. M2 AI assistance is unavailable in this demo, while manual input and editing remain usable.

## Tomorrow's API/sample evaluation

Use the normal development entrypoint described in [README_SETUP.md](README_SETUP.md) when live evaluation is explicitly authorized. Do not use the offline launcher to test credentials. Supply the sample videos, desired brand brief, approved claims and qualifications, available people/locations/materials, target language, and expected outputs. Record real recognition and creative quality separately from offline workflow tests using the [M9 rubric](docs/evaluation/m9-offline-and-live-rubric.md).
