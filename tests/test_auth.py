from types import SimpleNamespace


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

