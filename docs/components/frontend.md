# Frontend: `skip-web`

Das Frontend der SKIP-Plattform (`apps/skip-web`) ist eine moderne Webanwendung, die auf **SvelteKit 2** und **Svelte 5 (Runes)** basiert.

---

## 🎨 Technologie-Stack

- **Framework**: [SvelteKit 2](https://kit.svelte.dev/) mit [Svelte 5 (Runes: `$state`, `$derived`, `$effect`)](https://svelte.dev/)
- **Bundler & Dev Server**: [Vite](https://vitejs.dev/)
- **Styling**: [Tailwind CSS v4](https://tailwindcss.com/)
- **UI-Komponenten**: [Bits UI](https://bits-ui.com/) & [shadcn-svelte](https://shadcn-svelte.com/)
- **Icons**: [Lucide Svelte](https://lucide.dev/guide/packages/lucide-svelte)
- **Authentifizierung**: OIDC / OAuth2 Integration mit Authentik und serverseitigem Auth-Gate

---

## 🖥️ Hauptansichten & Features

### 1. Auth-Gate & Login-Landingpage (`/login`)
- Schützt alle internen Routen vor unberechtigtem Zugriff.
- **Modernes SKIP Login-Interface**: Zeigt den Plattform-Status, SSO-Login-Buttons und nützliche Dokumentations-Links.
- **Konfigurierbar**: Über die Umgebungsvariable `AUTH_DIRECT_REDIRECT=true` (Secret `platform-env`, siehe `deploy/local/.env.example`) kann bei Bedarf direkt zum Authentik-IdP durchgeleitet werden.

### 2. Template-Katalog (`/templates`)
- Zeigt alle verfügbaren `AppTemplates` aus Kubernetes als interaktive Karten an.
- Filterbar nach Kategorien (z. B. `data-science`), Schlagwörtern (`python`, `notebook`) und Reifegrad (`beta`, `experimental`, `stable`).
- Detaillierte Darstellung von Name, Version, Kurzbeschreibung und Autor.

### 3. Dynamische Formular-Engine (`/deploy/[id]`)
- Das Formular zur Konfiguration einer App wird zur Laufzeit aus dem KRO OpenAPI-Schema generiert:
  1. Frontend ruft `GET /api/templates/{name}/schema` und `GET /api/namespaces` auf.
  2. **Namespace-Dropdown**: Bietet nur die Namespaces an, für die der Benutzer berechtigt ist (z. B. persönlicher Namespace `user-<username>` oder Gruppen wie `team-data`).
  3. Die Formular-Engine rendert automatisch passende Eingabeelemente:
     - Enums $\rightarrow$ Dropdown-Selects (z. B. Jupyter-Varianten `minimal`, `scipy`, `datascience`)
     - Strings / Numbers $\rightarrow$ Validierte Text- und Nummern-Inputs (z. B. Speichergröße `1Gi`)
     - Advanced-Felder $\rightarrow$ Einklappbare Akkordeons für Fortgeschrittene

### 4. Deployments & Workspace Dashboard (`/deployments`)
- Zentrale Übersicht aller eigenen sowie geteilten Anwendungen.
- **Rollen-Badges**: Unterscheidet klar zwischen `Owner` (Ersteller) und `Mitglied` (freigeschalteter Kollege).
- **Status-Tracking**:
  - `Deploying`: Ressourcen werden von KRO erzeugt, Pods initialisieren sich.
  - `Running`: Deployment meldet verfügbare Replicas $\ge 1$ und ist einsatzbereit.
  - `Failed`: Fehlermeldungen aus Kubernetes Conditions werden transparent dargestellt.
- **App-Sharing & Zusammenarbeit**:
  - Besitzer können über einen Klick auf *"Teilen"* ein Freigabe-Modal öffnen und andere Benutzer direkt aus Authentik zur App hinzufügen.
- **Sicheres Lifecycle-Management**:
  - Bestätigungsbanner nach erfolgreichem Start.
  - Uninstall-Button für Besitzer zum Löschen der Instanz inkl. Secrets und Authentik-Gruppen.

### 5. Dateimanager & Home-Verzeichnis (`/storage`)
- **Persönliches Home-Verzeichnis**: Vollwertiger S3-Dateimanager für das persönliche Benutzer-Präfix (`home/<username>/`).
- **Dateiverwaltung**: Uploads via Presigned PUT-URLs (ohne Backend-Traffic), Downloads, Datei- und Ordnerlöschung sowie Anlegen neuer Unterordner.
- **Hierarchische Navigation**: Breadcrumbs zur intuitiven Navigation in tief verschachtelten Unterordnern.
- **Granulares Teilen**: Modal zur Freigabe von Ordnern oder Dateien an Kollegen (per Benutzername) oder Arbeitsgruppen (per Team/Gruppe).
- **Kollaborations-Reiter**: Trennung zwischen *„Meine Dateien“* und *„Für mich freigegeben“*.

### 6. Teams & Kollaboration (`/teams`)
- **Self-Service Teams**: Ermöglicht das Gründen eigener Arbeitsgruppen (z. B. für Forschungsprojekte oder Lehrveranstaltungen).
- **Übersichtskarten & Rollen**: Zeigt eigene Teams mit Owner-Badge sowie Teams an, in denen man als Mitglied mitwirkt.
- **Mitgliederverwaltung**: Besitzer können über ein Autocomplete-Modal (`GET /api/users`) registrierte Plattformbenutzer einladen oder entfernen.
- **Team-Auflösung**: Besitzer können Teams auflösen; Mitglieder können Gruppen selbstständig verlassen.

---

## 📁 Verzeichnisstruktur

```
apps/skip-web/
├── src/
│   ├── routes/
│   │   ├── +layout.svelte        # Globales Layout (Sidebar, Theme, Auth-Header)
│   │   ├── +page.svelte          # Startseite (Redirect zu /templates)
│   │   ├── login/                # SKIP Login Landingpage
│   │   ├── templates/            # Template-Katalog
│   │   ├── deploy/[id]/          # Dynamisches Deployment-Formular
│   │   ├── deployments/          # Deployments-Dashboard mit Sharing-Modal
│   │   ├── storage/              # S3-Dateimanager, Breadcrumbs & Freigaben
│   │   ├── teams/                # Self-Service Teams Dashboard & Mitgliederverwaltung
│   │   └── auth/                 # OIDC Handshake (/login, /callback, /logout)
│   ├── lib/
│   │   ├── components/           # UI-Komponenten (Sidebar, NavUser, Cards, Tables)
│   │   ├── server/auth.ts        # OIDC Token-Exchange & JWT Parsing
│   │   └── utils.ts              # Hilfsfunktionen
│   └── hooks.server.ts           # Globaler Auth-Gate Hook & Session Resolver
├── static/                       # Statische Assets (Favicon, Logos)
├── package.json                  # NPM Abhängigkeiten und Skripte
├── svelte.config.js              # SvelteKit Konfiguration (Adapter Node)
└── vite.config.ts                # Vite Bundler Konfiguration
```

---

## 🛠️ Lokale Frontend-Entwicklung

Falls du direkt am Frontend entwickeln möchtest:

```bash
cd apps/skip-web

# Abhängigkeiten installieren
npm install

# Entwicklungsserver starten
npm run dev
```

Der Server startet unter `http://localhost:5173`.

### Verfügbare Skripte

| Befehl | Beschreibung |
| :--- | :--- |
| `npm run dev` | Startet den Vite Entwicklungsserver |
| `npm run build` | Erstellt das produktive Build-Bundle |
| `npm run preview` | Vorschau des erstellten Production-Builds |
| `npm run check` | Führt `svelte-check` und TypeScript-Validierung durch (0 Fehler) |
| `npm run lint` | Prüft Codeformatierung mit Prettier |
| `npm run format` | Formatiert den Code automatisch mit Prettier |
