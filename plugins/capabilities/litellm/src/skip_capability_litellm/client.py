import logging
import os
from typing import Any

import requests

DEFAULT_BASE_URL = "http://litellm.platform.svc:4000"
HTTP_TIMEOUT_SECONDS = 15

logger = logging.getLogger(__name__)


class LiteLLMError(RuntimeError):
    """LiteLLM hat mit einem Fehler oder einer unbrauchbaren Antwort geantwortet."""


class LiteLLMClient:
    """Schlanker Wrapper um die Key-Management-API des LiteLLM-Proxys."""

    def __init__(
        self,
        base_url: str,
        master_key: str,
        timeout_seconds: int = HTTP_TIMEOUT_SECONDS,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout_seconds

        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {master_key}",
                "Content-Type": "application/json",
            }
        )

    @classmethod
    def from_env(cls) -> "LiteLLMClient":
        """Erzeugt einen Client aus LITELLM_BASE_URL / LITELLM_MASTER_KEY."""
        master_key = os.environ.get("LITELLM_MASTER_KEY")

        if not master_key:
            raise LiteLLMError("LITELLM_MASTER_KEY environment variable is not set")

        return cls(
            base_url=os.environ.get("LITELLM_BASE_URL", DEFAULT_BASE_URL),
            master_key=master_key,
        )

    def check_connection(self) -> None:
        """Prüft, ob LiteLLM erreichbar ist und den Master-Key akzeptiert.

        GET /key/list

        Die Key-Verwaltung braucht Proxy, Datenbank und einen gültigen
        Master-Key; eine minimale Abfrage deckt alle drei ab.
        """
        response = self.session.get(
            f"{self.base_url}/key/list",
            params={"page": 1, "size": 1},
            timeout=self.timeout,
        )

        self._raise_for_status(response)

    def generate_key(
        self,
        *,
        key_alias: str,
        models: list[str],
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Erstellt einen neuen virtuellen LiteLLM-Key und liefert den Rohwert.

        POST /key/generate
        """
        payload: dict[str, Any] = {
            "key_alias": key_alias,
            "models": models,
        }

        if metadata:
            payload["metadata"] = metadata

        response = self.session.post(
            f"{self.base_url}/key/generate", json=payload, timeout=self.timeout
        )

        self._raise_for_status(response)

        key = response.json().get("key")

        if not key:
            raise LiteLLMError("LiteLLM /key/generate response contained no 'key'")

        return key

    def update_key(self, *, key: str, key_alias: str, models: list[str]) -> bool:
        """Aktualisiert Alias und Modellliste eines bestehenden Keys.

        POST /key/update

        Liefert False, wenn LiteLLM den Key nicht (mehr) kennt, sonst True.
        Alle anderen Fehler lösen einen LiteLLMError aus.
        """
        response = self.session.post(
            f"{self.base_url}/key/update",
            json={"key": key, "key_alias": key_alias, "models": models},
            timeout=self.timeout,
        )

        if response.status_code == 404:
            return False

        self._raise_for_status(response)

        return True

    def delete_key_by_alias(self, *, key_alias: str) -> None:
        """Löscht alle Keys, die unter dem Alias registriert sind.

        POST /key/delete

        Ein unbekannter Alias ist kein Fehler: der Key ist dann bereits weg.
        """
        response = self.session.post(
            f"{self.base_url}/key/delete",
            json={"key_aliases": [key_alias]},
            timeout=self.timeout,
        )

        if response.status_code == 404:
            return

        self._raise_for_status(response)

    @staticmethod
    def _raise_for_status(response: requests.Response) -> None:
        try:
            response.raise_for_status()
        except requests.HTTPError as e:
            body = response.text[:2000]

            raise LiteLLMError(
                f"LiteLLM returned HTTP {response.status_code}: {body}"
            ) from e
