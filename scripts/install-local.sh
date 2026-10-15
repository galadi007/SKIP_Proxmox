#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

CLUSTER=skip-local
APPS=(traefik postgres authentik litellm silo)
export KUBECONFIG="$PWD/kubeconfig-local"

fail() { echo "FEHLER: $*" >&2; exit 1; }
step() { echo ""; echo ">> $*"; }

step "Dependencies pruefen"
for tool in k3d kubectl helm openssl docker; do
  command -v "$tool" >/dev/null || fail "'$tool' ist nicht installiert."
done
echo "   ok"

step "1/3 k3d-Cluster $CLUSTER"
if k3d cluster get "$CLUSTER" >/dev/null 2>&1; then
  echo "   existiert bereits"
  k3d cluster start "$CLUSTER" >/dev/null
else
  k3d cluster create --config deploy/local/k3d-cluster.yaml
fi
k3d kubeconfig get "$CLUSTER" > "$KUBECONFIG"
kubectl wait --for=condition=Ready nodes --all --timeout=120s >/dev/null

step "2/3 Secrets anlegen (vorhandene bleiben erhalten)"
./scripts/init-secrets.sh

step "3/3 Charts installieren"
for repo in $(grep -ho 'repository: https://[^ ]*' deploy/charts/*/Chart.yaml | awk '{print $2}' | sort -u); do
  helm repo add "skip-$(echo "$repo" | md5sum | cut -c1-8)" "$repo" --force-update >/dev/null
done

for app in "${APPS[@]}"; do
  chart="deploy/charts/$app"
  args=(-f "$chart/values.yaml")
  [ -f "$chart/values-local.yaml" ] && args+=(-f "$chart/values-local.yaml")
  echo "   $app"
  if grep -q '^dependencies:' "$chart/Chart.yaml"; then
    helm dependency build "$chart" >/dev/null
  fi
  helm upgrade --install "$app" "$chart" -n "$app" --create-namespace \
    "${args[@]}" --wait --timeout 10m >/dev/null \
    || fail "'$app' konnte nicht installiert werden (kubectl -n $app get pods)."
done

echo ""
echo "=== Lokaler Cluster bereit ==="
echo "export KUBECONFIG=$KUBECONFIG"
echo "Authentik: https://authentik.localhost:8443 (selbstsigniertes Zertifikat)"
