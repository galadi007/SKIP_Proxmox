# LiteLLM

AI-Gateway (LiteLLM Proxy), übernommen aus PG-SKIP-Platform. Läuft im eigenen
Namespace `litellm`, ohne externen Ingress (`ClusterIP`).

## Secret `litellm-secret`

Das Deployment lädt `LITELLM_MASTER_KEY` über `envFrom.secretRef` aus dem
Secret `litellm-secret` im Namespace `litellm`. Dieses Secret ist bewusst
**nicht** Teil dieser Manifeste und muss vor dem ersten Sync vorhanden sein,
sonst bleibt der Pod im Zustand `CreateContainerConfigError`.

Solange kein repo-weiter Secrets-Mechanismus feststeht (Entscheidung:
vorerst kein Tool wie SOPS/Sealed Secrets/External Secrets Operator, siehe
Änderungslog im Haupt-README), wird das Secret manuell angelegt:

```bash
KUBECONFIG=./kubeconfig kubectl create namespace litellm --dry-run=client -o yaml | \
  KUBECONFIG=./kubeconfig kubectl apply -f -

KUBECONFIG=./kubeconfig kubectl create secret generic litellm-secret \
  --from-literal=LITELLM_MASTER_KEY='<eigener-wert>' \
  -n litellm
```

**Kein** Klartext-Secret und **kein** „replace-me“-Platzhalterwert darf ins
Repo committet werden.

## Modellkonfiguration

`config.yaml` verwendet aktuell ein Platzhalter-Modell (`mock_response`),
da im Infra-Cluster noch kein Ollama-Backend erreichbar ist. Sobald Ollama
verfügbar ist, hier die echten `litellm_params` (model + api_base)
eintragen — das erfordert nur diesen einen Commit, keinen manuellen
Cluster-Eingriff.

## Health-Check

```bash
KUBECONFIG=./kubeconfig kubectl -n litellm port-forward svc/litellm 4000:4000
curl http://localhost:4000/health/liveliness
```
