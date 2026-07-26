# SKIP auf Proxmox

Dieses Repository baut die lokale SKIP-Infrastruktur auf der Ubuntu-VM
`skip` vollständig reproduzierbar auf:

- Server: `192.168.0.165`
- SSH-Benutzer: `ubuntu`
- Kubernetes: Single-Node-k3s `v1.35.4+k3s1`
- GitOps: ArgoCD App-of-Apps
- Ingress: Traefik über die NodePorts `30080` und `30443`
- Registry: Harbor mit persistentem `local-path`-Storage

Ansible bereitet Ubuntu vor, installiert k3s, erzeugt die lokale TLS-CA und
legt die Kubernetes-TLS-Secrets an. ArgoCD liest anschließend dieses
Repository und rollt Traefik, Harbor sowie die ArgoCD-Webroute aus.

## Voraussetzungen

Auf dem Admin-Rechner beziehungsweise in WSL werden benötigt:

```bash
sudo apt update
sudo apt install -y ansible make git curl python3
```

`kubectl` muss ebenfalls installiert sein. Der Ubuntu-Server muss bereits
unter `192.168.0.165` erreichbar sein und der Benutzer `ubuntu` muss SSH sowie
`sudo` verwenden können.

SSH-Zugang testen:

```bash
ssh ubuntu@192.168.0.165
```

Falls noch kein Schlüssel hinterlegt ist:

```bash
ssh-copy-id ubuntu@192.168.0.165
```

## Vollständiger Neuaufbau

Im Repository ausführen:

```bash
ansible all -i ansible/inventory.ini -m ping
make bootstrap
make test
make argocd-bootstrap
make status
```

Falls `sudo` auf dem Server ein Passwort verlangt:

```bash
make bootstrap ANSIBLE_ARGS=--ask-become-pass
```

`make bootstrap` legt automatisch zwei lokale, nicht versionierte Dateien an:

- `kubeconfig`
- `certs/skip-root-ca.crt`

## Änderungen auf dem bestehenden Cluster ausrollen

ArgoCD liest ausschließlich den Stand des Branches `main` aus GitHub. Deshalb
müssen Änderungen zuerst committed und gepusht werden:

```bash
git status --short
git diff --check
git add -A
git commit -m "Lokale Proxmox-Umgebung und GitOps-Struktur korrigieren"
git push origin main
```

Danach die TLS-Konfiguration auf dem vorhandenen Server aktualisieren und den
GitOps-Rollout starten:

```bash
make tls
make deploy
make status
```

Bei einem `sudo`-Passwort:

```bash
make tls ANSIBLE_ARGS=--ask-become-pass
```

`make deploy` aktualisiert die App-of-Apps-Anwendung, wartet auf alle
Core-Anwendungen und startet den ArgoCD-Server einmal neu, damit
`server.insecure` hinter der TLS-Terminierung von Traefik wirksam wird.

## Weboberflächen

Nach erfolgreichem Rollout:

- ArgoCD: <https://argocd.192-168-0-165.sslip.io:30443>
- Harbor: <https://harbor.192-168-0-165.sslip.io:30443>

ArgoCD-Anmeldung:

```bash
make argocd-password
```

Benutzername: `admin`

Falls die direkte Route noch nicht funktioniert, steht ein Port-Forward als
Fallback bereit:

```bash
make argocd-ui
```

Danach: <http://localhost:8080>

## Lokaler Root-CA vertrauen

Ansible erzeugt ein Zertifikat, das exakt für diese Hostnamen gültig ist:

- `harbor.192-168-0-165.sslip.io`
- `argocd.192-168-0-165.sslip.io`
- `*.192-168-0-165.sslip.io`

Damit Browser und Docker das Zertifikat ohne Warnung akzeptieren, muss
`certs/skip-root-ca.crt` auf dem Client als vertrauenswürdige Root-CA
installiert werden.

Windows PowerShell als Administrator, aus dem Repository:

```powershell
certutil -addstore -f Root .\certs\skip-root-ca.crt
```

Anschließend Browser und Docker Desktop neu starten.

Bei einer eigenständigen Docker-Engine unter Ubuntu:

```bash
sudo cp certs/skip-root-ca.crt \
  /usr/local/share/ca-certificates/skip-root-ca.crt
sudo update-ca-certificates
sudo systemctl restart docker
```

Zertifikat prüfen:

```bash
openssl s_client \
  -connect harbor.192-168-0-165.sslip.io:30443 \
  -servername harbor.192-168-0-165.sslip.io \
  -CAfile certs/skip-root-ca.crt </dev/null
```

Die Ausgabe soll `Verify return code: 0 (ok)` enthalten.

## Harbor verwenden

Anmelden:

```bash
docker login harbor.192-168-0-165.sslip.io:30443 -u admin
```

Beispiel-Image bauen und pushen:

```bash
docker build -t \
  harbor.192-168-0-165.sslip.io:30443/skip_infrastructure/harbor-test:v1 .

docker push \
  harbor.192-168-0-165.sslip.io:30443/skip_infrastructure/harbor-test:v1
```

Das Projekt `skip_infrastructure` muss zuvor in Harbor existieren. Das
anfängliche Harbor-Admin-Passwort steht im HelmChart-Manifest und sollte nach
der ersten Anmeldung geändert werden.

## Diagnose

Kompakter Gesamtstatus:

```bash
make status
```

Einzelne Prüfungen:

```bash
KUBECONFIG=./kubeconfig kubectl get applications -n argocd
KUBECONFIG=./kubeconfig kubectl get pods -A
KUBECONFIG=./kubeconfig kubectl get ingressroute.traefik.io -A
KUBECONFIG=./kubeconfig kubectl get pvc -A
```

Harbor-Logs:

```bash
KUBECONFIG=./kubeconfig kubectl logs \
  -n harbor deployment/harbor-core --tail=100

KUBECONFIG=./kubeconfig kubectl logs \
  -n harbor deployment/harbor-jobservice --tail=100
```

## Repository-Struktur

```text
.
├── ansible/
│   ├── inventory.ini
│   ├── inventory.example.ini
│   └── site.yml
├── apps/core/
│   ├── argocd/
│   ├── harbor/
│   └── traefik/
├── argocd/
│   ├── app-of-apps.yaml
│   └── core/
├── bootstrap.sh
├── Makefile
└── README.md
```

`argocd/app-of-apps.yaml` verwaltet die drei Child-Applications unter
`argocd/core/`. Diese verweisen ausschließlich auf:

```text
https://github.com/galadi007/SKIP_Proxmox.git
```

## Gepinnte Versionen

- k3s: `v1.35.4+k3s1`
- ArgoCD: `v3.4.4`
- Harbor Helm Chart: `1.16.0`
- Traefik Helm Chart: `33.2.1`

Harbor und Traefik bleiben zunächst auf den bereits erfolgreich eingesetzten
Versionen. Ein Versionssprung wird getrennt durchgeführt, weil Harbor dabei
Datenbankmigrationen und Traefik CRD-Änderungen enthalten kann.
