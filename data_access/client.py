import os
from typing import Optional

from supabase import create_client


class UnconfiguredSupabaseClient:
    """Test-safe placeholder that prevents accidental live database access."""

    def table(self, table_name: str):
        raise RuntimeError(
            f"Supabase is not configured for tests; attempted to access table '{table_name}'."
        )

    @property
    def storage(self):
        raise RuntimeError("Supabase storage is not configured for tests.")


def is_test_mode() -> bool:
    return os.getenv("INVENTORY_TEST_MODE") == "1"


def get_supabase_client(supabase_url: Optional[str], supabase_key: Optional[str]):
    if is_test_mode():
        return UnconfiguredSupabaseClient()
    if supabase_url and supabase_key:
        return create_client(supabase_url, supabase_key)
    raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set.")

