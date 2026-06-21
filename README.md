# FH-Server: Setup-Anleitung

> Team 1 – AI Infrastructure & Operations | Stand: 16.06.2026

---

## Voraussetzung

✓ EduVPN aktiv — der Server `gaming` (172.17.204.135) ist nur über EduVPN erreichbar.

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
Schritt 1:  Lokale Tools installieren
     ↓
Schritt 2:  SSH-Zugang einrichten
     ↓
Schritt 3:  FH-Server vorbereiten (per SSH)
     ↓
Schritt 4:  Repo klonen + Dateien anlegen
     ↓
Schritt 5:  make bootstrap
            → Ansible installiert k3s auf dem Server
            ⚠ Cluster bereit, aber noch NICHT GitOps-fähig
     ↓
Schritt 6:  make kubeconfig
            → kubeconfig lokal verfügbar machen
     ↓
Schritt 7:  make test
            → Cluster-Verbindung prüfen
     ↓
Schritt 8:  make argocd-bootstrap
            → ArgoCD + App-of-Apps installieren
            ✓ Ab jetzt ist der Cluster GitOps-fähig
```

---

## Phase 1 — Lokale Voraussetzungen

### macOS

```bash
brew install ansible kubectl helm make git
```

### Ubuntu / Debian

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

### Windows

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
> (`~/PG-SKIP-Infrastructure`), nicht ins Windows-Dateisystem (`/mnt/c/...`).

### Versionen prüfen

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
Host gaming
    HostName 172.17.204.135
    User <eigener-username>
    IdentityFile ~/.ssh/id_ed25519_skip
    IdentitiesOnly yes
```

### Schritt 2.4 — Verbindung testen

```bash
ssh gaming
```

Erwartete Ausgabe:

```
Welcome to Ubuntu 24.04.3 LTS ...
```

> EduVPN muss aktiv sein. Mit `exit` wieder zurück in das lokale Terminal.

---

## Phase 3 — FH-Server vorbereiten (per SSH)

Alle Befehle in dieser Phase direkt auf dem Server ausführen (`ssh gaming`).

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
git clone git@github.com:fhswf/PG-SKIP-Infrastructure.git
```

**Verzeichnis für alle Admins freigeben (einmalig pro Admin auf dem Server):**

```bash
git config --global --add safe.directory /opt/skip/PG-SKIP-Infrastructure
```

Server-Session beenden:

```bash
exit
```

---

## Phase 4 — Repo-Dateien anlegen (auf dem Admin-Rechner)

### Schritt 4.0 — GitHub SSH-Zugang einrichten

Damit `git clone` über SSH funktioniert, muss ein eigener SSH-Key bei GitHub hinterlegt sein.
Dieser Schritt ist einmalig pro Rechner — unabhängig vom Server-Key aus Phase 2.

**Schritt 4.0.1 — SSH-Schlüsselpaar generieren:**

```bash
ssh-keygen -t ed25519 -C "mail@fh-swf.de" -f ~/.ssh/id_ed25519_github
```

**Schritt 4.0.2 — Öffentlichen Schlüssel anzeigen:**

```bash
cat ~/.ssh/id_ed25519_github.pub
```

- Auf GitHub.com einloggen
- Rechts oben auf Profilbild klicken → **Settings** → **SSH and GPG keys** → **New SSH key**
- Titel vergeben (z.B. `skip-admin-macbook`) und Key einfügen

**Schritt 4.0.3 — SSH-Konfiguration anlegen:**

In `~/.ssh/config` einfügen:

```text
Host github.com
    HostName github.com
    User git
    IdentityFile ~/.ssh/id_ed25519_github
    IdentitiesOnly yes
```

**Schritt 4.0.4 — Verbindung testen:**

```bash
ssh -T git@github.com
```

Erwartete Ausgabe:

```
Hi <username>! You've successfully authenticated...
```

> **Zwei verschiedene SSH-Keys:** Der Key aus Phase 2 (`id_ed25519_skip`) ist für den
> Zugang zum FH-Server `gaming`. Dieser Key (`id_ed25519_github`) ist für den Zugang
> zu GitHub. Beide müssen separat eingerichtet werden.

### Schritt 4.1 — Repo klonen

```bash
git clone git@github.com:fhswf/PG-SKIP-Infrastructure.git
cd PG-SKIP-Infrastructure
```

> **Tipp:** Falls das Repo bereits über HTTPS geklont wurde, nachträglich auf SSH umstellen:
>
> ```bash
> git remote set-url origin git@github.com:fhswf/PG-SKIP-Infrastructure.git
> ```

### Schritt 4.2 — Verzeichnisstruktur anlegen

```bash
mkdir -p ansible
mkdir -p argocd
mkdir -p apps/core/metallb
mkdir -p apps/core/traefik
mkdir -p apps/core/cert-manager
mkdir -p apps/core/longhorn
mkdir -p apps/services/ollama
mkdir -p apps/services/open-webui
mkdir -p apps/services/qdrant
mkdir -p apps/services/monitoring
```

Ergebnis:

```
PG-SKIP-Infrastructure/
├── Makefile
├── bootstrap.sh
├── .gitignore
├── README.md
├── ansible/
│   ├── site.yml
│   └── inventory.ini.example
├── argocd/
│   └── app-of-apps.yaml
└── apps/
    ├── core/                  # Layer 4 — Infrastruktur-Dienste
    │   ├── metallb/
    │   ├── traefik/
    │   ├── cert-manager/
    │   └── longhorn/
    └── services/              # Layer 5 — KI-Dienste
        ├── ollama/
        ├── open-webui/
        ├── qdrant/
        └── monitoring/
```

### Schritt 4.3 — `.gitignore` anlegen

```bash
cat > .gitignore << 'EOF'
# Lokale Konfigurationsdateien — nicht committen
ansible/inventory.ini
kubeconfig

# SSH-Keys
*.pem
*.key
id_ed25519*
!*.pub

# Umgebungsvariablen
.env
EOF
```

### Schritt 4.4 — `bootstrap.sh` anlegen

```bash
cat > bootstrap.sh << 'EOF'
#!/bin/bash
set -euo pipefail

echo "=== SKIP Bootstrap ==="
echo "Zielserver: $(grep ansible_host ansible/inventory.ini | awk '{print $2}' | cut -d= -f2)"
echo ""

ansible-playbook -i ansible/inventory.ini ansible/site.yml

echo ""
echo "=== Bootstrap abgeschlossen ==="
echo "Nächster Schritt: make kubeconfig"
EOF

chmod +x bootstrap.sh
git update-index --chmod=+x bootstrap.sh
```

> `git update-index --chmod=+x` setzt das Executable-Bit direkt in Git —
> nach jedem `git clone` hat die Datei automatisch die richtigen Rechte.

### Schritt 4.5 — `Makefile` anlegen

```bash
cat > Makefile << 'EOF'
.PHONY: bootstrap kubeconfig test argocd-bootstrap argocd-password argocd-ui

# k3s auf dem Server installieren (via Ansible)
bootstrap:
	./bootstrap.sh

# kubeconfig vom Server holen und lokal verfügbar machen
kubeconfig:
	scp gaming:/etc/rancher/k3s/k3s.yaml ./kubeconfig
	sed -i 's/127.0.0.1/172.17.204.135/g' ./kubeconfig
	@echo "kubeconfig gespeichert. Aktivieren mit:"
	@echo "  export KUBECONFIG=\$$(pwd)/kubeconfig"

# Cluster-Verbindung prüfen
test:
	KUBECONFIG=./kubeconfig kubectl get nodes

# ArgoCD + App-of-Apps installieren
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
	@echo "Cluster ist jetzt GitOps-fähig."
	@echo "Passwort abrufen: make argocd-password"

# ArgoCD Admin-Passwort anzeigen
argocd-password:
	@KUBECONFIG=./kubeconfig kubectl -n argocd get secret argocd-initial-admin-secret \
	  -o jsonpath="{.data.password}" | base64 -d
	@echo ""

# ArgoCD Web UI per Port-Forward öffnen
argocd-ui:
	@echo "ArgoCD UI: https://localhost:8080  (User: admin)"
	KUBECONFIG=./kubeconfig kubectl port-forward svc/argocd-server -n argocd 8080:443
EOF
```

### Schritt 4.6 — `ansible/inventory.ini.example` anlegen

```bash
cat > ansible/inventory.ini.example << 'EOF'
# VORLAGE — als ansible/inventory.ini kopieren und anpassen
# ansible/inventory.ini wird NICHT committet (steht in .gitignore)
#
# Jeder Admin trägt hier seinen eigenen Username und SSH-Key-Pfad ein.
# Der Key-Name entspricht dem lokal generierten SSH-Key (Schritt 2.1).

[server]
gaming ansible_host=172.17.204.135 ansible_user=<eigener-username> ansible_ssh_private_key_file=~/.ssh/id_ed25519_skip
EOF
```

### Schritt 4.7 — `ansible/site.yml` anlegen

```yaml
# ansible/site.yml
```

```bash
cat > ansible/site.yml << 'EOF'
---
- name: SKIP Bootstrap — k3s auf FH-Server installieren
  hosts: server
  become: true

  vars:
    k3s_version: "v1.35.4+k3s1"
    k3s_server_ip: "172.17.204.135"

  tasks:

    # --- System vorbereiten ---

    - name: Pakete aktualisieren
      apt:
        update_cache: yes
        upgrade: dist

    - name: Benötigte Pakete installieren
      apt:
        name:
          - curl
          - git
          - jq
          - open-iscsi
          - nfs-common
        state: present

    - name: Swap deaktivieren (sofort)
      command: swapoff -a
      when: ansible_swaptotal_mb > 0

    - name: Swap dauerhaft deaktivieren (fstab)
      replace:
        path: /etc/fstab
        regexp: '^([^#].*\sswap\s.*)$'
        replace: '# \1'

    - name: Kernel-Module laden
      modprobe:
        name: "{{ item }}"
        state: present
      loop:
        - br_netfilter
        - overlay

    - name: Kernel-Module beim Boot laden
      copy:
        dest: /etc/modules-load.d/k3s.conf
        content: |
          br_netfilter
          overlay

    - name: Sysctl-Parameter setzen
      sysctl:
        name: "{{ item.name }}"
        value: "{{ item.value }}"
        state: present
        reload: yes
      loop:
        - { name: "net.bridge.bridge-nf-call-iptables",  value: "1" }
        - { name: "net.bridge.bridge-nf-call-ip6tables", value: "1" }
        - { name: "net.ipv4.ip_forward",                 value: "1" }

    # --- k3s installieren ---

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

    - name: k3s-Dienst aktivieren und starten
      systemd:
        name: k3s
        enabled: yes
        state: started

    # --- kubeconfig lokal verfügbar machen ---

    - name: kubeconfig lokal für alle Admins zugänglich machen
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

    - name: Node-Status ausgeben
      command: k3s kubectl get nodes
      register: node_status
      changed_when: false

    - name: Node-Status anzeigen
      debug:
        msg: "{{ node_status.stdout_lines }}"
EOF
```

> **Hinweis zu `--disable servicelb` und `--disable traefik`:**
> servicelb wird durch MetalLB ersetzt, Traefik wird über ArgoCD als Helm-Chart deployt.
> Beide werden deshalb bei der k3s-Installation deaktiviert.

### Schritt 4.8 — `argocd/app-of-apps.yaml` anlegen

```bash
cat > argocd/app-of-apps.yaml << 'EOF'
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: app-of-apps
  namespace: argocd
spec:
  project: default

  source:
    repoURL: https://github.com/fhswf/PG-SKIP-Infrastructure.git
    targetRevision: main
    path: apps/core

  destination:
    server: https://kubernetes.default.svc
    namespace: argocd

  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
EOF
```

> Das App-of-Apps-Pattern: ArgoCD verwaltet sich selbst und deployt alle weiteren
> Apps aus `apps/core/` und `apps/services/` automatisch aus Git heraus.

### Schritt 4.9 — Dateien committen

```bash
git add .
git commit -m "feat: Bootstrap-Struktur anlegen (Makefile, Ansible, ArgoCD)"
git push
```

---

## Phase 5 — Bootstrap ausführen (auf dem Admin-Rechner)

> **Hinweis zu "lokal":** Alle Befehle in Phase 5 werden auf dem **eigenen Rechner**
> des jeweiligen Admins ausgeführt (macOS, Linux oder WSL2) — nicht auf dem FH-Server.
> Ansible, kubectl und make verbinden sich von dort aus per SSH bzw. über die kubeconfig
> mit dem Server `gaming` (172.17.204.135).

### Schritt 5.1 — `inventory.ini` befüllen

```bash
cp ansible/inventory.ini.example ansible/inventory.ini
```

Eigenen Username und Key-Pfad eintragen:

```ini
[server]
gaming ansible_host=172.17.204.135 ansible_user=<eigener-username> ansible_ssh_private_key_file=~/.ssh/id_ed25519_skip
```

> Jeder Admin trägt seinen eigenen Username und Key ein.
> `inventory.ini` wird nicht committet — steht in `.gitignore`.

### Schritt 5.2 — Ansible-Verbindung testen

```bash
ansible all -i ansible/inventory.ini -m ping
```

Erwartete Ausgabe:

```
gaming | SUCCESS => { "ping": "pong" }
```

### Schritt 5.3 — Bootstrap ausführen

```bash
make bootstrap
```

Das Ansible-Playbook erledigt folgende Schritte automatisch auf dem Server:

| Phase | Was passiert |
|---|---|
| System vorbereiten | Pakete aktualisieren, Swap deaktivieren, Kernel-Module, Sysctl |
| Pakete installieren | curl, git, jq, open-iscsi, nfs-common |
| k3s installieren | Version `v1.35.4+k3s1`, servicelb und Traefik deaktiviert |
| Warten | Bis k3s API auf Port 6443 antwortet |
| Abschluss | kubeconfig lesbar machen, Node-Status ausgeben |

> ⚠ **Wichtig:** Nach diesem Schritt ist k3s betriebsbereit,
> aber der Cluster ist noch **nicht GitOps-fähig**.
> ArgoCD fehlt noch — erst nach `make argocd-bootstrap` synchronisiert der Cluster aus Git.

### Schritt 5.4 — kubeconfig aktivieren

Das Ansible-Playbook hat die kubeconfig bereits automatisch geholt und die Server-IP
eingetragen. Die Datei liegt nach dem Bootstrap unter `./kubeconfig` im Repo-Root.

> **Wie es funktioniert:** `fetch` in `site.yml` holt `/etc/rancher/k3s/k3s.yaml`
> vom Server nach `{{ playbook_dir }}/../kubeconfig` — also ins Repo-Root, nicht
> ins `ansible/`-Unterverzeichnis. Danach ersetzt `replace` die interne Adresse
> `127.0.0.1` durch die Server-IP `172.17.204.135` (Variable `k3s_server_ip`).

`make kubeconfig` ist in diesem Fall ein optionaler manueller Fallback falls der
Ansible-Schritt übersprungen wurde:

```bash
make kubeconfig
```

kubeconfig für die aktuelle Shell-Session aktivieren:

```bash
# bash / zsh
export KUBECONFIG=$(pwd)/kubeconfig

# fish
set -x KUBECONFIG (pwd)/kubeconfig
```

Dauerhaft in der Shell-Konfiguration eintragen:

**bash** (`~/.bashrc`):
```bash
echo 'export KUBECONFIG=~/PG-SKIP-Infrastructure/kubeconfig' >> ~/.bashrc
source ~/.bashrc
```

**zsh** (`~/.zshrc`):
```bash
echo 'export KUBECONFIG=~/PG-SKIP-Infrastructure/kubeconfig' >> ~/.zshrc
source ~/.zshrc
```

**fish** (`~/.config/fish/config.fish`):
```bash
echo 'set -x KUBECONFIG ~/PG-SKIP-Infrastructure/kubeconfig' >> ~/.config/fish/config.fish
source ~/.config/fish/config.fish
```

> Die kubeconfig enthält Zugangsdaten für den Cluster und wird **nicht committet**
> — steht in `.gitignore`.

### Schritt 5.5 — Cluster prüfen

```bash
make test
```

Erwartete Ausgabe:

```
NAME     STATUS   ROLES           AGE   VERSION
gaming   Ready    control-plane   Xm    v1.35.4+k3s1
```

### Schritt 5.6 — ArgoCD deployen

```bash
make argocd-bootstrap
```

Dieser Schritt installiert ArgoCD im Namespace `argocd` und deployt die `app-of-apps.yaml`.
Ab diesem Moment übernimmt ArgoCD die Synchronisation — alle weiteren Änderungen
werden über Git deployt.

```
⚠ KRITISCHER SCHRITT:
Erst nach make argocd-bootstrap ist der Cluster GitOps-fähig.
Bis dahin werden Git-Pushes nicht automatisch synchronisiert.
```

### Schritt 5.7 — ArgoCD prüfen

```bash
kubectl get applications -n argocd
```

Erwartete Ausgabe:

```
NAME          SYNC STATUS   HEALTH STATUS
app-of-apps   Synced        Healthy
```

**ArgoCD-Passwort abrufen:**

```bash
make argocd-password
```

**ArgoCD Web UI öffnen:**

```bash
make argocd-ui
```

> **Wie der Zugriff funktioniert:** ArgoCD läuft als Pod auf dem Server `gaming`
> (172.17.204.135) im Kubernetes-Cluster — nicht auf dem lokalen Rechner.
> `make argocd-ui` startet `kubectl port-forward`, der einen temporären Tunnel vom
> Admin-Rechner zum ArgoCD-Service im Cluster aufbaut:
>
> ```
> Browser (Admin-Rechner)
>   → localhost:8080
>   → kubectl port-forward  (Tunnel, läuft lokal)
>   → argocd-server Service im Cluster
>   → Pod auf gaming (172.17.204.135)
> ```
>
> Solange der Befehl läuft, ist die UI erreichbar. Mit `Ctrl+C` wird der Tunnel
> beendet. Später erhält ArgoCD über Traefik einen permanenten Ingress und ist
> direkt über eine URL erreichbar — dann entfällt der Port-Forward.

Im Browser öffnen: `https://localhost:8080` | User: `admin`

> Aktueller Befehl zum Passwort-Abruf (verwendet in `make argocd-password`):
> ```bash
> kubectl -n argocd get secret argocd-initial-admin-secret \
>   -o jsonpath="{.data.password}" | base64 -d
> ```
> Alternativ: `argocd admin initial-password -n argocd`

### Schritt 5.8 — GitOps-Workflow testen

```bash
git add .
git commit -m "test: ArgoCD sync prüfen"
git push
```

Sync beobachten:

```bash
kubectl get applications -n argocd -w
```

---

## Bekannte Probleme & Hinweise

| Problem | Ursache | Lösung |
|---|---|---|
| Server nicht erreichbar | EduVPN nicht aktiv | VPN verbinden, dann erneut versuchen |
| `ansible: command not found` | Ansible nicht installiert | Lokale Voraussetzungen (Phase 1) nachholen |
| `kubectl: command not found` | kubectl nicht installiert | Phase 1 nachholen |
| `KUBECONFIG` nicht gesetzt | Umgebungsvariable fehlt | `export KUBECONFIG=$(pwd)/kubeconfig` |
| `Permission denied` SSH | Falscher Key oder Username | `inventory.ini` prüfen |
| `docker.socket` startet Docker neu | Nur `docker.service` gestoppt | Immer beide stoppen: `docker.service docker.socket` |
| kubectl-Version stimmt nicht | Versionskonflikt mit k3s | kubectl Minor-Version muss zu k3s passen (`v1.35.x`) |
| `make kubeconfig` schlägt fehl | kubeconfig noch nicht lesbar | Ansible-Playbook prüfen ob `mode: 0644` gesetzt wurde |

---

## Versionen synchron halten

Wenn k3s auf dem Server geupdatet wird, muss kubectl lokal angepasst werden.

```bash
# k3s-Version auf dem Server prüfen
ssh gaming "k3s --version"

# kubectl-Version lokal prüfen
kubectl version --client
```

kubectl manuell aktualisieren (Linux/WSL2):

```bash
curl -LO "https://dl.k8s.io/release/v1.35.0/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
rm kubectl
```

---


> **Hinweis:** Ein `skip-tools` Docker Container für einheitliche Tool-Versionen
> ist als spätere Ergänzung geplant — sobald der Bootstrap-Prozess stabil läuft.

