.PHONY: bootstrap kubeconfig test argocd-bootstrap argocd-password argocd-port-forward check-env set-remote versions-sync versions-check local-up local-down

# Ein einfaches make startet weiterhin den Bootstrap.
.DEFAULT_GOAL := bootstrap

# .env einbinden (steuert per SKIP_ENV, welche Umgebung installiert wird)
-include .env
export

SKIP_ENV ?= development
VALID_ENVS := productive development test
PYTHON ?= /usr/bin/python3

# Lokale Versionspflege; keine Verbindung zum Cluster.
versions-sync:
# 	$(PYTHON) scripts/versions.py sync
	
versions-check:
# 	$(PYTHON) scripts/versions.py check
	

# Zielserver: SSH-Alias (siehe ~/.ssh/config, Phase 2.3) und öffentliche IP.
# Defaults entsprechen dem aktuellen FH-Server (ubuntu); für einen anderen
# Zielhost beides in .env überschreiben. Für die Ingress-Hostnamen
# (sslip.io) siehe deploy/charts/authentik/values.yaml.
SKIP_SSH_HOST ?= ubuntu@192.168.0.166
SKIP_SERVER_IP ?= 192.168.0.166

# Alternative zum SSH-Alias oben: explizite Zielangabe ohne ~/.ssh/config,
# z.B. für CI oder wenn kein Alias eingerichtet werden kann/soll. Wird
# SKIP_SSH_USER in .env gesetzt, überschreibt das den Alias-Default oben und
# baut SKIP_SSH_HOST automatisch aus SKIP_SSH_USER@SKIP_SERVER_IP. Beide
# Variablen leer lassen, um beim Alias zu bleiben. SKIP_SSH_PRIVATE_KEY_FILE
# ist optional und wird nur an scp durchgereicht, wenn gesetzt.
SKIP_SSH_USER ?=
SKIP_SSH_PRIVATE_KEY_FILE ?=
ifdef SKIP_SSH_USER
SKIP_SSH_HOST = $(SKIP_SSH_USER)@$(SKIP_SERVER_IP)
endif

# Repository-URL für `make set-remote` (siehe dort). Leer lassen, wenn der
# lokale Origin-Remote nicht per Makefile umgeschrieben werden soll.
SKIP_REPOSITORY_URL ?= git@github.com:galadi007/SKIP_Proxmox.git

# Prüft, ob SKIP_ENV gesetzt und gültig ist
check-env:
ifeq ($(filter $(SKIP_ENV),$(VALID_ENVS)),)
	$(error Ungültiger SKIP_ENV-Wert '$(SKIP_ENV)'. Erlaubt: $(VALID_ENVS). Siehe .env.example)
endif
	@echo ">> SKIP_ENV=$(SKIP_ENV)"
	@echo ">> SKIP_SSH_HOST=$(SKIP_SSH_HOST)"

# k3s auf dem Server installieren (via Ansible)
# development: kein eigener Server-Bootstrap nötig, bestehender Server wird genutzt
bootstrap: check-env versions-check
ifeq ($(SKIP_ENV),development)
	@echo "SKIP_ENV=development: Ansible-Provisioning wird übersprungen (bestehender Server wird verwendet)."
else
	./scripts/bootstrap.sh
endif

# kubeconfig vom Server holen und lokal verfügbar machen
kubeconfig: check-env
	scp $(if $(SKIP_SSH_PRIVATE_KEY_FILE),-i $(SKIP_SSH_PRIVATE_KEY_FILE)) $(SKIP_SSH_HOST):/etc/rancher/k3s/k3s.yaml ./kubeconfig
	sed -i 's/127.0.0.1/$(SKIP_SERVER_IP)/g' ./kubeconfig
	@echo "kubeconfig gespeichert. Aktivieren mit:"
	@echo "  export KUBECONFIG=\$$(pwd)/kubeconfig"

# Lokalen Origin-Remote auf SKIP_REPOSITORY_URL umstellen (z.B. eigener
# Fork). Bewusst kein Bestandteil von bootstrap/kubeconfig/etc. - läuft nur
# auf expliziten Aufruf, mit Bestätigung vor dem eigentlichen Umschreiben.
set-remote:
ifeq ($(strip $(SKIP_REPOSITORY_URL)),)
	$(error SKIP_REPOSITORY_URL ist nicht gesetzt. Siehe .env.example)
endif
	@echo "Setze Origin von $$(git remote get-url origin) auf $(SKIP_REPOSITORY_URL)"
	@read -p "Fortfahren? [y/N] " confirm && [ "$$confirm" = "y" ]
	git remote set-url origin "$(SKIP_REPOSITORY_URL)"

# Cluster-Verbindung prüfen
test: check-env
	KUBECONFIG=./kubeconfig kubectl get nodes

# ArgoCD + GitOps-Applications installieren
argocd-bootstrap:
	@echo "ArgoCD installieren"
	helm dependency build ./deploy/charts/argocd/
	KUBECONFIG=./kubeconfig helm upgrade --install argocd ./deploy/charts/argocd/ \
		--namespace argocd \
		--create-namespace \
		--set-file argo-cd.configs.credentialTemplates.github-ssh.sshPrivateKey=./keys/argocd-github-key


	@echo "Warte bis ArgoCD bereit ist..."
	KUBECONFIG=./kubeconfig kubectl wait --for=condition=available \
	  deployment/argocd-server deployment/argocd-repo-server -n argocd --timeout=300s
	KUBECONFIG=./kubeconfig kubectl apply -f deploy/argocd/root-app.yaml

	@echo "Warte, bis die ArgoCD-Application synchronisiert ist..."
	KUBECONFIG=./kubeconfig kubectl wait \
	  --for=jsonpath='{.status.sync.status}'=Synced \
	  application/root -n argocd --timeout=300s

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

# Lokaler k3d-Cluster mit den Charts aus deploy/charts (ohne ArgoCD,
# values.yaml + values-local.yaml). Siehe scripts/install-local.sh.
local-up:
	./scripts/install-local.sh

local-down:
	k3d cluster delete skip-local
	rm -f ./kubeconfig-local
