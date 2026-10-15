# Plattformdienste deployen


## Lokal testen (k3d)

`make local-up` legt den k3d-Cluster `skip-local` an (`deploy/local/k3d-cluster.yaml`)
und installiert die Charts direkt per Helm, ohne ArgoCD. Damit lassen sich auch
nicht gepushte Änderungen testen. Pro Chart wird `values.yaml` geladen und, falls
vorhanden, `values-local.yaml` darübergelegt (lokale Hostnamen, kleinere
Ressourcen/Volumes). Die ArgoCD-Applications nutzen nur `values.yaml`.

- kubeconfig: `export KUBECONFIG=$(pwd)/kubeconfig-local`
- Ingress: `127.0.0.1:8080` (HTTP) und `127.0.0.1:8443` (HTTPS)
- Authentik: https://authentik.localhost:8443
- Entfernen: `make local-down`
