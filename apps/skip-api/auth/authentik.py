import logging
import os
from functools import lru_cache
from typing import Any

import httpx

logger = logging.getLogger(__name__)

GROUP_ATTRIBUTES = {"managed_by": "skip-platform"}


def app_group_name(namespace: str, app_name: str) -> str:
    """Authentik-Gruppe, die den Zugriff auf eine App-Instanz steuert."""
    return f"app-{namespace}-{app_name}"


class AuthentikClient:
    """Synchroner Client fuer die Authentik v3 REST-API (Gruppen & Mitglieder).

    Alle Methoden sind fehlertolerant: Ist Authentik nicht erreichbar, wird
    geloggt und ein neutrales Ergebnis (None/False/[]) geliefert, damit das
    Deployment selbst nicht scheitert.
    """

    def __init__(self, base_url: str, token: str, timeout: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout

    @classmethod
    def from_env(cls) -> "AuthentikClient":
        return cls(
            os.environ.get("AUTHENTIK_API_URL", "").strip(),
            os.environ.get("AUTHENTIK_API_TOKEN", "").strip(),
        )

    @property
    def is_configured(self) -> bool:
        return bool(self.base_url and self.token)

    def _client(self) -> httpx.Client:
        return httpx.Client(
            base_url=f"{self.base_url}/api/v3",
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/json",
            },
            timeout=self.timeout,
        )

    def _find(self, path: str, field: str, value: str) -> dict[str, Any] | None:
        try:
            with self._client() as client:
                res = client.get(path, params={field: value})
                res.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("Authentik %s?%s=%s: %s", path, field, value, exc)
            return None
        for item in res.json().get("results", []):
            if item.get(field) == value:
                return item
        return None

    def get_group(self, name: str) -> dict[str, Any] | None:
        return self._find("/core/groups/", "name", name)

    def get_user(self, username: str) -> dict[str, Any] | None:
        return self._find("/core/users/", "username", username)

    def create_app_group(self, namespace: str, app_name: str) -> dict[str, Any] | None:
        name = app_group_name(namespace, app_name)
        if existing := self.get_group(name):
            return existing
        payload = {
            "name": name,
            "is_superuser": False,
            "attributes": {
                **GROUP_ATTRIBUTES,
                "skip_app": app_name,
                "skip_namespace": namespace,
            },
        }
        try:
            with self._client() as client:
                res = client.post("/core/groups/", json=payload)
                res.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("Authentik-Gruppe '%s' konnte nicht erstellt werden: %s", name, exc)
            return None
        logger.info("Authentik-Gruppe '%s' erstellt.", name)
        return res.json()

    def delete_app_group(self, namespace: str, app_name: str) -> bool:
        name = app_group_name(namespace, app_name)
        group = self.get_group(name)
        if not group:
            return True
        try:
            with self._client() as client:
                res = client.delete(f"/core/groups/{group['pk']}/")
                res.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("Authentik-Gruppe '%s' konnte nicht geloescht werden: %s", name, exc)
            return False
        logger.info("Authentik-Gruppe '%s' geloescht.", name)
        return True

    def _set_group_users(self, group: dict[str, Any], users: list[Any]) -> bool:
        try:
            with self._client() as client:
                res = client.patch(f"/core/groups/{group['pk']}/", json={"users": users})
                res.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error(
                "Mitglieder der Authentik-Gruppe '%s' konnten nicht gesetzt werden: %s",
                group.get("name"),
                exc,
            )
            return False
        return True

    def add_user_to_app_group(self, namespace: str, app_name: str, username: str) -> bool:
        group = self.create_app_group(namespace, app_name)
        if not group:
            return False
        user = self.get_user(username)
        if not user:
            logger.warning("Benutzer '%s' in Authentik nicht gefunden.", username)
            return False
        current = list(group.get("users", []))
        if user["pk"] in current:
            return True
        return self._set_group_users(group, current + [user["pk"]])

    def remove_user_from_app_group(
        self, namespace: str, app_name: str, username: str
    ) -> bool:
        group = self.get_group(app_group_name(namespace, app_name))
        user = self.get_user(username) if group else None
        if not group or not user:
            return False
        current = list(group.get("users", []))
        if user["pk"] not in current:
            return True
        return self._set_group_users(group, [pk for pk in current if pk != user["pk"]])

    def get_app_group_members(self, namespace: str, app_name: str) -> list[dict[str, Any]]:
        group = self.get_group(app_group_name(namespace, app_name))
        if not group:
            return []
        return [
            {
                "username": member.get("username"),
                "name": member.get("name"),
                "email": member.get("email"),
            }
            for member in group.get("users_obj", [])
        ]

    def is_member(self, namespace: str, app_name: str, username: str) -> bool:
        return any(
            member["username"] == username
            for member in self.get_app_group_members(namespace, app_name)
        )

    def search_users(self, query: str = "") -> list[dict[str, Any]]:
        params = {"search": query} if query else {}
        try:
            with self._client() as client:
                res = client.get("/core/users/", params=params)
                res.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("Benutzersuche in Authentik fehlgeschlagen: %s", exc)
            return []
        return [
            {
                "username": user.get("username"),
                "name": user.get("name"),
                "email": user.get("email"),
            }
            for user in res.json().get("results", [])
            if user.get("is_active") and user.get("type") == "internal"
        ]

    def list_groups(self) -> list[str]:
        try:
            with self._client() as client:
                res = client.get("/core/groups/")
                res.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("Gruppensuche in Authentik fehlgeschlagen: %s", exc)
            return []
        results: list[str] = []
        for g in res.json().get("results", []):
            name = g.get("name", "")
            if not name.startswith("app-") and not name.startswith("authentik"):
                results.append(name)
        return sorted(results)

    def team_group_name(self, name: str) -> str:
        clean = name.strip().lower().replace(" ", "-")
        return clean if clean.startswith("team-") else f"team-{clean}"

    def create_team(
        self, team_name: str, owner_username: str, description: str = ""
    ) -> dict[str, Any] | None:
        full_name = self.team_group_name(team_name)
        if existing := self.get_group(full_name):
            return existing
        user = self.get_user(owner_username)
        users = [user["pk"]] if user else []
        payload = {
            "name": full_name,
            "attributes": {
                **GROUP_ATTRIBUTES,
                "type": "team",
                "owner": owner_username,
                "description": description,
            },
            "users": users,
        }
        try:
            with self._client() as client:
                res = client.post("/core/groups/", json=payload)
                res.raise_for_status()
                return res.json()
        except httpx.HTTPError as exc:
            logger.warning("Gruppe %s konnte nicht angelegt werden: %s", full_name, exc)
            return None

    def get_team(self, team_name: str) -> dict[str, Any] | None:
        full_name = self.team_group_name(team_name)
        return self.get_group(full_name)

    def list_teams(
        self, username: str = "", is_admin: bool = False
    ) -> list[dict[str, Any]]:
        try:
            with self._client() as client:
                res = client.get("/core/groups/")
                res.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("Teams konnten nicht gelistet werden: %s", exc)
            return []

        teams: list[dict[str, Any]] = []
        for g in res.json().get("results", []):
            attrs = g.get("attributes", {}) or {}
            name = g.get("name", "")
            is_team = attrs.get("type") == "team" or (name.startswith("team-") and not name.startswith("app-"))
            if not is_team:
                continue

            owner = attrs.get("owner", "")
            members = [
                {
                    "username": m.get("username"),
                    "name": m.get("name"),
                    "email": m.get("email"),
                    "is_owner": m.get("username") == owner,
                }
                for m in g.get("users_obj", [])
            ]
            member_usernames = {m["username"] for m in members}

            # Filter: Admin sieht alle; normale Nutzer sehen Teams, in denen sie Owner oder Mitglied sind
            if not is_admin and username:
                if username != owner and username not in member_usernames:
                    continue

            teams.append(
                {
                    "id": str(g.get("pk")),
                    "name": name,
                    "description": attrs.get("description", ""),
                    "owner": owner,
                    "is_owner": username == owner or is_admin,
                    "members": members,
                }
            )
        return sorted(teams, key=lambda t: t["name"].lower())

    def add_user_to_team(self, team_name: str, username: str) -> bool:
        group = self.get_team(team_name)
        if not group:
            return False
        user = self.get_user(username)
        if not user:
            return False
        current = list(group.get("users", []))
        if user["pk"] in current:
            return True
        return self._set_group_users(group, current + [user["pk"]])

    def remove_user_from_team(self, team_name: str, username: str) -> bool:
        group = self.get_team(team_name)
        if not group:
            return False
        user = self.get_user(username)
        if not user:
            return False
        current = list(group.get("users", []))
        return self._set_group_users(group, [pk for pk in current if pk != user["pk"]])

    def delete_team(self, team_name: str) -> bool:
        group = self.get_team(team_name)
        if not group:
            return False
        try:
            with self._client() as client:
                res = client.delete(f"/core/groups/{group['pk']}/")
                res.raise_for_status()
                return True
        except httpx.HTTPError as exc:
            logger.warning("Team %s konnte nicht geloescht werden: %s", team_name, exc)
            return False


@lru_cache
def get_authentik_client() -> AuthentikClient | None:
    """Konfigurierter Client oder None, wenn AUTHENTIK_API_URL/-TOKEN fehlen."""
    client = AuthentikClient.from_env()
    if not client.is_configured:
        logger.warning(
            "Authentik nicht konfiguriert - App-Gruppen und Sharing sind deaktiviert."
        )
        return None
    return client
