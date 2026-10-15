# Capability-Plugin `llm-access` (LiteLLM)

Provisioniert für `CapabilityClaim`s vom Typ `llm-access` einen virtuellen
LiteLLM-Key und legt ihn als Secret `<claim>-credentials` (Schlüssel `api-key`
und `endpoint`) im Namespace des Claims ab. Die erlaubten Modelle kommen aus
`spec.properties.models`.

Beim Start (`initialize`) prüft das Plugin per `GET /key/list`, ob LiteLLM
erreichbar ist, die Datenbank angebunden ist und der Master-Key akzeptiert
wird. Schlägt das fehl, meldet der Operator betroffene Claims als
`CapabilityUnavailable` und versucht es erneut.

Registriert über den Entry Point `llm-access` in der Gruppe
`skip.capabilities` (siehe `pyproject.toml`).

```
src/skip_capability_litellm/
├── capability.py   LiteLLMCapability: initialize/provision/cleanup, Secret-Verwaltung
└── client.py       Schlanker Client fuer die Key-Management-API von LiteLLM
```

## Konfiguration

| Variable                  | Standard                             | Bedeutung                                   |
| ------------------------- | ------------------------------------ | ------------------------------------------- |
| `LITELLM_MASTER_KEY`      | –                                    | Master-Key des LiteLLM-Proxys (Pflicht)     |
| `LITELLM_BASE_URL`        | `http://litellm.platform.svc:4000`   | URL, über die der Operator LiteLLM erreicht |
| `LITELLM_PUBLIC_BASE_URL` | Wert von `LITELLM_BASE_URL`          | Endpunkt, der Anwendungen mitgeteilt wird   |

## Tests

```sh
uv run --group dev pytest plugins/capabilities/litellm
```
