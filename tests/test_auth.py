from types import SimpleNamespace

import pytest


TENANT_ONE_ID = "00000000-0000-4000-8000-000000000001"
TENANT_TWO_ID = "00000000-0000-4000-8000-000000000002"


class DummyUrl:
    def __init__(self, path="/admin", query=""):
        self.path = path
        self.query = query


def make_request(app_module, *, path="/admin", method="GET", session=None):
    return SimpleNamespace(
        session=session or {},
        method=method,
        url=DummyUrl(path=path),
    )


def test_role_normalization(app_module):
    assert app_module.normalize_account_role("ADMIN") == "admin"
    assert app_module.normalize_account_role("asset_manager") == "asset_manager"
    assert app_module.normalize_account_role("unknown") == "employee"


def test_admin_role_permissions(app_module):
    admin = make_request(app_module, session={"admin_authenticated": True, "admin_role": "admin"})
    manager = make_request(app_module, session={"admin_authenticated": True, "admin_role": "asset_manager"})
    viewer = make_request(app_module, session={"admin_authenticated": True, "admin_role": "viewer"})

    assert app_module.admin_role_can_manage_system(admin) is True
    assert app_module.admin_role_can_write(manager) is True
    assert app_module.admin_role_can_sync_export(manager) is True
    assert app_module.admin_role_can_sync_import(manager) is False
    assert app_module.admin_role_can_write(viewer) is False


def test_viewer_is_blocked_from_mutating_admin_routes(app_module):
    request = make_request(
        app_module,
        path="/admin/assets/123/assignment",
        method="POST",
        session={"admin_authenticated": True, "admin_role": "viewer"},
    )
    response = app_module.require_admin(request)
    assert response.status_code == 303
    assert response.headers["location"] == "/admin"
    assert request.session["admin_flash"]["message"] == "Viewer role has read-only access."


def test_unauthenticated_admin_redirects_to_login(app_module):
    request = make_request(app_module, path="/admin/assets")
    response = app_module.require_admin(request)
    assert response.status_code == 303
    assert response.headers["location"].startswith("/admin/login")


def test_password_hash_roundtrip(app_module):
    hashed = app_module.hash_password("correct horse battery staple")
    assert app_module.verify_password("correct horse battery staple", hashed) is True
    assert app_module.verify_password("wrong", hashed) is False


def test_environment_admin_login_stores_default_tenant(app_module):
    request = make_request(app_module, path="/admin/login", method="POST")

    response = app_module.admin_login_submit(
        request,
        username=app_module.ADMIN_USERNAME,
        password=app_module.ADMIN_PASSWORD,
        next="/admin",
    )

    assert response.status_code == 303
    assert request.session[app_module.TENANT_SESSION_KEY] == app_module.DEFAULT_TENANT_ID


def test_account_login_stores_person_tenant(app_module, monkeypatch):
    class NoopQuery:
        def update(self, payload):
            return self

        def eq(self, field_name, value):
            return self

        def execute(self):
            return SimpleNamespace(data=[])

    class NoopSupabase:
        def table(self, table_name):
            return NoopQuery()

    request = make_request(app_module, path="/account/login", method="POST")
    person = {
        "person_id": 202,
        "tenant_id": TENANT_TWO_ID,
        "name_eng": "Tenant Two User",
        "email": "user@tenant-two.example",
        "is_active": True,
        "account_role": "employee",
        "password_hash": app_module.hash_password("secret"),
    }
    monkeypatch.setattr(app_module, "get_account_login_person_by_email", lambda email: person)
    monkeypatch.setattr(app_module, "supabase", NoopSupabase())

    response = app_module.account_login_submit(
        request,
        email=person["email"],
        password="secret",
        next="/account",
    )

    assert response.status_code == 303
    assert request.session[app_module.TENANT_SESSION_KEY] == TENANT_TWO_ID
    assert request.session["account_person_id"] == 202


def test_account_promoted_admin_keeps_account_tenant(app_module, monkeypatch):
    request = make_request(
        app_module,
        path="/account",
        session={
            "account_person_id": 202,
            "account_role": "admin",
            "tenant_id": TENANT_TWO_ID,
        },
    )
    person = {
        "person_id": 202,
        "tenant_id": TENANT_TWO_ID,
        "name_eng": "Tenant Two Admin",
        "is_active": True,
        "account_role": "admin",
    }
    monkeypatch.setattr(app_module, "get_account_person", lambda request: person)

    response = app_module.account_home(request)

    assert response.headers["location"] == "/admin"
    assert request.session[app_module.TENANT_SESSION_KEY] == TENANT_TWO_ID
    assert request.session["admin_login_source"] == "account"


def test_authenticated_session_tenant_overrides_default(app_module):
    request = make_request(
        app_module,
        session={"admin_authenticated": True, "tenant_id": TENANT_TWO_ID},
    )

    assert app_module.get_current_tenant_id(request) == TENANT_TWO_ID


def test_legacy_unauthenticated_tenant_falls_back_to_default(app_module):
    request = make_request(app_module, session={"tenant_id": TENANT_TWO_ID})

    assert app_module.get_current_tenant_id(None) == app_module.DEFAULT_TENANT_ID
    assert app_module.get_current_tenant_id(request) == app_module.DEFAULT_TENANT_ID


def test_authenticated_session_missing_tenant_fails_closed(app_module):
    request = make_request(app_module, session={"admin_authenticated": True})

    with pytest.raises(app_module.TenantContextError, match="missing tenant_id"):
        app_module.get_current_tenant_id(request)


def test_authenticated_session_malformed_tenant_fails_closed(app_module):
    request = make_request(
        app_module,
        session={"account_person_id": 202, "tenant_id": "not-a-uuid"},
    )

    with pytest.raises(app_module.TenantContextError):
        app_module.get_current_tenant_id(request)


def test_get_account_person_rejects_tenant_mismatch(app_module, monkeypatch):
    request = make_request(
        app_module,
        session={
            "account_person_id": 202,
            "account_display_name": "Tenant Two User",
            "account_role": "employee",
            "tenant_id": TENANT_TWO_ID,
        },
    )
    monkeypatch.setattr(
        app_module,
        "get_person_by_id",
        lambda person_id, request=None: {
            "person_id": person_id,
            "tenant_id": TENANT_ONE_ID,
            "is_active": True,
        },
    )

    assert app_module.get_account_person(request) is None
    assert "account_person_id" not in request.session
    assert app_module.TENANT_SESSION_KEY not in request.session


def test_logout_removes_tenant_state(app_module):
    account_request = make_request(
        app_module,
        session={"account_person_id": 202, "tenant_id": TENANT_TWO_ID},
    )
    app_module.account_logout(account_request)
    assert app_module.TENANT_SESSION_KEY not in account_request.session

    admin_request = make_request(
        app_module,
        session={"admin_authenticated": True, "tenant_id": TENANT_ONE_ID},
    )
    app_module.admin_logout(admin_request)
    assert admin_request.session == {}


def test_tenant_helpers_use_request_bound_tenant(app_module):
    class RecordingQuery:
        def __init__(self):
            self.filters = []

        def eq(self, field_name, value):
            self.filters.append((field_name, value))
            return self

    request = make_request(
        app_module,
        session={"admin_authenticated": True, "tenant_id": TENANT_TWO_ID},
    )
    query = RecordingQuery()

    assert app_module.tenant_filter(query, request=request) is query
    assert query.filters == [("tenant_id", TENANT_TWO_ID)]
    assert app_module.add_tenant_id({"asset_id": 1}, request=request)["tenant_id"] == TENANT_TWO_ID
    assert app_module.add_tenant_id(
        {"asset_id": 1, "tenant_id": TENANT_ONE_ID},
        request=request,
    )["tenant_id"] == TENANT_TWO_ID

