from types import SimpleNamespace

import pytest


TENANT_ONE = "00000000-0000-4000-8000-000000000001"
TENANT_TWO = "00000000-0000-4000-8000-000000000002"


class FakeResponse:
    def __init__(self, data=None):
        self.data = data or []


class MemoryNotFilter:
    def __init__(self, query):
        self.query = query

    def is_(self, field_name, value):
        self.query.filters.append(("not_is", field_name, value))
        return self.query


class MemoryQuery:
    def __init__(self, database, table_name):
        self.database = database
        self.table_name = table_name
        self.filters = []
        self.orders = []
        self.limit_value = None
        self.range_value = None

    def select(self, *args, **kwargs):
        return self

    def eq(self, field_name, value):
        self.filters.append(("eq", field_name, value))
        return self

    def in_(self, field_name, values):
        self.filters.append(("in", field_name, values))
        return self

    def ilike(self, field_name, value):
        self.filters.append(("ilike", field_name, value))
        return self

    def is_(self, field_name, value):
        self.filters.append(("is", field_name, value))
        return self

    @property
    def not_(self):
        return MemoryNotFilter(self)

    def order(self, field_name, **kwargs):
        self.orders.append((field_name, kwargs))
        return self

    def limit(self, value):
        self.limit_value = value
        return self

    def range(self, start, end):
        self.range_value = (start, end)
        return self

    def execute(self):
        rows = [dict(row) for row in self.database.rows.get(self.table_name, [])]
        for operator, field_name, value in self.filters:
            if operator == "eq":
                rows = [row for row in rows if row.get(field_name) == value]
            elif operator == "in":
                rows = [row for row in rows if row.get(field_name) in value]
            elif operator == "ilike":
                needle = str(value).replace("%", "").casefold()
                rows = [row for row in rows if needle in str(row.get(field_name) or "").casefold()]
            elif operator == "is" and value == "null":
                rows = [row for row in rows if row.get(field_name) is None]
            elif operator == "not_is" and value == "null":
                rows = [row for row in rows if row.get(field_name) is not None]

        for field_name, kwargs in reversed(self.orders):
            rows.sort(
                key=lambda row: (row.get(field_name) is not None, str(row.get(field_name) or "")),
                reverse=bool(kwargs.get("desc")),
            )
        if self.range_value is not None:
            start, end = self.range_value
            rows = rows[start : end + 1]
        if self.limit_value is not None:
            rows = rows[: self.limit_value]

        self.database.operations.append(
            {"table": self.table_name, "filters": list(self.filters)}
        )
        return FakeResponse(rows)


class MemorySupabase:
    def __init__(self, rows):
        self.rows = rows
        self.operations = []

    def table(self, table_name):
        return MemoryQuery(self, table_name)


def authenticated_request(session_tenant_id=TENANT_ONE, person_id=None, **client_values):
    session = {
        "admin_authenticated": True,
        "admin_role": "admin",
        "admin_username": "admin",
        "tenant_id": session_tenant_id,
    }
    if person_id is not None:
        session["account_person_id"] = person_id
    return SimpleNamespace(
        session=session,
        method="GET",
        url=SimpleNamespace(path="/admin", query=""),
        query_params=client_values,
    )


@pytest.fixture
def mixed_tenant_supabase(app_module, monkeypatch):
    rows = {
        "assets": [
            {
                "asset_id": 1,
                "asset_tag_number": "TENANT-ONE-ASSET",
                "tenant_id": TENANT_ONE,
                "current_status": "functional",
            },
            {
                "asset_id": 2,
                "asset_tag_number": "TENANT-TWO-ASSET",
                "tenant_id": TENANT_TWO,
                "current_status": "functional",
            },
        ],
        "persons": [
            {"person_id": 101, "name_eng": "Tenant One Person", "tenant_id": TENANT_ONE},
            {"person_id": 202, "name_eng": "Tenant Two Person", "tenant_id": TENANT_TWO},
        ],
        "locations": [
            {"location_id": 301, "name": "Office One", "city": "Kyiv", "tenant_id": TENANT_ONE},
            {"location_id": 302, "name": "Office Two", "city": "Lviv", "tenant_id": TENANT_TWO},
        ],
        "asset_assignments": [
            {
                "assignment_id": 11,
                "asset_id": 1,
                "person_id": 101,
                "location_id": 301,
                "assignment_date": "2026-01-01",
                "return_date": None,
                "tenant_id": TENANT_ONE,
            },
            {
                "assignment_id": 22,
                "asset_id": 2,
                "person_id": 202,
                "location_id": 302,
                "assignment_date": "2026-02-01",
                "return_date": None,
                "tenant_id": TENANT_TWO,
            },
        ],
        "projects": [
            {"project_id": 401, "project_number": "T1-PROJECT", "tenant_id": TENANT_ONE},
            {"project_id": 402, "project_number": "T2-PROJECT", "tenant_id": TENANT_TWO},
        ],
        "donors": [
            {"donor_id": 501, "donor_name": "T1-DONOR", "tenant_id": TENANT_ONE},
            {"donor_id": 502, "donor_name": "T2-DONOR", "tenant_id": TENANT_TWO},
        ],
        "asset_projects": [
            {"asset_project_id": 41, "asset_id": 1, "project_id": 401, "donor_id": 501, "tenant_id": TENANT_ONE},
            {"asset_project_id": 42, "asset_id": 2, "project_id": 402, "donor_id": 502, "tenant_id": TENANT_TWO},
        ],
        "asset_payments": [
            {"payment_id": 51, "asset_id": 1, "payment_number": 1, "tenant_id": TENANT_ONE},
            {"payment_id": 52, "asset_id": 2, "payment_number": 1, "tenant_id": TENANT_TWO},
        ],
        "asset_transfers": [
            {
                "transfer_id": 61,
                "asset_id": 1,
                "to_person_id": 101,
                "transfer_date": "2026-03-01",
                "tenant_id": TENANT_ONE,
            },
            {
                "transfer_id": 62,
                "asset_id": 2,
                "to_person_id": 202,
                "transfer_date": "2026-04-01",
                "tenant_id": TENANT_TWO,
            },
        ],
        "asset_transfer_projects": [
            {"transfer_project_id": 71, "transfer_id": 61, "project_id": 401, "direction": "to", "tenant_id": TENANT_ONE},
            {"transfer_project_id": 72, "transfer_id": 62, "project_id": 402, "direction": "to", "tenant_id": TENANT_TWO},
        ],
        "asset_classifications": [
            {"classification_id": 81, "classification_name": "T1 CLASS", "tenant_id": TENANT_ONE},
            {"classification_id": 82, "classification_name": "T2 CLASS", "tenant_id": TENANT_TWO},
        ],
        "asset_sub_classifications": [
            {"sub_classification_id": 91, "sub_classification_name": "T1 SUB", "tenant_id": TENANT_ONE},
            {"sub_classification_id": 92, "sub_classification_name": "T2 SUB", "tenant_id": TENANT_TWO},
        ],
        "organization_branding": [
            {"tenant_key": "default", "company_name": "Tenant One", "tenant_id": TENANT_ONE},
            {"tenant_key": "default", "company_name": "Tenant Two", "tenant_id": TENANT_TWO},
        ],
        "audit_log": [
            {
                "audit_id": 1001,
                "entity_type": "Asset",
                "entity_label": "TENANT-ONE-ASSET",
                "source": "Admin",
                "event_date": "2026-08-25T10:00:00+00:00",
                "created_at": "2026-08-25T10:00:00+00:00",
                "tenant_id": TENANT_ONE,
            },
            {
                "audit_id": 1002,
                "entity_type": "Asset",
                "entity_label": "TENANT-TWO-ASSET",
                "source": "Admin",
                "event_date": "2026-08-26T10:00:00+00:00",
                "created_at": "2026-08-26T10:00:00+00:00",
                "tenant_id": TENANT_TWO,
            },
        ],
    }
    fake = MemorySupabase(rows)
    monkeypatch.setattr(app_module, "supabase", fake)
    return fake


def test_asset_lists_are_isolated_in_both_directions(app_module, mixed_tenant_supabase):
    tenant_one_assets = app_module.list_assets(request=authenticated_request(TENANT_ONE))
    tenant_two_assets = app_module.list_assets(request=authenticated_request(TENANT_TWO))

    assert [row["asset_tag_number"] for row in tenant_one_assets] == ["TENANT-ONE-ASSET"]
    assert [row["asset_tag_number"] for row in tenant_two_assets] == ["TENANT-TWO-ASSET"]
    assert tenant_one_assets[0]["current_assignment"]["responsible_person"] == "Tenant One Person"
    assert tenant_two_assets[0]["current_assignment"]["responsible_person"] == "Tenant Two Person"


def test_authenticated_asset_detail_and_account_person_reject_cross_tenant_rows(app_module, mixed_tenant_supabase):
    tenant_one_request = authenticated_request(TENANT_ONE, person_id=202)

    assert app_module.get_asset_by_id(2, request=tenant_one_request) is None
    assert app_module.get_account_person(tenant_one_request) is None
    assert "account_person_id" not in tenant_one_request.session
    assert tenant_one_request.session["tenant_id"] == TENANT_ONE


def test_assignment_transfer_and_relationship_history_are_tenant_scoped(app_module, mixed_tenant_supabase):
    request = authenticated_request(TENANT_ONE)

    assignments = app_module.get_assignment_history(1, request=request)
    transfers = app_module.get_asset_transfer_history(1, request=request)
    projects = app_module.get_asset_projects(1, request=request)
    payments = app_module.get_asset_payments(1, request=request)

    assert [row["assignment_id"] for row in assignments] == [11]
    assert [row["transfer_id"] for row in transfers] == [61]
    assert [row["project_number"] for row in projects] == ["T1-PROJECT"]
    assert [row["payment_id"] for row in payments] == [51]


def test_reference_and_branding_reads_are_tenant_scoped(app_module, mixed_tenant_supabase):
    request = authenticated_request(TENANT_TWO)

    assert [row["project_number"] for row in app_module.list_projects(request=request)] == ["T2-PROJECT"]
    assert [row["donor_name"] for row in app_module.list_donors(request=request)] == ["T2-DONOR"]
    assert [row["name"] for row in app_module.list_locations(request=request)] == ["Office Two"]
    assert app_module.list_lookup_values(
        "asset_classifications",
        "classification_name",
        request=request,
    ) == ["T2 CLASS"]
    assert app_module.list_lookup_values(
        "asset_sub_classifications",
        "sub_classification_name",
        request=request,
    ) == ["T2 SUB"]
    assert app_module.load_branding_settings_from_supabase("default", request=request)["company_name"] == "Tenant Two"


def test_non_default_tenant_branding_does_not_fall_back_to_tenant_one_file(
    app_module,
    mixed_tenant_supabase,
    monkeypatch,
):
    mixed_tenant_supabase.rows["organization_branding"] = [
        row
        for row in mixed_tenant_supabase.rows["organization_branding"]
        if row["tenant_id"] == TENANT_ONE
    ]
    monkeypatch.setattr(
        app_module,
        "load_branding_settings_from_file",
        lambda tenant_key: pytest.fail("Tenant #2 must not read the Tenant #1 branding file"),
    )

    settings, storage = app_module.load_branding_settings(
        "default",
        request=authenticated_request(TENANT_TWO),
    )

    assert settings == app_module.get_default_branding_settings()
    assert storage == "default"


def test_audit_log_and_recent_changes_are_tenant_scoped(app_module, mixed_tenant_supabase):
    request = authenticated_request(TENANT_ONE)

    recent = app_module.list_recent_audit_events(5, request=request)
    full_log = app_module.list_audit_log_events(page_size=100, request=request)

    assert [row["entity_label"] for row in recent] == ["TENANT-ONE-ASSET"]
    assert [row["entity_label"] for row in full_log["rows"]] == ["TENANT-ONE-ASSET"]
    assert full_log["total_matches"] == 1


def test_dashboard_and_reports_forward_the_trusted_request(app_module, monkeypatch):
    request = authenticated_request(TENANT_TWO)
    calls = []

    def fake_list_assets(limit=None, batch_size=500, request=None):
        calls.append(("assets", request))
        return []

    def fake_recent(limit=5, request=None):
        calls.append(("recent", request))
        return []

    monkeypatch.setattr(app_module, "list_assets", fake_list_assets)
    monkeypatch.setattr(app_module, "list_recent_audit_events", fake_recent)
    monkeypatch.setattr(
        app_module.templates,
        "TemplateResponse",
        lambda **kwargs: kwargs["context"],
    )

    app_module.admin_dashboard(request)
    app_module.admin_reports(request)

    assert calls == [("assets", request), ("recent", request), ("assets", request)]


def test_excel_read_helpers_use_request_tenant(app_module, mixed_tenant_supabase):
    request = authenticated_request(TENANT_TWO)

    assert [row["asset_tag_number"] for row in app_module.list_asset_records(request=request)] == [
        "TENANT-TWO-ASSET"
    ]
    assert [row["assignment_id"] for row in app_module.list_current_assignment_records(request=request)] == [22]
    assert [row["asset_project_id"] for row in app_module.list_asset_project_records(request=request)] == [42]
    assert [row["payment_id"] for row in app_module.list_asset_payment_records(request=request)] == [52]
    assert [row["transfer_id"] for row in app_module.list_asset_transfer_records(request=request)] == [62]


def test_client_supplied_tenant_id_cannot_change_read_scope(app_module, mixed_tenant_supabase):
    request = authenticated_request(TENANT_ONE, tenant_id=TENANT_TWO)

    projects = app_module.list_projects(request=request)

    assert [row["project_number"] for row in projects] == ["T1-PROJECT"]


@pytest.mark.parametrize("tenant_id", [None, "not-a-uuid"])
def test_authenticated_reads_fail_closed_for_missing_or_malformed_tenant(app_module, mixed_tenant_supabase, tenant_id):
    request = authenticated_request(TENANT_ONE)
    if tenant_id is None:
        request.session.pop("tenant_id")
    else:
        request.session["tenant_id"] = tenant_id

    with pytest.raises(app_module.TenantContextError):
        app_module.list_assets(request=request)


@pytest.mark.parametrize(
    "reader",
    [
        lambda app, request: app.list_recent_audit_events(5, request=request),
        lambda app, request: app.list_audit_log_events(request=request),
        lambda app, request: app.list_audit_filter_values("source", request=request),
        lambda app, request: app.load_branding_settings("default", request=request),
        lambda app, request: app.get_asset_transfer_history(1, request=request),
        lambda app, request: app.list_lookup_values(
            "asset_classifications",
            "classification_name",
            request=request,
        ),
        lambda app, request: app.get_asset_tag_standards(request=request),
    ],
)
def test_read_fallbacks_do_not_swallow_missing_tenant_context(
    app_module,
    mixed_tenant_supabase,
    reader,
):
    request = authenticated_request(TENANT_ONE)
    request.session.pop("tenant_id")

    with pytest.raises(app_module.TenantContextError):
        reader(app_module, request)


def test_public_asset_lookup_keeps_legacy_tenant_one_behavior(app_module, mixed_tenant_supabase):
    asset = app_module.get_asset_by_tag("TENANT-ONE-ASSET")

    assert asset["tenant_id"] == TENANT_ONE
    assert asset["asset_tag_number"] == "TENANT-ONE-ASSET"
