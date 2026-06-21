.PHONY: bootstrap kubeconfig test argocd-bootstrap argocd-password argocd-ui

# k3s auf dem Server installieren (via Ansible)
bootstrap:
	./bootstrap.sh

# kubeconfig vom Server holen und lokal verfügbar machen
kubeconfig:
	scp gaming:/etc/rancher/k3s/k3s.yaml ./kubeconfig
	sed -i 's/127.0.0.1/172.17.204.135/g' ./kubeconfig
	@echo "kubeconfig gespeichert. Aktivieren mit:"
	@echo "  export KUBECONFIG=\$$(pwd)/kubeconfig"

# Cluster-Verbindung prüfen
test:
	KUBECONFIG=./kubeconfig kubectl get nodes

# ArgoCD + App-of-Apps installieren
argocd-bootstrap:
	KUBECONFIG=./kubeconfig kubectl create namespace argocd --dry-run=client -o yaml | \
	  KUBECONFIG=./kubeconfig kubectl apply -f -
	KUBECONFIG=./kubeconfig kubectl apply -n argocd \
	  -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml \
	  --server-side
	@echo "Warte bis ArgoCD bereit ist..."
	KUBECONFIG=./kubeconfig kubectl wait --for=condition=available \
	  deployment/argocd-server -n argocd --timeout=300s
	KUBECONFIG=./kubeconfig kubectl apply -f argocd/app-of-apps.yaml
	@echo ""
	@echo "=== ArgoCD Bootstrap abgeschlossen ==="
	@echo "Cluster ist jetzt GitOps-fähig."
	@echo "Passwort abrufen: make argocd-password"

# ArgoCD Admin-Passwort anzeigen
argocd-password:
	@KUBECONFIG=./kubeconfig kubectl -n argocd get secret argocd-initial-admin-secret \
	  -o jsonpath="{.data.password}" | base64 -d
	@echo ""

# ArgoCD Web UI per Port-Forward öffnen
argocd-ui:
	@echo "ArgoCD UI: https://localhost:8080  (User: admin)"
	KUBECONFIG=./kubeconfig kubectl port-forward svc/argocd-server -n argocd 8080:443
