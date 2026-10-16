from fastapi.testclient import TestClient
from main import app


def test_catalog_mode_rejects_mutations_but_keeps_health(monkeypatch):
    monkeypatch.setenv('PLATFORM_CATALOG_ONLY', 'true')
    client = TestClient(app)
    response = client.post('/api/apps', json={})
    assert response.status_code == 503
    assert 'Katalogbetrieb' in response.json()['detail']
    assert client.get('/healthz').status_code == 200


def test_catalog_mode_off_keeps_auth_required(monkeypatch):
    monkeypatch.setenv('PLATFORM_CATALOG_ONLY', 'false')
    response = TestClient(app).post('/api/apps', json={})
    assert response.status_code == 401
