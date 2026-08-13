from types import SimpleNamespace


class FakeResponse:
    def __init__(self, data=None):
        self.data = data or []


class RecordingQuery:
    def __init__(self, database, table_name):
        self.database = database
        self.table_name = table_name
        self.action = None
        self.payload = None
        self.filters = []

    def select(self, *args, **kwargs):
        self.action = "select"
        return self

    def insert(self, payload):
        self.action = "insert"
        self.payload = payload
        return self

    def update(self, payload):
        self.action = "update"
        self.payload = payload
        return self

    def eq(self, field_name, value):
        self.filters.append(("eq", field_name, value))
        return self

    def is_(self, field_name, value):
        self.filters.append(("is", field_name, value))
        return self

    def execute(self):
        operation = {
            "table": self.table_name,
            "action": self.action,
            "payload": self.payload,
            "filters": self.filters,
        }
        self.database.operations.append(operation)
        return FakeResponse(self.database.responses.get((self.table_name, self.action), []))


class RecordingSupabase:
    def __init__(self, responses=None):
        self.responses = responses or {}
        self.operations = []

    def table(self, table_name):
        return RecordingQuery(self, table_name)


def make_admin_request():
    return SimpleNamespace(
        session={"admin_authenticated": True, "admin_role": "admin", "admin_username": "admin"},
        method="POST",
        url=SimpleNamespace(path="/admin/assets/101/edit", query=""),
    )


def test_asset_edit_route_updates_payload_and_redirects(app_module, monkeypatch):
    fake_supabase = RecordingSupabase()
    monkeypatch.setattr(app_module, "supabase", fake_supabase)
    monkeypatch.setattr(
        app_module,
        "get_asset_by_id",
        lambda asset_id: {
            "asset_id": asset_id,
            "asset_tag_number": "HELP-UKR-0753",
            "usage_type": "standard",
            "current_status": "functional",
        },
    )
    audit_calls = []
    monkeypatch.setattr(app_module, "audit_log_field_changes", lambda **kwargs: audit_calls.append(kwargs))

    response = app_module.admin_asset_edit(
        make_admin_request(),
        101,
        usage_type="low_cost",
        item_description="Wireless mouse",
        brand_make="Logitech",
        model="M185",
        asset_classification="IT",
        asset_sub_classification="Computer Accessories",
        quantity="1",
        purchase_price="20,31",
        currency="EUR",
        serial_number="SN-001",
        current_status="Not functional",
        remarks="Regression edit",
    )

    update_operation = fake_supabase.operations[0]
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/assets/101"
    assert update_operation["table"] == "assets"
    assert update_operation["action"] == "update"
    assert update_operation["filters"] == [("eq", "asset_id", 101)]
    assert update_operation["payload"] == {
        "usage_type": "low_cost",
        "item_description": "Wireless mouse",
        "brand_make": "Logitech",
        "model": "M185",
        "asset_classification": "IT",
        "asset_sub_classification": "Computer Accessories",
        "quantity": 1,
        "purchase_price": 20.31,
        "currency": "EUR",
        "serial_chassis_number": "SN-001",
        "current_status": "Not functional",
        "remarks": "Regression edit",
    }
    assert audit_calls[0]["entity_label"] == "HELP-UKR-0753"


def test_assignment_update_closes_current_assignment_inserts_new_status_and_updates_asset(app_module, monkeypatch):
    fake_supabase = RecordingSupabase(
        {("asset_assignments", "select"): [{"assignment_id": 77}]}
    )
    monkeypatch.setattr(app_module, "supabase", fake_supabase)
    monkeypatch.setattr(app_module, "log_assignment_field_changes", lambda *args, **kwargs: None)
    monkeypatch.setattr(app_module, "supports_asset_assignment_actor_columns", lambda: True)
    monkeypatch.setattr(app_module, "supports_asset_assignment_department_column", lambda: True)

    result = app_module.apply_asset_assignment_change(
        asset={
            "asset_id": 101,
            "asset_tag_number": "HELP-UKR-0753",
            "current_status": "functional",
            "current_assignment": {
                "assignment_id": 77,
                "person_id": 12,
                "location_id": 4,
                "assignment_date": "2026-06-01",
                "status": "functional",
                "responsible_person": "Maksym Storozhenko",
            },
        },
        parsed_person_id=12,
        parsed_location_id=4,
        assignment_department="PROGRAM",
        assignment_date="2026-08-13",
        status="Not functional",
        notes="Updated condition",
        handover_condition="Used",
        assignment_scope="personal",
        custody_note="Needs review",
        request=make_admin_request(),
    )

    assert result == {"changed": True, "message": "Assignment updated."}
    assert fake_supabase.operations[0] == {
        "table": "asset_assignments",
        "action": "select",
        "payload": None,
        "filters": [("eq", "asset_id", 101), ("is", "return_date", "null")],
    }
    assert fake_supabase.operations[1]["payload"]["return_date"] == "2026-08-13"
    inserted_assignment = fake_supabase.operations[2]["payload"]
    assert inserted_assignment["asset_id"] == 101
    assert inserted_assignment["person_id"] == 12
    assert inserted_assignment["location_id"] == 4
    assert inserted_assignment["assignment_department"] == "PROGRAM"
    assert inserted_assignment["status"] == "Not functional"
    assert inserted_assignment["updated_by"] == "admin"
    assert fake_supabase.operations[3]["table"] == "assets"
    assert fake_supabase.operations[3]["payload"] == {"current_status": "Not functional"}


def test_transfer_creation_records_asset_movement_and_project_history(app_module, monkeypatch):
    fake_supabase = RecordingSupabase(
        {("asset_transfers", "insert"): [{"transfer_id": 55}]}
    )
    monkeypatch.setattr(app_module, "supabase", fake_supabase)
    monkeypatch.setattr(app_module, "get_person_by_id", lambda person_id: {"person_id": person_id, "name_eng": "New Holder"})
    monkeypatch.setattr(
        app_module,
        "get_asset_projects",
        lambda asset_id: [
            {
                "project_id": 6,
                "project_number": "GLO-001",
                "allocation_percent": 100,
                "is_current": True,
            }
        ],
    )

    transfer_id = app_module.create_asset_transfer_from_assignment_change(
        asset={
            "asset_id": 101,
            "asset_tag_number": "HELP-UKR-0753",
            "usage_type": "standard",
            "item_description": "Monitor holder",
            "serial_chassis_number": "SN-001",
            "current_status": "functional",
        },
        from_assignment={
            "person_id": 12,
            "responsible_person": "Old Holder",
            "status": "functional",
            "handover_condition": "New",
        },
        to_person_id=13,
        transfer_date="2026-08-13",
        transfer_reason="Assignment changed in web app",
        status="Not functional",
        condition="Used",
    )

    assert transfer_id == 55
    transfer_payload = fake_supabase.operations[0]["payload"]
    assert transfer_payload["asset_id"] == 101
    assert transfer_payload["from_person_id"] == 12
    assert transfer_payload["to_person_id"] == 13
    assert transfer_payload["from_holder_name"] == "Old Holder"
    assert transfer_payload["to_holder_name"] == "New Holder"
    assert transfer_payload["asset_status"] == "Not functional"
    assert transfer_payload["from_project_raw"] == "GLO-001"
    project_payloads = fake_supabase.operations[1]["payload"]
    assert {row["direction"] for row in project_payloads} == {"from", "to"}
    assert all(row["transfer_id"] == 55 for row in project_payloads)
