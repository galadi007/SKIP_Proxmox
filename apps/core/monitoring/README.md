# Monitoring

Der Ordner installiert den offiziellen `kube-prometheus-stack` mit:

- Prometheus mit 7 Tagen Aufbewahrung auf einem 10-GiB-PVC
- Grafana mit persistentem 2-GiB-PVC
- Alertmanager mit persistentem 1-GiB-PVC
- Prometheus Operator, Node Exporter und kube-state-metrics
- Grafana-Zugriff ueber Traefik unter
  `https://grafana.<SKIP_SERVER_IP>.sslip.io`

Prometheus und Alertmanager bleiben clusterintern. Die fuer k3s nicht passend
auffindbaren separaten Control-Plane-Ziele sind deaktiviert, damit keine
falschen `TargetDown`-Alarme entstehen.

## Grafana-Zugangsdaten erzeugen

Vor dem Commit muss einmalig das verschluesselte Grafana-Secret erzeugt werden:

```bash
export KUBECONFIG="$(pwd)/kubeconfig"
chmod +x apps/core/monitoring/generate-grafana-secret.sh
apps/core/monitoring/generate-grafana-secret.sh
```

Das Skript fragt Benutzername und Passwort verdeckt ab und schreibt nur die
verschluesselte Datei `grafana-admin-sealedsecret.yaml`. Das Klartext-Secret
wird nicht auf der Festplatte gespeichert.

Danach koennen alle Monitoring-Dateien committed werden:

```bash
git add argocd/applicationset.yaml apps/core/monitoring README.md apps/core/README.md
git commit -m "Add Prometheus and Grafana monitoring"
git push origin main
```

## Synchronisation und Kontrolle

```bash
kubectl -n argocd annotate application core-apps \
  argocd.argoproj.io/refresh=hard --overwrite

kubectl -n argocd get application monitoring

kubectl -n argocd annotate application monitoring \
  argocd.argoproj.io/refresh=hard --overwrite

kubectl -n monitoring get pods,pvc
kubectl -n monitoring get sealedsecret,secret grafana-admin-credentials
```

Die Zugangsdaten koennen lokal kontrolliert werden, ohne das Passwort
auszugeben:

```bash
kubectl -n monitoring get secret grafana-admin-credentials \
  -o jsonpath='{.data.admin-user}' | base64 -d
echo
```

Hinweis: Grafana uebernimmt das Admin-Passwort beim erstmaligen Initialisieren
seiner Datenbank. Eine spaetere Passwortaenderung am SealedSecret allein setzt
das bereits gespeicherte Grafana-Passwort nicht automatisch zurueck.
