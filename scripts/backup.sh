#!/usr/bin/env bash
set -euo pipefail
umask 077
backup_dir="${1:-./backups}"
case "$backup_dir" in /|""|.) echo "Refusing unsafe backup directory" >&2; exit 2;; esac
mkdir -p -- "$backup_dir"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
out="$backup_dir/aegis-postgres-$stamp.dump"
docker compose exec -T postgres pg_dump -U "${POSTGRES_USER:-aegis}" -d "${POSTGRES_DB:-aegis}" -Fc > "$out"
test -s "$out"
sha256sum "$out" > "$out.sha256"
printf 'Backup created: %s\n' "$out"
