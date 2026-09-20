.PHONY: bootstrap kubeconfig test git-remote argocd-bootstrap argocd-password argocd-port-forward check-env

# check-env ist aus technischen Gründen das erste Target in der Datei
# (Variablen/Validierung müssen vor den anderen Targets stehen) und würde
# damit sonst zum impliziten Default-Goal von `make` werden. bootstrap
# bleibt das eigentliche Default-Goal.
.DEFAULT_GOAL := bootstrap

# Zentrale Projektkonfiguration und optionale lokale Abweichungen einbinden.
include apps/core/cluster-host/skip-settings.conf
-include .env
export

VALID_ENVS := productive development test

# Wird aus Benutzer und IP der zentralen Konfiguration abgeleitet.
SKIP_SSH_HOST = $(SKIP_SSH_USER)@$(SKIP_SERVER_IP)

# Prüft, ob SKIP_ENV gesetzt und gültig ist
check-env:
ifeq ($(filter $(SKIP_ENV),$(VALID_ENVS)),)
	$(error Ungültiger SKIP_ENV-Wert '$(SKIP_ENV)'. Erlaubt: $(VALID_ENVS). Siehe .env.example)
endif
	@echo ">> SKIP_ENV=$(SKIP_ENV)"

# k3s auf dem Server installieren (via Ansible)
# development: kein eigener Server-Bootstrap nötig, bestehender Server wird genutzt
bootstrap: check-env
ifeq ($(SKIP_ENV),development)
	@echo "SKIP_ENV=development: Ansible-Provisioning wird übersprungen (bestehender Server wird verwendet)."
else
	./bootstrap.sh
endif

# kubeconfig vom Server holen und lokal verfügbar machen
kubeconfig: check-env
	scp -i $(SKIP_SSH_PRIVATE_KEY_FILE) $(SKIP_SSH_HOST):/etc/rancher/k3s/k3s.yaml ./kubeconfig
	sed -i 's/127.0.0.1/$(SKIP_SERVER_IP)/g' ./kubeconfig
	@echo "kubeconfig gespeichert. Aktivieren mit:"
	@echo "  export KUBECONFIG=\$$(pwd)/kubeconfig"

# Cluster-Verbindung prüfen
test: check-env
	KUBECONFIG=./kubeconfig kubectl get nodes

# Lokalen Git-Remote mit der zentral konfigurierten Repository-URL abgleichen
git-remote: check-env
	git remote set-url origin "$(SKIP_REPOSITORY_URL)"
	@echo "Git-Remote origin: $$(git remote get-url origin)"

# ArgoCD + GitOps-Applications installieren
argocd-bootstrap: check-env
	KUBECONFIG=./kubeconfig kubectl create namespace argocd --dry-run=client -o yaml | \
	  KUBECONFIG=./kubeconfig kubectl apply -f -
	KUBECONFIG=./kubeconfig kubectl apply -n argocd \
	  -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml \
	  --server-side
	@echo "Warte bis ArgoCD bereit ist..."
	KUBECONFIG=./kubeconfig kubectl wait --for=condition=available \
	  deployment/argocd-server -n argocd --timeout=300s
	KUBECONFIG=./kubeconfig kubectl apply -k .

	@echo "Warte, bis das ApplicationSet die Applications erzeugt hat..."
	KUBECONFIG=./kubeconfig kubectl wait \
	  --for=create application/core-apps -n argocd --timeout=120s

	@echo "Warte, bis die ArgoCD-Application synchronisiert ist..."
	KUBECONFIG=./kubeconfig kubectl wait \
	  --for=jsonpath='{.status.sync.status}'=Synced \
	  application/core-apps -n argocd --timeout=300s

	KUBECONFIG=./kubeconfig kubectl rollout restart \
	  deployment/argocd-server -n argocd

	KUBECONFIG=./kubeconfig kubectl rollout status \
	  deployment/argocd-server -n argocd --timeout=300s

	@echo ""
	@echo "=== ArgoCD Bootstrap abgeschlossen ==="
	@echo "Cluster ist jetzt GitOps-fähig."
	@echo "Passwort abrufen: make argocd-password"

# ArgoCD Admin-Passwort anzeigen
argocd-password:
	@KUBECONFIG=./kubeconfig kubectl -n argocd get secret argocd-initial-admin-secret \
	  -o jsonpath="{.data.password}" | base64 -d
	@echo ""

# ArgoCD Web UI per Port-Forward öffnen (Debug/Fallback)
argocd-port-forward:
	@echo "ArgoCD UI: http://localhost:8080  (User: admin)"
	KUBECONFIG=./kubeconfig kubectl port-forward svc/argocd-server -n argocd 8080:80
