#!/usr/bin/env bash
# Legt alle Secrets an, die vor dem ersten Sync vorhanden sein muessen
# (postgres, authentik, litellm, silo). Aufruf aus dem Repo-Root.
export KUBECONFIG="${KUBECONFIG:-./kubeconfig}"

for ns in postgres authentik litellm silo; do
  kubectl create namespace "$ns" --dry-run=client -o yaml | kubectl apply -f -
done

AUTHENTIK_PW="$(openssl rand -base64 36 | tr -d '/+=')"
LITELLM_PW="$(openssl rand -base64 36 | tr -d '/+=')"

# Namespace postgres
kubectl -n postgres create secret generic postgres-superuser \
  --from-literal=POSTGRES_PASSWORD="$(openssl rand -base64 36 | tr -d '/+=')"
kubectl -n postgres create secret generic postgres-app-credentials \
  --from-literal=authentik-password="$AUTHENTIK_PW" \
  --from-literal=litellm-password="$LITELLM_PW"

# Namespace authentik
# Admin-Passwort (Benutzer akadmin) per AUTHENTIK_BOOTSTRAP_PASSWORD vorgeben,
# sonst wird eines erzeugt und einmalig ausgegeben.
BOOTSTRAP_PW="${AUTHENTIK_BOOTSTRAP_PASSWORD:-}"
if [ -z "$BOOTSTRAP_PW" ]; then
  BOOTSTRAP_PW="$(openssl rand -base64 18 | tr -d '/+=')"
  BOOTSTRAP_PW_GENERATED=1
fi
if kubectl -n authentik create secret generic authentik-secret \
  --from-literal=AUTHENTIK_SECRET_KEY="$(openssl rand -base64 60 | tr -d '\n')" \
  --from-literal=AUTHENTIK_POSTGRESQL__PASSWORD="$AUTHENTIK_PW" \
  --from-literal=AUTHENTIK_BOOTSTRAP_PASSWORD="$BOOTSTRAP_PW" \
  --from-literal=AUTHENTIK_BOOTSTRAP_TOKEN="$(openssl rand -hex 32)" \
  && [ -n "${BOOTSTRAP_PW_GENERATED:-}" ]; then
  AUTHENTIK_LOGIN_HINT="Authentik-Login: akadmin / $BOOTSTRAP_PW (nur fuer den ersten Start)"
fi

# Namespace litellm
kubectl -n litellm create secret generic litellm-db \
  --from-literal=username=litellm \
  --from-literal=password="$LITELLM_PW"

# Namespace silo
# Ein vorhandenes Secret bleibt unangetastet: die gespeicherten Daten gehoeren
# zu den bisherigen Root-Zugangsdaten.
if kubectl -n silo get secret silo-secret >/dev/null 2>&1; then
  echo "silo-secret existiert bereits, uebersprungen"
else
  kubectl -n silo create secret generic silo-secret \
    --from-literal=MINIO_ROOT_USER=admin \
    --from-literal=MINIO_ROOT_PASSWORD="$(openssl rand -base64 36 | tr -d '/+=')"
fi

if [ -n "${AUTHENTIK_LOGIN_HINT:-}" ]; then
  echo ""
  echo "$AUTHENTIK_LOGIN_HINT"
fi
