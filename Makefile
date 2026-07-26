SHELL := /bin/bash

SERVER_IP ?= 192.168.0.165
SERVER_USER ?= ubuntu
KUBECONFIG_FILE ?= $(CURDIR)/kubeconfig
KUBECTL = KUBECONFIG=$(KUBECONFIG_FILE) kubectl
ANSIBLE_ARGS ?=
ARGOCD_VERSION ?= v3.4.4
ARGOCD_INSTALL_URL ?= https://raw.githubusercontent.com/argoproj/argo-cd/$(ARGOCD_VERSION)/manifests/install.yaml

.PHONY: bootstrap tls kubeconfig test argocd-bootstrap deploy wait-core status \
	argocd-password argocd-ui urls

# Ubuntu vorbereiten, k3s installieren und die lokale TLS-CA erzeugen.
bootstrap:
	bash ./bootstrap.sh $(ANSIBLE_ARGS)

# Nur Zertifikate, TLS-Secrets und Harbor-Vertrauen auf einem bestehenden Cluster aktualisieren.
tls:
	ansible-playbook -i ansible/inventory.ini ansible/site.yml --tags tls $(ANSIBLE_ARGS)

# kubeconfig erneut vom Server holen. Das vollständige Bootstrap erledigt dies bereits automatisch.
kubeconfig:
	@test ! -d "$(KUBECONFIG_FILE)" || \
	  (echo "Fehler: $(KUBECONFIG_FILE) ist ein Verzeichnis." >&2; exit 1)
	scp "$(SERVER_USER)@$(SERVER_IP):/etc/rancher/k3s/k3s.yaml" "$(KUBECONFIG_FILE)"
	sed -i 's/127.0.0.1/$(SERVER_IP)/g' "$(KUBECONFIG_FILE)"
	chmod 600 "$(KUBECONFIG_FILE)"
	@echo "kubeconfig gespeichert: $(KUBECONFIG_FILE)"

# Cluster-Verbindung prüfen.
test:
	$(KUBECTL) get nodes

# ArgoCD installieren und das App-of-Apps-Manifest initial anwenden.
argocd-bootstrap:
	$(KUBECTL) create namespace argocd --dry-run=client -o yaml | \
	  $(KUBECTL) apply -f -
	$(KUBECTL) apply -n argocd \
	  -f "$(ARGOCD_INSTALL_URL)" \
	  --server-side
	@echo "Warte, bis ArgoCD bereit ist ..."
	$(KUBECTL) wait --for=condition=available \
	  deployment/argocd-server -n argocd --timeout=300s
	$(KUBECTL) apply -f argocd/app-of-apps.yaml
	$(KUBECTL) annotate application app-of-apps -n argocd \
	  argocd.argoproj.io/refresh=hard --overwrite
	$(MAKE) wait-core
	@echo "ArgoCD Bootstrap abgeschlossen."

# Änderungen nach einem Git-Push in den bestehenden Cluster übernehmen.
deploy:
	$(KUBECTL) apply -f argocd/app-of-apps.yaml
	$(KUBECTL) annotate application app-of-apps -n argocd \
	  argocd.argoproj.io/refresh=hard --overwrite
	$(MAKE) wait-core

# Auf alle Core-Applications warten und ArgoCD für server.insecure neu starten.
wait-core:
	@for app in traefik harbor argocd; do \
	  echo "Warte auf $$app ..."; \
	  for attempt in $$(seq 1 120); do \
	    state="$$( $(KUBECTL) get application "$$app" -n argocd \
	      -o jsonpath='{.status.sync.status}/{.status.health.status}' 2>/dev/null || true )"; \
	    if [[ "$$state" == "Synced/Healthy" ]]; then \
	      echo "$$app: $$state"; \
	      break; \
	    fi; \
	    if [[ "$$attempt" -eq 120 ]]; then \
	      echo "Timeout bei $$app, letzter Status: $${state:-nicht vorhanden}" >&2; \
	      exit 1; \
	    fi; \
	    sleep 5; \
	  done; \
	done
	$(KUBECTL) rollout restart deployment/argocd-server -n argocd
	$(KUBECTL) rollout status deployment/argocd-server -n argocd --timeout=180s

# Kompakte Zustandsübersicht.
status:
	$(KUBECTL) get applications -n argocd
	$(KUBECTL) get pods -A
	$(KUBECTL) get ingressroute.traefik.io -A

# Initiales ArgoCD-Admin-Passwort anzeigen.
argocd-password:
	@$(KUBECTL) -n argocd get secret argocd-initial-admin-secret \
	  -o jsonpath='{.data.password}' | base64 -d
	@echo

# Port-Forward als Fallback zur direkten Ingress-Adresse.
argocd-ui:
	@echo "ArgoCD UI: http://localhost:8080 (User: admin)"
	$(KUBECTL) port-forward svc/argocd-server -n argocd 8080:80

urls:
	@echo "ArgoCD: https://argocd.192-168-0-165.sslip.io:30443"
	@echo "Harbor: https://harbor.192-168-0-165.sslip.io:30443"
