# Production deploy runbook

Single-host stack: **Caddy (TLS) → SPA + FastAPI → Postgres + Redis + MinIO + arq worker**.

Streamlit (`make ui`) is **local demo only** and is not part of this compose file.

## Prerequisites

- Docker + Docker Compose
- Host with **≥16–32 GB RAM** for CPU Demucs (more if concurrent isolate jobs)
- ffmpeg is baked into the API/worker image
- Strong secrets (do not use compose defaults on the public internet)

## Env checklist

Copy [`.env.example`](.env.example) to `.env` and set:

| Variable | Required | Notes |
|----------|----------|--------|
| `ATT_SECRET_KEY` | **yes** | Long random string; required when `ATT_ENV=production` |
| `ATT_BOOTSTRAP_ADMIN_EMAIL` | yes | Only login user (no open signup) |
| `ATT_BOOTSTRAP_ADMIN_PASSWORD` | yes | Change immediately after first login |
| `ATT_SITE_ADDRESS` | yes | e.g. `example.com` or `localhost` |
| `ATT_CORS_ORIGINS` | yes | Public site origin, e.g. `https://example.com` — **never `*`** |
| `ATT_ACME_EMAIL` | for public TLS | Let’s Encrypt contact |
| `ATT_ALLOW_YOUTUBE` | default `false` | Keep off for public hosts |
| `ATT_MAX_UPLOAD_MB` | default `50` | Upload hard cap |
| `ATT_S3_*` | optional | MinIO credentials if not using defaults |

## Bring up

```bash
export ATT_SECRET_KEY="$(openssl rand -hex 32)"
# or put values in .env
docker compose up -d --build
```

- Site: `https://$ATT_SITE_ADDRESS` (Caddy; local uses internal CA — trust prompt in browser)
- API health: `https://$ATT_SITE_ADDRESS/v1/health`
- Login with bootstrap admin, then run Tab PDF or Isolate jobs

## Ops notes

- **Workers:** Demucs/Basic Pitch run in the `worker` service, not the API process.
- **Default isolate quality:** `fast` (safer wall-clock / RAM).
- **YouTube:** disabled by default; enable only behind auth + rate limits if you must.
- **GPU:** optional later; CPU is the documented first production target.
- **Backups:** snapshot Postgres volume `pg_data` and MinIO volume `minio_data` regularly.
- **Cancel / timeout:** `POST /v1/jobs/{id}/cancel`; wall-clock timeouts by quality tier (`ATT_JOB_TIMEOUT_*_SEC`).
- **Prewarm:** API/worker entrypoints run `scripts/prewarm.py` best-effort to pull models.

## Local development (not compose)

```bash
# API (auth optional in development)
export ATT_REQUIRE_AUTH=false
make backend

# SPA
cd web && npm install && npm run dev

# Streamlit demo only
make ui
```
