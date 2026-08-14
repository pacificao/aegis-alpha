#!/usr/bin/env bash
set -euo pipefail
docker compose config --quiet
docker compose build
docker compose up -d --wait
docker compose ps
curl --fail --silent http://127.0.0.1/health | grep -q '"trading":"DISABLED"'
if curl --silent --output /dev/null --write-out '%{http_code}' http://127.0.0.1/api/status | grep -q '^401$'; then
  echo "Unauthorized API access correctly blocked"
else
  echo "Expected /api/status to return 401 without a session" >&2; exit 1
fi
if ss -ltn | grep -E ':(3000|5432|6379|8000)[[:space:]]'; then
  echo "Internal service port unexpectedly exposed" >&2; exit 1
fi
docker compose run --rm backend pytest -q
docker compose run --rm frontend npm test -- --run

