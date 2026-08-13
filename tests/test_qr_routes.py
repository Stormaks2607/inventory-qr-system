def test_legacy_asset_json_route_uses_tag_lookup(app_module, client, monkeypatch):
    monkeypatch.setattr(
        app_module,
        "get_asset_by_tag",
        lambda tag: {"asset_tag_number": tag, "current_status": "functional"},
    )

    response = client.get("/asset/HELP-UKR-0753")
    assert response.status_code == 200
    assert response.json()["asset_tag_number"] == "HELP-UKR-0753"


def test_legacy_asset_json_route_returns_404_when_missing(app_module, client, monkeypatch):
    monkeypatch.setattr(app_module, "get_asset_by_tag", lambda tag: None)
    response = client.get("/asset/HELP-UKR-9999")
    assert response.status_code == 404


def test_legacy_public_view_route_remains_available(app_module, client, monkeypatch):
    monkeypatch.setattr(
        app_module,
        "get_asset_by_tag",
        lambda tag: {"asset_tag_number": tag, "item_description": "Monitor"},
    )
    response = client.get("/view/HELP-UKR-0753")
    assert response.status_code == 200
    assert "HELP-UKR-0753" in response.text

