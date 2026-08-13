def test_normalize_excel_transfer_record_requires_asset_and_date(app_module):
    assert app_module.normalize_excel_transfer_record({"asset_tag_number": "", "transfer_date": "17.04.2026"}, 8) is None
    assert app_module.normalize_excel_transfer_record({"asset_tag_number": "HELP-UKR-0753"}, 8) is None


def test_normalize_excel_transfer_record_maps_transfer_fields(app_module):
    record = app_module.normalize_excel_transfer_record(
        {
            "asset_tag_number": " help-ukr-0753 ",
            "transfer_date": "17.04.2026",
            "source_log_no": "176",
            "from_holder_name": "Supplier",
            "to_holder_name": "Warehouse",
            "transfer_reason": "Registration of the new asset",
            "asset_status": "functional",
        },
        9,
    )

    assert record["asset_tag_number"] == "HELP-UKR-0753"
    assert record["transfer_date"] == "2026-04-17"
    assert record["source_log_no"] == 176
    assert record["transfer_key"] == "registration:HELP-UKR-0753"

