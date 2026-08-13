def test_get_effective_status_prefers_current_assignment_status(app_module):
    asset = {
        "current_status": "LOST",
        "current_assignment": {"status": "functional"},
    }
    assert app_module.get_effective_status(asset) == "functional"


def test_get_effective_status_falls_back_to_asset_current_status(app_module):
    assert app_module.get_effective_status({"current_status": "Not functional"}) == "Not functional"


def test_get_effective_status_returns_dash_when_no_status_exists(app_module):
    assert app_module.get_effective_status({"current_assignment": {}}) == "-"


def test_excel_status_mapping_preserves_observed_variants(app_module):
    observed = ["functional", "No functional", "Not functional", "NOT functional", "LOST"]
    assert [app_module.normalize_sync_value("current_status", value) for value in observed] == [
        "functional",
        "no functional",
        "not functional",
        "not functional",
        "lost",
    ]

