# Video Anatomy: guided Render setup

This setup runs the app for your team using your server-side API key. You do not
need to buy or maintain a physical server. Nothing is deployed or billed just
because this file or its GitHub branch exists.

## Cost to approve

The prepared Blueprint uses one 1 CPU / 2 GB service (`1c-2g`, $25/month) and a
5 GB persistent disk ($0.25/GB/month), approximately **$26.25/month** at the
published rates checked on November 3, 2026. API usage, taxes, bandwidth/build
overages and any optional paid workspace plan are separate. Review Render's
actual checkout total before approving deployment.

The 2 GB size is a starting choice for video processing, not a benchmarked
capacity guarantee. The cheaper 512 MB size is not the prepared default. The
free service cannot attach the disk needed to preserve this app's projects.

Sources: [pricing](https://render.com/pricing),
[compute plans](https://render.com/docs/compute-plans),
[persistent disks](https://render.com/docs/disks).

## What you do once

1. Open [the prepared setup link](https://render.com/deploy?repo=https%3A%2F%2Fgithub.com%2FFrankwu899%2F586-project%2Ftree%2Ffeat%2Fintegration%2Fshared-backend-sol).
2. Create/sign in to your Render account with GitHub. If prompted to install
   Render's GitHub App, grant it access to **586-project**. This repository is
   private, so Render needs your authorization to build it. You can restrict
   access to this repository.
3. Review the proposed service and cost. In Render's `OPENAI_API_KEY` field,
   paste your real provider key. Enter it only on Render; do not send it in
   chat or include it in GitHub files. Render will generate the separate team
   login password for you.
4. Approve deployment only if you accept the displayed charges. Supply billing
   details privately if Render requests them. The first deployment also builds
   the container, which has not yet been built or tested on Render.
5. Once the service says **Live**, open its assigned HTTPS URL. In the browser's
   login prompt, use username `team` and the generated `VIDEO_TEAM_PASSWORD`
   from the service's Environment settings. This is the workspace password,
   not your OpenAI key.

Share the app URL and workspace login privately with your teammates. They use
the app through a browser and do not need your OpenAI key or a Render account.
Everyone with that login shares the team's projects and API allowance.

If the setup link does not find the private repository, authorize the GitHub
App first, then use Render **New → Blueprint**, select `Frankwu899/586-project`,
and select branch `feat/integration/shared-backend-sol`. Keep `render.yaml` as
the Blueprint path. Do not select main for this preview: it does not yet contain
the shared-server changes.

## What the configuration already handles

- Docker builds the frontend and FastAPI backend together, including ffmpeg.
- An attached disk preserves projects, media and results under `/data/library`.
- Container startup initializes disk-directory ownership, then drops to the
  unprivileged application user before starting the web server.
- The application reads Render's assigned URL from `RENDER_EXTERNAL_URL`, so
  you do not need to guess or enter it. `VIDEO_PUBLIC_ORIGIN` can override it
  later if you configure a custom domain.
- The server uses `gpt-6.1-sol` for text, vision and research, and `whisper-1`
  for transcription. End users cannot change the API key through the app.
- Automatic deploys from code pushes are disabled. The prepared deployment
  follows the integration branch; switching to main later is a separate,
  reviewed change after main contains the implementation.

## Before using it for a team session

Share the service URL and deployment status with the integrator, without API
keys or screenshots that reveal secrets. Confirm that sign-in works, projects
survive a service restart, and the API-key dialog is absent. A Live status only
proves startup; it does not prove real model access or successful generation.
A bounded, explicitly authorized real API check is still needed.

The earlier browser suite was blocked by the cloud environment's Chromium
launch permissions. Docker/Render deployment and live provider checks remain
unverified until performed. See [SHARED_SERVER.md](SHARED_SERVER.md) for the
shared-team access model and rollout details.
