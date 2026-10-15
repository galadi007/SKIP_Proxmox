# PostgreSQL (gemeinsam)

Eine PostgreSQL-Instanz fuer alle Dienste der Plattform (StatefulSet, 10Gi,
Default-StorageClass des Clusters). Pro Dienst gibt es eine eigene Datenbank und einen eigenen
Benutzer (gleicher Name), angelegt vom Job `postgres-provision` nach jedem
Sync (idempotent, setzt auch Passwoerter neu).

Erreichbar im Cluster unter `postgres.postgres.svc.cluster.local:5432`.

Aktuelle Nutzer: `authentik`, `litellm`.

## Secrets (vor dem ersten Sync anlegen)

Die Secrets sind nicht Teil der Manifeste. Ohne sie bleiben Pods im Zustand
`CreateContainerConfigError`. Angelegt werden sie fuer alle Dienste mit
(aus dem Repo-Root):

```bash
./scripts/init-secrets.sh
```

Das Authentik-Admin-Passwort optional per `AUTHENTIK_BOOTSTRAP_PASSWORD=...`
vorgeben, sonst wird eines erzeugt und ausgegeben. Fuer die Datenbank legt es
an:

| Namespace   | Secret                     | Keys                                          |
|-------------|----------------------------|-----------------------------------------------|
| `postgres`  | `postgres-superuser`       | `POSTGRES_PASSWORD`                           |
| `postgres`  | `postgres-app-credentials` | `authentik-password`, `litellm-password`      |
| `authentik` | `authentik-secret`         | u. a. `AUTHENTIK_POSTGRESQL__PASSWORD`        |
| `litellm`   | `litellm-db`               | `username`, `password`                        |

Das Passwort in `postgres-app-credentials` und im Secret des Dienstes muss
uebereinstimmen. Nie Secrets im Klartext committen.

`AUTHENTIK_SECRET_KEY` nach der Inbetriebnahme **nie mehr aendern** und
sichern. Das Bootstrap-Passwort gilt nur fuer den ersten Start (Benutzer
`akadmin`).

## Neuen Dienst anbinden

1. In `values.yaml` unter `databases` einen Eintrag `- name: <dienst>` ergaenzen.
2. Im Secret `postgres-app-credentials` den Key `<dienst>-password` ergaenzen.
3. Im Namespace des Dienstes ein Secret mit demselben Passwort anlegen und den
   Dienst auf `postgres.postgres.svc.cluster.local`, Datenbank/Benutzer
   `<dienst>` konfigurieren.

Nach dem Sync legt der Job Benutzer und Datenbank an.

## Pruefen

```bash
kubectl -n postgres get pods,jobs
kubectl -n postgres exec postgres-0 -- psql -U postgres -c '\l'
```
