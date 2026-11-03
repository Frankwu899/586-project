# Shared team server

For a guided setup without managing your own server, start with
[RENDER_SETUP.md](RENDER_SETUP.md) and its prepared deployment link.

This deployment serves the React application and FastAPI backend at one HTTPS
address. The owner configures one OpenAI key in the hosting service's secret
settings. Teammates sign in with a separate workspace username/password; they do
not supply an OpenAI key. The API connection button and dialog are absent in
shared mode, and credential editing/checking, local runtime details and shutdown
routes are blocked on the server.

This is one trusted team's workspace: everyone with the team password can view,
edit and delete its projects, use its generation quota, and change its default
language. It is not a public service with isolated customer accounts. Existing
task versions and review/approval gates still apply to concurrent edits.

## Model policy

| Capability | Shared-server model |
|---|---|
| Timeline visual analysis | `gpt-6.1-sol` |
| Structure analysis and its web research | `gpt-6.1-sol` |
| Brand/input assistance | `gpt-6.1-sol` |
| Ideas, refinement, production brief and storyboard | `gpt-6.1-sol` |
| Timestamped transcription | `whisper-1` |

Shared mode pins these choices even if older per-capability model/provider
environment variables exist. Local desktop launchers keep their existing
configuration behavior. The separate speech adapter remains the approved
exception. The owner selected Sol as baseline; Andrea's PR #14 is a preliminary
offline report, not a completed live quality/cost comparison. Startup makes no
provider calls and does not prove that the owner's account can use the models.
Provider failures remain failures; there is no fallback to another model.

## Hosting requirements

- Docker-capable host with HTTPS ingress and a persistent disk mounted at `/data`.
- Exactly one replica and one Python process. Stop the old container before
  starting its replacement; the entrypoint holds the existing library lock.
  Do not launch this app with multiple Uvicorn workers.
- Persistent disk writable by UID 10001. The default database/media directory
  is `/data/library`; its parent must also be writable for the process lock.
- Ingress must preserve the public `Host` header, allow video uploads and long
  generation requests, and keep the container port private. Direct public
  access to unencrypted port 8000 would expose team credentials.
- Outbound HTTPS access to the provider. Configure hosting request limits and
  the provider project's spending controls for the team's intended usage.

The runtime includes ffmpeg/ffprobe. Back up the entire persistent directory,
including databases, media, provider results and revision history. A source
checkout or Docker image does not contain the owner's existing project data.

## Operator setup

Build from a reviewed checkout:

```sh
docker build -f Dockerfile.shared -t video-anatomy-shared .
```

Configure these values in the host dashboard or secret manager, never in the
frontend, Git, Docker build arguments, image layers or a distributed ZIP:

| Variable | Value |
|---|---|
| `OPENAI_API_KEY` | Owner's project API key; secret |
| `VIDEO_TEAM_PASSWORD` | Separate randomly generated password, at least 32 characters; secret |
| `VIDEO_TEAM_USERNAME` | Team login name; defaults to `team` |
| `VIDEO_PUBLIC_ORIGIN` | Exact HTTPS origin; optional on Render, where the assigned URL is detected automatically |
| `VIDEO_ANATOMY_DATA_DIR` | `/data/library` by default |
| `PORT` | `8000` by default |

Generate the workspace password with a password manager. Share only the team
login with authorized teammates. Changing a secret requires a server restart.
Rotate the team password when someone leaves; this minimal team login has no
individual account revocation or in-app logout. Close the browser session to
clear cached HTTP Basic credentials. Access and brute-force controls belong at
the HTTPS ingress; this application does not implement login rate limiting.

Use public `GET /healthz` as the host's readiness check. It returns only
`{"status":"ok"}` and does not spend API credits. Other application, API and
media routes require authentication. Requests that change state also require
the same-origin `X-Video-Anatomy-Request: 1` header, supplied by the frontend.

The owner-hosted app uses the existing non-blocking usage reporting behavior;
the historical USD 3 Cloud experiment ledger is not its spending cap. Retries
default to zero. No real API request was run as part of this implementation.

## Verification and rollout

```sh
.venv/bin/python -m pytest -q tests/test_shared_server.py
npm --prefix frontend run build
cd frontend
npx playwright test --config playwright.shared.config.ts
```

The browser test uses fake credentials and performs no generation. It verifies
that the key dialog is absent, projects can be created/reopened, language can be
changed, and anonymous clients cannot read project data. Its result must be
reported separately from API tests; a failed browser launch is not a UI pass.

After deployment, verify HTTPS/authentication, disk survival across a restart,
and the absent key controls, then run an explicitly authorized small real API
check with the owner's account. Configuration tests do not establish provider
access, generation quality, transcription quality or cost efficiency.

Render is offered as a prepared setup option. No hosting purchase has been
approved, no real key has been installed, and no public deployment is claimed
by this document. The v0.7.7 professional
generation instruction package remains separate from runtime prompt integration.
