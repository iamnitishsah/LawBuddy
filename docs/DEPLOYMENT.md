# Deployment

```
browser ──► Vercel (frontend; rewrites /api/*) ──► AWS EC2 :8000 (API container)
GitHub push to main ──► Actions: tests · frontend build · image → GHCR ──SSH──► EC2: pull, restart, health check
```

- **Frontend:** Vercel, deployed by Vercel's Git integration. `frontend/vercel.json` rewrites `/api/*` to the API, so
  the browser only talks to the Vercel origin (no CORS setup needed).
- **API:** one EC2 instance (t3.micro: 2 vCPU burst, 1 GB RAM + 2 GB swap) running the LawBuddy image with Docker
  Compose. The image is built by GitHub Actions and pulled from GitHub Container Registry, so nothing is built on the
  small instance.
- **Secrets:** the API keys live only on the server, in `/opt/lawbuddy/lawbuddy.env` (mode 600). GitHub holds
  only the SSH key for deploying.

## Files

| File | Where it runs | Does |
|---|---|---|
| `.github/workflows/ci-cd.yml` | GitHub Actions | tests and frontend build on every push and PR; on `main`: image to GHCR, deploy, public health check |
| `deploy/setup-ec2.sh` | EC2, once | Docker + compose plugin, 2 GB swap, `/opt/lawbuddy` |
| `deploy/docker-compose.yml` | EC2 | the API container on port 8000, logs to `/opt/lawbuddy/logs`, 700 MB memory limit, log rotation |
| `deploy/deploy.sh` | EC2, each deploy | switch to the new image, health check, roll back to the previous image if unhealthy |
| `deploy/lawbuddy.env.example` | EC2 | template for the server's secrets and settings |
| `Dockerfile` | GitHub Actions | the API image (Python 3.12 slim, non-root, uvicorn reading the client IP from `X-Forwarded-For`) |

## One-time setup

**1. AWS**
- Allocate an **Elastic IP** and associate it with the instance, so the address survives a stop/start
  (`frontend/vercel.json` contains it).
- Security group inbound: **22** from your IP, **8000** for the API.

**2. The instance** (replace `ubuntu` with `ec2-user` on Amazon Linux)
```bash
scp -i key.pem deploy/setup-ec2.sh deploy/lawbuddy.env.example ubuntu@<ip>:~
ssh -i key.pem ubuntu@<ip> 'bash setup-ec2.sh'
ssh -i key.pem ubuntu@<ip>
nano /opt/lawbuddy/lawbuddy.env      # GROQ_API_KEY, NVIDIA_API_KEY, (GEMINI_API_KEY), CORS_ORIGINS
exit                                 # log in again later so the docker group applies
```

**3. GitHub** (repository Settings → Secrets and variables → Actions → New repository secret)

| Secret | Value |
|---|---|
| `EC2_HOST` | the Elastic IP |
| `EC2_USER` | `ubuntu` or `ec2-user` |
| `EC2_SSH_KEY` | the whole contents of the `.pem` file |
| `PUBLIC_URL` | `http://<elastic-ip>:8000` (optional; checked after each deploy) |

Also Settings → Environments → create **`production`** (the deploy job uses it; you can add required reviewers to
approve each deploy). The first push creates the GHCR package `lawbuddy`; the deploy pulls it with the job's own
short-lived token, so the package can stay private.

**4. Vercel**
- `frontend/vercel.json`: `"destination": "http://<elastic-ip>:8000/:path*"` (currently 16.179.200.29).
- Project → Settings → Environment Variables: **`VITE_API_BASE_URL=/api`**, so the app calls through the rewrite.
  Leave `VITE_API_KEY` empty unless the server sets `LAWBUDDY_API_KEY`. Redeploy after changing variables.

**5. Deploy:** push to `main`. Actions runs tests → image → deploy → health check.

## Every deploy

1. `backend-tests` (209 offline tests, KB validation) and `frontend` (lint, build) run on every push and PR.
2. On `main`: the image is built with layer caching and pushed as `ghcr.io/<owner>/lawbuddy:<sha>` and `:latest`.
3. The deploy job copies `docker-compose.yml` and `deploy.sh`, logs the server in to GHCR with the job's token, runs
   `deploy.sh`, and logs out.
4. `deploy.sh` waits up to 60 s for `/health`; if the new image is not healthy it shows the last logs and **switches back
   to the previous image**, and the job fails.
5. The job checks `PUBLIC_URL/health` from the internet.

Manual deploy of a specific version: Actions → CI/CD → Run workflow, or on the server
`/opt/lawbuddy/deploy.sh ghcr.io/<owner>/lawbuddy:<sha>` (after `docker login ghcr.io`).

## Operating it

```bash
cd /opt/lawbuddy
docker compose ps                         # is the API up?
docker compose logs -f --tail 50 api      # API logs
curl -s localhost:8000/health             # health
tail -f logs/chat.jsonl                   # turn log (no keys are logged)
nano lawbuddy.env && docker compose up -d # change a key or setting
```

## Limits of this setup

- **One instance, in-memory sessions:** a restart (including every deploy) forgets open conversations. Several
  instances would need a shared session store (Redis) and a load balancer.
- **Rate limit per client IP** relies on `X-Forwarded-For` from Vercel's proxy; a caller who reaches port 8000
  directly can set that header. Fine as a courtesy limit for a prototype, not as abuse protection.
- **Vercel's proxy** has its own limits on request duration and body size; LawBuddy turns take ~5-40 s and a voice
  note under two minutes is about 1-2 MB, but a very slow model (Gemini on the free tier, 73-101 s) may hit them.
- **t3.micro CPU credits:** sustained load drains the burst credits; the work is mostly waiting on external APIs, so
  typical use stays well within them.
