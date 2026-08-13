from datetime import datetime


def test_normalize_asset_tag_uppercases_and_collapses_spaces(app_module):
    assert app_module.normalize_asset_tag(" help-ukr-  0753 ") == "HELP-UKR- 0753"


def test_normalize_asset_usage_type_falls_back_to_tag_pattern(app_module):
    assert app_module.normalize_asset_usage_type("", "HELP-UKR-LC-0360") == "low_cost"
    assert app_module.normalize_asset_usage_type("", "HELP-UKR-0753") == "standard"
    assert app_module.normalize_asset_usage_type("low_cost", "HELP-UKR-0753") == "low_cost"


def test_parse_excel_sync_date_accepts_current_formats(app_module):
    assert app_module.parse_excel_sync_date("17.04.2026") == "2026-04-17"
    assert app_module.parse_excel_sync_date("2026-04-17") == "2026-04-17"
    assert app_module.parse_excel_sync_date(datetime(2026, 4, 17)) == "2026-04-17"
    assert app_module.parse_excel_sync_date("04-17-2026") is None


def test_format_project_allocations_documents_split_funding(app_module):
    allocations = [
        {"project_number": "UKR-029", "allocation_percent": 50},
        {"project_number": "UKR-032", "allocation_percent": 50},
    ]
    assert app_module.format_project_allocations(allocations) == "UKR-029 50% / UKR-032 50%"
    assert app_module.format_project_allocations([{"project_number": "GLO-001", "allocation_percent": 100}]) == "GLO-001"


def test_transfer_key_uses_stable_registration_key(app_module):
    record = {
        "asset_tag_number": " help-ukr-0753 ",
        "from_holder_name": "Supplier",
        "transfer_reason": "Registration of the new asset",
        "transfer_date": "2026-04-17",
        "source_log_no": 176,
        "to_holder_name": "Warehouse",
    }
    assert app_module.make_transfer_key(record) == "registration:HELP-UKR-0753"


def test_transfer_key_includes_movement_identity_for_legacy_rows(app_module):
    record = {
        "asset_tag_number": "HELP-UKR-LC-0079",
        "transfer_date": "2026-06-30",
        "source_log_no": 175,
        "from_holder_name": "Oleksandr Moiseyenko",
        "to_holder_name": "Warehouse",
    }
    assert app_module.make_transfer_key(record) == (
        "HELP-UKR-LC-0079|2026-06-30|175|oleksandr moiseyenko|warehouse"
    )

