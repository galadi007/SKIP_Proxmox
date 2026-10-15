# Schnellstart: SKIP Plattform testen

Diese Anleitung führt dich Schritt für Schritt durch das lokale Setup und das Starten der **SKIP Plattform**. Am Ende hast du einen lokalen Kubernetes-Cluster laufen, auf dem das Frontend, das Backend, der Capability-Operator und die Templates bereitgestellt sind.

---

## 📋 Voraussetzungen

Stelle sicher, dass folgende Software auf deinem Entwickler-System installiert ist:

| Werkzeug | Zweck |
| :--- | :--- |
| **Docker** | Container-Laufzeitumgebung für k3d und Image-Builds |
| **GNU Make** | Task Runner für Plattform-Befehle (`Makefile`, 3.81+ reicht) |
| **k3d** | Lokaler Kubernetes-in-Docker Cluster |
| **kubectl** | Kubernetes CLI |
| **helm** | Paketmanager (für KRO-Installation) |
| **skaffold** | Continuous Development & Build Tool |
| **uv** | Moderner Python Paket- und Projektmanager |
| **Python 3.12+** | Backend und Operator (Tests, Linting, IDE-Support auf dem Host) |
| **Node.js / npm** | Für das SvelteKit-Frontend (optional, nur für Lint/Tests/IDE-Support auf dem Host) |

!!! tip "Hinweis"
    Unter macOS reicht `brew install k3d kubectl helm skaffold uv node` (Docker Desktop separat installieren; `make` bringen die Xcode Command Line Tools mit). Unter Linux (z.B. Ubuntu/Debian) können `k3d`, `skaffold` und `uv` schnell über deren offizielle Paketquellen oder GitHub-Releases bezogen werden. Docker muss laufen (`docker info` darf keinen Fehler liefern).

---

## 🧰 1. Repository klonen und Workspace einrichten

```bash
git clone <repo-url> PG-SKIP-Platform
cd PG-SKIP-Platform

# Python-Workspace (skip-api, capability-operator, dev- und docs-Gruppe)
uv sync --all-groups

# Optional: Frontend-Dependencies für Type-Checks, Prettier und Tests auf dem Host
cd apps/skip-web && npm install && cd ../..
```

!!! warning "Immer aus dem Repository-Root arbeiten"
    Alle `make`-Kommandos aus dem Wurzelverzeichnis ausführen. Der k3d-Cluster mountet `${PWD}/templates` in die Nodes – aus einem anderen Verzeichnis gestartet, findet das Backend keine Templates.

---

## 🚀 2. Cluster erstellen und Plattform starten

Führe im Wurzelverzeichnis des Repositories folgenden Befehl aus:

```bash
make init-local
```

### Was passiert im Hintergrund?

`make init-local` fasst sechs Targets zusammen:

1. **`make create-cluster`**: Erstellt einen lokalen **k3d-Cluster** namens `skip-local` (1 Server, 1 Agent) laut `deploy/local/k3d-cluster.yaml`. Der Loadbalancer wird auf `127.0.0.1:8080` (HTTP) und `127.0.0.1:8443` (HTTPS) gebunden, `templates/` wird als `/templates` in alle Nodes gemountet.
2. **`make load-env`**: Kopiert `deploy/local/.env.example` nach `deploy/local/.env`, falls noch nicht vorhanden. Kustomize macht daraus das Secret `platform-env`.
3. **`make bootstrap`**: Installiert **KRO (Kube Resource Orchestrator)** via Helm in den Namespace `kro`, wendet die CRDs/ResourceGraphDefinitionen aus `deploy/crds/` an (Application-RGD, `CapabilityClaim`-CRD) und legt den lokalen Beispiel-Tenant `team-data` aus `deploy/local/bootstrap/` an.
4. **`make install-authentik`**: Installiert [Authentik](../components/authentik.md) als lokalen OIDC-Identity-Provider aus `deploy/local/dependencies/authentik/` in den Namespace `authentik` und wartet, bis der Server läuft. Ein Blueprint legt OIDC-Provider, Gruppen und die Testbenutzer `akadmin`/`AdminPw` (Admin) und `max.mustermann`/`Start123!` automatisch an.
5. **`make install-litellm`**: Installiert LiteLLM als lokale Dev-Fixture per Helm in den Namespace `litellm` (Modelle `mistral-small`/`mistral-large`). Dafür muss `MISTRAL_API_KEY` in `deploy/local/.env` gesetzt sein, sonst wird der Schritt übersprungen.
6. **`make dev`**: Startet `skaffold dev` – baut die Images `skip-api`, `skip-web` und `capability-operator`, deployt das Overlay `deploy/local` (Namespace `platform-system`, RBAC, drei Deployments, Ingress) und bleibt im Vordergrund, um Logs zu streamen und Codeänderungen zu synchronisieren.

Der erste Lauf dauert einige Minuten (Images werden gebaut, Helm-Chart und Base-Images werden geladen).

---

## 💻 3. Entwicklungsumgebung starten (Live-Reload)

Wenn der Cluster bereits existiert (z.B. am nächsten Tag oder nach **Ctrl-C**), genügt für den Wiedereinstieg:

```bash
make dev
```

Skaffold überwacht nun das Dateisystem:

- **Python** (`apps/skip-api/**/*.py`) wird per File-Sync in den Container kopiert, uvicorn lädt dank `--reload` neu.
- **Frontend** (`apps/skip-web/src/**`, `static/**`) wird gesynct, Vite macht Hot Module Replacement.
- **Templates** (`templates/`) sind als Host-Volume gemountet – Änderungen sind sofort im Backend sichtbar.
- **Operator** (`apps/capability-operator/**`) wird nicht gesynct; Skaffold baut das Image neu und deployt es.

**Ctrl-C** beendet Skaffold und räumt die Deployments aus dem Cluster; der Cluster selbst bleibt bestehen.

Der Zugriff läuft komplett über den Traefik-Ingress des k3d-Clusters (Port 8080):

| Dienst | URL | Beschreibung |
| :--- | :--- | :--- |
| **Frontend** | [http://localhost:8080](http://localhost:8080) | SvelteKit Web-Oberfläche (`skip-web`) |
| **Backend API** | [http://api.localhost:8080](http://api.localhost:8080) | FastAPI Control Plane (`skip-api`) |
| **Swagger UI** | [http://api.localhost:8080/docs](http://api.localhost:8080/docs) | Interaktive OpenAPI-Dokumentation |
| **Authentik** | [http://auth.localhost:8080](http://auth.localhost:8080) | Identity Provider / SSO (`akadmin`/`AdminPw`, `max.mustermann`/`Start123!`) |

!!! note
    Das Routing übernimmt Traefik über die Ingress-Regeln in `deploy/local/ingress.yaml` (Host `localhost` → `skip-web`, Host `api.localhost` → `platform-backend`) und `deploy/local/dependencies/authentik/ingress.yaml` (Host `auth.localhost` → `authentik-server`), siehe [Ingress & Routing](../deployment/ingress.md). Browser lösen `*.localhost` automatisch auf `127.0.0.1` auf, viele CLI-Tools nicht: Entweder `127.0.0.1 api.localhost` in `/etc/hosts` eintragen oder curl mit Host-Header aufrufen (`curl -H 'Host: api.localhost' http://localhost:8080/healthz`).

---

## 🧪 4. Plattform testen

### A. Template über die Web-UI starten

1. Öffne im Browser [http://localhost:8080](http://localhost:8080) und melde dich über Authentik an, z. B. als `max.mustermann` / `Start123!` (Gruppe `team-data`) oder als Admin `akadmin` / `AdminPw`.
2. Du siehst den **Template-Katalog** mit verfügbaren Templates wie *Jupyter Notebook*, *Marimo Notebook* oder *Open WebUI*.
3. Klicke auf ein Template (z.B. **Jupyter Notebook**).
4. Das Formular wird dynamisch aus dem Konfigurations-Schema der `template.yaml` generiert (z.B. Variante `minimal`, `scipy`, `datascience`, Speichergröße, CPU und Arbeitsspeicher).
5. Gib deiner Instanz einen Namen (z.B. `my-jupyter-test`) und wähle den Namespace: deinen persönlichen `user-<name>` (wird beim ersten Deploy angelegt) oder einen Gruppen-Namespace wie `team-data`, sofern du in Authentik Mitglied der Gruppe bist.
   Über **Teilen** in der Deployments-Ansicht kannst du die App später anderen Benutzern freigeben.
6. Klicke auf **Deploy**.
7. Die Instanz wechselt in den Status `Deploying` und nach erfolgreichem Start auf `Running`.

### B. Template über die API starten (cURL / HTTP)

Du kannst dieselbe Operation auch direkt über die REST-API ausführen. Alle Endpunkte außer `/healthz` erwarten ein Authentik-Bearer-Token (`Authorization: Bearer …`, setzt die Web-UI nach dem Login). Lokal akzeptiert das Backend alternativ den Header `X-User`, der Benutzer gilt dann als Mitglied von `team-data` und `skip-admins`:

```bash
# 0. Health-Check
curl http://api.localhost:8080/healthz    # -> {"status":"ok"}

# 1. Verfügbare Templates abfragen
curl -s -H 'X-User: dev@skip.de' http://api.localhost:8080/api/templates | jq .

# 2. Schema für Jupyter Notebook abfragen
curl -s -H 'X-User: dev@skip.de' http://api.localhost:8080/api/templates/jupyter-notebook/schema | jq .

# 3. Neue Jupyter-Instanz erzeugen
curl -X POST http://api.localhost:8080/api/apps \
  -H 'Content-Type: application/json' \
  -H 'X-User: dev@skip.de' \
  -d '{
    "template": "jupyter-notebook",
    "name": "my-notebook",
    "namespace": "team-data",
    "values": {
      "variant": "minimal",
      "storageSize": "1Gi"
    }
  }'

# 4. Eigene laufende Apps abfragen
curl -s -H 'X-User: dev@skip.de' http://api.localhost:8080/api/apps | jq .
```

---

## 🔍 5. Status und Cluster prüfen

Um den Status aller Platform-Komponenten auf einen Blick zu sehen (in einem zweiten Terminal):

```bash
make status    # KRO-Pods, ResourceGraphDefinitions, CapabilityClaims
```

Oder direkt mit `kubectl`:

```bash
# KRO Pods anzeigen
kubectl get pods -n kro

# System-Pods anzeigen (platform-backend, skip-web, capability-operator)
kubectl get pods -n platform-system

# Eigene App-Pods anzeigen (z.B. im Namespace team-data)
kubectl get pods -n team-data

# KRO Resource Graphs und CapabilityClaims anzeigen
kubectl get rgd
kubectl get claims -A
```

---

## 🧹 6. Cluster stoppen oder zurücksetzen

| Aktion | Befehl | Beschreibung |
| :--- | :--- | :--- |
| **Cluster pausieren** | `make stop-local` | Hält die Docker-Container des k3d-Clusters an, Zustand bleibt erhalten |
| **Cluster fortsetzen** | `make start-local` | Startet den pausierten k3d-Cluster wieder (danach `make dev`) |
| **Cluster neu starten** | `make restart-local` | Startet den k3d-Cluster neu |
| **Cluster löschen** | `make delete-local` | Löscht den lokalen k3d-Cluster rückstandslos |
| **Cluster komplett neu aufsetzen** | `make reset-local` *(oder `make nuke`)* | Löscht den Cluster und richtet ihn frisch von 0 auf ein |
