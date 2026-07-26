# Fachliche Dienste

Hier können später zusätzliche SKIP-Anwendungen wie Qdrant, Open WebUI, n8n
oder Jupyter als eigene GitOps-Manifeste abgelegt werden.

Jeder Dienst erhält ein eigenes Unterverzeichnis und eine zugehörige ArgoCD
Application. Die Core-Komponenten unter `apps/core/` bleiben davon getrennt.
