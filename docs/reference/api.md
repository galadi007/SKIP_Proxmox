# REST-API Referenz

Das Backend `skip-api` stellt eine REST-API bereit, über die alle Operationen der Plattform ausgeführt werden können.

!!! tip "Interaktive Swagger / OpenAPI-Dokumentation"
    Bei laufendem Cluster (`make dev`) ist die interaktive Swagger-UI über den Ingress unter **[http://api.localhost:8080/docs](http://api.localhost:8080/docs)** erreichbar. Dort können alle Endpunkte direkt im Browser getestet werden.

---

## 🔑 Authentifizierung & Header

Das Backend erwartet ein von [Authentik](../components/authentik.md) ausgestelltes JWT als Bearer-Token; die Web-UI setzt es automatisch aus der Session:

```http
Authorization: Bearer <access_token>
```

Lokal (`SKIP_ENV=local`) akzeptiert das Backend ohne Token alternativ den Header `X-User`. Der Benutzer erhält dann die Gruppen `team-data` und `skip-admins`, was `curl`-Aufrufe ohne Login erlaubt:

```http
X-User: <username>
```

Beispiel: `X-User: demo-user`. Ohne beides antwortet die API mit `401`.

Zusätzlich zu den unten beschriebenen Endpunkten gibt es `GET /api/me` (Profil, Gruppen, erlaubte Namespaces), `GET /api/namespaces`, `GET /api/users?query=` (Benutzersuche in Authentik) sowie `GET`/`POST`/`DELETE /api/apps/{template}/{ns}/{name}/members[/{username}]` für das App-Sharing; Details in der [Backend-Dokumentation](../components/backend.md).

---

## 📡 Endpunkte

### 1. Healthcheck
Prüft die Verfügbarkeit der API.

- **Methode**: `GET`
- **Pfad**: `/healthz`
- **Antwort**: `200 OK`
  ```json
  {
    "status": "ok"
  }
  ```

---

### 2. Templates auflisten
Gibt alle im Cluster registrierten `AppTemplates` zurück.

- **Methode**: `GET`
- **Pfad**: `/api/templates`
- **Header**: `X-User: <username>`
- **Antwort**: `200 OK`
  ```json
  [
    {
      "name": "jupyternotebook",
      "displayName": "Jupyter Notebook",
      "summary": "Ein einfaches Jupyter Notebook Template",
      "category": "data-science",
      "tags": ["python", "notebook", "analytics"],
      "maturity": "beta",
      "version": "0.4.0",
      "icon": {}
    },
    {
      "name": "marimo",
      "displayName": "Marimo Notebook",
      "summary": "Marimo Template",
      "category": "data-science",
      "tags": ["python", "notebook", "reactive"],
      "maturity": "experimental",
      "version": "0.1.0",
      "icon": {}
    }
  ]
  ```

---

### 3. Template-Details und Formular-Schema abrufen
Antworten von `POST`/`GET /api/apps` enthalten neben `phase`, `message` und `components[]` (Status je Komponente) die öffentliche URL der App (`url`, erste HTTP-Komponente) und je Komponente `components[].url`.

`GET /api/templates/{name}` liefert das vollständige Template für das Frontend: Metadaten, `descriptionMarkdown`, `parameters` (mit `displayName`, `values`, `default`, …), `capabilities`, `components` sowie die JSON-Schema-Sicht `configurationSchema` und `formHints`. Das Frontend rendert das Formular aus `parameters`.

`GET /api/templates/{name}/schema` liefert nur die JSON-Schema-Sicht (aus `spec.parameters` generiert):

- **Methode**: `GET`
- **Pfad**: `/api/templates/{name}/schema`
- **Beispiel**: `GET /api/templates/jupyter-notebook/schema`
- **Antwort**: `200 OK`
  ```json
  {
    "schema": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "variant": {
          "title": "Variante",
          "type": "string",
          "enum": ["minimal", "scipy", "datascience"],
          "x-enumLabels": {"minimal": "Minimal", "scipy": "SciPy", "datascience": "Data Science"},
          "default": "minimal"
        },
        "storageSize": {
          "title": "Speicher",
          "type": "string",
          "pattern": "^[0-9]+(Mi|Gi)$",
          "default": "5Gi"
        },
        "llmAccess": {"title": "LLM-Zugang", "type": "boolean", "default": false}
      }
    },
    "formHints": {
      "order": ["variant", "size", "storageSize", "llmAccess"],
      "labels": {"variant": "Variante", "size": "Größe", "storageSize": "Speicher", "llmAccess": "LLM-Zugang"},
      "advanced": []
    }
  }
  ```

---

### 4. Neue Anwendung deployen
Erstellt eine Instanz des angegebenen Templates.

- **Methode**: `POST`
- **Pfad**: `/api/apps`
- **Header**:
  - `Content-Type: application/json`
  - `X-User: <username>`
- **Request Body**:
  ```json
  {
    "template": "jupyternotebook",
    "name": "my-jupyter-app",
    "namespace": "team-data",
    "values": {
      "variant": "minimal",
      "storageSize": "1Gi"
    }
  }
  ```
- **Validierungsregeln**:
  - `namespace` muss in `ALLOWED_NAMESPACES` (z.B. `team-data`) enthalten sein.
  - `name` muss dem Regex `^[a-z0-9]([-a-z0-9]{0,44}[a-z0-9])?$` entsprechen.
- **Antwort**: `201 Created`
  ```json
  {
    "template": "jupyternotebook",
    "namespace": "team-data",
    "name": "my-jupyter-app"
  }
  ```

---

### 5. Eigene Anwendungen auflisten
Listet alle Instanzen auf, die dem aktuellen Benutzer gehören (`platform.skip.de/owner`).

- **Methode**: `GET`
- **Pfad**: `/api/apps`
- **Header**: `X-User: <username>`
- **Antwort**: `200 OK`
  ```json
  [
    {
      "template": "jupyternotebook",
      "name": "my-jupyter-app",
      "namespace": "team-data",
      "phase": "Running",
      "message": null,
      "status": {
        "availableReplicas": 1
      }
    }
  ]
  ```

---

### 6. Anwendungs-Status abfragen
- **Methode**: `GET`
- **Pfad**: `/api/apps/{template}/{namespace}/{name}`
- **Header**: `X-User: <username>`
- **Antwort**: `200 OK`
  ```json
  {
    "template": "jupyternotebook",
    "name": "my-jupyter-app",
    "namespace": "team-data",
    "phase": "Running",
    "message": null,
    "status": {
      "availableReplicas": 1,
      "conditions": [
        {
          "type": "Ready",
          "status": "True"
        }
      ]
    }
  }
  ```

---

### 7. Anwendung löschen
Löscht die Instanz und alle zugehörigen Ressourcen (durch Cascading OwnerReferences).

- **Methode**: `DELETE`
- **Pfad**: `/api/apps/{template}/{namespace}/{name}`
- **Header**: `X-User: <username>`
- **Antwort**: `204 No Content`

---

### 8. S3-Speicher & Presigned URLs

#### 8.1 Dateien & Ordner auflisten
Listet Objekte im Home-Verzeichnis (`home/<username>/`) oder geteilten Pfaden auf.

- **Methode**: `GET`
- **Pfad**: `/api/storage/files?prefix=home/max.mustermann/daten/`
- **Header**: `Authorization: Bearer <token>`
- **Antwort**: `200 OK`
  ```json
  {
    "prefix": "home/max.mustermann/daten/",
    "folders": ["home/max.mustermann/daten/csv/"],
    "files": [
      {
        "key": "home/max.mustermann/daten/training.csv",
        "name": "training.csv",
        "size": 1048576,
        "last_modified": "2026-09-22T20:00:00Z"
      }
    ]
  }
  ```

#### 8.2 Presigned Upload-URL anfordern
Generiert eine AWS SigV4 Presigned-PUT-URL für den direkten Datei-Upload vom Browser nach S3.

- **Methode**: `POST`
- **Pfad**: `/api/storage/upload-url`
- **Body**:
  ```json
  {
    "filename": "model.pt",
    "prefix": "home/max.mustermann/models/"
  }
  ```
- **Antwort**: `200 OK`
  ```json
  {
    "upload_url": "http://s3.localhost:8080/skip-bucket/home/max.mustermann/models/model.pt?X-Amz-Algorithm=...",
    "key": "home/max.mustermann/models/model.pt"
  }
  ```

#### 8.3 Presigned Download-URL anfordern
Generiert eine temporäre SigV4 Presigned-GET-URL zum sicheren Herunterladen einer Datei.

- **Methode**: `GET`
- **Pfad**: `/api/storage/download-url?key=home/max.mustermann/models/model.pt`
- **Antwort**: `200 OK`
  ```json
  {
    "download_url": "http://s3.localhost:8080/skip-bucket/home/max.mustermann/models/model.pt?X-Amz-Algorithm=..."
  }
  ```

#### 8.4 Datei oder Ordner teilen
Erstellt einen Freigabeeintrag im S3-Register (`_shares/<id>.json`).

- **Methode**: `POST`
- **Pfad**: `/api/storage/shares`
- **Body**:
  ```json
  {
    "item_type": "folder",
    "item_name": "daten",
    "source_key": "home/max.mustermann/daten/",
    "shared_with": ["erika.musterfrau", "team-ki-forschung"]
  }
  ```
- **Antwort**: `201 Created`

---

### 9. Self-Service Teams

#### 9.1 Teams auflisten
Gibt alle Teams zurück, in denen der aktuelle Benutzer Besitzer oder Mitglied ist.

- **Methode**: `GET`
- **Pfad**: `/api/teams`
- **Header**: `Authorization: Bearer <token>`
- **Antwort**: `200 OK`
  ```json
  [
    {
      "name": "team-ki-forschung",
      "display_name": "team-ki-forschung",
      "owner": "max.mustermann",
      "is_owner": true,
      "member_count": 2,
      "members": [
        {"username": "max.mustermann", "email": "max@example.com"},
        {"username": "erika.musterfrau", "email": "erika@example.com"}
      ]
    }
  ]
  ```

#### 9.2 Neues Team anlegen
Erstellt eine neue Gruppe mit Präfix `team-` in Authentik und hinterlegt Metadaten (`type: team`, `owner: <user>`).

- **Methode**: `POST`
- **Pfad**: `/api/teams`
- **Body**:
  ```json
  {
    "name": "ki-forschung"
  }
  ```
- **Antwort**: `201 Created`

#### 9.3 Kollegin ins Team einladen
Fügt einen in Authentik registrierten Benutzer zum Team hinzu (nur Owner oder `skip-admins`).

- **Methode**: `POST`
- **Pfad**: `/api/teams/team-ki-forschung/members`
- **Body**:
  ```json
  {
    "username": "erika.musterfrau"
  }
  ```
- **Antwort**: `200 OK`

#### 9.4 Mitglied entfernen
Entfernt einen Benutzer aus dem Team (Owner/Admin) bzw. verlässt das Team selbstständig (Mitglied).

- **Methode**: `DELETE`
- **Pfad**: `/api/teams/team-ki-forschung/members/erika.musterfrau`
- **Antwort**: `204 No Content`

#### 9.5 Team auflösen
Löscht das Team und entfernt die Gruppe aus Authentik (nur Owner oder `skip-admins`).

- **Methode**: `DELETE`
- **Pfad**: `/api/teams/team-ki-forschung`
- **Antwort**: `204 No Content`
