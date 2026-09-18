# FH-Server: Setup-Anleitung

> Team 1 – AI Infrastructure & Operations | Stand: 15.09.2026

---

## Änderungen (15.09.2026)

- **Sealed Secrets eingeführt:** Nach Abwägung von Sealed Secrets, External
  Secrets Operator und SOPS fiel die Wahl auf Sealed Secrets (Bitnami) —
  läuft komplett im eigenen Cluster, kein externes Vault-Backend nötig.
  Neue ArgoCD-Application (`argocd/core/sealed-secrets.yaml`), Manifeste
  unter `apps/core/sealed-secrets/` (HelmChart-CRD, Chart `2.20.0` /
  Controller `v0.40.0`). Details: siehe Phase 11 unten.
- **Secrets-Strategie damit teilweise revidiert:** Die frühere Entscheidung
  „Secrets bleiben vorerst manuell“ (siehe Eintrag 01.09.2026) gilt ab
  sofort nur noch für bereits bestehende Secrets (`litellm-secret`,
  `minio-secret`) — deren Migration ist als offener Punkt in Phase 11
  dokumentiert, da ihre Klartextwerte nirgends gespeichert und daher nicht
  automatisiert übernehmbar sind. Alle neuen Secrets sollen ab jetzt als
  `SealedSecret` committet werden.

## Änderungen (05.09.2026)

Nacharbeit aus einer formalen Repo-Inspektion (Protokoll liegt außerhalb
dieses Repos in der Team-1-internen Ablage):

- **Zielhost generalisiert (Makefile + Manifeste):** Der Änderungslog vom
  06.08.2026 behauptete, das Setup sei „für beliebige Zielhosts“
  generalisiert — tatsächlich betraf das nur `ansible/site.yml`. Jetzt sind
  auch `make kubeconfig` (`SKIP_SSH_HOST`/`SKIP_SERVER_IP` in `.env`, siehe
  `.env.example`) und die IngressRoute-Hostnamen von ArgoCD/Harbor
  (zentrale Quelle: `apps/core/cluster-host/kustomization.yaml`, per
  Kustomize `replacements` in beide IngressRoutes eingespeist)
  konfigurierbar, statt an >8 Stellen hartcodiert zu sein. **Nicht
  abgedeckt:** `externalURL` in `apps/core/harbor/helmrelease.yaml` bleibt
  bewusst hartcodiert (Begründung im Kommentar dort) und muss bei einem
  Host-Wechsel manuell nachgezogen werden.
- **Harbor `externalURL` korrigiert:** README dokumentierte
  `http://…:30080`, tatsächlich deployt ist `https://…:30443` (siehe
  Phase 8.5). Die Anleitung in Schritt 8.1 wurde an den tatsächlichen,
  funktionierenden Stand angepasst.
- **`ansible/site.yml`-Codeblock entfernt:** Schritt 4.8 dupliziert die
  Playbook-Inhalte nicht mehr als Codeblock (der war nach mehreren
  Weiterentwicklungen der echten Datei veraltet), sondern verweist direkt
  auf `ansible/site.yml`.
- **Tote Verweise auf `tasks/` entfernt:** Vier Stellen (README,
  `apps/services/litellm/README.md`) verwiesen auf einen `tasks/`-Ordner,
  der nie Teil dieses Repos war (lokale Team-1-Ablage). Verweise entfernt
  bzw. auf projektinterne Nachverfolgung umformuliert.
- **`apps/core/README.md` und `apps/services/README.md`** waren leere
  Platzhalter — jetzt mit einer kurzen Übersicht befüllt.
- **Kleinere Aufräumarbeiten:** widersprüchlicher Docker-Compose-Kommentar
  in `ansible/site.yml` entfernt (Setup läuft ohne Docker); Übersichtstabelle
  „Wo laufen welche Befehle?“ um die Server-seitigen Schritte aus Phase 6.1
  und 8.3 ergänzt; Warnhinweis zum Harbor-Admin-Passwort (Schritt 8.6)
  verstärkt.
- **MinIO als GitOps-Application:** MinIO (S3-kompatibler Objektspeicher)
  wurde ebenfalls aus PG-SKIP-Platform übernommen, nach demselben Muster wie
  LiteLLM: ArgoCD-Application (`argocd/core/minio.yaml`), Manifeste unter
  `apps/services/minio/` (StatefulSet mit PVC, Service via Kustomize),
  eigener Namespace `minio`, kein externer Ingress (`ClusterIP`). Details
  und Betrieb: siehe Phase 10 unten sowie `apps/services/minio/README.md`.
  Secret `minio-secret` wird wie bei LiteLLM manuell angelegt, nicht
  committet.

## Änderungen (01.09.2026)

Seit der letzten Version der Anleitung wurden folgende Punkte überarbeitet:

- **Umgebungen via `.env`:** Das Makefile liest jetzt eine `.env`-Datei
  (Vorlage: `.env.example`) mit der Variable `SKIP_ENV`. Erlaubte Werte:
  `productive`, `development`, `test`. Ein neues `check-env`-Target
  validiert den Wert und bricht mit klarer Fehlermeldung ab, falls er
  fehlt oder ungültig ist. Bei `SKIP_ENV=development` überspringt
  `make bootstrap` das Ansible-Provisioning, da hier der bestehende
  Server genutzt wird statt ein eigener Server aufgesetzt zu werden.
  `productive` und `test` durchlaufen aktuell denselben, vollen Ablauf
  (Ansible + kubeconfig + ArgoCD) — die weitere Differenzierung ist noch
  offen (Team-1-intern nachverfolgt, nicht Teil dieses Repos).
- **LiteLLM als GitOps-Application:** LiteLLM (AI-Gateway/Proxy) wurde aus
  PG-SKIP-Platform übernommen und läuft jetzt als reguläre
  ArgoCD-Application (`argocd/core/litellm.yaml`) über das bestehende
  App-of-Apps, analog zu Traefik/Harbor. Manifeste liegen unter
  `apps/services/litellm/` (Deployment, Service, ConfigMap via Kustomize),
  eigener Namespace `litellm`, kein externer Ingress (`ClusterIP`). Details
  und Betrieb: siehe Phase 9 unten sowie `apps/services/litellm/README.md`.
- **Secrets bleiben vorerst manuell:** Für LiteLLM (`litellm-secret`,
  `LITELLM_MASTER_KEY`) wurde entschieden, noch kein Secrets-Tool
  (SOPS/Sealed Secrets/External Secrets Operator) einzuführen — Secrets
  werden bis auf Weiteres manuell per `kubectl create secret` angelegt und
  nie committet. Gilt repo-weit, nicht nur für LiteLLM.

## Änderungen (06.08.2026)

Seit der letzten Version der Anleitung wurden folgende Punkte überarbeitet:

- **GitOps-Struktur refactored:** `argocd/app-of-apps.yaml` heißt jetzt
  `argocd/core-apps.yaml` (Application `core-apps` statt `app-of-apps`) und
  zeigt auf `argocd/core/`. Die einzelnen Core-Applications
  (`argocd/harbor.yaml`, `argocd/traefik.yaml`) liegen jetzt unter
  `argocd/core/`. Neu dazugekommen: `argocd/core/argocd.yaml` — ArgoCD
  verwaltet sich damit selbst als eigene Application.
- **ArgoCD hat jetzt ein eigenes Ingress:** `apps/core/argocd/ingressroute.yaml`
  und `apps/core/argocd/configmap.yaml` machen die ArgoCD-UI unter
  `https://argocd.172-17-204-135.sslip.io:30443` erreichbar (analog zu
  Harbor). Der bisherige Port-Forward-Weg funktioniert weiterhin als
  Fallback.
- **Makefile:** `make argocd-ui` heißt jetzt `make argocd-port-forward`
  (nur noch als Debug/Fallback gedacht) und nutzt `http://localhost:8080`
  statt `https`. `make argocd-bootstrap` wartet zusätzlich, bis die
  `core-apps`-Application synchronisiert ist, und startet ArgoCD danach neu.
- **k3s-Bootstrap generalisiert:** `ansible/site.yml` verwendet jetzt
  `{{ ansible_host }}` statt einer hartcodierten Server-IP — das Playbook
  funktioniert damit für beliebige Zielhosts, nicht nur für `172.17.204.135`.
- **Harbor:** Die explizite `logs:`-Konfiguration in
  `apps/core/harbor/helmrelease.yaml` wurde entfernt (ungültige Felder für
  den verwendeten Helm-Chart).

---

## Voraussetzung

✓ EduVPN aktiv — der Server `gaming` (172.17.204.135) ist nur über EduVPN erreichbar.

---

## Übersicht: Wo laufen welche Befehle?

| Schritt | Wo ausführen |
|---|---|
| Server aktualisieren, Docker stoppen, k3s reset (Phase 3) | SSH auf FH-Server |
| Deploy Key als Secret hinterlegen (Phase 6.1) | SSH auf FH-Server |
| containerd für HTTPS-Registry konfigurieren (Phase 8.3) | SSH auf FH-Server |
| Repo klonen, Ansible, kubectl, make (alle übrigen Schritte) | Lokaler Rechner (Terminal) |

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
          → .env anlegen und SKIP_ENV setzen (productive/development/test)
          → make bootstrap     (k3s via Ansible installieren,
                                 bei SKIP_ENV=development übersprungen)
          → make kubeconfig    (kubeconfig lokal verfügbar machen)
          → make test          (Cluster-Verbindung prüfen)
          → make argocd-bootstrap  (ArgoCD + GitOps-Applications installieren)
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
     ↓
Phase 9:  LiteLLM deployen
          → AI-Gateway via ArgoCD (Kustomize, apps/services/litellm)
          → litellm-secret manuell anlegen (LITELLM_MASTER_KEY)
          ✓ Health-Endpoint und Chat-Completion gegen Placeholder-Modell
     ↓
Phase 10: MinIO deployen
          → S3-Objektspeicher via ArgoCD (Kustomize, apps/services/minio)
          → minio-secret manuell anlegen (MINIO_ROOT_USER/MINIO_ROOT_PASSWORD)
          ✓ Health-Endpoint und Web-Console erreichbar
     ↓
Phase 11: Sealed Secrets installieren
          → Controller via ArgoCD (HelmChart CRD, apps/core/sealed-secrets)
          → kubeseal-CLI installieren, Schlüssel-Backup sichern
          ✓ Secrets künftig als SealedSecret committebar statt manuell
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
> (`~/PG-SKIP-Infrastructure`), nicht ins Windows-Dateisystem (`/mnt/c/...`).

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
> Zugang zum FH-Server `gaming`. Dieser Key (`id_ed25519_github`) ist für den Zugang
> zu GitHub. Beide müssen separat eingerichtet werden.

### Schritt 4.2 — Repo klonen

```bash
git clone git@github.com:fhswf/PG-SKIP-Infrastructure.git
cd PG-SKIP-Infrastructure
```

> **Tipp:** Falls das Repo bereits über HTTPS geklont wurde, nachträglich auf SSH umstellen:
>
> ```bash
> git remote set-url origin git@github.com:fhswf/PG-SKIP-Infrastructure.git
> ```

### Schritt 4.3 — Verzeichnisstruktur anlegen

```bash
mkdir -p ansible
mkdir -p argocd/core
mkdir -p apps/core/argocd
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

Aktuelle Fassung: [`.gitignore`](.gitignore) im Repo-Root (nicht als
Codeblock dupliziert, siehe Hinweis zu `ansible/site.yml` in Schritt 4.8).
Deckt u. a. Ansible-Inventory, kubeconfig, SSH-Keys, `.env` und
Secrets-Dateien ab.

### Schritt 4.5 — `bootstrap.sh` anlegen

Aktuelle Fassung: [`bootstrap.sh`](bootstrap.sh) im Repo-Root — ruft
`ansible-playbook` mit `ansible/inventory.ini` und `ansible/site.yml` auf.
Danach ausführbar machen:

```bash
chmod +x bootstrap.sh
git update-index --chmod=+x bootstrap.sh
```

### Schritt 4.6 — `Makefile` anlegen

Wie bei `ansible/site.yml` (Schritt 4.8) wird der Inhalt hier **nicht** als
Codeblock dupliziert — frühere Duplikate in dieser Anleitung liefen nach
Weiterentwicklung der Datei auseinander. Die aktuell gültige Fassung liegt
in [`Makefile`](Makefile) im Repo-Root; Targets: `bootstrap`, `kubeconfig`,
`test`, `argocd-bootstrap`, `argocd-password`, `argocd-port-forward`,
`check-env`.

> **Hinweis:** Die ArgoCD-UI ist nach dem Bootstrap außerdem direkt über
> Ingress erreichbar (siehe `apps/core/argocd/ingressroute.yaml`), der
> Port-Forward ist nur noch als Fallback gedacht.
>
> **Hinweis:** Zielserver (`SKIP_SSH_HOST`, `SKIP_SERVER_IP`) sind über
> `.env` konfigurierbar (siehe `.env.example`), Defaults entsprechen dem
> aktuellen FH-Server.

### Schritt 4.6a — `.env.example` anlegen

Aktuelle Fassung: [`.env.example`](.env.example) im Repo-Root — steuert
`SKIP_ENV` (`productive`/`development`/`test`) sowie `SKIP_SSH_HOST`/
`SKIP_SERVER_IP` für den Zielserver (siehe Schritt 4.9a).

> `.env` selbst ist über `.gitignore` ausgeschlossen (analog
> `ansible/inventory.ini`) — nur `.env.example` wird committet.

### Schritt 4.7 — `ansible/inventory.ini.example` anlegen

```ini
[server]
gaming ansible_host=172.17.204.135 ansible_user=<eigener-username> ansible_ssh_private_key_file=~/.ssh/id_ed25519_skip
```

### Schritt 4.8 — `ansible/site.yml` anlegen

Die vollständige, aktuell gültige Fassung des Playbooks liegt in der Datei
[`ansible/site.yml`](ansible/site.yml) — sie wird hier bewusst **nicht** als
Codeblock dupliziert, da frühere Duplikate in dieser Anleitung nach
Weiterentwicklung der Datei veraltet sind (Swap-Deaktivierung, Kernel-Module,
Sysctl-Parameter, `iscsid`-Aktivierung und `--tls-san`-Flag kamen später
dazu, ohne dass der Codeblock hier nachgezogen wurde). Für Schritt 4.8 die
Datei `ansible/site.yml` direkt aus dem Repo übernehmen bzw. bei einem
Neuaufbau von dort kopieren.

> **Hinweis:** `--disable servicelb` und `--disable traefik` — beide werden über
> ArgoCD deployt und deshalb bei der k3s-Installation deaktiviert.
>
> **Hinweis:** `k3s_server_ip` nutzt `{{ ansible_host }}` aus dem
> Inventory statt einer hartcodierten IP — das Playbook funktioniert damit
> für beliebige Zielhosts, nicht nur für `gaming` / `172.17.204.135`.

### Schritt 4.9 — `argocd/core-apps.yaml` anlegen

Aktuelle Fassung: [`argocd/core-apps.yaml`](argocd/core-apps.yaml) — die
App-of-Apps (`source.path: argocd/core`), die diesen Ordner überwacht und
seinen Inhalt automatisch synchronisiert.

> Die einzelnen Core-Applications (`argocd.yaml`, `harbor.yaml`,
> `traefik.yaml`, `litellm.yaml`) liegen unter `argocd/core/`.

### Schritt 4.9a — ArgoCD-Ingress und Self-Management einrichten

Damit ArgoCD sich selbst über GitOps verwaltet und die UI per Ingress statt
nur per Port-Forward erreichbar ist, werden vier weitere Dateien angelegt —
aktuelle Fassungen jeweils direkt im Repo, hier nicht dupliziert (siehe
Hinweis zu `ansible/site.yml` in Schritt 4.8):

| Datei | Zweck |
|---|---|
| [`argocd/core/argocd.yaml`](argocd/core/argocd.yaml) | ArgoCD verwaltet sich selbst als eigene Application (`source.path: apps/core/argocd`) |
| [`apps/core/argocd/configmap.yaml`](apps/core/argocd/configmap.yaml) | aktiviert `server.insecure`, damit Traefik die TLS-Terminierung übernehmen kann |
| [`apps/core/argocd/ingressroute.yaml`](apps/core/argocd/ingressroute.yaml) | Traefik IngressRoute für die ArgoCD-UI |
| [`apps/core/argocd/kustomization.yaml`](apps/core/argocd/kustomization.yaml) | bindet `../cluster-host` ein und ersetzt den Host-Teil in der IngressRoute oben per Kustomize `replacements` |

> **Zentraler Cluster-Host:** Die IngressRoute oben (und die von Harbor,
> Phase 8) beziehen den Hostnamen nicht mehr direkt, sondern über
> [`apps/core/cluster-host/kustomization.yaml`](apps/core/cluster-host/kustomization.yaml) —
> eine `configMapGenerator`-Datei, die den Wert `172-17-204-135` einmalig
> definiert. Bei einem Wechsel des Zielservers **nur diese eine Datei**
> ändern (siehe Kommentar darin) statt jede IngressRoute einzeln. Beide
> Ordner (`apps/core/argocd`, `apps/core/harbor`) binden sie über ihre
> eigene `kustomization.yaml` mit `resources: [../cluster-host, …]` und
> Kustomize `replacements` ein.

> Diese Dateien werden von `core-apps` automatisch aus Git synchronisiert
> — kein manuelles `kubectl apply` nötig. Da die ConfigMap-Änderung einen
> Neustart des ArgoCD-Servers erfordert, führt `make argocd-bootstrap`
> (Phase 5.6) diesen Neustart bereits automatisch per `kubectl rollout
> restart` aus.

### Schritt 4.10 — Dateien committen

```bash
git add .
git commit -m "feat: Bootstrap-Struktur anlegen (Makefile, Ansible, ArgoCD)"
git push
```

---

## Phase 5 — Bootstrap ausführen (auf dem Admin-Rechner)

### Schritt 5.0 — `.env` anlegen

```bash
cp .env.example .env
# SKIP_ENV nach Bedarf setzen: productive | development | test
```

> Bei `SKIP_ENV=development` wird in Schritt 5.3 kein eigener Server
> provisioniert — dafür muss `ansible/inventory.ini` trotzdem existieren
> (die anderen Targets greifen weiterhin darauf zu), Schritt 5.2 kann aber
> übersprungen werden, wenn kein Ansible-Zugriff nötig ist.

### Schritt 5.1 — `inventory.ini` befüllen

```bash
cp ansible/inventory.ini.example ansible/inventory.ini
# Eigenen Username eintragen
```

### Schritt 5.2 — Ansible-Verbindung testen

```bash
ansible all -i ansible/inventory.ini -m ping
```

Erwartete Ausgabe: `gaming | SUCCESS => { "ping": "pong" }`

### Schritt 5.3 — Bootstrap ausführen

```bash
make bootstrap
```

> ⚠ Nach diesem Schritt läuft k3s, aber der Cluster ist noch **nicht GitOps-fähig**.
> Erst nach `make argocd-bootstrap` synchronisiert ArgoCD aus Git.
>
> Bei `SKIP_ENV=development` überspringt dieser Schritt das
> Ansible-Provisioning (Meldung „Ansible-Provisioning wird übersprungen“) —
> es wird davon ausgegangen, dass der Server bereits läuft.

### Schritt 5.4 — kubeconfig aktivieren

```bash
# bash / zsh
export KUBECONFIG=$(pwd)/kubeconfig

# fish
set -x KUBECONFIG (pwd)/kubeconfig

# Dauerhaft (fish):
echo 'set -x KUBECONFIG ~/Development/SKIP/PG-SKIP-Infrastructure/kubeconfig' >> ~/.config/fish/config.fish
source ~/.config/fish/config.fish
```

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

> **Wichtig:** `--server-side` wird intern verwendet weil ArgoCD CRDs zu groß
> für normales `kubectl apply` sind.

### Schritt 5.7 — ArgoCD UI öffnen

```bash
make argocd-password        # Admin-Passwort anzeigen
make argocd-port-forward    # Port-Forward starten (Fallback, falls Ingress nicht erreichbar)
```

Browser (per Ingress, empfohlen): `https://argocd.172-17-204-135.sslip.io:30443` | User: `admin`
Browser (per Port-Forward, Fallback): `http://localhost:8080` | User: `admin`

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
ssh gaming

sudo kubectl -n argocd create secret generic pg-skip-repo \
  --from-literal=type=git \
  --from-literal=url=git@github.com:fhswf/PG-SKIP-Infrastructure.git \
  --from-file=sshPrivateKey=/opt/skip/.ssh/deploy_key

sudo kubectl -n argocd label secret pg-skip-repo \
  argocd.argoproj.io/secret-type=repository
```

> **Wichtig:** Niemals ins Repo committen — enthält den privaten SSH-Key.

### Schritt 6.2 — ArgoCD Applications auf SSH-URL patchen

```bash
sudo kubectl patch application core-apps -n argocd \
  --type merge \
  -p '{"spec":{"source":{"repoURL":"git@github.com:fhswf/PG-SKIP-Infrastructure.git"}}}'

sudo kubectl patch application traefik -n argocd \
  --type merge \
  -p '{"spec":{"source":{"repoURL":"git@github.com:fhswf/PG-SKIP-Infrastructure.git"}}}'
```

### Schritt 6.3 — YAML-Dateien im Repo korrigieren

```bash
sed -i 's|https://github.com/fhswf/PG-SKIP-Infrastructure.git|git@github.com:fhswf/PG-SKIP-Infrastructure.git|g' argocd/*.yaml argocd/core/*.yaml

git add .
git commit -m "fix: use SSH URL for ArgoCD repo references"
git push
```

> **Regel:** In allen `argocd/*.yaml` immer SSH-URL verwenden:
> `git@github.com:fhswf/PG-SKIP-Infrastructure.git`

---

## Phase 7 — Traefik deployen

Traefik läuft als **NodePort** — kein MetalLB erforderlich.

| Port | Protokoll | Erreichbar unter |
|------|-----------|-----------------|
| 30080 | HTTP | `http://172.17.204.135:30080` |
| 30443 | HTTPS | `https://172.17.204.135:30443` |

### Schritt 7.1 — Manifeste anlegen

Aktuelle Fassungen jeweils im Repo, hier nicht dupliziert (siehe Hinweis zu
`ansible/site.yml` in Schritt 4.8):

| Datei | Zweck |
|---|---|
| [`apps/core/traefik/namespace.yaml`](apps/core/traefik/namespace.yaml) | Namespace `traefik` |
| [`apps/core/traefik/helmrelease.yaml`](apps/core/traefik/helmrelease.yaml) | Helm-Chart via `HelmChart`-CRD, `NodePort` 30080/30443, Dashboard aktiviert |
| [`argocd/core/traefik.yaml`](argocd/core/traefik.yaml) | ArgoCD-Application, `source.path: apps/core/traefik` |

### Schritt 7.2 — Pushen und ArgoCD Application anlegen

> Auf dem **lokalen Rechner** ausführen.

```bash
git add .
git commit -m "feat: Add Traefik ingress controller"
git push

kubectl apply -f argocd/core/traefik.yaml
```

### Schritt 7.3 — Deployment prüfen

```bash
kubectl get application traefik -n argocd
kubectl get pods -n traefik
kubectl get svc -n traefik
```

Erreichbarkeit testen:

```bash
curl http://172.17.204.135:30080
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

> **Hostname:** `harbor.172-17-204-135.sslip.io` löst automatisch auf `172.17.204.135`
> auf — kein `/etc/hosts` Eintrag nötig, solange Internetzugang besteht.

> **Docker Push/Pull:** Läuft über Port **30443** (HTTPS) mit selbstsigniertem
> Traefik-Zertifikat. Docker muss die Registry als `insecure-registry` konfiguriert
> werden — dann akzeptiert Docker das Zertifikat.

### Schritt 8.1 — Manifeste anlegen

> Auf dem **lokalen Rechner** ausführen.

Aktuelle Fassungen jeweils im Repo, hier nicht dupliziert (siehe Hinweis zu
`ansible/site.yml` in Schritt 4.8):

| Datei | Zweck |
|---|---|
| [`apps/core/harbor/namespace.yaml`](apps/core/harbor/namespace.yaml) | Namespace `harbor` |
| [`apps/core/harbor/helmrelease.yaml`](apps/core/harbor/helmrelease.yaml) | Helm-Chart via `HelmChart`-CRD. Wichtigste Werte: `externalURL` (Traefik-IngressRoute, HTTPS/30443 — muss manuell synchron zu `apps/core/cluster-host/` gehalten werden, siehe Kommentar in der Datei), `expose.type: clusterIP` (Harbor-eigener Ingress verursacht Probleme mit Docker Push über Traefik), `harborAdminPassword` (Default — **sofort nach Schritt 8.6 ändern**), `registry.relativeurls: true` (korrekte Traefik-Weiterleitung) |
| [`apps/core/harbor/kustomization.yaml`](apps/core/harbor/kustomization.yaml) | bindet `../cluster-host` (siehe Schritt 4.9a) per Kustomize `replacements` in die `IngressRoute` ein |
| [`apps/core/harbor/ingressroute.yaml`](apps/core/harbor/ingressroute.yaml) | Traefik IngressRoute statt Harbor-eigenem Ingress. `websecure` + `tls: {}` stellt Harbor über HTTPS bereit (selbstsigniertes Zertifikat); jeder Pfad als eigene Route mit `priority: 100`, da Traefik v3 nur einen Pfad pro `PathPrefix`-Regel erlaubt |
| [`argocd/core/harbor.yaml`](argocd/core/harbor.yaml) | ArgoCD-Application, `source.path: apps/core/harbor` |

### Schritt 8.2 — Pushen und ArgoCD Application anlegen

> Auf dem **lokalen Rechner** ausführen.

```bash
git add .
git commit -m "feat: Add Harbor container registry with Traefik IngressRoute"
git push

kubectl apply -f argocd/core/harbor.yaml
```

> **fish shell:** `set -x KUBECONFIG ~/Development/SKIP/PG-SKIP-Infrastructure/kubeconfig`

### Schritt 8.3 — containerd für HTTPS-Registry konfigurieren

> Auf dem **Server** ausführen.

containerd muss Harbor als vertrauenswürdige Registry kennen:

```bash
ssh gaming
sudo nano /etc/rancher/k3s/registries.yaml
```

Inhalt:

```yaml
mirrors:
  "harbor.172-17-204-135.sslip.io:30443":
    endpoint:
      - "https://harbor.172-17-204-135.sslip.io:30443"
```

k3s neu starten:

```bash
sudo systemctl restart k3s
```

Warten bis k3s wieder bereit:

```bash
kubectl get nodes
# Erwartung: gaming   Ready
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

Browser: `https://harbor.172-17-204-135.sslip.io:30443`

> Traefik zeigt eine Zertifikatswarnung (selbstsigniertes Zertifikat) — einmalig bestätigen.

| Feld | Wert |
|------|------|
| User | `admin` |
| Passwort | `Harbor12345` (Default — sofort ändern!) |

### Schritt 8.6 — Admin-Passwort ändern

> ⚠ **Sicherheitshinweis:** `apps/core/harbor/helmrelease.yaml` legt beim
> Deploy das Passwort `Harbor12345` im Klartext fest (Helm-Chart-Standard,
> nichts erzwingt danach einen Wechsel). Solange dieser Schritt nicht
> durchgeführt wurde, kann sich **jede Person mit Lesezugriff auf dieses
> Repo** als Harbor-Admin anmelden. Diesen Schritt daher **unmittelbar**
> nach dem ersten erfolgreichen Deployment durchführen, nicht erst bei
> Bedarf.

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
  "insecure-registries": ["harbor.172-17-204-135.sslip.io:30443"]
}
```

Falls die Datei leer ist:

```json
{
  "insecure-registries": ["harbor.172-17-204-135.sslip.io:30443"]
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
  "insecure-registries": ["harbor.172-17-204-135.sslip.io:30443"]
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
docker login harbor.172-17-204-135.sslip.io:30443
docker tag hello-world harbor.172-17-204-135.sslip.io:30443/skip_applications/hello-world:latest
docker push harbor.172-17-204-135.sslip.io:30443/skip_applications/hello-world:latest
docker pull harbor.172-17-204-135.sslip.io:30443/skip_applications/hello-world:latest
```

Image in Harbor UI prüfen: `Projects → skip_applications → Repositories`

**Vom Server aus (Fallback):**

```bash
ssh gaming

sudo nano /etc/docker/daemon.json
# insecure-registries: ["harbor.172-17-204-135.sslip.io:30443"] eintragen

sudo systemctl restart docker
sudo docker login harbor.172-17-204-135.sslip.io:30443
sudo docker pull hello-world
sudo docker tag hello-world harbor.172-17-204-135.sslip.io:30443/skip_applications/hello-world:latest
sudo docker push harbor.172-17-204-135.sslip.io:30443/skip_applications/hello-world:latest
```

---

## Phase 9 — LiteLLM deployen

LiteLLM ist ein AI-Gateway/Proxy (OpenAI-kompatible API vor beliebigen
Modell-Backends), übernommen aus PG-SKIP-Platform als Pilot für die
Überführung von Platform-Services ins GitOps-Repo. Läuft rein intern
(`ClusterIP`, kein Ingress).

> Manifeste liegen unter `apps/services/litellm/` (Kustomize: Deployment,
> Service, ConfigMap). Die ArgoCD-`Application` (`argocd/core/litellm.yaml`)
> wird automatisch vom bestehenden App-of-Apps (`core-apps`) übernommen —
> kein separater `make`-Schritt nötig, sobald die Datei auf `main` liegt.

### Schritt 9.1 — `litellm-secret` anlegen

> Muss **vor** dem ersten Sync existieren, sonst bleibt der Pod in
> `CreateContainerConfigError` hängen. Es gibt (noch) keinen
> repo-weiten Secrets-Mechanismus (SOPS/Sealed Secrets/External Secrets
> Operator) — das Secret wird manuell angelegt und **nie** committet.

```bash
KUBECONFIG=./kubeconfig kubectl create namespace litellm --dry-run=client -o yaml | \
  KUBECONFIG=./kubeconfig kubectl apply -f -

KUBECONFIG=./kubeconfig kubectl create secret generic litellm-secret \
  --from-literal=LITELLM_MASTER_KEY='<eigener-wert>' \
  -n litellm
```

### Schritt 9.2 — Sync prüfen

```bash
KUBECONFIG=./kubeconfig kubectl get application litellm -n argocd
KUBECONFIG=./kubeconfig kubectl get pods -n litellm
```

Erwartete Ausgabe: `SYNC STATUS: Synced`, `HEALTH STATUS: Healthy`,
Pod `1/1 Running`.

### Schritt 9.3 — Health-Check und Smoke-Test

```bash
KUBECONFIG=./kubeconfig kubectl port-forward svc/litellm -n litellm 4000:4000
```

In einem zweiten Terminal:

```bash
curl http://localhost:4000/health/liveliness
curl http://localhost:4000/health/readiness

# Chat-Completion gegen das Placeholder-Modell
curl http://localhost:4000/chat/completions \
  -H "Authorization: Bearer <LITELLM_MASTER_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"model":"placeholder-model","messages":[{"role":"user","content":"hi"}]}'
```

Erwartete Ausgabe: beide Health-Checks `HTTP 200`, die Chat-Completion
liefert die feste Placeholder-Antwort aus `config.yaml` zurück.

> **Platzhalter-Modell:** `config.yaml` nutzt aktuell `mock_response` statt
> eines echten Backends — im Infra-Cluster ist (noch) kein Ollama erreichbar
> (im Gegensatz zu `host.k3d.internal` bei PG-SKIP-Platform). Sobald Ollama
> im Cluster verfügbar ist, dort die echten `litellm_params` (model +
> api_base) eintragen; das erfordert nur diesen einen Commit, keinen
> manuellen Cluster-Eingriff.

---

## Phase 10 — MinIO deployen

MinIO ist ein S3-kompatibler Objektspeicher, übernommen aus PG-SKIP-Platform
für Datensätze, Modell-Artefakte und Backups aus Jupyter-/ML-Workloads. Läuft
rein intern (`ClusterIP`, kein Ingress).

> Manifeste liegen unter `apps/services/minio/` (Kustomize: StatefulSet mit
> `volumeClaimTemplate`, Service). Die ArgoCD-`Application`
> (`argocd/core/minio.yaml`) wird automatisch vom bestehenden App-of-Apps
> (`core-apps`) übernommen — kein separater `make`-Schritt nötig, sobald die
> Datei auf `main` liegt.

### Schritt 10.1 — `minio-secret` anlegen

> Muss **vor** dem ersten Sync existieren, sonst bleibt der Pod in
> `CreateContainerConfigError` hängen. Es gibt (noch) keinen repo-weiten
> Secrets-Mechanismus (SOPS/Sealed Secrets/External Secrets Operator) — das
> Secret wird manuell angelegt und **nie** committet.

```bash
KUBECONFIG=./kubeconfig kubectl create namespace minio --dry-run=client -o yaml | \
  KUBECONFIG=./kubeconfig kubectl apply -f -

KUBECONFIG=./kubeconfig kubectl create secret generic minio-secret \
  --from-literal=MINIO_ROOT_USER='<eigener-wert>' \
  --from-literal=MINIO_ROOT_PASSWORD='<eigener-wert>' \
  -n minio
```

### Schritt 10.2 — Sync prüfen

```bash
KUBECONFIG=./kubeconfig kubectl get application minio -n argocd
KUBECONFIG=./kubeconfig kubectl get pods -n minio
```

Erwartete Ausgabe: `SYNC STATUS: Synced`, `HEALTH STATUS: Healthy`,
Pod `1/1 Running`.

### Schritt 10.3 — Health-Check

```bash
KUBECONFIG=./kubeconfig kubectl port-forward svc/minio -n minio 9000:9000 9001:9001
```

In einem zweiten Terminal:

```bash
curl http://localhost:9000/minio/health/live
```

Erwartete Ausgabe: `HTTP 200`. Die Web-Console ist unter
`http://localhost:9001` erreichbar (Login mit `MINIO_ROOT_USER`/
`MINIO_ROOT_PASSWORD`).

---

## Phase 11 — Sealed Secrets installieren

Bislang wurden Secrets (`litellm-secret`, `minio-secret`) manuell per
`kubectl create secret` angelegt und nie committet — das funktioniert,
lässt sich aber nicht in GitOps abbilden (ArgoCD sieht die Secrets nicht,
ein Cluster-Rebuild erfordert manuelles Nacharbeiten).
[Sealed Secrets](https://github.com/bitnami/sealed-secrets) löst das: ein
Controller im Cluster hält ein asymmetrisches Schlüsselpaar, `kubeseal` verschlüsselt
ein Secret lokal gegen den öffentlichen Teil, und nur das verschlüsselte
Ergebnis (`SealedSecret`) wird committet — entschlüsselbar ausschließlich
durch den Controller im Ziel-Cluster.

> Manifeste liegen unter `apps/core/sealed-secrets/` (Namespace,
> `HelmChart`-CRD für den Bitnami-Chart `sealed-secrets`, Version `2.20.0`
> / Controller `v0.40.0`). Die ArgoCD-`Application`
> (`argocd/core/sealed-secrets.yaml`) wird automatisch vom bestehenden
> App-of-Apps (`core-apps`) übernommen.

### Schritt 11.1 — `kubeseal`-CLI installieren

**macOS:**

```bash
brew install kubeseal
```

**Linux:**

```bash
KUBESEAL_VERSION='0.40.0'
curl -OL "https://github.com/bitnami/sealed-secrets/releases/download/v${KUBESEAL_VERSION}/kubeseal-${KUBESEAL_VERSION}-linux-amd64.tar.gz"
tar -xvzf "kubeseal-${KUBESEAL_VERSION}-linux-amd64.tar.gz" kubeseal
sudo install -m 755 kubeseal /usr/local/bin/kubeseal
rm kubeseal "kubeseal-${KUBESEAL_VERSION}-linux-amd64.tar.gz"
```

**Windows (WSL2):** wie Linux oben, im WSL2-Ubuntu-Terminal.

> Die `kubeseal`-Version sollte zur Controller-Version (`v0.40.0`) passen,
> siehe [Releases](https://github.com/bitnami/sealed-secrets/releases).

### Schritt 11.2 — Sync prüfen

```bash
KUBECONFIG=./kubeconfig kubectl get application sealed-secrets -n argocd
KUBECONFIG=./kubeconfig kubectl get pods -n sealed-secrets
```

Erwartete Ausgabe: `SYNC STATUS: Synced`, `HEALTH STATUS: Healthy`,
Pod `1/1 Running`.

### Schritt 11.3 — Schlüssel sichern (kritisch!)

> ⚠ **Der Controller generiert beim ersten Start automatisch ein
> Schlüsselpaar und legt den privaten Teil als Secret im Cluster ab.**
> Geht dieses Secret verloren (Cluster-Reset, Datenverlust), sind **alle**
> bereits committeten `SealedSecret`-Objekte dauerhaft unentschlüsselbar
> und müssen neu versiegelt werden. Dieses Backup **niemals** ins Git-Repo
> committen — es ist der Klartext-Generalschlüssel für alle Secrets.

```bash
KUBECONFIG=./kubeconfig kubectl get secret -n sealed-secrets \
  -l sealedsecrets.bitnami.com/sealed-secrets-key=active \
  -o yaml > sealed-secrets-key-backup.yaml
```

Backup außerhalb des Repos sicher ablegen (z. B. Passwort-Manager des
Teams), danach die lokale Datei löschen.

### Schritt 11.4 — Erstes Secret versiegeln (Beispiel)

```bash
KUBECONFIG=./kubeconfig kubectl create secret generic beispiel-secret \
  --from-literal=KEY='<wert>' \
  --namespace <ziel-namespace> \
  --dry-run=client -o yaml > beispiel-secret.yaml

kubeseal --format=yaml \
  --controller-name=sealed-secrets \
  --controller-namespace=sealed-secrets \
  --cert=<optional: gecachtes public-cert.pem> \
  < beispiel-secret.yaml > beispiel-sealedsecret.yaml

rm beispiel-secret.yaml   # Klartext nie committen, nur das Sealed-Ergebnis
```

`beispiel-sealedsecret.yaml` kann normal committet und per Kustomize in ein
`apps/services/<name>/`-Verzeichnis aufgenommen werden — der Controller
entschlüsselt es im Cluster automatisch zu einem regulären `Secret` mit
demselben Namen und Namespace.

> Öffentliches Zertifikat offline cachen (z. B. für CI, ohne Cluster-Zugriff):
> `kubeseal --controller-name=sealed-secrets --controller-namespace=sealed-secrets --fetch-cert > public-cert.pem`
> — dieses Zertifikat ist öffentlich und darf committet werden.

### Noch offen: bestehende Secrets migrieren

`litellm-secret` und `minio-secret` wurden vor Sealed Secrets manuell
angelegt und liegen nur im Cluster vor — ihre Klartextwerte sind nirgends
gespeichert und daher von hier aus nicht automatisiert migrierbar. Wer
Zugriff auf den laufenden Cluster hat, kann sie nachträglich versiegeln:

```bash
KUBECONFIG=./kubeconfig kubectl get secret litellm-secret -n litellm -o yaml \
  | kubeseal --format=yaml \
      --controller-name=sealed-secrets --controller-namespace=sealed-secrets \
  > apps/services/litellm/sealedsecret.yaml
```

(`metadata.creationTimestamp`, `resourceVersion` etc. aus dem Export vorher
entfernen — `kubeseal` übernimmt sonst unnötige Cluster-Metadaten in die
committete Datei.) Danach die `kustomization.yaml` des jeweiligen Dienstes
um die neue Datei ergänzen und das ursprüngliche, manuell angelegte Secret
im Cluster belassen (der Controller aktualisiert es beim Sync ohnehin).

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
| LiteLLM-Pod: `CreateContainerConfigError` | `litellm-secret` fehlt im Namespace `litellm` | Secret manuell anlegen (Phase 9.1) |
| MinIO-Pod: `CreateContainerConfigError` | `minio-secret` fehlt im Namespace `minio` | Secret manuell anlegen (Phase 10.1) |
| `kubeseal`: `no key could decrypt secret` | `SealedSecret` wurde gegen den Public Key eines anderen Clusters versiegelt | Neu versiegeln mit `--controller-name=sealed-secrets --controller-namespace=sealed-secrets` gegen den aktuellen Ziel-Cluster (Phase 11.4) |
| `kubeseal --fetch-cert` liefert Fehler/leer | Controller noch nicht `Running`, oder `--controller-namespace` falsch | `kubectl get pods -n sealed-secrets` prüfen (Phase 11.2), Namespace-Flag kontrollieren |

---

## Versionen synchron halten

```bash
# k3s-Version auf dem Server prüfen
ssh gaming "k3s --version"

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
          docker login harbor.172-17-204-135.sslip.io:30443 \
            -u admin --password-stdin
      - name: Build and Push
        run: |
          docker build -t harbor.172-17-204-135.sslip.io:30443/skip_applications/myapp:latest .
          docker push harbor.172-17-204-135.sslip.io:30443/skip_applications/myapp:latest
```

Runner auf dem Server installieren:

```bash
ssh gaming
mkdir -p /opt/skip/actions-runner && cd /opt/skip/actions-runner
curl -o actions-runner-linux-x64-2.321.0.tar.gz -L \
  https://github.com/actions/runner/releases/download/v2.321.0/actions-runner-linux-x64-2.321.0.tar.gz
tar xzf ./actions-runner-linux-x64-2.321.0.tar.gz

# Token aus: GitHub → Repository → Settings → Actions → Runners
./config.sh --url https://github.com/fhswf/PG-SKIP-Infrastructure \
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
            - "--context=git://github.com/fhswf/PG-SKIP-Infrastructure"
            - "--destination=harbor.172-17-204-135.sslip.io:30443/skip_applications/myapp:latest"
            - "--insecure"
      restartPolicy: Never
```

### Option C — n8n Workflow (Low-Code)

Wenn n8n deployt ist, kann ein Workflow den Build-Prozess per SSH auf `gaming` triggern.

### Empfehlung

**Kurzfristig:** Manueller Push über Port 30443 vom lokalen Rechner (Schritt 8.9).

**Mittelfristig:** GitHub Actions Self-Hosted Runner (Option A).

**Langfristig:** Kaniko im Cluster (Option B) — vollständig GitOps-konform.
