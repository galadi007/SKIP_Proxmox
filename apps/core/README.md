# apps/core

Kern-Infrastruktur des Clusters — wird vom zentralen ArgoCD-`ApplicationSet`
in `argocd/applicationset.yaml` automatisch synchronisiert. Jeder Unterordner
entspricht einer erzeugten ArgoCD-`Application`.

| Ordner | Komponente | ArgoCD-Application |
|---|---|---|
| `argocd/` | ArgoCD verwaltet sich selbst (Ingress, `server.insecure`-ConfigMap) | `argocd` |
| `traefik/` | Ingress Controller (Host-Ports 80/443) | `traefik` |
| `harbor/` | Container Registry | `harbor` |
| `sealed-secrets/` | Secrets-Verschlüsselung für GitOps (Bitnami Sealed Secrets) | `sealed-secrets` |
| `cluster-host/` | zentrale Basisdomain für `argocd/` und `harbor/` — keine eigene ArgoCD-Application | – |

Details je Komponente: siehe Haupt-`README.md` im Repo-Root (Phasen 7–9) und
die jeweiligen Manifeste.
