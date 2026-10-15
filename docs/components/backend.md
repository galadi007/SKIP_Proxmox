# Backend: `skip-api`

Das Backend der SKIP-Plattform (`apps/skip-api`) ist eine asynchrone **FastAPI**-Anwendung. Es fungiert als zentrale **Control Plane** zwischen dem Frontend (`skip-web`), Authentik (IdP) und dem Kubernetes API-Server.

---

## 🎯 Kernaufgaben

1. **Katalog-Verwaltung**: Auslesen aller clusterweit registrierten `AppTemplate`-Ressourcen (`platform.skip.de/v1alpha1`).
2. **Dynamische Schema-Extraktion**: Ermittlung der KRO OpenAPI-v3-Schemas und Verschmelzung mit `formHints` für die dynamische UI-Generierung.
3. **Provisioning & Namespace-Isolation**:
   - Prüfung von Benutzerberechtigungen auf Namespaces (eigener User-Namespace `user-<username>` oder Gruppen aus `ALLOWED_NAMESPACES`, in denen der Benutzer laut Authentik Mitglied ist).
   - On-Demand Erstellung des persönlichen Namespaces in Kubernetes (Gruppen-Namespaces wie `team-data` legt der Bootstrap an).
   - Dry-Run-Validierung gegen Kubernetes vor der Erstellung.
   - Automatische Generierung kryptografischer Auth-Tokens (`secrets.token_hex`) mit `OwnerReferences`.
4. **Authentik REST-API Integration**:
   - Automatische Erstellung dynamischer Gruppen (`app-<namespace>-<name>`) für jede deployte App.
   - Verwaltung von Mitgliedern und Freigaben (App-Sharing).
   - Saubere Löschung der Gruppe beim Uninstall der App.
5. **Multi-Tenancy & Autorisierung**:
   - Asymmetrische JWT-Token-Validierung (RS256) gegen Authentik JWKS.
   - Schutz von Apps: Nur Owner, berechtigte Gruppenmitglieder oder `skip-admins` können Apps einsehen oder verwalten.
6. **S3-Speicher & Presigned URLs (`storage/`)**:
   - Isolierung des persönlichen Benutzerbereichs (`home/<username>/`).
   - Erzeugung von AWS SigV4 Presigned URLs für direkte Browser-Uploads und Downloads ohne Backend-Bottleneck.
   - S3-basiertes Freigabesystem (`_shares/<id>.json`) für Dateien und Ordner.
7. **Self-Service Teams (`teams/`)**:
   - Erstellung und Verwaltung von kollaborativen Arbeitsgruppen (`team-<name>`) über die Authentik REST-API.
   - Autorisierungsprüfung (nur Owner/Admins dürfen Mitglieder einladen oder das Team löschen).

---

## ⚙️ Technische Details & Struktur

### Verzeichnisstruktur
```
apps/skip-api/
├── main.py              # FastAPI-App, bindet Router ein (apps, auth, storage, teams)
├── auth/                # Authentifizierung & Autorisierung
│   ├── oidc.py          #   PyJWT/JWKS-Validierung, Dependency get_current_user (lokal: X-User)
│   ├── authentik.py     #   REST-Client für Authentik v3 API (App-Gruppen, Teams, Users)
│   ├── service.py       #   Namespace-Regeln (user-<name>, Gruppen, skip-admins)
│   ├── entitlements.py  #   Berechtigungen (max. Apps, CPU/RAM, Capability-Klassen) - Mock
│   └── api.py           #   /api/me, /api/namespaces, /api/users
├── storage/             # S3-Objektspeicher & Presigned URLs
│   ├── s3.py            #   Boto3 Client & SigV4 Presigned URL Generierung
│   ├── dtos.py          #   Pydantic Modelle für Dateien, Ordner und Shares
│   ├── errors.py        #   Storage-spezifische Ausnahmen (FileNotFound, PermissionDenied)
│   ├── service.py       #   Home-Isolation, Pfadvalidierung & Freigabeprüfung
│   └── api.py           #   /api/storage: Files, Upload/Download URLs, Shares
├── teams/               # Self-Service Teams
│   ├── dtos.py          #   Pydantic Modelle (TeamResponse, Member, TeamCreateRequest)
│   ├── errors.py        #   TeamNotFound, TeamAlreadyExists, PermissionDenied
│   ├── service.py       #   Geschäftslogik & Berechtigungsprüfung (Owner vs. Member)
│   └── api.py           #   /api/teams: Teams anlegen, listen, Mitglieder verwalten
├── templates/           # Template-Katalog (Dateisystem) + /api/templates
├── deploy/              # /api/apps: render.py uebersetzt AppTemplate -> Application + Claims,
│                        #   service.py legt Instanzen an, prueft Zugriff/Berechtigungen, Sharing
├── tests/               # Pytest Unit- & Integrationstests
├── Dockerfile           # Python 3.13-slim Containerfile
└── pyproject.toml       # Paketdefinition & Abhängigkeiten (fastapi, kubernetes, boto3, httpx, PyJWT)
```

### Kubernetes API Integration
`skip-api` verwendet den offiziellen `kubernetes` Python-Client und initialisiert die Konfiguration automatisch:
```python
def _load_kubernetes_config() -> None:
    try:
        config.load_incluster_config()  # Im Pod (Production/Local Cluster)
    except config.ConfigException:
        config.load_kube_config()      # Lokale Entwicklung außerhalb des Clusters
```

Verwendete Kubernetes-APIs:
- `client.CustomObjectsApi`: Abfrage von `AppTemplate` und Erzeugen von KRO-Custom-Resources (`kro.run`).
- `client.ApiextensionsV1Api`: Auslesen von `CustomResourceDefinition`-Schemas.
- `client.CoreV1Api`: Erstellen von Namespaces und Auth-Token `Secret`-Ressourcen.

---

## 🔌 API-Endpunkte

| Methode | Pfad | Beschreibung |
| :--- | :--- | :--- |
| `GET` | `/healthz` | Liveness / Readiness Healthcheck (`{"status": "ok"}`) |
| `GET` | `/api/me` | Profil, Rollen und erlaubte Namespaces des aktuellen Benutzers |
| `GET` | `/api/namespaces` | Liste aller für den Benutzer freigeschalteten Namespaces |
| `GET` | `/api/templates` | Liste aller verfügbaren Templates mit Metadaten |
| `GET` | `/api/templates/{name}/schema` | OpenAPI Formular-Schema + `formHints` für ein Template |
| `POST` | `/api/apps` | Neue Instanz eines Templates deployen & Authentik-Gruppe anlegen |
| `GET` | `/api/apps` | Liste aller eigenen und freigegebenen App-Instanzen |
| `GET` | `/api/apps/{template}/{ns}/{name}` | Detaillierter Status einer Instanz |
| `DELETE` | `/api/apps/{template}/{ns}/{name}` | Instanz, abhängige Secrets und Authentik-Gruppe löschen |
| `GET` | `/api/apps/{template}/{ns}/{name}/members` | Mitgliederliste der freigegebenen App abrufen |
| `POST` | `/api/apps/{template}/{ns}/{name}/members` | Neuen Benutzer zur App-Gruppe hinzufügen (Sharing) |
| `DELETE` | `/api/apps/{template}/{ns}/{name}/members/{user}` | Benutzer aus der App-Gruppe entfernen |
| `GET` | `/api/users` | Autocomplete-Suche nach aktiven Benutzern in Authentik |
| `GET` | `/api/storage/files` | Dateien & Ordner im Home-Verzeichnis oder geteilten Pfaden auflisten |
| `POST` | `/api/storage/upload-url` | Presigned S3-PUT-URL für direkten Browser-Upload anfordern |
| `GET` | `/api/storage/download-url` | Presigned S3-GET-URL für sicheren Dateidownload anfordern |
| `POST` | `/api/storage/shares` | Datei oder Ordner für Benutzer oder Teams freigeben |
| `GET` | `/api/storage/shares` | Liste aller für den Benutzer freigegebenen Objekte abrufen |
| `GET` | `/api/teams` | Liste aller Teams, in denen der Benutzer Mitglied oder Owner ist |
| `POST` | `/api/teams` | Neues Self-Service Team gründen (erstellt Authentik-Gruppe `team-*`) |
| `GET` | `/api/teams/{team_name}` | Details und Mitgliederliste eines Teams abrufen |
| `DELETE` | `/api/teams/{team_name}` | Team auflösen und Gruppe aus Authentik entfernen (nur Owner/Admin) |
| `POST` | `/api/teams/{team_name}/members` | Kollegen über Authentik-Username ins Team einladen (nur Owner/Admin) |
| `DELETE` | `/api/teams/{team_name}/members/{user}` | Mitglied aus dem Team entfernen |

---

## 🔐 Authentifizierung & Token-Workflow

### 1. OIDC & PyJWT Validierung (`auth/oidc.py`)
Das Backend validiert eingehende Requests stateless über den Bearer-Token:
1. `PyJWKClient` lädt und cached die Signaturschlüssel von Authentik (`OIDC_JWKS_URL`, Standard: `<OIDC_ISSUER_URL>/jwks/`).
2. Die RS256-Signatur und Ablaufzeit (`exp`) werden kryptografisch geprüft (`iss`/`aud` nicht, da der Issuer je nach Aufrufweg Ingress vs. Cluster-DNS variiert).
3. Extraktion von `username`, `email` und zugewiesenen `groups` in das Pydantic-Objekt `AuthenticatedUser`.

!!! note "Lokaler Fallback"
    Ist `SKIP_ENV=local` oder keine `OIDC_ISSUER_URL` gesetzt, akzeptiert das Backend ohne Bearer-Token weiterhin den Header `X-User` (der Benutzer erhält dann die Gruppen `team-data` und `skip-admins`). Das erlaubt `curl`-Aufrufe und die Tests ohne Authentik.

Ist Authentik nicht konfiguriert (`AUTHENTIK_API_URL`/`AUTHENTIK_API_TOKEN` leer), laufen Deploy/Löschen normal weiter; nur App-Gruppen und Sharing sind deaktiviert.

### 2. Token-Generierung und OwnerReferences
Wenn im `AppTemplate` unter `provisioning.tokenSecrets` Einträge definiert sind (z. B. für Jupyter/Marimo Login-Tokens):
1. Backend generiert ein Secret: z. B. `my-jupyter-tokensecretref` mit einem 24-Byte Zufalls-Hex-Token.
2. Das Secret erhält eine `ownerReference` auf das erzeugte KRO-Objekt.
3. Das Backend trägt den Secret-Namen in die `spec.tokenSecretRef` der KRO-Instanz ein.
4. **Vorteil**: Wird die App gelöscht, löscht Kubernetes das Token-Secret dank Cascading Deletion automatisch mit!

---

## 🧪 Lokale Entwicklung des Backends

Um das Backend lokal (ohne Container) zu starten:

```bash
cd apps/skip-api
uv run uvicorn main:app --reload --port 8000
```

!!! note
    Wenn `skip-api` außerhalb des Clusters läuft, muss `kubectl` auf den laufenden k3d-Cluster (`k3d-skip-local`) zeigen, damit `config.load_kube_config()` funktioniert.
