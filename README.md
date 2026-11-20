# Movie Shorts

Movie Shorts is an AI-assisted video clipping application. It turns video files and supported YouTube URLs into short-form clips with transcription, segment selection, vertical reframing, captions, and export tools.

Movie Shorts is a customized derivative of [SupoClip](https://github.com/FujiwaraChoki/supoclip). It retains the upstream project's AGPL-3.0 licensing; see [LICENSE](LICENSE) and the attribution section below.

## What it does

- Accepts a video file or supported YouTube URL, including standard watch, Shorts, embed, and live URLs.
- Transcribes video and identifies candidate clip segments.
- Creates short-form clips with vertical or alternative framing presets.
- Adds editable captions, font choices, and cleanup options.
- Queues video processing in a background worker and tracks task progress.
- Includes unofficial caption starting presets for Kai Cenat, CarryMinati, and IShowSpeed. These presets only set initial caption styling; they are not affiliated with or endorsed by the creators.

**Content rights:** Only submit videos you own or are authorized by the rights holder to download, process, edit, and publish. The app requires an explicit confirmation in the UI and enforces that confirmation again at the task API.

## Architecture

| Component | Technology | Purpose |
| --- | --- | --- |
| Frontend | Next.js, React, TypeScript | App UI, authentication, task dashboard |
| Backend | FastAPI, Python | Uploads, task API, media processing |
| Worker | ARQ, Redis | Background video jobs |
| Database | PostgreSQL | Accounts, tasks, application data |
| AI services | AssemblyAI and a configured LLM provider | Transcription and clip analysis |

## Development quick start

### Requirements

- Docker Engine and Docker Compose.
- An AssemblyAI API key for transcription.
- An API key for one supported LLM provider, or a configured local Ollama instance.

### Start the development stack

From the repository root:

```bash
cp .env.example .env
```

Set `ASSEMBLY_AI_API_KEY`, choose an `LLM` provider, and set the matching provider key in `.env`. Then run:

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f
```

Open the application at **http://localhost:3107**. The backend health endpoint is **http://localhost:8000/health**. PostgreSQL and Redis are internal services in the Compose network.

### Frontend development without Docker

```bash
cd frontend
corepack enable
corepack prepare pnpm@10.27.0 --activate
pnpm install --frozen-lockfile
pnpm run dev
```

The frontend requires a running backend and PostgreSQL/Redis stack for the full application workflow.

## Production deployment

A separate production Compose file is provided. It binds the app and API to host loopback addresses, does not publish PostgreSQL or Redis ports, and expects real secrets and external HTTPS reverse-proxy configuration.

1. Copy `.env.production.example` to `.env.production`.
2. Generate independent production secrets and fill all required API credentials.
3. Configure public HTTPS app/API URLs and an exact frontend origin in `CORS_ORIGINS`.
4. Validate and start the stack:

```bash
docker compose --env-file .env.production -f docker-compose.production.yml config --quiet
docker compose --env-file .env.production -f docker-compose.production.yml up -d --build
docker compose --env-file .env.production -f docker-compose.production.yml ps
```

Read [docs/production-deployment.md](docs/production-deployment.md) before exposing the application publicly. The production Compose file is a deployment baseline, not a claim that a live deployment, load test, security audit, or backup restore has already been completed.

## Tests

The repository uses pytest for the backend, Vitest for frontend unit tests, and Playwright for browser smoke tests. CI also builds the frontend for production and validates the production Compose configuration.

```bash
# Backend
cd backend
uv sync --all-groups
.venv/bin/pytest

# Frontend unit tests
cd ../frontend
corepack enable
corepack prepare pnpm@10.27.0 --activate
pnpm install --frozen-lockfile
pnpm run test:coverage

# Playwright browser tests (after starting the required services)
pnpm run test:e2e

# Production frontend build
pnpm run build
```

Backend tests require PostgreSQL and Redis. See [docs/](docs/README.md) for setup, configuration, architecture, API, and troubleshooting documentation.

## Upstream attribution and license

Movie Shorts is derived from [FujiwaraChoki/SupoClip](https://github.com/FujiwaraChoki/supoclip). Preserve upstream attribution and all AGPL-3.0 notices. If you modify and distribute this software or make it available as a network service, review and comply with the applicable AGPL-3.0 source-sharing requirements.

See [LICENSE](LICENSE) for the license text and [CONTRIBUTING.md](CONTRIBUTING.md) for contribution terms.
