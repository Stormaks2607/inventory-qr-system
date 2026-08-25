from data_access import client as client_module


def test_test_mode_never_creates_configured_supabase_client(monkeypatch):
    monkeypatch.setenv("INVENTORY_TEST_MODE", "1")

    def fail_if_called(*args, **kwargs):
        raise AssertionError("create_client must not be called in test mode")

    monkeypatch.setattr(client_module, "create_client", fail_if_called)

    client = client_module.get_supabase_client(
        "https://plausible-project.supabase.co",
        "plausible-secret-key",
    )

    assert isinstance(client, client_module.UnconfiguredSupabaseClient)


def test_app_import_keeps_supabase_credentials_empty(app_module):
    assert app_module.SUPABASE_URL == ""
    assert app_module.SUPABASE_KEY == ""
    assert isinstance(app_module.supabase, client_module.UnconfiguredSupabaseClient)
