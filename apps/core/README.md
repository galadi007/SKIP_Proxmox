# apps/core

Kern-Infrastruktur des Clusters — wird von der ArgoCD-App-of-Apps
(`argocd/core-apps.yaml` → `argocd/core/`) automatisch synchronisiert.
Jeder Unterordner entspricht einer eigenen ArgoCD-`Application`.

| Ordner | Komponente | ArgoCD-Application |
|---|---|---|
| `argocd/` | ArgoCD verwaltet sich selbst (Ingress, `server.insecure`-ConfigMap) | `argocd/core/argocd.yaml` |
| `traefik/` | Ingress Controller (NodePort 30080/30443) | `argocd/core/traefik.yaml` |
| `harbor/` | Container Registry | `argocd/core/harbor.yaml` |
| `sealed-secrets/` | Secrets-Verschlüsselung für GitOps (Bitnami Sealed Secrets) | `argocd/core/sealed-secrets.yaml` |
| `cluster-host/` | zentrale Quelle für den Cluster-Host, wird von `argocd/` und `harbor/` per Kustomize eingebunden — keine eigene ArgoCD-Application | – |

Details je Komponente: siehe Haupt-`README.md` im Repo-Root (Phasen 7–9) und
die jeweiligen Manifeste.
