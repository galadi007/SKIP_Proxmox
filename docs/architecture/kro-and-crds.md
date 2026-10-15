# KRO & Kubernetes CRD-Modell

Ein zentrales Merkmal der **SKIP Plattform** ist die Nutzung von **KRO (Kube Resource Orchestrator)**: Anstatt Helm-Charts oder prozedurale Deploy-Logik im Backend zu pflegen, beschreibt eine einzige generische `ResourceGraphDefinition` (RGD), wie aus einer `Application`-Instanz die Kubernetes-Ressourcen entstehen. Die Templates selbst sind **keine CRDs**, sondern Dateien, die das Backend in diese Instanzen übersetzt.

---

## 🎯 Warum KRO (Kube Resource Orchestrator)?

KRO löst das klassische Problem der Kubernetes-Orchestrierung:
- **Herkömmlich**: Man schreibt entweder komplexe Kubernetes-Operatoren in Go (hoher Wartungsaufwand) oder verwendet Helm/Templates, die außerhalb des Clusters ausgeführt werden und keine Controller-Logik bieten.
- **Mit KRO**: Man definiert einen **Ressourcen-Graphen** in einfachem YAML (`ResourceGraphDefinition`). KRO übernimmt die Erzeugung der CRD, die Abhängigkeitsauflösung, das Instanziieren von Unter-Ressourcen (Deployment, Service, PVC, …) und die Statusaggregation im Cluster.

---

## 🏗️ Die drei Ebenen

```mermaid
classDiagram
    class AppTemplate {
        <<Datei templates/name/template.yaml>>
        +List~Parameter~ parameters
        +List~Capability~ capabilities
        +List~Component~ components
    }

    class Application_CR {
        <<kro.run/v1alpha1, generiert aus der RGD>>
        +String image
        +int port
        +List~EnvVar~ env
        +Resources resources
        +Storage storage
        +Status status
    }

    class CapabilityClaim_CR {
        <<platform.skip.io/v1alpha1>>
        +String type
        +Map properties
        +Binding status.binding
    }

    AppTemplate ..> Application_CR : skip-api rendert
    AppTemplate ..> CapabilityClaim_CR : skip-api legt an (Owner: Application)
    CapabilityClaim_CR ..> Application_CR : Secret per secretKeyRef in env
```

| Ebene | Ressource | Wo | Wer erzeugt sie |
| --- | --- | --- | --- |
| Katalog | `AppTemplate` (Datei) | `templates/<name>/template.yaml` | Template-Autor |
| Instanz | `Application` (CR) | Namespace des Benutzers | `skip-api` beim Deploy |
| Plattformdienst | `CapabilityClaim` (CR) | Namespace des Benutzers | `skip-api` beim Deploy, bearbeitet vom `capability-operator` |

Das AppTemplate-Format ist im [Template-Modell](template-model.md) beschrieben.

---

## 1. Die generische `Application`-RGD (`deploy/crds/application-rgd.yaml`)

`make bootstrap` installiert die RGD; KRO erzeugt daraus die CRD `applications.kro.run`. Eine Instanz entspricht **einer Komponente** eines Templates:

```yaml
apiVersion: kro.run/v1alpha1
kind: ResourceGraphDefinition
metadata:
  name: application
spec:
  schema:
    apiVersion: v1alpha1
    kind: Application
    types:                        # Kubernetes-Form, wird 1:1 durchgereicht
      EnvVar:        { name, value, valueFrom.secretKeyRef.{name,key} }
      ContainerPort: { name, containerPort, protocol }
      ServicePort:   { name, port, targetPort }
      VolumeMount:   { name, mountPath }
      Volume:        { name, persistentVolumeClaim.claimName }
    spec:
      app: string | default=""          # Gruppierung: App und Komponente
      component: string | default=""
      image: string | required=true
      command: "[]string | default=[]"
      args: "[]string | default=[]"
      ports: "[]ContainerPort | default=[]"
      servicePorts: "[]ServicePort | default=[]"   # leer = kein Service
      env: "[]EnvVar | default=[]"
      resources:
        requests: { cpu: string | default="100m", memory: string | default="64Mi" }
        limits:   { cpu: string | default="500m", memory: string | default="256Mi" }
      storage: { enabled: boolean | default=false, size: string | default="1Gi" }
      volumes: "[]Volume | default=[]"
      volumeMounts: "[]VolumeMount | default=[]"
      ingress: { enabled: boolean | default=false, host: string, className: string | default="traefik", portName: string | default="http" }
    status:
      availableReplicas: ${deployment.status.?availableReplicas.orValue(0)}
      readyReplicas: ${deployment.status.?readyReplicas.orValue(0)}
      desiredReplicas: ${deployment.spec.replicas}

  resources:
    - id: serviceAccount
    - id: storage                          # PVC, nur wenn storage.enabled
      includeWhen: [ "${schema.spec.storage.enabled}" ]
    - id: service                          # nur wenn servicePorts vorhanden
      includeWhen: [ "${size(schema.spec.servicePorts) > 0}" ]
    - id: ingress                          # nur wenn ingress.enabled (HTTP-Komponenten)
      includeWhen: [ "${schema.spec.ingress.enabled}" ]
    - id: deployment                       # Container mit image, command, args, ports, env, …
      readyWhen:
        - ${deployment.status.?availableReplicas.orValue(0) == deployment.spec.replicas}
```

Drei Details sind wichtig:

- **Listen als eigene Typen**: KRO kann in CEL-Ausdrücken keine neuen Objekte bauen, aber Listen mit definiertem Typ unverändert durchreichen. Deshalb rendert das Backend `env`, `ports`, `volumes` usw. bereits in Kubernetes-Form (inklusive `secretKeyRef` für Capability-Bindings).
- **Leere Listen werden weggelassen** (`size(x) > 0 ? x : null`): Kubernetes verwirft leere Listen, KRO sähe sonst bei jedem Abgleich ein Delta und bliebe dauerhaft in „resource update in progress“.
- **Optionale Status-Zugriffe** (`?` und `orValue`): `availableReplicas` fehlt, solange kein Pod Ready war. Ohne Absicherung könnte KRO die Instanz weder aktualisieren noch löschen. Der Service steht vor dem Deployment, damit er sofort und nicht erst nach dessen `readyWhen` entsteht.

Alle erzeugten Ressourcen tragen `app.kubernetes.io/part-of: <app>` und `app.kubernetes.io/component: <komponente>`:

```bash
kubectl get all,pvc -n team-data -l app.kubernetes.io/part-of=my-webui
```

### Beispiel einer gerenderten Instanz (Open WebUI, Komponente `open-webui`)

```yaml
apiVersion: kro.run/v1alpha1
kind: Application
metadata:
  name: my-webui-open-webui             # <app>-<komponente>
  namespace: team-data
  labels:
    platform.skip.de/owner: max.mustermann
    platform.skip.de/template: open-webui
    platform.skip.de/app: my-webui
    platform.skip.de/component: open-webui
spec:
  app: my-webui
  component: open-webui
  image: ghcr.io/open-webui/open-webui:v0.6.15
  ports: [ { name: http, containerPort: 8080, protocol: TCP } ]
  servicePorts: [ { name: web, port: 8080, targetPort: http } ]
  env:
    - { name: DATABASE_URL, value: "postgresql://webui:webui@my-webui-postgres:5432/webui" }
    - { name: ENABLE_OLLAMA_API, value: "false" }
    - name: OPENAI_API_BASE_URL
      valueFrom: { secretKeyRef: { name: my-webui-llm-credentials, key: endpoint } }
    - name: OPENAI_API_KEY
      valueFrom: { secretKeyRef: { name: my-webui-llm-credentials, key: api-key } }
  resources:
    requests: { cpu: 250m, memory: 512Mi }
    limits:   { cpu: "2",  memory: 4Gi }
  storage: { enabled: true, size: 2Gi }
  volumes: [ { name: data, persistentVolumeClaim: { claimName: my-webui-open-webui } } ]
  volumeMounts: [ { name: data, mountPath: /app/backend/data } ]
  ingress: { enabled: true, host: my-webui.team-data.apps.localhost, className: traefik, portName: web }
```

Die zweite Komponente `postgres` wird zur Instanz `my-webui-postgres` mit eigenem Service (`5432`) und PVC.

---

## 2. `CapabilityClaim` (`platform.skip.io/v1alpha1`)

Die CRD liegt unter `deploy/crds/capabilityclaims-crd.yaml` und gehört zum `capability-operator`. Für jede aktive Capability eines Templates legt das Backend einen Claim an:

```yaml
apiVersion: platform.skip.io/v1alpha1
kind: CapabilityClaim
metadata:
  name: my-webui-llm          # <app>-<capability>
  namespace: team-data
  ownerReferences:            # gehört allen Komponenten-Instanzen der App
    - { apiVersion: kro.run/v1alpha1, kind: Application, name: my-webui-open-webui, uid: … }
    - { apiVersion: kro.run/v1alpha1, kind: Application, name: my-webui-postgres, uid: … }
spec:
  type: llm-access
  properties:
    models: [mistral-small, mistral-large]
```

Der Operator provisioniert den Dienst (z. B. einen virtuellen LiteLLM-Key), schreibt `endpoint` und `api-key` in das Secret `<claim>-credentials` und setzt `status.binding` sowie die `Ready`-Condition. Details: [Capability-Operator](../components/capability-operator.md).

---

## ⚡ Wie KRO, Operator und Backend interagieren

1. **Bootstrap**: `make bootstrap` wendet `deploy/crds/` an; KRO erzeugt die CRD `applications.kro.run`.
2. **Deploy**: `skip-api` validiert die Parameter, rendert das AppTemplate zu einer `Application`-Instanz je Komponente (Dry-Run für alle, dann Create) und legt die `CapabilityClaim`s mit `ownerReferences` auf alle Instanzen an.
3. **KRO reconciled**: Aus jeder Instanz entstehen ServiceAccount, Service, PVC und Deployment. Pods warten (`CreateContainerConfigError`), bis referenzierte Claim-Secrets existieren.
4. **Operator provisioniert**: Der `capability-operator` bearbeitet die Claims und legt die Secrets an; der Pod startet.
5. **Status**: KRO spiegelt `availableReplicas` in den Instanz-Status; `skip-api` leitet daraus `Deploying`/`Running`/`Failed` ab.
6. **Löschen**: `DELETE /api/apps/…` entfernt alle Instanzen der App; Kubernetes räumt Claims und Secrets per Garbage Collection auf, sobald die letzte Instanz weg ist, der Operator den externen Key.

```bash
kubectl get rgd                                   # application  Active
kubectl get applications.kro.run,claims -n team-data
kubectl describe applications.kro.run my-webui-open-webui -n team-data
```
