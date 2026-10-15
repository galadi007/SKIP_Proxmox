# Umstellung auf SKIP_Proxmox

Dieses Paket ersetzt den bisherigen Repository-Inhalt. Es ist noch nicht auf GitHub oder der VM angewendet.

## Ziel

- Git: git@github.com:galadi007/SKIP_Proxmox.git, Branch main
- VM / SSH: ubuntu@192.168.0.166, Kubernetes-Knoten ubuntu
- k3s: v1.35.4+k3s1 (vorhanden, kein Upgrade vorgesehen)
- Authentik: https://authentik.192-168-0-166.sslip.io:30443
- Traefik: NodePort 30080 / 30443 entsprechend der neuen Vorlage
- ArgoCD: Port-Forward mittels make argocd-port-forward; die neue Vorlage enthält keine ArgoCD-Ingressroute.

Die bisherigen URLs ohne Port werden durch diese neue Vorlage nicht automatisch erhalten.
Externe Image-/Chart-Quellen, lokale Entwicklungsadressen und Projektverweise sind keine Zielserverdaten und bleiben bestehen.

## Vor Austausch im Git

1. VM-Backup in Proxmox erstellen, vorhandene Daten und Secrets sichern. Die PVCs von Harbor, MinIO und Monitoring enthalten weiterhin Bestandsdaten.
2. Aktuelle ArgoCD-Applications und ApplicationSets exportieren; insbesondere Quellen, automatische Synchronisation, OwnerReferences und Finalizer prüfen.
3. Alte GitOps-Steuerung einschließlich übergeordneter Applications geordnet stilllegen. core-apps darf die bisherigen Applications nicht erneut herstellen. Applications oder ApplicationSets nicht unkontrolliert mit Kaskadierung löschen.
4. Lokales Git-Arbeitsverzeichnis sichern und uncommittete Änderungen prüfen. Alten Commit als Rückkehrpunkt behalten. Neuen Inhalt im bestehenden Git-Checkout einspielen, .git sowie lokale Zugangsdaten erhalten. Nicht nur über alte Dateien kopieren: alte versionierte Manifeste müssen aus dem neuen Stand entfernt werden.
5. Änderungen prüfen, committen und nach main pushen. Erst danach neue root-Application aktivieren. Keine automatische Veröffentlichung durch dieses Paket.
6. Bestehende Traefik-/LiteLLM-Ressourcen und ArgoCD-Installation vor Übernahme prüfen. Die neue Struktur ist keine getestete In-place-Migration.

## Einrichtung nach Vorbereitung der Migration

Von WSL aus: .env.example nach .env kopieren, make kubeconfig verwenden.
SSH-Deploy-Key für ArgoCD muss Lesezugriff auf galadi007/SKIP_Proxmox haben.
Die neue Vorlage verwendet Helm für ArgoCD; eine Übernahme der bisherigen Installation muss zuvor geprüft werden.
make bootstrap ist für die vorhandene VM nicht erforderlich.

## Grenzen des gelieferten Stands

Die root-Application verwaltet Traefik, PostgreSQL, Authentik, LiteLLM und Silo.
Harbor, MinIO, Monitoring und Sealed Secrets sind nicht enthalten. Ihre Daten werden nicht migriert oder gelöscht.
Plattform-Frontend, API und Operator sind als Quellcode enthalten, aber nicht als Applications der root-Application eingerichtet.
Die übernommene lokale Entwicklungsdokumentation enthält teilweise veraltete Make-Targets.
scripts/init-secrets.sh aus der Vorlage ist bei teilweise bestehenden Secrets nicht zuverlässig wiederholbar: neu erzeugte DB-Passwörter können von bestehenden Secrets abweichen. Vor Ausführung muss der Secret-Bestand geprüft werden.

## Prüfung dieses Pakets

Zielangaben und Bootstrap-Dateipfade korrigiert; Shell-Syntax, YAML-Lesbarkeit und Make-Dry-Runs geprüft.
Kein Helm-Rendering mit geladenen Abhängigkeiten und kein Deployment-/Cluster-Test durchgeführt.
