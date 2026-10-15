# Anleitung: Ein neues Template erstellen

Ein Template ist vollständig deklarativ: eine `template.yaml` im Format
[AppTemplate](../architecture/template-model.md), optional eine `README.md`
und ein Logo. Es ist kein Code im Backend oder Frontend nötig und keine eigene
KRO-ResourceGraphDefinition – das Backend übersetzt das Template in eine
Instanz der generischen `Application`-RGD.

In dieser Anleitung entsteht beispielhaft ein Template für **Streamlit**.

---

## 📝 Schritt 1: Verzeichnis anlegen

```bash
mkdir -p templates/streamlit
```

---

## ⚙️ Schritt 2: `template.yaml` schreiben

```yaml
apiVersion: platform.skip.io/v1alpha1
kind: AppTemplate

metadata:
  name: streamlit

spec:
  displayName: Streamlit App
  summary: Interaktive Data-Apps mit Streamlit
  version: 0.1.0
  author: Team Data

  categories: [data-science]
  tags: [python, streamlit, dashboard]

  description:
    format: markdown
    inline: |
      Eine Streamlit-Instanz mit persistentem Arbeitsverzeichnis.

  # Nutzereingaben – daraus generiert das Frontend das Formular
  parameters:
    - name: size
      displayName: Größe
      type: enum
      default: small
      values:
        - name: small
          displayName: Small (0.5 CPU, 1 GiB)
          cpu: 500m
          memory: 1Gi
        - name: medium
          displayName: Medium (1 CPU, 2 GiB)
          cpu: "1"
          memory: 2Gi
    - name: storageSize
      displayName: Speicher
      type: string
      pattern: "^[0-9]+(Mi|Gi)$"
      default: 1Gi
    - name: llmAccess
      displayName: LLM-Zugang
      description: OPENAI_* Variablen für das Plattform-Gateway setzen
      type: boolean
      default: false

  # Optionaler Plattformdienst
  capabilities:
    - name: llm
      type: llm-access
      class: standard
      when: ${parameters.llmAccess}
      properties:
        models: [mistral-small]

  # Die laufende Komponente
  components:
    - name: streamlit
      image: ghcr.io/example/streamlit-app:1.0
      ports:
        - name: http
          containerPort: 8501
      expose:
        - name: web
          type: http
          port: http
      env:
        - name: STREAMLIT_SERVER_HEADLESS
          value: "true"
      resources:
        requests:
          cpu: ${parameters.size.cpu}
          memory: ${parameters.size.memory}
        limits:
          cpu: ${parameters.size.cpu}
          memory: ${parameters.size.memory}
      storage:
        size: ${parameters.storageSize}
        mountPath: /app/data
      bindings:
        - capability: llm
          env:
            endpoint: OPENAI_BASE_URL
            credential: OPENAI_API_KEY
```

Was passiert damit beim Deploy:

- `parameters` werden validiert (Enum-Werte, Muster, Typen) und über `${parameters.…}` in die Komponente eingesetzt. Enum-Werte dürfen beliebige Zusatzfelder tragen (`cpu`, `memory`, `image`, …), die per `${parameters.size.cpu}` erreichbar sind.
- Für jede aktive Capability legt das Backend einen `CapabilityClaim` `<app>-<capability>` an. Der `capability-operator` provisioniert den Dienst und schreibt `endpoint` und `api-key` in das Secret `<app>-<capability>-credentials`.
- `bindings` verdrahten dieses Secret als Umgebungsvariablen (`secretKeyRef`), ohne dass das Template Secrets oder Endpunkte kennen muss.
- Aus jeder Komponente entsteht eine `Application`-Instanz `<app>-<komponente>`; KRO erzeugt Deployment, ServiceAccount, einen Service (wenn `expose` gesetzt ist) und ein PVC (wenn `storage` gesetzt ist).

!!! tip "Mehrere Komponenten"
    Braucht die App z. B. eine Datenbank, wird sie als zweite Komponente ergänzt und über `${components.<name>.host}` (Service-DNS) und `${components.<name>.ports.<port>}` angesprochen. `templates/openwebui/template.yaml` zeigt das mit `open-webui` + `postgres`. Der Deploy-Status fasst alle Komponenten zusammen; Löschen entfernt alle.

Optional: `README.md` (über `description.file`) und ein Logo (`logo.file`) im selben Verzeichnis ablegen, so wie `templates/jupyter/`.

---

## 🚀 Schritt 3: Testen

`templates/` ist als Host-Volume in den k3d-Cluster gemountet und das Backend liest `template.yaml` direkt von dort. Es ist kein Apply-Schritt nötig, nur ein erneutes Einlesen des Katalogs:

```bash
curl -X POST -H 'X-User: dev@skip.de' http://api.localhost:8080/api/templates/reload
curl -s -H 'X-User: dev@skip.de' http://api.localhost:8080/api/templates/streamlit | jq .parameters
```

1. `make test` – die Backend-Tests laden alle Templates aus `templates/` und schlagen fehl, wenn eine `template.yaml` ungültig ist (z. B. ein Binding auf eine unbekannte Capability oder ein `expose` auf einen unbekannten Port).
2. Web-UI unter [http://localhost:8080](http://localhost:8080) öffnen: Das Template erscheint im Katalog, das Formular zeigt die Parameter mit ihren `displayName`s.
3. Deploy klicken und beobachten:

```bash
kubectl get applications.kro.run,claims -n team-data
kubectl get all,pvc -n team-data -l app.kubernetes.io/part-of=<app-name>
```

Ohne LLM-Zugang startet der Pod sofort; mit `llmAccess: true` wartet er (`CreateContainerConfigError`), bis der Claim `Ready` ist und das Secret existiert, und startet dann von selbst.
