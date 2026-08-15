#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
  echo "Run this reviewed installer with sudo." >&2
  exit 1
fi

if [[ $# -ne 1 ]] || [[ ! $1 =~ ^[a-z_][a-z0-9_-]*[$]?$ ]] || ! id --user "$1" >/dev/null 2>&1; then
  echo "Usage: sudo $0 <authorized-local-username>" >&2
  exit 1
fi
authorized_user=$1

repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
[[ -f "${repo_root}/infra/auth/aegis_pam_bridge.py" ]] || { echo "Bridge source not found." >&2; exit 1; }

install -d -o root -g root -m 0755 /usr/local/lib/aegis-alpha
install -o root -g root -m 0755 "${repo_root}/infra/auth/aegis_pam_bridge.py" /usr/local/lib/aegis-alpha/aegis_pam_bridge.py
install -o root -g root -m 0644 "${repo_root}/infra/auth/aegis-alpha.pam" /etc/pam.d/aegis-alpha
install -o root -g root -m 0644 "${repo_root}/infra/auth/aegis-auth-bridge.service" /etc/systemd/system/aegis-auth-bridge.service
install -d -o root -g root -m 0750 /etc/aegis
umask 0077
printf 'AEGIS_AUTHORIZED_USER=%s\n' "${authorized_user}" > /etc/aegis/auth-bridge.env
chown root:root /etc/aegis/auth-bridge.env
chmod 0600 /etc/aegis/auth-bridge.env
systemctl daemon-reload
systemctl enable aegis-auth-bridge.service
systemctl restart aegis-auth-bridge.service
systemctl --no-pager --full status aegis-auth-bridge.service

test -S /run/aegis-auth/pam.sock
socket_mode=$(stat -c '%a:%u:%g' /run/aegis-auth/pam.sock)
[[ "${socket_mode}" == "660:0:101" ]] || { echo "Unexpected socket mode/owner: ${socket_mode}" >&2; exit 1; }
echo "Aegis PAM bridge installed for the configured local operator; socket is ready."
