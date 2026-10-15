# Silo

S3-kompatibler Objektspeicher. **Silo** ist ein von [PGSTY](https://github.com/pgsty/silo)
gepflegter Fork von MinIO, der als Ersatz eingesetzt wird, nachdem die
Community-Distribution von MinIO eingestellt wurde. Silo ist protokoll- und
env-kompatibel zu MinIO (gleiche `MINIO_*`-Variablen, gleiche Ports, gleiche
Health-Endpoints, gleiches Datenformat), daher war der Wechsel ein reiner
1:1-Tausch des Images ohne Änderungen an Deployment-Logik oder Betrieb.

Läuft im eigenen Namespace `silo`, ohne externen Ingress (`ClusterIP`).

## Secret `silo-secret`

Das StatefulSet lädt `MINIO_ROOT_USER` und `MINIO_ROOT_PASSWORD` über
`envFrom.secretRef` aus dem Secret `silo-secret` im Namespace `silo` (Silo
übernimmt die `MINIO_*`-Variablennamen für Kompatibilität). Dieses Secret ist
bewusst **nicht** Teil dieser Manifeste und muss vor dem ersten Sync vorhanden
sein, sonst bleibt der Pod im Zustand `CreateContainerConfigError`.

Solange kein repo-weiter Secrets-Mechanismus feststeht (Entscheidung:
vorerst kein Tool wie SOPS/Sealed Secrets/External Secrets Operator, siehe
Änderungslog im Haupt-README), legt ein Skript das Secret zusammen mit den
Secrets der anderen Dienste an (aus dem Repo-Root):

```bash
./scripts/init-secrets.sh
```

Es erzeugt `MINIO_ROOT_USER=admin` und ein zufälliges `MINIO_ROOT_PASSWORD`.
Ein bereits vorhandenes `silo-secret` bleibt unverändert, da die gespeicherten
Daten zu den bisherigen Root-Zugangsdaten gehören.

**Kein** Klartext-Secret und **kein** „replace-me“-Platzhalterwert darf ins
Repo committet werden.

## Speicher

Das StatefulSet nutzt ein `volumeClaimTemplate` (`ReadWriteOnce`, 10Gi) für
`/data`. Größe/StorageClass bei Bedarf in `values.yaml` (`storage.size`,
`storage.storageClassName`) an den Zielcluster anpassen.

## Health-Check

```bash
KUBECONFIG=./kubeconfig kubectl -n silo port-forward svc/silo 9000:9000 9001:9001
curl http://localhost:9000/minio/health/live
```

Web-Console: `http://localhost:9001` (Login mit `MINIO_ROOT_USER`/
`MINIO_ROOT_PASSWORD`).
