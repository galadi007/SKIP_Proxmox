# apps/services

Begleitende Plattform-Dienste, übernommen aus PG-SKIP-Platform — wird von
der ArgoCD-App-of-Apps (`argocd/core-apps.yaml` → `argocd/core/`)
automatisch synchronisiert. Jeder Unterordner entspricht einer eigenen
ArgoCD-`Application`, jeweils ohne externen Ingress (`ClusterIP`).

| Ordner | Dienst | Zweck | ArgoCD-Application |
|---|---|---|---|
| `litellm/` | LiteLLM | AI-Gateway/Proxy (OpenAI-kompatible API) | `argocd/core/litellm.yaml` |
| `minio/` | MinIO | S3-kompatibler Objektspeicher | `argocd/core/minio.yaml` |

Details je Dienst (Secrets, Health-Check, Betrieb): siehe die README.md im
jeweiligen Unterordner sowie das Haupt-`README.md` im Repo-Root.
