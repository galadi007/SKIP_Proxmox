from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from templates.api import get_template_service, router
from templates.service import FileSystemTemplateService


TEMPLATES = Path(__file__).resolve().parents[3] / "templates"


def test_template_catalog_rest_api() -> None:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_template_service] = lambda: (
        FileSystemTemplateService.from_root(TEMPLATES)
    )
    client = TestClient(app)
    headers = {"X-User": "developer@skip.de"}

    listing = client.get("/api/templates", headers=headers)
    assert listing.status_code == 200
    assert {item["name"] for item in listing.json()} == {
        "jupyter-notebook",
        "marimo",
        "open-webui",
    }
    assert "displayName" in listing.json()[0]

    details = client.get("/api/templates/jupyter-notebook", headers=headers)
    assert details.status_code == 200
    assert details.json()["descriptionMarkdown"]

    schema = client.get(
        "/api/templates/jupyter-notebook/schema", headers=headers
    )
    assert schema.status_code == 200
    assert schema.json()["schema"]["type"] == "object"

    logo = client.get(
        "/api/templates/jupyter-notebook/logo", headers=headers
    )
    assert logo.status_code == 200
    assert logo.headers["content-type"].startswith("image/svg+xml")


def test_template_routes_require_authentication() -> None:
    app = FastAPI()
    app.include_router(router)
    response = TestClient(app).get("/api/templates")
    assert response.status_code == 401
