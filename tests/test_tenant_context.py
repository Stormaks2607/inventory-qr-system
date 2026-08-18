import pytest

from data_access import tenant


def test_tenant_context_uses_configured_default_tenant(monkeypatch):
    monkeypatch.setenv("DEFAULT_TENANT_ID", "00000000-0000-4000-8000-000000000123")
    monkeypatch.delenv("INVENTORY_TEST_MODE", raising=False)

    context = tenant.resolve_tenant_context()

    assert context.tenant_id == "00000000-0000-4000-8000-000000000123"


def test_tenant_context_uses_tenant_one_in_test_mode(monkeypatch):
    monkeypatch.delenv("DEFAULT_TENANT_ID", raising=False)
    monkeypatch.setenv("INVENTORY_TEST_MODE", "1")

    context = tenant.resolve_tenant_context()

    assert context.tenant_id == tenant.TENANT_ONE_ID


def test_tenant_context_fails_closed_without_default_outside_test(monkeypatch):
    monkeypatch.delenv("DEFAULT_TENANT_ID", raising=False)
    monkeypatch.delenv("INVENTORY_TEST_MODE", raising=False)

    with pytest.raises(tenant.TenantContextError):
        tenant.resolve_tenant_context()
