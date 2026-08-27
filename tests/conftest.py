import importlib
import os
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


os.environ["INVENTORY_TEST_MODE"] = "1"
os.environ["SUPABASE_URL"] = ""
os.environ["SUPABASE_KEY"] = ""
os.environ["TELEGRAM_WEBHOOK_SECRET"] = ""
os.environ.pop("PUBLIC_BASE_URL", None)
os.environ.pop("INTERNAL_API_BASE_URL", None)


@pytest.fixture
def app_module():
    module = importlib.import_module("app")
    return module


@pytest.fixture
def client(app_module):
    from fastapi.testclient import TestClient

    with TestClient(app_module.app) as test_client:
        yield test_client

