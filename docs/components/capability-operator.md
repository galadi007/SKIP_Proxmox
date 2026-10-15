# Capability-Operator

Der Capability-Operator (`apps/capability-operator/`) ist ein
[Kopf](https://kopf.readthedocs.io)-Operator, der `CapabilityClaim`-Ressourcen
(`platform.skip.io/v1alpha1`) bearbeitet. Eine Anwendung fordert damit einen
Plattform-Service an, zum Beispiel Zugang zum LLM-Gateway; der Operator legt
die nötigen externen Ressourcen an und schreibt Endpunkt und Secret-Referenz
nach `.status.binding`. Die eigentlichen Dienste implementieren Plugins unter
`plugins/capabilities/` gegen die Schnittstelle in `packages/skip-capability-sdk/`.

Deployment und RBAC liegen unter `deploy/capability-operator/`, die CRD unter
`deploy/crds/capabilityclaims-crd.yaml` (angewendet durch `make bootstrap`).
Im lokalen Dev-Loop wird das Image von Skaffold gebaut; da Kopf Code nicht neu
lädt, gibt es keinen File-Sync, sondern einen Image-Rebuild.

Die folgende Beschreibung ist die README des Operators.

---

--8<-- "apps/capability-operator/README.md"
