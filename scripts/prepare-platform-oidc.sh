#!/usr/bin/env bash
# Run on the k3s VM as root; never logs the generated credential.
set -euo pipefail
set +x
umask 077
command -v kubectl >/dev/null
command -v python3 >/dev/null
kubectl get namespace authentik >/dev/null
kubectl create namespace platform-system --dry-run=client -o yaml | kubectl apply -f - >/dev/null
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
# Prefer either existing copy; distinguish missing resources from API errors.
for ns in authentik platform-system; do
  kubectl -n "$ns" get secret platform-oidc --ignore-not-found -o json > "$work/$ns.json"
done
python3 - "$work" <<'PYTHON'
import base64, json, pathlib, secrets, sys
p=pathlib.Path(sys.argv[1])
values=[]
for ns in ('authentik','platform-system'):
    raw=(p/f'{ns}.json').read_text().strip()
    if raw:
        value=json.loads(raw).get('data',{}).get('OIDC_CLIENT_SECRET')
        if not value:
            raise SystemExit(f'{ns}/platform-oidc exists but is missing OIDC_CLIENT_SECRET; stopping')
        values.append(base64.b64decode(value,validate=True).decode())
if len(set(values))>1:
    raise SystemExit('Existing OIDC secret copies differ; stopping without replacing either')
value=values[0] if values else secrets.token_urlsafe(48)
if not value:
    raise SystemExit('Empty credential; stopping')
(p/'OIDC_CLIENT_SECRET').write_text(value)
PYTHON
for ns in authentik platform-system; do
  if [ ! -s "$work/$ns.json" ]; then
    kubectl -n "$ns" create secret generic platform-oidc \
      --from-file=OIDC_CLIENT_SECRET="$work/OIDC_CLIENT_SECRET" >/dev/null
  fi
done
echo 'OIDC secret is present and identical in authentik and platform-system.'
