# Template-System & Verfügbare Templates

In der SKIP-Plattform ist ein **Template** eine wiederverwendbare, paketierte Blaupause für eine Kubernetes-Anwendung. Jedes Template ist ein Verzeichnis unter `templates/<name>/` und besteht aus:

1. **`template.yaml`** (Pflicht): Das SKIP **AppTemplate** (`platform.skip.io/v1alpha1`) – Katalog-Metadaten, `parameters` für das Formular, angeforderte `capabilities` und die `components`, die laufen sollen. Nur diese Datei liest das Backend.
2. **`README.md`, `logo.svg`, `image/`** (optional): Katalog-Beschreibung, Logo und ein eigenes Docker-Image.

Das Backend übersetzt das Template beim Deploy in eine Instanz der generischen `Application`-RGD (`deploy/crds/application-rgd.yaml`) und in `CapabilityClaim`s; eine eigene RGD pro Template ist nicht nötig.

Das Modell ist im [Template-Modell](../architecture/template-model.md) beschrieben.

---

## 📦 Vorhandene Standard-Templates

Aktuell liefert die SKIP-Plattform folgende Templates im Verzeichnis `templates/` mit:

### 1. 🪐 Jupyter Notebook (`templates/jupyter/`, Name `jupyter-notebook`)

Ein vollständiger Data-Science- und Analytics-Arbeitsplatz.

- **Kategorien**: `development`, `data-science`, `ai`
- **Version**: `1.0.0`
- **Parameter**:
  - `variant` (Enum): Auswahl des Docker-Images (`minimal`, `scipy`, `datascience` → `quay.io/jupyter/*-notebook`).
  - `size` (Enum): `small` (1 CPU, 2 GiB), `medium` (2 CPU, 4 GiB), `large` (4 CPU, 8 GiB).
  - `storageSize` (String): Größe des persistenten Speicherplatzes unter `/home/jovyan/work` (Standard: `5Gi`).
  - `accessToken` (String, erweitert): Token für die Jupyter-Anmeldung (`JUPYTER_TOKEN`, Standard `skip`, leer = ohne Anmeldung).
  - `llmAccess` (Boolean): Optionaler Zugang zum LLM-Gateway; setzt `OPENAI_BASE_URL` und `OPENAI_API_KEY` im Notebook (Standard: aus).
- **Erzeugte Kubernetes-Ressourcen** (über die generische `Application`-RGD): `ServiceAccount`, `PersistentVolumeClaim`, `Deployment` mit den gewählten Ressourcenlimits und `Service`; mit `llmAccess` zusätzlich ein `CapabilityClaim`.

### 2. ⚡ Marimo Notebook (`templates/marimo/`, Name `marimo`)

Ein modernes, reaktives Python-Notebook für reproduzierbare Data Science und interaktive Apps.

- **Kategorien**: `development`, `data-science`
- **Version**: `0.1.0`
- **Parameter**:
  - `size` (Enum): `small` (0.5 CPU, 1 GiB), `medium` (1 CPU, 2 GiB), `large` (2 CPU, 4 GiB).
  - `storageSize` (String): Größe des persistenten Speichers unter `/home/marimo/work` (Standard: `1Gi`).
- **Image**: Eigenes Image aus `templates/marimo/image/`.
- **Besonderheit**: Reaktivität (Änderung einer Zelle aktualisiert abhängige Zellen sofort wie in einer Tabellenkalkulation).

### 3. 💬 Open WebUI (`templates/openwebui/`, Name `open-webui`)

Eine Chat-Oberfläche für die Sprachmodelle der Plattform mit eigener PostgreSQL-Datenbank – das Beispiel für ein **Template mit mehreren Komponenten**.

- **Kategorie**: `ai`
- **Parameter**:
  - `storageSize` (String): Größe des persistenten Datenverzeichnisses der Web-UI (Standard: `2Gi`).
  - `dbStorageSize` (String, erweitert): Größe des PostgreSQL-Volumes (Standard: `1Gi`).
- **Komponenten**: `open-webui` (Web-UI, Service auf 8080) und `postgres` (Datenbank, Service auf 5432). Die UI erreicht die Datenbank über `${components.postgres.host}`; beide werden zu eigenen Application-Instanzen `<app>-open-webui` und `<app>-postgres`.
- **Besonderheit**: Fordert die Capability `llm` (`llm-access`, Modelle `mistral-small`/`mistral-large`) verpflichtend an. Das Backend legt den `CapabilityClaim` `<app>-llm` an, der `capability-operator` provisioniert einen virtuellen Gateway-Key, und die Bindings setzen `OPENAI_API_BASE_URL` und `OPENAI_API_KEY` aus dem Claim-Secret (siehe [Shared Services](../components/services.md)).

---

## 🏗️ Verzeichnisaufbau eines Templates

Jedes Template liegt in einem eigenen Unterverzeichnis in `templates/<name>/`:

```
templates/
├── jupyter/
│   ├── template.yaml    # AppTemplate: Metadaten, parameters, capabilities, components
│   ├── README.md        # Katalog-Beschreibung (Markdown)
│   └── logo.svg         # Logo im Katalog
├── marimo/
│   ├── template.yaml
│   └── image/           # eigenes Docker-Image
└── openwebui/
    ├── template.yaml    # fordert Capability `llm` an, bindet sie als OPENAI_* env
    └── README.md
```

---

## 🔄 Wie Templates geladen werden

Es gibt keinen Apply-Schritt für den Katalog. `templates/` wird beim Erstellen des k3d-Clusters als `/templates` in die Nodes gemountet; das Backend bekommt im lokalen Overlay `TEMPLATES_DIR=/templates` (`deploy/local/api-reload-patch.yaml`) und liest beim Start jede `template.yaml` von dort. Neue oder geänderte Templates brauchen deshalb keinen Neustart, sondern nur ein erneutes Einlesen:

```bash
# Katalog neu einlesen und anzeigen (alle Endpunkte außer /healthz erwarten X-User)
curl -X POST -H 'X-User: dev@skip.de' http://api.localhost:8080/api/templates/reload
curl -H 'X-User: dev@skip.de' http://api.localhost:8080/api/templates
```

Im Cluster (ohne lokales Overlay) liest das Backend die Quellen aus der ConfigMap `template-sources`, z. B. Unterordner von GitHub-Repositories. Siehe [Templates aus Git-Repositories](sources.md).

Ob ein Template korrekt geparst wird, prüft auch `make test` – die Backend-Tests laden die echten Templates aus `templates/`.

Beim Deploy übersetzt das Backend (`apps/skip-api/deploy/render.py`) jede Komponente des Templates in eine Instanz der generischen `Application`-RGD (`<app>-<komponente>`), die `make bootstrap` aus `deploy/crds/` installiert, und legt für jede aktive Capability einen `CapabilityClaim` an (Owner: alle Instanzen der App). Komponenten mit `expose: type: http` bekommen einen Ingress und sind unter `http://<app>.<namespace>.apps.localhost:8080` erreichbar (siehe [Ingress & Routing](../deployment/ingress.md)). Details im [Template-Modell](../architecture/template-model.md).

Wie ein eigenes Template entsteht, zeigt die [Anleitung zur Template-Erstellung](authoring.md).
