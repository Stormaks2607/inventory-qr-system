import os
from typing import Optional


def clean_env_value(name: str) -> Optional[str]:
    value = os.getenv(name)
    if value is None:
        return None
    return value.strip().strip("\"'")


def normalize_base_url(value: str) -> str:
    return value.strip().rstrip("/")


def is_test_mode() -> bool:
    return os.getenv("INVENTORY_TEST_MODE") == "1"


def get_public_base_url() -> str:
    configured = clean_env_value("PUBLIC_BASE_URL")
    if configured:
        return normalize_base_url(configured)
    if is_test_mode():
        return "http://testserver"
    raise RuntimeError("PUBLIC_BASE_URL must be set outside INVENTORY_TEST_MODE.")


def get_internal_api_base_url() -> str:
    configured = clean_env_value("INTERNAL_API_BASE_URL") or clean_env_value("PUBLIC_BASE_URL")
    if configured:
        return normalize_base_url(configured)
    if is_test_mode():
        return "http://testserver"
    raise RuntimeError("INTERNAL_API_BASE_URL or PUBLIC_BASE_URL must be set for bot API access.")
