#!/usr/bin/env bash
# Runs on the EC2 instance (called by the CI/CD workflow over SSH): switch the API to a new image, check that it is
# healthy, and roll back to the previous image if it is not.
#
#   /opt/lawbuddy/deploy.sh ghcr.io/<owner>/lawbuddy:<git-sha>
set -euo pipefail

IMAGE="${1:?usage: deploy.sh <image>}"
DIR=/opt/lawbuddy
cd "$DIR"

# Compose variables (not secrets): API_IMAGE and DOMAIN live in .env; app secrets live in lawbuddy.env.
touch .env
previous="$(grep -E '^API_IMAGE=' .env | cut -d= -f2- || true)"
set_var() { if grep -qE "^$1=" .env; then sed -i "s|^$1=.*|$1=$2|" .env; else echo "$1=$2" >> .env; fi; }

echo "deploying $IMAGE (previous: ${previous:-none})"
set_var API_IMAGE "$IMAGE"
docker compose pull api
docker compose up -d --remove-orphans

healthy=""
for _ in $(seq 1 30); do
  if curl -fsS --max-time 4 http://127.0.0.1:8000/health > /dev/null; then healthy=1; break; fi
  sleep 2
done

if [ -z "$healthy" ]; then
  echo "!! the new image did not become healthy; last logs:"
  docker compose logs --tail 40 api || true
  if [ -n "$previous" ]; then
    echo "rolling back to $previous"
    set_var API_IMAGE "$previous"
    docker compose up -d api
  fi
  exit 1
fi

curl -fsS http://127.0.0.1:8000/health; echo
# Keep the disk of a small instance clean: images not used for 3 days.
docker image prune -af --filter "until=72h" > /dev/null || true
echo "deployed $IMAGE"
