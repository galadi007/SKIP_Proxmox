# Aufteilung zwischen Plattform- und Infrastruktur-Repository

## Zielbild

Für die Zusammenführung mit dem dedizierten Infrastruktur-Repository gilt als
Grundregel:

> Das Plattform-Repository verantwortet, **was die Software zum Betrieb
> benötigt**. Das Infrastruktur-Repository verantwortet, **wo und wie sie
> betrieben wird**.

Damit bleiben Anwendungsquellcode, fachliche Kubernetes-Verträge und lokale
Entwicklungswerkzeuge gemeinsam versioniert. Umgebungsabhängige Konfiguration,
Clusterbetrieb und gemeinsam genutzte Dienste liegen dagegen zusammen mit den
Ansible-Playbooks im Infrastruktur-Repository.

## Inhalte des Infrastruktur-Repositorys

Folgende Bestandteile gehören in das Infrastruktur-Repository:

- Ansible-Playbooks, Rollen, Inventories und Host-Konfiguration
- Bereitstellung und Konfiguration der Kubernetes-Cluster
- produktive und Staging-spezifische Namespaces, Quotas und Policies
- Ingress-Controller, DNS, TLS und cert-manager
- StorageClasses und umgebungsspezifische Persistenzkonfiguration
- Monitoring, Logging, Alerting und Backups
- gemeinsam genutzte Plattformdienste wie MinIO und LiteLLM
- Secret Management und ExternalSecret-Ressourcen
- umgebungsspezifische Domains, Replikazahlen und Ressourcenlimits
- Installation und Versionsfestlegung von KRO und anderen Drittkomponenten
- produktive und Staging-Overlays
- GitOps-Konfiguration für Argo CD oder Flux, sofern eingesetzt
- operative Runbooks

Die früher hier gepflegten MinIO-Manifeste, das Produktions-Overlay und die
Namespace-Definitionen wurden aus dem Plattform-Repository entfernt. Die
produktiven LiteLLM-Manifeste gehören ebenfalls in das
Infrastruktur-Repository. Shared Services dürfen nicht implizit Bestandteil
des Deployment-Basisverzeichnisses der Anwendung sein.

Die k3d-Konfiguration (`deploy/local/k3d-cluster.yaml`) und der
`localhost`-Ingress bleiben hier, weil sie eng mit Skaffold und dem lokalen
Mount des Verzeichnisses `templates/` gekoppelt sind. Sie wandern nur dann,
wenn das Infrastruktur-Repository ausdrücklich auch lokale Entwicklungscluster
verwaltet.

## Inhalte des Plattform-Repositorys

Folgende Bestandteile bleiben gemeinsam mit dem Anwendungscode in diesem
Repository:

- Quellcode von `skip-api`, `skip-web` und `capability-operator`
- Dockerfiles und Image-Build-Konfiguration
- CI für Build, Tests und Veröffentlichung der Images
- Skaffold und der lokale Entwicklungsablauf
- von der Anwendung benötigte RBAC-Verträge
- anwendungseigene CRDs und KRO-Definitionen
- Template-Katalog, Template-Schemata und deren Tests
- Workload-Templates
- umgebungsneutrale Kubernetes-Manifeste der Anwendung
- lokale Deployment-Overlays

Für die aktuelle Struktur betrifft dies insbesondere:

```text
apps/
templates/
skaffold.yaml
deploy/skip-api/
deploy/skip-web/
deploy/capability-operator/
deploy/crds/
deploy/local/
```

`make init-local` soll weiterhin vollständig aus diesem Repository heraus
funktionieren. Entwicklerinnen und Entwickler sollen das produktive
Infrastruktur-Repository nicht benötigen, um die Plattform lokal zu starten.

## Aufteilung mehrdeutiger Ressourcen

### RBAC

Die von `skip-api` fachlich benötigten Berechtigungen bleiben nahe am
Anwendungscode. Dazu gehören beispielsweise die erlaubten Kubernetes-APIs und
Verben.

Das Infrastruktur-Repository bestimmt dagegen:

- in welchen Namespaces die Anwendung installiert wird,
- welche produktive ServiceAccount-Identität verwendet wird,
- in welchen Tenant-Namespaces Bindings angelegt werden und
- welche umgebungsspezifischen Einschränkungen gelten.

Idealerweise liefert das Plattform-Release eine möglichst eng gefasste
`Role` oder `ClusterRole`. Das Infrastruktur-Repository erzeugt die konkreten
Bindings für die jeweilige Umgebung.

### CRDs und ResourceGraphDefinitions

Für CRDs und KRO-Ressourcen entscheidet die fachliche Eigentümerschaft:

- Von der SKIP-Plattform definierte Application- und Template-Verträge bleiben
  in diesem Repository.
- Die `CapabilityClaim`-CRD bleibt zusammen mit dem Operator, der sie
  implementiert (`apps/capability-operator`, CRD unter `deploy/crds/`), und
  wird als Teil dessen Releases ausgeliefert.
- CRDs von Drittanbietern werden im Infrastruktur-Repository installiert und
  dort auf eine konkrete Version festgelegt.

Eine CRD darf nicht manuell in beiden Repositorys gepflegt werden.

### Ingress

Ein lokaler Ingress für `localhost` bleibt im Plattform-Repository. Reale
Domains, TLS-Zertifikate, IngressClasses, Provider-Annotationen und External-DNS
gehören in das Infrastruktur-Repository.

### Lokale Shared Services

`init-local` darf weiterhin leichtgewichtige lokale Instanzen von MinIO oder
LiteLLM starten. Diese gelten als Entwicklungs-Fixtures und sind nicht mit den
produktiven Service-Definitionen im Infrastruktur-Repository gleichzusetzen.

Sie sollten eindeutig abgelegt werden, beispielsweise unter:

```text
deploy/local/dependencies/
```

## Empfohlene Repository-Struktur

### Plattform-Repository

```text
PG-SKIP-Platform/
├── apps/
│   ├── skip-api/
│   ├── skip-web/
│   └── capability-operator/
├── templates/
├── deploy/
│   ├── skip-api/
│   ├── skip-web/
│   ├── capability-operator/
│   ├── crds/
│   └── local/
├── skaffold.yaml
└── Makefile
```

Dieser Zustand ist umgesetzt. `deploy/<komponente>/` enthält die
umgebungsneutralen Manifeste samt RBAC, `deploy/crds/` die plattformeigenen
CRDs und KRO-Definitionen, `deploy/local/` ausschließlich den lokalen
Dev-Loop.

### Infrastruktur-Repository

```text
PG-SKIP-Infra/
├── ansible/
│   ├── inventories/
│   ├── roles/
│   └── playbooks/
├── clusters/
│   ├── dev/
│   ├── staging/
│   └── production/
├── platform-services/
│   ├── kro/
│   ├── litellm/
│   └── minio/
├── applications/
│   └── skip-platform/
│       ├── staging/
│       └── production/
└── secrets/
```

## Kopplung der Repositorys

Deployment-Manifeste sollten nicht manuell zwischen den Repositorys kopiert
werden. Stattdessen veröffentlicht das Plattform-Repository ein versioniertes,
unveränderliches Deployment-Artefakt. Geeignete Varianten sind:

1. ein Helm-Chart in einer OCI-Registry,
2. als OCI-Artefakt veröffentlichte Kubernetes-Manifeste oder
3. ein versionierter Git-Tag, den Kustomize referenziert.

Für die SKIP-Plattform wird ein kleines Helm-Chart empfohlen. Das
Infrastruktur-Repository kann damit Images, Ingress, Replikazahlen,
Namespaces, Secrets und Ressourcenlimits konfigurieren, ohne die
Anwendungsmanifeste zu duplizieren.

## Empfohlener Release- und Deployment-Ablauf

1. Die CI des Plattform-Repositorys testet Code und Templates.
2. Sie baut unveränderlich versionierte Images für API und Web-Anwendung.
3. Sie veröffentlicht ein Helm-Chart, das genau diese Image-Versionen
   referenziert.
4. Die CI erstellt automatisiert einen Pull Request im
   Infrastruktur-Repository und aktualisiert dort die Chart-Version.
5. Die CI des Infrastruktur-Repositorys validiert Manifeste und Policies.
6. Nach Freigabe wird die Version durch GitOps oder ein Ansible-Playbook
   ausgerollt.

Ansible sollte Hosts, Cluster und technische Voraussetzungen bereitstellen.
Der eigentliche Kubernetes-Workload sollte möglichst deklarativ über Helm und
GitOps ausgerollt werden. Umfangreiche Kubernetes-Manifeste sollten nicht
dynamisch in Ansible zusammengesetzt werden.

## Vorgeschlagene Migration

Die Umstellung sollte schrittweise erfolgen:

1. ~~Shared Services aus dem Deployment-Basisverzeichnis entfernen.~~ Erledigt.
2. ~~Lokal benötigte Abhängigkeiten explizit aufnehmen.~~ Erledigt: LiteLLM
   als Dev-Fixture unter `deploy/local/dependencies/litellm/`
   (`make install-litellm`).
3. ~~Produktions- und Staging-Overlays in das Infrastruktur-Repository
   verschieben.~~ Aus diesem Repository entfernt.
4. `skip-api`, `skip-web`, `capability-operator`, anwendungseigene CRDs und
   RBAC als ein versioniertes Deployment-Artefakt paketieren.
5. ~~Sicherstellen, dass `make init-local` weiterhin eigenständig
   funktioniert.~~ Erledigt.
6. Das produktive Deployment im Infrastruktur-Repository auf das
   veröffentlichte Artefakt umstellen.
7. Doppelte oder kopierte Manifeste erst entfernen, nachdem das neue Deployment
   in mindestens einer nicht-produktiven Umgebung erfolgreich verifiziert
   wurde.

Diese Aufteilung hält die Entwicklungszyklen der Anwendung kurz, verhindert
Konfigurationsduplikate und gibt dem Infrastruktur-Repository eine klare
Verantwortung für Cluster, Umgebungen und Betrieb.
