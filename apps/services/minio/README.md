# MinIO

S3-kompatibler Objektspeicher (MinIO), übernommen aus PG-SKIP-Platform. Läuft
im eigenen Namespace `minio`, ohne externen Ingress (`ClusterIP`).

## Secret `minio-secret`

Das StatefulSet lädt `MINIO_ROOT_USER` und `MINIO_ROOT_PASSWORD` über
`envFrom.secretRef` aus dem Secret `minio-secret` im Namespace `minio`.
Dieses Secret ist bewusst **nicht** Teil dieser Manifeste und muss vor dem
ersten Sync vorhanden sein, sonst bleibt der Pod im Zustand
`CreateContainerConfigError`.

Solange kein repo-weiter Secrets-Mechanismus feststeht (Entscheidung:
vorerst kein Tool wie SOPS/Sealed Secrets/External Secrets Operator, siehe
Änderungslog im Haupt-README), wird das Secret manuell angelegt:

```bash
KUBECONFIG=./kubeconfig kubectl create namespace minio --dry-run=client -o yaml | \
  KUBECONFIG=./kubeconfig kubectl apply -f -

KUBECONFIG=./kubeconfig kubectl create secret generic minio-secret \
  --from-literal=MINIO_ROOT_USER='<eigener-wert>' \
  --from-literal=MINIO_ROOT_PASSWORD='<eigener-wert>' \
  -n minio
```

**Kein** Klartext-Secret und **kein** „replace-me“-Platzhalterwert darf ins
Repo committet werden.

## Speicher

Das StatefulSet nutzt ein `volumeClaimTemplate` (`ReadWriteOnce`, 10Gi) für
`/data`. Größe/StorageClass bei Bedarf an den Zielcluster anpassen.

## Health-Check

```bash
KUBECONFIG=./kubeconfig kubectl -n minio port-forward svc/minio 9000:9000 9001:9001
curl http://localhost:9000/minio/health/live
```

Web-Console: `http://localhost:9001` (Login mit `MINIO_ROOT_USER`/
`MINIO_ROOT_PASSWORD`).
