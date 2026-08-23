#!/usr/bin/env bash
set -euo pipefail

[[ ${EUID} -eq 0 ]] || { echo "Run as root on the brokerage server." >&2; exit 1; }
readonly SOURCE="/opt/aegis-broker/source/scripts/update-broker-gateway.sh"
readonly TARGET="/usr/local/sbin/aegis-update-broker-gateway"
readonly CRON_FILE="/etc/cron.d/aegis-broker-update"

[[ -f "${SOURCE}" ]] || { echo "Updater missing from protected main." >&2; exit 1; }
bash -n "${SOURCE}"
install -o root -g root -m 0750 "${SOURCE}" "${TARGET}"
cat > "${CRON_FILE}" <<'EOF'
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
MAILTO=""
*/5 * * * * root /usr/local/sbin/aegis-update-broker-gateway >>/var/log/aegis-broker-update.log 2>&1
EOF
chown root:root "${CRON_FILE}"
chmod 0644 "${CRON_FILE}"
systemctl enable --now cron
"${TARGET}"
echo "Broker updater installed; protected main is checked every five minutes."
