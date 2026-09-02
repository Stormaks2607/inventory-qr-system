import os
from types import SimpleNamespace

import pytest


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
        self.orders = []

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

    def delete(self):
        self.action = "delete"
        return self

    def eq(self, field_name, value):
        self.filters.append(("eq", field_name, value))
        return self

    def in_(self, field_name, value):
        self.filters.append(("in", field_name, value))
        return self

    def ilike(self, field_name, value):
        self.filters.append(("ilike", field_name, value))
        return self

    def is_(self, field_name, value):
        self.filters.append(("is", field_name, value))
        return self

    @property
    def not_(self):
        return RecordingNotFilter(self)

    def order(self, field_name, **kwargs):
        self.orders.append((field_name, kwargs))
        return self

    def range(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def execute(self):
        operation = {
            "table": self.table_name,
            "action": self.action,
            "payload": self.payload,
            "filters": self.filters,
            "orders": self.orders,
        }
        self.database.operations.append(operation)
        return FakeResponse(self.database.responses.get((self.table_name, self.action), []))


class RecordingNotFilter:
    def __init__(self, query):
        self.query = query

    def is_(self, field_name, value):
        self.query.filters.append(("not_is", field_name, value))
        return self.query


class RecordingSupabase:
    def __init__(self, responses=None):
        self.responses = responses or {}
        self.operations = []

    def table(self, table_name):
        return RecordingQuery(self, table_name)


class FailingInsertQuery(RecordingQuery):
    def execute(self):
        operation = {
            "table": self.table_name,
            "action": self.action,
            "payload": self.payload,
            "filters": self.filters,
        }
        self.database.operations.append(operation)
        if self.table_name == self.database.fail_table and self.action == "insert":
            raise RuntimeError(self.database.fail_message)
        return FakeResponse(self.database.responses.get((self.table_name, self.action), []))


class FailingInsertSupabase(RecordingSupabase):
    def __init__(self, fail_table, fail_message="insert failed", responses=None):
        super().__init__(responses=responses)
        self.fail_table = fail_table
        self.fail_message = fail_message

    def table(self, table_name):
        return FailingInsertQuery(self, table_name)


def make_admin_request(tenant_id="00000000-0000-4000-8000-000000000001"):
    return SimpleNamespace(
        session={
            "admin_authenticated": True,
            "admin_role": "admin",
            "admin_username": "admin",
            "tenant_id": tenant_id,
        },
        method="POST",
        url=SimpleNamespace(path="/admin/assets/101/edit", query=""),
    )


def test_asset_edit_route_updates_payload_and_redirects(app_module, monkeypatch):
    fake_supabase = RecordingSupabase()
    monkeypatch.setattr(app_module, "supabase", fake_supabase)
    monkeypatch.setattr(
        app_module,
        "get_asset_by_id",
        lambda asset_id, request=None: {
            "asset_id": asset_id,
            "asset_tag_number": "HELP-UKR-0753",
            "usage_type": "standard",
            "current_status": "functional",
            "tenant_id": app_module.DEFAULT_TENANT_ID,
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
    assert update_operation["filters"] == [
        ("eq", "tenant_id", app_module.DEFAULT_TENANT_ID),
        ("eq", "asset_id", 101),
    ]
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


def test_asset_detail_edit_description_renders_multiline_textarea(app_module):
    multiline_description = "Type: Monitor holder\nHeight Adjustment Range: 0-260 mm\nRotation: +90°"
    template_source = (app_module.templates.env.loader.get_source(app_module.templates.env, "admin_asset_detail.html"))[0]
    description_control = '<textarea id="item_description" name="item_description" rows="4">{{ asset.item_description or \'\' }}</textarea>'
    rendered = app_module.templates.env.from_string(description_control).render(
        asset={"item_description": multiline_description}
    )

    assert description_control in template_source
    assert '<textarea id="item_description" name="item_description" rows="4">' in rendered
    assert multiline_description in rendered
    assert 'name="item_description" type="text"' not in template_source


def test_asset_edit_preserves_unchanged_multiline_description_and_audits_only_remarks(app_module, monkeypatch):
    multiline_description = "Type: Monitor holder\nHeight Adjustment Range: 0-260 mm\nRotation: +90°"
    fake_supabase = RecordingSupabase()
    monkeypatch.setattr(app_module, "supabase", fake_supabase)
    monkeypatch.setattr(
        app_module,
        "get_asset_by_id",
        lambda asset_id, request=None: {
            "asset_id": asset_id,
            "asset_tag_number": "HELP-UKR-0572",
            "usage_type": "standard",
            "item_description": multiline_description,
            "brand_make": "RZTK",
            "model": "NB-F80",
            "asset_classification": "EQUIPMENT",
            "asset_sub_classification": "Computer Accessories",
            "quantity": 1,
            "purchase_price": 20.31,
            "currency": "EUR",
            "serial_chassis_number": "SN-0572",
            "current_status": "functional",
            "remarks": "Old remarks",
            "tenant_id": app_module.DEFAULT_TENANT_ID,
        },
    )
    audit_calls = []
    monkeypatch.setattr(app_module, "audit_log_event", lambda **kwargs: audit_calls.append(kwargs) or True)

    response = app_module.admin_asset_edit(
        make_admin_request(),
        657,
        usage_type="standard",
        item_description=multiline_description,
        brand_make="RZTK",
        model="NB-F80",
        asset_classification="EQUIPMENT",
        asset_sub_classification="Computer Accessories",
        quantity="1",
        purchase_price="20.31",
        currency="EUR",
        serial_number="SN-0572",
        current_status="functional",
        remarks="Updated remarks",
    )

    update_operation = fake_supabase.operations[0]
    assert response.status_code == 303
    assert update_operation["filters"] == [
        ("eq", "tenant_id", app_module.DEFAULT_TENANT_ID),
        ("eq", "asset_id", 657),
    ]
    assert update_operation["payload"]["item_description"] == multiline_description
    assert update_operation["payload"]["remarks"] == "Updated remarks"
    assert {call["field_name"] for call in audit_calls} == {"remarks"}
    assert audit_calls[0]["old_value"] == "Old remarks"
    assert audit_calls[0]["new_value"] == "Updated remarks"
    assert audit_calls[0]["request"].session["admin_username"] == "admin"


def test_asset_edit_preserves_description_lf_bytes_when_browser_posts_crlf(app_module, monkeypatch):
    existing_description = "Line 1\nLine 2\nLine 3"
    submitted_description = "Line 1\r\nLine 2\r\nLine 3"
    fake_supabase = RecordingSupabase()
    monkeypatch.setattr(app_module, "supabase", fake_supabase)
    monkeypatch.setattr(
        app_module,
        "get_asset_by_id",
        lambda asset_id, request=None: {
            "asset_id": asset_id,
            "asset_tag_number": "HELP-UKR-0572",
            "usage_type": "standard",
            "item_description": existing_description,
            "brand_make": "RZTK",
            "model": "NB-F80",
            "asset_classification": "EQUIPMENT",
            "asset_sub_classification": "Computer Accessories",
            "quantity": 1,
            "purchase_price": 20.31,
            "currency": "EUR",
            "serial_chassis_number": "SN-0572",
            "current_status": "functional",
            "remarks": "Old remarks",
            "tenant_id": app_module.DEFAULT_TENANT_ID,
        },
    )
    audit_calls = []
    monkeypatch.setattr(app_module, "audit_log_event", lambda **kwargs: audit_calls.append(kwargs) or True)

    app_module.admin_asset_edit(
        make_admin_request(),
        657,
        usage_type="standard",
        item_description=submitted_description,
        brand_make="RZTK",
        model="NB-F80",
        asset_classification="EQUIPMENT",
        asset_sub_classification="Computer Accessories",
        quantity="1",
        purchase_price="20.31",
        currency="EUR",
        serial_number="SN-0572",
        current_status="functional",
        remarks="Updated remarks",
    )

    update_operation = fake_supabase.operations[0]
    assert update_operation["filters"] == [
        ("eq", "tenant_id", app_module.DEFAULT_TENANT_ID),
        ("eq", "asset_id", 657),
    ]
    assert update_operation["payload"]["item_description"] == existing_description
    assert "\r" not in update_operation["payload"]["item_description"]
    assert update_operation["payload"]["remarks"] == "Updated remarks"
    assert {call["field_name"] for call in audit_calls} == {"remarks"}


def test_asset_edit_preserves_remarks_lf_bytes_when_browser_posts_crlf(app_module, monkeypatch):
    existing_remarks = "Remark 1\nRemark 2"
    submitted_remarks = "Remark 1\r\nRemark 2"
    fake_supabase = RecordingSupabase()
    monkeypatch.setattr(app_module, "supabase", fake_supabase)
    monkeypatch.setattr(
        app_module,
        "get_asset_by_id",
        lambda asset_id, request=None: {
            "asset_id": asset_id,
            "asset_tag_number": "HELP-UKR-0572",
            "usage_type": "standard",
            "item_description": "Description",
            "brand_make": "RZTK",
            "model": "Old model",
            "asset_classification": "EQUIPMENT",
            "asset_sub_classification": "Computer Accessories",
            "quantity": 1,
            "purchase_price": 20.31,
            "currency": "EUR",
            "serial_chassis_number": "SN-0572",
            "current_status": "functional",
            "remarks": existing_remarks,
            "tenant_id": app_module.DEFAULT_TENANT_ID,
        },
    )
    audit_calls = []
    monkeypatch.setattr(app_module, "audit_log_event", lambda **kwargs: audit_calls.append(kwargs) or True)

    app_module.admin_asset_edit(
        make_admin_request(),
        657,
        usage_type="standard",
        item_description="Description",
        brand_make="RZTK",
        model="New model",
        asset_classification="EQUIPMENT",
        asset_sub_classification="Computer Accessories",
        quantity="1",
        purchase_price="20.31",
        currency="EUR",
        serial_number="SN-0572",
        current_status="functional",
        remarks=submitted_remarks,
    )

    update_operation = fake_supabase.operations[0]
    assert update_operation["payload"]["remarks"] == existing_remarks
    assert "\r" not in update_operation["payload"]["remarks"]
    assert update_operation["payload"]["model"] == "New model"
    assert {call["field_name"] for call in audit_calls} == {"model"}


def test_asset_edit_audits_genuine_multiline_description_change(app_module, monkeypatch):
    existing_description = "Line 1\nLine 2"
    submitted_description = "Line 1\r\nChanged line"
    fake_supabase = RecordingSupabase()
    monkeypatch.setattr(app_module, "supabase", fake_supabase)
    monkeypatch.setattr(
        app_module,
        "get_asset_by_id",
        lambda asset_id, request=None: {
            "asset_id": asset_id,
            "asset_tag_number": "HELP-UKR-0572",
            "usage_type": "standard",
            "item_description": existing_description,
            "brand_make": "RZTK",
            "model": "NB-F80",
            "asset_classification": "EQUIPMENT",
            "asset_sub_classification": "Computer Accessories",
            "quantity": 1,
            "purchase_price": 20.31,
            "currency": "EUR",
            "serial_chassis_number": "SN-0572",
            "current_status": "functional",
            "remarks": "Remarks",
            "tenant_id": app_module.DEFAULT_TENANT_ID,
        },
    )
    audit_calls = []
    monkeypatch.setattr(app_module, "audit_log_event", lambda **kwargs: audit_calls.append(kwargs) or True)

    app_module.admin_asset_edit(
        make_admin_request(),
        657,
        usage_type="standard",
        item_description=submitted_description,
        brand_make="RZTK",
        model="NB-F80",
        asset_classification="EQUIPMENT",
        asset_sub_classification="Computer Accessories",
        quantity="1",
        purchase_price="20.31",
        currency="EUR",
        serial_number="SN-0572",
        current_status="functional",
        remarks="Remarks",
    )

    update_operation = fake_supabase.operations[0]
    assert update_operation["payload"]["item_description"] == submitted_description.strip()
    assert {call["field_name"] for call in audit_calls} == {"item_description"}


def test_asset_edit_clearing_description_and_remarks_still_sets_none_and_audits(app_module, monkeypatch):
    fake_supabase = RecordingSupabase()
    monkeypatch.setattr(app_module, "supabase", fake_supabase)
    monkeypatch.setattr(
        app_module,
        "get_asset_by_id",
        lambda asset_id, request=None: {
            "asset_id": asset_id,
            "asset_tag_number": "HELP-UKR-0572",
            "usage_type": "standard",
            "item_description": "Line 1\nLine 2",
            "brand_make": "RZTK",
            "model": "NB-F80",
            "asset_classification": "EQUIPMENT",
            "asset_sub_classification": "Computer Accessories",
            "quantity": 1,
            "purchase_price": 20.31,
            "currency": "EUR",
            "serial_chassis_number": "SN-0572",
            "current_status": "functional",
            "remarks": "Remark 1\nRemark 2",
            "tenant_id": app_module.DEFAULT_TENANT_ID,
        },
    )
    audit_calls = []
    monkeypatch.setattr(app_module, "audit_log_event", lambda **kwargs: audit_calls.append(kwargs) or True)

    app_module.admin_asset_edit(
        make_admin_request(),
        657,
        usage_type="standard",
        item_description="",
        brand_make="RZTK",
        model="NB-F80",
        asset_classification="EQUIPMENT",
        asset_sub_classification="Computer Accessories",
        quantity="1",
        purchase_price="20.31",
        currency="EUR",
        serial_number="SN-0572",
        current_status="functional",
        remarks="",
    )

    update_operation = fake_supabase.operations[0]
    assert update_operation["payload"]["item_description"] is None
    assert update_operation["payload"]["remarks"] is None
    assert {call["field_name"] for call in audit_calls} == {"item_description", "remarks"}


def test_assignment_update_closes_current_assignment_inserts_new_status_and_updates_asset(app_module, monkeypatch):
    fake_supabase = RecordingSupabase(
        {
            ("asset_assignments", "select"): [{"assignment_id": 77}],
            ("persons", "select"): [{"person_id": 12}],
            ("locations", "select"): [{"location_id": 4}],
        }
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
            "tenant_id": app_module.DEFAULT_TENANT_ID,
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
    close_select = [
        operation
        for operation in fake_supabase.operations
        if operation["table"] == "asset_assignments" and operation["action"] == "select"
    ][0]
    assert close_select["filters"] == [
        ("eq", "tenant_id", app_module.DEFAULT_TENANT_ID),
        ("eq", "asset_id", 101),
        ("is", "return_date", "null"),
    ]
    close_update = [
        operation
        for operation in fake_supabase.operations
        if operation["table"] == "asset_assignments" and operation["action"] == "update"
    ][0]
    assert close_update["payload"]["return_date"] == "2026-08-13"
    inserted_assignment = [
        operation
        for operation in fake_supabase.operations
        if operation["table"] == "asset_assignments" and operation["action"] == "insert"
    ][0]["payload"]
    assert inserted_assignment["tenant_id"] == app_module.DEFAULT_TENANT_ID
    assert inserted_assignment["asset_id"] == 101
    assert inserted_assignment["person_id"] == 12
    assert inserted_assignment["location_id"] == 4
    assert inserted_assignment["assignment_department"] == "PROGRAM"
    assert inserted_assignment["status"] == "Not functional"
    assert inserted_assignment["updated_by"] == "admin"
    asset_update = [
        operation
        for operation in fake_supabase.operations
        if operation["table"] == "assets" and operation["action"] == "update"
    ][0]
    assert asset_update["payload"] == {"current_status": "Not functional"}


def test_transfer_creation_records_asset_movement_and_project_history(app_module, monkeypatch):
    fake_supabase = RecordingSupabase(
        {
            ("asset_transfers", "insert"): [{"transfer_id": 55}],
            ("persons", "select"): [{"person_id": 13, "name_eng": "New Holder"}],
        }
    )
    monkeypatch.setattr(app_module, "supabase", fake_supabase)
    monkeypatch.setattr(app_module, "get_person_by_id", lambda person_id, request=None: {"person_id": person_id, "name_eng": "New Holder"})
    monkeypatch.setattr(
        app_module,
        "get_asset_projects",
        lambda asset_id, request=None: [
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
            "tenant_id": app_module.DEFAULT_TENANT_ID,
        },
        from_assignment={
            "person_id": 12,
            "location_id": 4,
            "responsible_person": "Old Holder",
            "status": "functional",
            "handover_condition": "New",
        },
        to_person_id=13,
        transfer_date="2026-08-13",
        transfer_reason="Assignment changed in web app",
        status="Not functional",
        condition="Used",
        to_location_id=5,
    )

    assert transfer_id == 55
    transfer_payload = [
        operation
        for operation in fake_supabase.operations
        if operation["table"] == "asset_transfers" and operation["action"] == "insert"
    ][0]["payload"]
    assert transfer_payload["tenant_id"] == app_module.DEFAULT_TENANT_ID
    assert transfer_payload["asset_id"] == 101
    assert transfer_payload["from_person_id"] == 12
    assert transfer_payload["to_person_id"] == 13
    assert transfer_payload["from_location_id"] == 4
    assert transfer_payload["to_location_id"] == 5
    assert transfer_payload["from_holder_name"] == "Old Holder"
    assert transfer_payload["to_holder_name"] == "New Holder"
    assert transfer_payload["asset_status"] == "Not functional"
    assert transfer_payload["from_project_raw"] == "GLO-001"
    assert "description_snapshot" not in transfer_payload
    assert "serial_snapshot" not in transfer_payload
    project_payloads = [
        operation
        for operation in fake_supabase.operations
        if operation["table"] == "asset_transfer_projects" and operation["action"] == "insert"
    ][0]["payload"]
    assert {row["direction"] for row in project_payloads} == {"from", "to"}
    assert all(row["transfer_id"] == 55 for row in project_payloads)
    assert all(row["tenant_id"] == app_module.DEFAULT_TENANT_ID for row in project_payloads)


def test_transfer_insert_failure_is_not_silently_swallowed(app_module, monkeypatch):
    fake_supabase = FailingInsertSupabase(
        "asset_transfers",
        fail_message="schema column missing",
        responses={("persons", "select"): [{"person_id": 13, "name_eng": "New Holder"}]},
    )
    monkeypatch.setattr(app_module, "supabase", fake_supabase)
    monkeypatch.setattr(app_module, "get_person_by_id", lambda person_id, request=None: {"person_id": person_id, "name_eng": "New Holder"})
    monkeypatch.setattr(app_module, "get_asset_projects", lambda asset_id, request=None: [])

    result = None
    try:
        app_module.create_asset_transfer_from_assignment_change(
            asset={
                "asset_id": 101,
                "asset_tag_number": "HELP-UKR-0753",
                "tenant_id": app_module.DEFAULT_TENANT_ID,
            },
            from_assignment={"person_id": 12, "location_id": 4, "responsible_person": "Old Holder"},
            to_person_id=13,
            to_location_id=5,
            transfer_date="2026-08-13",
            transfer_reason="Assignment changed in web app",
        )
    except RuntimeError as error:
        result = str(error)

    assert result == "Asset transfer could not be created: schema column missing"


def test_assignment_flow_does_not_report_success_when_transfer_creation_fails(app_module, monkeypatch):
    fake_supabase = FailingInsertSupabase(
        "asset_transfers",
        fail_message="schema column missing",
        responses={
            ("asset_assignments", "select"): [{"assignment_id": 77}],
            ("persons", "select"): [{"person_id": 12}],
            ("locations", "select"): [{"location_id": 4}],
        },
    )
    monkeypatch.setattr(app_module, "supabase", fake_supabase)
    monkeypatch.setattr(app_module, "log_assignment_field_changes", lambda *args, **kwargs: None)
    monkeypatch.setattr(app_module, "supports_asset_assignment_actor_columns", lambda: True)
    monkeypatch.setattr(app_module, "supports_asset_assignment_department_column", lambda: True)
    monkeypatch.setattr(app_module, "get_person_by_id", lambda person_id, request=None: {"person_id": person_id, "name_eng": "New Holder"})
    monkeypatch.setattr(app_module, "get_asset_projects", lambda asset_id, request=None: [])

    result = None
    try:
        app_module.apply_asset_assignment_change(
            asset={
                "asset_id": 101,
                "asset_tag_number": "HELP-UKR-0753",
                "current_status": "functional",
                "tenant_id": app_module.DEFAULT_TENANT_ID,
                "current_assignment": {
                    "assignment_id": 77,
                    "person_id": 12,
                    "location_id": 4,
                    "assignment_date": "2026-06-01",
                    "status": "functional",
                    "responsible_person": "Old Holder",
                },
            },
            parsed_person_id=None,
            parsed_location_id=4,
            assignment_department="PROGRAM",
            assignment_date="2026-08-13",
            status="functional",
            notes="Updated holder",
            handover_condition="Used",
            assignment_scope="warehouse",
            custody_note="",
            request=make_admin_request(),
        )
    except RuntimeError as error:
        result = str(error)

    assert result == "Asset transfer could not be created: schema column missing"


def test_assignment_date_earlier_than_current_is_rejected_before_mutation(app_module, monkeypatch):
    fake_supabase = RecordingSupabase(
        {
            ("persons", "select"): [{"person_id": 12}],
            ("locations", "select"): [{"location_id": 4}],
        }
    )
    monkeypatch.setattr(app_module, "supabase", fake_supabase)

    result = None
    try:
        app_module.apply_asset_assignment_change(
            asset={
                "asset_id": 101,
                "asset_tag_number": "HELP-UKR-0753",
                "current_status": "functional",
                "tenant_id": app_module.DEFAULT_TENANT_ID,
                "current_assignment": {
                    "assignment_id": 77,
                    "person_id": 12,
                    "location_id": 4,
                    "assignment_date": "2026-08-13",
                    "status": "functional",
                    "responsible_person": "Old Holder",
                },
            },
            parsed_person_id=12,
            parsed_location_id=4,
            assignment_department="PROGRAM",
            assignment_date="2026-08-12",
            status="functional",
            notes="Too early",
            handover_condition="Used",
            assignment_scope="personal",
            custody_note="",
            request=make_admin_request(),
        )
    except ValueError as error:
        result = str(error)

    assert result == "Assignment date cannot be earlier than the current assignment date (2026-08-13)."
    assert not any(operation["table"] == "asset_assignments" and operation["action"] in {"insert", "update"} for operation in fake_supabase.operations)


TENANT_TWO_ID = "00000000-0000-4000-8000-000000000002"


def empty_sync_context():
    return {
        "person_lookup": {},
        "location_lookup": {},
        "project_lookup": {},
        "donor_lookup": {},
        "assignment_by_asset_id": {},
        "projects_by_asset_id": {},
        "payments_by_asset_id": {},
        "transfers_by_id": {},
        "transfer_signatures": set(),
        "supports_asset_project_purchase_origin": False,
    }


def test_excel_sync_new_asset_insert_includes_tenant_id(app_module, monkeypatch):
    fake_supabase = RecordingSupabase(
        {
            ("tenants", "select"): [
                {"tenant_id": app_module.DEFAULT_TENANT_ID, "status": "active"}
            ],
            ("assets", "insert"): [
                {
                    "asset_id": 101,
                    "asset_tag_number": "HELP-UKR-0753",
                    "tenant_id": app_module.DEFAULT_TENANT_ID,
                }
            ],
        }
    )
    monkeypatch.setattr(app_module, "supabase", fake_supabase)
    monkeypatch.setattr(app_module, "build_sync_context", lambda request: empty_sync_context())
    request = make_admin_request()

    result = app_module.apply_sync_preview(
        {
            "tenant_id": app_module.DEFAULT_TENANT_ID,
            "new_records": [
                {
                    "asset_tag_number": "HELP-UKR-0753",
                    "usage_type": "standard",
                    "item_description": "Monitor holder",
                    "current_status": "functional",
                }
            ],
            "changed_records": [],
            "transfer_log": {"new_records": []},
        },
        request,
    )

    assert result["inserted"] == 1
    asset_insert = next(
        operation
        for operation in fake_supabase.operations
        if operation["table"] == "assets" and operation["action"] == "insert"
    )
    assert asset_insert["table"] == "assets"
    assert asset_insert["payload"]["tenant_id"] == app_module.DEFAULT_TENANT_ID
    assert asset_insert["payload"]["asset_tag_number"] == "HELP-UKR-0753"


def test_tenant_two_excel_apply_keeps_new_asset_and_audit_in_tenant(app_module, monkeypatch):
    request = make_admin_request(TENANT_TWO_ID)
    fake_supabase = RecordingSupabase(
        {
            ("tenants", "select"): [{"tenant_id": TENANT_TWO_ID, "status": "active"}],
            ("assets", "insert"): [
                {"asset_id": 201, "asset_tag_number": "SYN-T2-EXCEL-001", "tenant_id": TENANT_TWO_ID}
            ],
        }
    )
    monkeypatch.setattr(app_module, "supabase", fake_supabase)
    monkeypatch.setattr(app_module, "build_sync_context", lambda request: empty_sync_context())
    monkeypatch.setattr(app_module, "asset_tag_exists", lambda asset_tag: False)

    result = app_module.apply_sync_preview(
        {
            "tenant_id": TENANT_TWO_ID,
            "new_records": [
                {
                    "asset_tag_number": "SYN-T2-EXCEL-001",
                    "usage_type": "standard",
                    "item_description": "Tenant two monitor",
                    "current_status": "functional",
                }
            ],
            "changed_records": [],
            "transfer_log": {"new_records": []},
        },
        request,
    )

    asset_insert = next(
        operation for operation in fake_supabase.operations
        if operation["table"] == "assets" and operation["action"] == "insert"
    )
    audit_insert = next(
        operation for operation in fake_supabase.operations
        if operation["table"] == "audit_log" and operation["action"] == "insert"
    )
    assert result["inserted"] == 1
    assert asset_insert["payload"]["tenant_id"] == TENANT_TWO_ID
    assert audit_insert["payload"]["tenant_id"] == TENANT_TWO_ID


def test_tenant_two_excel_apply_updates_existing_asset_in_tenant(app_module, monkeypatch):
    request = make_admin_request(TENANT_TWO_ID)
    fake_supabase = RecordingSupabase(
        {
            ("tenants", "select"): [{"tenant_id": TENANT_TWO_ID, "status": "active"}],
            ("assets", "select"): [{"asset_id": 202}],
        }
    )
    monkeypatch.setattr(app_module, "supabase", fake_supabase)
    monkeypatch.setattr(app_module, "build_sync_context", lambda request: empty_sync_context())

    result = app_module.apply_sync_preview(
        {
            "tenant_id": TENANT_TWO_ID,
            "new_records": [],
            "changed_records": [
                {
                    "asset_id": 202,
                    "asset_tag_number": "SYN-T2-EXCEL-002",
                    "changed_fields": ["remarks"],
                    "record": {"remarks": "Tenant two correction"},
                }
            ],
            "transfer_log": {"new_records": []},
        },
        request,
    )

    asset_update = next(
        operation for operation in fake_supabase.operations
        if operation["table"] == "assets" and operation["action"] == "update"
    )
    audit_insert = next(
        operation for operation in fake_supabase.operations
        if operation["table"] == "audit_log" and operation["action"] == "insert"
    )
    assert result["updated"] == 1
    assert ("eq", "tenant_id", TENANT_TWO_ID) in asset_update["filters"]
    assert audit_insert["payload"]["tenant_id"] == TENANT_TWO_ID


def test_model_only_excel_apply_does_not_reinsert_exported_transfer(app_module, monkeypatch):
    request = make_admin_request(TENANT_TWO_ID)
    transfer = {
        "transfer_id": 188,
        "asset_id": 1232,
        "transfer_date": "2026-08-29",
        "from_holder_name": "Warehouse",
        "to_holder_name": "Synthetic Tenant #2 Admin",
        "from_project_raw": "SYN-20001",
        "to_project_raw": "SYN-20001",
        "asset_status": "functional",
        "transfer_reason": "Assignment changed in web app",
    }
    context = empty_sync_context()
    context["transfers_by_id"] = {188: transfer}
    context["transfer_signatures"] = {
        app_module.make_transfer_signature(1232, transfer)
    }
    monkeypatch.setattr(app_module, "build_sync_context", lambda request: context)

    preview = app_module.build_sync_preview(
        [
            {
                "asset_tag_number": "SYN-T2-0001",
                "usage_type": "standard",
                "model": "T2-SYNC-REHEARSAL",
            }
        ],
        [
            {
                "asset_id": 1232,
                "asset_tag_number": "SYN-T2-0001",
                "usage_type": "standard",
                "model": None,
            }
        ],
        [
            {
                "system_transfer_id": 188,
                "asset_tag_number": "SYN-T2-0001",
                "transfer_date": "2026-08-29",
                "from_holder_name": "Warehouse",
                "to_holder_name": "Synthetic Tenant #2 Admin",
            }
        ],
        request=request,
    )

    assert preview["summary"]["changed_records"] == 1
    assert preview["changed_records"][0]["changed_fields"] == ["model"]
    assert preview["transfer_log"]["summary"]["new_records"] == 0
    assert preview["transfer_log"]["summary"]["skipped_existing"] == 1

    fake_supabase = RecordingSupabase(
        {
            ("tenants", "select"): [{"tenant_id": TENANT_TWO_ID, "status": "active"}],
            ("assets", "select"): [{"asset_id": 1232}],
        }
    )
    monkeypatch.setattr(app_module, "supabase", fake_supabase)
    result = app_module.apply_sync_preview(preview, request)

    assert result["updated"] == 1
    assert result["transfer_updated"] == 0
    assert not any(
        operation["table"] == "asset_transfers" and operation["action"] == "insert"
        for operation in fake_supabase.operations
    )


def test_tenant_two_sync_assignment_uses_tenant_parents_and_payload(app_module, monkeypatch):
    request = make_admin_request(TENANT_TWO_ID)
    person = {"person_id": 63, "name_eng": "Tenant Two Holder", "department": "PROGRAM"}
    location = {"location_id": 59, "city": "Synthetic City", "department": "PROGRAM"}
    fake_supabase = RecordingSupabase(
        {
            ("assets", "select"): [{"asset_id": 202}],
            ("persons", "select"): [{"person_id": 63}],
            ("locations", "select"): [{"location_id": 59}],
            ("asset_assignments", "select"): [],
        }
    )
    monkeypatch.setattr(app_module, "supabase", fake_supabase)
    monkeypatch.setattr(app_module, "supports_asset_assignment_actor_columns", lambda: True)
    monkeypatch.setattr(app_module, "supports_asset_assignment_department_column", lambda: True)
    context = empty_sync_context()
    context["person_lookup"] = app_module.build_person_lookup([person])
    context["location_lookup"] = app_module.build_location_lookup([location])

    applied = app_module.apply_sync_assignment(
        202,
        {
            "recipient_name": "Tenant Two Holder",
            "location_name": "Synthetic City",
            "department_name": "PROGRAM",
            "current_status": "functional",
        },
        context,
        request,
    )

    assignment_insert = next(
        operation for operation in fake_supabase.operations
        if operation["table"] == "asset_assignments" and operation["action"] == "insert"
    )
    parent_selects = [
        operation for operation in fake_supabase.operations
        if operation["table"] in {"assets", "persons", "locations"} and operation["action"] == "select"
    ]
    assert applied == 1
    assert assignment_insert["payload"]["tenant_id"] == TENANT_TWO_ID
    assert all(("eq", "tenant_id", TENANT_TWO_ID) in operation["filters"] for operation in parent_selects)


def test_tenant_two_sync_project_and_payment_rows_keep_tenant(app_module, monkeypatch):
    request = make_admin_request(TENANT_TWO_ID)
    fake_supabase = RecordingSupabase({("assets", "select"): [{"asset_id": 202}]})
    monkeypatch.setattr(app_module, "supabase", fake_supabase)
    context = empty_sync_context()
    context["project_lookup"] = app_module.build_project_lookup(
        [{"project_id": 20, "project_number": "SYN-20001"}]
    )
    context["donor_lookup"] = app_module.build_donor_lookup([{"donor_id": 8, "donor_name": "SYN-DONOR"}])
    project_record = {
        "purchased_project_no": "SYN-20001",
        "purchased_donor_name": "SYN-DONOR",
        "current_status": "functional",
    }

    project_count = app_module.apply_sync_project(202, project_record, context, request)
    payment_count = app_module.apply_sync_payments(
        202,
        {"remarks": "1000 UAH - 01.08.2026", "currency": "UAH"},
        request,
    )

    project_insert = next(
        operation for operation in fake_supabase.operations
        if operation["table"] == "asset_projects" and operation["action"] == "insert"
    )
    payment_insert = next(
        operation for operation in fake_supabase.operations
        if operation["table"] == "asset_payments" and operation["action"] == "insert"
    )
    assert project_count == 1
    assert payment_count == 1
    assert project_insert["payload"]["tenant_id"] == TENANT_TWO_ID
    assert project_insert["payload"]["project_id"] == 20
    assert project_insert["payload"]["donor_id"] == 8
    assert all(row["tenant_id"] == TENANT_TWO_ID for row in payment_insert["payload"])


def test_tenant_two_sync_transfer_projects_and_audit_keep_tenant(app_module, monkeypatch):
    request = make_admin_request(TENANT_TWO_ID)
    fake_supabase = RecordingSupabase(
        {
            ("assets", "select"): [{"asset_id": 202}],
            ("persons", "select"): [{"person_id": 63}],
            ("asset_transfers", "insert"): [{"transfer_id": 188}],
        }
    )
    monkeypatch.setattr(app_module, "supabase", fake_supabase)
    context = empty_sync_context()
    context["project_lookup"] = app_module.build_project_lookup(
        [{"project_id": 20, "project_number": "SYN-20001"}]
    )

    applied = app_module.apply_sync_transfer(
        {
            "asset_id": 202,
            "asset_tag_number": "SYN-T2-EXCEL-002",
            "from_person_id": None,
            "to_person_id": 63,
            "from_holder_name": "Warehouse",
            "to_holder_name": "Tenant Two Holder",
            "from_project_raw": "SYN-20001",
            "to_project_raw": "SYN-20001",
            "transfer_date": "2026-08-31",
        },
        context,
        request,
    )

    transfer_insert = next(
        operation for operation in fake_supabase.operations
        if operation["table"] == "asset_transfers" and operation["action"] == "insert"
    )
    project_insert = next(
        operation for operation in fake_supabase.operations
        if operation["table"] == "asset_transfer_projects" and operation["action"] == "insert"
    )
    audit_insert = next(
        operation for operation in fake_supabase.operations
        if operation["table"] == "audit_log" and operation["action"] == "insert"
    )
    assert applied == 1
    assert transfer_insert["payload"]["tenant_id"] == TENANT_TWO_ID
    assert all(row["tenant_id"] == TENANT_TWO_ID for row in project_insert["payload"])
    assert audit_insert["payload"]["tenant_id"] == TENANT_TWO_ID


@pytest.mark.parametrize(
    ("preview_tenant_id", "session_tenant_id"),
    [
        ("00000000-0000-4000-8000-000000000001", TENANT_TWO_ID),
        (TENANT_TWO_ID, "00000000-0000-4000-8000-000000000001"),
    ],
)
def test_excel_preview_cannot_be_applied_by_another_tenant(
    app_module,
    monkeypatch,
    preview_tenant_id,
    session_tenant_id,
):
    fake_supabase = RecordingSupabase(
        {("tenants", "select"): [{"tenant_id": session_tenant_id, "status": "active"}]}
    )
    monkeypatch.setattr(app_module, "supabase", fake_supabase)

    with pytest.raises(app_module.TenantContextError, match="belongs to a different tenant"):
        app_module.apply_sync_preview(
            {
                "tenant_id": preview_tenant_id,
                "new_records": [{"asset_tag_number": "SHOULD-NOT-WRITE"}],
                "changed_records": [],
                "transfer_log": {"new_records": []},
            },
            make_admin_request(session_tenant_id),
        )

    assert not any(operation["action"] in {"insert", "update", "delete"} for operation in fake_supabase.operations)


def test_excel_apply_requires_preview_tenant_and_trusted_request_before_writes(app_module, monkeypatch):
    fake_supabase = RecordingSupabase(
        {("tenants", "select"): [{"tenant_id": TENANT_TWO_ID, "status": "active"}]}
    )
    monkeypatch.setattr(app_module, "supabase", fake_supabase)
    preview = {
        "new_records": [{"asset_tag_number": "SHOULD-NOT-WRITE"}],
        "changed_records": [],
        "transfer_log": {"new_records": []},
    }

    with pytest.raises(app_module.TenantContextError, match="missing tenant identity"):
        app_module.apply_sync_preview(preview, make_admin_request(TENANT_TWO_ID))
    with pytest.raises(app_module.TenantContextError, match="authenticated tenant context"):
        app_module.apply_sync_preview({**preview, "tenant_id": TENANT_TWO_ID})

    assert not any(operation["action"] in {"insert", "update", "delete"} for operation in fake_supabase.operations)


def test_excel_apply_rejects_inactive_tenant_before_writes(app_module, monkeypatch):
    fake_supabase = RecordingSupabase({("tenants", "select"): []})
    monkeypatch.setattr(app_module, "supabase", fake_supabase)

    with pytest.raises(app_module.TenantContextError, match="missing or inactive"):
        app_module.apply_sync_preview(
            {
                "tenant_id": TENANT_TWO_ID,
                "new_records": [{"asset_tag_number": "SHOULD-NOT-WRITE"}],
                "changed_records": [],
                "transfer_log": {"new_records": []},
            },
            make_admin_request(TENANT_TWO_ID),
        )

    assert not any(operation["action"] in {"insert", "update", "delete"} for operation in fake_supabase.operations)


def test_excel_apply_rejects_malformed_preview_tenant_before_writes(app_module, monkeypatch):
    fake_supabase = RecordingSupabase(
        {("tenants", "select"): [{"tenant_id": TENANT_TWO_ID, "status": "active"}]}
    )
    monkeypatch.setattr(app_module, "supabase", fake_supabase)

    with pytest.raises(app_module.TenantContextError, match="invalid tenant identity"):
        app_module.apply_sync_preview(
            {
                "tenant_id": "../../tenant-one",
                "new_records": [{"asset_tag_number": "SHOULD-NOT-WRITE"}],
                "changed_records": [],
                "transfer_log": {"new_records": []},
            },
            make_admin_request(TENANT_TWO_ID),
        )

    assert not any(operation["action"] in {"insert", "update", "delete"} for operation in fake_supabase.operations)


def test_excel_apply_preflights_all_asset_parents_before_first_write(app_module, monkeypatch):
    fake_supabase = RecordingSupabase(
        {("tenants", "select"): [{"tenant_id": TENANT_TWO_ID, "status": "active"}]}
    )
    monkeypatch.setattr(app_module, "supabase", fake_supabase)
    monkeypatch.setattr(app_module, "build_sync_context", lambda request: empty_sync_context())
    monkeypatch.setattr(app_module, "asset_tag_exists", lambda asset_tag: False)

    with pytest.raises(app_module.TenantContextError, match="does not belong to the current tenant"):
        app_module.apply_sync_preview(
            {
                "tenant_id": TENANT_TWO_ID,
                "new_records": [{"asset_tag_number": "SYN-T2-WOULD-BE-PARTIAL"}],
                "changed_records": [
                    {
                        "asset_id": 287,
                        "asset_tag_number": "TENANT-ONE-ASSET",
                        "changed_fields": ["remarks"],
                        "record": {"remarks": "Cross-tenant attempt"},
                    }
                ],
                "transfer_log": {"new_records": []},
            },
            make_admin_request(TENANT_TWO_ID),
        )

    assert not any(operation["action"] in {"insert", "update", "delete"} for operation in fake_supabase.operations)


def test_sync_artifacts_and_state_are_isolated_by_server_tenant(app_module, monkeypatch, tmp_path):
    monkeypatch.setattr(app_module, "SYNC_STORAGE_DIR", str(tmp_path))
    monkeypatch.setattr(app_module, "sync_storage_object_exists", lambda request: False)
    tenant_one_request = make_admin_request()
    tenant_two_request = make_admin_request(TENANT_TWO_ID)

    tenant_one_paths = app_module.get_sync_artifact_paths(tenant_one_request)
    tenant_two_paths = app_module.get_sync_artifact_paths(tenant_two_request)

    assert tenant_one_paths["workbook"] != tenant_two_paths["workbook"]
    assert tenant_one_paths["state"] != tenant_two_paths["state"]
    assert tenant_one_paths["storage_workbook"] != tenant_two_paths["storage_workbook"]
    assert app_module.DEFAULT_TENANT_ID in tenant_one_paths["storage_workbook"]
    assert TENANT_TWO_ID in tenant_two_paths["storage_workbook"]

    app_module.save_sync_state(
        {
            "tenant_id": app_module.DEFAULT_TENANT_ID,
            "file_name": "tenant-one.xlsx",
            "preview": {"tenant_id": app_module.DEFAULT_TENANT_ID},
        },
        tenant_one_request,
    )
    assert app_module.load_sync_state(tenant_two_request) == {}

    with open(tenant_two_paths["state"], "w", encoding="utf-8") as file:
        file.write(
            '{"tenant_id": "00000000-0000-4000-8000-000000000001", '
            '"preview": {"tenant_id": "00000000-0000-4000-8000-000000000001"}}'
        )
    with pytest.raises(app_module.TenantContextError, match="state belongs to a different tenant"):
        app_module.load_sync_state(tenant_two_request)

    app_module.save_sync_state(
        {
            "tenant_id": TENANT_TWO_ID,
            "file_name": "tenant-two.xlsx",
            "preview": {"tenant_id": TENANT_TWO_ID},
        },
        tenant_two_request,
    )
    assert app_module.load_sync_state(tenant_one_request)["file_name"] == "tenant-one.xlsx"
    assert app_module.load_sync_state(tenant_two_request)["file_name"] == "tenant-two.xlsx"


def test_sync_tenants_do_not_fallback_to_legacy_global_local_workbook(app_module, monkeypatch, tmp_path):
    monkeypatch.setattr(app_module, "SYNC_STORAGE_DIR", str(tmp_path))
    monkeypatch.setattr(app_module, "download_sync_workbook_from_storage", lambda request, target_path=None: False)
    legacy_path = tmp_path / app_module.SYNC_WORKBOOK_FILENAME
    legacy_path.write_bytes(b"untrusted-legacy-workbook")

    for request in [make_admin_request(), make_admin_request(TENANT_TWO_ID)]:
        paths = app_module.get_sync_artifact_paths(request)
        with pytest.raises(ValueError, match="No official workbook is available"):
            app_module.ensure_sync_workbook_template(request)
        assert not os.path.exists(paths["workbook"])

    assert legacy_path.read_bytes() == b"untrusted-legacy-workbook"


def test_sync_tenants_never_request_legacy_global_storage_workbook(app_module, monkeypatch, tmp_path):
    class RecordingBucket:
        def __init__(self):
            self.download_paths = []

        def download(self, path):
            self.download_paths.append(path)
            if path == f"sync/{app_module.SYNC_WORKBOOK_FILENAME}":
                return b"untrusted-legacy-workbook"
            raise FileNotFoundError(path)

    bucket = RecordingBucket()
    monkeypatch.setattr(app_module, "SYNC_STORAGE_DIR", str(tmp_path))
    monkeypatch.setattr(app_module, "get_sync_storage_bucket", lambda: bucket)
    tenant_one_request = make_admin_request()
    tenant_two_request = make_admin_request(TENANT_TWO_ID)

    for request in [tenant_one_request, tenant_two_request]:
        with pytest.raises(ValueError, match="No official workbook is available"):
            app_module.ensure_sync_workbook_template(request)

    expected_paths = {
        app_module.get_sync_artifact_paths(tenant_one_request)["storage_workbook"],
        app_module.get_sync_artifact_paths(tenant_two_request)["storage_workbook"],
    }
    assert set(bucket.download_paths) == expected_paths
    assert f"sync/{app_module.SYNC_WORKBOOK_FILENAME}" not in bucket.download_paths


def test_sync_tenant_scoped_local_and_storage_workbooks_remain_available(app_module, monkeypatch, tmp_path):
    class ScopedBucket:
        def __init__(self, objects):
            self.objects = objects

        def download(self, path):
            return self.objects[path]

    monkeypatch.setattr(app_module, "SYNC_STORAGE_DIR", str(tmp_path))
    tenant_one_request = make_admin_request()
    tenant_two_request = make_admin_request(TENANT_TWO_ID)
    tenant_one_paths = app_module.ensure_sync_storage(tenant_one_request)
    tenant_two_paths = app_module.ensure_sync_storage(tenant_two_request)

    with open(tenant_one_paths["workbook"], "wb") as file:
        file.write(b"tenant-one-local")
    assert app_module.ensure_sync_workbook_template(tenant_one_request) == tenant_one_paths["workbook"]
    with open(tenant_one_paths["workbook"], "rb") as file:
        assert file.read() == b"tenant-one-local"

    bucket = ScopedBucket({tenant_two_paths["storage_workbook"]: b"tenant-two-storage"})
    monkeypatch.setattr(app_module, "get_sync_storage_bucket", lambda: bucket)
    assert app_module.ensure_sync_workbook_template(tenant_two_request) == tenant_two_paths["workbook"]
    with open(tenant_two_paths["workbook"], "rb") as file:
        assert file.read() == b"tenant-two-storage"


def test_sync_state_owner_mismatch_is_rejected_before_apply(app_module, monkeypatch):
    fake_supabase = RecordingSupabase(
        {("tenants", "select"): [{"tenant_id": TENANT_TWO_ID, "status": "active"}]}
    )
    monkeypatch.setattr(app_module, "supabase", fake_supabase)

    with pytest.raises(app_module.TenantContextError, match="state belongs to a different tenant"):
        app_module.validate_sync_state_ownership(
            {
                "tenant_id": app_module.DEFAULT_TENANT_ID,
                "preview": {"tenant_id": app_module.DEFAULT_TENANT_ID},
            },
            make_admin_request(TENANT_TWO_ID),
        )

    assert not any(operation["action"] in {"insert", "update", "delete"} for operation in fake_supabase.operations)


def test_payment_create_includes_tenant_id(app_module, monkeypatch):
    fake_supabase = RecordingSupabase()
    monkeypatch.setattr(app_module, "supabase", fake_supabase)
    monkeypatch.setattr(
        app_module,
        "get_asset_by_id",
        lambda asset_id, request=None: {
            "asset_id": asset_id,
            "asset_tag_number": "HELP-UKR-0753",
            "currency": "EUR",
            "tenant_id": app_module.DEFAULT_TENANT_ID,
        },
    )
    monkeypatch.setattr(app_module, "asset_payment_eur_equivalent_supported", lambda: True)

    response = app_module.admin_asset_payment_create(
        make_admin_request(),
        101,
        payment_date="13.08.2026",
        payment_amount="20,31",
        currency="EUR",
        eur_equivalent_amount="20,31",
        payment_status="paid",
        notes="Created in regression",
    )

    assert response.status_code == 303
    payment_insert = [operation for operation in fake_supabase.operations if operation["action"] == "insert"][0]
    assert payment_insert["table"] == "asset_payments"
    assert payment_insert["payload"]["tenant_id"] == app_module.DEFAULT_TENANT_ID
    assert payment_insert["payload"]["asset_id"] == 101


def test_project_funding_create_includes_tenant_id(app_module, monkeypatch):
    fake_supabase = RecordingSupabase(
        {
            ("projects", "select"): [{"project_id": 6, "project_number": "GLO-001"}],
            ("donors", "select"): [{"donor_id": 2, "donor_name": "BMZ"}],
        }
    )
    monkeypatch.setattr(app_module, "supabase", fake_supabase)
    monkeypatch.setattr(
        app_module,
        "get_asset_by_id",
        lambda asset_id, request=None: {
            "asset_id": asset_id,
            "asset_tag_number": "HELP-UKR-0753",
            "tenant_id": app_module.DEFAULT_TENANT_ID,
        },
    )
    monkeypatch.setattr(app_module, "get_asset_project_total_percent", lambda *args, **kwargs: 0)
    monkeypatch.setattr(app_module, "asset_project_purchase_origin_supported", lambda: True)

    response = app_module.admin_asset_project_create(
        make_admin_request(),
        101,
        project_id="6",
        donor_id="2",
        allocation_percent="100",
        allocation_amount="",
        currency="EUR",
        funding_note="Regression funding",
        is_primary="on",
        is_current="on",
        is_purchase_origin="on",
    )

    assert response.status_code == 303
    project_insert = [operation for operation in fake_supabase.operations if operation["action"] == "insert"][0]
    assert project_insert["table"] == "asset_projects"
    assert project_insert["payload"]["tenant_id"] == app_module.DEFAULT_TENANT_ID
    assert project_insert["payload"]["asset_id"] == 101
    assert project_insert["payload"]["project_id"] == 6


def test_assignment_rejects_cross_tenant_person_before_insert(app_module, monkeypatch):
    fake_supabase = RecordingSupabase(
        {
            ("persons", "select"): [],
            ("locations", "select"): [{"location_id": 4}],
        }
    )
    monkeypatch.setattr(app_module, "supabase", fake_supabase)

    result = None
    try:
        app_module.apply_asset_assignment_change(
            asset={
                "asset_id": 101,
                "asset_tag_number": "HELP-UKR-0753",
                "tenant_id": app_module.DEFAULT_TENANT_ID,
                "current_assignment": None,
            },
            parsed_person_id=12,
            parsed_location_id=4,
            assignment_department="PROGRAM",
            assignment_date="2026-08-13",
            status="functional",
            notes="",
            handover_condition="New",
            assignment_scope="personal",
            custody_note="",
            request=make_admin_request(),
        )
    except app_module.TenantContextError as error:
        result = str(error)

    assert result == "persons.person_id does not belong to the current tenant."
    assert not any(operation["table"] == "asset_assignments" and operation["action"] == "insert" for operation in fake_supabase.operations)


def test_assignment_rejects_cross_tenant_location_before_insert(app_module, monkeypatch):
    fake_supabase = RecordingSupabase(
        {
            ("persons", "select"): [{"person_id": 12}],
            ("locations", "select"): [],
        }
    )
    monkeypatch.setattr(app_module, "supabase", fake_supabase)

    result = None
    try:
        app_module.apply_asset_assignment_change(
            asset={
                "asset_id": 101,
                "asset_tag_number": "HELP-UKR-0753",
                "tenant_id": app_module.DEFAULT_TENANT_ID,
                "current_assignment": None,
            },
            parsed_person_id=12,
            parsed_location_id=4,
            assignment_department="PROGRAM",
            assignment_date="2026-08-13",
            status="functional",
            notes="",
            handover_condition="New",
            assignment_scope="personal",
            custody_note="",
            request=make_admin_request(),
        )
    except app_module.TenantContextError as error:
        result = str(error)

    assert result == "locations.location_id does not belong to the current tenant."
    assert not any(operation["table"] == "asset_assignments" and operation["action"] == "insert" for operation in fake_supabase.operations)


def test_transfer_rejects_cross_tenant_person_before_insert(app_module, monkeypatch):
    fake_supabase = RecordingSupabase({("persons", "select"): []})
    monkeypatch.setattr(app_module, "supabase", fake_supabase)
    monkeypatch.setattr(app_module, "get_asset_projects", lambda asset_id, request=None: [])

    result = None
    try:
        app_module.create_asset_transfer_from_assignment_change(
            asset={
                "asset_id": 101,
                "asset_tag_number": "HELP-UKR-0753",
                "tenant_id": app_module.DEFAULT_TENANT_ID,
            },
            from_assignment={"person_id": 12, "responsible_person": "Old Holder"},
            to_person_id=13,
            transfer_date="2026-08-13",
            transfer_reason="Assignment changed in web app",
        )
    except app_module.TenantContextError as error:
        result = str(error)

    assert result == "persons.person_id does not belong to the current tenant."
    assert not any(operation["table"] == "asset_transfers" and operation["action"] == "insert" for operation in fake_supabase.operations)


def test_sync_transfer_rejects_cross_tenant_person_before_insert(app_module, monkeypatch):
    fake_supabase = RecordingSupabase(
        {
            ("assets", "select"): [{"asset_id": 101}],
            ("persons", "select"): [],
        }
    )
    monkeypatch.setattr(app_module, "supabase", fake_supabase)

    result = None
    try:
        app_module.apply_sync_transfer(
            {
                "asset_id": 101,
                "asset_tag_number": "HELP-UKR-0753",
                "from_person_id": 12,
                "to_person_id": None,
                "transfer_date": "2026-08-13",
            },
            {"transfer_signatures": set()},
            make_admin_request(),
        )
    except app_module.TenantContextError as error:
        result = str(error)

    assert result == "persons.person_id does not belong to the current tenant."
    assert not any(operation["table"] == "asset_transfers" and operation["action"] == "insert" for operation in fake_supabase.operations)


def test_tenant_payload_overrides_client_supplied_tenant_id(app_module):
    payload = app_module.add_tenant_id({"asset_id": 101, "tenant_id": "client-supplied"})

    assert payload["tenant_id"] == app_module.DEFAULT_TENANT_ID


def test_assignment_update_rejects_parent_tenant_mismatch(app_module):
    result = None
    try:
        app_module.apply_asset_assignment_change(
            asset={
                "asset_id": 101,
                "asset_tag_number": "HELP-UKR-0753",
                "tenant_id": "00000000-0000-4000-8000-999999999999",
                "current_assignment": None,
            },
            parsed_person_id=None,
            parsed_location_id=4,
            assignment_department="PROGRAM",
            assignment_date="2026-08-13",
            status="functional",
            notes="",
            handover_condition="New",
            assignment_scope="warehouse",
            custody_note="",
            request=make_admin_request(),
        )
    except app_module.TenantContextError as error:
        result = str(error)

    assert result == "Asset belongs to a different tenant."


def test_missing_tenant_id_on_tenant_owned_record_fails_closed(app_module):
    result = None
    try:
        app_module.assert_record_tenant({"asset_id": 101}, label="Asset")
    except app_module.TenantContextError as error:
        result = str(error)

    assert result == "Asset is missing tenant_id."


def test_audit_insert_and_legacy_fallback_preserve_tenant_id(app_module, monkeypatch):
    fake_supabase = RecordingSupabase()
    monkeypatch.setattr(app_module, "supabase", fake_supabase)

    assert app_module.audit_log_event(entity_type="Asset", action="created", entity_id=101)
    assert fake_supabase.operations[0]["payload"]["tenant_id"] == app_module.DEFAULT_TENANT_ID

    class FakeApiError(Exception):
        def __init__(self):
            self.message = "Column event_date does not exist"
            self.details = ""

    class FallbackQuery(RecordingQuery):
        def execute(self):
            operation = {
                "table": self.table_name,
                "action": self.action,
                "payload": dict(self.payload),
                "filters": self.filters,
            }
            self.database.operations.append(operation)
            if not self.database.failed_once:
                self.database.failed_once = True
                raise FakeApiError()
            return FakeResponse([])

    class FallbackSupabase(RecordingSupabase):
        def __init__(self):
            super().__init__()
            self.failed_once = False

        def table(self, table_name):
            return FallbackQuery(self, table_name)

    fallback_supabase = FallbackSupabase()
    monkeypatch.setattr(app_module, "APIError", FakeApiError)
    monkeypatch.setattr(app_module, "supabase", fallback_supabase)

    assert app_module.audit_log_event(entity_type="Asset", action="created", entity_id=101)
    assert fallback_supabase.operations[0]["payload"]["tenant_id"] == app_module.DEFAULT_TENANT_ID
    assert "event_date" in fallback_supabase.operations[0]["payload"]
    assert fallback_supabase.operations[1]["payload"]["tenant_id"] == app_module.DEFAULT_TENANT_ID
    assert "event_date" not in fallback_supabase.operations[1]["payload"]


def test_audit_whitespace_and_line_endings_do_not_create_noise(app_module, monkeypatch):
    audit_calls = []
    monkeypatch.setattr(app_module, "audit_log_event", lambda **kwargs: audit_calls.append(kwargs) or True)

    logged = app_module.audit_log_field_changes(
        entity_type="Asset",
        entity_id=101,
        entity_label="HELP-UKR-0753",
        old_record={"remarks": "First line\r\nSecond line\n"},
        new_record={"remarks": " First line\nSecond line "},
        fields=["remarks"],
        request=make_admin_request(),
    )

    assert logged == 0
    assert audit_calls == []


def test_recent_audit_orders_valid_event_date_above_older_null_event_date(app_module, monkeypatch):
    rows = [
        {
            "audit_id": 655,
            "tenant_id": app_module.DEFAULT_TENANT_ID,
            "event_date": None,
            "created_at": "2026-08-23T12:00:00+00:00",
            "entity_label": "OLDER-NULL",
        },
        {
            "audit_id": 661,
            "tenant_id": app_module.DEFAULT_TENANT_ID,
            "event_date": "2026-08-24T08:00:00+00:00",
            "created_at": "2026-08-24T08:00:10+00:00",
            "entity_label": "NEWER-EVENT",
        },
    ]
    fake_supabase = RecordingSupabase({("audit_log", "select"): rows})
    monkeypatch.setattr(app_module, "supabase", fake_supabase)

    recent = app_module.list_recent_audit_events(5)

    assert [row["entity_label"] for row in recent] == ["NEWER-EVENT", "OLDER-NULL"]
    assert {operation["action"] for operation in fake_supabase.operations} == {"select"}


def test_recent_audit_null_event_date_uses_created_at_as_effective_time(app_module, monkeypatch):
    rows = [
        {
            "audit_id": 662,
            "tenant_id": app_module.DEFAULT_TENANT_ID,
            "event_date": "2026-08-23T20:00:00+00:00",
            "created_at": "2026-08-23T20:00:01+00:00",
            "entity_label": "VALID-EVENT",
        },
        {
            "audit_id": 663,
            "tenant_id": app_module.DEFAULT_TENANT_ID,
            "event_date": None,
            "created_at": "2026-08-24T09:30:00+00:00",
            "entity_label": "NULL-USES-CREATED",
        },
    ]
    fake_supabase = RecordingSupabase({("audit_log", "select"): rows})
    monkeypatch.setattr(app_module, "supabase", fake_supabase)

    recent = app_module.list_recent_audit_events(5)

    assert [row["entity_label"] for row in recent] == ["NULL-USES-CREATED", "VALID-EVENT"]


def test_recent_audit_orders_newest_first_with_deterministic_tie_break(app_module, monkeypatch):
    rows = [
        {
            "audit_id": 10,
            "tenant_id": app_module.DEFAULT_TENANT_ID,
            "event_date": None,
            "created_at": "2026-08-24T10:00:00+00:00",
            "entity_label": "TIE-LOWER-ID",
        },
        {
            "audit_id": 9,
            "tenant_id": app_module.DEFAULT_TENANT_ID,
            "event_date": "2026-08-25T09:00:00+00:00",
            "created_at": "2026-08-24T09:00:00+00:00",
            "entity_label": "NEWEST-EVENT",
        },
        {
            "audit_id": 11,
            "tenant_id": app_module.DEFAULT_TENANT_ID,
            "event_date": None,
            "created_at": "2026-08-24T10:00:00+00:00",
            "entity_label": "TIE-HIGHER-ID",
        },
    ]
    fake_supabase = RecordingSupabase({("audit_log", "select"): rows})
    monkeypatch.setattr(app_module, "supabase", fake_supabase)

    recent = app_module.list_recent_audit_events(5)

    assert [row["entity_label"] for row in recent] == ["NEWEST-EVENT", "TIE-HIGHER-ID", "TIE-LOWER-ID"]
    assert [row["tenant_id"] for row in recent] == [app_module.DEFAULT_TENANT_ID] * 3


def test_recent_audit_fetches_null_event_date_batch_exactly(app_module, monkeypatch):
    class FilteredAuditQuery(RecordingQuery):
        def __init__(self, database, table_name):
            super().__init__(database, table_name)
            self.limit_value = None

        def limit(self, value):
            self.limit_value = value
            return self

        def execute(self):
            rows = list(self.database.rows)
            if ("not_is", "event_date", "null") in self.filters:
                rows = [row for row in rows if row.get("event_date") is not None]
            if ("is", "event_date", "null") in self.filters:
                rows = [row for row in rows if row.get("event_date") is None]
            for field_name, kwargs in reversed(self.orders):
                rows = sorted(
                    rows,
                    key=lambda row: int(row.get(field_name) or 0) if field_name == "audit_id" else str(row.get(field_name) or ""),
                    reverse=bool(kwargs.get("desc")),
                )
            if self.limit_value is not None:
                rows = rows[: self.limit_value]
            self.database.operations.append(
                {
                    "table": self.table_name,
                    "action": self.action,
                    "payload": self.payload,
                    "filters": self.filters,
                    "orders": self.orders,
                }
            )
            return FakeResponse(rows)

    class FilteredAuditSupabase:
        def __init__(self, rows):
            self.rows = rows
            self.operations = []

        def table(self, table_name):
            return FilteredAuditQuery(self, table_name)

    old_valid_event_rows = [
        {
            "audit_id": audit_id,
            "tenant_id": app_module.DEFAULT_TENANT_ID,
            "event_date": f"2020-01-{audit_id:02d}T00:00:00+00:00",
            "created_at": f"2026-08-24T12:{audit_id:02d}:00+00:00",
            "entity_label": f"OLD-EVENT-{audit_id}",
        }
        for audit_id in range(1, 8)
    ]
    rows = old_valid_event_rows + [
        {
            "audit_id": 100,
            "tenant_id": app_module.DEFAULT_TENANT_ID,
            "event_date": None,
            "created_at": "2026-08-24T11:59:00+00:00",
            "entity_label": "NULL-EVENT-BELONGS-IN-TOP",
        }
    ]
    fake_supabase = FilteredAuditSupabase(rows)
    monkeypatch.setattr(app_module, "supabase", fake_supabase)

    recent = app_module.list_recent_audit_events(5)

    assert "NULL-EVENT-BELONGS-IN-TOP" in [row["entity_label"] for row in recent]
    assert recent[0]["entity_label"] == "NULL-EVENT-BELONGS-IN-TOP"
    assert fake_supabase.operations[0]["filters"] == [
        ("eq", "tenant_id", app_module.DEFAULT_TENANT_ID),
        ("not_is", "event_date", "null"),
    ]
    assert fake_supabase.operations[1]["filters"] == [
        ("eq", "tenant_id", app_module.DEFAULT_TENANT_ID),
        ("is", "event_date", "null"),
    ]


def test_recent_audit_candidate_queries_break_limit_ties_by_audit_id(app_module, monkeypatch):
    class FilteredAuditQuery(RecordingQuery):
        def __init__(self, database, table_name):
            super().__init__(database, table_name)
            self.limit_value = None

        def limit(self, value):
            self.limit_value = value
            return self

        def execute(self):
            rows = list(self.database.rows)
            if ("not_is", "event_date", "null") in self.filters:
                rows = [row for row in rows if row.get("event_date") is not None]
            if ("is", "event_date", "null") in self.filters:
                rows = [row for row in rows if row.get("event_date") is None]
            for field_name, kwargs in reversed(self.orders):
                rows = sorted(
                    rows,
                    key=lambda row: int(row.get(field_name) or 0) if field_name == "audit_id" else str(row.get(field_name) or ""),
                    reverse=bool(kwargs.get("desc")),
                )
            if self.limit_value is not None:
                rows = rows[: self.limit_value]
            self.database.operations.append(
                {
                    "table": self.table_name,
                    "action": self.action,
                    "payload": self.payload,
                    "filters": self.filters,
                    "orders": self.orders,
                }
            )
            return FakeResponse(rows)

    class FilteredAuditSupabase:
        def __init__(self, rows):
            self.rows = rows
            self.operations = []

        def table(self, table_name):
            return FilteredAuditQuery(self, table_name)

    rows = [
        {
            "audit_id": audit_id,
            "tenant_id": app_module.DEFAULT_TENANT_ID,
            "event_date": None,
            "created_at": "2026-08-24T10:00:00+00:00",
            "entity_label": f"NULL-TIE-{audit_id}",
        }
        for audit_id in range(1, 8)
    ]
    fake_supabase = FilteredAuditSupabase(rows)
    monkeypatch.setattr(app_module, "supabase", fake_supabase)

    recent = app_module.list_recent_audit_events(5)

    assert [row["audit_id"] for row in recent] == [7, 6, 5, 4, 3]
    assert fake_supabase.operations[0]["orders"] == [
        ("event_date", {"desc": True, "nullsfirst": False}),
        ("created_at", {"desc": True}),
        ("audit_id", {"desc": True}),
    ]
    assert fake_supabase.operations[1]["orders"] == [
        ("created_at", {"desc": True}),
        ("audit_id", {"desc": True}),
    ]


def test_full_audit_log_orders_by_effective_timestamp_and_audit_id(app_module, monkeypatch):
    rows = [
        {
            "audit_id": 655,
            "event_date": None,
            "created_at": "2026-08-23T12:00:00+00:00",
            "entity_label": "OLDER-NULL",
        },
        {
            "audit_id": 661,
            "event_date": "2026-08-24T08:00:00+00:00",
            "created_at": "2026-08-24T08:00:10+00:00",
            "entity_label": "NEWER-EVENT",
        },
        {
            "audit_id": 663,
            "event_date": None,
            "created_at": "2026-08-24T09:30:00+00:00",
            "entity_label": "NULL-USES-CREATED",
        },
        {
            "audit_id": 10,
            "event_date": None,
            "created_at": "2026-08-24T09:30:00+00:00",
            "entity_label": "NULL-TIE-LOWER-ID",
        },
    ]
    monkeypatch.setattr(app_module, "fetch_audit_log_candidates", lambda *args, **kwargs: rows)

    result = app_module.list_audit_log_events(page_size=100)

    assert [row["entity_label"] for row in result["rows"]] == [
        "NULL-USES-CREATED",
        "NULL-TIE-LOWER-ID",
        "NEWER-EVENT",
        "OLDER-NULL",
    ]
    assert result["total_matches"] == 4


def test_full_audit_log_filters_query_after_effective_sort(app_module, monkeypatch):
    rows = [
        {
            "audit_id": 1,
            "event_date": "2026-08-24T08:00:00+00:00",
            "created_at": "2026-08-24T08:00:00+00:00",
            "entity_label": "HELP-UKR-0001",
            "summary": "Ignored change",
        },
        {
            "audit_id": 2,
            "event_date": None,
            "created_at": "2026-08-25T08:00:00+00:00",
            "entity_label": "HELP-UKR-0002",
            "summary": "Target remarks",
        },
    ]
    monkeypatch.setattr(app_module, "fetch_audit_log_candidates", lambda *args, **kwargs: rows)

    result = app_module.list_audit_log_events(q="target", page_size=100)

    assert [row["entity_label"] for row in result["rows"]] == ["HELP-UKR-0002"]
    assert result["total_matches"] == 1


def test_full_audit_log_paginates_effective_sorted_rows(app_module, monkeypatch):
    rows = [
        {
            "audit_id": audit_id,
            "event_date": None,
            "created_at": "2026-08-24T10:00:00+00:00",
            "entity_label": f"ROW-{audit_id}",
        }
        for audit_id in range(1, 56)
    ]
    monkeypatch.setattr(app_module, "fetch_audit_log_candidates", lambda *args, **kwargs: rows)

    result = app_module.list_audit_log_events(page=2, page_size=50)

    assert [row["entity_label"] for row in result["rows"]] == ["ROW-5", "ROW-4", "ROW-3", "ROW-2", "ROW-1"]
    assert result["page"] == 2
    assert result["page_count"] == 2
    assert result["total_matches"] == 55


def test_full_audit_log_preserves_entity_type_source_filters(app_module, monkeypatch):
    calls = []

    def fake_fetch(entity_type="", source="", *, use_event_date=True, request=None):
        calls.append({"entity_type": entity_type, "source": source, "use_event_date": use_event_date})
        return []

    monkeypatch.setattr(app_module, "fetch_audit_log_candidates", fake_fetch)

    app_module.list_audit_log_events(entity_type="Asset", source="Admin")

    assert calls == [{"entity_type": "Asset", "source": "Admin", "use_event_date": True}]


def test_full_audit_log_legacy_event_date_fallback_still_sorts_created_at(app_module, monkeypatch):
    class FakeApiError(Exception):
        def __init__(self):
            self.message = "Column event_date does not exist"
            self.details = ""

    calls = []

    def fake_fetch(entity_type="", source="", *, use_event_date=True, request=None):
        calls.append(use_event_date)
        if use_event_date:
            raise FakeApiError()
        return [
            {
                "audit_id": 1,
                "event_date": None,
                "created_at": "2026-08-24T08:00:00+00:00",
                "entity_label": "OLDER",
            },
            {
                "audit_id": 2,
                "event_date": None,
                "created_at": "2026-08-25T08:00:00+00:00",
                "entity_label": "NEWER",
            },
        ]

    monkeypatch.setattr(app_module, "APIError", FakeApiError)
    monkeypatch.setattr(app_module, "fetch_audit_log_candidates", fake_fetch)

    result = app_module.list_audit_log_events(page_size=100)

    assert calls == [True, False]
    assert [row["entity_label"] for row in result["rows"]] == ["NEWER", "OLDER"]
