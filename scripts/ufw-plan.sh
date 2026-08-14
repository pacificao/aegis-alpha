#!/usr/bin/env bash
set -euo pipefail
ssh_port="$(ss -ltnH | awk '$4 ~ /:([0-9]+)$/ && ($4 ~ /:22$/) {sub(/^.*:/,"",$4); print $4; exit}')"
if [[ -z "${ssh_port}" || ! "${ssh_port}" =~ ^[0-9]+$ ]]; then
  echo "Could not safely detect the active SSH listening port. Stop; inspect sshd manually." >&2
  exit 1
fi
echo "Detected SSH listening port: ${ssh_port}"
echo "Review these commands. Keep a second SSH session open. Nathan must run them manually:"
echo "sudo ufw allow ${ssh_port}/tcp comment 'SSH - add before enabling'"
echo "sudo ufw allow 80/tcp comment 'Aegis HTTP'"
echo "sudo ufw allow 443/tcp comment 'Aegis HTTPS'"
echo "sudo ufw status numbered"
echo "sudo ufw enable"
echo "sudo ufw status verbose"

