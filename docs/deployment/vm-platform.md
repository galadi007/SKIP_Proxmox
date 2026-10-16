# SKIP auf der vorhandenen VM: Anmeldung und Katalog

Basis dieses Patches: Benutzer-Archiv von Commit 53a7709 (16.10.2026).
Änderungen erfolgen im WSL-Git-Checkout und gelangen über GitHub/ArgoCD zur VM.
Die entpackte VM-Kopie ist kein Git-Arbeitsverzeichnis.

## Umfang und noch offene Funktionen

Dieses Paket ergänzt Frontend/API, HTTPS-Route, Authentik-OIDC-Provider und Anwendung.
Es startet zunächst ausdrücklich im Katalogbetrieb (PLATFORM_CATALOG_ONLY=true).
Schreibende API-Aufrufe erhalten HTTP 503; der Katalog zeigt einen Hinweis und keinen
Bereitstellungsbutton. Der API-ServiceAccount hat nur Leserechte.

Es ist **noch keine vollständige Self-Service-Plattform**:
- KRO-Controller, Application-RGD und CapabilityClaim-CRD fehlen im gelieferten Ausgangsstand.
- Der Capability-Operator wird deshalb noch nicht gestartet.
- Authentik-API-Servicekonto/Token für Teams und Sharing ist noch nicht eingerichtet.
- Silo-Zugang für die Speicheroberfläche und LiteLLM-Anbindung müssen separat geprüft werden.
- Das vorhandene OutOfSync von litellm-masterkey wird nicht verändert.
- Benutzerkennwörter und das bestehende akadmin-Konto werden nicht überschrieben.

Nicht einfach PLATFORM_CATALOG_ONLY abschalten: Zuerst die oben genannten
Abhängigkeiten und passende Schreibrechte ergänzen und mit einer Testanwendung prüfen.
Andere Oberflächen als Login/Katalog können bis dahin Fehler melden oder unvollständig sein.

## 1. Patch in WSL anwenden

Archiv SKIP-Plattform-Login-Patch.zip im Windows-Downloads-Ordner speichern.

```bash
cd /mnt/c/Users/49176/projects/SKIP_Proxmox_Eigen_Repo
unzip /mnt/c/Users/49176/Downloads/SKIP-Plattform-Login-Patch.zip -d /tmp/skip-login-patch
git apply --check /tmp/skip-login-patch/platform-login.patch
git apply /tmp/skip-login-patch/platform-login.patch
git diff --stat
git status --short
```

Bei Patch-Konflikten anhalten, keine Dateien ersetzen oder Änderungen zurücksetzen.
Der Patch enthält ausschließlich Änderungen, keinen vollständigen Repository-Ersatz.

## 2. Secret einmalig vorbereiten (aus WSL)

Das Skript wird über SSH direkt auf der VM ausgeführt. Es erzeugt ein zufälliges
OIDC-Clientsecret, falls keines existiert, und legt es in authentik und platform-system ab.
Es gibt keinen geheimen Wert aus und verändert keine bestehenden DB-/LiteLLM-Secrets.
Bestehende gleiche Werte bleiben erhalten; unterschiedliche Werte führen zum Abbruch.

```bash
ssh ubuntu@192.168.0.166 'sudo -v'
ssh ubuntu@192.168.0.166 'sudo -n bash -s' < scripts/prepare-platform-oidc.sh
```

Falls sudo ein Terminal verlangt: Skript mit scp nach /home/ubuntu/ kopieren,
per SSH anmelden und dort `sudo bash /home/ubuntu/prepare-platform-oidc.sh` ausführen.
**Vor dem Synchronisieren von Authentik muss das Secret vorhanden sein.**

## 3. Änderungen committen und Images bauen

```bash
git add apps/skip-api apps/skip-web deploy/argocd/applications/platform.yaml deploy/charts/platform deploy/charts/authentik scripts/prepare-platform-oidc.sh docs/deployment/vm-platform.md
git commit -m "Add SKIP platform login and catalog deployment"
git push origin main
git rev-parse --short=7 HEAD
```

In GitHub Actions den erfolgreichen Abschluss von **Build and Push Images** abwarten.
Der Workflow baut skip-api, skip-web und capability-operator. Prüfe die tatsächlichen
Tags in den Build-Ausgaben. Üblicher Tag: `sha-` gefolgt von den sieben Commitzeichen.
Kein alter Tag: Das neue Frontend-Image muss den Produktionsbuild enthalten.

In `deploy/charts/platform/values.yaml` `image.tag` auf genau diesen erfolgreichen
Tag setzen, dann diese Datei committen und pushen. Beispiel (nicht wörtlich übernehmen):
`tag: "sha-abcdef0"`.

Bis ein Tag gesetzt ist, meldet die neue platform-Application bewusst einen
Renderfehler mit dieser Voraussetzung. Sie wird nicht automatisch synchronisiert.

Private GHCR-Pakete benötigen ein `kubernetes.io/dockerconfigjson`-Secret im Namespace
platform-system und den Namen unter `imagePullSecrets: [{name: ghcr-pull}]`.
Vor einem Rollout klären, ob die Pakete öffentlich lesbar oder passende Pull-Zugangsdaten
vorhanden sind. Niemals Registry-Passwörter oder Tokens ins Git schreiben.

## 4. ArgoCD synchronisieren

Die root-Application entdeckt platform automatisch. Die untergeordneten Applications
haben weiterhin manuelle Synchronisation.

1. Authentik in ArgoCD aktualisieren und synchronisieren.
2. Warten, bis Server und Worker bereit sind.
3. Unter Authentik Administration → Anpassung/Customization → Blueprints den Status
   von **SKIP Platform Login** prüfen. Er muss erfolgreich sein. Bei Fehlern zuerst
   Worker-Logs lesen. Die Standard-Flows und das selbstsignierte Signaturzertifikat
   müssen existieren; die Blueprint-Referenzen verwenden deren Standardnamen.
4. Unter Anwendungen erscheint **SKIP Platform** mit dem OIDC-Provider.
5. platform in ArgoCD aktualisieren und synchronisieren, sobald der Image-Tag gesetzt ist.

Prüfung auf der VM:

```bash
sudo kubectl -n authentik rollout status deployment/authentik-worker --timeout=300s
sudo kubectl -n authentik logs deployment/authentik-worker --since=10m --tail=100
sudo kubectl -n platform-system get pods
sudo kubectl -n platform-system rollout status deployment/skip-web --timeout=300s
sudo kubectl -n platform-system rollout status deployment/skip-api --timeout=300s
```

## 5. Login prüfen

Öffnen: https://skip.192-168-0-166.sslip.io:30443/

Anmelden über Authentik mit akadmin und dem bereits gesetzten Passwort.
Erwartung: Rückkehr zum SKIP-Templatekatalog mit Hinweis auf Katalogbetrieb.
Der Blueprint verändert keine Gruppenmitgliedschaften des Administrators.

Interne Token-/JWKS-Aufrufe verwenden den Authentik-Service auf Port 80.
Browser-Aufrufe verwenden HTTPS mit NodePort 30443. Das Frontend erhält ORIGIN
explizit, damit Redirects den externen Host und Port enthalten.

## Validierung und Grenzen

- Helm-Rendering mit Authentik-Chart 2026.8.3 erfolgreich; Secret-Einbindung und
  Blueprint-Mount im Worker geprüft.
- Plattform-Helm-Rendering mit gesetztem Test-Tag erfolgreich.
- Ruff erfolgreich; 87 bestehende Python-Tests und 2 neue Katalogmodus-Tests erfolgreich.
- npm ci und Frontend-Produktionsbuild erfolgreich.
- Gebauter Node-Server lokal: Login HTTP 200, Redirect zu Authentik und Secure-Cookies geprüft.
- Shell-Syntax und git diff --check geprüft.

Kein Zugriff auf die laufende VM/GitHub-Registry: Docker-Image-Build, Image-Pull,
Blueprint-Import in Authentik und kompletter OIDC-Roundtrip sind dort noch zu testen.
Das Paket wurde nicht nach GitHub gepusht oder auf der VM angewendet.
