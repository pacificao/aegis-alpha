#!/usr/bin/env bash
set -euo pipefail
canonical_url="${AEGIS_BASE_URL:-https://aegis-alpha.pacificao.com}"
docker compose config --quiet
docker compose build
docker compose up -d --wait
docker compose ps
curl --fail --silent "$canonical_url/health" | grep -q '"trading":"DISABLED"'
if curl --silent --output /dev/null --write-out '%{http_code}' "$canonical_url/api/status" | grep -q '^401$'; then
  echo "Unauthorized API access correctly blocked"
else
  echo "Expected /api/status to return 401 without a session" >&2; exit 1
fi
if ss -ltn | grep -E ':(3000|5432|6379|8000)[[:space:]]'; then
  echo "Internal service port unexpectedly exposed" >&2; exit 1
fi
docker compose run --rm -e PYTHONPATH=/app --entrypoint pytest backend -q /app/tests
docker run --rm -v "$PWD/frontend:/app" -w /app node:22.14-alpine npm test -- --run
