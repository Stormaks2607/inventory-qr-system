def test_app_imports_without_supabase_env(app_module):
    assert app_module.app.title == "Asset API"


def test_health_route(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

