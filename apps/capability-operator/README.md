# Capability-Operator

Kopf-Operator, der `CapabilityClaim`-Ressourcen bearbeitet und pro
Capability-Typ (`spec.type`) ein Plugin aufruft. Die Plugins liegen unter
`plugins/capabilities/` und werden beim Start über Python-Entry-Points geladen.
Aktuell ausgeliefert:

| `spec.type`  | Plugin                          | Ergebnis                                       |
| ------------ | ------------------------------- | ---------------------------------------------- |
| `llm-access` | `plugins/capabilities/litellm` | Virtueller LiteLLM-Key als Secret `<claim>-credentials` (Schlüssel `api-key` und `endpoint`) im Namespace |

## Aufbau

```
apps/capability-operator/
├── main.py                     Kopf-Handler: Plugins laden, Statusschreiben, Fehler-Mapping
├── capability_operator/
│   ├── plugins.py              Lädt Plugins aus der Entry-Point-Gruppe `skip.capabilities`
│   └── conditions.py           Ready-Condition fuer den Claim-Status
├── examples/                   Beispiel-Claim und Open-WebUI-Beispiel
└── tests/
packages/skip-capability-sdk/   Schnittstelle: Capability-Protocol, Claim, Binding, Fehlertypen
plugins/capabilities/<name>/    Ein Paket pro Capability (z. B. `litellm`)
```

Eine Capability implementiert `initialize()`, `provision(claim) -> Binding` und
`cleanup(claim)` (`skip_capability_sdk.Capability`). `provision` ist idempotent
und wird bei create, update und resume gleichermaßen aufgerufen. Sie wirft
`InvalidClaimError` (kein Retry) oder `TransientError` (Retry); `main.py`
übersetzt beides in Kopf-Fehler und schreibt die `Ready`-Condition.

Beim Start lädt der Operator alle installierten Entry Points der Gruppe
`skip.capabilities`; der Name des Entry Points ist der `spec.type`, das Ziel
wird ohne Argumente instanziiert. Ein Plugin, das nicht geladen werden kann,
wird protokolliert und übersprungen. Claims mit unbekanntem Typ erhalten
`Ready=False` mit Grund `UnsupportedCapability`.

Direkt nach dem Laden ruft der Operator `initialize()` jedes Plugins auf. Dort
prüft ein Plugin seine Konfiguration und die Erreichbarkeit des externen
Service (LiteLLM etwa Verbindung und Master-Key). Schlägt das fehl, bleibt das
Plugin registriert: Der Operator startet trotzdem und wiederholt
`initialize()` vor jedem `provision`/`cleanup`, bis es gelingt. Betroffene
Claims erhalten solange `Ready=False` mit Grund `CapabilityUnavailable` und
werden erneut versucht.

## Neues Capability-Plugin anlegen

1. Paket `plugins/capabilities/<name>/` mit `src/skip_capability_<name>/`
   anlegen (Vorlage: `plugins/capabilities/litellm`). Es hängt von
   `skip-capability-sdk` ab, nicht vom Operator oder von `kopf`.
2. Eine Klasse mit `initialize`/`provision`/`cleanup` implementieren, die ohne
   Argumente instanziierbar ist (Konfiguration aus Umgebungsvariablen, lazy
   lesen). `initialize` prüft Abhängigkeiten und wirft bei Problemen eine
   `CapabilityError`; braucht das Plugin nichts, bleibt es leer.
3. In der `pyproject.toml` des Plugins registrieren:

   ```toml
   [project.entry-points."skip.capabilities"]
   my-type = "skip_capability_<name>:MyCapability"
   ```

4. In der Root-`pyproject.toml` unter `[tool.uv.sources]` eintragen
   (`plugins/capabilities/*` ist bereits Workspace-Member) und in
   `apps/capability-operator/pyproject.toml` als Extra aufnehmen
   (`<name> = ["skip-capability-<name>"]`, plus in `all`), damit es im Image
   landet. Danach `uv lock`.

## CRD installieren

Die CRD liegt zusammen mit dem Application-RGD unter `deploy/crds/` und wird
per `make bootstrap` angewendet. Manuell:

```sh
kubectl apply -f deploy/crds/capabilityclaims-crd.yaml
kubectl wait --for=condition=Established crd/capabilityclaims.platform.skip.io --timeout=60s
```

## Operator lokal starten (ohne Cluster-Deployment)

```sh
# Konfiguration der Plugins, z. B. fuer llm-access (siehe Plugin-README)
export LITELLM_MASTER_KEY=sk-...
export LITELLM_BASE_URL=http://localhost:4000          # intern, für den Operator
export LITELLM_PUBLIC_BASE_URL=https://llm.example.org # optional, landet in .status.binding.endpoint

# aus dem Repo-Root
uv run --package capability-operator --extra all kopf run apps/capability-operator/main.py --standalone --verbose
```

Ohne In-Cluster-Konfiguration verwendet der Operator die lokale Kubeconfig.

## Beispiel

```sh
kubectl create namespace capability-test
kubectl apply -f apps/capability-operator/examples/llm-access-claim.yaml
kubectl get claims -n capability-test
kubectl get secret my-llm-credentials -n capability-test -o jsonpath='{.data.api-key}' | base64 -d
```

### Anwendung an LiteLLM binden

Der normale Weg ist ein AppTemplate mit `capabilities` und `bindings`
(`templates/openwebui/template.yaml`): `skip-api` legt den Claim beim Deploy an
und verdrahtet `endpoint`/`api-key` aus dem Secret per `secretKeyRef`.

`examples/openwebui/` zeigt dieselbe Anbindung von Hand: Claim, Deployment und
Service für Open WebUI, das Endpoint und Key aus dem Secret liest.

```sh
kubectl apply -k apps/capability-operator/examples/openwebui
kubectl -n team-data port-forward svc/openwebui 3000:8080   # http://localhost:3000
```

Details in `apps/capability-operator/examples/openwebui/README.md`.

## Tests

```sh
uv run --group dev pytest apps/capability-operator packages/skip-capability-sdk plugins/capabilities
```

## Konfiguration

| Variable                  | Standard                             | Bedeutung                                   |
| ------------------------- | ------------------------------------ | ------------------------------------------- |
| `API_GROUP`               | `platform.skip.io`                   | API-Gruppe der CRD                          |
| `API_VERSION`             | `v1alpha1`                           | Version der CRD                             |
| `CAPABILITY_PLUGINS`      | – (alle installierten)               | Kommagetrennte Liste der zu ladenden Plugins (Entry-Point-Namen) |

Plugin-spezifische Variablen stehen in der README des jeweiligen Plugins, z. B.
`LITELLM_*` in `plugins/capabilities/litellm/README.md`.
