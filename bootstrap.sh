#!/bin/bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Zentrale Konfiguration laden. Eine lokale .env darf Werte überschreiben.
set -a
source "${REPO_DIR}/skip-settings.conf"
if [[ -f "${REPO_DIR}/.env" ]]; then
  source "${REPO_DIR}/.env"
fi
set +a

echo "=== SKIP Bootstrap ==="
echo "Zielserver: ${SKIP_SSH_USER}@${SKIP_SERVER_IP}"
echo ""

ansible-playbook \
  -i "${REPO_DIR}/ansible/inventory.ini" \
  "${REPO_DIR}/ansible/site.yml" \
  --extra-vars "ansible_host=${SKIP_SERVER_IP}" \
  --extra-vars "ansible_user=${SKIP_SSH_USER}" \
  --extra-vars "ansible_ssh_private_key_file=${SKIP_SSH_PRIVATE_KEY_FILE}"

echo ""
echo "=== Bootstrap abgeschlossen ==="
echo "Nächster Schritt: make kubeconfig"
