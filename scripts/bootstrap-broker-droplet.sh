#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
  echo "Run as root from the DigitalOcean browser console." >&2
  exit 1
fi

BROKER_HOST="brokerage.aegis-alpha.pacificao.com"
AEGIS_UI="https://aegis-alpha.pacificao.com"
AEGIS_VPC_IP="10.124.0.3"
INSTALL_DIR="/opt/aegis-broker"
CONFIG_DIR="/etc/aegis-broker"
DATA_DIR="/var/lib/aegis-broker"

apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y ca-certificates certbot curl docker.io docker-buildx docker-compose-v2 git nginx ufw
systemctl enable --now docker

id nathan >/dev/null 2>&1 || adduser --disabled-password --gecos "" nathan
usermod -aG sudo nathan

install -d -m 0755 "${INSTALL_DIR}"
if [[ ! -d "${INSTALL_DIR}/source/.git" ]]; then
  git clone --depth 1 --branch main https://github.com/pacificao/aegis-alpha.git "${INSTALL_DIR}/source"
else
  git -C "${INSTALL_DIR}/source" switch main
  git -C "${INSTALL_DIR}/source" pull --ff-only origin main
fi

install -d -o root -g root -m 0700 "${CONFIG_DIR}"
install -d -o 10001 -g 10001 -m 0700 "${DATA_DIR}"
if [[ ! -f "${CONFIG_DIR}/broker-gateway.key" ]]; then
  openssl rand -base64 32 | tr '+/' '-_' > "${CONFIG_DIR}/broker-gateway.key"
fi
chown root:10001 "${CONFIG_DIR}/broker-gateway.key"
chmod 0440 "${CONFIG_DIR}/broker-gateway.key"
if [[ ! -f "${CONFIG_DIR}/shared-secret" ]]; then
  openssl rand -hex 48 > "${CONFIG_DIR}/shared-secret"
fi
chmod 0600 "${CONFIG_DIR}/shared-secret"

SHARED_SECRET="$(<"${CONFIG_DIR}/shared-secret")"
cat > "${CONFIG_DIR}/gateway.env" <<EOF
AEGIS_UI_URL=${AEGIS_UI}
OAUTH_CALLBACK_BASE_URL=https://${BROKER_HOST}
OAUTH_REDIRECT_URI=http://127.0.0.1:8765/callback
BROKER_AUTHORIZATION_ENABLED=true
BROKER_EXECUTION_ENABLED=false
BROKER_GATEWAY_SHARED_SECRET=${SHARED_SECRET}
BROKER_GATEWAY_DATA_DIR=/var/lib/aegis-broker
BROKER_GATEWAY_KEY_FILE=/run/secrets/broker_key
EOF
chmod 0600 "${CONFIG_DIR}/gateway.env"

cat > "${INSTALL_DIR}/compose.yml" <<EOF
services:
  broker-gateway:
    build: ${INSTALL_DIR}/source/broker-gateway
    env_file: ${CONFIG_DIR}/gateway.env
    ports: ["127.0.0.1:8100:8100"]
    volumes:
      - ${DATA_DIR}:/var/lib/aegis-broker
      - ${CONFIG_DIR}/broker-gateway.key:/run/secrets/broker_key:ro
    read_only: true
    tmpfs: [/tmp]
    security_opt: [no-new-privileges:true]
    cap_drop: [ALL]
    restart: unless-stopped
EOF

systemctl stop nginx
certbot certonly --standalone --non-interactive --agree-tos --register-unsafely-without-email -d "${BROKER_HOST}"

cat > /etc/nginx/sites-available/aegis-broker <<EOF
limit_req_zone \$binary_remote_addr zone=broker:10m rate=10r/s;
server {
  listen 80;
  listen [::]:80;
  server_name ${BROKER_HOST};
  return 301 https://\$host\$request_uri;
}
server {
  listen 443 ssl http2;
  listen [::]:443 ssl http2;
  server_name ${BROKER_HOST};
  server_tokens off;
  ssl_certificate /etc/letsencrypt/live/${BROKER_HOST}/fullchain.pem;
  ssl_certificate_key /etc/letsencrypt/live/${BROKER_HOST}/privkey.pem;
  ssl_protocols TLSv1.2 TLSv1.3;
  add_header Strict-Transport-Security "max-age=31536000" always;
  add_header X-Content-Type-Options nosniff always;
  add_header X-Frame-Options DENY always;
  client_max_body_size 64k;
  location = /health {
    proxy_pass http://127.0.0.1:8100;
    proxy_set_header Host \$host;
  }
  location = /api/broker/robinhood/oauth/callback {
    limit_req zone=broker burst=5 nodelay;
    proxy_pass http://127.0.0.1:8100;
    proxy_set_header Host \$host;
    proxy_set_header X-Forwarded-Proto https;
  }
  location = /api/broker/robinhood/oauth/complete {
    limit_req zone=broker burst=5 nodelay;
    proxy_pass http://127.0.0.1:8100;
    proxy_set_header Host \$host;
    proxy_set_header X-Forwarded-Proto https;
  }
  location /internal/ {
    allow ${AEGIS_VPC_IP};
    deny all;
    proxy_pass http://127.0.0.1:8100;
    proxy_set_header Host \$host;
    proxy_set_header X-Forwarded-Proto https;
  }
  location / { return 404; }
}
EOF
rm -f /etc/nginx/sites-enabled/default
ln -sfn /etc/nginx/sites-available/aegis-broker /etc/nginx/sites-enabled/aegis-broker
nginx -t

ufw default deny incoming
ufw default allow outgoing
sshd -T > /tmp/aegis-sshd-effective
SSHD_PORT="$(awk '$1 == "port" {print $2; exit}' /tmp/aegis-sshd-effective)"
ss -lntH > /tmp/aegis-listeners
if [[ ! "${SSHD_PORT}" =~ ^[0-9]+$ ]] || ! grep -Eq "[:.]${SSHD_PORT}[[:space:]]" /tmp/aegis-listeners; then
  echo "Unable to verify the active SSH listener; refusing to enable UFW." >&2
  exit 1
fi
ufw allow "${SSHD_PORT}/tcp" comment 'Verified active SSH listener'
ufw allow 80/tcp comment 'ACME and HTTPS redirect'
ufw allow 443/tcp comment 'Broker OAuth callback and private API'
ufw allow from "${AEGIS_VPC_IP}" to any port 443 proto tcp comment 'Aegis backend private access'
ufw --force enable

docker compose -f "${INSTALL_DIR}/compose.yml" up -d --build --wait
systemctl enable --now nginx
systemctl enable --now certbot.timer

echo "Broker gateway installed."
echo "Shared secret remains at ${CONFIG_DIR}/shared-secret; transfer it directly to the Aegis server without chat or Git."
echo "Do not begin OAuth until the Aegis backend points to https://${BROKER_HOST}."
