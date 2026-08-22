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
| `ATT_BOOTSTRAP_ADMIN_PASSWORD` | **yes** | Strong unique value; production refuses placeholders like `changeme` |
| `ATT_SITE_ADDRESS` | yes | e.g. `example.com` or `localhost` |
| `ATT_CORS_ORIGINS` | yes | Public site origin, e.g. `https://example.com` — **never `*`** |
| `ATT_ACME_EMAIL` | for public TLS | Let’s Encrypt contact |
| `ATT_ALLOW_YOUTUBE` | default `false` | Keep off for public hosts |
| `ATT_MAX_UPLOAD_MB` | default `50` | Upload hard cap |
| `ATT_S3_*` | optional | MinIO credentials if not using defaults |

### Public anonymous demo mode

Set `ATT_DEMO_MODE=true` with `ATT_REQUIRE_AUTH=false` to enable `POST /v1/auth/session`, which issues a per-tab anonymous JWT (distinct `user_id` per visitor) so the SPA can run Isolation/Tab without a login form. Upload and job routes require that session (or a login token); unauthenticated calls return 401. Production still requires a strong `ATT_SECRET_KEY` and an exact public frontend origin in `ATT_CORS_ORIGINS` (**never `*`**). Recommended caps for a public demo: `ATT_MAX_UPLOAD_MB=25`, `ATT_DEFAULT_ISOLATE_QUALITY=fast`, `ATT_ALLOW_YOUTUBE=false` (see [`.env.example`](.env.example)). Upload and job routes already rate-limit by `user_id` via `_rate_key`, so each anonymous session is limited independently. Anonymous users, jobs, and uploads accumulate in Postgres and object storage over time and should be pruned periodically by the operator (documented operational follow-up; no automated cleanup in this stack yet).

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

### Split hosting: static frontend + hosted API

Deploy `web/` to Vercel or Netlify (use that directory as the project root; see `web/vercel.json` / `web/netlify.toml`) and set `VITE_API_BASE_URL` to the public HTTPS origin of the existing `docker-compose.yml` API stack on a Docker-capable host. On the API side, set `ATT_CORS_ORIGINS` to the exact frontend origin(s) — production and any preview URLs — never `*`. The API host must expose HTTPS and WSS; an `https://` SPA will block mixed-content `ws://` WebSockets. You can keep the compose `caddy` service in front of the API for TLS, or terminate TLS at the host/provider instead — both are valid.

### Oracle Always Free (experimental)

[Oracle Cloud Free Tier](https://www.oracle.com/cloud/free/) Always Free Ampere is currently **2 OCPU / 12 GB RAM** (ARM). That is **below** the ≥16–32 GB guidance above for concurrent/full-song Demucs. Use this only for a short-clip public demo.

**Memory spike** (arm64, `htdemucs_6s` + `quality=fast`, synthetic tones): see [docs/oracle-free-memory-spike.md](docs/oracle-free-memory-spike.md). Peak RSS was ~2 GiB for ≤120 s in that run — **PASS** for short clips, not a promise for dense mixes or many parallel jobs.

**Lite compose** (one API container, SQLite, local disk, no Postgres/Redis/MinIO/worker):

```bash
cp .env.lite.example .env
# set ATT_SECRET_KEY, ATT_SITE_ADDRESS, ATT_CORS_ORIGINS
docker compose -f docker-compose.lite.yml up -d --build
```

Lite defaults: `ATT_DEMO_MODE=true`, `ATT_REQUIRE_AUTH=false`, `ATT_MAX_JOB_DURATION_SEC=90`, `ATT_SINGLE_FLIGHT_JOBS=true` (second job gets **503** until the first finishes), `ATT_MAX_UPLOAD_MB=25`. Models are not prewarmed (first isolate is slower).

**VM setup:** shape `VM.Standard.A1.Flex` with 2 OCPU / 12 GB in your home region; open 80/443; use Caddy in the lite compose for TLS (or terminate TLS at a load balancer). Add **4–8 GB swap** as a safety net. Build/run the Docker image on **linux/arm64** (Oracle Ampere).

**Not recommended** for “as many concurrent isolate testers as you want.” For that, use a ~16–24 GB x86 VPS (Hetzner/Contabo, roughly ¥2,500–¥3,500/month) with the full [docker-compose.yml](docker-compose.yml).
