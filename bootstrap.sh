#!/bin/bash
set -euo pipefail

inventory="ansible/inventory.ini"
playbook="ansible/site.yml"
target_ip="$(awk -F'ansible_host=' '/ansible_host=/{split($2, fields, /[[:space:]]/); print fields[1]; exit}' "$inventory")"

if [[ -z "$target_ip" ]]; then
  echo "Fehler: Keine ansible_host-Adresse in $inventory gefunden." >&2
  exit 1
fi

echo "=== SKIP Bootstrap ==="
echo "Zielserver: $target_ip"
echo

ansible-playbook -i "$inventory" "$playbook" "$@"

echo
echo "=== Bootstrap abgeschlossen ==="
echo "Nächste Schritte: make test && make argocd-bootstrap"
