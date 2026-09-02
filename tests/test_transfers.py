from types import SimpleNamespace

import pytest
from openpyxl import Workbook, load_workbook


TRANSFER_HEADERS = [
    "No.",
    "Transfer Date",
    "Standart/Low-cost",
    "Asset Tag No. / Inventory Code\n(new standardised system)",
    "Brand-Make/Model/Item Description",
    "Serial/Chassis No.",
    "Holder",
    "Current Project",
    "New Project",
    "New holder",
    "Current Status\n(functionality)",
    "Asset Condition Description",
    "Reason for Asset Transfer",
]


def create_transfer_workbook(path, *, include_system_id=False):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Transfer log"
    for column_number, header in enumerate(TRANSFER_HEADERS, start=3):
        sheet.cell(row=1, column=column_number).value = header
    if include_system_id:
        sheet.cell(row=1, column=16).value = "System Transfer ID"
        sheet.column_dimensions["P"].hidden = True
    workbook.save(path)


def existing_transfer_record(transfer_id=188):
    return {
        "system_transfer_id": transfer_id,
        "source_log_no": None,
        "transfer_date": "2026-08-29",
        "source_asset_type": "Standard",
        "asset_tag_number": "SYN-T2-0001",
        "from_holder_name": "Warehouse",
        "from_project_raw": "SYN-20001",
        "to_project_raw": "SYN-20001",
        "to_holder_name": "Synthetic Tenant #2 Admin",
        "asset_status": "functional",
        "transfer_reason": "Assignment changed in web app",
    }


def transfer_context(app_module, *transfers):
    return {
        "person_lookup": {},
        "project_lookup": {},
        "transfers_by_id": {
            transfer["transfer_id"]: transfer
            for transfer in transfers
            if transfer.get("transfer_id") is not None
        },
        "transfer_signatures": {
            app_module.make_transfer_signature(transfer["asset_id"], transfer)
            for transfer in transfers
        },
    }


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


def test_transfer_export_roundtrip_uses_hidden_stable_id_and_skips_existing(
    app_module,
    tmp_path,
):
    workbook_path = tmp_path / "roundtrip.xlsx"
    create_transfer_workbook(workbook_path)
    workbook = load_workbook(workbook_path)
    sheet = workbook["Transfer log"]

    result = app_module.write_transfer_log_records_to_excel_sheet(
        sheet,
        [existing_transfer_record()],
    )
    workbook.save(workbook_path)
    workbook.close()

    reopened = load_workbook(workbook_path)
    assert reopened["Transfer log"]["P1"].value == "System Transfer ID"
    assert reopened["Transfer log"].column_dimensions["P"].hidden is True
    reopened.close()

    imported = app_module.load_excel_transfer_log_rows(str(workbook_path))
    context = transfer_context(
        app_module,
        {
            "transfer_id": 188,
            "asset_id": 1232,
            **existing_transfer_record(),
        },
    )
    preview = app_module.build_transfer_log_preview(
        imported,
        {"SYN-T2-0001": {"asset_id": 1232, "asset_tag_number": "SYN-T2-0001"}},
        context,
    )

    assert result["exported_records"] == 1
    assert imported[0]["system_transfer_id"] == 188
    assert imported[0]["source_log_no"] == 1
    assert preview["summary"]["new_records"] == 0
    assert preview["summary"]["skipped_existing"] == 1


def test_database_transfer_export_record_includes_exact_transfer_id(app_module, monkeypatch):
    transfer = {
        "transfer_id": 188,
        "asset_id": 1232,
        "transfer_date": "2026-08-29",
        "from_holder_name": "Warehouse",
        "to_holder_name": "Synthetic Tenant #2 Admin",
    }
    monkeypatch.setattr(app_module, "list_asset_transfer_records", lambda request=None: [transfer])
    monkeypatch.setattr(
        app_module,
        "list_asset_records",
        lambda request=None: [{"asset_id": 1232, "asset_tag_number": "SYN-T2-0001"}],
    )
    monkeypatch.setattr(app_module, "list_people", lambda request=None: [])
    monkeypatch.setattr(app_module, "list_projects", lambda request=None: [])
    monkeypatch.setattr(app_module, "list_donors", lambda request=None: [])
    monkeypatch.setattr(app_module, "list_current_assignment_records", lambda request=None: [])
    monkeypatch.setattr(app_module, "list_asset_project_records", lambda request=None: [])
    monkeypatch.setattr(app_module, "list_asset_payment_records", lambda request=None: [])
    monkeypatch.setattr(app_module, "get_asset_transfer_project_rows", lambda transfer_ids: {})
    monkeypatch.setattr(app_module, "build_asset_registration_transfer_records", lambda *args: [])

    records = app_module.build_database_transfer_log_records(request=SimpleNamespace())

    assert len(records) == 1
    assert records[0]["system_transfer_id"] == 188


def test_same_looking_transfers_with_distinct_system_ids_remain_distinct(
    app_module,
    tmp_path,
):
    workbook_path = tmp_path / "distinct.xlsx"
    create_transfer_workbook(workbook_path)
    workbook = load_workbook(workbook_path)
    first = existing_transfer_record(188)
    second = existing_transfer_record(189)
    app_module.write_transfer_log_records_to_excel_sheet(
        workbook["Transfer log"],
        [first, second],
    )
    workbook.save(workbook_path)
    workbook.close()

    imported = app_module.load_excel_transfer_log_rows(str(workbook_path))
    context = transfer_context(
        app_module,
        {"transfer_id": 188, "asset_id": 1232, **first},
        {"transfer_id": 189, "asset_id": 1232, **second},
    )
    preview = app_module.build_transfer_log_preview(
        imported,
        {"SYN-T2-0001": {"asset_id": 1232}},
        context,
    )

    assert [row["system_transfer_id"] for row in imported] == [188, 189]
    assert preview["summary"]["new_records"] == 0
    assert preview["summary"]["skipped_existing"] == 2


@pytest.mark.parametrize("system_id", ["abc", "1.5", -1, True])
def test_invalid_system_transfer_id_fails_closed(app_module, system_id):
    with pytest.raises(ValueError, match="invalid System Transfer ID"):
        app_module.normalize_excel_transfer_record(
            {
                "system_transfer_id": system_id,
                "asset_tag_number": "SYN-T2-0001",
                "transfer_date": "29.08.2026",
                "from_holder_name": "Warehouse",
            },
            2,
        )


def test_system_transfer_id_requires_complete_transfer_row(app_module):
    with pytest.raises(ValueError, match="must contain a valid asset tag and transfer date"):
        app_module.normalize_excel_transfer_record(
            {
                "system_transfer_id": 188,
                "asset_tag_number": "SYN-T2-0001",
            },
            2,
        )


def test_legacy_transfer_workbook_without_system_id_still_parses(app_module, tmp_path):
    workbook_path = tmp_path / "legacy.xlsx"
    create_transfer_workbook(workbook_path)
    workbook = load_workbook(workbook_path)
    sheet = workbook["Transfer log"]
    values = [1, "29.08.2026", "Standard", "SYN-T2-0001", "Monitor", None, "Warehouse"]
    for column_number, value in enumerate(values, start=3):
        sheet.cell(row=2, column=column_number).value = value
    workbook.save(workbook_path)
    workbook.close()

    imported = app_module.load_excel_transfer_log_rows(str(workbook_path))

    assert len(imported) == 1
    assert imported[0]["system_transfer_id"] is None
    assert imported[0]["asset_tag_number"] == "SYN-T2-0001"


def test_cross_tenant_system_transfer_id_fails_closed(app_module):
    record = existing_transfer_record(188)
    current_assets = {"SYN-T2-0001": {"asset_id": 1232}}

    with pytest.raises(app_module.TenantContextError, match="current tenant and asset"):
        app_module.build_transfer_log_preview(
            [record],
            current_assets,
            transfer_context(app_module),
        )


def test_same_tenant_wrong_asset_system_transfer_id_fails_closed(app_module):
    record = existing_transfer_record(188)
    current_assets = {"SYN-T2-0001": {"asset_id": 1232}}

    with pytest.raises(app_module.TenantContextError, match="current tenant and asset"):
        app_module.build_transfer_log_preview(
            [record],
            current_assets,
            transfer_context(
                app_module,
                {"transfer_id": 188, "asset_id": 9999, **record},
            ),
        )


def test_same_looking_other_tenant_transfer_does_not_suppress_active_tenant(app_module):
    record = {**existing_transfer_record(), "system_transfer_id": None}
    other_tenant_signature = app_module.make_transfer_signature(9999, record)
    context = transfer_context(app_module)
    context["other_tenant_signatures"] = {other_tenant_signature}

    preview = app_module.build_transfer_log_preview(
        [record],
        {"SYN-T2-0001": {"asset_id": 1232}},
        context,
    )

    assert preview["summary"]["new_records"] == 1
    assert preview["summary"]["skipped_existing"] == 0


class TransferInsertQuery:
    def __init__(self, database):
        self.database = database
        self.payload = None

    def insert(self, payload):
        self.payload = payload
        return self

    def execute(self):
        self.database.inserts.append(self.payload)
        transfer_id = self.database.returned_ids.pop(0) if self.database.returned_ids else None
        return SimpleNamespace(data=[{"transfer_id": transfer_id}] if transfer_id else [])


class TransferInsertSupabase:
    def __init__(self, returned_ids):
        self.returned_ids = list(returned_ids)
        self.inserts = []

    def table(self, table_name):
        assert table_name == "asset_transfers"
        return TransferInsertQuery(self)


def test_new_semantic_transfer_inserts_once_and_repeat_is_idempotent(
    app_module,
    monkeypatch,
):
    database = TransferInsertSupabase([190])
    monkeypatch.setattr(app_module, "supabase", database)
    monkeypatch.setattr(app_module, "ensure_parent_tenant", lambda *args, **kwargs: None)
    monkeypatch.setattr(app_module, "validate_transfer_person_tenants", lambda *args, **kwargs: None)
    monkeypatch.setattr(app_module, "apply_transfer_project_rows", lambda *args, **kwargs: 0)
    monkeypatch.setattr(app_module, "audit_log_event", lambda **kwargs: True)
    context = transfer_context(app_module)
    record = {
        **existing_transfer_record(),
        "system_transfer_id": None,
        "asset_id": 1232,
    }

    first = app_module.apply_sync_transfer(record, context, SimpleNamespace(session={}))
    second = app_module.apply_sync_transfer(record, context, SimpleNamespace(session={}))

    assert first == 1
    assert second == 0
    assert len(database.inserts) == 1


def test_apply_rechecks_system_transfer_id_before_insert(app_module, monkeypatch):
    database = TransferInsertSupabase([190])
    monkeypatch.setattr(app_module, "supabase", database)
    monkeypatch.setattr(app_module, "ensure_parent_tenant", lambda *args, **kwargs: None)
    monkeypatch.setattr(app_module, "validate_transfer_person_tenants", lambda *args, **kwargs: None)
    record = {**existing_transfer_record(), "asset_id": 1232}

    with pytest.raises(app_module.TenantContextError, match="current tenant and asset"):
        app_module.apply_sync_transfer(
            record,
            transfer_context(app_module),
            SimpleNamespace(session={}),
        )

    assert database.inserts == []


def test_empty_transfer_insert_response_is_controlled_failure(app_module, monkeypatch):
    database = TransferInsertSupabase([])
    monkeypatch.setattr(app_module, "supabase", database)
    monkeypatch.setattr(app_module, "ensure_parent_tenant", lambda *args, **kwargs: None)
    monkeypatch.setattr(app_module, "validate_transfer_person_tenants", lambda *args, **kwargs: None)
    monkeypatch.setattr(app_module, "apply_transfer_project_rows", lambda *args, **kwargs: 0)

    with pytest.raises(RuntimeError, match="did not return a valid transfer_id"):
        app_module.apply_sync_transfer(
            {
                **existing_transfer_record(),
                "system_transfer_id": None,
                "asset_id": 1232,
            },
            transfer_context(app_module),
            SimpleNamespace(session={}),
        )


def test_registration_transfer_semantic_fallback_is_idempotent(app_module):
    record = {
        "system_transfer_id": None,
        "asset_tag_number": "SYN-T2-0001",
        "transfer_date": "2026-08-01",
        "from_holder_name": "Supplier",
        "to_holder_name": "Warehouse",
        "transfer_reason": "Registration of the new asset",
    }
    existing = {"transfer_id": 187, "asset_id": 1232, **record}
    preview = app_module.build_transfer_log_preview(
        [record],
        {"SYN-T2-0001": {"asset_id": 1232}},
        transfer_context(app_module, existing),
    )

    assert preview["summary"]["new_records"] == 0
    assert preview["summary"]["skipped_existing"] == 1

