# Make-Targets

Alle Kommandos werden aus dem Repository-Root mit GNU Make ausgeführt.
`make help` listet die Targets; die Quelle ist die `Makefile` im Root.

## Code-Qualität

| Target | Beschreibung |
| :--- | :--- |
| `make lint` | `ruff check` über alle Python-Apps |
| `make test` | `pytest` für `apps/skip-api` und `apps/capability-operator` |
| `make check` | Lint und Tests (entspricht der Python-CI) |
| `make render` | Rendert das lokale Kustomize-Overlay `deploy/local` (Fehlersuche) |

## Lokaler Cluster

| Target | Beschreibung |
| :--- | :--- |
| `make init-local` | Einstiegspunkt: `create-cluster` + `load-env` + `bootstrap` + `install-authentik` + `install-litellm` + `dev` |
| `make reset-local` (alias `make nuke`) | Cluster löschen und komplett neu aufsetzen |
| `make create-cluster` | k3d-Cluster `skip-local` laut `deploy/local/k3d-cluster.yaml` erstellen |
| `make load-env` | `deploy/local/.env` aus `.env.example` anlegen, falls nicht vorhanden |
| `make bootstrap` | KRO per Helm installieren, `deploy/crds/` und `deploy/local/bootstrap/` anwenden |
| `make install-authentik` | Authentik als lokale Dev-Fixture (`deploy/local/dependencies/authentik/`) in den Namespace `authentik` installieren; Secrets aus `.env`, wartet auf den Rollout |
| `make install-litellm` | LiteLLM als lokale Dev-Fixture per Helm in den Namespace `litellm` installieren (braucht `MISTRAL_API_KEY` in `.env`) |
| `make dev` | `skaffold dev`: Images bauen, `deploy/local` deployen, Code live syncen |
| `make start-local` / `make stop-local` / `make restart-local` | Cluster starten, anhalten, neu starten |
| `make delete-local` | Cluster löschen |
| `make status` | KRO-Pods, ResourceGraphDefinitions, Authentik- und LiteLLM-Pods sowie CapabilityClaims anzeigen |

## Dokumentation

| Target | Beschreibung |
| :--- | :--- |
| `make docs-start` | MkDocs-Server unter `http://127.0.0.1:8001` |
| `make docs-stop` | MkDocs-Server stoppen |
| `make docs-clean` | Stoppen und `site/` löschen |

## Typische Abläufe

```sh
make init-local        # einmalig: Cluster + Bootstrap + Dev-Loop
make dev               # Wiedereinstieg bei bestehendem Cluster
make check             # vor dem Commit
make bootstrap         # nach Änderungen an deploy/crds/
make install-litellm   # nach Änderungen an MISTRAL_API_KEY / LITELLM_MASTER_KEY
make install-authentik # nach Änderungen am Blueprint oder an AUTHENTIK_*/OIDC_CLIENT_*
```
