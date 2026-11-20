# Production Deployment

This guide describes the production Compose stack. It is separate from the development stack in `docker-compose.yml`; do not use the development Compose file as a public production deployment.

## Before deployment

1. Provision a Linux host with Docker Engine and the Docker Compose plugin.
2. Configure DNS for the application and API hostnames.
3. Put a TLS reverse proxy (for example, Caddy, Nginx, or a managed load balancer) in front of the host. The app and API origins must use HTTPS.
4. Copy `.env.production.example` to `.env.production`. Generate independent random secrets and fill every `CHANGE_ME` field. Do not commit the real file.
5. Configure the LLM provider and AssemblyAI credentials. The LLM model name must match the provider key you set.
6. Set `NEXT_PUBLIC_API_URL` to the public HTTPS API origin and `CORS_ORIGINS` to the exact frontend origin.
7. Confirm the hosting provider has persistent disk capacity for PostgreSQL, Redis, uploads, and rendered clips.

Generate independent secrets on the host:

```sh
openssl rand -hex 32
```

Run that command separately for `BETTER_AUTH_SECRET`, `BACKEND_AUTH_SECRET`, `APP_SETTINGS_ENCRYPTION_KEY`, `POSTGRES_PASSWORD`, and `REDIS_PASSWORD`. Use alphanumeric output for the database password so the connection URL does not require URL-encoding.

## Deploy

Validate Compose interpolation before starting services:

```sh
docker compose --env-file .env.production -f docker-compose.production.yml config --quiet
```

Build and start:

```sh
docker compose --env-file .env.production -f docker-compose.production.yml up -d --build
docker compose --env-file .env.production -f docker-compose.production.yml ps
docker compose --env-file .env.production -f docker-compose.production.yml logs --tail=200
```

The frontend listens on host loopback port 3107 and the backend on host loopback port 8000. Configure the TLS reverse proxy to forward the app hostname to `127.0.0.1:3107` and the API hostname to `127.0.0.1:8000`. PostgreSQL and Redis have no published host ports.

The backend API hostname is required because browser-side media upload flows may call the backend directly. The proxy must preserve request bodies and support long-running uploads; set request-size and timeout limits deliberately rather than relying on small defaults.

## First-deployment verification

- Confirm frontend and backend health checks are healthy.
- Create a test account, sign in, and sign out.
- Submit a video that you own or are authorized to process.
- Confirm the worker consumes the job, the task progresses, and a clip is rendered.
- Verify clip playback/download after restarting the application containers.
- Verify a database backup can be restored into a separate test database.
- Verify invalid auth signatures and revoked API keys are rejected.
- Confirm the API, database, and Redis are not directly exposed to the public internet.
- Confirm logs do not contain API keys, cookies, authorization headers, or uploaded media contents.

## Data protection and operations

The Compose file creates persistent Docker volumes, but volumes are not backups. Schedule encrypted PostgreSQL backups and test restores. Define retention and deletion policies for source videos, uploads, and generated clips. Monitor disk usage, queue depth, failed tasks, API latency, and worker restarts. Configure host-level firewalling, unattended security updates, TLS renewal, and off-host backups.

Do not run `docker compose down -v` in production: it deletes persistent volumes. Deploy new versions with a database backup first and a documented rollback plan. Database schema changes must be backward-compatible with the previous application version during rollout.

## Important limitations

This Compose stack is a production-oriented deployment baseline, not proof that the service is production-ready. A release still requires successful image builds, unit/integration/E2E tests, dependency and image vulnerability scans, security review, load testing, backup-restore testing, and a live HTTPS deployment. It does not provision a domain, reverse proxy, cloud object storage, email provider, monitoring service, or paid API credentials.

SupoClip's imported source is licensed under AGPL-3.0. If Movie Shorts is distributed or offered as a network service with modifications, review the license obligations and preserve required notices/source availability. This is an engineering note, not legal advice.
