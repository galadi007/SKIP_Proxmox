#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
export KUBECONFIG=./kubeconfig


APPS=(traefik postgres authentik litellm silo)

fail() { echo "FEHLER: $*" >&2; exit 1; }
step() { echo ""; echo ">> $*"; }

sync_app() {
  local app="$1" timeout="${2:-600s}"
  kubectl -n argocd patch application "$app" --type merge \
    -p '{"operation":{"initiatedBy":{"username":"install.sh"},"sync":{}}}' >/dev/null
  echo "   $app: Sync gestartet, warte auf Healthy (max. $timeout)..."
  kubectl -n argocd wait application/"$app" \
    --for=jsonpath='{.status.health.status}'=Healthy --timeout="$timeout" >/dev/null
  echo "   $app: Healthy"
}

step "Voraussetzungen pruefen"
for tool in kubectl helm make openssl; do
  command -v "$tool" >/dev/null || fail "'$tool' ist nicht installiert."
done
[ -f kubeconfig ] || fail "./kubeconfig fehlt. Erst 'make bootstrap' bzw. 'make kubeconfig' ausfuehren."
kubectl get nodes >/dev/null 2>&1 || fail "Cluster nicht erreichbar (kubectl get nodes). VPN/kubeconfig pruefen."
[ -f keys/argocd-github-key ] || fail "keys/argocd-github-key fehlt (Deploy-Key fuer das GitHub-Repo)."
echo "   ok"

if [ -n "$(kubectl -n argocd get applicationset core-apps --ignore-not-found -o name)" ]; then
  fail "Altes ApplicationSet core-apps ist noch aktiv. Erst die bestehende GitOps-Verwaltung geordnet migrieren (siehe README-UMSTELLUNG.md)."
fi

step "1/3 Secrets anlegen (vorhandene bleiben erhalten)"
./scripts/init-secrets.sh

step "2/3 ArgoCD installieren und root-App anwenden"
make argocd-bootstrap

step "3/3 Dienste synchronisieren"
for app in "${APPS[@]}"; do
  for _ in $(seq 60); do
    kubectl -n argocd get application "$app" >/dev/null 2>&1 && break
    sleep 5
  done
  kubectl -n argocd get application "$app" >/dev/null 2>&1 \
    || fail "Application '$app' wurde von der root-App nicht angelegt."
done

for app in "${APPS[@]}"; do
  sync_app "$app" || fail "'$app' ist nicht Healthy geworden. Details: kubectl -n argocd describe application $app"
done

AUTHENTIK_HOST="$(sed -n 's/^  host: *//p' deploy/charts/authentik/values.yaml)"

step "Fertig"
kubectl -n argocd get applications
echo ""
echo "ArgoCD:     make argocd-port-forward  ->  http://localhost:8080"
echo "            User admin, Passwort: $(make -s argocd-password)"
echo "Authentik:  https://${AUTHENTIK_HOST}:30443/if/flow/initial-setup/"
echo "            User akadmin, Passwort siehe Ausgabe von init-secrets oben"
echo "            bzw. AUTHENTIK_BOOTSTRAP_PASSWORD."
