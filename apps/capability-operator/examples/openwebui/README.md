# Beispiel: Open WebUI an LiteLLM binden

Zeigt von Hand, wie eine Anwendung über einen `CapabilityClaim` LLM-Zugang
bekommt, ohne den LiteLLM-Master-Key zu kennen. Über die Plattform passiert
dasselbe automatisch: `templates/openwebui/template.yaml` fordert die
Capability an, und `skip-api` legt Claim und Bindings beim Deploy an.

1. `capabilityclaim.yaml` fordert `llm-access` für die Modelle `mistral-small`
   und `mistral-large` an.
2. Der `capability-operator` legt in LiteLLM einen virtuellen Key mit genau
   diesen Modellen an und schreibt ihn in das Secret
   `openwebui-llm-credentials` (Schlüssel `api-key`).
3. `deployment.yaml` liest Key (`OPENAI_API_KEY`, Schlüssel `api-key`) und
   Endpoint (`OPENAI_API_BASE_URL`, Schlüssel `endpoint`) aus dem Secret und
   spricht LiteLLM über dessen OpenAI-kompatible API an.

Das Secret gehört dem Claim (OwnerReference): Wird der Claim gelöscht,
verschwinden Secret und LiteLLM-Key.

## Voraussetzungen

`make init-local` mit gesetztem `MISTRAL_API_KEY` in `deploy/local/.env`
(LiteLLM läuft im Namespace `litellm`, der Operator in `platform-system`,
der Namespace `team-data` existiert).

## Ausführen

```sh
kubectl apply -k apps/capability-operator/examples/openwebui

kubectl get claims -n team-data                      # Ready=True, Provisioned
kubectl get secret openwebui-llm-credentials -n team-data
kubectl get pods -n team-data -w                     # openwebui wird Ready

kubectl -n team-data port-forward svc/openwebui 3000:8080
```

Dann `http://localhost:3000` öffnen. In der Modellauswahl erscheinen
`mistral-small` und `mistral-large`; andere Modelle des Gateways sind mit
diesem Key nicht nutzbar.

Der Pod startet erst, wenn das Secret existiert. Solange der Claim nicht
`Ready` ist, meldet er `CreateContainerConfigError` und startet danach von
selbst.

## Aufräumen

```sh
kubectl delete -k apps/capability-operator/examples/openwebui
```
