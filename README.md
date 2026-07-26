# FH-Server: Setup-Anleitung

> Team 1 – AI Infrastructure & Operations | Stand: 21.07.2026

---

## Voraussetzung

✓ Die Proxmox-VM `proxmox` ist unter `192.168.0.165` im lokalen Netzwerk erreichbar.

---

## Übersicht: Wo laufen welche Befehle?

| Schritt | Wo ausführen |
|---|---|
| Server aktualisieren, Docker stoppen, k3s reset | SSH auf FH-Server |
| Repo klonen, Ansible, kubectl, make | Lokaler Rechner (Terminal) |

> Ansible, kubectl, helm und make werden direkt auf dem lokalen Rechner installiert.
> Es wird kein Docker Container benötigt.

---

## Gesamtablauf

```text
Phase 1:  Lokale Tools installieren
     ↓
Phase 2:  SSH-Zugang einrichten
     ↓
Phase 3:  FH-Server vorbereiten (per SSH)
     ↓
Phase 4:  Repo-Dateien anlegen
          → Makefile, Ansible, ArgoCD, App-Struktur
     ↓
Phase 5:  Bootstrap ausführen
          → make bootstrap     (k3s via Ansible installieren)
          → make kubeconfig    (kubeconfig lokal verfügbar machen)
          → make test          (Cluster-Verbindung prüfen)
          → make argocd-bootstrap  (ArgoCD + App-of-Apps installieren)
          ✓ Cluster ist jetzt GitOps-fähig
     ↓
Phase 6:  GitHub-Repo in ArgoCD registrieren
          → Deploy Key als Secret hinterlegen
          → ArgoCD Applications auf SSH-URL patchen
     ↓
Phase 7:  Traefik deployen
          → Ingress Controller via ArgoCD + HelmChart CRD
          ✓ HTTP/HTTPS Traffic routing aktiv
     ↓
Phase 8:  Harbor deployen
          → Container Registry via ArgoCD + HelmChart CRD
          → Docker Push/Pull über Port 30443 (HTTPS)
          ✓ Container Images intern pushen und pullen
```

---

## Phase 1 — Lokale Voraussetzungen

### Schritt 1.1 — Tools installieren

**macOS:**

```bash
brew install ansible kubectl helm make git
```

**Ubuntu / Debian:**

```bash
sudo apt update
sudo apt install -y ansible make git curl

# kubectl
curl -LO "https://dl.k8s.io/release/v1.35.0/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
rm kubectl

# helm
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
```

**Windows:**

WSL2 mit Ubuntu installieren, dann wie Ubuntu/Debian vorgehen.

```
1. wsl --install          (in PowerShell als Admin)
2. Ubuntu aus Microsoft Store installieren
3. WSL2-Ubuntu-Terminal öffnen
4. Dann: sudo apt update && sudo apt install -y ansible make git curl
5. kubectl und helm wie Ubuntu oben
```

> **Wichtig für Windows:** Alle nachfolgenden Befehle im WSL2-Ubuntu-Terminal ausführen,
> nicht in CMD oder PowerShell. Das Repo ins WSL2-Dateisystem klonen
> (`~/SKIP_Proxmox`), nicht ins Windows-Dateisystem (`/mnt/c/...`).

### Schritt 1.2 — Versionen prüfen

```bash
ansible --version
kubectl version --client
helm version
make --version
```

> kubectl sollte dieselbe Minor-Version wie k3s auf dem Server haben: `v1.35.x`

---

## Phase 2 — SSH-Zugang einrichten

### Schritt 2.1 — SSH-Schlüsselpaar generieren

```bash
ssh-keygen -t ed25519 -C "mail@fh-swf.de" -f ~/.ssh/id_ed25519_skip
```

### Schritt 2.2 — Public Key beim Prof hinterlegen

```bash
cat ~/.ssh/id_ed25519_skip.pub
```

Den Inhalt an Prof. Giefers schicken — er trägt den Key auf dem Server ein.

### Schritt 2.3 — SSH-Konfiguration anlegen

In `~/.ssh/config` einfügen:

```text
Host proxmox
    HostName 192.168.0.165
    User <eigener-username>
    IdentityFile ~/.ssh/id_ed25519_skip
    IdentitiesOnly yes
```

### Schritt 2.4 — Verbindung testen

```bash
ssh proxmox
```

Erwartete Ausgabe:

```
Welcome to Ubuntu 24.04.3 LTS ...
```

> EduVPN muss aktiv sein. Mit `exit` wieder zurück in das lokale Terminal.

---

## Phase 3 — FH-Server vorbereiten (per SSH)

Alle Befehle in dieser Phase direkt auf dem Server ausführen (`ssh proxmox`).

### Schritt 3.1 — Server aktualisieren

```bash
sudo apt update && sudo apt upgrade -y
```

### Schritt 3.2 — Docker stoppen und deaktivieren

```bash
sudo systemctl stop docker.service docker.socket
sudo systemctl disable docker.service docker.socket
```

> Docker besteht aus zwei Teilen: `docker.service` (Daemon) und `docker.socket`
> (lauscht auf Verbindungen). Beide müssen gestoppt werden — sonst bleibt der Socket
> aktiv und startet Docker bei Bedarf neu.

Prüfen:

```bash
sudo systemctl status docker.service docker.socket
```

Erwartete Ausgabe: beide `inactive (dead)`

### Schritt 3.3 — k3s deinstallieren

```bash
sudo k3s-uninstall.sh
```

> `k3s-uninstall.sh` liegt unter `/usr/local/bin/` und wird automatisch bei der
> k3s-Installation angelegt. Es entfernt k3s, alle Container, Volumes und den
> gesamten Kubernetes-Zustand sauber.

### Schritt 3.4 — `/opt/skip` anlegen

```bash
sudo mkdir -p /opt/skip
sudo chown -R :sudo /opt/skip
sudo chmod -R 775 /opt/skip
```

### Schritt 3.5 — Deploy Key erstellen und Repo clonen

**Deploy Key erzeugen:**

```bash
sudo mkdir -p /opt/skip/.ssh
sudo ssh-keygen -t ed25519 -C "skip-server-deploy" -f /opt/skip/.ssh/deploy_key
# Passphrase leer lassen
```

**Public Key anzeigen:**

```bash
sudo cat /opt/skip/.ssh/deploy_key.pub
```

**Public Key in GitHub hinterlegen:**

```
GitHub Repo → Settings → Deploy Keys → Add deploy key
Title:              skip-server
Key:                <Inhalt von deploy_key.pub>
Allow write access: NEIN (read-only reicht)
```

**SSH-Config einrichten:**

```bash
sudo tee /opt/skip/.ssh/config << EOF
Host github.com
    IdentityFile /opt/skip/.ssh/deploy_key
    StrictHostKeyChecking no
EOF
```

**Repo clonen:**

```bash
cd /opt/skip
sudo GIT_SSH_COMMAND="ssh -F /opt/skip/.ssh/config" \
git clone git@github.com:galadi007/SKIP_Proxmox.git
```

**Verzeichnis für alle Admins freigeben (einmalig pro Admin auf dem Server):**

```bash
git config --global --add safe.directory /opt/skip/SKIP_Proxmox
```

Server-Session beenden:

```bash
exit
```

---

## Phase 4 — Repo-Dateien anlegen (auf dem Admin-Rechner)

### Schritt 4.1 — GitHub SSH-Zugang einrichten

Damit `git clone` über SSH funktioniert, muss ein eigener SSH-Key bei GitHub hinterlegt sein.
Dieser Schritt ist einmalig pro Rechner — unabhängig vom Server-Key aus Phase 2.

**Schritt 4.1.1 — SSH-Schlüsselpaar generieren:**

```bash
ssh-keygen -t ed25519 -C "mail@fh-swf.de" -f ~/.ssh/id_ed25519_github
```

**Schritt 4.1.2 — Öffentlichen Schlüssel anzeigen:**

```bash
cat ~/.ssh/id_ed25519_github.pub
```

- Auf GitHub.com einloggen
- Rechts oben auf Profilbild klicken → **Settings** → **SSH and GPG keys** → **New SSH key**
- Titel vergeben (z.B. `skip-admin-macbook`) und Key einfügen

**Schritt 4.1.3 — SSH-Konfiguration anlegen:**

In `~/.ssh/config` einfügen:

```text
Host github.com
    HostName github.com
    User git
    IdentityFile ~/.ssh/id_ed25519_github
    IdentitiesOnly yes
```

**Schritt 4.1.4 — Verbindung testen:**

```bash
ssh -T git@github.com
```

Erwartete Ausgabe:

```
Hi <username>! You've successfully authenticated...
```

> **Zwei verschiedene SSH-Keys:** Der Key aus Phase 2 (`id_ed25519_skip`) ist für den
> Zugang zum FH-Server `proxmox`. Dieser Key (`id_ed25519_github`) ist für den Zugang
> zu GitHub. Beide müssen separat eingerichtet werden.

### Schritt 4.2 — Repo klonen

```bash
git clone git@github.com:galadi007/SKIP_Proxmox.git
cd SKIP_Proxmox
```

> **Tipp:** Falls das Repo bereits über HTTPS geklont wurde, nachträglich auf SSH umstellen:
>
> ```bash
> git remote set-url origin git@github.com:galadi007/SKIP_Proxmox.git
> ```

### Schritt 4.3 — Verzeichnisstruktur anlegen

```bash
mkdir -p ansible
mkdir -p argocd
mkdir -p apps/core/traefik
mkdir -p apps/core/harbor
mkdir -p apps/core/cert-manager
mkdir -p apps/core/longhorn
mkdir -p apps/services/ollama
mkdir -p apps/services/open-webui
mkdir -p apps/services/qdrant
mkdir -p apps/services/monitoring
```

### Schritt 4.4 — `.gitignore` anlegen

```bash
cat > .gitignore << 'EOF'
ansible/inventory.ini
kubeconfig
*.pem
*.key
id_ed25519*
!*.pub
.env
EOF
```

### Schritt 4.5 — `bootstrap.sh` anlegen

```bash
cat > bootstrap.sh << 'EOF'
#!/bin/bash
set -euo pipefail

echo "=== SKIP Bootstrap ==="
ansible-playbook -i ansible/inventory.ini ansible/site.yml
echo ""
echo "=== Bootstrap abgeschlossen ==="
echo "Nächster Schritt: make kubeconfig"
EOF

chmod +x bootstrap.sh
git update-index --chmod=+x bootstrap.sh
```

### Schritt 4.6 — `Makefile` anlegen

```makefile
.PHONY: bootstrap kubeconfig test argocd-bootstrap argocd-password argocd-ui

bootstrap:
	./bootstrap.sh

kubeconfig:
	scp proxmox:/etc/rancher/k3s/k3s.yaml ./kubeconfig
	sed -i 's/127.0.0.1/192.168.0.165/g' ./kubeconfig
	@echo "kubeconfig gespeichert. Aktivieren mit:"
	@echo "  export KUBECONFIG=$$(pwd)/kubeconfig"

test:
	KUBECONFIG=./kubeconfig kubectl get nodes

argocd-bootstrap:
	KUBECONFIG=./kubeconfig kubectl create namespace argocd --dry-run=client -o yaml | \
	  KUBECONFIG=./kubeconfig kubectl apply -f -
	KUBECONFIG=./kubeconfig kubectl apply -n argocd \
	  -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml \
	  --server-side
	@echo "Warte bis ArgoCD bereit ist..."
	KUBECONFIG=./kubeconfig kubectl wait --for=condition=available \
	  deployment/argocd-server -n argocd --timeout=300s
	KUBECONFIG=./kubeconfig kubectl apply -f argocd/app-of-apps.yaml
	@echo ""
	@echo "=== ArgoCD Bootstrap abgeschlossen ==="

argocd-password:
	@KUBECONFIG=./kubeconfig kubectl -n argocd get secret argocd-initial-admin-secret \
	  -o jsonpath="{.data.password}" | base64 -d
	@echo ""

argocd-ui:
	@echo "ArgoCD UI: https://localhost:8080  (User: admin)"
	KUBECONFIG=./kubeconfig kubectl port-forward svc/argocd-server -n argocd 8080:443
```

### Schritt 4.7 — `ansible/inventory.ini.example` anlegen

```ini
[server]
proxmox ansible_host=192.168.0.165 ansible_user=<eigener-username> ansible_ssh_private_key_file=~/.ssh/id_ed25519_skip
```

### Schritt 4.8 — `ansible/site.yml` anlegen

```yaml
---
- name: SKIP Bootstrap — k3s auf FH-Server installieren
  hosts: server
  become: true

  vars:
    k3s_version: "v1.35.4+k3s1"
    k3s_server_ip: "192.168.0.165"

  tasks:

    - name: Pakete aktualisieren
      apt:
        update_cache: yes
        upgrade: dist

    - name: Benötigte Pakete installieren
      apt:
        name: [curl, git, jq, open-iscsi, nfs-common]
        state: present

    - name: k3s installieren
      shell: |
        curl -sfL https://get.k3s.io | \
          INSTALL_K3S_VERSION="{{ k3s_version }}" \
          sh -s - server \
          --disable servicelb \
          --disable traefik \
          --write-kubeconfig-mode 0644
      args:
        creates: /usr/local/bin/k3s

    - name: Warten bis k3s API erreichbar ist
      wait_for:
        host: 127.0.0.1
        port: 6443
        delay: 5
        timeout: 120

    - name: kubeconfig lokal verfügbar machen
      fetch:
        src: /etc/rancher/k3s/k3s.yaml
        dest: "{{ playbook_dir }}/../kubeconfig"
        flat: true

    - name: Server-IP in kubeconfig eintragen
      delegate_to: localhost
      become: false
      replace:
        path: "{{ playbook_dir }}/../kubeconfig"
        regexp: 'https://127.0.0.1:6443'
        replace: "https://{{ k3s_server_ip }}:6443"
```

> **Hinweis:** `--disable servicelb` und `--disable traefik` — beide werden über
> ArgoCD deployt und deshalb bei der k3s-Installation deaktiviert.

### Schritt 4.9 — `argocd/app-of-apps.yaml` anlegen

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: app-of-apps
  namespace: argocd
spec:
  project: default
  source:
    repoURL: git@github.com:galadi007/SKIP_Proxmox.git
    targetRevision: main
    path: argocd
  destination:
    server: https://kubernetes.default.svc
    namespace: argocd
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
```

### Schritt 4.10 — Dateien committen

```bash
git add .
git commit -m "feat: Bootstrap-Struktur anlegen (Makefile, Ansible, ArgoCD)"
git push
```

---

## Phase 5 — Bootstrap ausführen (auf dem Admin-Rechner)

### Schritt 5.1 — `inventory.ini` befüllen

```bash
cp ansible/inventory.ini.example ansible/inventory.ini
# Eigenen Username eintragen
```

### Schritt 5.2 — Ansible-Verbindung testen

```bash
ansible all -i ansible/inventory.ini -m ping
```

Erwartete Ausgabe: `proxmox | SUCCESS => { "ping": "pong" }`

### Schritt 5.3 — Bootstrap ausführen

```bash
make bootstrap
```

> ⚠ Nach diesem Schritt läuft k3s, aber der Cluster ist noch **nicht GitOps-fähig**.
> Erst nach `make argocd-bootstrap` synchronisiert ArgoCD aus Git.

### Schritt 5.4 — kubeconfig aktivieren

```bash
# bash / zsh
export KUBECONFIG=$(pwd)/kubeconfig

# fish
set -x KUBECONFIG (pwd)/kubeconfig

# Dauerhaft (fish):
echo 'set -x KUBECONFIG ~/Development/SKIP/SKIP_Proxmox/kubeconfig' >> ~/.config/fish/config.fish
source ~/.config/fish/config.fish
```

### Schritt 5.5 — Cluster prüfen

```bash
make test
```

Erwartete Ausgabe:

```
NAME     STATUS   ROLES           AGE   VERSION
proxmox   Ready    control-plane   Xm    v1.35.4+k3s1
```

### Schritt 5.6 — ArgoCD deployen

```bash
make argocd-bootstrap
```

> **Wichtig:** `--server-side` wird intern verwendet weil ArgoCD CRDs zu groß
> für normales `kubectl apply` sind.

### Schritt 5.7 — ArgoCD UI öffnen

```bash
make argocd-password   # Admin-Passwort anzeigen
make argocd-ui         # Port-Forward starten
```

Browser: `https://localhost:8080` | User: `admin`

---

## Phase 6 — GitHub-Repo in ArgoCD registrieren

ArgoCD kann private GitHub-Repos nicht ohne Credentials lesen.
Ohne diesen Schritt zeigt ArgoCD folgenden Fehler:

```
ComparisonError: Failed to load target state: authentication required: Repository not found.
```

### Schritt 6.1 — Deploy Key als Secret hinterlegen

> Auf dem **Server** ausführen.

```bash
ssh proxmox

sudo kubectl -n argocd create secret generic pg-skip-repo \
  --from-literal=type=git \
  --from-literal=url=git@github.com:galadi007/SKIP_Proxmox.git \
  --from-file=sshPrivateKey=/opt/skip/.ssh/deploy_key

sudo kubectl -n argocd label secret pg-skip-repo \
  argocd.argoproj.io/secret-type=repository
```

> **Wichtig:** Niemals ins Repo committen — enthält den privaten SSH-Key.

### Schritt 6.2 — ArgoCD Applications auf SSH-URL patchen

```bash
sudo kubectl patch application app-of-apps -n argocd \
  --type merge \
  -p '{"spec":{"source":{"repoURL":"git@github.com:galadi007/SKIP_Proxmox.git"}}}'

sudo kubectl patch application traefik -n argocd \
  --type merge \
  -p '{"spec":{"source":{"repoURL":"git@github.com:galadi007/SKIP_Proxmox.git"}}}'
```

### Schritt 6.3 — YAML-Dateien im Repo korrigieren

```bash
sed -i 's|https://github.com/galadi007/SKIP_Proxmox.git|git@github.com:galadi007/SKIP_Proxmox.git|g' argocd/*.yaml

git add .
git commit -m "fix: use SSH URL for ArgoCD repo references"
git push
```

> **Regel:** In allen `argocd/*.yaml` immer SSH-URL verwenden:
> `git@github.com:galadi007/SKIP_Proxmox.git`

---

## Phase 7 — Traefik deployen

Traefik läuft als **NodePort** — kein MetalLB erforderlich.

| Port | Protokoll | Erreichbar unter |
|------|-----------|-----------------|
| 30080 | HTTP | `http://192.168.0.165:30080` |
| 30443 | HTTPS | `https://192.168.0.165:30443` |

### Schritt 7.1 — Manifeste anlegen

**`apps/core/traefik/namespace.yaml`**

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: traefik
```

**`apps/core/traefik/helmrelease.yaml`**

```yaml
apiVersion: helm.cattle.io/v1
kind: HelmChart
metadata:
  name: traefik
  namespace: kube-system
spec:
  repo: https://helm.traefik.io/traefik
  chart: traefik
  targetNamespace: traefik
  version: "33.2.1"
  valuesContent: |-
    deployment:
      replicas: 1

    service:
      type: NodePort

    ports:
      web:
        nodePort: 30080
      websecure:
        nodePort: 30443

    ingressRoute:
      dashboard:
        enabled: true

    logs:
      general:
        level: INFO

    resources:
      requests:
        cpu: 100m
        memory: 128Mi
      limits:
        cpu: 500m
        memory: 256Mi
```

**`argocd/traefik.yaml`**

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: traefik
  namespace: argocd
spec:
  project: default
  source:
    repoURL: git@github.com:galadi007/SKIP_Proxmox.git
    targetRevision: main
    path: apps/core/traefik
  destination:
    server: https://kubernetes.default.svc
    namespace: traefik
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
```

### Schritt 7.2 — Pushen und ArgoCD Application anlegen

> Auf dem **lokalen Rechner** ausführen.

```bash
git add .
git commit -m "feat: Add Traefik ingress controller"
git push

kubectl apply -f argocd/traefik.yaml
```

### Schritt 7.3 — Deployment prüfen

```bash
kubectl get application traefik -n argocd
kubectl get pods -n traefik
kubectl get svc -n traefik
```

Erreichbarkeit testen:

```bash
curl http://192.168.0.165:30080
# Erwartung: HTTP 404 von Traefik (korrekt — kein Ingress konfiguriert)
```

> **Traefik v3:** Erlaubt nur einen Pfad pro `PathPrefix` — mehrere Pfade in
> einer Regel sind nicht erlaubt. Jeden Pfad als separate Route definieren.

---

## Phase 8 — Harbor deployen

Harbor ist die Container Registry für das SKIP-Projekt.

| Komponente | Zweck |
|------------|-------|
| Core | API und Geschäftslogik |
| Portal | Web-UI |
| Registry | Eigentliche Image-Speicherung |
| JobService | Async-Jobs |
| PostgreSQL | Metadaten-Datenbank |
| Redis | Cache und Job-Queue |
| Trivy | Image-Vulnerability-Scanner |

> **Hostname:** `harbor.192-168-0-165.sslip.io` löst automatisch auf `192.168.0.165`
> auf — kein `/etc/hosts` Eintrag nötig, solange Internetzugang besteht.

> **Docker Push/Pull:** Läuft über Port **30443** (HTTPS) mit selbstsigniertem
> Traefik-Zertifikat. Docker muss die Registry als `insecure-registry` konfiguriert
> werden — dann akzeptiert Docker das Zertifikat.

### Schritt 8.1 — Manifeste anlegen

> Auf dem **lokalen Rechner** ausführen.

**`apps/core/harbor/namespace.yaml`**

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: harbor
```

**`apps/core/harbor/helmrelease.yaml`**

```yaml
apiVersion: helm.cattle.io/v1
kind: HelmChart
metadata:
  name: harbor
  namespace: kube-system
spec:
  repo: https://helm.goharbor.io
  chart: harbor
  targetNamespace: harbor
  version: "1.16.0"
  valuesContent: |-
    # externalURL auf HTTP/30080 — Harbor selbst kennt kein HTTPS
    externalURL: https://harbor.192-168-0-165.sslip.io:30443

    # ClusterIP statt Ingress — Traefik IngressRoute übernimmt das Routing
    # Harbor-eigener Ingress verursacht Probleme mit Docker Push über Traefik
    expose:
      type: clusterIP
      tls:
        enabled: false

    harborAdminPassword: "Harbor12345"

    persistence:
      enabled: true
      resourcePolicy: keep
      persistentVolumeClaim:
        registry:
          storageClass: local-path
          size: 20Gi
        jobservice:
          jobLog:
            storageClass: local-path
            size: 1Gi
        database:
          storageClass: local-path
          size: 1Gi
        redis:
          storageClass: local-path
          size: 1Gi
        trivy:
          storageClass: local-path
          size: 5Gi

    core:
      resources:
        requests:
          memory: 256Mi
          cpu: 100m
        limits:
          memory: 512Mi
          cpu: 500m

    registry:
      relativeurls: true    # Relative Upload-URLs für korrekte Traefik-Weiterleitung
      resources:
        requests:
          memory: 256Mi
          cpu: 100m
        limits:
          memory: 512Mi
          cpu: 500m

    database:
      internal:
        resources:
          requests:
            memory: 256Mi
            cpu: 100m
          limits:
            memory: 512Mi
            cpu: 500m

    redis:
      internal:
        resources:
          requests:
            memory: 64Mi
            cpu: 50m
          limits:
            memory: 256Mi
            cpu: 250m

    trivy:
      enabled: true
      resources:
        requests:
          memory: 256Mi
          cpu: 100m
        limits:
          memory: 512Mi
          cpu: 500m
```

**`apps/core/harbor/ingressroute.yaml`**

> Traefik IngressRoute statt Harbor-eigenem Ingress.
> `websecure` + `tls: {}` stellt Harbor über HTTPS bereit (selbstsigniertes Zertifikat).
> Jeder Pfad als eigene Route mit `priority: 100` — Traefik v3 erlaubt nur einen
> Pfad pro `PathPrefix` Regel.

```yaml
apiVersion: traefik.io/v1alpha1
kind: IngressRoute
metadata:
  name: harbor
  namespace: harbor
spec:
  entryPoints:
    - web
    - websecure
  routes:
    - match: Host(`harbor.192-168-0-165.sslip.io`) && PathPrefix(`/api/`)
      kind: Rule
      priority: 100
      services:
        - name: harbor-core
          port: 80
    - match: Host(`harbor.192-168-0-165.sslip.io`) && PathPrefix(`/service/`)
      kind: Rule
      priority: 100
      services:
        - name: harbor-core
          port: 80
    - match: Host(`harbor.192-168-0-165.sslip.io`) && PathPrefix(`/v2/`)
      kind: Rule
      priority: 100
      services:
        - name: harbor-core
          port: 80
    - match: Host(`harbor.192-168-0-165.sslip.io`) && PathPrefix(`/c/`)
      kind: Rule
      priority: 100
      services:
        - name: harbor-core
          port: 80
    - match: Host(`harbor.192-168-0-165.sslip.io`)
      kind: Rule
      priority: 10
      services:
        - name: harbor-portal
          port: 80
  tls: {}
```

**`argocd/harbor.yaml`**

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: harbor
  namespace: argocd
spec:
  project: default
  source:
    repoURL: git@github.com:galadi007/SKIP_Proxmox.git
    targetRevision: main
    path: apps/core/harbor
  destination:
    server: https://kubernetes.default.svc
    namespace: harbor
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
```

### Schritt 8.2 — Pushen und ArgoCD Application anlegen

> Auf dem **lokalen Rechner** ausführen.

```bash
git add .
git commit -m "feat: Add Harbor container registry with Traefik IngressRoute"
git push

kubectl apply -f argocd/harbor.yaml
```

> **fish shell:** `set -x KUBECONFIG ~/Development/SKIP/SKIP_Proxmox/kubeconfig`

### Schritt 8.3 — containerd für HTTPS-Registry konfigurieren

> Auf dem **Server** ausführen.

containerd muss Harbor als vertrauenswürdige Registry kennen:

```bash
ssh proxmox
sudo nano /etc/rancher/k3s/registries.yaml
```

Inhalt:

```yaml
mirrors:
  "harbor.192-168-0-165.sslip.io:30443":
    endpoint:
      - "https://harbor.192-168-0-165.sslip.io:30443"
```

k3s neu starten:

```bash
sudo systemctl restart k3s
```

Warten bis k3s wieder bereit:

```bash
kubectl get nodes
# Erwartung: proxmox   Ready
```

### Schritt 8.4 — Deployment prüfen

> Vom **lokalen Rechner** ausführen.

```bash
kubectl get application harbor -n argocd
kubectl get pods -n harbor -w
```

Erwartete Ausgabe:

```
NAME                      READY   STATUS
harbor-core-xxx           1/1     Running
harbor-database-xxx       1/1     Running
harbor-jobservice-xxx     1/1     Running
harbor-portal-xxx         1/1     Running
harbor-redis-xxx          1/1     Running
harbor-registry-xxx       2/2     Running
harbor-trivy-xxx          1/1     Running
```

> Erster Start dauert ca. 3–5 Minuten.

### Schritt 8.5 — Harbor Web-UI aufrufen

Browser: `https://harbor.192-168-0-165.sslip.io:30443`

> Traefik zeigt eine Zertifikatswarnung (selbstsigniertes Zertifikat) — einmalig bestätigen.

| Feld | Wert |
|------|------|
| User | `admin` |
| Passwort | `Harbor12345` (Default — sofort ändern!) |

### Schritt 8.6 — Admin-Passwort ändern

```
Admin (oben rechts) → User Profile → Change Password
```

Anforderungen: mindestens 8 Zeichen, Groß- und Kleinbuchstaben sowie Zahlen.

> **Niemals das Passwort ins Git-Repo committen.**
> Neues Passwort dem Team mitteilen — alle Admins brauchen es für `docker login`.

### Schritt 8.7 — Docker für Harbor Registry konfigurieren

> Auf jedem Rechner ausführen der Images pushen oder pullen soll.

Docker Push und Pull läuft über Port **30443** (HTTPS). Traefik verwendet ein
selbstsigniertes Zertifikat — Docker muss die Registry als `insecure-registry`
konfiguriert werden damit es das Zertifikat akzeptiert.

**Linux:**

```bash
sudo nano /etc/docker/daemon.json
```

Falls die Datei bereits Einträge enthält:

```json
{
  "bip": "192.168.200.1/24",
  "default-address-pools": [
    { "base": "192.168.200.0/20", "size": 24 }
  ],
  "insecure-registries": ["harbor.192-168-0-165.sslip.io:30443"]
}
```

Falls die Datei leer ist:

```json
{
  "insecure-registries": ["harbor.192-168-0-165.sslip.io:30443"]
}
```

Docker neu starten:

```bash
sudo systemctl restart docker
```

**macOS (Docker Desktop):**

Docker Desktop → Settings → Docker Engine → JSON ergänzen:

```json
{
  "insecure-registries": ["harbor.192-168-0-165.sslip.io:30443"]
}
```

Apply & Restart klicken.

### Schritt 8.8 — Projekte für SKIP anlegen

In der Harbor UI:

```
Projects → New Project → Name: skip_core         Access: Private
Projects → New Project → Name: skip_platform     Access: Private
Projects → New Project → Name: skip_applications Access: Private
```

| Projekt | Zweck |
|---------|-------|
| `skip_core` | Basis-Images, Infrastruktur-Tools |
| `skip_platform` | Platform-Services (Harbor, Traefik, etc.) |
| `skip_applications` | KI-Anwendungen (Ollama, Open WebUI, Qdrant, etc.) |

### Schritt 8.9 — Image pushen und pullen (Test)

**Vom lokalen Rechner (empfohlen):**

```bash
docker login harbor.192-168-0-165.sslip.io:30443
docker tag hello-world harbor.192-168-0-165.sslip.io:30443/skip_applications/hello-world:latest
docker push harbor.192-168-0-165.sslip.io:30443/skip_applications/hello-world:latest
docker pull harbor.192-168-0-165.sslip.io:30443/skip_applications/hello-world:latest
```

Image in Harbor UI prüfen: `Projects → skip_applications → Repositories`

**Vom Server aus (Fallback):**

```bash
ssh proxmox

sudo nano /etc/docker/daemon.json
# insecure-registries: ["harbor.192-168-0-165.sslip.io:30443"] eintragen

sudo systemctl restart docker
sudo docker login harbor.192-168-0-165.sslip.io:30443
sudo docker pull hello-world
sudo docker tag hello-world harbor.192-168-0-165.sslip.io:30443/skip_applications/hello-world:latest
sudo docker push harbor.192-168-0-165.sslip.io:30443/skip_applications/hello-world:latest
```

---

## Bekannte Probleme & Hinweise

| Problem | Ursache | Lösung |
|---|---|---|
| Server nicht erreichbar | EduVPN nicht aktiv | VPN verbinden |
| `ansible: command not found` | Ansible nicht installiert | Phase 1 nachholen |
| `kubectl: command not found` | kubectl nicht installiert | Phase 1 nachholen |
| `KUBECONFIG` nicht gesetzt | Umgebungsvariable fehlt | bash/zsh: `export KUBECONFIG=<pfad>/kubeconfig` — fish: `set -x KUBECONFIG <pfad>/kubeconfig` — dauerhaft in `~/.config/fish/config.fish` |
| `Permission denied` SSH | Falscher Key oder Username | `inventory.ini` prüfen |
| `docker.socket` startet Docker neu | Nur `docker.service` gestoppt | Immer beide stoppen: `docker.service docker.socket` |
| kubectl-Version stimmt nicht | Versionskonflikt mit k3s | kubectl Minor-Version muss zu k3s passen (`v1.35.x`) |
| `make kubeconfig` schlägt fehl — kubeconfig ist Verzeichnis | `scp` hat Verzeichnis statt Datei angelegt | `rm -rf kubeconfig` dann nochmal |
| ArgoCD: `authentication required` | Kein Credential hinterlegt | Deploy Key als Secret anlegen (Phase 6) |
| ArgoCD: Application bleibt `Unknown` | HTTPS/SSH-URL Mismatch | Applications mit `kubectl patch` auf SSH-URL umstellen (Phase 6.2) |
| `kubectl apply` bei ArgoCD schlägt fehl | CRD zu groß | `--server-side` verwenden |
| `docker push` mit `404` obwohl curl funktioniert | Docker sieht EduVPN-Route nicht (eigener Netzwerk-Namespace) | Port 30443 verwenden — funktioniert auf allen Systemen |
| `docker push` mit `404 page not found` über Traefik | Harbor-eigener Ingress funktioniert nicht mit Traefik für Docker Push | `expose.type: clusterIP` + Traefik `IngressRoute` verwenden (Phase 8.1) |
| `registry` Key doppelt in `helmrelease.yaml` | YAML überschreibt ersten Eintrag — `relativeurls: true` geht verloren | `registry` nur einmal definieren, `relativeurls: true` vor `resources` |
| `Ingress invalid: must be a DNS name, not an IP address` | Kubernetes erlaubt keine IP als Ingress-Host | sslip.io Hostname verwenden |
| `PathPrefix` mit mehreren Pfaden in Traefik v3 | Traefik v3 erlaubt nur einen Pfad pro Regel | Jeden Pfad als separate Route definieren |
| Harbor Pods bleiben in `Pending` | PVCs nicht gebunden | `kubectl get pvc -n harbor` prüfen |
| sslip.io nicht auflösbar | Kein Internetzugang | EduVPN prüfen |

---

## Versionen synchron halten

```bash
# k3s-Version auf dem Server prüfen
ssh proxmox "k3s --version"

# kubectl-Version lokal prüfen
kubectl version --client
```

---

## Nächste Schritte — Produktive CI/CD Pipeline

### Option A — GitHub Actions mit Self-Hosted Runner (empfohlen)

```yaml
# .github/workflows/build-push.yml
name: Build and Push Image
on:
  push:
    branches: [main]
jobs:
  build:
    runs-on: self-hosted
    steps:
      - uses: actions/checkout@v4
      - name: Login to Harbor
        run: |
          echo "${{ secrets.HARBOR_PASSWORD }}" | \
          docker login harbor.192-168-0-165.sslip.io:30443 \
            -u admin --password-stdin
      - name: Build and Push
        run: |
          docker build -t harbor.192-168-0-165.sslip.io:30443/skip_applications/myapp:latest .
          docker push harbor.192-168-0-165.sslip.io:30443/skip_applications/myapp:latest
```

Runner auf dem Server installieren:

```bash
ssh proxmox
mkdir -p /opt/skip/actions-runner && cd /opt/skip/actions-runner
curl -o actions-runner-linux-x64-2.321.0.tar.gz -L \
  https://github.com/actions/runner/releases/download/v2.321.0/actions-runner-linux-x64-2.321.0.tar.gz
tar xzf ./actions-runner-linux-x64-2.321.0.tar.gz

# Token aus: GitHub → Repository → Settings → Actions → Runners
./config.sh --url https://github.com/galadi007/SKIP_Proxmox \
  --token <RUNNER_TOKEN>

sudo ./svc.sh install
sudo ./svc.sh start
```

### Option B — Kaniko im Cluster (GitOps-konform)

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: kaniko-build
spec:
  template:
    spec:
      containers:
        - name: kaniko
          image: gcr.io/kaniko-project/executor:latest
          args:
            - "--context=git://github.com/galadi007/SKIP_Proxmox"
            - "--destination=harbor.192-168-0-165.sslip.io:30443/skip_applications/myapp:latest"
            - "--insecure"
      restartPolicy: Never
```

### Option C — n8n Workflow (Low-Code)

Wenn n8n deployt ist, kann ein Workflow den Build-Prozess per SSH auf `proxmox` triggern.

### Empfehlung

**Kurzfristig:** Manueller Push über Port 30443 vom lokalen Rechner (Schritt 8.9).

**Mittelfristig:** GitHub Actions Self-Hosted Runner (Option A).

**Langfristig:** Kaniko im Cluster (Option B) — vollständig GitOps-konform.
