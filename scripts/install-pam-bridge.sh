#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
  echo "Run this reviewed installer with sudo." >&2
  exit 1
fi

repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
[[ -f "${repo_root}/infra/auth/aegis_pam_bridge.py" ]] || { echo "Bridge source not found." >&2; exit 1; }

install -d -o root -g root -m 0755 /usr/local/lib/aegis-alpha
install -o root -g root -m 0755 "${repo_root}/infra/auth/aegis_pam_bridge.py" /usr/local/lib/aegis-alpha/aegis_pam_bridge.py
install -o root -g root -m 0644 "${repo_root}/infra/auth/aegis-alpha.pam" /etc/pam.d/aegis-alpha
install -o root -g root -m 0644 "${repo_root}/infra/auth/aegis-auth-bridge.service" /etc/systemd/system/aegis-auth-bridge.service
systemctl daemon-reload
systemctl enable --now aegis-auth-bridge.service
systemctl --no-pager --full status aegis-auth-bridge.service

test -S /run/aegis-auth/pam.sock
socket_mode=$(stat -c '%a:%u:%g' /run/aegis-auth/pam.sock)
[[ "${socket_mode}" == "660:0:101" ]] || { echo "Unexpected socket mode/owner: ${socket_mode}" >&2; exit 1; }
echo "Aegis PAM bridge installed; socket is ready."
