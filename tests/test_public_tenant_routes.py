TENANT_ONE = "00000000-0000-4000-8000-000000000001"
TENANT_TWO = "00000000-0000-4000-8000-000000000002"
UNREGISTERED_TENANT = "00000000-0000-4000-8000-000000000003"


class FakeResponse:
    def __init__(self, data=None):
        self.data = data or []


class MemoryQuery:
    def __init__(self, database, table_name):
        self.database = database
        self.table_name = table_name
        self.filters = []
        self.limit_value = None

    def select(self, *args, **kwargs):
        return self

    def eq(self, field_name, value):
        self.filters.append(("eq", field_name, value))
        return self

    def is_(self, field_name, value):
        self.filters.append(("is", field_name, value))
        return self

    def order(self, *args, **kwargs):
        return self

    def limit(self, value):
        self.limit_value = value
        return self

    def execute(self):
        rows = [dict(row) for row in self.database.rows.get(self.table_name, [])]
        for operator, field_name, value in self.filters:
            if operator == "eq":
                rows = [row for row in rows if row.get(field_name) == value]
            elif operator == "is" and value == "null":
                rows = [row for row in rows if row.get(field_name) is None]
        if self.limit_value is not None:
            rows = rows[: self.limit_value]
        self.database.operations.append(
            {"table": self.table_name, "filters": list(self.filters)}
        )
        return FakeResponse(rows)


class MemorySupabase:
    def __init__(self):
        self.rows = {
            "tenants": [
                {"tenant_id": TENANT_ONE, "status": "active"},
                {"tenant_id": TENANT_TWO, "status": "active"},
            ],
            "assets": [
                {
                    "asset_id": 1,
                    "asset_tag_number": "TENANT-ONE-ASSET",
                    "item_description": "Tenant One Monitor",
                    "current_status": "functional",
                    "tenant_id": TENANT_ONE,
                },
                {
                    "asset_id": 2,
                    "asset_tag_number": "TENANT-TWO-ASSET",
                    "item_description": "Tenant Two Monitor",
                    "current_status": "functional",
                    "tenant_id": TENANT_TWO,
                },
                {
                    "asset_id": 3,
                    "asset_tag_number": "UNREGISTERED-ASSET",
                    "current_status": "functional",
                    "tenant_id": UNREGISTERED_TENANT,
                },
            ],
            "asset_assignments": [
                {
                    "assignment_id": 11,
                    "asset_id": 1,
                    "person_id": 101,
                    "assignment_date": "2026-01-01",
                    "return_date": None,
                    "tenant_id": TENANT_ONE,
                },
                {
                    "assignment_id": 22,
                    "asset_id": 2,
                    "person_id": 202,
                    "assignment_date": "2026-02-01",
                    "return_date": None,
                    "tenant_id": TENANT_TWO,
                },
            ],
            "persons": [
                {"person_id": 101, "name_eng": "Tenant One Holder", "tenant_id": TENANT_ONE},
                {"person_id": 202, "name_eng": "Tenant Two Holder", "tenant_id": TENANT_TWO},
            ],
            "locations": [],
        }
        self.operations = []

    def table(self, table_name):
        return MemoryQuery(self, table_name)


def install_public_tenant_data(app_module, monkeypatch):
    fake = MemorySupabase()
    monkeypatch.setattr(app_module, "supabase", fake)
    return fake


def test_canonical_tenant_routes_resolve_matching_assets(app_module, client, monkeypatch):
    fake = install_public_tenant_data(app_module, monkeypatch)

    tenant_one_response = client.get(f"/t/{TENANT_ONE}/asset/TENANT-ONE-ASSET")
    tenant_two_response = client.get(f"/t/{TENANT_TWO}/view/TENANT-TWO-ASSET")

    assert tenant_one_response.status_code == 200
    assert tenant_one_response.json()["asset_tag_number"] == "TENANT-ONE-ASSET"
    assert tenant_one_response.json()["current_assignment"]["responsible_person"] == "Tenant One Holder"
    assert tenant_two_response.status_code == 200
    assert "Tenant Two Monitor" in tenant_two_response.text
    assert "Tenant Two Holder" in tenant_two_response.text
    assert all(
        ("eq", "tenant_id", TENANT_ONE) in operation["filters"]
        or ("eq", "tenant_id", TENANT_TWO) in operation["filters"]
        or operation["table"] == "tenants"
        for operation in fake.operations
    )


def test_canonical_tenant_routes_reject_cross_tenant_tags(app_module, client, monkeypatch):
    install_public_tenant_data(app_module, monkeypatch)

    assert client.get(f"/t/{TENANT_TWO}/asset/TENANT-ONE-ASSET").status_code == 404
    assert client.get(f"/t/{TENANT_ONE}/asset/TENANT-TWO-ASSET").status_code == 404


def test_unknown_or_unregistered_tenant_identifier_fails_closed(app_module, client, monkeypatch):
    fake = install_public_tenant_data(app_module, monkeypatch)

    assert client.get("/t/not-a-tenant/asset/TENANT-ONE-ASSET").status_code == 404
    assert fake.operations == []

    assert client.get(f"/t/{UNREGISTERED_TENANT}/asset/UNREGISTERED-ASSET").status_code == 404
    assert [operation["table"] for operation in fake.operations] == ["tenants"]


def test_generated_public_asset_urls_include_validated_tenant_boundary(app_module):
    view_url = app_module.build_tenant_public_asset_url(TENANT_TWO, "HELP UKR/0001")
    json_url = app_module.build_tenant_public_asset_url(
        TENANT_TWO,
        "HELP UKR/0001",
        view=False,
    )

    assert view_url.endswith(f"/t/{TENANT_TWO}/view/HELP%20UKR%2F0001")
    assert json_url.endswith(f"/t/{TENANT_TWO}/asset/HELP%20UKR%2F0001")
