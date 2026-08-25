import os
from dataclasses import dataclass
from typing import Optional
from uuid import UUID


TENANT_ONE_ID = "00000000-0000-4000-8000-000000000001"


class TenantContextError(RuntimeError):
    """Raised when the application cannot resolve a trusted tenant context."""


@dataclass(frozen=True)
class TenantContext:
    tenant_id: str


def is_test_mode() -> bool:
    return os.getenv("INVENTORY_TEST_MODE") == "1"


def clean_env_value(name: str) -> Optional[str]:
    value = os.getenv(name)
    if value is None:
        return None
    return value.strip().strip("\"'")


def get_default_tenant_id() -> str:
    tenant_id = clean_env_value("DEFAULT_TENANT_ID")
    if tenant_id:
        return normalize_tenant_uuid(tenant_id)
    if is_test_mode():
        return normalize_tenant_uuid(TENANT_ONE_ID)
    raise TenantContextError("DEFAULT_TENANT_ID must be configured outside INVENTORY_TEST_MODE.")


def resolve_tenant_context() -> TenantContext:
    return TenantContext(tenant_id=get_default_tenant_id())


def normalize_tenant_uuid(value: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError) as exc:
        raise TenantContextError("Tenant ID must be a valid UUID.") from exc
