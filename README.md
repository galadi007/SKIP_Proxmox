# SKIP Proxmox – Single-Node GitOps

Dieses Repository installiert und verwaltet die SKIP-Infrastruktur auf einem
Single-Node-k3s-Cluster. ArgoCD synchronisiert die Anwendungen automatisch aus
dem konfigurierten Git-Repository.

## Zentrale Konfiguration

Alle nicht geheimen, umgebungsspezifischen Werte stehen ausschließlich in:

```text
apps/core/cluster-host/skip-settings.conf
```

Die Datei enthält:

```ini
SKIP_ENV=productive
SKIP_REPOSITORY_URL=<Git-Repository>
SKIP_SERVER_IP=<Server-IP>
SKIP_BASE_DOMAIN=<Server-IP-mit-Bindestrichen>.sslip.io
SKIP_HTTPS_PORT=30443
SKIP_SSH_USER=<SSH-Benutzer>
SKIP_SSH_PRIVATE_KEY_FILE=<Pfad-zum-privaten-Schlüssel>
```

Bei einem Wechsel des Servers oder Repositorys wird diese zentrale Datei
angepasst. `SKIP_SERVER_IP` enthält die normale IP-Adresse, während
`SKIP_BASE_DOMAIN` dieselbe IP mit Bindestrichen für `sslip.io` enthält.

Die externen Webadressen werden aus Basisdomain und HTTPS-NodePort gebildet:

```text
https://argocd.<SKIP_BASE_DOMAIN>:<SKIP_HTTPS_PORT>
https://harbor.<SKIP_BASE_DOMAIN>:<SKIP_HTTPS_PORT>
```

`sslip.io` löst die eingebettete IP automatisch auf. Ein eigener DNS- oder
Hosts-Eintrag ist nicht notwendig.

## Verwaltete Komponenten

| Komponente | Pfad | Zugriff |
|---|---|---|
| ArgoCD | `apps/core/argocd` | HTTPS über Traefik |
| Harbor | `apps/core/harbor` | HTTPS über Traefik |
| Traefik | `apps/core/traefik` | NodePorts 30080 und 30443 |
| Sealed Secrets | `apps/core/sealed-secrets` | clusterintern |
| LiteLLM | `apps/services/litellm` | clusterintern |
| MinIO | `apps/services/minio` | clusterintern |

Das zentrale `argocd/applicationset.yaml` erzeugt und synchronisiert die
zugehörigen ArgoCD-Applications.

## Lokale Vorbereitung

Benötigt werden:

- WSL oder Linux
- SSH-Zugriff auf den Zielserver
- `git`, `make`, `ansible` und `kubectl`
- ein vorhandener privater SSH-Schlüssel

Konfiguration laden und prüfen:

```bash
source apps/core/cluster-host/skip-settings.conf

printf 'Repository: %s\n' "$SKIP_REPOSITORY_URL"
printf 'Server: %s@%s\n' "$SKIP_SSH_USER" "$SKIP_SERVER_IP"
```

SSH-Verbindung testen:

```bash
ssh -i "$SKIP_SSH_PRIVATE_KEY_FILE" \
  "$SKIP_SSH_USER@$SKIP_SERVER_IP"
```

## Git-Repository abgleichen

```bash
make git-remote
git remote -v
```

## k3s bereitstellen

Für `SKIP_ENV=productive` oder `SKIP_ENV=test`:

```bash
make bootstrap
```

Bei `SKIP_ENV=development` wird das Ansible-Provisioning übersprungen und ein
bereits vorhandener Server verwendet.

Kubeconfig abrufen und Verbindung prüfen:

```bash
make kubeconfig
export KUBECONFIG="$(pwd)/kubeconfig"
make test
```

## ArgoCD und GitOps installieren

```bash
make argocd-bootstrap
```

Die Root-Kustomization liest Repository und Serverdaten aus derselben
`skip-settings.conf`. Das ApplicationSet setzt die Repository-URL für alle
Applications. ArgoCD und Harbor verwenden die Server-IP für ihre
`sslip.io`-IngressRoutes.

Status prüfen:

```bash
kubectl -n argocd get applications
```

Erwartet wird für alle Applications `Synced` und `Healthy`.

## Weboberflächen

Nach dem Laden der Konfiguration:

```bash
source apps/core/cluster-host/skip-settings.conf

ARGOCD_URL="https://argocd.${SKIP_BASE_DOMAIN}:${SKIP_HTTPS_PORT}"
HARBOR_URL="https://harbor.${SKIP_BASE_DOMAIN}:${SKIP_HTTPS_PORT}"

printf '%s\n' "$ARGOCD_URL" "$HARBOR_URL"
```

Erreichbarkeit testen:

```bash
curl -kI "$ARGOCD_URL"
curl -kI "$HARBOR_URL"
```

Beide Aufrufe sollten mit HTTP 200 antworten. Wegen des standardmäßig
selbstsignierten Traefik-Zertifikats kann der Browser zunächst eine
Zertifikatswarnung anzeigen.

ArgoCD-Passwort abrufen:

```bash
make argocd-password
```

Port-Forward als Fallback:

```bash
make argocd-port-forward
```

## Änderungen ausrollen

```bash
git add .
git commit -m "Beschreibung der Änderung"
git pull --rebase origin main
git push origin main
```

ArgoCD synchronisiert Änderungen automatisch. Ein sofortiger Hard-Refresh ist
bei Bedarf möglich:

```bash
kubectl -n argocd annotate application argocd \
  argocd.argoproj.io/refresh=hard --overwrite

kubectl -n argocd annotate application harbor \
  argocd.argoproj.io/refresh=hard --overwrite
```

IngressRoutes prüfen:

```bash
kubectl -n argocd get ingressroute argocd \
  -o jsonpath='{.spec.routes[0].match}{"\n"}'

kubectl -n harbor get ingressroute harbor \
  -o jsonpath='{range .spec.routes[*]}{.match}{"\n"}{end}'
```

## Secrets

Geheime Werte gehören nicht in `skip-settings.conf` und nicht unverschlüsselt
ins Git-Repository. Lokale Abweichungen können in der von Git ignorierten
`.env` stehen. Kubernetes-Secrets werden manuell oder als `SealedSecret`
bereitgestellt.

Benötigte Schlüssel prüfen:

```bash
kubectl -n minio get secret minio-secret
kubectl -n litellm get secret litellm-secret
```

## Fehlerdiagnose

```bash
kubectl -n argocd get applications
kubectl -n argocd describe application argocd
kubectl -n argocd describe application harbor
kubectl -n traefik get pods
kubectl -n harbor get pods
```

Wenn eine IngressRoute noch einen alten Host enthält, zuerst prüfen, ob die
Änderung nach `main` gepusht wurde und ArgoCD den aktuellen Commit synchronisiert
hat.
