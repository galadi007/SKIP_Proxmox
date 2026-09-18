#!/bin/bash
set -euo pipefail

echo "=== SKIP Bootstrap ==="
echo "Zielserver: $(grep ansible_host ansible/inventory.ini | awk '{print $2}' | cut -d= -f2)"
echo ""

ansible-playbook -i ansible/inventory.ini ansible/site.yml

echo ""
echo "=== Bootstrap abgeschlossen ==="
echo "Nächster Schritt: make kubeconfig"
