#!/usr/bin/env bash
set -euo pipefail

readonly REPO_DIR="/opt/aegis-broker/source"
readonly COMPOSE_FILE="/opt/aegis-broker/compose.yml"
readonly STATE_DIR="/var/lib/aegis-broker/deployment"
readonly REVISION_FILE="${STATE_DIR}/deployed-revision"
readonly HEALTH_URL="https://brokerage.aegis-alpha.pacificao.com/health"
readonly LOCK_FILE="/run/lock/aegis-broker-update.lock"

log() { logger -t aegis-broker-update -- "$*"; printf '%s\n' "$*"; }
fail() { log "FAILED: $*"; exit 1; }

[[ ${EUID} -eq 0 ]] || fail "must run as root"
[[ -d "${REPO_DIR}/.git" ]] || fail "repository missing"
[[ -f "${COMPOSE_FILE}" ]] || fail "compose file missing"
[[ "$(realpath -e "${REPO_DIR}")" == "${REPO_DIR}" ]] || fail "unexpected repository path"

exec 9>"${LOCK_FILE}"
flock -n 9 || exit 0
install -d -o root -g root -m 0700 "${STATE_DIR}"
[[ -z "$(git -C "${REPO_DIR}" status --porcelain)" ]] || fail "dirty repository; operator review required"

git -C "${REPO_DIR}" fetch --prune origin main
current="$(git -C "${REPO_DIR}" rev-parse HEAD)"
target="$(git -C "${REPO_DIR}" rev-parse origin/main)"
[[ "${target}" =~ ^[0-9a-f]{40}$ ]] || fail "invalid target revision"

if [[ "${current}" == "${target}" ]]; then
  printf '%s\n' "${current}" > "${REVISION_FILE}"
  exit 0
fi

git -C "${REPO_DIR}" merge-base --is-ancestor "${current}" "${target}" || fail "main is not a fast-forward; operator review required"
old="${current}"
log "deploying ${target} over ${old}"
git -C "${REPO_DIR}" switch main
git -C "${REPO_DIR}" merge --ff-only "${target}"

rollback() {
  log "health check failed; rolling back to ${old}"
  git -C "${REPO_DIR}" reset --hard "${old}"
  docker compose -f "${COMPOSE_FILE}" up -d --build --wait broker-gateway
  curl --fail --silent --show-error --max-time 15 "${HEALTH_URL}" >/dev/null
  fail "deployment rolled back to ${old}"
}

docker compose -f "${COMPOSE_FILE}" up -d --build --wait broker-gateway || rollback
health="$(curl --fail --silent --show-error --max-time 15 "${HEALTH_URL}")" || rollback
grep -q '"status":"ok"' <<<"${health}" || rollback
printf '%s\n' "${target}" > "${REVISION_FILE}"
log "deployed ${target}; health verified"
