# Core-Anwendungen

Dieses Verzeichnis enthält die zwingend benötigten Plattformkomponenten:

- `traefik`: Ingress Controller und NodePorts
- `harbor`: interne Container Registry
- `argocd`: ArgoCD-Parameter und externe IngressRoute

Die Verzeichnisse werden von den Applications unter `argocd/core/` verwaltet.
Änderungen werden nach einem Git-Push mit `make deploy` ausgerollt.
