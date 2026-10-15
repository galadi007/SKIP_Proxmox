#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== SKIP Bootstrap ==="
echo "Zielserver: $(grep ansible_host bootstrap/ansible/inventory.ini | awk '{print $2}' | cut -d= -f2)"
echo ""

ansible-playbook -i bootstrap/ansible/inventory.ini bootstrap/ansible/site.yml

echo ""
echo "=== Bootstrap abgeschlossen ==="
echo "Nächster Schritt: make kubeconfig"
